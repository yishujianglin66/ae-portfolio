# Silhouette 渲染队列与批量输出

> 分类: 自动化与批处理
> 更新日期: 2026-07-11
> 概述: 渲染队列管理、优先级控制、并行渲染、输出监控完整说明。

## 目录
1. [渲染队列概述](#1-渲染队列概述)
2. [队列管理](#2-队列管理)
3. [优先级控制](#3-优先级控制)
4. [并行渲染](#4-并行渲染)
5. [输出监控](#5-输出监控)
6. [队列脚本化](#6-队列脚本化)
7. [渲染农场集成](#7-渲染农场集成)
8. [最佳实践](#8-最佳实践)

---

## 1. 渲染队列概述

### 1.1 什么是渲染队列

渲染队列(Render Queue)是管理多个渲染任务的系统,负责任务调度、资源分配、进度监控和结果收集。

### 1.2 队列核心功能

| 功能 | 说明 |
|------|------|
| 任务排队 | 多个渲染任务按序执行 |
| 优先级 | 高优先级任务优先执行 |
| 并行渲染 | 多任务同时执行(多 CPU/GPU) |
| 暂停/恢复 | 可暂停当前渲染,稍后恢复 |
| 失败重试 | 渲染失败自动重试 |
| 进度监控 | 实时显示渲染进度 |
| 输出验证 | 渲染完成后验证输出 |

### 1.3 队列架构

```
[任务提交] → [任务队列] → [调度器] → [渲染引擎] → [输出存储]
                ↓             ↓           ↓
            [优先级管理]  [资源分配]  [进度监控]
                                         ↓
                                    [结果验证]
```

## 2. 队列管理

### 2.1 任务结构

```python
class RenderTask:
    """渲染任务"""
    
    def __init__(self, task_id, project_path, session_name, 
                 frame_range, output_path, priority=0):
        self.task_id = task_id
        self.project_path = project_path
        self.session_name = session_name
        self.frame_range = frame_range  # (start, end)
        self.output_path = output_path
        self.priority = priority
        self.status = "pending"  # pending, running, completed, failed, cancelled
        self.progress = 0.0  # 0-1
        self.start_time = None
        self.end_time = None
        self.error = None
        self.retry_count = 0
        self.max_retries = 3
    
    def to_dict(self):
        return {
            "task_id": self.task_id,
            "project_path": self.project_path,
            "session_name": self.session_name,
            "frame_range": self.frame_range,
            "output_path": self.output_path,
            "priority": self.priority,
            "status": self.status,
            "progress": self.progress,
            "error": self.error,
            "retry_count": self.retry_count
        }
```

### 2.2 队列实现

```python
import heapq
import time

class RenderQueue:
    """渲染队列"""
    
    def __init__(self):
        self.queue = []  # 优先级队列
        self.running = {}  # 正在运行的任务
        self.completed = []  # 已完成
        self.failed = []  # 失败
        self.task_counter = 0
    
    def submit(self, project_path, session_name, frame_range, 
               output_path, priority=0):
        """提交渲染任务"""
        task_id = f"TASK_{self.task_counter:04d}"
        self.task_counter += 1
        
        task = RenderTask(
            task_id, project_path, session_name,
            frame_range, output_path, priority
        )
        
        # 使用负优先级,因为 heapq 是最小堆
        heapq.heappush(self.queue, (-priority, task_id, task))
        
        return task_id
    
    def get_next(self):
        """获取下一个任务"""
        while self.queue:
            _, _, task = heapq.heappop(self.queue)
            if task.status == "pending":
                return task
        return None
    
    def update_status(self, task_id, status, progress=None, error=None):
        """更新任务状态"""
        # 查找任务
        for task in list(self.running.values()) + self.completed + self.failed:
            if task.task_id == task_id:
                task.status = status
                if progress is not None:
                    task.progress = progress
                if error:
                    task.error = error
                if status == "completed":
                    task.end_time = time.time()
                    if task not in self.completed:
                        self.completed.append(task)
                    self.running.pop(task_id, None)
                elif status == "failed":
                    task.end_time = time.time()
                    if task not in self.failed:
                        self.failed.append(task)
                    self.running.pop(task_id, None)
                break
    
    def get_stats(self):
        """获取队列统计"""
        return {
            "pending": len(self.queue),
            "running": len(self.running),
            "completed": len(self.completed),
            "failed": len(self.failed)
        }
```

### 2.3 任务取消

```python
def cancel_task(self, task_id):
    """取消任务"""
    # 从队列中移除
    for i, (_, _, task) in enumerate(self.queue):
        if task.task_id == task_id:
            task.status = "cancelled"
            self.queue.pop(i)
            heapq.heapify(self.queue)
            return True
    
    # 如果正在运行,标记为取消(实际终止需要渲染器支持)
    if task_id in self.running:
        self.running[task_id].status = "cancelled"
        return True
    
    return False
```

## 3. 优先级控制

### 3.1 优先级策略

| 优先级 | 数值 | 说明 |
|--------|------|------|
| 紧急 | 100 | 必须立即执行 |
| 高 | 50 | 优先执行 |
| 普通 | 0 | 默认优先级 |
| 低 | -50 | 空闲时执行 |
| 后台 | -100 | 最低优先级 |

### 3.2 优先级调整

```python
def set_priority(self, task_id, priority):
    """调整任务优先级"""
    # 从队列中找到任务
    for i, (_, _, task) in enumerate(self.queue):
        if task.task_id == task_id:
            task.priority = priority
            # 重新堆化
            self.queue[i] = (-priority, task_id, task)
            heapq.heapify(self.queue)
            return True
    return False
```

### 3.3 优先级抢占

```python
def preempt_for_urgent(self, urgent_task):
    """为紧急任务抢占资源"""
    # 暂停当前最低优先级的运行任务
    if self.running:
        # 找到优先级最低的运行任务
        lowest = min(self.running.values(), key=lambda t: t.priority)
        
        # 暂停(实际实现需要渲染器支持)
        lowest.status = "paused"
        
        # 重新加入队列
        heapq.heappush(self.queue, (-lowest.priority, lowest.task_id, lowest))
        self.running.pop(lowest.task_id)
        
        # 执行紧急任务
        urgent_task.status = "running"
        self.running[urgent_task.task_id] = urgent_task
        
        return lowest.task_id
    return None
```

## 4. 并行渲染

### 4.1 多任务并行

```python
import threading

class ParallelRenderer:
    """并行渲染器"""
    
    def __init__(self, max_workers=4):
        self.max_workers = max_workers
        self.workers = []
        self.queue = RenderQueue()
        self.lock = threading.Lock()
    
    def start(self):
        """启动工作线程"""
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, args=(i,))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
    
    def _worker_loop(self, worker_id):
        """工作线程循环"""
        while True:
            with self.lock:
                task = self.queue.get_next()
                if not task:
                    time.sleep(1)
                    continue
                
                task.status = "running"
                task.start_time = time.time()
                self.queue.running[task.task_id] = task
            
            # 执行渲染
            try:
                self._render_task(task, worker_id)
                with self.lock:
                    self.queue.update_status(task.task_id, "completed")
            except Exception as e:
                with self.lock:
                    self.queue.update_status(task.task_id, "failed", error=str(e))
    
    def _render_task(self, task, worker_id):
        """执行渲染任务"""
        print(f"[Worker {worker_id}] 渲染任务: {task.task_id}")
        
        # 模拟渲染进度
        total_frames = task.frame_range[1] - task.frame_range[0] + 1
        for frame in range(task.frame_range[0], task.frame_range[1] + 1):
            # 渲染单帧
            self._render_frame(task, frame)
            
            # 更新进度
            progress = (frame - task.frame_range[0] + 1) / total_frames
            with self.lock:
                self.queue.update_status(task.task_id, "running", progress=progress)
    
    def _render_frame(self, task, frame):
        """渲染单帧"""
        # 实际渲染调用
        # render_frame(task.project_path, task.session_name, frame, task.output_path)
        time.sleep(0.1)  # 模拟渲染时间
```

### 4.2 帧分割并行

```python
def split_frame_range(start, end, num_chunks):
    """将帧范围分割为多个块"""
    total = end - start + 1
    chunk_size = total // num_chunks
    ranges = []
    
    for i in range(num_chunks):
        chunk_start = start + i * chunk_size
        chunk_end = chunk_start + chunk_size - 1 if i < num_chunks - 1 else end
        ranges.append((chunk_start, chunk_end))
    
    return ranges

# 示例:将 1-100 帧分为 4 块
# [(1, 25), (26, 50), (51, 75), (76, 100)]
```

### 4.3 资源管理

```python
class ResourceManager:
    """资源管理器"""
    
    def __init__(self, max_cpu=8, max_gpu=1, max_memory=32):
        self.max_cpu = max_cpu
        self.max_gpu = max_gpu
        self.max_memory = max_memory  # GB
        self.used_cpu = 0
        self.used_gpu = 0
        self.used_memory = 0
    
    def allocate(self, cpu=1, gpu=0, memory=4):
        """分配资源"""
        if (self.used_cpu + cpu <= self.max_cpu and
            self.used_gpu + gpu <= self.max_gpu and
            self.used_memory + memory <= self.max_memory):
            self.used_cpu += cpu
            self.used_gpu += gpu
            self.used_memory += memory
            return True
        return False
    
    def release(self, cpu=1, gpu=0, memory=4):
        """释放资源"""
        self.used_cpu = max(0, self.used_cpu - cpu)
        self.used_gpu = max(0, self.used_gpu - gpu)
        self.used_memory = max(0, self.used_memory - memory)
    
    def get_available(self):
        """获取可用资源"""
        return {
            "cpu": self.max_cpu - self.used_cpu,
            "gpu": self.max_gpu - self.used_gpu,
            "memory": self.max_memory - self.used_memory
        }
```

## 5. 输出监控

### 5.1 进度监控

```python
class RenderMonitor:
    """渲染监控器"""
    
    def __init__(self, queue):
        self.queue = queue
    
    def get_progress(self, task_id):
        """获取任务进度"""
        for task in list(self.queue.running.values()) + self.queue.completed + self.queue.failed:
            if task.task_id == task_id:
                return {
                    "task_id": task.task_id,
                    "status": task.status,
                    "progress": task.progress,
                    "start_time": task.start_time,
                    "end_time": task.end_time,
                    "error": task.error
                }
        return None
    
    def get_all_progress(self):
        """获取所有任务进度"""
        return [self.get_progress(t.task_id) for t in 
                list(self.queue.running.values()) + 
                [item[2] for item in self.queue.queue] +
                self.queue.completed + self.queue.failed]
    
    def estimate_time(self, task_id):
        """估算剩余时间"""
        task_info = self.get_progress(task_id)
        if not task_info or task_info["progress"] <= 0:
            return None
        
        elapsed = task_info["end_time"] - task_info["start_time"] if task_info["end_time"] \
                  else time.time() - task_info["start_time"]
        
        if task_info["progress"] <= 0:
            return None
        
        total_estimated = elapsed / task_info["progress"]
        remaining = total_estimated - elapsed
        return remaining
```

### 5.2 输出验证

```python
import os

class OutputValidator:
    """输出验证器"""
    
    @staticmethod
    def validate_output(task):
        """验证渲染输出"""
        issues = []
        
        # 检查输出路径是否存在
        if not os.path.exists(task.output_path):
            issues.append(f"输出路径不存在: {task.output_path}")
            return issues
        
        # 检查帧数是否正确
        expected_frames = task.frame_range[1] - task.frame_range[0] + 1
        actual_files = []
        
        for filename in os.listdir(task.output_path):
            if filename.endswith((".exr", ".png", ".tif", ".dpx")):
                actual_files.append(filename)
        
        if len(actual_files) != expected_frames:
            issues.append(f"帧数不匹配: 期望 {expected_frames}, 实际 {len(actual_files)}")
        
        # 检查缺失的帧
        expected_frame_nums = set(range(task.frame_range[0], task.frame_range[1] + 1))
        actual_frame_nums = set()
        
        for filename in actual_files:
            # 从文件名提取帧号
            import re
            match = re.search(r'(\d+)', filename)
            if match:
                actual_frame_nums.add(int(match.group(1)))
        
        missing = expected_frame_nums - actual_frame_nums
        if missing:
            issues.append(f"缺失帧: {sorted(missing)}")
        
        return issues
    
    @staticmethod
    def get_file_size(output_path):
        """获取输出文件总大小"""
        total = 0
        for dirpath, dirnames, filenames in os.walk(output_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total += os.path.getsize(fp)
        return total
```

### 5.3 通知系统

```python
class NotificationSystem:
    """通知系统"""
    
    def __init__(self):
        self.callbacks = {
            "task_completed": [],
            "task_failed": [],
            "queue_empty": []
        }
    
    def register(self, event, callback):
        """注册回调"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    def notify(self, event, *args, **kwargs):
        """发送通知"""
        if event in self.callbacks:
            for cb in self.callbacks[event]:
                cb(*args, **kwargs)

# 邮件通知示例
def email_notification(task):
    """邮件通知"""
    import smtplib
    # 发送邮件逻辑
    print(f"邮件通知: 任务 {task.task_id} 完成")

# Webhook 通知
def webhook_notification(task):
    """Webhook 通知"""
    import requests
    requests.post("http://monitor/api/notify", json={
        "task_id": task.task_id,
        "status": task.status
    })
```

## 6. 队列脚本化

### 6.1 完整队列管理脚本

```python
#!/usr/bin/env python
"""Silhouette 渲染队列管理"""

from fx import *
import time
import threading

class SilhouetteRenderQueue:
    """Silhouette 渲染队列"""
    
    def __init__(self, max_workers=2):
        self.queue = RenderQueue()
        self.renderer = ParallelRenderer(max_workers)
        self.monitor = RenderMonitor(self.queue)
        self.validator = OutputValidator()
        self.notifications = NotificationSystem()
    
    def start(self):
        """启动队列"""
        self.renderer.start()
        print("渲染队列已启动")
    
    def submit_render(self, project_path, session_name, frame_range, 
                      output_path, priority=0):
        """提交渲染任务"""
        task_id = self.queue.submit(
            project_path, session_name, frame_range,
            output_path, priority
        )
        print(f"任务已提交: {task_id}")
        return task_id
    
    def wait_for_completion(self, timeout=None):
        """等待所有任务完成"""
        start = time.time()
        while True:
            stats = self.queue.get_stats()
            if stats["pending"] == 0 and stats["running"] == 0:
                break
            
            if timeout and time.time() - start > timeout:
                print("等待超时")
                return False
            
            time.sleep(5)
        
        return True
    
    def get_status(self):
        """获取队列状态"""
        stats = self.queue.get_stats()
        return {
            "pending": stats["pending"],
            "running": stats["running"],
            "completed": stats["completed"],
            "failed": stats["failed"],
            "tasks": self.monitor.get_all_progress()
        }

# 使用示例
queue = SilhouetteRenderQueue(max_workers=4)
queue.start()

# 提交多个任务
queue.submit_render("/proj/shot1.sfx", "Main", (1, 100), "/out/shot1/", priority=10)
queue.submit_render("/proj/shot2.sfx", "Main", (1, 150), "/out/shot2/", priority=5)
queue.submit_render("/proj/shot3.sfx", "Main", (1, 80), "/out/shot3/", priority=0)

# 等待完成
queue.wait_for_completion()

# 获取状态
status = queue.get_status()
print(f"完成: {status['completed']}, 失败: {status['failed']}")
```

## 7. 渲染农场集成

### 7.1 Deadline 集成

```python
class DeadlineIntegration:
    """Deadline 渲染农场集成"""
    
    def __init__(self, deadline_command="deadlinecommand"):
        self.deadline_command = deadline_command
    
    def submit_job(self, task):
        """提交到 Deadline"""
        import subprocess
        cmd = [
            self.deadline_command,
            "-SubmitCommandLineJob",
            f"-executable silhouette",
            f"-arguments \"--headless --script render.py --project {task.project_path} --frames {task.frame_range[0]}-{task.frame_range[1]} --output {task.output_path}\"",
            f"-name {task.task_id}",
            f"-priority {task.priority}",
            "-pool silhouettes",
            "-group render"
        ]
        result = subprocess.run(" ".join(cmd), capture_output=True, text=True)
        return result.returncode == 0
```

### 7.2 Tractor 集成

```python
class TractorIntegration:
    """Tractor 渲染农场集成"""
    
    def __init__(self, tractor_engine="tractor:80"):
        self.tractor_engine = tractor_engine
    
    def submit_job(self, task):
        """提交到 Tractor"""
        # 构建 Tractor 脚本
        tractor_script = f"""
        Job {{
            Title "{task.task_id}"
            Priority {task.priority}
            Service "Silhouette"
            
            Task {{
                Name "Render {task.frame_range[0]}-{task.frame_range[1]}"
                Command "silhouette --headless --script render.py --project {task.project_path} --frames {task.frame_range[0]}-{task.frame_range[1]} --output {task.output_path}"
            }}
        }}
        """
        # 提交(实际使用 tractor-spool)
        return tractor_script
```

## 8. 最佳实践

### 8.1 队列配置建议

| 场景 | max_workers | 说明 |
|------|-------------|------|
| 工作站 | 2-4 | 与其他工作并行 |
| 渲染节点 | 8-16 | 最大化利用 |
| 渲染农场 | 1(每实例) | 多实例并行 |

### 8.2 任务分割策略

```python
# 短任务(< 100帧):不分割
# 中等任务(100-500帧):分割为 2-4 块
# 长任务(> 500帧):分割为 4-8 块

def auto_split_task(task, max_workers=4):
    """自动分割任务"""
    total_frames = task.frame_range[1] - task.frame_range[0] + 1
    
    if total_frames < 100:
        return [task]  # 不分割
    
    num_chunks = min(max_workers, total_frames // 100)
    ranges = split_frame_range(task.frame_range[0], task.frame_range[1], num_chunks)
    
    sub_tasks = []
    for i, (start, end) in enumerate(ranges):
        sub_task = RenderTask(
            f"{task.task_id}_SUB{i}",
            task.project_path,
            task.session_name,
            (start, end),
            f"{task.output_path}/chunk_{i}",
            task.priority
        )
        sub_tasks.append(sub_task)
    
    return sub_tasks
```

### 8.3 错误恢复

```python
def retry_failed_tasks(queue, max_retries=3):
    """重试失败的任务"""
    for task in queue.failed[:]:  # 副本,避免修改时迭代
        if task.retry_count < max_retries:
            task.retry_count += 1
            task.status = "pending"
            task.error = None
            
            # 重新加入队列
            heapq.heappush(queue.queue, (-task.priority, task.task_id, task))
            queue.failed.remove(task)
            
            print(f"重试任务: {task.task_id} (第 {task.retry_count} 次)")
```

### 8.4 日志与报告

```python
def generate_report(queue):
    """生成渲染报告"""
    report = {
        "summary": queue.get_stats(),
        "tasks": []
    }
    
    for task in queue.completed:
        report["tasks"].append({
            "task_id": task.task_id,
            "status": "completed",
            "duration": task.end_time - task.start_time if task.end_time and task.start_time else None,
            "frames": task.frame_range[1] - task.frame_range[0] + 1
        })
    
    for task in queue.failed:
        report["tasks"].append({
            "task_id": task.task_id,
            "status": "failed",
            "error": task.error,
            "retries": task.retry_count
        })
    
    return report
```

---

## 附录:队列状态速查

| 状态 | 说明 | 可执行操作 |
|------|------|-----------|
| pending | 等待中 | 取消、调整优先级 |
| running | 渲染中 | 监控进度 |
| completed | 已完成 | 验证输出 |
| failed | 失败 | 重试、查看错误 |
| cancelled | 已取消 | 重新提交 |
| paused | 已暂停 | 恢复 |

> **提示**:大规模渲染时,先用小帧范围测试单个任务,确认输出正确后再全量提交,避免浪费渲染资源。
