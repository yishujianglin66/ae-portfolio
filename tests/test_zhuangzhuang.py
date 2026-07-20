import sys
import os
import importlib

mf = importlib.import_module("media-fetcher")
MediaFetcher = mf.MediaFetcher

fetcher = MediaFetcher()

video_url = "https://v.douyin.com/gA1N4UaxjPk/"
output_dir = "D:/AE-Work/style_copy/zhuangzhuang"

print("=" * 60)
print("  下载壮壮的抖音视频")
print("=" * 60)
print()
print(f"  链接: {video_url}")
print(f"  输出目录: {output_dir}")
print()

result = fetcher.download_video(video_url, output_dir=output_dir)

if result["success"]:
    print("  ✓ 下载成功!")
    print(f"  方式: {result.get('method', 'yt-dlp')}")
    print()
    for f in result["files"]:
        print(f"  文件: {f['name']}")
        print(f"  大小: {f['size']/1024/1024:.2f} MB")
        print(f"  路径: {f['path']}")
        video_path = f["path"]
    print()
    
    print("=" * 60)
    print("  风格分析 (基于视频)")
    print("=" * 60)
    print()
    
    style_copy = importlib.import_module("style_copy.workflow")
    StyleCopyWorkflow = style_copy.StyleCopyWorkflow
    
    workflow = StyleCopyWorkflow()
    result = workflow.run(video_url)
    
    print(f"  状态: {'成功' if result.get('success') else '失败'}")
    
    if result.get("style"):
        style = result["style"]
        print()
        print("  [色彩]")
        print(f"    色调: {style.get('color_temperature', 'N/A')}")
        print(f"    饱和度: {style.get('saturation', 'N/A')}")
        print(f"    对比度: {style.get('contrast', 'N/A')}")
        print()
        print("  [节奏]")
        print(f"    速度: {style.get('pace', 'N/A')}")
        print(f"    剪辑频率: {style.get('cutting_rate', 'N/A')}")
        print()
        print("  [转场]")
        transitions = style.get('transitions', [])
        if transitions:
            for t in transitions[:5]:
                print(f"    - {t}")
        print()
        print("  [特效]")
        effects = style.get('effects', [])
        if effects:
            for e in effects[:5]:
                print(f"    - {e}")
        print()
        print("  [运镜]")
        camera = style.get('camera_movement', [])
        if isinstance(camera, list):
            for c in camera[:3]:
                print(f"    - {c}")
        else:
            print(f"    {camera}")
        print()
        print("  [字幕]")
        subtitles = style.get('subtitles', {})
        if subtitles:
            print(f"    风格: {subtitles.get('style', 'N/A')}")
            print(f"    位置: {subtitles.get('position', 'N/A')}")
        print()
        print("  [音频]")
        audio = style.get('audio', {})
        if audio:
            print(f"    情绪: {audio.get('mood', 'N/A')}")
            print(f"    类型: {audio.get('type', 'N/A')}")
    
    if result.get("tool_sequence"):
        print()
        print("  [工具调用序列]")
        for i, tool in enumerate(result["tool_sequence"], 1):
            print(f"    {i}. {tool['name']}")
            if tool.get('description'):
                print(f"       {tool['description'][:60]}")
    
    if result.get("ffmpeg_cmd"):
        print()
        print("  [FFmpeg 命令]")
        cmd = result["ffmpeg_cmd"]
        if isinstance(cmd, list):
            print(f"    {' '.join(cmd)[:200]}...")
        else:
            print(f"    {cmd[:200]}...")
else:
    print("  ✗ 下载失败")
    print(f"  错误: {result.get('error', '')}")

print()
print("=" * 60)
