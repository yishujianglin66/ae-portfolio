---
tags: [补丁草案, EDL桥, Step2, 编排器接线, 数据契约, 未落地]
date: 2026-09-12
status: §2(inject_edl_tracks)-APPLIED-2026-09-13 · §4(mastercut_agent接线)-PENDING
targets: [scripts/unified_edit.py, agents/mastercut_agent.py, scripts/inject_edl_tracks.py(新)]
depends_on: Step1_AE链消费EDL_补丁草案.md（§2+§3+§4+Step1.5 已合入）
---

# Step 2 草案：编排器接线 + EDL 轨道回填（让桥从"手动可用"变"管线自动用"）

> **状态：草案，未落地**。Step1 已让两个消费端（build_master_polish/build_text_overlay）能吃 `--edl`，但**管线里没人自动喂 edl.json 的 effects/text_events 轨**——目前全靠手动。Step2 解决"谁在何时把轨道填进 EDL、谁自动以 --edl 调用"。
> **为何是草案**：涉及核心管线（unified_edit.py / mastercut_agent.py）+ 一个架构决策（chicken-egg），风险高于 Step0/1，须你拍板方案后再落。

---

## 〇、现状与核心架构问题（侦察实证 2026-09-12）

### 现有数据流（侦察证据）

```
unified_edit.py (剪切装配期)
  ├─ 产 production_report.json (116 segments)
  ├─ L525 build_edl(_pr_path, bgm_path=, sources=, style=, theme=, duration=args.duration)
  │        → edl.json (只有 cuts/cut_points/inputs, ❌ 无 effects/text_events)
  └─ L529 save_edl(edl.json)  [try/except 非侵入, 失败不阻断主管线]
        ↓ (后续 polish 阶段, 由 agents/mastercut_agent.py 驱动)
build_master_polish  → plan_effects 现场规划特效 → tmp/master_plan.json → AE
build_text_overlay   → plan_events 现场规划文字 → run_dir/text_overlay/events.json → AE
```

### 🔴 chicken-egg（Step2 的本质难点）

**EDL 在剪切装配期（unified_edit L525）构建，但 effects/text_events 是后续 polish/text 阶段才由 `plan_effects`/`plan_events` 现场生成的。** 建 EDL 时这两轨的数据**还不存在**。

→ 不能简单"在 build_edl 调用处加 effects=/text_events="（那时没有数据）。必须选一种架构：

## 一、三方案对比

| 方案 | 做法 | 优点 | 缺点 | 风险 |
|---|---|---|---|---|
| **A. 事后回填**（推荐）| polish/text 跑完后，新增 `inject_edl_tracks.py` 把 master_plan/events.json 折回 edl.json 的 effects/text_events 轨 | 不改管线顺序；EDL 成为**已应用的审计真源**；隔离（新文件）| 需 reverse-map（内部格式→schema）| **低**（新文件，不碰核心） |
| B. 重排 | 把 effects/text 规划提到 build_edl 之前，直接传入 | EDL 一次成型 | 大改管线顺序；plan_effects 依赖 render 产物 | 高（动 unified_edit 主流程） |
| C. 契约优先 | 上游先**授权**effects/text_events 进 EDL（作为创作计划），polish 步骤只执行 | 真·单一真源；可复现 | 需一个"计划授权"环节（谁产 schema effects?）| 中（需新规划器/接线） |

**推荐 A（事后回填）+ 渐进到 C**：A 先让 EDL 成为完整审计记录（低风险、隔离），round-trip 跑通后，C 的"契约优先"自然浮现（回填的 EDL 就是下次 --edl replay 的契约）。

## 二、推荐方案 A：`scripts/inject_edl_tracks.py`（隔离新文件）

### 2.1 职责

读一个 run 的既有产物，把 effects/text_events 折回该 run 的 edl.json（幂等、可重跑）：

```
输入: output/<run>/edl.json (Step1 已有 cuts)
      output/<run>/text_overlay/events.json  → text_events 轨 (events 数组, 完整事件表)
      output/<run>/<effects>.json (schema 格式) → effects 轨
输出: 原地更新 output/<run>/edl.json (schema_version 保持 1.1, 补 effects/text_events)
      + 打印 effects_injection_report (对齐 build_master_polish: 禁止静默丢弃)
```

### 2.2 关键决策点（须你拍板）

1. ✅ **已由实现解决（解析优先级）**：inject 按 显式 `--effects-file` > `production_report.effects_source` > 自动探测(唯一才用; 多候选则 `[WARN]` 跳过不猜) 解析。**真实实证**：run53 的 3 个 effects 文件被正确判为歧义并告警，`--effects-file run53v43_effects.json` 消歧义后注入 8 条。mastercut_agent 接线时记录 `effects_source` 即自动消歧义（前向兼容钩子已留）。
2. **text_events 直接取 events.json 的 events 数组**（已实证 25 条完整搬运，无歧义）。✓
3. **evidence_chain**：effects 轨每条须带 `evidence_chain.skill_id`（lint L7 强制）。schema effects 文件已含（如 `run53-validated-2026-09-06`）；若从 master_plan 反推则缺，故**优先用 schema 文件作源**（而非内部 master_plan.json）。
4. **幂等**：重跑 inject 应覆盖而非追加轨道（避免 effects 翻倍）。

### 2.3 骨架（精确实现待决策后）

```python
# scripts/inject_edl_tracks.py（新, ~80 行）
"""把 run 的 effects/text_events 折回 edl.json（事后回填, 幂等）。"""
def inject(run_dir: Path, effects_file: Path | None):
    from scripts.edl import load_edl, save_edl, lint_edl
    edl = load_edl(run_dir / "edl.json", run_lint=False)  # 读旧(可能 1.0)
    edl["schema_version"] = "1.1"
    # text_events ← events.json（完整事件表）
    ev_p = run_dir / "text_overlay" / "events.json"
    if ev_p.exists():
        edl["text_events"] = json.loads(ev_p.read_text("utf-8"))["events"]
    # effects ← 权威 schema 文件（决策点1）
    if effects_file and effects_file.exists():
        _eff = json.loads(effects_file.read_text("utf-8"))
        edl["effects"] = _eff if isinstance(_eff, list) else _eff.get("effects", [])
    errs = lint_edl(edl)               # 回填后过闸门
    save_edl(edl, run_dir / "edl.json")
    return {"effects": len(edl.get("effects", [])),
            "text_events": len(edl.get("text_events", [])),
            "lint_errors": errs}
```

## 三、round-trip 闭环（Step2 的终点价值）

```
unified_edit → edl.json(cuts)
  → build_master_polish/text_overlay 现场规划+应用 → master_plan/events.json
  → inject_edl_tracks → edl.json(cuts + effects + text_events)  ← 完整审计真源
  → 下次: build_master_polish --edl edl.json / build_text_overlay --edl edl.json
          → 复现完全相同的 plan/events（无现场重规划漂移）  ← 可复现性(SLSA/MLflow 范式[33][7])
```

这一步把 EDL 从"切点记录"升级为"**完整、可复现、可审计的合成契约**"——正是 DEEP_RESEARCH [5][28][33] 的核心收益。

## 四、编排器自动接线（方案 A 落地后, 后续小步）

| 位置 | 改动 | 风险 |
|---|---|---|
| `agents/mastercut_agent.py::_apply_effects_to_video` | 应用特效后调 `inject_edl_tracks(run_dir, effects_file=<所用schema>)`；并把所用 effects 文件路径记入 production_report | 中（核心 agent，须测）|
| build_text_overlay 调用处 | 出 events.json 后调 inject（或合并到上一次 inject）| 中 |
| `unified_edit.py` L525 | **可选**：duration 已由 Step1.5 自动推导兜底，无需改；若要 EDL 一次带轨则走方案 B/C（暂不）| 低（不动）|

> 自动接线让"手动 --edl"变"管线默认走 EDL 契约"。但改 mastercut_agent 需端到端测（涉 AE），建议 inject_edl_tracks.py 先独立落地 + 手动验证 round-trip，再接线。

## 五、本会话已落地 vs Step2 待决

- ✅ **已落地（Step1.5，本会话）**：`build_edl` duration 自动推导（finding#1）——`duration=None` 时从 cuts 末帧兜底（edl.py，53 passed）。unified_edit L527 本就传 `args.duration`，此为双保险。
- ✅ **已落地（§4，本会话）**：build_text_overlay --edl 消费 text_events（真实数据实证 25 事件搬运）。
- ✅ **已落地（Step2 §2，本会话）**：`scripts/inject_edl_tracks.py`（事后回填、幂等、effects 权威源解析、lint 闸门、--dry-run）+ `tests/test_inject_edl_tracks.py`（7 测）+ **真实数据 round-trip 实证**（run53 产物、tmp 沙箱零污染：歧义告警→显式消歧→8 effects+25 text_events→两消费端 replay 视觉6/8+文字25、幂等不翻倍、lint PASS）。**60 passed**。
- 📝 **Step2 待决**：§4 mastercut_agent 自动接线（应用特效/文字后调 inject + 记录 effects_source）——涉核心 agent + AE 端到端，须隔离测，单独推进。

## 六、测试 / 风险 / 合入顺序

- **测试**：inject 幂等性（重跑不翻倍）+ round-trip（inject 后 --edl replay 产出 == 现场规划产出）+ lint 闸门。round-trip 测须 run_dir 夹具（可用 run53 真实产物，只读）。
- **风险**：① effects 权威源歧义（决策点1）——最大风险，须先定；② 改 mastercut_agent 涉 AE 端到端，须隔离测；③ inject 写 edl.json（run 目录，git-ignored，低风险）。
- **合入顺序**：1) 定决策点1 → 2) 落 inject_edl_tracks.py（隔离新文件）+ 手动 round-trip 验证 → 3) 接 mastercut_agent（端到端测）→ 4) 文档/回归。

---

> 返回 → [[📝-计划文件-MOC]] · 依据 → `09-计划文件/2026-09-11_管线集成与Skill封装落地方案.md` §1.2 Step2 · 前置 → `Step1_AE链消费EDL_补丁草案.md`（§2+§3+§4+Step1.5 已合入）
