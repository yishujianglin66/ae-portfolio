"""Search npm for dsh- plugins and output a formatted table."""
import json
import os
import subprocess
import sys

npm_path = r"C:\Program Files\nodejs\npm.cmd"
result = subprocess.run(
    [npm_path, "search", "dsh-", "--json", "--registry=https://registry.npmmirror.com"],
    capture_output=True, timeout=120
)

raw = result.stdout
try:
    data = json.loads(raw.decode("utf-8"))
except UnicodeDecodeError:
    data = json.loads(raw.decode("utf-16", errors="replace").strip())

# Already installed
installed = {
    "dsh-api-balance", "dsh-plugin-doc-reader", "dsh-safe-delete",
    "dsh-undo", "dsh-better-sidebar", "dsh-token-cost",
    "dsh-cloudflare-browser-run", "dsh-nocturne-memory",
}

# Filter to dsh- prefixed packages, exclude deepseek-ai org packages (core)
packages = []
for p in data:
    name = p.get("name", "")
    if not name.startswith("dsh-"):
        continue
    if name.startswith("@deepseek-ai/"):
        continue
    if name in installed:
        continue
    packages.append(p)

# Sort by name
packages.sort(key=lambda x: x.get("name", ""))

print(f"Total dsh- plugins on npm: {len(data)}")
print(f"Already installed: {len(installed)}")
print(f"New/available: {len(packages)}")
print()
print(f"{'Package':<45} {'Version':<12} {'Description'}")
print("-" * 120)
for p in packages:
    name = p.get("name", "unknown")
    version = p.get("version", "?")
    desc = (p.get("description") or "")[:70]
    print(f"{name:<45} {version:<12} {desc}")
