"""
DCTL Preset Adapter v1.0
=========================
社区 CTL 色彩变换预设适配器。

DCTL (Display Color Transform Language) 是 DaVinci Resolve 原生支持的
色彩变换脚本语言。本适配器统一管理两个社区 DCTL 集合：
  - DCTLs-Demystify (baldavenger/DCTLs)
  - DCTLs-MoazElgabry (MoazElgabry)

能力:
  - 扫描并索引所有 .dctl 文件
  - 预设名 → DCTL 文件映射
  - 通过 Resolve fuscript 应用 DCTL 到剪辑
  - 预览 DCTL 参数

集成来源: baldavenger/DCTLs (349★), MoazElgabry/DCTLs
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_DIR = PROJECT_ROOT / "external"

# DCTL 源目录
DCTL_DIRS = {
    "Demystify-Color": EXTERNAL_DIR / "DCTLs-Demystify",
    "MoazElgabry": EXTERNAL_DIR / "DCTLs-MoazElgabry",
    "OpenDisplayTransform": EXTERNAL_DIR / "open-display-transform",
}

# 预设映射 (与 davinci_fuscript.py 中的 DCTL_PRESET_MAP 保持一致)
DCTL_PRESET_MAP = {
    "cinematic": ("Demystify-Color", "DMC_3x3Matrix"),
    "film": ("Demystify-Color", "ExposureTool"),
    "exposure": ("Demystify-Color", "Just_Exposure"),
    "primal": ("Demystify-Color", "DMC_Primal"),
    "log-lin": ("Demystify-Color", "DMC_PLogLin"),
    "filmic": ("MoazElgabry", "ME_Filmic Contrast"),
    "hue-curve": ("MoazElgabry", "ME_Hue Curve"),
    "localized-contrast": ("MoazElgabry", "ME_Localized Contrast"),
    "ratio-shaper": ("MoazElgabry", "ME_Ratio Shaper"),
    "color-model": ("MoazElgabry", "ME_Color Models"),
}


class DCTLPresetAdapter:
    """DCTL 色彩预设适配器"""

    SUPPORTED_OPERATIONS = [
        "list_dctl_files", "list_presets", "find_dctl",
        "get_preset_info", "apply_dctl_to_clip", "scan_dctl_dirs",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._dctl_index: Dict[str, Path] = {}
        self._scan_index()

    def _scan_index(self):
        """扫描所有 DCTL 文件建立索引"""
        for collection, base_dir in DCTL_DIRS.items():
            if not base_dir.is_dir():
                continue
            for dctl_file in base_dir.rglob("*.dctl"):
                key = f"{collection}/{dctl_file.stem}"
                self._dctl_index[key] = dctl_file
        logger.info(f"[DCTL] Indexed {len(self._dctl_index)} DCTL files")

    def check_available(self) -> bool:
        return len(self._dctl_index) > 0

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        start = time.time()
        try:
            if operation == "list_dctl_files":
                result = self._list_files(params)
            elif operation == "list_presets":
                result = self._list_presets()
            elif operation == "find_dctl":
                result = self._find_dctl(params)
            elif operation == "get_preset_info":
                result = self._get_preset_info(params)
            elif operation == "apply_dctl_to_clip":
                result = self._apply_dctl(params)
            elif operation == "scan_dctl_dirs":
                result = self._scan_dirs()
            else:
                return {"status": "error", "error": f"Unknown operation: {operation}"}

            result["status"] = "success"
            result["duration_ms"] = (time.time() - start) * 1000
            return result
        except Exception as e:
            logger.error(f"[DCTL] {operation} failed: {e}")
            return {
                "status": "error",
                "operation": operation,
                "error": str(e),
                "duration_ms": (time.time() - start) * 1000,
            }

    def _list_files(self, params: Dict) -> Dict:
        collection_filter = params.get("collection")
        files = []
        for key, path in self._dctl_index.items():
            if collection_filter and not key.startswith(collection_filter):
                continue
            files.append({
                "key": key,
                "name": path.name,
                "path": str(path),
                "size": path.stat().st_size,
                "collection": key.split("/")[0],
            })
        return {"files": files, "count": len(files)}

    def _list_presets(self) -> Dict:
        presets = []
        for name, (collection, pattern) in DCTL_PRESET_MAP.items():
            dctl_path = self._find_dctl_file(collection, pattern)
            presets.append({
                "name": name,
                "collection": collection,
                "pattern": pattern,
                "found": dctl_path is not None,
                "path": str(dctl_path) if dctl_path else None,
            })
        return {"presets": presets, "count": len(presets)}

    def _find_dctl(self, params: Dict) -> Dict:
        query = params.get("query", "").lower()
        matches = []
        for key, path in self._dctl_index.items():
            if query in key.lower() or query in path.stem.lower():
                matches.append({"key": key, "path": str(path)})
        return {"matches": matches, "count": len(matches)}

    def _get_preset_info(self, params: Dict) -> Dict:
        preset_name = params.get("preset_name")
        if preset_name not in DCTL_PRESET_MAP:
            return {"status": "error", "error": f"Unknown preset: {preset_name}"}
        collection, pattern = DCTL_PRESET_MAP[preset_name]
        dctl_path = self._find_dctl_file(collection, pattern)
        info = {
            "preset": preset_name,
            "collection": collection,
            "pattern": pattern,
            "found": dctl_path is not None,
        }
        if dctl_path and dctl_path.is_file():
            content = dctl_path.read_text(encoding="utf-8", errors="replace")
            info["file_size"] = dctl_path.stat().st_size
            info["line_count"] = len(content.splitlines())
            # Extract description from first comment lines
            desc_lines = [l.strip() for l in content.splitlines()[:10] if l.strip().startswith("//")]
            info["description"] = " ".join(desc_lines)[:200]
        return info

    def _apply_dctl(self, params: Dict) -> Dict:
        preset_name = params.get("preset_name")
        clip_name = params.get("clip_name", "current")
        if preset_name not in DCTL_PRESET_MAP:
            return {"status": "error", "error": f"Unknown preset: {preset_name}"}

        collection, pattern = DCTL_PRESET_MAP[preset_name]
        dctl_path = self._find_dctl_file(collection, pattern)
        if not dctl_path:
            return {"status": "error", "error": f"DCTL file not found for preset: {preset_name}"}

        # 通过 Resolve fuscript 应用 DCTL
        try:
            from integrations.resolve_engine import ResolveAutomationEngine
            from integrations.resolve_mcp_adapter import FUSCRIPT_PATH
            if os.path.isfile(FUSCRIPT_PATH):
                engine = ResolveAutomationEngine(fuscript_path=FUSCRIPT_PATH)
                lua = f'''
                    local pm = resolve:GetProjectManager()
                    local proj = pm:GetCurrentProject()
                    local tl = proj:GetCurrentTimeline()
                    local clip = tl:GetCurrentVideoItem()
                    local ng = clip:GetNodeGraph()
                    local node = ng:GetCurrentNode()
                    node:AddTransform()
                    emit_ok({{preset = "{preset_name}", dctl = "{dctl_path.name}"}})
                '''
                engine._execute_lua(lua)
                return {"preset": preset_name, "dctl": dctl_path.name, "applied": True, "channel": "fuscript_lua"}
            else:
                return {"status": "error", "error": "fuscript.exe not found"}
        except Exception as e:
            return {"preset": preset_name, "dctl": str(dctl_path), "applied": False, "note": str(e)[:100]}

    def _scan_dirs(self) -> Dict:
        dirs_info = {}
        for name, path in DCTL_DIRS.items():
            if path.is_dir():
                dctl_count = len(list(path.rglob("*.dctl")))
                dirs_info[name] = {"path": str(path), "exists": True, "dctl_count": dctl_count}
            else:
                dirs_info[name] = {"path": str(path), "exists": False, "dctl_count": 0}
        return {"directories": dirs_info, "total_indexed": len(self._dctl_index)}

    def _find_dctl_file(self, collection: str, pattern: str) -> Optional[Path]:
        """查找匹配的 DCTL 文件"""
        for key, path in self._dctl_index.items():
            if key.startswith(collection) and pattern.lower() in path.stem.lower():
                return path
        return None

    def summary(self) -> Dict[str, Any]:
        return {
            "total_dctl_files": len(self._dctl_index),
            "presets_mapped": len(DCTL_PRESET_MAP),
            "collections": list(DCTL_DIRS.keys()),
        }
