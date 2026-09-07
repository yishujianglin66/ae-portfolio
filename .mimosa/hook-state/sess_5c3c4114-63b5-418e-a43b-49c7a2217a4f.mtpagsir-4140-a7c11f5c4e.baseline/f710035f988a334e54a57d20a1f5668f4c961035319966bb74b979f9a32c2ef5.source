#!/usr/bin/env python3
"""
视频处理统一管线 v2.2
======================
整合 PySceneDetect + video-use + DaVinci Resolve 引擎 + OpenMontage 风格
+ 多线程全阶段并行执行

能力:
- 自动场景检测（PySceneDetect）
- FFmpeg 快速预览调色（video-use grade.py）
- Resolve 专业 DCTL/LUT + Fusion 调色
- 智能调色推荐（cv2 分析 → 自动参数映射）
- FFmpeg 光流补帧（minterpolate）
- OpenMontage 风格预设（ghibli/premium/clean/flat/dramatic/vivid）
- 一键全流程：检测 → 分析 → 预览 → 调色 → 补帧 → 渲染
- v2.2 新增：多线程 DAG 并行执行（perceive ‖ analyze → plan → execute → render → verify）
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations.davinci_fuscript import (
    ResolveColorEngine, ColorGradeConfig, DCTL_PRESET_MAP
)

# video-use helpers 路径
VIDEO_USE_DIR = Path(__file__).resolve().parent.parent / "external" / "video-use"
HELPERS_DIR = VIDEO_USE_DIR / "helpers"

# OpenMontage 风格预设 → Resolve 调色参数映射
# 来源: external/OpenMontage/styles/*.yaml 的 visual_language + mood 特征
OPENMONTAGE_STYLE_MAP = {
    "ghibli": {
        "preset": "filmic",
        "brightness": 1.06,
        "contrast": 1.05,
        "saturation": 1.15,
        "description": "Anime Ghibli: 暖调、柔和、高饱和自然色",
    },
    "premium": {
        "preset": "cinematic",
        "brightness": 1.0,
        "contrast": 1.12,
        "saturation": 0.92,
        "description": "Premium Minimalist: 冷静、精确、低装饰",
    },
    "clean": {
        "preset": "cinematic",
        "brightness": 1.03,
        "contrast": 1.08,
        "saturation": 1.0,
        "description": "Clean Professional: 平衡、专业、适度对比",
    },
    "flat": {
        "preset": "opendrt",
        "brightness": 1.08,
        "contrast": 1.20,
        "saturation": 1.18,
        "description": "Flat Motion Graphics: 提升对比+饱和，补偿平坦影调",
    },
    "dramatic": {
        "preset": "shadow-contrast",
        "brightness": 0.95,
        "contrast": 1.25,
        "saturation": 0.88,
        "description": "Dramatic: 高对比、压暗、低饱和电影感",
    },
    "vivid": {
        "preset": "saturation",
        "brightness": 1.05,
        "contrast": 1.10,
        "saturation": 1.30,
        "description": "Vivid: 高饱和、明亮、活力感",
    },
}


class UnifiedVideoPipeline:
    """统一视频处理管线"""

    def __init__(self, resolve_home: str = r"D:\DaVinci Resolve"):
        self.engine = ResolveColorEngine(resolve_home=resolve_home)
        self.video_use_helpers = HELPERS_DIR

    # ----------------------------------------------------------------
    # 场景检测
    # ----------------------------------------------------------------

    def detect_scenes(
        self,
        video_path: str,
        threshold: float = 27.0,
        max_scenes: int = 20,
    ) -> List[Dict[str, Any]]:
        """PySceneDetect 自动场景检测"""
        print(f"\n[SceneDetect] Analyzing: {os.path.basename(video_path)}")
        scenes = self.engine.detect_scenes(
            video_path, threshold=threshold, max_scenes=max_scenes
        )
        if scenes and "error" in scenes[0]:
            print(f"  ERROR: {scenes[0]['error']}")
            return []
        print(f"  Found {len(scenes)} scenes")
        for i, s in enumerate(scenes[:10]):
            print(f"    Scene {i}: {s['start']} -> {s['end']} ({s['duration_frames']} frames)")
        return scenes

    # ----------------------------------------------------------------
    # FFmpeg 快速预览调色（video-use grade.py）
    # ----------------------------------------------------------------

    def quick_grade(
        self,
        video_path: str,
        output_path: str,
        preset: str = "warm_cinematic",
    ) -> str:
        """使用 video-use grade.py 进行 FFmpeg 快速预览调色"""
        grade_py = self.video_use_helpers / "grade.py"
        if not grade_py.exists():
            print(f"  WARNING: grade.py not found at {grade_py}")
            return ""

        cmd = [
            sys.executable, str(grade_py),
            video_path, "-o", output_path,
            "--preset", preset,
        ]
        print(f"\n[QuickGrade] {preset}: {os.path.basename(video_path)} -> {os.path.basename(output_path)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                size = os.path.getsize(output_path) if os.path.isfile(output_path) else 0
                print(f"  OK: {size / (1024*1024):.1f} MB")
                return output_path
            else:
                print(f"  FAILED: {result.stderr[:200]}")
        except Exception as e:
            print(f"  ERROR: {e}")
        return ""

    def auto_analyze(self, video_path: str) -> Dict[str, Any]:
        """自动分析视频：先尝试 FFmpeg signalstats，失败则回退到 OpenCV

        FFmpeg 8.x 的 signalstats 滤镜可能因兼容性问题报错（exit code -22），
        此方法提供 OpenCV 回退，确保分析能力始终可用。
        """
        print(f"\n[AutoAnalyze] {os.path.basename(video_path)}:")

        # 尝试 FFmpeg signalstats（video-use grade.py）
        grade_py = self.video_use_helpers / "grade.py"
        if grade_py.exists():
            cmd = [sys.executable, str(grade_py), "--analyze", video_path]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    print(result.stdout)
                    return {"stdout": result.stdout, "returncode": 0, "method": "ffmpeg"}
                else:
                    print(f"  FFmpeg analyze failed (exit {result.returncode}), falling back to OpenCV...")
            except Exception as e:
                print(f"  FFmpeg analyze error: {e}, falling back to OpenCV...")

        # 回退到 OpenCV 分析
        cv2_result = self._cv2_analyze(video_path)
        if "error" not in cv2_result:
            print("  OpenCV analysis:")
            print(f"    Brightness (Y mean): {cv2_result['y_mean']:.3f}")
            print(f"    Contrast (Y std):    {cv2_result['y_std']:.3f}")
            print(f"    Saturation (mean):   {cv2_result['sat_mean']:.3f}")
            if "frame_count" in cv2_result:
                print(f"    Frames: {cv2_result['frame_count']}, FPS: {cv2_result['fps']:.1f}")
                print(f"    Resolution: {cv2_result['resolution']}")
        return {**cv2_result, "method": "opencv"}

    def _cv2_analyze(self, video_path: str) -> Dict[str, Any]:
        """使用 OpenCV 进行视频分析（FFmpeg signalstats 不可用时的回退方案）

        通过采样帧并转换为 HLS 色彩空间计算：
        - y_mean: 平均亮度 (0..1)
        - y_std:  亮度标准差（对比度近似）(0..1)
        - sat_mean: 平均饱和度 (0..1)
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            return {"error": "OpenCV not available. Run: pip install opencv-python"}

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": "Cannot open video file"}

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 采样帧数（最多 10 帧）
        n_samples = min(10, max(frame_count, 1))
        sample_indices = [
            int(i * max(frame_count - 1, 0) / max(n_samples - 1, 1))
            for i in range(n_samples)
        ]

        y_means = []
        y_stds = []
        sat_means = []

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            # BGR → HLS 计算亮度和饱和度
            hls = cv2.cvtColor(frame, cv2.COLOR_BGR2HLS)
            l_channel = hls[:, :, 1]  # Lightness
            s_channel = hls[:, :, 2]  # Saturation

            y_means.append(float(np.mean(l_channel) / 255.0))
            y_stds.append(float(np.std(l_channel) / 255.0))
            sat_means.append(float(np.mean(s_channel) / 255.0))

        cap.release()

        if not y_means:
            return {"error": "No frames could be read from video"}

        import statistics
        return {
            "y_mean": float(statistics.mean(y_means)),
            "y_std": float(statistics.mean(y_stds)) if y_stds else 0.18,
            "sat_mean": float(statistics.mean(sat_means)) if sat_means else 0.25,
            "frame_count": frame_count,
            "fps": fps,
            "resolution": f"{width}x{height}",
        }

    # ----------------------------------------------------------------
    # 智能调色推荐（基于视频分析自动计算参数）
    # ----------------------------------------------------------------

    def smart_grade_params(self, video_path: str) -> Dict[str, Any]:
        """基于视频内容分析，自动推荐最佳调色参数

        分析视频亮度/对比度/饱和度，智能映射到 Resolve 调色参数：
        - brightness: 补偿曝光不足/过度
        - contrast: 补偿对比度不足/过高
        - saturation: 补偿色彩平淡/过饱和
        - preset: 根据整体影调推荐 DCTL 预设

        Returns:
            {"brightness": float, "contrast": float, "saturation": float,
             "preset": str, "analysis": dict, "reasoning": str}
        """
        print(f"\n[SmartGrade] Analyzing video for auto-grading...")
        analysis = self._cv2_analyze(video_path)
        if "error" in analysis:
            print(f"  ERROR: {analysis['error']}, using defaults")
            return {
                "brightness": 1.05, "contrast": 1.1, "saturation": 1.05,
                "preset": "cinematic", "analysis": {}, "reasoning": "analysis_failed_fallback",
            }

        y_mean = analysis["y_mean"]      # 0..1 平均亮度
        y_std = analysis["y_std"]        # 0..1 对比度近似
        sat_mean = analysis["sat_mean"]  # 0..1 平均饱和度

        reasons = []

        # --- 亮度补偿 ---
        if y_mean < 0.30:
            brightness = 1.20
            reasons.append(f"underexposed(Y={y_mean:.2f})→boost+20%")
        elif y_mean < 0.40:
            brightness = 1.10
            reasons.append(f"slightly_dark(Y={y_mean:.2f})→boost+10%")
        elif y_mean > 0.70:
            brightness = 0.92
            reasons.append(f"overexposed(Y={y_mean:.2f})→reduce-8%")
        elif y_mean > 0.60:
            brightness = 0.97
            reasons.append(f"slightly_bright(Y={y_mean:.2f})→reduce-3%")
        else:
            brightness = 1.03
            reasons.append(f"balanced(Y={y_mean:.2f})→subtle+3%")

        # --- 对比度补偿 ---
        if y_std < 0.12:
            contrast = 1.25
            reasons.append(f"flat(C={y_std:.2f})→boost+25%")
        elif y_std < 0.18:
            contrast = 1.15
            reasons.append(f"low_contrast(C={y_std:.2f})→boost+15%")
        elif y_std > 0.28:
            contrast = 0.95
            reasons.append(f"harsh(C={y_std:.2f})→soften-5%")
        else:
            contrast = 1.08
            reasons.append(f"normal(C={y_std:.2f})→gentle+8%")

        # --- 饱和度补偿 ---
        if sat_mean < 0.15:
            saturation = 1.25
            reasons.append(f"desaturated(S={sat_mean:.2f})→boost+25%")
        elif sat_mean < 0.22:
            saturation = 1.12
            reasons.append(f"muted(S={sat_mean:.2f})→boost+12%")
        elif sat_mean > 0.45:
            saturation = 0.90
            reasons.append(f"oversaturated(S={sat_mean:.2f})→reduce-10%")
        elif sat_mean > 0.35:
            saturation = 0.95
            reasons.append(f"vivid(S={sat_mean:.2f})→slight-5%")
        else:
            saturation = 1.05
            reasons.append(f"natural(S={sat_mean:.2f})→subtle+5%")

        # --- 预设推荐 ---
        preset = self._recommend_preset(y_mean, y_std, sat_mean)
        reasons.append(f"preset→{preset}")

        reasoning = "; ".join(reasons)
        print(f"  Brightness: {brightness:.2f} | Contrast: {contrast:.2f} | Saturation: {saturation:.2f}")
        print(f"  Preset: {preset}")
        print(f"  Reasoning: {reasoning}")

        return {
            "brightness": brightness,
            "contrast": contrast,
            "saturation": saturation,
            "preset": preset,
            "analysis": analysis,
            "reasoning": reasoning,
        }

    def _recommend_preset(self, y_mean: float, y_std: float, sat_mean: float) -> str:
        """根据影调特征推荐 DCTL 预设"""
        # 暗调 + 低对比 → 电影感
        if y_mean < 0.35 and y_std < 0.18:
            return "cinematic"
        # 暗调 + 高对比 → 胶片质感
        if y_mean < 0.40 and y_std > 0.22:
            return "filmic"
        # 高饱和 + 明亮 → OpenDRT 色彩科学
        if sat_mean > 0.35 and y_mean > 0.50:
            return "opendrt"
        # 低饱和 → 饱和度增强
        if sat_mean < 0.18:
            return "saturation"
        # 高对比 + 暗部 → 阴影对比
        if y_std > 0.25 and y_mean < 0.45:
            return "shadow-contrast"
        # 平衡 → 经典电影
        return "cinematic"

    # ----------------------------------------------------------------
    # FFmpeg 补帧（minterpolate 光流插值）
    # ----------------------------------------------------------------

    def frame_interpolate(
        self,
        video_path: str,
        output_path: str,
        target_fps: float = 60.0,
        method: str = "mvscale",
    ) -> str:
        """使用 FFmpeg minterpolate 滤镜进行光流补帧

        将视频从原始帧率插值到目标帧率，实现平滑慢动作或高帧率输出。
        无需 PyTorch/GPU，纯 CPU 光流估计。

        Args:
            video_path: 输入视频
            output_path: 输出路径
            target_fps: 目标帧率（默认 60fps）
            method: 插值方法 (mvscale/mci/blend)
                    mvscale: 运动矢量缩放（快速）
                    mci: 运动补偿插值（最佳质量）
                    blend: 帧混合（最快）

        Returns:
            输出文件路径，失败返回空字符串
        """
        ffmpeg = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
        if not os.path.isfile(ffmpeg):
            print(f"  ERROR: ffmpeg not found")
            return ""

        # 构建 minterpolate 滤镜
        mi_mode = {"mvscale": "mvscale", "mci": "mci", "blend": "blend"}.get(method, "mvscale")
        vf = f"minterpolate=fps={target_fps}:mi_mode={mi_mode}:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
        if method == "blend":
            vf = f"minterpolate=fps={target_fps}:mi_mode=blend"

        cmd = [
            ffmpeg, "-y", "-i", video_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "copy",
            output_path,
        ]

        print(f"\n[FrameInterpolate] {os.path.basename(video_path)} → {target_fps}fps ({method})")
        print(f"  Output: {os.path.basename(output_path)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode == 0 and os.path.isfile(output_path):
                size = os.path.getsize(output_path) / (1024 * 1024)
                print(f"  OK: {size:.1f} MB")
                return output_path
            else:
                print(f"  FAILED: {result.stderr[-300:] if result.stderr else 'unknown'}")
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT: 600s exceeded")
        except Exception as e:
            print(f"  ERROR: {e}")
        return ""

    # ----------------------------------------------------------------
    # Resolve 专业调色
    # ----------------------------------------------------------------

    def resolve_grade(
        self,
        video_path: str,
        output_dir: str,
        preset: str = "cinematic",
        segment_presets: Optional[Dict[str, str]] = None,
        brightness: float = 1.05,
        contrast: float = 1.1,
        saturation: float = 1.05,
        close_after: bool = True,
    ) -> Dict[str, Any]:
        """使用 Resolve 引擎进行专业 DCTL/LUT + Fusion 调色

        通过 engine.auto_grade() 获得完整生命周期管理：
        - 自动启动/关闭 Resolve
        - 3层重试 + 进程监控
        - v3.3 项目清理 + 素材预校验
        - API 就绪检测
        """
        print("\n[ResolveGrade] Starting professional grade...")
        print(f"  Preset: {preset}, Brightness: {brightness}, Contrast: {contrast}, Saturation: {saturation}")
        if segment_presets:
            print(f"  Segment presets: {len(segment_presets)} segments")

        config = ColorGradeConfig(
            preset=preset,
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            segment_presets=segment_presets,
        )

        project_name = f"Unified_{Path(video_path).stem}"
        result = self.engine.auto_grade(
            project_name=project_name,
            media_files=[video_path],
            color_config=config,
            render=True,
            output_dir=output_dir,
            close_after=close_after,
        )

        return {
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.return_code,
            "clips_graded": result.clips_graded,
            "clips_imported": result.clips_imported,
            "errors": result.errors,
            "output_path": result.output_path,
        }

    # ----------------------------------------------------------------
    # 一键全流程
    # ----------------------------------------------------------------

    def full_pipeline(
        self,
        video_path: str,
        output_dir: str,
        threshold: float = 27.0,
        quick_grade_preset: str = "warm_cinematic",
        resolve_preset: str = "cinematic",
        do_quick_grade: bool = True,
        do_resolve_grade: bool = True,
        smart_mode: bool = False,
        style: Optional[str] = None,
        interpolate_fps: float = 0,
        interpolate_method: str = "mvscale",
    ) -> Dict[str, Any]:
        """一键全流程：场景检测 → 智能分析 → FFmpeg 预览 → Resolve 调色 → 补帧 → 渲染

        新增 v2.1 参数:
            smart_mode: 启用智能调色（自动分析视频→计算最佳参数）
            style: OpenMontage 风格预设 (ghibli/premium/clean/flat/dramatic/vivid)
            interpolate_fps: 补帧目标帧率（0=不补帧，60=补到60fps）
            interpolate_method: 补帧方法 (mvscale/mci/blend)
        """
        results = {"video": video_path, "steps": {}}

        # Step 0: 智能分析 / 风格预设 → 覆盖参数
        brightness, contrast, saturation = 1.05, 1.1, 1.05
        if smart_mode:
            smart = self.smart_grade_params(video_path)
            results["steps"]["smart_analysis"] = smart
            resolve_preset = smart["preset"]
            brightness = smart["brightness"]
            contrast = smart["contrast"]
            saturation = smart["saturation"]
        elif style and style in OPENMONTAGE_STYLE_MAP:
            style_cfg = OPENMONTAGE_STYLE_MAP[style]
            resolve_preset = style_cfg["preset"]
            brightness = style_cfg["brightness"]
            contrast = style_cfg["contrast"]
            saturation = style_cfg["saturation"]
            results["steps"]["style_preset"] = {"style": style, **style_cfg}
            print(f"\n[Style] Applied '{style}': {style_cfg['description']}")

        # Step 1: 场景检测
        scenes = self.detect_scenes(video_path, threshold=threshold)
        results["steps"]["scene_detect"] = {"scenes": len(scenes), "data": scenes}

        # Step 2: 自动生成预设映射
        if scenes:
            preset_cycle = list(DCTL_PRESET_MAP.keys())[:6]
            segment_presets = {}
            for i in range(min(len(scenes), len(preset_cycle))):
                segment_presets[f"scene_{i}"] = preset_cycle[i % len(preset_cycle)]
            results["steps"]["segment_presets"] = segment_presets
        else:
            segment_presets = None

        # Step 3: FFmpeg 快速预览
        if do_quick_grade:
            quick_output = os.path.join(output_dir, f"quick_{Path(video_path).stem}_{quick_grade_preset}.mp4")
            self.quick_grade(video_path, quick_output, preset=quick_grade_preset)
            results["steps"]["quick_grade"] = quick_output

        # Step 4: Resolve 专业调色 + 渲染
        if do_resolve_grade:
            result = self.resolve_grade(
                video_path, output_dir,
                preset=resolve_preset,
                segment_presets=segment_presets,
                brightness=brightness,
                contrast=contrast,
                saturation=saturation,
            )
            results["steps"]["resolve_grade"] = result

        # Step 5: 补帧（可选）
        if interpolate_fps > 0:
            interp_input = results["steps"].get("resolve_grade", {}).get("output_path", "") or video_path
            interp_output = os.path.join(
                output_dir, f"{Path(interp_input).stem}_{int(interpolate_fps)}fps.mp4"
            )
            interp_result = self.frame_interpolate(
                interp_input, interp_output,
                target_fps=interpolate_fps,
                method=interpolate_method,
            )
            results["steps"]["frame_interpolate"] = {
                "output": interp_result,
                "target_fps": interpolate_fps,
                "method": interpolate_method,
            }

        return results


    # ----------------------------------------------------------------
    # 多线程全阶段执行
    # ----------------------------------------------------------------

    def run_multithreaded(
        self,
        video_path: str,
        output_dir: str,
        max_workers: int = 4,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """多线程全阶段执行（DAG 并行调度）

        DAG 依赖图:
            perceive ‖ analyze → plan → execute → render → verify

        阶段说明:
            perceive: 场景检测（PySceneDetect）
            analyze:  视频分析 + 智能调色参数（cv2/FFmpeg）
            plan:     生成调色预设映射
            execute:  Resolve 专业调色
            render:   FFmpeg 补帧渲染
            verify:   输出验证

        Args:
            video_path: 输入视频
            output_dir: 输出目录
            max_workers: 最大线程数
            progress_callback: 进度回调 cb(event_dict)

        Returns:
            执行结果字典
        """
        from pipeline.multi_thread_executor import create_video_pipeline_executor

        executor = create_video_pipeline_executor(
            pipeline_instance=self,
            video_path=video_path,
            output_dir=output_dir,
            max_workers=max_workers,
        )

        if progress_callback:
            executor.add_monitor_callback(progress_callback)

        result = executor.run_all()
        return result.to_dict()

    def full_pipeline_mt(
        self,
        video_path: str,
        output_dir: str,
        max_workers: int = 4,
        style: Optional[str] = None,
        smart_mode: bool = True,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """多线程全流程（v2.2 入口）

        与 full_pipeline 功能等价，但使用多线程 DAG 调度器
        自动将 perceive ‖ analyze 并行执行，缩短总耗时。

        Args:
            video_path: 输入视频
            output_dir: 输出目录
            max_workers: 最大线程数（默认 4）
            style: OpenMontage 风格预设
            smart_mode: 启用智能调色
            progress_callback: 进度回调

        Returns:
            完整结果字典
        """
        os.makedirs(output_dir, exist_ok=True)

        # 应用风格预设
        if style and style in OPENMONTAGE_STYLE_MAP:
            style_cfg = OPENMONTAGE_STYLE_MAP[style]
            self.set_context_override("style", style_cfg)
            print(f"\n[MT-Pipeline] Style '{style}': {style_cfg['description']}")

        return self.run_multithreaded(
            video_path=video_path,
            output_dir=output_dir,
            max_workers=max_workers,
            progress_callback=progress_callback,
        )

    def set_context_override(self, key: str, value: Any):
        """设置上下文覆盖（供多线程执行器读取）"""
        if not hasattr(self, '_context_overrides'):
            self._context_overrides = {}
        self._context_overrides[key] = value


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    import argparse
    ap = argparse.ArgumentParser(description="统一视频处理管线 v2.2")
    ap.add_argument("video", nargs="?", help="输入视频路径")
    ap.add_argument("-o", "--output-dir", default=r"D:\AE-Work\output", help="输出目录")
    ap.add_argument("--threshold", type=float, default=27.0, help="场景检测阈值")
    ap.add_argument("--quick-preset", default="warm_cinematic", help="FFmpeg 预览调色预设")
    ap.add_argument("--resolve-preset", default="cinematic", help="Resolve 专业调色预设")
    ap.add_argument("--no-quick", action="store_true", help="跳过 FFmpeg 预览")
    ap.add_argument("--no-resolve", action="store_true", help="跳过 Resolve 调色")
    ap.add_argument("--analyze-only", action="store_true", help="仅分析不处理")
    # v2.1 新增
    ap.add_argument("--smart", action="store_true", help="智能调色：自动分析视频→计算最佳参数")
    ap.add_argument("--style", choices=list(OPENMONTAGE_STYLE_MAP.keys()),
                    help="OpenMontage 风格预设")
    ap.add_argument("--interpolate", type=float, default=0, metavar="FPS",
                    help="补帧目标帧率（如 60）")
    ap.add_argument("--interp-method", default="mvscale",
                    choices=["mvscale", "mci", "blend"], help="补帧方法")
    ap.add_argument("--list-styles", action="store_true", help="列出可用风格预设")
    # v2.2 新增
    ap.add_argument("--mt", action="store_true", help="多线程模式（DAG 并行调度）")
    ap.add_argument("--workers", type=int, default=4, help="多线程工作线程数")
    args = ap.parse_args()

    if args.list_styles:
        print("\n可用 OpenMontage 风格预设:")
        print("-" * 50)
        for name, cfg in OPENMONTAGE_STYLE_MAP.items():
            print(f"  {name:12s} | {cfg['preset']:16s} | {cfg['description']}")
        return

    if not args.video:
        ap.error("请提供输入视频路径")

    pipeline = UnifiedVideoPipeline()

    if args.analyze_only:
        pipeline.auto_analyze(args.video)
        pipeline.detect_scenes(args.video, threshold=args.threshold)
        pipeline.smart_grade_params(args.video)
        return

    os.makedirs(args.output_dir, exist_ok=True)

    # 多线程模式
    if args.mt:
        results = pipeline.full_pipeline_mt(
            video_path=args.video,
            output_dir=args.output_dir,
            max_workers=args.workers,
            style=args.style,
            smart_mode=args.smart,
        )
        print("\n" + "=" * 60)
        print("  MULTI-THREAD PIPELINE COMPLETE (v2.2)")
        print("=" * 60)
        if "stages" in results:
            for name, stage_data in results["stages"].items():
                state = stage_data.get("state", "?")
                dur = stage_data.get("duration_sec", 0)
                print(f"  [{state.upper():6s}] {name:20s} | {dur:.1f}s")
        print(f"  Total: {results.get('total_duration_sec', 0):.1f}s")
        return

    # 单线程模式（默认）
    results = pipeline.full_pipeline(
        video_path=args.video,
        output_dir=args.output_dir,
        threshold=args.threshold,
        quick_grade_preset=args.quick_preset,
        resolve_preset=args.resolve_preset,
        do_quick_grade=not args.no_quick,
        do_resolve_grade=not args.no_resolve,
        smart_mode=args.smart,
        style=args.style,
        interpolate_fps=args.interpolate,
        interpolate_method=args.interp_method,
    )

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE (v2.2)")
    print("=" * 60)
    for step, data in results["steps"].items():
        if isinstance(data, dict) and "scenes" in data:
            print(f"  {step}: {data['scenes']} scenes detected")
        elif isinstance(data, dict) and "reasoning" in data:
            print(f"  {step}: {data['reasoning'][:60]}...")
        elif isinstance(data, dict) and "output" in data:
            print(f"  {step}: {data.get('output', 'done')}")
        elif isinstance(data, str):
            print(f"  {step}: {data}")
        else:
            print(f"  {step}: done")


if __name__ == "__main__":
    main()
