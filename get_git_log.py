import subprocess
import os
import sys

os.chdir(r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault')

# Get commits from last 24 hours
print("=== COMMITS (last 24h, no merges) ===")
r = subprocess.run(
    ['git', 'log', '--since=24 hours ago', '--pretty=format:%h|%ai|%an|%s', '--no-merges', '-n', '100'],
    capture_output=True, text=True
)
print(r.stdout)
if r.stderr:
    print("STDERR:", r.stderr, file=sys.stderr)

print("\n=== MERGE COMMITS (last 24h) ===")
r2 = subprocess.run(
    ['git', 'log', '--since=24 hours ago', '--pretty=format:%h|%ai|%an|%s', '--merges', '-n', '50'],
    capture_output=True, text=True
)
print(r2.stdout)

print("\n=== GIT STATUS ===")
r3 = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True)
print(r3.stdout)

print("\n=== GIT DIFF --STAT (unstaged) ===")
r4 = subprocess.run(['git', 'diff', '--stat'], capture_output=True, text=True)
print(r4.stdout)
