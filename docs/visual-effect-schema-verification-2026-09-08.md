# 视觉特效 Schema 链路 —— P0 修复与实证记录

**日期：** 2026-09-08
**范围：** 修复 2026-09-07「Task 8 / 计划 Task 3」遗留的执行链路断裂与假绿灯
**结论：** 链路已打通并通过真实 aerender 验证；但 **6 种 premium 插件类型仍无渲染实现**，属部分交付

---

## 1. 修复了什么

### 1.1 执行链路断裂（致命）

`_apply_effects_to_video()` 的调用方式与被调方契约完全脱节。

| 项 | 修复前 | 修复后 |
|---|---|---|
| 被调方参数形式 | 裸读 `sys.argv[1]`/`[2]`，零 argparse | argparse，位置参数 `<run_dir> <tag>` **契约不变** |
| Agent 传参 | `--input-video --effects-json --output-dir --tag` | `<run_dir> <tag> --effects-json <path>` |
| 结果 | `returncode=1`，**特效从未落地** | 链路跑通 |

实测的失败证据（修复前复现）：

```
[ERR] 非法 run 目录名(白名单 unified_run\d+): --input-video
returncode = 1
期望产物存在? False
>>> _apply_effects_to_video 实际会返回 success=False
```

原代码注释本身就承认是猜的：`# Note: This assumes build_master_polish.py accepts
--effects-json parameter`。这违反项目铁律「禁止任何未经实证的猜测式修改」。

### 1.2 补齐缺失的渲染步骤

`build_master_polish.py` **只建 comp 存 `polish/master.aep`，不产 mp4**。旧实现却
等待 `<tag>_polished.mp4` —— 没有任何代码会生成那个文件。

现在链路是两段：

```
build_master_polish.py <run> <tag> --effects-json X   →  polish/master.aep
render_master.py       <run> <tag>                    →  polish/<tag>_master.mp4
```

### 1.3 三层假绿灯全部拆除

| 位置 | 旧行为 | 新行为 |
|---|---|---|
| `_stage_render_cut` | 无条件 `effects_applied: len(effects)`，即使应用失败也报全量成功 | 只报 `effects_applied`（实测数），另出 `effects_unmapped` / `effects_skipped` / `effects_success` / `effects_error` |
| `render_run53v43_premium.py` | `.get('effects_applied', len(effects))` 兜底掩盖缺失 | 删除兜底，逐项对账打印 |
| `render_run53v43_premium.py` | 读 `result.data` —— **该字段不存在**（实为 `.output`），`hasattr()` 恒 False → 无论真实结果如何都走 FAIL 分支 | 读 `result.output`，并区分「工具未抛异常」与「渲染真成功」 |

另外两处新加的失败显式化：

- `build_master_polish.py`：Bridge 超时返回 `None` 时，旧代码只 `print` 后以 **0** 退出；现在 `sys.exit(4)`
- `build_master_polish.py`：schema 注入后 `applied_count == 0` 时 `sys.exit(3)`，拒绝空渲染
- `_apply_effects_to_video`：产物 `< 100KB`（`MIN_RENDER_BYTES`）判为黑屏/空合成，不算成功

### 1.4 顺带修掉的编码崩溃

旧代码 `subprocess.run(..., text=True)` 解码中文版 AE 的 GBK 输出会抛
`UnicodeDecodeError` 并拖垮 reader 线程（本次排查中真实复现过）。改为 bytes +
`errors="replace"`，并统一注入 `PYTHONIOENCODING=utf-8`。

### 1.5 第三个坏调用方

`scripts/apply_run53v43_effects.py` 有 **6 处各自独立的致命缺陷**（缺 tag 位置参数、
把 `jsx_script.name` 当脚本正文传给 `new Function()`、判定不存在的 `"success"` 键、
裸调 PATH 上的 `aerender`、渲染 `-comp POLISH` 而实际合成叫 `MASTER`、只查存在不查体积）。
已重写为委托 `agents.mastercut_agent` 单一实现，不在两处复制逻辑。

---

## 2. 实证证据

### 2.1 schema→plan→JSX 翻译（18 项测试，1.3s，不碰 AE）

`tests/test_visual_effect_schema.py` — **18 passed**

| 用例 | 输入 | 可执行 | 无实现 | 已跳过 | JSX 内实测效果条目 |
|---|---|---|---|---|---|
| 5 示例 | 5 | 4 | 1 (twixtor) | 0 | **4** ✓ |
| run53v43_effects | 8 | 6 | 2 (twixtor, zoom_pan) | 0 | **6** ✓ |
| …_dense | 135 | 110 | 5 | 20 (`radial` 非法定名) | — |
| …_premium_v2 | 139 | **33** | **106** | 0 | **33** ✓ |

关键性质（均有测试钉住）：

- **对账闭合**：`applied + unmapped + skipped == input`，四个文件全部成立 → 无静默丢弃
- **报告不虚报**：`report.applied_count` == JSX 内 `var shots/bursts` 载荷里的效果实例数
- **映射表无空洞**：schema 17 类型 ↔ 三张映射表，双向差集均为 `∅`
- **matchName 全部真实**：JSX 中出现的 matchName ⊆ `RECIPES` 值集。实测用到
  `ADBE Glo2`、`GUTS BadTV`、`RWB Fast Bokeh`、`CC Radial Fast Blur`、`CC Force Motion Blur`。
  **6 种 premium 插件类型留在 `SCHEMA_UNMAPPED`，未编造任何 matchName**
  （遵守「matchName 使用前必须枚举实证」硬约束）

### 2.2 真实 aerender 渲染（AE 当时空闲，无并发冲突）

```
[render] aerender master.aep (comp MASTER) → run53_master.mp4
[OK] output\unified_run53\polish\run53_master.mp4 (59238 KB)
```

`ffprobe` 内容校验：

| 项 | 值 |
|---|---|
| 视频 | h264 **1920x1080** @ **24/1** fps |
| 帧数 | **720** = 精确 **30.0s** |
| 音频 | aac，1408 帧 |
| 流数 | 2 |
| 体积 | **59,238,698 B（57.8 MB）** — 远超 100KB 铁律阈值 |
| 魔数 | `00 00 00 18 66 74 79 70 6d 70 34 32` → `ftyp` / `mp42` 合法 ISO BMFF |

**这条证明的是渲染半段**（`aerender_exe()` 解析、`render_master.py`、100KB 闸门、
新链路的产物路径）。它渲染的是 09-06 已验收的 `master.aep`，
**不是** schema 注入后的新 aep。

### 2.3 CLI 契约回归

| 调用 | 期望 | 实测 |
|---|---|---|
| `<run> <tag> --dry-run` | 可跑 | 通过（规范路径行为不变） |
| `--input-video X --effects-json Y …`（旧坏形式） | 明确拒绝 | `unrecognized arguments`，rc=2 |
| `evil_dir run53` | 白名单拒绝 | rc=2 |
| `unified_run53 "BAD TAG"` | 白名单拒绝 | rc=2 |
| `--help` | 列出新参数 | rc=0，含 `--effects-json` / `--dry-run` |

`ruff check`（项目闸门）对 5 个改动文件：**All checks passed**。

---

## 3. 尚未证明 / 尚未完成

1. **schema 注入 → AE 真实建合成 → 渲染** 这半段未做端到端实证。
   需要 AE 前台运行 + Bridge 监听器在线，而 `build_jsx` 生成的脚本会执行
   `app.project.close(DO_NOT_SAVE_CHANGES)` + `app.newProject()` ——
   **会销毁 AE 中当前打开的工程**。09-07 晚有并发会话正在编辑 `run53_premium_v3`，
   故未擅自触发。需在 AE 空闲且确认无未保存工作时执行：
   ```
   python scripts/build_master_polish.py output/unified_run53 run53 \
          --effects-json output/unified_run53/run53v43_effects.json
   python scripts/render_master.py output/unified_run53 run53
   ```
2. **6 种 premium 插件类型无 RECIPES 实现** —— `run53v43_effects_premium_v2.json`
   的 139 条中 106 条不可渲染（film_stocks 26 / magic_bullet_looks 20 / delirium 20 /
   particular 20 / optical_flares 15 / sapphire_glow 4，另 twixtor 1 走独立通道）。
   插件本身**确实已安装**（`docs/plugin_inventory.md` 2026-09-07 记录 86+ 插件），
   缺的是经 AE 枚举验证的 matchName 与参数索引。
3. **schema 三处数据缺陷未改**（详见 summary 的 Known Gaps）：`flow_angle`
   上限 180 应为 360、`radial`/`radial_blur` 命名分裂、`time_range` 缺跨字段约束。
4. **交付物未入 git** —— `agents/`、`schemas/`、两份文档全部 `??` 未跟踪。

---

## 4. 改动清单

| 文件 | 变化 |
|---|---|
| `scripts/build_master_polish.py` | 47,740 → 58,015 B。新增 `_parse_args()`、`SCHEMA_TO_RECIPE`/`SCHEMA_DYN_RECIPE`/`SCHEMA_UNMAPPED`/`BURST_TYPES`、`schema_effects_to_plan()`；`main()` 改 argparse + 注入 + `--dry-run` + Bridge 失败非零退出；bursts 不再被 `plan_bursts` 无条件覆盖 |
| `agents/mastercut_agent.py` | 25,382 → 30,586 B。重写 `_apply_effects_to_video()`；`_stage_render_cut()` 加 `effects_dry_run` 并如实上报；新增 `MIN_RENDER_BYTES` |
| `scripts/render_run53v43_premium.py` | 111 → 162 行。修 `.data`→`.output`、删兜底、加对账打印与 `--dry-run`、退出码分级 0/2/1 |
| `scripts/apply_run53v43_effects.py` | 重写为委托单一实现，清除 6 处缺陷 |
| `tests/test_visual_effect_schema.py` | 新建，280 行 / 18 项，1.3s |
| `docs/visual-effect-schema-summary.md` | 更正 11→17、Status 由「✅ COMPLETED」改为「⚠️ 部分完成」、加更正说明与 Known Gaps |

---

## 5. 2026-09-09 Schema 缺口修复

**日期：** 2026-09-09
**范围：** 修复 summary Known Gaps 中的 3 项数据缺陷 + particular 插件实现
**结论：** 3 项缺口已闭合，particular 已可渲染，测试从 18 增至 20 项全通过

### 5.1 flow_angle 上限 180 → 360

- 文件: `schemas/visual_effect_schema.json`
- 光流方向是 0-360°，dense 文件有 10 条数据用到 210/240/270/300/330，旧上限导致全部不通过
- `maximum` 从 180 改为 360

### 5.2 radial 别名加入 schema enum

- 文件: `schemas/visual_effect_schema.json` + `scripts/build_master_polish.py`
- dense 文件 20 条用 `radial`（RECIPES 键名），schema enum 只认 `radial_blur`，导致全部 skipped
- 双向兼容：schema enum 加 `"radial"` 作为合法值，`SCHEMA_TO_RECIPE` 加 `"radial": "radial"` 直接映射
- dense 文件 skipped 从 20 降为 0

### 5.3 particular 加入 RECIPES

- 文件: `scripts/build_master_polish.py`
- matchName `tc Particular` 已在 `.ae-mcp-bridge/enhance_v2.jsx` 和 `rebuild_v2.jsx` 中成功使用
- RECIPES 新增 `"particular"` 条目（velocity/life/size/pps 4 个默认参数）
- `SCHEMA_UNMAPPED` 删除 `"particular"` 条目，剩余 5 种 premium 插件

### 5.4 测试更新

- `tests/test_visual_effect_schema.py` 从 18 项增至 20 项：
  - 新增 `test_radial_alias_maps_to_same_recipe`: 验证 `radial` 和 `radial_blur` 映射到同一 RECIPES 键
  - 新增 `test_flow_angle_360_accepted`: 验证 270° 配置通过 schema、400° 被拒绝
  - 更新 `test_unmapped_premium_types_have_no_fabricated_matchname`: 移除 particular

### 5.5 预期产出

| 指标 | 修复前 | 修复后 |
|---|---|---|
| schema enum 类型数 | 17 | 18 (+radial 别名) |
| dense 文件 skipped (radial) | 20 | 0 |
| dense 文件 flow_angle 不通过 | 10 | 0 |
| SCHEMA_UNMAPPED 条目数 | 6 | 5 |
| premium_v2 可渲染 | 33 | 33 (+20 particular) |
| 测试数 | 18 | 20 |

### 5.6 剩余缺口

- 5 种 premium 插件 (sapphire_glow / optical_flares / delirium / magic_bullet_looks / film_stocks) 仍需 AE 枚举实证
- time_range 跨字段约束仍在翻译层兜底（JSON Schema draft-07 不支持数值比较）
