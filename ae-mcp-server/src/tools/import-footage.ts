import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {
  filePath: z.string().describe('素材文件的完整路径'),
  asSequence: z.boolean().optional().describe('是否作为序列导入，默认 false'),
  compName: z.string().optional().describe('目标合成名称（可选，指定后素材会添加到该合成）'),
  position: z.number().int().positive().optional().describe('添加到合成时的位置索引（1-based）'),
};

export const importFootage = createTool(
  'import-footage',
  '导入素材文件到项目，可选添加到指定合成',
  inputSchema,
  'importFootage'
);
