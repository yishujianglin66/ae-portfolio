"""collect_until_n.py — 无人值守样本采集循环

循环跑 collect_tuning_data.py 直到 train_samples.jsonl 达到目标条数,
完成后自动重训调参器。设计:
  - 每轮最多采 BATCH 个组合（避免单进程过长, 单轮崩了下轮继续）
  - 每次启动前检查样本数, 达到 target 即停
  - 异常/单轮失败不影响后续轮（try/except 包裹）

用法:
  python scripts/collect_until_n.py [--target 50] [--batch 10]

日志: 后台任务输出即进度; 每轮结束打印样本数。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SAMPLES = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"


def count_samples() -> int:
    """统计唯一帧目录样本数 (帧↔参数唯一对齐 = CNN 可用)。

    2026-08-16 修正: 原统计带帧总数, 但旧批次 sample_* 目录被 48 样本共享
    (帧↔参数错位) 虚高。唯一目录数 = 真正可训 CNN 的干净样本数。
    """
    if not SAMPLES.exists():
        return 0
    try:
        seen = set()
        for l in SAMPLES.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            fd = r.get("frame_dir", "")
            if fd and Path(fd).exists() and not Path(fd).name.startswith("sample_"):
                seen.add(fd)
        return len(seen)
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    print(f"[collect] 目标 {args.target} 样本, 每轮 {args.batch} 组合", flush=True)
    seed = args.seed
    round_no = 0
    while count_samples() < args.target:
        round_no += 1
        n_need = args.target - count_samples()
        n_run = min(args.batch, n_need)
        print(f"\n=== 第 {round_no} 轮: 采集 {n_run} 组合 (当前 {count_samples()}/{args.target}) ===", flush=True)
        try:
            r = subprocess.run(
                [sys.executable, str(PROJECT / "scripts" / "collect_tuning_data.py"),
                 "--n", str(n_run), "--seed", str(seed)],
                cwd=str(PROJECT), timeout=3600, text=True)
            seed += 1
            if r.returncode != 0:
                print(f"[collect] 本轮返回码 {r.returncode}, 5s 后重试", flush=True)
                time.sleep(5)
        except subprocess.TimeoutExpired:
            print(f"[collect] 本轮超时, 检查后继续", flush=True)
            time.sleep(10)
        except Exception as e:  # noqa: BLE001
            print(f"[collect] 异常: {e}, 30s 后继续", flush=True)
            time.sleep(30)

    # 达到目标 → 重训调参器
    print(f"\n[collect] 达到目标 {args.target} 样本, 重训调参器...", flush=True)
    subprocess.run([sys.executable, str(PROJECT / "scripts" / "train_param_tuner.py")],
                   cwd=str(PROJECT), timeout=300)
    print(f"[collect] 完成! 样本 {count_samples()}, 调参器已重训", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
