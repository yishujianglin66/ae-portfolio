import { z } from 'zod';
import { execFile } from 'child_process';
import * as path from 'path';
import { handleBridgeResult } from './_base.js';
import type { ToolDefinition } from './_base.js';

const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
const PYTHON_CMD = process.env.AEK_PYTHON || 'python';
const SCRIPT_PATH = path.join(PROJECT_ROOT, '13-素材获取与搜索', '03-AI语义搜索', 'multimodal_retriever.py');

/**
 * CLIP 语义搜索工具
 * 通过 multimodal_retriever.py 进行多模态融合检索
 */
export const clipSearch: ToolDefinition = {
  name: 'clip-search',
  description: 'CLIP 语义搜索 - 使用自然语言描述搜索素材（如"夕阳下的海滩"、"紧张的背景音乐"）',
  inputSchema: {
    query: z.string().describe('搜索查询文本（自然语言描述）'),
    index_path: z.string().optional().describe('向量索引路径（可选）'),
    top_k: z.number().optional().describe('返回结果数量（默认 20）'),
    target_bpm: z.number().optional().describe('目标 BPM'),
    mood: z.string().optional().describe('情绪筛选'),
    genre: z.string().optional().describe('曲风筛选'),
  },
  handler: async (args: any) => {
    // multimodal_retriever.py 使用 action 协议
    const jsonInput = JSON.stringify({
      action: 'search',
      query: args.query,
      index_path: args.index_path || '',
      top_k: args.top_k || 20,
      target_bpm: args.target_bpm,
      mood: args.mood,
      genre: args.genre,
    });

    return new Promise((resolve) => {
      const proc = execFile(
        PYTHON_CMD,
        [SCRIPT_PATH, '--json-input', jsonInput],
        { timeout: 120000, cwd: PROJECT_ROOT, maxBuffer: 10 * 1024 * 1024 },
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
              isError: !result.success,
            });
          } catch {
            resolve({
              content: [{ type: 'text', text: JSON.stringify({ status: 'error', raw: stdout?.substring(0, 500) }) }],
              isError: true,
            });
          }
        }
      );
    });
  },
};
