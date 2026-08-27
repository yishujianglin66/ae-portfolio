# -*- coding: utf-8 -*-
"""qwen_mm_adapter.py — Qwen-MM 多模态视觉理解适配器

通过检查 llm_gateway 中 qwen Provider 是否已注册（即 API key 是否可用）
来判断 Qwen-MM 集成是否可用。
"""
import os
from pathlib import Path
from typing import Any, Dict, List

# 确保 .env 被加载（适配器可能被独立调用）
try:
    from dotenv import load_dotenv
    _env = Path(__file__).resolve().parent.parent / ".env"
    if _env.exists():
        load_dotenv(_env, override=False)
except ImportError:
    pass


class QwenMMAdapter:
    """Qwen-MM 适配器 — 通过 DashScope / Qwen Provider 接入"""

    def check_available(self) -> bool:
        """检查 qwen Provider 是否可用（API key 存在即可）"""
        key = os.environ.get("QWEN_API_KEY", "") or os.environ.get("DASHSCOPE_API_KEY", "")
        return bool(key)

    def list_operations(self) -> List[str]:
        """列出可用操作"""
        return [
            "vision_understand",       # 多模态视觉理解
            "image_caption",           # 图片描述
            "style_analysis",          # 风格分析
            "quality_assessment",      # 质量评估
            "text_from_image",         # 图片文字提取
            "scene_understanding",     # 场景理解
            "visual_comparison",       # 视觉对比
        ]

    def execute(self, operation: str, **kwargs) -> Dict[str, Any]:
        """执行操作（委托给 llm_gateway）"""
        from core.llm_gateway import get_gateway
        gw = get_gateway()
        return gw.call_qwen_vision(operation, **kwargs)
