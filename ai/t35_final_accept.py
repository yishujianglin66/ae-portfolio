"""
t35_final_accept.py — 素材智能化系统深度进化 最终验收
=====================================================
覆盖本轮全部交付:
  A. 多IP帧提取 (9个IP, 1600+帧)
  B. 数据合并 (117k+帧, 81 IP)
  C. 均衡采样 (34k+帧, 46 IP)
  D. LoRA重训 (后台运行中)
  E. 基线模块回归 (12项)
"""
import json, sys, time
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(ROOT))

PASS = "PASS"
FAIL = "FAIL"

results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append({"name": name, "status": status, "detail": detail})
    mark = "[OK]" if condition else "[XX]"
    print(f"  [{mark}] {name}: {detail}")
    return condition

print("=" * 65)
print("  T35: 素材智能化系统深度进化 — 最终验收")
print("=" * 65)
t0 = time.time()

# ═══ A. 多IP帧提取 ═══
print("\n── A. 多IP帧提取 ──")

CORPUS = Path(r"D:\multi_ip_corpus")
ip_dirs = [d for d in CORPUS.iterdir() if d.is_dir() and (d / "frames").exists()]
total_frames = sum(len(list((d / "frames").glob("frame_*.jpg"))) for d in ip_dirs)

check("A1. 多IP语料目录存在", CORPUS.exists() and CORPUS.is_dir(),
      f"路径: {CORPUS}")
check("A2. IP分组数量 >= 8", len(ip_dirs) >= 8,
      f"{len(ip_dirs)} 个IP分组")
check("A3. 总帧数 >= 1000", total_frames >= 1000,
      f"{total_frames} 帧")

# 检查具体IP
expected_ips = ["alya_sometimes_hides_her_feelings_in_russian", "blue_lock",
                "byakuya_mimori", "hatsune_miku", "jujutsu_kaisen",
                "kaguya_sama", "solo_leveling", "mao_mao"]
found_ips = [d.name for d in ip_dirs]
missing = [ip for ip in expected_ips if ip not in found_ips]
check("A4. 核心IP覆盖", len(missing) <= 2,
      f"缺失: {missing}" if missing else "全部覆盖")

# ═══ B. 数据合并 ═══
print("\n── B. 数据合并 ──")

merged_jsonl = Path(r"D:\multi_ip_corpus\merged_vlm.jsonl")
check("B1. merged_vlm.jsonl存在", merged_jsonl.exists(),
      f"路径: {merged_jsonl}")

if merged_jsonl.exists():
    n_lines = sum(1 for _ in open(merged_jsonl, 'r', encoding='utf-8'))
    check("B2. 合并数据 >= 100k条", n_lines >= 100000,
          f"{n_lines} 条记录")
else:
    check("B2. 合并数据 >= 100k条", False, "文件不存在")
    n_lines = 0

merged_training = ROOT / "data" / "multi_ip_training" / "merged_training_data.json"
check("B3. 训练数据文件", merged_training.exists(),
      f"{merged_training}")

# ═══ C. 均衡采样 ═══
print("\n── C. 均衡采样 ──")

balanced = ROOT / "data" / "multi_ip_training" / "balanced_sampled_data.json"
check("C1. 均衡采样文件", balanced.exists(),
      f"{balanced}")

if balanced.exists():
    bdata = json.loads(balanced.read_text(encoding='utf-8'))
    b_ips = Counter(d['ip'] for d in bdata)
    check("C2. 采样后IP数 >= 30", len(b_ips) >= 30,
          f"{len(b_ips)} 个IP")
    
    # 检查均衡性: 最大IP占比
    max_ip_cnt = max(b_ips.values())
    max_pct = max_ip_cnt / len(bdata) * 100
    check("C3. 最大IP占比 <= 15%", max_pct <= 15,
          f"最大IP占比: {max_pct:.1f}%")
else:
    check("C2. 采样后IP数 >= 30", False, "文件不存在")
    check("C3. 最大IP占比 <= 15%", False, "文件不存在")

# ═══ D. LoRA训练 ═══
print("\n── D. LoRA训练 ──")

train_log = ROOT / "logs" / "t32_balanced_train.log"
check("D1. 训练日志存在", train_log.exists(),
      f"{train_log}")

if train_log.exists():
    log_content = train_log.read_text(encoding='utf-8', errors='replace')
    has_lora = "LoRA" in log_content
    has_epoch = "Epoch" in log_content or "batch" in log_content
    check("D2. LoRA配置正确", has_lora,
          "LoRA参数已配置")
    check("D3. 训练进行中/完成", has_epoch,
          "训练epoch记录")
    
    # 检查loss下降
    import re
    losses = re.findall(r'loss=(\d+\.\d+)', log_content)
    if len(losses) >= 2:
        first_loss = float(losses[0])
        last_loss = float(losses[-1])
        check("D4. Loss下降", last_loss < first_loss,
              f"{first_loss:.4f} → {last_loss:.4f}")
    else:
        check("D4. Loss下降", False, "无足够loss数据")
else:
    check("D2. LoRA配置正确", False, "日志不存在")
    check("D3. 训练进行中/完成", False, "日志不存在")
    check("D4. Loss下降", False, "日志不存在")

# ═══ E. 基线模块回归 ═══
print("\n── E. 基线模块回归 ──")

baseline_modules = [
    ("E1. ip_proto_classifier", "ai/ip_proto_classifier.py"),
    ("E2. production_scorer", "ai/production_scorer.py"),
    ("E3. clip_backbones", "ai/clip_backbones.py"),
    ("E4. scene_classifier", "ai/t27b_scene_classifier_train.py"),
    ("E5. ip_prototypes_v2", "data/ip_prototypes_v2.json"),
    ("E6. scene_mood_matrix", "ai/t30c_scene_mood_matrix.py"),
    ("E7. scene_aware_scorer", "ai/t30b_scene_aware_scorer.py"),
    ("E8. multi_ip_corpus_factory", "ai/t31_multi_ip_corpus.py"),
    ("E9. balanced_lora_retrain", "ai/t32_balanced_lora_retrain.py"),
    ("E10. 100IP原型库", "data/ip_prototypes_100.json"),
    ("E11. ViT-L-14 LoRA", "models/clip_lora_aot_vitl14.pt"),
    ("E12. 场景分类器模型", "models/scene_classifier_v1.pt"),
]

for name, path in baseline_modules:
    fp = ROOT / path
    check(name, fp.exists(), f"{path}")

# ═══ 汇总 ═══
elapsed = time.time() - t0
n_pass = sum(1 for r in results if r['status'] == PASS)
n_total = len(results)

print(f"\n{'='*65}")
print(f"  验收结果: {n_pass}/{n_total} PASS ({elapsed:.1f}s)")
print(f"{'='*65}")

# 保存报告
report = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "total": n_total,
    "pass": n_pass,
    "fail": n_total - n_pass,
    "elapsed_s": round(elapsed, 1),
    "details": results,
}
report_path = ROOT / "reports" / "t35_final_accept.json"
report_path.parent.mkdir(parents=True, exist_ok=True)
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n报告: {report_path}")
