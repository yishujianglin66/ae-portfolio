#!/usr/bin/env python3
"""
ToriiGate-v0.4-2B 全库氛围标注 (包2 核心脚本)

对 shots_manifest.jsonl 里的每个镜头抽 1 帧 (镜头中点),
用 ToriiGate-v0.4-2B (Qwen2-VL 微调的动漫 captioning 专家) 输出三维氛围标签:
  - mood (情绪): intense/serene/somber/mysterious/joyful/neutral (6 类)
  - time (时间): day/night/dawn_dusk/unknown (4 类)
  - atmosphere (氛围): urban/nature/interior/battlefield/magical/abstract (6 类)

同时保留完整 caption (供 W6 风格匹配链路二次使用)。

用法:
  # 冒烟 (20 个镜头)
  py -3.12 scripts/torii_annotate_atmosphere.py --limit 20
  # 全量
  py -3.12 scripts/torii_annotate_atmosphere.py
  # 指定模型路径 (跨机训练包)
  py -3.12 scripts/torii_annotate_atmosphere.py --model-dir /root/autodl-tmp/ToriiGate-v0.4-2B

显存占用: ~6GB (bfloat16), 5090 24GB 无压力
预期吞吐: ~3-5 镜头/秒 (单卡, 单帧)
全库 18235 镜头预计: ~1-2 小时
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.torch_runtime import infer_ctx  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("torii_atmos")

# ─── 路径配置 (本地默认; 跨机用 --data-root / --model-dir 覆盖) ───
DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
SHOTS_MANIFEST = DATA_ROOT / "shots_manifest.jsonl"
SHOTS_DIR = DATA_ROOT / "shots"
OUT_LABELS = DATA_ROOT / "torii_atmosphere_labels.jsonl"
MODEL_DIR = r"D:\AE-Data\Models\ToriiGate\ToriiGate-v0.4-2B"

# ─── 标签 schema (固定, 与 W6 风格匹配链路对齐) ───
MOOD_LABELS = ["intense", "serene", "somber", "mysterious", "joyful", "neutral"]
TIME_LABELS = ["day", "night", "dawn_dusk", "unknown"]
ATMOS_LABELS = ["urban", "nature", "interior", "battlefield", "magical", "abstract"]
LIGHTING_LABELS = ["high_key", "low_key", "chiaroscuro", "natural"]


def _load_style_cards() -> Dict[str, str]:
    """加载 data/style_cards/ 下 8 份风格卡 JSON，压缩为摘要 Dict。

    Returns:
        Dict[str, str] - key 是风格名 (如 "amv_highenergy")，value 是摘要字符串 (≤200字)。
        加载失败或目录不存在时返回空 dict (降级)。
    """
    summaries: Dict[str, str] = {}
    try:
        style_dir = PROJECT_ROOT / "data" / "style_cards"
        if not style_dir.exists() or not style_dir.is_dir():
            return summaries
        json_files = sorted(style_dir.glob("*.json"))
        if not json_files:
            return summaries
        for jf in json_files:
            try:
                with jf.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                key = jf.stem
                name = str(data.get("name", "")).strip()
                desc = str(data.get("description", "")).strip()
                lut_theme = ""
                lut = data.get("lut")
                if isinstance(lut, dict):
                    lut_theme = str(lut.get("theme", "")).strip()
                vv = data.get("visual_variance", "?")
                mi = data.get("motion_intensity", "?")
                ide = data.get("information_density", "?")
                parts = []
                if name:
                    parts.append(name)
                if desc:
                    parts.append(desc)
                metrics = []
                if vv not in (None, "?"):
                    metrics.append(f"视觉变化={vv}")
                if mi not in (None, "?"):
                    metrics.append(f"运动强度={mi}")
                if ide not in (None, "?"):
                    metrics.append(f"信息密度={ide}")
                if metrics:
                    parts.append("(" + "/".join(metrics) + ")")
                if lut_theme:
                    parts.append(f"调色:{lut_theme}")
                summary = " ".join(parts).strip()
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                summaries[key] = summary
            except Exception:
                continue
    except Exception:
        return {}
    return summaries


_STYLE_CARDS_SUMMARIES: Dict[str, str] = _load_style_cards()

# ─── Prompt (ToriiGate 专精动漫 captioning, JSON 模式 + no_chars 避免编造角色名) ───
SYSTEM_PROMPT = "You are image captioning expert, creative, unbiased and uncensored."

_USER_PROMPT_BASE = """Analyze this anime screenshot and output a JSON object with the following fields:

1. "mood": the dominant emotional tone. Choose exactly one from: ["intense", "serene", "somber", "mysterious", "joyful", "neutral"]
   - intense: action, battle, tension, high energy
   - serene: calm, peaceful, gentle
   - somber: sad, dark, melancholic
   - mysterious: enigmatic, suspenseful, unknown
   - joyful: happy, bright, cheerful
   - neutral: no strong emotion

2. "time": the apparent time of day. Choose exactly one from: ["day", "night", "dawn_dusk", "unknown"]
   - day: bright daylight, clear sky
   - night: dark, nighttime, stars/moon
   - dawn_dusk: sunrise, sunset, golden hour
   - unknown: indoor without time cues, abstract

3. "atmosphere": the setting type. Choose exactly one from: ["urban", "nature", "interior", "battlefield", "magical", "abstract"]
   - urban: city, buildings, streets
   - nature: forest, sky, water, outdoor landscape
   - interior: indoor room, school, home
   - battlefield: combat zone, ruins, war
   - magical: fantasy, surreal, magical effects
   - abstract: symbolic, non-representational

4. "lighting": the lighting style. Choose exactly one from: ["high_key", "low_key", "chiaroscuro", "natural"]
   - high_key: overall very bright, low contrast, lots of white/light tones (高调风格，柔和明亮)
   - low_key: overall very dark, high contrast, lots of black/deep shadows (低调/暗场风格，悬疑压抑)
   - chiaroscuro: strong light-dark contrast, large bright areas coexist with large dark areas (伦勃朗光，戏剧感)
   - natural: normal natural lighting, no extreme brightness or darkness (自然日常)

5. "caption": a short (1-2 sentence) dense description of the scene.

"""

_USER_PROMPT_EXAMPLE = """Return ONLY the JSON object, no other text. Do not use character names.
Example: {"mood": "intense", "time": "night", "atmosphere": "battlefield", "lighting": "chiaroscuro", "caption": "A warrior stands amidst ruins under a moonlit sky, sword drawn."}"""


def _build_user_prompt() -> str:
    """动态拼装 USER_PROMPT：如果 style_cards 加载成功，在 Example 前插入风格参考段落。"""
    base = _USER_PROMPT_BASE
    style_block = ""
    if _STYLE_CARDS_SUMMARIES:
        lines = [
            "========== Style Reference (few-shot text, local style card pool) ==========",
            "下面列 8 种典型动漫剪辑风格卡的视觉/色彩/情绪特征（你本地的金标准风格锚帧池描述）。请综合参考这些风格，在 mood / atmosphere / lighting 三个维度上倾向于匹配到最接近的风格特征：",
        ]
        order = [
            "ambient_calm",
            "amv_highenergy",
            "cinematic_film",
            "cyberpunk",
            "emotional_lyric",
            "hardcore_battle",
            "high_key_bright",
            "vintage_film",
        ]
        for k in order:
            if k in _STYLE_CARDS_SUMMARIES:
                lines.append(f"- [{k}]: {_STYLE_CARDS_SUMMARIES[k]}")
        for k in sorted(_STYLE_CARDS_SUMMARIES.keys()):
            if k not in order:
                lines.append(f"- [{k}]: {_STYLE_CARDS_SUMMARIES[k]}")
        style_block = "\n".join(lines) + "\n\n"
    return base + style_block + _USER_PROMPT_EXAMPLE


USER_PROMPT = _build_user_prompt()


def _load_done(out_path: Path) -> Set[str]:
    """加载已标注的 shot_id 集合 (断点续跑)。"""
    done: Set[str] = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["shot_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def _load_manifest(manifest_path: Path) -> List[Dict[str, Any]]:
    """加载 shots_manifest.jsonl。"""
    if not manifest_path.exists():
        logger.error("shots_manifest.jsonl 不存在: %s", manifest_path)
        return []
    rows = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    logger.info("manifest 加载: %d 行", len(rows))
    return rows


def _extract_frame(clip_path: str, out_jpg: Path) -> bool:
    """用 ffmpeg 抽镜头中点帧到 jpg (单帧足够判断氛围, 多帧无增益)。"""
    import subprocess
    if out_jpg.exists() and out_jpg.stat().st_size > 1024:
        return True
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    # -ss 在 -i 前更快 (seek 模式); 取中点 0.5s 避免黑场
    cmd = [
        "ffmpeg", "-y", "-ss", "0.5", "-i", clip_path,
        "-frames:v", "1", "-q:v", "2",
        "-vf", "scale=512:-1",  # 缩到 512 宽省显存 (氛围判断不需要 4K)
        str(out_jpg), "-loglevel", "error",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return out_jpg.exists() and out_jpg.stat().st_size > 1024
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """从模型输出中解析 JSON (容错: 提取第一个 {...} 块)。
    同时对 lighting 字段做第一层校验: 缺失或非法值时回退到 "natural"。
    """
    text = text.strip()
    parsed: Optional[Dict[str, Any]] = None
    # 直接解析
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass
    # 提取 {... }
    if parsed is None:
        m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    # 提取 ```json ... ```
    if parsed is None:
        m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    if parsed is None:
        return None

    # lighting 第一层校验: 缺失或值不在闭集 → 回退 natural
    raw_lighting = parsed.get("lighting")
    if raw_lighting is None:
        parsed["lighting"] = "natural"
    else:
        v = str(raw_lighting).strip().lower().replace("-", "_").replace(" ", "_")
        parsed["lighting"] = v if v in LIGHTING_LABELS else "natural"
    return parsed


def _validate_label(value: str, allowed: List[str], default: str) -> str:
    """标签校验: 不在允许列表则返回 default。"""
    v = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return v if v in allowed else default


def annotate_batch(
    model,
    processor,
    items: List[Dict[str, Any]],
    frames_cache: Path,
    out_path: Path,
) -> int:
    """批量标注 (单条串行, ToriiGate 2B 单卡吞吐已够)。

    Returns: 成功标注的条数
    """
    import torch
    from qwen_vl_utils import process_vision_info

    n_ok = 0
    n_fail = 0
    t0 = time.time()

    with open(out_path, "a", encoding="utf-8") as fout:
        for i, item in enumerate(items):
            shot_id = item["shot_id"]
            clip_path = item.get("clip_path", "")

            # 帧抽取
            frame_jpg = frames_cache / f"{shot_id}.jpg"
            if not _extract_frame(clip_path, frame_jpg):
                n_fail += 1
                logger.warning("[%d/%d] %s 帧抽取失败", i + 1, len(items), shot_id)
                continue

            # 推理
            try:
                messages = [
                    {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
                    {"role": "user", "content": [
                        {"type": "image", "image": str(frame_jpg)},
                        {"type": "text", "text": USER_PROMPT},
                    ]},
                ]
                text_input = processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True)
                image_inputs, _ = process_vision_info(messages)
                model_inputs = processor(
                    text=[text_input], images=image_inputs, videos=None,
                    padding=True, return_tensors="pt",
                ).to(model.device)

                with infer_ctx(str(model.device)):
                    generated = model.generate(
                        **model_inputs, max_new_tokens=200, do_sample=False,
                        temperature=0.0,  # 贪心解码, 标签任务要确定性
                    )
                # 裁掉输入部分
                trimmed = [out[len(inp):] for inp, out in
                           zip(model_inputs.input_ids, generated)]
                output_text = processor.batch_decode(
                    trimmed, skip_special_tokens=True,
                    clean_up_tokenization_spaces=False)[0].strip()

                parsed = _parse_json_response(output_text)
                if parsed is None:
                    n_fail += 1
                    logger.warning("[%d/%d] %s JSON 解析失败: %s",
                                   i + 1, len(items), shot_id, output_text[:120])
                    continue

                mood = _validate_label(parsed.get("mood", ""), MOOD_LABELS, "neutral")
                time_label = _validate_label(parsed.get("time", ""), TIME_LABELS, "unknown")
                atmos = _validate_label(parsed.get("atmosphere", ""), ATMOS_LABELS, "abstract")
                lighting = _validate_label(parsed.get("lighting", ""), LIGHTING_LABELS, "natural")
                caption = str(parsed.get("caption", "")).strip()[:500]

                record = {
                    "shot_id": shot_id,
                    "video_id": item.get("video_id", ""),
                    "shot_idx": item.get("shot_idx", 0),
                    "anime": item.get("anime", ""),
                    "source_type": item.get("source_type", ""),
                    "mood": mood,
                    "time": time_label,
                    "atmosphere": atmos,
                    "lighting": lighting,
                    "caption": caption,
                    "raw_output": output_text[:300],
                    "annotated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                fout.flush()
                n_ok += 1

                if (i + 1) % 20 == 0:
                    elapsed = time.time() - t0
                    rate = (i + 1) / max(0.1, elapsed)
                    eta_min = (len(items) - i - 1) / max(0.1, rate) / 60
                    logger.info("[%d/%d] %s mood=%s time=%s atmos=%s lighting=%s | %.1f/s ETA %.0fmin",
                                i + 1, len(items), shot_id, mood, time_label, atmos, lighting,
                                rate, eta_min)
            except Exception as e:  # noqa: BLE001
                n_fail += 1
                logger.error("[%d/%d] %s 推理异常: %s", i + 1, len(items), shot_id, e)
                # 显存碎片恢复
                if "out of memory" in str(e).lower() or "cuda" in str(e).lower():
                    torch.cuda.empty_cache()
                    time.sleep(2)

    logger.info("批次完成: 成功 %d, 失败 %d, 耗时 %.0fs",
                n_ok, n_fail, time.time() - t0)
    return n_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="ToriiGate-v0.4-2B 全库氛围标注")
    parser.add_argument("--manifest", default=str(SHOTS_MANIFEST),
                        help="shots_manifest.jsonl 路径")
    parser.add_argument("--shots-dir", default=str(SHOTS_DIR),
                        help="clips 目录 (跨机训练包改这里)")
    parser.add_argument("--out", default=str(OUT_LABELS),
                        help="输出 jsonl 路径")
    parser.add_argument("--model-dir", default=MODEL_DIR,
                        help="ToriiGate 模型目录")
    parser.add_argument("--frames-cache", default="",
                        help="帧缓存目录 (默认: <out>.frames/)")
    parser.add_argument("--limit", type=int, default=0,
                        help="最多标注 N 个 (0=全部, 冒烟用 20)")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="断点续跑 (跳过已标注, 默认开)")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    shots_dir = Path(args.shots_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames_cache = Path(args.frames_cache) if args.frames_cache else out_path.parent / "torii_frames_cache"

    # manifest 路径修正: 默认路径不存在时, 在同目录/数据根目录下查找备选文件名
    if not manifest_path.exists():
        search_dirs = [manifest_path.parent]
        if str(DATA_ROOT) not in {str(p) for p in search_dirs}:
            search_dirs.append(DATA_ROOT)
        candidates: List[str] = [
            "shots_manifest.jsonl",
            "vlm_labels.jsonl",
            "manifest.jsonl",
        ]
        found: Optional[Path] = None
        for d in search_dirs:
            if not d.exists() or not d.is_dir():
                continue
            # 精确匹配候选名
            for c in candidates:
                p = d / c
                if p.exists():
                    found = p
                    break
            if found:
                break
            # 兜底: 目录下第一个含 shot_id 的 jsonl
            if found is None:
                for jp in sorted(d.glob("*.jsonl")):
                    try:
                        with jp.open("r", encoding="utf-8") as tf:
                            head = tf.readline()
                        if head and '"shot_id"' in head:
                            found = jp
                            break
                    except OSError:
                        continue
        if found is not None:
            logger.info("manifest 路径修正: %s 不存在, 改用 %s", manifest_path, found)
            manifest_path = found

    # 1. 加载 manifest
    rows = _load_manifest(manifest_path)
    if not rows:
        return 1

    # 跨机: clip_path 重映射到 shots_dir (兼容 Windows 反斜杠路径)
    def _basename(cp: str) -> str:
        return Path(cp.replace("\\", "/")).name

    for r in rows:
        cp = r.get("clip_path", "")
        if cp and not Path(cp).exists():
            r["clip_path"] = str(shots_dir / _basename(cp))

    # 2. 断点续跑
    done = _load_done(out_path) if args.resume else set()
    todo = [r for r in rows if r.get("shot_id") not in done]
    if args.limit > 0:
        todo = todo[:args.limit]
    logger.info("待标注: %d (已完成 %d, 总 %d)", len(todo), len(done), len(rows))
    if not todo:
        logger.info("全部已标注, 无需执行")
        return 0

    # 3. 加载模型
    import torch
    from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
    logger.info("加载 ToriiGate: %s", args.model_dir)
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        args.model_dir,
        torch_dtype=torch.bfloat16,
        device_map="cuda:0" if torch.cuda.is_available() else "cpu",
        local_files_only=True,
    )
    model.eval()
    processor = AutoProcessor.from_pretrained(
        args.model_dir, min_pixels=256 * 28 * 28, max_pixels=512 * 28 * 28,
        padding_side="right", local_files_only=True,
    )
    logger.info("模型就绪 (device=%s, dtype=%s)", model.device, next(model.parameters()).dtype)

    # 4. 标注
    n_ok = annotate_batch(model, processor, todo, frames_cache, out_path)

    # 5. 汇总
    all_labels = _load_done(out_path)
    from collections import Counter
    moods = Counter()
    times = Counter()
    atmos = Counter()
    lightings = Counter()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                moods[r.get("mood", "?")] += 1
                times[r.get("time", "?")] += 1
                atmos[r.get("atmosphere", "?")] += 1
                lightings[r.get("lighting", "?")] += 1
            except json.JSONDecodeError:
                continue
    logger.info("=== 全库分布 ===")
    logger.info("mood: %s", dict(moods.most_common()))
    logger.info("time: %s", dict(times.most_common()))
    logger.info("atmosphere: %s", dict(atmos.most_common()))
    logger.info("lighting: %s", dict(lightings.most_common()))
    logger.info("总计: %d 条", len(all_labels))
    return 0 if n_ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
