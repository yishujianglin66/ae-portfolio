# Silhouette 脚本性能优化

> 分类: 自动化与批处理
> 更新日期: 2026-07-11
> 概述: 性能瓶颈分析、内存管理、GPU 利用、缓存策略完整说明。

## 目录
1. [性能优化概述](#1-性能优化概述)
2. [性能瓶颈分析](#2-性能瓶颈分析)
3. [内存管理](#3-内存管理)
4. [GPU 利用](#4-gpu-利用)
5. [缓存策略](#5-缓存策略)
6. [脚本优化技巧](#6-脚本优化技巧)
7. [性能测试](#7-性能测试)
8. [最佳实践](#8-最佳实践)

---

## 1. 性能优化概述

### 1.1 为什么需要优化

| 场景 | 问题 | 影响 |
|------|------|------|
| 大量节点 | 求值缓慢 | 交互卡顿 |
| 高分辨率 | 内存占用大 | 崩溃风险 |
| 长时间序列 | 渲染时间长 | 交付延迟 |
| 复杂 Roto | 实时预览差 | 效率降低 |
| 批量处理 | 总耗时长 | 成本增加 |

### 1.2 性能指标

| 指标 | 单位 | 说明 |
|------|------|------|
| FPS | 帧/秒 | 实时预览帧率 |
| 渲染时间 | 秒/帧 | 单帧渲染耗时 |
| 内存占用 | MB/GB | 峰值内存 |
| CPU 利用率 | % | 处理器使用率 |
| GPU 利用率 | % | 显卡使用率 |
| 磁盘 I/O | MB/s | 读写速度 |

### 1.3 性能优化目标

- **交互响应**:预览 FPS > 24
- **渲染效率**:单帧 < 10 秒(1080p)
- **内存安全**:峰值 < 可用内存的 80%
- **资源利用**:CPU/GPU 利用率 > 70%

## 2. 性能瓶颈分析

### 2.1 瓶颈识别

```python
import time
import cProfile
import pstats

class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self):
        self.timings = {}
        self.profiler = None
    
    def start_profiling(self):
        """开始性能分析"""
        self.profiler = cProfile.Profile()
        self.profiler.enable()
    
    def stop_profiling(self, output_file=None):
        """停止性能分析"""
        if self.profiler:
            self.profiler.disable()
            stats = pstats.Stats(self.profiler)
            stats.sort_stats("cumulative")
            
            if output_file:
                stats.dump_stats(output_file)
            else:
                stats.print_stats(20)  # 前 20 个最耗时函数
    
    def time_operation(self, name):
        """计时装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                if name not in self.timings:
                    self.timings[name] = []
                self.timings[name].append(elapsed)
                return result
            return wrapper
        return decorator
    
    def report(self):
        """生成报告"""
        report = {}
        for name, times in self.timings.items():
            report[name] = {
                "calls": len(times),
                "total": sum(times),
                "average": sum(times) / len(times),
                "min": min(times),
                "max": max(times)
            }
        return report
```

### 2.2 常见瓶颈

| 瓶颈类型 | 症状 | 诊断方法 |
|----------|------|----------|
| CPU 瓶颈 | CPU 100%,渲染慢 | 查看 CPU 利用率 |
| 内存瓶颈 | 内存满,崩溃 | 监控内存增长 |
| GPU 瓶颈 | GPU 未充分利用 | 查看 GPU 状态 |
| I/O 瓶颈 | 磁盘等待长 | 监控磁盘 I/O |
| 节点图瓶颈 | 节点链过长 | 分析节点深度 |

### 2.3 节点图分析

```python
def analyze_node_graph_performance(session):
    """分析节点图性能"""
    analysis = {
        "total_nodes": session.numNodes,
        "by_type": {},
        "chain_depth": 0,
        "bottlenecks": []
    }
    
    # 统计节点类型
    for i in range(session.numNodes):
        node = session.node(i)
        analysis["by_type"][node.type] = analysis["by_type"].get(node.type, 0) + 1
    
    # 计算链深度
    def max_depth(node, visited=None):
        if visited is None:
            visited = set()
        if id(node) in visited:
            return 0
        visited.add(id(node))
        
        max_d = 0
        for port in node.inputs:
            if port.source:
                d = max_depth(port.source, visited)
                max_d = max(max_d, d)
        return max_d + 1
    
    # 查找输出节点
    for i in range(session.numNodes):
        node = session.node(i)
        if node.type == "Output":
            depth = max_depth(node)
            analysis["chain_depth"] = max(analysis["chain_depth"], depth)
    
    # 识别瓶颈
    if analysis["chain_depth"] > 10:
        analysis["bottlenecks"].append("节点链过深(>10)")
    
    if analysis["total_nodes"] > 50:
        analysis["bottlenecks"].append("节点数量过多(>50)")
    
    # 检查重计算节点
    expensive_types = ["Filter", "Paint", "Tracker"]
    for etype in expensive_types:
        count = analysis["by_type"].get(etype, 0)
        if count > 5:
            analysis["bottlenecks"].append(f"{etype} 节点过多({count})")
    
    return analysis
```

## 3. 内存管理

### 3.1 内存监控

```python
import psutil
import os

class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.peak = 0
        self.history = []
    
    def current_usage(self):
        """当前内存使用(MB)"""
        mem = self.process.memory_info().rss / 1024 / 1024
        self.peak = max(self.peak, mem)
        return mem
    
    def record(self, label=""):
        """记录当前内存"""
        mem = self.current_usage()
        self.history.append((time.time(), mem, label))
        return mem
    
    def peak_usage(self):
        """峰值内存"""
        return self.peak
    
    def report(self):
        """内存报告"""
        return {
            "current_mb": self.current_usage(),
            "peak_mb": self.peak,
            "history_points": len(self.history)
        }
```

### 3.2 内存优化策略

```python
class MemoryOptimizer:
    """内存优化器"""
    
    @staticmethod
    def clear_node_cache(node):
        """清除节点缓存"""
        # Silhouette 通常自动管理缓存
        # 但可以手动触发清除
        pass
    
    @staticmethod
    def clear_session_cache(session):
        """清除 Session 缓存"""
        for i in range(session.numNodes):
            node = session.node(i)
            MemoryOptimizer.clear_node_cache(node)
    
    @staticmethod
    def reduce_cache_size(session, max_frames=10):
        """减少缓存帧数"""
        # 设置缓存大小(如果 API 支持)
        pass
    
    @staticmethod
    def unload_unused_nodes(session):
        """卸载未使用的节点数据"""
        # 查找未连接到输出的节点
        connected = set()
        
        def mark_connected(node):
            if id(node) in connected:
                return
            connected.add(id(node))
            for p in node.inputs:
                if p.source:
                    mark_connected(p.source)
        
        for i in range(session.numNodes):
            node = session.node(i)
            if node.type == "Output":
                mark_connected(node)
        
        # 卸载未连接的节点
        for i in range(session.numNodes):
            node = session.node(i)
            if id(node) not in connected:
                MemoryOptimizer.clear_node_cache(node)
```

### 3.3 大文件处理

```python
def process_large_sequence(input_path, output_path, frame_range, batch_size=10):
    """分批处理大序列"""
    start, end = frame_range
    
    for batch_start in range(start, end + 1, batch_size):
        batch_end = min(batch_start + batch_size - 1, end)
        
        print(f"处理批次: {batch_start}-{batch_end}")
        
        # 处理一个批次
        process_batch(input_path, output_path, batch_start, batch_end)
        
        # 清理内存
        import gc
        gc.collect()

def process_batch(input_path, output_path, start, end):
    """处理一个批次"""
    # 创建临时项目处理
    project = Project()
    session = Session()
    project.addItem(session)
    
    source = Node("Source")
    source.property("path").setValue(input_path, 0)
    source.property("startFrame").setValue(start, 0)
    source.property("endFrame").setValue(end, 0)
    session.addNode(source)
    
    output = Node("Output")
    output.property("outputPath").setValue(output_path, 0)
    session.addNode(output)
    output.inputs[0].connect(source.outputs[0])
    
    render(output, start, end)
```

## 4. GPU 利用

### 4.1 GPU 配置

```python
class GPUConfig:
    """GPU 配置"""
    
    @staticmethod
    def enable_gpu():
        """启用 GPU 加速"""
        # 通过环境变量或项目设置
        import os
        os.environ["SILHOUETTE_GPU"] = "1"
    
    @staticmethod
    def set_gpu_device(device_id=0):
        """设置 GPU 设备"""
        import os
        os.environ["SILHOUETTE_GPU_DEVICE"] = str(device_id)
    
    @staticmethod
    def disable_gpu():
        """禁用 GPU(使用 CPU)"""
        import os
        os.environ["SILHOUETTE_GPU"] = "0"
```

### 4.2 GPU 加速的效果

| 操作 | CPU 时间 | GPU 时间 | 加速比 |
|------|----------|----------|--------|
| 模糊(1080p) | 2.5s | 0.3s | 8x |
| 跟踪(100点) | 15s | 3s | 5x |
| 渲染(单帧) | 8s | 2s | 4x |
| Roto 预览 | 5 FPS | 24 FPS | 5x |

### 4.3 GPU 内存管理

```python
def check_gpu_memory():
    """检查 GPU 内存(如果支持)"""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,nounits"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                used, total = lines[1].split(", ")
                return {"used_mb": int(used), "total_mb": int(total)}
    except:
        pass
    return None
```

## 5. 缓存策略

### 5.1 缓存层级

```
L1: 节点缓存(内存,最快)
L2: Session 缓存(内存,较大)
L3: 磁盘缓存(磁盘,持久)
L4: 源文件(原始文件)
```

### 5.2 缓存配置

```python
class CacheConfig:
    """缓存配置"""
    
    def __init__(self):
        self.node_cache_frames = 20  # 节点缓存帧数
        self.session_cache_mb = 4096  # Session 缓存大小(MB)
        self.disk_cache_path = "/tmp/silhouette_cache"
        self.disk_cache_gb = 50  # 磁盘缓存大小(GB)
    
    def apply(self):
        """应用缓存配置"""
        import os
        os.environ["SILHOUETTE_CACHE_FRAMES"] = str(self.node_cache_frames)
        os.environ["SILHOUETTE_CACHE_MB"] = str(self.session_cache_mb)
        os.environ["SILHOUETTE_DISK_CACHE"] = self.disk_cache_path
        os.environ["SILHOUETTE_DISK_CACHE_GB"] = str(self.disk_cache_gb)
```

### 5.3 智能缓存

```python
class SmartCache:
    """智能缓存管理"""
    
    def __init__(self, max_memory_mb=4096):
        self.max_memory = max_memory_mb
        self.cache = {}  # {key: (data, size_mb, last_access)}
        self.total_used = 0
    
    def get(self, key):
        """获取缓存"""
        if key in self.cache:
            data, size, _ = self.cache[key]
            self.cache[key] = (data, size, time.time())
            return data
        return None
    
    def put(self, key, data, size_mb):
        """存入缓存"""
        # 清理空间
        while self.total_used + size_mb > self.max_memory:
            self._evict()
        
        self.cache[key] = (data, size_mb, time.time())
        self.total_used += size_mb
    
    def _evict(self):
        """LRU 淘汰"""
        if not self.cache:
            return
        
        # 找到最久未访问的
        oldest_key = min(self.cache.keys(), 
                        key=lambda k: self.cache[k][2])
        
        _, size, _ = self.cache.pop(oldest_key)
        self.total_used -= size
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.total_used = 0
    
    def stats(self):
        """缓存统计"""
        return {
            "entries": len(self.cache),
            "used_mb": self.total_used,
            "max_mb": self.max_memory,
            "utilization": self.total_used / self.max_memory
        }
```

## 6. 脚本优化技巧

### 6.1 避免重复计算

```python
# 错误:循环内重复查询
for i in range(100):
    node = session.node(0)
    prop = node.property("opacity")
    prop.setValue(i * 0.01, i)

# 正确:缓存引用
node = session.node(0)
prop = node.property("opacity")
for i in range(100):
    prop.setValue(i * 0.01, i)
```

### 6.2 批量操作

```python
# 错误:逐个添加节点
for i in range(100):
    node = Node("RotoShape")
    session.addNode(node)

# 正确:批量添加(如果 API 支持)
beginUndo("Batch Add")
try:
    for i in range(100):
        node = Node("RotoShape")
        session.addNode(node)
finally:
    endUndo()
```

### 6.3 延迟求值

```python
# 错误:每帧重新计算
def render_frame(frame):
    # 每次都重新创建节点
    node = Node("Filter")
    session.addNode(node)
    # ... 渲染 ...

# 正确:创建一次,复用
node = Node("Filter")
session.addNode(node)

for frame in range(1, 101):
    render_frame(frame)
```

### 6.4 使用生成器

```python
# 错误:一次性加载所有帧到内存
def load_all_frames(path, start, end):
    frames = []
    for f in range(start, end + 1):
        frames.append(load_image(path, f))
    return frames  # 内存爆炸!

# 正确:使用生成器逐帧处理
def frame_generator(path, start, end):
    for f in range(start, end + 1):
        yield load_image(path, f)

for frame in frame_generator(path, 1, 1000):
    process(frame)
```

### 6.5 属性访问优化

```python
class PropertyCache:
    """属性缓存"""
    
    def __init__(self, node):
        self.node = node
        self.cache = {}
    
    def get(self, name):
        if name not in self.cache:
            self.cache[name] = self.node.property(name)
        return self.cache[name]
    
    def set(self, name, value, frame=0):
        prop = self.get(name)
        if prop:
            prop.setValue(value, frame)

# 使用
cache = PropertyCache(node)
for i in range(1000):
    cache.set("opacity", i * 0.001, i)
```

## 7. 性能测试

### 7.1 基准测试

```python
class Benchmark:
    """基准测试"""
    
    def __init__(self):
        self.results = {}
    
    def run(self, name, func, iterations=10):
        """运行基准测试"""
        times = []
        
        for i in range(iterations):
            start = time.time()
            func()
            elapsed = time.time() - start
            times.append(elapsed)
        
        self.results[name] = {
            "iterations": iterations,
            "total": sum(times),
            "average": sum(times) / iterations,
            "min": min(times),
            "max": max(times)
        }
        
        return self.results[name]
    
    def compare(self, baseline, optimized):
        """对比基准"""
        if baseline not in self.results or optimized not in self.results:
            return None
        
        base_avg = self.results[baseline]["average"]
        opt_avg = self.results[optimized]["average"]
        
        return {
            "baseline_time": base_avg,
            "optimized_time": opt_avg,
            "speedup": base_avg / opt_avg,
            "improvement": (1 - opt_avg / base_avg) * 100
        }
    
    def report(self):
        """生成报告"""
        print("\n=== 性能基准测试报告 ===")
        for name, stats in self.results.items():
            print(f"\n{name}:")
            print(f"  平均: {stats['average']:.4f}s")
            print(f"  最小: {stats['min']:.4f}s")
            print(f"  最大: {stats['max']:.4f}s")
```

### 7.2 实际测试示例

```python
def benchmark_node_operations():
    """基准测试:节点操作"""
    bench = Benchmark()
    
    # 测试创建节点
    def create_nodes():
        session = Session()
        for i in range(100):
            n = Node("RotoShape")
            session.addNode(n)
    
    bench.run("create_100_nodes", create_nodes)
    
    # 测试连接节点
    def connect_nodes():
        session = Session()
        nodes = []
        for i in range(100):
            n = Node("RotoShape")
            session.addNode(n)
            nodes.append(n)
        for i in range(99):
            nodes[i+1].inputs[0].connect(nodes[i].outputs[0])
    
    bench.run("connect_100_nodes", connect_nodes)
    
    # 测试属性设置
    def set_properties():
        node = Node("Color")
        session.addNode(node)
        prop = node.property("gamma")
        for i in range(1000):
            prop.setValue(1.0 + i * 0.001, i)
    
    bench.run("set_1000_properties", set_properties)
    
    bench.report()

# 运行基准测试
benchmark_node_operations()
```

## 8. 最佳实践

### 8.1 性能优化优先级

```
1. 算法优化(最大收益)
   ↓
2. 缓存利用(中等收益)
   ↓
3. 内存管理(稳定性)
   ↓
4. 并行处理(线性提升)
   ↓
5. GPU 加速(硬件加速)
```

### 8.2 优化检查清单

| 检查项 | 说明 |
|--------|------|
| □ 避免重复计算 | 缓存常用结果 |
| □ 减少节点数量 | 合并相似节点 |
| □ 控制链深度 | 避免过深的节点链 |
| □ 使用缓存 | 利用节点级缓存 |
| □ 批量操作 | 减少单次操作开销 |
| □ 内存监控 | 防止内存泄漏 |
| □ GPU 启用 | 利用硬件加速 |
| □ 性能测试 | 有数据支撑的优化 |

### 8.3 常见反模式

```python
# 反模式1:深递归
def deep_traverse(node, depth=0):
    if depth > 1000:
        return  # 栈溢出风险
    for p in node.inputs:
        if p.source:
            deep_traverse(p.source, depth + 1)

# 改进:使用迭代
def iterative_traverse(node):
    stack = [node]
    visited = set()
    while stack:
        n = stack.pop()
        if id(n) in visited:
            continue
        visited.add(id(n))
        for p in n.inputs:
            if p.source:
                stack.append(p.source)

# 反模式2:频繁字符串拼接
result = ""
for i in range(10000):
    result += f"frame_{i}"  # O(n²)

# 改进:使用 join
parts = [f"frame_{i}" for i in range(10000)]
result = "".join(parts)  # O(n)

# 反模式3:全局变量
GLOBAL_CACHE = {}

def process_with_global(key):
    if key not in GLOBAL_CACHE:
        GLOBAL_CACHE[key] = expensive_computation(key)
    return GLOBAL_CACHE[key]

# 改进:封装为类
class Cache:
    def __init__(self):
        self._cache = {}
    
    def get(self, key, compute_func):
        if key not in self._cache:
            self._cache[key] = compute_func(key)
        return self._cache[key]
```

### 8.4 性能监控集成

```python
class PerformanceIntegration:
    """性能监控集成"""
    
    def __init__(self):
        self.memory = MemoryMonitor()
        self.analyzer = PerformanceAnalyzer()
        self.enabled = True
    
    def wrap_function(self, func, name=None):
        """包装函数,添加性能监控"""
        name = name or func.__name__
        
        def wrapper(*args, **kwargs):
            if not self.enabled:
                return func(*args, **kwargs)
            
            self.memory.record(f"before_{name}")
            start = time.time()
            
            result = func(*args, **kwargs)
            
            elapsed = time.time() - start
            self.memory.record(f"after_{name}")
            
            print(f"[PERF] {name}: {elapsed:.3f}s, "
                  f"内存: {self.memory.current_usage():.0f}MB")
            
            return result
        
        return wrapper
```

---

## 附录:性能优化速查表

| 优化手段 | 预期收益 | 实现难度 |
|----------|----------|----------|
| 缓存属性引用 | 2-5x | 低 |
| 批量操作 | 3-10x | 低 |
| 减少节点数 | 2-3x | 中 |
| GPU 加速 | 4-8x | 低 |
| 内存分批 | 防崩溃 | 中 |
| 并行渲染 | 线性提升 | 高 |
| 算法优化 | 10x+ | 高 |

> **提示**:优化前先用性能分析器定位瓶颈,"过早优化是万恶之源"——先确保正确,再追求速度。
