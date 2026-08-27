# -*- coding: utf-8 -*-
"""
Resolve → AE → Resolve 混合工作流编排器
=========================================

实现专业级三段式工作流（见 docs 中的顺序结论）：
    Stage A（达芬奇/引擎侧）：踩拍剪辑 + 变速 + 转场 → 高质量中间文件
    Stage B（AE 侧）       ：导入中间文件 → 建合成 → 文字动画/标题 → 渲染
                            （AE 离线时自动降级 FFmpeg drawtext 文字动画）
    Stage C（达芬奇/引擎侧）：全片 LUT+色轮调色 → BGM 混音淡出 → 成片

顺序铁律（不可颠倒）：
    1. 变速必须在 AE 之前（时间决定文字动画节奏）
    2. AE 合成在调色之前（画面锁定 Picture Lock）
    3. 调色最后（全局终饰，只执行一次）

依赖：
    - integrations/vrs_resolve_bridge.py（VrsResolveBridge）
    - .ae-mcp-bridge/ 文件轮询协议（踩坑档案 docs/ae_bridge_lessons.md）

用法：
    python integrations/resolve_ae_resolve_pipeline.py --clips C:\\VinlandClips --bgm "..."
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, List, Optional

from loguru import logger

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BRIDGE_DIR = os.path.join(_PROJECT_ROOT, ".ae-mcp-bridge")
_CMD_FILE = os.path.join(_BRIDGE_DIR, "ae_command.json")
_RES_FILE = os.path.join(_BRIDGE_DIR, "ae_result.json")


def _load_module(module_name: str, rel_path: str):
    file_path = os.path.join(_PROJECT_ROOT, rel_path)
    if not os.path.exists(file_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"加载模块失败 {rel_path}: {exc}")
        sys.modules.pop(module_name, None)
        return None


_bridge_mod = _load_module("_hybrid_vrs_bridge", "integrations/vrs_resolve_bridge.py")
if _bridge_mod is None:
    raise ImportError("无法加载 integrations/vrs_resolve_bridge.py")

VrsResolveBridge = _bridge_mod.VrsResolveBridge
ResolveError = _bridge_mod.ResolveError

# 智能导演系统（镜头感知驱动的文字动画决策）
_sd_mod = _load_module("_smart_director", "integrations/smart_director.py")
if _sd_mod is not None:
    build_smart_text_jsx = _sd_mod.build_smart_text_jsx
    analyze_shot_motion = _sd_mod.analyze_shot_motion
    analyze_scene_complexity = _sd_mod.analyze_scene_complexity
    analyze_color_richness = _sd_mod.analyze_color_richness
    decide_intensity = _sd_mod.decide_intensity
    get_last_run_stats = getattr(_sd_mod, "get_last_run_stats", None)
else:
    build_smart_text_jsx = None  # type: ignore
    analyze_color_richness = None
    get_last_run_stats = None

# 【P2-2】镜头特征 → 场景标签推断（驱动 SmartMatcher 精确表匹配）
_SCENE_TAG_BY_FEATURE = {
    ("intense", "rich"): "battle",
    ("intense", "medium"): "battle",
    ("intense", "poor"): "industrial",
    ("moderate", "rich"): "neon",
    ("moderate", "medium"): "cinematic",
    ("moderate", "poor"): "elegant",
    ("gentle", "rich"): "magic",
    ("gentle", "medium"): "elegant",
    ("gentle", "poor"): "ink_wash",
}


def _infer_scene_tag(intensity: str, color_richness: str) -> str:
    """【P2-2】根据镜头强度+色彩丰富度推断场景标签"""
    return _SCENE_TAG_BY_FEATURE.get(
        (intensity, color_richness), "cinematic")


# -----------------------------------------------------------------------------
# AE Bridge 客户端（防竞态实现，遵循 ae_bridge_lessons.md 第1节）
# -----------------------------------------------------------------------------
class AEBridgeLite:
    """极简 AE Bridge 客户端：executeAtomScript 专用，带 mtime 防竞态。"""

    def __init__(self):
        self._last_cmd_wall = 0.0  # 上一次写入的真实壁钟时间（time.time）

    def is_online(self, timeout: float = 8.0) -> bool:
        r = self._send({"command": "ping", "args": {}}, timeout)
        return r.get("status") == "success"

    def execute_jsx(self, jsx_body: str, timeout: float = 60.0,
                    retries: int = 2) -> Dict[str, Any]:
        """执行 JSX 函数体（自动加 return 前缀，与 return 同行避免 ASI 陷阱）。

        【实测踩坑】文件轮询存在偶发命令丢失竞态：ping 正常但紧随的
        JSX 命令 processed 恒为 None（写入与轮询采样竞态）。因此超时后
        先 ping 探活再重发同一命令；输出路径带 uuid 时重发无副作用。
        """
        script = "return " + jsx_body.replace("\n", " ")
        payload = {"command": "executeAtomScript", "args": {"script": script}}
        r = self._send(payload, timeout)
        for _ in range(retries):
            if r.get("status") == "success" and r.get("result") is not None:
                return r
            # 疑似命令丢失：探活后重发（AE 忙/弹窗导致的真卡死会再次超时，
            # 不会造成重复执行风险——重发前上一条命令已确认无响应）
            if not self.is_online(timeout=8.0):
                break  # AE 真离线/卡死，重发无意义
            logger.warning("AE Bridge 命令疑似丢失，重发同一 JSX 命令")
            r = self._send(payload, timeout)
        return r

    def _send(self, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        os.makedirs(_BRIDGE_DIR, exist_ok=True)
        # 记录发送前结果文件 mtime，要求严格增大才读取（防读旧结果）
        res_mtime_before = os.path.getmtime(_RES_FILE) if os.path.exists(_RES_FILE) else 0.0

        # 【竞态根治】串行间隔必须在写入之前执行：
        # 旧实现把等待放在写入之后，导致前一条命令发出 <1s 就写下一条，
        # listener 恰在 truncate 与 json.dump 之间采样到残缺 JSON → 命令丢失。
        wait = self._last_cmd_wall + 1.2 - time.time()
        if wait > 0:
            time.sleep(wait)
        self._last_cmd_wall = time.time()

        payload = dict(payload)
        payload.setdefault("status", "pending")
        payload["timestamp"] = time.time()
        # 【竞态根治】原子写入：先写临时文件再 os.replace，
        # listener 任何时刻读到的都是完整 JSON（旧或新），永不残缺。
        # 不能用 os.utime 强制 mtime 递增：Python 时钟与 Windows 文件时间
        # 可能存在分钟级偏差，utime 会把 mtime 设到"过去"导致桥接永久卡死。
        tmp_file = _CMD_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        # Windows 上 AE listener 恰好在读目标文件时 os.replace 会报 WinError 5，
        # 短重试；持续失败则降级为直接写（写前间隔已保证 listener 不在
        # 活跃轮询窗口内，读残缺风险极低）。
        for _ in range(10):
            try:
                os.replace(tmp_file, _CMD_FILE)
                break
            except PermissionError:
                time.sleep(0.1)
        else:
            with open(_CMD_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            try:
                os.remove(tmp_file)
            except OSError:
                pass

        start = time.time()
        while time.time() - start < timeout:
            try:
                if os.path.exists(_RES_FILE) and os.path.getmtime(_RES_FILE) > res_mtime_before:
                    with open(_RES_FILE, "r", encoding="utf-8") as f:
                        r = json.load(f)
                    if r.get("status") in ("success", "error"):
                        return r
            except (json.JSONDecodeError, OSError):
                pass
            time.sleep(0.4)
        return {"status": "error", "error": f"AE Bridge 超时 ({timeout}s)"}


# -----------------------------------------------------------------------------
# 混合工作流编排器
# -----------------------------------------------------------------------------
class ResolveAeResolvePipeline:
    """Resolve → AE → Resolve 三段式混合工作流。"""

    COMP_NAME = "hybrid_comp"

    def __init__(self, bridge: Optional[Any] = None):
        self.vrs = bridge or VrsResolveBridge()
        self.engine = self.vrs.engine
        self.ae = AEBridgeLite()
        self.last_report: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # FFmpeg-only 降级模式：使用 ProductionDirector
    # ------------------------------------------------------------------
    def run_ffmpeg_only(
        self,
        clip_paths: List[str],
        bgm_path: str,
        output_path: str,
        lyrics: Optional[List] = None,
        bgm_start_sec: float = 0.0,
        target_duration: Optional[float] = None,
        fps: int = 24,
        target_ip: str = "",
        strict: bool = True,
        allow_mixed: bool = False,
        verify_content: bool = True,
    ) -> str:
        """纯 FFmpeg 降级模式 — 使用 ProductionDirector 端到端渲染。

        当 Resolve/AE 均离线时，自动调用此方法。
        也可主动调用以跳过专业软件依赖。

        Args:
            target_ip: 目标IP/作品名，非空时只使用匹配该IP的素材
            strict: 严格模式，无匹配素材时报错而非降级
            allow_mixed: 是否允许多IP混剪类素材
            verify_content: 是否对成片进行VLM内容复核
        """
        logger.info(f"使用 ProductionDirector FFmpeg 降级模式" +
                    (f" (目标IP: {target_ip})" if target_ip else ""))
        from ai.production_director import ProductionDirector

        output_dir = os.path.dirname(output_path)
        output_name = os.path.basename(output_path)
        os.makedirs(output_dir, exist_ok=True)

        director = ProductionDirector()
        result = director.render(
            video_sources=list(clip_paths),
            bgm_path=bgm_path,
            output_dir=output_dir,
            output_name=output_name,
            lyrics=lyrics,
            bgm_start_sec=bgm_start_sec,
            target_duration=target_duration,
            fps=fps,
            target_ip=target_ip,
            strict=strict,
            allow_mixed=allow_mixed,
            verify_content=verify_content,
        )

        self.last_report = {
            "mode": "ffmpeg_only",
            "output": result,
            "director_version": "v4-strict",
            "target_ip": target_ip,
            "strict": strict,
        }
        return result

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def run(self, clip_paths: List[str], bgm_path: str, output_path: str,
            title: str = "AMV MIX", subtitle: str = "",
            beat_group: int = 4, transitions: Optional[List[str]] = None,
            lut_path: Optional[str] = None,
            speed_ramp: bool = True, fps: int = 24,
            beat_offset: float = 0.0,
            output_dir: str = "") -> str:
        """
        三段式端到端。Returns 最终成片路径。
    
        Args:
            title/subtitle: AE 文字动画内容（AE 离线时降级 FFmpeg drawtext）
            speed_ramp: Stage A 是否对前两个素材施加贝塞尔变速（剪辑前决策）
        """
        work = os.path.join(self.engine._temp_dir,
                            f"hybrid_{uuid.uuid4().hex[:8]}")
        os.makedirs(work, exist_ok=True)
        t0 = time.time()
    
        # ---------- 【第四轮新增】逐镜头差异化调色（Stage A 前） ----------
        # 在剪辑前对每个素材施加风格化调色，确保每个镜头有独特的色彩倾向
        clips_for_edit = list(clip_paths)
        graded_clips: List[str] = []
        for ci, clip in enumerate(clips_for_edit):
            graded = self._grade_clip_for_style(clip, ci, work)
            graded_clips.append(graded)
        clips_for_edit = graded_clips
        logger.info(f"逐镜头差异化调色: {len(clips_for_edit)} 个素材已施加风格化调色")
    
        # ---------- Stage A: 剪辑+变速+转场 ----------
        logger.info("Stage A: 踩拍剪辑 + 变速 + 转场")
        # 变速铁律：变速是“剪辑前决策”，作用于单个素材片段（而非成片），
        # 否则会破坏已对齐的切点节拍。
        if speed_ramp and len(clips_for_edit) >= 2:
            for ci, curve in ((0, [(0.0, 1.0), (0.5, 1.35), (1.0, 1.0)]),
                              (1, [(0.0, 1.0), (0.5, 0.75), (1.0, 1.0)])):
                ramped = os.path.join(work, f"clip_ramp_{ci}.mp4")
                self.engine.dynamic_speed_ramp(
                    clips_for_edit[ci], ramped, control_points=curve, fps=fps)
                clips_for_edit[ci] = ramped
            logger.info("Stage A: 前两个素材已施加贝塞尔变速（1.35x/0.75x）")

        stage_a = self.vrs.build_vrs_montage(
            clips_for_edit, bgm_path, os.path.join(work, "stage_a.mp4"),
            beat_group=beat_group, transitions=transitions,
            lut_path=None,  # 调色留到 Stage C（铁律3）
            enable_flash=False, enable_bounce=True, fps=fps,
            beat_offset=beat_offset)

        dur_a = self.engine._get_media_duration(stage_a) or 0.0
        logger.info(f"Stage A 完成: {stage_a} ({dur_a:.2f}s)")

        # 检测实际切点（供 Stage B 文字密度优化使用）
        cut_times = self._detect_cuts(stage_a)
        logger.info(f"Stage A 切点检测: {len(cut_times)} 个切点")

        # ---------- 智能导演：逐镜头特征提取 ----------
        shot_analysis: List[Dict[str, Any]] = []
        if build_smart_text_jsx is not None and cut_times:
            # 切点之间的片段就是各镜头段落
            for si, ct in enumerate(cut_times):
                ct_end = cut_times[si + 1] if si + 1 < len(cut_times) else dur_a
                if ct_end - ct < 0.3:
                    shot_analysis.append({"motion": 0.0, "complexity": "low", "intensity": "gentle"})
                    continue
                # 从 stage_a 中截取该段落做快速分析
                seg_path = os.path.join(work, f"shot_analysis_{si}.mp4")
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-ss", f"{ct:.3f}", "-i", stage_a,
                         "-t", f"{ct_end - ct:.3f}", "-c", "copy", "-an",
                         seg_path],
                        check=True, capture_output=True, timeout=30)
                    motion = analyze_shot_motion(seg_path)
                    complexity = analyze_scene_complexity(seg_path)
                    # 【第四轮新增】色彩丰富度分析
                    color_rich = "medium"
                    if analyze_color_richness is not None:
                        color_rich = analyze_color_richness(seg_path)
                    intensity = decide_intensity(motion, complexity, color_rich)
                    shot_analysis.append({
                        "motion": motion, "complexity": complexity,
                        "intensity": intensity, "color_richness": color_rich,
                        # 【P2-2】场景标签推断 → SmartMatcher 精确表
                        "scene_tag": _infer_scene_tag(intensity, color_rich)})
                except Exception:
                    shot_analysis.append({"motion": 0.0, "complexity": "medium", "intensity": "moderate", "scene_tag": "cinematic"})
                finally:
                    try:
                        os.remove(seg_path)
                    except OSError:
                        pass
            logger.info(f"智能导演: {len(shot_analysis)} 个镜头分析完成")
            for si, sa in enumerate(shot_analysis):
                logger.info(f"  shot#{si}: motion={sa['motion']:.2f} "
                            f"complexity={sa['complexity']} "
                            f"color={sa.get('color_richness', '?')} "
                            f"→ {sa['intensity']}")

        # ---------- Stage B: AE 文字动画（智能导演驱动）----------
        logger.info("Stage B: AE 文字动画/标题（智能导演模式）")
        ae_used = False
        if self.ae.is_online():
            try:
                stage_b = self._ae_title_pass(stage_a, work, title, subtitle,
                                              dur_a, fps, cut_times,
                                              shot_analysis=shot_analysis)
                ae_used = True
                logger.info(f"Stage B (AE) 完成: {stage_b}")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"AE 文字环节失败，降级 FFmpeg: {exc}")
                stage_b = self._ffmpeg_title_pass(stage_a, work, title,
                                                  subtitle, dur_a, fps)
        else:
            logger.warning("AE Bridge 离线，降级 FFmpeg drawtext 文字动画")
            stage_b = self._ffmpeg_title_pass(stage_a, work, title,
                                              subtitle, dur_a, fps)

        # ---------- Stage C: 逐镜头自适应调色 + BGM 混音 ----------
        logger.info("Stage C: 自适应调色 + BGM 混音")
        self._grade_and_mix(stage_b, bgm_path, output_path, lut_path,
                            cut_times=cut_times)

        self.last_report = {
            "output": output_path,
            "duration": self.engine._get_media_duration(output_path) or 0.0,
            "ae_used": ae_used,
            "elapsed_s": round(time.time() - t0, 1),
            "stage_a_duration": dur_a,
        }
        # 【P2-2】文字层统计回传: 三维特效组合使用情况 (AE→Resolve 传递验证)
        if get_last_run_stats is not None:
            try:
                sd_stats = get_last_run_stats()
                self.last_report["text_layer_stats"] = {
                    "combos_used": sd_stats.get("text_combos_used", []),
                    "combo_count": sd_stats.get("text_combo_count", 0),
                    "presets_used": sd_stats.get("presets_used", []),
                    "scene_tags": [sa.get("scene_tag", "")
                                   for sa in shot_analysis],
                }
            except Exception:  # noqa: BLE001
                pass
        logger.info(f"混合工作流完成: {output_path} "
                    f"({self.last_report['duration']:.1f}s, AE={ae_used}, "
                    f"{self.last_report['elapsed_s']}s)")
        return output_path

    # ------------------------------------------------------------------
    # 【第四轮新增】逐镜头差异化调色
    # ------------------------------------------------------------------
    # 每个镜头根据序号获得不同的色彩风格，避免“全部同一滤镜”的单调感。
    # 调色分两层：分镜层做差异化（Stage A 前），全片层做统一（Stage C）。
    _SHOT_COLOR_PROFILES = [
        # 暖调高对比（戏剧感）
        {"hue_s": 1.3, "eq_sat": 1.3, "contrast": 1.06,
         "cb": "rs=-0.03:gs=0.01:bs=0.06:rh=0.08:gh=-0.02:bh=-0.06",
         "label": "warm_dramatic"},
        # 青橙调色（经典 AMV）
        {"hue_s": 1.2, "eq_sat": 1.2, "contrast": 1.04,
         "cb": "rs=-0.06:gs=0.02:bs=0.08:rh=0.05:gh=0.01:bh=-0.04",
         "label": "teal_orange"},
        # 冷调低饱和（赛博朋克）
        {"hue_s": 1.1, "eq_sat": 1.1, "contrast": 1.05,
         "cb": "rs=-0.08:gs=0.03:bs=0.10:rh=-0.03:gh=0.05:bh=0.08",
         "label": "cyber_cool"},
        # 暖金调（史诗感）
        {"hue_s": 1.25, "eq_sat": 1.25, "contrast": 1.03,
         "cb": "rs=0.02:gs=0.01:bs=-0.02:rh=0.10:gh=0.04:bh=-0.06",
         "label": "golden_epic"},
        # 冷蓝调（科技感）
        {"hue_s": 1.15, "eq_sat": 1.15, "contrast": 1.04,
         "cb": "rs=-0.05:gs=0.0:bs=0.06:rh=-0.04:gh=0.02:bh=0.06",
         "label": "cool_blue"},
        # 柔和暖调（回忆感）
        {"hue_s": 1.1, "eq_sat": 1.1, "contrast": 1.02,
         "cb": "rs=0.04:gs=0.02:bs=-0.02:rh=0.06:gh=0.03:bh=-0.03",
         "label": "soft_warm"},
    ]

    def _grade_clip_for_style(self, clip_path: str, idx: int,
                               work_dir: str) -> str:
        """对单个素材施加差异化调色，输出到 work_dir。"""
        profile = self._SHOT_COLOR_PROFILES[idx % len(self._SHOT_COLOR_PROFILES)]
        out = os.path.join(work_dir, f"graded_{idx}_{profile['label']}.mp4")
        if os.path.exists(out):
            return out
        vf = (f"hue=s={profile['hue_s']},"
              f"eq=saturation={profile['eq_sat']}:contrast={profile['contrast']},"
              f"colorbalance={profile['cb']}")
        codec = self.engine._get_encoder_args(quality="high")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", clip_path, "-vf", vf,
                 *shlex.split(codec, posix=False), "-an", out],
                check=True, capture_output=True, timeout=300)
        except subprocess.CalledProcessError:
            logger.warning(f"逐镜头调色失败，使用原始素材: {clip_path}")
            return clip_path
        if not os.path.exists(out):
            return clip_path
        logger.debug(f"  clip#{idx}: {profile['label']} → {out}")
        return out

    # ------------------------------------------------------------------
    # 切点检测（供 Stage B 文字密度优化）
    # ------------------------------------------------------------------
    def _detect_cuts(self, video_path: str,
                     threshold: float = 0.25) -> List[float]:
        """ffmpeg scene 检测实际切点时间戳（去重 0.15s 窗口）。"""
        cmd = ["ffmpeg", "-i", video_path,
               "-vf", f"select=gt(scene\\,{threshold}),showinfo",
               "-f", "null", "-"]
        r = subprocess.run(cmd, capture_output=True,
                           encoding="utf-8", errors="ignore", timeout=300)
        cuts = sorted(float(t) for t in re.findall(
            r'pts_time:([\d.]+)', r.stderr))
        merged: List[float] = []
        for t in cuts:
            if not merged or t - merged[-1] > 0.15:
                merged.append(t)
        return merged

    # ------------------------------------------------------------------
    # Stage B 路径1：AE 文字动画（智能导演驱动，每切点多样化动画）
    # ------------------------------------------------------------------
    def _ae_title_pass(self, footage: str, work: str, title: str,
                       subtitle: str, duration: float, fps: int,
                       cut_times: Optional[List[float]] = None,
                       shot_analysis: Optional[List[Dict[str, Any]]] = None) -> str:
        """AE 导入中间文件 → 建合成 → 智能文字动画 → 渲染。

        【第三轮优化】文字动画由智能导演系统驱动：
        - 每个切点对应一个文字动画，类型/位置/节奏各不相同
        - 每个文字有完整的"入场→展示→出场"生命周期，禁止常驻
        - 动画类型参考 ae/presets/ 预设库（bounce/slide/rotate/drop/fade）
        - 动画强度根据镜头运动特征智能决策
        """
        footage_ff = footage.replace("\\", "/")
        out_base = os.path.join(work, f"stage_b_{uuid.uuid4().hex[:6]}")
        out_mov = out_base.replace("\\", "/") + ".mov"

        comp_tag = uuid.uuid4().hex[:6]
        comp_name = f"{self.COMP_NAME}_{comp_tag}"

        # ---------- 主标题：有入场+出场，不常驻 ----------
        title_dur = min(2.0, duration * 0.15)
        title_jsx = (
            f'var t1=c.layers.addText({json.dumps(title)});'
            "var td=t1.property('Source Text').value;"
            "td.fontSize=92;td.fillColor=[1,1,1];td.font='MicrosoftYaHei';"
            "td.strokeWidth=0;td.fauxBold=true;"
            "t1.property('Source Text').setValue(td);"
            "t1.property('Position').setValue([c.width/2,c.height*0.5]);"
            f"t1.property('Scale').setValuesAtTimes([0,{title_dur * 0.4:.3f},{title_dur:.3f}],"
            f"[[30,30],[115,115],[100,100]]);"
            f"t1.property('Opacity').setValuesAtTimes("
            f"[0,{title_dur * 0.3:.3f},{title_dur * 0.7:.3f},{title_dur:.3f}],"
            f"[0,100,100,0]);"
        )

        # ---------- 副标题（可选）：同样有出场 ----------
        sub_jsx = ""
        if subtitle:
            sub_dur = min(1.5, duration * 0.1)
            sub_jsx = (
                f'var t2=c.layers.addText({json.dumps(subtitle)});'
                "var td2=t2.property('Source Text').value;"
                "td2.fontSize=42;td2.fillColor=[1,0.9,0.65];td2.font='MicrosoftYaHei';"
                "t2.property('Source Text').setValue(td2);"
                "t2.property('Position').setValue([c.width/2,c.height*0.62]);"
                f"t2.property('Opacity').setValuesAtTimes("
                f"[{title_dur:.3f},{title_dur + 0.3:.3f},{title_dur + sub_dur - 0.3:.3f},{title_dur + sub_dur:.3f}],"
                f"[0,100,100,0]);"
            )

        # ---------- 智能导演：每切点多样化文字动画 ----------
        text_jsx = ""
        if cut_times and build_smart_text_jsx is not None:
            text_jsx = build_smart_text_jsx(cut_times, duration, shot_analysis)
            logger.info(f"智能导演: 生成 {len(cut_times)} 个多样化文字动画")
        elif cut_times:
            # 降级：智能导演不可用时，使用简单的缩放淡入淡出
            text_jsx = self._build_fallback_text_jsx(cut_times, duration)

        jsx = (
            "(function(){"
            "try{"
            "for(var qi=app.project.renderQueue.numItems;qi>=1;qi--){"
            "app.project.renderQueue.item(qi).remove();}"
            f'var io=new ImportOptions(File("{footage_ff}"));'
            "var ft=app.project.importFile(io);"
            f"var c=app.project.items.addComp('{comp_name}',1920,1080,1.0,{duration:.3f},{fps});"
            "var vl=c.layers.add(ft);"
            "vl.startTime=0;"
            + title_jsx + sub_jsx + text_jsx +
            "var rqi=app.project.renderQueue.items.add(c);"
            "var om=rqi.outputModule(1);"
            "om.format='QuickTime';"
            f'om.file=new File("{out_mov}");'
            "app.project.renderQueue.render();"
            "rqi.remove();"
            "c.remove();ft.remove();"
            f'return JSON.stringify({{success:true,data:{{out:"{out_mov}"}}}});'
            "}catch(e){"
            "return JSON.stringify({success:false,error:String(e)});"
            "}"
            "})();"
        )
        r = self.ae.execute_jsx(jsx, timeout=600)
        inner = r.get("result")
        for _ in range(2):
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except json.JSONDecodeError:
                    break
            elif isinstance(inner, dict) and "result" in inner and "success" not in inner:
                inner = inner.get("result")
            else:
                break
        if not (isinstance(inner, dict) and inner.get("success", False)):
            raise RuntimeError(f"AE 渲染失败: {inner or r}")
        out_actual = None
        for cand in (out_mov, out_base + ".mp4"):
            if os.path.exists(cand):
                out_actual = cand
                break
        if out_actual is None:
            raise RuntimeError(f"AE 输出文件缺失: {out_mov}")

        out_mp4 = os.path.join(work, "stage_b.mp4")
        codec = self.engine._get_encoder_args(quality="high")
        subprocess.run(
            ["ffmpeg", "-y", "-i", out_actual,
             *shlex.split(codec, posix=False), "-an", out_mp4],
            check=True, capture_output=True, timeout=900)
        if not os.path.exists(out_mp4):
            raise RuntimeError("AE 输出转码失败")
        return out_mp4

    # ------------------------------------------------------------------
    # 降级文字动画（智能导演不可用时）
    # ------------------------------------------------------------------
    def _build_fallback_text_jsx(self, cut_times: List[float],
                                  duration: float) -> str:
        """简单缩放+淡入淡出文字动画（每切点一个，有完整出入场）。"""
        labels = ["\u6226\u3044", "VINLAND", "SAGA", "\u51b0\u6d77\u6218\u8a18",
                  "AMV", "\u30c8\u30eb\u30d5\u30a3\u30f3", "\u7206\u70c8",
                  "\u6fc0\u71c3", "EPIC", "\u9583\u5149"]
        parts: list = []
        for ci, ct in enumerate(cut_times):
            seg_end = cut_times[ci + 1] if ci + 1 < len(cut_times) else duration
            seg_dur = seg_end - ct
            if seg_dur < 0.25:
                continue
            label = labels[ci % len(labels)]
            t_out = ct + seg_dur * 0.75
            if t_out - ct < 0.2:
                continue
            parts.append(
                f"var tt{ci}=c.layers.addText({json.dumps(label)});"
                f"var td{ci}=tt{ci}.property('Source Text').value;"
                f"td{ci}.fontSize=64;td{ci}.fillColor=[1,1,1];"
                f"td{ci}.font='MicrosoftYaHei';"
                f"tt{ci}.property('Source Text').setValue(td{ci});"
                f"tt{ci}.property('Position').setValue([c.width/2,c.height/2]);"
                f"tt{ci}.property('Scale').setValuesAtTimes("
                f"[{ct:.3f},{ct + 0.15:.3f},{t_out:.3f}],"
                f"[[70,70],[112,112],[100,100]]);"
                f"tt{ci}.property('Opacity').setValuesAtTimes("
                f"[{ct:.3f},{ct + 0.1:.3f},{t_out - 0.1:.3f},{t_out:.3f}],"
                f"[0,100,100,0]);"
            )
        return "".join(parts)

    # ------------------------------------------------------------------
    # Stage B 路径2：FFmpeg drawtext 降级（AE 离线时）
    # ------------------------------------------------------------------
    def _ffmpeg_title_pass(self, src: str, work: str, title: str,
                           subtitle: str, duration: float, fps: int) -> str:
        """drawtext 文字动画：标题 0~0.85s 淡入放大，副标题 0.9~1.6s 淡入。"""
        out = os.path.join(work, "stage_b.mp4")
        # Windows 下 fontfile 必须用正斜杠并转义冒号
        font = "C\\:/Windows/Fonts/msyh.ttc"
        end_show = max(duration - 0.5, 2.0)
        t_expr = (f"if(lt(t,0.35),0,if(lt(t,0.85),(t-0.35)/0.5,1))*"
                  f"if(gt(t,{end_show:.2f}),max(0,1-(t-{end_show:.2f})/0.5),1)")
        vf = (f"drawtext=text='{title}':fontfile='{font}':"
              f"fontsize=92:fontcolor=white:borderw=3:bordercolor=black@0.6:"
              f"x=(w-text_w)/2:y=(h/2)-text_h/2:alpha='{t_expr}'")
        if subtitle:
            s_expr = "if(lt(t,1.0),0,if(lt(t,1.7),(t-1.0)/0.7,1))"
            vf += (f",drawtext=text='{subtitle}':fontfile='{font}':"
                   f"fontsize=42:fontcolor=0xFFE6A6:borderw=2:bordercolor=black@0.5:"
                   f"x=(w-text_w)/2:y=h*0.62:alpha='{s_expr}'")
        codec = self.engine._get_encoder_args(quality="high")
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-vf", vf,
             *shlex.split(codec, posix=False), "-an", out],
            check=True, capture_output=True,
            encoding="utf-8", errors="ignore", timeout=900)
        if not os.path.exists(out):
            raise RuntimeError("FFmpeg 文字环节失败")
        return out

    # ------------------------------------------------------------------
    # Stage C: 轻统一调色 + BGM 混音（第四轮：不再全片重调色）
    # ------------------------------------------------------------------
    def _grade_and_mix(self, src: str, bgm_path: str, output_path: str,
                       lut_path: Optional[str],
                       cut_times: Optional[List[float]] = None) -> None:
        """Stage C 自适应调色 + 混音。

        【第五轮升级】引入 AdaptiveColorGrader 逐镜头色彩分析 + 自适应调色：
        - 有 cut_times 时：逐镜头分析色彩特征，为每段选择最优调色风格
        - 无 cut_times 时：退化为轻统一调色（向后兼容）
        - 色彩冲突自动修正（暗场景不叠高饱和、冷色不叠暖色等）
        """
        from integrations.adaptive_color_grader import AdaptiveColorGrader

        grader = AdaptiveColorGrader()
        total_dur = self.engine._get_media_duration(src) or 0.0

        # 尝试逐镜头自适应调色
        adaptive_vf = None
        grading_plan = []
        if cut_times and len(cut_times) >= 2:
            try:
                # 分析每个镜头段落的色彩特征
                shots = []
                for i, ct in enumerate(cut_times):
                    ct_end = cut_times[i + 1] if i + 1 < len(cut_times) else total_dur
                    seg_dur = ct_end - ct
                    if seg_dur < 0.1:
                        continue
                    info = grader.analyze_shot_color(src, i, ct, seg_dur)
                    shots.append(info)

                if shots:
                    # 生成调色方案
                    grading_plan = grader.compute_grading_plan(shots)
                    # 生成逐镜头 filter graph
                    adaptive_vf = grader.build_per_shot_filter(grading_plan, total_dur)

                    # 统计调色风格分布
                    styles_used = set(p["style"] for p in grading_plan)
                    logger.info(f"自适应调色: {len(shots)} 个镜头, "
                                f"{len(styles_used)} 种风格: {', '.join(styles_used)}")
            except Exception as e:
                logger.warning(f"自适应调色失败，降级统一调色: {e}")
                adaptive_vf = None

        if adaptive_vf is None:
            # 降级：轻统一调色（向后兼容）
            vf_parts = []
            if lut_path and os.path.exists(lut_path):
                lut_ff = lut_path.replace("\\", "/").replace(":", "\\:")
                vf_parts.append(f"lut3d='{lut_ff}'")
            vf_parts.append("hue=s=1.15")
            vf_parts.append("eq=saturation=1.15:contrast=1.02:brightness=0.005")
            vf_parts.append("colorbalance=rs=-0.02:gs=0.01:bs=0.03:rh=0.02:gh=0.01:bh=-0.02")
            video_filter = ",".join(vf_parts)
        else:
            video_filter = adaptive_vf

        codec = self.engine._get_encoder_args(quality="high")
        fade_start = max(0.0, total_dur - 1.5)

        # 构建 filter_complex
        if ";" in video_filter:
            # 逐镜头分段滤镜（已包含 [outv] 标签）
            fc = f"{video_filter};[1:a]afade=t=out:st={fade_start:.2f}:d=1.5[a]"
        else:
            # 简单全片滤镜
            fc = f"[0:v]{video_filter}[v];[1:a]afade=t=out:st={fade_start:.2f}:d=1.5[a]"

        codec_args = shlex.split(codec, posix=False)
        cmd = ["ffmpeg", "-y", "-i", src, "-i", bgm_path,
               "-filter_complex", fc,
               "-map", "[outv]", "-map", "[a]", *codec_args,
               "-c:a", "aac", "-b:a", "192k",
               "-shortest", output_path]
        # 如果是简单滤镜，用 -vf 更高效
        if ";" not in video_filter:
            cmd = ["ffmpeg", "-y", "-i", src, "-i", bgm_path,
                   "-vf", video_filter,
                   "-filter_complex",
                   f"[1:a]afade=t=out:st={fade_start:.2f}:d=1.5[a]",
                   "-map", "0:v", "-map", "[a]", *codec_args,
                   "-c:a", "aac", "-b:a", "192k",
                   "-shortest", output_path]

        subprocess.run(cmd, check=True, capture_output=True,
                       timeout=900)
        if not os.path.exists(output_path):
            raise ResolveError("Stage C 调色混音失败")

        # 记录调色风格到 last_report（供反馈闭环消费）
        if grading_plan:
            self._grading_styles_used = [p["style"] for p in grading_plan]
        else:
            self._grading_styles_used = ["uniform"]


# -----------------------------------------------------------------------------
# CLI 入口
# -----------------------------------------------------------------------------
def _main():
    import argparse
    parser = argparse.ArgumentParser(description="Resolve→AE→Resolve 混合工作流")
    parser.add_argument("--clips", required=True, help="素材目录或逗号分隔文件列表")
    parser.add_argument("--bgm", required=True, help="BGM 音频路径")
    parser.add_argument("--output", default=os.path.join(
        _PROJECT_ROOT, "output", "hybrid_pipeline", "hybrid_final.mp4"))
    parser.add_argument("--title", default="AMV MIX")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--beat-group", type=int, default=4)
    parser.add_argument("--transitions", default="whip_pan,glitch,flash,zoom")
    parser.add_argument("--lut", default=None)
    args = parser.parse_args()

    if os.path.isdir(args.clips):
        exts = {'.mp4', '.mov', '.mkv'}
        clips = sorted(os.path.join(args.clips, f) for f in os.listdir(args.clips)
                       if os.path.splitext(f)[1].lower() in exts)[:8]
    else:
        clips = [c.strip() for c in args.clips.split(",") if c.strip()]

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    pipe = ResolveAeResolvePipeline()
    out = pipe.run(clips, args.bgm, args.output,
                   title=args.title, subtitle=args.subtitle,
                   beat_group=args.beat_group,
                   transitions=args.transitions.split(","),
                   lut_path=args.lut)
    print(f"DONE: {out}")
    print(json.dumps(pipe.last_report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
