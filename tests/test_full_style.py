import importlib
import os
import sys

style_copy = importlib.import_module("style_copy.workflow")
StyleCopyWorkflow = style_copy.StyleCopyWorkflow

workflow = StyleCopyWorkflow()

video_path = "D:/AE-Work/style_copy/puppet_style/douyin_7495382676123.mp4"

print("=" * 60)
print("  视频风格智能复制 - 完整流程测试")
print("=" * 60)
print()
print(f"  输入视频: {video_path}")
print(f"  文件大小: {os.path.getsize(video_path)/1024/1024:.2f} MB")
print()

result = workflow.run(video_path)

print(f"  状态: {'✓ 成功' if result.get('success') else '✗ 失败'}")
print(f"  步骤: {result.get('step', 'unknown')}")
if result.get('error'):
    print(f"  错误: {result.get('error')}")
print()

data = result.get("data", {})
style = data.get("style")
tool_sequence = data.get("tool_sequence")
ffmpeg_cmd = data.get("ffmpeg_command")

if style:
    print("  ┌─────────────────────────────────┐")
    print("  │        风 格 分 析 结 果         │")
    print("  └─────────────────────────────────┘")
    print()
    
    print("  【色彩基调】")
    print(f"    色调: {style.get('color_temperature', 'N/A')}")
    print(f"    饱和度: {style.get('saturation', 'N/A')}")
    print(f"    对比度: {style.get('contrast', 'N/A')}")
    print(f"    主色: {', '.join(style.get('primary_colors', []))}")
    print()
    
    print("  【节奏与剪辑】")
    print(f"    整体节奏: {style.get('pace', 'N/A')}")
    print(f"    剪辑频率: {style.get('cutting_rate', 'N/A')}")
    print()
    
    print("  【转场效果】")
    transitions = style.get('transitions', [])
    if transitions:
        for t in transitions[:5]:
            print(f"    - {t}")
    print()
    
    print("  【视觉特效】")
    effects = style.get('effects', [])
    if effects:
        for e in effects[:5]:
            print(f"    - {e}")
    print()
    
    print("  【运镜方式】")
    camera = style.get('camera_movement', [])
    if isinstance(camera, list):
        for c in camera[:5]:
            print(f"    - {c}")
    else:
        print(f"    {camera}")
    print()
    
    print("  【字幕风格】")
    subtitles = style.get('subtitles', {})
    if subtitles:
        print(f"    样式: {subtitles.get('style', 'N/A')}")
        print(f"    位置: {subtitles.get('position', 'N/A')}")
        print(f"    字体: {subtitles.get('font', 'N/A')}")
    print()
    
    print("  【音频特征】")
    audio = style.get('audio', {})
    if audio:
        print(f"    情绪: {audio.get('mood', 'N/A')}")
        print(f"    类型: {audio.get('type', 'N/A')}")
        print(f"    BPM: {audio.get('bpm', 'N/A')}")

if tool_sequence:
    print()
    print("  ┌─────────────────────────────────┐")
    print("  │        工 具 调 用 序 列         │")
    print("  └─────────────────────────────────┘")
    print()
    for i, tool in enumerate(tool_sequence, 1):
        tool_name = tool.get('name') or tool.get('tool') or tool.get('id') or f'工具{i}'
        action = tool.get('action', '')
        desc = tool.get('description', '')
        print(f"  {i:2d}. {tool_name} - {action}")
        if desc:
            print(f"      {desc}")
        if tool.get('params'):
            params = tool['params']
            if isinstance(params, dict):
                for k, v in list(params.items())[:3]:
                    print(f"      · {k}: {v}")
        print()

if ffmpeg_cmd:
    print()
    print("  ┌─────────────────────────────────┐")
    print("  │       FFmpeg 生成命令           │")
    print("  └─────────────────────────────────┘")
    print()
    if isinstance(ffmpeg_cmd, list):
        cmd_str = " ".join(ffmpeg_cmd)
    else:
        cmd_str = str(ffmpeg_cmd)
    print(f"  {cmd_str[:300]}..." if len(cmd_str) > 300 else f"  {cmd_str}")

if data.get("ffmpeg_error"):
    print()
    print("  ⚠ FFmpeg执行提示:")
    print(f"    {data['ffmpeg_error'][:200]}")

print()
print("=" * 60)
