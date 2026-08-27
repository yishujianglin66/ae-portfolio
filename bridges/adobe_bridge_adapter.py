"""
DEPRECATED - Adobe Bridge Adapter（已弃用）
====================================

.. deprecated::
    本模块属于自研 .ae-mcp-bridge 文件轮询协议栈，已整体弃用。
    AE MCP 已转向开源基线（after-effects-mcp + 原版 mcp-bridge-auto.jsx）。
    AU/PS 暂无开源替代，保留功能但不应新增依赖。
    参见: archive/deprecated_self_built_bridge/README.md

原始功能说明：
统一适配器，提供对所有 Adobe 应用（AE、PR、PS、AU）的统一访问接口。

核心功能：
- 应用检测（检测哪些 Adobe 应用正在运行）
- 统一命令发送接口（跨应用执行脚本）
- 应用间通信桥接
- 健康状态监控
- 自动路由（根据任务类型选择最佳应用）

设计目标：
- 单一入口点：AdobeBridgeAdapter
- 统一 API：所有应用使用相同的方法签名
- 透明路由：自动选择合适的应用执行任务
- 错误隔离：一个应用失败不影响其他应用

Usage:
    adapter = AdobeBridgeAdapter()
    
    # 检测应用状态
    status = adapter.get_app_status()
    
    # 向特定应用发送命令
    result = adapter.send_to_pr("getProjectInfo")
    result = adapter.send_to_ps("getDocumentInfo")
    
    # 统一执行（自动路由）
    result = adapter.execute_script("app.version", app="ae")
    
    # 批量操作
    results = adapter.batch_execute([
        {"app": "ae", "command": "ping"},
        {"app": "pr", "command": "ping"},
    ])
"""
from __future__ import annotations

import warnings as _warnings
_warnings.warn(
    "bridges.adobe_bridge_adapter 已弃用：自研 .ae-mcp-bridge 协议已弃用，"
    "AE MCP 已转向开源 after-effects-mcp 基线。",
    DeprecationWarning,
    stacklevel=2,
)

import logging
import time
import threading
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class AdobeApp(str, Enum):
    """Adobe 应用枚举。"""
    AE = "ae"
    PR = "pr"
    PS = "ps"
    AU = "au"


class AppStatus(str, Enum):
    """应用状态枚举。"""
    OFFLINE = "offline"
    ONLINE = "online"
    DEGRADED = "degraded"
    ERROR = "error"


class AppInfo:
    """应用信息。"""

    def __init__(self, app: AdobeApp, status: AppStatus, version: str = "",
                 last_check: float = 0.0, error: str = ""):
        self.app = app
        self.status = status
        self.version = version
        self.last_check = last_check
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app": self.app.value,
            "status": self.status.value,
            "version": self.version,
            "last_check": self.last_check,
            "error": self.error,
        }


class BatchResult:
    """批量操作结果。"""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.success_count = 0
        self.failure_count = 0
        self.total_time = 0.0

    def add_result(self, app: AdobeApp, success: bool, result: Dict[str, Any],
                   duration: float) -> None:
        self.results.append({
            "app": app.value,
            "success": success,
            "result": result,
            "duration": duration,
        })
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.total_time += duration

    def to_dict(self) -> Dict[str, Any]:
        return {
            "results": self.results,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_time": round(self.total_time, 2),
            "success_rate": round(
                (self.success_count / (self.success_count + self.failure_count)) * 100
                if (self.success_count + self.failure_count) > 0 else 0,
                2
            ),
        }


class AdobeBridgeAdapter:
    """Adobe Bridge 统一适配器。

    提供对所有 Adobe 应用的统一访问接口，支持：
    - 应用状态检测
    - 跨应用脚本执行
    - 批量操作
    - 健康监控
    - 自动路由
    """

    def __init__(
        self,
        ae_bridge_dir: Optional[str] = None,
        pr_bridge_dir: Optional[str] = None,
        ps_bridge_dir: Optional[str] = None,
        au_bridge_dir: Optional[str] = None,
        auto_detect: bool = True,
        health_check_interval: float = 30.0,
    ):
        """初始化 Adobe Bridge 适配器。

        Args:
            ae_bridge_dir: AE Bridge 目录
            pr_bridge_dir: PR Bridge 目录
            ps_bridge_dir: PS Bridge 目录
            au_bridge_dir: AU Bridge 目录
            auto_detect: 是否自动检测应用
            health_check_interval: 健康检查间隔（秒）
        """
        self._clients: Dict[AdobeApp, Any] = {}
        self._app_info: Dict[AdobeApp, AppInfo] = {}
        self._health_check_interval = health_check_interval
        self._health_check_running = False
        self._health_check_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        project_root = Path(__file__).resolve().parent.parent

        if ae_bridge_dir is None:
            ae_bridge_dir = str(project_root / ".ae-mcp-bridge")
        if pr_bridge_dir is None:
            pr_bridge_dir = str(project_root / ".pr-mcp-bridge")
        if ps_bridge_dir is None:
            ps_bridge_dir = str(project_root / ".ps-mcp-bridge")
        if au_bridge_dir is None:
            au_bridge_dir = str(project_root / ".au-mcp-bridge")

        self._bridge_dirs = {
            AdobeApp.AE: ae_bridge_dir,
            AdobeApp.PR: pr_bridge_dir,
            AdobeApp.PS: ps_bridge_dir,
            AdobeApp.AU: au_bridge_dir,
        }

        self._initialize_clients()

        if auto_detect:
            self.detect_all_apps()

            if health_check_interval > 0:
                self.start_health_monitor()

    def _initialize_clients(self) -> None:
        """初始化各应用的 Bridge 客户端。"""
        for app in AdobeApp:
            self._app_info[app] = AppInfo(app, AppStatus.OFFLINE)

        try:
            from ae.ae_mcp_client import AEMCPClient
            self._clients[AdobeApp.AE] = AEMCPClient(
                bridge_dir=self._bridge_dirs[AdobeApp.AE],
                enable_middleware=True,
            )
            logger.info("AE Bridge 客户端已初始化")
        except Exception as e:
            logger.warning(f"AE Bridge 客户端初始化失败: {e}")

        try:
            from bridges.pr_bridge_client import PRBridgeClient
            self._clients[AdobeApp.PR] = PRBridgeClient(
                bridge_dir=self._bridge_dirs[AdobeApp.PR],
                signature_enabled=False,
                auto_setup_middleware=True,
            )
            logger.info("PR Bridge 客户端已初始化")
        except Exception as e:
            logger.warning(f"PR Bridge 客户端初始化失败: {e}")

        try:
            from bridges.ps_bridge_client import PSBridgeClient
            self._clients[AdobeApp.PS] = PSBridgeClient(
                bridge_dir=self._bridge_dirs[AdobeApp.PS],
                signature_enabled=False,
            )
            logger.info("PS Bridge 客户端已初始化")
        except Exception as e:
            logger.warning(f"PS Bridge 客户端初始化失败: {e}")

        try:
            from bridges.au_bridge_client import AUBridgeClient
            self._clients[AdobeApp.AU] = AUBridgeClient(
                bridge_dir=self._bridge_dirs[AdobeApp.AU],
                signature_enabled=False,
            )
            logger.info("AU Bridge 客户端已初始化")
        except Exception as e:
            logger.warning(f"AU Bridge 客户端初始化失败: {e}")

    # ------------------------------------------------------------------------
    # 应用检测
    # ------------------------------------------------------------------------

    def detect_all_apps(self) -> Dict[AdobeApp, AppInfo]:
        """检测所有 Adobe 应用的状态。

        Returns:
            各应用状态信息字典
        """
        with self._lock:
            for app in AdobeApp:
                self._check_app_status(app)
        return self._app_info

    def _check_app_status(self, app: AdobeApp) -> None:
        """检查单个应用状态。"""
        client = self._clients.get(app)
        if not client:
            self._app_info[app] = AppInfo(
                app, AppStatus.ERROR, error="客户端未初始化"
            )
            return

        try:
            result = client.ping(timeout=3)
            if result.get("status") == "success":
                version = result.get("result", {}).get("version", "")
                self._app_info[app] = AppInfo(
                    app, AppStatus.ONLINE, version=version,
                    last_check=time.time()
                )
            else:
                self._app_info[app] = AppInfo(
                    app, AppStatus.DEGRADED, last_check=time.time(),
                    error=result.get("error", "未知错误")
                )
        except Exception as e:
            self._app_info[app] = AppInfo(
                app, AppStatus.OFFLINE, last_check=time.time(),
                error=str(e)
            )

    def get_app_status(self, app: Optional[AdobeApp] = None) -> Union[AppInfo, Dict[AdobeApp, AppInfo]]:
        """获取应用状态。

        Args:
            app: 应用类型（None 返回所有）

        Returns:
            应用状态信息
        """
        if app is not None:
            return self._app_info.get(app, AppInfo(app, AppStatus.OFFLINE))
        return self._app_info

    def is_app_online(self, app: AdobeApp) -> bool:
        """检查应用是否在线。

        Args:
            app: 应用类型

        Returns:
            是否在线
        """
        info = self.get_app_status(app)
        return info.status == AppStatus.ONLINE

    def get_online_apps(self) -> List[AdobeApp]:
        """获取所有在线的应用。

        Returns:
            在线应用列表
        """
        return [app for app, info in self._app_info.items() if info.status == AppStatus.ONLINE]

    # ------------------------------------------------------------------------
    # 命令发送（按应用）
    # ------------------------------------------------------------------------

    def send_to_ae(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """向 AE 发送命令。

        Args:
            command: 命令名称
            params: 命令参数
            timeout: 超时时间（秒）

        Returns:
            命令结果
        """
        return self._send_command(AdobeApp.AE, command, params, timeout, **kwargs)

    def send_to_pr(
        self,
        command: str,
        script: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """向 PR 发送命令。

        Args:
            command: 命令名称
            script: ExtendScript 代码
            timeout: 超时时间（秒）

        Returns:
            命令结果
        """
        return self._send_command(AdobeApp.PR, command, {"script": script} if script else None, timeout, **kwargs)

    def send_to_ps(
        self,
        command: str,
        script: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """向 PS 发送命令。

        Args:
            command: 命令名称
            script: ExtendScript 代码
            timeout: 超时时间（秒）

        Returns:
            命令结果
        """
        return self._send_command(AdobeApp.PS, command, {"script": script} if script else None, timeout, **kwargs)

    def send_to_au(
        self,
        command: str,
        script: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """向 AU 发送命令。

        Args:
            command: 命令名称
            script: ExtendScript 代码
            timeout: 超时时间（秒）

        Returns:
            命令结果
        """
        return self._send_command(AdobeApp.AU, command, {"script": script} if script else None, timeout, **kwargs)

    def _send_command(
        self,
        app: AdobeApp,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """向指定应用发送命令。"""
        client = self._clients.get(app)
        if not client:
            return {
                "status": "error",
                "error": f"{app.value} 客户端未初始化",
            }

        try:
            if app == AdobeApp.AE:
                result = client._execute(
                    command=command,
                    params=params,
                    ttl=timeout * 1000 if timeout else None,
                    **kwargs,
                )
                return {"status": "success", "result": result}
            else:
                cmd_kwargs = {}
                if params and "script" in params:
                    cmd_kwargs["script"] = params["script"]
                if timeout:
                    cmd_kwargs["timeout"] = timeout

                result = client.send_command(command, **cmd_kwargs)
                return result

        except Exception as e:
            logger.error(f"向 {app.value} 发送命令失败: {e}")
            self._app_info[app] = AppInfo(
                app, AppStatus.ERROR, last_check=time.time(), error=str(e)
            )
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------------
    # 统一执行接口
    # ------------------------------------------------------------------------

    def execute_script(
        self,
        script: str,
        app: Union[str, AdobeApp] = AdobeApp.AE,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """在指定应用中执行 ExtendScript 代码。

        Args:
            script: ExtendScript 代码
            app: 目标应用（"ae", "pr", "ps", "au" 或 AdobeApp 枚举）
            timeout: 超时时间（秒）

        Returns:
            执行结果
        """
        if isinstance(app, str):
            try:
                app_enum = AdobeApp(app.lower())
            except ValueError:
                return {"status": "error", "error": f"未知应用: {app}"}
        else:
            app_enum = app

        return self._send_command(app_enum, "execute_script", {"script": script}, timeout)

    def auto_route(
        self,
        task_type: str,
        script: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """根据任务类型自动选择最佳应用执行。

        任务路由规则：
        - video_edit / timeline: PR（Premiere Pro）
        - graphics / image: PS（Photoshop）
        - audio / sound: AU（Audition）
        - motion / effect / composition: AE（After Effects）

        Args:
            task_type: 任务类型
            script: ExtendScript 代码
            params: 命令参数

        Returns:
            执行结果
        """
        route_map = {
            "video_edit": AdobeApp.PR,
            "timeline": AdobeApp.PR,
            "cut": AdobeApp.PR,
            "sequence": AdobeApp.PR,
            "graphics": AdobeApp.PS,
            "image": AdobeApp.PS,
            "photo": AdobeApp.PS,
            "design": AdobeApp.PS,
            "audio": AdobeApp.AU,
            "sound": AdobeApp.AU,
            "mix": AdobeApp.AU,
            "motion": AdobeApp.AE,
            "effect": AdobeApp.AE,
            "composition": AdobeApp.AE,
            "animation": AdobeApp.AE,
            "render": AdobeApp.AE,
        }

        app = route_map.get(task_type, AdobeApp.AE)

        online_apps = self.get_online_apps()
        if app not in online_apps and online_apps:
            logger.warning(f"首选应用 {app.value} 离线，使用备选应用")
            app = online_apps[0]

        return self._send_command(app, "execute_script", {"script": script} if script else params)

    # ------------------------------------------------------------------------
    # 批量操作
    # ------------------------------------------------------------------------

    def batch_execute(
        self,
        tasks: List[Dict[str, Any]],
        parallel: bool = True,
    ) -> BatchResult:
        """批量执行多个命令。

        Args:
            tasks: 任务列表，每个任务包含 app、command、可选的 script 和 params
            parallel: 是否并行执行

        Returns:
            批量操作结果
        """
        result = BatchResult()

        if parallel:
            threads = []
            results = {}

            def _execute_task(task: Dict[str, Any], idx: int):
                app_str = task.get("app", "ae")
                try:
                    app = AdobeApp(app_str.lower())
                except ValueError:
                    results[idx] = (False, {"status": "error", "error": f"未知应用: {app_str}"}, 0)
                    return

                start_time = time.time()
                command = task.get("command", "execute_script")
                script = task.get("script")
                params = task.get("params")

                try:
                    if script:
                        cmd_result = self._send_command(app, command, {"script": script})
                    elif params:
                        cmd_result = self._send_command(app, command, params)
                    else:
                        cmd_result = self._send_command(app, command)
                    results[idx] = (True, cmd_result, time.time() - start_time)
                except Exception as e:
                    results[idx] = (False, {"status": "error", "error": str(e)}, time.time() - start_time)

            for idx, task in enumerate(tasks):
                t = threading.Thread(target=_execute_task, args=(task, idx))
                t.start()
                threads.append(t)

            for t in threads:
                t.join()

            for idx in range(len(tasks)):
                success, cmd_result, duration = results.get(idx, (False, {}, 0))
                app_str = tasks[idx].get("app", "ae")
                try:
                    app = AdobeApp(app_str.lower())
                except ValueError:
                    app = AdobeApp.AE
                result.add_result(app, success, cmd_result, duration)
        else:
            for task in tasks:
                app_str = task.get("app", "ae")
                try:
                    app = AdobeApp(app_str.lower())
                except ValueError:
                    app = AdobeApp.AE

                start_time = time.time()
                command = task.get("command", "execute_script")
                script = task.get("script")
                params = task.get("params")

                try:
                    if script:
                        cmd_result = self._send_command(app, command, {"script": script})
                    elif params:
                        cmd_result = self._send_command(app, command, params)
                    else:
                        cmd_result = self._send_command(app, command)
                    result.add_result(app, True, cmd_result, time.time() - start_time)
                except Exception as e:
                    result.add_result(app, False, {"status": "error", "error": str(e)}, time.time() - start_time)

        return result

    # ------------------------------------------------------------------------
    # 健康监控
    # ------------------------------------------------------------------------

    def start_health_monitor(self) -> None:
        """启动健康监控线程。"""
        if self._health_check_running:
            return

        self._health_check_running = True
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
        )
        self._health_check_thread.start()
        logger.info("健康监控已启动")

    def stop_health_monitor(self) -> None:
        """停止健康监控线程。"""
        self._health_check_running = False
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)
        logger.info("健康监控已停止")

    def _health_check_loop(self) -> None:
        """健康检查循环。"""
        while self._health_check_running:
            try:
                self.detect_all_apps()
                online_count = len(self.get_online_apps())
                logger.debug(f"健康检查完成: {online_count}/{len(AdobeApp)} 应用在线")
            except Exception as e:
                logger.error(f"健康检查异常: {e}")

            time.sleep(self._health_check_interval)

    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告。

        Returns:
            健康报告字典
        """
        online_apps = self.get_online_apps()
        offline_apps = [app for app in AdobeApp if app not in online_apps]

        return {
            "total_apps": len(AdobeApp),
            "online_count": len(online_apps),
            "offline_count": len(offline_apps),
            "online_apps": [app.value for app in online_apps],
            "offline_apps": [app.value for app in offline_apps],
            "app_status": {app.value: info.to_dict() for app, info in self._app_info.items()},
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------------
    # 客户端访问
    # ------------------------------------------------------------------------

    def get_client(self, app: AdobeApp) -> Optional[Any]:
        """获取指定应用的客户端实例。

        Args:
            app: 应用类型

        Returns:
            客户端实例（None 如果未初始化）
        """
        return self._clients.get(app)

    # ------------------------------------------------------------------------
    # 资源管理
    # ------------------------------------------------------------------------

    def close(self) -> None:
        """关闭所有客户端连接。"""
        self.stop_health_monitor()
        logger.info("Adobe Bridge 适配器已关闭")
