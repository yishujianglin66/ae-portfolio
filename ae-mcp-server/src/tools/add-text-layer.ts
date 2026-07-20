import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {
  compName: z.string().describe('目标合成名称'),
  text: z.string().describe('文字内容'),
  name: z.string().optional().describe('图层名称（可选）'),
  fontSize: z.number().positive().optional().describe('字体大小，默认 72'),
  fillColor: z.array(z.number()).length(3).optional().describe('填充颜色 [r, g, b]，范围 0-1，默认白色'),
  fontFamily: z.string().optional().describe('字体名称，默认 Arial'),
  justification: z.enum(['left', 'center', 'right']).optional().describe('对齐方式，默认 center'),
  position: z.array(z.number()).length(2).optional().describe('位置 [x, y]，默认居中'),
};

export const addTextLayer = createTool(
  'add-text-layer',
  '在合成中添加文字图层',
  inputSchema,
  'addTextLayer'
);
