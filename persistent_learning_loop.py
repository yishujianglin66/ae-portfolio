"""
Persistent Learning Loop
Phase 5 - 持久化学习循环

在 learning_loop.py 的基础上增加：
  1. JSON文件持久化存储
  2. 自动保存/加载机制（每次操作后自动保存）
  3. 检查点机制（定期保存检查点）
  4. 跨IDE共享（文件系统存储）

对应架构设计文档 7.5 节 LearningLoop + 持久化扩展
"""

import os
import json
import time
import random
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

from learning_loop import (
    LearningLoop,
    CaseStore,
    DefaultValueStore,
    ParameterTemplate,
    ExpectedParameters,
    ExecutionResult as LRExecutionResult,
    VerificationResult as LRVerificationResult,
    UserFeedback,
    ExecutionRecord,
    ConfidenceAdjustment,
)


def _get_state_dir() -> str:
    """获取持久化状态目录（跨平台）"""
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("HOME", os.path.expanduser("~"))
    return os.path.join(base, "AE-Knowledge-Vault", "learning-state")


STATE_DIR = _get_state_dir()
CASE_STORE_FILE = os.path.join(STATE_DIR, "case-store.json")
DEFAULT_VALUE_STORE_FILE = os.path.join(STATE_DIR, "default-value-store.json")
EXECUTION_RECORDS_FILE = os.path.join(STATE_DIR, "execution-records.json")
CONFIDENCE_ADJUSTMENTS_FILE = os.path.join(STATE_DIR, "confidence-adjustments.json")
CHECKPOINTS_DIR = os.path.join(STATE_DIR, "checkpoints")

MAX_RECORDS = 10000
CHECKPOINT_INTERVAL_SEC = 3600


class FileSystemStorage:
    """文件系统持久化存储"""

    def load(self, file_path: str, default_value: Any) -> Any:
        try:
            if not os.path.exists(file_path):
                return default_value
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_value

    def save(self, file_path: str, data: Any) -> None:
        dir_path = os.path.dirname(file_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class PersistentCaseStore(CaseStore):
    """持久化参数模板存储"""

    def __init__(self, storage: FileSystemStorage):
        super().__init__()
        self._storage = storage
        self._templates: Dict[str, ParameterTemplate] = {}
        self._load()

    def _load(self) -> None:
        saved = self._storage.load(CASE_STORE_FILE, [])
        for t_data in saved:
            try:
                template = ParameterTemplate(
                    id=t_data.get("id", f"tpl_{int(time.time()*1000)}_{random.randint(0,9999)}"),
                    source=t_data.get("source", "loaded"),
                    effect_match_name=t_data.get("effectMatchName", ""),
                    effect_name=t_data.get("effectName", ""),
                    parameters=t_data.get("parameters", {}),
                    user_rating=t_data.get("userRating", "neutral"),
                    usage_count=t_data.get("usageCount", 0),
                    last_used=t_data.get("lastUsed", ""),
                    source_input=t_data.get("sourceInput", ""),
                )
                self._templates[template.id] = template
            except Exception:
                continue

    def _save(self) -> None:
        data = []
        for t in self._templates.values():
            data.append({
                "id": t.id,
                "source": t.source,
                "effectMatchName": t.effect_match_name,
                "effectName": t.effect_name,
                "parameters": t.parameters,
                "userRating": t.user_rating,
                "usageCount": t.usage_count,
                "lastUsed": t.last_used,
                "sourceInput": t.source_input,
            })
        self._storage.save(CASE_STORE_FILE, data)

    def add_template(self, template: ParameterTemplate) -> None:
        self._templates[template.id] = template
        self._save()

    def find_templates(self, effect_match_name: str) -> List[ParameterTemplate]:
        return sorted(
            [t for t in self._templates.values()
             if t.effect_match_name == effect_match_name],
            key=lambda t: t.usage_count,
            reverse=True,
        )

    def increment_usage(self, template_id: str) -> None:
        t = self._templates.get(template_id)
        if t:
            t.usage_count += 1
            t.last_used = datetime.now().isoformat()
            self._save()

    def get_all_templates(self) -> List[ParameterTemplate]:
        return list(self._templates.values())


class PersistentDefaultValueStore(DefaultValueStore):
    """持久化默认值存储"""

    def __init__(self, storage: FileSystemStorage):
        super().__init__()
        self._storage = storage
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._load()

    def _load(self) -> None:
        saved = self._storage.load(DEFAULT_VALUE_STORE_FILE, {})
        for key, entry in saved.items():
            if isinstance(entry, dict):
                self._store[key] = (entry.get("value"), entry.get("weight", 1.0))
            elif isinstance(entry, list) and len(entry) >= 2:
                self._store[key] = (entry[0], entry[1])

    def _save(self) -> None:
        data = {}
        for key, (value, weight) in self._store.items():
            data[key] = {"value": value, "weight": weight}
        self._storage.save(DEFAULT_VALUE_STORE_FILE, data)

    def get(self, effect_match_name: str, param_name: str) -> Any:
        key = f"{effect_match_name}.{param_name}"
        entry = self._store.get(key)
        return entry[0] if entry else None

    def update(self, effect_match_name: str, param_name: str, value: Any, weight: float = 1.0) -> None:
        key = f"{effect_match_name}.{param_name}"
        self._store[key] = (value, weight)
        self._save()

    def get_all(self) -> Dict[str, Any]:
        result = {}
        for key, (value, _) in self._store.items():
            result[key] = value
        return result


class PersistentLearningLoop(LearningLoop):
    """持久化学习循环 - 继承 LearningLoop 并添加持久化能力"""

    def __init__(self, storage: Optional[FileSystemStorage] = None,
                 auto_save: bool = True,
                 checkpoint_enabled: bool = True):
        self._pstorage = storage or FileSystemStorage()
        self._auto_save = auto_save
        self._checkpoint_enabled = checkpoint_enabled
        self._last_checkpoint_time = time.time()
        self._lock = threading.Lock()

        case_store = PersistentCaseStore(self._pstorage)
        default_value_store = PersistentDefaultValueStore(self._pstorage)

        super().__init__(case_store=case_store, default_value_store=default_value_store)

        self._load_execution_records()
        self._load_confidence_adjustments()

    # ========== 执行记录持久化 ==========

    def _load_execution_records(self) -> None:
        saved = self._pstorage.load(EXECUTION_RECORDS_FILE, [])
        self._execution_records = []
        for r_data in saved:
            try:
                record = self._dict_to_record(r_data)
                self._execution_records.append(record)
            except Exception:
                continue

    def _save_execution_records(self) -> None:
        records_to_save = self._execution_records[-MAX_RECORDS:]
        data = [self._record_to_dict(r) for r in records_to_save]
        self._pstorage.save(EXECUTION_RECORDS_FILE, data)

    def _load_confidence_adjustments(self) -> None:
        saved = self._pstorage.load(CONFIDENCE_ADJUSTMENTS_FILE, [])
        self._confidence_adjustments = []
        for a_data in saved:
            try:
                self._confidence_adjustments.append(ConfidenceAdjustment(
                    reasoning_path=a_data.get("reasoningPath", []),
                    direction=a_data.get("direction", "boost"),
                    delta=a_data.get("delta", 0.05),
                    timestamp=a_data.get("timestamp", ""),
                ))
            except Exception:
                continue

    def _save_confidence_adjustments(self) -> None:
        data = []
        for a in self._confidence_adjustments:
            data.append({
                "reasoningPath": a.reasoning_path,
                "direction": a.direction,
                "delta": a.delta,
                "timestamp": a.timestamp,
            })
        self._pstorage.save(CONFIDENCE_ADJUSTMENTS_FILE, data)

    def _dict_to_record(self, data: Dict[str, Any]) -> ExecutionRecord:
        expected = ExpectedParameters(
            comp_name=data.get("expected", {}).get("compName", ""),
            layer_index=data.get("expected", {}).get("layerIndex", 0),
            effect_match_name=data.get("expected", {}).get("effectMatchName", ""),
            effect_name=data.get("expected", {}).get("effectName", ""),
            properties=[],
        )
        execution = LRExecutionResult(
            success=data.get("execution", {}).get("success", False),
            error_code=data.get("execution", {}).get("errorCode", ""),
            error_message=data.get("execution", {}).get("errorMessage", ""),
            effect_name=data.get("execution", {}).get("effectName", ""),
            execution_time=data.get("execution", {}).get("executionTime", 0),
        )
        verification = LRVerificationResult(
            passed=data.get("verification", {}).get("passed", False),
            deviation_score=data.get("verification", {}).get("deviationScore"),
            mismatched_properties=data.get("verification", {}).get("mismatchedProperties", []),
            verified_at=data.get("verification", {}).get("verifiedAt", ""),
        )
        return ExecutionRecord(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", ""),
            user_input=data.get("userInput", ""),
            intent_type=data.get("intentType", ""),
            expected=expected,
            execution=execution,
            verification=verification,
            user_satisfied=data.get("userSatisfied"),
            user_adjusted=data.get("userAdjusted"),
            user_undone=data.get("userUndone"),
            final_params=data.get("finalParams"),
            reasoning_path=data.get("reasoningPath"),
        )

    def _record_to_dict(self, record: ExecutionRecord) -> Dict[str, Any]:
        expected = record.expected
        expected_dict = {
            "compName": getattr(expected, "comp_name", ""),
            "layerIndex": getattr(expected, "layer_index", 0),
            "effectMatchName": getattr(expected, "effect_match_name", ""),
            "effectName": getattr(expected, "effect_name", ""),
            "properties": [
                {"name": p.name, "value": p.value, "tolerance": getattr(p, "tolerance", 0.01)}
                for p in getattr(expected, "properties", [])
            ],
        }

        execution = record.execution
        execution_dict = {
            "success": getattr(execution, "success", False),
            "errorCode": getattr(execution, "error_code", ""),
            "errorMessage": getattr(execution, "error_message", ""),
            "effectName": getattr(execution, "effect_name", ""),
            "executionTime": getattr(execution, "execution_time", 0),
        }

        verification = record.verification
        verification_dict = {
            "passed": getattr(verification, "passed", False),
            "deviationScore": getattr(verification, "deviation_score"),
            "mismatchedProperties": getattr(verification, "mismatched_properties", []),
            "verifiedAt": getattr(verification, "verified_at", ""),
        }

        return {
            "id": record.id,
            "userInput": record.user_input,
            "intentType": record.intent_type,
            "timestamp": record.timestamp,
            "expected": expected_dict,
            "execution": execution_dict,
            "verification": verification_dict,
            "userSatisfied": record.user_satisfied,
            "userAdjusted": record.user_adjusted,
            "userUndone": record.user_undone,
            "finalParams": record.final_params,
            "reasoningPath": record.reasoning_path,
        }

    # ========== 检查点机制 ==========

    def _maybe_save_checkpoint(self) -> None:
        if not self._checkpoint_enabled:
            return
        now = time.time()
        if now - self._last_checkpoint_time < CHECKPOINT_INTERVAL_SEC:
            return

        try:
            if not os.path.exists(CHECKPOINTS_DIR):
                os.makedirs(CHECKPOINTS_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            cp_dir = os.path.join(CHECKPOINTS_DIR, f"checkpoint_{ts}")
            os.makedirs(cp_dir, exist_ok=True)

            import shutil
            for fname in [
                "case-store.json", "default-value-store.json",
                "execution-records.json", "confidence-adjustments.json",
            ]:
                src = os.path.join(STATE_DIR, fname)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(cp_dir, fname))

            checkpoints = sorted([
                d for d in os.listdir(CHECKPOINTS_DIR)
                if d.startswith("checkpoint_")
            ])
            for old_cp in checkpoints[:-10]:
                shutil.rmtree(os.path.join(CHECKPOINTS_DIR, old_cp), ignore_errors=True)

            self._last_checkpoint_time = now
        except Exception:
            pass

    def _trigger_save(self) -> None:
        if not self._auto_save:
            return
        with self._lock:
            try:
                self._save_execution_records()
                self._save_confidence_adjustments()
            except Exception:
                pass
            self._maybe_save_checkpoint()

    # ========== 覆盖父类方法 ==========

    def record_execution(
        self,
        user_input: str,
        intent_type: str,
        expected: ExpectedParameters,
        execution: LRExecutionResult,
        verification: LRVerificationResult,
        user_feedback: Optional[UserFeedback] = None,
        reasoning_path: Optional[List[str]] = None,
    ) -> ExecutionRecord:
        record = super().record_execution(
            user_input, intent_type, expected,
            execution, verification, user_feedback, reasoning_path
        )
        self._trigger_save()
        return record

    # ========== 额外方法 ==========

    def force_save(self) -> None:
        """强制立即保存所有状态"""
        with self._lock:
            self._save_execution_records()
            self._save_confidence_adjustments()
            if isinstance(self._case_store, PersistentCaseStore):
                self._case_store._save()
            if isinstance(self._default_value_store, PersistentDefaultValueStore):
                self._default_value_store._save()

    def load_from_checkpoint(self, checkpoint_name: str) -> bool:
        """从指定检查点恢复"""
        try:
            import shutil
            cp_dir = os.path.join(CHECKPOINTS_DIR, checkpoint_name)
            if not os.path.exists(cp_dir):
                return False
            for fname in [
                "case-store.json", "default-value-store.json",
                "execution-records.json", "confidence-adjustments.json",
            ]:
                src = os.path.join(cp_dir, fname)
                dst = os.path.join(STATE_DIR, fname)
                if os.path.exists(src):
                    shutil.copy2(src, dst)

            if isinstance(self._case_store, PersistentCaseStore):
                self._case_store._load()
            if isinstance(self._default_value_store, PersistentDefaultValueStore):
                self._default_value_store._load()
            self._load_execution_records()
            self._load_confidence_adjustments()
            return True
        except Exception:
            return False

    def list_checkpoints(self) -> List[str]:
        """列出所有检查点"""
        if not os.path.exists(CHECKPOINTS_DIR):
            return []
        return sorted([
            d for d in os.listdir(CHECKPOINTS_DIR)
            if d.startswith("checkpoint_")
        ], reverse=True)

    def get_stats(self) -> Dict[str, Any]:
        """获取持久化统计信息"""
        from learning_loop import LearningMetrics

        metrics: Dict[str, Any] = {
            "persistent": True,
            "state_dir": STATE_DIR,
            "auto_save": self._auto_save,
            "checkpoint_enabled": self._checkpoint_enabled,
            "checkpoints": len(self.list_checkpoints()),
            "templates_count": len(self._case_store.get_all_templates()),
            "execution_records_count": len(self._execution_records),
            "confidence_adjustments_count": len(self._confidence_adjustments),
        }
        return metrics
