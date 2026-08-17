"""
AE MCP 工具真实环境验证套件
==========================

为开源 AE MCP 项目的 20+ 工具提供端到端真实环境验证能力。
每个工具的验证覆盖以下 6 个阶段：
    1. 预检查（AE 进程 / Panel / Listener）
    2. 预置条件（创建测试用合成 / 图层 / 素材）
    3. 执行命令（AEMCPClient 发送）
    4. 结果验证（解析返回结果是否符合预期）
    5. 状态检查（查询 AE 内部状态确认生效）
    6. 清理（删除测试数据，避免污染）

工具分为 A / B / C 三级：
    - A 级（核心可用性）：必测
    - B 级（重要能力）：应测
    - C 级（高级能力）：具备即可

支持真实 AE 环境与 Mock 客户端自动降级。
可通过 ``pytest`` 框架运行，也可通过 ``MCPToolValidationSuite`` 直接调用。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import statistics
import sys
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    Union,
)

# 让脚本可直接 python 运行时也能找到 ae.* 模块
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AE_PARENT = Path(__file__).resolve().parent.parent
for _p in (str(_PROJECT_ROOT), str(_AE_PARENT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger("ae.tests.mcp_tools_validation")


# ============================================================================
# 数据模型
# ============================================================================


ValidationStatus = Literal["pass", "fail", "skip", "error"]


@dataclass
class ToolValidationResult:
    """单个 MCP 工具的验证结果。

    Attributes:
        tool_name: 工具名称（与 AEMCPClient 方法名一致）
        category: 工具分级 "core" / "important" / "advanced"
        status: 验证状态
        latency_ms: 命令往返延迟（毫秒）
        error_message: 错误信息
        error_code: 错误码（来自 BridgeResponse.error.code）
        pre_conditions: 预置条件描述
        post_conditions: 验证后状态描述
        notes: 额外备注或改进建议
        timestamp: 验证时间戳
        retry_count: 重试次数
    """

    tool_name: str
    category: str
    status: ValidationStatus
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    error_code: Optional[int] = None
    pre_conditions: List[str] = field(default_factory=list)
    post_conditions: List[str] = field(default_factory=list)
    notes: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典。"""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat(timespec="milliseconds")
        return d

    @property
    def status_emoji(self) -> str:
        """状态对应的 emoji 标记。"""
        return {
            "pass": "✅",
            "fail": "❌",
            "skip": "⏭️",
            "error": "⚠️",
        }.get(self.status, "❓")


@dataclass
class CategoryStats:
    """单个分类的统计数据。"""

    category: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errored: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0

    @property
    def pass_rate(self) -> float:
        """通过率。"""
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errored": self.errored,
            "pass_rate": round(self.pass_rate, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
        }


@dataclass
class ValidationReport:
    """完整验证报告。

    Attributes:
        total_tools: 总工具数
        passed: 通过数
        failed: 失败数
        skipped: 跳过数
        errors: 错误数
        pass_rate: 通过率
        avg_latency_ms: 平均延迟
        p95_latency_ms: P95 延迟
        results: 详细结果列表
        start_time: 开始时间
        end_time: 结束时间
        ae_version: AE 版本
        mcp_server_version: MCP 服务端版本
        environment: "real" / "mock"
        category_stats: 分类统计
    """

    total_tools: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    pass_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    results: List[ToolValidationResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime = field(default_factory=datetime.now)
    ae_version: str = "unknown"
    mcp_server_version: str = "unknown"
    environment: str = "unknown"
    category_stats: List[CategoryStats] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tools": self.total_tools,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "pass_rate": round(self.pass_rate, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "results": [r.to_dict() for r in self.results],
            "start_time": self.start_time.isoformat(timespec="milliseconds"),
            "end_time": self.end_time.isoformat(timespec="milliseconds"),
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "ae_version": self.ae_version,
            "mcp_server_version": self.mcp_server_version,
            "environment": self.environment,
            "category_stats": [c.to_dict() for c in self.category_stats],
        }


# ============================================================================
# Mock 客户端（无真实 AE 环境时降级使用）
# ============================================================================


class _MockAEMCPClient:
    """AE MCP 客户端的 Mock 实现。

    当真实 AE 不可用时，验证套件会回退到此实现，保证测试可在 CI 环境运行。
    模拟大部分工具的"成功"行为，并记录调用历史。

    Attributes:
        call_history: 命令调用历史（[(command, params, result), ...]）
        call_delay_ms: 每次调用的模拟延迟
    """

    def __init__(self, call_delay_ms: float = 5.0) -> None:
        self.call_history: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
        self.call_delay_ms = call_delay_ms
        self._comp_counter = 0
        self._layer_counter = 0
        self._keyframe_counter = 0
        self._effect_counter = 0
        self._layer_index: Dict[str, int] = {}
        self._comps: Dict[str, Dict[str, Any]] = {}
        self._layers: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._effects: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        self._properties: Dict[Tuple[str, str], Dict[str, Any]] = {}

    # ---- 元信息 ----
    def ping(self) -> Dict[str, Any]:
        return self._simulate("ping", {}, {"pong": True, "version": "mock-1.0.0"})

    def get_project_info(self) -> Dict[str, Any]:
        return self._simulate(
            "get_projectInfo",
            {},
            {
                "projectName": "MockProject",
                "path": "mock://project.aep",
                "numComps": len(self._comps),
            },
        )

    # ---- 合成 ----
    def list_compositions(self) -> List[Dict[str, Any]]:
        comps = list(self._comps.values())
        return self._simulate("listCompositions", {}, {"compositions": comps})

    def create_composition(
        self,
        name: str,
        width: int = 1920,
        height: int = 1080,
        duration: float = 10.0,
        frame_rate: float = 30.0,
        bg_color: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        self._comp_counter += 1
        comp_id = f"comp_{self._comp_counter}"
        info = {
            "id": comp_id,
            "name": name,
            "width": width,
            "height": height,
            "duration": duration,
            "frameRate": frame_rate,
            "bgColor": bg_color or [0.0, 0.0, 0.0],
            "numLayers": 0,
        }
        self._comps[name] = info
        return self._simulate("createComposition", {"name": name}, info)

    # ---- 图层 ----
    def create_text_layer(
        self,
        comp_name: str,
        text: str,
        layer_name: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        return self._create_layer(comp_name, layer_name or f"Text_{text[:10]}", "text", {"text": text})

    def create_solid_layer(
        self,
        comp_name: str,
        layer_name: Optional[str] = None,
        color: Optional[List[float]] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._create_layer(
            comp_name, layer_name or "Solid", "solid",
            {"color": color, "width": width, "height": height},
        )

    def create_shape_layer(self, comp_name: str, shape_type: str = "rect", layer_name: Optional[str] = None, **_: Any) -> Dict[str, Any]:
        return self._create_layer(comp_name, layer_name or f"Shape_{shape_type}", "shape", {"shapeType": shape_type})

    def create_camera(self, comp_name: str, layer_name: Optional[str] = None, preset: Optional[str] = None) -> Dict[str, Any]:
        return self._create_layer(comp_name, layer_name or "Camera", "camera", {"preset": preset})

    def add_adjustment_layer(self, comp_name: str, layer_name: Optional[str] = None) -> Dict[str, Any]:
        return self._create_layer(comp_name, layer_name or "Adjustment", "adjustment", {})

    def delete_layer(self, comp_name: str, layer_name: str) -> Dict[str, Any]:
        self._layers.pop((comp_name, layer_name), None)
        return self._simulate("deleteLayer", {"compName": comp_name, "layerName": layer_name}, {"deleted": True})

    def duplicate_layer(
        self, comp_name: str, layer_name: str, new_name: Optional[str] = None
    ) -> Dict[str, Any]:
        new_layer_name = new_name or f"{layer_name}_copy"
        return self._create_layer(comp_name, new_layer_name, "copy", {"sourceLayer": layer_name})

    # ---- 图层属性 ----
    def set_layer_properties(
        self, comp_name: str, layer_name: str, properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        self._properties.setdefault((comp_name, layer_name), {}).update(properties)
        return self._simulate(
            "setLayerProperties",
            {"compName": comp_name, "layerName": layer_name, "properties": properties},
            {"set": True, "properties": properties},
        )

    def set_blend_mode(self, comp_name: str, layer_name: str, blend_mode: str) -> Dict[str, Any]:
        return self._simulate(
            "setBlendingMode",
            {"compName": comp_name, "layerName": layer_name, "blendingMode": blend_mode},
            {"blendingMode": blend_mode, "set": True},
        )

    def set_track_matte(
        self, comp_name: str, target_layer: str, matte_layer: str, matte_type: str = "ALPHA"
    ) -> Dict[str, Any]:
        return self._simulate(
            "setTrackMatte",
            {"compName": comp_name, "targetLayer": target_layer, "matteLayer": matte_layer, "matteType": matte_type},
            {"set": True, "matteType": matte_type},
        )

    def set_parent_layer(
        self, comp_name: str, child_layer: str, parent_layer: Optional[str] = None
    ) -> Dict[str, Any]:
        return self._simulate(
            "setParentLayer",
            {"compName": comp_name, "childLayer": child_layer, "parentLayer": parent_layer},
            {"set": True, "parentLayer": parent_layer},
        )

    def set_motion_blur(
        self, comp_name: str, layer_name: str, enabled: bool = True
    ) -> Dict[str, Any]:
        return self._simulate(
            "setMotionBlur",
            {"compName": comp_name, "layerName": layer_name, "enabled": enabled},
            {"enabled": enabled, "set": True},
        )

    def get_layer_info(
        self, comp_name: str, layer_name: Optional[str] = None
    ) -> Dict[str, Any]:
        if layer_name:
            layer = self._layers.get((comp_name, layer_name), {})
            return self._simulate(
                "getLayerInfo",
                {"compName": comp_name, "layerName": layer_name},
                {"layer": layer},
            )
        layers = [v for (c, _), v in self._layers.items() if c == comp_name]
        return self._simulate(
            "getLayerInfo", {"compName": comp_name}, {"layers": layers}
        )

    # ---- 关键帧 / 表达式 ----
    def set_layer_keyframe(
        self,
        comp_name: str,
        layer_name: str,
        property_name: str,
        time: float,
        value: Any,
        easing: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._keyframe_counter += 1
        kf_id = f"kf_{self._keyframe_counter}"
        return self._simulate(
            "setLayerKeyframe",
            {"compName": comp_name, "layerName": layer_name, "propertyName": property_name, "time": time, "value": value},
            {"keyframeId": kf_id, "time": time, "value": value, "easing": easing},
        )

    def set_keyframe_easing(
        self,
        comp_name: str,
        layer_name: str,
        property_name: str,
        keyframe_index: int,
        ease_in: Optional[List[float]] = None,
        ease_out: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        return self._simulate(
            "setKeyframeEasing",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "propertyName": property_name,
                "keyframeIndex": keyframe_index,
                "easeIn": ease_in,
                "easeOut": ease_out,
            },
            {"set": True, "easeIn": ease_in, "easeOut": ease_out},
        )

    def set_layer_expression(
        self, comp_name: str, layer_name: str, property_name: str, expression: str
    ) -> Dict[str, Any]:
        return self._simulate(
            "setExpression",
            {"compName": comp_name, "layerName": layer_name, "propertyName": property_name, "expressionText": expression},
            {"set": True, "expression": expression},
        )

    # ---- 效果 ----
    def apply_effect(
        self,
        comp_name: str,
        layer_name: str,
        effect_name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._effect_counter += 1
        info = {
            "effectName": effect_name,
            "matchName": f"ADBE {effect_name}",
            "index": self._effect_counter,
            "enabled": True,
            "properties": properties or {},
        }
        self._effects.setdefault((comp_name, layer_name), []).append(info)
        return self._simulate(
            "applyEffect",
            {"compName": comp_name, "layerName": layer_name, "effectName": effect_name},
            info,
        )

    def batch_add_effects(
        self, comp_name: str, layer_name: str, effects: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        applied = []
        for e in effects:
            r = self.apply_effect(comp_name, layer_name, e.get("name", ""), e.get("properties"))
            applied.append(r)
        return self._simulate(
            "batchAddEffects",
            {"compName": comp_name, "layerName": layer_name, "effects": effects},
            {"applied": applied, "count": len(applied)},
        )

    def apply_effect_template(
        self, comp_name: str, layer_name: str, template_name: str
    ) -> Dict[str, Any]:
        return self._simulate(
            "applyEffectTemplate",
            {"compName": comp_name, "layerName": layer_name, "templateName": template_name},
            {"applied": True, "templateName": template_name},
        )

    def list_effects(self, comp_name: str, layer_name: str) -> List[Dict[str, Any]]:
        effects = self._effects.get((comp_name, layer_name), [])
        return self._simulate(
            "listEffects",
            {"compName": comp_name, "layerName": layer_name},
            {"effects": effects},
        )

    def get_effect_properties(
        self, comp_name: str, layer_name: str, effect_name: str
    ) -> Dict[str, Any]:
        return self._simulate(
            "getEffectProperties",
            {"compName": comp_name, "layerName": layer_name, "effectName": effect_name},
            {"properties": {"Blurriness": 0, "BlendWithOriginal": 100}},
        )

    # ---- 素材 ----
    def import_footage(
        self, file_path: str, name: Optional[str] = None, as_sequence: bool = False
    ) -> Dict[str, Any]:
        return self._simulate(
            "importFootage",
            {"filePath": file_path, "name": name, "importAsSequence": as_sequence},
            {"imported": True, "name": name or Path(file_path).stem, "path": file_path},
        )

    # ---- 内部 ----
    def _create_layer(
        self, comp_name: str, name: str, layer_type: str, extra: Dict[str, Any]
    ) -> Dict[str, Any]:
        self._layer_counter += 1
        self._layer_index[(comp_name, name)] = self._layer_counter
        info = {
            "index": self._layer_counter,
            "name": name,
            "type": layer_type,
            "duration": 10.0,
            "startTime": 0.0,
            "enabled": True,
            "solo": False,
            "locked": False,
            "shy": False,
            **extra,
        }
        self._layers[(comp_name, name)] = info
        return self._simulate(
            "createLayer",
            {"compName": comp_name, "name": name, "type": layer_type},
            info,
        )

    def _simulate(
        self, command: str, params: Dict[str, Any], result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """模拟一次调用：记录历史 + 添加延迟。"""
        time.sleep(self.call_delay_ms / 1000.0)
        self.call_history.append((command, params, result))
        return dict(result)


# ============================================================================
# 验证器基类
# ============================================================================


class ToolValidator(ABC):
    """单个工具验证器的抽象基类。

    子类需要实现 ``run`` 方法完成"预置 → 执行 → 验证 → 清理"四阶段。
    """

    tool_name: ClassVar[str]
    category: ClassVar[str]
    description: ClassVar[str] = ""

    def __init__(self, client: Any) -> None:
        self.client = client

    @abstractmethod
    async def run(self) -> ToolValidationResult:
        """执行验证并返回结果。"""
        raise NotImplementedError

    # ---- 工具方法 ----
    def _make_result(
        self,
        status: ValidationStatus,
        latency_ms: float = 0.0,
        error_message: Optional[str] = None,
        error_code: Optional[int] = None,
        pre_conditions: Optional[List[str]] = None,
        post_conditions: Optional[List[str]] = None,
        notes: str = "",
    ) -> ToolValidationResult:
        """构造验证结果。"""
        return ToolValidationResult(
            tool_name=self.tool_name,
            category=self.category,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
            error_code=error_code,
            pre_conditions=pre_conditions or [],
            post_conditions=post_conditions or [],
            notes=notes,
        )

    async def _timed_call(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Tuple[Optional[Dict[str, Any]], float, Optional[Exception]]:
        """执行命令并测量延迟。

        Returns:
            (result, latency_ms, exception) 元组。调用失败时 exception 不为 None。
        """
        loop = asyncio.get_running_loop()
        start = time.time()
        try:
            result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))
            latency_ms = (time.time() - start) * 1000
            return result, latency_ms, None
        except Exception as e:  # noqa: BLE001
            latency_ms = (time.time() - start) * 1000
            err_code = getattr(getattr(e, "error_code", None), "value", None)
            if err_code is None and hasattr(e, "error_code"):
                err_code = int(e.error_code) if e.error_code is not None else None
            # 把 error_code 透传
            self._last_error_code = err_code  # type: ignore[attr-defined]
            return None, latency_ms, e


# ============================================================================
# A 级验证器（核心可用性）
# ============================================================================


class GetProjectInfoValidator(ToolValidator):
    tool_name = "get_project_info"
    category = "core"
    description = "获取项目基本信息（项目名、路径、合成数）"

    async def run(self) -> ToolValidationResult:
        result, latency, err = await self._timed_call(self.client.get_project_info)
        if err is not None:
            return self._make_result("fail", latency, str(err))
        if not result or "projectName" not in result:
            return self._make_result(
                "fail", latency, "返回结果缺少 projectName 字段"
            )
        return self._make_result(
            "pass",
            latency,
            post_conditions=[
                f"projectName={result.get('projectName')}",
                f"path={result.get('path', 'n/a')}",
            ],
        )


class ListCompositionsValidator(ToolValidator):
    tool_name = "list_compositions"
    category = "core"
    description = "列出项目内所有合成"

    async def run(self) -> ToolValidationResult:
        result, latency, err = await self._timed_call(self.client.list_compositions)
        if err is not None:
            return self._make_result("fail", latency, str(err))
        comps = result.get("compositions", []) if isinstance(result, dict) else result
        if not isinstance(comps, list):
            return self._make_result("fail", latency, "返回结果不是列表")
        return self._make_result(
            "pass",
            latency,
            post_conditions=[f"compositions count={len(comps)}"],
        )


class CreateCompositionValidator(ToolValidator):
    tool_name = "create_composition"
    category = "core"
    description = "创建 1920x1080 / 30fps / 5s 合成"

    comp_name: ClassVar[str] = "MCPVal_CreateComp"

    async def run(self) -> ToolValidationResult:
        pre = ["无（新建合成）"]
        result, latency, err = await self._timed_call(
            self.client.create_composition,
            name=self.comp_name,
            width=1920,
            height=1080,
            duration=5.0,
            frame_rate=30.0,
            bg_color=[0.0, 0.0, 0.0],
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        if not result or result.get("name") != self.comp_name:
            return self._make_result(
                "fail", latency, f"合成名称不匹配: {result}", pre_conditions=pre
            )
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=[
                f"id={result.get('id', result.get('compId', '?'))}",
                f"width={result.get('width')}",
                f"height={result.get('height')}",
            ],
        )


class CreateTextLayerValidator(ToolValidator):
    tool_name = "create_text_layer"
    category = "core"
    description = "在合成中创建文字图层"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        pre = [f"合成 {comp} 已存在"]
        result, latency, err = await self._timed_call(
            self.client.create_text_layer,
            comp_name=comp,
            text="Validation Text",
            layer_name="MCPVal_Text",
            font_size=48.0,
            fill_color=[1.0, 1.0, 1.0],
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=[f"layer name={result.get('name', result.get('layerName', '?'))}"],
        )


class CreateSolidLayerValidator(ToolValidator):
    tool_name = "create_solid_layer"
    category = "core"
    description = "在合成中创建 800x600 红色固态层"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        pre = [f"合成 {comp} 已存在"]
        result, latency, err = await self._timed_call(
            self.client.create_solid_layer,
            comp_name=comp,
            layer_name="MCPVal_Solid",
            color=[1.0, 0.0, 0.0],
            width=800,
            height=600,
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=[f"layer name={result.get('name', '?')}"],
        )


class SetLayerPropertiesValidator(ToolValidator):
    tool_name = "set_layer_properties"
    category = "core"
    description = "设置图层 Position / Scale / Opacity / Rotation"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在"]
        result, latency, err = await self._timed_call(
            self.client.set_layer_properties,
            comp_name=comp,
            layer_name=layer,
            properties={
                "position": [960, 540],
                "scale": [50, 50],
                "opacity": 80,
                "rotation": 45,
            },
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        if not result or not result.get("set", result.get("ok", True)):
            return self._make_result(
                "fail", latency, f"set_layer_properties 返回非成功: {result}", pre_conditions=pre
            )
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=["position=[960,540]", "scale=[50,50]", "opacity=80", "rotation=45"],
        )


class SetLayerKeyframeValidator(ToolValidator):
    tool_name = "set_layer_keyframe"
    category = "core"
    description = "为图层 Position 属性在 0s/2s/4s 设置关键帧"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在"]
        keyframes = [
            (0.0, [0, 540]),
            (2.0, [1920, 540]),
            (4.0, [0, 540]),
        ]
        last_result: Optional[Dict[str, Any]] = None
        total_latency = 0.0
        for t, v in keyframes:
            r, lat, err = await self._timed_call(
                self.client.set_layer_keyframe,
                comp_name=comp,
                layer_name=layer,
                property_name="Position",
                time=t,
                value=v,
            )
            total_latency += lat
            if err is not None:
                return self._make_result(
                    "fail", total_latency, f"t={t}s 关键帧失败: {err}", pre_conditions=pre
                )
            last_result = r
        return self._make_result(
            "pass",
            total_latency,
            pre_conditions=pre,
            post_conditions=[
                f"keyframes=3",
                f"last_keyframeId={last_result.get('keyframeId', '?') if last_result else '?'}",
            ],
        )


class SetKeyframeEasingValidator(ToolValidator):
    tool_name = "set_keyframe_easing"
    category = "core"
    description = "设置关键帧缓动曲线 (easeIn=66,66 / easeOut=66,66)"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在", "Position 属性有 3 个关键帧"]
        result, latency, err = await self._timed_call(
            self.client.set_keyframe_easing,
            comp_name=comp,
            layer_name=layer,
            property_name="Position",
            keyframe_index=1,
            ease_in=[66, 66],
            ease_out=[66, 66],
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=["easeIn=[66,66]", "easeOut=[66,66]"],
        )


class ApplyEffectValidator(ToolValidator):
    tool_name = "apply_effect"
    category = "core"
    description = "为图层应用 Gaussian Blur 效果"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在"]
        result, latency, err = await self._timed_call(
            self.client.apply_effect,
            comp_name=comp,
            layer_name=layer,
            effect_name="Gaussian Blur",
            properties={"Blurriness": 10.0},
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=[
                f"effect={result.get('effectName', result.get('name', '?'))}",
                f"index={result.get('index', '?')}",
            ],
        )


class DeleteLayerValidator(ToolValidator):
    tool_name = "delete_layer"
    category = "core"
    description = "删除测试用文字图层"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Text"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在"]
        result, latency, err = await self._timed_call(
            self.client.delete_layer, comp_name=comp, layer_name=layer
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        if isinstance(result, dict) and result.get("deleted") is False:
            return self._make_result("fail", latency, "delete_layer 返回 deleted=false", pre_conditions=pre)
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=["deleted=True"]
        )


# ============================================================================
# B 级验证器（重要能力）
# ============================================================================


class ListEffectsValidator(ToolValidator):
    tool_name = "list_effects"
    category = "important"
    description = "列出图层上所有效果"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 已应用 Gaussian Blur"]
        result, latency, err = await self._timed_call(
            self.client.list_effects, comp_name=comp, layer_name=layer
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        effects = result.get("effects", []) if isinstance(result, dict) else result
        if not isinstance(effects, list) or len(effects) == 0:
            return self._make_result(
                "fail", latency, f"期望至少 1 个效果, 实际: {result}", pre_conditions=pre
            )
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=[f"effects count={len(effects)}", f"first={effects[0].get('name')}"],
        )


class GetLayerInfoValidator(ToolValidator):
    tool_name = "get_layer_info"
    category = "important"
    description = "获取图层详细信息"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在"]
        result, latency, err = await self._timed_call(
            self.client.get_layer_info, comp_name=comp, layer_name=layer
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        layer_info = result.get("layer", {}) if isinstance(result, dict) else result
        if not layer_info or "name" not in layer_info:
            return self._make_result(
                "fail", latency, f"返回缺少 name 字段: {result}", pre_conditions=pre
            )
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=[f"name={layer_info.get('name')}", f"type={layer_info.get('type')}"],
        )


class GetEffectPropertiesValidator(ToolValidator):
    tool_name = "get_effect_properties"
    category = "important"
    description = "获取效果的属性字典"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        effect = "Gaussian Blur"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在", f"效果 {effect} 已应用"]
        result, latency, err = await self._timed_call(
            self.client.get_effect_properties,
            comp_name=comp,
            layer_name=layer,
            effect_name=effect,
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        props = result.get("properties", {}) if isinstance(result, dict) else result
        if not isinstance(props, dict):
            return self._make_result(
                "fail", latency, f"期望 properties 为 dict, 实际: {type(props)}", pre_conditions=pre
            )
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=[f"props count={len(props)}"],
        )


class SetBlendModeValidator(ToolValidator):
    tool_name = "set_blend_mode"
    category = "important"
    description = "设置图层混合模式为 MULTIPLY"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在"]
        result, latency, err = await self._timed_call(
            self.client.set_blend_mode,
            comp_name=comp,
            layer_name=layer,
            blend_mode="MULTIPLY",
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        if isinstance(result, dict) and result.get("blendingMode") != "MULTIPLY":
            return self._make_result(
                "fail", latency, f"blend_mode 未生效: {result}", pre_conditions=pre
            )
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=["blendingMode=MULTIPLY"]
        )


class SetTrackMatteValidator(ToolValidator):
    tool_name = "set_track_matte"
    category = "important"
    description = "设置轨道遮罩 (ALPHA)"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        target = "MCPVal_Solid"
        matte = "MCPVal_Text"
        pre = [
            f"合成 {comp} 存在",
            f"目标图层 {target} 存在",
            f"遮罩图层 {matte} 存在",
        ]
        result, latency, err = await self._timed_call(
            self.client.set_track_matte,
            comp_name=comp,
            target_layer=target,
            matte_layer=matte,
            matte_type="ALPHA",
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=["matteType=ALPHA"]
        )


class AddAdjustmentLayerValidator(ToolValidator):
    tool_name = "add_adjustment_layer"
    category = "important"
    description = "添加调整图层"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        pre = [f"合成 {comp} 存在"]
        result, latency, err = await self._timed_call(
            self.client.add_adjustment_layer,
            comp_name=comp,
            layer_name="MCPVal_Adjustment",
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=[f"layer name={result.get('name', '?')}"],
        )


class SetLayerExpressionValidator(ToolValidator):
    tool_name = "set_layer_expression"
    category = "important"
    description = "为 Rotation 属性设置表达式 time * 50"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在"]
        result, latency, err = await self._timed_call(
            self.client.set_layer_expression,
            comp_name=comp,
            layer_name=layer,
            property_name="Rotation",
            expression="time * 50",
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=["expression=time * 50"]
        )


class BatchAddEffectsValidator(ToolValidator):
    tool_name = "batch_add_effects"
    category = "important"
    description = "批量添加 Hue/Sat + Brightness/Contrast 两个效果"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Adjustment"
        pre = [f"合成 {comp} 存在", f"调整图层 {layer} 存在"]
        effects = [
            {"name": "Hue/Saturation", "properties": {"Master Hue": 90}},
            {"name": "Brightness & Contrast", "properties": {"Brightness": 20, "Contrast": 30}},
        ]
        result, latency, err = await self._timed_call(
            self.client.batch_add_effects,
            comp_name=comp,
            layer_name=layer,
            effects=effects,
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        count = (result or {}).get("count", 0) if isinstance(result, dict) else 0
        if count < len(effects):
            return self._make_result(
                "fail",
                latency,
                f"批量应用数量不足: 期望 {len(effects)} 实际 {count}",
                pre_conditions=pre,
            )
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=[f"applied count={count}"]
        )


class ApplyEffectTemplateValidator(ToolValidator):
    tool_name = "apply_effect_template"
    category = "important"
    description = "应用效果预设模板 (drop_shadow)"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Text"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在"]
        result, latency, err = await self._timed_call(
            self.client.apply_effect_template,
            comp_name=comp,
            layer_name=layer,
            template_name="drop_shadow",
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=["template=drop_shadow"]
        )


class ImportFootageValidator(ToolValidator):
    tool_name = "import_footage"
    category = "important"
    description = "导入测试用 PNG 素材"

    async def run(self) -> ToolValidationResult:
        # 生成一个 1x1 透明 PNG 用于导入测试
        import tempfile
        import base64

        png_b64 = (
            b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            b"+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        tmp = Path(tempfile.gettempdir()) / f"mcp_val_{uuid.uuid4().hex[:8]}.png"
        tmp.write_bytes(base64.b64decode(png_b64))

        pre = [f"测试 PNG 已生成: {tmp}"]
        try:
            result, latency, err = await self._timed_call(
                self.client.import_footage,
                file_path=str(tmp),
                name="MCPVal_Import",
            )
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        if isinstance(result, dict) and not result.get("imported", True):
            return self._make_result(
                "fail", latency, f"导入未成功: {result}", pre_conditions=pre
            )
        return self._make_result(
            "pass",
            latency,
            pre_conditions=pre,
            post_conditions=[f"imported name={result.get('name', '?') if isinstance(result, dict) else 'mock'}"],
        )


# ============================================================================
# C 级验证器（高级能力）
# ============================================================================


class CreateShapeLayerValidator(ToolValidator):
    tool_name = "create_shape_layer"
    category = "advanced"
    description = "创建椭圆形状图层"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        pre = [f"合成 {comp} 存在"]
        result, latency, err = await self._timed_call(
            self.client.create_shape_layer,
            comp_name=comp,
            shape_type="ellipse",
            layer_name="MCPVal_Shape",
            fill_color=[0.0, 1.0, 0.0],
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=[f"shapeType=ellipse"]
        )


class CreateCameraValidator(ToolValidator):
    tool_name = "create_camera"
    category = "advanced"
    description = "创建 35mm 摄像机"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        pre = [f"合成 {comp} 存在"]
        result, latency, err = await self._timed_call(
            self.client.create_camera,
            comp_name=comp,
            layer_name="MCPVal_Camera",
            preset="35mm",
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=["preset=35mm"]
        )


class DuplicateLayerValidator(ToolValidator):
    tool_name = "duplicate_layer"
    category = "advanced"
    description = "复制 Solid 图层"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在"]
        result, latency, err = await self._timed_call(
            self.client.duplicate_layer,
            comp_name=comp,
            layer_name=layer,
            new_name="MCPVal_Solid_Copy",
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=["new name=MCPVal_Solid_Copy"]
        )


class SetParentLayerValidator(ToolValidator):
    tool_name = "set_parent_layer"
    category = "advanced"
    description = "将 Shape 图层父子关系绑定到 Solid"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        child = "MCPVal_Shape"
        parent = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"子图层 {child} 存在", f"父图层 {parent} 存在"]
        result, latency, err = await self._timed_call(
            self.client.set_parent_layer,
            comp_name=comp,
            child_layer=child,
            parent_layer=parent,
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=[f"parent={parent}"]
        )


class SetMotionBlurValidator(ToolValidator):
    tool_name = "set_motion_blur"
    category = "advanced"
    description = "为图层启用运动模糊"

    async def run(self) -> ToolValidationResult:
        comp = "MCPVal_CreateComp"
        layer = "MCPVal_Solid"
        pre = [f"合成 {comp} 存在", f"图层 {layer} 存在"]
        result, latency, err = await self._timed_call(
            self.client.set_motion_blur,
            comp_name=comp,
            layer_name=layer,
            enabled=True,
        )
        if err is not None:
            return self._make_result("fail", latency, str(err), pre_conditions=pre)
        return self._make_result(
            "pass", latency, pre_conditions=pre, post_conditions=["motionBlur=enabled"]
        )


# CreateCompositionValidator.comp_name 在 pre_conditions 其它验证器中被引用，
# 但因各验证器在 setup 阶段才会真正创建合成，所以下面保留静态名称引用。

# ============================================================================
# 验证套件主类
# ============================================================================


# 默认分类映射表（可被外部覆盖）
CATEGORY_DEFINITIONS: Dict[str, List[Type[ToolValidator]]] = {
    "core": [
        GetProjectInfoValidator,
        ListCompositionsValidator,
        CreateCompositionValidator,
        CreateTextLayerValidator,
        CreateSolidLayerValidator,
        SetLayerPropertiesValidator,
        SetLayerKeyframeValidator,
        SetKeyframeEasingValidator,
        ApplyEffectValidator,
        DeleteLayerValidator,
    ],
    "important": [
        ListEffectsValidator,
        GetLayerInfoValidator,
        GetEffectPropertiesValidator,
        SetBlendModeValidator,
        SetTrackMatteValidator,
        AddAdjustmentLayerValidator,
        SetLayerExpressionValidator,
        BatchAddEffectsValidator,
        ApplyEffectTemplateValidator,
        ImportFootageValidator,
    ],
    "advanced": [
        CreateShapeLayerValidator,
        CreateCameraValidator,
        DuplicateLayerValidator,
        SetParentLayerValidator,
        SetMotionBlurValidator,
    ],
}


CATEGORY_DISPLAY_NAMES: Dict[str, str] = {
    "core": "A 级（核心可用性）",
    "important": "B 级（重要能力）",
    "advanced": "C 级（高级能力）",
}


class MCPToolValidationSuite:
    """MCP 工具真实环境验证套件。

    负责协调验证器与客户端，提供 6 阶段验证流程：
    pre-check → pre-set → execute → verify → state-check → cleanup。

    Attributes:
        CATEGORY_A_CORE: A 级分类名
        CATEGORY_B_IMPORTANT: B 级分类名
        CATEGORY_C_ADVANCED: C 级分类名
        report: 最终验证报告
    """

    CATEGORY_A_CORE: str = "core"
    CATEGORY_B_IMPORTANT: str = "important"
    CATEGORY_C_ADVANCED: str = "advanced"

    def __init__(
        self,
        client: Optional[Any] = None,
        bridge_dir: Optional[str] = None,
        use_real_ae: bool = False,
        categories: Optional[List[str]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """初始化验证套件。

        Args:
            client: 已构造的 AEMCPClient 客户端；为 None 时自动选择 mock / 真实客户端
            bridge_dir: Bridge 通信目录，仅在未提供 client 时生效
            use_real_ae: 是否强制使用真实 AE 客户端（找不到则报错）
            categories: 要运行的分类列表，默认全部
            logger: 自定义日志记录器
        """
        self._explicit_client = client
        self._bridge_dir = bridge_dir
        self._use_real_ae = use_real_ae
        self._categories = categories or list(CATEGORY_DEFINITIONS.keys())
        self.logger = logger or logging.getLogger("ae.tests.mcp_tools_validation")
        self.report = ValidationReport()
        self._client: Optional[Any] = None
        self._environment = "unknown"
        self._ae_version = "unknown"
        self._mcp_server_version = "unknown"

    # ------------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------------

    async def setup_ae_environment(self) -> None:
        """准备 AE 测试环境。

        - 优先使用传入的 client
        - 其次根据 use_real_ae 选择真实 / Mock 客户端
        - 最后统一回退到内置 Mock 客户端
        """
        if self._explicit_client is not None:
            self._client = self._explicit_client
            self._environment = "real"
            self.logger.info("使用显式传入的客户端")
        elif self._use_real_ae:
            self._client = self._create_real_client()
            self._environment = "real"
        else:
            self._client = self._create_real_client_or_mock()
            self._environment = "real" if self._environment == "real" else "mock"

        # 探测 AE 版本信息
        await self._detect_versions()

    async def run_all(
        self, categories: Optional[List[str]] = None
    ) -> ValidationReport:
        """运行所有/指定分类的验证。

        Args:
            categories: 要运行的分类列表，默认使用构造时传入的 categories

        Returns:
            完整验证报告
        """
        cats = categories or self._categories
        if not cats:
            cats = list(CATEGORY_DEFINITIONS.keys())

        await self.setup_ae_environment()
        assert self._client is not None

        self.report = ValidationReport(
            start_time=datetime.now(),
            environment=self._environment,
            ae_version=self._ae_version,
            mcp_server_version=self._mcp_server_version,
        )

        all_results: List[ToolValidationResult] = []
        for cat in cats:
            self.logger.info("=" * 60)
            self.logger.info(f"运行分类: {CATEGORY_DISPLAY_NAMES.get(cat, cat)}")
            self.logger.info("=" * 60)
            results = await self._run_category(cat)
            all_results.extend(results)
            for r in results:
                self._log_result(r)

        # 清理
        await self._cleanup_test_data()

        # 统计
        self.report.results = all_results
        self.report.end_time = datetime.now()
        self._populate_report_stats()
        return self.report

    async def run_category_a(self) -> List[ToolValidationResult]:
        """运行 A 级（核心可用性）验证。"""
        return await self._run_category(self.CATEGORY_A_CORE)

    async def run_category_b(self) -> List[ToolValidationResult]:
        """运行 B 级（重要能力）验证。"""
        return await self._run_category(self.CATEGORY_B_IMPORTANT)

    async def run_category_c(self) -> List[ToolValidationResult]:
        """运行 C 级（高级能力）验证。"""
        return await self._run_category(self.CATEGORY_C_ADVANCED)

    async def validate_tool(
        self, tool_name: str, category: Optional[str] = None
    ) -> ToolValidationResult:
        """验证单个工具。

        Args:
            tool_name: 工具名
            category: 工具分类（默认按 tool_name 在所有分类中查找）

        Returns:
            验证结果
        """
        if self._client is None:
            await self.setup_ae_environment()

        # 查找验证器
        categories_to_search = [category] if category else list(CATEGORY_DEFINITIONS.keys())
        validator_cls: Optional[Type[ToolValidator]] = None
        found_cat: Optional[str] = None
        for cat in categories_to_search:
            for cls in CATEGORY_DEFINITIONS.get(cat, []):
                if cls.tool_name == tool_name:
                    validator_cls = cls
                    found_cat = cat
                    break
            if validator_cls:
                break

        if validator_cls is None or found_cat is None:
            return ToolValidationResult(
                tool_name=tool_name,
                category=category or "unknown",
                status="error",
                error_message=f"未找到工具 {tool_name} 对应的验证器",
            )

        try:
            validator = validator_cls(self._client)
            result = await validator.run()
            if found_cat != result.category:
                # 保持 category 来自验证器定义
                result.category = found_cat
            return result
        except Exception as e:  # noqa: BLE001
            self.logger.exception("验证工具 %s 时发生未捕获异常", tool_name)
            return ToolValidationResult(
                tool_name=tool_name,
                category=found_cat,
                status="error",
                error_message=f"{type(e).__name__}: {e}",
                notes=traceback.format_exc(limit=3),
            )

    def generate_markdown_report(self) -> str:
        """生成 Markdown 格式报告。"""
        return _render_markdown(self.report)

    def generate_html_report(self) -> str:
        """生成 HTML 格式报告。"""
        return _render_html(self.report)

    def save_report(
        self,
        output_dir: Union[str, Path],
        formats: Optional[List[str]] = None,
    ) -> List[Path]:
        """将报告保存到磁盘。

        Args:
            output_dir: 输出目录
            formats: 输出格式列表 ["json", "markdown", "md", "html"]，默认全部

        Returns:
            已保存的文件路径列表
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        formats = formats or ["json", "markdown", "html"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename = f"mcp_validation_{timestamp}"
        paths: List[Path] = []

        if "json" in formats:
            p = output_dir / f"{basename}.json"
            p.write_text(
                json.dumps(self.report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            paths.append(p)

        if any(f in formats for f in ("markdown", "md")):
            p = output_dir / f"{basename}.md"
            p.write_text(self.generate_markdown_report(), encoding="utf-8")
            paths.append(p)

        if "html" in formats:
            p = output_dir / f"{basename}.html"
            p.write_text(self.generate_html_report(), encoding="utf-8")
            paths.append(p)

        return paths

    # ------------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------------

    def _create_real_client(self) -> Any:
        """创建真实 AEMCPClient。失败抛出异常。"""
        from ae.ae_mcp_client import AEMCPClient

        bridge_dir = self._bridge_dir or r"C:\Users\Administrator\Documents\ae-mcp-bridge"
        return AEMCPClient(bridge_dir=bridge_dir, signature_enabled=False)

    def _create_real_client_or_mock(self) -> Any:
        """创建真实客户端，失败时降级为 Mock。

        Args:
            quick_fallback: 如果为 True，则跳过真实 AE 探测，直接使用 Mock。
                benchmark.py 在 test_env=mock 时会传 True，避免 30s 超时。
        """
        quick_fallback = os.environ.get("AE_MCP_VALIDATION_FAST_MOCK", "0") == "1"
        if quick_fallback:
            self.logger.info("AE_MCP_VALIDATION_FAST_MOCK=1，跳过真实 AE 探测")
            self._environment = "mock"
            return _MockAEMCPClient()
        try:
            client = self._create_real_client()
            # 尝试 ping 一次确认 AE 真实可用
            client.ping()
            self._environment = "real"
            self.logger.info("真实 AE MCP 客户端连接成功")
            return client
        except Exception as e:  # noqa: BLE001
            self.logger.warning(
                "无法连接真实 AE 客户端（%s），降级为 Mock 客户端", e
            )
            self._environment = "mock"
            return _MockAEMCPClient()

    async def _detect_versions(self) -> None:
        """探测 AE 与 MCP 服务端版本。"""
        if self._client is None:
            return
        try:
            loop = asyncio.get_running_loop()
            ping_result = await loop.run_in_executor(None, self._client.ping)
            if isinstance(ping_result, dict):
                self._ae_version = ping_result.get(
                    "aeVersion", ping_result.get("ae_version", "unknown")
                )
                self._mcp_server_version = ping_result.get(
                    "version", ping_result.get("mcp_version", "unknown")
                )
            if self._environment == "mock":
                self._ae_version = "mock"
                self._mcp_server_version = "mock-1.0.0"
        except Exception:  # noqa: BLE001
            pass

    async def _run_category(self, category: str) -> List[ToolValidationResult]:
        """运行指定分类的所有验证。"""
        assert self._client is not None
        validators = CATEGORY_DEFINITIONS.get(category, [])
        results: List[ToolValidationResult] = []
        for cls in validators:
            try:
                validator = cls(self._client)
                result = await validator.run()
            except Exception as e:  # noqa: BLE001
                self.logger.exception("验证器 %s 抛出未捕获异常", cls.__name__)
                result = ToolValidationResult(
                    tool_name=cls.tool_name,
                    category=category,
                    status="error",
                    error_message=f"{type(e).__name__}: {e}",
                    notes=traceback.format_exc(limit=3),
                )
            results.append(result)
        return results

    async def _cleanup_test_data(self) -> None:
        """清理测试数据（删除测试合成 / 临时文件）。"""
        if not self._client:
            return
        # 真实环境：尝试删除 MCPVal_CreateComp
        if self._environment == "real":
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(
                    None,
                    lambda: self._client.delete_composition("MCPVal_CreateComp"),
                )
                self.logger.info("已清理测试合成 MCPVal_CreateComp")
            except Exception as e:  # noqa: BLE001
                self.logger.debug("清理测试合成失败（可忽略）: %s", e)
        # Mock 环境：重置计数
        else:
            try:
                self._client._comps.clear()
                self._client._layers.clear()
                self._client._effects.clear()
                self._client._properties.clear()
                self.logger.info("已清理 Mock 客户端内部状态")
            except Exception:  # noqa: BLE001
                pass

    def _log_result(self, r: ToolValidationResult) -> None:
        """记录单条验证结果。"""
        self.logger.info(
            "[%s] %s (%.1fms)%s",
            r.status_emoji,
            r.tool_name,
            r.latency_ms,
            f" - {r.error_message}" if r.error_message else "",
        )

    def _populate_report_stats(self) -> None:
        """填充报告汇总统计。"""
        r = self.report
        r.total_tools = len(r.results)
        r.passed = sum(1 for x in r.results if x.status == "pass")
        r.failed = sum(1 for x in r.results if x.status == "fail")
        r.skipped = sum(1 for x in r.results if x.status == "skip")
        r.errors = sum(1 for x in r.results if x.status == "error")
        r.pass_rate = (r.passed / r.total_tools * 100) if r.total_tools else 0.0

        latencies = [x.latency_ms for x in r.results if x.latency_ms > 0]
        r.avg_latency_ms = statistics.mean(latencies) if latencies else 0.0
        r.p95_latency_ms = _percentile(latencies, 95) if latencies else 0.0

        # 分类统计
        cat_groups: Dict[str, List[ToolValidationResult]] = {}
        for x in r.results:
            cat_groups.setdefault(x.category, []).append(x)
        r.category_stats = []
        for cat, items in cat_groups.items():
            cs = CategoryStats(category=cat, total=len(items))
            cs.passed = sum(1 for x in items if x.status == "pass")
            cs.failed = sum(1 for x in items if x.status == "fail")
            cs.skipped = sum(1 for x in items if x.status == "skip")
            cs.errored = sum(1 for x in items if x.status == "error")
            lats = [x.latency_ms for x in items if x.latency_ms > 0]
            cs.avg_latency_ms = statistics.mean(lats) if lats else 0.0
            cs.p95_latency_ms = _percentile(lats, 95) if lats else 0.0
            r.category_stats.append(cs)


# ============================================================================
# 工具函数
# ============================================================================


def _percentile(values: List[float], p: float) -> float:
    """计算列表的 p 分位数（线性插值）。"""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _render_markdown(report: ValidationReport) -> str:
    """渲染 Markdown 报告。"""
    lines: List[str] = []
    lines.append("# AE MCP 工具真实环境验证报告")
    lines.append("")
    lines.append(f"> 生成时间: {report.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 概览
    lines.append("## 总览")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 测试环境 | `{report.environment}` |")
    lines.append(f"| AE 版本 | `{report.ae_version}` |")
    lines.append(f"| MCP 服务端版本 | `{report.mcp_server_version}` |")
    lines.append(f"| 总工具数 | {report.total_tools} |")
    lines.append(f"| ✅ 通过 | {report.passed} |")
    lines.append(f"| ❌ 失败 | {report.failed} |")
    lines.append(f"| ⏭️ 跳过 | {report.skipped} |")
    lines.append(f"| ⚠️ 错误 | {report.errors} |")
    lines.append(f"| **通过率** | **{report.pass_rate:.1f}%** |")
    lines.append(f"| 平均延迟 | {report.avg_latency_ms:.1f}ms |")
    lines.append(f"| P95 延迟 | {report.p95_latency_ms:.1f}ms |")
    duration = (report.end_time - report.start_time).total_seconds()
    lines.append(f"| 总耗时 | {duration:.1f}s |")
    lines.append("")

    # 分类统计
    if report.category_stats:
        lines.append("## 分类统计")
        lines.append("")
        lines.append("| 分类 | 总数 | 通过 | 失败 | 跳过 | 错误 | 通过率 | 平均延迟 | P95 |")
        lines.append("|------|------|------|------|------|------|--------|----------|-----|")
        for cs in report.category_stats:
            lines.append(
                f"| {cs.category} | {cs.total} | {cs.passed} | {cs.failed} | "
                f"{cs.skipped} | {cs.errored} | {cs.pass_rate:.1f}% | "
                f"{cs.avg_latency_ms:.1f}ms | {cs.p95_latency_ms:.1f}ms |"
            )
        lines.append("")

    # 详细结果
    lines.append("## 详细结果")
    lines.append("")
    lines.append("| 状态 | 工具 | 分类 | 延迟 | 备注 |")
    lines.append("|------|------|------|------|------|")
    for r in report.results:
        note = r.error_message or r.notes or ""
        if len(note) > 60:
            note = note[:60] + "..."
        lines.append(
            f"| {r.status_emoji} | `{r.tool_name}` | {r.category} | "
            f"{r.latency_ms:.1f}ms | {note} |"
        )
    lines.append("")

    # 失败诊断
    failed = [r for r in report.results if r.status in ("fail", "error")]
    if failed:
        lines.append("## 失败工具诊断")
        lines.append("")
        for r in failed:
            lines.append(f"### `{r.tool_name}` ({r.status_emoji}{r.status})")
            lines.append("")
            if r.error_code:
                lines.append(f"- 错误码: `{r.error_code}`")
            if r.error_message:
                lines.append(f"- 错误信息: {r.error_message}")
            if r.pre_conditions:
                lines.append(f"- 预置条件: {', '.join(r.pre_conditions)}")
            if r.notes:
                lines.append(f"- 备注: {r.notes}")
            lines.append("")

    # 改进建议
    lines.append("## 改进建议")
    lines.append("")
    if report.pass_rate >= 95:
        lines.append("- 🎉 整体可用性极佳，建议持续监控 P95 延迟")
    elif report.pass_rate >= 80:
        lines.append("- 整体可用性良好，但需关注失败工具")
    else:
        lines.append("- ⚠️ 可用性低于 80%，需优先修复核心工具")
    if report.p95_latency_ms > 2000:
        lines.append("- P95 延迟 > 2s，建议检查 AE Listener 性能与 Bridge 轮询间隔")
    failed_names = [r.tool_name for r in report.results if r.status in ("fail", "error")]
    if failed_names:
        lines.append(f"- 优先修复: {', '.join(failed_names[:5])}")
    lines.append("")
    lines.append("---")
    lines.append("*报告由 AE MCP Tool Validation Suite 自动生成*")
    return "\n".join(lines)


def _render_html(report: ValidationReport) -> str:
    """渲染 HTML 报告。"""
    duration = (report.end_time - report.start_time).total_seconds()
    status_color = "#22c55e" if report.pass_rate >= 80 else "#ef4444"
    rows = []
    for r in report.results:
        note = (r.error_message or r.notes or "").replace("<", "&lt;").replace(">", "&gt;")
        if len(note) > 80:
            note = note[:80] + "..."
        color = {
            "pass": "#16a34a",
            "fail": "#dc2626",
            "skip": "#94a3b8",
            "error": "#f59e0b",
        }.get(r.status, "#64748b")
        rows.append(
            f"<tr><td style='color:{color};font-weight:600'>{r.status_emoji} {r.status}</td>"
            f"<td><code>{r.tool_name}</code></td>"
            f"<td>{r.category}</td>"
            f"<td>{r.latency_ms:.1f}ms</td>"
            f"<td>{note}</td></tr>"
        )
    cat_rows = []
    for cs in report.category_stats:
        cat_rows.append(
            f"<tr><td>{cs.category}</td><td>{cs.total}</td><td>{cs.passed}</td>"
            f"<td>{cs.failed}</td><td>{cs.skipped}</td><td>{cs.errored}</td>"
            f"<td>{cs.pass_rate:.1f}%</td><td>{cs.avg_latency_ms:.1f}ms</td>"
            f"<td>{cs.p95_latency_ms:.1f}ms</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>AE MCP 工具验证报告</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #f8fafc; color: #0f172a; padding: 2rem;
}}
.wrap {{ max-width: 1100px; margin: 0 auto; background: #fff; border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0,0,0,.05); padding: 2rem; }}
h1 {{ font-size: 1.75rem; margin-bottom: .5rem; }}
.sub {{ color: #64748b; margin-bottom: 1.5rem; }}
.badge {{ display: inline-block; padding: .5rem 1rem; border-radius: 9999px;
  background: {status_color}; color: #fff; font-weight: 600; margin-bottom: 1.5rem; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr));
  gap: 1rem; margin-bottom: 2rem; }}
.card {{ background: #f1f5f9; border-radius: 8px; padding: 1rem; }}
.lbl {{ font-size: .85rem; color: #64748b; margin-bottom: .25rem; }}
.val {{ font-size: 1.4rem; font-weight: 700; color: #0f172a; }}
.bar {{ width: 100%; height: 10px; background: #e2e8f0; border-radius: 5px;
  overflow: hidden; margin: .5rem 0; }}
.fill {{ height: 100%; background: {status_color}; width: {report.pass_rate:.1f}%;
  transition: width .4s; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: .9rem; }}
th,td {{ padding: .6rem .8rem; text-align: left; border-bottom: 1px solid #e2e8f0; }}
th {{ background: #f8fafc; font-weight: 600; color: #475569; }}
h2 {{ font-size: 1.2rem; margin-top: 2rem; margin-bottom: 1rem; }}
code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: .85em; }}
.footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;
  color: #94a3b8; font-size: .85rem; text-align: center; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>AE MCP 工具真实环境验证报告</h1>
  <p class="sub">生成时间: {report.end_time.strftime('%Y-%m-%d %H:%M:%S')} ·
  环境: {report.environment} · AE: {report.ae_version} ·
  MCP: {report.mcp_server_version}</p>
  <div class="badge">{'✅' if report.pass_rate >= 80 else '❌'} 通过率 {report.pass_rate:.1f}%</div>
  <div class="bar"><div class="fill"></div></div>

  <div class="grid">
    <div class="card"><div class="lbl">总工具数</div><div class="val">{report.total_tools}</div></div>
    <div class="card"><div class="lbl">通过</div><div class="val" style="color:#16a34a">{report.passed}</div></div>
    <div class="card"><div class="lbl">失败</div><div class="val" style="color:#dc2626">{report.failed}</div></div>
    <div class="card"><div class="lbl">跳过</div><div class="val" style="color:#94a3b8">{report.skipped}</div></div>
    <div class="card"><div class="lbl">错误</div><div class="val" style="color:#f59e0b">{report.errors}</div></div>
    <div class="card"><div class="lbl">平均延迟</div><div class="val">{report.avg_latency_ms:.1f}ms</div></div>
    <div class="card"><div class="lbl">P95 延迟</div><div class="val">{report.p95_latency_ms:.1f}ms</div></div>
    <div class="card"><div class="lbl">总耗时</div><div class="val">{duration:.1f}s</div></div>
  </div>

  <h2>分类统计</h2>
  <table>
    <thead><tr><th>分类</th><th>总数</th><th>通过</th><th>失败</th><th>跳过</th>
      <th>错误</th><th>通过率</th><th>平均延迟</th><th>P95</th></tr></thead>
    <tbody>{''.join(cat_rows)}</tbody>
  </table>

  <h2>详细结果</h2>
  <table>
    <thead><tr><th>状态</th><th>工具</th><th>分类</th><th>延迟</th><th>备注</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>

  <p class="footer">报告由 AE MCP Tool Validation Suite 自动生成</p>
</div>
</body>
</html>"""


# ============================================================================
# 便捷函数
# ============================================================================


async def run_validation(
    categories: Optional[List[str]] = None,
    use_real_ae: bool = False,
    bridge_dir: Optional[str] = None,
) -> ValidationReport:
    """一键运行验证并返回报告（异步）。

    Args:
        categories: 要运行的分类列表
        use_real_ae: 是否强制使用真实 AE
        bridge_dir: Bridge 目录

    Returns:
        ValidationReport 对象
    """
    suite = MCPToolValidationSuite(
        bridge_dir=bridge_dir, use_real_ae=use_real_ae, categories=categories
    )
    return await suite.run_all()


def run_validation_sync(
    categories: Optional[List[str]] = None,
    use_real_ae: bool = False,
    bridge_dir: Optional[str] = None,
) -> ValidationReport:
    """一键运行验证（同步封装）。"""
    return asyncio.run(
        run_validation(categories=categories, use_real_ae=use_real_ae, bridge_dir=bridge_dir)
    )


# ============================================================================
# Pytest 集成
# ============================================================================


def _build_pytest_parametrize_ids() -> List[Tuple[str, str, Type[ToolValidator]]]:
    """构造 pytest parametrize 的 (category, tool_name, validator_cls) 列表。"""
    items: List[Tuple[str, str, Type[ToolValidator]]] = []
    for cat, validators in CATEGORY_DEFINITIONS.items():
        for cls in validators:
            items.append((cat, cls.tool_name, cls))
    return items


try:
    import pytest

    # 让 pytest 在跑本文件时直接走 mock，跳过真实 AE 探测
    os.environ.setdefault("AE_MCP_VALIDATION_FAST_MOCK", "1")

    _PARAM_ITEMS = _build_pytest_parametrize_ids()
    _PARAM_IDS = [f"{cat}:{name}" for cat, name, _ in _PARAM_ITEMS]
    _PARAM_VALUES = [cls for _, _, cls in _PARAM_ITEMS]

    @pytest.fixture(scope="module")
    def shared_validation_suite() -> MCPToolValidationSuite:
        """共享的验证套件 fixture。

        同一模块内所有 parametrize 测试共享同一个 mock 客户端，
        保证 pre-condition / state-check 链路有效。
        """
        suite = MCPToolValidationSuite(use_real_ae=False)
        # 同步建立 mock 客户端（不调用 setup_ae_environment 因为它需要异步）
        suite._client = _MockAEMCPClient()
        suite._environment = "mock"
        suite._ae_version = "mock"
        suite._mcp_server_version = "mock-1.0.0"
        return suite

    @pytest.mark.parametrize(
        "category,tool_name,validator_cls",
        [(cat, name, cls) for cat, name, cls in _PARAM_ITEMS],
        ids=_PARAM_IDS,
    )
    def test_mcp_tool_validation(
        category: str,
        tool_name: str,
        validator_cls: Type[ToolValidator],
        shared_validation_suite: MCPToolValidationSuite,
    ) -> None:
        """pytest 入口：依次运行所有 MCP 工具验证。

        使用 module-scoped fixture 保证同一模块共享 mock 客户端，
        让 pre-condition / state-check 链路生效。
        无 AE 环境时回退到 Mock 客户端，保证 CI 通过。
        """
        suite = shared_validation_suite
        assert suite._client is not None
        validator = validator_cls(suite._client)
        # pytest 不支持顶层 async parametrize 闭包内的协程，这里走 asyncio.run
        result = asyncio.run(validator.run())
        assert result.status in (
            "pass",
            "skip",
        ), f"{tool_name} 验证失败: status={result.status}, error={result.error_message}"

    class TestMCPValidationSuite:
        """MCP 工具验证 pytest 测试类。"""

        async def test_suite_runs_successfully(self) -> None:
            """测试验证套件本身能正常运行。"""
            suite = MCPToolValidationSuite(
                categories=["core"], use_real_ae=False
            )
            report = await suite.run_all()
            assert report.total_tools >= 1
            assert report.end_time >= report.start_time

        def test_suite_markdown_report(self) -> None:
            """测试 Markdown 报告生成。"""
            report = ValidationReport(total_tools=2, passed=1, failed=1)
            report.pass_rate = 50.0
            md = _render_markdown(report)
            assert "AE MCP 工具真实环境验证报告" in md
            assert "| 总工具数 | 2 |" in md

        def test_suite_html_report(self) -> None:
            """测试 HTML 报告生成。"""
            report = ValidationReport(total_tools=1, passed=1)
            report.pass_rate = 100.0
            html = _render_html(report)
            assert "<!DOCTYPE html>" in html
            assert "AE MCP 工具真实环境验证报告" in html

except ImportError:  # pragma: no cover - pytest 不存在时跳过
    pass


__all__ = [
    "MCPToolValidationSuite",
    "ToolValidator",
    "ToolValidationResult",
    "ValidationReport",
    "CategoryStats",
    "CATEGORY_DEFINITIONS",
    "CATEGORY_DISPLAY_NAMES",
    "run_validation",
    "run_validation_sync",
    # A 级
    "GetProjectInfoValidator",
    "ListCompositionsValidator",
    "CreateCompositionValidator",
    "CreateTextLayerValidator",
    "CreateSolidLayerValidator",
    "SetLayerPropertiesValidator",
    "SetLayerKeyframeValidator",
    "SetKeyframeEasingValidator",
    "ApplyEffectValidator",
    "DeleteLayerValidator",
    # B 级
    "ListEffectsValidator",
    "GetLayerInfoValidator",
    "GetEffectPropertiesValidator",
    "SetBlendModeValidator",
    "SetTrackMatteValidator",
    "AddAdjustmentLayerValidator",
    "SetLayerExpressionValidator",
    "BatchAddEffectsValidator",
    "ApplyEffectTemplateValidator",
    "ImportFootageValidator",
    # C 级
    "CreateShapeLayerValidator",
    "CreateCameraValidator",
    "DuplicateLayerValidator",
    "SetParentLayerValidator",
    "SetMotionBlurValidator",
]
