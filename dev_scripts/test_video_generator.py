#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试视频生成器 - 用于木偶风格化自动识别测试

生成多种类型的测试视频:
1. 纯色背景人物视频（使用AI生成人物图像）
2. 动态人物视频（模拟人物姿态变化）
3. 多场景切换视频（测试场景检测）
4. 运动模糊视频（测试跟踪鲁棒性）

输出格式: MP4 (H.264/AAC)
"""

import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).parent


class TestVideoGenerator:
    """测试视频生成器"""
    
    def __init__(self, ffmpeg_path: str = None):
        if ffmpeg_path:
            self.ffmpeg_path = ffmpeg_path
        else:
            self.ffmpeg_path = self._find_ffmpeg()
    
    def _find_ffmpeg(self) -> str:
        """查找系统中的 ffmpeg"""
        candidates = [
            r"D:\app\FormatFactory\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        
        try:
            result = subprocess.run(["where", "ffmpeg"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        return "ffmpeg"
    
    def is_ffmpeg_available(self) -> bool:
        """检查 ffmpeg 是否可用"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except:
            return False
    
    def generate_test_person_video(self, output_path: str, duration: int = 5,
                                   width: int = 1280, height: int = 720,
                                   fps: int = 30, style: str = "simple") -> bool:
        """生成包含人物的测试视频
        
        Args:
            output_path: 输出视频路径
            duration: 视频时长（秒）
            width: 视频宽度
            height: 视频高度
            fps: 帧率
            style: 风格类型 (simple/animated/scene_change/motion_blur)
            
        Returns:
            是否成功
        """
        if not self.is_ffmpeg_available():
            print("  ❌ ffmpeg 不可用")
            return False
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        if style == "simple":
            return self._generate_simple_person_video(output_path, duration, width, height, fps)
        elif style == "animated":
            return self._generate_animated_person_video(output_path, duration, width, height, fps)
        elif style == "scene_change":
            return self._generate_scene_change_video(output_path, duration, width, height, fps)
        elif style == "motion_blur":
            return self._generate_motion_blur_video(output_path, duration, width, height, fps)
        else:
            return self._generate_simple_person_video(output_path, duration, width, height, fps)
    
    def _generate_simple_person_video(self, output_path: str, duration: int,
                                      width: int, height: int, fps: int) -> bool:
        """生成简单的人物视频（纯色背景 + 模拟人物区域）"""
        center_x = width // 2
        center_y = height // 2
        person_width = int(width * 0.3)
        person_height = int(height * 0.7)
        
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=lightblue:d={duration}:s={width}x{height}:r={fps}",
            "-f", "lavfi",
            "-i", f"color=c=salmon:d={duration}:s={person_width}x{person_height}:r={fps}",
            "-filter_complex",
            f"[1:v]format=rgba,colorchannelmixer=aa=0.9[person];"
            f"[0:v][person]overlay=x={center_x - person_width//2}:y={center_y - person_height//2}[out]",
            "-map", "[out]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-t", str(duration),
            output_path,
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            success = os.path.exists(output_path) and os.path.getsize(output_path) > 0
            if success:
                print(f"  ✅ 生成成功: {os.path.getsize(output_path)} bytes")
            else:
                print(f"  ❌ 生成失败: {result.stderr.decode('utf-8', errors='ignore')[:200]}")
            return success
        except Exception as e:
            print(f"  ❌ 生成失败: {e}")
            return False
    
    def _generate_animated_person_video(self, output_path: str, duration: int,
                                        width: int, height: int, fps: int) -> bool:
        """生成带人物动画的视频（模拟人物姿态变化）"""
        center_x = width // 2
        center_y = height // 2
        person_width = int(width * 0.3)
        person_height = int(height * 0.7)
        
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=lightblue:d={duration}:s={width}x{height}:r={fps}",
            "-f", "lavfi",
            "-i", f"color=c=salmon:d={duration}:s={person_width}x{person_height}:r={fps}",
            "-f", "lavfi",
            "-i", f"color=c=gray:d={duration}:s={int(person_width*0.4)}x{int(person_height*0.3)}:r={fps}",
            "-filter_complex",
            f"[1:v]format=rgba,colorchannelmixer=aa=0.9[body];"
            f"[2:v]format=rgba,colorchannelmixer=aa=0.8[head];"
            f"[0:v][body]overlay=x='{center_x - person_width//2} + sin(t*2)*20':y='{center_y - person_height//2}'[tmp1];"
            f"[tmp1][head]overlay=x='{center_x - person_width*0.2}':y='{center_y - person_height*0.85 + cos(t*3)*10}'[out]",
            "-map", "[out]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-t", str(duration),
            output_path,
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            success = os.path.exists(output_path) and os.path.getsize(output_path) > 0
            if success:
                print(f"  ✅ 生成成功: {os.path.getsize(output_path)} bytes")
            else:
                print(f"  ❌ 生成失败: {result.stderr.decode('utf-8', errors='ignore')[:200]}")
            return success
        except Exception as e:
            print(f"  ❌ 生成失败: {e}")
            return False
    
    def _generate_scene_change_video(self, output_path: str, duration: int,
                                     width: int, height: int, fps: int) -> bool:
        """生成带场景切换的视频"""
        center_x = width // 2
        center_y = height // 2
        person_width = int(width * 0.3)
        person_height = int(height * 0.7)
        
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=lightblue:d={duration}:s={width}x{height}:r={fps}",
            "-f", "lavfi",
            "-i", f"color=c=salmon:d={duration}:s={person_width}x{person_height}:r={fps}",
            "-filter_complex",
            f"[0:v]geq='if(lt(t,{duration/2}),255,135)':128:128[bg];"
            f"[1:v]format=rgba,colorchannelmixer=aa=0.9[person];"
            f"[bg][person]overlay=x='{center_x - person_width//2} + (t>{duration/2})*100':y='{center_y - person_height//2}'[out]",
            "-map", "[out]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-t", str(duration),
            output_path,
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            success = os.path.exists(output_path) and os.path.getsize(output_path) > 0
            if success:
                print(f"  ✅ 生成成功: {os.path.getsize(output_path)} bytes")
            else:
                print(f"  ❌ 生成失败: {result.stderr.decode('utf-8', errors='ignore')[:200]}")
            return success
        except Exception as e:
            print(f"  ❌ 生成失败: {e}")
            return False
    
    def _generate_motion_blur_video(self, output_path: str, duration: int,
                                    width: int, height: int, fps: int) -> bool:
        """生成带运动模糊的视频"""
        center_x = width // 2
        center_y = height // 2
        person_width = int(width * 0.3)
        person_height = int(height * 0.7)
        
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=lightblue:d={duration}:s={width}x{height}:r={fps}",
            "-f", "lavfi",
            "-i", f"color=c=salmon:d={duration}:s={person_width}x{person_height}:r={fps}",
            "-filter_complex",
            f"[1:v]format=rgba,colorchannelmixer=aa=0.9,mblur=10[person];"
            f"[0:v][person]overlay=x='{center_x - person_width//2 + sin(t*5)*50}':y='{center_y - person_height//2}'[out]",
            "-map", "[out]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-t", str(duration),
            output_path,
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            success = os.path.exists(output_path) and os.path.getsize(output_path) > 0
            if success:
                print(f"  ✅ 生成成功: {os.path.getsize(output_path)} bytes")
            else:
                print(f"  ❌ 生成失败: {result.stderr.decode('utf-8', errors='ignore')[:200]}")
            return success
        except Exception as e:
            print(f"  ❌ 生成失败: {e}")
            return False
    
    def generate_test_batch(self, output_dir: str, styles: list = None) -> dict:
        """批量生成测试视频"""
        if styles is None:
            styles = ["simple", "animated", "scene_change", "motion_blur"]
        
        results = {
            "success": False,
            "generated": [],
            "failed": [],
            "ffmpeg_available": self.is_ffmpeg_available(),
        }
        
        if not results["ffmpeg_available"]:
            results["error"] = "ffmpeg 不可用"
            return results
        
        os.makedirs(output_dir, exist_ok=True)
        
        for style in styles:
            output_path = os.path.join(output_dir, f"test_person_{style}.mp4")
            print(f"\n  📹 生成 {style} 测试视频...")
            if self.generate_test_person_video(output_path, duration=5, style=style):
                results["generated"].append({
                    "style": style,
                    "path": output_path,
                    "size": os.path.getsize(output_path),
                })
            else:
                results["failed"].append(style)
        
        results["success"] = len(results["failed"]) == 0
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="测试视频生成器")
    parser.add_argument(
        "--output", "-o",
        default=str(PROJECT_ROOT / "test_media"),
        help="输出目录",
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=5,
        help="视频时长（秒）",
    )
    parser.add_argument(
        "--width", "-w",
        type=int,
        default=1280,
        help="视频宽度",
    )
    parser.add_argument(
        "--height", "-h",
        type=int,
        default=720,
        help="视频高度",
    )
    parser.add_argument(
        "--style", "-s",
        choices=["simple", "animated", "scene_change", "motion_blur", "all"],
        default="simple",
        help="视频风格",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出可用风格",
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎬 测试视频生成器")
    print("=" * 60)
    
    generator = TestVideoGenerator()
    
    if args.list:
        print("\n可用风格:")
        print("  - simple: 简单人物视频（纯色背景）")
        print("  - animated: 动画人物视频（模拟姿态变化）")
        print("  - scene_change: 场景切换视频")
        print("  - motion_blur: 运动模糊视频")
        print("  - all: 批量生成所有风格")
        return
    
    print("\n配置:")
    print(f"  输出目录: {args.output}")
    print(f"  时长: {args.duration}秒")
    print(f"  分辨率: {args.width}x{args.height}")
    print(f"  风格: {args.style}")
    print(f"  ffmpeg: {'可用' if generator.is_ffmpeg_available() else '不可用'}")
    
    if args.style == "all":
        print("\n开始批量生成...")
        results = generator.generate_test_batch(args.output)
    else:
        output_path = os.path.join(args.output, f"test_person_{args.style}.mp4")
        print(f"\n生成视频: {output_path}")
        success = generator.generate_test_person_video(
            output_path,
            duration=args.duration,
            width=args.width,
            height=args.height,
            style=args.style,
        )
        results = {
            "success": success,
            "generated": [{"style": args.style, "path": output_path}] if success else [],
            "failed": [] if success else [args.style],
        }
    
    if results["success"]:
        print("\n✅ 所有视频生成成功!")
        for item in results["generated"]:
            print(f"  - {item['style']}: {os.path.basename(item['path'])} ({item['size']} bytes)")
    else:
        print("\n❌ 生成失败")
        if results.get("error"):
            print(f"  错误: {results['error']}")
        if results.get("failed"):
            print(f"  失败: {', '.join(results['failed'])}")
        sys.exit(1)


if __name__ == "__main__":
    main()
