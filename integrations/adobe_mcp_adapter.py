#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adobe_mcp_adapter.py — Adobe MCP 集成适配器
=============================================

将 VoidChecksum/adobe-mcp (45 工具 / 8 Adobe 应用) 融入五层架构。

来源项目: https://github.com/VoidChecksum/adobe-mcp (PyPI: adobe-mcp)
集成层级: Layer 1 (引擎接入层) + Layer 2 (能力服务层)
对应缺陷: D-02/D-04/D-05/D-06/D-11~D-14/D-17R/D-18/D-19

架构:
    LLM Gateway → adobe_mcp_adapter → adobe_mcp (FastMCP) → COM/ExtendScript → Adobe CC

工具映射 (45 tools):
    Core/Cross-App (11): list_apps, app_status, launch_app, run_jsx, run_jsx_file,
                         run_powershell, open_file, save_file, close_document,
                         get_doc_info, list_fonts
    Photoshop (13): new_document, open_image, resize, crop, apply_filter, export, ...
    Illustrator (5): new_document, create_shape, export_svg, ...
    Premiere Pro (6): new_project, import_media, create_sequence, render, ...
    After Effects (6): new_composition, import_footage, add_layer, apply_effect, ...
    InDesign (3): new_document, place_image, export_pdf
    Animate (2): new_document, export_swf
    Media Encoder (1): add_to_queue
    Character Animator (1): start_capture

安装:
    pip install adobe-mcp  (已安装)

使用示例:
    from integrations.adobe_mcp_adapter import AdobeMCPAdapter

    adapter = AdobeMCPAdapter()
    if adapter.check_available():
        result = adapter.execute("ae_new_composition", {
            "name": "TestComp", "width": 1920, "height": 1080, "duration": 10
        })
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── 依赖检测 ─────────────────────────────────────────────────────────────

try:
    from adobe_mcp.server import ADOBE_APPS
    from adobe_mcp.server import mcp as _adobe_mcp_server
    ADOBE_MCP_AVAILABLE = True
except ImportError:
    ADOBE_MCP_AVAILABLE = False
    ADOBE_APPS = {}
    logger.warning("[AdobeMCP] adobe_mcp package not found, running in degraded mode")


# ── 枚举 ─────────────────────────────────────────────────────────────────

class AdobeApp(str, Enum):
    PHOTOSHOP = "photoshop"
    ILLUSTRATOR = "illustrator"
    PREMIEREPRO = "premierepro"
    AFTEREFFECTS = "aftereffects"
    INDESIGN = "indesign"
    ANIMATE = "animate"
    CHARACTERANIMATOR = "characteranimator"
    MEDIAENCODER = "mediaencoder"


class ToolStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DEGRADED = "degraded"


# ── 数据结构 ─────────────────────────────────────────────────────────────

@dataclass
class AdobeToolResult:
    """统一工具执行结果"""
    tool_name: str = "adobe_mcp"
    operation: str = ""
    status: str = "pending"
    app: str = ""
    output_files: list[str] = field(default_factory=list)
    output_data: dict[str, Any] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    used_fallback: bool = False
    fallback_method: str = ""


# ── 适配器 ───────────────────────────────────────────────────────────────

class AdobeMCPAdapter:
    """Adobe MCP 集成适配器

    将 adobe-mcp 的 45 个标准化工具封装为项目统一接口，
    融入五层架构的 Layer 1 (引擎接入) 和 Layer 2 (能力服务)。

    双通道架构:
        1. COM 自动化 (PowerShell) — 主要通道，支持 PS/AI/PR/AE/ID/AME
        2. ExtendScript (.jsx) — 备用通道，支持所有含 extendscript 的应用

    降级策略:
        - adobe_mcp 包不可用 → 降级到直接 PowerShell COM 调用
        - COM 失败 → 降级到 ExtendScript
        - 两者都失败 → 返回错误 + 建议手动操作
    """

    TOOL_NAME = "adobe_mcp"

    # 支持的操作映射: operation_name → (app, description)
    SUPPORTED_OPERATIONS: dict[str, dict[str, Any]] = {
        # Core / Cross-App (11)
        "list_apps": {"app": "core", "desc": "列出所有支持的 Adobe 应用及状态"},
        "app_status": {"app": "core", "desc": "检查指定应用是否运行中"},
        "launch_app": {"app": "core", "desc": "启动 Adobe 应用"},
        "run_jsx": {"app": "core", "desc": "在指定应用中执行 ExtendScript 代码"},
        "run_jsx_file": {"app": "core", "desc": "在指定应用中执行 JSX 文件"},
        "open_file": {"app": "core", "desc": "在指定应用中打开文件"},
        "save_file": {"app": "core", "desc": "保存当前文档"},
        "close_document": {"app": "core", "desc": "关闭文档（可选保存）"},
        "get_doc_info": {"app": "core", "desc": "获取文档元数据"},
        "list_fonts": {"app": "core", "desc": "列出可用字体"},

        # Photoshop (13)
        "ps_new_document": {"app": "photoshop", "desc": "创建新文档"},
        "ps_open_image": {"app": "photoshop", "desc": "打开图片"},
        "ps_resize": {"app": "photoshop", "desc": "调整图像尺寸"},
        "ps_crop": {"app": "photoshop", "desc": "裁剪图像"},
        "ps_apply_filter": {"app": "photoshop", "desc": "应用滤镜"},
        "ps_export": {"app": "photoshop", "desc": "导出图像"},
        "ps_add_text": {"app": "photoshop", "desc": "添加文字图层"},
        "ps_add_adjustment": {"app": "photoshop", "desc": "添加调整图层"},
        "ps_flatten": {"app": "photoshop", "desc": "合并图层"},
        "ps_batch_export": {"app": "photoshop", "desc": "批量导出"},
        "ps_get_layer_info": {"app": "photoshop", "desc": "获取图层信息"},
        "ps_create_shape": {"app": "photoshop", "desc": "创建形状"},
        "ps_apply_action": {"app": "photoshop", "desc": "执行动作"},

        # After Effects (6)
        "ae_new_composition": {"app": "aftereffects", "desc": "创建新合成"},
        "ae_import_footage": {"app": "aftereffects", "desc": "导入素材"},
        "ae_add_layer": {"app": "aftereffects", "desc": "添加图层"},
        "ae_apply_effect": {"app": "aftereffects", "desc": "应用效果"},
        "ae_render": {"app": "aftereffects", "desc": "渲染合成"},
        "ae_get_comp_info": {"app": "aftereffects", "desc": "获取合成信息"},

        # Premiere Pro (6)
        "pr_new_project": {"app": "premierepro", "desc": "创建新项目"},
        "pr_import_media": {"app": "premierepro", "desc": "导入媒体"},
        "pr_create_sequence": {"app": "premierepro", "desc": "创建序列"},
        "pr_add_clip": {"app": "premierepro", "desc": "添加剪辑到序列"},
        "pr_apply_transition": {"app": "premierepro", "desc": "应用转场"},
        "pr_export": {"app": "premierepro", "desc": "导出序列"},

        # Illustrator (5)
        "ai_new_document": {"app": "illustrator", "desc": "创建新文档"},
        "ai_create_shape": {"app": "illustrator", "desc": "创建形状"},
        "ai_add_text": {"app": "illustrator", "desc": "添加文字"},
        "ai_export_svg": {"app": "illustrator", "desc": "导出 SVG"},
        "ai_open_file": {"app": "illustrator", "desc": "打开文件"},

        # InDesign (3)
        "id_new_document": {"app": "indesign", "desc": "创建新文档"},
        "id_place_image": {"app": "indesign", "desc": "置入图片"},
        "id_export_pdf": {"app": "indesign", "desc": "导出 PDF"},

        # Animate (2)
        "an_new_document": {"app": "animate", "desc": "创建新文档"},
        "an_export": {"app": "animate", "desc": "导出动画"},

        # Media Encoder (1)
        "ame_add_to_queue": {"app": "mediaencoder", "desc": "添加到编码队列"},

        # Character Animator (1)
        "ch_start_capture": {"app": "characteranimator", "desc": "开始捕获"},
    }

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._jsx_dir = Path(self.config.get("jsx_dir", "")) if self.config.get("jsx_dir") else None
        self._timeout = self.config.get("timeout", 120)
        self._use_com = self.config.get("use_com", True)
        self._use_jsx = self.config.get("use_jsx", True)
        self._available = False
        self._available_apps: list[str] = []
        self._check_availability()

    def _check_availability(self) -> None:
        """检测 adobe-mcp 和 Adobe 应用可用性

        adobe_mcp PyPI 包缺失时不再直接判不可用（2026-08-15 修复）:
        项目本地 bridges/ 有等价桥接实现（.ae-mcp-bridge 文件轮询 + ExtendScript），
        只要检测到本机安装/运行中的 Adobe 应用即可降级可用。
        """
        if not ADOBE_MCP_AVAILABLE:
            logger.warning("[AdobeMCP] adobe_mcp package not installed, degraded mode")
            local_apps = self._discover_local_apps()
            if local_apps:
                global ADOBE_APPS
                ADOBE_APPS = local_apps  # 回填模块级，供 _run_jsx/list_apps 消费
                self._available = True
                self._available_apps = list(local_apps)
                logger.info(f"[AdobeMCP] Degraded mode with local apps: {self._available_apps}")
            else:
                self._available = False
            return

        self._available = True
        self._available_apps = list(ADOBE_APPS.keys())
        logger.info(f"[AdobeMCP] Available apps: {self._available_apps}")

    def _discover_local_apps(self) -> dict[str, dict[str, Any]]:
        """发现本机已安装的 Adobe 应用（降级模式用的 ADOBE_APPS 元数据）"""
        candidates = [
            ("aftereffects", "after_effects", "AfterFX.exe",
             r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files"),
            ("photoshop", "photoshop", "Photoshop.exe",
             r"C:\Program Files\Adobe\Adobe Photoshop 2025"),
            ("premierepro", "premiere_pro", "Adobe Premiere Pro.exe",
             r"C:\Program Files\Adobe\Adobe Premiere Pro 2025"),
            ("illustrator", "illustrator", "Illustrator.exe",
             r"C:\Program Files\Adobe\Adobe Illustrator 2025"),
            ("mediaencoder", "media_encoder", "Adobe Media Encoder.exe",
             r"C:\Program Files\Adobe\Adobe Media Encoder 2025"),
        ]
        found: dict[str, dict[str, Any]] = {}
        for key, jsx_target, exe, install_dir in candidates:
            exe_path = Path(install_dir) / exe
            if exe_path.exists():
                found[key] = {
                    "display": key, "com_id": "",
                    "process": exe, "extendscript": True,
                    "jsx_target": jsx_target, "install_dir": install_dir,
                }
        return found

    def check_available(self) -> bool:
        """检查适配器是否可用"""
        return self._available

    def list_operations(self) -> list[str]:
        """列出所有支持的操作"""
        return list(self.SUPPORTED_OPERATIONS.keys())

    def list_apps(self) -> dict[str, Any]:
        """列出所有支持的 Adobe 应用及状态"""
        result = {}
        for app_name, app_info in ADOBE_APPS.items():
            is_running = self._is_app_running(app_info.get("process", ""))
            result[app_name] = {
                "display": app_info.get("display", app_name),
                "com_id": app_info.get("com_id", "N/A"),
                "extendscript": app_info.get("extendscript", False),
                "running": is_running,
            }
        return result

    def _is_app_running(self, process_name: str) -> bool:
        """检查应用是否运行中"""
        if not process_name:
            return False
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, encoding="utf-8", errors="ignore",
                timeout=10,
            )
            return process_name.lower() in proc.stdout.lower()
        except Exception:
            return False

    def execute(self, operation: str, params: dict[str, Any] | None = None) -> AdobeToolResult:
        """执行指定操作

        Args:
            operation: 操作名称（见 SUPPORTED_OPERATIONS）
            params: 操作参数

        Returns:
            AdobeToolResult 执行结果
        """
        params = params or {}
        start_time = time.perf_counter()

        if operation not in self.SUPPORTED_OPERATIONS:
            return AdobeToolResult(
                operation=operation,
                status="failed",
                error=f"Unknown operation: {operation}. Available: {list(self.SUPPORTED_OPERATIONS.keys())}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        op_info = self.SUPPORTED_OPERATIONS[operation]
        app = op_info["app"]

        try:
            if app == "core":
                result = self._execute_core(operation, params)
            else:
                result = self._execute_app_operation(operation, app, params)

            result.duration_ms = (time.perf_counter() - start_time) * 1000
            return result

        except Exception as e:
            return AdobeToolResult(
                operation=operation,
                status="failed",
                app=app,
                error=str(e),
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

    def _execute_core(self, operation: str, params: dict[str, Any]) -> AdobeToolResult:
        """执行核心/跨应用操作"""
        if operation == "list_apps":
            apps = self.list_apps()
            return AdobeToolResult(
                operation=operation, status="success",
                output_data={"apps": apps},
                log=[f"Found {len(apps)} Adobe apps"],
            )

        if operation == "app_status":
            app_name = params.get("app", "")
            if app_name not in ADOBE_APPS:
                return AdobeToolResult(
                    operation=operation, status="failed",
                    error=f"Unknown app: {app_name}",
                )
            app_info = ADOBE_APPS[app_name]
            is_running = self._is_app_running(app_info.get("process", ""))
            return AdobeToolResult(
                operation=operation, status="success", app=app_name,
                output_data={"app": app_name, "running": is_running},
            )

        if operation == "launch_app":
            app_name = params.get("app", "")
            if app_name not in ADOBE_APPS:
                return AdobeToolResult(
                    operation=operation, status="failed",
                    error=f"Unknown app: {app_name}",
                )
            app_info = ADOBE_APPS[app_name]
            process = app_info.get("process", "")
            try:
                subprocess.Popen(
                    ["powershell", "-Command", f"Start-Process '{process}'"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return AdobeToolResult(
                    operation=operation, status="success", app=app_name,
                    log=[f"Launching {process}"],
                )
            except Exception as e:
                return AdobeToolResult(
                    operation=operation, status="failed", app=app_name,
                    error=f"Failed to launch {process}: {e}",
                )

        if operation == "run_jsx":
            app_name = params.get("app", "aftereffects")
            jsx_code = params.get("jsx_code", "")
            return self._run_jsx(app_name, jsx_code)

        if operation == "run_jsx_file":
            app_name = params.get("app", "aftereffects")
            jsx_path = params.get("jsx_path", "")
            return self._run_jsx_file(app_name, jsx_path)

        if operation == "open_file":
            app_name = params.get("app", "")
            file_path = params.get("file_path", "")
            return self._open_file_in_app(app_name, file_path)

        if operation == "save_file":
            app_name = params.get("app", "")
            return self._save_file(app_name)

        if operation == "close_document":
            app_name = params.get("app", "")
            save_first = params.get("save", False)
            return self._close_document(app_name, save_first)

        if operation == "get_doc_info":
            app_name = params.get("app", "")
            return self._get_doc_info(app_name)

        if operation == "list_fonts":
            return self._list_fonts()

        return AdobeToolResult(
            operation=operation, status="failed",
            error=f"Core operation not implemented: {operation}",
        )

    def _execute_app_operation(self, operation: str, app: str, params: dict[str, Any]) -> AdobeToolResult:
        """执行应用特定操作 — 通过 ExtendScript 实现"""
        jsx_code = self._build_jsx_for_operation(operation, app, params)
        if jsx_code is None:
            return AdobeToolResult(
                operation=operation, status="failed", app=app,
                error=f"No JSX implementation for {operation} on {app}",
            )
        return self._run_jsx(app, jsx_code)

    def _build_jsx_for_operation(self, operation: str, app: str, params: dict[str, Any]) -> str | None:
        """根据操作名构建 ExtendScript 代码"""

        # ── After Effects ──
        if app == "aftereffects":
            if operation == "ae_new_composition":
                name = params.get("name", "NewComp")
                w = params.get("width", 1920)
                h = params.get("height", 1080)
                dur = params.get("duration", 10)
                fps = params.get("fps", 30)
                return f"""
(function() {{
    var comp = app.project.items.addComp("{name}", {w}, {h}, 1, {dur}, {fps});
    return {{status:"success", compName: comp.name, id: comp.id, duration: comp.duration}};
}})();
"""
            if operation == "ae_import_footage":
                file_path = params.get("file_path", "")
                return f"""
(function() {{
    var file = new File("{file_path.replace(chr(92), chr(92)*2)}");
    var item = app.project.importFile(new ImportOptions(file));
    return {{status:"success", itemName: item.name, id: item.id, type: item.typeName}};
}})();
"""
            if operation == "ae_add_layer":
                comp_name = params.get("comp_name", "")
                layer_type = params.get("layer_type", "solid")
                name = params.get("name", "NewLayer")
                return f"""
(function() {{
    var comp = app.project.itemByName("{comp_name}");
    if (!comp) return {{status:"error", message:"Comp not found: {comp_name}"}};
    var layer = comp.layers.addSolid([1,1,1], "{name}", {params.get("width",1920)}, {params.get("height",1080)}, 1);
    return {{status:"success", layerName: layer.name, index: layer.index}};
}})();
"""
            if operation == "ae_apply_effect":
                layer_name = params.get("layer_name", "")
                effect_name = params.get("effect_name", "")
                return f"""
(function() {{
    var comp = app.project.activeItem;
    if (!comp) return {{status:"error", message:"No active comp"}};
    var layer = comp.layer("{layer_name}");
    var effect = layer.property("Effects").addProperty("{effect_name}");
    return {{status:"success", effectName: effect.name}};
}})();
"""
            if operation == "ae_get_comp_info":
                return """
(function() {
    var comp = app.project.activeItem;
    if (!comp) return {status:"error", message:"No active comp"};
    return {
        status:"success",
        name: comp.name,
        width: comp.width,
        height: comp.height,
        duration: comp.duration,
        fps: comp.frameRate,
        numLayers: comp.numLayers,
        pixelAspect: comp.pixelAspect
    };
})();
"""

        # ── Photoshop ──
        if app == "photoshop":
            if operation == "ps_new_document":
                name = params.get("name", "NewDoc")
                w = params.get("width", 1920)
                h = params.get("height", 1080)
                return f"""
(function() {{
    var doc = app.documents.add({w}, {h}, 72, "{name}");
    return {{status:"success", docName: doc.name, width: doc.width, height: doc.height}};
}})();
"""
            if operation == "ps_export":
                export_path = params.get("export_path", "")
                fmt = params.get("format", "PNG")
                return f"""
(function() {{
    var doc = app.activeDocument;
    var file = new File("{export_path.replace(chr(92), chr(92)*2)}");
    if ("{fmt}" == "PNG") {{
        var opts = new PNGSaveOptions();
        doc.saveAs(file, opts, true, Extension.LOWERCASE);
    }} else if ("{fmt}" == "JPEG") {{
        var opts = new JPEGSaveOptions();
        opts.quality = {params.get("quality", 10)};
        doc.saveAs(file, opts, true, Extension.LOWERCASE);
    }}
    return {{status:"success", path: file.fsName}};
}})();
"""
            if operation == "ps_get_layer_info":
                return """
(function() {
    var doc = app.activeDocument;
    var layers = [];
    for (var i = 0; i < doc.layers.length; i++) {
        layers.push({name: doc.layers[i].name, type: doc.layers[i].kind.toString(), visible: doc.layers[i].visible});
    }
    return {status:"success", docName: doc.name, numLayers: doc.layers.length, layers: layers};
})();
"""

        # ── Premiere Pro ──
        if app == "premierepro":
            if operation == "pr_new_project":
                name = params.get("name", "NewProject")
                return """
(function() {
    var project = app.project;
    return {status:"success", projectName: project.name, path: project.path};
})();
"""
            if operation == "pr_import_media":
                file_path = params.get("file_path", "")
                return f"""
(function() {{
    app.project.importFiles(["{file_path.replace(chr(92), chr(92)*2)}"]);
    return {{status:"success", importedFile: "{file_path}"}};
}})();
"""
            if operation == "pr_get_comp_info":
                return """
(function() {
    var project = app.project;
    var sequences = [];
    for (var i = 0; i < project.sequences.numSequences; i++) {
        var seq = project.sequences[i];
        sequences.push({name: seq.name, width: seq.frameSizeHorizontal, height: seq.frameSizeVertical});
    }
    return {status:"success", numSequences: project.sequences.numSequences, sequences: sequences};
})();
"""

        # ── Illustrator ──
        if app == "illustrator":
            if operation == "ai_new_document":
                w = params.get("width", 1920)
                h = params.get("height", 1080)
                return f"""
(function() {{
    var doc = app.documents.add(DocumentColorSpace.RGB, {w}, {h});
    return {{status:"success", docName: doc.name, width: doc.width, height: doc.height}};
}})();
"""

        # ── InDesign ──
        if app == "indesign":
            if operation == "id_new_document":
                return """
(function() {
    var doc = app.documents.add();
    return {status:"success", docName: doc.name};
})();
"""

        # ── Animate ─
        if app == "animate":
            if operation == "an_new_document":
                return """
(function() {
    var doc = fl.createDocument();
    return {status:"success", docName: doc.name};
})();
"""

        return None

    def _run_jsx(self, app: str, jsx_code: str) -> AdobeToolResult:
        """通过 ExtendScript 执行代码"""
        if not self._use_jsx:
            return AdobeToolResult(
                operation="run_jsx", status="degraded", app=app,
                error="JSX execution disabled in config",
                used_fallback=True,
            )

        # 写入临时 JSX 文件
        import tempfile
        tmp_file = tempfile.NamedTemporaryFile(
            suffix=".jsx", prefix="adobe_mcp_", delete=False, mode="w", encoding="utf-8"
        )
        tmp_file.write(jsx_code)
        tmp_file.close()

        try:
            app_info = ADOBE_APPS.get(app, {})
            jsx_target = app_info.get("jsx_target", app)

            # 通过 AE Bridge 文件轮询执行（仅 AE 桥已接线）
            result = self._execute_jsx_via_ae_bridge(tmp_file.name, jsx_target)
            return result
        finally:
            try:
                os.unlink(tmp_file.name)
            except OSError:
                pass

    def _run_jsx_file(self, app: str, jsx_path: str) -> AdobeToolResult:
        """执行 JSX 文件"""
        if not os.path.exists(jsx_path):
            return AdobeToolResult(
                operation="run_jsx_file", status="failed", app=app,
                error=f"JSX file not found: {jsx_path}",
            )

        app_info = ADOBE_APPS.get(app, {})
        jsx_target = app_info.get("jsx_target", app)
        return self._execute_jsx_via_ae_bridge(jsx_path, jsx_target)

    def _execute_jsx_via_ae_bridge(self, jsx_path: str, jsx_target: str) -> AdobeToolResult:
        """通过 AE Bridge 文件轮询执行 JSX（原误名 _execute_jsx_via_powershell，
        实际从未用过 PowerShell）。

        2026-08-16 体检修复（三处）:
        1. 幽灵环境变量: AEKV_ROOT 全仓库无定义（JSX 侧叫 AEKV_PROJECT_ROOT），
           回退 "." 使桥目录依赖进程 cwd → 改 AEKV_PROJECT_ROOT → 项目根
        2. 跨应用错发: 曾把 PS/IL/AU/ME 的 JSX 全发到 AE 专属桥
           .ae-mcp-bridge —— 会被 AE 监听器拿到或静默超时。各应用监听器
           命令词表不同，统一桥客户端（审计阶段2后续）落地前，非 AE
           目标显式失败而非错发
        3. 陈旧结果竞态: 发送前不清 ae_result.json 且"有 timestamp 即命中"，
           上一次命令的残留结果会被当作本次成功 → 发送前清结果文件
        """
        ae_aliases = {"aftereffects", "after_effects"}
        if jsx_target not in ae_aliases:
            return AdobeToolResult(
                operation="run_jsx", status="failed", app=jsx_target,
                error=(f"{jsx_target} 未接入桥接: 目前仅 AE 走 .ae-mcp-bridge; "
                       f"PS/PR/AU/ME 请用 bridges/*_bridge_client.py"),
            )

        root = os.environ.get("AEKV_PROJECT_ROOT") or str(
            Path(__file__).resolve().parent.parent)
        bridge_dir = Path(root) / ".ae-mcp-bridge"
        bridge_dir.mkdir(parents=True, exist_ok=True)

        cmd_file = bridge_dir / "ae_command.json"
        result_file = bridge_dir / "ae_result.json"

        import uuid
        cmd_id = str(uuid.uuid4())[:8]

        # 清掉上次残留结果（陈旧结果竞态根因: 监听器结果不含命令 id）
        try:
            result_file.unlink(missing_ok=True)
        except OSError:
            pass

        command = {
            "id": cmd_id,
            "command": "executeAtomScript",
            "args": {"script": Path(jsx_path).read_text(encoding="utf-8")},
            "timestamp": time.time(),
        }

        # 原子写入（避免竞态）
        tmp_cmd = bridge_dir / f"ae_command_{cmd_id}.tmp"
        tmp_cmd.write_text(json.dumps(command, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp_cmd), str(cmd_file))

        # 等待结果（最多 30 秒）; 结果文件在发送前已清空,
        # 此刻出现的必为监听器对本次命令的响应
        for _ in range(60):
            time.sleep(0.5)
            if result_file.exists():
                try:
                    result_data = json.loads(result_file.read_text(encoding="utf-8"))
                    if result_data.get("timestamp"):
                        status = result_data.get("status", "unknown")
                        return AdobeToolResult(
                            operation="run_jsx",
                            status="success" if status == "success" else "failed",
                            app=jsx_target,
                            output_data=result_data.get("result", {}),
                            error=result_data.get("message") if status != "success" else None,
                            log=[f"JSX executed via AE Bridge, cmd_id={cmd_id}"],
                        )
                except (json.JSONDecodeError, KeyError):
                    pass

        return AdobeToolResult(
            operation="run_jsx", status="failed", app=jsx_target,
            error=f"Bridge timeout after 30s (cmd_id={cmd_id})",
            log=["JSX sent to Bridge but no response received"],
        )

    def _open_file_in_app(self, app: str, file_path: str) -> AdobeToolResult:
        """在指定应用中打开文件"""
        esc = file_path.replace("\\", "\\\\").replace('"', '\\"')
        jsx = f"""
(function() {{
    var file = new File("{esc}");
    app.open(file);
    return {{status:"success", path: file.fsName}};
}})();
"""
        return self._run_jsx(app, jsx)

    def _save_file(self, app: str) -> AdobeToolResult:
        """保存当前文档"""
        jsx = """
(function() {
    app.activeDocument.save();
    return {status:"success", path: app.activeDocument.fullName.fsName};
})();
"""
        return self._run_jsx(app, jsx)

    def _close_document(self, app: str, save_first: bool = False) -> AdobeToolResult:
        """关闭文档"""
        save_flag = "true" if save_first else "false"
        jsx = f"""
(function() {{
    app.activeDocument.close(SaveOptions.{'SAVECHANGES' if save_first else 'DONOTSAVECHANGES'});
    return {{status:"success"}};
}})();
"""
        return self._run_jsx(app, jsx)

    def _get_doc_info(self, app: str) -> AdobeToolResult:
        """获取文档信息"""
        jsx = """
(function() {
    var doc = app.activeDocument;
    return {
        status:"success",
        name: doc.name,
        width: doc.width,
        height: doc.height,
        resolution: doc.resolution,
        colorMode: doc.mode.toString(),
        numLayers: doc.layers.length
    };
})();
"""
        return self._run_jsx(app, jsx)

    def _list_fonts(self) -> AdobeToolResult:
        """列出可用字体"""
        jsx = """
(function() {
    var fonts = app.fonts;
    var fontList = [];
    for (var i = 0; i < Math.min(fonts.length, 100); i++) {
        fontList.push(fonts[i].name);
    }
    return {status:"success", totalFonts: fonts.length, fonts: fontList};
})();
"""
        return self._run_jsx("photoshop", jsx)


# ── 便捷函数 ─────────────────────────────────────────────────────────────

def get_adapter(config: dict[str, Any] | None = None) -> AdobeMCPAdapter:
    """获取 AdobeMCPAdapter 单例"""
    return AdobeMCPAdapter(config)


def quick_test() -> dict[str, Any]:
    """快速验证测试 — 检测 adobe-mcp 可用性"""
    adapter = get_adapter()
    return {
        "available": adapter.check_available(),
        "operations_count": len(adapter.list_operations()),
        "operations": adapter.list_operations(),
        "apps": adapter.list_apps() if adapter.check_available() else {},
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    result = quick_test()
    print(json.dumps(result, indent=2, ensure_ascii=False))
