# 交接文档 2026-09-05（会话 2：从 v6 交付 → 源重复/切点/扩库/速度曲线）

> 给接手程序：**本文件是当前会话的权威进度同步**，读它就够续做。
> 前一日文档（v2–v6 演进史）见 `docs/handoff-2026-09-04-v6-full-sync.md`，只作历史参考。

---

## 0. 一句话状态

> **v10 修复 (09-05 15:00) 慢镜锚点重锚 — 已交付 `run53_final_curve_v4.mp4` (闸门 7/7)**:
> 接手 v9 遗留反馈"(17秒后)有几处慢镜头没对上音乐"。诊断链: 用谱通量(无平滑滞后)检真实 kick
> (`scripts/gen_true_onsets.py` → `tmp/true_onsets.json`, 110个/3.7s) 逐镜复测 → 慢镜切点其实大多贴 kick
> (±2帧), 真正错位的是**冻结锚点**4 处: 24.54 整段悬在两 kick 间(引擎网格源自 0.6s 平滑包络, 切点早
> 0.32s)、26.29/19.42 的 kick 在镜头中段(+1.8/+3.2帧)、27.25 的 kick 恰在出点后。v2 时代每拍闪帧
> 掩盖了这些, v8 deflash 抽走闪帧后暴露。修法(`build_master_polish.py`): `_twx_anchor` 三模式把冻结点
> 锚到镜头内/近旁最强真实 onset — cut=贴切点(现状,大多数)/mid=切点恒速续放→冻结在kick→放出/
> end=冲入→末尾冻结; 平均速度恒=spd, 只动 t0≥15 投诉区, 4 镜重锚其余逐键不动。
> 验证: ①AEP 关键帧 dump 与设计一致(`tmp/dump_twx_keys.py`) ②v3→v4 帧差仅在 4 窗(0.22-4.35,
> 其余 0.00-0.50 噪声) ③目检帧条无 Twixtor 撕裂, 26.29 可见"行走→26.366停→切出"。
> **坑: render_gate.py 旧版永远测 `{tag}_final.mp4`(底片), v2/v3 的"闸门7/7"实际测的是底片不是曲线版;
> 已加 `--final` 参数, 本次真正测了 v4。**

> **v9 同步 (09-05 13:45) ⚠️ 有一个用户反馈零处理**: v3 交付（13:26）后用户连发
> **"有几处慢镜头没对上音乐"（13:28，13:39/13:40 重发）→ "17秒后有几处慢镜头没对上音乐"（13:43）**，
> 但会话 `sess_cd63819c` 最后 5 次模型请求**全部失败**（GLM-5.3-Flash 网络层连续失败可重试；
> 13:43 切 deepseek-v4-flash 又被 400 拒绝），turn 52/53 五连败、四轮 rewind 重发，**没做任何事**。
> 最新成片仍是 `run53_final_curve_v3.mp4`（13:26），没有 v4。**接手第一件事 = 处理这条反馈**（见 §7.0）。
>
> 侧会话 `sess_5c3c4114`（13:26–13:42）项目复盘定调：**项目改名 MasterCut（中文口径：母版工坊）**，
> 用户已确认"需要"。名义改名、磁盘目录不动（数百处硬编码路径）。品牌口径已写入 4 个文档（未提交）：
> 新建根 `README.md`、`🏠-AE知识中心.md`、`01-项目概览/📋-项目概览-MOC.md`、`TASK_STATUS.md`。
> 复盘三个护栏（写规则时照办）：①"完美"要量化终点线（beat_hit_rate 追参照集前三分位、切点踩拍≥85%，
> 到线即验收）；②边打磨边沉淀（每轮验收过一条规则当场固化一条，别攒）；③单部作品规则入库带适用域标签
> （时长/BGM 结构/风格），防 run53 的 30s 燃向规则过拟合到别的片上。

> **v8 更新 (09-05 13:30) 闪帧减密**: 用户验收 v7 反馈"15秒后连续闪动, 没跟音乐节奏" →
> 测量: 底片自身 7.5次/s 帧突变 (引擎冲击帧文法每拍都闪=主因, 精修 burst 只加 2.2/s)。
> 引擎有未播种随机 → 重跑会换剪辑, 不可取 → 外科手术: `scripts/deflash_lut.py` 在底片上
> 检测闪动事件 (luma突跳+RGB条纹, 89个/3.0/s), 只保留音乐重音对齐的 15 个 (间距≥1.6s),
> 其余 74 个邻帧插值抹除 → 白黑闪 148→2 帧; burst 协调减密 (读 kept_events 避叠加±0.35s,
> drop cap 12→5 / build 6→3, 间距1.8/2.2s)。
> 交付 `run53_final_curve_v3.mp4` (闸门7/7)。坑: 缩略图插值放大输出毁分辨率(检测/抹除要分层);
> Windows 管道写大流 Errno22+stderr 不读死锁 → 临时 raw 文件中转。
> 若未来重跑引擎, 根治 = ai/production_director.py L3802-3819 冲击帧文法加间距门控+重音条件。

> **v7 更新 (09-05 12:20)**: 用户验收曲线版反馈"卡点对不上了，效果不错" → 已修复并交付
> `run53_final_curve_v2.mp4` (闸门 7/7)。根因×2: ①曲线下预卷段速度≠spd, 积分模型起点漂移
> sin×(v0/spd-1)=0.62s → 预卷写两个恒速 spd 关键帧钉相位 (对积分/逐点模型都成立);
> ②v1 把最快运动压在切点上 (音乐坠落点画面飞驰) → 曲线反转为冻结在切点→向下一拍渐加速
> (18.5%→51.3%→107.8%)。相位经 nofx 探针扫相验证 (峰值误差<半帧)。
> 修法在 `scripts/build_master_polish.py` `_twx_curve` (v7 注释)。

run53（30s 燃向，BGM=1_from10s.mp3）已完成：
① 源素材全局去重 ② 切点帧重复修复 ③ 评分参照工具链 ④ 素材库扩充（7→13 源）
⑤ Twixtor 连续速度曲线。闸门 **7/7 ACCEPT**。当前待你（接手程序）做：验收成片 + 按 §7 继续。
**交付件：`output/unified_run53/run53_final_curve.mp4`（最新，含速度曲线）；`run53_final.mp4`（13 源版，无曲线）。**

---

## 1. 本会话任务时间线与完成度

| # | 任务 | 状态 | 关键结果 |
|---|------|------|----------|
| **0** | **"17秒后慢镜没对上音乐"反馈** | ✅ **已修复交付 v4** | 4 镜重锚(19.42/24.54/26.29/27.25), 闸门 7/7, 待用户验收 |
| 8 | 源素材全局重复（洛天依） | ✅ 完成 | 复用簇 8→0，单源占比 30%→16.4% |
| 15 | 切点可见性短板（软切点） | ✅ 完成 | 根因=帧重复，fps 滤镜修复，用户确认"干脆了" |
| 13 | 同口径参照评分脚本 | ✅ 完成 | score_reference_gap.py |
| 12 | 素材库扩充 + 建档 | ✅ 完成 | 7→13 源、5→7 番 |
| 10 | 速度曲线 Twixtor 化 | 🔄 第一版已渲染 | 慢镜 匀速→连续减速曲线，待用户验收 |
| 14 | 下载顶尖漫剪参照集 | 🔄 12/20 | 下载通道已通，瓶颈在链接发现 |
| 9 | 等用户验收成片 | ⏳ | 见 §7 |
| 11 | 语义选效果 | ⏳ 未开始 | battle/closeup 接入效果映射 |

**本会话 5 个提交（git log）：**
```
c5a72d5 feat(tools): 同口径参照评分脚本 + 顶尖漫剪参照集清单
28503e8 fix(ae): 切点可见性修复 — 相邻同IP去重 + 源60/30fps用fps滤镜+禁B帧
d645216 fix(ae): 经验采集 subprocess 缺导入 + 交接文档去重收尾
440cda8 feat(ae): 源素材全局去重+单文件占比封顶 — 洛天依重复修复
1c82a80 docs(handoff): 全天完整同步 v6 终态（前一日）
```

---

## 2. 已修复的问题（症状 → 根因 → 修复 → 验证）

### 2.1 源素材全局重复（#8，用户反馈"洛天依重复出现"）
- **症状**：116 镜中同一源片段多次出现（最狠：独自升级5.mp4 @232s 同一画面出现 4 次）。
- **根因**：引擎 only 防"相邻"同源，不防"全局"同片段复用；且单文件占比失控（独自升级5 曾 30%）。
- **修复**（commit 440cda8）：`ai/production_director.py` 新增 `_enforce_global_source_uniqueness`，
  `_plan` 末尾调用：① 全局同片段去重（同 file+source_start≤0.5s 只留一次，冲突换起点/换源）；
  ② 单文件占比封顶 25%（超限换到最少使用的源）。验收工具 `scripts/scan_source_dupes.py`。
- **验证**：`scan_source_dupes.py` → clusters=0，max_share 16.4%（扩库后）。

### 2.2 切点"软/隐形"（#15，用户说"切了但没切开、难受"）
- **症状**：约 29% 切点处前后两帧几乎一样（部分逐像素 100% 相同），观众看不出切了。
- **排查链（重点，别重蹈）**：先后排除"同源连续/黑帧/低分辨率测量假象/同IP相邻/素材静帧"5 个误解，
  最后用**帧扫描 + 源素材对照**定位到真因——**源视频是 60fps/30fps，管线用 `-r 24` 硬转帧率+setpts，
  拼接边界复制了帧**。
- **修复**（commit 28503e8）：`_extract_clip` 用 `fps=24` 滤镜替代 `-r 24`（确定性重采样），
  并 `-bf 0` 禁 B 帧保 concat 边界干净。另加了 `_enforce_adjacent_diversity`（相邻镜头同 IP 去重，
  猫1/猫2、独自升级2/5 这类同番多文件，18 处相邻同 IP 归零）。
- **验证**：t=3.33 那个"100% 重复"切点变成 MAD=100 清晰突变；用户确认"干脆了"；闸门 7/7。

### 2.3 经验采集静默失败
- **症状**：`unified_edit.py` 自进化层1 harvest 步报 `name 'subprocess' is not defined`，经验没落库。
- **修复**（commit d645216）：`subprocess.run` → `_sp.run`（模块里只有 `import subprocess as _sp`）。

---

## 3. 交付的新能力 / 工具

| 文件 | 用途 |
|---|---|
| `scripts/scan_source_dupes.py` | 源片段复用验收：clusters=0 且 max_share≤25% |
| `scripts/score_reference_gap.py` | 参照集 vs 本片同口径评分（信号6项+语义7维→差值表+短板排行）。注意：hf_energy 已按时长归一 |
| `scripts/scan_material_library.py` | 扫素材库建档 → `data/material_manifest.json`（52 源/10 番，自动排除教程/成品/竖屏/残片） |
| `data/reference_top/` | 12 条顶尖漫剪参照 + README 清单（mp4 走 gitignore 不入库） |

---

## 4. 素材库扩充（#12）关键结论
- 本机 `D:\AE-Work\resources\video` 与 `D:\BaiduNetdiskDownload\AE新手10套` **是两份独立拷贝**（非链接，内容重复）。
- 共 52 个可用源 / 10 番；引擎此前只用了 7 源 / 5 番。
- 已把 `DEFAULT_SOURCES`（`scripts/unified_edit.py`）从 7 源扩到 **13 源 / 7 番**：
  新增 蓝色监狱（nagi2/Nagi Seishiro）、辉夜（辉夜1）、美人鱼补（alya-twix/alya-twixtor04）、五条悟补（第二季2）。
- 排除项：李诗雅竖屏（16:9 用不了）、8.15 与 do-you-mean（内容不明，用户也不知）、9.06s 通用残片、720p。
- 效果：独自升级5 29→19 镜，max_share 21.6%→16.4%，画面多样性显著提升（用户确认"丰富了很多"）。

---

## 5. 速度曲线 Twixtor 化（#10）实现细节
- **改动**：`scripts/build_master_polish.py`
  - 新增 `TWX_SPEED_PROFILE = [(0.0,1.6),(0.55,0.45),(1.0,0.22)]`（时长占比, 相对速度）= 快进→急减速→冻结在拍点。
  - 新增 `_twx_curve(t0,t1,spd)`：梯形积分归一（k=1/∫），产出关键帧 `[[comp_time, speed%],...]`。
  - JSX 里 TWX 分支：`Twixtor 45-0005` 从单个 `setValue(spd*100)` 改成 `setValueAtTime` 逐关键帧。
- **关键帧实测值**（spd=0.55）：`[0s→123.16%, 0.55·dur→34.64%, dur→16.93%]`，平均速度精确=55%，
  故 §4.5 的 `startTime = t0 - sin/spd` 时间模型与落拍点**不受影响**。
- **产物**：`run53_final_curve.mp4`（已渲染，95 层，Twixtor 无报错）。**待用户验收**：
  慢镜是否"冲入→急停"更有冲击感；若 17% 冻结太狠，放宽 `TWX_SPEED_PROFILE` 尾段（如第 3 项 0.22→0.35）。

---

## 6. 未提交/遗留（接手程序要注意）

### 未提交（git status，09-05 13:45 实测）
```
 M 01-项目概览/📋-项目概览-MOC.md   （MasterCut 品牌口径 + 主线改为母版精修线）
 M 🏠-AE知识中心.md                 （MasterCut · 母版工坊 定位重写）
 M TASK_STATUS.md                   （标题 MasterCut + 视频主线/工程平台分账说明）
?? README.md                        （复盘会话 13:45 新建根 README，MasterCut 定位）
 M data/reference_top/README.md     （参照集清单 6→12 条）
 M scripts/unified_edit.py          （DEFAULT_SOURCES 13 源）
?? data/material_manifest.json     （素材扫描输出）
?? scripts/scan_material_library.py（素材扫描脚本）
```
→ 闪帧减密相关改动已随 363a921 提交（13:27），本节旧清单作废。
→ 建议接手后拆三个提交：① MasterCut 品牌（4 个 MOC/README 文档）；② 速度曲线若验收过再提 build_master_polish；
③ 素材库扩充（unified_edit 源表+扫描脚本+manifest）。

### 已知遗留问题
1. **评分步骤 CUDA OOM**：unified_edit 阶段⑤「成片评分」加载 CLIP 时 8GB 显存不足
  （Qwen3-VL/VideoMAE 还驻留显存），报 `torch.AcceleratorError: out of memory`。
  **非阻塞**（渲染/成片已完成，只缺 final 评分与经验采集那一步）。根治：评分步用完模型后卸载
  （`torch.cuda.empty_cache()` + del model）。
2. **改名"文件被占用"**：ffmpeg 混流输出与输入同名会拒绝（已用临时名+mv 规避）；
   mv 到 `run53_final.mp4` 时若你的播放器还开着会报 Device busy。做法：先关播放器窗口，或直接看
   `run53_final_curve.mp4`。
3. **发布前提叫**：重跑 aerender 必须用**绝对路径**（相对路径会被解析到 AE 安装目录），见 §5.7 前版文档。

---

## 7. 下一步任务（接手程序从这里开始，按优先级）

0. ~~处理"17秒后慢镜没对上音乐"~~ → **已完成 (v10, 09-05 15:00)**: `run53_final_curve_v4.mp4` 已交付,
   闸门 7/7(--final 实测 v4 本体)。**待用户验收**: 重点听 17s 后慢镜段是否跟上了 kick; 若 24.54 的
   "冲入急停"感觉太冲, 可把 end 模式起速 1.05 降档(改 `_twx_curve` end 分支)。
1. **#9/#10 验收速度曲线**：打开 `run53_final_curve.mp4`。用户定调后再定：
   - 曲线太狠→改 `build_master_polish.py` 的 `TWX_SPEED_PROFILE` 尾段 0.22→0.30~0.35；
   - 满意→把曲线**推广到全部变速镜头**（现在只 13 个慢镜）；重渲命令见下。
2. **#14 参照集补到 15+**：B站 cookie 已通（`D:/AE-Work/cookies/bilibili_cookies.txt`，09-05 刷新）。
   链路：`yt-dlp --cookies <cookie> -f "bv*[height<=1080]+ba/b..." -o "data/reference_top/%(title).60s [%(id)s].%(ext)s" <BV链接>`。
   瓶颈是**链接发现**（bilisearch 412、WebSearch 零星），最快=让用户贴 3-5 条 BV 直链。
3. **#11 语义选效果**：把 `_get_semantic_windows`（Qwen3-VL 场景标签）接进 `build_master_polish.py`
   的效果映射：battle/fighting→冲击层、closeup→推镜+glint，替代现在的"速度/能量"单一维度选效果。
4. **评分 OOM 修复**：`core/cnn_scorer.py` 或 unified_edit 阶段⑤前 `import torch; torch.cuda.empty_cache()`，
   打分完卸载 CLIP，让最后评分+harvest 恢复落库。
5. **素材库再扩**：8.15 / do-you-mean 两个未确认内容的文件夹，等用户确认是什么再决定是否入源池。

### 重跑关键命令（完整闭环，实测校正过）
```bash
# 全链路重跑（改动引擎/DEFAULT_SOURCES 后）
python scripts/unified_edit.py --bgm "D:\AE-Work\音频素材库\BGM\1_from10s.mp3" --duration 30 --tag run53
# 验收：复用簇应为 0
python -X utf8 scripts/scan_source_dupes.py output/unified_run53/production_report.json
# AE 逐镜重渲（只改 build_master_polish.py 就只需这三步）
python scripts/build_master_polish.py output/unified_run53 run53
"C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/aerender.exe" \
  -project "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output\unified_run53\polish\master.aep" \
  -comp MASTER -output "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output\unified_run53\polish\master.mp4"
ffmpeg -y -i output/unified_run53/polish/master.mp4 -i output/unified_run53/run53_final.mp4 \
  -map 0:v -map 1:a -c copy output/unified_run53/run53_final_new.mp4   # 先写新名，再手动 mv
python -X utf8 scripts/render_gate.py output/unified_run53 run53 --bgm "D:/AE-Work/音频素材库/BGM/1_from10s.mp3"
# 参照评分
python -X utf8 scripts/score_reference_gap.py --mine output/unified_run53/run53_final.mp4 --refs data/reference_top/*.mp4
# v10: 真实 onset 表 (换 BGM 才需重跑; build_master_polish 的 TWX 锚点依赖它)
python -X utf8 scripts/gen_true_onsets.py "D:/AE-Work/音频素材库/BGM/1_from10s.mp3"
# 闸门 (v10 起 --final 指定被测交付件, 否则测的是底片)
python -X utf8 scripts/render_gate.py output/unified_run53 run53 --bgm "D:/AE-Work/音频素材库/BGM/1_from10s.mp3" \
  --final output/unified_run53/run53_final_curve_v4.mp4
```

---

## 8. 任务追踪器快照（09-05 15:00 同步）

已完成：#8 #12 #13 #15（端到端）、#10 闪帧减密（v8）、**#0 "17秒后慢镜没对上音乐"（v10, 4 镜重锚）**。
进行中：#10（待用户验收 v4 /推广）、#14（12/20）。待办：#9（待验收）、#11（语义选效果）。
品牌侧：MasterCut 改名已定调、文档已改未提交（§6）。