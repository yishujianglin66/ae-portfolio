#!/usr/bin/env python3
"""
Phase 4 - 意图路由决策器 (Python 版)

核心职责：
  1. 根据用户输入，决定任务流向
  2. 识别混合任务（如"扣人像后加发光"），拆分为 AE + Silhouette 子任务
  3. 提供降级策略（Silhouette 不可用时回退到 AE 原生工具）

路由类型：
  ae_only         → 纯 AE 效果/动画/图层操作
  silhouette_only → 纯 Silhouette roto/track/paint
  hybrid          → Silhouette 前置 + AE 后置
  unknown         → 无法识别，需追问
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# 混合任务拆分关键词
# ---------------------------------------------------------------------------

# 连接词，表示"先做A再做B"
HYBRID_CONNECTORS: List[re.Pattern] = [
    re.compile(r"然后", re.IGNORECASE),
    re.compile(r"之后再?", re.IGNORECASE),
    re.compile(r"接着", re.IGNORECASE),
    re.compile(r"完后", re.IGNORECASE),
    re.compile(r"最后", re.IGNORECASE),
    re.compile(r"然后加", re.IGNORECASE),
    re.compile(r"再加", re.IGNORECASE),
    re.compile(r"同时加", re.IGNORECASE),
    re.compile(r"并加", re.IGNORECASE),
    re.compile(r"后加", re.IGNORECASE),
    re.compile(r"后添加", re.IGNORECASE),
    re.compile(r"后做", re.IGNORECASE),
]

# Silhouette 相关关键词
SILHOUETTE_KEYWORDS: List[re.Pattern] = [
    re.compile(r"(?:扣|抠|遮罩|蒙版|mask|roto)", re.IGNORECASE),
    re.compile(r"(?:跟踪|追踪|track)", re.IGNORECASE),
    re.compile(r"(?:修|擦|paint|修复|去除|擦除)", re.IGNORECASE),
    re.compile(r"(?:silhouette)", re.IGNORECASE),
]

# AE 效果关键词
AE_EFFECT_KEYWORDS: List[re.Pattern] = [
    re.compile(r"(?:发光|辉光|glow|霓虹)", re.IGNORECASE),
    re.compile(r"(?:模糊|blur|高斯)", re.IGNORECASE),
    re.compile(r"(?:粒子|particle)", re.IGNORECASE),
    re.compile(r"(?:噪波|noise|分形)", re.IGNORECASE),
    re.compile(r"(?:渐变|ramp|gradient)", re.IGNORECASE),
    re.compile(r"(?:调色|color|lut|色调)", re.IGNORECASE),
    re.compile(r"(?:扭曲|distort|变形|warp)", re.IGNORECASE),
    re.compile(r"(?:阴影|shadow|投影)", re.IGNORECASE),
    re.compile(r"(?:动画|anim|弹入|淡入|滑入|缩放|旋转)", re.IGNORECASE),
    # 亮度/对比度调整类（匹配 ADBE Brightness & Contrast 2）
    re.compile(r"(?:亮度|对比度|bright|contrast|调亮|调暗|变亮|变暗)",
               re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class TaskRoute:
    """路由结果"""
    type: str  # ae_only | silhouette_only | hybrid | unknown
    ae_operations: List[Dict] = field(default_factory=list)
    silhouette_operations: List[Dict] = field(default_factory=list)
    execution_order: List[str] = field(default_factory=list)
    fallback: Optional[Dict] = None
    reason: str = ""
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# 降级策略映射
# ---------------------------------------------------------------------------

# Silhouette 任务类型 → 降级到 AE 原生操作的映射
FALLBACK_MAP: Dict[str, Dict] = {
    "roto": {
        "condition": "Silhouette 不可用或执行失败",
        "ae_fallback_ops": [
            {
                "op": "addEffect",
                "matchName": "ADBE Mask",
                "effectName": "AE 原生遮罩",
                "layerRef": "selected",
                "settings": {"maskPath": "手动绘制"},
            }
        ],
        "message": "降级到 AE 原生 Mask 工具（精度降低，需手动绘制）",
    },
    "track": {
        "condition": "Silhouette 不可用或执行失败",
        "ae_fallback_ops": [
            {
                "op": "addEffect",
                "matchName": "ADBE Tracker",
                "effectName": "AE 原生跟踪器",
                "layerRef": "selected",
                "settings": {"trackType": "point"},
            }
        ],
        "message": "降级到 AE 原生跟踪器（跟踪精度降低）",
    },
    "paint": {
        "condition": "Silhouette 不可用或执行失败",
        "ae_fallback_ops": [
            {
                "op": "addEffect",
                "matchName": "ADBE Paint",
                "effectName": "AE 原生 Paint",
                "layerRef": "selected",
                "settings": {"brushSize": 25},
            }
        ],
        "message": "降级到 AE 原生 Paint 工具（修复质量降低）",
    },
}


# ---------------------------------------------------------------------------
# 简易记忆系统接口（内部实现，可替换为外部 MemoryStore）
# ---------------------------------------------------------------------------

class _MemoryStore:
    """
    轻量记忆存储，用于缓存历史路由结果。
    实际项目中可替换为与 TS 端 MemoryStore 对接的适配器。
    """

    def __init__(self) -> None:
        self._entries: List[Dict] = []

    def remember(self, category: str, key: str, content: Dict,
                 tags: List[str], confidence: float) -> None:
        """记录一条经验"""
        self._entries.append({
            "category": category,
            "key": key,
            "content": content,
            "tags": tags,
            "confidence": confidence,
        })

    def get_experience(self, category: str, task_keyword: str,
                       limit: int = 3, min_confidence: float = 0.6) -> List[Dict]:
        """检索相似任务的历史经验"""
        results = [
            e for e in self._entries
            if e["category"] == category
            and e["confidence"] >= min_confidence
            and (task_keyword in e["key"] or e["key"] in task_keyword)
        ]
        # 按置信度降序排列
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:limit]


# 全局记忆存储单例
_memory_store = _MemoryStore()


# ---------------------------------------------------------------------------
# IntentRouter
# ---------------------------------------------------------------------------

class IntentRouter:
    """意图路由决策器 — 根据用户输入判断任务流向"""

    def __init__(self, memory_store: Optional[_MemoryStore] = None) -> None:
        self._memory = memory_store or _memory_store

    # ------------------------------------------------------------------
    # 主路由方法
    # ------------------------------------------------------------------

    def route(self, user_input: str, context: Optional[Dict] = None) -> TaskRoute:
        """
        根据用户输入路由任务。

        Args:
            user_input: 用户原始输入文本
            context: 可选的项目上下文信息

        Returns:
            TaskRoute 路由结果
        """
        # 检测各类关键词命中情况
        has_silhouette = any(p.search(user_input) for p in SILHOUETTE_KEYWORDS)
        has_ae = any(p.search(user_input) for p in AE_EFFECT_KEYWORDS)
        has_connector = any(p.search(user_input) for p in HYBRID_CONNECTORS)

        # 1. 混合任务：同时包含 Silhouette + AE + 连接词
        if has_silhouette and has_ae and has_connector:
            return self._route_hybrid(user_input)

        # 2. 纯 Silhouette 任务
        if has_silhouette and not has_ae:
            return self._route_silhouette_only(user_input)

        # 3. 纯 AE 任务
        if has_ae and not has_silhouette:
            return self._route_ae_only(user_input)

        # 4. 无法识别
        return TaskRoute(
            type="unknown",
            reason="未匹配到 AE 或 Silhouette 关键词",
            confidence=0.2,
        )

    # ------------------------------------------------------------------
    # 带记忆系统增强的路由
    # ------------------------------------------------------------------

    def route_enhanced(self, user_input: str, context: Optional[Dict] = None) -> TaskRoute:
        """
        带记忆系统增强的路由方法。
        先查记忆系统相似任务历史，高置信度直接复用缓存路由，
        低置信度或无历史时走本地规则路由。

        Args:
            user_input: 用户原始输入文本
            context: 可选的项目上下文信息

        Returns:
            TaskRoute 路由结果
        """
        # 1. 查记忆系统，看是否有相似任务的历史经验
        keyword = user_input[:50]
        experiences = self._memory.get_experience(
            category="intent_route",
            task_keyword=keyword,
            limit=3,
            min_confidence=0.6,
        )

        # 2. 如果有高置信度 (>0.8) 的历史经验，直接复用缓存路由
        if experiences and experiences[0]["confidence"] > 0.8:
            exp = experiences[0]
            cached_route_data = exp.get("content", {}).get("route")
            if cached_route_data and isinstance(cached_route_data, dict):
                cached_type = cached_route_data.get("type")
                if cached_type:
                    return TaskRoute(
                        type=cached_type,
                        ae_operations=cached_route_data.get("ae_operations", []),
                        silhouette_operations=cached_route_data.get("silhouette_operations", []),
                        execution_order=cached_route_data.get("execution_order", []),
                        fallback=cached_route_data.get("fallback"),
                        reason=f"{cached_route_data.get('reason', '')} (from memory)",
                        confidence=min(exp["confidence"], 0.95),
                    )

        # 3. 无高置信度缓存，走本地规则路由
        result = self.route(user_input, context)

        # 4. 记录到记忆系统
        self._memory.remember(
            category="intent_route",
            key=keyword,
            content={
                "route": {
                    "type": result.type,
                    "ae_operations": result.ae_operations,
                    "silhouette_operations": result.silhouette_operations,
                    "execution_order": result.execution_order,
                    "fallback": result.fallback,
                    "reason": result.reason,
                    "confidence": result.confidence,
                },
                "rawInput": user_input,
            },
            tags=[result.type],
            confidence=result.confidence,
        )

        return result

    # ------------------------------------------------------------------
    # 判断是否为混合任务
    # ------------------------------------------------------------------

    def is_hybrid(self, user_input: str) -> bool:
        """
        判断输入是否为混合任务（同时包含 Silhouette + AE + 连接词）。

        Args:
            user_input: 用户原始输入文本

        Returns:
            True 为混合任务，False 为非混合任务
        """
        has_silhouette = any(p.search(user_input) for p in SILHOUETTE_KEYWORDS)
        has_ae = any(p.search(user_input) for p in AE_EFFECT_KEYWORDS)
        has_connector = any(p.search(user_input) for p in HYBRID_CONNECTORS)
        return has_silhouette and has_ae and has_connector

    # ------------------------------------------------------------------
    # 拆分混合输入
    # ------------------------------------------------------------------

    def split_hybrid_input(self, user_input: str) -> Dict:
        """
        拆分混合输入为 Silhouette 部分和 AE 部分。

        Args:
            user_input: 用户原始输入文本

        Returns:
            {"silhouette_part": str, "ae_part": str} 或空字典
        """
        for connector in HYBRID_CONNECTORS:
            match = connector.search(user_input)
            if match:
                before = user_input[:match.start()].strip()
                after = user_input[match.end():].strip()

                before_is_silhouette = any(p.search(before) for p in SILHOUETTE_KEYWORDS)
                after_is_ae = any(p.search(after) for p in AE_EFFECT_KEYWORDS)

                if before_is_silhouette and after_is_ae:
                    return {"silhouette_part": before, "ae_part": after}

        return {}

    # ==================================================================
    # 内部路由方法
    # ==================================================================

    def _route_ae_only(self, user_input: str) -> TaskRoute:
        """纯 AE 路由"""
        ae_ops = self._generate_ae_ops(user_input)
        return TaskRoute(
            type="ae_only",
            ae_operations=ae_ops,
            execution_order=["ae"],
            reason=f"纯 AE 任务: {user_input[:30]}",
            confidence=0.85,
        )

    def _route_silhouette_only(self, user_input: str) -> TaskRoute:
        """纯 Silhouette 路由"""
        silhouette_ops = self._generate_silhouette_ops(user_input)
        task_type = self._detect_silhouette_task_type(user_input)
        return TaskRoute(
            type="silhouette_only",
            silhouette_operations=silhouette_ops,
            execution_order=["silhouette"],
            fallback=FALLBACK_MAP.get(task_type, {
                "condition": "Silhouette 不可用",
                "ae_fallback_ops": [],
                "message": "无法降级，请安装 Silhouette 或手动操作",
            }),
            reason=f"纯 Silhouette 任务: {user_input[:30]}",
            confidence=0.85,
        )

    def _route_hybrid(self, user_input: str) -> TaskRoute:
        """混合路由 — Silhouette 前置 + AE 后置"""
        ae_ops = self._generate_ae_ops(user_input)
        silhouette_ops = self._generate_silhouette_ops(user_input)
        task_type = self._detect_silhouette_task_type(user_input)
        return TaskRoute(
            type="hybrid",
            ae_operations=ae_ops,
            silhouette_operations=silhouette_ops,
            execution_order=["silhouette", "ae"],
            fallback=FALLBACK_MAP.get(task_type, {
                "condition": "Silhouette 不可用",
                "ae_fallback_ops": [],
                "message": "无法降级，请安装 Silhouette 或手动操作",
            }),
            reason=f"混合任务: Silhouette → AE: {user_input[:30]}",
            confidence=0.8,
        )

    # ==================================================================
    # 操作生成
    # ==================================================================

    def _generate_ae_ops(self, user_input: str) -> List[Dict]:
        """从用户输入中提取 AE 操作列表"""
        ops: List[Dict] = []

        # 尝试从拆分后的 AE 部分提取，或从整体输入提取
        split = self.split_hybrid_input(user_input)
        ae_text = split.get("ae_part", user_input)

        for pattern in AE_EFFECT_KEYWORDS:
            match = pattern.search(ae_text)
            if match:
                ops.append({
                    "op": "addEffect",
                    "effectName": match.group(0),
                    "layerRef": "selected",
                })
                break  # 取第一个匹配即可，复杂场景由后续阶段处理

        return ops

    def _generate_silhouette_ops(self, user_input: str) -> List[Dict]:
        """从用户输入中生成 Silhouette 操作列表"""
        task_type = self._detect_silhouette_task_type(user_input)
        if not task_type:
            return []

        # 尝试从拆分后的 Silhouette 部分提取
        split = self.split_hybrid_input(user_input)
        sil_text = split.get("silhouette_part", user_input)

        if task_type == "roto":
            return [{
                "taskType": "roto",
                "shapeType": "x-spline",
                "tolerance": 1.0,
                "keyframes": 5,
                "outputFormat": "exr",
                "target": "主体",
                "tracking": "planar",
            }]
        elif task_type == "track":
            return [{
                "taskType": "track",
                "trackType": "planar",
                "searchArea": 21,
                "accuracy": "medium",
                "outputFormat": "ae",
            }]
        elif task_type == "paint":
            return [{
                "taskType": "paint",
                "paintMode": "clone",
                "brushSize": 25,
                "brushHardness": 0.5,
                "outputFormat": "png",
            }]

        return []

    # ==================================================================
    # 工具方法
    # ==================================================================

    def _detect_silhouette_task_type(self, user_input: str) -> Optional[str]:
        """
        从用户输入中检测 Silhouette 任务类型。

        Returns:
            "roto" | "track" | "paint" | None
        """
        # 按优先级检测：roto > track > paint
        if re.search(r"(?:扣|抠|遮罩|蒙版|mask|roto)", user_input, re.IGNORECASE):
            return "roto"
        if re.search(r"(?:跟踪|追踪|track)", user_input, re.IGNORECASE):
            return "track"
        if re.search(r"(?:修|擦|paint|修复|去除|擦除)", user_input, re.IGNORECASE):
            return "paint"
        if re.search(r"(?:silhouette)", user_input, re.IGNORECASE):
            return "roto"  # 默认归为 roto
        return None
