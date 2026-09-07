"""
pipeline/engine_task_dispatcher.py — 统一引擎任务调度器
======================================================

管理 Adobe/DaVinci 引擎的 下发→轮询→回收→重试 闭环。
所有旗舰管线的真实引擎调用通过此模块统一调度。

架构:
    EngineTaskDispatcher (通用基类)
      ├── AETaskDispatcher     (AE Bridge + aerender)
      ├── PRTaskDispatcher     (PR Bridge)
      ├── ResolveTaskDispatcher (DaVinci fuscript)
      └── AMETaskDispatcher    (AME Watch Folder / encoder)

用法::

    from pipeline.engine_task_dispatcher import get_dispatcher, ExecutionMode

    dispatcher = get_dispatcher("after_effects")
    if dispatcher.is_available():
        result = dispatcher.dispatch_script(jsx_code, timeout=60)
        # result.mode == ExecutionMode.NATIVE_BRIDGE
    else:
        # 降级到 FFmpeg
        pass
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
#  执行模式枚举
# ============================================================================

class ExecutionMode(Enum):
    """引擎执行模式（按优先级降序）"""
    NATIVE_BRIDGE = "native_bridge"       # 软件内真实执行（Bridge 在线）
    NATIVE_CLI = "native_cli"             # 命令行工具（aerender/fuscript）
    FFMPEG_EQUIVALENT = "ffmpeg_equiv"    # FFmpeg 等效处理（当前实现）
    MANUAL_FALLBACK = "manual"            # 生成 JSX/Lua 供用户手动执行


# ============================================================================
#  任务结果数据类
# ============================================================================

@dataclass
class TaskResult:
    """引擎任务执行结果"""
    success: bool
    mode: ExecutionMode
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_s: float = 0.0
    retries: int = 0
    engine_version: Optional[str] = None

    def to_manifest_dict(self) -> Dict[str, Any]:
        """转换为可写入 manifest.json 的字典"""
        d = {
            "execution_mode": self.mode.value,
            "engine_success": self.success,
            "duration_s": round(self.duration_s, 2),
            "retry_count": self.retries,
        }
        if self.engine_version:
            d["engine_version"] = self.engine_version
        if self.error:
            d["engine_error"] = self.error[:500]
        d.update(self.data)
        return d


# ============================================================================
#  通用 Bridge 调度器
# ============================================================================

class BridgeDispatcher:
    """文件轮询 Bridge 通用调度器（AE/PR 共用协议）

    协议:
        Python 写 {app}_command.json → JSX listener 轮询执行 → 写 {app}_result.json
    """

    def __init__(
        self,
        app_name: str,
        bridge_dir: Path,
        cmd_filename: str,
        res_filename: str,
        poll_interval: float = 0.3,
        default_timeout: float = 30.0,
        max_retries: int = 2,
    ):
        self.app_name = app_name
        self.bridge_dir = bridge_dir
        self.cmd_path = bridge_dir / cmd_filename
        self.res_path = bridge_dir / res_filename
        self.poll_interval = poll_interval
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self._cached_available: Optional[bool] = None
        self._cache_time: float = 0.0
        self._cache_ttl: float = 15.0

    # ------------------------------------------------------------------
    # 可用性检测
    # ------------------------------------------------------------------

    def is_available(self, force_check: bool = False) -> bool:
        """检测 Bridge 是否在线（带缓存）"""
        now = time.time()
        if not force_check and self._cached_available is not None:
            if (now - self._cache_time) < self._cache_ttl:
                return self._cached_available

        available = self._ping()
        self._cached_available = available
        self._cache_time = now
        return available

    def _ping(self) -> bool:
        """发送 ping 命令检测 Bridge 在线"""
        if not self.bridge_dir.exists():
            return False
        result = self._send_command_raw(
            command="ping",
            args={},
            timeout=5.0,
        )
        return result is not None and result.get("status") == "success"

    # ------------------------------------------------------------------
    # 脚本执行
    # ------------------------------------------------------------------

    def dispatch_script(
        self,
        script: str,
        timeout: Optional[float] = None,
        command: str = "runScript",
        args_key: str = "code",
    ) -> TaskResult:
        """通过 Bridge 执行脚本（带重试）

        Args:
            script: ExtendScript 代码
            timeout: 超时秒数
            command: Bridge 命令名 (AE: "runScript", PR: "executeScript")
            args_key: 脚本参数键名 (AE: "code", PR: "script")
        """
        timeout = timeout or self.default_timeout
        t0 = time.time()
        last_error = ""

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                logger.info(f"[{self.app_name}] Retry {attempt}/{self.max_retries}")
                time.sleep(1.0)

            # 构建命令
            if command == "runScript":
                # AE 协议: {command: "runScript", args: {code: "..."}}
                cmd_data = {
                    "command": command,
                    "args": {args_key: script},
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(time.time()*1000)%1000:03d}",
                    "processed": False,
                }
            else:
                # PR 协议: {command: "executeScript", script: "..."}
                cmd_data = {
                    "command": command,
                    "script": script,
                    "params": {},
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(time.time()*1000)%1000:03d}",
                }

            result = self._send_command_raw(cmd_data, timeout=timeout)

            if result is None:
                last_error = f"Bridge timeout ({timeout}s)"
                continue

            status = result.get("status")
            if status == "success":
                # 解析结果数据
                data = self._extract_result_data(result, command)
                return TaskResult(
                    success=True,
                    mode=ExecutionMode.NATIVE_BRIDGE,
                    data=data,
                    duration_s=time.time() - t0,
                    retries=attempt,
                )
            else:
                # 提取错误信息
                err = self._extract_error(result)
                last_error = err
                # 如果是脚本逻辑错误（非通信错误），不重试
                if "SCRIPT_ERROR" in err or "ATOM_SCRIPT_ERROR" in err:
                    break

        return TaskResult(
            success=False,
            mode=ExecutionMode.NATIVE_BRIDGE,
            error=last_error,
            duration_s=time.time() - t0,
            retries=self.max_retries,
        )

    # ------------------------------------------------------------------
    # 内部通信
    # ------------------------------------------------------------------

    def _send_command_raw(
        self,
        cmd_data: Optional[Dict] = None,
        command: Optional[str] = None,
        args: Optional[Dict] = None,
        timeout: float = 30.0,
    ) -> Optional[Dict]:
        """写入命令文件并轮询等待结果

        支持两种调用方式:
        1. 传入完整 cmd_data dict
        2. 传入 command + args 自动构建
        """
        if cmd_data is None:
            cmd_data = {
                "command": command,
                "args": args or {},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "processed": False,
            }

        # 清理旧结果
        try:
            if self.res_path.exists():
                self.res_path.unlink()
        except OSError:
            pass

        # 写入命令
        try:
            self.cmd_path.parent.mkdir(parents=True, exist_ok=True)
            self.cmd_path.write_text(
                json.dumps(cmd_data, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as e:
            logger.error(f"[{self.app_name}] Failed to write command: {e}")
            return None

        # 轮询结果
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(self.poll_interval)
            if self.res_path.exists():
                try:
                    text = self.res_path.read_text(encoding="utf-8")
                    if text and len(text) > 2:
                        data = json.loads(text)
                        # 清理结果文件
                        try:
                            self.res_path.unlink()
                        except OSError:
                            pass
                        return data
                except (json.JSONDecodeError, OSError):
                    continue

        return None

    def _extract_result_data(self, result: Dict, command: str) -> Dict[str, Any]:
        """从 Bridge 响应中提取有效数据"""
        # AE 协议: {command, status, result: {success, data: {result: "..."}}}
        result_obj = result.get("result", {})
        if isinstance(result_obj, dict):
            data = result_obj.get("data", {})
            if isinstance(data, dict):
                raw = data.get("result", "")
                # 尝试 JSON 解析脚本返回值
                if isinstance(raw, str):
                    try:
                        return json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        return {"raw_result": raw}
                return {"raw_result": str(raw)}
            return data
        # PR 协议: {status: "success", result: "..."}
        raw = result.get("result", "")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return {"raw_result": raw}
        return {"raw_result": str(raw)}

    def _extract_error(self, result: Dict) -> str:
        """从 Bridge 响应中提取错误信息"""
        result_obj = result.get("result", {})
        if isinstance(result_obj, dict):
            err = result_obj.get("error", {})
            if isinstance(err, dict):
                return err.get("message", str(err))
            return str(err) if err else result.get("error", "Unknown error")
        return result.get("error", result.get("message", "Unknown error"))


# ============================================================================
#  AE 专用调度器
# ============================================================================

class AETaskDispatcher(BridgeDispatcher):
    """After Effects 任务调度器

    支持:
    - Bridge 脚本执行（创建合成/图层/特效）
    - aerender CLI 渲染
    """

    def __init__(self):
        super().__init__(
            app_name="AE",
            bridge_dir=PROJECT_ROOT / ".ae-mcp-bridge",
            cmd_filename="ae_command.json",
            res_filename="ae_result.json",
            poll_interval=0.3,
            default_timeout=60.0,
            max_retries=2,
        )
        self._aerender_path: Optional[Path] = None

    def dispatch_script(self, script: str, timeout: Optional[float] = None, **kw) -> TaskResult:
        """AE 使用 runScript + args.code 协议"""
        return super().dispatch_script(
            script=script, timeout=timeout,
            command="runScript", args_key="code",
        )

    def find_aerender(self) -> Optional[Path]:
        """查找 aerender.exe 路径（使用全面自动探测）"""
        if self._aerender_path and self._aerender_path.exists():
            return self._aerender_path

        # 使用 ae_render_engine 的全面探测函数（注册表+多盘符+多版本）
        try:
            # 先尝试导入 ae_render_engine 的 detect_aerender
            rendering_dir = PROJECT_ROOT / "rendering"
            if str(rendering_dir) not in sys.path:
                sys.path.insert(0, str(rendering_dir))
            try:
                from ae_render_engine import detect_aerender
                detected = detect_aerender()
                if detected and detected.exists():
                    self._aerender_path = detected
                    return detected
            except Exception:
                pass
        except Exception:
            pass

        # 降级：硬编码候选（保留旧逻辑作为 fallback）
        candidates = [
            r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe",
            r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\aerender.exe",
            r"C:\Program Files\Adobe\Adobe After Effects 2023\Support Files\aerender.exe",
            r"C:\Program Files\Adobe\Adobe After Effects 2022\Support Files\aerender.exe",
            r"D:\AE25\Support Files\aerender.exe",
            r"D:\AE\2025\Support Files\aerender.exe",
            r"D:\Adobe\Adobe After Effects 2025\Support Files\aerender.exe",
        ]
        for c in candidates:
            p = Path(c)
            if p.exists():
                self._aerender_path = p
                return p

        # 尝试从 settings 获取
        try:
            pa_src = PROJECT_ROOT / "puppet-automation" / "src"
            if str(pa_src) not in sys.path:
                sys.path.insert(0, str(pa_src))
            from config import settings
            if settings.aerender_path and Path(settings.aerender_path).exists():
                self._aerender_path = Path(settings.aerender_path)
                return self._aerender_path
        except Exception:
            pass

        return None

    def dispatch_render(
        self,
        project_path: Path,
        comp_name: str,
        output_path: Path,
        output_module: str = "H.264 - Match Source - High bitrate",
        render_settings: str = "Best Settings",
        timeout: float = 600.0,
    ) -> TaskResult:
        """通过 aerender CLI 渲染合成（带模板 fallback 和错误诊断）

        Args:
            project_path: .aep 工程路径
            comp_name: 合成名称
            output_path: 输出文件路径
            output_module: 输出模块模板（如果失败会自动尝试候选列表）
            render_settings: 渲染设置模板
            timeout: 渲染超时（秒）
        """
        t0 = time.time()
        aerender = self.find_aerender()

        if not aerender:
            return TaskResult(
                success=False,
                mode=ExecutionMode.NATIVE_CLI,
                error="aerender.exe not found (检查AE安装路径或设置AEKV_AERENDER_PATH环境变量)",
                duration_s=time.time() - t0,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 从 ae_render_engine 导入模板候选表
        try:
            rendering_dir = PROJECT_ROOT / "rendering"
            if str(rendering_dir) not in sys.path:
                sys.path.insert(0, str(rendering_dir))
            from ae_render_engine import OM_TEMPLATES, RS_TEMPLATES, parse_aerender_error
        except Exception:
            OM_TEMPLATES = {}
            RS_TEMPLATES = {}
            parse_aerender_error = None

        # 推断输出格式，获取候选模板列表
        # 修复：suffix 曾 lstrip('.') 后与 fmt_map 带点键永不匹配，
        # 导致 .mov 误用 h264 候选表，逐个试探不可用模板浪费数分钟/comp
        suffix = output_path.suffix.lower()
        fmt_map = {".mp4": "h264", ".mov": "mov", ".png": "png_seq", ".tif": "tiff_seq", ".tiff": "tiff_seq", ".exr": "exr_seq"}
        fmt = fmt_map.get(suffix, "h264")

        # 构建 OM 模板候选列表：先尝试用户指定的，再从候选表尝试
        om_candidates = [output_module]
        if fmt in OM_TEMPLATES:
            for tmpl in OM_TEMPLATES[fmt]:
                if tmpl not in om_candidates:
                    om_candidates.append(tmpl)
        # 最后尝试不加模板
        om_candidates.append(None)

        # RS 模板候选
        rs_candidates = [render_settings]
        if "best" in RS_TEMPLATES:
            for tmpl in RS_TEMPLATES["best"]:
                if tmpl not in rs_candidates:
                    rs_candidates.append(tmpl)
        rs_candidates.append(None)

        logger.info(f"[AE] aerender: {comp_name} → {output_path.name}")

        last_proc = None
        last_err = ""

        # 按候选模板依次尝试
        # 修复：zip 按短列表截断，om_candidates 更长时末尾 None 兜底永不执行，
        # 导致中文 AE 实例（命名模板均不可用）无法降级到默认输出模块
        for attempt_idx, (om_tmpl, rs_tmpl) in enumerate(
            itertools.zip_longest(om_candidates, rs_candidates)
        ):
            cmd = [str(aerender), "-project", str(project_path), "-comp", comp_name, "-output", str(output_path)]
            if om_tmpl:
                cmd.extend(["-OMtemplate", om_tmpl])
            if rs_tmpl:
                cmd.extend(["-RStemplate", rs_tmpl])
            cmd.extend([
                "-close", "DO_NOT_SAVE_CHANGES",
                "-continueOnMissingFootage",
                "-v", "ERRORS_AND_PROGRESS",
            ])

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True, text=True, errors='replace',
                    timeout=timeout,
                    cwd=str(PROJECT_ROOT),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                last_proc = proc

                # 等待文件写入完成
                if proc.returncode == 0:
                    for _ in range(8):
                        if output_path.exists():
                            try:
                                s1 = output_path.stat().st_size
                                time.sleep(0.5)
                                s2 = output_path.stat().st_size
                                if s1 == s2 and s1 > 1024:
                                    break
                            except Exception:
                                pass
                        time.sleep(0.5)

                # 修复：无 OM 模板时 aerender 会忽略 -output，按工程默认
                # 输出设置写到同目录的其它扩展名文件（如 .avi）；
                # 探测同 stem 兄弟文件并归位到期望路径
                if proc.returncode == 0 and not (
                    output_path.exists() and output_path.stat().st_size > 1024
                ):
                    siblings = sorted(
                        (p for p in output_path.parent.glob(f"{output_path.stem}.*")
                         if p != output_path and p.stat().st_size > 1024),
                        key=lambda p: p.stat().st_mtime, reverse=True,
                    )
                    if siblings:
                        try:
                            siblings[0].replace(output_path)
                            logger.info(
                                f"[AE] aerender 输出归位: {siblings[0].name} → {output_path.name}"
                            )
                        except Exception as mv_e:
                            logger.warning(f"[AE] 输出归位失败: {mv_e}")

                if proc.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
                    duration = time.time() - t0
                    return TaskResult(
                        success=True,
                        mode=ExecutionMode.NATIVE_CLI,
                        data={
                            "render_engine": "aerender",
                            "output_size_kb": round(output_path.stat().st_size / 1024, 1),
                            "comp_name": comp_name,
                            "om_template_used": om_tmpl or "(default)",
                            "rs_template_used": rs_tmpl or "(default)",
                            "attempt": attempt_idx + 1,
                        },
                        duration_s=duration,
                    )

                # 判断是否是模板错误，是的话继续尝试下一个候选
                stdout_lower = (proc.stdout or "").lower()
                stderr_lower = (proc.stderr or "").lower()
                is_template_error = (
                    "output module template" in stdout_lower + stderr_lower
                    or "render settings template" in stdout_lower + stderr_lower
                    or ("not found" in stdout_lower + stderr_lower and "template" in stdout_lower + stderr_lower)
                )
                last_err = (proc.stdout or "")[-600:] + (proc.stderr or "")[-200:]

                if is_template_error and om_tmpl is not None:
                    logger.warning(f"[AE] 模板 '{om_tmpl}' 不可用，尝试下一个候选...")
                    continue
                else:
                    # 不是模板错误，不再重试模板
                    break

            except subprocess.TimeoutExpired:
                return TaskResult(
                    success=False, mode=ExecutionMode.NATIVE_CLI,
                    error=f"aerender timeout ({timeout}s)",
                    duration_s=time.time() - t0,
                )
            except Exception as e:
                last_err = str(e)
                break

        # 所有尝试都失败
        duration = time.time() - t0
        diag = last_err
        if parse_aerender_error and last_proc is not None:
            err_msg, err_code, suggestion = parse_aerender_error(
                last_proc.stdout or "", last_proc.stderr or "", last_proc.returncode
            )
            diag = f"{err_msg}"
            if suggestion:
                diag += f" | 建议: {suggestion}"

        return TaskResult(
            success=False,
            mode=ExecutionMode.NATIVE_CLI,
            error=f"aerender failed: {diag[:800]}",
            duration_s=duration,
        )


# ============================================================================
#  PR 专用调度器
# ============================================================================

class PRTaskDispatcher(BridgeDispatcher):
    """Premiere Pro 任务调度器"""

    def __init__(self):
        super().__init__(
            app_name="PR",
            bridge_dir=PROJECT_ROOT / ".premiere-mcp-bridge",
            cmd_filename="pr_command.json",
            res_filename="pr_result.json",
            poll_interval=0.3,
            default_timeout=120.0,
            max_retries=2,
        )

    def dispatch_script(self, script: str, timeout: Optional[float] = None, **kw) -> TaskResult:
        """PR 使用 executeScript + script 字段协议"""
        return super().dispatch_script(
            script=script, timeout=timeout,
            command="executeScript", args_key="script",
        )


# ============================================================================
#  DaVinci Resolve 专用调度器
# ============================================================================

class ResolveTaskDispatcher:
    """DaVinci Resolve 任务调度器（通过 fuscript.exe 或 Python API）"""

    def __init__(self):
        self.app_name = "Resolve"
        self._resolve_available: Optional[bool] = None
        self._cache_time: float = 0.0
        self._engine = None

    def is_available(self, force_check: bool = False) -> bool:
        """检测 DaVinci Resolve 是否可用"""
        now = time.time()
        if not force_check and self._resolve_available is not None:
            if (now - self._cache_time) < 15.0:
                return self._resolve_available

        available = self._check_resolve()
        self._resolve_available = available
        self._cache_time = now
        return available

    def _check_resolve(self) -> bool:
        """检测 Resolve 是否运行 + API 可连接"""
        # 检查进程
        try:
            result = subprocess.run(
                ["tasklist"], capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="replace"
            )
            if "resolve" not in result.stdout.lower():
                return False
        except Exception:
            return False

        # 尝试连接 API（先设置环境变量确保 DaVinciResolveScript 可导入）
        try:
            engine = self._get_engine()
            if engine:
                # 使用正确的存活检查方法名
                if hasattr(engine, "_check_resolve_alive"):
                    return engine._check_resolve_alive()
                # 如果引擎初始化成功且 Resolve 进程运行中，视为可用
                return True
        except Exception:
            pass

        return False

    def _get_engine(self):
        """获取 ResolveColorEngine 实例"""
        if self._engine is None:
            try:
                import os
                import sys
                # 设置 DaVinci Resolve Scripting API 环境变量
                resolve_api_path = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules"
                if os.path.exists(resolve_api_path) and resolve_api_path not in sys.path:
                    sys.path.insert(0, resolve_api_path)
                os.environ.setdefault("RESOLVE_SCRIPT_API", resolve_api_path)

                if str(PROJECT_ROOT) not in sys.path:
                    sys.path.insert(0, str(PROJECT_ROOT))
                from integrations.davinci_fuscript import ResolveColorEngine
                self._engine = ResolveColorEngine()
            except Exception as e:
                logger.debug(f"[Resolve] Engine init failed: {e}")
        return self._engine

    def dispatch_grade(
        self,
        input_paths: List[Path],
        output_dir: Path,
        preset: str = "cinematic",
        node_count: int = 4,
        timeout: float = 300.0,
    ) -> TaskResult:
        """通过 Resolve 执行调色渲染

        Args:
            input_paths: 输入视频文件列表
            output_dir: 输出目录
            preset: 调色预设名
            node_count: 期望节点数
            timeout: 超时
        """
        t0 = time.time()

        try:
            engine = self._get_engine()
            if not engine:
                return TaskResult(
                    success=False,
                    mode=ExecutionMode.NATIVE_CLI,
                    error="ResolveColorEngine unavailable",
                    duration_s=time.time() - t0,
                )

            # 使用 quick_grade 对第一个输入执行调色
            result = engine.quick_grade(
                str(input_paths[0]),
                preset=preset,
                output_dir=str(output_dir),
            )

            duration = time.time() - t0

            if result.success and result.output_path:
                return TaskResult(
                    success=True,
                    mode=ExecutionMode.NATIVE_CLI,
                    data={
                        "resolve_used": True,
                        "preset": preset,
                        "output_path": result.output_path,
                        "clips_graded": result.clips_graded,
                        "render_complete": result.render_complete,
                        "nodes": node_count,
                        "has_lut": True,
                    },
                    duration_s=duration,
                )
            else:
                return TaskResult(
                    success=False,
                    mode=ExecutionMode.NATIVE_CLI,
                    error=f"Resolve grade failed: {result.errors}",
                    duration_s=duration,
                )
        except Exception as e:
            return TaskResult(
                success=False,
                mode=ExecutionMode.NATIVE_CLI,
                error=f"Resolve exception: {e}",
                duration_s=time.time() - t0,
            )


# ============================================================================
#  AME 专用调度器
# ============================================================================

class AMETaskDispatcher:
    """Adobe Media Encoder 任务调度器"""

    def __init__(self):
        self.app_name = "AME"
        self._ame_available: Optional[bool] = None
        self._cache_time: float = 0.0
        self.watch_folder = PROJECT_ROOT / "output" / "me_watch_folder"

    # ------------------------------------------------------------------
    # 安装检测（修复：历史上仅靠进程探测，已安装未运行即误报“未安装”）
    # ------------------------------------------------------------------

    def find_exe(self) -> Optional[Path]:
        """发现 AME exe 路径（环境变量/候选路径/快捷方式/注册表）"""
        try:
            from core.adobe_discovery import find_adobe_exe
            return find_adobe_exe("media_encoder")
        except Exception as e:
            logger.warning(f"[AME] 安装检测异常: {e}")
            return None

    def is_installed(self) -> bool:
        """AME 是否已安装（真实安装检测，非进程探测）"""
        return self.find_exe() is not None

    def ensure_running(self, timeout: float = 90.0) -> bool:
        """确保 AME 进程运行：已运行直接返回，已安装未运行则自动拉起"""
        if self._check_ame_process():
            return True
        ame_exe = self.find_exe()
        if ame_exe is None:
            logger.warning("[AME] 未检测到安装（环境变量/候选路径/快捷方式/注册表均未命中）")
            return False
        logger.info(f"[AME] 已安装但未运行，自动启动: {ame_exe}")
        try:
            subprocess.Popen(
                [str(ame_exe)],
                cwd=str(ame_exe.parent),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.error(f"[AME] 启动失败: {e}")
            return False
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._check_ame_process():
                logger.info("[AME] 进程已就绪")
                return True
            time.sleep(2.0)
        logger.warning(f"[AME] 启动超时（{timeout}s）")
        return False

    def is_available(self, force_check: bool = False) -> bool:
        """检测 AME 是否可用（进程运行中，或已安装可拉起）"""
        now = time.time()
        if not force_check and self._ame_available is not None:
            if (now - self._cache_time) < 15.0:
                return self._ame_available

        available = self._check_ame_process() or self.is_installed()
        self._ame_available = available
        self._cache_time = now
        return available

    def _check_ame_process(self) -> bool:
        """检测 AME 进程"""
        try:
            result = subprocess.run(
                ["tasklist"], capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="replace"
            )
            return "adobe media encoder" in result.stdout.lower()
        except Exception:
            return False

    def dispatch_encode(
        self,
        input_path: Path,
        output_path: Path,
        preset: str = "H.264 Match Source - High bitrate",
        timeout: float = 600.0,
    ) -> TaskResult:
        """通过 AME Watch Folder 或 PR encoder 编码

        优先尝试 PR Bridge 的 app.encoder，降级到 Watch Folder。
        """
        t0 = time.time()

        # 方式A: 通过 PR Bridge 的 encoder API
        pr_dispatcher = PRTaskDispatcher()
        if pr_dispatcher.is_available():
            jsx = f"""
            (function() {{
                try {{
                    var seq = app.project.activeSequence;
                    if (!seq) return JSON.stringify({{status: "error", message: "No active sequence"}});
                    var outPath = {json.dumps(str(output_path.resolve()).replace(chr(92), '/'))};
                    var preset = {json.dumps(preset)};
                    app.encoder.encodeSequence(seq, outPath, preset, 0);
                    app.encoder.startBatch();
                    return JSON.stringify({{status: "success", method: "pr_encoder", output: outPath}});
                }} catch(e) {{
                    return JSON.stringify({{status: "error", message: e.toString()}});
                }}
            }})();
            """
            result = pr_dispatcher.dispatch_script(jsx, timeout=60)
            if result.success:
                # 等待编码完成（轮询输出文件）
                encode_done = self._wait_for_output(output_path, timeout)
                if encode_done:
                    return TaskResult(
                        success=True,
                        mode=ExecutionMode.NATIVE_BRIDGE,
                        data={
                            "encoding_tool": "ame",
                            "method": "pr_encoder_api",
                            "output_size_mb": round(output_path.stat().st_size / 1024 / 1024, 2),
                        },
                        duration_s=time.time() - t0,
                    )

        # 方式B: Watch Folder（已安装未运行时自动拉起 AME）
        if self.ensure_running():
            wf_result = self._encode_via_watch_folder(input_path, output_path, timeout)
            if wf_result.success:
                return wf_result

        installed = self.is_installed()
        return TaskResult(
            success=False,
            mode=ExecutionMode.NATIVE_BRIDGE,
            error=(
                "AME not available (no PR encoder, AME 启动失败)"
                if installed else
                "AME not installed (环境变量/候选路径/快捷方式/注册表均未命中，"
                "可设 AEKV_ADOBE_AME_PATH 指向 exe)"
            ),
            duration_s=time.time() - t0,
        )

    def _wait_for_output(self, output_path: Path, timeout: float) -> bool:
        """轮询等待输出文件稳定"""
        deadline = time.time() + timeout
        last_size = -1
        stable_count = 0

        while time.time() < deadline:
            time.sleep(2.0)
            if output_path.exists():
                size = output_path.stat().st_size
                if size > 0 and size == last_size:
                    stable_count += 1
                    if stable_count >= 3:  # 连续 3 次大小不变 = 完成
                        return True
                else:
                    stable_count = 0
                last_size = size

        return output_path.exists() and output_path.stat().st_size > 0

    def _encode_via_watch_folder(
        self, input_path: Path, output_path: Path, timeout: float
    ) -> TaskResult:
        """Watch Folder 编码"""
        import shutil

        t0 = time.time()
        self.watch_folder.mkdir(parents=True, exist_ok=True)

        # 复制输入到 watch folder
        wf_input = self.watch_folder / input_path.name
        try:
            shutil.copy2(str(input_path), str(wf_input))
        except OSError as e:
            return TaskResult(
                success=False,
                mode=ExecutionMode.NATIVE_CLI,
                error=f"Watch folder copy failed: {e}",
                duration_s=time.time() - t0,
            )

        # 等待 AME 处理（检测输出文件）
        # AME Watch Folder 输出到同目录的 "output" 子文件夹
        wf_output_dir = self.watch_folder / "output"
        wf_output_dir.mkdir(exist_ok=True)

        # 轮询等待
        done = self._wait_for_output(output_path, timeout)
        if done:
            return TaskResult(
                success=True,
                mode=ExecutionMode.NATIVE_CLI,
                data={
                    "encoding_tool": "ame",
                    "method": "watch_folder",
                    "output_size_mb": round(output_path.stat().st_size / 1024 / 1024, 2),
                },
                duration_s=time.time() - t0,
            )

        return TaskResult(
            success=False,
            mode=ExecutionMode.NATIVE_CLI,
            error=f"Watch folder timeout ({timeout}s)",
            duration_s=time.time() - t0,
        )


# ============================================================================
#  调度器工厂
# ============================================================================

_dispatchers: Dict[str, Any] = {}


def get_dispatcher(engine_name: str) -> Any:
    """获取指定引擎的任务调度器（单例）

    Args:
        engine_name: "after_effects" | "premiere" | "davinci" | "media_encoder"

    Returns:
        对应的调度器实例
    """
    if engine_name not in _dispatchers:
        if engine_name == "after_effects":
            _dispatchers[engine_name] = AETaskDispatcher()
        elif engine_name == "premiere":
            _dispatchers[engine_name] = PRTaskDispatcher()
        elif engine_name == "davinci":
            _dispatchers[engine_name] = ResolveTaskDispatcher()
        elif engine_name == "media_encoder":
            _dispatchers[engine_name] = AMETaskDispatcher()
        else:
            raise ValueError(f"Unknown engine: {engine_name}")
    return _dispatchers[engine_name]


def detect_all_engines() -> Dict[str, Dict[str, Any]]:
    """检测所有引擎可用性（区分 运行中 / 已安装 / 未安装）"""
    status: Dict[str, Dict[str, Any]] = {}
    for name in ("after_effects", "premiere", "davinci", "media_encoder"):
        entry: Dict[str, Any] = {"running": False, "installed": False}
        try:
            d = get_dispatcher(name)
            entry["running"] = bool(d.is_available())
            if name == "media_encoder":
                entry["installed"] = d.is_installed()
                entry["exe_path"] = str(d.find_exe() or "")
            else:
                try:
                    from core.adobe_discovery import find_adobe_exe
                    exe = find_adobe_exe(name)
                    entry["installed"] = exe is not None
                    entry["exe_path"] = str(exe or "")
                except Exception:
                    entry["installed"] = entry["running"]
        except Exception:
            pass
        status[name] = entry
    return status
