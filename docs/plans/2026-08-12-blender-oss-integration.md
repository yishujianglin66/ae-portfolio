# Blender 生态开源项目集成方案

> 来源：GitHub 搜索 "blender" / "镜头追踪" / "抠像" 截图中约 30 个仓库的调研结果
> 日期：2026-08-12
> 现状基线：Blender 5.1.0（D:\Blender\Blender 5.1.0）、`puppet-automation/src/engines/blender/`（stage/cel-shading/render/camera export）、`bridges/blender_ae_bridge.py`、`mcp_blender` MCP（execute_blender_code / Polyhaven / Sketchfab / Hyper3D / Hunyuan3D）、`comfyui` 引擎、`sam2` 抠像流水线（batch_auto_frame 70GB 透明 mov）、`15-3D模型与骨骼动画知识库`

---

## 一、评估总表

| 项目 | 维护状态 | 与本项目契合点 | 结论 |
|------|---------|---------------|------|
| **UuuNyaa/blender_mmd_tools**（sugiany 原版的维护分支） | 活跃，支持 Blender 4.x | 导入 .pmx 模型 + .vmd 舞蹈动作 → cel-shading 渲染 → AE 合成（初音素材线） | **P1 集成** |
| **absolute-quantum/cats-blender-plugin** | 半停滞（2024-05），官方支持到 Blender 3.x | Fix Model / 自动减面 / 纹理图集 / 骨骼合并——MMD、Mixamo 模型一键清洗 | **P1 提炼复用**（不装插件，移植关键算子） |
| **hpc203/PP-MattingV2-onnxrun** | 可用（2023），纯 ONNXRuntime | 人像发丝级 alpha，免 prompt，速度远快于 SAM2 逐帧 | **P0 集成**（新 matting 引擎） |
| **RimoChan/modnet-entry** | 可用（2023），pip 可装 | 人像抠图极简 API；模型从 Google Drive 下载（国内网络风险） | P2 备选 |
| **jnulzl/cv_unet_image-matting**（BSHM ONNX） | 可用（2023） | 轻量人像抠图，单 onnx 文件 | P2 备选（matting 引擎的轻量档） |
| **stuffmatic/fSpy-Blender** | 停更（2022）但格式简单稳定 | 静态照片 → 相机标定 → Blender 相机 → `export_camera_data` → AE 重建机位 | **P1 集成** |
| **AIGODLIKE/ComfyUI-BlenderAI-node** | 活跃（2025-11，v2.0），官方推荐 Blender 3.5–4.0 | AI 材质生成/纹理烘焙、相机实时输入、ToonCrafter 补间、BiRefNet 抠图 | **P2 试点**（5.1 兼容性未验证；无头等价物走 comfyui 引擎） |
| **gd3kr/BlenderGPT** | 停更（2023-06），绑死 OpenAI GPT-4 | "自然语言 → bpy 脚本"模式 | **不装插件，P0 自建**：llm_gateway + mcp_blender 已具备全部能力 |
| **sobotka/filmic-blender** | 停更（2022） | 胶片色彩变换 | **不集成**：Blender 4.0+ 内置 AgX 已取代 Filmic |
| **KhronosGroup/glTF-Blender-IO** | 活跃 | glTF 2.0 导入导出 | **无需集成**：Blender 内置官方插件，`bpy.ops.export_scene.gltf` 直接用 |
| **sketchfab/blender** | 活跃 | Sketchfab 模型下载 | **不集成**：`mcp_blender` MCP 已覆盖（search/download_sketchfab_model） |
| **rlguy/Blender-FLIP-Fluids** | 活跃（付费插件，源码可见） | 高质量液体流体特效 | P3 按需（动漫水/饮料镜头） |
| **a1studmuffin/SpaceshipGenerator** | 可用（2024-05） | 程序化生成 3D 飞船 | P3 按需（科幻素材程序化生成范例） |
| **maximeraaf/BlenderNeRF** | 半活跃 | NeRF 合成数据集生成 | P3 研究向 |
| EpicGames/BlenderTools、xavier150/Blender-for-UnrealEngine、blender2ogre、BabylonJS/BlenderExporter、robmcrosby/BlenderUSDZ | — | 游戏引擎导出 | **不集成**：流水线无 UE/OGRE/Babylon/USDZ 目标 |
| CGCookie/retopoflow、hlorus/CAD_Sketcher、franMarz/TexTools-Blender、uhlik/bpy | 活跃 | 重拓扑/CAD 草图/UV 工具/点云 | **不集成**：交互式建模工具，非自动化流水线需求 |
| armory3d/armory、spatie/blender（PHP 同名） | — | 游戏引擎 / Laravel 模板 | **不集成**：与项目无关 |
| "镜头追踪"搜索结果（百度飞浆行人追踪、MediaPipe 手势玩具等） | — | — | **不集成**：学生竞赛项目，与相机追踪需求无关 |
| xd-tayde/matting、iosGrabcut、Brant-lzh/opencv_demo | 停更多年 | 传统抠图算法 | **不集成**：已被深度学习方法全面超越 |
| TommyLemon/CVAuto、AIFengheshu/Plug-play-modules | 活跃 | CV 测试工具 / 论文模块集 | **不集成**：非流水线组件 |

---

## 二、P0：立即实施（零新依赖 / 低风险）

### P0-1　matting 抠像引擎（PP-MattingV2，ONNXRuntime）

**动机**：当前抠像完全走 SAM2 子进程（venv-sam2 + torch），能力通用但对人像属于"杀鸡用牛刀"——需要 prompt/自动 mask 发现、逐帧推理重、显存占用高。batch_auto_frame 已产出 70.7GB 透明 mov，说明这是高频重负载环节。PP-MattingV2 是百度 PaddleSeg 的发丝级人像 matting 模型，ONNX 部署后**无需 paddle/torch，仅需 onnxruntime**，单帧 CPU 即可实时、GPU 更快，且免 prompt 全自动。

**接入方式**（遵循 engine-creation 六步流程）：

1. `puppet-automation/src/engines/matting/engine.py` 新建 `MattingEngine(BaseEngine)`，`name = "matting"`
2. 模型管理：`D:\AE-Work\models\matting\ppmattingv2_*.onnx`（从 hpc203 仓库的百度盘链接下载，18 个分辨率档位选 2–3 个常用档）；settings 加 `matting_model_dir: Path`
3. action 分发：
   - `human_matting`：单图/目录 → alpha + 透明 PNG/mov（复用现有 ffmpeg 引擎合成 ProRes 4444）
   - `batch_frames`：帧序列批处理，与 batch_auto_frame 流水线对齐
4. `main.py` 注册 + `/api/v1/matting/status|execute` 端点
5. `tests/test_matting_engine.py`：初始化、单图推理、模型缺失降级
6. **路由策略**：SAM2 保持通用抠像（非人主体、需语义指定目标）；matting 引擎负责人像全自动通道。服务层按"画面是否以人为主体"分流（可复用 `intent_classification` 走 llm_gateway，或直接按任务参数指定）

**预期收益**：人像抠像吞吐提升一个数量级，显存释放给 SAM2/ComfyUI；batch_auto_frame 类任务的人像场景可整体切换。

**依赖**：`onnxruntime-gpu`（Python312 环境安装即可，无 venv 隔离需求）。

### P0-2　"自然语言 → Blender 操作"服务（BlenderGPT 模式的自建版）

**动机**：BlenderGPT 验证了这个模式的价值，但它绑死 OpenAI GPT-4、仅英文、停更两年。**本项目已具备全部积木**：`llm_gateway.chat_with_routing(TaskType.code_generation)` 生成 bpy 脚本 + `mcp_blender` 的 `execute_blender_code` 执行 + BlenderEngine 的 background 渲染闭环。不需要装任何插件。

**接入方式**：

1. 服务层新增 `puppet-automation/src/services/blender_nl_service.py`：
   - 输入：自然语言指令（中文优先）+ 当前场景上下文（经 mcp_blender `get_scene_info` 注入 prompt）
   - Prompt 模板注入：`15-3D模型与骨骼动画知识库/07-Blender Python API参考/` 的速查片段作为 few-shot 上下文（知识库直接变现）
   - 生成代码 → 静态安全检查（禁止 `os.system`/`subprocess`/`__import__` 等）→ mcp_blender 执行 → `get_viewport_screenshot` 回传结果图 → LLM 自检失败时重试（最多 2 次）
2. API 端点 `/api/v1/blender/nl_execute`
3. 日志记录生成代码与执行结果，沉淀到知识库（成功用例回写为新的 few-shot）

**预期收益**：中文自然语言驱动 Blender，超越 BlenderGPT 原能力（多模型降级、中文、场景感知、自检闭环）。

### P0-3　色彩管理基线校正（不装 filmic-blender）

Blender 5.1 内置 **AgX** 视图变换，效果全面优于 filmic-blender（后者是 2017 年给 Blender 2.7x 的补丁）。行动项只有一个：在 BlenderEngine 的渲染模板中**显式固定** `scene.view_settings.look`/`view_transform`（如 `AgX - Medium High Contrast`），避免不同机器默认配置漂移导致 cel-shading 与 AE 合成端色彩不一致；调色终审仍走 DaVinci 引擎。

---

## 三、P1：近期实施（中收益 / 需适配）

### P1-1　MMD 内容线：mmd_tools（维护分支）+ cats 关键算子移植

**动机**：素材库有初音分类成品，`15-3D模型与骨骼动画知识库` 已覆盖 FBX/骨骼/蒙皮/武器归位。补上 MMD 一环后打通：**`.pmx 模型 + .vmd 动作 → cel-shading 渲染 → 透明序列帧 → AE 合成`**，这是动漫剪辑区的硬通货内容线。

**接入方式**：

1. 安装 [UuuNyaa/blender_mmd_tools](https://github.com/UuuNyaa/blender_mmd_tools)（sugiany 原版 2015 年已死，此分支支持 Blender 4.x；5.1 需实测，API 差异参考知识库 `07-11-Blender 4.x vs 5.x API差异.md`）
   - 部署位置：`D:\Blender\Blender 5.1.0\5.1\scripts\addons\mmd_tools`，并在 BlenderEngine 脚本模板开头 `bpy.ops.preferences.addon_enable(module="mmd_tools")` 幂等启用（background 模式同样生效）
2. BlenderEngine 新增 action：
   - `import_mmd(model_path, motion_path=None, scale=0.08)`：导入模型+动作，返回骨骼/材质清单
   - `render_mmd_cel(...)`：复用现有 `render_cel_animation` 管线输出
3. cats 插件**不整体安装**（官方止于 Blender 3.x，5.1 必炸），改为移植其纯 bpy 实现的关键清洗算子为引擎内脚本模块 `engines/blender/model_cleanup.py`：
   - Fix Model 等价物：合并网格、删除零权重骨骼、清理无用顶点组、合并同材质（cats 源码 `tools/armature.py`/`tools/common.py`，MIT 许可可移植）
   - Smart Decimation（保留 shapekey 的减面）——降低 MMD 模型在 Eevee 实时预览的负载
4. 测试：`tests/test_blender_mmd.py`（用一个轻量 .pmx 样本验证导入→渲染链路）

**风险**：cats 代码面向 Blender 2.8x API 编写，移植时需按 5.x API 适配（知识库有差异对照）；vmd 相机动作导入后走 `export_camera_data` 可同步给 AE。

### P1-2　fSpy 相机标定接入（静态镜头追踪）

**动机**：你搜索"镜头追踪"说明有"实拍/截图 → 恢复机位 → 叠加 3D 元素"的需求。fSpy（配套桌面应用，免费开源）对**静态图片**做消失点标定，fSpy-Blender 插件把 `.fspy` 工程导入为 Blender 相机——与引擎现有 `export_camera_data`（相机 JSON → AE 重建）正好首尾相接。

**接入方式**：

1. 人工或脚本在 fSpy 桌面端完成标定（一次性操作，每张参考图约 30 秒）
2. BlenderEngine 新增 action `import_fspy(fspy_path)`：插件核心就是解析 `.fspy`（JSON+zip）→ 设置 camera.data 的 lens/shift/旋转矩阵，fSpy-Blender 源码仅数百行且 GPL-3.0——**建议直接内化其解析逻辑**（`fspy_blender/core.py`）为引擎脚本，避免安装停更插件的 5.1 兼容风险
3. 闭环：`import_fspy` → 搭建 3D 前景 → `render_foreground_element`（alpha 序列）→ AE 叠加

**对"镜头追踪"需求的完整答案**：
- 静态图 → fSpy（本方案）
- 视频运动镜头 → Blender **内置** camera tracker（`bpy.ops.clip` 系，无需新依赖；可在引擎加 `track_camera` action 二期实现）
- 批量/高精度 SfM → COLMAP（开源标准，二期按需）
- 截图里的行人追踪/MediaPipe 玩具仓库全部不采用

---

## 四、P2/P3：试点与按需

### P2-1　ComfyUI-BlenderAI-node（AI 材质/纹理）

- **先做兼容性试点**：Blender 5.1 安装 v2.0 插件，验证节点编辑器能否连上项目现有 ComfyUI 服务（comfyui 引擎已管理 ComfyUI 进程，端口/路径从 settings 读取）
- 若 5.1 不兼容：**无头等价方案**——comfyui 引擎 + workflow_manager 直接跑 AI 纹理工作流（项目已有此能力），插件仅提供 GUI 便利，非必需
- 重点能力：AI 生成 PBR 材质 → EasyBakeNode 烘焙贴图 → MMD/程序化模型贴图增强；ToonCrafter 动漫补间

### P3（按需，不预投入）

- FLIP-Fluids：液体特效镜头时采购/编译（源码 GPL，可自行 build）
- SpaceshipGenerator：程序化资产生成参考实现
- BlenderNeRF：若未来做 NeRF/3DGS 数据集再说

---

## 五、实施路线图

| 阶段 | 内容 | 验收 |
|------|------|------|
| Step 1（P0） | matting 引擎骨架 + PP-MattingV2 单图链路 + 测试 | `pytest tests/test_matting_engine.py` 通过；样图发丝级 alpha 输出 |
| Step 2（P0） | blender_nl_service + `/api/v1/blender/nl_execute` | 中文指令"创建一个环绕相机的赛璐璐舞台"端到端成功 |
| Step 3（P0） | 渲染模板固定 AgX 配置 | cel 渲染与 AE 合成端色彩一致性抽查通过 |
| Step 4（P1） | mmd_tools 安装验证 + `import_mmd`/`render_mmd_cel` | 初音 .pmx + .vmd → cel 序列帧 → AE 合成 demo |
| Step 5（P1） | cats 清洗算子移植（model_cleanup.py） | MMD 模型一键清洗后骨骼/材质/面数指标达标 |
| Step 6（P1） | fSpy 解析内化 + `import_fspy` | 实拍照片标定 → 3D 元素叠加 AE 完成 demo |
| Step 7（P2） | ComfyUI-BlenderAI-node 5.1 兼容性试点 | 试点报告（可用则装，不可用则无头方案文档化） |

## 六、明确不集成清单（防止未来重复评估）

filmic-blender（AgX 取代）、sketchfab 插件（MCP 已覆盖）、BlenderGPT 插件（自建版取代）、glTF-Blender-IO（Blender 内置）、UE/OGRE/Babylon/USDZ 导出器（无目标引擎）、retopoflow/CAD_Sketcher/TexTools/bpy 点云（交互工具非流水线）、armory（游戏引擎）、spatie/blender（PHP 同名项目）、"镜头追踪"搜索全部仓库（学生项目）、xd-tayde/matting、iosGrabcut、opencv_demo（传统算法过时）、CVAuto、Plug-play-modules（非流水线组件）。
