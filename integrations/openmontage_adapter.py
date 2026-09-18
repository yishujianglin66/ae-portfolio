"""
OpenMontage 深度集成适配器 v1.0
=================================
AI 驱动的视频制作 pipeline 引擎。

OpenMontage 提供:
  - 13 个预定义 pipeline (cinematic, animation, documentary, etc.)
  - 6 个视觉风格 (anime, professional, minimalist, etc.)
  - 10+ 工具类别 (audio, avatar, subtitle, video, graphics, etc.)
  - Remotion (React) 渲染后端
  - Backlot 本地 storyboard 服务器 (FastAPI)
  - 多 AI 后端 (Gemini, OpenAI Sora, Kling)

集成来源: OpenMontage (83.5MB 源码)
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_DIR = PROJECT_ROOT / "external"
OM_DIR = EXTERNAL_DIR / "OpenMontage"


class OpenMontageAdapter:
    """OpenMontage 视频制作 pipeline 适配器"""

    SUPPORTED_OPERATIONS = [
        "list_pipelines", "list_styles", "list_tools",
        "get_pipeline_info", "get_style_info", "get_tool_info",
        "check_environment", "render_demo", "list_demos",
        "get_architecture",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._source_available = OM_DIR.is_dir()
        self._env_check = self._check_environment()

    def _check_environment(self) -> dict[str, Any]:
        checks = {
            "source_cloned": self._source_available,
        }
        # Python deps
        for mod in ["yaml", "pydantic", "jsonschema", "dotenv", "PIL", "numpy", "requests"]:
            try:
                __import__(mod)
                checks[f"dep_{mod}"] = True
            except ImportError:
                checks[f"dep_{mod}"] = False

        # Node.js
        try:
            r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
            checks["node_version"] = r.stdout.strip() if r.returncode == 0 else None
            checks["node_ok"] = r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            checks["node_version"] = None
            checks["node_ok"] = False

        # Remotion
        remotion_dir = OM_DIR / "remotion-composer" / "node_modules"
        checks["remotion_installed"] = remotion_dir.is_dir()

        return checks

    def check_available(self) -> bool:
        return self._source_available

    def list_operations(self) -> list[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        start = time.time()
        try:
            if operation == "list_pipelines":
                result = self._list_pipelines()
            elif operation == "list_styles":
                result = self._list_styles()
            elif operation == "list_tools":
                result = self._list_tools()
            elif operation == "get_pipeline_info":
                result = self._get_pipeline_info(params)
            elif operation == "get_style_info":
                result = self._get_style_info(params)
            elif operation == "get_tool_info":
                result = self._get_tool_info(params)
            elif operation == "check_environment":
                result = self._env_check.copy()
            elif operation == "list_demos":
                result = self._list_demos()
            elif operation == "get_architecture":
                result = self._get_architecture()
            elif operation == "render_demo":
                result = self._render_demo(params)
            else:
                return {"status": "error", "error": f"Unknown operation: {operation}"}

            result["status"] = result.get("status", "success")
            result["duration_ms"] = (time.time() - start) * 1000
            return result
        except Exception as e:
            logger.error(f"[OpenMontage] {operation} failed: {e}")
            return {"status": "error", "operation": operation, "error": str(e), "duration_ms": (time.time() - start) * 1000}

    def _list_pipelines(self) -> dict:
        pipeline_dir = OM_DIR / "pipeline_defs"
        pipelines = []
        if pipeline_dir.is_dir():
            for f in sorted(pipeline_dir.glob("*.yaml")):
                pipelines.append({"name": f.stem, "file": f.name})
        return {"pipelines": pipelines, "count": len(pipelines)}

    def _list_styles(self) -> dict:
        style_dir = OM_DIR / "styles"
        styles = []
        if style_dir.is_dir():
            for f in sorted(style_dir.glob("*.yaml")):
                styles.append({"name": f.stem, "file": f.name})
        return {"styles": styles, "count": len(styles)}

    def _list_tools(self) -> dict:
        tools_dir = OM_DIR / "tools"
        categories = []
        if tools_dir.is_dir():
            for d in sorted(tools_dir.iterdir()):
                if d.is_dir() and not d.name.startswith("_") and not d.name.startswith("."):
                    py_files = list(d.glob("*.py"))
                    categories.append({
                        "name": d.name,
                        "tools": [f.stem for f in py_files if f.stem != "__init__" and f.stem != "base_tool"],
                        "count": len([f for f in py_files if f.stem != "__init__" and f.stem != "base_tool"]),
                    })
        return {"categories": categories, "total_categories": len(categories),
                "total_tools": sum(c["count"] for c in categories)}

    def _get_pipeline_info(self, params: dict) -> dict:
        name = params.get("name", "")
        pipeline_file = OM_DIR / "pipeline_defs" / f"{name}.yaml"
        if not pipeline_file.is_file():
            return {"status": "error", "error": f"Pipeline not found: {name}"}
        try:
            import yaml
            data = yaml.safe_load(pipeline_file.read_text(encoding="utf-8"))
            return {"name": name, "data": data}
        except Exception as e:
            return {"name": name, "raw_content": pipeline_file.read_text(encoding="utf-8")[:500]}

    def _get_style_info(self, params: dict) -> dict:
        name = params.get("name", "")
        style_file = OM_DIR / "styles" / f"{name}.yaml"
        if not style_file.is_file():
            return {"status": "error", "error": f"Style not found: {name}"}
        try:
            import yaml
            data = yaml.safe_load(style_file.read_text(encoding="utf-8"))
            return {"name": name, "data": data}
        except Exception:
            return {"name": name, "raw_content": style_file.read_text(encoding="utf-8")[:500]}

    def _get_tool_info(self, params: dict) -> dict:
        category = params.get("category", "")
        tool_name = params.get("tool", "")
        tool_file = OM_DIR / "tools" / category / f"{tool_name}.py"
        if not tool_file.is_file():
            return {"status": "error", "error": f"Tool not found: {category}/{tool_name}"}
        content = tool_file.read_text(encoding="utf-8")
        # Extract docstring
        lines = content.split("\n")
        doc_lines = []
        in_doc = False
        for line in lines[:30]:
            if '"""' in line and not in_doc:
                in_doc = True
                continue
            if '"""' in line and in_doc:
                break
            if in_doc:
                doc_lines.append(line.strip())
        return {"category": category, "tool": tool_name, "docstring": "\n".join(doc_lines), "size": len(content)}

    def _list_demos(self) -> dict:
        props_dir = OM_DIR / "remotion-composer" / "public" / "demo-props"
        demos = []
        if props_dir.is_dir():
            for f in sorted(props_dir.glob("*.json")):
                demos.append({"name": f.stem, "file": f.name})
        return {"demos": demos, "count": len(demos)}

    def _get_architecture(self) -> dict:
        arch = {
            "project": "OpenMontage",
            "description": "AI-driven video production pipeline engine",
            "components": {
                "pipeline_defs": "13 predefined video pipelines",
                "styles": "6 visual styles",
                "tools": "10+ tool categories (audio, video, subtitle, avatar, etc.)",
                "backlot": "Local storyboard server (FastAPI + uvicorn)",
                "remotion-composer": "React/Remotion rendering backend",
                "ink-theater": "Presentation layer",
                "schemas": "JSON schemas for pipeline validation",
            },
            "ai_backends": ["Google Gemini (Veo, Lyria)", "OpenAI (Sora 2)", "Kling"],
            "source_available": self._source_available,
        }
        if self._source_available:
            for comp in arch["components"]:
                comp_dir = OM_DIR / comp
                if comp_dir.is_dir():
                    py_count = len(list(comp_dir.rglob("*.py")))
                    arch["components"][comp] += f" ({py_count} py files)"
        return arch

    def _render_demo(self, params: dict) -> dict:
        demo_name = params.get("name", "")
        if not self._env_check.get("node_ok"):
            return {"status": "blocked", "blocker": "Node.js not available"}
        if not self._env_check.get("remotion_installed"):
            return {"status": "blocked", "blocker": "Remotion deps not installed (run npm install in remotion-composer/)"}
        return {"status": "info", "demo": demo_name, "note": "Use render_demo.py to render"}

    def summary(self) -> dict[str, Any]:
        return {
            "source_available": self._source_available,
            "pipelines": len(list((OM_DIR / "pipeline_defs").glob("*.yaml"))) if self._source_available else 0,
            "styles": len(list((OM_DIR / "styles").glob("*.yaml"))) if self._source_available else 0,
            "node_ok": self._env_check.get("node_ok", False),
            "remotion_installed": self._env_check.get("remotion_installed", False),
        }
