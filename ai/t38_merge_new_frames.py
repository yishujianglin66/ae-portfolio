"""
t38_merge_new_frames.py - 将新提取的帧合并到训练数据
========================================================
新帧已经按IP分好目录，直接用IP名作为标签追加到 merged_vlm.jsonl。
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

CORPUS_DIR = Path(r"D:\multi_ip_corpus")
MERGED_VLM = Path(r"D:\multi_ip_corpus\merged_vlm.jsonl")
PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

# IP目录名 → 训练用IP标签 (与t32训练一致)
IP_LABEL_MAP = {
    "alya_sometimes_hides_her_feelings_in_russian": "Alya",
    "blue_lock": "Blue Lock",
    "byakuya_mimori": "Byakuya Mimori",
    "hatsune_miku": "Hatsune Miku",
    "jujutsu_kaisen": "Jujutsu Kaisen",
    "kaguya_sama": "Kaguya-sama",
    "mao_god_manga": "Mao God Manga",
    "mao_mao": "MaoMao",
    "solo_leveling": "Solo Leveling",
}


def main():
    print("=" * 60)
    print("  T38: 合并新帧到训练数据")
    print("=" * 60)
    
    # 1. 统计当前训练数据
    existing_paths = set()
    existing_count = 0
    ip_counter = Counter()
    
    if MERGED_VLM.exists():
        with open(MERGED_VLM, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                existing_paths.add(rec.get("frame_path", ""))
                existing_count += 1
                ip_counter[rec.get("ip", "unknown")] += 1
    
    print(f"\n[当前训练数据] {existing_count} 条")
    print("  IP分布:")
    for ip, cnt in ip_counter.most_common(20):
        print(f"    {ip}: {cnt} ({cnt/existing_count*100:.1f}%)")
    
    # 2. 扫描新帧
    print("\n[扫描新帧]")
    new_records = []
    new_by_ip = Counter()
    
    for ip_dir in sorted(CORPUS_DIR.iterdir()):
        if not ip_dir.is_dir():
            continue
        
        ip_name = ip_dir.name
        ip_label = IP_LABEL_MAP.get(ip_name, ip_name)
        frames_dir = ip_dir / "frames"
        
        if not frames_dir.exists():
            continue
        
        for frame_file in sorted(frames_dir.glob("*.jpg")):
            frame_path = str(frame_file)
            
            # 跳过已存在的
            if frame_path in existing_paths:
                continue
            
            # 只添加新提取的帧 (re* 或 mat* 或 dl* 前缀)
            # 也包含之前t33提取的 frame_* 前缀
            record = {
                "frame_path": frame_path,
                "ip": ip_label,
                "scene_type": "general",
                "mood": "neutral",
                "source": "direct_extract",
            }
            new_records.append(record)
            new_by_ip[ip_label] += 1
    
    print(f"  新增 {len(new_records)} 条记录")
    for ip, cnt in new_by_ip.most_common():
        print(f"    {ip}: +{cnt}")
    
    if not new_records:
        print("\n  没有新数据需要合并")
        return
    
    # 3. 追加到 merged_vlm.jsonl
    print(f"\n[追加到 {MERGED_VLM}]")
    with open(MERGED_VLM, "a", encoding="utf-8") as f:
        for rec in new_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    
    total_after = existing_count + len(new_records)
    print(f"  追加完成: {existing_count} → {total_after} 条")
    
    # 4. 更新后统计
    print("\n[更新后IP分布]")
    ip_counter_after = Counter()
    ip_counter_after.update(ip_counter)
    ip_counter_after.update(new_by_ip)
    
    for ip, cnt in ip_counter_after.most_common():
        pct = cnt / total_after * 100
        print(f"    {ip}: {cnt} ({pct:.1f}%)")
    
    print(f"\n  总记录: {total_after}")
    
    # 5. 保存合并报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "before_count": existing_count,
        "new_count": len(new_records),
        "after_count": total_after,
        "new_by_ip": dict(new_by_ip),
        "after_distribution": dict(ip_counter_after.most_common()),
    }
    report_path = PROJECT_ROOT / "reports" / "t38_merge_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  报告: {report_path}")


if __name__ == "__main__":
    main()
