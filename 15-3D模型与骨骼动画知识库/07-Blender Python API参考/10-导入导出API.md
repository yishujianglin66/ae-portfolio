# 导入导出API

## 问题场景

Blender支持多种3D格式的导入导出：FBX、OBJ、GLTF、Alembic等。不同格式有不同的参数设置，导入后的数据结构也不同。三渲二管线主要使用FBX导入。

## 核心原理

### FBX导入

```python
import bpy

# 基本导入
bpy.ops.import_scene.fbx(filepath="/path/to/model.fbx")

# 完整参数
bpy.ops.import_scene.fbx(
    filepath="/path/to/model.fbx",
    
    # 变换
    use_manual_orientation=False,  # 手动坐标轴
    axis_forward='-Z',             # 前方轴
    axis_up='Y',                   # 上方轴
    use_space_transform=True,      # 空间变换
    global_scale=1.0,              # 全局缩放
    
    # 骨骼
    use_anim=False,                # 导入动画
    ignore_leaf_bones=True,        # 忽略叶骨骼
    automatic_bone_orientation=True,  # 自动骨骼朝向
    primary_bone_axis='Y',         # 主骨骼轴
    secondary_bone_axis='X',       # 次骨骼轴
    
    # 网格
    use_mesh_edges=True,           # 导入边
    use_mesh_modifiers=True,       # 应用修改器
    
    # 材质
    use_custom_normals=True,       # 自定义法线
    use_image_search=True,         # 搜索贴图
    
    # 其他
    bake_space_transform=False,    # 烘焙空间变换
    use_prepost_rot=True,          # 预/后旋转
)
```

### FBX导出

```python
bpy.ops.export_scene.fbx(
    filepath="/path/to/output.fbx",
    
    # 选择
    use_selection=True,            # 只导出选中
    use_visible=True,              # 只导出可见
    
    # 对象类型
    object_types={'MESH', 'ARMATURE', 'EMPTY'},
    
    # 变换
    global_scale=1.0,
    axis_forward='-Z',
    axis_up='Y',
    bake_space_transform=True,
    
    # 动画
    bake_anim=True,
    bake_anim_use_all_actions=False,
    bake_anim_use_nla_strips=False,
    
    # 网格
    use_mesh_modifiers=True,
    mesh_smooth_type='FACE',  # OFF/FACE/EDGE
    
    # 骨骼
    add_leaf_bones=False,
    armature_nodetype='NULL',
)
```

### OBJ导入（Blender 4.0+新API）

```python
# Blender 4.0+ 使用新的OBJ导入器
bpy.ops.wm.obj_import(
    filepath="/path/to/model.obj",
    
    # 变换
    forward_axis='NEGATIVE_Z',
    up_axis='Y',
    global_scale=1.0,
    
    # 选项
    use_split_objects=True,
    use_split_groups=True,
    import_vertex_groups=True,
    validate_meshes=False,
)

# 旧版API（Blender 3.x）
# bpy.ops.import_scene.obj(filepath=...)  # 已废弃
```

### GLTF/GLB导入导出

```python
# 导入
bpy.ops.import_scene.gltf(
    filepath="/path/to/model.glb",
    merge_vertices=True,
    import_shading='NORMALS',
)

# 导出
bpy.ops.export_scene.gltf(
    filepath="/path/to/output.glb",
    export_format='GLB',  # GLB/GLTF/GLTF_SEPARATE
    use_selection=True,
    export_animations=True,
    export_skins=True,
)
```

### Alembic导入导出

```python
# 导入（缓存动画）
bpy.ops.wm.alembic_import(
    filepath="/path/to/cache.abc",
    as_background_job=False,
)

# 导出
bpy.ops.wm.alembic_export(
    filepath="/path/to/output.abc",
    start=1,
    end=100,
    selected=True,
)
```

### 导入后处理

```python
def post_import_cleanup():
    """导入后清理"""
    # 1. 查找导入的对象
    imported = bpy.context.selected_objects  # 导入时自动选中
    
    # 2. 按类型分类
    meshes = [o for o in imported if o.type == 'MESH']
    armatures = [o for o in imported if o.type == 'ARMATURE']
    empties = [o for o in imported if o.type == 'EMPTY']
    
    print(f"Imported: {len(meshes)} meshes, "
          f"{len(armatures)} armatures, {len(empties)} empties")
    
    # 3. 清理空物体（FBX常导入无用的Empty）
    for empty in empties:
        if len(empty.children) == 0:
            bpy.data.objects.remove(empty)
    
    # 4. 应用缩放（FBX可能有非1缩放）
    for obj in meshes:
        if obj.scale != Vector((1, 1, 1)):
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(scale=True)
    
    return meshes, armatures
```

### 纹理路径处理

```python
def fix_texture_paths(search_dirs):
    """修复导入后的纹理路径"""
    import os
    
    for img in bpy.data.images:
        if img.source != 'FILE':
            continue
        
        # 检查路径是否有效
        filepath = bpy.path.abspath(img.filepath)
        if os.path.exists(filepath):
            continue
        
        # 搜索纹理
        filename = os.path.basename(filepath)
        for search_dir in search_dirs:
            candidate = os.path.join(search_dir, filename)
            if os.path.exists(candidate):
                img.filepath = candidate
                print(f"Fixed: {img.name} -> {candidate}")
                break
        else:
            print(f"[WARN] Texture not found: {filename}")
```

### 格式对比

| 格式 | 骨骼 | 动画 | 材质 | 推荐用途 |
|------|------|------|------|----------|
| FBX | ✓ | ✓ | 部分 | 游戏资产、角色 |
| OBJ | ✗ | ✗ | 基础 | 静态网格 |
| GLTF | ✓ | ✓ | PBR | Web、实时渲染 |
| Alembic | ✓ | ✓(缓存) | ✗ | VFX、动画缓存 |
| USD | ✓ | ✓ | PBR | 电影、协作 |

## 常见陷阱

### 陷阱1：FBX缩放问题
```python
# 3dsMax导出的FBX可能有100倍缩放
# 解决：导入时global_scale=0.01
# 或导入后应用缩放
```

### 陷阱2：坐标系差异
```python
# 3dsMax: Z-up, Y-forward
# Blender: Z-up, -Y-forward（默认）
# Maya: Y-up
# 解决：调整axis_forward/axis_up参数
```

### 陷阱3：OBJ导入API变更
```python
# Blender 4.0+ 使用 wm.obj_import
# 旧版 import_scene.obj 已废弃
# 检查版本：
if bpy.app.version >= (4, 0, 0):
    bpy.ops.wm.obj_import(filepath=...)
else:
    bpy.ops.import_scene.obj(filepath=...)
```

## 本项目代码关联

`cel_shading.py` L50-100：
- FBX导入配置
- ignore_leaf_bones=True
- use_anim=False（静态网格）

## 版本兼容性

- Blender 4.0+: OBJ导入API变更
- Blender 4.2+: FBX导入器更新
- Blender 5.1.0 Alpha: 导入API稳定

## 参考链接

- [Blender Manual: FBX](https://docs.blender.org/manual/en/latest/addons/import_export/scene_fbx.html)
- [Blender Manual: Import/Export](https://docs.blender.org/manual/en/latest/addons/import_export/index.html)
