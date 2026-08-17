import json, os, time

CMD_FILE = r"C:\Users\Administrator\Documents\ae-mcp-bridge\ae_command.json"
RESULT_FILE = r"C:\Users\Administrator\Documents\ae-mcp-bridge\ae_mcp_result.json"

cmd = {
    "command": "executeAtomScript",
    "args": {
        "scriptContent": "alert('MCP Bridge test OK'); 'test_ok';"
    },
    "description": "test bridge",
    "status": "pending",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
}

with open(CMD_FILE, 'w', encoding='utf-8') as f:
    json.dump(cmd, f, ensure_ascii=False)

print("MCP测试命令已发送。请查看AE是否弹出 'MCP Bridge test OK' 弹窗。")
print("如果弹出，说明MCP Bridge正常工作，按OK后我可以继续自动执行工程重建。")
