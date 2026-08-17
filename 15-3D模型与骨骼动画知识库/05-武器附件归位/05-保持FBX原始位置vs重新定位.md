# 保持FBX原始位置vs重新定位的取舍

## 问题场景

v12策略演进中，最初尝试"保持FBX原始位置"（`_v12_no_reposition=True`），但发现FBX中扇子在地面(z=-6.2)。需要决定：保持原位还是重新定位到手部。

## 核心原理

### 两种策略对比

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 保持FBX原位 | 简单、无计算误差 | 武器可能在地面/空中 | FBX中武器已在手中 |
| 重新定位 | 武器一定在手中 | 需要手部检测+旋转计算 | FBX中武器不在手中 |

### 决策逻辑

```python
def should_reposition(weapon_parts, body_parts, armature_obj):
    """判断是否需要重新定位武器"""
    if not weapon_parts:
        return False
    
    # 检查武器是否已在手部区域
    hand_pos = detect_hand_from_mesh(body_parts)
    
    for weapon in weapon_parts:
        weapon_center = weapon.matrix_world.translation
        distance = (weapon_center - hand_pos).length
        
        # 如果武器离手超过阈值，需要重新定位
        if distance > 1.0:  # 1个Blender单位
            print(f"[Decision] Weapon '{weapon.name}' is {distance:.2f} from hand → REPOSITION")
            return True
    
    print("[Decision] All weapons near hand → KEEP POSITION")
    return False
```

### 本项目的决策过程

```
v8-v11: 尝试重新定位（各种方案）
v12初期: _v12_no_reposition = True（保持原位）
  → 失败：FBX中扇子在地面(z=-6.2)
v12最终: _v12_no_reposition = False（重新定位）
  → 成功：网格顶点检测手部 + rotate-first归位

关键发现：
- 3dsMax导出的FBX中，武器通常放在地面/旁边
- 不能假设FBX中武器已在正确位置
- 必须实现重新定位逻辑
```

### 混合策略

```python
def smart_weapon_position(weapon_parts, body_parts, armature_obj):
    """智能武器定位：检测后决定"""
    hand_pos, hand_verts = detect_hand_from_mesh(body_parts)
    
    for weapon in weapon_parts:
        weapon_pos = weapon.matrix_world.translation
        dist_to_hand = (weapon_pos - hand_pos).length
        
        if dist_to_hand < 0.5:
            # 已在手中，只需微调
            fine_tune_position(weapon, hand_pos)
        elif dist_to_hand < 3.0:
            # 在附近，平移对齐
            shift = hand_pos - weapon_pos
            weapon.location += shift
        else:
            # 远离（如在地面），完整重新定位
            full_reposition(weapon, hand_pos)
```

## 常见陷阱

### 陷阱1：假设FBX武器在手中
```python
# 错误假设：3dsMax导出时武器已在正确位置
# 实际：很多FBX中武器放在地面或单独位置
# 解决：始终检测武器与手部的距离
```

### 陷阱2：_v12_no_reposition跳过变量定义
```python
# 本项目的NameError根因：
# _v12_no_reposition=True时，定义_bc的块被跳过
# 但后续代码仍引用_bc → NameError
# 解决：所有条件分支都要确保变量有定义
```

## 本项目代码关联

`cel_shading.py`：
- L1486: `_v12_no_reposition = False`（最终决策）
- L1490: `if _weapon_parts and _v12_no_reposition:` → 保持原位分支
- L1510: `if _weapon_parts and not _v12_no_reposition:` → 重新定位分支

## 版本兼容性

- 纯逻辑决策，无Blender版本依赖

## 参考链接

- 本项目调试日志：`temp/v12_full_log.txt`
