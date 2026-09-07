import subprocess
import json
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict

REPO_ROOT = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"
OUTPUT_DIR = os.path.join(REPO_ROOT, "output", "evidence")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "git_branch_diff_20260818.json")

CATEGORY_PREFIXES = [
    "puppet-automation/",
    "ae/",
    "scripts/",
    "tests/",
    "config/",
]

def run_git(args, cwd=REPO_ROOT):
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip(), result.returncode

def get_latest_commit(branch):
    out, code = run_git(["rev-parse", branch])
    if code != 0:
        raise RuntimeError(f"Failed to get commit for {branch}: {out}")
    return out

def categorize(path):
    for prefix in CATEGORY_PREFIXES:
        if path.startswith(prefix):
            return prefix.rstrip("/")
    return "other"

def parse_ls_tree(output):
    entries = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        mode, obj_type, obj_hash, path = parts
        size = None
        if obj_type == "blob":
            size_out, _ = run_git(["cat-file", "-s", obj_hash])
            try:
                size = int(size_out)
            except ValueError:
                size = 0
        entries[path] = {
            "hash": obj_hash,
            "type": obj_type,
            "size": size if size is not None else 0,
        }
    return entries

def get_tree_entries(branch):
    out, code = run_git(["ls-tree", "-r", "-t", branch])
    if code != 0:
        raise RuntimeError(f"Failed to ls-tree {branch}: {out}")
    return parse_ls_tree(out)

def estimate_bytes_changed(path, master_hash, feat_hash):
    try:
        master_size_out, _ = run_git(["cat-file", "-s", master_hash])
        feat_size_out, _ = run_git(["cat-file", "-s", feat_hash])
        master_size = int(master_size_out) if master_size_out else 0
        feat_size = int(feat_size_out) if feat_size_out else 0
        diff_out, _ = run_git(["diff", "--numstat", f"{master_hash}..{feat_hash}"])
        added = 0
        deleted = 0
        for line in diff_out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    added += int(parts[0]) if parts[0] != "-" else 0
                    deleted += int(parts[1]) if parts[1] != "-" else 0
                except ValueError:
                    pass
        if added > 0 or deleted > 0:
            return abs(feat_size - master_size) + (added + deleted) * 50
        return abs(feat_size - master_size)
    except Exception:
        return 0

def build_file_entry(path, entry):
    return {
        "path": path,
        "size": entry["size"],
        "file_type": entry["type"],
        "category": categorize(path),
    }

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    branches_info = {}
    branch_names = [
        "master",
        "feat/project-consolidation-v1",
        "feat/phase1.1-gateway-consolidation",
    ]
    for b in branch_names:
        branches_info[b] = get_latest_commit(b)

    master_entries = get_tree_entries("master")
    feat_entries = get_tree_entries("feat/project-consolidation-v1")

    master_paths = set(master_entries.keys())
    feat_paths = set(feat_entries.keys())

    only_in_feat_paths = feat_paths - master_paths
    only_in_master_paths = master_paths - feat_paths
    common_paths = feat_paths & master_paths

    only_in_feat = []
    for p in sorted(only_in_feat_paths):
        only_in_feat.append(build_file_entry(p, feat_entries[p]))

    only_in_master = []
    for p in sorted(only_in_master_paths):
        only_in_master.append(build_file_entry(p, master_entries[p]))

    content_hash_diff = []
    for p in sorted(common_paths):
        m = master_entries[p]
        f = feat_entries[p]
        if m["hash"] != f["hash"] and m["type"] == "blob" and f["type"] == "blob":
            bytes_est = estimate_bytes_changed(p, m["hash"], f["hash"])
            content_hash_diff.append({
                "path": p,
                "master_hash": m["hash"],
                "feat_hash": f["hash"],
                "bytes_changed_est": bytes_est,
            })

    evidence = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "branches": {
            name: {"commit_hash": branches_info[name]}
            for name in branch_names
        },
        "diff_matrix": {
            "only_in_feat": only_in_feat,
            "only_in_master": only_in_master,
            "content_hash_diff": content_hash_diff,
        },
        "summary": {
            "total_only_in_feat": len(only_in_feat),
            "total_only_in_master": len(only_in_master),
            "total_hash_diff": len(content_hash_diff),
            "total_new_files_need_sync": len(only_in_feat),
        },
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fp:
        json.dump(evidence, fp, ensure_ascii=False, indent=2)

    total_entries = (
        len(only_in_feat)
        + len(only_in_master)
        + len(content_hash_diff)
    )
    print(f"EVIDENCE SAVED: {OUTPUT_FILE}  ({total_entries} entries)")

if __name__ == "__main__":
    main()
