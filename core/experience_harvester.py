"""
往期执行经验汲取模块 (Experience Harvester)
=============================================

从项目已有的历史执行记录中自动学习和提取经验，
并将这些经验反哺到管线的智能决策模块中。

数据源:
- logs/ 系统运行日志
- output_production/ 项目执行报告
- test_output_*/ 全链路测试日志
- 00-每日记录/ 开发日记
- data/error_patterns/ 错误模式库
- data/fallback_history.json 降级历史

经验注入目标:
- CausalEngine: 因果图条件概率
- BayesianOptimizer: 参数-效果观测对
- PipelineDigitalTwin: 耗时/成功率校准
- MetaStrategyEngine: Thompson Sampling 先验
- SelfEvolutionEngine: 经验蒸馏

Author: AE-Knowledge-Vault Team
"""

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class StageExperience:
    """单个阶段的执行经验"""
    stage_name: str
    success: bool = True
    duration_sec: float = 0.0
    error_type: str = ""
    error_msg: str = ""
    engine_used: str = ""
    memory_mb: float = 0.0
    quality_score: float = 0.0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperienceRecord:
    """一条完整的执行经验记录"""
    record_id: str = ""
    timestamp: float = 0.0
    source_file: str = ""
    source_type: str = ""          # log / production_report / test_log / daily_note / structured_data
    # 各阶段经验
    stages: list[StageExperience] = field(default_factory=list)
    # 汇总
    overall_success: bool = True
    total_duration: float = 0.0
    overall_quality: float = 0.0
    # 环境
    engines_available: list[str] = field(default_factory=list)
    memory_total_gb: float = 0.0
    memory_available_gb: float = 0.0
    # 提取的错误模式
    error_patterns: list[dict[str, str]] = field(default_factory=list)
    # 原始文本摘要
    raw_summary: str = ""


@dataclass
class HarvestReport:
    """经验汲取报告"""
    total_sources_scanned: int = 0
    total_records_extracted: int = 0
    total_error_patterns: int = 0
    total_stage_experiences: int = 0
    records_by_source: dict[str, int] = field(default_factory=dict)
    injection_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    duration_sec: float = 0.0


# ============================================================================
#  数据源解析器
# ============================================================================

class ProductionReportParser:
    """解析 output_production/production_report.json 格式的完整执行报告"""

    # 阶段名映射
    PHASE_MAP = {
        "Phase 1": "perceive",
        "Phase 2": "execute",
        "Phase 3": "plan",
        "Phase 4": "render",
        "Phase 5": "verify",
        "Phase 6": "verify",
    }

    def parse(self, report_path: str) -> ExperienceRecord | None:
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
        except Exception as e:
            logger.debug(f"[Harvester] Failed to read {report_path}: {e}")
            return None

        record = ExperienceRecord(
            record_id=self._make_id(report_path),
            source_file=report_path,
            source_type="production_report",
            raw_summary=f"Production report: {report.get('timestamp', '')}",
        )

        # 解析时间戳
        ts_str = report.get("timestamp", "")
        if ts_str:
            try:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                record.timestamp = dt.timestamp()
            except ValueError:
                record.timestamp = time.time()

        # 解析内存信息
        mem = report.get("memory_final", {})
        record.memory_total_gb = mem.get("total_gb", 0)
        record.memory_available_gb = mem.get("avail_gb", 0)

        # 解析日志行
        log_lines = report.get("log", [])
        stages = {}
        current_phase = ""
        engines = set()
        errors = []

        for line in log_lines:
            line = line.strip()

            # 提取阶段标记
            for phase_key, stage_name in self.PHASE_MAP.items():
                if phase_key in line and "完成" in line:
                    current_phase = stage_name
                    if stage_name not in stages:
                        stages[stage_name] = StageExperience(
                            stage_name=stage_name, success=True
                        )
                    break

            # 提取引擎信息
            if "AE Bridge" in line and "连通" in line:
                engines.add("ae")
            if "DaVinci Resolve" in line and ("已就绪" in line or "已安装" in line):
                engines.add("davinci")
            if "FFmpeg" in line or "MoviePy" in line:
                engines.add("ffmpeg")

            # 提取耗时
            if "耗时" in line:
                m = re.search(r"耗时(\d+)s", line)
                if m and current_phase:
                    stages[current_phase].duration_sec = float(m.group(1))

            # 提取错误
            if "[WARN]" in line or "[ERROR]" in line:
                error_msg = line.split("]")[-1].strip() if "]" in line else line
                errors.append(error_msg)

            # 提取内存
            if "可用=" in line:
                m = re.search(r"可用=([\d.]+)GB", line)
                if m:
                    record.memory_available_gb = max(
                        record.memory_available_gb, float(m.group(1))
                    )

            # 提取输出文件数
            if "输出文件" in line:
                m = re.search(r"(\d+) 个", line)
                if m:
                    record.overall_quality = min(100.0, float(m.group(1)) * 7)

        # 检查是否有失败
        for line in log_lines:
            if "未就绪" in line or "不可用" in line or "模拟" in line:
                # DaVinci API不可用是一个重要的经验
                if "DaVinci" in line:
                    if "execute" not in stages:
                        stages["execute"] = StageExperience(
                            stage_name="execute",
                            success=False,
                            error_type="davinci_api_unavailable",
                            error_msg="fusionscript initialization failed",
                            engine_used="davinci",
                        )
                    errors.append("DaVinci API unavailable, fell back to simulation")

        # 标记引擎可用性
        record.engines_available = list(engines)

        # 生成阶段经验
        for stage_name, stage_exp in stages.items():
            stage_exp.engine_used = stage_exp.engine_used or self._infer_engine(stage_name, engines)
            record.stages.append(stage_exp)

        # 确保至少有基础阶段
        for sn in ["perceive", "analyze", "plan", "execute", "render", "verify"]:
            if sn not in stages:
                record.stages.append(StageExperience(
                    stage_name=sn, success=True,
                    engine_used=self._infer_engine(sn, engines),
                ))

        # 记录错误模式
        for err in errors:
            record.error_patterns.append({
                "source": "production_report",
                "error_msg": err[:200],
                "context": report.get("timestamp", ""),
            })

        record.overall_success = len(errors) == 0
        return record

    def _infer_engine(self, stage: str, engines: set) -> str:
        if stage in ("execute", "plan"):
            return "ae" if "ae" in engines else "ffmpeg"
        if stage == "render":
            if "davinci" in engines:
                return "davinci"
            return "ae" if "ae" in engines else "ffmpeg"
        return "ffmpeg"

    def _make_id(self, path: str) -> str:
        return "prod_" + hashlib.md5(path.encode()).hexdigest()[:12]


class TestLogParser:
    """解析 test_output_v17_full/ 下的全链路测试日志"""

    def parse_report_json(self, path: str) -> ExperienceRecord | None:
        """解析 v17_full_pipeline_report.json"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                report = json.load(f)
        except Exception:
            return None

        record = ExperienceRecord(
            record_id="test_" + hashlib.md5(path.encode()).hexdigest()[:12],
            source_file=path,
            source_type="test_log",
            raw_summary=f"Test: {report.get('summary', {}).get('pass_rate', 'N/A')}",
        )

        ts_str = report.get("timestamp", "")
        if ts_str:
            try:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                record.timestamp = dt.timestamp()
            except ValueError:
                pass

        # 解析各阶段
        phases = report.get("phases", {})
        phase_to_stage = {
            "AE_Bridge": "execute",
            "Subtitle_Text": "plan",
            "DaVinci": "render",
            "OpenSource": "verify",
            "Unified": "perceive",
        }

        engines = set()
        for phase_name, phase_data in phases.items():
            stage_name = phase_to_stage.get(phase_name, "verify")
            passed = phase_data.get("passed", 0)
            failed = phase_data.get("failed", 0)
            total = phase_data.get("total", 0)
            errors = phase_data.get("errors", [])

            success_rate = passed / total if total > 0 else 0
            record.stages.append(StageExperience(
                stage_name=stage_name,
                success=failed == 0,
                quality_score=success_rate * 100,
                error_msg="; ".join(errors) if errors else "",
                error_type="test_failure" if errors else "",
            ))

            # 推断引擎
            if "AE" in phase_name:
                engines.add("ae")
            if "DaVinci" in phase_name:
                engines.add("davinci")
            if "OpenSource" in phase_name:
                engines.add("ffmpeg")

        record.engines_available = list(engines)
        record.overall_success = report.get("summary", {}).get("failed", 1) == 0

        # 错误日志
        for err in report.get("error_log", []):
            record.error_patterns.append({
                "source": "test_log",
                "error_msg": err[:200],
                "context": "test_checklist",
            })

        return record

    def parse_pipeline_log(self, path: str) -> ExperienceRecord | None:
        """解析 pipeline_log.txt"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return None

        record = ExperienceRecord(
            record_id="tlog_" + hashlib.md5(path.encode()).hexdigest()[:12],
            source_file=path,
            source_type="test_log",
        )

        # 提取通过率
        m = re.search(r"通过率:\s*([\d.]+)%", content)
        if m:
            record.overall_quality = float(m.group(1))
            record.overall_success = record.overall_quality >= 90

        # 提取PASS/FAIL
        passes = len(re.findall(r"\[PASS\]", content))
        fails = len(re.findall(r"\[FAIL\]", content))
        fail_lines = re.findall(r"\[FAIL\]\s*(.+)", content)

        for fl in fail_lines:
            record.error_patterns.append({
                "source": "pipeline_log",
                "error_msg": fl.strip()[:200],
            })

        # 推断各阶段
        stage_keywords = {
            "perceive": ["Whisper", "SRT", "字幕"],
            "execute": ["AE", "Bridge", "JSX"],
            "render": ["DaVinci", "调色", "LUT"],
            "verify": ["FFmpeg", "MoviePy", "GIF", "场景"],
        }
        for stage, keywords in stage_keywords.items():
            found = any(kw in content for kw in keywords)
            if found:
                record.stages.append(StageExperience(
                    stage_name=stage, success=True
                ))

        record.raw_summary = f"Pipeline log: {passes} pass, {fails} fail"
        return record


class SystemLogParser:
    """解析 logs/ 目录下的系统运行日志"""

    # 日志文件名模式 → 关联的管线阶段
    LOG_PATTERNS = {
        "api-server": "perceive",
        "auth": "perceive",
        "database": "analyze",
        "metrics": "verify",
        "media-system": "execute",
        "workflow-batch": "plan",
        "scheduler": "plan",
        "plugin-system": "execute",
        "resource-manager": "render",
        "task-persistence": "render",
    }

    def parse_log_file(self, path: str) -> ExperienceRecord | None:
        """解析单个日志文件"""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return None

        if not lines:
            return None

        filename = os.path.basename(path)
        # 提取日期
        date_match = re.search(r"(\d{8})", filename)
        ts = 0.0
        if date_match:
            try:
                dt = datetime.strptime(date_match.group(1), "%Y%m%d")
                ts = dt.timestamp()
            except ValueError:
                ts = time.time()

        # 确定关联阶段
        stage = "verify"
        for pattern, stage_name in self.LOG_PATTERNS.items():
            if pattern in filename:
                stage = stage_name
                break

        # 统计错误
        error_count = 0
        warn_count = 0
        error_msgs = []
        for line in lines:
            if "ERROR" in line or "CRITICAL" in line:
                error_count += 1
                if len(error_msgs) < 3:
                    error_msgs.append(line.strip()[:200])
            elif "WARN" in line:
                warn_count += 1

        record = ExperienceRecord(
            record_id="syslog_" + hashlib.md5(path.encode()).hexdigest()[:12],
            timestamp=ts,
            source_file=path,
            source_type="system_log",
            overall_success=error_count == 0,
            stages=[StageExperience(
                stage_name=stage,
                success=error_count == 0,
                error_type="system_error" if error_count > 0 else "",
                error_msg="; ".join(error_msgs),
            )],
            error_patterns=[
                {"source": "system_log", "error_msg": msg, "file": filename}
                for msg in error_msgs
            ],
            raw_summary=f"{filename}: {error_count} errors, {warn_count} warnings, {len(lines)} lines",
        )
        return record


class StructuredDataParser:
    """解析 data/ 目录下已有的结构化数据"""

    def __init__(self, data_dir: str = "data"):
        self._data_dir = Path(data_dir)

    def parse_error_patterns(self) -> list[dict[str, str]]:
        """解析 data/error_patterns/error_patterns.json"""
        path = self._data_dir / "error_patterns" / "error_patterns.json"
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                patterns = json.load(f)
            return [
                {
                    "error_type": p.get("error_type", ""),
                    "error_msg": p.get("error_msg", ""),
                    "fix_applied": p.get("fix_applied", ""),
                    "context": p.get("context_stage", ""),
                    "occurrences": str(p.get("occurrence_count", 1)),
                    "source": "error_patterns_db",
                }
                for p in patterns
            ]
        except Exception:
            return []

    def parse_fallback_history(self) -> dict[str, Any]:
        """解析 data/fallback_history.json"""
        path = self._data_dir / "fallback_history.json"
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def parse_pipeline_runs(self) -> list[ExperienceRecord]:
        """解析 data/pipeline_runs/ 下的历史管线运行记录

        每个 run_xxx 目录包含: pipeline_result.json + perceive/analyze/plan/execute/render/verify/learn.json
        """
        runs_dir = self._data_dir / "pipeline_runs"
        if not runs_dir.exists():
            return []

        records = []
        for run_dir in sorted(runs_dir.iterdir()):
            if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                continue
            try:
                record = self._parse_single_pipeline_run(run_dir)
                if record:
                    records.append(record)
            except Exception as e:
                logger.debug(f"[StructParser] Skip pipeline run {run_dir.name}: {e}")
        return records

    def _parse_single_pipeline_run(self, run_dir: Path) -> ExperienceRecord | None:
        """解析单个管线运行目录"""
        result_path = run_dir / "pipeline_result.json"
        if not result_path.exists():
            return None

        with open(result_path, "r", encoding="utf-8") as f:
            result = json.load(f)

        run_id = result.get("run_id", run_dir.name)
        overall_success = result.get("status") == "success"
        quality_score = result.get("quality_score", 0)
        total_duration = result.get("total_duration_sec", 0)
        mode = result.get("mode", "unknown")

        stages_data = result.get("stages", {})
        stage_experiences: list[StageExperience] = []

        for stage_name, stage_info in stages_data.items():
            if stage_name.startswith("_"):
                continue
            stage_status = stage_info.get("status", "unknown")
            stage_duration = stage_info.get("duration", 0)
            stage_error = stage_info.get("error", "")
            success = stage_status in ("done", "skipped", "success")

            params: dict[str, Any] = {}
            engine_used = None
            stage_quality = None

            stage_file = run_dir / f"{stage_name}.json"
            if stage_file.exists():
                try:
                    with open(stage_file, "r", encoding="utf-8") as sf:
                        stage_detail = json.load(sf)
                    data = stage_detail.get("data", {})

                    if stage_name == "execute":
                        engine_used = data.get("execution_mode", data.get("engine", ""))
                        params["layers_created"] = data.get("layers_created", 0)
                        params["effects_applied"] = data.get("effects_applied", 0)
                        params["composition"] = data.get("composition", "")
                    elif stage_name == "verify":
                        stage_quality = data.get("score", stage_quality)
                        checks = data.get("checks", {})
                        for check_name, check_data in checks.items():
                            if isinstance(check_data, dict):
                                params[f"verify_{check_name}_score"] = check_data.get("score", 0)
                                params[f"verify_{check_name}_status"] = check_data.get("status", "")
                    elif stage_name == "perceive":
                        materials = data.get("materials", [])
                        params["material_count"] = len(materials)
                        if materials:
                            params["first_material_duration"] = materials[0].get("duration_sec", 0)
                    elif stage_name == "render":
                        params["output_path"] = data.get("output_path", "")
                        engine_used = data.get("render_engine", data.get("engine", ""))
                    elif stage_name == "plan":
                        params["strategy"] = data.get("strategy", "")
                        params["effects_planned"] = len(data.get("effects", []))
                    elif stage_name == "analyze":
                        params["scenes_detected"] = len(data.get("scenes", []))
                        params["mood"] = data.get("mood", "")
                except Exception:
                    pass

            if stage_quality is None and stage_name == "verify":
                stage_quality = quality_score

            stage_exp = StageExperience(
                stage_name=stage_name,
                duration_sec=stage_duration,
                success=success,
                quality_score=stage_quality if stage_quality is not None else (quality_score if stage_name == "verify" else None),
                error_type="" if success else "stage_failure",
                error_msg=stage_error if not success else "",
                engine_used=engine_used,
                params=params if params else None,
            )
            stage_experiences.append(stage_exp)

        error_patterns: list[dict[str, str]] = []
        if not overall_success:
            for stage_exp in stage_experiences:
                if not stage_exp.success and stage_exp.error_msg:
                    error_patterns.append({
                        "error_type": stage_exp.error_type or "stage_failure",
                        "error_msg": stage_exp.error_msg,
                        "context_stage": stage_exp.stage_name,
                        "source": f"pipeline_run:{run_id}",
                    })

        record = ExperienceRecord(
            record_id=f"pipeline_run_{run_id}",
            source_file=f"data/pipeline_runs/{run_dir.name}/pipeline_result.json",
            source_type="pipeline_run",
            overall_success=overall_success,
            stages=stage_experiences,
            quality_score=quality_score,
            total_duration_sec=total_duration,
            error_patterns=error_patterns,
            raw_summary=f"Pipeline run {run_id} ({mode}): {result.get('status')}, "
                        f"quality={quality_score}, duration={total_duration:.1f}s",
        )
        return record

    def build_records_from_structured(self) -> list[ExperienceRecord]:
        """从结构化数据构建经验记录"""
        records = []

        # 管线运行历史 → 经验记录 (最高优先级，数据最完整)
        pipeline_records = self.parse_pipeline_runs()
        records.extend(pipeline_records)

        # 错误模式 → 经验记录
        error_patterns = self.parse_error_patterns()
        if error_patterns:
            record = ExperienceRecord(
                record_id="struct_errors",
                source_file="data/error_patterns/error_patterns.json",
                source_type="structured_data",
                error_patterns=error_patterns,
                overall_success=False,
                stages=[StageExperience(
                    stage_name=ep.get("context", "execute"),
                    success=False,
                    error_type=ep.get("error_type", ""),
                    error_msg=ep.get("error_msg", ""),
                ) for ep in error_patterns],
                raw_summary=f"Error patterns DB: {len(error_patterns)} patterns",
            )
            records.append(record)

        # 降级历史 → 经验记录
        fallback = self.parse_fallback_history()
        skipped_test_artifacts = 0
        for action, stats in fallback.items():
            success_count = stats.get("success", 0)
            total_count = stats.get("total", 0)
            if total_count > 0:
                last_error = stats.get("last_error", "")
                success_rate = success_count / total_count
                # 识别疑似测试污染的 fallback 记录（避免注入到因果/贝叶斯学习信号）
                # 典型场景：tests/test_config_workflow_regression_gaps.py 中 task_id="double_failure"
                # 的 fallback_func 抛 ZeroDivisionError("fallback also fails")，每次运行都向
                # 生产 fallback_history.json 累计失败计数。这种记录不应进入下游学习模块。
                is_test_artifact = (
                    success_count == 0
                    and total_count >= 5
                    and (
                        "fallback also fails" in last_error
                        or "double_failure" in action
                        or "[ZeroDivisionError]" in last_error
                    )
                )
                if is_test_artifact:
                    skipped_test_artifacts += 1
                    logger.info(
                        f"[StructParser] 跳过疑似测试污染的 fallback 记录: "
                        f"{action} ({success_count}/{total_count}, last_error={last_error[:80]!r})"
                    )
                    continue
                record = ExperienceRecord(
                    record_id=f"struct_fallback_{action}",
                    source_file="data/fallback_history.json",
                    source_type="structured_data",
                    overall_success=success_count > 0,
                    stages=[StageExperience(
                        stage_name="render" if "render" in action else "verify",
                        success=success_count == total_count,
                        error_msg=last_error,
                        params={
                            "action": action,
                            "success_rate": success_rate,
                            "total": total_count,
                        },
                    )],
                    raw_summary=f"Fallback {action}: {success_count}/{total_count}",
                )
                records.append(record)
        if skipped_test_artifacts > 0:
            logger.info(
                f"[StructParser] 共跳过 {skipped_test_artifacts} 条疑似测试污染的 fallback 记录"
            )

        return records


class FlagshipManifestParser:
    """解析 output/flagship_*/ 目录下的旗舰管线执行产物

    旗舰管线 manifest.json 格式:
    {
        "run_id": "flagship_1785514594",
        "stages": {
            "S0": {"elapsed": 1.68, "passed": true, ...},
            "S1": {"elapsed": 5.95, "videos": [...], ...},
            ...
        },
        "total_elapsed_s": 77.08,
        "status": "completed"
    }

    阶段映射 (S0-S7 → 数字孪生 7 阶段):
        S0 (健康检查)  → perceive
        S1 (素材规范化) → perceive
        S2 (节拍分析)  → analyze
        S3 (AE 合成)   → execute
        S4 (PR 粗剪)   → plan
        S5 (DaVinci调色) → render
        S6 (AME 导出)  → render
        S7 (质量门)    → verify
    """

    # S0-S7 → 数字孪生阶段映射
    STAGE_MAP = {
        "S0": "perceive",
        "S1": "perceive",
        "S2": "analyze",
        "S3": "execute",
        "S4": "plan",
        "S5": "render",
        "S6": "render",
        "S7": "verify",
    }

    # S0-S7 → 引擎标识
    ENGINE_MAP = {
        "S0": "system",
        "S1": "ffmpeg",
        "S2": "librosa",
        "S3": "ae",
        "S4": "premiere",
        "S5": "davinci",
        "S6": "ame",
        "S7": "opencv",
    }

    def parse_run_dir(self, run_dir: Path) -> ExperienceRecord | None:
        """解析单个旗舰管线运行目录"""
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            logger.debug(f"[FlagshipParser] Failed to read {manifest_path}: {e}")
            return None

        run_id = manifest.get("run_id", run_dir.name)
        status = manifest.get("status", "unknown")
        total_elapsed = manifest.get("total_elapsed_s", 0.0)
        stages_data = manifest.get("stages", {})
        critic_reports = manifest.get("critic_reports", [])

        # 判断成功: status == "completed" 或 S7.passed == True
        overall_success = status == "completed"
        if not overall_success and "S7" in stages_data:
            overall_success = stages_data["S7"].get("passed", False)

        # 中途自评裁决索引：每阶段最后一次裁决（TEMPO 思想：边界评价即学习信号）
        last_verdict: dict[str, dict[str, Any]] = {}
        for rep in critic_reports:
            st = rep.get("stage", "")
            if st:
                last_verdict[st] = rep

        # 构建阶段经验
        stage_experiences: list[StageExperience] = []
        engines_used: set[str] = set()
        error_patterns: list[dict[str, str]] = []

        for s_key, s_data in stages_data.items():
            if not s_key.startswith("S"):
                continue
            # 重试记录（S3_retry 等）不单独建阶段经验，仅用于耗时统计
            if s_key.endswith("_retry"):
                base = s_key.replace("_retry", "")
                if base in stages_data:
                    stages_data[base]["elapsed"] = round(
                        stages_data[base].get("elapsed", 0.0) + s_data.get("elapsed", 0.0), 2)
                continue

            twin_stage = self.STAGE_MAP.get(s_key, "verify")
            engine = self.ENGINE_MAP.get(s_key, "ffmpeg")
            elapsed = s_data.get("elapsed", 0.0)

            # 判断阶段成功
            stage_success = True
            if "passed" in s_data:
                stage_success = s_data["passed"]
            elif s_data.get("error"):
                stage_success = False
            # critic 边界裁决修正：被 abort/retry 拦截的阶段产物实际不健康
            v = last_verdict.get(s_key)
            if v and v.get("decision") in ("abort", "retry"):
                stage_success = False

            # 质量分: 从 QG 报告提取
            quality = 0.0
            if s_key == "S7":
                qg_report_path = run_dir / "S7_qg" / "quality_gate_report.json"
                if qg_report_path.exists():
                    try:
                        with open(qg_report_path, "r", encoding="utf-8") as qf:
                            qg = json.load(qf)
                        checks = qg.get("checks", [])
                        passed_count = sum(1 for c in checks if c.get("passed"))
                        quality = (passed_count / max(len(checks), 1)) * 100
                    except Exception:
                        pass

            stage_exp = StageExperience(
                stage_name=twin_stage,
                success=stage_success,
                duration_sec=elapsed,
                engine_used=engine,
                quality_score=quality,
                error_type="" if stage_success else f"{s_key}_failure",
                error_msg=s_data.get("error", "") if not stage_success else "",
                params={
                    "flagship_stage": s_key,
                    "file_size_mb": s_data.get("file_size_mb", 0),
                    "nodes": s_data.get("nodes", 0),
                },
            )
            stage_experiences.append(stage_exp)
            engines_used.add(engine)

            # 收集失败模式
            if not stage_success:
                error_patterns.append({
                    "source": f"flagship:{run_id}",
                    "error_msg": s_data.get("error", f"{s_key} failed"),
                    "context_stage": twin_stage,
                    "error_type": f"{s_key}_failure",
                })

        # 中途裁决转为独立阶段经验（P0-2：失败 run 的中途观测也回流，
        # 数字孪生从"每 run 一个终点观测"升级为"每 run 多个中途观测"）
        for rep in critic_reports:
            st = rep.get("stage", "")
            if st not in self.STAGE_MAP:
                continue
            decision = rep.get("decision", "continue")
            atomic = rep.get("atomic_checks", {})
            n_pass = sum(1 for ok in atomic.values() if ok)
            stage_experiences.append(StageExperience(
                stage_name=self.STAGE_MAP[st],
                success=(decision == "continue"),
                duration_sec=round(rep.get("elapsed_ms", 0.0) / 1000.0, 3),
                engine_used="critic",
                quality_score=round(float(rep.get("value_estimate", 0.0)) * 100, 1),
                error_type="" if decision == "continue" else f"critic_{decision}",
                error_msg="" if decision == "continue" else (
                    f"critic {decision}: "
                    + ",".join(k for k, ok in atomic.items() if not ok)
                ),
                params={
                    "flagship_stage": st,
                    "critic_value_estimate": rep.get("value_estimate", 0.0),
                    "critic_decision": decision,
                    "atomic_passed": f"{n_pass}/{len(atomic)}",
                },
            ))
            engines_used.add("critic")
            if decision == "abort":
                error_patterns.append({
                    "source": f"flagship_critic:{run_id}",
                    "error_msg": f"critic abort at {st}: "
                                 + ",".join(k for k, ok in atomic.items() if not ok),
                    "context_stage": self.STAGE_MAP[st],
                    "error_type": "critic_abort",
                })

        # 从 quality_gate_report 提取额外错误模式
        qg_report_path = run_dir / "S7_qg" / "quality_gate_report.json"
        if qg_report_path.exists():
            try:
                with open(qg_report_path, "r", encoding="utf-8") as qf:
                    qg = json.load(qf)
                for check in qg.get("checks", []):
                    if not check.get("passed", True):
                        error_patterns.append({
                            "source": f"flagship_qg:{run_id}",
                            "error_msg": f"QG {check.get('id','?')} failed: {check.get('name','')}",
                            "context_stage": "verify",
                            "error_type": "quality_gate_failure",
                        })
            except Exception:
                pass

        record = ExperienceRecord(
            record_id=f"flagship_{run_id}",
            timestamp=manifest.get("created_at", time.time()),
            source_file=str(manifest_path),
            source_type="flagship_manifest",
            stages=stage_experiences,
            overall_success=overall_success,
            total_duration=total_elapsed,
            overall_quality=next(
                (s.quality_score for s in stage_experiences if s.quality_score > 0), 0.0
            ),
            engines_available=list(engines_used),
            error_patterns=error_patterns,
            raw_summary=(
                f"Flagship pipeline {run_id}: status={status}, "
                f"elapsed={total_elapsed:.1f}s, "
                f"stages={len(stage_experiences)}, "
                f"engines={list(engines_used)}"
            ),
        )
        return record

    def parse_all_runs(self, output_dir: Path) -> list[ExperienceRecord]:
        """扫描 output/ 下所有 flagship_* 目录"""
        records = []
        if not output_dir.exists():
            return records
        for run_dir in sorted(output_dir.glob("flagship_*")):
            if not run_dir.is_dir():
                continue
            record = self.parse_run_dir(run_dir)
            if record:
                records.append(record)
        return records


class DailyNoteParser:
    """解析 00-每日记录/ 下的 Markdown 开发日记"""

    # 经验关键词模式
    EXPERIENCE_PATTERNS = [
        (r"(?:bug|问题|错误|失败|崩溃|crash).*?(?:修复|解决|fix)", "bug_fix"),
        (r"(?:成功|完成|通过|打通|验证)", "success"),
        (r"(?:注意|陷阱|坑|trap|pitfall|务必|必须)", "pitfall"),
        (r"(?:优化|提升|加速|改进)", "optimization"),
        (r"(?:降级|fallback|备选|容错)", "fallback"),
    ]

    def parse_daily_note(self, path: str) -> ExperienceRecord | None:
        """解析单个开发日记"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return None

        if not content.strip():
            return None

        filename = os.path.basename(path)
        # 提取日期
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        ts = 0.0
        if date_match:
            try:
                dt = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                ts = dt.timestamp()
            except ValueError:
                pass

        # 提取经验条目
        experiences = []
        for pattern, exp_type in self.EXPERIENCE_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches[:3]:  # 每类最多3条
                experiences.append({
                    "type": exp_type,
                    "text": str(match)[:200],
                    "source_file": filename,
                })

        # 推断涉及的引擎和阶段
        engines = []
        if "AE" in content or "After Effects" in content:
            engines.append("ae")
        if "DaVinci" in content or "Resolve" in content or "达芬奇" in content:
            engines.append("davinci")
        if "FFmpeg" in content:
            engines.append("ffmpeg")
        if "Bridge" in content:
            engines.append("ae_bridge")

        record = ExperienceRecord(
            record_id="daily_" + hashlib.md5(path.encode()).hexdigest()[:12],
            timestamp=ts,
            source_file=path,
            source_type="daily_note",
            engines_available=engines,
            overall_success=True,
            raw_summary=f"Daily note: {filename}, {len(experiences)} experiences, engines: {engines}",
        )

        # 将经验转化为阶段经验
        type_to_stage = {
            "bug_fix": "execute",
            "success": "verify",
            "pitfall": "execute",
            "optimization": "render",
            "fallback": "render",
        }
        for exp in experiences:
            stage = type_to_stage.get(exp["type"], "verify")
            record.stages.append(StageExperience(
                stage_name=stage,
                success=exp["type"] != "bug_fix",
                error_type=exp["type"] if exp["type"] == "bug_fix" else "",
                error_msg=exp["text"],
                params={"experience_type": exp["type"]},
            ))
            if exp["type"] in ("bug_fix", "pitfall"):
                record.error_patterns.append({
                    "source": "daily_note",
                    "error_msg": exp["text"],
                    "context": exp["type"],
                })

        return record


# ============================================================================
#  经验注入器 — 将提取的经验喂入各模块
# ============================================================================

class ExperienceInjector:
    """将经验记录注入到各高阶模块"""

    def __init__(self, data_dir: str = "data"):
        self._data_dir = Path(data_dir)

    def _state_dir(self, name: str) -> str:
        """构造 learning 状态子目录的绝对路径。

        统一基于 self._data_dir(经验库根目录) 派生，避免 "data/xxx" 相对路径
        依赖 CWD 导致的多入口路径来源不一致。
        """
        return str(self._data_dir / name)

    def inject_all(
        self, records: list[ExperienceRecord]
    ) -> dict[str, dict[str, Any]]:
        """向所有模块注入经验，返回各模块的注入结果"""
        results = {}

        results["causal_engine"] = self._inject_causal(records)
        results["bayesian_optimizer"] = self._inject_bayesian(records)
        results["digital_twin"] = self._inject_twin(records)
        results["strategy_engine"] = self._inject_strategy(records)
        results["self_evolution"] = self._inject_evolution(records)

        # 持久化各模块状态
        self._persist_module_states()

        # 持久化经验记录
        self._persist_records(records)

        return results

    def _persist_module_states(self) -> None:
        """调用各模块的 _save_state 确保持久化"""
        try:
            from core.causal_engine import get_causal_engine
            get_causal_engine(data_dir=self._state_dir("causal_engine"))._save_state()
        except Exception as e:
            logger.debug(f"save causal_engine: {e}")
        try:
            from core.bayesian_optimizer import get_optimizer
            get_optimizer(data_dir=self._state_dir("bayesian_optimizer"))._save_state()
        except Exception as e:
            logger.debug(f"save bayesian_optimizer: {e}")
        try:
            from core.pipeline_digital_twin import get_digital_twin
            get_digital_twin(data_dir=self._state_dir("digital_twin"))._save_state()
        except Exception as e:
            logger.debug(f"save digital_twin: {e}")
        try:
            from core.meta_strategy_engine import get_strategy_engine
            get_strategy_engine(data_dir=self._state_dir("meta_strategy"))._save_state()
        except Exception as e:
            logger.debug(f"save meta_strategy: {e}")

    # ----------------------------------------------------------------
    #  因果引擎注入
    # ----------------------------------------------------------------

    def _inject_causal(self, records: list[ExperienceRecord]) -> dict[str, Any]:
        """注入到因果推断引擎"""
        try:
            from core.causal_engine import ExecutionRecord as CausalExecutionRecord
            from core.causal_engine import get_causal_engine
            engine = get_causal_engine(data_dir=self._state_dir("causal_engine"))

            before_stats = engine.get_statistics()
            count = 0

            for record in records:
                if not record.stages:
                    continue

                causal_record = CausalExecutionRecord(
                    run_id=record.record_id,
                    timestamp=record.timestamp,
                    stages={
                        s.stage_name: {
                            "success": s.success,
                            "duration": s.duration_sec,
                            "error": s.error_msg,
                            "engine": s.engine_used,
                        }
                        for s in record.stages
                    },
                    engine_states={
                        eng: {"memory_gb": record.memory_available_gb}
                        for eng in record.engines_available
                    },
                    output_quality=record.overall_quality,
                    success=record.overall_success,
                )
                engine.record_execution(causal_record)
                count += 1

            after_stats = engine.get_statistics()
            return {
                "injected_records": count,
                "execution_log_before": before_stats.get("execution_log_size", 0),
                "execution_log_after": after_stats.get("execution_log_size", 0),
                "edge_count": after_stats.get("edge_count", 0),
            }
        except Exception as e:
            logger.warning(f"[Harvester] Causal injection failed: {e}")
            return {"error": str(e)}

    # ----------------------------------------------------------------
    #  贝叶斯优化器注入
    # ----------------------------------------------------------------

    def _inject_bayesian(self, records: list[ExperienceRecord]) -> dict[str, Any]:
        """注入到贝叶斯参数优化器"""
        try:
            from core.bayesian_optimizer import get_optimizer
            optimizer = get_optimizer(data_dir=self._state_dir("bayesian_optimizer"))

            count = 0
            effects_observed = set()

            # 从历史经验中构建参数-效果观测对
            for record in records:
                for stage in record.stages:
                    if not stage.params:
                        continue

                    # 映射阶段到效果名
                    effect_map = {
                        "execute": "Glow",
                        "render": "CC_StarGlow",
                        "plan": "TurbulentDisplace",
                    }
                    effect_name = effect_map.get(stage.stage_name)
                    if not effect_name:
                        continue

                    # 提取数值参数
                    numeric_params = {
                        k: float(v) for k, v in stage.params.items()
                        if isinstance(v, (int, float))
                    }
                    if not numeric_params:
                        # 用默认参数生成观测
                        numeric_params = {"intensity": 50.0, "radius": 10.0}

                    quality = stage.quality_score if stage.quality_score > 0 else (
                        70.0 if stage.success else 30.0
                    )

                    optimizer.observe(
                        effect_name=effect_name,
                        params=numeric_params,
                        quality=quality,
                        render_time=stage.duration_sec if stage.duration_sec > 0 else 30.0,
                        file_size=100.0,
                        success=stage.success,
                    )
                    effects_observed.add(effect_name)
                    count += 1

            # 如果没有参数化的阶段，用错误模式生成合成观测
            if count == 0:
                count = self._inject_synthetic_observations(optimizer, records)
                effects_observed.update(["Glow", "ColorBalance", "FastBlur"])

            return {
                "injected_observations": count,
                "effects_observed": list(effects_observed),
                "total_observations": sum(
                    len(obs) for obs in optimizer._observations.values()
                ),
            }
        except Exception as e:
            logger.warning(f"[Harvester] Bayesian injection failed: {e}")
            return {"error": str(e)}

    def _inject_synthetic_observations(
        self, optimizer, records: list[ExperienceRecord]
    ) -> int:
        """从错误模式和成功/失败记录中生成合成观测"""
        count = 0
        rng = np.random.RandomState(42)

        # 基于成功/失败比例生成观测
        n_success = sum(1 for r in records if r.overall_success)
        n_fail = sum(1 for r in records if not r.overall_success)
        n_total = max(n_success + n_fail, 1)

        for effect_name in ["Glow", "ColorBalance", "FastBlur", "CC_StarGlow"]:
            # 成功观测
            for _ in range(max(n_success, 3)):
                params = {
                    "intensity": rng.uniform(20, 80),
                    "radius": rng.uniform(5, 20),
                }
                optimizer.observe(
                    effect_name=effect_name,
                    params=params,
                    quality=rng.uniform(60, 95),
                    render_time=rng.uniform(10, 60),
                    file_size=rng.uniform(50, 200),
                    success=True,
                )
                count += 1

            # 失败观测
            for _ in range(max(n_fail, 1)):
                params = {
                    "intensity": rng.uniform(80, 100),
                    "radius": rng.uniform(20, 50),
                }
                optimizer.observe(
                    effect_name=effect_name,
                    params=params,
                    quality=rng.uniform(10, 40),
                    render_time=rng.uniform(60, 180),
                    file_size=rng.uniform(200, 500),
                    success=False,
                )
                count += 1

        return count

    # ----------------------------------------------------------------
    #  数字孪生注入
    # ----------------------------------------------------------------

    def _inject_twin(self, records: list[ExperienceRecord]) -> dict[str, Any]:
        """注入到管线数字孪生"""
        try:
            from core.pipeline_digital_twin import ExecutionObservation, get_digital_twin
            twin = get_digital_twin(data_dir=self._state_dir("digital_twin"))

            before_stats = twin.get_statistics()
            count = 0

            # 直接更新 StagePredictor 的观测数据
            predictor = twin._shared_predictor

            for record in records:
                for stage in record.stages:
                    obs = ExecutionObservation(
                        stage_name=stage.stage_name,
                        actual_duration=stage.duration_sec if stage.duration_sec > 0 else self._estimate_duration(stage.stage_name),
                        actual_success=stage.success,
                        actual_quality=stage.quality_score if stage.quality_score > 0 else 70.0,
                        actual_memory_mb=record.memory_available_gb * 1024 if record.memory_available_gb > 0 else 4000.0,
                    )
                    predictor._observations.setdefault(stage.stage_name, []).append(obs)
                    count += 1

            # 用实际数据更新贝叶斯参数
            for stage_name in predictor.STAGES:
                obs_list = predictor._observations.get(stage_name, [])
                if not obs_list:
                    continue

                durations = [o.actual_duration for o in obs_list if o.actual_duration > 0]
                if durations:
                    mean_dur = np.mean(durations)
                    var_dur = np.var(durations) if len(durations) > 1 else (mean_dur * 0.3) ** 2
                    predictor._duration_params[stage_name] = (float(mean_dur), float(max(var_dur, 1.0)))

                n_success = sum(1 for o in obs_list if o.actual_success)
                n_total = len(obs_list)
                if n_total > 0:
                    sr = n_success / n_total
                    predictor._success_params[stage_name] = (sr * 20, (1 - sr) * 20)

            after_stats = twin.get_statistics()
            return {
                "injected_observations": count,
                "stages_calibrated": len([
                    s for s in predictor.STAGES
                    if predictor._observations.get(s)
                ]),
                "duration_params_updated": len([
                    s for s in predictor.STAGES
                    if predictor._observations.get(s) and
                    any(o.actual_duration > 0 for o in predictor._observations[s])
                ]),
            }
        except Exception as e:
            logger.warning(f"[Harvester] Twin injection failed: {e}")
            return {"error": str(e)}

    def _estimate_duration(self, stage_name: str) -> float:
        """默认耗时估计"""
        defaults = {
            "perceive": 15.0, "analyze": 20.0, "plan": 10.0,
            "execute": 60.0, "render": 120.0, "verify": 30.0, "learn": 5.0,
        }
        return defaults.get(stage_name, 30.0)

    # ----------------------------------------------------------------
    #  策略引擎注入
    # ----------------------------------------------------------------

    def _inject_strategy(self, records: list[ExperienceRecord]) -> dict[str, Any]:
        """注入到元学习策略引擎"""
        try:
            from core.meta_strategy_engine import get_strategy_engine
            engine = get_strategy_engine(data_dir=self._state_dir("meta_strategy"))

            before_stats = engine.get_statistics()
            count = 0

            # 根据执行记录更新 Thompson Sampling 参数
            for record in records:
                # 推断使用的策略
                strategy_id = self._infer_strategy(record)

                engine.record_usage(
                    strategy_id=strategy_id,
                    success=record.overall_success,
                    quality=record.overall_quality,
                    duration=record.total_duration,
                )
                count += 1

            after_stats = engine.get_statistics()
            return {
                "injected_records": count,
                "ts_params_before": before_stats.get("ts_params", {}),
                "ts_params_after_sample": {
                    k: list(v) if isinstance(v, tuple) else v
                    for k, v in list(engine._ts_params.items())[:5]
                },
                "execution_history_size": after_stats.get("execution_history_size", 0),
            }
        except Exception as e:
            logger.warning(f"[Harvester] Strategy injection failed: {e}")
            return {"error": str(e)}

    def _infer_strategy(self, record: ExperienceRecord) -> str:
        """从执行记录推断使用的策略（映射到实际策略ID）"""
        engines = set(record.engines_available)
        if "davinci" in engines and "ae" in engines:
            return "default_balanced"
        if "ae" in engines:
            return "default_quality"
        if record.overall_success and record.overall_quality > 80:
            return "default_quality"
        if record.overall_success:
            return "default_balanced"
        return "default_safe"

    # ----------------------------------------------------------------
    #  自进化引擎注入
    # ----------------------------------------------------------------

    def _inject_evolution(self, records: list[ExperienceRecord]) -> dict[str, Any]:
        """注入到自进化引擎并触发经验蒸馏"""
        try:
            from core.self_evolution_engine import (
                ExecutionRecord as EvolutionRecord,
            )
            from core.self_evolution_engine import (
                get_evolution_engine,
            )
            # self_evolution 数据目录收口到 core.paths（运行时产物移出代码仓库）
            try:
                from core.paths import self_evolution_dir as _paths_evo_dir
                _evo_dir = _paths_evo_dir()
            except ImportError:
                _evo_dir = self._state_dir("self_evolution")
            engine = get_evolution_engine(data_dir=_evo_dir)

            count = 0
            reviews = []

            for record in records:
                evo_record = EvolutionRecord(
                    run_id=record.record_id,
                    timestamp=record.timestamp,
                    stages={
                        s.stage_name: {
                            "success": s.success,
                            "duration": s.duration_sec,
                            "error": s.error_msg,
                            "quality": s.quality_score,
                        }
                        for s in record.stages
                    },
                    output_quality=record.overall_quality,
                    success=record.overall_success,
                    total_duration=record.total_duration,
                )

                try:
                    import asyncio
                    review = asyncio.get_event_loop().run_until_complete(
                        engine.post_execution_review(evo_record)
                    )
                    reviews.append({
                        "run_id": record.record_id,
                        "quality": review.quality.overall_score if review else 0,
                    })
                except RuntimeError:
                    # 没有事件循环，直接添加到历史
                    engine._execution_history.append(evo_record)

                count += 1

            # 触发一次经验蒸馏
            distilled = {}
            successful = [r for r in records if r.overall_success]
            failed = [r for r in records if not r.overall_success]

            if successful or failed:
                try:
                    import asyncio

                    from core.self_evolution_engine import ExecutionRecord as EvoRecord
                    distilled_result = asyncio.get_event_loop().run_until_complete(
                        engine.distill_experience(
                            successful_runs=[
                                EvoRecord(
                                    run_id=r.record_id,
                                    timestamp=r.timestamp,
                                    stages={s.stage_name: {"success": s.success, "duration": s.duration_sec} for s in r.stages},
                                    output_quality=r.overall_quality,
                                    success=True,
                                )
                                for r in successful[:10]
                            ],
                            failed_runs=[
                                EvoRecord(
                                    run_id=r.record_id,
                                    timestamp=r.timestamp,
                                    stages={s.stage_name: {"success": s.success, "error": s.error_msg} for s in r.stages},
                                    output_quality=r.overall_quality,
                                    success=False,
                                )
                                for r in failed[:10]
                            ],
                        )
                    )
                    if distilled_result:
                        distilled = {
                            "rules_count": len(distilled_result.rules),
                            "error_patterns_count": len(distilled_result.error_patterns),
                            "parameter_insights_count": len(distilled_result.parameter_insights),
                        }
                except RuntimeError:
                    pass

            engine._save_state()
            return {
                "injected_records": count,
                "reviews_completed": len(reviews),
                "distilled_knowledge": distilled,
                "execution_history_size": len(engine._execution_history),
            }
        except Exception as e:
            logger.warning(f"[Harvester] Evolution injection failed: {e}")
            return {"error": str(e)}

    # ----------------------------------------------------------------
    #  持久化
    # ----------------------------------------------------------------

    def _persist_records(self, records: list[ExperienceRecord]) -> None:
        """持久化经验记录到 data/execution_records/"""
        records_dir = self._data_dir / "execution_records"
        records_dir.mkdir(parents=True, exist_ok=True)

        # 保存汇总索引
        index = []
        for record in records:
            index.append({
                "record_id": record.record_id,
                "timestamp": record.timestamp,
                "source_type": record.source_type,
                "source_file": record.source_file,
                "overall_success": record.overall_success,
                "overall_quality": record.overall_quality,
                "n_stages": len(record.stages),
                "n_errors": len(record.error_patterns),
            })

        index_path = records_dir / "harvest_index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        # 保存每条记录
        for record in records:
            record_path = records_dir / f"{record.record_id}.json"
            with open(record_path, "w", encoding="utf-8") as f:
                json.dump(asdict(record), f, ensure_ascii=False, indent=2)

        logger.info(f"[Harvester] Persisted {len(records)} records to {records_dir}")


# ============================================================================
#  主编排器
# ============================================================================

class ExperienceHarvester:
    """往期执行经验汲取器 — 扫描、解析、提取、注入"""

    def __init__(self, project_root: str = "."):
        self._root = Path(project_root)
        self._records: list[ExperienceRecord] = []

        # 解析器
        self._prod_parser = ProductionReportParser()
        self._test_parser = TestLogParser()
        self._syslog_parser = SystemLogParser()
        self._struct_parser = StructuredDataParser(
            data_dir=str(self._root / "data")
        )
        self._daily_parser = DailyNoteParser()
        self._flagship_parser = FlagshipManifestParser()
        self._injector = ExperienceInjector(
            data_dir=str(self._root / "data")
        )

    def harvest(self) -> HarvestReport:
        """执行完整的经验汲取流程"""
        start_time = time.time()
        report = HarvestReport()

        logger.info("[Harvester] === 开始往期执行经验汲取 ===")

        # 1. 扫描生产报告
        self._scan_production_reports(report)

        # 2. 扫描测试日志
        self._scan_test_logs(report)

        # 3. 扫描系统日志
        self._scan_system_logs(report)

        # 4. 扫描结构化数据
        self._scan_structured_data(report)

        # 5. 扫描开发日记
        self._scan_daily_notes(report)

        # 6. 扫描旗舰管线产物
        self._scan_flagship_outputs(report)

        report.total_records_extracted = len(self._records)
        report.total_error_patterns = sum(
            len(r.error_patterns) for r in self._records
        )
        report.total_stage_experiences = sum(
            len(r.stages) for r in self._records
        )

        logger.info(
            f"[Harvester] 提取完成: {len(self._records)} 条记录, "
            f"{report.total_error_patterns} 个错误模式, "
            f"{report.total_stage_experiences} 个阶段经验"
        )

        # 7. 注入到各模块
        logger.info("[Harvester] === 开始经验注入 ===")
        report.injection_results = self._injector.inject_all(self._records)

        for module, result in report.injection_results.items():
            logger.info(f"[Harvester] {module}: {result}")

        report.duration_sec = time.time() - start_time
        logger.info(
            f"[Harvester] === 经验汲取完成 === "
            f"({report.duration_sec:.1f}s, "
            f"{report.total_records_extracted} records)"
        )

        return report

    def harvest_incremental(self, parse_budget_sec: float = 25.0) -> HarvestReport:
        """增量经验汲取: 只处理上次汲取后新增/修改的文件
        
        通过 data/execution_records/.harvest_state.json 跟踪已处理文件。
        每次只扫描新增或修改时间变化的文件，避免重复注入。

        性能保护（首跑全量扫描加速）:
        - 解析阶段带时间预算 parse_budget_sec，超预算立即截断；
        - 未解析完的文件不写入 state，下次汲取继续处理，
          避免首次全量解析把主管线拖慢（配合调用方线程超时）。
        """
        start_time = time.time()
        report = HarvestReport()

        # 加载上次汲取状态
        state_path = self._root / "data" / "execution_records" / ".harvest_state.json"
        prev_state: dict[str, float] = {}  # file_path -> mtime
        if state_path.exists():
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    prev_state = json.load(f)
            except Exception:
                prev_state = {}

        # 扫描所有数据源，但只处理新增/修改的文件
        new_files: list[str] = []
        current_state: dict[str, float] = {}

        scan_dirs = [
            self._root / "output_production",
            self._root / "output_director",
            self._root / "test_output_v17_full",
            self._root / "test_output_v17",
            self._root / "logs",
            self._root / "00-每日记录",
            self._root / "data" / "pipeline_runs",
            self._root / "output",
        ]
        # 结构化数据文件
        struct_files = [
            self._root / "data" / "error_patterns" / "error_patterns.json",
            self._root / "data" / "fallback_history.json",
        ]

        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for f in scan_dir.rglob("*"):
                if f.is_file() and f.suffix in (".json", ".log", ".txt", ".md"):
                    fpath = str(f)
                    mtime = f.stat().st_mtime
                    current_state[fpath] = mtime
                    if fpath not in prev_state or prev_state[fpath] < mtime:
                        new_files.append(fpath)

        for sf in struct_files:
            if sf.exists():
                fpath = str(sf)
                mtime = sf.stat().st_mtime
                current_state[fpath] = mtime
                if fpath not in prev_state or prev_state[fpath] < mtime:
                    new_files.append(fpath)

        if not new_files:
            report.duration_sec = time.time() - start_time
            return report  # 无新数据，直接返回

        logger.info(f"[Harvester] 增量汲取: {len(new_files)} 个新/修改文件")

        # 只解析新文件，带时间预算截断（首跑全量时防止拖慢主管线）
        budget_deadline = time.time() + parse_budget_sec
        truncated = False
        parsed_set: set = set()
        for fpath in new_files:
            if time.time() >= budget_deadline:
                truncated = True
                break
            p = Path(fpath)
            try:
                if p.suffix == ".json" and ("report" in p.name.lower() or "output" in str(p.parent)):
                    record = self._prod_parser.parse(fpath)
                    if record:
                        self._records.append(record)
                        report.records_by_source["production_report"] = (
                            report.records_by_source.get("production_report", 0) + 1)
                elif p.suffix == ".log" or (p.suffix == ".txt" and "log" in p.name.lower()):
                    record = self._syslog_parser.parse_log_file(fpath)
                    if record:
                        self._records.append(record)
                        report.records_by_source["system_log"] = (
                            report.records_by_source.get("system_log", 0) + 1)
                elif p.suffix == ".md":
                    record = self._daily_parser.parse_daily_note(fpath)
                    if record:
                        self._records.append(record)
                        report.records_by_source["daily_note"] = (
                            report.records_by_source.get("daily_note", 0) + 1)
                parsed_set.add(fpath)
            except Exception as e:
                logger.debug(f"[Harvester] Skip {fpath}: {e}")
                parsed_set.add(fpath)  # 解析失败也标记，避免反复解析坏文件

        # 预算截断: 未解析完的文件不写入 state，下次汲取继续处理
        if truncated:
            for fpath in new_files:
                if fpath not in parsed_set:
                    current_state.pop(fpath, None)
            remaining = len(new_files) - len(parsed_set)
            logger.warning(
                f"[Harvester] 解析预算({parse_budget_sec:.0f}s)耗尽，"
                f"{remaining} 个文件留待下次汲取"
            )

        # 结构化数据: 如果有变化则重新解析（同样受预算保护）
        struct_changed = any(
            "error_pattern" in f or "fallback" in f or "pipeline_runs" in f
            for f in new_files
        )
        if struct_changed and not truncated:
            struct_records = self._struct_parser.build_records_from_structured()
            for record in struct_records:
                self._records.append(record)
                report.records_by_source["structured_data"] = (
                    report.records_by_source.get("structured_data", 0) + 1)

        report.total_sources_scanned = len(new_files)
        report.total_records_extracted = len(self._records)
        report.total_error_patterns = sum(len(r.error_patterns) for r in self._records)
        report.total_stage_experiences = sum(len(r.stages) for r in self._records)

        # 注入新记录到各模块
        if self._records:
            report.injection_results = self._injector.inject_all(self._records)

        # 项目5集成: River 在线学习 — 每条新记录实时更新预测模型
        if self._records:
            self._update_online_learner(self._records)

        # 保存状态
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(current_state, f, ensure_ascii=False)

        report.duration_sec = time.time() - start_time
        logger.info(
            f"[Harvester] 增量汲取完成: {report.total_records_extracted} 条新记录 "
            f"({report.duration_sec:.1f}s)"
        )
        return report

    def _scan_production_reports(self, report: HarvestReport) -> None:
        """扫描 output_production/ 和 output_director/ 下的报告"""
        search_dirs = [
            self._root / "output_production",
            self._root / "output_director",
            self._root / "test_output_v17_full",
            self._root / "test_output_v17",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for f in search_dir.rglob("*.json"):
                if "report" in f.name.lower():
                    report.total_sources_scanned += 1
                    record = self._prod_parser.parse(str(f))
                    if record:
                        self._records.append(record)
                        report.records_by_source["production_report"] = (
                            report.records_by_source.get("production_report", 0) + 1
                        )

    def _scan_test_logs(self, report: HarvestReport) -> None:
        """扫描测试日志"""
        test_dirs = [
            self._root / "test_output_v17_full",
            self._root / "test_output_v17",
        ]

        for search_dir in test_dirs:
            if not search_dir.exists():
                continue

            # JSON 报告
            for f in search_dir.rglob("*report*.json"):
                report.total_sources_scanned += 1
                record = self._test_parser.parse_report_json(str(f))
                if record:
                    self._records.append(record)
                    report.records_by_source["test_log"] = (
                        report.records_by_source.get("test_log", 0) + 1
                    )

            # TXT 日志
            for f in search_dir.rglob("*.txt"):
                if "log" in f.name.lower() or "pipeline" in f.name.lower():
                    report.total_sources_scanned += 1
                    record = self._test_parser.parse_pipeline_log(str(f))
                    if record:
                        self._records.append(record)
                        report.records_by_source["test_log"] = (
                            report.records_by_source.get("test_log", 0) + 1
                        )

    def _scan_system_logs(self, report: HarvestReport) -> None:
        """扫描 logs/ 目录"""
        logs_dir = self._root / "logs"
        if not logs_dir.exists():
            return

        for f in logs_dir.glob("*.log"):
            report.total_sources_scanned += 1
            record = self._syslog_parser.parse_log_file(str(f))
            if record:
                self._records.append(record)
                report.records_by_source["system_log"] = (
                    report.records_by_source.get("system_log", 0) + 1
                )

    def _scan_structured_data(self, report: HarvestReport) -> None:
        """扫描 data/ 下的结构化数据"""
        records = self._struct_parser.build_records_from_structured()
        for record in records:
            self._records.append(record)
            report.total_sources_scanned += 1
            report.records_by_source["structured_data"] = (
                report.records_by_source.get("structured_data", 0) + 1
            )

    def _scan_daily_notes(self, report: HarvestReport) -> None:
        """扫描 00-每日记录/"""
        notes_dir = self._root / "00-每日记录"
        if not notes_dir.exists():
            return

        for f in notes_dir.glob("*.md"):
            report.total_sources_scanned += 1
            record = self._daily_parser.parse_daily_note(str(f))
            if record and (record.stages or record.error_patterns):
                self._records.append(record)
                report.records_by_source["daily_note"] = (
                    report.records_by_source.get("daily_note", 0) + 1
                )

    def _scan_flagship_outputs(self, report: HarvestReport) -> None:
        """扫描 output/flagship_*/ 旗舰管线产物"""
        output_dir = self._root / "output"
        if not output_dir.exists():
            return

        flagship_records = self._flagship_parser.parse_all_runs(output_dir)
        for record in flagship_records:
            self._records.append(record)
            report.total_sources_scanned += 1
            report.records_by_source["flagship_manifest"] = (
                report.records_by_source.get("flagship_manifest", 0) + 1
            )

        if flagship_records:
            logger.info(
                f"[Harvester] 旗舰管线产物: {len(flagship_records)} 条运行记录"
            )

    def get_records(self) -> list[ExperienceRecord]:
        """获取所有提取的经验记录"""
        return list(self._records)

    def _update_online_learner(self, records: list[ExperienceRecord]) -> None:
        """项目5: 使用 River 在线学习器实时更新阶段预测模型

        每条新记录都会更新对应阶段的:
        - 耗时预测 (在线回归)
        - 成功率估计 (在线统计)
        - 质量分趋势 (在线统计)
        - 漂移检测 (连续异常时标记)

        S1闭环: 检测到漂移后，联动MetaStrategyEngine降权旧策略
        """
        try:
            from integrations.river_online_learner import RiverOnlineLearner
            learner = RiverOnlineLearner(
                data_dir=str(self._root / "data" / "online_learner")
            )
            for record in records:
                for stage_exp in record.stages:
                    learner.observe(
                        stage_name=stage_exp.stage_name,
                        duration=stage_exp.duration_sec,
                        success=stage_exp.success,
                        quality=stage_exp.quality_score,
                        params={"engine": stage_exp.engine_used} if stage_exp.engine_used else None,
                    )
            learner.save()
            logger.debug(f"[P5/River] Online learner updated with {len(records)} records")

            # S1闭环: 消费River漂移信号 → 联动MetaStrategyEngine降权
            self._apply_drift_to_strategy_engine(learner)
        except Exception as e:
            logger.debug(f"[P5/River] Online learner update skipped: {e}")

    def _apply_drift_to_strategy_engine(self, learner: "RiverOnlineLearner") -> None:
        """S1: 将River漂移信号联动到MetaStrategyEngine，触发策略降权

        获取所有阶段的漂移计数，对drift_counter >= 3的阶段触发降权。
        drift_score = drift_counter / 3.0 (归一化到严重度)
        """
        try:
            from core.meta_strategy_engine import get_strategy_engine
            engine = get_strategy_engine()
            applied_any = False
            for stage_name, stats in learner._stage_stats.items():
                drift_counter = learner._drift_counters.get(stage_name, 0)
                if drift_counter >= 3:
                    drift_score = drift_counter / 3.0
                    engine.apply_drift_penalty(stage_name, drift_score)
                    applied_any = True
                    logger.info(
                        f"[S1] Drift detected in '{stage_name}' "
                        f"(counter={drift_counter}), applied strategy penalty"
                    )
            if not applied_any:
                logger.debug("[S1] No drift detected, no strategy penalty applied")
        except Exception as e:
            logger.debug(f"[S1] Drift→Strategy linkage skipped: {e}")


# ============================================================================
#  便捷函数
# ============================================================================

_harvester_instance: ExperienceHarvester | None = None


def run_harvest(project_root: str = ".") -> HarvestReport:
    """运行一次完整的经验汲取"""
    harvester = ExperienceHarvester(project_root=project_root)
    return harvester.harvest()


def get_harvester(project_root: str = ".") -> ExperienceHarvester:
    """获取经验汲取器实例"""
    return ExperienceHarvester(project_root=project_root)
