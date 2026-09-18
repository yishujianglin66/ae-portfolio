#!/usr/bin/env python3
"""
Phase 4 - 混合任务协调器 (Python 版)

核心职责：
  1. 协调 Silhouette 和 AE 的执行顺序
  2. 管理 Silhouette → AE 的数据传递
  3. 处理执行失败时的降级策略
  4. 提供执行进度回调

执行流程（Hybrid 模式）：
  Phase 1: Silhouette 前置处理（roto/track/paint）
  Phase 2: 数据转换（Silhouette 输出 → AE 可用格式）
  Phase 3: AE 后置处理（导入 Matte + 应用效果）
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar

from intent_router import IntentRouter, TaskRoute

# ---------------------------------------------------------------------------
# 类型变量（用于泛型重试方法）
# ---------------------------------------------------------------------------
T = TypeVar("T")


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class ExecutionOptions:
    """执行选项"""
    source_path: str = ""
    output_dir: str = ""
    enable_fallback: bool = True
    max_retries: int = 3
    retry_delay_ms: int = 2000
    project_context: dict | None = None
    on_progress: Callable | None = None  # (phase: str, progress: float, message: str) -> None


@dataclass
class PhaseResult:
    """单个阶段结果"""
    phase: str  # silhouette | data_transfer | ae | fallback
    status: str  # pending | running | success | error | fallback
    duration_ms: float = 0
    outputs: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class HybridExecutionResult:
    """完整执行结果"""
    status: str  # pending | running | success | error | fallback
    route: TaskRoute | None = None
    phases: list[PhaseResult] = field(default_factory=list)
    silhouette_output: dict | None = None
    ae_script: str = ""
    error: str = ""
    total_duration_ms: float = 0
    used_fallback: bool = False


# ---------------------------------------------------------------------------
# HybridCoordinator
# ---------------------------------------------------------------------------

class HybridCoordinator:
    """
    混合任务协调器 — 协调 Silhouette 与 AE 的执行流程。

    执行流程：
      1. 通过 IntentRouter 获取路由决策
      2. 按路由中的 execution_order 依次执行各阶段
      3. Silhouette 阶段失败时尝试重试，再失败则降级
      4. 数据转换阶段将 Silhouette 输出转换为 AE 可用格式
      5. AE 阶段生成 JSX 脚本（含 Matte 导入、Track Matte 设置、效果应用）
    """

    def __init__(self, intent_router: IntentRouter | None = None) -> None:
        self._router = intent_router or IntentRouter()

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def execute(
        self,
        user_input: str,
        options: ExecutionOptions | None = None,
    ) -> HybridExecutionResult:
        """
        执行完整流程。

        Args:
            user_input: 用户原始输入文本
            options: 执行选项

        Returns:
            HybridExecutionResult 完整执行结果
        """
        start_time = time.time()
        if options is None:
            options = ExecutionOptions()

        max_retries = options.max_retries
        retry_delay = options.retry_delay_ms

        # 1. 路由决策
        route = self._router.route(user_input, options.project_context)
        phases: list[PhaseResult] = []

        # 未知路由，直接返回错误
        if route.type == "unknown":
            return HybridExecutionResult(
                status="error",
                route=route,
                error=route.reason,
                total_duration_ms=(time.time() - start_time) * 1000,
            )

        # 2. 按执行顺序处理
        silhouette_output: dict | None = None
        ae_script: str = ""
        used_fallback = False

        for phase in route.execution_order or []:
            if phase == "silhouette":
                # 带 重试的 Silhouette 执行
                result = self._execute_with_retry(
                    fn=lambda: self._execute_silhouette_phase(route, options),
                    max_retries=max_retries,
                    retry_delay_ms=retry_delay,
                    on_progress=options.on_progress,
                )
                phases.append(result)

                # 如果 Silhouette 失败，尝试降级
                if (result.status != "success"
                        and options.enable_fallback
                        and route.fallback):
                    if options.on_progress:
                        options.on_progress("fallback", 0, route.fallback.get("message", ""))
                    used_fallback = True
                    fallback_result = self._execute_fallback(route, options)
                    phases.append(fallback_result)

                # 读取 Silhouette 输出
                if result.outputs:
                    silhouette_output = self._read_silhouette_output(result.outputs[0])

            if phase == "ae":
                # 数据转换
                if silhouette_output:
                    transfer_result = self._execute_data_transfer(silhouette_output, options)
                    phases.append(transfer_result)

                # AE 执行
                ae_result = self._execute_ae_phase(route, silhouette_output, options)
                phases.append(ae_result)

                if ae_result.outputs and len(ae_result.outputs) > 1:
                    # outputs[0] 是脚本路径，outputs[1] 是脚本内容
                    ae_script = ae_result.outputs[1]

        # 3. 汇总结果
        has_error = any(p.status == "error" for p in phases)
        all_success = all(p.status in ("success", "fallback") for p in phases)

        return HybridExecutionResult(
            status="error" if has_error else ("success" if all_success else "fallback"),
            route=route,
            phases=phases,
            silhouette_output=silhouette_output,
            ae_script=ae_script,
            total_duration_ms=(time.time() - start_time) * 1000,
            used_fallback=used_fallback,
        )

    # ------------------------------------------------------------------
    # Phase 1: Silhouette 执行
    # ------------------------------------------------------------------

    def _execute_silhouette_phase(
        self,
        route: TaskRoute,
        options: ExecutionOptions,
    ) -> PhaseResult:
        """
        执行 Silhouette 阶段。
        调用 SilhouetteExecutor 真正执行 roto/track/paint 操作。
        """
        start = time.time()
        ops = route.silhouette_operations or []

        # 无操作则直接成功
        if not ops:
            return PhaseResult(
                phase="silhouette",
                status="success",
                duration_ms=0,
                outputs=[],
            )

        if options.on_progress:
            options.on_progress("silhouette", 0, "启动 Silhouette 执行...")

        try:
            from silhouette_executor import SilhouetteExecutor

            sil_mode = getattr(self, '_sil_mode', 'auto')
            executor = SilhouetteExecutor(mode=sil_mode)

            outputs = []
            for i, op in enumerate(ops):
                task_type = op.get("taskType", "unknown")
                command = f"silhouette_{task_type}"
                params = {
                    "source_path": options.source_path,
                    "output_path": options.output_dir,
                    **op,
                }

                if options.on_progress:
                    progress = 0.3 + 0.5 * (i / len(ops))
                    options.on_progress("silhouette", progress, f"执行 {command}...")

                result = executor.execute({"command": command, "params": params})

                if result.get("status") == "success":
                    ae_data = result.get("ae_integration_data", {})
                    if ae_data:
                        outputs.append(ae_data)
                elif result.get("status") == "fallback":
                    return PhaseResult(
                        phase="silhouette",
                        status="fallback",
                        duration_ms=(time.time() - start) * 1000,
                        error=result.get("message", "Silhouette 降级"),
                        outputs=[],
                    )
                else:
                    return PhaseResult(
                        phase="silhouette",
                        status="error",
                        duration_ms=(time.time() - start) * 1000,
                        error=result.get("error", result.get("message", "Unknown")),
                        outputs=[],
                    )

            if options.on_progress:
                options.on_progress("silhouette", 1.0, "Silhouette 完成")

            return PhaseResult(
                phase="silhouette",
                status="success",
                duration_ms=(time.time() - start) * 1000,
                outputs=outputs,
            )
        except ImportError:
            # SilhouetteExecutor 不可用时，走降级
            return PhaseResult(
                phase="silhouette",
                status="fallback",
                duration_ms=(time.time() - start) * 1000,
                error="SilhouetteExecutor 不可用",
                outputs=[],
            )
        except Exception as e:
            return PhaseResult(
                phase="silhouette",
                status="error",
                duration_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Phase 2: 数据转换（Silhouette → AE 格式）
    # ------------------------------------------------------------------

    def _execute_data_transfer(
        self,
        silhouette_output: dict,
        options: ExecutionOptions,
    ) -> PhaseResult:
        """执行数据转换阶段，将 Silhouette 输出转为 AE 可用格式"""
        start = time.time()

        try:
            # 生成 AE 集成数据
            ae_data = self._transfer_data(silhouette_output, options)

            # 写入 AE 集成 JSON
            output_base = options.output_dir or "D:/AE-Work/silhouette_output"
            data_path = os.path.join(output_base, "silhouette_to_ae.json")

            # 确保输出目录存在
            os.makedirs(output_base, exist_ok=True)

            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(ae_data, f, ensure_ascii=False, indent=2)

            if options.on_progress:
                options.on_progress("data_transfer", 1.0, "数据转换完成")

            return PhaseResult(
                phase="data_transfer",
                status="success",
                duration_ms=(time.time() - start) * 1000,
                outputs=[data_path],
            )
        except Exception as e:
            return PhaseResult(
                phase="data_transfer",
                status="error",
                duration_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Phase 3: AE 执行
    # ------------------------------------------------------------------

    def _execute_ae_phase(
        self,
        route: TaskRoute,
        silhouette_output: dict | None,
        options: ExecutionOptions,
    ) -> PhaseResult:
        """执行 AE 阶段，生成 JSX 脚本并写入文件"""
        start = time.time()

        try:
            if options.on_progress:
                options.on_progress("ae", 0, "生成 AE 脚本...")

            # 生成 AE JSX 脚本
            jsx_script = self._generate_ae_jsx(route, silhouette_output, options)

            if options.on_progress:
                options.on_progress("ae", 0.5, "执行 AE 脚本...")

            # 写入 JSX 文件
            output_base = options.output_dir or "D:/AE-Work/silhouette_output"
            script_path = os.path.join(output_base, "apply_silhouette_to_ae.jsx")

            # 确保输出目录存在
            os.makedirs(output_base, exist_ok=True)

            with open(script_path, "w", encoding="utf-8") as f:
                f.write(jsx_script)

            if options.on_progress:
                options.on_progress("ae", 1.0, "AE 脚本执行完成")

            return PhaseResult(
                phase="ae",
                status="success",
                duration_ms=(time.time() - start) * 1000,
                outputs=[script_path, jsx_script],
            )
        except Exception as e:
            return PhaseResult(
                phase="ae",
                status="error",
                duration_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # 带重试的执行
    # ------------------------------------------------------------------

    def _execute_with_retry(
        self,
        fn: Callable[[], T],
        max_retries: int,
        retry_delay_ms: int,
        on_progress: Callable | None = None,
    ) -> T:
        """
        带重试的执行。采用指数退避策略，delay * (i+1)。

        Args:
            fn: 要执行的函数
            max_retries: 最大重试次数
            retry_delay_ms: 基础重试延迟（毫秒）
            on_progress: 可选的进度回调

        Returns:
            函数执行结果

        Raises:
            最后一次重试的异常
        """
        last_error: Exception | None = None

        for i in range(max_retries):
            try:
                return fn()
            except Exception as e:
                last_error = e
                if i < max_retries - 1:
                    if on_progress:
                        on_progress("retry", (i + 1) / max_retries, f"重试 {i + 1}/{max_retries}...")
                    # 指数退避：delay * (i+1)
                    delay = (retry_delay_ms * (i + 1)) / 1000.0
                    time.sleep(delay)

        # 所有重试都失败，抛出最后一次的异常
        if last_error is not None:
            raise last_error
        raise RuntimeError("未知重试错误")

    # ------------------------------------------------------------------
    # 降级执行
    # ------------------------------------------------------------------

    def _execute_fallback(
        self,
        route: TaskRoute,
        options: ExecutionOptions,
    ) -> PhaseResult:
        """
        降级执行 — 从 route.fallback 获取 AE 原生替代操作。

        降级策略：
          roto → AE 原生 Mask
          track → AE 原生 Tracker
          paint → AE 原生 Paint
        """
        start = time.time()
        fallback = route.fallback

        if not fallback:
            return PhaseResult(
                phase="fallback",
                status="error",
                duration_ms=(time.time() - start) * 1000,
                error="无可用降级策略",
            )

        if options.on_progress:
            options.on_progress("fallback", 0.5, fallback.get("message", ""))

        # 生成降级 AE 脚本
        jsx_lines: list[str] = []
        jsx_lines.append("// 降级 AE 脚本: Silhouette 不可用")
        jsx_lines.append(f"// 原因: {fallback.get('condition', '')}")
        jsx_lines.append(f"// 提示: {fallback.get('message', '')}")
        jsx_lines.append("(function() {")

        for op in fallback.get("ae_fallback_ops", []):
            match_name = op.get("matchName")
            effect_name = op.get("effectName", "")
            if match_name:
                jsx_lines.append(f'  var fx = comp.layer(1).property("Effects").addProperty("{match_name}");')
                jsx_lines.append(f'  fx.name = "{effect_name}";')

        jsx_lines.append("})();")

        return PhaseResult(
            phase="fallback",
            status="fallback",
            duration_ms=(time.time() - start) * 1000,
            outputs=["\n".join(jsx_lines)],
        )

    # ------------------------------------------------------------------
    # 读取 Silhouette 输出
    # ------------------------------------------------------------------

    def _read_silhouette_output(self, output_path: str) -> dict | None:
        """
        读取 Silhouette 输出文件并校验。

        校验规则：
          - source == "silhouette"
          - 包含 aeIntegration 字段

        Args:
            output_path: Silhouette 输出文件路径

        Returns:
            解析后的字典，校验失败返回 None
        """
        try:
            if not os.path.exists(output_path):
                return None

            with open(output_path, "r", encoding="utf-8") as f:
                raw = f.read()

            data = json.loads(raw)

            # 基础校验：必须是 Silhouette 输出
            if data.get("source") != "silhouette" or not data.get("aeIntegration"):
                return None

            return data
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 生成 AE JSX 脚本
    # ------------------------------------------------------------------

    def _generate_ae_jsx(
        self,
        route: TaskRoute,
        silhouette_output: dict | None,
        options: ExecutionOptions,
    ) -> str:
        """
        生成 AE JSX 脚本（对齐 TS 端 generateAEJSX）。

        根据路由类型和 Silhouette 输出生成不同内容：
          - Roto: 导入 Matte 序列 → 添加到合成 → Track Matte Alpha
          - Track: 创建 Null 层 → 设置 Position/Scale/Rotation 关键帧
          - Paint: 导入修复帧
          - AE 效果: 添加效果
        """
        lines: list[str] = []
        lines.append("// AE JSX 脚本: 由 HybridCoordinator 自动生成")
        lines.append(f"// 任务类型: {route.type}")
        lines.append("(function() {")

        # Silhouette Matte 导入（Roto 场景）
        if silhouette_output and silhouette_output.get("roto"):
            roto = silhouette_output["roto"]
            matte_path = roto.get("matteSequence", "")
            resolution = roto.get("resolution", [1920, 1080])

            lines.append(f'  var mattePath = "{matte_path}";')
            lines.append("  var matteFile = new File(mattePath);")
            lines.append("  if (matteFile.exists) {")
            lines.append("    var io = new ImportOptions(matteFile);")
            lines.append("    io.sequence = true;")
            lines.append("    var matteFootage = app.project.importFile(io);")
            lines.append('    matteFootage.name = "Silhouette_Matte";')
            lines.append("  }")
            lines.append("")

            # 创建合成
            ae_integration = silhouette_output.get("aeIntegration", {})
            comp_name = ae_integration.get("compName", "SilhouetteComp")
            lines.append("  var comp = app.project.items.addComp(")
            lines.append(f'    "{comp_name}",')
            lines.append(f"    {resolution[0]}, {resolution[1]}, 1.0, 4.0, 30.0")
            lines.append("  );")
            lines.append("")

            # 添加 Matte 图层
            lines.append("  var matteLayer = comp.layers.add(matteFootage);")
            lines.append('  matteLayer.name = "Matte";')
            lines.append("")

        # 跟踪数据应用（Track 场景）
        if silhouette_output and silhouette_output.get("tracking"):
            tracking = silhouette_output["tracking"]
            null_name = tracking.get("nullObjectName", "Tracker_Null")
            lines.append("  var nullLayer = comp.layers.addNull();")
            lines.append(f'  nullLayer.name = "{null_name}";')
            lines.append("")

            trackers = tracking.get("trackers", [])
            for tracker in trackers:
                for kf in tracker.get("keyframes", []):
                    frame = kf.get("frame", 0)
                    position = kf.get("position", [0, 0])
                    time_val = f"{frame / 30.0:.4f}"
                    lines.append(f'  nullLayer.property("Position").setValueAtTime({time_val}, [{position[0]}, {position[1]}]);')

                    scale = kf.get("scale")
                    if scale is not None:
                        sc = f"{scale * 100:.2f}"
                        lines.append(f'  nullLayer.property("Scale").setValueAtTime({time_val}, [{sc}, {sc}]);')

                    rotation = kf.get("rotation")
                    if rotation is not None:
                        lines.append(f'  nullLayer.property("Rotation").setValueAtTime({time_val}, {rotation});')

            lines.append("")

        # 修复帧导入（Paint 场景）
        if silhouette_output and silhouette_output.get("paint"):
            paint = silhouette_output["paint"]
            painted_frames = paint.get("paintedFrames", "")
            if painted_frames:
                lines.append(f'  var paintPath = "{painted_frames}";')
                lines.append("  var paintFile = new File(paintPath);")
                lines.append("  if (paintFile.exists) {")
                lines.append("    var paintIo = new ImportOptions(paintFile);")
                lines.append("    paintIo.sequence = true;")
                lines.append("    var paintFootage = app.project.importFile(paintIo);")
                lines.append('    paintFootage.name = "Silhouette_Paint";')
                lines.append("  }")
                lines.append("")

        # AE 效果
        ae_operations = route.ae_operations or []
        for op in ae_operations:
            if op.get("op") == "addEffect" and op.get("effectName"):
                match_name = op.get("matchName") or op["effectName"]
                lines.append(f'  var fx = comp.layer(1).property("Effects").addProperty("{match_name}");')
                lines.append(f'  fx.name = "{op["effectName"]}";')

        # Track Matte 设置（Roto 场景 — 需在效果添加之后）
        if silhouette_output and silhouette_output.get("roto"):
            lines.append("  comp.layer(2).trackMatteType = TrackMatteType.ALPHA;")
            lines.append("  comp.layer(1).enabled = false;")

        lines.append('  $.writeln("[AE] Hybrid 执行完成!");')
        lines.append("})();")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 数据转换（Silhouette → AE 集成数据）
    # ------------------------------------------------------------------

    def _transfer_data(
        self,
        silhouette_output: dict,
        options: ExecutionOptions,
    ) -> dict:
        """
        Silhouette → AE 数据转换。

        输入：SilhouetteOutput（含 roto/tracking/paint/aeIntegration）
        输出：AE 集成数据 JSON（含 mattePath, trackingData, paintFrames, aeIntegration）

        Args:
            silhouette_output: Silhouette 输出数据
            options: 执行选项

        Returns:
            AE 集成数据字典
        """
        roto = silhouette_output.get("roto")
        tracking = silhouette_output.get("tracking")
        paint = silhouette_output.get("paint")

        return {
            "mattePath": roto.get("matteSequence") if roto else None,
            "trackingData": tracking.get("trackers") if tracking else None,
            "paintFrames": paint.get("paintedFrames") if paint else None,
            "aeIntegration": silhouette_output.get("aeIntegration"),
        }
