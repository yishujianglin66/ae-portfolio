import { z } from "zod";
import { spawn } from "child_process";
import * as path from "path";
import * as fs from "fs";

const PYTHON = process.env.AEKV_PYTHON || "python";
const SPAWN_TIMEOUT_MS = 120_000;

// ============================================================================
// 进程沙箱：子进程执行安全包装（脚本白名单 + 根目录包含 + 固定 cwd + 超时）
// 用于阻断：路径穿越执行任意脚本、工作目录逃逸、进程无限挂起
// ============================================================================

// 可执行脚本白名单（相对项目根的固定路径）。不在白名单内的脚本一律拒绝执行。
const PY_SCRIPT_ALLOWLIST: Record<string, string> = {
  "media-search": "scripts/media-search.py",
  "media-fetcher": "scripts/media-fetcher.py",
  "ffmpeg-toolkit": "scripts/ffmpeg-toolkit.py",
  "media-manager": "scripts/media-manager.py",
  "audio-analyzer": "audio-analyzer.py",
  "video-effect-analyzer": "vrs/video-effect-analyzer.py",
};

// 从当前模块位置向上探测项目根（以 scripts/media-search.py 存在为锚点）
function resolveProjectRoot(fromDir: string): string {
  let dir = path.resolve(fromDir);
  for (;;) {
    if (fs.existsSync(path.join(dir, "scripts", "media-search.py"))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return path.resolve(fromDir, "..");
    dir = parent;
  }
}

const PROJECT_ROOT = resolveProjectRoot(__dirname);

function resolveScriptPath(scriptName: string): string | null {
  const rel = PY_SCRIPT_ALLOWLIST[scriptName];
  if (!rel) return null;
  const abs = path.resolve(PROJECT_ROOT, rel);
  // 解析后的真实路径必须落在项目根内，防止目录穿越
  if (abs !== PROJECT_ROOT && !abs.startsWith(PROJECT_ROOT + path.sep)) return null;
  return fs.existsSync(abs) ? abs : null;
}

/**
 * 沙箱化的 Python 子进程执行：
 * - 脚本名必须在白名单内且真实路径位于项目根内
 * - 固定 cwd 为项目根，不继承调用方工作目录
 * - 统一超时，超时即 kill，防止子进程无限挂起
 * - 不使用 shell，避免命令注入
 */
function safeSpawnPython(
  scriptName: string,
  args: string[] = [],
  opts: { jsonInput?: string; timeoutMs?: number } = {},
): Promise<string> {
  const scriptPath = resolveScriptPath(scriptName);
  if (!scriptPath) {
    return Promise.reject(new Error(`[sandbox] 脚本不在白名单或不存在: ${scriptName}`));
  }
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON, [scriptPath, ...args], {
      cwd: PROJECT_ROOT,
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      windowsHide: true,
    });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`[sandbox] ${scriptName} 执行超时 (${opts.timeoutMs ?? SPAWN_TIMEOUT_MS}ms)`));
    }, opts.timeoutMs ?? SPAWN_TIMEOUT_MS);
    child.stdout.on("data", (data) => { stdout += data.toString(); });
    child.stderr.on("data", (data) => { stderr += data.toString(); });
    child.on("error", (err) => { clearTimeout(timer); reject(err); });
    child.on("exit", (code) => {
      clearTimeout(timer);
      if (code === 0) {
        resolve(stdout);
      } else {
        reject(new Error(`Python script failed (code ${code}): ${stderr || stdout}`));
      }
    });
    if (opts.jsonInput) {
      child.stdin.write(opts.jsonInput);
      child.stdin.end();
    }
  });
}

async function runPythonScript(scriptName: string, args: string[] = []): Promise<string> {
  return safeSpawnPython(scriptName, args);
}

async function runPythonWithJSON(scriptName: string, funcName: string, params: Record<string, any>): Promise<any> {
  const input = JSON.stringify({ func: funcName, params });
  try {
    const stdout = await safeSpawnPython(scriptName, ["--json-input"], { jsonInput: input });
    return JSON.parse(stdout);
  } catch (e) {
    throw e;
  }
}

export function registerMediaTools(server: any) {
    server.tool(
        "search-media",
        "搜索本地素材库或在线视频平台（抖音/B站/YouTube/快手），支持关键词、情绪、BPM等多维度搜索",
        {
            query: z.string().describe("搜索关键词或提示词"),
            type: z.enum(["video", "audio", "image"]).optional().describe("素材类型过滤"),
            platform: z.enum(["youtube", "bilibili", "douyin", "kuaishou", "local"]).optional().describe("搜索平台"),
            mood: z.string().optional().describe("情绪关键词: excited/calm/happy/sad/epic/mysterious"),
            bpm: z.number().optional().describe("目标BPM值"),
            minDuration: z.number().optional().describe("最小时长（秒）"),
            maxDuration: z.number().optional().describe("最大时长（秒）"),
            maxResults: z.number().int().min(1).max(50).optional().default(10)
        },
        async ({ query, type, platform, mood, bpm, minDuration, maxDuration, maxResults }) => {
            try {
                const params: Record<string, any> = {
                    query,
                    max_results: maxResults
                };
                
                if (type) params.type = type;
                if (platform) params.platform = platform;
                if (mood) params.mood = mood;
                if (bpm) params.bpm = bpm;
                if (minDuration) params.min_duration = minDuration;
                if (maxDuration) params.max_duration = maxDuration;
                
                let results: any[];
                
                if (platform === "local" || !platform) {
                    results = await runPythonWithJSON("media-search", "search_by_keyword", params);
                } else {
                    results = await runPythonWithJSON("media-search", "search_online", params);
                }
                
                if (!Array.isArray(results)) {
                    results = [results];
                }
                
                const summary = results.map((r, i) => {
                    const info = [];
                    info.push(`[${i + 1}] ${r.title || r.name || "未知"}`);
                    if (r.platform) info.push(`   平台: ${r.platform}`);
                    if (r.duration) info.push(`   时长: ${r.duration.toFixed(1)}s`);
                    if (r.url) info.push(`   链接: ${r.url}`);
                    if (r.view_count) info.push(`   播放: ${r.view_count.toLocaleString()}`);
                    if (r.similarity_score) info.push(`   匹配度: ${(r.similarity_score * 100).toFixed(0)}%`);
                    if (r.audio_features) {
                        const af = r.audio_features;
                        if (af.bpm) info.push(`   BPM: ${af.bpm}`);
                        if (af.mood) info.push(`   情绪: ${af.mood}`);
                    }
                    return info.join("\n");
                });
                
                return {
                    content: [{
                        type: "text",
                        text: `搜索结果（共 ${results.length} 条）:\n\n${summary.join("\n\n")}`
                    }]
                };
                
            } catch (e) {
                return {
                    content: [{
                        type: "text",
                        text: `❌ 搜索失败: ${String(e)}`
                    }],
                    isError: true
                };
            }
        }
    );

    server.tool(
        "download-media",
        "从 URL 下载视频或音频（支持抖音/B站/YouTube等1000+网站）",
        {
            url: z.string().describe("媒体 URL"),
            type: z.enum(["video", "audio"]).optional().default("video"),
            outputDir: z.string().optional().describe("自定义输出目录"),
            quality: z.enum(["best", "medium", "worst"]).optional().default("best")
        },
        async ({ url, type, outputDir, quality }) => {
            try {
                const params: Record<string, any> = {
                    url,
                    audio_only: type === "audio",
                    quality: quality || "best"
                };
                
                if (outputDir) params.output_dir = outputDir;
                
                const result = await runPythonWithJSON("media-fetcher", "download_video", params);
                
                if (result.success) {
                    const files = result.files || [];
                    const fileList = files.map(f => `- ${f.name} (${(f.size / 1024 / 1024).toFixed(2)} MB)`).join("\n");
                    
                    return {
                        content: [{
                            type: "text",
                            text: `✅ 下载成功！\n\n📂 输出目录: ${result.output_dir}\n\n下载文件:\n${fileList}`
                        }]
                    };
                } else {
                    return {
                        content: [{
                            type: "text",
                            text: `❌ 下载失败: ${result.error || "未知错误"}`
                        }],
                        isError: true
                    };
                }
                
            } catch (e) {
                return {
                    content: [{
                        type: "text",
                        text: `❌ 下载失败: ${String(e)}`
                    }],
                    isError: true
                };
            }
        }
    );

    server.tool(
        "extract-audio",
        "从视频文件中提取音频，支持 MP3/WAV/M4A/FLAC 格式",
        {
            inputFile: z.string().describe("视频文件路径"),
            outputFile: z.string().optional().describe("输出文件路径"),
            format: z.enum(["mp3", "wav", "m4a", "flac"]).optional().default("mp3"),
            bitrate: z.string().optional().describe("比特率，如 '192k', '320k'")
        },
        async ({ inputFile, outputFile, format, bitrate }) => {
            try {
                const params: Record<string, any> = {
                    input_file: inputFile,
                    format: format || "mp3"
                };
                
                if (outputFile) params.output_file = outputFile;
                if (bitrate) params.bitrate = bitrate;
                
                const result = await runPythonWithJSON("ffmpeg-toolkit", "extract_audio", params);
                
                if (result.success) {
                    return {
                        content: [{
                            type: "text",
                            text: `✅ 音频提取成功！\n\n📥 输入: ${result.input_file}\n📤 输出: ${result.output_file}\n🎵 格式: ${result.format}\n📊 大小: ${(result.size / 1024 / 1024).toFixed(2)} MB`
                        }]
                    };
                } else {
                    return {
                        content: [{
                            type: "text",
                            text: `❌ 提取失败: ${result.error || "未知错误"}`
                        }],
                        isError: true
                    };
                }
                
            } catch (e) {
                return {
                    content: [{
                        type: "text",
                        text: `❌ 提取失败: ${String(e)}`
                    }],
                    isError: true
                };
            }
        }
    );

    server.tool(
        "clip-media",
        "截取视频或音频片段，精确到毫秒级",
        {
            inputFile: z.string().describe("源文件路径"),
            startTime: z.number().describe("开始时间（秒）"),
            duration: z.number().positive().describe("截取时长（秒）"),
            outputFile: z.string().optional().describe("输出文件路径"),
            preserveAudio: z.boolean().optional().default(true).describe("是否保留音频（视频）"),
            type: z.enum(["video", "audio"]).optional().describe("媒体类型")
        },
        async ({ inputFile, startTime, duration, outputFile, preserveAudio, type }) => {
            try {
                const funcName = type === "audio" ? "extract_audio_segment" : "extract_video_segment";
                const params: Record<string, any> = {
                    input_file: inputFile,
                    start_time: startTime,
                    duration: duration
                };
                
                if (outputFile) params.output_file = outputFile;
                if (type !== "audio") params.preserve_audio = preserveAudio;
                
                const result = await runPythonWithJSON("ffmpeg-toolkit", funcName, params);
                
                if (result.success) {
                    return {
                        content: [{
                            type: "text",
                            text: `✅ 片段截取成功！\n\n📥 输入: ${result.input_file}\n📤 输出: ${result.output_file}\n⏱️ 起始: ${result.start_time.toFixed(2)}s\n⏱️ 时长: ${result.duration.toFixed(2)}s\n📊 大小: ${(result.size / 1024 / 1024).toFixed(2)} MB`
                        }]
                    };
                } else {
                    return {
                        content: [{
                            type: "text",
                            text: `❌ 截取失败: ${result.error || "未知错误"}`
                        }],
                        isError: true
                    };
                }
                
            } catch (e) {
                return {
                    content: [{
                        type: "text",
                        text: `❌ 截取失败: ${String(e)}`
                    }],
                    isError: true
                };
            }
        }
    );

    server.tool(
        "analyze-audio",
        "分析音频文件，提取BPM、情绪、曲风、音调等特征",
        {
            audioPath: z.string().describe("音频文件路径")
        },
        async ({ audioPath }) => {
            try {
                const result = await runPythonWithJSON("audio-analyzer", "analyze_audio", { audio_path: audioPath });
                
                if (result.success) {
                    const features = result.features;
                    const beats = result.beat_count || 0;
                    
                    return {
                        content: [{
                            type: "text",
                            text: `✅ 音频分析完成！\n\n🎵 基本信息:\n   - BPM: ${features.bpm}\n   - 时长: ${features.duration.toFixed(2)}s\n   - 节拍数: ${beats}\n\n🎹 音调信息:\n   - 调性: ${features.key} ${features.mode}\n\n🎭 情绪分析:\n   - 情绪: ${features.mood}\n   - 置信度: ${(features.mood_score * 100).toFixed(0)}%\n\n🎸 曲风分类:\n   - 曲风: ${features.genre}\n\n📊 声学特征:\n   - 能量: ${features.energy.toFixed(3)}\n   - 响度: ${features.loudness.toFixed(2)} dB\n   - 频谱重心: ${features.spectral_centroid.toFixed(0)} Hz`
                        }]
                    };
                } else {
                    return {
                        content: [{
                            type: "text",
                            text: `❌ 分析失败: ${result.error || "未知错误"}`
                        }],
                        isError: true
                    };
                }
                
            } catch (e) {
                return {
                    content: [{
                        type: "text",
                        text: `❌ 分析失败: ${String(e)}`
                    }],
                    isError: true
                };
            }
        }
    );

    server.tool(
        "find-bgm",
        "根据视频时长、情绪、BPM智能匹配背景音乐",
        {
            videoDuration: z.number().positive().describe("视频时长（秒）"),
            mood: z.string().optional().describe("目标情绪: excited/calm/happy/sad/epic/mysterious"),
            bpm: z.number().optional().describe("目标BPM值"),
            maxResults: z.number().int().min(1).max(10).optional().default(5)
        },
        async ({ videoDuration, mood, bpm, maxResults }) => {
            try {
                const result = await runPythonWithJSON("media-search", "find_bgm_for_video", {
                    video_duration: videoDuration,
                    mood: mood,
                    target_bpm: bpm,
                    max_results: maxResults
                });
                
                if (!Array.isArray(result)) {
                    return {
                        content: [{
                            type: "text",
                            text: "❌ 未找到匹配的背景音乐"
                        }],
                        isError: true
                    };
                }
                
                const matches = result.map((m, i) => {
                    const info = [];
                    info.push(`[${i + 1}] ${m.name}`);
                    info.push(`   匹配度: ${(m.similarity_score * 100).toFixed(0)}%`);
                    info.push(`   时长: ${m.duration.toFixed(2)}s`);
                    if (m.audio_features) {
                        info.push(`   BPM: ${m.audio_features.bpm}`);
                        info.push(`   情绪: ${m.audio_features.mood}`);
                        info.push(`   曲风: ${m.audio_features.genre}`);
                    }
                    info.push(`   路径: ${m.path}`);
                    return info.join("\n");
                });
                
                return {
                    content: [{
                        type: "text",
                        text: `🎵 背景音乐推荐（共 ${result.length} 条）\n\n目标: ${videoDuration.toFixed(2)}s ${mood ? `| 情绪:${mood} ` : ""}${bpm ? `| BPM:${bpm}` : ""}\n\n${matches.join("\n\n")}`
                    }]
                };
                
            } catch (e) {
                return {
                    content: [{
                        type: "text",
                        text: `❌ 匹配失败: ${String(e)}`
                    }],
                    isError: true
                };
            }
        }
    );

    server.tool(
        "get-media-info",
        "获取媒体文件详细信息（时长、分辨率、编码等）",
        {
            filePath: z.string().describe("媒体文件路径")
        },
        async ({ filePath }) => {
            try {
                const result = await runPythonWithJSON("ffmpeg-toolkit", "get_media_info", { input_file: filePath });
                
                if (result.success) {
                    const info = result.info;
                    const format = info.format || {};
                    const streams = info.streams || [];
                    
                    const streamInfo = streams.map((s: any, i: number) => {
                        const codecType = s.codec_type || "unknown";
                        const codecName = s.codec_name || "unknown";
                        const details = [];
                        
                        if (codecType === "video") {
                            details.push(`分辨率: ${s.width}x${s.height}`);
                            details.push(`帧率: ${s.r_frame_rate}`);
                            details.push(`像素格式: ${s.pix_fmt}`);
                        } else if (codecType === "audio") {
                            details.push(`采样率: ${s.sample_rate} Hz`);
                            details.push(`声道数: ${s.channels}`);
                            details.push(`采样格式: ${s.sample_fmt}`);
                        }
                        
                        return `流 ${i + 1} [${codecType}]: ${codecName}\n   ${details.join("\n   ")}`;
                    });
                    
                    return {
                        content: [{
                            type: "text",
                            text: `✅ 媒体信息:\n\n📄 文件信息:\n   - 时长: ${result.duration.toFixed(2)}s\n   - 大小: ${(result.size / 1024 / 1024).toFixed(2)} MB\n   - 格式: ${format.format_name || "unknown"}\n\n🔊 流信息:\n${streamInfo.join("\n\n")}`
                        }]
                    };
                } else {
                    return {
                        content: [{
                            type: "text",
                            text: `❌ 获取失败: ${result.error || "未知错误"}`
                        }],
                        isError: true
                    };
                }
                
            } catch (e) {
                return {
                    content: [{
                        type: "text",
                        text: `❌ 获取失败: ${String(e)}`
                    }],
                    isError: true
                };
            }
        }
    );

    server.tool(
        "library-stats",
        "获取本地素材库统计信息（视频/音频/图片数量、情绪分布等）",
        {},
        async () => {
            try {
                const result = await runPythonWithJSON("media-search", "get_library_stats", {});
                
                const moodDist = result.mood_distribution || {};
                const genreDist = result.genre_distribution || {};
                
                const moodList = Object.entries(moodDist).map(([k, v]) => `   - ${k}: ${v}`).join("\n");
                const genreList = Object.entries(genreDist).map(([k, v]) => `   - ${k}: ${v}`).join("\n");
                
                return {
                    content: [{
                        type: "text",
                        text: `📊 素材库统计:\n\n📦 总量:\n   - 总计: ${result.total} 个文件\n   - 视频: ${result.videos} 个\n   - 音频: ${result.audios} 个\n   - 图片: ${result.images} 个\n   - 总大小: ${result.total_size_human}\n   - 平均时长: ${result.avg_duration.toFixed(2)}s\n\n🎭 情绪分布:\n${moodList || "   - 暂无数据"}\n\n🎸 曲风分布:\n${genreList || "   - 暂无数据"}`
                    }]
                };
                
            } catch (e) {
                return {
                    content: [{
                        type: "text",
                        text: `❌ 获取失败: ${String(e)}`
                    }],
                    isError: true
                };
            }
        }
    );

    // ============================================================
    //  视频效果逆向分析
    // ============================================================
    server.tool(
        "analyze-video-effect",
        "分析参考视频的剪辑效果，提取AE可执行的参数表（场景/转场/调色/运动/特效）",
        {
            video_path: z.string().describe("视频文件路径"),
            detail_level: z.enum(["quick", "standard", "full"]).optional().default("standard").describe("分析精度: quick(快速)/standard(标准)/full(完整)")
        },
        async ({ video_path, detail_level }: { video_path: string; detail_level?: string }) => {
            try {
                const result = await runPythonWithJSON("video-effect-analyzer", "analyze_video", { 
                    video_path, detail_level: detail_level || "standard" 
                });
                
                if (!result.success) {
                    return { content: [{ type: "text", text: `❌ 分析失败: ${result.error}` }], isError: true };
                }
                
                const basic = result.basic_info || {};
                const color = result.color_grading || {};
                const motion = result.motion_analysis || {};
                const rhythm = result.rhythm_analysis || {};
                const vfx = result.visual_effects || {};
                const prompts = result.prompts || {};
                const aeParams = result.ae_parameters || {};
                
                const sceneList = (result.scenes || []).slice(0, 10).map((s: any) => 
                    `   ${s.scene_idx}. ${s.start_time}s-${s.end_time}s (${s.duration}s)`
                ).join("\n");
                
                const transList = (result.transitions || []).slice(0, 10).map((t: any) =>
                    `   - ${t.time_sec}s: ${t.type} (${(t.confidence * 100).toFixed(0)}%) → ${t.ae_effect || ""}`
                ).join("\n");
                
                const effectList = (vfx.detected_effects || []).map((e: any) =>
                    `   - ${e.name} (${(e.confidence * 100).toFixed(0)}%) → ${e.ae_effect}`
                ).join("\n");
                
                return {
                    content: [{
                        type: "text",
                        text: `🎬 视频效果分析报告\n\n` +
                              `📹 基础信息:\n` +
                              `   - 分辨率: ${basic.width}x${basic.height} (${basic.resolution_label})\n` +
                              `   - 帧率: ${basic.fps}fps\n` +
                              `   - 时长: ${basic.duration}s\n\n` +
                              `🎨 色彩调色:\n` +
                              `   - 调色风格: ${color.grading_style}\n` +
                              `   - 色温: ${color.color_temperature} (~${color.temperature_kelvin}K)\n` +
                              `   - 饱和度: ${color.saturation_style} (${color.avg_saturation})\n` +
                              `   - 对比度: ${color.contrast_style} (${color.avg_contrast})\n\n` +
                              `🎥 运动/速度:\n` +
                              `   - 运动风格: ${motion.motion_style}\n` +
                              `   - 相机运动: ${motion.camera_motion}\n` +
                              `   - 速度变化: ${motion.speed_changes?.length || 0}处\n\n` +
                              `✂️ 剪辑节奏:\n` +
                              `   - 节奏: ${rhythm.rhythm}\n` +
                              `   - 平均镜头时长: ${rhythm.avg_shot_duration}s\n` +
                              `   - 场景数: ${result.scene_count}\n\n` +
                              `🎬 场景列表:\n${sceneList || "   - 无场景检测"}\n\n` +
                              `🔄 转场效果:\n${transList || "   - 无明显转场"}\n\n` +
                              `✨ 视觉效果:\n${effectList || "   - 无明显特效"}\n\n` +
                              `📝 风格描述:\n${prompts.style_description || ""}\n\n` +
                              `🔧 MCP提示词:\n${prompts.mcp_prompt || ""}`
                    }]
                };
                
            } catch (e) {
                return {
                    content: [{ type: "text", text: `❌ 分析失败: ${String(e)}` }],
                    isError: true
                };
            }
        }
    );

    // ============================================================
    //  从URL提取BGM
    // ============================================================
    server.tool(
        "extract-and-import-bgm",
        "从视频链接提取BGM（抖音/B站/YouTube），可选截取片段，自动导入AE",
        {
            url: z.string().describe("视频链接（抖音/B站/YouTube等）"),
            format: z.enum(["mp3", "wav", "m4a"]).optional().default("mp3").describe("输出音频格式"),
            clip_start: z.number().optional().describe("截取起始时间（秒），不填则提取完整音频"),
            clip_duration: z.number().optional().describe("截取时长（秒），不填则提取完整音频"),
            import_to_ae: z.boolean().optional().default(true).describe("是否自动导入AE")
        },
        async ({ url, format, clip_start, clip_duration, import_to_ae }: { 
            url: string; format?: string; clip_start?: number; clip_duration?: number; import_to_ae?: boolean 
        }) => {
            try {
                const params: Record<string, any> = { url, format: format || "mp3" };
                if (clip_start !== undefined) params.clip_start = clip_start;
                if (clip_duration !== undefined) params.clip_duration = clip_duration;
                
                const result = await runPythonWithJSON("media-manager", "extract_bgm_from_url", params);
                
                if (!result.success) {
                    return { content: [{ type: "text", text: `❌ BGM提取失败: ${result.error}` }], isError: true };
                }
                
                const steps = (result.steps || []).map((s: any) => 
                    `${s.success ? "✅" : "❌"} ${s.description}`
                ).join("\n");
                
                return {
                    content: [{
                        type: "text",
                        text: `🎵 BGM提取成功!\n\n` +
                              `执行步骤:\n${steps}\n\n` +
                              `音频文件: ${result.audio_file || "未知"}\n\n` +
                              (import_to_ae ? `💡 提示: 可以使用 executeAtomScript 将音频导入AE合成` : "")
                    }]
                };
                
            } catch (e) {
                return {
                    content: [{ type: "text", text: `❌ BGM提取失败: ${String(e)}` }],
                    isError: true
                };
            }
        }
    );

    // ============================================================
    //  从URL分析参考视频效果
    // ============================================================
    server.tool(
        "analyze-video-from-url",
        "从URL下载参考视频并分析剪辑效果，生成AE参数和提示词",
        {
            url: z.string().describe("参考视频链接"),
            detail_level: z.enum(["quick", "standard", "full"]).optional().default("standard").describe("分析精度")
        },
        async ({ url, detail_level }: { url: string; detail_level?: string }) => {
            try {
                const result = await runPythonWithJSON("media-manager", "analyze_video_from_url", { 
                    url, detail_level: detail_level || "standard" 
                });
                
                if (!result.success) {
                    return { content: [{ type: "text", text: `❌ 分析失败: ${result.error}` }], isError: true };
                }
                
                const analysis = result.analysis || {};
                const color = analysis.color_grading || {};
                const motion = analysis.motion_analysis || {};
                const rhythm = analysis.rhythm_analysis || {};
                const prompts = analysis.prompts || {};
                
                return {
                    content: [{
                        type: "text",
                        text: `🎬 参考视频分析完成!\n\n` +
                              `🎨 调色风格: ${color.grading_style || "标准"}\n` +
                              `   色温: ${color.color_temperature || "中性"} | 饱和度: ${color.saturation_style || "中等"} | 对比度: ${color.contrast_style || "中等"}\n\n` +
                              `🎥 运动: ${motion.motion_style || "中等动态"} | ${motion.camera_motion || "固定"}\n\n` +
                              `✂️ 节奏: ${rhythm.rhythm || "中等"} | 平均镜头: ${rhythm.avg_shot_duration || 0}s | 场景数: ${analysis.scene_count || 0}\n\n` +
                              `📝 风格描述:\n${prompts.style_description || ""}\n\n` +
                              `🔧 AE参数表已生成，可用 generate_ae_script_from_analysis 生成ExtendScript\n\n` +
                              `💡 MCP提示词:\n${prompts.mcp_prompt || ""}`
                    }]
                };
                
            } catch (e) {
                return {
                    content: [{ type: "text", text: `❌ 分析失败: ${String(e)}` }],
                    isError: true
                };
            }
        }
    );
}