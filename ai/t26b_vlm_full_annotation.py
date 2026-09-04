# -*- coding: utf-8 -*-
r"""T26b: VLM全量标注管线 — SiliconFlow Qwen3-VL-8B 标注全部65714帧。

核心设计:
  1. 增量checkpoint: 每100帧追加写入, 不加载全量到内存
  2. 断点续传: 启动时扫描已标注帧, 跳过已完成的
  3. 教师参考: 伪标签作为参考通道, 用于一致性统计
  4. 进度日志: 每100帧打印进度+ETA+成本
  5. 容错: API失败自动重试, 图片损坏跳过

产物:
  D:\aot_corpus\vlm_full\results.jsonl   — 增量标注结果(每行一帧)
  D:\aot_corpus\vlm_full\ckpt.json       — 断点续传索引
  D:\aot_corpus\vlm_full\report.json     — 最终质量报告
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import io
from pathlib import Path
from typing import Optional

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# === 路径配置 ===
FRAMES_DIR = Path(r"D:\aot_corpus\frames")
PSEUDO_LABELS = Path(r"D:\aot_corpus\pseudolabels.json")
OUTPUT_DIR = Path(r"D:\aot_corpus\vlm_full")
RESULTS_FILE = OUTPUT_DIR / "results.jsonl"
CKPT_FILE = OUTPUT_DIR / "ckpt.json"
REPORT_FILE = OUTPUT_DIR / "report.json"
LOG_FILE = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\logs\t26b_vlm.log")

# === API配置 (SiliconFlow + Qwen3-VL-8B-Instruct) ===
VLM_API_KEY = os.environ.get("SILICONFLOW_API_KEY")
VLM_BASE_URL = "https://api.siliconflow.cn/v1"
VLM_MODEL = "Qwen/Qwen3-VL-8B-Instruct"
MAX_RETRIES = 3
CKPT_INTERVAL = 100  # 每100帧保存checkpoint

# === IP候选列表 ===
IP_CANDIDATES = "进击的巨人、火影忍者、海贼王、鬼灭之刃、咒术回战、链锯人、FATE、黑岩射手、地缚少年花子君、无限滑板、灼眼的夏娜、猫和老鼠、时光代理人、灵笼、赛博朋克：边缘行者、原神、斩·赤红之瞳、某科学的超电磁炮、JOJO的奇妙冒险、Move、抽烟猫、浪客行、龙族、K、间谍过家家、葬送的芙莉莲、药屋少女的呢喃、我推的孩子、蓝色监狱、排球少年、我的英雄学院、Re:从零开始的异世界生活、为美好的世界献上祝福、无职转生、关于我转生变成史莱姆这档事、Overlord、一拳超人、灵能百分百、钢之炼金术师、死亡笔记、Code Geass、EVA、星际牛仔、攻壳机动队、心理测量者、来自深渊、迷宫饭、斗罗大陆、斗破苍穹、完美世界、凡人修仙传、一人之下、雾山五行、百妖谱、天官赐福、魔道祖师、伍六七、银魂、全职猎人、幽游白书、龙珠、数码宝贝、宝可梦、游戏王、名侦探柯南、蜡笔小新、哆啦A梦、美少女战士、魔卡少女樱、轻音少女、凉宫春日的忧郁、命运石之门、罪恶王冠、刀剑神域、在下坂本有何贵干、齐木楠雄的灾难、日常、月刊少女野崎同学、冰菓、黑之契约者、天元突破、新海诚、千与千寻、龙猫、风之谷、幽灵公主、哈尔的移动城堡、铃芽之旅、你的名字、天气之子、Promare、SSSS.GRIDMAN"

ANNOTATE_PROMPT = """你是一个专业的动漫识别专家。请分析这张图片：

1. 这张图来自哪个动漫作品？请从以下候选中选择（如果都不像，可以写"其他"并说明）：
   %s
2. 画面中有哪些可辨识的角色？（如果看不清就写[]）
3. 这是什么类型的场景？（从以下选一个: battle/daily/dialog/flashback/landscape/ceremony/emotional/comedy）
4. 画面情绪基调？（从以下选一个: hot/warm/sad/tense/funny）

请严格返回JSON格式（不要其他文字，不要markdown代码块）:
{"ip_top3": [{"name": "动漫名", "confidence": 0.85}, {"name": "...", "confidence": 0.6}, {"name": "...", "confidence": 0.4}], "characters": ["角色1", "角色2"], "scene_type": "battle", "mood": "hot"}

重要:
- confidence必须真实反映你的确信程度: 非常确定=0.9-1.0, 比较确定=0.7-0.9, 有点像=0.5-0.7, 不太确定=0.3-0.5
- 不要给所有结果都打0.98以上的高分
- 如果完全看不出是哪个动漫，ip_top3第一个写"其他"，confidence写0.3以下
- 动漫名用中文""" % IP_CANDIDATES


def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_pseudolabel_index():
    """加载伪标签为 {frame_name: {ip, confidence}} 索引"""
    idx = {}
    if PSEUDO_LABELS.exists():
        pseudo = json.loads(PSEUDO_LABELS.read_text(encoding="utf-8"))
        for p in pseudo:
            name = Path(p.get("frame_path", p.get("frame", ""))).name
            idx[name] = {
                "ip": p.get("ip", ""),
                "confidence": p.get("confidence", 0),
            }
    _log(f"伪标签索引: {len(idx)}帧")
    return idx


def load_checkpoint():
    """加载断点续传信息"""
    done = set()
    total_results = 0
    total_cost = 0.0
    stats = {"agree": 0, "disagree": 0, "no_vlm": 0, "no_teacher": 0}

    if CKPT_FILE.exists():
        try:
            ckpt = json.loads(CKPT_FILE.read_text(encoding="utf-8"))
            done = set(ckpt.get("done_frames", []))
            total_results = ckpt.get("total_results", 0)
            total_cost = ckpt.get("total_cost", 0.0)
            stats = ckpt.get("stats", stats)
            _log(f"断点续传: {len(done)}帧已完成")
        except Exception as e:
            _log(f"Checkpoint加载失败: {e}, 从头开始")

    # 也扫描results.jsonl确认
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        r = json.loads(line)
                        done.add(r.get("frame_name", ""))
                        total_results += 1
                    except Exception:
                        pass
        _log(f"JSONL扫描确认: {len(done)}帧已标注")

    return done, total_results, total_cost, stats


def save_checkpoint(done_frames: set, total_results: int, total_cost: float, stats: dict):
    """保存checkpoint（只存索引，不存全量结果）"""
    ckpt = {
        "done_frames": list(done_frames),
        "total_results": total_results,
        "total_cost": round(total_cost, 4),
        "stats": stats,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    CKPT_FILE.write_text(json.dumps(ckpt, ensure_ascii=False), encoding="utf-8")


def annotate_frame(client, img_path: str) -> Optional[dict]:
    """标注单帧"""
    try:
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()

        for attempt in range(MAX_RETRIES):
            try:
                resp = client.chat.completions.create(
                    model=VLM_MODEL,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": ANNOTATE_PROMPT},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/jpeg;base64,{img_data}",
                                "detail": "low"
                            }}
                        ]
                    }],
                    max_tokens=500,
                    temperature=0.1,
                )
                text = resp.choices[0].message.content.strip()

                # 成本估算
                usage = resp.usage
                cost = (usage.prompt_tokens * 0.15 + usage.completion_tokens * 0.60) / 1e6

                # 解析JSON
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(lines[1:])
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

                result = json.loads(text)
                return result, cost

            except json.JSONDecodeError:
                if attempt == MAX_RETRIES - 1:
                    return None, 0.0
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    _log(f"  API错误: {e}")
                    return None, 0.0
                time.sleep(2 * (attempt + 1))
    except Exception as e:
        _log(f"  读图失败: {e}")
        return None, 0.0


def run_full_annotation():
    """Phase 2b: 全量标注"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    _log("=" * 60)
    _log("T26b: VLM全量标注 (SiliconFlow Qwen3-VL-8B)")
    _log("=" * 60)

    # 1. 扫描所有帧
    _log("[1/4] 扫描帧文件...")
    all_frames = sorted(FRAMES_DIR.rglob("*.jpg"))
    _log(f"  总帧数: {len(all_frames)}")

    # 2. 加载伪标签索引
    _log("[2/4] 加载伪标签索引...")
    pseudo_idx = load_pseudolabel_index()

    # 3. 加载checkpoint
    _log("[3/4] 加载断点续传...")
    done_frames, total_results, total_cost, stats = load_checkpoint()
    remaining = [f for f in all_frames if f.name not in done_frames]
    _log(f"  剩余: {len(remaining)}帧 (总{len(all_frames)}, 已完成{len(done_frames)})")

    if not remaining:
        _log("全部完成！无需继续标注。")
        return

    # 4. 初始化API
    _log("[4/4] 初始化VLM API...")
    import openai
    client = openai.OpenAI(api_key=VLM_API_KEY, base_url=VLM_BASE_URL)
    _log(f"  模型: {VLM_MODEL}")
    _log(f"  BaseURL: {VLM_BASE_URL}")

    # 5. 开始标注
    _log(f"\n开始标注 {len(remaining)} 帧...")
    t0 = time.time()
    t_epoch = time.time()
    results_file = open(RESULTS_FILE, "a", encoding="utf-8")

    try:
        for i, frame_path in enumerate(remaining):
            frame_name = frame_path.name

            # VLM标注
            vlm_result, cost = annotate_frame(client, str(frame_path))
            total_cost += cost

            # 提取VLM结果
            if vlm_result and vlm_result.get("ip_top3"):
                vlm_ip = vlm_result["ip_top3"][0].get("name", "")
                vlm_conf = vlm_result["ip_top3"][0].get("confidence", 0)
            else:
                vlm_ip = ""
                vlm_conf = 0
                stats["no_vlm"] += 1

            # 教师参考
            teacher_info = pseudo_idx.get(frame_name, {})
            teacher_ip = teacher_info.get("ip", "")
            teacher_conf = teacher_info.get("confidence", 0)

            if not teacher_ip:
                stats["no_teacher"] += 1

            # 一致性判断
            if vlm_ip and teacher_ip:
                if vlm_ip == teacher_ip:
                    stats["agree"] += 1
                    agree = True
                else:
                    stats["disagree"] += 1
                    agree = False
            else:
                agree = None

            # 写入结果
            record = {
                "frame_name": frame_name,
                "frame_path": str(frame_path),
                "vlm_ip": vlm_ip,
                "vlm_confidence": vlm_conf,
                "vlm_detail": vlm_result,
                "teacher_ip": teacher_ip,
                "teacher_confidence": teacher_conf,
                "agree": agree,
                "scene_type": vlm_result.get("scene_type", "") if vlm_result else "",
                "mood": vlm_result.get("mood", "") if vlm_result else "",
                "characters": vlm_result.get("characters", []) if vlm_result else [],
            }
            results_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            results_file.flush()

            done_frames.add(frame_name)
            total_results += 1

            # 进度日志
            if (i + 1) % 100 == 0:
                elapsed = time.time() - t0
                rate = total_results / elapsed
                eta = (len(remaining) - i - 1) / max(rate, 0.001)
                _log(f"  进度: {total_results}/{len(all_frames)} ({100*total_results/len(all_frames):.1f}%) | "
                     f"{rate:.2f}帧/s | ETA {eta/3600:.1f}h | cost=${total_cost:.2f} | "
                     f"一致率={stats['agree']/max(stats['agree']+stats['disagree'],1):.3f}")

            # 断点保存
            if (i + 1) % CKPT_INTERVAL == 0:
                save_checkpoint(done_frames, total_results, total_cost, stats)

    finally:
        results_file.close()

    # 最终保存
    save_checkpoint(done_frames, total_results, total_cost, stats)

    elapsed = time.time() - t0
    agree_rate = stats["agree"] / max(stats["agree"] + stats["disagree"], 1)

    _log(f"\n{'='*60}")
    _log(f"全量标注完成!")
    _log(f"  总帧数: {len(all_frames)}")
    _log(f"  已标注: {total_results}")
    _log(f"  耗时: {elapsed/3600:.1f}h ({elapsed:.0f}s)")
    _log(f"  平均速度: {total_results/elapsed:.2f}帧/s")
    _log(f"  总成本: ${total_cost:.2f}")
    _log(f"  一致率(VLM vs 教师): {agree_rate:.3f} ({stats['agree']}/{stats['agree']+stats['disagree']})")
    _log(f"  VLM无结果: {stats['no_vlm']}")
    _log(f"  无教师参考: {stats['no_teacher']}")
    _log(f"{'='*60}")

    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_frames": len(all_frames),
        "annotated": total_results,
        "elapsed_hours": round(elapsed / 3600, 2),
        "avg_speed_fps": round(total_results / elapsed, 2),
        "total_cost_usd": round(total_cost, 2),
        "agree_rate": round(agree_rate, 4),
        "stats": stats,
        "model": VLM_MODEL,
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"报告保存: {REPORT_FILE}")


if __name__ == "__main__":
    run_full_annotation()
