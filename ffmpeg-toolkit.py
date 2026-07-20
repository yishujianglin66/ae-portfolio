import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Optional

CONFIG_PATH = Path(__file__).parent / "config" / "media-config.json"

class FFmpegToolkit:
    def __init__(self, config_path: Path = CONFIG_PATH):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.ffmpeg = self.config["tools"]["ffmpeg"]
        self.ffprobe = self.config["tools"]["ffprobe"]
    
    def extract_audio(self, input_file: str, output_file: Optional[str] = None, 
                      format: str = "mp3", bitrate: str = None) -> Dict:
        """
        从视频中提取音频
        :param input_file: 输入视频文件路径
        :param output_file: 输出音频文件路径，默认在同一目录生成同名mp3
        :param format: 输出格式 (mp3, wav, m4a, flac)
        :param bitrate: 比特率，默认使用配置中的 default_bitrate
        """
        if not os.path.exists(input_file):
            return {"success": False, "error": "输入文件不存在"}
        
        if bitrate is None:
            bitrate = self.config["audio"]["default_bitrate"]
        
        if output_file is None:
            base = os.path.splitext(os.path.abspath(input_file))[0]
            output_file = f"{base}.{format}"
        else:
            output_file = os.path.abspath(output_file)
        
        cmd = [
            self.ffmpeg,
            "-i", input_file,
            "-vn",
            "-acodec", self._get_audio_codec(format),
            "-b:a", bitrate,
            "-y",
            output_file
        ]
        
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace"
            )
            
            if process.returncode == 0 and os.path.exists(output_file):
                return {
                    "success": True,
                    "input_file": input_file,
                    "output_file": output_file,
                    "format": format,
                    "bitrate": bitrate,
                    "size": os.path.getsize(output_file)
                }
            else:
                return {"success": False, "error": process.stderr[:300]}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def extract_video_segment(self, input_file: str, start_time: float, 
                              duration: float, output_file: Optional[str] = None,
                              preserve_audio: bool = True) -> Dict:
        """
        截取视频片段
        :param input_file: 输入视频文件路径
        :param start_time: 开始时间（秒）
        :param duration: 截取时长（秒）
        :param output_file: 输出文件路径
        :param preserve_audio: 是否保留音频
        """
        if not os.path.exists(input_file):
            return {"success": False, "error": "输入文件不存在"}
        
        if output_file is None:
            base = os.path.splitext(os.path.abspath(input_file))[0]
            output_file = f"{base}_segment_{start_time:.1f}_{duration:.1f}.mp4"
        else:
            output_file = os.path.abspath(output_file)
        
        cmd = [
            self.ffmpeg,
            "-i", input_file,
            "-ss", f"{start_time:.2f}",
            "-t", f"{duration:.2f}",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-y",
            output_file
        ]
        
        if not preserve_audio:
            cmd.insert(-1, "-an")
        
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace"
            )
            
            if process.returncode == 0 and os.path.exists(output_file):
                return {
                    "success": True,
                    "input_file": input_file,
                    "output_file": output_file,
                    "start_time": start_time,
                    "duration": duration,
                    "size": os.path.getsize(output_file)
                }
            else:
                return {"success": False, "error": process.stderr[:300]}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def extract_audio_segment(self, input_file: str, start_time: float, 
                              duration: float, output_file: Optional[str] = None) -> Dict:
        """
        截取音频片段
        """
        if not os.path.exists(input_file):
            return {"success": False, "error": "输入文件不存在"}
        
        if output_file is None:
            base = os.path.splitext(os.path.abspath(input_file))[0]
            output_file = f"{base}_segment_{start_time:.1f}_{duration:.1f}.mp3"
        else:
            output_file = os.path.abspath(output_file)
        
        cmd = [
            self.ffmpeg,
            "-i", input_file,
            "-ss", f"{start_time:.2f}",
            "-t", f"{duration:.2f}",
            "-vn",
            "-acodec", "libmp3lame",
            "-b:a", self.config["audio"]["default_bitrate"],
            "-y",
            output_file
        ]
        
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace"
            )
            
            if process.returncode == 0 and os.path.exists(output_file):
                return {
                    "success": True,
                    "input_file": input_file,
                    "output_file": output_file,
                    "start_time": start_time,
                    "duration": duration,
                    "size": os.path.getsize(output_file)
                }
            else:
                return {"success": False, "error": process.stderr[:300]}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_media_info(self, input_file: str) -> Dict:
        """
        获取媒体文件信息
        """
        if not os.path.exists(input_file):
            return {"success": False, "error": "文件不存在"}
        
        cmd = [
            self.ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            input_file
        ]
        
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )
            
            if process.returncode == 0:
                info = json.loads(process.stdout)
                return {
                    "success": True,
                    "info": info,
                    "duration": float(info.get("format", {}).get("duration", 0)),
                    "size": int(info.get("format", {}).get("size", 0)),
                    "streams": len(info.get("streams", []))
                }
            else:
                return {"success": False, "error": process.stderr[:200]}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def convert_video_format(self, input_file: str, output_file: str, 
                             target_format: str = "mp4") -> Dict:
        """
        转换视频格式
        """
        if not os.path.exists(input_file):
            return {"success": False, "error": "输入文件不存在"}
        
        cmd = [
            self.ffmpeg,
            "-i", input_file,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-y",
            output_file
        ]
        
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
                errors="replace"
            )
            
            if process.returncode == 0 and os.path.exists(output_file):
                return {
                    "success": True,
                    "input_file": input_file,
                    "output_file": output_file,
                    "size": os.path.getsize(output_file)
                }
            else:
                return {"success": False, "error": process.stderr[:300]}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_audio_codec(self, format: str) -> str:
        """根据格式获取对应的音频编码器"""
        codec_map = {
            "mp3": "libmp3lame",
            "wav": "pcm_s16le",
            "m4a": "aac",
            "flac": "flac",
            "ogg": "libvorbis"
        }
        return codec_map.get(format, "libmp3lame")
    
    def test_ffmpeg(self) -> Dict:
        """测试FFmpeg和FFprobe可用性"""
        ffmpeg_available = False
        ffprobe_available = False
        
        try:
            result = subprocess.run([self.ffmpeg, "--version"], capture_output=True, text=True, timeout=5)
            ffmpeg_available = result.returncode == 0
        except:
            pass
        
        try:
            result = subprocess.run([self.ffprobe, "--version"], capture_output=True, text=True, timeout=5)
            ffprobe_available = result.returncode == 0
        except:
            pass
        
        return {
            "ffmpeg_available": ffmpeg_available,
            "ffprobe_available": ffprobe_available
        }

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            if len(sys.argv) > 2:
                input_data = sys.argv[2]
            else:
                input_data = sys.stdin.read()
            
            if input_data:
                request = json.loads(input_data)
                toolkit = FFmpegToolkit()
                
                func_name = request.get("func")
                params = request.get("params", {})
                
                func_map = {
                    "extract_audio": toolkit.extract_audio,
                    "extract_video_segment": toolkit.extract_video_segment,
                    "extract_audio_segment": toolkit.extract_audio_segment,
                    "get_media_info": toolkit.get_media_info,
                    "convert_video_format": toolkit.convert_video_format,
                    "test_ffmpeg": toolkit.test_ffmpeg
                }
                
                if func_name in func_map:
                    result = func_map[func_name](**params)
                else:
                    result = {"success": False, "error": f"Unknown function: {func_name}"}
                
                print(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return
    
    toolkit = FFmpegToolkit()
    
    test_video = r"D:\AE-Work\视频素材库\demo.mp4"
    
    print("测试媒体信息获取...")
    info = toolkit.get_media_info(test_video)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    
    print("\n测试音频提取...")
    audio_result = toolkit.extract_audio(test_video)
    print(json.dumps(audio_result, ensure_ascii=False, indent=2))
    
    print("\n测试片段截取...")
    seg_result = toolkit.extract_video_segment(test_video, 5, 10)
    print(json.dumps(seg_result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
