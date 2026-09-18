"""puppet-automation AE 引擎适配器。

将 puppet-automation/src/engines/ae/engine.py 中的 AEEngine
封装为与 AEMCPClient 一致的同步 API（_execute 风格）。

设计要点：
1. **动态导入**：puppet-automation 是独立子项目，不强制依赖。
   适配器通过 ``importlib.util`` 按需加载，缺失时 ``is_available()`` 返回 False。
2. **同步 / 异步桥接**：AEEngine 是 async API，本适配器暴露同步方法。
   内部使用 ``asyncio.run`` 兼容同步调用上下文。
3. **结果归一化**：将 ``EngineResult`` 转换为与 MCP 同构的 dict 协议，
   让上层用统一的字段访问返回数据。
4. **可注入**：通过构造函数注入引擎实例或工厂，便于测试。

典型用法：
    >>> adapter = PuppetEngineAdapter()
    >>> if adapter.is_available():
    ...     result = adapter.create_composition("MyComp", 1920, 1080)
    ...     print(result)
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 基础适配器抽象
# ---------------------------------------------------------------------------


class BaseAEAdapter:
    """AE 通道适配器抽象基类。

    所有具体通道（puppet-automation / MCP）必须实现以下方法。
    方法签名必须与 AEMCPClient 兼容（camelCase 参数内部转为 snake_case）。
    """

    name: str = "base"

    # 通道能力声明
    supports_gui: bool = False
    requires_gui: bool = False

    def is_available(self) -> bool:
        """通道是否可用（引擎文件存在、依赖可导入、AE 已安装等）。"""
        return False

    # -- 合成管理 --
    def create_composition(
        self,
        name: str,
        width: int,
        height: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("create_composition")

    def list_compositions(self) -> list[dict[str, Any]]:
        return self._not_implemented("list_compositions")

    # -- 图层创建 --
    def create_text_layer(
        self,
        comp_name: str,
        text: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("create_text_layer")

    def create_solid_layer(
        self,
        comp_name: str,
        color: list[float],
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("create_solid_layer")

    def create_shape_layer(
        self,
        comp_name: str,
        shape_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("create_shape_layer")

    def add_adjustment_layer(
        self,
        comp_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("add_adjustment_layer")

    # -- 图层属性 --
    def set_layer_properties(
        self,
        comp_name: str,
        layer_index: int,
        **properties: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("set_layer_properties")

    def set_blend_mode(
        self,
        comp_name: str,
        layer_index: int,
        blend_mode: str,
    ) -> dict[str, Any]:
        return self._not_implemented("set_blend_mode")

    def set_track_matte(
        self,
        comp_name: str,
        layer_index: int,
        matte_type: str,
    ) -> dict[str, Any]:
        return self._not_implemented("set_track_matte")

    def set_parent_layer(
        self,
        comp_name: str,
        layer_index: int,
        parent_index: int,
    ) -> dict[str, Any]:
        return self._not_implemented("set_parent_layer")

    # -- 动画 --
    def set_layer_keyframe(
        self,
        comp_name: str,
        layer_index: int,
        property_name: str,
        time: float,
        value: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("set_layer_keyframe")

    def set_keyframe_easing(
        self,
        comp_name: str,
        layer_index: int,
        property_path: str,
        key_index: int,
        easing_type: str,
    ) -> dict[str, Any]:
        return self._not_implemented("set_keyframe_easing")

    def set_layer_expression(
        self,
        comp_name: str,
        layer_index: int,
        property_name: str,
        expression: str,
    ) -> dict[str, Any]:
        return self._not_implemented("set_layer_expression")

    # -- 效果 --
    def apply_effect(
        self,
        comp_name: str,
        layer_index: int,
        effect_name: str,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._not_implemented("apply_effect")

    def apply_effect_template(
        self,
        comp_name: str,
        layer_index: int,
        template_name: str,
    ) -> dict[str, Any]:
        return self._not_implemented("apply_effect_template")

    def batch_add_effects(
        self,
        comp_name: str,
        layer_index: int,
        effects: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._not_implemented("batch_add_effects")

    # -- 蒙版 --
    def set_layer_mask(
        self,
        comp_name: str,
        layer_index: int,
        **mask_params: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("set_layer_mask")

    # -- 渲染 --
    def render(
        self,
        comp_name: str,
        output_path: str,
        format: str = "h264",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("render")

    # -- 高级 --
    def execute_atom_script(
        self,
        script: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        return self._not_implemented("execute_atom_script")

    # -- 内部辅助 --
    def _not_implemented(self, method_name: str) -> dict[str, Any]:
        """返回未实现标记。"""
        return {
            "success": False,
            "error": f"method '{method_name}' not implemented in {self.name}",
            "channel": self.name,
        }


# ---------------------------------------------------------------------------
# puppet-automation 适配器
# ---------------------------------------------------------------------------


class PuppetEngineAdapter(BaseAEAdapter):
    """puppet-automation AE 引擎适配器。

    将 ``AEEngine`` 暴露的 async API 包装为同步 dict 接口，
    内部维护独立的 asyncio 事件循环（通过 ``asyncio.run``）。

    Attributes:
        name: 通道名称 ``"puppet"``
        supports_gui: False（aerender 是无界面渲染）
        requires_gui: False
    """

    name = "puppet"
    supports_gui = False
    requires_gui = False

    # 预留给 UnitTest 注入的工厂
    _engine_factory: Callable[[], Any] | None = None

    def __init__(
        self,
        ae_exe_path: str | None = None,
        render_path: str | None = None,
        project_root: str | None = None,
        engine: Any = None,
    ) -> None:
        """初始化 puppet-automation 适配器。

        Args:
            ae_exe_path: aerender.exe 路径。None 时使用默认 ``settings.aerender_path``。
            render_path: 渲染输出目录。None 时不强制。
            project_root: puppet-automation 项目根目录。
                None 时按本仓库布局推断 ``./puppet-automation``。
            engine: 已构造好的 AEEngine 实例（注入，主要用于测试）。
        """
        self._ae_exe_path = ae_exe_path
        self._render_path = render_path
        self._project_root = project_root
        self._engine_override = engine
        self._engine: Any | None = None
        self._module_loaded = False
        self._load_error: str | None = None

    # ------------------------------------------------------------------
    # 引擎加载
    # ------------------------------------------------------------------

    def _ensure_engine(self) -> Any:
        """确保引擎实例已加载并返回。"""
        if self._engine is not None:
            return self._engine
        if self._engine_override is not None:
            self._engine = self._engine_override
            return self._engine
        if self._engine_factory is not None:
            self._engine = self._engine_factory()
            return self._engine

        module = self._import_engine_module()
        # 构造 AEEngine
        kwargs: dict[str, Any] = {}
        if self._ae_exe_path:
            kwargs["executable_path"] = self._ae_exe_path
        engine_cls = module.AEEngine
        self._engine = engine_cls(**kwargs)
        return self._engine

    def _import_engine_module(self) -> Any:
        """动态导入 puppet-automation AE 引擎模块。

        Returns:
            包含 ``AEEngine`` 类的模块对象。

        Raises:
            ImportError: 引擎模块无法加载。
        """
        if self._module_loaded:
            return self._engine.__class__.__module__ and __import__(
                self._engine.__class__.__module__
            )

        project_root = Path(
            self._project_root
            or Path(__file__).resolve().parents[2] / "puppet-automation"
        )
        engine_path = (
            project_root / "src" / "engines" / "ae" / "engine.py"
        )
        if not engine_path.exists():
            raise ImportError(
                f"puppet-automation AE 引擎文件不存在: {engine_path}"
            )

        # 构造傀儡包名以避免污染 sys.modules
        spec = importlib.util.spec_from_file_location(
            "_puppet_ae_engine", str(engine_path)
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载 puppet-automation AE 引擎: {engine_path}")

        # 确保 src 目录在 path 中（让 ``from ...config import settings`` 工作）
        src_dir = project_root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._module_loaded = True
        return module

    # ------------------------------------------------------------------
    # 异步 → 同步桥接
    # ------------------------------------------------------------------

    def _run_async(self, coro: Any) -> Any:
        """在同步上下文中执行协程。"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已在事件循环中（很少见，例如 Jupyter / 异步测试中）
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    return ex.submit(asyncio.run, coro).result()
        except RuntimeError:
            pass
        return asyncio.run(coro)

    def _to_dict(self, result: Any) -> dict[str, Any]:
        """将 EngineResult 归一化为 dict。"""
        if result is None:
            return {"success": False, "error": "empty result", "channel": self.name}
        if isinstance(result, dict):
            d = dict(result)
            d.setdefault("channel", self.name)
            return d
        # EngineResult
        d: dict[str, Any] = {
            "success": bool(getattr(result, "success", False)),
            "metadata": dict(getattr(result, "metadata", {}) or {}),
            "channel": self.name,
        }
        if getattr(result, "output_path", None) is not None:
            d["output_path"] = str(result.output_path)
        if getattr(result, "error", None):
            d["error"] = str(result.error)
            d["success"] = False
        return d

    # ------------------------------------------------------------------
    # 通道能力
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """puppet-automation 引擎是否可用。

        判定条件：
        1. aerender.exe 存在；或
        2. 显式注入了 engine；或
        3. 工厂方法已配置。
        """
        if self._engine_override is not None or self._engine_factory is not None:
            return True
        try:
            engine = self._ensure_engine()
            return bool(getattr(engine, "executable_path", None)) and Path(
                str(engine.executable_path)
            ).exists()
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)
            logger.debug("puppet-automation 适配器不可用: %s", exc)
            return False

    # ------------------------------------------------------------------
    # 合成管理
    # ------------------------------------------------------------------

    def create_composition(
        self,
        name: str,
        width: int,
        height: int,
        fps: float = 30.0,
        duration: float = 10.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """创建合成（puppet-automation 实现）。

        Args:
            name: 合成名称
            width: 宽度（像素）
            height: 高度（像素）
            fps: 帧率
            duration: 时长（秒）
            **kwargs: 透传参数（如 ``project_path``）
        """
        engine = self._ensure_engine()
        result = self._run_async(
            engine.create_comp(
                name=name,
                width=int(width),
                height=int(height),
                fps=float(fps),
                duration=float(duration),
                project_path=kwargs.get("project_path"),
            )
        )
        return self._to_dict(result)

    def list_compositions(self) -> list[dict[str, Any]]:
        """列出当前项目中的所有合成（puppet 实现）。

        Returns:
            合成信息列表（空列表表示不可用或项目未打开）。
        """
        try:
            engine = self._ensure_engine()
        except Exception as exc:  # noqa: BLE001
            logger.warning("puppet-automation 引擎不可用: %s", exc)
            return []
        # 通过 inline script 获取合成清单
        script = """
(function() {
    var comps = [];
    for (var i = 1; i <= app.project.numItems; i++) {
        var item = app.project.item(i);
        if (item instanceof CompItem) {
            comps.push({
                name: item.name,
                id: item.id,
                width: item.width,
                height: item.height,
                duration: item.duration,
                frameRate: item.frameRate,
                numLayers: item.numLayers
            });
        }
    }
    return JSON.stringify({success: true, compositions: comps});
})();
"""
        result = self._run_async(engine.run_script(script))
        d = self._to_dict(result)
        if d.get("success") and "stdout" in d.get("metadata", {}):
            try:
                import json as _json
                payload = _json.loads(d["metadata"]["stdout"])
                if payload.get("compositions"):
                    return payload["compositions"]
            except Exception:  # noqa: BLE001
                pass
        return []

    # ------------------------------------------------------------------
    # 图层创建
    # ------------------------------------------------------------------

    def create_text_layer(
        self,
        comp_name: str,
        text: str,
        layer_name: str | None = None,
        font_size: float | None = None,
        fill_color: list[float] | None = None,
        position: list[float] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """创建文字图层（puppet 实现）。

        puppet-automation 通过 ``add_layer(layer_type='text')`` 间接实现。
        """
        engine = self._ensure_engine()
        result = self._run_async(
            engine.add_layer(
                comp_name=comp_name,
                layer_type="text",
                name=layer_name or text,
                position=kwargs.get("position"),
                project_path=kwargs.get("project_path"),
                text=text,
                fontSize=font_size,
                fillColor=fill_color,
            )
        )
        return self._to_dict(result)

    def create_solid_layer(
        self,
        comp_name: str,
        color: list[float],
        layer_name: str | None = None,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        engine = self._ensure_engine()
        result = self._run_async(
            engine.add_layer(
                comp_name=comp_name,
                layer_type="solid",
                name=layer_name or "Solid",
                position=kwargs.get("position"),
                project_path=kwargs.get("project_path"),
                color=color,
                width=width,
                height=height,
            )
        )
        return self._to_dict(result)

    def create_shape_layer(
        self,
        comp_name: str,
        shape_type: str,
        layer_name: str | None = None,
        fill_color: list[float] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        engine = self._ensure_engine()
        result = self._run_async(
            engine.add_layer(
                comp_name=comp_name,
                layer_type="shape",
                name=layer_name or "Shape",
                position=kwargs.get("position"),
                project_path=kwargs.get("project_path"),
                shapeType=shape_type,
                fillColor=fill_color,
            )
        )
        return self._to_dict(result)

    def add_adjustment_layer(
        self,
        comp_name: str,
        layer_name: str = "Adjustment",
        effects: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        engine = self._ensure_engine()
        result = self._run_async(
            engine.add_adjustment_layer(
                comp_name=comp_name,
                name=layer_name,
                effects=effects,
                position=kwargs.get("position"),
                project_path=kwargs.get("project_path"),
            )
        )
        return self._to_dict(result)

    # ------------------------------------------------------------------
    # 图层属性
    # ------------------------------------------------------------------

    def set_layer_properties(
        self,
        comp_name: str,
        layer_index: int,
        **properties: Any,
    ) -> dict[str, Any]:
        """批量设置图层属性（puppet 实现）。

        通过 ``set_keyframes`` 与 inline 脚本组合完成；本方法支持直接传
        ``{position: [...], opacity: 50, ...}`` 形式属性，转换成关键帧调用。
        """
        engine = self._ensure_engine()
        if not properties:
            return {"success": False, "error": "无属性可设置", "channel": self.name}
        last_result: dict[str, Any] = {"success": True, "channel": self.name}
        for prop_name, prop_value in properties.items():
            property_path = f"Transform/{prop_name.capitalize()}"
            keyframes = [{"time": 0.0, "value": prop_value, "easingType": "linear"}]
            res = self._run_async(
                engine.set_keyframes(
                    comp_name=comp_name,
                    layer_index=int(layer_index),
                    property_path=property_path,
                    keyframes=keyframes,
                )
            )
            d = self._to_dict(res)
            if not d.get("success"):
                last_result = d
                return d
        return last_result

    def set_blend_mode(
        self,
        comp_name: str,
        layer_index: int,
        blend_mode: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        engine = self._ensure_engine()
        result = self._run_async(
            engine.set_blend_mode(
                comp_name=comp_name,
                layer_index=int(layer_index),
                mode=blend_mode,
                project_path=kwargs.get("project_path"),
            )
        )
        return self._to_dict(result)

    def set_track_matte(
        self,
        comp_name: str,
        layer_index: int,
        matte_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        engine = self._ensure_engine()
        result = self._run_async(
            engine.set_track_matte(
                comp_name=comp_name,
                layer_index=int(layer_index),
                matte_type=matte_type,
                project_path=kwargs.get("project_path"),
            )
        )
        return self._to_dict(result)

    def set_parent_layer(
        self,
        comp_name: str,
        layer_index: int,
        parent_index: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """设置父图层（puppet 通过 inline script）。"""
        engine = self._ensure_engine()
        script = f"""
(function() {{
    for (var i = 1; i <= app.project.numItems; i++) {{
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === {json_repr(comp_name)}) {{
            if ({int(layer_index)} < 1 || {int(layer_index)} > item.numLayers) {{
                return JSON.stringify({{error: true, message: "layer index invalid"}});
            }}
            item.layer({int(layer_index)}).parent = item.layer({int(parent_index)});
            return JSON.stringify({{success: true, parentIndex: {int(parent_index)}}});
        }}
    }}
    return JSON.stringify({{error: true, message: "comp not found"}});
}})();
"""
        result = self._run_async(engine.run_script(script))
        return self._to_dict(result)

    # ------------------------------------------------------------------
    # 动画
    # ------------------------------------------------------------------

    def set_layer_keyframe(
        self,
        comp_name: str,
        layer_index: int,
        property_name: str,
        time: float,
        value: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        engine = self._ensure_engine()
        # puppet-automation 的 property_path 形如 "Transform/Position"
        property_path = (
            property_name
            if "/" in property_name
            else f"Transform/{property_name.capitalize()}"
        )
        result = self._run_async(
            engine.set_keyframes(
                comp_name=comp_name,
                layer_index=int(layer_index),
                property_path=property_path,
                keyframes=[{"time": float(time), "value": value, "easingType": "linear"}],
                project_path=kwargs.get("project_path"),
            )
        )
        return self._to_dict(result)

    def set_keyframe_easing(
        self,
        comp_name: str,
        layer_index: int,
        property_path: str,
        key_index: int,
        easing_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """puppet 实现：通过对关键帧时间点的最近帧应用缓动。

        实现细节：调用 ``set_keyframes`` 传入单帧指定 easingType，
        适配器在 ``engine.set_keyframes`` 内部已经支持。
        """
        engine = self._ensure_engine()
        script = f"""
(function() {{
    for (var i = 1; i <= app.project.numItems; i++) {{
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === {json_repr(comp_name)}) {{
            if ({int(layer_index)} < 1 || {int(layer_index)} > item.numLayers) {{
                return JSON.stringify({{error: true, message: "layer index invalid"}});
            }}
            var layer = item.layer({int(layer_index)});
            var pathParts = {json_repr(property_path)}.split("/");
            var prop = null;
            if (pathParts[0] === "Transform") {{
                prop = layer.property(pathParts[1]);
            }} else if (pathParts[0].indexOf("Effects") === 0) {{
                var m = pathParts[0].match(/Effects\\((\\d+)\\)/);
                if (m) {{ prop = layer.effect(parseInt(m[1])).property(pathParts[1]); }}
            }}
            if (!prop) {{ return JSON.stringify({{error: true, message: "property invalid"}}); }}
            if ({int(key_index)} < 1 || {int(key_index)} > prop.numKeys) {{
                return JSON.stringify({{error: true, message: "key index invalid"}});
            }}
            var inType = KeyframeInterpolationType.BEZIER;
            var outType = KeyframeInterpolationType.BEZIER;
            var et = {json_repr(easing_type)};
            if (et === "hold") {{ inType = outType = KeyframeInterpolationType.HOLD; }}
            else if (et === "easeIn") {{ outType = KeyframeInterpolationType.LINEAR; }}
            else if (et === "easeOut") {{ inType = KeyframeInterpolationType.LINEAR; }}
            prop.setInterpolationTypeAtKey({int(key_index)}, inType, outType);
            return JSON.stringify({{success: true}});
        }}
    }}
    return JSON.stringify({{error: true, message: "comp not found"}});
}})();
"""
        result = self._run_async(engine.run_script(script))
        return self._to_dict(result)

    def set_layer_expression(
        self,
        comp_name: str,
        layer_index: int,
        property_name: str,
        expression: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """puppet 实现：通过 inline script 设置表达式。"""
        engine = self._ensure_engine()
        property_path = (
            property_name
            if "/" in property_name
            else f"Transform/{property_name.capitalize()}"
        )
        script = f"""
(function() {{
    for (var i = 1; i <= app.project.numItems; i++) {{
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === {json_repr(comp_name)}) {{
            var layer = item.layer({int(layer_index)});
            var pathParts = {json_repr(property_path)}.split("/");
            var prop = null;
            if (pathParts[0] === "Transform") {{
                prop = layer.property(pathParts[1]);
            }} else if (pathParts[0].indexOf("Effects") === 0) {{
                var m = pathParts[0].match(/Effects\\((\\d+)\\)/);
                if (m) {{ prop = layer.effect(parseInt(m[1])).property(pathParts[1]); }}
            }}
            if (!prop) {{ return JSON.stringify({{error: true, message: "property invalid"}}); }}
            prop.expression = {json_repr(expression)};
            return JSON.stringify({{success: true}});
        }}
    }}
    return JSON.stringify({{error: true, message: "comp not found"}});
}})();
"""
        result = self._run_async(engine.run_script(script))
        return self._to_dict(result)

    # ------------------------------------------------------------------
    # 效果
    # ------------------------------------------------------------------

    def apply_effect(
        self,
        comp_name: str,
        layer_index: int,
        effect_name: str,
        settings: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        engine = self._ensure_engine()
        result = self._run_async(
            engine.add_effect(
                comp_name=comp_name,
                layer_index=int(layer_index),
                effect_name=effect_name,
                params=settings,
                project_path=kwargs.get("project_path"),
            )
        )
        return self._to_dict(result)

    def apply_effect_template(
        self,
        comp_name: str,
        layer_index: int,
        template_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """puppet 通道对 .ffx 预设支持较好（``apply_preset``）。"""
        preset_path = kwargs.get("preset_path") or template_name
        engine = self._ensure_engine()
        result = self._run_async(
            engine.apply_preset(
                comp_name=comp_name,
                layer_index=int(layer_index),
                preset_path=preset_path,
                project_path=kwargs.get("project_path"),
            )
        )
        return self._to_dict(result)

    def batch_add_effects(
        self,
        comp_name: str,
        layer_index: int,
        effects: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """批量添加效果（puppet 实现）。"""
        engine = self._ensure_engine()
        applied = 0
        for effect in effects or []:
            res = self._run_async(
                engine.add_effect(
                    comp_name=comp_name,
                    layer_index=int(layer_index),
                    effect_name=effect.get("effect_name") or effect.get("name"),
                    params=effect.get("params") or effect.get("settings"),
                    project_path=kwargs.get("project_path"),
                )
            )
            d = self._to_dict(res)
            if d.get("success"):
                applied += 1
        return {
            "success": applied == len(effects or []),
            "applied": applied,
            "total": len(effects or []),
            "channel": self.name,
        }

    # ------------------------------------------------------------------
    # 蒙版
    # ------------------------------------------------------------------

    def set_layer_mask(
        self,
        comp_name: str,
        layer_index: int,
        shape: str = "rect",
        **mask_params: Any,
    ) -> dict[str, Any]:
        """puppet 实现：通过 inline script 添加蒙版。"""
        engine = self._ensure_engine()
        feathering = mask_params.get("feathering", 0.0)
        opacity = mask_params.get("opacity", 100.0)
        inverted = mask_params.get("inverted", False)
        script = f"""
(function() {{
    for (var i = 1; i <= app.project.numItems; i++) {{
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === {json_repr(comp_name)}) {{
            if ({int(layer_index)} < 1 || {int(layer_index)} > item.numLayers) {{
                return JSON.stringify({{error: true, message: "layer index invalid"}});
            }}
            var layer = item.layer({int(layer_index)});
            var mask = layer.Masks.addProperty({json_repr(shape)});
            mask.feather = [{float(feathering)}, {float(feathering)}];
            mask.opacity = {float(opacity)};
            mask.inverted = {str(bool(inverted)).lower()};
            return JSON.stringify({{success: true, maskIndex: mask.propertyIndex}});
        }}
    }}
    return JSON.stringify({{error: true, message: "comp not found"}});
}})();
"""
        result = self._run_async(engine.run_script(script))
        return self._to_dict(result)

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def render(
        self,
        comp_name: str,
        output_path: str,
        format: str = "h264",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """puppet 通道最适合渲染（aerender CLI）。"""
        engine = self._ensure_engine()
        project_path = kwargs.get("project_path")
        if not project_path:
            return {
                "success": False,
                "error": "render 需要 project_path 参数",
                "channel": self.name,
            }
        # 帧范围
        start_frame = kwargs.get("start_frame")
        end_frame = kwargs.get("end_frame")
        output_module = _resolve_output_module(format)
        if start_frame is not None and end_frame is not None:
            result = self._run_async(
                engine.render_segment(
                    comp_name=comp_name,
                    start_frame=int(start_frame),
                    end_frame=int(end_frame),
                    output_path=output_path,
                    project_path=project_path,
                    output_module=output_module,
                    render_settings=kwargs.get("render_settings", "Best Settings"),
                )
            )
        else:
            result = self._run_async(
                engine.render_comp(
                    project_path=project_path,
                    comp_name=comp_name,
                    output_path=output_path,
                    output_module=output_module,
                    render_settings=kwargs.get("render_settings", "Best Settings"),
                    multiprocess=kwargs.get("multiprocess"),
                    multi_machine=kwargs.get("multi_machine"),
                )
            )
        return self._to_dict(result)

    # ------------------------------------------------------------------
    # 高级
    # ------------------------------------------------------------------

    def execute_atom_script(
        self,
        script: str,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """执行任意 ExtendScript（puppet 实现）。"""
        engine = self._ensure_engine()
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "script_length": len(script),
                "channel": self.name,
            }
        result = self._run_async(
            engine.run_script(script, project_path=kwargs.get("project_path"))
        )
        return self._to_dict(result)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def json_repr(value: Any) -> str:
    """JavaScript 字面量序列化（与 JSON 兼容但处理单引号/True/False）。"""
    import json
    return json.dumps(value, ensure_ascii=False)


def _resolve_output_module(format_name: str) -> str:
    """将友好的格式名映射为 aerender 的输出模块模板。"""
    mapping = {
        "h264": "H.264",
        "h265": "H.265",
        "hevc": "H.265",
        "prores": "Apple ProRes 422",
        "lossless": "Lossless",
        "png": "PNG Sequence",
        "tiff": "TIFF Sequence",
        "jpg": "JPEG Sequence",
        "exr": "OpenEXR Sequence",
        "wav": "Audio Output",
        "mp3": "MP3",
    }
    return mapping.get(format_name.lower(), format_name)


__all__ = [
    "BaseAEAdapter",
    "PuppetEngineAdapter",
]
