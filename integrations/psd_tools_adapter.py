"""
PSD Tools Adapter v1.0
========================
PSD 文件解析适配器，基于 psd-tools (1.4k★)。

能力:
  - 解析 PSD 文件结构 (图层/通道/蒙版/文字)
  - 导出单个图层为 PNG
  - 合成完整 PSD 为图像
  - 提取文字内容
  - 列出使用的字体

集成来源: psd-tools/psd-tools (GitHub 1.4k stars)
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "psd_exports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class PsdToolsAdapter:
    """PSD 文件解析适配器"""

    SUPPORTED_OPERATIONS = [
        "parse_psd", "extract_layers", "export_layer_as_png",
        "get_layer_info", "composite_psd", "list_fonts",
        "export_all_layers", "get_psd_metadata",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._available = False
        self._init_check()

    def _init_check(self):
        try:
            from psd_tools import PSDImage
            self._available = True
            logger.info("[PsdTools] psd-tools available")
        except ImportError:
            logger.warning("[PsdTools] psd-tools not installed")

    def check_available(self) -> bool:
        return self._available

    def list_operations(self) -> list[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        start = time.time()
        try:
            if operation == "parse_psd":
                result = self._parse_psd(params)
            elif operation == "extract_layers":
                result = self._extract_layers(params)
            elif operation == "export_layer_as_png":
                result = self._export_layer(params)
            elif operation == "get_layer_info":
                result = self._get_layer_info(params)
            elif operation == "composite_psd":
                result = self._composite(params)
            elif operation == "list_fonts":
                result = self._list_fonts(params)
            elif operation == "export_all_layers":
                result = self._export_all_layers(params)
            elif operation == "get_psd_metadata":
                result = self._get_metadata(params)
            else:
                return {"status": "error", "error": f"Unknown operation: {operation}"}

            result["status"] = "success"
            result["duration_ms"] = (time.time() - start) * 1000
            return result
        except Exception as e:
            logger.error(f"[PsdTools] {operation} failed: {e}")
            return {
                "status": "error",
                "operation": operation,
                "error": str(e),
                "duration_ms": (time.time() - start) * 1000,
            }

    def _load_psd(self, params: dict):
        from psd_tools import PSDImage
        path = params.get("psd_path") or params.get("file_path")
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(f"PSD file not found: {path}")
        return PSDImage.open(path), path

    def _parse_psd(self, params: dict) -> dict:
        psd, path = self._load_psd(params)
        layers = []
        for layer in psd.descendants():
            layers.append({
                "name": layer.name,
                "kind": layer.kind,
                "visible": layer.visible,
                "left": layer.left,
                "top": layer.top,
                "right": layer.right,
                "bottom": layer.bottom,
                "width": layer.width,
                "height": layer.height,
                "opacity": layer.opacity,
                "blend_mode": str(layer.blend_mode),
                "is_group": layer.kind == "group",
            })
        return {
            "file": os.path.basename(path),
            "width": psd.width,
            "height": psd.height,
            "num_channels": getattr(psd, 'num_channels', len(psd.channels) if hasattr(psd, 'channels') else 0),
            "depth": psd.depth,
            "color_mode": str(psd.color_mode),
            "layer_count": len(layers),
            "layers": layers,
        }

    def _extract_layers(self, params: dict) -> dict:
        psd, path = self._load_psd(params)
        layer_names = []
        for layer in psd.descendants():
            layer_names.append({
                "name": layer.name,
                "kind": layer.kind,
                "index": len(layer_names),
            })
        return {"layers": layer_names, "count": len(layer_names)}

    def _export_layer(self, params: dict) -> dict:
        psd, path = self._load_psd(params)
        layer_name = params.get("layer_name")
        layer_index = params.get("layer_index")

        target = None
        for i, layer in enumerate(psd.descendants()):
            if layer_name and layer.name == layer_name:
                target = layer
                break
            if layer_index is not None and i == layer_index:
                target = layer
                break

        if target is None:
            return {"status": "error", "error": f"Layer not found: {layer_name or layer_index}"}

        stem = Path(path).stem
        output_path = params.get("output_path", str(OUTPUT_DIR / f"{stem}_{target.name}.png"))
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        try:
            img = target.composite()
            if img:
                img.save(output_path)
                return {
                    "layer_name": target.name,
                    "output_path": output_path,
                    "size": os.path.getsize(output_path),
                }
            else:
                return {"status": "error", "error": "Layer composite returned None"}
        except Exception as e:
            return {"status": "error", "error": f"Export failed: {e}"}

    def _get_layer_info(self, params: dict) -> dict:
        psd, path = self._load_psd(params)
        layer_name = params.get("layer_name")
        for layer in psd.descendants():
            if layer.name == layer_name or layer_name is None:
                info = {
                    "name": layer.name,
                    "kind": layer.kind,
                    "visible": layer.visible,
                    "opacity": layer.opacity,
                    "blend_mode": str(layer.blend_mode),
                    "bounds": {"left": layer.left, "top": layer.top, "right": layer.right, "bottom": layer.bottom},
                    "has_mask": layer.has_mask,
                    "has_text": hasattr(layer, 'text_data') and layer.text_data is not None,
                }
                if layer_name:
                    return {"layer": info}
        return {"status": "error", "error": f"Layer not found: {layer_name}"}

    def _composite(self, params: dict) -> dict:
        psd, path = self._load_psd(params)
        img = psd.composite()
        stem = Path(path).stem
        output_path = params.get("output_path", str(OUTPUT_DIR / f"{stem}_composite.png"))
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        img.save(output_path)
        return {
            "output_path": output_path,
            "size": os.path.getsize(output_path),
            "width": img.width,
            "height": img.height,
        }

    def _list_fonts(self, params: dict) -> dict:
        psd, path = self._load_psd(params)
        fonts = set()
        for layer in psd.descendants():
            if hasattr(layer, 'text_data') and layer.text_data:
                try:
                    td = layer.text_data
                    if hasattr(td, 'engine_dict'):
                        for style_run in td.engine_dict.get("ResourceDict", {}).get("FontSet", []):
                            fonts.add(style_run.get("Name", "Unknown"))
                except Exception:
                    pass
        return {"fonts": list(fonts), "count": len(fonts)}

    def _export_all_layers(self, params: dict) -> dict:
        psd, path = self._load_psd(params)
        stem = Path(path).stem
        out_dir = params.get("output_dir", str(OUTPUT_DIR / stem))
        os.makedirs(out_dir, exist_ok=True)
        exported = []
        for i, layer in enumerate(psd.descendants()):
            try:
                img = layer.composite()
                if img and img.width > 0 and img.height > 0:
                    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in layer.name)
                    fp = os.path.join(out_dir, f"{i:03d}_{safe_name}.png")
                    img.save(fp)
                    exported.append({"name": layer.name, "path": fp, "size": os.path.getsize(fp)})
            except Exception:
                pass
        return {"exported": len(exported), "output_dir": out_dir, "layers": exported}

    def _get_metadata(self, params: dict) -> dict:
        psd, path = self._load_psd(params)
        return {
            "file": os.path.basename(path),
            "width": psd.width,
            "height": psd.height,
            "num_channels": getattr(psd, 'num_channels', len(psd.channels) if hasattr(psd, 'channels') else 0),
            "depth": psd.depth,
            "color_mode": str(psd.color_mode),
            "version": psd.version,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "available": self._available,
            "operations": len(self.SUPPORTED_OPERATIONS),
        }
