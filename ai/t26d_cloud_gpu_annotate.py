# -*- coding: utf-8 -*-
r"""T26d: 云GPU本地VLM推理标注 — 在AutoDL云GPU上直接运行Qwen3-VL-8B。

核心优势:
  1. 无API速率限制 — 本地推理，速度仅受GPU性能限制
  2. 批量推理 — GPU利用率最大化
  3. 无网络延迟 — 不需要上传图片

性能预估:
  RTX 4090 (24GB): ~2帧/s → 65714帧 ≈ 9h
  A100 (80GB): ~4帧/s → 65714帧 ≈ 4.5h

用法:
  1. 在AutoDL上创建实例 (推荐A100 80GB或RTX 4090)
  2. 运行 setup_cloud.sh 安装依赖 + 上传帧数据
  3. python t26d_cloud_gpu_annotate.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.torch_runtime import infer_ctx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# === 路径配置 (AutoDL环境) ===
FRAMES_DIR = Path(os.environ.get("FRAMES_DIR", "/root/data/frames"))
PSEUDO_LABELS = Path(os.environ.get("PSEUDO_LABELS", "/root/data/pseudolabels.json"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/root/data/vlm_full"))
RESULTS_FILE = OUTPUT_DIR / "results.jsonl"
CKPT_FILE = OUTPUT_DIR / "ckpt.json"
REPORT_FILE = OUTPUT_DIR / "report.json"

# === 模型配置 ===
MODEL_NAME = os.environ.get("VLM_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "4"))
IMG_MAX_SIZE = 512
CKPT_INTERVAL = 200

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


def load_model():
    """加载Qwen3-VL-8B模型到GPU"""
    _log(f"加载模型: {MODEL_NAME}")
    import torch
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_NAME, torch_dtype="auto", device_map="auto",
    )
    processor = AutoProcessor.from_pretrained(MODEL_NAME)

    _log(f"  GPU: {torch.cuda.get_device_name(0)}")
    _log(f"  VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")
    _log(f"  已用VRAM: {torch.cuda.memory_allocated() / 1e9:.1f} GB")
    return model, processor


def compress_image(img_path: str, max_size: int = IMG_MAX_SIZE):
    from PIL import Image
    img = Image.open(img_path)
    w, h = img.size
    if max(w, h) > max_size:
        scale = max_size / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def load_pseudolabel_index():
    idx = {}
    if PSEUDO_LABELS.exists():
        pseudo = json.loads(PSEUDO_LABELS.read_text(encoding="utf-8"))
        for p in pseudo:
            name = Path(p.get("frame_path", p.get("frame", ""))).name
            idx[name] = {"ip": p.get("ip", ""), "confidence": p.get("confidence", 0)}
    return idx


def load_checkpoint():
    done = set()
    total = 0
    if CKPT_FILE.exists():
        try:
            ckpt = json.loads(CKPT_FILE.read_text(encoding="utf-8"))
            done = set(ckpt.get("done_frames", []))
            total = ckpt.get("total_results", 0)
        except Exception:
            pass
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        r = json.loads(line)
                        done.add(r.get("frame_name", ""))
                        total += 1
                    except Exception:
                        pass
    return done, total


def save_checkpoint(done_frames, total):
    CKPT_FILE.write_text(json.dumps(
        {"done_frames": list(done_frames), "total_results": total,
         "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")},
        ensure_ascii=False), encoding="utf-8")


def parse_response(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
    if text.endswith("```"):
        text = text[:-3]
    try:
        return json.loads(text.strip())
    except Exception:
        return None


def run_cloud_annotation():
    import torch
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    _log("=" * 60)
    _log("T26d: 云GPU本地VLM推理标注")
    _log(f"  模型: {MODEL_NAME}, Batch: {BATCH_SIZE}")
    _log("=" * 60)

    # 1. 扫描帧
    all_frames = sorted(FRAMES_DIR.rglob("*.jpg"))
    _log(f"总帧数: {len(all_frames)}")

    # 2. 伪标签 + 断点
    pseudo_idx = load_pseudolabel_index()
    done_frames, total_results = load_checkpoint()
    remaining = [f for f in all_frames if f.name not in done_frames]
    _log(f"剩余: {len(remaining)}帧 (已完成{len(done_frames)})")

    if not remaining:
        _log("全部完成！")
        return

    # 3. 加载模型
    model, processor = load_model()

    # 4. 逐帧推理（GPU本地，无API限制）
    _log(f"开始推理 ({len(remaining)}帧)...")
    t0 = time.time()
    stats = {"agree": 0, "disagree": 0, "no_vlm": 0, "no_teacher": 0}
    results_file = open(RESULTS_FILE, "a", encoding="utf-8")

    try:
        for i, frame_path in enumerate(remaining):
            fname = frame_path.name
            try:
                img = compress_image(str(frame_path))
                messages = [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANNOTATE_PROMPT},
                        {"type": "image", "image": img},
                    ]
                }]
                text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                inputs = processor(text=[text], images=[img], padding=True, return_tensors="pt")
                inputs = {k: v.to(model.device) for k, v in inputs.items()}

                with infer_ctx():
                    output_ids = model.generate(**inputs, max_new_tokens=500, temperature=0.1)
                response = processor.decode(output_ids[0], skip_special_tokens=True)

                # 提取assistant回复
                assistant_start = response.rfind("\n")
                if assistant_start != -1:
                    result_text = response[assistant_start + 1:].strip()
                else:
                    result_text = response.strip()

                vlm_result = parse_response(result_text)

                if vlm_result and vlm_result.get("ip_top3"):
                    vlm_ip = vlm_result["ip_top3"][0].get("name", "")
                    vlm_conf = vlm_result["ip_top3"][0].get("confidence", 0)
                else:
                    vlm_ip = ""
                    vlm_conf = 0
                    stats["no_vlm"] += 1

                teacher_info = pseudo_idx.get(fname, {})
                teacher_ip = teacher_info.get("ip", "")
                teacher_conf = teacher_info.get("confidence", 0)
                if not teacher_ip:
                    stats["no_teacher"] += 1

                agree = None
                if vlm_ip and teacher_ip:
                    agree = (vlm_ip == teacher_ip)
                    if agree:
                        stats["agree"] += 1
                    else:
                        stats["disagree"] += 1

                record = {
                    "frame_name": fname,
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
                done_frames.add(fname)
                total_results += 1

            except Exception as e:
                _log(f"  处理失败 {fname}: {e}")

            # 进度日志
            if (i + 1) % 50 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / max(elapsed, 1)
                eta = (len(remaining) - i - 1) / max(rate, 0.001)
                agree_rate = stats["agree"] / max(stats["agree"] + stats["disagree"], 1)
                _log(f"  进度: {total_results}/{len(all_frames)} ({100*total_results/len(all_frames):.1f}%) | "
                     f"{rate:.2f}帧/s | ETA {eta/3600:.1f}h | 一致率={agree_rate:.3f}")

            # checkpoint
            if (i + 1) % CKPT_INTERVAL == 0:
                save_checkpoint(done_frames, total_results)

    finally:
        results_file.close()

    save_checkpoint(done_frames, total_results)
    elapsed = time.time() - t0
    agree_rate = stats["agree"] / max(stats["agree"] + stats["disagree"], 1)

    _log(f"\n{'='*60}")
    _log("云GPU标注完成!")
    _log(f"  总帧数: {len(all_frames)}")
    _log(f"  已标注: {total_results}")
    _log(f"  耗时: {elapsed/3600:.1f}h")
    _log(f"  速度: {total_results/max(elapsed,1):.2f}帧/s")
    _log(f"  一致率: {agree_rate:.3f}")
    _log(f"{'='*60}")

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_frames": len(all_frames),
        "annotated": total_results,
        "elapsed_hours": round(elapsed / 3600, 2),
        "avg_speed_fps": round(total_results / max(elapsed, 1), 2),
        "agree_rate": round(agree_rate, 4),
        "stats": stats,
        "model": MODEL_NAME,
        "gpu": torch.cuda.get_device_name(0),
        "batch_size": BATCH_SIZE,
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"报告: {REPORT_FILE}")


if __name__ == "__main__":
    run_cloud_annotation()