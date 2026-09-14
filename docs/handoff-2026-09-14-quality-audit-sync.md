# handoff-2026-09-14 — 质量审计+补强(Phase A/A5) 与 EDL 桥收尾交接

> **用途**：把 2026-09-12~14 的完整工作交接给下一个会话/执行体（零上下文可接手）。
> **阅读顺序**：§0 接续摘要 → §6 启动清单（含提交命令）→ §8 未完成项 → §2 陷阱清单。
> **铁律**：不得凭本文数字推断工作区现状；恢复时**必须重跑 §6.1 检查命令**。ZCode 并行会话活跃，动手前先 `git status` + `git log -1`。

---

## §0 接续摘要（TL;DR）

- 本会话两条线：**① EDL 桥收官（K3「双链无桥」已解决）**；**② 全面质量审计 + 补强 Phase A/A5 已落地**。
- ⚠️ **我全程未 `git commit`**（遵守不擅自提交纪律）——所有成果**未提交**，§6.2 给完整命令。
- **ZCode 并行会话极活跃**（本会话内 HEAD 从 v47→v50 `cd714ad`，每几分钟一提交，文字/字体线）。**热文件 `scripts/build_text_overlay.py` 勿碰**（我的 EDL §4 已在其 v47 提交里）。
- **最高价值下一步 = 修 7 个预存失败测试**（§8/§6.3）：5 个 phase2 JSX 编译**真回归** + 2 个 config **测试隔离 bug**，CI 因只跑 ~9 文件从未暴露。
- 已装 `coverage 7.16.1` 到 .venv（**未动 uv.lock，无 git 足迹**）。

---

## §1 已完成事项（勿重做）

### 1.1 EDL 桥（K3 双链无桥，✅ 已解决，63 passed）
四段闭环，让 R1 剪辑修复成果经 EDL 单一真源传导到视觉/文字双链：
- **① 契约层** `scripts/edl.py`：EDL v1.1 三轨(effects/text_events/overlays) + `lint_edl`(L1-L7) + `load_edl`(读+lint fail-fast 闸门) + `build_edl`(duration=None 时从 cuts 末帧自推导)。
- **② 消费层** `scripts/build_master_polish.py --edl`(effects 轨→`schema_effects_to_plan`，优先级 --effects-json>edl.effects>base) + `scripts/build_text_overlay.py --edl`(text_events 轨直接作事件表，跳过 plan_events)。**三处 run_dir 白名单统一** `RUN_DIR_PATTERN=unified_(?:run\d+|r1_fixed_v\d+)`（含 mastercut_agent），使桥能指向 R1 修复 run。
- **③ 回填层** `scripts/inject_edl_tracks.py`（新）：事后回填(chicken-egg 解法)——把 run 的 text_overlay/events.json + 权威 schema effects 折回 edl.json 三轨；幂等；effects 源优先级 显式--effects-file>production_report.effects_source>自动探测(多候选告警不猜)。
- **④ 接线层** `agents/mastercut_agent.py::_apply_effects_to_video`：应用特效后 guarded 调 inject 自动回填 + tag 派生守卫(r1_fixed 须显式 tag)。
- **附带修复** `scripts/render_regression.py`：emoji×GBK 崩溃根治（main() reconfigure UTF-8 stdout）。
- **数据流**：unified_edit 剪切期建 edl.json(仅cuts) → mastercut 应用特效+inject 回填 → 两消费端 --edl replay 复现。
- **实证**：真实数据 3 次（视觉 run53 8特效→6/8搬运、文字 25事件、round-trip 闭环），零污染 output/。
- **测试**：`tests/test_edl_v11_tracks.py`/`test_inject_edl_tracks.py`/`test_master_polish_whitelist.py`/`test_text_overlay_whitelist.py`/`test_mastercut_edl_wiring.py` = **63 passed**。
- 详见 `09-计划文件/patches/Step0~Step2b`。

### 1.2 全面质量审计（报告：`03-阶段报告/项目全景分析报告_2026-09-14.md`）
证据化审计（实时扫描+配置实读+记忆交叉验证）。**4 Critical**：C1 build-backend 损坏 / C2 CI 只强制 ~9/5593 测试(<3%) / C3 coverage 漏主体从未测 / C4 集成大面积模拟桩。**4 High**：H1 god 文件(5505/5027/4994/4231 行) / H2 lint 闸门形同虚设 / H3 bare except153+except-pass60 / H4 收集回退71s。**亮点**：无真实密钥泄漏、前端/编译器/Docker 有真 CI 门、uv.lock 可复现。

### 1.3 Tier 0（安全快赢，✅ 已落地已验证）
- **T0.1**(C1) `pyproject.toml` build-backend `setuptools.backends._legacy:_Backend`(不存在,ModuleNotFoundError) → **`setuptools.build_meta`**（PEP517 hooks 验证可导入）。
- **T0.2**(C3) coverage `source` 纳入 **core/ai/pipeline/integrations/agents**（原只列 ~17 根模块，漏主体）。
- **T0.3**(M4) `README.md` 状态 run53→**run61/beat 0.8455/78 runs/5593 collected/EDL桥**+指向权威源。

### 1.4 Phase A（质量闸门硬化，✅ 已落地，advisory-first 不阻断 ZCode）
- **A1** `ruff-advisory.toml`（新）：工业规则集 `select=[E,F,I,B,C4,C90,UP,RUF,S]`，**排除 CJK 噪音 RUF001/002/003**；核心库真实债基线 **11,102**（含威胁模型分级注释）。
- **A2/A3/A4** `.github/workflows/quality-hardening.yml`（新）：mypy beachhead(EDL模块) + pip-audit + 全量分片(pytest-xdist `-n2 --dist=loadscope`)，**4 job 全 `continue-on-error`**（债务 ratchet 清零后逐 job 转 required）。
- **A3** `.github/dependabot.yml`（新）：pip/gh-actions/npm(ae-dashboard,compiler) 周更。
- pyproject dev 补 `pytest-xdist/ruff/pip-audit`。
- **未动 `.pre-commit-config.yaml`**（共享，加 blocking hook 会拦 ZCode，隔离考量）。

### 1.5 A5（覆盖率基线实测，✅ 完成）
- 装 `coverage 7.16.1`（附加式，未动 uv.lock）→ 全量测量：**真实覆盖率 29.70%**（77189 语句/52551 未覆盖，--branch），远低于幻想的 fail_under=60 → 已设 **fail_under=29**（ratchet 地板）。
- **God 文件覆盖触目惊心**：filter_engine.py(5505行)=**0.00%** / transition_engine.py(4994)=**0.00%** / text_animation_engine.py(3693)=**0.00%** / production_director.py(5027)=**10.01%** / unified_pipeline.py(3761)=23.81% / llm_gateway.py(4231)=53.73%(最佳)。
- **测试全量结果**：`7 failed, 5503 passed, 37 skipped in 1093.34s(18分13秒)`。

---

## §2 陷阱清单（关键教训，勿踩）

- **T1 中文 mojibake**：子进程 print 中文/emoji 到管道，Windows GBK 下崩溃或乱码。修：入口 `sys.stdout.reconfigure(encoding="utf-8")` + 测试 subprocess `encoding="utf-8"` + **断言用 ASCII 标记**（勿断言中文）。
- **T2 "save failed unknown" 误报**：Write/SearchReplace 报保存失败常是假象。**先 Read/git 核验实际落盘，勿盲目重试**（防重复损坏）。本会话遇 4+ 次全是误报。
- **T3 ruff CJK 噪音**：`RUF001/RUF002/RUF003`(ambiguous-unicode) 对中文项目是**纯误报**（核心库 12,207 条），必须 ignore。
- **T4 B023 良性误报**：23 处 B023(闭包不绑定循环变量) 经核查**全是同迭代内立即调用/await**（`list(ex.map)`/`await gather`/同迭代调用），late-binding 不成 bug。**勿 churn 修**（我曾误标"真bug"，已纠正）。
- **T5 安全发现低风险**：S324 md5×35(均 path/内容指纹生成 ID，非安全)、S301 pickle×6(加载自产可信模型头)、S314 xml×3(本地 FCP 文件，Py3.7+ ET 默认不展开外部实体)——**本地管线威胁模型下无关键可利用漏洞**。勿当紧急漏洞 churn。
- **T6 god 文件 0% 覆盖 → 分解被阻断**：filter_engine/transition_engine/text_animation_engine = 0% 覆盖。**在 0% 覆盖文件上重构=盲飞**，必须先补 characterization/golden-master 测试建安全网再分解（Feathers《修改代码的艺术》铁律）。
- **T7 ZCode 隔离**：热文件 `build_text_overlay.py`（ZCode v43-v50 连续提交）勿碰；**永远勿 `git add -A`/`commit -am`**（会卷入 ZCode 的 build_text_overlay v50 WIP + `make_r1_preview.py`）；ZCode 做**定向提交**（v47 stat 仅 1 文件），故我的非热文件未提交工作**不会被自动卷入**，但仍应尽快提交。
- **T8 全量测试慢**：5593 测试收集 71s、全量+coverage 跑 18 分钟；**7 个失败是预存的**（非我引入，我只改配置），CI 只跑 ~9 文件从未暴露（C2 铁证）。
- **T9 PowerShell**：用 `;` 不用 `&&`；`Get-Content` 读 UTF-8 文件显示乱码是**显示假象**（用 Read 工具核验真实内容）；引号路径前加 `&` 调用符。

---

## §3 补强方案全景（research-grounded，2026 最佳实践）

原 Tier 排序经 A5 覆盖率数据**重塑**为证据驱动的正确序列：

| 序 | 动作 | 状态/依据 |
|---|---|---|
| Tier0 | build-backend/coverage source/README | ✅ 已落地 |
| Phase A | ruff-advisory + mypy/pip-audit/xdist CI + dependabot | ✅ 已落地(advisory) |
| **1(最高)** | **修 7 个失败测试** | 待做，§6.3。真 bug、隔离、具体 |
| **2** | **god 文件补 characterization 测试** | 待做，重构前置安全网(现 0% 覆盖) |
| **3(Phase C)** | god 文件分解(filter_engine 5505 行等) | **被 #2 阻断**，有了测试网才能做 |
| 4(Phase B) | bare except153/except-pass60 分类修 + print→logger | 待做，逐文件排除 build_text_overlay |
| 5 | bulk `ruff --fix`(~9000 自动可修 UP*/I001/F541) | 待做，**大 diff，ZCode 静默期专门批次** |
| 6(Phase D) | 模拟桩→真实集成(C4) / 知识库 7 缺口(M3) / coverage 接入 CI | 大工程，需资源/GPU/决策 |

调研依据（web-grounded）：ruff 一统(select E/F/I/B/C4/UP/RUF/S，S=bandit子集)；mypy 渐进(check-untyped-defs→strict-optional→strict，新码 strict 老码 ratchet)；pytest-xdist GH Actions 2 核用 `-n2 --dist=loadscope`；coverage ratchet(fail_under 设略低于实测,--cov-branch,--cov=包非.)；pip-audit(PyPA/OSV,递归子依赖)优于 safety。

---

## §4 关键技术细节

### 4.1 ruff advisory 债务分级（核心库 11,102，排除 CJK 噪音）
- **~9000+ 自动可修**：UP006(5380 List→list)/UP045(1422 Optional→|None)/UP035(694)/I001(319)/F541(318)/UP015/RUF100/UP009/UP037 → `ruff check --fix` 清。
- **高 severity 真实债**：F401 未用导入 480 / **C901 复杂函数 271**(印证 god 文件) / **S110 except-pass 214** / F841 未用变量 117 / RUF013 隐式Optional 106 / **RUF012 可变类默认 100**(bug风险) / E402 81 / S310 79 / S607 72 / S324 35(良性) / **B023 23(良性,见T4)** / B904 18 / E722 bare-except 16 / S301 pickle 6 / S314 xml 3。

### 4.2 7 失败根因（已确诊）
- **test_config_manager ×2**（`test_development_environment`/`test_production_environment`）：`assertEqual(config["environment"], "development")` → `'test' != 'development'`。**测试隔离 bug**：测试硬断言 dev/prod，但 `AEK_ENVIRONMENT=test` 环境变量覆盖之（CI 也设此变量→CI 跑到也会红）。**修法**：测试用 monkeypatch 固定环境或显式传 environment 参数（**勿弱化断言**）。
- **test_phase2_integration ×5**（`TestPipelineToJSXCompilation` ×4 + `TestEndToEndPhase2Integration::test_full_pipeline_with_jsx_compilation`）：`assert result["success"] is True` → `False`（`compile_planning` 返回 success=False）。**真实功能回归**：Phase2 管线→JSX 编译真的坏了。**修法**：先取 compile_planning 的具体 error 字段定位（是编译器代码坏了还是测试夹具过时），再修。相关：`compiler/` + `scripts/ae_ts_compiler_client.py` + pipeline→JSX 链路。

---

## §5 优先级分析

- **最高价值 = 修 7 失败**（真 bug/真回归，具体、隔离非 ZCode 文件、让全量套件诚实转绿）。5 个 phase2 是**真功能损坏**，比任何 lint/覆盖率都该修。
- **次 = characterization 测试**（god 文件 0% 覆盖是重构的硬阻断，必须先建网）。
- **环境约束**：ZCode 活跃期**只做隔离配置/CI + 非热文件**；bulk autofix/god 分解等 ZCode 静默期。
- 我的分析序列判断（先 A5 测量再重构）已被证据验证正确——若直接开 Phase C 必在 0% 覆盖文件上盲飞引入静默回归。

---

## §6 启动清单（Step-by-step）

### 6.1 恢复检查（必跑，勿凭本文推断现状）
```powershell
cd C:\Users\Administrator\Desktop\AE-Knowledge-Vault
git log --oneline -1                    # 看 ZCode 是否又提交(本会话末为 cd714ad v50)
git status --short                      # 看我的未提交足迹是否还在(§6.2 列表)
.venv\Scripts\python.exe -m ruff check --config ruff.toml .   # 期望 All checks passed!
.venv\Scripts\python.exe -m pytest tests/test_inject_edl_tracks.py tests/test_mastercut_edl_wiring.py tests/test_edl_v11_tracks.py tests/test_edl_regression.py tests/test_master_polish_whitelist.py tests/test_text_overlay_whitelist.py tests/test_visual_effect_schema.py -q   # 期望 63 passed
```

### 6.2 提交我的未提交成果（⚠️ 勿 `git add -A`；勿 add build_text_overlay.py / make_r1_preview.py）
```powershell
# commit 1 — EDL 桥代码(11 文件)
git add scripts/edl.py scripts/build_master_polish.py scripts/render_regression.py scripts/inject_edl_tracks.py agents/mastercut_agent.py tests/test_edl_regression.py tests/test_edl_v11_tracks.py tests/test_inject_edl_tracks.py tests/test_master_polish_whitelist.py tests/test_text_overlay_whitelist.py tests/test_mastercut_edl_wiring.py
git commit -m "feat(pipeline): EDL 桥全线贯通 — 双链 --edl 消费 + 事后回填 + 编排器接线 (解 K3)"

# commit 2 — 质量硬化 + Tier0(配置/CI/文档)
git add ruff-advisory.toml ".github/workflows/quality-hardening.yml" ".github/dependabot.yml" pyproject.toml README.md "03-阶段报告/项目全景分析报告_2026-09-14.md"
git commit -m "chore(quality): Phase A 闸门硬化 + Tier0 修复 — ruff advisory(债基线11102) + mypy/pip-audit/xdist全量分片CI(continue-on-error) + dependabot + 修build-backend(C1) + coverage纳入主包并设ratchet地板29(C3) + 全景审计报告"

# commit 3 — EDL 桥文档(每日记录/草案/MOC/落地方案/调研)
git add "00-每日记录/2026-09-13_EDL桥全线贯通.md" "09-计划文件/patches/" "09-计划文件/📝-计划文件-MOC.md" "09-计划文件/2026-09-10_多线整合全面推进计划.md" "09-计划文件/2026-09-11_管线集成与Skill封装落地方案.md" "DEEP_RESEARCH_视频管线集成与Skill封装.md"
git commit -m "docs(pipeline): EDL 桥 Step0-2b 草案 + 落地方案 + 41源调研 + MOC/进度同步"
```
> 提交前 `git diff --staged --stat` 复核每个 commit 只含预期文件。`build_text_overlay.py`(M=ZCode v50)、`make_r1_preview.py`(??=ZCode) 及 ZCode 的文字线文档**绝不可 add**。

### 6.3 修 7 失败（下一会话主任务）
```powershell
# 复现 + 看根因
$env:AEK_ENVIRONMENT="test"; $env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe -m pytest "tests/test_config_manager.py::TestGetConfig" tests/test_phase2_integration.py -q --tb=short -p no:cacheprovider
# config 2 失败: 修测试(monkeypatch 固定 environment 或显式传参), 勿弱化断言
# phase2 5 失败: 先打印 compile_planning 返回的 error 字段定位真因, 再修(compiler/ 或 pipeline→JSX 链路)
# 修完回归: 上面两文件应全绿; 再跑 §6.1 的 EDL 63 确保无连带破坏
```

---

## §7 文件索引

| 类别 | 路径 |
|---|---|
| 全景审计报告 | `03-阶段报告/项目全景分析报告_2026-09-14.md`（§1-14，含 A5 覆盖率+安全修正）|
| EDL 桥草案 | `09-计划文件/patches/Step0_EDL_v1.1_补丁草案.md` / `Step1_AE链消费EDL_补丁草案.md` / `Step2_编排器接线与EDL轨道回填_草案.md` / `Step2b_mastercut_agent接线_补丁草案.md` |
| EDL 桥代码 | `scripts/edl.py` / `scripts/inject_edl_tracks.py` / `scripts/build_master_polish.py` / `scripts/build_text_overlay.py`(§4在ZCode v47) / `agents/mastercut_agent.py` |
| 质量硬化配置 | `ruff-advisory.toml`(债务分级注释) / `ruff.toml`(baseline门) / `.github/workflows/quality-hardening.yml` / `.github/dependabot.yml` / `pyproject.toml`(build-backend/coverage/dev deps/fail_under=29) |
| 覆盖率产物 | `tmp/cov_report.txt`(逐文件覆盖率) / `tmp/cov_run.log`(全量测试日志) / `.coverage`(gitignored) |
| 每日记录 | `00-每日记录/2026-09-13_EDL桥全线贯通.md` |
| 权威进度 | `docs/handoff-2026-09-06-sync.md`(视频主线 run61/beat0.8455) + 本文(质量线) |
| 记忆 | id `64a8ecdb`(审计核心发现+Phase A/A5) / `d748db79`(EDL桥架构) |

---

## §8 未完成项（待办，按优先级）

1. **[最高] 修 7 失败测试**（§6.3）：5 phase2 JSX 编译真回归 + 2 config 测试隔离。具体、隔离、高价值。**✅ 已完成（见 §9，commit `5c8ac43`）——注：5 phase2 非编译代码回归，真因见 §9。**
2. **提交我的未提交成果**（§6.2，3 commits）——ZCode 活跃期越早越安全。
3. **god 文件 characterization 测试**（重构前置）：为 filter_engine/transition_engine/production_director 补 golden-master/特征测试，把 0%→有网。
4. **Phase C god 文件分解**（被 #3 阻断）：有了测试网后，按职责拆 5505/5027/4994 行巨file，每步全测试守护。
5. **Phase B**：bare except(153)/except-pass(60) 分类修 + ruff E722 门；print(11363)→logger(core/ai 优先)。逐文件排除 build_text_overlay.py。
6. **bulk `ruff --fix`**（~9000 自动可修）：ZCode 静默期专门隔离批次，先小范围验证行为不变。
7. **coverage 接入 CI**：现仍 dead config（fail_under=29 未被任何 workflow 执行）；把 quality-hardening.yml 的 full-suite-sharded job 加 `--cov` + `--cov-report=xml` + `--cov-fail-under=29`。
8. **A5 延伸**：本地装 mypy/pip-audit 拿基线（已加 CI config，本地未装）；mypy beachhead 扩至 core/。
9. **Phase D**：模拟桩→真实集成(C4，Whisper/RIFE/SAM2 按价值 + real/simulate 诚实标记 + 契约测试)；知识库 7 大理论缺口(M3：色彩科学/音频工程/电影摄影/剪辑理论)；集成测试体系(mark.integration 实装)。

---

> 返回 → [[🏠-AE知识中心]] · 相关 → [[📝-计划文件-MOC]]（EDL 桥 Step0-2b）· 视频主线 → `docs/handoff-2026-09-06-sync.md`

---

## §9 后续会话回写（2026-09-14 续会话：§6.1→§6.2→§6.3 已执行）

- **§6.1 恢复检查**：HEAD 仍 `cd714ad`（ZCode 未再提交）；`ruff check --config ruff.toml .` → All checks passed!；EDL 7 文件 **63 passed**。足迹与 §6.2 完全一致。
- **§6.2 提交（3 commits，均显式路径 add，未 `git add -A`）**：
  - `da42dd0` — EDL 桥代码 11 文件
  - `5ba9907` — 质量硬化 + Tier0（ruff-advisory/workflow/dependabot/pyproject/README/审计报告）
  - `5e61d54` — EDL 文档 + patches/ + 本交接文
  - `build_text_overlay.py`（已随 v50 提交，工作区干净）、`make_r1_preview.py` 均未卷入。
- **§6.3 修 7 失败（commit `5c8ac43`）——更正 §4.2 的两处诊断**：
  - **2 config**：根因确认=`tests/conftest.py` 的 autouse fixture **只对非 config 测试**设 `AEK_ENVIRONMENT=test`；而 `get_config("development")` 的**显式 environment 参数会被 `_apply_env_overrides` 用外层 env 覆盖**（优先级文档即如此）。故失败只在**外层**已设 `AEK_ENVIRONMENT=test` 时出现——CI 的 `quality-gate/ci/test-health` 三个 workflow 均设 test，所以 CI 跑到必红。修法：测试内 `_without_env("AEK_ENVIRONMENT")` 隔离（断言未弱化）。
  - **5 phase2**：**不是编译代码回归**。真因=`compiler/build/cli.js` 不存在（`compiler/build/` 被 .gitignore，仅 `ci.yml::compiler-test` 独立 job 构建）→ `_run_compiler` 返回 `success=False`；而 `compile_planning_to_jsx` 已把 `method` 标成 `"standalone_jsx"` 却**没有真正生成降级 JSX**（与 `AETSCompilerClient.compile_from_planning` 的降级行为不一致）→ 调用方拿到 `success=False` 且无 `jsx_code`。修法：补全降级分支（生成独立 JSX、`success=True`、真因保留在 `compile_error`）。
  - **验证**：`AEK_ENVIRONMENT=test` 与不设两条件下，`test_config_manager` + `test_phase2_integration` 均 **26 passed**；pipeline 相关 13 个测试文件 **209 passed**；EDL **63 passed** + ruff 无回归。
- **Mimosa 安全 hook 假阳性**：`core/config.py:794-819` 的 "硬编码凭据" 实为**环境变量名→配置路径映射表**（`"LLM_API_KEY": "model.api_key"`），无任何真实密钥值（grep `sk-`/`AKIA`/`eyJ` 于 core/ 零命中），与审计"无真实密钥泄漏"一致。
- **仍未动**：§8 #4（god 文件分解/Phase C）、#5（Phase B bare-except）、#6（bulk autofix）、#9（Phase D）；本地未装 mypy/pip-audit。工作区仍留 ZCode 文字线文档与 `make_r1_preview.py`（按 §2 T7 刻意不碰）。

### §9.1 续推进（本会话第二轮：§8 #3 characterization 安全网 + #7 coverage 接 CI）

- **§8 #3 god 文件 characterization 安全网**（commits `bfb9934` + `cfab531`）：
  纯新增测试文件 `tests/test_core_god_files_characterization.py`（65 条断言，无产品代码改动）。
  把 4 个 god 文件的**当前可观察行为**固化为 golden-master，为后续分解建网：
  - 覆盖提升（仅本文件，`--branch`）：`filter_engine.py` 0.00%→**48.55%** /
    `text_animation_engine.py` 0.00%→**42.49%** / `transition_engine.py` 0.00%→**41.32%**
    （三者合计 2811 语句 → 44.20%）。
  - 含：34 缓动端点不变量 + 7 组黄金数值 + `generate_keyframes`；`FilterParam`/`FilterPreset`
    契约（范围/归一化/强度锚缩放/深拷贝）；三端门面层（预设库 107/95、AI 推荐、跨软件统一 API、
    FFmpeg 滤镜分区 34=25+9）；字体/排版（**仅钉 WCAG 返回结构**，不钉疑似缺陷的数值）。
  - `ai/production_director.py`（+103 行）：钉死 `COLOR_PRESETS`/`SPEED_PRESETS`（drop 必须原速 1.0
    铁律）/`XFADE_MAP`/`XFADE_GROUP_SIZE=8` + 三个数据结构契约 + `export_decision_log` 的 .md 分支。
    ⚠️ 其公开面主要是 `render()`（需真实 ffmpeg/素材=集成层，由既有 9 个定向测试覆盖），
    故本批只覆盖接口面（该文件单测覆盖 3.35%，**整文件分解仍需更多集成级网**）。
  - **重要边界**：44% 只是确定性/门面表面的网；`filter_engine` 内大量 `generate_script` 分支与
    `transition_engine` 的 5 个软件引擎仍未覆盖 → **§8 #4 全量分解尚不安全**，需继续补网。
- **§8 #7 coverage 接入 CI**（`quality-hardening.yml::full-suite-sharded`）：加
  `--cov --cov-branch --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=29`
  + 安装 `pytest-cov` + 上传 `coverage.xml`。source 由 pyproject `[tool.coverage.run]` 提供，
  故用 bare `--cov`（已实测取到 80104 语句）。至此 `fail_under=29` 从**死配置**变为**活 advisory 门**
  （job 仍 `continue-on-error`，不阻断 ZCode）。
- **本地全量实跑验证**（同 CI 参数，`-n2 --dist=loadscope` + coverage）：
  **5621 passed / 0 failed / 37 skipped / 16 分 49 秒**，coverage **32.59%** > 29 地板，
  `coverage.xml` 正常产出，pytest exit 0。⚠️ 对比 A5 基线（`7 failed / 5503 passed / 29.70%`）：
  修完 7 失败后**全量套件已首次全绿**，且覆盖率升到 32.59%（新 characterization + 原失败用例现能跑完）。
  本地为此装了 `pytest-cov` / `pytest-xdist`(含 execnet) / `pytest-timeout`（**附加式，未动 uv.lock，无 git 足迹**；
  三者本就在 pyproject dev deps / CI 安装列表内）。

### §9.2 续推进（第三轮：校验 Phase A 未跑过的 advisory CI job + 发现真缺陷）

Phase A 的 4 个 advisory job 此前**从未实际执行**（无法从"CI 绿"推断其有效）。逐个本地实跑：

- **ruff-advisory**：✅ 有效。实测 **10,929 errors / 8,516 自动可修**，exit 1（continue-on-error 符合预期）。
- **mypy-advisory**：❌ **原命令有缺陷** → 已修。原命令只点名 3 个文件、**缺 `--follow-imports=silent`**，
  导致 mypy 仍跟随 import 分析整个 `pipeline/`+`core/` 图，**实测 1284 errors / 148 文件**（噪音，
  永远无法成为"干净基线"，与 A2 设定的 ratchet 目标矛盾）。加 `--follow-imports=silent` 后只报目标文件自身错误。
  同时修掉其中 21 处（`edl.py` ×2 注解 / `inject_edl_tracks.py` reconfigure union-attr / `mastercut_agent` 的
  `report` dict 注解——后者一处注解清掉 20 条 `[index]`）。**基线收敛到 3 errors**。
- **pip-audit**：⚠️ 未本地校验（需网络 + 会拉入较多依赖，为不扰动已全绿的环境而跳过；CI 侧参数未改）。
- **full-suite-sharded + coverage**：见 §9.1，已实跑验证。

#### ⚠️ 新发现真缺陷（P1，未修，需产品决策）：`mastercut_agent` 的 `analyze_beat` 能力已坏

- **现象（运行时实测）**：`agents/mastercut_agent.py::_stage_analyze_beat`（注册为 capability `analyze_beat`，
  见 `_register_default_tools` line ~697，并在 `run_full_pipeline` line ~806 被调用）调用**已不存在的旧 API**：
  - `BeatStrengthEngine().detect(bgm_path)` → **`AttributeError`**（现类只有 `classify_beats(beats_sec, downbeats_sec, ...)`）；
  - `MusicDynamicsAnalyzer().analyze(bgm_path)` → 现签名是 `analyze(rms, times, total_duration, beats_sec, onsets_sec)`，
    传路径字符串类型不符。
- **影响**：任何调用 `execute("analyze_beat", ...)` 的路径都会**硬崩**（非静默错误）。
- **未修原因**：修复需把"路径→音频数组"这段（用 `ae.beat_detector` + rms 提取）重新接上，
  属**新增行为**且无音频夹具可验证——盲目写会重蹈审计 C4（未验证的集成）覆辙。**建议**：
  用 `ae.beat_detector.BeatDetector` 取 beats + `core.beat_strength_engine.classify_beats` +
  `core.music_dynamics.analyze(rms, times, ...)` 重实现，或先 `deregister` 该能力（避免假成功）。
  已由 mypy beachhead 持续盯防（基线 3 errors 即此 3 处）。

**环境提示（附加式安装，未动 uv.lock/无 git 足迹）**：本地已装 `pytest-cov` / `pytest-xdist`(execnet) /
`pytest-timeout` / `mypy`。安装后已复验 pydantic 依赖链与 102 用例无回归（typing_extensions 4.16.0 / pydantic 2.13.5）。


