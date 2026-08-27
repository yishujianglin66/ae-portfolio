#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频效果逆向分析器 v2.0 - CV + VISION LLM 混合分析
====================================================

VRS (Video Reverse-engineering System) v2.0 核心模块。

在 v1.0 纯 CV 分析基础上，新增 VISION LLM 帧级分析能力：
1. CV 层：保留原版场景/转场/调色/运动/效果检测
2. VISION 层：通过 LLM 网关路由到视觉模型，识别 AE 效果/插件/混合模式/图层结构
3. 融合层：CV 量化指标 + VISION 语义判断 → 高保真参数表

成本优化策略：
- 先 CV 筛选关键帧（转场前后 + 等间隔采样），只把关键帧喂给 VISION
- 支持批量拼图模式（多帧合成一张图，减少调用次数）
- 感知哈希缓存，相似帧不重复调用

依赖：
- 必需：opencv-python, numpy, loguru, core.llm_gateway
- 可选：Pillow（图片压缩与网格拼图，未安装时降级为原始字节）
- 可选：scenedetect（场景检测，未安装时降级为 OpenCV 帧差法）

用法：
    # 单帧 VISION 分析
    python video_effect_analyzer_v2.py --test

    # 完整深度分析流程
    python video_effect_analyzer_v2.py --demo
"""
from __future__ import annotations

import asyncio
import base64
import importlib.util
import io
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

# -----------------------------------------------------------------------------
# 加载原版分析器（文件名含连字符，无法直接 import，用 importlib 动态加载）
# -----------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
_LEGACY_PATH = _PROJECT_ROOT / "video-effect-analyzer.py"

if not _LEGACY_PATH.exists():
    raise FileNotFoundError(f"原版分析器不存在: {_LEGACY_PATH}")

_spec = importlib.util.spec_from_file_location(
    "_video_effect_analyzer_legacy", _LEGACY_PATH
)
if _spec is None or _spec.loader is None:
    raise ImportError(f"无法加载原版分析器模块: {_LEGACY_PATH}")

_legacy_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy_module)
VideoEffectAnalyzer = _legacy_module.VideoEffectAnalyzer  # type: ignore

# -----------------------------------------------------------------------------
# LLM 网关（统一入口，禁止直连 Provider）
# -----------------------------------------------------------------------------
sys.path.insert(0, str(_PROJECT_ROOT))
from core.llm_gateway import (  # noqa: E402
    LLMResponse,
    TaskType,
    chat_with_routing,
    configure_from_env,
    llm_gateway,
)

# -----------------------------------------------------------------------------
# 可选依赖：Pillow
# -----------------------------------------------------------------------------
try:
    from PIL import Image  # type: ignore

    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    Image = None  # type: ignore


# =============================================================================
# VISION 系统提示词（基于 AE 效果视觉特征库）
# =============================================================================

VISION_SYSTEM_PROMPT = """你是 After Effects 视觉效果识别专家。任务：分析视频帧画面，识别所用的 AE 效果、插件、混合模式、图层结构，输出严格 JSON。

## 一、效果类型识别（effects[].type + name）

### blur 模糊类
- gaussian: 高斯模糊（各向同性均匀扩散，无方向偏好）
- directional: 定向模糊（单方向像素拉伸，运动拖尾）
- radial: 径向模糊（中心向外辐射，或绕中心旋转）
- camera_lens: 镜头模糊（高光多边形光斑，光圈叶片特征）
- box: 快速方框模糊（方块感，多次叠加接近高斯）
- compound: 复合模糊（区域差异，由控制图层决定）

### glow 发光类
- glow: 内置 Glow（颜色与原色一致，易饱和）
- deep_glow: Deep Glow（HDR 透亮感，高光不饱和，衰减柔和）
- s_glow: Sapphire S_Glow（分层质感：核心+扩散+微光）
- optical_flares: Optical Flares（镜头光斑、光环、镜头污渍）
- starglow: StarGlow（星形光线，4/6/8 点）
- saber: VC Saber（白色核心 + 颜色边缘发光，沿路径/文字/蒙版）
- shine: Trapcode Shine（专业体积光，光线颜色可渐变）

### particle 粒子类
- particular: Trapcode Particular（精灵纹理、Aux 二级粒子、3D 灯光影响、阴影）
- form: Trapcode Form（粒子排列成规则几何形态，网格/球体/OBJ）
- cc_particle_world: CC Particle World（内置 3D 粒子，参数少）
- cc_particle_systems: CC Particle Systems II（2D 粒子）

### distort 扭曲类
- turbulent_displace: 湍流置换（随机流体扭曲，Evolution 演化）
- wave_warp: 波形变形（周期性波形，正弦/方波/三角/锯齿）
- mesh_warp: 网格变形（局部变形，贝塞尔边界）
- liquify: 液化（手指推动感，局部像素流动）
- optics_compensation: 光学补偿（桶形/枕形畸变，鱼眼）
- cc_power_pin: 边角定位（四角独立拉伸，透视变形）

### color 调色类
- lumetri: Lumetri Color（多轮调色，色温，阴影/高光独立色调）
- curves: 曲线（S 曲线对比度，可分 RGB 通道）
- hue_saturation: 色相饱和度（整体或局部色相旋转）
- tritone: 三色调（高光/中间调/阴影三色映射）
- cc_toner: CC Toner
- lut: LUT 调色（电影级预设）

### transition 转场类
- linear_wipe: 线性擦除（直线擦除）
- radial_wipe: 径向擦除（扇形擦除）
- card_wipe: 卡片擦除（网格翻转，3D 透视）
- cc_block_load: CC Block Load（像素方块化）

### stylize 风格化
- find_edges: 查找边缘（线框风格）
- roughen_edges: 粗糙边缘（不规则锯齿）
- cc_glass: CC Glass（玻璃折射）

### generate 生成类
- cc_light_rays: CC 光束（从光源放射）
- fractal_noise: 分形噪波（云状/烟雾状纹理）
- cell_pattern: 单元格图案
- gradient_ramp: 渐变填充

### text 文字动画
- text_animator: 文字动画器（逐字动画）
- kinetic_typography: 动态排版

### camera_3d 3D 摄像机
- camera_tracker: 摄像机追踪（3D 解算）
- element_3d: Element 3D（OBJ 模型，PBR 材质）
- c4d_lite: Cinema 4D Lite（真实 3D 渲染）

### noise 噪点颗粒
- add_grain: 添加颗粒（胶片质感）
- noise: 杂色
- fractal_noise_texture: 分形噪波纹理叠加

### matte 遮罩
- vignette: 暗角（CC Vignette / Lumetri Vignette）

## 二、效果强度（intensity，0-100 整数）
- 0-20: 极弱，几乎不可察觉
- 20-40: 轻微
- 40-60: 中等
- 60-80: 明显
- 80-100: 极强

## 三、插件识别（matchName）
识别视觉指纹：
- Trapcode Particular: 精灵纹理 + 二级粒子 + 3D 灯光 + 阴影
- Trapcode Form: 粒子排列成规则几何
- Trapcode Shine: 自然衰减体积光
- VC Saber: 白色核心 + 颜色边缘，沿路径
- VC Optical Flares: 镜头光斑元素（光环/星形/污渍）
- VC Element 3D: 3D OBJ + PBR 材质
- VC Reflect: 倒影效果
- Newton: 物理模拟
- Red Giant Universe: 故障/VHS/全息（Universe 前缀）
- Boris FX Sapphire: S_ 前缀（S_Glow/S_Vignette/S_FilmEffect）
- AE 内置 matchName 示例：
  - Gaussian Blur: ADBE Gaussian Blur 2
  - Glow: ADBE Glo2
  - Deep Glow: ADBE Glo2
  - Lumetri Color: ADBE Lumetri Color
  - Directional Blur: ADBE Directional Blur
  - CC Radial Fast Blur: CC Radial Fast Blur
  - Turbulent Displace: ADBE Turbulent Displace
  - Wave Warp: ADBE Wave Warp
  - Camera Lens Blur: ADBE Camera Lens Blur
  - CC Particle World: CC Particle World
  - Optical Flares: VC Optical Flares
  - Saber: VC Saber

## 四、混合模式（blend_modes_detected）
基于叠加区域亮度/对比度/颜色变化推断：
- NORMAL: 正常（无混合）
- SCREEN: 滤色（变亮，暗部透明）→ 发光、光效叠加
- MULTIPLY: 相乘（变暗，亮部透明）→ 阴影、纹理叠加
- ADD: 相加（亮度直接相加，易过曝）→ 光效、粒子
- OVERLAY: 叠加（对比度增强）
- SOFT_LIGHT: 柔光（轻微对比度）
- HARD_LIGHT: 强光（强烈对比度）
- DIFFERENCE: 差值（负片效果）
- COLOR: 颜色（只改变颜色）
- LUMINOSITY: 亮度（只改变亮度）

## 五、图层结构（composition_structure）
判断画面中存在哪些图层角色：
- main_subject: 主体层（人物/物体/主角）
- adjustment_layer: 调整层（全局调色/效果应用）
- glow_layer: 光效层（独立发光/光斑/光束）
- particle_layer: 粒子层
- text_layer: 文字层
- background_layer: 背景层
- vignette_layer: 暗角层

## 六、风格标签（style_tags）
基于整体观感推断风格，可多选：
高燃、赛博朋克、霓虹、电影感、日漫风、美漫风、国风水墨、复古怀旧、
暗调情绪、清新日系、TVC广告感、AMV特效流、故障艺术、像素风、
梦幻柔光、科技未来、暗黑哥特、童话绘本

## 输出 JSON Schema（严格遵守）

{
  "effects": [
    {
      "type": "glow",
      "name": "Deep Glow",
      "matchName": "ADBE Glo2",
      "intensity": 75,
      "confidence": 0.85,
      "params": {"Glow Radius": 30, "Glow Intensity": 80, "Glow Threshold": 75},
      "layer_role": "adjustment_layer"
    }
  ],
  "blend_modes_detected": ["SCREEN", "ADD"],
  "composition_structure": {
    "main_subject": true,
    "adjustment_layer": true,
    "glow_layer": false,
    "particle_layer": false,
    "text_layer": false,
    "background_layer": true,
    "vignette_layer": false
  },
  "style_tags": ["高燃", "赛博朋克"],
  "overall_summary": "画面整体偏暖，主体人物有强烈发光晕染，疑似 Deep Glow 调整层。"
}

## 关键约束
1. 只输出 JSON，不要任何额外说明文字、Markdown 代码块标记或前后缀
2. 不确定的效果 confidence 降到 0.5 以下
3. 多个效果按 confidence 降序排列
4. params 参数名用 AE 标准英文（Glow Radius / Blurriness / Threshold 等）
5. 纯色或无效果画面，effects 返回空数组 []
6. intensity 必须是 0-100 整数
7. confidence 必须是 0-1 浮点数
"""


# =============================================================================
# 异步视频效果分析器 v2.0
# =============================================================================


class VideoEffectAnalyzerV2(VideoEffectAnalyzer):
    """增强版视频效果分析器 - 整合 CV 与 VISION LLM 能力。

    继承原版 VideoEffectAnalyzer 的全部 CV 分析能力，新增：
    - VISION LLM 帧级分析（效果类型/插件/混合模式/图层结构）
    - 智能关键帧筛选（转场前后 + 等间隔）
    - 批量拼图模式（降低 LLM 调用成本）
    - 感知哈希缓存（相似帧不重复调用）
    - CV + VISION 结果融合
    """

    # 每种 detail_level 对应的 VISION 采样间隔（秒）
    _VISION_SAMPLE_INTERVAL = {
        "quick": 5.0,
        "standard": 3.0,
        "full": 2.0,
    }

    # 转场前后各取多少帧送 VISION
    _TRANSITION_FRAME_PADDING = 3

    # VISION 调用超时（秒）— 多模态调用较慢，留足时间
    # 2026-07-20: 设为 90s（用户要求 60-90s 范围上限，兼顾成功率和效率）
    _VISION_TIMEOUT = 90

    # 批量拼图最大帧数
    _BATCH_MAX_FRAMES = 9

    # 感知哈希相似度阈值（Hamming 距离），低于此值视为相似帧
    _PHASH_HAMMING_THRESHOLD = 5

    def __init__(
        self,
        config_path: Optional[str] = None,
        max_image_size: int = 1024,
        frames_output_dir: Optional[str] = None,
        enable_vision: bool = True,
    ) -> None:
        """初始化 V2 分析器。

        Args:
            config_path: CV 分析配置文件路径（兼容原版）
            max_image_size: 送 VISION 前图片最长边压缩上限（像素）
            frames_output_dir: 关键帧图片输出目录，None 时用 output/vision_frames/
            enable_vision: 是否启用 VISION LLM 分析（False 时退化为纯 CV）
        """
        super().__init__(config_path=config_path)

        self.max_image_size = max_image_size
        self.enable_vision = enable_vision
        self.frames_output_dir = (
            Path(frames_output_dir)
            if frames_output_dir
            else _PROJECT_ROOT / "output" / "vision_frames"
        )

        # 感知哈希 → VISION 分析结果缓存
        self._vision_cache: Dict[str, Dict[str, Any]] = {}

        # LLM 网关可用性（懒检测）
        self._llm_checked: bool = False
        self._llm_usable: bool = False

        # 用量统计
        self._vision_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "cache_hits": 0,
            "frames_analyzed": 0,
        }

        if not _PIL_AVAILABLE:
            logger.warning(
                "Pillow 未安装，图片压缩与网格拼图将降级为原始字节模式。"
                "建议 pip install Pillow 以降低 VISION token 消耗。"
            )

    # -------------------------------------------------------------------------
    # 公共入口
    # -------------------------------------------------------------------------

    async def analyze_video_deep(
        self,
        video_path: str,
        detail_level: str = "full",
    ) -> Dict[str, Any]:
        """深度分析入口 - 整合 CV + VISION + 知识库。

        Args:
            video_path: 视频文件路径
            detail_level: 分析精度 quick/standard/full

        Returns:
            完整分析结果字典，包含 cv_result / vision_result / merged 三个层次
        """
        video_path_str = str(video_path)
        if not Path(video_path_str).exists():
            return {"success": False, "error": f"文件不存在: {video_path_str}"}

        logger.info(f"开始深度分析: {video_path_str} (detail={detail_level})")

        result: Dict[str, Any] = {
            "success": False,
            "video_path": video_path_str,
            "filename": os.path.basename(video_path_str),
            "analyze_time": datetime.now().isoformat(),
            "detail_level": detail_level,
            "analyzer_version": "2.0",
            "vision_enabled": self.enable_vision,
            "pil_available": _PIL_AVAILABLE,
        }

        # -------- 第 1 步：CV 层分析（同步阻塞，放线程池）--------
        try:
            cv_result = await asyncio.to_thread(
                self.analyze_video, video_path_str, detail_level
            )
            result["cv_result"] = cv_result
            logger.info(
                f"CV 层完成: success={cv_result.get('success')}, "
                f"scenes={cv_result.get('scene_count', 0)}, "
                f"transitions={len(cv_result.get('transitions', []))}"
            )
        except Exception as exc:
            logger.exception(f"CV 层分析异常: {exc}")
            result["error"] = f"CV 层失败: {exc}"
            return result

        if not cv_result.get("success"):
            result["error"] = f"CV 层失败: {cv_result.get('error', 'unknown')}"
            return result

        # -------- 第 2 步：VISION 层分析 --------
        vision_result: Dict[str, Any] = {
            "enabled": self.enable_vision,
            "available": False,
            "key_frames": [],
            "frame_analyses": [],
            "batch_analyses": [],
            "merged_summary": "",
            "stats": dict(self._vision_stats),
        }

        if not self.enable_vision:
            logger.info("VISION 层已禁用，跳过 LLM 分析")
            result["vision_result"] = vision_result
        elif not self._check_llm_available():
            logger.warning(
                "LLM 网关不可用（未配置 base_url/api_key），VISION 层降级为纯 CV"
            )
            vision_result["degraded_reason"] = "llm_gateway_unavailable"
            result["vision_result"] = vision_result
        else:
            try:
                vision_result = await self._run_vision_pipeline(
                    video_path_str, cv_result, detail_level
                )
            except Exception as exc:
                logger.exception(f"VISION 层异常，降级为纯 CV: {exc}")
                vision_result = {
                    "enabled": True,
                    "available": False,
                    "degraded_reason": f"vision_exception: {exc}",
                    "key_frames": [],
                    "frame_analyses": [],
                    "batch_analyses": [],
                    "merged_summary": "",
                    "stats": dict(self._vision_stats),
                }

        result["vision_result"] = vision_result

        # -------- 第 3 步：融合 CV + VISION --------
        try:
            merged = self._merge_cv_vision_results(cv_result, vision_result)
            result["merged_result"] = merged
            result["ae_parameters"] = merged.get("ae_parameters", cv_result.get("ae_parameters", {}))
            result["prompts"] = merged.get("prompts", cv_result.get("prompts", {}))
        except Exception as exc:
            logger.exception(f"结果融合异常: {exc}")
            result["merged_result"] = {"error": str(exc)}

        result["vision_stats"] = dict(self._vision_stats)
        result["success"] = True
        logger.info(
            f"深度分析完成: vision_calls={self._vision_stats['total_calls']}, "
            f"cache_hits={self._vision_stats['cache_hits']}, "
            f"frames={self._vision_stats['frames_analyzed']}"
        )
        return result

    # -------------------------------------------------------------------------
    # VISION 流水线
    # -------------------------------------------------------------------------

    async def _run_vision_pipeline(
        self,
        video_path: str,
        cv_result: Dict[str, Any],
        detail_level: str,
    ) -> Dict[str, Any]:
        """执行 VISION 分析流水线：选帧 → 抽帧 → 批量分析 → 汇总。"""
        frames_data = cv_result.get("frames_data", [])
        # 原版 _sample_frames 不返回 frames_data 字段，从 total_frames_sampled 重建
        if not frames_data:
            frames_data = self._reconstruct_frames_data(cv_result)

        scenes = cv_result.get("scenes", [])
        transitions = cv_result.get("transitions", [])

        # 1. 智能选帧
        key_frames = self._select_key_frames(frames_data, scenes, transitions)
        logger.info(f"VISION 选帧完成: {len(key_frames)} 个关键帧")

        if not key_frames:
            return {
                "enabled": True,
                "available": True,
                "key_frames": [],
                "frame_analyses": [],
                "batch_analyses": [],
                "merged_summary": "无可用关键帧",
                "stats": dict(self._vision_stats),
            }

        # 2. 抽取关键帧到磁盘
        self.frames_output_dir.mkdir(parents=True, exist_ok=True)
        video_stem = Path(video_path).stem
        frame_paths = await self._extract_frames_to_disk(
            video_path, key_frames, self.frames_output_dir, video_stem
        )
        logger.info(f"关键帧已落盘: {len(frame_paths)} 张 -> {self.frames_output_dir}")

        # 3. 批量 VISION 分析（网格拼图模式）
        batch_analyses: List[Dict[str, Any]] = []
        if len(frame_paths) > 1:
            batches = self._chunk_batches(frame_paths, self._BATCH_MAX_FRAMES)
            for batch_idx, batch in enumerate(batches):
                logger.info(
                    f"批量分析 {batch_idx + 1}/{len(batches)}: {len(batch)} 帧"
                )
                analysis = await self._analyze_frames_batch(batch)
                batch_analyses.append(analysis)

        # 4. 对未进入批次的单帧（或批次为 1）做单帧精分析
        frame_analyses: List[Dict[str, Any]] = []
        # 若帧数少，直接单帧分析更精确
        if len(frame_paths) <= 2:
            for fp in frame_paths:
                analysis = await self._analyze_frame_with_vision(fp)
                frame_analyses.append(analysis)

        # 5. 汇总
        all_effects = self._aggregate_effects(batch_analyses, frame_analyses)
        merged_summary = self._build_merged_summary(all_effects, cv_result)

        return {
            "enabled": True,
            "available": True,
            "key_frames": [
                {
                    "frame_idx": kf["frame_idx"],
                    "time_sec": kf.get("time_sec", 0),
                    "reason": kf.get("reason", ""),
                    "image_path": kf.get("image_path", ""),
                }
                for kf in key_frames
                if "image_path" in kf
            ],
            "frame_analyses": frame_analyses,
            "batch_analyses": batch_analyses,
            "aggregated_effects": all_effects,
            "merged_summary": merged_summary,
            "stats": dict(self._vision_stats),
        }

    # -------------------------------------------------------------------------
    # 智能选帧
    # -------------------------------------------------------------------------

    def _select_key_frames(
        self,
        frames_data: List[Dict[str, Any]],
        scenes: List[Dict[str, Any]],
        transitions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """智能选帧 - 从 CV 结果中选出转场前后、效果变化的关键帧。

        策略：
        1. 每 2-5 秒选 1 帧（基于 detail_level）
        2. 每个转场前后各取 3 帧（捕捉转场过程）
        3. 去重（同一 frame_idx 只保留一条，合并 reason）

        Args:
            frames_data: CV 采样帧特征列表
            scenes: 场景列表
            transitions: 转场列表

        Returns:
            关键帧元数据列表，每项含 frame_idx / time_sec / reason
        """
        if not frames_data:
            return []

        # detail_level → 采样间隔（秒）
        # 用 standard 作为默认（frames_data 本身已是采样后的）
        interval_sec = self._VISION_SAMPLE_INTERVAL.get("standard", 3.0)

        selected: Dict[int, Dict[str, Any]] = {}

        # 1. 等间隔采样
        last_selected_time = -1e9
        for fd in frames_data:
            t = fd.get("time_sec", 0)
            if t - last_selected_time >= interval_sec:
                idx = fd.get("frame_idx", 0)
                selected[idx] = {
                    "frame_idx": idx,
                    "time_sec": t,
                    "reason": "interval_sample",
                }
                last_selected_time = t

        # 2. 转场前后各 N 帧
        padding = self._TRANSITION_FRAME_PADDING
        frame_indices_sorted = sorted(
            [fd.get("frame_idx", 0) for fd in frames_data]
        )

        for tr in transitions:
            tr_time = tr.get("time_sec", 0)
            # 找到转场时间附近的采样帧
            nearby = []
            for fd in frames_data:
                ft = fd.get("time_sec", 0)
                if abs(ft - tr_time) <= padding * interval_sec:
                    nearby.append(fd)

            # 按时间距离排序，取前后各 padding 个
            nearby.sort(key=lambda x: abs(x.get("time_sec", 0) - tr_time))
            for fd in nearby[: padding * 2]:
                idx = fd.get("frame_idx", 0)
                reason = f"transition_{tr.get('type', 'unknown')}@{tr_time}s"
                if idx in selected:
                    # 合并 reason
                    existing = selected[idx]["reason"]
                    if reason not in existing:
                        selected[idx]["reason"] = f"{existing};{reason}"
                else:
                    selected[idx] = {
                        "frame_idx": idx,
                        "time_sec": fd.get("time_sec", 0),
                        "reason": reason,
                    }

        # 3. 场景边界帧
        for sc in scenes:
            start_frame = sc.get("start_frame", 0)
            if start_frame in selected:
                existing = selected[start_frame]["reason"]
                if "scene_start" not in existing:
                    selected[start_frame]["reason"] = f"{existing};scene_start"
            elif frame_indices_sorted:
                # 找最接近场景起点的采样帧
                closest = min(
                    frame_indices_sorted,
                    key=lambda x: abs(x - start_frame),
                )
                if abs(closest - start_frame) <= interval_sec * 30:  # 容差 1 秒
                    selected[closest] = {
                        "frame_idx": closest,
                        "time_sec": closest / 30.0,  # 近似
                        "reason": f"scene_{sc.get('scene_idx', '?')}_start",
                    }

        # 按时间排序
        result = sorted(selected.values(), key=lambda x: x.get("time_sec", 0))
        return result

    # -------------------------------------------------------------------------
    # 抽帧到磁盘
    # -------------------------------------------------------------------------

    async def _extract_frames_to_disk(
        self,
        video_path: str,
        key_frames: List[Dict[str, Any]],
        output_dir: Path,
        video_stem: str,
    ) -> List[str]:
        """从视频中抽取指定 frame_idx 的帧，保存为 PNG。

        Args:
            video_path: 视频文件路径
            key_frames: 关键帧元数据列表
            output_dir: 输出目录
            video_stem: 视频名（用于命名）

        Returns:
            落盘的帧图片路径列表（顺序与 key_frames 对应，已回填 image_path）
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        target_indices = {kf["frame_idx"]: i for i, kf in enumerate(key_frames)}

        # 对 video_stem 做 sanitize：去除 # 等会被 OpenCV 解释为占位符的特殊字符
        safe_stem = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in video_stem
        ).strip("_") or "video"

        def _extract_sync() -> List[str]:
            import cv2
            import numpy as np

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"无法打开视频抽帧: {video_path}")
                return []

            paths: List[str] = [""] * len(key_frames)
            try:
                frame_idx = 0
                while frame_idx < max(target_indices.keys(), default=-1) + 1:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if frame_idx in target_indices:
                        pos = target_indices[frame_idx]
                        out_path = (
                            output_dir
                            / f"{safe_stem}_kf{pos:03d}_f{frame_idx:06d}.png"
                        )
                        # 用 imencode + tofile 绕过 cv2.imwrite 对非 ASCII 路径的处理
                        ok, buf = cv2.imencode(".png", frame)
                        if ok:
                            buf.tofile(str(out_path))
                            paths[pos] = str(out_path)
                            key_frames[pos]["image_path"] = str(out_path)
                        else:
                            logger.warning(f"帧 {frame_idx} 编码失败")
                    frame_idx += 1
            finally:
                cap.release()
            return paths

        return await asyncio.to_thread(_extract_sync)

    # -------------------------------------------------------------------------
    # 单帧 VISION 分析
    # -------------------------------------------------------------------------

    async def _analyze_frame_with_vision(
        self,
        frame_path: str,
    ) -> Dict[str, Any]:
        """单帧 VISION 分析，返回效果类型/强度/插件判断。

        Args:
            frame_path: 帧图片路径

        Returns:
            分析结果字典，包含 effects / blend_modes / composition / style_tags
        """
        frame_path_str = str(frame_path)
        if not Path(frame_path_str).exists():
            return {
                "success": False,
                "frame_path": frame_path_str,
                "error": "frame_not_found",
            }

        # 感知哈希缓存检查
        phash = self._compute_phash(frame_path_str)
        if phash:
            for cached_hash, cached_result in self._vision_cache.items():
                if (
                    cached_hash
                    and self._hamming_distance(phash, cached_hash)
                    <= self._PHASH_HAMMING_THRESHOLD
                ):
                    logger.debug(f"缓存命中（相似帧）: {frame_path_str}")
                    self._vision_stats["cache_hits"] += 1
                    return {
                        "success": True,
                        "frame_path": frame_path_str,
                        "from_cache": True,
                        "cached_from_hash": cached_hash,
                        **cached_result,
                    }

        # 编码图片
        try:
            image_b64 = await asyncio.to_thread(self._encode_image_base64, frame_path_str)
        except Exception as exc:
            logger.warning(f"图片编码失败 {frame_path_str}: {exc}")
            self._vision_stats["failed_calls"] += 1
            return {
                "success": False,
                "frame_path": frame_path_str,
                "error": f"encode_failed: {exc}",
            }

        message = (
            "分析这一帧视频画面，识别所用的 AE 效果、插件、混合模式、图层结构。"
            "严格按照 JSON Schema 输出，不要任何额外文字。"
        )

        self._vision_stats["total_calls"] += 1
        self._vision_stats["frames_analyzed"] += 1

        try:
            response: LLMResponse = await asyncio.wait_for(
                chat_with_routing(
                    message=message,
                    task_type=TaskType.SCENE_DESCRIPTION,
                    system_prompt=VISION_SYSTEM_PROMPT,
                    temperature=0.3,
                    max_tokens=2048,
                    images=[image_b64],
                ),
                timeout=self._VISION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(f"VISION 调用超时 ({self._VISION_TIMEOUT}s): {frame_path_str}")
            self._vision_stats["failed_calls"] += 1
            return {
                "success": False,
                "frame_path": frame_path_str,
                "error": "timeout",
                "degraded": True,
            }
        except Exception as exc:
            logger.warning(f"VISION 调用异常 {frame_path_str}: {exc}")
            self._vision_stats["failed_calls"] += 1
            return {
                "success": False,
                "frame_path": frame_path_str,
                "error": str(exc),
                "degraded": True,
            }

        if not response.success:
            logger.warning(
                f"VISION 调用失败 {frame_path_str}: {response.error}"
            )
            self._vision_stats["failed_calls"] += 1
            return {
                "success": False,
                "frame_path": frame_path_str,
                "error": response.error,
                "degraded": True,
            }

        self._vision_stats["successful_calls"] += 1
        parsed = self._parse_vision_response(response.content)
        parsed.update(
            {
                "success": True,
                "frame_path": frame_path_str,
                "from_cache": False,
                "model": response.model,
                "provider": response.provider,
                "tokens_input": response.tokens_input,
                "tokens_output": response.tokens_output,
                "latency_ms": round(response.latency_ms, 1),
            }
        )

        # 写入缓存
        if phash:
            cache_payload = {
                k: v
                for k, v in parsed.items()
                if k
                not in {
                    "success",
                    "frame_path",
                    "from_cache",
                    "model",
                    "provider",
                    "tokens_input",
                    "tokens_output",
                    "latency_ms",
                }
            }
            self._vision_cache[phash] = cache_payload

        return parsed

    # -------------------------------------------------------------------------
    # 批量 VISION 分析（网格拼图）
    # -------------------------------------------------------------------------

    async def _analyze_frames_batch(
        self,
        frame_paths: List[str],
    ) -> Dict[str, Any]:
        """批量 VISION 分析 - 网格拼图模式，降低成本。

        将多帧合成为一张网格图，单次 LLM 调用分析全部帧。

        Args:
            frame_paths: 帧图片路径列表（建议 <= 9 张）

        Returns:
            批量分析结果，包含 per_frame 分析与整体汇总
        """
        if not frame_paths:
            return {"success": False, "error": "empty_batch"}

        # 单帧时直接走单帧分析
        if len(frame_paths) == 1:
            single = await self._analyze_frame_with_vision(frame_paths[0])
            return {
                "success": single.get("success", False),
                "batch_size": 1,
                "frame_paths": frame_paths,
                "per_frame": [single],
                "grid_mode": False,
            }

        # 缓存命中检查（全部命中则跳过 LLM 调用）
        phashes = [self._compute_phash(fp) for fp in frame_paths]
        all_cached = True
        per_frame: List[Dict[str, Any]] = []
        for fp, ph in zip(frame_paths, phashes):
            hit = None
            if ph:
                for cached_hash, cached_result in self._vision_cache.items():
                    if (
                        cached_hash
                        and self._hamming_distance(ph, cached_hash)
                        <= self._PHASH_HAMMING_THRESHOLD
                    ):
                        hit = {
                            "success": True,
                            "frame_path": fp,
                            "from_cache": True,
                            "cached_from_hash": cached_hash,
                            **cached_result,
                        }
                        self._vision_stats["cache_hits"] += 1
                        break
            if hit:
                per_frame.append(hit)
            else:
                all_cached = False
                per_frame.append({"frame_path": fp, "pending": True})

        if all_cached:
            logger.info(f"批次全部缓存命中 ({len(frame_paths)} 帧)")
            return {
                "success": True,
                "batch_size": len(frame_paths),
                "frame_paths": frame_paths,
                "per_frame": per_frame,
                "grid_mode": True,
                "all_cached": True,
            }

        # 生成网格拼图
        try:
            grid_b64 = await asyncio.to_thread(self._create_grid_image, frame_paths)
        except Exception as exc:
            logger.warning(
                f"网格拼图失败，降级为逐帧分析: {exc}"
            )
            # 降级：逐帧分析
            fallback_per_frame = []
            for fp in frame_paths:
                r = await self._analyze_frame_with_vision(fp)
                fallback_per_frame.append(r)
            return {
                "success": True,
                "batch_size": len(frame_paths),
                "frame_paths": frame_paths,
                "per_frame": fallback_per_frame,
                "grid_mode": False,
                "degraded_reason": f"grid_failed: {exc}",
            }

        # 构建批量分析消息
        frame_desc = "\n".join(
            f"  - 网格位置 {i + 1}: {Path(fp).name}"
            for i, fp in enumerate(frame_paths)
        )
        message = (
            f"下方是一张网格拼图，包含 {len(frame_paths)} 帧视频画面（按行优先排列）。\n"
            f"各帧位置：\n{frame_desc}\n\n"
            "请对每一帧分别识别 AE 效果/插件/混合模式/图层结构，"
            "并输出 JSON：\n"
            "{\n"
            '  "per_frame": [\n'
            '    {"frame_index": 1, "effects": [...], "blend_modes_detected": [...], '
            '"composition_structure": {...}, "style_tags": [...], "overall_summary": "..."},\n'
            '    {"frame_index": 2, ...}\n'
            "  ],\n"
            '  "batch_summary": "整批帧的整体效果趋势与共性"\n'
            "}\n"
            "严格 JSON，无额外文字。每帧的 effects 结构与单帧 Schema 一致。"
        )

        self._vision_stats["total_calls"] += 1
        self._vision_stats["frames_analyzed"] += len(frame_paths)

        try:
            response: LLMResponse = await asyncio.wait_for(
                chat_with_routing(
                    message=message,
                    task_type=TaskType.SCENE_DESCRIPTION,
                    system_prompt=VISION_SYSTEM_PROMPT,
                    temperature=0.3,
                    max_tokens=4096,
                    images=[grid_b64],
                ),
                timeout=self._VISION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"批量 VISION 超时 ({self._VISION_TIMEOUT}s)，降级逐帧分析"
            )
            self._vision_stats["failed_calls"] += 1
            fallback_per_frame = []
            for fp in frame_paths:
                r = await self._analyze_frame_with_vision(fp)
                fallback_per_frame.append(r)
            return {
                "success": True,
                "batch_size": len(frame_paths),
                "frame_paths": frame_paths,
                "per_frame": fallback_per_frame,
                "grid_mode": False,
                "degraded_reason": "batch_timeout",
            }
        except Exception as exc:
            logger.warning(f"批量 VISION 异常: {exc}")
            self._vision_stats["failed_calls"] += 1
            return {
                "success": False,
                "batch_size": len(frame_paths),
                "frame_paths": frame_paths,
                "per_frame": per_frame,
                "grid_mode": True,
                "error": str(exc),
            }

        if not response.success:
            logger.warning(f"批量 VISION 调用失败: {response.error}")
            self._vision_stats["failed_calls"] += 1
            # 降级逐帧
            fallback_per_frame = []
            for fp in frame_paths:
                r = await self._analyze_frame_with_vision(fp)
                fallback_per_frame.append(r)
            return {
                "success": True,
                "batch_size": len(frame_paths),
                "frame_paths": frame_paths,
                "per_frame": fallback_per_frame,
                "grid_mode": False,
                "degraded_reason": f"batch_failed: {response.error}",
            }

        self._vision_stats["successful_calls"] += 1
        parsed = self._parse_batch_response(response.content, len(frame_paths))

        # 用批量结果回填未命中的帧，并写缓存
        parsed_per_frame = parsed.get("per_frame", [])
        for i, fp in enumerate(frame_paths):
            if i < len(parsed_per_frame):
                frame_result = parsed_per_frame[i]
                # 合并到 per_frame
                for j, existing in enumerate(per_frame):
                    if existing.get("frame_path") == fp and existing.get("pending"):
                        per_frame[j] = {
                            "success": True,
                            "frame_path": fp,
                            "from_cache": False,
                            "model": response.model,
                            "provider": response.provider,
                            **frame_result,
                        }
                        # 写缓存
                        ph = phashes[i]
                        if ph:
                            cache_payload = {
                                k: v
                                for k, v in frame_result.items()
                                if k
                                not in {
                                    "success",
                                    "frame_path",
                                    "from_cache",
                                    "model",
                                    "provider",
                                }
                            }
                            self._vision_cache[ph] = cache_payload
                        break

        return {
            "success": True,
            "batch_size": len(frame_paths),
            "frame_paths": frame_paths,
            "per_frame": per_frame,
            "batch_summary": parsed.get("batch_summary", ""),
            "grid_mode": True,
            "model": response.model,
            "provider": response.provider,
            "tokens_input": response.tokens_input,
            "tokens_output": response.tokens_output,
            "latency_ms": round(response.latency_ms, 1),
        }

    # -------------------------------------------------------------------------
    # 结果融合
    # -------------------------------------------------------------------------

    def _merge_cv_vision_results(
        self,
        cv_result: Dict[str, Any],
        vision_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """融合 CV 和 VISION 分析结果。

        Args:
            cv_result: 原版 CV 分析结果
            vision_result: VISION 层分析结果

        Returns:
            融合后的结果，含 enhanced_ae_parameters / enhanced_prompts / confidence_map
        """
        merged: Dict[str, Any] = {
            "cv_summary": {
                "grading_style": cv_result.get("color_grading", {}).get("grading_style", ""),
                "rhythm": cv_result.get("rhythm_analysis", {}).get("rhythm", ""),
                "camera_motion": cv_result.get("motion_analysis", {}).get("camera_motion", ""),
                "scene_count": cv_result.get("scene_count", 0),
            },
            "vision_summary": {
                "available": vision_result.get("available", False),
                "degraded": "degraded_reason" in vision_result,
                "frame_count": len(vision_result.get("key_frames", [])),
                "merged_summary": vision_result.get("merged_summary", ""),
            },
        }

        # 聚合 VISION 识别到的效果
        aggregated = vision_result.get("aggregated_effects", [])
        if not aggregated:
            # 从 batch/frame analyses 重新聚合
            aggregated = self._aggregate_effects(
                vision_result.get("batch_analyses", []),
                vision_result.get("frame_analyses", []),
            )

        merged["vision_effects"] = aggregated
        merged["vision_blend_modes"] = self._aggregate_blend_modes(
            vision_result.get("batch_analyses", []),
            vision_result.get("frame_analyses", []),
        )
        merged["vision_style_tags"] = self._aggregate_style_tags(
            vision_result.get("batch_analyses", []),
            vision_result.get("frame_analyses", []),
        )

        # 增强 AE 参数表：在原版基础上叠加 VISION 识别的效果
        base_ae_params = cv_result.get("ae_parameters", {})
        enhanced_ae_params = self._enhance_ae_parameters(base_ae_params, aggregated)
        merged["ae_parameters"] = enhanced_ae_params

        # 增强提示词
        base_prompts = cv_result.get("prompts", {})
        enhanced_prompts = self._enhance_prompts(
            base_prompts, aggregated, merged["vision_style_tags"]
        )
        merged["prompts"] = enhanced_prompts

        # 置信度映射（CV 量化 + VISION 语义）
        merged["confidence_map"] = self._build_confidence_map(cv_result, aggregated)

        return merged

    # -------------------------------------------------------------------------
    # 辅助方法：图片处理
    # -------------------------------------------------------------------------

    def _encode_image_base64(self, image_path: str) -> str:
        """读取并压缩图片，返回 base64 编码字符串。"""
        if _PIL_AVAILABLE:
            with Image.open(image_path) as img:
                # 转换为 RGB（避免 PNG alpha / 调色板问题）
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                img.thumbnail(
                    (self.max_image_size, self.max_image_size),
                    Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.ANTIALIAS,
                )
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                raw = buf.getvalue()
        else:
            # Fallback：直接读取原始字节
            with open(image_path, "rb") as f:
                raw = f.read()
        return base64.b64encode(raw).decode("ascii")

    def _create_grid_image(self, image_paths: List[str]) -> str:
        """将多帧合成为网格拼图，返回 base64 字符串。"""
        if not image_paths:
            raise ValueError("image_paths 为空")

        if not _PIL_AVAILABLE:
            # Fallback：只用第一张
            logger.warning("PIL 未安装，网格拼图降级为第一帧")
            return self._encode_image_base64(image_paths[0])

        n = len(image_paths)
        cols = int(math.ceil(math.sqrt(n)))
        rows = int(math.ceil(n / cols))

        cell_size = max(128, self.max_image_size // max(cols, rows))

        # 加载并缩放每帧
        thumbnails: List[Any] = []
        for fp in image_paths:
            with Image.open(fp) as img:
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                img = img.copy()
                img.thumbnail((cell_size, cell_size), Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.ANTIALIAS)
                thumbnails.append(img)

        # 创建画布
        canvas_w = cols * cell_size
        canvas_h = rows * cell_size
        grid = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))

        for i, thumb in enumerate(thumbnails):
            r, c = i // cols, i % cols
            # 居中粘贴
            offset_x = c * cell_size + (cell_size - thumb.width) // 2
            offset_y = r * cell_size + (cell_size - thumb.height) // 2
            grid.paste(thumb, (offset_x, offset_y))

        buf = io.BytesIO()
        grid.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def _compute_phash(self, image_path: str) -> str:
        """计算简单的 8x8 平均感知哈希。

        无 PIL 时返回空字符串（关闭相似帧缓存）。
        """
        if not _PIL_AVAILABLE:
            return ""
        try:
            with Image.open(image_path) as img:
                gray = img.convert("L")
                gray = gray.resize((8, 8))
                pixels = list(gray.getdata())
            avg = sum(pixels) / len(pixels)
            bits = "".join("1" if p >= avg else "0" for p in pixels)
            # 转十六进制字符串
            return format(int(bits, 2), "016x")
        except Exception as exc:
            logger.debug(f"phash 计算失败 {image_path}: {exc}")
            return ""

    @staticmethod
    def _hamming_distance(hash_a: str, hash_b: str) -> int:
        """计算两个十六进制哈希字符串的 Hamming 距离。"""
        if not hash_a or not hash_b or len(hash_a) != len(hash_b):
            return 64  # 最大距离
        try:
            a = int(hash_a, 16)
            b = int(hash_b, 16)
            return bin(a ^ b).count("1")
        except ValueError:
            return 64

    # -------------------------------------------------------------------------
    # 辅助方法：VISION 响应解析
    # -------------------------------------------------------------------------

    def _parse_vision_response(self, content: str) -> Dict[str, Any]:
        """解析 VISION 返回的 JSON 内容，容错处理。"""
        if not content:
            return {"effects": [], "parse_error": "empty_content"}

        # 尝试提取 JSON（可能被包裹在 ```json``` 中）
        text = content.strip()
        if text.startswith("```"):
            # 去掉代码块标记
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # 尝试找到第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {"effects": [], "parse_error": "no_json_found", "raw": content[:500]}

        json_str = text[start : end + 1]
        try:
            parsed = json.loads(json_str)
            # 规范化字段
            if "effects" not in parsed:
                parsed["effects"] = []
            if "blend_modes_detected" not in parsed:
                parsed["blend_modes_detected"] = []
            if "composition_structure" not in parsed:
                parsed["composition_structure"] = {}
            if "style_tags" not in parsed:
                parsed["style_tags"] = []
            return parsed
        except json.JSONDecodeError as exc:
            logger.warning(f"VISION JSON 解析失败: {exc}")
            return {
                "effects": [],
                "parse_error": f"json_decode: {exc}",
                "raw": content[:500],
            }

    def _parse_batch_response(
        self,
        content: str,
        expected_count: int,
    ) -> Dict[str, Any]:
        """解析批量 VISION 响应。"""
        parsed = self._parse_vision_response(content)
        # 批量响应的 per_frame 字段
        per_frame = parsed.get("per_frame", [])
        if not per_frame:
            # 兼容：若模型直接返回单个效果列表，套到 per_frame[0]
            if parsed.get("effects"):
                per_frame = [parsed]
                parsed["per_frame"] = per_frame

        # 补齐长度
        while len(per_frame) < expected_count:
            per_frame.append({"effects": [], "parse_error": "missing_frame"})

        parsed["per_frame"] = per_frame
        return parsed

    # -------------------------------------------------------------------------
    # 辅助方法：聚合与融合
    # -------------------------------------------------------------------------

    def _aggregate_effects(
        self,
        batch_analyses: List[Dict[str, Any]],
        frame_analyses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """聚合所有帧的效果识别结果，按效果类型合并并取最高置信度。"""
        effect_map: Dict[str, Dict[str, Any]] = {}

        # 从批次提取
        for batch in batch_analyses:
            for fr in batch.get("per_frame", []):
                if not fr.get("success", True) and fr.get("pending"):
                    continue
                for eff in fr.get("effects", []) or []:
                    self._merge_effect_into(effect_map, eff)

        # 从单帧提取
        for fr in frame_analyses:
            if not fr.get("success", False):
                continue
            for eff in fr.get("effects", []) or []:
                self._merge_effect_into(effect_map, eff)

        # 按 confidence 降序
        result = sorted(
            effect_map.values(),
            key=lambda x: x.get("confidence", 0),
            reverse=True,
        )
        return result

    def _merge_effect_into(
        self,
        effect_map: Dict[str, Dict[str, Any]],
        eff: Dict[str, Any],
    ) -> None:
        """将单个效果合并进聚合 map。"""
        eff_type = eff.get("type") or eff.get("name") or "unknown"
        existing = effect_map.get(eff_type)
        if existing is None:
            effect_map[eff_type] = dict(eff)
            effect_map[eff_type]["occurrence"] = 1
            return

        existing["occurrence"] = existing.get("occurrence", 1) + 1
        # 取更高置信度的 params / matchName / intensity
        if eff.get("confidence", 0) > existing.get("confidence", 0):
            for key in ("name", "matchName", "intensity", "confidence", "params", "layer_role"):
                if key in eff:
                    existing[key] = eff[key]
        # intensity 取平均
        if "intensity" in eff and "intensity" in existing:
            existing["intensity"] = round(
                (existing["intensity"] + eff["intensity"]) / 2
            )

    def _aggregate_blend_modes(
        self,
        batch_analyses: List[Dict[str, Any]],
        frame_analyses: List[Dict[str, Any]],
    ) -> List[str]:
        """聚合所有帧检测到的混合模式（去重）。"""
        modes: List[str] = []
        seen = set()

        def _collect(fr: Dict[str, Any]) -> None:
            for m in fr.get("blend_modes_detected", []) or []:
                # 兼容新格式：元素可能是 {"mode": "SCREEN"} 字典
                if isinstance(m, dict):
                    m = m.get("mode")
                if not m:
                    continue
                if m not in seen:
                    seen.add(m)
                    modes.append(m)

        for batch in batch_analyses:
            for fr in batch.get("per_frame", []):
                _collect(fr)
        for fr in frame_analyses:
            _collect(fr)
        return modes

    def _aggregate_style_tags(
        self,
        batch_analyses: List[Dict[str, Any]],
        frame_analyses: List[Dict[str, Any]],
    ) -> List[str]:
        """聚合所有帧的风格标签（按出现频次降序）。"""
        tag_count: Dict[str, int] = {}

        def _collect(fr: Dict[str, Any]) -> None:
            for t in fr.get("style_tags", []) or []:
                tag_count[t] = tag_count.get(t, 0) + 1

        for batch in batch_analyses:
            for fr in batch.get("per_frame", []):
                _collect(fr)
        for fr in frame_analyses:
            _collect(fr)

        return sorted(tag_count.keys(), key=lambda x: tag_count[x], reverse=True)

    def _build_merged_summary(
        self,
        effects: List[Dict[str, Any]],
        cv_result: Dict[str, Any],
    ) -> str:
        """构建 CV + VISION 融合的整体描述。"""
        parts: List[str] = []
        if effects:
            top = effects[:3]
            names = [e.get("name") or e.get("type", "?") for e in top]
            parts.append(f"VISION 识别到 {len(effects)} 个效果（Top: {', '.join(names)}）")

        cv_style = cv_result.get("color_grading", {}).get("grading_style", "")
        if cv_style:
            parts.append(f"CV 调色风格: {cv_style}")

        rhythm = cv_result.get("rhythm_analysis", {}).get("rhythm", "")
        if rhythm:
            parts.append(f"剪辑节奏: {rhythm}")

        return " | ".join(parts) if parts else "无可用摘要"

    # -------------------------------------------------------------------------
    # 辅助方法：AE 参数表增强
    # -------------------------------------------------------------------------

    def _enhance_ae_parameters(
        self,
        base_params: Dict[str, Any],
        vision_effects: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """在原版 AE 参数表基础上叠加 VISION 识别的效果。"""
        enhanced = json.loads(json.dumps(base_params))  # 深拷贝
        if "effects" not in enhanced:
            enhanced["effects"] = []
        if "adjustment_layers" not in enhanced:
            enhanced["adjustment_layers"] = []

        for eff in vision_effects:
            if eff.get("confidence", 0) < 0.4:
                continue  # 低置信度不写入参数表
            entry = {
                "name": f"VISION_{eff.get('name', eff.get('type', 'unknown'))}",
                "effect": eff.get("name", eff.get("type", "")),
                "matchName": eff.get("matchName", ""),
                "intensity": eff.get("intensity", 0),
                "confidence": eff.get("confidence", 0),
                "source": "vision_llm",
                "params": eff.get("params", {}),
            }
            enhanced["effects"].append(entry)

            # 调整层判断
            role = eff.get("layer_role", "")
            if role == "adjustment_layer":
                enhanced["adjustment_layers"].append({
                    "name": f"VISION_{eff.get('name', eff.get('type', 'unknown'))}",
                    "effect": eff.get("name", eff.get("type", "")),
                    "params": eff.get("params", {}),
                    "source": "vision_llm",
                })

        enhanced["vision_enhanced"] = True
        return enhanced

    def _enhance_prompts(
        self,
        base_prompts: Dict[str, Any],
        vision_effects: List[Dict[str, Any]],
        style_tags: List[str],
    ) -> Dict[str, Any]:
        """增强 MCP 提示词，加入 VISION 识别的效果与风格。"""
        enhanced = json.loads(json.dumps(base_prompts))

        style_desc = enhanced.get("style_description", "")
        if style_tags:
            style_desc += f" VISION 风格标签：{', '.join(style_tags[:6])}。"
        if vision_effects:
            eff_names = [
                e.get("name") or e.get("type", "?")
                for e in vision_effects[:5]
                if e.get("confidence", 0) >= 0.5
            ]
            if eff_names:
                style_desc += f" VISION 识别效果：{', '.join(eff_names)}。"
        enhanced["style_description"] = style_desc

        mcp_prompt = enhanced.get("mcp_prompt", "")
        vision_lines: List[str] = []
        for eff in vision_effects:
            if eff.get("confidence", 0) < 0.5:
                continue
            params = eff.get("params", {})
            param_str = ", ".join(f"{k}={v}" for k, v in params.items()) if params else ""
            line = f"VISION: 添加 {eff.get('name', eff.get('type', '未知'))}"
            if param_str:
                line += f" ({param_str})"
            if eff.get("intensity"):
                line += f" [强度 {eff['intensity']}]"
            vision_lines.append(line)

        if vision_lines:
            enhanced["mcp_prompt"] = mcp_prompt + "\n" + "\n".join(vision_lines)

        tags = enhanced.get("tags", [])
        for st in style_tags:
            if st not in tags:
                tags.append(st)
        enhanced["tags"] = tags

        return enhanced

    def _build_confidence_map(
        self,
        cv_result: Dict[str, Any],
        vision_effects: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """构建置信度映射：CV 量化指标 + VISION 语义判断的交叉验证。"""
        cv_effects = cv_result.get("visual_effects", {}).get("detected_effects", [])
        cv_types = {e.get("type") for e in cv_effects if e.get("type")}
        vision_types = {
            e.get("type") for e in vision_effects if e.get("type")
        }

        # 提取更细粒度的 VISION type（glow/blur 等）
        vision_coarse = set()
        for v in vision_types:
            if isinstance(v, str):
                # 取主要类型（如 deep_glow → glow）
                if "_" in v:
                    vision_coarse.add(v.split("_")[-1])
                vision_coarse.add(v)

        confirmed = cv_types & vision_coarse
        cv_only = cv_types - vision_coarse
        vision_only = vision_coarse - cv_types

        return {
            "cv_detected_count": len(cv_types),
            "vision_detected_count": len(vision_types),
            "cross_confirmed": sorted(confirmed),
            "cv_only": sorted(cv_only),
            "vision_only": sorted(vision_only),
            "agreement_score": (
                len(confirmed) / max(len(cv_types | vision_coarse), 1)
            ),
        }

    # -------------------------------------------------------------------------
    # 辅助方法：杂项
    # -------------------------------------------------------------------------

    def _check_llm_available(self) -> bool:
        """检查 LLM 网关是否可用（懒检测，只检测一次）。"""
        if self._llm_checked:
            return self._llm_usable
        self._llm_checked = True
        try:
            # 尝试从环境变量配置
            if not llm_gateway.is_available():
                configure_from_env()
            self._llm_usable = llm_gateway.is_available()
        except Exception as exc:
            logger.warning(f"LLM 网关检测异常: {exc}")
            self._llm_usable = False
        if not self._llm_usable:
            logger.warning(
                "LLM 网关不可用。请配置 AEKV_LLM_BASE_URL 和 AEKV_LLM_API_KEY 环境变量。"
            )
        return self._llm_usable

    def _reconstruct_frames_data(self, cv_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从 CV 结果重建 frames_data（原版未保留时）。

        原版 _sample_frames 不写入 cv_result，这里基于 scenes/transitions
        的时间点重建一个最小可用的 frames_data 供选帧使用。
        """
        basic = cv_result.get("basic_info", {})
        fps = basic.get("fps", 30.0)
        duration = basic.get("duration", 0)
        total_sampled = cv_result.get("total_frames_sampled", 0)

        frames: List[Dict[str, Any]] = []
        if total_sampled > 0 and duration > 0:
            interval_sec = duration / total_sampled
            for i in range(total_sampled):
                frames.append(
                    {
                        "frame_idx": int(i * interval_sec * fps),
                        "time_sec": round(i * interval_sec, 3),
                    }
                )
        elif duration > 0:
            # 退化：每秒 1 帧
            for sec in range(int(duration) + 1):
                frames.append(
                    {"frame_idx": int(sec * fps), "time_sec": float(sec)}
                )
        return frames

    @staticmethod
    def _chunk_batches(
        items: List[Any],
        chunk_size: int,
    ) -> List[List[Any]]:
        """将列表切分为多个批次。"""
        if chunk_size <= 0:
            return [items]
        return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]

    def get_vision_stats(self) -> Dict[str, Any]:
        """获取 VISION 调用统计。"""
        return {
            "vision_stats": dict(self._vision_stats),
            "cache_size": len(self._vision_cache),
            "llm_usable": self._llm_usable,
            "gateway_stats": llm_gateway.get_stats(),
        }


# =============================================================================
# CLI 测试入口
# =============================================================================


def _print_json(label: str, data: Any) -> None:
    """格式化打印 JSON。"""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    try:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    except Exception as exc:
        print(f"(序列化失败: {exc})\n{data}")


async def _run_test_mode() -> None:
    """--test 模式：用 frames/frame_001.png 测试单帧 VISION 分析。"""
    frame_path = _PROJECT_ROOT / "frames" / "frame_001.png"
    if not frame_path.exists():
        print(f"错误：测试帧不存在: {frame_path}")
        print("请确认 frames/ 目录下有 frame_001.png")
        return

    print(f"测试帧: {frame_path}")

    analyzer = VideoEffectAnalyzerV2(enable_vision=True)
    if not analyzer._check_llm_available():
        print(
            "警告：LLM 网关不可用，将仅演示 CV 侧能力（图片特征读取）。\n"
            "请配置 AEKV_LLM_BASE_URL / AEKV_LLM_API_KEY 后重试。"
        )

    # 单帧分析
    result = await analyzer._analyze_frame_with_vision(str(frame_path))
    _print_json("单帧 VISION 分析结果", result)

    # 统计
    _print_json("VISION 统计", analyzer.get_vision_stats())


async def _run_demo_mode() -> None:
    """--demo 模式：用 output/test_sample.mp4 演示完整深度分析流程。"""
    video_path = _PROJECT_ROOT / "output" / "test_sample.mp4"
    if not video_path.exists():
        print(f"错误：测试视频不存在: {video_path}")
        print("请确认 output/test_sample.mp4 存在")
        return

    print(f"演示视频: {video_path}")

    analyzer = VideoEffectAnalyzerV2(enable_vision=True)

    if not analyzer._check_llm_available():
        print(
            "警告：LLM 网关不可用，VISION 层将自动降级为纯 CV。\n"
            "请配置 AEKV_LLM_BASE_URL / AEKV_LLM_API_KEY 以启用 VISION。"
        )

    result = await analyzer.analyze_video_deep(str(video_path), detail_level="full")

    # 摘要
    _print_json(
        "深度分析摘要",
        {
            "success": result.get("success"),
            "video_path": result.get("video_path"),
            "detail_level": result.get("detail_level"),
            "analyzer_version": result.get("analyzer_version"),
            "vision_enabled": result.get("vision_enabled"),
            "cv_scene_count": result.get("cv_result", {}).get("scene_count"),
            "cv_transitions": len(result.get("cv_result", {}).get("transitions", [])),
            "vision_available": result.get("vision_result", {}).get("available"),
            "vision_key_frames": len(result.get("vision_result", {}).get("key_frames", [])),
            "vision_batch_count": len(result.get("vision_result", {}).get("batch_analyses", [])),
            "vision_summary": result.get("vision_result", {}).get("merged_summary"),
            "vision_stats": result.get("vision_stats"),
            "merged_confidence": result.get("merged_result", {}).get("confidence_map"),
        },
    )

    # 完整结果输出到文件
    out_file = _PROJECT_ROOT / "output" / "vision_analysis_demo.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n完整结果已写入: {out_file}")


def main() -> None:
    """CLI 入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="视频效果逆向分析器 v2.0 - CV + VISION LLM 混合分析",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="单帧 VISION 分析测试（用 frames/frame_001.png）",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="完整深度分析流程演示（用 output/test_sample.mp4）",
    )
    args = parser.parse_args()

    if args.test:
        asyncio.run(_run_test_mode())
    elif args.demo:
        asyncio.run(_run_demo_mode())
    else:
        parser.print_help()
        print("\n使用示例：")
        print("  python video_effect_analyzer_v2.py --test")
        print("  python -m vrs.video_effect_analyzer_v2 --demo")
        print(
            "\n编程调用：\n"
            "  import asyncio\n"
            "  from vrs.video_effect_analyzer_v2 import VideoEffectAnalyzerV2\n"
            "  analyzer = VideoEffectAnalyzerV2()\n"
            "  result = asyncio.run(analyzer.analyze_video_deep('video.mp4', 'full'))\n"
        )


if __name__ == "__main__":
    main()
