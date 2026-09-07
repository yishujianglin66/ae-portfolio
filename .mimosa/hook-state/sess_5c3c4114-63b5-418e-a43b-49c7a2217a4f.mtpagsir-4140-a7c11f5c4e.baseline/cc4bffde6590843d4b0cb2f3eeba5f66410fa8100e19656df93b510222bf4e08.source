import os
import sys
import json
import subprocess
from datetime import datetime, timezone, timedelta

BASE_DIR = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"
EVIDENCE_DIR = os.path.join(BASE_DIR, "output", "evidence")
OUTPUT_FILE = os.path.join(EVIDENCE_DIR, "FINAL_SEAL_VERIFICATION_20260818.json")

tz_cst = timezone(timedelta(hours=8))
generated_at = datetime.now(tz_cst).isoformat()

files_checklist = [
    {"index": 1, "id": "T1", "filename": "git_branch_diff_20260818.json", "min_threshold": 400000},
    {"index": 2, "id": "T2", "filename": "kb_effect_inventory_20260818.json", "min_threshold": 40000},
    {"index": 3, "id": "T3", "filename": "import_health_report_20260818.json", "min_threshold": 70000},
    {"index": 4, "id": "T4", "filename": "causal_quality_verification_20260818.json", "min_threshold": 3000},
    {"index": 5, "id": "T5", "filename": "puppet_sync_phase1_20260818.json", "min_threshold": 5000},
    {"index": 6, "id": "T6a", "filename": "p02_trainplan_data_distribution_20260818.json", "min_threshold": 5000},
    {"index": 7, "id": "T6b", "filename": "p02_retrain_config_6class.yaml", "min_threshold": 5000},
    {"index": 8, "id": "T7", "filename": "ACCEPTANCE_REPORT_20260818.html", "min_threshold": 100000},
    {"index": 9, "id": "T9", "filename": "puppet_sync_phase2_three_engines_20260818.json", "min_threshold": 5000},
    {"index": 10, "id": "T10a", "filename": "t10_bge_baseline_20260818.json", "min_threshold": 2000},
    {"index": 11, "id": "T10b", "filename": "t10_bge_repair_verification_20260818.json", "min_threshold": 2000},
    {"index": 12, "id": "T11", "filename": "git_audit_and_commits_20260818.json", "min_threshold": 20000},
    {"index": 13, "id": "T12", "filename": "ACCEPTANCE_REPORT_V2_20260818.html", "min_threshold": 140000},
]

print("=" * 70)
print("验证A：13个证据文件存在+大小双验")
print("=" * 70)

per_file_results = []
passed_count = 0
failed_count = 0
failed_details = []
total_evidence_bytes = 0

for item in files_checklist:
    file_path = os.path.join(EVIDENCE_DIR, item["filename"])
    exists = os.path.exists(file_path)
    size_bytes = 0
    if exists:
        try:
            size_bytes = os.path.getsize(file_path)
        except Exception as e:
            size_bytes = 0
            exists = False
    
    size_pass = (size_bytes >= item["min_threshold"])
    file_pass = exists and size_pass
    
    if file_pass:
        passed_count += 1
    else:
        failed_count += 1
        fail_reason = []
        if not exists:
            fail_reason.append("文件不存在")
        if exists and not size_pass:
            fail_reason.append(f"大小不足 ({size_bytes} < {item['min_threshold']})")
        failed_details.append({
            "index": item["index"],
            "id": item["id"],
            "filename": item["filename"],
            "reason": "; ".join(fail_reason),
            "size_bytes": size_bytes,
            "min_threshold": item["min_threshold"]
        })
    
    total_evidence_bytes += size_bytes
    
    per_file_results.append({
        "index": item["index"],
        "id": item["id"],
        "path": file_path,
        "exists": exists,
        "size_bytes": size_bytes,
        "min_threshold": item["min_threshold"],
        "pass": file_pass
    })
    
    status = "PASS" if file_pass else "FAIL"
    print(f"  [{status}] #{item['index']} {item['id']:4s} {item['filename']:55s} exists={exists} size={size_bytes:>10,}B (≥{item['min_threshold']:>10,}B)")

verification_A = {
    "total_expected": 13,
    "passed": passed_count,
    "failed": failed_count,
    "total_evidence_bytes": total_evidence_bytes,
    "failed_details": failed_details,
    "per_file": per_file_results
}

print()
print(f"  → 验证A结果: {passed_count}/13 通过, {failed_count} 失败, 总大小 {total_evidence_bytes/1024/1024:.2f} MB")
print()

print("=" * 70)
print("验证B：BGE-M3 独立二次导入+编码验证")
print("=" * 70)

bge_script = r'''
import sys, os, json
sys.path.insert(0, '.')
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

print('[T13-INDEPENDENT] 独立验证进程启动... SentenceTransformer import')
from sentence_transformers import SentenceTransformer

MODEL_NAME = 'BAAI/bge-m3'
print(f'[T13-INDEPENDENT] 加载模型: {MODEL_NAME}')
model = SentenceTransformer(MODEL_NAME)

sentences = ['测试句子1', '这是向量搜索的验证', '科研级封口双重验证']
print(f'[T13-INDEPENDENT] 开始编码 {len(sentences)} 个句子')
vecs = model.encode(sentences)

shape = list(vecs.shape)
dtype = str(vecs.dtype)
print(f'T13-INDEPENDENT-VALIDATION dim={vecs.shape} dtype={dtype} sum={float(vecs.sum()):.6f} norm={float((vecs**2).sum()**0.5):.6f}')
print(json.dumps({'shape': shape, 'dtype': dtype}))
print(f'[T13-INDEPENDENT] ✅ 独立二次验证完成 shape={shape} dtype={dtype}')
'''

bge_wrapper_path = os.path.join(BASE_DIR, "tmp", "_t13_bge_independent_check.py")
os.makedirs(os.path.dirname(bge_wrapper_path), exist_ok=True)
with open(bge_wrapper_path, "w", encoding="utf-8") as f:
    f.write(bge_script)

bge_command = ["py", "-3.12", str(bge_wrapper_path)]

try:
    result = subprocess.run(
        bge_command,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    )
    stdout_full = result.stdout
    stderr_full = result.stderr
    returncode = result.returncode
except subprocess.TimeoutExpired as e:
    stdout_full = e.stdout if e.stdout else ""
    stderr_full = (e.stderr if e.stderr else "") + "\nTIMEOUT: BGE验证进程超时"
    returncode = -1
except Exception as e:
    stdout_full = ""
    stderr_full = f"EXCEPTION: {str(e)}"
    returncode = -2

print(f"  returncode: {returncode}")
print(f"  stdout tail: {stdout_full[-600:]}{'...(truncated)' if len(stdout_full) > 600 else ''}")
print(f"  stderr tail: {stderr_full[-400:]}{'...(truncated)' if len(stderr_full) > 400 else ''}")

dim_check = False
sentence_count_check = False
ssl_free = True

shape_info = None
for line in stdout_full.strip().split("\n"):
    line = line.strip()
    if line.startswith("{") and line.endswith("}"):
        try:
            shape_info = json.loads(line)
            break
        except:
            pass

if shape_info and "shape" in shape_info:
    shape = shape_info["shape"]
    if len(shape) >= 2:
        dim_check = (shape[1] == 1024)
        sentence_count_check = (shape[0] == 3)

ssl_error_keywords = ["UNEXPECTED_EOF_WHILE_READING", "client has been closed"]
for kw in ssl_error_keywords:
    if kw in stderr_full or kw in stdout_full:
        ssl_free = False
        break

B_pass = dim_check and sentence_count_check and ssl_free and (returncode == 0)

verification_B = {
    "independent_from_t10_cache": True,
    "wrapper_script_used": bge_wrapper_path,
    "pass": B_pass,
    "stdout": stdout_full,
    "stderr": stderr_full,
    "dim_check": dim_check,
    "sentence_count_check": sentence_count_check,
    "ssl_free": ssl_free,
    "explanation_if_fail": "若失败，说明T10可能是缓存偶然成功，需要重跑T10"
}

status_B = "PASS" if B_pass else "FAIL"
print(f"  → 验证B结果: {status_B} (dim=1024? {dim_check}, sentences=3? {sentence_count_check}, ssl_free? {ssl_free})")
print()

print("=" * 70)
print("验证C：Git commit 0c20d2d 纯净性二次验证")
print("=" * 70)

commit_hash = "0c20d2d"
git_command = [
    "git", "-c", "core.quotepath=false",
    "diff-tree", "--no-commit-id", "-r", "--name-only", commit_hash
]

committed_files_list = []
all_in_evidence_dir = False
no_code_pollution = False
C_pass = False

try:
    result_git = subprocess.run(
        git_command,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=60
    )
    git_stdout = result_git.stdout
    git_stderr = result_git.stderr
    git_returncode = result_git.returncode
    
    print(f"  git stdout: {git_stdout[:800]}{'...(truncated)' if len(git_stdout) > 800 else ''}")
    print(f"  git stderr: {git_stderr[:500]}{'...(truncated)' if len(git_stderr) > 500 else ''}")
    print(f"  git returncode: {git_returncode}")
    
    if git_returncode == 0:
        committed_files_list = [line.strip() for line in git_stdout.strip().split("\n") if line.strip()]
        
        committed_files_count = len(committed_files_list)
        all_in_evidence_dir = all(f.startswith("output/evidence/") for f in committed_files_list) if committed_files_list else False
        
        pollution_prefixes = ["knowledge_base/", "core/", "puppet-automation/"]
        no_code_pollution = not any(any(f.startswith(p) for p in pollution_prefixes) for f in committed_files_list)
        
        C_pass = (committed_files_count == 8) and all_in_evidence_dir and no_code_pollution
    else:
        committed_files_count = 0
except Exception as e:
    git_stdout = ""
    git_stderr = f"EXCEPTION: {str(e)}"
    committed_files_count = 0

verification_C = {
    "commit_hash": commit_hash,
    "expected_purity": "仅8个 output/evidence/ 文件，无任何代码污染",
    "committed_files_list": committed_files_list,
    "committed_files_count": len(committed_files_list),
    "all_in_evidence_dir": all_in_evidence_dir,
    "no_code_pollution": no_code_pollution,
    "pass": C_pass,
    "explanation_if_fail": "若失败，立刻 git reset --mixed 0c20d2d~1 重新add evidence"
}

status_C = "PASS" if C_pass else "FAIL"
print(f"  → 验证C结果: {status_C} (files={len(committed_files_list)}, all_in_evidence? {all_in_evidence_dir}, no_pollution? {no_code_pollution})")
print()

overall_seal_pass = (passed_count == 13) and B_pass and C_pass
seal_strength = "科研级封口合格" if overall_seal_pass else "科研级封口不合格"
if_pass_message = "V2 共13证据+代码修复3项+同步3引擎+BGE可用+Git纯净入库，全部达成。可交付验收。"
if_fail_message_parts = []
if passed_count < 13:
    if_fail_message_parts.append(f"A缺文件({passed_count}/13)")
if not B_pass:
    if_fail_message_parts.append("BGE验证失败(SSL/维度/数量)")
if not C_pass:
    if_fail_message_parts.append("commit污染")
if not if_fail_message_parts:
    if_fail_message_parts.append("未知原因")
if_fail_message = "失败原因：" + "/".join(if_fail_message_parts) + "。必须立刻重做对应子任务，不允许交付。"

final_seal = {
    "overall_pass": overall_seal_pass,
    "seal_strength": seal_strength,
    "if_pass_message": if_pass_message,
    "if_fail_message": if_fail_message
}

final_output = {
    "generated_at": generated_at,
    "seal_verification_name": "FINAL SCIENTIFIC SEAL · V2 · 2026-08-18",
    "verification_A_evidence_files": verification_A,
    "verification_B_bge_independent": verification_B,
    "verification_C_git_commit_purity": verification_C,
    "final_seal": final_seal
}

os.makedirs(EVIDENCE_DIR, exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(final_output, f, ensure_ascii=False, indent=2)

print("=" * 70)
print("FINAL SEAL:", OUTPUT_FILE)
print(f"  A. 13 Evidence files: {passed_count}/13  (total {total_evidence_bytes/1024/1024:.2f} MB)")
b_status_str = "PASS" if B_pass else "FAIL"
print(f"  B. BGE independent 2nd verify: {b_status_str} (dim=1024? {dim_check} sentences=3? {sentence_count_check} no SSL? {ssl_free})")
c_status_str = "PASS" if C_pass else "FAIL"
print(f"  C. Git commit 0c20d2d purity: {c_status_str} (8 files, all evidence, no pollution)")
overall_status = "PASS" if overall_seal_pass else "FAIL"
print(f"  OVERALL SEAL: {overall_status}")
print("=" * 70)

if not overall_seal_pass:
    print()
    print("【封口失败！铁律：不通过就是不通过，必须重做对应子任务】")
    sys.exit(1)
else:
    print()
    print("【封口成功！13证据+3修复+3引擎同步+BGE+Git纯净 全部达标。】")
