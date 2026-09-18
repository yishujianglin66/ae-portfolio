import subprocess
import sys

BRANCH_A = "master"
BRANCH_B = "feat/project-consolidation-v1"

def run_git(args):
    result = subprocess.run(["git"] + args, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def ls_tree(branch, path_prefix):
    stdout, stderr, rc = run_git(["ls-tree", "-r", "--name-only", branch])
    files = [f for f in stdout.split("\n") if f.startswith(path_prefix)]
    return sorted([f for f in files if f])

def file_exists(branch, filepath):
    _, _, rc = run_git(["cat-file", "-e", f"{branch}:{filepath}"])
    return rc == 0

def get_file_hash(branch, filepath):
    stdout, _, _ = run_git(["ls-tree", branch, filepath])
    parts = stdout.split()
    if len(parts) >= 3:
        return parts[2]
    return None

def compare_file(branch_a, branch_b, filepath):
    exists_a = file_exists(branch_a, filepath)
    exists_b = file_exists(branch_b, filepath)
    if not exists_a and not exists_b:
        return "both_missing"
    if not exists_a and exists_b:
        return "only_in_b"
    if exists_a and not exists_b:
        return "only_in_a"
    hash_a = get_file_hash(branch_a, filepath)
    hash_b = get_file_hash(branch_b, filepath)
    if hash_a == hash_b:
        return "same"
    return "different"

print("="*80)
print(f"分支对比分析报告: {BRANCH_A} vs {BRANCH_B}")
print("="*80)
print()

print("="*80)
print("【1】ae/adapters/ 目录适配器文件分析")
print("="*80)

excluded_adapters = {"au_adapter.py", "mcp_adapter.py", "pr_adapter.py", "ps_adapter.py"}
adapters_master = ls_tree(BRANCH_A, "ae/adapters/")
adapters_feature = ls_tree(BRANCH_B, "ae/adapters/")
adapters_master_files = set(f.replace("ae/adapters/", "") for f in adapters_master)
adapters_feature_files = set(f.replace("ae/adapters/", "") for f in adapters_feature)
new_in_feature = adapters_feature_files - adapters_master_files
all_new_files = sorted([f for f in new_in_feature if f.endswith(".py")])
print(f"\nmaster 分支 ae/adapters/ 下的 .py 文件: {sorted(adapters_master_files)}")
print(f"feat   分支 ae/adapters/ 下的 .py 文件: {sorted(adapters_feature_files)}")
print(f"\n排除已有4个适配器 {sorted(excluded_adapters)} 后:")
if all_new_files:
    print(f"⚠️  发现 {len(all_new_files)} 个新适配器在 feat 分支中缺失于 master:")
    missing_paths_1 = []
    for f in all_new_files:
        fpath = f"ae/adapters/{f}"
        missing_paths_1.append(fpath)
        print(f"   - {fpath}")
    print("\n同步命令:")
    for p in missing_paths_1:
        print(f"  git checkout {BRANCH_B} -- {p}")
else:
    print("✅  feat 分支中没有发现超出4个基础适配器之外的新适配器文件")

print()
print("="*80)
print("【2】puppet_adapter 相关代码分析")
print("="*80)

puppet_patterns = ["puppet_adapter", "puppet-automation"]
puppet_master_files = set()
puppet_feature_files = set()
stdout_m, _, _ = run_git(["ls-tree", "-r", "--name-only", BRANCH_A])
for f in stdout_m.split("\n"):
    if any(p in f.lower() for p in puppet_patterns):
        if f:
            puppet_master_files.add(f)
stdout_f, _, _ = run_git(["ls-tree", "-r", "--name-only", BRANCH_B])
for f in stdout_f.split("\n"):
    if any(p in f.lower() for p in puppet_patterns):
        if f:
            puppet_feature_files.add(f)

print(f"\nmaster 分支 puppet* 相关文件: {sorted(puppet_master_files)}")
print(f"feat   分支 puppet* 相关文件: {sorted(puppet_feature_files)}")

missing_puppet = sorted(puppet_feature_files - puppet_master_files)
existing_puppet = sorted(puppet_feature_files & puppet_master_files)

if missing_puppet:
    print(f"\n⚠️  {len(missing_puppet)} 个 puppet 相关文件缺失于 master:")
    for p in missing_puppet:
        print(f"   - {p}")
    print("\n同步命令:")
    for p in missing_puppet:
        print(f"  git checkout {BRANCH_B} -- {p}")
else:
    print("\n✅  feat 分支中没有新的 puppet 相关文件缺失于 master")

if existing_puppet:
    print("\n两分支共有的 puppet 文件内容对比:")
    for p in existing_puppet:
        status = compare_file(BRANCH_A, BRANCH_B, p)
        if status == "same":
            print(f"   ✅ {p} -> 已同步，文件内容hash一致")
        elif status == "different":
            print(f"   ⚠️  {p} -> 已同步，文件内容hash不一致")
            print(f"      同步命令: git checkout {BRANCH_B} -- {p}")

print()
print("="*80)
print("【3】emotion_curve* 相关文件分析")
print("="*80)

emotion_master_files = set()
emotion_feature_files = set()
for f in stdout_m.split("\n"):
    if "emotion_curve" in f and f:
        emotion_master_files.add(f)
for f in stdout_f.split("\n"):
    if "emotion_curve" in f and f:
        emotion_feature_files.add(f)

print(f"\nmaster 分支 emotion_curve* 相关文件: {sorted(emotion_master_files)}")
print(f"feat   分支 emotion_curve* 相关文件: {sorted(emotion_feature_files)}")

excluded_emotion = {"ae/emotion_curve_generator.py"}
missing_emotion = sorted(emotion_feature_files - emotion_master_files)
extra_emotion = sorted([f for f in missing_emotion if f not in excluded_emotion])
existing_emotion = sorted(emotion_feature_files & emotion_master_files)

if extra_emotion:
    print(f"\n⚠️  {len(extra_emotion)} 个 emotion_curve* 补充模块缺失于 master (排除 emotion_curve_generator.py):")
    for p in extra_emotion:
        print(f"   - {p}")
    print("\n同步命令:")
    for p in extra_emotion:
        print(f"  git checkout {BRANCH_B} -- {p}")
else:
    print("\n✅  feat 分支中没有发现 emotion_curve_generator.py 之外的补充模块缺失于 master")

if existing_emotion:
    print("\n两分支共有的 emotion_curve 文件内容对比:")
    for p in existing_emotion:
        status = compare_file(BRANCH_A, BRANCH_B, p)
        if status == "same":
            print(f"   ✅ {p} -> 已同步，文件内容hash一致")
        elif status == "different":
            print(f"   ⚠️  {p} -> 已同步，文件内容hash不一致")
            print(f"      同步命令: git checkout {BRANCH_B} -- {p}")

print()
print("="*80)
print("【4】ae/presets/combinations* 预设组合配置分析")
print("="*80)

combos_master = sorted([f for f in stdout_m.split("\n") if "ae/presets/combinations" in f and f])
combos_feature = sorted([f for f in stdout_f.split("\n") if "ae/presets/combinations" in f and f])

print(f"\nmaster 分支 combinations* 相关文件: {combos_master}")
print(f"feat   分支 combinations* 相关文件: {combos_feature}")

missing_combos = sorted(set(combos_feature) - set(combos_master))
existing_combos = sorted(set(combos_feature) & set(combos_master))

if missing_combos:
    print(f"\n⚠️  {len(missing_combos)} 个预设组合配置文件缺失于 master:")
    for p in missing_combos:
        print(f"   - {p}")
    print("\n同步命令:")
    for p in missing_combos:
        print(f"  git checkout {BRANCH_B} -- {p}")
else:
    print("\n✅  feat 分支中没有新的 combinations* 预设文件缺失于 master")

if existing_combos:
    print("\n两分支共有的 combinations 文件内容对比:")
    for p in existing_combos:
        status = compare_file(BRANCH_A, BRANCH_B, p)
        if status == "same":
            print(f"   ✅ {p} -> 已同步，文件内容hash一致")
        elif status == "different":
            print(f"   ⚠️  {p} -> 已同步，文件内容hash不一致")
            print(f"      同步命令: git checkout {BRANCH_B} -- {p}")

print()
print("="*80)
print("【汇总】缺失文件总清单")
print("="*80)
all_missing = missing_paths_1 if 'missing_paths_1' in dir() else []
all_missing += missing_puppet
all_missing += extra_emotion
all_missing += missing_combos
if all_missing:
    print(f"\n共 {len(all_missing)} 个文件需要从 {BRANCH_B} 同步到 {BRANCH_A}:")
    for p in all_missing:
        print(f"  - {p}")
    print("\n批量同步命令:")
    print(f"  git checkout {BRANCH_B} -- " + " ".join(all_missing))
else:
    print("\n✅  4类模块在 master 和 feat 分支中均已同步，无缺失文件")

print()
