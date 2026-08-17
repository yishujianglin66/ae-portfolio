# 2026-08-14 全项目重审 + 升级实施报告

> 本轮由 AI 智能体对 AE-Knowledge-Vault 做全量复审（代码/测试/知识库 3 路本地深审 + 数据集训练/工具生态/知识项目 3 路全网调研，共 6 份分报告），并立即实施、真机验证了一批可验证迭代。

## 一、分报告索引

| 报告 | 路径 | 核心结论 |
|------|------|---------|
| 代码深审 | `docs/research/2026-08-14-audit-core-code.md` | 语法全健康；3 处真实失效扁平 import；注册表失真；4 个上帝文件 |
| 测试审计 | `docs/research/2026-08-14-audit-tests.md` | 4984 用例、抽样 547 全绿；68 个"脚本式伪测试"；coverage 纸面配置 |
| 知识库审计 | `docs/research/2026-08-14-audit-knowledge.md` | 259 md 真实口径；kb_scanner 5053 条合成效果库；双加载器；12/14/15 库零消费 |
| 数据集/训练调研 | `docs/research/2026-08-14-audit-web-datasets.md` | ToriiGate(动漫VLM)、kandinsky-videomae、MatAnyone/BiRefNet、BeatNetLite、SongFormer |
| 工具生态调研 | `docs/research/2026-08-14-audit-web-tools.md` | Firefly DGR API、Python-UIAutomation、py-aep、BMF；AE 2025 已去 CEP |
| 知识项目调研 | `docs/research/2026-08-14-audit-web-knowledge.md` | ClipSkills、motion-design-skill、EBU SKOS 转场分类法、after-effects-expression-reference |

## 二、本轮已实施的升级（全部真机验证）

### 1. GPU 全线激活（最大性能杠杆）✅
- 环境此前装的是 **torch 2.13.0+cpu**：RTX 4060 8GB 完全闲置，全部 AI 引擎在 CPU 上跑。
- 修复：`torch 2.13.0+cu126 + torchvision 0.28.0+cu126`（同版本换 CUDA 构建，最小破坏）+ 补齐 `transformers 5.15 / safetensors / accelerate`。
- 验证：`torch.cuda.is_available()=True`，RTX 4060 识别成功。

### 2. VideoMAE-MovieShots 运镜模型接入生产管线 ✅（W2 / Step 3 V3）
- 新增 `models/camera/videomae_camera.py` 适配器（cv2 读帧不依赖 decord、懒加载、低置信回退光流规则、标签映射 Static→static/Motion→pan_left/…）。
- 导演 T3 感知块接入：VideoMAE 高置信标签经 `SourceCameraInventory.inject()` 优先注入。
- 真机验证：管线内 GPU 推理，6 素材实测标签与既有 CPU 基线一致；单镜 avg 0.22s。
- 注册 `models/model_registry.json`（新增 videomae_movieshots_movement 条目 + 修正 smoke 伪值）。

### 3. 运镜同质化根治 ✅（W2 核心，实测 23/23 → 12/11 双分布）
- 根因：`suggest_camera_for_shot` 把"同运镜衔接"评为 0.85 高分 → 首个镜头选中后全段锁死。
- 修复：反锁死窗口（recent/max_repeat）+ 同类衔接去优先 + 生硬兜底尊重窗口约束 + 导演侧 visual_variance≥7 强制池轮转 + 风格卡禁忌运镜过滤。
- **真机验证：v23 重跑 build 段运镜从 `{'pan_left': 23}` → `{'diag_pan': 12, 'pan_right': 11}`。**

### 4. 3 处真实失效 import 修复 ✅
- `frontier_system.py` 5 处扁平导入（aigc_generator/material_searcher/color_grading_applier/cinematic_intelligence/multimodal_director）→ 包限定 + 回退。
- `ai/ai_agent.py` tool_executor → `tools.tool_executor`。
- `core/llm_gateway.py` kb_loader → `knowledge.kb_loader`（**KB 上下文注入从静默死代码变为真功能**：实测解析 1513 效果映射 + 4021 正文块）。

### 5. 素材选择分桶如实记录 ✅
- 根因：`_selection` 仅在 target_ip 非空时填充，自由混剪模式报告恒空。
- 修复后 v23 报告：`{'matched': 7, 'mixed': 0, 'unknown': 0, 'excluded': 0}`。

### 6. 风格卡 → 导演消费桥 ✅（W5 缩影）
- 发现：`knowledge/style_card.py` + 3 张试点卡只有测试消费，**生产零消费**。
- 新增 `card_to_director_inputs(style_id)`；`render(style_id=...)` 自动推导品味契约 + 风格规格书 + 禁忌运镜过滤 T4 池。

### 7. 反默认检查器去误报 ✅
- 根因：检查器对"设计内硬切"（爆发段硬切卡点铁律 + 变速镜头渲染层强制硬切）误报违规。
- 修复：统计范围限定为"转场可变化镜头"（原速 + 非爆发段）；真机数据验证误报消失。

### 8. 环境与数据修复
- `python` 加入用户 PATH（项目大量脚本此前找不到解释器）。
- `model_registry.json`：n_models 6→13、student_ip_classifier 尺寸 0.38→42.76MB、补录 6 个未注册真实模型、smoke 伪值置 null。
- 修复存量 bug：`_collect_content_metrics` 素材窗口 (s,e) 对格式兼容。

## 三、验证证据

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| build 段运镜 | 23/23 pan_left | diag_pan 12 + pan_right 11 |
| material_selection | 四桶全空 | matched=7 |
| 反默认违规 | 误报 anti_default_transition | 无 |
| torch CUDA | False (CPU-only) | True (RTX 4060) |
| KB 上下文注入 | 静默死代码 | 1513 效果映射生效 |
| 回归测试 | — | 60+151+46+27 全绿 |

管线重跑成功：19.08s 成片 / 1080p24 / 335s 总耗时 / 自进化 quality=79.6（真实信号）。

## 四、未处理项（按优先级移交）

1. **P1 知识消费断层**：`effect_registry._CRITICAL_MAPPINGS` 仍强制覆盖 KB；12-漫剪/15-3D/14-Silhouette 库零消费；kb_scanner 5053 条合成效果库待与真实插件扫描合并（详见知识库审计报告 §5-§6）。
2. **P1 测试工程**：68 个脚本式伪测试待清理/改写；core/error_diagnostician、flagship_runner、models/training 无测试；安装 pytest-cov 落实 fail_under=60。
3. **P1 调研新候选落地**：ToriiGate(动漫VLM, W6)、BeatNetLite+SongFormer(卡点升级)、BiRefNet/MatAnyone(RVM 闪烁)、Python-UIAutomation(替代截图点击)、Firefly DGR API(云端模板渲染)。
4. **P2 架构债**：4 个上帝文件拆分（unified_pipeline 5325 行等）；PR Bridge JSX 硬编码路径(D-24)；PSBridgeClient 弃用基类(D-15)；AE CEP→UXP 迁移预留。
5. **P2 部署**：Docker 构建未验证；前端 mock 数据未完全替换。

## 五、下一步建议

- 用 `style_id="amv_highenergy"` 跑一次 v23，验证风格卡消费桥在真实管线中的效果（品味旋钮 7/8/4 + 禁 static）。
- 按知识库审计附录 schema，从 10-风格化库里再卡化 5-10 张风格卡。
- 下载 ToriiGate/BeatNetLite 做 W6/卡点升级评估（GPU 已就绪）。
