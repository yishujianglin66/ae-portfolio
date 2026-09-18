import importlib
import json
import sys

mf = importlib.import_module("media-fetcher")
MediaFetcher = mf.MediaFetcher

fetcher = MediaFetcher()

print("=== 测试平台状态 ===")
platforms = fetcher.list_platforms()
for name, cfg in platforms.items():
    print(f"  {name}: strategy={cfg['cookie_strategy']}, configured={cfg['cookie_configured']}")

print("\n=== 测试B站视频下载 ===")
result = fetcher.download_video(
    url="https://www.bilibili.com/video/BV1BK411577f/",
    output_dir="D:/AE-Work/test_bilibili",
)

print("下载结果:")
print(f"  成功: {result['success']}")
print(f"  平台: {result['platform']}")
print(f"  错误: {result.get('error', '')[:300]}")
print(f"  文件: {result.get('files', [])}")