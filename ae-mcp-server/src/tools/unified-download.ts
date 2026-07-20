import { z } from 'zod';
import { createPythonTool, PythonToolDefinition } from './_python_base.js';

const downloadSchema = {
  url: z.string().describe('视频/音频 URL（支持抖音、B站、YouTube 等）'),
  type: z.enum(['video', 'audio']).optional().describe('下载类型，默认 video'),
  output_dir: z.string().optional().describe('输出目录（可选，使用配置默认值）'),
};

export const unifiedDownload: PythonToolDefinition = createPythonTool(
  'unified-download',
  '统一下载器：从 URL 下载视频或音频，自动识别平台（抖音/B站/YouTube/快手等）',
  downloadSchema,
  '13-素材获取与搜索/01-下载器/unified_downloader.py',
  'download'
);
