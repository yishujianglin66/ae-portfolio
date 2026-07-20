# F2 — 文字图层基础动画应用: 完整研究报告

> 日期: 2026-06-05 | 版本: v1.0.0 | 状态: 待用户验证

---

## A. 对象模型验证

### Text Animator API 路径确认

```
Layer
  └── .property("ADBE Text Properties")          // PropertyGroup
        └── .property("ADBE Text Animators")      // PropertyGroup
              ├── .canAddProperty("ADBE Text Animator")
              └── .addProperty("ADBE Text Animator") → Animator
                    ├── .property("ADBE Text Selectors")
                    │     ├── .canAddProperty("ADBE Text Selector")
                    │     └── .addProperty("ADBE Text Selector") → Selector
                    │           ├── .property("ADBE Text Percent Start")    → float 0-100
                    │           ├── .property("ADBE Text Percent End")      → float 0-100
                    │           ├── .property("ADBE Text Percent Offset")   → float -100~100
                    │           └── .property("ADBE Text Range Advanced")
                    │                 ├── .property("ADBE Text Selector Based On")   → 1/2/3
                    │                 └── .property("ADBE Text Selector Smoothness") → float 0-100
                    └── .property("ADBE Text Animator Properties")
                          ├── .canAddProperty("ADBE Text Opacity")
                          ├── .canAddProperty("ADBE Text Position 3D")
                          ├── .canAddProperty("ADBE Text Scale 3D")
                          └── .canAddProperty("ADBE Text Rotation")
```

所有 API 在 AE CS4+ 中可用，本实现针对 AE 2023-2025 确认兼容。

### matchName 参考表

| matchName | 属性 | 取值类型 |
|-----------|------|---------|
| `ADBE Text Opacity` | 不透明度 | float 0-100 |
| `ADBE Text Position 3D` | 三维位置 | [x, y, z] |
| `ADBE Text Scale 3D` | 三维缩放 | [x%, y%, z%] |
| `ADBE Text Rotation` | 旋转 | float degrees |
| `ADBE Text Fill Color` | 填充色 | [r, g, b] 或 [r, g, b, a] |

---

## B. 代码骨架

### 文件: `F2_text_anim.jsx` (~345 行)

**配置区** (脚本开头):
```javascript
var CONFIG = {
    animationType: "fadeIn",   // 修改此处切换动画
    duration: 1.0,             // 时长 0.1-10.0
    intensity: 1.0,            // 强度 0.0-1.0
    charMode: 1,               // 1=逐字 2=逐词 3=逐行
    smoothness: 40             // 平滑度 0-100
};
```

**核心函数**:

| 函数 | 职责 |
|------|------|
| `_getAnimatorsGroup(layer)` | 获取文字 Animators 属性组 |
| `_addAnimator(layer)` | 创建新 Animator |
| `_addSelector(animator)` | 创建新 Range Selector |
| `_addAnimProp(animator, matchName)` | 添加动画器属性 |
| `_setSelectorRange(s, start, end, offset)` | 设置选择器范围 |
| `_setSelectorMode(s, mode)` | 设置选择器模式 |
| `_setSelectorSmoothness(s, val)` | 设置平滑度 |
| `_setKeyframe(prop, time, value, easeIn, easeOut)` | 安全设置关键帧+缓动 |
| `_isTextLayer(layer)` | 3 路径文字图层检测 |
| `_animFadeIn(layer, ...)` | fadeIn 动画实现 |
| `_animScalePop(layer, ...)` | scalePop 动画实现 |
| `_animSlideLeft(layer, ...)` | slideLeft 动画实现 |
| `runF2TextAnimation()` | 主入口 |

---

## C. 静态模拟执行

### C1: 无文字图层选中

```
输入: 选中了一个 ShapeLayer
执行路径:
  runF2TextAnimation()
    → 获取 sel = comp.selectedLayers
    → 遍历分类: _isTextLayer(ShapeLayer) → false
    → nonTextLayers = [ShapeLayer]
    → textLayers = []
    → alert: "未选中文字图层。当前图层: 'Shape Layer 1' (形状图层)"
    → return null
预期: alert 弹窗, 不修改任何图层
```

### C2: 选中 1 个文字图层 + fadeIn

```
输入: TextLayer "Hello 测试" + animationType="fadeIn"
执行路径:
  runF2TextAnimation()
    → _isTextLayer → true
    → _animFadeIn(layer, 1.0, 0, 1.0, 1, 40)
       → _addAnimator → Animator 1
       → _addAnimProp("ADBE Text Opacity") → Opacity prop, setValue(0)
       → _addSelector → Range Selector 1
       → Start: setValueAtTime(0, 0) + setValueAtTime(1.0, 100)
    → app.redraw()

预期可观测输出:
  - 文字图层的 Text → Animator 1 → Range Selector 1 被创建
  - Opacity 属性显示 0%
  - Start 属性有 2 个关键帧: 0s=0, 1s=100
  - 时间轴: 文字逐字淡入出现
```

### C3: 选中 1 个文字图层 + scalePop

```
预期可观测输出:
  - Scale 属性有 3 个关键帧: 0s=[0,0,100], 0.5s=[120,120,100], 1s=[100,100,100]
  - 时间轴: 文字从 0% 弹到 120% 再回弹到 100%
```

### C4: 选中 1 个文字图层 + slideLeft

```
预期可观测输出:
  - Position 属性显示 [-200, 0, 0]
  - Offset 属性有 2 个关键帧: 0s=0, 1s=100
  - 时间轴: 文字从左侧滑入
```

### C5: 选中 3 个文字图层 + 批量应用

```
输入: 3 个 TextLayer
预期: 每个文字图层独立创建 Animator, 全部成功
```

### C6: 选中混合图层 (2 文字 + 2 形状)

```
预期:
  - 2 个文字图层成功应用动画
  - 2 个形状图层被跳过
  - alert: "成功: 2 / 失败: 0 / 跳过 2 个非文字图层"
```

---

## D. 异常注入

### D1: 文字图层无 Text 属性 (极端情况)
```
代码行为: _getAnimatorsGroup 返回 null → 每个动画函数中 throw
预期: catch 捕获, 标记为 FAIL, 不崩溃
```

### D2: canAddProperty 返回 false
```
代码行为: _addAnimProp 检查 canAddProperty, false 时尝试获取已有属性
预期: 返回已有属性或 null, 不崩溃
```

### D3: duration=0 (非法配置)
```
代码行为: runF2TextAnimation 中 duration ≤ 0 → clamped to 1.0
预期: WARN 日志, 使用默认 1.0s
```

---

## E. 测试用例说明书

### 测试 T1: fadeIn

1. 在 F1_Test_Comp 中选中文字图层 "Hello 测试"
2. 打开 `F2_text_anim.jsx`
3. 确认 CONFIG 中: `animationType: "fadeIn"`, `duration: 1.0`
4. 运行脚本
5. **观察时间轴**: 展开文字图层 → Animator 1 → Range Selector 1
   - Opacity: 0%
   - Start: 0s 关键帧值=0, 1s 关键帧值=100
6. 按空格预览: 文字应逐字淡入

### 测试 T2: scalePop

1. 修改 CONFIG.animationType 为 "scalePop"
2. 运行脚本
3. **观察**: Scale 三个关键帧 [0,0,100] → [120,120,100] → [100,100,100]

### 测试 T3: slideLeft

1. 修改 CONFIG.animationType 为 "slideLeft"
2. 运行脚本
3. **观察**: Position [-200,0,0], Offset 0→100 关键帧

### 测试 T4: 非文字图层

1. 选中形状图层
2. 运行脚本
3. **预期 alert**: "未选中文字图层。当前图层..."

---

## F. 通过标准

1. ✅ fadeIn/scalePop/slideLeft 三种动画均可正常工作
2. ✅ 每种动画在时间轴上产生预期数量和位置的关键帧
3. ✅ 非文字图层被正确识别并跳过
4. ✅ 异常参数 (duration≤0, intensity 越界) 被 clamp 而非崩溃
5. ✅ Undo 组正确包裹, 可按 Ctrl+Z 撤销
6. ✅ 无 ES6 语法
