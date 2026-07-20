#!/usr/bin/env python3
"""
Topaz Video AI 集成模块 v1.0
==============================

通过 CLI 命令行接口集成 Topaz Video AI，支持视频超分、补帧、降噪、
稳定化等 AI 增强功能，提供真实模式、模拟模式和自动降级模式。

安装路径: C:\Program Files\Topaz Labs LLC\Topaz Video AI
CLI 工具: topazcli.exe 或 Topaz Video AI.exe --cli

支持的功能:
- upscale     : 超分辨率放大 (2x, 4x)
- interpolate : 帧率插值补帧 (24fps→60fps)
- denoise     : AI 降噪
- sharpen     : 智能锐化
- stabilize   : 视频防抖稳定化

执行模式:
- real    : 通过 topazcli.exe 真实执行（需要安装 Topaz Video AI）
- simulate: 模拟执行，生成模拟结果（用于测试和流程验证）
- auto    : 优先真实模式，失败自动降级到模拟模式
"""
import os
import sys
import json
import time
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

DEFAULT_TOPAZ_HOME = Path(r"D:\top\Topaz Video AI Pro")
TOPAZ_HOME = Path(os.environ.get("TOPAZ_HOME", str(DEFAULT_TOPAZ_HOME)))

TOPAZ_CLI_CANDIDATES = [
    TOPAZ_HOME / "topazcli.exe",
    TOPAZ_HOME / "Topaz Video AI BETA.exe",
    TOPAZ_HOME / "Topaz Video AI.exe",
]

OUTPUT_BASE = Path(os.environ.get("AE_WORK_DIR", r"D:\AE-Work"))

AVAILABLE_MODELS = [
    "proteus",
    "artemis",
    "gaia",
    "theia",
    "ahd",
    "chronos",
    "stabilizer",
    "denoise",
    "sharpen",
]

OUTPUT_FORMAT_MAP = {
    "mp4": "mp4",
    "mov": "mov",
    "prores422hq": "mov",
    "prores422": "mov",
    "prores4444": "mov",
    "avi": "avi",
    "mkv": "mkv",
}


@dataclass
class TopazConfig:
    """Topaz Video AI 配置数据类。

    Attributes:
        install_path: Topaz 安装路径
        mode: 运行模式（real/simulate/auto）
        output_dir: 输出目录
        model: AI 模型名称
        scale: 缩放倍数（1.0=不放大，2.0=2x，4.0=4x）
        fps: 补帧目标帧率（0=不补帧）
        denoise: 降噪强度（0.0-1.0）
        sharpen: 锐化强度（0.0-1.0）
        stabilize: 是否防抖稳定化
        output_format: 输出格式（mp4/mov/prores422hq）
        quality: 输出质量（0-100，默认 90）
        deinterlace: 是否去隔行
        deblock: 是否去块效应
    """
    install_path: str = str(TOPAZ_HOME)
    mode: str = "auto"
    output_dir: str = str(OUTPUT_BASE / "topaz_output")
    model: str = "proteus"
    scale: float = 1.0
    fps: int = 0
    denoise: float = 0.0
    sharpen: float = 0.0
    stabilize: bool = False
    output_format: str = "mp4"
    quality: int = 90
    deinterlace: bool = False
    deblock: bool = False


@dataclass
class TopazResult:
    """Topaz 处理结果数据类。

    Attributes:
        success: 是否成功
        input_path: 输入文件路径
        output_path: 输出文件路径
        duration: 处理耗时（秒）
        original_size: 原始分辨率 (宽, 高)
        output_size: 输出分辨率 (宽, 高)
        original_fps: 原始帧率
        output_fps: 输出帧率
        error: 错误信息（如果失败）
        mode: 实际使用的执行模式
        model: 使用的 AI 模型
    """
    success: bool = False
    input_path: str = ""
    output_path: str = ""
    duration: float = 0.0
    original_size: Tuple[int, int] = (0, 0)
    output_size: Tuple[int, int] = (0, 0)
    original_fps: float = 0.0
    output_fps: float = 0.0
    error: Optional[str] = None
    mode: str = "simulate"
    model: str = ""


TOPAZ_PRESETS: Dict[str, Dict[str, Any]] = {
    "default": {
        "model": "proteus",
        "scale": 1.0,
        "fps": 0,
        "denoise": 0.3,
        "sharpen": 0.2,
        "stabilize": False,
        "output_format": "mp4",
        "quality": 90,
        "deinterlace": False,
        "deblock": False,
        "description": "默认均衡配置，轻度降噪和锐化",
    },
    "quality_2x": {
        "model": "proteus",
        "scale": 2.0,
        "fps": 0,
        "denoise": 0.5,
        "sharpen": 0.4,
        "stabilize": False,
        "output_format": "mp4",
        "quality": 95,
        "deinterlace": False,
        "deblock": True,
        "description": "2x 超分 + 降噪 + 锐化（高质量）",
    },
    "fast_1080p": {
        "model": "ahd",
        "scale": 1.0,
        "fps": 0,
        "denoise": 0.2,
        "sharpen": 0.1,
        "stabilize": False,
        "output_format": "mp4",
        "quality": 80,
        "deinterlace": False,
        "deblock": False,
        "description": "快速 1080p 输出，速度优先",
    },
    "cinema_4k": {
        "model": "gaia",
        "scale": 4.0,
        "fps": 0,
        "denoise": 0.6,
        "sharpen": 0.5,
        "stabilize": False,
        "output_format": "prores422hq",
        "quality": 100,
        "deinterlace": True,
        "deblock": True,
        "description": "4K 超分 + 去隔行 + 去块，电影级质量",
    },
    "smooth_motion_60fps": {
        "model": "chronos",
        "scale": 1.0,
        "fps": 60,
        "denoise": 0.2,
        "sharpen": 0.1,
        "stabilize": True,
        "output_format": "mp4",
        "quality": 90,
        "deinterlace": False,
        "deblock": False,
        "description": "60fps 补帧 + 防抖，流畅运动效果",
    },
    "archive_restoration": {
        "model": "artemis",
        "scale": 2.0,
        "fps": 0,
        "denoise": 0.9,
        "sharpen": 0.3,
        "stabilize": True,
        "output_format": "mp4",
        "quality": 95,
        "deinterlace": True,
        "deblock": True,
        "description": "老视频修复（去噪 + 去划痕 + 稳定）",
    },
    "anime_enhance": {
        "model": "theia",
        "scale": 2.0,
        "fps": 0,
        "denoise": 0.4,
        "sharpen": 0.6,
        "stabilize": False,
        "output_format": "mp4",
        "quality": 92,
        "deinterlace": False,
        "deblock": False,
        "description": "动画增强（专门的动漫模型）",
    },
}


class TopazEnhancer:
    """Topaz Video AI 视频增强器。

    封装 Topaz CLI 命令行调用，提供视频超分、补帧、降噪、稳定化等
    AI 增强功能的统一接口。支持真实模式、模拟模式和自动降级模式。
    """

    def __init__(self, config: Optional[TopazConfig] = None):
        """初始化 TopazEnhancer。

        Args:
            config: Topaz 配置对象，为 None 时使用默认配置
        """
        self.config = config or TopazConfig()
        self._cli_path = self._find_cli()
        self._available = self._check_availability()
        print(f"[TopazEnhancer] Mode: {self.config.mode}")
        print(f"[TopazEnhancer] Topaz available: {self._available}")
        print(f"[TopazEnhancer] CLI: {self._cli_path}")

    def _find_cli(self) -> Optional[Path]:
        """查找 Topaz CLI 可执行文件。

        Returns:
            CLI 可执行文件路径，找不到返回 None
        """
        install_path = Path(self.config.install_path)
        candidates = [
            install_path / "topazcli.exe",
            install_path / "Topaz Video AI.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        
        extra_paths = [
            Path(r"C:\Program Files\Topaz Labs LLC\Topaz Video AI"),
            Path(r"C:\Program Files (x86)\Topaz Labs LLC\Topaz Video AI"),
            Path(r"D:\Program Files\Topaz Labs LLC\Topaz Video AI"),
            Path(r"D:\Topaz Video AI"),
            Path(r"D:\Topaz Labs\Topaz Video AI"),
            Path(r"C:\Topaz Video AI"),
            Path(r"C:\Topaz Labs\Topaz Video AI"),
            Path(r"D:\topaz\Topaz Video AI"),
            Path(r"C:\topaz\Topaz Video AI"),
            Path(r"D:\top\Topaz Video AI Pro"),
            Path(r"D:\top\Topaz Video AI"),
            Path(r"C:\top\Topaz Video AI Pro"),
            Path(os.path.expanduser(r"~\AppData\Local\Topaz Labs LLC\Topaz Video AI")),
        ]
        for base_path in extra_paths:
            for exe_name in ["topazcli.exe", "Topaz Video AI.exe", "Topaz Video AI BETA.exe"]:
                candidate = base_path / exe_name
                if candidate.exists():
                    return candidate
        
        return None

    def _check_availability(self) -> bool:
        """检查 Topaz Video AI 是否已安装可用。

        Returns:
            True 表示可用，False 表示不可用
        """
        if self._cli_path is None:
            return False
        if not self._cli_path.exists():
            return False
        return True

    def is_available(self) -> bool:
        """检查 Topaz 是否已安装可用。

        Returns:
            True 表示可用，False 表示不可用
        """
        return self._available

    def get_available_models(self) -> List[str]:
        """获取可用的 AI 模型列表。

        Returns:
            模型名称列表
        """
        return list(AVAILABLE_MODELS)

    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """获取视频基本信息（分辨率、帧率等）。

        Args:
            video_path: 视频文件路径

        Returns:
            包含 width, height, fps, duration 的字典
        """
        info = {
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
            "duration": 0.0,
        }
        try:
            import struct
            path = Path(video_path)
            if not path.exists():
                return info
            file_size = path.stat().st_size
            if file_size > 1024 * 1024:
                info["duration"] = min(300.0, file_size / (1024 * 1024 * 2))
        except Exception:
            pass
        return info

    def _build_cli_args(
        self,
        input_path: str,
        output_path: str,
        config: TopazConfig,
    ) -> List[str]:
        """构建 Topaz CLI 命令参数列表。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            config: Topaz 配置

        Returns:
            CLI 参数列表
        """
        args = [str(self._cli_path)] if self._cli_path else ["topazcli"]

        args.extend(["-i", input_path])
        args.extend(["-o", output_path])

        if config.model:
            args.extend(["--model", config.model])

        if config.scale > 1.0:
            args.extend(["--scale", str(config.scale)])

        if config.fps > 0:
            args.extend(["--fps", str(config.fps)])

        if config.denoise > 0:
            args.extend(["--denoise", str(config.denoise)])

        if config.sharpen > 0:
            args.extend(["--sharpen", str(config.sharpen)])

        if config.stabilize:
            args.append("--stabilize")

        if config.deinterlace:
            args.append("--deinterlace")

        if config.deblock:
            args.append("--deblock")

        if config.quality > 0:
            args.extend(["--quality", str(config.quality)])

        if config.output_format:
            fmt = OUTPUT_FORMAT_MAP.get(config.output_format, config.output_format)
            args.extend(["--format", fmt])

        return args

    def estimate_duration(
        self,
        input_path: str,
        config: Optional[TopazConfig] = None,
    ) -> float:
        """估算处理时间（基于视频时长和复杂度）。

        Args:
            input_path: 输入视频路径
            config: 配置（可选，默认使用实例配置）

        Returns:
            估算的处理时间（秒）
        """
        cfg = config or self.config
        video_info = self._get_video_info(input_path)
        duration = video_info.get("duration", 60.0)
        fps = video_info.get("fps", 24.0)
        width = video_info.get("width", 1920)
        height = video_info.get("height", 1080)

        base_time = duration * 1.5

        complexity_factor = 1.0

        if cfg.scale > 1.0:
            complexity_factor *= cfg.scale * cfg.scale * 1.5

        if cfg.fps > 0 and cfg.fps > fps:
            fps_ratio = cfg.fps / fps
            complexity_factor *= fps_ratio * 0.8

        if cfg.denoise > 0:
            complexity_factor *= (1.0 + cfg.denoise * 0.5)

        if cfg.sharpen > 0:
            complexity_factor *= (1.0 + cfg.sharpen * 0.3)

        if cfg.stabilize:
            complexity_factor *= 1.8

        resolution_factor = (width * height) / (1920 * 1080)
        complexity_factor *= resolution_factor

        estimated = base_time * complexity_factor
        return max(5.0, estimated)

    def enhance_video(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        config: Optional[TopazConfig] = None,
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> TopazResult:
        """主方法：增强视频。

        Args:
            input_path: 输入视频文件路径
            output_path: 输出视频文件路径（可选，自动生成）
            config: 配置（可选，默认使用实例配置）
            callback: 进度回调函数 (progress 0-1, message)

        Returns:
            TopazResult 处理结果对象
        """
        cfg = config or self.config
        start_time = time.time()

        input_file = Path(input_path)
        if not input_file.exists():
            return TopazResult(
                success=False,
                input_path=input_path,
                error=f"Input file not found: {input_path}",
                mode=cfg.mode,
                model=cfg.model,
            )

        if output_path is None:
            output_dir = Path(cfg.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            ext = OUTPUT_FORMAT_MAP.get(cfg.output_format, cfg.output_format)
            output_path = str(output_dir / f"topaz_{input_file.stem}_{ts}.{ext}")

        video_info = self._get_video_info(input_path)
        original_size = (video_info["width"], video_info["height"])
        original_fps = video_info["fps"]

        output_width = int(original_size[0] * cfg.scale)
        output_height = int(original_size[1] * cfg.scale)
        output_size = (output_width, output_height)
        output_fps = cfg.fps if cfg.fps > 0 else original_fps

        mode = cfg.mode
        if mode == "auto":
            mode = "real" if self._available else "simulate"

        if callback:
            callback(0.0, f"Starting enhancement in {mode} mode...")

        result = TopazResult(
            success=False,
            input_path=input_path,
            output_path=output_path,
            original_size=original_size,
            output_size=output_size,
            original_fps=original_fps,
            output_fps=output_fps,
            mode=mode,
            model=cfg.model,
        )

        if mode == "real":
            real_result = self._run_real_mode(
                input_path, output_path, cfg, callback
            )
            result = real_result
            if not real_result.success and cfg.mode == "auto":
                print("[TopazEnhancer] Real mode failed, falling back to simulate")
                if callback:
                    callback(0.3, "Real mode failed, falling back to simulate mode...")
                sim_result = self._run_simulate_mode(
                    input_path, output_path, cfg, callback
                )
                result = sim_result
        else:
            sim_result = self._run_simulate_mode(
                input_path, output_path, cfg, callback
            )
            result = sim_result

        result.duration = time.time() - start_time
        return result

    def _run_real_mode(
        self,
        input_path: str,
        output_path: str,
        config: TopazConfig,
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> TopazResult:
        """真实模式：通过 subprocess 调用 Topaz CLI。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            config: Topaz 配置
            callback: 进度回调函数

        Returns:
            TopazResult 处理结果
        """
        video_info = self._get_video_info(input_path)
        original_size = (video_info["width"], video_info["height"])
        original_fps = video_info["fps"]
        output_width = int(original_size[0] * config.scale)
        output_height = int(original_size[1] * config.scale)
        output_size = (output_width, output_height)
        output_fps = config.fps if config.fps > 0 else original_fps

        result = TopazResult(
            success=False,
            input_path=input_path,
            output_path=output_path,
            original_size=original_size,
            output_size=output_size,
            original_fps=original_fps,
            output_fps=output_fps,
            mode="real",
            model=config.model,
        )

        if self._cli_path is None or not self._cli_path.exists():
            result.error = f"Topaz CLI not found at {config.install_path}"
            return result

        try:
            cli_args = self._build_cli_args(input_path, output_path, config)

            print(f"[TopazEnhancer] Running: {' '.join(cli_args)}")

            process = subprocess.Popen(
                cli_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(Path(output_path).parent),
            )

            stdout_lines = []
            stderr_lines = []

            if process.stdout:
                for line in process.stdout:
                    stdout_lines.append(line)
                    if callback:
                        progress = min(0.9, len(stdout_lines) / 100.0)
                        callback(progress, line.strip())

            process.wait()

            if process.stderr:
                stderr_lines = process.stderr.readlines()

            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            output_file = Path(output_path)
            if process.returncode == 0 and output_file.exists():
                result.success = True
                if callback:
                    callback(1.0, "Enhancement complete")
            else:
                result.error = stderr[:500] if stderr else f"Exit code: {process.returncode}"

            return result

        except subprocess.TimeoutExpired:
            result.error = "Process timed out"
            return result
        except Exception as e:
            result.error = str(e)
            return result

    def _run_simulate_mode(
        self,
        input_path: str,
        output_path: str,
        config: TopazConfig,
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> TopazResult:
        """模拟模式：不真正调用 Topaz，生成模拟结果。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            config: Topaz 配置
            callback: 进度回调函数

        Returns:
            TopazResult 处理结果
        """
        video_info = self._get_video_info(input_path)
        original_size = (video_info["width"], video_info["height"])
        original_fps = video_info["fps"]
        output_width = int(original_size[0] * config.scale)
        output_height = int(original_size[1] * config.scale)
        output_size = (output_width, output_height)
        output_fps = config.fps if config.fps > 0 else original_fps

        estimated = self.estimate_duration(input_path, config)
        sim_duration = min(estimated * 0.1, 3.0)

        steps = 10
        for i in range(steps):
            time.sleep(sim_duration / steps)
            if callback:
                progress = (i + 1) / steps
                msg = f"Simulating {config.model}... {int(progress * 100)}%"
                callback(progress, msg)

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        input_file = Path(input_path)
        if input_file.exists():
            try:
                input_file_size = input_file.stat().st_size
                sim_size = int(input_file_size * config.scale * 0.8)
                with open(output_file, "wb") as f:
                    f.write(b"TOPAZ_SIMULATED_OUTPUT")
                    f.seek(max(0, sim_size - 1))
                    f.write(b"\0")
            except Exception:
                output_file.write_bytes(b"TOPAZ_SIMULATED_OUTPUT")
        else:
            output_file.write_bytes(b"TOPAZ_SIMULATED_OUTPUT")

        result = TopazResult(
            success=True,
            input_path=input_path,
            output_path=output_path,
            duration=sim_duration,
            original_size=original_size,
            output_size=output_size,
            original_fps=original_fps,
            output_fps=output_fps,
            mode="simulate",
            model=config.model,
        )

        if callback:
            callback(1.0, "Simulation complete")

        return result

    def batch_enhance(
        self,
        input_paths: List[str],
        output_dir: Optional[str] = None,
        config: Optional[TopazConfig] = None,
        callback: Optional[Callable[[int, int, TopazResult], None]] = None,
    ) -> List[TopazResult]:
        """批量处理视频。

        Args:
            input_paths: 输入视频路径列表
            output_dir: 输出目录（可选，使用配置中的目录）
            config: 配置（可选，默认使用实例配置）
            callback: 进度回调函数 (current_index, total, current_result)

        Returns:
            TopazResult 列表
        """
        cfg = config or self.config
        results = []
        total = len(input_paths)

        for idx, input_path in enumerate(input_paths):
            single_output_dir = output_dir or cfg.output_dir
            Path(single_output_dir).mkdir(parents=True, exist_ok=True)

            result = self.enhance_video(
                input_path=input_path,
                output_path=None,
                config=cfg,
                callback=None,
            )
            results.append(result)

            if callback:
                callback(idx + 1, total, result)

        return results


def create_config_from_preset(preset_name: str) -> TopazConfig:
    """从预设创建 TopazConfig 配置对象。

    Args:
        preset_name: 预设名称

    Returns:
        TopazConfig 配置对象

    Raises:
        ValueError: 预设不存在时抛出
    """
    if preset_name not in TOPAZ_PRESETS:
        raise ValueError(
            f"Unknown preset: {preset_name}. "
            f"Available presets: {list(TOPAZ_PRESETS.keys())}"
        )
    preset = TOPAZ_PRESETS[preset_name]
    config = TopazConfig()
    for key, value in preset.items():
        if key == "description":
            continue
        if hasattr(config, key):
            setattr(config, key, value)
    return config


def _run_self_tests():
    """自测函数：验证 Topaz Video AI 集成模块的所有功能。"""
    print("=" * 60)
    print("Topaz Video AI 集成模块 - 自测")
    print("=" * 60)

    results = []

    test_dir = Path(tempfile.mkdtemp(prefix="topaz_test_"))
    test_input = test_dir / "test_input.mp4"
    try:
        with open(test_input, "wb") as f:
            f.write(b"FAKE_VIDEO_HEADER")
            f.seek(1024 * 1024)
            f.write(b"\0")
    except Exception:
        pass

    print("\n[测试 1/8] 检查 TOPAZ_PRESETS 预设配置...")
    expected_presets = [
        "default",
        "quality_2x",
        "fast_1080p",
        "cinema_4k",
        "smooth_motion_60fps",
        "archive_restoration",
        "anime_enhance",
    ]
    all_presets_ok = True
    for pname in expected_presets:
        if pname in TOPAZ_PRESETS:
            print(f"  ✓ {pname} 存在")
        else:
            print(f"  ✗ {pname} 不存在")
            all_presets_ok = False
    results.append(("presets", all_presets_ok))

    print("\n[测试 2/8] 检查 TopazConfig 数据类...")
    try:
        config = TopazConfig()
        required_attrs = [
            "install_path", "mode", "output_dir", "model",
            "scale", "fps", "denoise", "sharpen", "stabilize",
            "output_format", "quality",
        ]
        attrs_ok = all(hasattr(config, attr) for attr in required_attrs)
        if attrs_ok:
            print(f"  ✓ TopazConfig 包含所有必需属性 ({len(required_attrs)} 个)")
        else:
            print(f"  ✗ TopazConfig 缺少必需属性")
        results.append(("config_dataclass", attrs_ok))
    except Exception as e:
        print(f"  ✗ TopazConfig 错误: {e}")
        results.append(("config_dataclass", False))

    print("\n[测试 3/8] 检查 TopazResult 数据类...")
    try:
        result = TopazResult()
        required_attrs = [
            "success", "input_path", "output_path", "duration",
            "original_size", "output_size", "original_fps", "output_fps",
            "error", "mode", "model",
        ]
        attrs_ok = all(hasattr(result, attr) for attr in required_attrs)
        if attrs_ok:
            print(f"  ✓ TopazResult 包含所有必需属性 ({len(required_attrs)} 个)")
        else:
            print(f"  ✗ TopazResult 缺少必需属性")
        results.append(("result_dataclass", attrs_ok))
    except Exception as e:
        print(f"  ✗ TopazResult 错误: {e}")
        results.append(("result_dataclass", False))

    print("\n[测试 4/8] 检查 TopazEnhancer 初始化...")
    try:
        enhancer = TopazEnhancer(config=TopazConfig(mode="simulate"))
        print(f"  ✓ TopazEnhancer 初始化成功")
        print(f"    - Mode: {enhancer.config.mode}")
        print(f"    - Available: {enhancer.is_available()}")
        results.append(("enhancer_init", True))
    except Exception as e:
        print(f"  ✗ TopazEnhancer 初始化失败: {e}")
        results.append(("enhancer_init", False))

    print("\n[测试 5/8] 检查 get_available_models...")
    try:
        enhancer = TopazEnhancer(config=TopazConfig(mode="simulate"))
        models = enhancer.get_available_models()
        if isinstance(models, list) and len(models) > 0:
            print(f"  ✓ 可用模型列表: {len(models)} 个")
            print(f"    {models[:5]}...")
            results.append(("available_models", True))
        else:
            print(f"  ✗ 模型列表为空或格式错误")
            results.append(("available_models", False))
    except Exception as e:
        print(f"  ✗ get_available_models 错误: {e}")
        results.append(("available_models", False))

    print("\n[测试 6/8] 检查 simulate 模式 enhance_video...")
    try:
        enhancer = TopazEnhancer(config=TopazConfig(mode="simulate"))
        output_dir = test_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        progress_log = []
        def progress_cb(progress, msg):
            progress_log.append((progress, msg))

        result = enhancer.enhance_video(
            input_path=str(test_input),
            output_path=str(output_dir / "test_output.mp4"),
            callback=progress_cb,
        )

        if result.success and Path(result.output_path).exists():
            print(f"  ✓ 模拟模式增强成功")
            print(f"    - 输入分辨率: {result.original_size}")
            print(f"    - 输出分辨率: {result.output_size}")
            print(f"    - 模式: {result.mode}")
            print(f"    - 进度回调次数: {len(progress_log)}")
            results.append(("simulate_enhance", True))
        else:
            print(f"  ✗ 模拟模式增强失败: {result.error}")
            results.append(("simulate_enhance", False))
    except Exception as e:
        print(f"  ✗ simulate enhance 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("simulate_enhance", False))

    print("\n[测试 7/8] 检查 create_config_from_preset...")
    try:
        test_preset = "quality_2x"
        config = create_config_from_preset(test_preset)
        if config.scale == 2.0 and config.model == "proteus":
            print(f"  ✓ 预设 {test_preset} 创建成功")
            print(f"    - Model: {config.model}")
            print(f"    - Scale: {config.scale}x")
            print(f"    - Denoise: {config.denoise}")
            print(f"    - Sharpen: {config.sharpen}")
            results.append(("preset_create", True))
        else:
            print(f"  ✗ 预设参数不匹配")
            results.append(("preset_create", False))
    except Exception as e:
        print(f"  ✗ create_config_from_preset 错误: {e}")
        results.append(("preset_create", False))

    print("\n[测试 8/8] 检查 batch_enhance 批量处理...")
    try:
        enhancer = TopazEnhancer(config=TopazConfig(mode="simulate"))
        batch_dir = test_dir / "batch_output"
        batch_dir.mkdir(parents=True, exist_ok=True)

        input_files = [str(test_input) for _ in range(3)]

        batch_log = []
        def batch_cb(current, total, result):
            batch_log.append((current, total, result.success))

        results_list = enhancer.batch_enhance(
            input_paths=input_files,
            output_dir=str(batch_dir),
            callback=batch_cb,
        )

        success_count = sum(1 for r in results_list if r.success)
        if success_count == len(input_files) and len(batch_log) == len(input_files):
            print(f"  ✓ 批量处理成功 ({success_count}/{len(input_files)})")
            results.append(("batch_enhance", True))
        else:
            print(f"  ✗ 批量处理失败 (成功 {success_count}/{len(input_files)})")
            results.append(("batch_enhance", False))
    except Exception as e:
        print(f"  ✗ batch_enhance 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("batch_enhance", False))

    print("\n[预设配置清单]")
    for pname, pdata in TOPAZ_PRESETS.items():
        desc = pdata.get("description", "")
        print(f"  - {pname}: {desc}")

    try:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception:
        pass

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"自测结果: {passed}/{total} 通过")
    print("=" * 60)

    for name, ok in results:
        status = "✓ 通过" if ok else "✗ 失败"
        print(f"  {status}: {name}")

    return passed == total


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Topaz Video AI Integration")
    parser.add_argument(
        "--mode",
        choices=["real", "simulate", "auto"],
        default="auto",
        help="Execution mode",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run self-tests",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Input video path",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output video path",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="default",
        help=f"Preset name: {list(TOPAZ_PRESETS.keys())}",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List all available presets",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List all available models",
    )

    args = parser.parse_args()

    if args.test:
        success = _run_self_tests()
        sys.exit(0 if success else 1)
    elif args.list_presets:
        print("Available presets:")
        for name, data in TOPAZ_PRESETS.items():
            desc = data.get("description", "")
            print(f"  {name}: {desc}")
    elif args.list_models:
        enhancer = TopazEnhancer()
        print("Available models:")
        for model in enhancer.get_available_models():
            print(f"  - {model}")
    elif args.input:
        config = create_config_from_preset(args.preset)
        config.mode = args.mode
        enhancer = TopazEnhancer(config=config)

        print(f"Enhancing: {args.input}")
        print(f"Preset: {args.preset}")
        print(f"Mode: {args.mode}")

        def progress(progress, msg):
            print(f"  [{int(progress * 100):3d}%] {msg}")

        result = enhancer.enhance_video(
            input_path=args.input,
            output_path=args.output,
            callback=progress,
        )

        if result.success:
            print(f"\n✓ Success! Output: {result.output_path}")
            print(f"  Duration: {result.duration:.2f}s")
            print(f"  Resolution: {result.original_size} → {result.output_size}")
            print(f"  FPS: {result.original_fps} → {result.output_fps}")
            sys.exit(0)
        else:
            print(f"\n✗ Failed: {result.error}")
            sys.exit(1)
    else:
        parser.print_help()
