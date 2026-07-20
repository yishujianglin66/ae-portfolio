import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {};

export const listCompositions = createTool(
  'list-compositions',
  '列出项目中所有合成的基本信息（名称、尺寸、时长、帧率、图层数）',
  inputSchema,
  'listCompositions'
);
