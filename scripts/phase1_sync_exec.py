import os
import ast
import json
import subprocess
from datetime import datetime, timezone

REPO_ROOT = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"
FEAT_BRANCH = "feat/project-consolidation-v1"
DIFF_FILE = os.path.join(REPO_ROOT, "output", "evidence", "git_branch_diff_20260818.json")
OUTPUT_FILE = os.path.join(REPO_ROOT, "output", "evidence", "puppet_sync_phase1_20260818.json")

PHASE1_FILES = [
    "puppet-automation/src/engines/registry.py",
    "puppet-automation/src/engines/base.py",
    "puppet-automation/src/config/settings.py",
    "puppet-automation/src/api/main.py",
    "puppet-automation/src/auth.py",
]


def run_git_checkout(rel_path: str):
    full_cmd = f'git checkout {FEAT_BRANCH} -- "{rel_path}"'
    result = subprocess.run(
        full_cmd,
        shell=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "command": full_cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def verify_file(rel_path: str):
    abs_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
    record = {
        "file": rel_path,
        "action": "synced",
        "size_bytes": None,
        "first_3_lines": [],
        "parse_ok": False,
        "error_message": None,
    }

    if not os.path.exists(abs_path):
        record["error_message"] = f"FILE_NOT_FOUND: {abs_path}"
        return record

    try:
        stat = os.stat(abs_path)
        record["size_bytes"] = stat.st_size

        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= 3:
                    break
                lines.append(line.rstrip("\n"))
            record["first_3_lines"] = lines

        if abs_path.endswith(".py") and record["size_bytes"] > 0:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            try:
                ast.parse(content)
                record["parse_ok"] = True
            except SyntaxError as e:
                record["parse_ok"] = False
                record["error_message"] = f"SYNTAX_ERROR: {e}"
        else:
            record["parse_ok"] = True if record["size_bytes"] and record["size_bytes"] > 0 else False

    except Exception as e:
        record["error_message"] = f"VERIFY_EXCEPTION: {e}"

    return record


def classify_pending(only_in_feat, content_hash_diff):
    new_engines = []
    engines_hash_diff = []
    new_services = []
    new_tests = []
    not_recommended = []

    engine_names = {
        "ae", "blender", "ffmpeg", "davinci", "silhouette", "topaz",
        "whisper", "rife", "comfyui", "photoshop", "openmontage",
        "premiere", "audition", "media_encoder", "moviepy",
        "cinema4d", "flux3", "matting", "sadtalker", "sam2", "pr",
    }
    new_engine_names = {"cinema4d", "flux3", "matting", "sadtalker", "sam2"}

    puppet_only = [e for e in only_in_feat if e["path"].startswith("puppet-automation/")]
    puppet_hashdiff = [e for e in content_hash_diff if e["path"].startswith("puppet-automation/")]

    for entry in puppet_only:
        p = entry["path"]
        parts = p.split("/")
        if "engines" in parts:
            eng_idx = parts.index("engines")
            if eng_idx + 1 < len(parts):
                eng_name = parts[eng_idx + 1]
                if eng_name in new_engine_names:
                    if p.endswith("engine.py") or p.endswith("__init__.py"):
                        if p not in new_engines:
                            new_engines.append(p)
                    else:
                        if p not in new_engines:
                            new_engines.append(p)
                elif eng_name in engine_names:
                    if p not in engines_hash_diff:
                        engines_hash_diff.append(p)
        elif "services" in parts and p.endswith(".py"):
            fname = os.path.basename(p)
            if fname in ("blender_nl_service.py", "dashboard_storage.py"):
                new_services.append(p)
            else:
                new_services.append(p)
        elif p.startswith("puppet-automation/tests/test_") and p.endswith("_engine.py"):
            new_tests.append(p)
        elif p.startswith("puppet-automation/tests/test_") and p.endswith(".py"):
            fname = os.path.basename(p)
            eng_test = False
            for en in engine_names:
                if fname == f"test_{en}_engine.py":
                    eng_test = True
                    break
            if eng_test:
                new_tests.append(p)
            else:
                new_tests.append(p)
        elif "workers" in parts and ("celery" in p):
            not_recommended.append(p)
        elif "mcp_gateway" in parts and p.endswith("gateway.py"):
            not_recommended.append(p)

    for entry in puppet_hashdiff:
        p = entry["path"]
        parts = p.split("/")
        if "engines" in parts:
            eng_idx = parts.index("engines")
            if eng_idx + 1 < len(parts):
                eng_name = parts[eng_idx + 1]
                if eng_name in new_engine_names:
                    if p not in new_engines:
                        new_engines.append(p)
                elif eng_name in engine_names:
                    if p not in engines_hash_diff:
                        engines_hash_diff.append(p)
        elif "workers" in parts and ("celery" in p):
            if p not in not_recommended:
                not_recommended.append(p)
        elif "mcp_gateway" in parts and p.endswith("gateway.py"):
            if p not in not_recommended:
                not_recommended.append(p)

    new_engines = sorted(set(new_engines))
    engines_hash_diff = sorted(set(engines_hash_diff))
    new_services = sorted(set(new_services))
    new_tests = sorted(set(new_tests))
    not_recommended = sorted(set(not_recommended))

    total = (
        len(new_engines)
        + len(engines_hash_diff)
        + len(new_services)
        + len(new_tests)
        + len(not_recommended)
    )
    return {
        "total_pending_files": total,
        "categories": {
            "new_engines": new_engines,
            "engines_hash_diff": engines_hash_diff,
            "new_services": new_services,
            "new_tests": new_tests,
            "not_recommended": not_recommended,
        },
        "recommendation": "Phase2建议逐引擎验证：先ae→blender→ffmpeg，每个引擎同步后跑对应test_*_engine.py",
    }


def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    synced_records = []
    checkout_commands = []
    success_count = 0
    fail_count = 0

    for rel_path in PHASE1_FILES:
        cmd_result = run_git_checkout(rel_path)
        checkout_commands.append(cmd_result["command"])

        if cmd_result["returncode"] != 0:
            rec = {
                "file": rel_path,
                "action": "sync_failed",
                "size_bytes": None,
                "first_3_lines": [],
                "parse_ok": False,
                "error_message": f"GIT_CHECKOUT_FAILED (rc={cmd_result['returncode']}): {cmd_result['stderr'].strip()}",
            }
            synced_records.append(rec)
            fail_count += 1
            continue

        verify_rec = verify_file(rel_path)
        synced_records.append(verify_rec)
        if verify_rec["error_message"] is None and verify_rec["parse_ok"]:
            success_count += 1
        else:
            fail_count += 1

    phase1_result = (
        "all_5_synced_successfully"
        if success_count == 5 and fail_count == 0
        else f"{success_count}_ok_{fail_count}_failed"
    )

    with open(DIFF_FILE, "r", encoding="utf-8") as f:
        diff_data = json.load(f)

    only_in_feat = diff_data.get("diff_matrix", {}).get("only_in_feat", [])
    content_hash_diff = diff_data.get("diff_matrix", {}).get("content_hash_diff", [])

    risky_pending = classify_pending(only_in_feat, content_hash_diff)

    evidence = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase1_synced_files": synced_records,
        "phase1_result": phase1_result,
        "risky_pending_sync": risky_pending,
        "phase1_git_checkout_commands": checkout_commands,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)

    pending_total = risky_pending["total_pending_files"]
    print(
        f"EVIDENCE SAVED: output/evidence/puppet_sync_phase1_20260818.json  "
        f"(Phase1: {success_count}/5 files OK, Phase2 pending: {pending_total} files)"
    )
    print(f"Phase1 result: {phase1_result}")
    for rec in synced_records:
        status = "OK" if rec.get("parse_ok") and not rec.get("error_message") else "FAIL"
        err = rec.get("error_message") or ""
        sz = rec.get("size_bytes")
        print(f"  [{status}] {rec['file']}  size={sz}  err={err[:80]}")
    cats = risky_pending["categories"]
    print(
        f"Pending categories: new_engines={len(cats['new_engines'])}, "
        f"engines_hash_diff={len(cats['engines_hash_diff'])}, "
        f"new_services={len(cats['new_services'])}, "
        f"new_tests={len(cats['new_tests'])}, "
        f"not_recommended={len(cats['not_recommended'])}"
    )


if __name__ == "__main__":
    main()
