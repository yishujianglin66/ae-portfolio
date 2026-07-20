# Blender 3D建模渲染核心功能完全指南

---

## 一、Blender界面与基础操作

### 1.1 界面架构

```python
class BlenderInterface:
    MAIN_EDITOR_TYPES = {
        '3d_view': {'name': '3D视图', 'shortcut': 'Shift+F5'},
        'timeline': {'name': '时间轴', 'shortcut': 'Shift+F1'},
        'graph_editor': {'name': '图表编辑器', 'shortcut': 'Shift+F6'},
        'dopesheet': {'name': '关键帧面板', 'shortcut': 'Shift+F12'},
        'uv_editor': {'name': 'UV编辑器', 'shortcut': 'Shift+F10'},
        'texture_editor': {'name': '纹理编辑器', 'shortcut': 'Shift+F11'},
        'node_editor': {'name': '节点编辑器', 'shortcut': 'Shift+F3'},
        'outliner': {'name': '大纲视图', 'shortcut': 'Shift+F9'},
        'properties': {'name': '属性面板', 'shortcut': 'Shift+F7'},
        'console': {'name': '控制台', 'shortcut': 'Shift+F4'},
        'text_editor': {'name': '文本编辑器', 'shortcut': 'Shift+F11'}
    }
    
    MODES = {
        'object': {'name': '物体模式', 'shortcut': 'Tab'},
        'edit': {'name': '编辑模式', 'shortcut': 'Tab'},
        'sculpt': {'name': '雕刻模式', 'shortcut': 'Tab'},
        'vertex_paint': {'name': '顶点绘制', 'shortcut': 'V'},
        'weight_paint': {'name': '权重绘制', 'shortcut': 'W'},
        'texture_paint': {'name': '纹理绘制', 'shortcut': 'T'},
        'particle_edit': {'name': '粒子编辑', 'shortcut': 'P'},
        'pose': {'name': '姿态模式', 'shortcut': 'Tab'}
    }
    
    def __init__(self):
        self.current_mode = 'object'
        self.active_editor = '3d_view'
        
    def switch_mode(self, mode):
        if mode in self.MODES:
            self.current_mode = mode
            return {'status': 'success', 'mode': self.MODES[mode]['name']}
        return {'status': 'error', 'message': '无效的模式'}
        
    def set_editor(self, editor_type):
        if editor_type in self.MAIN_EDITOR_TYPES:
            self.active_editor = editor_type
            return {'status': 'success', 'editor': self.MAIN_EDITOR_TYPES[editor_type]['name']}
        return {'status': 'error', 'message': '无效的编辑器类型'}
```

### 1.2 视图导航

```python
class ViewNavigation:
    NAVIGATION_TOOLS = {
        'orbit': {'description': '轨道旋转', 'shortcut': 'Middle Mouse'},
        'pan': {'description': '平移', 'shortcut': 'Shift+Middle Mouse'},
        'zoom': {'description': '缩放', 'shortcut': 'Ctrl+Middle Mouse / Mouse Wheel'},
        'zoom_to_selection': {'description': '缩放到选区', 'shortcut': 'NumPad +'},
        'view_all': {'description': '显示全部', 'shortcut': 'NumPad 0'},
        'front_view': {'description': '前视图', 'shortcut': 'NumPad 1'},
        'side_view': {'description': '侧视图', 'shortcut': 'NumPad 3'},
        'top_view': {'description': '顶视图', 'shortcut': 'NumPad 7'},
        'perspective': {'description': '透视视图', 'shortcut': 'NumPad 5'},
        'orthographic': {'description': '正交视图', 'shortcut': 'NumPad 5'}
    }
    
    def __init__(self):
        self.view_type = 'perspective'
        self.zoom_level = 1.0
        
    def set_view(self, view_type):
        if view_type in self.NAVIGATION_TOOLS:
            self.view_type = view_type
            return {'status': 'success', 'view': self.NAVIGATION_TOOLS[view_type]['description']}
        return {'status': 'error', 'message': '无效的视图类型'}
        
    def zoom(self, factor):
        self.zoom_level *= factor
        return {'status': 'success', 'zoom_level': self.zoom_level}
```

### 1.3 对象选择与变换

```python
class ObjectManipulation:
    SELECTION_MODES = {
        'vertex': {'description': '顶点选择', 'shortcut': '1'},
        'edge': {'description': '边选择', 'shortcut': '2'},
        'face': {'description': '面选择', 'shortcut': '3'}
    }
    
    TRANSFORM_MODES = {
        'translate': {'description': '移动', 'shortcut': 'G'},
        'rotate': {'description': '旋转', 'shortcut': 'R'},
        'scale': {'description': '缩放', 'shortcut': 'S'},
        'grab': {'description': '抓取', 'shortcut': 'G'}
    }
    
    def __init__(self):
        self.selection_mode = 'vertex'
        self.selected_objects = []
        
    def select_object(self, object_name):
        if object_name not in self.selected_objects:
            self.selected_objects.append(object_name)
        return {'status': 'success', 'selected': self.selected_objects}
        
    def deselect_object(self, object_name):
        if object_name in self.selected_objects:
            self.selected_objects.remove(object_name)
        return {'status': 'success', 'selected': self.selected_objects}
        
    def clear_selection(self):
        self.selected_objects = []
        return {'status': 'success', 'selected': self.selected_objects}
        
    def transform(self, mode, values):
        if mode not in self.TRANSFORM_MODES:
            return {'status': 'error', 'message': '无效的变换模式'}
            
        return {
            'status': 'success',
            'mode': self.TRANSFORM_MODES[mode]['description'],
            'values': values
        }
```

---

## 二、3D建模核心功能

### 2.1 基础几何体创建

```python
class PrimitiveCreator:
    PRIMITIVES = {
        'cube': {'description': '立方体', 'default_size': 2},
        'sphere': {'description': '球体', 'default_size': 1},
        'cylinder': {'description': '圆柱体', 'default_size': 1},
        'cone': {'description': '圆锥体', 'default_size': 1},
        'torus': {'description': '圆环', 'default_size': 1},
        'plane': {'description': '平面', 'default_size': 2},
        'ico_sphere': {'description': '二十面体球', 'default_size': 1},
        'monkey': {'description': '猴子', 'default_size': 1},
        'circle': {'description': '圆', 'default_size': 1},
        'uv_sphere': {'description': 'UV球体', 'default_size': 1}
    }
    
    def __init__(self):
        self.objects = []
        
    def create(self, primitive_type, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
        if primitive_type not in self.PRIMITIVES:
            return {'status': 'error', 'message': '无效的几何体类型'}
            
        obj = {
            'id': f'obj_{len(self.objects) + 1}',
            'type': primitive_type,
            'name': f'{primitive_type}_{len(self.objects) + 1}',
            'location': location,
            'rotation': rotation,
            'scale': scale,
            'created_at': datetime.now().isoformat()
        }
        
        self.objects.append(obj)
        return {'status': 'success', 'object': obj}
        
    def delete(self, object_id):
        self.objects = [o for o in self.objects if o['id'] != object_id]
        return {'status': 'success'}
        
    def list_objects(self):
        return {'status': 'success', 'objects': self.objects}
```

### 2.2 编辑模式工具

```python
class EditModeTools:
    TOOLS = {
        'extrude': {'description': '挤出', 'shortcut': 'E'},
        'bevel': {'description': '倒角', 'shortcut': 'Ctrl+B'},
        'loop_cut': {'description': '环切', 'shortcut': 'Ctrl+R'},
        'knife': {'description': '切割', 'shortcut': 'K'},
        'subdivide': {'description': '细分', 'shortcut': 'W > Subdivide'},
        'merge': {'description': '合并', 'shortcut': 'M'},
        'separate': {'description': '分离', 'shortcut': 'P'},
        'bridge': {'description': '桥接', 'shortcut': 'W > Bridge Edge Loops'},
        'fill': {'description': '填充', 'shortcut': 'F'},
        'inset': {'description': '内插', 'shortcut': 'I'},
        'spin': {'description': '旋转复制', 'shortcut': 'Alt+S'}
    }
    
    def __init__(self):
        self.active_tool = None
        
    def set_tool(self, tool_name):
        if tool_name in self.TOOLS:
            self.active_tool = tool_name
            return {'status': 'success', 'tool': self.TOOLS[tool_name]['description']}
        return {'status': 'error', 'message': '无效的工具'}
        
    def apply_tool(self, parameters=None):
        if not self.active_tool:
            return {'status': 'error', 'message': '未选择工具'}
            
        return {
            'status': 'success',
            'tool': self.TOOLS[self.active_tool]['description'],
            'parameters': parameters or {}
        }
```

### 2.3 细分曲面与建模技巧

```python
class SubdivisionModeling:
    SUBDIVISION_TYPES = {
        'catmull_clark': {'description': 'Catmull-Clark', 'smoothness': 'high'},
        'simple': {'description': '简单细分', 'smoothness': 'low'}
    }
    
    def __init__(self):
        self.subdivision_type = 'catmull_clark'
        self.levels = 2
        self.crease_weight = 0.0
        
    def set_subdivision_type(self, type_name):
        if type_name in self.SUBDIVISION_TYPES:
            self.subdivision_type = type_name
            return {'status': 'success', 'type': self.SUBDIVISION_TYPES[type_name]['description']}
        return {'status': 'error', 'message': '无效的细分类型'}
        
    def set_levels(self, levels):
        if 0 <= levels <= 6:
            self.levels = levels
            return {'status': 'success', 'levels': levels}
        return {'status': 'error', 'message': '细分级别必须在0-6之间'}
        
    def apply_subdivision(self, object_name):
        return {
            'status': 'success',
            'object': object_name,
            'subdivision_type': self.subdivision_type,
            'levels': self.levels,
            'crease_weight': self.crease_weight
        }
```

---

## 三、雕刻与拓扑

### 3.1 雕刻模式基础

```python
class SculptMode:
    BRUSH_TYPES = {
        'draw': {'description': '绘制', 'action': 'adds volume'},
        'smooth': {'description': '平滑', 'action': 'smooths surface'},
        'pinch': {'description': '收缩', 'action': 'pinches vertices'},
        'grab': {'description': '抓取', 'action': 'moves vertices'},
        'inflate': {'description': '膨胀', 'action': 'inflates surface'},
        'crease': {'description': '褶皱', 'action': 'creates sharp creases'},
        'flatten': {'description': '压平', 'action': 'flattens surface'},
        'clay': {'description': '黏土', 'action': 'adds clay-like volume'},
        'scrape': {'description': '刮擦', 'action': 'scrapes surface'},
        'mask': {'description': '遮罩', 'action': 'masks area'}
    }
    
    def __init__(self):
        self.active_brush = 'draw'
        self.brush_size = 50
        self.brush_strength = 0.5
        
    def set_brush(self, brush_name):
        if brush_name in self.BRUSH_TYPES:
            self.active_brush = brush_name
            return {'status': 'success', 'brush': self.BRUSH_TYPES[brush_name]['description']}
        return {'status': 'error', 'message': '无效的画笔类型'}
        
    def set_brush_size(self, size):
        if 1 <= size <= 500:
            self.brush_size = size
            return {'status': 'success', 'brush_size': size}
        return {'status': 'error', 'message': '画笔大小必须在1-500之间'}
        
    def set_strength(self, strength):
        if 0 <= strength <= 1:
            self.brush_strength = strength
            return {'status': 'success', 'strength': strength}
        return {'status': 'error', 'message': '强度必须在0-1之间'}
```

### 3.2 拓扑重构

```python
class RetopologyTools:
    RETOPO_TOOLS = {
        'retopo_project': {'description': '投影重构', 'shortcut': 'Shift+V'},
        'knife_project': {'description': '刀投影', 'shortcut': 'K > Knife Project'},
        'shrinkwrap': {'description': '收缩包裹', 'modifier': 'Shrinkwrap'},
        'decimate': {'description': '简化', 'modifier': 'Decimate'},
        'remesh': {'description': '重网格', 'modifier': 'Remesh'}
    }
    
    def __init__(self):
        self.target_poly_count = 10000
        
    def set_target_poly_count(self, count):
        if count > 0:
            self.target_poly_count = count
            return {'status': 'success', 'poly_count': count}
        return {'status': 'error', 'message': '多边形数量必须大于0'}
        
    def apply_retopology(self, object_name, method='retopo_project'):
        if method not in self.RETOPO_TOOLS:
            return {'status': 'error', 'message': '无效的重构方法'}
            
        return {
            'status': 'success',
            'object': object_name,
            'method': self.RETOPO_TOOLS[method]['description'],
            'target_poly_count': self.target_poly_count
        }
```

---

## 四、材质与渲染

### 4.1 材质系统

```python
class MaterialSystem:
    SHADER_TYPES = {
        'principled_bsdf': {'description': '原理化BSDF', 'complexity': 'high'},
        'diffuse': {'description': '漫反射', 'complexity': 'low'},
        'glossy': {'description': '光泽', 'complexity': 'low'},
        'emission': {'description': '自发光', 'complexity': 'low'},
        'transparent': {'description': '透明', 'complexity': 'low'},
        'glass': {'description': '玻璃', 'complexity': 'medium'},
        'subsurface_scattering': {'description': '次表面散射', 'complexity': 'high'},
        'metal': {'description': '金属', 'complexity': 'medium'}
    }
    
    def __init__(self):
        self.materials = []
        self.active_material = None
        
    def create_material(self, name, shader_type='principled_bsdf'):
        if shader_type not in self.SHADER_TYPES:
            return {'status': 'error', 'message': '无效的着色器类型'}
            
        material = {
            'id': f'mat_{len(self.materials) + 1}',
            'name': name,
            'shader_type': shader_type,
            'properties': {},
            'created_at': datetime.now().isoformat()
        }
        
        self.materials.append(material)
        self.active_material = material['id']
        return {'status': 'success', 'material': material}
        
    def set_property(self, property_name, value):
        if not self.active_material:
            return {'status': 'error', 'message': '未选择材质'}
            
        material = next((m for m in self.materials if m['id'] == self.active_material), None)
        if material:
            material['properties'][property_name] = value
            return {'status': 'success', 'property': {property_name: value}}
        return {'status': 'error', 'message': '材质不存在'}
        
    def assign_material(self, object_name, material_id):
        return {
            'status': 'success',
            'object': object_name,
            'material_id': material_id
        }
```

### 4.2 纹理系统

```python
class TextureSystem:
    TEXTURE_TYPES = {
        'image': {'description': '图像纹理', 'source': 'image file'},
        'noise': {'description': '噪点纹理', 'source': 'procedural'},
        'voronoi': {'description': '沃罗诺伊纹理', 'source': 'procedural'},
        'musgrave': {'description': '马斯格雷夫纹理', 'source': 'procedural'},
        'gradient': {'description': '渐变纹理', 'source': 'procedural'},
        'clouds': {'description': '云纹理', 'source': 'procedural'},
        'wood': {'description': '木纹纹理', 'source': 'procedural'},
        'bricks': {'description': '砖块纹理', 'source': 'procedural'}
    }
    
    MAPPING_MODES = {
        'uv': {'description': 'UV映射'},
        'generated': {'description': '生成映射'},
        'normal': {'description': '法线映射'},
        'object': {'description': '物体映射'},
        'camera': {'description': '相机映射'}
    }
    
    def __init__(self):
        self.textures = []
        
    def create_texture(self, name, texture_type='image'):
        if texture_type not in self.TEXTURE_TYPES:
            return {'status': 'error', 'message': '无效的纹理类型'}
            
        texture = {
            'id': f'tex_{len(self.textures) + 1}',
            'name': name,
            'type': texture_type,
            'mapping': 'uv',
            'properties': {},
            'created_at': datetime.now().isoformat()
        }
        
        self.textures.append(texture)
        return {'status': 'success', 'texture': texture}
        
    def set_mapping(self, texture_id, mapping_mode):
        if mapping_mode not in self.MAPPING_MODES:
            return {'status': 'error', 'message': '无效的映射模式'}
            
        texture = next((t for t in self.textures if t['id'] == texture_id), None)
        if texture:
            texture['mapping'] = mapping_mode
            return {'status': 'success', 'mapping': mapping_mode}
        return {'status': 'error', 'message': '纹理不存在'}
```

### 4.3 渲染引擎设置

```python
class RenderEngine:
    ENGINES = {
        'cycles': {'description': 'Cycles', 'type': 'Path Tracing', 'features': ['GPU Acceleration', 'Denoiser', 'Subsurface Scattering']},
        'eevee': {'description': 'Eevee', 'type': 'Real-time', 'features': ['RTX Support', 'Screen Space Effects', 'Bloom', 'SSAO']},
        'workbench': {'description': 'Workbench', 'type': 'Interactive', 'features': ['Wireframe', 'Solid', 'Flat Shading', 'Matcap']}
    }
    
    def __init__(self):
        self.engine = 'cycles'
        self.resolution = '1080p'
        self.fps = 24
        self.samples = 128
        
    def set_engine(self, engine_name):
        if engine_name in self.ENGINES:
            self.engine = engine_name
            return {'status': 'success', 'engine': self.ENGINES[engine_name]}
        return {'status': 'error', 'message': '无效的渲染引擎'}
        
    def set_resolution(self, resolution):
        resolutions = {'720p': (1280, 720), '1080p': (1920, 1080), '2K': (2560, 1440), '4K': (3840, 2160)}
        if resolution in resolutions:
            self.resolution = resolution
            return {'status': 'success', 'dimensions': resolutions[resolution]}
        return {'status': 'error', 'message': '无效的分辨率'}
        
    def set_samples(self, samples):
        if samples > 0:
            self.samples = samples
            return {'status': 'success', 'samples': samples}
        return {'status': 'error', 'message': '采样数必须大于0'}
        
    def render(self, output_path):
        return {
            'status': 'success',
            'engine': self.engine,
            'resolution': self.resolution,
            'samples': self.samples,
            'output': output_path
        }
```

---

## 五、动画与绑定

### 5.1 关键帧动画

```python
class KeyframeAnimation:
    INTERPOLATION_TYPES = {
        'linear': {'description': '线性', 'effect': 'constant speed'},
        'bezier': {'description': '贝塞尔', 'effect': 'smooth transitions'},
        'ease_in': {'description': '缓入', 'effect': 'slow start'},
        'ease_out': {'description': '缓出', 'effect': 'slow end'},
        'ease_in_out': {'description': '缓入缓出', 'effect': 'smooth start and end'},
        'step': {'description': '步进', 'effect': 'instant change'}
    }
    
    def __init__(self):
        self.keyframes = []
        self.interpolation = 'bezier'
        
    def add_keyframe(self, frame, property_name, value):
        keyframe = {
            'id': f'kf_{len(self.keyframes) + 1}',
            'frame': frame,
            'property': property_name,
            'value': value,
            'interpolation': self.interpolation,
            'created_at': datetime.now().isoformat()
        }
        
        self.keyframes.append(keyframe)
        self.keyframes.sort(key=lambda k: k['frame'])
        return {'status': 'success', 'keyframe': keyframe}
        
    def set_interpolation(self, interpolation_type):
        if interpolation_type in self.INTERPOLATION_TYPES:
            self.interpolation = interpolation_type
            return {'status': 'success', 'interpolation': self.INTERPOLATION_TYPES[interpolation_type]['description']}
        return {'status': 'error', 'message': '无效的插值类型'}
        
    def get_keyframes_for_property(self, property_name):
        return [k for k in self.keyframes if k['property'] == property_name]
```

### 5.2 骨骼绑定

```python
class RiggingSystem:
    RIG_TYPES = {
        'armature': {'description': '骨架', 'usage': 'character animation'},
        'ik': {'description': '反向运动学', 'usage': 'limb animation'},
        'fk': {'description': '正向运动学', 'usage': 'simple animation'},
        'constraints': {'description': '约束', 'usage': 'automatic animation'}
    }
    
    def __init__(self):
        self.bones = []
        self.constraints = []
        
    def create_armature(self, name):
        armature = {
            'id': f'arm_{len(self.bones) + 1}',
            'name': name,
            'bones': [],
            'created_at': datetime.now().isoformat()
        }
        return {'status': 'success', 'armature': armature}
        
    def add_bone(self, armature_id, bone_name, parent_bone=None):
        bone = {
            'id': f'bone_{len(self.bones) + 1}',
            'name': bone_name,
            'parent': parent_bone,
            'location': (0, 0, 0),
            'rotation': (0, 0, 0)
        }
        
        self.bones.append(bone)
        return {'status': 'success', 'bone': bone}
        
    def add_constraint(self, bone_id, constraint_type, target=None):
        constraints = ['ik', 'fk', 'copy_location', 'copy_rotation', 'follow_path']
        if constraint_type not in constraints:
            return {'status': 'error', 'message': '无效的约束类型'}
            
        constraint = {
            'id': f'const_{len(self.constraints) + 1}',
            'bone_id': bone_id,
            'type': constraint_type,
            'target': target
        }
        
        self.constraints.append(constraint)
        return {'status': 'success', 'constraint': constraint}
```

---

## 六、合成与后期

### 6.1 合成节点系统

```python
class CompositingSystem:
    NODE_TYPES = {
        'render_layers': {'description': '渲染层', 'inputs': [], 'outputs': ['Image', 'Depth', 'Normal']},
        'alpha_over': {'description': 'Alpha叠加', 'inputs': ['Image', 'Image'], 'outputs': ['Image']},
        'mix': {'description': '混合', 'inputs': ['Image', 'Image'], 'outputs': ['Image']},
        'color_correction': {'description': '颜色校正', 'inputs': ['Image'], 'outputs': ['Image']},
        'blur': {'description': '模糊', 'inputs': ['Image'], 'outputs': ['Image']},
        'glow': {'description': '发光', 'inputs': ['Image'], 'outputs': ['Image']},
        'vignette': {'description': '暗角', 'inputs': ['Image'], 'outputs': ['Image']},
        'depth_of_field': {'description': '景深', 'inputs': ['Image', 'Depth'], 'outputs': ['Image']},
        'denoise': {'description': '降噪', 'inputs': ['Image'], 'outputs': ['Image']},
        'file_output': {'description': '文件输出', 'inputs': ['Image'], 'outputs': []}
    }
    
    def __init__(self):
        self.nodes = []
        self.connections = []
        
    def create_node(self, node_type, position=(0, 0)):
        if node_type not in self.NODE_TYPES:
            return {'status': 'error', 'message': '无效的节点类型'}
            
        node = {
            'id': f'node_{len(self.nodes) + 1}',
            'type': node_type,
            'name': self.NODE_TYPES[node_type]['description'],
            'position': position,
            'properties': {},
            'created_at': datetime.now().isoformat()
        }
        
        self.nodes.append(node)
        return {'status': 'success', 'node': node}
        
    def connect_nodes(self, from_node_id, from_output, to_node_id, to_input):
        connection = {
            'id': f'conn_{len(self.connections) + 1}',
            'from_node': from_node_id,
            'from_output': from_output,
            'to_node': to_node_id,
            'to_input': to_input
        }
        
        self.connections.append(connection)
        return {'status': 'success', 'connection': connection}
        
    def set_node_property(self, node_id, property_name, value):
        node = next((n for n in self.nodes if n['id'] == node_id), None)
        if node:
            node['properties'][property_name] = value
            return {'status': 'success', 'property': {property_name: value}}
        return {'status': 'error', 'message': '节点不存在'}
```

### 6.2 后期效果

```python
class PostProcessingEffects:
    EFFECTS = {
        'bloom': {'description': '光晕', 'parameters': ['threshold', 'strength', 'radius']},
        'ssao': {'description': '屏幕空间环境光遮蔽', 'parameters': ['radius', 'strength', 'samples']},
        'motion_blur': {'description': '运动模糊', 'parameters': ['shutter', 'samples']},
        'depth_of_field': {'description': '景深', 'parameters': ['focal_length', 'aperture', 'focus_distance']},
        'color_grading': {'description': '颜色分级', 'parameters': ['contrast', 'saturation', 'brightness', 'gamma']},
        'chromatic_aberration': {'description': '色差', 'parameters': ['strength']},
        'vignette': {'description': '暗角', 'parameters': ['size', 'strength']},
        'film_grain': {'description': '胶片颗粒', 'parameters': ['strength', 'size']}
    }
    
    def __init__(self):
        self.active_effects = {}
        
    def enable_effect(self, effect_name):
        if effect_name not in self.EFFECTS:
            return {'status': 'error', 'message': '无效的效果'}
            
        self.active_effects[effect_name] = {}
        return {'status': 'success', 'effect': self.EFFECTS[effect_name]['description']}
        
    def disable_effect(self, effect_name):
        if effect_name in self.active_effects:
            del self.active_effects[effect_name]
            return {'status': 'success'}
        return {'status': 'error', 'message': '效果未启用'}
        
    def set_effect_parameter(self, effect_name, parameter, value):
        if effect_name not in self.active_effects:
            return {'status': 'error', 'message': '效果未启用'}
            
        if parameter not in self.EFFECTS[effect_name]['parameters']:
            return {'status': 'error', 'message': '无效的参数'}
            
        self.active_effects[effect_name][parameter] = value
        return {'status': 'success', 'parameter': {parameter: value}}
```

---

## 七、Python API自动化

### 7.1 基础API操作

```python
class BlenderPythonAPI:
    def __init__(self):
        self.objects = []
        self.materials = []
        
    def create_cube(self, name='Cube', location=(0, 0, 0), scale=(1, 1, 1)):
        obj = {
            'type': 'cube',
            'name': name,
            'location': location,
            'scale': scale,
            'vertices': 8,
            'faces': 6
        }
        self.objects.append(obj)
        return {'status': 'success', 'object': obj}
        
    def create_material(self, name='Material'):
        material = {
            'name': name,
            'shader': 'Principled BSDF',
            'properties': {
                'Base Color': (1, 1, 1, 1),
                'Metallic': 0.0,
                'Roughness': 0.5
            }
        }
        self.materials.append(material)
        return {'status': 'success', 'material': material}
        
    def assign_material(self, object_name, material_name):
        obj = next((o for o in self.objects if o['name'] == object_name), None)
        mat = next((m for m in self.materials if m['name'] == material_name), None)
        
        if obj and mat:
            obj['material'] = material_name
            return {'status': 'success', 'object': obj}
        return {'status': 'error', 'message': '对象或材质不存在'}
        
    def set_location(self, object_name, location):
        obj = next((o for o in self.objects if o['name'] == object_name), None)
        if obj:
            obj['location'] = location
            return {'status': 'success', 'location': location}
        return {'status': 'error', 'message': '对象不存在'}
        
    def set_keyframe(self, object_name, property_name, frame, value):
        obj = next((o for o in self.objects if o['name'] == object_name), None)
        if obj:
            if 'keyframes' not in obj:
                obj['keyframes'] = {}
            if property_name not in obj['keyframes']:
                obj['keyframes'][property_name] = []
            
            obj['keyframes'][property_name].append({
                'frame': frame,
                'value': value
            })
            
            return {'status': 'success', 'keyframe': {'frame': frame, 'value': value}}
        return {'status': 'error', 'message': '对象不存在'}
```

### 7.2 场景管理

```python
class SceneManager:
    def __init__(self):
        self.scenes = []
        self.active_scene = None
        
    def create_scene(self, name='Scene'):
        scene = {
            'id': f'scene_{len(self.scenes) + 1}',
            'name': name,
            'objects': [],
            'camera': None,
            'lighting': [],
            'render_settings': {
                'resolution': '1080p',
                'fps': 24,
                'engine': 'cycles',
                'samples': 128
            },
            'created_at': datetime.now().isoformat()
        }
        
        self.scenes.append(scene)
        self.active_scene = scene['id']
        return {'status': 'success', 'scene': scene}
        
    def add_object(self, scene_id, obj):
        scene = next((s for s in self.scenes if s['id'] == scene_id), None)
        if scene:
            scene['objects'].append(obj)
            return {'status': 'success', 'scene': scene}
        return {'status': 'error', 'message': '场景不存在'}
        
    def set_camera(self, scene_id, camera_obj):
        scene = next((s for s in self.scenes if s['id'] == scene_id), None)
        if scene:
            scene['camera'] = camera_obj
            return {'status': 'success', 'camera': camera_obj}
        return {'status': 'error', 'message': '场景不存在'}
        
    def add_lighting(self, scene_id, light_obj):
        scene = next((s for s in self.scenes if s['id'] == scene_id), None)
        if scene:
            scene['lighting'].append(light_obj)
            return {'status': 'success', 'lighting': scene['lighting']}
        return {'status': 'error', 'message': '场景不存在'}
```

---

## 八、渲染输出与优化

### 8.1 输出设置

```python
class OutputSettings:
    FORMATS = {
        'png': {'description': 'PNG', 'format': 'image', 'bit_depth': '8/16/32 bit'},
        'jpg': {'description': 'JPEG', 'format': 'image', 'quality': '0-100'},
        'exr': {'description': 'EXR', 'format': 'image', 'bit_depth': '32 bit float', 'features': ['layers', 'metadata']},
        'tiff': {'description': 'TIFF', 'format': 'image', 'bit_depth': '8/16/32 bit'},
        'mp4': {'description': 'MP4', 'format': 'video', 'codec': 'H.264'},
        'mov': {'description': 'MOV', 'format': 'video', 'codec': 'ProRes/H.264'},
        'webm': {'description': 'WebM', 'format': 'video', 'codec': 'VP9'},
        'avi': {'description': 'AVI', 'format': 'video', 'codec': 'various'}
    }
    
    def __init__(self):
        self.format = 'png'
        self.resolution = '1080p'
        self.output_path = '//render_output/'
        self.file_format = 'Image Sequence'
        self.quality = 100
        
    def set_format(self, format_name):
        if format_name in self.FORMATS:
            self.format = format_name
            return {'status': 'success', 'format': self.FORMATS[format_name]}
        return {'status': 'error', 'message': '无效的格式'}
        
    def set_output_path(self, path):
        self.output_path = path
        return {'status': 'success', 'path': path}
        
    def set_quality(self, quality):
        if 0 <= quality <= 100:
            self.quality = quality
            return {'status': 'success', 'quality': quality}
        return {'status': 'error', 'message': '质量必须在0-100之间'}
```

### 8.2 性能优化

```python
class PerformanceOptimizer:
    OPTIMIZATION_SETTINGS = {
        'viewport': {
            'options': ['subdivision_levels', 'texture_resolution', 'shader_simplify'],
            'description': '视口优化'
        },
        'render': {
            'options': ['samples', 'denoising', 'tile_size'],
            'description': '渲染优化'
        },
        'geometry': {
            'options': ['decimation', 'level_of_detail', 'instancing'],
            'description': '几何体优化'
        }
    }
    
    def __init__(self):
        self.settings = {}
        
    def optimize_viewport(self, subdivision_levels=1, texture_resolution='half', shader_simplify=True):
        self.settings['viewport'] = {
            'subdivision_levels': subdivision_levels,
            'texture_resolution': texture_resolution,
            'shader_simplify': shader_simplify
        }
        return {'status': 'success', 'settings': self.settings['viewport']}
        
    def optimize_render(self, samples=64, denoising=True, tile_size='256x256'):
        self.settings['render'] = {
            'samples': samples,
            'denoising': denoising,
            'tile_size': tile_size
        }
        return {'status': 'success', 'settings': self.settings['render']}
        
    def optimize_geometry(self, decimation_ratio=0.5, lod_enabled=True, instancing=True):
        self.settings['geometry'] = {
            'decimation_ratio': decimation_ratio,
            'lod_enabled': lod_enabled,
            'instancing': instancing
        }
        return {'status': 'success', 'settings': self.settings['geometry']}
```

---

## 九、完整工作流示例

```python
class BlenderWorkflowExample:
    def __init__(self):
        self.scene_manager = SceneManager()
        self.api = BlenderPythonAPI()
        self.material_system = MaterialSystem()
        self.render_engine = RenderEngine()
        
    def create_puppet_scene(self):
        print('=== 创建木偶场景 ===')
        
        scene = self.scene_manager.create_scene('PuppetScene')
        print(f'场景创建成功: {scene["scene"]["name"]}')
        
        puppet_body = self.api.create_cube('PuppetBody', (0, 0, 1), (0.8, 1.2, 0.4))
        print(f'木偶身体创建成功')
        
        puppet_head = self.api.create_cube('PuppetHead', (0, 0, 2.2), (0.6, 0.6, 0.6))
        print(f'木偶头部创建成功')
        
        wood_material = self.material_system.create_material('WoodMaterial', 'principled_bsdf')
        self.material_system.set_property('Base Color', (0.6, 0.4, 0.2, 1))
        self.material_system.set_property('Roughness', 0.7)
        self.material_system.set_property('Metallic', 0.1)
        print(f'木质材质创建成功')
        
        self.api.assign_material('PuppetBody', 'WoodMaterial')
        self.api.assign_material('PuppetHead', 'WoodMaterial')
        print(f'材质分配成功')
        
        self.api.set_keyframe('PuppetHead', 'rotation_euler', 1, (0, 0, 0))
        self.api.set_keyframe('PuppetHead', 'rotation_euler', 25, (0, 0.5, 0))
        self.api.set_keyframe('PuppetHead', 'rotation_euler', 50, (0, 0, 0))
        print(f'动画关键帧设置成功')
        
        self.render_engine.set_engine('cycles')
        self.render_engine.set_resolution('1080p')
        self.render_engine.set_samples(128)
        print(f'渲染设置完成')
        
        return {
            'status': 'success',
            'scene': scene['scene'],
            'objects': [puppet_body['object'], puppet_head['object']],
            'material': wood_material['material'],
            'render_settings': {
                'engine': 'cycles',
                'resolution': '1080p',
                'samples': 128
            }
        }

if __name__ == '__main__':
    import datetime
    
    workflow = BlenderWorkflowExample()
    result = workflow.create_puppet_scene()
    
    print(f'\n=== 工作流完成 ===')
    print(f'状态: {result["status"]}')
    print(f'场景名称: {result["scene"]["name"]}')
    print(f'对象数量: {len(result["objects"])}')
    print(f'渲染引擎: {result["render_settings"]["engine"]}')
```

---

## 附录：快捷键速查表

```python
class ShortcutReference:
    SHORTCUTS = {
        'navigation': {
            'Middle Mouse': '旋转视图',
            'Shift+Middle Mouse': '平移视图',
            'Ctrl+Middle Mouse': '缩放视图',
            'NumPad 0': '相机视图',
            'NumPad 1': '前视图',
            'NumPad 3': '侧视图',
            'NumPad 7': '顶视图',
            'NumPad 5': '透视/正交切换'
        },
        'selection': {
            'RMB': '选择对象',
            'Shift+RMB': '添加选择',
            'Ctrl+RMB': '移除选择',
            'A': '全选/取消全选',
            'L': '选择相连元素'
        },
        'transform': {
            'G': '移动',
            'R': '旋转',
            'S': '缩放',
            'X/Y/Z': '约束轴',
            'Ctrl': '精确变换'
        },
        'modes': {
            'Tab': '物体/编辑模式切换',
            'V': '顶点绘制',
            'W': '权重绘制',
            'T': '纹理绘制',
            'P': '粒子编辑'
        },
        'file': {
            'Ctrl+S': '保存',
            'Ctrl+O': '打开',
            'Ctrl+N': '新建',
            'F12': '渲染图像',
            'Ctrl+F12': '渲染动画'
        }
    }
    
    def get_shortcuts(self, category=None):
        if category and category in self.SHORTCUTS:
            return {'status': 'success', 'category': category, 'shortcuts': self.SHORTCUTS[category]}
        return {'status': 'success', 'shortcuts': self.SHORTCUTS}
        
    def search_shortcut(self, description):
        results = []
        for category, shortcuts in self.SHORTCUTS.items():
            for shortcut, desc in shortcuts.items():
                if description.lower() in desc.lower():
                    results.append({'category': category, 'shortcut': shortcut, 'description': desc})
                    
        if results:
            return {'status': 'success', 'results': results}
        return {'status': 'error', 'message': '未找到匹配的快捷键'}
```
