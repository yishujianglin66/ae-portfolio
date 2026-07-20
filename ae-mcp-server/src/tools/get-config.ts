import { z } from 'zod';
import { execFile } from 'child_process';
import * as path from 'path';
import type { ToolDefinition } from './_base.js';

const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
const PYTHON_CMD = process.env.AEK_PYTHON || 'python';
const SCRIPT_PATH = path.join(PROJECT_ROOT, 'config', 'config_manager.py');

/**
 * 获取配置工具
 * 通过 config_manager.py CLI 读取项目配置
 */
export const getConfig: ToolDefinition = {
  name: 'get-config',
  description: '获取项目配置 - 读取 media-config.json 中的配置项（目录路径、工具路径、平台设置等）',
  inputSchema: {
    key: z.string().optional().describe('配置键路径（如 "directories.video_library"、"tools.ffmpeg"），不填则返回全部配置'),
    action: z.enum(['get', 'list', 'ensure-dirs']).optional().describe('操作类型：get=获取配置, list=列出全部, ensure-dirs=创建所有目录'),
  },
  handler: async (args: any) => {
    const cliArgs: string[] = [SCRIPT_PATH];

    if (args.action === 'list' || (!args.key && !args.action)) {
      cliArgs.push('--list');
    } else if (args.action === 'ensure-dirs') {
      cliArgs.push('--ensure-dirs');
    } else if (args.key) {
      cliArgs.push('--get', args.key);
    }

    return new Promise((resolve) => {
      execFile(
        PYTHON_CMD,
        cliArgs,
        { timeout: 10000, cwd: PROJECT_ROOT },
        (error, stdout, stderr) => {
          if (error) {
            resolve({
              content: [{ type: 'text', text: JSON.stringify({ status: 'error', message: error.message }) }],
              isError: true,
            });
            return;
          }
          try {
            const result = JSON.parse(stdout.trim());
            resolve({
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            });
          } catch {
            // 非 JSON 输出（如 --get 返回纯字符串）
            resolve({
              content: [{ type: 'text', text: stdout.trim() }],
            });
          }
        }
      );
    });
  },
};
