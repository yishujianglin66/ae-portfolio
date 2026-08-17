# Parent与矩阵变换调试清单

## 问题场景

物体位置异常时的系统性排查流程。基于上官婉儿发冠偏移问题的实战经验总结。

## 调试清单

### Step 1: 确认当前状态

```python
import bpy

def debug_transform_state(obj):
    """输出物体完整变换状态"""
    bpy.context.view_layer.update()
    
    print(f"\n{'='*50}")
    print(f"Object: {obj.name}")
    print(f"{'='*50}")
    
    # 基础变换
    print(f"location: {obj.location.to_tuple()}")
    print(f"rotation_euler: {obj.rotation_euler.to_tuple()}")
    print(f"scale: {obj.scale.to_tuple()}")
    
    # 世界位置
    print(f"matrix_world.translation: {obj.matrix_world.translation.to_tuple()}")
    
    # Parent信息
    if obj.parent:
        print(f"\nparent: {obj.parent.name}")
        print(f"parent_type: {obj.parent_type}")
        print(f"parent_bone: {obj.parent_bone}")
        print(f"matrix_parent_inverse: {obj.matrix_parent_inverse.to_tuple()}")
    else:
        print(f"\nparent: None")
    
    # 约束
    if obj.constraints:
        print(f"\nconstraints:")
        for c in obj.constraints:
            print(f"  {c.type}: target={c.target.name if c.target else 'None'}")
```

### Step 2: 验证Parent计算

```python
def verify_parent_calculation(child_obj):
    """验证parent变换链是否正确"""
    bpy.context.view_layer.update()
    
    if not child_obj.parent:
        print("No parent - skip verification")
        return
    
    parent = child_obj.parent
    
    # 手动计算期望的world矩阵
    if child_obj.parent_type == 'OBJECT':
        expected = parent.matrix_world @ child_obj.matrix_parent_inverse @ child_obj.matrix_basis
    elif child_obj.parent_type == 'BONE':
        pb = parent.pose.bones[child_obj.parent_bone]
        bone_world = parent.matrix_world @ pb.matrix
        from mathutils import Matrix, Vector
        tail_mat = bone_world @ Matrix.Translation(Vector((0, pb.bone.length, 0)))
        expected = tail_mat @ child_obj.matrix_parent_inverse @ child_obj.matrix_basis
    
    actual = child_obj.matrix_world
    
    # 比较
    diff_loc = (expected.translation - actual.translation).length
    print(f"Position diff: {diff_loc:.6f}")
    
    if diff_loc > 0.001:
        print(f"  Expected: {expected.translation.to_tuple()}")
        print(f"  Actual: {actual.translation.to_tuple()}")
        print(f"  [FAIL] Transform chain mismatch!")
    else:
        print(f"  [OK] Transform chain correct")
```

### Step 3: 常见问题速查

| 症状 | 可能原因 | 检查方法 |
|------|----------|----------|
| 物体在原点 | parent_inverse未设置 | 检查mpi是否为Identity |
| 物体偏移bone_length | TAIL偏移未补偿 | 检查mpi是否包含TAIL逆 |
| 物体旋转异常 | 使用了rest pose矩阵 | 应该用pose.bones[].matrix |
| 物体不跟随动画 | parent_type='OBJECT' | 改为'BONE'或用约束 |
| 物体跳跃 | 设置parent前未update | 添加view_layer.update() |
| 缩放异常 | parent有非均匀缩放 | Apply parent缩放 |

### Step 4: 发冠问题复盘

```python
# 上官婉儿发冠偏移问题的完整诊断流程

def diagnose_crown_issue(crown_obj, armature_obj):
    """发冠位置诊断"""
    bpy.context.view_layer.update()
    
    # 1. 发冠当前世界位置
    crown_pos = crown_obj.matrix_world.translation
    print(f"Crown world pos: {crown_pos.to_tuple()}")
    
    # 2. Head骨骼世界位置
    pb_head = armature_obj.pose.bones['Head']
    head_world = armature_obj.matrix_world @ pb_head.matrix
    head_pos = head_world.translation
    print(f"Head bone pos: {head_pos.to_tuple()}")
    
    # 3. Head TAIL世界位置
    from mathutils import Matrix, Vector
    tail_mat = head_world @ Matrix.Translation(Vector((0, pb_head.bone.length, 0)))
    tail_pos = tail_mat.translation
    print(f"Head TAIL pos: {tail_pos.to_tuple()}")
    
    # 4. 期望位置 vs 实际位置
    expected_offset = crown_pos - tail_pos  # 发冠相对TAIL的偏移
    print(f"Crown offset from TAIL: {expected_offset.to_tuple()}")
    
    # 5. 检查matrix_parent_inverse
    mpi = crown_obj.matrix_parent_inverse
    print(f"matrix_parent_inverse is identity: {mpi.is_identity}")
    
    # 6. 判断问题
    if mpi.is_identity:
        print("[ISSUE] mpi is identity - TAIL offset not compensated!")
    else:
        print("[OK] mpi is set")
```

## 本项目代码关联

`cel_shading.py` L945-948（诊断打印）：
```python
_crown_world_pos = _crown_part.matrix_world.translation.to_tuple()
print(">>> [v12-RIG] Crown world pos: (...)")
```

## 版本兼容性

- Blender 5.1.0 Alpha: 所有诊断方法测试通过

## 参考链接

- [Blender API: Object](https://docs.blender.org/api/current/bpy.types.Object.html)
- [Blender Manual: Transform](https://docs.blender.org/manual/en/latest/scene_layout/object/editing/transform/index.html)
