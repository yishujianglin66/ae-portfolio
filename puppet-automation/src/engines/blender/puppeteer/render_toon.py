"""v6: 番剧级 3渲2 完整动画 — Toon BSDF 硬边色阶 + inverted-hull 描边 + 轮廓光 + 挥手"""
import math
import os

import bpy
from mathutils import Vector

OBJ = r'D:/AE-Data/tools/models/bailixuance.obj'
OUT = r'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/puppeteer_v6'
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=OBJ)
mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]
bpy.context.view_layer.objects.active = mesh
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.separate(type='LOOSE')
bpy.ops.object.mode_set(mode='OBJECT')
parts = [o for o in bpy.data.objects if o.type == 'MESH']

# 居中
minv = [1e9]*3; maxv = [-1e9]*3
for o in parts:
    for v in o.bound_box:
        w = o.matrix_world @ Vector(v)
        for i in range(3):
            minv[i] = min(minv[i], w[i]); maxv[i] = max(maxv[i], w[i])
center = Vector([(a+b)/2 for a,b in zip(minv,maxv)])
for o in parts:
    o.location -= center
bpy.context.view_layer.update()
size = max(b-a for a,b in zip(minv,maxv))

# === Toon BSDF 材质 (硬边色阶) ===
def make_toon(name, color, size=0.35):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    toon = nt.nodes.new('ShaderNodeBsdfToon')
    toon.inputs['Color'].default_value = color
    toon.inputs['Size'].default_value = size  # 阴影硬边
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(toon.outputs['BSDF'], out.inputs['Surface'])
    return mat

# 高饱和动漫色: 上装红/下身蓝/头肤
mat_upper = make_toon('ToonUpper', (0.85, 0.15, 0.15, 1), 0.35)   # 红
mat_lower = make_toon('ToonLower', (0.2, 0.35, 0.8, 1), 0.35)      # 蓝
mat_head = make_toon('ToonHead', (0.95, 0.75, 0.6, 1), 0.4)        # 肤色
mat_weapon = make_toon('ToonWeapon', (0.7, 0.7, 0.75, 1), 0.3)     # 金属灰

for o in parts:
    ys = [p.co.y for p in o.data.vertices]
    cy = (min(ys)+max(ys))/2
    xs = [p.co.x for p in o.data.vertices]
    w = max(xs)-min(xs)
    # 分类: 顶部=头, 宽=武器, 中=上装, 下=下装
    if cy > size*0.28:
        mat = mat_head
    elif cy > 0:
        mat = mat_upper
    else:
        mat = mat_lower
    if w > size*0.45 and cy > size*0.1:
        mat = mat_weapon
    if len(o.data.materials) == 0: o.data.materials.append(mat)
    else: o.data.materials[0] = mat

# === Inverted-hull 描边 ===
outline_mat = bpy.data.materials.new('Outline')
outline_mat.use_nodes = True
on = outline_mat.node_tree
on.nodes.clear()
obs = on.nodes.new('ShaderNodeOutputMaterial')
ob_bsdf = on.nodes.new('ShaderNodeBsdfPrincipled')
ob_bsdf.inputs['Base Color'].default_value = (0.04, 0.04, 0.05, 1)
on.links.new(ob_bsdf.outputs['BSDF'], obs.inputs['Surface'])
for o in list(parts):
    dup = o.copy()
    dup.data = o.data.copy()
    bpy.context.collection.objects.link(dup)
    mod = dup.modifiers.new('OutlineSolid', 'SOLIDIFY')
    mod.thickness = -size * 0.015
    mod.offset = -1.0
    mod.use_flip_normals = True
    dup.data.materials.clear()
    dup.data.materials.append(outline_mat)
    dup.name = o.name + '_ol'

# === 手臂关节 (细长件) ===
arm_obj = None
cands = []
for o in parts:
    v = o.data.vertices
    if len(v) < 30: continue
    ys = [p.co.y for p in v]; xs = [p.co.x for p in v]
    h = max(ys)-min(ys); w = max(xs)-min(xs)
    if w > 0.01 and h/w > 1.8:
        cands.append((o, h/w, len(v)))
cands.sort(key=lambda x: -x[2])
if cands:
    arm_obj = cands[0][0]
joint = None
if arm_obj:
    ys = [p.co.y for p in arm_obj.data.vertices]
    xs = [p.co.x for p in arm_obj.data.vertices]
    joint_loc = Vector(((min(xs)+max(xs))/2, min(ys)-0.1, 0))
    joint = bpy.data.objects.new('J_Arm', None)
    joint.location = joint_loc
    bpy.context.collection.objects.link(joint)
    bpy.context.view_layer.update()
    arm_obj.parent = joint
    arm_obj.matrix_parent_inverse = joint.matrix_world.inverted() @ arm_obj.matrix_world
    bpy.context.view_layer.update()
    # 挥手动画
    for f, rx, rz in [(1,0,0),(7,0.9,0.5),(13,0,0),(19,-0.9,-0.5),(25,0,0),
                      (31,0.9,0.5),(37,0,0),(43,-0.9,-0.5),(48,0,0)]:
        joint.rotation_euler = (rx, 0, rz)
        joint.keyframe_insert(data_path='rotation_euler', frame=f)

scene = bpy.context.scene
scene.frame_start = 1; scene.frame_end = 48; scene.render.fps = 24

# === 世界光 ===
if not bpy.data.worlds: bpy.ops.world.new()
world = bpy.data.worlds[0]
world.use_nodes = True
bg = next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'), None)
bg.inputs['Strength'].default_value = 0.8
bg.inputs['Color'].default_value = (0.55, 0.6, 0.7, 1)
bpy.context.scene.world = world

# === 渲染设置 ===
scene.render.engine = 'CYCLES'
scene.cycles.samples = 20
scene.render.resolution_x = 600
scene.render.resolution_y = 600

# 相机
bpy.ops.object.camera_add(location=(0, -size*1.15, size*0.15))
cam = bpy.context.object
cam.rotation_euler = (math.radians(100), 0, 0)
cam.data.lens = 50
scene.camera = cam

# 灯光: 主光+补光+轮廓光
bpy.ops.object.light_add(type='SUN', location=(size*0.7, -size*0.6, size*1.2))
sun = bpy.context.object
sun.rotation_euler = (0.6, 0, 0.4)
sun.data.energy = 5.0
bpy.ops.object.light_add(type='AREA', location=(-size*0.8, size*0.3, size*0.5))
fill = bpy.context.object
fill.rotation_euler = (1.0, 0, -0.5)
fill.data.energy = 30.0
fill.data.size = size
bpy.ops.object.light_add(type='AREA', location=(0, size*1.1, size*0.4))
rim = bpy.context.object
rim.rotation_euler = (1.57, 0, 0)
rim.data.energy = 40.0
rim.data.size = size*0.6
rim.data.color = (1.0, 0.6, 0.3)

# 渲染完整动画
scene.render.filepath = OUT + '/frame_'
scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(animation=True)
print('V6_DONE')
