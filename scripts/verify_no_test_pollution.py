"""端到端验收：跑完整测试套件，确认测试不再向仓库写运行期状态。

用法: python tmp/verify_no_test_pollution.py
判定:
  1. 运行前后 git status（排除并行会话/嵌套仓库噪声）必须完全一致；
  2. 仓库内不得有被跟踪文件被改写，也不得出现新的未跟踪文件；
  3. 旧画像路径 user_data/ 必须保持不再被写入（它现在已被 .gitignore 覆盖，
     仅靠 git status 判断会失效，所以单独用 mtime + 内容哈希盯它）。
结果写入 tmp/verify_no_test_pollution.log，便于跨会话查验。
"""
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG_PATH = REPO / "tmp" / "verify_no_test_pollution.log"
LEGACY_PROFILE = REPO / "13-素材获取与搜索" / "03-AI语义搜索" / "user_data"


def status_snapshot():
    raw = subprocess.run(["git", "status", "--porcelain", "-uall"],
                         capture_output=True, cwd=REPO).stdout.decode("utf-8", "replace")
    return {line for line in raw.splitlines() if line.strip()}


def is_unstable(line):
    """并行会话/嵌套仓库造成的已知噪声，不参与判定。"""
    markers = ("OpenSpace", "external/OpenMontage", "docs/handoff-2026-08-16-m2-tuner.md")
    return any(m in line for m in markers)


def clean(paths):
    out = set()
    for line in paths:
        body = line[3:].strip().strip('"')
        if not is_unstable(body):
            out.add(line)
    return out


def fingerprint_legacy_dir():
    """旧画像目录里每个文件的 (大小, mtime, 内容哈希)。"""
    if not LEGACY_PROFILE.exists():
        return {"<absent>": None}
    out = {}
    for p in LEGACY_PROFILE.rglob("*"):
        if not p.is_file():
            continue
        data = p.read_bytes()
        stat = p.stat()
        out[str(p.relative_to(REPO))] = {
            "size": len(data),
            "mtime": int(stat.st_mtime),
            "sha256": hashlib.sha256(data).hexdigest()[:16],
        }
    return out


lines = []


def say(msg):
    print(msg, flush=True)
    lines.append(str(msg))


t_start = time.time()
before = clean(status_snapshot())
legacy_before = fingerprint_legacy_dir()
say(f"[1/3] 运行前工作区（排除已知噪声）: {len(before)} 条")
for line in sorted(before):
    say(f"    {line}")
say(f"      旧画像目录指纹: {legacy_before}")

say("[2/3] 开始全量测试 ...")
proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=line"],
                      capture_output=True, cwd=REPO)
elapsed = time.time() - t_start
out = proc.stdout.decode("utf-8", "replace").splitlines()
say("\n".join(out[-15:]))
say(f"      pytest exit code = {proc.returncode}")

after = clean(status_snapshot())
legacy_after = fingerprint_legacy_dir()
say(f"\n[3/3] 运行后工作区（排除已知噪声）: {len(after)} 条  用时 {elapsed:.0f}s")

newly = after - before
disappeared = before - after
polluted_legacy = [
    name for name, fp in legacy_after.items()
    if legacy_before.get(name) != fp
]

ok = True
if newly or disappeared or polluted_legacy:
    ok = False
    say("==> 失败：测试仍然污染仓库")
    for line in sorted(newly):
        say(f"    新增脏项: {line}")
    for line in sorted(disappeared):
        say(f"    消失脏项: {line}")
    for name in polluted_legacy:
        say(f"    旧画像目录仍被写入: {name} before={legacy_before.get(name)} after={legacy_after.get(name)}")
else:
    say("==> 通过：全量测试未改动 git 工作区任何被跟踪/新产生的文件，且旧画像目录零写入")

say(f"    新画像目录: {Path.home() / '.ae-knowledge-vault' / 'user_preference'}")
dst = Path.home() / ".ae-knowledge-vault" / "user_preference"
if dst.exists():
    for p in sorted(dst.rglob("*")):
        if p.is_file():
            say(f"      {p.name}  {p.stat().st_size} bytes  mtime={time.strftime('%H:%M:%S', time.localtime(p.stat().st_mtime))}")

LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
sys.exit(0 if ok else 1)
