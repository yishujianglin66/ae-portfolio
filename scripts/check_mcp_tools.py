import json
import urllib.request

url = "http://127.0.0.1:8765/mcp/tools"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

tools = data.get("tools", [])
print(f"Total MCP tools: {len(tools)}")
print()
for t in tools:
    name = t.get("name", "?")
    desc = t.get("description", "")[:80]
    print(f"  [{name}]")
    print(f"    {desc}")
    print()
