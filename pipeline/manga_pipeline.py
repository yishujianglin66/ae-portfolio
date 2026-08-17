"""
pipeline/manga_pipeline.py — 漫剪专用管线调度
==============================================

基于 pipeline/templates/manga_edit.json 模板，
调度 AE Bridge 执行漫剪特效（闪白/震动/色差/速度线）+ PR 卡点剪辑 + DaVinci 调色。

用法::

    py -3.11 -m pipeline.manga_pipeline --images img1.png img2.png img3.png --audio bgm.mp3

设计原则：
- 复用 engine_task_dispatcher 统一调度
- JSX 模板参数化注入（{{PLACEHOLDER}} 替换）
- 引擎不在线时降级到 FFmpeg 等效
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "manga_edit.json"
JSX_DIR = PROJECT_ROOT / "ae" / "scripts" / "manga"


def load_template() -> Dict[str, Any]:
    """加载漫剪管线模板。"""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"模板不存在: {TEMPLATE_PATH}")
    return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def render_jsx_template(template_path: Path, params: Dict[str, Any]) -> str:
    """将 JSX 模板中的 {{KEY}} 占位符替换为实际参数值。

    Args:
        template_path: JSX 模板文件路径
        params: 参数字典（key 不含花括号）

    Returns:
        替换后的 JSX 代码字符串
    """
    code = template_path.read_text(encoding="utf-8")
    for key, value in params.items():
        placeholder = "{{" + key + "}}"
        if isinstance(value, str):
            code = code.replace(placeholder, value)
        elif isinstance(value, bool):
            code = code.replace(placeholder, "true" if value else "false")
        else:
            code = code.replace(placeholder, str(value))
    return code


def build_flash_shake_jsx(
    comp_name: str,
    layer_name: str,
    drop_time: float,
    fps: float = 24.0,
    flash_frames: int = 2,
    shake_amp: float = 15.0,
    shake_freq: float = 30.0,
    shake_decay: int = 8,
) -> str:
    """构建闪白+震动 JSX 代码。"""
    template = JSX_DIR / "flash_shake.jsx"
    if not template.exists():
        raise FileNotFoundError(f"JSX 模板不存在: {template}")
    return render_jsx_template(template, {
        "COMP_NAME": comp_name,
        "LAYER_NAME": layer_name,
        "DROP_TIME": f"{drop_time:.4f}",
        "FPS": f"{fps:.1f}",
        "FLASH_FRAMES": str(flash_frames),
        "SHAKE_AMP": f"{shake_amp:.1f}",
        "SHAKE_FREQ": f"{shake_freq:.1f}",
        "SHAKE_DECAY": str(shake_decay),
    })


def build_chromatic_jsx(
    comp_name: str,
    layer_name: str,
    trigger_time: float,
    fps: float = 24.0,
    offset_px: float = 4.0,
    direction: str = "horizontal",
    decay_frames: int = 6,
) -> str:
    """构建色差 JSX 代码。"""
    template = JSX_DIR / "chromatic_aberration.jsx"
    if not template.exists():
        raise FileNotFoundError(f"JSX 模板不存在: {template}")
    return render_jsx_template(template, {
        "COMP_NAME": comp_name,
        "LAYER_NAME": layer_name,
        "TRIGGER_TIME": f"{trigger_time:.4f}",
        "FPS": f"{fps:.1f}",
        "OFFSET_PX": f"{offset_px:.1f}",
        "DIRECTION": direction,
        "DECAY_FRAMES": str(decay_frames),
    })


def build_speed_lines_jsx(
    comp_name: str,
    trigger_time: float,
    fps: float = 24.0,
    duration_frames: int = 12,
    line_count: int = 80,
    center_x: float = 0.5,
    center_y: float = 0.5,
    line_speed: float = 2.0,
) -> str:
    """构建速度线 JSX 代码。"""
    template = JSX_DIR / "speed_lines.jsx"
    if not template.exists():
        raise FileNotFoundError(f"JSX 模板不存在: {template}")
    return render_jsx_template(template, {
        "COMP_NAME": comp_name,
        "TRIGGER_TIME": f"{trigger_time:.4f}",
        "FPS": f"{fps:.1f}",
        "DURATION_FRAMES": str(duration_frames),
        "LINE_COUNT": str(line_count),
        "CENTER_X": f"{center_x:.2f}",
        "CENTER_Y": f"{center_y:.2f}",
        "LINE_SPEED": f"{line_speed:.1f}",
    })


def run_manga_pipeline(
    image_paths: List[Path],
    audio_path: Path,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """执行漫剪管线。

    Args:
        image_paths: 动漫/漫画图片列表
        audio_path: BGM 音频文件
        output_dir: 输出目录（默认 output/manga_<timestamp>）

    Returns:
        管线执行结果 manifest
    """
    import sys
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    template = load_template()
    run_id = f"manga_{int(time.time())}"
    if output_dir is None:
        output_dir = PROJECT_ROOT / "output" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "run_id": run_id,
        "template": "manga_edit",
        "inputs": {
            "images": [str(p) for p in image_paths],
            "audio": str(audio_path),
        },
        "stages": {},
    }

    logger.info(f"[Manga] 管线启动: {run_id}")
    logger.info(f"[Manga] 图片: {len(image_paths)}, 音频: {audio_path.name}")

    # 尝试获取 AE dispatcher
    ae_available = False
    try:
        from pipeline.engine_task_dispatcher import get_dispatcher
        ae_disp = get_dispatcher("after_effects")
        ae_available = ae_disp.is_available()
    except ImportError:
        pass

    manifest["ae_available"] = ae_available

    # S2: 节拍分析
    logger.info("[Manga] S2: 节拍分析...")
    try:
        from pipeline.flagship_runner import stage_s2_beat
        s2_dir = output_dir / "S2_beat"
        s2_dir.mkdir(parents=True, exist_ok=True)
        s2 = stage_s2_beat(output_dir, audio_path)
        manifest["stages"]["S2"] = s2
        beats_json = Path(s2["beats_json"])
        beats_data = json.loads(beats_json.read_text(encoding="utf-8"))
        drops = beats_data.get("drops", [])
        peaks = beats_data.get("energy_peaks", [])
    except Exception as e:
        logger.warning(f"[Manga] S2 失败: {e}")
        drops, peaks = [], []
        manifest["stages"]["S2"] = {"error": str(e)}

    # S3: AE 特效
    logger.info("[Manga] S3: AE 特效合成...")
    s3_results = []

    if ae_available:
        try:
            from pipeline.engine_task_dispatcher import get_dispatcher
            ae_disp = get_dispatcher("after_effects")

            # 为每个 drop 生成闪白+震动
            for i, drop_time in enumerate(drops[:10]):  # 最多 10 个
                jsx_code = build_flash_shake_jsx(
                    comp_name=f"MangaComp_{i}",
                    layer_name="Image",
                    drop_time=drop_time,
                )
                result = ae_disp.dispatch_script(jsx_code, timeout=30)
                s3_results.append({
                    "type": "flash_shake",
                    "drop_time": drop_time,
                    "success": result.success,
                })

            # 为每个 energy peak 生成色差
            for i, peak_time in enumerate(peaks[:8]):
                jsx_code = build_chromatic_jsx(
                    comp_name=f"MangaComp_{i}",
                    layer_name="Image",
                    trigger_time=peak_time,
                )
                result = ae_disp.dispatch_script(jsx_code, timeout=30)
                s3_results.append({
                    "type": "chromatic",
                    "peak_time": peak_time,
                    "success": result.success,
                })

            manifest["stages"]["S3"] = {
                "mode": "native_bridge",
                "effects_count": len(s3_results),
                "results": s3_results,
            }
        except Exception as e:
            logger.warning(f"[Manga] S3 AE native 失败: {e}")
            manifest["stages"]["S3"] = {"mode": "failed", "error": str(e)}
    else:
        logger.info("[Manga] AE 不在线，S3 跳过 native 特效")
        manifest["stages"]["S3"] = {"mode": "skipped", "reason": "ae_offline"}

    # 保存 manifest
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"[Manga] 管线完成: {manifest_path}")

    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="漫剪管线")
    parser.add_argument("--images", nargs="+", required=True, help="图片文件列表")
    parser.add_argument("--audio", required=True, help="BGM 音频文件")
    parser.add_argument("--output", default=None, help="输出目录")
    args = parser.parse_args()

    result = run_manga_pipeline(
        image_paths=[Path(p) for p in args.images],
        audio_path=Path(args.audio),
        output_dir=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
