# Phase 3 方向调研：3D 文字特效

> 日期: 2026-07-27 | 状态: **API探针已完成，首批4预设验证通过 (26/26 SUCCESS)**
> 前置: 87预设(Phase1+2)全量验证通过，渲染管线成熟

---

## 1. 可行性结论（摘要）

| 路径 | 可行性 | 推荐度 | 理由 |
|------|--------|--------|------|
| AE原生 Cinema 4D 渲染器 | ✅ 高 | ⭐⭐⭐⭐⭐ | 纯ExtendScript可控，无需额外插件，挤出/倒角/材质/灯光全链路 |
| AE原生 Advanced 3D 渲染器 | ✅ 高 | ⭐⭐⭐⭐ | GPU加速PBR，支持环境光/HDRI，但API文档较少需探针 |
| Element 3D (已安装) | ✅ 高 | ⭐⭐⭐⭐ | 已验证安装，MCP已有e3d-load-model工具，但文字挤出需3DArray |
| VE 3D Bevel (已安装) | ⚠️ 中 | ⭐⭐⭐ | 轻量倒角效果，非真3D空间，适合2.5D标题 |
| Blender联动 | ⚠️ 中 | ⭐⭐ | 15-3D知识库有积累，但链路复杂，非实时 |

**推荐策略**：以 **Cinema 4D 渲染器 + 原生3D文字** 为主线，Element 3D 作为高级补充（金属/玻璃材质），开发 Phase 3 新品类 `3d_title` / `3d_kinetic`。

---

## 2. AE 2025 原生 3D 文字技术架构

### 2.1 三种渲染器对比

| 特性 | Classic 3D | Cinema 4D | Advanced 3D |
|------|-----------|-----------|-------------|
| 文字挤出 | ❌ | ✅ | ✅ |
| 倒角(Bevel) | ❌ | ✅ | ✅ |
| 材质系统 | 基础 | 标准 | Adobe Standard Material (PBR) |
| 环境光/HDRI | ❌ | ❌ | ✅ |
| 3D模型导入 | ❌ | ❌ | ✅ (GLTF/OBJ/FBX) |
| GPU加速 | ❌ | 部分 | ✅ (Mercury 3D) |
| 逐字3D化 | ✅ | ✅ | ✅ |
| 渲染速度 | 快 | 中 | 快(GPU) |
| ExtendScript可控 | ✅ | ✅ | 需探针 |

### 2.2 Cinema 4D 渲染器 - 文字3D参数

通过 **Geometry Options** 属性组控制：

| 参数 | 英文名 | 类型 | 范围 | 说明 |
|------|--------|------|------|------|
| 斜面样式 | Bevel Style | 枚举 | None/Angular/Concave/Convex | 边缘形状 |
| 斜面深度 | Bevel Depth | px | 0-100+ | 倒角大小 |
| 洞斜面深度 | Hole Bevel Depth | % | 0-100 | 内孔倒角(如"O") |
| 凸出深度 | Extrusion Depth | px | 0-1000+ | 文字厚度 |

通过 **Material Options** 属性组控制：

| 参数 | 英文名 | 说明 |
|------|--------|------|
| 反射强度 | Reflection Intensity | 环境反射 |
| 反射锐度 | Reflection Sharpness | 模糊→镜面 |
| 反射衰减 | Reflection Rolloff | Fresnel效果 |
| 高光亮度 | Specular Intensity | 镜面高光 |
| 高光锐度 | Specular Shininess | 高光范围 |
| 投射阴影 | Cast Shadows | On/Off/Only |
| 接受阴影 | Accept Shadows | On/Off |
| 接受光照 | Accept Lights | On/Off |
| 环境光 | Ambient | 环境光响应 |
| 漫射 | Diffuse | 漫反射系数 |

### 2.3 灯光系统

| 灯光类型 | 用途 | 关键参数 |
|----------|------|----------|
| Parallel(平行光) | 太阳光模拟 | Direction, Intensity, Color |
| Spot(聚光灯) | 舞台聚焦 | Cone Angle, Cone Feather, Falloff |
| Point(点光源) | 灯泡/能量核心 | Radius, Falloff Start/End |
| Ambient(环境光) | 基础照明 | Intensity, Color |

### 2.4 逐字3D化 (Per-character 3D)

```
动画制作 > 启用逐字 3D 化 (Animate > Enable Per-character 3D)
```
- 每个字符成为独立3D子图层
- 可分别控制Position(Z), X/Y/Z Rotation
- 通过Text Animator的Range Selector驱动逐字动画
- **这是3D Kinetic Typography的核心机制**

---

## 3. ExtendScript API 可用性分析（探针实证 2026-07-27）

### 3.0 探针结论摘要

| API路径 | 状态 | matchName | 备注 |
|---------|------|-----------|------|
| 渲染器切换 | **锁定** | comp.renderer只读 | 始终ADBE Advanced 3d，无法切换 |
| 几何选项组 | **存在但隐藏** | `ADBE Extrsn Options Group` | setValue报"属性被隐藏" |
| 凸出深度 | **不可写** | `ADBE Extrsn Depth` | enabled=true但setValue失败 |
| 斜面样式 | **不可写** | `ADBE Bevel Styles` | 同上 |
| 斜面深度 | **不可写** | `ADBE Bevel Depth` | 同上 |
| 洞斜面深度 | **不可写** | `ADBE Hole Bevel Depth` | 同上 |
| 材质-投射阴影 | **可写** | `ADBE Casts Shadows` | 0/1 |
| 材质-接受阴影 | **可写** | `ADBE Accepts Shadows` | 0/1 |
| 材质-接受光照 | **可写** | `ADBE Accepts Lights` | 0/1 |
| 材质-环境光 | **可写** | `ADBE Ambient Coefficient` | 0-100 |
| 材质-漫射 | **可写** | `ADBE Diffuse Coefficient` | 0-100 |
| 材质-镜面强度 | **可写** | `ADBE Specular Coefficient` | 0-100 |
| 材质-镜面反光度 | **可写** | `ADBE Shininess Coefficient` | 0-100 |
| 材质-金属质感 | **可写** | `ADBE Metal Coefficient` | 0-100 |
| 材质-反射/透明/折射 | **隐藏** | 多个 | Advanced 3D渲染器限制 |
| 灯光-强度 | **可写** | `ADBE Light Intensity` | 0-∞ |
| 灯光-颜色 | **可写** | `ADBE Light Color` | [r,g,b] 0-1 |
| 灯光-锥形角度 | **可写** | `ADBE Light Cone Angle` | 度 |
| 灯光-锥形羽化 | **可写** | `ADBE Light Cone Feather 2` | 0-100 |
| 灯光-衰减类型 | **可写** | `ADBE Light Falloff Type` | 0=None,1=Smooth,2=Inverse |
| 灯光-衰减起始 | **可写** | `ADBE Light Falloff Start` | px |
| 灯光-衰减距离 | **可写** | `ADBE Light Falloff Distance` | px |
| 灯光-投影 | **可写** | `ADBE Casts Shadows` | 0/1 |
| 灯光-阴影深度 | **可写** | `ADBE Light Shadow Darkness` | 0-100 |
| 灯光-阴影扩散 | **可写** | `ADBE Light Shadow Diffusion` | px |
| 摄像机-缩放 | **可写** | `ADBE Camera Zoom` | px |
| 摄像机-景深开关 | **可写** | `ADBE Camera Depth of Field` | 0/1 |
| 摄像机-焦距 | **可写** | `ADBE Camera Focus Distance` | px |
| 摄像机-光圈 | **可写** | `ADBE Camera Aperture` | f-stop |
| 摄像机-模糊层次 | **可写** | `ADBE Camera Blur Level` | 0-100 |
| 摄像机-Position[Z] | **BUG** | ADBE Position | "除以零"错误 |
| 灯光-Position[Z] | **BUG** | ADBE Position | 同上 |
| 逐字3D位置 | **可写** | `ADBE Text Position 3D` | Text Animator内 |
| 逐字Y旋转 | **可写** | `ADBE Text Rotate Y` | 表达式驱动 |

### 3.1 设计决策（基于探针结果）

**核心限制**：AE 2025 Advanced 3D渲染器下，Geometry Options（Extrusion/Bevel）通过ExtendScript **完全不可写**。

**替代方案（已验证）**：
1. **层叠深度模拟** - N层文字在Z轴堆叠，模拟挤出厚度（td_metallic_depth）
2. **逐字3D动画** - Text Animator + Position 3D表达式（td_perchar_wave）
3. **摄像机Zoom动画** - 替代不可用的Camera Position Z（td_depth_flythrough）
4. **材质+灯光** - 7个可写材质参数 + 完整灯光控制（td_shadow_drama）

---

## 4. API 探针执行记录（已完成）

### 4.1 执行概要

| 轮次 | 脚本 | 目标 | 结果 |
|------|------|------|------|
| Round 1 | `probe_3d_text.jsx` | 枚举Geometry/Material matchName | ✅ 确认属性存在但隐藏 |
| Round 2 | `probe_3d_text_v2.jsx` | setValue写入测试 + 渲染器切换 | ✅ 确认Geometry不可写、renderer只读 |
| Round 3 | `probe_3d_text_v3.jsx` | Material可写性 + Camera/Light详细枚举 | ✅ 确认7个材质+全部灯光+摄像机Zoom可写 |

### 4.2 执行方式

```
Bridge文件协议: ae_command.json → runScript → ae_result.json
去重机制: timestamp唯一性校验
结果输出: temp/probe_3d_result.txt, probe_3d_v2_result.txt, probe_3d_v3_result.txt
```

### 4.3 关键发现

1. **Geometry Options完全锁定** - AE 2025 Advanced 3D渲染器将Extrusion/Bevel标记为hidden
2. **渲染器不可切换** - `comp.renderer`只读，始终为`ADBE Advanced 3d`
3. **Camera/Light Position Z有BUG** - setValue触发"除以零"错误
4. **材质7参数可写** - Specular/Shininess/Metal/Diffuse/Ambient/CastsShadows/AcceptsShadows
5. **灯光全部参数可写** - Intensity/Color/ConeAngle/Feather/Falloff/Shadows
6. **摄像机Zoom/DOF可写** - 可替代Position Z实现纵深动画

---

## 5. 确认的参数映射表（实施版）

### 5.1 预设模板实际参数结构

已通过AE内验证的4个预设使用以下参数体系（`config/text_animation_presets.json` v3.0-alpha）：

| 预设ID | 品类 | 核心技术 | 参数 |
|--------|------|----------|------|
| `td_metallic_depth` | 3d_title | 层叠深度+金属材质+Spot Light | textLayerName, duration, depthLayers(3-12), depthSpacing(2-20) |
| `td_perchar_wave` | 3d_title | Text Animator逐字3D+表达式 | textLayerName, duration, waveAmplitude(30-300), waveSpeed(1-10) |
| `td_depth_flythrough` | 3d_title | 多Z层+Camera Zoom+DOF | textLayerName, duration, depthSpread(200-1500) |
| `td_shadow_drama` | 3d_title | 高对比Spot+Shadow+Y旋转 | textLayerName, duration, rotationRange(5-60) |

### 5.2 与现有预设体系集成（已实施）

| 现有字段 | 3D扩展 | 状态 |
|----------|--------|------|
| `categories` | 新增 `3d_title` (display: "3D Title & Kinetic") | ✅ 已注入 |
| `parameters[]` | 新增 depthLayers/depthSpacing/waveAmplitude/depthSpread/rotationRange | ✅ 已验证 |
| `jsx_template` | IIFE + try-catch + JSON.stringify返回 | ✅ 26/26 SUCCESS |
| `animationDNA` | 复用现有8种DNA（cinematicSlow/impactHit等） | ✅ 兼容 |
| `version` | 升级至 `3.0-alpha` | ✅ 91预设 |

---

### 6. 已实施试点预设 (4个, 26/26 SUCCESS)

### 6.1 `td_metallic_depth` - 金属3D深度标题 ✅
- **视觉**: 6层Z轴堆叠模拟挤出厚度，金属材质高光，Y轴旋转揭示
- **技术**: 层叠深度(duplicate+Z offset) + Material(Specular:90, Metal:100) + Spot Light + Parent Null旋转
- **验证**: `{"status":"success","depthLayers":6,"material":"metallic","light":"spot+ambient"}`
- **时长**: 3.0s | **缓动**: cinematicSlow (ease 80/60)

### 6.2 `td_perchar_wave` - 逐字3D波浪 ✅
- **视觉**: 每个字符独立Z轴正弦波运动 + Y轴微旋转
- **技术**: Text Animator(ADBE Text Position 3D + Rotate Y) + 表达式驱动 + Point Light falloff
- **验证**: `{"status":"success","animator":"Wave3D","expression":"z_wave","light":"point"}`
- **时长**: 3.0s(循环) | **表达式**: `z=sin(idx*0.6+t*6.28)*amp`

### 6.3 `td_depth_flythrough` - 3D纵深穿越 ✅
- **视觉**: 4层文字不同Z深度，Camera Zoom从800→2000穿越，DOF前景/背景虚化
- **技术**: 多Text Layer Z分布 + Camera Zoom关键帧(替代不可用的Position Z) + Focus Distance动画
- **验证**: `{"status":"success","layers":4,"camera":"zoom+DOF","light":"point"}`
- **时长**: 4.0s | **DOF**: Aperture:8, BlurLevel:80

### 6.4 `td_shadow_drama` - 戏剧阴影3D ✅
- **视觉**: 高对比聚光灯投射戏剧性阴影，暗色背景接收投影，慢速Y旋转
- **技术**: Material(Casts+Accepts Shadows) + Spot(Intensity:250, ShadowDarkness:95) + BG Solid Z:200 + Rim Light
- **验证**: `{"status":"success","material":"dramatic","lights":"spot+rim","shadow":true}`
- **时长**: 3.5s | **缓动**: cinematicSlow (ease 90/50)

### 6.5 后续扩展方向 (Phase 3.3)
- `3d_neon_pulse` - 霓虹脉冲（材质+Glow+彩色Point Light闪烁）
- `3d_explode_assemble` - 爆炸组装（逐字Position/Rotation随机→归位）
- `3d_glass_env` - 玻璃环境光（高Specular+低Diffuse+Ambient:80）
- `3d_kinetic_stagger` - 阶梯式3D入场（逐字Z+Opacity时序偏移）
- `3d_camera_orbit` - 环绕运镜（Parent Null Y旋转360°+DOF跟焦）

---

## 7. Element 3D 补充评估

### 7.1 已确认环境

```
插件路径: C:\Program Files\Adobe\...\Plug-ins\VideoCopilot\Element.aex
许可证: ElementLicense.license (已激活)
模型库: E3Dmodel\VideoCopilot\Models\ (Icosahedron, Primitives, Star等)
MCP工具: AfterEffectsMCP → e3d-load-model (已就绪)
```

### 7.2 Element 3D 优势场景

| 场景 | 原生AE | Element 3D |
|------|--------|-----------|
| 基础挤出+倒角 | ✅ 足够 | 过度 |
| 金属/玻璃PBR材质 | ⚠️ Advanced 3D可以 | ✅ 更成熟 |
| 自定义3D模型文字 | ❌ 不支持 | ✅ 导入OBJ/C4D |
| 多对象场景 | ❌ | ✅ Group系统 |
| 实时预览 | ⚠️ 需渲染 | ✅ GPU实时 |
| 粒子/碎片效果 | 需Particular | ✅ 内置碎片 |

### 7.3 结论

- **Phase 3 主线**: 使用原生 Cinema 4D / Advanced 3D 渲染器（纯ExtendScript可控，无GUI依赖）
- **Phase 3 补充**: 对需要高级材质（金属拉丝、玻璃折射、碳纤维）的预设，使用 Element 3D
- **Phase 4 远期**: 考虑 FontObj 脚本（文字→OBJ）+ Blender渲染联动（15-3D知识库已有基础）

---

## 8. 开发路线图（实施进度）

| 阶段 | 内容 | 状态 | 产出 |
|------|------|------|------|
| 3.0 | API探针: 3轮probe确认matchName+可写性 | ✅ 完成 | probe_3d_text*.jsx + 结果文件 |
| 3.1 | 模板引擎扩展: gen_phase3.js生成器 | ✅ 完成 | 4预设注入JSON, v3.0-alpha |
| 3.2 | 试点预设×4: 编写+AE内验证 | ✅ 完成 | 26/26 SUCCESS (含4个3D) |
| 3.3 | 品类扩展: 3d_title→15预设 | ⏳ 待启动 | 目标+11预设 |
| 3.4 | Element 3D集成: 高级材质预设×3 | ⏳ 待启动 | E3D探针 |
| **总计** | **~15个3D文字预设** | **40%完成** | |

### 验证管线

```
gen_phase3.js → config/text_animation_presets.json (v3.0-alpha, 91预设)
     ↓
gen_verify.js → temp/verify_phase3.jsx (Bridge → AE执行)
     ↓
ae_result.json → 26/26 SUCCESS
```

---

## 9. 风险与缓解（实证更新）

| 风险 | 实际结果 | 缓解措施 |
|------|----------|----------|
| Geometry Options不可写 | ⚠️ **已发生** - 完全锁定 | 层叠深度模拟(N层Z堆叠) |
| 渲染器不可切换 | ⚠️ **已发生** - renderer只读 | 使用默认Advanced 3D，不依赖Cinema4D |
| Camera/Light Position Z BUG | ⚠️ **已发生** - 除以零错误 | Camera Zoom动画替代Position Z |
| Per-char 3D无脚本触发 | ✅ 未发生 | Text Animator + ADBE Text Position 3D可用 |
| Material参数不可写 | ✅ 部分可用(7/17) | 使用可写的7个参数组合 |
| 渲染时间过长 | 未测试 | 待Phase 3.3渲染验证 |

---

## 10. 下一步行动

### 近期 (Phase 3.3)
1. **扩展3D预设至15个** - 基于已验证的4种技术模式组合扩展
2. **渲染验证** - aerender + ffmpeg截帧，确认3D预设视觉输出正确
3. **Showcase更新** - 将3D预设纳入gen_showcase.js渲染管线

### 中期 (Phase 3.4)
4. **Element 3D探针** - e3d-load-model MCP工具 + 文字挤出兼容性
5. **高级材质** - 金属拉丝/玻璃折射/碳纤维（E3D或Advanced 3D PBR）

### 技术债务
6. **Camera Position Z BUG** - 跟踪AE更新，可能在未来版本修复
7. **Geometry Options** - 关注Adobe是否开放ExtendScript写入（当前仅GUI可控）
