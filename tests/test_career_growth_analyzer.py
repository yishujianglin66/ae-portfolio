#!/usr/bin/env python3
"""
CareerGrowthEngine 单元测试 - 职场学习成长分析引擎

测试重点：
1. 日常记录的数据结构和验证
2. V4 分析的集成和错误处理
3. 月度报告生成的逻辑
4. 文件保存和加载的正确性
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from career_growth_analyzer import (
    CareerGrowthEngine,
    DailyRecord,
    MonthlyReport,
    generate_monthly_report,
    get_engine,
    record_day,
)


class TestDailyRecordDataclass(unittest.TestCase):
    """DailyRecord 数据结构测试"""

    def test_daily_record_creation(self):
        """应正确创建日常记录"""
        record = DailyRecord(
            date="2026-07-16",
            weekday="周三",
            content="今天学习了设备维护"
        )
        
        self.assertEqual(record.date, "2026-07-16")
        self.assertEqual(record.weekday, "周三")
        self.assertEqual(record.content, "今天学习了设备维护")
        self.assertEqual(record.work_content, [])
        self.assertEqual(record.learning_points, [])

    def test_daily_record_with_analysis(self):
        """包含分析结果的记录应正确存储"""
        record = DailyRecord(
            date="2026-07-16",
            weekday="周三",
            content="test content",
            psychological_journey="情绪积极，成就感高",
            growth_points=["学会设备操作"],
            improvement_suggestions=["加强理论学习"]
        )
        
        self.assertEqual(len(record.growth_points), 1)
        self.assertIn("学会设备操作", record.growth_points)

    def test_daily_record_defaults(self):
        """默认值应正确设置"""
        record = DailyRecord(date="2026-07-16", weekday="周三", content="test")
        
        self.assertEqual(record.model_used, "deepseek-v4-pro")
        self.assertEqual(record.psychological_journey, "")


class TestMonthlyReportDataclass(unittest.TestCase):
    """MonthlyReport 数据结构测试"""

    def test_monthly_report_creation(self):
        """应正确创建月度报告"""
        report = MonthlyReport(
            month="2026-07",
            total_days=10,
            records=[]
        )
        
        self.assertEqual(report.month, "2026-07")
        self.assertEqual(report.total_days, 10)

    def test_monthly_report_with_records(self):
        """包含记录的报告应正确存储"""
        record = DailyRecord(date="2026-07-01", weekday="周二", content="test")
        report = MonthlyReport(
            month="2026-07",
            total_days=1,
            records=[record]
        )
        
        self.assertEqual(len(report.records), 1)


class TestCareerGrowthEngineInit(unittest.TestCase):
    """CareerGrowthEngine 初始化测试"""

    def test_engine_creation_with_default_dir(self):
        """应使用默认目录"""
        engine = CareerGrowthEngine()
        
        self.assertIsNotNone(engine.data_dir)
        self.assertIsNotNone(engine.records_dir)
        self.assertIsNotNone(engine.reports_dir)

    def test_engine_creation_with_custom_dir(self):
        """应接受自定义目录"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            engine = CareerGrowthEngine(data_dir=temp_dir)
            
            self.assertEqual(str(engine.data_dir), temp_dir)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_engine_directories_created(self):
        """应创建必要目录"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            engine = CareerGrowthEngine(data_dir=temp_dir)
            
            self.assertTrue(engine.records_dir.exists())
            self.assertTrue(engine.reports_dir.exists())
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestCareerGrowthEngineRecordDay(unittest.TestCase):
    """record_day 方法测试"""

    def setUp(self):
        # 2026-08-27: 关闭 V4 分析，避免 record_day 发起真实 LLM 网络请求
        # （无超时的 requests 调用会挂死整个测试会话）。
        self._v4_patcher = patch('career_growth_analyzer.V4_AVAILABLE', False)
        self._v4_patcher.start()
        self.temp_dir = tempfile.mkdtemp()
        self.engine = CareerGrowthEngine(data_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self._v4_patcher.stop()

    def test_record_day_creates_record(self):
        """应创建日常记录"""
        record = self.engine.record_day("今天学习了设备维护")
        
        self.assertIsNotNone(record)
        self.assertEqual(record.date, datetime.now().strftime("%Y-%m-%d"))

    def test_record_day_with_custom_date(self):
        """应接受自定义日期"""
        record = self.engine.record_day(
            "test content",
            date="2026-07-01"
        )
        
        self.assertEqual(record.date, "2026-07-01")

    def test_record_day_weekday_calculation(self):
        """应正确计算星期几"""
        record = self.engine.record_day("test", date="2026-07-16")
        
        # 2026-07-16 是周四
        self.assertEqual(record.weekday, "周四")

    @patch('career_growth_analyzer.V4_AVAILABLE', False)
    def test_record_day_without_v4(self):
        """V4 不可用时应跳过分析"""
        engine = CareerGrowthEngine(data_dir=self.temp_dir)
        
        record = engine.record_day("test content")
        
        self.assertEqual(record.psychological_journey, "")


class TestCareerGrowthEngineMonthReport(unittest.TestCase):
    """generate_monthly_report 方法测试"""

    def setUp(self):
        # 同上：隔离真实 LLM 调用（record_day 聚合场景）。
        self._v4_patcher = patch('career_growth_analyzer.V4_AVAILABLE', False)
        self._v4_patcher.start()
        self.temp_dir = tempfile.mkdtemp()
        self.engine = CareerGrowthEngine(data_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self._v4_patcher.stop()

    def test_generate_monthly_report_empty(self):
        """无记录时应生成空报告"""
        report = self.engine.generate_monthly_report(2026, 7)
        
        self.assertEqual(report.month, "2026-07")
        self.assertEqual(report.total_days, 0)

    def test_generate_monthly_report_with_records(self):
        """有记录时应正确聚合"""
        # 添加记录
        self.engine.record_day("day 1 content", date="2026-07-01")
        self.engine.record_day("day 2 content", date="2026-07-02")
        
        report = self.engine.generate_monthly_report(2026, 7)
        
        self.assertEqual(report.total_days, 2)

    @patch('career_growth_analyzer.V4_AVAILABLE', False)
    def test_generate_monthly_report_without_v4(self):
        """V4 不可用时应跳过分析"""
        engine = CareerGrowthEngine(data_dir=self.temp_dir)
        engine.record_day("test", date="2026-07-01")
        
        report = engine.generate_monthly_report(2026, 7)
        
        self.assertEqual(report.overall_growth, "")


class TestCareerGrowthEngineGetWeekday(unittest.TestCase):
    """_get_weekday 方法测试"""

    def setUp(self):
        self.engine = CareerGrowthEngine()

    def test_get_weekday_monday(self):
        """周一应返回正确"""
        weekday = self.engine._get_weekday("2026-07-13")
        self.assertEqual(weekday, "周一")

    def test_get_weekday_sunday(self):
        """周日应返回正确"""
        weekday = self.engine._get_weekday("2026-07-19")
        self.assertEqual(weekday, "周日")


class TestCareerGrowthEngineExtractStructuredInfo(unittest.TestCase):
    """_extract_structured_info 方法测试"""

    def setUp(self):
        self.engine = CareerGrowthEngine()
        self.record = DailyRecord(
            date="2026-07-16",
            weekday="周四",
            content="test"
        )

    def test_extract_growth_keywords(self):
        """应提取成长关键词"""
        analysis = "今天学会了设备操作，有很大进步。"
        
        self.engine._extract_structured_info(self.record, analysis)
        
        self.assertGreater(len(self.record.growth_points), 0)

    def test_extract_suggestion_keywords(self):
        """应提取建议关键词"""
        analysis = "建议加强理论学习，可以多看资料。"
        
        self.engine._extract_structured_info(self.record, analysis)
        
        self.assertGreater(len(self.record.improvement_suggestions), 0)


class TestCareerGrowthEngineQuickFunctions(unittest.TestCase):
    """快捷函数测试"""

    def test_get_engine_singleton(self):
        """get_engine 应返回单例"""
        engine1 = get_engine()
        engine2 = get_engine()
        
        self.assertIs(engine1, engine2)


class TestCareerGrowthEngineEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def setUp(self):
        # 同上：边界用例只验证内容存取，不需真实 LLM 分析。
        self._v4_patcher = patch('career_growth_analyzer.V4_AVAILABLE', False)
        self._v4_patcher.start()
        self.temp_dir = tempfile.mkdtemp()
        self.engine = CareerGrowthEngine(data_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self._v4_patcher.stop()

    def test_empty_content(self):
        """空内容应正确处理"""
        record = self.engine.record_day("")
        
        self.assertEqual(record.content, "")

    def test_long_content(self):
        """长内容应正确处理"""
        long_content = "学习内容。" * 1000
        record = self.engine.record_day(long_content)
        
        self.assertEqual(record.content, long_content)

    def test_special_characters_in_content(self):
        """特殊字符应正确处理"""
        content = "学习了设备【维护】\n包含换行和\t制表符"
        record = self.engine.record_day(content)
        
        self.assertIn("【维护】", record.content)


if __name__ == "__main__":
    unittest.main(verbosity=2)