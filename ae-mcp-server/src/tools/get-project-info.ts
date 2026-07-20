import { z } from 'zod';
import { createTool } from './_base.js';

const inputSchema = {};

export const getProjectInfo = createTool(
  'get-project-info',
  '获取当前打开项目的详细信息，包括所有合成、图层、效果统计',
  inputSchema,
  'analyzeProject'
);
