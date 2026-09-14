---
tags: [补丁草案, EDL, 数据契约, Step0, 管线集成, 未落地]
date: 2026-09-11
status: APPLIED-2026-09-12
target: scripts/edl.py
based_on: 09-计划文件/2026-09-11_管线集成与Skill封装落地方案.md §1.2 Step0
---

# Step 0 补丁草案：EDL v1.1（effects / text_events / overlays 三轨 + lint L7）

> **状态：✅ 已合入（2026-09-12）**。C1-C4 已用 SearchReplace 精确落地到 `scripts/edl.py`（211→254 行）；新建 `tests/test_edl_v11_tracks.py`（9 测全过）；`tests/test_edl_regression.py` 版本断言改为版本无关。**pytest: 19 passed / 2 failed**——2 失败为 `render_regression.py` emoji×Windows GBK 预存编码 bug（不调 edl.py，非本次引入）。**未 git commit**（留给用户统一提交）。
> ~~**状态：草案，未落地**。~~（以下为原草案正文，保留作变更记录）`scripts/edl.py` 合入前 git clean，并行字体/文字会话未触碰它。
> **设计原则**：**纯追加 + FORWARD/BACKWARD 双兼容**——旧调用方（不传新参）产出与现状一致（仅 schema_version 号变）；旧 `edl.json`（1.0）仍被 lint 接受；旧 consumer 读新 edl 时忽略不认识的段。依据：数据契约兼容规则（DEEP_RESEARCH [29]）+ video-use overlays 段（[5]）。

---

## 一、改动摘要（4 处，均在 `scripts/edl.py`）

| # | 位置 | 改动 | 兼容性 |
|---|---|---|---|
| C1 | 版本常量（L34 附近） | `EDL_SCHEMA_VERSION` 1.0→1.1；新增 `SUPPORTED_EDL_SCHEMA_VERSIONS={"1.0","1.1"}` | BACKWARD（旧 1.0 文件仍合法） |
| C2 | `build_edl()` 签名 | 新增 3 个 keyword-only 可选参 `effects/text_events/overlays=None` | BACKWARD（默认 None，旧调用不变） |
| C3 | `build_edl()` 返回 | `return {...}` 改为 `edl={...}` + **仅当参数非 None 才写入**对应段 | FORWARD（不传则输出无新段） |
| C4 | `lint_edl()` | L1 改"∈ 支持集"；新增 **L7**（三轨时间不越界 + 必备字段 + effect 的 skill_id 必填） | 追加校验，不改 L1-L6 语义 |

---

## 二、精确 diff（before → after）

### C1 · 版本常量

```python
# BEFORE (L34-35)
EDL_SCHEMA_VERSION = "1.0"
HASH_CHUNK = 1 << 20  # 1MB 分块读文件算 SHA1

# AFTER
EDL_SCHEMA_VERSION = "1.1"                       # 1.0→1.1: 新增 effects/text_events/overlays 三轨(FORWARD 兼容)
SUPPORTED_EDL_SCHEMA_VERSIONS = {"1.0", "1.1"}   # lint L1 接受的历史版本(BACKWARD 兼容旧 edl.json)
HASH_CHUNK = 1 << 20  # 1MB 分块读文件算 SHA1
```

### C2 · build_edl 签名（在 `resolution=(1920, 1080),` 后、`) -> dict:` 前插入）

```python
# BEFORE (L58-68)
def build_edl(
    production_report_path: str | Path,
    *,
    bgm_path: str | None = None,
    sources: list | None = None,
    style: str | None = None,
    theme: str | None = None,
    duration: float | None = None,
    fps: int = 24,
    resolution=(1920, 1080),
) -> dict:

# AFTER
def build_edl(
    production_report_path: str | Path,
    *,
    bgm_path: str | None = None,
    sources: list | None = None,
    style: str | None = None,
    theme: str | None = None,
    duration: float | None = None,
    fps: int = 24,
    resolution=(1920, 1080),
    effects: list | None = None,       # v1.1 视觉特效轨(对齐 schemas/visual_effect_schema.json)
    text_events: list | None = None,   # v1.1 文字事件轨(对齐 text_overlay/events.json)
    overlays: list | None = None,      # v1.1 覆盖层轨(独立渲染的效果/木偶 alpha; video-use 式)
) -> dict:
```

### C3 · build_edl 返回（把结尾的 `return {...}` 改为先赋值再条件追加）

```python
# BEFORE (L111-130)
    return {
        "schema_version": EDL_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "production_report": str(pr_path),
        "render": {
            "style": style,
            "theme": theme,
            "duration": duration,
            "fps": fps,
            "resolution": list(resolution),
        },
        "inputs": inputs,
        "cuts": cuts,
        "cut_points": [round(t, 4) for t in cut_points],
        "toolchain": {
            "ffmpeg": _ffmpeg_version(),
            "python": sys.version.split()[0],
            "edl_schema": EDL_SCHEMA_VERSION,
        },
    }

# AFTER
    edl = {
        "schema_version": EDL_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "production_report": str(pr_path),
        "render": {
            "style": style,
            "theme": theme,
            "duration": duration,
            "fps": fps,
            "resolution": list(resolution),
        },
        "inputs": inputs,
        "cuts": cuts,
        "cut_points": [round(t, 4) for t in cut_points],
        "toolchain": {
            "ffmpeg": _ffmpeg_version(),
            "python": sys.version.split()[0],
            "edl_schema": EDL_SCHEMA_VERSION,
        },
    }
    # v1.1 三轨：仅当调用方显式传入才写入 —— 旧调用产出与 1.0 结构一致(最小惊讶 + FORWARD 兼容)
    if effects is not None:
        edl["effects"] = effects
    if text_events is not None:
        edl["text_events"] = text_events
    if overlays is not None:
        edl["overlays"] = overlays
    return edl
```

### C4 · lint_edl（L1 改支持集；函数末尾 `return errs` 前插入 L7）

```python
# BEFORE (L150-152)
    if edl.get("schema_version") != EDL_SCHEMA_VERSION:
        errs.append(f"L1 schema_version {edl.get('schema_version')!r} "
                    f"!= {EDL_SCHEMA_VERSION!r}")

# AFTER
    _sv = edl.get("schema_version")
    if _sv not in SUPPORTED_EDL_SCHEMA_VERSIONS:
        errs.append(f"L1 schema_version {_sv!r} not in "
                    f"{sorted(SUPPORTED_EDL_SCHEMA_VERSIONS)}")
```

```python
# BEFORE (L174-180, 函数结尾)
    declared = (edl.get("render") or {}).get("duration")
    if declared is not None and prev_end > 0:
        if abs(declared - prev_end) > duration_tolerance:
            errs.append(f"L5 duration mismatch: declared {declared} "
                        f"vs timeline end {round(prev_end, 3)}")

    return errs

# AFTER (在 return errs 之前插入 L7；复用 cuts 循环算出的 prev_end 作时间线末端)
    declared = (edl.get("render") or {}).get("duration")
    if declared is not None and prev_end > 0:
        if abs(declared - prev_end) > duration_tolerance:
            errs.append(f"L5 duration mismatch: declared {declared} "
                        f"vs timeline end {round(prev_end, 3)}")

    # --- L7 (v1.1): 三轨校验 —— 时间不越界 + 必备字段 + effect.skill_id 必填 ---
    _tend = prev_end  # cuts 循环后的时间线末端
    _tol = duration_tolerance
    for i, ov in enumerate(edl.get("overlays") or []):
        st, du = ov.get("start_in_output"), ov.get("duration")
        if not ov.get("file"):
            errs.append(f"L7 overlay#{i} missing file")
        if st is None or du is None:
            errs.append(f"L7 overlay#{i} missing start_in_output/duration")
            continue
        if st < -1e-6 or du <= 0:
            errs.append(f"L7 overlay#{i} invalid start/duration [{st},+{du}]")
        elif _tend > 0 and st + du > _tend + _tol:
            errs.append(f"L7 overlay#{i} exceeds timeline {st}+{du}>{round(_tend,3)}")
    for i, ef in enumerate(edl.get("effects") or []):
        tr = ef.get("time_range") or {}
        s, e = tr.get("start_sec"), tr.get("end_sec")
        if s is None or e is None or not (s < e):
            errs.append(f"L7 effect#{i} invalid time_range [{s},{e})")
        elif _tend > 0 and e > _tend + _tol:
            errs.append(f"L7 effect#{i} end {e} exceeds timeline {round(_tend,3)}")
        if not (ef.get("evidence_chain") or {}).get("skill_id"):
            errs.append(f"L7 effect#{i} missing evidence_chain.skill_id")
    for i, te in enumerate(edl.get("text_events") or []):
        ti, to = te.get("t_in"), te.get("t_out")
        if ti is None or to is None or not (ti < to):
            errs.append(f"L7 text_event#{i} invalid t_in/t_out [{ti},{to})")
        elif _tend > 0 and to > _tend + _tol:
            errs.append(f"L7 text_event#{i} t_out {to} exceeds timeline {round(_tend,3)}")

    return errs
```

> **注**：`lint_edl` 的 `duration_tolerance` 已是形参（默认 1.5），L7 直接复用，不新增参数。L7 只在对应段存在时触发——旧 1.0 文件无三段 → L7 全跳过，零回归。

---

## 三、新增测试（独立文件，不碰 `tests/test_edl_regression.py`）

新建 `tests/test_edl_v11_tracks.py`：

```python
"""EDL v1.1 三轨(effects/text_events/overlays) + lint L7 + 双兼容 回归测试。"""
import json
from pathlib import Path
from scripts.edl import (build_edl, lint_edl, save_edl,
                         EDL_SCHEMA_VERSION, SUPPORTED_EDL_SCHEMA_VERSIONS)


def _mk_pr(tmp_path: Path, segs=None) -> Path:
    """造一个最小 production_report.json（build_edl 的输入）。"""
    segs = segs if segs is not None else [
        {"index": 0, "start_time": 0.0, "end_time": 2.0,
         "source_file": None, "source_start": 0.0, "speed": 1.0,
         "transition": "cut", "mood": "intro", "energy": 0.3},
        {"index": 1, "start_time": 2.0, "end_time": 4.0,
         "source_file": None, "source_start": 5.0, "speed": 1.0,
         "transition": "cut", "mood": "drop", "energy": 0.9},
    ]
    pr = tmp_path / "production_report.json"
    pr.write_text(json.dumps({"script": {"segments": segs}}), encoding="utf-8")
    return pr


def test_version_bump():
    assert EDL_SCHEMA_VERSION == "1.1"
    assert "1.0" in SUPPORTED_EDL_SCHEMA_VERSIONS  # BACKWARD


def test_backward_compat_no_new_tracks(tmp_path):
    """不传新参 → 输出无 effects/text_events/overlays 键（旧调用最小惊讶）。"""
    edl = build_edl(_mk_pr(tmp_path))
    assert "effects" not in edl and "text_events" not in edl and "overlays" not in edl
    assert lint_edl(edl) == []          # L1-L7 全过


def test_lint_accepts_legacy_1_0(tmp_path):
    edl = build_edl(_mk_pr(tmp_path))
    edl["schema_version"] = "1.0"        # 模拟旧文件
    assert not any(e.startswith("L1") for e in lint_edl(edl))


def test_forward_new_tracks_present_and_valid(tmp_path):
    edl = build_edl(
        _mk_pr(tmp_path),
        effects=[{"effect_id": "b1", "effect_type": "bloom",
                  "time_range": {"start_sec": 2.0, "end_sec": 3.0},
                  "parameters": {}, "envelope": {"enabled": False},
                  "evidence_chain": {"skill_id": "bloom_drop"}}],
        text_events=[{"t_in": 2.0, "t_out": 3.5, "word": "最強",
                      "style_id": "drop_impact", "skill_id": "text_style_contrast"}],
        overlays=[{"file": "fx/wa2_alpha.mp4", "start_in_output": 1.0,
                   "duration": 2.0, "source_skill_id": "puppet_alpha"}],
    )
    assert edl["effects"] and edl["text_events"] and edl["overlays"]
    assert lint_edl(edl) == []


def test_l7_overlay_exceeds_timeline(tmp_path):
    edl = build_edl(_mk_pr(tmp_path),
                    overlays=[{"file": "x.mp4", "start_in_output": 3.0, "duration": 5.0}])
    assert any("overlay#0 exceeds timeline" in e for e in lint_edl(edl))


def test_l7_overlay_missing_file(tmp_path):
    edl = build_edl(_mk_pr(tmp_path),
                    overlays=[{"start_in_output": 0.5, "duration": 1.0}])
    assert any("overlay#0 missing file" in e for e in lint_edl(edl))


def test_l7_effect_bad_range_and_missing_skill(tmp_path):
    edl = build_edl(_mk_pr(tmp_path), effects=[
        {"effect_id": "e", "effect_type": "bloom",
         "time_range": {"start_sec": 3.0, "end_sec": 1.0},   # 逆序
         "parameters": {}, "evidence_chain": {}},            # 无 skill_id
    ])
    errs = lint_edl(edl)
    assert any("effect#0 invalid time_range" in e for e in errs)
    assert any("effect#0 missing evidence_chain.skill_id" in e for e in errs)


def test_l7_text_event_out_of_bounds(tmp_path):
    edl = build_edl(_mk_pr(tmp_path),
                    text_events=[{"t_in": 3.0, "t_out": 99.0, "word": "x"}])
    assert any("text_event#0 t_out 99.0 exceeds timeline" in e for e in lint_edl(edl))


def test_save_reload_roundtrip(tmp_path):
    edl = build_edl(_mk_pr(tmp_path), overlays=[
        {"file": "a.mp4", "start_in_output": 0.0, "duration": 1.0}])
    p = save_edl(edl, tmp_path / "edl.json")
    back = json.loads(p.read_text(encoding="utf-8"))
    assert back["overlays"] == edl["overlays"]
    assert lint_edl(back) == []
```

**验收**：`.venv/Scripts/python.exe -m pytest tests/test_edl_v11_tracks.py tests/test_edl_regression.py -q` 全绿（新测 + 旧回归均过 = 零破坏）。

---

## 四、兼容性论证（三向）

| 方向 | 场景 | 结果 |
|---|---|---|
| **BACKWARD**（旧数据/旧调用→新代码） | 旧 `edl.json`(1.0) 过新 `lint_edl` | L1 ∈ 支持集 → 通过；无三段 → L7 跳过 |
| | 旧调用 `build_edl(pr)` 不传新参 | 输出无三段键，结构同 1.0（仅版本号 1.1） |
| **FORWARD**（新数据→旧 consumer） | 旧 `build_master_polish`/`build_text_overlay` 读含三段的 edl | 它们只取 `cuts`/`production_report`，多余段被忽略（dict 取键不报错） |
| **自身** | 新 consumer 取 `effects/text_events/overlays` | Step1 的 `--edl` 消费端按需读取 |

> 唯一"破坏性"是 `schema_version` 号 1.0→1.1——但 L1 已改为"∈ 支持集"，旧文件不受影响；`toolchain.edl_schema` 同步为 1.1（信息字段，无 consumer 强依赖）。

## 五、合入方式与时机（隔离）

- **合入方式（二选一）**：① 你确认后我用 SearchReplace 按上文 before/after **精确落地**到 `scripts/edl.py` + 新建测试文件（最稳，逐块精确匹配）；② 生成 `.patch` 后 `git apply`（需 edl.py 未被并行会话改动，当前 clean）。
- **时机**：`edl.py` 当前 git clean、不在字体/文字会话的活跃文件集（其活跃集为 `build_text_overlay.py` + `schemas/font_registry.json` 等字体文件）→ **理论上可立即合入无冲突**。但遵循本会话"不落地"承诺 + 协作规约，**等你一句"合入"再动手**。
- **不连带**：本 Step 0 **不改** `build_text_overlay.py`/`build_master_polish.py`（那是 Step1，且 build_text_overlay 正被并行会话占用）——Step0 只动 edl.py + 新测试，与字体工作零交集。
- **回滚**：`git checkout scripts/edl.py` + 删 `tests/test_edl_v11_tracks.py`（纯追加，回滚无损）。

## 六、Step0 之后（不在本补丁内）

Step0 只提供"契约承载能力"。真正打通双链需 Step1（`build_text_overlay`/`build_master_polish` 加 `--edl` 消费三段）——**该步涉及并行会话活跃文件，须串行协调后再做**。

---

> 返回 → [[📝-计划文件-MOC]] · 依据 → `09-计划文件/2026-09-11_管线集成与Skill封装落地方案.md` §1.2
