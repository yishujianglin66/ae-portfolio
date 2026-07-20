# AE-MCP 创作知识体系 v2.0

## 🎯 核心理念

你不是在调用 API，你是一名专业的 After Effects 动态设计师。每次创作应该：
1. **先选预设，再做微调** — 5000 个预设覆盖了 90% 的常见效果
2. **分层组合** — 文字 + 粒子 + 光效 + 调色，层层叠加
3. **动画要有节奏** — 快入慢出、弹性回弹、延迟错位
4. **细节决定品质** — 动态模糊、景深、光晕、纹理
5. **⛔ 粒子效果不突兀的秘诀：Life曲线 + 随机性 + Turbulence + Aux系统**

---

## 🎬 动画十二法则（在 AE 中的实践）

| 法则 | AE 实现 |
|------|---------|
| 缓入缓出 | 关键帧 Easy Ease (F9)，或表达式 `ease(t, tMin, tMax, valMin, valMax)` |
| 预备动作 | 先反方向小位移再正向，如先缩小到 80% 再放大到 120% |
| 跟随动作 | 主体停后附属物继续动，用 `value + wiggle(0, amp) * decay` |
| 夸张 | 缩放时 overshoot：`linear(t, 0, 0.7, 80, 115) + linear(t, 0.7, 1, 115, 100)` |
| 节奏 | 不同的关键帧间隔：重要动作慢(多帧)、过渡动作快(少帧) |
| 弧线运动 | 位置 X 和 Y 用不同相位的 sin/cos，而非直线 |
| 次要动作 | 主图层 + 子图层（粒子、光斑、碎片）辅助 |
| 错位延迟 | 多图层用 `index * 0.1` 秒递增延迟 |

---

## 🔥 Particular 核心知识——决定粒子是否"突兀"的关键

> **有机粒子运动 = 随机性 + 力场 + 生命周期渐变 + 多层粒子结构**

### 🚨 最常见错误（导致粒子突兀）

| 错误做法 | 为什么错 | 正确做法 |
|----------|---------|----------|
| 所有参数用默认值 | 默认值=机械感 | 每个参数都微调 |
| Velocity Random = 0 | 所有粒子同速=CG感 | 设 20-50% |
| 不加 Opacity over Life | 粒子突然消失=突兀 | 淡入5-15% + 淡出15-30% |
| 不加 Size over Life | 粒子大小不变=不自然 | 钟形或衰减曲线 |
| Size Random = 0 | 所有粒子一样大=假 | 设 30-60% |
| 不加 Turbulence Field | 粒子直线运动=真空 | Amount 5-30, Scale 50-100 |
| 不加 Air Resistance | 粒子速度不变=不真实 | 0.5-3.0 |
| 不开启 Motion Blur | 运动轨迹不连贯 | Shutter Angle 180°-360° |

### ✅ Particular 黄金参数模板

#### 自然粒子三要素
```
1. Life Random [%] = 30-60%         ← 不同时死亡
2. Size Random [%] = 30-60%         ← 大小差异
3. Opacity Random [%] = 20-50%      ← 明暗层次
```

#### 生命周期三曲线（必须设置！）
```
Size over Life:
  - 烟雾/魔法：钟形 (0→大→小→0)
  - 火花/碎屑：衰减曲线 (大→0)
  - 漂浮灰尘：平坦 + 尾部淡出

Opacity over Life:
  - 始终加淡入！前 5-15%: 0→100
  - 始终加淡出！后 15-30%: 100→0
  - ⚠️ 粒子不应 "pop" 出现或 "click" 消失

Color over Life:
  - 火焰：白→黄→橙→红→暗
  - 魔法：亮金→暖橙→暗金
  - 设置 Color Random 5-15%
```

#### 物理系统（让运动有机）
```
Gravity:           根据场景 (-20漂浮 ~ +200重落)
Air Resistance:    0.5-3.0 (永远不要0)
Wind X/Y/Z:        10-50 (方向性漂移)
Turbulence Field:
  Amount:          5-30 (有机微扰) / 50-100 (混沌风暴)
  Scale:           小(5-20)=高频抖动 / 大(50-100)=缓慢涌动
  Evolution:       10-30°/秒 (持续变化)
  Octave Scale:    增加细节层级
Spin Amplitude:    10-30% Random (真实翻滚)
```

#### Aux System（次级粒子——专业级秘诀）
```
Emit:             "On Death" (碎片/余烬) 或 "Continuously" (尾迹/烟缕)
Life:             短于主粒子 (0.5-1.5s)
Size:             小于主粒子 (2-10px)
Type:             Cloudlet(烟雾) / Streaklet(火花) / Sphere(光点)
Gravity:          独立重力设置（通常高于主粒子）
```

### 🎯 Particular 自然现象速查

| 效果 | Emitter | 粒子/秒 | 速度 | 重力 | 空气阻力 | Turbulence | Size over Life | Aux |
|------|---------|---------|------|------|----------|------------|----------------|-----|
| **魔法飘浮** | Sphere | 80-200 | 20-50 | -0.5~-20 | 0.5 | Amount 5, Scale 80 | 钟形柔和 | 持续小光点 |
| **烟雾** | Point/Box | 50-150 | 30-80 | -5(上升) | 3.0 | Amount 15, Scale 30 | 钟形 | On Death Cloudlet |
| **火花** | Point | 200-500 | 100-300 | 200 | 0.2 | Amount 20, Scale 10 | 衰减 | On Death Streaklet |
| **雪花** | Box(大) | 50-100 | 10-30 | 30 | 0.8 | Amount 8, Scale 100 | 平坦+尾淡 | 无 |
| **水下微粒** | Box | 30-80 | 5-15 | 5 | 2.0 | Amount 25, Scale 50 | 平坦 | 无 |
| **金色光点** | Sphere | 100-200 | 20-40 | -10 | 0.5 | Amount 8, Scale 60 | 钟形 | 持续Star |
| **火焰余烬** | Point | 100-300 | 50-150 | -50(上升) | 1.5 | Amount 30, Scale 15 | 衰减 | On Death |

### 📐 粒子设计工作流（5步法）
```
1. Emitter (发射器选型+位置) → 决定粒子"从哪来"
2. Life Cycle (Life/Size/Opacity/Color over Life曲线) → 决定粒子"怎么活怎么死"
3. Aux System (次级粒子) → 增加细节层次
4. Physics (重力/阻力/风力/Turbulence) → 决定粒子"怎么动"
5. 3D Integration (Camera/DOF/Motion Blur) → 融入空间
```

> 💡 **粒子不生硬的秘诀：永远不要跳过第2和第4步。直接设 Emitter + 粒子数 = 必然突兀。**

---

## 📂 你的 5000 个预设库速查

### 文字动画预设（最常用）
位于 `Presets/Text/` 下 20+ 子分类：
- **Animate In** — 入场：淡入、滑入、打字机、缩放弹入
- **Animate Out** — 出场：淡出、飞出、炸裂
- **Blurs** — 模糊文字（焦点漂移效果）
- **Curves and Spins** — 曲线路径 + 旋转
- **Organic** — 有机感：颤抖、飘动、呼吸
- **Mechanical** — 机械感：逐字弹出、像素化
- **3D Text** — 三维文字预设
- **Expressions** — 表达式驱动的动态文字
- **Multi-Line** — 多行文字编排
- **Scale** / **Rotation** / **Tracking** — 单项属性动画

### 中文文字预设包
位于 `其他各类实用预设/` 下：
- **优雅文本预设** — 100/200 字符的渐入排列
- **Glitch_文字预设** — 位移、拉伸、缩放、组合故障
- **文字预设--进入** — 按字符/单词/行渐入
- **文字预设--退出** — 按字符/单词/行渐出
- **干扰损坏效果** — 噪点、紊乱、数据损坏

### 粒子预设
- `Particular/Trapcode HD Presets/` — 高清粒子预设
- `Particular/Trapcode SD Presets/` — 标清粒子预设
- `Particular/talkae/Original Magic Presets/` — 魔法粒子预设包
- `Particular/talkae/Fast Magic Presets/` — 快速魔法粒子
- `Form/` — 60+ 音频可视化/3D 网格预设

### 光效预设
- `Shine/` — 50+ 体积光预设（Apparition, Blaze, Electricity...）
- SS3 预设 — 投影/光照/倒角/发光

### 转场预设（600+）
- `600组转场特效预设/` — 文字动画、视频转换、调色
- `Transitions - Dissolves/` — 溶解
- `Transitions - Movement/` — 运动
- `Transitions - Wipes/` — 擦除

### 调色预设（1500+）
- `1200组调色预设/` — Mojo、电影、黑白、老电影...
- `70种电影大片风格调色预设/` — 复古、温馨、褐色...
- `275组调色预设/`
- `动真格调色预设112组/`

---

## 🔧 高级表达式库

### 弹性动画（Elastic）
```javascript
// 弹性缓出 - 用于文字弹入、图标弹出
freq = 3; decay = 5;
amp = 0.15 * comp.width; // 振幅
t = Math.max(time - inPoint, 0);
offset = amp * Math.sin(t * freq * 2 * Math.PI) / Math.exp(t * decay);
value + [0, -offset]
```

### 呼吸浮动（Breathing Float）
```javascript
// 轻量漂浮感 - 比 wiggle 更优雅
amp = 10; freq = 0.8;
yOffset = Math.sin(time * freq * Math.PI * 2) * amp;
xOffset = Math.cos(time * freq * 1.3 * Math.PI * 2) * amp * 0.6;
value + [xOffset, yOffset]
```

### 逐字延迟入场（Character Delay）
```javascript
// 给 Source Text 的 Opacity 用
delay = 0.05; // 每个字符延迟
myIndex = textIndex; // AE内置
tStart = inPoint + myIndex * delay;
tEnd = tStart + 0.3;
ease(time, tStart, tEnd, 0, 100)
```

### 故障效果（Glitch）
```javascript
// 随机水平位移 + 色差
seed = Math.floor(time * 30);
seedRandom(seed, true);
rShift = random(-20, 20);
gShift = random(-15, 15);
bShift = random(-25, 25);
// 分别应用给 R/G/B 通道的 Position
```

### 3D 视差漂移
```javascript
// 模拟 Z 轴深度的视差运动
zDepth = index * 50; // 每层50px深度差
parallax = thisComp.layer("Camera 1").transform.position[0] * (zDepth / 1000);
value + [parallax, 0]
```

### 音频反应
```javascript
// 配合 Sound Keys 或音频振幅层
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
linear(audioAmp, 5, 50, 100, 150) // 缩放随音频变化
```

### 数学之美 - 利萨如曲线
```javascript
// 优雅的数学轨迹
center = [thisComp.width/2, thisComp.height/2];
a = 100; b = 80;
freqX = 3; freqY = 2;
phase = time * 2;
center + [a * Math.sin(freqX * phase), b * Math.cos(freqY * phase)]
```

### 逐字位置波动（Character Wave）
```javascript
// 每个字符依次弹起 - 用于文字入场动效
delay = 0.03 * textIndex;
t = Math.max(time - (inPoint + delay), 0);
amp = 50; freq = 5; decay = 8;
offset = amp * Math.sin(t * freq * 2 * Math.PI) / Math.exp(t * decay);
value - [0, offset];
```

### 惯性弹跳（Inertial Bounce - 关键帧后自动回弹）
```javascript
n = 0; f = 6;
if (numKeys > 1) {
  n = nearestKey(time).index;
  if (key(n).time > time) n--;
}
if (n > 0) {
  t = time - key(n).time;
  v = -velocityAtTime(key(n).time - 0.001) * 10;
  amp = 0.08; decay = 4;
  value + v * amp * Math.sin(f * t * 2 * Math.PI) / Math.exp(decay * t);
} else { value; }
```

### Puppet Pin Null 绑定表达式
```javascript
// 把 Puppet Pin 位置绑定到 Null 层，实现真正的父子关系
l = thisComp.layer("Pin Controller 1");
fromComp(l.toComp(l.anchorPoint));
// 用法：为每个 Pin 创建 Null，用此表达式绑定 → Null 可旋转缩放
```

---

## 🎨 效果组合配方

### 1. 电影级文字出场
```
步骤：
1. 选文字预设 "优雅文本预设/字符" 获得基础出场节奏
2. 加 Deep Glow（强度 0.8，半径 40）
3. 加 S_Glow（暖色调，柔和光晕）
4. 加提取/曲线调色（暖色风格）
5. 可选：Particular 粒子在文字周围飘散
```

### 2. 科技感 HUD 效果
```
步骤：
1. 文字预设选 "Mechanical" 风格
2. 加 S_EdgeRays（边缘发光）
3. 加 Glitch故障预设
4. 调色：蓝/青色 LUT
5. 可选：Form 做数据流背景
```

### 3. 梦幻柔焦
```
步骤：
1. Fast Bokeh（大光圈，圆形光斑）
2. S_BlurMoCurves（选择性模糊曲线）
3. 调色：粉色/紫色偏移
4. 加光斑叠加层（Lens Flare）
```

### 4. 粒子爆炸
```
步骤：
1. Particular - 选 "Explosion" 预设
2. 调整发射器类型为 Sphere
3. 加大 Particles/sec 到 2000+
4. 添加物理：Gravity 200
5. 叠加 Shine 体积光
6. 加 Fast Bokeh 景深
```

### 5. 水墨/有机流动
```
步骤：
1. Form - Base Form 选 "Layer Grid"
2. Fractal Field 加 displacement
3. 调色：去饱和 + 暖褐 LUT
4. Fast Blur 轻微柔化
5. 叠加噪点纹理
```

### 6. 金色魔法飘浮（★ 改进版——粒子不再突兀）
```
步骤：
1. 创建暗色合成 (深蓝或深紫背景)
2. Particular 发射器: Sphere, 位置 [960, 400, -200]
3. 粒子密度: 150 Particles/sec
4. 速度: 25, Velocity Random: 40%
5. 重力: -15 (向上飘), Air Resistance: 0.8
6. Turbulence Field: Amount 8, Scale 65, Evolution 15°/s
7. Size over Life: 钟形曲线 (0→5px→0)
8. Opacity over Life: 淡入+淡出 (不是突然消失!)
9. Size Random: 50%, Opacity Random: 40%
10. Aux System: 持续发射, Streaklet, Size 2px, Life 1.5s
11. 文字层加 Spring In 预设 + Shine Apparition
12. 合成级别开启 Motion Blur (Shutter 360°)
```

---

## 🏗️ 3D 图层设计与合成（2024新能力）

### AE 2024 3D 新特性
```
- Advanced 3D Renderer: 高质量抗锯齿+透明+PBR材质
- Shadow Catcher: 3D物体在2D背景上投射真实阴影
- Depth Map: 从3D场景提取深度图→DOF/雾气/深度调色
- GLB/GLTF 导入: 含骨骼动画/关键帧，可在AE内重定时
- HDR 环境光: 基于图像的照明，即时场景重新打光
- Substance 3D 集成: 20000+ 3D模型/材质/HDR可直接使用
```

### 3D 场景搭建最佳实践
```
层级结构：
  Camera (35mm or 50mm, Depth of Field ON)
  ├── Light 1 (Key Light, 主光源, Intensity 100%, Cast Shadows ON)
  ├── Light 2 (Fill Light, 补光, Intensity 30-50%, 无阴影)
  ├── Light 3 (Rim Light, 轮廓光, Intensity 60-80%, 从背面)
  ├── Null "3D Controller" (控制所有3D图层)
  │   ├── 3D 文字层
  │   ├── 3D 形状层
  │   └── E3D 模型层
  └── Shadow Catcher 层 (接收阴影的2D背景)
```

### 景深公式
```
- 大景深 (f/8-16): 文字清晰，适合标题
- 浅景深 (f/1.4-2.8): 背景虚化，适合氛围镜头
- 焦距 50mm: 标准视角
- 焦距 85mm+: 压缩空间，适合肖像
- 焦距 24mm: 广角透视，适合宏大场景
```

### 3D 摄像机动画原则
```
1. 慢推 (Slow Push): Z轴 0→200 over 4-6秒, 大气感
2. 轨道 (Orbit): 围绕目标旋转, 展示立体感
3. 视差: 前景快/背景慢 → 深度感
4. 手持感: wiggle(0.5, 3) on Position + wiggle(0.3, 0.5) on Rotation
```

---

## 🎭 角色动画：Puppet Pin + Roto + 跟踪

### Puppet Pin 工作流（木偶骨骼动画）
```
步骤：
1. Photoshop 准备角色图层 → 确保Alpha通道完整
2. 导入AE → 选中图层 → 点击 Puppet Pin Tool (Ctrl+P)
3. 在关键关节点放置 Pin：
   - 髋部(hips)、膝(knees)、踝(ankles)
   - 肩(shoulders)、肘(elbows)、腕(wrists)
   - 颈(neck)、头(head — 可选)
4. 用 Puppet Starch Tool 加固不该变形的区域
5. 调整 Mesh → Expansion + Density 控制影响范围
6. 按住 Ctrl/Cmd 拖拽 Pin → 实时录制动画
7. 选所有关键帧 → Easy Ease → Graph Editor 微调曲线
```

### Puppet Pin 高级技巧
```
- Null 绑定法: 为每个Pin创建Null，用表达式绑定 → Null可旋转/缩放/加wiggle
- IK 表达式: 3个Pin (肩→肘→腕)，一个Null控制手腕，肘自动弯
- 走步循环: 5帧 (张腿→过渡→张腿(反)→过渡→循环)
  用 loopOut() 表达式无缝循环
- Rubberhose 3 + Rubberpin: 自动骨骼绑定，适合卡通风格
- 变形控制: Starch工具+网格密度调整，防止关节处撕裂
```

### Roto Brush 3.0（AI抠像）
```
步骤：
1. 双击图层进入Layer面板
2. 选Roto Brush工具(绿色) → 涂画要保留的主体
3. 按住Alt/Option(红色) → 涂画要去掉的区域
4. 逐帧传播(空格键) → AE自动生成遮罩
5. Refine Edge工具 → 处理头发/半透明边缘
6. 调整 Feather / Shift Edge / Reduce Chatter
7. Freeze（冻结）→ 最终确认后冻结结果
```

### 绿幕抠像流程
```
1. 先画 Garbage Matte（粗略遮罩）→ 排除不需要的区域
2. 应用 Keylight (1.2) → 吸管选绿色
3. 切换到 Screen Matte 视图 → 调 Clip Black/White
4. 叠加 Key Cleaner + Advanced Spill Suppressor
5. 必要时加 Hold-out Matte 保护特定区域
6. 拍摄建议：快门1/80-1/100减少运动模糊，用无压缩素材
```

### 3D 摄像机追踪
```
步骤：
1. 选素材 → Effects → 3D Camera Tracker
2. 等待分析完成（彩色追踪点出现）
3. 选一组共面追踪点 → 右键 Create Solid/Camera/Text
4. 对多个平面重复 → 建立3D空间参考
5. 插入的2D/3D元素会自动匹配摄像机运动
6. 配合 Shadow Catcher 投射阴影到追踪场景
```

### Mocha AE 平面追踪（内置）
```
- 适合：屏幕替换、标志贴附、平面纹理
- 比点追踪更稳定，处理旋转/缩放/透视
- 追踪数据可导出为Corner Pin或Transform数据
```

---

## 🌐 GitHub 开源资源生态

### 核心项目
| 项目 | 说明 |
|------|------|
| [TheLlamainator/after-effects-mcp](https://github.com/TheLlamainator/after-effects-mcp) | ⭐ 最成熟MCP Server (25+工具) |
| [JUNKDOGE-JOE/after-effects-mcp](https://github.com/JUNKDOGE-JOE/after-effects-mcp) | ⭐22 Python MCP + CEP面板 (30工具) |
| [Dakkshin/after-effects-mcp](https://github.com/Dakkshin/after-effects-mcp) | Mask/混合模式/3D切换支持 |

### 脚本与工具集合
| 项目 | 说明 |
|------|------|
| [kyletmartinez/After-Effects-Scripts](https://github.com/kyletmartinez/After-Effects-Scripts) | ⭐168 50+工作流脚本 |
| [volition74/after-effects-scripts](https://github.com/volition74/after-effects-scripts) | ⭐167 综合脚本库 |
| [aturtur/after-effects-scripts](https://github.com/aturtur/after-effects-scripts) | ⭐119 日常动效工具 |
| [creotip/ae-scripts](https://github.com/creotip/ae-scripts) | ⭐70 JS自动化+ScriptUI模板 |
| [billybuehl792/Expand-After-Effects-Presets](https://github.com/billybuehl792/Expand-After-Effects-Presets) | ⭐68 预设库扩展 |

### 表达式库
| 项目 | 说明 |
|------|------|
| [timothyshan/ae-expression-lib](https://github.com/timothyshan/ae-expression-lib) | ⭐48 工具函数加速表达式编写 |
| [CameronFoxly/AfterEffectsExpressionLibrary](https://github.com/CameronFoxly/AfterEffectsExpressionLibrary) | 精选可复用表达式集合 |
| [motiondeveloper/expressionist](https://github.com/motiondeveloper/expressionist) | Web端+AE内表达式编辑器 |
| [motiondeveloper/ae-keyframe](https://github.com/motiondeveloper/ae-keyframe) | ⭐38 关键帧动画通过表达式 |

### 专业框架
| 项目 | 说明 |
|------|------|
| [RxLaboratory/DuAEF](https://github.com/RxLaboratory/DuAEF) | ⭐29 AE脚本端到端框架 |
| [azaynzxz/after-effects-expression-panel](https://github.com/azaynzxz/after-effects-expression-panel) | 综合脚本面板(表达式+动画+工具) |

---

## 🎯 创作工作流：从简到精

### Level 1: 基础（30 秒）
```
create-composition → createTextLayer → apply-preset (文字入场) → 完成
```

### Level 2: 进阶（2 分钟）
```
创建合成 → 文字层 → 文字预设 → 调色预设 → 加光效 → 加粒子 → 完成
```

### Level 3: 专业（5 分钟）
```
创建合成 → 文字层+预设 → 自定义表达式 → 多图层分层入场 →
光效+粒子+景深 → 调色链 → 动态模糊 → 输出建议
```

### Level 4: 电影级（10 分钟+）
```
分镜规划 → 多合成嵌套 → 摄像机动画 → 3D 空间布局 →
Particular 多层粒子系统(含曲线+Aux) → E3D 三维元素 →
Sapphire 全套后期 → 音画同步表达式 → 色彩分级
```

---

## ⚡ 关键提醒

1. **先查预设再手写** — 预设比手调快 100 倍，且效果更专业
2. **图层不要太少** — 好的作品通常 5-15 层
3. **运动和颜色不能同时激进** — 动得多的颜色要柔和
4. **16:9 是画布，文字别贴边** — 留 10% 安全边距
5. **任何效果加 0.5-2px 运动模糊** — 这是电影感最简单的来源
6. **预览时按 0 键 RAM 预览** — 实时反馈比盲调更重要
7. **粒子不做曲线 = 铁定突兀** — Size/Opacity over Life 是必修课
8. **随机性是自然的本质** — Life/Size/Opacity/Velocity Random 永远不要为0
9. **粒子要有"来处"和"归宿"** — 淡入淡出赋予粒子生命
10. **Aux System 是专业的分水岭** — 单层粒子 vs 多层粒子系统
