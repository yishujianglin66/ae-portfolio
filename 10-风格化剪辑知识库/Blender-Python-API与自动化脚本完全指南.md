# Blender Python API与自动化脚本完全指南

> 适用版本：Blender 4.2 LTS / 4.3+ | 更新日期：2026-07-14 | 分类：3D自动化知识库

---

## 目录

- [一、Blender Python API架构](#一blender-python-api架构)
- [二、对象与场景操作](#二对象与场景操作)
- [三、材质与纹理API](#三材质与纹理api)
- [四、动画系统API](#四动画系统api)
- [五、渲染与输出API](#五渲染与输出api)
- [六、插件开发](#六插件开发)
- [七、与AE集成工作流](#七与ae集成工作流)
- [八、性能优化](#八性能优化)
- [附录](#附录)

---

## 一、Blender Python API架构

### 1.1 bpy模块核心架构

Blender Python API（bpy）是Blender内置的脚本接口，提供对全部功能模块的程序化访问能力。整个API基于RNA（Reference Named Attributes）系统构建，采用严格的属性描述与上下文隔离模型。

```python
class BpyArchitecture:
    VERSION = "4.2 LTS"
    
    CORE_MODULES = {
        'bpy.data': {
            'description': '数据访问层（直接访问所有Blend文件数据）',
            'persistence': True,
            'thread_safe': False,
            'access_pattern': 'bpy.data.objects / bpy.data.meshes / bpy.data.materials'
        },
        'bpy.context': {
            'description': '上下文层（当前活动场景、视图、模式）',
            'persistence': False,
            'thread_safe': False,
            'access_pattern': 'bpy.context.scene / bpy.context.object / bpy.context.area'
        },
        'bpy.ops': {
            'description': '操作层（用户操作的脚本封装）',
            'persistence': False,
            'thread_safe': False,
            'access_pattern': 'bpy.ops.object.add() / bpy.ops.mesh.primitive_cube_add()'
        },
        'bpy.types': {
            'description': '类型系统（注册自定义类型）',
            'persistence': True,
            'thread_safe': True,
            'access_pattern': 'bpy.types.Operator / bpy.types.Panel / bpy.types.PropertyGroup'
        },
        'bpy.props': {
            'description': '属性系统（定义自定义属性）',
            'persistence': True,
            'thread_safe': True,
            'access_pattern': 'bpy.props.StringProperty / bpy.props.FloatProperty'
        },
        'bpy.app': {
            'description': '应用层（Blender应用信息）',
            'persistence': True,
            'thread_safe': True,
            'access_pattern': 'bpy.app.version / bpy.app.binary_path'
        },
        'bpy.path': {
            'description': '路径工具（跨平台路径处理）',
            'persistence': True,
            'thread_safe': True,
            'access_pattern': 'bpy.path.abspath / bpy.path.relpath'
        },
        'bpy.utils': {
            'description': '工具函数（注册、预览、资源）',
            'persistence': True,
            'thread_safe': True,
            'access_pattern': 'bpy.utils.register_class / bpy.utils.previews'
        },
        'mathutils': {
            'description': '数学工具（向量、矩阵、欧拉）',
            'persistence': True,
            'thread_safe': True,
            'access_pattern': 'mathutils.Vector / mathutils.Matrix / mathutils.Euler'
        }
    }
    
    def __init__(self):
        self.active_context = None
        self.data_cache = {}
        
    def access_data(self, data_type, name=None):
        """访问bpy.data数据的标准入口"""
        valid_types = ['objects', 'meshes', 'materials', 'cameras', 'lamps',
                      'curves', 'texts', 'images', 'actions', 'armatures', 'scenes']
        if data_type not in valid_types:
            return {'status': 'error', 'message': f'无效数据类型: {data_type}'}
        
        collection = getattr(bpy.data, data_type)
        if name is None:
            return {'status': 'success', 'data': collection}
        item = collection.get(name)
        if item is None:
            return {'status': 'error', 'message': f'未找到: {name}'}
        return {'status': 'success', 'data': item}
```

### 1.2 数据访问模型

Blender的数据访问模型分为三层：`bpy.data`提供持久化数据集合访问，`bpy.context`提供当前活动状态访问，`bpy.ops`提供操作员级别的用户动作封装。

```python
class DataAccessModel:
    """三层访问模型的原子级规范"""
    
    DATA_ACCESS_LAYERS = {
        'persistent_data': {
            'module': 'bpy.data',
            'characteristics': ['持久化存储', '跨场景共享', '可批量遍历'],
            'use_case': '查询所有对象、按名称查找、批量修改',
            'example': "bpy.data.objects['Cube'].location = (0, 0, 1)",
            'thread_safety': '主线程独占'
        },
        'context_state': {
            'module': 'bpy.context',
            'characteristics': ['即时状态', '依赖活动视图', '可空指针风险'],
            'use_case': '获取活动对象、当前选中、当前模式',
            'example': "obj = bpy.context.active_object",
            'thread_safety': '主线程独占'
        },
        'operator_calls': {
            'module': 'bpy.ops',
            'characteristics': ['用户操作封装', '依赖活动上下文', '可能弹出对话框'],
            'use_case': '调用工具、执行命令、模拟用户操作',
            'example': "bpy.ops.object.select_all(action='SELECT')",
            'thread_safety': '主线程独占'
        }
    }
    
    CONTEXT_ATTRIBUTES = {
        'scene': {'type': 'bpy.types.Scene', 'description': '当前场景'},
        'object': {'type': 'bpy.types.Object', 'description': '活动对象（已弃用，使用active_object）'},
        'active_object': {'type': 'bpy.types.Object', 'description': '活动对象'},
        'selected_objects': {'type': 'list', 'description': '选中对象列表'},
        'view_layer': {'type': 'bpy.types.ViewLayer', 'description': '活动视图层'},
        'mode': {'type': 'str', 'description': '当前模式（OBJECT/EDIT/SCULPT等）'},
        'area': {'type': 'bpy.types.Area', 'description': '活动区域'},
        'region': {'type': 'bpy.types.Region', 'description': '活动区域中的子区域'},
        'window': {'type': 'bpy.types.Window', 'description': '活动窗口'},
        'workspace': {'type': 'bpy.types.WorkSpace', 'description': '活动工作区'},
        'tool_settings': {'type': 'bpy.types.ToolSettings', 'description': '工具设置'}
    }
    
    @staticmethod
    def safe_context_access(attr_name):
        """安全的上下文访问模式"""
        if not hasattr(bpy.context, attr_name):
            return {'status': 'error', 'message': f'上下文无此属性: {attr_name}'}
        value = getattr(bpy.context, attr_name)
        if value is None:
            return {'status': 'warning', 'message': f'{attr_name} 为 None'}
        return {'status': 'success', 'value': value}
```

### 1.3 属性系统与RNA系统

RNA（Reference Named Attributes）是Blender属性系统的底层框架，所有属性都通过RNA描述符进行类型检查和访问控制。

```python
class RNAPropertySystem:
    """RNA属性系统的原子级规范"""
    
    PROPERTY_TYPES = {
        'BoolProperty': {
            'python_type': bool,
            'default': False,
            'keywords': ['name', 'description', 'default', 'options', 'tags'],
            'use_case': '布尔开关、可见性控制'
        },
        'BoolVectorProperty': {
            'python_type': 'bpy.props.BoolVectorProperty',
            'default': (False, False, False),
            'keywords': ['name', 'description', 'default', 'size', 'subtype'],
            'use_case': '多轴开关、可见性位掩码'
        },
        'IntProperty': {
            'python_type': int,
            'default': 0,
            'keywords': ['name', 'description', 'default', 'min', 'max', 'soft_min', 'soft_max', 'step'],
            'use_case': '整数计数、索引值'
        },
        'IntVectorProperty': {
            'python_type': 'bpy.props.IntVectorProperty',
            'default': (0, 0, 0),
            'keywords': ['name', 'description', 'default', 'size', 'min', 'max'],
            'use_case': '坐标整数、分辨率'
        },
        'FloatProperty': {
            'python_type': float,
            'default': 0.0,
            'keywords': ['name', 'description', 'default', 'min', 'max', 'soft_min', 'soft_max', 'step', 'precision', 'subtype', 'unit'],
            'subtypes': ['NONE', 'FACTOR', 'ANGLE', 'TIME', 'DISTANCE', 'POWER', 'TEMPERATURE'],
            'use_case': '浮点数值、距离、角度'
        },
        'FloatVectorProperty': {
            'python_type': 'bpy.props.FloatVectorProperty',
            'default': (0.0, 0.0, 0.0),
            'keywords': ['name', 'description', 'default', 'size', 'min', 'max', 'subtype', 'unit'],
            'use_case': '颜色、位置、缩放向量'
        },
        'StringProperty': {
            'python_type': str,
            'default': '',
            'keywords': ['name', 'description', 'default', 'maxlen', 'options', 'subtype'],
            'use_case': '名称、路径、文本输入'
        },
        'EnumProperty': {
            'python_type': 'bpy.props.EnumProperty',
            'default': None,
            'keywords': ['name', 'description', 'items', 'default', 'options'],
            'use_case': '下拉选择、模式切换'
        },
        'PointerProperty': {
            'python_type': 'bpy.props.PointerProperty',
            'default': None,
            'keywords': ['name', 'description', 'type'],
            'use_case': '引用其他数据块、嵌套PropertyGroup'
        },
        'CollectionProperty': {
            'python_type': 'bpy.props.CollectionProperty',
            'default': None,
            'keywords': ['name', 'description', 'type'],
            'use_case': '列表数据、可变长度集合'
        }
    }
    
    @staticmethod
    def define_custom_property_example():
        """自定义属性定义示例"""
        return {
            'example_class': """
class MyPropertyGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name='名称', default='Item')
    enabled: bpy.props.BoolProperty(name='启用', default=True)
    count: bpy.props.IntProperty(name='数量', default=1, min=0, max=1000)
    scale: bpy.props.FloatProperty(name='缩放', default=1.0, min=0.001, soft_max=10.0)
    color: bpy.props.FloatVectorProperty(
        name='颜色',
        subtype='COLOR',
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0, max=1.0
    )
    mode: bpy.props.EnumProperty(
        name='模式',
        items=[
            ('FAST', '快速', '低质量快速渲染'),
            ('NORMAL', '常规', '平衡质量与速度'),
            ('HIGH', '高质量', '高质量慢速渲染')
        ],
        default='NORMAL'
    )

bpy.utils.register_class(MyPropertyGroup)
bpy.types.Scene.my_settings = bpy.props.PointerProperty(type=MyPropertyGroup)
"""
        }
```

### 1.4 上下文覆盖（Context Override）机制

上下文覆盖是Blender 2.8+引入的关键机制，用于在不依赖活动UI区域的情况下调用`bpy.ops`操作符。

```python
class ContextOverrideSystem:
    """上下文覆盖机制原子级规范"""
    
    OVERRIDE_KEYS = {
        'scene': {'type': 'bpy.types.Scene', 'description': '指定操作发生的场景'},
        'view_layer': {'type': 'bpy.types.ViewLayer', 'description': '指定视图层'},
        'window': {'type': 'bpy.types.Window', 'description': '指定窗口'},
        'area': {'type': 'bpy.types.Area', 'description': '指定区域（影响操作类型可用性）'},
        'region': {'type': 'bpy.types.Region', 'description': '指定子区域'},
        'object': {'type': 'bpy.types.Object', 'description': '活动对象'},
        'selected_objects': {'type': 'list', 'description': '选中对象列表'},
        'selected_editable_objects': {'type': 'list', 'description': '可编辑选中对象'},
        'active_object': {'type': 'bpy.types.Object', 'description': '活动对象'},
        'edit_object': {'type': 'bpy.types.Object', 'description': '编辑模式对象'},
        'mode': {'type': 'str', 'description': '当前模式'}
    }
    
    @staticmethod
    def legacy_override_pattern(area_type='VIEW_3D'):
        """2.8-3.x 旧式上下文覆盖（已弃用）"""
        return f"""
# 旧式覆盖（不推荐，4.0+已移除）
override = bpy.context.copy()
override['area'] = find_area_by_type('{area_type}')
with bpy.context.temp_override(**override):
    bpy.ops.object.select_all(action='SELECT')
"""
    
    @staticmethod
    def modern_override_pattern(area_type='VIEW_3D'):
        """3.0+ 新式上下文覆盖"""
        return f"""
# 新式覆盖（推荐）
import bpy

def find_area_by_type(area_type):
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == area_type:
                return area
    return None

area = find_area_by_type('{area_type}')
with bpy.context.temp_override(area=area):
    bpy.ops.object.select_all(action='SELECT')
"""
    
    @staticmethod
    def temp_override_full_example():
        """完整的临时覆盖示例"""
        return """
import bpy

def execute_in_view3d(operator_callable, *args, **kwargs):
    \"\"\"在3D视图上下文中执行操作符\"\"\"
    window = bpy.context.window
    screen = window.screen
    
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'WINDOW':
                    with bpy.context.temp_override(
                        window=window,
                        area=area,
                        region=region,
                        screen=screen
                    ):
                        return operator_callable(*args, **kwargs)
    raise RuntimeError('未找到3D视图区域')

# 调用示例
execute_in_view3d(bpy.ops.object.select_all, action='INVERT')
"""
```

---

## 二、对象与场景操作

### 2.1 场景管理

场景是Blender中组织内容的顶层容器，每个场景拥有独立的渲染设置、帧范围、活动层和对象集合。

```python
class SceneManagerAPI:
    """场景管理API原子级规范"""
    
    SCENE_PROPERTIES = {
        'render': {
            'resolution_x': {'type': 'int', 'default': 1920, 'description': '水平分辨率'},
            'resolution_y': {'type': 'int', 'default': 1080, 'description': '垂直分辨率'},
            'resolution_percentage': {'type': 'int', 'default': 100, 'range': [1, 100], 'description': '分辨率百分比'},
            'fps': {'type': 'int', 'default': 24, 'description': '帧率'},
            'fps_base': {'type': 'float', 'default': 1.0, 'description': '帧率基（NTSC用）'},
            'frame_start': {'type': 'int', 'default': 1, 'description': '起始帧'},
            'frame_end': {'type': 'int', 'default': 250, 'description': '结束帧'},
            'frame_step': {'type': 'int', 'default': 1, 'description': '帧步长'},
            'engine': {'type': 'str', 'default': 'CYCLES', 'options': ['CYCLES', 'BLENDER_EEVEE', 'BLENDER_WORKBENCH']},
            'film_transparent': {'type': 'bool', 'default': False, 'description': '透明背景'}
        },
        'view_settings': {
            'view_transform': {'type': 'str', 'default': 'Filmic', 'options': ['Standard', 'Filmic', 'Raw', 'False Color']},
            'look': {'type': 'str', 'default': 'None', 'options': ['None', 'Very High Contrast', 'High Contrast', 'Medium High Contrast', 'Medium Contrast', 'Medium Low Contrast', 'Low Contrast']},
            'exposure': {'type': 'float', 'default': 0.0, 'range': [-32, 32]},
            'gamma': {'type': 'float', 'default': 1.0, 'range': [0.0, 5.0]},
            'use_curve_mapping': {'type': 'bool', 'default': False}
        }
    }
    
    @staticmethod
    def create_scene(name):
        """创建新场景"""
        import bpy
        scene = bpy.data.scenes.new(name=name)
        return {'status': 'success', 'scene': scene.name}
    
    @staticmethod
    def delete_scene(name):
        """删除场景"""
        import bpy
        scene = bpy.data.scenes.get(name)
        if not scene:
            return {'status': 'error', 'message': f'场景不存在: {name}'}
        bpy.data.scenes.remove(scene)
        return {'status': 'success'}
    
    @staticmethod
    def configure_render_settings(scene_name, **kwargs):
        """配置渲染设置"""
        import bpy
        scene = bpy.data.scenes.get(scene_name)
        if not scene:
            return {'status': 'error', 'message': f'场景不存在: {scene_name}'}
        
        render = scene.render
        for key, value in kwargs.items():
            if hasattr(render, key):
                setattr(render, key, value)
            else:
                return {'status': 'error', 'message': f'无效渲染参数: {key}'}
        return {'status': 'success', 'scene': scene_name}
    
    @staticmethod
    def duplicate_scene(source_name, new_name, link_objects=True):
        """复制场景"""
        import bpy
        source = bpy.data.scenes.get(source_name)
        if not source:
            return {'status': 'error', 'message': '源场景不存在'}
        new_scene = source.copy()
        new_scene.name = new_name
        bpy.context.window_manager.windows[0].scene = new_scene
        return {'status': 'success', 'scene': new_name}
```

### 2.2 对象操作

```python
class ObjectManipulationAPI:
    """对象操作API原子级规范"""
    
    PRIMITIVE_TYPES = {
        'mesh': {
            'cube': 'bpy.ops.mesh.primitive_cube_add()',
            'uv_sphere': 'bpy.ops.mesh.primitive_uv_sphere_add()',
            'ico_sphere': 'bpy.ops.mesh.primitive_ico_sphere_add()',
            'cylinder': 'bpy.ops.mesh.primitive_cylinder_add()',
            'cone': 'bpy.ops.mesh.primitive_cone_add()',
            'torus': 'bpy.ops.mesh.primitive_torus_add()',
            'plane': 'bpy.ops.mesh.primitive_plane_add()',
            'circle': 'bpy.ops.mesh.primitive_circle_add()',
            'monkey': 'bpy.ops.mesh.primitive_monkey_add()'
        },
        'curve': {
            'bezier': 'bpy.ops.curve.primitive_bezier_curve_add()',
            'bezier_circle': 'bpy.ops.curve.primitive_bezier_circle_add()',
            'nurbs_curve': 'bpy.ops.curve.primitive_nurbs_curve_add()',
            'nurbs_circle': 'bpy.ops.curve.primitive_nurbs_circle_add()',
            'nurbs_path': 'bpy.ops.curve.primitive_nurbs_path_add()'
        },
        'surface': {
            'nurbs_surface': 'bpy.ops.surface.primitive_nurbs_surface_surface_add()',
            'nurbs_cylinder': 'bpy.ops.surface.primitive_nurbs_surface_cylinder_add()',
            'nurbs_sphere': 'bpy.ops.surface.primitive_nurbs_surface_sphere_add()',
            'nurbs_torus': 'bpy.ops.surface.primitive_nurbs_surface_torus_add()'
        },
        'text': {
            'text_data': 'bpy.ops.object.text_add()'
        },
        'metaball': {
            'meta_ball': 'bpy.ops.object.metaball_add()'
        }
    }
    
    TRANSFORM_PROPERTIES = {
        'location': {
            'type': 'mathutils.Vector',
            'default': (0.0, 0.0, 0.0),
            'description': '世界空间位置',
            'access': 'obj.location = (x, y, z)'
        },
        'rotation_euler': {
            'type': 'mathutils.Euler',
            'default': (0.0, 0.0, 0.0),
            'description': '欧拉旋转（XYZ）',
            'access': 'obj.rotation_euler = (rx, ry, rz)'
        },
        'rotation_quaternion': {
            'type': 'mathutils.Quaternion',
            'default': (1.0, 0.0, 0.0, 0.0),
            'description': '四元数旋转',
            'access': 'obj.rotation_quaternion = (w, x, y, z)'
        },
        'rotation_mode': {
            'type': 'str',
            'default': 'XYZ',
            'options': ['XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX', 'AXIS_ANGLE', 'QUATERNION'],
            'description': '旋转模式'
        },
        'scale': {
            'type': 'mathutils.Vector',
            'default': (1.0, 1.0, 1.0),
            'description': '局部空间缩放',
            'access': 'obj.scale = (sx, sy, sz)'
        },
        'dimensions': {
            'type': 'mathutils.Vector',
            'default': (0.0, 0.0, 0.0),
            'description': '包围盒尺寸（只读+赋值会重算scale）',
            'access': 'obj.dimensions = (dx, dy, dz)'
        },
        'matrix_world': {
            'type': 'mathutils.Matrix',
            'default': 'identity',
            'description': '世界变换矩阵（4x4）',
            'access': 'obj.matrix_world = Matrix.Translation((x,y,z))'
        },
        'matrix_local': {
            'type': 'mathutils.Matrix',
            'default': 'identity',
            'description': '局部变换矩阵（4x4）',
            'access': 'obj.matrix_local = ...'
        }
    }
    
    @staticmethod
    def create_primitive(primitive_type, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
        """创建基本图元的通用入口"""
        import bpy
        
        type_map = {
            'cube': bpy.ops.mesh.primitive_cube_add,
            'sphere': bpy.ops.mesh.primitive_uv_sphere_add,
            'cylinder': bpy.ops.mesh.primitive_cylinder_add,
            'cone': bpy.ops.mesh.primitive_cone_add,
            'torus': bpy.ops.mesh.primitive_torus_add,
            'plane': bpy.ops.mesh.primitive_plane_add,
            'monkey': bpy.ops.mesh.primitive_monkey_add
        }
        
        if primitive_type not in type_map:
            return {'status': 'error', 'message': f'无效类型: {primitive_type}'}
        
        type_map[primitive_type](location=location, rotation=rotation)
        obj = bpy.context.active_object
        obj.scale = scale
        return {'status': 'success', 'object': obj.name}
    
    @staticmethod
    def set_parent(child_name, parent_name, keep_transform=True):
        """设置父子关系"""
        import bpy
        
        child = bpy.data.objects.get(child_name)
        parent = bpy.data.objects.get(parent_name)
        
        if not child or not parent:
            return {'status': 'error', 'message': '对象不存在'}
        
        if keep_transform:
            child.matrix_parent_inverse = parent.matrix_world.inverted()
        
        child.parent = parent
        return {'status': 'success', 'child': child_name, 'parent': parent_name}
    
    @staticmethod
    def set_visibility(obj_name, hide_viewport=False, hide_render=False, hide_select=False):
        """设置对象可见性"""
        import bpy
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            return {'status': 'error', 'message': '对象不存在'}
        obj.hide_set(hide_viewport)
        obj.hide_render = hide_render
        obj.hide_select = hide_select
        return {'status': 'success'}
```

### 2.3 网格操作

```python
class MeshOperationAPI:
    """网格操作API原子级规范"""
    
    MESH_DATA_ACCESS = {
        'vertices': {
            'description': '顶点集合',
            'access': 'mesh.vertices',
            'count': 'len(mesh.vertices)',
            'position': 'v.co (mathutils.Vector)',
            'normal': 'v.normal (mathutils.Vector)',
            'selected': 'v.select (bool)'
        },
        'edges': {
            'description': '边集合',
            'access': 'mesh.edges',
            'count': 'len(mesh.edges)',
            'vertices': 'e.vertices (tuple of 2 vertex indices)',
            'crease': 'e.crease (float 0-1)',
            'use_edge_sharp': 'e.use_edge_sharp (bool)'
        },
        'polygons': {
            'description': '面集合',
            'access': 'mesh.polygons',
            'count': 'len(mesh.polygons)',
            'vertices': 'p.vertices (tuple of vertex indices)',
            'normal': 'p.normal (mathutils.Vector)',
            'area': 'p.area (float)',
            'material_index': 'p.material_index (int)',
            'use_smooth': 'p.use_smooth (bool)'
        },
        'loops': {
            'description': '循环边集合',
            'access': 'mesh.loops',
            'count': 'len(mesh.loops)',
            'vertex_index': 'l.vertex_index (int)',
            'edge_index': 'l.edge_index (int)',
            'normal': 'l.normal (mathutils.Vector)'
        }
    }
    
    @staticmethod
    def access_mesh_data_example():
        """网格数据访问示例"""
        return """
import bpy
import mathutils

obj = bpy.context.active_object
mesh = obj.data

# 访问顶点位置
for v in mesh.vertices:
    print(f'顶点 {v.index}: 位置 {v.co}, 法线 {v.normal}')

# 访问面的顶点索引
for p in mesh.polygons:
    print(f'面 {p.index}: 顶点 {p.vertices}, 面积 {p.area}')

# 修改顶点位置
mesh.vertices[0].co = mathutils.Vector((1.0, 2.0, 3.0))

# 更新网格
mesh.update()
"""
    
    @staticmethod
    def bmesh_operations_example():
        """BMesh底层网格操作示例"""
        return """
import bpy
import bmesh

# 创建BMesh
bm = bmesh.new()

# 方法1：从现有网格创建
mesh = bpy.context.active_object.data
bm.from_mesh(mesh)

# 方法2：在编辑模式中创建
# bm = bmesh.from_edit_mesh(mesh)

# 创建顶点
v1 = bm.verts.new((0, 0, 0))
v2 = bm.verts.new((1, 0, 0))
v3 = bm.verts.new((1, 1, 0))

# 创建边
e1 = bm.edges.new((v1, v2))
e2 = bm.edges.new((v2, v3))
e3 = bm.edges.new((v3, v1))

# 创建面
f1 = bm.faces.new((v1, v2, v3))

# 挤出
ret = bmesh.ops.extrude_face_region(bm, geom=[f1])
extruded_verts = [v for v in ret['geom'] if isinstance(v, bmesh.types.BMVert)]
bmesh.ops.translate(bm, vec=(0, 0, 1), verts=extruded_verts)

# 倒角
bmesh.ops.bevel(
    bm,
    geom=extruded_verts + [e for e in bm.edges if e.verts[0] in extruded_verts and e.verts[1] in extruded_verts],
    offset=0.1,
    segments=3,
    profile=0.5,
    affect='VERTICES'
)

# 写回网格
bm.to_mesh(mesh)
bm.free()
mesh.update()
"""
    
    @staticmethod
    def apply_modifier_example():
        """修改器应用示例"""
        return """
import bpy

obj = bpy.context.active_object

# 添加细分修改器
subsurf = obj.modifiers.new(name='Subsurf', type='SUBSURF')
subsurf.levels = 2
subsurf.render_levels = 3

# 添加镜像修改器
mirror = obj.modifiers.new(name='Mirror', type='MIRROR')
mirror.use_axis[0] = True  # X轴镜像
mirror.use_axis[1] = False
mirror.use_axis[2] = False

# 添加实体化修改器
solidify = obj.modifiers.new(name='Solidify', type='SOLIDIFY')
solidify.thickness = 0.1
solidify.offset = 0.0

# 应用修改器（注意上下文）
bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(modifier='Subsurf')
"""
```

---

## 三、材质与纹理API

### 3.1 节点式材质系统

```python
class NodeMaterialAPI:
    """节点式材质系统API原子级规范"""
    
    NODE_TREE_ACCESS = {
        'material_node_tree': {
            'access': 'material.node_tree',
            'type': 'bpy.types.ShaderNodeTree',
            'description': '材质节点树'
        },
        'nodes': {
            'access': 'material.node_tree.nodes',
            'type': 'bpy.types.bpy_prop_collection',
            'description': '节点集合'
        },
        'links': {
            'access': 'material.node_tree.links',
            'type': 'bpy.types.bpy_prop_collection',
            'description': '连接集合'
        }
    }
    
    NODE_TYPES = {
        'shader': {
            'ShaderNodeBsdfPrincipled': {'description': 'Principled BSDF', 'outputs': ['BSDF']},
            'ShaderNodeBsdfDiffuse': {'description': 'Diffuse BSDF', 'outputs': ['BSDF']},
            'ShaderNodeBsdfGlossy': {'description': 'Glossy BSDF', 'outputs': ['BSDF']},
            'ShaderNodeBsdfGlass': {'description': 'Glass BSDF', 'outputs': ['BSDF']},
            'ShaderNodeBsdfTranslucent': {'description': 'Translucent BSDF', 'outputs': ['BSDF']},
            'ShaderNodeBsdfTransparent': {'description': 'Transparent BSDF', 'outputs': ['BSDF']},
            'ShaderNodeBsdfVelvet': {'description': 'Velvet BSDF', 'outputs': ['BSDF']},
            'ShaderNodeEmission': {'description': 'Emission', 'outputs': ['Emission']},
            'ShaderNodeMixShader': {'description': 'Mix Shader', 'outputs': ['Shader']},
            'ShaderNodeAddShader': {'description': 'Add Shader', 'outputs': ['Shader']}
        },
        'texture': {
            'ShaderNodeTexNoise': {'description': '噪波纹理', 'outputs': ['Fac', 'Color']},
            'ShaderNodeTexVoronoi': {'description': '沃罗诺伊纹理', 'outputs': ['Distance', 'Color', 'Position']},
            'ShaderNodeTexMusgrave': {'description': '马斯格雷夫纹理（已弃用）', 'outputs': ['Fac']},
            'ShaderNodeTexGradient': {'description': '渐变纹理', 'outputs': ['Fac', 'Color']},
            'ShaderNodeTexWave': {'description': '波浪纹理', 'outputs': ['Fac', 'Color']},
            'ShaderNodeTexMagic': {'description': '魔幻纹理', 'outputs': ['Fac', 'Color']},
            'ShaderNodeTexChecker': {'description': '棋盘纹理', 'outputs': ['Fac', 'Color']},
            'ShaderNodeTexBrick': {'description': '砖块纹理', 'outputs': ['Fac', 'Color']},
            'ShaderNodeTexImage': {'description': '图像纹理', 'outputs': ['Color', 'Alpha']}
        },
        'input': {
            'ShaderNodeTexCoord': {'description': '纹理坐标', 'outputs': ['Generated', 'Object', 'UV', 'Normal', 'Camera', 'Window', 'Reflection']},
            'ShaderNodeValue': {'description': '值输入', 'outputs': ['Value']},
            'ShaderNodeRGB': {'description': '颜色输入', 'outputs': ['Color']},
            'ShaderNodeCameraData': {'description': '相机数据', 'outputs': ['View Vector', 'View Z Depth', 'View Distance']},
            'ShaderNodeNewGeometry': {'description': '几何数据', 'outputs': ['Position', 'Normal', 'Tangent', 'True Normal', 'Incoming', 'Parametric', 'Backfacing', 'Pointiness']},
            'ShaderNodeFresnel': {'description': '菲涅尔', 'outputs': ['Fac']},
            'ShaderNodeLayerWeight': {'description': '层权重', 'outputs': ['Fresnel', 'Facing']}
        },
        'output': {
            'ShaderNodeOutputMaterial': {'description': '材质输出', 'inputs': ['Surface', 'Volume', 'Displacement']},
            'ShaderNodeOutputWorld': {'description': '世界输出', 'inputs': ['Surface', 'Volume']},
            'ShaderNodeOutputLight': {'description': '灯光输出', 'inputs': ['Surface']}
        },
        'vector': {
            'ShaderNodeMapping': {'description': '映射', 'outputs': ['Vector']},
            'ShaderNodeVectorMath': {'description': '向量数学', 'outputs': ['Vector', 'Value']},
            'ShaderNodeBump': {'description': '凹凸', 'outputs': ['Normal']},
            'ShaderNodeNormalMap': {'description': '法线贴图', 'outputs': ['Normal']},
            'ShaderNodeDisplacement': {'description': '置换', 'outputs': ['Height']}
        },
        'converter': {
            'ShaderNodeMath': {'description': '数学运算', 'outputs': ['Value']},
            'ShaderNodeColorRamp': {'description': '色阶', 'outputs': ['Color', 'Alpha']},
            'ShaderNodeMixRGB': {'description': '颜色混合（已弃用，使用Mix Color）', 'outputs': ['Color']},
            'ShaderNodeMix': {'description': '混合（4.0+通用）', 'outputs': ['Result']},
            'ShaderNodeSeparateRGB': {'description': 'RGB分离（已弃用，使用Separate Color）', 'outputs': ['R', 'G', 'B']},
            'ShaderNodeCombineRGB': {'description': 'RGB合并（已弃用）', 'outputs': ['Image']},
            'ShaderNodeSeparateColor': {'description': '颜色分离', 'outputs': ['Red', 'Green', 'Blue', 'Alpha']},
            'ShaderNodeCombineColor': {'description': '颜色合并', 'outputs': ['Color', 'Alpha']}
        }
    }
    
    @staticmethod
    def create_material_with_nodes(name='NewMaterial'):
        """创建带节点树的材质"""
        import bpy
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        return mat
    
    @staticmethod
    def create_principled_material(name='PBR', base_color=(0.8, 0.8, 0.8, 1.0),
                                    metallic=0.0, roughness=0.5, emission_strength=0.0):
        """创建标准PBR材质"""
        import bpy
        
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        # 清除默认节点
        nodes.clear()
        
        # 创建输出节点
        output = nodes.new('ShaderNodeOutputMaterial')
        output.location = (300, 0)
        
        # 创建Principled BSDF
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (0, 0)
        bsdf.inputs['Base Color'].default_value = base_color
        bsdf.inputs['Metallic'].default_value = metallic
        bsdf.inputs['Roughness'].default_value = roughness
        if emission_strength > 0:
            bsdf.inputs['Emission Color'].default_value = base_color
            bsdf.inputs['Emission Strength'].default_value = emission_strength
        
        # 连接
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        
        return mat
    
    @staticmethod
    def connect_nodes(material, from_node_name, from_socket, to_node_name, to_socket):
        """连接两个节点"""
        import bpy
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        
        from_node = nodes.get(from_node_name)
        to_node = nodes.get(to_node_name)
        
        if not from_node or not to_node:
            return {'status': 'error', 'message': '节点不存在'}
        
        from_out = from_node.outputs.get(from_socket)
        to_in = to_node.inputs.get(to_socket)
        
        if not from_out or not to_in:
            return {'status': 'error', 'message': 'socket不存在'}
        
        links.new(from_out, to_in)
        return {'status': 'success'}
    
    @staticmethod
    def create_node_group_example():
        """创建节点组示例"""
        return """
import bpy

def create_noise_group(name='NoiseGroup'):
    group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    
    # 创建输入输出
    group_input = group.nodes.new('NodeGroupInput')
    group_input.location = (-400, 0)
    
    group_output = group.nodes.new('NodeGroupOutput')
    group_output.location = (400, 0)
    
    # 创建接口
    group.inputs.new('NodeSocketFloat', 'Scale')
    group.inputs[0].default_value = 5.0
    
    group.inputs.new('NodeSocketFloat', 'Detail')
    group.inputs[1].default_value = 2.0
    
    group.outputs.new('NodeSocketFloat', 'Fac')
    
    # 创建噪波节点
    noise = group.nodes.new('ShaderNodeTexNoise')
    noise.location = (0, 0)
    
    # 连接
    group.links.new(group_input.outputs['Scale'], noise.inputs['Scale'])
    group.links.new(group_input.outputs['Detail'], noise.inputs['Detail'])
    group.links.new(noise.outputs['Fac'], group_output.inputs['Fac'])
    
    return group

# 使用节点组
mat = bpy.data.materials.new('TestMat')
mat.use_nodes = True
group_node = mat.node_tree.nodes.new('ShaderNodeGroup')
group_node.node_tree = create_noise_group()
"""
```

### 3.2 程序化纹理

```python
class ProceduralTextureAPI:
    """程序化纹理API原子级规范"""
    
    NOISE_PARAMETERS = {
        'scale': {'type': 'float', 'default': 5.0, 'range': [0.0, 1000.0], 'description': '缩放'},
        'detail': {'type': 'float', 'default': 2.0, 'range': [0.0, 16.0], 'description': '细节等级'},
        'roughness': {'type': 'float', 'default': 0.5, 'range': [0.0, 1.0], 'description': '粗糙度'},
        'dimension': {'type': 'enum', 'default': '2D', 'options': ['1D', '2D', '3D', '4D'], 'description': '维度'},
        'noise_type': {'type': 'enum', 'default': 'MULTIFRACTAL', 
                      'options': ['MULTIFRACTAL', 'RIDGED_MULTIFRACTAL', 'HYBRID_MULTIFRACTAL', 'FBM', 'HETERO_TERRAIN'],
                      'description': '4.1+才支持'}
    }
    
    VORONOI_PARAMETERS = {
        'scale': {'type': 'float', 'default': 5.0, 'range': [0.0, 1000.0]},
        'distance': {'type': 'enum', 'default': 'EUCLIDEAN',
                    'options': ['EUCLIDEAN', 'MANHATTAN', 'CHEBYCHEV', 'MINKOWSKI'],
                    'description': '距离度量'},
        'feature': {'type': 'enum', 'default': 'F1',
                   'options': ['F1', 'F2', 'SMOOTH_F1', 'F2_F1', 'DISTANCE'],
                   'description': '特征输出'},
        'minkowski_exponent': {'type': 'float', 'default': 2.5, 'range': [0.0, 10.0]},
        'dimension': {'type': 'enum', 'default': '2D', 'options': ['1D', '2D', '3D', '4D']}
    }
    
    GRADIENT_PARAMETERS = {
        'gradient_type': {'type': 'enum', 'default': 'LINEAR',
                         'options': ['LINEAR', 'QUADRATIC', 'EASING', 'DIAGONAL', 'SPHERICAL', 'QUADRATIC_SPHERE', 'RADIAL'],
                         'description': '渐变类型'}
    }
    
    WAVE_PARAMETERS = {
        'wave_type': {'type': 'enum', 'default': 'BANDS',
                     'options': ['BANDS', 'RINGS'],
                     'description': '波形类型'},
        'bands_direction': {'type': 'enum', 'default': 'X', 'options': ['X', 'Y', 'Z', 'DIAGONAL']},
        'rings_direction': {'type': 'enum', 'default': 'X', 'options': ['X', 'Y', 'Z', 'SPHERICAL']},
        'wave_profile': {'type': 'enum', 'default': 'SIN', 'options': ['SIN', 'SAW', 'TRI']},
        'scale': {'type': 'float', 'default': 5.0},
        'distortion': {'type': 'float', 'default': 0.0, 'range': [0.0, 1000.0]},
        'detail': {'type': 'float', 'default': 2.0, 'range': [0.0, 16.0]},
        'detail_scale': {'type': 'float', 'default': 1.0, 'range': [0.0, 1000.0]}
    }
    
    @staticmethod
    def create_procedural_texture_network():
        """创建程序化纹理网络示例"""
        return """
import bpy

mat = bpy.data.materials.new('ProcMat')
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

# 输出
output = nodes.new('ShaderNodeOutputMaterial')
output.location = (400, 0)

# Principled BSDF
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
bsdf.location = (200, 0)

# 纹理坐标
tex_coord = nodes.new('ShaderNodeTexCoord')
tex_coord.location = (-800, 0)

# 映射
mapping = nodes.new('ShaderNodeMapping')
mapping.location = (-600, 0)
mapping.inputs['Scale'].default_value = (2.0, 2.0, 2.0)

# 噪波纹理（用作颜色变化）
noise = nodes.new('ShaderNodeTexNoise')
noise.location = (-400, 100)
noise.inputs['Scale'].default_value = 8.0
noise.inputs['Detail'].default_value = 4.0

# 色阶（调整噪波范围）
ramp = nodes.new('ShaderNodeColorRamp')
ramp.location = (-200, 100)
ramp.color_ramp.elements[0].position = 0.2
ramp.color_ramp.elements[0].color = (0.1, 0.05, 0.02, 1.0)
ramp.color_ramp.elements[1].position = 0.8
ramp.color_ramp.elements[1].color = (0.9, 0.7, 0.4, 1.0)

# 沃罗诺伊纹理（用作粗糙度变化）
voronoi = nodes.new('ShaderNodeTexVoronoi')
voronoi.location = (-400, -100)
voronoi.inputs['Scale'].default_value = 12.0

# 连接
links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
links.new(mapping.outputs['Vector'], voronoi.inputs['Vector'])
links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
links.new(voronoi.outputs['Distance'], bsdf.inputs['Roughness'])
links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
"""
```

### 3.3 PBR材质自动化

```python
class PBRMaterialAutomation:
    """PBR材质自动化批量处理API"""
    
    PBR_TEXTURE_SLOTS = {
        'base_color': {'suffix': ['_BaseColor', '_Albedo', '_Color', '_Diffuse', '_basecolor'],
                      'node_input': 'Base Color', 'color_space': 'sRGB'},
        'metallic': {'suffix': ['_Metallic', '_Metal', '_metallic'],
                    'node_input': 'Metallic', 'color_space': 'Non-Color'},
        'roughness': {'suffix': ['_Roughness', '_Rough', '_roughness'],
                     'node_input': 'Roughness', 'color_space': 'Non-Color'},
        'normal': {'suffix': ['_Normal', '_NRM', '_normal'],
                  'node_input': 'Normal', 'color_space': 'Non-Color', 'needs_normal_map': True},
        'height': {'suffix': ['_Height', '_Displacement', '_height'],
                  'node_input': 'Displacement', 'color_space': 'Non-Color'},
        'emission': {'suffix': ['_Emission', '_Emissive', '_emission'],
                    'node_input': 'Emission Color', 'color_space': 'sRGB'},
        'ao': {'suffix': ['_AO', '_AmbientOcclusion', '_ao'],
              'node_input': None, 'color_space': 'Non-Color', 'multiply_base_color': True},
        'opacity': {'suffix': ['_Opacity', '_Alpha', '_opacity'],
                   'node_input': 'Alpha', 'color_space': 'Non-Color'}
    }
    
    @staticmethod
    def create_pbr_from_textures(material_name, texture_dir, base_filename):
        """从纹理文件自动创建PBR材质"""
        import bpy
        import os
        
        mat = bpy.data.materials.new(material_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        
        # 创建输出和BSDF
        output = nodes.new('ShaderNodeOutputMaterial')
        output.location = (600, 0)
        
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (300, 0)
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        
        # 加载各通道纹理
        loaded_textures = {}
        for slot_name, slot_info in PBRMaterialAutomation.PBR_TEXTURE_SLOTS.items():
            for suffix in slot_info['suffix']:
                texture_path = os.path.join(texture_dir, f'{base_filename}{suffix}.png')
                if os.path.exists(texture_path):
                    img = bpy.data.images.load(texture_path)
                    img.colorspace_settings.name = slot_info['color_space']
                    
                    tex_node = nodes.new('ShaderNodeTexImage')
                    tex_node.image = img
                    tex_node.location = (0, -200 + len(loaded_textures) * -300)
                    loaded_textures[slot_name] = tex_node
                    break
        
        # 连接到BSDF
        if 'base_color' in loaded_textures:
            links.new(loaded_textures['base_color'].outputs['Color'],
                     bsdf.inputs['Base Color'])
        if 'metallic' in loaded_textures:
            links.new(loaded_textures['metallic'].outputs['Color'],
                     bsdf.inputs['Metallic'])
        if 'roughness' in loaded_textures:
            links.new(loaded_textures['roughness'].outputs['Color'],
                     bsdf.inputs['Roughness'])
        if 'emission' in loaded_textures:
            links.new(loaded_textures['emission'].outputs['Color'],
                     bsdf.inputs['Emission Color'])
            bsdf.inputs['Emission Strength'].default_value = 1.0
        if 'normal' in loaded_textures:
            normal_map = nodes.new('ShaderNodeNormalMap')
            normal_map.location = (150, -400)
            links.new(loaded_textures['normal'].outputs['Color'],
                     normal_map.inputs['Color'])
            links.new(normal_map.outputs['Normal'],
                     bsdf.inputs['Normal'])
        if 'opacity' in loaded_textures:
            links.new(loaded_textures['opacity'].outputs['Color'],
                     bsdf.inputs['Alpha'])
            mat.blend_method = 'BLEND'
        
        return mat
```

---

## 四、动画系统API

### 4.1 关键帧动画

```python
class KeyframeAnimationAPI:
    """关键帧动画API原子级规范"""
    
    INTERPOLATION_MODES = {
        'CONSTANT': {'description': '常量插值（突变）', 'curve': '阶梯'},
        'LINEAR': {'description': '线性插值', 'curve': '直线'},
        'BEZIER': {'description': '贝塞尔插值（默认）', 'curve': '平滑曲线'},
        'SINE': {'description': '正弦缓动', 'curve': '正弦'},
        'QUAD': {'description': '二次缓动', 'curve': '抛物线'},
        'CUBIC': {'description': '三次缓动', 'curve': '三次曲线'},
        'QUART': {'description': '四次缓动', 'curve': '四次曲线'},
        'QUINT': {'description': '五次缓动', 'curve': '五次曲线'},
        'EXPO': {'description': '指数缓动', 'curve': '指数曲线'},
        'CIRC': {'description': '圆形缓动', 'curve': '圆弧'},
        'BACK': {'description': '回退缓动', 'curve': '过冲回退'},
        'BOUNCE': {'description': '弹跳缓动', 'curve': '弹跳曲线'},
        'ELASTIC': {'description': '弹性缓动', 'curve': '弹性震荡'}
    }
    
    EASING_MODES = {
        'AUTO': {'description': '自动（默认）'},
        'EASE_IN': {'description': '缓入'},
        'EASE_OUT': {'description': '缓出'},
        'EASE_IN_OUT': {'description': '缓入缓出'}
    }
    
    @staticmethod
    def insert_keyframe_simple(obj_name, data_path, frame, value=None):
        """插入简单关键帧"""
        import bpy
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            return {'status': 'error', 'message': '对象不存在'}
        
        if value is not None:
            exec(f'obj.{data_path} = {value}')
        
        obj.keyframe_insert(data_path=data_path, frame=frame)
        return {'status': 'success'}
    
    @staticmethod
    def insert_keyframe_full_example():
        """完整关键帧插入示例"""
        return """
import bpy

obj = bpy.context.active_object
scene = bpy.context.scene

# 方法1：使用keyframe_insert
# 位置关键帧
scene.frame_set(1)
obj.location = (0, 0, 0)
obj.keyframe_insert(data_path='location', frame=1)

scene.frame_set(30)
obj.location = (5, 0, 0)
obj.keyframe_insert(data_path='location', frame=30)

scene.frame_set(60)
obj.location = (5, 5, 5)
obj.keyframe_insert(data_path='location', frame=60)

# 方法2：使用insert_keyframes（批量）
obj.location = (10, 0, 0)
obj.keyframe_insert(data_path='location', frame=90)

# 旋转关键帧
scene.frame_set(1)
obj.rotation_euler = (0, 0, 0)
obj.keyframe_insert(data_path='rotation_euler', frame=1)

scene.frame_set(60)
obj.rotation_euler = (0, 0, 3.14159)
obj.keyframe_insert(data_path='rotation_euler', frame=60)

# 缩放关键帧
obj.scale = (1, 1, 1)
obj.keyframe_insert(data_path='scale', frame=1)

obj.scale = (2, 2, 2)
obj.keyframe_insert(data_path='scale', frame=60)

# 材质属性关键帧
mat = obj.active_material
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.1
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].keyframe_insert(data_path='default_value', frame=1)
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].keyframe_insert(data_path='default_value', frame=60)
"""
    
    @staticmethod
    def modify_fcurve_example():
        """修改F-Curve插值示例"""
        return """
import bpy

obj = bpy.context.active_object
action = obj.animation_action

if action:
    # 获取位置X轴的F-Curve
    fcurve = action.fcurves.find('location', index=0)
    
    if fcurve:
        # 修改所有关键帧的插值模式
        for kp in fcurve.keyframe_points:
            kp.interpolation = 'BEZIER'
            kp.easing = 'EASE_IN_OUT'
        
        # 修改特定关键帧
        if len(fcurve.keyframe_points) >= 2:
            kp = fcurve.keyframe_points[1]
            kp.interpolation = 'ELASTIC'
            kp.easing = 'EASE_OUT'
        
        # 修改贝塞尔控制点
        for kp in fcurve.keyframe_points:
            kp.handle_left_type = 'AUTO_CLAMPED'
            kp.handle_right_type = 'AUTO_CLAMPED'
        
        # 更新F-Curve
        fcurve.update()
"""
    
    @staticmethod
    def delete_keyframe_example():
        """删除关键帧示例"""
        return """
import bpy

obj = bpy.context.active_object

# 删除特定帧的关键帧
obj.keyframe_delete(data_path='location', frame=30)

# 删除所有动画数据
if obj.animation_data:
    obj.animation_data_clear()

# 删除特定F-Curve
action = obj.animation_action
if action:
    for fcurve in list(action.fcurves):
        if fcurve.data_path == 'location':
            action.fcurves.remove(fcurve)
"""

    @staticmethod
    def set_handle_types_example():
        """设置手柄类型示例"""
        return """
import bpy

obj = bpy.context.active_object
action = obj.animation_action

HANDLE_TYPES = {
    'FREE': '自由（完全自定义）',
    'ALIGNED': '对齐（保持切线对称）',
    'VECTOR': '向量（自动线性）',
    'AUTO': '自动（自动平滑）',
    'AUTO_CLAMPED': '自动钳制（默认，不超调）'
}

if action:
    for fcurve in action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.handle_left_type = 'AUTO_CLAMPED'
            kp.handle_right_type = 'AUTO_CLAMPED'
"""
```

### 4.2 驱动器系统

```python
class DriverSystemAPI:
    """驱动器系统API原子级规范"""
    
    DRIVER_TYPES = {
        'SIMPLE': {
            'description': '简单驱动器（单变量表达式）',
            'use_case': '一个属性驱动另一个属性',
            'example': 'var * 2'
        },
        'SCRIPTED': {
            'description': '脚本驱动器（多变量表达式）',
            'use_case': '复杂逻辑、数学函数',
            'example': 'var1 + sin(var2) * var3'
        },
        'AVERAGE': {
            'description': '平均值驱动器',
            'use_case': '多变量平均',
            'example': '自动计算平均值'
        },
        'SUM': {
            'description': '求和驱动器',
            'use_case': '多变量求和',
            'example': '自动计算总和'
        },
        'MIN': {
            'description': '最小值驱动器',
            'use_case': '取最小值',
            'example': '自动计算最小值'
        },
        'MAX': {
            'description': '最大值驱动器',
            'use_case': '取最大值',
            'example': '自动计算最大值'
        }
    }
    
    VARIABLE_TYPES = {
        'SINGLE_PROP': {
            'description': '单一属性引用',
            'path_format': 'bpy.data.objects["Cube"].location[0]',
            'use_case': '直接引用任意属性'
        },
        'TRANSFORMS': {
            'description': '变换通道',
            'components': ['location_x/y/z', 'rotation_x/y/z', 'scale_x/y/z'],
            'use_case': '引用对象的变换值',
            'transform_type': ['LOC_X', 'LOC_Y', 'LOC_Z', 'ROT_X', 'ROT_Y', 'ROT_Z', 'SCALE_X', 'SCALE_Y', 'SCALE_Z']
        },
        'ROTATION_DIFF': {
            'description': '旋转差',
            'use_case': '两对象间的旋转差',
            'requires': ['两个对象']
        },
        'DISTANCE': {
            'description': '距离',
            'use_case': '两对象间的距离',
            'requires': ['两个对象']
        }
    }
    
    @staticmethod
    def add_driver_example():
        """添加驱动器示例"""
        return """
import bpy

# 获取目标对象
obj = bpy.context.active_object
target = bpy.data.objects.get('Target')

# 方法1：使用driver_add
# 让Cube的Z位置由Target的X位置驱动
fcurve = obj.driver_add('location', 2)  # 2表示Z轴
driver = fcurve.driver
driver.type = 'SCRIPTED'

# 添加变量
var = driver.variables.new()
var.name = 'target_x'
var.type = 'TRANSFORMS'

# 配置变量
target_id = var.targets[0]
target_id.id = target
target_id.transform_type = 'LOC_X'
target_id.transform_space = 'TRANSFORM_SPACE'

# 设置表达式
driver.expression = 'target_x * 2'

# 方法2：通过动画数据添加
ad = obj.animation_data_create()
if not ad.drivers:
    ad.drivers.from_existing()

# 安全设置驱动器（带表达式）
def safe_add_driver(obj, data_path, index, expression, var_definitions):
    \"\"\"安全添加驱动器
    var_definitions: [{'name': 'x', 'type': 'TRANSFORMS', 'id': target_obj,
                      'transform_type': 'LOC_X', 'transform_space': 'TRANSFORM_SPACE'}]
    \"\"\"
    fcurve = obj.driver_add(data_path, index)
    driver = fcurve.driver
    driver.type = 'SCRIPTED'
    
    for var_def in var_definitions:
        var = driver.variables.new()
        var.name = var_def['name']
        var.type = var_def['type']
        
        target = var.targets[0]
        target.id = var_def['id']
        if 'transform_type' in var_def:
            target.transform_type = var_def['transform_type']
        if 'transform_space' in var_def:
            target.transform_space = var_def['transform_space']
        if 'data_path' in var_def:
            target.data_path = var_def['data_path']
    
    driver.expression = expression
    return driver

# 使用
target_obj = bpy.data.objects['Target']
safe_add_driver(
    obj=bpy.context.active_object,
    data_path='location',
    index=2,
    expression='target_x * 2 + offset',
    var_definitions=[
        {'name': 'target_x', 'type': 'TRANSFORMS', 'id': target_obj,
         'transform_type': 'LOC_X', 'transform_space': 'TRANSFORM_SPACE'},
        {'name': 'offset', 'type': 'SINGLE_PROP', 'id': target_obj,
         'data_path': 'location[1]'}
    ]
)
"""
```

### 4.3 形状键动画

```python
class ShapeKeyAnimationAPI:
    """形状键动画API原子级规范"""
    
    SHAPE_KEY_TYPES = {
        'BASE': {
            'name': 'Basis',
            'description': '基础形状（不可删除）',
            'value': '不适用（始终为0）',
            'access': 'obj.data.shape_keys.key_blocks["Basis"]'
        },
        'NORMAL': {
            'name': '自定义名称',
            'description': '普通形状键',
            'value': '0.0-1.0',
            'access': 'obj.data.shape_keys.key_blocks["Key_Name"]'
        },
        'RELATIVE': {
            'name': '自定义名称',
            'description': '相对形状键（参考另一个形状键）',
            'value': '0.0-1.0',
            'access': 'obj.data.shape_keys.key_blocks["Key_Name"]',
            'extra': 'relative_key'
        }
    }
    
    @staticmethod
    def create_and_animate_shape_keys():
        """创建和动画形状键示例"""
        return """
import bpy

obj = bpy.context.active_object
mesh = obj.data

# 确保有基础形状键
if not mesh.shape_keys:
    basis = obj.shape_key_add(name='Basis', from_mix=False)

# 添加形状键（基于当前网格状态）
# 先进入编辑模式修改网格
bpy.ops.object.mode_set(mode='EDIT')
# ... 修改顶点 ...
bpy.ops.object.mode_set(mode='OBJECT')

# 添加新形状键
smile = obj.shape_key_add(name='Smile', from_mix=False)

# 添加另一个形状键
frown = obj.shape_key_add(name='Frown', from_mix=False)

# 设置形状键值
smile.value = 0.0
frown.value = 0.0

# 动画形状键
scene = bpy.context.scene

# 第1帧：中性
scene.frame_set(1)
smile.value = 0.0
smile.keyframe_insert(data_path='value', frame=1)

# 第30帧：微笑
scene.frame_set(30)
smile.value = 1.0
smile.keyframe_insert(data_path='value', frame=30)

# 第60帧：皱眉
scene.frame_set(60)
smile.value = 0.0
frown.value = 1.0
smile.keyframe_insert(data_path='value', frame=60)
frown.keyframe_insert(data_path='value', frame=60)

# 修改形状键顶点位置
shape_key = mesh.shape_keys.key_blocks['Smile']
for i in range(len(shape_key.data)):
    co = shape_key.data[i].co
    # 修改顶点位置（向上移动嘴角）
    shape_key.data[i].co = (co.x, co.y, co.z + 0.1)
"""
```

---

## 五、渲染与输出API

### 5.1 Cycles渲染器

```python
class CyclesRendererAPI:
    """Cycles渲染器API原子级规范"""
    
    RENDER_PROPERTIES = {
        'sampling': {
            'samples': {'type': 'int', 'default': 128, 'range': [1, 2**20], 'description': '渲染采样数'},
            'use_adaptive_sampling': {'type': 'bool', 'default': True, 'description': '自适应采样'},
            'adaptive_threshold': {'type': 'float', 'default': 0.01, 'range': [0.0, 1.0]},
            'adaptive_min_samples': {'type': 'int', 'default': 0, 'range': [0, 1024]},
            'use_denoising': {'type': 'bool', 'default': True, 'description': '降噪'},
            'denoiser': {'type': 'enum', 'default': 'OPENIMAGEDENOISE',
                        'options': ['OPTIX', 'OPENIMAGEDENOISE']}
        },
        'viewport_sampling': {
            'viewport_samples': {'type': 'int', 'default': 32, 'range': [1, 2**20]},
            'use_viewport_denoising': {'type': 'bool', 'default': True}
        },
        'light_paths': {
            'max_bounces': {'type': 'int', 'default': 12, 'range': [1, 1024]},
            'diffuse_bounces': {'type': 'int', 'default': 4, 'range': [0, 1024]},
            'glossy_bounces': {'type': 'int', 'default': 4, 'range': [0, 1024]},
            'transmission_bounces': {'type': 'int', 'default': 12, 'range': [0, 1024]},
            'volume_bounces': {'type': 'int', 'default': 0, 'range': [0, 1024]},
            'transparent_max_bounces': {'type': 'int', 'default': 8, 'range': [0, 1024]},
            'caustics_refractive': {'type': 'bool', 'default': False},
            'caustics_reflective': {'type': 'bool', 'default': False}
        },
        'performance': {
            'threads': {'type': 'int', 'default': 0, 'description': 'CPU线程数（0=自动）'},
            'use_spatial_splits': {'type': 'bool', 'default': False, 'description': '空间分割（更好的BVH）'},
            'use_hair_bvh': {'type': 'bool', 'default': False, 'description': '独立毛发BVH'},
            'tile_size': {'type': 'int', 'default': 2048, 'description': '瓦片大小'}
        },
        'gpu': {
            'compute_device_type': {'type': 'enum', 'default': 'NONE',
                                   'options': ['NONE', 'CUDA', 'OPTIX', 'HIP', 'ONEAPI', 'METAL']},
            'device': {'type': 'enum', 'default': 'CPU', 'options': ['CPU', 'GPU']}
        },
        'film': {
            'exposure': {'type': 'float', 'default': 1.0, 'range': [0.0, 10.0]},
            'pass_alpha_threshold': {'type': 'float', 'default': 0.0},
            'transparent': {'type': 'bool', 'default': False}
        }
    }
    
    @staticmethod
    def configure_cycles_high_quality():
        """配置高质量Cycles渲染"""
        import bpy
        
        scene = bpy.context.scene
        scene.render.engine = 'CYCLES'
        
        cycles = scene.cycles
        # 采样
        cycles.samples = 256
        cycles.use_adaptive_sampling = True
        cycles.adaptive_threshold = 0.005
        cycles.adaptive_min_samples = 32
        cycles.use_denoising = True
        cycles.denoiser = 'OPENIMAGEDENOISE'
        
        # 光线追踪
        cycles.max_bounces = 24
        cycles.diffuse_bounces = 6
        cycles.glossy_bounces = 6
        cycles.transmission_bounces = 12
        cycles.transparent_max_bounces = 16
        cycles.volume_bounces = 4
        
        # 性能
        cycles.use_spatial_splits = True
        cycles.use_persistent_data = True
        
        # GPU
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for device in prefs.devices:
            device.use = True
        cycles.device = 'GPU'
        
        return {'status': 'success', 'samples': cycles.samples}
    
    @staticmethod
    def setup_passes():
        """设置渲染通道"""
        import bpy
        
        view_layer = bpy.context.view_layer
        view_layer.use_pass_combined = True
        view_layer.use_pass_z = True
        view_layer.use_pass_mist = True
        view_layer.use_pass_normal = True
        view_layer.use_pass_position = True
        view_layer.use_pass_diffuse_color = True
        view_layer.use_pass_diffuse_direct = True
        view_layer.use_pass_diffuse_indirect = True
        view_layer.use_pass_glossy_color = True
        view_layer.use_pass_glossy_direct = True
        view_layer.use_pass_glossy_indirect = True
        view_layer.use_pass_transmission_color = True
        view_layer.use_pass_transmission_direct = True
        view_layer.use_pass_emission = True
        view_layer.use_pass_environment = True
        view_layer.use_pass_ambient_occlusion = True
        view_layer.use_pass_shadow = True
        view_layer.cycles.use_pass_crypto_object = True
        view_layer.cycles.crypto_depth = 4
```

### 5.2 Eevee渲染器

```python
class EeveeRendererAPI:
    """Eevee渲染器API原子级规范"""
    
    EEVEE_PROPERTIES = {
        'taa_render_samples': {'type': 'int', 'default': 64, 'range': [1, 2**16]},
        'taa_samples': {'type': 'int', 'default': 16, 'range': [1, 2**16], 'description': '视口采样'},
        'use_taa_reprojection': {'type': 'bool', 'default': True},
        'use_ssr': {'type': 'bool', 'default': True, 'description': '屏幕空间反射'},
        'use_ssr_refraction': {'type': 'bool', 'default': False, 'description': '屏幕空间折射'},
        'use_gtao': {'type': 'bool', 'default': False, 'description': '环境光遮蔽'},
        'use_bloom': {'type': 'bool', 'default': False, 'description': '辉光'},
        'use_ssr': {'type': 'bool', 'default': True},
        'use_motion_blur': {'type': 'bool', 'default': False},
        'motion_blur_position': {'type': 'enum', 'default': 'CENTER', 'options': ['START', 'CENTER', 'END']},
        'motion_blur_shutter': {'type': 'float', 'default': 0.5, 'range': [0.0, 1.0]},
        'use_depth_of_field': {'type': 'bool', 'default': True},
        'bokeh_max_size': {'type': 'float', 'default': 100.0, 'range': [0.0, 2000.0]},
        'use_volumetric': {'type': 'bool', 'default': True, 'description': '体积渲染'},
        'use_volumetric_shadows': {'type': 'bool', 'default': False},
        'shadow_cube_size': {'type': 'enum', 'default': '512', 'options': ['64', '128', '256', '512', '1024', '2048']},
        'shadow_cascade_size': {'type': 'enum', 'default': '1024', 'options': ['256', '512', '1024', '2048', '4096']}
    }
    
    @staticmethod
    def configure_eevee_for_animation():
        """为动画渲染配置Eevee"""
        import bpy
        
        scene = bpy.context.scene
        scene.render.engine = 'BLENDER_EEVEE'
        
        eevee = scene.eevee
        # 采样
        eevee.taa_render_samples = 128
        eevee.taa_samples = 32
        eevee.use_taa_reprojection = True
        
        # 屏幕空间效果
        eevee.use_ssr = True
        eevee.use_ssr_refraction = False
        eevee.use_gtao = True
        eevee.gtao_distance = 0.2
        eevee.gtao_factor = 1.0
        eevee.gtao_quality = 0.5
        
        # 辉光
        eevee.use_bloom = False  # 视情况启用
        
        # 运动模糊
        eevee.use_motion_blur = True
        eevee.motion_blur_position = 'CENTER'
        eevee.motion_blur_shutter = 0.5
        
        # 景深
        eevee.use_depth_of_field = True
        eevee.bokeh_max_size = 100.0
        
        # 体积
        eevee.use_volumetric = True
        eevee.use_volumetric_shadows = False  # 性能考虑
        
        # 阴影
        eevee.shadow_cube_size = '1024'
        eevee.shadow_cascade_size = '2048'
        eevee.shadow_soft_shadows = True
        
        return {'status': 'success'}
```

### 5.3 批量渲染

```python
class BatchRenderingAPI:
    """批量渲染API原子级规范"""
    
    @staticmethod
    def render_multiple_cameras(scene_name, camera_names, output_dir, image_format='PNG'):
        """多相机批量渲染"""
        import bpy
        
        scene = bpy.data.scenes.get(scene_name)
        if not scene:
            return {'status': 'error', 'message': '场景不存在'}
        
        results = []
        for cam_name in camera_names:
            cam = bpy.data.objects.get(cam_name)
            if not cam or cam.type != 'CAMERA':
                results.append({'camera': cam_name, 'status': 'error', 'message': '相机不存在或类型错误'})
                continue
            
            scene.camera = cam
            scene.render.filepath = f'{output_dir}/{cam_name}.png'
            scene.render.image_settings.file_format = image_format
            
            try:
                bpy.ops.render.render(write_still=True)
                results.append({'camera': cam_name, 'status': 'success'})
            except Exception as e:
                results.append({'camera': cam_name, 'status': 'error', 'message': str(e)})
        
        return {'status': 'success', 'results': results}
    
    @staticmethod
    def render_animation_range(scene_name, start_frame, end_frame, output_dir, fps=24):
        """渲染动画范围"""
        import bpy
        
        scene = bpy.data.scenes.get(scene_name)
        if not scene:
            return {'status': 'error', 'message': '场景不存在'}
        
        scene.frame_start = start_frame
        scene.frame_end = end_frame
        scene.render.fps = fps
        scene.render.filepath = f'{output_dir}/frame_####.png'
        scene.render.image_settings.file_format = 'PNG'
        
        bpy.ops.render.render(animation=True)
        return {'status': 'success'}
    
    @staticmethod
    def command_line_render_example():
        """命令行渲染示例"""
        return {
            'single_frame': 'blender -b scene.blend -f 1 -o //render/frame_ -F PNG',
            'animation': 'blender -b scene.blend -s 1 -e 100 -a -o //render/anim_ -F PNG',
            'multiple_engines': 'blender -b scene.blend -E CYCLES -f 1 -o //render/cycles_ -F PNG',
            'specific_camera': 'blender -b scene.blend -f 1 -o //render/cam1_ -- --camera Camera1',
            'python_script': 'blender -b scene.blend -P render_script.py',
            'background_python': 'blender -b -P setup_and_render.py -- --output //renders/ --samples 256',
            'multi_machine': 'blender -b scene.blend -s 1 -e 25 -a -o //renders/node1_ && blender -b scene.blend -s 26 -e 50 -a -o //renders/node2_'
        }
```

---

## 六、插件开发

### 6.1 插件结构

```python
class AddonStructure:
    """Blender插件结构原子级规范"""
    
    BL_INFO_REQUIRED_KEYS = {
        'name': {'type': 'str', 'description': '插件名称'},
        'author': {'type': 'str', 'description': '作者'},
        'version': {'type': 'tuple', 'description': '版本号 (x, y, z)'},
        'blender': {'type': 'tuple', 'description': '兼容Blender版本 (4, 2, 0)'},
        'location': {'type': 'str', 'description': '在UI中的位置说明'},
        'description': {'type': 'str', 'description': '插件描述'},
        'category': {'type': 'str', 'description': '分类',
                    'options': ['3D View', 'Add Curve', 'Add Mesh', 'Animation', 'Bake', 'Camera',
                               'Compositing', 'Development', 'Game Engine', 'Geometry Nodes',
                               'Grease Pencil', 'Import-Export', 'Lighting', 'Material',
                               'Mesh', 'Node', 'Object', 'Paint', 'Pipeline', 'Physics',
                               'Render', 'Rigging', 'Scene', 'Sculpt', 'Sequencer',
                               'System', 'Text Editor', 'Tracking', 'UV', 'User Interface']}
    }
    
    BL_INFO_OPTIONAL_KEYS = {
        'warning': {'type': 'str', 'description': '警告信息'},
        'doc_url': {'type': 'str', 'description': '文档URL'},
        'tracker_url': {'type': 'str', 'description': '问题跟踪URL'},
        'support': {'type': 'str', 'description': '支持类型',
                   'options': ['OFFICIAL', 'COMMUNITY', 'TESTING']}
    }
    
    @staticmethod
    def basic_addon_template():
        """基础插件模板"""
        return '''
bl_info = {
    "name": "My Addon",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > My Panel",
    "description": "插件描述",
    "category": "Object",
    "support": "COMMUNITY"
}

import bpy


class MyOperator(bpy.types.Operator):
    """操作符说明"""
    bl_idname = "object.my_operator"
    bl_label = "我的操作"
    bl_options = {'REGISTER', 'UNDO'}
    
    # 属性定义
    my_float: bpy.props.FloatProperty(
        name="数值",
        description="测试数值",
        default=1.0,
        min=0.0,
        max=10.0
    )
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None
    
    def execute(self, context):
        obj = context.active_object
        obj.scale.x *= self.my_float
        self.report({'INFO'}, f"已应用缩放: {self.my_float}")
        return {'FINISHED'}


class MyPanel(bpy.types.Panel):
    bl_label = "我的面板"
    bl_idname = "VIEW3D_PT_my_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'My Tools'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        col = layout.column()
        col.operator("object.my_operator", text="执行操作", icon='MESH_CUBE')


classes = (
    MyOperator,
    MyPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
'''
```

### 6.2 UI开发

```python
class UIDevelopment:
    """UI开发API原子级规范"""
    
    LAYOUT_METHODS = {
        'column': {
            'method': 'layout.column()',
            'description': '垂直列布局',
            'parameters': ['align (bool): 对齐子元素']
        },
        'row': {
            'method': 'layout.row()',
            'description': '水平行布局',
            'parameters': ['align (bool): 对齐子元素']
        },
        'box': {
            'method': 'layout.box()',
            'description': '带边框的盒子',
            'parameters': []
        },
        'split': {
            'method': 'layout.split(factor=0.5, align=False)',
            'description': '分割布局',
            'parameters': ['factor (float): 分割比例', 'align (bool): 对齐']
        },
        'grid': {
            'method': 'layout.grid_flow(row_major=False, columns=0, even_columns=False, even_rows=False, align=False)',
            'description': '网格布局',
            'parameters': ['row_major', 'columns', 'even_columns', 'even_rows', 'align']
        },
        'menu_pie': {
            'method': 'layout.menu_pie()',
            'description': '饼形菜单',
            'parameters': []
        }
    }
    
    UI_ELEMENTS = {
        'prop': {
            'method': 'layout.prop(data, property, text="", text_ctxt="", translate=True, icon=\'NONE\', icon_only=False, emboss=True, slider=False)',
            'description': '属性控件',
            'example': 'col.prop(obj, "location", text="位置")'
        },
        'props_enum': {
            'method': 'layout.props_enum(data, property, icon_only=False)',
            'description': '枚举按钮组',
            'example': 'row.props_enum(scene, "my_enum")'
        },
        'operator': {
            'method': 'layout.operator(operator, text="", text_ctxt="", translate=True, icon=\'NONE\', emboss=True, depress=False)',
            'description': '操作符按钮',
            'example': 'col.operator("object.my_op", text="执行", icon=\'PLAY\')'
        },
        'label': {
            'method': 'layout.label(text="", text_ctxt="", translate=True, icon=\'NONE\')',
            'description': '文本标签',
            'example': 'col.label(text="设置", icon=\'SETTINGS\')'
        },
        'separator': {
            'method': 'layout.separator(factor=1.0)',
            'description': '分隔符',
            'example': 'col.separator(factor=2.0)'
        },
        'template_list': {
            'method': 'layout.template_list(listtype_name, list_id, dataptr, propname, active_dataptr, active_propname, rows=5, maxrows=5, type=\'DEFAULT\')',
            'description': '列表模板',
            'example': 'layout.template_list("MATERIAL_UL_mats", "", obj, "material_slots", obj, "active_material_index")'
        },
        'template_color_picker': {
            'method': 'layout.template_color_picker(data, property, value_slider=False, cubic=False, lock=False, lock_luminosity=False)',
            'description': '颜色选择器',
            'example': 'layout.template_color_picker(mat, "diffuse_color", value_slider=True)'
        }
    }
    
    @staticmethod
    def popup_dialog_example():
        """弹出对话框示例"""
        return '''
class MyDialog(bpy.types.Operator):
    bl_idname = "object.my_dialog"
    bl_label = "我的对话框"
    bl_options = {'REGISTER'}
    
    # 对话框属性
    name: bpy.props.StringProperty(name="名称", default="NewItem")
    count: bpy.props.IntProperty(name="数量", default=1, min=1, max=100)
    color: bpy.props.FloatVectorProperty(
        name="颜色",
        subtype='COLOR',
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0, max=1.0
    )
    
    def execute(self, context):
        # 创建对象
        for i in range(self.count):
            bpy.ops.mesh.primitive_cube_add(location=(i * 2.5, 0, 0))
            obj = context.active_object
            obj.name = f"{self.name}_{i:02d}"
            mat = bpy.data.materials.new(f"{obj.name}_mat")
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes['Principled BSDF']
            bsdf.inputs['Base Color'].default_value = self.color
            obj.data.materials.append(mat)
        
        self.report({'INFO'}, f"创建了 {self.count} 个对象")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


bpy.utils.register_class(MyDialog)
# 调用
# bpy.ops.object.my_dialog('INVOKE_DEFAULT')
'''
```

### 6.3 实用插件示例

```python
class PracticalAddonExamples:
    """实用插件示例集合"""
    
    @staticmethod
    def batch_rename_tool():
        """批量重命名工具"""
        return '''
import bpy
import re

class OBJECT_OT_batch_rename(bpy.types.Operator):
    bl_idname = "object.batch_rename"
    bl_label = "批量重命名"
    bl_options = {'REGISTER', 'UNDO'}
    
    find: bpy.props.StringProperty(
        name="查找",
        description="要查找的字符串（支持正则）",
        default=""
    )
    replace: bpy.props.StringProperty(
        name="替换",
        description="替换字符串",
        default=""
    )
    use_regex: bpy.props.BoolProperty(
        name="使用正则",
        default=False
    )
    prefix: bpy.props.StringProperty(name="前缀", default="")
    suffix: bpy.props.StringProperty(name="后缀", default="")
    padding: bpy.props.IntProperty(name="数字补零", default=2, min=0, max=10)
    
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0
    
    def execute(self, context):
        objs = context.selected_objects
        for i, obj in enumerate(objs):
            name = obj.name
            if self.find:
                if self.use_regex:
                    name = re.sub(self.find, self.replace, name)
                else:
                    name = name.replace(self.find, self.replace)
            
            number_str = str(i+1).zfill(self.padding) if self.padding > 0 else str(i+1)
            new_name = f"{self.prefix}{name}{self.suffix}_{number_str}"
            obj.name = new_name
        
        self.report({'INFO'}, f"已重命名 {len(objs)} 个对象")
        return {'FINISHED'}


class VIEW3D_PT_batch_rename(bpy.types.Panel):
    bl_label = "批量重命名"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tools'
    
    def draw(self, context):
        layout = self.layout
        layout.operator("object.batch_rename")
'''
    
    @staticmethod
    def render_queue_tool():
        """渲染队列工具"""
        return '''
import bpy
import os

class RenderQueueItem(bpy.types.PropertyGroup):
    scene: bpy.props.StringProperty(name="场景")
    camera: bpy.props.StringProperty(name="相机")
    output_path: bpy.props.StringProperty(name="输出路径", subtype='FILE_PATH')
    samples: bpy.props.IntProperty(name="采样", default=128)
    enabled: bpy.props.BoolProperty(name="启用", default=True)

class RENDER_OT_execute_queue(bpy.types.Operator):
    bl_idname = "render.execute_queue"
    bl_label = "执行渲染队列"
    
    def execute(self, context):
        scene = context.scene
        queue = scene.render_queue_items
        
        for item in queue:
            if not item.enabled:
                continue
            
            target_scene = bpy.data.scenes.get(item.scene)
            if not target_scene:
                continue
            
            target_camera = bpy.data.objects.get(item.camera)
            if not target_camera:
                continue
            
            target_scene.camera = target_camera
            target_scene.cycles.samples = item.samples
            target_scene.render.filepath = item.output_path
            
            # 设置当前场景
            context.window.scene = target_scene
            
            # 渲染
            bpy.ops.render.render(write_still=True)
            self.report({'INFO'}, f"渲染完成: {item.scene} / {item.camera}")
        
        return {'FINISHED'}
'''
```

---

## 七、与AE集成工作流

### 7.1 Blender→AE导出流程

```python
class BlenderToAEPipeline:
    """Blender到AE导出流程原子级规范"""
    
    EXPORT_STRATEGIES = {
        'exr_multilayer': {
            'format': 'OPEN_EXR_MULTILAYER',
            'description': '多层EXR（推荐）',
            'color_depth': '32',
            'channels': ['Combined', 'Depth', 'Mist', 'CryptoObject', 'Diffuse', 'Specular'],
            'advantages': ['单文件包含所有通道', 'AE原生支持', '高质量浮点'],
            'disadvantages': ['文件较大']
        },
        'exr_single': {
            'format': 'OPEN_EXR',
            'description': '单层EXR',
            'color_depth': '32',
            'channels': ['Combined'],
            'use_case': '简单合成'
        },
        'png_sequence': {
            'format': 'PNG',
            'description': 'PNG序列',
            'color_depth': '8/16',
            'channels': ['Combined', 'Alpha'],
            'advantages': ['兼容性好', '文件小'],
            'disadvantages': ['无深度信息', '无HDR']
        },
        'tiff_sequence': {
            'format': 'TIFF',
            'description': 'TIFF序列',
            'color_depth': '8/16/32',
            'channels': ['Combined', 'Alpha']
        }
    }
    
    @staticmethod
    def setup_ae_friendly_render():
        """配置AE友好的渲染设置"""
        import bpy
        
        scene = bpy.context.scene
        
        # 渲染格式
        scene.render.image_settings.file_format = 'OPEN_EXR_MULTILAYER'
        scene.render.image_settings.color_depth = '32'
        scene.render.image_settings.exr_codec = 'ZIP'
        
        # 启用必要通道
        view_layer = scene.view_layers[0]
        view_layer.use_pass_combined = True
        view_layer.use_pass_z = True
        view_layer.use_pass_mist = True
        view_layer.use_pass_normal = True
        view_layer.use_pass_diffuse_direct = True
        view_layer.use_pass_diffuse_indirect = True
        view_layer.use_pass_specular_direct = True
        view_layer.use_pass_specular_indirect = True
        view_layer.use_pass_shadow = True
        view_layer.use_pass_ambient_occlusion = True
        view_layer.use_pass_crypto_object = True
        view_layer.cycles.crypto_depth = 6
        
        # 渲染分辨率匹配AE合成
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
        scene.render.resolution_percentage = 100
        
        # 帧率
        scene.render.fps = 24
        
        return {'status': 'success'}
    
    @staticmethod
    def export_camera_data_to_jsx():
        """导出相机数据为AE JSX脚本"""
        return '''
import bpy
import math

def export_camera_to_jsx(camera_name, output_path, frame_start=1, frame_end=120):
    \"\"\"导出Blender相机到AE JSX脚本\"\"\"
    cam = bpy.data.objects.get(camera_name)
    if not cam or cam.type != 'CAMERA':
        return None
    
    scene = bpy.context.scene
    fps = scene.render.fps
    
    jsx_lines = [
        "// AE JSX脚本 - 由Blender导出",
        "var comp = app.project.activeItem;",
        "if (!comp || !(comp instanceof CompItem)) {",
        "    alert('请先打开合成');",
        "}",
        "var cam = comp.layer('{cam_name}') || comp.layers.addCamera('{cam_name}', [0,0]);".format(cam_name=camera_name),
        "cam.name = '{cam_name}';".format(cam_name=camera_name),
        ""
    ]
    
    # 转换坐标系（Blender Z向上，AE Y向上）
    for frame in range(frame_start, frame_end + 1):
        scene.frame_set(frame)
        
        # 相机位置（Blender→AE坐标变换）
        loc = cam.matrix_world.translation
        # Blender: X右 Y里 Z上 / AE: X右 Y下 Z里
        ae_x = loc.x * comp.width / 2  # 缩放到像素
        ae_y = -loc.z * comp.height / 2  # Y轴反转
        ae_z = -loc.y * 1000  # 缩放Z深度
        
        # 相机旋转
        rot = cam.matrix_world.to_euler()
        # 转换为AE的度数
        ae_rot_x = math.degrees(rot.x)  # X旋转
        ae_rot_y = -math.degrees(rot.y)  # Y旋转（方向反转）
        ae_rot_z = -math.degrees(rot.z)  # Z旋转（方向反转）
        
        time_sec = (frame - frame_start) / fps
        
        jsx_lines.append(f"cam.position.setValueAtTime({time_sec}, [{ae_x}, {ae_y}, {ae_z}]);")
        jsx_lines.append(f"cam.rotationX.setValueAtTime({time_sec}, {ae_rot_x});")
        jsx_lines.append(f"cam.rotationY.setValueAtTime({time_sec}, {ae_rot_y});")
        jsx_lines.append(f"cam.rotationZ.setValueAtTime({time_sec}, {ae_rot_z});")
        
        # 焦距转换（毫米→像素）
        sensor_width = cam.data.sensor_width  # mm
        focal_length = cam.data.lens  # mm
        zoom = focal_length / sensor_width * comp.width
        jsx_lines.append(f"cam.zoom.setValueAtTime({time_sec}, {zoom});")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\\n'.join(jsx_lines))
    
    return output_path
'''
```

### 7.2 AEExpressionLink集成

```python
class AEExpressionLinkIntegration:
    """AEExpressionLink集成原子级规范"""
    
    DATA_EXPORT_FORMATS = {
        'json': {
            'description': 'JSON格式（通用）',
            'use_case': '跨软件数据交换',
            'structure': 'keyframes + properties'
        },
        'jsx': {
            'description': 'AE JavaScript脚本',
            'use_case': '直接在AE中执行',
            'structure': 'setValueAtTime调用'
        },
        'csv': {
            'description': 'CSV表格',
            'use_case': '手动数据查看',
            'structure': 'frame,value行'
        },
        'expression': {
            'description': 'AE表达式字符串',
            'use_case': '直接粘贴到AE表达式栏',
            'structure': 'JavaScript表达式'
        }
    }
    
    @staticmethod
    def export_blender_to_ae_expressions():
        """导出Blender数据为AE表达式"""
        return '''
import bpy
import json
import math

def export_camera_as_json(camera_name, output_path, frame_range=(1, 120)):
    \"\"\"导出相机数据为JSON格式\"\"\"
    cam = bpy.data.objects.get(camera_name)
    scene = bpy.context.scene
    fps = scene.render.fps
    
    data = {
        'camera': camera_name,
        'fps': fps,
        'resolution': [scene.render.resolution_x, scene.render.resolution_y],
        'keyframes': {
            'position': [],
            'rotation': [],
            'zoom': []
        }
    }
    
    for frame in range(frame_range[0], frame_range[1] + 1):
        scene.frame_set(frame)
        time = (frame - 1) / fps
        
        loc = cam.matrix_world.translation
        rot = cam.matrix_world.to_euler()
        
        # AE坐标系转换
        ae_pos = [loc.x, -loc.z, -loc.y]
        ae_rot = [math.degrees(rot.x), -math.degrees(rot.z), math.degrees(rot.y)]
        
        sensor = cam.data.sensor_width
        focal = cam.data.lens
        zoom = focal / sensor * scene.render.resolution_x
        
        data['keyframes']['position'].append({'time': time, 'value': ae_pos})
        data['keyframes']['rotation'].append({'time': time, 'value': ae_rot})
        data['keyframes']['zoom'].append({'time': time, 'value': zoom})
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return data


def generate_ae_expression_from_json(json_path, property_type='position'):
    \"\"\"从JSON生成AE表达式\"\"\"
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    if property_type not in data['keyframes']:
        return None
    
    keyframes = data['keyframes'][property_type]
    
    if property_type == 'position':
        # 生成位置表达式
        expr_lines = ['// 由Blender导出的位置表达式', 'var kfs = [']
        for kf in keyframes:
            v = kf['value']
            expr_lines.append(f"  [{kf['time']}, [{v[0]}, {v[1]}, {v[2]}]],")
        expr_lines.append('];')
        expr_lines.append('var t = time;')
        expr_lines.append('var result = kfs[kfs.length-1][1];')
        expr_lines.append('for (var i = 0; i < kfs.length - 1; i++) {')
        expr_lines.append('  if (t >= kfs[i][0] && t <= kfs[i+1][0]) {')
        expr_lines.append('    var dt = kfs[i+1][0] - kfs[i][0];')
        expr_lines.append('    var f = dt > 0 ? (t - kfs[i][0]) / dt : 0;')
        expr_lines.append('    result = [')
        expr_lines.append('      kfs[i][1][0] + (kfs[i+1][1][0] - kfs[i][1][0]) * f,')
        expr_lines.append('      kfs[i][1][1] + (kfs[i+1][1][1] - kfs[i][1][1]) * f,')
        expr_lines.append('      kfs[i][1][2] + (kfs[i+1][1][2] - kfs[i][1][2]) * f')
        expr_lines.append('    ];')
        expr_lines.append('    break;')
        expr_lines.append('  }')
        expr_lines.append('}')
        expr_lines.append('result;')
        return '\\n'.join(expr_lines)
    
    return None
'''
```

---

## 八、性能优化

### 8.1 Python脚本性能

```python
class PythonScriptPerformance:
    """Python脚本性能优化原子级规范"""
    
    PERFORMANCE_PATTERNS = {
        'batch_operations': {
            'description': '批量操作（减少重复访问）',
            'bad_practice': """
# 慢：循环访问属性
for obj in bpy.data.objects:
    obj.location.x = obj.location.x * 2
    obj.location.y = obj.location.y * 2
    obj.location.z = obj.location.z * 2
""",
            'good_practice': """
# 快：批量处理
import mathutils
for obj in bpy.data.objects:
    loc = obj.location
    obj.location = mathutils.Vector((loc.x*2, loc.y*2, loc.z*2))
"""
        },
        'avoid_context_updates': {
            'description': '避免循环中的上下文更新',
            'bad_practice': """
# 慢：每次循环都更新场景
for obj in bpy.data.objects:
    obj.location = (0, 0, 0)
    bpy.context.view_layer.update()  # 不要这样做！
""",
            'good_practice': """
# 快：批量修改后一次性更新
for obj in bpy.data.objects:
    obj.location = (0, 0, 0)
bpy.context.view_layer.update()  # 只更新一次
"""
        },
        'mesh_batch_edit': {
            'description': '网格批量编辑',
            'bad_practice': """
# 慢：逐个修改顶点（触发depsgraph）
for v in mesh.vertices:
    v.co.x += 0.1
""",
            'good_practice': """
# 快：使用BMesh批量处理
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh)
for v in bm.verts:
    v.co.x += 0.1
bm.to_mesh(mesh)
bm.free()
mesh.update()
"""
        },
        'disable_auto_update': {
            'description': '禁用自动更新',
            'code': """
# 大批量操作时禁用自动更新
import bpy
bpy.context.scene.render.engine = 'CYCLES'  # 切到EEVEE更快

# 方法1：上下文管理器
class DisableUpdates:
    def __enter__(self):
        self.use_anim = bpy.context.scene.use_preview_range
        bpy.context.scene.frame_set(bpy.context.scene.frame_current)
        return self
    def __exit__(self, *args):
        bpy.context.view_layer.update()

# 方法2：批量操作前后
bpy.ops.ed.undo_push(message="批量操作前")
# ... 大量操作 ...
bpy.context.view_layer.update()
"""
        },
        'memory_management': {
            'description': '内存管理',
            'patterns': [
                '及时释放bmesh: bm.free()',
                '删除对象后清理：bpy.data.meshes.remove(unnamed_mesh)',
                '清理orphan data：bpy.ops.outliner.orphans_purge()',
                '使用with语句管理资源',
                '避免在循环中创建临时对象'
            ]
        }
    }
    
    @staticmethod
    def profile_script_example():
        """脚本性能分析示例"""
        return '''
import bpy
import time
import cProfile
import pstats
import io

def profile_function(func, *args, **kwargs):
    \"\"\"分析函数性能\"\"\"
    pr = cProfile.Profile()
    pr.enable()
    result = func(*args, **kwargs)
    pr.disable()
    
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)
    print(s.getvalue())
    return result

def time_operation(func, *args, **kwargs):
    \"\"\"计时操作\"\"\"
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    print(f"{func.__name__}: {elapsed:.3f}秒")
    return result

# 使用示例
def batch_create_objects(count):
    for i in range(count):
        bpy.ops.mesh.primitive_cube_add(location=(i*2.5, 0, 0))

profile_function(batch_create_objects, 100)
time_operation(batch_create_objects, 100)
'''
```

### 8.2 渲染性能

```python
class RenderPerformanceOptimization:
    """渲染性能优化原子级规范"""
    
    OPTIMIZATION_STRATEGIES = {
        'sampling': {
            'adaptive_sampling': {
                'description': '自适应采样',
                'config': 'cycles.use_adaptive_sampling = True',
                'threshold': 'cycles.adaptive_threshold = 0.01',
                'benefit': '减少50-80%采样时间'
            },
            'denoising': {
                'description': '降噪',
                'config': 'cycles.use_denoising = True',
                'denoiser': 'OPENIMAGEDENOISE（推荐CPU）/ OPTIX（推荐NVIDIA）',
                'benefit': '可降低采样数4-8倍'
            },
            'viewport_samples': {
                'description': '视口采样降低',
                'config': 'eevee.taa_samples = 8（视口）',
                'benefit': '提高交互速度'
            }
        },
        'geometry': {
            'bvh_optimization': {
                'description': 'BVH构建优化',
                'config': 'cycles.use_spatial_splits = True',
                'benefit': '复杂场景渲染加速20-40%',
                'cost': 'BVH构建时间增加'
            },
            'persistent_data': {
                'description': '持久化数据',
                'config': 'cycles.use_persistent_data = True',
                'benefit': '动画渲染每帧减少BVH重建',
                'use_case': '场景几何不变的动画'
            },
            'simplify': {
                'description': '简化设置',
                'config': 'scene.render.use_simplify = True; scene.render.simplify_subdivision = 1',
                'benefit': '减少细分表面渲染时间'
            }
        },
        'materials': {
            'light_paths': {
                'description': '优化光线追踪深度',
                'config': 'cycles.max_bounces = 8; cycles.transparent_max_bounces = 4',
                'benefit': '减少不必要的光线计算'
            },
            'caustics': {
                'description': '禁用焦散（无玻璃场景）',
                'config': 'cycles.caustics_refractive = False; cycles.caustics_reflective = False',
                'benefit': '减少焦散光线计算'
            },
            'subsurface': {
                'description': '次表面散射优化',
                'config': '在材质中降低subsurface散射深度',
                'benefit': '减少SSS计算'
            }
        },
        'texture_memory': {
            'image_compression': {
                'description': '图像压缩',
                'config': 'image.use_alpha = False（无透明时）',
                'benefit': '减少内存占用'
            },
            'mipmap': {
                'description': 'Mipmap',
                'config': 'image.use_mipmap = True',
                'benefit': '减少远处纹理内存'
            },
            'resolution_limit': {
                'description': '限制纹理分辨率',
                'config': 'image.size = [1024, 1024]（如果允许）',
                'benefit': '减少显存占用'
            }
        },
        'render_layers': {
            'compositing_in_post': {
                'description': '后期合成',
                'config': '将辉光、AO等放到AE后期',
                'benefit': '减少Cycles计算量'
            },
            'layer_exclusion': {
                'description': '图层排除',
                'config': 'view_layer.layer_collection.exclude = True',
                'benefit': '不渲染不必要的对象'
            }
        }
    }
    
    @staticmethod
    def auto_optimize_for_animation():
        """为动画渲染自动优化"""
        import bpy
        
        scene = bpy.context.scene
        cycles = scene.cycles
        
        # 采样优化
        cycles.samples = 64  # 配合降噪
        cycles.use_adaptive_sampling = True
        cycles.adaptive_threshold = 0.02
        cycles.use_denoising = True
        cycles.denoiser = 'OPENIMAGEDENOISE'
        
        # 光线追踪优化
        cycles.max_bounces = 6
        cycles.diffuse_bounces = 2
        cycles.glossy_bounces = 2
        cycles.transmission_bounces = 4
        cycles.transparent_max_bounces = 4
        cycles.volume_bounces = 0
        cycles.caustics_refractive = False
        cycles.caustics_reflective = False
        
        # 性能优化
        cycles.use_spatial_splits = True
        cycles.use_persistent_data = True
        
        # 简化
        scene.render.use_simplify = True
        scene.render.simplify_subdivision_render = 2
        scene.render.simplify_child_particles_render = 0.5
        
        return {'status': 'success'}
```

---

## 附录

### 附录A：bpy API速查表

```python
class BpyQuickReference:
    """bpy API速查表"""
    
    QUICK_REFERENCE = {
        '对象操作': {
            '创建': 'bpy.ops.object.add(type="MESH")',
            '删除': 'bpy.data.objects.remove(obj)',
            '复制': 'bpy.ops.object.duplicate()',
            '选择': 'obj.select_set(True)',
            '激活': 'context.view_layer.objects.active = obj',
            '获取活动': 'context.active_object',
            '获取选中': 'context.selected_objects',
            '父级': 'child.parent = parent',
            '清除父级': 'child.parent = None',
            '链接场景': 'scene.collection.objects.link(obj)',
            '取消链接': 'scene.collection.objects.unlink(obj)'
        },
        '网格操作': {
            '创建网格': 'mesh = bpy.data.meshes.new("Name")',
            '添加顶点': 'mesh.vertices.add(count)',
            '更新网格': 'mesh.update()',
            '进入编辑模式': 'bpy.ops.object.mode_set(mode="EDIT")',
            '退出编辑模式': 'bpy.ops.object.mode_set(mode="OBJECT")'
        },
        '材质操作': {
            '创建材质': 'mat = bpy.data.materials.new("Name")',
            '启用节点': 'mat.use_nodes = True',
            '添加节点': 'mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")',
            '连接节点': 'mat.node_tree.links.new(from_socket, to_socket)',
            '分配材质': 'obj.data.materials.append(mat)'
        },
        '相机操作': {
            '创建相机': 'bpy.ops.object.camera_add()',
            '设置活动相机': 'scene.camera = cam',
            '焦距': 'cam.data.lens = 50  # mm',
            '传感器宽度': 'cam.data.sensor_width = 36',
            '光圈': 'cam.data.dof.aperture_fstop = 2.8',
            '对焦对象': 'cam.data.dof.focus_object = target_obj'
        },
        '灯光操作': {
            '点光源': 'bpy.ops.object.light_add(type="POINT")',
            '方向光': 'bpy.ops.object.light_add(type="SUN")',
            '聚光灯': 'bpy.ops.object.light_add(type="SPOT")',
            '面光源': 'bpy.ops.object.light_add(type="AREA")',
            '能量': 'light.data.energy = 1000',
            '颜色': 'light.data.color = (1.0, 0.9, 0.8)'
        },
        '动画操作': {
            '插入关键帧': 'obj.keyframe_insert(data_path="location", frame=1)',
            '删除关键帧': 'obj.keyframe_delete(data_path="location", frame=1)',
            '创建动作': 'action = bpy.data.actions.new("Name")',
            '获取F-Curve': 'action.fcurves.find("location", index=0)',
            '设置帧': 'scene.frame_set(frame)',
            '获取当前帧': 'scene.frame_current',
            '设置范围': 'scene.frame_start = 1; scene.frame_end = 120'
        },
        '渲染操作': {
            '渲染单帧': 'bpy.ops.render.render(write_still=True)',
            '渲染动画': 'bpy.ops.render.render(animation=True)',
            '设置路径': 'scene.render.filepath = "//renders/output.png"',
            '设置格式': 'scene.render.image_settings.file_format = "PNG"',
            '切换引擎': 'scene.render.engine = "CYCLES"',
            '设置分辨率': 'scene.render.resolution_x = 1920'
        },
        '数据访问': {
            '所有对象': 'bpy.data.objects',
            '所有网格': 'bpy.data.meshes',
            '所有材质': 'bpy.data.materials',
            '所有相机': 'bpy.data.cameras',
            '所有灯光': 'bpy.data.lights',
            '所有动作': 'bpy.data.actions',
            '所有图像': 'bpy.data.images',
            '所有场景': 'bpy.data.scenes',
            '按名查找': 'bpy.data.objects.get("Name")'
        }
    }
```

### 附录B：常用Blender Python代码片段

```python
"""
常用代码片段集合
"""

# 1. 遍历所有对象并按类型过滤
import bpy
mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH']
camera_objects = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
light_objects = [obj for obj in bpy.data.objects if obj.type == 'LIGHT']

# 2. 创建材质并分配
def create_material(name, base_color, metallic=0.0, roughness=0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = base_color
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    return mat

# 3. 设置渲染输出
def setup_render(filepath, resolution=(1920, 1080), fps=24, samples=128):
    scene = bpy.context.scene
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.fps = fps
    scene.render.filepath = filepath
    scene.render.image_settings.file_format = 'PNG'
    scene.cycles.samples = samples

# 4. 批量应用修改器
def apply_all_modifiers(obj):
    bpy.context.view_layer.objects.active = obj
    for mod in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)

# 5. 重置场景
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

# 6. 导出OBJ
def export_obj(filepath, selection_only=True):
    bpy.ops.wm.obj_export(
        filepath=filepath,
        export_selected_objects=selection_only
    )

# 7. 导出FBX
def export_fbx(filepath, selection_only=True):
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=selection_only,
        object_types={'MESH', 'CAMERA', 'LIGHT'},
        bake_anim=True
    )

# 8. 创建相机并设置
def create_camera(name, location=(0, -10, 0), rotation=(1.5708, 0, 0), focal_length=50):
    bpy.ops.object.camera_add(location=location, rotation=rotation)
    cam = bpy.context.active_object
    cam.name = name
    cam.data.lens = focal_length
    bpy.context.scene.camera = cam
    return cam

# 9. 创建三点光照
def create_three_point_lighting(target_obj):
    # 主光
    bpy.ops.object.light_add(type='AREA', location=(5, -5, 8))
    key = bpy.context.active_object
    key.name = 'KeyLight'
    key.data.energy = 1000
    key.data.size = 3
    key.rotation_euler = (0.6, 0.4, 0.5)
    
    # 补光
    bpy.ops.object.light_add(type='AREA', location=(-5, -3, 5))
    fill = bpy.context.active_object
    fill.name = 'FillLight'
    fill.data.energy = 500
    fill.data.size = 4
    
    # 背光
    bpy.ops.object.light_add(type='AREA', location=(0, 5, 6))
    back = bpy.context.active_object
    back.name = 'BackLight'
    back.data.energy = 800
    back.data.size = 2

# 10. 时间驱动动画
def animate_with_time(obj, expression, frame_range=(1, 120)):
    """使用表达式驱动动画"""
    import math
    scene = bpy.context.scene
    
    for frame in range(frame_range[0], frame_range[1] + 1):
        scene.frame_set(frame)
        t = (frame - frame_range[0]) / 24.0
        # 计算表达式
        x = math.sin(t * 2) * 5
        y = math.cos(t * 2) * 5
        z = math.sin(t * 4) * 2
        obj.location = (x, y, z)
        obj.keyframe_insert(data_path='location', frame=frame)
```

### 附录C：插件开发模板

```python
"""
完整插件开发模板
"""

bl_info = {
    "name": "Plugin Template",
    "author": "Author Name",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Template",
    "description": "Complete plugin template",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

import bpy
from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty
)
from bpy.types import (
    Operator,
    Panel,
    PropertyGroup,
    UIList
)


# ========== PropertyGroup ==========

class TemplateSettings(PropertyGroup):
    """插件设置属性组"""
    name_filter: StringProperty(
        name="名称过滤",
        description="按名称过滤对象",
        default=""
    )
    count: IntProperty(
        name="数量",
        description="创建数量",
        default=1,
        min=1,
        max=100
    )
    scale: FloatProperty(
        name="缩放",
        default=1.0,
        min=0.001,
        soft_max=10.0
    )
    use_random_rotation: BoolProperty(
        name="随机旋转",
        default=False
    )
    mode: EnumProperty(
        name="模式",
        items=[
            ('CUBE', '立方体', ''),
            ('SPHERE', '球体', ''),
            ('CYLINDER', '圆柱体', '')
        ],
        default='CUBE'
    )


# ========== Operator ==========

class TEMPLATE_OT_create_objects(Operator):
    """创建多个对象"""
    bl_idname = "template.create_objects"
    bl_label = "创建对象"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene is not None
    
    def execute(self, context):
        settings = context.scene.template_settings
        import random
        
        for i in range(settings.count):
            if settings.mode == 'CUBE':
                bpy.ops.mesh.primitive_cube_add()
            elif settings.mode == 'SPHERE':
                bpy.ops.mesh.primitive_uv_sphere_add()
            elif settings.mode == 'CYLINDER':
                bpy.ops.mesh.primitive_cylinder_add()
            
            obj = context.active_object
            obj.name = f"{settings.mode}_{i:03d}"
            obj.scale = (settings.scale,) * 3
            
            if settings.use_random_rotation:
                import math
                obj.rotation_euler = (
                    random.uniform(0, math.pi * 2),
                    random.uniform(0, math.pi * 2),
                    random.uniform(0, math.pi * 2)
                )
        
        self.report({'INFO'}, f"创建了 {settings.count} 个对象")
        return {'FINISHED'}


# ========== Panel ==========

class VIEW3D_PT_template(Panel):
    bl_label = "Template Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Template'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.template_settings
        
        box = layout.box()
        box.label(text="创建选项", icon='OBJECT_DATA')
        box.prop(settings, "mode")
        box.prop(settings, "count")
        box.prop(settings, "scale")
        box.prop(settings, "use_random_rotation")
        box.operator("template.create_objects", icon='ADD')


# ========== Registration ==========

classes = (
    TemplateSettings,
    TEMPLATE_OT_create_objects,
    VIEW3D_PT_template,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.template_settings = PointerProperty(type=TemplateSettings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.template_settings


if __name__ == "__main__":
    register()
```

### 附录D：渲染设置参数表

```python
class RenderSettingsReference:
    """渲染设置完整参数表"""
    
    RENDER_ENGINES = {
        'CYCLES': {
            'description': 'Cycles渲染器（光线追踪）',
            'quality': '高',
            'speed': '慢',
            'use_case': '高质量产品渲染、动画',
            'features': ['物理正确', '焦散', '次表面散射', '体积', '毛发']
        },
        'BLENDER_EEVEE': {
            'description': 'Eevee渲染器（实时）',
            'quality': '中高',
            'speed': '快',
            'use_case': '实时预览、动画、效果展示',
            'features': ['实时', '屏幕空间反射', '体积', '辉光', '景深']
        },
        'BLENDER_WORKBENCH': {
            'description': 'Workbench（工作台）',
            'quality': '低',
            'speed': '最快',
            'use_case': '建模预览、概念图',
            'features': ['基础着色', '材质预览', '线框']
        }
    }
    
    IMAGE_FORMATS = {
        'PNG': {
            'description': 'PNG（无损压缩）',
            'color_depth': ['8', '16'],
            'alpha': True,
            'use_case': '通用输出、合成素材'
        },
        'JPEG': {
            'description': 'JPEG（有损压缩）',
            'color_depth': ['8'],
            'alpha': False,
            'use_case': '最终输出、网络发布'
        },
        'OPEN_EXR': {
            'description': 'OpenEXR（HDR）',
            'color_depth': ['16', '32'],
            'alpha': True,
            'use_case': 'HDR合成、多层通道'
        },
        'OPEN_EXR_MULTILAYER': {
            'description': 'OpenEXR多层',
            'color_depth': ['16', '32'],
            'alpha': True,
            'use_case': '后期合成、Nuke/AE集成'
        },
        'TIFF': {
            'description': 'TIFF',
            'color_depth': ['8', '16', '32'],
            'alpha': True,
            'use_case': '印刷、广播'
        },
        'TARGA': {
            'description': 'TGA',
            'color_depth': ['8', '16'],
            'alpha': True,
            'use_case': '游戏纹理、传统合成'
        },
        'CINEON': {
            'description': 'Cineon',
            'color_depth': ['10'],
            'alpha': False,
            'use_case': '电影后期'
        },
        'DPX': {
            'description': 'DPX',
            'color_depth': ['8', '10', '12', '16'],
            'alpha': True,
            'use_case': '电影后期、广播'
        }
    }
    
    COLOR_SPACES = {
        'sRGB': {'description': '标准RGB（显示用）', 'gamma': 2.2},
        'Linear Rec.709': {'description': '线性Rec.709', 'gamma': 1.0},
        'Linear sRGB': {'description': '线性sRGB', 'gamma': 1.0},
        'Filmic sRGB': {'description': 'Filmic（电影感）', 'gamma': 2.2},
        'ACES2065-1': {'description': 'ACES2065-1', 'gamma': 1.0},
        'ACEScg': {'description': 'ACEScg', 'gamma': 1.0},
        'Non-Color': {'description': '非颜色数据', 'gamma': 1.0},
        'Raw': {'description': '原始数据', 'gamma': 1.0}
    }
    
    RENDER_QUALITY_PRESETS = {
        'draft': {
            'engine': 'BLENDER_EEVEE',
            'eevee_samples': 16,
            'cycles_samples': 32,
            'resolution_percentage': 50,
            'use_denoising': True,
            'use_simplify': True
        },
        'preview': {
            'engine': 'BLENDER_EEVEE',
            'eevee_samples': 32,
            'cycles_samples': 64,
            'resolution_percentage': 75,
            'use_denoising': True,
            'use_simplify': False
        },
        'final_eevee': {
            'engine': 'BLENDER_EEVEE',
            'eevee_samples': 128,
            'resolution_percentage': 100,
            'use_denoising': True,
            'use_motion_blur': True
        },
        'final_cycles': {
            'engine': 'CYCLES',
            'cycles_samples': 256,
            'resolution_percentage': 100,
            'use_denoising': True,
            'use_adaptive_sampling': True,
            'adaptive_threshold': 0.005
        },
        'high_quality': {
            'engine': 'CYCLES',
            'cycles_samples': 1024,
            'resolution_percentage': 100,
            'use_denoising': False,  # 最高质量不使用降噪
            'use_adaptive_sampling': True,
            'adaptive_threshold': 0.001,
            'max_bounces': 24
        }
    }
    
    @staticmethod
    def apply_preset(preset_name):
        """应用渲染预设"""
        import bpy
        
        presets = RenderSettingsReference.RENDER_QUALITY_PRESETS
        if preset_name not in presets:
            return {'status': 'error', 'message': '无效预设'}
        
        preset = presets[preset_name]
        scene = bpy.context.scene
        
        scene.render.engine = preset['engine']
        
        if preset['engine'] == 'CYCLES':
            cycles = scene.cycles
            cycles.samples = preset.get('cycles_samples', 128)
            cycles.use_denoising = preset.get('use_denoising', True)
            cycles.use_adaptive_sampling = preset.get('use_adaptive_sampling', True)
            if 'adaptive_threshold' in preset:
                cycles.adaptive_threshold = preset['adaptive_threshold']
            if 'max_bounces' in preset:
                cycles.max_bounces = preset['max_bounces']
        elif preset['engine'] == 'BLENDER_EEVEE':
            scene.eevee.taa_render_samples = preset.get('eevee_samples', 64)
        
        scene.render.resolution_percentage = preset.get('resolution_percentage', 100)
        if 'use_simplify' in preset:
            scene.render.use_simplify = preset['use_simplify']
        
        return {'status': 'success', 'preset': preset_name}
```

---

## 总结

本指南系统覆盖了Blender Python API的完整技术栈，从底层架构到实战应用：

| 章节 | 核心内容 | 适用场景 |
|------|---------|---------|
| 一、API架构 | bpy.data/context/ops三层模型，RNA属性系统 | 理解API设计哲学 |
| 二、对象与场景 | 场景管理、对象操作、BMesh网格 | 内容创建自动化 |
| 三、材质与纹理 | 节点材质系统、PBR自动化、程序化纹理 | 材质批量处理 |
| 四、动画系统 | 关键帧、F-Curve、驱动器、形状键 | 动画生产 |
| 五、渲染与输出 | Cycles/Eevee配置、批量渲染 | 渲染流水线 |
| 六、插件开发 | 完整插件架构、UI开发、实用工具 | 工具开发 |
| 七、AE集成 | EXR多通道、相机数据导出 | 3D合成工作流 |
| 八、性能优化 | 脚本性能、渲染优化 | 大规模生产 |

**关键技术要点**：
1. **上下文覆盖**是调用`bpy.ops`的关键，4.0+必须使用`temp_override`
2. **BMesh**是网格底层操作的推荐方式，避免触发depsgraph更新
3. **RNA属性系统**通过`bpy.props`提供严格的类型检查
4. **驱动器系统**支持复杂数学表达式，实现属性联动
5. **EXR多层渲染**是Blender→AE合成工作流的标准方案
6. **自适应采样+降噪**是Cycles性能优化的核心组合

> **集成建议**：在与AE集成场景中，推荐使用EXR多层渲染+JSON相机数据导出的组合方案，可最大化保留3D信息供后期合成使用。在批量生产场景中，结合命令行渲染和Python脚本可实现完全无人值守的渲染流水线。
