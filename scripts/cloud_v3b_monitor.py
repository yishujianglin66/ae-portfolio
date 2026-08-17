#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_v3b_monitor.py — 后台轮询云端 v3b 训练, 完成后自动回传权重到本地。

用法 (凭据走环境变量, 不落盘):
  set SSHPASS=xxx && py -3.12 scripts/cloud_v3b_monitor.py [--poll 60] [--timeout 7200]

回传后打印 '===DONE===' 供主会话识别; 每轮打印进度摘要。
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

import paramiko

HOST = "connect.weste.seetacloud.com"
PORT = 13132
USER = "root"
REMOTE_LOG = "/root/autodl-tmp/v3b_train.log"
REMOTE_DIR = "/root/autodl-tmp/output/anime_camera_lora_v3b"
LOCAL_DIR = pathlib.Path(
    r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\models\output\anime_camera_lora_v3")
FILES = ["adapter_model.safetensors", "adapter_config.json", "meta.json", "README.md"]


def connect() -> paramiko.SSHClient:
    import os
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, PORT, USER, os.environ["SSHPASS"], timeout=25)
    return c


def tail(c: paramiko.SSHClient, n: int = 6) -> str:
    _in, out, _ = c.exec_command(f"tail -{n} {REMOTE_LOG}", timeout=30)
    return out.read().decode("utf-8", "replace")


def is_done(c: paramiko.SSHClient) -> bool:
    _in, out, _ = c.exec_command(f"grep -c '完成: best val_acc' {REMOTE_LOG} || true", timeout=30)
    return "1" in out.read().decode("utf-8", "replace").strip()


def is_failed(c: paramiko.SSHClient) -> bool:
    _in, out, _ = c.exec_command(f"grep -icE 'Traceback|CUDA error|OutOfMemory' {REMOTE_LOG} || true", timeout=30)
    return int(out.read().decode("utf-8", "replace").strip() or "0") > 0


def download(c: paramiko.SSHClient) -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    sftp = c.open_sftp()
    for f in FILES:
        try:
            sftp.get(f"{REMOTE_DIR}/{f}", str(LOCAL_DIR / f))
            print(f"  OK {f} ({LOCAL_DIR.joinpath(f).stat().st_size} B)")
        except FileNotFoundError:
            print(f"  MISS {f}")
    sftp.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--poll", type=int, default=60)
    ap.add_argument("--timeout", type=int, default=7200)
    args = ap.parse_args()

    t0 = time.time()
    while time.time() - t0 < args.timeout:
        try:
            c = connect()
            if is_done(c):
                print("===DONE=== 训练完成, 回传权重...")
                download(c)
                print("===DONE=== 回传完成: " + str(LOCAL_DIR))
                c.close()
                return 0
            if is_failed(c):
                print("===FAILED=== 训练异常, 日志尾部:")
                print(tail(c, 25))
                c.close()
                return 1
            print(f"[{int(time.time()-t0)}s] " + tail(c, 1).strip()[:140])
            c.close()
        except Exception as e:  # noqa: BLE001
            print(f"[poll err] {e}")
        time.sleep(args.poll)

    print(f"===TIMEOUT=== {args.timeout}s 内未完成, 最后一次日志:")
    try:
        c = connect()
        print(tail(c, 20))
        c.close()
    except Exception as e:  # noqa: BLE001
        print(f"[final err] {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
