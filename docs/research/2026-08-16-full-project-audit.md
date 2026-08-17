# 2026-08-16 全项目体检报告（Full Project Audit）

> 审查方法：6 个并行探索代理分别审查 core/、scripts/、集成层与木偶自动化、测试与仓库卫生、文档知识体系、数据资产；本地实际运行全量 pytest 与精选 pytest 验证。覆盖全库约 32GB、core 106 个模块（约 6 万行）、scripts 297 个脚本、tests 322 个测试文件（约 5100 个测试函数）、docs 与编号知识目录全部。
>
> 结论性质：本文只做诊断与建议，未改动任何代码。

---

## 一、总体结论

项目**工程创造力和"探测→固化→验证"的迭代文化非常强**，近一周 261 次提交、三条主线（推镜分类器 / BiRefNet 混合微调 / 木偶动画）均按期交付。但项目正处在一个典型的转折点：**单体仓库内积累了至少 6 套平行基础设施、3 处旁路架构、以及一次已发生的事故（6 个 JSX 桥接文件语法错误导致 PS/AU/ME 桥全部失效而无人察觉）**。再不收敛，维护成本会开始反噬交付速度。

最需要立即处理的 4 件事（详见 P0）：
1. 修复 6 个 JSX 语法错误（PS/AU/ME 桥自 08-14 起已死）。
2. 处理已提交进 git 的 680MB `cloud_birefnet.tar`（.git 已 741MB）。
3. 处理 62 个未提交变更（含 468 行的木偶引擎 v14 实装）。
4. 修复全量 pytest 被单个真模型测试整会话杀死的问题。

---

## 二、项目全景

### 2.1 规模

| 维度 | 数值 |
|---|---|
| 磁盘总占用 | ~32 GB（external/ 18G、tmp/ 4.3G、models/ 3.6G、output/ 2.3G、data/ 1.7G、.git/ 741MB…） |
| core/ | 106 个 .py，约 59,800 行 |
| scripts/ | 297 个 .py（另有 _archive/ 26 个） |
| tests/ | 322 个 test_*.py，约 5,139 个测试函数（其中约 70 个文件无任何 test 函数，实为脚本） |
| 根目录 | 229 个文件 + 110 个目录（含 72 张调试截图、31 个一次性 ps1、25 个 JSX、29 个散置 py） |
| 近一周提交 | 261 次（08-10 起），高度活跃 |

### 2.2 当前工作主线（来自 09-计划文件/2026-08-16 交接文档 + docs 近期文档）

1. **推镜分类器** — VideoMAE-MovieShots LoRA v3b 已接入生产，粗 4 类精度 77.3%，14 测试全绿。✅ 完成
2. **抠像 BiRefNet 混合微调** — 7283 对训练集，动漫域 IoU 0.9756，v17 定案 MOV 已过 AE 真机验证，云实例已关。✅ 完成
3. **木偶动画** — Blender 5.1 部件木偶引擎（v4 定版→v14 迭代中），62 部件分离、look_at 正立、Toon BSDF 3渲2 已通；下一步固化完整挥剑动画。🔄 进行中
4. 平行主线：AMV 卡点剪辑 Round 系列（round2~20，已验收）。

### 2.3 文档活跃度

活跃区已迁移到 `docs/research/`、`docs/process/`、`09-计划文件/` 三处；编号目录中仅 15（3D）与 13（素材）维持热度；`00-每日记录` 断更于 08-07，`TASK_STATUS.md` 停留在 07-28 的梁祝 v37，已名存实亡。

---

## 三、P0 — 紧急（已发生事故 / 持续造成损害）

### P0-1 六个 JSX 桥接文件语法错误，PS/AU/ME 桥自 08-14 起全部失效

提交 `2aa33fe`（08-14 "D-24桥接路径四级解析"）把候选路径数组写成**未加引号**的形式（已经 Node 解析验证为 SyntaxError，ExtendScript 解析阶段即失败，整个文件不执行）：

- `au_mcp_bridge.jsx:33`
- `ps_mcp_bridge.jsx:32`
- `photoshop_mcp_listener.jsx:49`
- `premiere_mcp_listener.jsx:44`
- `media_encoder_mcp_listener.jsx:44`
- `mcp_bridge_panel.jsx:17`

正确写法参照 `pr_mcp_bridge.jsx:62-71` / `ae_mcp_auto_listener.jsx:217-227`（带引号）。
旁证：`.media_encoder-mcp-bridge` 里最后的成功记录停在 08-11。错误已进 HEAD，无未提交修复；CI 无任何 JSX 语法检查故漏网。

**修复**：6 处加引号；CI 增加 JSX 语法门禁（node --check 或 esprima 扫全部 *.jsx，注意 ExtendScript 的 `#target`/`#include` 需预处理剥离）。

### P0-2 680MB tar 已提交进 git，仓库被撑爆

`cloud_birefnet.tar`（679,851,520 字节）被 commit `17cc10c`（08-15）以普通 blob 提交（非 LFS），是 `.git` 达 741MB 的主因。该文件是**早期打包方式的云端上传包，已被 `tmp/matting_cloud.tar` 流程取代，训练闭环已完成**——可删。

**修复**：`git rm --cached cloud_birefnet.tar` + 删工作区文件 + `.gitignore` 加 `*.tar`；如需回收 .git 体积，需 `git filter-repo` 重写历史（需协调，见方案阶段 1）。

### P0-3 62 个未提交变更悬空

含：木偶引擎 v14（engine.py +468 行，含多项真机验证结论）、M2 六个新 core 模块（visual_scorer 等，共约 1,900 行）、相机分类器精度修复（+101 行）、10 个探针脚本。当前分支 `feat/project-consolidation-v1` 上这些工作随时可能因误操作丢失。

**修复**：按主题拆成数个提交落库（探针脚本可先归档再提交）。

### P0-4 全量 pytest 不可运行：单个真模型测试杀死整个会话

本地实测：`tests/test_camera_decision.py::test_analyze_returns_label_and_confidence` 对 `nonexistent.mp4` 仍会走 `VideoMAEForVideoClassification.from_pretrained`（models/anime_camera_classifier.py:107），超过 pyproject 的 `--timeout=30`；Windows 下 pytest-timeout 线程模式**直接 os._exit 杀死整个会话**，连汇总都不输出。这也是 CI 只跑精选列表的根因。

**修复**：真模型/下载类测试加 `@pytest.mark.real_model` 并默认 deselect；`_ensure_model` 对不存在文件应快速失败而非尝试加载。

### P0-5（安全相关，顺带确认无事故）

`.env`/`.env.bak`/`.env.doubao`/`.mcp_secret` 均被 ignore 且从未进历史（`git log --all` 确认）✅。但注意 `pr_mcp_bridge.jsx:88` 等处注释写"签名验证默认关闭"而代码是 `SIGNATURE_ENABLED = true`，注释与代码矛盾，需统一口径；桥目录 `eval()` 执行命令文件仍是任意代码执行入口（单机工作区可接受，但需知情）。

---

## 四、P1 — 高优（重复实现 / 架构旁路 / 组织混乱）

### 4.1 桥接层：8 份复制粘贴的监听器 + 5 套 AE 客户端 + PR 五条通路

- AE 桥客户端 5 套：`ae/ae_command_client.py`（998 行，最完善）、`bridges/mcp_bridge_client.py`、`bridges/ae_mcp_client.py`（弃用转发）、`integrations/adobe_mcp_adapter.py:660-712` 内联、tests 硬编码版。
- PR 通路 5 条（npm CEP / pr_mcp_bridge.jsx / premiere_mcp_listener.jsx / pr_fullauto_startup.jsx / pr_bridge_core.jsx），其中 3 条共用 `.premiere-mcp-bridge` 目录但协议互不兼容。
- 8 份 JSX 监听器各自复制 JSON polyfill、轮询、日志样板；轮询间隔 500/1000ms 不一。
- 每个应用侧监听器都 `eval()` 命令文件；无关联 ID，`ae_result.json` 无法区分新旧响应（`adobe_mcp_adapter.py:685-695` 的 timestamp 判定会把历史残留结果当本次成功）。
- `adobe_mcp_adapter.py:660-712` `_execute_jsx_via_powershell` 名不副实（没用 PowerShell），且**把 PS/PR/IL/ME 的 JSX 全发到 AE 专属桥**；`:666` 用了全仓库不存在的 `AEKV_ROOT` 环境变量（真实名是 `AEKV_PROJECT_ROOT`）。
- 孤儿目录：`.media-encoder-mcp-bridge`（连字符版，零引用）、`bridges/.ae-mcp-bridge`、`bridges/.photoshop-mcp-bridge`、`bridges/.pr-mcp-bridge`、空目录 `ae-mcp-bridge/`。
- `knowledge_mcp_server.py` 未注册进 .mcp.json，孤儿服务器。
- `tests/test_mcp_bridge.py` 无 test 函数，import 即执行且写死 Documents 路径，pytest 收集会炸。

**金标准已存在**：`puppet-automation/src/engines/premiere/pr_bridge_client.py`（cmd_id 关联 + keepalive + 分级超时 + 异常 + ping），应反向推广到 AE/PS/AU/ME。

### 4.2 core/：synthesis_orchestrator 单点膨胀 + 三处架构旁路

- `synthesis_orchestrator.py` 是事实上的 god module：8 处函数内惰性 import 把 M6/M7/P2/P5/P8 全焊在 `_build_layer`（约 100 行 6 路 elif，本次 diff 又 +229 行）。应拆 layer_builders/。
- `visual_scorer.py` 公开绕过 `llm_gateway` 直连 DashScope（第三份 .env 解析、重复 HTTP 样板）；与 `visual_eval_gateway.py`（671 行）构成两套视觉评估，缓存目录都各一份。正确方向是把 qwen provider 注册进 gateway。
- 10 个 core 模块 `sys.path.insert` 全局污染；`beat_strength_engine.py:329` 硬编码小写绝对路径。
- 效果参数知识**四处事实源**：`synthesis_orchestrator.MATCH_PARAM_MAP` / `jsx_generator._EFFECT_PARAM_INDEX` / `plugin_fx_templates._PART_IDX` / `data/fx_registry.json`（键风格还互不一致）；且 `plugin_fx_templates.py` 定义了 `_PART_IDX` 字典后正文全用裸数字（79/87/91/104-107 行），字典成死代码，头部注释与字典本身还互相矛盾（pos=18 vs 19）。
- 三套字体子系统：`font_style_map.py`（新，质量最好）/ `font_manager.py` / `font_scanner.py`。
- 四个 2000+ 行巨石：`llm_gateway.py`(4061)、`jsx_keyframe_animator.py`(2847)、`experience_harvester.py`(1952)、`causal_engine.py`(1924)。
- 六个"进化/学习"模块相互惰性 import 成网，边界不清。
- `core/__init__.py` 文档串列了不存在的模块（cache_manager 等），文档与实物脱节。

### 4.3 core 新代码的具体 bug（未提交文件里）

- `visual_scorer.py:414-428` `_apply_actions`：对 `edit_fx` 三次嵌套判断、`pass` 空分支、`fx[parts[0]] = node.get("amount", 10.0)` 对 shake 硬取 `amount` 键而实际键名是 `amp`（参数写到不存在的键上）、一处不可达死代码。
- `visual_scorer.py:158-240` `cv2.VideoCapture` 无 try/finally，异常时句柄泄漏；未检查 `isOpened()`。
- `visual_scorer.py:136-150` 重试循环最后一次失败后仍 sleep（徒增 12 秒）。
- `synthesis_orchestrator.py:122,149` JS 注入无转义：`comp_name`/`layer.id` 含引号时生成非法 JSX。
- `synthesis_orchestrator.py:161-169` import 了 `grain_layer_jsx` 却从未使用，手工内联重复实现。
- `camera_movement_classifier.py:513-518` `__main__` 结果 print 复制了两遍（合并残留）；`:425-437` pickle 缓存无 schema 版本号且哈希只取 10 位有碰撞风险；`_read_frames` 与 `_read_frames_range` 约 90% 重复；投票+置信度公式在两处各维护一份。
- `composition_tree.py:299` 死变量 beats；与 `gen_fx_provider.py:35` 的 FX_KINDS 双事实源。

### 4.4 scripts/：一次性脚本区承载了库职责

- `scripts/__init__.py` 自称"一次性脚本，不构成核心库"，但 8 个模块被当库引用，其中**核心生产代码反向 import scripts**（`ai/production_director.py:671`、根 `frontier_system.py:153`）——依赖方向倒挂。
- 54 个脚本各自手写 bridge 协议（写 command.json + os.replace + 轮询 result.json），实现细节五花八门；`ae_automation.py:124` 的 `send_bridge_command()` 才是正解。
- 10 个 `_probe_*.py`（untracked、零引用、~80% 逐字重复）探测结论已固化进 `core/plugin_fx_templates.py`——可合并为一个参数化探针或直接归档。
- 明确可合并/归档组：collect 三件套、lk 三件套（结论已进 core）、distill_m0~m4（仅 scope 字符串不同）、eval_birefnet×3、tune_thresholds×3、psd_to_blender×2、batch_render_expand×2、e2e_style_beat×2、make_one_mov（997 行旧版 vs 185 行终版）、test_create_seq×3。
- 77 个文件含 `Users\Administrator` 绝对路径、25 个含 D 盘写死路径；`build_real_edit.py` 无 CLI 无 main guard，import 即执行整条渲染管线；全目录 107 处裸 `except:`。
- `run_ae_effects_full.py:373` 结束直接 `taskkill /F` 杀 AE，会丢用户未保存工程。
- `matanyone_pipeline.py` subprocess 调用藏在 `output/step2_locator/` 里的下划线脚本——脚本逃逸到产物目录。
- 正面：`build_matting_dataset.py`、`train_param_tuner.py`、`cloud_matting_pipeline.py` 等新脚本质量明显更高（argpath 自适应、manifest 溯源、固定 seed、轮询重连扎实）。

### 4.5 根目录与 core 平行的六处基础设施

| 根目录文件 | 与谁重叠 | 建议 |
|---|---|---|
| exceptions.py (1032行) | core/__init__ 声称有统一异常层级但 core 里没有 | 移入 core/ |
| logger.py (163行) | core/observability.py(1019) + 裸 logging（实际三套） | 三选一收口 |
| config_schema.py (701行) | core/config.py(1257) 双配置体系 | schema 校验并入 config |
| database.py (732行) | core/memory_store.py 两套 SQLite | 统一数据层 |
| frontier_system.py (811行) | 与 3 个 orchestrator 构成 4 层编排 | 归位或明确边界 |
| frame_enhancement_pipeline.py (696行) | core/frame_extractor 等；硬编码重灾区 | 改用 core/paths 后入 scripts/ |

另：`knowledge/` 与 `knowledge_base/` 是两套并行的知识加载代码（kb_loader.py 等同名不同实现），前者被 core/ai 引用、后者只被 knowledge_mcp_server 引用——新旧两代未收敛。

### 4.6 仓库卫生

- **203 个文件命中 ignore 规却仍在索引**（`git ls-files -ci --exclude-standard`）：data/ 137、output_production/ 35、ae-dashboard/ 13 等——ignore 规则后加未 `git rm --cached`，形同虚设。
- `.gitignore` 缺口：`analysis_out/`、`pytest_tmp/`、`.pytest_tmp/`、`.media-encoder-mcp-bridge/`（连字符版）、`.zcode/`、`test_output*/` 通配、`_probe_*.py`、`_run_*.py`、`.tmp_*`。
- `*.png`/`*.ps1`/`*.vbs` 全局通配过激，与已追踪文件打架（建议收敛为 `/*.png` 根目录限定）。
- pyproject：dev extras 缺 `pytest-timeout`（addopts 用了它，本地装完 dev 跑 pytest 直接报错）；`[tool.flake8]` 段是死配置（flake8 不读 pyproject）；CI 精选列表包含被 conftest 排除的 `test_safe_lut_path.py`。
- pre-commit 配置存在（含 500KB 大文件拦截）但 680MB tar 照样进了库——hook 未真正生效。
- `SIGNATURE_ENABLED` 注释与代码矛盾（见 P0-5）。

### 4.7 测试体系

- 约 2/3 core 模块有测试、1/3（28 个）完全无测试——包括本次 6 个新模块全部裸奔。
- 70 个 test_*.py 无任何 test 函数（占 22%），靠 conftest 硬编码排除表 + 08-15 的启发式（含 sys.exit 即忽略）兜底——排除表本身成了维护负担。
- 11 个注册 marker 大多闲置（slow 仅 1 文件在用），真模型/重渲染测试没有隔离机制（导致 P0-4）。
- CI 只跑精选列表 + smoke，质量门（合成素材 E2E）设计合理。
- 精选子集健康度实测：与未提交改动相关的 37 个测试 3.65s 全绿 ✅。

### 4.8 数据与模型资产

- 大文件 33 个 >50MB；可立即回收约 8-10GB：birefnet 旧 checkpoint ×2（845M×2，保留 _mixed/_fp16/底模）、`models/ms_cache/` 578M（HF 缓存，应重定向 HF_HOME）、`tmp/` 4.3G（matting_cloud.tar 598M + cloud_bundle 598M 双份冗余 + renders 1.8G）、SD1.5 底模 4.0G（可重下）。
- `external/animeshooter/dataset_anime_shooter.zip` 6.2G zip 与解压版双留。
- 版本化两套注册表口径不一（model_registry/registry.json 3 个 vs models/model_registry.json 13 个，后者含绝对路径；前者记录 jsx-code-generator status: artifact_missing）。
- models/ 代码与权重混居；`models/output/anime_camera_lora*` 系列（README+meta.json+adapter_config）是版本化的正面样板，应推广为标准。
- data/ 无数据字典；但 `data/versions/`（v001-v047 + decision_log.jsonl）是优秀的自动化数据集版本管理实践。
- 产物目录无治理：output/ 285 条平铺混放调试脚本与成片、output_production/ 用 epoch 秒命名、reports/ accept_*.json 只增不减、无保留策略。

### 4.9 文档体系

- 过程记录五处分裂无互链：00-每日记录（断更）/ 03-阶段报告（空窗10天）/ docs/process / docs/research round* / 09-计划文件。
- 根目录导航全部陈旧 3-4 周（🏠-AE知识中心、知识分类索引、工具链集成总览、TASK_STATUS.md），不覆盖 8 月新增区域（docs/research、09-计划文件、15-3D）。
- 同主题三处存放：梁祝-扇子（根 TASK_STATUS + 根全记录 md + 15-3D 目录）、DeepSeek-V4（根规划 vs docs 报告）、AE_Manga_Edit_Knowledge.md（根 272KB vs 10-风格化剪辑知识库）。
- 编号规范破坏：两个 99- 目录；audit 系列 6 篇（08-14）结论未回流索引。

---

## 五、做得好的地方（应保持并推广）

1. **"真机探测→结论固化→带出处注释"文化**：`core/plugin_fx_templates.py` 头部注明探测脚本与日期；docs/research 记录每一轮迭代的参数与画面占比数据（3.8%→10.1%）。这是整个项目最值钱的方法论。
2. **composition_tree 作为纯数据模型零依赖**——分层正确，是好的架构锚点。
3. **pr_bridge_client.py 的 cmd_id + keepalive + 分级超时**——桥接协议金标准，值得推广到全部应用。
4. **data/versions/ 自动化数据集版本管理 + decision_log**。
5. **安全习惯**：.env 从未进历史、.mcp.json 用 `${env:...}` 引用、CI 内嵌密钥扫描 + detect-secrets 双保险。
6. **模型产物版本化样板**：models/output/anime_camera_lora*（README+meta+config）。
7. **新脚本质量趋势向好**：train_param_tuner/build_matting_dataset/cloud_matting_pipeline 等明显比历史脚本（dir1-7、puppet 系列）规范。
8. **交接文档文化**：09-计划文件的全项目同步文档让跨会话接力成为可能。

---

## 六、行动方案

### 阶段 0：止血（半天内）

| # | 动作 | 验证 |
|---|---|---|
| 0.1 | 修复 6 处 JSX 引号错误（照抄 pr_mcp_bridge 写法） | node/esprima 扫全部 *.jsx 通过；真机开 PS 桥发一条 ping |
| 0.2 | `git rm --cached cloud_birefnet.tar` + 删工作区副本 + .gitignore 加 `*.tar`（同时把 tmp/ 两份 598M 上传包删除，云端训练已闭环） | git status 干净 |
| 0.3 | 62 个未提交变更按主题分组提交（分类器精度修复 / M2 六模块 / 木偶 v14 / 探针归档） | 每组跑对应精选测试 |
| 0.4 | visual_scorer 三处 bug（amount/amp 键名、VideoCapture 泄漏、末次 sleep）、camera_classifier 重复 print | pytest 精选全绿 |
| 0.5 | test_camera_decision 真模型测试加 real_model marker 默认跳过 | 全量 pytest 能跑完出汇总 |

### 阶段 1：仓库瘦身与卫生（1 周）

1. `.gitignore` 修补清单落地（见 4.6）；对 203 个 tracked-but-ignored 批量 `git rm -r --cached`。
2. 根目录清理：72 张截图、31 个 ps1、_run/_verify/_measure 临时件移入 `archive/debug-screenshots/` 或删除；25 个根目录 JSX 迁入 `jsx/bridges/<app>/`；根目录 md 按主题归入编号目录。
3. 大文件回收 ~8GB（birefnet 旧 ckpt、ms_cache、tmp/、animeshooter zip 二选一、SD 底模移出）。
4. `git filter-repo` 清 cloud_birefnet.tar 历史（需团队协调：备份 → 重写 → 强推 → 全员 re-clone；单人仓库风险低）。可选，不做也能活。
5. scripts/ 归档浪潮：_probe_×10、lk×3、distill_m0-m3、eval_birefnet×2、tune×2、psd_to_blender v1、batch_render v1、make_one_mov 旧版、test_create_seq×2 → `scripts/_archive/`；collect 三件套合并。
6. pre-commit 真正装上（`pre-commit install`），补 pytest-timeout 到 dev extras，删死配置 [tool.flake8]。
7. CI 加 JSX 语法门禁 + 修正精选列表与 conftest 排除表冲突。

### 阶段 2：架构收敛（2-4 周，与功能开发交替进行）

1. **桥接统一**：以 pr_bridge_client 模式为基类做 `bridges/base_client.py`（cmd_id + 发送前清结果 + 分级超时 + ping），AE/PS/AU/ME 五套客户端收口为一套；JSX 监听器抽公共 include；adobe_mcp_adapter 按应用路由；删 5 个孤儿桥目录。
2. **synthesis_orchestrator 拆分**：layer_builders/ 按 type 一文件，orchestrator 只做 校验→预备→编排→build→发送；JS 注入统一转义工具函数。
3. **四处效果参数事实源 → 一个效果注册表模块**（以 data/fx_registry.json 为数据、plugin 专表为扩展）。
4. **visual_scorer 收口**：qwen provider 注册进 llm_gateway，删除直连旁路与第三份 .env 解析。
5. **三套字体 → font_style_map 收口**；root 六件平行基础设施归位（exceptions/logger/config_schema/database/frontier_system/frame_enhancement_pipeline）。
6. **scripts 库化**：8 个被 import 的模块升格进 core/ 或独立包，恢复"scripts 不被核心依赖"的边界；54 个手写 bridge 协议的脚本迁移到统一客户端。
7. **knowledge/ vs knowledge_base/ 二选一**，另一个标 deprecated。
8. **puppet 三件套收拢**：puppeteer/engine.py 注册进 engines/registry.py，调色板/模型路径配置化，v14 提交后在 puppet-automation/README 明确与 puppet/、puppet_effects/ 的分层。

### 阶段 3：长效机制（持续）

1. 文档统一入口：更新 🏠-AE知识中心.md 为唯一导航（或明确废弃改用 09-计划文件），TASK_STATUS.md 停用并指向交接文档；audit 结论回流索引。
2. 产物治理：output 统一 `runs/YYYY-MM-DD_实验名/`，epoch 命名废弃，tmp/montages 30 天清理，成片母版移作品集归档。
3. 测试分层：real_model/real_render/integration marker 体系 + CI 按 marker 选择执行，目标全量套件可跑完；新 core 模块交付时必须带单测（本次 6 个新模块补齐）。
4. 模型注册表统一为 model_registry/registry.json 单一口径，models/output/ 版本化样板推广为标准。
5. 根目录防复发：pre-commit 大文件拦截生效 + 根目录新增文件需进 README 索引（或用脚本检查根目录文件数上限）。

---

## 七、预期收益

- 阶段 0：桥接功能恢复（PS/AU/ME 复活）、工作不再悬空、全量测试可运行。
- 阶段 1：仓库 -8GB 工作区、-640MB .git、根目录从 229 文件降到 <30、新人心智负担减半。
- 阶段 2：桥接代码量约减 60%，效果参数/字体/视觉评估单一事实源，synthesis_orchestrator 可维护。
- 阶段 3：交接成本从"读五个目录"降到"读一个入口"；产物不再无限增长。

---

*审查执行：ZCode（GLM-5.3），2026-08-16。方法：6 并行探索代理 + 本地实测（全量 pytest、精选 pytest、JSX 抽查、git 索引核查）。*
