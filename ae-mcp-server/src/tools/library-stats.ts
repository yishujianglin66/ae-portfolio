import { z } from 'zod';
import { execFile } from 'child_process';
import * as path from 'path';
import type { ToolDefinition } from './_base.js';

const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
const PYTHON_CMD = process.env.AEK_PYTHON || 'python';
const SCRIPT_PATH = path.join(PROJECT_ROOT, 'media_metadata_db.py');

/**
 * 素材库统计工具
 * 通过 media_metadata_db.py 提供素材库统计和搜索
 */
export const libraryStats: ToolDefinition = {
  name: 'library-stats',
  description: '素材库统计与搜索 - 获取素材库统计信息、按条件搜索素材（支持类型/情绪/BPM/时长/平台筛选）',
  inputSchema: {
    action: z.enum(['stats', 'search', 'migrate']).describe('操作类型：stats=统计, search=搜索, migrate=从 JSON 迁移'),
    file_type: z.string().optional().describe('素材类型筛选（video/audio/image）'),
    mood: z.string().optional().describe('情绪筛选（energetic/calm/epic 等）'),
    genre: z.string().optional().describe('曲风筛选'),
    platform: z.string().optional().describe('来源平台（douyin/bilibili/youtube/pexels）'),
    min_duration: z.number().optional().describe('最小时长（秒）'),
    max_duration: z.number().optional().describe('最大时长（秒）'),
    min_bpm: z.number().optional().describe('最小 BPM'),
    max_bpm: z.number().optional().describe('最大 BPM'),
    query: z.string().optional().describe('全文搜索关键词'),
    limit: z.number().optional().describe('返回数量限制（默认 50）'),
    json_path: z.string().optional().describe('迁移源 JSON 文件路径'),
  },
  handler: async (args: any) => {
    const cliArgs: string[] = [SCRIPT_PATH];

    if (args.action === 'stats') {
      cliArgs.push('--stats');
    } else if (args.action === 'search') {
      if (args.query) {
        cliArgs.push('--search', args.query);
      } else {
        cliArgs.push('--list');
      }
    } else if (args.action === 'migrate') {
      if (!args.json_path) {
        return {
          content: [{ type: 'text', text: JSON.stringify({ status: 'error', message: 'migrate 操作需要 json_path 参数' }) }],
          isError: true,
        };
      }
      cliArgs.push('--migrate-from-json', args.json_path);
    }

    return new Promise((resolve) => {
      execFile(
        PYTHON_CMD,
        cliArgs,
        { timeout: 30000, cwd: PROJECT_ROOT },
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
            resolve({
              content: [{ type: 'text', text: stdout.trim() }],
            });
          }
        }
      );
    });
  },
};
