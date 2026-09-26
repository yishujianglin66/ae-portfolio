# FIX-02 执行验证记录（顶级退出码污染切断）

- 日期：2026-09-26（基线 HEAD `81e8d72`；FIX-01 已落 `fa671e2`）
- 方案出处：`09-计划文件/2026-09-26_全量问题修复执行方案.md` §一 FIX-02（审计 F1/B 类）
- 判定：**READY**（全部为真实执行验证，含真实 CLI 冒烟）

## 1. 变更清单（动手前逐一 `git status` 确认无在途 diff）

| 文件 | 变更要点 |
|---|---|
| `ai/auto_produce.py` | ① step6 `ok` 改由 `_artifact_verified()`（存在+ffprobe 时长>0，fail-closed）；② dry_run 语义拆离：`success` 只属于真实执行，新增 `dry_run_completed`/`artifact_verified`/`executed`；③ 每步报告加 `execution_path ∈ {real,simulated,failed}`；④ step1 `ok` 改 `count>0`；⑤ 占位评分显式标 `score_source="random_placeholder"`；⑥ **退出码 0=真实产物已验证 / 4=dry_run 冒烟(simulated) / 1=失败** |
| `api_server.py` | `_execute_puppet_style_task`/`_execute_quality_assessment`/`_execute_parameter_optimize` 三处：mode 默认 simulate→real；**删除异常时伪造 `frames_processed=100`/`psnr=38.5`/`optimized_params` 的假 success 分支**（异常直接上抛由任务队列记失败）；成功路径加 `execution_path` |
| `api/toolchain_api.py` | 7 处 `mode` 默认 `"auto"`→`"real"`（2 Field + 5 Query） |
| `tests/test_auto_produce_honest_exit.py` | 新建 9 用例（沙箱化重定向 `_PROJECT_ROOT`，不写真实 output/、不依赖 D 盘语料） |

## 2. 验证命令与真实输出

```powershell
# ① 新增行为测试（含 dry_run 必 False、缺产物必 False、fail-closed 验证实测、默认值回涨静态守卫）
$ .venv\Scripts\python.exe -m pytest tests/test_auto_produce_honest_exit.py -q --timeout=180
9 passed in 0.38s

# ② 真实 CLI 冒烟（审计 F1 的原始触发场景：默认 dry-run 不得再 exit 0 冒充成功）
$ .venv\Scripts\python.exe ai/auto_produce.py --dry-run --theme fix02_smoke_20260926 --duration 45
  末行输出: "DRY_RUN 流程冒烟通过(execution_path=simulated)——不是生产结论"
  CLI_EXIT=4                     # ← 修复前该场景为 exit 0 + success:true
  # 落盘报告核验: output/fix02_smoke_20260926_production_report.json
  #   "success": false / "dry_run_completed": true / 顶层 "execution_path": "simulated"
  #   step1-3(真实本地计算)="real"，step4-6(未执行)="simulated" —— 逐步如实标记

# ③ 既有消费面回归（触及 api_server/toolchain_api 的全部测试文件）
$ pytest tests/test_api_auth_fail_closed.py tests/test_p0_imports.py tests/test_auto_produce_honest_exit.py -q
23 passed in 4.86s

# ④ 静态门
$ ruff check --config ruff.toml ai/auto_produce.py api_server.py api/toolchain_api.py tests/... scripts/test_ae_real_chain.py
All checks passed!
$ py_compile ai/auto_produce.py api_server.py api/toolchain_api.py → COMPILE_EXIT=0
```

## 3. 过程记录（如实）

- 首轮 1 个测试红：`test_verified_artifact_succeeds` 因 `_fallback_shots` 内部无种子、
  8s 目标时长下最后一刀overshoot 触发 `validate()` ">20% 偏差"——**测试设计问题非产品回归**；
  修法是 fixture 固定 `random.seed(7)` + 目标时长 45s（overshoot 比例落入容差），未动产品逻辑。
- `api_server.py` 首轮编辑留下 3 个空 `try:`（删 except 后）→ 语法器即报错，第二轮改为
  去除 try 包裹并降缩进，编译/测试复验通过。
- 已知既有问题（不属 FIX-02，未动）：三 handler 成功路径的 `execution_path` 对 `mode="auto"`
  归为 `fallback`（底层实际路径不可知）——待 FIX-03 治理 integrations 层后自然消除。
- `auto_produce.py` 的 `_fallback_shots` 无内部种子本身是可复现性隐患（真实语料路径有
  seed(42)，fallback 没有）——登记给 FIX-16/FIX-28 类数据诚实化时一并处理，本轮不扩大改动面。

## 4. 影响与回退

- 行为变更（预期内）：以 `--dry-run` exit 0 判定"生产成功"的旧自动化会开始感知 exit 4；
  显式 `mode="simulate"` 之外的异常路径由"假成功"变为任务失败——正是 F1 修复目标。
- 回退：本记录对应单一提交，`git revert` 即可；未触碰并行线任何文件。

## 5. 复跑指令

```powershell
cd C:\Users\Administrator\Desktop\AE-Knowledge-Vault
.venv\Scripts\python.exe -m pytest tests/test_auto_produce_honest_exit.py tests/test_api_auth_fail_closed.py tests/test_p0_imports.py -q --timeout=300 -p no:cacheprovider
.venv\Scripts\python.exe ai/auto_produce.py --dry-run --theme <unique> --duration 45; $LASTEXITCODE   # 期望 4
```
