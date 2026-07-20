---
title: AE 自动化引擎架构设计
date: 2026-07-05
tags:
  - 架构
  - 自动化
  - 引擎
  - 端到端
  - 知识编译
---
# AE 自动化引擎架构设计

> [!abstract] 文档摘要
> 本文档设计了AE自动化引擎的完整五层架构，实现"自然语言→AE操作"的端到端能力。从L1自然语言理解层到L5执行层，每层的输入/输出/技术选型/错误处理均有详尽设计。同时给出了知识库与引擎的完整映射表、部署方案和分阶段实施路线图。本文档是整个AE知识库从"知识"走向"自动化"的顶层架构蓝图。

> [!tip] 使用指南
> - 架构师：从第一章系统总体架构开始，理解五层设计全貌
> - 层级开发者：直接跳转到对应层级的章节，关注技术选型和接口定义
> - 项目经理：重点阅读第九章部署方案和第十章路线图
> - 知识库维护者：第八章的知识库映射表是核心参考

---

## 第一章 系统总体架构

### 1.1 五层架构总览

AE自动化引擎采用五层分层架构，每一层职责明确，层与层之间通过定义良好的接口通信：

```
┌─────────────────────────────────────────────────────────────────────┐
│  L1: 自然语言理解层（NLU - Natural Language Understanding）          │
│  ─────────────────────────────────────────────────────────────────── │
│  输入：用户自然语言描述                                                │
│  输出：结构化意图 + 效果描述                                           │
│  技术选型：TRAE/Claude 对话 + 意图分类模型                              │
│  错误处理：意图模糊→追问确认 / 无法识别→回退到手动模式                    │
├─────────────────────────────────────────────────────────────────────┤
│  L2: 知识推理层（Inference）                                          │
│  ─────────────────────────────────────────────────────────────────── │
│  输入：结构化意图 + 效果描述                                           │
│  输出：原子参数JSON（含置信度）                                         │
│  技术选型：决策树引擎 + 映射库查询 + 案例模板匹配                         │
│  错误处理：低置信度→人工确认 / 无匹配→建议替代方案                        │
├─────────────────────────────────────────────────────────────────────┤
│  L3: 编译层（Compiler）                                               │
│  ─────────────────────────────────────────────────────────────────── │
│  输入：原子参数JSON                                                   │
│  输出：可执行ExtendScript代码                                          │
│  技术选型：模板引擎 + 代码生成器 + 语法验证器                            │
│  错误处理：编译失败→回退到简化版 / 语法错误→自动修复                      │
├─────────────────────────────────────────────────────────────────────┤
│  L4: 传输层（Transport）                                              │
│  ─────────────────────────────────────────────────────────────────── │
│  输入：ExtendScript代码                                               │
│  输出：执行结果（成功/失败+数据）                                       │
│  技术选型：MCP协议 + Command File轮询 / CEP直连 / WebSocket（未来）      │
│  错误处理：超时→重试 / 离线→等待 / 执行失败→错误码解析                    │
├─────────────────────────────────────────────────────────────────────┤
│  L5: 执行层（Execution）                                              │
│  ─────────────────────────────────────────────────────────────────── │
│  输入：ExtendScript代码（由L4传输）                                    │
│  输出：AE DOM操作结果 + 渲染预览                                       │
│  技术选型：ExtendScript运行时 + AE DOM API + 效果matchName              │
│  错误处理：DOM异常→回滚Undo / 效果未安装→提示 / 渲染失败→降级             │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 数据流总览

```
用户："给文字加一个暖色发光"
  │
  ▼ L1
意图：{ operation: "add_effect", effectType: "glow", style: "warm" }
  │
  ▼ L2
原子参数：{ effectMatchName: "ADBE Glo2", settings: { "Color A": [1,0.78,0.39,1], ... }, confidence: 0.85 }
  │
  ▼ L3
ExtendScript：layer.Effects.addProperty("ADBE Glo2"); effect.property("Color A").setValue([...])
  │
  ▼ L4
MCP命令：{ command: "add-effect-with-keyframes", params: {...} }
  │
  ▼ L5
AE执行：效果添加成功，Glow效果出现在图层面板上
```

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| 层间解耦 | 每层只依赖相邻层的接口，不跨层调用 |
| 向后兼容 | 新增能力不破坏已有功能，版本号语义化 |
| 失败可回滚 | 每层操作在beginUndoGroup内执行，可一键撤销 |
| 人机协同 | 关键步骤可插入人工确认节点，不完全自动 |
| 知识驱动 | 所有决策基于知识库文档，不做硬编码假设 |
| 增量构建 | 每层可独立开发和测试，逐步集成 |

---

## 第二章 L1 自然语言理解层

### 2.1 意图识别

L1层的核心任务是将用户的自然语言输入解析为结构化的操作意图。定义三大操作意图类别：

#### 2.1.1 操作意图分类

| 意图类别 | ID | 典型表达 | L2映射 |
|---------|-----|---------|--------|
| 添加效果 | INTENT_ADD_EFFECT | "加个模糊"、"添加发光"、"来个粒子" | 调用映射库查询效果参数 |
| 创建动画 | INTENT_CREATE_ANIM | "做弹入动画"、"加个缩放动画"、"文字入场" | 调用决策树+关键帧模板 |
| 调整参数 | INTENT_ADJUST_PARAM | "模糊调大一点"、"发光再强些"、"颜色偏暖" | 调用get-effect-properties+参数修改 |
| 创建图层 | INTENT_CREATE_LAYER | "建个合成"、"加个调整层"、"创建空对象" | 直接映射到MCP工具 |
| 风格化组合 | INTENT_STYLE_COMBO | "赛博朋克风格"、"电影级调色"、"梦幻柔焦" | 调用效果组合配方 |
| 逆向分析 | INTENT_REVERSE_ANALYZE | "这个效果怎么做的"、"分析一下这个视频" | 调用逆向分析管线 |

#### 2.1.2 意图识别实现

```typescript
interface Intent {
  type: IntentType;
  confidence: number;
  slots: Record<string, any>;
  rawInput: string;
}

enum IntentType {
  ADD_EFFECT = "INTENT_ADD_EFFECT",
  CREATE_ANIM = "INTENT_CREATE_ANIM",
  ADJUST_PARAM = "INTENT_ADJUST_PARAM",
  CREATE_LAYER = "INTENT_CREATE_LAYER",
  STYLE_COMBO = "INTENT_STYLE_COMBO",
  REVERSE_ANALYZE = "INTENT_REVERSE_ANALYZE",
  UNKNOWN = "INTENT_UNKNOWN"
}

class NLUParser {
  private intentPatterns: Map<IntentType, RegExp[]>;

  constructor() {
    this.intentPatterns = new Map([
      [IntentType.ADD_EFFECT, [
        /加[个一]?(\S+?)(?:效果|特效)?/,
        /添加(\S+?)(?:效果|特效)?/,
        /来[个一]?(\S+)/,
        /apply\s+(\w+)\s+effect/i,
      ]],
      [IntentType.CREATE_ANIM, [
        /做[个一]?(\S+?)(?:动画|动效)/,
        /加[个一]?(\S+?)(?:入场|出场|过渡)/,
        /(\S+?)弹入|弹[出落]/,
        /创建(?:弹性|缓动|弹性)(\S+)/,
      ]],
      [IntentType.ADJUST_PARAM, [
        /(\S+?)(?:调[大高小低]|加[强大弱]|[设改]变)/,
        /(\S+?)再(\S+?)[一点些]/,
        /(\S+?)偏(\S+)/,
      ]],
      [IntentType.STYLE_COMBO, [
        /(\S+?)风格/,
        /(\S+?)效果组合/,
        /做[个一]?(\S+?)(?:感|风|调)/,
      ]],
    ]);
  }

  parse(input: string): Intent {
    // 1. 模式匹配
    for (const [intentType, patterns] of this.intentPatterns) {
      for (const pattern of patterns) {
        const match = input.match(pattern);
        if (match) {
          return {
            type: intentType,
            confidence: 0.8,
            slots: { effectOrStyle: match[1] },
            rawInput: input,
          };
        }
      }
    }

    // 2. 回退到LLM理解
    return {
      type: IntentType.UNKNOWN,
      confidence: 0.3,
      slots: {},
      rawInput: input,
    };
  }
}
```

### 2.2 效果描述解析

从自然语言到《解析词汇表》的映射是L1层的关键环节。每个自然语言描述需要映射到解析词汇表中的标准术语：

```typescript
// 效果描述解析器
interface EffectDescription {
  effectKeywords: string[];     // 效果关键词
  styleKeywords: string[];      // 风格关键词
  directionKeywords: string[];  // 方向关键词
  intensityKeywords: string[];  // 强度关键词
  colorKeywords: string[];      // 颜色关键词
  temporalKeywords: string[];   // 时间关键词
}

class EffectDescriptionParser {
  // 自然语言→解析词汇映射
  private vocabularyMap: Record<string, string[]> = {
    // 模糊类
    "模糊": ["VT-001", "均匀模糊扩散"],
    "柔化": ["VT-001", "均匀模糊扩散"],
    "虚化": ["VT-001", "均匀模糊扩散"],
    "运动模糊": ["VT-002", "方向性拖尾"],
    "径向模糊": ["VT-003", "放射状模糊"],
    "景深": ["VT-004", "镜头光斑模糊"],

    // 发光类
    "发光": ["VT-010", "边缘光晕"],
    "辉光": ["VT-010", "边缘光晕"],
    "暖色发光": ["VT-015", "暖色边缘光晕"],
    "霓虹": ["VT-016", "冷色边缘光晕"],
    "体积光": ["VT-017", "射线状光晕"],

    // 粒子类
    "粒子": ["VT-020", "离散点状元素"],
    "飘散": ["VT-021", "向上扩散粒子"],
    "火花": ["VT-022", "高速衰减粒子"],
    "烟雾": ["VT-023", "缓慢上升云状体"],

    // 色彩类
    "暖色": ["VT-030", "暖色调偏移"],
    "冷色": ["VT-031", "冷色调偏移"],
    "赛博朋克": ["VT-035", "青品对比色调"],
    "电影感": ["VT-036", "橙青电影色调"],

    // 动画类
    "弹入": ["KF-010", "弹性缓入"],
    "淡入": ["KF-011", "线性渐入"],
    "滑入": ["KF-012", "位移渐入"],
    "缩放": ["KF-013", "缩放渐变"],
    "旋转": ["KF-014", "旋转变换"],
  };

  parse(input: string): EffectDescription {
    const result: EffectDescription = {
      effectKeywords: [],
      styleKeywords: [],
      directionKeywords: [],
      intensityKeywords: [],
      colorKeywords: [],
      temporalKeywords: [],
    };

    for (const [keyword, vocabRef] of Object.entries(this.vocabularyMap)) {
      if (input.includes(keyword)) {
        const [vocabId, vocabName] = vocabRef;
        if (vocabId.startsWith("VT-0")) {
          if (parseInt(vocabId.slice(3)) < 20) result.effectKeywords.push(vocabName);
          else if (parseInt(vocabId.slice(3)) < 30) result.colorKeywords.push(vocabName);
          else result.styleKeywords.push(vocabName);
        } else if (vocabId.startsWith("KF-")) {
          result.effectKeywords.push(vocabName);
        }
      }
    }

    return result;
  }
}
```

### 2.3 与TRAE/Claude的对话接口

L1层通过MCP协议与TRAE IDE中的Claude对话模型交互：

```typescript
// TRAE ↔ 引擎的对话接口
interface EngineDialogueInterface {
  // 用户输入→引擎处理
  processUserInput(input: string, context: ProjectContext): Promise<EngineResponse>;

  // 引擎追问用户
  askUserForClarification(question: string, options: string[]): Promise<string>;

  // 执行结果反馈给用户
  reportExecutionResult(result: ExecutionResult): void;
}

interface ProjectContext {
  activeCompName: string;
  selectedLayers: LayerInfo[];
  currentEffects: EffectInfo[];
  compResolution: [number, number];
  compFrameRate: number;
  compDuration: number;
}

interface EngineResponse {
  understood: boolean;
  intent: Intent;
  effectDescription: EffectDescription;
  needsClarification: boolean;
  clarificationQuestion?: string;
}
```

**对话交互流程**：

```
用户: "给这个文字加一个暖色发光"
  │
  ├── L1解析：
  │   意图: INTENT_ADD_EFFECT
  │   效果: "发光" → VT-010 "边缘光晕"
  │   风格: "暖色" → VT-015 "暖色边缘光晕"
  │   目标: "这个文字" → 当前选中文字图层
  │
  ├── 置信度评估：0.85（高于阈值0.7，直接执行）
  │
  ▼ 传入L2
```

**需要追问的场景**：

```
用户: "加个模糊"
  │
  ├── L1解析：
  │   意图: INTENT_ADD_EFFECT
  │   效果: "模糊" → VT-001 "均匀模糊扩散"（但不确定是高斯还是径向）
  │
  ├── 置信度评估：0.55（低于阈值0.7，需要追问）
  │
  ├── 追问: "请问是哪种模糊？1)高斯模糊 2)径向模糊 3)方向模糊"
  │
  ├── 用户: "高斯"
  │
  ▼ 重新解析，置信度提升到0.9，传入L2
```

---

## 第三章 L2 知识推理层

### 3.1 推理引擎总览

L2层是引擎的"大脑"，调用知识库文档完成从意图到原子参数的推理：

```
┌────────────────────────────────────────────────────────────────┐
│                    L2 知识推理层                                │
│                                                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ 解析词汇表与      │  │ 参数-效果原子级   │  │ 视频案例     │ │
│  │ 推理决策树        │  │ 映射库            │  │ 解析库       │ │
│  │                  │  │                  │  │              │ │
│  │ → 效果识别       │  │ → 参数还原        │  │ → 参数模板   │ │
│  │ → 推理路径       │  │ → 取值范围        │  │ → 实战经验   │ │
│  │ → 置信度评估     │  │ → 视觉签名匹配    │  │ → 关键帧模板 │ │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘ │
│           │                     │                    │         │
│           └──────────┬──────────┘────────────────────┘         │
│                      ▼                                         │
│           ┌──────────────────────┐                             │
│           │ 推理合成器            │                             │
│           │ → 综合三源推理结果    │                             │
│           │ → 置信度加权         │                             │
│           │ → 冲突消解           │                             │
│           │ → 输出原子参数JSON    │                             │
│           └──────────────────────┘                             │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 调用《解析词汇表与推理决策树》

推理决策树提供从视觉特征到参数的系统化推理路径：

```typescript
// 推理决策树调用器
class InferenceEngine {
  /**
   * 沿决策树推理：视觉特征 → 效果识别 → 参数值
   */
  reasonAlongDecisionTree(intent: Intent, description: EffectDescription): InferenceResult {
    const result: InferenceResult = {
      effects: [],
      parameters: [],
      confidence: 0,
      reasoningPath: [],
    };

    // 步骤1：视觉特征匹配（VT层）
    for (const keyword of description.effectKeywords) {
      const visualTerm = this.findVisualTerm(keyword);
      if (visualTerm) {
        result.reasoningPath.push(`VT: ${keyword} → ${visualTerm.term_name}`);

        // 步骤2：效果识别（EI层）
        const effectIdents = visualTerm.inference_chain;
        for (const chain of effectIdents) {
          result.effects.push({
            matchName: this.resolveMatchName(chain.effect),
            name: chain.effect,
            confidence: chain.confidence,
          });

          // 步骤3：参数值推断（PV层）
          result.parameters.push({
            effectName: chain.effect,
            parameterName: chain.parameter,
            valueRange: chain.value_range,
            recommendedValue: this.pickValueInRange(chain.value_range, "medium"),
            confidence: chain.confidence * 0.9,
          });
        }
      }
    }

    // 步骤4：关键帧推断（KF层 + EC层）
    if (intent.type === IntentType.CREATE_ANIM) {
      result.parameters.push(...this.inferKeyframes(description));
    }

    // 综合置信度
    result.confidence = this.calculateConfidence(result);

    return result;
  }

  private pickValueInRange(range: [number, number], level: "low" | "medium" | "high"): number {
    const [min, max] = range;
    switch (level) {
      case "low": return min + (max - min) * 0.25;
      case "medium": return min + (max - min) * 0.5;
      case "high": return min + (max - min) * 0.75;
    }
  }
}
```

### 3.3 调用《参数-效果原子级映射库》

映射库提供精确的参数→效果双向查询：

```typescript
class ParameterEffectMapper {
  /**
   * 正向查询：已知效果名 → 查所有参数及取值范围
   */
  forwardQuery(effectMatchName: string): ParameterMapping[] {
    // 示例：查询 Gaussian Blur 的所有参数
    // 返回：
    // [
    //   { name: "Blurriness", range: [0, 100], visual: "均匀柔化", keyframable: true },
    //   { name: "Repeat Pixels", range: [false, true], visual: "边缘重复", keyframable: false },
    // ]
    return this.mappingStore.get(effectMatchName) || [];
  }

  /**
   * 逆向查询：已知视觉特征 → 查对应参数和取值范围
   */
  reverseQuery(visualFeature: string): ParameterSuggestion[] {
    // 示例：查询 "暖色边缘光晕" →
    // [
    //   { effect: "ADBE Glo2", param: "Color A", value: [1, 0.78, 0.39, 1], range: "暖色系" },
    //   { effect: "ADBE Glo2", param: "Color B", value: [1, 0.59, 0.20, 1], range: "暖色系" },
    //   { effect: "ADBE Glo2", param: "Glow Intensity", value: 1.5, range: [0.5, 3.0] },
    // ]
    return this.reverseIndex.get(visualFeature) || [];
  }
}
```

### 3.4 调用《视频案例解析库》获取参数模板

案例库提供经过验证的参数模板，比纯推理更可靠：

```typescript
class CaseTemplateProvider {
  /**
   * 根据效果类型查找匹配的案例模板
   */
  findTemplate(effectType: string, style?: string): CaseTemplate | null {
    // 示例：查找 "金色魔法粒子" 模板
    // → CASE-1-3 "金色魔法飘浮" 模板
    // → 包含完整的 Particular 参数表、关键帧表、复现工程结构

    const candidates = this.caseStore.filter(c =>
      c.effectType === effectType &&
      (!style || c.style === style)
    );

    if (candidates.length === 0) return null;

    // 返回最匹配的案例
    return candidates.reduce((best, curr) =>
      curr.matchScore > best.matchScore ? curr : best
    );
  }

  /**
   * 将案例参数表转换为原子参数JSON
   */
  templateToAtomParams(template: CaseTemplate): AtomicParameterJSON {
    return {
      operation: this.inferOperation(template),
      target: { compName: "auto-detect" },
      effect: {
        matchName: template.effectMatchName,
        name: template.effectName,
      },
      properties: template.parameterTable.map(p => ({
        name: p.parameter,
        value: p.recommendedValue,
        animated: p.hasKeyframes,
      })),
      keyframes: template.keyframeTable.map(kf => ({
        propertyName: kf.property,
        time: kf.timeSeconds,
        value: kf.value,
        easingType: kf.easingType,
      })),
      source: `CASE-${template.caseId}`,
      confidence: 0.92, // 案例库的参数经过验证，置信度高
    };
  }
}
```

### 3.5 置信度评估与人工确认

推理结果的置信度决定是否需要人工确认：

| 置信度范围 | 处理策略 |
|-----------|---------|
| 0.9-1.0 | 直接执行，无需确认 |
| 0.7-0.9 | 提示用户确认参数，一键执行 |
| 0.5-0.7 | 展示推理过程，让用户选择/调整 |
| 0.3-0.5 | 提供多个候选方案，让用户选择 |
| 0-0.3 | 无法推理，回退到手动模式 |

```typescript
class ConfidenceEvaluator {
  evaluate(result: InferenceResult): number {
    let confidence = 0;

    // 因子1：词汇匹配精度（权重0.3）
    const vocabPrecision = result.reasoningPath.length > 0 ? 0.8 : 0.3;
    confidence += vocabPrecision * 0.3;

    // 因子2：参数覆盖度（权重0.3）
    const requiredParams = this.getRequiredParams(result.effects[0]?.matchName);
    const coveredParams = result.parameters.filter(p => requiredParams.includes(p.parameterName));
    const paramCoverage = coveredParams.length / Math.max(requiredParams.length, 1);
    confidence += paramCoverage * 0.3;

    // 因子3：案例库匹配度（权重0.25）
    const hasTemplate = result.parameters.some(p => p.source?.startsWith("CASE-"));
    confidence += (hasTemplate ? 0.9 : 0.4) * 0.25;

    // 因子4：效果可用性（权重0.15）
    const effectAvailable = this.checkEffectAvailability(result.effects[0]?.matchName);
    confidence += (effectAvailable ? 0.95 : 0.1) * 0.15;

    return Math.min(confidence, 1.0);
  }
}
```

---

## 第四章 L3 编译层

### 4.1 编译流程

L3编译层将原子参数JSON转换为可执行的ExtendScript代码：

```
原子参数JSON
  │
  ├── 1. 参数验证（类型检查、范围检查、必填项检查）
  │
  ├── 2. IR生成（中间表示）
  │
  ├── 3. 代码生成（从IR到ExtendScript）
  │
  ├── 4. 代码优化（合并重复操作、减少AE DOM调用）
  │
  ├── 5. 语法验证（干运行模式）
  │
  └── 6. 输出ExtendScript代码
```

### 4.2 调用《原子参数编译器规范》

编译器遵循原子参数编译器规范，将原子参数转换为中间表示（IR）：

```typescript
// 原子参数JSON结构
interface AtomicParameterJSON {
  operation: string;
  target: {
    compName: string;
    layerIndex: number | string; // "auto-select" | number
  };
  effect?: {
    matchName: string;
    name: string;
  };
  properties?: PropertySetting[];
  keyframes?: KeyframeSetting[];
  source?: string;
  confidence?: number;
}

// 中间表示（IR）
interface CompilationIR {
  steps: IRStep[];
  dependencies: string[];
  undoGroupName: string;
}

interface IRStep {
  type: "create_layer" | "add_effect" | "set_property" | "add_keyframe" | "set_expression" | "set_blend_mode" | "create_mask";
  target: string;  // 变量引用
  args: Record<string, any>;
}

class AtomCompiler {
  compile(atomParams: AtomicParameterJSON): CompilationIR {
    const ir: CompilationIR = {
      steps: [],
      dependencies: [],
      undoGroupName: `AutoEngine_${atomParams.operation}_${Date.now()}`,
    };

    // 步骤1：如果需要创建新图层
    if (atomParams.target.layerIndex === "new-solid" || atomParams.target.layerIndex === "auto-select") {
      ir.steps.push({
        type: "create_layer",
        target: "targetLayer",
        args: { type: "solid", name: atomParams.effect?.name || "Effect Layer" },
      });
    }

    // 步骤2：添加效果
    if (atomParams.effect) {
      ir.steps.push({
        type: "add_effect",
        target: "targetLayer",
        args: { matchName: atomParams.effect.matchName, variableName: "effect" },
      });
    }

    // 步骤3：设置属性
    if (atomParams.properties) {
      for (const prop of atomParams.properties) {
        ir.steps.push({
          type: "set_property",
          target: "effect",
          args: { name: prop.name, value: prop.value },
        });
      }
    }

    // 步骤4：添加关键帧
    if (atomParams.keyframes) {
      for (const kf of atomParams.keyframes) {
        ir.steps.push({
          type: "add_keyframe",
          target: "effect",
          args: {
            propertyName: kf.propertyName,
            time: kf.time,
            value: kf.value,
            easingType: kf.easingType || "linear",
          },
        });
      }
    }

    return ir;
  }
}
```

### 4.3 代码生成与优化

从IR生成ExtendScript代码：

```typescript
class CodeGenerator {
  generate(ir: CompilationIR): string {
    const lines: string[] = [];

    // IIFE包装
    lines.push("(function() {");

    // 获取活动合成
    lines.push("  var comp = app.project.activeItem;");
    lines.push("  if (!comp || !(comp instanceof CompItem)) {");
    lines.push('    return JSON.stringify({ success: false, error: "E101" });');
    lines.push("  }");

    // Undo组
    lines.push(`  app.beginUndoGroup("${ir.undoGroupName}");`);
    lines.push("  try {");

    // 生成每个步骤的代码
    for (const step of ir.steps) {
      switch (step.type) {
        case "create_layer":
          lines.push(...this.generateCreateLayer(step));
          break;
        case "add_effect":
          lines.push(...this.generateAddEffect(step));
          break;
        case "set_property":
          lines.push(...this.generateSetProperty(step));
          break;
        case "add_keyframe":
          lines.push(...this.generateAddKeyframe(step));
          break;
        case "set_expression":
          lines.push(...this.generateSetExpression(step));
          break;
        case "set_blend_mode":
          lines.push(...this.generateSetBlendMode(step));
          break;
      }
    }

    // 成功返回
    lines.push("    app.endUndoGroup();");
    lines.push("    return JSON.stringify({ success: true });");

    // 错误处理
    lines.push("  } catch (e) {");
    lines.push("    app.endUndoGroup();");
    lines.push('    return JSON.stringify({ success: false, error: "E200: " + e.toString() });');
    lines.push("  }");
    lines.push("})();");

    return lines.join("\n");
  }

  private generateAddEffect(step: IRStep): string[] {
    return [
      `  var ${step.args.variableName} = ${step.target}.Effects.addProperty("${step.args.matchName}");`,
    ];
  }

  private generateSetProperty(step: IRStep): string[] {
    const valueStr = JSON.stringify(step.args.value);
    return [
      `  ${step.target}.property("${step.args.name}").setValue(${valueStr});`,
    ];
  }

  private generateAddKeyframe(step: IRStep): string[] {
    const lines: string[] = [];
    const propRef = `${step.target}.property("${step.args.propertyName}")`;
    lines.push(`  ${propRef}.setValueAtTime(${step.args.time}, ${JSON.stringify(step.args.value)});`);

    if (step.args.easingType && step.args.easingType !== "linear") {
      const kfIndex = `${propRef}.nearestKeyIndex(${step.args.time})`;
      const [inType, outType] = this.easingToInterpolation(step.args.easingType);
      lines.push(`  ${propRef}.setInterpolationTypeAtKey(${kfIndex}, ${inType}, ${outType});`);
    }

    return lines;
  }

  private easingToInterpolation(easing: string): [string, string] {
    switch (easing) {
      case "easeIn": return ["KeyframeInterpolationType.BEZIER", "KeyframeInterpolationType.LINEAR"];
      case "easeOut": return ["KeyframeInterpolationType.LINEAR", "KeyframeInterpolationType.BEZIER"];
      case "easeInOut": return ["KeyframeInterpolationType.BEZIER", "KeyframeInterpolationType.BEZIER"];
      case "hold": return ["KeyframeInterpolationType.HOLD", "KeyframeInterpolationType.HOLD"];
      default: return ["KeyframeInterpolationType.LINEAR", "KeyframeInterpolationType.LINEAR"];
    }
  }

  private generateSetBlendMode(step: IRStep): string[] {
    return [
      `  ${step.target}.blendingMode = BlendingMode.${step.args.mode};`,
    ];
  }

  private generateSetExpression(step: IRStep): string[] {
    const escapedExpr = step.args.expression.replace(/'/g, "\\'").replace(/\n/g, "\\n");
    return [
      `  ${step.target}.property("${step.args.propertyName}").expression = '${escapedExpr}';`,
    ];
  }

  private generateCreateLayer(step: IRStep): string[] {
    return [
      `  var targetLayer = comp.layers.addSolid([0, 0, 0], "${step.args.name}", comp.width, comp.height, comp.pixelAspect, comp.duration);`,
    ];
  }
}
```

### 4.4 语法验证

编译后的代码在发送到AE之前进行语法验证：

```typescript
class SyntaxValidator {
  /**
   * 验证ExtendScript代码的语法正确性
   * 通过静态分析检查常见错误
   */
  validate(code: string): ValidationResult {
    const errors: ValidationError[] = [];

    // 检查1：IIFE包装
    if (!code.startsWith("(function()") || !code.endsWith("})();")) {
      errors.push({ severity: "error", message: "代码缺少IIFE包装" });
    }

    // 检查2：beginUndoGroup/endUndoGroup配对
    const beginCount = (code.match(/beginUndoGroup/g) || []).length;
    const endCount = (code.match(/endUndoGroup/g) || []).length;
    if (beginCount !== endCount) {
      errors.push({ severity: "error", message: `Undo组不配对: begin=${beginCount}, end=${endCount}` });
    }

    // 检查3：JSON.stringify返回值
    if (!code.includes("JSON.stringify")) {
      errors.push({ severity: "warning", message: "代码未使用JSON.stringify返回结果" });
    }

    // 检查4：未定义变量引用
    const varDeclarations = (code.match(/var\s+(\w+)/g) || []).map(v => v.replace("var ", ""));
    const usedVariables = (code.match(/\b\w+\./g) || []).map(v => v.replace(".", ""));
    for (const v of usedVariables) {
      if (!["app", "comp", "JSON", "Math", "KeyframeInterpolationType", "BlendingMode", "PropertyValueType"].includes(v)
          && !varDeclarations.includes(v)) {
        errors.push({ severity: "warning", message: `可能未定义的变量: ${v}` });
      }
    }

    // 检查5：代码长度限制
    if (code.length > 65536) {
      errors.push({ severity: "error", message: "代码超过64KB限制" });
    }

    return {
      valid: errors.filter(e => e.severity === "error").length === 0,
      errors,
    };
  }
}
```

---

## 第五章 L4 传输层

### 5.1 MCP协议（after-effects-mcp-main）

当前首选的传输方案，基于MCP Server + Command File轮询：

```
┌──────────────────────────┐     MCP协议      ┌──────────────────┐
│  AI助手 (TRAE/Claude)    │ ←──────────────→ │  MCP Server      │
│                          │   工具调用/结果    │  (Node.js)       │
└──────────────────────────┘                  └────────┬─────────┘
                                                       │ 写命令文件
                                                       ▼
                                              ┌──────────────────┐
                                              │ ae_command.json  │
                                              └────────┬─────────┘
                                                       │ 轮询(250ms)
                                                       ▼
                                              ┌──────────────────┐
                                              │ AE Bridge面板    │
                                              │ (CEP/ScriptUI)   │
                                              └────────┬─────────┘
                                                       │ evalScript()
                                                       ▼
                                              ┌──────────────────┐
                                              │ ExtendScript引擎  │
                                              └──────────────────┘
```

**优势**：标准化协议、已有成熟实现、与TRAE IDE原生集成
**劣势**：轮询延迟250ms、单命令串行执行

详细规范参见：[[MCP→AE效果操作桥接规范]]

### 5.2 CEP面板直连

通过CEP面板的`CSInterface.evalScript()`直接执行ExtendScript：

```
┌──────────────────────────┐   CSInterface   ┌──────────────────┐
│  CEP面板 (Chromium)      │ ──────────────→ │  ExtendScript     │
│  host/index.html          │  evalScript()   │  后端             │
└──────────────────────────┘                  └──────────────────┘
```

**优势**：无轮询延迟、可直接访问DOM、支持UI交互
**劣势**：需要安装CEP扩展、不通过MCP协议

### 5.3 Command File轮询

最基础的传输方案，直接通过文件系统通信：

```
写入方 → ae_command.json → Bridge轮询 → JSX执行 → ae_result.json → 读取方
```

**优势**：实现简单、无需网络
**劣势**：延迟高、无事件通知

### 5.4 WebSocket方案（未来）

通过WebSocket实现双向实时通信：

```
┌──────────────────────────┐   WebSocket    ┌──────────────────┐
│  MCP Server / AI助手     │ ←────────────→ │  AE WebSocket    │
│                          │   双向实时通信   │  插件            │
└──────────────────────────┘                └──────────────────┘
```

**优势**：实时通信（<10ms延迟）、双向事件通知、支持并发
**劣势**：需要开发WebSocket插件、AE端需额外组件

### 5.5 各方案对比与选择

| 维度 | MCP协议 | CEP直连 | Command File | WebSocket |
|------|--------|---------|-------------|-----------|
| 延迟 | 300-500ms | <50ms | 300-500ms | <10ms |
| 并发 | 不支持 | 不支持 | 不支持 | 支持 |
| AI集成 | 原生支持 | 需桥接 | 需桥接 | 原生支持 |
| 实现复杂度 | 中 | 低 | 低 | 高 |
| 稳定性 | ★★★★ | ★★★★ | ★★★ | ★★★ |
| 推荐场景 | 默认选择 | UI交互 | 简单脚本 | 实时控制 |

**当前推荐**：MCP协议（已实现，稳定可靠）
**未来方向**：WebSocket（需要开发AE端插件）

---

## 第六章 L5 执行层

### 6.1 ExtendScript运行时

AE的ExtendScript运行时基于ES3标准，有以下限制：

| 限制 | 说明 | 应对策略 |
|------|------|---------|
| ES3语法 | 不支持let/const/arrow function | 编译器只生成var/function语法 |
| 无Promise | 不支持异步 | 所有操作同步执行 |
| 无模块系统 | 无import/export | 所有代码打包为IIFE |
| JSON需polyfill | 无原生JSON对象 | Bridge面板注入JSON polyfill |
| 无console.log | 无标准console | 使用$.writeln()调试输出 |

### 6.2 AE DOM操作

AE DOM（Document Object Model）是ExtendScript操作AE项目的核心接口：

```javascript
// 常用DOM操作路径
app.project                          // 当前项目
app.project.activeItem              // 当前活动合成
comp.layer(index)                   // 按索引获取图层
layer.Effects                       // 图层效果集合
layer.Effects.addProperty(matchName)// 添加效果
effect.property(name)               // 获取效果属性
prop.setValue(value)                // 设置属性值
prop.setValueAtTime(time, value)    // 添加关键帧
prop.setInterpolationTypeAtKey()    // 设置关键帧插值
prop.expression = "..."             // 设置表达式
layer.blendingMode = BlendingMode.X // 设置混合模式
layer.parent = otherLayer           // 设置父子关系
layer.motionBlur = true             // 开启运动模糊
comp.layers.addSolid(...)           // 添加纯色层
comp.layers.precompose(...)         // 预合成
```

### 6.3 效果matchName查找

matchName是AE识别效果的唯一标识符，与显示名称不同：

```typescript
class MatchNameResolver {
  private matchNameDB: Record<string, string> = {
    // 内置效果
    "高斯模糊": "ADBE Gaussian Blur 2",
    "发光": "ADBE Glo2",
    "投影": "ADBE Drop Shadow",
    "色阶": "ADBE Pro Levels2",
    "曲线": "ADBE Pro Curves2",
    "色相饱和度": "ADBE HUE SATURATION",
    "色彩平衡": "ADBE Color Balance 2",
    "镜头模糊": "ADBE Lens Blur",
    "湍流置换": "ADBE Turbulent Displace",
    "方向模糊": "ADBE Motion Blur 2",
    "径向模糊": "ADBE Radial Blur 2",
    "通道混合器": "ADBE Channel Mixer",
    "位移映射": "ADBE DisplacementMap",
    "百叶窗": "ADBE Venetian Blinds",
    "杂色": "ADBE Noise2",
    "锐化": "ADBE Unsharp Mask2",

    // 第三方效果
    "Particular": "TC Particular2",
    "Form": "TC Form2",
    "Shine": "ADBE Shine",
    "Starglow": "ADBE Starglow",
    "Deep Glow": "Deep Glow",
    "Saber": "Saber",
    "BCC特效": "BCC_*",
    "Sapphire": "S_*",
  };

  resolve(name: string): string | null {
    return this.matchNameDB[name] || null;
  }

  // 动态查找：遍历AE已安装效果
  async findInstalledEffect(name: string): Promise<string | null> {
    // 通过MCP run-script执行查找脚本
    const script = `
      (function() {
        var comp = app.project.activeItem;
        if (!comp) return JSON.stringify({found: false});
        var layer = comp.layer(1);
        if (!layer) return JSON.stringify({found: false});
        var testEffect = layer.Effects.addProperty("${name}");
        var matchName = testEffect.matchName;
        testEffect.remove();
        return JSON.stringify({found: true, matchName: matchName});
      })();
    `;
    // 执行并返回matchName
    return null;
  }
}
```

### 6.4 错误捕获与恢复

执行层错误处理策略：

```javascript
// ExtendScript端的错误处理模板
(function() {
  var comp = app.project.activeItem;
  if (!comp || !(comp instanceof CompItem)) {
    return JSON.stringify({ success: false, error: "E101", message: "没有活动合成" });
  }

  app.beginUndoGroup("Engine Operation");

  try {
    // === 业务代码 ===

    app.endUndoGroup();
    return JSON.stringify({ success: true });

  } catch (e) {
    // 错误恢复：确保Undo组正确关闭
    try { app.endUndoGroup(); } catch (e2) {}

    // 分类错误
    var errorType = "E200"; // 默认运行时错误
    if (e.toString().indexOf("is not a function") > -1) errorType = "E300"; // 方法不存在
    if (e.toString().indexOf("No such") > -1) errorType = "E302"; // 属性不存在
    if (e.toString().indexOf("out of range") > -1) errorType = "E303"; // 值超范围

    return JSON.stringify({
      success: false,
      error: errorType,
      message: e.toString(),
      line: e.line || "unknown"
    });
  }
})();
```

---

## 第七章 反馈循环

### 7.1 反馈循环架构

```
┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐
│ L1   │───→│ L2   │───→│ L3   │───→│ L4   │───→│ L5   │
│ NLU  │    │推理  │    │编译  │    │传输  │    │执行  │
└──┬───┘    └──┬───┘    └──┬───┘    └──┬───┘    └──┬───┘
   │           │           │           │           │
   └───────────┴───────────┴───────────┴───────────┘
                         反馈回路
```

### 7.2 执行结果验证

#### 7.2.1 参数回读验证

执行后通过`get-effect-properties`工具回读参数，与预期对比：

```typescript
class ResultVerifier {
  async verify(expected: AtomicParameterJSON, actual: ExecutionResult): Promise<VerificationResult> {
    if (!actual.success) {
      return { passed: false, reason: `执行失败: ${actual.error}` };
    }

    // 回读效果属性
    const properties = await mcpClient.callTool("get-effect-properties", {
      compName: expected.target.compName,
      layerIndex: actual.effectIndex ? 1 : expected.target.layerIndex as number,
      effectIndex: actual.effectIndex,
    });

    // 对比参数
    const mismatches: ParameterMismatch[] = [];
    for (const expectedProp of expected.properties || []) {
      const actualProp = properties.find(p => p.name === expectedProp.name);
      if (!actualProp) {
        mismatches.push({ param: expectedProp.name, expected: expectedProp.value, actual: null });
      } else if (Math.abs(actualProp.value - expectedProp.value) > 0.01) {
        mismatches.push({ param: expectedProp.name, expected: expectedProp.value, actual: actualProp.value });
      }
    }

    return {
      passed: mismatches.length === 0,
      mismatches,
    };
  }
}
```

#### 7.2.2 截图对比验证（未来）

通过AE的`app.project.activeItem.saveFrameToPng()`导出截图，进行视觉对比：

```typescript
class VisualVerifier {
  async captureAndCompare(
    beforePath: string,
    afterPath: string
  ): Promise<VisualComparisonResult> {
    // 步骤1：在AE中截取当前帧
    // 步骤2：与操作前的截图进行像素级对比
    // 步骤3：计算差异区域和差异度
    // 步骤4：判断是否达到预期视觉效果

    return {
      differencePercentage: 0.15, // 15%的像素发生了变化
      significantChanges: ["区域A: 发光效果已添加", "区域B: 颜色偏暖"],
      passed: true,
    };
  }
}
```

### 7.3 失败重试策略

```typescript
class FailureRecovery {
  async handleFailure(error: ExecutionError, atomParams: AtomicParameterJSON): Promise<RecoveryAction> {
    switch (error.code) {
      case "E300": // 效果matchName无效
        // 尝试查找替代matchName
        const alternative = await this.findAlternativeEffect(atomParams.effect.matchName);
        if (alternative) {
          return { action: "retry_with_alternative", alternative };
        }
        return { action: "ask_user", message: "效果未安装，请安装对应插件" };

      case "E303": // 参数值超范围
        // 自动调整为有效范围
        return { action: "retry_with_adjusted_params", adjustedParams: this.clampParams(atomParams) };

      case "E600": // 执行超时
        return { action: "retry_with_longer_timeout", timeout: 15000 };

      case "E006": // Bridge离线
        return { action: "wait_and_retry", delay: 3000, maxRetries: 5 };

      default:
        return { action: "report_error", message: error.message };
    }
  }
}
```

### 7.4 用户确认流程

```typescript
class UserConfirmationFlow {
  async confirmOrAdjust(
    inferenceResult: InferenceResult,
    atomParams: AtomicParameterJSON
  ): Promise<ConfirmationResult> {
    // 构建确认消息
    const message = [
      `即将执行: ${inferenceResult.effects[0].name}`,
      `置信度: ${(inferenceResult.confidence * 100).toFixed(0)}%`,
      ``,
      `效果参数:`,
      ...atomParams.properties.map(p => `  ${p.name}: ${JSON.stringify(p.value)}`),
      ``,
      `是否继续？[确认/调整/取消]`,
    ].join("\n");

    return await this.presentToUser(message);
  }
}
```

### 7.5 从执行结果学习（闭环）

```
执行成功 → 参数记录到案例库（新增模板）
  │
  ├── 用户满意 → 置信度+0.05 → 更新映射库权重
  │
  ├── 用户微调 → 记录微调偏差 → 更新默认值
  │
  └── 用户撤销 → 记录失败原因 → 降低该路径置信度
```

```typescript
class LearningLoop {
  recordExecution(execution: ExecutionRecord): void {
    if (execution.userSatisfied) {
      // 正向学习：参数被用户认可
      this.caseStore.addTemplate({
        source: "auto-learned",
        effectType: execution.effectType,
        parameters: execution.finalParams,
        userRating: "positive",
      });

      // 提升该推理路径的置信度
      this.confidenceAdjuster.boost(execution.reasoningPath, 0.05);
    } else if (execution.userAdjusted) {
      // 偏差学习：用户调整了参数
      const deviation = this.calculateDeviation(execution.expectedParams, execution.finalParams);
      this.mappingStore.updateRecommendedValues(execution.effectMatchName, deviation);
    } else if (execution.userUndone) {
      // 负向学习：用户撤销了操作
      this.confidenceAdjuster.penalty(execution.reasoningPath, 0.1);
      this.failureStore.record({
        effectType: execution.effectType,
        reason: execution.undoReason || "unknown",
        params: execution.expectedParams,
      });
    }
  }
}
```

---

## 第八章 知识库与引擎的完整映射

### 8.1 完整映射表

| 知识库文档 | 引擎层 | 角色 | 调用方式 |
|-----------|--------|------|---------|
| 解析词汇表与推理决策树 | L2 | 推理核心 | 决策树路径遍历、词汇匹配、置信度计算 |
| 参数-效果原子级映射库 | L2/L3 | 参数→效果映射 | 正向查询（效果→参数）、逆向查询（视觉→参数） |
| AE ExtendScript API原子级映射手册 | L3/L5 | 代码生成模板 | DOM操作模板、matchName查找、属性路径解析 |
| 原子参数编译器规范 | L3 | 编译规则 | 原子参数→IR→ExtendScript的编译规则 |
| MCP→AE效果操作桥接规范 | L4 | 传输协议 | 命令格式、结果格式、错误码、重试策略 |
| 视频案例解析库 | L2 | 参数模板源 | 案例模板匹配、经验参数复用 |
| 视频效果逆向分析系统方法论 | L1/L2 | 分析方法论 | 三问分析法、分层拆解原则指导推理方向 |
| AE效果视觉特征库 | L1/L2 | 视觉识别 | 视觉签名匹配、效果识别辅助 |
| 关键帧与速度曲线逆向分析 | L2/L3 | 关键帧模板 | 缓动曲线模板、关键帧时间推断 |
| 图层堆栈与合成结构推断 | L2/L3 | 结构模板 | 合成层级模板、图层组织方案 |
| Trapcode Suite 全插件参数详解 | L2 | Particular/Form参数源 | 粒子效果参数精确查询 |
| Sapphire蓝宝石插件核心效果详解 | L2 | Sapphire参数源 | 高级效果参数查询 |
| 风格化预设宝典 | L2 | 风格组合模板 | 效果组合配方、参数套餐 |
| AE表达式进阶宝典 | L3 | 表达式模板 | 弹性/呼吸/故障等表达式生成 |
| AE第三方插件与脚本知识库 | L2 | 插件可用性检测 | 效果可用性检查、替代方案推荐 |
| 中国剪辑知识体系 | L1 | 中文语境理解 | 中文效果术语→标准术语映射 |
| 动态设计行业趋势2025-2026 | L1 | 风格趋势 | 流行效果推荐、趋势感知 |

### 8.2 映射关系图

```
知识库文档                          引擎层                数据流向
─────────────                     ──────               ────────

解析词汇表与推理决策树 ────────────→ L2推理层 ──→ 效果识别+参数推理
                                    ↑
参数-效果原子级映射库 ──────────────→ L2/L3 ────→ 参数精确映射
                                    ↑
视频案例解析库 ────────────────────→ L2 ────────→ 参数模板（高置信度）
                                    │
视频效果逆向分析系统方法论 ─────────→ L1/L2 ─────→ 推理方法论指导
                                    │
AE效果视觉特征库 ──────────────────→ L1/L2 ─────→ 视觉→效果映射
                                    │
                                    ↓
AE ExtendScript API原子级映射手册 ─→ L3/L5 ─────→ 代码生成模板
原子参数编译器规范 ────────────────→ L3 ─────────→ 编译规则
AE表达式进阶宝典 ─────────────────→ L3 ─────────→ 表达式模板
                                    │
                                    ↓
MCP→AE效果操作桥接规范 ───────────→ L4 ─────────→ 传输协议
                                    │
                                    ↓
关键帧与速度曲线逆向分析 ──────────→ L2/L3 ─────→ 关键帧模板
图层堆栈与合成结构推断 ───────────→ L2/L3 ─────→ 结构模板
Trapcode Suite参数详解 ──────────→ L2 ─────────→ 粒子参数源
Sapphire蓝宝石详解 ──────────────→ L2 ─────────→ 高级效果参数源
风格化预设宝典 ──────────────────→ L2 ─────────→ 风格组合配方
AE第三方插件知识库 ──────────────→ L2 ─────────→ 可用性检测
中国剪辑知识体系 ────────────────→ L1 ─────────→ 中文语境映射
动态设计行业趋势 ───────────────→ L1 ─────────→ 趋势推荐
```

---

## 第九章 部署方案

### 9.1 开发环境部署

```
┌─────────────────────────────────────────────────────────────┐
│  开发环境                                                    │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │ TRAE IDE      │  │ Node.js       │  │ After Effects  │  │
│  │ (含MCP Client)│  │ MCP Server    │  │ + Bridge面板   │  │
│  │ localhost     │  │ localhost     │  │ 本地安装       │  │
│  └───────┬───────┘  └───────┬───────┘  └────────┬───────┘  │
│          │                  │                    │          │
│          └──── MCP协议 ─────┘── Command File ───┘          │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐                      │
│  │ Obsidian      │  │ Git           │                      │
│  │ 知识库本地仓库 │  │ 版本控制       │                      │
│  └───────────────┘  └───────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

**部署步骤**：

1. **安装after-effects-mcp-main项目**
   ```bash
   git clone https://github.com/Dakkshin/after-effects-mcp.git
   cd after-effects-mcp
   npm install
   npm run build
   npm run install-bridge
   ```

2. **配置MCP Server**
   ```json
   {
     "mcpServers": {
       "AfterEffectsMCP": {
         "command": "node",
         "args": ["C:/path/to/after-effects-mcp/build/index.js"]
       }
     }
   }
   ```

3. **安装Bridge面板**
   - 在AE中：Window → Extensions → mcp-bridge-auto
   - 启用"Auto-run commands"

4. **部署知识库**
   - Obsidian打开AE-Knowledge-Vault仓库
   - 确认所有文档的双向链接正常

### 9.2 生产环境部署

```
┌─────────────────────────────────────────────────────────────┐
│  生产环境                                                    │
│                                                             │
│  ┌───────────────┐  ┌───────────────────────┐              │
│  │ TRAE Cloud    │  │ 本地AE工作站           │              │
│  │ (云端AI助手)  │  │ MCP Server + Bridge   │              │
│  │               │  │ + AE + 插件全套        │              │
│  └───────┬───────┘  └───────────┬───────────┘              │
│          │                      │                           │
│          └──── MCP over WS ─────┘                           │
│                                                             │
│  ┌───────────────────────────────────────────┐              │
│  │ 知识库服务器                               │              │
│  │ - 知识库API (查询接口)                     │              │
│  │ - 案例库存储                               │              │
│  │ - 学习反馈存储                             │              │
│  └───────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 9.3 与TRAE IDE的集成

```typescript
// TRAE IDE集成配置
const traeIntegration = {
  // 1. MCP Server配置
  mcpConfig: {
    serverCommand: "node",
    serverArgs: ["./after-effects-mcp/build/index.js"],
    tools: [
      // 现有22个工具 + 14个新工具
      "create-composition", "create-text-layer", "add-effect-with-keyframes",
      "set-keyframe-easing", "batch-add-effects", "execute-atom-script",
      // ... 全部36个工具
    ],
  },

  // 2. 知识库上下文
  knowledgeBaseContext: {
    // 自动注入到对话上下文的知识库文档
    primaryDocs: [
      "解析词汇表与推理决策树",
      "参数-效果原子级映射库",
      "AE效果视觉特征库",
    ],
    // 按需加载的知识库文档
    secondaryDocs: [
      "视频案例解析库",
      "风格化预设宝典",
      "AE表达式进阶宝典",
    ],
  },

  // 3. 自定义Skill
  skills: [
    {
      name: "ae-auto-effect",
      description: "根据自然语言描述自动添加AE效果",
      trigger: /加[个一].*效果|创建.*风格|添加.*动画/,
      layers: ["L1", "L2", "L3", "L4"],
    },
  ],
};
```

### 9.4 与Obsidian知识库的联动

```
Obsidian Vault                          自动化引擎
┌──────────────┐                       ┌──────────────┐
│ 知识库文档    │  ←── 文档变更通知 ──→  │ 知识缓存刷新  │
│ (Markdown)   │                       │ (内存索引)    │
└──────┬───────┘                       └──────┬───────┘
       │                                      │
       │ 文件监视                              │ 查询请求
       ▼                                      ▼
┌──────────────┐                       ┌──────────────┐
│ 增量索引器    │  ──→ 索引更新 ──→     │ 知识查询API   │
│ (watch+parse)│                       │ (REST/gRPC)  │
└──────────────┘                       └──────────────┘
```

**联动机制**：

1. **知识库变更→引擎更新**：Obsidian中文档变更后，通过文件监视器触发引擎的索引刷新
2. **引擎学习→知识库写入**：引擎从执行结果中学习的经验，自动写入Obsidian知识库的新文档
3. **双向链接**：引擎输出中包含知识库文档的双向链接，方便溯源

```typescript
class ObsidianIntegration {
  // 监视知识库变更
  watchVault(vaultPath: string): void {
    const watcher = fs.watch(vaultPath, { recursive: true }, (event, filename) => {
      if (filename?.endsWith(".md")) {
        this.engine.invalidateCache(filename);
      }
    });
  }

  // 写入学习结果到知识库
  async writeLearnedTemplate(template: LearnedTemplate): Promise<void> {
    const docPath = path.join(this.vaultPath, "10-风格化剪辑知识库", "视频案例解析库-自动学习.md");
    const content = this.formatAsMarkdown(template);
    await fs.appendFile(docPath, content);
  }
}
```

---

## 第十章 路线图

### 10.1 Phase 1：基础编译器（1-2周）

**目标**：实现原子参数→ExtendScript的编译管线

```
输入: 原子参数JSON
  │
  ├── AtomCompiler.compile() → IR
  ├── CodeGenerator.generate() → ExtendScript代码
  ├── SyntaxValidator.validate() → 验证结果
  └── 通过MCP run-script执行

输出: ExtendScript代码在AE中执行
```

**交付物**：
- AtomCompiler编译器核心
- CodeGenerator代码生成器
- SyntaxValidator语法验证器
- 10个基础效果的编译模板
- 单元测试覆盖

**验收标准**：
- 给定原子参数JSON，能正确生成可执行的ExtendScript代码
- 生成的代码在AE中执行成功率 > 90%
- 编译延迟 < 100ms

### 10.2 Phase 2：MCP工具扩展（1-2周）

**目标**：实现14个新MCP工具，覆盖效果操作全场景

```
新增工具:
├── add-effect-with-keyframes    (效果+关键帧)
├── set-keyframe-easing          (缓动设置)
├── batch-add-effects            (批量效果)
├── set-blend-mode               (混合模式)
├── set-track-matte              (轨道遮罩)
├── set-parent-layer             (父子关系)
├── add-adjustment-layer         (调整层)
├── add-precomp                  (预合成)
├── import-footage               (导入素材)
├── set-motion-blur              (运动模糊)
├── add-mask-with-shape          (遮罩)
├── execute-atom-script          (原子脚本)
├── get-effect-properties        (属性查询)
└── set-effect-keyframes         (效果关键帧)
```

**交付物**：
- 14个JSX脚本文件
- MCP Server注册代码
- Bridge白名单配置更新
- 工具集成测试

**验收标准**：
- 14个新工具全部可通过MCP调用
- 每个工具的参数Schema完整且验证通过
- Bridge面板可正确执行所有新脚本

### 10.3 Phase 3：知识推理集成（2-3周）

**目标**：将决策树、映射库、案例库接入推理层

```
知识源接入:
├── 解析词汇表与推理决策树 → InferenceEngine
├── 参数-效果原子级映射库 → ParameterEffectMapper
├── 视频案例解析库 → CaseTemplateProvider
└── 置信度评估 → ConfidenceEvaluator

推理管线:
  意图+效果描述 → 推理决策树 → 参数映射 → 案例模板匹配 → 原子参数JSON
```

**交付物**：
- InferenceEngine推理引擎
- ParameterEffectMapper映射器
- CaseTemplateProvider模板提供者
- ConfidenceEvaluator评估器
- 知识库索引与查询API

**验收标准**：
- 给定自然语言效果描述，推理出原子参数JSON的准确率 > 80%
- 置信度评估与实际成功率的相关性 > 0.7
- 案例模板匹配命中率 > 60%

### 10.4 Phase 4：NLU层集成（2-3周）

**目标**：实现自然语言→意图识别→效果描述的完整NLU管线

```
NLU管线:
  用户输入 → NLUParser → Intent → EffectDescriptionParser → 结构化效果描述
    │
    ├── 意图识别（6种操作意图）
    ├── 效果描述解析（6类关键词）
    ├── 追问确认（低置信度时）
    └── TRAE对话接口集成
```

**交付物**：
- NLUParser意图解析器
- EffectDescriptionParser效果描述解析器
- TRAE IDE集成配置
- 对话式交互UI
- 中英文双语支持

**验收标准**：
- 常见效果描述的意图识别准确率 > 85%
- 追问机制将低置信度场景的成功率提升 > 30%
- 用户满意度调查 > 4.0/5.0

### 10.5 Phase 5：反馈闭环（1-2周）

**目标**：实现执行验证→学习更新→知识库同步的闭环

```
反馈闭环:
  执行结果 → ResultVerifier → VerificationResult
    │
    ├── 成功 → 记录参数模板 → 更新映射权重
    ├── 微调 → 记录偏差 → 更新默认值
    └── 失败 → 记录原因 → 降低置信度

知识更新:
  学习结果 → ObsidianIntegration → 知识库文档更新
```

**交付物**：
- ResultVerifier结果验证器
- LearningLoop学习循环
- ObsidianIntegration知识库联动
- 失败重试策略优化
- 学习效果度量报告

**验收标准**：
- 执行结果回读验证覆盖率 > 90%
- 学习闭环运行后，推理准确率提升 > 10%
- 知识库自动更新无冲突

### 10.6 总体时间线

```
Week 1-2:  Phase 1 - 基础编译器        ████████
Week 2-4:  Phase 2 - MCP工具扩展       ████████
Week 4-7:  Phase 3 - 知识推理集成      ████████████
Week 7-10: Phase 4 - NLU层集成         ████████████
Week 10-12:Phase 5 - 反馈闭环          ████████

关键里程碑:
  M1 (Week 2):  编译器可工作，原子参数→ExtendScript
  M2 (Week 4):  36个MCP工具全部可用
  M3 (Week 7):  知识推理管线端到端运行
  M4 (Week 10): 自然语言→AE执行全链路打通
  M5 (Week 12): 反馈闭环运行，系统自我进化
```

### 10.7 风险与缓解

| 风险 | 概率 | 影响 | 缓解策略 |
|------|------|------|---------|
| ExtendScript兼容性问题 | 高 | 中 | 编译器严格限制为ES3语法，充分测试 |
| 第三方效果未安装 | 中 | 高 | 预检机制+替代方案推荐 |
| 推理准确率不达标 | 中 | 高 | 案例库优先+人工确认兜底 |
| Bridge面板稳定性 | 低 | 高 | 心跳检测+自动重启+错误恢复 |
| 性能瓶颈（轮询延迟） | 中 | 低 | 自适应轮询+未来迁移到WebSocket |
| 知识库文档不一致 | 中 | 中 | 定期审计+自动校验+版本控制 |

---

> **文档版本**：v1.0 | **最后更新**：2026-07-05 | **维护者**：AE Knowledge Vault
