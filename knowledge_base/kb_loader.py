"""
knowledge_base/kb_loader.py - 知识库门面 API (Layer 5)

单例类，整合 Layer 1-4 提供统一的知识加载接口。

用法：
    from knowledge_base.kb_loader import KnowledgeBaseLoader

    loader = KnowledgeBaseLoader.get_instance()
    effect_map = loader.get_effect_map()
    trans_map = loader.get_transition_map()
    presets = loader.get_color_presets()
    recipes = loader.get_style_recipes()
    plugin_effects = loader.load_plugin_effects()
    effect_template = loader.generate_effect_template("Gaussian Blur")
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from knowledge_base.types import (
    BlockType,
    MdBlock,
    EffectMapping,
    TransitionRecipe,
    ColorPreset,
    StyleRecipe,
)
from knowledge_base.md_parser import MdParser
from knowledge_base.table_extractor import TableExtractor
from knowledge_base.section_parser import SectionParser
from knowledge_base.kb_cache import KbCache
from knowledge_base.adapters.effect_adapter import EffectAdapter
from knowledge_base.adapters.transition_adapter import TransitionAdapter


# 默认知识库路径 —— 支持多目录聚合（10/11/12/14/15/13 六大知识库）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_KB_DIRS = [
    str(_PROJECT_ROOT / "10-风格化剪辑知识库"),
    str(_PROJECT_ROOT / "11-大师知识库"),
    str(_PROJECT_ROOT / "12-漫剪拉镜大师"),
    str(_PROJECT_ROOT / "14-Silhouette知识库"),
    str(_PROJECT_ROOT / "15-3D模型与骨骼动画知识库"),
    str(_PROJECT_ROOT / "13-素材获取与搜索"),
]
_DEFAULT_CACHE_DIR = str(_PROJECT_ROOT / "data" / "kb_cache")
_DEFAULT_EFFECT_CATALOG = str(_PROJECT_ROOT / "knowledge_base" / "effect_catalog.json")


def _iter_kb_dirs(kb_dirs: Optional[List[str]] = None) -> List[str]:
    """过滤实际存在的知识库目录列表。"""
    dirs = kb_dirs if kb_dirs is not None else _DEFAULT_KB_DIRS
    return [d for d in dirs if os.path.isdir(d)]


@dataclass
class EffectFullInfo:
    """完整效果信息数据类。"""
    name: str
    match_name: str = ""
    category: str = "other"
    plugin_package: str = ""
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    usage_scenarios: List[str] = field(default_factory=list)
    default_presets: List[Dict[str, Any]] = field(default_factory=list)
    source: str = ""
    confidence: float = 0.8


# 效果参数模板生成规则
_PARAM_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "blur": {
        "Blurriness": {"type": "number", "min": 0, "max": 1000, "default": 10, "description": "模糊强度"},
        "Blur Dimensions": {"type": "enum", "values": ["Horizontal & Vertical", "Horizontal Only", "Vertical Only"], "default": "Horizontal & Vertical", "description": "模糊维度"},
        "Repeat Edge Pixels": {"type": "boolean", "default": False, "description": "重复边缘像素"},
    },
    "color": {
        "Brightness": {"type": "number", "min": -100, "max": 100, "default": 0, "description": "亮度"},
        "Contrast": {"type": "number", "min": -100, "max": 100, "default": 0, "description": "对比度"},
        "Saturation": {"type": "number", "min": -100, "max": 100, "default": 0, "description": "饱和度"},
        "Hue": {"type": "number", "min": -180, "max": 180, "default": 0, "description": "色相"},
    },
    "distort": {
        "Amount": {"type": "number", "min": 0, "max": 10000, "default": 100, "description": "强度"},
        "Size": {"type": "number", "min": 0.1, "max": 1000, "default": 50, "description": "大小"},
        "Complexity": {"type": "number", "min": 1, "max": 10, "default": 3, "description": "复杂度"},
        "Evolution": {"type": "number", "min": 0, "max": 360, "default": 0, "description": "演化"},
    },
    "light": {
        "Brightness": {"type": "number", "min": 0, "max": 200, "default": 100, "description": "亮度"},
        "Glow Radius": {"type": "number", "min": 0, "max": 300, "default": 15, "description": "发光半径"},
        "Glow Intensity": {"type": "number", "min": 0, "max": 5, "default": 1.0, "description": "发光强度"},
        "Color": {"type": "color", "default": [1.0, 1.0, 1.0, 1.0], "description": "颜色"},
    },
    "particle": {
        "Particles/Sec": {"type": "number", "min": 0, "max": 10000, "default": 100, "description": "每秒粒子数"},
        "Longevity": {"type": "number", "min": 0, "max": 60, "default": 5, "description": "生命周期(秒)"},
        "Size": {"type": "number", "min": 0, "max": 100, "default": 3, "description": "粒子大小"},
        "Emitter Type": {"type": "enum", "values": ["Point", "Line", "Grid", "Box", "Sphere"], "default": "Point", "description": "发射器类型"},
        "Gravity": {"type": "number", "min": -1000, "max": 1000, "default": 50, "description": "重力"},
    },
    "generate": {
        "Color": {"type": "color", "default": [1.0, 1.0, 1.0, 1.0], "description": "颜色"},
        "Opacity": {"type": "number", "min": 0, "max": 100, "default": 100, "description": "不透明度"},
        "Scale": {"type": "number", "min": 0, "max": 1000, "default": 100, "description": "缩放"},
        "Position": {"type": "point", "default": [50, 50], "description": "位置"},
    },
    "keying": {
        "Key Color": {"type": "color", "default": [0.0, 1.0, 0.0, 1.0], "description": "键控色"},
        "Tolerance": {"type": "number", "min": 0, "max": 100, "default": 30, "description": "容差"},
        "Edge Softness": {"type": "number", "min": 0, "max": 100, "default": 5, "description": "边缘柔化"},
        "Spill Suppression": {"type": "number", "min": 0, "max": 100, "default": 50, "description": "溢色抑制"},
    },
    "stylize": {
        "Amount": {"type": "number", "min": 0, "max": 100, "default": 50, "description": "效果强度"},
        "Edge Thickness": {"type": "number", "min": 0, "max": 50, "default": 3, "description": "边缘厚度"},
        "Blend With Original": {"type": "number", "min": 0, "max": 100, "default": 50, "description": "与原图混合"},
    },
    "transition": {
        "Transition Completion": {"type": "number", "min": 0, "max": 100, "default": 0, "description": "转场完成度"},
        "Wipe Angle": {"type": "number", "min": -360, "max": 360, "default": 0, "description": "擦除角度"},
        "Feather": {"type": "number", "min": 0, "max": 500, "default": 50, "description": "羽化"},
        "Border Width": {"type": "number", "min": 0, "max": 100, "default": 0, "description": "边框宽度"},
    },
    "matte": {
        "Choke": {"type": "number", "min": -100, "max": 100, "default": 0, "description": "抑制"},
        "Feather": {"type": "number", "min": 0, "max": 200, "default": 5, "description": "羽化"},
        "Contrast": {"type": "number", "min": 0, "max": 100, "default": 0, "description": "对比度"},
    },
    "noise": {
        "Amount": {"type": "number", "min": 0, "max": 100, "default": 20, "description": "数量"},
        "Size": {"type": "number", "min": 0.01, "max": 10, "default": 0.5, "description": "大小"},
        "Noise Type": {"type": "enum", "values": ["Film", "Video", "Uniform", "Gaussian"], "default": "Film", "description": "噪点类型"},
    },
    "text": {
        "Size": {"type": "number", "min": 1, "max": 1000, "default": 100, "description": "字号"},
        "Tracking": {"type": "number", "min": -100, "max": 500, "default": 0, "description": "字距"},
        "Leading": {"type": "number", "min": 0, "max": 500, "default": 120, "description": "行距"},
        "Font": {"type": "string", "default": "Arial", "description": "字体"},
        "Color": {"type": "color", "default": [1.0, 1.0, 1.0, 1.0], "description": "颜色"},
    },
    "3d": {
        "Rotation X": {"type": "number", "min": -360, "max": 360, "default": 0, "description": "X轴旋转"},
        "Rotation Y": {"type": "number", "min": -360, "max": 360, "default": 0, "description": "Y轴旋转"},
        "Rotation Z": {"type": "number", "min": -360, "max": 360, "default": 0, "description": "Z轴旋转"},
        "Position Z": {"type": "number", "min": -10000, "max": 10000, "default": 0, "description": "Z轴位置"},
        "Scale": {"type": "number", "min": 0, "max": 1000, "default": 100, "description": "缩放"},
    },
    "audio": {
        "Level": {"type": "number", "min": -60, "max": 12, "default": 0, "description": "电平(dB)"},
        "Frequency": {"type": "number", "min": 20, "max": 20000, "default": 1000, "description": "频率(Hz)"},
        "Q Factor": {"type": "number", "min": 0.1, "max": 20, "default": 1, "description": "Q值"},
    },
    "utility": {
        "Opacity": {"type": "number", "min": 0, "max": 100, "default": 100, "description": "不透明度"},
        "Blend Mode": {"type": "enum", "values": ["Normal", "Add", "Screen", "Multiply", "Overlay", "Soft Light"], "default": "Normal", "description": "混合模式"},
        "Time Stretch": {"type": "number", "min": 0.01, "max": 100, "default": 100, "description": "时间拉伸(%)"},
    },
    "tracking": {
        "Track Type": {"type": "enum", "values": ["Point", "Parallel", "Perspective", "Corner Pin"], "default": "Point", "description": "追踪类型"},
        "Motion Blur": {"type": "boolean", "default": True, "description": "运动模糊"},
        "Subpixel Positioning": {"type": "boolean", "default": True, "description": "子像素定位"},
    },
    "other": {
        "Amount": {"type": "number", "min": 0, "max": 100, "default": 50, "description": "效果强度"},
        "Blend With Original": {"type": "number", "min": 0, "max": 100, "default": 0, "description": "与原图混合"},
    },
}

# 使用场景推荐
_USAGE_SCENARIOS: Dict[str, List[str]] = {
    "blur": ["背景虚化", "景深效果", "运动模糊", "柔化画面", "过渡转场"],
    "color": ["调色", "色彩校正", "风格化调色", "肤色美化", "胶片模拟"],
    "distort": ["变形效果", "波浪扭曲", "鱼眼效果", "透视校正", "故障效果"],
    "light": ["光效增强", "发光效果", "镜头光晕", "体积光", "电影感光效"],
    "particle": ["粒子特效", "爆炸效果", "烟雾模拟", "雨雪效果", "魔法特效"],
    "generate": ["背景生成", "纹理生成", "渐变填充", "图案创建", "视觉元素"],
    "keying": ["绿幕抠像", "蓝幕抠像", "透明背景", "合成工作", "特效叠加"],
    "stylize": ["风格化", "卡通效果", "素描效果", "油画风格", "艺术加工"],
    "transition": ["转场效果", "场景切换", "视频过渡", "片头片尾", "剪辑节奏"],
    "matte": ["遮罩处理", "边缘细化", "Alpha通道", "合成辅助", "边缘羽化"],
    "noise": ["胶片颗粒", "噪点效果", "纹理添加", "复古效果", "真实感增强"],
    "text": ["文字动画", "标题设计", "字幕效果", "动态排版", "LOGO动画"],
    "3d": ["三维空间", "3D合成", "摄像机运动", "空间感", "深度效果"],
    "audio": ["音频处理", "音效设计", "音乐可视化", "节奏同步", "声音设计"],
    "utility": ["实用工具", "画面调整", "格式转换", "质量提升", "工作流优化"],
    "tracking": ["运动追踪", "画面稳定", "特效匹配", "摄像机反求", "3D跟踪"],
    "other": ["其他效果", "自定义效果", "特殊效果", "实验性效果"],
}


class KnowledgeBaseLoader:
    """知识库加载器 - 门面 API。

    单例模式，确保全库只解析一次。
    """

    _instance: Optional["KnowledgeBaseLoader"] = None

    def __init__(
        self,
        kb_dir: str = "",
        kb_dirs: Optional[List[str]] = None,
        cache_dir: str = "",
    ) -> None:
        """初始化加载器（支持多目录聚合）。

        Args:
            kb_dir: 单个知识库目录路径（向后兼容，将作为单元素插入 kb_dirs 列表）
            kb_dirs: 多个知识库目录路径列表（推荐；不填时使用 _DEFAULT_KB_DIRS 全量）
            cache_dir: 缓存目录路径（默认 data/kb_cache/）
        """
        # 多目录：向后兼容 + 默认全量聚合
        if kb_dirs:
            self._kb_dirs: List[str] = list(kb_dirs)
        elif kb_dir:
            self._kb_dirs = [kb_dir]
        else:
            self._kb_dirs = _iter_kb_dirs()

        self._kb_dir = self._kb_dirs[0] if self._kb_dirs else ""
        self._cache_dir = cache_dir or _DEFAULT_CACHE_DIR

        self._parser = MdParser()
        self._table_extractor = TableExtractor()
        self._section_parser = SectionParser()
        self._effect_adapter = EffectAdapter()
        self._transition_adapter = TransitionAdapter()
        self._cache = KbCache(cache_dir=self._cache_dir)

        # 缓存解析结果
        # key = "<目录名>/<文件名>"，避免跨目录同名文件互相覆盖
        self._file_blocks: Dict[str, List[MdBlock]] = {}
        self._effect_map: Optional[Dict[str, str]] = None
        self._transition_map: Optional[Dict[str, Dict[str, Any]]] = None
        self._color_presets: Optional[List[ColorPreset]] = None
        self._style_recipes: Optional[List[StyleRecipe]] = None


    @classmethod
    def get_instance(
        cls,
        kb_dir: str = "",
        kb_dirs: Optional[List[str]] = None,
        cache_dir: str = "",
    ) -> "KnowledgeBaseLoader":
        """获取单例实例。"""
        if cls._instance is None:
            cls._instance = cls(kb_dir=kb_dir, kb_dirs=kb_dirs, cache_dir=cache_dir)
        return cls._instance

    def list_files(self) -> List[str]:
        """列出所有知识库目录中的 md 文件（返回 "<目录名>/<文件名>" 复合键）。"""
        files: List[str] = []
        for kb_dir in self._kb_dirs:
            if not os.path.isdir(kb_dir):
                continue
            dir_tag = os.path.basename(kb_dir.rstrip(os.sep)) or "kb"
            for name in sorted(os.listdir(kb_dir)):
                if name.endswith(".md"):
                    files.append(f"{dir_tag}/{name}")
        return files

    def _resolve_file(self, key: str) -> str:
        """将 list_files 产生的复合键解析为绝对路径。

        策略：
        1. 若 key 为 "dir/file.md"，则从 self._kb_dirs 里找到 basename==dir 的目录并拼接。
        2. 否则按向后兼容处理：在 self._kb_dirs[0] 下直接查找。
        """
        if "/" in key or "\\" in key:
            parts = key.replace("\\", "/").split("/", 1)
            if len(parts) == 2:
                dir_tag, fname = parts
                for kb_dir in self._kb_dirs:
                    if os.path.basename(kb_dir.rstrip(os.sep)) == dir_tag:
                        candidate = os.path.join(kb_dir, fname)
                        if os.path.isfile(candidate):
                            return candidate
        # 向后兼容：单目录直查
        for kb_dir in self._kb_dirs:
            candidate = os.path.join(kb_dir, key)
            if os.path.isfile(candidate):
                return candidate
        return ""

    def parse_file(self, filename: str) -> List[MdBlock]:
        """解析单个知识库文件（filename 可为复合键 dir/file.md 或纯文件名）。"""
        if filename in self._file_blocks:
            return self._file_blocks[filename]

        file_path = self._resolve_file(filename)
        if not file_path or not os.path.isfile(file_path):
            return []

        # 检查缓存
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return []

        cached = self._cache.get(file_path, mtime=mtime)
        if cached is not None:
            blocks = self._blocks_from_cache(cached)
            self._file_blocks[filename] = blocks
            return blocks

        # 解析文件
        blocks = self._parser.parse_file(file_path)
        self._file_blocks[filename] = blocks

        # 写入缓存
        cache_data = self._blocks_to_cache(blocks)
        self._cache.set(file_path, cache_data, mtime=mtime)

        return blocks

    def _parse_all_files(self) -> None:
        """解析所有知识库文件。"""
        for filename in self.list_files():
            self.parse_file(filename)

    def get_effect_map(
        self,
        fallback: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """获取效果映射字典。

        输出格式与 effect_registry.KEYWORD_TO_EFFECT_MAP 兼容。

        Args:
            fallback: 硬编码 fallback 映射（知识库映射优先）

        Returns:
            keyword -> matchName 字典
        """
        if self._effect_map is not None and fallback is None:
            return dict(self._effect_map)

        self._parse_all_files()

        all_mappings: List[EffectMapping] = []
        for filename, blocks in self._file_blocks.items():
            mappings = self._effect_adapter.extract_from_blocks(
                blocks, source_file=filename
            )
            all_mappings.extend(mappings)
            # 也从文本中提取
            text_mappings = self._effect_adapter.extract_from_text_blocks(
                blocks, source_file=filename
            )
            all_mappings.extend(text_mappings)

        if fallback:
            self._effect_map = self._effect_adapter.merge_with_fallback(
                all_mappings, fallback
            )
        else:
            self._effect_map = self._effect_adapter.to_dict(all_mappings)

        self._cache.save()
        return dict(self._effect_map)

    def get_transition_map(
        self,
        fallback: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """获取转场配方字典。

        输出格式与 transition_rebuilder.TRANSITION_IMPL_MAP 兼容。

        Args:
            fallback: 硬编码 fallback 配方

        Returns:
            transition_type -> recipe dict
        """
        if self._transition_map is not None and fallback is None:
            return dict(self._transition_map)

        self._parse_all_files()

        all_recipes: List[TransitionRecipe] = []
        for filename, blocks in self._file_blocks.items():
            recipes = self._transition_adapter.extract_from_blocks(
                blocks, source_file=filename
            )
            all_recipes.extend(recipes)
            # 注意：不从文本块提取转场配方，避免过度匹配非转场数据

        if fallback:
            self._transition_map = self._transition_adapter.merge_with_fallback(
                all_recipes, fallback
            )
        else:
            self._transition_map = self._transition_adapter.to_dict(all_recipes)

        self._cache.save()
        return dict(self._transition_map)

    def get_color_presets(self) -> List[ColorPreset]:
        """获取调色预设列表。

        Returns:
            ColorPreset 列表
        """
        if self._color_presets is not None:
            return list(self._color_presets)

        self._parse_all_files()
        # 调色预设提取（从表格中查找包含"预设名/参数/AE复刻"列的表格）
        self._color_presets = []
        # 暂不实现详细提取，返回空列表
        return list(self._color_presets)

    def get_style_recipes(self) -> List[StyleRecipe]:
        """获取风格配方列表。

        Returns:
            StyleRecipe 列表
        """
        if self._style_recipes is not None:
            return list(self._style_recipes)

        self._parse_all_files()
        self._style_recipes = []
        return list(self._style_recipes)

    # =========================================================================
    # 缓存序列化
    # =========================================================================

    @staticmethod
    def _blocks_to_cache(blocks: List[MdBlock]) -> Dict[str, Any]:
        """将 MdBlock 列表转为可 JSON 序列化的格式。"""
        return {
            "blocks": [
                {
                    "block_type": b.block_type.value,
                    "content": b.content,
                    "level": b.level,
                    "metadata": b.metadata,
                }
                for b in blocks
            ]
        }

    @staticmethod
    def _blocks_from_cache(data: Dict[str, Any]) -> List[MdBlock]:
        """从缓存数据恢复 MdBlock 列表。"""
        blocks: List[MdBlock] = []
        for item in data.get("blocks", []):
            try:
                bt = BlockType(item["block_type"])
            except ValueError:
                continue
            blocks.append(MdBlock(
                block_type=bt,
                content=item.get("content", ""),
                level=item.get("level", 0),
                metadata=item.get("metadata", {}),
            ))
        return blocks

    # =========================================================================
    # 插件效果加载
    # =========================================================================

    def load_plugin_effects(
        self,
        generate_missing: bool = True,
        use_catalog: bool = True,
    ) -> Dict[str, EffectFullInfo]:
        """加载插件效果。

        优先从预生成的 effect_catalog.json 加载，若不存在则通过
        KBScanner 扫描插件目录生成。

        Args:
            generate_missing: 是否生成缺失的效果（用于达到 5000+ 目标）
            use_catalog: 是否优先使用预生成的效果目录

        Returns:
            效果名称 -> EffectFullInfo 字典
        """
        if use_catalog:
            catalog_path = Path(_DEFAULT_EFFECT_CATALOG)
            if catalog_path.exists():
                try:
                    return self._load_from_catalog(catalog_path)
                except Exception as e:
                    logger.warning(f"从 effect_catalog.json 加载失败，回退到扫描: {e}")

        from knowledge_base.kb_scanner import KBScanner

        logger.info("开始加载插件效果...")

        scanner = KBScanner()
        scanner.scan_plugins(generate_missing=generate_missing)
        scanner.scan_knowledge_base()

        effects: Dict[str, EffectFullInfo] = {}

        for key, effect_info in scanner._effects.items():
            full_info = self._convert_to_full_info(effect_info)
            full_info = self.enrich_effect_with_kb(full_info)
            effects[key] = full_info

        logger.info(f"插件效果加载完成，共 {len(effects)} 个效果")
        return effects

    def _load_from_catalog(self, catalog_path: Path) -> Dict[str, EffectFullInfo]:
        """从预生成的 effect_catalog.json 加载效果。

        Args:
            catalog_path: 效果目录 JSON 文件路径

        Returns:
            效果名称 -> EffectFullInfo 字典
        """
        import json

        logger.info(f"从效果目录加载: {catalog_path}")

        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        effects: Dict[str, EffectFullInfo] = {}
        effects_data = data.get("effects", data)

        if isinstance(effects_data, dict):
            items = effects_data.items()
        elif isinstance(effects_data, list):
            items = [(e.get("name", ""), e) for e in effects_data]
        else:
            items = []

        for key, effect_data in items:
            try:
                full_info = EffectFullInfo(
                    name=effect_data.get("name", key),
                    match_name=effect_data.get("match_name", effect_data.get("name", key)),
                    category=effect_data.get("category", "other"),
                    plugin_package=effect_data.get("plugin_package", ""),
                    description=effect_data.get("description", ""),
                    params=effect_data.get("params", {}),
                    usage_scenarios=effect_data.get("usage_scenarios", []),
                    default_presets=effect_data.get("default_presets", {}),
                    source=effect_data.get("source", "catalog"),
                    confidence=effect_data.get("confidence", 0.7),
                )
                effects[full_info.name.lower()] = full_info
            except Exception as e:
                logger.debug(f"跳过无效效果条目 {key}: {e}")

        logger.info(f"从效果目录加载了 {len(effects)} 个效果")
        return effects

    def _convert_to_full_info(self, effect_info: Any) -> EffectFullInfo:
        """将 KBScanner 的 EffectInfo 转换为 EffectFullInfo。"""
        return EffectFullInfo(
            name=effect_info.name,
            match_name=effect_info.match_name,
            category=effect_info.category,
            plugin_package=effect_info.plugin_package,
            description=effect_info.description,
            params=effect_info.params,
            usage_scenarios=effect_info.usage_scenarios,
            default_presets=effect_info.default_presets,
            source=effect_info.source,
            confidence=effect_info.confidence,
        )

    # =========================================================================
    # 效果模板生成
    # =========================================================================

    def generate_effect_template(
        self,
        effect_name: str,
        category: str = "",
    ) -> Dict[str, Any]:
        """为效果生成默认参数模板。

        根据效果分类生成默认参数模板。如果指定了分类则直接使用，
        否则自动从效果名称推断分类。

        Args:
            effect_name: 效果名称
            category: 效果分类（可选，自动推断）

        Returns:
            参数字典，包含参数名、类型、范围、默认值、说明
        """
        if not category:
            category = self._infer_category(effect_name)

        template = _PARAM_TEMPLATES.get(category, _PARAM_TEMPLATES["other"])
        return dict(template)

    def _infer_category(self, effect_name: str) -> str:
        """从效果名称推断分类。"""
        try:
            from knowledge_base.kb_scanner import KBScanner
            scanner = KBScanner()
            return scanner.classify_effect(effect_name)
        except Exception:
            pass

        name_lower = effect_name.lower()
        for cat, keywords in _PARAM_TEMPLATES.items():
            if cat == "other":
                continue
            if cat in name_lower:
                return cat

        return "other"

    # =========================================================================
    # 知识库内容丰富
    # =========================================================================

    def enrich_effect_with_kb(self, effect: EffectFullInfo) -> EffectFullInfo:
        """用知识库内容丰富效果说明。

        从知识库中查找相关描述，补充效果说明、使用场景和预设。

        Args:
            effect: 效果信息对象

        Returns:
            丰富后的效果信息对象
        """
        if not effect.description:
            effect.description = f"{effect.name} 效果 - {effect.category} 分类"

        if not effect.usage_scenarios:
            scenarios = _USAGE_SCENARIOS.get(effect.category, [])
            effect.usage_scenarios = list(scenarios)

        if not effect.params:
            effect.params = self.generate_effect_template(
                effect.name, effect.category
            )

        if not effect.default_presets:
            effect.default_presets = self._generate_default_presets(
                effect.name, effect.category
            )

        return effect

    def _generate_default_presets(
        self,
        effect_name: str,
        category: str,
    ) -> List[Dict[str, Any]]:
        """生成默认预设。"""
        presets = []

        if category == "blur":
            presets = [
                {
                    "name": "轻微模糊",
                    "params": {"Blurriness": 3},
                    "description": "轻微柔化画面",
                },
                {
                    "name": "中度模糊",
                    "params": {"Blurriness": 15},
                    "description": "中等程度模糊",
                },
                {
                    "name": "重度模糊",
                    "params": {"Blurriness": 50},
                    "description": "强烈模糊效果",
                },
            ]
        elif category == "color":
            presets = [
                {
                    "name": "暖色调",
                    "params": {"Saturation": 10, "Brightness": 5},
                    "description": "温暖的色调",
                },
                {
                    "name": "冷色调",
                    "params": {"Saturation": 10, "Brightness": -5},
                    "description": "清冷的色调",
                },
                {
                    "name": "电影感",
                    "params": {"Contrast": 15, "Saturation": -10},
                    "description": "电影级调色",
                },
            ]
        elif category == "light":
            presets = [
                {
                    "name": "柔和发光",
                    "params": {"Glow Radius": 10, "Glow Intensity": 0.8},
                    "description": "温和的发光效果",
                },
                {
                    "name": "强烈发光",
                    "params": {"Glow Radius": 30, "Glow Intensity": 2.0},
                    "description": "强烈的发光效果",
                },
            ]
        elif category == "particle":
            presets = [
                {
                    "name": "细雨",
                    "params": {"Particles/Sec": 200, "Longevity": 2, "Size": 2},
                    "description": "小雨效果",
                },
                {
                    "name": "暴雪",
                    "params": {"Particles/Sec": 500, "Longevity": 5, "Size": 5},
                    "description": "大雪效果",
                },
            ]
        else:
            presets = [
                {
                    "name": "默认",
                    "params": {},
                    "description": "默认参数设置",
                },
                {
                    "name": "轻量",
                    "params": {"Amount": 25},
                    "description": "轻量效果",
                },
                {
                    "name": "强度",
                    "params": {"Amount": 75},
                    "description": "强度效果",
                },
            ]

        return presets

    # =========================================================================
    # 效果目录导出
    # =========================================================================

    def export_effect_catalog(
        self,
        output_path: str = "",
        format: str = "json",
    ) -> str:
        """导出效果目录。

        Args:
            output_path: 输出文件路径
            format: 导出格式（json/csv）

        Returns:
            输出文件路径
        """
        effects = self.load_plugin_effects()

        if not output_path:
            output_path = _DEFAULT_EFFECT_CATALOG

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            data = []
            for key, effect in effects.items():
                data.append({
                    "name": effect.name,
                    "match_name": effect.match_name,
                    "category": effect.category,
                    "plugin_package": effect.plugin_package,
                    "description": effect.description,
                    "params": effect.params,
                    "usage_scenarios": effect.usage_scenarios,
                    "default_presets": effect.default_presets,
                    "source": effect.source,
                    "confidence": effect.confidence,
                })

            output.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(f"效果目录已导出到: {output}")

        return str(output)
