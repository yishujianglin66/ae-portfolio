"""
core/causal_engine.py — 跨引擎因果推断引擎 v1.0
====================================================

从执行日志中自动发现引擎间因果关系，支持反事实推理和最优干预搜索。

设计原则:
1. 数据驱动: 从历史执行记录中自动发现因果关系（PC算法）
2. 专家先验: 支持注入领域专家知识作为先验因果图
3. 反事实推理: 基于结构因果模型(SCM) 回答 "如果...会怎样"
4. 干预优化: 计算最优干预策略阻断故障传播
5. 增量学习: 每次运行后贝叶斯后验更新因果边权重
6. 离线可用: 所有算法纯 numpy/scipy 实现，无需外部因果库

集成方式:
    from core.causal_engine import get_causal_engine

    engine = get_causal_engine()
    # 反事实查询
    result = await engine.counterfactual_query(failure, intervention, context)
    # 最优干预
    plan = await engine.optimal_intervention(state, target)
"""
from __future__ import annotations

import json
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

class EngineType(Enum):
    """引擎类型"""
    AE = "ae"
    DAVINCI = "davinci"
    FFMPEG = "ffmpeg"
    PIPELINE = "pipeline"  # 管线自身


class NodeType(Enum):
    """因果图节点类型"""
    ENGINE_STAGE = auto()    # 引擎+阶段组合 (如 ae_execute, davinci_color)
    ENGINE_STATE = auto()    # 引擎状态 (如 ae_memory, ffmpeg_cpu)
    PARAMETER = auto()       # 参数节点 (如 blur_radius, saturation)
    OUTPUT_QUALITY = auto()  # 输出质量节点


@dataclass
class CausalNode:
    """因果图节点"""
    id: str
    node_type: NodeType
    engine: EngineType
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CausalEdge:
    """因果图边（含权重和置信度）"""
    source: str
    target: str
    weight: float = 0.0          # 因果效应强度 [-1, 1]
    confidence: float = 0.0      # 边的置信度 [0, 1]
    is_expert: bool = False      # 是否来自专家先验
    sample_count: int = 0        # 支撑样本数
    last_updated: float = 0.0    # 最后更新时间戳


@dataclass
class EngineFailure:
    """引擎故障记录"""
    engine: EngineType
    stage: str
    error_msg: str
    error_type: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    upstream_outputs: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class Intervention:
    """干预动作"""
    target_node: str          # 干预目标节点
    action: str               # 干预类型: "fix_param" | "insert_transcode" | "skip_stage" | "retry"
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class InterventionPlan:
    """干预计划"""
    interventions: List[Intervention]
    expected_success_rate: float = 0.0
    expected_quality_impact: float = 0.0
    estimated_cost: float = 0.0  # 额外耗时(秒)
    reasoning: str = ""


@dataclass
class CounterfactualResult:
    """反事实查询结果"""
    observed: str               # 实际观测到的结果
    counterfactual: str         # 反事实结果
    causal_effect: float        # 因果效应量
    confidence: float           # 置信度
    explanation: str = ""
    alternative_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    # P3.2 扩展字段（向后兼容：均有默认值）
    alternative_engine: str = ""                # 假设使用的替代引擎
    failure_id: str = ""                        # 关联的故障记录 ID
    estimated_success_rate: float = 0.0         # 反事实估算的成功率
    estimated_quality: float = 0.0              # 反事实估算的质量分
    historical_support: int = 0                 # 历史支撑样本数


@dataclass
class CausalLink:
    """因果链中的一跳
    
    表示从 source 节点到 target 节点的因果关系，包含:
    - 边的权重（因果效应强度）
    - 边的置信度
    - 该跳的解释
    """
    source: str
    target: str
    weight: float = 0.0
    confidence: float = 0.0
    explanation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "weight": self.weight,
            "confidence": self.confidence,
            "explanation": self.explanation,
        }


@dataclass
class ExecutionRecord:
    """单次管线执行记录（用于因果发现）"""
    run_id: str
    timestamp: float = 0.0
    # 每个阶段的执行结果: stage_name -> {success, duration, error, engine, params}
    stages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # 引擎状态快照: engine -> {memory, cpu, ...}
    engine_states: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # 最终输出质量
    output_quality: float = 0.0
    # 是否整体成功
    success: bool = False


# ============================================================================
#  专家先验因果图
# ============================================================================

# 基于领域知识的先验因果关系
EXPERT_PRIOR_EDGES: List[Dict[str, Any]] = [
    # AE 输出质量 → DaVinci 输入质量
    {"source": "ae_execute", "target": "davinci_color", "weight": 0.7, "confidence": 0.8},
    # AE 崩溃 → 下游 FFmpeg 无输入
    {"source": "ae_execute", "target": "ffmpeg_transcode", "weight": -0.9, "confidence": 0.9},
    # DaVinci 调色 → FFmpeg 最终输出
    {"source": "davinci_color", "target": "ffmpeg_transcode", "weight": 0.6, "confidence": 0.7},
    # AE 内存占用 → AE 稳定性
    {"source": "ae_memory", "target": "ae_execute", "weight": -0.5, "confidence": 0.7},
    # FFmpeg CPU → FFmpeg 稳定性
    {"source": "ffmpeg_cpu", "target": "ffmpeg_transcode", "weight": -0.4, "confidence": 0.6},
    # 效果参数 → AE 执行稳定性
    {"source": "effect_params", "target": "ae_execute", "weight": -0.3, "confidence": 0.6},
    # AE 输出格式 → DaVinci 兼容性
    {"source": "ae_output_format", "target": "davinci_color", "weight": 0.5, "confidence": 0.7},
    # DaVinci 项目DB → DaVinci 稳定性
    {"source": "davinci_db_state", "target": "davinci_color", "weight": -0.4, "confidence": 0.6},
    # 素材分辨率 → AE 内存占用
    {"source": "input_resolution", "target": "ae_memory", "weight": 0.6, "confidence": 0.8},
    # 素材编码 → FFmpeg 解码稳定性
    {"source": "input_codec", "target": "ffmpeg_transcode", "weight": -0.3, "confidence": 0.6},
]


# ============================================================================
#  因果图数据结构
# ============================================================================

class CausalGraph:
    """因果图（有向无环图）
    
    支持:
    - 节点/边的增删改
    - 拓扑排序
    - d-分离判定
    - 祖先/后代查询
    - JSON 序列化/反序列化
    """
    
    def __init__(self):
        self._nodes: Dict[str, CausalNode] = {}
        self._edges: Dict[str, Dict[str, CausalEdge]] = {}  # source -> target -> edge
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)  # 邻接表
        self._reverse_adj: Dict[str, Set[str]] = defaultdict(set)  # 反向邻接
    
    @property
    def nodes(self) -> Dict[str, CausalNode]:
        return self._nodes
    
    @property
    def edges(self) -> List[CausalEdge]:
        return [e for targets in self._edges.values() for e in targets.values()]
    
    def add_node(self, node: CausalNode) -> None:
        self._nodes[node.id] = node
    
    def add_edge(self, edge: CausalEdge) -> None:
        if edge.source not in self._nodes or edge.target not in self._nodes:
            return
        self._edges.setdefault(edge.source, {})[edge.target] = edge
        self._adjacency[edge.source].add(edge.target)
        self._reverse_adj[edge.target].add(edge.source)
    
    def get_edge(self, source: str, target: str) -> Optional[CausalEdge]:
        return self._edges.get(source, {}).get(target)
    
    def parents(self, node_id: str) -> Set[str]:
        return self._reverse_adj.get(node_id, set())
    
    def children(self, node_id: str) -> Set[str]:
        return self._adjacency.get(node_id, set())
    
    def ancestors(self, node_id: str) -> Set[str]:
        """获取所有祖先节点"""
        visited = set()
        stack = list(self.parents(node_id))
        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)
            stack.extend(self.parents(n))
        return visited
    
    def descendants(self, node_id: str) -> Set[str]:
        """获取所有后代节点"""
        visited = set()
        stack = list(self.children(node_id))
        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)
            stack.extend(self.children(n))
        return visited
    
    def topological_sort(self) -> List[str]:
        """Kahn 算法拓扑排序"""
        in_degree = {n: len(self.parents(n)) for n in self._nodes}
        queue = [n for n, d in in_degree.items() if d == 0]
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for child in self.children(node):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)
        return result
    
    def has_path(self, source: str, target: str) -> bool:
        """判断是否存在有向路径"""
        visited = set()
        stack = [source]
        while stack:
            n = stack.pop()
            if n == target:
                return True
            if n in visited:
                continue
            visited.add(n)
            stack.extend(self.children(n))
        return False
    
    def all_paths(self, source: str, target: str) -> List[List[str]]:
        """枚举所有有向路径"""
        paths = []
        self._dfs_paths(source, target, [source], set(), paths)
        return paths
    
    def _dfs_paths(self, current: str, target: str, path: List[str],
                   visited: Set[str], paths: List[List[str]], max_depth: int = 10):
        if current == target:
            paths.append(list(path))
            return
        if len(path) > max_depth:
            return
        visited.add(current)
        for child in self.children(current):
            if child not in visited:
                path.append(child)
                self._dfs_paths(child, target, path, visited, paths, max_depth)
                path.pop()
        visited.discard(current)
    
    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "nodes": {
                nid: {
                    "id": n.id, "node_type": n.node_type.name,
                    "engine": n.engine.value, "name": n.name,
                    "metadata": n.metadata
                }
                for nid, n in self._nodes.items()
            },
            "edges": [
                {
                    "source": e.source, "target": e.target,
                    "weight": e.weight, "confidence": e.confidence,
                    "is_expert": e.is_expert, "sample_count": e.sample_count,
                    "last_updated": e.last_updated
                }
                for e in self.edges
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "CausalGraph":
        """从字典反序列化"""
        g = cls()
        for nid, ndata in data.get("nodes", {}).items():
            g.add_node(CausalNode(
                id=ndata["id"],
                node_type=NodeType[ndata["node_type"]],
                engine=EngineType(ndata["engine"]),
                name=ndata["name"],
                metadata=ndata.get("metadata", {})
            ))
        for edata in data.get("edges", []):
            g.add_edge(CausalEdge(
                source=edata["source"], target=edata["target"],
                weight=edata.get("weight", 0.0),
                confidence=edata.get("confidence", 0.0),
                is_expert=edata.get("is_expert", False),
                sample_count=edata.get("sample_count", 0),
                last_updated=edata.get("last_updated", 0.0)
            ))
        return g


# ============================================================================
#  引擎状态感知层 (M1.4)
# ============================================================================

class EngineStateObserver:
    """引擎状态感知层
    
    监听各引擎实时状态，作为因果图节点的观测值。
    支持:
    - 引擎可用性检测
    - 资源占用监控
    - 状态变化事件记录
    """
    
    def __init__(self):
        self._current_states: Dict[str, Dict[str, float]] = {}
        self._state_history: List[Dict[str, Any]] = []
        self._last_check: float = 0.0
    
    def observe(self, engine: str, metrics: Dict[str, float]) -> None:
        """记录引擎状态观测"""
        ts = time.time()
        self._current_states[engine] = {**metrics, "_timestamp": ts}
        self._state_history.append({
            "engine": engine, "metrics": metrics, "timestamp": ts
        })
        self._last_check = ts
    
    def get_state(self, engine: str) -> Dict[str, float]:
        """获取引擎最新状态"""
        return self._current_states.get(engine, {})
    
    def is_healthy(self, engine: str) -> bool:
        """判断引擎是否健康"""
        state = self.get_state(engine)
        if not state:
            return True  # 无数据时假设健康
        # 内存使用 > 90% 视为不健康
        mem_pct = state.get("memory_pct", 0)
        if mem_pct > 90:
            return False
        return True
    
    def get_recent_states(self, engine: str, n: int = 10) -> List[Dict]:
        """获取最近 N 次状态记录"""
        engine_records = [r for r in self._state_history if r["engine"] == engine]
        return engine_records[-n:]
    
    def snapshot(self) -> Dict[str, Dict[str, float]]:
        """获取所有引擎当前状态快照"""
        return dict(self._current_states)


# ============================================================================
#  因果发现算法 (M1.1)
# ============================================================================

class CausalDiscovery:
    """因果结构发现引擎
    
    实现:
    1. PC 算法 (约束方法): 通过条件独立性检验学习因果骨架
    2. 方向依赖: 基于先验知识和时间顺序定向
    3. 增量更新: 新数据到来时增量更新因果边
    
    由于离线环境约束，不依赖 causal-learn 库，纯 numpy 实现。
    """
    
    def __init__(self, alpha: float = 0.05):
        """
        Args:
            alpha: 条件独立性检验的显著性水平
        """
        self._alpha = alpha
    
    def _fisher_z_test(self, data: np.ndarray, x: int, y: int,
                       conditioning: List[int]) -> float:
        """Fisher Z 条件独立性检验
        
        检验: X ⊥ Y | conditioning_set
        
        Returns:
            p-value (越小越不独立)
        """
        n = data.shape[0]
        if n < 5:
            return 1.0  # 样本不足，无法判断
        
        # 构建回归矩阵
        if conditioning:
            # 偏相关: 回归掉条件集的影响
            Z = data[:, conditioning]
            # 添加截距项
            Z_aug = np.column_stack([np.ones(n), Z])
            
            # 残差 X ~ Z
            try:
                beta_x = np.linalg.lstsq(Z_aug, data[:, x], rcond=None)[0]
                res_x = data[:, x] - Z_aug @ beta_x
            except np.linalg.LinAlgError:
                return 1.0
            
            # 残差 Y ~ Z
            try:
                beta_y = np.linalg.lstsq(Z_aug, data[:, y], rcond=None)[0]
                res_y = data[:, y] - Z_aug @ beta_y
            except np.linalg.LinAlgError:
                return 1.0
            
            # 残差相关系数
            if np.std(res_x) < 1e-10 or np.std(res_y) < 1e-10:
                return 1.0
            r = np.corrcoef(res_x, res_y)[0, 1]
            dof = n - len(conditioning) - 2
        else:
            # 简单相关
            if np.std(data[:, x]) < 1e-10 or np.std(data[:, y]) < 1e-10:
                return 1.0
            r = np.corrcoef(data[:, x], data[:, y])[0, 1]
            dof = n - 2
        
        if dof <= 0:
            return 1.0
        
        # Fisher Z 变换
        r = np.clip(r, -0.999, 0.999)
        z = 0.5 * math.log((1 + r) / (1 - r))
        z_stat = abs(z) * math.sqrt(dof)
        
        # 近似 p-value (标准正态)
        p_value = 2 * (1 - _norm_cdf(z_stat))
        return p_value
    
    def discover_skeleton(
        self,
        data: np.ndarray,
        var_names: List[str]
    ) -> Tuple[Set[Tuple[int, int]], Dict[Tuple[int, int], Set[int]]]:
        """发现因果骨架（无向）
        
        PC 算法骨架发现阶段:
        1. 从完全图开始
        2. 对每对变量，逐步增大条件集
        3. 如果找到使两者条件独立的条件集，删除边
        
        Args:
            data: (n_samples, n_vars) 观测数据矩阵
            var_names: 变量名列表
            
        Returns:
            skeleton: 无向边集合 {(i, j), ...}
            sep_sets: 分离集 {(i, j): conditioning_set, ...}
        """
        n_vars = data.shape[1]
        
        # 初始化: 完全图
        skeleton = set()
        for i in range(n_vars):
            for j in range(i + 1, n_vars):
                skeleton.add((i, j))
        
        sep_sets: Dict[Tuple[int, int], Set[int]] = {}
        
        # 逐步增大条件集
        max_cond_size = n_vars - 2
        for cond_size in range(0, max_cond_size + 1):
            edges_to_remove = []
            
            for (i, j) in list(skeleton):
                # 获取 i 的邻居（排除 j）
                neighbors_i = set()
                for (a, b) in skeleton:
                    if a == i and b != j:
                        neighbors_i.add(b)
                    elif b == i and a != j:
                        neighbors_i.add(a)
                
                if len(neighbors_i) < cond_size:
                    continue
                
                # 枚举条件集
                for cond_set in _combinations(sorted(neighbors_i), cond_size):
                    cond_list = list(cond_set)
                    p_value = self._fisher_z_test(data, i, j, cond_list)
                    
                    if p_value > self._alpha:
                        # X_i ⊥ X_j | cond_set → 删除边
                        edges_to_remove.append((i, j))
                        sep_sets[(i, j)] = set(cond_list)
                        sep_sets[(j, i)] = set(cond_list)
                        break
            
            for edge in edges_to_remove:
                skeleton.discard(edge)
        
        return skeleton, sep_sets
    
    def orient_edges(
        self,
        skeleton: Set[Tuple[int, int]],
        sep_sets: Dict[Tuple[int, int], Set[int]],
        prior_edges: Optional[List[Tuple[int, int]]] = None,
        temporal_order: Optional[List[str]] = None
    ) -> List[Tuple[int, int]]:
        """定向边（基于先验知识和时间顺序）
        
        规则:
        1. 先验边直接采用给定方向
        2. 时间顺序: 先发生的 → 后发生的
        3. v-结构: 如果 A - C - B 且 C 不在 sep_set(A,B)，则 A→C←B
        4. 其余按相关性方向
        """
        directed: List[Tuple[int, int]] = []
        undirected = set(skeleton)
        
        # 规则1: 先验边
        if prior_edges:
            for (s, t) in prior_edges:
                if (s, t) in undirected or (t, s) in undirected:
                    directed.append((s, t))
                    undirected.discard((s, t))
                    undirected.discard((t, s))
        
        # 规则2: 时间顺序
        if temporal_order:
            time_idx = {name: i for i, name in enumerate(temporal_order)}
            for (i, j) in list(undirected):
                name_i = f"var_{i}"
                name_j = f"var_{j}"
                ti = time_idx.get(name_i, i)
                tj = time_idx.get(name_j, j)
                if ti < tj:
                    directed.append((i, j))
                    undirected.discard((i, j))
                elif tj < ti:
                    directed.append((j, i))
                    undirected.discard((i, j))
        
        # 规则3: v-结构定向
        # 构建邻接表
        adj: Dict[int, Set[int]] = defaultdict(set)
        for (i, j) in undirected:
            adj[i].add(j)
            adj[j].add(i)
        
        v_structured = set()
        for c in adj:
            neighbors_c = sorted(adj[c])
            for idx_a in range(len(neighbors_c)):
                for idx_b in range(idx_a + 1, len(neighbors_c)):
                    a, b = neighbors_c[idx_a], neighbors_c[idx_b]
                    # a - c - b 且 a 和 b 不相邻
                    if b not in adj[a]:
                        # c 不在 sep_set(a, b) → v-结构 a→c←b
                        sep = sep_sets.get((a, b), set())
                        if c not in sep:
                            directed.append((a, c))
                            directed.append((b, c))
                            v_structured.add((a, c))
                            v_structured.add((b, c))
                            v_structured.add((c, a))
                            v_structured.add((c, b))
        
        # 剩余未定向的边按默认规则
        for (i, j) in list(undirected):
            if (i, j) not in v_structured and (j, i) not in v_structured:
                # 默认: 编号小的 → 编号大的
                directed.append((i, j))
        
        return directed


# ============================================================================
#  结构因果模型 (SCM) — 反事实推理 (M1.2)
# ============================================================================

class StructuralCausalModel:
    """结构因果模型
    
    每个节点的值为父节点的函数 + 噪声:
        X_i = f_i(parents(X_i)) + epsilon_i
    
    支持:
    - 观测预测 (prediction)
    - 干预计算 (do-calculus 近似)
    - 反事实查询 (abduction → action → prediction)
    """
    
    def __init__(self, graph: CausalGraph):
        self._graph = graph
        # 每个节点的结构方程: node_id -> (weights, bias)
        # X_i = sum(weight_j * X_j for j in parents) + bias + noise
        self._equations: Dict[str, Tuple[np.ndarray, float, float]] = {}
        # 噪声标准差
        self._noise_std: Dict[str, float] = {}
    
    def fit_from_data(
        self,
        data: np.ndarray,
        var_names: List[str],
        parent_map: Dict[str, List[str]]
    ) -> None:
        """从数据拟合结构方程
        
        Args:
            data: (n_samples, n_vars)
            var_names: 变量名
            parent_map: 每个变量的父节点列表
        """
        name_to_idx = {name: i for i, name in enumerate(var_names)}
        
        for var_name in var_names:
            parents = parent_map.get(var_name, [])
            var_idx = name_to_idx[var_name]
            
            if not parents:
                # 无父节点: X = mean(X) + noise
                mean_val = float(np.mean(data[:, var_idx]))
                noise = float(np.std(data[:, var_idx]))
                self._equations[var_name] = (np.array([]), mean_val, noise)
                self._noise_std[var_name] = max(noise, 1e-6)
                continue
            
            # 线性回归: X = W @ parents + bias
            parent_indices = [name_to_idx[p] for p in parents if p in name_to_idx]
            if not parent_indices:
                mean_val = float(np.mean(data[:, var_idx]))
                noise = float(np.std(data[:, var_idx]))
                self._equations[var_name] = (np.array([]), mean_val, noise)
                self._noise_std[var_name] = max(noise, 1e-6)
                continue
            
            X_parents = data[:, parent_indices]
            y = data[:, var_idx]
            
            # 最小二乘
            try:
                X_aug = np.column_stack([np.ones(len(y)), X_parents])
                beta = np.linalg.lstsq(X_aug, y, rcond=None)[0]
                bias = float(beta[0])
                weights = beta[1:]
                residuals = y - X_aug @ beta
                noise = float(np.std(residuals))
            except np.linalg.LinAlgError:
                bias = float(np.mean(y))
                weights = np.zeros(len(parent_indices))
                noise = float(np.std(y))
            
            self._equations[var_name] = (weights, bias, noise)
            self._noise_std[var_name] = max(noise, 1e-6)
    
    def predict(self, observations: Dict[str, float]) -> Dict[str, float]:
        """基于观测预测所有节点值"""
        topo_order = self._topological_order()
        values = dict(observations)
        
        for node_id in topo_order:
            if node_id in values:
                continue
            if node_id not in self._equations:
                continue
            
            weights, bias, _ = self._equations[node_id]
            parents = self._get_parent_names(node_id)
            
            if len(weights) == 0:
                values[node_id] = bias
            else:
                parent_vals = [values.get(p, 0.0) for p in parents]
                values[node_id] = float(np.dot(weights, parent_vals) + bias)
        
        return values
    
    def do_intervention(
        self,
        observations: Dict[str, float],
        intervention: Dict[str, float]
    ) -> Dict[str, float]:
        """do-算子: 干预某些节点为固定值，重新预测
        
        do(X=x) 等价于: 移除 X 的所有入边，设 X=x，然后前向传播
        """
        topo_order = self._topological_order()
        values = dict(observations)
        # 应用干预
        values.update(intervention)
        
        for node_id in topo_order:
            if node_id in intervention:
                continue  # 干预节点值固定
            if node_id not in self._equations:
                continue
            
            weights, bias, _ = self._equations[node_id]
            parents = self._get_parent_names(node_id)
            
            if len(weights) == 0:
                values[node_id] = bias
            else:
                parent_vals = [values.get(p, 0.0) for p in parents]
                values[node_id] = float(np.dot(weights, parent_vals) + bias)
        
        return values
    
    def counterfactual(
        self,
        observations: Dict[str, float],
        intervention: Dict[str, float],
        query_nodes: List[str]
    ) -> Dict[str, float]:
        """反事实查询: abduction → action → prediction
        
        1. Abduction: 从观测推断噪声项
        2. Action: 应用干预（修改结构方程）
        3. Prediction: 前向传播计算反事实值
        """
        # Step 1: Abduction — 推断每个节点的噪声
        topo_order = self._topological_order()
        predicted = {}
        noise_terms = {}
        
        for node_id in topo_order:
            if node_id not in self._equations:
                continue
            weights, bias, _ = self._equations[node_id]
            parents = self._get_parent_names(node_id)
            
            if len(weights) == 0:
                predicted[node_id] = bias
            else:
                parent_vals = [predicted.get(p, observations.get(p, 0.0))
                              for p in parents]
                predicted[node_id] = float(np.dot(weights, parent_vals) + bias)
            
            # 推断噪声
            observed_val = observations.get(node_id, predicted[node_id])
            noise_terms[node_id] = observed_val - predicted[node_id]
        
        # Step 2 & 3: Action + Prediction — 应用干预并前向传播
        cf_values = {}
        for node_id in topo_order:
            if node_id in intervention:
                cf_values[node_id] = intervention[node_id]
                continue
            
            if node_id not in self._equations:
                cf_values[node_id] = observations.get(node_id, 0.0)
                continue
            
            weights, bias, _ = self._equations[node_id]
            parents = self._get_parent_names(node_id)
            
            if len(weights) == 0:
                cf_values[node_id] = bias + noise_terms.get(node_id, 0.0)
            else:
                parent_vals = [cf_values.get(p, observations.get(p, 0.0))
                              for p in parents]
                cf_values[node_id] = float(
                    np.dot(weights, parent_vals) + bias + noise_terms.get(node_id, 0.0)
                )
        
        return {n: cf_values.get(n, 0.0) for n in query_nodes}
    
    def _topological_order(self) -> List[str]:
        """获取拓扑排序顺序"""
        in_degree = {}
        children_map: Dict[str, List[str]] = defaultdict(list)
        
        for node_id in self._equations:
            in_degree.setdefault(node_id, 0)
            parents = self._get_parent_names(node_id)
            for p in parents:
                if p in self._equations:
                    children_map[p].append(node_id)
                    in_degree[node_id] = in_degree.get(node_id, 0) + 1
        
        queue = [n for n, d in in_degree.items() if d == 0]
        result = []
        while queue:
            n = queue.pop(0)
            result.append(n)
            for c in children_map.get(n, []):
                in_degree[c] -= 1
                if in_degree[c] == 0:
                    queue.append(c)
        return result
    
    def _get_parent_names(self, node_id: str) -> List[str]:
        """获取节点的父节点名列表"""
        return sorted(self._graph.parents(node_id))


# ============================================================================
#  主引擎: CausalEngine
# ============================================================================

class CausalEngine:
    """跨引擎因果推断引擎
    
    整合因果发现、SCM、状态感知，提供:
    1. 自动因果发现 (从执行日志)
    2. 反事实推理 ("如果当时做了X...")
    3. 最优干预搜索
    4. 增量学习
    """
    
    DEFAULT_DATA_DIR = "data/causal_engine"
    
    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # 因果图
        self._graph = CausalGraph()
        # 结构因果模型
        self._scm: Optional[StructuralCausalModel] = None
        # 引擎状态感知
        self.observer = EngineStateObserver()
        # 因果发现算法
        self._discovery = CausalDiscovery()
        
        # 历史执行记录
        self._execution_log: List[ExecutionRecord] = []
        # 变量名映射
        self._var_names: List[str] = []
        # 数据矩阵
        self._data_matrix: Optional[np.ndarray] = None
        
        # 初始化先验因果图
        self._init_expert_prior()
        # 加载持久化数据
        self._load_state()
    
    # ----------------------------------------------------------------
    #  M1.1: 因果图自动发现
    # ----------------------------------------------------------------
    
    def _init_expert_prior(self) -> None:
        """初始化专家先验因果图"""
        # 创建所有涉及的节点
        known_nodes = set()
        for edge_def in EXPERT_PRIOR_EDGES:
            known_nodes.add(edge_def["source"])
            known_nodes.add(edge_def["target"])
        
        for node_id in known_nodes:
            engine = self._infer_engine(node_id)
            node_type = self._infer_node_type(node_id)
            self._graph.add_node(CausalNode(
                id=node_id,
                node_type=node_type,
                engine=engine,
                name=node_id
            ))
        
        # 添加先验边
        for edge_def in EXPERT_PRIOR_EDGES:
            self._graph.add_edge(CausalEdge(
                source=edge_def["source"],
                target=edge_def["target"],
                weight=edge_def["weight"],
                confidence=edge_def["confidence"],
                is_expert=True,
                sample_count=0,
                last_updated=time.time()
            ))
    
    def _infer_engine(self, node_id: str) -> EngineType:
        """从节点ID推断所属引擎"""
        nid = node_id.lower()
        if nid.startswith("ae") or "ae_" in nid:
            return EngineType.AE
        elif nid.startswith("davinci") or "davinci" in nid:
            return EngineType.DAVINCI
        elif nid.startswith("ffmpeg") or "ffmpeg" in nid:
            return EngineType.FFMPEG
        else:
            return EngineType.PIPELINE
    
    def _infer_node_type(self, node_id: str) -> NodeType:
        """从节点ID推断节点类型"""
        nid = node_id.lower()
        if "memory" in nid or "cpu" in nid or "db" in nid:
            return NodeType.ENGINE_STATE
        elif "param" in nid:
            return NodeType.PARAMETER
        elif "quality" in nid or "output" in nid:
            return NodeType.OUTPUT_QUALITY
        else:
            return NodeType.ENGINE_STAGE
    
    async def discover_causal_structure(
        self,
        execution_logs: List[ExecutionRecord]
    ) -> CausalGraph:
        """从历史执行记录中发现因果关系
        
        流程:
        1. 将执行记录转换为数值矩阵
        2. PC 算法发现因果骨架
        3. 结合先验知识定向边
        4. 更新因果图
        """
        if len(execution_logs) < 5:
            logger.info(f"[CausalEngine] 样本不足 ({len(execution_logs)} < 5), 使用先验因果图")
            return self._graph
        
        # 合并执行日志（不覆盖已有记录）
        existing_ids = {r.run_id for r in self._execution_log}
        for rec in execution_logs:
            if rec.run_id not in existing_ids:
                self._execution_log.append(rec)
        
        # Step 1: 转换为数值矩阵
        data, var_names = self._logs_to_matrix(execution_logs)
        self._var_names = var_names
        self._data_matrix = data
        
        if data.shape[0] < 5 or data.shape[1] < 2:
            logger.info("[CausalEngine] 矩阵维度不足, 使用先验因果图")
            return self._graph
        
        # Step 2: PC 算法发现骨架
        skeleton, sep_sets = self._discovery.discover_skeleton(data, var_names)
        
        # Step 3: 定向（结合先验）
        prior_edges = []
        for edge in self._graph.edges:
            if edge.is_expert:
                s_idx = var_names.index(edge.source) if edge.source in var_names else -1
                t_idx = var_names.index(edge.target) if edge.target in var_names else -1
                if s_idx >= 0 and t_idx >= 0:
                    prior_edges.append((s_idx, t_idx))
        
        directed = self._discovery.orient_edges(
            skeleton, sep_sets,
            prior_edges=prior_edges,
            temporal_order=var_names
        )
        
        # Step 4: 更新因果图
        # 确保所有变量都有对应节点
        for name in var_names:
            if name not in self._graph.nodes:
                engine = self._infer_engine(name)
                self._graph.add_node(CausalNode(
                    id=name, node_type=self._infer_node_type(name),
                    engine=engine, name=name
                ))
        
        # 更新/添加边
        for (s_idx, t_idx) in directed:
            s_name = var_names[s_idx]
            t_name = var_names[t_idx]
            
            existing = self._graph.get_edge(s_name, t_name)
            if existing:
                # 增量更新: 贝叶斯后验
                existing.sample_count += 1
                existing.confidence = min(1.0, existing.confidence + 0.05)
                existing.last_updated = time.time()
            else:
                # 新边: 基于相关性计算权重
                if data.shape[0] > 2:
                    corr = np.corrcoef(data[:, s_idx], data[:, t_idx])[0, 1]
                    weight = float(np.clip(corr, -1, 1))
                else:
                    weight = 0.3
                self._graph.add_edge(CausalEdge(
                    source=s_name, target=t_name,
                    weight=weight, confidence=0.5,
                    is_expert=False, sample_count=1,
                    last_updated=time.time()
                ))
        
        # 重建 SCM
        self._rebuild_scm(data, var_names)
        
        logger.info(f"[CausalEngine] 因果发现完成: {len(self._graph.nodes)} 节点, "
                    f"{len(self._graph.edges)} 边")
        return self._graph
    
    def _logs_to_matrix(
        self, logs: List[ExecutionRecord]
    ) -> Tuple[np.ndarray, List[str]]:
        """将执行记录转换为数值矩阵
        
        特征提取:
        - 每个阶段: success(0/1), duration, error_count
        - 引擎状态: memory_pct, cpu_pct
        - 输出质量: quality_score
        """
        # 收集所有变量名
        all_vars = set()
        for log in logs:
            for stage_name in log.stages:
                all_vars.add(f"{stage_name}_success")
                all_vars.add(f"{stage_name}_duration")
            for engine_name in log.engine_states:
                for metric_name in log.engine_states[engine_name]:
                    all_vars.add(f"{engine_name}_{metric_name}")
            all_vars.add("output_quality")
        
        var_names = sorted(all_vars)
        var_to_idx = {v: i for i, v in enumerate(var_names)}
        
        n = len(logs)
        data = np.zeros((n, len(var_names)))
        
        for i, log in enumerate(logs):
            for stage_name, stage_data in log.stages.items():
                s_idx = var_to_idx.get(f"{stage_name}_success")
                d_idx = var_to_idx.get(f"{stage_name}_duration")
                if s_idx is not None:
                    data[i, s_idx] = 1.0 if stage_data.get("success", False) else 0.0
                if d_idx is not None:
                    data[i, d_idx] = stage_data.get("duration", 0.0)
            
            for engine_name, metrics in log.engine_states.items():
                for metric_name, value in metrics.items():
                    v_idx = var_to_idx.get(f"{engine_name}_{metric_name}")
                    if v_idx is not None:
                        data[i, v_idx] = value
            
            oq_idx = var_to_idx.get("output_quality")
            if oq_idx is not None:
                data[i, oq_idx] = log.output_quality
        
        return data, var_names
    
    def _rebuild_scm(self, data: np.ndarray, var_names: List[str]) -> None:
        """重建结构因果模型"""
        parent_map: Dict[str, List[str]] = {v: [] for v in var_names}
        
        for edge in self._graph.edges:
            if edge.source in parent_map and edge.target in var_names:
                parent_map[edge.target].append(edge.source)
        
        self._scm = StructuralCausalModel(self._graph)
        self._scm.fit_from_data(data, var_names, parent_map)
    
    # ----------------------------------------------------------------
    #  M1.2: 反事实推理
    # ----------------------------------------------------------------
    
    async def counterfactual_query(
        self,
        observed_failure: EngineFailure,
        intervention: Intervention,
        context: Optional[Dict[str, Any]] = None
    ) -> CounterfactualResult:
        """反事实查询: 如果当时做了X，结果会怎样？
        
        Args:
            observed_failure: 实际观测到的故障
            intervention: 假设的干预动作
            context: 额外上下文
            
        Returns:
            CounterfactualResult
        """
        if not self._scm:
            return CounterfactualResult(
                observed=observed_failure.error_msg,
                counterfactual="数据不足，无法推断",
                causal_effect=0.0,
                confidence=0.0,
                explanation="需要先积累足够的执行记录来构建因果模型"
            )
        
        # 构建观测向量
        observations = self._failure_to_observations(observed_failure, context)
        
        # 确定干预目标值
        intervention_values = self._intervention_to_values(intervention)
        
        # 确定查询节点（干预目标的所有后代）
        query_nodes = sorted(self._graph.descendants(intervention.target_node))
        if not query_nodes:
            query_nodes = [intervention.target_node]
        
        # SCM 反事实推理
        cf_values = self._scm.counterfactual(
            observations, intervention_values, query_nodes
        )
        
        # 计算因果效应
        observed_vals = self._scm.predict(observations)
        
        # 综合效应
        effects = []
        for node_id in query_nodes:
            obs_val = observed_vals.get(node_id, 0.0)
            cf_val = cf_values.get(node_id, 0.0)
            effects.append(cf_val - obs_val)
        
        avg_effect = float(np.mean(effects)) if effects else 0.0
        
        # 置信度基于样本数和边置信度
        sample_count = min(e.sample_count for e in self._graph.edges) if self._graph.edges else 0
        confidence = min(1.0, sample_count / 20.0) * 0.8
        
        # 生成解释
        explanation = self._generate_cf_explanation(
            observed_failure, intervention, cf_values, avg_effect
        )
        
        return CounterfactualResult(
            observed=observed_failure.error_msg,
            counterfactual=f"干预后预期结果: {cf_values}",
            causal_effect=avg_effect,
            confidence=confidence,
            explanation=explanation,
            alternative_outcomes=[
                {"node": n, "observed": observed_vals.get(n, 0.0),
                 "counterfactual": cf_values.get(n, 0.0)}
                for n in query_nodes
            ]
        )
    
    def _failure_to_observations(
        self, failure: EngineFailure, context: Optional[Dict] = None
    ) -> Dict[str, float]:
        """将故障记录转换为SCM观测向量"""
        obs: Dict[str, float] = {}
        
        # 故障阶段
        stage_key = f"{failure.stage}_success"
        obs[stage_key] = 0.0  # 失败
        dur_key = f"{failure.stage}_duration"
        obs[dur_key] = 0.0  # 失败时耗时为0
        
        # 引擎状态
        for engine_name, metrics in self.observer.snapshot().items():
            for metric_name, value in metrics.items():
                obs[f"{engine_name}_{metric_name}"] = value
        
        # 上游输出
        for key, value in failure.upstream_outputs.items():
            if isinstance(value, (int, float)):
                obs[key] = float(value)
        
        # 上下文
        if context:
            for key, value in context.items():
                if isinstance(value, (int, float)):
                    obs[key] = float(value)
        
        return obs
    
    def _intervention_to_values(
        self, intervention: Intervention
    ) -> Dict[str, float]:
        """将干预动作转换为SCM干预值"""
        values: Dict[str, float] = {}
        
        if intervention.action == "fix_param":
            # 参数修复: 将参数节点设为修复后的值
            for k, v in intervention.params.items():
                if isinstance(v, (int, float)):
                    values[k] = float(v)
                else:
                    values[intervention.target_node] = 1.0  # 修复成功
        elif intervention.action == "insert_transcode":
            values[intervention.target_node] = 1.0  # 转码成功
        elif intervention.action == "skip_stage":
            values[intervention.target_node] = 0.0  # 跳过
        elif intervention.action == "retry":
            values[intervention.target_node] = 1.0  # 重试成功
        
        return values
    
    def _generate_cf_explanation(
        self,
        failure: EngineFailure,
        intervention: Intervention,
        cf_values: Dict[str, float],
        effect: float
    ) -> str:
        """生成反事实解释"""
        direction = "改善" if effect > 0 else "恶化"
        return (
            f"在 {failure.engine.value}/{failure.stage} 发生故障后，"
            f"如果执行干预 [{intervention.description or intervention.action}] "
            f"于 {intervention.target_node}，预期会{direction} "
            f"（效应量: {effect:+.3f}）。"
        )
    
    # ----------------------------------------------------------------
    #  M1.3: 最优干预搜索
    # ----------------------------------------------------------------
    
    async def optimal_intervention(
        self,
        current_state: Dict[str, Any],
        target_outcome: Dict[str, float],
        max_interventions: int = 5
    ) -> InterventionPlan:
        """给定当前状态和期望结果，计算最优干预策略
        
        策略:
        1. 识别当前故障节点
        2. 枚举所有可能的干预点
        3. 对每个干预点计算期望效果
        4. 选择效果/成本比最高的干预组合
        """
        if not self._scm:
            return InterventionPlan(
                interventions=[], expected_success_rate=0.0,
                reasoning="因果模型尚未构建"
            )
        
        # 识别故障节点
        failure_nodes = []
        for key, value in current_state.items():
            if isinstance(value, (int, float)) and value < 0.5 and "success" in key:
                failure_nodes.append(key.replace("_success", ""))
        
        if not failure_nodes:
            return InterventionPlan(
                interventions=[], expected_success_rate=1.0,
                reasoning="当前无故障节点"
            )
        
        # 枚举可能的干预
        candidate_interventions: List[Tuple[Intervention, float]] = []
        
        for fail_node in failure_nodes:
            # 干预策略1: 直接修复故障节点
            candidate_interventions.append((
                Intervention(
                    target_node=fail_node,
                    action="retry",
                    description=f"重试 {fail_node}"
                ),
                10.0  # 成本: 10秒
            ))
            
            # 干预策略2: 修复上游节点
            ancestors = self._graph.ancestors(fail_node)
            for anc in ancestors:
                edge = self._graph.get_edge(anc, fail_node)
                if edge and abs(edge.weight) > 0.3:
                    candidate_interventions.append((
                        Intervention(
                            target_node=anc,
                            action="fix_param",
                            description=f"修复上游 {anc} 以解决 {fail_node}"
                        ),
                        20.0
                    ))
            
            # 干预策略3: 在故障节点和下游之间插入转码
            descendants = self._graph.descendants(fail_node)
            for desc in descendants:
                candidate_interventions.append((
                    Intervention(
                        target_node=fail_node,
                        action="insert_transcode",
                        params={"target": desc},
                        description=f"在 {fail_node} → {desc} 间插入转码"
                    ),
                    30.0
                ))
        
        # 评估每个干预的期望效果
        scored: List[Tuple[Intervention, float, float]] = []  # (intervention, score, cost)
        
        for intervention, cost in candidate_interventions[:max_interventions * 2]:
            obs = {k: float(v) for k, v in current_state.items()
                   if isinstance(v, (int, float))}
            int_values = self._intervention_to_values(intervention)
            
            # 预测干预后结果
            cf_values = self._scm.do_intervention(obs, int_values)
            
            # 计算与目标的距离改善
            current_quality = obs.get("output_quality", 0.0)
            cf_quality = cf_values.get("output_quality", current_quality)
            improvement = cf_quality - current_quality
            
            score = improvement / max(cost, 1.0)  # 效果/成本比
            scored.append((intervention, score, cost))
        
        # 按效果/成本比排序
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # 选择 top-K 不重叠的干预
        selected: List[Intervention] = []
        total_cost = 0.0
        seen_targets: Set[str] = set()
        
        for intervention, score, cost in scored:
            if len(selected) >= max_interventions:
                break
            if intervention.target_node in seen_targets:
                continue
            selected.append(intervention)
            seen_targets.add(intervention.target_node)
            total_cost += cost
        
        # 计算期望成功率
        avg_score = np.mean([s for _, s, _ in scored[:len(selected)]]) if scored else 0.0
        expected_success = min(0.95, 0.5 + avg_score * 0.3)
        
        return InterventionPlan(
            interventions=selected,
            expected_success_rate=expected_success,
            expected_quality_impact=avg_score,
            estimated_cost=total_cost,
            reasoning=f"从 {len(candidate_interventions)} 个候选干预中选出 "
                      f"{len(selected)} 个最优干预"
        )
    
    # ----------------------------------------------------------------
    #  M1.6: 持久化与增量学习
    # ----------------------------------------------------------------
    
    def record_execution(self, record: ExecutionRecord) -> None:
        """记录一次管线执行"""
        self._execution_log.append(record)
        
        # 增量更新: 每 5 次执行触发一次因果图更新
        if len(self._execution_log) % 5 == 0 and len(self._execution_log) >= 5:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 在已有事件循环中安排任务
                    asyncio.ensure_future(
                        self.discover_causal_structure(self._execution_log)
                    )
                else:
                    loop.run_until_complete(
                        self.discover_causal_structure(self._execution_log)
                    )
            except RuntimeError:
                pass  # 非关键路径，静默处理
        
        self._save_state()
    
    def _save_state(self) -> None:
        """持久化因果图和执行日志"""
        try:
            # 保存因果图
            graph_path = self._data_dir / "causal_graph.json"
            with open(graph_path, "w", encoding="utf-8") as f:
                json.dump(self._graph.to_dict(), f, ensure_ascii=False, indent=2)
            
            # 保存执行日志摘要（避免文件过大）
            log_path = self._data_dir / "execution_log.json"
            log_summary = [
                {
                    "run_id": r.run_id,
                    "timestamp": r.timestamp,
                    "stages": r.stages,
                    "success": r.success,
                    "output_quality": r.output_quality
                }
                for r in self._execution_log[-100:]  # 只保留最近100条
            ]
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(log_summary, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[CausalEngine] Save state failed: {e}")
    
    def _load_state(self) -> None:
        """加载持久化状态"""
        try:
            graph_path = self._data_dir / "causal_graph.json"
            if graph_path.exists():
                with open(graph_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                loaded_graph = CausalGraph.from_dict(data)
                # 合并: 保留先验边 + 加载数据驱动边
                for edge in loaded_graph.edges:
                    if not edge.is_expert:
                        existing = self._graph.get_edge(edge.source, edge.target)
                        if not existing:
                            self._graph.add_edge(edge)
                # 添加新节点
                for nid, node in loaded_graph.nodes.items():
                    if nid not in self._graph.nodes:
                        self._graph.add_node(node)
            
            # 加载执行日志
            log_path = self._data_dir / "execution_log.json"
            if log_path.exists():
                with open(log_path, "r", encoding="utf-8") as f:
                    log_data = json.load(f)
                for entry in log_data:
                    rec = ExecutionRecord(
                        run_id=entry.get("run_id", ""),
                        timestamp=entry.get("timestamp", ""),
                        stages=entry.get("stages", {}),
                        success=entry.get("success", False),
                        output_quality=entry.get("output_quality", 0.0),
                    )
                    self._execution_log.append(rec)
        except Exception as e:
            logger.warning(f"[CausalEngine] Load state failed: {e}")
    
    # ----------------------------------------------------------------
    #  统计与诊断
    # ----------------------------------------------------------------
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取引擎统计信息"""
        edges = self._graph.edges
        expert_edges = [e for e in edges if e.is_expert]
        data_edges = [e for e in edges if not e.is_expert]
        
        return {
            "node_count": len(self._graph.nodes),
            "edge_count": len(edges),
            "expert_edges": len(expert_edges),
            "data_driven_edges": len(data_edges),
            "execution_log_size": len(self._execution_log),
            "scm_built": self._scm is not None,
            "avg_confidence": float(np.mean([e.confidence for e in edges])) if edges else 0.0,
            "avg_weight": float(np.mean([abs(e.weight) for e in edges])) if edges else 0.0,
        }
    
    def get_causal_graph(self) -> CausalGraph:
        """获取当前因果图"""
        return self._graph
    
    def get_scm(self) -> Optional[StructuralCausalModel]:
        """获取当前SCM"""
        return self._scm

    # ----------------------------------------------------------------
    #  P3.2: 反事实推理与根因链分析
    # ----------------------------------------------------------------

    def counterfactual_analysis(
        self,
        failure_id: str,
        alternative_engine: str,
    ) -> CounterfactualResult:
        """反事实推理: "如果当时用 X 引擎会怎样？"
        
        基于 EngineRegistry 中各引擎的历史成功率与因果图，估算:
        1. 如果当时改用 alternative_engine，故障节点的预期成功率
        2. 反事实场景下的输出质量
        3. 因果效应量（实际失败 - 反事实成功 = 改善空间）
        
        推理逻辑（公式）:
            P(成功 | do(engine=X)) ≈ SR_X(stage) × AdjustFactor
            其中 SR_X(stage) 是引擎 X 在该 stage 的历史成功率
            AdjustFactor 因果调整因子来自因果图边权重的乘积
            
        若数据不足（无 EngineRegistry / 无历史 / 无 SCM），返回低置信度结果。
        
        Args:
            failure_id: 故障记录 ID（用于从执行日志中查找原始故障）
            alternative_engine: 假设使用的替代引擎名 (ae / davinci / ffmpeg / moviepy ...)
            
        Returns:
            CounterfactualResult，含 alternative_engine / failure_id 等扩展字段
        """
        # 查找故障记录
        failure_record = self._find_failure_record(failure_id)
        
        if failure_record is None:
            return CounterfactualResult(
                observed=f"failure_id={failure_id} not found",
                counterfactual="无法推断",
                causal_effect=0.0,
                confidence=0.0,
                explanation="未找到对应的故障记录，无法进行反事实推理",
                alternative_engine=alternative_engine,
                failure_id=failure_id,
            )
        
        # 识别故障节点和 stage
        fail_stage = failure_record.get("stage", "execute")
        fail_engine = failure_record.get("engine", "ae")
        fail_node = f"{fail_engine}_{fail_stage}"
        
        # 从 EngineRegistry 获取替代引擎的历史成功率
        alt_success_rate = self._estimate_engine_success_rate(alternative_engine, fail_stage)
        orig_success_rate = self._estimate_engine_success_rate(fail_engine, fail_stage)
        
        # 因果调整: 通过因果图计算反事实传播效应
        # 若 SCM 可用，用 do_intervention 估算
        cf_quality = 0.0
        causal_effect = 0.0
        historical_support = 0
        
        if self._scm is not None:
            # 构建"反事实场景": 将故障节点设置为成功(1.0)
            try:
                obs = {
                    f"{fail_stage}_success": 0.0,
                    "output_quality": failure_record.get("quality", 0.0),
                }
                # 加入引擎状态观测
                for k, v in failure_record.get("engine_states", {}).items():
                    if isinstance(v, (int, float)):
                        obs[k] = float(v)
                
                intervention = {f"{fail_stage}_success": 1.0}
                # 反事实查询: 如果故障节点成功，下游会怎样
                query_nodes = [n for n in self._graph.descendants(fail_node)
                               if "quality" in n or "success" in n]
                if not query_nodes:
                    query_nodes = ["output_quality"]
                
                cf_values = self._scm.counterfactual(obs, intervention, query_nodes)
                cf_quality = float(cf_values.get("output_quality", 0.0))
                
                # 因果效应 = 反事实质量 - 实际质量
                actual_quality = failure_record.get("quality", 0.0)
                causal_effect = float(cf_quality - actual_quality)
                
                # 历史支撑: 因果图中相关边的样本数总和
                relevant_edges = [
                    e for e in self._graph.edges
                    if e.source == fail_node or e.target == fail_node
                ]
                historical_support = sum(e.sample_count for e in relevant_edges)
            except Exception as e:
                logger.debug(f"[CausalEngine/P3.2] SCM counterfactual failed: {e}")
        
        # 如果 SCM 不可用，用成功率差异估算
        if causal_effect == 0.0 and alt_success_rate > 0:
            # 简化估算: 因果效应 ≈ (替代引擎成功率 - 原引擎成功率) * 100
            causal_effect = float((alt_success_rate - orig_success_rate) * 100.0)
            cf_quality = float(failure_record.get("quality", 50.0) + causal_effect)
            cf_quality = float(np.clip(cf_quality, 0.0, 100.0))
        
        # 置信度: 基于历史支撑样本数 + 替代引擎数据量
        alt_data_count = self._count_engine_history(alternative_engine, fail_stage)
        confidence = float(np.clip(
            0.3 + 0.4 * min(1.0, historical_support / 10.0)
            + 0.3 * min(1.0, alt_data_count / 20.0),
            0.0, 1.0
        ))
        
        # 生成解释
        if alt_success_rate > orig_success_rate:
            direction = "改善"
            improvement = (alt_success_rate - orig_success_rate) * 100
        elif alt_success_rate < orig_success_rate:
            direction = "恶化"
            improvement = (orig_success_rate - alt_success_rate) * 100
        else:
            direction = "无明显变化"
            improvement = 0.0
        
        explanation = (
            f"故障 {failure_id} 发生在 {fail_engine}/{fail_stage}。"
            f"如果当时改用 '{alternative_engine}' 引擎，"
            f"基于历史数据（替代引擎成功率={alt_success_rate:.1%}, "
            f"原引擎成功率={orig_success_rate:.1%}），"
            f"预期结果会{direction}（成功率差异 {improvement:.1f}%），"
            f"质量分变化 {causal_effect:+.2f}。"
            f"反事实估算质量={cf_quality:.1f}, 历史支撑样本={historical_support}。"
        )
        
        result = CounterfactualResult(
            observed=f"{fail_engine}/{fail_stage} 故障: {failure_record.get('error', 'unknown')}",
            counterfactual=f"使用 {alternative_engine} 替代后预期成功率={alt_success_rate:.1%}, 质量={cf_quality:.1f}",
            causal_effect=causal_effect,
            confidence=confidence,
            explanation=explanation,
            alternative_outcomes=[
                {"engine": alternative_engine, "stage": fail_stage,
                 "estimated_success_rate": alt_success_rate,
                 "estimated_quality": cf_quality},
            ],
            alternative_engine=alternative_engine,
            failure_id=failure_id,
            estimated_success_rate=alt_success_rate,
            estimated_quality=cf_quality,
            historical_support=historical_support,
        )
        
        # 持久化到 data/causal_engine/counterfactuals.json
        self._persist_counterfactual(result)
        
        return result
    
    def root_cause_chain(
        self,
        failure_id: str,
        max_hops: int = 3,
    ) -> List[CausalLink]:
        """多跳因果链推理: 找出故障的根因链
        
        从故障节点出发，沿着因果图的反向边（parents 方向）追溯，
        直到达到根因（无父节点的节点）或达到 max_hops 跳数限制。
        
        推理规则:
        - 选择权重 |w| 最大的父节点作为下一跳（因果效应最强）
        - 边的 confidence < 0.3 时停止（不可靠的因果链）
        - 避免环路（已访问的节点不再访问）
        - 默认最多 3 跳（避免过长链路降低可解释性）
        
        Args:
            failure_id: 故障记录 ID
            max_hops: 最大跳数（1-5），默认 3
            
        Returns:
            List[CausalLink]，从故障节点到根因的因果链
            （第一个元素是故障节点的直接父节点，最后一个是最深根因）
        """
        max_hops = int(np.clip(max_hops, 1, 5))
        
        failure_record = self._find_failure_record(failure_id)
        if failure_record is None:
            return []
        
        fail_stage = failure_record.get("stage", "execute")
        fail_engine = failure_record.get("engine", "ae")
        start_node = f"{fail_engine}_{fail_stage}"
        
        # 若起始节点不在图中，尝试只取 stage 名
        if start_node not in self._graph.nodes:
            candidates = [n for n in self._graph.nodes
                          if fail_stage in n or fail_engine in n]
            if candidates:
                start_node = candidates[0]
            else:
                return []
        
        chain: List[CausalLink] = []
        visited: Set[str] = {start_node}
        current = start_node
        
        for hop in range(max_hops):
            parents = self._graph.parents(current)
            # 排除已访问节点
            unvisited_parents = [p for p in parents if p not in visited]
            if not unvisited_parents:
                break
            
            # 选择 |权重| 最大的父节点
            best_parent = None
            best_edge = None
            best_abs_weight = -1.0
            for p in unvisited_parents:
                edge = self._graph.get_edge(p, current)
                if edge is None:
                    continue
                if edge.confidence < 0.3:
                    continue  # 跳过低置信度边
                if abs(edge.weight) > best_abs_weight:
                    best_abs_weight = abs(edge.weight)
                    best_parent = p
                    best_edge = edge
            
            if best_parent is None or best_edge is None:
                break
            
            # 生成解释
            effect_direction = "促进" if best_edge.weight > 0 else "抑制"
            chain.append(CausalLink(
                source=best_parent,
                target=current,
                weight=best_edge.weight,
                confidence=best_edge.confidence,
                explanation=(
                    f"第{hop + 1}跳: {best_parent} {effect_direction} {current} "
                    f"(权重={best_edge.weight:+.2f}, 置信度={best_edge.confidence:.2f}, "
                    f"专家先验={'是' if best_edge.is_expert else '否'}, "
                    f"样本数={best_edge.sample_count})"
                ),
            ))
            
            visited.add(best_parent)
            current = best_parent
        
        return chain
    
    def _find_failure_record(self, failure_id: str) -> Optional[Dict[str, Any]]:
        """从执行日志中查找故障记录
        
        Args:
            failure_id: 故障 ID（通常是 run_id 或 stage:run_id 格式）
            
        Returns:
            故障记录字典，包含 engine/stage/error/quality/engine_states 等字段；
            未找到返回 None
        """
        # 直接按 run_id 匹配
        for rec in self._execution_log:
            if rec.run_id == failure_id:
                return self._record_to_failure_dict(rec)
        
        # 兼容 stage:run_id 格式
        if ":" in failure_id:
            stage_part, run_part = failure_id.split(":", 1)
            for rec in self._execution_log:
                if rec.run_id == run_part:
                    fd = self._record_to_failure_dict(rec)
                    fd["stage"] = stage_part
                    return fd
        
        # 尝试在阶段数据中查找失败阶段
        for rec in self._execution_log:
            for stage_name, stage_data in rec.stages.items():
                if not stage_data.get("success", True):
                    # 用 run_id 作为 failure_id 的代理
                    if rec.run_id == failure_id or stage_name == failure_id:
                        fd = self._record_to_failure_dict(rec)
                        fd["stage"] = stage_name
                        return fd
        
        return None
    
    def _record_to_failure_dict(self, rec: "ExecutionRecord") -> Dict[str, Any]:
        """将 ExecutionRecord 转换为故障分析用的字典"""
        # 找到失败的阶段
        fail_stage = "execute"
        fail_engine = "pipeline"
        error_msg = "unknown"
        for stage_name, stage_data in rec.stages.items():
            if not stage_data.get("success", True):
                fail_stage = stage_name
                fail_engine = stage_data.get("engine", "pipeline")
                error_msg = stage_data.get("error", "unknown")
                break
        
        return {
            "run_id": rec.run_id,
            "stage": fail_stage,
            "engine": fail_engine,
            "error": error_msg,
            "quality": rec.output_quality,
            "engine_states": dict(rec.engine_states) if rec.engine_states else {},
            "timestamp": rec.timestamp,
        }
    
    def _estimate_engine_success_rate(
        self, engine_name: str, stage: str
    ) -> float:
        """估算指定引擎在指定 stage 的历史成功率
        
        优先从 EngineRegistry 获取；不可用时回退到专家先验。
        
        Args:
            engine_name: 引擎名
            stage: 阶段名
            
        Returns:
            成功率 [0, 1]
        """
        # 默认成功率（基于专家先验）
        defaults = {
            "ae": 0.75, "davinci": 0.85, "ffmpeg": 0.90,
            "moviepy": 0.85, "topaz": 0.80, "blender": 0.70,
            "pipeline": 0.80,
        }
        base = defaults.get(engine_name.lower(), 0.75)
        
        # 尝试从 EngineRegistry 获取
        try:
            from core.engine_registry import get_engine_registry
            registry = get_engine_registry()
            stats = registry.get_statistics(engine_name)
            if stats and stats.get("total", 0) > 0:
                return float(stats.get("success_rate", base))
        except Exception as e:
            logger.debug(f"[CausalEngine/P3.2] registry lookup failed: {e}")
        
        return base
    
    def _count_engine_history(self, engine_name: str, stage: str) -> int:
        """统计指定引擎在指定 stage 的历史执行次数"""
        try:
            from core.engine_registry import get_engine_registry
            registry = get_engine_registry()
            stats = registry.get_statistics(engine_name)
            if stats and "total" in stats:
                return int(stats["total"])
        except Exception:
            pass
        return 0
    
    def _persist_counterfactual(self, result: CounterfactualResult) -> None:
        """持久化反事实分析结果到 data/causal_engine/counterfactuals.json
        
        保留最近 100 条记录，避免文件无限增长。
        """
        try:
            cf_path = self._data_dir / "counterfactuals.json"
            existing: List[Dict[str, Any]] = []
            if cf_path.exists():
                try:
                    with open(cf_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, list):
                            existing = loaded
                        elif isinstance(loaded, dict) and "records" in loaded:
                            existing = loaded["records"]
                except Exception:
                    existing = []
            
            existing.append({
                "failure_id": result.failure_id,
                "alternative_engine": result.alternative_engine,
                "observed": result.observed,
                "counterfactual": result.counterfactual,
                "causal_effect": result.causal_effect,
                "confidence": result.confidence,
                "estimated_success_rate": result.estimated_success_rate,
                "estimated_quality": result.estimated_quality,
                "historical_support": result.historical_support,
                "explanation": result.explanation,
                "timestamp": time.time(),
            })
            
            # 保留最近 100 条
            existing = existing[-100:]
            
            with open(cf_path, "w", encoding="utf-8") as f:
                json.dump({"records": existing}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[CausalEngine/P3.2] persist counterfactual failed: {e}")


# ============================================================================
#  全局单例
# ============================================================================

_global_engine: Optional[CausalEngine] = None


def get_causal_engine(data_dir: str = CausalEngine.DEFAULT_DATA_DIR) -> CausalEngine:
    """获取全局因果引擎单例"""
    global _global_engine
    if _global_engine is None:
        _global_engine = CausalEngine(data_dir)
    return _global_engine


# ============================================================================
#  工具函数
# ============================================================================

def _norm_cdf(x: float) -> float:
    """标准正态分布 CDF 近似"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _combinations(items: List[int], k: int):
    """生成组合（不依赖 itertools 的简单实现）"""
    if k == 0:
        yield ()
        return
    if len(items) < k:
        return
    for i in range(len(items) - k + 1):
        first = items[i]
        for rest in _combinations(items[i + 1:], k - 1):
            yield (first,) + rest
