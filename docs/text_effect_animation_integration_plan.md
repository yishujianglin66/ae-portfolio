# "特效+动画"一体化整合方案

> 版本: 1.3 | 日期: 2026-08-05 | 状态: **P0+P1+P2全部完成验收 (107/107测试通过)**
> 基于两大文字系统对比分析，设计空间层(特效质感) × 时间层(动画运动)的融合架构
>
> **P0交付证据**:
> - `core/jsx_keyframe_animator.py`: EffectLayerBuilder + SmartMatcher + orchestrate_layer 集成
> - `tests/test_text_integration.py`: 77项验收全部通过
> - `tmp/gen_text_anim_video.py`: FX模拟升级，预览视频 1967KB (较v3 +221KB)
>
> **P1交付证据**:
> - 31套特效参数键覆盖缺口归零(补齐 Drop Shadow angle + Bevel Emboss 双色合并)
> - SmartMatcher 全量场景覆盖: 89个best_for标签全命中 + 字符重叠模糊匹配 + 别名边界防护
> - Ground Truth 展示视频: `text_ground_truth_showcase.mp4` (625KB, 6套verified基准)
> - 测试升级: 77→83 项全部通过
>
> **P2交付证据**:
> - `integrations/smart_director.py`: select_text_combo_for_shot 镜头节奏→三维组合，导演JSX自动注入特效段(try/catch包裹)
> - `integrations/resolve_ae_resolve_pipeline.py`: 9宫格场景标签推断 + 文字层统计回传(text_layer_stats)
> - `core/jsx_keyframe_animator.py`: PresetTracker.record_combo 三维覆盖率追踪(特效|动画|字体)
> - `tests/test_text_integration_p2.py`: 24项验收全部通过；覆盖率报告实测: 6镜头→6唯一组合多样性100%

---

## 一、统一架构设计

### 1.1 系统定位

| 系统 | 角色 | 核心文件 | 管辖维度 |
|------|------|----------|----------|
| 文字特效生成 (System A) | **空间层** — 文字"长什么样" | `puppet-automation/src/services/text_effect_service.py` | 字体质感、AE效果器(Glow/Bevel/TurbulentDisplace)、多层合成(TXT_/GLOW_/RGB_/GRAD_) |
| 文字动画生成 (System B) | **时间层** — 文字"怎么动" | `core/jsx_keyframe_animator.py` | 36种动画风格、缓动曲线、节拍同步、编排轮转、强度分级 |
| 三维预设矩阵 (数据库) | **匹配引擎** — "什么配什么" | `scripts/build_text_preset_matrix.py` | 30套特效 × 25种入场 × 50款字体，含推荐规则 |
| 字体策略系统 (配置) | **风格约束** — "这类场景用什么字体" | `scripts/apply_font_design.py` | 11类FONT_STRATEGY分类及字体分配规则 |
| 跨平台引擎 (参考) | **多平台扩展** | `video/text_animation_engine.py` | AE/PR/PS/Resolve/Blender 5平台JSX生成 |

### 1.2 融合架构：EffectLayerBuilder 嵌入 AnimationOrchestrator

```
┌─────────────────────────────────────────────────────────────┐
│                  AnimationOrchestrator                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │Entrance  │ │TextAnim  │ │BeatSync  │ │CameraAnimator │  │
│  │Animator  │ │ator      │ │Animator  │ │               │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬────────┘  │
│       │            │            │               │           │
│       └────────────┴────────────┴───────────────┘           │
│                        │                                    │
│              ┌─────────▼──────────┐                         │
│              │ EffectLayerBuilder  │ ← 新增模块             │
│              │ (空间层效果生成器)   │                         │
│              └─────────┬──────────┘                         │
│                        │                                    │
│              ┌─────────▼──────────┐                         │
│              │ SmartMatcher       │ ← 新增模块             │
│              │ (字体×特效×动画     │                         │
│              │  三维智能匹配)      │                         │
│              └────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
                        │
              ┌─────────▼──────────┐
              │ to_jsx_snippet()   │
              │ 输出: 动画关键帧    │
              │   + 效果器设置     │
              │   + 多层架构JSX    │
              └────────────────────┘
```

### 1.3 数据流定义

```python
# 调用入口
orchestrator.orchestrate_layer(
    layer_config={
        "type": "text",
        "role": "title",          # "title" | "subtitle"
        "text": "热血战斗",
        "scene_tag": "battle",    # 场景标签，驱动智能匹配
    },
    style_category="amv_pull_zoom",
    beats=[BeatTiming(time=0.5, strength=1.0, is_downbeat=True), ...],
    duration=2.0,
    start_time=0.0,
)

# 内部数据流
# Step 1: SmartMatcher 根据 scene_tag 匹配最佳组合
match_result = SmartMatcher.match(
    scene_tag="battle",
    role="title",
    intensity=AnimationIntensity.INTENSE,
)
# → { font: "Impact", effect_combo: "effect_cyber_glitch",
#     animation: TextAnimationStyle.IMPACT_SHAKE,
#     font_strategy: "kinetic_typography" }

# Step 2: TextAnimator 生成时间层轨道
anim_tracks = text_animator.build_tracks(
    style=match_result.animation,
    text_start=start_time,
    text_duration=duration * 0.6,
    magnitude=match_result.intensity.amplitude_scale * 50,
)

# Step 3: EffectLayerBuilder 生成空间层效果配置
effect_config = effect_builder.build_effect_config(
    combo_id=match_result.effect_combo,
    font=match_result.font,
    font_size=hierarchy.title_font_size,
)

# Step 4: 合并输出
layer_anim._text_meta = {
    **anim_meta,
    "effect_combo": match_result.effect_combo,
    "effect_layers": effect_config.layers,  # GLOW_/RGB_/GRAD_ 层配置
    "font": ae_safe_font_name(match_result.font),
}
```

### 1.4 EffectLayerBuilder 接口定义

```python
class EffectLayerBuilder:
    """空间层效果生成器 — 将 EFFECT_COMBOS 转为 AE JSX 效果器配置"""

    # 效果器 matchName → JSX 属性设置模板
    EFFECT_TEMPLATES = {
        "ADBE Glo2": {  # Glow
            "params": ["Threshold", "Radius", "Intensity", "GlowColor"],
            "jsx_pattern": 'var fx = layer.property("Effects").addProperty("ADBE Glo2");\n'
                          'fx.property("ADBE Glo2-0001").setValue({threshold});\n'
                          'fx.property("ADBE Glo2-0002").setValue({radius});\n'
                          'fx.property("ADBE Glo2-0003").setValue({intensity});\n',
        },
        "ADBE Turbulent Displace": {  # Turbulent Displace
            "params": ["Amount", "Size"],
            "jsx_pattern": '...setValue({amount});\n...setValue({size});\n',
        },
        "ADBE Bevel Emboss": { ... },
        "ADBE Drop Shadow": { ... },
        "ADBE Ramp": { ... },
        "ADBE Venetian Blinds": { ... },
        "ADBE Tint": { ... },
        "ADBE Fractal Noise": { ... },
    }

    def build_effect_config(
        self,
        combo_id: str,
        font: str,
        font_size: float,
        intensity: AnimationIntensity = AnimationIntensity.MODERATE,
    ) -> EffectConfig:
        """从 EFFECT_COMBOS 数据库查找并构建效果器配置"""
        ...

    def to_multi_layer_jsx(self, config: EffectConfig,
                            text_layer_var: str) -> str:
        """生成多层架构 JSX：TXT_ + GLOW_ + RGB_R_ + RGB_C_ + GRAD_"""
        ...
```

### 1.5 SmartMatcher 接口定义

```python
class SmartMatcher:
    """三维智能匹配引擎"""

    def __init__(self):
        # 加载三维矩阵数据库
        self.db = load_text_presets_database()  # 30 effects + 25 anims + 50 fonts
        self.font_strategy = FONT_STRATEGY       # 11 类字体策略
        self._build_scene_index()                # 按 best_for 建立倒排索引

    def _build_scene_index(self):
        """建立 场景标签 → (effect, animation, font) 倒排索引"""
        # 从 EFFECT_COMBOS[i].best_for 提取场景关键词
        # 从 ENTRANCE_ANIMATIONS[i].best_for 提取场景关键词
        # 从 FONT_LIBRARY[i].best_for 提取场景关键词
        # 建立倒排索引: "热血标题" → [effect_cyber_glitch, anim_kinetic_smash, font_impact]
        ...

    def match(
        self,
        scene_tag: str,
        role: str = "title",
        intensity: AnimationIntensity = AnimationIntensity.MODERATE,
    ) -> MatchResult:
        """根据场景标签返回最佳组合"""
        ...

    def match_by_keywords(self, keywords: List[str],
                          ...) -> MatchResult:
        """多关键词模糊匹配"""
        ...
```

---

## 二、字体-特效-动画三维匹配矩阵

### 2.1 匹配规则来源

三维匹配的核心约束来自已有数据中的 `recommended_*` 和 `best_for` 字段：

```
FONT_LIBRARY[i].recommended_effects    → 字体A适合哪些特效
FONT_LIBRARY[i].recommended_animations → 字体A适合哪些动画
EFFECT_COMBOS[i].recommended_font_traits → 特效B适合什么特征的字体
ENTRANCE_ANIMATIONS[i].best_for        → 动画C最适合什么场景
```

### 2.2 场景驱动匹配表（核心20组 Ground Truth）

以下基于 `verified=True` 的基准案例 + FONT_STRATEGY 分类推导：

| # | 场景标签 | 字体策略 | 主字体 | 特效组合 | 动画风格 | 强度 |
|---|---------|---------|--------|---------|---------|------|
| 1 | `battle` 热血战斗 | kinetic_typography | Impact | effect_cyber_glitch | IMPACT_SHAKE | intense |
| 2 | `cyberpunk` 赛博朋克 | cyberpunk | Consolas | effect_rgb_split | GLITCH_TEXT | intense |
| 3 | `cinematic` 电影史诗 | cinematic | BodoniMT | effect_golden_logo | ELASTIC_OVERSHOOT | moderate |
| 4 | `anime` 日系热血 | anime_fx | YuGothic-Bold | effect_fire_burn | KINETIC_TYPING | intense |
| 5 | `ink_wash` 水墨国风 | art_typography | STXingkai | effect_ink_wash | WAVE_ENTRANCE | subtle |
| 6 | `neon` 霓虹潮流 | cyberpunk | DINNextLTPro-Bold | effect_neon_pulse | NEON_FLICKER | moderate |
| 7 | `social` 社交活力 | social_media | YouYuan | effect_soft_glow | LETTER_POP | subtle |
| 8 | `horror` 神秘恐怖 | vfx_presets | Chiller | effect_smoke_dissolve | CASCADE_FALL | moderate |
| 9 | `tech` 科技HUD | cyberpunk | Consolas | effect_hologram_hud | PER_CHAR_WAVE | subtle |
| 10 | `elegant` 优雅文艺 | cinema_titles | PalaceScriptMT | effect_elegant_fade | FLOAT_UP | subtle |
| 11 | `sport` 运动冲击 | kinetic_typography | Impact | effect_electric_shock | SCALE_DOWN_BOUNCE | intense |
| 12 | `retro` 复古怀旧 | cyberpunk | CourierNew | effect_retro_vhs | TYPEWRITER | moderate |
| 13 | `magic` 魔法能量 | vfx_presets | RageItalic | effect_aurora | SPIRAL_ENTRANCE | intense |
| 14 | `industrial` 工业力量 | advanced_kinetic | Stencil | effect_metallic_bevel | DOMINO_FALL | moderate |
| 15 | `cute` 可爱童趣 | social_media | YouYuan | effect_neon_sign | SQUASH_STRETCH | subtle |
| 16 | `data` 数据可视化 | cyberpunk | Consolas | effect_matrix_digital | SCATTER_CONVERGE | moderate |
| 17 | `brand` 品牌展示 | 3d_title_extended | BodoniMT | effect_chrome_reflect | SPRING_SCALE | moderate |
| 18 | `comic` 漫画冲击 | kinetic_typography | Bangers | effect_rgb_split | RANDOM_POP | intense |
| 19 | `title_kit` 通用标题 | modern | Arial-BoldMT | effect_clean_shadow | FADE_UP_STAGGER | subtle |
| 20 | `lyric` 歌词字幕 | anime_fx | STKaiti | effect_light_leak | BASELINE_SHIFT | subtle |

### 2.3 匹配优先级规则

```
1. scene_tag 精确匹配 → 直接查表
2. scene_tag 模糊匹配 → 从 best_for 字段倒排索引中找最近场景
3. role 约束 → title 优先 entrance 类动画，subtitle 优先 continuous 类
4. intensity 约束 → subtle 限幅 0.5x，moderate 1.0x，intense 1.8x
5. 字体 fallback → 匹配失败时按 FONT_STRATEGY category 选 primary 字体
```

---

## 三、分阶段实施路线图

### P0 — 核心融合骨架（最高优先级）

**目标**: 在 `AnimationOrchestrator` 中完成 EffectLayerBuilder + SmartMatcher 集成

| 任务 | 文件 | 交付物 | 验证标准 |
|------|------|--------|----------|
| P0-1 新增 EffectLayerBuilder 类 | `core/jsx_keyframe_animator.py` | EffectLayerBuilder 类，支持 8 种核心效果器的 JSX 生成 | 每种效果器能独立生成可执行 JSX |
| P0-2 新增 SmartMatcher 类 | `core/jsx_keyframe_animator.py` | 基于 best_for 倒排索引的场景匹配引擎 | 20 组 Ground Truth 场景全部匹配成功 |
| P0-3 AnimationOrchestrator 集成 | `core/jsx_keyframe_animator.py` | orchestrate_layer() 内部调用 SmartMatcher + EffectLayerBuilder | _text_meta 包含 effect_combo 和 effect_layers |
| P0-4 to_jsx_snippet() 多层输出 | `core/jsx_keyframe_animator.py` | 单次调用输出 TXT_ + GLOW_ + RGB_ 完整 JSX | JSX 在 AE 中执行无报错 |
| P0-5 预览视频同步升级 | `tmp/gen_text_anim_video.py` | 6×6 网格，每格标注"动画名 + 字体名 + 特效名" | 预览视频可播放，标注清晰可读 |

**P0 风险检查点**:
- [ ] AE_SAFE_FONTS 映射覆盖所有 50 款字体
- [ ] JSX 中枚举属性使用 BlendingMode.ADD 等枚举对象，禁止裸数字
- [ ] return 语句与后续代码同行，避免 ASI 陷阱
- [ ] 预览 RGBA 管线全程 RGBA 模式

### P1 — 三维矩阵完善 + 预览验证

**目标**: 完成 30 套特效 × 36 种动画的完整 JSX 实现 + 自动化预览验证

| 任务 | 文件 | 交付物 | 验证标准 |
|------|------|--------|----------|
| P1-1 补全 30 套 EFFECT_COMBOS 的 JSX 模板 | `core/jsx_keyframe_animator.py` | 每种效果器的完整参数映射 | 30/30 效果器可生成 JSX |
| P1-2 场景匹配扩展到全量 | `core/jsx_keyframe_animator.py` | SmartMatcher 覆盖所有 best_for 标签 | 任意 scene_tag 都能返回合理组合 |
| P1-3 强度分级联动 | `core/jsx_keyframe_animator.py` | AnimationIntensity 影响幅度/时长/效果器参数 | subtle/moderate/intense 三档视觉差异明显 |
| P1-4 自动化预览生成 | `tmp/gen_text_anim_video.py` | 按三维矩阵自动生成多组预览视频 | 每组预览展示特效+动画的完整效果 |
| P1-5 Ground Truth 对比验证 | `tests/` | 与 textFX_Showcase.jsx 基准案例的视觉对比 | 6 个 verified 基准案例全部通过 |

**P1 风险检查点**:
- [ ] Bridge 通信使用原子写入 (os.replace)，防止竞态
- [ ] alert/confirm 模态框零调用，信息走 JSON 返回
- [ ] FFmpeg stderr 使用 encoding='utf-8', errors='ignore'
- [ ] 循环动画全部持续循环，禁止一次性入场后静止
- [ ] 中间文件使用 uuid 目录，禁止跨调用缓存冲突

### P2 — 智能导演集成 + 管线闭环

**目标**: 与 `integrations/smart_director.py` 深度集成，实现场景节奏驱动的自动文字特效分配

| 任务 | 文件 | 交付物 | 验证标准 |
|------|------|--------|----------|
| P2-1 智能导演集成 | `integrations/smart_director.py` | 根据镜头强度/情绪自动选择文字组合 | 不同强度镜头自动分配不同特效+动画 |
| P2-2 Resolve 混合管线适配 | `integrations/resolve_ae_resolve_pipeline.py` | 多层文字系统的 AE→Resolve 传递 | Resolve 时间线中文字层位置和时长正确 |
| P2-3 预设覆盖率追踪升级 | `core/jsx_keyframe_animator.py` | PresetTracker 追踪三维组合覆盖率 | 覆盖率报告包含 特效×动画×字体 三维 |
| P2-4 经验闭环 | memory | 更新 experience_lessons | 实施中发现的新陷阱全部记录 |

**P2 风险检查点**:
- [ ] Resolve SetRenderSettings 先切换 Deliver 页
- [ ] Resolve 渲染使用 FFmpeg 转码方案（Format 设置无效）
- [ ] fuscript.exe 不支持 -e 内联，必须写文件执行
- [ ] BGM 使用用户音频素材库，非参考视频音轨

---

## 四、预览验证机制

### 4.1 预览视频规格

```
分辨率: 1920×1080
帧率: 30fps
时长: 12s (6×6 网格，每格 2s 展示)
网格: 6列 × 6行 = 36 种动画
每格标注:
  ┌─────────────────────┐
  │ [动画英文名]         │ ← 10pt, 灰色
  │ [动画中文名]         │ ← 22pt, 白色, 动画展示文字
  │ Font: [字体名]       │ ← 9pt, 青色
  │ FX: [特效名]         │ ← 9pt, 橙色
  │ Intensity: ●●○       │ ← 9pt, 强度指示
  └─────────────────────┘
```

### 4.2 预览渲染规则

1. **RGBA 管线**: `Image.new('RGBA', ...)` 全程，最终 `convert('RGB')` 输出
2. **循环动画**: 所有动画使用 `(at % period) / period` 无限循环
3. **振幅下限**: 位移 ≥ 20px，缩放 ≥ 0.4x 变化，透明度 0-255 全范围
4. **字体差异**: 每格使用匹配的专业字体（非统一微软雅黑）
5. **特效模拟**: 在 PIL 中模拟 Glow(外发光)、RGB分离(双色偏移)、模糊等效果
6. **编码**: `subprocess.run(cmd, encoding='utf-8', errors='ignore')`

### 4.3 预览验证流程

```
1. 运行 gen_text_anim_video.py → 输出 text_animation_preview.mp4
2. 提取 4 个时间点帧 (1s, 4s, 7s, 10s)
3. 人工检查: 每格是否有明显动态变化
4. 对比: 与上次预览的文件大小差异 (应增大，说明效果更丰富)
5. 标注检查: 每格文字标注是否清晰可读
```

---

## 五、开发前强制检查清单

> **任何相关任务开工前，必须逐项确认以下清单。禁止在未查阅历史经验的情况下直接开始新开发。**

### 5.1 开发前：经验检索（必须执行）

```
□ 1. 检索 memory → task_summary_experience 中与文字动画/特效相关的所有经验
□ 2. 检索 memory → common_pitfalls_experience 中三大类陷阱:
     □ AE ExtendScript 与缓存冲突 (6条)
     □ FFmpeg 与 Resolve 自动化 (10条)
     □ Bridge 竞态与编码环境 (10条)
□ 3. 检索 memory → experience_lessons / skill_experience 中的操作技巧
□ 4. 确认本方案第四节"防坑清单"中所有条目已理解
```

### 5.2 AE ExtendScript 防坑清单

| # | 陷阱 | 规则 | 来源 |
|---|------|------|------|
| AE-1 | 字体名空格 | 所有字体名必须经 `ae_safe_font_name()` 处理，"Arial Narrow" → "ArialNarrow" | memory:f626f055 |
| AE-2 | 枚举属性裸数字 | 混合模式用 `BlendingMode.ADD`，对齐用 `ParagraphJustification.CENTER_JUSTIFIED`，禁止 `.setValue(12)` | memory:40c09aef |
| AE-3 | ASI 换行 | `return` 与后续代码必须同行: `return (function(){...})();` | memory:423556dc |
| AE-4 | 属性访问模式 | 统一使用 matchName 链: `layer.property("ADBE Transform Group").property("ADBE Opacity")` | 实测验证 |
| AE-5 | 模态框冻结 | 脚本中禁止 `alert()`/`confirm()`，信息一律走 JSON 返回值 | memory:88d6508a |

### 5.3 Bridge 通信防坑清单

| # | 陷阱 | 规则 | 来源 |
|---|------|------|------|
| BR-1 | 文件轮询竞态 | 使用 `os.replace(tmp, target)` 原子写入，发送间隔 ≥ 1.2s | memory:ca915be3 |
| BR-2 | 注入方式 | 命令行 `-r script.jsx` 无效，必须通过 Bridge 的 `$.evalFile()` 或 `executeAtomScript` | memory:0fb19811 |
| BR-3 | 冻结恢复 | alert 冻结后只能通过 AE UI 关闭对话框恢复，命令行注入无效 | memory:88d6508a |
| BR-4 | 响应判定 | 以 `status` 字段为准（`status="success"`），非 `success` 字段 | memory:0fb19811 |

### 5.4 PIL/FFmpeg 预览防坑清单

| # | 陷阱 | 规则 | 来源 |
|---|------|------|------|
| PIL-1 | RGBA 管线 | 全程 `Image.new('RGBA', ...)`，最终 `convert('RGB')` 输出，否则 alpha 通道失效 | 实测验证 |
| PIL-2 | 中文字体路径 | 使用绝对路径 `C:/Windows/Fonts/msyhbd.ttc`，相对路径找不到 | 实测验证 |
| PIL-3 | 缩放/旋转合成 | 渲染到临时 RGBA 层 → resize/rotate → `paste(tmp, (x,y), tmp)` 用 tmp 做 mask | 实测验证 |
| FF-1 | stderr 编码 | `subprocess.run(cmd, encoding='utf-8', errors='ignore')` | memory:53e23d8b |
| FF-2 | 帧序列输入 | `ffmpeg -framerate 30 -i frame_%04d.png -c:v libx264 -pix_fmt yuv420p` | 实测验证 |
| FF-3 | 循环动画 | 所有动画使用 `(at % period) / period`，禁止一次性播放后静止 | 用户反馈 |
| FF-4 | 振幅下限 | 位移 ≥ 20px，缩放变化 ≥ 0.4x，透明度 0-255 全范围 | 用户反馈 |

### 5.5 Resolve 混合管线防坑清单

| # | 陷阱 | 规则 | 来源 |
|---|------|------|------|
| RS-1 | SetRenderSettings | 必须先切换到 Deliver 页 + 加载预设，否则设置无效 | memory |
| RS-2 | Format 设置 | Resolve Format 设置无效，统一使用 FFmpeg 转码方案 | memory |
| RS-3 | Quick Export | `.mov` 容器有陷阱，注意输出格式选择 | memory |
| RS-4 | 超时处理 | 自动化脚本可能超时但 UI 显示完成，需额外验证 | memory |
| RS-5 | fuscript | `fuscript.exe` 不支持 `-e` 内联，必须写文件再执行 | memory |
| RS-6 | 缓存冲突 | 中间文件使用 uuid 唯一目录，禁止固定目录名缓存 | memory:fe0cd042 |

### 5.6 开发后：经验闭环

```
□ 1. 实施过程中发现的新陷阱 → 立即创建 memory (common_pitfalls_experience)
□ 2. 任务完成后的经验总结 → 更新 memory (task_summary_experience)
□ 3. 检查本检查清单是否需要补充新条目
□ 4. 确认 PresetTracker 覆盖率报告已生成
```

---

## 六、最佳适用场景标注表

> 基于 Ground Truth 基准案例 (verified=True) + 漫剪/AMV 实际制作经验

| 特效+动画组合 | 最佳场景 | 对标案例 | 强度 |
|--------------|---------|---------|------|
| 赛博故障 + 冲击震动 | 游戏标题、电竞开场 | S1 (Cyber Glitch) | intense |
| 水墨书法 + 波浪入场 | 文化片头、古籍引用 | S2 (Ink Calligraphy) | subtle |
| 霓虹脉冲 + 霓虹闪烁 | 夜店风格、音乐视频 | S3 (Neon Pulse) | moderate |
| 全息HUD + 逐字波浪 | 科幻界面、数据展示 | S4 (Hologram HUD) | subtle |
| 元素对比 + 弹性过冲 | 热血标题、战斗场景 | S5 (Fire & Ice) | intense |
| 金色LOGO + 弹簧缩放 | 品牌片尾、颁奖典礼 | S6 (Golden Logo) | moderate |
| RGB分离 + 故障闪烁 | 潮流视觉、故障艺术 | effect_rgb_split | intense |
| 金属浮雕 + 多米诺骨牌 | 高端品牌、工业力量 | effect_metallic_bevel | moderate |
| 极光幻彩 + 螺旋入场 | 梦幻场景、冥想视频 | effect_aurora | subtle |
| 烈焰燃烧 + 动态打字 | 热血混剪、战斗高潮 | effect_fire_burn | intense |

---

## 七、关键文件清单

| 文件 | 角色 | 改动类型 |
|------|------|---------|
| `core/jsx_keyframe_animator.py` | 核心引擎 | **新增**: EffectLayerBuilder, SmartMatcher, 集成到 AnimationOrchestrator |
| `tmp/gen_text_anim_video.py` | 预览渲染 | **重写**: 36种动画 + 字体匹配 + 特效模拟 + 标注系统 |
| `scripts/build_text_preset_matrix.py` | 数据库 | **只读**: 提供 EFFECT_COMBOS + ENTRANCE_ANIMATIONS + FONT_LIBRARY |
| `scripts/apply_font_design.py` | 字体策略 | **只读**: 提供 FONT_STRATEGY 11 类分类规则 |
| `puppet-automation/src/services/text_effect_service.py` | 参考实现 | **参考**: 多层架构(TXT_/GLOW_/RGB_/GRAD_)的 JSX 模式 |
| `video/text_animation_engine.py` | 参考实现 | **参考**: PSTextEffectGenerator 的图层样式 JSX 模板 |
| `integrations/smart_director.py` | 智能导演 | **P2改动**: 集成 SmartMatcher 调用 |

---

## 附录 A: 历史经验索引

### 已确认的 26 条踩坑记录（按类别）

**AE ExtendScript (6条)**:
字体名空格、枚举裸数字、ASI换行、属性matchName、模态框冻结、缓存冲突

**FFmpeg/Resolve (10条)**:
SetRenderSettings顺序、Format无效、Quick Export mov、超时假完成、fuscript -e、zoompan d=1、时间变量、lerp不支持、滤镜变量、ffprobe空结果

**Bridge竞态/编码 (10条)**:
轮询竞态原子写入、注入方式、冻结恢复、status判定、alert冻结、subprocess编码、PowerShell引号、emit_ok失效、PR app.execute、Resolve Python API

### 已确认的 5 条操作技巧

向AE注入JSX的正确方式、视频饱和度1.5x平衡点、饱和度增强与scene检测平衡、文件轮询IPC根治方案、AE addComp第4参数是pixelAspect

---

*文档结束。P0+P1+P2 全部验收完成 (2026-08-05)，一体化整合方案收官：空间层(特效质感) × 时间层(动画运动) × 智能导演(场景节奏) 三维闭环已打通。*
