"""ComfyUI workflow manager.

Manages workflow templates:
- Built-in puppet style workflows
- Save / load / list user workflows
- Workflow parameter substitution (input image, style params)
- Execute workflow via ComfyUIEngine
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from src.engines.base import EngineResult
from src.engines.comfyui import ComfyUIEngine


@dataclass
class WorkflowInfo:
    """Metadata about a workflow."""
    name: str
    display_name: str
    description: str = ""
    category: str = "general"
    style: str | None = None  # e.g. "wooden", "stop_motion"
    file_path: Path | None = None
    builtin: bool = False


class WorkflowManager:
    """Manages ComfyUI workflow templates.

    Workflows are stored as JSON files with ComfyUI prompt format:
    {
      "1": { "class_type": "LoadImage", "inputs": { ... } },
      "2": { ... },
      ...
    }
    """

    def __init__(
        self,
        engine: ComfyUIEngine | None = None,
        workflows_dir: Path | None = None,
    ) -> None:
        self.engine = engine
        self.workflows_dir = Path(workflows_dir) if workflows_dir else Path("data/comfyui_workflows")
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self._builtin_cache: dict[str, dict[str, Any]] = {}

    # ============================================================
    # Workflow discovery
    # ============================================================

    def list_workflows(self, category: str | None = None) -> list[WorkflowInfo]:
        """List all available workflows (builtin + user)."""
        workflows: dict[str, WorkflowInfo] = {}

        # Built-in
        for name, wf in BUILTIN_WORKFLOWS.items():
            info = WorkflowInfo(
                name=name,
                display_name=wf.get("display_name", name),
                description=wf.get("description", ""),
                category=wf.get("category", "puppet"),
                style=wf.get("style"),
                builtin=True,
            )
            workflows[name] = info

        # User workflows from directory
        if self.workflows_dir.exists():
            for json_file in self.workflows_dir.glob("**/*.json"):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    # Support both raw workflow and wrapped with metadata
                    if "workflow" in data:
                        meta = data.get("metadata", {})
                        name = meta.get("name", json_file.stem)
                        info = WorkflowInfo(
                            name=name,
                            display_name=meta.get("display_name", name),
                            description=meta.get("description", ""),
                            category=meta.get("category", "user"),
                            style=meta.get("style"),
                            file_path=json_file,
                            builtin=False,
                        )
                    else:
                        info = WorkflowInfo(
                            name=json_file.stem,
                            display_name=json_file.stem,
                            category="user",
                            file_path=json_file,
                            builtin=False,
                        )
                    workflows[info.name] = info
                except Exception as e:
                    logger.warning(f"[WorkflowManager] Failed to read {json_file}: {e}")

        result = list(workflows.values())
        if category:
            result = [w for w in result if w.category == category]
        return sorted(result, key=lambda w: (not w.builtin, w.name))

    def get_workflow(self, name: str) -> dict[str, Any] | None:
        """Load a workflow by name. Returns raw ComfyUI prompt dict."""
        # Check built-in first
        if name in BUILTIN_WORKFLOWS:
            return self._get_builtin(name)

        # Check user workflows
        info = self._find_user_workflow(name)
        if info and info.file_path and info.file_path.exists():
            try:
                data = json.loads(info.file_path.read_text(encoding="utf-8"))
                return data.get("workflow", data)
            except Exception as e:
                logger.warning(f"[WorkflowManager] Failed to load {name}: {e}")

        return None

    def _find_user_workflow(self, name: str) -> WorkflowInfo | None:
        """Find a user workflow by name."""
        for w in self.list_workflows():
            if w.name == name and not w.builtin:
                return w
        return None

    def _get_builtin(self, name: str) -> dict[str, Any] | None:
        """Get a built-in workflow by name (with caching)."""
        if name in self._builtin_cache:
            return self._builtin_cache[name]

        if name not in BUILTIN_WORKFLOWS:
            return None

        builder = BUILTIN_WORKFLOWS[name].get("builder")
        if builder:
            wf = builder()
        else:
            wf = BUILTIN_WORKFLOWS[name].get("workflow", {})

        self._builtin_cache[name] = wf
        return wf

    # ============================================================
    # Workflow management
    # ============================================================

    def save_workflow(
        self,
        name: str,
        workflow: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        overwrite: bool = True,
    ) -> Path:
        """Save a user workflow to disk."""
        safe_name = Path(name).name
        file_path = self.workflows_dir / f"{safe_name}.json"
        if file_path.exists() and not overwrite:
            raise FileExistsError(f"Workflow '{name}' already exists")

        save_data = {
            "metadata": {
                "name": name,
                "display_name": (metadata or {}).get("display_name", name),
                "description": (metadata or {}).get("description", ""),
                "category": (metadata or {}).get("category", "user"),
                "style": (metadata or {}).get("style"),
            },
            "workflow": workflow,
        }
        file_path.write_text(json.dumps(save_data, indent=2), encoding="utf-8")
        logger.info(f"[WorkflowManager] Saved workflow: {name} -> {file_path}")
        return file_path

    def delete_workflow(self, name: str) -> bool:
        """Delete a user workflow. Returns True if deleted."""
        info = self._find_user_workflow(name)
        if info and info.file_path and info.file_path.exists():
            info.file_path.unlink()
            logger.info(f"[WorkflowManager] Deleted workflow: {name}")
            return True
        return False

    # ============================================================
    # Workflow execution
    # ============================================================

    async def execute_workflow(
        self,
        workflow_name: str,
        params: dict[str, Any] | None = None,
        output_dir: Path | None = None,
    ) -> EngineResult:
        """Execute a named workflow with optional parameter substitution.

        Args:
            workflow_name: Name of the workflow to run
            params: Dict of {node_id: {param: value}} to inject
            output_dir: Where to save output files

        Returns:
            EngineResult with outputs
        """
        if not self.engine:
            return EngineResult(success=False, error="No ComfyUI engine configured")

        workflow = self.get_workflow(workflow_name)
        if not workflow:
            return EngineResult(success=False, error=f"Workflow '{workflow_name}' not found")

        # Apply parameter substitutions
        if params:
            import copy
            workflow = copy.deepcopy(workflow)
            for node_id, node_params in params.items():
                if node_id in workflow:
                    existing = workflow[node_id].get("inputs", {})
                    existing.update(node_params)
                    workflow[node_id]["inputs"] = existing

        return await self.engine.run_workflow(workflow, output_dir)

    async def execute_raw(
        self,
        workflow: dict[str, Any],
        output_dir: Path | None = None,
    ) -> EngineResult:
        """Execute a raw workflow dict."""
        if not self.engine:
            return EngineResult(success=False, error="No ComfyUI engine configured")
        return await self.engine.run_workflow(workflow, output_dir)


# ============================================================
# Built-in workflows (programmatically generated)
# ============================================================

def _build_simple_image_pass() -> dict[str, Any]:
    """Simple load -> save passthrough workflow."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "input.png"},
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "ComfyUI"},
        },
    }


def _build_wooden_puppet_style() -> dict[str, Any]:
    """Wooden puppet style workflow (stylization + texture overlay).

    Note: This is a template that requires a LoadImage node and a
    VAE + model for actual generation. In real use, user provides
    a complete workflow with model checkpoints configured.
    """
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "input.png"},
        },
        "2": {
            "class_type": "ImageToImage",
            "inputs": {"pixels": ["1", 0], "strength": 0.65},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "wooden_puppet"},
        },
    }


def _build_stop_motion_style() -> dict[str, Any]:
    """Stop motion / claymation style workflow template."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "input.png"},
        },
        "2": {
            "class_type": "ImageToImage",
            "inputs": {"pixels": ["1", 0], "strength": 0.7},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "stop_motion"},
        },
    }


def _build_miniature_style() -> dict[str, Any]:
    """Miniature / tilt-shift diorama style workflow template."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "input.png"},
        },
        "2": {
            "class_type": "ImageToImage",
            "inputs": {"pixels": ["1", 0], "strength": 0.6},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "miniature"},
        },
    }


def _build_clay_style() -> dict[str, Any]:
    """Claymation / plasticine style workflow template."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "input.png"},
        },
        "2": {
            "class_type": "ImageToImage",
            "inputs": {"pixels": ["1", 0], "strength": 0.65},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "clay"},
        },
    }


def _build_shadow_style() -> dict[str, Any]:
    """Shadow puppet / silhouette style workflow template."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "input.png"},
        },
        "2": {
            "class_type": "ImageToImage",
            "inputs": {"pixels": ["1", 0], "strength": 0.8},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "shadow"},
        },
    }


def _build_paper_style() -> dict[str, Any]:
    """Paper cutout / papercraft style workflow template."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "input.png"},
        },
        "2": {
            "class_type": "ImageToImage",
            "inputs": {"pixels": ["1", 0], "strength": 0.65},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "paper"},
        },
    }


def _build_voxel_style() -> dict[str, Any]:
    """Voxel / Minecraft style workflow template."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "input.png"},
        },
        "2": {
            "class_type": "ImageToImage",
            "inputs": {"pixels": ["1", 0], "strength": 0.75},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "voxel"},
        },
    }


def _build_handle_style() -> dict[str, Any]:
    """Marionette / string puppet style workflow template."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "input.png"},
        },
        "2": {
            "class_type": "ImageToImage",
            "inputs": {"pixels": ["1", 0], "strength": 0.6},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "handle"},
        },
    }


BUILTIN_WORKFLOWS: dict[str, dict[str, Any]] = {
    "simple_passthrough": {
        "display_name": "Simple Pass-through",
        "description": "Basic load image -> save image workflow for testing",
        "category": "utility",
        "builder": _build_simple_image_pass,
    },
    "wooden_puppet": {
        "display_name": "Wooden Puppet Style",
        "description": "Wooden marionette style with grain texture and articulated joints",
        "category": "puppet",
        "style": "wooden",
        "builder": _build_wooden_puppet_style,
    },
    "stop_motion_puppet": {
        "display_name": "Stop Motion Style",
        "description": "Claymation stop-motion aesthetic with low framerate feel",
        "category": "puppet",
        "style": "stop_motion",
        "builder": _build_stop_motion_style,
    },
    "miniature_puppet": {
        "display_name": "Miniature / Diorama Style",
        "description": "Tilt-shift miniature model diorama style",
        "category": "puppet",
        "style": "miniature",
        "builder": _build_miniature_style,
    },
    "clay_puppet": {
        "display_name": "Claymation Style",
        "description": "Plasticine claymation soft form style",
        "category": "puppet",
        "style": "clay",
        "builder": _build_clay_style,
    },
    "shadow_puppet": {
        "display_name": "Shadow Puppet Style",
        "description": "Silhouette shadow play with backlit lighting",
        "category": "puppet",
        "style": "shadow",
        "builder": _build_shadow_style,
    },
    "paper_puppet": {
        "display_name": "Paper Cutout Style",
        "description": "Papercraft layered cutout animation style",
        "category": "puppet",
        "style": "paper",
        "builder": _build_paper_style,
    },
    "voxel_puppet": {
        "display_name": "Voxel Style",
        "description": "Blocky voxel / Minecraft aesthetic",
        "category": "puppet",
        "style": "voxel",
        "builder": _build_voxel_style,
    },
    "handle_puppet": {
        "display_name": "Marionette Style",
        "description": "Classic string-controlled marionette puppet style",
        "category": "puppet",
        "style": "handle",
        "builder": _build_handle_style,
    },
}
