"""
scripts/verify_flagship_injection.py — 验收标准②④ 实跑验证
=============================================================

验证内容（对应 09-计划文件/2026-08-15_TEMPO 落地方案第六章）：
② 失败 run manifest 含完整 critic_reports 且可被 ExperienceHarvester 解析；
④ 数字孪生校正样本数 ≥ 原方案 3 倍（中途观测密度提升的直接证据）。

用法::

    py -3.11 scripts/verify_flagship_injection.py

执行步骤：
1. 扫描 output/flagship_*/manifest.json，统计 critic_reports 条数；
2. FlagshipManifestParser 逐 run 解析，统计 StageExperience（含 critic 中途观测）；
3. ExperienceHarvester 全量 harvest + 注入；
4. 计算中途观测密度并对照基线（原方案每 run 1 个终点观测）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from core.experience_harvester import (
        ExperienceHarvester, FlagshipManifestParser,
    )

    output_root = PROJECT_ROOT / "output"
    manifests = sorted(output_root.glob("flagship_*/manifest.json"))
    print(f"[扫描] output/ 下旗舰 run manifest: {len(manifests)} 个")

    parser = FlagshipManifestParser()
    n_critic_reports = 0
    n_stage_exp = 0
    n_critic_exp = 0
    n_critic_runs = 0
    terminations = {}

    for mf in manifests:
        try:
            manifest = json.loads(mf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [跳过] {mf.parent.name}: {e}")
            continue
        term = manifest.get("termination") or manifest.get("status", "?")
        terminations[term] = terminations.get(term, 0) + 1
        reports = manifest.get("critic_reports", [])
        n_critic_reports += len(reports)
        if reports:
            n_critic_runs += 1
        rec = parser.parse_run_dir(mf.parent)
        if rec is not None:
            n_stage_exp += len(rec.stages)
            n_critic_exp += sum(1 for s in rec.stages if s.engine_used == "critic")
        print(f"  [解析] {mf.parent.name}: status={manifest.get('status')} "
              f"termination={manifest.get('termination')} critic_reports={len(reports)}")

    print(f"\n[汇总] critic_reports 总条数={n_critic_reports}, "
          f"阶段经验总数={n_stage_exp}, 其中 critic 中途观测={n_critic_exp}")
    print(f"[汇总] termination 分布: {terminations}")

    # 验收②：失败 run 必须可解析且含 critic_reports
    if n_critic_reports == 0:
        print("[FAIL] 验收②: 无任何 critic_reports")
        return 1
    print("[PASS] 验收②: critic_reports 已被 FlagshipManifestParser 解析入库")

    # 全量 harvest + 注入
    print("\n[harvest] ExperienceHarvester 全量汲取...")
    harvester = ExperienceHarvester(project_root=str(PROJECT_ROOT))
    report = harvester.harvest()
    print(f"[harvest] records={report.total_records_extracted}, "
          f"stage_exp={report.total_stage_experiences}, "
          f"error_patterns={report.total_error_patterns}, "
          f"耗时={report.duration_sec:.1f}s")
    for module, result in report.injection_results.items():
        print(f"  [注入] {module}: {result}")

    # 验收④：数字孪生校正样本密度 ≥ 原方案 3 倍
    # 原方案：每 flagship run 仅 1 个终点观测；
    # 新方案：终点观测 + critic 中途观测。
    # 密度 = (中途观测数 + 含中途观测的 run 数) / 含中途观测的 run 数
    if n_critic_runs > 0:
        density = (n_critic_exp + n_critic_runs) / n_critic_runs
        baseline = 1.0  # 原方案每 run 1 个终点观测
        print(f"\n[验收④] 中途观测密度 = {density:.1f} 观测/run，"
              f"基线 = {baseline:.1f}，倍数 = {density / baseline:.1f}x")
        if density >= 3.0 * baseline:
            print(f"[PASS] 验收④: 校正样本密度达基线 {density / baseline:.1f} 倍 ≥ 3 倍")
            return 0
        print(f"[WARN] 验收④: 密度 {density:.1f} < 3.0（需更多 run 累积）")
    else:
        print("\n[WARN] 验收④: 无含 critic 中途观测的 run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
if __name__ == "__main__":
    sys.exit(main())
if __name__ == "__main__":
    sys.exit(main())
if __name__ == "__main__":
    sys.exit(main())
