---
title: Roto-Brush-3与AI辅助遮罩实战
date: 2026-07-04
tags:
  - Roto-Brush
  - AI抠像
  - 遮罩
  - Mocha
  - Silhouette
  - RunwayML
  - SAM2
  - Keylight
  - Track-Matte
  - Content-Aware-Fill
---
# ✂️ Roto-Brush-3与AI辅助遮罩实战（完整版）

> 从 AE 内置 AI 抠像到云端 API——2025-2026 年抠像/遮罩工具的完整生态、参数体系与混合工作流。本文覆盖 Roto Brush 3.0、Content-Aware Fill、Keylight、Mocha AE、第三方 AI 工具、15 个实战案例与 10+ JSX 脚本，总字数 3 万+，是 AE 遮罩领域的全景式参考手册。

---

## 一、Roto-Brush 3 基础

### 1.1 Roto-Brush 3 概述与新功能

Roto Brush 3.0 是 Adobe After Effects 自 2023 年 v24.0 版本起引入的第三代 AI 驱动自动抠像工具，基于 Adobe Sensei 深度学习框架训练，相较前代在边缘检测精度、运动模糊处理、半透明物体识别三个核心维度实现了跨越式提升。它通过卷积神经网络（CNN）对每一帧进行语义分割，自动识别前景主体并跨帧传播遮罩信息，使原本需要数小时手动逐帧描摹的 Rotoscoping 工作压缩至分钟级完成。

**Roto Brush 3.0 核心新功能：**

| 新功能 | 描述 | 实际收益 |
|--------|------|----------|
| 全新 AI 模型 | 基于 Sensei 升级版分割网络，训练数据集扩大 4 倍 | 头发/毛边识别精度提升约 40% |
| 运动模糊处理 | 智能识别运动方向并生成方向性模糊遮罩 | 高速运动物体边缘不再"撕裂" |
| 透明物体支持 | 部分识别玻璃、烟雾、水流的半透明区域 | 减少手动二级抠像工作量 |
| 跨帧传播加速 | GPU 并行计算传播路径 | 5-10 秒片段处理时间降低 50% |
| Refine Edge XL | 扩展精炼边缘工具支持 8K 分辨率 | 适配高分辨率工作流 |
| 多主体同时分离 | 单次描摹可区分多个独立前景对象 | 复杂场景一键拆分 |

### 1.2 与 Roto-Brush 1/2 的对比

| 对比维度 | Roto Brush 1.0（CS5） | Roto Brush 2.0（v17.5） | Roto Brush 3.0（v24.0+） |
|----------|----------------------|------------------------|--------------------------|
| 发布年份 | 2010 | 2020 | 2023 |
| 核心技术 | 像素差分 + 光流 | Adobe Sensei v1 神经网络 | Sensei v2 升级网络 + 时序一致性 |
| 头发处理 | 几乎不可用 | 可用但需大量 Refine Edge | 自动识别发丝级细节 |
| 运动模糊 | 严重撕裂 | 一般 | 方向性模糊遮罩 |
| 透明物体 | 不支持 | 不支持 | 部分支持 |
| 处理速度 | 慢 | 中等 | 快（GPU 加速）|
| 跨帧传播稳定性 | 易漂移 | 较稳定 | 稳定（带时序一致性约束）|
| GPU 要求 | CPU only | NVIDIA 推荐 | NVIDIA 强烈推荐 |
| 内存占用 | 低 | 中 | 高（4K 约 8GB）|
| 最佳片段长度 | <5 秒 | <10 秒 | <20 秒（更长需分段）|
| 冻结（Freeze）稳定性 | 一般 | 较好 | 好（偶发崩溃已知问题）|

### 1.3 系统要求与 GPU 加速

**最低系统要求：**

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| 操作系统 | Windows 10 64-bit / macOS 11 | Windows 11 / macOS 14 |
| 处理器 | Intel 7代 / Ryzen 3000 | Intel 12代+ / Ryzen 7000+ |
| 内存 | 16 GB | 32 GB（4K）/ 64 GB（8K）|
| GPU | NVIDIA GTX 1060 6GB | RTX 4070 12GB+ |
| GPU 驱动 | NVIDIA Studio Driver 535+ | 最新 Studio Driver |
| 显存 | 6 GB | 12 GB+ |
| 硬盘 | 50GB 可用空间 | NVMe SSD + 100GB+ 缓存 |
| 显示器 | 1920×1080 | 4K HDR |

**GPU 加速说明：**

Roto Brush 3.0 强依赖 NVIDIA CUDA 加速。在 AMD 或 Intel GPU 上，工具会自动回退至 Roto Brush 2.0 引擎，性能与精度均下降。可通过 `编辑 → 首选项 → 显示与视频` 中查看 GPU 加速状态。若发现紫色覆盖层异常或传播停滞，应首先检查 GPU 是否为 NVIDIA 且驱动为 Studio Driver 而非 Game Ready Driver。

### 1.4 工作原理：AI 驱动的边缘检测

Roto Brush 3.0 的工作流程可拆解为五个阶段：

1. **用户描摹阶段**：用户在初始帧（基准帧 Base Frame）用绿色画笔涂抹前景主体，用 Alt+红色画笔涂抹背景区域。AI 将这些涂鸦作为"种子"信号。
2. **语义分割阶段**：Sensei 神经网络对整帧像素进行语义分类，识别哪些像素属于前景主体（人、物、动物等），哪些属于背景。
3. **边缘精炼阶段**：在前景/背景交界处，AI 进一步细化边界，识别毛发、半透明边缘等复杂细节，生成软边 Alpha。
4. **跨帧传播阶段**：基于光流与时序一致性约束，将基准帧的分割结果向前/向后传播到相邻帧，每帧独立运行 AI 模型保证精度。
5. **冻结阶段**：用户确认传播结果后，点击 Freeze 将遮罩烘焙为静态 Alpha 通道，避免后续编辑时重新计算。

### 1.5 适用场景与限制

**适用场景：**

- 主体与背景对比度明显的人物、物体抠取
- 短片段（<20 秒）的快速遮罩生成
- 头发、毛发等复杂边缘的初步处理
- 不适合绿幕拍摄的复杂背景素材
- 动态主体（人物走动、手势变化）的跟踪遮罩

**已知限制：**

- 长片段（>30 秒）易出现漂移、崩溃
- 低对比度场景（如深色主体在深色背景中）精度下降
- 极快速运动（>200 像素/帧）边缘可能丢失
- 多主体交错遮挡场景需分段处理
- 透明物体仅部分支持，玻璃反光严重时仍需手动
- AMD/Intel GPU 用户无法使用 3.0 引擎
- Freeze 操作偶发崩溃，建议先保存项目再执行

---

## 二、Roto-Brush 3 完全操作指南

### 2.1 基础操作流程

#### 2.1.1 创建 Roto-Brush 图层

**操作步骤：**

1. 在项目面板中双击素材，将其在图层面板（Layer Panel）中打开——注意不是合成面板，Roto Brush 只能在图层面板中操作。
2. 时间指示器移动到主体运动最清晰、边缘细节最丰富的帧（通常是主体正面、运动暂停的瞬间）作为基准帧。
3. 按下 `Alt+W` 快捷键激活 Roto Brush 工具，或选择工具栏中的 Roto Brush 图标（画笔带绿色描边）。
4. 此时图层面板会出现绿色十字光标，并显示笔刷大小提示。

**注意事项：**

- 必须在图层面板（双击图层打开）中操作，合成面板中无法激活 Roto Brush
- 基准帧选择至关重要——应选择主体完整可见、边缘清晰的帧
- 一个图层只能有一个 Roto Brush 效果，多个区域可通过同一画笔涂选

#### 2.1.2 笔刷大小设置

笔刷大小直接影响描摹精度与速度。Roto Brush 笔刷是"区域指示"而非精确绘画——AI 会根据涂抹区域推断主体边界，因此不需要描到像素级精确。

**笔刷大小参考表：**

| 主体类型 | 推荐笔刷大小（占主体高度比例）| 实际像素示例（1080p）|
|----------|------------------------------|----------------------|
| 全身人物 | 5-8% | 50-80 px |
| 半身人物 | 8-12% | 80-120 px |
| 面部特写 | 3-5% | 30-50 px |
| 小物体（杯子）| 15-25% | 20-40 px |
| 复杂边缘（头发）| 1-3% | 10-30 px |
| 大面积背景（草地）| 20-30% | 200-300 px |

**调整快捷键：**
- `Ctrl+拖拽`（Windows）/ `Cmd+拖拽`（macOS）：实时调整笔刷大小
- `[` / `]`：缩小/放大笔刷（与 Photoshop 一致）
- 按住 `Ctrl` 时画笔显示直径数值

#### 2.1.3 前景/背景绘制

**前景绘制（绿色画笔）：**

默认状态下画笔为绿色，表示"添加到前景"。在主体中心区域涂抹，AI 会自动扩展到主体边界。无需涂到边缘——AI 推断范围约为笔刷直径的 2-3 倍。

**背景绘制（红色画笔）：**

按住 `Alt` 键，绿色画笔变为红色，表示"从前景中减去"。用于：
- 主体内部有背景透出的孔洞（如手指间、衣袖开口）
- AI 过度扩展将背景误判为前景
- 多主体场景中排除其他对象

**最佳实践：**

1. 先用大笔刷快速涂抹主体中心 70% 区域
2. 等待 AI 计算（底部进度条），观察自动扩展的边界
3. 用小笔刷补充遗漏区域（绿色）
4. 用 Alt+红色画笔擦除误判区域
5. 反复迭代直至基准帧遮罩准确

#### 2.1.4 传播帧（Propagate）

基准帧确定后，需要将遮罩传播到其他帧。

**传播方式：**

| 方式 | 操作 | 用途 |
|------|------|------|
| 自动传播 | 在图层面板时间轴上拖动时间指示器 | AI 自动向前/向后传播 |
| 步进传播 | `Page Up` / `Page Down` 逐帧查看 | 检查每帧精度 |
| 强制重算 | `Ctrl+拖拽` 时间指示器 | 修正某帧后重新传播 |

**传播方向：**

- 向前传播：从基准帧向后（时间轴右侧）传播
- 向后传播：从基准帧向前（时间轴左侧）传播
- 双向传播：默认行为，AI 同时向两个方向计算

**传播信息显示：**

图层面板底部显示信息栏：
- 绿色进度条：正在计算
- 粉色帧：已传播但未冻结
- 绿色帧：已冻结
- 灰色帧：未计算

#### 2.1.5 冻结结果（Freeze）

确认所有帧的遮罩准确后，点击图层面板底部的 `Freeze` 按钮将遮罩烘焙。

**Freeze 的作用：**

- 将动态计算的遮罩转为静态 Alpha 通道
- 释放 CPU/GPU 计算资源
- 关闭图层面板后遮罩不再重新计算
- 项目保存后遮罩数据持久化

**Freeze 操作注意事项：**

| 注意点 | 说明 |
|--------|------|
| 不可逆性 | Freeze 后无法回到 Roto Brush 编辑模式，需"Unfreeze"重置 |
| 崩溃风险 | 长片段 Freeze 时偶发崩溃，建议先 `Ctrl+S` 保存 |
| 内存需求 | Freeze 需要将所有帧遮罩写入内存，4K 长片段可能 OOM |
| 解决方案 | 分段 Freeze：每 5-10 秒一段，分别预合成 |
| 取消 Freeze | 右键图层 → Roto Brush → Unfreeze |

### 2.2 高级操作技巧

#### 2.2.1 多个 Roto-Brush 图层叠加

由于一个图层只能有一个 Roto Brush 效果，复杂场景需要将素材复制多层，分别用 Roto Brush 处理不同主体。

**操作流程：**

1. 选中素材图层，`Ctrl+D` 复制（建议重命名为"主体 A"、"主体 B"）
2. 双击"主体 A"图层进入图层面板，用 Roto Brush 描摹主体 A
3. 双击"主体 B"图层进入图层面板，用 Roto Brush 描摹主体 B
4. 分别 Freeze 后，在合成面板中将两层叠加
5. 可对每层独立调色、添加效果、调整位置

**应用场景：**
- 多人对话场景，每个演员独立遮罩
- 主体前后有遮挡物，需要分别处理
- 部分主体需要单独替换背景

#### 2.2.2 Roto-Brush 与遮罩组合

Roto Brush 生成的遮罩可与手动遮罩组合使用，弥补 AI 的不足。

**组合方式：**

| 组合方式 | 操作 | 应用场景 |
|----------|------|----------|
| Roto Brush + Add 遮罩 | 在 Roto Brush 图层上添加普通遮罩，模式 Add | 补充 Roto Brush 遗漏的区域 |
| Roto Brush + Subtract 遮罩 | 添加普通遮罩，模式 Subtract | 擦除 Roto Brush 误判的区域 |
| Roto Brush + Intersect 遮罩 | 添加普通遮罩，模式 Intersect | 限制 Roto Brush 仅作用于某区域 |
| Roto Brush 预合成 + 外部遮罩 | 将 Roto Brush 预合成后用 Track Matte | 精确控制最终遮罩形状 |

#### 2.2.3 Roto-Brush 与 Alpha Matte 组合

将 Roto Brush 结果作为 Alpha Matte 应用到其他图层，是高级合成常用技巧。

**操作步骤：**

1. 图层 A 用 Roto Brush 生成主体遮罩，Freeze
2. 图层 A 上方放置图层 B（要应用遮罩的图层，如调色调整层、文字层）
3. 选中图层 B，在 Track Matte 列选择 `Alpha Matte "图层 A"`
4. 图层 B 现在仅显示在图层 A 的主体范围内

**典型应用：**
- 主体局部调色：调色调整层 + Alpha Matte（Roto Brush 主体）
- 主体局部发光：发光效果层 + Alpha Matte
- 主体局部模糊（如人脸马赛克）：模糊层 + Alpha Matte

#### 2.2.4 隔离复杂边缘（头发、毛发）

头发是 Roto Brush 最具挑战的场景，需结合 Refine Edge 工具。

**完整流程：**

1. **第一阶段：粗描摹**
   - 用中等笔刷涂抹头部主体（不包括发丝）
   - Alt+红色画笔涂抹背景区域
   - 确认主体边界大致正确

2. **第二阶段：Refine Edge 精炼**
   - 切换到 Refine Edge 工具（`Alt+W` 切换，或工具栏第二个图标）
   - 用小笔刷（10-20px）沿发丝外缘涂抹
   - AI 会自动识别发丝并生成软边 Alpha
   - 调整 Refine Edge 参数：Feather 2-4、Shift Edge -5%、Reduce Chatter 30%

3. **第三阶段：传播验证**
   - `Page Down` 逐帧检查发丝遮罩
   - 发现问题帧：回到该帧重新用 Refine Edge 涂抹
   - 注意发丝随风、运动时的遮罩连续性

4. **第四阶段：冻结**
   - 全部检查无误后 Freeze
   - 若 Freeze 崩溃，导出 Alpha 通道为 PNG 序列，再用序列合成

**发丝处理参数推荐：**

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| Refine Edge Feather | 2-4 px | 太小发丝硬，太大背景渗入 |
| Refine Edge Shift Edge | -3% ~ -8% | 向内收缩消除背景色边 |
| Refine Edge Reduce Chatter | 25-40% | 平滑帧间发丝闪烁 |
| Refine Edge Decontamination | 5-15% | 去除背景色污染 |
| Smoothness | 1-3 | 太高发丝细节丢失 |

#### 2.2.5 处理运动模糊

运动模糊是 Roto Brush 3.0 的重点改进，但仍需参数调优。

**处理策略：**

1. **识别运动方向**：观察主体运动方向，运动模糊通常沿运动方向延伸
2. **扩展描摹范围**：在模糊区域用绿色画笔覆盖整个模糊带，不要只涂主体实体
3. **Refine Edge 设置**：
   - Motion Blur 滑块：根据模糊程度调整 30-70%
   - Direction：手动指定运动方向（角度），帮助 AI 识别
4. **后处理**：
   - 若 Roto Brush 生成的遮罩仍有"阶梯感"，添加 `Matte Choker` 效果，Choke 1 设置为 2-5
   - 使用 `CC Force Motion Blur` 给遮罩层添加匹配的运动模糊
   - 高端方案：用 `RSMB`（ReelSmart Motion Blur）插件基于像素运动生成精确模糊

#### 2.2.6 处理透明物体

玻璃、水、烟雾等透明物体是 Roto Brush 的难点。

**透明物体处理流程：**

1. **基础描摹**：用绿色画笔涂抹物体实体边缘（不包括透明内部）
2. **半透明区域**：用 Alt+红色画笔轻轻涂抹完全透明的区域（如玻璃中心），保留边缘的半透明
3. **Refine Edge**：
   - Feather 5-10 px（半透明需要柔和过渡）
   - Shift Edge 0%（不要收缩，保留透明感）
   - Decontamination 0%（透明物体不需要去溢色）
4. **结合 Keylight**：如果透明物体有色（如蓝色玻璃杯），可叠加 Keylight 抠取该颜色作为补充遮罩
5. **手动遮罩补强**：在 Roto Brush 基础上添加手动遮罩，控制透明度梯度

### 2.3 参数详解

#### 2.3.1 检测精度（Search Region）

Search Region 控制 AI 在每帧中搜索主体的范围。

| 参数值 | 范围 | 适用场景 | 处理速度 |
|--------|------|----------|----------|
| Small | 1-10 px | 主体运动小（<5px/帧）| 最快 |
| Medium | 10-30 px | 主体运动中等（5-20px/帧）| 中等 |
| Large | 30-60 px | 主体运动大（20-50px/帧）| 慢 |
| XL | 60-100 px | 主体运动剧烈（>50px/帧）| 最慢 |

**调优建议：**
- 默认 Medium 适合大多数场景
- 主体快速运动时调大，但精度可能下降
- 主体静止时调小，加速传播

#### 2.3.2 平滑度（Smoothness）

Smoothness 控制遮罩边缘的时间平滑度，减少帧间抖动。

| 参数值 | 效果 | 副作用 |
|--------|------|--------|
| 0-1 | 几乎无平滑，保留原始抖动 | 边缘可能闪烁 |
| 2-3 | 适度平滑，适合大多数场景 | 细节轻微丢失 |
| 4-5 | 强力平滑，边缘稳定 | 发丝等细节可能模糊 |
| 6+ | 极强平滑，边缘"漂移" | 不推荐 |

#### 2.3.3 反转（Invert）

Invert 反转遮罩，将背景变前景。常用于：
- 主体难以描摹但背景简单时，先抠背景再反转
- 制作"挖空"效果，保留背景去除主体

#### 2.3.4 传播设置（Propagation）

Propagation 子菜单控制跨帧传播行为：

| 参数 | 作用 | 推荐值 |
|------|------|--------|
| Search Region | 搜索区域大小 | Medium |
| Smoothness | 时间平滑度 | 2-3 |
| Dampen Reflections | 抑制反光干扰 | 0-20% |
| Motion Thresh | 运动阈值，低于此值视为静止 | 5-15% |
| Edge Detection | 边缘检测算法（Standard/Fine）| Fine |

#### 2.3.5 精炼边缘（Refine Edge）

Refine Edge 工具专门处理复杂边缘：

| 参数 | 作用 | 推荐值 |
|------|------|--------|
| Feather | 边缘羽化 | 1-5 px |
| Contrast | 边缘硬度 | 50-80% |
| Shift Edge | 边缘内外移动 | -10% ~ +5% |
| Reduce Chatter | 减少帧间抖动 | 20-50% |
| Use Motion Blur | 启用运动模糊识别 | On |
| Decontamination | 去除背景色污染 | 5-20% |

#### 2.3.6 精选遮罩（Refined Matte）

Refined Matte 是经过所有精炼处理后的最终遮罩，可在 Effect Controls 面板中查看实时效果。建议在工作时开启 `Roto Brush Matte` 显示模式（图层面板右下角下拉菜单）对比原图、遮罩、合成效果。

---

## 三、AI辅助遮罩技术

### 3.1 Content-Aware Fill

#### 3.1.1 Content-Aware Fill 概述

Content-Aware Fill（内容识别填充）是 AE 自 v16.1（2019）起内置的 AI 去除工具，基于 Adobe Sensei 神经网络，可自动分析画面并填充被去除区域。常用于去除威亚、标志、穿帮物体、不需要的路人等。

**核心能力：**

- 自动填充静止背景中的小物体
- 基于相邻帧信息进行时序填充
- 支持三种填充模式适配不同场景
- 与遮罩配合使用，精确控制去除区域

#### 3.1.2 工作原理

Content-Aware Fill 工作流程分三步：

1. **遮罩定义**：用户用遮罩标记要去除的区域
2. **内容分析**：AI 分析遮罩周围像素、前后帧信息、镜头运动
3. **填充生成**：基于分析结果生成填充内容，并跟踪镜头运动保持时序一致

AI 会综合考虑：
- 空间信息：遮罩周围的像素纹理
- 时序信息：前后帧对应位置的内容
- 运动信息：镜头平移、缩放、旋转

#### 3.1.3 操作流程

**完整步骤：**

1. **选择图层**：在合成面板选中要处理的素材图层
2. **创建遮罩**：
   - 双击图层进入图层面板
   - 用钢笔工具（G）或形状工具绘制遮罩，覆盖要去除的物体
   - 遮罩模式保持默认 `Add`
   - 适当 Feather（2-5 px）使填充边缘自然
3. **打开 Content-Aware Fill 面板**：`窗口 → Content-Aware Fill`
4. **选择填充方法**（见 3.1.4）
5. **生成填充**：点击 `Generate Fill` 按钮
6. **预览效果**：AE 自动生成填充图层，预览效果
7. **迭代优化**：若效果不佳，调整遮罩范围或切换方法，重新生成

#### 3.1.4 参数设置

**填充方法（Fill Method）：**

| 方法 | 适用场景 | 工作原理 | 速度 |
|------|----------|----------|------|
| Object | 静止或慢速运动物体 | 仅基于当前帧内容填充 | 快 |
| Surface | 平面表面（墙、地面）| 基于平面跟踪填充 | 中 |
| Edge Blend | 边缘融合，简单背景 | 模糊遮罩边界并融合 | 最快 |
| Perspective | 透视平面（如地板）| 考虑透视变换 | 慢 |
| Color | 纯色或渐变背景 | 用平均颜色填充 | 最快 |

**关键参数：**

| 参数 | 作用 | 推荐值 |
|------|------|--------|
| Fill Method | 填充算法 | 见上表 |
| Range | 填充范围（Work Area/Full Comp）| Work Area |
| Alpha Expansion | Alpha 扩展，遮罩外扩 | 2-5 px |
| Fill Resolution | 填充分辨率（Full/Half/Quarter）| Half（预览）/ Full（最终）|
| Use Mask | 启用遮罩 | On |
| Reference Frame | 参考帧（用于 Object 模式）| 选择背景完整帧 |

#### 3.1.5 适用场景与限制

**适用场景：**

- 威亚去除（最经典应用）
- 穿帮物体（麦克风、灯架）去除
- 简单背景中的路人去除
- 文字标识去除（如商标、水印）
- 传感器脏点去除

**限制：**

- 复杂纹理背景效果差（如草地、人群）
- 大面积去除（>20% 画面）效果差
- 高频运动背景（如水波、火焰）填充可能闪烁
- 透视变化剧烈时 Perspective 模式可能失败
- 处理时间随片段长度线性增长，4K 10 秒约需 5-15 分钟

### 3.2 AI 驱动的遮罩工具

#### 3.2.1 Mask Tracker（遮罩跟踪器）

Mask Tracker 是 AE 内置的遮罩跟踪工具，自动跟踪遮罩形状变化。

**操作流程：**

1. 在图层上绘制遮罩（钢笔工具或形状工具）
2. 选中遮罩，右键 → `Track Mask`
3. 或在 Tracker 面板中选择 `Track Mask`
4. 选择跟踪方式：
   - **Property Only**：仅跟踪遮罩属性（位置、缩放、旋转）
   - **Vertices**：跟踪遮罩顶点变形（适合形变物体）
5. 点击 `Analyze Forward` 开始跟踪
6. 跟踪完成后，遮罩自动生成关键帧

**参数设置：**

| 参数 | 作用 | 推荐值 |
|------|------|--------|
| Track Type | 跟踪类型 | Property / Vertices |
| Use Previous Frame | 使用前一帧作为参考 | On |
| Subpixel | 子像素精度 | On |
| Confidence | 置信度阈值 | 50-80% |

**适用场景：**
- 简单形状物体的跟踪（如圆形球体）
- 遮罩位置、缩放变化的跟踪
- 不适合形变剧烈或快速运动的物体

#### 3.2.2 Auto Mask

Auto Mask 是基于 Content-Aware Fill 同源 AI 的自动遮罩工具，可根据颜色或亮度自动生成遮罩。

**操作流程：**

1. 选中图层，`效果 → 生成 → Auto Mask`（或通过效果面板搜索）
2. 选择遮罩类型：Color（基于颜色）或 Luma（基于亮度）
3. 用吸管工具点击要遮罩的区域颜色
4. 调整 Tolerance（容差）扩展遮罩范围
5. 调整 Feather 柔化边缘

#### 3.2.3 AI 主体检测

2026 版 AE v26.2 引入 Object Matte 功能，基于 Adobe Sensei 实现一键 AI 主体检测。

**操作流程：**

1. 选中图层，右键 → `Layer → Create Object Matte`
2. AI 自动识别画面中的主要主体（人物、物体、动物）
3. 生成对应的遮罩图层
4. 可选择多个主体分别生成遮罩
5. 支持文字提示：在弹出的输入框中描述要选择的主体（如"穿红衣服的人"）

**优势：**
- 无需 Roto Brush 描摹
- 速度极快（5-10 秒生成遮罩）
- 多主体分别识别
- 支持自然语言提示

**限制：**
- 需要网络连接（云端 AI 推理）
- 精度略低于 Roto Brush 3.0 精细调整
- 复杂场景可能误判

#### 3.2.4 AI 背景分离

AI 背景分离是 Object Matte 的反向应用，一键分离前景与背景。

**操作流程：**

1. 选中图层，`效果 → 透视 → AI Background Separation`
2. AI 自动分析画面，识别前景主体与背景
3. 生成前景遮罩图层与背景图层
4. 可单独调整前景/背景（如背景模糊、调色）

### 3.3 第三方 AI 遮罩工具

#### 3.3.1 Runway ML

Runway ML 是云端 AI 视频处理平台，提供强大的抠像功能。

**核心功能：**

| 功能 | 描述 | 价格 |
|------|------|------|
| Remove Background | 一键去除背景，保留主体 | $12-28/月 |
| Green Screen | AI 增强绿幕抠像 | 含在订阅中 |
| Inpainting | 内容识别填充（类似 Content-Aware Fill）| $28/月 |
| Object Segmentation | 多对象分割 | $28/月 |

**工作流程：**

1. 上传视频到 Runway 平台
2. 选择 Remove Background 工具
3. 点击主体，AI 自动分割
4. 跨帧传播遮罩
5. 下载遮罩视频（带 Alpha 通道）或遮罩序列
6. 导入 AE 继续合成

**优势：**
- 不依赖 GPU，云端处理
- 处理速度快（10 秒视频约 1-2 分钟）
- 复杂场景（头发、运动模糊）效果好
- 支持 Aleph 文本编辑

#### 3.3.2 Topaz Mask AI

Topaz Mask AI 是 Topaz Labs 出品的桌面级 AI 抠像工具。

**核心功能：**
- 三色画笔系统：红色（背景）、绿色（前景）、蓝色（边缘）
- AI 自动识别边缘，包括头发、毛发
- 支持 TIFF、PNG 序列批量处理
- 与 Photoshop、Lightroom 集成

**价格：** $99.99 一次性购买

#### 3.3.3 Adobe Sensei

Adobe Sensei 是 Adobe 全家桶的 AI 基础设施，在 AE 中驱动以下功能：

| 功能 | Sensei 应用 |
|------|-------------|
| Roto Brush 3.0 | 语义分割、边缘检测 |
| Content-Aware Fill | 内容识别填充 |
| Object Matte | 对象检测、实例分割 |
| Auto Reframe | 智能重构图（保持主体在画面中）|
| Scene Edit Detection | 场景切换检测 |
| Face Tracking | 面部特征点跟踪 |

#### 3.3.4 Silhouette AI Roto

Silhouette 是 Boris FX 旗下的电影级 Roto 工具，2025.5 版本引入 AI Roto 功能。

**核心功能：**

| 功能 | 描述 |
|------|------|
| Mask ML | 基于 ML 的自动遮罩生成 |
| Object Brush ML | 类似 Roto Brush 的描摹工具，AI 增强 |
| Matte Assist ML | 智能遮罩辅助，自动精炼边缘 |
| Matte Refine ML | 遮罩精炼，处理头发、运动模糊 |
| Face ML | 面部特征自动跟踪 |

**价格：** $2,195 永久授权（专业版）

**与 AE 的协作：**
- Silhouette 可作为 AE 的插件运行
- 支持 AE 遮罩路径的导入/导出
- 节点式工作流适合复杂多层 Roto

---

## 四、遮罩类型与应用

### 4.1 遮罩基础

#### 4.1.1 遮罩类型

AE 遮罩有四种基本模式，控制遮罩区域的合并方式：

| 遮罩模式 | 作用 | 图示 | 应用场景 |
|----------|------|------|----------|
| **Add**（添加）| 显示遮罩内区域 | ◯ | 基础遮罩，显示某区域 |
| **Subtract**（减去）| 隐藏遮罩内区域 | ◯→隐藏 | 在已显示区域中挖洞 |
| **Intersect**（相交）| 仅显示多个遮罩重叠区域 | ◯∩◯ | 限制作用范围 |
| **Difference**（差异）| 显示非重叠区域 | ◯⊕◯ | 制作镂空效果 |
| **Lighten**（变亮）| 取最亮遮罩区域 | — | 类似 Add 但更柔和 |
| **Darken**（变暗）| 取最暗遮罩区域 | — | 类似 Subtract |
| **None**（无）| 遮罩不影响显示 | — | 临时禁用遮罩 |

**多遮罩组合规则：**

同一图层多个遮罩按从上到下顺序应用。第一个遮罩作用于原图，第二个遮罩作用于第一个的结果，以此类推。可通过遮罩模式控制叠加行为。

#### 4.1.2 遮罩属性

每个遮罩有以下可动画属性：

| 属性 | 作用 | 快捷键 |
|------|------|--------|
| **Mask Path** | 遮罩路径形状 | 选中遮罩 → Ctrl+T |
| **Mask Feather** | 羽化（边缘柔化）| F |
| **Mask Opacity** | 遮罩不透明度 | T |
| **Mask Expansion** | 遮罩扩展（向外/向内）| E |

**Mask Feather 详解：**

| Feather 值 | 效果 | 应用 |
|------------|------|------|
| 0 px | 硬边 | 旗帜、标志、几何图形 |
| 2-5 px | 轻微柔化 | 自然物体边缘 |
| 10-30 px | 中等羽化 | 调色局部、光效 |
| 50+ px | 大范围羽化 | 渐变、光晕、模糊过渡 |

**Mask Expansion 详解：**

| Expansion 值 | 效果 | 应用 |
|--------------|------|------|
| -50 ~ -10 px | 遮罩向内收缩 | 消除边缘杂色 |
| -5 ~ +5 px | 微调遮罩范围 | 精确控制 |
| +10 ~ +50 px | 遮罩向外扩展 | 扩大影响范围 |

#### 4.1.3 遮罩动画

遮罩属性均可关键帧动画，制作动态遮罩效果。

**常见动画类型：**

1. **Mask Path 动画**：遮罩形状变化，用于物体形变跟踪
2. **Mask Feather 动画**：羽化变化，用于渐变过渡
3. **Mask Opacity 动画**：不透明度变化，用于淡入淡出
4. **Mask Expansion 动画**：扩展变化，用于遮罩扫过效果

**Mask Path 动画技巧：**

- 关键帧之间 AE 自动插值顶点位置
- 顶点数量必须一致才能正确插值
- 使用"Mask Interpolation"关键帧助手优化插值
- 复杂形变建议用 Mocha AE 的遮罩跟踪

### 4.2 Track Matte（轨道遮罩）

Track Matte 使用一个图层的 Alpha 或亮度信息作为另一图层的遮罩。

#### 4.2.1 Alpha Matte

**原理：** 用上图层的 Alpha 通道（不透明区域）作为下图层的遮罩。

**操作：**
1. 图层 A（遮罩源）放在图层 B（被遮罩层）上方
2. 选中图层 B，Track Matte 列选择 `Alpha Matte "图层 A"`
3. 图层 B 仅在图层 A 不透明区域显示

**应用场景：**
- 文字渐变填充：渐变图层 + Alpha Matte 文字图层
- 视频在形状内显示：视频 + Alpha Matte 形状图层
- Roto Brush 主体局部调色：调色层 + Alpha Matte Roto Brush 主体

#### 4.2.2 Alpha Inverted Matte

与 Alpha Matte 相反，用上图层的 Alpha 反相作为下图层遮罩。即图层 B 在图层 A 透明区域显示。

**应用场景：**
- 主体外区域调色：调色层 + Alpha Inverted Matte 主体
- 背景模糊，主体清晰：模糊层 + Alpha Inverted Matte 主体
- 前后景分别处理

#### 4.2.3 Luma Matte

**原理：** 用上图层的亮度信息（亮区）作为下图层的遮罩。

**应用场景：**
- 烟雾、火焰等亮度不均匀的遮罩
- 渐变遮罩（用渐变图层作为 Luma Matte）
- 光效合成（光晕图层作为 Luma Matte）

#### 4.2.4 Luma Inverted Matte

与 Luma Matte 相反，用上图层的暗区作为下图层遮罩。

#### 4.2.5 Track Matte 动画

Track Matte 源图层动画会实时影响被遮罩图层。

**典型动画方式：**

| 方式 | 操作 | 效果 |
|------|------|------|
| 遮罩源位置动画 | 移动遮罩源图层 | 被遮罩内容跟随移动 |
| 遮罩源缩放动画 | 缩放遮罩源图层 | 被遮罩区域缩放 |
| 遮罩源遮罩动画 | 动画遮罩源的 Mask Path | 被遮罩区域形状变化 |
| 文字动画 | 文字图层作为 Alpha Matte | 文字内显示视频/图片 |

### 4.3 遮罩与效果组合

#### 4.3.1 遮罩 + 调色

**局部调色工作流：**

1. 创建调色调整图层（`图层 → 新建 → 调整图层`）
2. 添加调色效果（如 `Lumetri Color`）
3. 在调整图层上绘制遮罩，限定调色区域
4. 设置遮罩 Feather（10-50 px）使调色自然过渡
5. 动画遮罩 Mask Path 跟随主体运动

**典型应用：**
- 人物面部提亮（遮罩限定面部）
- 背景压暗（遮罩限定背景，反相）
- 局部色彩增强（如仅增强天空蓝色）
- 商品突出（遮罩限定商品，提高饱和度）

#### 4.3.2 遮罩 + 模糊

**局部模糊工作流：**

1. 创建调整图层，添加 `Gaussian Blur` 效果
2. 绘制遮罩限定模糊区域
3. 设置较高 Feather（30-100 px）使模糊过渡自然
4. 调整模糊半径

**典型应用：**
- 人脸马赛克（隐私保护）
- 背景虚化（模拟浅景深）
- 敏感信息遮挡（车牌、身份证号）
- 聚焦效果（仅中心清晰，四周模糊）

#### 4.3.3 遮罩 + 发光

**局部发光工作流：**

1. 复制主体图层（`Ctrl+D`）
2. 在副本上添加 `Glow` 或 `CC Light Burst` 效果
3. 用遮罩限定发光区域（如仅眼睛、武器发光）
4. 调整发光参数（半径、强度、颜色）
5. 混合模式设为 `Add` 或 `Screen`

#### 4.3.4 遮罩 + 粒子

**粒子限定区域工作流：**

1. 创建粒子效果（如 `CC Particle World`、`Particular`）
2. 用遮罩或 Track Matte 限定粒子显示区域
3. 典型应用：
   - 粒子从主体边缘飘出（Roto Brush 主体作为 Luma Matte）
   - 粒子填充文字（文字作为 Alpha Matte）
   - 粒子在特定形状内运动

---

## 五、抠像技术完全指南

### 5.1 Keylight

Keylight 是 AE 内置的专业级抠像插件（基于 The Foundry 的 Keylight 算法），是绿幕/蓝幕抠像的首选工具。

#### 5.1.1 Keylight 参数详解

Keylight 效果分为五个主要参数组：

| 参数组 | 作用 |
|--------|------|
| **Screen Colour** | 选择要抠除的颜色（绿/蓝）|
| **Screen Matte** | 遮罩精修 |
| **Inside Mask / Outside Mask** | 内/外遮罩限制 |
| **Foreground/Background Colour** | 前景/背景颜色校正 |
| **Source** | 源素材设置 |

#### 5.1.2 Screen Colour

**操作：**
1. 在 Effect Controls 中找到 Keylight → Screen Colour
2. 用吸管点击素材中的绿幕/蓝幕颜色
3. 选择具有代表性的中间色，避免选最亮或最暗的绿

**注意事项：**
- 选择画面中分布最广的绿色
- 避免选择阴影区或高光区的绿色
- 若绿幕不均匀，先添加 `Levels` 或 `Curves` 均匀化

#### 5.1.3 Screen Gain / Balance

| 参数 | 作用 | 推荐值 |
|------|------|--------|
| **Screen Gain** | 颜色抠除强度 | 1.0-1.2 |
| **Screen Balance** | 颜色平衡（影响抠像算法）| 绿幕 1.0 / 蓝幕 0.9 |

**调优建议：**
- Screen Gain 过高会导致前景边缘透明
- Screen Balance 影响 Alpha 通道质量，一般保持默认

#### 5.1.4 Screen Matte

Screen Matte 是 Keylight 最核心的精修区域：

| 参数 | 作用 | 推荐值 |
|------|------|--------|
| **Clip Black** | 黑点（低于此值完全透明）| 5-20 |
| **Clip White** | 白点（高于此值完全不透明）| 80-95 |
| **Clip Rollback** | 黑点回滚（恢复前景细节）| 5-15 |
| **Screen Shrink/Grow** | 遮罩收缩/扩展 | -1 ~ -3 px |
| **Screen Softness** | 遮罩柔化 | 0.5-2 |
| **Despill Bias** | 去溢色偏移 | 用吸管点击前景颜色 |
| **Alpha Bias** | Alpha 偏移 | 用吸管点击前景颜色 |

**Clip Black / White 调优流程：**

1. 切换 View 模式为 `Screen Matte`（仅看 Alpha）
2. 调高 Clip Black 直到背景完全黑（无灰色噪点）
3. 调低 Clip White 直到前景完全白（无灰色半透明）
4. 切换回 `Final Result` 查看效果
5. 用 Clip Rollback 恢复被过度抠除的前景细节

#### 5.1.5 Inside Mask / Outside Mask

| 参数 | 作用 |
|------|------|
| **Inside Mask** | 强制保留的区域（不被抠除）|
| **Outside Mask** | 强制抠除的区域（不被保留）|

**应用场景：**
- Inside Mask：标记主体内部（如面部），保证不被误抠
- Outside Mask：标记主体外部的背景区域，强制抠除难以处理的背景杂物

#### 5.1.6 Alpha 处理

Keylight 的 `View` 模式可切换不同显示：

| View 模式 | 用途 |
|-----------|------|
| **Final Result** | 最终合成效果 |
| **Screen Matte** | 仅查看 Alpha 通道 |
| **Inside Mask** | 查看内遮罩 |
| **Outside Mask** | 查看外遮罩 |
| **Combined Matte** | 组合遮罩 |
| **Status** | 状态查看（红=背景，白=前景，灰=半透明）|

### 5.2 其他抠像效果

#### 5.2.1 Color Key

最基础的抠像效果，抠除指定颜色。

**参数：**

| 参数 | 作用 |
|------|------|
| **Key Color** | 要抠除的颜色 |
| **Color Tolerance** | 颜色容差 |
| **Edge Thin** | 边缘收缩 |
| **Edge Feather** | 边缘羽化 |

**适用：** 简单纯色背景，不推荐用于复杂绿幕。

#### 5.2.2 Linear Color Key

比 Color Key 更精确的线性抠像，支持多个颜色样本。

**参数：**

| 参数 | 作用 |
|------|------|
| **Key Color** | 主抠除颜色 |
| **Matching Colors** | 匹配颜色模式（RGB/HSV/HLS）|
| **Matching Tolerance** | 匹配容差 |
| **Matching Softness** | 匹配柔化 |
| **Key Operation** | Key / Add / Subtract |

#### 5.2.3 Color Range

基于颜色范围的抠像，类似 Photoshop 的"色彩范围"。

**特点：**
- 支持多个吸管采样（添加、减去颜色）
- 适合复杂颜色背景（如天空、水面）
- 提供 Fuzziness 滑块控制柔化

#### 5.2.4 Inner/Outer Key

基于内外遮罩的抠像工具，适合复杂边缘。

**操作：**
1. 绘制 Inner Mask（紧贴主体内边缘）
2. 绘制 Outer Mask（紧贴主体外边缘，包含背景）
3. Inner/Outer Key 根据两个遮罩之间的过渡生成 Alpha

**适用：** 头发、毛发等复杂边缘。

#### 5.2.5 Difference Matte

基于两张图的差异生成遮罩。

**操作：**
1. 准备背景空镜头（无主体的背景）
2. 将背景层放在主体层下方
3. 对主体层应用 Difference Matte，指定背景层
4. 设置 Difference Threshold 控制差异阈值

**适用：** 静止相机拍摄的镜头，有干净背景空镜。

#### 5.2.6 Extract

基于亮度或通道的抠像，适合亮度差异大的场景。

**参数：**

| 参数 | 作用 |
|------|------|
| **Channel** | 提取通道（Luma/Red/Green/Blue/Alpha）|
| **Black Point** | 黑点 |
| **White Point** | 白点 |
| **Black Softness** | 黑色柔化 |
| **White Softness** | 白色柔化 |

### 5.3 高级抠像技巧

#### 5.3.1 绿幕/蓝幕抠像

**标准工作流：**

1. **预处理**：
   - 添加 `Levels` 效果，调整绿幕均匀度
   - 添加 `Remove Grain` 减少噪点
   - 必要时用 `Matte Choker` 预处理边缘

2. **Keylight 抠像**：
   - 用吸管选择绿色
   - 切换到 Screen Matte 视图
   - 调整 Clip Black/White
   - 调整 Screen Shrink/Grow 消除绿边

3. **去溢色**：
   - Keylight 内置 Despill
   - 额外添加 `Spill Suppressor` 效果
   - 或用 `Hue/Saturation` 降低绿色饱和度

4. **边缘精修**：
   - 添加 `Matte Choker` 收缩遮罩
   - 添加 `Refine Hard Matte` 硬化边缘
   - 必要时用 Roto Brush 补充发丝

5. **合成**：
   - 将抠像结果与背景合成
   - 添加 `Match Grain` 匹配背景噪点
   - 调整 `Color Balance` 融合环境色

#### 5.3.2 复杂背景抠像

非绿幕的复杂背景（如户外场景）抠像策略：

1. **首选 Roto Brush 3.0**：AI 处理复杂背景效果最好
2. **Keylight + 手动遮罩**：用 Keylight 抠除主要颜色，手动遮罩补充
3. **Difference Matte**：如有干净背景空镜头
4. **多工具组合**：
   - Roto Brush 粗抠
   - Keylight 精修边缘
   - 手动遮罩处理问题区域

#### 5.3.3 毛发抠像

毛发是抠像最难的场景之一：

**绿幕毛发抠像：**
1. 用 Keylight 基础抠像
2. 切换到 `Status` 视图查看毛发区域
3. 调整 Clip Rollback 恢复毛发细节
4. 添加 `Advanced Spill Suppressor` 去溢色
5. 必要时用 Refine Edge 工具补充

**复杂背景毛发抠像：**
1. 用 Roto Brush 3.0 描摹头部主体
2. 用 Refine Edge 工具沿发丝外缘涂抹
3. 调整 Refine Edge 参数（Feather 2-4，Reduce Chatter 30%）
4. 逐帧检查发丝遮罩
5. 必要时叠加手动遮罩补充

#### 5.3.4 透明物体抠像

玻璃、水等透明物体抠像：

1. **基于亮度**：用 Extract 效果基于 Luma 通道提取
2. **基于颜色**：透明物体若有色调（如蓝色玻璃），用 Keylight 抠除该色
3. **Roto Brush + 手动**：Roto Brush 描摹实体边缘，手动遮罩处理透明内部
4. **保留半透明**：
   - 不要过度调整 Clip Black/White
   - 保留 Alpha 通道的灰色区域
   - 用 Mask Opacity 控制透明度

#### 5.3.5 运动模糊抠像

运动模糊物体边缘"拖影"，抠像困难：

1. **Keylight 设置**：
   - 降低 Clip White（保留运动模糊的半透明）
   - 提高 Screen Softness（柔化边缘）
2. **后处理**：
   - 添加 `CC Force Motion Blur` 给遮罩层添加运动模糊
   - 或用 `RSMB` 插件基于像素运动生成精确模糊
3. **手动遮罩**：
   - 在运动模糊方向上扩展遮罩
   - 设置遮罩 Feather 模拟模糊过渡

#### 5.3.6 多层抠像组合

复杂场景需要多层抠像组合：

**示例：人物 + 头发 + 衣服半透明**

1. **层 1：主体实体抠像**
   - 用 Keylight 抠除绿幕
   - 调整 Clip Black/White 使主体完全不透明

2. **层 2：头发精修**
   - 复制图层，重新 Keylight
   - 调整参数保留头发半透明
   - 用 Refine Edge 补充发丝

3. **层 3：衣服半透明**
   - 复制图层，调整 Keylight 参数
   - 保留衣服的半透明区域

4. **合成**：
   - 三层叠加
   - 每层独立调整遮罩
   - 添加 `Matte Choker` 统一边缘

---

## 六、遮罩跟踪

### 6.1 Mask Tracker

#### 6.1.1 自动遮罩跟踪

Mask Tracker 是 AE 内置的遮罩跟踪工具，适合简单遮罩跟踪。

**操作流程：**

1. 在图层上绘制遮罩（钢笔工具 G）
2. 选中遮罩，在 Tracker 面板点击 `Track Mask`
3. 选择跟踪类型：
   - **Property Only**：仅跟踪遮罩整体属性（位置、缩放、旋转、变形）
   - **Vertices**：跟踪每个顶点独立运动（形变跟踪）
4. 点击 `Analyze Forward` 开始正向跟踪
5. 跟踪完成后，遮罩属性自动生成关键帧
6. 预览跟踪效果，必要时手动修正

#### 6.1.2 跟踪精度设置

| 设置 | 作用 | 推荐值 |
|------|------|--------|
| **Subpixel** | 子像素精度 | On（高精度）|
| **Confidence** | 置信度阈值 | 50-80% |
| **Use Previous Frame** | 参考前一帧 | On |
| **Track Frame Rate** | 跟踪帧率 | Comp Frame Rate |

#### 6.1.3 跟踪修正

跟踪误差修正方法：

1. **逐帧检查**：`Page Up/Down` 逐帧查看遮罩位置
2. **手动调整**：在问题帧手动调整遮罩形状，自动生成新关键帧
3. **删除问题关键帧**：删除错误帧的关键帧，让 AE 重新插值
4. **分段跟踪**：将长片段分为多段，分别跟踪
5. **切换跟踪方向**：正向跟踪失败时，尝试反向跟踪

### 6.2 手动遮罩跟踪

#### 6.2.1 关键帧遮罩动画

复杂形变物体需手动设置关键帧：

**操作流程：**

1. 在初始帧绘制遮罩，展开 Mask 属性
2. 点击 `Mask Path` 前的秒表图标，创建关键帧
3. 移动到下一个关键位置（如 5-10 帧后）
4. 调整遮罩形状（移动顶点、添加/删除顶点）
5. 自动创建新关键帧
6. 重复直至完成

**关键帧策略：**

| 策略 | 描述 | 适用 |
|------|------|------|
| **关键帧最少** | 仅在运动变化点设置关键帧 | 简单运动 |
| **逐帧精细** | 每帧设置关键帧 | 复杂形变 |
| **混合策略** | 主要点关键帧 + 逐帧修正 | 推荐做法 |

#### 6.2.2 遮罩变形动画

遮罩顶点的添加、删除动画：

- 在 Mask Path 动画中，不同关键帧可有不同顶点数
- AE 通过最近顶点匹配进行插值
- 复杂形变建议保持顶点数一致

#### 6.2.3 遮罩路径插值

**Mask Interpolation 关键帧助手：**

选中两个 Mask Path 关键帧，`动画 → 关键帧助手 → Mask Interpolation`：

| 选项 | 作用 |
|------|------|
| **Keyframe Interpolation** | 关键帧插值方式 |
| **Mask Shape** | 遮罩形状（保持顶点数）|
| **First Vertex** | 第一个顶点匹配 |
| **Use Linear Vertex Path** | 线性顶点路径 |

### 6.3 Mocha AE 集成

#### 6.3.1 Mocha AE 概述

Mocha AE 是 AE 内置的 Planar Tracking（平面跟踪）工具，由 Boris FX 提供。适合复杂跟踪、遮罩跟踪、屏幕替换等。

**Mocha AE vs Mocha Pro：**

| 功能 | Mocha AE（免费）| Mocha Pro（付费）|
|------|-----------------|------------------|
| Planar Tracking | ✓ | ✓ |
| Mask Tracking | ✓ | ✓ |
| 屏幕替换 | ✓ | ✓（增强）|
| Object Removal | ✗ | ✓ |
| 3D Camera Solve | ✗ | ✓ |
| Lens Calibration | ✗ | ✓ |
| Plug-in 版本 | ✗ | ✓ |

#### 6.3.2 Planar Tracking

Planar Tracking 原理：基于"平面"（如墙面、地面、屏幕）的跟踪，比点跟踪更稳定。

**操作流程：**

1. 选中图层，`动画 → 在 Mocha AE 中跟踪`
2. Mocha AE 独立窗口打开
3. 用 X Spline 工具绘制跟踪平面（如屏幕的四边形）
4. 点击 `Track Forward` 跟踪
5. 跟踪完成后，导出跟踪数据

**跟踪参数：**

| 参数 | 作用 | 推荐值 |
|------|------|--------|
| **Track Field** | 跟踪场（亮度/颜色）| 亮度 |
| **Motion** | 运动类型（Translate/Scale/Shear/Perspective）| 根据场景 |
| **Large Motion** | 大运动模式 | 运动剧烈时开启 |
| **Smoothing** | 平滑跟踪数据 | 5-10 帧 |

#### 6.3.3 遮罩导出/导入

**从 Mocha AE 导出遮罩到 AE：**

1. 在 Mocha AE 中绘制遮罩（X Spline 或 Bezier）
2. 跟踪遮罩（`Track Forward`）
3. 选中遮罩，`Edit → Copy`
4. 切换到 AE，选中目标图层
5. `Edit → Paste`，遮罩粘贴并带有关键帧

**导出选项：**

| 选项 | 描述 |
|------|------|
| **Copy to Clipboard** | 复制到剪贴板，直接粘贴到 AE |
| **Export Shape Data** | 导出形状数据（.shape 文件）|
| **Export Tracking Data** | 导出跟踪数据（位置、缩放等）|

#### 6.3.4 Mocha 与 AE 工作流

**标准工作流：**

1. **AE 中准备**：导入素材，创建合成
2. **启动 Mocha**：选中图层 → `动画 → 在 Mocha AE 中跟踪`
3. **Mocha 中跟踪**：绘制跟踪平面、遮罩，执行跟踪
4. **导出到 AE**：复制遮罩数据，粘贴回 AE 图层
5. **AE 中应用**：将遮罩用于效果限定、屏幕替换等
6. **最终调整**：在 AE 中精修遮罩，添加效果

**屏幕替换工作流：**

1. Mocha AE 跟踪屏幕四边形
2. 导出 `Corner Pin` 数据
3. AE 中粘贴到替换图层
4. 替换图层自动匹配屏幕透视
5. 添加 `Mask` 精修边缘
6. 调整 `Color` 匹配环境光

---

## 七、实战案例（15个）

### 7.1 案例 1：人物抠像（简单背景）

**问题描述：** 需要将人物从纯色背景中抠出，用于合成新背景。背景为浅灰色，人物服装深色，对比度明显。

**解决方案：** 使用 Roto Brush 3.0 快速抠像，10 秒内完成。

**操作步骤：**

1. 双击素材在图层面板打开
2. 移动到人物正面清晰的帧作为基准帧
3. `Alt+W` 激活 Roto Brush，笔刷设为 60px
4. 用绿色画笔涂抹人物主体（从头部到脚部）
5. AI 自动扩展，等待传播完成
6. `Alt+红色画笔` 涂抹人物间的背景空隙（如手臂间）
7. `Page Down` 逐帧检查，必要时修正
8. 调整参数：Feather 3px，Shift Edge -5%
9. 点击 `Freeze` 冻结遮罩

**参数设置：**

| 参数 | 值 |
|------|-----|
| 笔刷大小 | 60 px |
| Feather | 3 px |
| Shift Edge | -5% |
| Reduce Chatter | 30% |
| 处理时间 | ~2 分钟（10秒片段）|

### 7.2 案例 2：人物抠像（复杂背景）

**问题描述：** 人物在户外复杂背景（树木、草地、建筑）中，需要抠出用于背景替换。

**解决方案：** Roto Brush 3.0 + 手动遮罩组合。

**操作步骤：**

1. Roto Brush 基础描摹：用绿色画笔涂抹人物，AI 自动识别
2. 用 Alt+红色画笔涂抹与人物颜色相似的背景区域（如深色树干）
3. 逐帧检查，重点处理：
   - 人物与背景颜色相近的边缘
   - 人物运动时的边缘
4. 对问题区域添加手动遮罩（Subtract 模式）精修
5. 调整 Refine Edge：Feather 4px，Reduce Chatter 40%
6. Freeze 冻结
7. 将抠像结果与背景图层用 `Matte Choker`（Choke 1: 2）合成

**参数设置：**

| 参数 | 值 |
|------|-----|
| 笔刷大小 | 50 px |
| Feather | 4 px |
| Shift Edge | -8% |
| Reduce Chatter | 40% |
| Matte Choker Choke 1 | 2 |
| 处理时间 | ~10 分钟（10秒片段）|

### 7.3 案例 3：毛发细节抠像

**问题描述：** 人物长发飘逸，需要保留发丝细节用于合成。

**解决方案：** Roto Brush 3.0 + Refine Edge 工具。

**操作步骤：**

1. 基础描摹：用绿色画笔涂抹头部主体（不包括发丝）
2. Alt+红色画笔涂抹发丝间的背景
3. 切换到 Refine Edge 工具（`Alt+W` 切换）
4. 用小笔刷（15px）沿发丝外缘涂抹
5. AI 自动识别发丝，生成软边 Alpha
6. 调整 Refine Edge 参数：
   - Feather 2px
   - Shift Edge -3%
   - Reduce Chatter 30%
   - Decontamination 10%
7. 逐帧检查发丝连续性，必要时修正
8. Freeze 冻结

**参数设置：**

| 参数 | 值 |
|------|-----|
| Refine Edge 笔刷 | 15 px |
| Feather | 2 px |
| Shift Edge | -3% |
| Reduce Chatter | 30% |
| Decontamination | 10% |
| 处理时间 | ~20 分钟（5秒片段）|

### 7.4 案例 4：透明物体抠像

**问题描述：** 需要抠取玻璃杯，保留透明感和反射。

**解决方案：** Roto Brush + 手动遮罩 + Keylight 组合。

**操作步骤：**

1. Roto Brush 描摹玻璃杯实体边缘
2. Alt+红色画笔涂抹完全透明的玻璃中心
3. 保留边缘的半透明区域
4. Refine Edge 设置：
   - Feather 8px（柔和过渡）
   - Shift Edge 0%（不收缩）
   - Decontamination 0%
5. 手动遮罩补强：
   - 添加 Add 遮罩，限定玻璃杯高光区域
   - 设置 Mask Opacity 50% 保留透明感
6. 若玻璃有蓝色调，叠加 Keylight 抠除蓝色作为补充遮罩
7. 与背景合成时，添加 `Displacement Map` 模拟玻璃折射

**参数设置：**

| 参数 | 值 |
|------|-----|
| Feather | 8 px |
| Shift Edge | 0% |
| Mask Opacity | 50% |
| 处理时间 | ~30 分钟 |

### 7.5 案例 5：运动模糊物体抠像

**问题描述：** 快速运动的物体（如飞行的球）有严重运动模糊，抠像时边缘拖影。

**解决方案：** Roto Brush 3.0 + CC Force Motion Blur。

**操作步骤：**

1. Roto Brush 描摹：
   - 用绿色画笔覆盖整个运动模糊带（不只实体球）
   - AI 自动识别运动方向
2. 调整 Refine Edge：
   - Use Motion Blur: On
   - Motion Blur 50%
   - Direction: 手动指定运动方向
3. Freeze 冻结遮罩
4. 选中遮罩图层，添加 `CC Force Motion Blur` 效果
5. 设置：
   - Motion Blur Samples: 8
   - Shutter Angle: 180
6. 与背景合成，遮罩边缘的运动模糊自然过渡

**参数设置：**

| 参数 | 值 |
|------|-----|
| Motion Blur | 50% |
| CC Force Motion Blur Samples | 8 |
| Shutter Angle | 180 |
| 处理时间 | ~15 分钟 |

### 7.6 案例 6：物体去除（Content-Aware Fill）

**问题描述：** 画面中有一个不需要的物体（如麦克风支架），需要去除。

**解决方案：** Content-Aware Fill。

**操作步骤：**

1. 选中素材图层，双击进入图层面板
2. 用钢笔工具（G）绘制遮罩，覆盖要去除的物体
3. 遮罩设置：
   - Mask Mode: Add
   - Feather: 3px
   - 范围略大于物体（外扩 2-3px）
4. 打开 Content-Aware Fill 面板（`窗口 → Content-Aware Fill`）
5. 选择 Fill Method：
   - 物体静止：Object
   - 平面背景（墙、地）：Surface
   - 简单背景：Edge Blend
6. 点击 `Generate Fill`
7. AE 生成填充图层，预览效果
8. 若效果不佳：
   - 调整遮罩范围
   - 切换 Fill Method
   - 重新 Generate Fill

**参数设置：**

| 参数 | 值 |
|------|-----|
| Fill Method | Object |
| Feather | 3 px |
| Alpha Expansion | 2 px |
| Fill Resolution | Half（预览）/ Full（最终）|
| 处理时间 | ~5 分钟（10秒片段）|

### 7.7 案例 7：威亚去除

**问题描述：** 动作镜头中有威亚（钢丝）穿帮，需要去除。

**解决方案：** Content-Aware Fill + 手动遮罩。

**操作步骤：**

1. 逐帧检查威亚位置，通常随主体运动
2. 用钢笔工具绘制遮罩覆盖威亚
3. 动画遮罩 Mask Path 跟随威亚运动
4. 遮罩宽度略大于威亚（外扩 2-3px）
5. Feather 2px
6. Content-Aware Fill：
   - Fill Method: Object
   - 若威亚经过复杂背景，可能需要分段处理
7. Generate Fill
8. 问题区域手动用 Clone Stamp 工具补强

**参数设置：**

| 参数 | 值 |
|------|-----|
| Fill Method | Object |
| 遮罩宽度 | 威亚宽度 + 4px |
| Feather | 2 px |
| 处理时间 | ~15-30 分钟（取决于威亚长度）|

### 7.8 案例 8：文字标识去除

**问题描述：** 需要去除画面中的商标、水印或文字标识。

**解决方案：** Content-Aware Fill 或 Clone Stamp（动态）。

**操作步骤：**

**简单情况（静态标识）：**

1. 绘制遮罩覆盖标识
2. Content-Aware Fill → Fill Method: Object
3. Generate Fill

**复杂情况（标识在复杂背景上）：**

1. 绘制遮罩覆盖标识
2. Content-Aware Fill → Fill Method: Surface（如果是平面）
3. 若效果不佳，用 `Clone Stamp` 工具：
   - 双击图层进入图层面板
   - 选择 Clone Stamp 工具
   - `Alt+点击` 采样背景区域
   - 涂抹覆盖标识
   - 动画 Clone Stamp 的 Sample 位置跟随背景运动

**参数设置：**

| 参数 | 值 |
|------|-----|
| Fill Method | Object / Surface |
| Clone Stamp Brush Size | 标识宽度 + 5px |
| Feather | 2-3 px |

### 7.9 案例 9：背景替换

**问题描述：** 将原背景替换为新背景，保留前景主体。

**解决方案：** Roto Brush 3.0 抠像 + 背景合成。

**操作步骤：**

1. Roto Brush 3.0 抠取前景主体
2. Freeze 冻结遮罩
3. 在前景图层下方放置新背景图层
4. 颜色匹配：
   - 调整背景图层颜色、亮度，匹配前景
   - 用 `Lumetri Color` 调整背景
5. 添加 `Match Grain` 使背景噪点与前景一致
6. 边缘精修：
   - 添加 `Matte Choker` 收缩前景遮罩
   - 或用 `Refine Hard Matte` 硬化边缘
7. 阴影添加：
   - 在前景下方用椭圆遮罩绘制阴影
   - Feather 20px，Opacity 30%
   - 模拟主体在新背景上的投影

**参数设置：**

| 参数 | 值 |
|------|-----|
| Roto Brush Feather | 3-5 px |
| Matte Choker Choke 1 | 2 |
| Match Grain | 根据前景噪点调整 |
| 阴影 Feather | 20 px |
| 阴影 Opacity | 30% |

### 7.10 案例 10：天空替换

**问题描述：** 将原天空替换为新天空（如阴天换晴天）。

**解决方案：** Luma Matte + 遮罩动画。

**操作步骤：**

1. 在原素材上方放置新天空图层
2. 复制原素材图层，放在新天空图层上方
3. 对原素材副本应用 `Extract` 效果：
   - Channel: Luma
   - 调整 Black Point/White Point，使天空白色，前景黑色
4. 将新天空图层的 Track Matte 设为 `Alpha Matte "原素材副本"`
5. 手动遮罩补强：
   - 在新天空图层绘制遮罩，沿前景轮廓（山、建筑、树）
   - 遮罩模式 Subtract，Feather 10-30px
6. 动画遮罩（若镜头运动）：
   - 用 Mask Tracker 跟踪前景轮廓
7. 颜色匹配：调整新天空颜色，与前景协调
8. 添加 `Match Grain` 匹配噪点

**参数设置：**

| 参数 | 值 |
|------|-----|
| Extract Black Point | 100-150 |
| Extract White Point | 200-250 |
| 遮罩 Feather | 10-30 px |
| 处理时间 | ~20 分钟 |

### 7.11 案例 11：局部调色遮罩

**问题描述：** 仅对人物面部提亮，不影响其他区域。

**解决方案：** 调整图层 + 遮罩 + Mask Tracker。

**操作步骤：**

1. 创建调整图层（`图层 → 新建 → 调整图层`）
2. 添加 `Lumetri Color` 效果
3. 调整参数提亮：
   - Exposure: +0.5
   - Highlights: +10
4. 在调整图层上绘制遮罩覆盖面部
5. 遮罩设置：
   - Feather: 30px（自然过渡）
   - Mask Opacity: 80%（避免过度）
6. 用 Mask Tracker 跟踪面部运动
7. 必要时手动修正关键帧
8. 若面部角度变化大，动画 Mask Path 调整遮罩形状

**参数设置：**

| 参数 | 值 |
|------|-----|
| Exposure | +0.5 |
| Highlights | +10 |
| Feather | 30 px |
| Mask Opacity | 80% |

### 7.12 案例 12：转场遮罩

**问题描述：** 制作自定义转场效果，如遮罩扫过、形状转场。

**解决方案：** Track Matte + 遮罩动画。

**操作步骤：**

1. 将两个视频图层叠加（视频 A 在上，视频 B 在下）
2. 在视频 A 上方添加调整图层或形状图层作为遮罩源
3. 绘制遮罩形状（如圆形、矩形）
4. 动画遮罩：
   - Mask Path 关键帧：从空到满
   - 或 Mask Expansion 动画：从负值扩展到正值
5. 将视频 A 的 Track Matte 设为遮罩源
6. 添加 `Easy Ease` 关键帧缓动
7. Feather 设置（10-50px）使转场柔和

**典型转场参数：**

| 转场类型 | 遮罩形状 | 动画方式 | Feather |
|----------|----------|----------|---------|
| 横向擦除 | 矩形 | Mask Expansion 0→100% | 0 px |
| 圆形展开 | 椭圆 | Mask Expansion -100→100% | 20 px |
| 不规则 | 自由形状 | Mask Path 动画 | 30 px |
| 文字描边 | 文字 | Track Matte Alpha | 5 px |

### 7.13 案例 13：分屏遮罩

**问题描述：** 制作分屏效果，多个视频同时显示。

**解决方案：** 遮罩限定各视频显示区域。

**操作步骤：**

1. 导入多个视频图层
2. 对每个视频图层绘制遮罩，限定显示区域
3. 遮罩模式 Add，Feather 根据需要
4. 典型分屏布局：

| 布局 | 遮罩设置 |
|------|----------|
| 左右分屏 | 视频 A 遮罩左半，视频 B 遮罩右半 |
| 上下分屏 | 视频 A 遮罩上半，视频 B 遮罩下半 |
| 四宫格 | 四个视频各占四分之一，分别遮罩 |
| 不规则 | 用自由形状遮罩划分区域 |

5. 添加分割线（用形状图层或固态层）
6. 各视频独立调色、缩放、定位

### 7.14 案例 14：光效遮罩

**问题描述：** 制作局部光效，如聚光灯、光晕、光线。

**解决方案：** 遮罩 + 发光效果。

**操作步骤：**

1. 创建黑色固态层
2. 添加 `Glow` 或 `CC Light Burst` 效果
3. 绘制遮罩限定光效区域
4. 遮罩设置：
   - Feather: 50-100px（柔和光晕）
   - Mask Opacity: 50-80%
5. 混合模式设为 `Add` 或 `Screen`
6. 动画遮罩位置，模拟光线移动
7. 颜色调整：用 `Hue/Saturation` 改变光色

**典型光效参数：**

| 光效类型 | 遮罩形状 | Feather | 混合模式 |
|----------|----------|---------|----------|
| 聚光灯 | 椭圆 | 80 px | Add |
| 光晕 | 圆形 | 100 px | Screen |
| 光线 | 矩形 | 30 px | Add |
| 窗户光 | 多边形 | 50 px | Screen |

### 7.15 案例 15：粒子遮罩

**问题描述：** 粒子效果限定在特定区域内显示。

**解决方案：** 粒子图层 + Track Matte。

**操作步骤：**

1. 创建粒子效果：
   - `效果 → 模拟 → CC Particle World`
   - 或使用 `Trapcode Particular` 插件
2. 调整粒子参数（数量、大小、颜色等）
3. 创建遮罩源图层：
   - 形状图层（如文字、形状）
   - 或用 Roto Brush 抠取的主体
4. 将遮罩源图层放在粒子图层上方
5. 粒子图层 Track Matte 设为 `Alpha Matte "遮罩源"`
6. 粒子仅在遮罩源不透明区域显示
7. 动画遮罩源（如文字打字机效果）使粒子动态填充

**典型应用：**

| 应用 | 遮罩源 | 效果 |
|------|--------|------|
| 文字粒子填充 | 文字图层 | 粒子填充文字形状 |
| 主体粒子飘出 | Roto Brush 主体 | 粒子从主体边缘飘出 |
| 形状粒子 | 形状图层 | 粒子在特定形状内 |
| 渐变粒子 | 渐变图层 | 粒子根据亮度分布 |

---

## 八、遮罩性能优化

### 8.1 遮罩渲染优化

**优化策略：**

| 策略 | 效果 | 实施方法 |
|------|------|----------|
| 预合成遮罩 | 避免重复计算 | 将遮罩图层预合成，`Ctrl+Shift+C` |
| 简化遮罩形状 | 减少计算量 | 删除多余顶点，用 Bezier 而非多个直线点 |
| 关闭无用遮罩 | 释放资源 | 将不需要的遮罩 Mask Mode 设为 None |
| 分辨率降低 | 加速预览 | 合成面板分辨率设为 Half/Quarter |
| 跳帧预览 | 加速预览 | 跳帧设置为 1/2 或 1/4 |

### 8.2 Roto-Brush 性能优化

**单一最大收益项：** 裁剪工作区域。只处理需要的像素——用 `Masks to Cropped Layers II` 脚本（aescripts.com）裁剪预合成。

**核心策略：**

| 策略 | 效果 |
|------|------|
| 分割长片段为 5-10 秒段 | 降低崩溃风险、加速传播 |
| Freeze → Precomp → Pre-render | 烘焙后不再重新计算 |
| 独立 NVMe 做 Disk Cache（100+ GB）| 3-5x 工作流加速 |
| 代理工作流 | 编辑用 720p 代理，最终渲染切回原生 |
| 帧内存公式 | 4K 32bpc = ~144 MB/帧；10 秒 24fps = ~34.5 GB |

**Roto Brush 性能调优表：**

| 场景 | 推荐设置 | 预期速度 |
|------|----------|----------|
| 1080p 10秒 | 默认 | 1-2 分钟 |
| 4K 10秒 | Half Resolution | 3-5 分钟 |
| 4K 30秒 | 分段 + 代理 | 5-10 分钟/段 |
| 8K 10秒 | Quarter + 代理 | 10-15 分钟 |

### 8.3 多遮罩管理

**多遮罩优化技巧：**

1. **命名规范**：为每个遮罩命名（如"面部"、"身体"、"背景"），便于管理
2. **颜色标记**：使用遮罩颜色区分（双击遮罩可设置颜色）
3. **遮罩分组**：相关遮罩放在同一预合成中
4. **遮罩预合成**：复杂遮罩组合预合成，减少主合成复杂度
5. **遮罩锁定**：完成的遮罩锁定，防止误操作

### 8.4 预合成策略

**预合成时机：**

| 场景 | 是否预合成 | 原因 |
|------|------------|------|
| Roto Brush 冻结后 | 是 | 避免重新计算 |
| 多遮罩组合 | 是 | 简化主合成 |
| 嵌套遮罩 | 是 | 保持层级清晰 |
| 简单单遮罩 | 否 | 不必要 |
| 调整图层 | 否 | 不需要 |

**预合成选项：**

- `Move all attributes into the new composition`：所有属性移入预合成
- `Leave all attributes in`：属性保留在主合成

### 8.5 代理使用

**代理工作流：**

1. `合成 → 预合成` 创建代理
2. 在项目面板右键预合成 → `Create Proxy → Still`（静帧代理）或 `Movie`（视频代理）
3. 设置代理分辨率（通常 Half 或 Quarter）
4. 编辑时使用代理，最终渲染切回原素材

**代理与 Roto Brush：**

- 用代理预览 Roto Brush 效果
- 最终渲染时切回原素材
- 注意：Roto Brush 在代理和原素材上需要分别处理

---

## 九、遮罩 JSX 脚本

### 9.1 自动创建遮罩脚本

以下脚本自动为选中图层创建椭圆遮罩：

```javascript
// AutoCreateEllipseMask.jsx
// 为选中图层创建居中椭圆遮罩
(function() {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        alert("请先打开一个合成");
        return;
    }
    
    var selectedLayers = comp.selectedLayers;
    if (selectedLayers.length === 0) {
        alert("请先选择一个图层");
        return;
    }
    
    app.beginUndoGroup("创建椭圆遮罩");
    
    for (var i = 0; i < selectedLayers.length; i++) {
        var layer = selectedLayers[i];
        var compWidth = comp.width;
        var compHeight = comp.height;
        
        // 创建椭圆遮罩路径
        var maskShape = new Shape();
        maskShape.closed = true;
        maskShape.vertices = [
            [compWidth / 2, compHeight * 0.2],  // 上
            [compWidth * 0.8, compHeight / 2],   // 右
            [compWidth / 2, compHeight * 0.8],   // 下
            [compWidth * 0.2, compHeight / 2]    // 左
        ];
        maskShape.inTangents = [
            [-compWidth * 0.15, 0],
            [0, -compHeight * 0.15],
            [compWidth * 0.15, 0],
            [0, compHeight * 0.15]
        ];
        maskShape.outTangents = [
            [compWidth * 0.15, 0],
            [0, compHeight * 0.15],
            [-compWidth * 0.15, 0],
            [0, -compHeight * 0.15]
        ];
        
        var mask = layer.Masks.addProperty("Mask");
        mask.maskShape.setValue(maskShape);
        mask.maskFeather.setValue([20, 20]);
        mask.maskOpacity.setValue(100);
        
        alert("已为图层 " + layer.name + " 创建椭圆遮罩");
    }
    
    app.endUndoGroup();
})();
```

### 9.2 遮罩批量管理脚本

以下脚本批量重命名选中图层的所有遮罩：

```javascript
// BatchRenameMasks.jsx
// 批量重命名遮罩
(function() {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        alert("请先打开一个合成");
        return;
    }
    
    var selectedLayers = comp.selectedLayers;
    if (selectedLayers.length === 0) {
        alert("请先选择图层");
        return;
    }
    
    var prefix = prompt("输入遮罩名称前缀:", "Mask");
    if (!prefix) return;
    
    app.beginUndoGroup("批量重命名遮罩");
    
    for (var i = 0; i < selectedLayers.length; i++) {
        var layer = selectedLayers[i];
        var masks = layer.Masks;
        
        for (var j = 1; j <= masks.numProperties; j++) {
            var mask = masks.property(j);
            mask.name = prefix + "_" + (j < 10 ? "0" : "") + j;
        }
    }
    
    app.endUndoGroup();
    alert("遮罩重命名完成");
})();
```

### 9.3 遮罩动画脚本

以下脚本为遮罩创建淡入淡出动画：

```javascript
// MaskFadeAnimation.jsx
// 为选中遮罩创建淡入淡出动画
(function() {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        alert("请先打开一个合成");
        return;
    }
    
    var selectedLayers = comp.selectedLayers;
    if (selectedLayers.length === 0) {
        alert("请先选择图层");
        return;
    }
    
    var fadeDuration = parseFloat(prompt("淡入淡出时长（秒）:", "0.5"));
    if (isNaN(fadeDuration) || fadeDuration <= 0) {
        alert("请输入有效数字");
        return;
    }
    
    app.beginUndoGroup("遮罩淡入淡出");
    
    for (var i = 0; i < selectedLayers.length; i++) {
        var layer = selectedLayers[i];
        var masks = layer.Masks;
        
        for (var j = 1; j <= masks.numProperties; j++) {
            var mask = masks.property(j);
            var opacity = mask.property("ADBE Mask Opacity");
            
            // 清除现有关键帧
            opacity.expression = "";
            
            var startTime = layer.inPoint;
            var fadeInEnd = startTime + fadeDuration;
            var fadeOutStart = layer.outPoint - fadeDuration;
            var endTime = layer.outPoint;
            
            // 淡入关键帧
            opacity.setValueAtTime(startTime, 0);
            opacity.setValueAtTime(fadeInEnd, 100);
            
            // 淡出关键帧
            opacity.setValueAtTime(fadeOutStart, 100);
            opacity.setValueAtTime(endTime, 0);
            
            // 缓动
            for (var k = 1; k <= opacity.numKeys; k++) {
                opacity.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER);
            }
        }
    }
    
    app.endUndoGroup();
    alert("遮罩淡入淡出动画已创建");
})();
```

### 9.4 Track Matte 自动设置脚本

以下脚本自动设置 Track Matte：

```javascript
// AutoTrackMatte.jsx
// 自动将选中图层的 Track Matte 设为上方图层
(function() {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        alert("请先打开一个合成");
        return;
    }
    
    var selectedLayers = comp.selectedLayers;
    if (selectedLayers.length === 0) {
        alert("请先选择要应用遮罩的图层");
        return;
    }
    
    var matteType = confirm("点击确定：Alpha Matte\n点击取消：Luma Matte");
    var matteEnum = matteType ? TrackMatteType.ALPHA : TrackMatteType.LUMA;
    
    app.beginUndoGroup("设置 Track Matte");
    
    for (var i = 0; i < selectedLayers.length; i++) {
        var layer = selectedLayers[i];
        var layerIndex = layer.index;
        
        if (layerIndex === 1) {
            alert("图层 " + layer.name + " 上方无图层，跳过");
            continue;
        }
        
        var matteLayer = comp.layer(layerIndex - 1);
        layer.trackMatteType = matteEnum;
        layer.setMatteLayer = matteLayer;
    }
    
    app.endUndoGroup();
    alert("Track Matte 设置完成");
})();
```

### 9.5 10 个实用 JSX 脚本合集

**脚本 1：反转所有遮罩**

```javascript
// InvertAllMasks.jsx
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    var layers = comp.selectedLayers;
    app.beginUndoGroup("反转所有遮罩");
    for (var i = 0; i < layers.length; i++) {
        var masks = layers[i].Masks;
        for (var j = 1; j <= masks.numProperties; j++) {
            masks.property(j).property("ADBE Mask Inverted").setValue(true);
        }
    }
    app.endUndoGroup();
})();
```

**脚本 2：统一遮罩 Feather**

```javascript
// UniformFeather.jsx
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    var feather = parseFloat(prompt("Feather 值:", "10"));
    var layers = comp.selectedLayers;
    app.beginUndoGroup("统一 Feather");
    for (var i = 0; i < layers.length; i++) {
        var masks = layers[i].Masks;
        for (var j = 1; j <= masks.numProperties; j++) {
            masks.property(j).property("ADBE Mask Feather").setValue([feather, feather]);
        }
    }
    app.endUndoGroup();
})();
```

**脚本 3：遮罩扩展动画**

```javascript
// MaskExpansionAnimation.jsx
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    var layers = comp.selectedLayers;
    var startValue = parseFloat(prompt("起始扩展值:", "-100"));
    var endValue = parseFloat(prompt("结束扩展值:", "100"));
    var duration = parseFloat(prompt("动画时长（秒）:", "1"));
    
    app.beginUndoGroup("遮罩扩展动画");
    for (var i = 0; i < layers.length; i++) {
        var masks = layers[i].Masks;
        for (var j = 1; j <= masks.numProperties; j++) {
            var expansion = masks.property(j).property("ADBE Mask Offset");
            var startTime = comp.time;
            expansion.setValueAtTime(startTime, startValue);
            expansion.setValueAtTime(startTime + duration, endValue);
        }
    }
    app.endUndoGroup();
})();
```

**脚本 4：遮罩关键帧清理**

```javascript
// CleanMaskKeyframes.jsx
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    var layers = comp.selectedLayers;
    app.beginUndoGroup("清理遮罩关键帧");
    for (var i = 0; i < layers.length; i++) {
        var masks = layers[i].Masks;
        for (var j = 1; j <= masks.numProperties; j++) {
            var mask = masks.property(j);
            var props = ["ADBE Mask Shape", "ADBE Mask Feather", "ADBE Mask Opacity", "ADBE Mask Offset"];
            for (var k = 0; k < props.length; k++) {
                var prop = mask.property(props[k]);
                if (prop.numKeys > 2) {
                    // 保留首尾关键帧，删除中间
                    while (prop.numKeys > 2) {
                        prop.removeKey(2);
                    }
                }
            }
        }
    }
    app.endUndoGroup();
})();
```

**脚本 5：遮罩转固态层**

```javascript
// MaskToSolid.jsx
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    var layers = comp.selectedLayers;
    app.beginUndoGroup("遮罩转固态层");
    for (var i = 0; i < layers.length; i++) {
        var layer = layers[i];
        var masks = layer.Masks;
        for (var j = 1; j <= masks.numProperties; j++) {
            var mask = masks.property(j);
            var solid = comp.layers.addSolid([1, 0, 0], "Mask_" + j, comp.width, comp.height, 1);
            solid.moveAfter(layer);
            var newMask = solid.Masks.addProperty("Mask");
            newMask.maskShape.setValue(mask.property("ADBE Mask Shape").value);
            newMask.maskFeather.setValue(mask.property("ADBE Mask Feather").value);
        }
    }
    app.endUndoGroup();
})();
```

**脚本 6：遮罩跟踪数据导出**

```javascript
// ExportMaskData.jsx
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    var layers = comp.selectedLayers;
    if (layers.length === 0) {
        alert("请选择图层");
        return;
    }
    
    var layer = layers[0];
    var masks = layer.Masks;
    if (masks.numProperties === 0) {
        alert("图层无遮罩");
        return;
    }
    
    var mask = masks.property(1);
    var shapeProp = mask.property("ADBE Mask Shape");
    
    var output = "遮罩数据导出\n";
    output += "图层: " + layer.name + "\n";
    output += "遮罩: " + mask.name + "\n";
    output += "关键帧数: " + shapeProp.numKeys + "\n\n";
    
    for (var i = 1; i <= shapeProp.numKeys; i++) {
        var time = shapeProp.keyTime(i);
        var shape = shapeProp.keyValue(i);
        output += "时间: " + time.toFixed(3) + "s\n";
        output += "顶点数: " + shape.vertices.length + "\n";
        for (var j = 0; j < shape.vertices.length; j++) {
            output += "  顶点" + j + ": [" + shape.vertices[j][0].toFixed(1) + ", " + shape.vertices[j][1].toFixed(1) + "]\n";
        }
        output += "\n";
    }
    
    var file = new File("~/Desktop/mask_export.txt");
    file.open("w");
    file.write(output);
    file.close();
    alert("遮罩数据已导出到桌面");
})();
```

**脚本 7：批量遮罩反转**

```javascript
// BatchInvertMasks.jsx
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    var layers = comp.selectedLayers;
    app.beginUndoGroup("批量反转遮罩");
    for (var i = 0; i < layers.length; i++) {
        var masks = layers[i].Masks;
        for (var j = 1; j <= masks.numProperties; j++) {
            var current = masks.property(j).property("ADBE Mask Inverted").value;
            masks.property(j).property("ADBE Mask Inverted").setValue(!current);
        }
    }
    app.endUndoGroup();
})();
```

**脚本 8：遮罩预览模式切换**

```javascript
// ToggleMaskPreview.jsx
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    var layers = comp.selectedLayers;
    app.beginUndoGroup("切换遮罩预览");
    for (var i = 0; i < layers.length; i++) {
        var masks = layers[i].Masks;
        for (var j = 1; j <= masks.numProperties; j++) {
            var mask = masks.property(j);
            // 切换遮罩模式：Add <-> None
            if (mask.maskMode.value === MaskMode.ADD) {
                mask.maskMode.setValue(MaskMode.NONE);
            } else {
                mask.maskMode.setValue(MaskMode.ADD);
            }
        }
    }
    app.endUndoGroup();
})();
```

**脚本 9：遮罩中心点计算**

```javascript
// CalculateMaskCenter.jsx
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    var layers = comp.selectedLayers;
    if (layers.length === 0) {
        alert("请选择图层");
        return;
    }
    
    var layer = layers[0];
    var masks = layer.Masks;
    if (masks.numProperties === 0) {
        alert("图层无遮罩");
        return;
    }
    
    var mask = masks.property(1);
    var shape = mask.property("ADBE Mask Shape").value;
    var vertices = shape.vertices;
    
    var minX = Infinity, maxX = -Infinity;
    var minY = Infinity, maxY = -Infinity;
    
    for (var i = 0; i < vertices.length; i++) {
        if (vertices[i][0] < minX) minX = vertices[i][0];
        if (vertices[i][0] > maxX) maxX = vertices[i][0];
        if (vertices[i][1] < minY) minY = vertices[i][1];
        if (vertices[i][1] > maxY) maxY = vertices[i][1];
    }
    
    var centerX = (minX + maxX) / 2;
    var centerY = (minY + maxY) / 2;
    
    alert("遮罩中心点:\nX: " + centerX.toFixed(1) + "\nY: " + centerY.toFixed(1) + 
          "\n宽度: " + (maxX - minX).toFixed(1) + 
          "\n高度: " + (maxY - minY).toFixed(1));
})();
```

**脚本 10：遮罩备份与恢复**

```javascript
// BackupRestoreMasks.jsx
(function() {
    var comp = app.project.activeItem;
    if (!comp) return;
    var layers = comp.selectedLayers;
    if (layers.length === 0) {
        alert("请选择图层");
        return;
    }
    
    var action = confirm("确定：备份遮罩\n取消：恢复遮罩");
    
    if (action) {
        // 备份
        app.beginUndoGroup("备份遮罩");
        for (var i = 0; i < layers.length; i++) {
            var layer = layers[i];
            var masks = layer.Masks;
            // 保存遮罩数据到图层标签
            var backupData = [];
            for (var j = 1; j <= masks.numProperties; j++) {
                var mask = masks.property(j);
                backupData.push({
                    name: mask.name,
                    shape: mask.property("ADBE Mask Shape").value,
                    feather: mask.property("ADBE Mask Feather").value,
                    opacity: mask.property("ADBE Mask Opacity").value,
                    expansion: mask.property("ADBE Mask Offset").value,
                    inverted: mask.property("ADBE Mask Inverted").value,
                    mode: mask.maskMode.value
                });
            }
            layer.comment = backupData.toSource();
        }
        app.endUndoGroup();
        alert("遮罩已备份");
    } else {
        // 恢复
        app.beginUndoGroup("恢复遮罩");
        for (var i = 0; i < layers.length; i++) {
            var layer = layers[i];
            if (!layer.comment) continue;
            
            var backupData = eval(layer.comment);
            var masks = layer.Masks;
            
            // 清除现有遮罩
            while (masks.numProperties > 0) {
                masks.property(1).remove();
            }
            
            // 恢复遮罩
            for (var j = 0; j < backupData.length; j++) {
                var data = backupData[j];
                var mask = masks.addProperty("Mask");
                mask.name = data.name;
                mask.property("ADBE Mask Shape").setValue(data.shape);
                mask.property("ADBE Mask Feather").setValue(data.feather);
                mask.property("ADBE Mask Opacity").setValue(data.opacity);
                mask.property("ADBE Mask Offset").setValue(data.expansion);
                mask.property("ADBE Mask Inverted").setValue(data.inverted);
                mask.maskMode.setValue(data.mode);
            }
        }
        app.endUndoGroup();
        alert("遮罩已恢复");
    }
})();
```

---

## 十、遮罩常见问题

### 10.1 遮罩边缘锯齿

**原因：** 遮罩 Feather 为 0 或过小，遮罩路径顶点过少。

**解决方案：**

| 方案 | 操作 |
|------|------|
| 增加 Feather | Mask Feather 设为 2-5 px |
| 优化遮罩路径 | 使用 Bezier 曲线，避免直线段 |
| 添加 Refine Hard Matte | 效果 → 遮罩 → Refine Hard Matte |
| 使用 Matte Choker | Choke 1: 1-2，Choke 2: 0 |
| 渲染设置 | 启用最高质量渲染 |

### 10.2 遮罩溢出

**原因：** 遮罩范围过大，包含背景区域。

**解决方案：**

- 调整遮罩 Mask Path，精确贴合主体
- 设置 Mask Expansion 为负值（-2 ~ -5 px）收缩遮罩
- 添加 Subtract 遮罩擦除溢出区域
- 使用 Matte Choker 收缩遮罩

### 10.3 遮罩闪烁

**原因：** 遮罩关键帧过多或帧间不一致。

**解决方案：**

| 方案 | 操作 |
|------|------|
| Roto Brush | 增加 Reduce Chatter 至 30-50% |
| 手动遮罩 | 删除多余关键帧，使用 Bezier 插值 |
| 添加运动模糊 | CC Force Motion Blur 或 RSMB |
| 预合成 | 遮罩预合成后添加运动模糊 |
| 时间平滑 | 效果 → 时间 → CC Time Blend |

### 10.4 跟踪丢失

**原因：** 主体运动过快、对比度低、遮挡。

**解决方案：**

1. 分段跟踪：将问题区域分为多段，分别跟踪
2. 切换跟踪方向：正向失败时尝试反向
3. 手动修正：在丢失帧手动调整遮罩
4. 使用 Mocha AE：Planar Tracking 更稳定
5. 增大搜索区域：在 Mocha AE 中调整跟踪设置

### 10.5 抠像边缘问题

**绿幕抠像常见边缘问题：**

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 绿色边缘 | 去溢色不足 | 增加 Spill Suppressor，调整 Despill |
| 边缘锯齿 | Clip Black/White 间距过大 | 调整 Clip Rollback |
| 边缘透明 | Screen Gain 过高 | 降低 Screen Gain |
| 毛发丢失 | Clip White 过低 | 提高 Clip White，用 Refine Edge 补充 |
| 噪点闪烁 | 遮罩不稳定 | 添加 Matte Choker，增加 Reduce Chatter |

### 10.6 15 个常见问题解答

**Q1: Roto Brush 3.0 为什么在我的电脑上特别慢？**

A: Roto Brush 3.0 依赖 NVIDIA GPU 加速。检查：
1. GPU 是否为 NVIDIA（AMD/Intel 会回退到 2.0 引擎）
2. 驱动是否为 Studio Driver（不是 Game Ready Driver）
3. 显存是否充足（4K 需 8GB+）
4. 内存是否充足（4K 32bpc 约 144MB/帧）
5. 硬盘缓存是否在 NVMe SSD 上

**Q2: Roto Brush Freeze 时崩溃怎么办？**

A: 解决方案：
1. 先 `Ctrl+S` 保存项目
2. 分段 Freeze：每 5-10 秒一段
3. 切回 Roto Brush 2.0（`效果 → Roto Brush 版本`）
4. 导出 Alpha 通道为 PNG 序列，再用序列合成
5. 降低合成分辨率到 Half

**Q3: 遮罩 Feather 值设置多少合适？**

A: 取决于场景：
- 硬边物体（标志、几何）：0-1 px
- 自然物体（人物、动物）：2-5 px
- 调色局部：10-50 px
- 光效、渐变：50-200 px
- 大范围过渡：200+ px

**Q4: Track Matte 不生效怎么办？**

A: 检查：
1. 遮罩源图层在被遮罩图层上方（紧邻上方）
2. Track Matte 类型选择正确（Alpha/Luma）
3. 遮罩源图层有 Alpha 或亮度信息
4. 遮罩源图层的视频开关（眼睛图标）会自动关闭，这是正常的
5. 预合成时选择"Leave all attributes in"

**Q5: Content-Aware Fill 效果不好怎么办？**

A: 优化策略：
1. 切换 Fill Method（Object/Surface/Edge Blend）
2. 调整遮罩范围（外扩或缩小 2-3px）
3. 增加遮罩 Feather（3-5px）
4. 分段处理：将长片段分为多段
5. 手动用 Clone Stamp 补充问题区域
6. 使用 Reference Frame 指定最佳参考帧

**Q6: Keylight 抠像后前景发绿怎么办？**

A: 去溢色方法：
1. Keylight → Screen Matte → Despill Bias，用吸管点击前景颜色
2. 添加 `Spill Suppressor` 效果，Color To Suppress 选绿色
3. 添加 `Hue/Saturation`，降低绿色通道饱和度
4. 用 `Curves` 降低绿色通道高光

**Q7: Mocha AE 跟踪数据导入 AE 后位置不对？**

A: 检查：
1. Mocha AE 中的素材尺寸与 AE 合成一致
2. 导出时选择正确的数据类型（Corner Pin / Transform）
3. 粘贴时选中正确的图层
4. 检查图层的 Anchor Point 是否在中心
5. 必要时在 Mocha AE 中对齐跟踪点

**Q8: 遮罩动画关键帧太多，编辑困难？**

A: 优化：
1. 删除多余关键帧，仅保留运动变化点
2. 使用 `Mask Interpolation` 关键帧助手优化插值
3. 用表达式代替关键帧（如 `loopOut()` 循环动画）
4. 将复杂遮罩动画分解为多个简单遮罩
5. 使用 Mocha AE 自动跟踪代替手动关键帧

**Q9: Roto Brush 传播时出现"漂移"怎么办？**

A: 漂移（主体边缘逐渐偏移）解决方案：
1. 在漂移开始的帧重新绘制基准帧
2. 增加基准帧密度（每隔 5-10 帧设一个基准帧）
3. 调整 Search Region 为更小值
4. 用 Alt+红色画笔明确标记背景区域
5. 考虑切换到 Mocha AE 进行稳定跟踪

**Q10: 多个遮罩叠加时如何控制顺序？**

A: AE 中遮罩从上到下依次应用：
1. 第一个遮罩作用于原图层
2. 后续遮罩作用于前一遮罩的结果
3. 调整遮罩顺序：在时间轴中拖动遮罩
4. 不同模式组合产生不同效果（如 Add + Subtract 挖洞）

**Q11: 4K 素材 Roto Brush 处理特别慢？**

A: 优化策略：
1. 使用代理：创建 1080p 代理，编辑时代理，最终渲染切回原素材
2. 降低合成分辨率到 Half
3. 分段处理：每 5-10 秒一段
4. 关闭其他不必要的图层和效果
5. 增加磁盘缓存到 NVMe SSD（100GB+）
6. 增加内存到 32GB+

**Q12: 遮罩在预览和渲染时效果不一致？**

A: 检查：
1. 预览分辨率（Half/Quarter）与渲染分辨率（Full）不一致
2. 运动模糊设置（预览可能关闭，渲染开启）
3. 效果的渲染质量设置
4. 颜色管理设置（工作色彩空间）
5. 渲染设置中的"使用缺省的渲染设置"

**Q13: 透明物体（玻璃）抠像后失去透明感？**

A: 保留透明感：
1. 不要过度调整 Clip Black/White
2. 保留 Alpha 通道的灰色区域（半透明）
3. Mask Opacity 设为 50-80%
4. 用 Luma Matte 代替 Alpha Matte
5. 添加 Displacement Map 模拟折射

**Q14: 遮罩跟踪在快速运动时丢失？**

A: 解决方案：
1. 切换到 Mocha AE，使用 Planar Tracking
2. 在 Mocha AE 中开启 Large Motion 模式
3. 分段跟踪：快速运动段单独处理
4. 手动设置关键帧补充
5. 使用 Roto Brush 3.0（支持运动模糊）

**Q15: 抠像后主体边缘有"彩色边"怎么办？**

A: 彩色边（ fringe）处理：
1. **绿色边（绿幕）**：添加 Spill Suppressor，或用 Hue/Saturation 降绿色
2. **蓝色边（蓝幕）**：同上，降蓝色
3. **黑色边**：Matte Choker 收缩遮罩，或 Lighten 模式遮罩
4. **白色边**：Matte Choker Choke 设为正值
5. **通用方案**：Refine Hard Matte 效果硬化边缘
6. **极端方案**：用 Refine Edge 工具重新处理边缘

---

## 附录：版本演进与工具对比

### 版本演进表

| 版本 | 发布时间 | 核心提升 |
|------|---------|---------|
| **Roto Brush 1.0** | 2010 CS5 | 首次自动抠像，运动模糊/头发/复杂背景不行 |
| **Roto Brush 2.0** | 2020 v17.5 | Adobe Sensei AI，边缘检测大幅改进 |
| **Roto Brush 3.0** | 2023 v24.0 | 全新 AI 模型，头发/透明物体/运动模糊大幅提升 |
| **Object Matte** | 2026 v26.2 | 一键 AI 对象选择，无需画笔描摹 |

### AI 抠像工具全景（2025-2026）

#### 桌面级工具

| 工具 | 价格 | 最佳场景 |
|------|------|---------|
| **Roto Brush 3.0 / Object Matte** | CC 订阅含 | AE 内置首选 |
| **DaVinci Magic Mask 2** | $295（Studio） | 调色→抠像一体化；发丝级精度但速度慢 3x |
| **Mocha Pro 2026** | $325/年 | 平面跟踪 + AI 遮罩（Object Brush ML + Matte Assist ML + Matte Refine ML + Face ML）|
| **Silhouette 2025.5** | $2,195 永久 | 电影工业标准——Mask ML + 3D Scene Node + Compound Nodes |
| **Nuke + CopyCat** | ~$5,000/年 | 高端 VFX 工作室，ML 训练自定义抠像模型 |

#### 云端/API 工具

| 工具 | 价格 | 亮点 |
|------|------|------|
| **RunwayML** | $12-28/月 | Remove Background——点击主体→全自动传播；Aleph 文本编辑 |
| **Beeble** | $19-75/月 | SwitchLight 3.0 AI；处理复杂运动/头发/运动模糊 |
| **SAM 2 / SAM3** | 免费开源 | Meta 的视频分割基座模型；文本提示分割（SAM3）|
| **CorridorKey** | 免费开源 | AI 色度抠像——GreenFormer 神经网络；保留头发半透明 |
| **WaveSpeedAI SAM3** | $0.05/5秒 | 文本描述"穿红衬衫的人"→自动分割 |
| **Slapshot Autopilot** | 企业 | 全自动 API 驱动抠像 |
| **Electric Sheep Spotlight** | 企业 | 比传统快 24x；输出可编辑 Spline 非光栅遮罩 |

#### 中国工具

| 工具 | 亮点 |
|------|------|
| **剪映/CapCut** | 全民 AI 抠像 + Seedance 模型 |
| **Mask Prompter 3** | SAM2 基座——文字描述抠像；实战案例 72 小时 → 45 分钟（~90% 时间缩减）|
| **Goodbye Greenscreen 2** | 三模式（Auto Mask/Color/Background）一键抠像 |
| **Video Mask 3.1** | 唯一声称支持透明物体抠像（玻璃等）|

### Roto Brush vs Mocha AE 决策

| 场景 | 最佳工具 |
|------|---------|
| 快速主体隔离、高对比度、紧急截止 | **Roto Brush 3.0** |
| 精细细节（手指/头发）、重度运动模糊 | **Mocha AE** |
| 屏幕替换 / 平面表面 | **Mocha AE** |
| 全程在 AE 内工作 | **Roto Brush 3.0** |
| 复杂多层合成 | **Mocha AE / Mocha Pro** |
| 低对比度素材 | **Mocha AE**（手动 Spline 控制）|

### 混合策略

专业人士常用 **Roto Brush 3.0 做快速粗遮罩** → 导出为遮罩片段 → 喂入 **Mocha** 作为前景遮挡层进行精确平面跟踪。

### 专业 Roto 多工具编排

```
1. 镜头评估 → 映射独立运动元素，决定精度级别

2. AI第一遍 → 先试 Keyer（如有色彩对比度）
              → Roto Brush / Silhouette Mask ML 做 70-80% 粗遮罩

3. 运动跟踪 → Mocha Pro 平面跟踪主要表面
              → 链接 Roto 形状到跟踪数据

4. 精密 Roto → Silhouette 形状层级系统
              → 变化点关键帧策略（减少 60-70% 关键帧）

5. AE合成   → Paste Mocha Mask → Precomp → Matte Choker + Feather
              → CC Force Motion Blur / RSMB → 最终边缘优化
```

---

## 性能优化速查

### 单一最大收益项

**裁剪工作区域。** 只处理需要的像素——用 Masks to Cropped Layers II 脚本（aescripts.com）裁剪预合成。

### 核心策略

| 策略 | 效果 |
|------|------|
| 分割长片段为 5-10 秒段 | 降低崩溃风险、加速传播 |
| Freeze → Precomp → Pre-render | 烘焙后不再重新计算 |
| 独立 NVMe 做 Disk Cache（100+ GB）| 3-5x 工作流加速 |
| 代理工作流 | 编辑用 720p 代理，最终渲染切回原生 |
| 帧内存公式 | 4K 32bpc = ~144 MB/帧；10 秒 24fps = ~34.5 GB |

### 性能优化完整表

| 优化项 | 效果 | 实施方法 |
|--------|------|----------|
| 裁剪工作区域 | 显著减少计算量 | 用遮罩裁剪预合成 |
| 分段处理 | 降低崩溃风险 | 每 5-10 秒一段 |
| Freeze + Precomp | 烘焙遮罩 | Freeze 后预合成并预渲染 |
| 独立 NVMe 缓存 | 3-5x 加速 | Disk Cache 设到独立 NVMe |
| 代理工作流 | 编辑流畅 | 720p 代理，最终渲染切回 |
| 降分辨率预览 | 加速预览 | Half 或 Quarter |
| 关闭效果预览 | 加速预览 | 暂时关闭非必要效果 |
| 内存清理 | 释放内存 | 编辑 → 清理 → 所有内存 |

---

## 推荐学习路径

| 阶段 | 资源 |
|------|------|
| 入门 | B站「3种抠像方法快速入门」BV1m8ZuY4EpZ |
| 进阶 | Coursera *Master After Effects* |
| 专业 | Udemy *VFX Rotoscoping 101*（Vicki Lau）|
| Mocha | CGSociety *Rotoscoping with Mocha 2.6*（Steve Wright）|
| 电影级 | fxphd Roto Strategies |
| Keylight | The Foundry 官方 Keylight 教程 |
| Silhouette | Boris FX 官方 Silhouette 培训 |
| RunwayML | Runway 官方文档与案例库 |

---

## 相关链接

- [[风格化剪辑技巧与预设]] · [[静止系MAD知识体系]] · [[国际剪辑理论进阶]] · [[🎬-风格化剪辑知识库-MOC]]

---

## 快捷键速查表

### Roto Brush 快捷键

| 快捷键 | 功能 |
|--------|------|
| **Alt+W** | 切换 Roto Brush / Refine Edge |
| **Ctrl+拖拽** | 调整笔刷大小 |
| **Page Up/Down** | 逐帧移动 |
| **Alt+拖拽** | 红色画笔（减选背景）|
| **Ctrl+拖拽时间指示器** | 强制重算 |
| **[ / ]** | 缩小/放大笔刷 |
| **Home/End** | 跳到工作区开始/结束 |
| **Space** | 预览播放 |

### 遮罩快捷键

| 快捷键 | 功能 |
|--------|------|
| **G** | 钢笔工具 |
| **Q** | 形状工具 |
| **Ctrl+T** | 选择工具（编辑遮罩顶点）|
| **M** | 选中遮罩显示 Mask Path |
| **M, M** | 双击 M 显示所有遮罩属性 |
| **F** | Mask Feather |
| **T** | Mask Opacity |
| **E** | Mask Expansion |
| **Shift+F** | 选中遮罩 Feather |
| **Shift+T** | 选中遮罩 Opacity |
| **Ctrl+Shift+N** | 新建遮罩 |
| **Alt+Shift+M** | 追踪遮罩 |

### Keylight 快捷键

| 快捷键 | 功能 |
|--------|------|
| **Alt+双击效果** | 打开 Keylight 完整界面 |
| **Ctrl+点击吸管** | 重置颜色选择 |
| **View 下拉菜单** | 切换查看模式（Final/Matte/Status）|

---

> 本文档总字数约 3 万字，覆盖 Roto Brush 3.0、Content-Aware Fill、Keylight、Mocha AE、第三方 AI 工具、15 个实战案例、10+ JSX 脚本与 15 个常见问题解答。是 AE 遮罩领域的完整参考手册，建议结合实际项目练习掌握。
