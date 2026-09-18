import json
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

cmd_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json'
res_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json'

# Send ping
cmd = {"command": "ping", "processed": False, "description": "bridge_test"}
if os.path.exists(res_path):
    os.remove(res_path)
json.dump(cmd, open(cmd_path, 'w', encoding='utf-8'), ensure_ascii=False)
print("Ping sent to AE bridge...")

# Wait for response
for i in range(10):
    time.sleep(3)
    if os.path.exists(res_path):
        with open(res_path, 'r', encoding='utf-8') as f:
            result = f.read()
        print(f"Got response after {(i+1)*3}s: {result[:200]}")
        break
    print(f"  Waiting... ({(i+1)*3}s)")
else:
    print("No response after 30s")
    log = os.popen('powershell -Command "Get-Content C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\.ae-mcp-bridge\\ae_listener_log.txt -Tail 5"').read()
    print(f"Log: {log.strip()}")
