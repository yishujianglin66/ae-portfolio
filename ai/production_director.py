#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ProductionDirector — 生产级导演系统统一入口
============================================

端到端视频生产管线：从素材输入到成片输出，一条命令完成。

核心能力:
1. 感知层: 真实节拍检测 + 情绪曲线 + 素材内容分析 + 歌词-节拍绑定
2. 编排层: 情绪驱动段落规划 + 素材智能匹配 + 文字动画编排
3. 执行层: FFmpeg踩拍剪辑 + PIL文字叠加 + BGM混音
4. 验证层: ffprobe质量检查

用法:
    director = ProductionDirector()
    output = director.render(
        video_sources=["levi_amv.mp4"],
        bgm_path="bgm.mp3",
        lyrics=[(0.0, 1.5, "歌词", "gold"), ...],
        output_dir="output/",
    )
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 项目根目录
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# 导入核心模块
from ae.beat_detector import BeatDetector, BeatInfo
from ae.emotion_curve_generator import EmotionCurveGenerator, EmotionCurve
from ae.visual_content_analyzer import VisualContentAnalyzer, MaterialTag
from core.temporal_analyzer import TemporalAnalyzer, MotionProfile, ShotStructure
from core.audiovisual_correlator import AudioVisualCorrelator
from ae.text_animation_engine import (
    TextAnimationEngine, TextAnimation, TextStyle, AnimationConfig,
    AnimationPreset, MOOD_COLORS, POSITION_MAP,
)
from ai.material_intelligence import (
    MaterialIntelligenceEngine, MaterialIntelTag, MaterialIndex,
)


# ================================================================
#  数据结构
# ================================================================

@dataclass
class DirectorSegment:
    """导演段落"""
    index: int
    start_time: float       # 在输出视频中的起始时间
    end_time: float         # 在输出视频中的结束时间
    duration: float
    mood: str               # intro/build/drop/climax/break/outro
    energy: float           # 0.0 ~ 1.0
    source_file: str        # 使用的素材文件路径
    source_start: float     # 素材内的起始时间
    text_overlay: Optional[Dict]  # {lyric, start, end, color, mood}
    color_grade: str
    transition: str
    # ---- 方向B扩展（2026-08-10）----
    speed: float = 1.0                       # 段落播放速度（0.25~4.0，<1慢放 >1加速）
    transition_params: Optional[Dict] = None  # {type, duration} 显式转场参数，优先于 transition 标签
    zoompan_effect: Optional[str] = None       # 运镜效果: zoom_in/zoom_out/pan_left/diag_pan
    onset_times: Optional[List[float]] = None  # 镜头内 onset 时间点列表（输出视频相对时间）


@dataclass
class DirectorScript:
    """导演剧本"""
    title: str
    total_duration: float
    bgm_path: str
    bgm_start_sec: float
    segments: List[DirectorSegment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "total_duration": self.total_duration,
            "bgm_path": self.bgm_path,
            "bgm_start_sec": self.bgm_start_sec,
            "segments": [
                {
                    "index": s.index, "start_time": s.start_time,
                    "end_time": s.end_time, "duration": s.duration,
                    "mood": s.mood, "energy": s.energy,
                    "source_file": s.source_file, "source_start": s.source_start,
                    "text_overlay": s.text_overlay,
                    "color_grade": s.color_grade, "transition": s.transition,
                    "speed": s.speed, "transition_params": s.transition_params,
                    "zoompan_effect": s.zoompan_effect,
                    "onset_times": s.onset_times,
                }
                for s in self.segments
            ],
            "metadata": self.metadata,
        }

    # ── P2: YAML化 (借鉴OpenMontage: 剧本即可读可diff的数据文件) ──
    def to_yaml(self) -> str:
        """序列化为YAML (含切点/时长/speed/技巧/调色全部字段)"""
        import yaml
        return yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> "DirectorScript":
        """从YAML反序列化 (跨版本节奏骨架对比/回放)"""
        import yaml
        d = yaml.safe_load(text)
        segs = [DirectorSegment(
            index=s.get("index", i),
            start_time=s["start_time"], end_time=s["end_time"],
            duration=s["duration"], mood=s.get("mood", ""),
            energy=s.get("energy", 0.0), source_file=s.get("source_file", ""),
            source_start=s.get("source_start", 0.0),
            text_overlay=s.get("text_overlay"),
            color_grade=s.get("color_grade", ""),
            transition=s.get("transition", "cut"),
            speed=s.get("speed", 1.0),
            transition_params=s.get("transition_params"),
            zoompan_effect=s.get("zoompan_effect"),
            onset_times=s.get("onset_times"),
        ) for i, s in enumerate(d.get("segments", []))]
        return cls(title=d.get("title", ""),
                   total_duration=d.get("total_duration", 0.0),
                   bgm_path=d.get("bgm_path", ""),
                   bgm_start_sec=d.get("bgm_start_sec", 0.0),
                   segments=segs, metadata=d.get("metadata", {}))

    def save_yaml(self, path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_yaml(), encoding="utf-8")
        return p


def export_decision_log(script: DirectorScript, path,
                        rationale: Optional[Dict[int, Dict]] = None) -> Path:
    """P2: 导出镜头决策日志 (每镜: 为何选该技巧/素材/速度/转场)

    Args:
        script:    导演剧本
        path:      输出路径 (.yaml 或 .md, 按后缀分流)
        rationale: {seg_index: {"material":.., "speed":.., "tech":.., "transition":..}}
                   调用方在编排时记录的显式决策依据; 缺失时从字段推导兜底。
    """
    rationale = rationale or {}
    entries = []
    for s in script.segments:
        r = rationale.get(s.index, {})
        entries.append({
            "index": s.index,
            "time": f"{round(s.start_time, 3)}-{round(s.end_time, 3)}s",
            "duration": round(s.duration, 3),
            "mood": s.mood, "energy": round(s.energy, 3),
            "source": Path(s.source_file).name if s.source_file else "",
            "source_start": round(s.source_start, 3),
            "speed": s.speed,
            "technique": s.zoompan_effect or "static",
            "transition": s.transition,
            "color_grade": s.color_grade,
            "rationale": {
                "material": r.get("material") or f"情绪{s.mood}能量{s.energy:.2f}匹配的可用素材窗口",
                "speed": r.get("speed") or f"音乐动态映射: mood={s.mood}→{s.speed}x",
                "technique": r.get("technique") or (
                    f"运镜{s.zoompan_effect}" if s.zoompan_effect else "常规镜头无需特效运镜"),
                "transition": r.get("transition") or f"段落边界/节拍强度决定: {s.transition}",
            },
        })
    payload = {"title": script.title, "total_duration": script.total_duration,
               "bgm_path": script.bgm_path, "segment_count": len(script.segments),
               "decisions": entries}

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() in (".yaml", ".yml"):
        import yaml
        p.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                     encoding="utf-8")
    else:  # .md 人工审查视图
        lines = [f"# 决策日志 — {script.title}", "",
                 f"总时长 {script.total_duration:.2f}s | {len(script.segments)}镜 | BGM: {Path(script.bgm_path).name}", "",
                 "| # | 时间 | 时长 | 情绪 | 速度 | 技巧 | 转场 | 素材 | 决策依据 |",
                 "|---|------|------|------|------|------|------|------|----------|"]
        for e in entries:
            why = "; ".join(f"{k}:{v}" for k, v in e["rationale"].items())
            lines.append(f"| {e['index']} | {e['time']} | {e['duration']}s | {e['mood']} "
                         f"| {e['speed']}x | {e['technique']} | {e['transition']} "
                         f"| {e['source']} | {why} |")
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


@dataclass
class RenderResult:
    """渲染结果"""
    output_path: str
    success: bool
    duration: float = 0.0
    file_size_mb: float = 0.0
    resolution: Tuple[int, int] = (0, 0)
    fps: int = 0
    has_audio: bool = False
    elapsed_time: float = 0.0
    error_message: str = ""
    # 生产级内容复核
    content_verified: Optional[bool] = None   # None=未复核, True/False=复核结果
    verification_reason: str = ""


# ================================================================
#  调色预设（每段落情绪对应的 FFmpeg eq 参数）
# ================================================================

COLOR_PRESETS = {
    "intro":   {"saturation": 1.35, "contrast": 1.04, "brightness": 0.02},
    "build":   {"saturation": 1.4,  "contrast": 1.06, "brightness": 0.0},
    "drop":    {"saturation": 1.5,  "contrast": 1.08, "brightness": -0.02},
    "climax":  {"saturation": 1.5,  "contrast": 1.10, "brightness": -0.03},
    "break":   {"saturation": 1.3,  "contrast": 1.03, "brightness": 0.03},
    "outro":   {"saturation": 1.35, "contrast": 1.05, "brightness": 0.01},
}

# ================================================================
#  变速预设（方向B：情绪驱动的播放速度，需 render(use_speed_ramp=True) 启用）
# ================================================================

SPEED_PRESETS = {
    # 漫剪惯例（2026-08-12 v23实测修正）：
    #   build 加速蓄力(>1) → drop 原速爆发(=1, 卡点瞬间不能慢放!)
    #   break 慢放缓冲(<1, 爆发后子弹时间) → outro 缓收
    "intro":   1.0,
    "build":   1.3,    # 蓄力段加速，积累能量（原 1.0）
    "drop":    1.0,    # 爆发段原速，卡点干脆（原 0.8 慢放会吃掉冲击！）
    "climax":  1.1,    # 高能段微加速，保持冲击
    "break":   0.85,   # 缓冲段轻慢放（爆发后的子弹时间）
    "outro":   0.9,
}

# ================================================================
#  转场映射（方向B：剧本转场标签 → ffmpeg xfade 滤镜，均已实测可用）
# ================================================================

XFADE_MAP = {
    # 剧本标签: (xfade滤镜名, 默认时长秒)
    "fade":   ("fadeblack", 0.35),
    "cross_dissolve": ("fade", 0.30),  # 真·叠化 (2026-08-14 补, 供转场分类法消费)
    "flash":  ("fadewhite", 0.12),
    "zoom":   ("smoothup",  0.30),
    "slide":  ("slideleft", 0.30),
    "glitch": ("pixelize",  0.20),
    # v21b 转场库扩展 (Phase C, ffmpeg xfade 内置滤镜, 无需额外依赖)
    "wipe":   ("wipeleft",  0.25),
    "circle": ("circleopen", 0.30),
    "radial": ("radial",    0.30),
    "hblur":  ("hblur",     0.25),
    "diagtl": ("diagtl",    0.25),
    "vertopen": ("vertopen", 0.25),
    "squeezech": ("squeezeh", 0.25),
}

# 单条 xfade 链最大段数（滤镜图过长易崩，超出分组后组间硬切——符合段落边界硬切惯例）
XFADE_GROUP_SIZE = 8


# ================================================================
#  生产级导演系统
# ================================================================

class ProductionDirector:
    """生产级导演系统 — 端到端视频生产"""

    def __init__(
        self,
        ffmpeg_path: str = None,
        ffprobe_path: str = None,
        work_dir: Optional[str] = None,
        taste_profile: Optional[dict] = None,
    ):
        # ffmpeg/ffprobe 默认路径收口到 core/paths.py（AEK_FFMPEG / AEK_FFPROBE 可覆盖）
        try:
            from core.paths import ffmpeg_bin, ffprobe_bin
            self.ffmpeg = ffmpeg_path or ffmpeg_bin()
            self.ffprobe = ffprobe_path or ffprobe_bin()
        except ImportError:
            self.ffmpeg = ffmpeg_path or r"C:\ffmpeg\bin\ffmpeg.exe"
            self.ffprobe = ffprobe_path or r"C:\ffmpeg\bin\ffprobe.exe"
        self.work_dir = Path(work_dir or str(_PROJECT_ROOT / "tmp" / "director_work"))

        # T4: 品味契约接入
        from ai.taste_contract import TasteProfile, DEFAULT_TASTE
        self.taste: TasteProfile = (
            TasteProfile.from_dict(taste_profile) if taste_profile else DEFAULT_TASTE
        )

        # 核心模块
        self.beat_detector = BeatDetector()
        self.emotion_generator = EmotionCurveGenerator()
        self.visual_analyzer = VisualContentAnalyzer(sample_fps=1.0, max_samples=50)
        self.text_engine = TextAnimationEngine()
        self.intel_engine = MaterialIntelligenceEngine(frame_sample_count=3)
        self.temporal_analyzer = TemporalAnalyzer(sample_fps=5.0)
        self.av_correlator = AudioVisualCorrelator(tolerance_ms=100)

        # 分析缓存
        self._beats: List[BeatInfo] = []
        self._emotion_curve: Optional[EmotionCurve] = None
        self._material_tags: Dict[str, MaterialTag] = {}
        self._intel_tags: Dict[str, MaterialIntelTag] = {}
        self._material_index: Optional[MaterialIndex] = None
        self._source_durations: Dict[str, float] = {}
        # 生产级素材选择结果
        self._selection: Dict[str, List[str]] = {}
        self._selected_sources: List[str] = []

        # 本地训练模型中枢（懒加载，权重缺失/推理失败自动降级，不中断渲染）
        from ai.local_model_hub import get_hub
        self.model_hub = get_hub()
        self._scene_model_tags: Dict[str, Dict] = {}   # 素材场景模型预测证据
        self._rhythm_selection: Dict[str, Any] = {}    # 节奏奖励择优证据
        self._used_windows: Dict[str, List[float]] = {}  # 素材已用窗口记录(防重复)
        self._highlight_pool: Optional[Dict[str, List[Tuple[float, float]]]] = None  # 高光段池懒加载
        self._semantic_windows: Optional[Dict[str, List[Tuple[float, str]]]] = None  # 语义窗口池懒加载(Stage2)
        self._beat_class = None       # v22 节拍强弱分级结果 (懒加载)
        self._dyn = None              # v22 音乐动态分析器 (懒加载)
        self._preset_sys = None       # v22 风格预设 (choose_camera 运镜池)
        self._arc_levels = {}         # arc_segment start → music_dynamics level (high/mid/low)
        self._beatgrid = None         # OpenMontage audiomap 鼓类型/网格语义 (懒加载)
        self._beatnet_fusion = None   # BeatNet 三层信号融合结果 (use_beatnet=True 时)
        self._last_flash_sec = -999.0  # 闪白间距门控 (2026-08-14: flash ≥20s 间隔)
        self._last_punch_sec = -999.0  # 拉进-闪回撞击间距门控 (2026-08-15: 全片≤6次, 间隔≥20s)
        self._punch_budget = 6          # 撞击运镜总预算 (v22 全片 pulse 仅 2 次 → 稀缺强调)
        self._shot_plan = None          # LLM 镜头设计计划 (ai/shot_design_llm.py, 2026-08-15)
        self._arc_shot_plan: Dict[float, dict] = {}  # 弧段start(round3) → 计划弧段
        self._punch_points: List[float] = []         # LLM 指定撞击点 (绝对秒)
        self._source_use_count: Dict[str, int] = {}  # 素材使用计数 (2026-08-15 防重复:
        #                                              v6 独自升级5 独占101镜 → 均衡轮转)
        self._motion_profiles: Dict[str, MotionProfile] = {}   # 素材运动画像
        self._shot_structures: Dict[str, ShotStructure] = {}   # 素材镜头结构

        # P0: SSIM自适应抽帧器懒加载 (素材预处理标准接口)
        self._frame_extractor = None

    @property
    def frame_extractor(self):
        """P0: SSIM自适应抽帧器 (懒加载, 磁盘缓存 cache/frame_extract/)

        标准接口: extract()/extract_frames()/indices_within()
        动漫一拍二/三重复帧自动去除; 同一素材多次调用命中缓存零重解。
        可注入 HighlightScorer(frame_extractor=...) 使评分采样同源去重。
        """
        if self._frame_extractor is None:
            from core.frame_extractor import FrameExtractor
            self._frame_extractor = FrameExtractor()
        return self._frame_extractor

    # ================================================================
    #  公开 API
    # ================================================================

    def render(
        self,
        video_sources: List[str],
        bgm_path: str,
        output_dir: str,
        output_name: str = "director_output.mp4",
        lyrics: Optional[List[Tuple]] = None,
        bgm_start_sec: float = 0.0,
        target_duration: Optional[float] = None,
        resolution: Tuple[int, int] = (1920, 1080),
        fps: int = 24,
        target_ip: str = "",
        strict: bool = True,
        allow_mixed: bool = False,
        verify_content: bool = True,
        use_speed_ramp: bool = False,
        style_spec: Optional[dict] = None,
        style_id: Optional[str] = None,
        use_beatnet: bool = False,
        bpm_override: Optional[float] = None,
        theme: Optional[str] = None,
        enable_ae_channel: bool = False,
    ) -> str:
        """端到端渲染。

        Args:
            theme: 主题/叙事描述 (如 "进击的巨人对抗巨兽的燃向混剪")。
                   传入时 _plan 调用 multimodal_director.direct_from_text 生成
                   分镜(structure: 段落/情绪/镜头意图), 给每段加"叙事角色",
                   素材按叙事角色匹配(解决"镜头杂乱无章"——v23 此前纯按节拍分段)。
                   不传则保持纯节拍驱动(无故事层)。
            style_id: 风格卡 ID (data/style_cards/*.json, 如 "amv_highenergy")。
                      非空时从知识卡推导 taste_profile 与 style_spec
                      (卡片此前仅被测试消费, 2026-08-14 接线到生产管线)。
            use_beatnet: True 时用 BeatNetLite 对 BGM 做节拍/下拍/拍号三层
                      信号分析并与项目 beatgrid 调和 (结果写入报告
                      metadata.beatnet_fusion, 只增补标注不改切点)。

        Args:
            target_ip: 目标IP/作品名 (如 "进击的巨人")。
                       非空时只使用匹配该IP的素材，杜绝无关素材混入。
            strict: 严格模式。target_ip非空且无匹配素材时直接报错，
                    绝不隐式降级到"用全部素材"。默认True(生产模式)。
            allow_mixed: 是否允许使用多IP混剪类素材。默认False。
            verify_content: 渲染完成后是否用VLM复核成片内容确为目标IP。默认True。
            use_speed_ramp: 启用情绪驱动变速（SPEED_PRESETS）。默认False保持基线行为。
        """
        t0 = time.time()

        # 风格卡 → 导演输入 (品味契约 + 风格规格书)
        if style_id:
            try:
                from knowledge.style_card import card_to_director_inputs
                _card_inputs = card_to_director_inputs(style_id)
                if _card_inputs:
                    _tp = _card_inputs.get("taste_profile")
                    if _tp:
                        from ai.taste_contract import TasteProfile
                        self.taste = TasteProfile.from_dict(_tp)
                    if style_spec is None:
                        style_spec = _card_inputs.get("style_spec")
                    print(f"  [style] 风格卡 '{style_id}' 已加载 → 品味契约 + 风格规格书")
            except Exception as _e:  # noqa: BLE001
                print(f"  [style] 风格卡加载失败({_e}), 继续使用显式参数")

        # 风格卡/规格书中的运镜禁忌 → T4 池过滤
        self._forbidden_cameras: List[str] = []
        if style_spec and style_spec.get("camera_preferences"):
            _forbid = style_spec["camera_preferences"].get("forbidden") or []
            self._forbidden_cameras = [str(c) for c in _forbid]

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_name
        self._output_dir = output_dir  # 供 AE 通道等使用

        self.work_dir.mkdir(parents=True, exist_ok=True)

        print("=" * 60)
        print("ProductionDirector — 端到端渲染")
        print("=" * 60)

        # LUT 调色路径：暂时禁用（LUT生成算法待修复），使用eq=saturation直接处理
        self._lut_path = None
        self._render_fps = int(fps)  # 供 _plan 帧网格吸附用
        # if style_spec and style_spec.get("color"):
        #     _sat_boost = float(style_spec["color"].get("saturation_boost", 1.0))
        #     if _sat_boost > 1.0:
        #         _lut_dir = _PROJECT_ROOT / "config"
        #         _lut_level = "1.5" if _sat_boost <= 1.2 else "1.8" if _sat_boost <= 1.5 else "2.0" if _sat_boost <= 2.2 else "2.5"
        #         _lut_file = _lut_dir / f"saturation_boost_{_lut_level}x.cube"
        #         if _lut_file.exists():
        #             self._lut_path = str(_lut_file)
        #             print(f"  [LUT] 饱和度增益 {_sat_boost}x → 使用 {_lut_level}x LUT")

        try:
            # Phase 1: 感知分析
            print("\n[Phase 1] 感知分析...")
            self._analyze(bgm_path, video_sources, bgm_start_sec, target_duration,
                          target_ip, strict, allow_mixed, bpm_override=bpm_override,
                          use_beatnet=use_beatnet, theme=theme)

            # Phase 2: 剧本编排
            print("\n[Phase 2] 剧本编排...")
            # 修复: actual_duration 必须钳制到 BGM 实际时长(_emotion_curve.duration)。
            # 此前取 target_duration 原值, 当 BGM 比目标短时, 叙事弧/切点规划在
            # "不存在的时长"上, 后半段切点全错位 (v23 实测: 40s 计划 vs 19.38s 成片,
            # 这是"观感不卡点"的真正根因)
            actual_duration = min(target_duration, self._emotion_curve.duration) \
                if target_duration else \
                self._music_effective_end(bgm_path, self._emotion_curve.duration)
            script = self._plan(video_sources, bgm_path, bgm_start_sec,
                                actual_duration, lyrics, target_ip,
                                style_spec=style_spec,
                                use_speed_ramp=use_speed_ramp,
                                theme=theme)

            # P2: 剧本YAML化 + 决策日志 (与渲染同步输出, 失败不阻断渲染)
            try:
                script.metadata.setdefault("version", "director_script_v1")
                script.save_yaml(output_dir / "director_script.yaml")
                export_decision_log(script, output_dir / "decision_log.yaml",
                                    rationale=script.metadata.get("decision_rationale"))
                export_decision_log(script, output_dir / "decision_log.md",
                                    rationale=script.metadata.get("decision_rationale"))
                print("  [P2] director_script.yaml + decision_log 已输出")
            except Exception as _e:
                print(f"  [WARN] 剧本YAML/决策日志输出失败(不阻断): {_e}")

            # P0-2026-08-16 阶段自评 (TEMPO 式): 剧本编排完成 → critic 估计价值
            try:
                self._critique_stage(
                    stage="2_scripting",
                    stage_summary=(f"剧本 {len(script.segments)} 段 / "
                                   f"{script.total_duration:.1f}s / "
                                   f"镜头节奏 {script.metadata.get('rhythm_pattern', 'n/a')}"),
                    decisions=str(script.metadata.get("decision_rationale", ""))[:400],
                    goal=f"{target_ip or '自由混剪'} {actual_duration:.0f}s",
                )
            except Exception:
                pass

        # Phase 3: 渲染执行
            print("\n[Phase 3] 渲染执行...")
            # 磁盘守卫 (2026-08-16): C盘满(No space left)曾击穿渲染,
            # 渲染前清理历史 run 目录并校验剩余空间
            try:
                _dw = Path(self.work_dir)
                if _dw.exists():
                    import shutil as _sh
                    for _old in _dw.glob("run_*"):
                        if _old.is_dir():
                            _sh.rmtree(_old, ignore_errors=True)
                _free = _sh.disk_usage(_dw if _dw.exists() else Path.cwd()).free
                if _free < 6 * 1024 ** 3:
                    raise RuntimeError(
                        f"磁盘剩余空间不足 6GB ({_free / 1024**3:.1f}GB), "
                        "请清理磁盘后重试")
                print(f"  [磁盘] 剩余 {_free / 1024**3:.1f}GB, 历史run目录已清理")
            except RuntimeError:
                raise
            except Exception as _disk_e:  # noqa: BLE001
                print(f"  [磁盘] 守卫跳过({_disk_e})")
            temp_video = self._execute(script, resolution, fps,
                                       enable_ae_channel=enable_ae_channel)

            # 3.5 时长守卫 (2026-08-16): 帧量化后的最后防线 — 实测成片与
            # 剧本时长差 >0.15s 时重编码裁齐, 杜绝"多出几秒"类交付缺陷
            try:
                _vdur = self._probe_duration(temp_video)
                if abs(_vdur - actual_duration) > 0.15:
                    _trimmed = Path(temp_video).with_name("trimmed_final.mp4")
                    _tr = subprocess.run(
                        [self.ffmpeg, "-y", "-i", temp_video,
                         "-t", f"{actual_duration:.4f}",
                         "-c:v", "libx264", "-preset", "fast",
                         "-b:v", "50M", "-maxrate", "60M", "-bufsize", "100M",
                         "-pix_fmt", "yuv420p", "-an",
                         "-movflags", "+faststart", str(_trimmed)],
                        capture_output=True, text=True, timeout=1800)
                    if _tr.returncode == 0 and _trimmed.exists():
                        print(f"  [时长守卫] {_vdur:.2f}s → 裁齐 "
                              f"{actual_duration:.2f}s")
                        temp_video = str(_trimmed)
                    else:
                        print(f"  [时长守卫] 裁剪失败, 保持原片({_vdur:.2f}s)")
            except Exception as _guard_e:  # noqa: BLE001
                print(f"  [时长守卫] 跳过({_guard_e})")

            # Phase 4: 文字叠加
            if any(seg.text_overlay for seg in script.segments):
                print("\n[Phase 4] 文字叠加...")
                text_video = self._overlay_text(temp_video, script)
            else:
                text_video = temp_video

            # Phase 5: BGM 混音
            print("\n[Phase 5] BGM 混音...")
            self._mix_audio(text_video, bgm_path, str(output_path),
                            bgm_start_sec, script.total_duration)

            # Phase 6: 质量验证
            print("\n[Phase 6] 质量验证...")
            result = self._validate(str(output_path))

            # Phase 7: 成片内容复核 (生产交付的最后防线)
            if result.success and target_ip and verify_content:
                print("\n[Phase 7] 成片内容复核...")
                verification = self.intel_engine.verify_video_ip(
                    str(output_path), target_ip, frame_count=4)
                result.content_verified = verification["verified"]
                result.verification_reason = verification["reason"]
                print(f"      复核结果: {'✅ 通过' if verification['verified'] else '❌ 不通过'}")
                print(f"      依据: {verification['reason']}")
                if verification["detected_ips"]:
                    print(f"      检测到: {verification['detected_ips']}")
                if strict and not verification["verified"]:
                    self._save_production_report(output_dir, script, target_ip, result)
                    raise RuntimeError(
                        f"成片内容复核未通过: 输出未确认为《{target_ip}》内容。"
                        f"依据: {verification['reason']} 输出保留于 {output_path} 供人工审查")

            # 保存生产审计报告
            self._save_production_report(output_dir, script, target_ip, result)

            # P0-2026-08-16 阶段自评 (TEMPO 式): 渲染完成 → critic 估计最终质量
            try:
                self._critique_stage(
                    stage="6_rendered",
                    stage_summary=(f"成片 {result.duration:.1f}s / "
                                   f"{result.file_size_mb:.1f}MB / "
                                   f"{result.resolution[0]}x{result.resolution[1]} "
                                   f"success={result.success}"),
                    decisions=(f"复核={'通过' if result.content_verified else '未复核/不通过'}"
                               if result.content_verified is not None else "未启用复核"),
                    goal=f"{target_ip or '自由混剪'} {actual_duration:.0f}s",
                )
            except Exception:
                pass

            # Phase 8: 叙事语义复核 (Stage3 — 逐镜头"画面是否表达叙事意图")
            # 可量化验收: 对每个叙事角色段的中点抽帧, Qwen3-VL 分析画面情绪,
            # 与叙事角色预期情绪比对, 输出一致性得分 + 写入 decision_log 依据。
            if result.success:
                try:
                    self._verify_narrative_semantics(
                        str(output_path), script, output_dir)
                except Exception as _e:
                    print(f"  [WARN] 叙事语义复核失败(不阻断): {_e}")

            elapsed = time.time() - t0
            print(f"\n{'=' * 60}")
            if result.success:
                print(f"渲染成功!")
                print(f"输出: {output_path}")
                print(f"大小: {result.file_size_mb:.2f} MB")
                print(f"时长: {result.duration:.2f}s")
                print(f"分辨率: {result.resolution[0]}x{result.resolution[1]}")
                print(f"帧率: {result.fps}fps")
                print(f"音频: {'有' if result.has_audio else '无'}")
                if result.content_verified is not None:
                    print(f"内容复核: {'✅ 通过' if result.content_verified else '❌ 不通过'}")
            else:
                print(f"渲染异常: {result.error_message}")
            print(f"总耗时: {elapsed:.1f}s")
            print(f"{'=' * 60}")

            # ── 自进化自动采集: 渲染成功后异步写入 ExecutionRecord ──
            if result.success:
                content = self._collect_content_metrics(script)
                self._trigger_auto_evolution(
                    output_path=str(output_path),
                    result=result,
                    elapsed=elapsed,
                    target_ip=target_ip,
                    video_sources=video_sources,
                    bgm_path=bgm_path,
                    content=content,
                )

            # ── 后处理引导 (P1): 渲染成功后提示超分/补帧入口, 非阻塞, 默认关 ──
            # 由 tmp/render_v22.py 双通道沉淀进主引擎。enabled=false 时仅打印提示。
            if result.success:
                try:
                    from core.post_enhancer import PostEnhancer
                    PostEnhancer().report_after_render(str(output_path))
                except Exception as _e:
                    print(f"  [WARN] 后处理引导加载失败(不阻断): {_e}")

            # ── 渲染产物生命周期管理 (2026-08-15): 渲染完成后自动清理旧中间产物 ──
            # 三层保留: 文档归档 / 最后版本保活 / 高完成度成品保留;
            # 活跃目录(含本次输出)自动跳过; 节流 1h; 任何异常不阻断渲染。
            try:
                from core.render_cleanup import auto_cleanup_quiet
                _cl = auto_cleanup_quiet()
                if _cl and not _cl.get("skipped"):
                    print(f"  [清理] 释放 {_cl['freed_gb']:.2f}GB, "
                          f"归档文档 {_cl['archived_docs']} 个, "
                          f"保留成品 {_cl['kept_finals']} 个")
            except Exception:
                pass

            return str(output_path)

        except Exception as e:
            elapsed = time.time() - t0
            print(f"\n[ERROR] 渲染失败 ({elapsed:.1f}s): {e}")
            import traceback
            traceback.print_exc()
            raise

    # ================================================================
    #  自进化自动采集钩子
    # ================================================================

    def _collect_content_metrics(self, script) -> dict:
        """从本次运行 script + _beats + _used_windows 组装内容级指标。

        供自进化引擎真实评分(style_consistency 维度)。
        返回的 dict 会随 ExecutionRecord 提交给 AutoQualityEvaluator。
        """
        segments = getattr(script, "segments", []) or []
        # 素材窗口: _used_windows 为 {src: [窗口,...]}, 每个窗口兼容两种格式:
        #   (s, e) 对 → (src, start, end)
        #   标量 start → (src, start, 0.0) (旧调用方)
        windows = []
        for src, starts in (getattr(self, "_used_windows", {}) or {}).items():
            for s in (starts or []):
                if isinstance(s, (list, tuple)) and len(s) >= 2:
                    windows.append((src, float(s[0]), float(s[1])))
                else:
                    windows.append((src, float(s), 0.0))
        return {
            "beat_times": [
                b.time for b in (getattr(self, "_beats", None) or [])
            ],
            "cut_times": [
                seg.start_time for seg in segments
                if getattr(seg, "start_time", None) is not None
            ],
            "camera_moves": [
                seg.zoompan_effect for seg in segments
                if getattr(seg, "zoompan_effect", None)
            ],
            "material_windows": windows,
            "energy_series": [
                seg.energy for seg in segments
                if getattr(seg, "energy", None) is not None
            ],
        }

    def _verify_narrative_semantics(self, output_path: str, script,
                                    output_dir) -> None:
        """Phase 8: 叙事语义复核 (Stage3) — 画面 scene_type vs 叙事角色预期一致性

        可量化验收: 对每个镜头(抽关键帧)用 Qwen3-VL 分析画面 scene_type,
        与叙事角色预期 scene 比对, 输出一致性得分 + 逐镜头依据。
        这是"镜头表达意图"的可检测证据。

        修复(2026-08-13): 之前用 mood(情绪)比对, 但选材用 scene_type,
        两套标准不匹配 → 一致性数字失真(38%不代表选材质量)。
        改为与 _pick_by_narrative_role 的 _role_scene 完全对齐:
          铺垫 → landscape/closeup/indoor/dialogue
          蓄力 → action/closeup/landscape
          爆发 → battle/fighting
          收尾 → landscape/closeup/dialogue/indoor
        """
        import json as _json
        try:
            from ai.material_intelligence import MaterialIntelligenceEngine
            _eng = MaterialIntelligenceEngine()
            _eng._env = None
        except Exception:
            return

        # 与 _pick_by_narrative_role 完全一致的 scene_type 期望
        _role_scene = {
            "铺垫": ("landscape", "closeup", "indoor", "dialogue"),
            "蓄力": ("action", "closeup", "landscape"),
            "爆发": ("battle", "fighting"),
            "收尾": ("landscape", "closeup", "dialogue", "indoor"),
        }
        segs = getattr(script, "segments", []) or []
        if not segs:
            return

        # 抽关键帧: 每个镜头中点 (限前 12 镜控制成本, 覆盖全部叙事角色)
        import cv2
        _cv2 = cv2
        _cap = _cv2.VideoCapture(output_path)
        if not _cap.isOpened():
            _cap.release()
            return
        _fps = _cap.get(_cv2.CAP_PROP_FPS) or 24.0

        results = []
        # 修复(2026-08-13): 之前 segs[:18] 只采开头(铺垫/蓄力), 爆发段在末尾采不到,
        # 且 _seen_roles 每角色只采1镜 → 实测只采2镜(铺垫/蓄力), 缺爆发/收尾。
        # 改为: 每个角色均匀采最多3镜, 覆盖全片时间轴。
        from collections import defaultdict as _dd
        _role_count = _dd(int)
        _role_max = 3
        for _s in segs:
            # 镜头 start_time → 最近弧段角色
            _role = ""
            if self._narrative_roles:
                _arc_starts = sorted(self._narrative_roles.keys())
                import bisect as _bisect
                _i = _bisect.bisect_right(_arc_starts, _s.start_time) - 1
                if _i >= 0:
                    _role = self._narrative_roles[_arc_starts[_i]]
                elif _arc_starts:
                    _role = self._narrative_roles[_arc_starts[0]]
            if not _role:
                continue
            if _role_count[_role] >= _role_max:
                continue
            _role_count[_role] += 1
            _mid = _s.start_time + _s.duration / 2
            _cap.set(_cv2.CAP_PROP_POS_MSEC, _mid * 1000)
            _ret, _fr = _cap.read()
            if not _ret:
                continue
            _h, _w = _fr.shape[:2]
            _scale = min(640 / max(_h, _w), 1.0)
            if _scale < 1.0:
                _fr = _cv2.resize(_fr, (int(_w * _scale), int(_h * _scale)))
            _ok, _buf = _cv2.imencode(".jpg", _fr,
                                      [_cv2.IMWRITE_JPEG_QUALITY, 80])
            if not _ok:
                continue
            import base64
            _b64 = base64.b64encode(_buf.tobytes()).decode()
            try:
                _res, _model = _eng._vlm_analyze([_b64], output_path)
                _shot_mood = str(_res.get("mood", "neutral"))
                _scene = str(_res.get("scene_type", "unknown"))
            except Exception:
                _shot_mood, _scene = "neutral", "unknown"
            # 与选材标准对齐: 用 scene_type 比对 (拆复合值 battle/action)
            _expect = _role_scene.get(_role, ())
            _scene_parts = [p.strip() for p in _scene.lower().split("/")]
            _match = any(_e in _scene_parts for _e in _expect) if _expect else False
            results.append({
                "index": _s.index,
                "time": round(_mid, 2),
                "role": _role,
                "expected_scene": list(_expect),
                "shot_mood": _shot_mood,
                "scene": _scene,
                "match": _match,
                "model": _model,
            })
        _cap.release()

        if results:
            _n = len(results)
            _n_match = sum(1 for r in results if r["match"])
            _score = _n_match / _n
            print(f"\n[Phase 8] 叙事语义复核: {_n_match}/{_n} 镜头 "
                  f"场景匹配叙事角色 (一致性 {_score:.0%})")
            for r in results:
                print(f"    [{r['role']:4s}] {r['time']:5.1f}s "
                      f"期望scene{r['expected_scene'][:2]} 实测[{r['scene']}] "
                      f"{'✅' if r['match'] else '❌'}")
            # 写盘供验收
            _out = Path(output_dir) / "narrative_verification.json"
            _out.write_text(_json.dumps(
                {"consistency": _score, "n_matched": _n_match, "n_total": _n,
                 "results": results}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            print(f"  叙事验证报告: {_out}")
            # 写入 script.metadata 供 decision_log 关联
            if not hasattr(script, "metadata"):
                script.metadata = {}
            script.metadata["narrative_verification"] = {
                "consistency": _score, "n_matched": _n_match, "n_total": _n}

    def _trigger_auto_evolution(
        self, output_path, result, elapsed, target_ip, video_sources, bgm_path,
        content=None,
    ):
        """渲染成功后异步提交 ExecutionRecord 到自进化引擎。

        设计原则:
        - 绝不阻塞主管线 return（后台线程 + 10s 超时）
        - 失败只打 warning，不 raise
        - 数据尽量丰富，供自进化引擎蒸馏经验
        """
        import threading

        def _submit():
            try:
                from datetime import datetime
                from core.self_evolution_engine import (
                    get_evolution_engine, ExecutionRecord,
                )
                import asyncio

                engine = get_evolution_engine()
                record = ExecutionRecord(
                    run_id=f"director_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=time.time(),
                    stages={
                        "source": "production_director",
                        "target_ip": target_ip,
                        "video_sources": video_sources,
                        "bgm_path": bgm_path,
                        "content_verified": result.content_verified,
                        "content": content or {},
                    },
                    input_spec={
                        "resolution": list(result.resolution),
                        "fps": result.fps,
                        "has_audio": result.has_audio,
                    },
                    config={
                        "auto_captured": True,
                        "output_path": output_path,
                    },
                    output_path=output_path,
                    output_quality=0.0,  # 由 engine 自动评估
                    success=result.success,
                    total_duration=result.duration,
                    strategy_id="production_director",
                )

                loop = asyncio.new_event_loop()
                try:
                    review = loop.run_until_complete(
                        engine.post_execution_review(record)
                    )
                    print(
                        f"[自进化] 自动采集完成: "
                        f"quality={review.quality.overall_score:.1f}, "
                        f"deviation={review.prediction_deviation:.3f}"
                    )
                    # D2 修复: 导演真实参数反馈写入
                    try:
                        from ai.director_feedback_hook import record_director_feedback
                        from datetime import datetime as _dt
                        record_director_feedback({
                            "run_id": f"director_{_dt.now().strftime('%Y%m%d_%H%M%S')}",
                            "quality": review.quality.overall_score,
                            "ramps": [],  # TODO: 从 script.segments 提取 speed/zoompan 参数
                            "style": target_ip,
                        })
                    except Exception as fb_err:
                        print(f"[反馈] 导演参数反馈写入失败(不影响渲染): {fb_err}")
                finally:
                    loop.close()

            except Exception as e:
                print(f"[自进化] 自动采集失败 (不影响渲染结果): {e}")

        t = threading.Thread(target=_submit, daemon=True, name="auto-evolution")
        t.start()
        t.join(timeout=10)  # 最多等 10s，超时不阻塞

    # ================================================================
    #  Phase 1: 感知分析
    # ================================================================

    def _analyze(self, bgm_path, video_sources, bgm_start_sec, target_duration,
                 target_ip="", strict=True, allow_mixed=False, bpm_override=None,
                 use_beatnet: bool = False, theme: Optional[str] = None):
        """执行感知分析 — 包含素材IP智能识别与严格素材选择"""

        # 1.1 节拍检测
        print("  [1.1] 节拍检测...")
        self._beats = self.beat_detector.detect_beats(bgm_path)
        bpm, conf = self.beat_detector.detect_bpm(bgm_path)

        # 1.1b BeatNet 三层信号融合 (可选): 节拍+下拍+拍号交叉验证
        self._beatnet_fusion = None
        if use_beatnet:
            try:
                from models.beat.beatnet_adapter import get_beatnet
                from models.beat.rhythm_fusion import fuse_beatgrids
                _bn = get_beatnet()
                if _bn.available():
                    _grid = _bn.analyze(bgm_path)
                    if _grid:
                        self._beatnet_fusion = fuse_beatgrids(
                            [b.time for b in self._beats], _grid)
                        _f = self._beatnet_fusion
                        print(f"  [1.1b] BeatNet: tempo {_f.tempo_beatnet} vs "
                              f"{_f.tempo_project} BPM "
                              f"({'一致' if _f.tempo_consistent else '不一致'}), "
                              f"对齐率 {_f.alignment_rate:.0%}, "
                              f"下拍 {len(_f.downbeat_times)}")
                    else:
                        print("  [1.1b] BeatNet: 分析失败, 跳过")
            except Exception as _e:  # noqa: BLE001
                print(f"  [1.1b] BeatNet: 跳过({_e})")
        
        # BPM 覆盖：使用 StyleSpec 的 BPM 生成合成节拍网格
        if bpm_override and abs(bpm_override - bpm) > 1.0:
            # 获取 BGM 时长
            import subprocess, json as _json
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", bgm_path],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            bgm_dur = float(_json.loads(probe.stdout).get("format", {}).get("duration", 20.0))
            # 生成合成节拍网格（BeatInfo 对象）
            from ae.beat_detector import BeatInfo
            beat_interval = 60.0 / bpm_override
            n_beats = int(bgm_dur / beat_interval)
            self._beats = [
                BeatInfo(
                    time=i * beat_interval,
                    beat_index=i + 1,
                    bar=(i // 4) + 1,
                    beat_in_bar=(i % 4) + 1,
                    strength=1.0 if (i % 4) == 0 else 0.7,
                    is_downbeat=(i % 4) == 0,
                )
                for i in range(n_beats)
            ]
            print(f"      BPM={bpm}->{bpm_override}(override), 置信度={conf}, "
                  f"合成节拍数={len(self._beats)} (间隔{beat_interval:.3f}s)")
            bpm = bpm_override
        else:
            print(f"      BPM={bpm}, 置信度={conf}, 节拍数={len(self._beats)}")

        # 1.1b Onset 检测（能量突增点，驱动镜头内脉冲运镜）
        self._onsets = self._detect_onsets(bgm_path)
        print(f"  [1.1b] Onset检测: {len(self._onsets)} 个能量突增点")
        # 1.1c 鼓类型/网格语义骨架 (OpenMontage beatgrid, kick优先锚定)
        self._beatgrid = self._load_beatgrid(bgm_path)
        if self._beatgrid:
            print(f"  [1.1c] beatgrid: kick={len(self._beatgrid['kick'])} "
                  f"strong={len(self._beatgrid['strong'])} "
                  f"weak={len(self._beatgrid['weak'])} (撞拍锚定)")

        # 1.2 情绪曲线
        print("  [1.2] 情绪曲线...")
        self._emotion_curve = self.emotion_generator.generate(
            bgm_path, target_duration=target_duration, start_time=bgm_start_sec,
        )
        print(f"      段落数: {len(self._emotion_curve.segments)}, "
              f"平均情绪: {self._emotion_curve.avg_emotion:.3f}, "
              f"时长: {self._emotion_curve.duration:.1f}s")

        # 1.3 素材智能识别 (VLM + CV 双通道)
        print("  [1.3] 素材智能识别...")
        if target_ip:
            print(f"      目标IP: {target_ip}")
        intel_index = MaterialIndex()
        for src in video_sources:
            p = Path(src)
            if not p.exists():
                print(f"      [WARN] 素材不存在: {src}")
                continue
            # 时长
            dur = self._probe_duration(src)
            self._source_durations[src] = dur
            # 智能识别
            try:
                itag = self.intel_engine.analyze_video(src)
                # 本地场景分类器(scene_classifier_v1.pt): 充实 scene_type
                # unknown时用模型预测回填；已有VLM结果时仅记录模型证据供对比
                if self.model_hub.scene_classifier_available():
                    spred = self.model_hub.classify_video_scene(src)
                    if spred:
                        self._scene_model_tags[src] = spred
                        if itag.content.scene_type in ("", "unknown"):
                            itag.content.scene_type = spred["content_scene"]
                            print(f"      {p.name}: 场景模型修正 → {spred['scene']}"
                                  f"(置信{spred['confidence']:.0%})")
                        else:
                            print(f"      {p.name}: 场景模型预测={spred['scene']}"
                                  f"(置信{spred['confidence']:.0%}, 保留VLM={itag.content.scene_type})")
                self._intel_tags[src] = itag
                intel_index.add(itag)
                print(f"      {p.name}: {dur:.1f}s, "
                      f"IP={itag.primary_ip or '未识别'}"
                      f"{'(混剪)' if itag.is_mixed else ''}, "
                      f"类型={itag.content_kind}, 场景={itag.content.scene_type}")
            except Exception as e:
                print(f"      {p.name}: {dur:.1f}s (识别失败: {e})")

        self._material_index = intel_index

        # 1.3b 时间维度分析（运动画像+镜头结构）
        # 结果仅用于可观测性日志(不参与下游编排), 但 4K 素材 farneback 密集
        # 光流极慢(单素材 30-90s, 7素材≈5-10分钟)且每次渲染重跑。
        # 双层缓存:
        #   L1 整文件缓存 (path, mtime, size) — 未变素材命中 <1ms
        #   L2 分段缓存 (内容块指纹, core/temporal_segment_cache) — 素材被裁切后
        #      未受影响时间段的块仍复用, 仅与裁切点相交的块重算
        print("  [1.3b] 时间维度分析...")
        _temporal_cache_dir = os.path.join(
            str(_PROJECT_ROOT), "cache", "temporal_analysis")
        for src in list(self._source_durations.keys()):
            p = Path(src)
            if not p.exists():
                continue
            try:
                _st = p.stat()
                _tkey = hashlib.md5(
                    (str(src) + "|" + str(int(_st.st_mtime)) + "|" + str(_st.st_size))
                    .encode()).hexdigest()[:12]
                _tcache = os.path.join(_temporal_cache_dir, f"{_tkey}.pkl")
                if os.path.exists(_tcache):
                    with open(_tcache, "rb") as _f:
                        _mp, _ss = pickle.load(_f)
                else:
                    # L1 miss → L2 分段缓存 (裁切素材复用未变块, 冷启动与整文件等价)
                    try:
                        from core.temporal_segment_cache import analyze_cached
                        _mp, _ss = analyze_cached(self.temporal_analyzer, src)
                    except Exception as _seg_e:
                        print(f"        [WARN] 分段缓存降级整文件分析: {_seg_e}")
                        _mp = self.temporal_analyzer.analyze_motion(src)
                        _ss = self.temporal_analyzer.detect_shot_structure(src)
                    try:
                        os.makedirs(_temporal_cache_dir, exist_ok=True)
                        with open(_tcache, "wb") as _f:
                            pickle.dump((_mp, _ss), _f)
                    except OSError:
                        pass
                self._motion_profiles[src] = _mp
                self._shot_structures[src] = _ss
                print(f"      {p.name}: 运镜={_mp.dominant_motion.value}, "
                      f"运动={_mp.avg_magnitude:.2f}, 抖动={_mp.shake_score:.2f}, "
                      f"镜头={_ss.total_shots}, ASL={_ss.asl:.1f}s, "
                      f"节奏={_ss.rhythm_pattern}")
            except Exception as e:
                print(f"      {p.name}: 时间分析跳过 ({e})")

        # 1.4 生产级素材选择 — 严格模式绝不隐式降级
        self._selection = {"matched": [], "mixed": [], "unknown": [], "excluded": []}
        self._selected_sources = list(self._source_durations.keys())
        if target_ip and self._intel_tags:
            selection = intel_index.select_for_ip(
                target_ip, allow_mixed=allow_mixed)
            self._selection = selection
            matched = selection["matched"]
            # 1.4d 画像过滤 (2026-08-14): IP 匹配模式同样排除教程录屏
            # (content=not_painting 进 excluded 桶, 与自由混剪模式 1.4b 对齐)
            try:
                _profile = self._load_atmosphere_annotations()
                _tutorial = [
                    m for m in matched
                    if (_profile.get(Path(m).name) or {}).get("content")
                    == "not_painting"
                ]
                if _tutorial:
                    matched = [m for m in matched if m not in _tutorial]
                    selection["matched"] = matched
                    selection.setdefault("excluded", []).extend(_tutorial)
                    print(f"  [1.4d] 画像过滤: 匹配集中 {len(_tutorial)} "
                          f"个教程录屏移入 excluded")
            except Exception:  # noqa: BLE001
                pass
            print(f"  [1.4] 素材选择 '{target_ip}': "
                  f"匹配 {len(matched)}, 混剪排除 {len(selection['mixed'])}, "
                  f"未识别排除 {len(selection['unknown'])}, "
                  f"其他IP/教程排除 {len(selection['excluded'])}")
            for m in matched:
                print(f"      ✅ {Path(m).name}")
            for m in selection["mixed"] + selection["unknown"] + selection["excluded"]:
                print(f"      ❌ {Path(m).name}")
            if not matched:
                if strict:
                    raise RuntimeError(
                        f"严格模式: 无任何素材匹配目标IP《{target_ip}》。"
                        f"已识别素材归属: "
                        + ", ".join(f"{Path(k).name}→{v.primary_ip or '未识别'}"
                                    for k, v in self._intel_tags.items())
                        + "。拒绝降级到无关素材，请提供《"
                        + target_ip + "》的真实素材后重试。")
                else:
                    print(f"      [WARN] 非严格模式: 无匹配素材，将使用全部素材")
            else:
                self._selected_sources = matched
            # 覆盖度检查
            need = target_duration or self._emotion_curve.duration
            avail = sum(self._source_durations.get(m, 0) for m in self._selected_sources)
            if avail > 0 and avail < need:
                print(f"      [WARN] 匹配素材总时长 {avail:.0f}s < 目标 {need:.0f}s，"
                      f"部分段落将复用素材区间")
        else:
            # 无 IP 过滤 (自由混剪): 全部素材即选中集, 分桶如实记录
            # (修复: 此前混剪模式报告 material_selection 四桶恒为空)
            self._selection["matched"] = list(self._selected_sources)
            # 1.4b 画像驱动过滤 (2026-08-14): 统一画像 content=not_painting
            # (教程录屏/宣传图) 不适合混剪成片 → 移入 excluded (可观测, 不硬阻断)
            try:
                _profile = self._load_atmosphere_annotations()
                _excluded_content = [
                    s for s in self._selection["matched"]
                    if (_profile.get(Path(s).name) or {}).get("content")
                    == "not_painting"
                ]
                if _excluded_content:
                    self._selection["matched"] = [
                        s for s in self._selection["matched"]
                        if s not in _excluded_content
                    ]
                    self._selection["excluded"] = _excluded_content
                    self._selected_sources = list(self._selection["matched"])
                    print(f"  [1.4b] 画像过滤: {len(_excluded_content)} 个教程录屏"
                          f"(content=not_painting) 移入 excluded")
                # 1.4c 氛围偏好排序: theme 含燃/战斗 → 燃向/战斗素材前置
                _theme = (theme or "")
                if any(k in _theme for k in ("燃", "战斗", "热血", "高燃")):
                    _pref = {"燃向", "战斗"}

                    def _atmo_rank(src: str) -> int:
                        _a = (_profile.get(Path(src).name) or {}).get("atmosphere")
                        return 0 if _a in _pref else 1

                    self._selection["matched"].sort(key=_atmo_rank)
                    print("  [1.4c] 氛围偏好排序: 燃向/战斗素材前置")
            except Exception as _e:  # noqa: BLE001
                print(f"  [1.4b] 画像过滤跳过({_e})")

    # ================================================================
    #  Phase 2: 剧本编排
    # ================================================================

    def _plan(self, video_sources, bgm_path, bgm_start_sec, duration, lyrics, target_ip="",
              style_spec=None, use_speed_ramp: bool = False, theme: Optional[str] = None):
        """编排导演剧本 — 基于情绪曲线划分段落，踩拍切点，智能素材匹配

        2026-08-13 Stage1: theme 传入时用 direct_from_text 生成分镜,
        给每段加"叙事角色"(铺垫/爆发/收尾), 素材按角色匹配 — 解决杂乱无章。
        Args:
            style_spec: StyleSpec 风格规格书（方向A接口预留，None时行为不变）。
                        后续接入时驱动段落时长分布/转场抽样/色调消费。
            use_speed_ramp: 启用 SPEED_PRESETS 情绪驱动变速。
        """

        script = DirectorScript(
            title="Director Output",
            total_duration=duration,
            bgm_path=bgm_path,
            bgm_start_sec=bgm_start_sec,
        )

        # 收集目标时间范围内的强拍作为候选切点
        target_beats = [
            b for b in self._beats
            if bgm_start_sec <= b.time <= bgm_start_sec + duration
        ]
        downbeats = [b for b in target_beats if b.is_downbeat]

        if not downbeats:
            # 没有强拍则用所有节拍
            downbeats = target_beats[:32] if target_beats else []

        # 基于情绪曲线段落生成导演段落
        segments = []
        seg_idx = 0
        # 生产级候选集: 优先使用严格选择结果
        if self._selected_sources:
            available_sources = list(self._selected_sources)
        else:
            available_sources = [s for s in video_sources if s in self._source_durations]
        if not available_sources:
            available_sources = video_sources

        # 情绪曲线的时间可能是绝对时间（如从 bgm_start_sec=120 开始）
        # 需要转换为输出视频的相对时间
        curve_start = self._emotion_curve.segments[0].start_time if self._emotion_curve.segments else bgm_start_sec

        # style_spec 色彩覆盖：根据参考视频色调调整饱和度/对比度
        # 使用局部副本避免污染全局 COLOR_PRESETS
        import copy as _copy
        self._color_presets = _copy.deepcopy(COLOR_PRESETS)
        # 支持两种 key：color_profile（StyleSpec.to_dict）和 color（手动构造）
        _color_section = None
        if style_spec:
            _color_section = style_spec.get("color_profile") or style_spec.get("color")
        if _color_section:
            # 从参考视频的 color_profile 计算缩放因子
            # 中性饱和度基准=50（HSV S 范围 0~100），ref/50 即为缩放比
            _ref_sat = float(_color_section.get("saturation", 50.0))
            _ref_con = float(_color_section.get("contrast", 50.0))
            # 饱和度用超线性衰减，更强地降低饱和度（实测最优）
            _sat_ratio = _ref_sat / 50.0
            _sat_boost = max(0.35, min(1.8, _sat_ratio ** 1.3))
            # 对比度用平方根衰减（实测 ref=27.7 → boost=0.74 为最优平衡点）
            _con_boost = max(0.7, (_ref_con / 50.0) ** 0.5)
            _con_boost = min(1.2, _con_boost)
            for _k in self._color_presets:
                _new_sat = self._color_presets[_k]["saturation"] * _sat_boost
                _new_con = self._color_presets[_k]["contrast"] * _con_boost
                # 允许降饱和（下限 0.3），对比度上下限 [0.7, 1.5]
                self._color_presets[_k]["saturation"] = max(0.3, min(2.5, _new_sat))
                self._color_presets[_k]["contrast"] = max(0.7, min(1.5, _new_con))

        # === NarrativeArcPlanner 五段式叙事驱动 ===
        # 核心原则：音乐结构决定剪辑结构
        # intro(12%) → build(24%) → drop(34%) → break(12%) → outro(18%)
        # 每段有独立的切点密度、能量目标、运镜偏好
        # break段零切点(留白) / drop段密集切 / intro/outro舒缓
        bpm_val = 99.4  # 默认
        if self._beats:
            from ae.beat_detector import BeatDetector
            _bd = BeatDetector()
            bpm_val, _ = _bd.detect_bpm(bgm_path)

        # === 音乐真实能量分层 (2026-08-12 修复) ===
        # 根因: NarrativeArcPlanner 固定模板(intro12%/build24%/drop34%/break/outro)
        # 与音乐实际能量严重错位 — 实测本BGM高潮段(17.4-19.4s 能量0.83)被模板
        # 打成 outro(低能), 切点全错。v22 用 music_dynamics 从音频实际能量
        # 推导 high/mid/low, 节奏完全跟音乐走。此处改用同款分析, 生成
        # 结构兼容的 arc_segments (type→mood 映射见下, cut_times 由能量驱动)。
        import librosa as _librosa
        import numpy as _np
        from core.music_dynamics import MusicDynamicsAnalyzer
        _dyn = MusicDynamicsAnalyzer(min_section_dur=1.2, smooth_frames=15)
        _y, _sr = _librosa.load(bgm_path, sr=22050, mono=True)
        _rms = _librosa.feature.rms(y=_y, frame_length=2048, hop_length=512)[0]
        _rms_times = _librosa.frames_to_time(
            _np.arange(len(_rms)), sr=_sr, hop_length=512)
        _onsets_arr = getattr(self, "_onsets", [])
        _dyn_sections = _dyn.analyze(
            _rms, _rms_times, len(_y) / _sr,
            beats_sec=_np.array([b.time for b in self._beats]) if self._beats else None,
            onsets_sec=_np.array(_onsets_arr) if _onsets_arr else None,
        )
        # 保存 v22 细节编排所需实例
        self._dyn = _dyn
        # 保存 RMS 真实能量 + 时间轴 (v22 e_norm 用 RMS 分位数归一化)
        self._rms_energy = _rms
        self._rms_times = _rms_times
        try:
            from core.beat_strength_engine import BeatStrengthEngine
            _be = BeatStrengthEngine(fps=self._render_fps)
            _dbt = _np.array([b.time for b in self._beats
                              if getattr(b, "is_downbeat", False)]) if self._beats else _np.array([])
            self._beat_class = _be.classify_beats(
                _np.array([b.time for b in self._beats]) if self._beats else _np.array([]),
                _dbt,
                onset_envelope=_librosa.onset.onset_strength(y=_y, sr=_sr),
                rms_energy=_rms, times=_rms_times, sr=_sr, hop_length=512)
        except Exception as _e:
            print(f"      [WARN] BeatStrengthEngine 分级失败(不影响): {_e}")
            self._beat_class = None
        try:
            from core.style_presets import StylePresetSystem
            self._preset_sys = StylePresetSystem()
        except Exception:
            self._preset_sys = None
        # 能量段 → arc_segment (兼容现有 type/energy_target/cut_times 结构)
        # high→drop(密集切) / mid→build(中密度) / low→intro(长镜头)
        _LEVEL_TO_TYPE = {"high": "drop", "mid": "build", "low": "intro"}
        # ── Stage1 叙事层: theme → 分镜角色映射 (2026-08-13) ──────────
        # 用户给主题时, 用 direct_from_text 生成分镜(structure: 段落/情绪/镜头意图),
        # 给每段标注"叙事角色"(铺垫/蓄力/爆发/收尾)。素材匹配时优先按角色语义,
        # 而非纯高光/时间分散 → 解决"镜头杂乱无章"(此前每段只贴节拍无叙事意图)。
        # 失败/无 theme 时保持纯节拍驱动(行为不变)。
        self._narrative_roles: Dict[float, str] = {}  # 弧段start → 叙事角色
        self._narrative_sections: List[Dict] = []     # LLM 分镜 structure
        _theme_role = None
        if theme:
            try:
                from ai.multimodal_director import MultimodalDirector
                _md = MultimodalDirector()
                _es = _md.direct_from_text(
                    description=theme,
                    available_materials=video_sources,
                    target_duration=duration,
                    target_ip=target_ip,
                )
                _narr = _es.segments or []
                print(f"  叙事分镜(theme): {len(_narr)} 段 "
                      f"({[s.get('section','?') for s in _narr[:6]]}...)")
                # 角色推导: 首段=铺垫, 情绪渐强→蓄力, 最高情绪→爆发, 尾部→收尾
                # 2026-08-13 修复: LLM 返回 mood 是中文描述(如"压抑、绝望"),
                # 不在英文强度表 → fallback 全 2 → 角色全错。加中文关键词强度。
                _moods = [str(s.get("mood", "neutral")) for s in _narr]
                _mood_intensity = {  # 英文 mood 兜底
                    "calm": 1, "neutral": 2, "emotional": 3,
                    "build": 4, "intense": 5, "epic": 6, "climax": 7,
                }
                _MOOD_STRONG_CN = ("爆", "炸", "燃", "无敌", "高潮", "最强",
                                   "决战", "巅峰", "epic", "climax", "intense")
                _MOOD_BUILD_CN = ("蓄", "挣扎", "对抗", "升", "积", "推进",
                                  "build", "rising", "drive")
                _MOOD_CALM_CN = ("压", "绝望", "平静", "静", "余韵", "孤",
                                 "calm", "emotional", "quiet", "淡")

                def _mood_score(m: str) -> int:
                    ml = m.lower()
                    if any(k in ml for k in _MOOD_STRONG_CN):
                        return 7
                    if any(k in ml for k in _MOOD_BUILD_CN):
                        return 4
                    if any(k in ml for k in _MOOD_CALM_CN):
                        return 2
                    return _mood_intensity.get(ml.strip(), 2)

                _mood_scores = [_mood_score(m) for m in _moods]
                _peak_idx = max(range(len(_mood_scores)),
                                key=lambda i: _mood_scores[i])
                _n_segs = len(_narr)
                for _i, _s in enumerate(_narr):
                    _sc = _mood_scores[_i]
                    if _i == _peak_idx or _sc >= 5:
                        _role = "爆发"
                    elif _i < _peak_idx:
                        _role = "蓄力" if _i > 0 else "铺垫"
                    elif _i > _peak_idx:
                        _role = "收尾"
                    else:
                        _role = "铺垫"
                    _s["narrative_role"] = _role
                _theme_role = _narr
            except Exception as _e:
                print(f"  [WARN] 叙事分镜生成失败(保持纯节拍): {_e}")
        arc_segments = []
        self._arc_levels = {}
        for _ds in _dyn_sections:
            _t = _LEVEL_TO_TYPE.get(_ds.level, "build")
            _seg_dict = {
                "start": _ds.start, "end": _ds.end,
                "duration": _ds.end - _ds.start,
                "type": _t,
                "energy_target": [max(0.0, _ds.energy_mean - 0.15),
                                  min(1.0, _ds.energy_mean + 0.15)],
                "intensity": "intense" if _ds.level == "high"
                else "moderate" if _ds.level == "mid" else "gentle",
                "cut_times": [],
            }
            self._arc_levels[round(_ds.start, 3)] = _ds.level  # 逐镜头细节决策用
            arc_segments.append(_seg_dict)
        _summ = ", ".join(
            "{}:{:.1f}s".format(s_["type"], s_["duration"]) for s_ in arc_segments)
        print(f"  音乐能量分段: {len(arc_segments)} 段 ({_summ})")

        # === breath_break 标记段时间线修正 ===
        # 它嵌套在 drop 段内(如 11.6-12.8 ⊂ 7.0-13.6)，若按列表顺序追加渲染
        # 会造成时间线双重计数与转场分组错乱；正确做法：从宿主弧段中
        # 切出该区间，所有弧段按 start 排序，保证时间线单调无重叠
        _bb = [s_ for s_ in arc_segments if s_["type"] == "breath_break"]
        if _bb:
            _rest = [s_ for s_ in arc_segments if s_["type"] != "breath_break"]
            _new_arcs = []
            for s_ in _rest:
                _pieces = [s_]
                for b in _bb:
                    if s_["start"] <= b["start"] and b["end"] <= s_["end"]:
                        _split = []
                        for p in _pieces:
                            if p["start"] < b["start"] - 0.01:
                                _split.append(dict(p, end=b["start"],
                                                   duration=round(b["start"] - p["start"], 3)))
                            if p["end"] > b["end"] + 0.01:
                                _split.append(dict(p, start=b["end"],
                                                   duration=round(p["end"] - b["end"], 3)))
                        _pieces = _split
                for p in _pieces:
                    p["cut_times"] = [t for t in p.get("cut_times", [])
                                      if p["start"] <= t <= p["end"]]
                _new_arcs.extend(_pieces)
            arc_segments = sorted(_new_arcs + _bb, key=lambda s_: s_["start"])
        
        print(f"  叙事弧线: {len(arc_segments)} 段 (BPM={bpm_val:.1f})")
        for arc_seg in arc_segments:
            n_cuts = len(arc_seg.get('cut_times', []))
            print(f"    {arc_seg['type']:12s} | {arc_seg['start']:.1f}-{arc_seg['end']:.1f}s "
                  f"({arc_seg['duration']:.1f}s) | 切点={n_cuts} | "
                  f"能量={arc_seg['energy_target']} | {arc_seg['intensity']}")
        
        # === 真实节拍/onset 吸附: 替换合成BPM网格切点 ===
        # 根因修复: 合成网格锚定t=0, 与真实鼓点存在相位差;
        # 参考片实测对齐目标是onset(鼓点瞬态)而非节拍网格(53.6% vs 10.7%)
        real_beats_rel = sorted(
            b.time - bgm_start_sec for b in self._beats
            if bgm_start_sec <= b.time <= bgm_start_sec + duration)
        onset_rel = sorted(
            ot - bgm_start_sec for ot in getattr(self, "_onsets", [])
            if bgm_start_sec <= ot <= bgm_start_sec + duration)
        if len(real_beats_rel) >= 4:
            # 切点密度由 music_dynamics 能量级(high/mid/low)直接决定 (v22 plan_cuts 核心)。
            # 修复(2026-08-13): 之前用 onset 密度判定, 但 low 段的 hihat 也被当 onset,
            # 导致 low 段也密集切(实测76%镜头<0.3s, 无节奏呼吸)。
            # 正确节奏: low 长镜头蓄力(1-2s) → mid 渐密(0.5s) → high 爆发快切(0.18s)
            _MIN_SHOT_DUR = 0.18  # 对齐 v22 music_dynamics.min_shot_dur
            # information_density 旋钮 → 切点密度 (2026-08-13 接入):
            # 低信息密度(一帧一意)→ 铺垫段长镜呼吸; 高信息密度 → 整体更密。
            # 只缩放 low/mid 段的镜头时长, high 段保持爆发快切(冲击不丢)。
            _info_d = getattr(self.taste, "information_density", 5)
            # density 1-10 → 低段最小间隔 1.2s(慢) → 0.3s(快)
            _low_gap = max(0.3, 1.5 - 0.12 * _info_d)
            _mid_gap = max(0.18, 0.8 - 0.06 * _info_d)
            _downbeat_rel = sorted(
                b.time - bgm_start_sec for b in self._beats
                if getattr(b, "is_downbeat", False)
                and bgm_start_sec <= b.time <= bgm_start_sec + duration)
            for s_ in arc_segments:
                seg_onsets = [t for t in onset_rel
                              if s_["start"] + 0.05 <= t <= s_["end"] - 0.05]
                seg_beats = [t for t in real_beats_rel
                             if s_["start"] + 0.05 <= t <= s_["end"] - 0.05]
                _level = self._arc_levels.get(round(s_["start"], 3), "mid")

                # P1a (2026-08-14): onset 双拍子网格吸附 + ~30ms 相位补偿
                # WS-2 实测(beatdetect_comparison.json): ①拍网格对双鼓点对
                # 0% 双拍全命中, 而 onset 检测 90%+ 命中 → 鼓点瞬态在 onset 上,
                # 不在拍网格上; ②拍点领先 onset 系统性 ~30ms(mean -28.8ms)。
                # → 高/中能量段的切点先吸附到 ±100ms 内最近 onset(鼓点瞬态),
                #   无近邻 onset 时做 +30ms 相位前移, 让"切"落在鼓点上。
                def _snap_onset(_t, _grid, _tol=0.10, _phase=0.030):
                    import bisect as _bis
                    if not _grid:
                        return _t + _phase
                    _i = _bis.bisect_left(_grid, _t)
                    _cs = []
                    if _i < len(_grid):
                        _cs.append(_grid[_i])
                    if _i > 0:
                        _cs.append(_grid[_i - 1])
                    _near = min(_cs, key=lambda x: abs(x - _t))
                    if abs(_near - _t) <= _tol:
                        return _near
                    return _t + _phase

                if _level == "high":
                    # v23.1 双鼓点编排 (用户 2026-08-14): 爆发段"每拍一镜" —
                    # 镜头覆盖该拍的鼓点对(kick+snare 双鼓点), 镜头内部用
                    # _extract_clip 的"双鼓点对模式"做 第一鼓点推进→第二鼓点拉回。
                    # 此前 onset∪beat 全切 → 0.18s 碎切: ①装不下推进+拉回
                    # (需 ~11 帧) ②爆发战斗画面一闪而过看不清。
                    # 参考片实测(2026-08-14): drop 段镜头 ≈0.47s ≈ 1拍/镜。
                    # P1a: 每拍切点吸附到最近 onset(鼓点瞬态) + 相位补偿。
                    _pts = sorted(set(_snap_onset(b, seg_onsets) for b in seg_beats))
                    new_cuts = []
                    for _p in _pts:
                        if not new_cuts or _p - new_cuts[-1] >= _MIN_SHOT_DUR:
                            new_cuts.append(round(_p, 3))
                elif _level == "low":
                    # 低能量段 (对齐 v22 low): 仅 downbeat, 长镜头蓄力 (呼吸感)
                    # 重拍间隔>4s 时补充普通拍 (防止>5s无切点的死镜头)
                    _pts = [t for t in _downbeat_rel
                            if s_["start"] + 0.05 <= t <= s_["end"] - 0.05]
                    if not _pts:
                        _pts = [seg_beats[0]] if seg_beats else []
                    # information_density 缩放: 低信息密度 → 长镜呼吸
                    _filtered = []
                    for _p in _pts:
                        if not _filtered or _p - _filtered[-1] >= _low_gap:
                            _filtered.append(_p)
                    _gap_ok = all(
                        _filtered[i + 1] - _filtered[i] <= 5.0
                        for i in range(len(_filtered) - 1))
                    new_cuts = _filtered if _gap_ok else [_filtered[0]]
                else:
                    # 中能量段 (对齐 v22 mid): beat 逐拍 (中速)
                    # information_density 缩放: 高密度时逐拍, 低密度时抽稀
                    # P1a: 每拍切点吸附到最近 onset(鼓点瞬态) + 相位补偿
                    _new_mid = []
                    for _t in seg_beats:
                        _t = _snap_onset(_t, seg_onsets)
                        if not _new_mid or _t - _new_mid[-1] >= _mid_gap:
                            _new_mid.append(round(_t, 3))
                    new_cuts = _new_mid
                # 强制锚定 kick(低频重音)+强拍 (2026-08-13 漫剪撞拍核心):
                # 仅 high/mid 段强制 (low 段保持长镜头呼吸, 不塞快切)
                if self._beatgrid and _level != "low":
                    _mand = sorted(set(
                        self._beatgrid["kick"] + self._beatgrid["strong"]))
                    _mand = [t for t in _mand
                             if s_["start"] + 0.03 <= t <= s_["end"] - 0.03]
                    _merged = list(new_cuts)
                    for _m in _mand:
                        if all(abs(_m - c) >= _MIN_SHOT_DUR for c in _merged):
                            _merged.append(round(_m, 3))
                    new_cuts = sorted(set(_merged))
                s_["cut_times"] = new_cuts
                print(f"      [{_level:5s}] 切点={len(new_cuts)} "
                      f"(段长{s_['duration']:.1f}s)")
            print(f"  切点吸附: 真实节拍{len(real_beats_rel)}个 + onset{len(onset_rel)}个 "
                  f"(替代合成BPM网格)")

        # === 连击段(rolls)抽稀: 重击连击段内切"连续视觉"而非离散快切 ===
        # 深度研究文档§3.2: kick/snare 连击段(如17.9-19.1s kick加速滚奏=全曲
        # 最高潮)应合并成长镜头+内部脉冲缩放, 而非 0.18s 离散碎切。hihat 连击
        # 不抽稀(高频弱击本身就该密集快切)。
        _heavy_rolls = [
            r for r in (self._beatgrid or {}).get("rolls", []) or []
            if r.get("drum") in ("kick", "snare")]
        if _heavy_rolls:
            _roll_spanned = set()
            for _r in _heavy_rolls:
                _rs, _re = float(_r["start"]), float(_r["end"])
                for s_ in arc_segments:
                    _cuts = sorted(set(s_.get("cut_times", [])))
                    if not _cuts:
                        continue
                    # roll 段内(不含边界)的切点全部删除 → 合并成长镜头
                    _inner = [c for c in _cuts if _rs < c < _re]
                    if _inner:
                        _keep = [c for c in _cuts if c not in set(_inner)]
                        # roll 段边界补入(长镜头起点/终点), 保证时间线闭合
                        for _b in (_rs, _re):
                            if s_["start"] <= _b <= s_["end"] and _b not in _keep:
                                _keep.append(round(_b, 3))
                        s_["cut_times"] = sorted(set(_keep))
                        _roll_spanned.add(round(_rs, 2))
            if _roll_spanned:
                print(f"  连击段抽稀(kick/snare): {sorted(_roll_spanned)} "
                      f"→ 合并长镜头+脉冲缩放")

        # === rhythm_reward 本地模型: 切点方案择优 ===
        # 生成多个候选切点方案，用训练好的节奏奖励模型预测踩拍质量并择最优
        # （模型设计目标即“多方案择优”，视频级CV成对排序准确率95.2%）
        self._rhythm_selection = {}
        global_cuts = sorted(t for s_ in arc_segments for t in s_.get("cut_times", []))
        beats_abs = [b.time for b in self._beats
                     if bgm_start_sec <= b.time <= bgm_start_sec + duration]
        # 局部节拍间隔(高密度段硬切判定用, 不依赖奖励模型可用性)
        bi_local = 0.0
        if len(beats_abs) > 1:
            import numpy as np
            bi_local = float(np.median(np.diff(np.array(beats_abs))))
        if (self.model_hub.rhythm_scorer_available() and len(global_cuts) >= 3
                and len(beats_abs) >= 4):
            import numpy as np
            ba = np.array(beats_abs)
            bi = float(np.median(np.diff(ba)))

            def _to_abs(cuts_rel):
                # 输出视频时间 → BGM绝对时间（与 beats_abs 同坐标系）
                return [c + bgm_start_sec for c in cuts_rel]

            plans: Dict[str, List[float]] = {"arc_plan": list(global_cuts)}
            # 候选变体仅提供结构性替代(半拍偏移=切在弱拍):
            # 不提供小抖动变体——切点已吸附真实鼓点, 任何拖动都会破坏对齐
            plans["half_shift"] = sorted(
                float(c + bi / 2) for c in global_cuts if c + bi / 2 < duration)
            scores = {name: round(self.model_hub.score_cut_plan(
                _to_abs(cuts), beats_abs, duration), 4)
                for name, cuts in plans.items()}
            best_name = max(scores, key=scores.get)
            self._rhythm_selection = {
                "scores": scores, "best": best_name,
                "n_cuts": len(global_cuts), "beat_interval": round(bi, 4),
            }
            print("  节奏奖励择优(rhythm_reward.pkl): "
                  + ", ".join(f"{k}={v:.3f}" for k, v in scores.items())
                  + f" → 采用[{best_name}]")
            if best_name != "arc_plan":
                # 采纳更优方案：全局最优切点重新映射回各弧段
                best_cuts = plans[best_name]
                for s_ in arc_segments:
                    s_["cut_times"] = [c for c in best_cuts
                                       if s_["start"] <= c <= s_["end"]]
        else:
            print("  节奏奖励择优: 跳过(模型缺失或切点/节拍数不足)")

        # ── LLM 镜头设计 (2026-08-15, 用户要求"调用api模型进行辅助") ──
        # DeepSeek V4 以剪辑导演身份生成镜头剧本: 分弧段运动预算 +
        # 撞击点清单。任何失败→规则兜底(T4.5/T4.6), 不中断渲染。
        self._arc_shot_plan = {}
        self._punch_points = []
        try:
            from ai.shot_design_llm import design_shot_plan
            _local_mood_map = {
                "intro": "intro", "build": "build", "drop": "drop",
                "break": "break", "outro": "outro", "breath_break": "break",
            }
            _arc_info = [{
                "start": a["start"], "end": a["end"],
                "type": _local_mood_map.get(a["type"], "climax"),
                "level": self._arc_levels.get(round(a["start"], 3), "mid"),
                "n_cuts": len(a.get("cut_times", []) or []),
            } for a in arc_segments]
            _cache_dir = Path(getattr(self, "_output_dir", ".")) / "shot_design"
            _plan = design_shot_plan(
                _arc_info, cache_dir=_cache_dir,
                bgm_stem=Path(bgm_path).stem if bgm_path else "bgm")
            if _plan:
                self._shot_plan = _plan
                for _pa in _plan["arcs"]:
                    self._arc_shot_plan[round(float(_pa["start"]), 3)] = _pa
                    for _pp in (_pa.get("punch_points") or []):
                        self._punch_points.append(float(_pp))
                self._punch_points = sorted(set(
                    round(p, 2) for p in self._punch_points))
                if _plan.get("global"):
                    _gb = _plan["global"].get("punch_budget")
                    if isinstance(_gb, int):
                        self._punch_budget = max(len(self._punch_points), _gb)
        except Exception as _llm_e:  # noqa: BLE001
            print(f"  [LLM镜头设计] 跳过({_llm_e}) → 规则兜底")

        # ── Stage1: 弧段 → 叙事角色映射 (theme 分镜) ────────────────
        if _theme_role and arc_segments:
            self._narrative_roles = {}
            _n = len(_theme_role)
            # 修复(2026-08-13): 之前用弧段中点比例 _rel 映射分镜段,
            # 但音乐能量段(3段) vs 分镜段(4段)粒度不匹配, 比例映射
            # 丢段(实测只映射出'收尾,爆发', 缺'铺垫,蓄力')。
            # 改为: 按弧段在时间轴上的归一化位置直接推导角色,
            # 首段=铺垫, 末段=收尾, 中段按能量级(high=爆发/mid=蓄力)。
            _arcs_sorted = sorted(arc_segments, key=lambda a: a["start"])
            _total = max(duration, 0.1)
            for _ai, _arc in enumerate(_arcs_sorted):
                _rel = (_arc["start"] + _arc["end"]) / 2 / _total
                _lvl = self._arc_levels.get(round(_arc["start"], 3), "mid")
                _is_last = _ai == len(_arcs_sorted) - 1
                _is_first = _ai == 0
                # 角色推导优先级: 能量级 > 位置。末段若是 high(高潮)
                # 应是"爆发"而非"收尾"(音乐高潮≠叙事收尾); 只有低能末段才是收尾。
                if _lvl == "high":
                    _role = "爆发"
                elif _is_first:
                    _role = "铺垫"
                elif _is_last:
                    _role = "收尾"  # 末段低能=真正收尾
                elif _lvl == "mid":
                    _role = "蓄力"
                else:
                    _role = "铺垫"
                self._narrative_roles[round(_arc["start"], 3)] = _role
            print(f"  叙事角色映射: {len(arc_segments)} 弧段 "
                  f"({', '.join(sorted(set(self._narrative_roles.values())))})")

        # ── T3: 素材运镜感知 (光流分类器 + 决策层) ────────────────
        _cam_inv = None
        _prev_camera = "unknown"
        _recent_cams: list = []   # 反锁死窗口 (最近 2 镜运镜)
        _MAX_RECENT = 2
        try:
            from ai.camera_decision import (
                SourceCameraInventory, suggest_camera_for_shot,
            )
            _cam_inv = SourceCameraInventory()
            _cam_inv.batch_analyze(available_sources)
            # Step 3 V3.1: 三级级联运镜注入 (kandinsky-large → gullalc base → 光流规则)
            # A/B 实测 (models/output/videomae_ab_20260814.json): base 版把 68% 素材
            # 误标 pan_left, kandinsky 有效标签置信中位 0.99 → 高精度优先
            try:
                from models.camera.videomae_camera import classify_cascade
                _n_cam = _n_base = 0
                for _src in available_sources:
                    _res = classify_cascade(_src)
                    if _res:
                        _cam_inv.inject(_src, label=_res["label"],
                                        confidence=_res["confidence"])
                        if _res.get("stage") == "kandinsky":
                            _n_cam += 1
                        else:
                            _n_base += 1
                if _n_cam or _n_base:
                    print(f"  VideoMAE运镜: kandinsky={_n_cam} base={_n_base} / "
                          f"{len(available_sources)} 素材注入 (其余回退光流规则)")
            except Exception as _vmae_e:  # noqa: BLE001
                print(f"  VideoMAE运镜: 跳过({_vmae_e})")
            _src_cam_labels = {
                src: _cam_inv.analyze(src)["label"]
                for src in available_sources
            }
            print(f"  运镜感知(T3): {', '.join(f'{Path(s).name}={l}' for s, l in _src_cam_labels.items())}")
        except Exception as _e:
            print(f"  运镜感知(T3): 跳过({_e})")

        # 情绪→mood映射
        _ARC_MOOD = {
            "intro": "intro", "build": "build", "drop": "drop",
            "break": "break", "outro": "outro", "breath_break": "break",
        }
        
        for arc_idx, arc_seg in enumerate(arc_segments):
            arc_start = arc_seg["start"]
            arc_end = arc_seg["end"]
            # 2026-08-15: 成片时长裁剪 (尾部静音) 后, 弧段表来自全曲分析,
            # 必须钳制到 duration, 否则尾弧越过裁剪点把电影又拉回原长
            # (v7 实测: 计划 164.2s 但成片 168.48s)
            if arc_start >= duration - 0.05:
                continue
            if arc_end > duration:
                arc_end = duration
                # 帧网格吸附: 裁剪点对齐 1/fps 整数倍, 防止 ffmpeg -t
                # 向上取整逐 clip 累积漂移 (2026-08-16 根因)
                _fg = getattr(self, "_render_fps", 24) or 24
                arc_end = round(round(arc_end * _fg) / _fg, 4)
            arc_type = arc_seg["type"]
            mood = _ARC_MOOD.get(arc_type, "climax")
            energy_val = (arc_seg["energy_target"][0] + arc_seg["energy_target"][1]) / 2
            # 该弧段对应的 music_dynamics 能量级 (high/mid/low) — v22 细节决策依据
            _level = self._arc_levels.get(round(arc_start, 3), "mid")
            _v22_tech = None  # speed_for_shot 返回的技巧标签 (pulse/slowmo/fast_pan)
            cut_times = arc_seg.get("cut_times", [])
            
            # 构建切点列表：将 arc 的 cut_times 转为段落内边界
            boundaries = [arc_start] + sorted(cut_times) + [arc_end]
            # 去重 + 过滤范围外
            boundaries = sorted(set(b for b in boundaries if arc_start <= b <= arc_end))
            # 边界吸附到最近拍点 (2026-08-13 修复):
            # 弧段 start/end 来自 music_dynamics 能量分层边界(非拍点),
            # 产生"不在拍上"的镜头边界(实测7个偏移84-307ms)。
            # v22 plan_cuts 只从拍/onset 生成切点(空档处不切), 故100%踩拍。
            # 策略: 非首尾边界在 250ms 内有拍/onset 则吸附; 完全空档
            # (无拍)处保留原边界(长镜头跨越空档 = 正确行为, 非偏移)。
            _snap_grid = sorted(set(
                [t for t in real_beats_rel if arc_start <= t <= arc_end] +
                [t for t in onset_rel if arc_start <= t <= arc_end]))
            if _snap_grid:
                import bisect as _bisect
                _snapped = [boundaries[0]]
                for _b in boundaries[1:-1]:
                    _i = _bisect.bisect_left(_snap_grid, _b)
                    _cands = []
                    if _i < len(_snap_grid):
                        _cands.append(_snap_grid[_i])
                    if _i > 0:
                        _cands.append(_snap_grid[_i - 1])
                    if _cands:
                        _near = min(_cands, key=lambda x: abs(x - _b))
                        if abs(_near - _b) < 0.25:
                            _b = _near
                    if _b - _snapped[-1] >= 0.05:
                        _snapped.append(_b)
                if boundaries[-1] - _snapped[-1] >= 0.05:
                    _snapped.append(boundaries[-1])
                else:
                    _snapped[-1] = boundaries[-1]
                boundaries = _snapped
            # 帧网格吸附: 边界对齐到 1/fps 整数倍, 使每片段时长为整帧数,
            # 消除逐片段舍入误差的累积漂移(根因: 计划切点62%踩拍但成片仅18%)
            _fps_grid = getattr(self, "_render_fps", 24) or 24
            boundaries = sorted(set(round(round(b * _fps_grid) / _fps_grid, 4)
                                    for b in boundaries))
            # 过短区间并入前段（而非跳过）：跳过会产生时间线缺口,
            # 导致后续所有切点累积前移
            # P1a(2026-08-14): 阈值 0.15→0.18 对齐 _MIN_SHOT_DUR —
            # onset 吸附后边界收敛可能产生 0.16s 碎切(实测), 一并合并
            _merged = [boundaries[0]]
            for _b in boundaries[1:]:
                if _b - _merged[-1] < 0.18:
                    continue
                _merged.append(_b)
            if _merged[-1] < boundaries[-1]:
                _merged[-1] = boundaries[-1]
            boundaries = _merged
            
            for bi in range(len(boundaries) - 1):
                seg_start = boundaries[bi]
                seg_end = boundaries[bi + 1]
                seg_dur = seg_end - seg_start
                if seg_dur < 0.05:
                    continue
                
                color_grade = mood if mood in self._color_presets else "climax"

                # 智能素材匹配：叙事角色优先 (Stage2 语义匹配)
                # 修复(2026-08-13): get_smart_assignment 按 mood 匹配时 7素材
                # mood 标签区分度不足, 退化成轮转(实测各5-6镜完全平均)。
                # 改为: 叙事角色 → 语义窗口匹配, 用预分析缓存(cache/semantic_windows)
                # 铺垫=calm(猫/美人鱼) 蓄力=intense/bright(五条悟/初音) 爆发=battle(独自升级)
                _role = self._narrative_roles.get(round(arc_start, 3), "")
                _all_caps = {s: self._source_durations.get(s, 60.0)
                             for s in available_sources}
                if _role and _role in ("铺垫", "蓄力", "爆发", "收尾"):
                    source = self._pick_by_narrative_role(_role, available_sources, seg_idx)
                    if not source:
                        source = self._balanced_pick(available_sources, seg_idx,
                                                     capacities=_all_caps)
                elif self._material_index and len(self._material_index.tags) > 0:
                    source = self._material_index.get_smart_assignment(
                        seg_idx, len(arc_segments),
                        target_mood=mood, target_ip=target_ip,
                        candidates=available_sources,
                    )
                    if not source:
                        source = self._balanced_pick(available_sources, seg_idx,
                                                     capacities=_all_caps)
                else:
                    source = self._balanced_pick(available_sources, seg_idx,
                                                 capacities=_all_caps)
                # 素材使用计数 (2026-08-15 均衡轮转依据)
                self._source_use_count[source] = \
                    self._source_use_count.get(source, 0) + 1
                src_dur = self._source_durations.get(source, 60.0)

                # 素材内的起始时间：贪心最远点分散取点，避免同区间复用导致视觉疲劳
                source_start = self._calc_source_start(
                    seg_idx, src_dur, seg_dur, mood, source_key=source,
                    role=_role if _role else None,
                )

                # 文字叠加
                text_overlay = None
                if lyrics:
                    for item in lyrics:
                        if len(item) == 5:
                            ls, le, text, lcolor, lmood = item
                        elif len(item) == 4:
                            ls, le, text, lcolor = item
                            lmood = mood
                        else:
                            continue
                        if seg_start <= ls < seg_end:
                            text_overlay = {
                                "lyric": text,
                                "start": ls,
                                "end": le,
                                "color": lcolor,
                                "mood": lmood,
                            }
                            break

                # 节拍上下文预取 (2026-08-14): 供转场/运镜稀疏化决策复用
                _bs_val = "medium"
                _is_db = False
                if getattr(self, "_beat_class", None):
                    try:
                        _bs0 = self._beat_class.get_beat_at_time(seg_start, tolerance=0.08)
                        if _bs0 is None:
                            _all_b = getattr(self._beat_class, "beats", None)
                            if _all_b:
                                _bs0 = min(_all_b, key=lambda b: abs(b.time_sec - seg_start))
                        if _bs0 is not None:
                            _bs_val = getattr(_bs0, "strength", None)
                            _bs_val = _bs_val.value if _bs_val is not None else "medium"
                            _is_db = bool(getattr(_bs0, "is_downbeat", False))
                    except Exception:
                        pass
                _is_strong = (_bs_val == "strong") or _is_db

                # 转场：叙事段类型驱动
                transition = "cut"
                if style_spec and style_spec.get("transitions"):
                    import random as _rng
                    _trans_pool = style_spec["transitions"]
                    _weights = [t.get("probability", 0.2) for t in _trans_pool]
                    _types = [t.get("type", "fade") for t in _trans_pool]
                    if mood in ("drop", "climax"):
                        _boost = {"flash": 3.0, "zoom": 2.0, "glitch": 2.0, "fade": 0.5, "slide": 0.5}
                    elif mood in ("intro", "outro"):
                        _boost = {"fade": 2.0, "slide": 1.5, "flash": 0.3, "zoom": 0.5, "glitch": 0.3}
                    else:
                        _boost = {"fade": 1.0, "slide": 1.0, "flash": 1.0, "zoom": 1.0, "glitch": 1.0}
                    _boosted = [_weights[i] * _boost.get(_types[i], 1.0) for i in range(len(_types))]
                    transition = _rng.choices(_types, weights=_boosted, k=1)[0]
                elif mood in ("drop", "climax"):
                    # 爆发段: 默认硬切; 闪白只落在下拍上 (2026-08-14 用户反馈:
                    # 此前每段 flash 或强拍都闪 → 闪回泛滥; 下拍=小节级冲击点)
                    transition = "flash" if _is_db else "cut"
                elif mood == "intro":
                    transition = "fade"
                elif mood == "build":
                    # 蓄力段转场轮转 (主体硬切保节奏, 每 6 镜插入闪白/叠化)
                    # (修复: 此前 build 段一律 cut。注: 变速镜头渲染层强制硬切
                    #  防切点漂移, 此轮转仅在原速镜头间生效)
                    _r = seg_idx % 6
                    transition = {2: "flash", 5: "fade"}.get(_r, "cut")
                elif mood == "break":
                    transition = "fade"  # break段用淡入淡出

                # 高密度踩拍段强制硬切：xfade重叠期(0.12-0.35s)会模糊切点,
                # 导致"有几帧速度和时间跟不上"的拖沓感(漫剪惯例: drop硬切卡点)
                if mood in ("drop", "climax") and bi_local > 0 and seg_dur <= bi_local * 1.5:
                    transition = "cut"
                # 喘息点进入/退出用硬切：瞬间静止是节奏设计的一部分,
                # 淡入淡出会糊掉"突然安静"的对比感
                if arc_type == "breath_break":
                    transition = "cut"

                # 硬停止(hard_stop) → 闪白: 音乐突然停止的瞬间, 用闪白/定格
                # 放大"戛然而止"冲击 (深度研究文档§3.3)。hard_stop 时间轴与
                # onset 同源(BGM 文件时间), 需减 bgm_start_sec 转输出时间。
                _hs_rel = [float(h["t"]) - bgm_start_sec
                           for h in (self._beatgrid or {}).get("hard_stops", []) or []]
                _is_hard_stop = any(
                    abs(seg_start - _h) < 0.12 or abs(seg_end - _h) < 0.12
                    for _h in _hs_rel)
                if _is_hard_stop:
                    transition = "flash"

                # 闪白间距门控 (2026-08-14 用户反馈): 非 hard_stop 的 flash
                # 最少间隔 25s — 闪白是冲击符号, 泛滥即失效。
                if transition == "flash" and not _is_hard_stop:
                    if seg_start - self._last_flash_sec < 25.0:
                        transition = "cut"
                    else:
                        self._last_flash_sec = seg_start

                # 变速：style_spec 覆盖 > 逐镜头动态决策(v22 beat_strength) > SPEED_PRESETS
                if style_spec and style_spec.get("speed_curve") and mood in style_spec["speed_curve"]:
                    speed = float(style_spec["speed_curve"][mood])
                elif use_speed_ramp:
                    # v22 细节决策: 逐镜头看节拍强弱+能量 → speed_for_shot
                    # (漫剪惯例: low+强拍→慢放落点0.55x 沉下去; high+普通拍→加速1.3-1.5x)
                    # v22 逐镜头细节: 节拍强弱 → speed_for_shot
                    # 修复: 1) beat匹配用"最近拍"回退(v22 cut吸附在拍上能命中,
                    #    v23 边界有偏移 → 55%退化MEDIUM全原速)
                    #    2) e_norm 用 RMS 真实能量分位归一(v22 铁律公式)
                    _bs = None
                    if getattr(self, "_beat_class", None):
                        _bs = self._beat_class.get_beat_at_time(seg_start, tolerance=0.08)
                        if _bs is None:
                            # 最近拍回退: 找所有拍点中离 seg_start 最近的
                            _all_b = self._beat_class.beats
                            if _all_b:
                                _bs = min(
                                    _all_b, key=lambda b: abs(b.time_sec - seg_start))
                    _bs_val = (_bs.strength.value if _bs else "medium")
                    _is_db = bool(getattr(_bs, "is_downbeat", False))
                    # e_norm: 镜头中点处的 RMS 真实能量 (v22 用 e_p10/e_p90 分位)
                    _seg_mid = (seg_start + seg_end) / 2
                    _e_norm = 0.5
                    if getattr(self, "_rms_energy", None) is not None and \
                            len(self._rms_energy) > 0:
                        try:
                            import numpy as _npx
                            _e10 = float(_npx.percentile(self._rms_energy, 10))
                            _e90 = float(_npx.percentile(self._rms_energy, 90))
                            _em = float(_npx.interp(
                                _seg_mid, self._rms_times, self._rms_energy))
                            _e_norm = float(_npx.clip(
                                (_em - _e10) / max(_e90 - _e10, 1e-6), 0, 1))
                        except Exception:
                            _e_norm = 0.5
                    _speed, _tech = self._dyn.speed_for_shot(
                        _level, _bs_val, _e_norm, _is_db)
                    speed = _speed
                    _v22_tech = _tech  # 供运镜决策使用
                    # 变速稀疏化 (2026-08-14 用户二次反馈): 慢放/变速是强调
                    # 手段而非全片默认 — 非强拍镜头保持原速 (1.0x)。
                    if not _is_strong and speed != 1.0:
                        speed = 1.0
                        _v22_tech = "normal"
                else:
                    speed = 1.0

                # ── T3 运镜决策: 素材感知 + 情绪映射 + 衔接平滑 ────
                _source_cam = "unknown"
                if _cam_inv is not None:
                    _source_cam = _src_cam_labels.get(source, "unknown")

                if _cam_inv is not None:
                    # T3: 综合决策 (情绪 + 素材运镜 + 前一镜衔接 + 反锁死窗口)
                    zoompan_effect = suggest_camera_for_shot(
                        mood=mood,
                        source_camera=_source_cam,
                        prev_camera=_prev_camera,
                        recent=_recent_cams,
                        max_repeat=_MAX_RECENT,
                    )
                    # pulse 技巧: 爆发段鼓点 → 推进镜头 (快推撞击感, 替代缓推 zoom_in)
                    if _v22_tech == "pulse":
                        zoompan_effect = "push"
                else:
                    # 降级: 旧版逻辑 (T3 模块不可用时)
                    _ZOOMPAN_MAP = {
                        "intro": "zoom_in", "build": "pan_left",
                        "drop": "zoom_in", "climax": "zoom_in",
                        "break": "diag_pan", "outro": "zoom_out",
                    }
                    if use_speed_ramp and getattr(self, "_beat_class", None):
                        _active_preset = None
                        if getattr(self, "_preset_sys", None):
                            try:
                                _active_preset = self._preset_sys.active
                            except Exception:
                                _active_preset = self._preset_sys.active()
                        if _level == "low":
                            zoompan_effect = "zoom_in" if seg_idx % 2 == 0 else "zoom_out"
                        elif _level == "high":
                            _zp = _active_preset.choose_camera(
                                beat_strength=_bs_val, index=seg_idx) if _active_preset else None
                            zoompan_effect = _zp or "zoom_in"
                        else:
                            if _bs_val == "strong":
                                _zp = _active_preset.choose_camera(
                                    beat_strength="strong", index=seg_idx) if _active_preset else None
                                zoompan_effect = _zp or "zoom_back"
                            else:
                                zoompan_effect = ["pan_left", "zoom_in", "diag_pan", "zoom_out"][seg_idx % 4]
                        if _v22_tech == "pulse":
                            zoompan_effect = "push"
                    else:
                        zoompan_effect = _ZOOMPAN_MAP.get(mood, "zoom_in")
                        if mood in ("drop", "climax") and seg_idx % 2 == 1:
                            zoompan_effect = "zoom_back"

                # T4: 品味契约约束运镜池 — 若选中运镜不在品味池内, 从池中循环选取;
                # visual_variance >= 7 (高视觉变化度) 时强制池内轮转 (反默认机)。
                _taste_pool = self.taste.camera_pool()
                _forbid = getattr(self, "_forbidden_cameras", []) or []
                if _forbid:
                    _allowed = [c for c in _taste_pool if c not in _forbid]
                    if _allowed:
                        _taste_pool = _allowed
                if _taste_pool and len(_taste_pool) > 1:
                    if self.taste.visual_variance >= 7:
                        _pick = _taste_pool[seg_idx % len(_taste_pool)]
                        _guard = 0
                        while _pick in _recent_cams and _guard < len(_taste_pool):
                            _guard += 1
                            _pick = _taste_pool[(seg_idx + _guard) % len(_taste_pool)]
                        zoompan_effect = _pick
                    elif zoompan_effect not in _taste_pool:
                        zoompan_effect = _taste_pool[seg_idx % len(_taste_pool)]

                # T4.55 LLM撞击点强制 (2026-08-15): 剧本指定爆发段强拍 → push
                _plan_punch = (
                    mood in ("drop", "climax")
                    and any(abs(seg_start - _pp) < 0.35
                            for _pp in self._punch_points)
                )
                if _plan_punch:
                    zoompan_effect = "push"

                # T4.5 镜头设计层 (2026-08-14 用户二次反馈重设计):
                # 静态为主、运动为稀缺强调。专业 AMV 大部分镜头固定硬切,
                # 运动镜头集中作为强调 (按段落 10-30%), 而非全片均匀推拉。
                # (2026-08-15) 运动预算优先取 LLM 镜头剧本的分弧段值。
                if zoompan_effect != "static" and not _plan_punch:
                    _motion_per_10 = {
                        "intro": 1, "build": 2, "drop": 3,
                        "climax": 3, "break": 1, "outro": 1,
                    }.get(mood, 2)
                    _pa = self._arc_shot_plan.get(round(arc_start, 3))
                    if _pa and isinstance(_pa.get("motion_per_10"), int):
                        _motion_per_10 = int(_pa["motion_per_10"])
                    if (seg_idx * 7 + 3) % 10 >= _motion_per_10:
                        zoompan_effect = "static"

                # T4.6 撞击运镜预算 (2026-08-15 用户三次反馈 + v22 对比学习):
                # v22 全片 pulse 仅 2 次, 且无 onset 逐拍推拉 — 拉进/闪回撞击
                # 是稀缺强调, 只属于爆发段(drop/climax)强拍。全片预算 6 次、
                # 间隔 >=20s; 其余 push/zoom_in 一律降为静态, 防止再次
                # "每个镜头都推拉闪回"。LLM 剧本指定点优先放行。
                if zoompan_effect in ("push", "zoom_in"):
                    _punch_ok = _plan_punch or (
                        mood in ("drop", "climax")
                        and _is_strong
                        and (seg_start - self._last_punch_sec >= 20.0)
                        and self._punch_budget > 0
                    )
                    if _punch_ok:
                        if not _plan_punch:
                            self._punch_budget -= 1
                        self._last_punch_sec = seg_start
                    else:
                        zoompan_effect = "static"

                # 记录前一镜运镜 (供 T3 衔接平滑度用) + 反锁死窗口
                _prev_camera = zoompan_effect
                _recent_cams.append(zoompan_effect)
                if len(_recent_cams) > _MAX_RECENT:
                    _recent_cams.pop(0)

                # 计算该镜头内的 onset 时间点（用于脉冲运镜）
                seg_onsets = []
                if hasattr(self, '_onsets') and self._onsets:
                    for ot in self._onsets:
                        # onset 在 BGM 文件时间，转换为输出视频时间
                        out_t = ot - bgm_start_sec
                        if seg_start <= out_t < seg_end:
                            # 转换为镜头内相对时间
                            seg_onsets.append(out_t - seg_start)

                seg = DirectorSegment(
                    index=seg_idx,
                    start_time=seg_start,
                    end_time=seg_end,
                    duration=seg_dur,
                    mood=mood,
                    energy=energy_val,
                    source_file=source,
                    source_start=source_start,
                    text_overlay=text_overlay,
                    color_grade=color_grade,
                    transition=transition,
                    speed=speed,
                    zoompan_effect=zoompan_effect,
                    onset_times=seg_onsets,
                )
                segments.append(seg)
                seg_idx += 1

        # ---- style_spec 切率驱动段落细分 ----
        # 节拍驱动模式下禁用细分：切点已严格对齐节拍，不再人为加密
        # 只有当段落数极少（<5）且参考切率极高时才触发
        if style_spec and style_spec.get("cut_rate") and len(segments) < 5:
            _target_cr = float(style_spec["cut_rate"])
            _current_cr = len(segments) / max(duration, 0.1)
            if _target_cr > _current_cr * 1.2:  # 差距>20%时触发
                # 目标段落时长：取 1/cut_rate 和 0.4s 的较大值（避免碎片化）
                _target_seg_dur = max(0.2, min(0.5, 1.0 / _target_cr))
                _beat_times_rel = []
                if self._beats:
                    _beat_times_rel = [b.time - curve_start for b in self._beats
                                       if 0 <= b.time - curve_start <= duration]
                # 收集可用素材源（用于细分时交替取源，增加切点视觉差异）
                _alt_sources = list(set(s for s in self._source_durations.keys()))
                _new_segments = []
                for seg in segments:
                    if seg.duration <= _target_seg_dur * 1.3:
                        _new_segments.append(seg)
                        continue
                    # 计算切分数
                    import math as _math
                    _n_splits = _math.ceil(seg.duration / _target_seg_dur)
                    _n_splits = max(2, min(_n_splits, 10))
                    # 生成切分时间点（优先对齐节拍）
                    _split_times = [seg.start_time]
                    for _si in range(1, _n_splits):
                        _ideal = seg.start_time + (seg.duration * _si / _n_splits)
                        # 在 ±0.15s 范围内找最近的节拍点对齐
                        _best_snap = _ideal
                        for _bt in _beat_times_rel:
                            if abs(_bt - _ideal) < 0.15 and seg.start_time < _bt < seg.end_time:
                                if abs(_bt - _ideal) < abs(_best_snap - _ideal):
                                    _best_snap = _bt
                        _split_times.append(_best_snap)
                    _split_times.append(seg.end_time)
                    # 去重并排序
                    _split_times = sorted(set(_split_times))
                    for _si in range(len(_split_times) - 1):
                        _sub_start = _split_times[_si]
                        _sub_end = _split_times[_si + 1]
                        _sub_dur = _sub_end - _sub_start
                        if _sub_dur < 0.1:
                            continue
                        # 细分时交替取不同素材位置，增加切点视觉差异
                        if _si % 2 == 0:
                            _sub_src = seg.source_file
                            _sub_src_start = seg.source_start + (_sub_start - seg.start_time)
                        elif len(_alt_sources) > 1:
                            # 交替到另一素材的随机位置
                            _other = [s for s in _alt_sources if s != seg.source_file]
                            if _other:
                                import random as _rnd
                                _sub_src = _rnd.choice(_other)
                                _other_dur = self._source_durations.get(_sub_src, 60.0)
                                _sub_src_start = max(0, _rnd.uniform(0, max(0, _other_dur - _sub_dur)))
                            else:
                                _sub_src = seg.source_file
                                _sub_src_start = seg.source_start + (_sub_start - seg.start_time)
                        else:
                            # 单素材：跳到不同时间位置
                            _src_dur = self._source_durations.get(seg.source_file, 60.0)
                            _sub_src = seg.source_file
                            _sub_src_start = max(0, (_sub_src_start + _src_dur * 0.37) % max(1, _src_dur - _sub_dur))
                        _sub_seg = DirectorSegment(
                            index=seg_idx,
                            start_time=_sub_start,
                            end_time=_sub_end,
                            duration=_sub_dur,
                            mood=seg.mood,
                            energy=seg.energy,
                            source_file=_sub_src,
                            source_start=_sub_src_start,
                            text_overlay=None,
                            color_grade=seg.color_grade,
                            transition="cut" if _si < len(_split_times) - 2 else seg.transition,
                            speed=seg.speed,
                            zoompan_effect=seg.zoompan_effect,
                        )
                        _new_segments.append(_sub_seg)
                        seg_idx += 1
                segments = _new_segments
                for _ri, _rs in enumerate(segments):
                    _rs.index = _ri
                seg_idx = len(segments)

        script.segments = segments
        # 逐镜头决策依据收集: 由已编排字段显式生成 (供 decision_log rationale 用,
        # 避免全靠兜底推导出模糊理由)
        _decision_rationale = {}
        for _s in segments:
            _why = {
                "material": f"情绪{_s.mood}能量{round(_s.energy, 2)}匹配的素材窗口",
                "speed": f"音乐动态映射: mood={_s.mood}→{_s.speed}x",
                "technique": (f"运镜{_s.zoompan_effect}" if _s.zoompan_effect
                              else "常规镜头无需特效运镜"),
                "transition": f"段落边界/节拍强度决定: {_s.transition}",
            }
            _decision_rationale[_s.index] = _why
        script.metadata = {
            "beat_count": len(self._beats),
            "downbeat_count": len(downbeats),
            "emotion_segments": len(self._emotion_curve.segments),
            "material_count": len(video_sources),
            "rhythm_reward_selection": self._rhythm_selection,
            "beatnet_fusion": (
                self._beatnet_fusion.to_dict() if self._beatnet_fusion else None
            ),
            "scene_model_tags": {
                Path(k).name: v for k, v in self._scene_model_tags.items()
            },
            "decision_rationale": _decision_rationale,
            "t3_camera_perception": {
                Path(k).name: v for k, v in _src_cam_labels.items()
            } if _cam_inv is not None else None,
        }

        # 如果情绪曲线未覆盖完整时长，用最后一段情绪填充剩余
        covered = sum(s.duration for s in segments)
        if covered < duration * 0.9 and segments:
            last = segments[-1]
            gap = duration - covered
            if gap >= 0.5:
                fill_start = last.end_time
                src = last.source_file
                src_dur = self._source_durations.get(src, 60.0)
                fill_seg = DirectorSegment(
                    index=len(segments),
                    start_time=fill_start,
                    end_time=fill_start + gap,
                    duration=gap,
                    mood=last.mood,
                    energy=last.energy,
                    source_file=src,
                    source_start=min(last.source_start + last.duration, max(src_dur - gap, 0)),
                    text_overlay=None,
                    color_grade=last.color_grade,
                    transition=last.transition,
                    zoompan_effect=getattr(last, 'zoompan_effect', 'zoom_in'),
                )
                segments.append(fill_seg)
                covered += gap
                print(f"  补充 {gap:.1f}s 填充段落")

        print(f"  生成 {len(segments)} 个段落, 总时长 {duration:.1f}s")
        return script

    def _load_beatgrid(self, bgm_path: str) -> Optional[Dict[str, Any]]:
        """加载 OpenMontage beatgrid 音频骨架 (鼓类型/网格语义)。

        2026-08-13: 漫剪"跟音乐剪辑"核心——切点锚定 kick(低频重音)+强拍,
        而非笼统 onset(混入 hihat/切分音)。调 analyze-beatgrid.py 生成
        audiomap.json (按 BGM 名缓存 tmp/), 解析:
          kick_times:  低频重音 <150Hz (撞拍核心)
          strong_times: 强拍 (正拍)
          weak_times:  弱拍 (排除 hihat, 高密度补充)
        失败返回 None → 回退现有 onset 逻辑, 不阻断渲染。
        """
        try:
            import hashlib, subprocess, json, os
            _h = hashlib.md5(os.path.basename(bgm_path).encode()).hexdigest()[:8]
            _cache = os.path.join("tmp", f"audiomap_{_h}.json")
            _script = os.path.join(
                _PROJECT_ROOT, "external", "OpenMontage", ".agents",
                "skills", "music-to-video", "scripts", "analyze-beatgrid.py")
            if not os.path.exists(_script):
                return None
            if not os.path.exists(_cache):
                _r = subprocess.run(
                    [sys.executable, _script, bgm_path, "-o", _cache],
                    capture_output=True, timeout=180)
                if _r.returncode != 0:
                    return None
            with open(_cache, encoding="utf-8") as _f:
                _d = json.load(_f)
            _events = _d.get("events", [])
            kicks = [float(e["t"]) for e in _events if e.get("drum") == "kick"]
            # 修复(2026-08-13): strong 必须排除 hihat——铁律"strong拍强制锚定
            # (排除 hihat/riser/glitch)"。此前只 weak 排 hihat, strong 混入 5 个
            # hihat strong(4.9/7.31/12.1/13.26/14.47s), 切在镲片上观感不"撞"。
            strongs = [float(e["t"]) for e in _events
                       if e.get("grid") == "strong" and e.get("drum") != "hihat"]
            weaks = [float(e["t"]) for e in _events
                     if e.get("grid") == "weak" and e.get("drum") != "hihat"]
            # 连击段/关键时刻/突然停止 (深度研究文档§3.2/§3.3, 此前被丢弃):
            # rolls → 连击段内切"连续视觉"而非离散快切; hard_stops/moments →
            # 关键时刻语义(定格/闪白/变速)。原样透传, 编排层消费。
            _rolls = _d.get("rolls", []) or []
            _moments = _d.get("key_moments", []) or []
            _hard_stops = _d.get("hard_stops", []) or []
            return {
                "kick": sorted(set(kicks)),
                "strong": sorted(set(strongs)),
                "weak": sorted(set(weaks)),
                "rolls": _rolls,
                "moments": _moments,
                "hard_stops": _hard_stops,
            }
        except Exception as _e:
            print(f"      [WARN] beatgrid 加载失败(回退onset): {_e}")
            return None

    def _detect_onsets(self, bgm_path: str) -> list:
        """检测 BGM 中的能量突增点 (onset) — 驱动镜头内脉冲运镜

        2026-08-12 修复: 改用 librosa onset_detect (频谱通量法)。
        自写能量包络法(1.4x 阈值)精度差——v22 成片实测 onset 对齐 78.3%
        用 librosa, 而自写检测出的 onset 与真实鼓点偏移大, 导致 v23
        切点密度对了但对齐率反降 (56.1%)。统一为 v22 同款检测。

        Returns:
            List[float]: onset 时间点列表（秒）
        """
        try:
            import librosa
            import numpy as np
        except ImportError as e:
            print(f"      Onset检测失败(librosa缺失): {e}")
            return []
        try:
            y, sr = librosa.load(bgm_path, sr=44100, mono=True)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            frames = librosa.onset.onset_detect(
                onset_envelope=onset_env, sr=sr, backtrack=False)
            onsets = [float(t) for t in librosa.frames_to_time(frames, sr=sr)]
            return onsets
        except Exception as e:
            print(f"      Onset检测失败: {e}")
            return []

    def _calc_source_start(self, seg_idx, src_dur, seg_dur, mood, source_key="",
                           role: Optional[str] = None):
        """计算素材内起始时间 — 内容感知高光优先 + 叙事角色语义匹配 + 贪心去重

        2026-08-13 Stage2: 叙事角色(铺垫/蓄力/爆发/收尾) → 匹配素材中
        对应语义的时间窗口。Qwen3-VL 实测同一素材不同时间段语义可区分
        (5s=孤独/坐 → 55s=intense/fight → 100s=tense/combat),
        铺垫段应配 calm 窗口, 爆发段应配 battle/intense 窗口。
        语义窗口懒加载 + 磁盘缓存(失败回退高光池/贪心, 不阻断)。
        """
        # 叙事角色 → 场景偏好 (用于匹配时间窗口, 与 _pick_by_narrative_role 对齐)
        # 修复(2026-08-13): 之前用 mood(intense/action) 匹配, 但语义窗口存的是
        # scene_type, "action" 同时命中 battle/closeup 动作镜头, 导致爆发段选到
        # 特写。改为 scene 精确匹配: 爆发=battle/fighting(不含 action)。
        _role_scene = {
            "铺垫": ("landscape", "closeup", "indoor", "dialogue"),
            "蓄力": ("action", "closeup", "landscape"),
            "爆发": ("battle", "fighting"),
            "收尾": ("landscape", "closeup", "dialogue", "indoor"),
        }
        if role and role in _role_scene:
            _semantic_pool = self._get_semantic_windows(source_key)
            if _semantic_pool:
                used = self._used_windows.setdefault(source_key, [])
                _scene_pref = _role_scene[role]
                # 按语义偏好排序的候选窗口, 取未用的
                # 主场景匹配: "battle/action" → 首段 "battle"(避免 action 误匹配)
                # v4 帧级对齐 (2026-08-14): 窗口(3s)标签=中部单帧(50%),
                # 返回 +1.5s(中部) 让渲染帧恰好命中被 VLM 判定的那一帧。
                # (v3 曾 +0.75s 对齐 25% 帧, 但标签可能由 75% 帧驱动,
                #  实测爆发段取到 closeup intro → 叙事一致性仅 0.625)
                _win_offset = 1.5
                for _start, _tag in _semantic_pool:
                    _primary = str(_tag).split("/")[0].strip().lower()
                    _pick = _start + _win_offset
                    if _primary in _scene_pref and _pick + seg_dur <= src_dur and \
                            all(abs(_pick - u) >= max(seg_dur * 2.5, 1.5)
                                for u in used):
                        used.append(_pick)
                        return round(_pick, 2)
                # 语义池无匹配: 回退高光池逻辑

        # 高光段池 (懒加载, 复用 v22 磁盘缓存 cache/highlight_scores/)
        pool = self._get_highlight_pool(source_key)
        used = self._used_windows.setdefault(source_key, [])

        if pool is not None:
            # 优先: 未用且长度足够的最高分段
            for start_sec, total in pool:
                if start_sec + seg_dur <= src_dur and \
                        all(abs(start_sec - u) >= max(seg_dur * 2.5, 1.5)
                            for u in used):
                    used.append(start_sec)
                    return round(start_sec, 2)
            # 高光池耗尽: 回退贪心分散取点 (旧逻辑), 不固定取 pool[0]
            # (v23e 实测: fallback 固定 pool[0] 导致成品.mp4 22镜全在2.0s)
        usable = max(src_dur - seg_dur, 0)
        if usable <= 0:
            return 0.0
        ratio_map = {
            "intro": 0.0,
            "build": 0.15,
            "drop": 0.3,
            "climax": 0.5,
            "break": 0.7,
            "outro": 0.85,
        }
        base = ratio_map.get(mood, 0.3)
        # 候选点: 情绪基准 ± 周边 + 均匀网格覆盖全区间
        cands = sorted({min(max(base + k * 0.125, 0.0), 1.0) for k in range(-2, 7)})
        cands += [i / 8.0 for i in range(9)]
        cands = sorted(set(cands))
        # 修复: 剔除已用窗口附近候选 (>=0.8s), 避免选中已用点导致视觉重复
        cands = [c * usable for c in cands
                 if all(abs(c * usable - u) >= 0.8 for u in used)]
        if not cands:
            # 全部候选都近已用点: 取"距已用点最远"的候选(保底, 不固定0.0)
            _grid = sorted({c * usable for c in sorted({i / 8.0 for i in range(9)})})
            cands = [max(_grid, key=lambda s: min((abs(s - u) for u in used),
                                                  default=float("inf")))]
        best, best_d = cands[0], -1.0
        for s in cands:
            d = min((abs(s - u) for u in used), default=float("inf"))
            if d > best_d:
                best_d, best = d, s
        used.append(best)
        return round(best, 2)

    # ================================================================
    #  高光段池 (v22 内容感知选材)
    # ================================================================

    def _pick_by_narrative_role(self, role: str, available_sources: List[str],
                                seg_idx: int) -> Optional[str]:
        """按叙事角色选素材 — 用语义窗口缓存匹配 (Stage2 核心)。

        叙事角色 → 偏好情绪: 铺垫=calm/dark/quiet, 蓄力=intense/bright/epic,
        爆发=battle/intense/action, 收尾=calm/sad/melancholy。
        对每个候选素材看其语义窗口的主导 mood, 匹配角色偏好则入选。
        修复(2026-08-13): 之前永远返回最高分素材, 导致同角色内 22镜全同素材
        (蓄力段全初音)单调。改为: 返回"匹配池", 按 seg_idx 轮转。
        修复(2026-08-15): 主导标签门控过严 — v6 爆发段池坍缩为单一素材
        (独自升级5 独占101镜)。改为: 主导命中 OR ≥20%窗口命中 均入选;
        池内按使用计数均衡轮转 (最少使用优先, 平手按 seg_idx 错开)。
        返回 None → 调用方均衡轮转兜底。
        """
        _role_pref = {
            "铺垫": ("calm", "dark", "quiet", "sad", "neutral", "romantic"),
            "蓄力": ("intense", "bright", "epic", "tense", "neutral"),
            "爆发": ("battle", "intense", "action", "epic", "fighting"),
            "收尾": ("calm", "sad", "melancholy", "quiet", "dark"),
        }
        _pref = _role_pref.get(role)
        if not _pref:
            return None
        # 打分: 素材的主导 scene_type 匹配叙事角色 (精确, 替代泛化 mood)。
        # 修复(2026-08-13): mood=intense 同时出现在蓄力/爆发, 无法区分;
        # scene_type 精确: 爆发=battle/fighting, 铺垫=landscape/closeup/dialogue,
        # 蓄力=action(不含battle), 收尾=landscape/dialogue/indoor。
        _role_scene = {
            "铺垫": ("landscape", "closeup", "indoor", "dialogue"),
            "蓄力": ("action", "closeup", "landscape"),
            "爆发": ("battle", "fighting"),
            "收尾": ("landscape", "closeup", "dialogue", "indoor"),
        }
        _scene_pref = _role_scene.get(role, ())
        from collections import Counter as _Cnt
        _matched = []
        for _src in available_sources:
            _wins = self._get_semantic_windows(_src)
            if not _wins:
                continue
            _tags = [str(t).split("/")[0].strip() for _, t in _wins]
            if not _tags:
                continue
            _tag_cnt = _Cnt(_tags)
            _dominant = _tag_cnt.most_common(1)[0][0]
            # 精确匹配: 主导 scene 落在角色偏好集内;
            # 2026-08-15 放宽: 主导不中但偏好场景窗口占比>=20% 也入选
            # (修复爆发段池坍缩 — 独自升级2/五条悟 的 battle 窗口被
            #  closeup/indoor 主导标签遮蔽)
            _hit = sum(v for k, v in _tag_cnt.items() if k in _scene_pref)
            if _dominant in _scene_pref or _hit / max(len(_tags), 1) >= 0.2:
                _matched.append(_src)
        if not _matched:
            return None
        # 画像深化 (2026-08-14): 统一画像 (content/atmosphere) 参与角色排序 —
        # 角色氛围命中的素材前置, 教程录屏 (not_painting) 垫底。
        try:
            _profile = getattr(self, "_material_profile", None)
            if _profile is None:
                _profile = self._load_atmosphere_annotations()
                self._material_profile = _profile
            _role_atmo = {
                "爆发": ("燃向", "战斗"),
                "蓄力": ("燃向",),
                "铺垫": ("抒情", "治愈", "日常"),
                "收尾": ("抒情", "治愈"),
            }
            _pref_atmo = _role_atmo.get(role, ())

            def _profile_rank(_src: str) -> int:
                _p = _profile.get(Path(_src).name) or {}
                if _p.get("content") == "not_painting":
                    return 2
                if _p.get("atmosphere") in _pref_atmo:
                    return 0
                return 1

            _matched.sort(key=_profile_rank)
        except Exception:  # noqa: BLE001
            pass
        # 2026-08-15: 容量加权均衡 — 长素材多承担/短素材少承担,
        # 修复"爆发段 101 镜全同一素材"与短素材过载双重重复。
        _caps = {s: self._source_durations.get(s, 60.0) for s in _matched}
        return self._balanced_pick(_matched, seg_idx, capacities=_caps)

    def _balanced_pick(self, pool: List[str], seg_idx: int,
                       capacities: Optional[Dict[str, float]] = None) -> str:
        """素材均衡选择: 按"使用占比/容量"最低优先 (确定性)。

        2026-08-15: 纯计数均衡让 53s 短素材与 232s 长素材同频使用,
        短素材内部取点密度过高 → 视觉重复 (v7: 五条悟 43 镜/53s)。
        改为按素材时长加权: 长素材多承担, 短素材少承担; 平手按
        seg_idx 错开。
        """
        if not pool:
            return ""
        if len(pool) == 1:
            return pool[0]
        _caps = capacities or {s: 1.0 for s in pool}

        def _ratio(s: str) -> float:
            _c = max(float(_caps.get(s, 1.0)), 1e-6)
            return self._source_use_count.get(s, 0) / _c

        _min_r = min(_ratio(s) for s in pool)
        _tie = sorted(s for s in pool if _ratio(s) <= _min_r + 1e-9)
        return _tie[seg_idx % len(_tie)]

    def _get_semantic_windows(self, source_key: str) -> Optional[List[Tuple[float, str]]]:
        """懒加载素材的语义窗口池 [(start_sec, scene_tag), ...] — Qwen3-VL 分析。

        2026-08-13 Stage2: 叙事角色匹配素材语义。把素材按时间窗口抽帧,
        用 Qwen3-VL 分析 scene, 存磁盘缓存 (cache/semantic_windows/)。
        v3 细化: 窗口 8s→3s (爆发段 battle/closeup 精确区分, 旧 8s
        窗口把"混战全景+角色特写"混为一个 battle 标签, 取点落特写帧),
        版本号入文件名避免旧粗粒度缓存被误用。失败返回 None → 回退高光池。
        v4 细化 (用户 2026-08-14): 窗口抽帧 count 2→1 且只抽中部单帧
        (50%处)。v3 抽 25%/75% 两帧给 VLM 判一个标签 → 标签可能由 75% 帧
        驱动, 但取点回 +0.75s(25%帧) → 渲染帧≠被判定帧, 爆发段取到
        closeup intro (实测 2026-08-14 narrative_verification 0.625)。
        v4 只抽中帧 → 标签=该帧内容, 取点 +1.5s 恰好命中被判定帧。
        """
        try:
            import hashlib, json as _json
            if not source_key or not os.path.exists(source_key):
                return None
            if self._semantic_windows is None:
                self._semantic_windows = {}
            if source_key in self._semantic_windows:
                return self._semantic_windows[source_key]
            _h = hashlib.md5(os.path.abspath(source_key).encode()).hexdigest()[:12]
            _cache_dir = os.path.join(str(_PROJECT_ROOT), "cache", "semantic_windows")
            _cache = os.path.join(_cache_dir, f"{_h}_v4_3s.json")
            if os.path.exists(_cache):
                with open(_cache, encoding="utf-8") as _f:
                    self._semantic_windows[source_key] = [
                        (float(s), str(m)) for s, m in _json.load(_f)]
                return self._semantic_windows[source_key]
            # 无缓存: 按 3s 时间窗口抽帧, 用 Qwen3-VL(_vlm_analyze) 逐窗口分析
            from ai.material_intelligence import MaterialIntelligenceEngine
            _eng = MaterialIntelligenceEngine()
            _d = self._source_durations.get(source_key, 60.0)
            _win = 3
            _windows = []
            for _ws in range(0, max(1, int(_d)), _win):
                try:
                    # v4: count=1 只抽窗口中部单帧(50%), 标签=该帧内容,
                    # 与 _calc_source_start 的 +1.5s 取点精确对齐
                    _b64 = _eng.extract_frames_window_b64(
                        source_key, start_sec=_ws, end_sec=min(_ws + _win, _d),
                        count=1)
                    if not _b64:
                        _mood = "neutral"
                    else:
                        _res, _ = _eng._vlm_analyze(_b64, source_key)
                        # 存 "scene:action" 复合标签, 爆发段用 scene 精确区分
                        # (mood 太泛: intense 同时出现在蓄力/爆发, scene=battle
                        #  才能精确判定爆发)
                        _mood = str(_res.get("scene_type", "neutral"))
                except Exception:
                    _mood = "neutral"
                _windows.append((float(_ws), str(_mood)))
            os.makedirs(_cache_dir, exist_ok=True)
            with open(_cache, "w", encoding="utf-8") as _f:
                _json.dump(_windows, _f, ensure_ascii=False)
            self._semantic_windows[source_key] = _windows
            print(f"  语义窗口(Qwen3-VL): {os.path.basename(source_key)} "
                  f"{len(_windows)}段 {[(round(s), m) for s, m in _windows[:4]]}...")
            return _windows
        except Exception as _e:
            print(f"  [WARN] 语义窗口失败(回退高光池): {_e}")
            return None

    def _get_highlight_pool(self, source_key: str) -> Optional[List[Tuple[float, float]]]:
        """懒加载某素材的高光段池 [(start_sec, total_score), ...] 按total降序。

        复用 HighlightScorer 磁盘缓存 (v22 已生成 cache/highlight_scores/),
        无缓存/不可用返回 None → 调用方回退均匀分散。
        """
        try:
            if not source_key or not os.path.exists(source_key):
                return None
            if self._highlight_pool is None:
                self._highlight_pool = {}
                from core.highlight_scorer import HighlightScorer
                scorer = HighlightScorer(
                    sample_fps=6, resize=(256, 144), cache_enabled=True,
                    disk_cache_dir=os.path.join(
                        _PROJECT_ROOT, "cache", "highlight_scores"))
                src = list(self._source_durations.keys())
                for sp in src:
                    try:
                        segs = scorer.load_disk_cache(sp, segment_duration=2.0)
                        if segs:
                            self._highlight_pool[sp] = sorted(
                                [(s.start_sec, float(s.total)) for s in segs],
                                key=lambda x: x[1], reverse=True)
                    except Exception:
                        continue
            return self._highlight_pool.get(source_key)
        except Exception:
            return None

    # ================================================================
    #  Phase 3: 渲染执行
    # ================================================================

    def _execute(self, script, resolution, fps, enable_ae_channel: bool = False):
        """执行渲染 — 变速裁剪素材 + xfade真转场合成（硬切兜底）

        enable_ae_channel: 高级运镜镜头(zoom_back/pulse)走 AE 贝塞尔缓动+运动模糊
        通道(v22 双通道架构), 其余走 FFmpeg。默认 False(纯 FFmpeg)。
        """
        import uuid

        run_dir = self.work_dir / f"run_{uuid.uuid4().hex[:8]}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # 0. 转场安全化 (2026-08-16 无预补偿重构):
        #    旧机制: clip_i 渲染时长 = d_i + t_{i+1} (逐镜预补偿), xfade 消耗 t;
        #    当 _xfade_chain 的 accum 守卫把 t 钳小, 预补偿 > 实际消耗 →
        #    时长泄漏 (v7c 实测: 164.2s 剧本 → 168.16s 成片, +3.96s)。
        #    新机制: 各 clip 精确渲染 d_i; 链内最后一个 clip 一次性渲染
        #    d_last + Σt(本链全部转场时长); xfade offset 递推 → 链输出
        #    恒等于 Σd_i, 数学上零泄漏。
        #    约束: 每个非cut转场 t_i ≤ min(d_{i-1}, d_i) - 0.1, 不满足降级cut。
        segs = script.segments
        group_heads = {0}

        def _compute_heads() -> set:
            heads = {0}
            _cl = 1
            for i, seg in enumerate(segs[1:], start=1):
                _n, _t = self._xfade_for(seg)
                if not _n or _cl >= XFADE_GROUP_SIZE:
                    heads.add(i)
                    _cl = 1
                else:
                    _cl += 1
            return heads

        def _demote(seg) -> None:
            seg.transition = "cut"
            if isinstance(seg.transition_params, dict):
                seg.transition_params.pop("type", None)
                seg.transition_params.pop("duration", None)

        # (a) 链头降级: 链头自身的非cut转场无同链前置片段可消耗
        group_heads = _compute_heads()
        for i in group_heads:
            if i > 0 and self._xfade_for(segs[i])[0]:
                _demote(segs[i])
        group_heads = _compute_heads()
        # (b) 逐转场钳制: t_i ≤ min(d_{i-1}, d_i) - 0.1
        for i in range(1, len(segs)):
            name, t = self._xfade_for(segs[i])
            if not name:
                continue
            _allowed = min(segs[i - 1].duration, segs[i].duration) - 0.1
            if _allowed < 0.1:
                _demote(segs[i])
            elif t > _allowed:
                params = segs[i].transition_params if isinstance(
                    segs[i].transition_params, dict) else {}
                params["type"] = params.get("type") or segs[i].transition
                params["duration"] = round(_allowed, 3)
                segs[i].transition_params = params

        # 链内最后一个 clip 的一次性补偿时长: Σt (本链全部转场)
        chain_last_extra: Dict[int, float] = {}
        _heads_sorted = sorted(group_heads)
        for _hi, _head in enumerate(_heads_sorted):
            _end = _heads_sorted[_hi + 1] if _hi + 1 < len(_heads_sorted) else len(segs)
            _chain = list(range(_head, _end))
            _extra = 0.0
            for _j in _chain[1:]:
                _n2, _t2 = self._xfade_for(segs[_j])
                if _n2:
                    _extra += _t2
            if _extra > 0:
                # 帧量化: 补偿时长对齐整帧, 与 _extract_clip 的帧量化一致
                _fg2 = getattr(self, "_render_fps", 24) or 24
                _extra = round(_extra * _fg2) / _fg2
                chain_last_extra[_chain[-1]] = _extra

        _n_active = sum(1 for s in segs if self._xfade_for(s)[0])
        print(f"    转场安全化: {_n_active}处生效转场, {len(group_heads)}条链")

        # 1. 裁剪（含预补偿：渲染时长 = 段落时长 + 进入下一段的转场时长）
        #    预补偿基于安全化后的最终分组: 仅当 i+1 与 i 同链时才加长
        clips: List[Tuple[str, DirectorSegment]] = []

        # 1.5 AE高级运镜通道: 识别 zoom_back/pulse 镜头, 批量 AE 预渲染
        # (v22 双通道架构: AE 贝塞尔缓动+运动模糊 替代 FFmpeg 匀速 zoompan)
        ae_clips_map: Dict[int, str] = {}
        if enable_ae_channel:
            from ai.ae_render_channel import AERenderChannel, AE_TECHS
            _ae_plan = {}
            for _i, _seg in enumerate(segs):
                _zp = getattr(_seg, 'zoompan_effect', None)
                _onsets = getattr(_seg, 'onset_times', None) or []
                if _zp not in AE_TECHS:
                    continue
                # 运镜技巧决策: 撞击镜头(push/zoom_in)且带 onset 才走 pulse,
                # 与 ffmpeg 通道一致 — static/pan 等不再被鼓点脉冲覆盖
                # (2026-08-15 根因修复)。
                _tech = "pulse" if (_onsets and _zp in ("push", "zoom_in")) else _zp
                # 无预补偿: 链内最后镜头一次性补偿本链转场时长
                _render_dur = _seg.duration + chain_last_extra.get(_i, 0.0)
                _preset = self._color_presets.get(_seg.color_grade,
                                                  self._color_presets["climax"])
                _ae_plan[_seg.index] = {
                    "source": _seg.source_file,
                    "source_start": _seg.source_start,
                    "render_dur": _render_dur,
                    "speed": _seg.speed,
                    "tech": _tech,
                    "onsets": _onsets,
                    "fps": fps,
                    "resolution": resolution,
                    "color": dict(_preset),
                }
            if _ae_plan:
                print(f"  [AE通道] {len(_ae_plan)}个高级运镜镜头 → AE贝塞尔缓动+运动模糊")
                _chan = AERenderChannel(str(self._output_dir), str(_PROJECT_ROOT))
                ae_clips_map = _chan.build_and_render(
                    _ae_plan, fps,
                    on_fail_reason=lambda e: print(f"    [AE-FALLBACK] {e} → ffmpeg通道"))
                if ae_clips_map:
                    print(f"  [AE通道] 成功渲染 {len(ae_clips_map)}/{len(_ae_plan)} 镜头")

        for i, seg in enumerate(segs):
            if not Path(seg.source_file).exists():
                print(f"    [WARN] 素材不存在: {seg.source_file}")
                continue

            # 无预补偿渲染: 各 clip 精确 d_i; 链内最后 clip 一次性
            # 补偿本链全部转场时长 (2026-08-16 零泄漏重构)
            render_dur = seg.duration + chain_last_extra.get(i, 0.0)

            clip_path = run_dir / f"clip_{seg.index:03d}.mp4"
            preset = self._color_presets.get(seg.color_grade, self._color_presets["climax"])

            # AE 通道优先: 高级运镜镜头直接用 AE 预渲染产物 (贝塞尔+运动模糊)
            _ae_path = ae_clips_map.get(seg.index)
            if _ae_path and Path(_ae_path).exists():
                shutil.copy(_ae_path, str(clip_path))
                ok = clip_path.exists() and clip_path.stat().st_size > 0
            else:
                ok = self._extract_clip(
                    source=seg.source_file,
                    output=str(clip_path),
                    start_time=seg.source_start,
                    duration=render_dur,
                    resolution=resolution,
                    fps=fps,
                    color=preset,
                    speed=seg.speed,
                    lut_path=getattr(self, '_lut_path', None),
                    zoompan_effect=getattr(seg, 'zoompan_effect', None),
                    onset_times=getattr(seg, 'onset_times', None),
                )
            if ok and clip_path.exists() and clip_path.stat().st_size > 0:
                clips.append((str(clip_path), seg))

        if not clips:
            raise RuntimeError("所有素材裁剪失败，无法生成视频")

        print(f"  [3.2] 合成 {len(clips)} 个片段（xfade真转场）...")
        concat_output = run_dir / "concatenated.mp4"

        if len(clips) == 1:
            shutil.copy(clips[0][0], str(concat_output))
            return str(concat_output)

        # 2. 按转场边界分组：cut 转场处分链，非cut链内 xfade，链超上限再强切
        groups = self._group_for_transitions(clips)
        group_outputs: List[str] = []
        for gi, group in enumerate(groups):
            g_out = run_dir / f"group_{gi:02d}.mp4"
            if len(group) == 1:
                shutil.copy(group[0][0], str(g_out))
                group_outputs.append(str(g_out))
            elif self._xfade_chain(group, str(g_out)):
                group_outputs.append(str(g_out))
            else:
                # 单链失败降级：组内硬切拼接
                print(f"    [WARN] xfade链#{gi} 失败，组内降级硬切")
                if self._concat_hard([c[0] for c in group], str(g_out)):
                    group_outputs.append(str(g_out))

        if not group_outputs:
            raise RuntimeError("所有片段合成失败，无法生成视频")

        # 3. 组间硬切拼接（段落边界硬切 = 漫剪惯例）
        if len(group_outputs) == 1:
            shutil.copy(group_outputs[0], str(concat_output))
        elif not self._concat_hard(group_outputs, str(concat_output)):
            print(f"    [WARN] 组间拼接失败，使用首片段")
            shutil.copy(group_outputs[0], str(concat_output))

        n_xfade = sum(1 for _, seg in clips[1:] if self._xfade_for(seg)[1] > 0)
        print(f"      生效转场: {n_xfade} 处, 链数: {len(group_outputs)}")

        # 3.5 磁盘治理 (2026-08-16): 片段/链中间产物清理 —
        # 每次渲染留 3-5GB 中间文件, 58 次运行堆满 C 盘 (No space left
        # on device 直接击穿渲染)。合成完成后立即删除 clip_*/group_*,
        # 仅保留 concatenated.mp4 供混音消费。
        try:
            for _p in run_dir.glob("clip_*.mp4"):
                _p.unlink(missing_ok=True)
            for _p in run_dir.glob("group_*.mp4"):
                _p.unlink(missing_ok=True)
            for _p in run_dir.glob("concat_*.txt"):
                _p.unlink(missing_ok=True)
        except Exception as _clean_e:  # noqa: BLE001
            print(f"    [WARN] 中间产物清理失败(不影响交付): {_clean_e}")

        return str(concat_output)

    def _xfade_for(self, seg) -> Tuple[str, float]:
        """进入该段落的转场 → (xfade滤镜名, 时长秒)；cut 返回 ('', 0)"""
        params = seg.transition_params if isinstance(seg.transition_params, dict) else {}
        tag = str(params.get("type") or getattr(seg, "transition", "cut") or "cut")
        if os.environ.get("V23_FORCE_CUT") == "1":
            return None, 0.0
        # 变速镜头强制硬切 (2026-08-12): 变速(setpts)与 xfade 预补偿叠加会
        # 引入渲染漂移(实测变速版98%切点滞后)。变速镜头用硬切隔离,
        # 避免漂移经 xfade 链累积传播; 转场只用于原速镜头之间。
        if getattr(seg, "speed", 1.0) != 1.0:
            return "", 0.0
        if tag == "cut" or tag not in XFADE_MAP:
            return "", 0.0
        name, default_dur = XFADE_MAP[tag]
        dur = float(params.get("duration", default_dur))
        # 帧量化 (2026-08-16): xfade 内部按帧取整, 转场时长对齐整帧,
        # 与 clip 帧量化一致, 消除逐链 (t'-t) 累积漂移
        _fg = getattr(self, "_render_fps", 24) or 24
        dur = round(dur * _fg) / _fg
        return name, max(1 / _fg, min(dur, 0.5))

    def _group_for_transitions(self, clips):
        """按转场边界分组：cut 转场处断开新链，链长超 XFADE_GROUP_SIZE 强切"""
        groups = []
        current = [clips[0]]
        for path, seg in clips[1:]:
            name, _t = self._xfade_for(seg)
            if not name or len(current) >= XFADE_GROUP_SIZE:
                groups.append(current)
                current = [(path, seg)]
            else:
                current.append((path, seg))
        if current:
            groups.append(current)
        return groups

    def _xfade_chain(self, group, output) -> bool:
        """xfade 链式合成一组片段。offset 基于实际 probe 时长递推：
        accum_0 = dur_0; offset_i = accum_{i-1} - t_i; accum_i = accum_{i-1} + dur_i - t_i
        （片段时长已经帧网格吸附+输出级-t硬裁保证整帧精确,
        probe 递推可自动补偿残余偏差, 不会丢时间）

        2026-08-16 无预补偿重构: 链内最后 clip 已含 Σt 补偿, 数学上
        链输出 = Σd_i; 不再需要 accum 守卫钳制 t (安全化已保证
        t_i ≤ min(d_{i-1}, d_i) - 0.1, 归纳法可证 offset 恒非负)。
        """
        inputs = []
        durs = []
        for path, _seg in group:
            inputs.extend(["-i", path])
            durs.append(self._probe_duration(path))

        filters = []
        prev = "0:v"
        accum = durs[0]
        for i in range(1, len(group)):
            name, t = self._xfade_for(group[i][1])
            if not name:
                return False  # 不应发生（分组已保证链内非cut）
            offset = max(0.0, accum - t)
            out_label = "v" if i == len(group) - 1 else f"xf{i}"
            filters.append(
                f"[{prev}][{i}:v]xfade=transition={name}:duration={t:.2f}:offset={offset:.3f}[{out_label}]"
            )
            accum = accum + durs[i] - t
            prev = out_label

        cmd = [self.ffmpeg, "-y"] + inputs + [
            "-filter_complex", ";".join(filters),
            "-map", f"[{prev}]",
            "-c:v", "libx264", "-preset", "slow",
            "-b:v", "50M", "-maxrate", "60M", "-bufsize", "100M",
            "-minrate", "40M",
            "-pix_fmt", "yuv420p", "-an",
            "-movflags", "+faststart",
            output,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                               encoding="utf-8", errors="ignore")
            if r.returncode != 0:
                print(f"    [WARN] xfade滤镜报错: {(r.stderr or '')[:200]}")
                return False
            return Path(output).exists() and Path(output).stat().st_size > 0
        except subprocess.TimeoutExpired:
            print(f"    [WARN] xfade链合成超时")
            return False

    def _concat_hard(self, clip_paths, output) -> bool:
        """硬切 concat 拼接（基线路径，也是 xfade 的兜底）

        2026-08-14 修复: 此前用 libx264 preset slow 重编码整片 + 600s 超时,
        229 组长片 (165s) 在机器负载高时超时 → 回退首片段 (13.5s 截断 bug)。
        改为: 优先 -c:v copy 流拷贝 (各组同编码参数, 秒级完成);
        失败 (混合编码) 再回退重编码。
        """
        concat_file = Path(output).parent / f"concat_{Path(output).stem}.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for c in clip_paths:
                # FFmpeg concat 需要单引号包裹路径
                safe_path = c.replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        # 1) 流拷贝 (同参数 H.264 片段直接拼接)
        cmd_copy = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "copy", "-an",
            "-movflags", "+faststart",
            output,
        ]
        try:
            r = subprocess.run(cmd_copy, capture_output=True, text=True, timeout=600)
            if r.returncode == 0 and Path(output).exists() \
                    and Path(output).stat().st_size > 0:
                return True
        except subprocess.TimeoutExpired:
            pass

        # 2) 回退: 重编码 (混合编码/流拷贝失败时)
        cmd = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264", "-preset", "slow",
            "-b:v", "50M", "-maxrate", "60M", "-bufsize", "100M",
            "-minrate", "40M",
            "-pix_fmt", "yuv420p", "-an",
            "-movflags", "+faststart",
            output,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if r.returncode != 0 or not Path(output).exists() or Path(output).stat().st_size == 0:
                return False
            return True
        except subprocess.TimeoutExpired:
            return False

    def _extract_clip(self, source, output, start_time, duration, resolution, fps, color,
                      speed: float = 1.0, lut_path: str = None, zoompan_effect: str = None,
                      onset_times: list = None):
        """裁剪单个素材段，返回是否成功

        Args:
            duration: 目标输出时长（变速后仍保证输出≈duration）
            speed: 播放速度。>1加速 <1慢放。
                   换算：读取 read_dur = duration * speed 的素材区间，
                   再用 setpts=PTS/{speed} 拉伸到 duration。
                   慢放(0.5x): 读0.5倍素材→拉伸到2倍时长; 加速(2x): 读2倍素材→压缩到0.5倍时长
            lut_path: 可选 .cube LUT 路径，用于 lut3d 调色（突破 eq 饱和度上限）
        """
        src_dur = self._source_durations.get(source, 60.0)

        # 边界保护
        if start_time < 0:
            start_time = 0
        if start_time >= src_dur:
            start_time = 0
        if duration <= 0:
            duration = 2.0

        # 帧量化 (2026-08-16 根因修复): ffmpeg -t 按帧向上取整, 每 clip
        # 多 ≤1 帧 → 229 clip 累积 +3.9s (v7 实测 164.2→168.1)。
        # duration 四舍五入到整帧, 输出严格 = round(duration*fps) 帧。
        _frames = max(1, int(round(duration * fps)))
        duration = _frames / fps

        speed = max(0.25, min(4.0, float(speed or 1.0)))
        read_dur = duration * speed
        # 不要超出素材末尾
        if start_time + read_dur > src_dur:
            start_time = max(0, src_dur - read_dur)

        w, h = resolution
        sat = color.get("saturation", 1.2)
        con = color.get("contrast", 1.05)
        bri = color.get("brightness", 0.0)

        # 调色：LUT 优先（突破 eq 饱和度上限），否则回退 eq
        if lut_path and Path(lut_path).exists():
            # lut3d 处理饱和度，eq 仅保留 contrast/brightness 微调
            # Windows路径需要正斜杠+转义特殊字符给ffmpeg滤镜图
            _lut_safe = str(Path(lut_path)).replace("\\", "/").replace(":", "\\:")
            vf_parts = [
                f"scale={w}:{h}",
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black",
                f"lut3d='{_lut_safe}'",
                f"eq=contrast={con}:brightness={bri}",
            ]
        else:
            vf_parts = [
                f"scale={w}:{h}",
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black",
                f"eq=saturation={sat}:contrast={con}:brightness={bri}",
            ]
        if abs(speed - 1.0) > 0.01:
            # setpts 置于调色之后：先处理画面再改时间轴
            # PTS/speed: speed<1→拉伸PTS(慢放), speed>1→压缩PTS(加速)
            vf_parts.append(f"setpts=PTS/{speed:.4f}")
        # zoompan 运镜：onset 驱动脉冲 或 基础效果
        # (2026-08-15 根因修复): onset 逐拍"拉进-闪回"只允许作用于
        # 剧本显式派发的撞击镜头(push/zoom_in) — 此前该分支优先级高于
        # static, 导致 173 个静态镜头全被鼓点推拉覆盖 (用户"每个镜头
        # 都晃动推拉闪回"的真实原因)。static/pan/diag/zoom_back 不再被覆盖。
        if onset_times and len(onset_times) > 0 and \
                zoompan_effect in ("push", "zoom_in"):
            # === Onset 驱动"拉进-闪回"撞击运镜 ===
            # 每个鼓点做一次完整撞击: 拉进(快速冲近) + 闪回(快速弹回),
            # 冲击力来自"快起快回", 而非单调推拉/交替阶梯。
            # (用户 2026-08-14: "先拉进后闪回, 有视觉冲击力, 踩鼓点节拍")
            _zp_fps = fps
            _zp_w, _zp_h = w, h
            # 将 onset 时间转换为帧号 (zoompan 处理输出帧, 直接用 ot*fps)
            onset_frames = sorted(set(
                max(0, int(round(ot * fps))) for ot in onset_times))
            # 密集连击合并: <0.17s(4帧) 的合并, 避免 punch 重叠成糊
            _min_gap = 4
            _filtered = []
            for _f in onset_frames:
                if not _filtered or _f - _filtered[-1] >= _min_gap:
                    _filtered.append(_f)
            onset_frames = _filtered
            # v23.1 双鼓点对编排 (用户 2026-08-14):
            # "第一个镜头有两个跳动鼓点, 第一个鼓点推进, 第二个鼓点拉回"
            # 镜头内恰好 2 个鼓点(间隔≥3帧) → 单峰曲线:
            #   1.0 →(h1, easeIn 4帧)→ 峰值保持 →(h2, easeOut 6帧)→ 1.0
            # 推进是"冲上去", 拉回是"弹回来", 视觉是一推一拉卡双鼓点。
            # 其余(1个或≥3个鼓点)保持逐鼓点"拉进-闪回"。
            if len(onset_frames) == 2 and \
                    onset_frames[1] - onset_frames[0] >= 3:
                _f1, _f2 = onset_frames
                _pk, _at, _rl = 0.12, 4, 6
                _z_pair = (
                    f"if(lt(on,{_f1}),1.0,"
                    f"if(lt(on,{_f1+_at}),"
                    f"1.0+{_pk}*((on-{_f1})/{_at})*((on-{_f1})/{_at}),"
                    f"if(lt(on,{_f2}),1.0+{_pk},"
                    f"if(lt(on,{_f2+_rl}),"
                    f"1.0+{_pk}*(1-(on-{_f2})/{_rl})*(1-(on-{_f2})/{_rl}),1.0))))"
                )
                z_final = f"min({_z_pair},1.15)"
                _zp = (f"zoompan=z='{z_final}'"
                       f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                       f":d=1:s={_zp_w}x{_zp_h}:fps={_zp_fps}")
                vf_parts.append(_zp)
            else:
                # 每个鼓点: 拉进(3帧 0→peak 二次加速=冲) + 闪回(8帧 peak→0 easeOut=弹)
                _peak = 0.12
                _attack = 3
                _release = 8
                _z = "1.0"
                for _fi in onset_frames:
                    _p = (
                        f"if(between(on,{_fi},{_fi+_attack}),"
                        f"{_peak}*((on-{_fi})/{_attack})*((on-{_fi})/{_attack}),"
                        f"if(between(on,{_fi+_attack},{_fi+_attack+_release}),"
                        f"{_peak}*(1-(on-{_fi}-{_attack})/{_release})"
                        f"*(1-(on-{_fi}-{_attack})/{_release}),0))"
                    )
                    _z = f"max({_z},1.0+({_p}))"
                z_final = f"min({_z},1.15)"
                _zp = (f"zoompan=z='{z_final}'"
                       f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                       f":d=1:s={_zp_w}x{_zp_h}:fps={_zp_fps}")
                vf_parts.append(_zp)
        elif zoompan_effect:
            _zp_fps = fps  # zoompan fps 必须用字面数字
            _zp_w, _zp_h = w, h
            # 幅度克制 (2026-08-14 用户二次反馈): 大幅推拉/快速摇移=晃眼,
            # 幅度统一收敛到 1.06-1.15 倍、平移速度减半以下
            if zoompan_effect == "zoom_in":
                # easeOut 推近: 快起慢收(二次方缓动), 幅度 1.12 封顶
                _zi_n = max(int(duration * _zp_fps), 1)
                _zi_z = (f"min(1.12,1.0+0.12*(2*(on/{_zi_n})-(on/{_zi_n})*(on/{_zi_n})))")
                _zp = f"zoompan=z='{_zi_z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={_zp_w}x{_zp_h}:fps={_zp_fps}"
            elif zoompan_effect == "zoom_back":
                # 两段式运动曲线(smoothstep缓动): 前半段推近至1.1x, 后半段拉回1.0x
                _mid = max(int(duration * _zp_fps / 2), 1)
                _zb_z = (
                    f"if(lt(on,{_mid}),"
                    f"1.0+0.1*(on/{_mid})*(on/{_mid})*(3-2*on/{_mid}),"
                    f"max(1.0,1.1-0.1*((on-{_mid})/{_mid})*((on-{_mid})/{_mid})"
                    f"*(3-2*(on-{_mid})/{_mid})))")
                _zp = f"zoompan=z='{_zb_z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={_zp_w}x{_zp_h}:fps={_zp_fps}"
            elif zoompan_effect == "zoom_out":
                _zp = f"zoompan=z='if(eq(on,1),1.15,max(1.0,on*0.998+0.002))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={_zp_w}x{_zp_h}:fps={_zp_fps}"
            elif zoompan_effect == "push":
                # 快推: easeIn 加速冲向落点(撞击感), 幅度 1.15 封顶
                _pu_n = max(int(duration * _zp_fps), 1)
                _pu_z = f"min(1.15,1.0+0.15*(on/{_pu_n})*(on/{_pu_n}))"
                _zp = f"zoompan=z='{_pu_z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={_zp_w}x{_zp_h}:fps={_zp_fps}"
            elif zoompan_effect == "pan_left":
                _zp = f"zoompan=z='1.06':x='iw/4-(iw/zoom/4)+on*0.22':y='ih/2-(ih/zoom/2)':d=1:s={_zp_w}x{_zp_h}:fps={_zp_fps}"
            elif zoompan_effect == "pan_right":
                _zp = f"zoompan=z='1.06':x='iw/4-(iw/zoom/4)-on*0.22':y='ih/2-(ih/zoom/2)':d=1:s={_zp_w}x{_zp_h}:fps={_zp_fps}"
            elif zoompan_effect == "diag_pan":
                _zp = f"zoompan=z='1.06':x='on*0.15':y='on*0.1':d=1:s={_zp_w}x{_zp_h}:fps={_zp_fps}"
            else:
                _zp = None
            if _zp:
                vf_parts.append(_zp)
        vf = ",".join(vf_parts)

        cmd = [
            self.ffmpeg, "-y",
            "-ss", f"{start_time:.3f}",
            "-t", f"{read_dur:.3f}",  # 输入级读取限制：变速后输出=read_dur/speed=duration
            "-i", source,
            "-vf", vf,
            "-r", str(fps),
            "-t", f"{duration:.4f}",  # 输出级硬裁: 保证帧数=round(duration*fps),
            #                             防止输入-t+setpts/帧量化的±1帧误差累积成切点漂移
            "-c:v", "libx264", "-preset", "slow",
            "-b:v", "50M", "-maxrate", "60M", "-bufsize", "100M",
            "-minrate", "40M",
            "-pix_fmt", "yuv420p", "-an",
            "-movflags", "+faststart",
            output,
        ]

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                               encoding="utf-8", errors="ignore")
            if r.returncode != 0:
                err = r.stderr[:300] if r.stderr else "unknown"
                print(f"    [WARN] 裁剪失败 ({Path(output).name}): {err}")
                return False
            return True
        except subprocess.TimeoutExpired:
            print(f"    [WARN] 裁剪超时: {Path(output).name}")
            return False

    # ================================================================
    #  Phase 4: 文字叠加
    # ================================================================

    def _overlay_text(self, input_video, script):
        """使用 PIL 渲染歌词 PNG + FFmpeg overlay 叠加"""
        from PIL import Image, ImageDraw, ImageFont

        # 收集文字叠加
        overlays = []
        for seg in script.segments:
            if seg.text_overlay:
                overlays.append({
                    "text": seg.text_overlay["lyric"],
                    "start": seg.text_overlay.get("start", seg.start_time),
                    "end": seg.text_overlay.get("end", seg.end_time),
                    "color": seg.text_overlay.get("color", "white"),
                    "mood": seg.text_overlay.get("mood", seg.mood),
                })

        if not overlays:
            return input_video

        # 渲染 PNG
        png_list = []
        for i, ov in enumerate(overlays):
            png_path = self.work_dir / f"lyric_{i:03d}.png"
            self._render_lyric_png(ov["text"], ov["color"], str(png_path))
            png_list.append((str(png_path), ov["start"], ov["end"]))

        # 限制最多8句避免滤镜链过长
        if len(png_list) > 8:
            png_list = png_list[:8]

        # 构建 FFmpeg overlay 滤镜链
        inputs = ["-i", input_video]
        filters = []
        prev_label = "0:v"

        for i, (png, start, end) in enumerate(png_list):
            inputs.extend(["-i", png])
            out_label = f"v{i}"
            start_t = max(0, start)
            end_t = max(start_t + 0.5, end)
            filters.append(
                f"[{i+1}:v]format=rgba[l{i}];"
                f"[{prev_label}][l{i}]overlay=enable='between(t,{start_t:.2f},{end_t:.2f})'[{out_label}]"
            )
            prev_label = out_label

        filter_complex = ";".join(filters)

        cmd = [self.ffmpeg, "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", f"[{prev_label}]",
            "-c:v", "libx264", "-preset", "slow",
            "-b:v", "50M", "-maxrate", "60M", "-bufsize", "100M",
            "-minrate", "40M",
            "-pix_fmt", "yuv420p", "-an",
            "-movflags", "+faststart",
            str(self.work_dir / "with_text.mp4"),
        ]

        text_output = str(self.work_dir / "with_text.mp4")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                               encoding="utf-8", errors="ignore")
            if r.returncode != 0:
                print(f"    [WARN] 文字叠加失败: {r.stderr[:200]}")
                return input_video
            if Path(text_output).exists() and Path(text_output).stat().st_size > 0:
                return text_output
        except subprocess.TimeoutExpired:
            print(f"    [WARN] 文字叠加超时")

        return input_video

    def _render_lyric_png(self, text, color, output_path, width=1920, height=1080):
        """渲染歌词为透明 PNG"""
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 字体
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 72)
        except Exception:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 72)
            except Exception:
                font = ImageFont.load_default()

        # 文字位置（底部居中偏上）
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (width - tw) // 2
        y = int(height * 0.75)

        # 颜色映射
        color_map = {
            "gold": (255, 215, 0),
            "cyan": (0, 255, 255),
            "red": (255, 50, 50),
            "orange": (255, 165, 0),
            "white": (255, 255, 255),
        }
        rgb = color_map.get(color, (255, 255, 255))

        # 光晕（8方向偏移）
        for dx in range(-6, 7, 3):
            for dy in range(-6, 7, 3):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), text, font=font,
                          fill=(rgb[0], rgb[1], rgb[2], 40))

        # 描边
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), text, font=font,
                          fill=(0, 0, 0, 200))

        # 主体
        draw.text((x, y), text, font=font, fill=(*rgb, 255))

        img.save(output_path)

    def _music_effective_end(self, bgm_path: str, fallback: float) -> float:
        """BGM 有效结束时间 — 剔除尾部静音 (2026-08-15 用户反馈"音频杂乱").

        DiorGoFlex_AllEyesOnMe_full.mp3 实测 163.0s 音乐结束, 其后 5.5s 为
        数字静音 → 成片尾段 5.5s 无声死气。检测尾部静音区并裁剪到音乐
        实际结束点; 无尾部静音则原时长。
        """
        try:
            _probe = subprocess.run(
                [self.ffmpeg, "-hide_banner", "-i", bgm_path,
                 "-af", "silencedetect=noise=-45dB:d=0.8", "-f", "null", "-"],
                capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="ignore")
            _silence_starts = re.findall(
                r"silence_start:\s*([\d.]+)", _probe.stderr or "")
            _silence_ends = re.findall(
                r"silence_end:\s*([\d.]+)", _probe.stderr or "")
            if _silence_starts and _silence_ends:
                _last_start = float(_silence_starts[-1])
                _last_end = float(_silence_ends[-1])
                # 尾部静音: 静音区延伸到文件末尾且长度 >=1.5s
                if abs(_last_end - fallback) < 0.8 and \
                        (_last_end - _last_start) >= 1.5:
                    _eff = round(_last_start, 2)
                    print(f"  [音频] 检测到尾部静音 {_last_start:.1f}-{_last_end:.1f}s "
                          f"→ 成片时长裁剪 {fallback:.1f}s → {_eff:.1f}s")
                    return _eff
        except Exception as _e:  # noqa: BLE001
            print(f"  [音频] 尾部静音检测跳过({_e})")
        return fallback

    # ================================================================
    #  Phase 5: BGM 混音
    # ================================================================

    def _mix_audio(self, video_path, bgm_path, output_path, bgm_start_sec, duration):
        """混合 BGM 到视频"""

        # 先检查视频是否有音频流
        has_audio = self._probe_has_audio(video_path)

        if has_audio:
            filter_complex = (
                f"[0:a]volume=0.3[orig];"
                f"[1:a]atrim=start={bgm_start_sec}:end={bgm_start_sec + duration},"
                f"asetpts=PTS-STARTPTS,volume=0.98[bgm];"
                f"[orig][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            cmd = [
                self.ffmpeg, "-y",
                "-i", video_path,
                "-ss", "0", "-i", bgm_path,
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                output_path,
            ]
        else:
            # 视频无音频，直接用 BGM
            # (2026-08-15) volume=0.98 (-0.2dB 余量): 该 BGM 峰值 0dB 砖墙
            # 削波, mp3→AAC 重编码会恶化采样间削波产生"杂音"听感
            cmd = [
                self.ffmpeg, "-y",
                "-i", video_path,
                "-ss", f"{bgm_start_sec}", "-i", bgm_path,
                "-map", "0:v", "-map", "1:a",
                "-af", "volume=0.98",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                "-shortest",
                output_path,
            ]

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                               encoding="utf-8", errors="ignore")
            if r.returncode != 0:
                err = r.stderr[:300] if r.stderr else ""
                print(f"    [WARN] 混音失败: {err}")
                # 降级：直接复制视频
                shutil.copy(video_path, output_path)
        except subprocess.TimeoutExpired:
            print(f"    [WARN] 混音超时")
            shutil.copy(video_path, output_path)

    # ================================================================
    #  Phase 6: 质量验证
    # ================================================================

    def _validate(self, output_path) -> RenderResult:
        """验证输出文件"""
        result = RenderResult(output_path=output_path, success=False)

        if not Path(output_path).exists():
            result.error_message = "输出文件不存在"
            return result

        cmd = [
            self.ffprobe, "-v", "error",
            "-show_entries", "format=duration,size:stream=width,height,r_frame_rate,codec_name,codec_type",
            "-of", "json", output_path,
        ]

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            info = json.loads(r.stdout)

            result.duration = float(info["format"]["duration"])
            result.file_size_mb = int(info["format"]["size"]) / 1024 / 1024

            for stream in info.get("streams", []):
                if stream.get("codec_type") == "audio":
                    result.has_audio = True
                if "width" in stream:
                    result.resolution = (stream["width"], stream["height"])
                    fps_str = stream.get("r_frame_rate", "24/1")
                    if "/" in fps_str:
                        num, den = fps_str.split("/")
                        result.fps = int(num) // int(den) if int(den) > 0 else 24

            result.success = True
        except Exception as e:
            result.error_message = str(e)

        return result

    # ================================================================
    #  生产审计报告
    # ================================================================

    def _load_atmosphere_annotations(self) -> Dict[str, Dict]:
        """加载 W6 氛围标注缓存 (ToriiGate 批量产物) → {文件名: 标注 dict}。

        优先数据源: data/material_tags/unified_tags.json (三源融合画像,
        round-7 起含 content/atmosphere/energy); 回退: 散落的
        data/atmosphere_annotations/*.json。缺失/损坏时返回空 dict,
        不阻断报告生成。
        """
        try:
            import json as _json
            _unified = _PROJECT_ROOT / "data" / "material_tags" / "unified_tags.json"
            if _unified.exists():
                data = _json.loads(_unified.read_text(encoding="utf-8"))
                tags = data.get("tags") or {}
                merged: Dict[str, Dict] = {}
                for name, val in tags.items():
                    if isinstance(val, dict):
                        merged[name] = {
                            "atmosphere": val.get("atmosphere"),
                            "energy": val.get("energy"),
                            "emotion": val.get("emotion"),
                            "scene_type": val.get("scene_type"),
                            "content": val.get("content"),
                        }
                return merged
            _anno_dir = _PROJECT_ROOT / "data" / "atmosphere_annotations"
            if not _anno_dir.is_dir():
                return {}
            merged = {}
            for f in sorted(_anno_dir.glob("*.json")):
                try:
                    data = _json.loads(f.read_text(encoding="utf-8"))
                except (OSError, _json.JSONDecodeError):
                    continue
                for name, val in (data.get("results") or {}).items():
                    if isinstance(val, dict):
                        merged[name] = val
            return merged
        except Exception:  # noqa: BLE001
            return {}

    def _critique_stage(self, stage: str, stage_summary: str, decisions: str,
                        goal: str) -> None:
        """TEMPO 式阶段自评: 调 StageCritic 估计当前阶段价值 (2026-08-16)。

        同步包装 async 调用; 任何异常静默 (自评是辅助信号, 绝不阻断渲染)。
        结果由 StageCritic 写入 tmp/run_notes.jsonl, 审计报告合并读取。
        """
        try:
            import asyncio
            from ai.stage_critic import StageCritic
            note = asyncio.run(StageCritic().critique(
                stage=stage, stage_summary=stage_summary,
                decisions=decisions, goal=goal))
            if note:
                print(f"  [自评] {stage}: value={note['value']}/10 — "
                      f"{note['rationale'][:60]}")
        except Exception:
            pass

    def _save_production_report(self, output_dir, script, target_ip, result):
        """保存生产审计报告 — 记录素材归属与复核结果，供交付追溯"""
        try:
            # W6 氛围标注 (ToriiGate 批量产物) 按文件名合并进 attribution
            _atmo = self._load_atmosphere_annotations()
            report = {
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "director_version": "v4-strict",
                "target_ip": target_ip,
                "output": result.output_path,
                "render_success": result.success,
                "content_verified": result.content_verified,
                "verification_reason": result.verification_reason,
                "material_selection": {
                    k: [Path(p).name for p in v]
                    for k, v in self._selection.items()
                },
                "material_attribution": {
                    Path(k).name: {
                        "primary_ip": v.primary_ip,
                        "is_mixed": v.is_mixed,
                        "content_kind": v.content_kind,
                        "confidence": v.ip_tags[0].confidence if v.ip_tags else 0,
                        "description": v.description[:120],
                        "atmosphere": (_atmo.get(Path(k).name) or {}).get("atmosphere"),
                        "energy": (_atmo.get(Path(k).name) or {}).get("energy"),
                        "content": (_atmo.get(Path(k).name) or {}).get("content"),
                    }
                    for k, v in self._intel_tags.items()
                },
                "segments": [
                    {
                        "index": s.index, "mood": s.mood,
                        "start": round(s.start_time, 2), "end": round(s.end_time, 2),
                        "source": Path(s.source_file).name,
                        "source_ip": self._intel_tags.get(s.source_file, MaterialIntelTag()).primary_ip,
                        "source_start": s.source_start,
                    }
                    for s in script.segments
                ],
                "script": script.to_dict(),
            }
            # T4: 品味契约审计
            from ai.taste_contract import check_anti_defaults
            seg_dicts = [
                {"transition": s.transition, "zoompan_effect": s.zoompan_effect}
                for s in script.segments
            ]
            violations = check_anti_defaults(seg_dicts, self.taste)
            report["taste_profile"] = {
                "visual_variance": self.taste.visual_variance,
                "motion_intensity": self.taste.motion_intensity,
                "information_density": self.taste.information_density,
                "design_read": self.taste.design_read,
                "anti_default_violations": violations,
            }
            # P0-2026-08-16: 五维 rubric + 原子检查 + 阶段自评 (TEMPO/LongTraceRL 借鉴)
            try:
                from core.atomic_checks import run_atomic_checks
                from core.render_rubric import compute_rubric
                from ai.stage_critic import StageCritic
                _ac = run_atomic_checks(
                    result.output_path,
                    expect={"width": result.resolution[0],
                            "height": result.resolution[1],
                            "fps": result.fps if hasattr(result, "fps") else None,
                            "duration_range": (max(1.0, script.total_duration * 0.8),
                                               script.total_duration * 1.2 + 5.0)},
                    render_success=result.success,
                    content_verified=result.content_verified,
                )
                _notes = StageCritic.load_notes()
                _rubric = compute_rubric(atomic_score=_ac.score)
                report["atomic_checks"] = _ac.to_dict()
                report["rubric"] = _rubric
                report["stage_self_critique"] = _notes
                print(f"  [验收] 原子检查 {_ac.score}/100, "
                      f"rubric={_rubric.get('grade', 'N/A')}")
            except Exception as _p0_e:  # noqa: BLE001
                print(f"  [WARN] rubric/原子检查计算失败(不阻断): {_p0_e}")
            report_path = Path(output_dir) / "production_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"  审计报告: {report_path}")
        except Exception as e:
            print(f"  [WARN] 审计报告保存失败: {e}")

    # ================================================================
    #  工具方法
    # ================================================================

    def _probe_duration(self, path) -> float:
        """探测文件时长"""
        cmd = [
            self.ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", path,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            info = json.loads(r.stdout)
            return float(info["format"]["duration"])
        except Exception:
            return 60.0

    def _probe_has_audio(self, path) -> bool:
        """检查文件是否有音频流"""
        cmd = [
            self.ffprobe, "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "json", path,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            info = json.loads(r.stdout)
            return len(info.get("streams", [])) > 0
        except Exception:
            return False


# ================================================================
#  CLI 入口
# ================================================================

def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="ProductionDirector — 生产级导演系统")
    parser.add_argument("--videos", required=True, help="视频素材路径，逗号分隔")
    parser.add_argument("--bgm", required=True, help="BGM 音频路径")
    parser.add_argument("--output", required=True, help="输出文件路径")
    parser.add_argument("--bgm-start", type=float, default=0.0, help="BGM 使用段落起始(秒)")
    parser.add_argument("--duration", type=float, default=None, help="目标时长(秒)")
    parser.add_argument("--fps", type=int, default=24, help="输出帧率")
    parser.add_argument("--target-ip", default="", help="目标IP/作品名 (如 '进击的巨人')")
    parser.add_argument("--no-strict", action="store_true",
                        help="关闭严格模式 (无匹配素材时降级到全部素材，不推荐)")
    parser.add_argument("--allow-mixed", action="store_true",
                        help="允许使用多IP混剪类素材")
    parser.add_argument("--no-verify", action="store_true",
                        help="跳过成片内容复核")

    args = parser.parse_args()

    video_sources = [v.strip() for v in args.videos.split(",") if v.strip()]
    output_dir = str(Path(args.output).parent)
    output_name = Path(args.output).name

    director = ProductionDirector()
    output = director.render(
        video_sources=video_sources,
        bgm_path=args.bgm,
        output_dir=output_dir,
        output_name=output_name,
        bgm_start_sec=args.bgm_start,
        target_duration=args.duration,
        fps=args.fps,
        target_ip=args.target_ip,
        strict=not args.no_strict,
        allow_mixed=args.allow_mixed,
        verify_content=not args.no_verify,
    )

    print(f"\n输出文件: {output}")


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
