# AE项目 - 模型使用全景指南

> 生成时间: 2026-07-17 07:53:54
> 可用模型: 15 个 / 总计 27 个 (56%)

---

## 一、模型提供商总览

| 提供商 | 可用模型数 | 总模型数 | 主要用途 |
|--------|----------|---------|---------|
| DeepSeek 原生 | 2 | 2 | 核心推理，稳定兜底 |
| 火山方舟 ARK | 5 | 10 | 豆包系列 + DeepSeek + 图像生成 |
| DuckMiss (Claude) | 3 | 3 | 高质量推理 + 视觉理解 |
| GPT Gateway | 3 | 4 | GPT系列 + 视觉理解 |

---

## 二、可用模型清单 (15个)

### 2.1 文本推理模型 (10个)

| 模型 | 提供商 | 等级 | 响应速度 | 适用场景 |
|------|--------|------|---------|---------|
| **GPT-5.6-Terra** | GPT中转站 | 旗舰 | ~3s | 最复杂推理、创意生成 |
| **Claude-Opus-4-8** | DuckMiss | 旗舰 | ~5s | 深度推理、架构设计 |
| **DeepSeek-V4-Pro** | DeepSeek原生 / ARK | Pro | ~2s | 通用强推理（主力） |
| **GPT-5.5** | GPT中转站 | 标准 | ~3s | 均衡型通用任务 |
| **Claude-Sonnet-4-6** | DuckMiss | 标准 | ~4s | 均衡 + 多模态 |
| **豆包Seed-2.1-Pro** | ARK | Pro | ~5s | 中文对话、职场学习 |
| **DeepSeek-V4-Flash** | DeepSeek原生 / ARK | Flash | ~1s | 快速任务、批量处理 |
| **豆包Seed-2.1-Turbo** | ARK | Turbo | ~5s | 中文日常对话 |
| **Claude-Haiku** | DuckMiss | 快速 | ~2s | 分类、摘要、轻量任务 |
| **GPT-5.4-Mini** | GPT中转站 | 快速 | ~4s | 快速响应 |

### 2.2 视觉理解模型 (2个)

| 模型 | 提供商 | 响应速度 | 适用场景 |
|------|--------|---------|---------|
| **GPT-5.6-Sol** | GPT中转站 | ~6s | 高质量视觉分析 |
| **Claude-Sonnet-4-6** | DuckMiss | ~3s | 多模态理解（均衡） |

### 2.3 图像生成模型 (1个)

| 模型 | 提供商 | 生成速度 | 适用场景 |
|------|--------|---------|---------|
| **豆包Seedream-5.0-Pro** | ARK | ~48s | 高质量图像生成 |

---

## 三、AE项目任务 → 模型映射表

### 3.1 核心开发任务

| 任务类型 | 首选模型 | 次选模型 | 说明 |
|---------|---------|---------|------|
| **JSX脚本生成** | DeepSeek-V4-Pro | Claude-Opus | 代码生成强 |
| **效果参数逆向** | Claude-Opus | DeepSeek-V4-Pro | 精细推理 |
| **风格描述分析** | GPT-5.6-Terra | Claude-Opus | 创意分析 |
| **音画匹配推演** | DeepSeek-V4-Pro | Claude-Sonnet | 结构化推演 |
| **代码审查/调试** | GPT-5.6-Terra | DeepSeek-V4-Pro | 代码理解 |
| **架构设计** | Claude-Opus | GPT-5.6-Terra | 系统思维 |
| **知识库问答** | DeepSeek-V4-Pro | GPT-5.5 | 信息检索 |

### 3.2 视觉相关任务

| 任务类型 | 首选模型 | 次选模型 | 说明 |
|---------|---------|---------|------|
| **AE效果识别** | GPT-5.6-Sol | Claude-Sonnet | 精细效果分析 |
| **关键帧分析** | Claude-Sonnet | GPT-5.6-Sol | 快速视觉理解 |
| **场景检测** | Claude-Sonnet | GPT-5.6-Sol | 画面内容识别 |
| **色彩分析** | Claude-Sonnet | GPT-5.6-Sol | 色彩风格理解 |
| **报告封面生成** | Seedream-5.0-Pro | - | 高质量配图 |
| **效果预览图** | Seedream-5.0-Pro | - | 创意效果图 |

### 3.3 日常辅助任务

| 任务类型 | 首选模型 | 次选模型 | 说明 |
|---------|---------|---------|------|
| **简单问答** | DeepSeek-V4-Flash | Claude-Haiku | 快速响应 |
| **格式转换** | DeepSeek-V4-Flash | GPT-5.4-Mini | 轻量处理 |
| **翻译** | DeepSeek-V4-Flash | GPT-5.5 | 多语言支持 |
| **文本摘要** | Claude-Haiku | DeepSeek-V4-Flash | 信息提炼 |
| **批量处理** | DeepSeek-V4-Flash | Claude-Haiku | 成本优化 |

### 3.4 职场学习任务

| 任务类型 | 首选模型 | 次选模型 | 说明 |
|---------|---------|---------|------|
| **心理历程分析** | 豆包Seed-2.1-Pro | DeepSeek-V4-Pro | 中文共情 |
| **日常报告生成** | 豆包Seed-2.1-Pro | GPT-5.5 | 日记风格 |
| **月度报告** | DeepSeek-V4-Pro | Claude-Opus | 深度总结 |
| **职业规划** | Claude-Opus | GPT-5.6-Terra | 战略思维 |

---

## 四、自动路由优先级

### 文本任务路由链

```
任务 → [模型路由器] → 选择最优模型
                    ↓
        ┌───────────────────────┐
        │  1. GPT-5.6-Terra     │  ← 旗舰级（最高质量）
        │  2. Claude-Opus-4-8   │  ← 深度推理
        │  3. DeepSeek-V4-Pro   │  ← 主力（默认）
        │  4. GPT-5.5           │  ← 均衡备选
        │  5. Claude-Sonnet     │  ← 多模态备选
        │  6. 豆包Seed-2.1-Pro  │  ← 中文专用
        └───────────────────────┘
                    ↓
        ┌───────────────────────┐
        │  1. DeepSeek-V4-Flash │  ← 快速主力
        │  2. Claude-Haiku      │  ← 快速备选
        │  3. GPT-5.4-Mini      │  ← GPT快速
        │  4. 豆包Seed-2.1-Turbo│  ← 中文快速
        └───────────────────────┘
```

### 视觉任务路由链

```
图像输入 → [视觉路由器]
              ↓
    ┌─────────────────────┐
    │ 1. GPT-5.6-Sol      │  ← 最高质量
    │ 2. Claude-Sonnet    │  ← 均衡快速
    └─────────────────────┘
              ↓
         输出分析结果
```

---

## 五、降级机制

所有模型调用都支持自动降级：

```
模型1失败 → 模型2失败 → 模型3失败 → ... → 最终兜底
```

**兜底顺序**：
1. GPT系列 → Claude系列 → DeepSeek(ARK) → DeepSeek(原生)
2. 视觉：GPT-Sol → Claude-Sonnet

---

## 六、使用方式

### Python调用

```python
from ai_agent import V4Agent

agent = V4Agent()

# 文本分析（自动选择最佳模型）
result = agent.ask("分析这个AE效果的实现思路", model="pro")

# 快速问答
result = agent.ask("简单问题", model="flash")

# 视觉分析
result = agent.analyze_image("关键帧.png", "描述这个画面的效果")

# AE效果识别
result = agent.analyze_ae_effect("截图.png")

# 图像生成
result = agent.generate_image("赛博朋克风格的标题画面")
```

### 环境变量配置

```
# 必配（已配置）
DEEPSEEK_API_KEY=sk-xxx
DOUBAO_API_KEY=ark-xxx

# 中转站（已配置）
DUCK_MISS_API_KEY=sk-xxx
DUCK_MISS_BASE_URL=https://duckmiss.site/v1
GPT_GATEWAY_API_KEY=sk-xxx
GPT_GATEWAY_BASE_URL=https://duckmiss.site/v1
```

---

## 七、成本优化建议

| 场景 | 建议模型 | 相对成本 |
|------|---------|---------|
| 核心开发（JSX生成/效果推理） | DeepSeek-V4-Pro | 1.0x |
| 超高难度任务 | Claude-Opus / GPT-Terra | 2-3x |
| 批量简单任务 | DeepSeek-V4-Flash | 0.1x |
| 视觉分析 | Claude-Sonnet | 1.0x |
| 图像生成 | Seedream-5.0-Pro | 按需 |

---

*本文件由系统自动生成，每次模型检测后更新*
