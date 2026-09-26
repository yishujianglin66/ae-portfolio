# -*- coding: utf-8 -*-
"""T18: 端到端零点击生产 — 一条命令从素材到成片。

流程: 检索选片→导演编排→ShotScript→Resolve→AE→回Resolve调色→渲染交付
验收: 进击的巨人主题90s AMV从命令到成片零人工点击。

v2: 接入真实语料库(D:\aot_corpus)镜头数据，自动编排满足目标时长。

v3 (2026-09-26, FIX-02/契约 docs/execution_result_contract.md):
  诚实化退出码与成功语义——未真实渲染不得报 success=True/exit 0。
  退出码: 0=真实生产完成且产物 ffprobe 可验; 4=dry_run 流程冒烟通过(仿真，非生产结论); 1=失败。
  报告字段: execution_path ∈ {real, simulated, failed}; dry_run_completed 与 success 分离。
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.stdout.reconfigure(encoding="utf-8")
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from ai.ae_executor import AEExecutor
from ai.resolve_executor import ResolveExecutor
from ai.shot_script import ShotScript, ShotUnit, SpeedSegment, TextOverlay, create_shot_script

# 情绪曲线模板: (mood, scene_type, speed_range)
EMOTION_CURVE = [
    ("calm",      "scenery",   (0.8, 1.0)),   # 开篇铺陈
    ("building",  "action",    (0.9, 1.1)),   # 情绪爬升
    ("intense",   "action",    (1.0, 1.3)),   # 高燃段
    ("climax",    "action",    (1.2, 1.5)),   # 最高潮
    ("intense",   "action",    (1.0, 1.2)),   # 余韵
    ("calm",      "scenery",   (0.8, 1.0)),   # 收尾
]

# 文字叠加模板
TEXT_TEMPLATES = [
    {"text": "{theme}之魂",   "animation": "typewriter",  "position": "center"},
    {"text": "{theme}",       "animation": "fadeCascade", "position": "top"},
    {"text": "BURN",          "animation": "glitchIn",    "position": "center"},
    {"text": "燃",            "animation": "scalePop",    "position": "bottom"},
]

CORPUS_META_PATH = Path(r"D:\aot_corpus\corpus_meta.json")


def _artifact_verified(path: Path) -> bool:
    """内容级产物验证（契约 §2.3）：存在 + ffprobe 可读且时长>0。"""
    if not path.exists() or path.stat().st_size < 1024:
        return False
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        # 无 ffprobe 时不得盲判成功（fail-closed）
        return False
    try:
        r = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="ignore",
        )
        return r.returncode == 0 and float((r.stdout or "0").strip() or 0) > 0
    except Exception:
        return False


def _load_corpus_shots(theme: str, duration_target: float) -> list[dict]:
    """从语料库提取真实镜头时间码，按情绪曲线编排至目标时长。"""
    if not CORPUS_META_PATH.exists():
        return _fallback_shots(theme, duration_target)

    meta = json.loads(CORPUS_META_PATH.read_text(encoding="utf-8"))
    videos = meta.get("videos", [])
    if not videos:
        return _fallback_shots(theme, duration_target)

    # 收集所有可用镜头(带时间码)
    all_shots: list[dict] = []
    for vid in videos:
        vid_name = vid.get("name", "")
        for fr in vid.get("frames", []):
            t_in = fr.get("t_in", 0)
            t_out = fr.get("t_out", 0)
            dur = t_out - t_in
            if 2.0 <= dur <= 12.0:  # 过滤异常镜头
                all_shots.append({
                    "source": vid_name,
                    "t_in": t_in,
                    "t_out": t_out,
                    "dur": dur,
                    "shot_idx": fr.get("shot", 0),
                })

    if not all_shots:
        return _fallback_shots(theme, duration_target)

    # 按情绪曲线选镜头
    random.seed(42)  # 可复现
    selected: list[dict] = []
    total_dur = 0.0
    curve_idx = 0

    while total_dur < duration_target and all_shots:
        mood, scene, speed = EMOTION_CURVE[curve_idx % len(EMOTION_CURVE)]
        # 随机选一个镜头
        candidate = random.choice(all_shots)
        all_shots.remove(candidate)

        # 应用变速
        speed_factor = random.uniform(*speed)
        effective_dur = candidate["dur"] / speed_factor

        selected.append({
            "source": candidate["source"],
            "in": round(candidate["t_in"], 3),
            "out": round(candidate["t_out"], 3),
            "dur": round(candidate["dur"], 3),
            "effective_dur": round(effective_dur, 3),
            "speed_factor": round(speed_factor, 2),
            "mood": mood,
            "scene_type": scene,
            "ip": "进击的巨人",
        })
        total_dur += effective_dur
        curve_idx += 1

    return selected


def _fallback_shots(theme: str, duration_target: float) -> list[dict]:
    """无真实语料时的降级演示数据。"""
    lib_dir = _PROJECT_ROOT / "data" / "real_amv_test"
    sources = [f.name for f in lib_dir.glob("*.mp4") if not f.name.startswith("DL_")]
    if not sources:
        sources = ["demo_source.mp4"]

    selected = []
    total = 0.0
    idx = 0
    while total < duration_target:
        src = sources[idx % len(sources)]
        dur = random.uniform(3.0, 7.0)
        mood_i = (idx // 3) % len(EMOTION_CURVE)
        mood, scene, speed = EMOTION_CURVE[mood_i]
        sf = random.uniform(*speed)
        selected.append({
            "source": src, "in": round(idx * 10.0, 3),
            "out": round(idx * 10.0 + dur, 3), "dur": round(dur, 3),
            "effective_dur": round(dur / sf, 3), "speed_factor": round(sf, 2),
            "mood": mood, "scene_type": scene, "ip": theme,
        })
        total += dur / sf
        idx += 1
    return selected


def exit_code_for(report: dict) -> int:
    """退出码映射（FIX-02，供 CLI 与测试共用，可测化）：

    0=真实产物已验证 / 4=dry_run 冒烟通过（simulated，非生产结论）/ 1=失败。
    """
    if report.get("success"):
        return 0
    if report.get("dry_run_completed"):
        return 4
    return 1


def auto_produce(
    bgm: str = "",
    theme: str = "",
    duration_target: float = 90.0,
    dry_run: bool = True,
) -> dict:
    """零点击端到端生产

    Args:
        bgm: BGM文件路径
        theme: 主题关键词
        duration_target: 目标时长(秒)
        dry_run: 仅模拟不实际执行

    Returns:
        生产报告
    """
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "theme": theme,
        "bgm": bgm,
        "duration_target": duration_target,
        "dry_run": dry_run,
        "steps": [],
        "success": False,
    }

    print("=" * 70)
    print(f"T18 端到端零点击生产 | 主题: {theme} | 目标: {duration_target}s")
    print("=" * 70)

    # Step 1: 检索选片
    print("\n[1/6] 检索选片...")
    t0 = time.time()
    # 优先使用语料库，降级到本地素材库
    corpus_available = CORPUS_META_PATH.exists()
    if corpus_available:
        meta = json.loads(CORPUS_META_PATH.read_text(encoding="utf-8"))
        candidates = [v["name"] for v in meta.get("videos", [])[:10]]
        source_label = "语料库(D:\\aot_corpus)"
    else:
        library_dir = _PROJECT_ROOT / "data" / "real_amv_test"
        candidates = [f.name for f in library_dir.glob("*.mp4")][:10]
        source_label = "本地素材库"

    report["candidates"] = candidates[:5]
    report["step1_retrieve"] = {
        "ok": len(candidates) > 0,
        "count": len(candidates),
        "source": source_label,
        "execution_path": "real",
        "time_s": round(time.time() - t0, 2),
    }
    print(f"  ✅ [{source_label}] 检索到 {len(candidates)} 个候选视频")
    for c in candidates[:3]:
        print(f"     - {c}")

    # Step 2: 导演编排 — 从真实语料自动编排至目标时长
    print("\n[2/6] 导演编排...")
    t0 = time.time()
    script = create_shot_script(
        title=f"{theme}_AMV",
        bgm=bgm,
        theme=theme,
        duration_target=duration_target,
    )

    # 从语料库提取真实镜头并按情绪曲线编排
    corpus_shots = _load_corpus_shots(theme, duration_target)

    for i, data in enumerate(corpus_shots):
        shot = ShotUnit(
            shot_id=i + 1,
            source_video=data["source"],
            in_tc=data["in"],
            out_tc=data["out"],
            duration=data["effective_dur"],
            ip=data["ip"],
            mood=data["mood"],
            scene_type=data["scene_type"],
            speed_curve=[SpeedSegment(0.0, 1.0, data["speed_factor"])],
            # ⚠占位评分（非模型产出，契约 §1 要求显式标记，见 step2 报告 score_source）
            aesthetic_score=round(random.uniform(0.75, 0.95), 3),
            rhythm_score=round(random.uniform(0.80, 0.98), 3),
        )
        # 每8个镜头插入一个文字叠加(高潮点)
        if i > 0 and i % 8 == 0:
            tpl = TEXT_TEMPLATES[(i // 8) % len(TEXT_TEMPLATES)]
            shot.text_overlay = TextOverlay(
                text=tpl["text"].format(theme=theme),
                font="Source Han Sans CN Bold",
                animation=tpl["animation"],
                position=tpl["position"],
                start=0.5,
                duration=min(2.5, data["effective_dur"] * 0.6),
            )
        script.shots.append(shot)

    total_dur = sum(s.duration for s in script.shots)
    report["step2_direct"] = {
        "ok": True,
        "shot_count": len(script.shots),
        "total_duration": total_dur,
        "corpus_driven": corpus_available,
        "execution_path": "real",
        "score_source": "random_placeholder",  # 非真实美学模型，显式声明（契约 §1）
        "time_s": round(time.time() - t0, 2),
    }
    print(f"  ✅ 编排 {len(script.shots)} 个镜头，总时长 {total_dur:.1f}s (目标 {duration_target}s)")
    # 情绪分布统计
    mood_dist = {}
    for s in script.shots:
        mood_dist[s.mood] = mood_dist.get(s.mood, 0) + 1
    print(f"  📊 情绪分布: {mood_dist}")

    # Step 3: ShotScript校验
    print("\n[3/6] ShotScript校验...")
    t0 = time.time()
    errors = script.validate()
    report["step3_validate"] = {
        "ok": len(errors) == 0,
        "errors": errors,
        "execution_path": "real",
        "time_s": round(time.time() - t0, 2),
    }
    if errors:
        print(f"  ⚠️ 校验发现 {len(errors)} 个问题: {errors}")
    else:
        print("  ✅ ShotScript校验通过")

    # 保存ShotScript
    output_dir = _PROJECT_ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    script_path = output_dir / f"{theme}_shot_script.json"
    script.save(script_path)
    print(f"  💾 ShotScript已保存: {script_path}")

    # Step 4: Resolve执行
    print("\n[4/6] Resolve执行...")
    t0 = time.time()
    resolve_exec = ResolveExecutor()
    resolve_report = resolve_exec.execute(script, dry_run=dry_run)
    report["step4_resolve"] = {
        "ok": resolve_report.get("success", False),
        "media_count": resolve_report.get("media_count", 0),
        "dry_run": dry_run,
        "execution_path": "simulated" if dry_run else ("real" if resolve_report.get("success") else "failed"),
        "time_s": round(time.time() - t0, 2),
    }
    if resolve_report.get("success"):
        print(f"  ✅ Resolve执行成功 (dry_run={dry_run})")
    else:
        print(f"  ❌ Resolve执行失败: {resolve_report.get('error')}")

    # Step 5: AE执行
    print("\n[5/6] AE执行...")
    t0 = time.time()
    ae_exec = AEExecutor()
    ae_report = ae_exec.execute(script, dry_run=dry_run)
    report["step5_ae"] = {
        "ok": ae_report.get("success", False),
        "overlay_count": ae_report.get("total_overlays", 0),
        "success_count": ae_report.get("success_count", 0),
        "dry_run": dry_run,
        "execution_path": "simulated" if dry_run else ("real" if ae_report.get("success") else "failed"),
        "time_s": round(time.time() - t0, 2),
    }
    if ae_report.get("success"):
        print(f"  ✅ AE执行成功 (dry_run={dry_run})")
    else:
        print(f"  ❌ AE执行失败: {ae_report.get('error')}")

    # Step 6: 渲染交付 — 成功与否以磁盘真实产物为准（FIX-02，严禁未渲染报 ok）
    print("\n[6/6] 渲染交付...")
    t0 = time.time()
    final_output = output_dir / f"{theme}_AMV.mp4"
    verified = (not dry_run) and _artifact_verified(final_output)
    report["step6_render"] = {
        # dry_run 未执行任何渲染 → ok 必为 False；真实模式仅当产物内容级验证通过才 True
        "ok": verified,
        "executed": not dry_run,
        "artifact_verified": verified,
        "output_path": str(final_output),
        "dry_run": dry_run,
        "execution_path": "simulated" if dry_run else ("real" if verified else "failed"),
        "time_s": round(time.time() - t0, 2),
    }
    if dry_run:
        print(f"  📝 [dry_run/simulated] 未执行渲染，不产出真实产物: {final_output}")
    elif verified:
        print(f"  🎬 渲染产物已验证(ffprobe): {final_output}")
    else:
        print(f"  ❌ 渲染产物缺失或未通过 ffprobe 验证: {final_output}")

    # 总结（契约 §1：success 只属于真实执行；dry-run 另有 dry_run_completed）
    steps_ok = all(
        report[k]["ok"]
        for k in ("step1_retrieve", "step2_direct", "step3_validate",
                  "step4_resolve", "step5_ae", "step6_render")
    )
    dry_flow_ok = dry_run and all(
        report[k]["ok"]
        for k in ("step1_retrieve", "step2_direct", "step3_validate",
                  "step4_resolve", "step5_ae")
    )
    report["dry_run_completed"] = bool(dry_flow_ok)
    report["success"] = bool((not dry_run) and steps_ok)
    report["execution_path"] = "simulated" if dry_run else ("real" if report["success"] else "failed")

    print("\n" + "=" * 70)
    if report["success"]:
        print(f"✅ 端到端生产完成(真实产物已验证) | 主题: {theme}")
    elif dry_flow_ok:
        print(f"📝 DRY_RUN 流程冒烟通过(execution_path=simulated)——不是生产结论 | 主题: {theme}")
    else:
        print("❌ 端到端生产失败")
    print("=" * 70)

    # 保存报告
    report_path = output_dir / f"{theme}_production_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📊 生产报告: {report_path}")

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="T18 端到端零点击生产（退出码: 0=真实产物已验证 / 4=dry_run冒烟通过(simulated) / 1=失败）",
    )
    parser.add_argument("--bgm", type=str, default="", help="BGM文件路径")
    parser.add_argument("--theme", type=str, default="进击的巨人", help="主题关键词")
    parser.add_argument("--duration", type=float, default=90.0, help="目标时长(秒)")
    parser.add_argument("--dry-run", action="store_true", help="仅模拟不实际执行（报告 execution_path=simulated）")
    args = parser.parse_args()

    report = auto_produce(
        bgm=args.bgm,
        theme=args.theme,
        duration_target=args.duration,
        dry_run=args.dry_run,
    )

    # FIX-02: 退出码反映真实产物存在性（审计 F1 根治点）——dry_run 不得以 0 冒充生产成功
    sys.exit(exit_code_for(report))
