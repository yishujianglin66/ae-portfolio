"""Find test files that hang during execution."""
import glob
import os
import subprocess
import sys

os.chdir(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

# Parse ignore list from pytest.ini
ignored = set()
with open("pytest.ini", encoding="utf-8") as f:
    for line in f:
        if "--ignore=tests/" in line:
            ignored.add(line.strip().split("--ignore=")[1].strip())

all_tests = sorted(glob.glob("tests/test_*.py"))
active = [t.replace("\\", "/") for t in all_tests]
active = [t for t in active if t not in ignored]
print(f"Active test files: {len(active)}")

hang = []
fail = []
for t in active:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", t, "-q", "--tb=no", "--no-header",
             "--timeout=8", "--timeout-method=thread"],
            capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace"
        )
        if "passed" in r.stdout:
            pass  # OK
        elif r.returncode != 0:
            fail.append(t)
    except subprocess.TimeoutExpired:
        hang.append(t)
    except Exception as e:
        fail.append(f"{t}: {e}")

print(f"\nHanging ({len(hang)}):")
for h in hang:
    print(f"  {h}")
print(f"\nFailed ({len(fail)}):")
for f2 in fail:
    print(f"  {f2}")
