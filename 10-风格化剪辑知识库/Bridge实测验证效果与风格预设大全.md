# Bridge 实测验证效果与风格预设大全

> 实测环境: AE 2025 (25.3x71) 中文版 | Bridge文件轮询 | aerender渲染验证
> 验证日期: 2026-07-25
> 验证标准: Bridge执行成功 + aerender输出 >100KB

---

## 一、已验证特效清单 (ALL PASS)

### 1.1 粒子特效 (4项)

| 效果ID | 名称 | 渲染大小 | 核心技术 |
|--------|------|----------|----------|
| fire_sparks | 火焰火花 | >100KB | CC Particle World, 暖色系, 上升重力 |
| magic_burst | 魔法爆发 | >100KB | CC Particle World, 放射状, 紫色系 |
| cyber_rain | 电子雨 | >100KB | CC Particle World, 下落, 青色系 |
| ember_float | 余烬漂浮 | >100KB | CC Particle World, 慢速漂浮, 橙色 |

### 1.2 文字特效 (7项)

| 效果ID | 名称 | 渲染大小 | 核心技术 |
|--------|------|----------|----------|
| flip3d | 3D翻转 | >100KB | Text Animator + Rotation Y |
| typewriter | 打字机 | >100KB | Text Animator + Opacity逐字 |
| blur_fade | 模糊淡入 | >100KB | Gaussian Blur + Opacity关键帧 |
| scanline | 扫描线 | >100KB | 线性遮罩 + 位置动画 |
| wave | 波浪 | >100KB | Text Animator + Position Y + 延迟 |
| elastic_scale | 弹性缩放 | >100KB | Scale关键帧 + 过冲 |
| tracking | 字间距 | >100KB | Text Animator + Tracking |

### 1.3 高级技法 (Phase 2 新增, 10项)

| 测试ID | 名称 | 渲染大小 | 核心技术 |
|--------|------|----------|----------|
| beat_flash | 快闪/卡点 | 2145KB | 表达式阶梯闪烁 + 缩放脉冲 |
| particular_basic | Particular基础粒子 | 666KB | tc Particular-XXXX 属性设置 |
| vignette | 暗角+胶片颗粒 | 9167KB | 反转椭圆遮罩+大羽化 + Fractal Noise |
| stroke_anim | 描边动画 | 2989KB | Shape Layer + Trim Paths |
| part_layer_emit | Particular图层发射器 | 128KB | tc Particular-0782=6 + 物理场 |
| 3d_rotation | 逐字3D旋转 | 271KB | Text Animator + ADBE Text Rotation Y |
| time_remap | 时间重映射+运动模糊 | 730KB | precomp + timeRemapEnabled |
| color_grade | 调色链路 | 2646KB | CurvesCustom + Hue/Sat + Vignette |
| camera_dof | 摄像机景深 | 4258KB | Camera DOF + Focus Distance动画 |
| path_text | 路径文字动画 | 6090KB | Mask路径 + Text Path Options |

---

## 二、关键参数映射 (实测验证)

### 2.1 Trapcode Particular

```
matchName: "tc Particular"
addProperty: "Trapcode Particular" 或 "tc Particular"
属性结构: 完全扁平 (7756个属性均在一级)
访问格式: fx.property("tc Particular-XXXX")
```

| 参数ID | 中文名 | 范围 | 备注 |
|--------|--------|------|------|
| tc Particular-0782 | 发射器类型 | [1,7] | 1=Point,2=Box,3=Sphere,4=Grid,5=Light,6=Layer |
| tc Particular-0146 | 粒子/秒 | - | 发射速率 |
| tc Particular-0011 | 速率 | - | 粒子初速度 |
| tc Particular-0012 | 速率随机 | - | 速度随机量 |
| tc Particular-0002 | 生命周期 | - | 秒 |
| tc Particular-0065 | 生命随机 | - | % |
| tc Particular-0027 | 大小 | - | 粒子尺寸 |
| tc Particular-0074 | 大小随机 | - | % |
| tc Particular-0033 | 不透明度 | - | % |
| tc Particular-0017 | 重力 | - | 正=下落,负=上升 |
| tc Particular-0018 | 空气阻力 | - | |
| tc Particular-0113 | 方向 | **[1,6]** | ⚠️ 不是角度! 1=全方向 |
| tc Particular-0010 | 扩展(Spread) | **[0,100]** | ⚠️ 不是0-360! 百分比 |
| tc Particular-0070 | 颜色 | - | [R,G,B] 数组 |
| tc Particular-0783 | 作为字符串 | [0,1] | Layer Emitter相关 |
| tc Particular-0786 | 行为 | [1,2] | Layer Emitter行为 |

### 2.2 CC Particle World

```
matchName: "CC Particle World"
addProperty: "CC Particle World"
访问格式: fx.property("CC Particle World-XXXX")
```

| 参数ID | 用途 | 典型值 |
|--------|------|--------|
| CC Particle World-0004 | 粒子类型 | 2-4 |
| CC Particle World-0005 | 粒子样式 | 3-5 |
| CC Particle World-0007 | 发射器X | 960 |
| CC Particle World-0008 | 发射器Y | 1100(底部) |
| CC Particle World-0015 | 生命周期 | 3-5 |
| CC Particle World-0016 | 速度 | 0.3-1.0 |
| CC Particle World-0018 | 重力 | -0.3~0.5 |
| CC Particle World-0023 | 大小 | 3-6 |
| CC Particle World-0027 | 不透明度 | 40-80 |
| CC Particle World-0029 | 出生色 | [R,G,B] |
| CC Particle World-0030 | 死亡色 | [R,G,B] |
| CC Particle World-0039 | 不透明度映射 | 1 |

### 2.3 Glow (ADBE Glo2)

```
matchName: "ADBE Glo2"
⚠️ 必须用属性索引, 禁止用英文显示名(中文版)
```

| 索引 | 用途 | 典型值 |
|------|------|--------|
| property(2) | Glow Threshold | 0-0.2 |
| property(3) | Glow Radius | 50-150 |
| property(4) | Glow Intensity | 1.5-3.0 |

### 2.4 Hue/Saturation (ADBE HUE SATURATION)

```
matchName: "ADBE HUE SATURATION"
⚠️ property(1)=通道控制[1-7], property(2)=通道范围(CUSTOM不可设)
```

| 索引 | 中文名 | 范围 | 备注 |
|------|--------|------|------|
| property(1) | 通道控制 | [1,7] | 下拉选择, 不要设! |
| property(2) | 通道范围 | CUSTOM | ⚠️ 不可setValue! |
| property(3) | 主色相 | -180~180 | Master Hue |
| property(4) | 主饱和度 | -100~100 | Master Saturation |
| property(5) | 主亮度 | -100~100 | Master Lightness |
| property(6) | 彩色化 | 0-100 | Colorize开关 |

### 2.5 Curves

```
正确matchName: "ADBE CurvesCustom" (不是 "ADBE Curves")
属性数: 3 (通道/曲线/合成选项)
```

### 2.6 Camera DOF

```javascript
var camOpts = cam.property('ADBE Camera Options Group');
camOpts.property('ADBE Camera Depth of Field').setValue(1); // 启用
camOpts.property('ADBE Camera Focus Distance').setValue(500); // 焦距
camOpts.property('ADBE Camera Aperture').setValue(5); // 光圈(模糊程度)
```

### 2.7 Text Path (路径文字)

```javascript
// 1. 在文字层创建遮罩路径
var mk = txt.property('ADBE Mask Parade').addProperty('Mask');
mk.maskMode = MaskMode.NONE; // 不影响显示
// 2. 设置路径选项
var pathOpts = tp.property('ADBE Text Path Options');
pathOpts.property('ADBE Text Path').setValue(1); // Mask 1
// 3. 动画: First Margin
pathOpts.property('ADBE Text First Margin').setValueAtTime(0, -600);
pathOpts.property('ADBE Text First Margin').setValueAtTime(2, 0);
```

---

## 三、风格预设包 (Phase 3 验证)

### 3.1 Cyberpunk (8920 KB)

```
入场: 逐字3D旋转 (Text Animator + Rotation Y, offset -100→100)
持续: Glow闪烁表达式 (70+30*sin(t*15))
转场: 快闪白帧 (@2s, @3.5s, opacity表达式脉冲)
粒子: Trapcode Particular (电子雨, 青色, 重力下落)
调色: 无(靠粒子+发光)
```

### 3.2 Cinematic (9317 KB)

```
入场: Shape描边动画 (Trim Paths End 0→100)
持续: 3D文字 + Camera DOF (Focus Distance=500)
转场: 自然淡入淡出
粒子: 胶片颗粒 (Fractal Noise小尺寸+scale放大+Overlay+wiggle)
调色: Hue/Saturation(3/4/5) + 暗角(反转遮罩+羽化250)
```

### 3.3 Neon Dream (5495 KB)

```
入场: 路径文字 (Mask弧形路径 + First Margin动画)
持续: 强发光 (Glow Radius=150, Intensity=3.0)
转场: 缩放脉冲 (scale表达式 sin曲线)
粒子: CC Particle World (彩色漂浮, 粉紫色系)
调色: 无(靠发光+粒子颜色)
```

### 3.4 Epic Extreme (4849 KB)

```
入场: 缩放冲击 (scale [300,300]→[100,100] 0.3s)
持续: Particular图层发射器 (EmitterType=6, 火花上升)
转场: 快闪 (@1.5s, @3s, @4.2s)
粒子: Trapcode Particular Layer Emitter + Glow
调色: 运动模糊(comp.motionBlur=true)
摄像机: DOF (Focus=2000, Aperture=3)
```

---

## 四、常见陷阱与修复

| 陷阱 | 错误信息 | 修复 |
|------|----------|------|
| Particular Direction=0 | "值 0 在 1 至 6 的范围外" | tc Particular-0113 范围[1,6], 设1=全方向 |
| Particular Spread=180 | "值 180 在 0 至 100 的范围外" | tc Particular-0010 范围[0,100], 是百分比 |
| Hue/Sat property(1) | "值 -8 在 1 至 7 的范围外" | property(1)是通道下拉, 用property(3/4/5) |
| Hue/Sat property(2) | "CUSTOM_VALUE 尚未实施" | property(2)是通道范围, 不可设值 |
| scale.setValueAtTime(t, 300) | "值不是数组" | scale需要数组 [300,300] |
| Fractal Noise Scale=300 | "值 300 在 0 至 1 的范围外" | 不设Scale, 改用小Solid+layer.scale放大 |
| Curves matchName | "ADBE Curves" 不存在 | 正确: "ADBE CurvesCustom" |
| Glow用英文名 | 中文版找不到属性 | 必须用property(2/3/4)索引 |

---

## 五、ES3 语法约束清单

```
✅ var (不用 let/const)
✅ function(){} (不用箭头函数)
✅ 字符串拼接 (不用模板字符串)
✅ opacity 0-100 (不是0-1)
✅ 中文版用 matchName 或索引访问属性
✅ addProperty("Trapcode Particular") 添加Particular
✅ fx.property("tc Particular-XXXX") 设参数
✅ Glow: gf.property(2/3/4) 索引访问
```

---

## 六、文件位置

| 文件 | 路径 |
|------|------|
| 风格预设工程(V1) | D:\AE-Work\StylePresets.aep |
| 风格预设工程(V2) | D:\AE-Work\StylePresets_V2.aep |
| Phase2工程 | D:\AE-Work\TextFX_Phase2.aep |
| 渲染输出(Phase2) | D:\AE-Work\output\phase2\ |
| 渲染输出(Phase3 V1) | D:\AE-Work\output\phase3\ |
| 渲染输出(Phase3 V2) | D:\AE-Work\output\phase3_v2\ |
| **最终合并视频** | **D:\AE-Work\output\phase3_v2\风格预览_全部风格_v2_20260725.mp4** (8.2MB) |
| 测试脚本 | temp\test_phase2_*.py, temp\test_phase3_*.py |

---

## 七、V2 增强版风格预设 (专业漫剪级, 2026-07-25)

> 对标外网 AMV/Manga Edit 视觉水准，新增: 色差分离/速度线/弹性表达式/帧冻结/多层粒子/摄像机震动

| 风格 | 渲染大小 | 新增技法 |
|------|----------|----------|
| Cyberpunk_V2 | 9240KB | RGB色差分离 + 故障抖动 + 弹性缩放 + 速度线 + 双层粒子 |
| Cinematic_V2 | 9070KB | DOF拉焦动画 + 信宽比黑边 + 强暗角(80%) + 强胶片颗粒 |
| NeonDream_V2 | 5415KB | 多层发光(内+外) + 弹性副标题 + 双层彩色粒子 |
| EpicExtreme_V2 | 8813KB | 帧冻结微震 + 16条集中线 + Particular爆发 + 摄像机震动 |
| **EpicExtreme_V3** | **5151KB** | **节拍式爆发(0→4000→5000→3500) + 3层粒子叠加 + 物理增强 + 20条速度线 + 衰减震动** |

**合并输出规范:**
- V2: `风格预览_全部风格_v2_20260725.mp4`
- **V3: `风格预览_全部风格_v3_20260725.mp4`** (最新)
- 每段前0.5s黑场+风格名称字幕
- ffmpeg concat + libx264 CRF18

**V2新发现参数范围:**
- `tc Particular-0012`(速率随机): [0,100]，不能设>100

---

## 八、EpicExtreme V3 深度优化详解 (2026-07-25)

> 对标外网专业漫剪 AMV 的 Extreme/Epic 风格，核心改进: 持续喷射→节拍式爆发

### 8.1 节拍式粒子爆发模式

```
时间轴 (5s, 30fps):
  0.0s ─── 0.4s ── [0.5s PEAK] ── 1.0s ─── 1.9s ── [2.0s PEAK] ── 2.5s ─── 3.4s ── [3.5s PEAK] ── 4.0s ─── 5.0s
  rate=0       0      4000→200→0       0        0      5000→300→0       0        0      3500→150→0       0        0

爆发模式: 2-3帧内从0飙升到4000-5000, 然后快速衰减到0
```

### 8.2 三层粒子架构

| 层 | 引擎 | 特征 | 物理 |
|------|------|------|------|
| P_Large | Trapcode Particular | 大颗粒(8px), 慢速, 橙红 | 重力=120, 空气=40 |
| P_Small | Trapcode Particular | 小颗粒(2px), 快速, 金黄 | 重力=200, 空气=60 |
| P_Trail | CC Particle World | 拖尾余烬, 持续漂浮 | 速度=0.6, 重力=0.3 |

### 8.3 完整效果栈 (9层)

```
[Camera]     DOF + 衰减式震动 (35-45px, 0.5s衰减)
[Flash]      多重闪白脉冲 (@0.5/2.0/3.5, 双闪/三闪)
[Text]       EPIC + 弹性缩放 + 帧冻结微震
[SubText]    EXTREME + Glow
[SpeedLines] 20条放射线 + 爆发同步opacity衰减
[P_Small]    Particular 快速小粒子 (rate peak 8000)
[P_Large]    Particular 大颗粒 (rate peak 5000)
[P_Trail]    CC Particle World 环境余烬
[BG]         Fractal Noise 暗纹理
```

---

## 九、音画同步实战训练 (2026-07-25)

> 首次实现: 音频分析→节拍提取→关键帧自动生成 的完整pipeline
> BGM: Lorde - The Love Club (BPM=184.6) | 40s | 渲染输出 22.78MB

### 9.1 音频驱动链路 (已验证)

```
[源文件] MP3/FLAC/WAV
    ↓ ffmpeg (-ss -t -acodec pcm_s16le -ar 44100)
[WAV 44.1kHz 16bit stereo]
    ↓ librosa.beat.beat_track()
[BPM + beat_times[] + downbeats[]]
    ↓ librosa.feature.rms() + 峰值检测
[energy_peaks[] (time, intensity)]
    ↓ Python生成JSX关键帧
[AE合成: 文字动画+粒子爆发+闪白+震动 全部对齐节拍]
    ↓ aerender
[MP4输出]
```

### 9.2 节拍→效果映射规则

| 音乐事件 | 触发效果 | 参数 |
|----------|----------|------|
| **Downbeat(强拍)** | 文字入场触发 | 弹性缩放/3D翻转/打字机 |
| **Energy Peak(能量峰)** | Particular爆发 + 闪白 + 速度线 + 摄像机震动 | rate 0→4000-6000→0 (2-3帧) |
| **段落切换** | 转场(闪白双闪+震动) + 新文字段 | 0.5s过渡 |
| **持续节拍** | 环境粒子漂浮 + 暗角呼吸 | CC Particle World continuous |

### 9.3 40s合成结构 (15层, 22.78MB)

```
时间轴: 0─────1.66─────10.8─────19.92─────29.06─────40s
        [Intro] [Seg2:ALL EYES] [Seg3:ON ME] [Seg4:FEEL IT] [Seg5:EVERYTHING]
        黑场    弹性缩放+Glow   3D翻转+打字机  模糊淡入+扫描线  缩放冲击+帧冻结

粒子爆发: @5.25s(4000) @11.77s(5000) @15.69s(4500) @29.06s(6000) @34.27s(4000)
闪白帧:   @1.34 @2.65 @5.25 @9.17 @11.77 @15.69 @29.06(三闪) @34.27
摄像机震: @5.25(25px) @11.77(30px) @29.06(40px) @34.27(25px)
```

### 9.4 关键发现

- **源文件陷阱**: `.flac`扩展名实际可能是MP3(ID3头), 需检查文件头魔数
- **ffmpeg路径**: 系统PATH中 `C:\ffmpeg\bin\ffmpeg.exe` (非项目external目录)
- **WAV导入AE**: `new ImportOptions(File)` + `app.project.importFile()` 直接可用
- **40s合成渲染**: aerender约需3-4分钟, 输出22.78MB(视觉内容极其丰富)
- **BPM 184.6**: 属于燃系AMV范围(140-180+), 每拍0.325s, 每4拍1.3s一个强拍
- **librosa精度**: beat_track精度约±20ms, 对AE关键帧足够(1帧=33ms@30fps)

### 9.5 文件位置

| 文件 | 路径 |
|------|------|
| AE工程 | D:\AE-Work\AudioTraining.aep |
| WAV音频 | D:\AE-Work\output\audio_training\all_eyes_on_me_40s.wav |
| 节拍数据 | D:\AE-Work\output\audio_training\beat_data.json |
| 渲染输出 | D:\AE-Work\output\audio_training\all_eyes_text_anim.mp4 (22.78MB) |
| 构建脚本 | temp\build_audio_training.py |
| 分析脚本 | temp\audio_analyze.py |
