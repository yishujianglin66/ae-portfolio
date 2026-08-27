"""审计 .gitignore：每条否定规则（!xxx）是否真的还能救回文件。只读，不改任何文件。

为什么需要这个检查（两条 git 语义，都不会让任何测试变红）：
  1. git 取"最后匹配的规则"生效。写在后面的全局规则（如 *.png）会静默作废
     写在它前面的白名单（如 !05-测试套件/test_resources/*.png）。
  2. 若某目录本身被排除（如 resources/），其内文件的 ! 白名单永远无效——
     git 不会进入被排除目录去匹配文件级规则，必须先 ! 该目录本身。

用法: python scripts/audit_gitignore_negations.py [--verbose]
退出码: 0 = 全部白名单有效；1 = 存在死规则（配置写了但不生效）。
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GITIGNORE = REPO / ".gitignore"
VERBOSE = "--verbose" in sys.argv


def probe_path(pattern):
    """由否定模式反推一个"应当可被跟踪"的具体路径。"""
    p = pattern.strip()
    if not p:
        return None
    if p.endswith("/"):
        return p + "probe_placeholder.txt"
    if "*" in p:
        head, sep, tail = p.rpartition("/")
        name = tail.replace("*", "probe")
        return f"{head}/{name}" if head else name
    if "." in Path(p).name:
        return p
    return p + "/probe_placeholder.txt"


def is_ignored(path):
    """check-ignore -q：退出码 0 = 被忽略（无法新增入库）；命中否定规则时为 1。"""
    return subprocess.run(["git", "check-ignore", "-q", "--no-index", path],
                          cwd=REPO).returncode == 0


def matching_rule(path):
    out = subprocess.run(["git", "check-ignore", "-v", "--no-index", path],
                         capture_output=True, cwd=REPO).stdout.decode("utf-8", "replace")
    return out.split("\t")[0].strip() or "(无匹配)"


rules = GITIGNORE.read_text(encoding="utf-8").splitlines()
negations = [(i + 1, line[1:]) for i, line in enumerate(rules) if line.startswith("!")]

dead, alive, unresolvable = [], [], []
for lineno, pat in negations:
    probe = probe_path(pat)
    if probe is None:
        unresolvable.append((lineno, pat))
        continue
    if is_ignored(probe):
        dead.append((lineno, pat, probe, matching_rule(probe)))
    else:
        alive.append((lineno, pat, probe))

print(f".gitignore 共 {len(rules)} 行，否定规则 {len(negations)} 条")
print(f"  有效 {len(alive)} / 已失效 {len(dead)}"
      + (f" / 无法自动判定 {len(unresolvable)}" if unresolvable else ""))

if dead:
    print("\n=== 失效白名单：写了但救不回任何文件 ===")
    for lineno, pat, probe, rule in dead:
        print(f"  .gitignore:{lineno}  !{pat}")
        print(f"          探针 {probe} 仍被忽略 -> 命中 {rule}")
        print("          修法：把该 ! 规则移到文件末尾（全局规则之后）；"
              "若其父目录被排除，需先 ! 该目录本身")

if VERBOSE:
    print("\n=== 有效白名单 ===")
    for lineno, pat, probe in alive:
        print(f"  .gitignore:{lineno}  !{pat}   (探针 {probe} 可入库)")
    for lineno, pat in unresolvable:
        print(f"  .gitignore:{lineno}  !{pat}   (无法构造探针，请人工确认)")

sys.exit(1 if dead else 0)
