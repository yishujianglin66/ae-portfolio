import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {
  compName: z.string().describe('目标合成名称'),
  layerIndex: z.number().int().positive().describe('图层索引（1-based）'),
  matteType: z.enum([
    'NO_TRACK_MATTE',
    'ALPHA_TRACK_MATTE',
    'ALPHA_INVERTED_TRACK_MATTE',
    'LUMA_TRACK_MATTE',
    'LUMA_INVERTED_TRACK_MATTE',
  ]).describe('轨道遮罩类型'),
};

export const setTrackMatte = createTool(
  'set-track-matte',
  '设置图层的轨道遮罩类型',
  inputSchema,
  'setTrackMatte'
);
