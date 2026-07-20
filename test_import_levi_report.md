# AE MCP importFootage 实战测试报告

## 测试目标
验证 AE MCP Bridge 的 `importFootage` 能力以及批量导入利威尔素材后图层在时间轴上的正确排列。

## 测试环境
- AE 2025 (25.x)
- MCP Bridge Auto panel (`mcp-bridge-auto.jsx`)
- 素材来源：`C:\Users\Administrator\Desktop\视频剪辑工作流\利威尔剪辑素材`

## 修复项

### 1. mcp-bridge-auto.jsx JSON / Date polyfill 前置
- **问题**：`JSON` 与 `Date.prototype.toISOString` 的 polyfill 位于文件后半段（约第 1480 行），而多个工具函数在文件前半段（第 29 行起）已调用 `JSON.stringify`，导致面板加载时报错 `'JSON' 未定义`、`Date().toISOString 未定义`。
- **修复**：将 JSON / Date polyfill 移到文件最开头，在所有函数定义之前执行，并删除原位置重复代码。

### 2. 导入脚本图层索引漂移
- **问题**：批量添加图层时，新图层总是插入到最顶层，已保存的 `layer.index` 在后续添加后会失效。原脚本用保存的 index 重新获取图层并设置 `startTime`，导致时间轴设置到了错误的图层上，最终表现为多个图层重叠、只能看到一个视频。
- **修复**：在导入循环中保存图层对象引用（`layerRefs`），排列时间轴时直接使用引用设置 `startTime`，按每个素材的实际 `duration` 顺序排列。

## 待完成操作
1. 手动将 `AE-Knowledge-Vault/mcp-bridge-auto.jsx` 复制到 `C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels\`（沙箱限制，无法自动写入 Program Files）。
2. 启动 AE 2025，确认 MCP Bridge Auto 面板加载无报错。
3. 在 AE 中执行 `test_import_levi.jsx`（File > Scripts > Run Script File）。
4. 检查结果文件：`D:\AE-Work\日志与报告\test_import_result.json`。

## 预期结果
- 合成 `利威尔导入测试` 内包含 3 个素材图层。
- 每个图层按其实际时长首尾相接排列在时间轴上。
- 结果文件 `success: true`，并记录每个图层的 index、duration、resolution。

## 备注
- 测试脚本已输出日志到 `D:\AE-Work\日志与报告\`，符合知识库与生产文件分离的约定。
- 若 AE 仍提示首选项/临时文件夹权限错误，建议以管理员身份启动 AE 或重置首选项（启动时按住 Ctrl+Alt+Shift）。
