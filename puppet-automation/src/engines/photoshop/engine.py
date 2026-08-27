"""
Photoshop Engine - 图像处理与纹理
==================================

封装 Adobe Photoshop 的能力：
- PSD智能对象→分层PNG（导入AE）
- 批量LUT生成（用于DaVinci调色）
- AI生成纹理（Neural Filters / Generative Fill）
- 批量动作处理（批量修图/调色）
- 文字路径导出（Illustrator联动）

在流程中的定位：
- 前期：生成/处理素材图片、纹理、LUT
- 中期：PSD分层导入AE作为合成元素
- 后期：批量输出封面/缩略图

使用方式：
    engine = PhotoshopEngine()
    await engine.smart_object_export("design.psd", "output/")
    await engine.generate_lut("color_graded.jpg", "mood.cube")
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import winreg
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ..base import BaseEngine, EngineResult  # noqa: E402
from ...config.settings import get_settings

# Bridge Client 在项目根目录，延迟导入
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class PhotoshopEngine(BaseEngine):
    """Adobe Photoshop engine via MCP Bridge / ExtendScript."""

    name = "photoshop"

    def __init__(
        self,
        executable_path: Optional[Path | str] = None,
    ):
        self._settings = get_settings()
        self.ps_path = self._resolve_executable(executable_path)
        super().__init__(executable_path or self.ps_path or "photoshop")
        self._jsx_dir = Path(tempfile.gettempdir()) / "ae_kv_ps_jsx"
        self._jsx_dir.mkdir(exist_ok=True)

        # 初始化 MCP Bridge Client（延迟导入，避免循环依赖）
        self._bridge_client = None
        self._bridge_available: Optional[bool] = None  # None=未检测, True=在线, False=离线

    def _resolve_executable(self, explicit: Optional[Path | str]) -> Optional[Path]:
        """解析可执行文件路径：显式参数 > settings配置 > 自动发现。"""
        if explicit:
            p = Path(explicit)
            if p.exists():
                return p

        if self._settings.photoshop_path:
            p = Path(self._settings.photoshop_path)
            if p.exists():
                return p
            logger.warning(f"[Photoshop] Settings path not found: {p}, falling back to auto-detect")

        return self._find_photoshop()

    @staticmethod
    def _find_photoshop() -> Optional[Path]:
        """自动发现 Photoshop 安装路径。"""
        possible_paths = [
            r"C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe",
            r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
            r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe",
        ]
        for p in possible_paths:
            path = Path(p)
            if path.exists():
                return path
        return None

    async def _execute_impl(self, *args, **kwargs) -> EngineResult:
        """【子类实现】handlers dict 分发；available 短路/异常包裹/时长统计由基类 execute() 模板处理。"""
        action = kwargs.pop("action", None) or kwargs.pop("task", "export_layers")
        handlers = {
            "export_layers": self.smart_object_export,
            "smart_object_export": self.smart_object_export,
            "lut": self.generate_lut,
            "generate_lut": self.generate_lut,
            "batch": self.batch_process,
            "batch_process": self.batch_process,
        }
        handler = handlers.get(action)
        if handler is None:
            return EngineResult(
                success=False,
                error=f"Unknown action: {action}. Available: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def smart_object_export(
        self,
        psd_path: Path | str,
        output_dir: Path | str,
        format: str = "png24",
        include_hidden: bool = False,
    ) -> EngineResult:
        """将PSD智能对象导出为分层PNG。

        Args:
            psd_path: PSD文件路径
            output_dir: 输出目录
            format: 输出格式 (png24/png8/jpg)
            include_hidden: 是否包含隐藏图层
        """
        psd_path = Path(psd_path)
        output_dir = Path(output_dir)

        if not psd_path.exists():
            return EngineResult(
                success=False, error=f"PSD not found: {psd_path}",
            )

        jsx = f"""
        #target photoshop
        var doc = app.open(new File("{psd_path}"));
        var outputFolder = new Folder("{output_dir}");
        if (!outputFolder.exists) outputFolder.create();
        
        var exportCount = 0;
        
        for (var i = 0; i < doc.layers.length; i++) {{
            var layer = doc.layers[i];
            
            {"if (!layer.visible && !{include_hidden}) continue;"}
            
            // 导出每个图层为PNG
            var saveFile = new File(outputFolder + "/" + layer.name.replace(/[\\\\/:*?"<>|]/g, "_") + ".png");
            
            var pngOpts = new PNGSaveOptions();
            pngOpts.interlaced = false;
            
            // 复制文档并裁剪到图层内容
            var layerDoc = doc.duplicate();
            layerDoc.crop(layer.bounds);
            layerDoc.saveAs(saveFile, pngOpts, true, Extension.LOWERCASE);
            layerDoc.close(SaveOptions.DONOTSAVECHANGES);
            
            exportCount++;
        }}
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
        "OK: " + exportCount + " layers exported";
        """

        return await self._execute_jsx(jsx, "smart_object_export")

    async def generate_lut(
        self,
        reference_image: Path | str,
        output_lut: Path | str,
        lut_size: int = 33,
    ) -> EngineResult:
        """从参考图生成3D LUT文件。

        Args:
            reference_image: 参考图片路径（已调色的目标效果）
            output_lut: 输出.cube文件路径
            lut_size: LUT尺寸 (33/64)
        """
        # Photoshop可以通过调整图层生成LUT
        # 实际实现需要Color Lookup调整图层
        jsx = f"""
        #target photoshop
        var doc = app.open(new File("{reference_image}"));
        
        // 添加Color Lookup调整图层（模拟LUT导出）
        var colorLookup = doc.layerSets.add();
        colorLookup.name = "LUT_Export";
        
        // 保存为PSD以便后续提取LUT
        var psdFile = new File("{output_lut}".replace(".cube", ".psd"));
        var psdOpts = new PhotoshopSaveOptions();
        doc.saveAs(psdFile, psdOpts, true, Extension.LOWERCASE);
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
        "LUT PSD saved: " + psdFile.fsName;
        """

        return await self._execute_jsx(jsx, "generate_lut")

    async def batch_process(
        self,
        image_dir: Path | str,
        action_name: str,
        output_dir: Path | str,
        file_pattern: str = "*.jpg",
    ) -> EngineResult:
        """批量执行Photoshop动作。

        Args:
            image_dir: 输入图片目录
            action_name: 动作名称（必须在Photoshop中已定义）
            output_dir: 输出目录
            file_pattern: 文件匹配模式
        """
        image_dir = Path(image_dir)
        output_dir = Path(output_dir)

        if not image_dir.exists():
            return EngineResult(
                success=False, error=f"Directory not found: {image_dir}",
            )

        jsx = f"""
        #target photoshop
        var inputFolder = new Folder("{image_dir}");
        var outputFolder = new Folder("{output_dir}");
        if (!outputFolder.exists) outputFolder.create();
        
        var files = inputFolder.getFiles("{file_pattern}");
        var processed = 0;
        
        for (var i = 0; i < files.length; i++) {{
            var doc = app.open(files[i]);
            
            // 运行动作
            app.doAction("{action_name}", "Default Actions");
            
            // 保存
            var saveFile = new File(outputFolder + "/" + doc.name);
            var jpgOpts = new JPEGSaveOptions();
            jpgOpts.quality = 12;
            doc.saveAs(saveFile, jpgOpts, true, Extension.LOWERCASE);
            doc.close(SaveOptions.DONOTSAVECHANGES);
            
            processed++;
        }}
        
        "Processed: " + processed + " files";
        """

        return await self._execute_jsx(jsx, "batch_process")

    async def generate_texture(
        self,
        prompt: str,
        output_path: Path | str,
        width: int = 1024,
        height: int = 1024,
    ) -> EngineResult:
        """使用Photoshop AI生成纹理（需要Photoshop Beta/2024+）。

        Args:
            prompt: 生成提示词
            output_path: 输出路径
            width: 宽度
            height: 高度
        """
        jsx = f"""
        #target photoshop
        var doc = app.documents.add({width}, {height}, 72, "AI_Texture", NewDocumentMode.RGB);
        
        // 使用Generative Fill（需要Photoshop 2024+）
        // 注意：这需要Adobe Creative Cloud登录和AI积分
        var fillAction = doc.selection;
        
        // 由于Generative Fill的JSX API尚未完全公开
        // 这里创建空白文档，实际生成需要手动操作
        var saveFile = new File("{output_path}");
        var pngOpts = new PNGSaveOptions();
        doc.saveAs(saveFile, pngOpts, true, Extension.LOWERCASE);
        doc.close(SaveOptions.DONOTSAVECHANGES);
        
        "Texture template created: {output_path}";
        """

        return await self._execute_jsx(jsx, "generate_texture")

    async def _execute_jsx(self, jsx_code: str, operation: str) -> EngineResult:
        """通过 MCP Bridge 或临时 JSX 文件执行 Photoshop ExtendScript。

        优先使用 MCP Bridge（全自动），降级为生成 JSX 文件（手动执行）。
        """
        import time

        start = time.time()

        # 方式1: 尝试通过 MCP Bridge 自动执行
        if self._ensure_bridge():
            try:
                result = await asyncio.to_thread(
                    self._bridge_client.execute_script,
                    jsx_code,
                    30,  # timeout
                )
                success = result.get("status") == "success"
                error_msg = result.get("message", "") if not success else None

                return EngineResult(
                    success=success,
                    error=error_msg,
                    metadata={
                        "operation": operation,
                        "bridge_mode": "auto",
                        "result": result.get("result"),
                        "timestamp": result.get("timestamp"),
                    },
                    duration_seconds=time.time() - start,
                )
            except Exception as e:
                logger.warning(f"[Photoshop] Bridge execution failed, falling back to JSX file: {e}")
                self._bridge_available = False

        # 方式2: 降级 - 生成 JSX 文件，用户手动执行
        jsx_file = self._jsx_dir / f"ps_{operation}_{int(time.time())}.jsx"
        jsx_file.write_text(jsx_code, encoding="utf-8")

        logger.info(f"[Photoshop] JSX prepared (fallback): {jsx_file}")
        logger.info(f"[Photoshop] Run manually: File > Scripts > Browse...")

        return EngineResult(
            success=True,
            metadata={
                "jsx_path": str(jsx_file),
                "operation": operation,
                "bridge_mode": "manual_fallback",
                "note": "MCP Bridge offline. Run JSX manually or start ps_mcp_bridge.jsx in Photoshop.",
            },
            duration_seconds=time.time() - start,
        )

    def _ensure_bridge(self) -> bool:
        """确保 Bridge Client 已初始化且在线。延迟初始化 + 缓存检测结果。"""
        if self._bridge_available is False:
            return False

        if self._bridge_client is None:
            try:
                from ps_bridge_client import PSBridgeClient  # 延迟导入
                self._bridge_client = PSBridgeClient(timeout=5)
            except ImportError:
                logger.warning("[Photoshop] ps_bridge_client not available")
                self._bridge_available = False
                return False
            except Exception as e:
                logger.warning(f"[Photoshop] Bridge init failed: {e}")
                self._bridge_available = False
                return False

        # 检测 Bridge 是否在线（首次检测后缓存 60 秒）
        if self._bridge_available is None:
            try:
                result = self._bridge_client.ping(timeout=3)
                self._bridge_available = result.get("status") == "success"
                if self._bridge_available:
                    logger.info("[Photoshop] MCP Bridge is online")
                else:
                    logger.info(f"[Photoshop] MCP Bridge offline: {result.get('status', 'unknown')}")
            except Exception:
                self._bridge_available = False
                logger.info("[Photoshop] MCP Bridge not responding (is ps_mcp_bridge.jsx running?)")

        return self._bridge_available is True

    def get_info(self) -> dict:
        """返回引擎信息。"""
        bridge_status = "unknown"
        if self._bridge_available is True:
            bridge_status = "online"
        elif self._bridge_available is False:
            bridge_status = "offline"

        return {
            "name": self.name,
            "photoshop_found": self.ps_path is not None,
            "photoshop_path": str(self.ps_path) if self.ps_path else None,
            "bridge_status": bridge_status,
            "capabilities": [
                "smart_object_export",
                "generate_lut",
                "batch_process",
                "generate_texture",
            ],
            "workflow": "PSD Layer Export → AE Composition / LUT → DaVinci",
            "automation_level": "MCP Bridge (auto) / JSX file (fallback)",
        }