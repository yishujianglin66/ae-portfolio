# Silhouette 命令行执行与无头模式

> 分类: 自动化与批处理
> 更新日期: 2026-07-11
> 概述: CLI 参数详解、无头渲染、脚本自动执行、退出码规范完整说明。

## 目录
1. [命令行概述](#1-命令行概述)
2. [CLI 参数详解](#2-cli-参数详解)
3. [无头模式](#3-无头模式)
4. [脚本自动执行](#4-脚本自动执行)
5. [退出码规范](#5-退出码规范)
6. [环境变量](#6-环境变量)
7. [自动化集成](#7-自动化集成)
8. [最佳实践](#8-最佳实践)

---

## 1. 命令行概述

### 1.1 Silhouette CLI

Silhouette 提供命令行接口(CLI),允许在不启动图形界面的情况下执行脚本、渲染输出。

### 1.2 可执行文件路径

| 操作系统 | 默认路径 |
|----------|----------|
| Windows | `C:\Program Files\Boris FX\Silhouette [version]\silhouette.exe` |
| macOS | `/Applications/Silhouette [version]/silhouette` |
| Linux | `/opt/silhouette[silhouette [version]/bin/silhouette` |

### 1.3 基本调用

```bash
# 基本启动
silhouette

# 带参数启动
silhouette --headless --script my_script.py

# 打开项目
silhouette /path/to/project.sfx
```

## 2. CLI 参数详解

### 2.1 参数列表

| 参数 | 缩写 | 说明 | 示例 |
|------|------|------|------|
| `--help` | `-h` | 显示帮助 | `silhouette --help` |
| `--version` | `-v` | 显示版本 | `silhouette --version` |
| `--headless` | | 无界面模式 | `silhouette --headless` |
| `--script` | `-s` | 执行脚本 | `silhouette --script script.py` |
| `--project` | `-p` | 打开项目 | `silhouette --project proj.sfx` |
| `--render` | `-r` | 渲染输出 | `silhouette --render session.sfx` |
| `--output` | `-o` | 输出路径 | `silhouette -o /output/` |
| `--frames` | `-f` | 帧范围 | `silhouette -f 1-100` |
| `--format` | | 输出格式 | `silhouette --format exr` |
| `--config` | `-c` | 配置文件 | `silhouette -c config.json` |
| `--log` | `-l` | 日志文件 | `silhouette -l process.log` |
| `--verbose` | | 详细输出 | `silhouette --verbose` |
| `--license` | | 许可证服务器 | `silhouette --license server:port` |
| `--no-gpu` | | 禁用 GPU | `silhouette --no-gpu` |
| `--memory` | `-m` | 内存限制 | `silhouette -m 16G` |

### 2.2 参数组合示例

```bash
# 无头模式执行脚本
silhouette --headless --script process.py --verbose

# 渲染指定帧范围
silhouette --headless --project proj.sfx --render --frames 1-100 --output /output/

# 使用配置文件批量处理
silhouette --headless --config batch.json --log batch.log

# 指定许可证服务器
silhouette --headless --license 192.168.1.100:27001 --script render.py
```

### 2.3 参数优先级

```
命令行参数 > 配置文件 > 环境变量 > 默认值
```

## 3. 无头模式

### 3.1 什么是无头模式

无头模式(Headless Mode)是指不启动图形用户界面(GUI),仅在后台执行任务的模式。

### 3.2 无头模式特点

| 特点 | 说明 |
|------|------|
| 无 GUI | 不显示界面,节省资源 |
| 后台运行 | 适合服务器/渲染农场 |
| 脚本驱动 | 通过 Python 脚本控制 |
| 输出到文件 | 结果写入文件而非屏幕 |
| 退出码 | 通过退出码报告状态 |

### 3.3 无头模式启动

```bash
# 基本无头模式
silhouette --headless

# 无头模式执行脚本
silhouette --headless --script my_script.py

# 无头模式 + 详细日志
silhouette --headless --script my_script.py --verbose --log output.log
```

### 3.4 无头模式脚本结构

```python
#!/usr/bin/env python
"""无头模式脚本模板"""

from fx import *
import sys

def main():
    """主函数"""
    print("=== Silhouette 无头处理 ===")
    
    # 1. 创建或打开项目
    project = Project()
    session = Session()
    project.addItem(session)
    session.activate()
    
    # 2. 执行任务
    try:
        # 业务逻辑
        result = process_task(session)
        print(f"任务完成: {result}")
    except Exception as e:
        print(f"任务失败: {e}", file=sys.stderr)
        sys.exit(1)  # 非零退出码表示失败
    
    # 3. 保存结果
    project.save("/output/result.sfx")
    
    print("=== 处理完成 ===")
    sys.exit(0)  # 0 表示成功

def process_task(session):
    """具体任务处理"""
    # 创建节点、处理数据
    source = Node("Source")
    source.property("path").setValue("/input/footage.####.exr", 0)
    session.addNode(source)
    
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(source.outputs[0])
    output.property("outputPath").setValue("/output/result.####.exr", 0)
    
    # 渲染
    render(output, 1, 100)
    
    return "渲染完成"

if __name__ == "__main__":
    main()
```

## 4. 脚本自动执行

### 4.1 脚本路径传递

```bash
# 直接传递脚本路径
silhouette --headless --script /path/to/script.py

# 带参数的脚本
silhouette --headless --script script.py -- --input /footage --output /result
```

### 4.2 脚本参数解析

```python
#!/usr/bin/env python
"""支持命令行参数的脚本"""

from fx import *
import sys
import argparse

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Silhouette 自动化脚本")
    parser.add_argument("--input", required=True, help="输入路径")
    parser.add_argument("--output", required=True, help="输出路径")
    parser.add_argument("--start", type=int, default=1, help="起始帧")
    parser.add_argument("--end", type=int, default=100, help="结束帧")
    parser.add_argument("--format", default="exr", help="输出格式")
    return parser.parse_args()

def main():
    args = parse_args()
    
    project = Project()
    session = Session()
    project.addItem(session)
    session.activate()
    
    # 使用参数
    source = Node("Source")
    source.property("path").setValue(args.input, 0)
    source.property("startFrame").setValue(args.start, 0)
    source.property("endFrame").setValue(args.end, 0)
    session.addNode(source)
    
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(source.outputs[0])
    output.property("format").setValue(args.format, 0)
    output.property("outputPath").setValue(args.output, 0)
    
    render(output, args.start, args.end)
    print(f"渲染完成: {args.output}")

if __name__ == "__main__":
    main()
```

### 4.3 脚本调用脚本

```python
# 主脚本调用其他脚本
import importlib.util

def run_script(script_path, *args):
    """运行另一个 Python 脚本"""
    spec = importlib.util.spec_from_file_location("module", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "main"):
        return module.main(*args)

# 使用
run_script("/scripts/import_footage.py", "/path/to/footage")
```

## 5. 退出码规范

### 5.1 标准退出码

| 退出码 | 含义 | 说明 |
|--------|------|------|
| 0 | 成功 | 任务正常完成 |
| 1 | 一般错误 | 未指定的错误 |
| 2 | 参数错误 | 命令行参数无效 |
| 3 | 许可证错误 | 许可证无效或过期 |
| 4 | 文件错误 | 文件不存在或无法访问 |
| 5 | 内存错误 | 内存不足 |
| 6 | 渲染错误 | 渲染过程失败 |
| 7 | 超时 | 任务超时 |
| 8 | 取消 | 用户取消 |
| 9 | 依赖错误 | 缺少依赖项 |

### 5.2 退出码使用

```python
import sys

# 成功退出
sys.exit(0)

# 失败退出
sys.exit(1)

# 带具体错误码
sys.exit(4)  # 文件错误
```

### 5.3 退出码检查

```bash
#!/bin/bash
# Shell 脚本检查退出码

silhouette --headless --script process.py
exit_code=$?

case $exit_code in
    0)
        echo "处理成功"
        ;;
    3)
        echo "许可证错误,请检查许可证服务器"
        ;;
    4)
        echo "文件错误,请检查路径"
        ;;
    5)
        echo "内存不足,请减少帧范围或增加内存"
        ;;
    *)
        echo "处理失败,退出码: $exit_code"
        ;;
esac

exit $exit_code
```

### 5.4 Python 退出码检查

```python
import subprocess

def run_silhouette(script_path, *args):
    """运行 Silhouette 并返回退出码"""
    cmd = ["silhouette", "--headless", "--script", script_path] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    exit_codes = {
        0: "成功",
        1: "一般错误",
        2: "参数错误",
        3: "许可证错误",
        4: "文件错误",
        5: "内存错误",
        6: "渲染错误",
    }
    
    status = exit_codes.get(result.returncode, f"未知错误({result.returncode})")
    print(f"状态: {status}")
    if result.stderr:
        print(f"错误输出: {result.stderr}")
    
    return result.returncode, result.stdout, result.stderr
```

## 6. 环境变量

### 6.1 Silhouette 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `SILHOUETTE_PATH` | 安装路径 | `/opt/silhouette` |
| `SILHOUETTE_LICENSE` | 许可证服务器 | `27001@server` |
| `SILHOUETTE_PLUGIN_PATH` | 插件路径 | `/plugins` |
| `SILHOUETTE_SCRIPT_PATH` | 脚本路径 | `/scripts` |
| `SILHOUETTE_TEMP` | 临时目录 | `/tmp/silhouette` |
| `SILHOUETTE_MEMORY` | 内存限制 | `16G` |
| `SILHOUETTE_GPU` | GPU 设备 | `0` |

### 6.2 设置环境变量

```bash
# Linux/macOS
export SILHOUETTE_LICENSE=27001@license-server
export SILHOUETTE_MEMORY=32G
silhouette --headless --script render.py

# Windows (PowerShell)
$env:SILHOUETTE_LICENSE = "27001@license-server"
$env:SILHOUETTE_MEMORY = "32G"
silhouette --headless --script render.py
```

### 6.3 脚本中读取环境变量

```python
import os

def get_config():
    """从环境变量获取配置"""
    return {
        "license": os.environ.get("SILHOUETTE_LICENSE", ""),
        "memory": os.environ.get("SILHOUETTE_MEMORY", "8G"),
        "temp_dir": os.environ.get("SILHOUETTE_TEMP", "/tmp"),
        "script_path": os.environ.get("SILHOUETTE_SCRIPT_PATH", "."),
    }
```

## 7. 自动化集成

### 7.1 与任务调度器集成

```python
"""与 Deadline/Tractor 等任务调度器集成"""

import subprocess
import os

def submit_to_farm(script_path, project_path, frame_range, output_path):
    """提交到渲染农场"""
    cmd = [
        "silhouette",
        "--headless",
        "--script", script_path,
        "--project", project_path,
        "--frames", frame_range,
        "--output", output_path,
        "--log", f"{output_path}/render.log"
    ]
    
    # 提交到调度器(以 Deadline 为例)
    deadline_cmd = [
        "deadlinecommand",
        "-SubmitCommandLineJob",
        "-executable", " ".join(cmd),
        "-name", os.path.basename(script_path),
        "-frames", frame_range,
    ]
    
    subprocess.run(deadline_cmd)
```

### 7.2 与 CI/CD 集成

```yaml
# GitLab CI 示例
stages:
  - render

render_task:
  stage: render
  script:
    - silhouette --headless --script render.py --input $INPUT_PATH --output $OUTPUT_PATH
  only:
    - main
```

### 7.3 监控集成

```python
"""与监控系统集成"""

import requests
import subprocess

def render_with_monitoring(script_path):
    """带监控的渲染"""
    # 发送开始通知
    requests.post("http://monitor/api/start", json={
        "task": script_path,
        "status": "running"
    })
    
    # 执行渲染
    result = subprocess.run([
        "silhouette", "--headless", "--script", script_path
    ])
    
    # 发送完成通知
    status = "success" if result.returncode == 0 else "failed"
    requests.post("http://monitor/api/complete", json={
        "task": script_path,
        "status": status,
        "exit_code": result.returncode
    })
    
    return result.returncode
```

## 8. 最佳实践

### 8.1 无头模式优化

```bash
# 禁用不必要的功能
silhouette --headless \
    --no-gpu \              # 不需要 GPU 时禁用
    --memory 16G \          # 限制内存
    --script process.py \
    --log output.log \
    --verbose
```

### 8.2 日志管理

```bash
# 日志轮转
silhouette --headless --script render.py --log render_$(date +%Y%m%d_%H%M%S).log

# 日志分级
# --verbose: 详细日志(DEBUG 级别)
# 默认: INFO 级别
```

### 8.3 错误处理最佳实践

```python
#!/usr/bin/env python
"""健壮的无头脚本"""

from fx import *
import sys
import traceback

def main():
    try:
        # 初始化
        setup()
        
        # 执行任务
        process()
        
        # 清理
        cleanup()
        
        print("任务完成")
        sys.exit(0)
        
    except FileNotFoundError as e:
        print(f"文件错误: {e}", file=sys.stderr)
        sys.exit(4)
    except MemoryError:
        print("内存不足", file=sys.stderr)
        sys.exit(5)
    except KeyboardInterrupt:
        print("用户取消", file=sys.stderr)
        sys.exit(8)
    except Exception as e:
        print(f"未知错误: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

def setup():
    """初始化"""
    print("初始化...")

def process():
    """主处理逻辑"""
    print("处理中...")

def cleanup():
    """清理"""
    print("清理中...")

if __name__ == "__main__":
    main()
```

### 8.4 安全性

```bash
# 1. 使用非特权用户运行
su - renderuser -c "silhouette --headless --script render.py"

# 2. 限制资源
ulimit -v 16777216  # 限制虚拟内存 16GB
ulimit -t 3600      # 限制 CPU 时间 1 小时
silhouette --headless --script render.py

# 3. 沙箱环境(可选)
# 使用容器或 chroot 隔离
```

### 8.5 性能监控

```python
import resource
import time

def monitor_resources():
    """监控资源使用"""
    mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    cpu_time = resource.getrusage(resource.RUSAGE_SELF).ru_utime
    print(f"内存: {mem / 1024:.0f} MB, CPU: {cpu_time:.1f}s")

# 在脚本中定期调用
start = time.time()
# ... 执行任务 ...
elapsed = time.time() - start
print(f"用时: {elapsed:.1f}s")
monitor_resources()
```

---

## 附录:常用命令速查

| 任务 | 命令 |
|------|------|
| 查看版本 | `silhouette --version` |
| 查看帮助 | `silhouette --help` |
| 无头执行脚本 | `silhouette --headless --script script.py` |
| 打开项目 | `silhouette --project proj.sfx` |
| 渲染帧范围 | `silhouette --render --frames 1-100` |
| 指定输出 | `silhouette -o /output/` |
| 指定格式 | `silhouette --format exr` |
| 详细日志 | `silhouette --verbose --log out.log` |
| 禁用 GPU | `silhouette --no-gpu` |
| 限制内存 | `silhouette -m 16G` |

> **提示**:生产环境使用无头模式时,务必配置日志记录和退出码检查,确保任务状态可追踪。
