"""puppeteer engine — 部件木偶引擎 (2026-08-16 v14)

把静态 OBJ 角色拆成部件, 建关节 Empty 刚性挂接, 驱动关节旋转做木偶动画,
Cycles 3渲2 渲染动画序列。零蒙皮、零变形风险 (Live2D 式部件木偶)。

关键经验 (v1-v14 踩坑):
- Blender 5.1.0 Alpha 的 EEVEE 未注册 (渲染全黑) → 必须用 Cycles
- ⚠️ 5.1 Alpha 渲染管线不重算 Empty 父子驱动的动画 (帧_set 求值正常但渲染帧差=0)
  → v12 改用"部件原点移到关节 + 部件自身关键帧", 渲染实测有效
- 相机: look_at 矩阵数学确定 (v12), 欧拉角 hack 已废弃 (v4 的 100° 技巧)
- 相机距离 ≥ 1.7×size: 55mm 镜头全高可视距离 = 1.52×size, 0.9×size 会裁切 41% (v12 教训)
- 先居中模型 → 再建关节 (parent 后 location 语义变)
- 关节位置用世界坐标 (v8 教训: 居中后局部坐标错位)
- 手动部件名比自动几何分类可靠 (游戏模型是装备件结构, 几何分类不准)
- render(animation=True) 与 手动 frame_set+write_still 都可用 (v12 双路径验证)
- 3dsMax OBJ 沿 X 站立 → 绕 Y 转 90° 立起 (v11, 仅李白型模型正确)
- v13 根因修复: 3dsMax OBJ 立起后侧面朝Y(薄边)、正面朝X (李白dx=0.74/dy=4.58)
  → auto_fix_orientation 补第3条判断: dx<dy*0.5 时绕Z转90让正面朝Y
- v14 终极修复: 去掉硬编码 rotate_y=90 (李白正确, 但上官婉儿原始已沿Z站立导致转歪!)
  → 新增 auto_calibrate_pose() 两阶段全自动校准:
     阶段1【立起】: 找最长轴(容忍双长轴5%歧义)转到Z, 解决李白(沿X躺) vs 上官婉儿(原始Z站立)差异
     阶段2【水平面】: 若 X<<Y (肩宽在Y而非X) 绕Z+90交换, 保证正面朝Y, az=90/270为正面
- OBJ 的 mtllib 嵌套中文路径会读取失败 → 用 libai_fixed.obj (同目录 MTL+贴图)
- 贴图相对 MTL 所在目录解析, OBJ/MTL 必须与贴图同目录

用法 (Blender background):
  blender -b -P engine.py -- --obj <path> --out <dir> [--arm-name libai_fixed.221]
      [--azimuth 270] [--anim swing|wave] [--rotate-y 0] [--dist-scale 1.7] [--res 640]

流程:
  1. 导入 OBJ → auto_calibrate_pose (自动立起+水平面校准) → 分离部件 → 居中
  2. 动画部件挂到关节 (v12: 部件原点移到关节, 直接打部件旋转关键帧)
  3. 挥剑/挥手动画: 关节 X/Z 轴旋转关键帧
  4. look_at 相机 + 三点布光
  5. Cycles 渲染 48 帧动画序列
  6. 输出 PNG (FFmpeg 合成由上层完成)
"""
import bpy
from mathutils import Vector, Matrix
import math
import os
import sys


def parse_args():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    d = {}
    k = None
    for a in args:
        if a.startswith('--'):
            k = a[2:]
            d[k] = ''
        elif k:
            d[k] = a
    return d


def separate_loose(mesh_obj):
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    return [o for o in bpy.data.objects if o.type == 'MESH']


def center_model(parts):
    minv = [1e9] * 3
    maxv = [-1e9] * 3
    for o in parts:
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            for i in range(3):
                minv[i] = min(minv[i], w[i])
                maxv[i] = max(maxv[i], w[i])
    center = Vector([(a + b) / 2 for a, b in zip(minv, maxv)])
    for o in parts:
        o.location -= center
    bpy.context.view_layer.update()
    size = max(b - a for a, b in zip(minv, maxv))
    return size


def make_joint(name, loc, child_obj):
    """v12: 不再用 Empty 父子 (5.1 Alpha 渲染管线不重算父级驱动动画, 实测帧差=0)。
    改为把部件原点移到关节位置, 直接对部件打旋转关键帧 —— 渲染实测有效 (帧差0.25/362px)。
    保留函数名兼容, 返回部件本身。"""
    saved_cursor = bpy.context.scene.cursor.location.copy()
    bpy.context.view_layer.objects.active = child_obj
    bpy.ops.object.select_all(action='DESELECT')
    child_obj.select_set(True)
    bpy.context.scene.cursor.location = loc
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.context.scene.cursor.location = saved_cursor
    bpy.context.view_layer.update()
    return child_obj


def _make_diffuse_mat(name, rgb, roughness=0.95):
    """v14: 用Diffuse BSDF创建材质，Blender 5.1 Principled BSDF已重写，Diffuse更可靠且无高光冲白风险。"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes; links = mat.node_tree.links
    for n in list(nodes): nodes.remove(n)
    bsdf = nodes.new('ShaderNodeBsdfDiffuse')
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf.inputs[0].default_value = (rgb[0], rgb[1], rgb[2], 1.0)  # Color
    try:
        bsdf.inputs['Roughness'].default_value = roughness
    except Exception:
        pass
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


def _is_fallback_gray(mat):
    """判断材质是否是"OBJ导入MTL失败"后的灰色：没有有效节点树/没有贴图纹理且颜色接近灰白。"""
    if mat is None: return True
    try:
        if not mat.use_nodes:
            # 只有旧版设置，接近灰白则fallback
            cd = getattr(mat, 'diffuse_color', None)
            if cd is None: return True
            rg, gg, bg, _ = cd
            return abs(rg-gg) < 0.06 and abs(gg-bg) < 0.06 and rg > 0.5 and rg < 0.92
        nodes = mat.node_tree.nodes
        # 找Principled BSDF或Diffuse节点
        for ntype in ('BSDF_PRINCIPLED', 'BSDF_DIFFUSE'):
            bsdf = next((n for n in nodes if n.type == ntype), None)
            if bsdf is None: continue
            # 看Base Color / Color输入端有没有Texture节点（有贴图=成功导入MTL，不该替换）
            col_inp_key = 'Base Color' if ntype == 'BSDF_PRINCIPLED' else 'Color'
            col_in = bsdf.inputs.get(col_inp_key)
            if col_in is not None and col_in.is_linked:
                return False  # 接了纹理=OK
            # 无贴图：颜色如果接近灰色(R=G=B)且在灰白范围=fallback
            try:
                c = col_in.default_value
            except Exception:
                return True
            r, g, b = c[0], c[1], c[2]
            # 如果颜色饱和度足够（不是灰），保留也OK
            mx, mn = max(r,g,b), min(r,g,b)
            if (mx - mn) > 0.12:
                return False  # 有颜色，保留
            return mx > 0.5 and mx < 0.92  # 灰白=需要替换
        # 没有标准BSDF：默认认为不可靠
        return True
    except Exception:
        return True


def setup_material(parts, size=1.0):
    """v14_semantic setup_material:
    如果MTL导入成功（有纹理或非灰有饱和色）→ 原样保留。
    如果MTL失效（中文路径、找不到文件）→ 用Diffuse BSDF分配语义色（皮肤/头/发/武器/衣服/鞋）。
    """
    # 1. 先收集部件信息
    info = []
    for p in parts:
        bb = [p.matrix_world @ Vector(co) for co in p.bound_box]
        xs=[v[0] for v in bb]; ys=[v[1] for v in bb]; zs=[v[2] for v in bb]
        cx,cy,cz = (max(xs)+min(xs))/2, (max(ys)+min(ys))/2, (max(zs)+min(zs))/2
        dx,dy,dz = max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)
        vol = max(1e-9, dx*dy*dz)
        info.append((p, cx, cy, cz, dx, dy, dz, vol))
    vols = [t[7] for t in info]
    czs = [t[3] for t in info]
    if size <= 0:
        size = max(max(x) - min(x) for x in zip(*[(p.bound_box[i][j] for i in range(8) for p in [t[0]]) for j in range(3)])) if info else 1.0
    size = max(size, 1e-3)
    cz_max = max(czs) if czs else 0
    v_50 = sorted(vols)[len(vols)//2] if vols else 0

    # === 梁祝皮肤配色（参考王者荣耀官方原画）===
    # 服饰: 淡蓝+淡紫青衣戏服（主色调），不是粉色
    # 扇子: 青色荷叶扇（不是红色武器）
    # 毛笔: 棕色笔杆
    # 玉佩: 白玉浅绿（蝴蝶定情信物）
    # 靴子: 深色越剧高跟靴
    # 皮肤: 白皙清秀（女小生扮相）
    SKIN       = (0.95, 0.82, 0.72)   # 白皙肤色（不是深橙）
    HAIR       = (0.08, 0.05, 0.12)   # 深紫黑发
    DRESS_BLUE = (0.35, 0.55, 0.88)   # 淡蓝戏衣（主色）
    DRESS_PURP = (0.52, 0.38, 0.78)   # 淡紫戏衣（辅色）
    DRESS_CYAN = (0.30, 0.68, 0.72)   # 青色戏衣（荷叶元素）
    FAN        = (0.25, 0.65, 0.55)   # 青色扇子（荷叶色）
    BRUSH      = (0.55, 0.35, 0.15)   # 棕色毛笔
    JADE       = (0.70, 0.85, 0.65)   # 白玉浅绿（玉佩）
    SHOES      = (0.12, 0.06, 0.03)   # 深色靴子
    RIBBON     = (0.85, 0.75, 0.45)   # 暗金丝带
    OTHER      = (0.50, 0.48, 0.52)   # 中灰其他

    n_fixed = 0
    for (p, cx, cy, cz, dx, dy, dz, vol) in info:
        # 检查是否需要fallback（MTL失败=灰色）
        need_fallback = (len(p.data.materials) == 0) or _is_fallback_gray(p.data.materials[0] if p.data.materials else None)
        if not need_fallback:
            continue  # MTL成功，不动
        # 分类
        rank = sum(1 for v in vols if v > vol)
        is_head = (cz > cz_max*0.82) and (dz < size*0.22)
        is_hair = (cz > cz_max*0.68) and (dz < size*0.36) and vol < v_50*4.5 and not is_head
        is_shoe = cz < size*0.02
        long_rat = max(dx,dy,dz)/max(0.0001, min(dx,dy,dz)+0.0001)
        is_ribbon = long_rat > 4 and cz > cz_max*0.55
        is_dress = (not is_head) and (not is_shoe) and vol > v_50*0.7
        # 扇子: 体积最大且扁平（rank=0, dx/dz大dy薄）
        is_fan = (rank == 0) and (dy < max(dx, dz) * 0.4)
        # 毛笔: 细长（long_rat>4）且在中低高度
        is_brush = (long_rat > 4) and (cz < cz_max * 0.6) and (not is_shoe)
        # 玉佩: 小体积在胸口（cz 0.4~0.6 cz_max, vol小）
        is_jade = (cz > cz_max*0.35) and (cz < cz_max*0.65) and (vol < v_50*0.3) and (not is_head) and (not is_hair)
        if is_head:           c = SKIN
        elif is_hair:         c = HAIR
        elif is_shoe:         c = SHOES
        elif is_fan:          c = FAN
        elif is_brush:        c = BRUSH
        elif is_jade:         c = JADE
        elif is_ribbon and not is_dress: c = RIBBON
        elif is_dress and rank < 3: c = DRESS_BLUE    # 前几大衣服件=淡蓝
        elif is_dress and rank < 6: c = DRESS_PURP    # 中等=淡紫
        elif is_dress:        c = DRESS_CYAN          # 其余=青色
        elif long_rat > 3 and not is_brush: c = OTHER
        else:                 c = OTHER
        mat = _make_diffuse_mat(f'sem_{p.name}', c, 0.95)
        # 绑定（mesh级+object级双重确保生效）
        p.data.materials.clear()
        p.data.materials.append(mat)
        if hasattr(p, 'material_slots') and len(p.material_slots) == 0:
            try:
                bpy.context.view_layer.objects.active = p
                bpy.ops.object.material_slot_add()
            except Exception:
                pass
        try:
            if len(p.material_slots) > 0: p.material_slots[0].material = mat
        except Exception:
            pass
        if hasattr(p.data, 'polygons'):
            for poly in p.data.polygons:
                poly.material_index = 0
        n_fixed += 1
    print(f'MATERIAL_DONE: fallback着色部件={n_fixed}/{len(parts)} (其余MTL正常保留)')


def setup_world_light(size=1.0):
    """v14: 适中光照——避免冲白但也不要太暗。"""
    if not bpy.data.worlds:
        bpy.ops.world.new()
    world = bpy.data.worlds[0]
    world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'), None)
    if bg:
        bg.inputs['Strength'].default_value = 1.5
        bg.inputs['Color'].default_value = (0.80, 0.85, 0.95, 1.0)
    bpy.context.scene.world = world
    scene = bpy.context.scene
    try:
        opts = [e.identifier for e in scene.view_settings.bl_rna.properties['look'].enum_items]
        scene.view_settings.look = 'AgX - Base Contrast' if 'AgX - Base Contrast' in opts else (opts[0] if opts else 'None')
        scene.view_settings.exposure = 0.5  # 适度提亮（之前-0.4太暗，RGB中位仅70）
    except Exception:
        pass


def look_at_matrix(pos, target, up=None):
    """v12: 数学确定的 look_at 矩阵 (替代欧拉角 hack)。
    Blender 相机朝 -Z, 第三列 = -forward。俯仰接近垂直时 up 退化, 自动换 up 轴。"""
    if up is None:
        up = Vector((0, 0, 1))
    forward = (target - pos).normalized()
    if abs(forward.dot(up)) > 0.999:
        up = Vector((0, 1, 0))  # 近垂直视角保护
    right = forward.cross(up).normalized()
    true_up = right.cross(forward).normalized()
    return Matrix((
        (right.x, true_up.x, -forward.x, pos.x),
        (right.y, true_up.y, -forward.y, pos.y),
        (right.z, true_up.z, -forward.z, pos.z),
        (0, 0, 0, 1),
    ))


def setup_camera_lights(size, azimuth_deg=337.5, dist_scale=1.7, lens=50):
    """v14: 改用大面积Area柔光（光强减半），避免高光反射+金属高光造成渲染一片白。"""
    scene = bpy.context.scene
    az = math.radians(azimuth_deg)
    target = Vector((0, 0, 0))
    d = size * dist_scale
    pos = Vector((d * math.cos(az), d * math.sin(az), size * 0.18))  # 相机略抬高看全身
    bpy.ops.object.camera_add(location=(0, 0, 0))
    cam = bpy.context.object
    cam.data.lens = lens
    cam.matrix_world = look_at_matrix(pos, target)
    scene.camera = cam
    # 大面积柔光 (主光 / 补光 / 背面轮廓光 / 头顶补光)
    # 主光：相机右上方45°
    bpy.ops.object.light_add(type='AREA', location=(d * 0.7 * math.cos(az - 0.9), d * 0.7 * math.sin(az - 0.9), size * 0.95))
    bpy.context.object.data.energy = 60; bpy.context.object.data.size = size * 1.9
    # 补光：左下方
    bpy.ops.object.light_add(type='AREA', location=(d * 0.6 * math.cos(az + 2.5), d * 0.6 * math.sin(az + 2.5), size * 0.55))
    bpy.context.object.data.energy = 40; bpy.context.object.data.size = size * 1.8
    # 背面光（轮廓分离）
    bpy.ops.object.light_add(type='AREA', location=(d * 0.55 * math.cos(az + math.pi), d * 0.55 * math.sin(az + math.pi), size * 0.4))
    bpy.context.object.data.energy = 9; bpy.context.object.data.size = size * 1.6
    # 顶柔光
    bpy.ops.object.light_add(type='AREA', location=(0, 0, size * 1.15))
    bpy.context.object.data.energy = 7; bpy.context.object.data.size = size * 1.2


def animate_wave(joint, frames=(1, 48)):
    """挥手: X轴前后摆 + Z轴侧摆, 周期12帧。"""
    for f, rx, rz in [(frames[0], 0, 0), (frames[0] + 6, 0.9, 0.5),
                      (frames[0] + 12, 0, 0), (frames[0] + 18, -0.9, -0.5),
                      (frames[0] + 24, 0, 0), (frames[0] + 30, 0.9, 0.5),
                      (frames[0] + 36, 0, 0), (frames[0] + 42, -0.9, -0.5),
                      (frames[1], 0, 0)]:
        joint.rotation_euler = (rx, 0, rz)
        joint.keyframe_insert(data_path='rotation_euler', frame=f)


def _set_linear_interp(joint):
    """关键帧改线性插值 (5.1 slotted actions 兼容: fcurves 在 channelbag 里)。"""
    ad = joint.animation_data
    if not ad or not ad.action:
        return
    fcurves = []
    try:
        fcurves = list(ad.action.fcurves)  # Blender <=4.3 legacy
    except AttributeError:
        try:
            slot = ad.action_slot or ad.action.slots[0]
            for layer in ad.action.layers:
                for strip in layer.strips:
                    cb = strip.channelbag(slot)
                    if cb:
                        fcurves.extend(cb.fcurves)
        except Exception:
            return
    for fc in fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def animate_sword_swing(joint, frames=(1, 48)):
    """v12 挥剑: 蓄力上举(1-14) → 定格(14-18) → 快速劈砍(18-30) → 收势回位(30-48)。
    X 轴抬落 + Z 轴横扫, 关键帧间用阶跃式劈砍制造速度感。"""
    keys = [
        (frames[0], 0.0, 0.0),          # 起势
        (frames[0] + 8, -0.7, 0.35),    # 蓄力上举后仰
        (frames[0] + 14, -0.9, 0.5),    # 举到最高
        (frames[0] + 18, -0.9, 0.5),    # 定格(蓄势)
        (frames[0] + 24, 0.9, -0.45),   # 劈砍到底(快)
        (frames[0] + 30, 0.95, -0.5),   # 砍到最低点
        (frames[0] + 40, 0.3, -0.15),   # 收势
        (frames[1], 0.0, 0.0),          # 回位
    ]
    for f, rx, rz in keys:
        joint.rotation_euler = (rx, 0, rz)
        joint.keyframe_insert(data_path='rotation_euler', frame=f)
    # 劈砍段加速: 线性插值 (默认贝塞尔会慢进慢出)
    _set_linear_interp(joint)


def _compute_bbox(mesh_objs):
    minv = [1e9]*3; maxv = [-1e9]*3
    for o in mesh_objs:
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            for i in range(3):
                minv[i] = min(minv[i], w[i]); maxv[i] = max(maxv[i], w[i])
    return maxv[0]-minv[0], maxv[1]-minv[1], maxv[2]-minv[2]


def _apply_rotation(mesh_objs, axis, deg):
    """对所有 mesh 绕指定轴旋转 deg 度，立即 apply transform。"""
    for m in mesh_objs:
        if axis == 'x':
            m.rotation_euler.x += math.radians(deg)
        elif axis == 'y':
            m.rotation_euler.y += math.radians(deg)
        else:
            m.rotation_euler.z += math.radians(deg)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    bpy.ops.object.select_all(action='DESELECT')


def auto_calibrate_pose(mesh_objs):
    """v14: 替代硬编码 rotate_y=90 + auto_fix_orientation，两阶段全自动校准:
      阶段1【立起】: 找出最长轴(身高), 旋转到 Z+ 方向 (容忍<5%的双长轴歧义，优先保持Z为身高)
      阶段2【水平面】: 肩宽应该在X、前后厚度应该在Y。若 X<<Y，说明肩宽在Y方向(被转歪)，绕Z+90交换。
    返回 (stand_fixed, horiz_fixed)"""
    dx, dy, dz = _compute_bbox(mesh_objs)
    print(f'STAGE1_CHECK dx={dx:.2f} dy={dy:.2f} dz={dz:.2f}')
    dims = [('x', dx), ('y', dy), ('z', dz)]
    dims.sort(key=lambda t: -t[1])  # 从大到小
    longest, d1 = dims[0]
    second, d2 = dims[1]
    shortest, d3 = dims[2]
    stand_fixed = False
    # 最长轴明显领先 (差距>5%) 则必须转到Z
    if longest != 'z' and d1 > max(d2, d3) * 1.05:
        if longest == 'x':
            # X 最长 (李白型: 沿X躺) → 绕Y+90立起
            _apply_rotation(mesh_objs, 'y', 90)
            stand_fixed = True
            print('STAGE1_FIX: X最长(沿X躺)→绕Y+90立起')
        elif longest == 'y':
            # Y 最长 (前后倒) → 绕X-90立起
            _apply_rotation(mesh_objs, 'x', -90)
            stand_fixed = True
            print('STAGE1_FIX: Y最长(前后倒)→绕X-90立起')
    elif longest == 'z' or (longest != 'z' and d1 / max(d2, d3) <= 1.05):
        # Z已是最长 或 X/Z双长(差距<=5%, 如上官婉儿dx=0.83 dz=0.82) → 不转, 假定Z为身高
        print('STAGE1_OK: Z为身高(已立起或双长轴歧义)，无需立起旋转')
    else:
        print('STAGE1_SKIP: 未触发立起旋转')

    # 阶段2：水平面校准 (肩宽=X大, 厚度=Y小; 若反过来则绕Z+90交换)
    dx, dy, dz = _compute_bbox(mesh_objs)
    print(f'STAGE2_CHECK dx={dx:.2f} dy={dy:.2f} dz={dz:.2f}')
    horiz_fixed = False
    # Z必须是身高，否则阶段1失败；如果此时 X明显薄于Y → X是厚度，肩宽在Y → 水平面转90
    if dz >= max(dx, dy) * 0.95 and dx < dy * 0.5:
        _apply_rotation(mesh_objs, 'z', 90)
        horiz_fixed = True
        print(f'STAGE2_FIX: 水平面绕Z+90° (dx={dx:.2f}<dy*0.5={dy*0.5:.2f}, 肩宽交换到X)')
    else:
        print('STAGE2_OK: 水平面正常 (X肩宽≥Y厚度 或 Z非身高)，无需旋转')
    return stand_fixed, horiz_fixed


# 兼容老调用: auto_fix_orientation = 阶段2水平面校准 (单独可调用)
def auto_fix_orientation(mesh_objs):
    """v14兼容函数: 仅做阶段2水平面校准, 老代码调用时返回bool。"""
    dx, dy, dz = _compute_bbox(mesh_objs)
    print(f'ORIENT_CHECK dx={dx:.2f} dy={dy:.2f} dz={dz:.2f}')
    if dz >= max(dx, dy) * 0.95 and dx < dy * 0.5:
        _apply_rotation(mesh_objs, 'z', 90)
        print(f'ORIENT_FIX: 水平面转90° (dx={dx:.2f}<dy*0.5={dy*0.5:.2f})')
        return True
    print('ORIENT_OK: 无需水平面校准')
    return False


def main():
    args = parse_args()
    obj_path = args.get('obj', r'D:/AE-Data/tools/models/libai/libai_fixed.obj')
    out_dir = args.get('out', r'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/puppeteer_v14')
    arm_name = args.get('arm-name', '')
    # v14: 水平面校准后 肩宽=X 厚度=Y 正面朝Y → az=90/270 为正面方位 (az=270=相机在-Y看+Y=看正面)
    azimuth = float(args.get('azimuth', '270'))
    anim_mode = args.get('anim', 'swing')       # v12 默认挥剑
    # rotate-y 参数保留但默认值=0 (v14 使用 auto_calibrate_pose 自动立起，不再硬编码绕Y+90)
    rotate_y = float(args.get('rotate-y', '0'))
    dist_scale = float(args.get('dist-scale', '1.7'))
    res = int(args.get('res', '640'))
    os.makedirs(out_dir, exist_ok=True)

    # 1. 导入 → v14自动校准(阶段1:立起 + 阶段2:水平面) → 分离 → 居中
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=obj_path)
    mesh = [o for o in bpy.data.objects if o.type == 'MESH']
    if not mesh:
        print('ERROR: no mesh'); return 1
    # 向后兼容: 用户显式指定 rotate-y 时，先应用手动旋转，再自动校准
    if rotate_y:
        for m in mesh:
            m.rotation_euler = (0, math.radians(rotate_y), 0)
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        bpy.ops.object.select_all(action='DESELECT')
        print(f'ROTATE_Y(manual)={rotate_y}')
    # v14: 全自动两阶段校准 (替代老的 rotate_y=90 + auto_fix_orientation)
    stand_fixed, horiz_fixed = auto_calibrate_pose(mesh)
    print(f'AUTO_CALIBRATE_DONE stand={stand_fixed} horizontal={horiz_fixed}')
    parts = separate_loose(mesh[0])
    size = center_model(parts)
    print(f'PARTS={len(parts)} SIZE={size:.2f}')

    # 2. 动画部件 (手动指定 or 细长件自动)
    arm_obj = None
    if arm_name:
        arm_obj = next((o for o in parts if o.name == arm_name), None)
        print(f'ARM_MANUAL={arm_name} found={arm_obj is not None}')
    if arm_obj is None:
        # 自动: 细长比>1.8 且体积大的部件
        cands = []
        for o in parts:
            v = o.data.vertices
            if len(v) < 30:
                continue
            ys = [p.co.y for p in v]
            xs = [p.co.x for p in v]
            h = max(ys) - min(ys)
            w = max(xs) - min(xs)
            if w > 0.01 and h / w > 1.8:
                cands.append((o, h / w, len(v)))
        cands.sort(key=lambda x: -x[2])
        if cands:
            arm_obj = cands[0][0]
            print(f'ARM_AUTO={arm_obj.name}')
    if arm_obj is None:
        print('ERROR: no arm'); return 1

    # 3. 关节: 部件长轴(局部Y)低端略偏 —— 用世界坐标 (v8 教训: 居中后局部坐标不可靠)
    ws = [arm_obj.matrix_world @ v.co for v in arm_obj.data.vertices]
    joint_loc = Vector((
        sum(p.x for p in ws) / len(ws),
        min(p.y for p in ws) - 0.1,
        sum(p.z for p in ws) / len(ws),
    ))
    joint = make_joint('J_Arm', joint_loc, arm_obj)
    print(f'JOINT={tuple(round(c, 2) for c in joint_loc)}')

    # 4. 动画
    if anim_mode == 'swing':
        animate_sword_swing(joint, (1, 48))
    else:
        animate_wave(joint, (1, 48))
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 48
    scene.render.fps = 24
    print(f'ANIM_OK mode={anim_mode}')

    # 5. 材质: v14_semantic fallback着色（MTL失败=灰白→自动分配语义色）
    setup_material(parts, size)
    setup_world_light(size)
    setup_camera_lights(size, azimuth_deg=azimuth, dist_scale=dist_scale)
    print(f'CAMERA look_at az={azimuth} dist={size*dist_scale:.2f}')

    # 6. Cycles 渲染（减少样本提速+v14降曝光）
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 18
    try:
        scene.cycles.use_denoising = True
    except Exception:
        pass
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.filepath = out_dir + '/frame_'
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(animation=True)
    print(f'RENDER_DONE {out_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
