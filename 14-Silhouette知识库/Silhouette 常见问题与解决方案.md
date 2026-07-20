# Silhouette 常见问题与解决方案

> 分类: 故障排查
> 更新日期: 2026-07-11
> 概述: 按类别整理 Silhouette 常见问题（FAQ），涵盖安装、渲染、脚本、跟踪、Roto、Paint 等模块

## 目录
---

- [一、安装与授权](#一安装与授权)
- [二、渲染问题](#二渲染问题)
- [三、脚本与 API](#三脚本与-api)
- [四、跟踪问题](#四跟踪问题)
- [五、Roto 问题](#五roto-问题)
- [六、Paint 问题](#六paint-问题)
- [七、性能问题](#七性能问题)
- [八、文件与 IO](#八文件与-io)
- [九、集成与导出](#九集成与导出)
- [十、AI 功能问题](#十ai-功能问题)

---

## 一、安装与授权

### Q1.1 安装失败：提示"缺少 Visual C++ 运行库"

**症状**：安装过程中断，提示缺少 VC++ 运行库。

**原因**：系统未安装 Visual C++ Redistributable。

**解决方案**：
1. 下载并安装 Visual C++ Redistributable for Visual Studio 2019
2. 安装 x64 版本
3. 重启系统后重新安装 Silhouette

### Q1.2 启动时崩溃：提示"无法加载 GPU 驱动"

**症状**：启动后立即崩溃，错误日志显示 GPU 驱动加载失败。

**原因**：GPU 驱动过旧或不兼容。

**解决方案**：
1. 更新 GPU 驱动至最新版本
   - NVIDIA：https://www.nvidia.com/drivers
   - AMD：https://www.amd.com/support
2. 如问题持续，尝试禁用 GPU 加速启动：
   ```
   Silhouette.exe --disable-gpu
   ```
3. 检查 GPU 是否满足最低要求

### Q1.3 授权激活失败：提示"激活码无效"

**症状**：输入授权码后提示无效。

**原因**：
- 授权码输入错误
- 授权码已被其他设备使用
- 网络连接问题

**解决方案**：
1. 仔细核对授权码（区分大小写）
2. 检查授权码是否已在其他设备激活
3. 确保网络连接正常
4. 联系 Boris FX 客服 reset 授权

### Q1.4 macOS 上无法启动：提示"无法验证开发者"

**解决方案**：
```bash
# 在终端执行
sudo xattr -rd com.apple.quarantine /Applications/Silhouette.app
```

### Q1.5 Linux 上缺少依赖库

**解决方案**：
```bash
# CentOS/RHEL
sudo yum install libGLU mesa-libGLU

# Ubuntu/Debian
sudo apt install libglu1-mesa
```

---

## 二、渲染问题

### Q2.1 渲染输出全黑

**症状**：渲染出的 EXR 序列全部为黑色。

**排查步骤**：
1. 检查源节点是否正确加载素材
2. 检查节点连接是否正确
3. 检查 Output 节点路径是否有写入权限
4. 检查 Alpha 通道是否被意外反转

```python
from fx import *

# 诊断脚本
session = activeSession()
for i in range(session.numNodes):
    node = session.node(i)
    print(f"Node: {node.label}, Type: {node.type}")
    if node.type == "OutputNode":
        path = node.property("path").value
        print(f"  Output path: {path}")
```

### Q2.2 渲染速度极慢

**症状**：渲染速度比预期慢 5 倍以上。

**排查步骤**：
1. 检查 GPU 加速是否启用
2. 检查是否有其他 GPU 程序占用
3. 检查磁盘空间是否充足
4. 检查内存是否不足导致频繁交换

```python
from fx import *

proj = activeProject()
gpu = proj.property("gpu")
print(f"GPU enabled: {gpu.value('enabled')}")
print(f"GPU device: {gpu.value('device')}")
```

### Q2.3 渲染中途崩溃

**症状**：渲染进行到某一帧时崩溃。

**原因**：
- 该帧素材损坏
- 内存不足
- 节点参数异常

**解决方案**：
1. 检查崩溃帧的素材是否完整
2. 增加虚拟内存
3. 使用代理渲染
4. 跳过问题帧后单独渲染

### Q2.4 输出文件过大

**症状**：EXR 文件比预期大很多。

**解决方案**：
1. 使用压缩格式（ZIP/DWAB）
2. 降低色深（32-bit → 16-bit）
3. 只输出必要通道
4. 检查是否意外输出多通道

```python
from fx import *

out = session.node("OutputNode")
out.property("compression").setValue("DWAB", 0)  # 使用 DWAB 压缩
out.property("bitDepth").setValue("half", 0)      # 16-bit half
```

### Q2.5 帧率不匹配

**症状**：输出视频帧率与项目不一致。

**解决方案**：
```python
from fx import *

session = activeSession()
src = session.node("SourceNode")
out = session.node("OutputNode")

# 确保输出帧率与源一致
src_fps = src.property("frameRate").value
out.property("frameRate").setValue(src_fps, 0)
```

---

## 三、脚本与 API

### Q3.1 脚本无法运行：提示"ImportError: No module named fx"

**原因**：脚本未在 Silhouette 环境内运行。

**解决方案**：
1. 确保通过 Silhouette 的脚本编辑器运行
2. 或通过命令行调用 Silhouette 的 Python：
   ```
   "C:\Program Files\Boris FX\Silhouette 2026\python.exe" script.py
   ```

### Q3.2 节点属性设置无效

**症状**：`property.setValue()` 后值未变化。

**原因**：
- 属性名错误
- 帧参数错误
- 属性类型不匹配

**解决方案**：
```python
from fx import *

node = session.node("RotoNode")

# 检查属性是否存在
print(node.properties)  # 打印所有属性名

# 正确设置（注意帧参数）
node.property("alpha.blur").setValue(0.5, 0)  # 第0帧

# 检查类型
prop = node.property("alpha.blur")
print(f"Type: {prop.type}, Value: {prop.value}")
```

### Q3.3 节点连接失败

**症状**：`port.connect()` 抛出异常。

**原因**：
- 端口索引错误
- 端口已连接
- 节点类型不兼容

**解决方案**：
```python
from fx import *

src = session.node("SourceNode")
roto = session.node("RotoNode")

# 先断开现有连接
if roto.inputs[1].isConnected():
    roto.inputs[1].disconnect()

# 再连接
src.outputs[0].connect(roto.inputs[1])
```

### Q3.4 批处理脚本内存泄漏

**症状**：批处理大量镜头时内存持续增长。

**解决方案**：
```python
import gc
from fx import *

shots = ["sh010", "sh020", "sh030"]
for shot in shots:
    # 处理每个镜头
    process_shot(shot)

    # 显式清理
    gc.collect()

    # 清理项目
    proj = activeProject()
    proj.clear()
```

### Q3.5 脚本日志查看

**解决方案**：
```python
import logging

# 配置日志
logging.basicConfig(
    filename='silhouette_script.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logging.info("脚本开始执行")
# ... 脚本代码 ...
logging.info("脚本执行完成")
```

---

## 四、跟踪问题

### Q4.1 跟踪点丢失

**症状**：跟踪过程中跟踪点突然消失。

**原因**：
- 目标被遮挡
- 目标移出画面
- 光照变化剧烈

**解决方案**：
1. 手动在丢失帧重新定位跟踪点
2. 使用平面跟踪替代点跟踪
3. 调整搜索区域大小
4. 使用 AI 跟踪（2026 新功能）

```python
from fx import *

tracker = session.node("TrackerNode")
tracker.property("searchSize").setValue(64, 0)  # 增大搜索区域
tracker.property("trackMode").setValue("robust", 0)  # 鲁棒模式
```

### Q4.2 跟踪数据漂移

**症状**：长时间跟踪后，跟踪点逐渐偏离目标。

**原因**：
- 累积误差
- 特征点不明显
- 压缩失真

**解决方案**：
1. 定期校正关键帧（每 50-100 帧）
2. 使用多个跟踪点取平均
3. 使用平面跟踪
4. 启用平滑滤波

### Q4.3 平面跟踪失败

**症状**：平面跟踪无法锁定目标。

**原因**：
- 选择区域过小
- 区域纹理不足
- 平面变形过大

**解决方案**：
1. 扩大跟踪区域
2. 选择纹理丰富的区域
3. 使用变形平面模式
4. 分段跟踪

### Q4.4 导出跟踪数据格式错误

**症状**：导出的跟踪数据在 AE/Nuke 中无法使用。

**解决方案**：
```python
from fx import *

tracker = session.node("TrackerNode")

# 确保选择正确的导出格式
# AE: "ae_keyframes"
# Nuke: "nuke_tracker"
# Boujou: "boujou"
tracker.property("exportFormat").setValue("ae_keyframes", 0)
tracker.property("exportPath").setValue("D:/tracks/track.txt", 0)
tracker.export()
```

---

## 五、Roto 问题

### Q5.1 遮罩边缘抖动

**症状**：逐帧查看时，遮罩边缘有明显跳动。

**原因**：
- 关键帧过少
- 形状变化不流畅
- 运动模糊处理不当

**解决方案**：
1. 增加关键帧密度
2. 使用样条插值
3. 启用时序平滑
4. 使用 AI 去抖动

```python
from fx import *

roto = session.node("RotoNode")
roto.property("temporalSmooth").setValue(True, 0)
roto.property("smoothRadius").setValue(3, 0)  # 3帧平滑
```

### Q5.2 头发区域遮罩不精确

**症状**：头发等细节区域遮罩不清晰。

**解决方案**：
1. 使用 AI Roto 处理头发区域
2. 单独为头发创建形状
3. 使用边缘细化功能
4. 结合 Paint 修复

### Q5.3 运动模糊区域遮罩失败

**症状**：快速运动区域遮罩不准确。

**解决方案**：
1. 启用运动模糊模拟
2. 调整模糊量匹配原素材
3. 使用 Frame Interp 模式

```python
roto = session.node("RotoNode")
roto.property("motionBlur").setValue(True, 0)
roto.property("motionBlurAmount").setValue(1.5, 0)
```

### Q5.4 形状无法编辑

**症状**：形状点无法拖动或编辑。

**原因**：
- 形状被锁定
- 当前帧非关键帧
- 工具模式错误

**解决方案**：
1. 检查形状锁定状态
2. 切换到编辑模式
3. 确保在关键帧上编辑

### Q5.5 多形状管理混乱

**解决方案**：
1. 使用形状组管理
2. 规范命名
3. 使用颜色标签
4. 定期清理未使用形状

---

## 六、Paint 问题

### Q6.1 克隆源不匹配

**症状**：克隆的区域与周围环境不协调。

**解决方案**：
1. 调整克隆源位置
2. 匹配光照方向
3. 使用变换工具调整
4. 使用 AI Paint 智能匹配

### Q6.2 修复区域有痕迹

**症状**：修复后的区域可见克隆痕迹。

**解决方案**：
1. 使用频率分离
2. 降低画笔不透明度
3. 多次轻涂而非一次重涂
4. 使用 AI 修复

### Q6.3 帧间不一致

**症状**：逐帧查看时修复区域跳动。

**解决方案**：
1. 启用时序跟踪
2. 使用跟踪驱动的克隆
3. 检查每帧结果
4. 使用 AI 时序一致性

```python
paint = session.node("PaintNode")
paint.property("temporalTrack").setValue(True, 0)
paint.property("trackSource").setValue("auto", 0)
```

### Q6.4 大区域修复失败

**症状**：大面积修复后画面不自然。

**解决方案**：
1. 分块修复
2. 使用 AI Paint（diffusion 模式）
3. 多源克隆融合
4. 结合纹理生成

---

## 七、性能问题

### Q7.1 预览卡顿

**症状**：拖动时间轴时预览不流畅。

**解决方案**：
1. 降低预览质量
2. 使用代理
3. 启用 GPU 加速
4. 增加缓存

```python
from fx import *

proj = activeProject()
preview = proj.property("preview")
preview.setValue("quality", 0.5)  # 半分辨率预览
preview.setValue("cache", True)
```

### Q7.2 内存不足崩溃

**症状**：处理大项目时崩溃，提示内存不足。

**解决方案**：
1. 增加物理内存
2. 使用代理工作流
3. 分段处理
4. 启用内存压缩

### Q7.3 GPU 利用率低

**症状**：任务管理器显示 GPU 利用率仅 10-20%。

**原因**：
- GPU 加速未启用
- 当前任务不支持 GPU
- 驱动问题

**解决方案**：
1. 确认 GPU 加速已启用
2. 检查任务是否 GPU 加速支持
3. 更新驱动
4. 检查显存是否充足

### Q7.4 磁盘 IO 瓶颈

**症状**：磁盘活动指示灯常亮，处理速度慢。

**解决方案**：
1. 使用 NVMe SSD
2. 分散 IO（素材、缓存、输出分开）
3. 增加缓存大小
4. 使用更高压缩比格式

---

## 八、文件与 IO

### Q8.1 无法加载 EXR 序列

**症状**：导入 EXR 序列失败。

**原因**：
- 文件命名不连续
- EXR 版本不兼容
- 权限问题

**解决方案**：
1. 检查文件命名（需连续编号）
2. 确认 EXR 2.0 兼容
3. 检查文件权限
4. 尝试单帧加载

### Q8.2 项目文件损坏

**症状**：打开项目文件失败或崩溃。

**解决方案**：
1. 尝试打开自动保存版本
2. 使用备份文件
3. 创建新项目，逐节点迁移
4. 联系技术支持

```python
from fx import *

# 尝试修复项目
proj = Project()
try:
    proj.load("damaged_project.sfx")
except Exception as e:
    print(f"加载失败: {e}")
    # 尝试加载自动保存
    proj.load("damaged_project_autosave.sfx")
```

### Q8.3 中文路径问题

**症状**：包含中文的路径无法读取或写入。

**解决方案**：
1. 使用英文路径
2. 或使用 UNC 路径
3. 检查文件编码

```python
# 统一使用正斜杠和英文路径
path = "D:/projects/shot010/output.exr"
```

### Q8.4 网络存储读写慢

**解决方案**：
1. 使用 10Gbps 网络
2. 本地缓存工作副本
3. 使用 SMB 3.0+
4. 避免高峰期访问

---

## 九、集成与导出

### Q9.1 导出 AE Mask 数据失败

**症状**：导出的 AE Mask 数据无法在 AE 中使用。

**解决方案**：
1. 确认 AE 版本兼容
2. 检查导出路径权限
3. 确认形状类型支持
4. 使用最新版 Silhouette

### Q9.2 Nuke 导入遮罩异常

**症状**：Nuke 导入 Silhouette 遮罩后位置偏移。

**原因**：坐标系统不一致。

**解决方案**：
1. 检查分辨率设置
2. 确认像素长宽比
3. 使用 EXR 格式传输
4. 检查 Nuke 项目设置

### Q9.3 OFX 插件在宿主中崩溃

**解决方案**：
1. 更新宿主软件
2. 更新 Silhouette OFX
3. 清理宿主缓存
4. 检查 GPU 兼容性

### Q9.4 跟踪数据帧率不匹配

**症状**：导出的跟踪数据在目标软件中速度不对。

**解决方案**：
```python
from fx import *

tracker = session.node("TrackerNode")
# 确保帧率设置正确
src_fps = session.node("SourceNode").property("frameRate").value
tracker.property("exportFrameRate").setValue(src_fps, 0)
tracker.export()
```

---

## 十、AI 功能问题

### Q10.1 AI Roto 结果不准确

**症状**：AI 生成的遮罩与目标不符。

**解决方案**：
1. 提供更明确的提示（点击目标中心）
2. 增加关键帧
3. 尝试不同模型
4. 手动修正后重新初始化

```python
from fx.ai import AIRoto

ai = AIRoto()
ai.setMode("transformer_v2")  # 高精度模式
ai.setKeyFrames([1, 60, 120, 240])  # 增加关键帧
ai.process()
```

### Q10.2 AI Paint 修复质量差

**解决方案**：
1. 切换到 diffusion 模式
2. 缩小修复区域
3. 分多次修复
4. 结合手动克隆

### Q10.3 AI 处理速度慢

**解决方案**：
1. 使用更强大的 GPU
2. 降低处理分辨率
3. 启用 FP16
4. 更新 TensorRT

### Q10.4 GPU 显存不足

**症状**：AI 处理时提示 "CUDA out of memory"。

**解决方案**：
1. 降低处理分辨率
2. 关闭其他 GPU 应用
3. 分块处理
4. 增加 GPU 显存限制

```python
from fx import *

proj = activeProject()
gpu = proj.property("gpu")
gpu.setValue("memoryLimit", 12)  # 限制显存使用
gpu.setValue("fp16", True)       # 启用 FP16
```

### Q10.5 AI 模型加载失败

**症状**：启动 AI 功能时提示模型加载失败。

**解决方案**：
1. 检查模型文件完整性
2. 重新安装 AI 模型
3. 检查磁盘空间
4. 更新 GPU 驱动

---

## 附录：错误码速查表

| 错误码 | 含义 | 解决方案 |
|--------|------|---------|
| E001 | 授权失效 | 重新激活 |
| E101 | GPU 初始化失败 | 更新驱动 |
| E102 | 显存不足 | 降低分辨率 |
| E201 | 文件读取失败 | 检查权限 |
| E202 | 文件写入失败 | 检查磁盘空间 |
| E301 | 节点连接错误 | 检查端口 |
| E302 | 属性设置错误 | 检查属性名 |
| E401 | AI 模型加载失败 | 重新安装 |
| E402 | AI 推理失败 | 检查 GPU |
| E501 | 渲染失败 | 检查节点链 |
| E502 | 内存不足 | 增加内存 |

---

> 相关文档：
> - [[Silhouette 脚本调试与错误处理]]
> - [[Silhouette 性能优化深度研究]]
> - [[Silhouette 项目管理最佳实践]]
