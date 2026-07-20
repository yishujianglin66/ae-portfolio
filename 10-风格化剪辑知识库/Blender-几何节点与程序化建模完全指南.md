# Blender 几何节点与程序化建模完全指南

> 适用版本：Blender 4.2 LTS / 4.3+ | 更新日期：2026-07-14 | 分类：程序化建模知识库

---

## 目录

- [一、几何节点系统概述](#一几何节点系统概述)
- [二、核心节点详解](#二核心节点详解)
- [三、程序化建模工作流](#三程序化建模工作流)
- [四、动画与模拟](#四动画与模拟)
- [五、材质与渲染](#五材质与渲染)
- [六、性能优化](#六性能优化)
- [七、与AE集成](#七与ae集成)
- [附录](#附录)

---

## 一、几何节点系统概述

### 1.1 几何节点架构原理

几何节点（Geometry Nodes）是Blender 2.9+引入的程序化建模系统，4.0起升级为支持字段（Field）和命名属性（Named Attributes）的完整节点图系统。它采用数据流驱动模型，所有几何数据通过节点连接传递，每个节点接收输入几何体并输出处理后的几何体。

```python
class GeometryNodesArchitecture:
    """几何节点系统架构原子级规范"""
    
    VERSION = "4.2 LTS"
    
    ARCHITECTURE_LAYERS = {
        'geometry_set': {
            'description': '几何集合（最顶层容器）',
            'components': ['Mesh', 'Curve', 'Point Cloud', 'Volume', 'Instance'],
            'characteristics': ['可包含多种几何类型', '可同时存在', '可分别访问'],
            'access_pattern': '通过Geometry节点输入/输出'
        },
        'field_system': {
            'description': '字段系统（按元素求值）',
            'characteristics': ['延迟求值', '按上下文求值', '可组合'],
            'data_flow': '字段通过socket连接在节点间传递',
            'difference_from_value': '值是常数，字段是函数'
        },
        'attribute_system': {
            'description': '属性系统（命名属性存储）',
            'domains': ['POINT', 'EDGE', 'FACE', 'CORNER', 'CURVE', 'INSTANCE', 'LAYER'],
            'data_types': ['FLOAT', 'INT', 'FLOAT_VECTOR', 'FLOAT_COLOR', 'BYTE_COLOR', 'BOOLEAN', 'QUATERNION', 'FLOAT4X4'],
            'storage': '属性存储在几何体的特定domain上'
        },
        'node_tree': {
            'description': '节点树（计算图）',
            'evaluation_mode': ['MODIFIER（修改器模式）', 'NODE（节点模式）'],
            'caching': '基于depsgraph的缓存机制',
            'thread_safety': '主线程求值，并行处理元素'
        }
    }
    
    CORE_DATA_TYPES = {
        'Geometry': {
            'description': '几何体类型（最通用）',
            'contains': ['mesh', 'curve', 'points', 'volume', 'instances'],
            'use_case': '节点间几何传递'
        },
        'Mesh': {
            'description': '网格几何体',
            'components': ['vertices', 'edges', 'faces', 'corners'],
            'use_case': '多边形建模'
        },
        'Curve': {
            'description': '曲线几何体',
            'components': ['splines', 'control_points'],
            'use_case': '路径生成、样条线操作'
        },
        'Points': {
            'description': '点云几何体',
            'components': ['points'],
            'use_case': '粒子、实例化基础'
        },
        'Instances': {
            'description': '实例引用',
            'components': ['reference_object', 'transform_matrix'],
            'use_case': '高效重复几何'
        },
        'Volume': {
            'description': '体积数据',
            'components': ['voxel_grid'],
            'use_case': '体积渲染、流体数据'
        }
    }
    
    def __init__(self):
        self.node_groups = {}
        self.active_tree = None
        
    def create_node_group(self, name):
        """创建新的节点组"""
        import bpy
        ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        # 创建输入输出节点
        ng.nodes.new('NodeGroupInput')
        ng.nodes.new('NodeGroupOutput')
        return ng
```

### 1.2 节点图与数据流

```python
class NodeGraphDataFlow:
    """节点图数据流原子级规范"""
    
    EVALUATION_FLOW = {
        'left_to_right': {
            'description': '从左到右求值',
            'input': 'Group Input节点',
            'processing': '中间处理节点',
            'output': 'Group Output节点'
        },
        'field_evaluation': {
            'description': '字段按元素求值',
            'mechanism': '字段socket在每个几何元素上独立计算',
            'example': 'Position字段在每个顶点返回其坐标'
        },
        'dependency_graph': {
            'description': '依赖图（depsgraph）',
            'trigger': '上游节点变化触发下游重新求值',
            'caching': '不变的子图结果被缓存'
        }
    }
    
    SOCKET_TYPES = {
        'Geometry': {'color': '黄绿色', 'description': '几何体'},
        'Mesh': {'color': '浅红', 'description': '网格'},
        'Curve': {'color': '黄色', 'description': '曲线'},
        'Points': {'color': '紫色', 'description': '点云'},
        'Instances': {'color': '浅蓝', 'description': '实例'},
        'Volume': {'color': '深蓝', 'description': '体积'},
        'Value (Float)': {'color': '灰色', 'description': '浮点数（菱形）'},
        'Value (Int)': {'color': '绿色', 'description': '整数（菱形）'},
        'Vector': {'color': '紫色', 'description': '向量（菱形）'},
        'Boolean': {'color': '蓝色', 'description': '布尔（菱形）'},
        'Rotation': {'color': '棕色', 'description': '旋转（菱形）'},
        'Matrix': {'color': '粉红色', 'description': '4x4矩阵（菱形）'},
        'Material': {'color': '浅绿', 'description': '材质引用'},
        'Collection': {'color': '白色', 'description': '集合引用'},
        'Object': {'color': '白色', 'description': '对象引用'},
        'Image': {'color': '浅绿', 'description': '图像引用'},
        'String': {'color': '蓝绿色', 'description': '字符串'}
    }
    
    SOCKET_SHAPES = {
        'diamond': {'description': '菱形（字段或值）', 'use_case': '可被求值的字段'},
        'circle': {'description': '圆形（数据）', 'use_case': '几何体、对象引用等'},
        'square': {'description': '方形', 'use_case': '特定数据类型'}
    }
    
    DOMAIN_HIERARCHY = {
        'POINT': {'description': '点域（顶点/控制点）', 'use_case': '位置、法线'},
        'EDGE': {'description': '边域', 'use_case': '边折痕、边选择'},
        'FACE': {'description': '面域', 'use_case': '材质索引、面选择'},
        'CORNER': {'description': '角点域（面的顶点）', 'use_case': 'UV、顶点法线'},
        'CURVE': {'description': '曲线域（样条线）', 'use_case': '样条属性'},
        'INSTANCE': {'description': '实例域', 'use_case': '实例变换'},
        'LAYER': {'description': '图层域（4.2+）', 'use_case': '图层属性'}
    }
```

### 1.3 字段（Field）系统

字段是几何节点的核心概念。字段本质上是一个函数，它在与几何体相关联的特定域上求值，返回每个元素对应的值。这与常数值（Value）形成对比——常数值对所有元素都返回相同的值。

```python
class FieldSystem:
    """字段系统原子级规范"""
    
    FIELD_VS_VALUE = {
        'value': {
            'description': '常数值（对所有元素相同）',
            'socket_shape': '菱形（实心）',
            'example': '数学节点的常数输入',
            'evaluation': '只计算一次'
        },
        'field': {
            'description': '字段（按元素求值的函数）',
            'socket_shape': '菱形（空心）',
            'example': 'Position节点输出的位置字段',
            'evaluation': '每个元素独立计算',
            'composition': '可与其他字段组合形成新字段'
        }
    }
    
    COMMON_FIELD_CONTEXTS = {
        'position': {
            'node': 'Position节点',
            'domain': 'POINT',
            'output_type': 'Vector',
            'description': '返回每个点/顶点/控制点的位置'
        },
        'normal': {
            'node': 'Normal节点',
            'domain': '自动适配（FACE/CORNER）',
            'output_type': 'Vector',
            'description': '返回每个面或顶点的法线'
        },
        'id': {
            'node': 'ID节点',
            'domain': 'POINT',
            'output_type': 'Int',
            'description': '返回稳定的元素ID（跨编辑保持）'
        },
        'index': {
            'node': 'Index节点',
            'domain': 'POINT',
            'output_type': 'Int',
            'description': '返回元素索引（可能因编辑而变化）'
        },
        'spline_parameter': {
            'node': 'Spline Parameter节点',
            'domain': 'POINT（曲线）',
            'output_type': 'Float/Vector',
            'description': '返回曲线上的参数位置（0-1）'
        }
    }
    
    FIELD_OPERATIONS = {
        'math': {
            'node': 'Math节点',
            'inputs': ['Float字段A', 'Float字段B'],
            'operations': ['ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'POWER', 
                          'SINE', 'COSINE', 'TANGENT', 'SQRT', 'ABSOLUTE',
                          'MINIMUM', 'MAXIMUM', 'LESS_THAN', 'GREATER_THAN'],
            'use_case': '数值运算'
        },
        'vector_math': {
            'node': 'Vector Math节点',
            'inputs': ['Vector字段A', 'Vector字段B'],
            'operations': ['ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE',
                          'CROSS_PRODUCT', 'PROJECT', 'REFLECT', 'DOT_PRODUCT',
                          'DISTANCE', 'LENGTH', 'SCALE', 'NORMALIZE',
                          'WRAP', 'FLOOR', 'CEIL', 'FRACTION', 'ABSOLUTE', 'SNAP'],
            'use_case': '向量运算'
        },
        'capture_attribute': {
            'node': 'Capture Attribute节点',
            'description': '捕获字段为命名属性',
            'use_case': '在节点图中保存中间字段供后续使用',
            'output': '几何体 + 字段值'
        },
        'field_at_index': {
            'node': 'Field at Index节点（4.2+）',
            'description': '在特定索引处求值字段',
            'use_case': '访问其他元素的字段值'
        }
    }
```

### 1.4 属性系统与数据类型

```python
class AttributeSystem:
    """属性系统原子级规范"""
    
    BUILTIN_ATTRIBUTES = {
        'mesh': {
            'position': {'domain': 'POINT', 'type': 'FLOAT_VECTOR', 'description': '顶点位置（不可删除）'},
            'normal': {'domain': 'FACE', 'type': 'FLOAT_VECTOR', 'description': '面法线（自动计算）'},
            'sharp_face': {'domain': 'FACE', 'type': 'BOOLEAN', 'description': '锐利面标记'},
            'shade_smooth': {'domain': 'FACE', 'type': 'BOOLEAN', 'description': '平滑着色'},
            'material_index': {'domain': 'FACE', 'type': 'INT', 'description': '材质索引'},
            'crease': {'domain': 'EDGE', 'type': 'FLOAT', 'description': '细分折痕'},
            'material_slot_names': {'domain': 'LAYER', 'type': 'STRING', 'description': '材质槽名称'}
        },
        'curve': {
            'position': {'domain': 'POINT', 'type': 'FLOAT_VECTOR', 'description': '控制点位置'},
            'radius': {'domain': 'POINT', 'type': 'FLOAT', 'default': 1.0, 'description': '控制点半径'},
            'tilt': {'domain': 'POINT', 'type': 'FLOAT', 'default': 0.0, 'description': '倾斜角度'},
            'cyclic': {'domain': 'CURVE', 'type': 'BOOLEAN', 'description': '是否闭合'},
            'resolution': {'domain': 'CURVE', 'type': 'INT', 'description': '细分分辨率'}
        },
        'instances': {
            'position': {'domain': 'INSTANCE', 'type': 'FLOAT_VECTOR', 'description': '实例位置'},
            'rotation': {'domain': 'INSTANCE', 'type': 'FLOAT_VECTOR', 'description': '实例旋转'},
            'scale': {'domain': 'INSTANCE', 'type': 'FLOAT_VECTOR', 'description': '实例缩放'},
            'instance_reference': {'domain': 'INSTANCE', 'type': 'REFERENCE', 'description': '实例引用对象'}
        }
    }
    
    NAMED_ATTRIBUTE_NODES = {
        'store_named_attribute': {
            'node': 'Store Named Attribute节点',
            'description': '存储命名属性',
            'inputs': ['Geometry', 'Name', 'Value (字段)'],
            'domain': '可选择domain',
            'use_case': '保存中间数据供后续节点或外部使用'
        },
        'named_attribute': {
            'node': 'Named Attribute节点',
            'description': '读取命名属性',
            'inputs': ['Name'],
            'output': '字段值',
            'use_case': '读取之前存储的属性'
        },
        'remove_attribute': {
            'node': 'Remove Attribute节点',
            'description': '删除命名属性',
            'inputs': ['Geometry', 'Name'],
            'use_case': '清理不需要的属性'
        }
    }
    
    @staticmethod
    def create_geometry_nodes_modifier_example():
        """创建几何节点修改器示例"""
        return '''
import bpy

# 创建新的几何节点组
def create_simple_geo_node_group(name="SimpleDeform"):
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    
    # 创建Group Input和Output
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-400, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (400, 0)
    
    # 创建接口
    ng.inputs.new('NodeSocketGeometry', 'Geometry')
    ng.outputs.new('NodeSocketGeometry', 'Geometry')
    
    # 创建变换节点
    transform = ng.nodes.new('GeometryNodeTransform')
    transform.location = (0, 0)
    
    # 连接
    ng.links.new(input_node.outputs['Geometry'], transform.inputs['Geometry'])
    ng.links.new(transform.outputs['Geometry'], output_node.inputs['Geometry'])
    
    return ng

# 应用到对象
obj = bpy.context.active_object
modifier = obj.modifiers.new(name="GeometryNodes", type='NODES')
modifier.node_group = create_simple_geo_node_group()
'''
```

---

## 二、核心节点详解

### 2.1 输入节点

```python
class InputNodes:
    """输入节点原子级规范"""
    
    INPUT_NODES = {
        'position': {
            'class': 'GeometryNodeInputPosition',
            'output_type': 'Vector字段',
            'domain': 'POINT',
            'description': '返回每个顶点/控制点的位置',
            'use_case': '基于位置的变形、噪声扰动'
        },
        'normal': {
            'class': 'GeometryNodeInputNormal',
            'output_type': 'Vector字段',
            'domain': '自动',
            'description': '返回法线方向',
            'use_case': '沿法线挤出、偏移'
        },
        'id': {
            'class': 'GeometryNodeInputID',
            'output_type': 'Int字段',
            'domain': 'POINT',
            'description': '返回稳定的元素ID',
            'use_case': '随机性种子、稳定识别'
        },
        'index': {
            'class': 'GeometryNodeInputIndex',
            'output_type': 'Int字段',
            'domain': 'POINT',
            'description': '返回元素索引',
            'use_case': '按索引分组、序列化操作'
        },
        'scene_time': {
            'class': 'GeometryNodeInputSceneTime',
            'output_type': 'Float值',
            'sub_outputs': ['Seconds', 'Frame'],
            'description': '场景时间',
            'use_case': '时间驱动动画'
        },
        'random_value': {
            'class': 'GeometryNodeRandomValue',
            'output_type': '多种类型',
            'parameters': {
                'min': {'type': 'Float/Vector/Int', 'default': 0.0},
                'max': {'type': 'Float/Vector/Int', 'default': 1.0},
                'probability': {'type': 'Float', 'default': 0.5, 'range': [0, 1], 'description': '仅Boolean模式'},
                'id': {'type': 'Int字段', 'description': '随机种子（可选）'},
                'seed': {'type': 'Int', 'default': 0}
            },
            'description': '随机值生成',
            'use_case': '随机化位置、缩放、旋转'
        },
        'value': {
            'class': 'ShaderNodeValue',
            'output_type': 'Float值',
            'description': '常数值',
            'use_case': '常数参数输入'
        },
        'vector': {
            'class': 'FunctionNodeInputVector',
            'output_type': 'Vector值',
            'description': '常向量',
            'use_case': '常向量输入'
        },
        'color': {
            'class': 'FunctionNodeInputColor',
            'output_type': 'Color值',
            'description': '常颜色',
            'use_case': '常颜色输入'
        },
        'boolean': {
            'class': 'FunctionNodeInputBoolean',
            'output_type': 'Boolean值',
            'description': '常布尔',
            'use_case': '开关控制'
        },
        'integer': {
            'class': 'FunctionNodeInputInt',
            'output_type': 'Int值',
            'description': '常整数',
            'use_case': '整数参数'
        },
        'string': {
            'class': 'FunctionNodeInputString',
            'output_type': 'String值',
            'description': '常字符串',
            'use_case': '属性名、命名'
        },
        'object': {
            'class': 'GeometryNodeObjectInfo',
            'output_type': 'Geometry + Transform',
            'description': '获取对象信息',
            'use_case': '将外部对象引入节点图'
        },
        'collection_info': {
            'class': 'GeometryNodeCollectionInfo',
            'output_type': 'Instances',
            'parameters': {
                'collection': {'type': 'Collection', 'description': '集合引用'},
                'separate_children': {'type': 'Boolean', 'default': False},
                'reset_children': {'type': 'Boolean', 'default': True}
            },
            'description': '获取集合中所有对象',
            'use_case': '实例化集合、批量生成'
        },
        'image_info': {
            'class': 'GeometryNodeImageInfo',
            'output_type': '多个值',
            'description': '获取图像信息',
            'use_case': '图像尺寸、颜色空间'
        },
        'is_viewport': {
            'class': 'GeometryNodeIsViewport',
            'output_type': 'Boolean值',
            'description': '是否在视口中求值',
            'use_case': '视口与渲染差异化处理'
        }
    }
```

### 2.2 几何操作节点

```python
class GeometryOperationNodes:
    """几何操作节点原子级规范"""
    
    GEOMETRY_NODES = {
        'transform': {
            'class': 'GeometryNodeTransform',
            'inputs': ['Geometry', 'Translation', 'Rotation', 'Scale'],
            'description': '变换几何体',
            'use_case': '移动、旋转、缩放整个几何体',
            'note': '影响所有元素'
        },
        'join_geometry': {
            'class': 'GeometryNodeJoinGeometry',
            'inputs': ['多个Geometry输入'],
            'description': '合并多个几何体',
            'use_case': '组合多个分支结果',
            'note': '属性需匹配，不匹配的属性会丢失'
        },
        'separate_geometry': {
            'class': 'GeometryNodeSeparateGeometry',
            'inputs': ['Geometry', 'Selection (字段)'],
            'parameters': {
                'domain': {'options': ['POINT', 'EDGE', 'FACE', 'CURVE', 'INSTANCE'], 'default': 'POINT'}
            },
            'outputs': ['Selection', 'Inverted'],
            'description': '分离几何体',
            'use_case': '根据条件分离元素'
        },
        'delete_geometry': {
            'class': 'GeometryNodeDeleteGeometry',
            'inputs': ['Geometry', 'Selection (字段)', 'Mode'],
            'parameters': {
                'mode': {'options': ['ALL', 'EDGE_FACE', 'ONLY_FACE'], 'default': 'ALL'},
                'domain': {'options': ['POINT', 'EDGE', 'FACE', 'CURVE', 'INSTANCE']}
            },
            'description': '删除选中的几何元素',
            'use_case': '布尔裁剪、剪裁'
        },
        'merge_by_distance': {
            'class': 'GeometryNodeMergeByDistance',
            'inputs': ['Geometry', 'Selection', 'Distance'],
            'description': '按距离合并顶点',
            'use_case': '焊接重叠顶点、清理网格'
        },
        'subdivide_mesh': {
            'class': 'GeometryNodeSubdivideMesh',
            'inputs': ['Mesh', 'Level'],
            'description': '细分网格',
            'use_case': '增加网格密度',
            'note': 'Level是整数，0-7'
        },
        'subdivision_surface': {
            'class': 'GeometryNodeSubdivisionSurface',
            'inputs': ['Mesh', 'Level', 'Creases', 'Boundary Smooth', 'Smooth UVs'],
            'description': '细分表面（Catmull-Clark）',
            'use_case': '平滑细分、高质量建模'
        },
        'triangulate': {
            'class': 'GeometryNodeTriangulate',
            'inputs': ['Mesh', 'Minimum Vertices', 'Keep Custom Normals', 'Method'],
            'parameters': {
                'quad_method': {'options': ['BEAUTIFUL', 'FIXED', 'FIXED_ALTERNATE', 'SHORTEST_DIAGONAL', 'LONGEST_DIAGONAL']},
                'ngon_method': {'options': ['BEAUTIFUL', 'CLIP']}
            },
            'description': '三角化网格',
            'use_case': '游戏导出、稳定拓扑'
        },
        'scale_elements': {
            'class': 'GeometryNodeScaleElements',
            'inputs': ['Mesh', 'Selection', 'Scale', 'Center', 'Axis', 'Domain'],
            'description': '缩放元素',
            'use_case': '面缩放、边缩放'
        },
        'extrude_mesh': {
            'class': 'GeometryNodeExtrudeMesh',
            'inputs': ['Mesh', 'Selection', 'Offset (Vector字段)', 'Offset Scale'],
            'parameters': {
                'mode': {'options': ['VERTICES', 'EDGES', 'FACES'], 'default': 'FACES'}
            },
            'outputs': ['Top', 'Side'],
            'description': '挤出网格元素',
            'use_case': '建模挤出操作'
        },
        'flip_faces': {
            'class': 'GeometryNodeFlipFaces',
            'inputs': ['Mesh', 'Selection'],
            'description': '翻转面',
            'use_case': '修复法线方向'
        },
        'scale_instances': {
            'class': 'GeometryNodeScaleInstances',
            'inputs': ['Instances', 'Selection', 'Scale', 'Center', 'Local Spaces'],
            'description': '缩放实例',
            'use_case': '实例尺寸调整'
        },
        'rotate_instances': {
            'class': 'GeometryNodeRotateInstances',
            'inputs': ['Instances', 'Selection', 'Rotation', 'Pivot Point', 'Local Space'],
            'description': '旋转实例',
            'use_case': '实例方向调整'
        },
        'translate_instances': {
            'class': 'GeometryNodeTranslateInstances',
            'inputs': ['Instances', 'Selection', 'Translation', 'Local Space'],
            'description': '平移实例',
            'use_case': '实例位置调整'
        }
    }
    
    @staticmethod
    def create_procedural_deform_example():
        """程序化变形示例"""
        return '''
import bpy
import mathutils

def create_noise_deform_group():
    \"\"\"创建噪波变形节点组\"\"\"
    ng = bpy.data.node_groups.new('NoiseDeform', 'GeometryNodeTree')
    
    # 接口
    ng.inputs.new('NodeSocketGeometry', 'Geometry')
    ng.inputs.new('NodeSocketFloat', 'Strength')
    ng.inputs[1].default_value = 1.0
    ng.inputs.new('NodeSocketFloat', 'Scale')
    ng.inputs[2].default_value = 5.0
    ng.outputs.new('NodeSocketGeometry', 'Geometry')
    
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-800, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (800, 0)
    
    # 位置节点
    pos = ng.nodes.new('GeometryNodeInputPosition')
    pos.location = (-600, 200)
    
    # 噪波纹理节点
    noise = ng.nodes.new('GeometryNodeTexNoise')
    noise.location = (-400, 100)
    noise.inputs['Scale'].default_value = 5.0
    
    # 法线节点
    normal = ng.nodes.new('GeometryNodeInputNormal')
    normal.location = (-400, -100)
    
    # 向量数学（缩放法线）
    vec_scale = ng.nodes.new('ShaderNodeVectorMath')
    vec_scale.location = (-200, -100)
    vec_scale.operation = 'SCALE'
    
    # 向量数学（位置 + 偏移）
    vec_add = ng.nodes.new('ShaderNodeVectorMath')
    vec_add.location = (0, 0)
    vec_add.operation = 'ADD'
    
    # Set Position节点
    set_pos = ng.nodes.new('GeometryNodeSetPosition')
    set_pos.location = (200, 0)
    
    # 连接
    ng.links.new(pos.outputs['Position'], noise.inputs['Vector'])
    ng.links.new(noise.outputs['Fac'], vec_scale.inputs['Scale'])
    ng.links.new(normal.outputs['Normal'], vec_scale.inputs['Vector'])
    ng.links.new(pos.outputs['Position'], vec_add.inputs[0])
    ng.links.new(vec_scale.outputs['Vector'], vec_add.inputs[1])
    ng.links.new(input_node.outputs['Geometry'], set_pos.inputs['Geometry'])
    ng.links.new(vec_add.outputs['Vector'], set_pos.inputs['Position'])
    ng.links.new(set_pos.outputs['Geometry'], output_node.inputs['Geometry'])
    
    # 连接强度参数
    ng.links.new(input_node.outputs['Strength'], vec_scale.inputs['Scale'])
    ng.links.new(input_node.outputs['Scale'], noise.inputs['Scale'])
    
    return ng

# 应用
obj = bpy.context.active_object
mod = obj.modifiers.new(name='NoiseDeform', type='NODES')
mod.node_group = create_noise_deform_group()
'''
```

### 2.3 曲线节点

```python
class CurveNodes:
    """曲线节点原子级规范"""
    
    CURVE_NODES = {
        'curve_to_mesh': {
            'class': 'GeometryNodeCurveToMesh',
            'inputs': ['Curve', 'Profile Curve', 'Fill Caps'],
            'description': '曲线转网格',
            'use_case': '路径建模、文字、管状几何'
        },
        'curve_to_points': {
            'class': 'GeometryNodeCurveToPoints',
            'inputs': ['Curve', 'Count/Length', 'Mode'],
            'parameters': {
                'mode': {'options': ['COUNT', 'LENGTH', 'EVALUATED']}
            },
            'outputs': ['Points', 'Tangent', 'Normal', 'Rotation'],
            'description': '曲线转点',
            'use_case': '在曲线上分布点、实例化'
        },
        'resample_curve': {
            'class': 'GeometryNodeResampleCurve',
            'inputs': ['Curve', 'Selection', 'Count/Length', 'Mode'],
            'parameters': {
                'mode': {'options': ['EVALUATED', 'COUNT', 'LENGTH']}
            },
            'description': '重采样曲线',
            'use_case': '均匀分布控制点'
        },
        'subdivide_curve': {
            'class': 'GeometryNodeSubdivideCurve',
            'inputs': ['Curve', 'Cuts'],
            'description': '细分曲线',
            'use_case': '增加控制点密度'
        },
        'trim_curve': {
            'class': 'GeometryNodeTrimCurve',
            'inputs': ['Curve', 'Selection', 'Start', 'End'],
            'parameters': {
                'mode': {'options': ['FACTOR', 'LENGTH']}
            },
            'description': '修剪曲线',
            'use_case': '截取曲线段'
        },
        'curve_length': {
            'class': 'GeometryNodeCurveLength',
            'inputs': ['Curve'],
            'output_type': 'Float值',
            'description': '计算曲线长度',
            'use_case': '路径长度计算'
        },
        'curve_circle': {
            'class': 'GeometryNodeCurveCircle',
            'parameters': {
                'mode': {'options': ['POINTS', 'RADIUS']}
            },
            'outputs': ['Curve', 'Center'],
            'description': '创建圆形曲线',
            'use_case': '圆形基础形状'
        },
        'curve_line': {
            'class': 'GeometryNodeCurveLine',
            'inputs': ['Start', 'End'],
            'description': '创建直线曲线',
            'use_case': '直线基础形状'
        },
        'curve_spiral': {
            'class': 'GeometryNodeCurveSpiral',
            'inputs': ['Resolution', 'Rotations', 'Start Radius', 'End Radius', 'Height'],
            'description': '创建螺旋曲线',
            'use_case': '螺旋、弹簧'
        },
        'quadratic_bezier': {
            'class': 'GeometryNodeCurveQuadraticBezier',
            'inputs': ['Resolution', 'Start', 'Middle', 'End'],
            'description': '二次贝塞尔曲线',
            'use_case': '简单贝塞尔曲线'
        },
        'bezier_segment': {
            'class': 'GeometryNodeCurveBezierSegment',
            'inputs': ['Resolution', 'Start', 'Handle 1', 'Handle 2', 'End'],
            'parameters': {
                'mode': {'options': ['POSITION', 'POSITION_AND_HANDLES']}
            },
            'description': '三次贝塞尔段',
            'use_case': '复杂贝塞尔曲线'
        },
        'set_curve_normal': {
            'class': 'GeometryNodeSetCurveNormal',
            'inputs': ['Curve', 'Mode'],
            'parameters': {
                'mode': {'options': ['MINIMUM_TWIST', 'Z_UP', 'POLY']}
            },
            'description': '设置曲线法线模式',
            'use_case': '控制曲线转网格时的旋转方向'
        },
        'set_curve_radius': {
            'class': 'GeometryNodeSetCurveRadius',
            'inputs': ['Curve', 'Selection', 'Radius (字段)'],
            'description': '设置曲线半径',
            'use_case': '变量半径管状建模'
        },
        'set_curve_tilt': {
            'class': 'GeometryNodeSetCurveTilt',
            'inputs': ['Curve', 'Selection', 'Tilt (字段)'],
            'description': '设置曲线倾斜',
            'use_case': '控制曲线扭转'
        },
        'curve_handle_positions': {
            'class': 'GeometryNodeCurveHandlePositions',
            'inputs': ['Curve', 'Selection'],
            'outputs': ['Left', 'Right'],
            'description': '获取曲线手柄位置',
            'use_case': '访问贝塞尔手柄'
        },
        'set_handle_positions': {
            'class': 'GeometryNodeSetHandlePositions',
            'inputs': ['Curve', 'Selection', 'Position', 'Offset'],
            'parameters': {
                'mode': {'options': ['LEFT', 'RIGHT']}
            },
            'description': '设置曲线手柄位置',
            'use_case': '修改贝塞尔手柄'
        },
        'curve_handle_type_selection': {
            'class': 'GeometryNodeCurveHandleTypeSelection',
            'parameters': {
                'handle_type': {'options': ['AUTO', 'AUTO_ANIMATED', 'VECTOR', 'ALIGN', 'FREE_ALIGN', 'FREE']}
            },
            'description': '按手柄类型选择',
            'use_case': '批量修改手柄类型'
        }
    }
```

### 2.4 网格节点

```python
class MeshNodes:
    """网格节点原子级规范"""
    
    MESH_NODES = {
        'mesh_primitive_cube': {
            'class': 'GeometryNodeMeshCube',
            'inputs': ['Size (Vector)', 'Vertices X', 'Vertices Y', 'Vertices Z'],
            'description': '创建立方体',
            'use_case': '基础形状生成'
        },
        'mesh_primitive_cylinder': {
            'class': 'GeometryNodeMeshCylinder',
            'inputs': ['Vertices', 'Radius', 'Depth', 'Fill Type', 'Side Segments', 'Top Segments', 'Bottom Segments'],
            'description': '创建圆柱体',
            'use_case': '柱状基础形状'
        },
        'mesh_primitive_circle': {
            'class': 'GeometryNodeMeshCircle',
            'inputs': ['Vertices', 'Radius', 'Fill Type'],
            'description': '创建圆形',
            'use_case': '圆形基础形状'
        },
        'mesh_primitive_cone': {
            'class': 'GeometryNodeMeshCone',
            'inputs': ['Vertices', 'Side Segments', 'Fill Segments', 'Radius Top', 'Radius Bottom', 'Depth', 'Fill Type'],
            'description': '创建圆锥体',
            'use_case': '锥形基础形状'
        },
        'mesh_primitive_grid': {
            'class': 'GeometryNodeMeshGrid',
            'inputs': ['Size X', 'Size Y', 'Vertices X', 'Vertices Y'],
            'description': '创建网格平面',
            'use_case': '地形基础、平面建模'
        },
        'mesh_primitive_ico_sphere': {
            'class': 'GeometryNodeMeshIcoSphere',
            'inputs': ['Radius', 'Subdivisions'],
            'description': '创建二十面体球',
            'use_case': '均匀分布的球体'
        },
        'mesh_primitive_uv_sphere': {
            'class': 'GeometryNodeMeshUVSphere',
            'inputs': ['Segments', 'Rings', 'Radius'],
            'description': '创建UV球体',
            'use_case': '标准球体'
        },
        'mesh_line': {
            'class': 'GeometryNodeMeshLine',
            'inputs': ['Count', 'Resolution', 'Start Location', 'Offset', 'Mode'],
            'description': '创建网格线',
            'use_case': '网格阵列、序列点'
        },
        'mesh_to_points': {
            'class': 'GeometryNodeMeshToPoints',
            'inputs': ['Mesh', 'Selection', 'Mode'],
            'parameters': {
                'mode': {'options': ['VERTICES', 'EDGES', 'FACES', 'CORNERS']}
            },
            'description': '网格转点云',
            'use_case': '点云生成、粒子基础'
        },
        'mesh_to_curve': {
            'class': 'GeometryNodeMeshToCurve',
            'inputs': ['Mesh'],
            'description': '网格边转曲线',
            'use_case': '从网格提取路径'
        },
        'mesh_to_volume': {
            'class': 'GeometryNodeMeshToVolume',
            'inputs': ['Mesh', 'Density', 'Voxel Size', 'Voxel Amount', 'Fill Volume'],
            'description': '网格转体积',
            'use_case': '体积生成'
        },
        'volume_to_mesh': {
            'class': 'GeometryNodeVolumeToMesh',
            'inputs': ['Volume', 'Voxel Size', 'Threshold', 'Adaptivity'],
            'description': '体积转网格',
            'use_case': '从体积重建网格'
        },
        'dual_mesh': {
            'class': 'GeometryNodeDualMesh',
            'inputs': ['Mesh', 'Keep Boundaries'],
            'description': '对偶网格',
            'use_case': '网格拓扑转换'
        },
        'edge_paths_to_curves': {
            'class': 'GeometryNodeEdgePathsToCurves',
            'inputs': ['Mesh', 'Start Vertices', 'Next Vertex Index'],
            'description': '边路径转曲线',
            'use_case': '路径提取'
        },
        'set_shade_smooth': {
            'class': 'GeometryNodeSetShadeSmooth',
            'inputs': ['Mesh', 'Selection', 'Shade Smooth'],
            'parameters': {
                'domain': {'options': ['EDGE', 'FACE']}
            },
            'description': '设置平滑着色',
            'use_case': '批量平滑着色'
        },
        'set_material': {
            'class': 'GeometryNodeSetMaterial',
            'inputs': ['Geometry', 'Selection', 'Material'],
            'description': '设置材质',
            'use_case': '程序化材质分配'
        },
        'set_material_index': {
            'class': 'GeometryNodeSetMaterialIndex',
            'inputs': ['Geometry', 'Selection', 'Material Index'],
            'description': '设置材质索引',
            'use_case': '按索引分配材质'
        }
    }
```

### 2.5 实例化节点

```python
class InstancingNodes:
    """实例化节点原子级规范"""
    
    INSTANCING_NODES = {
        'instances_on_points': {
            'class': 'GeometryNodeInstanceOnPoints',
            'inputs': ['Points', 'Selection', 'Instance', 'Pick Instances',
                      'Choose Instance Index', 'Rotation', 'Scale'],
            'description': '在点上实例化几何',
            'use_case': '在曲线/网格点上分布对象',
            'note': 'Pick Instances用于从集合中随机选择实例'
        },
        'instance_transform': {
            'class': 'GeometryNodeInstanceTransform',
            'inputs': ['Instances', 'Translation', 'Rotation', 'Scale'],
            'description': '变换实例',
            'use_case': '批量实例变换'
        },
        'realize_instances': {
            'class': 'GeometryNodeRealizeInstances',
            'inputs': ['Geometry'],
            'description': '实例化实现（转换为实际几何）',
            'use_case': '导出、需要修改实例内容时',
            'note': '会大幅增加几何数量，谨慎使用'
        },
        'rotate_instances': {
            'class': 'GeometryNodeRotateInstances',
            'inputs': ['Instances', 'Selection', 'Rotation', 'Pivot Point', 'Local Space'],
            'description': '旋转实例',
            'use_case': '实例方向控制'
        },
        'scale_instances': {
            'class': 'GeometryNodeScaleInstances',
            'inputs': ['Instances', 'Selection', 'Scale', 'Center', 'Local Space'],
            'description': '缩放实例',
            'use_case': '实例尺寸控制'
        },
        'translate_instances': {
            'class': 'GeometryNodeTranslateInstances',
            'inputs': ['Instances', 'Selection', 'Translation', 'Local Space'],
            'description': '平移实例',
            'use_case': '实例位置控制'
        },
        'instance_rotation': {
            'class': 'GeometryNodeInputInstanceRotation',
            'output_type': 'Vector字段',
            'domain': 'INSTANCE',
            'description': '获取实例旋转',
            'use_case': '基于现有旋转的修改'
        },
        'instance_scale': {
            'class': 'GeometryNodeInputInstanceScale',
            'output_type': 'Vector字段',
            'domain': 'INSTANCE',
            'description': '获取实例缩放',
            'use_case': '基于现有缩放的修改'
        }
    }
    
    @staticmethod
    def create_point_distribution_example():
        """点分布实例化示例"""
        return '''
import bpy

def create_scatter_objects_group():
    \"\"\"创建对象散布节点组\"\"\"
    ng = bpy.data.node_groups.new('ScatterObjects', 'GeometryNodeTree')
    
    # 接口
    ng.inputs.new('NodeSocketGeometry', 'Target')
    ng.inputs.new('NodeSocketGeometry', 'Instance')
    ng.inputs.new('NodeSocketFloat', 'Density')
    ng.inputs[2].default_value = 0.5
    ng.inputs.new('NodeSocketFloat', 'Min Scale')
    ng.inputs[3].default_value = 0.5
    ng.inputs.new('NodeSocketFloat', 'Max Scale')
    ng.inputs[4].default_value = 1.5
    ng.inputs.new('NodeSocketInt', 'Seed')
    ng.inputs[5].default_value = 0
    ng.outputs.new('NodeSocketGeometry', 'Geometry')
    
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-1200, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (800, 0)
    
    # Distribute Points on Faces
    distribute = ng.nodes.new('GeometryNodeDistributePointsOnFaces')
    distribute.location = (-800, 100)
    distribute.distribute_method = 'RANDOM'
    
    # Random Value (Scale)
    random_scale = ng.nodes.new('GeometryNodeRandomValue')
    random_scale.location = (-400, -100)
    random_scale.data_type = 'FLOAT'
    
    # Random Value (Rotation)
    random_rot = ng.nodes.new('GeometryNodeRandomValue')
    random_rot.location = (-400, -300)
    random_rot.data_type = 'FLOAT_VECTOR'
    random_rot.inputs[0].default_value = (0.0, 0.0, 0.0)
    random_rot.inputs[1].default_value = (6.283, 6.283, 6.283)  # 2π
    
    # Instance on Points
    instance = ng.nodes.new('GeometryNodeInstanceOnPoints')
    instance.location = (0, 100)
    
    # 连接
    ng.links.new(input_node.outputs['Target'], distribute.inputs['Mesh'])
    ng.links.new(input_node.outputs['Density'], distribute.inputs['Density Max'])
    ng.links.new(input_node.outputs['Seed'], distribute.inputs['Seed'])
    
    ng.links.new(input_node.outputs['Min Scale'], random_scale.inputs[2])
    ng.links.new(input_node.outputs['Max Scale'], random_scale.inputs[3])
    
    ng.links.new(distribute.outputs['Points'], instance.inputs['Points'])
    ng.links.new(input_node.outputs['Instance'], instance.inputs['Instance'])
    ng.links.new(random_rot.outputs['Value'], instance.inputs['Rotation'])
    ng.links.new(random_scale.outputs['Value'], instance.inputs['Scale'])
    
    ng.links.new(instance.outputs['Instances'], output_node.inputs['Geometry'])
    
    return ng

# 使用
obj = bpy.context.active_object
mod = obj.modifiers.new(name='Scatter', type='NODES')
mod.node_group = create_scatter_objects_group()

# 设置实例对象（需要先创建一个简单对象作为实例）
# mod['Input_1'] = some_object
'''
```

---

## 三、程序化建模工作流

### 3.1 参数化建筑生成

```python
class ProceduralBuildingWorkflow:
    """参数化建筑生成工作流原子级规范"""
    
    BUILDING_PARAMETERS = {
        'dimensions': {
            'width': {'type': 'float', 'default': 20.0, 'range': [5, 200], 'description': '建筑宽度'},
            'depth': {'type': 'float', 'default': 15.0, 'range': [5, 200], 'description': '建筑深度'},
            'floor_height': {'type': 'float', 'default': 3.5, 'range': [2.5, 6], 'description': '楼层高度'},
            'floor_count': {'type': 'int', 'default': 5, 'range': [1, 50], 'description': '楼层数量'}
        },
        'windows': {
            'window_width': {'type': 'float', 'default': 1.5, 'range': [0.5, 5], 'description': '窗户宽度'},
            'window_height': {'type': 'float', 'default': 1.8, 'range': [0.5, 4], 'description': '窗户高度'},
            'windows_per_floor': {'type': 'int', 'default': 4, 'range': [1, 20], 'description': '每层窗户数'},
            'window_margin': {'type': 'float', 'default': 1.0, 'range': [0.1, 3], 'description': '窗户间距'}
        },
        'roof': {
            'roof_type': {'type': 'enum', 'options': ['FLAT', 'GABLE', 'HIP'], 'default': 'FLAT'},
            'roof_height': {'type': 'float', 'default': 2.0, 'range': [0, 10], 'description': '屋顶高度'},
            'roof_overhang': {'type': 'float', 'default': 0.5, 'range': [0, 3], 'description': '屋檐出挑'}
        },
        'materials': {
            'wall_material': {'type': 'material', 'description': '墙体材质'},
            'window_material': {'type': 'material', 'description': '窗户材质'},
            'roof_material': {'type': 'material', 'description': '屋顶材质'}
        }
    }
    
    @staticmethod
    def building_generation_workflow():
        """建筑生成工作流节点序列"""
        return {
            'step_1': {
                'name': '基础体积生成',
                'nodes': ['Mesh Cube（按尺寸）', 'Transform（设置位置）'],
                'output': '基础建筑体积'
            },
            'step_2': {
                'name': '楼层分割',
                'nodes': ['Subdivide Mesh', 'Index（楼层索引）', 'Math（计算楼层位置）'],
                'output': '按楼层分割的网格'
            },
            'step_3': {
                'name': '窗户位置计算',
                'nodes': [
                    'Position（顶点位置）',
                    'Math（归一化到0-1）',
                    'Vector Math（投影到墙面）',
                    'Separate XYZ（分离坐标）',
                    'Math（计算窗户网格位置）'
                ],
                'output': '窗户中心位置点云'
            },
            'step_4': {
                'name': '窗户生成',
                'nodes': [
                    'Instance on Points（在窗户位置实例化窗户预设）',
                    'Random Value（窗户随机变化）',
                    'Boolean（从墙体减去窗户洞口）'
                ],
                'output': '带窗户的建筑网格'
            },
            'step_5': {
                'name': '屋顶生成',
                'nodes': [
                    'Conditional（根据roof_type选择）',
                    'Mesh Primitive（创建屋顶基础）',
                    'Transform（位置调整）',
                    'Join Geometry（合并到主体）'
                ],
                'output': '完整建筑网格'
            },
            'step_6': {
                'name': '材质分配',
                'nodes': [
                    'Store Named Attribute（标记元素类型）',
                    'Set Material（按属性分配材质）'
                ],
                'output': '带材质的建筑'
            }
        }
    
    @staticmethod
    def create_parametric_building_example():
        """参数化建筑生成示例"""
        return '''
import bpy

def create_building_generator():
    \"\"\"创建参数化建筑生成器\"\"\"
    ng = bpy.data.node_groups.new('BuildingGenerator', 'GeometryNodeTree')
    
    # 接口
    ng.inputs.new('NodeSocketFloat', 'Width')
    ng.inputs[0].default_value = 20.0
    ng.inputs.new('NodeSocketFloat', 'Depth')
    ng.inputs[1].default_value = 15.0
    ng.inputs.new('NodeSocketFloat', 'Floor Height')
    ng.inputs[2].default_value = 3.5
    ng.inputs.new('NodeSocketInt', 'Floor Count')
    ng.inputs[3].default_value = 5
    ng.inputs.new('NodeSocketInt', 'Windows Per Floor')
    ng.inputs[4].default_value = 4
    ng.inputs.new('NodeSocketFloat', 'Window Width')
    ng.inputs[5].default_value = 1.5
    ng.inputs.new('NodeSocketFloat', 'Window Height')
    ng.inputs[6].default_value = 1.8
    ng.outputs.new('NodeSocketGeometry', 'Building')
    
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-1500, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (1500, 0)
    
    # 计算总高度
    total_height = ng.nodes.new('ShaderNodeMath')
    total_height.location = (-1200, 200)
    total_height.operation = 'MULTIPLY'
    
    # 创建基础立方体
    cube = ng.nodes.new('GeometryNodeMeshCube')
    cube.location = (-800, 200)
    
    # 设置立方体尺寸（向量构造）
    combine_size = ng.nodes.new('ShaderNodeCombineXYZ')
    combine_size.location = (-1000, 200)
    
    # Transform（移动到正确位置，让底部在原点）
    transform = ng.nodes.new('GeometryNodeTransform')
    transform.location = (-400, 200)
    
    # 窗户位置生成（在网格面上分布点）
    distribute = ng.nodes.new('GeometryNodeDistributePointsOnFaces')
    distribute.location = (0, 0)
    distribute.distribute_method = 'GRID'
    
    # 创建窗户基础形状
    window_cube = ng.nodes.new('GeometryNodeMeshCube')
    window_cube.location = (-400, -400)
    
    # 实例化窗户
    instance = ng.nodes.new('GeometryNodeInstanceOnPoints')
    instance.location = (400, 0)
    
    # 合并几何
    join = ng.nodes.new('GeometryNodeJoinGeometry')
    join.location = (800, 0)
    
    # 连接
    ng.links.new(input_node.outputs['Floor Height'], total_height.inputs[0])
    ng.links.new(input_node.outputs['Floor Count'], total_height.inputs[1])
    
    ng.links.new(input_node.outputs['Width'], combine_size.inputs['X'])
    ng.links.new(input_node.outputs['Depth'], combine_size.inputs['Y'])
    ng.links.new(total_height.outputs['Value'], combine_size.inputs['Z'])
    
    ng.links.new(combine_size.outputs['Vector'], cube.inputs['Size'])
    ng.links.new(cube.outputs['Mesh'], transform.inputs['Geometry'])
    
    # Transform的Z位移（半高，让底部在0）
    half_height = ng.nodes.new('ShaderNodeMath')
    half_height.location = (-600, 100)
    half_height.operation = 'MULTIPLY'
    half_height.inputs[1].default_value = 0.5
    ng.links.new(total_height.outputs['Value'], half_height.inputs[0])
    
    transform_offset = ng.nodes.new('ShaderNodeCombineXYZ')
    transform_offset.location = (-600, 50)
    transform_offset.inputs['X'].default_value = 0.0
    transform_offset.inputs['Y'].default_value = 0.0
    ng.links.new(half_height.outputs['Value'], transform_offset.inputs['Z'])
    ng.links.new(transform_offset.outputs['Vector'], transform.inputs['Translation'])
    
    # 窗户分布
    ng.links.new(transform.outputs['Geometry'], distribute.inputs['Mesh'])
    
    # 窗户尺寸
    window_size = ng.nodes.new('ShaderNodeCombineXYZ')
    window_size.location = (-200, -400)
    ng.links.new(input_node.outputs['Window Width'], window_size.inputs['X'])
    ng.links.new(input_node.outputs['Window Height'], window_size.inputs['Z'])
    window_size.inputs['Y'].default_value = 0.1  # 窗户深度
    
    ng.links.new(window_size.outputs['Vector'], window_cube.inputs['Size'])
    
    ng.links.new(distribute.outputs['Points'], instance.inputs['Points'])
    ng.links.new(window_cube.outputs['Mesh'], instance.inputs['Instance'])
    
    # 合并
    ng.links.new(transform.outputs['Geometry'], join.inputs[0])
    ng.links.new(instance.outputs['Instances'], join.inputs[1])
    
    ng.links.new(join.outputs['Geometry'], output_node.inputs['Building'])
    
    return ng

# 应用
obj = bpy.context.active_object
mod = obj.modifiers.new(name='Building', type='NODES')
mod.node_group = create_building_generator()
'''
```

### 3.2 程序化地形

```python
class ProceduralTerrainWorkflow:
    """程序化地形工作流原子级规范"""
    
    TERRAIN_PARAMETERS = {
        'base': {
            'size': {'type': 'float', 'default': 100.0, 'range': [10, 1000]},
            'resolution': {'type': 'int', 'default': 100, 'range': [10, 500]}
        },
        'noise': {
            'noise_type': {'type': 'enum', 'options': ['FBM', 'RIDGED', 'HETERO_TERRAIN', 'MULTIFRACTAL'], 'default': 'FBM'},
            'scale': {'type': 'float', 'default': 0.05, 'range': [0.001, 1]},
            'amplitude': {'type': 'float', 'default': 20.0, 'range': [1, 100]},
            'detail': {'type': 'float', 'default': 8.0, 'range': [1, 16]},
            'roughness': {'type': 'float', 'default': 0.5, 'range': [0, 1]},
            'offset': {'type': 'float', 'default': 0.0, 'range': [-100, 100]},
            'seed': {'type': 'int', 'default': 0, 'range': [0, 1000]}
        },
        'erosion': {
            'erosion_strength': {'type': 'float', 'default': 0.5, 'range': [0, 1]},
            'erosion_iterations': {'type': 'int', 'default': 100, 'range': [0, 1000]}
        },
        'vegetation': {
            'vegetation_density': {'type': 'float', 'default': 0.1, 'range': [0, 1]},
            'vegetation_height_range': {'type': 'vector', 'default': (0, 10, 0)},
            'vegetation_slope_max': {'type': 'float', 'default': 30.0, 'range': [0, 90]}
        }
    }
    
    @staticmethod
    def terrain_generation_steps():
        """地形生成步骤"""
        return {
            'step_1': '创建网格平面（Grid节点）',
            'step_2': '获取顶点位置（Position节点）',
            'step_3': '应用噪波纹理（Noise Texture）',
            'step_4': '调整高度范围（Map Range / Math）',
            'step_5': '设置顶点Z坐标（Set Position节点）',
            'step_6': '计算法线（Normal节点）',
            'step_7': '计算坡度（Vector Math - Angle）',
            'step_8': '根据高度和坡度分配材质',
            'step_9': '在合适位置分布植被（Distribute Points on Faces）',
            'step_10': '实例化植被模型（Instance on Points）'
        }
    
    @staticmethod
    def create_terrain_example():
        """地形生成示例"""
        return '''
import bpy

def create_terrain_generator():
    \"\"\"创建地形生成器\"\"\"
    ng = bpy.data.node_groups.new('TerrainGenerator', 'GeometryNodeTree')
    
    # 接口
    ng.inputs.new('NodeSocketFloat', 'Size')
    ng.inputs[0].default_value = 100.0
    ng.inputs.new('NodeSocketInt', 'Resolution')
    ng.inputs[1].default_value = 100
    ng.inputs.new('NodeSocketFloat', 'Noise Scale')
    ng.inputs[2].default_value = 0.05
    ng.inputs.new('NodeSocketFloat', 'Height')
    ng.inputs[3].default_value = 20.0
    ng.inputs.new('NodeSocketFloat', 'Detail')
    ng.inputs[4].default_value = 8.0
    ng.inputs.new('NodeSocketInt', 'Seed')
    ng.inputs[5].default_value = 0
    ng.outputs.new('NodeSocketGeometry', 'Terrain')
    
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-1200, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (800, 0)
    
    # 网格平面
    grid = ng.nodes.new('GeometryNodeMeshGrid')
    grid.location = (-800, 0)
    
    # 位置输入
    pos = ng.nodes.new('GeometryNodeInputPosition')
    pos.location = (-800, 200)
    
    # 噪波纹理
    noise = ng.nodes.new('GeometryNodeTexNoise')
    noise.location = (-600, 200)
    
    # 高度缩放
    height_scale = ng.nodes.new('ShaderNodeMath')
    height_scale.location = (-400, 200)
    height_scale.operation = 'MULTIPLY'
    
    # 分离XYZ
    sep = ng.nodes.new('ShaderNodeSeparateXYZ')
    sep.location = (-400, 0)
    
    # 合并XYZ（新高度）
    combine = ng.nodes.new('ShaderNodeCombineXYZ')
    combine.location = (-200, 100)
    
    # Set Position
    set_pos = ng.nodes.new('GeometryNodeSetPosition')
    set_pos.location = (0, 100)
    
    # 连接
    ng.links.new(input_node.outputs['Size'], grid.inputs['Size X'])
    ng.links.new(input_node.outputs['Size'], grid.inputs['Size Y'])
    
    res_x = ng.nodes.new('ShaderNodeMath')
    res_x.location = (-1000, -200)
    res_x.operation = 'MULTIPLY'
    res_x.inputs[1].default_value = 0.01
    ng.links.new(input_node.outputs['Resolution'], res_x.inputs[0])
    
    # 噪波参数
    ng.links.new(pos.outputs['Position'], noise.inputs['Vector'])
    ng.links.new(input_node.outputs['Noise Scale'], noise.inputs['Scale'])
    ng.links.new(input_node.outputs['Detail'], noise.inputs['Detail'])
    ng.links.new(input_node.outputs['Seed'], noise.inputs['Seed'])
    
    ng.links.new(noise.outputs['Fac'], height_scale.inputs[0])
    ng.links.new(input_node.outputs['Height'], height_scale.inputs[1])
    
    ng.links.new(pos.outputs['Position'], sep.inputs['Vector'])
    ng.links.new(sep.outputs['X'], combine.inputs['X'])
    ng.links.new(sep.outputs['Y'], combine.inputs['Y'])
    ng.links.new(height_scale.outputs['Value'], combine.inputs['Z'])
    
    ng.links.new(grid.outputs['Mesh'], set_pos.inputs['Geometry'])
    ng.links.new(combine.outputs['Vector'], set_pos.inputs['Position'])
    
    ng.links.new(set_pos.outputs['Geometry'], output_node.inputs['Terrain'])
    
    return ng

# 应用
obj = bpy.context.active_object
mod = obj.modifiers.new(name='Terrain', type='NODES')
mod.node_group = create_terrain_generator()
'''
```

### 3.3 程序化道路

```python
class ProceduralRoadWorkflow:
    """程序化道路工作流原子级规范"""
    
    ROAD_PARAMETERS = {
        'path': {
            'path_curve': {'type': 'curve_object', 'description': '路径曲线'},
            'path_resolution': {'type': 'int', 'default': 100, 'range': [10, 1000]}
        },
        'road': {
            'road_width': {'type': 'float', 'default': 8.0, 'range': [1, 50]},
            'road_thickness': {'type': 'float', 'default': 0.2, 'range': [0.01, 2]},
            'road_segments': {'type': 'int', 'default': 4, 'range': [1, 20]}
        },
        'markings': {
            'marking_type': {'type': 'enum', 'options': ['NONE', 'CENTER_LINE', 'DASHED', 'DOUBLE_LINE']},
            'marking_width': {'type': 'float', 'default': 0.2, 'range': [0.05, 1]},
            'marking_color': {'type': 'color', 'default': (1, 1, 1, 1)}
        }
    }
    
    @staticmethod
    def road_generation_steps():
        """道路生成步骤"""
        return {
            'step_1': '获取路径曲线',
            'step_2': '重采样曲线（Resample Curve）',
            'step_3': '创建道路截面曲线（Curve Circle或Bezier）',
            'step_4': '曲线转网格（Curve to Mesh）',
            'step_5': '计算车道标线位置',
            'step_6': '实例化标线对象',
            'step_7': '合并所有几何体'
        }
```

### 3.4 程序化城市

```python
class ProceduralCityWorkflow:
    """程序化城市工作流原子级规范"""
    
    CITY_GENERATION_ALGORITHM = {
        'grid_based': {
            'description': '网格布局算法',
            'steps': [
                '创建网格点阵列',
                '为每个点分配地块属性',
                '根据地块属性选择建筑类型',
                '实例化建筑模型',
                '添加道路网格'
            ],
            'advantages': ['简单可控', '现代城市规划感'],
            'disadvantages': ['过于规整', '缺乏自然感']
        },
        'voronoi_based': {
            'description': '沃罗诺伊布局算法',
            'steps': [
                '随机分布种子点',
                '计算沃罗诺伊图',
                '将每个沃罗诺伊单元作为地块',
                '在每个地块中生成建筑',
                '沿单元边界生成道路'
            ],
            'advantages': ['自然有机', '适合古代城市'],
            'disadvantages': ['计算量大', '不可控']
        },
        'l_system': {
            'description': 'L-系统布局算法',
            'steps': [
                '定义道路生成规则',
                '迭代应用L-系统规则',
                '生成道路网络',
                '在道路间填充建筑',
                '添加细节'
            ],
            'advantages': ['有机生长', '真实感强'],
            'disadvantages': ['实现复杂', '参数敏感']
        }
    }
    
    CITY_BUILDING_TYPES = {
        'skyscraper': {
            'height_range': (50, 200),
            'footprint_range': (20, 40),
            'window_density': 'high',
            'material': 'glass'
        },
        'mid_rise': {
            'height_range': (15, 50),
            'footprint_range': (15, 30),
            'window_density': 'medium',
            'material': 'concrete_glass'
        },
        'low_rise': {
            'height_range': (5, 15),
            'footprint_range': (10, 25),
            'window_density': 'low',
            'material': 'brick_concrete'
        },
        'house': {
            'height_range': (3, 8),
            'footprint_range': (8, 15),
            'window_density': 'low',
            'material': 'brick_wood'
        }
    }
```

---

## 四、动画与模拟

### 4.1 几何节点动画

```python
class GeometryNodesAnimation:
    """几何节点动画原子级规范"""
    
    ANIMATION_DRIVERS = {
        'scene_time': {
            'node': 'Scene Time节点',
            'outputs': ['Seconds', 'Frame'],
            'use_case': '基于时间的动画',
            'example': '使用Frame输出驱动Math节点的Sin计算'
        },
        'custom_attribute': {
            'method': '在对象上创建自定义属性',
            'use_case': '从外部动画系统驱动',
            'example': 'obj["animation_phase"] = 0.5'
        },
        'driver': {
            'method': '使用Blender驱动器驱动节点参数',
            'use_case': '复杂动画曲线',
            'example': 'driver.expression = "sin(frame / 20) * 0.5"'
        }
    }
    
    ANIMATION_TYPES = {
        'time_driven': {
            'description': '时间驱动动画',
            'pattern': 'Scene Time → Math → Transform',
            'use_case': '旋转、脉动、波动'
        },
        'vertex_animation': {
            'description': '顶点动画',
            'pattern': 'Position → Noise → Set Position',
            'use_case': '波动表面、变形'
        },
        'instance_animation': {
            'description': '实例动画',
            'pattern': 'Index + Scene Time → Math → Instance Transform',
            'use_case': '波浪实例、序列动画'
        },
        'morphing': {
            'description': '形态变化',
            'pattern': 'Mix (Geometry) + Time → Blend',
            'use_case': '形状过渡、生长动画'
        }
    }
    
    @staticmethod
    def create_wave_animation_example():
        """波浪动画示例"""
        return '''
import bpy

def create_wave_animation_group():
    \"\"\"创建波浪动画节点组\"\"\"
    ng = bpy.data.node_groups.new('WaveAnimation', 'GeometryNodeTree')
    
    ng.inputs.new('NodeSocketGeometry', 'Geometry')
    ng.inputs.new('NodeSocketFloat', 'Wave Height')
    ng.inputs[1].default_value = 2.0
    ng.inputs.new('NodeSocketFloat', 'Wave Length')
    ng.inputs[2].default_value = 5.0
    ng.inputs.new('NodeSocketFloat', 'Speed')
    ng.inputs[3].default_value = 1.0
    ng.outputs.new('NodeSocketGeometry', 'Geometry')
    
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-1200, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (800, 0)
    
    # 场景时间
    time = ng.nodes.new('GeometryNodeInputSceneTime')
    time.location = (-1000, 200)
    
    # 位置
    pos = ng.nodes.new('GeometryNodeInputPosition')
    pos.location = (-1000, 0)
    
    # 分离XYZ
    sep = ng.nodes.new('ShaderNodeSeparateXYZ')
    sep.location = (-800, 0)
    
    # 计算距离（使用X和Y）
    dist = ng.nodes.new('ShaderNodeMath')
    dist.location = (-600, 100)
    dist.operation = 'MULTIPLY'
    dist.inputs[1].default_value = 1.0  # 将使用Wave Length
    
    # 波长除法
    wave_div = ng.nodes.new('ShaderNodeMath')
    wave_div.location = (-600, -100)
    wave_div.operation = 'DIVIDE'
    
    # 时间 × 速度
    time_speed = ng.nodes.new('ShaderNodeMath')
    time_speed.location = (-800, 200)
    time_speed.operation = 'MULTIPLY'
    
    # 距离 + 时间
    wave_input = ng.nodes.new('ShaderNodeMath')
    wave_input.location = (-400, 0)
    wave_input.operation = 'ADD'
    
    # Sin计算
    sin = ng.nodes.new('ShaderNodeMath')
    sin.location = (-200, 0)
    sin.operation = 'SINE'
    
    # 高度乘法
    height_mult = ng.nodes.new('ShaderNodeMath')
    height_mult.location = (0, 0)
    height_mult.operation = 'MULTIPLY'
    
    # 合并新位置
    combine = ng.nodes.new('ShaderNodeCombineXYZ')
    combine.location = (200, 0)
    
    # Set Position
    set_pos = ng.nodes.new('GeometryNodeSetPosition')
    set_pos.location = (400, 0)
    
    # 连接
    ng.links.new(pos.outputs['Position'], sep.inputs['Vector'])
    ng.links.new(sep.outputs['X'], dist.inputs[0])
    ng.links.new(input_node.outputs['Wave Length'], wave_div.inputs[1])
    ng.links.new(sep.outputs['X'], wave_div.inputs[0])
    
    ng.links.new(time.outputs['Seconds'], time_speed.inputs[0])
    ng.links.new(input_node.outputs['Speed'], time_speed.inputs[1])
    
    ng.links.new(wave_div.outputs['Value'], wave_input.inputs[0])
    ng.links.new(time_speed.outputs['Value'], wave_input.inputs[1])
    
    ng.links.new(wave_input.outputs['Value'], sin.inputs[0])
    ng.links.new(sin.outputs['Value'], height_mult.inputs[0])
    ng.links.new(input_node.outputs['Wave Height'], height_mult.inputs[1])
    
    ng.links.new(sep.outputs['X'], combine.inputs['X'])
    ng.links.new(sep.outputs['Y'], combine.inputs['Y'])
    ng.links.new(height_mult.outputs['Value'], combine.inputs['Z'])
    
    ng.links.new(input_node.outputs['Geometry'], set_pos.inputs['Geometry'])
    ng.links.new(combine.outputs['Vector'], set_pos.inputs['Position'])
    
    ng.links.new(set_pos.outputs['Geometry'], output_node.inputs['Geometry'])
    
    return ng

# 应用到平面
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
obj = bpy.context.active_object
# 细分平面
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=20)
bpy.ops.object.mode_set(mode='OBJECT')

mod = obj.modifiers.new(name='Wave', type='NODES')
mod.node_group = create_wave_animation_group()
'''
```

### 4.2 粒子模拟

```python
class ParticleSimulationInGeoNodes:
    """几何节点中的粒子模拟原子级规范"""
    
    PARTICLE_NODES_PATTERN = {
        'simulation_zone': {
            'node': 'Simulation Zone节点（4.0+）',
            'inputs': ['Geometry', 'Delta Time'],
            'outputs': ['Geometry (输出)', 'Delta Time'],
            'description': '模拟区域，在帧间保持状态',
            'use_case': '粒子系统、物理模拟'
        },
        'particle_emission': {
            'pattern': '在每帧从几何体生成新点',
            'nodes': ['Distribute Points on Faces', 'Simulation Zone Input'],
            'parameters': ['emission_rate', 'initial_velocity']
        },
        'particle_motion': {
            'pattern': '更新粒子位置',
            'nodes': ['Position', 'Vector Math (ADD velocity)', 'Set Position'],
            'forces': ['gravity', 'wind', 'turbulence']
        },
        'particle_lifecycle': {
            'pattern': '管理粒子生命周期',
            'nodes': ['Store Named Attribute (age)', 'Math (compare with max_age)', 'Delete Geometry']
        }
    }
    
    @staticmethod
    def create_particle_simulation_example():
        """粒子模拟示例"""
        return '''
import bpy

def create_particle_sim_group():
    \"\"\"创建粒子模拟节点组（需要4.0+）\"\"\"
    ng = bpy.data.node_groups.new('ParticleSim', 'GeometryNodeTree')
    
    # 接口
    ng.inputs.new('NodeSocketGeometry', 'Emitter')
    ng.inputs.new('NodeSocketInt', 'Emission Rate')
    ng.inputs[1].default_value = 10
    ng.inputs.new('NodeSocketFloat', 'Particle Lifetime')
    ng.inputs[2].default_value = 60.0
    ng.inputs.new('NodeSocketVector', 'Gravity')
    ng.inputs[3].default_value = (0, 0, -9.8)
    ng.outputs.new('NodeSocketGeometry', 'Particles')
    
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-1200, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (1200, 0)
    
    # 模拟区域
    sim_input = ng.nodes.new('GeometryNodeSimulationInput')
    sim_input.location = (-600, 0)
    sim_input_pair = None  # 输出节点
    
    sim_output = ng.nodes.new('GeometryNodeSimulationOutput')
    sim_output.location = (600, 0)
    
    # 配对模拟输入输出
    sim_output.pair_with_input(sim_input)
    
    # 在模拟区域内部：
    # 1. 生成新粒子
    distribute = ng.nodes.new('GeometryNodeDistributePointsOnFaces')
    distribute.location = (-400, 200)
    
    # 2. 给新粒子赋初速度
    initial_vel = ng.nodes.new('GeometryNodeRandomValue')
    initial_vel.location = (-200, 200)
    initial_vel.data_type = 'FLOAT_VECTOR'
    
    # 3. 合并新旧粒子
    join = ng.nodes.new('GeometryNodeJoinGeometry')
    join.location = (0, 100)
    
    # 4. 应用重力（更新速度）
    # 5. 更新位置
    # 6. 删除过期粒子
    
    # 连接（简化版）
    ng.links.new(input_node.outputs['Emitter'], distribute.inputs['Mesh'])
    ng.links.new(distribute.outputs['Points'], join.inputs[0])
    ng.links.new(sim_input.outputs['Geometry'], join.inputs[1])
    ng.links.new(join.outputs['Geometry'], sim_output.inputs['Geometry'])
    ng.links.new(sim_output.outputs['Geometry'], output_node.inputs['Particles'])
    
    return ng

# 注意：模拟区域需要正确的设置，这里只是基本框架
'''
```

### 4.3 布料模拟集成

```python
class ClothSimulationIntegration:
    """布料模拟集成原子级规范"""
    
    CLOTH_IN_GEOMETRY_NODES = {
        'approach_1': {
            'description': '使用Simulation Zone实现简单布料',
            'components': ['弹簧网络', '重力', '碰撞', '约束'],
            'limitation': '复杂度有限，性能受限'
        },
        'approach_2': {
            'description': '与Blender内置布料修改器集成',
            'components': ['几何节点生成网格', '布料修改器', '缓存'],
            'use_case': '需要高质量布料模拟时'
        }
    }
```

---

## 五、材质与渲染

### 5.1 几何节点材质分配

```python
class GeometryNodesMaterialAssignment:
    """几何节点材质分配原子级规范"""
    
    MATERIAL_ASSIGNMENT_NODES = {
        'set_material': {
            'class': 'GeometryNodeSetMaterial',
            'inputs': ['Geometry', 'Selection (字段)', 'Material'],
            'description': '设置材质',
            'use_case': '单一材质分配'
        },
        'set_material_index': {
            'class': 'GeometryNodeSetMaterialIndex',
            'inputs': ['Geometry', 'Selection', 'Material Index'],
            'description': '设置材质索引',
            'use_case': '从材质列表中选择'
        },
        'set_material_from_index': {
            'class': 'GeometryNodeSetMaterialFromIndex',
            'inputs': ['Geometry', 'Material Index'],
            'description': '从索引设置材质',
            'use_case': '基于属性的材质选择'
        },
        'material_selection': {
            'class': 'GeometryNodeMaterialSelection',
            'inputs': ['Material'],
            'output': 'Boolean字段',
            'description': '按材质选择',
            'use_case': '材质特定操作'
        },
        'material_index': {
            'class': 'GeometryNodeInputMaterialIndex',
            'output': 'Int字段',
            'description': '获取材质索引',
            'use_case': '基于材质索引的逻辑'
        }
    }
    
    @staticmethod
    def create_procedural_material_assignment():
        """程序化材质分配示例"""
        return '''
import bpy

def create_height_based_material_group():
    \"\"\"基于高度分配材质的节点组\"\"\"
    ng = bpy.data.node_groups.new('HeightMaterial', 'GeometryNodeTree')
    
    ng.inputs.new('NodeSocketGeometry', 'Geometry')
    ng.inputs.new('NodeSocketMaterial', 'Low Material')
    ng.inputs.new('NodeSocketMaterial', 'Mid Material')
    ng.inputs.new('NodeSocketMaterial', 'High Material')
    ng.inputs.new('NodeSocketFloat', 'Low Height')
    ng.inputs[4].default_value = 5.0
    ng.inputs.new('NodeSocketFloat', 'High Height')
    ng.inputs[5].default_value = 15.0
    ng.outputs.new('NodeSocketGeometry', 'Geometry')
    
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-800, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (800, 0)
    
    # 位置
    pos = ng.nodes.new('GeometryNodeInputPosition')
    pos.location = (-600, 200)
    
    # 分离Z
    sep = ng.nodes.new('ShaderNodeSeparateXYZ')
    sep.location = (-400, 200)
    
    # 判断高/中/低
    # 低: Z < Low Height
    low_compare = ng.nodes.new('ShaderNodeMath')
    low_compare.location = (-200, 200)
    low_compare.operation = 'LESS_THAN'
    
    # 高: Z > High Height
    high_compare = ng.nodes.new('ShaderNodeMath')
    high_compare.location = (-200, 100)
    high_compare.operation = 'GREATER_THAN'
    
    # 设置低材质
    set_low = ng.nodes.new('GeometryNodeSetMaterial')
    set_low.location = (0, 200)
    
    # 设置高材质
    set_high = ng.nodes.new('GeometryNodeSetMaterial')
    set_high.location = (200, 200)
    
    # 设置中材质（其他情况）
    set_mid = ng.nodes.new('GeometryNodeSetMaterial')
    set_mid.location = (400, 200)
    
    # 连接
    ng.links.new(pos.outputs['Position'], sep.inputs['Vector'])
    ng.links.new(sep.outputs['Z'], low_compare.inputs[0])
    ng.links.new(input_node.outputs['Low Height'], low_compare.inputs[1])
    ng.links.new(sep.outputs['Z'], high_compare.inputs[0])
    ng.links.new(input_node.outputs['High Height'], high_compare.inputs[1])
    
    ng.links.new(input_node.outputs['Geometry'], set_low.inputs['Geometry'])
    ng.links.new(low_compare.outputs['Value'], set_low.inputs['Selection'])
    ng.links.new(input_node.outputs['Low Material'], set_low.inputs['Material'])
    
    ng.links.new(set_low.outputs['Geometry'], set_high.inputs['Geometry'])
    ng.links.new(high_compare.outputs['Value'], set_high.inputs['Selection'])
    ng.links.new(input_node.outputs['High Material'], set_high.inputs['Material'])
    
    # 中材质：反转高和低的选择
    not_low = ng.nodes.new('ShaderNodeMath')
    not_low.location = (0, 100)
    not_low.operation = 'SUBTRACT'
    not_low.inputs[1].default_value = 1.0
    
    not_high = ng.nodes.new('ShaderNodeMath')
    not_high.location = (200, 100)
    not_high.operation = 'SUBTRACT'
    not_high.inputs[1].default_value = 1.0
    
    mid_select = ng.nodes.new('ShaderNodeMath')
    mid_select.location = (400, 100)
    mid_select.operation = 'MULTIPLY'
    
    ng.links.new(low_compare.outputs['Value'], not_low.inputs[0])
    ng.links.new(high_compare.outputs['Value'], not_high.inputs[0])
    ng.links.new(not_low.outputs['Value'], mid_select.inputs[0])
    ng.links.new(not_high.outputs['Value'], mid_select.inputs[1])
    
    ng.links.new(set_high.outputs['Geometry'], set_mid.inputs['Geometry'])
    ng.links.new(mid_select.outputs['Value'], set_mid.inputs['Selection'])
    ng.links.new(input_node.outputs['Mid Material'], set_mid.inputs['Material'])
    
    ng.links.new(set_mid.outputs['Geometry'], output_node.inputs['Geometry'])
    
    return ng
'''
```

### 5.2 UV与纹理

```python
class UVAndTextureNodes:
    """UV与纹理节点原子级规范"""
    
    UV_NODES = {
        'store_named_attribute_uv': {
            'method': '使用Store Named Attribute节点存储UV',
            'domain': 'CORNER',
            'data_type': 'FLOAT_VECTOR',
            'name': 'uv_map',
            'use_case': '程序化生成UV'
        },
        'uv_unwrap': {
            'node': 'GeometryNodeUVUnwrap',
            'inputs': ['Selection', 'Seam (字段)', 'Margin', 'Fill Holes'],
            'description': '自动UV展开',
            'use_case': '自动UV生成'
        },
        'attribute_to_uv': {
            'method': '将属性用作UV',
            'use_case': '从已有属性生成UV坐标'
        }
    }
    
    TEXTURE_NODES = {
        'texture_image': {
            'node': 'GeometryNodeImageTexture',
            'inputs': ['Image', 'Vector (UV)', 'Frame', 'Interpolation', 'Extension', 'Projection'],
            'outputs': ['Color', 'Alpha'],
            'description': '在几何节点中采样图像',
            'use_case': '基于图像的几何变形、地形高度图'
        },
        'noise_texture': {
            'node': 'GeometryNodeTexNoise',
            'parameters': ['Scale', 'Detail', 'Roughness', 'Dimension', 'Lacunarity', 'Normalize'],
            'use_case': '程序化噪声变形'
        },
        'voronoi_texture': {
            'node': 'GeometryNodeTexVoronoi',
            'parameters': ['Distance', 'Feature', 'Scale', 'Minkowski Exponent', 'Dimension'],
            'use_case': '细胞状结构、破裂效果'
        }
    }
    
    @staticmethod
    def create_displacement_from_texture():
        """从纹理置换示例"""
        return '''
import bpy

def create_texture_displacement_group():
    \"\"\"从图像纹理置换几何体\"\"\"
    ng = bpy.data.node_groups.new('TextureDisplacement', 'GeometryNodeTree')
    
    ng.inputs.new('NodeSocketGeometry', 'Geometry')
    ng.inputs.new('NodeSocketImage', 'Image')
    ng.inputs.new('NodeSocketFloat', 'Strength')
    ng.inputs[2].default_value = 1.0
    ng.outputs.new('NodeSocketGeometry', 'Geometry')
    
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-800, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (600, 0)
    
    # 位置（用作UV）
    pos = ng.nodes.new('GeometryNodeInputPosition')
    pos.location = (-600, 200)
    
    # 分离XYZ用于UV
    sep = ng.nodes.new('ShaderNodeSeparateXYZ')
    sep.location = (-400, 200)
    
    # 合并XY为UV（Z为0）
    uv = ng.nodes.new('ShaderNodeCombineXYZ')
    uv.location = (-200, 200)
    
    # 图像纹理
    img_tex = ng.nodes.new('GeometryNodeImageTexture')
    img_tex.location = (0, 200)
    
    # 分离颜色（取R通道）
    color_sep = ng.nodes.new('ShaderNodeSeparateColor')
    color_sep.location = (200, 200)
    
    # 强度乘法
    mult = ng.nodes.new('ShaderNodeMath')
    mult.location = (200, 0)
    mult.operation = 'MULTIPLY'
    
    # 合并新位置
    new_pos = ng.nodes.new('ShaderNodeCombineXYZ')
    new_pos.location = (200, -200)
    
    # Set Position
    set_pos = ng.nodes.new('GeometryNodeSetPosition')
    set_pos.location = (400, 0)
    
    # 连接
    ng.links.new(pos.outputs['Position'], sep.inputs['Vector'])
    ng.links.new(sep.outputs['X'], uv.inputs['X'])
    ng.links.new(sep.outputs['Y'], uv.inputs['Y'])
    
    ng.links.new(input_node.outputs['Image'], img_tex.inputs['Image'])
    ng.links.new(uv.outputs['Vector'], img_tex.inputs['Vector'])
    
    ng.links.new(img_tex.outputs['Color'], color_sep.inputs['Color'])
    ng.links.new(color_sep.outputs['Red'], mult.inputs[0])
    ng.links.new(input_node.outputs['Strength'], mult.inputs[1])
    
    ng.links.new(sep.outputs['X'], new_pos.inputs['X'])
    ng.links.new(sep.outputs['Y'], new_pos.inputs['Y'])
    ng.links.new(mult.outputs['Value'], new_pos.inputs['Z'])
    
    ng.links.new(input_node.outputs['Geometry'], set_pos.inputs['Geometry'])
    ng.links.new(new_pos.outputs['Vector'], set_pos.inputs['Position'])
    
    ng.links.new(set_pos.outputs['Geometry'], output_node.inputs['Geometry'])
    
    return ng
'''
```

---

## 六、性能优化

### 6.1 节点图优化

```python
class NodeGraphOptimization:
    """节点图优化原子级规范"""
    
    OPTIMIZATION_STRATEGIES = {
        'avoid_recomputation': {
            'description': '避免重复计算',
            'bad_practice': '在多个分支中重复计算相同的字段',
            'good_practice': '使用Capture Attribute存储中间结果',
            'benefit': '减少30-50%计算时间'
        },
        'use_instances': {
            'description': '使用实例而非真实几何',
            'bad_practice': '对每个重复几何使用Join Geometry',
            'good_practice': '使用Instance on Points + 实例化',
            'benefit': '内存减少90%，性能提升80%'
        },
        'simplify_node_chains': {
            'description': '简化节点链',
            'bad_practice': '多个Math节点串联（ADD后MULTIPLY再ADD）',
            'good_practice': '使用单个Math节点配合Map Range',
            'benefit': '减少节点求值开销'
        },
        'attribute_propagation': {
            'description': '属性传播优化',
            'bad_practice': '在不同domain间频繁切换',
            'good_practice': '保持domain一致性，必要时显式转换',
            'benefit': '减少domain转换开销'
        },
        'cache_intermediate': {
            'description': '缓存中间结果',
            'method': '使用Capture Attribute节点',
            'use_case': '复杂字段计算结果被多次使用时',
            'benefit': '避免重复求值'
        },
        'use_named_attributes_carefully': {
            'description': '谨慎使用命名属性',
            'warning': '过多的命名属性会增加内存使用和求值开销',
            'recommendation': '只在需要跨节点组传递时使用'
        }
    }
    
    PERFORMANCE_ANTI_PATTERNS = {
        'nested_realize_instances': {
            'description': '嵌套实例化实现',
            'problem': 'Realize Instances后再次实例化会导致几何爆炸',
            'solution': '尽量保持实例链，只在最终输出时实现'
        },
        'high_subdivision': {
            'description': '过高的细分级别',
            'problem': 'Subdivision Surface节点级别过高',
            'solution': '使用合理的细分级别，依赖渲染时细分'
        },
        'unnecessary_join': {
            'description': '不必要的合并',
            'problem': '过早使用Join Geometry',
            'solution': '保持几何分支独立，最后再合并'
        },
        'field_in_loops': {
            'description': '循环中的复杂字段',
            'problem': '在Repeat Zone中使用复杂字段',
            'solution': '简化循环内计算，预计算外部数据'
        }
    }
    
    @staticmethod
    def create_optimization_example():
        """优化示例"""
        return '''
# 优化前：重复计算位置
"""
Position → Math (Multiply 2) → Set Position
Position → Math (Multiply 2) → Other Operations
"""

# 优化后：使用Capture Attribute缓存
"""
Position → Capture Attribute → Set Position
                       ↓
              Other Operations
"""

# 实例化优化示例
import bpy

def optimized_scatter():
    \"\"\"优化的散布系统\"\"\"
    ng = bpy.data.node_groups.new('OptimizedScatter', 'GeometryNodeTree')
    
    # 接口
    ng.inputs.new('NodeSocketGeometry', 'Surface')
    ng.inputs.new('NodeSocketInt', 'Count')
    ng.inputs[1].default_value = 1000
    ng.inputs.new('NodeSocketCollection', 'Objects')
    ng.outputs.new('NodeSocketGeometry', 'Instances')
    
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-800, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (800, 0)
    
    # 获取对象集合作为实例
    collection_info = ng.nodes.new('GeometryNodeCollectionInfo')
    collection_info.location = (-600, -200)
    collection_info.inputs['Separate Children'].default_value = True
    collection_info.inputs['Reset Children'].default_value = True
    
    # 在表面分布点
    distribute = ng.nodes.new('GeometryNodeDistributePointsOnFaces')
    distribute.location = (-400, 100)
    distribute.distribute_method = 'RANDOM'
    
    # 随机选择实例索引
    random_index = ng.nodes.new('GeometryNodeRandomValue')
    random_index.location = (-200, -100)
    random_index.data_type = 'INT'
    random_index.inputs[2].default_value = 0  # min
    random_index.inputs[3].default_value = 10  # max (动态设置)
    
    # 实例化
    instance = ng.nodes.new('GeometryNodeInstanceOnPoints')
    instance.location = (0, 100)
    instance.inputs['Pick Instances'].default_value = True
    
    # 随机旋转
    random_rot = ng.nodes.new('GeometryNodeRandomValue')
    random_rot.location = (-200, -300)
    random_rot.data_type = 'FLOAT_VECTOR'
    random_rot.inputs[0].default_value = (0, 0, 0)
    random_rot.inputs[1].default_value = (6.283, 6.283, 6.283)
    
    # 随机缩放
    random_scale = ng.nodes.new('GeometryNodeRandomValue')
    random_scale.location = (-200, -500)
    random_scale.data_type = 'FLOAT'
    random_scale.inputs[2].default_value = 0.5
    random_scale.inputs[3].default_value = 2.0
    
    # 连接
    ng.links.new(input_node.outputs['Objects'], collection_info.inputs['Collection'])
    ng.links.new(input_node.outputs['Surface'], distribute.inputs['Mesh'])
    ng.links.new(input_node.outputs['Count'], distribute.inputs['Selection'])  # 简化
    
    ng.links.new(collection_info.outputs['Instances'], instance.inputs['Instance'])
    ng.links.new(distribute.outputs['Points'], instance.inputs['Points'])
    ng.links.new(random_index.outputs['Value'], instance.inputs['Choose Instance Index'])
    ng.links.new(random_rot.outputs['Value'], instance.inputs['Rotation'])
    ng.links.new(random_scale.outputs['Value'], instance.inputs['Scale'])
    
    # 不Realize，直接输出实例
    ng.links.new(instance.outputs['Instances'], output_node.inputs['Instances'])
    
    return ng
'''
```

### 6.2 视口性能

```python
class ViewportPerformance:
    """视口性能优化原子级规范"""
    
    VIEWPORT_OPTIMIZATION = {
        'lod_system': {
            'description': '详细级别（LOD）',
            'method': '根据相机距离切换几何复杂度',
            'nodes': ['Geometry Proximity', 'Switch', '不同细节的几何分支'],
            'benefit': '近处高细节，远处低细节，性能提升50-80%'
        },
        'occlusion_culling': {
            'description': '遮挡剔除',
            'method': '使用Geometry Proximity + Selection控制可见性',
            'benefit': '不渲染被遮挡的几何'
        },
        'viewport_simplify': {
            'description': '视口简化',
            'method': '使用Is Viewport节点差异化处理',
            'pattern': 'Switch节点（视口/渲染分支）',
            'benefit': '视口流畅，渲染高质量'
        },
        'instance_optimization': {
            'description': '实例优化',
            'method': '尽量使用实例而非真实几何',
            'benefit': 'GPU可以高效渲染大量实例'
        }
    }
    
    @staticmethod
    def create_lod_example():
        """LOD系统示例"""
        return '''
import bpy

def create_lod_system():
    \"\"\"创建LOD系统节点组\"\"\"
    ng = bpy.data.node_groups.new('LODSystem', 'GeometryNodeTree')
    
    # 接口
    ng.inputs.new('NodeSocketGeometry', 'High Detail')
    ng.inputs.new('NodeSocketGeometry', 'Mid Detail')
    ng.inputs.new('NodeSocketGeometry', 'Low Detail')
    ng.inputs.new('NodeSocketFloat', 'Camera Distance')
    ng.inputs.new('NodeSocketFloat', 'Mid Distance')
    ng.inputs[4].default_value = 50.0
    ng.inputs.new('NodeSocketFloat', 'Far Distance')
    ng.inputs[5].default_value = 200.0
    ng.outputs.new('NodeSocketGeometry', 'Geometry')
    
    input_node = ng.nodes.new('NodeGroupInput')
    input_node.location = (-600, 0)
    
    output_node = ng.nodes.new('NodeGroupOutput')
    output_node.location = (600, 0)
    
    # 比较距离
    close_compare = ng.nodes.new('ShaderNodeMath')
    close_compare.location = (-400, 0)
    close_compare.operation = 'LESS_THAN'
    
    mid_compare = ng.nodes.new('ShaderNodeMath')
    mid_compare.location = (-400, -200)
    mid_compare.operation = 'LESS_THAN'
    
    # Switch节点（4.2+或使用Math + Join）
    # 使用Index + Math选择
    
    # 简化版：直接根据距离选择
    # ...
    
    return ng
'''
```

---

## 七、与AE集成

### 7.1 几何节点模型导出

```python
class GeoNodesToAEExport:
    """几何节点模型导出到AE原子级规范"""
    
    EXPORT_WORKFLOWS = {
        'baked_geometry': {
            'description': '烘焙几何为静态网格',
            'steps': [
                '在特定帧应用几何节点修改器',
                '导出为OBJ/FBX',
                '在Element 3D或其他3D插件中导入'
            ],
            'advantages': ['兼容性好', '可在任何AE 3D插件中使用'],
            'disadvantages': ['丢失动画', '需要每帧手动处理']
        },
        'animation_sequence': {
            'description': '导出为动画序列',
            'steps': [
                '渲染几何节点动画为PNG/EXR序列',
                '在AE中导入序列',
                '作为2D层使用'
            ],
            'advantages': ['简单直接', '保留所有视觉效果'],
            'disadvantages': ['失去3D相机集成']
        },
        'camera_data_sync': {
            'description': '相机数据同步',
            'steps': [
                '从Blender导出相机动画数据',
                '在AE中通过表达式或脚本应用',
                '确保3D元素与2D合成对齐'
            ],
            'use_case': '将几何节点生成的3D元素与AE 2D元素结合'
        },
        'exr_multilayer': {
            'description': 'EXR多层渲染集成',
            'steps': [
                '在Blender中启用必要的渲染通道',
                '渲染为EXR多层序列',
                '在AE中导入并分离通道',
                '使用通道进行后期合成'
            ],
            'advantages': ['保留深度、法线等信息', '高质量合成'],
            'use_case': '复杂3D合成'
        }
    }
    
    @staticmethod
    def setup_geo_nodes_for_ae_export():
        """为AE导出配置几何节点"""
        return '''
import bpy

def setup_geo_nodes_render_for_ae():
    \"\"\"配置几何节点渲染以便AE集成\"\"\"
    scene = bpy.context.scene
    
    # 渲染设置
    scene.render.image_settings.file_format = 'OPEN_EXR_MULTILAYER'
    scene.render.image_settings.color_depth = '32'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.fps = 24
    
    # 启用渲染通道
    view_layer = scene.view_layers[0]
    view_layer.use_pass_combined = True
    view_layer.use_pass_z = True
    view_layer.use_pass_normal = True
    view_layer.use_pass_mist = True
    view_layer.use_pass_diffuse_direct = True
    view_layer.use_pass_specular_direct = True
    view_layer.use_pass_shadow = True
    view_layer.use_pass_ambient_occlusion = True
    
    # 加密对象通道（用于遮罩）
    view_layer.cycles.use_pass_crypto_object = True
    view_layer.cycles.crypto_depth = 6
    
    # 确保几何节点修改器在渲染时正确求值
    for obj in scene.objects:
        for mod in obj.modifiers:
            if mod.type == 'NODES':
                # 确保修改器在渲染时启用
                mod.show_render = True
                mod.show_viewport = True
    
    return {'status': 'success'}

# 执行
setup_geo_nodes_render_for_ae()
'''
```

### 7.2 程序化动画导出

```python
class ProceduralAnimationExport:
    """程序化动画导出原子级规范"""
    
    EXPORT_METHODS = {
        'json_keyframes': {
            'description': '导出为JSON关键帧数据',
            'process': [
                '在Blender中评估几何节点动画',
                '在每帧提取关键对象的位置/旋转/缩放',
                '导出为JSON文件',
                '在AE中通过脚本应用关键帧'
            ],
            'use_case': '同步几何节点生成的动画到AE对象'
        },
        'ae_expression': {
            'description': '生成AE表达式',
            'process': [
                '分析几何节点动画的数学规律',
                '将规律转换为AE表达式',
                '在AE中应用表达式到属性'
            ],
            'use_case': '可数学描述的动画（波浪、旋转等）'
        },
        'null_object_sync': {
            'description': '空对象同步',
            'process': [
                '在Blender中创建跟踪空对象',
                '将空对象位置约束到几何节点生成的元素',
                '导出空对象动画到AE',
                '在AE中使用空对象作为锚点'
            ],
            'use_case': '将动态生成的元素位置同步到AE'
        }
    }
    
    @staticmethod
    def export_animation_data_to_ae():
        """导出动画数据到AE"""
        return '''
import bpy
import json
import math

def export_geo_nodes_animation(obj_name, output_path, frame_range=(1, 120)):
    \"\"\"导出几何节点动画数据\"\"\"
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return None
    
    scene = bpy.context.scene
    fps = scene.render.fps
    
    # 数据结构
    data = {
        'object': obj_name,
        'fps': fps,
        'frame_range': list(frame_range),
        'keyframes': {
            'location': [],
            'rotation': [],
            'scale': []
        },
        'geo_nodes_outputs': []
    }
    
    # 遍历帧
    for frame in range(frame_range[0], frame_range[1] + 1):
        scene.frame_set(frame)
        scene.view_layer.update()
        
        time = (frame - frame_range[0]) / fps
        
        # 对象变换（受几何节点影响的世界变换）
        loc = obj.matrix_world.translation
        rot = obj.matrix_world.to_euler()
        scale = obj.matrix_world.to_scale()
        
        # 转换到AE坐标系
        ae_loc = [loc.x, -loc.z, -loc.y]
        ae_rot = [math.degrees(rot.x), -math.degrees(rot.z), math.degrees(rot.y)]
        ae_scale = [scale.x, scale.z, scale.y]
        
        data['keyframes']['location'].append({
            'time': time, 'frame': frame, 'value': ae_loc
        })
        data['keyframes']['rotation'].append({
            'time': time, 'frame': frame, 'value': ae_rot
        })
        data['keyframes']['scale'].append({
            'time': time, 'frame': frame, 'value': ae_scale
        })
    
    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return data


def generate_ae_apply_script(json_path, ae_layer_name):
    \"\"\"生成AE应用脚本\"\"\"
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    jsx_lines = [
        '// AE JSX脚本 - 应用Blender几何节点动画',
        f'var layer = app.project.activeItem.layer("{ae_layer_name}");',
        'if (!layer) { alert("未找到图层"); }',
        ''
    ]
    
    # 应用位置关键帧
    for kf in data['keyframes']['location']:
        v = kf['value']
        jsx_lines.append(
            f'layer.position.setValueAtTime({kf["time"]}, [{v[0]}, {v[1]}, {v[2]}]);'
        )
    
    # 应用旋转关键帧
    for kf in data['keyframes']['rotation']:
        v = kf['value']
        jsx_lines.append(
            f'layer.rotationX.setValueAtTime({kf["time"]}, {v[0]});'
        )
        jsx_lines.append(
            f'layer.rotationY.setValueAtTime({kf["time"]}, {v[1]});'
        )
        jsx_lines.append(
            f'layer.rotationZ.setValueAtTime({kf["time"]}, {v[2]});'
        )
    
    # 应用缩放关键帧
    for kf in data['keyframes']['scale']:
        v = kf['value']
        jsx_lines.append(
            f'layer.scale.setValueAtTime({kf["time"]}, [{v[0]*100}, {v[1]*100}, {v[2]*100}]);'
        )
    
    return '\\n'.join(jsx_lines)
'''
```

### 7.3 多通道渲染合成

```python
class MultiPassCompositing:
    """多通道渲染合成原子级规范"""
    
    PASS_COMPOSITION_STRATEGY = {
        'beauty_pass': {
            'description': '主渲染层（Combined）',
            'use_in_ae': '主图层',
            'blend_mode': 'Normal'
        },
        'depth_pass': {
            'description': '深度通道',
            'use_in_ae': '深度遮罩、景深模糊',
            'blend_mode': '用作遮罩'
        },
        'normal_pass': {
            'description': '法线通道',
            'use_in_ae': '重新打光、边缘检测',
            'blend_mode': 'Add或Screen'
        },
        'shadow_pass': {
            'description': '阴影通道',
            'use_in_ae': '阴影增强、阴影颜色调整',
            'blend_mode': 'Multiply'
        },
        'ao_pass': {
            'description': '环境光遮蔽通道',
            'use_in_ae': 'AO增强',
            'blend_mode': 'Multiply'
        },
        'diffuse_pass': {
            'description': '漫反射通道',
            'use_in_ae': '颜色调整',
            'blend_mode': 'Normal'
        },
        'specular_pass': {
            'description': '高光通道',
            'use_in_ae': '高光增强',
            'blend_mode': 'Add或Screen'
        },
        'crypto_object': {
            'description': '加密对象遮罩',
            'use_in_ae': '对象级遮罩',
            'use_case': '通过Cryptomatte插件提取'
        }
    }
    
    @staticmethod
    def create_ae_composition_template():
        """创建AE合成模板"""
        return '''
# AE合成结构模板（伪代码描述）
AE_COMPOSITION = {
    'main_comp': {
        'resolution': (1920, 1080),
        'fps': 24,
        'duration': '120帧',
        'layers': [
            {
                'name': 'Background',
                'type': 'solid',
                'color': '#000000'
            },
            {
                'name': 'Blender_Render',
                'type': 'EXR序列',
                'passes': {
                    'combined': 'Normal混合',
                    'shadow': 'Multiply 50%',
                    'ao': 'Multiply 80%',
                    'specular': 'Add 100%'
                }
            },
            {
                'name': 'Depth_FX',
                'type': '调整图层',
                'effects': ['Lens Blur（基于深度通道）'],
                'mask': 'Depth Pass'
            },
            {
                'name': 'Color_Correction',
                'type': '调整图层',
                'effects': ['Curves', 'HSL', 'Exposure']
            },
            {
                'name': 'Overlay_FX',
                'type': '调整图层',
                'effects': ['Glow', 'Vignette']
            }
        ]
    }
}
'''
```

---

## 附录

### 附录A：几何节点速查表

```python
class GeometryNodesQuickReference:
    """几何节点速查表"""
    
    QUICK_REFERENCE = {
        '输入节点': {
            'Position': '获取顶点/控制点位置',
            'Normal': '获取法线',
            'ID': '获取稳定ID',
            'Index': '获取索引',
            'Scene Time': '场景时间（秒/帧）',
            'Random Value': '随机值',
            'Value/Vector/Color': '常数值',
            'Object Info': '获取对象信息',
            'Collection Info': '获取集合信息'
        },
        '几何操作': {
            'Transform': '变换几何',
            'Join Geometry': '合并几何',
            'Separate Geometry': '分离几何',
            'Delete Geometry': '删除几何',
            'Merge by Distance': '按距离合并',
            'Set Position': '设置位置',
            'Set Material': '设置材质'
        },
        '曲线节点': {
            'Curve to Mesh': '曲线转网格',
            'Curve to Points': '曲线转点',
            'Resample Curve': '重采样曲线',
            'Subdivide Curve': '细分曲线',
            'Trim Curve': '修剪曲线',
            'Curve Circle': '创建圆形',
            'Curve Spiral': '创建螺旋'
        },
        '网格节点': {
            'Mesh Cube/Cylinder/Sphere': '创建基本图元',
            'Subdivide Mesh': '细分网格',
            'Subdivision Surface': '细分表面',
            'Triangulate': '三角化',
            'Extrude Mesh': '挤出',
            'Mesh to Points': '网格转点',
            'Mesh to Curve': '网格转曲线'
        },
        '实例化': {
            'Instance on Points': '在点上实例化',
            'Realize Instances': '实现实例',
            'Rotate/Scale/Translate Instances': '实例变换',
            'Instance Rotation/Scale': '获取实例属性'
        },
        '属性': {
            'Store Named Attribute': '存储命名属性',
            'Named Attribute': '读取命名属性',
            'Remove Attribute': '删除命名属性',
            'Capture Attribute': '捕获属性'
        },
        '数学': {
            'Math': '数学运算',
            'Vector Math': '向量运算',
            'Boolean Math': '布尔运算',
            'Map Range': '范围映射',
            'Color Ramp': '色阶'
        },
        '实用工具': {
            'Switch': '条件切换',
            'Boolean Math': '布尔逻辑',
            'Compare': '比较',
            'Float Curve': '浮点曲线',
            'String': '字符串操作'
        }
    }
```

### 附录B：常用节点组合模板

```python
class NodeCombinationTemplates:
    """常用节点组合模板"""
    
    TEMPLATES = {
        'noise_deformation': {
            'name': '噪波变形',
            'nodes': [
                'Position → Noise Texture → Vector Math (Scale) → Vector Math (Add with Position) → Set Position'
            ],
            'use_case': '表面扰动、有机变形',
            'parameters': ['Noise Scale', 'Deformation Strength']
        },
        'height_based_material': {
            'name': '基于高度的材质分配',
            'nodes': [
                'Position → Separate XYZ → Math (Compare) → Set Material (Multiple)'
            ],
            'use_case': '地形材质、垂直分层'
        },
        'random_scatter': {
            'name': '随机散布',
            'nodes': [
                'Mesh → Distribute Points on Faces → Random Value (Rotation/Scale) → Instance on Points'
            ],
            'use_case': '植被分布、碎片散布'
        },
        'curve_path_following': {
            'name': '曲线路径跟随',
            'nodes': [
                'Curve → Curve to Points → Instance on Points (with Rotation from Tangent)'
            ],
            'use_case': '路径动画、链条生成'
        },
        'boolean_cutout': {
            'name': '布尔切割',
            'nodes': [
                'Mesh → Mesh Boolean (with cutter object) → Delete Geometry'
            ],
            'use_case': '窗户洞口、镂空效果'
        },
        'array_pattern': {
            'name': '阵列图案',
            'nodes': [
                'Mesh Line → Instance on Points → Join Geometry'
            ],
            'use_case': '重复元素、装饰图案'
        },
        'time_based_wave': {
            'name': '时间波浪',
            'nodes': [
                'Scene Time → Math (Multiply Speed) → Math (Add with Position.x) → Math (Sin) → Math (Multiply Height) → Set Position Z'
            ],
            'use_case': '波浪动画、脉动效果'
        },
        'proximity_based_effect': {
            'name': '基于接近的效果',
            'nodes': [
                'Geometry Proximity → Math (Map Range) → Set Material / Set Position / Instance Scale'
            ],
            'use_case': '交互效果、影响区域'
        }
    }
```

### 附录C：程序化建模参数表

```python
class ProceduralModelingParameters:
    """程序化建模参数表"""
    
    NOISE_TYPE_COMPARISON = {
        'FBM': {
            'description': '分形布朗运动',
            'characteristics': ['平滑', '自然', '适合地形'],
            'amplitude_decay': True,
            'use_case': '地形、云、有机纹理'
        },
        'Ridged': {
            'description': '脊状噪声',
            'characteristics': ['锐利', '脊线', '山脊感'],
            'use_case': '山脉、岩石'
        },
        'Multifractal': {
            'description': '多重分形',
            'characteristics': ['复杂', '多变', '细节丰富'],
            'use_case': '复杂地形、火星表面'
        },
        'Hetero_Terrain': {
            'description': '异质地形',
            'characteristics': ['层次感', '区域差异'],
            'use_case': '混合地形类型'
        }
    }
    
    SUBDIVISION_METHODS = {
        'simple': {
            'node': 'Subdivide Mesh',
            'description': '简单细分（不光滑）',
            'use_case': '增加顶点密度'
        },
        'catmull_clark': {
            'node': 'Subdivision Surface',
            'description': 'Catmull-Clark细分（光滑）',
            'use_case': '平滑建模、有机形状'
        },
        'loop': {
            'method': 'Loop细分（仅四边形）',
            'use_case': '高质量网格平滑'
        }
    }
    
    DISTRIBUTION_METHODS = {
        'random': {
            'method': 'RANDOM',
            'characteristics': ['完全随机', '可能聚集'],
            'use_case': '自然分布（草、石）'
        },
        'poisson': {
            'method': 'POISSON（4.2+）',
            'characteristics': ['泊松盘采样', '最小距离保证'],
            'use_case': '均匀分布（树木、建筑）'
        },
        'grid': {
            'method': 'GRID',
            'characteristics': ['网格排列', '可调间距'],
            'use_case': '规则阵列（窗户、地砖）'
        }
    }
```

### 附录D：性能基准测试数据

```python
class PerformanceBenchmarks:
    """性能基准测试数据"""
    
    BENCHMARK_RESULTS = {
        'instance_performance': {
            'description': '实例化性能对比',
            'test_scenario': '10000个立方体',
            'results': {
                'realize_instances': {
                    'memory': '~2GB',
                    'fps': '5-10',
                    'render_time': '慢'
                },
                'instances_only': {
                    'memory': '~100MB',
                    'fps': '60+',
                    'render_time': '快'
                }
            },
            'conclusion': '使用实例化可减少95%内存，提升6-10倍性能'
        },
        'subdivision_performance': {
            'description': '细分性能对比',
            'test_scenario': '100x100平面网格',
            'results': {
                'level_0': {'vertices': 10201, 'fps': 60, 'memory': '10MB'},
                'level_1': {'vertices': 40401, 'fps': 55, 'memory': '40MB'},
                'level_2': {'vertices': 160801, 'fps': 40, 'memory': '160MB'},
                'level_3': {'vertices': 641601, 'fps': 20, 'memory': '640MB'},
                'level_4': {'vertices': 2563201, 'fps': 5, 'memory': '2.5GB'}
            },
            'conclusion': '细分级别每增加1，顶点数增加4倍'
        },
        'field_evaluation': {
            'description': '字段求值性能',
            'test_scenario': '在100000顶点上应用噪声',
            'results': {
                'simple_noise': {'time': '50ms', 'fps': 60},
                'layered_noise': {'time': '200ms', 'fps': 30},
                'complex_field_chain': {'time': '500ms', 'fps': 15}
            },
            'conclusion': '复杂字段链可显著影响性能，使用Capture Attribute优化'
        },
        'simulation_performance': {
            'description': '模拟区域性能',
            'test_scenario': '1000粒子系统',
            'results': {
                'simple_motion': {'fps': 60, 'memory': '50MB'},
                'with_collision': {'fps': 30, 'memory': '100MB'},
                'complex_forces': {'fps': 15, 'memory': '200MB'}
            },
            'conclusion': '模拟区域性能受粒子数和力场复杂度影响'
        },
        'recommended_limits': {
            'description': '推荐性能限制',
            'values': {
                'instances': {'recommended': 100000, 'maximum': 1000000},
                'vertices_per_object': {'recommended': 1000000, 'maximum': 10000000},
                'subdivision_level': {'recommended': 3, 'maximum': 5},
                'particles': {'recommended': 10000, 'maximum': 100000},
                'node_count': {'recommended': 200, 'maximum': 500}
            }
        }
    }
```

---

## 总结

本指南系统覆盖了Blender几何节点与程序化建模的完整技术栈：

| 章节 | 核心内容 | 适用场景 |
|------|---------|---------|
| 一、系统概述 | 架构原理、数据流、字段系统、属性系统 | 理解核心概念 |
| 二、核心节点 | 输入、几何操作、曲线、网格、实例化 | 节点选择参考 |
| 三、程序化建模 | 建筑、地形、道路、城市 | 大规模场景生成 |
| 四、动画与模拟 | 时间动画、粒子、布料 | 动态内容生成 |
| 五、材质与渲染 | 材质分配、UV、纹理 | 视觉表现 |
| 六、性能优化 | 节点图优化、视口性能 | 大规模生产 |
| 七、AE集成 | 模型导出、动画同步、多通道合成 | 3D合成工作流 |

**关键技术要点**：
1. **字段系统**是几何节点的核心，理解字段与值的区别至关重要
2. **属性系统**通过命名属性实现跨节点数据传递
3. **实例化**是性能优化的关键，应尽量避免不必要的Realize Instances
4. **Simulation Zone**（4.0+）支持状态保持的模拟系统
5. **程序化建模**通过节点组合实现参数化、可调整的建模流程
6. **与AE集成**主要通过EXR多通道渲染和JSON数据交换实现

**最佳实践建议**：
- 在节点图中使用`Capture Attribute`缓存复杂字段计算结果
- 使用`Is Viewport`节点差异化处理视口与渲染，提升交互性能
- 对重复几何使用实例化，避免内存爆炸
- 为节点组设计清晰的输入输出接口，提高复用性
- 在与AE集成时，使用EXR多层渲染+JSON相机数据的组合方案
- 程序化建模时，从简单到复杂逐步迭代，每步验证结果

> **集成建议**：几何节点生成的复杂程序化模型在与AE集成时，推荐工作流为：1）在Blender中完成所有程序化建模与动画；2）使用EXR多层渲染输出高质量序列；3）在AE中通过Cryptomatte和深度通道进行精确合成；4）对于需要同步的相机/对象动画，使用JSON导出方案。这样可以最大化保留3D信息，同时保持后期合成的灵活性。
