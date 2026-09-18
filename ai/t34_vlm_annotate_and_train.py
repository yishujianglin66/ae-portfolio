r"""
t34_vlm_annotate_and_train.py — VLM标注 + 均衡采样LoRA训练
=============================================================
完整管线:
1. 修复mao_mao帧提取
2. VLM识别pending目录IP
3. 合并所有数据源 (AoT VLM + 多IP新帧)
4. 均衡采样LoRA重训 (dry-run模式)

数据源:
- AoT VLM标注: 65,714帧 (D:\aot_corpus\vlm_full\results.jsonl)
- 多IP新帧: ~1,600帧 (D:\multi_ip_corpus\)
- 伪标签: 50,454帧 (D:\aot_corpus\pseudolabels.json)
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

# ── 路径配置 ─────────────────────────────────────────
PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
CORPUS_DIR = Path(r"D:\multi_ip_corpus")
AOT_VLM = Path(r"D:\aot_corpus\vlm_full\results.jsonl")
AOT_FRAMES = Path(r"D:\aot_corpus\frames")
OUTPUT_DIR = PROJECT_ROOT / "data" / "multi_ip_training"

# ── API配置 ──────────────────────────────────────────
def load_api_key():
    """从.env.doubao加载SiliconFlow API key"""
    env_path = PROJECT_ROOT / ".env.doubao"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("SILICONFLOW_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and not val.startswith("#"):
                    return val
    return ""

def run_cmd(cmd, timeout=300):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return r.returncode, r.stdout.decode('utf-8', errors='replace'), r.stderr.decode('utf-8', errors='replace')
    except Exception as e:
        return -1, "", str(e)

# ══════════════════════════════════════════════════════
#  Step 1: 修复mao_mao帧提取
# ══════════════════════════════════════════════════════
def fix_mao_mao():
    """直接访问猫猫目录提取帧"""
    print("\n=== Step 1: 修复mao_mao ===")
    
    video_dir = Path(r"D:\AE-Work\resources\video")
    mao_output = CORPUS_DIR / "mao_mao" / "frames"
    
    # 找到猫猫目录
    mao_video_dir = None
    for root, dirs, files in os.walk(video_dir):
        # 检查是否有大视频文件
        has_big_video = False
        for f in files:
            fp = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.mp4', '.mkv', '.mov') and os.path.getsize(fp) > 500 * 1024 * 1024:
                has_big_video = True
                break
        if has_big_video and "素材" in root or "猫" in root:
            mao_video_dir = root
            break
    
    if not mao_video_dir:
        # 尝试直接通过大小找
        for root, dirs, files in os.walk(video_dir):
            for f in files:
                fp = os.path.join(root, f)
                if os.path.getsize(fp) > 800 * 1024 * 1024:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in ('.mp4', '.mkv', '.mov'):
                        mao_video_dir = root
                        break
            if mao_video_dir:
                break
    
    if not mao_video_dir:
        print("  ✗ 未找到猫猫视频目录")
        return 0
    
    print(f"  视频目录: {mao_video_dir}")
    
    existing = len(list(mao_output.glob("frame_*.jpg"))) if mao_output.exists() else 0
    start_num = existing + 100
    
    total_new = 0
    for f in sorted(os.listdir(mao_video_dir)):
        fp = os.path.join(mao_video_dir, f)
        ext = os.path.splitext(f)[1].lower()
        if ext not in ('.mp4', '.mkv', '.mov', '.avi'):
            continue
        size_mb = os.path.getsize(fp) / (1024 * 1024)
        if size_mb < 50:
            continue
        
        mao_output.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-i", fp,
            "-vf", "fps=1", "-q:v", "2",
            "-frames:v", "600",
            "-start_number", str(start_num),
            str(mao_output / "frame_%04d.jpg")
        ]
        rc, out, err = run_cmd(cmd, timeout=300)
        new_frames = len(list(mao_output.glob("frame_*.jpg"))) - (total_new + existing)
        total_new = len(list(mao_output.glob("frame_*.jpg"))) - existing
        print(f"  {f[:40]:40s} {size_mb:8.1f} MB → +{new_frames} frames")
        start_num += new_frames + 1
    
    final_count = len(list(mao_output.glob("frame_*.jpg")))
    print(f"  mao_mao 总帧数: {final_count}")
    return final_count

# ══════════════════════════════════════════════════════
#  Step 2: VLM识别pending目录
# ══════════════════════════════════════════════════════
def vlm_identify_frame(frame_path, api_key):
    """用VLM识别单帧的IP"""
    with open(frame_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
    
    payload = {
        "model": "Qwen/Qwen3-VL-8B-Instruct",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": "这是哪个日本动漫IP？请回答IP的标准英文名（如jujutsu_kaisen, demon_slayer, blue_lock, solo_leveling等）。只回答IP名，不要其他内容。"}
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
            return result['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"ERROR: {e}"

def identify_pending(api_key):
    """识别pending目录的IP并重命名"""
    print("\n=== Step 2: VLM识别pending目录 ===")
    
    pending_dirs = [d for d in CORPUS_DIR.iterdir() if d.is_dir() and d.name.startswith("pending")]
    
    if not pending_dirs:
        print("  无pending目录")
        return
    
    for pdir in pending_dirs:
        print(f"\n  处理: {pdir.name}")
        frames = sorted((pdir / "frames").glob("frame_*.jpg"))
        if not frames:
            print("    ✗ 无帧")
            continue
        
        # 采样2帧
        samples = [frames[0], frames[len(frames)//2]]
        ip_votes = []
        
        for sp in samples:
            print(f"    VLM识别: {sp.name}...", end=" ", flush=True)
            ip = vlm_identify_frame(sp, api_key)
            print(f"→ {ip}")
            ip_votes.append(ip)
        
        # 投票决定
        if ip_votes:
            ip_name = Counter(ip_votes).most_common(1)[0][0]
            # 清理IP名
            ip_name = ip_name.lower().replace(" ", "_").replace("-", "_")
            
            # 重命名目录
            new_dir = CORPUS_DIR / ip_name
            if new_dir.exists() and new_dir != pdir:
                # 合并帧
                print(f"    合并到已存在的 {ip_name}")
                for f in (pdir / "frames").glob("*.jpg"):
                    dst = new_dir / "frames" / f.name
                    if not dst.exists():
                        shutil.copy2(f, dst)
                shutil.rmtree(pdir)
            else:
                print(f"    重命名: {pdir.name} → {ip_name}")
                pdir.rename(new_dir)

# ══════════════════════════════════════════════════════
#  Step 3: 合并数据集
# ══════════════════════════════════════════════════════
def merge_datasets():
    """合并所有数据源到统一训练集"""
    print("\n=== Step 3: 合并数据集 ===")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 3a. 加载AoT VLM数据
    print("  加载AoT VLM数据...")
    aot_data = []
    if AOT_VLM.exists():
        with open(AOT_VLM, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    aot_data.append({
                        'frame_path': d['frame_path'],
                        'ip': d.get('vlm_ip', '') or 'attack_on_titan',
                        'scene_type': d.get('scene_type', ''),
                        'mood': d.get('mood', ''),
                        'source': 'vlm_full'
                    })
    print(f"    AoT VLM: {len(aot_data)} 帧")
    
    # 3b. 扫描多IP语料
    print("  扫描多IP语料...")
    multi_ip_data = []
    ip_counts = Counter()
    
    for d in sorted(CORPUS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith(('.', '__')):
            continue
        if d.name in ('extraction_report.json',):
            continue
            
        frames_dir = d / "frames"
        if not frames_dir.exists():
            continue
        
        ip_name = d.name
        frames = sorted(frames_dir.glob("frame_*.jpg"))
        
        for fp in frames:
            multi_ip_data.append({
                'frame_path': str(fp),
                'ip': ip_name,
                'scene_type': '',  # 待scene classifier填充
                'mood': '',
                'source': 'multi_ip'
            })
            ip_counts[ip_name] += 1
    
    print(f"    多IP新帧: {len(multi_ip_data)} 帧, {len(ip_counts)} 个IP")
    for ip, cnt in ip_counts.most_common():
        print(f"      {ip:50s} {cnt:6d}")
    
    # 3c. 加载伪标签数据（作为补充）
    print("  加载伪标签数据...")
    pseudo_data = []
    pseudo_path = Path(r"D:\aot_corpus\pseudolabels.json")
    if pseudo_path.exists():
        pseudo = json.load(open(pseudo_path, 'r', encoding='utf-8'))
        for p in pseudo:
            pseudo_data.append({
                'frame_path': p['frame_path'],
                'ip': p.get('ip', ''),
                'scene_type': '',
                'mood': '',
                'source': 'pseudolabels',
                'confidence': p.get('confidence', 0)
            })
    print(f"    伪标签: {len(pseudo_data)} 帧")
    
    # 3d. 合并并保存
    all_data = aot_data + multi_ip_data + pseudo_data
    
    # 统计IP分布
    all_ip_counts = Counter(d['ip'] for d in all_data if d['ip'])
    print(f"\n  合并总计: {len(all_data)} 帧, {len(all_ip_counts)} 个IP")
    print(f"\n  {'IP':50s} {'帧数':>8s} {'占比':>8s}")
    print("  " + "-" * 70)
    for ip, cnt in all_ip_counts.most_common(20):
        pct = cnt / len(all_data) * 100
        print(f"  {ip:50s} {cnt:8d} {pct:7.1f}%")
    
    # 保存合并数据
    merged_path = OUTPUT_DIR / "merged_training_data.json"
    with open(merged_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"\n  已保存: {merged_path}")
    
    return all_data

# ══════════════════════════════════════════════════════
#  Step 4: 均衡采样 (dry-run)
# ══════════════════════════════════════════════════════
def balanced_sampling_demo(all_data):
    """演示均衡采样效果"""
    print("\n=== Step 4: 均衡采样演示 ===")
    
    MAX_PER_IP = 3000
    
    # 按IP分组
    by_ip = defaultdict(list)
    for d in all_data:
        ip = d.get('ip', '')
        if ip:
            by_ip[ip].append(d)
    
    print(f"  原始IP数: {len(by_ip)}")
    print(f"  MAX_PER_IP: {MAX_PER_IP}")
    
    # 均衡采样
    sampled = []
    sample_counts = Counter()
    
    for ip, items in by_ip.items():
        if len(items) <= MAX_PER_IP:
            sampled.extend(items)
            sample_counts[ip] = len(items)
        else:
            import random
            random.seed(42)
            chosen = random.sample(items, MAX_PER_IP)
            sampled.extend(chosen)
            sample_counts[ip] = MAX_PER_IP
    
    # 统计采样后分布
    print(f"\n  采样后: {len(sampled)} 帧")
    print(f"\n  {'IP':50s} {'原始':>8s} {'采样后':>8s} {'占比':>8s}")
    print("  " + "-" * 78)
    for ip in sorted(sample_counts.keys(), key=lambda x: -sample_counts[x]):
        orig = len(by_ip[ip])
        samp = sample_counts[ip]
        pct = samp / len(sampled) * 100
        print(f"  {ip:50s} {orig:8d} {samp:8d} {pct:7.1f}%")
    
    # 保存采样数据
    sampled_path = OUTPUT_DIR / "balanced_sampled_data.json"
    with open(sampled_path, 'w', encoding='utf-8') as f:
        json.dump(sampled, f, ensure_ascii=False, indent=2)
    print(f"\n  已保存: {sampled_path}")
    
    return sampled

# ══════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════
def main():
    print("█" * 60)
    print("  T34: VLM标注 + 数据合并 + 均衡采样")
    print("█" * 60)
    
    # Step 1: 修复mao_mao
    fix_mao_mao()
    
    # Step 2: VLM识别pending
    api_key = load_api_key()
    if api_key:
        print(f"\n  API Key: {api_key[:8]}...")
        identify_pending(api_key)
    else:
        print("\n  ✗ 无SiliconFlow API Key, 跳过VLM识别")
    
    # Step 3: 合并数据集
    all_data = merge_datasets()
    
    # Step 4: 均衡采样演示
    sampled = balanced_sampling_demo(all_data)
    
    # 最终汇总
    print("\n" + "=" * 60)
    print("  管线完成!")
    print(f"  合并数据: {len(all_data)} 帧")
    print(f"  均衡采样: {len(sampled)} 帧")
    print(f"  输出目录: {OUTPUT_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
