# 角色动画与抠图合成指南

## 🎭 Puppet Pin（木偶销钉）骨骼动画

### 基础工作流

```
1. 素材准备
   - Photoshop: 角色各部位分层, 确保完整Alpha通道
   - 把断开的部位(头/身体)在Alpha通道中用白色连接
     (RGB保持分离，但Alpha连为一体 → 网格当作一个整体)
   - 保存为 PSD → 导入AE为 Composition

2. 放置 Puppet Pin
   - 选中图层 → 工具栏选 Puppet Pin Tool (Ctrl+P)
   - 在关键关节放置 Pin:
     身体: 髋(hips) → 腰 → 胸 → 颈(neck)
     手臂: 肩(shoulder) → 肘(elbow) → 腕(wrist) → 手指尖(可选)
     腿部: 髋 → 膝(knee) → 踝(ankle) → 脚尖(可选)
   
   ⚠️ Pin 数量原则: 够用即可，不是越多越好
     太多 Pin = 难控制 + 易产生不自然变形

3. 加固刚性区域
   - 选 Puppet Starch Tool (在Puppet Pin工具组)
   - 在不该弯曲的区域添加 Starch (如头部、躯干)
   - Starch 密度越高 = 该区域越硬

4. 调整网格
   - Expansion: 控制网格扩展范围 (增大→覆盖更多像素边缘)
   - Triangles: 网格三角数量 (更多=更精确但更慢)
   - 对复杂形状可增加 Triangles

5. 动画录制
   - 时间线移到起始帧
   - 按住 Ctrl/Cmd + 鼠标悬停在 Pin 上 (光标显示时钟图标)
   - 拖拽 Pin → 实时录制动作
   - 或手动设关键帧: 选 Pin → 移动 → 自动创建关键帧
```

### 高级技巧

#### Null 绑定法（最推荐）

```
问题: Puppet Pin 不能直接旋转、不能做缩放动画、没有缓动曲线
解决: 用 Null 层桥接

步骤:
1. 为每个关键 Pin 创建一个 Null 层
   命名: "Ctrl_Hip", "Ctrl_Shoulder_L", "Ctrl_Wrist_R" 等
   设为3D图层(可选)

2. 在 Pin 的 Position 属性上写表达式:
   L = thisComp.layer("Ctrl_Wrist_R");
   fromComp(L.toComp(L.anchorPoint));

3. 现在操作 Null 层 = 操作 Pin!
   - Null 可以做 Position/Rotation/Scale 关键帧
   - Null 可以用 Easy Ease / Graph Editor
   - Null 可以加 wiggle() 抖动
   - Null 可以 Parent 到其他层
   - Null 可以复制关键帧到其他 Null

进阶: IK效应
   Null层级: Hip Null → Knee Null → Ankle Null (Parent链)
   移动 Ankle Null = 整条腿跟随(类似IK)
```

#### 走步循环 (Walk Cycle)

```
关键帧位置 (30fps, loopOut):

帧 0:  腿张开 (左前右后)
帧 7:  过渡 (左脚着地, 右膝抬起)
帧 15: 腿张开 (右前左后 — 与帧0相反)
帧 23: 过渡 (右脚着地, 左膝抬起)
帧 30: = 帧0 (复制帧0)

循环表达式 (在最后一个关键帧后):
  loopOut("cycle", 0)

配合身体上下弹跳:
  帧0: 身体 Y 最低
  帧7: 身体 Y 最高
  帧15: 身体 Y 最低
  帧23: 身体 Y 最高
```

#### 手臂摆动公式

```javascript
// 手臂自然摆动 — 在 Null 的 Rotation 上
amp = 15; // 摆动幅度(度)
freq = 1; // 与步伐同频
phase = 0; // 左手=0, 右手=180 (反相)
Math.sin(time * freq * Math.PI * 2 + phase) * amp;

// 走路时手臂:
// 左脚在前 → 右臂在前 (反之亦然)
// 所以左右手的 phase 差 180°
```

### 常见问题与解决

| 问题 | 原因 | 解决 |
|------|------|------|
| 关节处撕裂 | 网格三角不够密 | 增加 Triangles |
| 不自然扭曲 | 缺少 Starch 加固 | 在不该动的区域加 Starch |
| 边缘出现"鬼影" | Expansion 太小 | 增大 Expansion 2-5px |
| 动画抖动 | Mesh 关键帧过多 | 减少 Pin 数量, 用 Null 间接控制 |
| Alpha 边缘有锯齿 | 素材Alpha不干净 | Photoshop 中清理Alpha通道 |

---

## ✂️ Roto Brush 3.0（AI智能抠像）

### 完整工作流

```
1. 双击素材图层 → 打开 Layer 面板
2. 时间指示器移到第一帧
3. 工具栏选 Roto Brush (Alt+W)
4. 绿色笔刷: 涂画要保留的主体
   - 从中心向外画
   - 覆盖主体边缘的关键区域
   - 尽量覆盖头发/衣服等复杂边缘
5. 按住 Alt/Option: 红色笔刷
   - 涂画要排除的区域
   - 涂画背景、不需要的元素
6. 按 Page Down 前进一帧 (或空格播放)
   - AE 自动传播遮罩到下一帧
   - 如果传播错误 → 在当前帧修正 → 继续
7. 每次修正后按 Page Down → 让修正传播
8. 逐帧检查关键帧(动作大的地方容易出错)
9. 使用 Refine Edge Tool (在Roto Brush工具组)
   - 涂画头发/半透明/模糊边缘
   - 让AE学习更精确的边缘
10. 完成后 → Freeze (冻结) → 回主合成查看
```

### Roto Brush 参数

```
Feather:          2-5px (柔和边缘)
Shift Edge:       -5 ~ +5px (收缩/扩展边缘)
Reduce Chatter:   50-70% (减少边缘抖动)
Refine Edge:      涂画后自动应用

Decontamination:  去色溢 (绿幕残留的颜色)
  - 开启后自动校正边缘颜色污染
```

### 最佳实践

```
✅ 先确定一个"好帧"作为起始帧 (清晰、无模糊)
✅ 从主体中心开始涂绿色 → 再处理边缘
✅ 关键帧不要跳太多 (每1-3帧检查)
✅ 动作大的地方用更多修正笔触
✅ 复杂毛发用 Refine Edge 而非多次涂画
❌ 不要试图一次涂满整个主体 (分步来)
❌ 不要在运动模糊处强行抠 (找无模糊的帧重新开始)
❌ 不要在低对比度区域死磕 (配合手动Mask)
```

---

## 🟢 绿幕抠像 (Green Screen Keying)

### Keylight 标准流程

```
1. Garbage Matte (垃圾遮罩) — 第一步!
   - 用 Pen Tool 画粗略 Mask 围住主体
   - 排除不需要的绿幕区域(边缘杂物、灯光)
   - 节省 Keylight 处理时间 + 提高质量

2. 应用 Keylight (1.2)
   - Effects → Keying → Keylight (1.2)
   - Screen Color: 用吸管选绿色背景
   - 大部分绿色立即消失

3. 检查遮罩
   - View 切换为 Screen Matte
   - 白色 = 保留, 黑色 = 抠掉, 灰色 = 半透明

4. 调整 Clip Black / Clip White
   - Clip Black: 增大 → 更多区域变黑(抠掉)
     目标: 背景全黑, 没有灰色残留
   - Clip White: 减小 → 更多区域变白(保留)
     目标: 主体全白, 没有透明区域

5. Screen Matte 参数
   - Screen Softness: 1-3px (柔和边缘)
   - Screen Shrink/Grow: -1 ~ +1px (收边/扩边)
   - Screen Despot Black: 去除黑点
   - Screen Despot White: 去除白点

6. 返回 Final Result 视图
   如果边缘有绿色残留 → 进入第7步

7. 色溢抑制 (Spill Suppression)
   - Key Cleaner: Effects → Keying → Key Cleaner
   - Advanced Spill Suppressor: Effects → Keying → Advanced Spill Suppressor
   - 或: Keylight 内置 → Spill Suppression 调 Despill Bias

8. 精细调整
   - 如果头发/细节丢失: 降低 Clip Black
   - 如果背景残留: 增大 Clip Black
   - 如果有噪点: 增大 Screen Softness
```

### 多键叠加（处理不均匀绿幕）

```
问题: 绿幕亮度不均 (阴影区 + 亮区)
解决: 多个 Keylight 叠加

步骤:
1. 第一个 Keylight: 处理亮区绿幕
   → 调好亮区 → 背景阴影区可能残留

2. 复制图层 → 第二个 Keylight on 复制层
   → 用不同 Screen Color 采样阴影区绿色

3. 第二个图层的 Mask: 只覆盖阴影区域
   (用 Pen Tool 画大Mask → 大量 Feather 柔和过渡)

4. 两个图层叠加 → 完整抠像
```

### 拍摄绿幕素材的建议

```
✅ 快门速度 1/80 - 1/100 (减少运动模糊)
✅ 绿幕离主体至少1.5米 (减少绿色溢出)
✅ 绿幕均匀打光 (光比不超过1档)
✅ 主体与背景分离打光
✅ 用无压缩或低压缩素材 (ProRes, DNxHR)
❌ 避免穿绿色/反光衣服
❌ 避免细碎毛发漂浮 (后期难处理)
❌ 避免浅景深拍摄 (模糊边缘难抠)
```

---

## 🎯 动态追踪 (Motion Tracking)

### 点追踪 (Point Tracker)

```
适用: 简单的XY位移追踪、屏幕内容替换
速度: 快

步骤:
1. Window → Tracker
2. 选素材 → Track Motion
3. 放置追踪点在有高对比度特征的位置
   - 特征点: 角点、边缘交点、高对比区域
   - 内框: 特征本身
   - 外框: 搜索区域 (每帧搜索范围)
4. 点击 Analyze Forward
5. 如果追踪飘移: 手动修正 → 继续Analyze
6. Edit Target → 选择要应用的图层
7. Apply → X/Y

Track Type:
  - Transform: 只追踪XY位置
  - Stabilize: 反向追踪 → 稳定画面
  - Parallel Corner Pin: 4点透视追踪
  - Perspective Corner Pin: 透视变换
```

### 3D Camera Tracker

```
适用: 追踪摄像机运动 → 插入3D/2D元素
速度: 慢 (需要分析时间)

步骤:
1. 选素材 → Effects → Perspective → 3D Camera Tracker
2. 等待分析完成
   - 多彩色十字出现
   - 绿色 = 高置信 (用这些)
   - 黄色 = 中等 (少用)
   - 红色 = 低 (避免)

3. 框选一组绿色追踪点
   - 选共面的点 (在同一表面上)
   - 选稳定不跳变的点

4. 右键 → 创建:
   - Create Camera: 创建匹配运动的摄像机
   - Create Solid: 创建贴附到追踪面的固态层
   - Create Text: 创建贴附的文字
   - Create Null: 创建追踪Null (最灵活)
   - Create Shadow Catcher (2024)

5. 如果追踪不准:
   - 删除跳跃的红色/黄色点
   - 删除大面积移动物体上的点(车/人等)
   - 重新Solve

6. 插入的3D元素自动匹配原始摄像机的:
   - 位置、旋转、焦距、透视畸变
```

### Mocha AE 平面追踪

```
适用: 屏幕替换、广告牌、衣服标志、任何平面纹理
优势: 比点追踪更稳定(处理旋转/缩放/透视)

步骤:
1. Effects → Boris FX Mocha → Mocha AE
2. Mocha界面打开
3. 用 X-Spline 工具画追踪区域
   - 沿平面边缘画(电视屏幕、广告牌)
   - 包含一些额外边缘用于参考
4. 选中图层 → Track Forward
5. 检查追踪 → 有问题处手动修正
6. Export → 选导出类型:
   - Corner Pin (Support): 透视贴附
   - Transform: 位置/缩放/旋转
7. Copy to Clipboard
8. 回AE → 选目标图层 → Paste
9. Mocha自动创建:
   - Corner Pin效果 (或 Transform关键帧)
   - 目标图层完美贴附到追踪面
```

---

## 🧩 综合合成技巧

### 抠像后合成检查清单

```
□ Alpha通道干净: 主体=白, 背景=黑, 半透明区=灰
□ 边缘无锯齿/阶梯
□ 无绿色溢出 (decontamination)
□ 光线方向匹配 (主体受光 vs 背景光源)
□ 颜色匹配 (主体色调 vs 背景色调)
□ 颗粒/噪点匹配 (主体 vs 背景)
□ 运动模糊方向匹配
□ 景深匹配 (主体焦点 vs 背景焦点)
□ 阴影投射 (Shadow Catcher)
□ 镜子/反射面处理
```

### 背景融合技巧

```
1. 色温匹配
   主体层 → Effects → Color Correction → Lumetri Color
   Temperature 调暖/冷以匹配背景

2. 亮度匹配
   主体层 → Curves
   调 Gamma 以匹配背景中间调

3. 颗粒匹配
   背景层 → Effects → Noise & Grain → Add Grain
   记录颗粒大小/强度
   主体层 → 同样 Add Grain 参数

4. 边缘融合
   遮罩层 → Matte → Simple Choker
   Choke Matte -0.5 ~ -1 (轻微收缩)
   再加 Feather 1-3px

5. 光包裹 (Light Wrap)
   主体边缘轻微"吸收"背景光
   方法: 主体 Duplicate → 用背景做 Displacement Map
   加 Fast Blur 2-5px → Blend: Screen 10-30%
```

---

## 📦 推荐插件工具

| 工具 | 用途 | 来源 |
|------|------|------|
| Keylight 1.2 | 基础抠像 | AE内置 |
| Key Cleaner | 遮罩清洁 | AE内置 |
| Advanced Spill Suppressor | 色溢抑制 | AE内置 |
| Roto Brush 3.0 | AI抠像 | AE内置 |
| Mocha AE | 平面追踪 | AE内置 |
| 3D Camera Tracker | 摄像机追踪 | AE内置 |
| Rubberhose 3 | 骨骼绑定 | Battle Axe (付费) |
| DuIK | 角色绑定/IK | RxLaboratory (免费) |
| Lockdown | 变形面追踪 | aescripts (付费) |
| Silhouette | 专业抠像 | Boris FX (付费) |
| Primatte Keyer | 高级抠像 | Red Giant (付费) |
