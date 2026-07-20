import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# D2 修复：使用 ConfigManager 替代硬编码路径
_PROJECT_ROOT = Path(__file__).resolve().parent

try:
    from config.config_manager import ConfigManager as _ConfigManager
    _cfg = _ConfigManager()
    LOG_DIR = _cfg.get_directory("logs") or str(_PROJECT_ROOT / "data" / "logs")
    ARCHIVE_DIR = _cfg.get_directory("training_archive") or str(_PROJECT_ROOT / "data" / "training_archive")
except Exception:
    # ConfigManager 不可用时回退到默认路径
    LOG_DIR = os.path.join(str(_PROJECT_ROOT), "data", "logs")
    ARCHIVE_DIR = os.path.join(str(_PROJECT_ROOT), "data", "training_archive")

try:
    from training_state_manager import TrainingStateManager
    from system_memory import SystemMemory
    STATE_MANAGER_AVAILABLE = True
except ImportError:
    STATE_MANAGER_AVAILABLE = False


class TrainingLogger:
    def __init__(self, task_name: str, use_state_manager: bool = True):
        self.task_name = task_name
        self.start_time = datetime.now()
        self.log_entries: List[Dict] = []
        self.metrics: Dict = {}
        self.artifacts: List[str] = []
        
        self.state_manager = None
        self.system_memory = None
        
        if use_state_manager and STATE_MANAGER_AVAILABLE:
            self.state_manager = TrainingStateManager()
            self.system_memory = SystemMemory()
            self.system_memory.remember(f"task_{task_name}_start", {
                "task_name": task_name,
                "start_time": self.start_time.isoformat()
            }, category="task")
        
        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(ARCHIVE_DIR, exist_ok=True)

    def log(self, level: str, message: str, **kwargs):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }
        self.log_entries.append(entry)
        print(f"[{level.upper()}] {message}")

    def info(self, message: str, **kwargs):
        self.log("info", message, **kwargs)

    def warning(self, message: str, **kwargs):
        self.log("warning", message, **kwargs)

    def error(self, message: str, **kwargs):
        self.log("error", message, **kwargs)

    def success(self, message: str, **kwargs):
        self.log("success", message, **kwargs)

    def add_metric(self, name: str, value, unit: str = ""):
        self.metrics[name] = {"value": value, "unit": unit}

    def add_artifact(self, path: str, description: str = ""):
        self.artifacts.append({"path": path, "description": description})

    def save_report(self, title: str, summary: str = "") -> str:
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        report = {
            "title": title,
            "task_name": self.task_name,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "summary": summary,
            "logs": self.log_entries,
            "metrics": self.metrics,
            "artifacts": self.artifacts
        }
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"{timestamp}_{self.task_name}.json"
        report_path = os.path.join(LOG_DIR, report_filename)
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        archive_path = os.path.join(ARCHIVE_DIR, report_filename)
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        if self.system_memory:
            self.system_memory.save_experiment_report(report_filename, report)
        
        if self.state_manager:
            self.state_manager.record_execution({
                "task_name": self.task_name,
                "title": title,
                "status": "completed",
                "duration": duration,
                "metrics": self.metrics
            })
            self.state_manager.save_state(f"任务完成: {title}")
        
        self.info(f"报告已保存: {report_path}")
        return report_path

    def generate_markdown_report(self, title: str) -> str:
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        md = f"# {title}\n\n"
        md += f"**任务名称**: {self.task_name}\n\n"
        md += f"**开始时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += f"**结束时间**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += f"**耗时**: {duration:.2f} 秒\n\n"
        
        md += "## 📊 指标\n\n"
        if self.metrics:
            for name, metric in self.metrics.items():
                md += f"- **{name}**: {metric['value']} {metric['unit']}\n"
        else:
            md += "无指标记录\n"
        
        md += "\n## 📁 产出物\n\n"
        if self.artifacts:
            for artifact in self.artifacts:
                clean_path = artifact['path'].replace('\\', '/')
                md += f"- [{artifact['description']}](file:///{clean_path})\n"
        else:
            md += "无产出物\n"
        
        md += "\n## 📝 日志\n\n"
        for entry in self.log_entries:
            timestamp = entry["timestamp"].split("T")[1].split(".")[0]
            level = entry["level"].upper()
            message = entry["message"]
            md += f"**[{timestamp}] {level}**: {message}\n\n"
        
        return md

    def save_markdown_report(self, title: str) -> str:
        md_content = self.generate_markdown_report(title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"{timestamp}_{self.task_name}.md"
        report_path = os.path.join(LOG_DIR, report_filename)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        self.info(f"Markdown报告已保存: {report_path}")
        return report_path


class VideoGenerationLogger(TrainingLogger):
    def __init__(self, music_path: str, clip_paths: List[str], output_path: str):
        super().__init__(task_name="video_generation")
        self.music_path = music_path
        self.clip_paths = clip_paths
        self.output_path = output_path
        
        self.info("视频生成任务初始化", 
                  music=os.path.basename(music_path),
                  clips=[os.path.basename(c) for c in clip_paths],
                  output=output_path)

    def log_stage(self, stage: str, status: str, **kwargs):
        self.info(f"阶段 [{stage}] {status}", stage=stage, status=status, **kwargs)

    def log_effect_apply(self, effect_name: str, layer_name: str, params: Dict):
        self.info(f"应用效果: {effect_name} → {layer_name}", 
                  effect=effect_name, layer=layer_name, params=params)

    def log_keyframe(self, property_name: str, time_sec: float, value):
        self.info(f"设置关键帧: {property_name} @ {time_sec:.2f}s = {value}",
                  property=property_name, time=time_sec, value=value)

    def complete(self, success: bool, error_message: str = ""):
        if success:
            self.success(f"视频生成完成: {self.output_path}")
            self.add_artifact(self.output_path, "生成的视频成品")
        else:
            self.error(f"视频生成失败: {error_message}")
            self.add_metric("success", False)
        return self.save_report("视频生成实验报告")


class TrainingSessionLogger(TrainingLogger):
    def __init__(self, session_name: str, level: str = "入门级"):
        super().__init__(task_name="training_session")
        self.session_name = session_name
        self.level = level
        self.exercises_completed = 0
        self.exercises_failed = 0
        
        self.info(f"训练会话开始: {session_name} (级别: {level})")

    def log_exercise(self, name: str, success: bool, duration: float = 0, notes: str = ""):
        if success:
            self.exercises_completed += 1
            self.success(f"练习完成: {name}", duration=duration)
        else:
            self.exercises_failed += 1
            self.error(f"练习失败: {name}", notes=notes)

    def complete(self):
        total = self.exercises_completed + self.exercises_failed
        success_rate = (self.exercises_completed / total * 100) if total > 0 else 0
        
        self.add_metric("completed", self.exercises_completed)
        self.add_metric("failed", self.exercises_failed)
        self.add_metric("success_rate", f"{success_rate:.1f}", "%")
        
        self.info(f"训练会话完成: {self.exercises_completed}/{total} 通过")
        
        return self.save_report(f"训练报告 - {self.session_name}")


class PipelineLogger(TrainingLogger):
    """AE Agent Pipeline 专用日志器 (D2 新增)

    自动记录 5 层管线执行过程，生成结构化报告。
    用法：
        logger = PipelineLogger("bgm_match_task")
        logger.log_perception(audio_path="test.mp3", features={...})
        logger.log_understanding(intent="bgm_match", confidence=0.9)
        logger.log_planning(steps=[...])
        logger.log_execution(completed=3, total=5)
        logger.log_feedback(rating=4.2)
        logger.save_pipeline_report()
    """

    def __init__(self, task_name: str, pipeline_config: Optional[Dict] = None):
        super().__init__(task_name=task_name)
        self.pipeline_config = pipeline_config or {}
        self.layer_results: Dict[str, Dict] = {}

    def log_perception(self, **kwargs):
        self.layer_results["perception"] = kwargs
        self.info("感知层完成", **{k: str(v)[:100] for k, v in kwargs.items()})

    def log_understanding(self, **kwargs):
        self.layer_results["understanding"] = kwargs
        confidence = kwargs.get("confidence", 0)
        intent = kwargs.get("intent", "unknown")
        self.info(f"理解层完成: intent={intent}, confidence={confidence}")

    def log_planning(self, **kwargs):
        self.layer_results["planning"] = kwargs
        steps = kwargs.get("steps", [])
        self.info(f"规划层完成: {len(steps)} 个步骤")

    def log_execution(self, **kwargs):
        self.layer_results["execution"] = kwargs
        completed = kwargs.get("steps_completed", 0)
        total = kwargs.get("total_steps", 0)
        self.info(f"执行层完成: {completed}/{total}")

    def log_feedback(self, **kwargs):
        self.layer_results["feedback"] = kwargs
        rating = kwargs.get("rating", 0)
        self.info(f"反馈层评分: {rating}")

    def save_pipeline_report(self, title: str = "") -> str:
        """生成管线执行报告"""
        if not title:
            title = f"Pipeline 执行报告 - {self.task_name}"

        # 添加管线特有指标
        for layer_name, layer_data in self.layer_results.items():
            for key, value in layer_data.items():
                if isinstance(value, (int, float, str, bool)):
                    self.add_metric(f"{layer_name}.{key}", value)

        return self.save_report(title)


def get_latest_reports(count: int = 5) -> List[str]:
    if not os.path.exists(LOG_DIR):
        return []
    reports = sorted(
        [f for f in os.listdir(LOG_DIR) if f.endswith(".json")],
        reverse=True
    )[:count]
    return reports


def load_report(report_path: str) -> Dict:
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    logger = TrainingLogger("测试日志系统")
    logger.info("系统启动")
    logger.warning("测试警告")
    logger.add_metric("test_value", 42, "units")
    logger.add_artifact("test.txt", "测试文件")
    logger.success("测试完成")
    
    report_path = logger.save_report("测试报告")
    md_path = logger.save_markdown_report("测试报告")
    
    print(f"\nJSON报告: {report_path}")
    print(f"MD报告: {md_path}")