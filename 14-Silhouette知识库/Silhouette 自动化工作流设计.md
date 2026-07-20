# Silhouette 自动化工作流设计

> 分类: 自动化与批处理
> 更新日期: 2026-07-11
> 概述: 工作流设计模式、状态机、错误处理、日志记录完整说明。

## 目录
1. [工作流设计概述](#1-工作流设计概述)
2. [设计模式](#2-设计模式)
3. [状态机](#3-状态机)
4. [错误处理](#4-错误处理)
5. [日志记录](#5-日志记录)
6. [工作流引擎](#6-工作流引擎)
7. [实际案例](#7-实际案例)
8. [最佳实践](#8-最佳实践)

---

## 1. 工作流设计概述

### 1.1 什么是自动化工作流

自动化工作流是将一系列处理步骤组织成可重复、可监控、可恢复的执行流程。

### 1.2 工作流核心要素

| 要素 | 说明 |
|------|------|
| 步骤(Step) | 工作流中的单个操作 |
| 状态(State) | 工作流当前所处阶段 |
| 转换(Transition) | 从一个状态到另一个 |
| 条件(Condition) | 控制流程走向 |
| 错误处理 | 异常情况的处理 |
| 日志 | 执行过程记录 |

### 1.3 工作流分类

| 类型 | 说明 | 示例 |
|------|------|------|
| 线性工作流 | 顺序执行 | 导入→处理→导出 |
| 分支工作流 | 根据条件选择路径 | 有跟踪→跟踪Roto;无跟踪→直接Roto |
| 循环工作流 | 重复执行 | 多镜头批量处理 |
| 并行工作流 | 多任务同时执行 | 多通道并行渲染 |

## 2. 设计模式

### 2.1 管道模式(Pipeline)

```python
class Pipeline:
    """管道模式:顺序执行"""
    
    def __init__(self):
        self.steps = []
    
    def add_step(self, name, func):
        """添加步骤"""
        self.steps.append({"name": name, "func": func})
        return self
    
    def run(self, context=None):
        """执行管道"""
        if context is None:
            context = {}
        
        for step in self.steps:
            print(f"执行步骤: {step['name']}")
            try:
                result = step["func"](context)
                context[step["name"]] = result
            except Exception as e:
                print(f"步骤失败: {step['name']} - {e}")
                raise
        return context

# 使用
pipeline = Pipeline()
pipeline.add_step("import", import_footage)
pipeline.add_step("track", run_tracking)
pipeline.add_step("roto", create_roto)
pipeline.add_step("export", export_result)

context = {"input_path": "/footage/"}
pipeline.run(context)
```

### 2.2 分支模式(Branch)

```python
class BranchWorkflow:
    """分支模式:条件选择"""
    
    def __init__(self):
        self.branches = []
    
    def add_branch(self, condition, func, name=""):
        """添加分支"""
        self.branches.append({
            "condition": condition,
            "func": func,
            "name": name
        })
    
    def run(self, context):
        """执行匹配的分支"""
        for branch in self.branches:
            if branch["condition"](context):
                print(f"执行分支: {branch['name']}")
                return branch["func"](context)
        
        print("没有匹配的分支")
        return None

# 使用
workflow = BranchWorkflow()
workflow.add_branch(
    lambda ctx: ctx.get("has_tracking", False),
    tracked_roto_workflow,
    "跟踪 Roto"
)
workflow.add_branch(
    lambda ctx: not ctx.get("has_tracking", False),
    manual_roto_workflow,
    "手动 Roto"
)
workflow.run(context)
```

### 2.3 循环模式(Loop)

```python
class LoopWorkflow:
    """循环模式:重复执行"""
    
    def __init__(self, items_key, func):
        self.items_key = items_key
        self.func = func
    
    def run(self, context):
        """对列表中的每个项目执行"""
        items = context.get(self.items_key, [])
        results = []
        
        for i, item in enumerate(items):
            print(f"处理项目 {i+1}/{len(items)}")
            try:
                result = self.func(item, context)
                results.append(result)
            except Exception as e:
                print(f"项目 {i+1} 失败: {e}")
                results.append({"error": str(e)})
        
        return results
```

### 2.4 并行模式(Parallel)

```python
import threading

class ParallelWorkflow:
    """并行模式:多任务同时执行"""
    
    def __init__(self, max_workers=4):
        self.max_workers = max_workers
        self.tasks = []
    
    def add_task(self, func, *args, **kwargs):
        """添加并行任务"""
        self.tasks.append({"func": func, "args": args, "kwargs": kwargs})
    
    def run(self):
        """并行执行所有任务"""
        results = [None] * len(self.tasks)
        threads = []
        
        def worker(idx, task):
            try:
                results[idx] = task["func"](*task["args"], **task["kwargs"])
            except Exception as e:
                results[idx] = {"error": str(e)}
        
        for i, task in enumerate(self.tasks):
            t = threading.Thread(target=worker, args=(i, task))
            threads.append(t)
            t.start()
            
            # 限制并发数
            while sum(1 for t in threads if t.is_alive()) >= self.max_workers:
                time.sleep(0.1)
        
        for t in threads:
            t.join()
        
        return results
```

## 3. 状态机

### 3.1 状态机设计

```python
class StateMachine:
    """状态机"""
    
    def __init__(self, initial_state="idle"):
        self.state = initial_state
        self.transitions = {}  # {state: {event: (next_state, action)}}
        self.history = []
    
    def add_transition(self, from_state, event, to_state, action=None):
        """添加状态转换"""
        if from_state not in self.transitions:
            self.transitions[from_state] = {}
        self.transitions[from_state][event] = (to_state, action)
    
    def trigger(self, event, context=None):
        """触发事件"""
        if self.state not in self.transitions:
            return False
        
        if event not in self.transitions[self.state]:
            return False
        
        to_state, action = self.transitions[self.state][event]
        
        # 记录历史
        self.history.append((self.state, event, to_state))
        
        # 执行动作
        if action:
            action(context)
        
        # 转换状态
        self.state = to_state
        return True
    
    def can_trigger(self, event):
        """检查是否可以触发事件"""
        return (self.state in self.transitions and 
                event in self.transitions[self.state])
```

### 3.2 渲染工作流状态机

```python
def create_render_state_machine():
    """创建渲染工作流状态机"""
    sm = StateMachine("idle")
    
    # 状态转换定义
    sm.add_transition("idle", "start", "initializing", init_render)
    sm.add_transition("initializing", "ready", "loading", load_project)
    sm.add_transition("loading", "loaded", "configuring", configure_output)
    sm.add_transition("configuring", "configured", "rendering", start_render)
    sm.add_transition("rendering", "progress", "rendering", update_progress)
    sm.add_transition("rendering", "complete", "finalizing", finalize_output)
    sm.add_transition("rendering", "error", "error", handle_error)
    sm.add_transition("finalizing", "done", "completed", cleanup)
    sm.add_transition("error", "retry", "initializing", init_render)
    sm.add_transition("error", "abort", "aborted", cleanup)
    sm.add_transition("completed", "reset", "idle", reset)
    sm.add_transition("aborted", "reset", "idle", reset)
    
    return sm

# 状态图:
# idle → initializing → loading → configuring → rendering → finalizing → completed
#                                                            ↓
#                                                          error
#                                                       ↓        ↓
#                                                    retry      abort
#                                                       ↓        ↓
#                                               initializing  aborted
```

### 3.3 状态机动作

```python
def init_render(context):
    """初始化渲染"""
    print("初始化渲染...")
    context["start_time"] = time.time()

def load_project(context):
    """加载项目"""
    print(f"加载项目: {context.get('project_path')}")
    # 实际加载逻辑

def configure_output(context):
    """配置输出"""
    print(f"配置输出: {context.get('output_path')}")
    # 实际配置逻辑

def start_render(context):
    """开始渲染"""
    print(f"开始渲染: {context.get('frame_range')}")
    # 实际渲染逻辑

def update_progress(context):
    """更新进度"""
    print(f"进度: {context.get('progress', 0):.1%}")

def handle_error(context):
    """处理错误"""
    print(f"错误: {context.get('error')}")

def finalize_output(context):
    """完成输出"""
    print("完成输出...")

def cleanup(context):
    """清理"""
    print("清理资源...")

def reset(context):
    """重置"""
    print("重置状态...")
```

## 4. 错误处理

### 4.1 错误分类

```python
class ErrorType:
    """错误类型"""
    RECOVERABLE = "recoverable"  # 可恢复
    FATAL = "fatal"              # 致命
    WARNING = "warning"          # 警告
    INFO = "info"                # 信息

class WorkflowError(Exception):
    """工作流错误"""
    def __init__(self, message, error_type=ErrorType.FATAL, recoverable=False):
        super().__init__(message)
        self.error_type = error_type
        self.recoverable = recoverable

class FileError(WorkflowError):
    """文件错误"""
    pass

class RenderError(WorkflowError):
    """渲染错误"""
    pass

class LicenseError(WorkflowError):
    """许可证错误"""
    pass
```

### 4.2 错误处理策略

```python
class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.strategies = {
            ErrorType.RECOVERABLE: self._handle_recoverable,
            ErrorType.FATAL: self._handle_fatal,
            ErrorType.WARNING: self._handle_warning,
            ErrorType.INFO: self._handle_info
        }
    
    def handle(self, error, context=None):
        """处理错误"""
        strategy = self.strategies.get(error.error_type, self._handle_fatal)
        return strategy(error, context)
    
    def _handle_recoverable(self, error, context):
        """处理可恢复错误"""
        print(f"[可恢复] {error}")
        return "retry"
    
    def _handle_fatal(self, error, context):
        """处理致命错误"""
        print(f"[致命] {error}")
        return "abort"
    
    def _handle_warning(self, error, context):
        """处理警告"""
        print(f"[警告] {error}")
        return "continue"
    
    def _handle_info(self, error, context):
        """处理信息"""
        print(f"[信息] {error}")
        return "continue"
```

### 4.3 重试机制

```python
class RetryHandler:
    """重试处理器"""
    
    def __init__(self, max_retries=3, backoff_base=1):
        self.max_retries = max_retries
        self.backoff_base = backoff_base
    
    def execute_with_retry(self, func, *args, **kwargs):
        """带重试的执行"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except WorkflowError as e:
                last_error = e
                if not e.recoverable:
                    raise
                
                wait_time = self.backoff_base * (2 ** attempt)
                print(f"尝试 {attempt + 1}/{self.max_retries} 失败, "
                      f"等待 {wait_time}s 后重试")
                time.sleep(wait_time)
            except Exception as e:
                last_error = e
                print(f"未知错误: {e}")
                break
        
        raise last_error
```

## 5. 日志记录

### 5.1 日志系统

```python
import logging
import json
from datetime import datetime

class WorkflowLogger:
    """工作流日志记录器"""
    
    def __init__(self, name, log_file=None, level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # 控制台输出
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        
        # 文件输出
        if log_file:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
    
    def info(self, msg, **kwargs):
        self.logger.info(msg, extra=kwargs)
    
    def error(self, msg, **kwargs):
        self.logger.error(msg, extra=kwargs)
    
    def debug(self, msg, **kwargs):
        self.logger.debug(msg, extra=kwargs)
    
    def log_step(self, step_name, status, **details):
        """记录步骤"""
        self.info(f"步骤 [{step_name}] {status}", **details)
```

### 5.2 结构化日志

```python
class StructuredLogger:
    """结构化日志(JSON 格式)"""
    
    def __init__(self, log_file):
        self.log_file = log_file
        self.entries = []
    
    def log(self, level, message, **kwargs):
        """记录结构化日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "data": kwargs
        }
        self.entries.append(entry)
        
        # 写入文件
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def info(self, message, **kwargs):
        self.log("INFO", message, **kwargs)
    
    def error(self, message, **kwargs):
        self.log("ERROR", message, **kwargs)
    
    def warning(self, message, **kwargs):
        self.log("WARNING", message, **kwargs)
```

### 5.3 性能日志

```python
class PerformanceLogger:
    """性能日志"""
    
    def __init__(self, logger):
        self.logger = logger
        self.timings = {}
    
    def start(self, operation):
        """开始计时"""
        self.timings[operation] = {"start": time.time()}
    
    def end(self, operation):
        """结束计时"""
        if operation in self.timings:
            elapsed = time.time() - self.timings[operation]["start"]
            self.timings[operation]["elapsed"] = elapsed
            self.logger.info(f"性能: {operation} 用时 {elapsed:.2f}s")
            return elapsed
        return None
    
    def summary(self):
        """性能摘要"""
        total = sum(t.get("elapsed", 0) for t in self.timings.values())
        return {
            "total_time": total,
            "operations": self.timings
        }
```

## 6. 工作流引擎

### 6.1 工作流定义

```python
class WorkflowDefinition:
    """工作流定义"""
    
    def __init__(self, name):
        self.name = name
        self.steps = []
        self.error_handlers = {}
    
    def add_step(self, name, func, condition=None, on_error=None):
        """添加步骤"""
        self.steps.append({
            "name": name,
            "func": func,
            "condition": condition,
            "on_error": on_error
        })
        return self
    
    def get_step(self, name):
        """获取步骤"""
        for step in self.steps:
            if step["name"] == name:
                return step
        return None
```

### 6.2 工作流引擎实现

```python
class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self, logger=None):
        self.logger = logger or WorkflowLogger("WorkflowEngine")
        self.perf = PerformanceLogger(self.logger)
    
    def execute(self, workflow, context=None):
        """执行工作流"""
        if context is None:
            context = {}
        
        self.logger.info(f"开始执行工作流: {workflow.name}")
        self.perf.start(workflow.name)
        
        results = {}
        
        for step in workflow.steps:
            # 检查条件
            if step["condition"] and not step["condition"](context):
                self.logger.info(f"跳过步骤: {step['name']}")
                continue
            
            self.logger.log_step(step["name"], "开始")
            self.perf.start(step["name"])
            
            try:
                result = step["func"](context)
                results[step["name"]] = result
                context[step["name"]] = result
                self.perf.end(step["name"])
                self.logger.log_step(step["name"], "完成")
                
            except Exception as e:
                self.perf.end(step["name"])
                self.logger.error(f"步骤失败: {step['name']} - {e}")
                
                # 错误处理
                if step["on_error"]:
                    action = step["on_error"](e, context)
                    if action == "continue":
                        continue
                    elif action == "abort":
                        break
                    elif action == "retry":
                        # 重试逻辑
                        pass
                else:
                    raise
        
        self.perf.end(workflow.name)
        self.logger.info(f"工作流完成: {workflow.name}")
        
        return results
```

## 7. 实际案例

### 7.1 Roto 自动化工作流

```python
def create_roto_workflow():
    """创建 Roto 自动化工作流"""
    workflow = WorkflowDefinition("Auto_Roto")
    
    # 步骤定义
    workflow.add_step("import_footage", import_footage)
    workflow.add_step("analyze_scene", analyze_scene)
    workflow.add_step("create_tracker", create_tracker, 
                      condition=lambda ctx: ctx.get("needs_tracking", True))
    workflow.add_step("run_tracking", run_tracking,
                      condition=lambda ctx: ctx.get("needs_tracking", True))
    workflow.add_step("create_roto", create_roto_shapes)
    workflow.add_step("apply_tracking", apply_tracking_to_roto,
                      condition=lambda ctx: ctx.get("needs_tracking", True))
    workflow.add_step("refine_roto", refine_roto_edges)
    workflow.add_step("export_matte", export_matte)
    
    return workflow

# 执行
engine = WorkflowEngine()
workflow = create_roto_workflow()
context = {
    "footage_path": "/input/shot_001.####.exr",
    "output_path": "/output/shot_001/",
    "frame_range": (1, 100),
    "needs_tracking": True
}
engine.execute(workflow, context)
```

### 7.2 批量处理工作流

```python
def create_batch_workflow():
    """创建批量处理工作流"""
    workflow = WorkflowDefinition("Batch_Process")
    
    workflow.add_step("load_shot_list", load_shot_list)
    workflow.add_step("validate_shots", validate_shots)
    workflow.add_step("process_each_shot", batch_process)
    workflow.add_step("generate_report", generate_report)
    
    return workflow

def batch_process(context):
    """批量处理每个镜头"""
    shots = context.get("shots", [])
    results = []
    
    for shot in shots:
        try:
            result = process_single_shot(shot)
            results.append({"shot": shot["id"], "status": "success", "result": result})
        except Exception as e:
            results.append({"shot": shot["id"], "status": "failed", "error": str(e)})
    
    context["batch_results"] = results
    return results
```

## 8. 最佳实践

### 8.1 工作流设计原则

1. **单一职责**:每个步骤只做一件事
2. **可测试**:步骤可独立测试
3. **可重用**:步骤可在不同工作流中复用
4. **可监控**:执行过程可追踪
5. **可恢复**:失败后可从断点恢复

### 8.2 上下文管理

```python
class WorkflowContext:
    """工作流上下文"""
    
    def __init__(self, **kwargs):
        self.data = kwargs
        self.history = []
    
    def set(self, key, value):
        """设置值"""
        self.history.append((key, self.data.get(key)))
        self.data[key] = value
    
    def get(self, key, default=None):
        """获取值"""
        return self.data.get(key, default)
    
    def rollback(self, steps=1):
        """回滚"""
        for _ in range(steps):
            if self.history:
                key, old_value = self.history.pop()
                if old_value is None:
                    self.data.pop(key, None)
                else:
                    self.data[key] = old_value
    
    def to_dict(self):
        """转换为字典"""
        return dict(self.data)
```

### 8.3 工作流测试

```python
def test_workflow():
    """测试工作流"""
    workflow = create_roto_workflow()
    engine = WorkflowEngine()
    
    # 测试上下文
    context = {
        "footage_path": "/test/footage.exr",
        "output_path": "/test/output/",
        "frame_range": (1, 10),
        "needs_tracking": False
    }
    
    try:
        results = engine.execute(workflow, context)
        print("测试通过")
        return True
    except Exception as e:
        print(f"测试失败: {e}")
        return False
```

### 8.4 工作流文档化

```python
def document_workflow(workflow):
    """生成工作流文档"""
    doc = f"# 工作流: {workflow.name}\n\n"
    doc += "## 步骤\n\n"
    
    for i, step in enumerate(workflow.steps, 1):
        doc += f"{i}. **{step['name']}**\n"
        if step.get("condition"):
            doc += f"   - 条件: {step['condition'].__name__}\n"
        doc += "\n"
    
    return doc
```

---

## 附录:工作流设计检查清单

| 检查项 | 说明 |
|--------|------|
| □ 步骤清晰 | 每个步骤有明确输入输出 |
| □ 条件完备 | 所有可能的路径都有处理 |
| □ 错误处理 | 每个步骤都有错误处理策略 |
| □ 日志完整 | 关键操作都有日志记录 |
| □ 可恢复 | 失败后可从断点恢复 |
| □ 可测试 | 步骤可独立测试 |
| □ 性能监控 | 关键步骤有性能计时 |
| □ 文档齐全 | 工作流有完整文档 |

> **提示**:设计复杂工作流时,先用流程图画出所有状态和转换,再编写代码实现,可避免遗漏边界情况。
