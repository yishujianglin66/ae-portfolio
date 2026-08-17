#!/usr/bin/env python3
"""cloud_matting_monitor.py — 云端混合微调完成监控 + 自动回传验证

后台运行: 每 300s 轮询云端 finetune.done 标记, 训练完成后:
  1. 下载 finetuned_anime.pth 到本地 external/birefnet/finetuned_anime_mixed.pth
  2. 验证权重可加载 (参数数/首键)
  3. 追加记录到 docs/research/2026-08-15-matting-mixed-finetune-monitor.log
用法:
  SSHPASS=xxx SSHPORT=xxx python scripts/cloud_matting_monitor.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

import paramiko

HOST = os.environ.get("SSHHOST", "connect.westb.seetacloud.com")
PORT = int(os.environ.get("SSHPORT", "30222"))
TMP = "/root/autodl-tmp"
LOCAL_CKPT = pathlib.Path(
    r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\external\birefnet\finetuned_anime_mixed.pth")
LOG_FILE = pathlib.Path(
    r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\docs\research\2026-08-15-matting-mixed-finetune-monitor.log")


def connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, PORT, "root", os.environ["SSHPASS"], timeout=25)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 60) -> str:
    _in, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    return (o + "\n[stderr] " + e) if e.strip() else o


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    t0 = time.time()
    print(f"[monitor] 开始监控 {HOST}:{PORT} (每 300s 轮询)")
    while True:
        try:
            c = connect()
            done = run(c, f"cat {TMP}/finetune.done 2>/dev/null || echo RUNNING", timeout=40).strip()
            prog = run(c, f"tail -1 {TMP}/finetune.log 2>/dev/null || echo no-log", timeout=40).strip()
            epochs = run(c, f"ls {TMP}/birefnet_mixed/*.pth 2>/dev/null | wc -l", timeout=40).strip()
            c.close()
            print(f"[{int(time.time()-t0)}s] {prog} (epochs={epochs})")
            if "FINETUNE_DONE" in done:
                print("[monitor] 训练完成! 开始回传...")
                c = connect()
                sftp = c.open_sftp()
                sftp.get(f"{TMP}/birefnet_mixed/finetuned_anime.pth", str(LOCAL_CKPT))
                sftp.close()
                c.close()
                sz = LOCAL_CKPT.stat().st_size
                print(f"[monitor] 回传完成: {LOCAL_CKPT} ({sz/1e6:.1f}MB)")
                # 验证权重可加载
                import torch
                sd = torch.load(str(LOCAL_CKPT), map_location="cpu")
                if isinstance(sd, dict) and "state_dict" in sd:
                    sd = sd["state_dict"]
                entry = {
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "size_mb": round(sz / 1e6, 1),
                    "n_params": len(sd),
                    "first_key": list(sd.keys())[0],
                    "remote_log_tail": prog,
                }
                LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                print(f"[monitor] 验证: {entry['n_params']} 参数, 首键 {entry['first_key']}")
                print(f"[monitor] 记录已追加 {LOG_FILE}")
                return 0
        except Exception as e:  # noqa: BLE001
            print(f"[monitor] 轮询异常: {type(e).__name__} {e}")
        time.sleep(300)


if __name__ == "__main__":
    sys.exit(main())
