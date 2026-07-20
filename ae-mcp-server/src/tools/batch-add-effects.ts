import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {
  compName: z.string().describe('目标合成名称'),
  layerIndex: z.number().int().positive().describe('图层索引（1-based）'),
  effects: z.array(
    z.object({
      effectMatchName: z.string().describe('效果匹配名称'),
      settings: z.record(z.any()).optional().describe('效果参数设置 {propertyName: value}'),
    })
  ).describe('要添加的效果数组'),
};

export const batchAddEffects = createTool(
  'batch-add-effects',
  '批量向图层添加多个效果',
  inputSchema,
  'batchAddEffects'
);
