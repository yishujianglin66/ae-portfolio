#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V4 智能编排器 (V4 Intelligent Orchestrator)
============================================

DeepSeek V4 驱动的工作流智能编排系统。
用户用自然语言描述需求 → V4分析并生成工作流 → 真实执行 → 返回结果。

核心流程:
    用户: "把这个视频超分到4K并加电影调色"
        ↓
    V4分析: 1. Topaz超分 2. FFmpeg调色 3. AE特效
        ↓
    生成工作流JSON（含步骤、工具、参数、依赖）
        ↓
    调用UnifiedToolIntegrator执行
        ↓
    返回执行结果

使用方式:
    from v4_orchestrator import V4Orchestrator
    orchestrator = V4Orchestrator()
    result = orchestrator.run("把input.mp4超分到4K并加调色")
"""

import os
import sys
import json
import time
import uuid
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import requests
except ImportError:
    print("请安装 requests: py -3.11 -m pip install requests")
    sys.exit(1)

from unified_tool_integrator import (
    UnifiedToolIntegrator,
    WorkflowResult,
    StepResult,
    PhaseStatus,
    ExecutionMode,
    ToolType,
)

# ============================================================================
# 配置
# ============================================================================

API_BASE = "https://api.deepseek.com"
FLASH_MODEL = "deepseek-v4-flash"
PRO_MODEL = "deepseek-v4-pro"

ORCHESTRATOR_SYSTEM_PROMPT = """你是AE-Knowledge-Vault项目的V4智能编排器。

你的职责：
1. 分析用户的自然语言需求
2. 从可用工具中选择合适的工具组合
3. 生成可执行的工作流JSON
4. 确保步骤之间的依赖关系正确

可用工具及操作:

| 工具 | tool_id | 支持的操作 |
|------|---------|-----------|
| FFmpeg | ffmpeg | probe, transcode, extract_audio, compress, resize, concat, watermark, extract_frames, create_slideshow, batch_transcode |
| Topaz Video AI | topaz_video_ai | enhance, denoise, interpolate, stabilize, face_enhance, batch_enhance, upscale, restore, slow_motion, frame_extract, quality_boost, auto_fix |
| Blender | blender | render_scene, render_animation, export_obj, composite, bake_textures, fluid_sim, smoke_sim, cloth_sim, particle_sim, geometry_nodes, material_bake, sculpt_export, camera_track, motion_blur, denoise, freestyle, compositing_nodes, alembic_export, usd_export, batch_render |
| After Effects | after_effects | create_comp, add_layer, apply_effect, keyframe_animation, expression, track_matte, adjust_layer, text_layer, shape_layer, solid_layer, precompose, render, import_media, camera_layer, light_layer, 3d_layer, motion_blur, time_remap, puppet_pin, roto_brush, color_grade, expression_control, script_execute |
| Premiere Pro | premiere_pro | import, cut, transition, color_correction, audio_mix, export, multi_cam, proxy, title, speed_ramp, link_ae, marker, autocolor |
| Photoshop | photoshop | open, layer, mask, retouch, color_adjust, filter, export, batch_process, smart_object, blend_mode, adjustment_layer, brush, text, paths, slice, automate, script_listener |
| Illustrator | illustrator | open, pen_tool, shape_builder, pathfinder, gradient, typography, export_svg, export_png, pattern, blend, envelope_distort, symbol, artboard, layer_manage, color_mode, trace, effect_3d |
| Media Encoder | media_encoder | add_to_queue, preset_apply, start_encode, batch_encode, watch_folder, export_preset, import_preset, custom_preset, destination_set, metadata_embed |

工作流JSON格式:
```json
{
  "name": "工作流名称",
  "description": "工作流描述",
  "category": "custom",
  "steps": [
    {
      "step_id": "step_1",
      "name": "步骤名称",
      "tool": "ffmpeg",
      "operation": "transcode",
      "description": "步骤描述",
      "params": {
        "input_file": "输入文件路径",
        "output_file": "输出文件路径",
        "codec": "libx264",
        "crf": 23
      },
      "depends_on": [],
      "enabled": true
    }
  ]
}
```

规则:
1. 步骤ID使用 step_1, step_2... 格式
2. depends_on列出必须先完成的步骤ID
3. 后续步骤应使用前序步骤的输出文件作为输入
4. 输出文件路径使用 D:\\AE-Work\\_integrator_output\\ 目录
5. 工具ID必须与上表一致
6. 参数应具体可执行，不要用占位符
7. 只输出JSON，不要输出其他内容
"""


class V4Orchestrator:
    """V4智能编排器 - 自然语言到工具链执行"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_mode: str = "real",
        output_dir: str = r"D:\AE-Work\_integrator_output",
        config_file: Optional[str] = None,
        preset_file: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise ValueError("未设置 DEEPSEEK_API_KEY 环境变量")

        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 创建工具集成器实例
        self._integrator = UnifiedToolIntegrator(
            default_mode=default_mode,
            output_dir=output_dir,
            preset_file=preset_file,
            config_file=config_file,
        )

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def analyze_request(self, user_request: str, model: str = "pro") -> Dict[str, Any]:
        """
        使用V4分析用户需求，生成工作流JSON

        Args:
            user_request: 用户的自然语言需求
            model: "pro" 或 "flash"

        Returns:
            工作流定义字典
        """
        model_name = PRO_MODEL if model != "flash" else FLASH_MODEL

        # 获取可用工具信息
        tools_info = self._integrator.get_all_tools_info()
        available_tools = {
            k: v for k, v in tools_info.items() if v.get("available", False)
        }

        # 构建上下文
        context = f"\n\n当前可用工具状态:\n"
        for tool_id, info in available_tools.items():
            context += f"- {tool_id}: {info.get('name', tool_id)} (操作数: {info.get('operations_count', 0)})\n"

        context += f"\n输出目录: {self.output_dir}\n"

        # 如果有输入文件路径，提取出来
        input_files = self._extract_file_paths(user_request)
        if input_files:
            context += f"\n检测到的输入文件: {input_files}\n"

        messages = [
            {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_request + context},
        ]

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 8192,
        }

        if model == "flash":
            payload["reasoning_effort"] = "high"

        start = time.time()
        response = self._session.post(
            f"{API_BASE}/v1/chat/completions",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()

        duration = time.time() - start

        if "choices" not in result or not result["choices"]:
            raise RuntimeError(f"V4 API返回异常: {result}")

        content = result["choices"][0]["message"]["content"]

        # 统计
        usage = result.get("usage", {})
        tokens = usage.get("total_tokens", 0)
        cost = self._calc_cost(usage, model_name)
        print(f"[V4编排] 模型: {model_name} | 耗时: {duration:.1f}s | "
              f"Token: {tokens} | 费用: ¥{cost:.4f}")

        # 解析JSON
        workflow_def = self._extract_json(content)

        return workflow_def

    def execute_workflow(self, workflow_def: Dict[str, Any]) -> WorkflowResult:
        """
        执行V4生成的工作流

        Args:
            workflow_def: 工作流定义字典

        Returns:
            执行结果
        """
        # 将工作流定义注册为临时预设
        preset_id = f"v4_custom_{uuid.uuid4().hex[:8]}"
        workflow_name = workflow_def.get("name", "V4自定义工作流")

        # 转换为集成器可用的预设格式
        preset = {
            "id": preset_id,
            "name": workflow_name,
            "description": workflow_def.get("description", ""),
            "category": workflow_def.get("category", "custom"),
            "steps": workflow_def.get("steps", []),
        }

        # 注册临时预设
        self._integrator._external_presets[preset_id] = preset

        print(f"\n[V4编排] 工作流: {workflow_name}")
        print(f"[V4编排] 步骤数: {len(preset['steps'])}")
        for i, step in enumerate(preset["steps"], 1):
            deps = step.get("depends_on", [])
            dep_str = f" (依赖: {', '.join(deps)})" if deps else ""
            print(f"  {i}. [{step.get('tool')}] {step.get('name')} - "
                  f"{step.get('operation')}{dep_str}")

        # 执行工作流
        result = self._integrator.run_workflow(preset_id)

        return result

    def run(
        self,
        user_request: str,
        model: str = "pro",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        完整流程：V4分析 → 生成工作流 → 执行

        Args:
            user_request: 自然语言需求
            model: V4模型选择
            dry_run: 仅生成工作流不执行

        Returns:
            包含工作流定义和执行结果的字典
        """
        print("=" * 60)
        print("V4 智能编排器")
        print("=" * 60)
        print(f"需求: {user_request}")
        print(f"模型: {model}")
        print(f"模式: {'预览' if dry_run else '真实执行'}")
        print("=" * 60)

        # Step 1: V4分析需求
        print("\n[Step 1] V4分析需求并生成工作流...")
        workflow_def = self.analyze_request(user_request, model=model)

        if not workflow_def or "steps" not in workflow_def:
            return {
                "success": False,
                "error": "V4未能生成有效的工作流",
                "raw_response": workflow_def,
            }

        print(f"\n[Step 1] 完成 - 工作流: {workflow_def.get('name', 'N/A')}")
        print(f"  步骤数: {len(workflow_def['steps'])}")

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "workflow": workflow_def,
            }

        # Step 2: 执行工作流
        print(f"\n[Step 2] 开始执行工作流...")
        result = self.execute_workflow(workflow_def)

        # 汇总结果
        successful = len(result.successful_steps())
        failed = len(result.failed_steps())
        total = len(result.steps)

        print(f"\n[Step 2] 完成")
        print(f"  总步骤: {total}")
        print(f"  成功: {successful}")
        print(f"  失败: {failed}")
        print(f"  耗时: {result.total_duration_ms / 1000:.1f}s")
        print(f"  输出文件: {len(result.output_files)}")

        return {
            "success": result.status == PhaseStatus.SUCCESS.value,
            "workflow": workflow_def,
            "result": result.to_dict(),
            "summary": {
                "total_steps": total,
                "successful": successful,
                "failed": failed,
                "duration_ms": result.total_duration_ms,
                "output_files": result.output_files,
                "log_file": result.log_file_path,
                "report_file": result.report_file_path,
            },
        }

    def _extract_json(self, content: str) -> Dict[str, Any]:
        """从V4回复中提取JSON"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试从代码块中提取
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找到第一个{和最后一个}
        first = content.find('{')
        last = content.rfind('}')
        if first != -1 and last != -1:
            try:
                return json.loads(content[first:last + 1])
            except json.JSONDecodeError:
                pass

        return {"error": "无法解析JSON", "raw": content[:500]}

    def _extract_file_paths(self, text: str) -> List[str]:
        """从文本中提取文件路径"""
        patterns = [
            r'[A-Za-z]:\\[^\s<>"|*?]+',
            r'[A-Za-z]:/[^\s<>"|*?]+',
            r'/[^\s<>"|*?]+',
        ]
        paths = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            paths.extend(matches)
        return list(set(paths))

    def _calc_cost(self, usage: dict, model: str) -> float:
        """计算费用"""
        if "pro" in model:
            in_price, out_price = 3, 6
        else:
            in_price, out_price = 1, 2

        prompt = usage.get("prompt_tokens", 0) / 1_000_000
        completion = usage.get("completion_tokens", 0) / 1_000_000
        return prompt * in_price + completion * out_price

    def list_available_tools(self) -> Dict[str, Any]:
        """列出可用工具"""
        return self._integrator.get_all_tools_info()

    def list_presets(self) -> List[Dict[str, Any]]:
        """列出预设工作流"""
        return self._integrator.list_presets()


# ============================================================================
# 便捷函数
# ============================================================================

_orchestrator = None


def get_orchestrator(
    mode: str = "real",
    config_file: Optional[str] = None,
) -> V4Orchestrator:
    """获取全局V4编排器实例"""
    global _orchestrator
    if _orchestrator is None:
        config_path = config_file or os.path.join(
            os.path.dirname(__file__), "tool_config.json"
        )
        _orchestrator = V4Orchestrator(
            default_mode=mode,
            config_file=config_path if os.path.exists(config_path) else None,
        )
    return _orchestrator


def run(request: str, model: str = "pro", dry_run: bool = False) -> Dict[str, Any]:
    """快捷执行：自然语言 → V4分析 → 工具链执行"""
    return get_orchestrator().run(request, model=model, dry_run=dry_run)


def analyze(request: str, model: str = "pro") -> Dict[str, Any]:
    """仅分析需求，生成工作流定义（不执行）"""
    return get_orchestrator().run(request, model=model, dry_run=True)


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="V4智能编排器 - 自然语言到工具链执行"
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="自然语言需求描述",
    )
    parser.add_argument(
        "--model", "-m",
        choices=["pro", "flash"],
        default="pro",
        help="V4模型选择 (默认: pro)",
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="仅生成工作流不执行",
    )
    parser.add_argument(
        "--config-file", "-c",
        default="tool_config.json",
        help="工具配置文件路径",
    )
    parser.add_argument(
        "--mode",
        choices=["real", "simulate", "auto"],
        default="real",
        help="执行模式 (默认: real)",
    )

    args = parser.parse_args()

    if not args.request:
        print("V4智能编排器 - 使用示例:")
        print('  py -3.11 v4_orchestrator.py "把input.mp4超分到4K并加电影调色"')
        print('  py -3.11 v4_orchestrator.py "提取视频音频并压缩为MP3" --model flash')
        print('  py -3.11 v4_orchestrator.py "批量转码D:\\videos目录下所有视频" --dry-run')
        return

    config_path = os.path.join(os.path.dirname(__file__), args.config_file)
    orchestrator = V4Orchestrator(
        default_mode=args.mode,
        config_file=config_path if os.path.exists(config_path) else None,
    )

    result = orchestrator.run(
        args.request,
        model=args.model,
        dry_run=args.dry_run,
    )

    if result.get("success"):
        if result.get("dry_run"):
            print("\n工作流定义（预览模式）:")
            print(json.dumps(result["workflow"], ensure_ascii=False, indent=2))
        else:
            summary = result.get("summary", {})
            print(f"\n执行完成!")
            print(f"  成功率: {summary.get('successful', 0)}/{summary.get('total_steps', 0)}")
            if summary.get("output_files"):
                print(f"  输出文件:")
                for f in summary["output_files"]:
                    print(f"    - {f}")
    else:
        print(f"\n执行失败: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    main()
