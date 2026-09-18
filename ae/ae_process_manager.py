#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AE Process Manager
==================
Detects, starts, and monitors Adobe After Effects.
Can auto-launch AE with the MCP auto-listener script.
Optional REST API for remote status queries.

Usage:
    python ae_process_manager.py
    python ae_process_manager.py --api --port 8123
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Optional HTTP server for REST API
try:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    _HAS_HTTP = True
except ImportError:
    _HAS_HTTP = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_LISTENER = Path(__file__).with_name("ae_mcp_auto_listener.jsx")
DEFAULT_SEARCH_PATHS: list[Path] = [
    Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"),
    Path(r"D:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"),
    Path(r"E:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"),
]
AE_PROCESS_NAME = "AfterFX.exe"


# ---------------------------------------------------------------------------
# AEProcessManager
# ---------------------------------------------------------------------------
class AEProcessManager:
    """Manages the After Effects process lifecycle."""

    def __init__(
        self,
        ae_exe_path: str | None = None,
        listener_script_path: str | None = None,
    ):
        self.ae_exe_path: Path | None = None
        self.listener_script_path: Path | None = None
        self._last_status: dict = {}
        self._started_by_manager: bool = False

        # Resolve AE executable
        if ae_exe_path:
            candidate = Path(ae_exe_path)
            if candidate.exists():
                self.ae_exe_path = candidate.resolve()
            else:
                raise FileNotFoundError(
                    f"Provided AE executable not found: {ae_exe_path}"
                )
        else:
            self.ae_exe_path = self._find_ae_executable()

        # Resolve listener script
        if listener_script_path:
            candidate = Path(listener_script_path)
            if candidate.exists():
                self.listener_script_path = candidate.resolve()
            else:
                raise FileNotFoundError(
                    f"Provided listener script not found: {listener_script_path}"
                )
        else:
            self.listener_script_path = self._find_listener_script()

    # --------------- Discovery helpers ---------------

    @staticmethod
    def _find_ae_executable() -> Path | None:
        for p in DEFAULT_SEARCH_PATHS:
            if p.exists():
                return p.resolve()
        # Broad search under Program Files
        for root in [Path(r"C:\Program Files\Adobe"), Path(r"D:\Program Files\Adobe")]:
            if not root.exists():
                continue
            for sub in root.iterdir():
                if sub.is_dir() and "After Effects" in sub.name:
                    exe = sub / "Support Files" / "AfterFX.exe"
                    if exe.exists():
                        return exe.resolve()
        return None

    @staticmethod
    def _find_listener_script() -> Path | None:
        candidate = DEFAULT_LISTENER
        if candidate.exists():
            return candidate.resolve()
        # Search CWD
        cwd_candidate = Path.cwd() / "ae_mcp_auto_listener.jsx"
        if cwd_candidate.exists():
            return cwd_candidate.resolve()
        return None

    # --------------- Process queries ---------------

    def is_ae_running(self) -> bool:
        """Return True if AfterFX.exe is currently running."""
        try:
            import psutil
        except ImportError:
            # Fallback via tasklist (Windows-only)
            return self._is_running_via_tasklist()

        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == AE_PROCESS_NAME.lower():
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _is_running_via_tasklist() -> bool:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {AE_PROCESS_NAME}"],
                capture_output=True,
                text=True,
                check=False,
            )
            return AE_PROCESS_NAME.lower() in result.stdout.lower()
        except Exception:
            return False

    def get_ae_status(self) -> dict:
        """Return a dict with current AE process status."""
        running = self.is_ae_running()
        status = {
            "running": running,
            "ae_exe_path": str(self.ae_exe_path) if self.ae_exe_path else None,
            "listener_script_path": str(self.listener_script_path)
            if self.listener_script_path
            else None,
            "started_by_manager": self._started_by_manager,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        if running:
            try:
                import psutil

                for proc in psutil.process_iter(["name", "pid", "create_time"]):
                    if proc.info["name"] and proc.info["name"].lower() == AE_PROCESS_NAME.lower():
                        status["pid"] = proc.info["pid"]
                        status["create_time"] = proc.info["create_time"]
                        break
            except ImportError:
                pass
        else:
            status["pid"] = None
            status["create_time"] = None

        self._last_status = status
        return status

    # --------------- Lifecycle actions ---------------

    def start_ae_with_listener(self) -> bool:
        """Launch AE with the auto-listener script (non-blocking)."""
        if self.is_ae_running():
            print("[INFO] After Effects is already running.")
            return False

        if not self.ae_exe_path:
            print("[ERR]  After Effects executable not found.")
            return False

        cmd = [str(self.ae_exe_path)]
        if self.listener_script_path and self.listener_script_path.exists():
            # -r runs a script on startup
            cmd.extend(["-r", str(self.listener_script_path)])
            print(f"[INFO] Will run listener: {self.listener_script_path}")
        else:
            print("[WARN] Listener script not found; starting AE without it.")

        try:
            print(f"[INFO] Starting AE: {self.ae_exe_path}")
            subprocess.Popen(cmd, shell=False)
            self._started_by_manager = True
            print("[OK]   After Effects launched (non-blocking).")
            return True
        except Exception as exc:
            print(f"[ERR]  Failed to start AE: {exc}")
            return False

    def restart_ae(self) -> bool:
        """Kill any running AE process, then start fresh."""
        print("[INFO] Restarting After Effects...")
        if self.is_ae_running():
            self._kill_ae()
            # Wait for process to exit
            for _ in range(30):
                if not self.is_ae_running():
                    break
                time.sleep(1)
            else:
                print("[ERR]  AE did not terminate in time.")
                return False
        return self.start_ae_with_listener()

    def _kill_ae(self) -> None:
        try:
            import psutil

            for proc in psutil.process_iter(["name"]):
                if proc.info["name"] and proc.info["name"].lower() == AE_PROCESS_NAME.lower():
                    print(f"[INFO] Terminating PID {proc.pid}")
                    proc.terminate()
        except ImportError:
            subprocess.run(
                ["taskkill", "/F", "/IM", AE_PROCESS_NAME],
                capture_output=True,
                check=False,
            )

    # --------------- Monitoring loop ---------------

    def monitor(self, interval_sec: int = 5, auto_start: bool = True) -> None:
        """Block and periodically print AE status."""
        print("[INFO] Starting AE monitor (Ctrl+C to stop)...")
        try:
            while True:
                status = self.get_ae_status()
                if not status["running"] and auto_start:
                    print("[WARN] AE not running; auto-starting...")
                    self.start_ae_with_listener()
                else:
                    state = "running" if status["running"] else "stopped"
                    print(f"[INFO] AE status: {state}")
                time.sleep(interval_sec)
        except KeyboardInterrupt:
            print("\n[INFO] Monitor stopped by user.")


# ---------------------------------------------------------------------------
# Optional REST API
# ---------------------------------------------------------------------------
class _AEStatusHandler(BaseHTTPRequestHandler):
    manager: AEProcessManager | None = None

    def log_message(self, format, *args):
        # Suppress default HTTP logging
        pass

    def _send_json(self, data: dict, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def do_GET(self):
        if self.path in ("/", "/status"):
            if self.manager is None:
                self._send_json({"error": "Manager not initialized"}, 500)
                return
            self._send_json(self.manager.get_ae_status())
        elif self.path == "/start":
            if self.manager is None:
                self._send_json({"error": "Manager not initialized"}, 500)
                return
            ok = self.manager.start_ae_with_listener()
            self._send_json({"started": ok})
        elif self.path == "/restart":
            if self.manager is None:
                self._send_json({"error": "Manager not initialized"}, 500)
                return
            ok = self.manager.restart_ae()
            self._send_json({"restarted": ok})
        else:
            self._send_json({"error": "Not found"}, 404)


def run_api_server(manager: AEProcessManager, host: str, port: int):
    if not _HAS_HTTP:
        print("[ERR]  HTTP server module not available in this Python build.")
        sys.exit(1)

    _AEStatusHandler.manager = manager
    server = HTTPServer((host, port), _AEStatusHandler)
    print(f"[INFO] API server listening on http://{host}:{port}")
    print("[INFO] Endpoints: GET /status, /start, /restart")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] API server stopped.")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="After Effects Process Manager"
    )
    parser.add_argument(
        "--ae-exe",
        dest="ae_exe",
        default=None,
        help="Path to AfterFX.exe",
    )
    parser.add_argument(
        "--listener",
        dest="listener",
        default=None,
        help="Path to ae_mcp_auto_listener.jsx",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Monitor AE and auto-restart if needed",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Monitor interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Run REST API server",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="API bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8123,
        help="API port (default: 8123)",
    )
    args = parser.parse_args()

    # Create manager
    try:
        mgr = AEProcessManager(
            ae_exe_path=args.ae_exe,
            listener_script_path=args.listener,
        )
    except FileNotFoundError as exc:
        print(f"[ERR]  {exc}")
        sys.exit(1)

    # Print initial status
    print("=" * 50)
    print("AE Process Manager")
    print("=" * 50)
    print(f"AE exe       : {mgr.ae_exe_path}")
    print(f"Listener     : {mgr.listener_script_path}")
    print(f"AE running   : {mgr.is_ae_running()}")
    print("=" * 50)

    if args.api:
        run_api_server(mgr, args.host, args.port)
    elif args.monitor:
        mgr.monitor(interval_sec=args.interval, auto_start=True)
    else:
        # One-shot: start if not running
        if not mgr.is_ae_running():
            mgr.start_ae_with_listener()
        else:
            print("[INFO] AE is already running.")
        # Print final status as JSON
        print(json.dumps(mgr.get_ae_status(), indent=2))


if __name__ == "__main__":
    main()
