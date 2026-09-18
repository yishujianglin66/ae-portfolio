#!/usr/bin/env python3
"""
反馈管理器 v1.0
建立完整的反馈通道，支持学习循环和置信度校准

核心功能：
1. 执行结果记录 - 完整记录每次执行的输入、输出和中间状态
2. 学习循环 - 从成功/失败案例中提取模式，优化后续决策
3. 置信度校准 - 根据历史数据调整各模块的置信度评分
4. 模式库管理 - 存储和检索成功的配置模式
5. A/B测试支持 - 记录不同策略的对比结果
"""
import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class ExecutionRecord:
    record_id: str = ""
    timestamp: str = ""
    pipeline_id: str = ""
    input_config: dict = field(default_factory=dict)
    perception_result: dict = field(default_factory=dict)
    understanding_result: dict = field(default_factory=dict)
    planning_result: dict = field(default_factory=dict)
    execution_result: dict = field(default_factory=dict)
    feedback_result: dict = field(default_factory=dict)
    duration: float = 0.0
    success: bool = False


@dataclass
class PatternEntry:
    pattern_id: str = ""
    category: str = ""
    mood: str = ""
    style: str = ""
    effect_config: dict = field(default_factory=dict)
    keyframe_config: list[dict] = field(default_factory=list)
    transition_config: list[dict] = field(default_factory=list)
    usage_count: int = 0
    success_rate: float = 0.0
    confidence_score: float = 0.5
    last_used: str = ""


@dataclass
class ConfidenceEntry:
    module: str = ""
    task_type: str = ""
    mood: str = ""
    style: str = ""
    total_executions: int = 0
    successful_executions: int = 0
    average_confidence: float = 0.5
    confidence_history: list[dict] = field(default_factory=list)
    calibrated_score: float = 0.5


class FeedbackManager:
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.records_dir = os.path.join(data_dir, "execution_records")
        self.patterns_dir = os.path.join(data_dir, "patterns")
        self.confidence_dir = os.path.join(data_dir, "confidence")
        self.ab_test_dir = os.path.join(data_dir, "ab_tests")
        
        self._init_directories()
        
        self.patterns: dict[str, PatternEntry] = {}
        self.confidence_store: dict[str, ConfidenceEntry] = {}
        
        self._load_patterns()
        self._load_confidence()

    def _init_directories(self):
        for dir_path in [self.data_dir, self.records_dir, self.patterns_dir, 
                        self.confidence_dir, self.ab_test_dir]:
            os.makedirs(dir_path, exist_ok=True)

    def record_execution(self, 
                        pipeline_id: str,
                        input_config: dict,
                        perception_result: dict,
                        understanding_result: dict,
                        planning_result: dict,
                        execution_result: dict,
                        feedback_result: dict,
                        duration: float = 0.0) -> str:
        """
        记录一次完整的执行结果
        """
        record = ExecutionRecord(
            record_id=self._generate_id(),
            timestamp=datetime.now().isoformat(),
            pipeline_id=pipeline_id,
            input_config=input_config,
            perception_result=perception_result,
            understanding_result=understanding_result,
            planning_result=planning_result,
            execution_result=execution_result,
            feedback_result=feedback_result,
            duration=duration,
            success=execution_result.get("success", False)
        )
        
        record_path = os.path.join(self.records_dir, f"{record.record_id}.json")
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(self._dataclass_to_dict(record), f, ensure_ascii=False, indent=2)
        
        self._update_learning_loop(record)
        self._update_confidence(record)
        
        return record.record_id

    def _generate_id(self) -> str:
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:16]

    def _dataclass_to_dict(self, obj) -> dict:
        if hasattr(obj, '__dataclass_fields__'):
            result = {}
            for field_name in obj.__dataclass_fields__:
                value = getattr(obj, field_name)
                result[field_name] = self._dataclass_to_dict(value)
            return result
        elif isinstance(obj, dict):
            return {k: self._dataclass_to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._dataclass_to_dict(item) for item in obj]
        else:
            return obj

    def _update_learning_loop(self, record: ExecutionRecord):
        """
        从执行记录中学习，提取模式
        """
        if not record.success:
            self._log_failure_pattern(record)
            return
        
        mood = record.understanding_result.get("mood", "unknown")
        style = record.understanding_result.get("style", "default")
        
        pattern_key = f"{mood}_{style}"
        
        if pattern_key not in self.patterns:
            self.patterns[pattern_key] = PatternEntry(
                pattern_id=pattern_key,
                category="style_template",
                mood=mood,
                style=style,
                effect_config={},
                keyframe_config=[],
                transition_config=[],
                usage_count=0,
                success_rate=1.0,
                confidence_score=0.5,
                last_used=record.timestamp
            )
        
        pattern = self.patterns[pattern_key]
        pattern.usage_count += 1
        pattern.last_used = record.timestamp
        
        effects = record.planning_result.get("effects", [])
        keyframes = record.planning_result.get("keyframes", [])
        transitions = record.planning_result.get("transitions", [])
        
        if effects:
            pattern.effect_config = {e["effectName"]: e["settings"] for e in effects}
        
        if keyframes:
            pattern.keyframe_config = keyframes
        
        if transitions:
            pattern.transition_config = transitions
        
        pattern.confidence_score = min(1.0, pattern.confidence_score + 0.05)
        
        self._save_pattern(pattern)

    def _log_failure_pattern(self, record: ExecutionRecord):
        """
        记录失败模式，用于后续分析
        """
        failure_dir = os.path.join(self.records_dir, "failures")
        os.makedirs(failure_dir, exist_ok=True)
        
        failure_data = {
            "record_id": record.record_id,
            "timestamp": record.timestamp,
            "mood": record.understanding_result.get("mood", "unknown"),
            "style": record.understanding_result.get("style", "default"),
            "error": record.execution_result.get("error_message", "Unknown"),
            "planning_result": record.planning_result
        }
        
        failure_path = os.path.join(failure_dir, f"{record.record_id}_failure.json")
        with open(failure_path, "w", encoding="utf-8") as f:
            json.dump(failure_data, f, ensure_ascii=False, indent=2)

    def _update_confidence(self, record: ExecutionRecord):
        """
        更新各模块的置信度
        """
        modules = ["perception", "understanding", "planning", "execution"]
        
        for module in modules:
            result_key = f"{module}_result"
            result_data = getattr(record, result_key, {})
            
            mood = record.understanding_result.get("mood", "unknown")
            style = record.understanding_result.get("style", "default")
            
            confidence_key = f"{module}_{mood}_{style}"
            
            if confidence_key not in self.confidence_store:
                self.confidence_store[confidence_key] = ConfidenceEntry(
                    module=module,
                    task_type="video_generation",
                    mood=mood,
                    style=style,
                    total_executions=0,
                    successful_executions=0,
                    average_confidence=0.5,
                    confidence_history=[],
                    calibrated_score=0.5
                )
            
            entry = self.confidence_store[confidence_key]
            entry.total_executions += 1
            
            if record.success:
                entry.successful_executions += 1
            
            feedback_confidence = record.feedback_result.get("confidence", 0.5)
            entry.confidence_history.append({
                "timestamp": record.timestamp,
                "confidence": feedback_confidence,
                "success": record.success
            })
            
            if len(entry.confidence_history) > 50:
                entry.confidence_history = entry.confidence_history[-50:]
            
            entry.average_confidence = sum(
                h["confidence"] for h in entry.confidence_history
            ) / len(entry.confidence_history)
            
            success_rate = entry.successful_executions / entry.total_executions
            entry.calibrated_score = 0.6 * entry.average_confidence + 0.4 * success_rate
            
            self._save_confidence(entry)

    def _save_pattern(self, pattern: PatternEntry):
        pattern_path = os.path.join(self.patterns_dir, f"{pattern.pattern_id}.json")
        with open(pattern_path, "w", encoding="utf-8") as f:
            json.dump(self._dataclass_to_dict(pattern), f, ensure_ascii=False, indent=2)

    def _save_confidence(self, entry: ConfidenceEntry):
        confidence_path = os.path.join(self.confidence_dir, f"{entry.module}_{entry.mood}_{entry.style}.json")
        with open(confidence_path, "w", encoding="utf-8") as f:
            json.dump(self._dataclass_to_dict(entry), f, ensure_ascii=False, indent=2)

    def _load_patterns(self):
        for filename in os.listdir(self.patterns_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.patterns_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        pattern = PatternEntry(**data)
                        self.patterns[pattern.pattern_id] = pattern
                except:
                    pass

    def _load_confidence(self):
        for filename in os.listdir(self.confidence_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.confidence_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        entry = ConfidenceEntry(**data)
                        key = f"{entry.module}_{entry.mood}_{entry.style}"
                        self.confidence_store[key] = entry
                except:
                    pass

    def get_pattern(self, mood: str, style: str) -> PatternEntry | None:
        """
        获取特定情绪和风格的模式配置
        """
        key = f"{mood}_{style}"
        if key in self.patterns:
            return self.patterns[key]
        return None

    def get_calibrated_confidence(self, module: str, mood: str, style: str) -> float:
        """
        获取经过校准的置信度评分
        """
        key = f"{module}_{mood}_{style}"
        if key in self.confidence_store:
            return self.confidence_store[key].calibrated_score
        
        key_generic = f"{module}_unknown_default"
        if key_generic in self.confidence_store:
            return self.confidence_store[key_generic].calibrated_score
        
        return 0.5

    def suggest_optimization(self, mood: str, style: str) -> dict:
        """
        根据历史数据提供优化建议
        """
        pattern = self.get_pattern(mood, style)
        
        suggestions = {
            "mood": mood,
            "style": style,
            "recommendations": [],
            "warnings": [],
            "improvements": []
        }
        
        if pattern:
            if pattern.usage_count >= 5:
                suggestions["recommendations"].append({
                    "type": "proven_pattern",
                    "message": f"该模式已成功使用 {pattern.usage_count} 次",
                    "confidence": pattern.confidence_score
                })
            
            if pattern.confidence_score > 0.7:
                suggestions["recommendations"].append({
                    "type": "high_confidence",
                    "message": "置信度较高，可以直接应用该模式",
                    "confidence": pattern.confidence_score
                })
            elif pattern.confidence_score < 0.4:
                suggestions["warnings"].append({
                    "type": "low_confidence",
                    "message": "置信度较低，建议调整参数",
                    "confidence": pattern.confidence_score
                })
            
            if len(pattern.effect_config) < 3:
                suggestions["improvements"].append({
                    "type": "add_effects",
                    "message": "考虑添加更多效果增强视觉表现力"
                })
            
            if len(pattern.keyframe_config) < 5:
                suggestions["improvements"].append({
                    "type": "add_keyframes",
                    "message": "考虑添加更多关键帧动画"
                })
        else:
            suggestions["warnings"].append({
                "type": "no_pattern",
                "message": "未找到该模式的历史数据，将使用默认配置"
            })
        
        return suggestions

    def get_performance_summary(self) -> dict:
        """
        获取整体性能摘要
        """
        records = self._load_all_records()
        
        total_records = len(records)
        successful_records = sum(1 for r in records if r.success)
        failure_records = total_records - successful_records
        
        avg_duration = sum(r.duration for r in records) / total_records if total_records > 0 else 0
        
        mood_stats = {}
        style_stats = {}
        
        for record in records:
            mood = record.understanding_result.get("mood", "unknown")
            style = record.understanding_result.get("style", "default")
            
            if mood not in mood_stats:
                mood_stats[mood] = {"total": 0, "success": 0}
            mood_stats[mood]["total"] += 1
            if record.success:
                mood_stats[mood]["success"] += 1
            
            if style not in style_stats:
                style_stats[style] = {"total": 0, "success": 0}
            style_stats[style]["total"] += 1
            if record.success:
                style_stats[style]["success"] += 1
        
        for mood in mood_stats:
            mood_stats[mood]["success_rate"] = mood_stats[mood]["success"] / mood_stats[mood]["total"]
        
        for style in style_stats:
            style_stats[style]["success_rate"] = style_stats[style]["success"] / style_stats[style]["total"]
        
        return {
            "total_executions": total_records,
            "successful_executions": successful_records,
            "failure_executions": failure_records,
            "overall_success_rate": successful_records / total_records if total_records > 0 else 0,
            "average_duration": avg_duration,
            "mood_stats": mood_stats,
            "style_stats": style_stats,
            "pattern_count": len(self.patterns),
            "confidence_entries": len(self.confidence_store)
        }

    def _load_all_records(self) -> list[ExecutionRecord]:
        records = []
        for filename in os.listdir(self.records_dir):
            if filename.endswith(".json") and not filename.startswith("."):
                filepath = os.path.join(self.records_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        records.append(ExecutionRecord(**data))
                except:
                    pass
        return records

    def create_ab_test(self, test_name: str, variant_a: dict, variant_b: dict) -> str:
        """
        创建A/B测试
        """
        test_id = self._generate_id()
        
        test_data = {
            "test_id": test_id,
            "test_name": test_name,
            "created_at": datetime.now().isoformat(),
            "variant_a": variant_a,
            "variant_b": variant_b,
            "results_a": [],
            "results_b": [],
            "status": "running"
        }
        
        test_path = os.path.join(self.ab_test_dir, f"{test_id}_{test_name}.json")
        with open(test_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        
        return test_id

    def record_ab_test_result(self, test_id: str, variant: str, success: bool, metrics: dict):
        """
        记录A/B测试结果
        """
        for filename in os.listdir(self.ab_test_dir):
            if test_id in filename:
                filepath = os.path.join(self.ab_test_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        test_data = json.load(f)
                    
                    result_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "success": success,
                        "metrics": metrics
                    }
                    
                    if variant == "a":
                        test_data["results_a"].append(result_entry)
                    elif variant == "b":
                        test_data["results_b"].append(result_entry)
                    
                    count_a = len(test_data["results_a"])
                    count_b = len(test_data["results_b"])
                    
                    if count_a >= 10 and count_b >= 10:
                        test_data["status"] = "completed"
                        test_data["conclusion"] = self._analyze_ab_test(test_data)
                    
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(test_data, f, ensure_ascii=False, indent=2)
                    
                    return True
                except:
                    pass
        
        return False

    def _analyze_ab_test(self, test_data: dict) -> dict:
        results_a = test_data["results_a"]
        results_b = test_data["results_b"]
        
        success_a = sum(1 for r in results_a if r["success"])
        success_b = sum(1 for r in results_b if r["success"])
        
        rate_a = success_a / len(results_a)
        rate_b = success_b / len(results_b)
        
        conclusion = {
            "variant_a_success_rate": rate_a,
            "variant_b_success_rate": rate_b,
            "winner": "a" if rate_a > rate_b else "b" if rate_b > rate_a else "tie",
            "improvement": ((rate_b - rate_a) / rate_a * 100) if rate_a > 0 else 0
        }
        
        return conclusion

    def save_learning_summary(self) -> str:
        """
        保存学习摘要报告
        """
        summary = {
            "generated_at": datetime.now().isoformat(),
            "performance": self.get_performance_summary(),
            "patterns": {k: self._dataclass_to_dict(v) for k, v in self.patterns.items()},
            "confidence_entries": {k: self._dataclass_to_dict(v) for k, v in self.confidence_store.items()}
        }
        
        summary_path = os.path.join(self.data_dir, f"learning_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        return summary_path


def main():
    manager = FeedbackManager()
    
    print("="*60)
    print("📊 反馈管理器 - 学习循环系统")
    print("="*60)
    
    summary = manager.get_performance_summary()
    
    print("\n📈 总体统计")
    print(f"  总执行次数: {summary['total_executions']}")
    print(f"  成功次数: {summary['successful_executions']}")
    print(f"  失败次数: {summary['failure_executions']}")
    print(f"  成功率: {summary['overall_success_rate']:.2%}")
    print(f"  平均耗时: {summary['average_duration']:.2f}秒")
    
    print("\n🎯 情绪统计")
    for mood, stats in summary['mood_stats'].items():
        print(f"  {mood}: {stats['success']}/{stats['total']} ({stats['success_rate']:.2%})")
    
    print("\n🎨 风格统计")
    for style, stats in summary['style_stats'].items():
        print(f"  {style}: {stats['success']}/{stats['total']} ({stats['success_rate']:.2%})")
    
    print("\n📚 模式库")
    print(f"  已保存模式数: {summary['pattern_count']}")
    print(f"  置信度记录数: {summary['confidence_entries']}")
    
    summary_path = manager.save_learning_summary()
    print(f"\n📄 学习摘要已保存: {summary_path}")


if __name__ == "__main__":
    main()