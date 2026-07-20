# Silhouette 脚本调试与错误处理

> 分类: 故障排查
> 更新日期: 2026-07-11
> 概述: 系统讲解 Silhouette 脚本常见错误、调试技巧、异常处理与日志分析方法

## 目录
---

- [一、脚本开发环境](#一脚本开发环境)
- [二、常见脚本错误](#二常见脚本错误)
- [三、调试技巧](#三调试技巧)
- [四、异常处理](#四异常处理)
- [五、日志系统](#五日志系统)
- [六、性能分析](#六性能分析)
- [七、最佳实践](#七最佳实践)

---

## 一、脚本开发环境

### 1.1 Silhouette 脚本编辑器

Silhouette 内置 Python 脚本编辑器，位于 `Window → Script Editor`（F5）。

**功能**：
- 语法高亮
- 自动补全
- 即时执行
- 输出窗口
- 断点调试（2026 新功能）

### 1.2 外部 IDE 集成

**VS Code 集成**：

1. 安装 Python 扩展
2. 配置 `settings.json`：
```json
{
  "python.pythonPath": "C:\\Program Files\\Boris FX\\Silhouette 2026\\python.exe",
  "python.autoComplete.extraPaths": [
    "C:\\Program Files\\Boris FX\\Silhouette 2026\\python\\Lib"
  ]
}
```

3. 创建 `silhouette_stubs.py` 用于自动补全：
```python
# 类型提示存根
from typing import Any, List, Optional

class Project:
    def __init__(self): ...
    def activate(self) -> None: ...
    def addItem(self, item: Any) -> None: ...
    @property
    def numItems(self) -> int: ...

class Session:
    def __init__(self): ...
    def addNode(self, node: Any) -> None: ...
    @property
    def numNodes(self) -> int: ...
```

### 1.3 脚本目录结构

**推荐的项目脚本结构**：

```
scripts/
├── lib/                    # 通用库
│   ├── __init__.py
│   ├── silhouette_utils.py # 工具函数
│   ├── node_helpers.py     # 节点操作
│   └── io_helpers.py       # IO 操作
├── shots/                  # 镜头脚本
│   ├── sh010_roto.py
│   └── sh020_paint.py
├── batch/                  # 批处理脚本
│   └── batch_render.py
└── tools/                  # 工具脚本
    ├── qc_check.py
    └── export.py
```

---

## 二、常见脚本错误

### 2.1 导入错误

**错误**：
```python
ImportError: No module named 'fx'
```

**原因**：脚本在 Silhouette 环境外运行。

**解决**：
```python
# 检查运行环境
try:
    from fx import *
except ImportError:
    print("此脚本必须在 Silhouette 内运行")
    sys.exit(1)
```

### 2.2 属性访问错误

**错误**：
```python
AttributeError: 'Node' object has no attribute 'property'
```

或：
```python
KeyError: 'alpha.blur'
```

**原因**：属性名错误或节点类型不匹配。

**解决**：
```python
from fx import *

node = session.node("RotoNode")

# 安全的属性访问
def safe_get_property(node, name, default=None):
    """安全获取节点属性"""
    try:
        if name in node.properties:
            return node.property(name)
        return default
    except Exception as e:
        print(f"获取属性 {name} 失败: {e}")
        return default

# 使用
blur = safe_get_property(node, "alpha.blur")
if blur:
    blur.setValue(0.5, 0)
else:
    print(f"属性 alpha.blur 不存在，可用属性: {node.properties}")
```

### 2.3 节点连接错误

**错误**：
```python
IndexError: Port index out of range
```

**解决**：
```python
from fx import *

def safe_connect(src_node, src_port_idx, dst_node, dst_port_idx):
    """安全的节点连接"""
    try:
        # 检查端口是否存在
        if src_port_idx >= len(src_node.outputs):
            print(f"源节点 {src_node.label} 输出端口 {src_port_idx} 不存在")
            print(f"可用输出端口数: {len(src_node.outputs)}")
            return False

        if dst_port_idx >= len(dst_node.inputs):
            print(f"目标节点 {dst_node.label} 输入端口 {dst_port_idx} 不存在")
            print(f"可用输入端口数: {len(dst_node.inputs)}")
            return False

        # 断开现有连接
        dst_port = dst_node.inputs[dst_port_idx]
        if dst_port.isConnected():
            dst_port.disconnect()

        # 连接
        src_node.outputs[src_port_idx].connect(dst_port)
        print(f"连接成功: {src_node.label}[{src_port_idx}] -> {dst_node.label}[{dst_port_idx}]")
        return True

    except Exception as e:
        print(f"连接失败: {e}")
        return False
```

### 2.4 帧范围错误

**错误**：
```python
ValueError: Frame out of range
```

**解决**：
```python
from fx import *

def get_safe_frame_range(session):
    """获取安全的帧范围"""
    src = None
    for i in range(session.numNodes):
        node = session.node(i)
        if node.type == "SourceNode":
            src = node
            break

    if not src:
        print("未找到 SourceNode")
        return [0, 0]

    start = src.property("startFrame").value
    end = src.property("endFrame").value
    return [start, end]

# 使用
frame_range = get_safe_frame_range(session)
print(f"安全帧范围: {frame_range}")
```

### 2.5 类型转换错误

**错误**：
```python
TypeError: Invalid type for property value
```

**解决**：
```python
from fx import *

def safe_set_property(node, prop_name, value, frame=0):
    """安全设置属性值，自动处理类型"""
    try:
        prop = node.property(prop_name)
        prop_type = prop.type

        # 根据类型转换
        if prop_type == "int":
            value = int(value)
        elif prop_type == "float":
            value = float(value)
        elif prop_type == "bool":
            value = bool(value)
        elif prop_type == "string":
            value = str(value)

        prop.setValue(value, frame)
        return True
    except Exception as e:
        print(f"设置属性 {prop_name} 失败: {e}")
        return False
```

### 2.6 内存错误

**错误**：
```python
MemoryError: Out of memory
```

**解决**：
```python
import gc
from fx import *

def process_large_batch(shots, max_per_batch=10):
    """分批处理大量镜头，避免内存溢出"""
    for i in range(0, len(shots), max_per_batch):
        batch = shots[i:i+max_per_batch]
        for shot in batch:
            try:
                process_shot(shot)
            except MemoryError:
                print(f"内存不足，处理 {shot} 失败")
                continue

        # 每批清理内存
        gc.collect()
        proj = activeProject()
        if proj:
            proj.clear()

        print(f"完成批次 {i//max_per_batch + 1}")
```

---

## 三、调试技巧

### 3.1 打印调试

**基础打印**：
```python
from fx import *

# 打印当前会话信息
session = activeSession()
print(f"Session: {session.label}")
print(f"Resolution: {session.width}x{session.height}")
print(f"Frame rate: {session.frameRate}")
print(f"Nodes: {session.numNodes}")

# 打印所有节点
for i in range(session.numNodes):
    node = session.node(i)
    print(f"  [{i}] {node.label} ({node.type})")
    print(f"      Inputs: {len(node.inputs)}, Outputs: {len(node.outputs)}")
```

### 3.2 断点调试（2026 新功能）

```python
from fx import *

# 设置断点
breakpoint()  # Python 3.7+

# 或使用 Silhouette 的断点
import fx.debug
fx.debug.breakpoint()
```

### 3.3 可视化调试

```python
from fx import *
import json

def dump_node_tree(session, output_file="node_tree.json"):
    """导出节点树为 JSON，便于分析"""
    tree = {
        "session": session.label,
        "resolution": [session.width, session.height],
        "nodes": []
    }

    for i in range(session.numNodes):
        node = session.node(i)
        node_info = {
            "index": i,
            "label": node.label,
            "type": node.type,
            "properties": {},
            "inputs": [],
            "outputs": []
        }

        # 记录属性
        for prop_name in node.properties:
            try:
                prop = node.property(prop_name)
                node_info["properties"][prop_name] = {
                    "type": prop.type,
                    "value": str(prop.value)
                }
            except:
                pass

        tree["nodes"].append(node_info)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    print(f"节点树已导出: {output_file}")
```

### 3.4 逐步执行

```python
from fx import *
import time

def step_by_step_render(session, start_frame, end_frame):
    """逐步渲染，便于调试"""
    for frame in range(start_frame, end_frame + 1):
        print(f"处理第 {frame} 帧...")

        try:
            # 设置当前帧
            session.currentFrame = frame

            # 更新视图
            session.updateView()

            # 等待用户确认（调试模式）
            input("按 Enter 继续下一帧...")

        except KeyboardInterrupt:
            print("用户中断")
            break
        except Exception as e:
            print(f"第 {frame} 帧出错: {e}")
            continue
```

### 3.5 条件断点

```python
from fx import *

def process_with_condition(session, condition_func=None):
    """带条件的处理"""
    for i in range(session.numNodes):
        node = session.node(i)

        # 条件断点
        if condition_func and condition_func(node):
            print(f"条件触发: {node.label}")
            breakpoint()  # 进入调试

        process_node(node)
```

---

## 四、异常处理

### 4.1 完整的异常处理框架

```python
from fx import *
import traceback
import logging

class SilhouetteErrorHandler:
    """Silhouette 统一错误处理器"""

    def __init__(self, log_file="silhouette_errors.log"):
        self.logger = self._setup_logger(log_file)
        self.error_count = 0
        self.warning_count = 0

    def _setup_logger(self, log_file):
        """配置日志"""
        logger = logging.getLogger("silhouette")
        logger.setLevel(logging.DEBUG)

        # 文件处理器
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)

        # 控制台处理器
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # 格式
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

        return logger

    def handle(self, func, *args, **kwargs):
        """安全的函数调用"""
        try:
            return func(*args, **kwargs)
        except ProjectError as e:
            self.error_count += 1
            self.logger.error(f"项目错误: {e}")
            self.logger.debug(traceback.format_exc())
            return None
        except NodeError as e:
            self.error_count += 1
            self.logger.error(f"节点错误: {e}")
            self.logger.debug(traceback.format_exc())
            return None
        except IOError as e:
            self.error_count += 1
            self.logger.error(f"IO错误: {e}")
            return None
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"未知错误: {e}")
            self.logger.debug(traceback.format_exc())
            return None

    def report(self):
        """生成错误报告"""
        report = f"""
=== 错误报告 ===
错误数: {self.error_count}
警告数: {self.warning_count}
"""
        self.logger.info(report)
        return report


# 使用示例
handler = SilhouetteErrorHandler()

# 安全调用
result = handler.handle(create_roto, session, "character")
result = handler.handle(set_property, node, "alpha.blur", 0.5)

# 生成报告
handler.report()
```

### 4.2 自定义异常

```python
class SilhouetteScriptError(Exception):
    """Silhouette 脚本基础异常"""
    pass

class NodeNotFoundError(SilhouetteScriptError):
    """节点未找到"""
    def __init__(self, node_label):
        self.node_label = node_label
        super().__init__(f"节点未找到: {node_label}")

class PropertyError(SilhouetteScriptError):
    """属性错误"""
    def __init__(self, node_label, prop_name):
        self.node_label = node_label
        self.prop_name = prop_name
        super().__init__(f"属性错误: {node_label}.{prop_name}")

class ConnectionError(SilhouetteScriptError):
    """连接错误"""
    def __init__(self, src_label, dst_label):
        self.src_label = src_label
        self.dst_label = dst_label
        super().__init__(f"连接失败: {src_label} -> {dst_label}")


def get_node(session, label):
    """获取节点，不存在则抛出异常"""
    for i in range(session.numNodes):
        node = session.node(i)
        if node.label == label:
            return node
    raise NodeNotFoundError(label)

# 使用
try:
    roto = get_node(session, "Main_Roto")
except NodeNotFoundError as e:
    print(f"错误: {e}")
    print("请检查节点名称")
```

### 4.3 重试机制

```python
import time
from fx import *

def retry(max_retries=3, delay=1.0):
    """重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    print(f"第 {attempt+1} 次尝试失败: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
            raise last_error
        return wrapper
    return decorator

# 使用
@retry(max_retries=3, delay=2.0)
def load_large_project(path):
    """加载大项目（可能失败）"""
    proj = Project()
    proj.load(path)
    return proj
```

---

## 五、日志系统

### 5.1 日志配置

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_dir="logs", level=logging.DEBUG):
    """配置日志系统"""
    import os
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("silhouette")
    logger.setLevel(level)

    # 滚动文件处理器（10MB，保留 5 个）
    fh = RotatingFileHandler(
        f"{log_dir}/silhouette.log",
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding="utf-8"
    )
    fh.setLevel(level)

    # 控制台处理器
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # 格式
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

logger = setup_logging()
```

### 5.2 上下文日志

```python
class ContextLogger:
    """带上下文的日志"""

    def __init__(self, logger, context=""):
        self.logger = logger
        self.context = context

    def info(self, msg):
        self.logger.info(f"[{self.context}] {msg}")

    def error(self, msg):
        self.logger.error(f"[{self.context}] {msg}")

    def debug(self, msg):
        self.logger.debug(f"[{self.context}] {msg}")

# 使用
shot_logger = ContextLogger(logger, "SH010")
shot_logger.info("开始处理")
shot_logger.error("缺少素材")
```

### 5.3 性能日志

```python
import time
import logging

class PerformanceLogger:
    """性能日志"""

    def __init__(self, logger):
        self.logger = logger
        self.marks = {}

    def mark(self, name):
        """标记性能点"""
        self.marks[name] = time.time()

    def measure(self, start, end, message=""):
        """测量两个标记间的时间"""
        if start in self.marks and end in self.marks:
            duration = self.marks[end] - self.marks[start]
            self.logger.info(f"性能: {start}->{end} 耗时 {duration:.3f}s {message}")
            return duration
        return None

# 使用
perf = PerformanceLogger(logger)
perf.mark("start")
# ... 执行代码 ...
perf.mark("end")
perf.measure("start", "end", "Roto 渲染")
```

---

## 六、性能分析

### 6.1 函数级性能分析

```python
import cProfile
import pstats
from fx import *

def profile_function(func, *args, **kwargs):
    """分析函数性能"""
    profiler = cProfile.Profile()
    profiler.enable()

    result = func(*args, **kwargs)

    profiler.disable()

    # 输出统计
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    stats.print_stats(20)  # 前 20 个最耗时函数

    # 保存到文件
    stats.dump_stats("profile.prof")

    return result
```

### 6.2 节点性能分析

```python
from fx import *
import time

def analyze_node_performance(session):
    """分析每个节点的性能"""
    results = []

    for i in range(session.numNodes):
        node = session.node(i)

        # 测量处理时间
        start = time.time()
        try:
            node.process()
        except:
            pass
        duration = time.time() - start

        results.append({
            "label": node.label,
            "type": node.type,
            "duration": duration
        })

    # 按耗时排序
    results.sort(key=lambda x: x["duration"], reverse=True)

    print("\n=== 节点性能分析 ===")
    for r in results:
        print(f"{r['label']:30s} {r['type']:20s} {r['duration']:.3f}s")

    return results
```

---

## 七、最佳实践

### 7.1 脚本规范

```python
"""
脚本名称：batch_roto.py
功能描述：批量处理 Roto 任务
作者：张三
日期：2026-07-11
版本：1.0
"""

from fx import *
import logging
import os

# 常量定义
DEFAULT_FRAME_RATE = 24.0
DEFAULT_RESOLUTION = [1920, 1080]
MAX_BATCH_SIZE = 50

# 日志配置
logger = logging.getLogger(__name__)


def main(shots, output_dir):
    """主函数"""
    logger.info(f"开始批处理，共 {len(shots)} 个镜头")

    for i, shot in enumerate(shots):
        logger.info(f"[{i+1}/{len(shots)}] 处理 {shot}")
        try:
            process_shot(shot, output_dir)
        except Exception as e:
            logger.error(f"处理 {shot} 失败: {e}")
            continue

    logger.info("批处理完成")


def process_shot(shot, output_dir):
    """处理单个镜头"""
    # 实现细节
    pass


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        main(sys.argv[1:], sys.argv[-1])
```

### 7.2 代码复用

```python
# lib/silhouette_utils.py
from fx import *

class SilhouetteUtils:
    """Silhouette 工具集"""

    @staticmethod
    def create_session(label, width=1920, height=1080, fps=24.0):
        """创建标准会话"""
        session = Session()
        session.label = label
        activate(session)
        return session

    @staticmethod
    def add_source(session, path, fps=24.0):
        """添加源节点"""
        src = Node("SourceNode")
        src.property("mediaPath").setValue(path.replace("\\", "/"), 0)
        src.property("frameRate").setValue(fps, 0)
        session.addNode(src)
        return src

    @staticmethod
    def add_output(session, path, format="exr"):
        """添加输出节点"""
        out = Node("OutputNode")
        out.property("path").setValue(path.replace("\\", "/"), 0)
        out.property("format").setValue(format, 0)
        session.addNode(out)
        return out

    @staticmethod
    def connect(src, dst, src_port=0, dst_port=0):
        """连接节点"""
        src.outputs[src_port].connect(dst.inputs[dst_port])
```

### 7.3 测试策略

```python
# tests/test_roto.py
import unittest
from fx import *

class TestRotoCreation(unittest.TestCase):

    def setUp(self):
        """每个测试前创建空会话"""
        self.session = Session()
        self.session.label = "Test"
        activate(self.session)

    def tearDown(self):
        """每个测试后清理"""
        self.session = None

    def test_create_roto_node(self):
        """测试创建 Roto 节点"""
        roto = Node("RotoNode")
        self.session.addNode(roto)

        self.assertEqual(self.session.numNodes, 1)
        self.assertEqual(roto.type, "RotoNode")

    def test_set_blur(self):
        """测试设置模糊"""
        roto = Node("RotoNode")
        self.session.addNode(roto)

        roto.property("alpha.blur").setValue(0.5, 0)
        self.assertEqual(roto.property("alpha.blur").value, 0.5)

if __name__ == "__main__":
    unittest.main()
```

### 7.4 版本兼容

```python
import fx

# 获取版本
VERSION = fx.version
MAJOR_VERSION = int(VERSION.split(".")[0])

def create_ai_roto():
    """创建 AI Roto，兼容不同版本"""
    if MAJOR_VERSION >= 2026:
        # 2026 新 API
        from fx.ai import AIRoto
        ai = AIRoto()
        ai.setMode("transformer_v2")
        return ai
    elif MAJOR_VERSION >= 2024:
        # 2024 API
        node = Node("AIRotoNode")
        node.property("model").setValue("mask_rcnn")
        return node
    else:
        raise RuntimeError(f"版本 {VERSION} 不支持 AI Roto")
```

---

## 八、总结

脚本调试与错误处理是 Silhouette 自动化开发的关键技能。通过：

1. **完善的错误处理**：捕获并记录所有异常
2. **系统的日志**：便于问题追溯
3. **性能分析**：定位瓶颈
4. **代码规范**：提高可维护性
5. **测试覆盖**：确保稳定性

可以构建健壮的 Silhouette 自动化工作流。

---

> 相关文档：
> - [[Silhouette 常见问题与解决方案]]
> - [[Silhouette fx API 参数详解手册]]
> - [[Silhouette 项目管理最佳实践]]
