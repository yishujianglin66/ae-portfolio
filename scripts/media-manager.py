import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

CONFIG_PATH = Path(__file__).parent / "config" / "media-config.json"
PROJECT_ROOT = Path(__file__).parent

class MediaManager:
    def __init__(self, config_path: Path = CONFIG_PATH):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self._normalize_paths()
        self._ensure_directories()

    def _normalize_paths(self):
        """将配置中的相对路径解析为绝对路径（基于项目根目录）。"""
        for key, value in self.config.get("directories", {}).items():
            if isinstance(value, str) and (value.startswith("./") or value.startswith(".\\")):
                self.config["directories"][key] = str(PROJECT_ROOT / value[2:])
        for platform_key, platform_cfg in self.config.get("platforms", {}).items():
            if isinstance(platform_cfg, dict) and "cookie_path" in platform_cfg:
                cp = platform_cfg["cookie_path"]
                if isinstance(cp, str) and (cp.startswith("./") or cp.startswith(".\\")):
                    platform_cfg["cookie_path"] = str(PROJECT_ROOT / cp[2:])

    def _ensure_directories(self):
        for dir_path in self.config["directories"].values():
            os.makedirs(dir_path, exist_ok=True)

    def download(self, url: str, type: str = "video", quality: str = "best",
                 output_dir: str | None = None) -> dict:
        from media_fetcher import MediaFetcher
        fetcher = MediaFetcher()
        return fetcher.download_video(url, output_dir=output_dir, 
                                      audio_only=(type == "audio"), quality=quality)

    def download_bgm(self, url: str) -> dict:
        return self.download(url, type="audio")

    def download_batch(self, urls: list[str], type: str = "video") -> list[dict]:
        from media_fetcher import MediaFetcher
        fetcher = MediaFetcher()
        return fetcher.download_batch(urls, audio_only=(type == "audio"))

    def download_douyin(self, url: str, audio_only: bool = False) -> dict:
        from douyin_downloader import DouyinDownloader
        downloader = DouyinDownloader()
        return downloader.download_video(url, audio_only=audio_only)

    def search_douyin(self, keyword: str, max_results: int = 5, audio_only: bool = False) -> list[dict]:
        from douyin_downloader import DouyinDownloader
        downloader = DouyinDownloader()
        return downloader.search_and_download(keyword, max_results=max_results, audio_only=audio_only)

    def download_douyin_bgm(self, url: str) -> dict:
        return self.download_douyin(url, audio_only=True)

    def extract_audio(self, video_path: str, format: str = "mp3", bitrate: str = None) -> dict:
        from ffmpeg_toolkit import FFmpegToolkit
        toolkit = FFmpegToolkit()
        return toolkit.extract_audio(video_path, format=format, bitrate=bitrate)

    def clip_video(self, input_file: str, start_time: float, duration: float,
                   output_file: str | None = None) -> dict:
        from ffmpeg_toolkit import FFmpegToolkit
        toolkit = FFmpegToolkit()
        return toolkit.extract_video_segment(input_file, start_time, duration, output_file)

    def clip_audio(self, input_file: str, start_time: float, duration: float,
                   output_file: str | None = None) -> dict:
        from ffmpeg_toolkit import FFmpegToolkit
        toolkit = FFmpegToolkit()
        return toolkit.extract_audio_segment(input_file, start_time, duration, output_file)

    def get_media_info(self, file_path: str) -> dict:
        from ffmpeg_toolkit import FFmpegToolkit
        toolkit = FFmpegToolkit()
        return toolkit.get_media_info(file_path)

    def analyze_audio(self, audio_path: str) -> dict:
        from audio_analyzer import AudioAnalyzer
        analyzer = AudioAnalyzer()
        return analyzer.analyze_audio(audio_path)

    def generate_beat_map(self, audio_path: str) -> dict:
        from audio_analyzer import AudioAnalyzer
        analyzer = AudioAnalyzer()
        return analyzer.generate_beat_map(audio_path)

    def search_library(self, keyword: str, media_type: str | None = None,
                       max_results: int = 20) -> list[dict]:
        from media_search import MediaSearchEngine
        engine = MediaSearchEngine()
        results = engine.search_by_keyword(keyword, media_type=media_type, max_results=max_results)
        return [r.to_dict() for r in results]

    def search_online(self, query: str, platform: str | None = None,
                      max_results: int = 10) -> list[dict]:
        from media_search import MediaSearchEngine
        engine = MediaSearchEngine()
        return engine.search_online(query, platform=platform, max_results=max_results)

    def find_bgm(self, video_duration: float, mood: str | None = None,
                 bpm: float | None = None, max_results: int = 5) -> list[dict]:
        from media_search import MediaSearchEngine
        engine = MediaSearchEngine()
        results = engine.find_bgm_for_video(video_duration, mood=mood, 
                                            target_bpm=bpm, max_results=max_results)
        return [r.to_dict() for r in results]

    def search_by_mood(self, mood: str, max_results: int = 10) -> list[dict]:
        from media_search import MediaSearchEngine
        engine = MediaSearchEngine()
        results = engine.search_by_mood(mood, max_results=max_results)
        return [r.to_dict() for r in results]

    def search_by_bpm(self, target_bpm: float, tolerance: float = 10,
                      max_results: int = 10) -> list[dict]:
        from media_search import MediaSearchEngine
        engine = MediaSearchEngine()
        results = engine.search_by_bpm(target_bpm, tolerance=tolerance, max_results=max_results)
        return [r.to_dict() for r in results]

    def get_library_stats(self) -> dict:
        from media_search import MediaSearchEngine
        engine = MediaSearchEngine()
        return engine.get_library_stats()

    def validate_douyin_cookie(self) -> dict:
        from douyin_downloader import DouyinDownloader
        downloader = DouyinDownloader()
        return downloader.validate_cookie()

    def auto_manage_cookies(self) -> dict:
        from douyin_downloader import DouyinDownloader
        downloader = DouyinDownloader()
        return downloader.auto_manage_cookies()

    def batch_extract_audio(self, video_directory: str = None) -> list[dict]:
        from douyin_downloader import DouyinDownloader
        downloader = DouyinDownloader()
        return downloader.batch_extract_audio(video_directory)

    def download_trending(self, count: int = 5, platform: str = "douyin",
                         audio_only: bool = False) -> list[dict]:
        if platform == "douyin":
            from douyin_downloader import DouyinDownloader
            downloader = DouyinDownloader()
            return downloader.download_trending_videos(count=count, audio_only=audio_only)
        else:
            return [{"success": False, "error": f"不支持的平台: {platform}"}]
    
    # ============================================================
    #  BGM自动提取→导入AE 完整工作流
    # ============================================================
    
    def extract_bgm_from_url(self, url: str, format: str = "mp3", 
                             clip_start: float = None, clip_duration: float = None) -> dict:
        """
        从视频链接提取BGM的完整流程：
        URL → 下载视频 → 提取音频 → (可选)截取片段 → 返回音频路径
        
        :param url: 视频链接（抖音/B站/YouTube等）
        :param format: 输出音频格式 mp3/wav/m4a
        :param clip_start: 截取起始时间（秒），None则不截取
        :param clip_duration: 截取时长（秒），None则不截取
        :return: 结果字典，包含音频文件路径
        """
        result = {"steps": [], "audio_file": None}
        
        # Step 1: 下载视频
        step = {"step": "download", "description": f"下载视频: {url[:50]}"}
        download_result = self.download(url)
        step["success"] = download_result.get("success", False)
        result["steps"].append(step)
        
        if not download_result.get("success"):
            result["error"] = download_result.get("error", "下载失败")
            return result
        
        # 找到下载的视频文件
        video_file = None
        for f in download_result.get("files", []):
            if any(f["name"].endswith(ext) for ext in [".mp4", ".mov", ".webm", ".mkv"]):
                video_file = f["path"]
                break
        
        if not video_file or not os.path.exists(video_file):
            result["error"] = "下载的视频文件未找到"
            return result
        
        # Step 2: 提取音频
        step = {"step": "extract_audio", "description": "提取音频"}
        audio_result = self.extract_audio(video_file, format=format)
        step["success"] = audio_result.get("success", False)
        result["steps"].append(step)
        
        if not audio_result.get("success"):
            result["error"] = audio_result.get("error", "音频提取失败")
            return result
        
        audio_file = audio_result.get("output_file")
        
        # Step 3: 可选 - 截取片段
        if clip_start is not None and clip_duration is not None:
            step = {"step": "clip_audio", "description": f"截取 {clip_start}s-{clip_start+clip_duration}s"}
            clip_result = self.clip_audio(audio_file, clip_start, clip_duration)
            step["success"] = clip_result.get("success", False)
            result["steps"].append(step)
            if clip_result.get("success"):
                audio_file = clip_result.get("output_file")
        
        result["audio_file"] = audio_file
        result["success"] = True
        return result
    
    def extract_bgm_from_douyin(self, url: str, format: str = "mp3") -> dict:
        """
        从抖音视频提取BGM（使用抖音专用下载器）
        """
        result = {"steps": [], "audio_file": None}
        
        # Step 1: 下载抖音视频（仅音频模式）
        step = {"step": "download_douyin_bgm", "description": "提取抖音BGM"}
        download_result = self.download_douyin_bgm(url)
        step["success"] = download_result.get("success", False)
        result["steps"].append(step)
        
        if download_result.get("success"):
            # 找到音频文件
            for f in download_result.get("files", []):
                if any(f["name"].endswith(ext) for ext in [".mp3", ".m4a", ".wav"]):
                    result["audio_file"] = f["path"]
                    break
            result["success"] = True
        else:
            # 备用方案：先下载视频再提取
            step = {"step": "fallback_download_video", "description": "备用：下载完整视频"}
            download_result = self.download_douyin(url, audio_only=False)
            step["success"] = download_result.get("success", False)
            result["steps"].append(step)
            
            if download_result.get("success"):
                for f in download_result.get("files", []):
                    if f["name"].endswith((".mp4", ".mov")):
                        step = {"step": "extract_audio", "description": "从视频提取音频"}
                        audio_result = self.extract_audio(f["path"], format=format)
                        step["success"] = audio_result.get("success", False)
                        result["steps"].append(step)
                        if audio_result.get("success"):
                            result["audio_file"] = audio_result.get("output_file")
                            result["success"] = True
                            break
        
        if not result.get("success"):
            result["error"] = result.get("error", "抖音BGM提取失败")
        
        return result
    
    # ============================================================
    #  参考视频效果分析 → AE参数生成
    # ============================================================
    
    def analyze_video_effect(self, video_path: str, detail_level: str = "standard") -> dict:
        """
        分析参考视频的剪辑效果，生成AE参数表
        :param video_path: 视频文件路径
        :param detail_level: quick/standard/full
        :return: 包含AE参数和提示词的分析结果
        """
        from vrs.video_effect_analyzer_v1 import VideoEffectAnalyzer
        analyzer = VideoEffectAnalyzer()
        return analyzer.analyze_video(video_path, detail_level=detail_level)
    
    def analyze_video_from_url(self, url: str, detail_level: str = "standard") -> dict:
        """
        从URL下载参考视频并分析效果：URL → 下载 → 分析 → 返回AE参数
        :param url: 视频链接
        :param detail_level: quick/standard/full
        :return: 分析结果+AE参数+提示词
        """
        result = {"steps": [], "analysis": None}
        
        # Step 1: 下载视频
        step = {"step": "download", "description": f"下载参考视频: {url[:50]}"}
        download_result = self.download(url)
        step["success"] = download_result.get("success", False)
        result["steps"].append(step)
        
        if not download_result.get("success"):
            result["error"] = download_result.get("error", "下载失败")
            return result
        
        # 找到视频文件
        video_file = None
        for f in download_result.get("files", []):
            if any(f["name"].endswith(ext) for ext in [".mp4", ".mov", ".webm", ".mkv"]):
                video_file = f["path"]
                break
        
        if not video_file or not os.path.exists(video_file):
            result["error"] = "下载的视频文件未找到"
            return result
        
        # Step 2: 分析视频效果
        step = {"step": "analyze", "description": "分析视频剪辑效果"}
        analysis = self.analyze_video_effect(video_file, detail_level=detail_level)
        step["success"] = analysis.get("success", False)
        result["steps"].append(step)
        
        result["analysis"] = analysis
        result["video_file"] = video_file
        result["success"] = analysis.get("success", False)
        
        return result
    
    def generate_ae_script_from_analysis(self, analysis: dict) -> str:
        """
        从分析结果生成AE ExtendScript脚本
        :param analysis: analyze_video_effect的返回结果
        :return: ExtendScript脚本字符串
        """
        ae_params = analysis.get("ae_parameters", {})
        comp = ae_params.get("composition", {})
        
        script_lines = []
        
        # 创建合成
        script_lines.append('// 自动生成的AE脚本 - 基于视频效果分析')
        script_lines.append('var comp = app.project.items.addComp(')
        script_lines.append('  "Analyzed Comp",')
        script_lines.append(f'  {comp.get("width", 1920)},')
        script_lines.append(f'  {comp.get("height", 1080)},')
        script_lines.append('  1,')
        script_lines.append(f'  {comp.get("duration", 10)},')
        script_lines.append(f'  {comp.get("fps", 30)}')
        script_lines.append(');')
        
        # 添加调整层
        for adj in ae_params.get("adjustment_layers", []):
            script_lines.append(f'// {adj["name"]}')
            script_lines.append(f'var adjLayer = comp.layers.addSolid([0.5,0.5,0.5], "{adj["name"]}", {comp.get("width", 1920)}, {comp.get("height", 1080)}, 1);')
            script_lines.append('adjLayer.adjustmentLayer = true;')
            if adj.get("effect") == "Lumetri Color":
                params = adj.get("params", {})
                script_lines.append('var lumetri = adjLayer.Effects.addProperty("ADBE Lumetri");')
                if "temperature" in params:
                    script_lines.append(f'lumetri.property("Temperature").setValue({params["temperature"]});')
                if "tint" in params:
                    script_lines.append(f'lumetri.property("Tint").setValue({params["tint"]});')
                if "contrast" in params:
                    script_lines.append(f'lumetri.property("Contrast").setValue({params["contrast"]});')
                if "saturation" in params:
                    script_lines.append(f'lumetri.property("Saturation").setValue({params["saturation"]});')
        
        # 添加效果
        for eff in ae_params.get("effects", []):
            script_lines.append(f'// {eff["name"]}')
            params = eff.get("params", {})
            if "expression" in params:
                script_lines.append(f'// Expression: {params["expression"]}')
            elif params.get("property") == "Gaussian Blur":
                script_lines.append(f'var effectLayer = comp.layers.addSolid([0,0,0], "{eff["name"]}", {comp.get("width", 1920)}, {comp.get("height", 1080)}, 1);')
                script_lines.append('var blur = effectLayer.Effects.addProperty("ADBE Gaussian Blur 2");')
                script_lines.append(f'blur.property("Blurriness").setValue({params.get("blurriness", 20)});')
            elif params.get("property") == "Glow":
                script_lines.append(f'var effectLayer = comp.layers.addSolid([0,0,0], "{eff["name"]}", {comp.get("width", 1920)}, {comp.get("height", 1080)}, 1);')
                script_lines.append('var glow = effectLayer.Effects.addProperty("ADBE Glo2");')
                script_lines.append(f'glow.property("Intensity").setValue({params.get("intensity", 80)});')
                script_lines.append(f'glow.property("Radius").setValue({params.get("radius", 30)});')
        
        # 添加表达式
        for expr in ae_params.get("expressions", []):
            script_lines.append(f'// Expression: {expr["name"]}')
            script_lines.append(f'// layer.property("{expr["property"]}").expression = "{expr["expression"]}";')
        
        return "\n".join(script_lines)

    def complete_workflow(self, url: str, clip_start: float = None, clip_duration: float = None,
                         extract_audio_flag: bool = False, analyze_flag: bool = False) -> dict:
        result = {
            "steps": [],
            "final_files": []
        }

        step = {"step": "download", "description": "下载媒体文件"}
        download_result = self.download(url)
        step["result"] = download_result["success"]
        result["steps"].append(step)

        if not download_result["success"]:
            result["error"] = download_result["error"]
            return result

        downloaded_files = download_result["files"]
        if downloaded_files:
            main_file = downloaded_files[0]["path"]
            result["final_files"].append(main_file)

            if clip_start is not None and clip_duration is not None:
                step = {"step": "clip", "description": f"截取片段 {clip_start}-{clip_start+clip_duration}"}
                clip_result = self.clip_video(main_file, clip_start, clip_duration)
                step["result"] = clip_result["success"]
                result["steps"].append(step)

                if clip_result["success"]:
                    main_file = clip_result["output_file"]
                    result["final_files"].append(main_file)

            if extract_audio_flag:
                step = {"step": "extract_audio", "description": "提取音频"}
                audio_result = self.extract_audio(main_file)
                step["result"] = audio_result["success"]
                result["steps"].append(step)

                if audio_result["success"]:
                    result["final_files"].append(audio_result["output_file"])

            if analyze_flag:
                step = {"step": "analyze", "description": "分析音频特征"}
                analyze_result = self.analyze_audio(main_file)
                step["result"] = analyze_result["success"]
                result["steps"].append(step)

                if analyze_result["success"]:
                    result["audio_features"] = analyze_result["features"]

        result["success"] = True
        return result

    def find_and_download_bgm(self, mood: str, duration: float, bpm: float | None = None,
                              source: str = "library") -> dict:
        if source == "library":
            bgm_list = self.find_bgm(duration, mood=mood, bpm=bpm)
            if bgm_list:
                return {
                    "success": True,
                    "source": "library",
                    "results": bgm_list
                }
            else:
                return {"success": False, "error": "本地库中未找到匹配的BGM"}

        elif source == "douyin":
            results = self.search_douyin(mood, max_results=3, audio_only=True)
            if any(r["success"] for r in results):
                return {
                    "success": True,
                    "source": "douyin",
                    "results": results
                }
            else:
                return {"success": False, "error": "抖音搜索未找到匹配的BGM"}

        else:
            return {"success": False, "error": f"不支持的源: {source}"}

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
                manager = MediaManager()

                func_name = request.get("func")
                params = request.get("params", {})

                func_map = {
                    "download": manager.download,
                    "download_bgm": manager.download_bgm,
                    "download_batch": manager.download_batch,
                    "download_douyin": manager.download_douyin,
                    "search_douyin": manager.search_douyin,
                    "download_douyin_bgm": manager.download_douyin_bgm,
                    "extract_audio": manager.extract_audio,
                    "clip_video": manager.clip_video,
                    "clip_audio": manager.clip_audio,
                    "get_media_info": manager.get_media_info,
                    "analyze_audio": manager.analyze_audio,
                    "generate_beat_map": manager.generate_beat_map,
                    "search_library": manager.search_library,
                    "search_online": manager.search_online,
                    "find_bgm": manager.find_bgm,
                    "search_by_mood": manager.search_by_mood,
                    "search_by_bpm": manager.search_by_bpm,
                    "get_library_stats": manager.get_library_stats,
                    "validate_douyin_cookie": manager.validate_douyin_cookie,
                    "auto_manage_cookies": manager.auto_manage_cookies,
                    "batch_extract_audio": manager.batch_extract_audio,
                    "download_trending": manager.download_trending,
                    "complete_workflow": manager.complete_workflow,
                    "find_and_download_bgm": manager.find_and_download_bgm,
                    "extract_bgm_from_url": manager.extract_bgm_from_url,
                    "extract_bgm_from_douyin": manager.extract_bgm_from_douyin,
                    "analyze_video_effect": manager.analyze_video_effect,
                    "analyze_video_from_url": manager.analyze_video_from_url,
                    "generate_ae_script_from_analysis": manager.generate_ae_script_from_analysis
                }

                if func_name in func_map:
                    result = func_map[func_name](**params)
                else:
                    result = {"success": False, "error": f"Unknown function: {func_name}"}

                print(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return

    manager = MediaManager()

    print("=== Media Manager 测试 ===")
    print("\n1. 素材库统计:")
    stats = manager.get_library_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    print("\n2. 在线搜索测试:")
    online = manager.search_online("anime epic", platform="youtube", max_results=3)
    for item in online:
        print(f"   - {item['title']} ({item['platform']})")

    print("\n3. 抖音Cookie验证:")
    cookie = manager.validate_douyin_cookie()
    print(f"   状态: {'有效' if cookie['success'] else '无效'}")

if __name__ == "__main__":
    main()