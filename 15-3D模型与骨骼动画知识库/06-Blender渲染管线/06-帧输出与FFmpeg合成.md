# 帧输出与FFmpeg合成

## 问题场景

Blender渲染输出PNG序列帧后，需要用FFmpeg合成为视频（MP4）。需要正确配置输出路径、帧命名、FFmpeg参数。

## 核心原理

### Blender帧输出

```python
import bpy
import os

def setup_frame_output(output_dir, frame_start=1, frame_end=60):
    """配置帧输出"""
    scene = bpy.context.scene
    
    os.makedirs(output_dir, exist_ok=True)
    
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    
    # PNG序列（带Alpha通道）
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.compression = 15  # PNG压缩级别
    
    # 输出路径（Blender自动添加帧号）
    scene.render.filepath = os.path.join(output_dir, "frame_")
    # 输出: frame_0001.png, frame_0002.png, ...

def render_frames():
    """渲染所有帧"""
    bpy.ops.render.render(animation=True)  # 渲染帧范围
```

### FFmpeg合成

```python
import subprocess
import os

def frames_to_video(frames_dir, output_path, fps=30, resolution=(1920, 1080)):
    """
    用FFmpeg将PNG序列合成为MP4
    """
    # 帧文件模式
    frame_pattern = os.path.join(frames_dir, "frame_%04d.png")
    
    # FFmpeg命令
    cmd = [
        "ffmpeg",
        "-y",  # 覆盖输出
        "-framerate", str(fps),
        "-i", frame_pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",  # 质量（0-51，越小越好）
        "-preset", "medium",
        "-vf", f"scale={resolution[0]}:{resolution[1]}",
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"[FFmpeg] Video created: {output_path}")
        return True
    else:
        print(f"[FFmpeg] Error: {result.stderr}")
        return False
```

### 带Alpha通道的合成

```python
def frames_to_video_with_alpha(frames_dir, output_path, fps=30):
    """导出带Alpha通道的视频（WebM格式）"""
    frame_pattern = os.path.join(frames_dir, "frame_%04d.png")
    
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate", str(fps),
        "-i", frame_pattern,
        "-c:v", "libvpx-vp9",  # VP9支持Alpha
        "-pix_fmt", "yuva420p",  # 带Alpha的像素格式
        "-b:v", "2M",
        output_path.replace(".mp4", ".webm")
    ]
    
    subprocess.run(cmd, capture_output=True)
```

### 帧文件验证

```python
def validate_frames(frames_dir, expected_count):
    """验证帧文件完整性"""
    import glob
    
    frames = sorted(glob.glob(os.path.join(frames_dir, "frame_*.png")))
    
    if len(frames) != expected_count:
        print(f"[WARN] Expected {expected_count} frames, found {len(frames)}")
        return False
    
    # 检查文件大小（排除空文件）
    for f in frames:
        size = os.path.getsize(f)
        if size < 1000:  # 小于1KB可能是空帧
            print(f"[WARN] Suspicious frame: {f} ({size} bytes)")
    
    print(f"[OK] {len(frames)} frames validated")
    return True
```

## 常见陷阱

### 陷阱1：FFmpeg找不到帧文件
```python
# 帧号必须从1开始且连续
# frame_0001.png, frame_0002.png, ...
# 不能跳帧！
```

### 陷阱2：视频颜色偏差
```python
# PNG是RGB，视频是YUV
# 添加 -pix_fmt yuv420p 确保兼容性
```

## 本项目代码关联

`engine.py`：
- 渲染后调用FFmpeg合成
- 输出MP4到成品库

## 版本兼容性

- FFmpeg 5.x/6.x: 命令参数兼容
- Blender 5.1.0 Alpha: PNG输出测试通过

## 参考链接

- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [Blender Manual: Output Settings](https://docs.blender.org/manual/en/latest/render/output.html)
