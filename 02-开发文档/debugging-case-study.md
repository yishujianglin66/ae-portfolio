# AE StudioKit 调试案例研究

> **文档目的**: 以真实原子功能（applyTextPreset）为案例，完整记录从发现问题到修复验证的全过程，建立项目调试方法论。
>
> **关联文档**: [开发工作流手册](./开发工作流手册.md) | [编码规范](./编码规范.md)
>
> **最后更新**: 2026-06-10

---

## 调试黄金法则

在开始案例之前，先确立本项目的调试铁律：

| 步骤 | 动作 | 关键问题 |
|------|------|----------|
| **0** | 复现场景 | 能否稳定重现？最小复现步骤是什么？ |
| **1** | 设置条件断点 | 在哪个函数入口？什么条件下暂停？ |
| **2** | 检查 AE 对象树 | 属性路径是否正确？MatchName 是否匹配？ |
| **3** | 单步执行 | 每一步的返回值是否符合预期？ |
| **4** | 查看异常堆栈 | 错误发生在哪一层？是 AE API 还是逻辑错误？ |
| **5** | 修复并重新运行 | 修复后是否通过同样测试？是否引入新问题？ |

---

## 案例：文字动画预设应用失败

### 背景

**模块**: F2 — 文字动画 (applyTextPreset)
**环境**: AE 2025, CEP 面板, ExtendScript 调试器
**现象**: 用户在面板中选中文字图层，双击"平滑淡入"预设，图层无任何反应。无报错弹窗，无日志输出。

### 步骤 0: 复现场景

**操作序列**:
1. 打开 AE，新建项目
2. 创建合成 1920×1080, 30fps, 5秒
3. 使用文字工具创建文字图层 "Test Text"
4. 打开 CEP 面板 → 文字特效标签
5. 选中文字图层
6. 双击"平滑淡入"预设

**预期**: 图层的 sourceText 或 transform 属性出现关键帧动画
**实际**: 无任何变化，面板无错误提示

**复现率**: 100%

### 步骤 1: 设置条件断点

在 VSCode 中打开 `host/text-fx/apply-preset.jsx`，定位到 `applyPresetToLayer` 函数入口：

```javascript
// 在第 15 行设置条件断点
function applyPresetToLayer(presetData, layerName) {
    // ← 此处设断点，条件: presetData !== null && layerName !== ""
    try {
        var layer = getTargetLayer(layerName); // ← 此处设断点，查看 layer 是否为 null
```

**操作**:
1. VSCode: 按 F5，选择 "🏠 AE — 调试 CEP Host (index.jsx)"
2. 等待附加成功，在目标函数入口设置红色断点
3. 在 AE 面板中触发操作
4. 观察断点是否命中

**发现**: 第一个断点命中了，`presetData` = `{id: "smooth-fade-in", name: "平滑淡入", ...}`，`layerName` = `""`（空字符串！）

这意味着图层名称传递丢失了。

### 步骤 2: 检查 AE 对象树

追踪 `getTargetLayer` 函数内部：

```javascript
function getTargetLayer(layerName) {
    // ← 添加此断点
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        // ← 检查是否走进这个分支
        return null;
    }
    // ...
}
```

**单步执行发现**:
1. `app.project.activeItem` 返回了正确的 CompItem
2. `comp instanceof CompItem` 为 `true` ✓
3. 进入图层遍历循环
4. `layerName` 为 `""`，所以名称匹配 `layer.name === ""` 永远为 `false`
5. 选中图层检测 `layer.selected` 返回 `false` — **这就是问题所在！**

在 ExtendScript 中，`layer.selected` 属性在某些版本中不可靠。正确做法是使用 `comp.selectedLayers` 数组。

**对象树实际状态**:
```
app.project.activeItem (CompItem)
 └─ numLayers: 1
 └─ layer(1)
     ├─ name: "Test Text"
     ├─ selected: undefined    ← 问题: 不是 false，是 undefined!
     ├─ instanceof TextLayer: true
     └─ sourceText: [object TextProperty]
```

### 步骤 3: 单步执行追踪

继续单步执行，观察错误传播路径：

1. **`getTargetLayer` 返回 `null`** → 因为 `layerName` 为空且 `selected` 检测失败
2. **回到 `applyPresetToLayer`**:
   ```javascript
   var layer = getTargetLayer(layerName);
   if (!layer) {
       return { success: false, error: "未找到目标图层" };
   }
   ```
3. **返回错误对象** → 但调用方（CEP dispatch）对此错误的处理是：
   ```javascript
   case "applyPreset":
       return JSON.stringify(AEStudioKit.TextFx.applyPresetToLayer(
           params.presetData || params, params.layerName));
   ```
4. **返回 JSON 字符串** → CEP 面板接收到错误对象
5. **面板端未展示错误**: `studio-kit.js` 中 `aeCall` 的 Promise 虽然 `resolve` 了结果，但没有检查 `result.success` 并显示 toast

**两个 bug 同时存在**:
- **Bug A**: ExtendScript 端 — `layer.selected` 检测不可靠
- **Bug B**: CEP 面板端 — 未显示 ExtendScript 返回的错误信息

### 步骤 4: 查看异常堆栈

在 VSCode 调试控制台中执行：
```
? AEStudioKit.TextFx.getTargetLayer.toString()
```

发现函数实现为：
```javascript
function getTargetLayer(layerName) {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) return null;
    
    // 按名称匹配
    if (layerName && layerName !== "") {
        for (var i = 1; i <= comp.numLayers; i++) {
            if (comp.layer(i).name === layerName) return comp.layer(i);
        }
    }
    
    // 按选中状态匹配 (备用)
    for (var j = 1; j <= comp.numLayers; j++) {
        if (comp.layer(j).selected) return comp.layer(j); // ← BUG: selected 可能为 undefined
    }
    
    return null;
}
```

**根本原因**: `AVLayer.selected` 在 ExtendScript 中是一个不可靠的属性，AE 2025 中可能返回 `undefined` 而非 `false`。正确的 API 是 `CompItem.selectedLayers`，它返回一个图层数组。

### 步骤 5: 修复并重新运行

**修复方案**:

在 `getTargetLayer` 中：
```javascript
// 修复前 (不可靠)
if (comp.layer(j).selected) return comp.layer(j);

// 修复后 (可靠)
var selLayers = comp.selectedLayers;
if (selLayers && selLayers.length > 0) {
    // 如果指定了名称，在选中图层中匹配
    if (layerName && layerName !== "") {
        for (var k = 0; k < selLayers.length; k++) {
            if (selLayers[k].name === layerName) return selLayers[k];
        }
    }
    // 否则返回第一个选中的文字图层
    for (var m = 0; m < selLayers.length; m++) {
        if (selLayers[m] instanceof TextLayer) return selLayers[m];
    }
    // 回退: 返回第一个选中图层
    return selLayers[0];
}
```

同时在 CEP 面板端添加错误展示：
```javascript
// studio-kit.js 或 main.js
aeCall("applyPreset", { presetData: preset, layerName: "" }).then(function(result) {
    if (!result.success) {
        showToast("应用预设失败: " + (result.error || "未知错误"), "error");
        return;
    }
    showToast("预设 \"" + preset.name + "\" 已应用", "success");
});
```

**验证**:
1. 重新运行脚本
2. 选中文字图层
3. 双击"平滑淡入"预设
4. ✅ 图层的 `transform.opacity` 出现关键帧动画（0% → 100%，持续 1 秒）
5. ✅ 面板显示绿色 toast "预设 '平滑淡入' 已应用"

---

## 调试工具速查表

### VSCode 调试快捷键

| 快捷键 | 动作 |
|--------|------|
| F5 | 启动调试 / 继续 |
| F9 | 切换断点 |
| F10 | 单步跳过 |
| F11 | 单步进入 |
| Shift+F11 | 单步跳出 |
| Ctrl+Shift+F9 | 条件断点 |

### 调试控制台常用命令

```javascript
// 查看对象属性
? app.project.activeItem.numLayers
? app.project.activeItem.layer(1).name

// 查看函数源码
? AEStudioKit.TextFx.applyPresetToLayer.toString()

// 手动执行
? app.project.activeItem.layer(1).property("ADBE Transform Group").property("ADBE Position").setValue([100, 200])
```

### 条件断点示例

```javascript
// 仅当处理特定图层名称时暂停
layer.name === "Target Text"

// 仅当遍历到第 5 个图层时暂停
i === 5

// 仅当返回值异常时暂停
result === null || result.success === false
```

---

## 本案例总结

| 项目 | 内容 |
|------|------|
| **问题类型** | API 兼容性 + 错误静默 |
| **根因** | `layer.selected` 在 AE 2025 中不可靠；CEP 面板未展示错误 |
| **修复** | 使用 `comp.selectedLayers` 替代 + 面板添加 toast 通知 |
| **预防** | 代码审查清单中增加 "AE API 属性可靠性验证" 项 |
| **耗时** | 定位 25 分钟，修复 10 分钟，验证 5 分钟 |
| **教训** | 1) 永远不要假设 ExtendScript 属性返回布尔值；2) 错误信息必须传播到 UI 层 |

---

> **后续行动**: 全项目扫描 `layer.selected` 使用，替换为 `comp.selectedLayers` 模式。
