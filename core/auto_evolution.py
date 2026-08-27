#!/usr/bin/env python3
"""
auto_evolution.py — 自动数据采集 + 定时进化触发器
===================================================

功能:
  1. scan_and_capture: 扫描导演系统输出目录，自动写入 ExecutionRecord
  2. run_evolution_cycle: 执行一轮进化循环（经验蒸馏 + 策略进化）
  3. run_acceptance: 跑回归验收
  4. daily_routine: 每日例行任务（采集 + 进化 + 验收 + 报告）

用法:
  # 单次采集（导演系统出片后手动触发）
  py -3.12 -m core.auto_evolution --scan

  # 跑一轮进化
  py -3.12 -m core.auto_evolution --evolve

  # 每日例行（采集 + 进化 + 验收）
  py -3.12 -m core.auto_evolution --daily

  # 注册 Windows 计划任务（每天凌晨 3 点自动跑）
  py -3.12 -m core.auto_evolution --register-task
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 项目根
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("auto_evolution")

# 自进化数据目录收口到 core.paths（运行时产物移出代码仓库）
try:
    from core.paths import self_evolution_dir as _paths_evo_dir
    EVO_DIR = Path(_paths_evo_dir())
except ImportError:
    EVO_DIR = ROOT / "data" / "self_evolution"

KNOWLEDGE_PATH = EVO_DIR / "evolution_knowledge.jsonl"


def distill_review_knowledge(reviews: List[Dict], sink_path: str = None) -> int:
    """将 review 结果蒸馏为知识行追加落盘(D4 修复: 知识积累停滞)。

    返回新增条数; 同 run_id 不重复写入。
    """
    sink = Path(sink_path) if sink_path else KNOWLEDGE_PATH
    if not reviews:
        return 0
    seen = set()
    if sink.exists():
        for line in sink.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(line).get("run_id"))
            except json.JSONDecodeError:
                continue
    added = 0
    sink.parent.mkdir(parents=True, exist_ok=True)
    with open(sink, "a", encoding="utf-8") as f:
        for r in reviews:
            rid = r.get("run_id")
            if not rid or rid in seen:
                continue
            entry = {
                "run_id": rid,
                "quality": r.get("quality"),
                "deviation": r.get("deviation"),
                "success": r.get("success"),
                "failure_mode": (r.get("quality") or 0) < 60 or not r.get("success", True),
                "distilled_at": time.time(),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            seen.add(rid)
            added += 1
    return added


# ============================================================
# 1. 自动数据采集 — 扫描导演系统输出
# ============================================================

# 已知输出目录（导演系统 + 管线输出）
OUTPUT_DIRS = [
    ROOT / "output_director",
    ROOT / "output_production",
    Path("D:/output_director"),
]

# 已处理的 run_id 记录
PROCESSED_LOG = EVO_DIR / "processed_outputs.jsonl"


def _load_processed() -> set:
    """加载已处理的输出路径"""
    processed = set()
    if PROCESSED_LOG.exists():
        with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        processed.add(json.loads(line).get("output_path"))
                    except json.JSONDecodeError:
                        pass
    return processed


def _mark_processed(output_path: str, record: Dict):
    """标记为已处理"""
    PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"output_path": output_path, **record}, ensure_ascii=False) + "\n")


def _probe_video(path: str) -> Dict[str, Any]:
    """用 ffprobe 探测视频信息"""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15,
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            fmt = data.get("format", {})
            video_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
            if video_streams:
                vs = video_streams[0]
                return {
                    "duration": float(fmt.get("duration", 0)),
                    "size_mb": round(int(fmt.get("size", 0)) / 1024 / 1024, 2),
                    "width": int(vs.get("width", 0)),
                    "height": int(vs.get("height", 0)),
                    "codec": vs.get("codec_name", "unknown"),
                    "fps": eval(vs.get("r_frame_rate", "0/1")) if "/" in vs.get("r_frame_rate", "") else float(vs.get("r_frame_rate", 0)),
                }
    except Exception:
        pass
    return {}


def scan_and_capture() -> int:
    """扫描所有输出目录，发现新视频并写入 ExecutionRecord

    Returns:
        新发现并处理的视频数量
    """
    from core.self_evolution_engine import get_evolution_engine, ExecutionRecord

    processed = _load_processed()
    engine = get_evolution_engine()
    new_count = 0

    for out_dir in OUTPUT_DIRS:
        if not out_dir.exists():
            continue

        # 递归查找所有 .mp4 / .mov 文件
        for ext in ("*.mp4", "*.mov"):
            for video_path in out_dir.rglob(ext):
                path_str = str(video_path.resolve())

                # 跳过已处理
                if path_str in processed:
                    continue

                # 探测视频信息
                info = _probe_video(path_str)
                if not info or info.get("duration", 0) < 1:
                    continue

                # 从路径推断上下文
                rel_path = video_path.relative_to(out_dir.parent) if out_dir.parent in video_path.parents else video_path.name
                parts = rel_path.parts

                # 构建 ExecutionRecord
                record = ExecutionRecord(
                    run_id=f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{video_path.stem[:12]}",
                    timestamp=video_path.stat().st_mtime,
                    stages={
                        "source": "auto_capture",
                        "output_dir": str(out_dir),
                    },
                    input_spec={
                        "source_type": "director_system",
                        "output_path": path_str,
                    },
                    config={
                        "auto_captured": True,
                        "file_name": video_path.name,
                        "relative_path": str(rel_path),
                    },
                    output_path=path_str,
                    output_quality=0.0,  # 由 engine 自动评估
                    success=True,
                    total_duration=info.get("duration", 0),
                    strategy_id="auto_capture",
                )

                # 提交评审
                try:
                    loop = asyncio.new_event_loop()
                    review = loop.run_until_complete(engine.post_execution_review(record))
                    loop.close()

                    _mark_processed(path_str, {
                        "run_id": record.run_id,
                        "quality": review.quality.overall_score,
                        "captured_at": time.time(),
                        "video_info": info,
                    })

                    logger.info(
                        f"Captured: {video_path.name} "
                        f"({info.get('duration', 0):.0f}s, {info.get('size_mb', 0):.1f}MB) "
                        f"→ quality={review.quality.overall_score:.1f}"
                    )
                    new_count += 1

                except Exception as e:
                    logger.warning(f"Failed to capture {video_path.name}: {e}")

    logger.info(f"Scan complete: {new_count} new videos captured")
    return new_count


# ============================================================
# 2. 进化循环
# ============================================================

def run_evolution_cycle(task_type: str = "style_transfer", iterations: int = 2) -> Dict:
    """执行一轮进化循环

    Returns:
        进化报告摘要
    """
    from core.evolution.run_evolution import EvolutionLoop
    from core.evolution.evaluator import EvolutionEvaluator
    from core.evolution.optimizer_agent import get_optimizer_agent
    from core.evolution.version_manager import get_version_manager

    logger.info(f"Starting evolution cycle: task={task_type}, iterations={iterations}")

    evaluator = EvolutionEvaluator(
        benchmark_dir=str(ROOT / "data" / "benchmark"),
        enable_rubrics=False,  # 离线模式不用 LLM rubrics
    )
    loop = EvolutionLoop(
        evaluator=evaluator,
        optimizer=get_optimizer_agent(),
        version_manager=get_version_manager(data_dir=str(ROOT / "data" / "versions")),
        task_type=task_type,
        execute_real=False,  # 模拟模式，不真实渲染
    )

    report = loop.run(iterations=iterations, blind_test=True)
    logger.info(f"Evolution cycle complete: status={report.get('status')}")
    return report


# ============================================================
# 3. 回归验收
# ============================================================

def run_acceptance() -> Dict:
    """跑回归验收

    Returns:
        验收报告
    """
    logger.info("Running acceptance tests...")

    try:
        r = subprocess.run(
            [sys.executable, "-m", "ai.accept_runner", "--quick"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(ROOT), timeout=300,
        )
        # 找最新的 accept 报告
        reports_dir = ROOT / "reports"
        accept_reports = sorted(reports_dir.glob("accept_*.json"), reverse=True)
        if accept_reports:
            with open(accept_reports[0], "r", encoding="utf-8") as f:
                report = json.load(f)
            logger.info(f"Acceptance: pass_rate={report.get('ip_proto_v1', {}).get('pass_rate', '?')}")
            return report
    except Exception as e:
        logger.warning(f"Acceptance test failed: {e}")
        return {"error": str(e)}

    return {"error": "acceptance report not found"}


# ============================================================
# 4. 每日例行
# ============================================================

def daily_routine() -> Dict:
    """每日例行任务: 采集 → 进化 → 验收 → 汇总

    Returns:
        每日例行报告
    """
    start = time.time()
    report = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "started_at": datetime.now().isoformat(),
        "steps": {},
    }

    # Step 1: 扫描采集
    logger.info("=" * 50)
    logger.info("Step 1/3: Scanning & capturing new outputs...")
    logger.info("=" * 50)
    try:
        captured = scan_and_capture()
        report["steps"]["scan_capture"] = {"status": "ok", "new_videos": captured}
    except Exception as e:
        report["steps"]["scan_capture"] = {"status": "error", "error": str(e)}
        logger.error(f"Scan failed: {e}")

    # Step 1.5: D4 蒸馏新采集记录的 review 知识
    try:
        state_file = EVO_DIR / "evolution_state.json"
        if state_file.exists():
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            n = distill_review_knowledge(state.get("review_history", [])[-50:])
            report["steps"]["knowledge_distill"] = {"status": "ok", "new": n}
        else:
            report["steps"]["knowledge_distill"] = {"status": "skip", "reason": "no state file"}
    except Exception as e:
        report["steps"]["knowledge_distill"] = {"status": "error", "error": str(e)}

    # Step 2: 进化循环
    logger.info("=" * 50)
    logger.info("Step 2/3: Running evolution cycle...")
    logger.info("=" * 50)
    try:
        evo_report = run_evolution_cycle(iterations=2)
        report["steps"]["evolution"] = {
            "status": "ok",
            "report_status": evo_report.get("status"),
            "iterations": evo_report.get("iterations_completed", 0),
        }
    except Exception as e:
        report["steps"]["evolution"] = {"status": "error", "error": str(e)}
        logger.error(f"Evolution failed: {e}")

    # Step 3: 回归验收
    logger.info("=" * 50)
    logger.info("Step 3/3: Running acceptance tests...")
    logger.info("=" * 50)
    try:
        accept_report = run_acceptance()
        report["steps"]["acceptance"] = {
            "status": "ok" if "error" not in accept_report else "error",
            "pass_rate": accept_report.get("ip_proto_v1", {}).get("pass_rate"),
            "regression_gate": accept_report.get("regression_gate", {}),
        }
    except Exception as e:
        report["steps"]["acceptance"] = {"status": "error", "error": str(e)}

    # 汇总
    report["duration_sec"] = round(time.time() - start, 1)
    report["completed_at"] = datetime.now().isoformat()

    # 保存报告
    report_dir = ROOT / "reports" / "auto_evolution"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"daily_{report['date']}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'=' * 50}")
    logger.info(f"Daily routine complete in {report['duration_sec']}s")
    logger.info(f"Report: {report_path}")
    logger.info(f"{'=' * 50}")

    return report


# ============================================================
# 5. Windows 计划任务注册
# ============================================================

def register_scheduled_task():
    """注册 Windows 计划任务: 每天凌晨 3:00 自动跑 daily_routine"""
    task_name = "AE_Vault_Daily_Evolution"
    python_exe = sys.executable
    script_path = str(ROOT / "core" / "auto_evolution.py")

    # 创建计划任务的 schtasks 命令（参数列表形式，禁止 shell=True 防命令注入）
    cmd = [
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", f'"{python_exe}" "{script_path}" --daily',
        "/sc", "daily",
        "/st", "03:00",
        "/f",
        "/rl", "highest",
    ]

    logger.info(f"Registering scheduled task: {task_name}")
    logger.info(f"  Schedule: Daily at 03:00")

    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        if r.returncode == 0:
            logger.info("Scheduled task registered successfully!")
            logger.info(f"  Run: schtasks /run /tn \"{task_name}\"  (手动触发)")
            logger.info(f"  Query: schtasks /query /tn \"{task_name}\"")
            logger.info(f"  Delete: schtasks /delete /tn \"{task_name}\" /f")
            return True
        else:
            logger.error(f"Failed: {r.stderr}")
            return False
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        return False


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="自进化自动数据采集 + 定时触发器",
    )
    parser.add_argument("--scan", action="store_true", help="扫描输出目录，采集新视频")
    parser.add_argument("--evolve", action="store_true", help="执行一轮进化循环")
    parser.add_argument("--accept", action="store_true", help="跑回归验收")
    parser.add_argument("--daily", action="store_true", help="每日例行: 采集+进化+验收")
    parser.add_argument("--register-task", action="store_true", help="注册 Windows 计划任务")
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    args = parser.parse_args()

    if args.status:
        _print_status()
        return

    if args.scan:
        scan_and_capture()
        return

    if args.evolve:
        run_evolution_cycle()
        return

    if args.accept:
        run_acceptance()
        return

    if args.daily:
        daily_routine()
        return

    if args.register_task:
        register_scheduled_task()
        return

    # 无参数时显示帮助
    parser.print_help()


def _print_status():
    """打印当前自进化系统状态"""
    from core.memory_store import memory_store

    print("=" * 60)
    print("自进化系统状态")
    print("=" * 60)

    # MemoryStore
    stats = memory_store.get_stats()
    print(f"\nMemoryStore: {stats['total_memories']} memories, avg_conf={stats['avg_confidence']}")
    for cat, count in sorted(stats.get("categories", {}).items()):
        print(f"  {cat}: {count}")

    # FeedbackStore
    from learning.parameter_optimizer import FeedbackStore
    fs = FeedbackStore()
    print(f"\nFeedbackStore: {fs.count} records")

    # Evolution state
    state_path = EVO_DIR / "evolution_state.json"
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        print(f"\nEvolution state:")
        print(f"  review_history: {len(state.get('review_history', []))} reviews")
        print(f"  last_evolution_run: {state.get('last_evolution_run', 0)}")

    # Processed outputs
    if PROCESSED_LOG.exists():
        with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        print(f"\nProcessed outputs: {len(lines)} videos captured")

    # Daily reports
    daily_dir = ROOT / "reports" / "auto_evolution"
    if daily_dir.exists():
        reports = sorted(daily_dir.glob("daily_*.json"))
        print(f"\nDaily reports: {len(reports)}")
        if reports:
            latest = reports[-1]
            with open(latest, "r", encoding="utf-8") as f:
                r = json.load(f)
            print(f"  Latest: {r.get('date')} ({r.get('duration_sec', 0):.0f}s)")

    # Benchmark
    train_path = ROOT / "data" / "benchmark" / "train" / "initial_tasks.json"
    if train_path.exists():
        with open(train_path, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        print(f"\nBenchmark tasks: {len(tasks)} total")

    # Eval history
    hist_path = ROOT / "data" / "benchmark" / "results" / "evaluation_history.jsonl"
    if hist_path.exists():
        with open(hist_path, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        print(f"Evaluation history: {len(lines)} records")

    # Windows task
    try:
        r = subprocess.run(
            ["schtasks", "/query", "/tn", "AE_Vault_Daily_Evolution"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        if r.returncode == 0:
            print(f"\nScheduled task: REGISTERED (AE_Vault_Daily_Evolution)")
        else:
            print(f"\nScheduled task: NOT REGISTERED")
    except Exception:
        print(f"\nScheduled task: UNKNOWN")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
