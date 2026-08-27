"""扫描待入库的未跟踪文件是否包含凭据类字符串。只读，不改任何文件。"""
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

raw = subprocess.run(["git", "status", "--porcelain", "-uall"],
                     capture_output=True).stdout.decode("utf-8", "replace")
untracked = [line[3:].strip() for line in raw.splitlines() if line.startswith("?? ")]
payload = [f for f in untracked
           if not f.replace("\\", "/").startswith("models/weights/")]

PATTERNS = {
    "api_key": re.compile(
        r"(?i)\b(api[_-]?key|apikey|secret[_-]?key|access[_-]?key)\b\s*[:=]\s*['\"][^'\"]{8,}"),
    "token": re.compile(
        r"(?i)\b(token|bearer)\b\s*[:=]\s*['\"][A-Za-z0-9_\-.]{16,}"),
    "sk_live": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "aws": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "password": re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]{4,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "url_credentials": re.compile(r"\w{3,9}://[^/\s'\"]+:[^/\s'\"]+@"),
}

hits = []
scanned = 0
for rel in payload:
    path = os.path.join(REPO, rel.replace("\\", "/"))
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > 2_000_000:
            continue
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        hits.append((rel, "read_error", str(exc)))
        continue
    scanned += 1
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        # PowerShell 等工具默认写 UTF-16：每个 ASCII 字符后跟 NUL，
        # 不能按"含 NUL 即二进制"跳过，否则这类文件永远没被扫过。
        text = data.decode("utf-16", "replace")
    elif b"\x00" in data[:4096]:
        continue
    else:
        text = data.decode("utf-8", "replace")
    for name, rx in PATTERNS.items():
        for match in rx.finditer(text):
            lineno = text[:match.start()].count("\n") + 1
            snippet = match.group(0).replace("\n", "\\n")[:70]
            hits.append((rel, name, f"L{lineno}: {snippet}"))

print(f"扫描 {scanned}/{len(payload)} 个文件 -> {len(hits)} 处可疑命中\n")
for rel, name, detail in hits:
    print(f"  [{name}] {rel}  {detail}")
