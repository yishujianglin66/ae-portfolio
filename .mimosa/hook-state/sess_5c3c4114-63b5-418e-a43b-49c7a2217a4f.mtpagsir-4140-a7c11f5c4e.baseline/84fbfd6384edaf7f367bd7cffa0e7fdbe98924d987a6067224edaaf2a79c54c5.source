import { createComposition } from './create-composition.js';
import { addTextLayer } from './add-text-layer.js';
import { addShapeLayer } from './add-shape-layer.js';
import { addAdjustmentLayer } from './add-adjustment-layer.js';
import { setBlendMode } from './set-blend-mode.js';
import { setTrackMatte } from './set-track-matte.js';
import { addEffectWithKeyframes } from './add-effect-with-keyframes.js';
import { batchAddEffects } from './batch-add-effects.js';
import { importFootage } from './import-footage.js';
import { runJsxScript } from './run-jsx-script.js';
import { getProjectInfo } from './get-project-info.js';
import { listCompositions } from './list-compositions.js';
// Phase 8 素材工具（Python 后端）
import { unifiedDownload } from './unified-download.js';
import { searchFreeMedia } from './search-free-media.js';
import { analyzeAudioFeatures } from './analyze-audio-features.js';
// Phase D 扩展工具
import { clipSearch } from './clip-search.js';
import { getConfig } from './get-config.js';
import { libraryStats } from './library-stats.js';
import type { ToolDefinition } from './_base.js';

export const tools: ToolDefinition[] = [
  createComposition,
  addTextLayer,
  addShapeLayer,
  addAdjustmentLayer,
  setBlendMode,
  setTrackMatte,
  addEffectWithKeyframes,
  batchAddEffects,
  importFootage,
  runJsxScript,
  getProjectInfo,
  listCompositions,
  // Phase 8 素材工具
  unifiedDownload as any,
  searchFreeMedia as any,
  analyzeAudioFeatures as any,
  // Phase D 扩展工具
  clipSearch,
  getConfig,
  libraryStats,
];

export * from './_base.js';
