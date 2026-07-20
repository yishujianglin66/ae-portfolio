# Silhouette fx API 参数详解手册

## 版本信息

- **Silhouette 版本**: 2026.0.2
- **API 类型**: Python fx 模块
- **文档来源**: Boris FX Silhouette 官方文档

---

## 一、核心模块

### 1.1 fx 模块入口

```python
from fx import *
```

### 1.2 Project 类

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `Project()` | 无 | Project | 创建新项目 |
| `activeProject()` | 无 | Project/None | 获取当前活动项目 |
| `activate(proj)` | proj: Project | None | 激活项目 |
| `addItem(item)` | item: Session/Clip | None | 添加项目项 |
| `numItems` | 无 | int | 项目项数量 |
| `item(index)` | index: int | ProjectItem | 获取项目项 |

### 1.3 Session 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `Session()` | 无 | Session | 创建会话 |
| `activeSession()` | 无 | Session/None | 获取当前活动会话 |
| `activate(sess)` | sess: Session | None | 激活会话 |
| `addNode(node)` | node: Node | None | 添加节点 |
| `numNodes` | 无 | int | 节点数量 |
| `node(index)` | index: int | Node | 获取节点 |
| `label` | 无 | str | 会话标签 |
| `width` | 无 | int | 会话宽度 |
| `height` | 无 | int | 会话高度 |
| `frameRate` | 无 | float | 帧率 |

### 1.4 Node 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `Node(type)` | type: str | Node | 创建节点 |
| `label` | 无 | str | 节点标签 |
| `type` | 无 | str | 节点类型 |
| `properties` | 无 | list | 属性名称列表 |
| `property(name)` | name: str | Property | 获取属性 |
| `addProperty(prop)` | prop: Property | None | 添加属性 |
| `inputs` | 无 | list | 输入端口列表 |
| `outputs` | 无 | list | 输出端口列表 |
| `remove()` | 无 | None | 删除节点 |

### 1.5 Property 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `Property(name, type_str)` | name: str, type_str: str | Property | 创建属性 |
| `name` | 无 | str | 属性名称 |
| `type` | 无 | str | 属性类型 |
| `value` | 无 | Any | 当前值 |
| `setValue(value, frame)` | value: Any, frame: int | None | 在指定帧设置值 |
| `getValue(frame)` | frame: int | Any | 获取指定帧的值 |
| `numKeys` | 无 | int | 关键帧数量 |
| `keyValue(keyIndex)` | keyIndex: int | Any | 获取关键帧值 |
| `keyTime(keyIndex)` | keyIndex: int | float | 获取关键帧时间 |

### 1.6 Port 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `connect(target)` | target: Port | None | 连接到目标端口 |
| `disconnect()` | 无 | None | 断开连接 |
| `isConnected()` | 无 | bool | 是否已连接 |
| `source` | 无 | Node | 源节点（只读） |
| `target` | 无 | Node | 目标节点（只读） |
| `index` | 无 | int | 端口索引 |

---

## 二、节点类型详解

### 2.1 SourceNode（源节点）

**输入端口**: 无

**输出端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | output | 主输出 |

**属性**:
| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| mediaPath | string | "" | 媒体文件路径 |
| frameStart | int | 0 | 起始帧 |
| frameEnd | int | 100 | 结束帧 |
| frameRate | float | 24.0 | 帧率 |
| loop | bool | false | 是否循环 |

### 2.2 RotoNode（Roto遮罩节点）

**输入端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | obey_matte | 遮罩服从 |
| 1 | foreground | **主输入** |
| 2 | background | 背景 |
| 3 | occlusion | 遮挡 |
| 4 | data | 数据 |

**输出端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | output | 主输出 |
| 1 | colorComp | 颜色合成 |
| 2 | composite | 合成 |
| 3 | channels | 通道 |
| 4 | objects | 对象 |

**属性**:
| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| alpha.blur | float | 0.0 | 边缘模糊 |
| antialias | float | 1.0 | 抗锯齿 |
| fill | bool | true | 是否填充 |
| stroke | bool | false | 是否描边 |
| stroke.width | float | 1.0 | 描边宽度 |
| stroke.color | color | [1,1,1] | 描边颜色 |
| matte.mode | string | "alpha" | 遮罩模式 |
| matte.invert | bool | false | 反转遮罩 |
| motionBlur | bool | false | 运动模糊 |
| motionBlur.shutter | float | 0.5 | 快门时间 |

### 2.3 TrackerNode（跟踪节点）

**输入端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | source | 源输入 |

**输出端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | output | 跟踪数据输出 |

**属性**:
| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| trackType | string | "planar" | 跟踪类型 |
| searchArea | int | 21 | 搜索区域大小 |
| accuracy | string | "medium" | 精度 |
| patternSize | int | 11 | 模板大小 |
| keyframes | int | 1 | 关键帧间隔 |
| forward | bool | true | 向前跟踪 |
| backward | bool | false | 向后跟踪 |
| autoKeyframe | bool | true | 自动关键帧 |

### 2.4 PaintNode（Paint修复节点）

**输入端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | source | 源输入 |

**输出端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | output | 修复后输出 |

**属性**:
| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| brush.size | float | 25.0 | 笔刷大小 |
| brush.hardness | float | 0.5 | 笔刷硬度 |
| brush.flow | float | 1.0 | 笔刷流量 |
| mode | string | "clone" | 模式 |
| sampleOffset | [float, float] | [0,0] | 采样偏移 |
| cloneSource | string | "current" | 克隆源 |

### 2.5 OutputNode（输出节点）

**输入端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | input | 主输入 |

**输出端口**: 无

**属性**:
| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| path | string | "" | 输出路径 |
| format | string | "exr" | 输出格式 |
| compression | string | "none" | 压缩方式 |
| depth | string | "32f" | 位深度 |
| channels | string | "rgba" | 通道 |
| frameStart | int | 0 | 起始帧 |
| frameEnd | int | 100 | 结束帧 |

---

## 三、属性类型

### 3.1 基础类型

| 类型字符串 | Python类型 | 示例 |
|-----------|-----------|------|
| "string" | str | "alpha" |
| "bool" | bool | true/false |
| "int" | int | 25 |
| "float" | float | 0.5 |
| "color" | [float, float, float] | [1.0, 0.5, 0.0] |
| "point" | [float, float] | [1920, 1080] |
| "vector" | [float, float, float] | [0, 0, 1] |
| "enum" | str | "medium" |

### 3.2 枚举值

**trackType**:
- "planar" - 平面跟踪
- "point" - 点跟踪
- "paint-track" - Paint跟踪

**accuracy**:
- "low" - 低精度
- "medium" - 中等精度
- "high" - 高精度

**mode** (Paint):
- "clone" - 克隆
- "repair" - 修复
- "erase" - 擦除

**format** (Output):
- "exr" - OpenEXR
- "tiff" - TIFF
- "png" - PNG
- "jpg" - JPEG

---

## 四、常用操作示例

### 4.1 创建项目和会话

```python
from fx import *

proj = activeProject()
if proj is None:
    proj = Project()
    activate(proj)

session = activeSession()
if session is None:
    session = Session()
    session.label = "AutoRoto"
    activate(session)
    proj.addItem(session)
```

### 4.2 创建节点并连接

```python
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/video.mov", 0)
session.addNode(src)

roto = Node("RotoNode")
roto.label = "AutoRoto"
session.addNode(roto)

out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/matte_[####].exr", 0)
session.addNode(out_node)

src.outputs[0].connect(roto.inputs[1])
roto.outputs[0].connect(out_node.inputs[0])
```

### 4.3 设置属性关键帧

```python
roto.property("alpha.blur").setValue(0.5, 0)
roto.property("alpha.blur").setValue(1.0, 50)
roto.property("alpha.blur").setValue(0.5, 100)
```

### 4.4 导出跟踪数据

```python
track = Node("TrackerNode")
track.property("trackType").setValue("planar", 0)
track.property("searchArea").setValue(31, 0)
track.property("accuracy").setValue("high", 0)

src.outputs[0].connect(track.inputs[0])
session.addNode(track)
```

---

## 五、脚本执行方式

### 5.1 在 Silhouette 内部执行

```python
# 通过 Silhouette 菜单: Script > Run Script
# 或命令行: Silhouette.exe -script script.py
```

### 5.2 通过 Python API（Silhouette 内置）

```python
# Silhouette 内置 Python 路径:
# C:\Program Files\BorisFX\Silhouette 2026.0\resources\python\python.exe
```

### 5.3 fx_emulator 模拟执行

```python
# 使用 fx_emulator.py 模拟 fx 模块
# 适用于开发和测试，不生成真实输出
```

---

## 六、注意事项

1. **Property 第二个参数必须是字符串类型**
2. **Object 类不能直接实例化，使用 createObject()**
3. **Port.source 是只读属性，不能直接赋值**
4. **版本号是浮点数，不是函数**
5. **脚本执行前必须关闭所有模态对话框**
6. **节点连接使用 src.outputs[0].connect(dst.inputs[n])**
7. **RotoNode 主输入是 foreground（索引1），不是索引0**
