---
tags: [补丁草案, EDL桥, Step2b, mastercut_agent, 编排器接线, 未落地]
date: 2026-09-13
status: APPLIED-2026-09-13（3 处 diff 已落地, 63 passed; AE e2e 待真实 run）
targets: [agents/mastercut_agent.py]
depends_on: Step2_编排器接线与EDL轨道回填_草案.md（inject_edl_tracks.py 已落地）
---

# Step 2b 草案：mastercut_agent 自动接线（让管线自动回填 EDL 轨道）

> **状态：已落地（2026-09-13）**。三处 diff 均已应用于 `agents/mastercut_agent.py`：白名单放宽(复用 RUN_DIR_PATTERN) + tag 派生守卫(r1_fixed 须显式 tag) + inject 非侵入接线。验证：py_compile OK / 两个 lazy import 解析 OK / **63 passed**(含新增 tests/test_mastercut_edl_wiring.py 3 测：r1_fixed 无tag报错 / 非法run_dir拒绝 / r1_fixed+显式tag放行到lut阶段)。**完整 AE e2e 待真实 run 顺带验证**(inject 接线 guarded, 失败不阻断)。
> **为何草案**：mastercut_agent 是核心 agent（862 行, clean）+ 涉 AE 端到端，且侦察发现 2 处微妙（第三白名单 + tag 派生），须确认后落。

---

## 〇、侦察发现（agents/mastercut_agent.py，2026-09-13）

`_apply_effects_to_video`（L194-）流程：
```
L222 out_dir = Path(output_dir)                        # run 输出目录 (如 output/unified_run53)
L227 if not fullmatch(r"unified_run\d+", run_dir_name) # 🔴 第三处白名单 — 同样挡 r1_fixed!
L236 tag = run_dir_name.removeprefix("unified_")       # 🔴 unified_r1_fixed_v7 → "r1_fixed_v7" 非法 tag
L255 effects_json = out_dir/f"{tag}_schema_effects.json"  # ✅ 权威 effects 文件(此路径无歧义)
L256 effects_json.write_text(effects)                  # 写入已校验特效
L260 cmd = [python, build_master_polish.py, run_dir_name, tag, "--effects-json", effects_json]
L266 build = sp.run(cmd, ...)                          # 调 build_master_polish 应用特效
L271 report_p = tmp/effects_injection_report.json      # 读注入记账
L305 if dry_run: return                                # dry_run 早返回(不产视频)
L312 aep = out_dir/"polish"/"master.aep"               # 真实路径: 继续渲染
```

**两个关键发现**：
1. 🔴 **第三处白名单**（L227 `unified_run\d+`）：即便 Step1.5 放宽了两个 build 脚本，mastercut_agent 仍会在 L227 拒绝 `unified_r1_fixed_vN`——编排器路径下 R1 run 进不来。
2. 🔴 **tag 自动派生对 r1_fixed 失效**（L236）：`unified_r1_fixed_v7`.removeprefix → `r1_fixed_v7`，不符 tag 白名单 `run\d+`（L237 会拒）。→ r1_fixed run 须**显式传 tag**（如 run7）。
3. ✅ **effects 权威源无歧义**：mastercut_agent 自己写 `{tag}_schema_effects.json` 并显式传给 build_master_polish。inject 直接用这个路径即可（run53 那 3 个 `*effects*.json` 是手动跑遗留，非此路径产物）。

## 一、精确 diff（3 处，均在 `_apply_effects_to_video`）

### 1.1 放宽第三白名单（L227，复用 Step1.5 单一真源）

```python
# BEFORE (L227)
    if not _re.fullmatch(r"unified_run\d+", str(run_dir_name)):
        return {
            "success": False,
            "error": (f"output_dir 目录名 '{run_dir_name}' 不符合 build_master_polish.py "
                      f"白名单 unified_run\\d+ — 无法定位 run 目录"),
# AFTER
    from scripts.build_master_polish import RUN_DIR_PATTERN   # 单一真源(Step1.5), 避免三处漂移
    if not _re.fullmatch(RUN_DIR_PATTERN, str(run_dir_name)):
        return {
            "success": False,
            "error": (f"output_dir 目录名 '{run_dir_name}' 不符合白名单 "
                      f"unified_run<N> | unified_r1_fixed_v<N> — 无法定位 run 目录"),
```

### 1.2 tag 派生对 r1_fixed 失败时要求显式 tag（L235-236）

```python
# BEFORE (L235-236)
    if tag is None:
        tag = str(run_dir_name).removeprefix("unified_")   # unified_run53 → run53
# AFTER
    if tag is None:
        _derived = str(run_dir_name).removeprefix("unified_")   # unified_run53 → run53
        if not _re.fullmatch(r"run\d+", _derived):
            return {"success": False, "effects_applied": 0, "effects_requested": len(effects),
                    "error": (f"run '{run_dir_name}' 无法自动派生合法 tag(得 '{_derived}'); "
                              f"r1_fixed 类须显式传 tag=runN")}
        tag = _derived
```

### 1.3 特效应用后自动回填 EDL（在 L310 dry_run 早返回之后，真实成功路径）

```python
# 插入位置: L310 (dry_run return 之后) 与 L312 (aep = ...) 之间
    # Step2 §4: 特效已由 build_master_polish 应用到 AE → 事后回填 EDL 轨道
    # (非侵入: 失败只记日志, 绝不阻断主流程 — 同 unified_edit L520 EDL 块口径)
    try:
        from scripts.inject_edl_tracks import inject_edl_tracks
        _inj = inject_edl_tracks(out_dir, effects_file=str(effects_json))
        result["edl_inject"] = {"effects": _inj["effects_injected"],
                                "text_events": _inj["text_events_injected"],
                                "lint_errors": _inj["lint_errors"]}
        logger.info(f"[edl-inject] effects={_inj['effects_injected']} "
                    f"text_events={_inj['text_events_injected']} "
                    f"lint={len(_inj['lint_errors'])}")
    except Exception as _ie:  # noqa: BLE001
        logger.warning(f"[edl-inject 跳过] {_ie}")
```

## 二、放置决策（dry_run vs 真实路径）

- **选真实路径**（L310 之后）：dry_run 只生成 plan+JSX **未应用到 AE**，此时回填会让 edl.json 记录"未真正应用"的特效，违背"EDL=已应用审计真源"。**故 inject 只在真实成功路径跑**。
- **代价**：dry_run 不触发 inject → 无法用 dry_run 端到端测 inject 接线。**缓解**：inject_edl_tracks 本体已 7 测 + 真实数据 round-trip 实证；接线是 3 行 guarded 调用，py_compile + dry_run 向后兼容测即可，完整 AE e2e 待真实 run 顺带验证。
- **text_events 时序**：inject 读 out_dir/text_overlay/events.json。若 build_text_overlay 在特效之后才跑，此刻 events.json 可能不存在 → inject 跳过 text_events（幂等，文字步骤后再跑一次 inject 即补上）。**建议**：文字步骤后也调一次 inject（或统一在管线末尾调一次 inject 收口两轨）。

## 三、隔离测策略

| 测什么 | 怎么测 | 需 AE? |
|---|---|---|
| inject 本体逻辑 | tests/test_inject_edl_tracks.py（已 7 测）| 否 |
| 白名单放宽 | 单测 `_apply_effects_to_video` 的 run_dir 校验分支（r1_fixed 通过 / 垃圾拒）| 否 |
| tag 派生 | 单测 r1_fixed 无显式 tag → 明确报错 | 否 |
| dry_run 向后兼容 | 调 `_apply_effects_to_video(dry_run=True)` 确认 inject 块不触发、既有行为不变 | 否（dry_run 不调 AE）|
| inject 接线 in-situ | 真实 run 顺带验证（guarded, 失败不阻断）| 是（延后）|

## 四、风险 / 合入顺序

- **风险**：① mastercut_agent 是核心 agent — 改动限 `_apply_effects_to_video` 内 3 处，均 additive/guarded；② 白名单放宽复用 Step1.5 单一真源（RUN_DIR_PATTERN），不新增漂移；③ inject 调用 try/except 包裹，失败只 warning 不阻断（同 unified_edit EDL 块）；④ AE e2e 不可隔离测 → 靠 guarded + 本体已测兜底。
- **合入顺序**：1) 落 1.1+1.2（白名单+tag，纯校验，可单测）→ py_compile + 白名单/tag 单测；2) 落 1.3（inject 接线）→ py_compile + dry_run 向后兼容测；3) 真实 run 时验证 in-situ inject + lint。**不 git commit**（同前，待你统一提交）。

---

> 返回 → [[📝-计划文件-MOC]] · 前置 → `Step2_编排器接线与EDL轨道回填_草案.md`（inject_edl_tracks 已落地）· 单一真源 → `scripts/build_master_polish.py::RUN_DIR_PATTERN`
