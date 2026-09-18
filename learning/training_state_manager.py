import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

STATE_DIR = r"D:\AE-Work\训练归档\状态存储"
SESSIONS_DIR = os.path.join(STATE_DIR, "sessions")
MODELS_DIR = os.path.join(STATE_DIR, "models")
METRICS_DIR = os.path.join(STATE_DIR, "metrics")
CHECKPOINTS_DIR = os.path.join(STATE_DIR, "checkpoints")

class TrainingStateManager:
    def __init__(self, project_name: str = "AE-Knowledge-Vault"):
        self.project_name = project_name
        self.current_session_id = self._generate_session_id()
        self.state: dict[str, Any] = {
            "project_name": project_name,
            "session_id": self.current_session_id,
            "creation_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "training_progress": {},
            "model_states": {},
            "learning_metrics": {},
            "execution_history": [],
            "user_preferences": {},
            "system_config": {},
            "cache": {},
            "templates": [],
            "confidence_adjustments": [],
            "default_values": {}
        }
        
        self._ensure_directories()
        self._load_last_state()
    
    def _ensure_directories(self):
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        os.makedirs(MODELS_DIR, exist_ok=True)
        os.makedirs(METRICS_DIR, exist_ok=True)
        os.makedirs(CHECKPOINTS_DIR, exist_ok=True)
    
    def _generate_session_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_str = hashlib.md5(f"{timestamp}_{os.getpid()}".encode()).hexdigest()[:8]
        return f"ses_{timestamp}_{hash_str}"
    
    def _get_state_file_path(self) -> str:
        return os.path.join(SESSIONS_DIR, f"{self.current_session_id}.json")
    
    def _get_last_state_file(self) -> str | None:
        files = sorted(
            [f for f in os.listdir(SESSIONS_DIR) if f.endswith(".json")],
            reverse=True
        )
        if files:
            return os.path.join(SESSIONS_DIR, files[0])
        return None
    
    def _load_last_state(self):
        last_file = self._get_last_state_file()
        if last_file:
            try:
                with open(last_file, "r", encoding="utf-8") as f:
                    saved_state = json.load(f)
                self._merge_state(saved_state)
                self.current_session_id = saved_state.get("session_id", self.current_session_id)
                print(f"📦 已加载上次会话状态: {self.current_session_id}")
            except Exception as e:
                print(f"⚠️ 加载上次状态失败: {e}")
    
    def _merge_state(self, saved_state: dict):
        for key in ["training_progress", "model_states", "learning_metrics", 
                    "execution_history", "user_preferences", "system_config",
                    "cache", "templates", "confidence_adjustments", "default_values"]:
            if key in saved_state:
                if isinstance(saved_state[key], dict):
                    self.state[key].update(saved_state[key])
                elif isinstance(saved_state[key], list):
                    self.state[key].extend(saved_state[key])
    
    def save_state(self, description: str = "") -> str:
        self.state["last_modified"] = datetime.now().isoformat()
        self.state["description"] = description
        
        file_path = self._get_state_file_path()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
        
        latest_path = os.path.join(SESSIONS_DIR, "latest.json")
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
        
        print(f"💾 状态已保存: {file_path}")
        return file_path
    
    def save_checkpoint(self, checkpoint_name: str, extra_data: dict = None) -> str:
        checkpoint = {
            "checkpoint_name": checkpoint_name,
            "session_id": self.current_session_id,
            "timestamp": datetime.now().isoformat(),
            "state": self.state,
            "extra_data": extra_data or {}
        }
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_path = os.path.join(CHECKPOINTS_DIR, f"{checkpoint_name}_{timestamp}.json")
        
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        
        print(f"📌 检查点已保存: {checkpoint_path}")
        return checkpoint_path
    
    def load_checkpoint(self, checkpoint_path: str) -> bool:
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)
            
            self.state = checkpoint.get("state", self.state)
            self.current_session_id = checkpoint.get("session_id", self.current_session_id)
            print(f"🔄 已从检查点恢复: {checkpoint_path}")
            return True
        except Exception as e:
            print(f"⚠️ 加载检查点失败: {e}")
            return False
    
    def record_execution(self, execution_data: dict):
        execution_record = {
            "id": execution_data.get("id", f"exec_{datetime.now().timestamp()}"),
            "timestamp": datetime.now().isoformat(),
            **execution_data
        }
        self.state["execution_history"].append(execution_record)
        if len(self.state["execution_history"]) > 1000:
            self.state["execution_history"] = self.state["execution_history"][-500:]
    
    def update_training_progress(self, phase: str, progress: float, status: str = "running"):
        self.state["training_progress"][phase] = {
            "progress": progress,
            "status": status,
            "updated_at": datetime.now().isoformat()
        }
    
    def update_model_state(self, model_name: str, model_data: dict):
        self.state["model_states"][model_name] = {
            "data": model_data,
            "updated_at": datetime.now().isoformat()
        }
    
    def update_metrics(self, metrics: dict):
        for name, value in metrics.items():
            if isinstance(value, dict):
                self.state["learning_metrics"][name] = value
            else:
                self.state["learning_metrics"][name] = {
                    "value": value,
                    "updated_at": datetime.now().isoformat()
                }
    
    def add_template(self, template: dict):
        self.state["templates"].append(template)
    
    def add_confidence_adjustment(self, adjustment: dict):
        self.state["confidence_adjustments"].append(adjustment)
    
    def update_default_value(self, effect_match_name: str, param_name: str, value: Any):
        key = f"{effect_match_name}.{param_name}"
        self.state["default_values"][key] = {
            "value": value,
            "updated_at": datetime.now().isoformat()
        }
    
    def set_user_preference(self, key: str, value: Any):
        self.state["user_preferences"][key] = value
    
    def get_user_preference(self, key: str, default: Any = None) -> Any:
        return self.state["user_preferences"].get(key, default)
    
    def set_system_config(self, key: str, value: Any):
        self.state["system_config"][key] = value
    
    def get_system_config(self, key: str, default: Any = None) -> Any:
        return self.state["system_config"].get(key, default)
    
    def cache_result(self, cache_key: str, result: Any, ttl_seconds: int = 3600):
        self.state["cache"][cache_key] = {
            "result": result,
            "cached_at": datetime.now().isoformat(),
            "ttl_seconds": ttl_seconds
        }
    
    def get_cached_result(self, cache_key: str) -> Any | None:
        entry = self.state["cache"].get(cache_key)
        if not entry:
            return None
        
        cached_at = datetime.fromisoformat(entry["cached_at"])
        age = (datetime.now() - cached_at).total_seconds()
        if age > entry.get("ttl_seconds", 3600):
            del self.state["cache"][cache_key]
            return None
        
        return entry["result"]
    
    def get_state_summary(self) -> dict:
        return {
            "project_name": self.state["project_name"],
            "session_id": self.state["session_id"],
            "creation_time": self.state["creation_time"],
            "last_modified": self.state["last_modified"],
            "training_phases": len(self.state["training_progress"]),
            "models_count": len(self.state["model_states"]),
            "executions_count": len(self.state["execution_history"]),
            "templates_count": len(self.state["templates"]),
            "confidence_adjustments_count": len(self.state["confidence_adjustments"])
        }
    
    def clear_cache(self):
        self.state["cache"] = {}
        print("🧹 缓存已清除")
    
    def reset_state(self):
        self.current_session_id = self._generate_session_id()
        self.state = {
            "project_name": self.project_name,
            "session_id": self.current_session_id,
            "creation_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "training_progress": {},
            "model_states": {},
            "learning_metrics": {},
            "execution_history": [],
            "user_preferences": {},
            "system_config": {},
            "cache": {},
            "templates": [],
            "confidence_adjustments": [],
            "default_values": {}
        }
        print("🔄 状态已重置")
    
    def get_all_sessions(self, limit: int = 10) -> list[str]:
        files = sorted(
            [f for f in os.listdir(SESSIONS_DIR) if f.startswith("ses_") and f.endswith(".json")],
            reverse=True
        )[:limit]
        return [os.path.join(SESSIONS_DIR, f) for f in files]
    
    def load_session(self, session_path: str) -> bool:
        try:
            with open(session_path, "r", encoding="utf-8") as f:
                self.state = json.load(f)
            self.current_session_id = self.state.get("session_id", self._generate_session_id())
            print(f"🔄 已加载会话: {self.current_session_id}")
            return True
        except Exception as e:
            print(f"⚠️ 加载会话失败: {e}")
            return False

    def export_state(self, export_path: str) -> str:
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
        print(f"📤 状态已导出到: {export_path}")
        return export_path
    
    def import_state(self, import_path: str) -> bool:
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                imported_state = json.load(f)
            self._merge_state(imported_state)
            self.state["last_modified"] = datetime.now().isoformat()
            print(f"📥 已从 {import_path} 导入状态")
            return True
        except Exception as e:
            print(f"⚠️ 导入状态失败: {e}")
            return False

if __name__ == "__main__":
    manager = TrainingStateManager()
    
    print("\n📊 当前状态摘要:")
    summary = manager.get_state_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    manager.update_training_progress("Phase1", 0.8, "completed")
    manager.update_metrics({"success_rate": 0.95, "avg_deviation": 0.05})
    manager.add_template({
        "id": "test_template",
        "effect_match_name": "ADBE Gaussian Blur 2",
        "parameters": {"Blurriness": 10}
    })
    manager.record_execution({
        "id": "test_exec",
        "user_input": "添加模糊效果",
        "success": True,
        "effect_name": "高斯模糊"
    })
    
    save_path = manager.save_state("测试状态保存")
    print(f"\n💾 状态已保存到: {save_path}")
    
    new_manager = TrainingStateManager()
    print("\n🔄 重新加载后状态摘要:")
    summary2 = new_manager.get_state_summary()
    for key, value in summary2.items():
        print(f"  {key}: {value}")