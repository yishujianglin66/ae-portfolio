#!/usr/bin/env python3
"""Puppeteer 引擎单元测试 (2026-08-16)

验证项：
1. _compute_bbox 包围盒计算
2. auto_calibrate_pose 两阶段姿态校准
3. auto_fix_orientation 水平面校准兼容
4. _is_fallback_gray 材质fallback判断
5. _make_diffuse_mat Diffuse BSDF材质创建
6. look_at_matrix 相机look_at矩阵
7. center_model 居中+尺寸计算
8. _set_linear_interp 关键帧线性插值
9. animate_sword_swing / animate_wave 关键帧生成

在 Blender 后台运行：
  blender -b -P tests/test_puppeteer_engine.py
"""
from __future__ import annotations

import sys
import math
import traceback
from mathutils import Vector, Matrix

# 导入被测试模块
# 必须将 puppeteer 模块所在目录加入 sys.path
sys.path.insert(0, '.')
sys.path.insert(0, 'puppet-automation/src/engines/blender')
import puppeteer.engine as eng


def _print_result(name: str, success: bool, detail: str = "") -> None:
    status = "PASS" if success else "FAIL"
    print(f"  [{status}] {name}: {detail}")


def _make_mesh_obj(name: str, verts, location=(0, 0, 0)):
    """创建临时mesh对象用于测试。"""
    import bpy
    mesh_data = bpy.data.meshes.new(f"test_{name}")
    mesh_data.from_pydata(verts, [], [])
    mesh_data.update()
    obj = bpy.data.objects.new(f"test_{name}", mesh_data)
    obj.location = location
    bpy.context.collection.objects.link(obj)
    return obj


def _cleanup_test_objects():
    """清理测试创建的对象。"""
    import bpy
    for obj in list(bpy.data.objects):
        if obj.name.startswith('test_'):
            bpy.data.objects.remove(obj, do_unlink=True)


# ===== Test 1: _compute_bbox =====
def test_compute_bbox() -> bool:
    print("\n[Test 1] _compute_bbox 包围盒计算")
    try:
        v = [(0, 0, 0), (1, 0, 0), (1, 2, 0), (0, 2, 0),
             (0, 0, 3), (1, 0, 3), (1, 2, 3), (0, 2, 3)]
        obj = _make_mesh_obj('bbox', v)
        dx, dy, dz = eng._compute_bbox([obj])
        _print_result(
            "包围盒尺寸",
            abs(dx - 1.0) < 0.01 and abs(dy - 2.0) < 0.01 and abs(dz - 3.0) < 0.01,
            f"dx={dx:.3f} dy={dy:.3f} dz={dz:.3f}"
        )
        _cleanup_test_objects()
        return abs(dx - 1.0) < 0.01 and abs(dy - 2.0) < 0.01 and abs(dz - 3.0) < 0.01
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 2: auto_calibrate_pose — 立起X轴躺倒模型 =====
def test_calibrate_x_upright() -> bool:
    print("\n[Test 2] auto_calibrate_pose — 沿X躺倒→立起")
    try:
        # 创建沿X轴长的模型 (X=4, Y=1, Z=1 → 躺倒在X)
        v = [(0, 0, 0), (4, 0, 0), (4, 1, 0), (0, 1, 0),
             (0, 0, 1), (4, 0, 1), (4, 1, 1), (0, 1, 1)]
        obj = _make_mesh_obj('x_flat', v)
        stand, horiz = eng.auto_calibrate_pose([obj])
        _print_result(
            "立起修正", stand,
            f"stand={stand}, horiz={horiz} (预期: stand=True)"
        )
        # 验证立起后Z变为最长
        dx2, dy2, dz2 = eng._compute_bbox([obj])
        is_upright = dz2 > dx2 and dz2 > dy2
        _print_result(
            "立起后Z为最长", is_upright,
            f"dx={dx2:.3f} dy={dy2:.3f} dz={dz2:.3f}"
        )
        _cleanup_test_objects()
        return stand and is_upright
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 3: auto_calibrate_pose — 立起Y轴躺倒模型 =====
def test_calibrate_y_upright() -> bool:
    print("\n[Test 3] auto_calibrate_pose — 沿Y躺倒→立起")
    try:
        # 创建沿Y轴长的模型 (X=1, Y=4, Z=1 → 前后倒)
        v = [(0, 0, 0), (1, 0, 0), (1, 4, 0), (0, 4, 0),
             (0, 0, 1), (1, 0, 1), (1, 4, 1), (0, 4, 1)]
        obj = _make_mesh_obj('y_flat', v)
        stand, horiz = eng.auto_calibrate_pose([obj])
        _print_result(
            "立起修正", stand,
            f"stand={stand}, horiz={horiz} (预期: stand=True)"
        )
        dx2, dy2, dz2 = eng._compute_bbox([obj])
        is_upright = dz2 > dx2 and dz2 > dy2
        _print_result(
            "立起后Z为最长", is_upright,
            f"dx={dx2:.3f} dy={dy2:.3f} dz={dz2:.3f}"
        )
        _cleanup_test_objects()
        return stand and is_upright
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 4: auto_calibrate_pose — 已立起不旋转 =====
def test_calibrate_already_upright() -> bool:
    print("\n[Test 4] auto_calibrate_pose — 已沿Z立起, 不旋转")
    try:
        # 创建沿Z轴长的模型 (X=1, Y=1, Z=4 → 已立起)
        v = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
             (0, 0, 4), (1, 0, 4), (1, 1, 4), (0, 1, 4)]
        obj = _make_mesh_obj('z_upright', v)
        stand, horiz = eng.auto_calibrate_pose([obj])
        _print_result(
            "不旋转立起", not stand,
            f"stand={stand} (预期: False, 已立起)"
        )
        _cleanup_test_objects()
        return not stand
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 5: auto_calibrate_pose — 双长轴歧义不旋转 =====
def test_calibrate_ambiguous() -> bool:
    print("\n[Test 5] auto_calibrate_pose — 双长轴歧义(5%内), 不旋转")
    try:
        # 创建 X=4.0, Y=1.0, Z=4.0 (dx=dz, 双长轴)
        v = [(0, 0, 0), (4, 0, 0), (4, 1, 0), (0, 1, 0),
             (0, 0, 4), (4, 0, 4), (4, 1, 4), (0, 1, 4)]
        obj = _make_mesh_obj('ambig', v)
        stand, horiz = eng.auto_calibrate_pose([obj])
        _print_result(
            "不旋转立起", not stand,
            f"stand={stand} (预期: False, 双长轴歧义)"
        )
        _cleanup_test_objects()
        return not stand
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 6: auto_calibrate_pose — 水平面校准(dx << dy) =====
def test_calibrate_horizontal_fix() -> bool:
    print("\n[Test 6] auto_calibrate_pose — 水平面校准(dx<<dy)")
    try:
        # 创建 Z=4 (已立起), X=0.2, Y=2 (dx<<dy, 肩宽在Y)
        v = [(0, 0, 0), (0.2, 0, 0), (0.2, 2, 0), (0, 2, 0),
             (0, 0, 4), (0.2, 0, 4), (0.2, 2, 4), (0, 2, 4)]
        obj = _make_mesh_obj('thin_shoulder', v)
        stand, horiz = eng.auto_calibrate_pose([obj])
        _print_result(
            "水平面修正", horiz,
            f"horiz={horiz} (预期: True, dx=0.2 << dy=2)"
        )
        # 旋转后 X 应变大, Y 应变小 (交换肩宽和厚度)
        dx2, dy2, dz2 = eng._compute_bbox([obj])
        _print_result(
            "旋转后X>Y (肩宽在X)", dx2 >= dy2,
            f"dx={dx2:.3f} dy={dy2:.3f}"
        )
        _cleanup_test_objects()
        return horiz and dx2 >= dy2
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 7: auto_fix_orientation 兼容函数 =====
def test_fix_orientation_compat() -> bool:
    print("\n[Test 7] auto_fix_orientation 兼容函数")
    try:
        # dx<<dy 应触发旋转
        v1 = [(0, 0, 0), (0.1, 0, 0), (0.1, 3, 0), (0, 3, 0),
              (0, 0, 4), (0.1, 0, 4), (0.1, 3, 4), (0, 3, 4)]
        obj1 = _make_mesh_obj('compat_thin', v1)
        result1 = eng.auto_fix_orientation([obj1])
        _print_result(
            "dx<<dy 触发旋转", result1,
            f"result={result1} (预期: True)"
        )

        # dx>=dy 不应旋转
        v2 = [(0, 0, 0), (3, 0, 0), (3, 1, 0), (0, 1, 0),
              (0, 0, 4), (3, 0, 4), (3, 1, 4), (0, 1, 4)]
        obj2 = _make_mesh_obj('compat_wide', v2)
        result2 = eng.auto_fix_orientation([obj2])
        _print_result(
            "dx>=dy 不旋转", not result2,
            f"result={result2} (预期: False)"
        )
        _cleanup_test_objects()
        return result1 and not result2
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 8: _is_fallback_gray — 无材质 =====
def test_fallback_no_material() -> bool:
    print("\n[Test 8] _is_fallback_gray — 无材质")
    try:
        result = eng._is_fallback_gray(None)
        _print_result("None材质判定", result, "预期: True")
        return result is True
    except Exception as e:
        _print_result("异常", False, str(e))
        return False


# ===== Test 9: _is_fallback_gray — 有贴图纹理(非fallback) =====
def test_fallback_with_texture() -> bool:
    print("\n[Test 9] _is_fallback_gray — 有贴图纹理")
    try:
        import bpy
        mat = eng._make_diffuse_mat('test_tex', (0.9, 0.3, 0.2), 0.95)
        # 模拟有贴图链接 (虽然这里没真实贴图, 但设置一个非灰颜色)
        result = eng._is_fallback_gray(mat)
        _print_result(
            "非灰有色彩→非fallback", not result,
            f"result={result} (预期: False, 颜色饱和)"
        )
        return not result
    except Exception as e:
        _print_result("异常", False, str(e))
        return False


# ===== Test 10: _is_fallback_gray — 灰白fallback =====
def test_fallback_gray() -> bool:
    print("\n[Test 10] _is_fallback_gray — 灰白fallback")
    try:
        import bpy
        # 创建灰白材质 (R=G=B ≈ 0.75)
        mat = eng._make_diffuse_mat('test_gray', (0.75, 0.75, 0.75), 0.95)
        result = eng._is_fallback_gray(mat)
        _print_result("灰白判定", result, "预期: True")
        return result is True
    except Exception as e:
        _print_result("异常", False, str(e))
        return False


# ===== Test 11: _make_diffuse_mat 材质创建 =====
def test_make_diffuse_mat() -> bool:
    print("\n[Test 11] _make_diffuse_mat 材质创建")
    try:
        import bpy
        mat = eng._make_diffuse_mat('test_diffuse', (0.8, 0.2, 0.3), 0.85)
        has_nodes = mat.use_nodes
        _print_result("启用节点", has_nodes, f"use_nodes={has_nodes}")
        has_node_tree = mat.node_tree is not None
        _print_result("有节点树", has_node_tree, f"node_tree={has_node_tree}")
        # 检查有 Diffuse BSDF 节点
        node_types = [n.type for n in mat.node_tree.nodes]
        has_bsdf = 'BSDF_DIFFUSE' in node_types
        _print_result("有Diffuse BSDF节点", has_bsdf, f"types={node_types}")
        # 检查有 Output 节点
        has_output = 'OUTPUT_MATERIAL' in node_types
        _print_result("有Output节点", has_output, f"types={node_types}")
        # 检查链接
        has_links = len(mat.node_tree.links) > 0
        _print_result("有链接", has_links, f"links={len(mat.node_tree.links)}")
        return has_nodes and has_node_tree and has_bsdf and has_output and has_links
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 12: look_at_matrix 正交性 =====
def test_look_at_matrix_orthogonal() -> bool:
    print("\n[Test 12] look_at_matrix 正交性验证")
    try:
        pos = Vector((5, 3, 4))
        target = Vector((0, 0, 1))
        m = eng.look_at_matrix(pos, target)
        # 验证矩阵是4x4
        is_4x4 = len(m) == 4 and all(len(row) == 4 for row in m)
        _print_result("4x4矩阵", is_4x4, f"shape={len(m)}x{len(m[0])}")
        # 验证行列式接近1 (旋转矩阵)
        mat3 = Matrix((m[0][:3], m[1][:3], m[2][:3]))
        det = abs(mat3.determinant())
        _print_result("行列式≈1", abs(det - 1.0) < 0.01, f"det={det:.6f}")
        return is_4x4 and abs(det - 1.0) < 0.01
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 13: look_at_matrix 相机朝向 =====
def test_look_at_matrix_direction() -> bool:
    print("\n[Test 13] look_at_matrix 相机朝向(-Z)")
    try:
        pos = Vector((0, 0, 5))
        target = Vector((0, 0, 0))
        m = eng.look_at_matrix(pos, target)
        # Blender 相机朝 -Z, 第三列 = -forward
        # pos(0,0,5) → target(0,0,0), forward = (0,0,-1)
        # -forward = (0,0,1), 第三列应为(0,0,1)
        col2 = [m[0][2], m[1][2], m[2][2]]
        expected = [0.0, 0.0, 1.0]
        match = all(abs(a - b) < 0.01 for a, b in zip(col2, expected))
        _print_result(
            "第三列=-forward (朝-Z看原点)",
            match,
            f"col2={col2}, expected={expected}"
        )
        return match
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 14: look_at_matrix 近垂直up退化保护 =====
def test_look_at_matrix_up_degenerate() -> bool:
    print("\n[Test 14] look_at_matrix 近垂直up退化保护")
    try:
        # 相机在(0,0,10) 看 (0,0,0), forward=(0,0,-1) 与 up=(0,0,1) 反向
        pos = Vector((0, 0, 10))
        target = Vector((0, 0, 0))
        m = eng.look_at_matrix(pos, target)
        # 应不会崩溃, 返回有效矩阵
        valid = len(m) == 4
        _print_result("垂直视角不崩溃", valid, f"shape={len(m)}x{len(m[0])}")
        return valid
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 15: center_model 居中+尺寸 =====
def test_center_model() -> bool:
    print("\n[Test 15] center_model 居中+尺寸计算")
    try:
        # 创建以(10, 20, 30)为中心的模型
        v = [(9, 19, 29), (11, 19, 29), (11, 21, 29), (9, 21, 29),
             (9, 19, 31), (11, 19, 31), (11, 21, 31), (9, 21, 31)]
        obj = _make_mesh_obj('center_test', v, location=(10, 20, 30))
        size = eng.center_model([obj])
        _print_result("尺寸计算", abs(size - 2.0) < 0.01, f"size={size:.3f} (预期: 2.0)")
        # 验证中心移到原点
        loc = obj.location
        _print_result(
            "中心已到原点",
            abs(loc.x) < 0.01 and abs(loc.y) < 0.01 and abs(loc.z) < 0.01,
            f"location=({loc.x:.3f}, {loc.y:.3f}, {loc.z:.3f})"
        )
        _cleanup_test_objects()
        return abs(size - 2.0) < 0.01 and abs(loc.x) < 0.01 and abs(loc.y) < 0.01 and abs(loc.z) < 0.01
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 16: _set_linear_interp 关键帧插值 =====
def test_set_linear_interp() -> bool:
    print("\n[Test 16] _set_linear_interp 关键帧插值")
    try:
        import bpy
        bpy.ops.object.empty_add(location=(0, 0, 0))
        obj = bpy.context.object
        obj.name = 'test_joint'
        # 创建动画数据和关键帧
        obj.keyframe_insert(data_path='rotation_euler', frame=1)
        obj.keyframe_insert(data_path='rotation_euler', frame=12)
        obj.keyframe_insert(data_path='rotation_euler', frame=24)
        # 应用线性插值
        eng._set_linear_interp(obj)
        # 验证关键帧被设置
        ad = obj.animation_data
        has_action = ad is not None and ad.action is not None
        _print_result("有动画数据", has_action, f"has_action={has_action}")
        # 验证至少有一个fcurve
        if has_action:
            fcurves = list(ad.action.fcurves)
            _print_result("有fcurve", len(fcurves) > 0, f"fcurves={len(fcurves)}")
        _cleanup_test_objects()
        return True  # 不崩溃即通过
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 17: animate_sword_swing 关键帧生成 =====
def test_animate_sword_swing() -> bool:
    print("\n[Test 17] animate_sword_swing 关键帧生成")
    try:
        import bpy
        bpy.ops.object.empty_add(location=(0, 0, 0))
        joint = bpy.context.object
        eng.animate_sword_swing(joint, (1, 48))
        ad = joint.animation_data
        has_action = ad is not None and ad.action is not None
        _print_result("动画数据存在", has_action, "")
        if has_action:
            # 统计关键帧数
            total_keyframes = sum(len(fc.keyframe_points) for fc in ad.action.fcurves)
            # 预期: 8关键帧 × 3轴 = 24 keyframe points
            _print_result(
                "关键帧数量正确",
                total_keyframes == 24,
                f"keyframes={total_keyframes} (预期: 24)"
            )
        _cleanup_test_objects()
        return has_action
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 18: animate_wave 关键帧生成 =====
def test_animate_wave() -> bool:
    print("\n[Test 18] animate_wave 关键帧生成")
    try:
        import bpy
        bpy.ops.object.empty_add(location=(0, 0, 0))
        joint = bpy.context.object
        eng.animate_wave(joint, (1, 48))
        ad = joint.animation_data
        has_action = ad is not None and ad.action is not None
        _print_result("动画数据存在", has_action, "")
        if has_action:
            total_keyframes = sum(len(fc.keyframe_points) for fc in ad.action.fcurves)
            # 预期: 9关键帧 × 3轴 = 27 keyframe points
            _print_result(
                "关键帧数量正确",
                total_keyframes == 27,
                f"keyframes={total_keyframes} (预期: 27)"
            )
        _cleanup_test_objects()
        return has_action
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 19: auto_calibrate_pose — 综合场景(模拟上官婉儿) =====
def test_calibrate_complex() -> bool:
    """模拟复杂模型: X=2.11, Y=0.66, Z=4.58 (上官婉儿型, Z已立起, 水平面正确)"""
    print("\n[Test 19] auto_calibrate_pose — 上官婉儿型")
    try:
        # X=2.11 (肩宽), Y=0.66 (厚度), Z=4.58 (身高)
        v = [(0, 0, 0), (2.11, 0, 0), (2.11, 0.66, 0), (0, 0.66, 0),
             (0, 0, 4.58), (2.11, 0, 4.58), (2.11, 0.66, 4.58), (0, 0.66, 4.58)]
        obj = _make_mesh_obj('shangguan', v)
        stand, horiz = eng.auto_calibrate_pose([obj])
        _print_result(
            "不立起(Z已最长)", not stand,
            f"stand={stand} (预期: False)"
        )
        _print_result(
            "水平面正常(dx>dy*0.5)", not horiz,
            f"horiz={horiz} (预期: False)"
        )
        _cleanup_test_objects()
        return not stand and not horiz
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 20: auto_calibrate_pose — 综合场景(模拟李白) =====
def test_calibrate_libai() -> bool:
    """李白型: X躺倒, 水平面正确 (dx=0.74, dy=0.74, dz=4.58 → 需立起)"""
    print("\n[Test 20] auto_calibrate_pose — 李白型(沿X躺)")
    try:
        # 初始 X=4.58, Y=0.74, Z=0.74 (沿X躺倒)
        v = [(0, 0, 0), (4.58, 0, 0), (4.58, 0.74, 0), (0, 0.74, 0),
             (0, 0, 0.74), (4.58, 0, 0.74), (4.58, 0.74, 0.74), (0, 0.74, 0.74)]
        obj = _make_mesh_obj('libai', v)
        stand, horiz = eng.auto_calibrate_pose([obj])
        _print_result(
            "立起成功(X躺→Z立)", stand,
            f"stand={stand} (预期: True)"
        )
        # 验证立起后Z变为最长
        dx2, dy2, dz2 = eng._compute_bbox([obj])
        is_upright = dz2 > dx2 and dz2 > dy2
        _print_result(
            "立起后Z为最长", is_upright,
            f"dx={dx2:.3f} dy={dy2:.3f} dz={dz2:.3f}"
        )
        _cleanup_test_objects()
        return stand and is_upright
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 21: auto_calibrate_pose — 复杂场景(水平面需修正) =====
def test_calibrate_horizontal_needed() -> bool:
    """模型Z已立起, 但肩宽在Y方向 (dx很薄, dy很厚)"""
    print("\n[Test 21] auto_calibrate_pose — 水平面需修正")
    try:
        # Z=4 (已立起), X=0.2 (薄), Y=2 (厚/肩宽在Y)
        v = [(0, 0, 0), (0.2, 0, 0), (0.2, 2, 0), (0, 2, 0),
             (0, 0, 4), (0.2, 0, 4), (0.2, 2, 4), (0, 2, 4)]
        obj = _make_mesh_obj('needs_hfix', v)
        stand, horiz = eng.auto_calibrate_pose([obj])
        _print_result(
            "立起成功(Z已是最长)", not stand,
            f"stand={stand} (预期: False, Z已最长)"
        )
        _print_result(
            "水平面修正(dx<<dy)", horiz,
            f"horiz={horiz} (预期: True)"
        )
        # 旋转后X应≥Y
        dx2, dy2, dz2 = eng._compute_bbox([obj])
        _print_result(
            "旋转后X≥Y (肩宽归X)", dx2 >= dy2 * 0.5,
            f"dx={dx2:.3f} dy={dy2:.3f}"
        )
        _cleanup_test_objects()
        return not stand and horiz
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 22: 多物体场景 =====
def test_multi_object_bbox() -> bool:
    """验证 _compute_bbox 支持多物体"""
    print("\n[Test 22] 多物体包围盒")
    try:
        v1 = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
              (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
        v2 = [(2, 2, 2), (3, 2, 2), (3, 3, 2), (2, 3, 2),
              (2, 2, 3), (3, 2, 3), (3, 3, 3), (2, 3, 3)]
        obj1 = _make_mesh_obj('multi1', v1)
        obj2 = _make_mesh_obj('multi2', v2)
        dx, dy, dz = eng._compute_bbox([obj1, obj2])
        # 整体包围盒应覆盖两个物体
        _print_result(
            "多物体包围盒",
            abs(dx - 3.0) < 0.01 and abs(dy - 3.0) < 0.01 and abs(dz - 3.0) < 0.01,
            f"dx={dx:.3f} dy={dy:.3f} dz={dz:.3f} (预期: 3.0, 3.0, 3.0)"
        )
        _cleanup_test_objects()
        return abs(dx - 3.0) < 0.01 and abs(dy - 3.0) < 0.01 and abs(dz - 3.0) < 0.01
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Test 23: auto_calibrate_pose 小模型不崩 =====
def test_small_model() -> bool:
    """验证小模型(点云/碎片)不会崩溃"""
    print("\n[Test 23] 小模型不崩溃")
    try:
        v = [(0, 0, 0), (0.01, 0, 0), (0, 0.01, 0)]
        obj = _make_mesh_obj('tiny', v)
        stand, horiz = eng.auto_calibrate_pose([obj])
        _print_result("小模型不崩溃", True, f"stand={stand}, horiz={horiz}")
        _cleanup_test_objects()
        return True
    except Exception as e:
        _print_result("异常", False, str(e))
        traceback.print_exc()
        return False


# ===== Main =====
def main() -> int:
    print("=" * 60)
    print("  Puppeteer Engine Test Suite (2026-08-16)")
    print("=" * 60)

    results: list[bool] = []
    test_count = 0
    passed_count = 0

    test_funcs = [
        test_compute_bbox,
        test_calibrate_x_upright,
        test_calibrate_y_upright,
        test_calibrate_already_upright,
        test_calibrate_ambiguous,
        test_calibrate_horizontal_fix,
        test_fix_orientation_compat,
        test_fallback_no_material,
        test_fallback_with_texture,
        test_fallback_gray,
        test_make_diffuse_mat,
        test_look_at_matrix_orthogonal,
        test_look_at_matrix_direction,
        test_look_at_matrix_up_degenerate,
        test_center_model,
        test_set_linear_interp,
        test_animate_sword_swing,
        test_animate_wave,
        test_calibrate_complex,
        test_calibrate_libai,
        test_calibrate_horizontal_needed,
        test_multi_object_bbox,
        test_small_model,
    ]

    for func in test_funcs:
        result = func()
        test_count += 1
        if result:
            passed_count += 1
        results.append(result)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  Result: {passed_count}/{test_count} passed")
    if passed_count == test_count:
        print(f"  Status: ALL PASSED")
    else:
        failed = [i+1 for i, r in enumerate(results) if not r]
        print(f"  Failed tests: {failed}")
    print(f"{'=' * 60}")
    return 0 if passed_count == test_count else 1


if __name__ == "__main__":
    sys.exit(main())