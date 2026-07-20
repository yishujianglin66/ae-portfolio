# Silhouette 环境变量与全局配置

> 分类: API与参数手册
> 更新日期: 2026-07-11
> 概述: 包括 Silhouette 环境变量、渲染线程配置、GPU加速设置、内存管理、日志级别、插件路径等全局配置

## 目录

- [一、环境变量总览](#一环境变量总览)
- [二、核心路径配置](#二核心路径配置)
- [三、渲染与性能配置](#三渲染与性能配置)
- [四、GPU 加速设置](#四gpu-加速设置)
- [五、内存管理](#五内存管理)
- [六、日志系统配置](#六日志系统配置)
- [七、插件路径配置](#七插件路径配置)
- [八、Python 环境配置](#八python-环境配置)
- [九、网络与代理配置](#九网络与代理配置)
- [十、配置文件详解](#十配置文件详解)
- [十一、最佳实践](#十一最佳实践)

---

## 一、环境变量总览

Silhouette 通过环境变量控制运行时行为，可在系统环境或启动脚本中设置。

### 环境变量分类

| 分类 | 变量前缀 | 说明 |
|------|----------|------|
| 路径配置 | `SILHOUETTE_PATH` / `SILHOUETTE_*_PATH` | 各种资源路径 |
| 渲染配置 | `SILHOUETTE_RENDER_*` | 渲染相关参数 |
| GPU配置 | `SILHOUETTE_GPU_*` | GPU加速控制 |
| 内存配置 | `SILHOUETTE_MEMORY_*` | 内存管理 |
| 日志配置 | `SILHOUETTE_LOG_*` | 日志级别与输出 |
| 插件配置 | `SILHOUETTE_PLUGIN_*` | 插件加载 |
| Python配置 | `SILHOUETTE_PYTHON_*` | Python环境 |

### 设置方式

```bash
# Windows 系统环境变量
set SILHOUETTE_PATH=D:\Silhouette\resources

# Linux / macOS
export SILHOUETTE_PATH=/opt/Silhouette/resources
```

```python
# 在 Python 脚本中读取
import os
path = os.environ.get("SILHOUETTE_PATH", "")
print(f"Silhouette 路径: {path}")
```

---

## 二、核心路径配置

### 2.1 路径变量表

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SILHOUETTE_PATH` | 安装目录 | Silhouette 主安装路径 |
| `SILHOUETTE_RESOURCE_PATH` | $SILHOUETTE_PATH/resources | 资源文件路径 |
| `SILHOUETTE_SCRIPT_PATH` | $SILHOUETTE_PATH/scripts | 脚本搜索路径 |
| `SILHOUETTE_PLUGIN_PATH` | $SILHOUETTE_PATH/plugins | 插件搜索路径 |
| `SILHOUETTE_PRESET_PATH` | $SILHOUETTE_PATH/presets | 预设文件路径 |
| `SILHOUETTE_LUT_PATH` | $SILHOUETTE_PATH/luts | LUT文件路径 |
| `SILHOUETTE_OCIO_PATH` | $SILHOUETTE_PATH/ocio | OCIO配置路径 |
| `SILHOUETTE_TEMP_PATH` | 系统临时目录 | 临时文件路径 |
| `SILHOUETTE_CACHE_PATH` | $SILHOUETTE_PATH/cache | 缓存路径 |

### 2.2 多路径配置

路径变量支持分号（Windows）或冒号（Linux/macOS）分隔多个路径：

```bash
# Windows
set SILHOUETTE_SCRIPT_PATH=D:\my_scripts;D:\shared_scripts;E:\project_scripts

# Linux / macOS
export SILHOUETTE_SCRIPT_PATH=/home/user/my_scripts:/shared/scripts
```

### 2.3 脚本中访问路径

```python
import os

# 获取各类路径
def get_silhouette_paths():
    paths = {
        "main": os.environ.get("SILHOUETTE_PATH", ""),
        "resources": os.environ.get("SILHOUETTE_RESOURCE_PATH", ""),
        "scripts": os.environ.get("SILHOUETTE_SCRIPT_PATH", ""),
        "plugins": os.environ.get("SILHOUETTE_PLUGIN_PATH", ""),
        "presets": os.environ.get("SILHOUETTE_PRESET_PATH", ""),
        "luts": os.environ.get("SILHOUETTE_LUT_PATH", ""),
        "temp": os.environ.get("SILHOUETTE_TEMP_PATH", os.path.join(os.environ.get("TEMP", "/tmp"), "silhouette")),
        "cache": os.environ.get("SILHOUETTE_CACHE_PATH", ""),
    }
    return paths

paths = get_silhouette_paths()
for name, path in paths.items():
    print(f"{name}: {path}")
```

### 2.4 自定义脚本路径

```python
import os
import sys

# 添加自定义脚本路径
custom_path = "D:/my_silhouette_scripts"
if custom_path not in sys.path:
    sys.path.insert(0, custom_path)

# 现在可以导入自定义模块
from my_roto_utils import batch_create_shapes
from my_export_utils import export_to_ae
```

---

## 三、渲染与性能配置

### 3.1 渲染配置变量

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SILHOUETTE_RENDER_THREADS` | 0 (自动) | 渲染线程数 |
| `SILHOUETTE_RENDER_PRIORITY` | normal | 渲染优先级 (low/normal/high) |
| `SILHOUETTE_RENDER_TILE_SIZE` | 256 | 分块渲染大小 |
| `SILHOUETTE_RENDER_TIMEOUT` | 0 (无限) | 渲染超时（秒） |
| `SILHOUETTE_PREVIEW_QUALITY` | medium | 预览质量 (low/medium/high) |
| `SILHOUETTE_PREVIEW_RESOLUTION` | 1.0 | 预览分辨率比例 |

### 3.2 线程配置

```python
import os

# 获取CPU核心数
cpu_count = os.cpu_count()
print(f"CPU核心数: {cpu_count}")

# 推荐线程数配置
# - 4核以下：threads = cpu_count - 1
# - 8核：threads = cpu_count - 2
# - 16核以上：threads = cpu_count - 4
if cpu_count <= 4:
    recommended_threads = cpu_count - 1
elif cpu_count <= 8:
    recommended_threads = cpu_count - 2
else:
    recommended_threads = cpu_count - 4

print(f"推荐渲染线程数: {recommended_threads}")
```

### 3.3 预览质量配置

```python
from fx import *

# 设置预览质量
# low: 快速预览，适合交互操作
# medium: 平衡模式（默认）
# high: 高质量预览

# 分块渲染大小影响大画幅性能
# 小tile: 内存占用低，速度慢
# 大tile: 内存占用高，速度快
```

### 3.4 性能配置最佳实践

| 场景 | 线程数 | 预览质量 | Tile大小 |
|------|--------|----------|----------|
| 交互式Roto | 2-4 | low | 128 |
| 跟踪预览 | 4-6 | medium | 256 |
| 最终渲染 | 全部-2 | high | 512 |
| 超大画幅(4K+) | 全部-4 | medium | 256 |

---

## 四、GPU 加速设置

### 4.1 GPU 配置变量

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SILHOUETTE_GPU_ENABLED` | 1 | 启用GPU加速 (0/1) |
| `SILHOUETTE_GPU_DEVICE` | 0 | GPU设备索引 |
| `SILHOUETTE_GPU_MEMORY` | 0 (自动) | GPU显存限制(MB) |
| `SILHOUETTE_GPU_FALLBACK` | 1 | GPU失败时回退CPU (0/1) |
| `SILHOUETTE_CUDA_VISIBLE_DEVICES` | 全部 | 可见CUDA设备 |

### 4.2 GPU 加速适用场景

| 功能 | GPU加速 | 说明 |
|------|---------|------|
| 运动模糊 | 是 | 大幅提升速度 |
| 滤镜（模糊/锐化） | 是 | 显著提升 |
| 跟踪 | 是 | 提升跟踪速度 |
| Paint渲染 | 部分 | 笔触渲染加速 |
| Roto形状渲染 | 部分 | 形状光栅化加速 |
| 颜色校正 | 是 | 像素级并行 |
| EXR编解码 | 是 | 压缩/解压加速 |

### 4.3 GPU 配置脚本

```python
import os

def configure_gpu(enabled=True, device=0, memory_limit=0):
    """配置GPU加速参数"""
    os.environ["SILHOUETTE_GPU_ENABLED"] = "1" if enabled else "0"
    os.environ["SILHOUETTE_GPU_DEVICE"] = str(device)
    os.environ["SILHOUETTE_GPU_MEMORY"] = str(memory_limit)
    os.environ["SILHOUETTE_GPU_FALLBACK"] = "1"

    status = "启用" if enabled else "禁用"
    print(f"[GPU] {status}, 设备: {device}, 显存限制: {memory_limit}MB")

# 配置示例
configure_gpu(enabled=True, device=0, memory_limit=4096)
```

### 4.4 GPU 故障排查

```python
import os

def gpu_troubleshoot():
    """GPU故障排查"""
    print("=== GPU 配置检查 ===")
    print(f"GPU启用: {os.environ.get('SILHOUETTE_GPU_ENABLED', '未设置(默认1)')}")
    print(f"GPU设备: {os.environ.get('SILHOUETTE_GPU_DEVICE', '未设置(默认0)')}")
    print(f"GPU回退: {os.environ.get('SILHOUETTE_GPU_FALLBACK', '未设置(默认1)')}")

    # 如果GPU有问题，临时禁用
    if os.environ.get("SILHOUETTE_GPU_ENABLED") == "0":
        print("[WARNING] GPU已禁用，渲染将使用CPU（较慢）")
        print("建议：检查GPU驱动是否最新，或尝试设置 SILHOUETTE_GPU_FALLBACK=1")
```

---

## 五、内存管理

### 5.1 内存配置变量

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SILHOUETTE_MEMORY_LIMIT` | 0 (自动) | 最大内存限制(MB) |
| `SILHOUETTE_CACHE_SIZE` | 2048 | 图像缓存大小(MB) |
| `SILHOUETTE_UNDO_LIMIT` | 50 | 撤销历史步数 |
| `SILHOUETTE_HISTORY_SIZE` | 100 | 历史记录大小(MB) |
| `SILHOUETTE_TEXTURE_LIMIT` | 0 (无限制) | 纹理内存上限(MB) |

### 5.2 内存配置建议

| 系统内存 | 缓存大小 | 撤销步数 | 说明 |
|----------|----------|----------|------|
| 8 GB | 1024 | 20 | 最小配置 |
| 16 GB | 2048 | 50 | 推荐配置 |
| 32 GB | 4096 | 100 | 大型项目 |
| 64 GB+ | 8192 | 200 | 工作站配置 |

### 5.3 内存监控脚本

```python
import os
import psutil  # 需要安装 psutil

def monitor_memory():
    """监控系统内存使用"""
    mem = psutil.virtual_memory()
    process = psutil.Process(os.getpid())

    print("=== 内存监控 ===")
    print(f"系统总内存: {mem.total / 1024**3:.1f} GB")
    print(f"系统已用: {mem.used / 1024**3:.1f} GB ({mem.percent}%)")
    print(f"系统可用: {mem.available / 1024**3:.1f} GB")
    print(f"进程内存: {process.memory_info().rss / 1024**2:.1f} MB")

    # Silhouette 缓存配置
    cache = os.environ.get("SILHOUETTE_CACHE_SIZE", "2048")
    print(f"Silhouette缓存: {cache} MB")

    if mem.percent > 85:
        print("[WARNING] 内存使用率过高，建议关闭不必要的程序")
```

### 5.4 缓存管理

```python
from fx import *

def clear_caches():
    """清理各种缓存"""
    # 清除图像缓存
    # clearImageCache()  # 如果API支持

    # 清除临时文件
    import os
    import glob
    temp_path = os.environ.get("SILHOUETTE_TEMP_PATH",
                                os.path.join(os.environ.get("TEMP", "/tmp"), "silhouette"))
    if os.path.exists(temp_path):
        for f in glob.glob(os.path.join(temp_path, "*.tmp")):
            try:
                os.remove(f)
            except:
                pass

    print("[CACHE] 缓存已清理")

# 在渲染大项目前调用
clear_caches()
```

---

## 六、日志系统配置

### 6.1 日志配置变量

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SILHOUETTE_LOG_LEVEL` | info | 日志级别 (debug/info/warning/error/none) |
| `SILHOUETTE_LOG_FILE` | 自动 | 日志文件路径 |
| `SILHOUETTE_LOG_CONSOLE` | 1 | 输出到控制台 (0/1) |
| `SILHOUETTE_LOG_FILE_ENABLED` | 1 | 输出到文件 (0/1) |
| `SILHOUETTE_LOG_MAX_SIZE` | 10 | 日志文件最大大小(MB) |
| `SILHOUETTE_LOG_BACKUP_COUNT` | 3 | 日志备份数 |

### 6.2 日志级别说明

| 级别 | 数值 | 说明 | 适用场景 |
|------|------|------|----------|
| debug | 10 | 调试信息 | 开发调试 |
| info | 20 | 一般信息 | 日常使用（默认） |
| warning | 30 | 警告信息 | 注意潜在问题 |
| error | 40 | 错误信息 | 生产环境 |
| none | 50 | 关闭日志 | 性能测试 |

### 6.3 日志配置脚本

```python
import os
import logging

def setup_logging(level="info", log_file=None):
    """配置日志系统"""
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }

    log_level = level_map.get(level, logging.INFO)

    # 设置环境变量
    os.environ["SILHOUETTE_LOG_LEVEL"] = level
    if log_file:
        os.environ["SILHOUETTE_LOG_FILE"] = log_file

    # Python logging 配置
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        filename=log_file,
        filemode="a"
    )

    logger = logging.getLogger("silhouette")
    logger.info(f"日志系统初始化，级别: {level}")
    return logger

# 使用
logger = setup_logging("debug", "D:/logs/silhouette.log")
logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
```

---

## 七、插件路径配置

### 7.1 插件配置变量

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SILHOUETTE_PLUGIN_PATH` | $SILHOUETTE_PATH/plugins | 插件搜索路径 |
| `SILHOUETTE_PLUGIN_DISABLED` | "" | 禁用的插件列表（逗号分隔） |
| `SILHOUETTE_PLUGIN_DEBUG` | 0 | 插件调试模式 (0/1) |

### 7.2 插件目录结构

```
plugins/
├── my_plugin/
│   ├── plugin.json          # 插件描述文件
│   ├── __init__.py          # Python入口
│   ├── nodes/               # 自定义节点
│   │   ├── my_node.py
│   │   └── ...
│   ├── scripts/             # 脚本
│   └── resources/           # 资源文件
```

### 7.3 插件加载脚本

```python
import os

def get_plugin_paths():
    """获取所有插件路径"""
    plugin_path = os.environ.get("SILHOUETTE_PLUGIN_PATH", "")
    # Windows用分号，Linux用冒号
    separator = ";" if os.name == "nt" else ":"
    return [p for p in plugin_path.split(separator) if p]

def list_plugins():
    """列出所有可用插件"""
    paths = get_plugin_paths()
    plugins = []

    for path in paths:
        if not os.path.exists(path):
            continue
        for item in os.listdir(path):
            plugin_dir = os.path.join(path, item)
            plugin_json = os.path.join(plugin_dir, "plugin.json")
            if os.path.isfile(plugin_json):
                plugins.append({
                    "name": item,
                    "path": plugin_dir,
                    "config": plugin_json
                })

    return plugins

plugins = list_plugins()
for p in plugins:
    print(f"插件: {p['name']}, 路径: {p['path']}")
```

### 7.4 禁用特定插件

```python
import os

# 禁用有问题的插件
def disable_plugin(plugin_name):
    current = os.environ.get("SILHOUETTE_PLUGIN_DISABLED", "")
    if plugin_name not in current:
        if current:
            current += ","
        current += plugin_name
        os.environ["SILHOUETTE_PLUGIN_DISABLED"] = current
        print(f"[PLUGIN] 已禁用: {plugin_name}")

# disable_plugin("problematic_plugin")
```

---

## 八、Python 环境配置

### 8.1 Python 配置变量

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SILHOUETTE_PYTHON_PATH` | 内置Python | Python解释器路径 |
| `SILHOUETTE_PYTHON_VERSION` | 3.x | Python版本 |
| `SILHOUETTE_PYTHON_MODULES` | "" | 额外模块搜索路径 |
| `PYTHONPATH` | "" | Python标准模块路径 |

### 8.2 模块路径配置

```python
import os
import sys

def setup_python_paths():
    """配置Python模块搜索路径"""
    # 获取配置的额外模块路径
    extra_modules = os.environ.get("SILHOUETTE_PYTHON_MODULES", "")

    # 添加标准位置
    standard_paths = [
        os.path.join(os.environ.get("SILHOUETTE_PATH", ""), "python", "lib"),
        os.path.join(os.environ.get("SILHOUETTE_PATH", ""), "python", "site-packages"),
        os.path.expanduser("~/.silhouette/python"),
    ]

    for path in standard_paths + extra_modules.split(os.pathsep):
        if path and path not in sys.path and os.path.exists(path):
            sys.path.insert(0, path)

    print(f"Python路径: {sys.version}")
    print(f"模块搜索路径数: {len(sys.path)}")

setup_python_paths()
```

### 8.3 检查可用模块

```python
def check_required_modules():
    """检查必需的Python模块"""
    required = {
        "numpy": "数值计算",
        "json": "JSON处理",
        "os": "系统操作",
        "math": "数学运算",
    }

    optional = {
        "PIL": "图像处理",
        "cv2": "计算机视觉",
        "scipy": "科学计算",
        "matplotlib": "数据可视化",
    }

    print("=== 必需模块 ===")
    for mod, desc in required.items():
        try:
            __import__(mod)
            print(f"  [OK] {mod} ({desc})")
        except ImportError:
            print(f"  [MISSING] {mod} ({desc})")

    print("=== 可选模块 ===")
    for mod, desc in optional.items():
        try:
            __import__(mod)
            print(f"  [OK] {mod} ({desc})")
        except ImportError:
            print(f"  [NOT FOUND] {mod} ({desc}) - 非必需")

check_required_modules()
```

---

## 九、网络与代理配置

### 9.1 网络配置变量

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SILHOUETTE_NETWORK_TIMEOUT` | 30 | 网络超时（秒） |
| `SILHOUETTE_PROXY_HOST` | "" | 代理服务器地址 |
| `SILHOUETTE_PROXY_PORT` | 0 | 代理端口 |
| `SILHOUETTE_PROXY_USER` | "" | 代理用户名 |
| `SILHOUETTE_PROXY_PASS` | "" | 代理密码 |

### 9.2 网络配置示例

```python
import os

def configure_network(timeout=30, proxy=None):
    """配置网络参数"""
    os.environ["SILHOUETTE_NETWORK_TIMEOUT"] = str(timeout)

    if proxy:
        host, port = proxy.split(":")
        os.environ["SILHOUETTE_PROXY_HOST"] = host
        os.environ["SILHOUETTE_PROXY_PORT"] = port

    print(f"[NETWORK] 超时: {timeout}秒")
    if proxy:
        print(f"[NETWORK] 代理: {proxy}")

# configure_network(timeout=60, proxy="proxy.example.com:8080")
```

---

## 十、配置文件详解

### 10.1 配置文件位置

| 平台 | 配置文件路径 |
|------|-------------|
| Windows | `%APPDATA%/Silhouette/silhouette.cfg` |
| macOS | `~/Library/Preferences/Silhouette/silhouette.cfg` |
| Linux | `~/.config/Silhouette/silhouette.cfg` |

### 10.2 配置文件格式

```ini
# silhouette.cfg 配置文件示例

[General]
version = 2026.0.2
language = zh_CN
theme = dark

[Render]
threads = 0
priority = normal
tile_size = 256
preview_quality = medium

[GPU]
enabled = 1
device = 0
memory_limit = 0
fallback = 1

[Memory]
cache_size = 2048
undo_limit = 50
history_size = 100

[Logging]
level = info
console = 1
file_enabled = 1
max_size = 10
backup_count = 3

[Paths]
scripts = D:/my_scripts
plugins = D:/my_plugins
presets = D:/my_presets

[Python]
version = 3.9
modules = D:/python_modules
```

### 10.3 读取配置文件

```python
import os
import configparser

def load_config():
    """加载Silhouette配置文件"""
    # 确定配置文件路径
    if os.name == "nt":
        config_path = os.path.join(os.environ.get("APPDATA", ""), "Silhouette", "silhouette.cfg")
    else:
        config_path = os.path.expanduser("~/.config/Silhouette/silhouette.cfg")

    config = configparser.ConfigParser()

    if os.path.exists(config_path):
        config.read(config_path, encoding="utf-8")
        print(f"[CONFIG] 已加载配置: {config_path}")
    else:
        print(f"[CONFIG] 配置文件不存在: {config_path}")

    return config

config = load_config()

# 读取配置值
if config.has_section("Render"):
    threads = config.get("Render", "threads", fallback="0")
    print(f"渲染线程: {threads}")

if config.has_section("GPU"):
    gpu_enabled = config.get("GPU", "enabled", fallback="1")
    print(f"GPU加速: {'启用' if gpu_enabled == '1' else '禁用'}")
```

### 10.4 修改配置文件

```python
import os
import configparser

def save_config(config_data):
    """保存配置到文件"""
    config = configparser.ConfigParser()

    for section, options in config_data.items():
        config.add_section(section)
        for key, value in options.items():
            config.set(section, key, str(value))

    # 确定路径
    if os.name == "nt":
        config_dir = os.path.join(os.environ.get("APPDATA", ""), "Silhouette")
    else:
        config_dir = os.path.expanduser("~/.config/Silhouette")

    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "silhouette.cfg")

    with open(config_path, "w", encoding="utf-8") as f:
        config.write(f)

    print(f"[CONFIG] 配置已保存: {config_path}")

# 修改配置
save_config({
    "Render": {"threads": 8, "priority": "high"},
    "GPU": {"enabled": "1", "device": "0"},
    "Memory": {"cache_size": "4096"},
})
```

---

## 十一、最佳实践

### 11.1 环境检测脚本

```python
import os
import sys

def detect_environment():
    """检测Silhouette运行环境"""
    print("=== Silhouette 环境检测 ===\n")

    # 路径检测
    print("[路径配置]")
    paths = {
        "SILHOUETTE_PATH": "主路径",
        "SILHOUETTE_SCRIPT_PATH": "脚本路径",
        "SILHOUETTE_PLUGIN_PATH": "插件路径",
        "SILHOUETTE_TEMP_PATH": "临时路径",
    }
    for var, desc in paths.items():
        val = os.environ.get(var, "未设置")
        print(f"  {desc}: {val}")

    # 渲染配置
    print("\n[渲染配置]")
    threads = os.environ.get("SILHOUETTE_RENDER_THREADS", "自动")
    print(f"  渲染线程: {threads}")
    print(f"  CPU核心数: {os.cpu_count()}")

    # GPU配置
    print("\n[GPU配置]")
    gpu = os.environ.get("SILHOUETTE_GPU_ENABLED", "1")
    print(f"  GPU加速: {'启用' if gpu == '1' else '禁用'}")

    # 内存配置
    print("\n[内存配置]")
    cache = os.environ.get("SILHOUETTE_CACHE_SIZE", "2048")
    print(f"  缓存大小: {cache}MB")

    # Python环境
    print("\n[Python环境]")
    print(f"  Python版本: {sys.version}")
    print(f"  模块路径数: {len(sys.path)}")

detect_environment()
```

### 11.2 配置模板

```python
def setup_production_environment():
    """生产环境配置模板"""
    import os

    # 渲染配置 - 高性能
    os.environ["SILHOUETTE_RENDER_THREADS"] = str(max(os.cpu_count() - 2, 2))
    os.environ["SILHOUETTE_RENDER_PRIORITY"] = "high"

    # GPU加速 - 启用
    os.environ["SILHOUETTE_GPU_ENABLED"] = "1"
    os.environ["SILHOUETTE_GPU_FALLBACK"] = "1"

    # 内存 - 大缓存
    os.environ["SILHOUETTE_CACHE_SIZE"] = "4096"
    os.environ["SILHOUETTE_UNDO_LIMIT"] = "100"

    # 日志 - 生产级别
    os.environ["SILHOUETTE_LOG_LEVEL"] = "warning"
    os.environ["SILHOUETTE_LOG_FILE_ENABLED"] = "1"

    print("[ENV] 生产环境配置完成")

def setup_development_environment():
    """开发环境配置模板"""
    import os

    # 渲染配置 - 快速预览
    os.environ["SILHOUETTE_RENDER_THREADS"] = "4"
    os.environ["SILHOUETTE_PREVIEW_QUALITY"] = "low"

    # GPU加速 - 启用
    os.environ["SILHOUETTE_GPU_ENABLED"] = "1"

    # 内存 - 适中
    os.environ["SILHOUETTE_CACHE_SIZE"] = "2048"

    # 日志 - 调试级别
    os.environ["SILHOUETTE_LOG_LEVEL"] = "debug"
    os.environ["SILHOUETTE_LOG_CONSOLE"] = "1"
    os.environ["SILHOUETTE_PLUGIN_DEBUG"] = "1"

    print("[ENV] 开发环境配置完成")
```

### 11.3 配置验证

```python
def validate_config():
    """验证配置是否合理"""
    import os
    issues = []

    # 检查路径是否存在
    script_path = os.environ.get("SILHOUETTE_SCRIPT_PATH", "")
    if script_path and not os.path.exists(script_path):
        issues.append(f"脚本路径不存在: {script_path}")

    # 检查线程数
    threads = int(os.environ.get("SILHOUETTE_RENDER_THREADS", "0"))
    cpu = os.cpu_count()
    if threads > cpu:
        issues.append(f"渲染线程数({threads})超过CPU核心数({cpu})")

    # 检查缓存大小
    cache = int(os.environ.get("SILHOUETTE_CACHE_SIZE", "2048"))
    if cache < 512:
        issues.append(f"缓存大小过小({cache}MB)，建议至少512MB")

    # 输出结果
    if issues:
        print("[CONFIG] 发现配置问题:")
        for issue in issues:
            print(f"  [!] {issue}")
    else:
        print("[CONFIG] 配置验证通过")

    return len(issues) == 0

validate_config()
```
