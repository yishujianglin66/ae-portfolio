import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {
  scriptContent: z.string().describe('要执行的 JSX 脚本内容'),
  scriptName: z.string().optional().describe('脚本名称，用于日志标识'),
  dryRun: z.boolean().optional().describe('干运行模式，仅检查语法不执行，默认 false'),
  timeout: z.number().int().positive().optional().describe('超时时间（毫秒），默认 10000'),
};

export const runJsxScript = createTool(
  'run-jsx-script',
  '执行任意 JSX 脚本（有安全限制，禁止系统调用和外部文件执行）',
  inputSchema,
  'executeAtomScript'
);
