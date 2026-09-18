import json
import os

import requests


def get_session_cookies():
    cookie_file = "D:/AE-Work/cookies/douyin_cookies.txt"
    cookies = {}
    with open(cookie_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 6:
                name = parts[5]
                value = parts[6]
                cookies[name] = value
    return cookies

def download_douyin_video(video_url, output_dir="D:/AE-Work/test_douyin"):
    cookies = get_session_cookies()
    print(f"获取到 {len(cookies)} 条cookies")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/",
        "Accept": "application/json",
    }
    
    video_id = video_url.split("/")[-1].split("?")[0]
    print(f"视频ID: {video_id}")
    
    api_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}"
    
    print(f"请求API: {api_url}")
    resp = requests.get(api_url, headers=headers, cookies=cookies, timeout=15)
    print(f"状态码: {resp.status_code}")
    
    try:
        data = resp.json()
        print(f"响应JSON: {json.dumps(data, ensure_ascii=False)[:500]}")
        
        aweme_detail = data.get("aweme_detail", {})
        if aweme_detail:
            title = aweme_detail.get("desc", "video")
            print(f"\n标题: {title}")
            
            video = aweme_detail.get("video", {})
            play_addr = video.get("play_addr", {})
            url_list = play_addr.get("url_list", [])
            
            if url_list:
                video_download_url = url_list[0]
                print(f"视频地址: {video_download_url[:100]}...")
                
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, f"{video_id}.mp4")
                
                print("\n开始下载...")
                video_resp = requests.get(
                    video_download_url,
                    headers=headers,
                    cookies=cookies,
                    stream=True,
                    timeout=60,
                )
                
                if video_resp.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in video_resp.iter_content(chunk_size=64*1024):
                            f.write(chunk)
                    size = os.path.getsize(output_path)
                    print(f"下载完成: {output_path}")
                    print(f"文件大小: {size/1024/1024:.2f} MB")
                    return True
                else:
                    print(f"下载失败: {video_resp.status_code}")
            else:
                print("未找到视频地址")
        else:
            print("未找到视频详情")
            
    except Exception as e:
        print(f"解析失败: {e}")
        print(f"响应内容: {resp.text[:200]}")
    
    return False

download_douyin_video("https://www.douyin.com/video/7562348910123")
