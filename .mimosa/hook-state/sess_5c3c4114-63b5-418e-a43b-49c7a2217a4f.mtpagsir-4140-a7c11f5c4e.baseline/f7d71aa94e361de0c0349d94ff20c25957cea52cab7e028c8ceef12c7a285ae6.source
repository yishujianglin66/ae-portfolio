import sys
import importlib

mf = importlib.import_module("media-fetcher")
MediaFetcher = mf.MediaFetcher

fetcher = MediaFetcher()

print("=== 抖音视频下载测试 ===")
print(f"平台状态: {fetcher.list_platforms()['douyin']}")
print()

result = fetcher.download_video(
    url="https://www.douyin.com/video/7562348910123",
    output_dir="D:/AE-Work/test_douyin",
)

print(f"下载结果:")
print(f"  成功: {result['success']}")
print(f"  平台: {result['platform']}")
print(f"  方式: {result.get('method', 'yt-dlp')}")
err = result.get('error')
if err:
    print(f"  错误: {err[:500]}")
print(f"  文件:")
for f in result.get('files', []):
    print(f"    - {f['name']} ({f['size']/1024/1024:.2f} MB)")
    print(f"      路径: {f['path']}")
