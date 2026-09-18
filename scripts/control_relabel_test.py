"""对照实验: 严格 prompt 的自洽性检验。

对 30 条原高置信(>=0.85)单一方向镜头用同一严格 prompt 重标,
若与原标签一致率 >=90% → prompt 稳定, complex 改标可信;
若一致率低 → prompt 噪声大, 清洗结果应作废。
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.relabel_complex_shots import extract_frames, relabel  # noqa: E402

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
LABELS_FILE = DATA_ROOT / "vlm_labels.jsonl"


def main() -> int:
    rows = [json.loads(l) for l in LABELS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    control = [r for r in rows
               if r.get("movement_label") not in ("complex",)
               and float(r.get("confidence", 0)) >= 0.85]
    random.seed(42)
    control = random.sample(control, 30)
    print(f"对照集: {len(control)} 条高置信单一方向")

    import os

    from openai import OpenAI
    api_key = os.environ.get("SILICONFLOW_API_KEY", "")
    if not api_key:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("SILICONFLOW_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")

    agree = 0
    total = 0
    for r in control:
        try:
            frames = extract_frames(r["clip_path"])
            result, _ = relabel(client, frames)
        except Exception as exc:  # noqa: BLE001
            print(f"  {r['shot_id']} 异常: {str(exc)[:40]}")
            continue
        total += 1
        new_d = (result or {}).get("direction", "")
        if new_d == r["movement_label"]:
            agree += 1
            print(f"  {r['shot_id']} {r['movement_label']:12s} -> {new_d:12s} 一致")
        else:
            print(f"  {r['shot_id']} {r['movement_label']:12s} -> {new_d:12s} ✗不一致")
    acc = agree / total if total else 0
    print(f"\n=== 对照一致率: {acc:.2%} ({agree}/{total}) ===")
    print("判定: " + ("prompt 稳定, complex 改标可信 ✅" if acc >= 0.9
                     else ("prompt 有噪声, 清洗结果需人工抽验 ⚠️" if acc >= 0.7
                           else "prompt 不可靠, 清洗结果作废 ❌")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
