# 2026-08-16 阶段1仓库瘦身执行记录

> 承接 `docs/research/2026-08-16-full-project-audit.md` 阶段1方案。原则：**只动确定无引用的东西，不碰活跃链路**。全程零测试回归（JSX 门禁 259/0、pytest 收集 5038/5186 无错误）。

## 已完成

### 1. tracked-but-ignored 清理（203 项审计 → 处置 201 项）
`git rm --cached`（工作区文件全部保留，仅移出版本库）：
- data/ 运行产物 137 项（pipeline_runs 97 / models 展示图 17 / pipeline_feedback 14 / observability 7 / 其他 4）
- output_production/ 35、ae-dashboard 截图 13、test_outputs 6、ultralytics 缓存 2
- 根目录临时脚本 6（`_run_v23_v*.py`×4、`_verify_v24.py`、`_measure_alignment.py` → 随大扫除移入 archive）
- external/OpenMontage + external/rife：无 `.gitmodules` 的裸 gitlink（克隆只会得到空目录），移出索引，本地目录保留

**保留并加 .gitignore 白名单例外**（有意版本化的工具）：`install_adobe_bridges.ps1`、`D盘AE脚本管理器.ps1`、`close_dialog.ps1`、`puppet-automation/scripts/*.ps1`、`mcp-extension/install.ps1`、`05-测试套件/test_resources/*.png`。

### 2. 根目录大扫除（229 → 124 个文件）
72 张调试截图 + 31 个一次性 ps1 + vbs/wav/日志/调试 jsx + 6 个临时 py → `archive/root-cleanup-2026-08-16/`（本地归档，不版本化，已加 ignore 规则）。

**根目录 JSX 监听器本轮刻意不动**：它们被 AE Startup 加载器和面板按"项目根 + 文件名"路径引用（如 `mcp_bridge_panel.jsx:19`、`z_mcp_bridge_loader.jsx`），迁移必须先改引用链，留给阶段2桥接统一时一并处理。

### 3. scripts 归档浪潮（13 个，均验证零代码引用）
distill_m0-m3、tune_thresholds、tune_fine_thresholds、psd_to_blender v1、batch_render_expand v1、e2e_style_beat v1、eval_birefnet anime/coco、test_create_seq/sequence → `scripts/_archive/`。

**核实后不动的**：`make_one_mov_pipeline.py`（被 `matanyone_pipeline.py`/`_m4` 引用）；lk 三件套与 tune_camera_thresholds（昨日刚提交、相机线仍活跃）；collect 三件套（M2 管线在用，合并留待专门重构）。

### 4. 磁盘回收 ~3.1GB
- external/birefnet 被取代 checkpoint ×3（4.2G→1.7G；保留 `_mixed` 终版、`_fp16` 部署版、`model.safetensors` 底模）
- models/ms_cache HF 缓存 578M

**证据核查后否决了审计报告的两条建议**：
- ~~删 animeshooter zip~~ → 实查**只有 zip、没有解压版**，删=毁掉 6.2G 数据集
- ~~清 tmp/renders~~ → 实查含**本周新实验产物**（B0/B2 基线），tmp/ 整体未动

### 5. 工程配置
- pyproject：dev extras 补 `pytest-timeout`+`pre-commit`（修"本地装完 dev 跑 pytest 报 unrecognized argument"）；删除死配置 `[tool.flake8]` 段（flake8 不读 pyproject）
- CI（ci.yml）：新增 `jsx-syntax-gate` job（node+python 跑 `scripts/check_jsx_syntax.py`）；精选列表移除被 conftest 排除的 `test_safe_lut_path.py`（此前在 CI 里被静默跳过）

### 6. pre-commit：已安装、钩子暂缓
`pip install pre-commit`（4.6.2，走清华镜像）成功，但钩子初始化需从 GitHub 拉取钩子仓库——当前 Clash 代理（127.0.0.1:7897，全局 git config 配置）进程未运行，GitHub 直连不通。**已主动卸载钩子**避免"每次提交都失败"阻塞工作流。代理恢复后一键启用：

```bash
python -m pre_commit install
python -m pre_commit run --all-files   # 首次全量跑一遍
```

## 未做/移交事项

| 事项 | 原因 | 建议时机 |
|---|---|---|
| git filter-repo 清 680MB tar 历史 | 有 GitHub 远程（github.com/yishujianglin66/ae），重写历史需强推、改写全部哈希 | 你确认后执行：`git filter-repo --path cloud_birefnet.tar --invert-paths` → 强推 → 其他克隆重新 clone；执行前 `git bundle create backup.bundle --all` 做备份 |
| SD1.5 底模 4G / clip_lora 旧权重 1.5G | ComfyUI/对比实验可能在用 | 确认无人使用后移数据盘 |
| output/ 成片母版 735M | 属于作品资产，处置是你的决定 | 移作品集归档目录 |
| 根目录 md 归位（25 篇） | 知识体系重组需要你确认目标结构 | 阶段3 文档统一入口时一并做 |

## 提交记录
- `b3dc14a` chore(repo): 阶段1仓库瘦身 — 201项运行产物出索引 + 根目录大扫除 + 13脚本归档
- （阶段0 的 10 个提交见 `docs/research/2026-08-16-full-project-audit.md` 后续记录）
