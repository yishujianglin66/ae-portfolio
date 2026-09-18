#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流DSL解析器 (Workflow DSL Parser)
=====================================

允许用户使用JSON格式定义自定义工作流，支持：
- 步骤定义（工具、操作、参数、依赖）
- 变量插值（${var}）
- 条件执行
- 循环结构
- 模板继承

DSL格式示例:
```json
{
  "name": "我的工作流",
  "version": "1.0",
  "variables": {
    "input_dir": "D:/videos",
    "output_dir": "D:/output"
  },
  "steps": [
    {
      "id": "step_1",
      "name": "超分辨率",
      "tool": "topaz_video_ai",
      "operation": "enhance",
      "params": {
        "input_file": "${input_dir}/raw.mp4",
        "output_file": "${output_dir}/enhanced.mp4",
        "model": "proteus",
        "scale": 2
      }
    },
    {
      "id": "step_2",
      "name": "调色输出",
      "tool": "ffmpeg",
      "operation": "transcode",
      "params": {
        "input_file": "${step_1.output_file}",
        "output_file": "${output_dir}/final.mp4",
        "filters": ["eq=contrast=1.2"]
      },
      "depends_on": ["step_1"],
      "condition": "${step_1.status} == 'success'"
    }
  ]
}
```

使用方式:
    from workflow_dsl import WorkflowDSL

    dsl = WorkflowDSL()
    workflow = dsl.parse("my_workflow.json")
    result = dsl.execute(workflow)
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from unified_tool_integrator import UnifiedToolIntegrator
    INTEGRATOR_AVAILABLE = True
except ImportError:
    INTEGRATOR_AVAILABLE = False


class DSLSyntaxError(Exception):
    """DSL语法错误"""
    pass


class DSLValidationError(Exception):
    """DSL验证错误"""
    pass


class WorkflowDSL:
    """工作流DSL解析器"""

    SUPPORTED_TOOLS = [
        "ffmpeg", "topaz_video_ai", "blender",
        "after_effects", "premiere_pro", "photoshop",
        "illustrator", "media_encoder", "audition"
    ]

    def __init__(
        self,
        mode: str = "real",
        output_dir: str = None,
        config_file: str = None,
    ):
        self.mode = mode
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(__file__), "output"
        )
        self.config_file = config_file

        self._integrator = None
        if INTEGRATOR_AVAILABLE:
            self._integrator = UnifiedToolIntegrator(
                default_mode=mode,
                output_dir=self.output_dir,
                config_file=config_file,
            )

        # 解析上下文
        self._variables: dict[str, Any] = {}
        self._step_results: dict[str, dict] = {}

    def parse(self, dsl_path: str) -> dict[str, Any]:
        """
        解析DSL文件

        Args:
            dsl_path: DSL JSON文件路径

        Returns:
            解析后的工作流定义
        """
        with open(dsl_path, "r", encoding="utf-8") as f:
            content = f.read()

        return self.parse_string(content)

    def parse_string(self, content: str) -> dict[str, Any]:
        """
        解析DSL字符串

        Args:
            content: DSL JSON字符串

        Returns:
            解析后的工作流定义
        """
        try:
            dsl = json.loads(content)
        except json.JSONDecodeError as e:
            raise DSLSyntaxError(f"JSON解析失败: {e}")

        # 验证结构
        self._validate_dsl(dsl)

        # 提取变量
        self._variables = dsl.get("variables", {})

        # 解析步骤
        steps = dsl.get("steps", [])
        parsed_steps = []

        for i, step in enumerate(steps):
            parsed_step = self._parse_step(step, i)
            parsed_steps.append(parsed_step)

        return {
            "name": dsl.get("name", "未命名工作流"),
            "version": dsl.get("version", "1.0"),
            "description": dsl.get("description", ""),
            "variables": self._variables,
            "steps": parsed_steps,
        }

    def _validate_dsl(self, dsl: dict) -> None:
        """验证DSL结构"""
        if "steps" not in dsl:
            raise DSLValidationError("DSL必须包含steps字段")

        if not isinstance(dsl["steps"], list):
            raise DSLValidationError("steps必须是数组")

        for i, step in enumerate(dsl["steps"]):
            self._validate_step(step, i)

    def _validate_step(self, step: dict, index: int) -> None:
        """验证步骤定义"""
        required = ["tool", "operation"]
        for field in required:
            if field not in step:
                raise DSLValidationError(
                    f"步骤{index + 1}缺少必填字段: {field}"
                )

        if step["tool"] not in self.SUPPORTED_TOOLS:
            raise DSLValidationError(
                f"步骤{index + 1}的工具'{step['tool']}'不支持，"
                f"可用工具: {', '.join(self.SUPPORTED_TOOLS)}"
            )

    def _parse_step(self, step: dict, index: int) -> dict:
        """解析单个步骤"""
        step_id = step.get("id", f"step_{index + 1}")

        # 解析参数（变量插值）
        params = step.get("params", {})
        parsed_params = self._interpolate_params(params)

        parsed = {
            "step_id": step_id,
            "name": step.get("name", f"步骤{index + 1}"),
            "tool": step["tool"],
            "operation": step["operation"],
            "params": parsed_params,
            "depends_on": step.get("depends_on", []),
            "enabled": step.get("enabled", True),
            "condition": step.get("condition"),
            "on_error": step.get("on_error", "fail"),  # fail / skip / retry
        }

        return parsed

    def _interpolate_params(self, params: dict) -> dict:
        """参数变量插值"""
        result = {}

        for key, value in params.items():
            if isinstance(value, str):
                result[key] = self._interpolate_string(value)
            elif isinstance(value, dict):
                result[key] = self._interpolate_params(value)
            elif isinstance(value, list):
                result[key] = [
                    self._interpolate_string(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                result[key] = value

        return result

    def _interpolate_string(self, s: str) -> str:
        """字符串变量插值"""
        # ${var} 格式
        pattern = r'\$\{([^}]+)\}'

        def replacer(match):
            expr = match.group(1)

            # step_x.output_file 格式（引用前序步骤输出）
            if '.' in expr:
                parts = expr.split('.', 1)
                step_id = parts[0]
                attr = parts[1]

                if step_id in self._step_results:
                    step_result = self._step_results[step_id]
                    if attr == "output_file":
                        files = step_result.get("output_files", [])
                        return files[0] if files else ""
                    elif attr == "status":
                        return step_result.get("status", "")
                    else:
                        return str(step_result.get("output_data", {}).get(attr, ""))
                return ""

            # 普通变量
            if expr in self._variables:
                return str(self._variables[expr])

            return match.group(0)  # 保留原样

        return re.sub(pattern, replacer, s)

    def execute(self, workflow: dict, dry_run: bool = False) -> dict:
        """
        执行工作流

        Args:
            workflow: 解析后的工作流定义
            dry_run: 是否仅预览不执行

        Returns:
            执行结果
        """
        if not self._integrator:
            return {"success": False, "error": "工具集成器不可用"}

        steps = workflow.get("steps", [])

        # 转换为集成器格式
        preset_id = "dsl_custom_" + workflow.get("name", "workflow").replace(" ", "_")
        preset = {
            "id": preset_id,
            "name": workflow.get("name", "DSL工作流"),
            "description": workflow.get("description", ""),
            "category": "dsl",
            "steps": steps,
        }

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "workflow": preset,
                "steps_count": len(steps),
            }

        # 注册预设
        self._integrator._external_presets[preset_id] = preset

        # 执行
        result = self._integrator.run_workflow(preset_id)

        return result.to_dict()

    def load_template(self, template_name: str) -> dict:
        """加载预设模板"""
        templates = {
            "video_enhance": {
                "name": "视频画质增强",
                "description": "使用Topaz AI增强视频画质",
                "variables": {
                    "input_file": "",
                    "output_file": "",
                    "model": "proteus",
                    "scale": 2,
                },
                "steps": [
                    {
                        "id": "enhance",
                        "name": "AI增强",
                        "tool": "topaz_video_ai",
                        "operation": "enhance",
                        "params": {
                            "input_file": "${input_file}",
                            "output_file": "${output_file}",
                            "model": "${model}",
                            "scale": "${scale}",
                        },
                    }
                ],
            },
            "batch_transcode": {
                "name": "批量转码",
                "description": "使用FFmpeg批量转码",
                "variables": {
                    "input_files": [],
                    "output_dir": "",
                    "codec": "libx264",
                },
                "steps": [
                    {
                        "id": "transcode",
                        "name": "批量转码",
                        "tool": "ffmpeg",
                        "operation": "batch_transcode",
                        "params": {
                            "input_files": "${input_files}",
                            "output_dir": "${output_dir}",
                            "codec": "${codec}",
                        },
                    }
                ],
            },
            "ae_render": {
                "name": "AE渲染",
                "description": "After Effects项目渲染",
                "variables": {
                    "project_file": "",
                    "comp_name": "",
                    "output_file": "",
                },
                "steps": [
                    {
                        "id": "open",
                        "name": "打开项目",
                        "tool": "after_effects",
                        "operation": "open_project",
                        "params": {
                            "file_path": "${project_file}",
                        },
                    },
                    {
                        "id": "render",
                        "name": "渲染合成",
                        "tool": "after_effects",
                        "operation": "render",
                        "params": {
                            "comp_name": "${comp_name}",
                            "output_file": "${output_file}",
                        },
                        "depends_on": ["open"],
                    },
                ],
            },
        }

        return templates.get(template_name, {})

    def list_templates(self) -> list[str]:
        """列出可用模板"""
        return ["video_enhance", "batch_transcode", "ae_render"]

    def validate_workflow(self, workflow: dict) -> dict[str, list[str]]:
        """验证工作流定义"""
        errors = []
        warnings = []

        # 检查步骤依赖
        steps = workflow.get("steps", [])
        step_ids = {s["step_id"] for s in steps}

        for step in steps:
            for dep in step.get("depends_on", []):
                if dep not in step_ids:
                    errors.append(f"步骤'{step['step_id']}'依赖了不存在的步骤'{dep}'")

        # 检查循环依赖
        if self._has_circular_dependency(steps):
            errors.append("工作流存在循环依赖")

        # 检查参数完整性
        for step in steps:
            params = step.get("params", {})
            if not params:
                warnings.append(f"步骤'{step['step_id']}'没有定义参数")

        return {"errors": errors, "warnings": warnings}

    def _has_circular_dependency(self, steps: list[dict]) -> bool:
        """检查循环依赖"""
        step_ids = [s["step_id"] for s in steps]
        dep_graph = {s["step_id"]: s.get("depends_on", []) for s in steps}

        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for dep in dep_graph.get(node, []):
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for step_id in step_ids:
            if step_id not in visited:
                if has_cycle(step_id):
                    return True

        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="工作流DSL解析器")
    parser.add_argument("dsl_file", nargs="?", help="DSL JSON文件路径")
    parser.add_argument("--validate", "-v", action="store_true", help="仅验证不执行")
    parser.add_argument("--dry-run", "-d", action="store_true", help="预览模式")
    parser.add_argument("--templates", "-t", action="store_true", help="列出可用模板")
    parser.add_argument("--mode", "-m", default="real", help="执行模式")

    args = parser.parse_args()

    dsl = WorkflowDSL(mode=args.mode)

    if args.templates:
        print("可用模板:")
        for t in dsl.list_templates():
            template = dsl.load_template(t)
            print(f"  - {t}: {template.get('name', '')}")
        return

    if not args.dsl_file:
        print("用法: py -3.11 workflow_dsl.py <workflow.json>")
        print("选项:")
        print("  --validate    仅验证不执行")
        print("  --dry-run     预览模式")
        print("  --templates   列出可用模板")
        return

    try:
        workflow = dsl.parse(args.dsl_file)

        print(f"\n工作流: {workflow['name']}")
        print(f"版本: {workflow.get('version', '1.0')}")
        print(f"步骤数: {len(workflow['steps'])}")

        # 验证
        validation = dsl.validate_workflow(workflow)

        if validation["errors"]:
            print("\n错误:")
            for e in validation["errors"]:
                print(f"  ❌ {e}")
            return

        if validation["warnings"]:
            print("\n警告:")
            for w in validation["warnings"]:
                print(f"  ⚠️ {w}")

        if args.validate:
            print("\n验证通过 ✓")
            return

        # 执行
        result = dsl.execute(workflow, dry_run=args.dry_run)

        print("\n执行结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except (DSLSyntaxError, DSLValidationError) as e:
        print(f"\nDSL错误: {e}")
    except Exception as e:
        print(f"\n执行错误: {e}")


if __name__ == "__main__":
    main()