import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {
  compName: z.string().describe('目标合成名称'),
  name: z.string().optional().describe('调整图层名称，默认 "Adjustment Layer"'),
  position: z.number().int().optional().describe('插入位置索引（1-based），默认最顶层'),
};

export const addAdjustmentLayer = createTool(
  'add-adjustment-layer',
  '在合成中添加调整图层',
  inputSchema,
  'addAdjustmentLayer'
);
