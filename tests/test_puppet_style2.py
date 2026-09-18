import importlib
import os
import sys

style_copy = importlib.import_module("style_copy.workflow")
StyleCopyWorkflow = style_copy.StyleCopyWorkflow

workflow = StyleCopyWorkflow()

prompt = """
壮壮的抖音木偶风格视频，特点：
1. 人物动作像被线操控的提线木偶，关节有明显的停顿和机械感
2. 动作节奏缓慢，有拉扯感
3. 整体色调偏暗，戏剧化打光
4. 背景简洁，突出人物主体
5. 有神秘、仪式感的氛围
6. 音乐偏向空灵、神秘风格
7. 镜头以固定机位和缓慢推拉为主
"""

print("=" * 60)
print("  壮壮的木偶风格 - 风格复制分析")
print("=" * 60)
print()
print(f"  风格提示词: {prompt.strip()[:80]}...")
print()

result = workflow.run(prompt)

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
    print("  ┌────────────────────────────────────┐")
    print("  │      木 偶 风 格 分 析 结 果        │")
    print("  └────────────────────────────────────┘")
    print()
    
    print("  【色彩基调】")
    print(f"    色调: {style.get('color_temperature', 'N/A')}")
    print(f"    饱和度: {style.get('saturation', 'N/A')}")
    print(f"    对比度: {style.get('contrast', 'N/A')}")
    primary = style.get('primary_colors', [])
    if primary:
        print(f"    主色: {', '.join(primary[:3])}")
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
    if isinstance(camera, list) and camera:
        for c in camera[:5]:
            print(f"    - {c}")
    elif camera:
        print(f"    {camera}")
    print()
    
    print("  【字幕风格】")
    subtitles = style.get('subtitles', {})
    if subtitles:
        print(f"    样式: {subtitles.get('style', 'N/A')}")
        print(f"    位置: {subtitles.get('position', 'N/A')}")
    print()
    
    print("  【音频特征】")
    audio = style.get('audio', {})
    if audio:
        print(f"    情绪: {audio.get('mood', 'N/A')}")
        print(f"    类型: {audio.get('type', 'N/A')}")

if tool_sequence:
    print()
    print("  ┌────────────────────────────────────┐")
    print("  │        工 具 调 用 序 列            │")
    print("  └────────────────────────────────────┘")
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
    print("  ┌────────────────────────────────────┐")
    print("  │       FFmpeg 滤镜命令              │")
    print("  └────────────────────────────────────┘")
    print()
    if isinstance(ffmpeg_cmd, list):
        cmd_str = " ".join(ffmpeg_cmd)
    else:
        cmd_str = str(ffmpeg_cmd)
    print(f"  {cmd_str[:300]}..." if len(cmd_str) > 300 else f"  {cmd_str}")

print()
print("=" * 60)
print()
print("  💡 提示：")
print("     1. 以上是基于壮壮木偶风格描述的分析结果")
print("     2. 如需基于真实视频分析，请提供视频链接")
print("     3. 系统会自动调用AE/PR/达芬奇等软件执行风格复制")
print("=" * 60)
