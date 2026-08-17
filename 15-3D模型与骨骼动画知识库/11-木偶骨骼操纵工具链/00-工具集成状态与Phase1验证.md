# 木偶骨骼操纵 — 工具集成状态 + Phase 1 验证（2026-08-16）

## 一、工具集成状态（已装 Blender 5.1.0 Alpha）

| 工具 | 状态 | 验证结果 | 路径 |
|---|---|---|---|
| **Rigify** | ✅ 内置 | `RIGIFY_AVAILABLE` | Blender 自带（addons_core） |
| **GameRig** | ✅ 已装 | `gamerig_generate` 操作注册成功 | 用户 addons/gamerig |
| **Rokoko Studio Live** | ✅ 已装 | retargeting/fbx_patcher import OK | 用户 addons/rokoko_studio_live |
| StellarToon | ⏳ 已下载 | **需 Goo Engine**（Blender NPR fork），标准 5.1 不可用 → Phase 4 | /d/AE-Data/tools/blender_ext/ |
| MediaPipe | ❌ py3.12 无 wheel | 需 py3.11 环境 | — |
| CMU BVH | ⏳ 下载不稳 | Rokoko 插件已兜底动捕 | — |

安装位置：`C:\Users\Administrator\AppData\Roaming\Blender Foundation\Blender\5.1\scripts\addons\`
注意：GameRig 需先启用 rigify 再启用（依赖顺序），unregister 报错是退出噪音不影响功能。

## 二、关键发现：FBX vs OBJ

**3dsMax 导出的 FBX 有实例（instance）问题**：
- `shangguan_er.fbx`：8 个对象只有 1 个有几何（64 顶点），其余空壳
- `百里玄策-白虎志.FBX`：3 对象只有 1 个有效（1034 顶点）
- **OBJ 完整可靠**：百里玄策 OBJ 导入 8350 顶点完整

→ **管线改用 OBJ 作为导入源**（或修复 FBX 实例展开）

## 三、Phase 1 可行性验证（部件木偶）

百里玄策 OBJ → 按连通域分离（mesh.separate LOOSE）→ **62 个部件** ✅

- 模型是"游戏装备件"结构（头/发/身/四肢/武器分件）
- 62 部件 = 部件木偶方案的天然素材（每部件设 pivot 做关节旋转）
- 与方案一致：部件刚性挂接 + 关节 Empty/bone pivot，零蒙皮风险

## 四、下一步（Phase 1 开发）

1. 部件语义分类脚本：按 z 高度 + 尺寸 + 位置启发式把 62 部件归为 头/躯干/左臂/右臂/左腿/右腿/武器
2. 关节 pivot 创建：每关节建 Empty，部件 parent 挂接（Keep Transform）
3. 挥手/转身动画：驱动关节 Empty 旋转，验证零变形
4. 渲染对比：单帧 A/B（整体位移 vs 关节旋转）
