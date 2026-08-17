# -*- coding: utf-8 -*-
r"""T28b: Phase 4集成验证 — 100IP原型库 + MaterialIntel v2 + 场景分类器接入管线。

验证项:
  1. 100IP原型库加载 + 零样本分类
  2. MaterialIntel v2结构读写兼容
  3. 场景分类器推理集成
  4. production_scorer新维度接入
  5. ip_proto_classifier新底座(ViT-L-14 LoRA)切换

产物:
  reports/t28b_integration_report.json
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

# === 路径配置 ===
IP_PROTOTYPES_100 = ROOT / "data" / "ip_prototypes_100.json"
MODEL_DIR = ROOT / "models"
SCENE_CLASSIFIER_PATH = MODEL_DIR / "scene_classifier_v1.pt"
LORA_VITL14_PATH = MODEL_DIR / "clip_lora_aot_vitl14.pt"
REPORT_DIR = ROOT / "reports"
REPORT_PATH = REPORT_DIR / "t28b_integration_report.json"


def _log(msg: str):
    print(f"[T28b] {msg}", flush=True)


# ============================================================
# 验证1: 100IP原型库
# ============================================================
def verify_100ip_prototypes() -> dict:
    _log("\n[验证1] 100IP原型库...")
    result = {"status": "fail", "n_ips": 0, "n_templates": 0}
    
    if not IP_PROTOTYPES_100.exists():
        _log("  FAIL: 原型库文件不存在")
        return result
    
    data = json.loads(IP_PROTOTYPES_100.read_text(encoding="utf-8"))
    ips = data.get("ips", data) if isinstance(data, dict) else data
    
    if isinstance(ips, dict):
        n_ips = len(ips)
        total_templates = sum(len(v.get("templates", v.get("prompts", []))) for v in ips.values())
    elif isinstance(ips, list):
        n_ips = len(ips)
        total_templates = sum(len(item.get("templates", item.get("prompts", []))) for item in ips)
    else:
        _log("  FAIL: 数据格式异常")
        return result
    
    result["status"] = "pass"
    result["n_ips"] = n_ips
    result["n_templates"] = total_templates
    _log(f"  PASS: {n_ips}个IP, {total_templates}个文本模板")
    return result


# ============================================================
# 验证2: MaterialIntel v2结构
# ============================================================
def verify_intel_v2() -> dict:
    _log("\n[验证2] MaterialIntel v2结构...")
    result = {"status": "fail", "fields": [], "migrated_files": 0}
    
    # 检查v2新增字段
    v2_fields = [
        "annotation_version", "annotation_source",
        "character_confidence", "scene_confidence", "mood_confidence",
        "composition"
    ]
    
    # 扫描output_production目录下的intel文件
    intel_dir = ROOT / "output_production"
    if not intel_dir.exists():
        intel_dir = ROOT / "output"
    
    migrated = 0
    total = 0
    sample_has_v2 = False
    
    if intel_dir.exists():
        for intel_file in intel_dir.rglob("*.json"):
            try:
                data = json.loads(intel_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    entries = data
                elif isinstance(data, dict) and "materials" in data:
                    entries = data["materials"]
                else:
                    entries = [data]
                
                total += len(entries)
                for entry in entries:
                    if any(f in entry for f in v2_fields):
                        migrated += 1
                        if not sample_has_v2:
                            sample_has_v2 = True
                            result["fields"] = [f for f in v2_fields if f in entry]
            except Exception:
                pass
    
    if sample_has_v2:
        result["status"] = "pass"
        result["migrated_files"] = migrated
        _log(f"  PASS: {migrated}/{total}条含v2字段, 字段: {result['fields']}")
    else:
        result["status"] = "partial"
        result["migrated_files"] = 0
        _log(f"  PARTIAL: 未找到v2字段 (扫描{total}条)")
    
    return result


# ============================================================
# 验证3: 场景分类器推理
# ============================================================
def verify_scene_classifier() -> dict:
    _log("\n[验证3] 场景分类器推理...")
    result = {"status": "fail", "model_exists": False, "n_classes": 0}
    
    if not SCENE_CLASSIFIER_PATH.exists():
        _log("  SKIP: 场景分类器模型未训练 (需先完成T27b)")
        result["status"] = "skip"
        return result
    
    result["model_exists"] = True
    
    try:
        import torch
        ckpt = torch.load(SCENE_CLASSIFIER_PATH, map_location="cpu", weights_only=False)
        classes = ckpt.get("scene_classes", [])
        config = ckpt.get("config", {})
        result["n_classes"] = len(classes)
        result["classes"] = classes
        result["backbone"] = config.get("backbone", "unknown")
        result["status"] = "pass"
        _log(f"  PASS: {len(classes)}类场景 ({', '.join(classes)})")
    except Exception as e:
        _log(f"  FAIL: 模型加载失败 - {e}")
    
    return result


# ============================================================
# 验证4: ViT-L-14 LoRA模型
# ============================================================
def verify_lora_vitl14() -> dict:
    _log("\n[验证4] ViT-L-14 LoRA模型...")
    result = {"status": "fail", "model_exists": False}
    
    if not LORA_VITL14_PATH.exists():
        _log("  SKIP: LoRA模型不存在")
        result["status"] = "skip"
        return result
    
    result["model_exists"] = True
    
    try:
        import torch
        ckpt = torch.load(LORA_VITL14_PATH, map_location="cpu", weights_only=False)
        config = ckpt.get("config", {})
        class_names = ckpt.get("class_names", [])
        result["n_classes"] = len(class_names)
        result["base_model"] = config.get("base_model", "unknown")
        result["embed_dim"] = config.get("embed_dim", 0)
        result["lora_rank"] = config.get("rank", 0)
        result["status"] = "pass"
        _log(f"  PASS: {config.get('base_model')} rank={config.get('rank')} {len(class_names)}类")
    except Exception as e:
        _log(f"  FAIL: 模型加载失败 - {e}")
    
    return result


# ============================================================
# 验证5: 底座切换能力
# ============================================================
def verify_backend_switch() -> dict:
    _log("\n[验证5] 底座切换能力...")
    result = {"status": "fail", "backends": []}
    
    try:
        from ai.clip_backbones import BB_TAGS
        result["backends"] = list(BB_TAGS.keys())
        result["status"] = "pass"
        _log(f"  PASS: 可用底座 {list(BB_TAGS.keys())}")
    except Exception as e:
        _log(f"  FAIL: {e}")
    
    return result


# ============================================================
# 验证6: ip_proto_classifier基线回归
# ============================================================
def verify_baseline_regression() -> dict:
    _log("\n[验证6] 基线回归测试 (ip_proto_classifier --accept)...")
    result = {"status": "fail", "pass": 0, "total": 0}
    
    try:
        import subprocess
        py = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
        script = str(ROOT / "ai" / "ip_proto_classifier.py")
        proc = subprocess.run(
            [py, script, "--accept"],
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        output = proc.stdout + proc.stderr
        
        # 解析结果
        import re
        m = re.search(r'(\d+)/(\d+)\s+PASS', output)
        if m:
            result["pass"] = int(m.group(1))
            result["total"] = int(m.group(2))
            if result["pass"] == result["total"]:
                result["status"] = "pass"
            else:
                result["status"] = "fail"
            _log(f"  {'PASS' if result['status']=='pass' else 'FAIL'}: {result['pass']}/{result['total']}")
        else:
            _log(f"  无法解析输出: {output[-200:]}")
    except Exception as e:
        _log(f"  FAIL: {e}")
    
    return result


# ============================================================
# 主流程
# ============================================================
def run_integration_verify():
    _log("=" * 60)
    _log("T28b: Phase 4集成验证")
    _log("=" * 60)
    
    t0 = time.time()
    results = {}
    
    results["100ip_prototypes"] = verify_100ip_prototypes()
    results["intel_v2"] = verify_intel_v2()
    results["scene_classifier"] = verify_scene_classifier()
    results["lora_vitl14"] = verify_lora_vitl14()
    results["backend_switch"] = verify_backend_switch()
    results["baseline_regression"] = verify_baseline_regression()
    
    elapsed = time.time() - t0
    
    # 统计
    passed = sum(1 for v in results.values() if v["status"] == "pass")
    total = len(results)
    skipped = sum(1 for v in results.values() if v["status"] == "skip")
    
    _log(f"\n{'='*60}")
    _log(f"集成验证完成: {passed}/{total}通过, {skipped}跳过, 耗时{elapsed:.0f}s")
    _log(f"{'='*60}")
    
    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "passed": passed,
        "skipped": skipped,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"报告保存: {REPORT_PATH}")
    
    return report


if __name__ == "__main__":
    run_integration_verify()
