"""引擎看门狗（Plan B / P0-2）

目标：让旗舰管线在 Adobe 引擎（AE / PR / Resolve / AME）Bridge 中途掉线或
假死时能够自愈——杀掉无响应的进程树并自动重启——而非静默降级到
ffmpeg_equiv 产物。

设计约束（稳定性优先，绝不影响主流程）：
- 纯新增模块，不修改现有引擎 / 编排逻辑；只被 flagship_runner._ensure_ae_bridge_ready 调用。
- 所有外部调用包裹 try/except，看门狗自身故障绝不能拖垮主流程。
- 常驻巡检线程默认关闭，由环境变量 AEKV_WATCHDOG=1 开启，避免与管线启动争抢。
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("engine_watchdog")

# 引擎名 -> 进程名（用于 tasklist / pgrep 探测与按名杀树）
ENGINE_PROCESS_NAME = {
    "after_effects": "afterfx.exe",
    "premiere": "premiere pro.exe",
    "resolve": "resolve.exe",
    "media_encoder": "adobe media encoder.exe",
}

_WATCHDOG_THREAD: threading.Thread | None = None
_WATCHDOG_STOP = threading.Event()


# ============================================================================
# 健康注册表 + 资源配额（P3：健康常态化 + 背压）
# ============================================================================

@dataclass
class _EngineState:
    status: str = "unknown"            # unknown|healthy|dead|launching
    last_seen_healthy_ts: float = 0.0
    last_error: str = ""
    launch_in_progress: bool = False
    updated_ts: float = 0.0


class EngineHealthRegistry:
    """线程安全的引擎健康注册表（看门狗 / 编排器共享的唯一事实源）。

    解决缺陷矩阵『无 supervisor/watchdog，引擎掉线靠人工』与 P0-2 发现的
    『瞬时探测失败 + 并发双拉起』竞态：所有拉起 / 探活结果统一写入此表，
    编排与看门狗据此做 go/no-go，避免重复拉起；也为 manifest/events 提供
    可被观测的健康视图（健康常态化）。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._states: dict[str, _EngineState] = {}

    def _state(self, name: str) -> _EngineState:
        s = self._states.get(name)
        if s is None:
            s = _EngineState()
            self._states[name] = s
        return s

    def mark_launch_started(self, name: str) -> None:
        with self._lock:
            s = self._state(name)
            s.launch_in_progress = True
            s.status = "launching"
            s.updated_ts = time.time()

    def mark_launch_done(self, name: str, ok: bool) -> None:
        with self._lock:
            s = self._state(name)
            s.launch_in_progress = False
            s.status = "healthy" if ok else "dead"
            s.updated_ts = time.time()

    def mark_healthy(self, name: str) -> None:
        with self._lock:
            s = self._state(name)
            s.status = "healthy"
            s.last_seen_healthy_ts = time.time()
            s.launch_in_progress = False
            s.updated_ts = time.time()

    def mark_dead(self, name: str, err: str = "") -> None:
        with self._lock:
            s = self._state(name)
            s.status = "dead"
            s.last_error = err
            s.launch_in_progress = False
            s.updated_ts = time.time()

    def is_launch_in_progress(self, name: str) -> bool:
        with self._lock:
            return self._state(name).launch_in_progress

    def get(self, name: str) -> dict:
        with self._lock:
            s = self._state(name)
            return {
                "status": s.status,
                "last_seen_healthy_ts": s.last_seen_healthy_ts,
                "last_error": s.last_error,
                "launch_in_progress": s.launch_in_progress,
                "updated_ts": s.updated_ts,
            }

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return {k: dict(self._state(k).__dict__) for k in self._states}


ENGINE_HEALTH = EngineHealthRegistry()


class ResourceQuota:
    """引擎资源配额（背压）：同引擎互斥 + 全局并发上限。

    固件视角：多引擎（AE / PR / Resolve）抢 GPU/CPU 属『无资源隔离 / 背压』缺陷。
    此处以信号量限全局并发、以每引擎锁防同引擎并发双拉起；超额时 fail-fast
    （返回 False），由调用方按 P1 八类策略处理，而非野蛮抢占。
    """

    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self._sem = threading.Semaphore(max_concurrent)
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()
        self._active = 0
        self._active_lock = threading.Lock()

    def _lock_for(self, name: str) -> threading.RLock:
        with self._locks_guard:
            lk = self._locks.get(name)
            if lk is None:
                lk = threading.RLock()
                self._locks[name] = lk
            return lk

    def acquire_engine(self, name: str, timeout: float = 5.0) -> bool:
        # 全局并发上限（背压：超过 max_concurrent 个引擎同时操作则拒绝）
        if not self._sem.acquire(blocking=True, timeout=timeout):
            return False
        # 同引擎互斥（防 watchdog / 编排器并发双拉起）
        if not self._lock_for(name).acquire(blocking=True, timeout=timeout):
            self._sem.release()
            return False
        with self._active_lock:
            self._active += 1
        return True

    def release_engine(self, name: str) -> None:
        with self._active_lock:
            if self._active > 0:
                self._active -= 1
        try:
            self._lock_for(name).release()
        except Exception:
            pass
        try:
            self._sem.release()
        except Exception:
            pass

    def status(self) -> dict:
        with self._active_lock:
            active = self._active
        return {
            "max_concurrent": self.max_concurrent,
            "active": active,
            "available": max(0, self.max_concurrent - active),
        }


ENGINE_QUOTA = ResourceQuota()


def get_engine_health(engine_name: str) -> dict:
    """取某引擎当前健康快照（观测层统一入口）。"""
    return ENGINE_HEALTH.get(engine_name)


def all_engine_health() -> dict[str, dict]:
    """取全部已登记引擎健康快照。"""
    return ENGINE_HEALTH.snapshot()


def quota_status() -> dict:
    """取资源配额当前占用。"""
    return ENGINE_QUOTA.status()


def engine_health_metrics_prometheus() -> str:
    """导出 Prometheus 文本格式的健康 / 配额指标（零依赖，供网关 /metrics 复用）。

    指标：
      engine_health_up{engine=...}                     1=healthy 0=其它
      engine_health_last_seen_healthy_ts{engine=...}   最近一次健康探针 unix ts（0=从未）
      engine_quota_max_concurrent / active / available
    """
    up_map = {"healthy": 1, "launching": 0, "dead": 0, "unknown": 0}
    snap = ENGINE_HEALTH.snapshot()
    lines = [
        "# HELP engine_health_up Whether the engine passed its last health check (1=healthy).",
        "# TYPE engine_health_up gauge",
    ]
    for name, st in snap.items():
        lines.append(
            f'engine_health_up{{engine="{name}"}} {up_map.get(st.get("status", "unknown"), 0)}'
        )
    lines += [
        "# HELP engine_health_last_seen_healthy_ts Unix ts of last healthy probe (0 if never).",
        "# TYPE engine_health_last_seen_healthy_ts gauge",
    ]
    for name, st in snap.items():
        lines.append(
            f'engine_health_last_seen_healthy_ts{{engine="{name}"}} '
            f'{st.get("last_seen_healthy_ts", 0):.0f}'
        )
    q = ENGINE_QUOTA.status()
    lines += [
        "# HELP engine_quota_max_concurrent Max concurrent engine operations allowed.",
        "# TYPE engine_quota_max_concurrent gauge",
        f'engine_quota_max_concurrent {q["max_concurrent"]}',
        "# HELP engine_quota_active Currently active engine operations.",
        "# TYPE engine_quota_active gauge",
        f'engine_quota_active {q["active"]}',
        "# HELP engine_quota_available Available engine slots.",
        "# TYPE engine_quota_available gauge",
        f'engine_quota_available {q["available"]}',
    ]
    return "\n".join(lines) + "\n"



# ============================================================================
# 进程探测 / 树杀
# ============================================================================

def is_process_running(process_name: str) -> bool:
    """探测指定进程名是否在运行（跨平台）。

    稳定性加固：tasklist/pgrep 可能因管道争用或瞬时失败而抛异常。
    若一次失败就返回 False，看门狗会误判引擎死亡并重复拉起（资源泄漏）。
    故探测失败时重试，只有连续失败才认定「不在运行」。
    """
    attempts = 3
    for i in range(attempts):
        try:
            if os.name == "nt":
                proc = subprocess.run(
                    ["tasklist"], capture_output=True, text=True, timeout=5,
                    encoding="utf-8", errors="replace",
                )
                if proc.returncode == 0 and process_name.lower() in proc.stdout.lower():
                    return True
            else:
                out = subprocess.run(
                    ["pgrep", "-f", process_name], capture_output=True, text=True, timeout=5,
                )
                if out.returncode == 0 and bool(out.stdout.strip()):
                    return True
            # 探测成功但未命中：本次明确「不在」。仅当全部尝试都未命中才判死。
            if i < attempts - 1:
                time.sleep(0.2)
                continue
            return False
        except Exception as e:
            logger.warning(f"[Watchdog] 进程探测异常 {process_name} (第{i+1}次): {e}")
            if i < attempts - 1:
                time.sleep(0.2)
                continue
            return False
    return False


def kill_process_tree(pid: int) -> None:
    """按进程树杀（含 aerender / ffmpeg 等子进程）。跨平台。"""
    if pid is None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
        else:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            time.sleep(2)
            if os.getpgid(pid) >= 0:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception as e:
        logger.warning(f"[Watchdog] 进程树杀失败 pid={pid}: {e}")


def kill_process_tree_by_name(process_name: str) -> None:
    """按进程名杀掉所有匹配进程及其子树。"""
    try:
        if os.name == "nt":
            out = subprocess.run(
                ["tasklist", "/fo", "csv"], capture_output=True, text=True,
                timeout=5, encoding="utf-8", errors="replace",
            )
            for line in out.stdout.splitlines()[1:]:
                cols = line.split('","')
                if len(cols) >= 2 and process_name.lower() in cols[0].lower().strip('"'):
                    try:
                        kill_process_tree(int(cols[1].strip('"')))
                    except ValueError:
                        continue
        else:
            out = subprocess.run(
                ["pgrep", "-f", process_name], capture_output=True, text=True, timeout=5,
            )
            for pid_s in out.stdout.split():
                kill_process_tree(int(pid_s))
    except Exception as e:
        logger.warning(f"[Watchdog] 按名杀进程失败 {process_name}: {e}")


# ============================================================================
# 进程级冷重启恢复（Plan B 续：编排器进程崩溃后的孤儿回收）
# ============================================================================
#
# 固件映射：manifest = 非易失状态镜像（P2 已落地）；本段补齐「看门狗复位清残留」——
# 若编排器进程本身在子进程（aerender/ffmpeg）运行途中崩溃，那些子进程会成为
# 孤儿继续占用 GPU/CPU。冷重启（新进程以同 run_id 续跑）时须先把上一次遗留的
# 孤儿按「命令特征」精确回收，再续跑，保证无数据损坏、无资源泄漏。
#
# 安全约束（与桥自愈一致，绝不误杀）：
# - 仅回收本 run 显式追踪记录过的子进程 PID（写入 <run_dir>/.children.json）。
# - 回收前校验进程仍存活且命令特征（marker）匹配，避免杀掉 PID 复用受害者。
# - 默认关闭（AEKV_ORPHAN_RECLAIM=1 启用），不改动既有默认行为。

def orphan_reclaim_enabled() -> bool:
    """孤儿回收默认关闭（AEKV_ORPHAN_RECLAIM=1 启用）。"""
    return os.environ.get("AEKV_ORPHAN_RECLAIM") == "1"


def _children_path(run_dir) -> Path:
    return Path(run_dir) / ".children.json"


def record_child(run_dir, pid: int, marker: str) -> None:
    """记录一个由本 run 派生的子进程 PID + 命令特征（崩溃恢复用）。best-effort。"""
    try:
        p = _children_path(run_dir)
        entries = []
        if p.exists():
            try:
                entries = json.loads(p.read_text(encoding="utf-8")) or []
            except Exception:
                entries = []
        entries.append({"pid": int(pid), "marker": str(marker), "ts": time.time()})
        p.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def clear_children(run_dir) -> None:
    """清理本 run 的子进程追踪 sidecar（正常完成后调用）。best-effort。"""
    try:
        _children_path(run_dir).unlink(missing_ok=True)
    except Exception:
        pass


def is_process_running_pid(pid: int) -> bool:
    """按 PID 探测进程是否存活（跨平台，零依赖；signal 0 = 仅存在性检查）。"""
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # 进程存在但无权查询 -> 视为存活
        return True
    except Exception:
        return False


def _process_cmdline(pid: int) -> str:
    """读取进程完整命令行（用于回收前的命令特征校验）。读取失败返回空串。"""
    try:
        if os.name == "nt":
            ps = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            return (ps.stdout or "").strip()
        out = subprocess.run(
            ["ps", "-p", str(int(pid)), "-o", "args="],
            capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace",
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def reclaim_orphans(run_dir) -> int:
    """冷重启回收上一次崩溃遗留的子进程。返回回收数量；best-effort，绝不抛异常。

    每个记录项：先确认进程仍存活（is_process_running_pid），再读取其命令行，
    若 marker 非空且命令行不含 marker 说明 PID 被无关进程复用 -> 跳过以防误杀；
    命令行不可读（无权限/工具缺失）则仍尝试回收（优先清理自身孤儿）。
    """
    try:
        p = _children_path(run_dir)
        if not p.exists():
            return 0
        try:
            entries = json.loads(p.read_text(encoding="utf-8")) or []
        except Exception:
            entries = []
        reclaimed = 0
        for e in entries:
            pid = e.get("pid")
            marker = e.get("marker", "")
            if not pid:
                continue
            if not is_process_running_pid(pid):
                continue
            if marker:
                cl = _process_cmdline(pid)
                if cl and marker not in cl:
                    logger.debug(
                        f"[Reclaim] PID {pid} 仍存活但命令行不含 marker={marker!r}，"
                        f"疑似 PID 复用受害者，跳过以防误杀")
                    continue
            try:
                kill_process_tree(pid)
                reclaimed += 1
            except Exception as e2:
                logger.warning(f"[Reclaim] 回收 PID {pid} 失败: {e2}")
        # 无论回收与否，清理 sidecar
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass
        if reclaimed:
            logger.info(f"[Reclaim] 已回收 {reclaimed} 个崩溃遗留子进程 (run={run_dir})")
        return reclaimed
    except Exception as e:
        logger.warning(f"[Reclaim] 孤儿回收异常: {e}")
        return 0


# ============================================================================
# 桥进程自愈（P3 收尾：AE 重启后 Bridge 是独立进程，需一并重启方能恢复连接）
# ============================================================================

# 引擎 -> .mcp.json 中对应 MCP server 名（桥进程由该 server 拉起）
# 2026-08-27: premiere 改指现存 AdobePremiereMCP（6476ef2 重组后的实际条目）
BRIDGE_MCP_MAP = {
    "after_effects": "AdobeMCP",
    "premiere": "AdobePremiereMCP",
    "resolve": "DaVinciResolveMCP",
    "media_encoder": None,
}


def bridge_restart_enabled() -> bool:
    """桥自愈默认关闭（AEKV_BRIDGE_RESTART=1 启用）。

    杀桥进程属有风险操作：桥通常以 python.exe 运行，与仓库/代理/本 agent 等
    其它 python 进程同名。故必须显式开启，且定位只用启动命令里的唯一脚本子串，
    绝不按 'python.exe' 这种歧义名批量杀，避免误伤无关进程。
    """
    return os.environ.get("AEKV_BRIDGE_RESTART") == "1"


def _bridge_launch_spec(engine_name: str) -> dict | None:
    """从仓库根 .mcp.json 读取该引擎桥进程的启动规格（command/args/cwd/marker）。

    以 .mcp.json 为唯一事实源，避免硬编码用户专属 python 路径；读取失败则禁用。
    marker = 启动参数里能唯一定位桥进程的子串（如 adobe_mcp_server.py）。
    """
    mcp_name = BRIDGE_MCP_MAP.get(engine_name)
    if not mcp_name:
        return None
    try:
        mcp_path = Path(__file__).resolve().parent.parent / ".mcp.json"
        if not mcp_path.exists():
            return None
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        srv = data.get("mcpServers", {}).get(mcp_name)
        if not srv:
            return None
        command = srv.get("command")
        args = list(srv.get("args", []))
        cwd = srv.get("cwd")
        marker = ""
        for a in reversed(args):
            if "/" in a or "\\" in a or a.endswith(".py") or a.endswith(".js"):
                marker = a.replace("\\", "/").split("/")[-1]
                break
        if not marker:
            marker = mcp_name
        return {"command": command, "args": args, "cwd": cwd, "marker": marker}
    except Exception as e:
        logger.debug(f"[Watchdog] 读取桥启动规格失败 {engine_name}: {e}")
        return None


def find_bridge_pids(engine_name: str) -> list[int]:
    """按唯一脚本子串（marker）精确定位桥进程 PID，杜绝按 python.exe 歧义名误杀。"""
    spec = _bridge_launch_spec(engine_name)
    if not spec:
        return []
    marker = spec.get("marker") or ""
    if not marker:
        return []
    try:
        if os.name == "nt":
            ps = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%{marker}%'\" "
                 f"| Select-Object -ExpandProperty ProcessId"],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            return [int(x.strip()) for x in ps.stdout.split() if x.strip().isdigit()]
        out = subprocess.run(
            ["pgrep", "-f", marker], capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace",
        )
        return [int(x) for x in out.stdout.split() if x.strip().isdigit()]
    except Exception as e:
        logger.warning(f"[Watchdog] 桥进程探测异常 {engine_name}: {e}")
        return []


def restart_bridge(engine_name: str) -> bool:
    """重启桥进程：先按唯一子串精确定杀旧进程，再以 .mcp.json 规格重新拉起。

    仅在 bridge_restart_enabled() 时由自愈分支调用。返回是否执行了重启动作。
    """
    spec = _bridge_launch_spec(engine_name)
    if not spec:
        logger.debug(f"[Watchdog] {engine_name} 无桥启动规格，跳过桥重启")
        return False
    try:
        for pid in find_bridge_pids(engine_name):
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        capture_output=True, text=True, timeout=10,
                        encoding="utf-8", errors="replace",
                    )
                else:
                    os.kill(pid, signal.SIGTERM)
            except Exception as e:
                logger.warning(f"[Watchdog] 桥进程终止失败 pid={pid}: {e}")
        time.sleep(1)
        cmd = [spec["command"], *spec["args"]]
        subprocess.Popen(cmd, cwd=spec.get("cwd"),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"[Watchdog] 已重启桥进程 {engine_name}: {' '.join(cmd)}")
        return True
    except Exception as e:
        logger.error(f"[Watchdog] 桥进程重启失败 {engine_name}: {e}")
        return False


# ============================================================================
# 引擎发现 / 拉起
# ============================================================================

def discover_exe(engine_name: str) -> str | None:
    """发现引擎可执行文件：优先 adobe_discovery，回退硬编码路径。"""
    try:
        from core.adobe_discovery import find_adobe_exe
        p = find_adobe_exe(engine_name)
        if p:
            return str(p)
    except Exception:
        pass
    if engine_name == "after_effects":
        legacy = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
        if os.path.exists(legacy):
            return legacy
    return None


def launch_engine(engine_name: str, exe: str | None = None) -> bool:
    """拉起引擎进程（Startup 脚本会自动加载 Bridge）。"""
    target = exe or discover_exe(engine_name)
    if not target or not os.path.exists(target):
        logger.warning(f"[Watchdog] 未找到 {engine_name} 可执行文件: {target}")
        return False
    try:
        subprocess.Popen(
            [target], cwd=os.path.dirname(target),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        logger.info(f"[Watchdog] 已拉起 {engine_name}: {target}")
        return True
    except Exception as e:
        logger.error(f"[Watchdog] 启动 {engine_name} 失败: {e}")
        return False


# ============================================================================
# 探活 / 就绪保证
# ============================================================================

def probe_bridge(is_available: Callable[[], bool], timeout: float = 120.0) -> bool:
    """轮询 Bridge 可用性直至超时。

    is_available 应为 dispatcher.is_available(force_check=True)。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if is_available():
                return True
        except Exception:
            pass
        time.sleep(2.0)
    return False


def ensure_ready(
    engine_name: str,
    is_available: Callable[[], bool] | None = None,
    timeout: float = 120.0,
) -> bool:
    """确保引擎就绪（P3：配额 + 双检锁 + 健康注册表）：

    1. 拿引擎配额（同引擎互斥 + 全局并发上限）；
    2. 进程未运行 -> 双检锁后拉起（杜绝看门狗/编排器并发双拉起）；
    3. 有 Bridge 探针时探活，成功返回 True；
    4. 探活超时且进程在但无响应（假死）-> 杀树重启再探一次；
    5. 仍不可用返回 False（由调用方决定降级或中止，P1 一致性收口负责）。
    全程把结果写入 ENGINE_HEALTH 注册表，供观测层与看门狗共享。
    """
    proc_name = ENGINE_PROCESS_NAME.get(engine_name)
    # 全局并发配额（背压）：拿不到则 fail-fast，不野蛮抢占 GPU
    if not ENGINE_QUOTA.acquire_engine(engine_name, timeout=5.0):
        ENGINE_HEALTH.mark_dead(engine_name, "资源配额耗尽（并发引擎上限）")
        logger.warning(f"[Watchdog] {engine_name} ensure_ready 被资源配额拒绝")
        return False
    try:
        if proc_name:
            if not is_process_running(proc_name):
                # 双检锁：拿到引擎独占锁后再确认一次，杜绝并发双拉起
                ENGINE_HEALTH.mark_launch_started(engine_name)
                if not is_process_running(proc_name):
                    if not launch_engine(engine_name):
                        ENGINE_HEALTH.mark_dead(engine_name, "启动失败")
                        return False
                    ENGINE_HEALTH.mark_launch_done(engine_name, True)
                else:
                    # 锁内复检发现已在运行（被看门狗/另一路径抢先拉起）
                    ENGINE_HEALTH.mark_launch_done(engine_name, True)
            else:
                ENGINE_HEALTH.mark_launch_done(engine_name, True)

        if is_available is None:
            # 无 Bridge 探针能力时，仅保证进程在运行
            healthy = bool(proc_name and is_process_running(proc_name))
            if healthy:
                ENGINE_HEALTH.mark_healthy(engine_name)
            else:
                ENGINE_HEALTH.mark_dead(engine_name, "进程不在运行")
            return healthy

        if probe_bridge(is_available, timeout=timeout):
            ENGINE_HEALTH.mark_healthy(engine_name)
            return True

        # 假死自愈：进程在但 Bridge 无响应 -> 杀树重启再探一次
        logger.warning(f"[Watchdog] {engine_name} Bridge 探活超时，判定假死，执行杀树重启...")
        if proc_name:
            kill_process_tree_by_name(proc_name)
            time.sleep(2)
            ENGINE_HEALTH.mark_launch_started(engine_name)
            launch_engine(engine_name)
            ENGINE_HEALTH.mark_launch_done(engine_name, True)
            # 桥自愈（opt-in）：AE 应用重启后，Bridge 是独立进程，需一并重启方能恢复连接
            if bridge_restart_enabled():
                restart_bridge(engine_name)
            if probe_bridge(is_available, timeout=timeout):
                ENGINE_HEALTH.mark_healthy(engine_name)
                return True
        ENGINE_HEALTH.mark_dead(engine_name, "重启后仍不可用")
        logger.error(f"[Watchdog] {engine_name} 重启后仍不可用")
        return False
    finally:
        ENGINE_QUOTA.release_engine(engine_name)


# ============================================================================
# 常驻巡检线程（默认关闭，AEKV_WATCHDOG=1 启用）
# ============================================================================

def _watchdog_loop(interval: float = 15.0) -> None:
    """周期探活已登记引擎；发现假死则杀树重启。仅 env AEKV_WATCHDOG=1 启用。

    P3：每次巡检把结果写回 ENGINE_HEALTH 注册表（健康常态化），且假死自愈
    在引擎配额锁内执行，与 ensure_ready 互斥，杜绝双拉起。
    """
    engines = ["after_effects", "premiere", "resolve", "media_encoder"]
    while not _WATCHDOG_STOP.is_set():
        try:
            from pipeline.engine_task_dispatcher import get_dispatcher
            for name in engines:
                try:
                    disp = get_dispatcher(name)
                    if disp is None:
                        continue
                    proc_name = ENGINE_PROCESS_NAME.get(name)
                    available = disp.is_available(force_check=True)
                    if available:
                        ENGINE_HEALTH.mark_healthy(name)
                        continue
                    if proc_name and is_process_running(proc_name):
                        # 假死 -> 在引擎锁内杀树重启，与 ensure_ready 互斥
                        if ENGINE_QUOTA.acquire_engine(name, timeout=5.0):
                            try:
                                logger.warning(f"[Watchdog] {name} 假死，执行杀树重启")
                                kill_process_tree_by_name(proc_name)
                                time.sleep(2)
                                ENGINE_HEALTH.mark_launch_started(name)
                                launch_engine(name)
                                ENGINE_HEALTH.mark_launch_done(name, True)
                                # 桥自愈（opt-in）：AE 应用重启后，Bridge 是独立进程，需一并重启
                                if bridge_restart_enabled():
                                    restart_bridge(name)
                            finally:
                                ENGINE_QUOTA.release_engine(name)
                        else:
                            logger.debug(f"[Watchdog] {name} 自愈被配额拒绝，下轮重试")
                    else:
                        ENGINE_HEALTH.mark_dead(name, "不可用且进程不在运行")
                except Exception as e:
                    logger.debug(f"[Watchdog] 巡检 {name} 跳过: {e}")
        except Exception as e:
            logger.debug(f"[Watchdog] 巡检循环异常: {e}")
        _WATCHDOG_STOP.wait(interval)


def start_ae_watchdog(interval: float = 15.0) -> None:
    """启动常驻看门狗（幂等）。默认不启动，需 AEKV_WATCHDOG=1。"""
    global _WATCHDOG_THREAD
    if os.environ.get("AEKV_WATCHDOG") != "1":
        logger.debug("[Watchdog] 未启用（设置 AEKV_WATCHDOG=1 开启常驻巡检）")
        return
    if _WATCHDOG_THREAD is not None and _WATCHDOG_THREAD.is_alive():
        return
    _WATCHDOG_STOP.clear()
    _WATCHDOG_THREAD = threading.Thread(
        target=_watchdog_loop, args=(interval,), daemon=True,
    )
    _WATCHDOG_THREAD.start()
    logger.info("[Watchdog] 常驻巡检线程已启动")


def stop_ae_watchdog() -> None:
    _WATCHDOG_STOP.set()
