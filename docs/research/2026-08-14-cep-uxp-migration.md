# CEP → UXP 迁移评估 (AE 2025+ 兼容性预留)

> 2026-08-14 | 依据: 工具生态调研 (docs/research/2026-08-14-audit-web-tools.md)
> "AE 2025 已移除 CEP" + 本地 cep_panel 现状核查

## 一、现状盘点

| 组件 | 路径 | CEP 依赖 | 状态 |
|---|---|---|---|
| CEP 面板 | `cep_panel/com.ae.knowledgevault/` (8 文件) | **是** (CSXS manifest v7.0) | 仅 AE ≤ 2024 可用 |
| AE 主监听 | `ae_mcp_auto_listener.jsx` (File > Scripts 运行) | **否** | 全版本可用 ✅ |
| 桥接核心 | `.ae-mcp-bridge/` 文件轮询协议 | **否** | 与宿主 UI 无关 ✅ |
| 自启动 | PS/PR 用 Presets\Scripts\ 自动加载 | **否** | AE 亦支持 ✅ |

**关键结论**: 项目核心链路 (JSX 监听 + 文件交换) **不依赖 CEP**。
CEP 面板只是可选 UI 壳, 其功能 (启动/停止监听、查看日志) 全部可由
File > Scripts + 日志文件替代。CEP 移除影响面 = 仅面板 UI。

## 二、manifest 现状问题

`cep_panel/.../CSXS/manifest.xml` 声明 `Host Version="[15.0,99.9]"` —
暗示支持到 AE 99.9, 但 AE 2025 (v25) 起不再加载 CEP 扩展,
该声明名不副实。修复选项:
1. 收紧为 `[15.0,24.9]` 如实声明 (推荐, 一行改动)
2. 保留并加 README 免责声明

## 三、UXP 迁移路径

1. **工具**: UXP Developer Tool (UDT, Adobe 官方), manifest v5 JSON
   (manifest.json 替代 CSXS XML)
2. **UI**: UXP 面板基于 Spectrum UXP 组件 (原 CEP 面板为原生 HTML+CSInterface,
   需重写 UI 层, 通信改 `require("uxp").scripting` 或文件交换)
3. **宿主脚本**: AE 2025 UXP 对 ExtendScript 宿主访问与批处理 API 支持
   有限 — **文件交换协议保持为唯一可靠的跨版本通道**, UXP 面板只做
   "启动/停止/读日志"的 UI, 不承载核心逻辑 (与现在 CEP 面板的分工一致)
4. **兼容策略**: JSX 监听器 (File > Scripts) 保持为生产通道;
   CEP 面板保留给 AE ≤ 2024; UXP 面板为 AE 2025+ 增量交付

## 四、迁移优先级建议

| 优先级 | 动作 | 成本 |
|---|---|---|
| P0 | manifest Host Version 收紧 `[15.0,24.9]` | 一行 |
| P1 | 安装 UXP Developer Tool, 建最小 UXP 面板骨架 (启动/停止按钮 → 文件交换) | 半日 |
| P2 | 面板 UI 完整复刻 (日志查看/命令测试) | 1-2 日 |
| P3 | 废弃 cep_panel (AE ≤ 2024 用户退场后) | — |

## 五、已验证事实 (落地时直接引用)

- AE 2025+ 不加载 CEP; File > Scripts 与 Presets\Scripts 自动加载仍受支持
- PS 2025 已实践 Presets\Scripts 自启动 (见 bridges/ps_bridge_client.py
  部署说明), AE 同机制
- 本项目 D-24 已把 JSX 路径解析改为四级回退 (环境变量/脚本路径/候选表),
  与 UXP 面板组合部署无障碍
