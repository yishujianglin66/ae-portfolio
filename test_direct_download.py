import sys
import importlib

mf = importlib.import_module("media-fetcher")
MediaFetcher = mf.MediaFetcher

fetcher = MediaFetcher()

print("=== 测试直链视频下载 ===")
result = fetcher.download_video(
    url="https://www.w3schools.com/html/mov_bbb.mp4",
    output_dir="D:/AE-Work/test_direct",
)

print(f"下载结果:")
print(f"  成功: {result['success']}")
print(f"  平台: {result['platform']}")
print(f"  错误: {result.get('error', '')}")
print(f"  文件: {result.get('files', [])}")