import importlib
import os

mf = importlib.import_module("media-fetcher")
MediaFetcher = mf.MediaFetcher

fetcher = MediaFetcher()

url = "https://www.douyin.com/video/7562348910123"
output_dir = "D:/AE-Work/style_copy/zhuangzhuang"

print("测试 _download_douyin_playwright...")
result = fetcher._download_douyin_playwright(url, output_dir)

print(f"成功: {result['success']}")
print(f"平台: {result['platform']}")
print(f"方式: {result.get('method', '')}")
if result.get('error'):
    print(f"错误: {result['error'][:300]}")
for f in result.get('files', []):
    print(f"文件: {f['name']} ({f['size']/1024/1024:.2f} MB)")
