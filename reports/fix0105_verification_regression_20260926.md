# FIX-01~05 欠账清偿验证记录（全量回归 + FIX-02 子项闭环）

- 日期：2026-09-26（回归窗口 13:04–13:23，末次读取 HEAD `ff17b01`）
- 依据：用户指令「质量精度 > 速度；串行逐项闭环」后的 §十⓪ 订正清单还债
- 判定：**FIX-02 → READY**（验收栏全部子项闭环）；全仓回归欠账清偿（FIX-01/04/05 的整仓层验证由本次覆盖）

## 1. 全量回归（FIX-01~05 共同欠账 ①）——真实输出

```powershell
$ .venv\Scripts\python.exe -m pytest -q --timeout=300 -p no:cacheprovider --ignore=mcp-extension
6398 passed, 46 skipped, 60 warnings in 1125.70s (0:18:45)
# 日志在盘: tmp/full_regression_fixclose_20260926.log（65KB，LastWriteTime 13:23:04）
```

0 failed。此前定向套件（98/23/50 passed）之外无新增红——FIX-01~05 的改动在整仓层面无回归。

### ⚠️ 两条如实披露（不影响本次数字，但影响解读）

1. **`test_real_e2e_all_modules.py` 不在这 6398 之内**：它被 `tests/conftest.py:80`
   collect_ignore 排除（目录遍历时静默跳过；显式传路径时仍会因"无本地 mp4 素材"在收集期 assert）。
   早前 stash 复现收集炸 = 显式路径行为；本次全绿 = 排除生效。**该文件是 FIX-16 账目的真实候选，
   "全量绿"不得被解读为"它也是绿的"。**
2. **混合工作区归因**：回归窗口内并行线提交了 `ff17b01`（13:16，其此前为工作区内容，commit 不改
   磁盘），故本次全量验证覆盖的是"我方 4 提交 + 并行线工作区内容"的合集状态；46 skipped 中可能含
   并行线未收敛 WIP 的自跳过。此项按 §十⓪ 纪律如实标注，不冒充纯净基线。

## 2. FIX-02 剩余子项闭环（欠账 ②③）

| 子项 | 实装 | 验证（真实输出） |
|---|---|---|
| ② CLI 退出码映射可测化 | `auto_produce.py` 抽出 `exit_code_for(report)`（0/4/1），`__main__` 仅调用它——行为与原手工实锤一致 | `TestExitCodeMapping` 4 例：dry_run→4（**绝不得为 0**，F1 核心场景）、success→0、失败→1、空报告→1 |
| ③ `_artifact_verified` 正例 | 测试内用 `ffmpeg -f lavfi color` 生成 1s 真 mp4 → 断言验证器 True（与既有 garbage 负例成对，同时防"永远 False"退化） | `test_real_ffmpeg_output_passes` **实跑非 skip**（本机 ffmpeg/ffprobe 在 PATH） |

```powershell
$ .venv\Scripts\python.exe -m pytest tests/test_auto_produce_honest_exit.py tests/test_execution_contract_schema.py -q
30 passed in 0.69s          # ← 真实输出；0 skipped 意味着正例真跑了
$ .venv\Scripts\python.exe -m ruff check --config ruff.toml ai/auto_produce.py tests/test_auto_produce_honest_exit.py
All checks passed!
```

**FIX-02 验收栏逐条对账**：① 无产物断言测试 ✓；② 真实 CLI exit≠0 ✓（手工 exit=4 + 本次自动映射守卫双保险）；
③ api/toolchain 默认值静态守卫 ✓（`TestDownstreamDefaultsHonest`）；④ 全仓回归 ✓（本次）。→ **升 READY**。

## 3. §十⓪ 订正清单更新后状态

| 项 | 状态变化 | 剩余 |
|---|---|---|
| FIX-02 | 部分完成 → **READY** | 无 |
| FIX-01 | 部分完成（全仓回归欠账已清） | 仅"被 FIX-09 引用"随 FIX-09 落地回头补 |
| FIX-04 | 部分完成（pipeline 级消费面回归由本次 6398 覆盖） | 既有 `test_multimodal_fusion_hub.py` 补 fake 路径新规格断言（下一项） |
| FIX-05 | 部分完成 | collect_materials 全 Mock 端到端断言（下一项）；真实 run 报告字段核验挂账至下次真出片 |

## 4. 复跑指令

```powershell
cd C:\Users\Administrator\Desktop\AE-Knowledge-Vault
.venv\Scripts\python.exe -m pytest tests/test_auto_produce_honest_exit.py tests/test_execution_contract_schema.py -q --timeout=300 -p no:cacheprovider
# 全量（约 19 分钟）：
.venv\Scripts\python.exe -m pytest -q --timeout=300 -p no:cacheprovider --ignore=mcp-extension
```
