# 15-3D模型与骨骼动画知识库

> 基于上官婉儿三渲二动画项目的实战经验，覆盖从FBX导入到最终渲染输出的完整链路。
> 当前环境：Blender 5.1.0 Alpha | Python 3.11 | Windows
> 核心代码：`puppet-automation/src/engines/blender/cel_shading.py`

## 知识库规模

| 子目录 | 文档数 | 核心主题 |
|--------|--------|----------|
| 01-FBX导入与网格处理 | 12 | FBX格式、纹理路径、坐标系、缩放归一化 |
| 02-程序化骨骼创建 | 11 | Bone API、层级设计、A-pose策略 |
| 03-权重分配与蒙皮 | 11 | ARMATURE_AUTO、距离反比权重、验证方法 |
| 04-Parent与矩阵变换 | 11 | BONE parent、matrix_parent_inverse、矩阵组合 |
| 05-武器附件归位 | 11 | 手部检测、扇子组装、定位策略 |
| 06-Blender渲染管线 | 12 | Background模式、赛璐璐shader、相机动画 |
| 07-Blender Python API参考 | 12 | bpy.ops/data/context、版本差异 |
| 08-调试与诊断模式 | 11 | 日志解析、异常隔离、测试策略 |
| **总计** | **91** | |

## 问题→知识文档→代码修复 索引映射表

| 问题现象 | 根因 | 知识文档 | 代码位置 |
|----------|------|----------|----------|
| 发冠下沉一个bone length | parent_type='BONE'原点在TAIL非HEAD | [[04-01-parent_type_BONE的TAIL原点特性]] | cel_shading.py L928-946 |
| NameError: '_bc' is not defined | _v12_no_reposition跳过变量定义块 | [[08-04-try-except异常隔离与变量作用域]] | cel_shading.py L1486-1547 |
| 扇子在地面未贴合手部 | _v12_no_reposition=True跳过定位管线 | [[05-03-保持FBX原始位置vs重新定位]] | cel_shading.py L1483-1486 |
| FBX纹理路径全部为空 | 3dsMax导出贴图#N无FileName | [[01-03-纹理路径解析]] | FBX导入阶段 |
| ARMATURE_AUTO权重无效 | Heat Diffusion对分离部件失败 | [[03-06-常见蒙皮失败原因]] | cel_shading.py L817-821 |
| 渲染success=False但无Python异常 | Blender exit code≠0因C层Error | [[08-05-子进程管理与退出码]] | engine.py L1087 |
| 日志中文乱码(UTF-16) | PowerShell重定向编码问题 | [[08-02-UTF-16编码日志解析]] | 测试脚本输出 |
| bound_box与真实顶点不一致警告 | 旋转后bbox未更新(需view_layer.update) | [[07-09-mathutils数学库]] | cel_shading.py L1722 |
| 扇柄旋转后脱手 | 先移动后旋转→旋转绕物体原点 | [[05-05-旋转优先vs移动优先]] | cel_shading.py L1710-1741 |
| Material.use_nodes deprecated | Blender 5.x移除旧API | [[07-06-版本差异]] | 生成脚本 L678/874 |

## 快速排查清单（新模型适用）

遇到新FBX模型时，按以下顺序检查：

1. **导入检查**：`bpy.ops.import_scene.fbx()` 后检查 mesh_objects 数量、名称
2. **坐标系**：确认Y-up vs Z-up，检查模型是否"躺倒"
3. **缩放**：bounds_size 是否合理（目标6单位高度）
4. **纹理**：材质是否有有效贴图路径（3dsMax导出常为空）
5. **部件分类**：weapon/crown/face/body 名称匹配是否正确
6. **骨骼需求**：FBX是否自带Armature（无则需程序化创建）
7. **权重测试**：ARMATURE_AUTO是否有效（检查vertex_groups非空）
8. **配件位置**：FBX原始位置是否合理（扇子/发冠在哪）
9. **渲染测试**：单帧渲染确认模型在画面内、材质正确
10. **动画测试**：多帧渲染确认骨骼变形正常

## 文档格式规范

每篇文档统一包含：
- **问题场景**：什么情况下会遇到这个问题
- **核心原理**：底层机制解释
- **代码示例**：Blender Python可运行代码
- **常见陷阱**：易犯错误与解决方案
- **版本兼容**：Blender 5.1.0 Alpha注意事项
- **关联代码**：cel_shading.py中的对应行号
- **参考链接**：Blender官方文档/社区资源
