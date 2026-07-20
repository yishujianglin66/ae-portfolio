import { z } from 'zod';
import { createPythonTool, PythonToolDefinition } from './_python_base.js';

const analyzeSchema = {
  audio_path: z.string().describe('音频文件路径'),
};

export const analyzeAudioFeatures: PythonToolDefinition = createPythonTool(
  'analyze-audio-features',
  '音频深度分析：BPM/节拍/调性/情绪/曲风/频谱特征（librosa 引擎，超时自动降级到 FFprobe）',
  analyzeSchema,
  'audio-analyzer.py',
  'analyze_audio'
);
