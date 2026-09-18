"""rescore_fine.py — 用小数版 prompt 重评分带帧样本（细粒度标签）

旧标签是 qwen 整数版(3 档), 粒度粗导致调参器无法区分 7.3 vs 7.6。
小数版 prompt 已实证能出小数分(6.5/7.2 等)。对 38 带帧样本重评分,
更新 train_samples.jsonl 的评分标签（保留参数特征）。

用法: python scripts/rescore_fine.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
from core.visual_scorer import _PROMPT, _call_qwen_vl, _frame_to_b64

SAMPLES = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"

def main() -> int:
    rows = [json.loads(l) for l in SAMPLES.read_text(encoding="utf-8").splitlines() if l.strip()]
    # 备份
    SAMPLES.with_suffix(".jsonl.bak_int").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"备份整数标签: {len(rows)} 条")

    updated = 0
    for i, r in enumerate(rows):
        fd = r.get("frame_dir", "")
        if not fd or not Path(fd).exists():
            continue
        frames = sorted(Path(fd).glob("*.jpg"))
        if len(frames) < 2:
            continue
        b64s = [_frame_to_b64(str(f)) for f in frames[:3]]
        res = _call_qwen_vl(b64s, _PROMPT)
        sc = res.get("scores", {})
        if not sc:
            print(f"  [{i}] 评分失败: {res.get('error')}")
            continue
        for dim in ["dynamism","composition","color_harmony","text_read","texture","pacing"]:
            v = sc.get(dim)
            if v is not None:
                r[f"score_{dim}"] = float(v)
        ov = res.get("overall")
        if ov is not None:
            r["score_overall"] = float(ov)
        r["_fine"] = True
        updated += 1
        if updated % 5 == 0:
            print(f"  已重评 {updated}", flush=True)
        time.sleep(0.3)

    # 落盘（保留原顺序）
    SAMPLES.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"重评完成: {updated}/{len(rows)} 带帧样本 → 小数标签")
    return 0

if __name__ == "__main__":
    sys.exit(main())
