#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_matting_pipeline.py — 新实例 10309 抠像集成训练管线编排

前置条件全部后台就绪后, 按序执行 (每步 setsid 分离 + 标记文件轮询, 抗断连):
  1. build_matting_dataset.py   动漫 + VOC2012 + cityscapes + ADE person GT mask
  2. gen_celeba_pseudo_mask.py  CelebA BiRefNet 自标注伪 mask (发丝边缘)
  3. finetune_birefnet.py       混合微调 (冻结 backbone, decoder/refiner + AMP)
  4. 回传最佳权重到本地 external/birefnet/finetuned_anime_mixed.pth

用法 (凭据走环境变量):
  set SSHPASS=xxx && py -3.12 scripts/cloud_matting_pipeline.py [--poll 60]
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time

import paramiko

HOST = os.environ.get("SSHHOST", "connect.westb.seetacloud.com")
PORT = int(os.environ.get("SSHPORT", "30222"))
USER = "root"
TMP = "/root/autodl-tmp"
PY = "/root/miniconda3/bin/python"

LOCAL_CKPT = pathlib.Path(
    r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\external\birefnet\finetuned_anime_mixed.pth")


def connect() -> paramiko.SSHClient:
    import os
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, PORT, USER, os.environ["SSHPASS"], timeout=25)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 120) -> str:
    _in, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    return (o + "\n[stderr] " + e) if e.strip() else o


def launch(c: paramiko.SSHClient, name: str, cmdline: str) -> None:
    """setsid 分离启动并写日志, 返回后立刻可断连。"""
    launch_cmd = (f"cd {TMP} && setsid nohup bash -c '{cmdline} && "
                  f"echo {name.upper()}_DONE > {TMP}/{name}.done' "
                  f"> {TMP}/{name}.log 2>&1 < /dev/null &")
    # 只发送命令不读输出: 后台化进程 stdout 已重定向, 读 channel 会因
    # SSH 通道不关闭而阻塞超时; setsid 已分离, 进程不随连接关闭而亡
    try:
        _in, out, _ = c.exec_command(launch_cmd, timeout=10)
        out.channel.close()  # 立即关 channel, 不等远程进程
    except Exception as e:  # noqa: BLE001 — 启动命令发送失败可重试
        print(f"[launch {name}] 发送异常: {e}")
    print(f"启动 {name}: {cmdline[:100]}...")


def wait_done(name: str, poll: int, timeout_s: int) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            c = connect()
            o = run(c, f"cat {TMP}/{name}.done 2>/dev/null || echo none; "
                      f"tail -2 {TMP}/{name}.log 2>/dev/null | tr '\\n' ' '", timeout=30)
            c.close()
            if f"{name.upper()}_DONE" in o:
                print(f"[{name}] 完成")
                return
            if "Traceback" in o or "Error" in o:
                print(f"[{name}] 疑似异常: {o[-300:]}")
            print(f"[{name}] 进行中 ({int(time.time()-t0)}s) ...")
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] poll err {e}")
        time.sleep(poll)
    print(f"[{name}] 超时 {timeout_s}s")
    sys.exit(1)


def prereqs_ready(c: paramiko.SSHClient) -> tuple[bool, str]:
    checks = [
        (f"{PY} -c 'import torch, transformers, cv2' 2>&1 | tail -1",
         lambda o: "ModuleNotFound" not in o and "ImportError" not in o),
        (f"cat {TMP}/datasets/.extract_done 2>/dev/null",
         lambda o: "EXTRACT_DONE" in o),
        (f"cat {TMP}/celeba/.done 2>/dev/null",
         lambda o: "CELEBA_DONE" in o),
        (f"ls -la {TMP}/birefnet/model.safetensors 2>/dev/null",
         lambda o: "model.safetensors" in o and "No such file" not in o),
        (f"ls -la {TMP}/imgs-masks.zip 2>/dev/null",
         lambda o: "imgs-masks.zip" in o and "No such file" not in o),
    ]
    msgs = []
    for cmd, ok in checks:
        o = run(c, cmd, timeout=60).strip()
        if not ok(o):
            msgs.append(o[:90])
    return (len(msgs) == 0, " | ".join(msgs))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(line_buffering=True)  # 后台 -u 未生效时保证实时可见
    ap = argparse.ArgumentParser()
    ap.add_argument("--poll", type=int, default=60)
    ap.add_argument("--n-celeba", type=int, default=4000)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()

    # 1. 等前置
    while True:
        try:
            c = connect()
            ready, msg = prereqs_ready(c)
            c.close()
        except Exception as e:  # noqa: BLE001 — 网络抖动/SFTP 超时都容错重试
            print(f"[连接抖动] {e}")
            time.sleep(args.poll)
            continue
        if ready:
            print("=== 前置条件全部就绪 ===")
            break
        print(f"[等待] {msg}")
        time.sleep(args.poll)

    # 2. 解压动漫数据集
    c = connect()
    run(c, f"mkdir -p {TMP}/animeseg/dataset && cd {TMP}/animeseg/dataset && "
           f"unzip -q -o {TMP}/imgs-masks.zip", timeout=180)
    n_anime = run(c, f"ls {TMP}/animeseg/dataset/imgs | wc -l", timeout=30)
    print(f"动漫数据解压: {n_anime.strip()} 图")
    c.close()

    # 3. 构建 GT 数据集 (IO 密集, 后台跑)
    c = connect()
    launch(c, "build", f"{PY} {TMP}/build_matting_dataset.py "
                       f"--out {TMP}/matting_dataset "
                       f"--anime {TMP}/animeseg/dataset "
                       f"--voc {TMP}/datasets/VOC2012 "
                       f"--cityscapes {TMP}/datasets "
                       f"--ade {TMP}/datasets/ADEChallengeData2016")
    c.close()
    wait_done("build", args.poll, 3600)

    # 4. CelebA 伪 mask (GPU, 后台跑)
    c = connect()
    launch(c, "celeba", f"{PY} {TMP}/gen_celeba_pseudo_mask.py "
                        f"--celeba {TMP}/celeba/img_align_celeba "
                        f"--model-dir {TMP}/birefnet "
                        f"--out {TMP}/matting_dataset "
                        f"--n {args.n_celeba} --batch {args.batch}")
    c.close()
    wait_done("celeba", args.poll, 10800)

    # 5. 混合微调 (GPU, 后台跑)
    c = connect()
    launch(c, "finetune", f"{PY} {TMP}/finetune_birefnet.py "
                          f"--data {TMP}/matting_dataset "
                          f"--model-dir {TMP}/birefnet "
                          f"--ckpt-dir {TMP}/birefnet_mixed "
                          f"--epochs {args.epochs} --batch {args.batch}")
    c.close()
    wait_done("finetune", args.poll, 18000)

    # 6. 回传最佳权重
    c = connect()
    sftp = c.open_sftp()
    remote_best = f"{TMP}/birefnet_mixed/finetuned_anime.pth"
    try:
        sftp.get(remote_best, str(LOCAL_CKPT))
        print(f"回传完成: {LOCAL_CKPT} ({LOCAL_CKPT.stat().st_size} B)")
    except FileNotFoundError:
        print("未找到最佳权重, 检查训练日志")
    sftp.close()
    c.close()
    print("===DONE=== 抠像集成训练管线完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
