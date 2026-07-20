#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_copy/input_parser.py
输入解析与预处理模块

功能:
  - 解析用户输入（提示词/视频链接）
  - 使用 yt-dlp 下载视频
  - 提取关键帧（用于V4视觉分析）
  - 提取音频（用于BPM分析）
  - 场景切分

复用项目:
  - media-fetcher.py 的 yt-dlp 下载
  - scene_detector.py 的镜头分割
  - ffmpeg-toolkit.py 的视频处理
"""

import os
import re
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple

import importlib

MediaFetcherModule = importlib.import_module("media-fetcher")
MediaFetcher = MediaFetcherModule.MediaFetcher
from scene_detector import SceneDetector

# 从 media-config.json 读取 ffmpeg 路径
_CONFIG_PATH = Path(__file__).parent.parent / "config" / "media-config.json"
with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _MEDIA_CONFIG = json.load(_f)
FFMPEG_BIN = _MEDIA_CONFIG["tools"]["ffmpeg"]
FFPROBE_BIN = _MEDIA_CONFIG["tools"]["ffprobe"]


class InputParser:
    """输入解析器"""

    SUPPORTED_PLATFORMS = {"youtube", "bilibili", "douyin", "kuaishou", "tiktok"}

    def __init__(self, work_dir: Optional[str] = None):
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="style_copy_"))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.fetcher = MediaFetcher()
        self.scene_detector = SceneDetector()
    
    def parse(self, input_str: str) -> Dict:
        """解析用户输入"""
        if self._is_local_file(input_str):
            return self._handle_local_file(input_str)
        
        url = self._extract_url(input_str)
        
        if url:
            return self._handle_url(url)
        else:
            return self._handle_prompt(input_str)
    
    def _is_local_file(self, path: str) -> bool:
        """判断是否为本地视频文件"""
        import os
        if os.path.exists(path):
            ext = os.path.splitext(path)[1].lower()
            return ext in (".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv", ".m4v")
        return False
    
    def _handle_local_file(self, video_path: str) -> Dict:
        """处理本地视频文件"""
        import os
        
        if not os.path.exists(video_path):
            return {
                "success": False,
                "type": "local",
                "error": f"文件不存在: {video_path}"
            }
        
        # 提取关键帧
        frames_dir = self.work_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        
        keyframe_paths = self._extract_keyframes(video_path, frames_dir)
        
        # 提取音频
        audio_path = self._extract_audio(video_path)
        
        # 场景分割
        scene_result = self.scene_detector.detect(video_path)
        
        return {
            "success": True,
            "type": "url",
            "platform": "local",
            "video_path": video_path,
            "audio_path": audio_path,
            "frames_dir": str(frames_dir),
            "keyframe_paths": keyframe_paths,
            "scene_count": scene_result.scene_count if scene_result.success else 0,
            "segments": [s.to_dict() for s in scene_result.segments] if scene_result.success else [],
            "video_info": {},
            "work_dir": str(self.work_dir)
        }
    
    def _extract_url(self, text: str) -> Optional[str]:
        """从文本中提取URL"""
        url_pattern = r"https?://[^\s<>\"']+"
        match = re.search(url_pattern, text)
        if match:
            return match.group(0)
        return None
    
    def _handle_url(self, url: str) -> Dict:
        """处理视频链接"""
        platform = self._detect_platform(url)
        
        # 下载视频
        download_result = self.fetcher.download_video(
            url,
            output_dir=str(self.work_dir),
            quality="best"
        )
        
        if not download_result["success"]:
            return {
                "success": False,
                "type": "url",
                "platform": platform,
                "error": download_result.get("error", "下载失败")
            }
        
        video_path = download_result["files"][0]["path"]
        
        # 提取关键帧
        frames_dir = self.work_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        
        keyframe_paths = self._extract_keyframes(video_path, frames_dir)
        
        # 提取音频
        audio_path = self._extract_audio(video_path)
        
        # 场景分割
        scene_result = self.scene_detector.detect(video_path)
        
        # 获取视频信息
        info = self.fetcher.get_video_info(url)
        
        return {
            "success": True,
            "type": "url",
            "platform": platform,
            "video_path": video_path,
            "audio_path": audio_path,
            "frames_dir": str(frames_dir),
            "keyframe_paths": keyframe_paths,
            "scene_count": scene_result.scene_count if scene_result.success else 0,
            "segments": [s.to_dict() for s in scene_result.segments] if scene_result.success else [],
            "video_info": info.get("info", {}),
            "work_dir": str(self.work_dir)
        }
    
    def _handle_prompt(self, prompt: str) -> Dict:
        """处理文本提示词"""
        return {
            "success": True,
            "type": "prompt",
            "prompt": prompt,
            "work_dir": str(self.work_dir)
        }
    
    def _detect_platform(self, url: str) -> str:
        """检测视频平台"""
        # 直链视频文件
        path = url.split("?")[0].split("#")[0].lower()
        if any(path.endswith(ext) for ext in (".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv", ".m4v")):
            return "direct"
        if re.search(r"(youtube|youtu\.be)", url, re.I):
            return "youtube"
        elif re.search(r"(bilibili|b23\.tv)", url, re.I):
            return "bilibili"
        elif re.search(r"(douyin|tiktok)", url, re.I):
            return "douyin"
        elif re.search(r"(kuaishou|ks)", url, re.I):
            return "kuaishou"
        else:
            return "unknown"
    
    def _extract_keyframes(self, video_path: str, output_dir: Path, fps: int = 2) -> list:
        """提取关键帧（每秒fps帧）"""
        output_pattern = str(output_dir / "frame_%04d.png")

        cmd = [
            FFMPEG_BIN, "-i", video_path,
            "-vf", f"fps={fps}",
            "-q:v", "2",
            output_pattern,
            "-y", "-hide_banner", "-loglevel", "error"
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return sorted([str(p) for p in output_dir.glob("frame_*.png")])
        except subprocess.CalledProcessError:
            return []

    def _extract_audio(self, video_path: str) -> Optional[str]:
        """提取音频"""
        audio_path = str(Path(video_path).with_suffix(".mp3"))

        cmd = [
            FFMPEG_BIN, "-i", video_path,
            "-q:a", "0", "-map", "a",
            audio_path,
            "-y", "-hide_banner", "-loglevel", "error"
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return audio_path if os.path.exists(audio_path) else None
        except subprocess.CalledProcessError:
            return None


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("用法: py -3.11 input_parser.py <url或提示词>")
        return
    
    input_str = " ".join(sys.argv[1:])
    parser = InputParser()
    result = parser.parse(input_str)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()