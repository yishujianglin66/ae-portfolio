"""morning_pipeline.py — 晨间后处理管线（通宵采集完成后一条命令跑全链）

采集 100 干净样本后依次执行:
  1. 重建 clean_index (唯一帧目录)
  2. 重编码 CLIP 嵌入 (--clean)
  3. 重训 CNN Ridge 头
  4. calibrate_gold_set 签名自愈 (新样本命中黄金签名 → 补 frame_dir/cnn/gbdt)
  5. calibrate_cnn_head 重标定 (LOOCV ≥10% 才写入)
  6. eval_gold_benchmark 基准
  7. 回归测试 test_gold_benchmark

用法:
  python scripts/morning_pipeline.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

SAMPLES = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"


def step(name, fn):
    print(f"\n=== {name} ===")
    r = fn()
    ok = r if isinstance(r, bool) else r.returncode == 0
    print(f"{'✅' if ok else '❌'} {name}")
    return ok


def rebuild_clean_index() -> bool:
    rows = [json.loads(l) for l in SAMPLES.read_text(encoding="utf-8").splitlines() if l.strip()]
    seen = {}
    for i, r in enumerate(rows):
        fd = r.get("frame_dir")
        if fd:
            seen.setdefault(fd, []).append(i)
    clean = sorted(idxs[0] for fd, idxs in seen.items()
                   if len(idxs) == 1 and not Path(fd).name.startswith("sample_"))
    (PROJECT / "data" / "param_tuning" / "clean_index.json").write_text(
        json.dumps({"clean_row_idx": clean}, indent=2), encoding="utf-8")
    print(f"干净样本: {len(clean)}/{len(rows)}")
    return len(clean) >= 50


def run(cmd):
    return subprocess.run(cmd, cwd=str(PROJECT), timeout=1800)


def main() -> int:
    ok = True
    ok &= step("① 重建 clean_index", rebuild_clean_index)
    ok &= step("② 重编码嵌入", lambda: run(
        [sys.executable, "scripts/encode_tuning_frames.py", "--clean"]))
    ok &= step("③ 重训 CNN 头", lambda: run(
        [sys.executable, "-m", "core.cnn_scorer", "--train"]))
    ok &= step("④ 黄金集签名自愈", lambda: run(
        [sys.executable, "scripts/calibrate_gold_set.py"]))
    ok &= step("⑤ CNN 黄金重标定", lambda: run(
        [sys.executable, "scripts/calibrate_cnn_head.py", "--write"]))
    ok &= step("⑥ 黄金基准", lambda: run(
        [sys.executable, "scripts/eval_gold_benchmark.py"]))
    ok &= step("⑦ 回归测试", lambda: run(
        [sys.executable, "-m", "pytest", "tests/test_gold_benchmark.py", "-q"]))
    print(f"\n{'🎉 全链完成' if ok else '⚠ 有失败步骤, 见上'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
