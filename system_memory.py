import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any
from training_state_manager import TrainingStateManager

MEMORY_DIR = r"D:\AE-Work\训练归档\记忆存储"
MEMORY_FILE = os.path.join(MEMORY_DIR, "system_memory.json")
BACKUP_DIR = os.path.join(MEMORY_DIR, "backups")

class SystemMemory:
    def __init__(self):
        self.memory: Dict[str, Any] = {}
        self.state_manager = TrainingStateManager()
        self._ensure_directories()
        self._load_memory()
    
    def _ensure_directories(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)
    
    def _load_memory(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
                print(f"🧠 已加载系统记忆: {len(self.memory)} 条记录")
            except Exception as e:
                print(f"⚠️ 加载系统记忆失败: {e}")
    
    def _save_memory(self):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)
        
        self._create_backup()
        print(f"💾 系统记忆已保存")
    
    def _create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"memory_backup_{timestamp}.json")
        shutil.copy2(MEMORY_FILE, backup_path)
        
        backups = sorted(os.listdir(BACKUP_DIR), reverse=True)
        if len(backups) > 10:
            for old_backup in backups[10:]:
                os.remove(os.path.join(BACKUP_DIR, old_backup))
    
    def remember(self, key: str, value: Any, category: str = "general", description: str = ""):
        self.memory[key] = {
            "value": value,
            "category": category,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "access_count": 0
        }
        self._save_memory()
    
    def recall(self, key: str) -> Optional[Any]:
        entry = self.memory.get(key)
        if entry:
            entry["last_accessed"] = datetime.now().isoformat()
            entry["access_count"] += 1
            self._save_memory()
            return entry["value"]
        return None
    
    def forget(self, key: str):
        if key in self.memory:
            del self.memory[key]
            self._save_memory()
            print(f"🗑️ 已遗忘: {key}")
    
    def search(self, query: str, category: str = None) -> List[Dict]:
        results = []
        for key, entry in self.memory.items():
            if query.lower() in key.lower() or query.lower() in entry.get("description", "").lower():
                if category and entry["category"] != category:
                    continue
                results.append({
                    "key": key,
                    "category": entry["category"],
                    "description": entry["description"],
                    "value": entry["value"],
                    "access_count": entry["access_count"]
                })
        return sorted(results, key=lambda x: x["access_count"], reverse=True)
    
    def get_category(self, category: str) -> List[Dict]:
        return [
            {"key": key, **entry}
            for key, entry in self.memory.items()
            if entry["category"] == category
        ]
    
    def save_training_result(self, training_id: str, result: Dict):
        key = f"training_{training_id}"
        self.remember(
            key,
            result,
            category="training",
            description=f"训练结果: {result.get('title', '未知')}"
        )
    
    def load_training_result(self, training_id: str) -> Optional[Dict]:
        return self.recall(f"training_{training_id}")
    
    def save_project_state(self, project_name: str, state: Dict):
        key = f"project_{project_name}"
        self.remember(
            key,
            state,
            category="project",
            description=f"项目状态: {project_name}"
        )
    
    def load_project_state(self, project_name: str) -> Optional[Dict]:
        return self.recall(f"project_{project_name}")
    
    def save_user_preferences(self, preferences: Dict):
        self.remember(
            "user_preferences",
            preferences,
            category="system",
            description="用户偏好设置"
        )
    
    def load_user_preferences(self) -> Dict:
        return self.recall("user_preferences") or {}
    
    def save_workflow_template(self, template_name: str, template: Dict):
        key = f"workflow_{template_name}"
        self.remember(
            key,
            template,
            category="workflow",
            description=f"工作流模板: {template_name}"
        )
    
    def load_workflow_template(self, template_name: str) -> Optional[Dict]:
        return self.recall(f"workflow_{template_name}")
    
    def get_all_workflow_templates(self) -> List[Dict]:
        return self.get_category("workflow")
    
    def save_experiment_report(self, experiment_id: str, report: Dict):
        key = f"experiment_{experiment_id}"
        self.remember(
            key,
            report,
            category="experiment",
            description=f"实验报告: {report.get('title', '未知')}"
        )
    
    def load_experiment_report(self, experiment_id: str) -> Optional[Dict]:
        return self.recall(f"experiment_{experiment_id}")
    
    def get_recent_experiments(self, count: int = 10) -> List[Dict]:
        experiments = self.get_category("experiment")
        return sorted(experiments, key=lambda x: x["created_at"], reverse=True)[:count]
    
    def save_lesson_learned(self, lesson: str, context: Dict = None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        key = f"lesson_{timestamp}"
        self.remember(
            key,
            {"lesson": lesson, "context": context or {}},
            category="lesson",
            description=lesson[:50]
        )
    
    def get_all_lessons(self) -> List[Dict]:
        return sorted(
            self.get_category("lesson"),
            key=lambda x: x["created_at"],
            reverse=True
        )
    
    def save_audio_analysis(self, audio_path: str, analysis: Dict):
        import hashlib
        file_hash = hashlib.md5(audio_path.encode()).hexdigest()[:16]
        key = f"audio_analysis_{file_hash}"
        self.remember(
            key,
            {"audio_path": audio_path, **analysis},
            category="audio_analysis",
            description=f"音频分析: {os.path.basename(audio_path)}"
        )
    
    def load_audio_analysis(self, audio_path: str) -> Optional[Dict]:
        import hashlib
        file_hash = hashlib.md5(audio_path.encode()).hexdigest()[:16]
        return self.recall(f"audio_analysis_{file_hash}")
    
    def save_video_match(self, bgm_path: str, matches: List[Dict]):
        import hashlib
        file_hash = hashlib.md5(bgm_path.encode()).hexdigest()[:16]
        key = f"video_match_{file_hash}"
        self.remember(
            key,
            {"bgm_path": bgm_path, "matches": matches},
            category="video_match",
            description=f"视频匹配结果: {os.path.basename(bgm_path)}"
        )
    
    def load_video_match(self, bgm_path: str) -> Optional[Dict]:
        import hashlib
        file_hash = hashlib.md5(bgm_path.encode()).hexdigest()[:16]
        return self.recall(f"video_match_{file_hash}")
    
    def get_memory_summary(self) -> Dict:
        categories = {}
        for entry in self.memory.values():
            cat = entry["category"]
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            "total_entries": len(self.memory),
            "categories": categories,
            "last_modified": datetime.now().isoformat(),
            "backup_count": len(os.listdir(BACKUP_DIR))
        }
    
    def export_memory(self, export_path: str) -> str:
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)
        print(f"📤 系统记忆已导出到: {export_path}")
        return export_path
    
    def import_memory(self, import_path: str) -> bool:
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                imported_memory = json.load(f)
            self.memory.update(imported_memory)
            self._save_memory()
            print(f"📥 已从 {import_path} 导入记忆")
            return True
        except Exception as e:
            print(f"⚠️ 导入记忆失败: {e}")
            return False
    
    def clear_category(self, category: str):
        keys_to_remove = [key for key, entry in self.memory.items() if entry["category"] == category]
        for key in keys_to_remove:
            del self.memory[key]
        self._save_memory()
        print(f"🧹 已清除类别 '{category}' 的所有记录")
    
    def clear_all(self):
        self.memory = {}
        self._save_memory()
        print("🗑️ 所有记忆已清除")

if __name__ == "__main__":
    memory = SystemMemory()
    
    print("\n📊 记忆摘要:")
    summary = memory.get_memory_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    memory.save_lesson_learned("executeAtomScript是最可靠的AE控制方式", {
        "source": "2026-07-06 BGM实战演练",
        "context": "importFootage MCP工具超时，改用executeAtomScript成功"
    })
    
    memory.save_audio_analysis("D:/AE-Work/音频素材库/BGM/test.mp3", {
        "duration": 55.52,
        "bpm": 95,
        "mood": "epic",
        "genre": "ambient"
    })
    
    memory.save_workflow_template("抖音BGM下载", {
        "steps": ["解析短链接", "获取Cookie", "下载视频", "提取音频", "导入AE"],
        "tools": ["douyin_downloader_pro", "ffmpeg-toolkit", "ae-importer"]
    })
    
    print("\n📚 学习到的经验:")
    lessons = memory.get_all_lessons()
    for lesson in lessons:
        print(f"  • {lesson['value']['lesson']}")
    
    print("\n📋 工作流模板:")
    templates = memory.get_all_workflow_templates()
    for template in templates:
        print(f"  • {template['key'].replace('workflow_', '')}")
    
    print("\n✅ 系统记忆测试完成")