"""style_card_compliance.py — 风格卡达标度自检（感知反向驱动剪辑决策）

方法论依据 (2026-08-16 技术路线参考):
  OmniScientist "感知层塑造研究问题" → 让视觉感知反向驱动剪辑决策。
  本脚本实现闭环: 渲染 → 感知评分 → 反推品味旋钮实测 → 对比风格卡目标 → 偏差驱动动作。

与 taste_contract.py 的关系:
  taste_contract 定义"导演应该怎么剪" (三旋钮 → 运镜池/决策规则, 前向)
  compliance 校验"剪出来的实际符不符合品味契约" (感知实测 → 偏差 → 修正, 反馈)

旋钮感知映射 (评分 → 旋钮, 标注置信度):
  motion_intensity     ← dynamism 评分          (直接, 高置信)
  节奏/卡点对齐          ← pacing 评分            (直接, 高置信)
  visual_variance      ← 需多段 dynamism 方差     (单视频不可测, 低置信, 用 psize/dynamism 代理)
  information_density  ← composition 反向         (代理, 低置信: 高分=主体清晰=信息不过载)

动作表 (偏差 → 修正):
  motion_intensity 实测 < 目标 → 运镜池升级 + 粒子 punch 加强
  pacing 实测 < 目标          → 节拍事件密度提升 (卡点更密)
  composition 实测 < 目标     → 粒子缩小 (防遮挡)
  text_read 实测 < 目标       → 主标题字号增大

用法:
  python scripts/style_card_compliance.py --video output/m2_iteration/round4.mp4 \
      --style amv_highenergy [--scorer hybrid|local|qwen]
输出:
  output/m2_iteration/style_compliance.json  (达标报告 + 修正动作)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from knowledge.style_card import load_card  # noqa: E402
from core.cnn_scorer import score_video_mode  # noqa: E402

# 评分维度 → 旋钮映射 (键: 旋钮, 值: (评分键, 置信度, 方向))
KNOB_MAP = [
    ("motion_intensity",    "score_dynamism", "high", 1.0),
    ("pacing_alignment",    "score_pacing",   "high", 1.0),
    ("composition_clarity", "score_composition", "medium", 1.0),
    ("text_readability",    "score_text_read",   "medium", 1.0),
]

# 风格卡旋钮字段 → 感知旋钮对照 (风格卡没有的直接旋钮字段跳过)
CARD_KNOB_FIELDS = {
    "motion_intensity": None,        # 风格卡无 motion_intensity 字段(在 taste_profile 里)
    "pacing_alignment": "target_beat_alignment",   # 0-1, ×10 对齐 0-10
    "composition_clarity": None,
    "text_readability": None,
}


def compliance(video: str, style_id: str, scorer: str) -> dict:
    card = load_card(style_id)
    # 风格卡三旋钮目标 (优先 card 内嵌, 缺省用默认 5)
    target_knobs = {
        "motion_intensity": getattr(card, "motion_intensity", 5) if hasattr(card, "motion_intensity") else 5,
        "pacing_alignment": card.target_beat_alignment * 10 if getattr(card, "target_beat_alignment", None) else 6,
        "composition_clarity": 7,  # 无风格卡字段, 用通用目标 (主体清晰优先)
        "text_readability": 7,
    }
    score = score_video_mode(video, scorer)
    if score.get("error"):
        return {"error": score["error"]}
    scores = score.get("scores", {})

    knobs = {}
    for knob, score_key, conf, _ in KNOB_MAP:
        val = scores.get(score_key)
        if val is None:
            continue
        knobs[knob] = {"obs": round(float(val), 2), "target": target_knobs[knob], "conf": conf,
                       "gap": round(float(val) - target_knobs[knob], 2)}

    # 偏差驱动动作 (只对高置信旋钮 + 未达标)
    actions = []
    if knobs.get("motion_intensity", {}).get("gap", 0) < -0.5:
        actions.append({"action": "boost_motion",
                        "reason": f"motion_intensity 实测{knobs['motion_intensity']['obs']} < 目标{knobs['motion_intensity']['target']}",
                        "detail": "运镜池升级 + 粒子 punch 加强"})
    if knobs.get("pacing_alignment", {}).get("gap", 0) < -0.5:
        actions.append({"action": "tighten_beat",
                        "reason": f"pacing 实测{knobs['pacing_alignment']['obs']} < 目标{knobs['pacing_alignment']['target']}",
                        "detail": "节拍事件密度提升"})
    if knobs.get("composition_clarity", {}).get("gap", 0) < -0.5:
        actions.append({"action": "shrink_particles",
                        "reason": f"composition 实测{knobs['composition_clarity']['obs']} < 目标{knobs['composition_clarity']['target']}",
                        "detail": "粒子缩小防遮挡"})
    if knobs.get("text_readability", {}).get("gap", 0) < -0.5:
        actions.append({"action": "enlarge_title",
                        "reason": f"text_read 实测{knobs['text_readability']['obs']} < 目标{knobs['text_readability']['target']}",
                        "detail": "主标题字号增大"})

    result = {
        "style": style_id,
        "video": video,
        "scorer": scorer,
        "scores": {k: v for k, v in scores.items() if k.startswith("score_")},
        "knob_compliance": knobs,
        "actions": actions,
        "source": score.get("source", {}),
    }
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--style", required=True)
    ap.add_argument("--scorer", default="hybrid", choices=["local", "hybrid", "qwen"])
    args = ap.parse_args()

    r = compliance(args.video, args.style, args.scorer)
    out = PROJECT / "output" / "m2_iteration" / "style_compliance.json"
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    if r.get("error"):
        print(f"错误: {r['error']}")
        return 1

    print(f"\n=== 风格卡达标度: {args.style} ({args.scorer}) ===")
    for knob, k in r["knob_compliance"].items():
        mark = "✅" if k["gap"] >= 0 else ("⚠️" if k["gap"] > -0.8 else "❌")
        print(f"  {mark} {knob:<22} 实测 {k['obs']:.2f} / 目标 {k['target']} (gap {k['gap']:+.2f}, {k['conf']})")
    print(f"\n修正动作 ({len(r['actions'])}):")
    for a in r["actions"]:
        print(f"  → {a['action']}: {a['reason']} | {a['detail']}")
    if not r["actions"]:
        print("  全部达标 ✅")
    print(f"\n报告: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
