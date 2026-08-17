# 导演系统生产级架构设计方案

## 1. 设计目标

将多模态导演系统从"剧本生成器"升级为"端到端视频生产管线"，实现：
- **输入**：视频素材 + BGM + 歌词（可选）
- **输出**：完整视频文件（踩拍剪辑 + 文字特效 + 调色 + BGM混音）
- **一条命令跑通**，无需人工干预

## 2. 核心架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ProductionDirector (统一入口)                       │
├─────────────────────────────────────────────────────────────────────────┤
│  Phase 1: ANALYZE (感知层)                                              │
│  ├── BeatDetector          → 节拍网格、BPM、音乐结构                     │
│  ├── EmotionCurveGenerator → 情绪曲线 (0.0~1.0)                        │
│  ├── VisualContentAnalyzer → 素材标签 (场景类型、运动强度、色调)           │
│  └── LyricBeatBinder       → 歌词-节拍精确对齐                          │
├─────────────────────────────────────────────────────────────────────────┤
│  Phase 2: PLAN (编排层)                                                 │
│  ├── SegmentPlanner        → 段落划分 (intro/build/drop/break/outro)    │
│  ├── ShotSelector          → 素材-段落匹配 (基于情绪+内容)               │
│  └── TextAnimationPlanner  → 文字动画编排 (情绪驱动预设选择)              │
├─────────────────────────────────────────────────────────────────────────┤
│  Phase 3: EXECUTE (执行层)                                              │
│  ├── FFmpegRenderer        → 视频剪辑+转场+调色                          │
│  ├── TextOverlayEngine     → PIL PNG渲染 + FFmpeg overlay               │
│  └── BGMMixer              → 音频混合 (原声+BGM)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  Phase 4: VALIDATE (验证层)                                             │
│  ├── QualityChecker        → 分辨率/帧率/时长/音频验证                    │
│  └── ContentVerifier       → 素材匹配度/歌词可见性检查                    │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. 数据流

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 视频素材     │     │ BGM 音频     │     │ 歌词文本     │
│ *.mp4        │     │ *.mp3/*.flac │     │ (可选)       │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│                    ANALYZE (感知)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ BeatDetect  │  │ EmotionCurve│  │ VisualAnalyzer  │ │
│  │             │  │             │  │                 │ │
│  │ • beat_times│  │ • curve[]   │  │ • scene_type    │ │
│  │ • bpm       │  │ • segments  │  │ • motion_level  │ │
│  │ • structure │  │ • levels    │  │ • color_tone    │ │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         │                │                  │          │
│         └────────────────┼──────────────────┘          │
│                          ▼                             │
│                   ┌─────────────┐                      │
│                   │ LyricBinder │                      │
│                   │             │                      │
│                   │ • bindings  │                      │
│                   │ • offsets   │                      │
│                   └──────┬──────┘                      │
└──────────────────────────┼────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                     PLAN (编排)                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │ DirectorScript (结构化剧本)                      │   │
│  │                                                 │   │
│  │ segments: [                                     │   │
│  │   {                                             │   │
│  │     time_range: (start, end),                   │   │
│  │     mood: "climax",                             │   │
│  │     source_clips: [clip1, clip2],               │   │
│  │     text_overlay: {lyric, animation, style},    │   │
│  │     color_grade: "teal_orange",                 │   │
│  │     transition: "flash_cut"                     │   │
│  │   },                                            │   │
│  │   ...                                           │   │
│  │ ]                                               │   │
│  └─────────────────────┬───────────────────────────┘   │
└────────────────────────┼────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    EXECUTE (执行)                        │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ ClipAssembly│  │ TextOverlay │  │   BGMMixer      │ │
│  │             │  │             │  │                 │ │
│  │ FFmpeg:     │  │ PIL:        │  │ FFmpeg:         │ │
│  │ • 裁剪素材  │  │ • 渲染PNG   │  │ • amix滤镜      │ │
│  │ • 踩拍切点  │  │ • 多层叠加  │  │ • 音量控制      │ │
│  │ • 转场效果  │  │ • 动画时序  │  │ • 淡入淡出      │ │
│  │ • 调色LUT   │  │             │  │                 │ │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         │                │                  │          │
│         └────────────────┼──────────────────┘          │
│                          ▼                             │
│                   ┌─────────────┐                      │
│                   │ FinalOutput │                      │
│                   │             │                      │
│                   │ 1920x1080   │                      │
│                   │ 24fps       │                      │
│                   │ H.264+AAC   │                      │
│                   └─────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

## 4. 模块职责

### 4.1 感知层模块 (已有)

| 模块 | 文件 | 输入 | 输出 |
|------|------|------|------|
| BeatDetector | ae/beat_detector.py | 音频文件 | BeatInfo[], BPM, 段落结构 |
| EmotionCurveGenerator | ae/emotion_curve_generator.py | 音频文件 | EmotionCurve, 情绪段落 |
| VisualContentAnalyzer | ae/visual_content_analyzer.py | 视频文件 | MaterialTag (场景/运动/色调) |
| LyricBeatBinder | phase1_3_lyric_beat_binding.py | 歌词+节拍 | LyricBeatBinding[] |

### 4.2 编排层模块 (新增)

| 模块 | 职责 |
|------|------|
| SegmentPlanner | 基于情绪曲线划分段落，确定每段时长/情绪/切点密度 |
| ShotSelector | 根据段落情绪匹配素材 (高燃段→高运动素材，抒情段→特写素材) |
| TextAnimationPlanner | 为每句歌词选择动画预设 (情绪驱动) |

### 4.3 执行层模块 (整合)

| 模块 | 职责 |
|------|------|
| FFmpegRenderer | 素材裁剪、踩拍切点、转场、调色 |
| TextOverlayEngine | PIL渲染PNG + FFmpeg overlay叠加 |
| BGMMixer | 原声+BGM混合，音量控制 |

### 4.4 验证层模块 (新增)

| 模块 | 职责 |
|------|------|
| QualityChecker | ffprobe验证输出文件完整性 |
| ContentVerifier | 检查素材匹配度、歌词可见性 |

## 5. 统一入口 API

```python
from ai.production_director import ProductionDirector

# 创建导演实例
director = ProductionDirector()

# 端到端渲染
output = director.render(
    # 输入素材
    video_sources=[
        "data/real_amv_test/BV1A64y1u78E.mp4",  # 利威尔AMV
    ],
    bgm_path="D:/AE-Work/音频素材库/BGM/DiorGoFlex_AllEyesOnMe_v2.mp3",
    
    # 可选：歌词
    lyrics=[
        (0.0, 1.5, "像是只鸟飞不停", "gold"),
        (1.5, 3.5, "漫无目的地飞行", "cyan"),
        # ...
    ],
    
    # 可选：BGM使用段落
    bgm_start_sec=120.0,
    target_duration=48.0,
    
    # 输出配置
    output_dir="D:/AE-Work/output/levi_mad_director_v1/",
    output_name="Levi_MAD_Final.mp4",
)

print(f"输出文件: {output}")
```

## 6. 与现有管线集成

### 6.1 独立运行模式
```bash
python ai/production_director.py \
    --videos "video1.mp4,video2.mp4" \
    --bgm "bgm.mp3" \
    --output "output.mp4"
```

### 6.2 集成到 resolve_ae_resolve_pipeline.py
```python
# 在 ResolveAeResolvePipeline.run() 中
if ae_offline:
    # AE离线时降级到 ProductionDirector
    from ai.production_director import ProductionDirector
    director = ProductionDirector()
    return director.render(
        video_sources=clip_paths,
        bgm_path=bgm_path,
        output_dir=output_dir,
    )
```

## 7. 验证标准

### 7.1 运行验证
```bash
# 用实际素材运行
python ai/production_director.py \
    --videos "data/real_amv_test/BV1A64y1u78E.mp4" \
    --bgm "D:/AE-Work/音频素材库/BGM/DiorGoFlex_AllEyesOnMe_v2.mp3" \
    --output "D:/AE-Work/output/levi_mad_director_v1/test_output.mp4"
```

### 7.2 预期输出
- 文件存在且可播放
- 分辨率: 1920x1080
- 帧率: 24fps
- 时长: ~48s
- 编码: H.264 + AAC
- 包含歌词文字特效
- 包含BGM混音

### 7.3 成功判定
```python
assert Path(output).exists()
assert file_size > 10 * 1024 * 1024  # > 10MB
assert duration ≈ 48.0 ± 0.5
assert resolution == (1920, 1080)
assert has_audio_track == True
```

## 8. 关键设计决策

### 8.1 为什么用 FFmpeg 而非 AE/Resolve？
- **可用性**：FFmpeg 始终可用，AE/Resolve 可能离线
- **自动化**：命令行驱动，无需GUI交互
- **速度**：对于文字叠加类任务，FFmpeg 足够快
- **降级策略**：AE在线时可用 AE 做更复杂的文字动画

### 8.2 文字渲染方案
- **PIL + PNG overlay**：比 FFmpeg drawtext 更灵活，支持中文、复杂效果
- **多层结构**：光晕层 + 主体层 + 高光层，模拟专业字幕效果
- **时序控制**：`enable='between(t,start,end)'` 精确控制每句歌词显示时间

### 8.3 情绪驱动编排
- 情绪曲线决定段落结构
- 每个情绪等级对应视觉风格预设
- 文字动画类型由情绪驱动选择

## 9. 文件清单

```
ai/
├── production_director.py      # 统一入口 (新增)
├── segment_planner.py          # 段落规划器 (新增)
├── shot_selector.py            # 素材选择器 (新增)
└── quality_checker.py          # 质量检查器 (新增)

ae/
├── beat_detector.py            # 已有，修复API
├── visual_content_analyzer.py  # 已有
├── text_animation_engine.py    # 已有
└── emotion_curve_generator.py  # 已有
```

## 10. 实施计划

1. **Phase A**: 实现 ProductionDirector 核心框架
2. **Phase B**: 实现编排层模块 (SegmentPlanner, ShotSelector)
3. **Phase C**: 实现执行层整合 (FFmpeg渲染+文字叠加+混音)
4. **Phase D**: 实现验证层，端到端测试
