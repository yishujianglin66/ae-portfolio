# AE 渲染队列与输出设置完全指南

> 版本: 2025-v1 | 适用: 渲染输出/编码设置/批量渲染

## 一、渲染队列

### 1.1 渲染队列面板

| 功能 | 用途 | 操作 |
|------|------|------|
| 添加到队列 | 添加合成到渲染 | Ctrl+Shift+/ |
| 渲染设置 | 质量/帧率/分辨率 | 点击设置 |
| 输出模块 | 格式/编解码器 | 点击输出 |
| 输出到 | 输出路径 | 选择位置 |

### 1.2 渲染设置

| 设置 | 说明 | 建议 |
|------|------|------|
| 质量 | 最佳/草稿 | 最佳 |
| 分辨率 | 完整/半/四分之一 | 完整 |
| 帧率 | 合成帧率/自定义 | 合成帧率 |
| 帧范围 | 工作区域/指定范围 | 工作区域 |
| 场渲染 | 逐行/上场优先/下场优先 | 逐行 |

### 1.3 批量渲染

```
批量渲染流程:
1. 添加多个合成到队列
2. 为每个合成设置输出
3. 设置输出路径
4. 点击"开始队列"
5. 监控渲染进度

队列管理:
- 调整优先级: 拖拽排序
- 暂停/恢复: 暂停按钮
- 取消任务: 选择→删除
- 查看日志: 信息面板
```

## 二、输出格式

### 2.1 视频格式

| 格式 | 编解码器 | 用途 | 质量 |
|------|---------|------|------|
| QuickTime | ProRes 422/4444 | 后期协作 | 高 |
| QuickTime | Animation | 无损 | 最高 |
| AVI | 无压缩 | 无损 | 最高 |
| AVI | DV | 标清 | 中 |
| MP4 | H.264 | 网络分享 | 中-高 |
| MP4 | H.265 | 高效压缩 | 中-高 |
| MXF | DNxHR/DNxHD | Avid协作 | 高 |

### 2.2 图像序列

| 格式 | 位深 | Alpha | 用途 |
|------|------|-------|------|
| PNG | 8/16-bit | ✅ | 通用序列 |
| TIFF | 8/16-bit | ✅ | 印刷 |
| OpenEXR | 16/32-bit | ✅ | 高质量 |
| JPEG | 8-bit | ❌ | 预览 |
| DPX | 10/12-bit | ❌ | 电影 |

### 2.3 音频输出

| 格式 | 位深 | 用途 |
|------|------|------|
| WAV | 16/24-bit | 高质量音频 |
| AIFF | 16/24-bit | Mac兼容 |
| MP3 | 128-320kbps | 压缩音频 |
| AAC | 可变 | Apple设备 |

## 三、输出模块设置

### 3.1 QuickTime输出

```
QuickTime ProRes输出:
1. 输出模块→QuickTime
2. 格式选项:
   - ProRes 4444: 最高质量(带Alpha)
   - ProRes 422 HQ: 高质量
   - ProRes 422: 标准质量
   - ProRes Proxy: 代理质量
3. 音频: 启用(如需要)
4. 输出路径
5. 添加到队列

ProRes选择指南:
- 4444: 需要Alpha/最高质量
- 422 HQ: 高质量后期
- 422: 标准后期
- Proxy: 代理剪辑
```

### 3.2 H.264输出

```
H.264输出:
1. 输出模块→H.264
2. 视频设置:
   - 配置文件: High
   - 级别: 4.2/5.2
   - 目标比特率: 10-50 Mbps
   - 最大比特率: 15-70 Mbps
3. 音频设置:
   - 格式: AAC
   - 比特率: 192-320 kbps
4. 输出路径
5. 添加到队列

比特率指南:
- 1080p 30fps: 10-15 Mbps
- 1080p 60fps: 15-20 Mbps
- 4K 30fps: 30-40 Mbps
- 4K 60fps: 40-60 Mbps
```

### 3.3 图像序列输出

```
PNG序列输出:
1. 输出模块→PNG序列
2. 颜色: RGB+Alpha(如需要)
3. 深度: 16位/通道(高质量)
4. 输出路径
5. 添加到队列

OpenEXR序列:
1. 输出模块→OpenEXR序列
2. 颜色: RGB+Alpha
3. 深度: 32位/通道
4. 压缩: Zip(推荐)
5. 输出路径
```

## 四、Adobe Media Encoder

### 4.1 发送到AME

```
发送到Media Encoder:
1. 渲染队列→发送到Media Encoder
2. AME自动打开
3. 在AME中设置:
   - 格式
   - 预设
   - 输出位置
4. 开始渲染

优势:
- 后台渲染
- 多格式同时
- 预设管理
- 队列管理
```

### 4.2 AME预设

| 预设 | 格式 | 用途 |
|------|------|------|
| YouTube 1080p | H.264 | YouTube |
| Vimeo 1080p | H.264 | Vimeo |
| 高比特率1080p | H.264 | 高质量 |
| ProRes 422 | QuickTime | 后期 |
| ProRes 4444 | QuickTime | 最高质量 |
| 自定义 | 任意 | 自定义 |

## 五、渲染优化

### 5.1 硬件加速

| 功能 | 设置 | 效果 |
|------|------|------|
| GPU加速 | 项目设置→常规 | 加速效果 |
| 内存分配 | 首选项→内存 | 优化RAM |
| 磁盘缓存 | 首选项→媒体缓存 | 加速预览 |
| 多帧渲染 | 首选项→内存 | 多核利用 |

### 5.2 渲染优化技巧

```
优化渲染速度:
1. 使用代理剪辑
2. 降低预览分辨率
3. 清理媒体缓存
4. 关闭不必要的效果
5. 使用渲染和替换
6. 预渲染复杂段落
7. 使用GPU加速
8. 增加内存分配

优化渲染质量:
1. 使用32位/通道
2. 启用色彩管理
3. 使用无损格式
4. 避免过度压缩
5. 检查场渲染设置
```

## 六、自动化渲染

### 6.1 ExtendScript渲染

```javascript
// render_script.jsx
var comp = app.project.item(1);
var renderQueue = app.project.renderQueue;

// 添加合成到渲染队列
var renderQueueItem = renderQueue.items.add(comp);

// 设置输出模块
var outputModule = renderQueueItem.outputModule(1);
outputModule.file = new File("/exports/output.mp4");

// 设置渲染设置
var renderSettings = renderQueueItem.getSettings();
renderSettings.quality = "Best Settings";
renderSettings.resolution = "Full";
renderQueueItem.setSettings(renderSettings);

// 开始渲染
renderQueue.startRendering();
```

### 6.2 命令行渲染

```bash
# 命令行渲染
aerender -project "project.aep" -comp "Composition 1" -output "output.mp4"

# 批量渲染
aerender -project "project.aep" -rqindex 1-5

# 使用模板
aerender -project "project.aep" -template "H.264"
```

## 七、最佳实践

### 7.1 渲染检查清单

- [ ] 合成设置正确
- [ ] 帧范围正确
- [ ] 输出格式选择
- [ ] 色彩空间设置
- [ ] 音频设置
- [ ] 输出路径
- [ ] 磁盘空间充足

### 7.2 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 渲染失败 | 磁盘空间不足 | 清理磁盘 |
| 色彩偏移 | 色彩管理 | 检查设置 |
| 音频不同步 | 帧率不匹配 | 统一帧率 |
| 渲染缓慢 | 效果复杂 | 预渲染 |
