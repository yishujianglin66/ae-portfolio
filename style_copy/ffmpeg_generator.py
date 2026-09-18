#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_copy/ffmpeg_generator.py
FFmpeg命令生成器 - 根据风格JSON生成滤镜命令

功能:
  - 将风格参数映射为FFmpeg滤镜链
  - 生成调色、变速、转场、特效等命令

复用项目:
  - ffmpeg-toolkit.py 的工具方法
"""

import json
from typing import Dict, List

STYLE_TO_FILTER_MAP = {
    "color_temperature": {
        "warm": "colorbalance=rs=0.2:gs=0.15:bs=-0.1",
        "cool": "colorbalance=rs=-0.15:gs=-0.1:bs=0.2",
        "neutral": ""
    },
    "contrast": {
        "low": "eq=contrast=0.8",
        "medium": "",
        "high": "eq=contrast=1.3"
    },
    # 注：本机 ffmpeg 构建不含原生 glow/bloom 滤镜，以下用可用滤镜做近似映射，
    # 避免生成不可执行的命令（无需依赖外部剪枝）。
    "effects": {
        # 原生 glow 滤镜本机缺失 -> unsharp 局部对比提升近似"高光溢出/辉光"
        "glow": "unsharp=9:9:0.6",
        # 原生 bloom 滤镜本机缺失 -> gblur 柔和模糊近似"光晕扩散"
        "bloom": "gblur=sigma=6",
        "film_grain": "noise=alls=8:allf=t+u",
        "lens_flare": "lenscorrection=cx=0.5:cy=0.5:k1=0.1:k2=-0.05",
        "vintage": "curves=vintage",
        "cinematic": "unsharp=5:5:0.8,vignette",
        "dreamy": "gblur=sigma=0.5,eq=contrast=0.9:saturation=1.2",
        "dramatic": "eq=contrast=1.5:saturation=1.3,curves=contrast+"
    },
    "pace": {
        "slow": "setpts=1.5*PTS",
        "medium": "",
        "fast": "setpts=0.7*PTS",
        "very_fast": "setpts=0.5*PTS"
    },
    "transitions": {
        "hard_cut": "",
        "dissolve": "xfade=transition=dissolve:duration=0.5",
        "fade": "xfade=transition=fade:duration=0.5",
        "slide": "xfade=transition=slideleft:duration=0.3",
        "zoom": "xfade=transition=zoom:duration=0.4",
        "whip_pan": "xfade=transition=whip:duration=0.3"
    }
}


class FFmpegCommandGenerator:
    """FFmpeg命令生成器"""
    
    def __init__(self):
        self.filters = []
    
    def generate_command(self, input_path: str, output_path: str, style: dict) -> list[str]:
        """生成完整的FFmpeg命令"""
        self.filters = []
        
        self._add_color_filters(style)
        self._add_effect_filters(style)
        self._add_pace_filters(style)
        
        cmd = ["ffmpeg", "-i", input_path]
        
        if self.filters:
            filter_complex = ",".join(self.filters)
            cmd.extend(["-filter_complex", filter_complex])
        
        cmd.extend([
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "192k",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            output_path
        ])
        
        return cmd
    
    def _add_color_filters(self, style: dict):
        """添加调色滤镜"""
        temp = style.get("color_temperature", "neutral")
        if temp in STYLE_TO_FILTER_MAP["color_temperature"]:
            filt = STYLE_TO_FILTER_MAP["color_temperature"][temp]
            if filt:
                self.filters.append(filt)
        
        contrast = style.get("contrast", "medium")
        if contrast in STYLE_TO_FILTER_MAP["contrast"]:
            filt = STYLE_TO_FILTER_MAP["contrast"][contrast]
            if filt:
                self.filters.append(filt)
    
    def _add_effect_filters(self, style: dict):
        """添加特效滤镜"""
        effects = style.get("effects", [])
        for effect in effects:
            effect_lower = effect.lower()
            for key, filt in STYLE_TO_FILTER_MAP["effects"].items():
                if key in effect_lower:
                    if filt:
                        self.filters.append(filt)
                    break
    
    def _add_pace_filters(self, style: dict):
        """添加节奏/变速滤镜"""
        pace = style.get("pace", "medium")
        if pace in STYLE_TO_FILTER_MAP["pace"]:
            filt = STYLE_TO_FILTER_MAP["pace"][pace]
            if filt:
                self.filters.append(filt)
    
    def generate_transition_command(self, input_paths: list[str], output_path: str, 
                                    transition_type: str = "dissolve") -> list[str]:
        """生成带转场的合并命令"""
        if len(input_paths) < 2:
            return ["ffmpeg", "-i", input_paths[0], "-y", output_path]
        
        transition = STYLE_TO_FILTER_MAP["transitions"].get(transition_type, "xfade=transition=dissolve:duration=0.5")
        
        inputs = []
        v_streams = []
        a_streams = []
        
        for i, path in enumerate(input_paths):
            inputs.extend(["-i", path])
            v_streams.append(f"[{i}:v]")
            a_streams.append(f"[{i}:a]")
        
        v_chain = v_streams[0]
        a_chain = a_streams[0]
        
        for i in range(1, len(input_paths)):
            v_chain += f"[{i}:v]{transition}"
            a_chain += f"[{i}:a]acrossfade=d=0.5:c1=tri:c2=tri"
        
        filter_complex = f"{v_chain}[v];{a_chain}[a]"
        
        cmd = ["ffmpeg"]
        cmd.extend(inputs)
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-crf", "23",
            "-c:a", "aac",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            output_path
        ])
        
        return cmd


def main():
    import sys
    
    if len(sys.argv) < 3:
        print("用法:")
        print("  py -3.11 ffmpeg_generator.py <输入视频> <输出视频>")
        print("  py -3.11 ffmpeg_generator.py --style <style.json>")
        return
    
    generator = FFmpegCommandGenerator()
    
    if sys.argv[1] == "--style":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            style = json.load(f)
        
        cmd = generator.generate_command("input.mp4", "output.mp4", style)
        print(" ".join(cmd))
    
    else:
        input_path = sys.argv[1]
        output_path = sys.argv[2]
        
        default_style = {
            "color_temperature": "warm",
            "contrast": "high",
            "effects": ["cinematic", "glow"],
            "pace": "medium"
        }
        
        cmd = generator.generate_command(input_path, output_path, default_style)
        print("生成的命令:")
        print(" ".join(cmd))


if __name__ == "__main__":
    main()