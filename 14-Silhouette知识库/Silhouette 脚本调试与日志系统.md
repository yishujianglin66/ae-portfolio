# Silhouette 脚本调试与日志系统

> 分类: API与参数手册
> 更新日期: 2026-07-11
> 概述: 包括 print/debug/log 函数使用、断点调试、性能分析、错误捕获与处理、日志级别控制

## 目录

- [一、日志输出函数](#一日志输出函数)
- [二、日志级别控制](#二日志级别控制)
- [三、断点调试](#三断点调试)
- [四、性能分析](#四性能分析)
- [五、错误捕获与处理](#五错误捕获与处理)
- [六、日志文件管理](#六日志文件管理)
- [七、调试工具函数](#七调试工具函数)
- [八、实战调试场景](#八实战调试场景)
- [九、最佳实践](#九最佳实践)

---

## 一、日志输出函数

### 1.1 基础输出函数

| 函数 | 参数 | 说明 |
|------|------|------|
| `print(msg)` | msg: Any | 标准输出到控制台 |
| `fx.log(msg)` | msg: str | Silhouette 内置日志 |
| `fx.debug(msg)` | msg: str | 调试级别日志 |
| `fx.warning(msg)` | msg: str | 警告级别日志 |
| `fx.error(msg)` | msg: str | 错误级别日志 |
| `fx.info(msg)` | msg: str | 信息级别日志 |

### 1.2 基本使用

```python
from fx import *

# 标准输出
print("Hello Silhouette")

# 内置日志函数
fx.info("这是一条信息")
fx.debug("调试信息")
fx.warning("警告信息")
fx.error("错误信息")
```

### 1.3 格式化输出

```python
from fx import *

node = Node("RotoNode")
node.label = "TestRoto"

# f-string 格式化
print(f"节点: {node.label}, 类型: {node.type}")

# 多变量输出
frame = 30
opacity = 0.85
print(f"帧 {frame}: opacity = {opacity:.2f}")

# 列表/字典格式化
shapes = ["Body", "Head", "Arm"]
print(f"形状列表: {shapes}")
print(f"形状数量: {len(shapes)}")
```

### 1.4 带前缀的输出

```python
# 建议使用统一前缀便于日志过滤
def log_info(msg):
    print(f"[INFO] {msg}")

def log_warn(msg):
    print(f"[WARN] {msg}")

def log_error(msg):
    print(f"[ERROR] {msg}")

def log_debug(msg):
    print(f"[DEBUG] {msg}")

# 使用
log_info("开始处理")
log_debug(f"当前帧: {currentFrame}")
log_warn("缓存即将满")
log_error("文件不存在: D:/footage/missing.mov")
```

---

## 二、日志级别控制

### 2.1 日志级别

| 级别 | 数值 | 说明 |
|------|------|------|
| DEBUG | 10 | 详细调试信息 |
| INFO | 20 | 一般运行信息 |
| WARNING | 30 | 警告信息 |
| ERROR | 40 | 错误信息 |
| CRITICAL | 50 | 严重错误 |
| NONE | 100 | 关闭日志 |

### 2.2 设置日志级别

```python
import os
import logging

# 通过环境变量设置
os.environ["SILHOUETTE_LOG_LEVEL"] = "debug"

# 通过Python logging设置
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("silhouette")
```

### 2.3 自定义日志系统

```python
import logging
import os
from datetime import datetime

class SilhouetteLogger:
    """Silhouette 自定义日志系统"""

    LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    def __init__(self, name="silhouette", level="info", log_file=None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.LEVELS.get(level, logging.INFO))

        # 避免重复添加handler
        if not self.logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)-7s] %(message)s",
                datefmt="%H:%M:%S"
            )

            # 控制台输出
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            self.logger.addHandler(console)

            # 文件输出
            if log_file:
                file_handler = logging.FileHandler(log_file, encoding="utf-8")
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)

    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        self.logger.critical(msg)

# 使用
log = SilhouetteLogger(level="debug", log_file="D:/logs/silhouette.log")
log.info("日志系统初始化")
log.debug("调试信息")
log.warning("警告信息")
```

---

## 三、断点调试

### 3.1 pdb 断点调试

```python
import pdb

def complex_roto_operation(shapes_config):
    # 设置断点
    pdb.set_trace()

    for cfg in shapes_config:
        shape = createObject(cfg["type"])
        shape.name = cfg["name"]
        # ... 处理逻辑
```

### 3.2 条件断点

```python
import pdb

def process_frame(frame, node):
    # 仅在特定条件断点
    if frame == 30 and node.type == "RotoNode":
        pdb.set_trace()

    # 正常处理
    pass
```

### 3.3 断点调试命令

| 命令 | 简写 | 说明 |
|------|------|------|
| `continue` | `c` | 继续执行 |
| `step` | `s` | 单步进入 |
| `next` | `n` | 单步跳过 |
| `return` | `r` | 执行到返回 |
| `break` | `b` | 设置断点 |
| `print` | `p` | 打印变量 |
| `list` | `l` | 查看代码 |
| `where` | `w` | 查看调用栈 |
| `quit` | `q` | 退出调试 |

### 3.4 调试输出辅助

```python
def debug_dump_node(node, prefix=""):
    """输出节点的完整调试信息"""
    print(f"{prefix}=== 节点调试信息 ===")
    print(f"{prefix}标签: {node.label}")
    print(f"{prefix}类型: {node.type}")
    print(f"{prefix}启用: {node.enabled}")
    print(f"{prefix}选中: {node.selected}")

    print(f"{prefix}--- 属性 ---")
    for name in node.properties:
        prop = node.property(name)
        val = prop.value
        animated = " [动画]" if prop.isAnimated else ""
        print(f"{prefix}  {name}: {val}{animated}")

    print(f"{prefix}--- 端口 ---")
    print(f"{prefix}  输入: {len(node.inputs)}")
    for i, port in enumerate(node.inputs):
        connected = "已连接" if port.isConnected() else "未连接"
        print(f"{prefix}    [{i}] {port.name} - {connected}")
    print(f"{prefix}  输出: {len(node.outputs)}")
    for i, port in enumerate(node.outputs):
        connected = "已连接" if port.isConnected() else "未连接"
        print(f"{prefix}    [{i}] {port.name} - {connected}")
```

---

## 四、性能分析

### 4.1 时间测量

```python
import time

def measure_time(func):
    """函数执行时间测量装饰器"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"[PERF] {func.__name__} 耗时: {elapsed:.3f}秒")
        return result
    return wrapper

# 使用
@measure_time
def create_roto_pipeline():
    from fx import *
    # ... 创建节点
    pass

create_roto_pipeline()
```

### 4.2 详细性能分析

```python
import cProfile
import pstats
import io

def profile_function(func, *args, **kwargs):
    """详细性能分析"""
    profiler = cProfile.Profile()
    profiler.enable()

    result = func(*args, **kwargs)

    profiler.disable()

    # 输出统计
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")

    # 打印到字符串
    output = io.StringIO()
    stats.stream = output
    stats.print_stats(20)  # 前20个函数

    print(output.getvalue())
    return result

# 使用
def heavy_operation():
    from fx import *
    for i in range(100):
        node = Node("RotoNode")
        session.addNode(node)

profile_function(heavy_operation)
```

### 4.3 帧渲染性能监控

```python
import time

class FramePerformanceMonitor:
    """帧渲染性能监控器"""

    def __init__(self):
        self.frame_times = {}
        self.current_frame = None
        self.start_time = None

    def begin_frame(self, frame):
        self.current_frame = frame
        self.start_time = time.time()

    def end_frame(self):
        if self.current_frame is not None and self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.frame_times[self.current_frame] = elapsed
            self.current_frame = None
            self.start_time = None

    def report(self):
        if not self.frame_times:
            print("[PERF] 无性能数据")
            return

        times = list(self.frame_times.values())
        avg = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        max_frame = max(self.frame_times, key=self.frame_times.get)

        print("=== 帧渲染性能报告 ===")
        print(f"总帧数: {len(times)}")
        print(f"总耗时: {sum(times):.2f}秒")
        print(f"平均: {avg:.3f}秒/帧")
        print(f"最快: {min_time:.3f}秒")
        print(f"最慢: {max_time:.3f}秒 (帧 {max_frame})")

        # 标记慢帧
        threshold = avg * 2
        slow_frames = [(f, t) for f, t in self.frame_times.items() if t > threshold]
        if slow_frames:
            print(f"\n慢帧 (超过平均2倍):")
            for f, t in sorted(slow_frames, key=lambda x: -x[1]):
                print(f"  帧 {f}: {t:.3f}秒")

# 使用
monitor = FramePerformanceMonitor()
for frame in range(0, 100):
    monitor.begin_frame(frame)
    # renderFrame(frame)  # 渲染帧
    monitor.end_frame()

monitor.report()
```

### 4.4 内存使用监控

```python
import os
import tracemalloc

def memory_snapshot(label=""):
    """内存快照"""
    if not tracemalloc.tracing:
        tracemalloc.start()

    snapshot = tracemalloc.take_snapshot()
    if label:
        print(f"[MEM] 快照: {label}")

    top = snapshot.statistics("lineno")
    print("[MEM] 内存占用 Top 10:")
    for stat in top[:10]:
        print(f"  {stat}")

# 使用
memory_snapshot("开始")
# ... 执行操作
memory_snapshot("结束")
```

---

## 五、错误捕获与处理

### 5.1 异常处理结构

```python
from fx import *

def safe_node_operation(session, node_type, label):
    """安全的节点操作"""
    try:
        node = Node(node_type)
        node.label = label
        session.addNode(node)
        return node

    except TypeError as e:
        print(f"[ERROR] 类型错误: {e}")
        return None

    except AttributeError as e:
        print(f"[ERROR] 属性错误: {e}")
        return None

    except Exception as e:
        print(f"[ERROR] 未知错误: {type(e).__name__}: {e}")
        return None

    finally:
        print("[INFO] 操作完成")
```

### 5.2 属性操作安全包装

```python
def safe_set_property(node, prop_name, value, frame=0):
    """安全的属性设置"""
    try:
        if prop_name not in node.properties:
            print(f"[WARN] 属性不存在: {node.label}.{prop_name}")
            return False

        prop = node.property(prop_name)
        prop.setValue(value, frame)
        print(f"[OK] 设置 {node.label}.{prop_name} = {value}")
        return True

    except Exception as e:
        print(f"[ERROR] 设置属性失败: {node.label}.{prop_name}: {e}")
        return False

def safe_get_property(node, prop_name, frame=0, default=None):
    """安全的属性获取"""
    try:
        if prop_name not in node.properties:
            return default
        return node.property(prop_name).getValue(frame)
    except Exception as e:
        print(f"[ERROR] 获取属性失败: {node.label}.{prop_name}: {e}")
        return default
```

### 5.3 批量操作错误处理

```python
def batch_create_nodes(session, node_configs):
    """批量创建节点，带错误处理"""
    results = {"success": [], "failed": []}

    for i, cfg in enumerate(node_configs):
        try:
            node = Node(cfg["type"])
            node.label = cfg.get("label", f"Node_{i}")

            # 设置属性
            for prop_name, value in cfg.get("properties", {}).items():
                safe_set_property(node, prop_name, value)

            session.addNode(node)
            results["success"].append(node)

        except Exception as e:
            print(f"[ERROR] 创建节点 {i} 失败: {e}")
            results["failed"].append({"config": cfg, "error": str(e)})

    print(f"[INFO] 成功: {len(results['success'])}, 失败: {len(results['failed'])}")
    return results
```

### 5.4 自定义异常

```python
class SilhouetteError(Exception):
    """Silhouette 脚本基础异常"""
    pass

class NodeNotFoundError(SilhouetteError):
    """节点未找到"""
    pass

class PropertyNotFoundError(SilhouetteError):
    """属性未找到"""
    pass

class RenderError(SilhouetteError):
    """渲染错误"""
    pass

def find_node_or_raise(session, label):
    """查找节点或抛出异常"""
    node = session.findNode(label)
    if node is None:
        raise NodeNotFoundError(f"节点 '{label}' 不存在")
    return node

# 使用
try:
    roto = find_node_or_raise(session, "Main_Roto")
    prop = roto.property("alpha.blur")
    if prop is None:
        raise PropertyNotFoundError("alpha.blur")
except NodeNotFoundError as e:
    print(f"[ERROR] {e}")
except PropertyNotFoundError as e:
    print(f"[ERROR] {e}")
```

---

## 六、日志文件管理

### 6.1 日志文件配置

```python
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_file_logging(log_dir="D:/logs", max_size=10, backup_count=3):
    """配置文件日志系统"""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "silhouette.log")

    # 轮转文件处理器
    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_size * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8"
    )

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(filename)s:%(lineno)d: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    logger = logging.getLogger("silhouette")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    return logger

log = setup_file_logging()
log.info("日志系统启动")
```

### 6.2 日志清理

```python
import os
import time

def clean_old_logs(log_dir, days=7):
    """清理旧日志文件"""
    if not os.path.exists(log_dir):
        return

    current_time = time.time()
    max_age = days * 24 * 60 * 60  # 转为秒
    cleaned = 0

    for filename in os.listdir(log_dir):
        filepath = os.path.join(log_dir, filename)
        if os.path.isfile(filepath):
            file_time = os.path.getmtime(filepath)
            if current_time - file_time > max_age:
                os.remove(filepath)
                cleaned += 1
                print(f"[CLEAN] 删除: {filename}")

    print(f"[CLEAN] 清理完成，删除 {cleaned} 个文件")

clean_old_logs("D:/logs", days=7)
```

---

## 七、调试工具函数

### 7.1 会话状态转储

```python
from fx import *

def dump_session_state(session=None):
    """转储会话完整状态"""
    if session is None:
        session = activeSession()
    if session is None:
        print("[DEBUG] 无活动会话")
        return

    print("=" * 60)
    print(f"会话: {session.label}")
    print(f"尺寸: {session.width}x{session.height}")
    print(f"帧率: {session.frameRate}")
    print(f"帧范围: {session.frameStart}-{session.frameEnd}")
    print(f"节点数: {session.numNodes}")
    print("=" * 60)

    for i in range(session.numNodes):
        node = session.node(i)
        print(f"\n[节点 {i}] {node.label} ({node.type})")
        print(f"  启用: {node.enabled}")

        # 属性
        for name in node.properties:
            prop = node.property(name)
            val = prop.value
            anim = " *" if prop.isAnimated else ""
            print(f"  .{name} = {val}{anim}")

        # 连接
        for j, port in enumerate(node.inputs):
            if port.isConnected():
                src = port.source
                print(f"  输入[{j}] ← {src.label}")

# 使用
dump_session_state()
```

### 7.2 节点图可视化

```python
def visualize_node_graph(session):
    """文本可视化节点图"""
    print("\n=== 节点图 ===\n")

    for node in session.nodes:
        # 输入连接
        inputs = []
        for port in node.inputs:
            if port.isConnected():
                inputs.append(port.source.label)

        # 输出连接
        outputs = []
        for port in node.outputs:
            if port.isConnected():
                outputs.append(port.target.label)

        in_str = " ← [" + ", ".join(inputs) + "]" if inputs else ""
        out_str = " → [" + ", ".join(outputs) + "]" if outputs else ""

        print(f"  ({node.type}) {node.label}{in_str}{out_str}")

# 使用
visualize_node_graph(activeSession())
```

### 7.3 变量检查

```python
def inspect_variables(locals_dict, filter_prefix=""):
    """检查局部变量"""
    print("=== 变量检查 ===")
    for name, value in sorted(locals_dict.items()):
        if filter_prefix and not name.startswith(filter_prefix):
            continue
        if name.startswith("_"):
            continue

        type_name = type(value).__name__
        if isinstance(value, (str, int, float, bool)):
            print(f"  {name}: {type_name} = {value}")
        elif isinstance(value, list):
            print(f"  {name}: {type_name}[{len(value)}]")
        elif isinstance(value, dict):
            print(f"  {name}: {type_name}{{{len(value)}}}")
        else:
            print(f"  {name}: {type_name}")

# 使用
# inspect_variables(locals())
```

---

## 八、实战调试场景

### 8.1 调试节点连接问题

```python
def debug_node_connection(src_node, dst_node):
    """调试节点连接问题"""
    print(f"[DEBUG] 检查连接: {src_node.label} → {dst_node.label}")

    # 检查节点有效性
    if not src_node.valid:
        print(f"  [ERROR] 源节点无效")
        return False
    if not dst_node.valid:
        print(f"  [ERROR] 目标节点无效")
        return False

    # 检查端口
    if len(src_node.outputs) == 0:
        print(f"  [ERROR] 源节点无输出端口")
        return False
    if len(dst_node.inputs) == 0:
        print(f"  [ERROR] 目标节点无输入端口")
        return False

    # 检查已连接状态
    out_port = src_node.outputs[0]
    if out_port.isConnected():
        target = out_port.target
        if target and target.label == dst_node.label:
            print(f"  [OK] 已连接")
            return True
        else:
            print(f"  [WARN] 输出已连接到其他节点: {target.label if target else 'None'}")

    # 尝试连接
    try:
        out_port.connect(dst_node.inputs[0])
        print(f"  [OK] 连接成功")
        return True
    except Exception as e:
        print(f"  [ERROR] 连接失败: {e}")
        return False
```

### 8.2 调试属性动画

```python
def debug_property_animation(node, prop_name):
    """调试属性动画"""
    if prop_name not in node.properties:
        print(f"[ERROR] 属性不存在: {prop_name}")
        return

    prop = node.property(prop_name)
    print(f"[DEBUG] 属性动画: {node.label}.{prop_name}")
    print(f"  类型: {prop.type}")
    print(f"  当前值: {prop.value}")
    print(f"  默认值: {prop.defaultValue}")
    print(f"  是否动画: {prop.isAnimated}")

    if prop.isAnimated:
        print(f"  关键帧数: {prop.numKeys}")
        print(f"  关键帧列表:")
        for i in range(prop.numKeys):
            time = prop.keyTime(i)
            value = prop.keyValue(i)
            print(f"    [{i}] 帧 {time}: {value}")

        # 采样值
        print(f"  采样值:")
        if prop.numKeys >= 2:
            start_frame = int(prop.keyTime(0))
            end_frame = int(prop.keyTime(prop.numKeys - 1))
            step = max(1, (end_frame - start_frame) // 10)
            for f in range(start_frame, end_frame + 1, step):
                val = prop.getValue(f)
                print(f"    帧 {f}: {val}")

# 使用
# debug_property_animation(roto, "alpha.blur")
```

### 8.3 调试渲染问题

```python
def debug_render_setup(output_node):
    """调试渲染配置"""
    print("[DEBUG] 渲染配置检查")

    # 检查输出路径
    path = safe_get_property(output_node, "path", default="")
    if not path:
        print("  [ERROR] 输出路径为空")
        return False
    print(f"  路径: {path}")

    # 检查路径目录是否存在
    import os
    dir_path = os.path.dirname(path)
    if dir_path and not os.path.exists(dir_path):
        print(f"  [WARN] 输出目录不存在: {dir_path}")
        try:
            os.makedirs(dir_path, exist_ok=True)
            print(f"  [OK] 已创建目录")
        except Exception as e:
            print(f"  [ERROR] 创建目录失败: {e}")
            return False

    # 检查帧范围
    start = safe_get_property(output_node, "frameStart", default=0)
    end = safe_get_property(output_node, "frameEnd", default=0)
    if end <= start:
        print(f"  [ERROR] 帧范围无效: {start}-{end}")
        return False
    print(f"  帧范围: {start}-{end} ({end - start + 1}帧)")

    # 检查输入连接
    if not output_node.inputs[0].isConnected():
        print(f"  [ERROR] 输入未连接")
        return False

    source = output_node.inputs[0].source
    print(f"  输入源: {source.label}")

    print("  [OK] 渲染配置正常")
    return True
```

---

## 九、最佳实践

### 9.1 日志使用规范

```python
# 推荐的日志使用模式
class ScriptLogger:
    """脚本日志规范"""

    def __init__(self, script_name):
        self.name = script_name

    def info(self, msg):
        print(f"[{self.name}][INFO] {msg}")

    def warn(self, msg):
        print(f"[{self.name}][WARN] {msg}")

    def error(self, msg):
        print(f"[{self.name}][ERROR] {msg}")

    def debug(self, msg):
        import os
        if os.environ.get("SILHOUETTE_LOG_LEVEL") == "debug":
            print(f"[{self.name}][DEBUG] {msg}")

log = ScriptLogger("RotoPipeline")

log.info("开始创建Roto流水线")
log.debug(f"输入路径: {source_path}")
log.warn("检测到大量形状，可能影响性能")
log.error("输出路径不可写")
```

### 9.2 调试模式开关

```python
import os

DEBUG = os.environ.get("SILHOUETTE_DEBUG", "0") == "1"

def debug_print(msg):
    """仅在调试模式下输出"""
    if DEBUG:
        print(f"[DEBUG] {msg}")

# 使用
debug_print("这条消息只在调试模式显示")
```

### 9.3 完整调试模板

```python
from fx import *
import time
import os

DEBUG = os.environ.get("SILHOUETTE_DEBUG", "0") == "1"

def main():
    if DEBUG:
        print("=" * 60)
        print("[DEBUG] 脚本开始")
        print(f"[DEBUG] Python版本: {__import__('sys').version}")
        print(f"[DEBUG] 工作目录: {os.getcwd()}")
        print("=" * 60)

    try:
        start_time = time.time()

        # 主逻辑
        session = activeSession()
        if session is None:
            raise RuntimeError("无活动会话")

        if DEBUG:
            dump_session_state(session)

        # ... 业务逻辑

        elapsed = time.time() - start_time
        print(f"[INFO] 完成，耗时 {elapsed:.2f}秒")

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        if DEBUG:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
```
