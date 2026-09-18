import asyncio
import importlib
import sys

mf = importlib.import_module("media-fetcher")
MediaFetcher = mf.MediaFetcher

fetcher = MediaFetcher()

print("=" * 60)
print("  木偶风格视频素材下载")
print("=" * 60)
print()

search_keywords = ["提线木偶", "木偶人", "puppet"]
output_dir = "D:/AE-Work/style_copy/puppet_style"

print(f"  搜索关键词: {', '.join(search_keywords)}")
print(f"  输出目录: {output_dir}")
print()

test_urls = [
    "https://www.douyin.com/video/7495382676123",
]

for i, url in enumerate(test_urls):
    print(f"  [{i+1}/{len(test_urls)}] 下载: {url}")
    result = fetcher.download_video(url, output_dir=output_dir)
    
    if result["success"]:
        for f in result["files"]:
            print(f"    ✓ {f['name']} ({f['size']/1024/1024:.2f} MB)")
    else:
        print(f"    ✗ {result.get('error', '')[:100]}")

print()
print("=" * 60)
print()

print("=" * 60)
print("  风格分析 (提示词模式 - 木偶风格)")
print("=" * 60)
print()

style_copy = importlib.import_module("style_copy.workflow")
StyleCopyWorkflow = style_copy.StyleCopyWorkflow

workflow = StyleCopyWorkflow()

prompt = (
    "提线木偶风格视频，特点："
    "1. 人物动作像被线操控的木偶，有机械感"
    "2. 关节处有明显的停顿和抖动"
    "3. 配色偏复古、戏剧化"
    "4. 背景简洁，突出主体"
    "5. 音乐节奏与动作同步，有提线拉扯的音效"
    "6. 镜头固定或缓慢移动"
)

print(f"  风格提示词: {prompt[:80]}...")
print()

result = workflow.run(prompt)

print(f"  分析状态: {'成功' if result.get('success') else '失败'}")

if "style" in result:
    style = result["style"]
    print()
    print("  风格分析结果:")
    print(f"    - 色彩基调: {style.get('color_temperature', '')}")
    print(f"    - 对比度: {style.get('contrast', '')}")
    print(f"    - 节奏: {style.get('pace', '')}")
    print(f"    - 特效: {', '.join(style.get('effects', []))}")
    print(f"    - 转场: {', '.join(style.get('transitions', []))}")

if "tool_sequence" in result:
    print()
    print("  工具调用序列:")
    for i, tool in enumerate(result["tool_sequence"], 1):
        print(f"    {i}. {tool['name']} - {tool.get('description', '')}")

print()
print("=" * 60)
