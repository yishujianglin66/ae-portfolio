"""
pipeline/stages/execution.py - 执行阶段 v2.0
=============================================
AE自动化执行：通过 UnifiedAEClient → puppet/MCP双通道 → AE Bridge 执行剪辑操作

命令链路：
  Python → UnifiedAEClient → puppet通道(aerender) / MCP通道(Bridge+JSX)
                           → 自动降级 + 统计追踪

v2.0 变更：
  - 接入 ae.unified_ae_client.UnifiedAEClient（替代已弃用的 AECommandClient）
  - 支持 puppet + MCP 双通道自动降级
  - 修复 executeAtomScript 不支持问题
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Bridge 支持的 JSX 命令（对应 ae_additive_scripts/*.jsx，原 ae-mcp-server 已归档）
_BRIDGE_COMMANDS = {
    "create_comp": "createComposition",
    "import_footage": "importFootage",
    "add_effect_kf": "addEffectWithKeyframes",
    "add_text": "addTextLayer",
    "add_shape": "addShapeLayer",
    "add_adjustment": "addAdjustmentLayer",
    "batch_effects": "batchAddEffects",
    "set_blend": "setBlendMode",
    "set_matte": "setTrackMatte",
    "list_comps": "listCompositions",
    "analyze": "analyzeProject",
}


class ExecutionStage:
    """执行阶段：通过 AE Bridge 执行剪辑操作"""

    # Bridge 使用单文件轮询协议（ae_command.json / ae_result.json），
    # 并发调用会互相覆盖，需全局串行化
    _bridge_lock = threading.Lock()

    def __init__(self, config):
        self.config = config
        self._client = None
        self._ae_ready = False

    def _ensure_ae_ready(self) -> bool:
        """确保 AE 已启动且 Bridge 已连通，必要时自动启动"""
        if self._ae_ready:
            return True

        # 1. 检查 AE 是否已运行
        try:
            try:
                from ae.ae_process_manager import AEProcessManager
            except ImportError:
                from ae_process_manager import AEProcessManager
            mgr = AEProcessManager()

            if not mgr.is_ae_running():
                logger.info("AE 未运行，自动启动...")
                ok = mgr.start_ae_with_listener()
                if not ok:
                    logger.error("AE 启动失败")
                    return False
                # 等待 AE 完全启动
                logger.info("等待 AE 启动 (最多60s)...")
                for i in range(60):
                    time.sleep(1)
                    if mgr.is_ae_running():
                        logger.info(f"AE 已启动 ({i+1}s)")
                        break
                else:
                    logger.error("AE 启动超时")
                    return False
                # 额外等待 Bridge Listener 加载
                logger.info("等待 Bridge Listener 就绪 (最多30s)...")
                time.sleep(5)

            self._ae_ready = True
            return True

        except Exception as e:
            logger.warning(f"AE 自动启动失败: {e}，尝试降级模式")
            return False

    def _get_client(self):
        """延迟初始化 UnifiedAEClient（v2.0: 替代已弃用的 AECommandClient）"""
        if self._client is None:
            try:
                from ae.unified_ae_client import UnifiedAEClient
                self._client = UnifiedAEClient(enable_fallback=True, stats_enabled=True)
                logger.info("UnifiedAEClient 初始化成功")
            except ImportError:
                try:
                    from unified_ae_client import UnifiedAEClient
                    self._client = UnifiedAEClient(enable_fallback=True, stats_enabled=True)
                except ImportError:
                    logger.warning("UnifiedAEClient 不可用，使用降级模式")
                    self._client = None
        return self._client

    def _send(self, op: str, params: dict) -> dict:
        """发送命令到 AE（直接 Bridge 文件协议）

        v2.1: 直接写入 ~/Documents/ae-mcp-bridge/ae_command.json
              绕过 UnifiedAEClient 协议栈（格式不兼容）
        """
        # 命令名映射：snake_case → camelCase
        cmd_map = {
            "create_comp": "createComposition",
            "import_footage": "importFootage",
            "add_text": "createTextLayer",
            "add_shape": "createShapeLayer",
            "add_adjustment": "addAdjustmentLayer",
            "set_blend": "setBlendMode",
            "set_matte": "setTrackMatte",
            "list_comps": "listCompositions",
            "analyze": "analyzeProject",
            "add_effect_kf": "addEffectWithKeyframes",
            "execute_script": "executeAtomScript",
        }
        bridge_cmd = cmd_map.get(op, op)
        return self._send_bridge_command(bridge_cmd, params)

    def _send_bridge_command(self, command: str, args: dict, timeout: float = 15.0) -> dict:
        """通过 AE Bridge 文件轮询协议执行命令。

        listener (ae_mcp_auto_listener.jsx) 原生支持 ping / getProjectInfo /
        listCompositions / importFootage / executeAtomScript 等命令，
        不支持 runScript — 非原生命令自动包装为 executeAtomScript + JSX。

        协议: 写入 ae_command.json → AE listener 轮询 → 写入 ae_result.json
        目录: <project_root>/.ae-mcp-bridge/

        并发保护: Bridge 为单文件协议，并发调用会互相覆盖 ae_command/ae_result，
        通过类级锁串行化所有命令（acquire/release + try/finally）。
        """
        self._bridge_lock.acquire()
        try:
            return self._send_bridge_command_impl(command, args, timeout)
        finally:
            self._bridge_lock.release()

    def _send_bridge_command_impl(self, command: str, args: dict, timeout: float = 15.0) -> dict:
        """Bridge 命令实际执行（已由 _send_bridge_command 串行化保护）"""
        import time as _time

        # 修复: 使用项目根目录下的 .ae-mcp-bridge（非 ~/Documents/ae-mcp-bridge）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        bridge_dir = os.path.join(project_root, ".ae-mcp-bridge")
        cmd_path = os.path.join(bridge_dir, "ae_command.json")
        res_path = os.path.join(bridge_dir, "ae_result.json")  # 修复: ae_mcp_result.json → ae_result.json
        os.makedirs(bridge_dir, exist_ok=True)

        # runScript 兼容: listener 不支持 runScript，转换为 executeAtomScript
        if command == "runScript":
            command = "executeAtomScript"
            args = {"script": args.get("code", args.get("script", ""))}

        # listener 原生命令直接发送; 其余包装为 executeAtomScript + JSX
        # (createComposition 故意走 JSX 包装，包装版含 openInViewer 保证 activeItem 正确)
        native_commands = {"ping", "getProjectInfo", "executeAtomScript", "listCompositions", "importFootage"}
        if command in native_commands:
            bridge_cmd = command
            bridge_args = args
        else:
            jsx_code = self._build_jsx_for_command(command, args)
            if not jsx_code:
                return {"status": "error", "message": f"No JSX mapping for command: {command}", "success": False}
            bridge_cmd = "executeAtomScript"
            # listener 用 new Function(script) 执行，脚本体需 return 才能拿到返回值
            bridge_args = {"script": "return " + jsx_code}

        # 高精度时间戳
        ts = _time.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(_time.time() * 1000) % 1000:03d}"
        cmd_data = {
            "command": bridge_cmd,
            "args": bridge_args,
            "timestamp": ts,
            "processed": False,
        }
        try:
            with open(cmd_path, "w", encoding="utf-8") as f:
                json.dump(cmd_data, f, ensure_ascii=False)
            # listener 用文件 mtime 变化检测新命令，Windows 下 mtime 仅秒级精度，
            # 同秒内连续写命令会因 mtime 不变被跳过 → 强制 mtime 严格递增
            prev_mtime = getattr(type(self), "_last_cmd_mtime", 0.0)
            new_mtime = max(_time.time(), prev_mtime + 1.0)
            type(self)._last_cmd_mtime = new_mtime
            os.utime(cmd_path, (new_mtime, new_mtime))
        except Exception as e:
            return {"status": "error", "message": f"Bridge write failed: {e}", "success": False}

        # 竞态防护: listener 先置 processed 后写 ae_result.json，
        # 记录发送前的 result mtime，等到文件真正更新后再读
        try:
            prev_result_mtime = os.path.getmtime(res_path) if os.path.isfile(res_path) else -1.0
        except OSError:
            prev_result_mtime = -1.0

        # 轮询等待: 检查 ae_command.json 的 processed 标志
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            _time.sleep(0.3)
            try:
                with open(cmd_path, "r", encoding="utf-8") as f:
                    current_cmd = json.load(f)
                if not current_cmd.get("processed"):
                    continue
                # 命令已处理 — 等待新结果文件写入（mtime 必须严格大于发送前）
                if not os.path.isfile(res_path):
                    return {"status": "error", "message": "Command processed but ae_result.json missing", "success": False}
                try:
                    cur_result_mtime = os.path.getmtime(res_path)
                except OSError:
                    cur_result_mtime = -1.0
                if cur_result_mtime <= prev_result_mtime:
                    continue
                with open(res_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 统一返回格式（对齐 listener: {status, result}，以 status 判定成败；
                # handler 返回数据对象无 success 字段，错误为 {status:error, message}）
                status = data.get("status", "error")
                result_obj = data.get("result", {})
                if status == "success":
                    payload = result_obj
                    # executeAtomScript 包装返回值为 {executed, result}
                    if isinstance(payload, dict) and "executed" in payload and "result" in payload:
                        payload = payload.get("result")
                    # JSX 返回 JSON 字符串 → 解析
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except (json.JSONDecodeError, ValueError):
                            payload = {"raw": payload}
                    # 脚本内部失败 {success:false, error:{message}}
                    if isinstance(payload, dict) and payload.get("success") is False:
                        err_info = payload.get("error", {})
                        err_msg = err_info.get("message", "script error") if isinstance(err_info, dict) else str(err_info)
                        return {"status": "error", "message": err_msg, "success": False}
                    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                        return {"status": "success", "data": payload["data"], "success": True}
                    return {"status": "success", "data": payload if isinstance(payload, dict) else {"result": payload}, "success": True}
                else:
                    err_msg = data.get("message", "Bridge error")
                    return {"status": "error", "message": err_msg, "success": False}
            except (json.JSONDecodeError, OSError):
                continue

        return {"status": "error", "message": f"Bridge timeout ({timeout}s) for: {command}", "success": False}

    @staticmethod
    def _build_jsx_for_command(command: str, args: dict) -> str:
        """为非原生命令生成 JSX 脚本（通过 runScript 执行）。

        支持的命令: createComposition / importFootage / createTextLayer /
        createShapeLayer / addAdjustmentLayer / setBlendMode / setTrackMatte /
        listCompositions / analyzeProject / addEffectWithKeyframes / executeAtomScript
        """
        import json as _json

        def _s(v):
            return _json.dumps(str(v))

        def _comp_prefix(a):
            """生成合成定位 JSX 片段: 有 compName 按名查找（避免 activeItem 被导入素材劫持），否则用 activeItem"""
            cname = a.get("compName", "")
            if cname:
                return ('function __gc(n){for(var i=1;i<=app.project.numItems;i++){'
                        'var it=app.project.item(i);if(it instanceof CompItem&&it.name===n)return it;}return null;}'
                        f'var c=__gc({_s(cname)});')
            return 'var c=app.project.activeItem;'

        if command == "createComposition":
            name = args.get("name", "Comp 1")
            w = args.get("width", 1920)
            h = args.get("height", 1080)
            fps = args.get("frameRate", 30)
            dur = args.get("duration", 5)
            return f'(function(){{try{{var c=app.project.items.addComp({_s(name)},{w},{h},1,{dur},{fps});c.openInViewer();return JSON.stringify({{success:true,data:{{compName:c.name}}}});}}catch(e){{return JSON.stringify({{success:false,error:{{message:e.toString()}}}});}}}})();'
        if command == "importFootage":
            path = args.get("path", args.get("file", "")).replace("\\", "/")
            return f'(function(){{try{{var f=new File({_s(path)});if(!f.exists)return JSON.stringify({{success:false,error:{{message:"not found"}}}});var io=new ImportOptions(f);var fp=app.project.importFile(io);return JSON.stringify({{success:true,data:{{footageName:fp.name}}}});}}catch(e){{return JSON.stringify({{success:false,error:{{message:e.toString()}}}});}}}})();'
        if command == "createTextLayer":
            text = args.get("text", "")
            name = args.get("name", text)
            pre = _comp_prefix(args)
            return '(function(){try{' + pre + f'if(!c||!(c instanceof CompItem))return JSON.stringify({{success:false,error:{{message:"no target comp"}}}});var l=c.layers.addText({_s(text)});l.name={_s(name)};return JSON.stringify({{success:true,data:{{layerIndex:l.index}}}});}}catch(e){{return JSON.stringify({{success:false,error:{{message:e.toString()}}}});}}}})();'
        if command == "createShapeLayer":
            name = args.get("name", "Shape")
            pre = _comp_prefix(args)
            return '(function(){try{' + pre + f'if(!c||!(c instanceof CompItem))return JSON.stringify({{success:false,error:{{message:"no target comp"}}}});var l=c.layers.addShape();l.name={_s(name)};return JSON.stringify({{success:true,data:{{layerIndex:l.index}}}});}}catch(e){{return JSON.stringify({{success:false,error:{{message:e.toString()}}}});}}}})();'
        if command == "addAdjustmentLayer":
            name = args.get("name", "Adjustment")
            pre = _comp_prefix(args)
            return '(function(){try{' + pre + f'if(!c||!(c instanceof CompItem))return JSON.stringify({{success:false,error:{{message:"no target comp"}}}});var l=c.layers.addSolid([0,0,0],{_s(name)},c.width,c.height,1,c.duration);l.adjustmentLayer=true;return JSON.stringify({{success:true,data:{{layerIndex:l.index}}}});}}catch(e){{return JSON.stringify({{success:false,error:{{message:e.toString()}}}});}}}})();'
        if command == "setBlendMode":
            layer_idx = args.get("layerIndex", args.get("layer", 1))
            mode = args.get("mode", args.get("blendMode", "SCREEN")).upper()
            pre = _comp_prefix(args)
            return '(function(){try{' + pre + f'if(!c)return JSON.stringify({{success:false,error:{{message:"no comp"}}}});var m={{"NONE":BlendingMode.NONE,"SCREEN":BlendingMode.SCREEN,"MULTIPLY":BlendingMode.MULTIPLY,"ADD":BlendingMode.ADD,"OVERLAY":BlendingMode.OVERLAY}};c.layer({layer_idx}).blendingMode=m[{_s(mode)}]||BlendingMode.SCREEN;return JSON.stringify({{success:true}});}}catch(e){{return JSON.stringify({{success:false,error:{{message:e.toString()}}}});}}}})();'
        if command == "setTrackMatte":
            layer_idx = args.get("layerIndex", 1)
            matte = args.get("matteType", "ALPHA_TRACK_MATTE").upper()
            pre = _comp_prefix(args)
            return '(function(){try{' + pre + f'if(!c)return JSON.stringify({{success:false,error:{{message:"no comp"}}}});var m={{"NO_TRACK_MATTE":TrackMatteType.NO_TRACK_MATTE,"ALPHA_TRACK_MATTE":TrackMatteType.ALPHA_TRACK_MATTE,"LUMA_TRACK_MATTE":TrackMatteType.LUMA_TRACK_MATTE}};c.layer({layer_idx}).trackMatteType=m[{_s(matte)}]||TrackMatteType.ALPHA_TRACK_MATTE;return JSON.stringify({{success:true}});}}catch(e){{return JSON.stringify({{success:false,error:{{message:e.toString()}}}});}}}})();'
        if command == "listCompositions":
            return '(function(){try{var comps=[];for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it instanceof CompItem)comps.push({name:it.name,duration:it.duration,width:it.width,height:it.height});}return JSON.stringify({success:true,data:{compositions:comps}});}catch(e){return JSON.stringify({success:false,error:{message:e.toString()}});}})();'
        if command == "analyzeProject":
            return '(function(){try{var comps=[];for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it instanceof CompItem)comps.push({name:it.name,duration:it.duration});}return JSON.stringify({success:true,data:{compositions:comps,totalItems:app.project.numItems}});}catch(e){return JSON.stringify({success:false,error:{message:e.toString()}});}})();'
        if command == "addEffectWithKeyframes":
            layer_idx = args.get("layerIndex", args.get("layer", 1))
            effect_name = args.get("effectName", args.get("matchName", ""))
            prop_name = args.get("propertyName", "")
            keyframes = args.get("keyframes", [])
            kf_json = _json.dumps(keyframes)
            pre = _comp_prefix(args)
            return '(function(){try{' + pre + f'if(!c)return JSON.stringify({{success:false,error:{{message:"no comp"}}}});var l=c.layer({layer_idx});var eff=l.Effects.addProperty({_s(effect_name)});var kf={kf_json};var pn={_s(prop_name)};if(pn&&kf.length>0){{var p=eff.property(pn);for(var i=0;i<kf.length;i++){{p.setValueAtTime(kf[i].time,kf[i].value);}}}}return JSON.stringify({{success:true,data:{{effectIndex:eff.propertyIndex}}}});}}catch(e){{return JSON.stringify({{success:false,error:{{message:e.toString()}}}});}}}})();'
        if command == "executeAtomScript":
            return args.get("scriptContent", args.get("script", ""))
        return ""

    def _send_atom_script(self, op: str, params: dict) -> dict:
        """通过 executeAtomScript 执行未映射的命令"""
        jsx_body = self._build_jsx_for_op(op, params)
        if not jsx_body:
            logger.debug(f"No JSX mapping for op: {op}")
            return {"status": "error", "message": f"Unsupported op: {op}", "success": False}
        # listener 期望键为 script; eval 保证多语句体的最后一个表达式值可作为返回值
        return self._send_bridge_command(
            "executeAtomScript",
            {"script": "return eval(" + json.dumps(jsx_body) + ");"},
        )

    @staticmethod
    def _build_jsx_for_op(op: str, params: dict) -> str:
        """为未映射的命令生成 JSX 脚本"""
        import json as _json

        def _s(v):
            """安全转义 JSX 字符串插值"""
            return _json.dumps(str(v))

        if op == "importFootage":
            path = params.get("path", "").replace("\\", "/")
            return f'var f = new File({_s(path)}); app.project.importFile(f);'
        if op == "analyzeProject":
            return (
                'var comps = [];'
                'for (var i = 1; i <= app.project.numItems; i++) {'
                '  var item = app.project.item(i);'
                '  if (item instanceof CompItem) comps.push({name: item.name, duration: item.duration});'
                '}'
                'JSON.stringify({compositions: comps, totalItems: app.project.numItems});'
            )
        if op == "addEffectWithKeyframes":
            layer = params.get("layerIndex", 1)
            effect_name = params.get("effectName", "")
            return (
                f'var comp = app.project.activeItem;'
                f'var layer = comp.layer({layer});'
                f'layer.Effects.addProperty({_s(effect_name)});'
            )
        return ""

    def run(self, previous_data: dict) -> dict:
        """执行阶段：将剧本转化为 AE 项目操作 (或 Resolve/FFmpeg 降级)"""
        plan = previous_data.get("plan", {})
        script = plan.get("script")
        if not script:
            return {"project_path": "", "error": "No script from planning stage"}

        result = {
            "project_path": "",
            "composition": "",
            "layers_created": 0,
            "effects_applied": 0,
            "keyframes_set": 0,
            "bridge_connected": False,
            "execution_mode": "",
        }

        # 执行路径优先级:
        # 1. AE Bridge → 合成/图层/效果
        # 2. Resolve Bridge → 调色/渲染
        # 3. FFmpeg 降级 → 基础编辑

        # 0. 尝试 AE Bridge
        self._ensure_ae_ready()
        bridge_ok = self._check_bridge()
        result["bridge_connected"] = bridge_ok

        if bridge_ok:
            result["execution_mode"] = "ae_bridge"
            return self._execute_ae(script, plan, previous_data, result)

        # 1. 尝试 Resolve Bridge（调色/渲染）
        resolve_ok = self._check_resolve()
        if resolve_ok:
            result["execution_mode"] = "resolve_bridge"
            return self._execute_resolve(script, plan, previous_data, result)

        # 2. FFmpeg 降级执行
        result["execution_mode"] = "ffmpeg_fallback"
        return self._execute_ffmpeg(script, plan, previous_data, result)

    def _execute_ae(self, script: dict, plan: dict, previous_data: dict, result: dict) -> dict:
        """AE Bridge 执行路径 — 建工程 + 加效果 + 真实渲染输出"""
        project_path = self._create_project(script)
        result["project_path"] = project_path

        comp_name = script.get("title", self.config.input_topic or "Pipeline_Output")
        comp_duration = script.get("total_duration", 30)
        comp = self._create_composition(comp_name, comp_duration, script)
        result["composition"] = comp

        perceive = previous_data.get("perceive", {})
        media_files = perceive.get("videos", []) + perceive.get("images", [])
        imported = self._import_footage(media_files)
        result["layers_created"] = len(imported)

        # 将导入的素材添加到合成中（P3-A: 按合成名定位）
        if imported:
            self._add_footage_to_comp(imported, comp_name)

        shots = plan.get("shot_list", [])
        arranged = self._arrange_shots(shots, comp_name)
        result["layers_created"] += arranged

        transitions = plan.get("transition_plan", [])
        result["effects_applied"] = self._apply_transitions(transitions, comp_name, comp_duration)

        effects = plan.get("effect_stack", [])
        result["effects_applied"] += self._apply_effects(effects, comp_name)

        result["keyframes_set"] = self._set_keyframes(plan.get("style_params", {}), comp_name)

        # P3-B: 风格效果真实落地（调整图层 + 可见效果）
        style_ops = self._build_style_ops(plan)
        if style_ops:
            result["effects_applied"] += self._apply_visible_style(comp_name, style_ops)
            result["style_effects"] = [op.get("label", op.get("effect", "")) for op in style_ops]

        # === P0 关键修复: 真实渲染输出 ===
        # 保存项目 → 通过 AE 内部渲染队列输出真实视频
        output_dir = self.config.output_dir or "output"
        os.makedirs(output_dir, exist_ok=True)
        project_name = self.config.project_name or script.get("title", "pipeline_output")
        video_output = os.path.join(output_dir, f"{project_name}.mp4")

        # 保存 .aep 到真实路径
        aep_path = os.path.join(output_dir, f"{project_name}.aep")
        save_ok = self._save_project_as(aep_path)
        if save_ok:
            result["project_path"] = aep_path

        # 通过 AE 内部渲染队列输出视频（P3-A: 按合成名定位）
        render_ok = self._render_via_bridge(video_output, comp_duration, comp_name)
        if render_ok and os.path.isfile(video_output):
            file_size = os.path.getsize(video_output)
            if file_size > 10240:  # >10KB 才算有效
                result["project_path"] = video_output
                result["execution_mode"] = "ae_render"
                result["render_output"] = video_output
                result["file_size_mb"] = round(file_size / (1024 * 1024), 2)
                logger.info(f"[AE-RENDER] 真实渲染成功: {video_output} ({result['file_size_mb']}MB)")
                return result
            else:
                logger.warning(f"[AE-RENDER] 输出文件过小 ({file_size}B)，视为失败")
        else:
            logger.warning("[AE-RENDER] AE 内部渲染失败，尝试 aerender 降级")

        # 降级: 尝试 aerender CLI
        if save_ok and os.path.isfile(aep_path):
            aerender_ok = self._render_aerender_fallback(aep_path, comp_name, video_output)
            if aerender_ok and os.path.isfile(video_output) and os.path.getsize(video_output) > 10240:
                result["project_path"] = video_output
                result["execution_mode"] = "ae_render"
                result["render_output"] = video_output
                result["file_size_mb"] = round(os.path.getsize(video_output) / (1024 * 1024), 2)
                logger.info(f"[AERENDER] 渲染成功: {video_output}")
                return result

        # 最终降级: FFmpeg 路径（使用已感知素材）
        logger.warning("[AE-EXEC] AE 渲染全部失败，降级到 FFmpeg")
        result["execution_mode"] = "ffmpeg_fallback"
        return self._execute_ffmpeg(script, plan, previous_data, result)

    def _execute_ffmpeg(self, script: dict, plan: dict, previous_data: dict, result: dict) -> dict:
        """FFmpeg 降级执行路径 — 使用 FFmpeg 编辑引擎实现真实视频处理"""
        import subprocess
        perceive = previous_data.get("perceive", {})
        videos = perceive.get("videos", [])

        output_dir = self.config.output_dir or "output"
        os.makedirs(output_dir, exist_ok=True)
        project_name = self.config.project_name or script.get("title", "pipeline_output")
        concat_path = os.path.join(output_dir, f"{project_name}_concat.mp4")
        final_path = os.path.join(output_dir, f"{project_name}_final.mp4")

        # 如果有素材，使用编辑引擎处理
        if videos:
            file_paths = [v.get("path", "") for v in videos if os.path.isfile(v.get("path", ""))]
            if file_paths:
                try:
                    from pipeline.ffmpeg_edit_engine import FFmpegEditEngine, TransitionEngine
                    from pipeline.stages import resolve_ffmpeg
                    ffmpeg = resolve_ffmpeg(self.config)
                    engine = FFmpegEditEngine(ffmpeg)

                    # 1. 尝试带转场拼接 (如果plan中有转场信息)
                    transitions = plan.get("transition_plan", [])
                    shot_list = plan.get("shot_list", [])
                    use_transitions = len(transitions) > 0 and len(file_paths) >= 2

                    if use_transitions and len(file_paths) >= 2:
                        # 映射plan中的转场到FFmpeg
                        t_types = []
                        t_durs = []
                        for t in transitions:
                            t_type = t.get("type", "fade")
                            t_map = {"dissolve": "dissolve", "wipe": "wipeleft",
                                     "push": "slideright", "fade": "fade", "cut": "fade"}
                            t_types.append(t_map.get(t_type, "fade"))
                            t_durs.append(t.get("duration", 0.5))
                        # 补齐
                        while len(t_types) < len(file_paths) - 1:
                            t_types.append("fade")
                            t_durs.append(0.5)
                        success = engine.concat_with_transitions(
                            file_paths, concat_path, t_types, t_durs
                        )
                        if success:
                            result["effects_applied"] = len(t_types)
                            logger.info(f"转场拼接: {len(file_paths)} clips, {len(t_types)} transitions")
                    else:
                        # 普通concat
                        success = self._do_concat(file_paths, concat_path, ffmpeg, output_dir)

                    if not success and not os.path.isfile(concat_path):
                        raise RuntimeError("concat failed")

                    # 2. 应用滤镜增强 (从plan的style_params/effect_stack提取)
                    filter_applied = self._apply_ffmpeg_filters(
                        engine, concat_path, final_path, plan, script
                    )

                    output_path = final_path if filter_applied and os.path.isfile(final_path) else concat_path
                    result["project_path"] = output_path
                    result["composition"] = project_name
                    result["layers_created"] = len(file_paths)
                    logger.info(f"FFmpeg编辑完成: {output_path}")
                    return result

                except Exception as e:
                    logger.debug(f"FFmpeg edit engine failed: {e}")

        # 最终降级: 记录剧本供手动执行
        script_path = os.path.join(output_dir, f"{project_name}_script.json")
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                json.dump(script, f, ensure_ascii=False, indent=2)
            result["project_path"] = script_path
            result["composition"] = project_name
            logger.info(f"Script saved for manual execution: {script_path}")
        except Exception as e:
            logger.debug(f"Script save failed: {e}")
        return result

    def _do_concat(self, file_paths: list[str], output: str, ffmpeg: str, output_dir: str) -> bool:
        """基础concat拼接"""
        import subprocess
        list_path = os.path.join(output_dir, "_concat_list.txt")
        with open(list_path, "w") as f:
            for fp in file_paths:
                f.write(f"file '{fp.replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n")
        cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", list_path,
               "-c", "copy", "-movflags", "+faststart", output]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
        return r.returncode == 0 and os.path.isfile(output)

    def _apply_ffmpeg_filters(self, engine, input_path: str, output_path: str,
                               plan: dict, script: dict) -> bool:
        """从plan中提取滤镜参数并应用"""
        from pipeline.ffmpeg_edit_engine import ColorGradeParams, FFmpegFilterBuilder, SharpenParams, VignetteParams
        fb = FFmpegFilterBuilder()
        has_filter = False

        # 从 style_params 提取调色信息
        style_params = plan.get("style_params", {})
        if style_params:
            color = ColorGradeParams(
                brightness=style_params.get("brightness", 0),
                contrast=style_params.get("contrast", 1.0),
                saturation=style_params.get("saturation", 1.0),
                gamma=style_params.get("gamma", 1.0),
            )
            if any([color.brightness != 0, color.contrast != 1.0,
                    color.saturation != 1.0, color.gamma != 1.0]):
                fb.color_grade(color)
                has_filter = True

        # 从 effect_stack 提取效果
        effect_stack = plan.get("effect_stack", [])
        for eff in effect_stack:
            name = eff.get("name", "").lower()
            if "sharpen" in name or "锐化" in name:
                fb.sharpen(SharpenParams(amount=1.2, radius=0.8))
                has_filter = True
            elif "vignette" in name or "暗角" in name:
                fb.vignette(VignetteParams())
                has_filter = True

        # 从 VRS 分析结果提取风格标签
        vrs_analysis = plan.get("vrs_analysis", {})
        if vrs_analysis:
            try:
                from pipeline.vrs_effect_lander import VRSEffectLander
                lander = VRSEffectLander(engine.ffmpeg_bin)
                vrs_result = lander.apply(input_path, vrs_analysis, output_path)
                if vrs_result.get("success") and vrs_result.get("applied"):
                    return True
            except Exception as e:
                logger.debug(f"VRS lander failed: {e}")

        if not has_filter:
            # 默认应用轻度增强
            fb.sharpen(SharpenParams(amount=0.8, radius=0.6))
            fb.color_grade(ColorGradeParams(contrast=1.05, saturation=1.05))
            has_filter = True

        if has_filter:
            total_dur = engine._get_duration(input_path)
            return engine.apply_filters(input_path, output_path, fb, total_dur)
        return False

    def _check_bridge(self) -> bool:
        """检测 AE Bridge 是否在线（通过 ping 命令，不依赖工程状态）"""
        result = self._send_bridge_command("ping", {}, timeout=8.0)
        return result.get("status") == "success"

    def _check_resolve(self) -> bool:
        """检测 Resolve 是否可用"""
        try:
            from integrations.davinci_fuscript import ResolveColorEngine
            engine = ResolveColorEngine()
            return engine.check_resolve_running()
        except Exception as e:
            logger.debug(f"Resolve check failed: {e}")
            return False

    def _execute_resolve(self, script: dict, plan: dict, previous_data: dict, result: dict) -> dict:
        """Resolve Bridge 执行路径 — 调色/渲染"""
        try:
            from integrations.davinci_fuscript import ColorGradeConfig, ResolveColorEngine

            perceive = previous_data.get("perceive", {})
            media_files = perceive.get("videos", [])
            video_paths = [v.get("path", "") for v in media_files if isinstance(v, dict) and os.path.isfile(v.get("path", ""))]

            if not video_paths:
                # Resolve 需要实际视频文件，没有则降级到 FFmpeg
                logger.info("Resolve: no video files, falling back to FFmpeg")
                result["execution_mode"] = "ffmpeg_fallback"
                return self._execute_ffmpeg(script, plan, previous_data, result)

            output_dir = self.config.output_dir or "output"
            os.makedirs(output_dir, exist_ok=True)
            project_name = self.config.project_name or script.get("title", "pipeline_resolve")

            engine = ResolveColorEngine()
            style_params = plan.get("style_params", {})
            preset = style_params.get("preset", "cinematic")

            config = ColorGradeConfig(
                preset=preset,
                brightness=style_params.get("brightness", 1.0),
                contrast=style_params.get("contrast", 1.0),
                saturation=style_params.get("saturation", 1.0),
            )

            logger.info(f"Resolve grade: {len(video_paths)} videos, preset={preset}")
            fuscript_result = engine.create_project(
                project_name=project_name,
                media_files=video_paths,
                color_config=config,
                render=True,
                output_dir=output_dir,
            )

            if fuscript_result.success:
                result["project_path"] = fuscript_result.output_path or output_dir
                result["composition"] = project_name
                result["layers_created"] = fuscript_result.clips_graded
                logger.info(f"Resolve grade complete: {fuscript_result.output_path}")
            else:
                logger.warning(f"Resolve grade failed: {fuscript_result.errors}")
                # 降级到 FFmpeg
                result["execution_mode"] = "ffmpeg_fallback"
                return self._execute_ffmpeg(script, plan, previous_data, result)

            engine.close_resolve()
            return result

        except Exception as e:
            logger.warning(f"Resolve execution failed: {e}, falling back to FFmpeg")
            result["execution_mode"] = "ffmpeg_fallback"
            return self._execute_ffmpeg(script, plan, previous_data, result)

    def _create_project(self, script: dict) -> str:
        """创建AE项目路径"""
        output_dir = self.config.output_dir or "output"
        os.makedirs(output_dir, exist_ok=True)
        project_name = self.config.project_name or script.get("title", "pipeline_output")
        project_path = os.path.join(output_dir, f"{project_name}.aep")
        # AE Bridge 不支持直接创建项目，需要在 AE 中手动操作或使用 File > New
        # 这里记录项目路径供后续使用
        return project_path

    def _create_composition(self, name: str, duration: float, script: dict) -> str:
        """通过 Bridge 创建合成"""
        result = self._send("create_comp", {
            "name": name,
            "width": script.get("width", 1920),
            "height": script.get("height", 1080),
            "frameRate": script.get("fps", 30),
            "duration": duration,
            "bgColor": script.get("bg_color", [0, 0, 0]),
        })
        if result.get("status") == "success":
            logger.info(f"合成已创建: {name} ({duration}s)")
            return name
        else:
            logger.debug(f"合成创建降级: {result.get('message', 'unknown')}")
            return name

    def _import_footage(self, files: list[dict]) -> list[dict]:
        """通过 Bridge 导入素材，返回 [{"path": ..., "name": AE内项目名}]"""
        imported = []
        for f in files:
            path = f.get("path", "") if isinstance(f, dict) else str(f)
            if not path or not os.path.isfile(path):
                continue
            result = self._send("import_footage", {
                "filePath": path,
                "type": "footage",
            })
            if result.get("status") == "success":
                ae_name = ""
                data = result.get("data", {})
                if isinstance(data, dict):
                    ae_name = data.get("footageName", "") or data.get("name", "")
                imported.append({"path": path, "name": ae_name or os.path.basename(path)})
                logger.debug(f"素材已导入: {os.path.basename(path)}")
            else:
                logger.debug(f"素材导入失败: {path} - {result.get('message', '')}")
        return imported

    def _arrange_shots(self, shots: list[dict], comp_name: str = "") -> int:
        """按剧本排列镜头到时间线（创建对应图层）"""
        arranged = 0
        for shot in shots:
            shot_type = shot.get("type", "text")
            shot_name = f"Shot_{shot.get('index', arranged)}"

            if shot_type == "text":
                result = self._send("add_text", {
                    "text": shot.get("text", shot_name),
                    "name": shot_name,
                    "fontSize": shot.get("font_size", 48),
                    "color": shot.get("color", [1, 1, 1]),
                    "compName": comp_name,
                })
            elif shot_type == "shape":
                result = self._send("add_shape", {
                    "shapeType": shot.get("shape", "rectangle"),
                    "name": shot_name,
                    "color": shot.get("color", [0.5, 0.5, 0.5]),
                    "compName": comp_name,
                })
            else:
                result = self._send("add_adjustment", {
                    "name": shot_name,
                    "compName": comp_name,
                })

            if result.get("status") == "success":
                arranged += 1
        return arranged

    def _apply_transitions(self, transitions: list[dict], comp_name: str = "",
                           comp_duration: float = 30.0) -> int:
        """应用转场效果：闪白/硬切类用闪白固态图层，其余用转场效果关键帧"""
        applied = 0
        n = len(transitions)
        for idx, t in enumerate(transitions):
            t_type = str(t.get("type", "dissolve")).lower()
            if t_type in ("flash", "flash_white", "cut", "闪白", "硬切"):
                # P3-B: 闪白转场 — 时间点处叠加白色闪烁图层
                time_pos = t.get("start_time")
                if time_pos is None:
                    time_pos = comp_duration * (idx + 1) / (n + 1)
                if self._add_flash_white(comp_name, float(time_pos)):
                    applied += 1
                continue

            effect_name = t.get("effect_name", "")
            if not effect_name:
                effect_map = {
                    "dissolve": "ADBE Linear Dissolve",
                    "wipe": "ADBE Linear Wipe",
                    "push": "ADBE Push",
                    "slide": "ADBE Slide",
                }
                effect_name = effect_map.get(t_type, "ADBE Linear Dissolve")

            result = self._send("add_effect_kf", {
                "layerIndex": t.get("to", 0),
                "effectName": effect_name,
                "propertyName": "Transition Completion",
                "keyframes": [
                    {"time": t.get("start_time", 0), "value": 0},
                    {"time": t.get("start_time", 0) + t.get("duration", 1), "value": 100},
                ],
                "compName": comp_name,
            })
            if result.get("status") == "success":
                applied += 1
        return applied

    def _apply_effects(self, effects: list[dict], comp_name: str = "") -> int:
        """应用效果"""
        applied = 0
        for eff in effects:
            result = self._send("add_effect_kf", {
                "layerName": eff.get("layer", ""),
                "effectName": eff.get("match_name", eff.get("name", "")),
                "params": eff.get("params", {}),
                "compName": comp_name,
            })
            if result.get("status") == "success":
                applied += 1
        return applied

    def _set_keyframes(self, style_params: dict, comp_name: str = "") -> int:
        """设置关键帧"""
        if not style_params:
            return 0
        set_count = 0
        for prop, val in style_params.items():
            if isinstance(val, dict) and "keyframes" in val:
                result = self._send("add_effect_kf", {
                    "layerName": val.get("layer", ""),
                    "propertyName": prop,
                    "keyframes": val["keyframes"],
                    "compName": comp_name,
                })
                if result.get("status") == "success":
                    set_count += len(val["keyframes"])
        return set_count

    def _add_footage_to_comp(self, imported_files: list[dict], comp_name: str) -> int:
        """将已导入的素材按顺序叠加到指定合成（P3-A: 按名定位，不再依赖 activeItem）

        叠加规则：每个素材的 startTime = 现有图层的最大 outPoint；
        超出合成时长则裁剪 outPoint；完全溢出则丢弃。
        """
        added = 0
        for item in imported_files:
            item_name = item.get("name") or os.path.basename(item.get("path", ""))
            jsx = (
                '(function(){try{'
                'function __gc(n){for(var i=1;i<=app.project.numItems;i++){'
                'var it=app.project.item(i);if(it instanceof CompItem&&it.name===n)return it;}return null;}'
                f'var c=__gc({json.dumps(comp_name)});'
                'if(!c)return JSON.stringify({success:false,error:{message:"comp not found"}});'
                f'var itemName={json.dumps(item_name)};'
                'var found=null;'
                'for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);'
                'if(it.name===itemName&&it instanceof FootageItem){found=it;break;}}'
                'if(!found)return JSON.stringify({success:false,error:{message:"footage not found: "+itemName}});'
                'var start=0;'
                'for(var j=1;j<=c.numLayers;j++){var ly=c.layer(j);if(ly.outPoint>start)start=ly.outPoint;}'
                'if(start>=c.duration)return JSON.stringify({success:false,error:{message:"comp full"}});'
                'var layer=c.layers.add(found);'
                'layer.startTime=start;'
                'if(layer.outPoint>c.duration)layer.outPoint=c.duration;'
                'return JSON.stringify({success:true,data:{layerName:found.name,startTime:start}});'
                '}catch(e){return JSON.stringify({success:false,error:{message:e.toString()}});}})();'
            )
            r = self._send_bridge_command("executeAtomScript", {"script": "return " + jsx}, timeout=15.0)
            if r.get("status") == "success":
                added += 1
            else:
                logger.debug(f"素材入合成失败: {item_name} - {r.get('message', '')}")
        return added

    # P3-B: AE 效果 matchName 映射表
    AE_EFFECT_MATCH_NAMES = {
        "hue_saturation": "ADBE HUE SATURATION",
        "brightness_contrast": "ADBE Brightness & Contrast 2",
        "color_balance": "ADBE Color Balance",
        "glow": "ADBE Glo2",
        "noise": "ADBE Noise",
    }

    def _build_style_ops(self, plan: dict) -> list[dict]:
        """从 plan 的 style_params/effect_stack 构建可见效果操作列表（P3-B）

        每个 op: {"effect": matchName, "prop": 属性名, "value": 数值, "label": 语义标签}
        """
        ops: list[dict] = []
        style_params = plan.get("style_params", {}) or {}
        style_text = json.dumps(plan, ensure_ascii=False).lower()

        # 1) 数值型风格参数 → 换算为 AE 效果属性（propMatch 已在本项目验证，见 video/style_migrator.py）
        sat = style_params.get("saturation", 1.0)
        if isinstance(sat, (int, float)) and abs(sat - 1.0) > 0.02:
            # saturation 1.0 → 0；0.7 → -30；clamp [-100, 100]
            val = max(-100, min(100, int(round((sat - 1.0) * 100))))
            ops.append({"effect": "ADBE HUE SATURATION", "propMatch": "ADBE HUE SATURATION-0005",
                        "value": val, "label": f"saturation={sat}"})
        contrast = style_params.get("contrast", 1.0)
        if isinstance(contrast, (int, float)) and abs(contrast - 1.0) > 0.02:
            val = max(-100, min(100, int(round((contrast - 1.0) * 100))))
            ops.append({"effect": "ADBE Brightness & Contrast 2", "propMatch": "ADBE Brightness & Contrast 2-0002",
                        "value": val, "label": f"contrast={contrast}"})
        brightness = style_params.get("brightness", 1.0)
        if isinstance(brightness, (int, float)) and abs(brightness - 1.0) > 0.02:
            val = max(-100, min(100, int(round((brightness - 1.0) * 100))))
            ops.append({"effect": "ADBE Brightness & Contrast 2", "propMatch": "ADBE Brightness & Contrast 2-0001",
                        "value": val, "label": f"brightness={brightness}"})

        # 2) 语义关键词 → 预设效果组合
        warm_kw = ("暖", "warm", "胶片", "film", "日系", "复古")
        cool_kw = ("冷", "cool", "赛博", "cyber", "霓虹", "neon")
        if any(k in style_text for k in warm_kw):
            ops.append({"effect": "ADBE Color Balance", "propMatch": "ADBE Color Balance-0001",
                        "value": 12, "label": "warm_red+12"})
            ops.append({"effect": "ADBE Color Balance", "propMatch": "ADBE Color Balance-0003",
                        "value": -12, "label": "warm_blue-12"})
            if not any(o["effect"] == "ADBE HUE SATURATION" for o in ops):
                ops.append({"effect": "ADBE HUE SATURATION", "propMatch": "ADBE HUE SATURATION-0005",
                            "value": -20, "label": "film_low_sat"})
        if any(k in style_text for k in cool_kw):
            ops.append({"effect": "ADBE Color Balance", "propMatch": "ADBE Color Balance-0003",
                        "value": 15, "label": "cool_blue+15"})
            ops.append({"effect": "ADBE Color Balance", "propMatch": "ADBE Color Balance-0001",
                        "value": -8, "label": "cool_red-8"})
            ops.append({"effect": "ADBE Glo2", "propMatch": "", "value": 0,
                        "label": "neon_glow"})

        # 3) effect_stack 文本 → 效果
        for eff in plan.get("effect_stack", []) or []:
            name = str(eff.get("name", "") if isinstance(eff, dict) else eff).lower()
            if "glow" in name or "发光" in name:
                if not any(o["label"] == "neon_glow" for o in ops):
                    ops.append({"effect": "ADBE Glo2", "propMatch": "", "value": 0,
                                "label": f"glow:{name}"})
            elif "grain" in name or "颗粒" in name or "noise" in name:
                ops.append({"effect": "ADBE Noise", "propMatch": "ADBE Noise-0001",
                            "value": 8, "label": f"grain:{name}"})
        return ops

    def _apply_visible_style(self, comp_name: str, ops: list[dict]) -> int:
        """在合成顶部建调整图层并逐个应用可见效果（P3-B）"""
        if not ops:
            return 0
        ops_json = json.dumps(ops, ensure_ascii=False)
        jsx = (
            '(function(){try{'
            'function __gc(n){for(var i=1;i<=app.project.numItems;i++){'
            'var it=app.project.item(i);if(it instanceof CompItem&&it.name===n)return it;}return null;}'
            f'var c=__gc({json.dumps(comp_name)});'
            'if(!c)return JSON.stringify({success:false,error:{message:"comp not found"}});'
            'var adj=c.layers.addSolid([0.5,0.5,0.5],"StyleAdjust",c.width,c.height,1,c.duration);'
            'adj.adjustmentLayer=true;'
            f'var ops={ops_json};'
            'var applied=0;var errors=[];'
            'for(var i=0;i<ops.length;i++){try{'
            'var eff=adj.Effects.addProperty(ops[i].effect);'
            'if(ops[i].propMatch){var found=null;'
            'for(var j=1;j<=eff.numProperties;j++){var pp=eff.property(j);if(pp.matchName===ops[i].propMatch){found=pp;break;}}'
            'if(found){found.setValue(ops[i].value);}else{errors.push(ops[i].propMatch+":not found");}}'
            'applied++;'
            '}catch(e){errors.push(ops[i].effect+":"+e.toString());}}'
            'return JSON.stringify({success:true,data:{applied:applied,errors:errors}});'
            '}catch(e){return JSON.stringify({success:false,error:{message:e.toString()}});}})();'
        )
        r = self._send_bridge_command("executeAtomScript", {"script": "return " + jsx}, timeout=20.0)
        if r.get("status") == "success":
            data = r.get("data", {}) if isinstance(r.get("data"), dict) else {}
            applied = int(data.get("applied", 0))
            errors = data.get("errors", [])
            logger.info(f"[P3-B] 风格效果落地: {applied}/{len(ops)}"
                        + (f"，失败: {errors}" if errors else ""))
            return applied
        logger.debug(f"[P3-B] 风格效果落地失败: {r.get('message', '')}")
        return 0

    def _add_flash_white(self, comp_name: str, time_pos: float) -> bool:
        """在时间点添加闪白转场图层（不透明度三角关键帧）"""
        jsx = (
            '(function(){try{'
            'function __gc(n){for(var i=1;i<=app.project.numItems;i++){'
            'var it=app.project.item(i);if(it instanceof CompItem&&it.name===n)return it;}return null;}'
            f'var c=__gc({json.dumps(comp_name)});'
            'if(!c)return JSON.stringify({success:false,error:{message:"comp not found"}});'
            f'var t={float(time_pos)};'
            'var l=c.layers.addSolid([1,1,1],"FlashWhite",c.width,c.height,1,0.3);'
            'l.startTime=Math.max(0,t-0.15);'
            'var op=l.property("Transform").property("Opacity");'
            'op.setValueAtTime(Math.max(0,t-0.15),0);'
            'op.setValueAtTime(t,100);'
            'op.setValueAtTime(Math.min(c.duration,t+0.15),0);'
            'return JSON.stringify({success:true,data:{time:t}});'
            '}catch(e){return JSON.stringify({success:false,error:{message:e.toString()}});}})();'
        )
        r = self._send_bridge_command("executeAtomScript", {"script": "return " + jsx}, timeout=15.0)
        return r.get("status") == "success"

    def _render_via_bridge(self, output_path: str, duration: float = 30.0, comp_name: str = "") -> bool:
        """通过 AE 内部渲染队列输出视频（P3-A: 按名定位合成，不依赖 activeItem）"""
        # 清理旧输出
        if os.path.isfile(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass

        output_escaped = output_path.replace("\\", "/")
        if comp_name:
            comp_ref = (
                'function __gc(n){for(var i=1;i<=app.project.numItems;i++){'
                'var it=app.project.item(i);if(it instanceof CompItem&&it.name===n)return it;}return null;}'
                f'var comp=__gc({json.dumps(comp_name)});'
            )
        else:
            comp_ref = 'var comp=app.project.activeItem;'
        jsx = (
            '(function(){try{'
            + comp_ref +
            'if(!comp||!(comp instanceof CompItem))'
            'return JSON.stringify({success:false,error:{message:"no comp for render"}});'
            'var rq=app.project.renderQueue;'
            'var rqi=rq.items.add(comp);'
            'var om=rqi.outputModule(1);'
            f'om.file=new File("{output_escaped}");'
            'om.format="QuickTime";'
            'om.useRegionOfInterest=false;'
            'rq.render();'
            'rqi.remove();'
            'return JSON.stringify({success:true,data:{rendered:true}});'
            '}catch(e){return JSON.stringify({success:false,error:{message:e.toString()}});}})();'
        )
        # 渲染可能需要较长时间
        render_timeout = max(120.0, duration * 10)
        r = self._send_bridge_command("executeAtomScript", {"script": "return " + jsx}, timeout=render_timeout)
        if r.get("status") == "success":
            # 等待文件写入完成
            for _ in range(30):
                if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
                    return True
                time.sleep(1)
            return os.path.isfile(output_path)
        else:
            logger.debug(f"Bridge render failed: {r.get('message', 'unknown')}")
            return False

    def _render_aerender_fallback(self, aep_path: str, comp_name: str, output_path: str) -> bool:
        """aerender CLI 降级渲染"""
        try:
            from rendering.ae_render_engine import AERenderEngine
            engine = AERenderEngine()
            job = engine.render(
                project=aep_path,
                composition=comp_name,
                output=output_path,
                output_format="mp4",
                reuse_ae=True,
            )
            engine.wait(job.job_id, timeout=600)
            return job.status.value == "success" and os.path.isfile(output_path)
        except Exception as e:
            logger.debug(f"aerender fallback failed: {e}")
            return False

    def _save_project(self):
        """保存项目（通过 executeAtomScript 执行 app.project.save()）"""
        jsx = (
            '(function(){try{'
            'app.project.save();'
            'return JSON.stringify({success:true});'
            '}catch(e){return JSON.stringify({success:false,error:{message:e.toString()}});}})();'
        )
        result = self._send_bridge_command("executeAtomScript", {"script": "return " + jsx}, timeout=10.0)
        if result.get("status") != "success":
            logger.debug(f"Save failed: {result.get('message', 'unknown')}")

    def _save_project_as(self, path: str) -> bool:
        """另存项目到指定路径"""
        path_escaped = path.replace("\\", "/")
        jsx = (
            '(function(){try{'
            f'app.project.save(new File("{path_escaped}"));'
            'return JSON.stringify({success:true});'
            '}catch(e){return JSON.stringify({success:false,error:{message:e.toString()}});}})();'
        )
        r = self._send_bridge_command("executeAtomScript", {"script": "return " + jsx}, timeout=15.0)
        return r.get("status") == "success"
