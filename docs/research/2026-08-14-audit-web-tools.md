# AE 自动化与视频工具链全网调研报告 (2026-08-14)

> 目标: 为「AE 自动化管线项目」做一次 6 大板块的全网调研 (26 次 web_search)。
> 方法: 逐项核验 2025-2026 最新方案，标注 名称 / URL / 类型 / 活跃度 / 许可 / 对应板块 / 集成成本评级 (P0 立即 / P1 规划 / P2 观望)。
> 标注约定: ⭐ = 重点新发现; ✅已拥有 = 项目本地已有，勿重复引入; ⚠️ = 需谨慎/有风险。

---

## TL;DR — 前 8 个新发现 (优先级排序)

| # | 发现 | 类型 | 一句话价值 | 评级 |
|---|---|---|---|---|
| 1 | **Adobe Firefly Services DGR API** | 官方云渲染 | Adobe 官方 MOGRT 云端渲染 API，绕开本地 AE 崩溃/监听不稳定痛点 | ⭐ P0 |
| 2 | **kumoproductions/mcp-aftereffects** | TypeScript MCP | 文件 IPC + 原子 undo 组，架构最贴近本项目，可作 bridge 重构参照 | ⭐ P1 |
| 3 | **forticheprod/py-aep** | AEP 解析 | 《双城之战》工作室 Fortiche 的 .aep Python 编辑库，对比项目自带 aep_binary_parser.py | ⭐ P1 |
| 4 | **yinkaisheng/Python-UIAutomation-for-Windows** | UI 自动化 | 成熟 MS UIA wrapper，替代"截图+点击"的语义级 UI 控制 | ⭐ P0 |
| 5 | **microsoft/UFO + FlaUI-MCP** | UI Agent/MCP | 微软官方 Windows UI agent + FlaUI MCP，UI 自动化可 MCP 化 | ⭐ P1 |
| 6 | **BabitMF/bmf** | GPU 视频框架 | 字节跳动开源，GPU 加速异构视频处理，补 FFmpeg 之外的 GPU 管线 | ⭐ P1 |
| 7 | **PyNvVideoCodec 2.0** | GPU 编解码 | NVIDIA 官方 Python GPU 编解码，适配 RTX 4060 加速 | ⭐ P1 |
| 8 | **MustafaJafar/AfterEffects-Prism-Plugin** | 渲染管线插件 | Prism 管线框架的 AE 插件，可作多 DCC 编排参照 | ⭐ P2 |

---

## 一、AE 自动化与 Adobe 官方 MCP 现状

### 1.1 核心结论

- **Adobe 官方 MCP 目前只有 Photoshop / Acrobat / Express**。2025 年 12 月 Adobe 宣布把
  Photoshop、Acrobat、Adobe Express 接入 ChatGPT ([Engadget](https://www.engadget.com/ai/adobe-brings-photoshop-acrobat-and-adobe-express-to-chatgpt-130000389.html))，
  官方 MCP server 已发布。**AE / Premiere Pro 官方 MCP 尚未发布** (截至调研日)。
- **AE 2025 已移除 CEP**，官方推动 UXP 迁移，但 AE 的 UXP 面板 API 覆盖不完整，
  社区抱怨迁移阻塞 ([CEP Removal and UXP Panel Support Issue #11655](https://forums.creativeclouddeveloper.com/t/after-effects-2025-cep-removal-and-uxp-panel-support-issue/11655))。
  本项目依赖 ExtendScript JSX listener (CEP 体系) 的技术债会随版本升级放大。
- 社区已出现多个 **AE MCP server**，但普遍质量参差，多基于 ExtendScript 或文件 IPC。

### 1.2 发现清单

| 名称 | URL | 类型 | 活跃度/许可 | 对应板块 | 评级 |
|---|---|---|---|---|---|
| Adobe 官方 MCP (PS/Acrobat/Express) | [adobe 官方 + Engadget](https://www.engadget.com/ai/adobe-brings-photoshop-acrobat-and-adobe-express-to-chatgpt-130000389.html) | 官方 MCP | 官方, 闭源 | MCP bridge 规范参照 | ⭐ P1 (仅作协议参照) |
| **kumoproductions/mcp-aftereffects** | [GitHub](https://github.com/kumoproductions/mcp-aftereffects) | TypeScript MCP server | 活跃, Windows/macOS | AE bridge 重构参照 | ⭐ P1 |
| matrayu/adobe-mcp | [GitHub](https://github.com/matrayu/adobe-mcp) | 统一 MCP (PS/PR/AI/ID) | 社区 | 多 DCC 统一 bridge | P2 |
| hodor/ae-mcp | [GitHub](https://github.com/hodor/ae-mcp) | AE MCP "more control" | 社区 | AE bridge | P2 |
| TheLlamainator/after-effects-mcp | [GitHub](https://github.com/TheLlamainator/after-effects-mcp) | ExtendScript MCP | 社区 | AE bridge | P2 (同源重复) |
| Dakkshin/after-effects-mcp | [GitHub](https://github.com/Dakkshin/after-effects-mcp) | ExtendScript MCP | 社区 | AE bridge | P2 (同源重复) |
| maaz997/after-effects-mcp | [GitHub](https://github.com/maaz997/after-effects-mcp) | AE MCP | 社区 | AE bridge | P2 |
| sunqirui1987/ae-mcp | [GitHub](https://github.com/sunqirui1987/ae-mcp) | AE MCP | 社区 | AE bridge | P2 |
| alisaitteke/photoshop-mcp | [GitHub](https://github.com/alisaitteke/photoshop-mcp) | PS MCP, 50+ tools | 社区 | PS bridge 参照 | P2 |

### 1.3 对项目的关键判断

1. **mcp-aftereffects 最值得研究**: 它用 **文件 IPC**（非轮询 HTTP）+ **原子 undo-grouped 操作** +
   JSON 项目导出/导入 + 单帧渲染，恰好解决项目痛点历史里的「AE 脚本监听不稳定」。
   建议对照它的 TypeScript 实现，评估本项目 JSX listener 是否需要换成文件 IPC 或更短的轮询心跳。
2. **UXP 迁移是长期必选项**: 项目 JSX 属 CEP 体系，AE 2025 起 CEP 已被官方移除；
   建议预留 UXP 迁移路线 (虽 UXP 在 AE 的脚本 API 仍不完整)。
3. **官方 MCP 短期指望不上 AE/PR**: 目前只能继续自建 bridge，或等 Adobe 扩展官方 MCP 覆盖。

---

## 二、视频编辑 Agent 竞品 (对比)

### 2.1 核心结论

2025-2026 是「视频编辑 Agent」爆发期，主流方向分三类：
1. **Agentic 剪辑** (LLM 规划 + 工具调用做选片/卡点/剪辑)。
2. **编码式视频生成** (Remotion 体系，Claude Code 直接写代码生成视频)。
3. **多 Agent 可追溯工作流** (长视频、小时级素材)。

### 2.2 发现清单

| 名称 | URL | 类型 | 活跃度/许可 | 对应板块 | 评级 |
|---|---|---|---|---|---|
| GVCLab/CutClaw | [GitHub](https://github.com/GVCLab/CutClaw) | 音乐同步 agentic 剪辑 | 学术开源 | 卡点/漫剪 | ⭐ P1 (设计参照) |
| UniVA | [arXiv 2511.08521](https://huggingface.co/papers/2511.08521) | 通用视频 Agent | 开源 | Agent 架构 | ⭐ P1 (架构参照) |
| VideoAgent | [arXiv 2606.23327](https://arxiv-org.ezproxy.obspm.fr/html/2606.23327v1) | all-in-one 视频理解编辑 | 学术 | Agent 架构 | P2 |
| Crayotter | [arXiv 2606.07636](https://arxiv-org.ezproxy.obspm.fr/html/2606.07636v1) | 可追溯多 Agent 长视频 | 学术 | 长视频编排 | P2 |
| Memories-ai-labs/vea-open-source | [GitHub](https://github.com/Memories-ai-labs/vea-open-source) | VEA 视频编辑 Agent | 开源 | Agent 架构 | P2 |
| Kemerd/premiere-agent | [GitHub](https://github.com/Kemerd/premiere-agent) | Claude Code → Premiere | 开源, 本地 | PR 桥接参照 | ⭐ P1 |
| Theorvane/openscene | [GitHub](https://github.com/Theorvane/openscene) | local-first 桌面编辑器+Agent | 开源 | 本地管线 | P2 |
| diffusionstudio/editor | [GitHub](https://github.com/diffusionstudio/editor) | 为 coding agent 打造的编辑器 | 开源 | 编辑 UI | P2 |
| ronak-create/FableCut | [GitHub](https://github.com/ronak-create/FableCut) | browser 编辑器 JSON timeline MCP+REST | 开源 | 时间线 DSL | ⭐ P1 |
| haidrrrry/claude-remotion-skill | [GitHub](https://github.com/haidrrrry/claude-remotion-skill) | Remotion motion graphics skill | 开源 | 动效生成 | P2 |
| gregcmartin/auto-vid-editor | [GitHub](https://github.com/gregcmartin/auto-vid-editor) | qwen 模型自动剪辑 | 开源 | 自动剪辑 | P2 |
| idreesaziz/Narrative | [GitHub](https://github.com/idreesaziz/Narrative) | 视频叙事 Agent | 开源 | 叙事 | P2 |
| OpenMontage | [GitHub](https://github.com/calesthio/OpenMontage) | agentic 视频生产系统 | 开源 | 全链路 | ✅已拥有 (12 pipelines/100+ tools/700+ skills) |

### 2.3 对项目的关键判断

1. **CutClaw 的「音乐同步 + 小时级长视频」** 与项目漫剪方向高度重合，其镜头选择/卡点对齐策略值得借鉴，但**不引入代码**。
2. **FableCut 的 JSON timeline + MCP + REST** 是一种轻量时间线 DSL，可作为本项目「时间线可编程化」的设计参照。
3. **premiere-agent** 验证了「Claude Code 直接驱动 Premiere」的可行性，与本项目 PR bridge 同构，可对照其 on-device 预处理思路。

---

## 三、AE 渲染与模板生态

### 3.1 发现清单

| 名称 | URL | 类型 | 活跃度/许可 | 对应板块 | 评级 |
|---|---|---|---|---|---|
| **Adobe Firefly DGR API** | [官方文档](https://developer.adobe.com/audio-video-firefly-services/) | 官方云端 MOGRT 渲染 | 官方 SaaS | 模板渲染 (绕本地 AE) | ⭐ P0 |
| inlife/nexrender | [GitHub](https://github.com/inlife/nexrender) | 数据驱动 AE 渲染 | 开源 | 渲染自动化 | ✅已拥有 (已本地化) |
| jaguars-dev/fork-nexrender | [GitHub](https://github.com/jaguars-dev/fork-nexrender) | nexrender fork | 社区 | 渲染自动化 | P2 (上游不活跃时备用) |
| **forticheprod/py-aep** | [GitHub](https://github.com/forticheprod/py-aep) | .aep Python 编辑 | Fortiche 工作室 | AEP 解析 (对比 aep_binary_parser.py) | ⭐ P1 |
| aep-parser | [GitLab](https://gitlab.com/poufie/aep-parser) / [pypi](https://www.piwheels.org/project/aep-parser/) | .aep 解析 | 社区 | AEP 解析 | P2 |
| MoDeck.io | [aescripts](https://aescripts.com/modeck/) | AE 模板自动化 SaaS | 商业 | 模板市场 | P2 (商业, 观察) |
| Plainly Videos | [plainlyvideos.com](https://www.plainlyvideos.com/blog/after-effects-render-bot) | AE render bot SaaS | 商业 | 云渲染 | P2 (商业, 观察) |
| nexrender-n8n-node | [GitHub](https://github.com/nexrender/nexrender-n8n-node) | nexrender 的 n8n 节点 | 开源 | 工作流编排 | P2 |

### 3.2 对项目的关键判断

1. **DGR API 是最大战略发现**: Adobe 官方把 MOGRT 云端渲染做成 API，可**绕开本地 AE
   崩溃/监听不稳定/内存泄漏**三大痛点。适合「模板型」批量产出场景；本地复杂合成仍需 AE。
   建议评估：把 mogrt_toolkit.jsx 产出的模板上云渲染，本地 AE 只做交互式精修。
2. **py-aep 价值高**: Fortiche（《双城之战》）开源的 .aep 读写库，比自研 aep_binary_parser.py
   覆盖更全、有真实生产背书。建议**对照其解析逻辑补强自研 parser**，而非整体替换。

---

## 四、UI 自动化替代方案 (Windows)

### 4.1 核心结论

项目痛点「UI 自动化依赖截图点击（脆弱）」在 2025-2026 已有成熟替代：**语义级 UI 自动化
(MS UIA / Accessibility 树)**，不依赖像素坐标。多个方案已 MCP 化，可被 agent 直接驱动。

### 4.2 发现清单

| 名称 | URL | 类型 | 活跃度/许可 | 对应板块 | 评级 |
|---|---|---|---|---|---|
| **yinkaisheng/Python-UIAutomation-for-Windows** | [GitHub](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows) | MS UIA Python wrapper | 活跃, MIT | UI 自动化 (替代截图点击) | ⭐ P0 |
| **microsoft/UFO** | [GitHub](https://github.com/microsoft/UFO) | 微软 Windows UI agent | 微软官方 | UI agent | ⭐ P1 |
| **FlaUI-MCP** | [anokye-labs](https://github.com/anokye-labs/FlaUI-MCP) / [shanselman](https://github.com/shanselman/FlaUI-MCP) | FlaUI 的 MCP server | 开源 | UI 自动化 MCP 化 | ⭐ P1 |
| pywinauto | [GitHub](https://github.com/pywinauto/pywinauto) | 经典 Windows GUI 自动化 | 活跃 | UI 自动化 | ✅已有参考 (P0 可换 uia) |
| CursorTouch/Windows-Use | [GitHub](https://github.com/CursorTouch/Windows-Use) | GUI 级 Windows AI agent | 开源 | UI agent | P2 |
| adact / AutoControlGUI / Flue | [adact](https://github.com/84q/adact) | AI 驱动桌面 CLI | 开源 | UI agent | P2 |
| **MustafaJafar/AfterEffects-Prism-Plugin** | [GitHub](https://github.com/MustafaJafar/AfterEffects-Prism-Plugin) | Prism 管线的 AE 插件 | 开源 | 多 DCC 渲染编排 | ⭐ P2 |

### 4.3 对项目的关键判断

1. **UIA 三件套已在项目里** (见 `docs/automation-playbooks/GUI自动化通用速查-UIA三件套.md`)，
   但当前实现仍是「截图+点击」。建议**升级到 yinkaisheng/Python-UIAutomation-for-Windows 的
   语义控件定位**：按 ControlType/Name/AutomationId 定位，而非像素坐标，显著降低脆弱性。
2. **FlaUI-MCP / UFO** 让 UI 自动化本身成为 MCP 工具，可直接挂进项目现有 MCP 编排。
3. **Prism 插件**提示一条路径：若多 DCC 编排 (AE/Blender/C4D/Houdini) 成为刚需，可评估
   Prism Pipeline 框架，而非自研各软件桥接。

---

## 五、视频处理新工具与 GPU 管线

### 5.1 发现清单

| 名称 | URL | 类型 | 活跃度/许可 | 对应板块 | 评级 |
|---|---|---|---|---|---|
| moviepy 2.0 | [Zulko/moviepy](https://github.com/Zulko/moviepy) + [updating_to_v2](https://github.com/OsaAjani/moviepy/blob/76e948bb0e53222a3adcf92b932c3209b0955122/docs/getting_started/updating_to_v2.rst) | Python 视频剪辑 | 活跃 | 视频处理 | ✅已拥有 (注意 v2 API breaking) |
| **BabitMF/bmf** | [GitHub](https://github.com/BabitMF/bmf) | 字节 GPU 视频框架 | 活跃 | GPU 视频处理 | ⭐ P1 |
| **PyNvVideoCodec 2.0** | [NVIDIA](https://developer.nvidia.com/blog/whats-new-in-pynvvideocodec-2-0-for-python-gpu-accelerated-video-processing/) | NVIDIA GPU 编解码 | NVIDIA 官方 | GPU 编解码 | ⭐ P1 |
| torchcodec | [GitLab](https://salsa.debian.org/deeplearning-team/torchcodec) | Meta/PyTorch 视频编解码 | 活跃 | 视频解码 | P2 |
| Remotion (AI coding agents) | [remotion.dev](https://www.remotion.dev/docs/ai/coding-agents) | 编码式视频生成 + Claude Code 插件 | 活跃 | 程序化视频 | ⭐ P1 (动效参照) |
| avtensor / nelux | [pypi](https://pypi.org/project/avtensor/) | 视频张量工具 | 社区 | GPU 处理 | P2 |

### 5.2 对项目的关键判断

1. **moviepy 2.0 有 breaking changes** (numpy 2 兼容 + API 变更，见 `updating_to_v2.rst`)。
   项目已在用 MoviePy，需核对当前版本是否受 v2 迁移影响，避免隐性回归。
2. **BabitMF (字节 bmf)** 是 FFmpeg 之外的最强 GPU 视频框架，支持异构、多语言、AI 推理集成，
   适合「AI 推理 + 转码」一体化管线；但引入成本高，作为 P1 评估。
3. **PyNvVideoCodec 2.0** 若项目有大量 GPU 编解码需求 (RTX 4060)，比 FFmpeg CPU 方案快数倍，
   P1 评估。

---

## 六、B 站 / 中文视频生态工具

### 6.1 发现清单

| 名称 | URL | 类型 | 活跃度/许可 | 对应板块 | 评级 |
|---|---|---|---|---|---|
| Nemo2011/bilibili-api | [GitHub](https://deepwiki.com/Nemo2011/bilibili-api/1.1-installation-and-setup) / [pypi](https://pypi.org/project/bilibili-api-python/) | B 站 API SDK (原 MoyuScript) | 活跃 | 素材采集 | ✅已拥有 (bilibili_creator_analyzer.py 相关) |
| HeavenElegy/bilibili-api | [GitHub](https://github.com/HeavenElegy/bilibili-api) | bilibili-api fork | 社区 | 素材采集 | P2 (上游备用) |
| MediaCrawler (nanmicoder) | [awesome-repositories](https://awesome-repositories.com/repository/nanmicoder-mediacrawler) | 多平台采集 | 开源 | 素材采集 | ✅已拥有 (已本地化) |
| mcp-service/media-crawler-mcp-service | [GitHub](https://github.com/mcp-service/media-crawler-mcp-service) | 采集 MCP (B站/小红书/抖音…) | 社区 | 采集 MCP 化 | ⭐ P1 |
| OpenBiliClaw (whiteguo233) | [GitHub](https://github.com/whiteguo233/OpenBiliClaw) | 本地私有 AI 内容发现 Agent | 1.7k★ | 内容发现 | ⚠️调研中 (勿重复引入) |
| yt-dlp (bilibili extractor) | [yt-dlp issue #14551](https://github.com/yt-dlp/yt-dlp/issues/14551) | 通用下载 | 活跃 | 素材下载 | ✅已拥有 (注意 2025.9 后 bilibili 有回归) |
| you-get | [deepwiki](https://deepwiki.com/soimort/you-get/3.2-bilibili-extractor) | 通用下载 | 维护中 | 素材下载 | P2 (备用) |

### 6.2 对项目的关键判断

1. **yt-dlp 在 2025.9.26 之后 bilibili 下载出现回归** ([issue #14551](https://github.com/yt-dlp/yt-dlp/issues/14551))，
   若项目依赖 yt-dlp 下 B 站素材，需锁定版本或准备 you-get/自研 extractor 兜底。
2. **media-crawler-mcp-service** 把采集能力 MCP 化，可直接并入项目 MCP 编排，替代当前
   独立脚本式 MediaCrawler 调用。
3. **OpenBiliClaw (1.7k★)** 是「先理解用户再主动找内容」的 local-first agent，与 MediaCrawler
   定位不同（后者是关键词采集）；项目已在调研中，**勿重复引入**，仅需与其做差异化定位。

---

## 七、综合结论与建议 (按优先级)

### P0 — 立即评估 (高杠杆、低成本)
1. **DGR API**：把模板型产出上云渲染，绕开本地 AE 不稳定，作为并行渲染通道。
2. **UIA 语义定位**：把 UI 自动化从「截图+点击」升级为 `Python-UIAutomation-for-Windows` 语义控件定位。
3. **锁定 yt-dlp 版本**：规避 bilibili 下载回归。

### P1 — 规划集成
1. **mcp-aftereffects** 架构对照：文件 IPC + 原子 undo，重构 AE bridge 稳定性。
2. **py-aep** 对照：补强自研 aep_binary_parser.py。
3. **FlaUI-MCP / UFO**：UI 自动化 MCP 化，挂入现有编排。
4. **BabitMF / PyNvVideoCodec**：GPU 视频处理加速。
5. **media-crawler-mcp-service**：采集 MCP 化。
6. **CutClaw / FableCut / Remotion**：作为设计参照，不引入代码。

### P2 — 观望
1. Adobe 官方 AE/PR MCP (等官方扩展覆盖)。
2. 社区 AE MCP (同源重复，质量参差)。
3. MoDeck / Plainly (商业 SaaS，仅观察其产品形态)。
4. Prism Pipeline (多 DCC 编排成为刚需时再评估)。

### ⚠️ 项目已拥有、勿重复引入清单
- nexrender (已本地化)
- MoviePy (注意 v2 迁移)
- MediaCrawler (已本地化)
- OpenMontage (已本地化)
- bilibili-api / bilibili_creator_analyzer.py
- OpenBiliClaw (调研中，勿重复)
- pywinauto (已有 UIA 三件套 playbook)

---

## 附: 参考来源汇总

- Adobe 官方 MCP 接入 ChatGPT: https://www.engadget.com/ai/adobe-brings-photoshop-acrobat-and-adobe-express-to-chatgpt-130000389.html
- AE 2025 CEP 移除: https://forums.creativeclouddeveloper.com/t/after-effects-2025-cep-removal-and-uxp-panel-support-issue/11655
- Adobe Firefly DGR API: https://developer.adobe.com/audio-video-firefly-services/
- kumoproductions/mcp-aftereffects: https://github.com/kumoproductions/mcp-aftereffects
- forticheprod/py-aep: https://github.com/forticheprod/py-aep
- yinkaisheng/Python-UIAutomation-for-Windows: https://github.com/yinkaisheng/Python-UIAutomation-for-Windows
- microsoft/UFO: https://github.com/microsoft/UFO
- FlaUI-MCP: https://github.com/anokye-labs/FlaUI-MCP
- BabitMF/bmf: https://github.com/BabitMF/bmf
- PyNvVideoCodec 2.0: https://developer.nvidia.com/blog/whats-new-in-pynvvideocodec-2-0-for-python-gpu-accelerated-video-processing/
- CutClaw: https://github.com/GVCLab/CutClaw
- UniVA: https://huggingface.co/papers/2511.08521
- FableCut: https://github.com/ronak-create/FableCut
- media-crawler-mcp-service: https://github.com/mcp-service/media-crawler-mcp-service
- OpenBiliClaw: https://github.com/whiteguo233/OpenBiliClaw
- yt-dlp bilibili 回归: https://github.com/yt-dlp/yt-dlp/issues/14551
