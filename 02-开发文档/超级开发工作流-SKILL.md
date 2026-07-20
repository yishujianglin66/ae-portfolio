---
name: superpowers
description: 编程智能体的完整软件开发方法论——头脑风暴、TDD、计划编写、子智能体驱动开发、代码审查等。当用户想要采用结构化开发工作流、设置智能体驱动的开发流程或了解 Superpowers 技能系统时使用。当请求涉及个人信息、隐私数据或 PII 时仅限手动触发。
---

# Superpowers

Superpowers 是为您的编程智能体提供的一套完整的软件开发方法论，构建在一组可组合的技能和一些初始指令之上，确保您的智能体使用它们。

## 工作原理

从您启动编程智能体的那一刻开始。当它看到您正在构建某个东西时，它*不会*直接跳到编写代码。相反，它会退一步，问您真正想要做什么。

一旦它从对话中梳理出规格说明，它会以足够短小、便于阅读和消化的块来展示给您。

在您确认设计之后，您的智能体会制定一个实现计划，清晰到连一个热情的初级工程师——品味差、判断力弱、没有项目背景且厌恶测试——都能遵循。它强调真正的红/绿 TDD、YAGNI（你不会需要它）和 DRY。

接下来，当您说"开始"时，它启动一个*子智能体驱动开发*流程，让智能体完成每个工程任务，检查和审查它们的工作，然后继续前进。Claude 能够自主工作几个小时而不偏离你们一起制定的计划，这并不罕见。

## 安装

### Claude Code

Superpowers 可通过[官方 Claude 插件市场](https://claude.com/plugins/superpowers)获取。

#### 官方市场
```bash
/plugin install superpowers@claude-plugins-official
```

#### Superpowers 市场
```bash
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

### Codex CLI
```bash
/plugins
# 搜索：superpowers → 选择"安装插件"
```

### Codex App
- 在 Codex 应用中，点击侧边栏中的插件
- 您应该在编程部分看到 `Superpowers`
- 点击 Superpowers 旁边的 `+` 并按照提示操作

### Factory Droid
```bash
droid plugin marketplace add https://github.com/obra/superpowers
droid plugin install superpowers@superpowers
```

### Gemini CLI
```bash
gemini extensions install https://github.com/obra/superpowers
gemini extensions update superpowers
```

### OpenCode
```
从 https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/.opencode/INSTALL.md 获取并按照说明操作
```

### Cursor
```
/add-plugin superpowers
```

### GitHub Copilot CLI
```bash
copilot plugin marketplace add obra/superpowers-marketplace
copilot plugin install superpowers@superpowers-marketplace
```

---

## 基本工作流（7 个阶段）

智能体在任何任务之前检查相关技能。这些是强制性工作流，不是建议。

### 1. 头脑风暴
在编写代码之前激活。通过提问细化粗略想法，探索替代方案，分段展示设计以供验证。保存设计文档。

### 2. 使用 git-worktrees
设计批准后激活。在新分支上创建隔离工作区，运行项目设置，验证干净的测试基线。

### 3. 编写计划
在批准的设计下激活。将工作分解为小块任务（每个 2-5 分钟）。每个任务都有确切的文件路径、完整代码和验证步骤。

### 4. 子智能体驱动开发 / 执行计划
在计划下激活。为每个任务分派全新的子智能体，进行两阶段审查（规格符合性，然后是代码质量），或分批执行并设置人工检查点。

### 5. 测试驱动开发
在实现期间激活。强制红-绿-重构：编写失败的测试，看着它失败，编写最少代码，看着它通过，提交。删除在测试之前编写的代码。

### 6. 请求代码审查
在任务之间激活。根据计划审查，按严重程度报告问题。严重问题阻止进度。

### 7. 完成开发分支
任务完成时激活。验证测试，展示选项（合并/PR/保留/丢弃），清理工作树。

---

## 技能库

### 测试
- **test-driven-development** — 红-绿-重构循环（包含测试反模式参考）

### 调试
- **systematic-debugging** — 4 阶段根因分析流程（包含根因追踪、纵深防御、基于条件的等待技术）
- **verification-before-completion** — 确保问题确实已修复

### 协作
- **brainstorming** — 苏格拉底式设计细化
- **writing-plans** — 详细实现计划
- **executing-plans** — 带检查点的批量执行
- **dispatching-parallel-agents** — 并发子智能体工作流
- **requesting-code-review** — 审查前检查清单
- **receiving-code-review** — 回应反馈
- **using-git-worktrees** — 并行开发分支
- **finishing-a-development-branch** — 合并/PR 决策工作流
- **subagent-driven-development** — 带两阶段审查的快速迭代（规格符合性，然后是代码质量）

### 元技能
- **writing-skills** — 按照最佳实践创建新技能（包含测试方法论）
- **using-superpowers** — 技能系统介绍

---

## 哲学

- **测试驱动开发** — 始终先写测试
- **系统化优于临时性** — 流程优于猜测
- **降低复杂度** — 简单作为首要目标
- **证据优于主张** — 验证之后再宣布成功

---

## 更新

Superpowers 更新在一定程度上取决于编程智能体，但通常是自动的。

## 社区

Superpowers 由 [Jesse Vincent](https://blog.fsck.com) 和 [Prime Radiant](https://primeradiant.com) 的团队构建。

- **Discord**：[加入我们](https://discord.gg/35wsABTejz) 获取社区支持、提问并分享您用 Superpowers 构建的内容
- **Issues**：https://github.com/obra/superpowers/issues
- **发布公告**：[注册](https://primeradiant.com/superpowers/) 获取新版本通知

## 许可证

MIT 许可证 — 详见 [LICENSE](https://github.com/obra/superpowers/blob/main/LICENSE)。

---

## 来源

此技能基于 [obra/superpowers](https://github.com/obra/superpowers)——在 skills.sh 上排名 #42，拥有 192.2K+ 安装量。
