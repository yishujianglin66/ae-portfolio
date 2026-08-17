# Blender脚本日志输出

## 问题场景

Blender background模式执行脚本时，所有输出通过stdout/stderr。需要设计结构化的日志系统，便于后续分析和错误定位。本项目使用subprocess调用Blender，日志解析是调试的关键。

## 核心原理

### 基本输出

```python
import bpy
import sys

# 基本打印（输出到stdout）
print("Script started")
print(f"Blender version: {bpy.app.version_string}")

# 错误输出（输出到stderr）
print("Error message", file=sys.stderr)

# 刷新输出（确保立即显示）
print("Progress...", flush=True)
```

### 结构化日志

```python
import logging
import sys
from datetime import datetime

class BlenderLogger:
    """Blender脚本日志器"""
    
    LEVELS = {
        'DEBUG': 0,
        'INFO': 1,
        'WARNING': 2,
        'ERROR': 3,
    }
    
    def __init__(self, name="blender_script", level='INFO', 
                 log_file=None):
        self.name = name
        self.level = self.LEVELS.get(level, 1)
        self.log_file = log_file
        self._file_handle = None
        
        if log_file:
            self._file_handle = open(log_file, 'w', encoding='utf-8')
    
    def _output(self, level, msg):
        if self.LEVELS[level] < self.level:
            return
        
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        line = f"[{timestamp}] [{level}] [{self.name}] {msg}"
        
        # 控制台输出
        print(line, flush=True)
        
        # 文件输出
        if self._file_handle:
            self._file_handle.write(line + '\n')
            self._file_handle.flush()
    
    def debug(self, msg):
        self._output('DEBUG', msg)
    
    def info(self, msg):
        self._output('INFO', msg)
    
    def warning(self, msg):
        self._output('WARNING', msg)
    
    def error(self, msg):
        self._output('ERROR', msg)
    
    def close(self):
        if self._file_handle:
            self._file_handle.close()

# 使用
logger = BlenderLogger("cel_render", level='DEBUG')
logger.info("Pipeline started")
logger.debug(f"Objects: {len(bpy.data.objects)}")
logger.close()
```

### 日志格式约定

```python
# 本项目日志格式约定：
# [PHASE] 阶段标记
# [OK] 成功操作
# [WARN] 警告
# [ERROR] 错误
# [DEBUG] 调试信息

# 示例：
print("[PHASE] FBX Import")
print("[OK] Imported 15 mesh objects")
print("[WARN] Texture not found: body_diffuse.png")
print("[ERROR] Armature creation failed: bone 'Hips' not found")
print("[DEBUG] Vertex count: 45230")

# 进度标记
print("[PROGRESS] 10/60 frames rendered")
```

### 阶段标记

```python
class PhaseLogger:
    """阶段日志器"""
    
    def __init__(self, logger):
        self.logger = logger
        self.phase_start = None
    
    def start(self, phase_name):
        import time
        self.phase_start = time.time()
        self.logger.info(f"[PHASE START] {phase_name}")
    
    def end(self, phase_name):
        import time
        elapsed = time.time() - self.phase_start
        self.logger.info(f"[PHASE END] {phase_name} ({elapsed:.2f}s)")
    
    def step(self, msg):
        self.logger.info(f"  [STEP] {msg}")

# 使用
phases = PhaseLogger(logger)
phases.start("FBX Import")
phases.step("Loading file...")
phases.step("Processing meshes...")
phases.end("FBX Import")
```

### 数据dump

```python
import json

def dump_scene_state(output_file):
    """导出场景状态到JSON"""
    state = {
        "objects": [],
        "materials": [],
        "render_settings": {},
    }
    
    for obj in bpy.data.objects:
        obj_info = {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
        }
        if obj.type == 'MESH':
            obj_info["vertices"] = len(obj.data.vertices)
            obj_info["faces"] = len(obj.data.polygons)
            obj_info["materials"] = [
                m.name for m in obj.data.materials if m]
        state["objects"].append(obj_info)
    
    scene = bpy.context.scene
    state["render_settings"] = {
        "engine": scene.render.engine,
        "resolution": [scene.render.resolution_x, 
                       scene.render.resolution_y],
        "frame_range": [scene.frame_start, scene.frame_end],
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] Scene state dumped to {output_file}")
```

### 条件日志

```python
# 通过环境变量控制日志级别
import os

LOG_LEVEL = os.environ.get('BLENDER_LOG_LEVEL', 'INFO')
DEBUG_MODE = os.environ.get('BLENDER_DEBUG', '0') == '1'

def log(msg, level='INFO'):
    levels = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3}
    if levels.get(level, 1) >= levels.get(LOG_LEVEL, 1):
        print(f"[{level}] {msg}", flush=True)

# 使用
log("Detailed info", 'DEBUG')  # 只在DEBUG级别显示
log("Normal info", 'INFO')
log("Something wrong", 'WARNING')
```

## 常见陷阱

### 陷阱1：输出缓冲
```python
# print默认有缓冲，崩溃时可能丢失日志
# 解决：使用flush=True
print("Important message", flush=True)

# 或设置环境变量
# PYTHONUNBUFFERED=1
```

### 陷阱2：中文编码
```python
# Windows控制台可能不支持中文
# 解决：日志文件使用UTF-8
with open(log_file, 'w', encoding='utf-8') as f:
    f.write("中文日志\n")
```

## 本项目代码关联

`cel_shading.py`：
- 全文使用print输出日志
- [PHASE]/[OK]/[WARN]/[ERROR]标记

`engine.py` L900-1000：
- subprocess捕获stdout/stderr
- 解析日志判断成功/失败

## 版本兼容性

- 日志系统与Blender版本无关
- Python logging模块通用

## 参考链接

- [Python Logging](https://docs.python.org/3/library/logging.html)
- [Blender Command Line](https://docs.blender.org/manual/en/latest/advanced/command_line/index.html)
