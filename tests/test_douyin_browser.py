import importlib
import sys

mf = importlib.import_module("media-fetcher")
MediaFetcher = mf.MediaFetcher

fetcher = MediaFetcher()

print("=== 测试抖音视频下载 (browser策略) ===")
print(f"抖音策略: {fetcher.list_platforms()['douyin']['cookie_strategy']}")

result = fetcher.download_video(
    url="https://www.douyin.com/video/7562348910123",
    output_dir="D:/AE-Work/test_douyin",
)

print("\n下载结果:")
print(f"  成功: {result['success']}")
print(f"  平台: {result['platform']}")
print(f"  错误: {result.get('error', '')[:500]}")
print(f"  文件: {result.get('files', [])}")