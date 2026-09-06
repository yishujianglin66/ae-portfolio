"""
PR Bridge Client — 通过 CEP 插件桥接协议与 Premiere Pro 通信

协议：
  1. 将 ExtendScript 写入 <tempDir>/cmd_<id>.jsx
  2. CEP 插件（MCPBridgeCEP）轮询到后执行 evalScript()
  3. 结果写入 <tempDir>/res_<id>.json
  4. 轮询读取结果文件

使用方式：
    client = PRBridgeClient()
    await client.ping()  # 检测桥接是否在线
    await client.import_media(["C:/video.mp4"])
    await client.create_sequence("My Sequence")
    await client.add_to_timeline("video.mp4", track_index=0)
    await client.export_sequence("C:/output.mp4")
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# 桥接目录（与 CEP 插件配置一致）
BRIDGE_DIR = Path(
    os.environ.get(
        "PREMIERE_TEMP_DIR",
        r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\.premiere-mcp-bridge",
    )
)
POLL_INTERVAL = 0.1  # 轮询间隔（秒）
DEFAULT_TIMEOUT = 30.0  # 默认超时（秒）
EXPORT_TIMEOUT = 180.0  # 导出超时（秒）

# ExtendScript 助手函数（与 premiere-pro-mcp 一致）
HELPERS = """
var TICKS_PER_SECOND = 254016000000;

function __ticksToSeconds(ticks) {
  return parseFloat(ticks) / TICKS_PER_SECOND;
}

function __secondsToTicks(seconds) {
  return Math.round(parseFloat(seconds) * TICKS_PER_SECOND);
}

function __findSequence(name) {
  var project = app.project;
  for (var i = 0; i < project.sequences.numSequences; i++) {
    var seq = project.sequences[i];
    if (seq.name === name) return seq;
  }
  return null;
}

function __findProjectItem(name, rootItem) {
  if (!rootItem) rootItem = app.project.rootItem;
  for (var i = 0; i < rootItem.children.numItems; i++) {
    var item = rootItem.children[i];
    if (item.name === name) return item;
    if (item.type === 2) {
      var found = __findProjectItem(name, item);
      if (found) return found;
    }
  }
  return null;
}

function __result(data) {
  return JSON.stringify({ success: true, data: data });
}

function __error(msg) {
  return JSON.stringify({ success: false, error: String(msg) });
}
"""


class PRBridgeError(Exception):
    """PR 桥接通信错误。"""


class SequenceCreationError(PRBridgeError):
    """无法自动创建序列，需要用户手动创建。"""


class PRBridgeClient:
    """Premiere Pro 桥接客户端 — 支持双协议自动切换。

    协议1（CEP，自动启动）：
      - 写入 <bridgeDir>/cmd_<id>.jsx
      - CEP 插件 MCPBridgeCEP 自动轮询执行 evalScript()
      - 结果写入 <bridgeDir>/res_<id>.json
      - 无需手动操作

    协议2（Standalone JSX，需手动启动）：
      - 写入 <bridgeDir>/pr_command.json
      - pr_mcp_bridge.jsx 文件轮询监听器执行
      - 结果写入 <bridgeDir>/pr_result.json
      - 需要在 PR 中手动运行一次 pr_mcp_bridge.jsx
    """

    def __init__(self, bridge_dir: Optional[Path | str] = None):
        self._bridge_dir = Path(bridge_dir) if bridge_dir else BRIDGE_DIR
        self._bridge_dir.mkdir(parents=True, exist_ok=True)
        self._cmd_counter = 0
        self._bridge_ready = False
        self._preferred_protocol: str = "cep"  # cep | standalone | auto

    # ------------------------------------------------------------------
    # 底层通信 — 双协议自动切换
    # ------------------------------------------------------------------

    async def _send_script(
        self, script: str, timeout: float = DEFAULT_TIMEOUT
    ) -> dict[str, Any]:
        """发送 ExtendScript 到 PR 并等待结果。

        自动尝试 CEP 协议，超时后降级为 standalone JSX 协议。
        """
        if self._preferred_protocol == "cep":
            try:
                return await self._send_via_cep(script, timeout)
            except PRBridgeError:
                logger.warning("[PRBridge] CEP protocol failed, trying standalone JSX...")
                self._preferred_protocol = "standalone"
                return await self._send_via_standalone(script, timeout)
        elif self._preferred_protocol == "standalone":
            return await self._send_via_standalone(script, timeout)
        else:
            # auto: try CEP first, fallback to standalone
            try:
                return await self._send_via_cep(script, timeout)
            except PRBridgeError:
                logger.warning("[PRBridge] CEP protocol failed, trying standalone JSX...")
                return await self._send_via_standalone(script, timeout)

    async def _send_via_cep(
        self, script: str, timeout: float = DEFAULT_TIMEOUT
    ) -> dict[str, Any]:
        """通过 CEP 插件协议发送命令（cmd_<id>.jsx → res_<id>.json）。"""
        self._cmd_counter += 1
        cmd_id = f"{int(time.time() * 1000)}_{self._cmd_counter}"
        cmd_file = self._bridge_dir / f"cmd_{cmd_id}.jsx"
        res_file = self._bridge_dir / f"res_{cmd_id}.json"

        full_script = f"{HELPERS}\n(function(){{\ntry{{\n{script}\n}}catch(e){{\nreturn __error(e.toString());\n}}\n}})();"
        cmd_file.write_text(full_script, encoding="utf-8")
        logger.debug(f"[PRBridge] CEP: Sent cmd_{cmd_id}.jsx ({len(full_script)} chars)")

        return await self._poll_result(cmd_file, res_file, timeout, "CEP")

    async def _send_via_standalone(
        self, script: str, timeout: float = DEFAULT_TIMEOUT
    ) -> dict[str, Any]:
        """通过 Standalone JSX 协议发送命令（pr_command.json → pr_result.json）。"""
        cmd_file = self._bridge_dir / "pr_command.json"
        res_file = self._bridge_dir / "pr_result.json"

        # 清理旧结果文件
        try:
            if res_file.exists():
                res_file.unlink()
        except Exception:
            pass

        cmd_data = {
            "command": "executeScript",
            "script": script,
            "params": {},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        cmd_file.write_text(json.dumps(cmd_data, ensure_ascii=False), encoding="utf-8")
        logger.debug(f"[PRBridge] Standalone: Sent pr_command.json ({len(script)} chars)")

        return await self._poll_result(cmd_file, res_file, timeout, "Standalone")

    async def _poll_result(
        self, cmd_file: Path, res_file: Path, timeout: float, protocol: str
    ) -> dict[str, Any]:
        """轮询结果文件，支持 CEP 和 standalone 两种协议。"""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if res_file.exists():
                try:
                    raw = res_file.read_text(encoding="utf-8")
                    if raw and len(raw) > 2:
                        result = json.loads(raw)

                        # 清理文件（standalone 协议不删除 pr_command.json）
                        if protocol == "CEP":
                            try:
                                cmd_file.unlink(missing_ok=True)
                            except Exception:
                                pass
                        try:
                            res_file.unlink(missing_ok=True)
                        except Exception:
                            pass

                        # 统一结果格式
                        if isinstance(result, dict):
                            # CEP 协议: {success: true/false, data: ..., error: ...}
                            if result.get("success") is False:
                                raise PRBridgeError(result.get("error", "Unknown error"))
                            if result.get("success") is True:
                                return result
                            # Standalone 协议: {status: "success"/"error", result: ..., message: ...}
                            status = result.get("status")
                            if status == "success":
                                data = result.get("result")
                                if isinstance(data, str):
                                    try:
                                        data = json.loads(data)
                                    except (json.JSONDecodeError, TypeError):
                                        pass
                                return {"success": True, "data": data}
                            elif status == "error":
                                raise PRBridgeError(result.get("message", "Unknown error"))

                        return {"success": True, "data": result}
                except json.JSONDecodeError:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                except PRBridgeError:
                    raise
                except Exception as e:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

            await asyncio.sleep(POLL_INTERVAL)

        # 超时，清理
        try:
            if protocol == "CEP":
                cmd_file.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            res_file.unlink(missing_ok=True)
        except Exception:
            pass

        raise PRBridgeError(
            f"{protocol} protocol timeout after {timeout}s. "
            "For CEP: ensure Premiere Pro is running with MCP Bridge CEP plugin (Window > Extensions > MCP Bridge). "
            "For Standalone: run pr_mcp_bridge.jsx in Premiere (File > Scripts > Run Script File...)."
        )

    # ------------------------------------------------------------------
    # 桥接状态检测
    # ------------------------------------------------------------------

    async def ping(self) -> dict[str, Any]:
        """检测桥接是否在线。"""
        script = """
        return __result({
            pong: true,
            appName: app.appName,
            appVersion: app.version,
            project: app.project ? app.project.name : null,
            sequence: app.project && app.project.activeSequence ? app.project.activeSequence.name : null
        });
        """
        try:
            result = await self._send_script(script, timeout=5.0)
            self._bridge_ready = True
            return result
        except PRBridgeError as e:
            self._bridge_ready = False
            raise PRBridgeError(f"Bridge not responding: {e}")

    async def get_info(self) -> dict[str, Any]:
        """获取 PR 引擎信息。"""
        script = """
        var info = {
            appName: app.appName,
            appVersion: app.version,
            project: app.project ? app.project.name : null,
            projectPath: app.project && app.project.path ? app.project.path.fsName : null,
            sequences: [],
            binCount: 0
        };
        if (app.project) {
            info.binCount = app.project.rootItem.children.numItems;
            for (var i = 0; i < app.project.sequences.numSequences; i++) {
                info.sequences.push({
                    name: app.project.sequences[i].name,
                    videoTracks: app.project.sequences[i].videoTracks.numTracks,
                    audioTracks: app.project.sequences[i].audioTracks.numTracks
                });
            }
        }
        return __result(info);
        """
        return await self._send_script(script)

    # ------------------------------------------------------------------
    # 素材导入
    # ------------------------------------------------------------------

    async def import_media(
        self,
        file_paths: list[str],
        target_bin: Optional[str] = None,
        suppress_ui: bool = True,
    ) -> dict[str, Any]:
        """导入素材文件到项目。"""
        paths_js = ", ".join('"' + p.replace("\\", "\\\\") + '"' for p in file_paths)
        suppress = "true" if suppress_ui else "false"

        if target_bin:
            bin_lookup = (
                f'var targetBin = __findProjectItem("{target_bin}");'
                f'if (!targetBin) return __error("Bin not found: {target_bin}");'
            )
        else:
            bin_lookup = "var targetBin = app.project.rootItem;"

        script = f"""
        {bin_lookup}
        var filePaths = [{paths_js}];
        var importSuccess = app.project.importFiles(filePaths, {suppress}, targetBin, false);
        if (!importSuccess) return __error("Import failed");
        return __result({{ imported: filePaths.length, files: filePaths }});
        """
        return await self._send_script(script, timeout=60.0)

    # ------------------------------------------------------------------
    # 序列管理
    # ------------------------------------------------------------------

    async def create_sequence(self, name: str) -> dict[str, Any]:
        """创建新序列（安全分步探测 - 避免 ExtendScript 死锁）。

        已知问题：PR 2025 中 createNewSequence(name, presetName) 会死锁 ExtendScript 引擎。
        因此采用多策略：
          1. 检查已有序列，有则直接激活
          2. 尝试 createNewSequence(name, "") 空预设名
          3. 尝试 createNewSequence(name) 无预设名（PR 2025 报 "Not Enough Parameters"）
          4. 全失败则抛出 SequenceCreationError，引导用户手动创建
        """
        # 第一步：检查已有序列
        probe = f"""
        var info = {{}};
        try {{ info.seqCount = app.project.sequences.numSequences; }} catch(e) {{ info.seqCount = -1; }}
        if (info.seqCount > 0) {{
            info.existingNames = [];
            for (var i = 0; i < app.project.sequences.numSequences; i++) {{
                try {{ info.existingNames.push(app.project.sequences[i].name); }} catch(e) {{}}
            }}
        }}
        return __result(info);
        """
        probe_result = await self._send_script(probe, timeout=10.0)
        probe_data = probe_result.get("data", {})
        seq_count = probe_data.get("seqCount", -1)
        existing_names = probe_data.get("existingNames", [])

        # 如果有已有序列，直接激活第一个
        if seq_count and seq_count > 0:
            act_name = existing_names[0] if existing_names else name
            logger.info(f"[PRBridge] 使用已有序列: {act_name}")
            return await self.set_active_sequence(act_name)

        # 第二步：尝试创建新序列（多策略）
        logger.info("[PRBridge] 项目无序列，尝试创建新序列...")

        # 策略1: 空字符串预设名
        logger.info("[PRBridge] 策略1: createNewSequence(name, '')")
        try:
            result = await self._send_script(f"""
            try {{
                app.project.createNewSequence("{name}", "");
                var seq = app.project.activeSequence;
                if (!seq) {{
                    var allSeqs = app.project.sequences;
                    if (allSeqs.numSequences > 0) {{
                        seq = allSeqs[allSeqs.numSequences - 1];
                    }}
                }}
                if (seq) return __result({{created:true, name:seq.name}});
            }} catch(e) {{ }}
            return __error("Strategy1 failed");
            """, timeout=10.0)
            logger.info(f"[PRBridge] 策略1成功: {result}")
            return result
        except PRBridgeError:
            logger.warning("[PRBridge] 策略1失败，尝试策略2")

        # 策略2: 无预设名（PR 2025 可能报 "Not Enough Parameters"）
        logger.info("[PRBridge] 策略2: createNewSequence(name) 无预设名")
        try:
            result = await self._send_script(f"""
            try {{
                app.project.createNewSequence("{name}");
                var seq = app.project.activeSequence;
                if (!seq) {{
                    var allSeqs = app.project.sequences;
                    if (allSeqs.numSequences > 0) {{
                        seq = allSeqs[allSeqs.numSequences - 1];
                    }}
                }}
                if (seq) return __result({{created:true, name:seq.name}});
            }} catch(e) {{ }}
            return __error("Strategy2 failed");
            """, timeout=10.0)
            logger.info(f"[PRBridge] 策略2成功: {result}")
            return result
        except PRBridgeError:
            logger.warning("[PRBridge] 策略2失败")

        # 所有策略失败 - 抛出引导错误
        raise SequenceCreationError(
            "PR 2025 ExtendScript API 限制：无法自动创建序列。\n\n"
            "请手动在 Premiere Pro 中创建序列:\n"
            "  1. 在 PR 中点击: File > New > Sequence\n"
            f"  2. 选择任意预设（如 DSLR 1080p29.97），序列名设为 \"{name}\"\n"
            "  3. 点击 OK\n"
            "  4. 然后重新运行本脚本"
        )

    async def wait_for_sequence(
        self, name: str, timeout: float = 300.0, poll_interval: float = 2.0
    ) -> dict[str, Any]:
        """等待用户手动创建序列并激活。

        在无法自动创建序列时使用，轮询等待用户手动创建。
        """
        logger.info(f"[PRBridge] 等待用户手动创建序列 '{name}'（超时 {int(timeout)} 秒）...")
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            try:
                probe = f"""
                var info = {{}};
                try {{ info.seqCount = app.project.sequences.numSequences; }} catch(e) {{ info.seqCount = -1; }}
                if (info.seqCount > 0) {{
                    info.existingNames = [];
                    for (var i = 0; i < app.project.sequences.numSequences; i++) {{
                        try {{ info.existingNames.push(app.project.sequences[i].name); }} catch(e) {{}}
                    }}
                }}
                return __result(info);
                """
                result = await self._send_script(probe, timeout=5.0)
                data = result.get("data", {})
                seq_count = data.get("seqCount", -1)
                existing_names = data.get("existingNames", [])

                if seq_count and seq_count > 0:
                    # 找到匹配名称的序列，或有序列可用
                    act_name = name
                    if name in existing_names:
                        logger.info(f"[PRBridge] 找到匹配序列: {name}")
                    else:
                        act_name = existing_names[0]
                        logger.info(f"[PRBridge] 使用第一个可用序列: {act_name}")
                    return await self.set_active_sequence(act_name)

                elapsed = int(time.monotonic() - start)
                if elapsed % 10 == 0:
                    logger.info(f"  等待序列创建中... ({elapsed}s)")
                await asyncio.sleep(poll_interval)

            except PRBridgeError:
                await asyncio.sleep(poll_interval)

        raise PRBridgeError(
            f"等待序列创建超时 ({int(timeout)} 秒)。\n"
            f"请在 PR 中手动创建序列 '{name}' 后重试。"
        )

    async def set_active_sequence(self, name: str) -> dict[str, Any]:
        """设置活动序列。"""
        script = f"""
        var seq = __findSequence("{name}");
        if (!seq) return __error("Sequence not found: {name}");
        app.project.activeSequence = seq;
        return __result({{ activated: true, name: seq.name }});
        """
        return await self._send_script(script)

    # ------------------------------------------------------------------
    # 时间线操作
    # ------------------------------------------------------------------

    async def add_to_timeline(
        self,
        item_name: str,
        track_index: int = 0,
        start_seconds: float = 0,
        audio_track_index: int = 0,
    ) -> dict[str, Any]:
        """将项目素材添加到时间线。"""
        script = f"""
        var seq = app.project.activeSequence;
        if (!seq) return __error("No active sequence");

        var item = __findProjectItem("{item_name}");
        if (!item) return __error("Project item not found: {item_name}");

        var startTicks = __secondsToTicks({start_seconds}).toString();
        seq.insertClip(item, startTicks, {track_index}, {audio_track_index});

        return __result({{
            added: true, item: item.name,
            trackIndex: {track_index}, startSeconds: {start_seconds}
        }});
        """
        return await self._send_script(script)

    # ------------------------------------------------------------------
    # 转场
    # ------------------------------------------------------------------

    async def add_transition(
        self,
        transition_name: str,
        track_index: int,
        cut_point_seconds: float,
        duration_seconds: float = 1.0,
    ) -> dict[str, Any]:
        """在指定时间点添加视频转场。"""
        script = f"""
        app.enableQE();
        var qeSeq = qe.project.getActiveSequence();
        if (!qeSeq) return __error("No active sequence (QE)");

        var qeTrack = qeSeq.getVideoTrackAt({track_index});
        if (!qeTrack) return __error("Track not found");

        var transitionName = "{transition_name}";
        var transitionQE = null;

        try {{
            if (qe.project.getVideoTransitionByName) {{
                transitionQE = qe.project.getVideoTransitionByName(transitionName);
            }}
        }} catch(e1) {{}}

        if (!transitionQE) {{
            try {{
                var transitions = qe.project.getVideoTransitionList();
                for (var i = 0; i < transitions.numItems; i++) {{
                    if (transitions[i].name === transitionName) {{
                        transitionQE = transitions[i];
                        break;
                    }}
                }}
            }} catch(e2) {{}}
        }}

        if (!transitionQE) return __error("Transition not found: " + transitionName);

        var cutTicks = __secondsToTicks({cut_point_seconds}).toString();
        var durationTicks = __secondsToTicks({duration_seconds}).toString();

        qeTrack.addTransition(transitionQE, true, cutTicks, durationTicks, "0", false);

        return __result({{
            added: true, transition: transitionName,
            trackIndex: {track_index}, atSeconds: {cut_point_seconds},
            durationSeconds: {duration_seconds}
        }});
        """
        return await self._send_script(script)

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    async def export_sequence(
        self, output_path: str, preset_path: Optional[str] = None
    ) -> dict[str, Any]:
        """导出序列为视频文件。"""
        if preset_path:
            preset_code = f'var presetPath = "{preset_path.replace(chr(92), chr(92)+chr(92))}";'
        else:
            preset_code = """
            var presetPath = __findH264Preset();
            if (!presetPath) return __error("Could not locate a default H.264 preset.");
            """

        script = f"""
        var seq = app.project.activeSequence;
        if (!seq) return __error("No active sequence");

        var outputPath = "{output_path.replace(chr(92), chr(92)+chr(92))}";
        {preset_code}

        var exportResult = seq.exportAsMediaDirect(
            outputPath, presetPath, app.encoder.ENCODE_ENTIRE
        );

        return __result({{
            exported: true, outputPath: outputPath, presetUsed: presetPath
        }});
        """
        return await self._send_script(script, timeout=EXPORT_TIMEOUT)

    # ------------------------------------------------------------------
    # 实用工具
    # ------------------------------------------------------------------

    async def create_project(self, project_path: str) -> dict[str, Any]:
        """创建新项目。"""
        script = f"""
        var projFile = new File("{project_path.replace(chr(92), chr(92)+chr(92))}");
        app.newProject(projFile);
        return __result({{ created: true, path: project_path }});
        """
        return await self._send_script(script)

    async def save_project(self, project_path: Optional[str] = None) -> dict[str, Any]:
        """保存项目。"""
        if project_path:
            script = f"""
            var projFile = new File("{project_path.replace(chr(92), chr(92)+chr(92))}");
            app.project.saveAs(projFile);
            return __result({{ saved: true, path: project_path }});
            """
        else:
            script = """
            app.project.save();
            return __result({ saved: true });
            """
        return await self._send_script(script)


# ====================================================================
# 独立入口：启动 PR 并执行自动化工作流
# ====================================================================

async def auto_edit_workflow(
    media_files: list[str],
    output_path: str,
    sequence_name: str = "AutoEdit",
    transition_name: str = "Cross Dissolve",
    transition_duration: float = 0.5,
    project_path: Optional[str] = None,
) -> dict[str, Any]:
    """完整的 PR 自动化剪辑工作流。

    Args:
        media_files: 素材文件路径列表
        output_path: 输出视频文件路径
        sequence_name: 序列名称
        transition_name: 转场名称
        transition_duration: 转场时长（秒）
        project_path: 项目文件保存路径（可选）

    Returns:
        工作流执行结果
    """
    client = PRBridgeClient()
    results = {"steps": [], "success": False, "error": None}

    try:
        # 1. 检测桥接
        logger.info("[PR Workflow] 检测桥接连接...")
        ping_result = await client.ping()
        results["steps"].append({"step": "ping", "status": "ok", "data": ping_result})
        logger.info(f"[PR Workflow] 桥接在线: {ping_result}")

        # 2. 创建项目（如果没有项目）
        info = await client.get_info()
        if not info.get("data", {}).get("project"):
            if project_path:
                logger.info(f"[PR Workflow] 创建新项目: {project_path}")
                await client.create_project(project_path)
                results["steps"].append({"step": "create_project", "status": "ok"})
            else:
                logger.warning("[PR Workflow] PR 无活动项目，请手动创建项目后重试")
                results["error"] = "No active project in Premiere Pro"
                return results

        # 3. 导入素材
        logger.info(f"[PR Workflow] 导入 {len(media_files)} 个素材...")
        import_result = await client.import_media(media_files)
        results["steps"].append({"step": "import_media", "status": "ok", "data": import_result})
        logger.info(f"[PR Workflow] 素材导入完成: {import_result}")

        # 4. 创建序列（自动尝试，失败则引导用户手动创建）
        logger.info(f"[PR Workflow] 创建序列: {sequence_name}")
        try:
            seq_result = await client.create_sequence(sequence_name)
            results["steps"].append({"step": "create_sequence", "status": "ok", "data": seq_result})
            logger.info(f"[PR Workflow] 序列创建完成: {seq_result}")
        except SequenceCreationError as e:
            logger.warning(f"[PR Workflow] 无法自动创建序列: {e}")
            print()
            print("=" * 60)
            print("  需要手动创建序列")
            print("=" * 60)
            print()
            print("  PR 2025 ExtendScript API 限制，无法自动创建序列。")
            print("  请在 Premiere Pro 中手动操作:")
            print(f"    1. 点击: File > New > Sequence")
            print(f"    2. 选择任意预设（如 DSLR 1080p29.97）")
            print(f"    3. 序列名称设为: {sequence_name}")
            print(f"    4. 点击 OK")
            print()
            print(f"  脚本将在 5 秒后开始等待，最多等待 5 分钟...")
            print()
            await asyncio.sleep(5)
            seq_result = await client.wait_for_sequence(sequence_name, timeout=300.0)
            results["steps"].append({"step": "create_sequence", "status": "ok", "data": seq_result})
            logger.info(f"[PR Workflow] 用户已创建序列: {seq_result}")

        # 5. 将素材添加到时间线
        for i, media_file in enumerate(media_files):
            # 从路径提取文件名（用作项目素材名称）
            media_name = Path(media_file).name
            clip_start = i * 5.0  # 每个片段间隔 5 秒

            logger.info(f"[PR Workflow] 添加素材到时间线 [{i+1}/{len(media_files)}]: {media_name}")
            add_result = await client.add_to_timeline(
                item_name=media_name,
                track_index=0,
                start_seconds=clip_start,
            )
            results["steps"].append({
                "step": f"add_clip_{i}",
                "status": "ok",
                "data": add_result,
            })

            # 6. 添加转场（从第二个片段开始，在片段衔接处）
            if i > 0:
                cut_point = clip_start  # 当前片段的起始位置就是转场点
                logger.info(
                    f"[PR Workflow] 添加转场 [{i}/{len(media_files)-1}]: "
                    f"{transition_name} @ {cut_point}s"
                )
                trans_result = await client.add_transition(
                    transition_name=transition_name,
                    track_index=0,
                    cut_point_seconds=cut_point,
                    duration_seconds=transition_duration,
                )
                results["steps"].append({
                    "step": f"transition_{i}",
                    "status": "ok",
                    "data": trans_result,
                })

        # 7. 导出
        logger.info(f"[PR Workflow] 导出序列到: {output_path}")
        export_result = await client.export_sequence(output_path)
        results["steps"].append({"step": "export", "status": "ok", "data": export_result})
        logger.info(f"[PR Workflow] 导出完成: {export_result}")

        results["success"] = True
        return results

    except PRBridgeError as e:
        logger.error(f"[PR Workflow] 桥接错误: {e}")
        results["error"] = str(e)
        return results
    except Exception as e:
        logger.error(f"[PR Workflow] 未知错误: {e}")
        results["error"] = str(e)
        return results


if __name__ == "__main__":
    """命令行入口：测试 PR 桥接连接。"""
    import sys

    async def main():
        client = PRBridgeClient()
        print("=" * 60)
        print("PR Bridge Client - 连接测试")
        print("=" * 60)
        print(f"桥接目录: {client._bridge_dir}")
        print()

        try:
            print("正在检测桥接连接...")
            info = await client.get_info()
            print(f"✅ 桥接在线!")
            print(f"   PR 版本: {info.get('data', {}).get('appVersion', 'unknown')}")
            print(f"   项目: {info.get('data', {}).get('project', '无')}")
            seqs = info.get("data", {}).get("sequences", [])
            if seqs:
                print(f"   序列: {len(seqs)} 个")
                for s in seqs:
                    print(f"     - {s['name']} (V{s['videoTracks']} A{s['audioTracks']})")
            else:
                print("   序列: 无")
        except PRBridgeError as e:
            print(f"❌ 桥接离线: {e}")
            print()
            print("请确保:")
            print("  1. Premiere Pro 已启动")
            print("  2. MCP Bridge CEP 插件已自动运行")
            print("     (窗口 > 扩展 > MCP Bridge)")
            print(f"  3. 桥接目录存在: {client._bridge_dir}")
            sys.exit(1)

    asyncio.run(main())