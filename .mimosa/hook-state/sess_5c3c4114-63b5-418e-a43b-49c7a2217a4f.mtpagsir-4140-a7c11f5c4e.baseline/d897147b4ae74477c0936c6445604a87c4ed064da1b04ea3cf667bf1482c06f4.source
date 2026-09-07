"""Convert merged training data to JSONL format for t32 training."""
import json
from pathlib import Path
from collections import Counter

MERGED_DATA = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\multi_ip_training\merged_training_data.json")
OUTPUT_JSONL = Path(r"D:\multi_ip_corpus\merged_vlm.jsonl")

def main():
    print("=== 转换合并数据为JSONL格式 ===")
    
    data = json.loads(MERGED_DATA.read_text(encoding="utf-8"))
    print(f"  加载: {len(data)} 条记录")
    
    # 验证帧文件存在性
    valid = 0
    missing = 0
    ip_counts = Counter()
    
    with open(OUTPUT_JSONL, 'w', encoding='utf-8') as f:
        for d in data:
            fp = d.get('frame_path', '')
            ip = d.get('ip', '')
            if not fp or not ip:
                continue
            if not Path(fp).exists():
                missing += 1
                continue
            
            record = {
                'frame_path': fp,
                'ip': ip,
                'scene_type': d.get('scene_type', ''),
                'mood': d.get('mood', ''),
                'source': d.get('source', 'merged'),
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            valid += 1
            ip_counts[ip] += 1
    
    print(f"  有效: {valid}, 缺失: {missing}")
    print(f"  IP数: {len(ip_counts)}")
    print(f"  输出: {OUTPUT_JSONL}")
    
    # Top 10 IPs
    print(f"\n  {'IP':50s} {'帧数':>8s}")
    print("  " + "-" * 60)
    for ip, cnt in ip_counts.most_common(10):
        print(f"  {ip:50s} {cnt:8d}")

if __name__ == "__main__":
    main()
