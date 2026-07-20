import { z } from 'zod';
import { createPythonTool, PythonToolDefinition } from './_python_base.js';

const searchSchema = {
  query: z.string().describe('搜索关键词'),
  media_type: z.enum(['video', 'image', 'all']).optional().describe('媒体类型，默认 all'),
  max_results: z.number().int().positive().optional().describe('每个平台最大结果数，默认 5'),
};

export const searchFreeMedia: PythonToolDefinition = createPythonTool(
  'search-free-media',
  '免费素材搜索：跨 Pixabay/Pexels/Jamendo 三平台并行搜索免费视频、图片、音乐',
  searchSchema,
  '13-素材获取与搜索/02-免费素材API/unified_search.py',
  'search_all'
);
