import json
import os
import time

bridge_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'ae-mcp-bridge')

result_path = os.path.join(bridge_dir, 'ae_mcp_result.json')
cmd_path = os.path.join(bridge_dir, 'ae_command.json')

if os.path.exists(cmd_path):
    with open(cmd_path, 'r', encoding='utf-8') as f:
        cmd = json.load(f)
    print('=== 命令状态 ===')
    print('状态:', cmd.get('status'))
    print('命令:', cmd.get('command'))
    args = cmd.get('args', {})
    print('脚本名:', args.get('scriptName') if isinstance(args, dict) else 'N/A')
    print('时间:', cmd.get('timestamp'))

print()
if os.path.exists(result_path):
    mtime = os.path.getmtime(result_path)
    print('=== 结果 (修改时间: {}) ==='.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))))
    with open(result_path, 'r', encoding='utf-8') as f:
        result = f.read()
    print(result)
else:
    print('无结果文件')
