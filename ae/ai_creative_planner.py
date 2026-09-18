#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 创意规划引擎 - 核心组件
负责调用 LLM 解析创意描述，生成结构化任务图，并执行到 AE
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

from .creative_patterns import (
    CREATIVE_PATTERNS,
    find_patterns_by_keyword,
    generate_task_graph,
    get_pattern_by_name,
)
from .preset_executor import PresetExecutor, PresetLibrary, initialize_default_combinations
from .preset_system import PresetSystem
from .prompt_templates import (
    build_creative_analysis_prompt,
    build_parameter_optimization_prompt,
    build_style_transfer_prompt,
    build_subtitle_optimization_prompt,
)
from .subtitle_system import SubtitleSystem


def _gateway_chat(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str | None:
    """同步桥接 core.llm_gateway.chat()（异步统一网关）。

    网关不可用 / 已有运行中的事件循环时返回 None，由调用方降级直连。
    """
    try:
        import asyncio

        from core.llm_gateway import llm_gateway
    except Exception:
        return None
    try:
        asyncio.get_running_loop()
        return None
    except RuntimeError:
        pass
    try:
        response = asyncio.run(
            llm_gateway.chat(
                message=user_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
    except Exception:
        return None
    if not response or not getattr(response, "success", False):
        return None
    return getattr(response, "content", None)


class AICreativePlanner:
    """AI 创意规划引擎"""

    def __init__(
        self,
        llm_api_url: str = None,
        llm_api_key: str = None,
        model: str = "deepseek",
        timeout: int = 30,
        enable_presets: bool = True,
        enable_subtitles: bool = True,
    ):
        self.llm_api_url = llm_api_url or os.environ.get("LLM_API_URL")
        self.llm_api_key = llm_api_key or os.environ.get("LLM_API_KEY")
        self.model = model
        self.timeout = timeout

        if enable_presets:
            self.preset_system = PresetSystem()
            self.preset_executor = PresetExecutor(self.preset_system)
            self.preset_library = PresetLibrary()
            initialize_default_combinations(self.preset_library)

        if enable_subtitles:
            self.subtitle_system = SubtitleSystem(
                llm_api_url=self.llm_api_url,
                llm_api_key=self.llm_api_key,
                model=self.model,
            )

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str | None:
        """经统一网关调用 LLM，网关不可用时降级直连 LLM API。

        Returns:
            模型返回的原始文本内容；失败返回 None。
        """
        content = _gateway_chat(system_prompt, user_prompt, temperature, max_tokens)
        if content is not None:
            return content
        # 降级：直连 LLM API（临时直连，待网关完全覆盖）
        if requests is None or not self.llm_api_url:
            return None
        try:
            response = requests.post(
                self.llm_api_url,
                headers={
                    "Authorization": f"Bearer {self.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.RequestException:
            return None
        if "choices" in result and result["choices"]:
            return result["choices"][0]["message"]["content"]
        if "content" in result:
            return result["content"]
        return None

    def parse_creative_description(self, description: str) -> dict[str, Any]:
        """
        解析创意描述，生成任务图

        Args:
            description: 用户的创意描述（自然语言）

        Returns:
            包含分析结果和任务图的字典
        """
        # 0. 预设快速路径：先搜索预设系统
        if hasattr(self, "preset_system"):
            preset_results = self.preset_system.search_presets(description)
            if preset_results and len(preset_results) >= 1:
                # 如果找到匹配的预设，生成预设任务图
                preset = preset_results[0]
                task_graph = self.generate_preset_task_graph(preset.name)
                all_patterns = [p.name for p in preset_results[:3]]
                return {
                    "analysis": {
                        "original_description": description,
                        "patterns": all_patterns,
                        "styles": [],
                        "animations": [],
                        "keywords": self._extract_keywords(description),
                        "parameters": {"preset": preset.name},
                        "confidence": 0.90,
                        "source": "preset_match",
                        "preset_matches": [p.name for p in preset_results[:5]],
                    },
                    "task_graph": task_graph,
                }

        # 1. 先尝试使用内置模式匹配（快速路径）
        patterns = find_patterns_by_keyword(description)

        # 如果匹配到明确的模式，直接生成任务图
        if patterns and len(patterns) == 1:
            pattern = patterns[0]
            task_graph = generate_task_graph(pattern.name, {"text": description})
            return {
                "analysis": {
                    "original_description": description,
                    "patterns": [pattern.name],
                    "styles": [],
                    "animations": [],
                    "keywords": [],
                    "parameters": {"text": description},
                    "confidence": 0.95,
                    "source": "pattern_match",
                },
                "task_graph": task_graph,
            }

        # 2. 使用 LLM 解析（智能路径）
        if not self.llm_api_url:
            # 如果没有 LLM API，使用启发式分析
            return self._heuristic_analysis(description)

        return self._llm_analysis(description)

    def _heuristic_analysis(self, description: str) -> dict[str, Any]:
        """
        启发式分析创意描述（无 LLM 时的备选方案）

        根据关键词匹配创意模式，生成任务图
        """
        description_lower = description.lower()

        # 匹配风格
        style_map = {
            "cyberpunk": "style_cyberpunk",
            "赛博朋克": "style_cyberpunk",
            "neon": "style_neon",
            "霓虹": "style_neon",
            "hologram": "style_hologram",
            "全息": "style_hologram",
            "ink": "style_ink",
            "水墨": "style_ink",
            "fire": "style_fire_ice",
            "ice": "style_fire_ice",
            "冰火": "style_fire_ice",
            "gold": "style_gold",
            "金色": "style_gold",
            "chrome": "style_chrome",
            "金属": "style_chrome",
        }
        matched_style = None
        for keyword, style_name in style_map.items():
            if keyword in description_lower:
                matched_style = style_name
                break

        # 匹配动画
        animation_map = {
            "typewriter": "typewriter",
            "打字机": "typewriter",
            "reveal": "dissolve",
            "浮现": "dissolve",
            "explode": "dissolve",
            "爆炸": "dissolve",
            "wave": "wave",
            "波浪": "wave",
            "bounce": "bounce_in",
            "弹跳": "bounce_in",
            "scale": "scale_in",
            "缩放": "scale_in",
            "rotate": "rotate_in",
            "旋转": "rotate_in",
            "slide": "slide_in",
            "滑动": "slide_in",
            "per_char": "per_char",
            "逐字": "per_char",
            "shock": "shock",
            "震动": "shock",
            "spiral": "spiral",
            "螺旋": "spiral",
        }
        matched_animation = "fade"
        for keyword, animation_name in animation_map.items():
            if keyword in description_lower:
                matched_animation = animation_name
                break

        # 匹配视频类型
        video_type_map = {
            "opening": "video_opening",
            "片头": "video_opening",
            "intro": "video_opening",
            "ending": "video_ending",
            "片尾": "video_ending",
            "outro": "video_ending",
            "music": "video_music_visualization",
            "audio": "video_music_visualization",
            "subtitle": "subtitle",
            "字幕": "subtitle",
            "caption": "subtitle",
            "对白": "subtitle",
            "台词": "subtitle",
        }
        matched_video_type = None
        for keyword, video_name in video_type_map.items():
            if keyword in description_lower:
                matched_video_type = video_name
                break

        # 提取文字内容
        text_content = self._extract_text_from_description(description)

        # 确定主模式
        if matched_video_type == "subtitle":
            main_pattern = "subtitle"
        elif matched_video_type:
            main_pattern = matched_video_type
        elif matched_style:
            main_pattern = matched_style
        else:
            main_pattern = "text_reveal"

        # 生成任务图
        params = {
            "text": text_content or "CREATIVE TEXT",
            "duration": self._extract_duration(description),
            "animation": matched_animation,
            "style": matched_style or "default",
        }

        if main_pattern == "subtitle":
            task_graph = self._generate_subtitle_task_graph(params)
        else:
            task_graph = generate_task_graph(main_pattern, params)

        return {
            "analysis": {
                "original_description": description,
                "patterns": [main_pattern],
                "styles": [matched_style] if matched_style else [],
                "animations": [matched_animation],
                "keywords": self._extract_keywords(description),
                "parameters": params,
                "confidence": 0.75,
                "source": "heuristic",
                "task_type": "subtitle" if main_pattern == "subtitle" else "creative",
            },
            "task_graph": task_graph,
        }

    def _generate_subtitle_task_graph(self, params: dict[str, Any]) -> dict[str, Any]:
        """生成字幕任务图"""
        return {
            "version": "1.0",
            "project": "Subtitle_Project",
            "duration": params.get("duration", 30),
            "pattern": "subtitle",
            "tasks": [
                {
                    "id": "subtitle_import",
                    "name": "导入字幕",
                    "type": "ae_script",
                    "script": "import_subtitles",
                    "params": {
                        "comp_name": "Main_Comp",
                        "text": params.get("text", ""),
                        "font_size": params.get("font_size", 48),
                        "font_family": params.get("font_family", "Arial"),
                        "style": params.get("style", "default"),
                        "animation": params.get("animation", "fade"),
                        "position_y": params.get("position_y", 0.85),
                    },
                    "dependencies": [],
                    "timeout": 30,
                }
            ],
        }

    def _llm_analysis(self, description: str) -> dict[str, Any]:
        """
        使用 LLM 分析创意描述

        Args:
            description: 用户的创意描述

        Returns:
            包含分析结果和任务图的字典
        """
        if requests is None:
            raise ImportError("需要安装 requests 库")

        # 注入预设能力清单到LLM提示词
        preset_sys = getattr(self, "preset_system", None)
        prompt = build_creative_analysis_prompt(description, preset_system=preset_sys)

        content = self._call_llm(prompt["system"], prompt["user"], 0.7, 2000)
        if content is None:
            return self._heuristic_analysis(description)

        # 提取 JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 如果不是纯 JSON，尝试提取其中的 JSON
            return self._extract_json_from_text(content)

    def _extract_json_from_text(self, text: str) -> dict[str, Any]:
        """从文本中提取 JSON"""
        import re

        # 查找第一个 { 和最后一个 } 之间的内容
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return self._heuristic_analysis(text)

    def _extract_text_from_description(self, description: str) -> str | None:
        """从描述中提取文字内容"""
        import re

        # 尝试匹配引号内的内容
        match = re.search(r'"([^"]+)"', description)
        if match:
            return match.group(1)

        # 尝试匹配中文引号内的内容
        match = re.search(r'“([^”]+)”', description)
        if match:
            return match.group(1)

        # 尝试匹配冒号后的内容
        match = re.search(r'文字[:：]\s*([^。，,]+)', description)
        if match:
            return match.group(1).strip()

        return None

    def _extract_duration(self, description: str) -> float:
        """从描述中提取时长（秒）"""
        import re

        match = re.search(r'(\d+)\s*秒', description)
        if match:
            return float(match.group(1))

        match = re.search(r'(\d+)\s*s', description, re.IGNORECASE)
        if match:
            return float(match.group(1))

        match = re.search(r'(\d+)\s*分钟', description)
        if match:
            return float(match.group(1)) * 60

        return 5.0

    def _extract_keywords(self, description: str) -> list[str]:
        """从描述中提取关键词"""
        keywords = []
        keyword_list = [
            "赛博朋克", "cyberpunk", "霓虹", "neon",
            "全息", "hologram", "科幻", "scifi",
            "水墨", "ink", "书法", "calligraphy",
            "冰火", "fire", "ice",
            "金色", "gold", "金属", "chrome",
            "片头", "opening", "intro",
            "片尾", "ending", "outro",
            "音乐", "audio", "visualization",
            "打字机", "typewriter",
            "浮现", "reveal",
            "爆炸", "explode",
            "波浪", "wave",
            "弹跳", "bounce",
            "缩放", "scale",
            "旋转", "rotate",
            "滑动", "slide",
            "逐字", "per_char",
            "震动", "shock",
            "螺旋", "spiral",
            "字幕", "subtitle", "caption",
            "对白", "台词", "transcript",
            "发光", "glow", "shadow",
            "描边", "stroke", "border",
        ]
        for kw in keyword_list:
            if kw in description.lower():
                keywords.append(kw)
        return keywords

    async def generate_subtitles_from_audio(
        self,
        audio_path: Path | str,
        language: str = "zh",
        optimize_with_llm: bool = True,
    ) -> dict[str, Any]:
        """
        从音频生成字幕（集成字幕系统）

        Args:
            audio_path: 音频文件路径
            language: 语言代码
            optimize_with_llm: 是否使用 LLM 优化字幕

        Returns:
            包含字幕列表和任务图的字典
        """
        if not hasattr(self, "subtitle_system"):
            return {"success": False, "error": "字幕系统未启用"}

        subtitles = await self.subtitle_system.generate_subtitles_from_audio(
            audio_path, language, optimize_with_llm
        )

        task_graph = {
            "version": "1.0",
            "project": "Audio_Subtitle_Project",
            "duration": subtitles[-1].end_time if subtitles else 30,
            "pattern": "subtitle",
            "tasks": [
                {
                    "id": "subtitle_import",
                    "name": "导入音频生成的字幕",
                    "type": "ae_script",
                    "script": "import_subtitles",
                    "params": {
                        "comp_name": "Main_Comp",
                        "subtitles": [s.to_dict() for s in subtitles],
                        "font_size": 48,
                        "font_family": "Arial",
                        "style": "default",
                        "animation": "fade",
                    },
                    "dependencies": [],
                    "timeout": 30,
                }
            ],
        }

        return {
            "success": True,
            "subtitles": [s.to_dict() for s in subtitles],
            "task_graph": task_graph,
            "subtitle_count": len(subtitles),
        }

    async def optimize_subtitles(
        self,
        subtitles: list[dict[str, Any]],
        language: str = "zh",
        style: str = "default",
    ) -> list[dict[str, Any]]:
        """
        使用 LLM 优化字幕

        Args:
            subtitles: 字幕列表
            language: 目标语言
            style: 字幕风格

        Returns:
            优化后的字幕列表
        """
        if not hasattr(self, "subtitle_system"):
            return subtitles

        from .subtitle_system import SubtitleItem

        subtitle_items = [SubtitleItem(**s) for s in subtitles]
        optimized = await self.subtitle_system._optimize_subtitles_with_llm(
            subtitle_items, language, style
        )
        return [s.to_dict() for s in optimized]

    def optimize_parameters(
        self, description: str, current_params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        优化参数

        Args:
            description: 优化描述
            current_params: 当前参数

        Returns:
            优化后的参数
        """
        if not self.llm_api_url:
            return current_params

        prompt = build_parameter_optimization_prompt(description, current_params)

        content = self._call_llm(prompt["system"], prompt["user"], 0.5, 1000)
        if content is None:
            return current_params

        try:
            data = json.loads(content)
            return data.get("optimized_params", current_params)
        except json.JSONDecodeError:
            return current_params

    def analyze_style(self, reference_description: str) -> dict[str, Any]:
        """
        分析参考风格

        Args:
            reference_description: 参考风格描述

        Returns:
            风格分析结果
        """
        if not self.llm_api_url:
            return {
                "style_analysis": {
                    "name": "default",
                    "description": reference_description,
                    "color_scheme": {"primary": [1, 1, 1], "secondary": [0.5, 0.5, 0.5], "background": [0, 0, 0]},
                    "effects": {"glow": {"enabled": True, "color": [1, 1, 1], "radius": 20, "intensity": 1.5}},
                    "animation": {"type": "fade", "duration": 3, "easing": "easeOut"},
                },
                "apply_params": {},
            }

        prompt = build_style_transfer_prompt(reference_description)

        content = self._call_llm(prompt["system"], prompt["user"], 0.7, 1500)
        if content is None:
            return {
                "style_analysis": {"name": "default"},
                "apply_params": {},
            }

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "style_analysis": {"name": "default"},
                "apply_params": {},
            }

    def execute_task_graph(self, task_graph: dict[str, Any], ae_client=None) -> dict[str, Any]:
        """
        执行任务图

        Args:
            task_graph: 任务图
            ae_client: AE 客户端实例

        Returns:
            执行结果
        """
        results = []

        for task in task_graph.get("tasks", []):
            task_id = task.get("id")
            script_name = task.get("script")
            params = task.get("params", {})

            print(f"执行任务: {task_id} - {script_name}")

            if ae_client:
                try:
                    result = ae_client.run_script(script_name, params)
                    results.append({
                        "task_id": task_id,
                        "script": script_name,
                        "success": True,
                        "result": result,
                    })
                except Exception as e:
                    results.append({
                        "task_id": task_id,
                        "script": script_name,
                        "success": False,
                        "error": str(e),
                    })
            else:
                results.append({
                    "task_id": task_id,
                    "script": script_name,
                    "success": True,
                    "status": "dry_run",
                    "params": params,
                })

        return {
            "project": task_graph.get("project"),
            "duration": task_graph.get("duration"),
            "pattern": task_graph.get("pattern"),
            "results": results,
            "total_tasks": len(results),
            "success_count": sum(1 for r in results if r.get("success")),
        }

    def generate_and_execute(
        self,
        description: str,
        ae_client=None,
        optimize: bool = False,
    ) -> dict[str, Any]:
        """
        生成任务图并执行

        Args:
            description: 用户的创意描述
            ae_client: AE 客户端实例
            optimize: 是否优化参数

        Returns:
            完整的执行结果
        """
        start_time = time.time()

        # 1. 解析创意描述
        analysis_result = self.parse_creative_description(description)
        task_graph = analysis_result.get("task_graph")

        # 2. 优化参数（可选）
        if optimize and self.llm_api_url:
            params = analysis_result.get("analysis", {}).get("parameters", {})
            optimized_params = self.optimize_parameters(description, params)
            # 更新任务图中的参数
            for task in task_graph.get("tasks", []):
                task["params"] = {**task.get("params", {}), **optimized_params}

        # 3. 执行任务图
        execution_result = self.execute_task_graph(task_graph, ae_client)

        total_time = time.time() - start_time

        return {
            "description": description,
            "analysis": analysis_result.get("analysis"),
            "task_graph": task_graph,
            "execution": execution_result,
            "total_time": round(total_time, 2),
        }

    def list_available_patterns(self) -> list[dict[str, Any]]:
        """列出所有可用的创意模式"""
        return [pattern.to_dict() for pattern in CREATIVE_PATTERNS]

    def list_presets(self, category: str = None) -> list[str]:
        """列出所有可用的预设"""
        if hasattr(self, 'preset_system'):
            return self.preset_system.list_presets(category)
        return []

    def search_presets(self, keyword: str) -> list[dict[str, Any]]:
        """搜索预设"""
        if hasattr(self, 'preset_system'):
            presets = self.preset_system.search_presets(keyword)
            return [preset.to_dict() for preset in presets]
        return []

    def execute_preset(self, preset_name: str, ae_client=None, **kwargs) -> dict[str, Any]:
        """执行预设"""
        if hasattr(self, 'preset_executor'):
            return self.preset_executor.execute_preset(preset_name, ae_client, **kwargs)
        return {"success": False, "error": "预设系统未启用"}

    def execute_preset_combination(self, combination_name: str, ae_client=None, **kwargs) -> dict[str, Any]:
        """执行预设组合"""
        if hasattr(self, 'preset_library') and hasattr(self, 'preset_executor'):
            combo = self.preset_library.get_combination(combination_name)
            if combo:
                return self.preset_executor.execute_preset_chain(
                    combo.presets,
                    ae_client,
                    combo.parameters,
                    **kwargs
                )
            return {"success": False, "error": f"组合不存在: {combination_name}"}
        return {"success": False, "error": "预设系统未启用"}

    def generate_preset_task_graph(self, preset_name: str, **kwargs) -> dict[str, Any]:
        """从预设生成任务图"""
        if hasattr(self, 'preset_system'):
            preset = self.preset_system.get_preset(preset_name)
            if preset:
                jsx_code = preset.generate_jsx(**kwargs)
                return {
                    "version": "1.0",
                    "project": f"Preset_{preset_name}",
                    "duration": kwargs.get("duration", 5),
                    "pattern": preset_name,
                    "tasks": [
                        {
                            "id": f"preset_{preset_name}",
                            "name": preset.description,
                            "type": "ae_script",
                            "script": "executeAtomScript",
                            "params": {
                                "script": jsx_code,
                                "preset": preset_name,
                            },
                            "dependencies": [],
                            "timeout": 30,
                        }
                    ],
                }
            return {"error": f"预设不存在: {preset_name}"}
        return {"error": "预设系统未启用"}

    def list_preset_combinations(self) -> list[str]:
        """列出所有预设组合"""
        if hasattr(self, 'preset_library'):
            return self.preset_library.list_combinations()
        return []
