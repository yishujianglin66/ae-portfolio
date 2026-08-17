# FBX格式结构解析（FBXElem/Properties70）

## 问题场景

从3dsMax导出的FBX文件在Blender中导入时，控制台输出大量 `Error, could not find any file path in FBXElem(id=b'Texture'...)` 错误。需要理解FBX二进制格式的内部结构才能诊断问题。

## 核心原理

### FBX文件层次结构

FBX（Filmbox）是Autodesk的3D交换格式，内部为树状节点结构：

```
FBXDocument
├── GlobalSettings          # 全局设置（坐标系、单位）
├── Documents               # 文档信息
├── References              # 外部引用
├── Definitions             # 对象定义计数
├── Objects                 # 核心数据
│   ├── Geometry (Mesh)     # 网格数据（顶点/面/UV/法线）
│   ├── Model               # 变换节点（位置/旋转/缩放）
│   ├── Material            # 材质定义
│   ├── Texture             # 纹理引用 ← 问题高发区
│   ├── Video               # 视频/图像文件引用
│   └── Pose                # 绑定姿态
└── Connections             # 对象间连接关系
```

### FBXElem结构

每个节点由 `FBXElem` 表示：

```python
FBXElem(
    id=b'Texture',           # 节点类型标识
    props=[                   # 属性列表（按props_type解析）
        983306304,           # L = int64 (唯一ID)
        b'贴图 #5\x00\x01Texture',  # S = bytes (名称\x00\x01类型)
        b''                  # S = bytes (备用名)
    ],
    props_type=bytearray(b'LSS'),  # 属性类型声明
    elems=[...]              # 子节点列表
)
```

### Properties70 属性系统

3dsMax导出的FBX使用 `Properties70` 存储扩展属性：

```python
FBXElem(id=b'Properties70', props=[], elems=[
    FBXElem(id=b'P', props=[
        b'3dsMax',           # 属性名
        b'Compound',         # 类型
        b'',                 # 类型标签
        b''                  # 标志 ('A'=动画, ''=静态)
    ]),
    FBXElem(id=b'P', props=[
        b'bitmapName',       # 位图文件名属性
        b'KString',          # 字符串类型
        b'', b'A',
        b''                  # ← 值为空！这就是纹理丢失的根因
    ]),
])
```

### 纹理引用链

正常流程：`Material → Texture → Video → FileName(实际路径)`

3dsMax导出问题：
- `Texture.FileName` = 空
- `Texture.RelativeFilename` = 空  
- `Video` 节点可能完全缺失
- 仅保留 `TextureName`（如"贴图 #5"）但无实际文件路径

## 代码示例

### 诊断FBX纹理状态

```python
import bpy

# 导入FBX
bpy.ops.import_scene.fbx(filepath="model.fbx")

# 检查所有材质的纹理状态
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            img = node.image
            if img is None:
                print(f"[WARN] {mat.name}: 纹理节点无图像")
            elif img.filepath == "":
                print(f"[WARN] {mat.name}: 图像路径为空 ({img.name})")
            else:
                print(f"[OK] {mat.name}: {img.filepath}")
```

### 从FBXElem提取纹理信息

```python
# 在Blender的FBX导入源码中 (io_scene_fbx/fbx_utils.py)
# 可以hook FBXElem解析过程来获取原始数据

def inspect_fbx_textures(fbx_root):
    """遍历FBX节点树，提取所有Texture节点信息"""
    textures = []
    for elem in fbx_root.elems:
        if elem.id == b'Objects':
            for obj in elem.elems:
                if obj.id == b'Texture':
                    info = {'id': obj.props[0], 'name': obj.props[1]}
                    for sub in obj.elems:
                        if sub.id == b'FileName':
                            info['filename'] = sub.props[0]
                        elif sub.id == b'RelativeFilename':
                            info['relative'] = sub.props[0]
                    textures.append(info)
    return textures
```

## 常见陷阱

| 陷阱 | 原因 | 解决方案 |
|------|------|----------|
| 所有纹理路径为空 | 3dsMax导出时未嵌入媒体 | 手动指定纹理目录 |
| 纹理名称含中文 | 3dsMax默认命名"贴图 #N" | 导入后按名称重映射 |
| `\x00\x01`分隔符 | FBX名称格式：`Name\x00\x01Type` | 解析时split(b'\x00\x01') |
| props_type理解错误 | L=int64, S=bytes, I=int32, F=float, D=double | 严格按类型解析 |

## 版本兼容

- Blender 5.1.0 Alpha：FBX导入器为内置addon `io_scene_fbx`
- `Material.use_nodes` 在Blender 6.0将移除（DeprecationWarning）
- 纹理路径错误为C层输出，不会导致Python异常或退出码非零

## 关联代码

- `cel_shading.py` L380-420：FBX导入参数设置
- `engine.py` L1082-1085：Blender子进程执行

## 参考链接

- [FBX SDK Documentation](https://help.autodesk.com/view/FBX/2020/ENU/)
- Blender源码：`scripts/addons/io_scene_fbx/fbx_utils.py`
- [FBX二进制格式逆向分析](https://code.blender.org/2013/08/fbx-binary-file-format-specification/)
