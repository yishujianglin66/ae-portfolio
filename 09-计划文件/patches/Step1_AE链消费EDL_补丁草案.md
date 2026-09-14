---
tags: [补丁草案, EDL桥, Step1, 管线集成, 数据契约, 未落地]
date: 2026-09-12
status: §2+§3+Step1.5(白名单)-APPLIED-2026-09-12 · §4-DEFERRED
targets: [scripts/build_master_polish.py, scripts/build_text_overlay.py, scripts/edl.py]
depends_on: Step0_EDL_v1.1_补丁草案.md（已合入：EDL 已具 effects/text_events/overlays 三轨 + lint L7）
---

# Step 1 补丁草案：AE 链消费 EDL（`--edl` + lint 契约闸门）

> **状态：§2（edl.load_edl）+ §3（build_master_polish --edl）已合入并验证（py_compile ✅ · --edl 注册 ✅ · pytest 45 passed，含 test_visual_effect_schema 回归）；§4（build_text_overlay）仍为草案，待 ZCode 字体会话空闲后重定位锚点再落**。目的：让 `build_master_polish.py` / `build_text_overlay.py` 能吃 `edl.json` 的三轨，使 R1 修复成果经 EDL 单一真源传导到视觉/文字层（解 K3「双链无桥」）。
> **依据**：落地方案 §1.2 Step1；数据契约"管线内嵌校验"（DEEP_RESEARCH [28][29]）；video-use `render.py <edl.json>` 单命令消费契约 [5]。

---

## 〇、隔离警示（必读，决定本草案的落地策略）

| 文件 | git 状态 | 落地策略 |
|---|---|---|
| `scripts/edl.py` | clean（本会话 Step0 已改，我方可控） | ✅ **可精确落地**（§2 共享 helper） |
| `scripts/build_master_polish.py` | **clean**（1148 行，稳定） | ✅ **可精确落地**（§3 精确 diff） |
| `scripts/build_text_overlay.py` | 🔴 **M（并行会话实时重写中）** | ⛔ **仅设计级**（§4）——侦察期间该文件 1369→1402 行持续增长，ZCode 正加 `--mood/--entropy/--speed/--seed` 等参数。**锚点必漂移，须待其落地并协调后重定位再改** |

**结论**：Step1 拆两半——**§2+§3（edl.py + build_master_polish）可立即落地**（与字体会话零交集）；**§4（build_text_overlay）挂起待协调**。

---

## 一、前置依赖（已满足）

Step0 已合入：`edl.py` 的 EDL v1.1 具 `effects/text_events/overlays` 三轨 + `lint_edl` L7 + `SUPPORTED_EDL_SCHEMA_VERSIONS`。本 Step1 在其上加"消费端"。

---

## 二、共享 helper：`edl.load_edl()`（精确，落 `scripts/edl.py`）

两个消费端共用的"读取 + lint 契约闸门"。加在 `save_edl` 之后（edl.py 当前 L149 附近）：

```python
def load_edl(path: str | Path, *, run_lint: bool = True) -> dict:
    """读取 edl.json 并跑 lint 契约闸门(fail-fast)。

    数据契约"管线内嵌校验"(DEEP_RESEARCH [28]): 违约不向下游传播。
    run_lint=False 仅用于调试/迁移期读旧文件。
    """
    p = Path(path)
    edl = json.loads(p.read_text(encoding="utf-8"))
    if run_lint:
        errs = lint_edl(edl)
        if errs:
            raise ValueError(f"EDL lint FAIL ({len(errs)}): " + "; ".join(errs[:8]))
    return edl
```

> 导出：`from scripts.edl import build_edl, save_edl, lint_edl, load_edl`。

---

## 三、`build_master_polish.py --edl`（精确 diff，文件 clean）

### 3.1 `_parse_args()` 加 `--edl`（在 `--effects-json` 后、`--dry-run` 前，当前 L797/798 之间）

```python
# BEFORE (L796-799)
    ap.add_argument("--effects-json", dest="effects_json", default=None,
                    help="visual_effect_schema.json 兼容配置; 传入时取代内部 plan_effects 的 fx 规划")
    ap.add_argument("--dry-run", action="store_true",
                    help="只生成 plan + JSX 并落盘, 不调用 AE Bridge (离线验证用)")

# AFTER
    ap.add_argument("--effects-json", dest="effects_json", default=None,
                    help="visual_effect_schema.json 兼容配置; 传入时取代内部 plan_effects 的 fx 规划")
    ap.add_argument("--edl", dest="edl", default=None,
                    help="edl.json 路径; 提供时先过 lint 契约闸门, 并在无 --effects-json 时用其 effects 轨")
    ap.add_argument("--dry-run", action="store_true",
                    help="只生成 plan + JSX 并落盘, 不调用 AE Bridge (离线验证用)")
```

### 3.2 `main()` 加载 + lint EDL（在 `segs = pr["script"]["segments"]` 后，当前 L821 之后插入）

```python
# BEFORE (L820-823)
    pr = json.loads(pr_p.read_text(encoding="utf-8"))
    segs = pr["script"]["segments"]

    inj_report = None

# AFTER
    pr = json.loads(pr_p.read_text(encoding="utf-8"))
    segs = pr["script"]["segments"]

    # Step1: --edl 数据契约闸门(读+lint, fail-fast)。仅显式传入才启用 → 无 --edl 时零行为变化(BACKWARD)
    _edl = None
    if args.edl:
        from scripts.edl import load_edl
        _edl_p = Path(args.edl)
        if not _edl_p.exists():
            print(f"[ERR] --edl 不存在: {_edl_p}")
            sys.exit(2)
        try:
            _edl = load_edl(_edl_p)          # lint 失败抛 ValueError
        except ValueError as _e:
            print(f"[ERR] EDL 契约校验失败: {_e}")
            sys.exit(2)

    inj_report = None
```

### 3.3 effects 来源改为优先级链（当前 L823-832 的 `if args.effects_json:` 块）

```python
# BEFORE (L823-832)
    inj_report = None
    if args.effects_json:
        ej = Path(args.effects_json)
        if not ej.exists():
            print(f"[ERR] --effects-json 不存在: {ej}")
            sys.exit(2)
        _eff = json.loads(ej.read_text(encoding="utf-8"))
        if isinstance(_eff, dict):
            _eff = _eff.get("effects") or _eff.get("effect_configs") or [_eff]
        plan, bursts, inj_report = schema_effects_to_plan(_eff)

# AFTER (优先级: 显式 --effects-json > EDL effects 轨 > 无)
    inj_report = None
    _eff = None
    if args.effects_json:                              # 优先级1: 显式文件(向后兼容)
        ej = Path(args.effects_json)
        if not ej.exists():
            print(f"[ERR] --effects-json 不存在: {ej}")
            sys.exit(2)
        _eff = json.loads(ej.read_text(encoding="utf-8"))
    elif _edl is not None and _edl.get("effects"):     # 优先级2: EDL effects 轨(Step1 桥)
        _eff = _edl["effects"]
    if _eff is not None:
        if isinstance(_eff, dict):
            _eff = _eff.get("effects") or _eff.get("effect_configs") or [_eff]
        plan, bursts, inj_report = schema_effects_to_plan(_eff)
```

> L833 起（`base = plan_effects(segs, run_dir, tag)` 及后续合并逻辑）**不变**——只是 `_eff` 的来源多了一条 EDL 通道。`segs` 仍来自 production_report（EDL 由其派生，同 run 一致）；EDL 的 `overlays` 轨留待 Step1.5（合成层）消费。

---

## 四、`build_text_overlay.py --edl`（🔴 设计级，文件正被并行会话重写，勿直接套用）

> **警告**：以下锚点为 2026-09-12 快照（该文件 1369→1402 行实时增长中）。**合入前必须重新定位**，且须与字体/变款会话协调（避免同文件冲突）。

### 4.1 契约设计

`--edl <path>` 提供时：
1. `load_edl(path)`（读 + lint 契约闸门，同 §2）。
2. **若 `edl["text_events"]` 非空 → 直接作为事件表**（事件成为上游 EDL 契约，跳过从 segments+onsets 的现场生成）——这是"单一真源"的核心收益。
3. 若 `edl["text_events"]` 缺失 → **回退**当前逻辑（`load_segments` + `load_onsets` 现场生成），保证 BACKWARD。
4. `edl["cuts"]` 可替代 `load_segments(run_dir)` 的 production_report 读取（cuts 是 segments 的规范化子集）；`edl["overlays"]` 供未来预渲染覆盖层引用。

### 4.2 插入点（provisional，需重定位）

| 位置 | 快照行号 | 改动 |
|---|---|---|
| argparse | ~L1248-1264（`--seed` 后） | 加 `--edl`（同 §3.1 语义） |
| `main()` 事件构建前 | ~L1278（production_report 存在性检查后） | 加 EDL 加载 + lint；若 `text_events` 存在则走"直接消费"分支，否则现状生成 |
| `load_segments`（L283）| 稳定 | 可选：加 `from_edl(edl)` 变体，用 `edl["cuts"]` 映射为 segments 结构 |

### 4.3 与并行会话的协调点

- ZCode 正在加的 `--mood/--entropy/--speed/--seed`（变款 PRNG）与 `--edl` **正交**，无逻辑冲突，但**同文件编辑需串行**（协作规约§九：提交前 `git diff --staged` 复核，防卷入）。
- 建议：待 ZCode 字体会话告一段落并 commit 后，基于其最新版重定位锚点再落 §4。

---

## 五、测试草案（`tests/test_master_polish_edl.py`，§3 落地后可跑）

```python
"""build_master_polish --edl 消费 EDL effects 轨 + lint 闸门（dry-run，不碰 AE）。"""
import json, subprocess, sys
from pathlib import Path
PROJECT = Path(__file__).resolve().parent.parent

def _edl_with_effects(tmp_path, effects):
    # 造一个最小合法 edl.json（schema_version 1.1 + cuts + effects）
    edl = {"schema_version": "1.1", "render": {"duration": 4.0, "fps": 24},
           "inputs": [], "cuts": [
               {"index": 0, "start_time": 0.0, "end_time": 2.0, "source_file": None,
                "source_start": 0.0, "speed": 1.0, "transition": "cut"},
               {"index": 1, "start_time": 2.0, "end_time": 4.0, "source_file": None,
                "source_start": 5.0, "speed": 1.0, "transition": "cut"}],
           "cut_points": [2.0], "effects": effects, "toolchain": {}}
    p = tmp_path / "edl.json"; p.write_text(json.dumps(edl), encoding="utf-8"); return p

def test_edl_effects_equal_effects_json(tmp_path):
    """--edl 的 effects 轨 与 --effects-json 同配置 → plan 一致（dry-run 比对）。"""
    eff = [{"effect_id": "b1", "effect_type": "bloom",
            "time_range": {"start_sec": 2.0, "end_sec": 3.0},
            "parameters": {"threshold": 0.8, "radius": 6, "intensity": 0.38},
            "envelope": {"enabled": False},
            "evidence_chain": {"skill_id": "bloom_drop"}}]
    edl_p = _edl_with_effects(tmp_path, eff)
    ej_p = tmp_path / "eff.json"; ej_p.write_text(json.dumps(eff), encoding="utf-8")
    # 两次 dry-run（--edl vs --effects-json）比对落盘 plan（需 run_dir 有 production_report）
    # 断言: 两路 schema_effects_to_plan 产出的 applied 计数一致
    ...  # 落地时补 run_dir 夹具（复用 test_edl_regression 的 _make_report 思路）

def test_edl_lint_gate_blocks_bad_contract(tmp_path):
    """EDL 含越界 overlay/effect → load_edl 抛错 → build_master_polish exit 2。"""
    bad = [{"effect_id": "x", "effect_type": "bloom",
            "time_range": {"start_sec": 9.0, "end_sec": 1.0},  # 逆序 → L7
            "parameters": {}, "evidence_chain": {"skill_id": "s"}}]
    edl_p = _edl_with_effects(tmp_path, bad)
    from scripts.edl import load_edl
    import pytest
    with pytest.raises(ValueError):
        load_edl(edl_p)
```

---

## 六、兼容性 / 优先级 / 风险

- **BACKWARD**：不传 `--edl` → build_master_polish 行为逐字节不变（`_edl=None`，effects 仍走 --effects-json/base plan）。
- **优先级**：`--effects-json`（显式）> `edl["effects"]`（契约）> base plan。避免"两个来源同时生效"的歧义。
- **lint 闸门**：`--edl` 传入即跑 `lint_edl`，违约 exit 2（数据契约"不向下游传播坏数据"[28]）——这是 EDL 桥相对"直接读 production_report"的核心增量（契约保证）。
- **run-agnostic（✅ 已解 Step1.5）**：`--edl` 可指任意 edl.json。原 build_master_polish 的 run_dir 白名单 `unified_run\d+` 会拒绝 `unified_r1_fixed_v7`（§八 实证发现的 K3 卡点），**现已放宽为 `unified_(?:run\d+|r1_fixed_v\d+)`**（提取为可测常量 RUN_DIR_PATTERN，严格 fullmatch 防遍历语义不变）→ 桥现在**能指向 R1 修复run**，K3「R1→视觉」最后一步已通。
- **风险**：`segs` 仍来自 production_report（非 edl.cuts）——因 build_master_polish 需要 segment 的 `zoompan_effect` 等完整字段，EDL cuts 是规范化子集不含这些。**Step1 只桥接 effects 轨**；完整"EDL 作唯一 timeline 源"留待后续（需 EDL cuts 扩字段或 build_master_polish 改读 cuts）。

## 七、合入顺序与时机

1. **立即可落**（与字体会话零交集）：§2（edl.load_edl）+ §3（build_master_polish --edl）+ §5 测试。
2. **挂起待协调**：§4（build_text_overlay --edl）——待 ZCode 字体会话 commit 后重定位锚点。
3. 落地方式：你确认后我用 SearchReplace 精确应用 §2/§3（clean 文件），跑 §5 测试 + 既有回归，**不 git commit**。

## 八、真实数据实证结果（2026-09-12，零共享副作用）

§2+§3 已合入。用 run53 真实 `production_report.json`(116 segments) + 真实 `run53v43_effects.json`(8 特效)，走 `build_edl(effects=)→save_edl→load_edl(lint 闸门)→schema_effects_to_plan`：

- ✅ `lint_edl` **PASS(0 errs)** — 契约闸门在真实数据上校验通过
- ✅ `load_edl` 闸门放行，edl.effects=8
- ✅ **6/8 特效搬运到 plan/bursts**：plan=[bloom,badtv,bokeh,fmb] / bursts=[burst_radial,burst_badtv]
- ✅ twixtor + zoom_pan **如实记为 unmapped**（"不接受外部注入"/"由 segments 驱动"），skipped=0 — **无静默丢弃**
- ✅ 全程未写 `tmp/master_plan.json`（mtime 仍 09-07）、未碰 output/、未跑 ffmpeg/AE — 外科式直调，零共享污染

**结论**：EDL 桥在真实数据上通了（视觉链一端）。

### 实证暴露的 2 个真实缺口（合成夹具未发现 → 交 Step2）

1. **`build_edl` 不自动推导 `render.duration`**：它是显式 kwarg，调用方不传则 `duration=None`（lint 容忍，但下游读到 null）。→ Step2 编排器建 EDL 时须显式传 duration（可从 segments 末帧 end_time 算）。
2. ✅ **已解（Step1.5，本会话）**：`build_master_polish` run_dir 白名单原 `unified_run\d+` 挡住 R1 修复run → 已放宽为 `unified_(?:run\d+|r1_fixed_v\d+)`（提取 RUN_DIR_PATTERN/TAG_PATTERN 常量 + tests/test_master_polish_whitelist.py 4 测：接受 runN+r1_fixed_vN、拒绝遍历/垃圾/_BAD、CLI exit2 前置拦截）。**K3「R1→视觉」最后卡点已清**，49 passed（含 visual_effect_schema 回归）。

---

> 返回 → [[📝-计划文件-MOC]] · 依据 → `09-计划文件/2026-09-11_管线集成与Skill封装落地方案.md` §1.2 · 前置 → `Step0_EDL_v1.1_补丁草案.md`（已合入）
