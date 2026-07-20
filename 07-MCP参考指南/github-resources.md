# GitHub 开源资源与工具生态

## 🏆 核心 MCP Server 项目

### [TheLlamainator/after-effects-mcp](https://github.com/TheLlamainator/after-effects-mcp) ⭐ 最成熟
MCP Server for Adobe After Effects，通过 ExtendScript 桥接面板实现 AI 远程控制。

**核心能力:**
- 合成/图层创建与管理
- 关键帧+表达式+效果控制
- 预设搜索与应用 (.ffx)
- 音频分析 (WAV波形→标记)
- 标记/标签系统

**技术栈:** Node.js 18+ / TypeScript / ExtendScript

---

### [JUNKDOGE-JOE/after-effects-mcp](https://github.com/JUNKDOGE-JOE/after-effects-mcp) ⭐ 22
Python MCP server + CEP 面板架构，30 个 `ae.*` 动词工具。

**亮点功能:**
- 技能系统 (CRUD + 持久化)
- 检查点/回滚 (checkpoint/revert)
- 表达式验证 (ae.validateExpressions)
- 预览帧截图 (非渲染快速预览)
- Codex/Cursor/Claude Code 全兼容

**架构:** `MCP Client → Python MCP → HTTP 127.0.0.1:11488 → CEP Panel → AE ExtendScript`

---

## 📜 脚本集合 (Script Collections)

### [kyletmartinez/After-Effects-Scripts](https://github.com/kyletmartinez/After-Effects-Scripts) ⭐ 168
组织完善的脚本库，按类别分类：
- Compositions / Expressions / Keyframes / Layers
- Lottie / Markers / Project / Properties
- Selection / Utilities

### [volition74/after-effects-scripts](https://github.com/volition74/after-effects-scripts) ⭐ 167
50+ 工作流脚本，覆盖日常工作需求。

### [aturtur/after-effects-scripts](https://github.com/aturtur/after-effects-scripts) ⭐ 119
流行的日常动效工具集——精选实用脚本。

### [creotip/ae-scripts](https://github.com/creotip/ae-scripts) ⭐ 70
JS 自动化工具 + ScriptUI 项目模板。

### [billybuehl792/Expand-After-Effects-Presets](https://github.com/billybuehl792/Expand-After-Effects-Presets) ⭐ 68
预设库扩展：Assets / Paths / Styles / Text Animations / Transitions。

---

## 🔢 表达式库 (Expression Libraries)

| 项目 | ⭐ | 说明 |
|------|-----|------|
| [timothyshan/ae-expression-lib](https://github.com/timothyshan/ae-expression-lib) | 48 | 实用函数加速表达式编写 |
| [anbdesign/After_Effects_Expressions](https://github.com/anbdesign/After_Effects_Expressions) | 38 | 常用和有趣的AE表达式 |
| [CameronFoxly/AfterEffectsExpressionLibrary](https://github.com/CameronFoxly/AfterEffectsExpressionLibrary) | - | 精选可复用表达式集合 |
| [motiondeveloper/expressionist](https://github.com/motiondeveloper/expressionist) | 21 | Web端+AE内表达式编辑器 |
| [motiondeveloper/ae-keyframe](https://github.com/motiondeveloper/ae-keyframe) | 38 | 通过表达式实现关键帧动画+缓动 |

---

## 🛠 专业框架与工具

| 项目 | 说明 |
|------|------|
| [RxLaboratory/DuAEF](https://github.com/RxLaboratory/DuAEF) ⭐29 | AE脚本端到端开发框架 |
| [RxLaboratory/DuIK](https://github.com/RxLaboratory/DuIK) | 免费角色骨骼绑定+IK工具 |
| [azaynzxz/after-effects-expression-panel](https://github.com/azaynzxz/after-effects-expression-panel) | 综合脚本面板 (表达式+动画+工具) |
| [baffects/Baffects.js](https://github.com/baffects/Baffects.js) | Processing语言适配AE表达式 |

---

## 🔌 推荐免费插件/脚本下载

### 角色动画
| 工具 | 类型 | 链接 |
|------|------|------|
| **DuIK** | 免费 | [rxlaboratory.org/duik](https://rxlaboratory.org/duik/) |
| **Rubberhose 3** | 付费 | [battleaxe.co/rubberhose](https://www.battleaxe.co/rubberhose) |
| **Limber** | 付费 | aescripts.com |

### 合成/抠像
| 工具 | 类型 | 链接 |
|------|------|------|
| **Lockdown** | 付费 | aescripts.com (变形面追踪) |
| **Silhouette** | 付费 | Boris FX (专业Roto/抠像) |
| **Primatte Keyer** | 付费 | Red Giant |

### 粒子/特效
| 工具 | 类型 | 链接 |
|------|------|------|
| **Trapcode Suite** | 付费 | Maxon/Red Giant (Particular, Form, Mir, Shine, Tao) |
| **Saber** | 免费 | [VideoCopilot.net](https://www.videocopilot.net/) (能量光束) |
| **FX Console** | 免费 | VideoCopilot (快速搜索应用效果) |

### 3D
| 工具 | 类型 | 链接 |
|------|------|------|
| **Element 3D** | 付费 | VideoCopilot |
| **Substance 3D Assets** | 订阅 | Adobe (20000+ 模型/材质/HDR) |

---

## 📚 学习资源

### 官方文档
- [Adobe After Effects Help](https://helpx.adobe.com/after-effects/user-guide.html)
- [Adobe After Effects 2024 新特性](https://helpx.adobe.com/after-effects/using/whats-new.html)
- [AE Expression Reference](https://helpx.adobe.com/after-effects/using/expression-language-reference.html)

### 社区
- [r/AfterEffects (Reddit)](https://reddit.com/r/AfterEffects)
- [Creative COW AE Forum](https://creativecow.net/)
- [aescripts.com](https://aescripts.com/) (最大脚本市场)
- [lesterbanks.com](https://lesterbanks.com/) (教程+新闻)
- [School of Motion](https://www.schoolofmotion.com/) (专业培训)

### 经典书籍
- *Adobe After Effects Classroom in a Book 2024* — 官方培训教材
- *Compositing Visual Effects in After Effects* — Lee Lanier
- *Creative Motion Mastery with Adobe After Effects* — 综合进阶
