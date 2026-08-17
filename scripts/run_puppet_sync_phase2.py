"""Puppet Phase2: ae+blender+ffmpeg 三引擎逐次同步验证脚本"""
import ast
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
PHASE1_PATH = REPO_ROOT / "output" / "evidence" / "puppet_sync_phase1_20260818.json"
OUTPUT_PATH = REPO_ROOT / "output" / "evidence" / "puppet_sync_phase2_three_engines_20260818.json"
PYTHON_CMD = ["py", "-3.12"]

ENGINES = ["ae", "blender", "ffmpeg"]
ENGINE_DIRS = {e: f"puppet-automation/src/engines/{e}/" for e in ENGINES}
IMPORT_PATHS = {
    "ae": "from src.engines.ae import AEEngine",
    "blender": "from src.engines.blender import BlenderEngine",
    "ffmpeg": "from src.engines.ffmpeg import FFmpegEngine",
}
CLASS_NAMES = {
    "ae": "AEEngine",
    "blender": "BlenderEngine",
    "ffmpeg": "FFmpegEngine",
}

git_checkout_commands_executed = []


def run_git(args, cwd=REPO_ROOT):
    """运行git命令并返回 (returncode, stdout, stderr)"""
    full_args = ["git", "-c", "core.quotepath=false"] + args
    try:
        proc = subprocess.run(
            full_args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return -1, "", str(e)


def build_pending_files_from_phase1():
    """从Phase1 JSON中筛选三个引擎的待同步文件清单"""
    ae_files, blender_files, ffmpeg_files = [], [], []

    if PHASE1_PATH.exists():
        with open(PHASE1_PATH, "r", encoding="utf-8") as f:
            phase1 = json.load(f)
        risky = phase1.get("risky_pending_sync", {})
        sources = [
            risky.get("categories", {}).get("engines_hash_diff", []),
            risky.get("categories", {}).get("new_tests", []),
            risky.get("categories", {}).get("new_engines", []),
        ]
        all_pending = []
        for s in sources:
            all_pending.extend(s)

        ae_dir = ENGINE_DIRS["ae"].rstrip("/")
        blender_dir = ENGINE_DIRS["blender"].rstrip("/")
        ffmpeg_dir = ENGINE_DIRS["ffmpeg"].rstrip("/")

        for p in all_pending:
            if p.startswith(ae_dir):
                ae_files.append(p)
            elif p.startswith(blender_dir):
                blender_files.append(p)
            elif p.startswith(ffmpeg_dir):
                ffmpeg_files.append(p)

    return {"ae": ae_files, "blender": blender_files, "ffmpeg": ffmpeg_files}


def build_pending_from_git_diff(engine):
    """当Phase1清单为空时，使用git diff列出变更文件"""
    engine_dir = ENGINE_DIRS[engine].rstrip("/")
    rc, out, err = run_git([
        "diff", "--name-only", "master", "feat/project-consolidation-v1", "--", engine_dir
    ])
    files = []
    if rc == 0:
        for line in out.strip().split("\n"):
            line = line.strip()
            if line:
                files.append(line)
    return files


def collect_engine_python_files(engine):
    """收集引擎目录下所有 .py 文件（用于ast.parse）"""
    engine_rel = ENGINE_DIRS[engine].rstrip("/")
    engine_path = REPO_ROOT / engine_rel
    py_files = []
    if engine_path.exists():
        for root, dirs, files in os.walk(str(engine_path)):
            for fn in files:
                if fn.endswith(".py"):
                    full = Path(root) / fn
                    rel = full.relative_to(REPO_ROOT).as_posix()
                    py_files.append(rel)
    return sorted(py_files)


def git_checkout_engine(engine):
    """Step 1: 对引擎目录执行 git checkout feat/project-consolidation-v1"""
    engine_rel = ENGINE_DIRS[engine].rstrip("/")
    cmd = [
        "checkout", "feat/project-consolidation-v1", "--", engine_rel
    ]
    cmd_str = "git -c core.quotepath=false checkout feat/project-consolidation-v1 -- " + engine_rel
    git_checkout_commands_executed.append(cmd_str)
    rc, out, err = run_git(cmd)
    return rc, out, err


def record_sync_actions(engine):
    """Step 2: 记录 sync_actions = [{file, pre_existed(bool), size, git_status}]"""
    engine_rel = ENGINE_DIRS[engine].rstrip("/")
    engine_path = REPO_ROOT / engine_rel
    all_files = []
    if engine_path.exists():
        for root, dirs, files in os.walk(str(engine_path)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in files:
                full = Path(root) / fn
                rel = full.relative_to(REPO_ROOT).as_posix()
                if "__pycache__" not in rel:
                    all_files.append(rel)
    all_files = sorted(all_files)

    rc, status_out, _ = run_git(["status", "--porcelain", "--", engine_rel])
    status_map = {}
    if rc == 0:
        for line in status_out.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) >= 2:
                flag, path = parts[0], parts[1].strip('"')
                status_map[path] = flag

    actions = []
    for rel in all_files:
        full = REPO_ROOT / rel
        try:
            size = full.stat().st_size
        except OSError:
            size = 0
        pre_existed = rel.replace("\\", "/") not in status_map.get(rel, "") and rel not in status_map
        actions.append({
            "file": rel,
            "pre_existed": pre_existed,
            "size": size,
            "git_status": status_map.get(rel, ""),
        })
    return actions


def run_ast_parse(engine):
    """Step 3: ast.parse 验证引擎目录下所有 .py 文件"""
    py_files = collect_engine_python_files(engine)
    total = len(py_files)
    ok_count = 0
    fail_count = 0
    fails = []
    for rel in py_files:
        full = REPO_ROOT / rel
        try:
            src = open(str(full), "r", encoding="utf-8").read()
            ast.parse(src, filename=rel)
            ok_count += 1
        except SyntaxError as e:
            fail_count += 1
            fails.append({
                "file": rel,
                "error": f"SyntaxError: {e.msg} (line {e.lineno}, col {e.offset})",
            })
        except Exception as e:
            fail_count += 1
            fails.append({
                "file": rel,
                "error": f"{type(e).__name__}: {str(e)}",
            })
    return {
        "total": total,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "fails": fails,
    }


def run_import_test(engine):
    """Step 4: 最小导入验证"""
    import_line = IMPORT_PATHS[engine]
    puppet_root = REPO_ROOT / "puppet-automation"
    script = (
        f"import sys, os\n"
        f"sys.path.insert(0, r'{puppet_root}')\n"
        f"try:\n"
        f"    {import_line}\n"
        f"    print('IMPORT_OK')\n"
        f"except Exception as e:\n"
        f"    print('IMPORT_FAIL:' + repr(str(e)))\n"
    )
    try:
        proc = subprocess.run(
            PYTHON_CMD + ["-c", script],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        lines = out.strip().split("\n")
        ok = False
        error = None
        for line in lines:
            if line.startswith("IMPORT_OK"):
                ok = True
                error = None
                break
            if line.startswith("IMPORT_FAIL:"):
                ok = False
                error = line[len("IMPORT_FAIL:"):]
                break
        if not ok and error is None:
            error = out.strip()[-500:] if out.strip() else f"exit_code={proc.returncode}"
        return {"ok": ok, "error": error}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)}"}


def find_test_file(engine):
    """Step 5: 查找并收集测试文件（pytest --co）"""
    candidates = []
    tests_dir = REPO_ROOT / "puppet-automation" / "tests"
    if tests_dir.exists():
        for pattern in [f"test_{engine}_engine.py", f"test_{engine}*.py"]:
            for p in tests_dir.glob(pattern):
                if p.is_file():
                    candidates.append(p)
    puppet_root = REPO_ROOT / "puppet-automation"
    if puppet_root.exists():
        for pattern in [f"test_{engine}*.py"]:
            for p in puppet_root.glob(pattern):
                if p.is_file():
                    candidates.append(p)

    seen = set()
    unique_candidates = []
    for c in candidates:
        if str(c) not in seen:
            seen.add(str(c))
            unique_candidates.append(c)

    if not unique_candidates:
        return {"found": False, "message": "test file not found"}

    test_path = unique_candidates[0]
    test_rel = test_path.relative_to(REPO_ROOT).as_posix()

    try:
        proc = subprocess.run(
            PYTHON_CMD + ["-m", "pytest", "-xvs", "--co", str(test_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode == 0
        collected = 0
        for line in out.split("\n"):
            if "collected" in line and "error" not in line.lower():
                tokens = line.strip().split()
                for tok in tokens:
                    if tok.isdigit():
                        collected = int(tok)
                        break
        return {
            "found": True,
            "path": test_rel,
            "collected_tests_count": collected,
            "collect_ok": ok,
        }
    except Exception as e:
        return {
            "found": True,
            "path": test_rel,
            "collected_tests_count": 0,
            "collect_ok": False,
            "error": f"{type(e).__name__}: {str(e)}",
        }


def process_engine(engine, pending_files_from_phase1):
    """逐引擎完整流程"""
    result = {
        "pending_files_count": 0,
        "synced_files_count": 0,
        "sync_actions": [],
        "parse_results": {},
        "import_test": {},
        "test_file": {},
        "git_checkout": {"ok": True, "error": None, "stdout": "", "stderr": ""},
    }

    pending = pending_files_from_phase1.get(engine, [])
    if not pending:
        pending = build_pending_from_git_diff(engine)
    result["pending_files_count"] = len(pending)

    rc, out, err = git_checkout_engine(engine)
    result["git_checkout"]["stdout"] = out
    result["git_checkout"]["stderr"] = err
    if rc != 0:
        result["git_checkout"]["ok"] = False
        result["git_checkout"]["error"] = err.strip() or f"git checkout exit code {rc}"

    result["sync_actions"] = record_sync_actions(engine)
    result["synced_files_count"] = len(result["sync_actions"])

    result["parse_results"] = run_ast_parse(engine)
    result["import_test"] = run_import_test(engine)
    result["test_file"] = find_test_file(engine)

    return result


def engine_passed(engine_result):
    """判断引擎是否通过所有检查"""
    pr = engine_result["parse_results"]
    it = engine_result["import_test"]
    gc = engine_result["git_checkout"]["ok"]
    parse_ok = pr.get("fail_count", 999) == 0
    import_ok = it.get("ok", False)
    return gc and parse_ok and import_ok


def main():
    os.makedirs(str(OUTPUT_PATH.parent), exist_ok=True)

    pending_map = build_pending_files_from_phase1()

    engines_result = {}
    for e in ENGINES:
        print(f"\n========== Processing engine: {e} ==========")
        try:
            engines_result[e] = process_engine(e, pending_map)
            passed = "PASS" if engine_passed(engines_result[e]) else "FAIL"
            print(f"  => {e}: {passed}")
        except Exception as exc:
            engines_result[e] = {
                "pending_files_count": 0,
                "synced_files_count": 0,
                "sync_actions": [],
                "parse_results": {"total": 0, "ok_count": 0, "fail_count": 0, "fails": []},
                "import_test": {"ok": False, "error": f"Fatal: {type(exc).__name__}: {str(exc)}"},
                "test_file": {"found": False, "message": f"engine processing crashed: {type(exc).__name__}: {str(exc)}"},
                "git_checkout": {"ok": False, "error": f"Fatal exception: {traceback.format_exc(limit=2)}"},
            }
            print(f"  => {e}: FAIL (fatal exception)")

    engines_passed_count = sum(1 for e in ENGINES if engine_passed(engines_result[e]))
    summary_parts = []
    for e in ENGINES:
        summary_parts.append(f"{e}: {'PASS' if engine_passed(engines_result[e]) else 'FAIL'}")
    summary = ", ".join(summary_parts)

    final = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engines_synced": ENGINES,
        "engines": engines_result,
        "all_git_checkout_commands": git_checkout_commands_executed,
        "overall_result": {
            "engines_passed_count": engines_passed_count,
            "summary": summary,
        },
        "skipped_reason": "Phase2严格只同步这3个引擎，其余cinema4d/matting/flux3/sam2等62个文件保持pending（避免整体崩盘）",
    }

    with open(str(OUTPUT_PATH), "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"\nEVIDENCE SAVED: output/evidence/puppet_sync_phase2_three_engines_20260818.json ({engines_passed_count}/3 engines passed)")


if __name__ == "__main__":
    main()
