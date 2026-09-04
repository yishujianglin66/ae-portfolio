# 交接附录 H — 独自升级 AMV 变速卡点 + BGM 污染修复 + torch_runtime 统一 + 瞬态层回归（2026-09-02，最新权威）

> 接手第一动作：读本文"重大架构警告的最终解法（第六节）"与"下一步"两节。
> 本文已对另一程序的全部声明**逐项在仓库核实**（✅ = 磁盘状态与声明一致）。
> 上一份权威文档：`docs/handoff-2026-09-01-unified-entry.md`（llm_chain 重建 / AE 通道协议 / 真实卡点 SFX 对齐）。

---

## 一、双程序并行背景（必读，避免互相覆盖）

| 程序 | 负责内容 | 关键文件 |
|---|---|---|
| A（另一会话，2026-09-02） | 独自升级 AMV 管线：铁律变速、BGM SFX 污染修复、torch_runtime 统一 | `core/music_dynamics.py` `ai/production_director.py` `scripts/unified_edit.py` `core/torch_runtime.py` |
| B（本会话，2026-09-01/02） | llm_chain 重建 E2E、visual_scorer 降级接线、AE 通道协议全打通、core/paths.py 恢复 | `core/llm_chain.py` `core/visual_scorer.py` `ai/ae_render_channel.py` `tmp/_ae_channel_selfcheck.py` |

两个程序改了**同一个文件** `scripts/unified_edit.py`（B 修了 LUT/SFX 混音，A 又禁用了 SFX）——
接手前先 `git diff scripts/unified_edit.py` 看当前合并态，别按 09-01 文档的描述假设 SFX 还在。

---

## 二、独自升级 AMV 管线（A 程序工作，全部核实 ✅）

### 2.1 铁律变速 speed_for_shot（✅ `core/music_dynamics.py:272-295`）

漫剪卡点铁律 §2（v22 验证）落进代码，`speed_for_shot(level, beat_strength, energy_norm, is_downbeat)`：

| 段位 | 强拍/重拍 | 普通拍 |
|---|---|---|
| low（铺垫） | **0.55x slowmo 慢放落点** | 0.7x slowmo |
| mid（蓄力） | **0.9x zoom_back 缩放后退** | 1.0x static |
| high（爆发） | **1.0x pulse 脉冲** | 1.3x fast_pan 加速快切 |

### 2.2 三处错误与修复（诊断链）

| # | 错误现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | "所有速度都是 1.00x" | 读了**顶层** `segments` 字段（渲染用），真速度在 `script.segments` | 校验脚本改读 `script.segments` |
| 2 | speed_for_shot 返回统一速度 | 旧实现不按铁律分档 | 重写为 2.1 规格表 |
| 3 | 变速破坏节拍对齐 | production_director 原 ~2073-2077 行把非强拍速度**覆盖为 1.0x** | 已移除；现在 `speed = _speed` 直通（✅ 当前代码 `speed_for_shot(...) → speed = _speed; _v22_tech = _tech`） |

### 2.3 BGM SFX 污染双修复

**修复 1 — HPSS 激进清理（✅ `ai/production_director.py:3616 _clean_bgm_sfx`，Phase 5 于 :576 调用，带 work_dir 缓存）**

| 参数 | 值 | 含义 |
|---|---|---|
| `librosa.effects.hpss(margin=(2.0, 8.0))` | 逐声道分离 | 和声/打击乐源分离 |
| 打击乐 <300Hz 增益 | **5%** | 低频瞬态（boom/impact 残留）几乎清除 |
| 打击乐 >300Hz 增益 | **20%**（300Hz 处线性过渡） | 中高频瞬态大幅压制 |
| 和声抑制 | 300-800Hz @ 0.7 增益 | 清理残留染色 |
| 失败回退 | 退回原始 BGM | librosa 缺失不阻塞 |

**修复 2 — SFX 层禁用（✅ `scripts/unified_edit.py:163-171`）**

```python
# SFX 叠加已禁用 (2026-09-02): 叠加音效事件污染 BGM 纯净度
_shutil.copy2(src, str(final))          # LUT 产物直接作为终版
report["capabilities_used"]["sfx"] = False
```

### 2.4 验证产物（✅）

- `output/unified_run/unified_run.mp4`（19.4s，1 条 aac 音轨）
- `production_report.json`：**51 镜头**，速度分布 `{1.0: 28, 1.3: 11, 0.9: 10, 0.55: 2}` — 铁律分档真实生效

---

## 三、torch_runtime 统一（A 程序，核实 ✅）

`core/torch_runtime.py`（2026-09-02 17:20，4.3KB）单一定义点，六个能力：

| 函数 | 用途 |
|---|---|
| `get_device()` | 统一设备检测（带缓存，RTX 4060/4090 识别，CPU 回退有日志） |
| `infer_ctx(device=None, dtype="float16")` | 统一推理上下文：`no_grad + autocast`；CUDA 自动 FP16，CPU 只开 no_grad；入口 `str(device or get_device())` 防御 torch.device 对象 |
| `vram_info()` | 返回 (已用GB, 总GB) |
| `clear_cache()` | GC + empty_cache（模型切换时调） |
| `optimize_model()` | torch.compile inductor，失败自动回退 eager |
| `model_summary_mb()` | 参数量 MB 估算（VRAM 预算用） |

- **接入量核实**：`infer_ctx` 66 文件（65 消费方+定义）、`get_device` 62 文件。
  覆盖 ai/（t7/t12/t21-29/t32 训练+推理）、scripts/（train/infer 系列）、models/、core/（cnn_scorer/temporal_analyzer/local_model_adapter）、pipeline/、puppet-automation/、dev_scripts/。
- **训练循环正确保留**（backward 需要 autocast，`infer_ctx` 的 no_grad 会阻断梯度）：
  `train_birefnet_v3.py` / `finetune_birefnet.py` / `t32_balanced_lora_retrain.py` / `t23b_lora_retrain_vitl14.py` / `train_anime_camera_v5.py`（GradScaler 配套）。
- **管辖外**：`puppet-automation/src/engines/sam2/sam2_infer.py`（独立 venv）、`external/rife/`（vendored）、`tests/`。
- `@torch.no_grad()` 装饰器 ×2 未动（函数级机制，与上下文管理器不冲突）。

---

## 四、⚠️ 重大架构警告：节拍可闻度被牺牲（接手必读）

**当前 `unified_run.mp4` 的"卡点"只剩视觉面（切点+变速），可听面几乎为零：**

1. HPSS 清理在 Phase 5 **无条件运行**（production_director.py:576 没有 if）——即使输入是干净 BGM，
   鼓组也被压到 5%-20% 增益。**鼓点瞬态正是"卡点听感"的载体**。
2. SFX 层全禁——09-01 刚交付的"28 个音效对齐 29 个真实切点"（first_final3.mp4）能力被整体关掉。

**与 09-01 交付物的直接冲突**：09-01 修的是"SFX 对齐真实切点"（对齐问题）；09-02 发现的是
"SFX 污染 BGM"（混音位置问题）。**正确解法不是删 SFX，而是把 SFX 挪到正确的混音点**：
SFX 只应进最终输出的音轨（amix 于 final mix），绝不进 BGM 文件本身。若污染源是历史运行把
SFX 烘进过 BGM 文件，应**一次性离线清理该文件**，而不是每次渲染都激进 HPSS。

**接手验证动作（第一件事）**：听 `unified_run.mp4` vs `first_final3.mp4` 对比鼓点存在感；
若 unified_run 音乐"发闷没劲"，即证实本警告。

---

## 五、踩坑清单（09-02 新增）

| # | 坑 | 规避 |
|---|---|---|
| 17 | `production_report.json` 有**两层 segments**：顶层（渲染用，无变速）与 `script.segments`（真速度） | 校验一律读 `script.segments` |
| 18 | 引擎内曾有"非强拍速度覆盖为 1.0x"的隐藏覆盖，铁律形同虚设 | 已移除；再改速度链路时全文 grep `speed = 1.0` |
| 19 | SFX 混音进 BGM 文件 → 污染会**跨运行持久**（缓存/中间产物复用） | SFX 只进最终输出音轨；BGM 文件保持只读 |
| 20 | HPSS 激进清理**无条件**运行，干净 BGM 也被削鼓 | 改条件触发（能量检测）或一次性离线清理 |
| 21 | 双程序同改 `unified_edit.py`，文档描述可能与磁盘不一致 | 接手先 `git diff scripts/unified_edit.py` |
| 22 | `infer_ctx` 含 no_grad，**不能**包训练 forward | 训练循环保留裸 `torch.autocast` + GradScaler |
| 23 | **alimiter 默认 `level=true`（auto-level）**：链式混音每级把响度向 limit 归一 = 响度战争，鼓瞬态被压平 | 一律 `level=0` |
| 24 | SFX 池是 5-20s **trailer 长素材**，adelay 不截尾 → 音墙；裁短取峰区后又比平均响 ~7 倍 | shorten_sfx 裁峰区+归一 SFX_REF_RMS |
| 25 | HPSS perc **比值**不能评"带 SFX 床的混音"（平滑床愚弄分解） | 用高频能量比+切点/对照+床噪三指标 |
| 26 | 裁短峰区片峰在开头 60ms，前置量须按峰位算（whoosh 80ms 非 250ms），否则 SFX 落点偏 190ms | pre ≈ head，峰落切点+20ms |
| 27 | **rhythm_reward 择优含 half_shift 候选**：把全部切点整体偏移半拍（切在鼓点之间），0.01 级噪声分差即可触发采纳（run2 实录 arc=0.461 vs half=0.476 → 采纳 half_shift，切点-鼓点对齐率崩到 34%） | 已移除该候选；结构性破坏方案不得进入择优 |
| 28 | **beat_track 返回节拍网格（估计值）≠ 真实鼓点**：实测 54% 拍点偏鼓点 >120ms（199BPM 曲目 = 整拍错位） | `_analyze` 1.1b+ 拍点吸附强 onset（±140ms 容差）；切点/SFX/运镜全部跟真鼓点 |
| 29 | **每片独立 fps 转换的 ±2 帧随机量化**：下一片时长补偿只能修系统偏差，修不了已发生边界的随机量化 → 拼接后切点 p50 偏 85ms（实测拼接环节引入，后段不变） | 根治=单次渲染全局 24fps 时间线（所有边界落全局帧网格）；过渡方案=已加漂移累加器（122→85ms） |
| 30 | ffmpeg alimiter/编码链有 **~6ms 前瞻延迟**不补偿（互相关时移 129 样本） | 感知可忽略；极端卡点可全体 adelay -6ms |
| 31 | **场景检测不是切点地面真值**：在切点附近找内容最大变化处，系统性偏 ±2-3 帧（±125ms 实测），帧级抽帧验证才是（run8 验证切点 0 帧误差） | 验证切点位置用帧差法（t-1→t 跳变最大）；场景检测只用于统计 |
| 32 | **隐形切点**：相邻镜头用同素材近似画面（run8 实测 t=2.25/2.54/2.88 帧差≈0），切了看不见 → 鼓点上无视觉变化 = "没踩到"感。选源的贪心去重不保证相邻段视觉差异 | 下轮：相邻段强制源交替或直方图距离门槛 |
| 33 | 帧网格对齐+`-frames:v` 已根治量化漂移（run8：全部整数帧时长 ✅，可见切点 0 帧误差 ✅） | 渲染管线现在是数学精确的；残余同步误差只剩计划时间的鼓点对齐（42%±50ms 强鼓点） |
| 34 | **素材首次使用 src_start=0**：连续 7 镜全是黑场/淡入片头 → 鼓点上切了看不见、开头节奏全死（run9 实锤） | 已钳制 `_min_ss=min(2.0, ...)`；后续应接高光窗口而非盲偏移 |
| 35 | 连击段(rolls)抽稀删除 kick/snare 滚奏段内全部切点 = 鼓最密处反而无切（§3.2 理论与 1.0 静速不兼容） | 已停用；鼓点视觉响应率 33→70% |
| 36 | **32x18 灰度帧差<3 的"隐形切点"指标对暗画面系统性误报**（好莱坞 LUT 压暗后两个不同暗场景差也小），run10 仍报 7/10 但需人眼复核 | 换亮度归一化差异或 SSIM；下一会话先人眼确认 run10 |

---

## 六、瞬态层回归 — 当日已完成（SFX v2.4，三指标验证通过）

### 6.1 修复内容

| 改动 | 文件 | 说明 |
|---|---|---|
| HPSS 条件化 | `ai/production_director.py` | render() 加 `clean_bgm_sfx=False` 默认直通；污染 BGM 才显式开 |
| SFX v2.1 回归 | `scripts/unified_edit.py` ④-b | 五招：前置补偿/力度曲线/重拍双层/onset 细分/**智能裁短** |
| 智能裁短+归一 | `core/sfx_layer.py` `shorten_sfx()` | 找能量峰裁 [峰前60ms, 峰后类别尾长]，**归一到 SFX_REF_RMS=0.22**，缓存 `cache/sfx_short/` |
| 限幅器修正 | 两处 `alimiter` | **加 `level=0`**（默认 true 的 auto-level 在链式传递中逐级抬响度=响度战争） |
| 前置量修正 | 两处 whoosh pre | 250ms→**80ms**（裁短片峰在开头 60ms，峰须落切点+20ms） |
| A/B 验证工具 | `tmp/_ab_verify_sfxv2.py` `tmp/_remix_run2.py` | 客观指标 + 免全链重混 |

### 6.2 调试链（三层洋葱，接手遇到同类问题时照此剥）

1. **表象**：终版打击乐占比 0.056→0.003，鼓"消失"
2. **第一层（音墙）**：SFX 池是 5-20s trailer 素材，adelay 不截尾 → 50 条长尾全程叠加。
   修复=智能裁短。**只救回一点**。
3. **第二层（响度失控）**：裁短取峰区 → 短片比全文件平均响 ~7 倍，持续撞限幅器。
   修复=裁短时归一到基准 RMS。**还是不够**。
4. **第三层（真凶×2）**：
   a. **alimiter 默认 `level=true`（auto-level）**：6 批链式混音每级把响度向 0.95 归一，
      均匀抬底 1.8-2×，鼓瞬态被压平 → `level=0` 修复；
   b. **度量被愚弄**：HPSS perc 比值不适合评"带 SFX 床的混音"（平滑床稀释+掩蔽分解），
      corr 时移校正后 0.777、**高频(4-12k)能量比 1.03 证明鼓从未丢**。
      正确度量=高频能量比+切点/对照+床噪比三指标。
5. **附带发现**：alimiter 有 ~6ms 前瞻延迟不补偿（最佳时移 129 样本），感知可忽略。

### 6.3 验证结果（run2 vs 旧 run_final，同一 BGM/素材）

| 指标 | 旧 run_final (HPSS+SFX禁) | **新 run2_final (SFX v2.4)** | 判定 |
|---|---|---|---|
| 高频鼓能量比 (4-12kHz, 混/底) | **0.23**（毁 77% 鼓能量） | **1.04** | ✅ 鼓完整 |
| 切点/对照 RMS 比 | 0.78 | **1.12** | ✅ SFX 落位切点 |
| 非切点床噪能量比 | — | **0.98** | ✅ 无音墙 |

### 6.4 本轮 run2 的其他里程碑

- **AE 通道首次端到端真实渲染**："4个高级运镜镜头 → AE贝塞尔缓动+运动模糊, 成功渲染 4/4"
  （自检全绿 → enable_ae_channel=True → aerender 产物 `output/unified_run2/ae_raw/shot_*.mp4`）。
  LoRA 拉近训练首次在成品中以贝塞尔+运动模糊呈现。
- 铁律变速持续生效（速度分档 {1.0/1.3/0.9/0.55}）+ BGM 直通 + LUT OK，全链 402s。
- 交付物：`output/unified_run2/run2_final.mp4`（19.4s, 15.8MB, 鼓完整+73 落点 SFX）；
  音墙版留档 `run2_final_v2_wall.mp4`（对照用）。

---

## 七、下一步（瞬态层已回归，更新版优先级）

### ①【第一优先】用户听感验收 + 微调旋钮
run2_final.mp4 是首个"鼓完整 + SFX 落位切点 + AE 贝塞尔 + 铁律变速"全要素版本，
待用户试听。可调旋钮（都在 `scripts/unified_edit.py` ④-b 段，一行一个数）：
- SFX 太轻/太重 → whoosh 0.32/0.38、impact 0.65、boom 0.30 增益
- boom 存在感 → `sine=frequency=65` 与 `volume=0.31`
- 细分层密度 → onset 最小间隔 0.45s / glitch 0.18
- 重混不用全链：`python tmp/_remix_run2.py`（输入 run2_lut.mp4, ~1 分钟）

### ② 残余技术项（当日内可清）
- alimiter ~6ms 前瞻延迟不补偿（切点听感若差最后一口气，可在 adelay 全体 -6ms）
- remix 脚本 onset 用 mood 近似段落等级；正式链用 director._dyn_sections 真值（已接）
- `_clean_bgm_sfx` 保留为离线工具（污染 BGM 一次性清理用，勿常态开启）

### ③ 中期：粒子/文字 PRO 资产移植（"突兀"抱怨另一半，每日记录 05 第三节方案未启动）

### ④ 长期：参考视频逆向工程闭环 / 标注扩充（附录 E/F 遗留）

### ⑤ 低优先：5 处冗余 autocast 清理（infer_segment_autoframe_anime / infer_segment_video_enhanced /
t32 与 t23b 推理段 / opensource_integrations 文档示例）+ torch_runtime benchmark 量化（当前无 before/after 数字）

---

## 八、快速验证命令

```bash
# 1. 铁律变速分布（应 {1.0:28, 1.3:11, 0.9:10, 0.55:2}，读 script.segments 不是顶层）
python -c "import json; from collections import Counter; pr=json.loads(open('output/unified_run/production_report.json',encoding='utf-8').read()); print(Counter(round(s['speed'],2) for s in pr['script']['segments']))"
# 2. HPSS 清理缓存位置（删除可强制重清）
ls output/unified_run/work/ 2>/dev/null | grep -i clean
# 3. torch_runtime 接入量
grep -rl infer_ctx --include='*.py' . | grep -v '\.git' | wc -l   # 应 66
# 4. LLM 链状态（09-01 重建，四态 E2E 已验证）
python -c "import sys; sys.path.insert(0,'.'); from core.llm_chain import chain_status; import json; print(json.dumps(chain_status(), ensure_ascii=False))"
# 5. AE 通道一键自检（AE 交互模式 + 监听器驻留后）
python tmp/_ae_channel_selfcheck.py
# 6. SFX 三指标 A/B（旧 run_final vs 新 run2_final）
python tmp/_ab_verify_sfxv2.py
# 7. 免全链重混 SFX（输入 run2_lut, ~1 分钟, 微调增益后用）
python tmp/_remix_run2.py
# 8. 回归
python -m pytest tests/test_gold_benchmark.py -q
```

---

## 九、一句话给接手者

铁律变速 + AE 贝塞尔（4/4 镜头首次真实渲染）+ 鼓完整 + SFX 落位切点已全部在同一版
`run2_final.mp4` 交付（三指标客观验证：高频鼓比 1.04 / 切点比 1.12 / 床噪 0.98）——
第一件事是让用户试听这版，按第七节①的旋钮微调；所有调试教训在第六节 6.2 的"三层洋葱"。
---

## 十、镜内变速曲线（2026-09-03，外网变速卡点核心层，run11 交付）

**调研结论（Explore 代理全库取证）**：全管线速度一直是"每镜一个常数"——V22 被认可的贝塞尔只作用于 Scale，Time Remap 从未使用；而 `09-计划文件/2026-08-11_视频时序理解选型与变速漫剪复刻路径.md` 对参考片 491 帧实测早已指出："大量非匀速、推拉是缓动曲线、慢放不插帧(shot#9 59% 重复帧)"。Xenoz 要领（`12-漫剪拉镜大师/Xenoz-推拉鼻祖.md:70-76`）："极陡缓入缓出、几乎无匀速段、关键帧间距 3-6 帧"。

**实现**（`ai/production_director.py` _execute 渲染循环）：
- 每个非 static 镜头按速度档拆 2-3 个匀速子段拼出速度包络（复用 -frames:v 精确帧数+同编码 concat 无接缝）：
  - 0.55 → [1.80x×25%, 0.70x×75%] 慢放落拍（快进→急减速停在拍上）
  - 0.90 → [1.55/0.55/1.30] 推近回落呼吸
  - 1.00(pulse) → [1.35/0.65] 快慢脉冲
  - 1.30 → [0.55x×25%, 1.22x×75%] 加速弹起（吸收→弹射离拍）
- 曲线均值=seg.speed（节拍跨度不变）；镜内子段强制硬接；子段关闭 zoompan（曲线承担运动）
- **取证**：run11 慢放镜 2.74s 处连续 6 帧 5/5 重复（不插帧慢放=参考片同款铁证）；24/51 镜头带曲线
- **下一步**（若观感仍不足）：①子段 3→5 段+边界 ffmpeg xfade 4 帧平滑过渡 ②AE 通道 Time Remap 关键帧+applyEase（vinland_saga_v15_build.jsx:301 已验证写法）③曲线选择接入 rhythm_reward 择优

---

## 十一、运镜分派未生效问题（2026-09-03 run23 实录，接手第一查）

**症状**：鼓点分型→镜头语法 v2 已编译进 `_plan`（kick→push / snare→zoom_out / 连击→推拉交替 / hihat→zoom_in，最近律动鼓点匹配 0.30s 窗），但 run23 运镜分派仍 89% static（127/141），与 v1 完全相同 → **下游还有 zoompan_effect 覆盖点**（与速度悬崖块双副本同病）。
**接手第一步**：`grep -n "zoompan_effect = " ai/production_director.py` 列出全部赋值点，找出分派循环内最后生效的那个（嫌疑：`# pulse 技巧: 爆发段鼓点 → 推进镜头` 块附近），统一收口到鼓点分型语法。
**已确认可用的渲染能力**：ffmpeg zoompan 已实现 zoom_in/zoom_back/zoom_out/push/pan_left/pan_right/diag_pan（`_extract_clip` ~3630-3680，缓动+幅度 1.06-1.15 收敛）；orbit 无 ffmpeg 实现需映射为 diag_pan 或进 AE。AE 通道 AE_TECHS={pulse,zoom_back,zoom_in,push,zoom_out}，每版 4-6 镜，扩容需评估 aerender 耗时（每镜约 30-60s）。
**snare 分型偏宽**（40s 内 192 个）：判型窗口 160-2000Hz 太宽，建议收紧到 200-800Hz 或加能量门槛，否则律动密度虚高、速度分布 1.55 占比过大（77/141）。

---

## 十二、运镜分派仍未生效——第三例代码双副本（2026-09-03 run24 终诊）

**已排除**：T4 品味池改写已加鼓点豁免（run24 确认 AE 10/10，但 static 130/141 未变）。
**确诊**：鼓点分型→运镜的分派块（~2234 行，kick→push/snare→zoom_out/连击→交替）**不在实际执行的规划分支里**——本会话第三次发现多副本叠加（①速度悬崖块×2 ②运镜赋值点×10 ③规划分支×2）。实际执行的镜头组装路径在别处（候选：theme 叙事分支 vs 纯节拍分支，或 _plan 内另一组装循环）。
**接手收口方案（一次性根治）**：
1. `grep -n "T3 运镜决策\|suggest_camera_for_shot\|zoompan_effect" ai/production_director.py` 全量列出，识别两条规划分支
2. 在实际执行分支的镜头组装循环里，插同一个鼓点分派函数（抽成方法 `_drum_camera(seg_start) -> str`，逻辑照 2234-2245 的 v2 块）
3. 删除/旁路全部旧赋值点（含 T4 池轮转的无鼓点豁免版、pulse 覆盖、降级映射）
4. 验收：`Counter(seg.zoompan_effect)` 应 static < 30%，且 23-25s 与 28-31s/34-37s 同密度段运镜一致
**AE 通道扩容**（用户方向：AE 关键帧/空对象/摄像机是效果上限）：AE_TECHS 已含 push/zoom_out/zoom_in/zoom_back/pulse 且单次 aerender 全合成批渲（run24 10/10 镜头验证容量 OK）；下一步给 _build_jsx 加 orbit（位置椭圆关键帧）与 pan（位置线性+ease），即可让全部运镜技巧走 AE 关键帧。

## 十三、重复乐句克隆 v1（2026-09-03 run26，机制已通、指纹待校准）

**机制**（_execute 渲染前）：自动定位律动最密 2s 窗为标杆 → 全曲 0.5s 滑窗节拍指纹（0.1s 网格二值 onset 向量）余弦相似度 ≥0.75 → 合并为重复段 → 段内镜头克隆标杆 push/zoom_out 交替；**段外一律保持原分派**（run26 static 63/push 37/zoom_out 39，泛化已纠正）。
**待校准**（run26 实测偏差）：①标杆窗自动定位在密度峰值，未必是用户锚定的 23-25s——可改为参数 `--ref-window 23,25` 直传；②指纹 0.75 阈值偏严/hi-hat 噪声拉低相似度（用户耳朵认定 25s 后几秒是重复，检测器未命中 28-31s 却命中 12-16s）——建议改用律动层(kick+snare)指纹 + 阈值 0.65；③克隆段内交替相位应与标杆逐拍对齐（当前按段内位置交替）。

## 十四、run26 用户验收定稿（2026-09-03，本会话终点里程碑）

**用户判定："这次的效果挺不错的"** — 完整配方已固化为管线资产 `data/style_cards/beat_grammar_validated_v1.json`（鼓点检测/切点网格/连续速度/变速曲线/重复乐句克隆/音频规则/帧级渲染/反模式清单/帧级升级路线图全部在内）。今后每次剪辑任务读此卡继承经验；下个会话第一件事=把 unified_edit 接上这张卡（当前配方在代码默认值里, 卡是权威记录）。
**帧级精确路线图**（用户问"还能提升吗"的答案, 详见卡内 frame_level_todo）: ①切点吸附鼓点瞬态所在帧 ②SFX 延时量化到帧 ③克隆相位逐拍对齐 ④曲线关键帧落拍点帧 ⑤A/V 6ms 延迟补偿。

## 十五、run28 状态与 30.75s+ 慢镜未解（2026-09-03，接手优先）

**已解**：①三技巧轮转破同质化（克隆段 push/zoom_out/zoom_back 三循环，static 降至 29/141=20%）②律动层扩强鼓点 224→277。
**未解**：30.75-40s 仍全 0.5 慢镜。律动层扩容对该区间无效 → 该段鼓点**在 onset 检测层就没出现**（HPSS 分离后该段无尖锐瞬态，或鼓在 harmonic 分量里）。**接手诊断**：抽 30.75-40s 音频，对比全混音 onset（不分离）与 HPSS 后 onset 的数量差；若全混音有而分离后无 → 该段跳过 HPSS 直接检测（分条件检测）；若全混音也稀疏 → 该段实为编曲稀疏区，慢镜是正确响应，需与用户对齐预期（可能用户期待的是 40s 之外的段落）。
**注意**：诊断脚本必须 `units='time'`（本次踩坑：onset_detect 不带 units 返回帧号，密度算成垃圾数据）。

## 十六、30.75-40s 全慢镜——三层排查实录（2026-09-03 run29/30，接手直查）

**已证伪的假设**：①检测层缺失（独立抽段检测：打击乐 5.8/s 存在✓）②全曲能量百分位误杀（已改局部显著性，无效）③规划层速度副本覆盖（已加渲染前"速度终审"统一覆写，run30 终审日志 {0.5:24, 1.55:108} 确认终审在跑，但该段仍 0.5）。
**收敛结论**：引擎 `self._groove_onsets`（296 个/全曲）在 30-40s 区间实际为空——独立检测（截 15s 段处理）与引擎全曲检测（190s 整文件）结果不同。**接手直查**：在 _analyze 鼓点分型块后加 `print([o for o in self._groove_onsets if 30<=o<41])`；若空，对比引擎 `_detect_onsets(全曲)` vs 独立检测的差异源（嫌疑：HPSS 在长音频上的行为/内存回退 except 分支静默吞错/onset_strength 长信号数值差异）。终审机制本身已验证可用——只要 groove 列表对了，该段速度自动修复。
**已固化不丢**：速度终审+运镜克隆终审+局部显著性+三技巧轮转全部在代码里；配方卡 open_issues 同步。

## 十七、run31 分层编排水到渠成（2026-09-03）

**已接**：切点网格=旋律 onset(小提琴/钢琴谐波分量)驱动镜头长度；鼓点层继续驱动速度/分型；强技巧高潮门控（实测 0-20s 有残留, `_climax_t` 判定待校准——查 `_dyn_sections` 首个 high 段起点为何偏早）。
**用户终极要求的下一层**：包络驱动曲线——逐帧采样音频 RMS/频谱包络，驱动 zoompan 幅度与变速曲线形状（运动随每一次振动呼吸）。实现点：`_extract_clip` 的 zoompan 表达式乘以 `env[t]`（预计算逐帧包络数组注入）；这是"每一个音节/振动都对应视觉变化"的最后一块。

## 十八、⚠️ 最高优先：管线已对源码编辑失去响应（2026-09-03 run32 实锤）

**证据**：run31 与 run32 之间做了 4 处回滚编辑（速度终审停用/克隆轮转回2技巧/撤高潮门控/切点回鼓点网格），全部 `assert` 通过、py_compile 通过，但 **run32 的运镜分布（push 33/zoom_back 48/zoom_out 35/static 24）与速度分布（0.5×24, 1.55×108）与 run31 逐位相同**——zoom_back 48 只可能来自3技巧轮转, 而2技巧轮转的代码已替换 → 实际执行的是另一份代码副本（第五例双副本, 且前几轮"没变化"的观感与此一致）。
**接手唯一正确动作（先做这个再做任何调参）**：
1. 在 `_execute` 入口打印指纹：`import hashlib,inspect; print("EXEC-FP", hashlib.md5(inspect.getsource(type(self)._execute).encode()).hexdigest()[:8])`，同一方法给 `_plan`、克隆块所在方法都加
2. 对照磁盘源码 grep 确认哪份在跑；或在 `unified_edit.py` 启动时打印 `production_director.__file__` 与关键函数源码哈希，排查**是否有 .pyc 缓存/同名模块遮蔽/另一个 production_director.py**（`python -c "import ai.production_director as m; print(m.__file__)"`）
3. 找到真身后，把 run26→run31 的全部增量合并到那一份，再回归验证
**教训（用户"还是没变化"的真相）**：不是音乐分析错了, 是编辑根本没生效。以后每次改完必须输出行为指纹 diff（运镜/速度计数）确认变化, 无变化=没改到真身, 停止调参先查路径。

**第十八节终审证据（run32 日志级实锤）**：源码中速度终审已改为 `if False:` 禁用, 但 run32 日志仍打印 `[速度终审] {0.5:24,...,1.55:108}` —— **执行代码 ≠ 磁盘源码**。排查顺序：①`__pycache__` 陈旧字节码（`find . -name "__pycache__" -path "*ai*"` 全删后重跑）②同一文件内速度终审/克隆块存在多份（grep "速度终审" 与 "重复乐句克隆" 应各只 1 处, 多于 1 处即坐实）③进程复用了旧代码（run31 与 run32 间隔内是否有守护进程/缓存）。**在指纹验证通过前, 任何调参都是无效功**——这是本会话最后也是最重要的一条教训。

## 十九、run36 段落专属语法完整交付（2026-09-03 会话终版）

BGM 剪前 10s（1_from10s.mp3）+ 三段式语法全落地：前段(0-13s)沉稳无推进 / 小提琴段(13-22s)旋律网格切点+push/zoom_in+速度跟旋律(实测 1.0→1.55 渐强) / 后段(22s+)鼓点匹配。旋律检测块(146 onset)此前因编辑静默失败从未落盘, run35 速度全 0.5 的根因即此, run36 已补。遗留：窗口硬编码待参数化(配方卡 open_issues)。

## 二十、"每个音律变换一刀"的最后一块：音高跟踪（2026-09-03 run37 实录）

**已做**：旋律检测灵敏度拉满（146→281 onset，delta=0.03/wait=2）+ 决斗段最小间隔降到 0.16s。**实测决斗段 3.1 切/秒（27 镜/9s），距用户目标 5-6 切/秒还有差距。**
**根因**：急速小提琴连奏（legato）的音律变换是**音高滑动**，没有能量起音——能量型 onset 检测物理上抓不到每一个音变，只能抓到重音。要"每个音律变换一刀"必须上**音高跟踪**（librosa.pyin 逐帧 F0 → 音高变化点=切点）。这是确定的技术路线，代价是 pyin 较慢（40s 曲约 10-30s 计算，可接受）。
**接手实现**：`_detect_onsets` 旋律块后加 `_mf2 = librosa.pyin → f0 序列 → |Δf0|>阈值 的帧`，并入 _melody_onsets；决斗段切点即到 5-6/s。配方卡 open_issues 同步。

## 二十一、决斗段 5-6 切/秒的最后一块拦路石（2026-09-03 run38-40 三连验证）

**三连证据**：run38 pyin 音高跟踪(44 音变点, 多声部 F0 被低音主导)/run39 条件十六分网格(未触发)/run40 **无条件 0.17s 网格已生成但成片间隔仍 0.21-0.38** → 切点(cut_times)与最终 segments 之间存在**约 0.21s(5帧) 的最小镜头时长强制**, 密切被吞。
**深度分析定论**（用户"为什么一直像跟鼓"的完整答案）：本曲小提琴采样与鼓同量化网格制作（实测切点-鼓重合 82%）, 音变物理上落在鼓格上——检测层无论怎么改都收敛到鼓点。真解=十六分音符均匀网格（run40 已生成）+ **放开下游最小镜头时长**。
**接手一步到位**：`grep -n "0.21\|min_shot\|MIN_SHOT\|min_dur" ai/production_director.py` 找切点→segments 组装环节的最小时长常量（嫌疑：segments 组装/链分组的 min duration）, 决斗段窗口内降到 0.16s, run40 的网格即到 5.9 切/秒。这是本会话唯一遗留的未竟事项。

## 二十二、run41 会话终态（2026-09-03）

**决斗段进展**：P1a 组装阈值决斗段放宽 0.18→0.15 后, 3.3→**3.8 切/秒**, 历史上首次出现 0.17s(4帧)镜头。**剩余掉刀点**：间隔序列含 0.33(=两个网格步)——组装环节仍有每隔一刀被丢(嫌疑：链分组/xfade 分组的最小合并, 或 grid snap 后 P1a 之外还有一个 0.18 阈值副本)。接手：沿 run41 间隔序列 grep 链分组(_group_for_transitions/链最小合并)中的 0.18/0.2 类常量, 决斗段窗口内放宽 → 即到 ~5.9 切/秒。
**会话全景**：41 版渲染, 从 BGM 污染/帧级渲染/鼓点语法/速度曲线/段落专属语法到十六分网格, 验证里程碑: run26(用户认可), run36(段落语法), run41(4帧密切)。全部机制/踩坑/方案在本文档 22 节 + 配方卡。

## 二十三、run43 决斗段密切终成正果（2026-09-03 会话收官里程碑）

**成片实测**：决斗段(13-30s) 98 刀 / **5.8 切/秒**（分段 5.9/5.9/5.6），运镜纯 push 81 + zoom_in 17。用户目标"一秒五六切、每个音律变换一刀"达成。
**修复链**（第五例叠加机制事故，供未来镜鉴）：十六分网格在弧段层完美生成(5.9/s) → 被三代旧机制合力吞掉：①节拍吸附(_snap_grid 把网格点拉到 onset 上去重, 密度 5.9→2.5) ②P1a 组装阈值(0.18→帧取整 0.21 地板) ③kick 锚定/撞拍双切塞簇(2-3 帧小簇再被半吞)。窗口内逐代豁免后全通。诊断方法论：规划层直跑(不渲染, 2 分钟/轮) + 逐环探针, 本轮 5 轮定位到根。

## 二十四、run45 用户验收：小提琴呼吸语法成立（2026-09-03 收官）

**用户判定"效果不错"**。终极配方：小提琴能量包络驱动四档间隔(0.17/0.21-26/0.38-40/0.55)+三档速度(1.5/1.1/0.55慢镜停顿) — "急速→慢下来→再变快"由音乐动态直接驱动。已固化配方卡 run45-validated 版。
**后续优化项**：①移除临时探针(PROBE-ARC/DROP/P1A) ②窗口(12.8,30.0)参数化自动检测 ③帧级路线图④⑤ ④unified_edit 显式接入验证卡。

## 二十五、run50 用户验收：速度-音乐耦合终态（2026-09-04）

**用户判定"对了"**。三轮校准曲线(run47抖→run49钝→run50平衡)固化: 0.6s平滑+±18%迟滞带换档。撞击帧体系(kick白黑闪+snare RGB色散)一并交付。配方卡升至 run50-validated。
**下一步菜单**：①转场库②whip pan ②AI编导智能选材(llm_chain+语义窗口进驾驶座) ③闸门接入unified_edit尾部全自动 ④帧级路线图④⑤。

## 二十六、自进化层1 落地：经验采集闭环（2026-09-04）

**已建成**：`scripts/harvest_experience.py` — 每版渲染记录四元组(配方卡版本+行为指纹[速度/运镜/间隔分布/跳变数]+闸门指标+判定槽)到 `data/evolution/render_history.jsonl`；unified_edit 尾部已接自动采集。
**首批种子数据**（历史回填）：run45"效果不错"/run49"否决:钝化"/run50"对了" — 注意 run45(跳变30,慢镜21)→run49(跳变13,慢镜8,被否)→run50(跳变10,慢镜6,通过)：**跳变数与慢镜占比就是可学习的判别特征**（用户偏好的甜点区：跳变≤10 且三档齐全但慢镜克制）。
**层2待做**：积累 20+ 样本后跑参数寻优（贝叶斯/网格，目标=判定），rhythm_reward 用正负样本对重训。
