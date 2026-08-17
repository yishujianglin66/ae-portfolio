# AE 附加式 JSX 脚本库（ae_additive_scripts）

本目录存放从已退役的自研 `ae-mcp-server` 中**抢救**出来的有价值 JSX 功能脚本。
它们以**附加式**方式接入开源 AE MCP 基线，**不修改**开源 bridge 与服务器源码。

## 调用方式（经开源 execute-atom-script 工具）

开源 `AfterEffectsMCP` 的 `execute-atom-script` 工具会对 `scriptContent` 执行 `eval()`。
由于 `eval()` 不解析 ExtendScript 的 `#include`，需先用本目录的助手把 `_lib` 依赖内联：

```bash
# 列出所有可用附加脚本
py -3.12 run_additive_jsx.py --list

# 组装自包含 scriptContent（输出到 stdout 或 --out 文件）
py -3.12 run_additive_jsx.py applyColorCorrection "{\"compName\":\"Comp 1\",\"layerIndex\":1,\"correctionType\":\"full_grade\"}" --out payload.jsx
```

然后把生成的 `payload.jsx` 内容作为 `execute-atom-script` 的 `scriptContent` 参数传入即可。
执行结果会存入 AE 全局 `$.global.__aeAdditiveResult`，可用 `run-script` 读取。

## 脚本约定

- 每个 JSX 定义一个与文件同名的全局函数 `<name>(args)`，返回 JSON 字符串
  （由 `_lib/response_utils.jsx` 的 `buildSuccess` / `buildError` 构建）
- 依赖的工具库放在 `_lib/`，通过 `#include "_lib/xxx.jsx"` 引入（助手会自动内联）

## 可用脚本

| 脚本 | 功能 |
|------|------|
| `applyColorCorrection` | 专业级色彩校正（curves/levels/hue_saturation/color_balance/channel_mixer/color_wheels/full_grade）|
| `applyTracker` | 运动跟踪应用 |
| `apply3DComposition` | 3D 合成搭建 |
| `applyExpression` | 表达式应用 |
| `addTextLayerAdvanced` | 高级文字图层 |
| `applyTextAnimation` | 文字动画 |
| `createSubtitleTemplate` | 字幕模板创建 |
| `trackedSubtitle` | 跟踪字幕 |
| `batchApplySubtitles` | 批量字幕应用 |

## 注意

- 这些脚本来源于已归档的 `archive/deprecated_self_built_bridge/ae-mcp-server/`
- 新增功能请遵循"附加式"原则：独立 JSX 放本目录，经 `execute-atom-script`/`run-script` 调用，
  切勿修改开源 `mcp-bridge-auto.jsx` 或 `after-effects-mcp-main/src/index.ts`
