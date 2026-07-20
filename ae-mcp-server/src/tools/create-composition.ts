import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {
  name: z.string().describe('合成名称'),
  width: z.number().int().positive().default(1920).describe('合成宽度（像素）'),
  height: z.number().int().positive().default(1080).describe('合成高度（像素）'),
  duration: z.number().positive().default(10).describe('合成持续时间（秒）'),
  frameRate: z.number().positive().default(30).describe('帧速率（fps）'),
  pixelAspect: z.number().positive().default(1).describe('像素宽高比'),
};

export const createComposition = createTool(
  'create-composition',
  '创建新的 After Effects 合成',
  inputSchema,
  'createComposition'
);
