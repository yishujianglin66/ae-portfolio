"""
t33b_fix_and_identify.py — 修复提取问题 + VLM识别pending目录
================================================================
1. 重新提取 mao_mao 的大视频帧
2. 用VLM识别 pending_do_you_mean 目录的IP
3. 为所有新帧生成scene/mood标签
"""
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CORPUS_DIR = Path(r"D:\multi_ip_corpus")
VLM_RESULTS = Path(r"D:\aot_corpus\vlm_full\results.jsonl")

def run_cmd(cmd, timeout=300):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return r.returncode, r.stdout.decode('utf-8', errors='replace'), r.stderr.decode('utf-8', errors='replace')
    except Exception as e:
        return -1, "", str(e)

def extract_frames(video_path, output_dir, fps=1, max_frames=600, start_num=100):
    """提取帧，支持起始编号避免覆盖"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"fps={fps}",
        "-q:v", "2",
        "-frames:v", str(max_frames),
        "-start_number", str(start_num),
        str(output_dir / "frame_%04d.jpg")
    ]
    rc, out, err = run_cmd(cmd, timeout=300)
    frames = list(output_dir.glob("frame_*.jpg"))
    return len(frames)

def fix_mao_mao():
    """重新提取猫猫的大视频帧"""
    print("=== 修复 mao_mao ===")
    mao_dir = CORPUS_DIR / "mao_mao" / "frames"
    video_dir = Path(r"D:\AE-Work\resources\video")
    
    # 找到猫猫目录下的视频
    mao_video_dir = None
    for root, dirs, files in os.walk(video_dir):
        if "猫猫" in root:
            mao_video_dir = root
            break
    
    if not mao_video_dir:
        print("  ✗ 未找到猫猫视频目录")
        return
    
    print(f"  目录: {mao_video_dir}")
    
    # 提取所有视频
    start_num = 100  # 避免覆盖已有的8帧
    total = 0
    for f in sorted(os.listdir(mao_video_dir)):
        fp = os.path.join(mao_video_dir, f)
        ext = os.path.splitext(f)[1].lower()
        if ext not in ('.mp4', '.mkv', '.mov', '.avi'):
            continue
        size_mb = os.path.getsize(fp) / (1024*1024)
        if size_mb < 50:
            continue
        
        # 获取时长
        cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", fp]
        rc, out, _ = run_cmd(cmd)
        duration = float(out.strip()) if rc == 0 and out.strip() else 0
        
        print(f"  {f}: {size_mb:.0f}MB, {duration:.0f}s")
        
        n = extract_frames(fp, mao_dir, fps=1, max_frames=600, start_num=start_num)
        start_num += n + 1
        total += n
        print(f"    → 提取 {n} 帧 (起始编号 {start_num-n})")
    
    all_frames = len(list(mao_dir.glob("frame_*.jpg")))
    print(f"  mao_mao 总帧数: {all_frames}")

def identify_pending_vlm():
    """用VLM识别pending目录的IP - 采样几帧发送VLM"""
    print("\n=== 识别 pending 目录 ===")
    
    # 找到pending目录
    pending_dir = None
    for d in CORPUS_DIR.iterdir():
        if d.is_dir() and d.name.startswith("pending"):
            pending_dir = d
            break
    
    if not pending_dir:
        print("  无pending目录")
        return
    
    print(f"  目录: {pending_dir.name}")
    frames_dir = pending_dir / "frames"
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    
    if not frames:
        print("  ✗ 无帧文件")
        return
    
    # 采样3帧用VLM识别
    sample_indices = [0, len(frames)//2, -1]
    sample_paths = [str(frames[i]) for i in sample_indices if i < len(frames)]
    
    try:
        from ai.t26c_vlm_teacher_label import call_vlm_api
    except:
        # 直接调用SiliconFlow API
        import urllib.request
        api_key = os.environ.get("SILICONFLOW_API_KEY", "")
        if not api_key:
            # 从.env读取
            env_path = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.env")
            if env_path.exists():
                for line in env_path.read_text(encoding='utf-8').splitlines():
                    if line.startswith("SILICONFLOW_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
        
        if not api_key:
            print("  ✗ 无SiliconFlow API Key")
            return
        
        print(f"  对 {len(sample_paths)} 帧进行VLM识别...")
        
        for sp in sample_paths:
            import base64
            with open(sp, 'rb') as f:
                img_b64 = base64.b64encode(f.read()).decode()
            
            payload = {
                "model": "Qwen/Qwen3-VL-8B-Instruct",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                        {"type": "text", "text": "这是哪个日本动漫IP？请回答IP的标准英文名（如jujutsu_kaisen, demon_slayer, blue_lock等）。只回答IP名，不要其他内容。"}
                    ]
                }],
                "max_tokens": 50
            }
            
            req = urllib.request.Request(
                "https://api.siliconflow.cn/v1/chat/completions",
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode('utf-8'))
                    answer = result['choices'][0]['message']['content'].strip()
                    print(f"  帧 {Path(sp).name} → {answer}")
            except Exception as e:
                print(f"  ✗ API错误: {e}")
    
    # 根据目录名猜测
    dir_name = pending_dir.name
    print(f"\n  目录名: {dir_name}")
    print("  建议: 检查目录名中的中文，手动指定IP")

def main():
    print("█" * 60)
    print("  T33b: 修复提取问题 + IP识别")
    print("█" * 60)
    
    fix_mao_mao()
    identify_pending_vlm()
    
    # 最终汇总
    print("\n=== 最终多IP语料汇总 ===")
    total = 0
    for d in sorted(CORPUS_DIR.iterdir()):
        if d.is_dir() and d.name != "__pycache__":
            frames_dir = d / "frames"
            if frames_dir.exists():
                n = len(list(frames_dir.glob("frame_*.jpg")))
                total += n
                print(f"  {d.name:55s} {n:6d} frames")
    print(f"  {'总计':55s} {total:6d} frames")

if __name__ == "__main__":
    main()
