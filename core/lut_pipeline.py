"""lut_pipeline.py — LUT 转码管线（ffmpeg lut3d + 强度混合）

AE 内 Lumetri 的 LUT 参数是资产型, 脚本 setValue 会弹 UI 卡死无人值守
（2026-08-16 真机实测 ADBE Lumetri-0005/0125/0127 均不可脚本化）。
因此 LUT 走 ffmpeg 转码阶段: aerender 出 avi → ffmpeg lut3d + blend 强度
→ 最终 mp4。渲染管线的既有转码步骤被本模块替代/扩展。

效果已实测 (好莱坞 LUT vs 原帧): 饱和度 9→215, 色相偏移 100+, 平均像素差 18.9
—— 色彩方差真实注入。RGB 像素级线性验证: B 通道 6.8→22.6(0.5)→43.4(1.0)。
⚠ 验证必须用 RGB 像素差, HSV 的 S 在深色帧上非线性 (2026-08-17 教训)。

⚠ 2026-08-27 事故记录: 本文件曾被残废版覆盖 (load_sampling 返回 {} /
transcode_with_lut 退化为 shutil.copy2), git 提交 4554aa3 时已丢失原版,
导致 multisegment seg4 LUT 静默失效 ("LUT: 无可用 cube")。
本版从开发会话记录完整重建。接手者改动前先读本注释。

用法:
  from core.lut_pipeline import transcode, transcode_with_lut
  transcode(avi, mp4)                          # 无 LUT (等价旧管线)
  transcode_with_lut(avi, mp4, cube, 0.7)      # LUT 70% 强度
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

PROJECT = Path(__file__).resolve().parent.parent
LUT_INDEX = PROJECT / "data" / "luts" / "index.json"
LUT_SAMPLING = PROJECT / "data" / "luts" / "sampling.json"


def _ff_escape(path: str) -> str:
    """ffmpeg filter 内的文件路径转义: 反斜杠→正斜杠, 冒号转义。"""
    p = path.replace("\\", "/")
    return p.replace(":", "\\:")


def transcode(src: str, dst: str, crf: int = 17) -> bool:
    """纯转码 (无 LUT, 与旧管线等价)。"""
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-c:v", "libx264", "-preset", "medium",
         "-crf", str(crf), "-pix_fmt", "yuv420p", dst],
        capture_output=True, timeout=300)
    return Path(dst).exists() and r.returncode == 0


def transcode_with_lut(src: str, dst: str, cube: str, strength: float = 1.0,
                       crf: int = 17) -> bool:
    """转码 + 3D LUT + 强度混合。

    strength: 0.0-1.0, 0=原帧 1=全 LUT。
    实现: split 双路, 一路 lut3d, blend all_expr 线性插值混合。
    """
    s = max(0.0, min(1.0, float(strength)))
    if s <= 0.001 or not cube:
        return transcode(src, dst, crf)
    vf = (
        f"[0:v]split=2[a][b];"
        f"[a]lut3d='{_ff_escape(cube)}'[l];"
        f"[b][l]blend=all_expr='A*(1-{s:.3f})+B*{s:.3f}'"
    )
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-filter_complex", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
         "-pix_fmt", "yuv420p", dst],
        capture_output=True, timeout=300)
    if not (Path(dst).exists() and r.returncode == 0):
        # 转码失败通常 = src avi 损坏/被锁 — 把 stderr 尾部抛给调用方日志
        import sys
        sys.stderr.write(
            f"[lut_pipeline] transcode_with_lut 失败 rc={r.returncode} "
            f"src={src}\n{r.stderr.decode(errors='ignore')[-300:]}\n")
        return False
    return True


def load_sampling() -> dict:
    """主题 → cube 路径列表 (采样池, data/luts/sampling.json)。

    兼容两种布局: {"theme": [file...]} 与 {"themes": {theme: [file...]}}。
    """
    try:
        d = json.loads(LUT_SAMPLING.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(d, dict) and isinstance(d.get("themes"), dict):
        return d["themes"]
    return d if isinstance(d, dict) else {}


def lut_md5(cube_path: str) -> str | None:
    """从索引查 cube 的内容 md5 (数据卫生: 样本行记录哈希防路径移动错位)。"""
    try:
        idx = json.loads(LUT_INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for e in idx:
        if e.get("file") == cube_path:
            return e.get("md5")
    return None


__all__ = ["transcode", "transcode_with_lut", "load_sampling", "lut_md5"]
