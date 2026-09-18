# -*- coding: utf-8 -*-
r"""T30: 原型库VLM统计升级 — 将65714帧VLM标注统计注入IP原型库。

升级内容:
  1. 每个IP注入VLM帧频、场景分布、情绪分布、Top角色
  2. 构建"素材→场景→情绪"共现矩阵 (IP × Scene × Mood)
  3. 生成 ip_prototypes_v2.json (向后兼容v1)

产物:
  data/ip_prototypes_v2.json — 升级版原型库
  reports/t30_prototype_upgrade.json — 升级报告
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

VLM_FULL = Path(r"D:\aot_corpus\vlm_full\results.jsonl")
PROTO_V1 = ROOT / "data" / "ip_prototypes_100.json"
PROTO_V2 = ROOT / "data" / "ip_prototypes_v2.json"
REPORT = ROOT / "reports" / "t30_prototype_upgrade.json"


def _log(msg):
    print(f"[T30] {msg}", flush=True)


def load_vlm_stats():
    """从VLM标注结果统计每个IP的帧频/场景/情绪/角色"""
    _log("加载VLM标注数据...")
    ip_frames = Counter()          # IP → 帧数
    ip_scenes = defaultdict(Counter)  # IP → {scene: count}
    ip_moods = defaultdict(Counter)   # IP → {mood: count}
    ip_chars = defaultdict(Counter)   # IP → {character: count}
    ip_scene_mood = defaultdict(Counter)  # IP → {(scene,mood): count}
    total = 0

    with open(VLM_FULL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            total += 1

            ip = r.get("vlm_ip", "").strip()
            scene = r.get("scene_type", "").strip().lower()
            mood = r.get("mood", "").strip().lower()
            detail = r.get("vlm_detail") or {}
            characters = detail.get("characters") or []

            if not ip or ip in ("", "其他", "unknown"):
                continue

            ip_frames[ip] += 1
            if scene:
                ip_scenes[ip][scene] += 1
            if mood:
                ip_moods[ip][mood] += 1
            for c in characters:
                if c and c.strip():
                    ip_chars[ip][c.strip()] += 1
            if scene and mood:
                ip_scene_mood[ip][(scene, mood)] += 1

    _log(f"  总帧数: {total}")
    _log(f"  有效IP: {len(ip_frames)}种")
    _log(f"  Top5 IP: {ip_frames.most_common(5)}")

    return ip_frames, ip_scenes, ip_moods, ip_chars, ip_scene_mood


def normalize_ip_name(vlm_ip):
    """VLM IP名 → 原型库key的模糊匹配"""
    # 直接匹配
    vlm_lower = vlm_ip.strip().lower()
    
    # 常见别名映射 (VLM输出 → 原型库key)
    ALIAS_MAP = {
        "进击的巨人": "进击的巨人",
        "电锯人": "电锯人",
        "鬼灭之刃": "鬼灭之刃",
        "鬼灭": "鬼灭之刃",
        "咒术回战": "咒术回战",
        "间谍过家家": "间谍过家家",
        "间谍家家": "间谍过家家",
        "我的英雄学院": "我的英雄学院",
        "地缚少年花子君": "地缚少年花子君",
        "地缚少年": "地缚少年花子君",
    }
    
    if vlm_ip in ALIAS_MAP:
        return ALIAS_MAP[vlm_ip]
    
    # 子串匹配
    for alias, canonical in ALIAS_MAP.items():
        if alias in vlm_ip or vlm_ip in alias:
            return canonical
    
    return vlm_ip


def upgrade_prototypes():
    """升级原型库"""
    _log("=" * 60)
    _log("T30: 原型库VLM统计升级")
    _log("=" * 60)
    
    t0 = time.time()
    
    # 1. 加载VLM统计
    ip_frames, ip_scenes, ip_moods, ip_chars, ip_scene_mood = load_vlm_stats()
    
    # 2. 加载v1原型库
    _log(f"\n加载原型库: {PROTO_V1}")
    v1 = json.loads(PROTO_V1.read_text(encoding="utf-8"))
    _log(f"  v1 IP数: {len(v1)}")
    
    # 建立 name_cn → key 映射
    cn_to_key = {}
    for key, proto in v1.items():
        cn = proto.get("name_cn", key)
        cn_to_key[cn] = key
        cn_to_key[cn.lower()] = key
    
    # 3. 注入VLM统计到每个IP
    matched = 0
    unmatched_ips = []
    v2 = {}
    
    for key, proto in v1.items():
        cn = proto.get("name_cn", key)
        
        # 尝试在VLM统计中找到匹配
        vlm_key = None
        if cn in ip_frames:
            vlm_key = cn
        elif cn.lower() in ip_frames:
            vlm_key = cn.lower()
        else:
            # 模糊匹配
            for vlm_ip in ip_frames:
                if cn in vlm_ip or vlm_ip in cn:
                    vlm_key = vlm_ip
                    break
        
        # 复制原始数据
        v2[key] = dict(proto)
        
        if vlm_key and ip_frames[vlm_key] > 0:
            matched += 1
            n_frames = ip_frames[vlm_key]
            
            # 注入VLM统计字段
            v2[key]["vlm_frame_count"] = n_frames
            v2[key]["vlm_scene_dist"] = dict(ip_scenes[vlm_key].most_common())
            v2[key]["vlm_mood_dist"] = dict(ip_moods[vlm_key].most_common())
            v2[key]["vlm_top_characters"] = [
                {"name": name, "count": cnt}
                for name, cnt in ip_chars[vlm_key].most_common(10)
            ]
            v2[key]["vlm_scene_mood_top"] = [
                {"scene": s, "mood": m, "count": c}
                for (s, m), c in ip_scene_mood[vlm_key].most_common(5)
            ]
            
            # 推断主导场景和情绪
            if ip_scenes[vlm_key]:
                v2[key]["vlm_dominant_scene"] = ip_scenes[vlm_key].most_common(1)[0][0]
            if ip_moods[vlm_key]:
                v2[key]["vlm_dominant_mood"] = ip_moods[vlm_key].most_common(1)[0][0]
        else:
            # 无VLM数据的IP
            v2[key]["vlm_frame_count"] = 0
            v2[key]["vlm_scene_dist"] = {}
            v2[key]["vlm_mood_dist"] = {}
            v2[key]["vlm_top_characters"] = []
            v2[key]["vlm_scene_mood_top"] = []
            unmatched_ips.append(cn)
    
    _log(f"\n匹配结果: {matched}/{len(v1)} IP有VLM数据")
    if unmatched_ips:
        _log(f"  无VLM数据: {unmatched_ips[:10]}{'...' if len(unmatched_ips) > 10 else ''}")
    
    # 4. 注入VLM中识别到但不在原型库的IP (作为新发现)
    vlm_only = []
    for vlm_ip, count in ip_frames.most_common():
        if count < 10:
            break
        # 检查是否已匹配
        already = False
        for key, proto in v2.items():
            if proto.get("vlm_frame_count", 0) == count and proto.get("name_cn") == vlm_ip:
                already = True
                break
            cn = proto.get("name_cn", "")
            if vlm_ip in cn or cn in vlm_ip:
                already = True
                break
        if not already:
            vlm_only.append({
                "vlm_ip": vlm_ip,
                "frame_count": count,
                "top_scene": ip_scenes[vlm_ip].most_common(1)[0][0] if ip_scenes[vlm_ip] else "",
                "top_mood": ip_moods[vlm_ip].most_common(1)[0][0] if ip_moods[vlm_ip] else "",
            })
    
    _log(f"  VLM新发现IP(>=10帧): {len(vlm_only)}个")
    
    # 5. 构建全局共现矩阵
    _log("\n构建场景-情绪共现矩阵...")
    global_scene_mood = Counter()
    for ip_sm in ip_scene_mood.values():
        global_scene_mood.update(ip_sm)
    
    scene_mood_matrix = []
    for (scene, mood), count in global_scene_mood.most_common(20):
        scene_mood_matrix.append({
            "scene": scene, "mood": mood, "count": count
        })
    
    _log("  Top10 场景-情绪组合:")
    for sm in scene_mood_matrix[:10]:
        _log(f"    {sm['scene']}+{sm['mood']}: {sm['count']}")
    
    # 6. 保存v2原型库
    v2_data = {
        "version": "v2",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "vlm_source": str(VLM_FULL),
        "vlm_total_frames": sum(ip_frames.values()),
        "vlm_matched_ips": matched,
        "vlm_new_ips": len(vlm_only),
        "scene_mood_matrix": scene_mood_matrix,
        "prototypes": v2,
    }
    
    PROTO_V2.parent.mkdir(parents=True, exist_ok=True)
    PROTO_V2.write_text(
        json.dumps(v2_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    _log(f"\nv2原型库保存: {PROTO_V2}")
    
    # 7. 保存报告
    elapsed = time.time() - t0
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "v1_count": len(v1),
        "v2_count": len(v2),
        "matched": matched,
        "unmatched": len(v1) - matched,
        "new_discovered": len(vlm_only),
        "top_scene_mood": scene_mood_matrix[:10],
        "elapsed_s": round(elapsed, 1),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    _log(f"报告保存: {REPORT}")
    _log(f"耗时: {elapsed:.1f}s")
    
    return report


if __name__ == "__main__":
    upgrade_prototypes()
