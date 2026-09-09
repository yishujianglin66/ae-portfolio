# cut_visibility 根因诊断报告（B1 / R1）

> 日期：2026-09-09 · 对象：`output/unified_run61/polish/master_hr.mp4`（当前最佳候选）
> 方法：新增逐切点诊断工具 `scripts/cut_visibility_diag.py`（与官方口径完全一致）+ 交叉验证项目自有的 `scripts/cutpoint_selfeval.py`
> 结论性质：**根因已定位，收益已量化，修复方案已存在但未接线**

---

## 一、结论先行

| 项 | 结果 |
|---|------|
| 根因 | **76 处 `frozen_cut`**（切点两侧画面几乎没变），非"闪白频率"问题 |
| 当前 cut_visibility | 0.8698（官方采样 12 点口径） |
| 全切点真实均值 | **0.6909**（远低于官方口径——采样恰好避开了多数弱切点） |
| 修复后预期 | **0.9969**（模拟：把被采样的 frozen 切点提到中位数水平） |
| 是否超 0.92 目标线 | ✅ 是（+0.127） |
| 修复工具 | **已存在**：`scripts/cutpoint_selfeval.py:repair_cutpoints/repair_loop` |
| 阻塞点 | `unified_edit.py:510` **只检测不修复**——检测出 76 处事故仍照常出片 |

---

## 二、度量口径（必须先说清，否则会修错方向）

`cut_visibility` 定义（`scripts/score_reference_gap.py:112-118`）：

```
切点 t 的可见性 = mean(|norm(frame(t - 1/24)) - norm(frame(t + 3/24))|)
其中 norm(x) = (x - mean(x)) / std(x)      ← 零均值单位方差归一化
```

**关键推论**：归一化会把整体亮度/闪白变化消掉。因此：
- ❌ 加闪白、加白场过渡 → 对该指标**无效**（这正是 run61 加闪白后 0.8696→0.8698 无变化的原因）
- ✅ 让切点两侧的**画面内容结构**真正不同 → 有效

采样方式：`cuts[::max(1, n//12)][:12]`——110 个切点里只取索引 0,9,18,…,99 共 12 个。

---

## 三、逐切点诊断结果

### 3.1 分布（110 个切点全测）

| 统计量 | 值 |
|--------|-----|
| 均值 | 0.6909 |
| 中位数 | 0.8861 |
| 标准差 | 0.4520 |
| min / max | 0.0014 / 1.3659 |

| 阈值 | 切点数 | 占比 |
|------|--------|------|
| < 0.05 | 8 | 7% |
| < 0.1 | 11 | 10% |
| < 0.2 | 26 | 24% |
| < 0.5 | 44 | 40% |
| < 0.8 | 48 | 44% |

### 3.2 最弱切点（可见性接近 0）

| t(s) | 可见性 | 说明 |
|------|--------|------|
| 21.708 | 0.0014 | 后一帧为纯色（std=0.5，仅 4 个灰度值）——黑场/淡出 |
| 26.708 | 0.0044 | |
| 12.833 | 0.0045 | |
| 12.458 | 0.0056 | |
| 0.833 | 0.0071 | |
| 8.083 | 0.0106 | |

**纯色帧是极端情形**：归一化后成为常数向量，与任何帧的差异都趋近 0。

### 3.3 官方采样恰好避开多数弱切点

官方 12 个采样点的可见性：1.1555, 1.3188, 0.8327, 1.1740, 0.9392, **0.0529**, 0.8897, **0.2288**, 1.1534, **0.4356**, 1.0666, 1.1899

→ 只有 3 个明显偏低。**这说明 0.8698 这个数字系统性高估了实际切点质量**（全切点均值仅 0.6909）。

---

## 四、交叉验证：两把独立的尺子指向同一批切点

项目自有的 `scripts/cutpoint_selfeval.py`（吸收 video-use "每切点 self-eval" 设计）对同一成片的判定：

```
verdict: FAIL
issues: 132 条 = frozen_cut 76 + audio_pop 56
```

其中 frozen_cut 判据：切点两侧 ahash/dhash Hamming 距离 < 10（`FREEZE_HAMMING_DEFAULT`）。

**交叉验证结果**：26 个弱切点（vis<0.2）中，**16 个（62%）与 frozen_cut 对应**（±0.06s 容差）。两套独立检测器（帧差归一化 vs 感知哈希）指向同一批问题切点。

### 注意：两把尺子不完全等价

| t(s) | cut_visibility | 是否 frozen_cut |
|------|---------------|----------------|
| 4.88 | 0.8327 | 是 |
| 25.50 | 1.0666 | 是 |
| 13.46 | **0.0529** | 是 |

说明：`frozen_cut`（结构哈希相似）会误报一些帧差很大的切点（画面整体构图相似但细节差异大）。**修复时应以 cut_visibility 为准做最终验收，frozen_cut 作为候选定位器**。

---

## 五、修复收益模拟

在 110 个切点上模拟"把 frozen_cut 对应的切点可见性提升到中位数（0.9071）"：

| 场景 | 官方口径 | 全切点均值 |
|------|---------|-----------|
| 当前 | 0.8698 | 0.6909 |
| 修复被采样的 frozen（6 个） | **0.9969** | — |
| 修复全部 76 个 frozen | **0.9969** | 0.8134 |

**判定：只要修掉 frozen_cut，cut_visibility 即达 0.9969，远超 0.92 目标线。**

> 注：这是上限模拟（假设修复后切点达到中位数水平）。实际修复需真实重渲后复测。

---

## 六、修复路径（工具已存在，缺接线）

`scripts/cutpoint_selfeval.py` 已实现：

```python
repair_cutpoints(cut_times, issues, fps)   # frozen_cut/min_gap → 丢弃；audio_pop → ±1 帧微调
repair_loop(render_fn, cut_times, video_path, max_rounds=3)  # analyze → repair → render → 再检
```

**当前状态**：`unified_edit.py:510-521` 只调 `analyze_cutpoints` 写报告，**不调 `repair_loop`**。即：检测出 76 处事故，仍然照常出片并标记为成功。

### 建议接线（待 Boss 确认，涉及重渲成本）

1. **丢弃式修复优先**：frozen_cut 对应的切点直接丢弃（该处视觉上本来就没切），不重渲——可在**后期**用切点表重建，成本低。
2. **若必须重渲**：接入 `repair_loop`，`render_fn` 注入 ProductionDirector 的重渲接口，`max_rounds=3`。
3. **验收线**：`cut_visibility ≥ 0.92`（当前 0.8698），每轮留 evidence。

---

## 七、与既有认知的差异（重要）

| 原报告说法 | 实测结论 |
|-----------|---------|
| "差距源于切点帧内容，参照集为硬内容跳变，本项目为效果叠加" | **方向对，但具体机制是 frozen_cut（切点两侧画面没变），不是"效果叠加不足"** |
| "先修 `tmp/post_freeze.py` 滤镜图拼接 bug" | **两者无关**。`post_freeze.py` 是后期冻结帧实验脚本；`AEKV_IMPACT_SHIFT` 在 `build_master_polish.py:875`，是定格内容平移机制。frozen_cut 根因在**编排阶段切点选择**，与二者都不直接相关 |
| "AEKV_IMPACT_SHIFT=1 重评" | 该开关改变的是"定格帧显示哪一帧"，**不解决切点两侧画面相同的问题**——不建议作为 R1 主路径 |
| "闪白频率问题" | **已证伪**：归一化会消掉亮度变化，闪白对该指标无效 |

---

## 八、证据索引

| 证据 | 路径 |
|------|------|
| 逐切点诊断原始数据 | `reports/cutvis_run61.json`（110 切点全量） |
| 切点事故检测 | `output/unified_run61/run61_cutpoints.json`（132 issues，verdict FAIL） |
| EDL 切点表 | `output/unified_run61/edl.json`（107 cut_points） |
| 诊断工具 | `scripts/cut_visibility_diag.py` |
| 修复工具（已有） | `scripts/cutpoint_selfeval.py` |
| 参照集同口径分位数 | `reports/reference_stats.json` |

复现命令：

```bash
python scripts/cut_visibility_diag.py --video output/unified_run61/polish/master_hr.mp4 --weakest 15
python scripts/cutpoint_selfeval.py --video output/unified_run61/polish/master_hr.mp4 \
    --cutpoints output/unified_run61/edl.json
```
