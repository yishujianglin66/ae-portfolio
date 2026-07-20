import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {
  compName: z.string().describe('目标合成名称'),
  layerIndex: z.number().int().positive().describe('图层索引（1-based）'),
  effectMatchName: z.string().describe('效果匹配名称（如 ADBE Gaussian Blur 2）'),
  settings: z.record(z.any()).optional().describe('效果初始参数设置 {propertyName: value}'),
  keyframes: z.array(
    z.object({
      propertyName: z.string().describe('效果属性名称'),
      time: z.number().describe('关键帧时间（秒）'),
      value: z.any().describe('关键帧值'),
      easingType: z.enum(['linear', 'hold', 'easeIn', 'easeOut', 'easeInOut', 'bezier']).optional().describe('缓动类型'),
    })
  ).optional().describe('关键帧数组'),
};

export const addEffectWithKeyframes = createTool(
  'add-effect-with-keyframes',
  '向图层添加效果并设置关键帧动画',
  inputSchema,
  'addEffectWithKeyframes'
);
