"""
职场学习成长分析引擎
===================

核心功能：
1. 日常记录解析 - 从对话式输入提取关键信息
2. V4深度分析 - 心理历程、能力成长、改进方向
3. 月度报告生成 - 整合月度数据，生成结构化报告
4. 知识补充搜索 - 多平台搜索相关知识

使用方式：
    from career_growth_analyzer import CareerGrowthEngine

    engine = CareerGrowthEngine()

    # 日常记录
    engine.record_day("今天我做了XXX，学到了XXX...")

    # 月度报告
    report = engine.generate_monthly_report(2026, 7)

    # 知识搜索
    knowledge = engine.search_knowledge("锂电池维护", platforms=["知乎", "小红书"])
"""

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ai_agent import V4Agent
    V4_AVAILABLE = True
except ImportError:
    V4_AVAILABLE = False


@dataclass
class DailyRecord:
    """日常记录数据结构"""
    date: str
    weekday: str
    content: str
    work_content: list[str] = field(default_factory=list)
    learning_points: list[str] = field(default_factory=list)
    difficulties: list[str] = field(default_factory=list)
    emotions: list[str] = field(default_factory=list)
    psychological_journey: str = ""
    growth_points: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)
    created_at: str = ""
    analyzed_at: str = ""
    model_used: str = "deepseek-v4-pro"


@dataclass
class MonthlyReport:
    """月度报告数据结构"""
    month: str
    total_days: int
    records: list[DailyRecord]
    overall_growth: str = ""
    psychological_trajectory: dict = field(default_factory=dict)
    skill_progress: dict[str, Any] = field(default_factory=dict)
    key_achievements: list = field(default_factory=list)
    areas_for_improvement: list = field(default_factory=list)
    next_month_goals: list = field(default_factory=list)
    generated_at: str = ""
    model_used: str = "deepseek-v4-pro"


class CareerGrowthEngine:
    """职场学习成长分析引擎"""

    PSYCHOLOGY_PROMPT = """你是一位专业的职场心理分析师，负责分析职场新人的心理历程。

用户背景：
- 姓名：闫起名
- 公司：力王新能源
- 岗位：设备维护技术员（实习生）
- 背景：3+1校企合作，桂林信息科技学院智能制造工程专业
- 特点：性格开朗、善于沟通、当选班长

请根据用户的日常描述，进行深度心理历程分析：

1. **情绪分析**：
   - 当天的情绪基调（积极/消极/中性）
   - 情绪波动点（什么触发了情绪变化）
   - 情绪管理建议

2. **心理状态**：
   - 压力水平（高/中/低）
   - 动力来源（内在/外在）
   - 归属感和成就感

3. **成长轨迹**：
   - 相比之前有什么进步
   - 正在克服什么挑战
   - 心理韧性的变化

4. **改进建议**：
   - 针对性的心理调适建议
   - 学习策略优化
   - 人际关系建议

请用温暖、鼓励、专业的语气，给出结构化的分析报告。"""

    MONTHLY_PROMPT = """你是一位专业的职场成长顾问，负责整合分析月度学习数据。

用户背景：
- 姓名：闫起名
- 公司：力王新能源
- 岗位：设备维护技术员（实习生）
- 背景：3+1校企合作，桂林信息科技学院智能制造工程专业

请根据用户本月的所有日常记录，生成月度成长报告：

## 一、月度概览
- 本月工作天数、主要工作内容
- 本月学习投入时间
- 整体成长评价（1-10分）

## 二、心理历程
- 本月情绪变化曲线
- 压力峰值和低谷
- 心理韧性变化

## 三、能力成长
- 专业技能进步
- 软技能提升
- 认知能力变化

## 四、关键成就
- 本月最重要的3个成就
- 获得的认可和肯定

## 五、改进空间
- 仍需加强的能力
- 遇到的持续挑战
- 改进行动计划

## 六、下月目标
- 学习目标
- 行动计划
- 预期成果

请用专业、鼓励、有指导性的语气生成报告。"""

    def __init__(self, data_dir: str | None = None):
        if data_dir is None:
            self.data_dir = Path(__file__).parent / "14-职场学习成长档案"
        else:
            self.data_dir = Path(data_dir)
        self.records_dir = self.data_dir / "01-日常记录"
        self.reports_dir = self.data_dir / "02-月度报告"
        self._v4_agent = None
        self._records: dict[str, DailyRecord] = {}
        self._ensure_dirs()
        self._load_records()

    def _ensure_dirs(self):
        """确保目录存在"""
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def _load_records(self):
        """加载已有记录"""
        if not self.records_dir.exists():
            return
        for record_file in self.records_dir.glob("*_日常记录.md"):
            try:
                date_str = record_file.stem.split("_")[0]
                # 从文件中提取内容（简化实现，只记录日期）
                self._records[date_str] = DailyRecord(
                    date=date_str,
                    weekday=self._get_weekday(date_str),
                    content="(已加载的历史记录)"
                )
            except Exception:
                continue

    @property
    def v4_agent(self):
        """获取V4 Agent实例"""
        if self._v4_agent is None:
            if not V4_AVAILABLE:
                raise RuntimeError("V4Agent不可用，请检查ai_agent.py")
            self._v4_agent = V4Agent()
        return self._v4_agent

    def record_day(self, content: str, date: str | None = None) -> DailyRecord:
        """记录一天的内容（对话式输入）

        Args:
            content: 用户自由描述的内容
            date: 日期，默认今天

        Returns:
            DailyRecord: 包含V4分析结果的记录
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        weekday = self._get_weekday(date)
        record = DailyRecord(
            date=date,
            weekday=weekday,
            content=content,
            created_at=datetime.now().isoformat()
        )

        if V4_AVAILABLE:
            self._analyze_record(record)

        self._records[date] = record
        self._save_record(record)
        return record

    def _get_weekday(self, date: str) -> str:
        """获取星期几"""
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        dt = datetime.strptime(date, "%Y-%m-%d")
        return weekdays[dt.weekday()]

    def _analyze_record(self, record: DailyRecord):
        """使用V4-Pro深度分析记录"""
        prompt = self.PSYCHOLOGY_PROMPT + "\n\n---\n用户今日描述：\n" + record.content + "\n\n请进行心理历程分析："
        try:
            analysis = self.v4_agent.ask(prompt, model="pro")
            record.psychological_journey = analysis
            record.analyzed_at = datetime.now().isoformat()
            record.model_used = "deepseek-v4-pro"
            self._extract_structured_info(record, analysis)
        except Exception as e:
            record.psychological_journey = f"分析失败: {e}"

    def _extract_structured_info(self, record: DailyRecord, analysis: str):
        """从V4分析结果中提取结构化信息"""
        # 成长关键词
        growth_keywords = ["进步", "学会", "掌握", "成长", "提升", "突破", "成长点"]
        for keyword in growth_keywords:
            if keyword in analysis:
                record.growth_points.append(f"包含成长关键词: {keyword}")

        # 建议关键词
        suggestion_keywords = ["建议", "加强", "改进", "需要", "应该", "可以", "优化"]
        for keyword in suggestion_keywords:
            if keyword in analysis:
                record.improvement_suggestions.append(f"包含建议关键词: {keyword}")

    def _save_record(self, record: DailyRecord):
        """保存记录到文件"""
        record_dir = self.records_dir / record.date
        record_dir.mkdir(parents=True, exist_ok=True)
        record_file = record_dir / f"{record.date}_日常记录.md"
        with open(record_file, "w", encoding="utf-8") as f:
            f.write(self._format_record_markdown(record))

    def _format_record_markdown(self, record: DailyRecord) -> str:
        """格式化记录为Markdown"""
        growth_text = "\n".join(f"- {g}" for g in record.growth_points) if record.growth_points else "（暂无）"
        suggestion_text = "\n".join(f"- {s}" for s in record.improvement_suggestions) if record.improvement_suggestions else "（暂无）"
        return (
            f"# 日常记录 - {record.date}\n\n"
            f"> 记录日期：{record.date}  \n"
            f"> 星期：{record.weekday}  \n"
            f"> 分析模型：{record.model_used}\n\n"
            f"---\n\n## 用户描述\n\n{record.content}\n\n"
            f"---\n\n## V4深度分析\n\n### 心理历程分析\n\n{record.psychological_journey}\n\n"
            f"---\n\n## 成长点识别\n\n{growth_text}\n\n"
            f"---\n\n## 改进建议\n\n{suggestion_text}\n\n"
            f"---\n\n*记录时间：{record.created_at}*  \n*分析时间：{record.analyzed_at}*\n"
        )

    def generate_monthly_report(self, year: int, month: int) -> MonthlyReport:
        """生成月度报告

        Args:
            year: 年份
            month: 月份

        Returns:
            MonthlyReport: 月度报告
        """
        month_str = f"{year}-{month:02d}"

        # 先从内存记录中筛选
        month_records = [r for r in self._records.values() if r.date.startswith(month_str)]

        # 如果内存中没有，从文件加载
        if not month_records:
            month_records = self._load_month_records(month_str)

        report = MonthlyReport(
            month=month_str,
            total_days=len(month_records),
            records=month_records,
            generated_at=datetime.now().isoformat()
        )

        if V4_AVAILABLE and month_records:
            self._generate_monthly_analysis(report)

        self._save_monthly_report(report)
        return report

    def _load_month_records(self, month_str: str) -> list[DailyRecord]:
        """从文件加载月度记录"""
        records = []
        if not self.records_dir.exists():
            return records
        for record_file in self.records_dir.glob("*_日常记录.md"):
            try:
                date_str = record_file.stem.split("_")[0]
                if date_str.startswith(month_str):
                    records.append(DailyRecord(
                        date=date_str,
                        weekday=self._get_weekday(date_str),
                        content="(从文件加载的记录)"
                    ))
            except Exception:
                continue
        return records

    def _generate_monthly_analysis(self, report: MonthlyReport):
        """使用V4-Pro生成月度分析"""
        records_text = "\n\n---\n\n".join(
            f"## {r.date} ({r.weekday})\n\n{r.content}" for r in report.records
        )
        prompt = self.MONTHLY_PROMPT + "\n\n---\n本月所有记录：\n" + records_text + "\n\n请生成月度成长报告："
        try:
            analysis = self.v4_agent.ask(prompt, model="pro")
            report.overall_growth = analysis
            report.model_used = "deepseek-v4-pro"
        except Exception as e:
            report.overall_growth = f"分析失败: {e}"

    def _save_monthly_report(self, report: MonthlyReport):
        """保存月度报告"""
        report_file = self.reports_dir / f"{report.month}_月度学习报告.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(self._format_monthly_report_markdown(report))

    def _format_monthly_report_markdown(self, report: MonthlyReport) -> str:
        """格式化月度报告为Markdown"""
        records_list = "\n".join(
            f"- [{r.date}] {r.content[:50]}..." for r in report.records
        ) if report.records else "（无记录）"
        return (
            f"# {report.month} 月度学习报告\n\n"
            f"> 报告月份：{report.month}  \n"
            f"> 记录天数：{report.total_days}天  \n"
            f"> 分析模型：{report.model_used}\n\n"
            f"---\n\n## 月度成长分析\n\n{report.overall_growth}\n\n"
            f"---\n\n## 本月记录清单\n\n{records_list}\n\n"
            f"---\n\n*生成时间：{report.generated_at}*\n"
        )

    def search_knowledge(self, query: str, platforms: list[str] | None = None) -> dict[str, Any]:
        """搜索知识补充

        Args:
            query: 搜索关键词
            platforms: 平台列表，如 ["知乎", "小红书"]

        Returns:
            搜索结果
        """
        if platforms is None:
            platforms = ["知乎", "小红书", "B站"]
        return {
            "query": query,
            "platforms": platforms,
            "results": [],
            "message": "知识搜索功能需要集成搜索API"
        }

    def get_growth_summary(self) -> str:
        """获取成长摘要"""
        if not self._records:
            return "无记录"
        dates = list(self._records.keys())
        return f"{min(dates)} ~ {max(dates)}（共{len(self._records)}条记录）"


_engine: CareerGrowthEngine | None = None


def get_engine() -> CareerGrowthEngine:
    """获取全局引擎实例"""
    global _engine
    if _engine is None:
        _engine = CareerGrowthEngine()
    return _engine


def record_day(content: str, date: str | None = None) -> DailyRecord:
    """快捷函数：记录一天"""
    return get_engine().record_day(content, date)


def generate_monthly_report(year: int, month: int) -> MonthlyReport:
    """快捷函数：生成月度报告"""
    return get_engine().generate_monthly_report(year, month)


if __name__ == "__main__":
    print("=" * 60)
    print("职场学习成长分析引擎 - 测试")
    print("=" * 60)

    test_content = """
今天是我入职力王新能源的第一天，参加了公司的入职培训。

工作内容：
1. 办理入职手续，领取工牌和办公用品
2. 学习公司企业文化和发展历程
3. 参加学长见面会，听前辈分享经验
4. 参加能量操，感受公司活力
5. 参加班委竞选，成功当选班长！

学习收获：
- 了解了力王新能源的发展历程和核心价值观
- 学会了如何在团队中展现自己
- 明白了作为班长的责任

心情：
- 很激动，能当选班长很开心
- 有点紧张，担心能否胜任
- 对未来充满期待
"""

    print("\n测试内容：")
    print(test_content[:100] + "...")

    engine = CareerGrowthEngine()

    if V4_AVAILABLE:
        print("\n开始V4深度分析...")
        record = engine.record_day(test_content)
        print(f"\n记录时间：{record.date}")
        print(f"分析结果：{record.psychological_journey[:200]}...")
    else:
        print("\nV4不可用，跳过分析")
        record = engine.record_day(test_content)
        print(f"\n记录时间：{record.date}")

    print("\n" + "=" * 60)
    print("测试完成")
