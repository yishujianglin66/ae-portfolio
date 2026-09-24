# -*- coding: utf-8 -*-
"""经验汲取器解析层特征化测试（2026-09-22）。

背景：覆盖率快照里 `core/experience_harvester.py` 未覆盖 792 行、仅 10.75%，
是本仓最靠前的几个缺口之一。但它的**解析层**（ProductionReportParser /
TestLogParser / SystemLogParser / DailyNoteParser）与注入层的**纯映射函数**
（_infer_engine / _infer_strategy / _estimate_duration）都不依赖外部服务，
是最适合特征化的对象 —— 单测成本低、断言强。

本文件的取向：锁**真实契约**（含"坏输入返回 None 而非抛异常"这类降级语义），
不追求行数。
"""
import json
import sys
import time
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.experience_harvester import (  # noqa: E402
    DailyNoteParser,
    ExperienceHarvester,
    ExperienceInjector,
    ExperienceRecord,
    HarvestReport,
    ProductionReportParser,
    StageExperience,
    SystemLogParser,
    TestLogParser,
)


def _write(tmp_path: Path, name: str, text: str) -> str:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# ProductionReportParser
# ---------------------------------------------------------------------------

class TestProductionReportParser:
    def _report(self, **kw) -> str:
        base = {
            "timestamp": "2026-09-20 12:34:56",
            "memory_final": {"total_gb": 32.0, "avail_gb": 11.5},
            "log": [],
        }
        base.update(kw)
        return json.dumps(base, ensure_ascii=False)

    def test_missing_file_returns_none(self, tmp_path):
        assert ProductionReportParser().parse(str(tmp_path / "nope.json")) is None

    def test_bad_json_returns_none(self, tmp_path):
        p = _write(tmp_path, "bad.json", "{not json")
        assert ProductionReportParser().parse(p) is None

    def test_minimal_report_fields(self, tmp_path):
        p = _write(tmp_path, "r.json", self._report())
        rec = ProductionReportParser().parse(p)
        assert rec is not None
        assert rec.source_type == "production_report"
        assert rec.record_id.startswith("prod_")
        assert rec.source_file == p
        assert rec.memory_total_gb == 32.0
        assert rec.memory_available_gb == 11.5

    def test_timestamp_parsed_to_epoch(self, tmp_path):
        p = _write(tmp_path, "r.json", self._report())
        rec = ProductionReportParser().parse(p)
        assert rec.timestamp > 0
        # 2026-09-20 12:34:56 本地时区
        assert abs((rec.timestamp - time.time()) / 86400) < 800

    def test_invalid_timestamp_falls_back_to_now(self, tmp_path):
        p = _write(tmp_path, "r.json", self._report(timestamp="not-a-time"))
        rec = ProductionReportParser().parse(p)
        assert rec is not None and abs(rec.timestamp - time.time()) < 60

    def test_phase_lines_create_stages_with_duration(self, tmp_path):
        log = ["[Phase 1] 感知分析... 完成", "耗时12s",
               "[Phase 4] 渲染执行... 完成", "耗时95s"]
        p = _write(tmp_path, "r.json", self._report(log=log))
        rec = ProductionReportParser().parse(p)
        by_name = {s.stage_name: s for s in rec.stages}
        assert "perceive" in by_name and by_name["perceive"].duration_sec == 12.0
        assert "render" in by_name and by_name["render"].duration_sec == 95.0

    def test_engines_detected_from_log(self, tmp_path):
        log = ["AE Bridge 连通", "DaVinci Resolve 已就绪", "FFmpeg 就绪"]
        p = _write(tmp_path, "r.json", self._report(log=log))
        rec = ProductionReportParser().parse(p)
        assert {"ae", "davinci", "ffmpeg"} <= set(rec.engines_available)

    def test_warn_and_error_lines_become_error_patterns(self, tmp_path):
        log = ["[WARN] 素材缺失", "[ERROR] 渲染失败: timeout"]
        p = _write(tmp_path, "r.json", self._report(log=log))
        rec = ProductionReportParser().parse(p)
        assert len(rec.error_patterns) >= 2

    def test_memory_from_log_takes_max(self, tmp_path):
        log = ["可用=8.0GB", "可用=13.5GB"]
        p = _write(tmp_path, "r.json", self._report(log=log))
        rec = ProductionReportParser().parse(p)
        assert rec.memory_available_gb == 13.5

    def test_quality_caps_at_100(self, tmp_path):
        """输出文件数 × 7 且封顶 100（20 个文件即封顶）。"""
        log = ["输出文件 20 个"]
        p = _write(tmp_path, "r.json", self._report(log=log))
        rec = ProductionReportParser().parse(p)
        assert rec.overall_quality == 100.0

    def test_phase_map_covers_six_phases(self):
        pm = ProductionReportParser.PHASE_MAP
        assert set(pm) == {"Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5", "Phase 6"}
        assert pm["Phase 2"] == "execute" and pm["Phase 4"] == "render"


class TestParserPureHelpers:
    @pytest.mark.parametrize("stage,engines,expected", [
        ("execute", {"ae"}, "ae"),
        ("execute", set(), "ffmpeg"),
        ("plan", {"ae", "davinci"}, "ae"),
        ("render", {"davinci", "ae"}, "davinci"),   # davinci 优先
        ("render", {"ae"}, "ae"),
        ("render", set(), "ffmpeg"),
        ("verify", {"ae", "davinci"}, "ffmpeg"),    # 其余阶段固定 ffmpeg
        ("learn", set(), "ffmpeg"),
    ])
    def test_infer_engine(self, stage, engines, expected):
        assert ProductionReportParser()._infer_engine(stage, engines) == expected

    def test_make_id_deterministic_and_prefixed(self):
        np_ = ProductionReportParser()
        a, b = np_._make_id("output/x/production_report.json"), \
            np_._make_id("output/x/production_report.json")
        assert a == b and a.startswith("prod_") and len(a) == len("prod_") + 12
        assert a != np_._make_id("output/y/production_report.json")


# ---------------------------------------------------------------------------
# 其它解析器：坏输入一律返回 None（降级语义）
# ---------------------------------------------------------------------------

class TestOtherParsersDegrade:
    def test_test_log_parser_missing_file(self, tmp_path):
        assert TestLogParser().parse_report_json(str(tmp_path / "nope.json")) is None

    def test_test_log_parser_bad_json(self, tmp_path):
        p = _write(tmp_path, "bad.json", "}{")
        assert TestLogParser().parse_report_json(p) is None

    def test_system_log_parser_missing_file(self, tmp_path):
        assert SystemLogParser().parse_log_file(str(tmp_path / "nope.log")) is None

    def test_daily_note_parser_missing_file(self, tmp_path):
        assert DailyNoteParser().parse_daily_note(str(tmp_path / "nope.md")) is None

    def test_daily_note_parser_reads_markdown(self, tmp_path):
        """日报是自由文本：解析器必须容忍任意内容（不抛异常）。"""
        p = _write(tmp_path, "note.md", "# 2026-09-20\n- 完成 A\n- 失败 B\n")
        rec = DailyNoteParser().parse_daily_note(p)
        assert rec is None or isinstance(rec, ExperienceRecord)


# ---------------------------------------------------------------------------
# 注入层纯映射
# ---------------------------------------------------------------------------

class TestInjectorPureLogic:
    def test_estimate_duration_defaults(self):
        inj = ExperienceInjector()
        assert inj._estimate_duration("render") == 120.0
        assert inj._estimate_duration("perceive") == 15.0
        assert inj._estimate_duration("unknown_stage") == 30.0   # 兜底

    @pytest.mark.parametrize("engines,success,quality,expected", [
        (["davinci", "ae"], True, 90, "default_balanced"),   # 双引擎 → 平衡
        (["ae"], True, 50, "default_quality"),
        ([], True, 95, "default_quality"),                   # 无引擎但高质量
        ([], True, 50, "default_balanced"),
        ([], False, 0, "default_safe"),                      # 失败 → 保守
    ])
    def test_infer_strategy(self, engines, success, quality, expected):
        inj = ExperienceInjector()
        rec = ExperienceRecord(engines_available=list(engines),
                               overall_success=success, overall_quality=quality)
        assert inj._infer_strategy(rec) == expected


# ---------------------------------------------------------------------------
# 顶层收割器：空项目必须产出空报告而非异常
# ---------------------------------------------------------------------------

class TestHarvesterEmptyProject:
    def test_harvest_on_empty_root_returns_report(self, tmp_path):
        h = ExperienceHarvester(project_root=str(tmp_path))
        rep = h.harvest()
        assert isinstance(rep, HarvestReport)
        assert rep.total_records_extracted == 0
        assert rep.total_sources_scanned == 0
        assert isinstance(h.get_records(), list)

    def test_scan_methods_tolerate_missing_dirs(self, tmp_path):
        """各 _scan_* 必须容错：目录不存在时只记账、不抛异常。"""
        h = ExperienceHarvester(project_root=str(tmp_path))
        rep = HarvestReport()
        for name in ("_scan_production_reports", "_scan_test_logs",
                     "_scan_system_logs", "_scan_structured_data",
                     "_scan_daily_notes", "_scan_flagship_outputs"):
            getattr(h, name)(rep)
        assert rep.total_records_extracted == 0

    def test_stage_experience_defaults(self):
        s = StageExperience(stage_name="render")
        assert s.success is True and s.duration_sec == 0.0 and s.params == {}
