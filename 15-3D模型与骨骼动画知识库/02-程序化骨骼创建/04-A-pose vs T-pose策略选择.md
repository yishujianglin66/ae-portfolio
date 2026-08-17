# A-pose vs T-pose策略选择

## 问题场景

程序化骨骼必须匹配FBX网格的原始姿态。上官婉儿模型为A-pose（手臂向下约30°展开），如果骨骼按T-pose创建（手臂水平），权重分配和动画变形都会出错。

## 核心原理

### 姿态类型对比

| 姿态 | 手臂角度 | 常见来源 | 优点 | 缺点 |
|------|----------|----------|------|------|
| T-pose | 水平(0°) | Maya/游戏 | 权重对称、标准 | 肩部变形不自然 |
| A-pose | 下垂30-45° | 3dsMax/影视 | 肩部自然 | 权重不对称 |
| 自定义pose | 任意 | 特殊需求 | 匹配原始 | 需特殊处理 |

### 本项目策略：保持A-pose

```python
# cel_shading.py L894-926 的核心决策：
# v12策略: 保持A-pose(与参考图一致), 动画用相机环绕+微摆实现
# 根因: heat diffusion权重分配不准确, 手臂顶点主要被分配到Spine/Chest
#       导致手臂旋转后网格不变形, 骨骼位置≠网格位置

# 具体实现：
_arm_drop_angle = 0.0  # v12: 手臂不下压, 保持原始A-pose (0度)
if 'UpperArm_L' in _pose_bones:
    _pose_bones['UpperArm_L'].rotation_euler[1] = 0.0  # 不旋转
if 'UpperArm_R' in _pose_bones:
    _pose_bones['UpperArm_R'].rotation_euler[1] = 0.0  # 不旋转
```

### 骨骼创建时匹配A-pose

```python
import math

def create_arm_bones_a_pose(arm_data, side='R', shoulder_pos=None, model_h=6.0):
    """创建A-pose手臂骨骼（向下30°）"""
    sign = -1 if side == 'R' else 1
    angle = math.radians(30)  # A-pose下垂角度
    
    sx, sy, sz = shoulder_pos
    
    # 上臂：从肩部向下30°展开
    arm_len = model_h * 0.13
    elbow_x = sx + sign * arm_len * math.cos(angle)
    elbow_z = sz - arm_len * math.sin(angle)
    
    upper = arm_data.edit_bones.new(f'UpperArm_{side}')
    upper.head = (sx, sy, sz)
    upper.tail = (elbow_x, sy, elbow_z)
    
    # 前臂：继续同方向
    fore_len = model_h * 0.12
    wrist_x = elbow_x + sign * fore_len * math.cos(angle)
    wrist_z = elbow_z - fore_len * math.sin(angle)
    
    fore = arm_data.edit_bones.new(f'ForeArm_{side}')
    fore.head = (elbow_x, sy, elbow_z)
    fore.tail = (wrist_x, sy, wrist_z)
    fore.parent = upper
    
    return upper, fore
```

## 常见陷阱

| 陷阱 | 后果 | 解决 |
|------|------|------|
| T-pose骨骼+A-pose网格 | 手臂顶点被分配到Spine | 骨骼匹配网格姿态 |
| 强行旋转手臂到T-pose | 权重不准导致变形撕裂 | 保持原始姿态，用相机动画 |
| A-pose角度估算错误 | 骨骼与网格偏差 | 从实际顶点计算手臂方向 |
| 左右不对称 | 一侧手臂变形异常 | 确保左右角度完全对称 |

## 关联代码

- `cel_shading.py` L894-926：v12 A-pose保持策略
- `cel_shading.py` L700-810：骨骼创建（手臂位置基于网格实际分布）
- 决策记录：auto-weight对此模型无效 → 保持A-pose → 动画用相机环绕
