# Silhouette 实战案例-批量处理工作流

> 分类: 实战案例
> 更新日期: 2026-07-11
> 概述: 批量处理多个镜头的自动化案例，涵盖脚本驱动、队列管理与错误恢复

## 目录
---

- [一、案例背景](#一案例背景)
- [二、批处理架构](#二批处理架构)
- [三、镜头清单管理](#三镜头清单管理)
- [四、批处理脚本](#四批处理脚本)
- [五、渲染队列](#五渲染队列)
- [六、错误处理与恢复](#六错误处理与恢复)
- [七、进度监控](#七进度监控)
- [八、总结](#八总结)

---

## 一、案例背景

### 1.1 项目信息

- **项目名称**：电视剧《都市迷踪》第一季
- **镜头数量**：150 个 Roto 镜头
- **单镜头时长**：3-8 秒
- **分辨率**：1920×1080
- **帧率**：25 fps
- **任务**：批量生成角色遮罩
- **周期**：5 天（1 人）

### 1.2 批处理需求

1. **自动化**：减少人工操作
2. **一致性**：所有镜头质量统一
3. **可恢复**：出错后可继续
4. **可监控**：实时掌握进度
5. **可扩展**：支持增加镜头

---

## 二、批处理架构

### 2.1 整体架构

```
镜头清单 CSV
    │
    ▼
[批处理控制器]
    │
    ├─ 读取镜头信息
    │
    ├─ 创建项目
    │
    ├─ 应用模板
    │
    ├─ AI Roto（自动）
    │
    ├─ 渲染输出
    │
    └─ 更新状态
         │
         ▼
    进度报告
```

### 2.2 数据流

```
footage/          ← 原始素材
    │
    ▼
batch_controller  ← 批处理控制器
    │
    ├─ projects/  ← Silhouette 项目
    │
    ├─ output/    ← 渲染输出
    │
    └─ logs/      ← 日志与状态
```

---

## 三、镜头清单管理

### 3.1 镜头清单格式

**shots.csv**：
```csv
shot_name,sequence,shot,footage_path,duration,complexity,priority
SH010,1,10,D:/footage/sh010.mov,3,simple,5
SH020,1,20,D:/footage/sh020.mov,5,medium,4
SH030,1,30,D:/footage/sh030.mov,8,complex,3
...
```

### 3.2 清单管理类

```python
import csv
import os

class ShotListManager:
    """镜头清单管理"""

    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.shots = []
        self.load()

    def load(self):
        """加载镜头清单"""
        with open(self.csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["sequence"] = int(row["sequence"])
                row["shot"] = int(row["shot"])
                row["duration"] = float(row["duration"])
                row["priority"] = int(row["priority"])
                row["status"] = "pending"  # pending/processing/done/error
                self.shots.append(row)

        print(f"加载 {len(self.shots)} 个镜头")

    def get_pending_shots(self):
        """获取待处理镜头"""
        return [s for s in self.shots if s["status"] == "pending"]

    def get_by_complexity(self, complexity):
        """按复杂度筛选"""
        return [s for s in self.shots if s["complexity"] == complexity]

    def sort_by_priority(self):
        """按优先级排序"""
        self.shots.sort(key=lambda x: x["priority"], reverse=True)

    def update_status(self, shot_name, status):
        """更新镜头状态"""
        for shot in self.shots:
            if shot["shot_name"] == shot_name:
                shot["status"] = status
                break

    def generate_report(self):
        """生成进度报告"""
        status_count = {}
        for shot in self.shots:
            status_count[shot["status"]] = status_count.get(shot["status"], 0) + 1

        return {
            "total": len(self.shots),
            "status": status_count,
            "progress": status_count.get("done", 0) / len(self.shots) * 100
        }

# 使用
manager = ShotListManager("D:/project/shots.csv")
manager.sort_by_priority()
print(f"待处理: {len(manager.get_pending_shots())}")
```

---

## 四、批处理脚本

### 4.1 批处理控制器

```python
from fx import *
import os
import time
import logging

class BatchProcessor:
    """批处理控制器"""

    def __init__(self, shot_list, output_dir):
        self.shot_list = shot_list
        self.output_dir = output_dir
        self.logger = self._setup_logger()
        self.processed = 0
        self.errors = 0

    def _setup_logger(self):
        """配置日志"""
        logger = logging.getLogger("batch")
        logger.setLevel(logging.INFO)

        log_dir = os.path.join(self.output_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)

        fh = logging.FileHandler(
            os.path.join(log_dir, f"batch_{int(time.time())}.log"),
            encoding="utf-8"
        )
        fh.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        return logger

    def process_all(self):
        """处理所有镜头"""
        self.logger.info(f"开始批处理，共 {len(self.shot_list.shots)} 个镜头")

        for shot in self.shot_list.shots:
            if shot["status"] == "done":
                continue

            try:
                self.logger.info(f"处理 {shot['shot_name']}")
                self.shot_list.update_status(shot["shot_name"], "processing")

                self._process_shot(shot)

                self.shot_list.update_status(shot["shot_name"], "done")
                self.processed += 1
                self.logger.info(f"完成 {shot['shot_name']} ({self.processed}/{len(self.shot_list.shots)})")

            except Exception as e:
                self.shot_list.update_status(shot["shot_name"], "error")
                self.errors += 1
                self.logger.error(f"失败 {shot['shot_name']}: {e}")

        self.logger.info(f"批处理完成: 成功 {self.processed}, 失败 {self.errors}")

    def _process_shot(self, shot):
        """处理单个镜头"""
        # 创建项目
        proj = Project()
        activate(proj)
        session = Session()
        session.label = shot["shot_name"]
        activate(session)
        proj.addItem(session)

        # 加载素材
        src = Node("SourceNode")
        src.property("mediaPath").setValue(shot["footage_path"].replace("\\", "/"), 0)
        src.property("frameRate").setValue(25.0, 0)
        session.addNode(src)

        # 根据复杂度选择处理方式
        if shot["complexity"] == "simple":
            self._process_simple(session, src, shot)
        elif shot["complexity"] == "medium":
            self._process_medium(session, src, shot)
        else:
            self._process_complex(session, src, shot)

        # 渲染输出
        self._render_output(session, shot)

        # 保存项目
        proj_path = os.path.join(self.output_dir, "projects", f"{shot['shot_name']}.sfx")
        os.makedirs(os.path.dirname(proj_path), exist_ok=True)
        proj.save(proj_path)

        # 清理
        proj.clear()

        import gc
        gc.collect()

    def _process_simple(self, session, src, shot):
        """简单镜头：AI 自动处理"""
        try:
            from fx.ai import AIRoto
            ai = AIRoto()
            ai.setSource(src)
            ai.setMode("fast")  # 快速模式
            ai.process(frameRange=[1, int(shot["duration"] * 25)])
            self.logger.info(f"  AI Roto 完成: {shot['shot_name']}")
        except Exception as e:
            self.logger.warning(f"  AI 不可用，使用基础 Roto: {e}")
            roto = Node("RotoNode")
            session.addNode(roto)
            src.outputs[0].connect(roto.inputs[1])

    def _process_medium(self, session, src, shot):
        """中等镜头：AI + 模板"""
        self._process_simple(session, src, shot)

        # 添加运动模糊
        roto = session.node("RotoNode") if session.numNodes > 1 else None
        if roto:
            roto.property("motionBlur").setValue(True, 0)
            roto.property("motionBlurAmount").setValue(1.0, 0)

    def _process_complex(self, session, src, shot):
        """复杂镜头：AI + 手动"""
        self._process_medium(session, src, shot)

        # 创建分层 Roto
        # 实际中需要手动干预
        self.logger.info(f"  复杂镜头需手动检查: {shot['shot_name']}")

    def _render_output(self, session, shot):
        """渲染输出"""
        output_path = os.path.join(
            self.output_dir,
            "output",
            shot["shot_name"],
            f"{shot['shot_name']}_roto_v001.####.exr"
        ).replace("\\", "/")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        out = Node("OutputNode")
        out.property("path").setValue(output_path, 0)
        out.property("format").setValue("exr", 0)
        out.property("compression").setValue("ZIP", 0)
        out.property("startFrame").setValue(1, 0)
        out.property("endFrame").setValue(int(shot["duration"] * 25), 0)
        session.addNode(out)

        # 连接最后一个 Roto 节点
        for i in range(session.numNodes - 1, -1, -1):
            node = session.node(i)
            if node.type == "RotoNode":
                node.outputs[0].connect(out.inputs[0])
                break

        # 渲染
        session.render()
        self.logger.info(f"  渲染完成: {output_path}")

# 使用
processor = BatchProcessor(manager, "D:/project/batch")
processor.process_all()
```

---

## 五、渲染队列

### 5.1 渲染队列管理

```python
from fx import *
import os
import time
import threading

class RenderQueue:
    """渲染队列"""

    def __init__(self, max_workers=1):
        self.queue = []
        self.max_workers = max_workers
        self.completed = []
        self.failed = []

    def add_task(self, session, output_path, frame_range):
        """添加渲染任务"""
        task = {
            "session": session,
            "output_path": output_path,
            "frame_range": frame_range,
            "status": "pending",
            "added_time": time.time()
        }
        self.queue.append(task)

    def process(self):
        """处理队列"""
        for task in self.queue:
            if task["status"] != "pending":
                continue

            task["status"] = "processing"
            task["start_time"] = time.time()

            try:
                self._render(task)
                task["status"] = "done"
                task["end_time"] = time.time()
                self.completed.append(task)
            except Exception as e:
                task["status"] = "error"
                task["error"] = str(e)
                self.failed.append(task)

    def _render(self, task):
        """执行单个渲染任务"""
        session = task["session"]

        # 设置输出
        out = Node("OutputNode")
        out.property("path").setValue(task["output_path"], 0)
        out.property("format").setValue("exr", 0)
        out.property("startFrame").setValue(task["frame_range"][0], 0)
        out.property("endFrame").setValue(task["frame_range"][1], 0)
        session.addNode(out)

        # 执行渲染
        session.render()

    def get_progress(self):
        """获取进度"""
        total = len(self.queue)
        done = len(self.completed)
        failed = len(self.failed)
        return {
            "total": total,
            "done": done,
            "failed": failed,
            "progress": done / total * 100 if total > 0 else 0
        }
```

### 5.2 后台渲染（2026 新功能）

```python
from fx.render import RenderQueue, RenderTask

def background_render(shots, output_dir):
    """使用 2026 后台渲染队列"""
    queue = RenderQueue()

    for shot in shots:
        # 加载项目
        proj = Project()
        proj.load(f"projects/{shot}.sfx")
        session = proj.item(0)

        # 创建渲染任务
        task = RenderTask(
            session=session,
            output=f"{output_dir}/{shot}_v001.####.exr",
            frameRange=[1, 100]
        )
        queue.addTask(task)

    # 后台启动
    queue.start(background=True)

    # 监控进度
    while queue.isRunning():
        progress = queue.getProgress()
        print(f"进度: {progress['completed']}/{progress['total']}")
        time.sleep(10)

    print("渲染队列完成")
```

---

## 六、错误处理与恢复

### 6.1 错误处理策略

```python
class BatchErrorHandler:
    """批处理错误处理"""

    def __init__(self, processor):
        self.processor = processor
        self.retry_count = {}

    def handle_error(self, shot, error):
        """处理错误"""
        shot_name = shot["shot_name"]
        self.retry_count[shot_name] = self.retry_count.get(shot_name, 0) + 1

        # 重试策略
        if self.retry_count[shot_name] <= 3:
            print(f"重试 {shot_name} (第 {self.retry_count[shot_name]} 次)")
            self.processor.shot_list.update_status(shot_name, "pending")
            return "retry"
        else:
            print(f"放弃 {shot_name}，记录错误")
            self.processor.shot_list.update_status(shot_name, "failed")
            self._log_error(shot, error)
            return "failed"

    def _log_error(self, shot, error):
        """记录错误"""
        import json
        error_log = {
            "shot": shot["shot_name"],
            "error": str(error),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "retry_count": self.retry_count[shot["shot_name"]]
        }

        error_path = os.path.join(
            self.processor.output_dir,
            "logs",
            "errors.json"
        )

        errors = []
        if os.path.exists(error_path):
            with open(error_path) as f:
                errors = json.load(f)

        errors.append(error_log)

        with open(error_path, "w") as f:
            json.dump(errors, f, indent=2, ensure_ascii=False)
```

### 6.2 检查点与恢复

```python
class CheckpointManager:
    """检查点管理"""

    def __init__(self, checkpoint_file):
        self.checkpoint_file = checkpoint_file

    def save(self, shot_list):
        """保存检查点"""
        import json
        state = {
            "shots": [
                {
                    "shot_name": s["shot_name"],
                    "status": s["status"]
                }
                for s in shot_list.shots
            ],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        print(f"检查点已保存: {self.checkpoint_file}")

    def load(self, shot_list):
        """从检查点恢复"""
        import json

        if not os.path.exists(self.checkpoint_file):
            print("无检查点")
            return

        with open(self.checkpoint_file, encoding="utf-8") as f:
            state = json.load(f)

        for saved_shot in state["shots"]:
            for shot in shot_list.shots:
                if shot["shot_name"] == saved_shot["shot_name"]:
                    shot["status"] = saved_shot["status"]
                    break

        print(f"从检查点恢复: {state['timestamp']}")

# 使用
checkpoint = CheckpointManager("D:/project/batch/checkpoint.json")
checkpoint.load(manager)
# ... 处理 ...
checkpoint.save(manager)
```

---

## 七、进度监控

### 7.1 实时进度报告

```python
import time

class ProgressMonitor:
    """进度监控"""

    def __init__(self, shot_list):
        self.shot_list = shot_list
        self.start_time = time.time()

    def report(self):
        """生成报告"""
        report = self.shot_list.generate_report()
        elapsed = time.time() - self.start_time

        done = report["status"].get("done", 0)
        total = report["total"]

        if done > 0:
            avg_time = elapsed / done
            remaining = (total - done) * avg_time
        else:
            avg_time = 0
            remaining = 0

        print(f"\n=== 批处理进度 ===")
        print(f"总计: {total}")
        print(f"完成: {done}")
        print(f"处理中: {report['status'].get('processing', 0)}")
        print(f"错误: {report['status'].get('error", 0)}")
        print(f"进度: {report['progress']:.1f}%")
        print(f"已用时: {elapsed/60:.1f} 分钟")
        print(f"预计剩余: {remaining/60:.1f} 分钟")
        print(f"平均每镜头: {avg_time/60:.1f} 分钟")

# 使用
monitor = ProgressMonitor(manager)
# 定期报告
while True:
    monitor.report()
    time.sleep(300)  # 每5分钟报告
```

### 7.2 状态文件

```python
def write_status_file(shot_list, output_dir):
    """写入状态文件供外部监控"""
    import json
    import os

    status = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(shot_list.shots),
        "by_status": {},
        "shots": []
    }

    for shot in shot_list.shots:
        status["by_status"][shot["status"]] = status["by_status"].get(shot["status"], 0) + 1
        status["shots"].append({
            "name": shot["shot_name"],
            "status": shot["status"]
        })

    status_path = os.path.join(output_dir, "status.json")
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
```

---

## 八、总结

### 8.1 效率提升

| 方法 | 节省时间 | 实施难度 |
|------|---------|---------|
| AI 自动 Roto | 60% | 低 |
| 脚本批处理 | 40% | 中 |
| 渲染队列 | 30% | 中 |
| 检查点恢复 | 20% | 低 |

**综合效率提升**：约 70-80%

### 8.2 关键经验

1. **分层处理**：按复杂度分级处理
2. **检查点**：定期保存避免重做
3. **错误恢复**：自动重试机制
4. **进度监控**：实时掌握状态
5. **资源管理**：及时清理内存

### 8.3 适用场景

- 大量相似镜头的 Roto（>20 个）
- 广告系列项目
- 电视剧批量镜头
- 标准化工作流

---

> 相关文档：
> - [[Silhouette 实战案例-人物抠像全流程]]
> - [[Silhouette 项目管理最佳实践]]
> - [[Silhouette 脚本调试与错误处理]]
