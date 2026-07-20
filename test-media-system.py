#!/usr/bin/env python3
import sys
import os
import json
import subprocess
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_python_script(script_name, function_name, args=None):
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    if not os.path.exists(script_path):
        return {"success": False, "error": f"脚本不存在: {script_path}"}
    
    try:
        request = {
            "func": function_name,
            "params": args if args else {}
        }
        
        result = subprocess.run(
            [sys.executable, script_path, "--json-input", json.dumps(request)],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            return {"success": False, "error": result.stderr}
        
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"success": False, "error": f"JSON解析失败: {result.stdout}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "执行超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_media_fetcher():
    print("=" * 60)
    print("测试 MediaFetcher (跨平台下载器)")
    print("=" * 60)
    
    print("\n1. 获取视频信息...")
    test_url = "https://www.bilibili.com/video/BV1xx411c7mZ"
    result = run_python_script("media-fetcher.py", "get_video_info", {"url": test_url})
    print(f"   结果: {'成功' if result.get('success') else '失败'}")
    if result.get("success") and result.get("info"):
        info = result["info"]
        print(f"   标题: {info.get('title', '')[:30]}...")
        print(f"   时长: {info.get('duration', '')}")
        print(f"   缩略图: {info.get('thumbnail', '')[:50]}...")
    else:
        print(f"   错误: {result.get('error', '')[:100]}")
    
    print("\n2. 搜索YouTube...")
    result = run_python_script("media-fetcher.py", "search_youtube", {"query": "epic music", "max_results": 3})
    print(f"   结果: {'成功' if result.get('success') else '失败'}")
    if result.get("success") and result.get("results"):
        for i, item in enumerate(result["results"], 1):
            print(f"   {i}. {item.get('title', '')[:40]}...")
    else:
        print(f"   错误: {result.get('error', '')[:100]}")

def test_ffmpeg_toolkit():
    print("\n" + "=" * 60)
    print("测试 FFmpegToolkit (音视频处理)")
    print("=" * 60)
    
    print("\n1. 获取媒体信息...")
    test_video = os.path.join(os.path.dirname(__file__), "test-data", "sample.mp4")
    if os.path.exists(test_video):
        result = run_python_script("ffmpeg-toolkit.py", "get_media_info", {"input_file": test_video})
        print(f"   结果: {'成功' if result.get('success') else '失败'}")
        if result.get("success") and result.get("info"):
            info = result["info"]
            print(f"   格式: {info.get('format', '')}")
            print(f"   时长: {info.get('duration', '')}")
            print(f"   视频: {info.get('video_codec', '')}")
            print(f"   音频: {info.get('audio_codec', '')}")
    else:
        print("   跳过: 测试视频不存在")
    
    print("\n2. 测试工具可用性...")
    result = run_python_script("ffmpeg-toolkit.py", "test_ffmpeg", {})
    print(f"   FFmpeg: {'可用' if result.get('ffmpeg_available') else '不可用'}")
    print(f"   FFprobe: {'可用' if result.get('ffprobe_available') else '不可用'}")

def test_douyin_downloader():
    print("\n" + "=" * 60)
    print("测试 DouyinDownloader (抖音下载器)")
    print("=" * 60)
    
    print("\n1. 验证Cookie...")
    result = run_python_script("douyin-downloader.py", "validate_cookie", {})
    print(f"   结果: {'成功' if result.get('success') else '失败'}")
    if result.get("success"):
        print(f"   Cookie状态: {result.get('cookie_status', '')}")
    else:
        print(f"   错误: {result.get('error', '')[:100]}")
    
    print("\n2. 搜索抖音视频...")
    result = run_python_script("douyin-downloader.py", "search_videos", {"keyword": "风景", "count": 3})
    print(f"   结果: {'成功' if result.get('success') else '失败'}")
    if result.get("success") and result.get("videos"):
        for i, video in enumerate(result["videos"], 1):
            print(f"   {i}. {video.get('title', '')[:40]}...")
            print(f"      URL: {video.get('url', '')[:50]}...")
    else:
        print(f"   错误: {result.get('error', '')[:100]}")

def test_audio_analyzer():
    print("\n" + "=" * 60)
    print("测试 AudioAnalyzer (音频分析器)")
    print("=" * 60)
    
    print("\n1. 测试librosa可用性...")
    result = run_python_script("audio-analyzer.py", "test_librosa", {})
    print(f"   librosa: {'可用' if result.get('librosa_available') else '不可用'}")
    print(f"   scipy: {'可用' if result.get('scipy_available') else '不可用'}")
    
    print("\n2. 分析测试音频...")
    test_audio = os.path.join(os.path.dirname(__file__), "test-data", "sample.mp3")
    if os.path.exists(test_audio):
        result = run_python_script("audio-analyzer.py", "analyze_audio", {"audio_path": test_audio})
        print(f"   结果: {'成功' if result.get('success') else '失败'}")
        if result.get("success") and result.get("features"):
            features = result["features"]
            print(f"   BPM: {features.get('bpm', '')}")
            print(f"   情绪: {features.get('mood', '')}")
            print(f"   曲风: {features.get('genre', '')}")
            print(f"   音调: {features.get('key', '')}")
    else:
        print("   跳过: 测试音频不存在")
    
    print("\n3. 生成节拍映射...")
    if os.path.exists(test_audio):
        result = run_python_script("audio-analyzer.py", "generate_beat_map", {"audio_path": test_audio})
        print(f"   结果: {'成功' if result.get('success') else '失败'}")
        if result.get("success") and result.get("beat_map"):
            beats = result["beat_map"]
            print(f"   节拍数: {len(beats)}")
            print(f"   前5个节拍: {beats[:5]}")
    else:
        print("   跳过: 测试音频不存在")

def test_media_search():
    print("\n" + "=" * 60)
    print("测试 MediaSearchEngine (素材搜索引擎)")
    print("=" * 60)
    
    print("\n1. 获取素材库统计...")
    result = run_python_script("media-search.py", "get_library_stats", {})
    print(f"   结果: {'成功' if result.get('success') else '失败'}")
    if result.get("success") and result.get("stats"):
        stats = result["stats"]
        print(f"   视频数量: {stats.get('video_count', 0)}")
        print(f"   音频数量: {stats.get('audio_count', 0)}")
        print(f"   图片数量: {stats.get('image_count', 0)}")
    
    print("\n2. 关键词搜索...")
    result = run_python_script("media-search.py", "search_by_keyword", {"keyword": "风景", "max_results": 3})
    print(f"   结果: {'成功' if result.get('success') else '失败'}")
    if result.get("success") and result.get("results"):
        for i, item in enumerate(result["results"], 1):
            print(f"   {i}. {item.get('filename', '')}")
            print(f"      路径: {item.get('path', '')[:60]}...")
    
    print("\n3. 在线搜索...")
    result = run_python_script("media-search.py", "search_online", {"query": "cinematic", "platform": "youtube", "max_results": 3})
    print(f"   结果: {'成功' if result.get('success') else '失败'}")
    if result.get("success") and result.get("results"):
        for i, item in enumerate(result["results"], 1):
            print(f"   {i}. {item.get('title', '')[:40]}...")

def test_media_manager():
    print("\n" + "=" * 60)
    print("测试 MediaManager (综合管理)")
    print("=" * 60)
    
    print("\n1. 获取库统计...")
    result = run_python_script("media-manager.py", "library_stats", {})
    print(f"   结果: {'成功' if result.get('success') else '失败'}")
    if result.get("success") and result.get("stats"):
        stats = result["stats"]
        print(f"   视频: {stats.get('video_count', 0)}")
        print(f"   音频: {stats.get('audio_count', 0)}")
    
    print("\n2. 查找BGM...")
    result = run_python_script("media-manager.py", "find_bgm", {"video_duration": 30, "mood": "epic", "max_results": 3})
    print(f"   结果: {'成功' if result.get('success') else '失败'}")
    if result.get("success") and result.get("matches"):
        for i, match in enumerate(result["matches"], 1):
            print(f"   {i}. {match.get('filename', '')}")
            print(f"      时长: {match.get('duration', '')}")
            print(f"      BPM: {match.get('bpm', '')}")
            print(f"      情绪: {match.get('mood', '')}")

def test_mcp_tools():
    print("\n" + "=" * 60)
    print("测试 MCP 工具封装")
    print("=" * 60)
    
    print("\n1. 检查MCP工具文件...")
    mcp_file = os.path.join(os.path.dirname(__file__), "mcp-extension", "media-mcp-tools.ts")
    if os.path.exists(mcp_file):
        print("   media-mcp-tools.ts: 存在 ✓")
        with open(mcp_file, 'r', encoding='utf-8') as f:
            content = f.read()
            tool_count = content.count("server.tool(")
            print(f"   注册工具数量: {tool_count}")
    else:
        print("   media-mcp-tools.ts: 不存在 ✗")
    
    print("\n2. 检查Skill文件...")
    skill_file = os.path.join(os.path.dirname(__file__), ".trae", "skills", "media-acquisition", "SKILL.md")
    if os.path.exists(skill_file):
        print("   SKILL.md: 存在 ✓")
    else:
        print("   SKILL.md: 不存在 ✗")

def run_all_tests():
    print("\n" + "=" * 70)
    print("AE Knowledge Vault - 素材管理系统 完整测试套件")
    print("=" * 70)
    
    test_media_fetcher()
    test_ffmpeg_toolkit()
    test_douyin_downloader()
    test_audio_analyzer()
    test_media_search()
    test_media_manager()
    test_mcp_tools()
    
    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="AE素材管理系统测试套件")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    parser.add_argument("--fetcher", action="store_true", help="测试MediaFetcher")
    parser.add_argument("--ffmpeg", action="store_true", help="测试FFmpegToolkit")
    parser.add_argument("--douyin", action="store_true", help="测试DouyinDownloader")
    parser.add_argument("--audio", action="store_true", help="测试AudioAnalyzer")
    parser.add_argument("--search", action="store_true", help="测试MediaSearchEngine")
    parser.add_argument("--manager", action="store_true", help="测试MediaManager")
    parser.add_argument("--mcp", action="store_true", help="测试MCP工具")
    
    args = parser.parse_args()
    
    if args.all or not any([args.fetcher, args.ffmpeg, args.douyin, args.audio, args.search, args.manager, args.mcp]):
        run_all_tests()
        return
    
    if args.fetcher:
        test_media_fetcher()
    if args.ffmpeg:
        test_ffmpeg_toolkit()
    if args.douyin:
        test_douyin_downloader()
    if args.audio:
        test_audio_analyzer()
    if args.search:
        test_media_search()
    if args.manager:
        test_media_manager()
    if args.mcp:
        test_mcp_tools()

if __name__ == "__main__":
    main()