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
        # 风格标识（用于规则适用域裁决；taste_profile 里带 style_id 时记录）
        self._style_id: Optional[str] = (
            (taste_profile or {}).get("style_id") if taste_profile else None
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
        self._highlight_pool_warned: bool = False  # 高光池失效只报一次(每选段都会调,防刷屏)
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
        clean_bgm_sfx: bool = False,
        beat_lock_hard_cuts: bool = False,
        cut_times_override: Optional[List[float]] = None,
    ) -> str:
        """端到端渲染。

        Args:
            clean_bgm_sfx: HPSS 激进清理 BGM 打击乐(鼓点压到 5%-20%)。
                2026-09-02 教训: 无条件清理会削掉鼓点瞬态——"卡点听感"的载体。
                只在确认 BGM 文件被 SFX 烘入污染时才开(一次性修复用);
                常规运行 False = 原始 BGM 直通。SFX 只进最终输出音轨
                (unified_edit 阶段④), 绝不进 BGM 文件。
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
            cut_times_override: 外部切点表（输出视频时间轴, 秒）。非空时跳过
                内部切点计算结果，按弧段区间重新分配该表（P2 切点自检 repair
                接线用, 2026-09-10）。弧段边界/能量结构/择优逻辑全部保持。
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
                                theme=theme,
                                cut_times_override=cut_times_override)

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
            # V23_KEEP_INTERMEDIATES=1 时跳过 rmtree (2026-09-10):
            # 后台沙箱批量删除熔断无TTY确认会判死, 保留供事后人工清理。
            try:
                _dw = Path(self.work_dir)
                if _dw.exists() and os.environ.get("V23_KEEP_INTERMEDIATES") != "1":
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
                                       enable_ae_channel=enable_ae_channel,
                                       beat_lock_hard_cuts=beat_lock_hard_cuts)

            # _execute 内的乐句克隆/重音强调 pass 会就地改写 speed 与
            # zoompan_effect, Phase2 落的 yaml 因此描述的是另一部片子
            # (run62: yaml 12.8s 后 51 镜全 1.55x, 实渲为 0.55/1.1/1.5 三档)。
            # 渲染后重写, 让可比对的剧本工件与实际交付一致。
            try:
                script.save_yaml(output_dir / "director_script.yaml")
            except Exception as _ys_e:  # noqa: BLE001
                print(f"  [WARN] 剧本YAML重写失败(不阻断): {_ys_e}")

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

            # Phase 5: BGM SFX 清理 + 混音
            # 2026-09-02: 改条件触发 — 默认直通原始 BGM (鼓点=卡点听感载体)。
            # 只有调用方显式确认 BGM 文件被污染时才 HPSS 清理。
            if clean_bgm_sfx:
                print("\n[Phase 5] BGM SFX 清理 (HPSS 激进模式)...")
                bgm_cleaned = self._clean_bgm_sfx(bgm_path, str(self.work_dir))
            else:
                print("\n[Phase 5] BGM 直通 (HPSS 清理关闭, 保留鼓点瞬态)")
                bgm_cleaned = bgm_path

            print("\n[Phase 5b] BGM 混音...")
            self._mix_audio(text_video, bgm_cleaned, str(output_path),
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
                    target_duration=target_duration,
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
        content=None, target_duration=None,
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
                # 从 RenderResult 已知信息推导初始质量基线，避免永远 0.0
                # — success(+40) + content_verified(+35) + duration合理性(+25)
                _base = 0.0
                if result.success:
                    _base += 40.0
                    if result.duration and result.duration > 0:
                        # duration 正常区间: 目标±30% → 满分25；越短越线性衰减
                        if target_duration and target_duration > 0:
                            _ratio = result.duration / target_duration
                            if 0.7 <= _ratio <= 1.3:
                                _base += 25.0
                            elif 0.4 <= _ratio <= 1.6:
                                _base += 15.0
                            else:
                                _base += 5.0
                        else:
                            _base += 20.0
                    if result.content_verified is True:
                        _base += 35.0
                    elif result.content_verified is None:
                        _base += 15.0
                    # False -> +0
                output_quality_initial = max(0.0, min(100.0, _base)) / 100.0

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
                        "target_duration": target_duration,
                    },
                    config={
                        "auto_captured": True,
                        "output_path": output_path,
                    },
                    output_path=output_path,
                    output_quality=output_quality_initial,
                    success=result.success,
                    total_duration=result.duration,
                    strategy_id="production_director",
                )

                loop = asyncio.new_event_loop()
                try:
                    review = loop.run_until_complete(
                        engine.post_execution_review(record)
                    )
                    # —— 关键修复：review 计算出 overall_score 后，回填 record.output_quality
                    #    否则日志里永远保留的是初始值，导致 causal_engine 看到的全是 0.0
                    try:
                        final_score = float(getattr(getattr(review, "quality", None), "overall_score", 0.0))
                        if 0.0 <= final_score <= 1.0:
                            record.output_quality = final_score
                        elif final_score > 1.0:
                            # 百分制 → 归一化
                            record.output_quality = final_score / 100.0
                    except (TypeError, ValueError):
                        pass
                    # 尝试显式持久化（兼容：如果 engine 提供 record.save）
                    try:
                        persist = getattr(record, "persist", None) or getattr(engine, "_persist_record", None)
                        if callable(persist):
                            persist(record)
                    except Exception:
                        pass
                    print(
                        f"[自进化] 自动采集完成: "
                        f"quality_init={output_quality_initial:.2f} → "
                        f"quality_final={record.output_quality:.2f}, "
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

        # 鼓点分型 (2026-09-03 用户语法: kick→推进, snare→拉远, hihat→快切)
        self._onset_types = {}
        self._onset_energy = {}
        try:
            import librosa as _lb4
            import numpy as _np5
            _yt, _srt = _lb4.load(bgm_path, sr=22050, mono=True)
            for _ot in self._onsets:
                _i0 = max(0, int((_ot - 0.02) * _srt))
                _i1 = min(len(_yt), int((_ot + 0.08) * _srt))
                if _i1 <= _i0:
                    continue
                _seg = _yt[_i0:_i1]
                _F = abs(_np5.fft.rfft(_seg))
                _fr = _np5.fft.rfftfreq(len(_seg), 1.0 / _srt)
                _lo = _F[(_fr >= 30) & (_fr < 160)].sum()
                _mid = _F[(_fr >= 160) & (_fr < 2000)].sum()
                _hi = _F[(_fr >= 2000)].sum()
                _m = max(_lo, _mid, _hi)
                self._onset_types[round(float(_ot), 3)] = (
                    "kick" if (_m == _lo or _lo >= 0.55 * _mid)
                    else ("snare" if _m == _mid else "hihat"))
                self._onset_energy[round(float(_ot), 3)] = float(_lo + _mid + _hi)
            _nt = {}
            for _v in self._onset_types.values():
                _nt[_v] = _nt.get(_v, 0) + 1
            print(f"  鼓点分型: {_nt}")
            # 律动层密度源 (2026-09-03 用户口径: 快/慢鼓=底鼓军鼓律动,
            # hi-hat 十六分音符全程铺满会把慢段也测成 6/s)
            # 2026-09-03 终修 30.75s+ 全慢镜: 鼓点实际存在(实测 5.8/s)但被
            # 全曲能量百分位误杀 — 该段弦乐垫底、鼓相对弱, 在全曲尺度排不进
            # 前40%。人耳听相对强度 → 改局部显著性: ±2s 窗内能量 ≥ 中位数
            # 90% 即入律动层。绝对阈值(全曲)会系统性误杀弱伴奏段。
            import numpy as _np6
            _oe = sorted(getattr(self, "_onset_energy", {}).items())
            _gt = _np6.array([float(k) for k, _ in _oe])
            _ge = _np6.array([e for _, e in _oe])
            _gset = {k for k, v in self._onset_types.items()
                     if v in ("kick", "snare")}
            for k, e in _oe:
                _sel = _ge[abs(_gt - float(k)) <= 2.0]
                _lm = float(_np6.median(_sel)) if len(_sel) else 0.0
                if e >= _lm * 0.9:
                    _gset.add(k)
            self._groove_onsets = sorted(float(g) for g in _gset)
            print(f"  律动层鼓点(kick+snare): {len(self._groove_onsets)} 个")
        except Exception as _ot_e:  # noqa: BLE001
            print(f"  鼓点分型跳过({_ot_e})")

        # ── E0-1 鼓点 stem 锚定 (2026-09-05): separate_drums.py 真值优先 ──
        # 频段启发式把 hihat/切分音也当切点候选（docs/漫剪跟音乐剪辑深度研究
        # 诊断的锚定粒度缺口）；stem 分离后 kick/snare 来自真实鼓轨，hihat
        # 天然不存在。anchors.json 缺席时保持原启发式（fail-safe）。
        # 环境开关 MASTER_NO_DRUM_ANCHORS=1 可强制关闭（A/B 对照组用）。
        self._drum_anchor_mode = False
        import os as _os_da
        # 规则库裁决（E1-1 消费闭环）: cut_anchor 规则退役/翻负 → 自动回退启发式。
        # 规则库未建立(data/rules/ruleset.jsonl 不存在) → None, 管线自便。
        # 适用域校验（2026-09-09, R4）: 透传 style/duration，异风格运行时
        # 不适用的规则自动退场 → 回退启发式（此前 applicability 从未被校验）。
        _rule_gate = None
        _rule_ctx = None
        try:
            _rule_ctx = {"style": self._style_id, "duration": target_duration}
            from scripts.rule_registry import cut_anchor_allowed as _caa
            _rule_gate = _caa(_rule_ctx)
        except Exception as _rg_e:  # noqa: BLE001
            print(f"  [drum-anchor] 规则库不可达({_rg_e.__class__.__name__}), 按未建立处理")
        if _os_da.environ.get("MASTER_NO_DRUM_ANCHORS") == "1":
            print("  [drum-anchor] 已通过环境开关强制关闭（对照组模式）")
        elif _rule_gate is False and _os_da.environ.get("MASTER_ANCHOR_V2") != "1":
            print(f"  [drum-anchor] 规则库裁决: cut_anchor 规则不适用当前运行"
                  f"(style={_rule_ctx.get('style')}, duration={target_duration}s)"
                  f" → 回退启发式")
        else:
            try:
                import hashlib as _hl
                from pathlib import Path as _PathA
                _ak = (_PathA("cache/stems") /
                       _hl.sha256(_PathA(bgm_path).read_bytes()).hexdigest()[:12] /
                       "anchors.json")
                if _ak.exists():
                    _anch = json.loads(_ak.read_text(encoding="utf-8"))
                    self._onset_types = {}
                    self._onset_energy = {}
                    _strong_anchors = []
                    self._anchor_events = {"kick": [], "snare": []}
                    for _kind in ("kick", "snare"):
                        for _t, _s in _anch.get(f"{_kind}_onsets", []):
                            _k3 = round(float(_t), 3)
                            self._onset_types[_k3] = _kind
                            self._onset_energy[_k3] = float(_s)
                            self._anchor_events[_kind].append((float(_t), float(_s)))
                            if float(_s) >= 0.5:
                                _strong_anchors.append(float(_t))
                    # 律动层 = 全部 kick/snare 真值（hihat 已被 stem 分离天然排除）
                    self._groove_onsets = sorted(float(t) for t in self._onset_types)
                    self._anchor_strong = sorted(_strong_anchors)
                    self._drum_anchor_mode = True
                    # E0-1 关键注入: 切点候选池消费方全部升级为 stem 真值。
                    # （此前只改 _onset_types 时切点层不受影响——第一轮 A/B已证伪：
                    #   两臂 plan 切点分布完全相同，因为池子仍是笼统 onset）
                    _drum_times = sorted({float(t) for ev in self._anchor_events.values()
                                          for t, _ in ev})
                    # v2 旋律锚 (2026-09-05 用户听感反馈: 高潮段没卡小提琴节奏变换/
                    # 重音没有适配镜头) — other 声部的攻击音+音变点并入 _onsets
                    # (脉冲运镜触发源)，并以 stem 真值覆盖 _melody_onsets/_melody_env
                    # (raw BGM pyin 被低音主导, 音变检出率被压制 51 vs 44)
                    _mel = [(round(float(t), 3), float(s))
                            for t, s in _anch.get("melody_onsets", [])]
                    _drum_times = sorted(set(_drum_times))
                    # ── R-2026-0002: 事件选择 × 网格相位 (2026-09-06) ──
                    # R-0001 两次听感否决的教训: 表达性音符(旋律音变/花音)不在
                    # 节拍网格上, 切点跟事件时间走 → 每个 cut 都"在某声音上"
                    # 但整体脱离 BPM 相位 → 人耳判"完全不在点上"。
                    # v2: 全部锚点事件吸附到最近 16 分音符网格位(相位取自拍点),
                    # 事件只决定哪些网格位是热的; 距网格超过半格的事件丢弃——
                    # 宁可少切, 不切在格间。MASTER_ANCHOR_V2=1 启用(A/B 实验位)。
                    _v2 = _os_da.environ.get("MASTER_ANCHOR_V2") == "1"
                    _qd, _qm = _drum_times, [t for t, _ in _mel]
                    if _v2 and getattr(self, "_beats", None) and \
                            len(self._beats) >= 2:
                        _bpm = 60.0 / max(1e-6, float(self._beats[1].time -
                                                       self._beats[0].time))
                        _t0 = float(self._beats[0].time)
                        _step = 60.0 / max(1e-6, _bpm) / 4.0  # 16 分音符
                        _half = _step / 2.0

                        def _q(t):
                            k = round((float(t) - _t0) / _step)
                            return round(_t0 + k * _step, 3)

                        _qd = sorted({max(0.0, _q(t)) for t in _drum_times
                                      if abs(float(t) - _q(t)) <= _half})
                        _qm = sorted({max(0.0, _q(t)) for t, _ in _mel
                                      if abs(float(t) - _q(t)) <= _half})
                        print(f"  [anchor-v2] 网格量化: {_step*1000:.0f}ms 格"
                              f" (BPM {_bpm:.0f}) — 鼓 {len(_drum_times)}→{len(_qd)}, "
                              f"旋律 {len(_mel)}→{len(_qm)} (格间事件弃用)")
                    self._onsets = sorted({*_qd, *_qm})
                    self._onset_types.update({t: "melody" for t in _qm
                                              if t not in self._onset_types})
                    for t, s in _mel:
                        self._onset_energy.setdefault(round(float(t), 3), float(s))
                    self._melody_onsets = list(_qm)
                    _menv = _anch.get("melody_env")
                    if _menv:
                        self._melody_env = ([float(t) for t, _ in _menv],
                                            [float(v) for _, v in _menv])
                    print(f"  [drum-anchor] stems 真值模式: kick/snare 共 "
                          f"{len(_drum_times)} 个 (强 {len(self._anchor_strong)}), "
                          f"旋律锚 {len(_mel)} 个, 源={_ak}")
                    print(f"  [drum-anchor] _onsets 已替换为 鼓锚+旋律锚 "
                          f"{len(self._onsets)} 个（笼统 onset 退出切点池）")
                else:
                    print(f"  [drum-anchor] 无 anchors.json({_ak.name}), 保持频段启发式")
            except Exception as _da_e:  # noqa: BLE001
                print(f"  [drum-anchor] 加载失败, 保持启发式: {_da_e}")

        # 1.1b+ 拍点吸附真实鼓点 (2026-09-02 根因修复):
        # beat_track 返回的是速度先验下的节拍网格(估计值), 实测切点只有
        # 34% 落在强鼓点±50ms 内, 54% 偏差>120ms (199BPM 曲目 = 整拍错位),
        # 用户听感"完全没卡上鼓点"。修复: 每个拍点吸附到最近的**强 onset**
        # (强度前 50%, ±140ms 容差) — 切点/SFX/运镜全部跟着真鼓点走。
        try:
            import librosa as _lb
            import numpy as _np2
            _y2, _sr2 = _lb.load(bgm_path, sr=22050, mono=True)
            _oenv = _lb.onset.onset_strength(y=_y2, sr=_sr2, hop_length=512)
            _otimes = _lb.times_like(_oenv, sr=_sr2, hop_length=512)
            _strs = []
            for _ot in self._onsets:
                _oi = _np2.searchsorted(_otimes, _ot)
                _strs.append(float(_oenv[min(_oi, len(_oenv) - 1)]))
            _strs = _np2.array(_strs) if _strs else _np2.array([])
            if len(_strs) and self._beats:
                _thresh = _np2.percentile(_strs, 50)
                _strong = sorted(
                    float(t) for t, s in zip(self._onsets, _strs) if s >= _thresh)
                # E0-1: 锚点模式下吸附目标升级为 stem 真鼓点（kick/snare 强集）
                if getattr(self, "_drum_anchor_mode", False) and getattr(self, "_anchor_strong", []):
                    _strong = list(self._anchor_strong)
                _snapped = 0
                for _b in self._beats:
                    if not _strong:
                        break
                    _near = min(_strong, key=lambda o: abs(o - _b.time))
                    if abs(_near - _b.time) <= 0.140:
                        if _near != _b.time:
                            _b.time = round(_near, 4)
                            _snapped += 1
                print(f"      拍点吸附: {_snapped}/{len(self._beats)} 个拍点"
                      f"已吸附到强鼓点 (强 onset {len(_strong)} 个)")
        except Exception as _snap_e:  # noqa: BLE001
            print(f"      拍点吸附跳过({_snap_e})")
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
              style_spec=None, use_speed_ramp: bool = False, theme: Optional[str] = None,
              cut_times_override: Optional[List[float]] = None):
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
        self._dyn_sections = _dyn_sections
        # 保存 RMS 真实能量 + 时间轴 (v22 e_norm 用 RMS 分位数归一化)
        self._rms_energy = _rms
        self._rms_times = _rms_times
        try:
            from core.beat_strength_engine import BeatStrengthEngine
            _be = BeatStrengthEngine(fps=self._render_fps)
            _beats_arr = _np.array([b.time for b in self._beats]) if self._beats else _np.array([])
            _dbt = _np.array([b.time for b in self._beats
                              if getattr(b, "is_downbeat", False)]) if self._beats else _np.array([])
            if len(_beats_arr) == 0:
                raise RuntimeError("self._beats 为空, 无法分级")
            _onset_env = _librosa.onset.onset_strength(y=_y, sr=_sr)
            self._beat_class = _be.classify_beats(
                _beats_arr, _dbt,
                onset_envelope=_onset_env,
                rms_energy=_rms, times=_rms_times, sr=_sr, hop_length=512)
            _bc_stats = self._beat_class.statistics()
            print(f"      [BeatStrength] 分级成功: "
                  f"强{_bc_stats['strong']}/中{_bc_stats['medium']}/弱{_bc_stats['weak']}")
        except Exception as _e:
            import traceback
            print(f"      [WARN] BeatStrengthEngine 分级失败: {_e}")
            traceback.print_exc()
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
            # 保存原始弧段边界用于 level 继承
            _orig_arcs = [(s_["start"], s_["end"],
                           self._arc_levels.get(round(s_["start"], 3), "mid"))
                          for s_ in arc_segments]
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
            # 修复(2026-09-02): breath_break 切分后, 新弧段的 start 不在
            # _arc_levels 中 → 后续查表默认 "mid" → 切点密度错乱。
            # 正确做法: 用原始弧段的时间范围继承 energy level。
            self._arc_levels = {}
            for _seg in arc_segments:
                _inherited = "mid"
                for _os, _oe, _ol in _orig_arcs:
                    if _os <= _seg["start"] + 0.001 and _seg["start"] - 0.001 <= _oe:
                        _inherited = _ol
                        break
                self._arc_levels[round(_seg["start"], 3)] = _inherited
        
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
            # 强鼓点集合 (2026-09-02 run3 复盘): 高分段把弱 onset(hi-hat等)
            # 也当切点 → 切点-强鼓点对齐率仅 33%, 用户听感"没卡上鼓点"。
            # 切点必须优先强鼓点(强度前 55%), 弱 onset 仅密度不足时补位。
            _strong_onset_rel: list = []
            try:
                import librosa as _lb3
                import numpy as _np4
                _yb2, _srb2 = _lb3.load(bgm_path, sr=22050, mono=True)
                _oe2 = _lb3.onset.onset_strength(y=_yb2, sr=_srb2, hop_length=512)
                _ot2 = _lb3.times_like(_oe2, sr=_srb2, hop_length=512)
                _od2 = _lb3.onset.onset_detect(y=_yb2, sr=_srb2, units="time")
                _ost2 = [float(_oe2[min(_np4.searchsorted(_ot2, t), len(_oe2) - 1)])
                         for t in _od2]
                _th2 = _np4.percentile(_ost2, 55)
                _strong_onset_rel = sorted(
                    round(float(t - bgm_start_sec), 3)
                    for t, s in zip(_od2, _ost2)
                    if s >= _th2
                    and bgm_start_sec <= t <= bgm_start_sec + duration)
                _th3 = _np4.percentile(_ost2, 78)
                _hit_anchor_rel = sorted(
                    round(float(t - bgm_start_sec), 3)
                    for t, s in zip(_od2, _ost2)
                    if s >= _th3
                    and bgm_start_sec <= t <= bgm_start_sec + duration)
                print(f"  强鼓点集(切点优先): {len(_strong_onset_rel)} 个 | "
                      f"撞拍锚(前22%): {len(_hit_anchor_rel)} 个")
            except Exception as _so_e:  # noqa: BLE001
                print(f"  强鼓点集跳过({_so_e})")

            def _is_strong_onset(t: float) -> bool:
                return any(abs(t - s) <= 0.045 for s in _strong_onset_rel)

            def _is_hit_anchor(t: float) -> bool:
                return any(abs(t - s) <= 0.045 for s in _hit_anchor_rel)

            # 密度自适应间隔 (2026-09-03 用户根因: 23-25s 实测鼓点 4.5/s 的
            # 爆发段被判 intro 后被 0.9s 固定间隔吞掉 10 个鼓点):
            # 急速鼓点→0.18s 快切 / 中速→0.35s / 慢段→0.7s, 与段位分级解耦
            def _adaptive_gap(tt: float) -> float:
                # 小提琴决斗段 (用户 2026-09-03): 每个音律变换一刀, 允许
                # 每秒 5-6 切 → 最小间隔降到 0.16s (~4帧)
                if getattr(self, '_burst_win', (12.8, 30.0))[0] <= tt <= getattr(self, '_burst_win', (12.8, 30.0))[1]:
                    return 0.16
                _d = sum(1 for o in onset_rel if abs(o - tt) <= 0.5)
                if _d >= 3:
                    return _MIN_SHOT_DUR
                if _d >= 2:
                    return 0.35
                return 0.7

            # 小提琴急速段 (用户定稿 2026-09-03): 1号曲 from-10s 剪辑版,
            # 原 23-32s 急速小提琴段 = 新轴 13-22s — 该段切点严格跟小提琴
            # 变换频率(旋律 onset 网格), 其余段落保持鼓点网格
            _VIOLIN_BURST = getattr(self, "_burst_win", (12.8, 30.0))
            _mel_rel = sorted(
                mt - bgm_start_sec
                for mt in (getattr(self, "_melody_onsets", None) or [])
                if bgm_start_sec <= mt <= bgm_start_sec + duration)
            for s_ in arc_segments:
                seg_onsets = [t for t in onset_rel
                              if s_["start"] + 0.05 <= t <= s_["end"] - 0.05]
                if s_["start"] < _VIOLIN_BURST[1] and s_["end"] > _VIOLIN_BURST[0]:
                    _vi = [t for t in _mel_rel
                           if s_["start"] + 0.05 <= t <= s_["end"] - 0.05]
                    # 决斗段密度保障 (2026-09-03 深度分析结论): 本曲小提琴采样
                    # 与鼓同网格制作(切点与鼓重合 82%), 且多声部混音里 pyin F0
                    # 被低音主导 — 检测路线全堵死。用户"一秒五六切"=十六分音符
                    # 网格 → 旋律网格密度不足 4.5/s 时直接上 0.17s 十六分网格
                    # 密度调制网格 (2026-09-03 用户终版: 跟小提琴速度变化跳动
                    # — 急奏→密切, 放慢→疏切, 再提速→再密, 而非恒速十六分)
                    _t0 = max(s_["start"], _VIOLIN_BURST[0]) + 0.05
                    _t1 = min(s_["end"], _VIOLIN_BURST[1]) - 0.05
                    _env = getattr(self, "_melody_env", None)
                    _p70 = _p40 = _p20 = None
                    if _env:
                        import numpy as _npg
                        _et, _er = _env
                        _in_w = [e for tt, e in zip(_et, _er)
                                 if 12.8 <= tt <= 30.0]
                        if len(_in_w) > 20:
                            _p70 = float(_npg.percentile(_in_w, 70))
                            _p40 = float(_npg.percentile(_in_w, 40))
                            _p20 = float(_npg.percentile(_in_w, 20))
                    # 用户终极诉求 (2026-09-04): 切点位置=小提琴音符事件本身
                    # (含反拍音符 — 与跟鼓的可见区别), 包络只定稀疏步长;
                    # 琴休止(步长内无音符)才回退时间网格点
                    def _env_step(tt):
                        if _p70 is not None:
                            import bisect as _bis2
                            _i2 = _bis2.bisect_left(_env[0], tt)
                            _e2 = _env[1][min(_i2, len(_env[1]) - 1)]
                            if _e2 >= _p70:
                                return 0.17   # 小提琴强奏
                            elif _e2 >= _p40:
                                return 0.26
                            elif _e2 >= _p20:
                                return 0.40   # 渐弱
                            return 0.55       # 持续音/停顿
                        _md = sum(1 for m in _mel_rel if abs(m - tt) <= 0.5)
                        return (0.17 if _md >= 5 else 0.26 if _md >= 3
                                else 0.40 if _md >= 2 else 0.55)

                    _vi, _last, _tc = [], -1e9, _t0
                    _mels = [x for x in _mel_rel if _t0 <= x <= _t1]
                    while _tc < _t1:
                        _stp = _env_step(_tc)
                        _nxt = next((x for x in _mels
                                     if _tc + 0.08 <= x <= _tc + _stp + 0.25), None)
                        _pt = _nxt if _nxt is not None else _tc + _stp
                        _vi.append(round(_pt, 3))
                        _last, _tc = _pt, _pt
                    if _vi:
                        seg_onsets = _vi
                seg_beats = [t for t in real_beats_rel
                             if s_["start"] + 0.05 <= t <= s_["end"] - 0.05]
                _level = self._arc_levels.get(round(s_["start"], 3), "mid")

                # 根因修复(2026-09-02): onset 检测命中 90%+ 鼓点瞬态,
                # 而 beat grid 仅 53.6%. 鼓点瞬态在 onset 上, 不在拍网格上.
                # 之前用 beat 作主切点再吸附 onset 是本末倒置 — 现在直接用 onset 作主切点.
                # beat grid 仅用于密度参考和 fallback.
                def _nearest_onset(_t, _grid):
                    import bisect as _bis
                    if not _grid:
                        return None
                    _i = _bis.bisect_left(_grid, _t)
                    _cs = []
                    if _i < len(_grid):
                        _cs.append(_grid[_i])
                    if _i > 0:
                        _cs.append(_grid[_i - 1])
                    return min(_cs, key=lambda x: abs(x - _t)) if _cs else None

                if _level == "high":
                    # 爆发段: 强鼓点优先作主切点(每记重击一刀); 弱 onset 仅在
                    # 强鼓点密度不足(段长/0.7 以下)时补位。最小间隔 _MIN_SHOT_DUR。
                    _pts = sorted(set(seg_onsets))
                    new_cuts = []
                    for _p in _pts:
                        if not new_cuts or _p - new_cuts[-1] >= _adaptive_gap(_p):
                            new_cuts.append(round(_p, 3))
                    # 撞拍双切 (2026-09-02 用户语法): 最重鼓点(强度前22%)在爆发段
                    # 触发双切——重击瞬间一刀 + 0.18s 第二刀, 双击撞击感
                    # 2026-09-03 决斗段跳过: 十六分网格已是密度权威, 双切会造
                    # 成 2-3 帧簇 → P1a 半吞 → 净距 0.33 (run42 掉刀根因)
                    for _a in ([] if getattr(self, '_burst_win', (12.8, 30.0))[0] <= s_["start"] < getattr(self, '_burst_win', (12.8, 30.0))[1]
                               else [t for t in _pts if _is_hit_anchor(t)]):
                        _tw = round(_a + 0.18, 3)
                        if _tw <= s_["end"] - 0.05 and all(
                                abs(_tw - c) >= _MIN_SHOT_DUR for c in new_cuts):
                            new_cuts.append(_tw)
                    new_cuts = sorted(set(new_cuts))
                    # fallback: 若无 onset 则退回 beat
                    if not new_cuts and seg_beats:
                        new_cuts = [round(b, 3) for b in seg_beats]
                elif _level == "low":
                    # 鼓点网格(2026-09-03 用户最终语法): 慢段 onset 间隔天然长
                    # → 长镜+变速曲线, 跟着鼓点放慢而放慢
                    new_cuts = []
                    for _p in sorted(set(seg_onsets)):
                        if not new_cuts or _p - new_cuts[-1] >= _adaptive_gap(_p):
                            new_cuts.append(round(_p, 3))
                else:
                    # 中能量段: 强鼓点按 _mid_gap 过滤优先; 密度不足再补全部 onset
                    _base = sorted(set(seg_onsets))
                    _new_mid = []
                    for _t in sorted(_base):
                        if not _new_mid or _t - _new_mid[-1] >= _adaptive_gap(_t):
                            _new_mid.append(round(_t, 3))
                    new_cuts = _new_mid
                    # fallback: 若无 onset 切点则退回 beat
                    if not new_cuts and seg_beats:
                        new_cuts = [round(b, 3) for b in seg_beats]
                # 强制锚定 kick(低频重音)+强拍 (2026-08-13 漫剪撞拍核心):
                # 仅 high/mid 段强制 (low 段保持长镜头呼吸, 不塞快切)
                if self._beatgrid and _level != "low" and not (
                        getattr(self, '_burst_win', (12.8, 30.0))[0] <= s_["start"] < getattr(self, '_burst_win', (12.8, 30.0))[1]):
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

        # ── 切点覆盖注入 (P2 repair 接线, 2026-09-10) ──
        # unified_edit 切点自检 FAIL → repair_cutpoints 修表 → 带本参数重渲。
        # 注入点选在所有内部切点计算(吸附/抽稀)之后、择优与镜头设计之前:
        # 覆盖表即最终切点, 下游 rhythm 择优/LLM 镜头设计/时间线构建照常消费。
        if cut_times_override:
            _ov = sorted(set(round(float(t), 3) for t in cut_times_override
                             if 0.0 < float(t) < duration))
            for s_ in arc_segments:
                s_["cut_times"] = [t for t in _ov
                                   if s_["start"] + 1e-3 < t < s_["end"] - 1e-3]
            self._cut_times_override = list(_ov)
            print(f"  切点覆盖: 注入 {len(_ov)} 个修复切点 "
                  f"(P2 repair, 跳过内部切点计算结果)")

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
            # 2026-09-02 移除 half_shift 候选: 它把全部切点整体偏移半拍
            # (切在弱拍/鼓点之间), run2 实测被采纳后切点-鼓点对齐率仅 34%,
            # 用户听感"完全没卡上鼓点"。0.01 级分差属噪声, 却能整体毁掉
            # 节奏感 — 此类"结构性破坏"候选一律不得进入择优。
            # 切点已吸附真实鼓点(见 _analyze 1.1b+), 任何整体拖动都破坏对齐。
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
            # arc_plan 是唯一候选, 不再重映射切点
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
                [t for t in onset_rel if arc_start <= t <= arc_end] +
                [t for t in ((self._beatgrid.get("kick", []) or []) +
                             (self._beatgrid.get("strong", []) or []))
                 if arc_start <= t <= arc_end]))
            # 2026-09-03 决斗段豁免: 节拍吸附会把十六分网格(0.17s)坍缩到
            # onset 网格上(多网格点吸到同一拍→0.05去重→密度 5.9→2.5)。
            # 网格本身已节奏对齐, 无需吸附。
            if _snap_grid and not (arc_start < getattr(self, '_burst_win', (12.8, 30.0))[1] and arc_end > getattr(self, '_burst_win', (12.8, 30.0))[0]):
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
            _nb = len(boundaries)
            _merged = [boundaries[0]]
            for _b in boundaries[1:]:
                # 2026-09-03 决斗段密切放行: 0.18 经 24fps 取整=5帧(0.208s)
                # 正是密切被吞的地板; 决斗段窗口内放宽到 0.15 允许十六分网格
                _thr = 0.15 if (getattr(self, '_burst_win', (12.8, 30.0))[0] <= _b <= getattr(self, '_burst_win', (12.8, 30.0))[1]) else 0.18
                if _b - _merged[-1] < _thr:
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
                # 片头黑场钳制 (2026-09-03 真凶: 素材首次使用 src_start=0, 连续
                # 7 个镜头全是黑场/淡入开头 → 鼓点上切了看不见, 开头节奏全死)
                _min_ss = min(2.0, max(0.0, src_dur - seg_dur - 0.5))
                if source_start < _min_ss:
                    source_start = _min_ss
                # 死区避让 (2026-09-06 run53 教训: 黑场/水印卡/静帧整段死滞)
                source_start = self._nudge_to_live_window(
                    source, source_start, seg_dur)

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
                    # 局部鼓点密度 → 速度 (2026-09-03 用户最终语法:
                    # 急速鼓点→快切, 鼓点放慢→变速慢镜; 段落规则只做中段兜底)
                    _ons_local = (getattr(self, "_groove_onsets", None)
                                  or getattr(self, "_onsets", None) or [])
                    _dens = sum(1 for o in _ons_local
                                if abs(o - seg_start) <= 0.6) / 1.2
                    _speed = round(min(1.55, max(0.50, 0.28 + 0.21 * _dens))
                                   / 0.05) * 0.05
                    _tech = ("fast_pan" if _dens >= 3.0 else
                             "slowmo" if _dens <= 1.4 else "pulse")
                    speed = _speed
                    _v22_tech = _tech  # 供运镜决策使用
                else:
                    speed = 1.0

                # ── T3 运镜决策: 素材感知 + 情绪映射 + 衔接平滑 ────
                _source_cam = "unknown"
                if _cam_inv is not None:
                    _source_cam = _src_cam_labels.get(source, "unknown")

                # 鼓点分型→镜头语法 (2026-09-03 用户语法, v2: 全镜头生效):
                # kick(低频重击)→推进 push / snare(中频军鼓)→拉远 zoom_out /
                # 连击段(律动层密度≥3.5/s)→推拉交替=连续场面切换
                # v1 根因: 70ms 硬窗+藏在 _cam_inv 分支内 → 89% 镜头掉回 static
                _groove = getattr(self, "_groove_onsets", None) or []
                _ot_type = None
                _best_d = 1e9
                for _otk, _oty in getattr(self, "_onset_types", {}).items():
                    _dd = abs(_otk - seg_start)
                    if _dd < _best_d:
                        _best_d = _dd
                        _ot_type = _oty
                if _best_d > 0.30:
                    _ot_type = None  # 300ms 内无鼓点 → 非鼓点起始镜头
                _gdens = (sum(1 for o in _groove if abs(o - seg_start) <= 0.6)
                          / 1.2 if _groove else 0)
                if _gdens >= 3.5:
                    zoompan_effect = ("push" if getattr(self, "_roll_alt", 0) == 0
                                      else "zoom_out")
                    self._roll_alt = 1 - getattr(self, "_roll_alt", 0)
                elif _ot_type == "kick":
                    zoompan_effect = "push"
                elif _ot_type == "snare":
                    zoompan_effect = "zoom_out"
                elif _ot_type == "hihat" and _gdens >= 1.5:
                    zoompan_effect = "zoom_in"
                elif _cam_inv is not None:
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
                # 2026-09-03 鼓点分派豁免: T4 池轮转曾无条件覆盖鼓点分型
                # (visual_variance>=7 时逐镜轮转) → 89% static、同鼓点不同待遇。
                # 鼓点是运镜的唯一权威来源, 品味池只管无鼓点依据的镜头。
                _drum_assigned = (_gdens >= 3.5 or _ot_type in ("kick", "snare")
                                  or (_ot_type == "hihat" and _gdens >= 1.5))
                if not _drum_assigned and _taste_pool and len(_taste_pool) > 1:
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

        # 全局同片段去重 + 单文件占比封顶 (2026-09-04 洛天依/同源重复修复)
        segments = self._enforce_global_source_uniqueness(segments)
        # 相邻镜头同 IP 去重 (2026-09-05 切点可见性短板修复)
        segments = self._enforce_adjacent_diversity(segments)

        print(f"  生成 {len(segments)} 个段落, 总时长 {duration:.1f}s")
        return script

    def _rolls_from_anchor_events(self, kick_times, snare_times, bpm):
        """E0-1: 用 stem 鼓锚重建连击段（与 _load_beatgrid 同款聚类算法）。"""
        all_drum_times = sorted(set(
            [round(t, 4) for t in kick_times] + [round(t, 4) for t in snare_times]))
        rolls = []
        if len(all_drum_times) < 4:
            return rolls
        _roll_start = None
        _roll_prev = None
        _bi = 60.0 / max(float(bpm or 120), 60)
        _roll_thresh = _bi * 0.35
        for dt in all_drum_times:
            if _roll_prev is not None and (dt - _roll_prev) < _roll_thresh:
                if _roll_start is None:
                    _roll_start = _roll_prev
            else:
                if _roll_start is not None and _roll_prev is not None:
                    _rdur = _roll_prev - _roll_start
                    if _rdur >= 0.3:
                        _drum = "kick" if any(
                            abs(_roll_start - k) < 0.1 for k in kick_times) else "snare"
                        rolls.append({"start": round(_roll_start, 3),
                                      "end": round(_roll_prev, 3),
                                      "drum": _drum, "t": round(_roll_start, 3)})
                _roll_start = None
            _roll_prev = dt
        if _roll_start is not None and _roll_prev is not None:
            _rdur = _roll_prev - _roll_start
            if _rdur >= 0.3:
                _drum = "kick" if any(
                    abs(_roll_start - k) < 0.1 for k in kick_times) else "snare"
                rolls.append({"start": round(_roll_start, 3),
                              "end": round(_roll_prev, 3),
                              "drum": _drum, "t": round(_roll_start, 3)})
        return rolls

    def _inject_stem_anchors(self, grid: Dict[str, Any], bgm_path: str) -> Dict[str, Any]:
        """E0-1 鼓点 stem 锚定: anchors.json 真值覆盖 beatgrid 的 kick/strong/weak/rolls。

        频段 FFT 分离的 kick/snare 是启发式（150Hz/5kHz 割裂 + librosa onset）；
        stem 分离后的鼓锚来自真实鼓轨。moments/hard_stops 保留原能量分析。
        anchors.json 缺席或锚点模式关闭时原样返回（fail-safe）。
        注意: 锚点时间基于 BGM 文件时间轴, 适用于 bgm_start_sec=0 的用法。
        """
        if not getattr(self, "_drum_anchor_mode", False):
            return grid
        if not grid:
            return grid
        try:
            ev = getattr(self, "_anchor_events", None) or {}
            kick = sorted({round(t, 4) for t, _ in ev.get("kick", [])})
            snare = sorted({round(t, 4) for t, _ in ev.get("snare", [])})
            all_events = {round(t, 4): float(s)
                          for kind in ("kick", "snare")
                          for t, s in ev.get(kind, [])}
            strong = sorted(t for t, s in all_events.items() if s >= 0.5)
            weak = sorted(t for t, s in all_events.items() if s < 0.5)
            grid["kick"] = kick
            grid["strong"] = strong
            grid["weak"] = weak
            grid["rolls"] = self._rolls_from_anchor_events(kick, snare, grid.get("bpm"))
            grid["source"] = "stem_anchors"
            print(f"      [beatgrid] stem 锚定覆盖: kick={len(kick)} strong={len(strong)} "
                  f"weak={len(weak)} rolls={len(grid['rolls'])}（频段启发式退出）")
        except Exception as _ij_e:  # noqa: BLE001
            print(f"      [beatgrid] stem 锚定注入失败, 保留频段版: {_ij_e}")
        return grid

    def _load_beatgrid(self, bgm_path: str) -> Optional[Dict[str, Any]]:
        """自包含 beatgrid 分析：librosa 频段分离 → 鼓点分类 → 节拍网格。

        替代已失效的 OpenMontage analyze-beatgrid.py 外部脚本。
        频段划分: kick <150Hz / snare 150-5kHz / hihat >5kHz。
        铁律: strong/weak 排除 hihat（镲片不"撞"）。
        结果按 BGM 文件名缓存 tmp/audiomap_{hash}.json，同一 BGM 不重复分析。
        失败返回 None → 回退 onset 逻辑，不阻断渲染。
        """
        try:
            import hashlib
            import json
            import os

            import librosa
            import numpy as np

            _h = hashlib.md5(os.path.basename(bgm_path).encode()).hexdigest()[:8]
            os.makedirs("tmp", exist_ok=True)
            _cache = os.path.join("tmp", f"audiomap_{_h}.json")

            if os.path.exists(_cache):
                with open(_cache, encoding="utf-8") as _f:
                    return self._inject_stem_anchors(json.load(_f), bgm_path)

            print(f"      [beatgrid] 分析 BGM: {os.path.basename(bgm_path)}")
            y, sr = librosa.load(bgm_path, sr=22050, mono=True)
            duration = len(y) / sr

            # ── STFT + 频段分离 ──
            S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
            freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)

            low_mask = freqs < 150
            mid_mask = (freqs >= 150) & (freqs < 5000)
            high_mask = freqs >= 5000

            S_low = S.copy()
            S_low[~low_mask] = 0
            S_mid = S.copy()
            S_mid[~mid_mask] = 0
            S_high = S.copy()
            S_high[~high_mask] = 0

            y_low = librosa.istft(S_low, hop_length=512, length=len(y))
            y_mid = librosa.istft(S_mid, hop_length=512, length=len(y))
            y_high = librosa.istft(S_high, hop_length=512, length=len(y))

            # ── 各频段 onset 检测 ──
            kick_times = librosa.onset.onset_detect(
                y=y_low, sr=sr, hop_length=512, units="time",
                backtrack=True, pre_max=3, post_max=3,
                delta=0.07, wait=10)
            snare_times = librosa.onset.onset_detect(
                y=y_mid, sr=sr, hop_length=512, units="time",
                backtrack=True, pre_max=3, post_max=3,
                delta=0.05, wait=10)
            hihat_times = librosa.onset.onset_detect(
                y=y_high, sr=sr, hop_length=512, units="time",
                backtrack=True, pre_max=2, post_max=2,
                delta=0.05, wait=5)

            kick_times = sorted(set(float(t) for t in kick_times
                                    if 0.05 <= t <= duration - 0.05))
            snare_times = sorted(set(float(t) for t in snare_times
                                     if 0.05 <= t <= duration - 0.05))
            hihat_times = sorted(set(float(t) for t in hihat_times
                                     if 0.05 <= t <= duration - 0.05))

            # ── 节拍追踪 → 小节结构 ──
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=512)
            tempo = float(np.asarray(tempo).flat[0])
            beat_times_arr = librosa.frames_to_time(beat_frames, sr=sr, hop_length=512)
            beat_times_arr = sorted(float(t) for t in beat_times_arr
                                    if 0.05 <= t <= duration - 0.05)

            # 按 4/4 小节分配 strong(拍1) / weak(拍2-4)
            # 修复(2026-09-02): 旧代码用 _near_hihat 过滤 → 大量 beat 被跳过,
            # 19s 曲目仅得 1 个 strong beat, 撞拍锚定几乎失效.
            # 正确做法: 以首个 kick 为小节参考点(kick 通常落在拍1),
            # 所有 beat 按 bar position 分类, 不过滤 hihat.
            _beat_period = 60.0 / max(tempo, 60)
            _bar_period = 4 * _beat_period
            _ref = kick_times[0] if len(kick_times) > 0 else (
                beat_times_arr[0] if beat_times_arr else 0.0)

            strong_times = []
            weak_times = []
            for bt in beat_times_arr:
                _pos = (bt - _ref) % _bar_period
                if _pos < _beat_period * 0.5:
                    strong_times.append(round(bt, 4))
                else:
                    weak_times.append(round(bt, 4))

            # ── 连击段 (rolls)：快速连续 onset 聚类 ──
            all_drum_times = sorted(set(
                [round(t, 4) for t in kick_times]
                + [round(t, 4) for t in snare_times]
            ))
            rolls = []
            if len(all_drum_times) >= 4:
                _roll_start = None
                _roll_prev = None
                _bi = 60.0 / max(tempo, 60)
                _roll_thresh = _bi * 0.35
                for dt in all_drum_times:
                    if _roll_prev is not None and (dt - _roll_prev) < _roll_thresh:
                        if _roll_start is None:
                            _roll_start = _roll_prev
                    else:
                        if _roll_start is not None and _roll_prev is not None:
                            _rdur = _roll_prev - _roll_start
                            if _rdur >= 0.3:
                                _drum = "kick" if any(
                                    abs(_roll_start - k) < 0.1 for k in kick_times
                                ) else "snare"
                                rolls.append({
                                    "start": round(_roll_start, 3),
                                    "end": round(_roll_prev, 3),
                                    "drum": _drum,
                                    "t": round(_roll_start, 3),
                                })
                        _roll_start = None
                    _roll_prev = dt
                if _roll_start is not None and _roll_prev is not None:
                    _rdur = _roll_prev - _roll_start
                    if _rdur >= 0.3:
                        _drum = "kick" if any(
                            abs(_roll_start - k) < 0.1 for k in kick_times
                        ) else "snare"
                        rolls.append({
                            "start": round(_roll_start, 3),
                            "end": round(_roll_prev, 3),
                            "drum": _drum,
                            "t": round(_roll_start, 3),
                        })

            # ── 硬停止 (hard_stops)：RMS 能量骤降 ──
            hard_stops = []
            rms = librosa.feature.rms(S=S, frame_length=2048, hop_length=512)[0]
            rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
            if len(rms) > 20:
                rms_smooth = np.convolve(rms, np.ones(10) / 10, mode="same")
                rms_diff = np.diff(rms_smooth, prepend=rms_smooth[0])
                rms_std = np.std(rms_diff) if len(rms_diff) > 0 else 1.0
                if rms_std > 0:
                    drop_indices = np.where(rms_diff < -3.0 * rms_std)[0]
                    for idx in drop_indices:
                        t_val = float(rms_times[min(idx, len(rms_times) - 1)])
                        if 0.5 <= t_val <= duration - 0.5:
                            hard_stops.append(round(t_val, 3))
                _min_gap = 2.0
                _filtered_hs = []
                for hs in sorted(hard_stops):
                    if not _filtered_hs or hs - _filtered_hs[-1] >= _min_gap:
                        _filtered_hs.append(hs)
                hard_stops = _filtered_hs

            # ── 关键时刻 (moments)：kick + strong 密度峰值区 ──
            moments = []
            _key_times = sorted(kick_times + [float(t) for t in strong_times])
            if len(_key_times) >= 6:
                _window = 4.0
                _step = 1.0
                _t = 0.0
                _best_density = 0
                _best_t = 0.0
                while _t < duration - _window:
                    _count = sum(1 for kt in _key_times
                                 if _t <= kt < _t + _window)
                    if _count > _best_density:
                        _best_density = _count
                        _best_t = _t
                    _t += _step
                if _best_density >= 6:
                    moments.append({
                        "t": round(_best_t + _window / 2, 3),
                        "label": "climax",
                        "density": _best_density,
                    })

            result = {
                "kick": [round(t, 4) for t in kick_times],
                "strong": strong_times,
                "weak": weak_times,
                "rolls": rolls,
                "moments": moments,
                "hard_stops": [{"t": t} for t in hard_stops],
                "bpm": round(float(tempo), 1) if tempo else None,
                "source": "librosa_self_contained",
            }

            with open(_cache, "w", encoding="utf-8") as _f:
                json.dump(result, _f, ensure_ascii=False)

            print(f"      [beatgrid] 完成: kick={len(result['kick'])} "
                  f"strong={len(result['strong'])} weak={len(result['weak'])} "
                  f"rolls={len(rolls)} hard_stops={len(hard_stops)} "
                  f"bpm={result.get('bpm')}")
            return self._inject_stem_anchors(result, bgm_path)

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
                onset_envelope=onset_env, sr=sr, backtrack=False,
                hop_length=256, delta=0.03, wait=2)
            onsets = [float(t) for t in librosa.frames_to_time(
                frames, sr=sr, hop_length=256)]
            # 旋律 onset (小提琴/钢琴=谐波分量): 小提琴急速段专用网格
            _yh2 = None
            try:
                _yh2, _ = librosa.effects.hpss(y)
            except Exception:
                pass
            try:
                _mf = librosa.onset.onset_detect(
                    y=(_yh2 if _yh2 is not None else y), sr=sr, units="time",
                    hop_length=256, backtrack=False, delta=0.03, wait=2)
                _mel = [float(m) for m in _mf]
                # ══ 音高跟踪切点 (2026-09-03 决斗段终极修复) ══════════════
                # 深度分析结论: 小提琴音变两类——起弓攻击音(可检测但大多与鼓
                # 重合, 故历版都"像跟鼓走") + 连奏音变(legato 音高滑动, 无能量
                # 突变, 能量检测物理不可见)。要真跟小提琴必须检测 F0 变化:
                # pyin 逐帧基频 → 中值滤波抑制颤音(vibrato ±20-50 cents) →
                # 平滑曲线上的持续音高变化(≥35音分/帧) = 真实音变点。
                try:
                    import numpy as _npf
                    from scipy.signal import medfilt
                    _ysrc = (_yh2 if _yh2 is not None else y)
                    _f0, _, _ = librosa.pyin(
                        _ysrc, fmin=196, fmax=2000, sr=sr,
                        frame_length=2048, hop_length=256)
                    _f0s = medfilt(_npf.nan_to_num(_f0, nan=0.0), 5)
                    _voiced = _f0s > 150
                    _cents = _npf.full(len(_f0s), 0.0)
                    _ok = _voiced[1:] & _voiced[:-1] & (_f0s[:-1] > 150)
                    _cents[1:][_ok] = 1200 * _npf.log2(
                        _f0s[1:][_ok] / _f0s[:-1][_ok])
                    _chg = _npf.where(_npf.abs(_cents) >= 35)[0]
                    _pt, _last = [], -1.0
                    for _cf in _chg:
                        _tt = float(_cf * 256 / sr)
                        if _tt - _last >= 0.08:  # 同一音变去重
                            _pt.append(_tt)
                            _last = _tt
                    # 攻击音与音变点合并(80ms 内去重)
                    _allm = sorted(_mel + _pt)
                    _merged_m, _prev = [], -1.0
                    for _m3 in _allm:
                        if _m3 - _prev >= 0.08:
                            _merged_m.append(round(_m3, 3))
                            _prev = _m3
                    self._melody_onsets = _merged_m
                    print(f"      旋律网格: 攻击{len(_mel)} + 音高变化{len(_pt)}"
                          f" = {len(_merged_m)} 个")
                except Exception as _py_e:
                    self._melody_onsets = _mel
                    print(f"      音高跟踪跳过({_py_e}), 仅攻击音 {len(_mel)} 个")
            except Exception:
                self._melody_onsets = []
            # 小提琴动态包络 (谐波 RMS): 用户"变速停顿"的调制源 — 急奏强→
            # 密切, 持续音/休止弱→疏切+慢镜, 再起→再密
            try:
                _esrc = (_yh2 if _yh2 is not None else y)
                import numpy as _npe
                _rms_m = librosa.feature.rms(y=_esrc, frame_length=1024,
                                             hop_length=256)[0]
                _ets_m = librosa.frames_to_time(
                    _npe.arange(len(_rms_m)), sr=sr, hop_length=256)
                # 0.4s 滑动平均 (2026-09-04 修 20-30s 速度乱跳): 逐点包络受
                # 音符起音/释放噪声影响, 同档能量的镜头被随机推入不同速度档
                # (实测 20-30s 能量全"中"档但速度 0.55/1.1/1.5 逐镜跳)。
                # 0.6s 平滑 (2026-09-04 三次校准: 无平滑=临界抖动, 1.2s=抹掉
                # 节奏变化被用户否决; 0.6s 保留音符级响应, 抖动交给迟滞机制)
                _rms_s = _npe.convolve(_rms_m, _npe.ones(52) / 52, mode="same")
                self._melody_env = (_ets_m.tolist(), _rms_s.tolist())
                try:
                    import numpy as _npw
                    _er_a = _npw.asarray(_rms_m)
                    _th55 = float(_npw.percentile(_er_a, 55))
                    _hot = _er_a >= _th55
                    _best_s = _best_e = 0
                    _run_s = None
                    for _i4, _h4 in enumerate(_hot):
                        if _h4 and _run_s is None:
                            _run_s = _i4
                        elif not _h4 and _run_s is not None:
                            if (_i4 - _run_s) * 256 / sr >= 4.0:
                                _best_s, _best_e = _run_s, _i4
                            _run_s = None
                    if _run_s is not None and (len(_hot) - _run_s) * 256 / sr >= 4.0:
                        _best_s, _best_e = _run_s, len(_hot)
                    if _best_e > _best_s:
                        self._burst_win = (round(_best_s * 256 / sr, 1),
                                           round(_best_e * 256 / sr, 1))
                        print(f"      决斗窗自动检测: {self._burst_win[0]}"
                              f"-{self._burst_win[1]}s")
                except Exception:
                    pass
            except Exception:
                self._melody_env = None
            return onsets
        except Exception as e:
            print(f"      Onset检测失败: {e}")
            return []

    def _nudge_to_live_window(self, source, offset, seg_dur,
                              max_scan=4.0, step=0.4):
        """死区避让 (2026-09-06 run53 教训): 窗口为黑场/水印卡/静帧时, 就近扫描活窗。

        活窗判据 (与 build_master_polish._win_ok 同口径):
        亮度 18-225 / 平均运动 ≥0.2 (纯静帧拒绝) / 窗内无硬切 (MAD≤40)。
        实现: 一次连续解码 [offset-max_scan, offset+max_scan] (规避逐候选 -ss
        寻址在 VFR 素材上的落点漂移), 在流内按帧索引评估候选。
        找不到活窗时原样返回 (调用方无需处理)。
        """
        try:
            import subprocess as _s
            import numpy as _np
            # 源 fps 探测 (run53 教训: 60fps 素材按 24 映射, 时间标签错 2.5 倍)
            _pr = _s.run(["ffprobe", "-v", "error", "-show_entries", "stream=r_frame_rate",
                          "-of", "csv=p=0", source], capture_output=True, text=True, timeout=30)
            _rr = _pr.stdout.strip().splitlines()[0].split(",")[0]
            _fn, _fd = _rr.split("/")
            _fps = float(_fn) / float(_fd) if float(_fd) else 24.0
            _d0 = max(0.0, offset - max_scan)
            _r = _s.run(["ffmpeg", "-v", "error", "-ss", f"{_d0:.3f}",
                         "-t", f"{(offset - _d0) + max_scan + seg_dur + 0.2:.3f}",
                         "-i", source, "-vf", f"scale=160:90,fps={_fps:.0f}", "-f", "rawvideo",
                         "-pix_fmt", "gray", "-"], capture_output=True, timeout=120)
            _n = len(_r.stdout) // (160 * 90)
            if _n < 8:
                return offset
            _fr = _np.frombuffer(_r.stdout[:_n * 160 * 90],
                                 dtype=_np.uint8).reshape(_n, 90, 160).astype(_np.float32)
            _mo = _np.array([0.0] + [float(_np.abs(_fr[i] - _fr[i - 1]).mean())
                                     for i in range(1, _n)])
            # 候选起点: 以 step 为步距, 每个候选占 seg_dur 的帧窗
            _cands = []
            _k = 0
            while True:
                _c = offset - max_scan + _k * step
                if _c > offset + max_scan:
                    break
                if _c >= 0.1:
                    _cands.append(_c)
                _k += 1
            if not _cands:
                return offset

            def _win_dead(c):
                _i0 = int(round((c - _d0) * _fps))
                _i1 = min(_n - 1, _i0 + int(round(seg_dur * _fps)))
                if _i1 - _i0 < 2:
                    return True
                _seg_m = _mo[_i0:_i1 + 1]
                _lm = _fr[_i0:_i1 + 1].mean(axis=(1, 2))
                if _lm.min() < 18 or _lm.max() > 235:
                    return True   # 黑场/过曝
                if float(_seg_m.mean()) < 0.2 or float(_seg_m.max()) > 40:
                    return True   # 纯静帧/含硬切
                return False

            _live = [c for c in _cands if not _win_dead(c)]
            if not _live:
                return offset
            _best = min(_live, key=lambda c: abs(c - offset))
            if abs(_best - offset) < step * 0.5:
                return offset   # 原窗口已活
            print(f"    [死区避让] {os.path.basename(source)[-16:]} "
                  f"{offset:.2f} → {_best:.2f}")
            return round(_best, 3)
        except Exception:
            return offset

    def _enforce_global_source_uniqueness(self, segments, gap=0.5,
                                          max_share=0.08):
        """全局同片段去重 + 单文件占比封顶 (2026-09-04 洛天依/同源重复修复)。

        整场范围内的兜底约束, 不依赖源选择路径的局部去重:
        1. 同一 (file, source_start 相距<=gap) 全片只保留一次; 冲突时先在原文件
           内找一个距所有已用点>=0.6s 的新起点, 找不到才换源。
        2. 单文件镜头占比封顶 max_share (run53 教训 2026-09-06: 0.25 时独自升级5
           19 镜吃干 5.7s 源整段切碎撒全片 → 重复出境; 收紧 0.08 ≈ 每源 ≤9)。
           换源目标 = 使用最少的源 (多源全满时也强制分散, 不拒绝)。
        原地修改 segments (只改 source_file / source_start), 返回 segments。
        确定性: 无随机, 可复现。
        """
        if not segments:
            return segments
        from collections import defaultdict

        dur_of = self._source_durations or {}
        all_src = [f for f in dur_of if dur_of.get(f, 0.0) > 0.0]
        if not all_src:
            all_src = sorted({s.source_file for s in segments})
        used = defaultdict(list)
        counts = defaultdict(int)
        max_per_file = max(int(len(segments) * max_share), 1)

        def fresh_start(f, win, min_gap):
            dur = dur_of.get(f, 60.0)
            usable = dur - win
            if usable <= 0:
                return None
            lo = min(2.0, max(0.0, usable - 0.5)) if usable > 2.0 else 0.0
            cands = [lo + k * (usable - lo) / 12.0 for k in range(13)]
            cands += [lo + k * 0.5 for k in range(int((usable - lo) / 0.5) + 1)]
            best, best_d = None, -1.0
            for c in sorted(set(cands)):
                if c + win > dur + 1e-6:
                    continue
                d = min((abs(c - u) for u in used[f]), default=float("inf"))
                if d >= min_gap and d > best_d:
                    best_d, best = d, round(c, 2)
            return best

        n_nudge = n_swap = 0
        for s in segments:
            f = s.source_file
            win = max(float(s.duration), 0.05)
            over = counts[f] >= max_per_file
            clash = bool(used[f]) and \
                min((abs(float(s.source_start) - u) for u in used[f]),
                    default=float("inf")) <= gap
            if not clash and not over:
                used[f].append(float(s.source_start))
                counts[f] += 1
                continue
            # 未超限: 优先在原文件内换一个新鲜起点
            new_ss = fresh_start(f, win, 0.6)
            if not over and new_ss is not None:
                s.source_start = new_ss
                used[f].append(new_ss)
                counts[f] += 1
                n_nudge += 1
                continue
            # 换源: 使用最少 + 未超限 + 时长足够的文件, 取新鲜起点
            swapped = False
            for cand in sorted(all_src, key=lambda x: (counts[x],)):
                if cand == f:
                    continue
                if dur_of.get(cand, 60.0) > win:
                    ss = fresh_start(cand, win, 0.6)
                    if ss is not None:
                        s.source_file = cand
                        s.source_start = ss
                        used[cand].append(ss)
                        counts[cand] += 1
                        n_swap += 1
                        swapped = True
                        break
            if swapped:
                continue
            # 兜底: 同文件硬找一个 (含超限), 保证不崩溃
            fallback = fresh_start(f, win, 0.0)
            s.source_start = fallback if fallback is not None else float(s.source_start)
            used[f].append(float(s.source_start))
            counts[f] += 1

        if n_nudge or n_swap:
            print(f"  [去重] 起帧调整 {n_nudge} 镜, 换源 {n_swap} 镜 "
                  f"(全局同片段去重 + 单文件占比≤{int(max_share * 100)}%)")
        return segments

    def _enforce_adjacent_diversity(self, segments):
        """相邻镜头同 IP 去重 (2026-09-05 切点可见性短板修复之一)。

        根因: 素材池同 IP 往往对应多个文件(猫1/猫2、独自升级2/5), 引擎只换文件
        不换 IP → 相邻两镜画面同质, 切点"隐形"(帧差<0.35)。实测 run53 相邻同 IP
        切点占 16%。兜底: 相邻两镜不得同 IP, 冲突时把后一镜换到使用最少的异 IP
        文件并取新鲜起点, 且不破坏全局同片段去重(≥0.6s 间距)。原地修改。
        """
        if len(segments) < 2:
            return segments
        import re
        from collections import Counter, defaultdict
        from pathlib import Path

        def franch(src):
            return re.sub(r"[0-9\-_.]+$", "", Path(src).stem).lower()

        dur_of = self._source_durations or {}
        all_src = [f for f in dur_of if dur_of.get(f, 0.0) > 0.0] \
            or sorted({s.source_file for s in segments})
        counts = Counter(s.source_file for s in segments)
        used = defaultdict(list)
        for s in segments:
            used[s.source_file].append(float(s.source_start))

        def fresh_start(f, win):
            dur = dur_of.get(f, 60.0)
            usable = dur - win
            if usable <= 0:
                return None
            lo = min(2.0, max(0.0, usable - 0.5)) if usable > 2.0 else 0.0
            cands = [lo + k * (usable - lo) / 12.0 for k in range(13)]
            cands += [lo + k * 0.5 for k in range(int((usable - lo) / 0.5) + 1)]
            best, best_d = None, -1.0
            for c in sorted(set(cands)):
                if c + win > dur + 1e-6:
                    continue
                d = min((abs(c - u) for u in used[f]), default=float("inf"))
                if d >= 0.6 and d > best_d:
                    best_d, best = d, round(c, 2)
            return best

        n_swap = 0
        for i in range(1, len(segments)):
            prev, cur = segments[i - 1], segments[i]
            if franch(prev.source_file) != franch(cur.source_file):
                continue
            cands = [f for f in all_src if franch(f) != franch(cur.source_file)]
            if not cands:
                continue
            cand = min(cands, key=lambda f: counts[f])
            win = max(float(cur.duration), 0.05)
            ss = fresh_start(cand, win)
            if ss is not None:
                counts[cur.source_file] -= 1
                cur.source_file = cand
                cur.source_start = ss
                used[cand].append(ss)
                counts[cand] += 1
                n_swap += 1
        if n_swap:
            print(f"  [差异化] 相邻同IP换源 {n_swap} 镜 (切点可见性修复)")
        return segments

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

    def _check_semantic_degenerate(self, windows, name: str, cached: bool) -> None:
        """语义窗口退化检测 — 全同标签 = 零区分度。

        判据不绑定 _calc_source_start 的 _role_scene 词表(避免两处维护漂移):
        只要所有窗口标签相同, 叙事角色匹配就必然落空, 选段一律穿透到高光池。
        neutral 额外提示: 它是抽帧失败/无 scene_type/异常共用的默认值,
        全 neutral 且来自缓存 = 上游失败已被固化, 会永久命中且不再重试。
        """
        if not windows:
            return
        tags = [str(t) for _, t in windows]
        if len(set(tags)) > 1:
            return
        _tag = tags[0]
        print(f"  [semantic-window] {name}: {len(tags)} 窗口全为 '{_tag}'"
              f"({'缓存' if cached else '本次分析'}) → 零区分度, "
              f"叙事角色匹配必然落空, 选段穿透到高光池"
              + ("；该缓存已固化上游失败, 建议删除后重跑"
                 if cached and _tag == "neutral" else ""))

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
                    _loaded = [(float(s), str(m)) for s, m in _json.load(_f)]
                self._semantic_windows[source_key] = _loaded
                self._check_semantic_degenerate(
                    _loaded, os.path.basename(source_key), cached=True)
                return self._semantic_windows[source_key]
            # 无缓存: 按 3s 时间窗口抽帧, 用 Qwen3-VL(_vlm_analyze) 逐窗口分析
            from ai.material_intelligence import MaterialIntelligenceEngine
            _eng = MaterialIntelligenceEngine()
            _d = self._source_durations.get(source_key, 60.0)
            _win = 3
            _windows = []
            # neutral 是三种失败共用的默认值, 分类计数才能区分"VLM 判为中性"
            # 与"VLM 根本没跑起来" —— 后者不该被当成结果固化进缓存
            _stats = {"ok": 0, "no_frame": 0, "no_key": 0, "err": 0}
            for _ws in range(0, max(1, int(_d)), _win):
                try:
                    # v4: count=1 只抽窗口中部单帧(50%), 标签=该帧内容,
                    # 与 _calc_source_start 的 +1.5s 取点精确对齐
                    _b64 = _eng.extract_frames_window_b64(
                        source_key, start_sec=_ws, end_sec=min(_ws + _win, _d),
                        count=1)
                    if not _b64:
                        _mood = "neutral"
                        _stats["no_frame"] += 1
                    else:
                        _res, _ = _eng._vlm_analyze(_b64, source_key)
                        # 存 "scene:action" 复合标签, 爆发段用 scene 精确区分
                        # (mood 太泛: intense 同时出现在蓄力/爆发, scene=battle
                        #  才能精确判定爆发)
                        if isinstance(_res, dict) and "scene_type" in _res:
                            _mood = str(_res["scene_type"])
                            _stats["ok"] += 1
                        else:
                            _mood = "neutral"
                            _stats["no_key"] += 1
                except Exception:
                    _mood = "neutral"
                    _stats["err"] += 1
                _windows.append((float(_ws), str(_mood)))
            self._semantic_windows[source_key] = _windows
            if _stats["ok"] == 0:
                # 无一窗口拿到真实 scene_type → 本次是失败不是结果, 不落盘,
                # 否则会被永久命中且再不重试(2026-09-06 实测 392 窗口全 neutral)
                print(f"  [semantic-window] {os.path.basename(source_key)}: "
                      f"{len(_windows)} 窗口无一拿到 scene_type "
                      f"(抽帧失败 {_stats['no_frame']} / 无 scene_type 键 "
                      f"{_stats['no_key']} / 异常 {_stats['err']}) → 拒绝落盘, 下次重试")
            else:
                os.makedirs(_cache_dir, exist_ok=True)
                with open(_cache, "w", encoding="utf-8") as _f:
                    _json.dump(_windows, _f, ensure_ascii=False)
                print(f"  语义窗口(Qwen3-VL): {os.path.basename(source_key)} "
                      f"{len(_windows)}段 有效 {_stats['ok']}"
                      + (f" (抽帧失败 {_stats['no_frame']} / 无键 {_stats['no_key']}"
                         f" / 异常 {_stats['err']})"
                         if _stats["no_frame"] + _stats["no_key"] + _stats["err"] else "")
                      + f" {[(round(s), m) for s, m in _windows[:4]]}...")
            self._check_semantic_degenerate(
                _windows, os.path.basename(source_key), cached=False)
            return _windows
        except Exception as _e:
            print(f"  [WARN] 语义窗口失败(回退高光池): {_e}")
            return None

    def _warn_highlight_pool(self, msg: str) -> None:
        """高光池失效播报(只一次) — 本方法每选段都会调, 直接 print 会刷屏。"""
        if self._highlight_pool_warned:
            return
        self._highlight_pool_warned = True
        print(f"  [highlight-pool] {msg}")

    def _get_highlight_pool(self, source_key: str) -> Optional[List[Tuple[float, float]]]:
        """懒加载某素材的高光段池 [(start_sec, total_score), ...] 按total降序。

        只读 HighlightScorer 磁盘缓存 (cache/highlight_scores/), 该缓存由
        scripts/build_highlight_cache.py 预扫描生成; 本方法不会自己算分。
        无缓存/不可用返回 None → 调用方回退均匀分散, 并播报一次原因。
        """
        try:
            if not source_key or not os.path.exists(source_key):
                return None
            if self._highlight_pool is None:
                self._highlight_pool = {}
                try:
                    from core.highlight_scorer import HighlightScorer
                except ImportError as e:
                    self._warn_highlight_pool(
                        f"HighlightScorer 不可用({e}) → 全程回退均匀取点")
                    return None
                scorer = HighlightScorer(
                    sample_fps=6, resize=(256, 144), cache_enabled=True,
                    disk_cache_dir=os.path.join(
                        _PROJECT_ROOT, "cache", "highlight_scores"))
                src = list(self._source_durations.keys())
                _errs = 0
                for sp in src:
                    try:
                        segs = scorer.load_disk_cache(sp, segment_duration=2.0)
                        if segs:
                            self._highlight_pool[sp] = sorted(
                                [(s.start_sec, float(s.total)) for s in segs],
                                key=lambda x: x[1], reverse=True)
                    except Exception:
                        _errs += 1
                        continue
                if not self._highlight_pool:
                    self._warn_highlight_pool(
                        f"{len(src)} 源全部无高光缓存"
                        + (f"(读取异常 {_errs})" if _errs else "")
                        + " → 跑 python scripts/build_highlight_cache.py")
                elif len(self._highlight_pool) < len(src) or _errs:
                    self._warn_highlight_pool(
                        f"高光缓存覆盖 {len(self._highlight_pool)}/{len(src)} 源"
                        + (f", 读取异常 {_errs}" if _errs else "")
                        + " → 未覆盖源回退均匀取点")
            return self._highlight_pool.get(source_key)
        except Exception as e:
            self._warn_highlight_pool(
                f"高光池加载异常 {type(e).__name__}: {e} → 回退均匀取点")
            return None

    # ================================================================
    #  Phase 3: 渲染执行
    # ================================================================

    def _execute(self, script, resolution, fps, enable_ae_channel: bool = False,
                 beat_lock_hard_cuts: bool = False):
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
        # ══ 重复乐句克隆 (2026-09-03 用户定稿语法) ═══════════════════════
        # 用户澄清: 不是全片段泛化, 而是"25s 后有几秒音乐与 23-25s 是同一段
        # (重复乐句)"→只把这些重复段用标杆段同款编导克隆。专业漫剪惯例:
        # 重复乐句 = 重复视觉语法 (motif repetition)。
        # 实现: 自动定位律动最密的 2s 标杆窗 → 全曲滑动窗节拍指纹(0.1s 网格
        # 二值 onset 向量)余弦相似度 → 相似度≥0.75 的窗口合并为重复段 →
        # 段内镜头克隆标杆的 push/zoom_out 交替; 段外镜头一律保持原分派。
        _groove = getattr(self, "_groove_onsets", None) or []
        if len(_groove) >= 8:
            import numpy as _npq

            def _fp(a, b):
                _bins = _npq.arange(a, b, 0.1)
                _v = _npq.zeros(len(_bins))
                for o in _groove:
                    if a <= o < b:
                        _v[min(int((o - a) / 0.1), len(_bins) - 1)] = 1.0
                return _v

            _dur = max(s.duration + s.start_time for s in segs) if segs else 0
            # 标杆窗 = 律动最密的 2s
            _best_t, _best_n = 0.0, -1
            for _wt in _npq.arange(0, max(_dur - 2, 0.1), 0.5):
                _n = sum(1 for o in _groove if _wt <= o < _wt + 2.0)
                if _n > _best_n:
                    _best_n, _best_t = _n, float(_wt)
            _ref_fp = _fp(_best_t, _best_t + 2.0)
            _ref_norm = float(_npq.linalg.norm(_ref_fp)) or 1.0
            # 重复段检测 (排除标杆自身邻域)
            _repeats = []
            for _wt in _npq.arange(0, max(_dur - 2, 0.1), 0.5):
                if abs(_wt - _best_t) < 2.5:
                    continue
                _f = _fp(float(_wt), float(_wt) + 2.0)
                _fn = float(_npq.linalg.norm(_f)) or 1e-9
                _sim = float(_f @ _ref_fp) / (_fn * _ref_norm)
                if _sim >= 0.75:
                    _repeats.append((float(_wt), float(_wt) + 2.0, round(_sim, 2)))
            # 合并重叠重复段
            _merged = []
            for _a, _b, _s2 in _repeats:
                if _merged and _a <= _merged[-1][1] + 0.5:
                    _merged[-1] = (_merged[-1][0], _b, max(_merged[-1][2], _s2))
                else:
                    _merged.append((_a, _b, _s2))
            _VIOLIN_BURST2 = getattr(self, "_burst_win", (12.8, 30.0))
            _zones = [(_best_t, _best_t + 2.0, 1.0)] + _merged
            # 用户定稿(对调完成态): 小提琴急速段=推进/放大专属区; 前段(0-12.8s)
            # 撤掉推进保持沉稳铺垫 — 强技巧集中爆发, 与 run26 的对比美学一致
            _bw3 = getattr(self, '_burst_win', (12.8, 30.0))
            _zones = [(_bw3[0], _bw3[1], 1.0)] + [
                (a, b, s2) for a, b, s2 in _zones
                if a >= _bw3[1]]
            print(f"  [重复乐句克隆] 标杆 { _best_t:.1f}-{_best_t+2:.1f}s "
                  f"(律动{_best_n}) | 重复段: "
                  + (", ".join(f"{a:.1f}-{b:.1f}s(sim{s2})" for a, b, s2 in _merged)
                     or "无"))
            # 段内镜头克隆标杆编导: 相位逐拍对齐 (帧级路线图③)
            # 旧版按段内位置交替 → 标杆与克隆段相位有半拍错位;
            # 现按"镜头起始前段内律动拍序号"的奇偶交替 — 每段第一拍
            # 必为 push, 与标杆逐拍同相。
            for _s in segs:
                _st = float(_s.start_time)
                for _za, _zb, _zs3 in _zones:
                    if _za - 0.05 <= _st < _zb:
                        _beat_idx = sum(1 for o in _groove
                                        if _za - 0.05 <= o < _st - 0.02)
                        if abs(_za - _bw3[0]) < 0.01:
                            # 小提琴段专属: 推进/放大 + 速度跟旋律律动(非鼓点)
                            # 持续音镜头(≥0.38s=琴拉长音)→缓推跟弓, 短镜→交替撞击
                            if _s.duration >= 0.38:
                                _s.zoompan_effect = "zoom_in"
                            else:
                                _s.zoompan_effect = ("push" if _beat_idx % 2 == 0
                                                      else "zoom_in")
                            _env3 = getattr(self, "_melody_env", None)
                            if _env3:
                                import bisect as _bis3
                                _i3 = _bis3.bisect_left(_env3[0], _st)
                                _e3 = _env3[1][min(_i3, len(_env3[1]) - 1)]
                                import numpy as _nph
                                _w3 = [e for tt, e in zip(*_env3)
                                       if _bw3[0] <= tt <= _bw3[1]]
                                _p60 = float(_nph.percentile(_w3, 60)) if _w3 else 0
                                _p30 = float(_nph.percentile(_w3, 30)) if _w3 else 0
                                # 迟滞换档 (2026-09-04): 能量明确越过阈值±18%带
                                # 才换档 — 临界抖动被吸收, 真实乐句变化立即响应
                                _m3 = 0.18 * max(_p60 - _p30, 1e-9)
                                _tier = getattr(self, "_sp_tier", 1)
                                if _e3 >= _p60 + _m3:
                                    _tier = 2
                                elif _e3 <= _p30 - _m3:
                                    _tier = 0
                                elif _tier == 2 and _e3 < _p60 - _m3:
                                    _tier = 1
                                elif _tier == 0 and _e3 > _p30 + _m3:
                                    _tier = 1
                                self._sp_tier = _tier
                                _s.speed = (0.55, 1.1, 1.5)[_tier]
                            else:
                                _mel_d = sum(
                                    1 for m in (getattr(self, "_melody_onsets", None)
                                                or [])
                                    if abs(m - _st) <= 0.6) / 1.2
                                _s.speed = round(
                                    min(1.55, max(0.50, 0.28 + 0.21 * _mel_d))
                                    / 0.05) * 0.05
                        else:
                            _s.zoompan_effect = ("push" if _beat_idx % 2 == 0
                                                  else "zoom_out")
                        break

        # ══ 重音强调 pass v2 (2026-09-06 v9 语法汲取: 停顿=短镜快吸) ════
        # v9 20-30s 逐镜拆解结论: 0.55 停顿必须是 0.17-0.33s 短镜(快速吸气,
        # 读作"顿挫"); 套在 0.4-0.6s 长镜上 = 拖泥带水(run59 教训)。镜头语言
        # 统一 push(v9 35/37)。节奏: 每 ~2s 一次 dip, 尾部允许三连慢收。
        try:
            _acc = sorted(getattr(self, "_anchor_strong", []) or [])
            _acc_used, _acc_last = 0, -10.0
            for _s in segs:
                _st = float(_s.start_time)
                _en = _st + float(_s.duration)
                if not (14.5 <= _st <= 30.0) or _st - _acc_last < 1.2:
                    continue
                if float(_s.duration) > 0.33:   # v9 语法: 停顿=短镜, 长镜慢放=拖
                    continue
                _hit = next((a for a in _acc
                             if _st + 0.02 <= a <= _en - 0.02), None)
                if _hit is None:
                    continue
                _s.speed = 0.55
                _s.zoompan_effect = "push"
                _acc_used += 1
                _acc_last = _st
                if _acc_used >= 9:
                    break
            print(f"  [重音强调 v2] {_acc_used} 处短镜 0.55 dip "
                  f"(v9 语法: 停顿=短吸, push 统一)")
        except Exception as _ac_e:  # noqa: BLE001
            print(f"  [重音强调] 跳过: {_ac_e}")

        # ══ 速度终审 (2026-09-03, 与运镜克隆终审同款根治) ═══════════════
        # 规划层存在多副本速度赋值(第四次发现), 30.75s+ 段的 0.5 来自未收口
        # 的旧副本。解法同运镜: 渲染前用验证公式统一覆写, 单一权威源。
        _groove_sp = []  # 回滚: 终审曾把 108 镜压成 1.55 抹平 run26 层次
        if False:
            for _s in segs:
                _st = float(_s.start_time)
                _d = sum(1 for o in _groove_sp if abs(o - _st) <= 0.6) / 1.2
                _s.speed = round(min(1.55, max(0.50, 0.28 + 0.21 * _d)) / 0.05) * 0.05
            from collections import Counter as _CS
            print("  [速度终审] "
                  + str(dict(sorted(_CS(round(x.speed, 2) for x in segs).items()))))

        # 全局帧网格对齐 (2026-09-02 踩坑#29 根治): 每片独立量化累计 p50 85ms
        # 随机漂移(下一片补偿修不了已发生边界的随机量化)。切点吸附全局 fps 帧
        # 网格 + 逐片精确帧数渲染(-frames:v), concat 累计边界=网格=计划切点。
        _gp = 0.0
        for _s in segs:
            _b = _gp + _s.duration
            _bg = round(_b * fps) / fps
            _s.duration = round(_bg - _gp, 6)
            _s.start_time = round(_gp, 6)
            _gp = _bg

        if enable_ae_channel:
            from ai.ae_render_channel import AERenderChannel, AE_TECHS
            _ae_plan = {}
            for _i, _seg in enumerate(segs):
                if len(_ae_plan) >= 12:
                    break  # 2026-09-03 容量上限: aerender 每镜30-60s, 超量防爆
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
                if _chan.failures:
                    import json as _json
                    (self._output_dir / "ae_failures.json").write_text(
                        _json.dumps(_chan.get_failures(), ensure_ascii=False, indent=2),
                        encoding="utf-8")

        # 节拍锁定硬切模式 (2026-09-02): fade/xfade 的渐变中点天然糊掉切点
        # (实测实际切点 vs 计划 p50 偏 122ms, 最大 587ms, xfade 链内边界数学
        # 是漂移主源)。漫剪铁律: 卡点用硬切。全量降级后组边界=concat 累计
        # 时长, 由 _tl_drift 累加器锁死在计划切点 (±1帧)。
        if beat_lock_hard_cuts:
            _demoted = 0
            for _s in segs:
                if getattr(_s, "transition", "cut") != "cut":
                    _s.transition = "cut"
                    if isinstance(getattr(_s, "transition_params", None), dict):
                        _s.transition_params.pop("type", None)
                        _s.transition_params.pop("duration", None)
                    _demoted += 1
            if _demoted:
                print(f"  [节拍锁定] {_demoted} 个转场降级硬切 (切点=concat累计, 漂移累加器锁定)")

        # 累计帧量化漂移反馈 (2026-09-02 根因修复 → 2026-09-10 二次根因):
        # 每片段被量化到整帧 (24fps → ±20.8ms), 50 片随机游走累计 ±150ms,
        # 实测实际切点-强鼓点对齐率仅 13% (报告 42%) — 渲染层把切点漂离鼓点。
        # 累加器: 每片实测时长(ffprobe)与计划时长之差累加, 反馈进下一片
        # 目标时长, 把累计时间线锁死在计划切点上 (±1 帧内)。
        #   ⚠ 2026-09-10 实测 bug: run61 实测 49.62s vs plan 30s, 漂移 +19.62s!
        #   根因: 慢放段 (speed<1) 下, read_dur=duration*speed 比 out_frames/fps
        #   短, 慢源 30fps 经 fps=24 重采样后输出帧数 < out_frames; 但 -frames:v
        #   仍按 out_frames 算 _ad 期望, 实际 _probe_dur < render_dur, 漂移逐片
        #   累加且无人衰减, 边界保护 (start_time>=src_dur 重置为 0) 在漂移巨大
        #   后把 source_start 推回素材头/尾, 多段坍塌到同一画面 → 切点不可见。
        #   修复: 漂移钳制到 ±2 帧 (≈ ±83ms @24fps), 溢出则强制补偿 (把 render_dur
        #   调整到 _ad, 下一片漂移清零), 避免累加器发散。
        _tl_drift = 0.0
        _TL_DRIFT_LIMIT = 2.0 / 24.0   # ±2 帧 ≈ ±83ms (24fps)

        def _probe_dur(p) -> float:
            try:
                _ffp = getattr(self, "_ffprobe_bin", None)
                if not _ffp:
                    _ffp = shutil.which("ffprobe") or str(Path(self.ffmpeg).with_name("ffprobe.exe"))
                    self._ffprobe_bin = _ffp
                _r = subprocess.run(
                    [_ffp, "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "csv=p=0", str(p)],
                    capture_output=True, text=True, timeout=30)
                return float(_r.stdout.strip())
            except Exception:  # noqa: BLE001
                return 0.0

        for i, seg in enumerate(segs):
            if not Path(seg.source_file).exists():
                print(f"    [WARN] 素材不存在: {seg.source_file}")
                continue

            # 无预补偿渲染: 各 clip 精确 d_i; 链内最后 clip 一次性
            # 补偿本链全部转场时长 (2026-08-16 零泄漏重构)
            render_dur = seg.duration + chain_last_extra.get(i, 0.0) + _tl_drift

            # 漂移钳制 (2026-09-10): 累加器一旦溢出 ±2 帧就强制归零, 防止
            # run61 实测 +19.62s 失控漂移把 source_start 推回素材尾/头导致
            # 多段坍塌。钳制内仍允许 ±1 帧的 beat-lock 微调。
            if abs(_tl_drift) > _TL_DRIFT_LIMIT:
                _tl_drift = 0.0

            clip_path = run_dir / f"clip_{seg.index:03d}.mp4"
            preset = self._color_presets.get(seg.color_grade, self._color_presets["climax"])

            # AE 通道优先: 高级运镜镜头直接用 AE 预渲染产物 (贝塞尔+运动模糊)
            _ae_path = ae_clips_map.get(seg.index)
            if _ae_path and Path(_ae_path).exists():
                shutil.copy(_ae_path, str(clip_path))
                ok = clip_path.exists() and clip_path.stat().st_size > 0
                if ok:
                    clips.append((str(clip_path), seg))
                    _ad = _probe_dur(clip_path)
                    if _ad > 0:
                        _tl_drift += render_dur - _ad
                continue

            # ══ 镜内变速曲线 (2026-09-03 外网变速卡点核心) ══════════════
            # 调研结论: 全管线速度只有每镜常数; 参考片逆向(09-计划文件
            # 2026-08-11)实测"大量非匀速、缓动曲线、慢放不插帧"。Xenoz 要领
            # 撞击帧决策 (2026-09-03): 起始踩律动层强鼓点的镜头 → 头2帧闪,
            # 白黑轮换, 每3个锚点留1个不闪(呼吸, 防闪帧疲劳)
            # (2026-09-05 上移至段循环开头: 曲线变速子段与恒速路径共用,
            #  修复曲线子段引用未定义变量导致的 NameError 静默回退)
            _flash_c, _trans_c = "", ""
            _st_seg = float(seg.start_time)
            # 最近律动鼓点分型: kick→白黑闪 / snare→RGB故障 / 其余不处理
            _ntype, _nd = None, 0.06
            for _tk, _tv in (getattr(self, "_onset_types", {}) or {}).items():
                _td = abs(_tk - _st_seg)
                if _td < _nd:
                    _nd, _ntype = _td, _tv
            if _ntype == "kick":
                self._flash_alt = getattr(self, "_flash_alt", 0) + 1
                # cut_visibility 冲刺 (2026-09-06): drop 段 kick 闪白覆盖 2/3→3/3
                # (参照集 0.955 vs 我方 0.87 的最后一档=切点帧冲击; build 段保留
                #  1/3 呼吸跳过防闪帧疲劳)
                _in_drop = _st_seg >= 14.5
                if _in_drop or self._flash_alt % 3 != 0:
                    _flash_c = ("white" if self._flash_alt % 2 == 0 else "black")
            elif _ntype == "snare":
                self._glitch_alt = getattr(self, "_glitch_alt", 0) + 1
                if self._glitch_alt % 2 == 0:  # 半数 snare 故障, 防过密
                    _trans_c = "glitch"
            # "极陡缓入缓出、几乎无匀速段"。实现: 每镜拆 2-3 个匀速子段拼出
            # 速度包络, 复用 -frames:v 精确帧数 + concat(同编码无接缝),
            # 曲线均值=seg.speed 保证节拍跨度不变。
            _sp = round(float(getattr(seg, "speed", 1.0) or 1.0), 2)
            _CURVES = {  # (占比, 相对速度) — 均值=1 再按 seg.speed 缩放
                0.55: [(0.25, 1.80), (0.75, 0.70)],          # 慢放落拍: 快进→急减速停在拍上
                0.70: [(0.30, 1.55), (0.70, 0.72)],          # 温和慢放
                0.90: [(0.30, 1.55), (0.50, 0.55), (0.20, 1.30)],  # 推近回落呼吸
                1.00: [(0.50, 1.35), (0.50, 0.65)],          # pulse: 快→慢 脉冲
                1.30: [(0.25, 0.55), (0.75, 1.22)],          # 加速弹起: 吸收→弹射离拍
            }
            _curve = None
            if getattr(seg, "zoompan_effect", None) == "pulse" or _sp in (0.55, 0.7, 0.9, 1.3):
                _curve = _CURVES.get(_sp) or (_CURVES[1.00] if _sp == 1.0 else None)

            if _curve:
                import copy as _copy
                _avg = sum(f * v for f, v in _curve)
                _k = _sp / _avg  # 缩放使曲线均值=seg.speed
                _src_off = seg.source_start
                _ok_all = True
                # 帧级路线图④ (2026-09-04): 子段边界吸附段内律动拍点(±0.12s)
                # — 变速拐点落在鼓点帧上, 曲线与节拍帧级对齐
                _bt0 = float(seg.start_time)
                _gro = getattr(self, "_groove_onsets", None) or []
                _snapped = []
                _acc = 0.0
                for _frac, _v in _curve[:-1]:
                    _acc += _frac
                    _bt = _bt0 + _acc * render_dur
                    _g0 = None
                    _gd = 0.12
                    for g in _gro:
                        if abs(g - _bt) < _gd:
                            _gd, _g0 = abs(g - _bt), g
                    _snapped.append(max(_bt0, _g0 if _g0 is not None else _bt))
                _bounds = _snapped + [_bt0 + render_dur]
                _prev_b = _bt0
                for _ci, ((_frac, _v), _sb) in enumerate(zip(_curve, _bounds)):
                    _sub_dur = max(0.08, _sb - _prev_b)
                    _prev_b = _sb
                    _vv = _v * _k
                    _sub_path = run_dir / f"clip_{seg.index:03d}s{_ci}.mp4"
                    _sub_ok = self._extract_clip(
                        source=seg.source_file, output=str(_sub_path),
                        start_time=_src_off, duration=_sub_dur,
                        resolution=resolution, fps=fps, color=preset,
                        speed=_vv, lut_path=getattr(self, '_lut_path', None),
                        zoompan_effect=None, onset_times=None,
                        out_frames=max(2, round(_sub_dur * fps)),
                        flash=(_flash_c if _ci == 0 else ""),
                        trans=(_trans_c if _ci == 0 else ""),
                    )
                    _ok_all = _ok_all and _sub_ok and _sub_path.exists()
                    if not _sub_ok:
                        break
                    _sub_seg = _copy.copy(seg)
                    _sub_seg.transition = "cut"   # 镜内子段硬接(同编码无接缝)
                    clips.append((str(_sub_path), _sub_seg))
                    _ad = _probe_dur(_sub_path)
                    if _ad > 0:
                        _tl_drift += _sub_dur - _ad
                    _src_off += _sub_dur * _vv
                ok = False  # 已在循环内处理 append
                if _ok_all:
                    continue
                # 曲线渲染失败 → 落到下方单段恒速回退
            # (撞击帧决策已上移至段循环开头, 此处直接使用 _flash_c/_trans_c)
            if True:
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
                    out_frames=max(2, round(render_dur * fps)),
                    flash=_flash_c, trans=_trans_c,
                )
            if ok and clip_path.exists() and clip_path.stat().st_size > 0:
                clips.append((str(clip_path), seg))
                # 漂移累加: 计划 - 实测, 反馈给下一片 (负=实际偏长则下片缩短)
                _ad = _probe_dur(clip_path)
                if _ad > 0:
                    _tl_drift += render_dur - _ad

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
        # V23_KEEP_INTERMEDIATES=1 跳过清理 (2026-09-10): 后台沙箱对批量
        # 删除有 turn 级 50 次熔断 (SAFE_DELETE_BULK_CONFIRM_REQUIRED),
        # 无TTY 无法确认直接判死; 调试/后台跑批时置 1 保留中间产物。
        if os.environ.get("V23_KEEP_INTERMEDIATES") == "1":
            print("    [磁盘] V23_KEEP_INTERMEDIATES=1, 保留中间产物")
            return str(concat_output)
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
                      onset_times: list = None, out_frames: int = 0,
                      flash: str = "", trans: str = ""):
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
        vf_parts.append(f"fps={fps}")  # 2026-09-05 切点可见性修复: 源为60/30fps, 用fps滤镜
        #                              确定性重采样到目标fps(替代-r, 避免边界复制帧)
        vf = ",".join(vf_parts)

        cmd = [
            self.ffmpeg, "-y",
            "-ss", f"{start_time:.3f}",
            "-t", f"{read_dur:.3f}",  # 输入级读取限制：变速后输出=read_dur/speed=duration
            "-i", source,
            "-vf", vf,
            "-t", f"{duration:.4f}",  # 输出级硬裁: 保证帧数=round(duration*fps),
            #                             防止输入-t+setpts/帧量化的±1帧误差累积成切点漂移
            "-c:v", "libx264", "-preset", "slow",
            "-bf", "0",  # 2026-09-05 切点可见性修复: 禁B帧→流拷贝concat边界不复制帧
            "-b:v", "50M", "-maxrate", "60M", "-bufsize", "100M",
            "-minrate", "40M",
            "-pix_fmt", "yuv420p", "-an",
            "-movflags", "+faststart",
            output,
        ]

        if trans == "whip":
            # 甩镜转场 (2026-09-04 转场库②): 段落衔接镜头头3帧横向模糊甩动
            cmd[cmd.index("-vf") + 1] += (
                ",boxblur=luma_radius=20:luma_power=1:enable='lt(n,3)'")
        if trans == "glitch":
            # 故障转场 (2026-09-03 转场库①): snare 起始镜头头3帧 RGB 色散
            # — 与 kick 白黑闪构成两套打击语言
            cmd[cmd.index("-vf") + 1] += (
                ",rgbashift=rh=12:bv=-12:enable='lt(n,3)'")
        if flash in ("white", "black"):
            # 撞击帧 (2026-09-03 第一梯队①): 强鼓点起始镜头头 2 帧闪 —
            # 外网编辑打击感核心武器; fade from color 实现, 无需新资产
            _vi2 = cmd.index("-vf")
            cmd[_vi2 + 1] += (f",fade=t=in:st=0:d={2 / fps:.4f}:"
                              f"color={'white' if flash == 'white' else 'black'}")
        if out_frames > 0:
            # 精确帧数输出: -frames:v N 硬于 -t (编码器精确停在第 N 帧,
            # 消除 ±1 帧的时长→帧数换算误差)
            _ti = [i for i, a in enumerate(cmd) if a == "-t"]
            if len(_ti) >= 2:
                cmd[_ti[1]:_ti[1] + 2] = ["-frames:v", str(out_frames)]
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
    #  Phase 5a: BGM SFX 污染清理 (librosa HPSS)
    # ================================================================

    def _clean_bgm_sfx(self, bgm_path: str, work_dir: str) -> str:
        """HPSS 分离 BGM 中的 percussive SFX 污染

        独自升级.mp3 为动漫 OST, 含嵌入式打击/爆炸/冲击音效:
          - 82.7% percussive 能量集中在 <300Hz
          - 冲击类 SFX 在 100-500Hz 有谐波分量
        用 librosa HPSS 做激进分离, 对 percussive 全频段深度衰减,
        并对 harmonic 在 SFX 谐波频段做选择性压制.
        """
        import hashlib
        src_hash = hashlib.md5(
            str(Path(bgm_path).resolve()).encode()
        ).hexdigest()[:8]
        stem_name = Path(bgm_path).stem
        cleaned_path = Path(work_dir) / f"{stem_name}_sfx_cleaned_{src_hash}.wav"

        if cleaned_path.exists():
            print(f"    [SFX清理] 命中缓存: {cleaned_path.name}")
            return str(cleaned_path)

        try:
            import librosa
            import numpy as np
            import soundfile as sf
        except ImportError as e:
            print(f"    [SFX清理] librosa 未安装({e}), 退回原始 BGM")
            return bgm_path

        print(f"    [SFX清理] HPSS 音源分离中 (激进模式)...")

        try:
            y, sr = librosa.load(bgm_path, sr=44100, mono=False)
            if y.ndim == 1:
                y = np.stack([y, y])

            n_ch = y.shape[0]
            y_harmonic = np.zeros_like(y)
            y_perc = np.zeros_like(y)

            for ch in range(n_ch):
                y_h, y_p = librosa.effects.hpss(y[ch], margin=(2.0, 8.0))
                y_harmonic[ch] = y_h
                y_perc[ch] = y_p

            sfx_gain_low = 0.05
            sfx_gain_high = 0.20
            cutoff_hz = 300.0
            harm_suppress_low = 300.0
            harm_suppress_high = 800.0
            harm_gain = 0.7

            n_fft = 2048
            hop = n_fft // 4
            freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)
            cutoff_bin = int(np.searchsorted(freqs, cutoff_hz))
            harm_lo_bin = int(np.searchsorted(freqs, harm_suppress_low))
            harm_hi_bin = int(np.searchsorted(freqs, harm_suppress_high))

            for ch in range(n_ch):
                stft_p = librosa.stft(y_perc[ch], n_fft=n_fft, hop_length=hop)
                mag_p, phase_p = np.abs(stft_p), np.exp(1j * np.angle(stft_p))

                mask_p = np.full(mag_p.shape, sfx_gain_high)
                mask_p[:cutoff_bin, :] = sfx_gain_low

                transition = max(1, cutoff_bin // 4)
                ramp_start = max(0, cutoff_bin - transition)
                for b in range(ramp_start, min(cutoff_bin, mag_p.shape[0])):
                    t = (b - ramp_start) / max(1, cutoff_bin - ramp_start)
                    mask_p[b, :] = sfx_gain_low + (sfx_gain_high - sfx_gain_low) * t

                stft_clean_p = mag_p * mask_p * phase_p
                y_perc[ch] = librosa.istft(stft_clean_p, hop_length=hop, length=len(y[ch]))

                stft_h = librosa.stft(y_harmonic[ch], n_fft=n_fft, hop_length=hop)
                mag_h, phase_h = np.abs(stft_h), np.exp(1j * np.angle(stft_h))

                mask_h = np.ones(mag_h.shape)
                for b in range(harm_lo_bin, min(harm_hi_bin, mag_h.shape[0])):
                    mask_h[b, :] = harm_gain

                stft_clean_h = mag_h * mask_h * phase_h
                y_harmonic[ch] = librosa.istft(stft_clean_h, hop_length=hop, length=len(y[ch]))

            mixed = y_harmonic + y_perc
            mixed = np.clip(mixed.T, -1.0, 1.0)
            sf.write(str(cleaned_path), mixed, sr)

            print(f"    [SFX清理] 完成: percussive <{cutoff_hz}Hz->{sfx_gain_low:.0%}, "
                  f">{cutoff_hz}Hz->{sfx_gain_high:.0%}, "
                  f"harmonic {harm_suppress_low}-{harm_suppress_high}Hz->{harm_gain:.0%}")
            return str(cleaned_path)

        except Exception as e:
            print(f"    [SFX清理] HPSS 失败({e}), 退回原始 BGM")
            return bgm_path

    # ================================================================
    #  Phase 5b: BGM 混音
    # ================================================================

    def _mix_audio(self, video_path, bgm_path, output_path, bgm_start_sec, duration):
        """混合 BGM 到视频 (bgm_path 应为 SFX 清理后的文件)"""

        # 先检查视频是否有音频流
        has_audio = self._probe_has_audio(video_path)

        fade_in = 1.0
        fade_out = 1.5
        fade_out_start = max(0, duration - fade_out)

        if has_audio:
            # 2026-09-02: 静音原始视频音频(动漫素材自带爆炸/冲击等音效),
            # 仅使用 HPSS 清理后的 BGM — 之前 30% 原始音频是"音效污染"根因
            filter_complex = (
                f"[1:a]atrim=start={bgm_start_sec}:end={bgm_start_sec + duration},"
                f"asetpts=PTS-STARTPTS,"
                f"volume=0.8,"
                f"afade=t=in:st=0:d={fade_in},"
                f"afade=t=out:st={fade_out_start}:d={fade_out}[bgm]"
            )
            cmd = [
                self.ffmpeg, "-y",
                "-i", video_path,
                "-ss", "0", "-i", bgm_path,
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[bgm]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                output_path,
            ]
        else:
            cmd = [
                self.ffmpeg, "-y",
                "-i", video_path,
                "-ss", f"{bgm_start_sec}", "-i", bgm_path,
                "-map", "0:v", "-map", "1:a",
                "-af", (f"atrim=0:{duration},asetpts=PTS-STARTPTS,"
                        f"volume=0.8,"
                        f"afade=t=in:st=0:d={fade_in},"
                        f"afade=t=out:st={fade_out_start}:d={fade_out}"),
                "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                "-t", str(duration),
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
