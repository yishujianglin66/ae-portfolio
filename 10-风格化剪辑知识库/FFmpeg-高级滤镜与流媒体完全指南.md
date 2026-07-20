# FFmpeg 高级滤镜与流媒体完全指南

---

## 一、滤镜基础

### 1.1 滤镜语法

```bash
# 基础滤镜语法
ffmpeg -i input.mp4 -vf "滤镜1=参数;滤镜2=参数" output.mp4

# 多个滤镜链式处理
ffmpeg -i input.mp4 -vf "滤镜1=参数,滤镜2=参数,滤镜3=参数" output.mp4

# 滤镜复杂链
ffmpeg -i input.mp4 -filter_complex "[0:v]滤镜1[out1];[out1]滤镜2[out2]" -map "[out2]" output.mp4
```

### 1.2 滤镜分类

| 类别 | 常用滤镜 | 用途 |
|------|---------|------|
| **缩放** | scale, scale2ref | 调整分辨率 |
| **裁剪** | crop | 裁剪画面 |
| **旋转** | rotate, transpose | 旋转/翻转 |
| **调色** | eq, colorchannelmixer, lut | 色彩调整 |
| **降噪** | denoise, hqdn3d | 画面降噪 |
| **锐化** | unsharp, sharpen | 锐化处理 |
| **模糊** | blur, boxblur, gblur | 模糊效果 |
| **水印** | drawtext, overlay | 添加水印/叠加 |

---

## 二、视频滤镜详解

### 2.1 缩放滤镜

```bash
# 基础缩放
ffmpeg -i input.mp4 -vf "scale=1920:1080" output.mp4

# 保持宽高比缩放
ffmpeg -i input.mp4 -vf "scale=1920:-1" output.mp4

# 按比例缩放
ffmpeg -i input.mp4 -vf "scale=iw*0.5:ih*0.5" output.mp4

# 对比缩放（参考另一路视频）
ffmpeg -i video1.mp4 -i video2.mp4 -filter_complex \
    "[1:v]scale=1920:1080[ref];[0:v]scale2ref=1920:1080[main][ref]" \
    -map "[main]" output.mp4
```

### 2.2 裁剪滤镜

```bash
# 基础裁剪 (x:y:width:height)
ffmpeg -i input.mp4 -vf "crop=1280:720:0:0" output.mp4

# 居中裁剪
ffmpeg -i input.mp4 -vf "crop=1280:720" output.mp4

# 动态裁剪
ffmpeg -i input.mp4 -vf "crop=in_w-100:in_h-100:50:50" output.mp4

# 比例裁剪（16:9）
ffmpeg -i input.mp4 -vf "crop=ih*16/9:ih" output.mp4
```

### 2.3 旋转与翻转

```bash
# 旋转90度（顺时针）
ffmpeg -i input.mp4 -vf "transpose=1" output.mp4

# 旋转90度（逆时针）
ffmpeg -i input.mp4 -vf "transpose=2" output.mp4

# 水平翻转
ffmpeg -i input.mp4 -vf "hflip" output.mp4

# 垂直翻转
ffmpeg -i input.mp4 -vf "vflip" output.mp4

# 任意角度旋转
ffmpeg -i input.mp4 -vf "rotate=45*PI/180" output.mp4
```

---

## 三、色彩调整滤镜

### 3.1 基础色彩调整

```bash
# 亮度、对比度、饱和度
ffmpeg -i input.mp4 -vf "eq=brightness=0.2:contrast=1.5:saturation=1.3" output.mp4

# Gamma校正
ffmpeg -i input.mp4 -vf "eq=gamma=1.2" output.mp4

# 色相调整
ffmpeg -i input.mp4 -vf "hue=h=90" output.mp4

# 色彩通道混合
ffmpeg -i input.mp4 -vf "colorchannelmixer=rr=0.9:rg=0:rb=0:gr=0:gg=1.1:gb=0:br=0:bg=0:bb=1.0" output.mp4
```

### 3.2 高级调色

```bash
# 使用LUT调色
ffmpeg -i input.mp4 -vf "lut3d=cinematic.lut" output.mp4

# 曲线调整
ffmpeg -i input.mp4 -vf "curves=vintage" output.mp4

# 自定义曲线
ffmpeg -i input.mp4 -vf "curves=master='0/0.1 0.5/0.4 1/1'" output.mp4

# 颜色空间转换
ffmpeg -i input.mp4 -vf "colorspace=bt709:iall=bt601-6-625:fast=1" output.mp4
```

---

## 四、降噪与锐化

### 4.1 降噪滤镜

```bash
# 基础降噪
ffmpeg -i input.mp4 -vf "hqdn3d=4.0:3.0:6.0:4.5" output.mp4

# 时域降噪
ffmpeg -i input.mp4 -vf "tdenoise=4.0:1.0:0.0" output.mp4

# 双边滤波降噪
ffmpeg -i input.mp4 -vf "bilateral=5:0.1" output.mp4

# 降噪+锐化组合
ffmpeg -i input.mp4 -vf "hqdn3d=3.0:2.0:5.0:3.5,unsharp=5:5:1.0" output.mp4
```

### 4.2 锐化滤镜

```bash
# 基础锐化
ffmpeg -i input.mp4 -vf "unsharp=5:5:1.0" output.mp4

# 高斯锐化
ffmpeg -i input.mp4 -vf "sharpen=1.0" output.mp4

# 边缘增强
ffmpeg -i input.mp4 -vf "edgeenhance" output.mp4

# 智能锐化
ffmpeg -i input.mp4 -vf "smartblur=luma_radius=1.0:luma_strength=2.0" output.mp4
```

---

## 五、水印与叠加

### 5.1 文字水印

```bash
# 基础文字水印
ffmpeg -i input.mp4 -vf "drawtext=text='Watermark':fontsize=24:fontcolor=white:x=10:y=10" output.mp4

# 带阴影的文字水印
ffmpeg -i input.mp4 -vf "drawtext=text='Watermark':fontsize=24:fontcolor=white:shadowcolor=black:shadowx=2:shadowy=2:x=10:y=10" output.mp4

# 动态时间戳水印
ffmpeg -i input.mp4 -vf "drawtext=text='%{localtime\:%Y-%m-%d %H\:%M\:%S}':fontsize=20:fontcolor=white:x=10:y=10" output.mp4

# 右下角水印
ffmpeg -i input.mp4 -vf "drawtext=text='Copyright':fontsize=24:fontcolor=white:x=w-text_w-10:y=h-text_h-10" output.mp4
```

### 5.2 图片水印

```bash
# 基础图片水印
ffmpeg -i input.mp4 -i logo.png -vf "overlay=10:10" output.mp4

# 右下角图片水印
ffmpeg -i input.mp4 -i logo.png -vf "overlay=main_w-overlay_w-10:main_h-overlay_h-10" output.mp4

# 半透明水印
ffmpeg -i input.mp4 -i logo.png -filter_complex "[1:v]format=rgba,colorchannelmixer=aa=0.5[logo];[0:v][logo]overlay=10:10" output.mp4

# 多个水印
ffmpeg -i input.mp4 -i logo1.png -i logo2.png -filter_complex \
    "[0:v][1:v]overlay=10:10[tmp];[tmp][2:v]overlay=W-w-10:H-h-10" output.mp4
```

---

## 六、复杂滤镜链

### 6.1 多输入滤镜

```bash
# 视频拼接
ffmpeg -i input1.mp4 -i input2.mp4 -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0" output.mp4

# 画中画
ffmpeg -i main.mp4 -i small.mp4 -filter_complex \
    "[1:v]scale=320:240[small];[0:v][small]overlay=10:10" output.mp4

# 左右分屏
ffmpeg -i video1.mp4 -i video2.mp4 -filter_complex \
    "[0:v]scale=960:540[v1];[1:v]scale=960:540[v2];[v1][v2]hstack" output.mp4

# 上下分屏
ffmpeg -i video1.mp4 -i video2.mp4 -filter_complex \
    "[0:v]scale=1920:540[v1];[1:v]scale=1920:540[v2];[v1][v2]vstack" output.mp4
```

### 6.2 多输出滤镜

```bash
# 同时输出多种分辨率
ffmpeg -i input.mp4 -filter_complex \
    "[0:v]scale=1920:1080[hd];[0:v]scale=1280:720[sd];[0:v]scale=640:360[low]" \
    -map "[hd]" hd_output.mp4 \
    -map "[sd]" sd_output.mp4 \
    -map "[low]" low_output.mp4
```

---

## 七、音频滤镜

### 7.1 基础音频滤镜

```bash
# 音量调整
ffmpeg -i input.mp4 -af "volume=2.0" output.mp4

# 音频淡入淡出
ffmpeg -i input.mp4 -af "afade=t=in:st=0:d=3,afade=t=out:st=10:d=3" output.mp4

# 音频均衡器
ffmpeg -i input.mp4 -af "equalizer=f=1000:t=q:w=1:g=5" output.mp4

# 音频压缩
ffmpeg -i input.mp4 -af "acompressor=threshold=-20dB:ratio=4:attack=5:release=50" output.mp4
```

### 7.2 降噪与修复

```bash
# 音频降噪
ffmpeg -i input.mp4 -af "highpass=f=200,lowpass=f=3000" output.mp4

# 去除静音
ffmpeg -i input.mp4 -af "silenceremove=start_periods=1:start_duration=0.5:start_threshold=-60dB" output.mp4

# 音频延迟
ffmpeg -i input.mp4 -af "adelay=1000|1000" output.mp4

# 音频混响
ffmpeg -i input.mp4 -af "aecho=0.8:0.9:1000:0.3" output.mp4
```

---

## 八、流媒体

### 8.1 推流到RTMP服务器

```bash
# 推流到RTMP服务器
ffmpeg -i input.mp4 -c:v libx264 -c:a aac -f flv rtmp://server/live/stream

# 实时推流（摄像头）
ffmpeg -f dshow -i video="摄像头名称":audio="麦克风名称" \
    -c:v libx264 -c:a aac -f flv rtmp://server/live/stream

# 推流时添加水印
ffmpeg -i input.mp4 -vf "drawtext=text='Live':fontsize=30:fontcolor=red" \
    -c:v libx264 -c:a aac -f flv rtmp://server/live/stream
```

### 8.2 HLS流媒体

```bash
# 生成HLS播放列表
ffmpeg -i input.mp4 -c:v libx264 -c:a aac -hls_time 10 -hls_list_size 0 output.m3u8

# HLS加密
ffmpeg -i input.mp4 -c:v libx264 -c:a aac -hls_time 10 -hls_key_info_file key_info.txt output.m3u8

# HLS多码率
ffmpeg -i input.mp4 -filter_complex \
    "[0:v]scale=1920:1080[hd];[0:v]scale=1280:720[sd];[0:v]scale=640:360[low]" \
    -map "[hd]" -c:v:0 libx264 -b:v:0 5M \
    -map "[sd]" -c:v:1 libx264 -b:v:1 2M \
    -map "[low]" -c:v:2 libx264 -b:v:2 1M \
    -map 0:a -c:a aac -b:a 128k \
    -hls_time 10 -hls_list_size 0 -master_pl_name master.m3u8 \
    -var_stream_map "v:0,a:0,name:hd v:1,a:0,name:sd v:2,a:0,name:low" \
    output_%v.m3u8
```

### 8.3 DASH流媒体

```bash
# 生成DASH播放列表
ffmpeg -i input.mp4 -c:v libx264 -c:a aac -f dash output.mpd

# DASH多码率
ffmpeg -i input.mp4 -filter_complex \
    "[0:v]scale=1920:1080[hd];[0:v]scale=1280:720[sd]" \
    -map "[hd]" -c:v:0 libx264 -b:v:0 5M \
    -map "[sd]" -c:v:1 libx264 -b:v:1 2M \
    -map 0:a -c:a aac -b:a 128k \
    -f dash -seg_duration 10 output.mpd
```

---

## 九、批处理脚本

### 9.1 批量转码

```bash
# Windows批处理 - 批量转码为H.264
@echo off
for %%f in (*.mp4) do (
    ffmpeg -i "%%f" -c:v libx264 -c:a aac "output\%%~nf_h264.mp4"
)
```

```python
# Python脚本 - 批量转码
import subprocess
import os

def batch_convert(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    
    for filename in os.listdir(input_folder):
        if filename.endswith('.mp4'):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename.replace('.mp4', '_converted.mp4'))
            
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264', '-c:a', 'aac',
                '-crf', '23', output_path
            ]
            
            subprocess.run(cmd, check=True)
```

### 9.2 批量添加水印

```python
# Python脚本 - 批量添加水印
import subprocess
import os

def batch_add_watermark(input_folder, output_folder, watermark_text):
    os.makedirs(output_folder, exist_ok=True)
    
    for filename in os.listdir(input_folder):
        if filename.endswith('.mp4'):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)
            
            cmd = [
                'ffmpeg', '-i', input_path,
                '-vf', f"drawtext=text='{watermark_text}':fontsize=24:fontcolor=white:x=10:y=10",
                '-c:a', 'copy', output_path
            ]
            
            subprocess.run(cmd, check=True)
```

---

## 十、性能优化

### 10.1 硬件加速

```bash
# NVIDIA NVENC加速
ffmpeg -i input.mp4 -c:v h264_nvenc -c:a aac output.mp4

# Intel QSV加速
ffmpeg -i input.mp4 -c:v h264_qsv -c:a aac output.mp4

# AMD AMF加速
ffmpeg -i input.mp4 -c:v h264_amf -c:a aac output.mp4

# GPU解码+GPU编码
ffmpeg -hwaccel cuda -i input.mp4 -c:v h264_nvenc -c:a aac output.mp4
```

### 10.2 编码优化

```bash
# 高质量编码（慢但质量好）
ffmpeg -i input.mp4 -c:v libx264 -preset slow -crf 18 -c:a aac output.mp4

# 快速编码（快但质量一般）
ffmpeg -i input.mp4 -c:v libx264 -preset fast -crf 23 -c:a aac output.mp4

# 使用多个线程
ffmpeg -i input.mp4 -c:v libx264 -threads 8 -c:a aac output.mp4

# 零拷贝模式
ffmpeg -i input.mp4 -c copy -map 0 output.mp4
```

---

> **关联文档**：
> - [[FFmpeg-命令行工具与流媒体核心功能完全指南]]
> - [[Phase1-预处理全链路技术详解]]