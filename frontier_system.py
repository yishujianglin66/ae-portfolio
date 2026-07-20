#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frontier_system.py — 前沿能力统一调度系统
==========================================

将5大前沿能力集成到统一入口:
  1. VISION 自动复刻 — 看一个视频，自动在AE里复刻
  2. 多模态导演系统 — 文字/图片/视频/音乐任意输入，生成完整剧本
  3. AIGC 原生工作流 — 零素材，纯AI生成到成片
  4. 风格迁移 — 把A视频的画风套到B视频上
  5. 智能剪辑 — AI自动选择镜头/转场/节奏，产出电影感作品

架构:
  FrontierSystem (统一入口)
    ├── VisionReplicateEngine   → visual_content_analyzer + video_reproduce_pipeline
    ├── MultimodalDirector      → ai_agent + visual_analyzer + beat_mapper
    ├── AIGCNativeWorkflow      → aigc_generator + material_searcher
    ├── StyleTransferEngine     → style_copy + color_grading_applier
    └── CinematicEditEngine     → cinematic_intelligence + scene_detector

用法:
    system = FrontierSystem()
    
    # 自动识别任务类型
    result = system.execute("帮我复刻这个视频的特效", video="ref.mp4")
    
    # 显式调用某个能力
    result = system.vision_replicate("ref.mp4")
    result = system.multimodal_direct("做一个高燃混剪")
    result = system.aigc_native("赛博朋克城市夜景")
    result = system.style_transfer(source="video.mp4", style_ref="style.mp4")
    result = system.cinematic_edit(materials=["a.mp4","b.mp4"], music="bgm.mp3")
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ================================================================
#  能力1: VISION 自动复刻引擎
# ================================================================

class VisionReplicateEngine:
    """VISION自动复刻 — 看视频→分析→在AE复刻"""

    name = "vision_replicate"
    description = "输入参考视频，自动识别特效/转场/调色，生成AE工程"

    def __init__(self):
        self._analyzer = None
        self._pipeline = None

    @property
    def analyzer(self):
        if self._analyzer is None:
            from visual_content_analyzer import VisualContentAnalyzer
            self._analyzer = VisualContentAnalyzer()
        return self._analyzer

    @property
    def pipeline(self):
        if self._pipeline is None:
            from video_reproduce_pipeline import VideoReproducePipeline
            self._pipeline = VideoReproducePipeline()
        return self._pipeline

    def execute(self, video_path: str, output_dir: str = "output/replicate",
                **kwargs) -> Dict:
        """执行VISION复刻"""
        log(f"[VISION] 开始复刻: {video_path}")
        result = {"capability": self.name, "status": "running", "steps": []}

        # Step 1: 视觉分析
        log("[VISION] Step 1/3: 视觉内容分析...")
        try:
            analysis = self.analyzer.analyze(video_path, num_frames=8)
            result["steps"].append({"step": "visual_analysis", "status": "ok",
                                    "data": analysis})
        except Exception as e:
            log(f"[VISION] 视觉分析失败: {e}", "WARN")
            analysis = {"mood": "unknown", "tags": []}
            result["steps"].append({"step": "visual_analysis", "status": "error",
                                    "error": str(e)})

        # Step 2: 效果复现管线
        log("[VISION] Step 2/3: 效果复现...")
        try:
            reproduce_result = self.pipeline.reproduce(
                video_path=video_path,
                output_mode="jsx",
                output_dir=output_dir,
            )
            result["steps"].append({"step": "effect_reproduce", "status": "ok",
                                    "data": reproduce_result})
        except Exception as e:
            log(f"[VISION] 效果复现失败: {e}", "WARN")
            reproduce_result = {"error": str(e)}
            result["steps"].append({"step": "effect_reproduce", "status": "error",
                                    "error": str(e)})

        # Step 3: 汇总
        result["status"] = "completed"
        result["output"] = {
            "analysis": analysis,
            "reproduce": reproduce_result,
            "output_dir": output_dir,
        }
        log(f"[VISION] 复刻完成 → {output_dir}")
        return result


# ================================================================
#  能力2: AIGC 原生工作流
# ================================================================

class AIGCNativeWorkflow:
    """AIGC原生工作流 — 零素材，纯AI生成"""

    name = "aigc_native"
    description = "从零开始，一句话生成完整视频素材"

    def __init__(self):
        self._generator = None
        self._searcher = None

    @property
    def generator(self):
        if self._generator is None:
            from aigc_generator import AIGCGenerator
            self._generator = AIGCGenerator()
        return self._generator

    @property
    def searcher(self):
        if self._searcher is None:
            from material_searcher import MaterialSearcher
            self._searcher = MaterialSearcher()
        return self._searcher

    def execute(self, prompt: str, output_dir: str = "output_director/materials",
                num_images: int = 3, num_videos: int = 1,
                search_first: bool = True, **kwargs) -> Dict:
        """执行AIGC原生生成"""
        log(f"[AIGC] 零素材生成: {prompt[:50]}...")
        result = {"capability": self.name, "status": "running", "steps": []}

        materials = []

        # Step 1: 先尝试搜索真实素材
        if search_first:
            log("[AIGC] Step 1/3: 搜索真实素材...")
            try:
                search_results = self.searcher.search_and_download(
                    prompt, Path(output_dir), max_results=num_images
                )
                materials.extend(search_results)
                result["steps"].append({"step": "material_search", "status": "ok",
                                        "count": len(search_results)})
                log(f"[AIGC] 搜索到 {len(search_results)} 个素材")
            except Exception as e:
                log(f"[AIGC] 素材搜索失败: {e}", "WARN")
                result["steps"].append({"step": "material_search", "status": "error",
                                        "error": str(e)})

        # Step 2: AI生成补充素材
        log("[AIGC] Step 2/3: AI生成补充素材...")
        try:
            gen = self.generator
            # 生成图片
            for i in range(num_images):
                try:
                    img_result = gen.generate_image(
                        prompt=f"{prompt} scene {i+1}",
                        output_dir=output_dir,
                    )
                    if img_result:
                        materials.append(img_result)
                except Exception as e:
                    log(f"[AIGC] 图片生成失败: {e}", "WARN")

            result["steps"].append({"step": "ai_generate", "status": "ok",
                                    "generated": len(materials)})
        except Exception as e:
            log(f"[AIGC] AI生成失败: {e}", "WARN")
            result["steps"].append({"step": "ai_generate", "status": "error",
                                    "error": str(e)})

        # Step 3: 汇总
        result["status"] = "completed"
        result["output"] = {
            "total_materials": len(materials),
            "materials": materials,
            "prompt": prompt,
        }
        log(f"[AIGC] 完成: 共 {len(materials)} 个素材")
        return result


# ================================================================
#  能力3: 风格迁移引擎
# ================================================================

class StyleTransferEngine:
    """风格迁移 — 将参考视频的画风应用到目标视频"""

    name = "style_transfer"
    description = "提取参考视频风格，应用到目标视频"

    def __init__(self):
        self._analyzer = None
        self._grader = None

    @property
    def analyzer(self):
        if self._analyzer is None:
            from visual_content_analyzer import VisualContentAnalyzer
            self._analyzer = VisualContentAnalyzer()
        return self._analyzer

    @property
    def grader(self):
        if self._grader is None:
            from color_grading_applier import ColorGradingApplier
            self._grader = ColorGradingApplier()
        return self._grader

    def execute(self, source_video: str, style_reference: str = "",
                style_description: str = "",
                output_dir: str = "output/style_transfer", **kwargs) -> Dict:
        """执行风格迁移"""
        log(f"[风格迁移] 源: {source_video}")
        result = {"capability": self.name, "status": "running", "steps": []}

        # Step 1: 分析风格
        style = {}
        if style_reference:
            log("[风格迁移] Step 1/3: 分析参考视频风格...")
            try:
                style = self.analyzer.analyze(style_reference, num_frames=6)
                result["steps"].append({"step": "style_analysis", "status": "ok",
                                        "style": style})
            except Exception as e:
                log(f"[风格迁移] 风格分析失败: {e}", "WARN")
                result["steps"].append({"step": "style_analysis", "status": "error",
                                        "error": str(e)})
        elif style_description:
            style = self._description_to_style(style_description)
            result["steps"].append({"step": "style_parse", "status": "ok"})

        # Step 2: 生成调色方案
        log("[风格迁移] Step 2/3: 生成调色方案...")
        try:
            grading_plan = self.grader.generate_color_grade_jsx(style)
            result["steps"].append({"step": "grading_plan", "status": "ok",
                                    "plan": grading_plan})
        except Exception as e:
            log(f"[风格迁移] 调色方案失败: {e}", "WARN")
            grading_plan = {}
            result["steps"].append({"step": "grading_plan", "status": "error",
                                    "error": str(e)})

        # Step 3: 输出
        result["status"] = "completed"
        result["output"] = {
            "style": style,
            "grading_plan": grading_plan,
            "source": source_video,
            "output_dir": output_dir,
        }
        log("[风格迁移] 完成")
        return result

    def _description_to_style(self, desc: str) -> Dict:
        """将文字描述转换为风格参数"""
        style_map = {
            "赛博朋克": {"color_tone": "neon_cool", "contrast": "high", "saturation": "high"},
            "电影感": {"color_tone": "teal_orange", "contrast": "medium", "grain": True},
            "胶片": {"color_tone": "warm_fade", "grain": True, "contrast": "low"},
            "冷色调": {"color_tone": "cool_blue", "saturation": "medium"},
            "暖色调": {"color_tone": "warm_golden", "saturation": "medium"},
            "暗黑": {"color_tone": "dark_desaturated", "contrast": "high", "vignette": True},
            "唯美": {"color_tone": "soft_pastel", "contrast": "low", "glow": True},
            "高燃": {"color_tone": "intense_warm", "contrast": "high", "saturation": "high"},
        }
        for keyword, style_params in style_map.items():
            if keyword in desc:
                return style_params
        return {"color_tone": "neutral", "contrast": "medium"}


# ================================================================
#  能力4: 智能剪辑引擎
# ================================================================

class CinematicEditEngine:
    """智能剪辑 — AI自动选择镜头/转场/节奏"""

    name = "cinematic_edit"
    description = "AI智能选择镜头语言和转场，产出电影感作品"

    def __init__(self):
        self._ci = None
        self._director = None

    @property
    def ci(self):
        if self._ci is None:
            from cinematic_intelligence import CinematicIntelligence
            self._ci = CinematicIntelligence()
        return self._ci

    @property
    def director(self):
        if self._director is None:
            from multimodal_director import MultimodalDirector
            self._director = MultimodalDirector()
        return self._director

    def execute(self, materials: List[str] = None, music: str = "",
                description: str = "", target_duration: float = 120.0,
                output_dir: str = "output/cinematic", **kwargs) -> Dict:
        """执行智能剪辑"""
        log(f"[智能剪辑] 素材: {len(materials or [])}个, 音乐: {bool(music)}")
        result = {"capability": self.name, "status": "running", "steps": []}

        # Step 1: 生成初始剧本
        log("[智能剪辑] Step 1/3: 生成剧本...")
        director = self.director
        if music:
            script = director.direct_from_music(
                music, description, materials, 
            )
        elif description:
            script = director.direct_from_text(
                description, materials, target_duration
            )
        else:
            script = director.direct_from_text(
                "自动混剪", materials, target_duration
            )
        result["steps"].append({"step": "script_generation", "status": "ok",
                                "segments": len(script.segments)})

        # Step 2: 镜头语言优化
        log("[智能剪辑] Step 2/3: 镜头语言优化...")
        script_dict = script.to_dict()
        optimized = self.ci.optimize_script(script_dict)
        result["steps"].append({"step": "cinematic_optimize", "status": "ok"})

        # Step 3: 连续性检查
        log("[智能剪辑] Step 3/3: 连续性检查...")
        issues = self.ci.analyze_continuity(optimized.get("segments", []))
        result["steps"].append({"step": "continuity_check", "status": "ok",
                                "issues": len(issues)})

        # 保存剧本
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        script_path = str(output_path / "edit_script.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(optimized, f, ensure_ascii=False, indent=2)

        result["status"] = "completed"
        result["output"] = {
            "script_path": script_path,
            "total_duration": sum(s.get("duration", 0) for s in optimized.get("segments", [])),
            "segment_count": len(optimized.get("segments", [])),
            "issues": issues,
        }
        log(f"[智能剪辑] 完成 → {script_path}")
        return result


# ================================================================
#  统一调度系统
# ================================================================

# 任务类型关键词 → 能力映射
TASK_ROUTING = {
    "复刻": "vision_replicate",
    "复制": "vision_replicate",
    "模仿": "vision_replicate",
    "还原": "vision_replicate",
    " replicate": "vision_replicate",
    "导演": "multimodal_direct",
    "分镜": "multimodal_direct",
    "剧本": "multimodal_direct",
    "生成": "aigc_native",
    "AI生成": "aigc_native",
    "零素材": "aigc_native",
    "创造": "aigc_native",
    "风格": "style_transfer",
    "画风": "style_transfer",
    "调色": "style_transfer",
    "色调": "style_transfer",
    "迁移": "style_transfer",
    "混剪": "cinematic_edit",
    "剪辑": "cinematic_edit",
    "智能剪": "cinematic_edit",
    "电影感": "cinematic_edit",
}


class FrontierSystem:
    """前沿能力统一调度系统
    
    5大能力:
      1. vision_replicate  — VISION自动复刻
      2. multimodal_direct — 多模态导演
      3. aigc_native       — AIGC原生工作流
      4. style_transfer    — 风格迁移
      5. cinematic_edit    — 智能剪辑
    """

    def __init__(self):
        self._engines: Dict[str, Any] = {}
        self._init_engines()

    def _init_engines(self):
        """懒初始化所有引擎"""
        # 不立即初始化，按需加载
        self._engine_classes = {
            "vision_replicate": VisionReplicateEngine,
            "multimodal_direct": None,  # 使用 MultimodalDirector
            "aigc_native": AIGCNativeWorkflow,
            "style_transfer": StyleTransferEngine,
            "cinematic_edit": CinematicEditEngine,
        }
        log("FrontierSystem 已初始化, 5大能力就绪")

    def _get_engine(self, name: str):
        """获取引擎实例（懒加载）"""
        if name not in self._engines:
            if name == "multimodal_direct":
                from multimodal_director import MultimodalDirector
                self._engines[name] = MultimodalDirector()
            else:
                cls = self._engine_classes.get(name)
                if cls:
                    self._engines[name] = cls()
                else:
                    raise ValueError(f"未知能力: {name}")
        return self._engines[name]

    # ----------------------------------------------------------------
    #  统一入口
    # ----------------------------------------------------------------

    def execute(self, task_description: str, **inputs) -> Dict:
        """统一入口 — 根据任务描述自动路由到合适的能力
        
        Args:
            task_description: 任务描述（中文）
            **inputs: 可选参数
                - video: 参考视频路径
                - materials: 素材列表
                - music: 音乐路径
                - images: 图片列表
                - output_dir: 输出目录
        
        Returns:
            执行结果字典
        """
        log(f"\n{'='*60}")
        log(f"  FrontierSystem 任务: {task_description[:50]}...")
        log(f"{'='*60}")

        # 自动路由
        capability = self._route_task(task_description)
        log(f"  路由到: {capability}")

        # 执行
        return self._execute_capability(capability, task_description, **inputs)

    def _route_task(self, description: str) -> str:
        """根据任务描述路由到能力"""
        for keyword, capability in TASK_ROUTING.items():
            if keyword in description:
                return capability

        # 默认: 如果有video参数 → vision_replicate
        # 如果有materials → cinematic_edit
        # 否则 → multimodal_direct
        return "multimodal_direct"

    def _execute_capability(self, capability: str, description: str,
                            **inputs) -> Dict:
        """执行指定能力"""
        if capability == "vision_replicate":
            video = inputs.pop("video", "")
            if not video:
                return {"error": "VISION复刻需要 video 参数"}
            return self.vision_replicate(video, **inputs)

        elif capability == "multimodal_direct":
            inputs.pop("text", None)
            return self.multimodal_direct(description, **inputs)

        elif capability == "aigc_native":
            inputs.pop("prompt", None)
            return self.aigc_native(description, **inputs)

        elif capability == "style_transfer":
            source = inputs.pop("source", inputs.pop("video", ""))
            style_ref = inputs.pop("style_ref", "")
            if not source:
                return {"error": "风格迁移需要 source 参数"}
            return self.style_transfer(source, style_ref, **inputs)

        elif capability == "cinematic_edit":
            inputs.pop("description", None)
            return self.cinematic_edit(description=description, **inputs)

        else:
            return {"error": f"未知能力: {capability}"}

    # ----------------------------------------------------------------
    #  显式调用接口
    # ----------------------------------------------------------------

    def vision_replicate(self, video_path: str, **kwargs) -> Dict:
        """VISION自动复刻"""
        engine = self._get_engine("vision_replicate")
        return engine.execute(video_path, **kwargs)

    def multimodal_direct(self, description: str, **kwargs) -> Dict:
        """多模态导演"""
        director = self._get_engine("multimodal_direct")
        materials = kwargs.get("materials")
        video = kwargs.get("video", "")
        music = kwargs.get("music", "")
        images = kwargs.get("images")

        if video and music:
            script = director.direct_mixed(
                text=description, video=video, music=music,
                images=images, materials=materials,
            )
        elif video:
            script = director.direct_from_video(video, materials)
        elif music:
            script = director.direct_from_music(music, description, materials)
        elif images:
            script = director.direct_from_images(images, description, materials)
        else:
            script = director.direct_from_text(description, materials)

        # 保存剧本
        output_dir = kwargs.get("output_dir", "output/director")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        script_path = Path(output_dir) / "edit_script.json"
        script.save(str(script_path))

        return {
            "capability": "multimodal_direct",
            "status": "completed",
            "script": script.to_dict(),
            "script_path": str(script_path),
        }

    def aigc_native(self, prompt: str, **kwargs) -> Dict:
        """AIGC原生工作流"""
        engine = self._get_engine("aigc_native")
        return engine.execute(prompt, **kwargs)

    def style_transfer(self, source: str, style_ref: str = "",
                       style_description: str = "", **kwargs) -> Dict:
        """风格迁移"""
        engine = self._get_engine("style_transfer")
        return engine.execute(source, style_ref, style_description, **kwargs)

    def cinematic_edit(self, materials: List[str] = None,
                       music: str = "", description: str = "",
                       **kwargs) -> Dict:
        """智能剪辑"""
        engine = self._get_engine("cinematic_edit")
        return engine.execute(materials, music, description, **kwargs)

    # ----------------------------------------------------------------
    #  系统状态
    # ----------------------------------------------------------------

    def status(self) -> Dict:
        """返回系统状态"""
        return {
            "system": "FrontierSystem v1.0",
            "capabilities": {
                "vision_replicate": {
                    "name": "VISION自动复刻",
                    "status": "ready",
                    "description": VisionReplicateEngine.description,
                },
                "multimodal_direct": {
                    "name": "多模态导演",
                    "status": "ready",
                    "description": "文字/图片/视频/音乐任意输入，生成完整剧本",
                },
                "aigc_native": {
                    "name": "AIGC原生工作流",
                    "status": "ready",
                    "description": AIGCNativeWorkflow.description,
                },
                "style_transfer": {
                    "name": "风格迁移",
                    "status": "ready",
                    "description": StyleTransferEngine.description,
                },
                "cinematic_edit": {
                    "name": "智能剪辑",
                    "status": "ready",
                    "description": CinematicEditEngine.description,
                },
            },
        }


# ================================================================
#  CLI 测试
# ================================================================

if __name__ == "__main__":
    system = FrontierSystem()

    print("\n" + "=" * 60)
    print("  系统状态")
    print("=" * 60)
    status = system.status()
    for cap_id, cap_info in status["capabilities"].items():
        print(f"  [{cap_info['status']}] {cap_info['name']}: {cap_info['description']}")

    print("\n" + "=" * 60)
    print("  测试1: 自动路由 — 文字导演")
    print("=" * 60)
    result = system.execute("做一个进击的巨人高燃混剪")
    print(f"  状态: {result['status']}")
    if 'script' in result:
        script = result['script']
        print(f"  标题: {script.get('title', 'N/A')}")
        print(f"  段落: {len(script.get('segments', []))}")

    print("\n" + "=" * 60)
    print("  测试2: 自动路由 — 风格迁移")
    print("=" * 60)
    result2 = system.execute(
        "把这个视频调成赛博朋克风格",
        source="output_director/materials/01_Barricades全OP高燃.mp4",
    )
    print(f"  状态: {result2['status']}")

    print("\n" + "=" * 60)
    print("  测试3: 显式调用 — 智能剪辑")
    print("=" * 60)
    materials_dir = Path("output_director/materials")
    mp4_files = [str(f) for f in materials_dir.glob("*.mp4")][:3]
    result3 = system.cinematic_edit(
        materials=mp4_files,
        description="进击的巨人高燃混剪",
    )
    print(f"  状态: {result3['status']}")
    if 'output' in result3:
        out = result3['output']
        print(f"  总时长: {out.get('total_duration', 0):.1f}s")
        print(f"  段落数: {out.get('segment_count', 0)}")

    print("\n所有测试完成!")
