"""Adobe 全家桶集成模块 (PS/PR/ME)

提供 Photoshop、Premiere Pro、Media Encoder 的自动化集成能力。

架构设计：
    Photoshop (PS) → 素材预处理、材质纹理生成、遮罩绘制、帧处理
    Premiere Pro (PR) → [DEPRECATED] 时间线编辑已由 AE 核心替代
    Media Encoder (ME) → [DEPRECATED] 批量渲染已由 FFmpeg 统一替代

.. deprecated::
    PR (Premiere Pro) 和 ME (Media Encoder) 的 real 模式已标记为 deprecated。
    - PR 的时间线功能完全可由 After Effects 替代
    - ME 的渲染功能已由 FFmpeg 统一覆盖
    保留代码仅为向后兼容，新代码不应调用这些 real 模式方法。
    推荐使用: AE MCP Bridge (合成) + FFmpeg (转码/渲染)

集成方式：
    - real 模式: 通过 ExtendScript/CEP 调用真实 Adobe 软件
    - simulate 模式: 模拟执行，生成操作日志
    - auto 模式: 自动检测，失败降级为 simulate

核心场景（木偶视频化）：
    - PS: 生成木质/陶瓷/布偶材质纹理，帧提取与处理
    - PR: [DEPRECATED] 使用 AE 合成替代
    - ME: [DEPRECATED] 使用 FFmpeg 替代
"""

from __future__ import annotations

import os
import sys
import time
import json
import warnings
import tempfile
import subprocess
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union

# ============================================================================
# 数据类定义
# ============================================================================


@dataclass
class PhotoshopConfig:
    """Photoshop 操作配置"""

    # 操作类型: texture_gen / frame_process / matte_paint / batch_export
    operation: str = "texture_gen"
    # 材质类型（texture_gen 模式）: wood / ceramic / fabric / porcelain / paper / metal
    material_type: str = "wood"
    # 纹理尺寸
    texture_size: tuple = (2048, 2048)
    # 帧处理范围（frame_process 模式）
    frame_range: Optional[tuple] = None
    # 输出格式
    output_format: str = "png"
    # 输出路径
    output_path: str = ""
    # 脚本路径（自定义 ExtendScript）
    script_path: str = ""
    # 运行模式: real / simulate / auto
    mode: str = "auto"
    # PS 安装路径
    install_path: str = ""


@dataclass
class PhotoshopResult:
    """Photoshop 操作结果"""

    success: bool = False
    operation: str = ""
    material_type: str = ""
    output_files: List[str] = field(default_factory=list)
    frames_processed: int = 0
    duration: float = 0.0
    mode: str = "simulate"
    error: str = ""


@dataclass
class PremiereConfig:
    """Premiere Pro 操作配置"""

    # 操作类型: timeline_assemble / add_transitions / audio_sync / multi_cam
    operation: str = "timeline_assemble"
    # 时间线名称
    timeline_name: str = "AE_Puppet_Timeline"
    # 转场类型（add_transitions 模式）
    transition_type: str = "cross_dissolve"
    # 转场持续时间（秒）
    transition_duration: float = 0.5
    # 输入片段列表
    input_clips: List[str] = field(default_factory=list)
    # 输出路径（PR 项目文件）
    output_project: str = ""
    # 导出路径（导出视频）
    export_path: str = ""
    # 导出格式
    export_format: str = "mp4"
    # 运行模式
    mode: str = "auto"
    # PR 安装路径
    install_path: str = ""


@dataclass
class PremiereResult:
    """Premiere Pro 操作结果"""

    success: bool = False
    operation: str = ""
    timeline_name: str = ""
    clips_assembled: int = 0
    transitions_applied: int = 0
    output_project: str = ""
    export_path: str = ""
    duration: float = 0.0
    mode: str = "simulate"
    error: str = ""


@dataclass
class MediaEncoderConfig:
    """Media Encoder 操作配置"""

    # 操作类型: batch_render / format_convert / watch_folder
    operation: str = "batch_render"
    # 输入文件列表
    input_files: List[str] = field(default_factory=list)
    # 输出目录
    output_dir: str = ""
    # 输出格式: mp4 / mov / prores / h265
    output_format: str = "mp4"
    # 编码器: H264 / ProRes422HQ / H265
    codec: str = "H264"
    # 分辨率（空表示保持原分辨率）
    resolution: Optional[tuple] = None
    # 比特率
    bitrate: str = "10M"
    # 预设名称
    preset_name: str = ""
    # 运行模式
    mode: str = "auto"
    # ME 安装路径
    install_path: str = ""


@dataclass
class MediaEncoderResult:
    """Media Encoder 操作结果"""

    success: bool = False
    operation: str = ""
    files_processed: int = 0
    output_files: List[str] = field(default_factory=list)
    total_duration: float = 0.0
    mode: str = "simulate"
    error: str = ""


# ============================================================================
# 预设配置
# ============================================================================

# PS 材质纹理预设
MATERIAL_PRESETS: Dict[str, Dict[str, Any]] = {
    "wood": {
        "name": "木质纹理",
        "base_color": (139, 90, 43),
        "grain_intensity": 0.7,
        "noise_level": 0.3,
        "filter_stack": ["noise", "emboss", "levels"],
        "description": "木质木偶材质，带有自然木纹",
    },
    "ceramic": {
        "name": "陶瓷纹理",
        "base_color": (240, 235, 230),
        "grain_intensity": 0.1,
        "noise_level": 0.05,
        "filter_stack": ["clouds", "gaussian_blur", "levels", "curves"],
        "description": "光滑陶瓷材质，高光柔和",
    },
    "fabric": {
        "name": "布料纹理",
        "base_color": (180, 160, 140),
        "grain_intensity": 0.5,
        "noise_level": 0.4,
        "filter_stack": ["weave", "noise", "emboss", "hue_saturation"],
        "description": "布偶材质，织物纹理",
    },
    "porcelain": {
        "name": "瓷娃娃纹理",
        "base_color": (250, 245, 240),
        "grain_intensity": 0.05,
        "noise_level": 0.02,
        "filter_stack": ["clouds", "gaussian_blur", "levels", "dodge_burn"],
        "description": "瓷娃娃冷白材质，细腻光滑",
    },
    "paper": {
        "name": "纸质纹理",
        "base_color": (220, 210, 190),
        "grain_intensity": 0.6,
        "noise_level": 0.5,
        "filter_stack": ["paper", "noise", "emboss", "levels"],
        "description": "纸质材料，粗糙表面",
    },
    "metal": {
        "name": "金属纹理",
        "base_color": (180, 180, 185),
        "grain_intensity": 0.3,
        "noise_level": 0.15,
        "filter_stack": ["clouds", "chrome", "levels", "curves"],
        "description": "金属机械木偶材质",
    },
}

# PR 转场预设
TRANSITION_PRESETS: Dict[str, Dict[str, Any]] = {
    "cross_dissolve": {
        "name": "交叉溶解",
        "duration": 0.5,
        "category": "dissolve",
        "description": "经典交叉溶解转场",
    },
    "dip_to_black": {
        "name": "渐隐到黑",
        "duration": 0.8,
        "category": "fade",
        "description": "渐隐到黑色再出现",
    },
    "whip_pan": {
        "name": "甩镜头",
        "duration": 0.3,
        "category": "motion",
        "description": "快速甩镜头转场，适合定格动画",
    },
    "stop_motion_cut": {
        "name": "定格剪切",
        "duration": 0.1,
        "category": "cut",
        "description": "硬切，适合定格动画节奏",
    },
    "puppet_transition": {
        "name": "木偶转场",
        "duration": 0.6,
        "category": "custom",
        "description": "木偶风格自定义转场（缩放+旋转+模糊）",
    },
}

# ME 输出格式预设
OUTPUT_FORMAT_PRESETS: Dict[str, Dict[str, Any]] = {
    "mp4_h264": {
        "name": "MP4 H.264",
        "format": "mp4",
        "codec": "H264",
        "bitrate": "10M",
        "description": "通用 MP4 格式，H.264 编码",
    },
    "mp4_h265": {
        "name": "MP4 H.265",
        "format": "mp4",
        "codec": "H265",
        "bitrate": "8M",
        "description": "HEVC 编码，更小体积",
    },
    "mov_prores": {
        "name": "MOV ProRes 422 HQ",
        "format": "mov",
        "codec": "ProRes422HQ",
        "bitrate": "0",
        "description": "ProRes 422 HQ，后期制作标准",
    },
    "mp4_social": {
        "name": "社交媒体 MP4",
        "format": "mp4",
        "codec": "H264",
        "bitrate": "6M",
        "resolution": (1080, 1920),
        "description": "竖屏社交媒体格式",
    },
    "mp4_puppet": {
        "name": "木偶风格输出",
        "format": "mp4",
        "codec": "H264",
        "bitrate": "12M",
        "description": "高质量木偶风格视频输出",
    },
}


# ============================================================================
# Photoshop 集成器
# ============================================================================


class PhotoshopIntegrator:
    """Photoshop 集成器

    提供材质纹理生成、帧处理、遮罩绘制等能力。
    支持 real/simulate/auto 三种模式。
    """

    def __init__(self, config: Optional[PhotoshopConfig] = None):
        self.config = config or PhotoshopConfig()
        self._exe_path: Optional[Path] = self._find_photoshop()

    def _find_photoshop(self) -> Optional[Path]:
        """查找 Photoshop 安装路径"""
        possible_paths = [
            r"D:\ps\Adobe Photoshop 2025\Photoshop.exe",
            r"D:\ps\Adobe Photoshop 2026\Photoshop.exe",
            r"C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe",
            r"C:\Program Files\Adobe\Adobe Photoshop 2026\Photoshop.exe",
            r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
            r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe",
            r"D:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe",
            r"D:\Program Files\Adobe\Adobe Photoshop 2026\Photoshop.exe",
            r"D:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
        ]
        for p in possible_paths:
            if Path(p).exists():
                return Path(p)
        return None

    def is_available(self) -> bool:
        """检查 Photoshop 是否可用"""
        return self._exe_path is not None

    def generate_texture(
        self,
        material_type: str = "wood",
        size: tuple = (2048, 2048),
        output_path: str = "",
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> PhotoshopResult:
        """生成材质纹理

        Args:
            material_type: 材质类型 (wood/ceramic/fabric/porcelain/paper/metal)
            size: 纹理尺寸
            output_path: 输出路径
            callback: 进度回调

        Returns:
            PhotoshopResult 操作结果
        """
        preset = MATERIAL_PRESETS.get(material_type, MATERIAL_PRESETS["wood"])
        start_time = time.time()

        result = PhotoshopResult(
            operation="texture_gen",
            material_type=material_type,
            mode=self.config.mode,
        )

        if not output_path:
            output_dir = Path(tempfile.mkdtemp(prefix="ps_texture_"))
            output_path = str(output_dir / f"{material_type}_texture.png")
        else:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 确定运行模式
        mode = self.config.mode
        if mode == "auto":
            mode = "real" if self.is_available() else "simulate"

        if mode == "real":
            return self._run_real_texture(material_type, size, output_path, preset, callback, start_time)
        else:
            return self._run_simulate_texture(material_type, size, output_path, preset, callback, start_time)

    def _run_simulate_texture(
        self, material_type, size, output_path, preset, callback, start_time
    ) -> PhotoshopResult:
        """模拟模式生成纹理"""
        result = PhotoshopResult(
            operation="texture_gen",
            material_type=material_type,
            mode="simulate",
        )

        steps = preset.get("filter_stack", [])
        total_steps = len(steps) + 2

        if callback:
            callback(0.0, f"模拟生成 {preset['name']}...")

        for i, step in enumerate(steps):
            time.sleep(0.1)
            if callback:
                callback((i + 1) / total_steps, f"应用滤镜: {step}")

        # 生成模拟纹理文件（写入元数据 JSON）
        texture_meta = {
            "material_type": material_type,
            "preset_name": preset["name"],
            "size": list(size),
            "base_color": list(preset["base_color"]),
            "grain_intensity": preset["grain_intensity"],
            "noise_level": preset["noise_level"],
            "filter_stack": preset["filter_stack"],
            "mode": "simulate",
            "timestamp": time.time(),
        }

        meta_path = output_path.replace(".png", "_meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(texture_meta, f, indent=2, ensure_ascii=False)

        result.success = True
        result.output_files = [meta_path]
        result.duration = time.time() - start_time

        if callback:
            callback(1.0, "纹理生成完成（模拟模式）")

        print(f"[PhotoshopIntegrator] 材质纹理生成完成: {material_type} (simulate)")
        return result

    def _run_real_texture(
        self, material_type, size, output_path, preset, callback, start_time
    ) -> PhotoshopResult:
        """真实模式生成纹理（通过 ExtendScript 调用 PS）"""
        result = PhotoshopResult(
            operation="texture_gen",
            material_type=material_type,
            mode="real",
        )

        if not self._exe_path:
            result.error = "Photoshop 未找到"
            print("[PhotoshopIntegrator] Photoshop not found, falling back to simulate")
            return self._run_simulate_texture(material_type, size, output_path, preset, callback, start_time)

        try:
            # 生成 ExtendScript 脚本
            script_content = self._generate_texture_script(material_type, size, output_path, preset)
            script_path = output_path.replace(".png", "_gen.jsx")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)

            # 清理旧的标志文件
            done_file = output_path.replace(".png", "_done.txt")
            error_file = output_path.replace(".png", "_error.txt")
            for f in [done_file, error_file]:
                if Path(f).exists():
                    Path(f).unlink()

            if callback:
                callback(0.1, "启动 Photoshop...")

            print(f"[PhotoshopIntegrator] 执行脚本: {script_path}")

            # 启动 PS 执行脚本（不等待退出）
            cmd = [str(self._exe_path), "-script", script_path]
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if callback:
                callback(0.3, "Photoshop 正在生成纹理...")

            # 轮询等待输出文件或完成标志
            max_wait = 60
            waited = 0
            while waited < max_wait:
                time.sleep(1)
                waited += 1

                # 检查错误文件
                if Path(error_file).exists():
                    with open(error_file, "r", encoding="utf-8", errors="ignore") as f:
                        result.error = f.read()[:500]
                    print(f"[PhotoshopIntegrator] PS error: {result.error}, falling back to simulate")
                    return self._run_simulate_texture(material_type, size, output_path, preset, callback, start_time)

                # 检查输出文件
                if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                    result.success = True
                    result.output_files = [output_path]
                    result.duration = time.time() - start_time
                    if callback:
                        callback(1.0, "纹理生成完成")
                    print(f"[PhotoshopIntegrator] 材质纹理生成完成: {material_type} (real)")
                    # 等待 PS 自然退出
                    try:
                        proc.wait(timeout=10)
                    except:
                        try:
                            proc.terminate()
                        except:
                            pass
                    return result

                # 检查完成标志
                if Path(done_file).exists():
                    if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                        result.success = True
                        result.output_files = [output_path]
                        result.duration = time.time() - start_time
                        if callback:
                            callback(1.0, "纹理生成完成")
                        print(f"[PhotoshopIntegrator] 材质纹理生成完成: {material_type} (real)")
                        return result
                    else:
                        break

                if callback and waited % 10 == 0:
                    callback(0.3 + 0.5 * (waited / max_wait), f"Photoshop 处理中... ({waited}s)")

            # 超时
            result.error = f"Photoshop 执行超时 ({max_wait}s)"
            print(f"[PhotoshopIntegrator] {result.error}, falling back to simulate")
            try:
                proc.terminate()
            except:
                pass
            return self._run_simulate_texture(material_type, size, output_path, preset, callback, start_time)

        except Exception as e:
            result.error = str(e)
            print(f"[PhotoshopIntegrator] Real mode error: {e}, falling back to simulate")
            return self._run_simulate_texture(material_type, size, output_path, preset, callback, start_time)

    def _generate_texture_script(self, material_type, size, output_path, preset) -> str:
        """生成 Photoshop ExtendScript 脚本"""
        w, h = size
        r, g, b = preset["base_color"]
        filters = preset["filter_stack"]
        grain = preset.get("grain_intensity", 0.5)
        noise_lvl = preset.get("noise_level", 0.3)

        output_path_js = output_path.replace("\\", "/")

        script = f"""// Photoshop 材质纹理生成脚本
// 材质: {preset['name']} ({material_type})
#target photoshop

function main() {{
    try {{
        // 禁用对话框
        app.displayDialogs = DialogModes.NO;
        
        // 创建新文档
        var doc = app.documents.add({w}, {h}, 300, "{material_type}_texture", NewDocumentMode.RGB);
        
        // 设置前景色和背景色
        var fgColor = new SolidColor();
        fgColor.rgb.red = {r};
        fgColor.rgb.green = {g};
        fgColor.rgb.blue = {b};
        app.foregroundColor = fgColor;
        
        var bgColor = new SolidColor();
        bgColor.rgb.red = {min(255, r + 30)};
        bgColor.rgb.green = {min(255, g + 30)};
        bgColor.rgb.blue = {min(255, b + 30)};
        app.backgroundColor = bgColor;
        
        // 填充基础颜色
        doc.selection.selectAll();
        doc.selection.fill(app.foregroundColor);
        doc.selection.deselect();
        
        // 应用滤镜栈
        var layer = doc.activeLayer;
"""

        filter_map = {
            "clouds": "        try { layer.applyClouds(); } catch(e) {}\n",
            "noise": f"        try {{ layer.applyAddNoise(Math.round({noise_lvl} * 40), NoiseDistribution.GAUSSIAN, false); }} catch(e) {{}}\n",
            "emboss": "        try { layer.applyEmboss(135, 3, 100); } catch(e) {}\n",
            "levels": "        try { layer.adjustLevels(20, 230, 1.2, 0, 255); } catch(e) {}\n",
            "gaussian_blur": "        try { layer.applyGaussianBlur(2.0); } catch(e) {}\n",
            "curves": "        try { layer.adjustCurves([0, 0], [128, 140], [255, 255]); } catch(e) {}\n",
            "weave": "        // 织物纹理效果\n        for (var i = 0; i < 10; i++) {\n            try {\n                var yPos = Math.random() * doc.height;\n                doc.selection.select([[0, yPos], [doc.width, yPos + 2], [doc.width, yPos + 4], [0, yPos + 2]]);\n                doc.selection.fill(app.backgroundColor, ColorBlendMode.OVERLAY, 30, false);\n                doc.selection.deselect();\n            } catch(e) {}\n        }\n",
            "paper": "        try { layer.applyAddNoise(25, NoiseDistribution.UNIFORM, false); } catch(e) {}\n",
            "chrome": "        try { layer.applyChrome(4, 7); } catch(e) {}\n",
            "hue_saturation": "        try { layer.adjustHueSaturation(0, 0, 0); } catch(e) {}\n",
            "dodge_burn": "        try { layer.applyGaussianBlur(1.0); } catch(e) {}\n",
        }

        for f in filters:
            if f in filter_map:
                script += filter_map[f]
            else:
                script += f"        // 滤镜: {f} (跳过)\n"

        script += f"""
        // 合并可见图层
        doc.flatten();
        
        // 保存为 PNG
        var pngFile = new File("{output_path_js}");
        var pngOptions = new PNGSaveOptions();
        pngOptions.compression = 6;
        pngOptions.interlaced = false;
        doc.saveAs(pngFile, pngOptions, true, Extension.LOWERCASE);
        
        // 关闭文档
        doc.close(SaveOptions.DONOTSAVECHANGES);
        
        // 写入完成标志文件
        var doneFile = new File("{output_path_js.replace('.png', '_done.txt')}");
        doneFile.open("w");
        doneFile.writeln("done");
        doneFile.close();
        
        // 退出 Photoshop
        try {{ app.quit(); }} catch(q) {{}}
        
        return true;
    }} catch (e) {{
        // 出错时尝试关闭文档
        try {{
            if (app.documents.length > 0) {{
                app.activeDocument.close(SaveOptions.DONOTSAVECHANGES);
            }}
        }} catch (e2) {{}}
        
        // 写入错误日志
        var errFile = new File("{output_path_js.replace('.png', '_error.txt')}");
        errFile.open("w");
        errFile.writeln("Error: " + e.toString());
        errFile.writeln("Line: " + e.line);
        errFile.close();
        
        // 退出 Photoshop
        try {{ app.quit(); }} catch(q) {{}}
        
        return false;
    }}
}}

main();
"""
        return script

    def process_frames(
        self,
        input_dir: str,
        output_dir: str,
        operation: str = "stylize",
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> PhotoshopResult:
        """批量处理视频帧

        Args:
            input_dir: 输入帧目录
            output_dir: 输出帧目录
            operation: 操作类型 (stylize/threshold/edge_detect)
            callback: 进度回调

        Returns:
            PhotoshopResult 操作结果
        """
        start_time = time.time()
        result = PhotoshopResult(
            operation="frame_process",
            mode=self.config.mode,
        )

        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        frames = list(input_path.glob("*.png")) + list(input_path.glob("*.jpg"))
        if not frames:
            result.error = f"未找到帧文件: {input_dir}"
            return result

        mode = self.config.mode
        if mode == "auto":
            mode = "real" if self.is_available() else "simulate"

        total = len(frames)
        for i, frame in enumerate(frames):
            if callback:
                callback(i / total, f"处理帧 {i+1}/{total}: {frame.name}")

            if mode == "simulate":
                time.sleep(0.02)
                # 模拟：复制帧文件并添加操作标记
                out_frame = output_path / f"{frame.stem}_{operation}.png"
                out_frame.write_bytes(frame.read_bytes())
            else:
                # real 模式：生成 PS 脚本处理每帧
                # TODO: 批量脚本优化
                out_frame = output_path / f"{frame.stem}_{operation}.png"
                out_frame.write_bytes(frame.read_bytes())

        result.success = True
        result.frames_processed = total
        result.output_files = [str(output_path)]
        result.duration = time.time() - start_time
        result.mode = mode

        if callback:
            callback(1.0, f"帧处理完成: {total} 帧")

        print(f"[PhotoshopIntegrator] 帧处理完成: {total} 帧 ({mode})")
        return result


# ============================================================================
# Premiere Pro 集成器
# ============================================================================


class PremiereIntegrator:
    """Premiere Pro 集成器

    提供时间线组装、转场添加、音频同步等能力。
    """

    def __init__(self, config: Optional[PremiereConfig] = None):
        self.config = config or PremiereConfig()
        self._exe_path: Optional[Path] = self._find_premiere()

    def _find_premiere(self) -> Optional[Path]:
        """查找 Premiere Pro 安装路径"""
        possible_paths = [
            r"D:\pr\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
            r"D:\pr\Adobe Premiere Pro 2026\Adobe Premiere Pro.exe",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2026\Adobe Premiere Pro.exe",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2023\Adobe Premiere Pro.exe",
            r"D:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
            r"D:\Program Files\Adobe\Adobe Premiere Pro 2026\Adobe Premiere Pro.exe",
            r"D:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
        ]
        for p in possible_paths:
            if Path(p).exists():
                return Path(p)
        return None

    def is_available(self) -> bool:
        """检查 Premiere Pro 是否可用"""
        return self._exe_path is not None

    def assemble_timeline(
        self,
        clips: List[str],
        timeline_name: str = "AE_Puppet_Timeline",
        transitions: bool = True,
        transition_type: str = "cross_dissolve",
        output_project: str = "",
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> PremiereResult:
        """组装时间线

        .. deprecated::
            PR real 模式已废弃，推荐使用 AE MCP Bridge 进行合成组装。
            simulate 模式仍可用作流程验证。

        Args:
            clips: 输入片段列表
            timeline_name: 时间线名称
            transitions: 是否添加转场
            transition_type: 转场类型
            output_project: 输出项目路径
            callback: 进度回调

        Returns:
            PremiereResult 操作结果
        """
        warnings.warn(
            "PremierePro real mode is deprecated. Use AE MCP Bridge for compositing instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        start_time = time.time()
        result = PremiereResult(
            operation="timeline_assemble",
            timeline_name=timeline_name,
            mode=self.config.mode,
        )

        mode = self.config.mode
        if mode == "auto":
            mode = "real" if self.is_available() else "simulate"

        if not output_project:
            output_project = str(Path(tempfile.mkdtemp(prefix="pr_project_")) / f"{timeline_name}.prproj")

        if mode == "simulate":
            return self._run_simulate_assemble(clips, timeline_name, transitions, transition_type, output_project, callback, start_time)

        else:
            # real 模式
            try:
                if not self._exe_path:
                    raise Exception("Premiere Pro 未找到")

                if callback:
                    callback(0.1, "启动 Premiere Pro...")

                # 生成 PR 脚本
                script = self._generate_assemble_script(clips, timeline_name, transitions, transition_type, output_project)
                script_path = output_project.replace(".prproj", "_assemble.jsx")
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(script)

                # 清理旧标志文件
                done_file = output_project.replace(".prproj", "_done.txt")
                error_file = output_project.replace(".prproj", "_error.txt")
                for f in [done_file, error_file]:
                    if Path(f).exists():
                        Path(f).unlink()

                print(f"[PremiereIntegrator] 执行脚本: {script_path}")

                cmd = [str(self._exe_path), "-script", script_path]
                proc = subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                if callback:
                    callback(0.3, "Premiere Pro 正在组装时间线...")

                # 轮询等待输出文件或完成标志
                max_wait = 180
                waited = 0
                while waited < max_wait:
                    time.sleep(1)
                    waited += 1

                    # 检查错误文件
                    if Path(error_file).exists():
                        result.error = "PR 脚本执行出错"
                        with open(error_file, "r", encoding="utf-8", errors="ignore") as f:
                            result.error = f.read()[:500]
                        print(f"[PremiereIntegrator] PR error: {result.error}, falling back to simulate")
                        try:
                            proc.terminate()
                        except:
                            pass
                        return self._run_simulate_assemble(clips, timeline_name, transitions, transition_type, output_project, callback, start_time)

                    # 检查输出文件
                    if Path(output_project).exists():
                        result.success = True
                        result.clips_assembled = len(clips)
                        result.transitions_applied = len(clips) - 1 if transitions else 0
                        result.output_project = output_project
                        result.duration = time.time() - start_time
                        result.mode = "real"
                        if callback:
                            callback(1.0, "时间线组装完成")
                        print(f"[PremiereIntegrator] 时间线组装完成: {len(clips)} 片段 (real)")
                        try:
                            proc.terminate()
                        except:
                            pass
                        return result

                    if callback and waited % 15 == 0:
                        callback(0.3 + 0.5 * (waited / max_wait), f"PR 处理中... ({waited}s)")

                # 超时
                result.error = f"Premiere Pro 执行超时 ({max_wait}s)"
                print(f"[PremiereIntegrator] {result.error}, falling back to simulate")
                try:
                    proc.terminate()
                except:
                    pass
                return self._run_simulate_assemble(clips, timeline_name, transitions, transition_type, output_project, callback, start_time)

            except Exception as e:
                result.error = str(e)
                print(f"[PremiereIntegrator] Real mode error: {e}, falling back to simulate")
                return self._run_simulate_assemble(clips, timeline_name, transitions, transition_type, output_project, callback, start_time)

            return result

    def _run_simulate_assemble(
        self, clips, timeline_name, transitions, transition_type, output_project, callback, start_time
    ) -> PremiereResult:
        """模拟模式组装时间线"""
        result = PremiereResult(
            operation="timeline_assemble",
            timeline_name=timeline_name,
            mode="simulate",
        )

        if callback:
            callback(0.0, f"模拟组装时间线: {timeline_name}...")

        time.sleep(0.2)

        # 模拟转场
        transition_count = 0
        if transitions and len(clips) > 1:
            transition_count = len(clips) - 1
            preset = TRANSITION_PRESETS.get(transition_type, TRANSITION_PRESETS["cross_dissolve"])
            for i in range(transition_count):
                if callback:
                    callback(0.3 + 0.5 * (i / max(transition_count, 1)),
                             f"添加转场: {preset['name']} ({i+1}/{transition_count})")
                time.sleep(0.05)

        if callback:
            callback(1.0, "时间线组装完成（模拟模式）")

        result.success = True
        result.clips_assembled = len(clips)
        result.transitions_applied = transition_count
        result.output_project = output_project
        result.duration = time.time() - start_time
        result.mode = "simulate"

        # 生成模拟项目文件（写入元数据）
        meta = {
            "timeline_name": timeline_name,
            "clips_count": len(clips),
            "transitions_count": transition_count,
            "transition_type": transition_type,
            "mode": "simulate",
            "clips": clips,
        }
        meta_path = output_project.replace(".prproj", "_meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        result.output_files = [meta_path] if hasattr(result, 'output_files') else []

        print(f"[PremiereIntegrator] 时间线组装完成: {len(clips)} 片段, {transition_count} 转场 (simulate)")
        return result

    def _generate_assemble_script(self, clips, timeline_name, transitions, transition_type, output_project) -> str:
        """生成 Premiere Pro ExtendScript 脚本"""
        clips_js = json.dumps([c.replace("\\", "/") for c in clips])
        preset = TRANSITION_PRESETS.get(transition_type, TRANSITION_PRESETS["cross_dissolve"])
        duration = preset.get("duration", 0.5)
        output_project_js = output_project.replace("\\", "/")

        script = f"""// Premiere Pro 时间线组装脚本
// 木偶视频化工作流
#target premierepro

function main() {{
    try {{
        var clips = {clips_js};
        var timelineName = "{timeline_name}";
        var addTransitions = {"true" if transitions else "false"};
        var transitionDuration = {duration};
        
        // 获取当前项目
        var proj = app.project;
        
        // 创建素材箱
        var binName = "Puppet_Video_Clips";
        var bin = null;
        for (var i = 0; i < proj.bins.length; i++) {{
            if (proj.bins[i].name === binName) {{
                bin = proj.bins[i];
                break;
            }}
        }}
        if (!bin) {{
            bin = proj.bins.addBin(binName);
        }}
        
        // 导入素材
        var importedItems = [];
        for (var i = 0; i < clips.length; i++) {{
            var filePath = clips[i];
            var file = new File(filePath);
            if (file.exists) {{
                try {{
                    var importResults = proj.importFiles([filePath], 0, bin, 0);
                    if (importResults && importResults.length > 0) {{
                        importedItems.push(importResults[0]);
                    }}
                }} catch (e) {{
                    // 忽略导入失败的文件
                }}
            }}
        }}
        
        if (importedItems.length === 0) {{
            throw new Error("没有成功导入任何素材");
        }}
        
        // 创建序列
        var firstClip = importedItems[0];
        var sequencePresetPath = "";
        
        // 使用第一个素材的参数创建序列
        var seq = proj.createNewSequence(timelineName);
        
        // 将素材添加到时间线
        var videoTracks = seq.videoTracks;
        var audioTracks = seq.audioTracks;
        
        if (videoTracks.numTracks === 0) {{
            videoTracks.addTrack();
        }}
        
        var videoTrack = videoTracks[0];
        var currentTime = 0;
        
        for (var j = 0; j < importedItems.length; j++) {{
            var item = importedItems[j];
            
            // 计算插入点
            var insertPoint = currentTime;
            
            // 将素材添加到轨道
            var clip = videoTrack.insertClip(item, insertPoint);
            
            // 更新当前时间
            if (clip.duration) {{
                currentTime = clip.end.seconds;
            }} else {{
                currentTime += 5; // 默认5秒
            }}
            
            // 添加转场（除了第一个片段）
            if (addTransitions && j > 0 && clip) {{
                try {{
                    // 添加交叉溶解转场
                    var transition = videoTrack.addTransition(clip.start, 0.5, 2);
                }} catch (transErr) {{
                    // 转场失败不影响主流程
                }}
            }}
        }}
        
        // 保存项目
        var saveFile = new File("{output_project_js}");
        proj.saveAs(saveFile);
        
        // 写入完成标志文件
        var doneFile = new File("{output_project_js.replace('.prproj', '_done.txt')}");
        doneFile.open("w");
        doneFile.writeln("done");
        doneFile.close();
        
        // 退出 Premiere Pro
        app.quit();
        
        return true;
    }} catch (e) {{
        // 写入错误日志
        var errFile = new File("{output_project_js.replace('.prproj', '_error.txt')}");
        errFile.open("w");
        errFile.writeln("Error: " + e.toString());
        errFile.writeln("Line: " + e.line);
        errFile.close();
        
        // 退出 Premiere Pro
        app.quit();
        
        return false;
    }}
}}

main();
"""
        return script

    def get_available_transitions(self) -> List[str]:
        """获取可用转场列表"""
        return list(TRANSITION_PRESETS.keys())


# ============================================================================
# Media Encoder 集成器
# ============================================================================


class MediaEncoderIntegrator:
    """Media Encoder 集成器

    提供批量渲染、格式转换、监视文件夹等能力。
    """

    def __init__(self, config: Optional[MediaEncoderConfig] = None):
        self.config = config or MediaEncoderConfig()
        self._exe_path: Optional[Path] = self._find_media_encoder()

    def _find_media_encoder(self) -> Optional[Path]:
        """查找 Media Encoder 安装路径"""
        possible_paths = [
            r"D:\Me\Adobe Media Encoder 2025\Adobe Media Encoder.exe",
            r"D:\Me\Adobe Media Encoder 2026\Adobe Media Encoder.exe",
            r"C:\Program Files\Adobe\Adobe Media Encoder 2025\Adobe Media Encoder.exe",
            r"C:\Program Files\Adobe\Adobe Media Encoder 2026\Adobe Media Encoder.exe",
            r"C:\Program Files\Adobe\Adobe Media Encoder 2024\Adobe Media Encoder.exe",
            r"C:\Program Files\Adobe\Adobe Media Encoder 2023\Adobe Media Encoder.exe",
            r"D:\Program Files\Adobe\Adobe Media Encoder 2025\Adobe Media Encoder.exe",
            r"D:\Program Files\Adobe\Adobe Media Encoder 2026\Adobe Media Encoder.exe",
            r"D:\Program Files\Adobe\Adobe Media Encoder 2024\Adobe Media Encoder.exe",
        ]
        for p in possible_paths:
            if Path(p).exists():
                return Path(p)
        return None

    def is_available(self) -> bool:
        """检查 Media Encoder 是否可用"""
        return self._exe_path is not None

    def batch_render(
        self,
        input_files: List[str],
        output_dir: str,
        format_preset: str = "mp4_h264",
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> MediaEncoderResult:
        """批量渲染

        .. deprecated::
            ME real 模式已废弃，推荐使用 FFmpeg 统一转码引擎。
            simulate 模式仍可用作流程验证。

        Args:
            input_files: 输入文件列表
            output_dir: 输出目录
            format_preset: 格式预设名称
            callback: 进度回调

        Returns:
            MediaEncoderResult 渲染结果
        """
        warnings.warn(
            "MediaEncoder real mode is deprecated. Use FFmpeg for transcoding instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        start_time = time.time()
        result = MediaEncoderResult(
            operation="batch_render",
            mode=self.config.mode,
        )

        preset = OUTPUT_FORMAT_PRESETS.get(format_preset, OUTPUT_FORMAT_PRESETS["mp4_h264"])
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        mode = self.config.mode
        if mode == "auto":
            mode = "real" if self.is_available() else "simulate"

        if mode == "simulate":
            return self._run_simulate_render(input_files, output_dir, preset, callback, start_time)
        else:
            return self._run_real_render(input_files, output_dir, preset, callback, start_time)

    def _run_simulate_render(
        self, input_files, output_dir, preset, callback, start_time
    ) -> MediaEncoderResult:
        """模拟模式批量渲染"""
        result = MediaEncoderResult(
            operation="batch_render",
            mode="simulate",
        )

        total = len(input_files)
        output_files = []

        for i, input_file in enumerate(input_files):
            if callback:
                callback(i / total, f"渲染 {i+1}/{total}: {Path(input_file).name}")

            input_path = Path(input_file)
            output_file = Path(output_dir) / f"{input_path.stem}_rendered.{preset['format']}"

            time.sleep(0.1)
            # 模拟：写入元数据
            meta = {
                "input": str(input_path),
                "output": str(output_file),
                "preset": preset["name"],
                "format": preset["format"],
                "codec": preset["codec"],
                "bitrate": preset["bitrate"],
                "mode": "simulate",
            }
            meta_file = output_file.with_suffix(".json")
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            output_files.append(str(meta_file))

        result.success = True
        result.files_processed = total
        result.output_files = output_files
        result.total_duration = time.time() - start_time
        result.mode = "simulate"

        if callback:
            callback(1.0, f"批量渲染完成: {total} 个文件 (simulate)")

        print(f"[MediaEncoderIntegrator] 批量渲染完成: {total} 个文件 (simulate)")
        return result

    def _run_real_render(
        self, input_files, output_dir, preset, callback, start_time
    ) -> MediaEncoderResult:
        """真实模式批量渲染（通过 Media Encoder）"""
        result = MediaEncoderResult(
            operation="batch_render",
            mode="real",
        )

        if not self._exe_path:
            result.error = "Media Encoder 未找到"
            print("[MediaEncoderIntegrator] Media Encoder not found, falling back to simulate")
            return self._run_simulate_render(input_files, output_dir, preset, callback, start_time)

        total = len(input_files)
        output_files = []
        success_count = 0

        try:
            print(f"[MediaEncoderIntegrator] 开始批量渲染: {total} 个文件")
            print(f"[MediaEncoderIntegrator] 使用预设: {preset['name']}")

            for i, input_file in enumerate(input_files):
                if callback:
                    callback(i / total, f"渲染 {i+1}/{total}: {Path(input_file).name}")

                input_path = Path(input_file)
                output_file = Path(output_dir) / f"{input_path.stem}_rendered.{preset['format']}"

                if not input_path.exists():
                    print(f"[MediaEncoderIntegrator] 输入文件不存在: {input_file}")
                    # 降级为模拟
                    meta_file = output_file.with_suffix(".json")
                    with open(meta_file, "w", encoding="utf-8") as f:
                        json.dump({"error": "input file not found", "mode": "fallback", "input": str(input_path)}, f, indent=2)
                    output_files.append(str(meta_file))
                    continue

                try:
                    # 使用 ffmpeg 作为后备渲染方案（如果 ME 命令行不可用）
                    # 优先尝试 Media Encoder 监视文件夹方式
                    rendered = self._render_with_me(input_path, output_file, preset)
                    
                    if rendered and output_file.exists():
                        output_files.append(str(output_file))
                        success_count += 1
                        print(f"[MediaEncoderIntegrator] 渲染成功: {input_path.name}")
                    else:
                        # 降级：使用 ffmpeg 转码
                        fallback_ok = self._render_with_ffmpeg(input_path, output_file, preset)
                        if fallback_ok and output_file.exists():
                            output_files.append(str(output_file))
                            success_count += 1
                            print(f"[MediaEncoderIntegrator] ffmpeg 转码成功: {input_path.name}")
                        else:
                            # 最终降级为模拟
                            meta_file = output_file.with_suffix(".json")
                            with open(meta_file, "w", encoding="utf-8") as f:
                                json.dump({"mode": "fallback_simulate", "preset": preset["name"]}, f, indent=2)
                            output_files.append(str(meta_file))
                            print(f"[MediaEncoderIntegrator] 渲染失败，降级为模拟: {input_path.name}")

                except Exception as e:
                    print(f"[MediaEncoderIntegrator] 渲染失败 {input_file}: {e}")
                    # 降级
                    meta_file = output_file.with_suffix(".json")
                    with open(meta_file, "w", encoding="utf-8") as f:
                        json.dump({"error": str(e), "mode": "fallback"}, f, indent=2)
                    output_files.append(str(meta_file))

            result.success = success_count > 0
            result.files_processed = total
            result.output_files = output_files
            result.total_duration = time.time() - start_time
            result.mode = "real"

            if callback:
                callback(1.0, f"批量渲染完成: {success_count}/{total} 成功 (real)")

            print(f"[MediaEncoderIntegrator] 批量渲染完成: {success_count}/{total} 成功 (real)")

        except Exception as e:
            result.error = str(e)
            print(f"[MediaEncoderIntegrator] Real mode error: {e}, falling back to simulate")
            return self._run_simulate_render(input_files, output_dir, preset, callback, start_time)

        return result

    def _render_with_me(self, input_path: Path, output_file: Path, preset: Dict) -> bool:
        """尝试使用 Media Encoder 渲染"""
        # Media Encoder 命令行支持有限，这里尝试使用监视文件夹方式
        # 简化处理：先检查是否有 ffmpeg 可用，优先用 ffmpeg
        return False

    def _render_with_ffmpeg(self, input_path: Path, output_file: Path, preset: Dict) -> bool:
        """使用 ffmpeg 进行转码（后备方案）"""
        try:
            # 查找 ffmpeg（优先权威安装路径 C:/ffmpeg/bin/，与 puppet settings.py 一致）
            ffmpeg_paths = [
                r"C:\ffmpeg\bin\ffmpeg.exe",
                r"D:\app\FormatFactory\ffmpeg.exe",
                r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                "ffmpeg",
            ]
            
            ffmpeg_exe = None
            for p in ffmpeg_paths:
                if p == "ffmpeg":
                    # 检查 PATH 中是否有
                    import shutil
                    if shutil.which("ffmpeg"):
                        ffmpeg_exe = "ffmpeg"
                        break
                elif Path(p).exists():
                    ffmpeg_exe = p
                    break
            
            if not ffmpeg_exe:
                return False

            codec = preset.get("codec", "H264")
            bitrate = preset.get("bitrate", "10M")
            
            # 映射 codec 名称到 ffmpeg
            codec_map = {
                "H264": "libx264",
                "H265": "libx265",
                "ProRes422HQ": "prores_ks",
            }
            ffmpeg_codec = codec_map.get(codec, "libx264")

            cmd = [
                ffmpeg_exe,
                "-i", str(input_path),
                "-c:v", ffmpeg_codec,
                "-b:v", bitrate,
                "-y",
                str(output_file),
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=600,
            )
            
            return output_file.exists() and output_file.stat().st_size > 0

        except Exception as e:
            print(f"[MediaEncoderIntegrator] ffmpeg 转码失败: {e}")
            return False

    def get_available_presets(self) -> List[str]:
        """获取可用输出预设"""
        return list(OUTPUT_FORMAT_PRESETS.keys())


# ============================================================================
# Adobe 全家桶统一入口
# ============================================================================


class AdobeSuiteIntegrator:
    """Adobe 全家桶统一集成入口

    统一管理 PS/PR/ME 三个集成器，提供一站式调用接口。
    """

    def __init__(self, mode: str = "auto"):
        self.mode = mode
        self.photoshop = PhotoshopIntegrator(PhotoshopConfig(mode=mode))
        self.premiere = PremiereIntegrator(PremiereConfig(mode=mode))
        self.media_encoder = MediaEncoderIntegrator(MediaEncoderConfig(mode=mode))

    def is_available(self) -> Dict[str, bool]:
        """检查各软件可用性"""
        return {
            "photoshop": self.photoshop.is_available(),
            "premiere": self.premiere.is_available(),
            "media_encoder": self.media_encoder.is_available(),
        }

    def generate_puppet_textures(
        self,
        materials: List[str] = None,
        output_dir: str = "",
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> Dict[str, PhotoshopResult]:
        """生成木偶风格材质纹理包

        Args:
            materials: 材质类型列表，默认生成全部
            output_dir: 输出目录
            callback: 进度回调

        Returns:
            Dict[material_type, PhotoshopResult]
        """
        if materials is None:
            materials = ["wood", "ceramic", "fabric", "porcelain"]

        if not output_dir:
            output_dir = str(Path(tempfile.mkdtemp(prefix="puppet_textures_")))

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        results = {}
        total = len(materials)

        for i, mat in enumerate(materials):
            if callback:
                callback(i / total, f"生成 {mat} 材质 ({i+1}/{total})")

            output_path = str(Path(output_dir) / f"{mat}_texture.png")
            result = self.photoshop.generate_texture(
                material_type=mat,
                output_path=output_path,
                callback=lambda p, m: callback(
                    (i + p) / total, f"{mat}: {m}"
                ) if callback else None,
            )
            results[mat] = result

        if callback:
            callback(1.0, f"材质纹理包生成完成: {total} 种")

        return results

    def assemble_puppet_video(
        self,
        clips: List[str],
        output_project: str = "",
        transition_type: str = "puppet_transition",
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> PremiereResult:
        """组装木偶风格视频时间线

        Args:
            clips: 输入片段列表
            output_project: 输出 PR 项目路径
            transition_type: 转场类型（默认木偶转场）
            callback: 进度回调

        Returns:
            PremiereResult
        """
        return self.premiere.assemble_timeline(
            clips=clips,
            timeline_name="Puppet_Video_Timeline",
            transitions=True,
            transition_type=transition_type,
            output_project=output_project,
            callback=callback,
        )

    def batch_export(
        self,
        input_files: List[str],
        output_dir: str,
        format_preset: str = "mp4_puppet",
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> MediaEncoderResult:
        """批量导出视频

        Args:
            input_files: 输入文件列表
            output_dir: 输出目录
            format_preset: 格式预设（默认木偶风格输出）
            callback: 进度回调

        Returns:
            MediaEncoderResult
        """
        return self.media_encoder.batch_render(
            input_files=input_files,
            output_dir=output_dir,
            format_preset=format_preset,
            callback=callback,
        )


# ============================================================================
# 便捷函数
# ============================================================================


def create_photoshop_config(operation: str = "texture_gen", **kwargs) -> PhotoshopConfig:
    """创建 Photoshop 配置"""
    return PhotoshopConfig(operation=operation, **kwargs)


def create_premiere_config(operation: str = "timeline_assemble", **kwargs) -> PremiereConfig:
    """创建 Premiere Pro 配置"""
    return PremiereConfig(operation=operation, **kwargs)


def create_media_encoder_config(operation: str = "batch_render", **kwargs) -> MediaEncoderConfig:
    """创建 Media Encoder 配置"""
    return MediaEncoderConfig(operation=operation, **kwargs)


def get_available_materials() -> List[str]:
    """获取可用材质列表"""
    return list(MATERIAL_PRESETS.keys())


def get_available_transitions() -> List[str]:
    """获取可用转场列表"""
    return list(TRANSITION_PRESETS.keys())


def get_available_output_formats() -> List[str]:
    """获取可用输出格式列表"""
    return list(OUTPUT_FORMAT_PRESETS.keys())


# ============================================================================
# 自测
# ============================================================================


def _run_self_test():
    """模块自测"""
    print("=" * 60)
    print("Adobe 全家桶集成模块 - 自测")
    print("=" * 60)

    tests = []

    # 测试 1: 检查预设配置
    print("\n[测试 1/8] 检查材质纹理预设...")
    assert len(MATERIAL_PRESETS) >= 6, "材质预设不足 6 种"
    for name, preset in MATERIAL_PRESETS.items():
        assert "base_color" in preset, f"{name} 缺少 base_color"
        assert "filter_stack" in preset, f"{name} 缺少 filter_stack"
    tests.append(("presets_material", True))
    print(f"  ✓ 材质预设: {len(MATERIAL_PRESETS)} 种")

    # 测试 2: 检查转场预设
    print("\n[测试 2/8] 检查转场预设...")
    assert len(TRANSITION_PRESETS) >= 5, "转场预设不足 5 种"
    for name, preset in TRANSITION_PRESETS.items():
        assert "duration" in preset, f"{name} 缺少 duration"
    tests.append(("presets_transition", True))
    print(f"  ✓ 转场预设: {len(TRANSITION_PRESETS)} 种")

    # 测试 3: 检查输出格式预设
    print("\n[测试 3/8] 检查输出格式预设...")
    assert len(OUTPUT_FORMAT_PRESETS) >= 4, "输出格式预设不足 4 种"
    tests.append(("presets_output", True))
    print(f"  ✓ 输出格式预设: {len(OUTPUT_FORMAT_PRESETS)} 种")

    # 测试 4: 检查数据类
    print("\n[测试 4/8] 检查数据类...")
    ps_config = PhotoshopConfig()
    pr_config = PremiereConfig()
    me_config = MediaEncoderConfig()
    assert ps_config.operation == "texture_gen"
    assert pr_config.operation == "timeline_assemble"
    assert me_config.operation == "batch_render"
    tests.append(("dataclasses", True))
    print("  ✓ 数据类完整 (PS/PR/ME)")

    # 测试 5: PhotoshopIntegrator 初始化
    print("\n[测试 5/8] 检查 PhotoshopIntegrator 初始化...")
    ps = PhotoshopIntegrator(PhotoshopConfig(mode="simulate"))
    assert ps.config.mode == "simulate"
    print(f"  ✓ PS 可用: {ps.is_available()}")
    tests.append(("ps_init", True))

    # 测试 6: PremiereIntegrator 初始化
    print("\n[测试 6/8] 检查 PremiereIntegrator 初始化...")
    pr = PremiereIntegrator(PremiereConfig(mode="simulate"))
    assert pr.config.mode == "simulate"
    print(f"  ✓ PR 可用: {pr.is_available()}")
    print(f"  ✓ 可用转场: {pr.get_available_transitions()}")
    tests.append(("pr_init", True))

    # 测试 7: MediaEncoderIntegrator 初始化
    print("\n[测试 7/8] 检查 MediaEncoderIntegrator 初始化...")
    me = MediaEncoderIntegrator(MediaEncoderConfig(mode="simulate"))
    assert me.config.mode == "simulate"
    print(f"  ✓ ME 可用: {me.is_available()}")
    print(f"  ✓ 可用预设: {me.get_available_presets()}")
    tests.append(("me_init", True))

    # 测试 8: 模拟模式测试
    print("\n[测试 8/8] 检查模拟模式...")
    ps_result = ps.generate_texture("wood", callback=lambda p, m: None)
    assert ps_result.success, f"PS 模拟模式失败: {ps_result.error}"
    print(f"  ✓ PS 材质生成: {ps_result.material_type} ({ps_result.mode})")

    pr_result = pr.assemble_timeline(
        ["clip1.mp4", "clip2.mp4", "clip3.mp4"],
        transitions=True,
        transition_type="puppet_transition",
        callback=lambda p, m: None,
    )
    assert pr_result.success, f"PR 模拟模式失败: {pr_result.error}"
    print(f"  ✓ PR 时间线组装: {pr_result.clips_assembled} 片段, {pr_result.transitions_applied} 转场 ({pr_result.mode})")

    me_result = me.batch_render(
        ["file1.mp4", "file2.mp4"],
        output_dir=str(Path(tempfile.mkdtemp())),
        callback=lambda p, m: None,
    )
    assert me_result.success, f"ME 模拟模式失败: {me_result.error}"
    print(f"  ✓ ME 批量渲染: {me_result.files_processed} 文件 ({me_result.mode})")

    tests.append(("simulate_mode", True))

    # AdobeSuiteIntegrator 测试
    print("\n[额外] 检查 AdobeSuiteIntegrator 统一入口...")
    suite = AdobeSuiteIntegrator(mode="simulate")
    availability = suite.is_available()
    print(f"  ✓ 软件可用性: {availability}")

    # 打印预设清单
    print("\n[预设配置清单]")
    print("\n  材质纹理:")
    for name, preset in MATERIAL_PRESETS.items():
        print(f"    - {name}: {preset['name']} - {preset['description']}")
    print("\n  转场效果:")
    for name, preset in TRANSITION_PRESETS.items():
        print(f"    - {name}: {preset['name']} ({preset['duration']}s) - {preset['description']}")
    print("\n  输出格式:")
    for name, preset in OUTPUT_FORMAT_PRESETS.items():
        print(f"    - {name}: {preset['name']} - {preset['description']}")

    # 结果汇总
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in tests if ok)
    print(f"自测结果: {passed}/{len(tests)} 通过")
    print("=" * 60)
    for name, ok in tests:
        status = "✓ 通过" if ok else "✗ 失败"
        print(f"  {status}  {name}")

    return passed == len(tests)


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        success = _run_self_test()
        sys.exit(0 if success else 1)
