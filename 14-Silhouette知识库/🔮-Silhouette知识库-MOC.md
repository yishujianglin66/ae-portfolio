# 🔮 Silhouette 知识库总览

> Silhouette 是 Boris FX 旗下的专业 Rotoscoping、Paint 修复与跟踪工具，广泛应用于电影、电视剧、广告及流媒体的视觉特效制作。本知识库涵盖 API 参数、操作指南、深度研究、故障排查、实战案例与代码模板。

---

## 📂 目录结构

```
14-Silhouette知识库/
│
├── 🔮-Silhouette知识库-MOC.md                    # 本文件 - 知识库索引
├── Silhouette知识库完整性检查报告.md              # 知识库完整性报告
│
├── 📚 API与参数手册（11篇）
│   ├── Silhouette 节点类型完全参数库.md
│   ├── Silhouette 属性类型完全手册.md
│   ├── Silhouette Python API 速查手册.md
│   ├── Silhouette fx API 参数详解手册.md
│   ├── Silhouette 对象模型与继承体系.md
│   ├── Silhouette 事件系统与回调机制.md
│   ├── Silhouette 环境变量与全局配置.md
│   ├── Silhouette 脚本调试与日志系统.md
│   ├── Silhouette 数学与几何工具库.md
│   ├── Silhouette IO模块与文件操作.md
│   └── Silhouette 渲染引擎与输出系统.md
│
├── 🎨 Roto抠像专题（12篇）
│   ├── Silhouette X-Spline与Bézier曲线详解.md
│   ├── Silhouette 形状层与关键帧动画.md
│   ├── Silhouette 边缘优化与运动模糊.md
│   ├── Silhouette 智能遮罩与AI辅助抠像.md
│   ├── Silhouette 毛发与半透明物体抠像.md
│   ├── Silhouette 硬边与柔边遮罩技巧.md
│   ├── Silhouette 多形状管理与层级控制.md
│   ├── Silhouette 遮罩混合与布尔运算.md
│   ├── Silhouette Roto工作流最佳实践.md
│   ├── Silhouette 逐帧与插值策略.md
│   ├── Silhouette 遮罩质量检查与优化.md
│   └── Silhouette Roto遮罩完全指南.md
│
├── 🎯 跟踪技术专题（10篇）
│   ├── Silhouette 平面跟踪完全指南.md
│   ├── Silhouette 点跟踪与多点跟踪.md
│   ├── Silhouette Paint跟踪修复技术.md
│   ├── Silhouette 跟踪数据导出与格式转换.md
│   ├── Silhouette 摄像机解算与3D跟踪.md
│   ├── Silhouette 稳定化与反向跟踪.md
│   ├── Silhouette 跟踪精度优化技巧.md
│   ├── Silhouette 运动匹配与偏移修正.md
│   ├── Silhouette 跟踪失败排查指南.md
│   └── Silhouette 跟踪技术实战手册.md
│
├── 🖌️ Paint修复专题（10篇）
│   ├── Silhouette 克隆与修复笔刷详解.md
│   ├── Silhouette Paint动画与序列修复.md
│   ├── Silhouette 去除威亚与物体擦除.md
│   ├── Silhouette 画面修复与数字化妆.md
│   ├── Silhouette Paint跟踪与自动修复.md
│   ├── Silhouette 笔刷参数与压力感应.md
│   ├── Silhouette 逐帧修复策略.md
│   ├── Silhouette Paint与Roto联合工作流.md
│   ├── Silhouette 修复质量评估标准.md
│   └── Silhouette Paint修复完全指南.md
│
├── 🔗 节点与合成系统（8篇）
│   ├── Silhouette 节点系统完全手册.md
│   ├── Silhouette 管线与合成工作流.md
│   ├── Silhouette 多通道输出与EXR工作流.md
│   ├── Silhouette 节点连接与数据流.md
│   ├── Silhouette 合成节点与混合模式.md
│   ├── Silhouette 遮罩节点与通道操作.md
│   ├── Silhouette 色彩校正节点.md
│   └── Silhouette 滤镜与效果节点.md
│
├── ⚡ 自动化与批处理（6篇）
│   ├── Silhouette 批处理与自动化脚本.md
│   ├── Silhouette 命令行执行与无头模式.md
│   ├── Silhouette 项目模板与预设系统.md
│   ├── Silhouette 渲染队列与批量输出.md
│   ├── Silhouette 自动化工作流设计.md
│   └── Silhouette 脚本性能优化.md
│
├── 🔌 集成与导出（8篇）
│   ├── Silhouette Matte序列导出指南.md
│   ├── Silhouette 跟踪数据AE导入规范.md
│   ├── Silhouette 与Nuke集成工作流.md
│   ├── Silhouette 与Premiere集成工作流.md
│   ├── Silhouette 立体3D工作流.md
│   ├── Silhouette 多软件协作流程.md
│   ├── Silhouette 导出格式参考手册.md
│   └── Silhouette 与AE集成工作流.md
│
├── ⚙️ 预设与配置（5篇）
│   ├── Silhouette 预设配置系统.md
│   ├── Silhouette 项目模板库.md
│   ├── Silhouette 渲染设置参考.md
│   ├── Silhouette 快捷键与操作技巧.md
│   └── Silhouette 界面自定义指南.md
│
├── 🔬 深度研究（6篇）
│   ├── Silhouette 在影视特效中的应用研究.md
│   ├── Silhouette 与其他Roto工具对比分析.md
│   ├── Silhouette AI辅助功能研究.md
│   ├── Silhouette 性能优化深度研究.md
│   ├── Silhouette 行业标准与质量规范.md
│   └── Silhouette 2026新功能速览.md
│
├── 🔧 故障排查与最佳实践（4篇）
│   ├── Silhouette 常见问题与解决方案.md
│   ├── Silhouette 脚本调试与错误处理.md
│   ├── Silhouette 项目管理最佳实践.md
│   └── Silhouette 团队协作工作流.md
│
├── 🎬 实战案例与教程（6篇）
│   ├── Silhouette 实战案例-人物抠像全流程.md
│   ├── Silhouette 实战案例-产品广告修复.md
│   ├── Silhouette 实战案例-特效合成辅助.md
│   ├── Silhouette 实战案例-运动跟踪合成.md
│   ├── Silhouette 实战案例-批量处理工作流.md
│   └── Silhouette 实战训练体系.md
│
└── 📁 案例模板/（26个Python脚本）
    ├── roto/（8个）
    │   ├── standard_keying.py
    │   ├── hair_keying.py
    │   ├── hard_edge_keying.py
    │   ├── soft_edge_keying.py
    │   ├── multi_shape_keying.py
    │   ├── ai_assisted_keying.py
    │   ├── garbage_matte.py
    │   └── holdout_matte.py
    ├── track/（6个）
    │   ├── planar_track.py
    │   ├── high_precision_track.py
    │   ├── fast_track.py
    │   ├── point_track.py
    │   ├── stabilize.py
    │   └── camera_solve.py
    ├── paint/（6个）
    │   ├── clone_repair.py
    │   ├── smart_repair.py
    │   ├── wire_removal.py
    │   ├── digital_makeup.py
    │   ├── sequence_repair.py
    │   └── object_removal.py
    ├── export/（4个）
    │   ├── ae_export.py
    │   ├── multi_channel_export.py
    │   ├── nuke_export.py
    │   └── tracking_data_export.py
    └── composite/（2个）
        ├── alpha_composite.py
        └── edge_blend.py
```

---

## 📑 分类索引

### 📚 API与参数手册（11篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette 节点类型完全参数库]] | 所有节点类型完整参数列表、默认值、取值范围、数据类型 |
| [[Silhouette 属性类型完全手册]] | Property 类体系、所有属性类型、动画曲线、表达式系统 |
| [[Silhouette Python API 速查手册]] | Python API 快速参考、常用函数、代码片段、最佳实践 |
| [[Silhouette fx API 参数详解手册]] | fx 模块完整 API：Project/Session/Node/Property/Port 类详解 |
| [[Silhouette 对象模型与继承体系]] | 对象层次结构、类继承关系、多态机制、内存管理 |
| [[Silhouette 事件系统与回调机制]] | 事件类型、回调注册、事件分发、自定义事件 |
| [[Silhouette 环境变量与全局配置]] | 环境变量列表、全局设置、配置文件、启动参数 |
| [[Silhouette 脚本调试与日志系统]] | 调试工具、日志级别、错误追踪、性能分析器 |
| [[Silhouette 数学与几何工具库]] | 向量运算、矩阵变换、几何计算、插值算法 |
| [[Silhouette IO模块与文件操作]] | 文件读写、项目管理、序列处理、格式支持 |
| [[Silhouette 渲染引擎与输出系统]] | 渲染管线、GPU加速、缓存机制、输出格式引擎 |

---

### 🎨 Roto抠像专题（12篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette X-Spline与Bézier曲线详解]] | X-Spline 与 Bézier 曲线原理、控制点操作、曲线转换 |
| [[Silhouette 形状层与关键帧动画]] | 形状层管理、关键帧插值、动画曲线、时间重映射 |
| [[Silhouette 边缘优化与运动模糊]] | 羽化控制、运动模糊参数、边缘检测、抗锯齿优化 |
| [[Silhouette 智能遮罩与AI辅助抠像]] | AI Roto 功能、智能边缘检测、机器学习模型、自动追踪 |
| [[Silhouette 毛发与半透明物体抠像]] | 发丝处理、半透明遮罩、颜色溢出抑制、细节保留技巧 |
| [[Silhouette 硬边与柔边遮罩技巧]] | 硬边遮罩技法、柔边过渡控制、边缘硬度调整 |
| [[Silhouette 多形状管理与层级控制]] | 形状组管理、层级结构、父子关系、可见性控制 |
| [[Silhouette 遮罩混合与布尔运算]] | 加/减/交运算、混合模式、遮罩组合、层级混合 |
| [[Silhouette Roto工作流最佳实践]] | 标准 Roto 流程、效率技巧、质量控制、团队协作规范 |
| [[Silhouette 逐帧与插值策略]] | 关键帧策略、插值算法、逐帧修复、运动估计 |
| [[Silhouette 遮罩质量检查与优化]] | QC 检查清单、常见缺陷、优化技巧、验收标准 |
| [[Silhouette Roto遮罩完全指南]] | Roto 节点完整操作手册、从入门到精通 |

---

### 🎯 跟踪技术专题（10篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette 平面跟踪完全指南]] | 平面跟踪原理、跟踪点布置、平面解算、透视校正 |
| [[Silhouette 点跟踪与多点跟踪]] | 单点跟踪、多点跟踪、特征点选择、跟踪器管理 |
| [[Silhouette Paint跟踪修复技术]] | 跟踪驱动 Paint、克隆源跟踪、运动路径修复 |
| [[Silhouette 跟踪数据导出与格式转换]] | 跟踪数据格式、导出选项、格式转换、数据清洗 |
| [[Silhouette 摄像机解算与3D跟踪]] | 摄像机反求、3D 空间点、解算参数、精度评估 |
| [[Silhouette 稳定化与反向跟踪]] | 画面稳定、反向跟踪、运动平滑、抖动去除 |
| [[Silhouette 跟踪精度优化技巧]] | 精度提升方法、参数调优、误差分析、亚像素精度 |
| [[Silhouette 运动匹配与偏移修正]] | 运动匹配、偏移调整、缩放旋转、手动微调 |
| [[Silhouette 跟踪失败排查指南]] | 常见跟踪失败原因、诊断方法、补救措施、预防策略 |
| [[Silhouette 跟踪技术实战手册]] | Tracker 节点完整指南、实战技巧与案例 |

---

### 🖌️ Paint修复专题（10篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette 克隆与修复笔刷详解]] | Clone Brush 工作原理、笔刷类型、取样技巧、压力感应 |
| [[Silhouette Paint动画与序列修复]] | 动画序列修复、帧间一致性、时间克隆、运动模糊 |
| [[Silhouette 去除威亚与物体擦除]] | 威亚去除技巧、物体擦除方法、背景重建、纹理合成 |
| [[Silhouette 画面修复与数字化妆]] | 皮肤修饰、疤痕去除、皱纹处理、数字化妆技术 |
| [[Silhouette Paint跟踪与自动修复]] | 跟踪驱动 Paint、自动修复流程、批量处理、AI辅助 |
| [[Silhouette 笔刷参数与压力感应]] | 笔刷参数详解、压感设置、笔刷预设、自定义笔刷 |
| [[Silhouette 逐帧修复策略]] | 逐帧修复方法、效率优化、质量控制、批量处理 |
| [[Silhouette Paint与Roto联合工作流]] | Paint 与 Roto 协同、遮罩辅助修复、分层工作流 |
| [[Silhouette 修复质量评估标准]] | 修复质量指标、QC 流程、验收标准、常见问题 |
| [[Silhouette Paint修复完全指南]] | Paint 节点完整操作手册、修复技术大全 |

---

### 🔗 节点与合成系统（8篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette 节点系统完全手册]] | 节点系统架构、节点类型、节点图操作、生命周期 |
| [[Silhouette 管线与合成工作流]] | 节点管线设计、合成流程、层管理、渲染顺序 |
| [[Silhouette 多通道输出与EXR工作流]] | EXR 多通道、通道命名、分层输出、工作流整合 |
| [[Silhouette 节点连接与数据流]] | 端口连接、数据流动、节点图优化、缓存机制 |
| [[Silhouette 合成节点与混合模式]] | 合成算法、混合模式、Alpha 处理、数学运算 |
| [[Silhouette 遮罩节点与通道操作]] | 遮罩节点类型、通道操作、遮罩生成、通道分离 |
| [[Silhouette 色彩校正节点]] | 颜色空间、调色工具、曲线调整、色彩匹配 |
| [[Silhouette 滤镜与效果节点]] | 模糊锐化、变形扭曲、噪点颗粒、风格化效果 |

---

### ⚡ 自动化与批处理（6篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette 批处理与自动化脚本]] | 批处理脚本编写、批量处理框架、错误处理、进度监控 |
| [[Silhouette 命令行执行与无头模式]] | CLI 参数、无头渲染、脚本执行、远程调用 |
| [[Silhouette 项目模板与预设系统]] | 项目模板创建、预设保存加载、参数继承机制 |
| [[Silhouette 渲染队列与批量输出]] | 渲染队列管理、批量输出、优先级控制、错误恢复 |
| [[Silhouette 自动化工作流设计]] | 工作流架构、自动化模式、触发器、条件分支 |
| [[Silhouette 脚本性能优化]] | 性能瓶颈分析、优化技巧、内存管理、并行处理 |

---

### 🔌 集成与导出（8篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette Matte序列导出指南]] | Matte 导出设置、序列格式、命名规范、质量控制 |
| [[Silhouette 跟踪数据AE导入规范]] | AE 导入格式、数据映射、常见问题、最佳实践 |
| [[Silhouette 与Nuke集成工作流]] | Nuke 桥接、脚本交换、节点对应、工作流整合 |
| [[Silhouette 与Premiere集成工作流]] | Premiere 集成、序列交换、动态链接、协作流程 |
| [[Silhouette 立体3D工作流]] | 立体 3D 制作、左右眼同步、视差调整、深度控制 |
| [[Silhouette 多软件协作流程]] | 跨软件协作、数据交换、版本同步、资产管理 |
| [[Silhouette 导出格式参考手册]] | 所有导出格式详解、参数说明、兼容性、适用场景 |
| [[Silhouette 与AE集成工作流]] | AE 桥接规范、MCP 协议、数据格式、集成工作流 |

---

### ⚙️ 预设与配置（5篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette 预设配置系统]] | 预设 JSON 结构、参数覆盖、场景匹配、自动加载 |
| [[Silhouette 项目模板库]] | 项目模板分类、模板参数、使用方法、自定义模板 |
| [[Silhouette 渲染设置参考]] | 渲染参数详解、输出设置、缓存配置、性能调优 |
| [[Silhouette 快捷键与操作技巧]] | 快捷键大全、操作技巧、效率提升、自定义快捷键 |
| [[Silhouette 界面自定义指南]] | 界面布局、工作区、面板管理、主题定制 |

---

### 🔬 深度研究（6篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette 在影视特效中的应用研究]] | 电影/电视剧/广告应用案例、行业标准、工作流定位 |
| [[Silhouette 与其他Roto工具对比分析]] | vs Mocha Pro/NUKE Roto/AE Roto Brush 功能与性能对比 |
| [[Silhouette AI辅助功能研究]] | AI Roto/Paint/Track 原理、机器学习模型、精度评估 |
| [[Silhouette 性能优化深度研究]] | CPU/GPU 利用率、内存优化、磁盘 IO、硬件配置建议 |
| [[Silhouette 行业标准与质量规范]] | 交付标准、QC 流程、验收标准、版本管理、色彩管理 |
| [[Silhouette 2026新功能速览]] | 2026 版本 AI 增强、GPU 优化、API 更新、升级指南 |

---

### 🔧 故障排查与最佳实践（4篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette 常见问题与解决方案]] | 按类别 FAQ：安装/渲染/脚本/跟踪/Roto/Paint/性能/AI |
| [[Silhouette 脚本调试与错误处理]] | 常见脚本错误、调试技巧、异常处理框架、最佳实践 |
| [[Silhouette 项目管理最佳实践]] | 项目目录结构、命名规范、版本控制、备份策略 |
| [[Silhouette 团队协作工作流]] | 多人协作、任务分配、合并策略、冲突解决、审查流程 |

---

### 🎬 实战案例与教程（6篇）

| 文档 | 内容概要 |
|------|---------|
| [[Silhouette 实战案例-人物抠像全流程]] | 从素材分析到最终输出：分层 Roto、头发处理、Paint 修复 |
| [[Silhouette 实战案例-产品广告修复]] | 产品广告：灰尘去除、标签去除、反光修复、皮肤美化 |
| [[Silhouette 实战案例-特效合成辅助]] | 为特效合成提供遮罩与跟踪数据：分层遮罩、多通道输出 |
| [[Silhouette 实战案例-运动跟踪合成]] | 运动跟踪驱动的合成：人物跟踪、场景稳定、数据导出 |
| [[Silhouette 实战案例-批量处理工作流]] | 批量处理 150 个镜头：镜头清单管理、批处理脚本、错误恢复 |
| [[Silhouette 实战训练体系]] | 五级能力模型、练习项目、技能评估、12 周学习计划 |

---

## 📁 案例模板索引（26个）

### 🎨 Roto 模板（8个）

| 模板 | 路径 | 功能说明 |
|------|------|---------|
| **标准抠像** | `案例模板/roto/standard_keying.py` | 标准 Roto 抠像管线，适用于大多数场景 |
| **毛发抠像** | `案例模板/roto/hair_keying.py` | 头发专用抠像，处理发丝细节与半透明效果 |
| **硬边抠像** | `案例模板/roto/hard_edge_keying.py` | 硬边遮罩抠像，适用于边缘清晰的物体 |
| **柔边抠像** | `案例模板/roto/soft_edge_keying.py` | 柔边遮罩抠像，羽化边缘自然过渡 |
| **多形状抠像** | `案例模板/roto/multi_shape_keying.py` | 多形状组合抠像，层级管理与布尔运算 |
| **AI辅助抠像** | `案例模板/roto/ai_assisted_keying.py` | AI 智能辅助抠像，自动边缘检测与追踪 |
| **垃圾遮罩** | `案例模板/roto/garbage_matte.py` | Garbage Matte 快速粗略遮罩，排除无关区域 |
| **保留遮罩** | `案例模板/roto/holdout_matte.py` | Holdout Matte 保留区域遮罩，控制合成范围 |

### 🎯 跟踪模板（6个）

| 模板 | 路径 | 功能说明 |
|------|------|---------|
| **平面跟踪** | `案例模板/track/planar_track.py` | 平面跟踪管线，含数据导出与透视校正 |
| **高精度跟踪** | `案例模板/track/high_precision_track.py` | 高精度跟踪配置，亚像素精度与误差控制 |
| **快速跟踪** | `案例模板/track/fast_track.py` | 快速跟踪模式，平衡速度与精度 |
| **点跟踪** | `案例模板/track/point_track.py` | 点跟踪管线，多点跟踪与数据管理 |
| **稳定化** | `案例模板/track/stabilize.py` | 画面稳定，抖动去除与运动平滑 |
| **摄像机解算** | `案例模板/track/camera_solve.py` | 3D 摄像机解算，空间点重建 |

### 🖌️ Paint 模板（6个）

| 模板 | 路径 | 功能说明 |
|------|------|---------|
| **克隆修复** | `案例模板/paint/clone_repair.py` | 克隆修复管线，时序克隆与跟踪驱动 |
| **智能修复** | `案例模板/paint/smart_repair.py` | 智能修复算法，自动纹理合成与填充 |
| **威亚去除** | `案例模板/paint/wire_removal.py` | 威亚去除专用，多帧融合与背景重建 |
| **数字化妆** | `案例模板/paint/digital_makeup.py` | 数字化妆与皮肤修饰，频率分离技术 |
| **序列修复** | `案例模板/paint/sequence_repair.py` | 序列帧批量修复，帧间一致性保持 |
| **物体移除** | `案例模板/paint/object_removal.py` | 物体擦除，大面积区域重建与修复 |

### 📤 导出模板（4个）

| 模板 | 路径 | 功能说明 |
|------|------|---------|
| **AE导出** | `案例模板/export/ae_export.py` | 导出 AE 兼容的遮罩与跟踪数据 |
| **多通道导出** | `案例模板/export/multi_channel_export.py` | 多通道 EXR 导出，含通道清单与命名规范 |
| **Nuke导出** | `案例模板/export/nuke_export.py` | Nuke 格式导出：遮罩/跟踪/形状/脚本模板 |
| **跟踪数据导出** | `案例模板/export/tracking_data_export.py` | 多格式跟踪数据导出（AE/Nuke/Boujou/JSON/CSV） |

### 🔗 合成模板（2个）

| 模板 | 路径 | 功能说明 |
|------|------|---------|
| **Alpha合成** | `案例模板/composite/alpha_composite.py` | Alpha 通道合成，含多层合成支持 |
| **边缘融合** | `案例模板/composite/edge_blend.py` | 边缘融合：溢出抑制/光包裹/色彩匹配/噪点匹配 |

---

## ⚙️ 预设配置系统索引

### 8 个内置预设与模板对应关系

| 预设编号 | 预设名称 | 类型 | 对应模板 | 关联文档 | 适用场景 |
|---------|---------|------|---------|---------|---------|
| **01** | **Roto_Standard** | 节点预设 | `roto/standard_keying.py` | [[Silhouette Roto遮罩完全指南]] | 通用标准抠像场景 |
| **02** | **Roto_Hair** | 节点预设 | `roto/hair_keying.py` | [[Silhouette 毛发与半透明物体抠像]] | 头发与半透明物体抠像 |
| **03** | **Track_Planar** | 节点预设 | `track/planar_track.py` | [[Silhouette 平面跟踪完全指南]] | 平面跟踪与透视匹配 |
| **04** | **Track_Stabilize** | 节点预设 | `track/stabilize.py` | [[Silhouette 稳定化与反向跟踪]] | 画面稳定与抖动去除 |
| **05** | **Paint_Clone** | 节点预设 | `paint/clone_repair.py` | [[Silhouette 克隆与修复笔刷详解]] | 克隆修复与瑕疵去除 |
| **06** | **Paint_WireRemoval** | 工作流预设 | `paint/wire_removal.py` | [[Silhouette 去除威亚与物体擦除]] | 威亚与 unwanted 物体移除 |
| **07** | **Export_MultiChannel_EXR** | 输出预设 | `export/multi_channel_export.py` | [[Silhouette 多通道输出与EXR工作流]] | 多通道 EXR 高质量输出 |
| **08** | **VFX_Standard_Pipeline** | 项目预设 | 多模板组合 | [[Silhouette 管线与合成工作流]] | 标准 VFX 全流程项目 |

> 💡 **预设使用说明**：预设系统详细配置方法请参考 [[Silhouette 预设配置系统]]，模板使用方法请参考 [[Silhouette 项目模板库]]。

---

## 🎯 核心模块速查

| 模块 | 说明 | 关键文档 |
|------|------|---------|
| **fx** | Silhouette 内置脚本模块 | [[Silhouette fx API 参数详解手册]] |
| **Node** | 节点基类，创建处理节点 | [[Silhouette 节点类型完全参数库]] |
| **Property** | 属性类，设置节点参数 | [[Silhouette 属性类型完全手册]] |
| **Session** | 会话管理 | [[Silhouette fx API 参数详解手册]] |
| **Project** | 项目管理 | [[Silhouette fx API 参数详解手册]] |
| **RotoShape** | 动态遮罩 | [[Silhouette Roto遮罩完全指南]] |
| **Paint** | 图像修复 | [[Silhouette Paint修复完全指南]] |
| **Tracker** | 跟踪 | [[Silhouette 跟踪技术实战手册]] |
| **AI** | AI 辅助功能（2026+） | [[Silhouette AI辅助功能研究]] |

---

## 🔄 工作流程

```
用户输入 → Intent识别 → 知识库检索 → 模板匹配 → Silhouette执行 → AE/Nuke集成
```

### 典型工作流

**工作流1：人物抠像**
```
素材分析 → [[Silhouette 实战案例-人物抠像全流程|人物抠像全流程]] → 分层Roto → Paint修复 → QC → 交付
  ↓ 模板: roto/hair_keying.py + roto/multi_shape_keying.py
```

**工作流2：特效合成辅助**
```
素材分析 → [[Silhouette 实战案例-特效合成辅助|特效合成辅助]] → 遮罩生成 → 跟踪数据 → 多通道EXR → Nuke合成
  ↓ 模板: roto/standard_keying.py + track/planar_track.py + export/multi_channel_export.py
```

**工作流3：批量处理**
```
镜头清单 → [[Silhouette 实战案例-批量处理工作流|批量处理工作流]] → 自动Roto → 渲染队列 → QC → 交付
  ↓ 模板: 批处理脚本 + 渲染队列管理
```

**工作流4：AE集成**
```
Silhouette Roto → [[Silhouette 与AE集成工作流|AE导出]] → AE集成 → 合成 → 输出
  ↓ 模板: export/ae_export.py + export/tracking_data_export.py
```

**工作流5：Paint修复**
```
瑕疵分析 → [[Silhouette Paint修复完全指南|Paint修复]] → 克隆/修复 → 跟踪驱动 → 质量检查
  ↓ 模板: paint/clone_repair.py + paint/smart_repair.py
```

---

## 📊 知识库统计

| 类别 | 文档数 | 脚本数 |
|------|--------|--------|
| 📚 API与参数手册 | 11 | - |
| 🎨 Roto抠像专题 | 12 | 8 |
| 🎯 跟踪技术专题 | 10 | 6 |
| 🖌️ Paint修复专题 | 10 | 6 |
| 🔗 节点与合成系统 | 8 | 2 |
| ⚡ 自动化与批处理 | 6 | - |
| 🔌 集成与导出 | 8 | 4 |
| ⚙️ 预设与配置 | 5 | - |
| 🔬 深度研究 | 6 | - |
| 🔧 故障排查与最佳实践 | 4 | - |
| 🎬 实战案例与教程 | 6 | - |
| **合计** | **86 文档** | **26 脚本** |

---

## 🔗 与其他知识库的关联

- **[[🎬-风格化剪辑知识库-MOC]]** — AE 风格化剪辑知识体系，与 Silhouette 集成
- **[[🏠-AE知识中心]]** — AE 知识库总中心
- **Roto-Brush-3与AI辅助遮罩实战** — AE Roto Brush 与 Silhouette 对比

---

## 🚀 快速入门

### 新手入门路径
1. 阅读 [[Silhouette fx API 参数详解手册]] 了解基础
2. 学习 [[Silhouette Roto遮罩完全指南]] 掌握核心操作
3. 按 [[Silhouette 实战训练体系]] 的 Level 1 开始练习
4. 使用 `roto/standard_keying.py` 模板快速开始

### 进阶学习路径
1. 深入 [[Silhouette AI辅助功能研究]] 了解 AI 能力
2. 学习 [[Silhouette 性能优化深度研究]] 提升效率
3. 参考 [[Silhouette 实战案例-人物抠像全流程]] 完成实战
4. 掌握 [[Silhouette 脚本调试与错误处理]] 开发自动化工具

### 团队管理路径
1. 参考 [[Silhouette 项目管理最佳实践]] 建立规范
2. 按 [[Silhouette 团队协作工作流]] 组织团队
3. 遵循 [[Silhouette 行业标准与质量规范]] 交付
4. 使用 [[Silhouette 实战案例-批量处理工作流]] 提升产能

---

> 更新日期: 2026-07-11
> 版本: 3.0（全面更新：86篇文档 + 26个模板，11大分类完整体系）
> 知识库完整性: [[Silhouette知识库完整性检查报告]]

---

> 返回 → [[🏠-AE知识中心]]
