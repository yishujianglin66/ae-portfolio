# try/except异常隔离策略

## 问题场景

Blender脚本中某个步骤失败不应导致整个管线崩溃。需要合理的异常隔离策略：捕获特定错误、记录上下文、尝试恢复或优雅降级。本项目v12的NameError就是因为缺少异常隔离。

## 核心原理

### 基本异常处理

```python
import bpy
import traceback

# 基本结构
try:
    # 可能失败的代码
    result = risky_operation()
except SpecificError as e:
    # 处理特定错误
    print(f"[ERROR] {e}")
except Exception as e:
    # 处理其他错误
    print(f"[FATAL] {type(e).__name__}: {e}")
    traceback.print_exc()
else:
    # 无异常时执行
    print("[OK] Operation succeeded")
finally:
    # 总是执行（清理）
    cleanup()
```

### 管线步骤隔离

```python
class PipelineStep:
    """管线步骤包装器"""
    
    def __init__(self, name, func, required=True):
        self.name = name
        self.func = func
        self.required = required  # 是否必须成功
    
    def execute(self, *args, **kwargs):
        print(f"[STEP] {self.name}")
        try:
            result = self.func(*args, **kwargs)
            print(f"[OK] {self.name}")
            return True, result
        except Exception as e:
            print(f"[ERROR] {self.name}: {e}")
            traceback.print_exc()
            
            if self.required:
                raise  # 必须步骤，重新抛出
            else:
                return False, None  # 可选步骤，继续

# 使用
steps = [
    PipelineStep("FBX Import", import_fbx, required=True),
    PipelineStep("Bone Creation", create_bones, required=True),
    PipelineStep("Weight Assignment", assign_weights, required=True),
    PipelineStep("Weapon Reposition", reposition_weapon, required=False),
    PipelineStep("Render", render_scene, required=True),
]

for step in steps:
    success, result = step.execute()
    if not success and step.required:
        print(f"[FATAL] Required step failed: {step.name}")
        break
```

### 上下文保存与恢复

```python
import copy

class StateCheckpoint:
    """状态检查点"""
    
    def __init__(self):
        self.saved_state = None
    
    def save(self):
        """保存当前状态"""
        self.saved_state = {
            'objects': {obj.name: {
                'location': obj.location.copy(),
                'rotation': obj.rotation_euler.copy(),
                'scale': obj.scale.copy(),
            } for obj in bpy.data.objects},
            'frame': bpy.context.scene.frame_current,
        }
        print("[CHECKPOINT] State saved")
    
    def restore(self):
        """恢复状态"""
        if not self.saved_state:
            return
        
        for name, state in self.saved_state['objects'].items():
            obj = bpy.data.objects.get(name)
            if obj:
                obj.location = state['location']
                obj.rotation_euler = state['rotation']
                obj.scale = state['scale']
        
        bpy.context.scene.frame_set(self.saved_state['frame'])
        print("[CHECKPOINT] State restored")

# 使用
checkpoint = StateCheckpoint()
checkpoint.save()

try:
    risky_operation()
except Exception as e:
    print(f"[ERROR] {e}, restoring state...")
    checkpoint.restore()
```

### 重试机制

```python
import time

def retry(func, max_retries=3, delay=1.0, exceptions=(Exception,)):
    """重试装饰器"""
    for attempt in range(max_retries):
        try:
            return func()
        except exceptions as e:
            if attempt == max_retries - 1:
                raise
            print(f"[RETRY] Attempt {attempt+1}/{max_retries} failed: {e}")
            time.sleep(delay)
            delay *= 2  # 指数退避

# 使用
def render_frame():
    bpy.ops.render.render(write_still=True)

retry(render_frame, max_retries=3, exceptions=(RuntimeError,))
```

### 优雅降级

```python
def setup_rendering_with_fallback():
    """渲染设置（带降级）"""
    scene = bpy.context.scene
    
    # 尝试EEVEE Next
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
        scene.eevee.taa_render_samples = 64
        print("[OK] Using EEVEE Next")
        return 'EEVEE_NEXT'
    except:
        pass
    
    # 降级到旧版EEVEE
    try:
        scene.render.engine = 'BLENDER_EEVEE'
        scene.eevee.taa_render_samples = 64
        print("[OK] Using EEVEE (legacy)")
        return 'EEVEE'
    except:
        pass
    
    # 最终降级到Cycles
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    print("[WARN] Fallback to Cycles")
    return 'CYCLES'
```

### 变量定义保护（v12 NameError案例）

```python
# 错误示例（v12的问题）：
if not _v12_no_reposition:
    _bc = calculate_bounds_center(weapon)  # 条件内定义
    # ...

# 后面无条件使用
weapon.location = hand_pos - _bc  # NameError if _v12_no_reposition=True!

# 正确示例：
# 方法1：提前定义默认值
_bc = Vector((0, 0, 0))  # 默认值
if not _v12_no_reposition:
    _bc = calculate_bounds_center(weapon)

# 方法2：条件保护使用
if not _v12_no_reposition:
    _bc = calculate_bounds_center(weapon)
    weapon.location = hand_pos - _bc
# else: 跳过整个逻辑

# 方法3：函数封装
def get_bounds_center(obj, fallback=Vector((0,0,0))):
    try:
        return calculate_bounds_center(obj)
    except:
        return fallback
```

### 异常链

```python
# 保留原始异常信息
try:
    import_fbx(filepath)
except FileNotFoundError as e:
    raise RuntimeError(f"FBX file not found: {filepath}") from e

# 输出：
# RuntimeError: FBX file not found: model.fbx
# FileNotFoundError: [Errno 2] No such file or directory: 'model.fbx'
```

## 常见陷阱

### 陷阱1：过宽的except
```python
# 错误：捕获所有异常（包括KeyboardInterrupt）
try:
    operation()
except:  # 太宽泛！
    pass

# 正确：
try:
    operation()
except (RuntimeError, ValueError) as e:
    handle_error(e)
```

### 陷阱2：except中再次出错
```python
try:
    operation()
except Exception as e:
    # 这里的代码也可能出错！
    log_error(e)  # 如果log_error出错，原始异常丢失
    
# 解决：嵌套try
except Exception as e:
    try:
        log_error(e)
    except:
        print(f"Fallback log: {e}")
```

## 本项目代码关联

`cel_shading.py`：
- v12 NameError案例（_bc未定义）
- 武器归位逻辑缺少异常保护

`engine.py`：
- subprocess错误处理
- 超时机制

## 版本兼容性

- Python异常处理通用
- 与Blender版本无关

## 参考链接

- [Python Exceptions](https://docs.python.org/3/tutorial/errors.html)
- [Python try/except](https://docs.python.org/3/reference/compound_stmts.html#try)
