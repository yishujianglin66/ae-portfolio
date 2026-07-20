"""统一资源索引服务 - Resource Index Service.

提供 D:/AE-Work/resources/ 资源库的统一索引、查询与清单 API。
消除引擎/服务对资源库的硬编码路径依赖，让 AI 规划器能感知可用资源。

设计原则：
    - 惰性扫描：首次调用任何 find_* 方法时触发扫描
    - 缓存机制：扫描结果按类别缓存，支持 refresh_index() 刷新
    - 模糊匹配：精确 → 小写不敏感 → 包含匹配
    - 异步优先：所有 I/O 操作使用 async def + asyncio.to_thread()
    - LLM 友好：list_* 方法返回结构化清单，供 AI 规划器注入提示词

使用示例：
    from ..services.resource_index_service import resource_index_service

    # 查找单个资源
    font_path = await resource_index_service.find_font("华文中宋")
    lut_path = await resource_index_service.find_lut("cinematic")

    # 获取资源清单（供 AI 规划器使用）
    fonts = await resource_index_service.list_fonts(limit=50)
    luts = await resource_index_service.list_luts(limit=50)

    # 获取索引摘要
    summary = resource_index_service.get_index_summary()
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ..config import settings


# 资源类别 → (settings 字段名, 允许的扩展名列表)
_RESOURCE_CATEGORIES: Dict[str, tuple] = {
    "fonts": ("fonts_dir", (".ttf", ".otf", ".ttc")),
    "luts": ("luts_dir", (".cube", ".3dl", ".look", ".cms")),
    "effects": ("effects_dir", (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")),
    "psd": ("psd_dir", (".psd", ".psb")),
    "audio": ("audio_dir", (".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg")),
    "video": ("video_dir", (".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm")),
    "models": ("models_dir", (".fbx", ".obj", ".max", ".blend", ".3ds", ".dae")),
    "davinci": ("davinci_dir", (".drfx", ".drp", ".setting", ".dctl")),
    "premiere": ("premiere_dir", (".mogrt", ".prfpset", ".prpreset")),
    "projects": ("resource_projects_dir", (".aep", ".aet", ".aepx")),
    "ae_presets": ("presets_dir", (".ffx", ".aex", ".anim")),
    "scripts": ("scripts_dir", (".jsx", ".jsxbin", ".js")),
    "plugins": ("plugins_dir", (".zxp", ".aex", ".exe", ".msi")),
    "templates": ("templates_dir", (".aep", ".aet", ".aepx", ".mogrt")),
    "images": ("images_dir", (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif", ".psd")),
}


@dataclass
class ResourceEntry:
    """资源索引条目。"""

    name: str           # 文件名（不含扩展名）
    file_path: str      # 完整路径（字符串，便于 JSON 序列化）
    extension: str      # 扩展名（小写，含点）
    size_bytes: int     # 文件大小（字节）
    category: str       # 资源类别（fonts/luts/effects/...）
    relative_path: str  # 相对资源库根目录的路径

    def to_dict(self) -> Dict[str, Any]:
        """转为字典（供 API 返回 / LLM 注入使用）。"""
        return asdict(self)


class ResourceIndexService:
    """统一资源索引服务 - 索引 D:/AE-Work/resources/ 资源库。

    单例模式：模块级 `resource_index_service` 实例。
    """

    def __init__(self) -> None:
        self._index: Dict[str, List[ResourceEntry]] = {}
        self._initialized: bool = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # 索引初始化与刷新
    # ------------------------------------------------------------------

    async def _ensure_initialized(self) -> None:
        """惰性初始化索引（线程安全）。"""
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            await self._build_index_internal()
            self._initialized = True

    async def refresh_index(self) -> None:
        """刷新索引（重新扫描所有资源类别）。"""
        async with self._lock:
            await self._build_index_internal()
            self._initialized = True

    async def _build_index_internal(self) -> None:
        """构建完整索引（同步扫描在 thread 中执行）。"""
        logger.info("开始构建资源索引...")
        self._index = await asyncio.to_thread(self._scan_all_categories)
        total = sum(len(v) for v in self._index.values())
        summary = {k: len(v) for k, v in self._index.items()}
        logger.info(f"资源索引构建完成: 共 {total} 个资源 | 分布: {summary}")

    def _scan_all_categories(self) -> Dict[str, List[ResourceEntry]]:
        """扫描所有资源类别（同步，在 thread 中调用）。"""
        index: Dict[str, List[ResourceEntry]] = {}
        for category, (settings_field, extensions) in _RESOURCE_CATEGORIES.items():
            index[category] = self._scan_category(category, settings_field, extensions)
        return index

    def _scan_category(
        self,
        category: str,
        settings_field: str,
        extensions: tuple,
    ) -> List[ResourceEntry]:
        """扫描单个资源类别目录。"""
        root_dir: Path = getattr(settings, settings_field, None)
        if root_dir is None:
            logger.warning(f"settings.{settings_field} 未定义，跳过 {category}")
            return []

        if not root_dir.exists():
            logger.warning(f"资源目录不存在: {root_dir} (category={category})")
            return []

        entries: List[ResourceEntry] = []
        try:
            for file_path in root_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                if file_path.suffix.lower() not in extensions:
                    continue
                try:
                    stat = file_path.stat()
                except OSError:
                    continue
                try:
                    rel_path = str(file_path.relative_to(settings.resources_dir))
                except ValueError:
                    rel_path = str(file_path)
                entries.append(
                    ResourceEntry(
                        name=file_path.stem,
                        file_path=str(file_path),
                        extension=file_path.suffix.lower(),
                        size_bytes=stat.st_size,
                        category=category,
                        relative_path=rel_path,
                    )
                )
        except Exception as e:
            logger.error(f"扫描 {category} 目录失败: {e}")
            return []

        return entries

    # ------------------------------------------------------------------
    # 查询 API
    # ------------------------------------------------------------------

    async def find_resource(
        self,
        category: str,
        name: str,
        exact: bool = False,
    ) -> Optional[Path]:
        """查找资源（通用方法）。

        Args:
            category: 资源类别（fonts/luts/effects/psd/audio/video/models/davinci/premiere/projects/ae_presets）
            name: 资源名称（文件名，可不含扩展名）
            exact: 是否精确匹配文件名（默认模糊匹配）

        Returns:
            找到的资源文件 Path，未找到返回 None
        """
        await self._ensure_initialized()
        entries = self._index.get(category, [])
        return await asyncio.to_thread(self._match_entry, entries, name, exact)

    def _match_entry(
        self,
        entries: List[ResourceEntry],
        name: str,
        exact: bool,
    ) -> Optional[Path]:
        """在条目列表中匹配名称（同步）。"""
        if not entries:
            return None

        name_lower = name.lower()
        name_stripped = Path(name).stem.lower()

        # 1. 完全匹配文件名（含扩展名）
        for entry in entries:
            if Path(entry.file_path).name.lower() == name_lower:
                return Path(entry.file_path)

        # 2. 精确匹配 stem（文件名不含扩展名）
        for entry in entries:
            if entry.name.lower() == name_stripped:
                return Path(entry.file_path)

        if exact:
            return None

        # 3. 小写不敏感的 stem 匹配
        for entry in entries:
            if entry.name.lower() == name_lower:
                return Path(entry.file_path)

        # 4. 包含匹配（用户输入是 stem 的子串，或 stem 是用户输入的子串）
        for entry in entries:
            entry_lower = entry.name.lower()
            if name_lower in entry_lower or entry_lower in name_lower:
                return Path(entry.file_path)

        return None

    async def find_font(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找字体文件。"""
        return await self.find_resource("fonts", name, exact)

    async def find_lut(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找 LUT 文件。"""
        return await self.find_resource("luts", name, exact)

    async def find_effect_image(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找特效贴图。"""
        return await self.find_resource("effects", name, exact)

    async def find_psd(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找 PSD 文件。"""
        return await self.find_resource("psd", name, exact)

    async def find_audio(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找音频文件。"""
        return await self.find_resource("audio", name, exact)

    async def find_video(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找视频文件。"""
        return await self.find_resource("video", name, exact)

    async def find_model(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找 3D 模型文件。"""
        return await self.find_resource("models", name, exact)

    async def find_davinci_preset(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找达芬奇预设/插件文件。"""
        return await self.find_resource("davinci", name, exact)

    async def find_premiere_preset(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找 PR 预设文件。"""
        return await self.find_resource("premiere", name, exact)

    async def find_project(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找 AE 工程文件。"""
        return await self.find_resource("projects", name, exact)

    async def find_ae_preset(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找 AE 插件预设文件（.ffx / .aex / .anim）。"""
        return await self.find_resource("ae_presets", name, exact)

    async def find_script(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找 AE 脚本文件（.jsx / .jsxbin / .js）。"""
        return await self.find_resource("scripts", name, exact)

    async def find_plugin_package(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找 AE 插件安装包（.zxp / .aex / .exe / .msi）。"""
        return await self.find_resource("plugins", name, exact)

    async def find_template(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找 AE 工程模板文件（.aep / .aet / .mogrt）。"""
        return await self.find_resource("templates", name, exact)

    async def find_image(self, name: str, exact: bool = False) -> Optional[Path]:
        """查找图片素材文件。"""
        return await self.find_resource("images", name, exact)

    # ------------------------------------------------------------------
    # 列表 API（供 AI 规划器注入提示词）
    # ------------------------------------------------------------------

    async def list_resources_by_type(
        self,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """列出指定类别的资源清单。

        Args:
            category: 资源类别
            limit: 返回数量上限
            offset: 偏移量（分页）

        Returns:
            资源条目字典列表
        """
        await self._ensure_initialized()
        entries = self._index.get(category, [])
        sliced = entries[offset : offset + limit]
        return [e.to_dict() for e in sliced]

    async def list_fonts(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出字体清单（供 LLM 推荐字体时使用）。"""
        return await self.list_resources_by_type("fonts", limit, offset)

    async def list_luts(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出 LUT 清单（供 LLM 推荐调色方案时使用）。"""
        return await self.list_resources_by_type("luts", limit, offset)

    async def list_effects(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出现效贴图清单。"""
        return await self.list_resources_by_type("effects", limit, offset)

    async def list_audio(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出音频清单。"""
        return await self.list_resources_by_type("audio", limit, offset)

    async def list_video(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出视频素材清单。"""
        return await self.list_resources_by_type("video", limit, offset)

    async def list_scripts(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出 AE 脚本清单。"""
        return await self.list_resources_by_type("scripts", limit, offset)

    async def list_plugins(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出 AE 插件包清单。"""
        return await self.list_resources_by_type("plugins", limit, offset)

    async def list_templates(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出 AE 模板清单。"""
        return await self.list_resources_by_type("templates", limit, offset)

    async def list_images(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出图片素材清单。"""
        return await self.list_resources_by_type("images", limit, offset)

    # ------------------------------------------------------------------
    # 摘要与统计
    # ------------------------------------------------------------------

    def get_index_summary(self) -> Dict[str, int]:
        """获取索引摘要（各类别资源数量）。

        Returns:
            类别 → 数量 的字典；若未初始化返回空字典
        """
        if not self._initialized:
            return {}
        return {category: len(entries) for category, entries in self._index.items()}

    def get_total_count(self) -> int:
        """获取资源总数。"""
        if not self._initialized:
            return 0
        return sum(len(v) for v in self._index.values())

    def is_initialized(self) -> bool:
        """索引是否已初始化。"""
        return self._initialized


# 模块级单例
resource_index_service = ResourceIndexService()
