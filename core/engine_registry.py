"""core/engine_registry.py - 统一引擎注册中心 v1.0
====================================================

集中管理视频流水线所有可用引擎（AE/DaVinci/FFmpeg/Topaz/Blender/MoviePy/...）的
注册、查询、能力声明、执行历史与基于成功率的最优选择。

设计目标:
1. **单一来源**: 所有引擎元数据、能力、执行历史集中在 registry_state.json
2. **历史感知**: record_execution 记录每次执行的 success/duration/quality
3. **成功率优先**: select_best(stage, context) 基于贝叶斯平滑的成功率选择最优引擎
4. **降级友好**: 当 registry 不可用 (ImportError / 文件损坏) 时，调用方应回退到原有逻辑
5. **线程安全**: 单例模式 + 简单锁，确保并发记录执行历史不会丢数据

集成方式:
    from core.engine_registry import get_engine_registry, EngineMetadata

    registry = get_engine_registry()
    registry.register("ae", AEEngineClass, EngineMetadata(
        name="ae", version="2024", capabilities=["execute", "render"],
        cost_per_sec=0.05, quality_tier="high"
    ))
    engine_name = registry.select_best("execute", task_context)
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class EngineMetadata:
    """引擎元数据
    
    Attributes:
        name: 引擎唯一标识 (ae / davinci / ffmpeg / moviepy / topaz / blender ...)
        version: 引擎版本字符串
        capabilities: 能力声明列表 (perceive / analyze / plan / execute / render / verify)
        cost_per_sec: 每秒执行成本 (USD 或任意货币单位)，用于成本敏感场景
        quality_tier: 质量分级 (low / medium / high / ultra)
    """
    name: str
    version: str = "1.0"
    capabilities: List[str] = field(default_factory=list)
    cost_per_sec: float = 0.0
    quality_tier: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EngineMetadata":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0"),
            capabilities=list(data.get("capabilities", [])),
            cost_per_sec=float(data.get("cost_per_sec", 0.0)),
            quality_tier=data.get("quality_tier", "medium"),
        )


@dataclass
class EngineExecutionRecord:
    """引擎单次执行记录 (用于统计与选择)"""
    engine_name: str
    stage: str
    success: bool
    duration: float
    quality: float
    timestamp: float = field(default_factory=time.time)


# ============================================================================
#  EngineRegistry 单例
# ============================================================================

class EngineRegistry:
    """统一引擎注册中心
    
    负责引擎注册、查询、历史记录与最优选择。所有状态持久化到
    `data/engine_registry/registry_state.json`，进程重启后可恢复。
    """

    # 默认持久化路径 (相对项目根目录)
    DEFAULT_STATE_FILE = "data/engine_registry/registry_state.json"

    # 单例用 — 不要直接访问，使用 get_engine_registry()
    def __init__(self, state_file: Optional[str] = None):
        """初始化注册中心
        
        Args:
            state_file: 自定义持久化文件路径。None 时使用默认路径。
        """
        self._state_file = Path(state_file) if state_file else Path(self.DEFAULT_STATE_FILE)
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

        # 引擎类注册表: name -> (engine_class, metadata)
        self._engines: Dict[str, Dict[str, Any]] = {}
        # 执行历史: engine_name -> {stage -> [records]}
        self._history: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        # 选择记录: path_id -> {engine, reason, timestamp} 用于 explain
        self._choice_log: Dict[str, Dict[str, Any]] = {}

        self._lock = threading.RLock()
        self._load_state()

    # -------------------------------------------------------------------------
    #  注册与查询
    # -------------------------------------------------------------------------

    def register(
        self,
        engine_name: str,
        engine_class: Type,
        metadata: EngineMetadata,
    ) -> None:
        """注册引擎类与元数据
        
        Args:
            engine_name: 引擎唯一名 (重复注册将覆盖)
            engine_class: 引擎类 (调用方负责实例化)
            metadata: 引擎元数据
        """
        if not engine_name:
            raise ValueError("engine_name 不能为空")
        with self._lock:
            self._engines[engine_name] = {
                "class": engine_class,
                "metadata": metadata,
            }
            if engine_name not in self._history:
                self._history[engine_name] = {}
            logger.debug(
                "[EngineRegistry] Registered engine '%s' (caps=%s, tier=%s)",
                engine_name, metadata.capabilities, metadata.quality_tier,
            )
            self._save_state()

    def get(self, engine_name: str) -> Optional[Type]:
        """获取引擎类
        
        Args:
            engine_name: 引擎名
        
        Returns:
            引擎类，未注册返回 None
        """
        with self._lock:
            entry = self._engines.get(engine_name)
            return entry["class"] if entry else None

    def get_metadata(self, engine_name: str) -> Optional[EngineMetadata]:
        """获取引擎元数据"""
        with self._lock:
            entry = self._engines.get(engine_name)
            return entry["metadata"] if entry else None

    def list_available(self) -> List[str]:
        """列出所有已注册引擎名"""
        with self._lock:
            return list(self._engines.keys())

    def list_by_capability(self, capability: str) -> List[str]:
        """按能力筛选引擎
        
        Args:
            capability: 能力名 (execute / render / ...)
        
        Returns:
            具备该能力的引擎名列表
        """
        with self._lock:
            return [
                name for name, entry in self._engines.items()
                if capability in entry["metadata"].capabilities
            ]

    # -------------------------------------------------------------------------
    #  执行历史
    # -------------------------------------------------------------------------

    def record_execution(
        self,
        engine_name: str,
        success: bool,
        duration: float,
        quality: float,
        stage: str = "",
    ) -> None:
        """记录一次引擎执行结果
        
        Args:
            engine_name: 引擎名
            success: 是否成功
            duration: 执行耗时 (秒)
            quality: 输出质量分 (0-100)
            stage: 所属阶段 (execute / render ...)
        """
        if engine_name not in self._history:
            self._history[engine_name] = {}
        if stage not in self._history[engine_name]:
            self._history[engine_name][stage] = []

        record = {
            "success": bool(success),
            "duration": float(duration),
            "quality": float(quality),
            "timestamp": time.time(),
        }
        with self._lock:
            self._history[engine_name][stage].append(record)
            # 限制历史长度，防止无限增长
            if len(self._history[engine_name][stage]) > 200:
                self._history[engine_name][stage] = self._history[engine_name][stage][-200:]
            self._save_state()

    def get_statistics(self, engine_name: str) -> Dict[str, Any]:
        """获取引擎的执行统计
        
        Args:
            engine_name: 引擎名
        
        Returns:
            统计字典 (total / success / avg_duration / avg_quality / success_rate)
            未注册返回空字典
        """
        with self._lock:
            history = self._history.get(engine_name, {})
            all_records: List[Dict[str, Any]] = []
            for stage_records in history.values():
                all_records.extend(stage_records)

            if not all_records:
                return {"total": 0, "success_rate": 0.5, "engine_name": engine_name}

            total = len(all_records)
            success_count = sum(1 for r in all_records if r["success"])
            avg_dur = sum(r["duration"] for r in all_records) / total
            avg_q = sum(r["quality"] for r in all_records) / total
            return {
                "engine_name": engine_name,
                "total": total,
                "success": success_count,
                "success_rate": success_count / total,
                "avg_duration": avg_dur,
                "avg_quality": avg_q,
            }

    # -------------------------------------------------------------------------
    #  最优选择
    # -------------------------------------------------------------------------

    def select_best(
        self,
        stage: str,
        context: Optional[Any] = None,
        candidates: Optional[List[str]] = None,
    ) -> Optional[str]:
        """基于历史成功率选择最优引擎
        
        评分函数 (贝叶斯平滑 + 多因子):
            score = 0.6 * success_rate_smoothed
                  + 0.2 * quality_normalized
                  + 0.1 * speed_normalized
                  + 0.1 * tier_bonus
        
        其中 success_rate_smoothed 使用 Beta(α=2, β=2) 先验做平滑:
            smoothed = (success + 2) / (total + 4)
        这样无历史的引擎默认得 0.5，不会因零先验被完全排除。
        
        Args:
            stage: 目标阶段 (execute / render ...)
            context: 任务上下文 (可选，用于未来按上下文过滤)
            candidates: 候选引擎列表 (None 时使用所有具备该 stage 能力的引擎)
        
        Returns:
            最优引擎名，无可用引擎返回 None
        """
        with self._lock:
            # 显式传入空列表 (candidates=[]) 表示"无候选"，直接返回 None
            # 传入 None 表示"未指定"，自动按能力过滤
            if candidates is None:
                candidates = self.list_by_capability(stage)
                # 若能力过滤也无结果，退回到所有已注册引擎
                if not candidates:
                    candidates = list(self._engines.keys())
            if not candidates:
                return None

            scored: List[tuple] = []
            for name in candidates:
                stats = self.get_statistics(name)
                meta = self.get_metadata(name) or EngineMetadata(name=name)

                total = stats.get("total", 0)
                success = stats.get("success", 0)
                # 贝叶斯平滑
                smoothed_rate = (success + 2) / (total + 4)

                avg_q = stats.get("avg_quality", 50.0) / 100.0
                avg_dur = stats.get("avg_duration", 30.0)
                speed_norm = max(0.0, min(1.0, 30.0 / max(avg_dur, 0.1)))

                tier_map = {"ultra": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}
                tier_bonus = tier_map.get(meta.quality_tier, 0.5)

                # 成本惩罚 (cost_per_sec 越高，分数越低)
                cost_penalty = max(0.0, 1.0 - meta.cost_per_sec * 0.1)

                score = (
                    0.6 * smoothed_rate
                    + 0.2 * avg_q
                    + 0.1 * speed_norm
                    + 0.1 * tier_bonus
                ) * cost_penalty

                scored.append((score, name))
                logger.debug(
                    "[EngineRegistry] score(%s)=%.3f (rate=%.2f, q=%.2f, speed=%.2f, tier=%.2f)",
                    name, score, smoothed_rate, avg_q, speed_norm, tier_bonus,
                )

            scored.sort(reverse=True)
            best = scored[0][1] if scored else None

            # 记录选择，供 explain_choice 使用
            if best:
                path_id = f"{stage}:{best}:{int(time.time()*1000)}"
                self._choice_log[path_id] = {
                    "stage": stage,
                    "engine": best,
                    "score": scored[0][0],
                    "candidates": list(candidates),
                    "reason": f"Bayesian-smoothed success rate * quality * speed * tier",
                    "timestamp": time.time(),
                }
            return best

    def explain_choice(self, path_id: str) -> Dict[str, Any]:
        """解释某次选择决策
        
        Args:
            path_id: 选择路径 ID (由 select_best 内部生成)
        
        Returns:
            决策详情字典，找不到返回空字典
        """
        with self._lock:
            return dict(self._choice_log.get(path_id, {}))

    def list_recent_choices(self, limit: int = 10) -> List[Dict[str, Any]]:
        """列出最近的选择记录"""
        with self._lock:
            sorted_choices = sorted(
                self._choice_log.values(),
                key=lambda x: x.get("timestamp", 0),
                reverse=True,
            )
            return sorted_choices[:limit]

    # -------------------------------------------------------------------------
    #  持久化
    # -------------------------------------------------------------------------

    def _save_state(self) -> None:
        """将注册中心状态序列化到磁盘
        
        注意: engine_class 是 Python 类对象，不可 JSON 序列化。
        持久化时只保存 metadata + history + choice_log。
        重新加载后，调用方需重新 register() 注册引擎类。
        """
        try:
            state = {
                "metadata": {
                    name: entry["metadata"].to_dict()
                    for name, entry in self._engines.items()
                },
                "history": self._history,
                "choice_log": self._choice_log,
                "version": "1.0",
                "saved_at": time.time(),
            }
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning("[EngineRegistry] Save state failed: %s", e)

    def _load_state(self) -> None:
        """从磁盘恢复状态 (仅 metadata + history，类需重新注册)"""
        if not self._state_file.exists():
            return
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            # 恢复 history
            self._history = state.get("history", {})
            # 恢复 choice_log
            self._choice_log = state.get("choice_log", {})
            # 恢复 metadata (类对象需调用方重新 register 补充)
            for name, meta_dict in state.get("metadata", {}).items():
                self._engines[name] = {
                    "class": None,  # 类对象需重新注册
                    "metadata": EngineMetadata.from_dict(meta_dict),
                }
                # 确保 history 字典结构完整
                if name not in self._history:
                    self._history[name] = {}
            logger.debug(
                "[EngineRegistry] Loaded state: %d engines, %d choices",
                len(self._engines), len(self._choice_log),
            )
        except Exception as e:
            logger.warning("[EngineRegistry] Load state failed: %s", e)

    def clear_history(self) -> None:
        """清空执行历史 (用于测试)"""
        with self._lock:
            self._history = {name: {} for name in self._engines}
            self._choice_log = {}
            self._save_state()


# ============================================================================
#  单例工厂
# ============================================================================

_global_registry: Optional[EngineRegistry] = None
_registry_lock = threading.Lock()


def get_engine_registry(state_file: Optional[str] = None) -> EngineRegistry:
    """获取全局 EngineRegistry 单例
    
    Args:
        state_file: 仅在首次调用时生效，用于自定义持久化路径
    
    Returns:
        全局 EngineRegistry 实例
    """
    global _global_registry
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = EngineRegistry(state_file=state_file)
    return _global_registry


def reset_engine_registry() -> None:
    """重置全局单例 (主要用于测试)"""
    global _global_registry
    with _registry_lock:
        _global_registry = None
