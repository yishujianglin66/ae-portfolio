import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {
  compName: z.string().describe('目标合成名称'),
  shapeType: z.enum(['rectangle', 'ellipse', 'star', 'polygon']).describe('形状类型'),
  name: z.string().optional().describe('图层名称（可选）'),
  position: z.array(z.number()).length(2).optional().describe('位置 [x, y]，默认居中'),
  size: z.array(z.number()).length(2).optional().describe('尺寸 [宽, 高]，默认合成的 50%'),
  fillColor: z.array(z.number()).length(3).optional().describe('填充颜色 [r, g, b]，范围 0-1，默认白色'),
  strokeColor: z.array(z.number()).length(3).optional().describe('描边颜色 [r, g, b]，范围 0-1，默认黑色'),
  strokeWidth: z.number().min(0).optional().describe('描边宽度，默认 0（无描边）'),
};

export const addShapeLayer = createTool(
  'add-shape-layer',
  '在合成中添加形状图层（矩形/椭圆/星形/多边形）',
  inputSchema,
  'addShapeLayer'
);
