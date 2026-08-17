# Background模式脚本执行

## 问题场景

Blender的`--background`模式无GUI，所有操作必须通过Python脚本完成。理解background模式的限制和正确用法是自动化渲染的基础。

## 核心原理

### 启动命令

```bash
# 基本用法
blender --background --python script.py

# 带参数
blender --background --python script.py -- --input model.fbx --output frames/

# 指定Python版本（Blender内置）
"D:\Blender\Blender 5.1.0\blender.exe" --background --python script.py
```

### Background模式的限制

| 功能 | GUI模式 | Background模式 |
|------|:---:|:---:|
| 渲染 | ✅ | ✅ |
| 脚本执行 | ✅ | ✅ |
| Viewport交互 | ✅ | ❌ |
| Weight Paint | ✅ | ❌ |
| 弹窗/对话框 | ✅ | ❌ |
| 预览渲染 | ✅ | ❌ |
| 文件I/O | ✅ | ✅ |

### 脚本结构模板

```python
import bpy
import sys
import os

def main():
    """主函数"""
    # 1. 清空场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    # 2. 导入模型
    bpy.ops.import_scene.fbx(filepath="model.fbx")
    
    # 3. 设置材质/灯光/相机
    setup_scene()
    
    # 4. 渲染
    bpy.ops.render.render(animation=True)
    
    # 5. 写入成功标记
    with open("render_complete.marker", "w") as f:
        f.write("success")

if __name__ == "__main__":
    main()
```

### 从外部Python调用Blender

```python
import subprocess
import os

def run_blender_script(script_path, blend_file=None):
    """从外部Python调用Blender执行脚本"""
    blender_exe = r"D:\Blender\Blender 5.1.0\blender.exe"
    
    cmd = [blender_exe, "--background"]
    if blend_file:
        cmd.append(blend_file)
    cmd.extend(["--python", script_path])
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300  # 5分钟超时
    )
    
    success = result.returncode == 0
    return success, result.stdout, result.stderr
```

### 日志输出

```python
# background模式下print输出到stdout
print(">>> [INFO] Starting render...")

# 错误输出到stderr
import sys
print(">>> [ERROR] Something failed", file=sys.stderr)

# 日志会被subprocess捕获
# stdout: 正常日志
# stderr: 错误信息 + Blender警告
```

## 常见陷阱

### 陷阱1：脚本路径含中文/空格
```python
# 错误：
cmd = f"blender --background --python {script_path}"
# 如果script_path含空格 → 命令解析错误

# 正确：使用列表形式
cmd = [blender_exe, "--background", "--python", script_path]
subprocess.run(cmd)  # 自动处理引号
```

### 陷阱2：Blender退出码
```python
# 脚本异常 → 退出码=1
# 脚本正常完成 → 退出码=0
# 渲染失败但脚本未异常 → 退出码=0（需额外检查）
```

## 本项目代码关联

`engine.py` L1060-1120：
- 调用Blender background模式
- 检查退出码和marker文件
- `success = code == 0 and marker_path.exists()`

## 版本兼容性

- Blender 4.x/5.x: --background模式行为一致
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender Manual: Command Line Arguments](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html)
