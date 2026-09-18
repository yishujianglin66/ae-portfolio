"""After Effects engine - aerender CLI + ExtendScript execution."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ...config import settings
from ..base import BaseEngine, EngineResult


class AEEngine(BaseEngine):
    """Adobe After Effects engine via aerender CLI."""

    name = "after_effects"

    def __init__(self, executable_path: Path | str | None = None):
        path = Path(executable_path) if executable_path else settings.aerender_path
        super().__init__(path)
        # AfterFX.exe — ExtendScript 执行入口（aerender 不支持运行脚本）
        self._afterfx_path: Path = path.parent / "AfterFX.exe"
        # MCP Bridge 目录 — AE 监听器通过 ae_command.json/ae_result.json 文件轮询通信
        self._bridge_dir: Path = settings.project_root / ".ae-mcp-bridge"

    async def render_comp(
        self,
        project_path: Path | str,
        comp_name: str,
        output_path: Path | str,
        output_module: str = "H.264",
        render_settings: str = "Best Settings",
        multiprocess: int | None = None,
        multi_machine: int | None = None,
    ) -> EngineResult:
        """Render AE composition via aerender CLI.

        Args:
            project_path: Path to the .aep project file
            comp_name: Composition name to render
            output_path: Output file path
            output_module: Output module template (H.264, Lossless, etc.)
            render_settings: Render settings template (Best Settings, etc.)
            multiprocess: 多进程渲染进程数（同一台机器上使用多个进程并行渲染）。
                对应 aerender 的 -mp 参数（multiprocess rendering）。
            multi_machine: 多机渲染标识（跨多台机器分布式渲染）。
                对应 aerender 的 -PdM 参数。注意：AE 的多机渲染通常通过
                Watch Folder 模式实现，-PdM 标志的可用性取决于 AE 版本，
                如不支持可改用 Watch Folder 工作流。
        """
        from ..base import validate_path_safety
        project_path = validate_path_safety(project_path, must_exist=True)
        output_path = validate_path_safety(output_path, must_exist=False)
        output_path = Path(output_path) if isinstance(output_path, str) else output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self.executable_path),
            "-project", str(project_path),
            "-comp", comp_name,
            "-output", str(output_path),
            "-OMtemplate", output_module,
            "-RStemplate", render_settings,
        ]
        # -mp：多进程渲染（单机多进程并行处理）
        if multiprocess:
            cmd.extend(["-mp", str(multiprocess)])
        # -PdM：多机渲染（跨机器分布式渲染，依赖 AE 版本支持）
        if multi_machine:
            cmd.extend(["-PdM", str(multi_machine)])

        code, stdout, stderr, err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )
        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            metadata={
                "comp_name": comp_name,
                "output_module": output_module,
                "render_settings": render_settings,
                "stdout": stdout[:2000],
            },
            error=stderr if code != 0 else None,
            error_code=err_code if code != 0 else None,
        )

    async def run_script(
        self,
        script_content: str,
        project_path: Path | str | None = None,
        timeout: float = 30.0,
    ) -> EngineResult:
        """Execute ExtendScript via MCP Bridge (primary) or AfterFX.exe (fallback).

        aerender.exe 不支持运行脚本（-s 是"起始帧"参数），因此脚本执行必须通过：
        1. MCP Bridge 文件轮询协议（主路径，需 AE 已启动且加载了 bridge listener）
        2. AfterFX.exe -r script.jsx（兜底，异步执行无法捕获返回值）

        Args:
            script_content: ExtendScript 代码（推荐用 IIFE 包装并 return JSON 字符串）
            project_path: 可选工程路径（bridge 忽略此参数；AfterFX 兜底时不使用）
            timeout: Bridge 轮询超时秒数（默认 30s）

        Returns:
            EngineResult: success 时 metadata.stdout 包含脚本返回值（通常为 JSON 字符串）
        """
        # 主路径: MCP Bridge（需 AE 运行 + listener 加载）
        success, stdout, error, err_code = await asyncio.to_thread(
            self._run_script_via_bridge, script_content, timeout
        )
        if success:
            return EngineResult(
                success=True,
                metadata={"stdout": stdout[:2000] if stdout else "", "method": "bridge"},
            )

        # 兜底: AfterFX.exe -r（异步，无法捕获返回值，仅判断启动是否成功）
        bridge_error = error or ""
        if self._afterfx_path.exists():
            import tempfile
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".jsx", delete=False, encoding="utf-8"
            ) as tf:
                tf.write(script_content)
                temp_script = tf.name
            try:
                cmd = [str(self._afterfx_path), "-r", temp_script]
                code, _stdout, stderr, ec = await asyncio.to_thread(
                    self._run_subprocess, cmd, timeout=60
                )
                if code == 0:
                    return EngineResult(
                        success=True,
                        metadata={
                            "stdout": "",
                            "method": "afterfx",
                            "note": "async via AfterFX.exe -r, no result capture",
                        },
                    )
                return EngineResult(
                    success=False,
                    error=f"AfterFX.exe failed: {stderr}",
                    error_code=ec or "AE_AFTERFX_FAILED",
                    metadata={"bridge_error": bridge_error},
                )
            finally:
                try:
                    Path(temp_script).unlink(missing_ok=True)
                except OSError:
                    pass

        return EngineResult(
            success=False,
            error=f"Bridge: {bridge_error}; AfterFX.exe not found at {self._afterfx_path}",
            error_code=err_code or "AE_SCRIPT_EXEC_FAILED",
        )

    def _run_script_via_bridge(
        self, script_content: str, timeout: float = 30.0
    ) -> tuple[bool, str, str | None, str | None]:
        """通过 MCP Bridge 文件轮询协议执行 ExtendScript。

        协议: 写入 ae_command.json → AE listener 轮询执行 → 写入 ae_result.json
        Bridge v4.1 handler: runScript，参数 args.code = 脚本内容，返回 String(eval(code))。

        健壮性改进：
        1. 发送命令前清理旧结果文件，避免读到上次的结果
        2. 优先检查结果文件存在性（比 processed 标志更可靠）
        3. 同时检查 processed 标志作为兜底

        Returns: (success, stdout, error_message, error_code)
        """
        import time as _time

        if not self._bridge_dir.exists():
            return False, "", f"Bridge directory not found: {self._bridge_dir}", "AE_BRIDGE_DIR_MISSING"

        cmd_path = self._bridge_dir / "ae_command.json"
        res_path = self._bridge_dir / "ae_result.json"

        # 清理旧结果文件，避免读到上次的残留结果
        try:
            if res_path.exists():
                res_path.unlink()
        except OSError:
            pass

        # 高精度时间戳，用于唯一标识本次命令
        ts = _time.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(_time.time() * 1000) % 1000:03d}"

        cmd_data = {
            "command": "runScript",
            "args": {"code": script_content},
            "timestamp": ts,
            "processed": False,
        }

        # 写入命令文件
        try:
            cmd_path.write_text(
                json.dumps(cmd_data, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as e:
            return False, "", f"Failed to write ae_command.json: {e}", "AE_BRIDGE_WRITE_FAILED"

        # 轮询等待结果: 优先检查结果文件存在性（更可靠），兜底检查 processed 标志
        # 注意：可能有其他进程（MCP 服务器）同时发送命令，需要通过 command 字段匹配
        deadline = _time.time() + timeout
        expected_cmd = "runScript"
        while _time.time() < deadline:
            _time.sleep(0.3)
            # 优先检查结果文件（结果文件只在命令处理完后才被写入）
            if res_path.exists():
                try:
                    res_text = res_path.read_text(encoding="utf-8")
                    if res_text and len(res_text) > 2:
                        res_data = json.loads(res_text)
                        # 检查结果是否对应我们的命令（过滤其他进程的命令结果）
                        res_cmd = res_data.get("command", "")
                        if res_cmd != expected_cmd:
                            # 结果是其他命令的（如 executeAtomScript），删除并继续轮询
                            try:
                                res_path.unlink()
                            except OSError:
                                pass
                            continue
                        status = res_data.get("status")
                        result_obj = res_data.get("result", {})
                        if status == "success" and isinstance(result_obj, dict) and result_obj.get("success"):
                            data = result_obj.get("data", {})
                            return True, str(data.get("result", "")), None, None
                        else:
                            err_msg = "Bridge script error"
                            if isinstance(result_obj, dict):
                                err_info = result_obj.get("error", {})
                                err_msg = err_info.get("message", err_msg) if isinstance(err_info, dict) else str(err_info)
                            elif isinstance(result_obj, str):
                                err_msg = result_obj
                            return False, "", err_msg, "AE_SCRIPT_ERROR"
                except (json.JSONDecodeError, OSError):
                    # 结果文件可能正在写入中，继续轮询
                    continue
            # 兜底：检查 processed 标志
            try:
                current_cmd = json.loads(cmd_path.read_text(encoding="utf-8"))
                if current_cmd.get("processed"):
                    # 命令已处理但结果文件可能还没出现，稍等再检查
                    if not res_path.exists():
                        _time.sleep(0.2)
                        if not res_path.exists():
                            return False, "", "Command processed but ae_result.json missing", "AE_BRIDGE_NO_RESULT"
                    # 结果文件已存在，循环顶部会处理
            except (json.JSONDecodeError, OSError):
                continue

        return False, "", (
            f"Bridge timeout ({timeout}s) — AE may not be running or bridge listener not loaded. "
            f"Check: AE process running? z_mcp_bridge_startup.jsx in Scripts/Startup/?"
        ), "AE_BRIDGE_TIMEOUT"

    # ==================== 高层操作 API ====================

    async def create_project(
        self,
        project_path: Path | str,
        comp_name: str = "Main Comp",
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
        duration: float = 5.0,
    ) -> EngineResult:
        """创建新的 AE 工程（.aep）并保存到指定路径。

        关闭当前工程（不保存）→ newProject() → addComp() → save()。

        Args:
            project_path: .aep 文件保存路径
            comp_name: 初始合成名称
            width: 合成宽度（像素）
            height: 合成高度（像素）
            fps: 帧率
            duration: 时长（秒）

        Returns:
            EngineResult: 成功时 metadata 包含 projectPath / compName，output_path 为 .aep 路径
        """
        project_path = Path(project_path)
        # 路径安全校验（与 render_comp 基线一致，防止任意路径写入）
        from ..base import validate_path_safety
        project_path = validate_path_safety(project_path, must_exist=False)
        project_path.parent.mkdir(parents=True, exist_ok=True)
        ae_path = project_path.as_posix()

        script = f'''
(function() {{
    try {{
        if (app.project && app.project.file) {{
            app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
        }}
        var proj = app.newProject();
        if (!proj) return JSON.stringify({{error: true, message: "newProject() returned null"}});
        var comp = proj.items.addComp("{comp_name}", {width}, {height}, 1, {duration}, {fps});
        var f = new File("{ae_path}");
        proj.save(f);
        return JSON.stringify({{
            success: true,
            projectPath: f.fsName,
            compName: comp.name,
            width: comp.width,
            height: comp.height,
            duration: comp.duration,
            fps: comp.frameRate
        }});
    }} catch(e) {{
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "创建工程失败")
                    result.error_code = "AE_CREATE_PROJECT_FAILED"
                else:
                    result.metadata.update(data)
                    result.output_path = project_path
            except Exception as _e:
                logger.error(f"[AE] JSON parse failed at create_project: {_e}")
                result.success = False
                result.error = f"JSON parse error: {_e}"
                result.error_code = "AE_JSON_PARSE_ERROR"
        return result

    async def create_comp(
        self,
        name: str,
        width: int,
        height: int,
        fps: float,
        duration: float,
        project_path: Path | str | None = None,
    ) -> EngineResult:
        """创建合成。

        Args:
            name: 合成名称
            width: 宽度（像素）
            height: 高度（像素）
            fps: 帧率
            duration: 时长（秒）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 成功时 metadata 包含 compName
        """
        script = f'''
(function() {{
    var comp = app.project.items.addComp("{name}", {width}, {height}, 1, {duration}, {fps});
    return JSON.stringify({{
        success: true,
        compName: comp.name,
        width: comp.width,
        height: comp.height,
        duration: comp.duration,
        fps: comp.frameRate
    }});
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                result.metadata.update(data)
            except Exception as _e:
                logger.error(f"[AE] JSON parse failed at create_comp: {_e}")
                result.success = False
                if result.error is None:
                    result.error = f"Partial failure: {type(_e).__name__}: {_e}"
                if "partial_failures" not in result.metadata:
                    result.metadata["partial_failures"] = []
                result.metadata["partial_failures"].append(f"{type(_e).__name__}: {str(_e)[:200]}")
                if not result.error_code:
                    result.error_code = "AE_PARTIAL_FAILURE"
        return result

    async def import_footage(
        self,
        footage_path: Path | str,
        comp_name: str | None = None,
        as_sequence: bool = False,
        position: int | None = None,
        project_path: Path | str | None = None,
    ) -> EngineResult:
        """导入素材到项目，可选添加到合成。

        Args:
            footage_path: 素材文件路径
            comp_name: 目标合成名称（可选）
            as_sequence: 是否作为序列导入
            position: 在合成中的图层位置（1-based，可选）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 成功时 metadata 包含 footageName, layerIndex
        """
        footage_path = Path(footage_path)
        # 素材为读取操作且可位于任意素材库（D:/AE-Work 等），
        # 仅要求绝对路径 + 存在性检查；写入路径才需 validate_path_safety。
        if not footage_path.is_absolute():
            return EngineResult(
                success=False,
                error=f"素材路径必须是绝对路径: {footage_path}",
            )
        if not footage_path.exists():
            return EngineResult(
                success=False,
                error=f"素材文件不存在: {footage_path}",
            )

        # 构建 JSON 参数（复用 MCP importFootage.jsx 逻辑）
        args = {
            "filePath": str(footage_path),
            "asSequence": as_sequence,
        }
        if comp_name:
            args["compName"] = comp_name
        if position is not None:
            args["position"] = position

        args_json = json.dumps(args, ensure_ascii=False)
        script = f'''
(function() {{
    var args = {args_json};
    try {{
        var file = new File(args.filePath);
        if (!file.exists) {{
            return JSON.stringify({{error: true, message: "文件不存在: " + args.filePath}});
        }}

        app.beginUndoGroup("Import Footage");
        var importOptions = new ImportOptions(file);
        importOptions.sequence = args.asSequence || false;
        var footage = app.project.importFile(importOptions);

        var result = {{
            success: true,
            footageName: footage.name,
            filePath: args.filePath
        }};

        if (args.compName) {{
            var comp = null;
            for (var i = 1; i <= app.project.numItems; i++) {{
                var item = app.project.item(i);
                if (item instanceof CompItem && item.name === args.compName) {{
                    comp = item;
                    break;
                }}
            }}
            if (comp) {{
                var addedLayer = comp.layers.add(footage);
                if (args.position && args.position > 0 && args.position <= comp.numLayers) {{
                    addedLayer.moveAfter(comp.layer(args.position));
                }}
                result.compName = args.compName;
                result.layerIndex = addedLayer.index;
            }}
        }}

        app.endUndoGroup();
        return JSON.stringify(result);
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "导入失败")
                else:
                    result.metadata.update(data)
            except Exception as _e:
                logger.error(f"[AE] JSON parse/params apply failed at import_footage: {_e}")
                result.success = False
                if result.error is None:
                    result.error = f"Partial failure: {type(_e).__name__}: {_e}"
                if "partial_failures" not in result.metadata:
                    result.metadata["partial_failures"] = []
                result.metadata["partial_failures"].append(f"{type(_e).__name__}: {str(_e)[:200]}")
                if not result.error_code:
                    result.error_code = "AE_PARTIAL_FAILURE"
        return result

    async def add_layer(
        self,
        comp_name: str,
        layer_type: str,
        name: str,
        position: int | None = None,
        project_path: Path | str | None = None,
        **kwargs: Any,
    ) -> EngineResult:
        """在合成中添加图层。

        Args:
            comp_name: 合成名称
            layer_type: 图层类型（solid, null, adjustment, text, shape）
            name: 图层名称
            position: 插入位置（1-based，可选）
            project_path: 项目路径（可选）
            **kwargs: 其他参数（如 color, width, height 等）

        Returns:
            EngineResult: 成功时 metadata 包含 layerIndex
        """
        layer_type = layer_type.lower()
        args = {
            "compName": comp_name,
            "layerType": layer_type,
            "name": name,
            "position": position,
            **kwargs,
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到: " + args.compName}});
        }}

        app.beginUndoGroup("Add Layer");

        var layer = null;
        var layerType = args.layerType.toLowerCase();

        if (layerType === "solid") {{
            var color = args.color || [1, 1, 1];
            var width = args.width || comp.width;
            var height = args.height || comp.height;
            layer = comp.layers.addSolid(color, args.name, width, height, 1, comp.duration);
        }} else if (layerType === "null") {{
            layer = comp.layers.addNull(comp.duration);
            layer.name = args.name;
        }} else if (layerType === "adjustment") {{
            layer = comp.layers.addSolid([0, 0, 0], args.name, comp.width, comp.height, 1, comp.duration);
            layer.adjustmentLayer = true;
        }} else if (layerType === "text") {{
            layer = comp.layers.addText(args.name);
        }} else if (layerType === "shape") {{
            layer = comp.layers.addShape();
            layer.name = args.name;
        }} else {{
            app.endUndoGroup();
            return JSON.stringify({{error: true, message: "不支持的图层类型: " + layerType}});
        }}

        // 设置图层顺序（遵循 project_memory：moveToBeginning + moveAfter）
        if (args.position !== null && args.position !== undefined) {{
            var pos = parseInt(args.position);
            if (pos > 0 && pos <= comp.numLayers) {{
                layer.moveAfter(comp.layer(pos));
            }} else if (pos <= 0) {{
                layer.moveToBeginning();
            }}
        }}

        app.endUndoGroup();
        return JSON.stringify({{
            success: true,
            layerIndex: layer.index,
            layerName: layer.name,
            layerType: layerType
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "添加图层失败")
                else:
                    result.metadata.update(data)
            except Exception as _e:
                logger.error(f"[AE] JSON parse/params apply failed at add_layer: {_e}")
                result.success = False
                if result.error is None:
                    result.error = f"Partial failure: {type(_e).__name__}: {_e}"
                if "partial_failures" not in result.metadata:
                    result.metadata["partial_failures"] = []
                result.metadata["partial_failures"].append(f"{type(_e).__name__}: {str(_e)[:200]}")
                if not result.error_code:
                    result.error_code = "AE_PARTIAL_FAILURE"
        return result

    async def add_effect(
        self,
        comp_name: str,
        layer_index: int,
        effect_name: str,
        params: dict[str, Any] | None = None,
        project_path: Path | str | None = None,
    ) -> EngineResult:
        """为图层添加效果。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            effect_name: 效果匹配名（如 "ADBE Gaussian Blur"）
            params: 效果参数字典（可选）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 成功时 metadata 包含 effectIndex, effectName
        """
        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "effectMatchName": effect_name,
            "settings": params or {},
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
            return JSON.stringify({{error: true, message: "图层索引无效"}});
        }}

        app.beginUndoGroup("Add Effect");

        var layer = comp.layer(args.layerIndex);
        var effect = layer.Effects.addProperty(args.effectMatchName);

        // 应用参数
        var appliedKeys = [];
        var failedKeys = [];
        if (args.settings) {{
            for (var key in args.settings) {{
                try {{
                    var prop = effect.property(key);
                    if (prop && prop.canSetValue) {{
                        prop.setValue(args.settings[key]);
                        appliedKeys.push(key);
                    }}
                }} catch (e) {{
                    if (!failedKeys) failedKeys = [];
                    failedKeys.push(key + ': ' + e.toString().slice(0, 100));
                }}
            }}
        }}

        app.endUndoGroup();
        return JSON.stringify({{
            success: true,
            effectIndex: effect.propertyIndex,
            effectName: effect.name,
            appliedKeys: appliedKeys,
            failedKeys: failedKeys
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "添加效果失败")
                else:
                    result.metadata.update(data)
            except Exception as _e:
                logger.error(f"[AE] JSON parse/params apply failed at add_effect: {_e}")
                result.success = False
                if result.error is None:
                    result.error = f"Partial failure: {type(_e).__name__}: {_e}"
                if "partial_failures" not in result.metadata:
                    result.metadata["partial_failures"] = []
                result.metadata["partial_failures"].append(f"{type(_e).__name__}: {str(_e)[:200]}")
                if not result.error_code:
                    result.error_code = "AE_PARTIAL_FAILURE"
        return result

    async def set_keyframes(
        self,
        comp_name: str,
        layer_index: int,
        property_path: str,
        keyframes: list[dict[str, Any]],
        project_path: Path | str | None = None,
    ) -> EngineResult:
        """设置属性关键帧。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            property_path: 属性路径（如 "Transform/Position" 或 "Effects(1)/Blur"）
            keyframes: 关键帧列表，每项包含 time, value, easingType
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 成功时 metadata 包含 keyframesAdded
        """
        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "propertyPath": property_path,
            "keyframes": keyframes,
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
            return JSON.stringify({{error: true, message: "图层索引无效"}});
        }}

        app.beginUndoGroup("Set Keyframes");

        var layer = comp.layer(args.layerIndex);
        var prop = null;

        // 解析属性路径（简化版：仅支持 Transform/Prop 和 Effects(index)/Prop）
        var pathParts = args.propertyPath.split("/");
        if (pathParts[0] === "Transform") {{
            prop = layer.property(pathParts[1]);
        }} else if (pathParts[0].startsWith("Effects")) {{
            var match = pathParts[0].match(/Effects\\((\\d+)\\)/);
            if (match) {{
                var effectIndex = parseInt(match[1]);
                prop = layer.effect(effectIndex).property(pathParts[1]);
            }}
        }}

        if (!prop || !prop.canSetValue) {{
            app.endUndoGroup();
            return JSON.stringify({{error: true, message: "属性无效或不可设置"}});
        }}

        var keyframesAdded = 0;
        var kfFailedKeys = [];
        for (var k = 0; k < args.keyframes.length; k++) {{
            var kf = args.keyframes[k];
            try {{
                prop.setValueAtTime(kf.time, kf.value);

                // 缓动设置
                if (kf.easingType && kf.easingType !== "linear") {{
                    var kfIndex = prop.nearestKeyIndex(kf.time);
                    var inType = KeyframeInterpolationType.BEZIER;
                    var outType = KeyframeInterpolationType.BEZIER;
                    if (kf.easingType === "hold") {{
                        inType = KeyframeInterpolationType.HOLD;
                        outType = KeyframeInterpolationType.HOLD;
                    }} else if (kf.easingType === "easeIn") {{
                        outType = KeyframeInterpolationType.LINEAR;
                    }} else if (kf.easingType === "easeOut") {{
                        inType = KeyframeInterpolationType.LINEAR;
                    }}
                    prop.setInterpolationTypeAtKey(kfIndex, inType, outType);
                }}
                keyframesAdded++;
            }} catch (e) {{
                if (!kfFailedKeys) kfFailedKeys = [];
                kfFailedKeys.push('kf[' + k + '] time=' + kf.time + ': ' + e.toString().slice(0, 100));
            }}
        }}

        app.endUndoGroup();
        return JSON.stringify({{
            success: true,
            keyframesAdded: keyframesAdded,
            failedKeyframes: kfFailedKeys
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "设置关键帧失败")
                else:
                    result.metadata.update(data)
            except Exception as _e:
                logger.error(f"[AE] JSON parse/params apply failed at set_keyframes: {_e}")
                result.success = False
                if result.error is None:
                    result.error = f"Partial failure: {type(_e).__name__}: {_e}"
                if "partial_failures" not in result.metadata:
                    result.metadata["partial_failures"] = []
                result.metadata["partial_failures"].append(f"{type(_e).__name__}: {str(_e)[:200]}")
                if not result.error_code:
                    result.error_code = "AE_PARTIAL_FAILURE"
        return result

    async def apply_preset(
        self,
        comp_name: str,
        layer_index: int,
        preset_path: Path | str,
        project_path: Path | str | None = None,
    ) -> EngineResult:
        """应用效果预设。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            preset_path: 预设文件路径（.ffx）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 操作结果
        """
        preset_path = Path(preset_path)
        if not preset_path.exists():
            return EngineResult(
                success=False,
                error=f"预设文件不存在: {preset_path}",
            )

        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "presetPath": str(preset_path),
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
            return JSON.stringify({{error: true, message: "图层索引无效"}});
        }}

        app.beginUndoGroup("Apply Preset");

        var layer = comp.layer(args.layerIndex);
        var presetFile = new File(args.presetPath);
        if (!presetFile.exists) {{
            app.endUndoGroup();
            return JSON.stringify({{error: true, message: "预设文件不存在"}});
        }}

        layer.applyPreset(presetFile);

        app.endUndoGroup();
        return JSON.stringify({{success: true}});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "应用预设失败")
            except Exception as _e:
                logger.error(f"[AE] JSON parse/params apply failed at apply_preset: {_e}")
                result.success = False
                if result.error is None:
                    result.error = f"Partial failure: {type(_e).__name__}: {_e}"
                if "partial_failures" not in result.metadata:
                    result.metadata["partial_failures"] = []
                result.metadata["partial_failures"].append(f"{type(_e).__name__}: {str(_e)[:200]}")
                if not result.error_code:
                    result.error_code = "AE_PARTIAL_FAILURE"
        return result

    async def set_blend_mode(
        self,
        comp_name: str,
        layer_index: int,
        mode: str,
        project_path: Path | str | None = None,
    ) -> EngineResult:
        """设置图层混合模式。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            mode: 混合模式（NONE, SCREEN, MULTIPLY, ADD, OVERLAY 等）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 操作结果
        """
        mode = mode.upper()
        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "blendMode": mode,
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
            return JSON.stringify({{error: true, message: "图层索引无效"}});
        }}

        var blendModeMap = {{
            "NONE": BlendingMode.NONE,
            "DISSOLVE": BlendingMode.DISSOLVE,
            "MULTIPLY": BlendingMode.MULTIPLY,
            "SCREEN": BlendingMode.SCREEN,
            "OVERLAY": BlendingMode.OVERLAY,
            "SOFT_LIGHT": BlendingMode.SOFT_LIGHT,
            "HARD_LIGHT": BlendingMode.HARD_LIGHT,
            "ADD": BlendingMode.ADD,
            "COLOR_DODGE": BlendingMode.COLOR_DODGE,
            "COLOR_BURN": BlendingMode.COLOR_BURN,
            "DARKEN": BlendingMode.DARKEN,
            "LIGHTEN": BlendingMode.LIGHTEN,
            "DIFFERENCE": BlendingMode.DIFFERENCE,
            "EXCLUSION": BlendingMode.EXCLUSION,
            "HUE": BlendingMode.HUE,
            "SATURATION": BlendingMode.SATURATION,
            "COLOR": BlendingMode.COLOR,
            "LUMINOSITY": BlendingMode.LUMINOSITY
        }};

        if (!blendModeMap.hasOwnProperty(args.blendMode)) {{
            return JSON.stringify({{error: true, message: "不支持的混合模式: " + args.blendMode}});
        }}

        app.beginUndoGroup("Set Blend Mode");
        var layer = comp.layer(args.layerIndex);
        layer.blendingMode = blendModeMap[args.blendMode];
        app.endUndoGroup();

        return JSON.stringify({{success: true, blendMode: args.blendMode}});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "设置混合模式失败")
                else:
                    result.metadata.update(data)
            except Exception as _e:
                logger.error(f"[AE] JSON parse/params apply failed at set_blend_mode: {_e}")
                result.success = False
                if result.error is None:
                    result.error = f"Partial failure: {type(_e).__name__}: {_e}"
                if "partial_failures" not in result.metadata:
                    result.metadata["partial_failures"] = []
                result.metadata["partial_failures"].append(f"{type(_e).__name__}: {str(_e)[:200]}")
                if not result.error_code:
                    result.error_code = "AE_PARTIAL_FAILURE"
        return result

    async def set_track_matte(
        self,
        comp_name: str,
        layer_index: int,
        matte_type: str,
        project_path: Path | str | None = None,
    ) -> EngineResult:
        """设置轨道遮罩类型。

        Args:
            comp_name: 合成名称
            layer_index: 图层索引（1-based）
            matte_type: 遮罩类型（NO_TRACK_MATTE, ALPHA_TRACK_MATTE, LUMA_TRACK_MATTE 等）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 操作结果
        """
        matte_type = matte_type.upper()
        args = {
            "compName": comp_name,
            "layerIndex": layer_index,
            "matteType": matte_type,
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {{
            return JSON.stringify({{error: true, message: "图层索引无效"}});
        }}

        var matteMap = {{
            "NO_TRACK_MATTE": TrackMatteType.NO_TRACK_MATTE,
            "ALPHA_TRACK_MATTE": TrackMatteType.ALPHA_TRACK_MATTE,
            "ALPHA_INVERTED_TRACK_MATTE": TrackMatteType.ALPHA_INVERTED_TRACK_MATTE,
            "LUMA_TRACK_MATTE": TrackMatteType.LUMA_TRACK_MATTE,
            "LUMA_INVERTED_TRACK_MATTE": TrackMatteType.LUMA_INVERTED_TRACK_MATTE
        }};

        if (!matteMap.hasOwnProperty(args.matteType)) {{
            return JSON.stringify({{error: true, message: "不支持的轨道遮罩类型: " + args.matteType}});
        }}

        app.beginUndoGroup("Set Track Matte");
        var layer = comp.layer(args.layerIndex);
        layer.trackMatteType = matteMap[args.matteType];
        app.endUndoGroup();

        return JSON.stringify({{success: true, matteType: args.matteType}});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "设置轨道遮罩失败")
                else:
                    result.metadata.update(data)
            except Exception as _e:
                logger.error(f"[AE] JSON parse/params apply failed at set_track_matte: {_e}")
                result.success = False
                if result.error is None:
                    result.error = f"Partial failure: {type(_e).__name__}: {_e}"
                if "partial_failures" not in result.metadata:
                    result.metadata["partial_failures"] = []
                result.metadata["partial_failures"].append(f"{type(_e).__name__}: {str(_e)[:200]}")
                if not result.error_code:
                    result.error_code = "AE_PARTIAL_FAILURE"
        return result

    async def add_adjustment_layer(
        self,
        comp_name: str,
        name: str,
        effects: list[dict[str, Any]] | None = None,
        position: int | None = None,
        project_path: Path | str | None = None,
    ) -> EngineResult:
        """添加调整图层。

        Args:
            comp_name: 合成名称
            name: 图层名称
            effects: 效果列表，每项包含 effectName, params
            position: 插入位置（1-based，可选）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 成功时 metadata 包含 layerIndex, effectsAdded
        """
        args = {
            "compName": comp_name,
            "name": name,
            "effects": effects or [],
            "position": position,
        }
        args_json = json.dumps(args, ensure_ascii=False)

        script = f'''
(function() {{
    var args = {args_json};
    try {{
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}

        app.beginUndoGroup("Add Adjustment Layer");

        // 创建调整图层（黑色固态层）
        var adjLayer = comp.layers.addSolid([0, 0, 0], args.name, comp.width, comp.height, 1, comp.duration);
        adjLayer.adjustmentLayer = true;

        // 设置图层顺序（遵守 project_memory：moveToBeginning + moveAfter）
        if (args.position !== null && args.position !== undefined) {{
            var pos = parseInt(args.position);
            if (pos > 0 && pos <= comp.numLayers) {{
                adjLayer.moveAfter(comp.layer(pos));
            }} else if (pos <= 0) {{
                adjLayer.moveToBeginning();
            }}
        }}

        // 添加效果
        var effectsAdded = 0;
        var effectFailedKeys = [];
        if (args.effects && args.effects.length > 0) {{
            for (var e = 0; e < args.effects.length; e++) {{
                try {{
                    var effectInfo = args.effects[e];
                    var effect = adjLayer.Effects.addProperty(effectInfo.effectName);
                    if (effectInfo.params) {{
                        for (var key in effectInfo.params) {{
                            try {{
                                var prop = effect.property(key);
                                if (prop && prop.canSetValue) {{
                                    prop.setValue(effectInfo.params[key]);
                                }}
                            }} catch (err) {{
                                if (!effectFailedKeys) effectFailedKeys = [];
                                effectFailedKeys.push('effect[' + e + '].param.' + key + ': ' + err.toString().slice(0, 100));
                            }}
                        }}
                    }}
                    effectsAdded++;
                }} catch (ex) {{
                    if (!effectFailedKeys) effectFailedKeys = [];
                    effectFailedKeys.push('effect[' + e + '] add: ' + ex.toString().slice(0, 100));
                }}
            }}
        }}

        app.endUndoGroup();
        return JSON.stringify({{
            success: true,
            layerIndex: adjLayer.index,
            effectsAdded: effectsAdded,
            effectFailedKeys: effectFailedKeys
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "添加调整图层失败")
                else:
                    result.metadata.update(data)
            except Exception as _e:
                logger.error(f"[AE] JSON parse/params apply failed at add_adjustment_layer: {_e}")
                result.success = False
                if result.error is None:
                    result.error = f"Partial failure: {type(_e).__name__}: {_e}"
                if "partial_failures" not in result.metadata:
                    result.metadata["partial_failures"] = []
                result.metadata["partial_failures"].append(f"{type(_e).__name__}: {str(_e)[:200]}")
                if not result.error_code:
                    result.error_code = "AE_PARTIAL_FAILURE"
        return result

    async def render_segment(
        self,
        comp_name: str,
        start_frame: int,
        end_frame: int,
        output_path: Path | str,
        project_path: Path | str,
        output_module: str = "H.264",
        render_settings: str = "Best Settings",
    ) -> EngineResult:
        """渲染合成片段。

        Args:
            comp_name: 合成名称
            start_frame: 起始帧
            end_frame: 结束帧
            output_path: 输出文件路径
            project_path: 项目路径
            output_module: 输出模块模板
            render_settings: 渲染设置模板

        Returns:
            EngineResult: 渲染结果
        """
        output_path = Path(output_path)
        project_path = Path(project_path)
        # 路径安全校验（与 render_comp 基线一致，防止任意路径读写）
        from ..base import validate_path_safety
        project_path = validate_path_safety(project_path, must_exist=True)
        output_path = validate_path_safety(output_path, must_exist=False)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用 aerender 的 -s 和 -e 参数指定帧范围
        cmd = [
            str(self.executable_path),
            "-project", str(project_path),
            "-comp", comp_name,
            "-s", str(start_frame),
            "-e", str(end_frame),
            "-output", str(output_path),
            "-OMtemplate", output_module,
            "-RStemplate", render_settings,
        ]

        code, stdout, stderr, err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )

        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            metadata={
                "comp_name": comp_name,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "output_module": output_module,
                "stdout": stdout[:2000],
            },
            error=stderr if code != 0 else None,
            error_code=err_code if code != 0 else None,
        )

    async def import_subtitles(
        self,
        comp_name: str,
        subtitle_path: Path | str,
        project_path: Path | str | None = None,
        font_family: str = "Arial",
        font_size: int = 48,
        font_color: list[float] | None = None,
        stroke_color: list[float] | None = None,
        stroke_width: float = 2.0,
        glow_enabled: bool = True,
        glow_color: list[float] | None = None,
        glow_radius: float = 15.0,
        position_y: float = 0.85,
    ) -> EngineResult:
        """导入字幕文件到 AE 合成。

        Args:
            comp_name: 目标合成名称
            subtitle_path: 字幕文件路径（SRT/VTT/ASS）
            project_path: 项目路径（可选）
            font_family: 字体名称
            font_size: 字体大小
            font_color: 字体颜色 [r, g, b]
            stroke_color: 描边颜色 [r, g, b]
            stroke_width: 描边宽度
            glow_enabled: 是否启用发光效果
            glow_color: 发光颜色 [r, g, b]
            glow_radius: 发光半径
            position_y: 垂直位置比例（0=顶部, 1=底部）

        Returns:
            EngineResult: 导入结果
        """
        subtitle_path = Path(subtitle_path)
        if not subtitle_path.exists():
            return EngineResult(
                success=False,
                error=f"字幕文件不存在: {subtitle_path}",
            )

        font_color = font_color or [1.0, 1.0, 1.0]
        stroke_color = stroke_color or [0.0, 0.0, 0.0]
        glow_color = glow_color or [0.0, 0.5, 1.0]

        import json
        style = {
            "font_family": font_family,
            "font_size": font_size,
            "font_color": font_color,
            "stroke_color": stroke_color,
            "stroke_width": stroke_width,
            "glow_enabled": glow_enabled,
            "glow_color": glow_color,
            "glow_radius": glow_radius,
            "position_y": position_y,
        }

        script = f'''
(function() {{
    var style = {json.dumps(style, ensure_ascii=False)};
    var subtitlePath = "{subtitle_path.as_posix()}";
    
    function parseSRT(content) {{
        var items = [];
        var pattern = /(\\d+)\\s*\\n(\\d{{2}}:\\d{{2}}:\\d{{2}},\\d{{3}})\\s*-->\\s*(\\d{{2}}:\\d{{2}}:\\d{{2}},\\d{{3}})\\s*\\n((?:.*\\s*)*?)\\s*\\n/g;
        var match;
        while ((match = pattern.exec(content)) !== null) {{
            items.push({{
                index: parseInt(match[1]),
                start_time: parseTimecode(match[2]),
                end_time: parseTimecode(match[3]),
                text: match[4].replace(/\\n/g, " ").trim()
            }});
        }}
        return items;
    }}
    
    function parseTimecode(timecode) {{
        var parts = timecode.replace(",", ".").split(":");
        if (parts.length === 3) {{
            return parseFloat(parts[0]) * 3600 + parseFloat(parts[1]) * 60 + parseFloat(parts[2]);
        }}
        return parseFloat(parts[0]) * 60 + parseFloat(parts[1]);
    }}
    
    try {{
        var file = new File(subtitlePath);
        if (!file.exists) {{
            return JSON.stringify({{error: true, message: "字幕文件不存在"}});
        }}
        file.encoding = "UTF-8";
        file.open("r");
        var content = file.read();
        file.close();
        
        var subtitles = parseSRT(content);
        
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === "{comp_name}") {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}
        
        app.beginUndoGroup("Import Subtitles");
        
        var importedCount = 0;
        for (var j = 0; j < subtitles.length; j++) {{
            var sub = subtitles[j];
            var textLayer = comp.layers.addText(sub.text);
            textLayer.name = "Subtitle_" + sub.index;
            textLayer.inPoint = sub.start_time;
            textLayer.outPoint = sub.end_time;
            
            var sourceText = textLayer.property("Source Text");
            var textDoc = sourceText.value;
            textDoc.fontSize = style.font_size;
            textDoc.fontFamily = style.font_family;
            textDoc.fillColor = new RGBColor();
            textDoc.fillColor.red = style.font_color[0];
            textDoc.fillColor.green = style.font_color[1];
            textDoc.fillColor.blue = style.font_color[2];
            sourceText.setValue(textDoc);
            
            var position = textLayer.property("Position");
            var posVal = position.value;
            posVal[0] = comp.width * 0.5;
            posVal[1] = comp.height * style.position_y;
            position.setValue(posVal);
            
            textLayer.property("Anchor Point").setValue([comp.width * 0.5, comp.height * 0.1]);
            
            if (style.stroke_width > 0) {{
                var stroke = textLayer.Effects.addProperty("ADBE Stroke");
                stroke.property("ADBE Stroke-0001").setValue(new RGBColor());
                stroke.property("ADBE Stroke-0001").value.red = style.stroke_color[0];
                stroke.property("ADBE Stroke-0001").value.green = style.stroke_color[1];
                stroke.property("ADBE Stroke-0001").value.blue = style.stroke_color[2];
                stroke.property("ADBE Stroke-0002").setValue(style.stroke_width);
            }}
            
            if (style.glow_enabled) {{
                var glow = textLayer.Effects.addProperty("ADBE Glow");
                glow.property("ADBE Glow-0001").setValue(new RGBColor());
                glow.property("ADBE Glow-0001").value.red = style.glow_color[0];
                glow.property("ADBE Glow-0001").value.green = style.glow_color[1];
                glow.property("ADBE Glow-0001").value.blue = style.glow_color[2];
                glow.property("ADBE Glow-0002").setValue(style.glow_radius);
                glow.property("ADBE Glow-0003").setValue(1.0);
            }}
            
            importedCount++;
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            importedCount: importedCount,
            totalSubtitles: subtitles.length,
            format: "srt"
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "导入字幕失败")
                else:
                    result.metadata.update(data)
            except Exception as _e:
                logger.error(f"[AE] JSON parse/params apply failed at import_subtitles: {_e}")
                result.success = False
                if result.error is None:
                    result.error = f"Partial failure: {type(_e).__name__}: {_e}"
                if "partial_failures" not in result.metadata:
                    result.metadata["partial_failures"] = []
                result.metadata["partial_failures"].append(f"{type(_e).__name__}: {str(_e)[:200]}")
                if not result.error_code:
                    result.error_code = "AE_PARTIAL_FAILURE"
        return result

    async def export_subtitles(
        self,
        comp_name: str,
        output_path: Path | str,
        format_type: str = "srt",
        project_path: Path | str | None = None,
    ) -> EngineResult:
        """从 AE 合成导出字幕。

        Args:
            comp_name: 合成名称
            output_path: 输出文件路径
            format_type: 输出格式（srt, vtt, ass）
            project_path: 项目路径（可选）

        Returns:
            EngineResult: 导出结果
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        script = f'''
(function() {{
    try {{
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === "{comp_name}") {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到"}});
        }}
        
        var subtitles = [];
        var index = 1;
        
        for (var j = 1; j <= comp.numLayers; j++) {{
            var layer = comp.layer(j);
            if (layer instanceof TextLayer) {{
                var text = "";
                try {{
                    text = layer.property("Source Text").value.getText();
                }} catch (e) {{
                    text = layer.name.replace("Subtitle_", "");
                }}
                
                subtitles.push({{
                    index: index,
                    start_time: layer.inPoint,
                    end_time: layer.outPoint,
                    text: text
                }});
                index++;
            }}
        }}
        
        subtitles.sort(function(a, b) {{ return a.start_time - b.start_time; }});
        
        return JSON.stringify({{
            success: true,
            subtitles: subtitles,
            count: subtitles.length
        }});
    }} catch (e) {{
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        result = await self.run_script(script, project_path)
        if result.success and result.metadata:
            try:
                data = json.loads(result.metadata.get("stdout", "{}"))
                if data.get("error"):
                    result.success = False
                    result.error = data.get("message", "导出字幕失败")
                else:
                    from ae.subtitle_system import SubtitleGenerator, SubtitleItem
                    
                    items = [SubtitleItem(**s) for s in data["subtitles"]]
                    if format_type == "srt":
                        content = SubtitleGenerator.to_srt(items)
                    elif format_type == "vtt":
                        content = SubtitleGenerator.to_vtt(items)
                    elif format_type == "ass":
                        content = SubtitleGenerator.to_ass(items)
                    else:
                        content = SubtitleGenerator.to_srt(items)
                    
                    output_path.write_text(content, encoding='utf-8')
                    result.output_path = output_path
                    result.metadata.update({
                        "output_path": str(output_path),
                        "format": format_type,
                        "count": data["count"],
                    })
            except Exception as e:
                result.error = str(e)
                result.success = False
        return result

    async def generate_subtitles_from_audio(
        self,
        audio_path: Path | str,
        language: str = "zh",
        use_llm: bool = True,
    ) -> EngineResult:
        """从音频生成字幕（使用 Whisper + LLM 优化）。

        Args:
            audio_path: 音频文件路径
            language: 语言代码（zh, en, ja 等）
            use_llm: 是否使用 LLM 优化字幕

        Returns:
            EngineResult: 生成结果，metadata 包含字幕列表
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            return EngineResult(
                success=False,
                error=f"音频文件不存在: {audio_path}",
            )

        try:
            import whisper

            from ae.subtitle_system import SubtitleGenerator, SubtitleSystem
            
            subtitle_system = SubtitleSystem()
            subtitles = await subtitle_system.generate_subtitles_from_audio(
                audio_path, language, use_llm
            )
            
            srt_content = SubtitleGenerator.to_srt(subtitles)
            srt_path = audio_path.parent / f"{audio_path.stem}.srt"
            srt_path.write_text(srt_content, encoding='utf-8')
            
            return EngineResult(
                success=True,
                output_path=srt_path,
                metadata={
                    "subtitle_count": len(subtitles),
                    "language": language,
                    "use_llm": use_llm,
                    "srt_path": str(srt_path),
                },
            )
        except ImportError:
            return EngineResult(
                success=False,
                error="需要安装 whisper 库: pip install openai-whisper",
            )
        except Exception as e:
            return EngineResult(
                success=False,
                error=f"生成字幕失败: {str(e)}",
            )

    async def _execute_impl(self, **kwargs) -> EngineResult:
        action = kwargs.pop("action", "render_comp")
        handler = {
            "render_comp": self.render_comp,
            "run_script": self.run_script,
            # 高层操作 API
            "create_project": self.create_project,
            "create_comp": self.create_comp,
            "import_footage": self.import_footage,
            "add_layer": self.add_layer,
            "add_effect": self.add_effect,
            "set_keyframes": self.set_keyframes,
            "apply_preset": self.apply_preset,
            "set_blend_mode": self.set_blend_mode,
            "set_track_matte": self.set_track_matte,
            "add_adjustment_layer": self.add_adjustment_layer,
            "render_segment": self.render_segment,
            # 字幕相关 API
            "import_subtitles": self.import_subtitles,
            "export_subtitles": self.export_subtitles,
            "generate_subtitles_from_audio": self.generate_subtitles_from_audio,
            # 旗舰管线 API
            "bridge_smoke_probe": self.bridge_smoke_probe,
            "render_comp_bridge": self.render_comp_bridge,
        }.get(action)
        if handler is None:
            return EngineResult(success=False, error=f"Unknown action: {action}")
        return await handler(**kwargs)

    # ======================================================================
    #  旗舰管线专用 API (Flagship E2E Pipeline)
    # ======================================================================

    async def bridge_smoke_probe(self, **kwargs) -> EngineResult:
        """旗舰管线 S3 前置探测：验证 AE Bridge 真实可用。

        执行序列：
        1. ping (app.version)
        2. 创建测试合成
        3. 删除测试合成
        4. 返回 available=True/False

        任何步骤失败则返回 success=False + error_code=BRIDGE_DOWN。
        """
        probe_comp_name = f"_FlagshipProbe_{int(time.time())}"

        # Step 1: ping
        ping_result = await self.run_script(
            "JSON.stringify({pong:true, ver:app.version})",
            timeout=10.0,
        )
        if not ping_result.success:
            return EngineResult(
                success=False,
                error=f"Bridge ping 失败: {ping_result.error}",
                error_code="BRIDGE_DOWN",
                available=False,
            )

        # Step 2: 创建测试合成
        create_jsx = (
            f'var comp = app.project.items.addComp('
            f'"{probe_comp_name}", 1920, 1080, 1, 3, 24);'
            f'JSON.stringify({{created: comp.name}});'
        )
        create_result = await self.run_script(create_jsx, timeout=15.0)
        if not create_result.success:
            return EngineResult(
                success=False,
                error=f"Bridge 创建测试合成失败: {create_result.error}",
                error_code="BRIDGE_DOWN",
                available=False,
            )

        # Step 3: 删除测试合成
        delete_jsx = (
            f'var items = app.project.items;'
            f'for (var i = items.length; i >= 1; i--) {{'
            f'  if (items[i].name == "{probe_comp_name}") {{ items[i].remove(); break; }}'
            f'}}'
            f'"cleaned";'
        )
        await self.run_script(delete_jsx, timeout=10.0)

        return EngineResult(
            success=True,
            metadata={
                "bridge_available": True,
                "ae_version": ping_result.metadata.get("stdout", ""),
                "probe_comp": probe_comp_name,
            },
            available=True,
        )

    async def render_comp_bridge(
        self,
        comp_name: str,
        output_path: Path | str,
        duration_s: float = 3.0,
        width: int = 1920,
        height: int = 1080,
        fps: int = 24,
        source_video: Path | str | None = None,
        preset_path: Path | str | None = None,
        **kwargs,
    ) -> EngineResult:
        """通过 Bridge 创建合成并渲染为 .mov（旗舰管线 S3 专用）。

        流程：
        1. 创建合成 (comp_name, width×height, duration_s, fps)
        2. 可选：导入源视频并添加到时间线
        3. 可选：应用预设
        4. 通过 aerender 渲染为 .mov

        Args:
            comp_name: 合成名称
            output_path: 输出 .mov 路径
            duration_s: 合成时长（秒）
            width/height/fps: 合成规格
            source_video: 可选源视频路径
            preset_path: 可选 AE 预设路径 (.ffx)

        Returns:
            EngineResult
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Step 1: 创建合成
        create_jsx = (
            f'var comp = app.project.items.addComp('
            f'"{comp_name}", {width}, {height}, 1, {duration_s}, {fps});'
        )

        # Step 2: 导入源视频
        if source_video:
            src = str(Path(source_video)).replace("\\", "/")
            create_jsx += (
                f'var file = new File("{src}");'
                f'if (file.exists) {{'
                f'  var io = new ImportOptions(file);'
                f'  var footage = app.project.importFile(io);'
                f'  comp.layers.add(footage);'
                f'}}'
            )

        # Step 3: 应用预设
        if preset_path:
            preset = str(Path(preset_path)).replace("\\", "/")
            create_jsx += (
                f'var presetFile = new File("{preset}");'
                f'if (presetFile.exists && comp.layer(1)) {{'
                f'  comp.layer(1).applyPreset(presetFile);'
                f'}}'
            )

        create_jsx += f'JSON.stringify({{comp: "{comp_name}", created: true}});'

        create_result = await self.run_script(create_jsx, timeout=30.0)
        if not create_result.success:
            return EngineResult(
                success=False,
                error=f"创建合成失败: {create_result.error}",
                error_code="SCRIPT_SYNTAX",
            )

        # Step 4: 保存工程并通过 aerender 渲染
        # 先保存工程到临时路径
        aep_path = output_path.parent / f"{comp_name}.aep"
        save_jsx = (
            f'app.project.save(new File("{str(aep_path).replace(chr(92), "/")}"));'
            f'"saved";'
        )
        await self.run_script(save_jsx, timeout=20.0)

        # 通过 aerender CLI 渲染
        if aep_path.exists():
            render_result = await self.render_comp(
                project_path=aep_path,
                comp_name=comp_name,
                output_path=output_path,
                output_module="Lossless",
            )
            if render_result.success and output_path.exists():
                return EngineResult(
                    success=True,
                    output_path=output_path,
                    metadata={
                        "comp_name": comp_name,
                        "duration_s": duration_s,
                        "aep_path": str(aep_path),
                    },
                )
            # aerender 失败，返回错误
            return EngineResult(
                success=False,
                error=f"aerender 渲染失败: {render_result.error}",
                error_code="OUTPUT_CORRUPT",
            )

        return EngineResult(
            success=False,
            error="工程保存失败，无法渲染",
            error_code="SCRIPT_SYNTAX",
        )
