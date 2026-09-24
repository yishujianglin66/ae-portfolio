"""ae_channel_status.py — AE 三轨通道盘点（2026-09-19）。

背景
----
集成计划评审 §六 发现"三轨并存、弃用声明与实际不符"：
  · ① 自研文件轮询  = ai/ae_render_channel.py（.ae-mcp-bridge 协议）
  · ② 开源 after-effects-mcp（node）   = .mcp.json 配置，源码在 Desktop 不在仓库
  · ③ 自研多 app MCP = bridges/adobe_mcp_server.py + adobe_mcp_manager.py
而 bridges/adobe_bridge_adapter.py 的 docstring 一度声称"自研协议已整体弃用"，
与"① 仍在承载全部自动化渲染"的事实矛盾 —— 本脚本把三者**实际状态**打出来，
让收敛进度可复跑、可复查，而不是靠文档自述。

判据（每条都指向磁盘/进程/配置的客观事实，不读自述文字）：
  ① 执行通道: ae_render_channel.py 在盘 + production_director 有 enable_ae_channel 接线
  ② 开源轨  : .mcp.json 是否配置 + 入口文件是否在盘 + 源码是否在仓库内 + 进程是否存活
  ③ 交互通道: adobe_mcp_server.py 在盘 + .mcp.json 中挂载了几个 app + 各 app 桥目录

用法:
  python scripts/ae_channel_status.py [--json reports/ae_channel_status.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _node_procs(pattern: str) -> int:
    """统计命令行含 pattern 的 node 进程数 (Windows; 失败返回 -1)。"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | "
             f"Where-Object {{ $_.CommandLine -like '*{pattern}*' }} | "
             "Measure-Object).Count"],
            capture_output=True, text=True, timeout=30)
        return int((r.stdout or "0").strip() or 0)
    except Exception:  # noqa: BLE001
        return -1


def check_render_channel() -> dict:
    """① 自研文件轮询 (自动化渲染执行通道)。"""
    mod = PROJ / "ai" / "ae_render_channel.py"
    src = mod.read_text(encoding="utf-8", errors="replace") if mod.exists() else ""
    bridge_dir_name = ".ae-mcp-bridge"
    wired = "enable_ae_channel" in (PROJ / "ai" / "production_director.py"
                                    ).read_text(encoding="utf-8", errors="replace")
    return {
        "name": "① 自研文件轮询 (执行通道)",
        "module": str(mod.relative_to(PROJ)),
        "present": mod.exists(),
        "protocol_dir": bridge_dir_name,
        "uses_hmac": "hmac" in src,
        "uses_failure_chain": "core.bridge_failure" in src,
        "wired_into_director": wired,
        "verdict": "活跃（生产必用）" if (mod.exists() and wired) else "缺接线",
    }


def check_open_source_track() -> dict:
    """② 开源 after-effects-mcp (node)。"""
    mcp = _read_json(PROJ / ".mcp.json").get("mcpServers", {})
    entry = next((v for k, v in mcp.items()
                  if "after-effects-mcp" in str(v.get("args", ""))), None)
    entry_path = None
    if entry:
        args = entry.get("args") or []
        entry_path = next((a for a in args if str(a).endswith(".js")), None)
    in_repo = (PROJ / "external" / "after-effects-mcp").exists()
    running = _node_procs("after-effects-mcp") if entry else 0
    return {
        "name": "② 开源 after-effects-mcp (node)",
        "configured_in_mcp_json": bool(entry),
        "entrypoint": entry_path,
        "entrypoint_on_disk": bool(entry_path and Path(entry_path).exists()),
        "source_in_repo": in_repo,
        "running_processes": running,
        "verdict": ("建议退役：源码不在仓库(不可复现) + 与③功能重叠"
                    if entry and not in_repo else
                    "保留（源码已入库）" if in_repo else "未配置"),
    }


def _manager_listeners() -> dict:
    """在测试同款环境 (import 重定向钩子) 下问 manager: 四个监听器解析到哪。

    这是 2026-09-19 修复项的**可复跑判据** —— 原实现把它们解析到
    bridges/*.jsx (不存在), 于是 install_bridge 恒返回 False。
    """
    # 用占位符替换而非 str.format: 内嵌代码里含 {} 字面量, format 会误解析
    code = (
        "import json,sys\n"
        "sys.path.insert(0, r'__PROJ__')\n"
        "sys.path.insert(0, r'__BRIDGES__')\n"
        "try:\n"
        "    import tests.conftest\n"
        "except Exception:\n"
        "    pass\n"
        "from adobe_mcp_manager import AdobeMCPManager\n"
        "from pathlib import Path\n"
        "m = AdobeMCPManager()\n"
        "print(json.dumps({k: Path(v).exists() for k, v in m.jsx_files.items()}))\n"
    ).replace("__PROJ__", str(PROJ)).replace("__BRIDGES__", str(PROJ / "bridges"))
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=120, cwd=str(PROJ))
        line = [ln for ln in (r.stdout or "").splitlines() if ln.startswith("{")]
        return json.loads(line[-1]) if line else {}
    except Exception:  # noqa: BLE001
        return {}


def check_mcp_server() -> dict:
    """③ 自研 Adobe MCP stdio (agent 交互通道, 4 app)。"""
    srv = PROJ / "bridges" / "adobe_mcp_server.py"
    mgr = PROJ / "bridges" / "adobe_mcp_manager.py"
    mcp = _read_json(PROJ / ".mcp.json").get("mcpServers", {})
    apps = sorted({str(v.get("args", [None, None])[-1])
                   for v in mcp.values()
                   if "adobe_mcp_server.py" in str(v.get("args", ""))})
    bridges_present = sorted(d.name for d in (PROJ / "bridges").glob(".*-mcp-bridge")
                             if d.is_dir())
    listeners = _manager_listeners()
    return {
        "name": "③ 自研 Adobe MCP stdio (交互通道)",
        "server": str(srv.relative_to(PROJ)),
        "manager": str(mgr.relative_to(PROJ)),
        "present": srv.exists() and mgr.exists(),
        "apps_in_mcp_json": apps,
        "bridge_dirs": bridges_present,
        "listeners_resolved": listeners,
        "verdict": ("活跃（仓库内自包含）"
                    if (srv.exists() and mgr.exists() and listeners
                        and all(listeners.values()))
                    else "监听器解析异常（install_bridge 会失败）"),
    }


def check_deprecated_wrapper() -> dict:
    """附: 旧统一适配器包装类 (声明弃用)。"""
    mod = PROJ / "bridges" / "adobe_bridge_adapter.py"
    src = mod.read_text(encoding="utf-8", errors="replace") if mod.exists() else ""
    init = (PROJ / "bridges" / "__init__.py").read_text(encoding="utf-8",
                                                        errors="replace")
    lazy = "lazy" in init.lower() or "__getattr__" in init
    eager = "\nfrom .adobe_bridge_adapter import" in init
    return {
        "name": "附: adobe_bridge_adapter (旧包装类)",
        "present": mod.exists(),
        "declares_deprecated": "DEPRECATED" in src,
        "eagerly_imported": eager,
        "lazily_exported": lazy and not eager,
        "verdict": ("弃用已生效（惰性导出，导入期无警告）"
                    if (lazy and not eager) else "仍为饿汉式导入（导入期触发警告）"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    rows = [check_render_channel(), check_open_source_track(),
            check_mcp_server(), check_deprecated_wrapper()]
    rep = {"generated_by": "scripts/ae_channel_status.py", "tracks": rows}

    print("\n=== AE 通道盘盘 (三轨 + 旧包装类) ===")
    for r in rows:
        print(f"\n{r['name']}")
        for k, v in r.items():
            if k in ("name", "verdict"):
                continue
            print(f"    {k}: {v}")
        print(f"    → {r['verdict']}")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print(f"\n→ {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
