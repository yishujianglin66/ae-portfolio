# 多 Agent 协作隔离约定

> 日期：2026-08-14 · 背景：两个 agent 在**同一工作树 + 同一分支**上并行工作，
> 全天踩过 4 类冲突。本文记录踩坑案例与强制约定，配套工具 `scripts/task_guard.py`。

## 一、踩过的坑（真实案例）

| # | 场景 | 后果 | 教训 |
|---|---|---|---|
| 1 | 并行任务 `git add` 了 70+ 个重命名（tests→dev_scripts），我提交时它们混进了我的暂存区 | 差点把他人改动随我的提交一起推上去 | **提交前必须核对暂存区完整清单** |
| 2 | 我编辑 `production_director.py` 时，并行任务同时改了它 | edit 工具报 "file changed since read"，被迫重读 | **改文件前先查状态，改后核对 diff** |
| 3 | 我做 LFS 历史重写前 stash 了它的未提交改动，reflog expire + gc 后 stash 丢失 | 它 87 项改动快照被删（所幸它自己已另行提交） | **重写历史前必须先与对方确认工作树干净** |
| 4 | 每次 `git add -u` / `git add -A` 都会把它的新改动一并暂存 | 每轮都要 reset 后重 add，浪费且危险 | **禁止全量暂存，必须按文件清单显式 add** |

## 二、强制约定

1. **禁止全量暂存**：不许 `git add -A` / `git add -u` / `git add .`。
   必须按本任务文件清单逐个显式 add（用 `scripts/task_guard.py stage` 更好）。
2. **提交前双核对**：`git diff --cached --name-only` 必须与本任务清单一致，
   发现他人文件 → `git reset` 释放，绝不随提交带走。
3. **改文件前三看**：`git status --short <file>` 看是否正被改动；
   改完后 `git diff --stat <file>` 确认只动了预期内容。
4. **破坏性操作先行确认**：`git stash` / `git reset --hard` / 历史重写（filter-repo、
   lfs migrate）之前，必须先查 `git status` 是否干净；不干净先与对方对齐（等待其
   提交，或快照其改动到独立分支再操作）。
5. **重写历史后立即广播**：force push 后对方必须 `git fetch && git reset --hard
   origin/<branch>` 再继续，否则基于旧历史提交会冲突。
6. **运行数据不碰他人目录**：`data/atmosphere_annotations/`、`data/model_lifecycle/`
   等运行时/标注产物由产出方自行提交，他人不代劳、不清理。

## 三、任务守卫工具

`scripts/task_guard.py`（本次随约定一起交付）：

```
py -3.12 scripts/task_guard.py status          # 列工作树改动, 按最近提交者标注归属
py -3.12 scripts/task_guard.py stage <file...> # 仅暂存清单内文件; 发现暂存区有清单外文件先告警
py -3.12 scripts/task_guard.py check           # 提交前检查: 暂存区是否含非本任务文件
```

判定逻辑：每个改动文件的"最近一次提交者"若与本 agent 署名不同，标为 ⚠️ 疑似他人文件。
本仓库署名约定（`git config user.name`）：

- 并行任务 agent：以其提交署名识别（当前为 "Trae"/其他，见 git log --format='%an'）
- 本 agent：`AE Knowledge Vault`（路径/配置/性能优化系列提交）

## 四、冲突处理流程（发现对方文件在暂存区时）

```
1. git diff --cached --name-only          # 拿到完整清单
2. git reset <他人文件...>                # 只释放他人文件, 不 reset 全部
3. git status --short                     # 确认对方文件回到未暂存状态
4. 继续本任务提交
```

## 五、遗留问题（后续优化方向）

- 理想做法是**分支隔离**（每任务一分支 + 定期 merge/rebase），但并行任务不受本侧控制，
  只能先靠约定 + 工具兜底。若可协调，建议改为：`feat/<task-name>` 分支，主分支只进
  已完成任务的合并提交。
- pre-commit hook 的全局文件归属检查可行但会影响对方工作流，暂不引入。
