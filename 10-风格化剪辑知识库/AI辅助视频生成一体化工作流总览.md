---
title: AI辅助视频生成一体化工作流总览
date: 2026-07-05
tags:
  - 工作流
  - 一体化
  - 端到端
  - AI辅助
  - 原子级
---
# AI辅助视频生成一体化工作流总览

> [!abstract] 文档摘要
> 本文档定义 AI 辅助视频生成的端到端一体化工作流。从原始素材到最终成片的 9 个阶段：素材管理→预处理→音乐分析→片段分析→音画匹配→参数推演→AE生成→音效设计→质量验证。整合所有既有知识体系（Phase 1-6 + 音效 + 图层操作 + 修剪工具）。

> [!tip] 使用指南
> - 总览：第一章是整体架构
> - 实施：第二至九章是各阶段详解
> - 快速上手：第十章是一键调用入口
> - 质量保证：第十一章是 QC 体系

---

## 第一章 工作流总览

### 1.1 9阶段流水线

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AI 辅助视频生成一体化工作流                             │
└─────────────────────────────────────────────────────────────────────────┘

  Stage 0        Stage 1       Stage 2       Stage 3       Stage 4
  项目初始化  →  素材预处理  →  音乐分析  →  片段分析  →  音画匹配
                   │             │             │             │
                FFmpeg       librosa       OpenCV      决策树+DTW
                   │             │             │             │
                   ▼             ▼             ▼             ▼
             统一格式       MusicAtom    ClipAtom     MatchPlan
             场景检测       BPM/段落    运动/色彩     节拍对齐
             代理生成       能量曲线    构图/能量     效果绑定
                                                           ▲
                                                           │
  Stage 8  ←  Stage 7  ←  Stage 6  ←  Stage 5  ←  Stage 4.5
  质量验证     音效设计     AE生成执行    参数反推      剪辑思路
     │             │             │             │           │
   QC脚本     FFmpeg混音    MCP工具执行   强度→参数   叙事/节奏
     │             │             │             │           │
     ▼             ▼             ▼             ▼           ▼
  质量报告     音效时间轴   .aep 工程    CompilerInput  推演报告
     │
     ▼
  最终成片
```

### 1.2 工具栈全景

```yaml
tools_by_stage:
  stage_0_项目初始化:
    - 工作目录模板: "01-项目概览/项目工作流模板"
    - 文件夹生成: "Python脚本"
  
  stage_1_素材预处理:
    - 格式统一: "FFmpeg (libx264 CRF 18)"
    - 场景检测: "PySceneDetect"
    - 代理生成: "FFmpeg (540p proxy)"
    - 质量评估: "Python (OpenCV+librosa)"
  
  stage_2_音乐分析:
    - BPM检测: "librosa.beat"
    - 段落分割: "librosa + 自相似矩阵"
    - 频谱分析: "librosa.stft"
    - 情绪识别: "valence-arousal model"
  
  stage_3_片段分析:
    - 运动估计: "OpenCV (Farneback光流)"
    - 色彩分析: "K-Means + HSL"
    - 构图分析: "三分法/对称性"
    - 场景识别: "ResNet 分类"
  
  stage_4_音画匹配:
    - 节拍对齐: "动态规划 DTW"
    - 段落配对: "匈牙利算法"
    - 效果绑定: "频段-效果映射表"
    - 转场方案: "规则推理决策树"
  
  stage_5_参数反推:
    - 强度→参数: "映射公式库"
    - 关键帧生成: "节拍/段落/峰值驱动"
    - 转场操作: "转场操作生成器"
    - CompilerInput: "对接 Phase 1"
  
  stage_6_AE生成:
    - 引擎执行: "Phase 1-5 编译器"
    - MCP工具: "after-effects-mcp (36个工具)"
    - 图层操作: "修剪/排序/混合模式"
    - 实时预览: "AE RAM Preview"
  
  stage_7_音效设计:
    - 音效库: "36个原子音效"
    - 音画同步: "视觉事件→音效映射"
    - 混音: "FFmpeg (amix/loudnorm)"
    - 音效关键帧: "音效驱动视觉动画"
  
  stage_8_质量验证:
    - 时长检查: "ffprobe"
    - 音画同步: "Python 分析"
    - 质量评分: "多维度QC"
    - 反馈学习: "Phase 5 学习闭环"
```

### 1.3 核心数据流转

```
原始输入:
  - 音乐文件: music.mp3
  - 视频片段: clip1.mp4, clip2.mp4, clip3.mp4
  - 目标风格: "cyberpunk" / "cinematic" / "dream"

中间产物:
  MusicAtom (YAML)
  ClipAtom[] (YAML)
  MatchPlan (YAML)
  CompilerInput (JSON)
  SoundTimeline (YAML)
  AE工程文件 (.aep)

最终输出:
  - 成片视频: final_output.mp4
  - AE工程: project.aep
  - 推演报告: analysis_report.md
  - 质量报告: quality_report.md
```

---

## 第二章 Stage 0：项目初始化

### 2.1 初始化流程

```yaml
stage_0_init:
  step_1_创建项目目录:
    tool: "Python 脚本"
    input:
      project_name: "项目名称"
      style: "目标风格"
      date: "开始日期"
    output:
      - "01-策划/"
      - "02-素材/原始素材/"
      - "02-素材/剪辑素材/"
      - "02-素材/代理素材/"
      - "03-工程/AE/"
      - "03-工程/PR/"
      - "04-渲染输出/草稿/"
      - "04-渲染输出/送审版/"
      - "04-渲染输出/最终版/"
      - "05-音效/"
      - "06-参考/"
  
  step_2_素材导入:
    action: "复制音乐和片段到 02-素材/原始素材/"
    naming:
      - "music/music_original.mp3"
      - "video/clip_001.mp4"
      - "video/clip_002.mp4"
  
  step_3_创建需求文档:
    template: "需求文档模板"
    fields:
      - 项目名称
      - 目标时长
      - 目标风格
      - 参考视频
      - 特殊要求
      - 交稿日期
```

### 2.2 初始化脚本

```python
"""
init_project.py
项目初始化脚本
"""
import os
import shutil
from datetime import datetime

def init_project(project_name, style="cinematic", base_path="D:/AE-Work/02-项目库"):
    """初始化新项目"""
    
    # 项目目录名
    date_str = datetime.now().strftime("%Y-%m-%d")
    project_dir = os.path.join(base_path, f"{date_str}-{project_name}")
    
    # 子目录列表
    subdirs = [
        "01-策划",
        "02-素材/原始素材/music",
        "02-素材/原始素材/video",
        "02-素材/剪辑素材",
        "02-素材/代理素材",
        "03-工程/AE",
        "03-工程/PR",
        "04-渲染输出/草稿",
        "04-渲染输出/送审版",
        "04-渲染输出/最终版",
        "05-音效/SFX",
        "05-音效/Music",
        "06-参考",
        "99-归档"
    ]
    
    # 创建目录
    os.makedirs(project_dir, exist_ok=True)
    for subdir in subdirs:
        os.makedirs(os.path.join(project_dir, subdir), exist_ok=True)
    
    # 创建需求文档
    readme = f"""# {project_name} - 项目需求

**项目名称**：{project_name}
**开始日期**：{date_str}
**目标风格**：{style}
**目标时长**：待定
**交稿日期**：待定

## 需求描述

[在此填写项目需求]

## 参考资料

- 参考视频1：[链接]
- 参考视频2：[链接]

## 素材清单

- 音乐：music/music_original.mp3
- 视频片段：
  - clip_001.mp4
  - clip_002.mp4
  - clip_003.mp4

## 特殊要求

[在此填写特殊要求]
"""
    
    with open(os.path.join(project_dir, "01-策划/需求文档.md"), 'w', encoding='utf-8') as f:
        f.write(readme)
    
    print(f"✓ 项目已创建: {project_dir}")
    return project_dir
```

---

## 第三章 Stage 1：素材预处理

### 3.1 处理流程

```yaml
stage_1_preprocessing:
  step_1_格式统一:
    tool: "FFmpeg"
    input: "02-素材/原始素材/"
    output: "02-素材/剪辑素材/"
    params:
      video_codec: "libx264"
      crf: 18
      preset: "fast"
      audio_codec: "aac"
      audio_bitrate: "320k"
      resolution: "1920x1080"
      frame_rate: 30
      container: "mp4"
      faststart: true
    note: "统一所有素材格式，确保后续处理一致"
  
  step_2_场景检测:
    tool: "PySceneDetect"
    input: "02-素材/剪辑素材/"
    output: "02-素材/剪辑素材/scenes/"
    threshold: 0.4
    min_scene_len: 1.0
    note: "检测每个素材的场景切换点，用于粗剪参考"
  
  step_3_代理生成:
    tool: "FFmpeg"
    input: "02-素材/剪辑素材/"
    output: "02-素材/代理素材/"
    params:
      resolution: "960x540"
      crf: 23
      preset: "ultrafast"
    note: "生成低分辨率代理，加快预览速度"
  
  step_4_质量评估:
    tool: "Python (OpenCV+librosa)"
    input: "02-素材/剪辑素材/"
    output: "quality_report.md"
    checks:
      - 分辨率 ≥ 1080p
      - 帧率 ≥ 24fps
      - 码率 ≥ 8Mbps
      - 音频 立体声
      - 时长 ≥ 3s
    note: "评估素材质量，标记低质量素材"
```

---

## 第四章 Stage 2：音乐分析

### 4.1 分析流程

```yaml
stage_2_music_analysis:
  step_1_加载音频:
    tool: "librosa"
    params:
      sample_rate: 44100
      mono: false
  
  step_2_节拍检测:
    output:
      - bpm: 128
      - beat_grid: []
      - downbeats: []
    accuracy: "±2 BPM"
  
  step_3_段落分割:
    algorithm: "自相似矩阵 + 层次聚类"
    output:
      - segments: [intro, verse, chorus, bridge, chorus, outro]
    accuracy: "±0.5s 边界"
  
  step_4_频谱分析:
    output:
      - 6频段能量曲线
      - 频谱质心
      - 频谱通量
  
  step_5_情绪识别:
    model: "valence-arousal"
    output:
      - valence: 0-1
      - arousal: 0-1
      - dominant_key: "C minor"
      - mode: "minor"
  
  step_6_输出MusicAtom:
    format: "YAML"
    path: "analysis/music_atom.yaml"
```

---

## 第五章 Stage 3：片段分析

### 5.1 分析流程

```yaml
stage_3_clip_analysis:
  step_1_运动分析:
    algorithm: "Farneback 稠密光流"
    output:
      - motion_intensity: 0-1
      - motion_curve: []
      - dominant_direction: "right/left/..."
      - camera_movement: "pan/zoom/tilt/static"
  
  step_2_色彩分析:
    algorithm: "K-Means 聚类 (K=5)"
    output:
      - palette: ["#xxxxx", ...]
      - temperature: "warm/cool/neutral"
      - saturation: 0-1
      - brightness: 0-1
      - contrast: 0-1
  
  step_3_构图分析:
    output:
      - rule_of_thirds: 0-1
      - symmetry: 0-1
      - depth: "shallow/medium/deep"
      - subject_position: [x, y]
  
  step_4_能量计算:
    formula: "0.5*运动 + 0.25*饱和度 + 0.25*对比度"
    output:
      - overall_energy: 0-1
      - energy_curve: []
      - peak_time: float
  
  step_5_场景识别:
    model: "ResNet50 (ImageNet)"
    output:
      - scene_type: "cityscape/nature/portrait/..."
      - top5: [... ]
    accuracy: ">75%"
  
  step_6_输出ClipAtom:
    format: "YAML"
    path: "analysis/clip_001_atom.yaml"
    数量: "每个片段一个"
```

---

## 第六章 Stage 4-5：音画匹配与参数推演

### 6.1 匹配流程

```yaml
stage_4_matching:
  step_1_节拍对齐:
    algorithm: "动态规划"
    input:
      - beat_grid
      - clip_durations
    output:
      - alignment: [{time, clip, cut_type}]
  
  step_2_段落配对:
    algorithm: "匈牙利算法 + 能量匹配"
    input:
      - segments (音乐段落)
      - clip_atoms
    output:
      - segment_clip_pairs: [{segment, clip, confidence}]
  
  step_3_效果绑定:
    algorithm: "频段→效果映射表"
    input:
      - spectrum_bands
      - target_style
    output:
      - effect_bindings: [{time_range, effect, intensity}]
  
  step_4_转场方案:
    algorithm: "决策树规则推理"
    input:
      - alignment
      - segments
      - target_style
    output:
      - transition_plan: [{time, type, duration}]
  
  step_5_剪辑思路:
    output:
      - narrative_structure: [cold_open, build, climax, ...]
      - pacing_curve: []
      - emotional_curve: []

stage_5_parameter_inference:
  step_1_强度→参数反推:
    input:
      - effect_bindings
      - target_style
    output:
      - effect_params: {matchName, params}
  
  step_2_关键帧生成:
    generators:
      - 节拍驱动关键帧
      - 段落驱动关键帧
      - 峰值驱动关键帧
    output:
      - keyframes: [{time, value, easing}]
  
  step_3_转场操作生成:
    output:
      - transition_ops: [{op, params}]
  
  step_4_输出CompilerInput:
    format: "JSON"
    spec: "Phase 1 CompilerInput 规范"
    path: "analysis/compiler_input.json"
```

---

## 第七章 Stage 6：AE生成执行

### 7.1 执行流程

```yaml
stage_6_ae_execution:
  step_1_编译代码:
    tool: "Phase 1 编译器"
    input: "CompilerInput (JSON)"
    output: "ExtendScript (.jsx)"
  
  step_2_MCP执行:
    tool: "after-effects-mcp (36个工具)"
    tools_used:
      - create_comp / createComp
      - add_layer / addLayer
      - add_effect / addEffect
      - add_effect_with_keyframes
      - set_property / setProperty
      - batch_add_effects
      - execute_extendscript
      - get_effect_properties
      - 等...
    output:
      - AE合成已创建
      - 图层/效果/关键帧已设置
  
  step_3_音效图层:
    operation: "导入音效文件到 AE"
    tracks:
      - A1: 主音乐
      - A2: 转场音效
      - A3: 卡点音效
      - A4: 氛围音效
  
  step_4_实时预览:
    tool: "AE RAM Preview"
    action: "空格键播放预览"
    duration: "预览 10 秒"
  
  step_5_保存工程:
    path: "03-工程/AE/project_v1.aep"
    note: "版本号递增"
```

### 7.2 图层操作集成

```yaml
layer_operations_in_pipeline:
  修剪操作:
    - 按节拍对齐设置 in_point/out_point
    - 场景分割点修剪
    - 时间重映射（速度变化）
  
  排序操作:
    - 按时间线排列图层
    - 上层：效果调整层
    - 中层：视频图层
    - 下层：背景/底图
  
  混合模式:
    - 发光效果层：Add / Screen
    - 暗角效果层：Multiply
    - 调整层：Normal（不透明调整）
  
  预合成:
    - 复杂效果组合预合成
    - 文字动画组预合成
    - 粒子系统预合成
  
  文字图层:
    - 片头标题
    - 字幕
    - 水印
```

---

## 第八章 Stage 7：音效设计

### 8.1 音效生成流程

```yaml
stage_7_sound_design:
  step_1_音效时间轴生成:
    input:
      - match_plan
      - music_atom
      - clip_atoms
    output:
      - sound_timeline (YAML)
    events:
      - 转场音效
      - 卡点音效
      - 氛围音效
      - 效果触发音效
  
  step_2_音效选择:
    library: "音效原子库 (36个音效)"
    selection_rules:
      - 视觉事件类型 → 音效类型
      - 音乐段落 → 音效层次
      - 风格目标 → 音效风格
  
  step_3_音效时间调整:
    operations:
      - 对齐到节拍
      - 对齐到视觉峰值
      - 时长匹配转场时长
      - 淡入淡出
  
  step_4_混音:
    tool: "FFmpeg"
    layers:
      - L1: 主音乐 (-3dB)
      - L2: 转场音效 (-6dB)
      - L3: 卡点音效 (-8dB)
      - L4: 氛围音效 (-18dB)
      - L5: 设计音效 (-10dB)
    loudness: "-16 LUFS"
    output: "05-音效/mixed_audio.wav"
  
  step_5_音画同步验证:
    check: "视觉峰值 ↔ 音效峰值 时间差"
    tolerance: "< 50ms"
```

---

## 第九章 Stage 8：质量验证

### 9.1 验证清单

```yaml
stage_8_quality_check:
  step_1_基础检查:
    - 时长符合要求
    - 分辨率正确 (1920x1080)
    - 帧率正确 (30fps)
    - 音画同步 (误差 < 50ms)
    - 无黑边/白边
    - 音频无爆音
    - 文件完整可播放
  
  step_2_节拍对齐检查:
    tool: "Python 分析"
    method: "视频亮度峰值 vs 音乐节拍"
    target: "对齐率 > 90%"
  
  step_3_风格匹配检查:
    tool: "视觉签名检测"
    target: "风格匹配度 > 0.8"
  
  step_4_主观质量评分:
    dimensions:
      - 节奏感 (0-10)
      - 色彩协调性 (0-10)
      - 转场流畅度 (0-10)
      - 音效契合度 (0-10)
      - 整体观感 (0-10)
  
  step_5_生成质量报告:
    format: "Markdown"
    path: "04-渲染输出/质量报告_v1.md"
  
  step_6_反馈学习:
    tool: "Phase 5 学习闭环"
    input:
      - 执行结果
      - 质量评分
      - 用户反馈
    output:
      - 更新参数模板
      - 更新默认值
      - 更新置信度
```

---

## 第十章 一键调用入口

### 10.1 主入口函数

```typescript
/**
 * AI 辅助视频生成 —— 一键端到端调用
 */
interface AutoVideoRequest {
  // 输入文件
  musicFile: string;              // 音乐文件路径
  clipFiles: string[];            // 视频片段路径列表
  
  // 目标参数
  targetStyle: string;            // 目标风格：cyberpunk/cinematic/dream/...
  targetDuration?: number;        // 目标时长（秒，默认跟随音乐）
  targetResolution?: [number, number]; // 目标分辨率，默认 [1920, 1080]
  targetFrameRate?: number;       // 目标帧率，默认 30
  
  // 偏好设置
  preferences?: {
    cutDensity?: number;          // 切镜密度 0-1，默认自动
    effectIntensity?: number;     // 效果强度 0-1，默认 0.8
    includeSoundDesign?: boolean; // 是否生成音效，默认 true
    colorGrading?: boolean;       // 是否调色，默认 true
    textOverlays?: TextOverlay[]; // 文字叠加
  };
  
  // 输出
  outputPath: string;             // 输出目录
}

interface AutoVideoResult {
  // 最终输出
  outputVideo: string;            // 成片路径
  aeProject: string;              // AE工程路径
  
  // 中间产物
  musicAtom: MusicAtom;
  clipAtoms: ClipAtom[];
  matchPlan: MatchPlan;
  compilerInput: CompilerInput;
  soundTimeline: SoundTimeline;
  
  // 质量
  qualityReport: QualityReport;
  reasoningPath: string[];        // 推演路径
  prediction: OutcomePrediction;  // 成片预判
  
  // 耗时统计
  timing: {
    total: number;
    stages: Record<string, number>;
  };
}

/**
 * 主入口：一键生成
 */
async function autoGenerateVideo(req: AutoVideoRequest): Promise<AutoVideoResult> {
  const timing: Record<string, number> = {};
  const t0 = Date.now();
  
  // Stage 0: 初始化
  const t1 = Date.now();
  const projectDir = initProject(req);
  timing.init = Date.now() - t1;
  
  // Stage 1: 素材预处理
  const t2 = Date.now();
  const processedClips = preprocessClips(req.clipFiles, projectDir);
  timing.preprocessing = Date.now() - t2;
  
  // Stage 2: 音乐分析
  const t3 = Date.now();
  const musicAtom = analyzeMusic(req.musicFile);
  timing.music_analysis = Date.now() - t3;
  
  // Stage 3: 片段分析
  const t4 = Date.now();
  const clipAtoms = analyzeClips(processedClips);
  timing.clip_analysis = Date.now() - t4;
  
  // Stage 4: 音画匹配
  const t5 = Date.now();
  const matchPlan = matchAudioVisual(musicAtom, clipAtoms, req.targetStyle);
  timing.matching = Date.now() - t5;
  
  // Stage 5: 参数反推
  const t6 = Date.now();
  const compilerInput = inferParameters(matchPlan, musicAtom, req.targetStyle);
  timing.inference = Date.now() - t6;
  
  // Stage 6: AE 执行
  const t7 = Date.now();
  const aeResult = executeInAE(compilerInput, projectDir);
  timing.ae_execution = Date.now() - t7;
  
  // Stage 7: 音效设计
  const t8 = Date.now();
  const soundResult = designSound(matchPlan, musicAtom, clipAtoms, projectDir);
  timing.sound_design = Date.now() - t8;
  
  // Stage 8: 质量验证
  const t9 = Date.now();
  const qualityReport = verifyQuality(aeResult, soundResult, musicAtom);
  timing.quality_check = Date.now() - t9;
  
  timing.total = Date.now() - t0;
  
  return {
    outputVideo: aeResult.outputVideo,
    aeProject: aeResult.projectFile,
    musicAtom,
    clipAtoms,
    matchPlan,
    compilerInput,
    soundTimeline: soundResult.timeline,
    qualityReport,
    reasoningPath: matchPlan.reasoningPath,
    prediction: predictOutcome(matchPlan, compilerInput),
    timing
  };
}
```

### 10.2 典型使用场景

```yaml
use_cases:
  卡点视频:
    input:
      music: "EDM 128bpm.mp3"
      clips: ["城市夜景.mp4", "霓虹招牌.mp4", "车流.mp4"]
      style: "cyberpunk"
    output: "赛博朋克卡点视频"
    expected_duration: "~60秒"
    expected_quality: "8.5/10"
  
  抒情MV:
    input:
      music: "流行抒情 90bpm.mp3"
      clips: ["人物特写×4"]
      style: "cinematic"
    output: "电影感人像MV"
  
  旅行Vlog:
    input:
      music: "轻快民谣 95bpm.mp3"
      clips: ["风景×5 + 人文×5"]
      style: "japanese_style"
    output: "日系清新旅行Vlog"
  
  产品宣传:
    input:
      music: "电子科技 120bpm.mp3"
      clips: ["产品特写×5"]
      style: "tech_clean"
    output: "科技感产品宣传片"
```

---

## 第十一章 QC 体系

### 11.1 自动化 QC 脚本

```python
"""
auto_qc.py
自动质量检查脚本
"""
import subprocess
import json

def auto_quality_check(video_path, expected_duration=None):
    """自动质量检查"""
    results = {}
    
    # 1. 基础元数据检查
    info = get_video_info(video_path)
    results["metadata"] = {
        "resolution": f"{info['width']}x{info['height']}",
        "duration": info["duration"],
        "codec": info["codec"],
        "frame_rate": info["frame_rate"]
    }
    
    # 2. 时长检查
    if expected_duration:
        diff = abs(info["duration"] - expected_duration)
        results["duration_check"] = {
            "expected": expected_duration,
            "actual": info["duration"],
            "diff": diff,
            "passed": diff < 0.5
        }
    
    # 3. 音频检查
    results["audio_check"] = {
        "has_audio": info["has_audio"],
        "channels": info.get("audio_channels", 0),
        "sample_rate": info.get("audio_sample_rate", 0),
        "passed": info["has_audio"] and info["audio_channels"] >= 2
    }
    
    # 4. 输出报告
    overall = all(v.get("passed", True) for v in results.values() if isinstance(v, dict))
    results["overall"] = overall
    
    return results
```

### 11.2 质量分级

| 等级 | 评分范围 | 描述 | 处理方式 |
|------|---------|------|---------|
| S | 9-10 | 完美 | 直接交付 |
| A | 8-9 | 优秀 | 微调后交付 |
| B | 7-8 | 良好 | 可送审 |
| C | 6-7 | 一般 | 需要修改 |
| D | <6 | 不合格 | 重新生成 |

---

## 第十二章 关联文档

### 12.1 核心系统文档

- [[音画匹配推演系统总览]] — Phase 6 顶层架构
- [[音乐结构原子分析与节拍映射]] — Stage 2
- [[片段元数据与视觉能量图谱]] — Stage 3
- [[音画匹配决策树与剪辑思路推演]] — Stage 4
- [[参数反向推演与原子输出规范]] — Stage 5
- [[效果推演引擎与成片预判]] — 成片预判
- [[音效设计原子体系与音画同步]] — Stage 7
- [[图层操作与视频修剪工具链]] — Stage 1 & 6
- [[AE 自动化引擎架构设计]] — 引擎基础
- [[视频剪辑项目工作流模板]] — 项目组织

### 12.2 知识库文档

- [[风格化预设宝典]] — 风格配方
- [[风格化剪辑技巧与预设]] — 剪辑技巧
- [[国际剪辑理论进阶]] — 剪辑理论
- [[中国剪辑知识体系]] — 中国视角
- [[剪辑思维与逻辑]] — 思维方法
- [[解析词汇表与推理决策树]] — 决策树基础
- [[视频案例解析库]] — 案例库
- [[音画匹配实战案例库与知识图谱]] — 音画案例

### 12.3 时间轴精密映射知识库（原子级制片库）

> [!important] 核心知识库
> Stage 4-5（音画匹配与参数推演）的精密参数全部来源于此知识库。它将「音乐时间轴位置」精确映射到「音效+视觉效果+关键帧曲线+速度值+转场」的完整配方。

- [[节拍-关键帧精密映射库]] — 7种节拍×12种效果的关键帧曲线+贝塞尔精确值+数学包络
- [[段落结构-效果编排与转场联动库]] — 7种段落×40+效果配方×转场-节拍-音效联动矩阵
- [[能量-情绪-色彩-音效四维映射库]] — E×V×A×HSL四维空间×27种情绪配方×10流派校准
- [[流派专属音画配方库]] — 10大流派×30+子流派×40+完整案例×5层效果栈
- [[时间轴推理引擎与决策规范]] — 9层推理架构×TimelinePlan Schema×多目标优化

**五层映射精度**：L1节拍级(±10ms) → L2段落级(±50ms) → L3四维联动(连续值) → L4流派级(风格化) → L5推理引擎(全自动)

> 返回 [[🎬-风格化剪辑知识库-MOC]] · [[🏠-AE知识中心]]
