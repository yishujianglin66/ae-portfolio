# -*- coding: utf-8 -*-
r"""T26c: VLM并发标注管线 — 16线程并发 + 图片压缩加速。

相比T26b的改进:
  1. 16线程并发API调用 (ThreadPoolExecutor)
  2. 图片压缩到512px再base64编码 (减少80%传输量)
  3. 线程安全的文件写入 (Lock保护)
  4. 兼容T26b断点续传 (已有403帧不丢失)

速度预估:
  串行: ~0.01帧/秒 → 100小时
  16并发+压缩: ~0.5帧/秒 → ~36小时
  32并发+压缩: ~1.0帧/秒 → ~18小时

产物:
  D:\aot_corpus\vlm_full\results.jsonl   — 增量标注结果
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
import threading
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# === 路径配置 ===
FRAMES_DIR = Path(r"D:\aot_corpus\frames")
PSEUDO_LABELS = Path(r"D:\aot_corpus\pseudolabels.json")
OUTPUT_DIR = Path(r"D:\aot_corpus\vlm_full")
RESULTS_FILE = OUTPUT_DIR / "results.jsonl"
CKPT_FILE = OUTPUT_DIR / "ckpt.json"
REPORT_FILE = OUTPUT_DIR / "report.json"
LOG_FILE = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\logs\t26c_vlm.log")

# === API配置 ===
VLM_API_KEY = os.environ.get("SILICONFLOW_API_KEY")
VLM_BASE_URL = "https://api.siliconflow.cn/v1"
VLM_MODEL = "Qwen/Qwen3-VL-8B-Instruct"
MAX_RETRIES = 3
CKPT_INTERVAL = 100

# === 并发配置 ===
NUM_WORKERS = int(os.environ.get("VLM_WORKERS", "16"))  # 并发线程数
IMG_MAX_SIZE = 512  # 图片压缩到最大512px

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

# === 全局锁和计数器 ===
_write_lock = threading.Lock()
_progress_lock = threading.Lock()
_total_results = 0
_total_cost = 0.0
_stats = {"agree": 0, "disagree": 0, "no_vlm": 0, "no_teacher": 0}
_results_file = None
_done_frames = set()
_t0 = 0.0
_last_log_count = 0


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


def compress_image(img_path: str, max_size: int = IMG_MAX_SIZE) -> str:
    """压缩图片到max_size像素并返回base64编码字符串"""
    from PIL import Image
    img = Image.open(img_path)
    # 等比缩放
    w, h = img.size
    if max(w, h) > max_size:
        scale = max_size / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    # 转RGB（处理RGBA/P模式）
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def load_pseudolabel_index():
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

    # 修复: total_results以实际done帧数为准，避免重复计数
    total_results = len(done)

    return done, total_results, total_cost, stats


def save_checkpoint(done_frames: set, total_results: int, total_cost: float, stats: dict):
    ckpt = {
        "done_frames": list(done_frames),
        "total_results": total_results,
        "total_cost": round(total_cost, 4),
        "stats": stats,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    CKPT_FILE.write_text(json.dumps(ckpt, ensure_ascii=False), encoding="utf-8")


def annotate_single_frame(client, img_path: str) -> Tuple[Optional[dict], float]:
    """标注单帧（线程安全）"""
    try:
        img_b64 = compress_image(img_path)

        for attempt in range(MAX_RETRIES):
            try:
                resp = client.chat.completions.create(
                    model=VLM_MODEL,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": ANNOTATE_PROMPT},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/jpeg;base64,{img_b64}",
                                "detail": "low"
                            }}
                        ]
                    }],
                    max_tokens=500,
                    temperature=0.1,
                    timeout=60,
                )
                text = resp.choices[0].message.content.strip()
                usage = resp.usage
                cost = (usage.prompt_tokens * 0.15 + usage.completion_tokens * 0.60) / 1e6

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
                    return None, 0.0
                time.sleep(2 * (attempt + 1))
    except Exception:
        return None, 0.0


def process_frame(client, frame_path: Path, pseudo_idx: dict) -> Optional[dict]:
    """处理单帧：标注 + 比对 + 写入（线程安全）"""
    global _total_results, _total_cost, _last_log_count

    frame_name = frame_path.name
    vlm_result, cost = annotate_single_frame(client, str(frame_path))

    if vlm_result and vlm_result.get("ip_top3"):
        vlm_ip = vlm_result["ip_top3"][0].get("name", "")
        vlm_conf = vlm_result["ip_top3"][0].get("confidence", 0)
    else:
        vlm_ip = ""
        vlm_conf = 0

    teacher_info = pseudo_idx.get(frame_name, {})
    teacher_ip = teacher_info.get("ip", "")
    teacher_conf = teacher_info.get("confidence", 0)

    # 一致性
    agree = None
    if vlm_ip and teacher_ip:
        agree = (vlm_ip == teacher_ip)

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

    # 线程安全写入
    with _write_lock:
        global _results_file, _done_frames
        _results_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        _results_file.flush()
        _done_frames.add(frame_name)

    with _progress_lock:
        _total_results += 1
        _total_cost += cost
        if vlm_ip and teacher_ip:
            if agree:
                _stats["agree"] += 1
            else:
                _stats["disagree"] += 1
        elif not vlm_ip:
            _stats["no_vlm"] += 1
        if not teacher_ip:
            _stats["no_teacher"] += 1

        current = _total_results
        if not teacher_ip:
            _stats["no_teacher"] += 0  # already counted

    # 进度日志（每100帧）
    with _progress_lock:
        should_log = (_total_results - _last_log_count) >= 100
        if should_log:
            _last_log_count = _total_results
            cur_total = _total_results
            cur_cost = _total_cost
            cur_stats = dict(_stats)

    if should_log:
        elapsed = time.time() - _t0
        rate = cur_total / max(elapsed, 1)
        remaining_est = (len(all_frames_global) - cur_total) / max(rate, 0.001)
        agree_rate = cur_stats["agree"] / max(cur_stats["agree"] + cur_stats["disagree"], 1)
        _log(f"  进度: {cur_total}/{len(all_frames_global)} ({100*cur_total/len(all_frames_global):.1f}%) | "
             f"{rate:.2f}帧/s | ETA {remaining_est/3600:.1f}h | cost=${cur_cost:.2f} | "
             f"一致率={agree_rate:.3f} | workers={NUM_WORKERS}")

    return record


# 全局变量供进度日志使用
all_frames_global = []


def run_concurrent_annotation():
    global _results_file, _done_frames, _t0, _total_results, _total_cost, all_frames_global

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    _log("=" * 60)
    _log(f"T26c: VLM并发标注 ({NUM_WORKERS}线程 + 图片压缩{IMG_MAX_SIZE}px)")
    _log("=" * 60)

    # 1. 扫描帧
    _log("[1/4] 扫描帧文件...")
    all_frames = sorted(FRAMES_DIR.rglob("*.jpg"))
    all_frames_global = all_frames
    _log(f"  总帧数: {len(all_frames)}")

    # 2. 伪标签
    _log("[2/4] 加载伪标签索引...")
    pseudo_idx = load_pseudolabel_index()

    # 3. 断点续传
    _log("[3/4] 加载断点续传...")
    done_frames, total_results, total_cost, stats = load_checkpoint()
    remaining = [f for f in all_frames if f.name not in done_frames]
    _log(f"  剩余: {len(remaining)}帧 (已完成{len(done_frames)})")

    if not remaining:
        _log("全部完成！")
        return

    # 4. 初始化API（每个线程需要独立的client）
    _log(f"[4/4] 初始化VLM API ({NUM_WORKERS}并发)...")
    import openai
    import httpx
    # 关键修复: 设置60秒超时，防止线程永远挂起
    client = openai.OpenAI(
        api_key=VLM_API_KEY,
        base_url=VLM_BASE_URL,
        timeout=httpx.Timeout(60.0, connect=10.0),
    )

    # 设置全局变量
    _t0 = time.time()
    _total_results = total_results
    _total_cost = total_cost
    _done_frames = done_frames

    _log(f"\n开始并发标注 {len(remaining)} 帧 (workers={NUM_WORKERS})...")
    _log(f"预计速度: {NUM_WORKERS}x并发 ≈ {NUM_WORKERS * 0.1:.1f}帧/s")
    _log(f"预计耗时: {len(remaining) / max(NUM_WORKERS * 0.1, 0.01) / 3600:.1f}h")

    _results_file = open(RESULTS_FILE, "a", encoding="utf-8")

    try:
        last_progress_time = time.time()
        last_progress_count = _total_results
        STALL_TIMEOUT = 300  # 5分钟无进度视为卡死

        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = {}
            for frame_path in remaining:
                future = executor.submit(process_frame, client, frame_path, pseudo_idx)
                futures[future] = frame_path

            # 等待完成，同时监控进度
            completed = 0
            for future in as_completed(futures):
                try:
                    future.result(timeout=120)  # 单帧最多等2分钟
                except Exception as e:
                    frame_path = futures[future]
                    _log(f"  帧处理失败 {frame_path.name}: {e}")
                completed += 1

                # 定期保存checkpoint
                if completed % CKPT_INTERVAL == 0:
                    with _write_lock:
                        save_checkpoint(_done_frames, _total_results, _total_cost, _stats)

                # 看门狗: 检测卡死
                if completed % 50 == 0:
                    with _progress_lock:
                        current_count = _total_results
                    if current_count > last_progress_count:
                        last_progress_count = current_count
                        last_progress_time = time.time()
                    elif time.time() - last_progress_time > STALL_TIMEOUT:
                        _log(f"  [看门狗] {STALL_TIMEOUT}秒无进度，自动退出！已处理{completed}帧")
                        _log(f"  当前JSONL行数可断点续传，请重启脚本")
                        raise RuntimeError("Stall detected - auto restart needed")

    finally:
        _results_file.close()

    # 最终保存
    save_checkpoint(_done_frames, _total_results, _total_cost, _stats)

    elapsed = time.time() - _t0
    agree_rate = _stats["agree"] / max(_stats["agree"] + _stats["disagree"], 1)

    _log(f"\n{'='*60}")
    _log(f"并发标注完成!")
    _log(f"  总帧数: {len(all_frames)}")
    _log(f"  已标注: {_total_results}")
    _log(f"  耗时: {elapsed/3600:.1f}h ({elapsed:.0f}s)")
    _log(f"  平均速度: {_total_results/max(elapsed,1):.2f}帧/s")
    _log(f"  总成本: ${_total_cost:.2f}")
    _log(f"  一致率: {agree_rate:.3f}")
    _log(f"  并发数: {NUM_WORKERS}")
    _log(f"{'='*60}")

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_frames": len(all_frames),
        "annotated": _total_results,
        "elapsed_hours": round(elapsed / 3600, 2),
        "avg_speed_fps": round(_total_results / max(elapsed, 1), 2),
        "total_cost_usd": round(_total_cost, 2),
        "agree_rate": round(agree_rate, 4),
        "stats": _stats,
        "model": VLM_MODEL,
        "workers": NUM_WORKERS,
        "img_max_size": IMG_MAX_SIZE,
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"报告保存: {REPORT_FILE}")


if __name__ == "__main__":
    run_concurrent_annotation()
