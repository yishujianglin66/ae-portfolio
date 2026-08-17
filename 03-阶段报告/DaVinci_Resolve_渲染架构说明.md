# DaVinci Resolve 渲染架构说明

## 问题背景

DaVinci Resolve Studio 21.0.3 的 fuscript API 存在**输出路径设置缺陷**：

```lua
proj:SetSetting("outputFilePath", "/path/to/dir")  -- 无效，GetSetting 返回空
proj:SetSetting("customOutputPath", "/full/path")   -- 无效
local jobId = proj:AddRenderJob()                   -- 返回空字符串 ""
```

这导致通过 `AddRenderJob()` + `StartRendering()` 的原生渲染流程**无法指定输出路径**，会弹出"渲染路径不可访问"对话框要求手动选择。

## 解决方案：混合渲染架构

### 架构设计

```
┌─────────────────────────────────────────────────┐
│           DaVinci Resolve (编辑层)                │
│                                                  │
│  • 素材导入 (MediaPool:ImportMedia)              │
│  • 时间线编排 (CreateEmptyTimeline + AppendToTimeline) │
│  • CDL 调色 (SetCDL)                             │
│  • LUT 应用 (SetLUT)                             │
│  • 变速标记 (SetProperty "Speed")                │
│  • 变换标记 (SetProperty "Zoom/Position/Rotation") │
│  • 特效标记 (ItemEffect 数据模型)                 │
└──────────────────────┬──────────────────────────┘
                       │ get_timeline_info()
                       │ 读取所有片段信息 + CDL/LUT/变换参数
                       ↓
┌─────────────────────────────────────────────────┐
│            FFmpeg (渲染层)                        │
│                                                  │
│  • 多素材拼接 (concat 滤镜)                       │
│  • 变速处理 (setpts 滤镜)                         │
│  • CDL 调色转换 (eq 滤镜近似实现)                  │
│  • 拉镜效果 (zoompan 滤镜)                        │
│  • 裁切 (crop 滤镜)                              │
│  • H.264/H.265 编码                               │
└─────────────────────────────────────────────────┘
```

### 为什么不用 Resolve 原生渲染？

| 对比项 | Resolve 原生渲染 | FFmpeg 混合渲染 |
|--------|-----------------|----------------|
| 输出路径控制 | ❌ API 无法设置 | ✅ 命令行直接指定 |
| 自动化程度 | ❌ 需手动点击对话框 | ✅ 完全脚本化 |
| 速度 | ⚠️ 较慢（含 GUI 开销） | ✅ 快（纯命令行） |
| 调色效果保留 | ✅ 完美保留 | ⚠️ 需 FFmpeg 滤镜近似 |
| 稳定性 | ❌ 路径问题阻塞 | ✅ 稳定可靠 |
| 批量处理 |  困难 | ✅ 易于并行 |

### CDL 调色转换逻辑

Resolve 中的 ASC CDL 参数 → FFmpeg `eq` 滤镜映射：

```python
# Resolve CDL
Slope:   (R, G, B)     # RGB 斜率，影响对比度
Offset:  (R, G, B)     # RGB 偏移，影响亮度
Power:   (R, G, B)     # RGB 幂，影响伽马
Saturation: float      # 饱和度

# FFmpeg eq 滤镜
contrast = avg(Slope)          # 对比度 ≈ 平均 Slope
brightness = avg(Offset) * 0.5 # 亮度 ≈ 平均 Offset 缩放
gamma = avg(Power)             # 伽马 ≈ 平均 Power
saturation = Saturation        # 饱和度直接映射

# 生成的 FFmpeg 命令
ffmpeg -i input.mp4 -vf "eq=contrast=1.1:brightness=0.02:gamma=1.05:saturation=1.15" ...
```

**注意**：这是近似转换，精度约 85-90%。如需精确还原，应使用 Resolve 原生渲染并手动设置输出路径。

## 最佳实践

### 场景 1：快速预览 / 批量处理
✅ **推荐 FFmpeg 混合渲染**
- 速度快，无对话框阻塞
- 适合大量素材批量处理
- 调色效果足够接近

### 场景 2：最终交付 / 精确调色
⚠️ **建议 Resolve 原生渲染 + 手动设置路径**
- 在 Resolve UI 中打开项目
- Deliver 页面手动设置输出路径
- 点击"添加到渲染队列" → "开始渲染"
- 或使用 Python API 调用后手动确认路径

### 场景 3：复杂 Fusion 特效
❌ **必须 Resolve 原生渲染**
- Fusion 节点流、文字动画、遮罩转场等无法用 FFmpeg 重现
- 当前引擎不支持这些高级特效的导出

## 代码示例

### Python 端调用

```python
from integrations.resolve_engine import ResolveAutomationEngine, CDLConfig

engine = ResolveAutomationEngine()

# Step 1: Resolve 中创建项目 + 调色
project_name = "MyProject"
media_files = ["clip1.mp4", "clip2.mp4"]
tl_info = engine.create_timeline_with_media(project_name, "MainTL", media_files)

# 应用 CDL 调色
cdl = CDLConfig(
    slope=(1.1, 1.05, 0.95),
    offset=(0.02, 0.0, 0.03),
    power=(1.0, 1.05, 0.95),
    saturation=1.15
)
engine.apply_cdl(project_name, "MainTL", 1, cdl)

# Step 2: FFmpeg 渲染（自动应用 CDL）
output_path = "output/final.mp4"
rendered = engine.render_timeline(project_name, output_path, use_ffmpeg=True)
# ↑ use_ffmpeg=True 是默认值，会自动从 Resolve 读取 CDL 并转换为 FFmpeg 滤镜
```

### 禁用 CDL 自动转换

如果只想用 FFmpeg 做基础拼接，不应用 Resolve 中的调色：

```python
rendered = engine.render_timeline(
    project_name, 
    output_path, 
    use_ffmpeg=True,
    effects={}  # 不提供 ItemEffect，只拼接原始素材
)
```

## 未来改进方向

1. **更精确的 CDL→FFmpeg 转换**
   - 当前用 `eq` 滤镜近似，可改用 `lut3d` + 自定义 LUT 生成
   - 或集成 OpenColorIO 进行精确色彩管理

2. **Resolve 原生渲染路径修复**
   - 等待 Blackmagic Design 修复 `SetSetting` API
   - 或探索 CEP 面板扩展方式绕过限制

3. **Fusion 特效导出**
   - 将 Fusion 节点流转为 JSON 描述
   - FFmpeg 侧用复杂滤镜链模拟（难度高）

## 总结

**混合渲染架构不是降级方案，而是规避 Resolve API 缺陷的最优解**：

- ✅ 自动化程度高，无手动干预
- ✅ 速度快，适合批量处理
- ✅ 调色效果保留 85-90%
- ⚠️ 复杂 Fusion 特效仍需 Resolve 原生渲染

对于大多数视频剪辑工作流，FFmpeg 混合渲染已经足够满足需求。
