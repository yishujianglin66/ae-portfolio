# 不同DCC软件FBX导出差异

## 问题场景

不同DCC软件（3dsMax/Maya/Blender/MotionBuilder）导出的FBX存在结构差异，导致同一导入代码在不同模型上表现不一致。需要建立兼容性处理策略。

## 核心差异对比

| 特性 | 3dsMax | Maya | Blender | MotionBuilder |
|------|--------|------|---------|---------------|
| 默认单位 | 厘米 | 厘米 | 米 | 厘米 |
| Up轴 | Z | Y | Z | Y |
| 骨骼命名 | 自定义 | 自定义 | Bone.NNN | 标准 |
| 纹理嵌入 | 默认不嵌入 | 可选 | 默认嵌入 | 不嵌入 |
| 叶骨骼 | 导出 | 导出 | 可忽略 | 导出 |
| 动画格式 | Bake | 原始曲线 | Bake | 原始曲线 |
| 材质类型 | Standard/Physical | Lambert/Blinn | Principled | Standard |

## 兼容性处理策略

```python
def detect_fbx_source(fbx_path):
    """通过FBX内容推测来源DCC"""
    # 读取FBX二进制头部
    with open(fbx_path, 'rb') as f:
        header = f.read(128)
    
    # 检查Creator字段
    if b'3ds Max' in header or b'3dsMax' in header:
        return '3dsmax'
    elif b'Maya' in header:
        return 'maya'
    elif b'Blender' in header:
        return 'blender'
    elif b'MotionBuilder' in header:
        return 'mobu'
    return 'unknown'

def get_import_params(source):
    """根据来源调整导入参数"""
    base_params = {
        'use_anim': False,
        'ignore_leaf_bones': True,
        'automatic_bone_orientation': True,
    }
    
    if source == '3dsmax':
        base_params.update({
            'use_prepost_rot': False,  # 3dsMax的预旋转处理
            'bake_space_transform': True,
        })
    elif source == 'maya':
        base_params.update({
            'axis_forward': '-Z',
            'axis_up': 'Y',
        })
    
    return base_params
```

## 常见陷阱

| 来源 | 特有问题 | 解决方案 |
|------|----------|----------|
| 3dsMax | 纹理名为"贴图 #N"，路径为空 | 使用程序化材质替代 |
| 3dsMax | 导出多余Point/Helper对象 | 过滤type!='MESH'的对象 |
| Maya | Y-up需要坐标转换 | axis_up='Y' |
| Maya | 命名空间前缀(ns:object) | strip命名空间 |
| Blender | 已Z-up无需转换 | 直接导入 |
| 通用 | 叶骨骼产生多余bone | ignore_leaf_bones=True |

## 关联代码

- `cel_shading.py` 当前仅处理3dsMax导出的FBX
- 扩展到其他DCC时需调整：导入参数、坐标转换、名称匹配规则
- 部件分类关键词（weapon/crown/face）需要根据模型命名约定调整
