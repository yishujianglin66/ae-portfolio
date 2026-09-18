# -*- coding: utf-8 -*-
r"""T29: MaterialIntel结构升级 — 支持细粒度标签+版本化标注来源。

升级内容:
  v1 (当前): {ip, confidence, scene_type, mood, ...}
  v2 (升级): + annotation_version, annotation_source, character_confidence,
             scene_confidence, mood_confidence, composition, vlm_detail

设计原则:
  - 向后兼容: 旧字段不变, 新字段可选(默认值)
  - 版本化: annotation_version标记标签来源版本
  - 渐进迁移: 旧数据不强制重写, 读取时自动补全默认值

产物:
  ai/t29_intel_upgrade.py — 升级工具函数
  reports/t29_upgrade_report.json — 迁移报告
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INTEL_DIR = ROOT / "cache" / "material_intel"
REPORT_DIR = ROOT / "reports"

# 当前版本号
CURRENT_VERSION = "v2_vlm"


def _log(msg: str):
    print(f"[T29] {msg}", flush=True)


def upgrade_intel_entry(entry: dict, vlm_data: dict = None) -> dict:
    """升级单条MaterialIntel到v2结构。
    
    Args:
        entry: 原始MaterialIntel dict
        vlm_data: 可选的VLM标注数据(用于更新标签)
    
    Returns:
        升级后的dict(原地修改+返回)
    """
    # 检查是否已升级
    if entry.get("annotation_version") == CURRENT_VERSION:
        return entry
    
    # 记录旧版本
    old_version = entry.get("annotation_version", "v1")
    
    # === 新增字段 ===
    
    # 1. annotation_version: 标注版本
    entry["annotation_version"] = CURRENT_VERSION
    
    # 2. annotation_source: 标注来源
    if vlm_data:
        entry["annotation_source"] = vlm_data.get("annotation_source", "vlm_consensus")
    else:
        entry["annotation_source"] = entry.get("annotation_source", "teacher_ensemble")
    
    # 3. character_confidence: 角色置信度列表
    if "ip_tags" in entry:
        for tag in entry["ip_tags"]:
            if "characters" in tag and "character_confidence" not in tag:
                # 为每个角色添加默认置信度
                chars = tag["characters"]
                tag["character_confidence"] = [
                    {"name": c, "confidence": tag.get("confidence", 0.5) * 0.8}
                    for c in chars
                ]
    
    # 4. scene_confidence: 场景置信度
    if "content" in entry:
        content = entry["content"]
        if "scene_confidence" not in content:
            content["scene_confidence"] = 0.7  # 默认值
    
    # 5. mood_confidence: 情绪置信度
    if "content" in entry:
        content = entry["content"]
        if "mood_confidence" not in content:
            content["mood_confidence"] = 0.6  # 默认值
    
    # 6. composition: 构图分析
    if "composition" not in entry:
        entry["composition"] = {
            "position": "unknown",
            "color_mood": content.get("color_palette", "neutral") if "content" in entry else "neutral",
            "depth": "medium",
        }
    
    # 7. ip_timeline升级: 添加confidence和annotation字段
    if "ip_timeline" in entry:
        for seg in entry["ip_timeline"]:
            if "annotation_version" not in seg:
                seg["annotation_version"] = CURRENT_VERSION
    
    # 8. VLM详细数据(如果有)
    if vlm_data:
        entry["vlm_detail"] = {
            "ip_top3": vlm_data.get("vlm_detail", {}).get("ip_top3", []),
            "characters": vlm_data.get("characters", []),
            "scene_type": vlm_data.get("scene_type", ""),
            "mood": vlm_data.get("mood", ""),
            "annotators": vlm_data.get("annotators", {}),
        }
        # 用VLM结果更新primary_ip(如果VLM置信度更高)
        if vlm_data.get("vlm_ip") and vlm_data.get("vlm_confidence", 0) > entry.get("ip_tags", [{}])[0].get("confidence", 0):
            entry["primary_ip"] = vlm_data["vlm_ip"]
    
    return entry


def migrate_all_intel_files():
    """迁移所有MaterialIntel文件到v2结构"""
    _log("=" * 60)
    _log("MaterialIntel v2迁移")
    _log("=" * 60)
    
    if not INTEL_DIR.exists():
        _log(f"目录不存在: {INTEL_DIR}")
        return None
    
    files = list(INTEL_DIR.glob("*.json"))
    # 排除test_results等
    files = [f for f in files if f.name != "test_results.json"]
    _log(f"找到 {len(files)} 个MaterialIntel文件")
    
    migrated = 0
    skipped = 0
    errors = 0
    
    for f in files:
        try:
            entry = json.loads(f.read_text(encoding="utf-8"))
            if entry.get("annotation_version") == CURRENT_VERSION:
                skipped += 1
                continue
            
            upgraded = upgrade_intel_entry(entry)
            f.write_text(json.dumps(upgraded, ensure_ascii=False, indent=2), encoding="utf-8")
            migrated += 1
        except Exception as e:
            errors += 1
            _log(f"  错误: {f.name}: {e}")
    
    _log("\n迁移完成:")
    _log(f"  已升级: {migrated}")
    _log(f"  已跳过(已是v2): {skipped}")
    _log(f"  错误: {errors}")
    
    # 报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_version": CURRENT_VERSION,
        "total_files": len(files),
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "t29_upgrade_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"\n报告: {report_path}")
    
    return report


def create_intel_from_scene_analysis(frame_path: str, ip_result: dict,
                                      scene_result: dict, composition: dict) -> dict:
    """从T27场景分析结果创建v2 MaterialIntel条目。
    
    Args:
        frame_path: 帧文件路径
        ip_result: IP分类结果 {ip, confidence}
        scene_result: 场景分析结果 {scene_type, scene_confidence}
        composition: 构图分析结果 {position, color_mood, depth}
    
    Returns:
        v2 MaterialIntel dict
    """
    return {
        "frame_path": frame_path,
        "primary_ip": ip_result.get("ip", ""),
        "ip_confidence": ip_result.get("confidence", 0),
        "ip_tags": [{
            "ip_name": ip_result.get("ip", ""),
            "confidence": ip_result.get("confidence", 0),
            "characters": [],
            "character_confidence": [],
        }],
        "content": {
            "scene_type": scene_result.get("scene_type", "unknown"),
            "scene_confidence": scene_result.get("scene_confidence", 0),
            "mood": scene_result.get("mood", "unknown"),
            "mood_confidence": scene_result.get("mood_confidence", 0),
        },
        "composition": composition,
        "annotation_version": CURRENT_VERSION,
        "annotation_source": "t27_pipeline",
    }


if __name__ == "__main__":
    migrate_all_intel_files()
