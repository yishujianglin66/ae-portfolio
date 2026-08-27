#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_copy/tool_orchestrator.py
工具链智能编排器 - V2.0

功能:
  - 根据风格JSON生成工具调用序列
  - 集成V4智能编排器
  - 调用unified_tool_integrator真实执行

复用项目:
  - v4_orchestrator.py 的自然语言编排
  - unified_tool_integrator.py 的工具执行
"""

import os
import sys
import json
from typing import Dict, List, Optional, Any

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from v4_orchestrator import V4Orchestrator
    V4_AVAILABLE = True
except ImportError:
    V4_AVAILABLE = False

try:
    from unified_tool_integrator import UnifiedToolIntegrator, ToolConfig, ToolType
    INTEGRATOR_AVAILABLE = True
except ImportError:
    INTEGRATOR_AVAILABLE = False


class ToolOrchestrator:
    """工具链编排器 - V2.0"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        mode: str = "real",
        output_dir: str = None,
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("DUCK_MISS_API_KEY", "") or os.environ.get("DOUBAO_API_KEY", "")
        self.mode = mode
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "output"
        )

        # 初始化V4编排器
        self.v4_orchestrator = None
        if V4_AVAILABLE and self.api_key:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "tool_config.json"
            )
            self.v4_orchestrator = V4Orchestrator(
                api_key=self.api_key,
                default_mode=mode,
                output_dir=self.output_dir,
                config_file=config_path if os.path.exists(config_path) else None,
            )

        # 初始化工具集成器
        self.integrator = None
        if INTEGRATOR_AVAILABLE:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "tool_config.json"
            )
            self.integrator = UnifiedToolIntegrator(
                default_mode=mode,
                output_dir=self.output_dir,
                config_file=config_path if os.path.exists(config_path) else None,
            )

    def generate_tool_sequence(self, style: Dict, input_video: str) -> Dict:
        """根据风格生成工具调用序列"""
        if self.v4_orchestrator:
            return self._generate_with_v4(style, input_video)
        else:
            return self._generate_with_rules(style, input_video)

    def _generate_with_v4(self, style: Dict, input_video: str) -> Dict:
        """使用V4生成工具序列"""
        # 构建自然语言请求
        request = self._build_request_from_style(style, input_video)

        try:
            result = self.v4_orchestrator.run(
                request,
                model="pro",
                dry_run=True,  # 先只生成工作流
            )

            if result.get("success"):
                return {
                    "success": True,
                    "steps": result.get("workflow", {}).get("steps", []),
                    "workflow": result.get("workflow", {}),
                }
            else:
                return {"success": False, "error": result.get("error", "V4生成失败")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _build_request_from_style(self, style: Dict, input_video: str) -> str:
        """从风格描述构建自然语言请求"""
        parts = [f"处理视频 {input_video}"]

        # 色彩
        if style.get("color_temperature"):
            parts.append(f"应用{style['color_temperature']}色调")
        if style.get("color_palette"):
            parts.append(f"主色调为{style['color_palette']}")

        # 节奏
        if style.get("pace"):
            parts.append(f"节奏{style['pace']}")

        # 特效
        if style.get("effects"):
            parts.append(f"添加特效: {', '.join(style['effects'])}")

        # 转场
        if style.get("transitions"):
            parts.append(f"使用{', '.join(style['transitions'])}转场")

        # 字幕
        if style.get("text_style"):
            ts = style["text_style"]
            if ts.get("font"):
                parts.append(f"字幕字体{ts['font']}")
            if ts.get("position"):
                parts.append(f"字幕位置{ts['position']}")

        # 输出
        parts.append(f"输出到 {self.output_dir}")

        return "，".join(parts)

    @staticmethod
    def _has_toolchain() -> bool:
        """Phase1 ToolchainManager 是否可导入（兼容两条候选路径）"""
        try:
            from toolchain_manager import ToolchainManager  # noqa: F401
            return True
        except ImportError:
            try:
                from tools.toolchain_manager import ToolchainManager  # noqa: F401
                return True
            except ImportError:
                return False

    def execute_tool_sequence(self, steps: List[Dict], input_video: str = "") -> Dict:
        """执行工具序列

        收口：优先走 Phase1 已验证的 ToolchainManager（ffmpeg 真实出片，
        Topaz/AE 无 CLI/工程时诚实降级），unified_tool_integrator 仅作回退。
        返回字典同时携带 status/success 双字段以兼容旧调用方。
        """
        # 优先：Phase1 引擎（统一执行出口，消除三引擎碎片化）
        if self._has_toolchain():
            res = self.execute_via_toolchain(steps, input_video, mode=self.mode)
            res["status"] = "success" if res.get("success") else "failed"
            return res

        # 回退：旧 unified_tool_integrator 路径（仅 ToolchainManager 不可用时）
        if not self.integrator:
            return {"success": False, "status": "failed",
                    "error": "ToolchainManager 与 Integrator 均不可用"}

        # 将步骤转换为工作流预设
        preset_id = "style_copy_custom"
        preset = {
            "id": preset_id,
            "name": "风格复制自定义工作流",
            "description": "基于风格分析的工具序列",
            "category": "style_copy",
            "steps": steps,
        }

        # 注册临时预设
        self.integrator._external_presets[preset_id] = preset

        # 执行工作流
        result = self.integrator.run_workflow(preset_id)

        return result.to_dict()

    def run_style_copy(self, style: Dict, input_video: str, execute: bool = True) -> Dict:
        """
        完整流程：风格分析 → 工具序列生成 → 执行

        Args:
            style: 风格描述字典
            input_video: 输入视频路径
            execute: 是否真实执行

        Returns:
            结果字典
        """
        # Step 1: 生成工具序列
        seq_result = self.generate_tool_sequence(style, input_video)

        if not seq_result.get("success"):
            return seq_result

        steps = seq_result.get("steps", [])

        if not execute:
            return {
                "success": True,
                "dry_run": True,
                "steps": steps,
                "workflow": seq_result.get("workflow", {}),
            }

        # Step 2: 执行工具序列（收口到 Phase1 ToolchainManager）
        exec_result = self.execute_tool_sequence(steps, input_video)

        return {
            "success": exec_result.get("status") == "success" or bool(exec_result.get("success")),
            "steps": steps,
            "result": exec_result,
        }

    def run_style_copy_via_toolchain(self, style: Dict, input_video: str = "",
                                     mode: str = None) -> Dict:
        """统一入口：风格 → 规则编排 → Phase1 ToolchainManager 真实执行

        将 analyze + orchestrate + execute 三步收口为单一出口，避免分散调用
        造成执行引擎碎片化。mode 缺省继承实例 mode。
        """
        mode = mode or self.mode
        seq = self.generate_tool_sequence(style, input_video)
        if not seq.get("success"):
            return seq
        return self.execute_via_toolchain(seq["steps"], input_video, mode=mode)

    def _generate_with_rules(self, style: Dict, input_video: str) -> Dict:
        """使用规则生成工具序列"""
        steps = []
        base_name = os.path.splitext(input_video)[0]

        # 1. 画质增强
        if style.get("effects"):
            effects = style["effects"]
            if any(e in ["glow", "film_grain", "cinematic", "vintage"] for e in effects):
                steps.append({
                    "step_id": "step_1",
                    "name": "画质增强",
                    "tool": "topaz_video_ai",
                    "operation": "enhance",
                    "params": {
                        "input_file": input_video,
                        "output_file": f"{base_name}_enhanced.mp4",
                        "model": "proteus",
                    },
                    "depends_on": [],
                })

        # 2. 调色
        steps.append({
            "step_id": "step_2",
            "name": "风格调色",
            "tool": "ffmpeg",
            "operation": "transcode",
            "params": {
                "input_file": input_video,
                "output_file": f"{base_name}_graded.mp4",
                "filters": self._get_ffmpeg_filters(style),
            },
            "depends_on": ["step_1"] if len(steps) > 0 else [],
        })

        # 3. 字幕
        if style.get("text_style"):
            ts = style["text_style"]
            steps.append({
                "step_id": "step_3",
                "name": "添加字幕",
                "tool": "after_effects",
                "operation": "add_text_layer",
                "params": {
                    "text": ts.get("text", ""),
                    "font_size": ts.get("font_size", 72),
                    "position": ts.get("position", "bottom"),
                },
                "depends_on": ["step_2"],
            })

        # 4. 最终输出
        steps.append({
            "step_id": "step_4",
            "name": "最终合成",
            "tool": "ffmpeg",
            "operation": "transcode",
            "params": {
                "input_file": f"{base_name}_graded.mp4",
                "output_file": f"{self.output_dir}/style_copy_final.mp4",
                "codec": "libx264",
            },
            "depends_on": ["step_3"] if len(steps) > 2 else ["step_2"],
        })

        return {"success": True, "steps": steps}

    def _get_ffmpeg_filters(self, style: Dict) -> List[str]:
        """获取FFmpeg滤镜列表"""
        filters = []

        # 对比度
        contrast = style.get("contrast", "medium")
        if contrast == "high":
            filters.append("eq=contrast=1.3:brightness=0.05")
        elif contrast == "low":
            filters.append("eq=contrast=0.85")

        # 色温
        temp = style.get("color_temperature", "neutral")
        if temp == "warm":
            filters.append("colorbalance=rs=0.1:gs=0:bs=-0.1")
        elif temp == "cool":
            filters.append("colorbalance=rs=-0.1:gs=0:bs=0.1")

        # 节奏
        pace = style.get("pace", "medium")
        if pace == "fast":
            filters.append("setpts=0.7*PTS")
        elif pace == "slow":
            filters.append("setpts=1.4*PTS")

        return filters

    def execute_via_toolchain(self, steps: List[Dict], input_video: str = "",
                              mode: str = "auto") -> Dict:
        """将规则编排步骤经 Phase1 已验证的 ToolchainManager 执行（ffmpeg 真实出片）

        步骤参数名映射: input_file->input_path, output_file->output_path。
        支持: ffmpeg(transcode 带风格滤镜, 真实执行),
              topaz_video_ai/after_effects(无 CLI 或缺少工程时诚实降级 simulate)。
        """
        try:
            from toolchain_manager import ToolchainManager
        except ImportError:
            try:
                from tools.toolchain_manager import ToolchainManager
            except ImportError:
                return {"success": False, "error": "ToolchainManager 不可用（Phase1 引擎缺失）"}

        mgr = ToolchainManager()
        results = []
        output_files = []
        step_map = {
            ("topaz_video_ai", "enhance"): ("topaz_video_ai", "enhance"),
            ("ffmpeg", "transcode"): ("ffmpeg", "transcode"),
            ("after_effects", "add_text_layer"): ("after_effects", "render_comp"),
        }
        for step in steps:
            tool = step.get("tool", "")
            op = step.get("operation", "")
            p = step.get("params", {}) or {}
            t_tool, t_op = step_map.get((tool, op), (tool, op))
            params = {}
            params["input_path"] = p.get("input_file") or p.get("input_path") or ""
            params["output_path"] = p.get("output_file") or p.get("output_path") or ""
            if p.get("filters"):
                params["filters"] = p["filters"]
            if p.get("codec"):
                params["codec"] = p["codec"]
            # after_effects 真实渲染需工程文件；无则提供占位以触发诚实降级 simulate
            if t_tool == "after_effects":
                params["project_path"] = input_video or "dummy.aep"
                params["comp_name"] = p.get("text", "main")
            try:
                res = mgr.execute_tool(t_tool, t_op, params, mode=mode)
                results.append({
                    "step": step.get("step_id"), "tool": t_tool, "operation": t_op,
                    "success": res.success, "mode": res.mode_used,
                    "output": res.output_path, "error": res.error,
                })
                if res.success and res.output_path:
                    output_files.append(res.output_path)
            except Exception as e:
                results.append({
                    "step": step.get("step_id"), "tool": t_tool, "operation": t_op,
                    "success": False, "mode": "error", "output": None, "error": str(e),
                })

        # 写运行清单（非致命）
        try:
            from pathlib import Path as _P
            import time as _t, json as _j
            out_dir = _P("output/workflow_runs")
            out_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "engine": "toolchain_manager", "mode": mode,
                "steps": results, "output_files": output_files,
                "generated_at": _t.strftime("%Y-%m-%dT%H:%M:%S", _t.localtime()),
            }
            path = out_dir / f"style_copy_{int(_t.time())}.json"
            path.write_text(_j.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            output_files.append(str(path))
        except Exception:
            pass

        return {
            "success": all(r["success"] for r in results) if results else False,
            "engine": "toolchain_manager",
            "steps": results,
            "output_files": output_files,
        }

    def list_available_tools(self) -> Dict[str, Any]:
        """列出可用工具"""
        if self.integrator:
            return self.integrator.get_all_tools_info()
        return {}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="工具链编排器")
    parser.add_argument("style_json", help="风格JSON文件")
    parser.add_argument("input_video", help="输入视频路径")
    parser.add_argument("--execute", "-e", action="store_true", help="真实执行")
    parser.add_argument("--mode", "-m", default="real", help="执行模式")

    args = parser.parse_args()

    with open(args.style_json, "r", encoding="utf-8") as f:
        style = json.load(f)

    orchestrator = ToolOrchestrator(mode=args.mode)
    result = orchestrator.run_style_copy(
        style, args.input_video, execute=args.execute
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()