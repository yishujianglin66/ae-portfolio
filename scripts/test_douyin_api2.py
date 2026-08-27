import requests
import re
import json
import os

video_id = "7651343231908753649"

cookie_file = "D:/AE-Work/cookies/douyin_cookies.txt"
cookies = {}
with open(cookie_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]

print(f"加载了 {len(cookies)} 条cookies")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.douyin.com/",
    "Accept": "application/json, text/plain, */*",
}

# 尝试多个API
apis = [
    f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}",
    f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}",
    f"https://api-hl.amemv.com/aweme/v1/aweme/detail/?aweme_id={video_id}",
]

for api_url in apis:
    print(f"\n尝试 API: {api_url[:80]}...")
    try:
        resp = requests.get(api_url, headers=headers, cookies=cookies, timeout=15)
        print(f"  状态码: {resp.status_code}")
        print(f"  内容长度: {len(resp.text)}")
        
        if resp.status_code == 200 and resp.text:
            try:
                data = resp.json()
                print(f"  JSON解析成功")
                
                # 查找视频地址
                def find_video_url(obj, depth=0):
                    if depth > 10:
                        return None
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k in ("play_addr", "playAddr") and isinstance(v, dict):
                                url_list = v.get("url_list", [])
                                if url_list:
                                    return url_list[0]
                            if k == "url_list" and isinstance(v, list) and v:
                                for u in v:
                                    if isinstance(u, str) and ".mp4" in u:
                                        return u
                            res = find_video_url(v, depth + 1)
                            if res:
                                return res
                    elif isinstance(obj, list):
                        for item in obj:
                            res = find_video_url(item, depth + 1)
                            if res:
                                return res
                    return None
                
                video_url = find_video_url(data)
                if video_url:
                    print(f"\n  ✓ 找到视频地址:")
                    print(f"    {video_url}")
                    
                    # 下载
                    output_dir = "D:/AE-Work/style_copy/zhuangzhuang"
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = os.path.join(output_dir, f"douyin_{video_id}.mp4")
                    
                    print(f"\n  开始下载...")
                    video_resp = requests.get(video_url, headers=headers, stream=True, timeout=120)
                    if video_resp.status_code == 200:
                        with open(output_path, "wb") as f:
                            for chunk in video_resp.iter_content(chunk_size=64*1024):
                                f.write(chunk)
                        size = os.path.getsize(output_path)
                        print(f"  ✓ 下载完成: {output_path}")
                        print(f"    大小: {size/1024/1024:.2f} MB")
                    else:
                        print(f"  ✗ 下载失败: {video_resp.status_code}")
                    break
                else:
                    print(f"  未找到视频地址")
                    print(f"  响应keys: {list(data.keys())[:10]}")
            except:
                print(f"  JSON解析失败: {resp.text[:100]}")
    except Exception as e:
        print(f"  错误: {e}")
