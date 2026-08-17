"""
Style Template Library — 风格模板知识库（统一入口）
===================================================
主版本位于 `video/style_template_library.py`（含 intensity_param / intensity_factor
驱动字段与 40+ 风格配方）。

历史沿革：本文件曾为 12 风格 Premiere Lumetri 配方（含 preferred_transition /
preferred_camera / tempo 等字段），已被 video 版本取代。为消除双副本漂移，
本文件改为转发 video 主版本 —— `from ae.style_template_library import STYLE_TEMPLATES`
与 `from video.style_template_library import STYLE_TEMPLATES` 得到同一份数据。
"""

from video.style_template_library import STYLE_TEMPLATES

__all__ = ["STYLE_TEMPLATES"]
