import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {
  compName: z.string().describe('目标合成名称'),
  layerIndex: z.number().int().positive().describe('图层索引（1-based）'),
  blendMode: z.enum([
    'NONE',
    'DISSOLVE',
    'MULTIPLY',
    'SCREEN',
    'OVERLAY',
    'SOFT_LIGHT',
    'HARD_LIGHT',
    'ADD',
    'COLOR_DODGE',
    'COLOR_BURN',
    'DARKEN',
    'LIGHTEN',
    'DIFFERENCE',
    'EXCLUSION',
    'HUE',
    'SATURATION',
    'COLOR',
    'LUMINOSITY',
  ]).describe('混合模式'),
};

export const setBlendMode = createTool(
  'set-blend-mode',
  '设置图层的混合模式',
  inputSchema,
  'setBlendMode'
);
