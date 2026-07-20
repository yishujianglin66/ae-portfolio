import { z } from 'zod';
import { execFile } from 'child_process';
import * as path from 'path';
import { handleBridgeResult } from './_base.js';

export interface PythonToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, z.ZodType<any>>;
  handler: (args: any) => Promise<any>;
}

// 项目根目录
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
const PYTHON_CMD = process.env.AEK_PYTHON || 'python';
const PYTHON_TIMEOUT = parseInt(process.env.AEK_PYTHON_TIMEOUT || '60000', 10);

/**
 * 创建一个调用 Python 脚本的 MCP 工具。
 * Python 脚本需支持 --json-input 协议。
 */
export function createPythonTool(
  name: string,
  description: string,
  inputSchema: Record<string, z.ZodType<any>>,
  scriptPath: string,
  funcName: string
): PythonToolDefinition {
  return {
    name,
    description,
    inputSchema,
    handler: async (args: any) => {
      const fullScriptPath = path.resolve(PROJECT_ROOT, scriptPath);
      const jsonInput = JSON.stringify({ func: funcName, params: args });

      return new Promise((resolve) => {
        const proc = execFile(
          PYTHON_CMD,
          [fullScriptPath, '--json-input', jsonInput],
          {
            timeout: PYTHON_TIMEOUT,
            cwd: PROJECT_ROOT,
            env: { ...process.env },
            maxBuffer: 10 * 1024 * 1024,
          },
          (error, stdout, stderr) => {
            if (error) {
              resolve({
                content: [
                  {
                    type: 'text',
                    text: JSON.stringify({
                      status: 'error',
                      errorCode: 'PYTHON_ERROR',
                      message: `Python 脚本执行失败: ${error.message}`,
                      stderr: stderr?.substring(0, 500),
                    }, null, 2),
                  },
                ],
                isError: true,
              });
              return;
            }

            try {
              const result = JSON.parse(stdout.trim());
              resolve(handleBridgeResult(result));
            } catch (parseError) {
              resolve({
                content: [
                  {
                    type: 'text',
                    text: JSON.stringify({
                      status: 'error',
                      errorCode: 'PARSE_ERROR',
                      message: 'Python 输出解析失败',
                      raw_output: stdout?.substring(0, 1000),
                    }, null, 2),
                  },
                ],
                isError: true,
              });
            }
          }
        );
      });
    },
  };
}
