# Media Encoder 编码参数与预设完全指南

> 版本: 2025-v1 | 适用: 视频编码/格式输出/批量渲染

## 一、编码格式详解

### 1.1 H.264 (AVC)

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| Profile | 编码复杂度 | High(高质量)/Main(兼容) |
| Level | 分辨率/帧率上限 | 4.2(1080p)/5.2(4K) |
| Bitrate | 码率控制 | VBR 1pass |
| Target | 目标码率 | 10-20Mbps(1080p) |
| Max | 最大码率 | 1.5x Target |
| Keyframe | 关键帧间隔 | 2x帧率 |
| B-frames | 双向预测帧 | 3 |

### 1.2 H.265 (HEVC)

| 对比 | H.264 | H.265 |
|------|-------|-------|
| 压缩效率 | 基准 | 提升50% |
| 同质量码率 | 100% | 50-60% |
| 编码速度 | 快 | 慢2-3x |
| 兼容性 | 最广 | 新设备支持 |
| 适用 | 网络/通用 | 4K/HDR/存档 |

### 1.3 ProRes

| 变体 | 码率(1080p24) | 用途 |
|------|--------------|------|
| Proxy | ~45Mbps | 代理编辑 |
| LT | ~102Mbps | 轻量编辑 |
| 422 | ~132Mbps | 标准编辑 |
| 422 HQ | ~220Mbps | 高质量编辑 |
| 4444 | ~330Mbps | 含Alpha通道 |
| 4444 XQ | ~500Mbps | 最高质量 |

### 1.4 DNxHR

| 变体 | 用途 | 质量 |
|------|------|------|
| DNxHR LB | 代理 | 最低 |
| DNxHR SQ | 标准编辑 | 中等 |
| DNxHR HQ | 高质量 | 高 |
| DNxHR HQX | 12bit高质量 | 极高 |
| DNxHR 444 | 含Alpha | 最高 |

## 二、AME预设管理

### 2.1 内置预设

| 类别 | 预设 | 用途 |
|------|------|------|
| H.264 | YouTube 1080p | 网络发布 |
| H.264 | 匹配源-高码率 | 通用高质量 |
| HEVC | 4K匹配源 | 4K高效压缩 |
| ProRes | ProRes 422 LT | Mac编辑 |
| DNxHR | DNxHR SQ | Win编辑 |
| MPEG | MPEG2 DVD | 光盘 |
| 音频 | MP3 320kbps | 音频导出 |

### 2.2 自定义预设

```
创建自定义预设:
1. 设置好导出参数
2. 点击"导出设置"面板底部
3. 点击"保存预设"按钮
4. 命名并选择分类
5. 可导出为.epr文件分享

预设文件位置:
Windows: C:\Users\[用户名]\AppData\Roaming\Adobe\Common\Encoder Presets
Mac: ~/Library/Application Support/Adobe/Common/Encoder Presets
```

### 2.3 预设导入/导出

```
导出预设:
1. 预设浏览器 → 选择预设
2. 右键 → 导出预设
3. 保存.epr文件

导入预设:
1. 预设浏览器 → 导入预设
2. 选择.epr文件
3. 预设出现在列表中
```

## 三、批量渲染

### 3.1 Watch Folder(监视文件夹)

```
设置监视文件夹:
1. 编辑 → 首选项 → 常规
2. 设置监视文件夹路径
3. 将待渲染文件放入该文件夹
4. AME自动检测并开始渲染
5. 使用预设匹配源或默认预设

适用场景:
- 团队协作自动渲染
- 多项目批量输出
- 定时任务渲染
```

### 3.2 队列管理

```
队列操作:
1. 从PR发送到AME队列
2. 或直接在AME中导入文件
3. 为每个项目选择预设
4. 调整渲染顺序(拖拽)
5. 点击"开始队列"

并行渲染:
- 编辑 → 首选项 → 常规
- 启用"同时编码多个文件"
- 设置最大并行任务数(CPU核心/4)
```

## 四、编码质量评估

### 4.1 质量指标

| 指标 | 说明 | 工具 |
|------|------|------|
| PSNR | 峰值信噪比 | 越高越好(>40dB) |
| SSIM | 结构相似度 | 接近1为好 |
| VMAF | 感知质量 | Netflix开发(0-100) |
| 文件大小 | 输出体积 | 码率决定 |
| 编码时间 | 渲染耗时 | 硬件/设置决定 |

### 4.2 码率与质量关系

```
1080p参考码率:
- 2Mbps: 低质量(手机观看)
- 5Mbps: 中等(网络流畅)
- 10Mbps: 高质量(YouTube推荐)
- 20Mbps: 极高(接近无损)
- 50Mbps+: 母版级

4K参考码率:
- 10Mbps: 低质量
- 20Mbps: 中等
- 35-50Mbps: 高质量(YouTube推荐)
- 100Mbps+: 母版级
```

## 五、API自动化

### 5.1 命令行渲染

```
# 基本渲染
MediaEncoder.exe -input "input.mp4" -preset "H.264 Match Source - High bitrate"

# 批量渲染
for %f in (*.mp4) do MediaEncoder.exe -input "%f" -preset "YouTube 1080p"

# 指定输出
MediaEncoder.exe -input "input.mp4" -output "output.mp4" -preset "H.264 Match Source"
```

### 5.2 Watch Folder自动化脚本

```python
# watch_folder_render.py
import os, shutil, time

watch_folder = r"C:\AME_Watch"
done_folder = r"C:\AME_Done"

while True:
    files = [f for f in os.listdir(watch_folder) if f.endswith(('.mp4', '.mov'))]
    for f in files:
        src = os.path.join(watch_folder, f)
        # AME会自动检测并渲染
        print(f"Detected: {f}")
    time.sleep(5)
```
