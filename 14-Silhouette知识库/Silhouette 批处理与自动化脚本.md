# Silhouette 批处理与自动化脚本

> 分类: 自动化与批处理
> 更新日期: 2026-07-11
> 概述: 批量处理多个镜头、自动化工作流构建、错误恢复机制完整说明。

## 目录
1. [批处理概述](#1-批处理概述)
2. [批量镜头处理](#2-批量镜头处理)
3. [自动化工作流](#3-自动化工作流)
4. [错误恢复机制](#4-错误恢复机制)
5. [进度监控](#5-进度监控)
6. [批处理脚本模板](#6-批处理脚本模板)
7. [并行处理](#7-并行处理)
8. [最佳实践](#8-最佳实践)

---

## 1. 批处理概述

### 1.1 什么是批处理

批处理是指对多个镜头、多个任务或多个文件执行相同或相似操作的能力,是提高生产效率的关键技术。

### 1.2 批处理应用场景

| 场景 | 说明 | 典型操作 |
|------|------|----------|
| 多镜头 Roto | 100+ 镜头统一 Roto | 应用相同跟踪+Roto 模板 |
| 批量导出 | 多个 Session 导出 Matte | 统一命名+格式 |
| 批量调色 | 多镜头应用相同调色 | 加载 LUT/调色预设 |
| 批量跟踪 | 多镜头特征点跟踪 | 统一参数 |
| 批量修复 | 多镜头标记点去除 | Paint 自动修复 |

### 1.3 批处理架构

```
[任务列表] → [任务调度器] → [执行引擎] → [结果收集] → [报告生成]
                ↓               ↓
            [进度监控]      [错误处理]
```

## 2. 批量镜头处理

### 2.1 镜头列表管理

```python
from fx import *
import os
import json

class ShotList:
    """镜头列表管理"""
    
    def __init__(self):
        self.shots = []
    
    def add_shot(self, shot_id, source_path, frame_range, output_path):
        """添加镜头"""
        shot = {
            "id": shot_id,
            "source": source_path,
            "start_frame": frame_range[0],
            "end_frame": frame_range[1],
            "output": output_path,
            "status": "pending",
            "error": None
        }
        self.shots.append(shot)
        return shot
    
    def load_from_json(self, json_path):
        """从 JSON 文件加载镜头列表"""
        with open(json_path, "r") as f:
            data = json.load(f)
        for item in data:
            self.add_shot(
                item["id"],
                item["source"],
                (item["start"], item["end"]),
                item["output"]
            )
        return self.shots
    
    def save_to_json(self, json_path):
        """保存镜头列表到 JSON"""
        with open(json_path, "w") as f:
            json.dump(self.shots, f, indent=2, ensure_ascii=False)
    
    def get_pending(self):
        """获取待处理的镜头"""
        return [s for s in self.shots if s["status"] == "pending"]
    
    def get_failed(self):
        """获取失败的镜头"""
        return [s for s in self.shots if s["status"] == "failed"]
```

### 2.2 批量处理执行器

```python
class BatchProcessor:
    """批量处理执行器"""
    
    def __init__(self, shot_list):
        self.shot_list = shot_list
        self.current_index = 0
        self.results = []
        self.callbacks = {}
    
    def register_callback(self, event, callback):
        """注册事件回调
        events: "start", "progress", "complete", "error"
        """
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)
    
    def _emit(self, event, *args, **kwargs):
        if event in self.callbacks:
            for cb in self.callbacks[event]:
                cb(*args, **kwargs)
    
    def process_shot(self, shot, process_func):
        """处理单个镜头"""
        self._emit("start", shot)
        try:
            result = process_func(shot)
            shot["status"] = "completed"
            self._emit("complete", shot, result)
            return result
        except Exception as e:
            shot["status"] = "failed"
            shot["error"] = str(e)
            self._emit("error", shot, e)
            return None
    
    def run(self, process_func, resume=False):
        """运行批处理
        process_func: 处理函数,接收 shot dict
        resume: 是否从上次中断处继续
        """
        total = len(self.shot_list.shots)
        
        for i, shot in enumerate(self.shot_list.shots):
            self.current_index = i
            self._emit("progress", i + 1, total, shot)
            
            if resume and shot["status"] == "completed":
                continue  # 跳过已完成的
            
            self.process_shot(shot, process_func)
        
        return self.results
```

### 2.3 镜头处理函数示例

```python
def process_roto_shot(shot):
    """Roto 处理函数示例"""
    # 1. 创建项目
    project = Project()
    
    # 2. 创建 Session
    session = Session()
    project.addItem(session)
    session.activate()
    
    # 3. 导入源素材
    source = Node("Source")
    source.property("path").setValue(shot["source"], 0)
    source.property("startFrame").setValue(shot["start_frame"], 0)
    source.property("endFrame").setValue(shot["end_frame"], 0)
    session.addNode(source)
    
    # 4. 创建 Roto 节点
    roto = Node("RotoShape")
    roto.label = f"ROTO_{shot['id']}"
    session.addNode(roto)
    roto.inputs[0].connect(source.outputs[0])
    
    # 5. 创建输出节点
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(roto.outputs[0])
    output.property("format").setValue("exr", 0)
    output.property("outputPath").setValue(shot["output"], 0)
    
    # 6. 渲染
    render(output, shot["start_frame"], shot["end_frame"])
    
    return {"output": shot["output"], "frames": shot["end_frame"] - shot["start_frame"] + 1}
```

## 3. 自动化工作流

### 3.1 工作流模板

```python
class WorkflowTemplate:
    """工作流模板"""
    
    TEMPLATES = {
        "roto_export": {
            "nodes": ["Source", "RotoShape", "Output"],
            "connections": [(0, 1, 0), (1, 2, 0)]
        },
        "tracked_roto": {
            "nodes": ["Source", "Tracker", "RotoShape", "Output"],
            "connections": [(0, 1, 0), (0, 2, 0), (2, 3, 0)]
        },
        "paint_cleanup": {
            "nodes": ["Source", "Paint", "Output"],
            "connections": [(0, 1, 0), (1, 2, 0)]
        },
        "full_vfx": {
            "nodes": ["Source", "Tracker", "RotoShape", "Paint", "Color", "Composite", "Output"],
            "connections": [(0, 1, 0), (0, 2, 0), (0, 3, 0), (0, 5, 0), (3, 4, 0), (4, 5, 1), (2, 5, 2), (5, 6, 0)]
        }
    }
    
    @classmethod
    def apply(cls, session, source_node, template_name):
        """应用工作流模板"""
        if template_name not in cls.TEMPLATES:
            raise ValueError(f"未知模板: {template_name}")
        
        template = cls.TEMPLATES[template_name]
        nodes = []
        
        # 创建节点
        for i, ntype in enumerate(template["nodes"]):
            if ntype == "Source":
                nodes.append(source_node)
            else:
                n = Node(ntype)
                n.label = f"{ntype}_{i:02d}"
                session.addNode(n)
                nodes.append(n)
        
        # 连接
        for src_idx, tgt_idx, input_idx in template["connections"]:
            nodes[tgt_idx].inputs[input_idx].connect(nodes[src_idx].outputs[0])
        
        return nodes
```

### 3.2 自动化任务链

```python
class TaskChain:
    """任务链:顺序执行多个任务"""
    
    def __init__(self):
        self.tasks = []
    
    def add_task(self, name, func, *args, **kwargs):
        """添加任务"""
        self.tasks.append({
            "name": name,
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "status": "pending"
        })
        return self
    
    def run(self, context=None):
        """运行任务链"""
        results = {}
        
        for task in self.tasks:
            print(f"执行任务: {task['name']}")
            try:
                result = task["func"](*task["args"], **task["kwargs"])
                task["status"] = "completed"
                results[task["name"]] = result
            except Exception as e:
                task["status"] = "failed"
                results[task["name"]] = {"error": str(e)}
                print(f"任务失败: {task['name']} - {e}")
                break  # 失败后停止
        
        return results

# 使用示例
chain = TaskChain()
chain.add_task("import", import_footage, "/path/to/footage")
chain.add_task("track", run_tracking, frame_range=(1, 100))
chain.add_task("roto", create_roto, template="character")
chain.add_task("export", export_matte, "/path/to/output")
results = chain.run()
```

## 4. 错误恢复机制

### 4.1 检查点机制

```python
import pickle

class Checkpoint:
    """检查点:保存处理进度"""
    
    def __init__(self, checkpoint_file):
        self.checkpoint_file = checkpoint_file
    
    def save(self, state):
        """保存状态"""
        with open(self.checkpoint_file, "wb") as f:
            pickle.dump(state, f)
    
    def load(self):
        """加载状态"""
        if not os.path.exists(self.checkpoint_file):
            return None
        with open(self.checkpoint_file, "rb") as f:
            return pickle.load(f)
    
    def clear(self):
        """清除检查点"""
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)

class ResumableProcessor:
    """可恢复的批处理器"""
    
    def __init__(self, shot_list, checkpoint_file="checkpoint.pkl"):
        self.shot_list = shot_list
        self.checkpoint = Checkpoint(checkpoint_file)
    
    def run(self, process_func):
        """运行,支持从检查点恢复"""
        # 尝试加载检查点
        state = self.checkpoint.load()
        if state:
            print(f"从检查点恢复,已完成 {len(state.get('completed', []))} 个镜头")
            self.shot_list.shots = state["shots"]
        
        # 处理待完成的镜头
        for shot in self.shot_list.get_pending():
            try:
                process_func(shot)
                shot["status"] = "completed"
                # 定期保存检查点
                self.checkpoint.save({"shots": self.shot_list.shots})
            except Exception as e:
                shot["status"] = "failed"
                shot["error"] = str(e)
                # 保存状态以便恢复
                self.checkpoint.save({"shots": self.shot_list.shots})
        
        # 完成后清除检查点
        self.checkpoint.clear()
```

### 4.2 重试机制

```python
import time

def retry_with_backoff(func, max_retries=3, initial_delay=1):
    """带退避的重试机制"""
    delay = initial_delay
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            print(f"尝试 {attempt + 1}/{max_retries} 失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2  # 指数退避
    
    raise last_error

# 使用示例
def process_with_retry(shot):
    def _process():
        return process_roto_shot(shot)
    return retry_with_backoff(_process, max_retries=3)
```

### 4.3 错误分类处理

```python
class ErrorHandler:
    """错误分类处理器"""
    
    RECOVERABLE = ["timeout", "memory", "temporary"]
    FATAL = ["license", "corrupt_file", "missing_dependency"]
    
    @classmethod
    def handle(cls, error, shot):
        """处理错误"""
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # 判断错误类型
        if any(k in error_msg for k in cls.RECOVERABLE):
            print(f"可恢复错误: {error}")
            return "retry"
        elif any(k in error_msg for k in cls.FATAL):
            print(f"致命错误: {error}")
            return "abort"
        else:
            print(f"未知错误: {error}")
            return "skip"
```

## 5. 进度监控

### 5.1 进度报告

```python
class ProgressMonitor:
    """进度监控器"""
    
    def __init__(self):
        self.start_time = None
        self.completed = 0
        self.failed = 0
        self.total = 0
    
    def start(self, total):
        """开始监控"""
        import time
        self.start_time = time.time()
        self.total = total
        self.completed = 0
        self.failed = 0
    
    def update(self, shot, success=True):
        """更新进度"""
        if success:
            self.completed += 1
        else:
            self.failed += 1
        
        self._print_progress()
    
    def _print_progress(self):
        """打印进度"""
        import time
        elapsed = time.time() - self.start_time if self.start_time else 0
        processed = self.completed + self.failed
        progress = processed / self.total * 100 if self.total > 0 else 0
        
        if processed > 0:
            eta = (elapsed / processed) * (self.total - processed)
        else:
            eta = 0
        
        print(f"\r进度: {processed}/{self.total} ({progress:.1f}%) "
              f"| 成功: {self.completed} | 失败: {self.failed} "
              f"| 用时: {elapsed:.0f}s | 预计剩余: {eta:.0f}s", end="")
    
    def summary(self):
        """输出摘要"""
        import time
        elapsed = time.time() - self.start_time if self.start_time else 0
        print(f"\n\n=== 批处理完成 ===")
        print(f"总计: {self.total}")
        print(f"成功: {self.completed}")
        print(f"失败: {self.failed}")
        print(f"用时: {elapsed:.1f}s")
        if self.total > 0:
            print(f"平均: {elapsed/self.total:.1f}s/镜头")
```

### 5.2 日志记录

```python
import logging

class BatchLogger:
    """批处理日志记录器"""
    
    def __init__(self, log_file="batch_process.log"):
        self.logger = logging.getLogger("BatchProcessor")
        self.logger.setLevel(logging.DEBUG)
        
        # 文件处理器
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        
        # 控制台处理器
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # 格式
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
    
    def info(self, msg):
        self.logger.info(msg)
    
    def error(self, msg):
        self.logger.error(msg)
    
    def debug(self, msg):
        self.logger.debug(msg)
```

## 6. 批处理脚本模板

### 6.1 完整批处理脚本

```python
#!/usr/bin/env python
"""Silhouette 批处理脚本模板"""

from fx import *
import os
import json
import time

class SilhouetteBatchProcessor:
    """Silhouette 批处理完整实现"""
    
    def __init__(self, config_file):
        self.config = self._load_config(config_file)
        self.logger = self._setup_logger()
        self.progress = ProgressMonitor()
    
    def _load_config(self, config_file):
        """加载配置"""
        with open(config_file, "r") as f:
            return json.load(f)
    
    def _setup_logger(self):
        """设置日志"""
        return BatchLogger(self.config.get("log_file", "batch.log"))
    
    def process_all(self):
        """处理所有镜头"""
        shots = self.config["shots"]
        self.progress.start(len(shots))
        self.logger.info(f"开始批处理,共 {len(shots)} 个镜头")
        
        for shot in shots:
            try:
                self._process_single_shot(shot)
                self.progress.update(shot, success=True)
                self.logger.info(f"镜头 {shot['id']} 处理完成")
            except Exception as e:
                self.progress.update(shot, success=False)
                self.logger.error(f"镜头 {shot['id']} 处理失败: {e}")
        
        self.progress.summary()
    
    def _process_single_shot(self, shot):
        """处理单个镜头"""
        self.logger.debug(f"处理镜头: {shot['id']}")
        
        # 创建项目
        project = Project()
        
        # 创建 Session
        session = Session()
        session.label = shot["id"]
        project.addItem(session)
        session.activate()
        
        # 应用工作流
        source = self._create_source(session, shot)
        nodes = self._apply_workflow(session, source, shot.get("workflow", "roto_export"))
        
        # 渲染输出
        self._render_output(session, shot)
        
        # 保存项目
        project.save(os.path.join(shot["output_dir"], f"{shot['id']}.sfx"))
    
    def _create_source(self, session, shot):
        """创建源节点"""
        source = Node("Source")
        source.property("path").setValue(shot["source"], 0)
        source.property("startFrame").setValue(shot["start_frame"], 0)
        source.property("endFrame").setValue(shot["end_frame"], 0)
        session.addNode(source)
        return source
    
    def _apply_workflow(self, session, source, workflow_name):
        """应用工作流模板"""
        return WorkflowTemplate.apply(session, source, workflow_name)
    
    def _render_output(self, session, shot):
        """渲染输出"""
        # 查找 Output 节点
        output_node = None
        for i in range(session.numNodes):
            if session.node(i).type == "Output":
                output_node = session.node(i)
                break
        
        if output_node:
            output_node.property("outputPath").setValue(
                os.path.join(shot["output_dir"], f"{shot['id']}_####.exr"), 0
            )
            render(output_node, shot["start_frame"], shot["end_frame"])

# 使用
if __name__ == "__main__":
    processor = SilhouetteBatchProcessor("batch_config.json")
    processor.process_all()
```

### 6.2 配置文件示例

```json
{
    "log_file": "batch_process.log",
    "shots": [
        {
            "id": "SHOT_001",
            "source": "/path/to/footage/shot_001.####.exr",
            "start_frame": 1,
            "end_frame": 100,
            "output_dir": "/path/to/output/shot_001",
            "workflow": "tracked_roto"
        },
        {
            "id": "SHOT_002",
            "source": "/path/to/footage/shot_002.####.exr",
            "start_frame": 1,
            "end_frame": 150,
            "output_dir": "/path/to/output/shot_002",
            "workflow": "roto_export"
        }
    ]
}
```

## 7. 并行处理

### 7.1 多进程处理

```python
import multiprocessing

def parallel_process(shots, process_func, max_workers=4):
    """并行处理(概念性,实际受 Silhouette 单实例限制)"""
    # 注意:Silhouette 通常为单实例,实际并行需要多个 Silhouette 进程
    with multiprocessing.Pool(max_workers) as pool:
        results = pool.map(process_func, shots)
    return results
```

### 7.2 命令行并行

```python
import subprocess

def launch_parallel_batches(config_files):
    """启动多个 Silhouette 实例处理不同配置"""
    processes = []
    for config in config_files:
        p = subprocess.Popen([
            "silhouette", "--headless", "--script", "batch.py",
            "--config", config
        ])
        processes.append(p)
    
    # 等待所有完成
    for p in processes:
        p.wait()
    
    return [p.returncode for p in processes]
```

## 8. 最佳实践

### 8.1 批处理设计原则

1. **幂等性**:同一镜头多次处理结果应一致
2. **可恢复**:支持从断点继续
3. **可监控**:实时报告进度
4. **可回滚**:失败时能回退到之前状态
5. **可扩展**:支持添加新任务类型

### 8.2 性能优化

| 优化项 | 建议 |
|--------|------|
| 项目复用 | 相似镜头复用项目模板 |
| 缓存利用 | 静态数据预计算并缓存 |
| 内存管理 | 处理完一个镜头后释放内存 |
| I/O 优化 | 输出目录使用 SSD |
| 网络存储 | 大批量处理避免网络路径 |

### 8.3 错误处理策略

```python
def robust_process(shot, max_retries=3):
    """健壮的处理函数"""
    for attempt in range(max_retries):
        try:
            return process_roto_shot(shot)
        except MemoryError:
            # 内存不足:清理后重试
            clear_memory()
            continue
        except FileNotFoundError as e:
            # 文件缺失:不可恢复
            log_error(f"文件缺失: {e}")
            return None
        except Exception as e:
            # 其他错误:重试
            if attempt < max_retries - 1:
                wait(5 * (attempt + 1))  # 退避
                continue
            log_error(f"处理失败: {e}")
            return None
```

### 8.4 测试与验证

```python
def validate_batch_results(shot_list):
    """验证批处理结果"""
    issues = []
    for shot in shot_list.shots:
        if shot["status"] != "completed":
            issues.append(f"{shot['id']}: 状态异常 ({shot['status']})")
            continue
        
        # 检查输出文件是否存在
        if not os.path.exists(shot["output"]):
            issues.append(f"{shot['id']}: 输出文件不存在")
        
        # 检查帧数是否正确
        expected_frames = shot["end_frame"] - shot["start_frame"] + 1
        # (实际检查文件数量)
    
    return issues
```

---

## 附录:批处理检查清单

| 检查项 | 说明 |
|--------|------|
| □ 镜头列表完整 | 所有镜头都已配置 |
| □ 源文件可访问 | 所有素材路径有效 |
| □ 输出目录可写 | 有写入权限 |
| □ 磁盘空间充足 | 预估输出大小 |
| □ 许可证有效 | Silhouette 许可证可用 |
| □ 检查点机制 | 已配置断点恢复 |
| □ 日志记录 | 日志路径已设置 |
| □ 错误通知 | 失败时有通知机制 |
| □ 测试运行 | 已用小样本测试 |

> **提示**:大规模批处理前,务必用 2-3 个镜头进行小规模测试,确认工作流和参数正确后再全量执行。
