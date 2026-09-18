"""Get detailed info for each new DSH plugin."""
import json
import os
import subprocess
import sys

npm = r"C:\Program Files\nodejs\npm.cmd"

plugins = [
    "dsh-cc-tui",
    "dsh-milestone",
    "dsh-working-activity",
    "dsh-email",
    "dsh-feishu-bot",
    "dsh-lark-bot",
]

for name in plugins:
    try:
        result = subprocess.run(
            [npm, "view", name, "--json", "--registry=https://registry.npmmirror.com"],
            capture_output=True, timeout=30
        )
        raw = result.stdout
        try:
            d = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            d = json.loads(raw.decode("utf-16", errors="replace").strip())
        
        print(f"\n{'='*60}")
        print(f"  {name} v{d.get('version', '?')}")
        print(f"{'='*60}")
        print(f"  Desc: {d.get('description', 'N/A')}")
        print(f"  Keywords: {', '.join(d.get('keywords', []))}")
        print(f"  License: {d.get('license', 'N/A')}")
        author = d.get('author', {})
        if isinstance(author, dict):
            print(f"  Author: {author.get('name', 'N/A')}")
        else:
            print(f"  Author: {author}")
        
        # Check if it's a bundle or plugin type
        dsh_info = d.get('dsh', {})
        if dsh_info:
            print(f"  DSH bundle: {dsh_info.get('bundle', False)}")
            print(f"  DSH client: {'yes' if dsh_info.get('client') else 'no'}")
        else:
            print("  DSH type: unknown (no dsh field in package.json)")
            
        # Check dependencies
        deps = list(d.get('dependencies', {}).keys())
        if deps:
            print(f"  Dependencies ({len(deps)}): {', '.join(deps[:8])}")
    except Exception as e:
        print(f"\n{name}: ERROR - {e}")
