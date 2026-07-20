# AE + Silhouette 最优集成方案

## 1. 架构设计

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户输入层                                    │
│                    自然语言 / API 请求 / UI 操作                          │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         NLU 理解层                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │ 意图识别     │  │ 槽位提取     │  │ 置信度评估   │                  │
│  │ (NLUParser)  │  │ (Slots)      │  │ (Confidence) │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                 │                 │                          │
│         └─────────────────┼─────────────────┘                          │
│                           ▼                                            │
│              ┌───────────────────────┐                                  │
│              │  意图决策器           │                                  │
│              │  AE任务 / Silhouette任务 / 混合任务                      │
│              └───────────┬───────────┘                                  │
└──────────────────────────┼──────────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   AE 任务流   │  │Silhouette任务│  │   混合任务流   │
│   生成器      │  │   生成器      │  │   协调器      │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        ▼                  ▼                  │
┌───────────────┐  ┌───────────────┐         │
│   AE JSX      │  │  fx Script    │         │
│   脚本生成    │  │  脚本生成     │         │
└───────┬───────┘  └───────┬───────┘         │
        │                  │                  │
        ▼                  ▼                  │
┌───────────────┐  ┌───────────────┐         │
│   AE 执行     │  │ Silhouette    │         │
│   (MCP Bridge)│  │ 执行 (fx API) │         │
└───────┬───────┘  └───────┬───────┘         │
        │                  │                  │
        │                  ▼                  │
        │          ┌───────────────┐          │
        │          │  渲染输出     │          │
        │          │  (Matte/Track)│          │
        │          └───────┬───────┘          │
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         AE 合成层                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │ 导入 Matte   │  │ 设置 Track   │  │ 应用效果     │                  │
│  │ 序列         │  │ 关键帧       │  │              │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 分层职责

| 层级 | 职责 | 关键组件 |
|------|------|----------|
| **用户输入层** | 接收自然语言/API/UI输入 | Trae Agent, Web API |
| **NLU理解层** | 意图识别、槽位提取、决策路由 | NLUParser, IntentRouter |
| **任务生成层** | AE/Silhouette/混合任务生成 | EffectGenerator, SilhouetteGenerator, HybridCoordinator |
| **脚本生成层** | JSX/fx脚本生成 | CodeGenerator, FxScriptGenerator |
| **执行层** | AE/Silhouette脚本执行 | AEBridge, SilhouetteExecutor |
| **合成层** | 最终AE合成组装 | AE JSX, Comp Builder |

---

## 2. 模块设计

### 2.1 NLU 决策器 (IntentRouter)

```typescript
export class IntentRouter {
    route(intent: Intent): TaskRoute {
        // 纯 AE 任务: 效果、动画、图层操作
        if (isAEOnly(intent)) {
            return { type: 'ae_only', operations: generateAEOperations(intent) };
        }
        
        // 纯 Silhouette 任务: roto/track/paint
        if (isSilhouetteOnly(intent)) {
            return { type: 'silhouette_only', operations: generateSilhouetteOperations(intent) };
        }
        
        // 混合任务: 需要两边协作
        if (isHybrid(intent)) {
            return { type: 'hybrid', aeOps: [...], silhouetteOps: [...] };
        }
        
        return { type: 'unknown' };
    }
}
```

**路由规则：**

| 用户输入示例 | 路由类型 | 原因 |
|------------|----------|------|
| "加个模糊效果" | ae_only | 纯 AE 效果 |
| "扣个人像" | silhouette_only | 纯遮罩 |
| "扣人像后加发光" | hybrid | Silhouette 抠像 + AE 发光 |
| "跟踪物体并添加文字" | hybrid | Silhouette 跟踪 + AE 文字动画 |
| "修复画面瑕疵" | silhouette_only | Paint 修复 |

### 2.2 任务协调器 (HybridCoordinator)

```typescript
export class HybridCoordinator {
    async execute(route: HybridTaskRoute): Promise<ExecutionResult> {
        // Phase 1: Silhouette 前置处理
        const silhouetteResult = await this.silhouetteExecutor.execute(route.silhouetteOps);
        
        // Phase 2: AE 后置处理
        const aeResult = await this.aeBridge.execute(route.aeOps, silhouetteResult.outputs);
        
        // Phase 3: 结果整合
        return {
            silhouetteArtifacts: silhouetteResult.artifacts,
            aeComposition: aeResult.composition,
            status: 'success'
        };
    }
}
```

### 2.3 Silhouette 执行引擎 (SilhouetteExecutor v2)

**增强版执行端，支持更多命令类型：**

| 命令 | 功能 | 参数 | 输出 |
|------|------|------|------|
| `silhouette_roto` | 自动生成 Roto 遮罩 | shape_type, tolerance, tracking | Matte 序列 |
| `silhouette_track` | 平面/点跟踪 | track_type, accuracy, search_area | 跟踪数据 JSON |
| `silhouette_paint` | Paint 修复/擦除 | paint_mode, brush_size | 修复帧序列 |
| `silhouette_export` | 导出 Matte/Tracking | export_format, output_path | AE 兼容文件 |
| `silhouette_ml_mask` | AI 自动遮罩 | model_type, sensitivity | AI Matte |
| `silhouette_stabilize` | 画面稳定 | stabilize_mode, smoothing | 稳定后视频 |
| `silhouette_composite` | Silhouette 内合成 | composite_mode, layers | 合成结果 |

### 2.4 数据交换层

**统一的数据交换格式，兼容 AE 和 Silhouette：**

```typescript
export interface SilhouetteOutput {
    version: string;
    source: 'silhouette';
    timestamp: string;
    
    // Roto 输出
    roto?: {
        matteSequence: string;           // PNG/EXR 序列路径
        shapeType: 'x-spline' | 'bezier';
        frameRange: [number, number];
        resolution: [number, number];
    };
    
    // 跟踪输出
    tracking?: {
        trackers: TrackerData[];         // 跟踪器数据
        exportFormat: 'ae_keyframes' | 'mocha' | 'json';
        nullObjectName: string;
    };
    
    // Paint 输出
    paint?: {
        paintedFrames: string;           // 修复帧序列
        paintMode: 'clone' | 'blend' | 'replace';
    };
    
    // AE 集成信息
    aeIntegration: {
        compName: string;
        importPath: string;
        applyAs: 'track_matte' | 'tracking_data' | 'replace_frames';
        targetLayer?: string;
        matteMode?: 'alpha' | 'luma';
    };
}

export interface TrackerData {
    name: string;
    type: 'planar' | 'point' | 'corner';
    keyframes: {
        frame: number;
        position: [number, number];
        scale?: number;
        rotation?: number;
        corners?: [[number, number], [number, number], [number, number], [number, number]];
    }[];
}
```

---

## 3. 最优流程方案

### 3.1 Roto 遮罩 → AE 合成流程

```
步骤1: 用户输入
    "扣个人像，用贝塞尔曲线，边缘羽化"
    
步骤2: NLU 解析
    Intent: SILHOUETTE_TASK
    Slots: { silhouetteTask: "roto", rotoTarget: "人像", effectName: "bezier" }
    
步骤3: 路由决策
    Route: silhouette_only
    
步骤4: Silhouette 执行
    silhouette_roto {
        source_path: "input_video.mp4",
        shape_type: "bezier",
        tolerance: 1.5,
        tracking: "planar",
        output_format: "exr"
    }
    
步骤5: Silhouette 渲染
    → D:/AE-Work/silhouette_output/matte_roto_[####].exr
    
步骤6: AE 集成 JSX
    - 导入 Matte 序列
    - 创建合成
    - 设置 Track Matte
    - 添加背景层
    
步骤7: 最终效果
    人物被完美抠出，背景透明
```

### 3.2 跟踪 → AE 动画流程

```
步骤1: 用户输入
    "跟踪这个物体，让文字跟着动"
    
步骤2: NLU 解析
    Intent: SILHOUETTE_TASK
    Slots: { silhouetteTask: "track", trackType: "planar" }
    
步骤3: 路由决策
    Route: hybrid
    SilhouetteOps: [silhouette_track]
    AEOps: [create_text, link_to_tracking]
    
步骤4: Silhouette 跟踪
    silhouette_track {
        source_path: "input_video.mp4",
        track_type: "planar",
        export_format: "ae_keyframes"
    }
    
步骤5: 输出跟踪数据
    → track_data.json (包含所有关键帧)
    
步骤6: AE 执行
    - 创建 Null 对象
    - 应用跟踪关键帧 (Position/Scale/Rotation)
    - 创建文字图层
    - 父子链接到 Null
    
步骤7: 最终效果
    文字自动跟随被跟踪物体运动
```

### 3.3 Paint 修复 → AE 流程

```
步骤1: 用户输入
    "修掉画面里的水印，用 clone 模式"
    
步骤2: NLU 解析
    Intent: SILHOUETTE_TASK
    Slots: { silhouetteTask: "paint", paintMode: "clone" }
    
步骤3: 路由决策
    Route: silhouette_only
    
步骤4: Silhouette Paint
    silhouette_paint {
        source_path: "input_video.mp4",
        paint_mode: "clone",
        brush_size: 30
    }
    
步骤5: 输出修复帧
    → D:/AE-Work/silhouette_output/paint_repair_[####].png
    
步骤6: AE 集成
    - 导入修复帧序列
    - 在原素材上替换指定帧
    
步骤7: 最终效果
    水印被移除，画面无缝修复
```

---

## 4. 数据流向图

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  用户输入  │───►│  NLU解析  │───►│  路由决策  │───►│ 任务生成  │
└──────────┘    └──────────┘    └──────────┘    └─────┬────┘
                                                      │
                    ┌──────────────────────────────────┼──────────────────────────────────┐
                    ▼                                  ▼                                  ▼
            ┌──────────────┐                  ┌──────────────┐                  ┌──────────────┐
            │ AE 脚本生成   │                  │ fx 脚本生成   │                  │ 混合任务协调 │
            │ (JSX)        │                  │ (Python)     │                  │ (Coordinator)│
            └──────┬───────┘                  └──────┬───────┘                  └──────┬───────┘
                   │                                  │                                  │
                   ▼                                  ▼                                  │
            ┌──────────────┐                  ┌──────────────┐                         │
            │ AE 执行      │                  │ Silhouette   │                         │
            │ (MCP Bridge) │                  │ 执行 (fx API)│                         │
            └──────┬───────┘                  └──────┬───────┘                         │
                   │                                  │                                  │
                   │                                  ▼                                  │
                   │                         ┌──────────────┐                         │
                   │                         │ 渲染输出      │                         │
                   │                         │ Matte/Track   │                         │
                   │                         └──────┬───────┘                         │
                   │                                  │                                  │
                   └──────────────────────────────────┼──────────────────────────────────┘
                                                      ▼
                                              ┌──────────────┐
                                              │ AE 合成组装   │
                                              │ (JSX)        │
                                              └──────────────┘
```

---

## 5. 容错与错误处理

### 5.1 执行容错机制

```typescript
export class ExecutionGuard {
    async executeWithRetry<T>(
        operation: () => Promise<T>,
        maxRetries: number = 3,
        delayMs: number = 2000
    ): Promise<T> {
        for (let i = 0; i < maxRetries; i++) {
            try {
                return await operation();
            } catch (error) {
                if (i === maxRetries - 1) throw error;
                await sleep(delayMs * (i + 1));
            }
        }
        throw new Error('Max retries exceeded');
    }
}
```

### 5.2 错误分类与处理

| 错误类型 | 处理策略 | 恢复方案 |
|----------|----------|----------|
| Silhouette 未安装 | 降级到 AE 原生工具 | AE Mask + 原生跟踪器 |
| 文件路径错误 | 自动重试 + 用户提示 | 重新选择文件 |
| 渲染超时 | 分段渲染 + 断点续传 | 从失败帧继续 |
| AE 脚本错误 | 回滚到上一状态 | 恢复 AE 项目 |
| 内存不足 | 释放资源 + 分批处理 | 分帧处理 |

---

## 6. 性能优化策略

### 6.1 缓存机制

```typescript
export class TaskCache {
    private cache = new Map<string, ExecutionResult>();
    
    get(key: string): ExecutionResult | undefined {
        return this.cache.get(key);
    }
    
    set(key: string, result: ExecutionResult): void {
        this.cache.set(key, result);
    }
    
    invalidate(pattern: RegExp): void {
        for (const key of this.cache.keys()) {
            if (pattern.test(key)) {
                this.cache.delete(key);
            }
        }
    }
}
```

### 6.2 并行处理

```typescript
export class ParallelExecutor {
    async executeAll(tasks: Task[]): Promise<Result[]> {
        const results = await Promise.allSettled(
            tasks.map(t => this.executeTask(t))
        );
        
        return results.map((r, i) => ({
            taskId: tasks[i].id,
            result: r.status === 'fulfilled' ? r.value : null,
            error: r.status === 'rejected' ? r.reason : null
        }));
    }
}
```

### 6.3 智能调度

| 任务类型 | 执行时机 | 优先级 |
|----------|----------|--------|
| Roto 遮罩 | 后台异步 | 中 |
| 跟踪 | 后台异步 | 中 |
| Paint 修复 | 后台异步 | 中 |
| AE 效果 | 实时同步 | 高 |
| 渲染输出 | 空闲时段 | 低 |

---

## 7. 扩展性设计

### 7.1 插件架构

```typescript
export interface SilhouettePlugin {
    name: string;
    version: string;
    commands: Command[];
    
    register(executor: SilhouetteExecutor): void;
    execute(command: string, params: any): Promise<any>;
}

// 示例插件: AI Mask 插件
export class AIMaskPlugin implements SilhouettePlugin {
    name = 'ai-mask';
    version = '1.0';
    commands = ['silhouette_ml_mask'];
    
    register(executor: SilhouetteExecutor) {
        executor.registerCommand('silhouette_ml_mask', this.handleMLMask.bind(this));
    }
    
    async handleMLMask(params: any) {
        // 调用 AI 模型生成遮罩
    }
}
```

### 7.2 节点类型扩展

| 节点类型 | 功能 | 适用场景 |
|----------|------|----------|
| `RotoNode` | 手动 Roto 遮罩 | 精确抠像 |
| `PowerMatteNode` | 自动遮罩 | 毛发/半透明 |
| `MLMaskTrackerNode` | AI 自动跟踪遮罩 | 复杂场景 |
| `TrackerNode` | 平面/点跟踪 | 物体跟踪 |
| `StabilityAINode` | AI 画面稳定 | 手持素材 |
| `PaintNode` | Paint 修复 | 瑕疵修复 |
| `MLInpaintNode` | AI 修复 | 大面积修复 |

---

## 8. 兼容性设计

### 8.1 AE 版本兼容

| AE 版本 | 支持功能 | 限制 |
|---------|----------|------|
| AE 2024+ | 全部功能 | 无 |
| AE 2023 | 大部分功能 | ML 效果可能不可用 |
| AE 2022 | 基础功能 | 部分新效果不可用 |

### 8.2 Silhouette 版本兼容

| Silhouette 版本 | 支持功能 | 限制 |
|-----------------|----------|------|
| 2026.0.2 | 全部功能（含 AI 工具） | 无 |
| 2025 | 基础功能 | ML 节点不可用 |
| 2024 | 基础功能 | 部分 AI 节点不可用 |

### 8.3 操作系统兼容

| 系统 | AE | Silhouette | 状态 |
|------|-----|------------|------|
| Windows 10/11 | ✅ | ✅ | 完全支持 |
| macOS | ✅ | ✅ | 完全支持 |
| Linux | ❌ | ✅ | Silhouette 可用 |

---

## 9. 安全设计

### 9.1 签名验证

```python
class AEBridgeClient:
    def _verify_signature(self, data: Dict) -> bool:
        if not self.signature_enabled:
            return True
        
        expected_signature = data.pop('signature', '')
        calculated = hmac.new(
            self.secret.encode(),
            json.dumps(data, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()
        
        return calculated == expected_signature
```

### 9.2 路径白名单

```python
ALLOWED_PATHS = [
    r"D:\AE-Work",
    r"C:\Users\Administrator\Documents",
    r"C:\Temp"
]

def validate_path(path: str) -> bool:
    return any(path.startswith(p) for p in ALLOWED_PATHS)
```

---

## 10. 监控与日志

### 10.1 执行日志

```typescript
export interface ExecutionLog {
    timestamp: string;
    taskId: string;
    command: string;
    params: any;
    status: 'pending' | 'running' | 'success' | 'error';
    durationMs: number;
    error?: string;
    outputPath?: string;
}
```

### 10.2 性能监控

| 指标 | 监控方式 | 告警阈值 |
|------|----------|----------|
| 执行时间 | 计时器 | > 5分钟 |
| 内存使用 | 系统 API | > 80% |
| 渲染进度 | 回调 | - |
| 错误率 | 统计 | > 5% |

---

## 11. 总结

### 11.1 优势

1. **完整覆盖**: 支持 AE 和 Silhouette 全部核心功能
2. **智能路由**: 根据用户意图自动选择最优工具链
3. **混合任务**: 支持 AE + Silhouette 协作的复杂任务
4. **容错可靠**: 多级重试和错误恢复机制
5. **性能优化**: 缓存、并行、智能调度
6. **高度扩展**: 插件架构，易于添加新功能
7. **安全可靠**: 签名验证和路径白名单

### 11.2 关键文件清单

| 文件 | 职责 |
|------|------|
| `compiler/src/phase4/nlu-parser.ts` | NLU 意图识别 |
| `compiler/src/phase4/ai-scheduler.ts` | AI 调度引擎 |
| `compiler/src/phase4/types.ts` | 类型定义 |
| `silhouette_executor.py` | Silhouette 执行端 |
| `ae_agent_pipeline.py` | 端到端流程管理 |
| `silhouette_fx_emulator.py` | fx API 模拟器 |
| `apply_silhouette_to_ae.jsx` | AE 集成脚本 |

### 11.3 下一步建议

1. 实现 IntentRouter 路由决策器
2. 增强 SilhouetteExecutor 支持更多命令
3. 实现 HybridCoordinator 混合任务协调器
4. 添加完整的错误处理和日志系统
5. 实现缓存和并行执行机制
6. 编写端到端集成测试
