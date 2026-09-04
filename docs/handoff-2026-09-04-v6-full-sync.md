# 交接文档 2026-09-04 全天完整同步版 (v6 Twixtor 完成态)

> 给接手程序: 本文件是**当前会话唯一权威进度同步**。先读本文件, 再按"下一步"
> 章节工作。相关逐日手记: docs/handoff-2026-09-04-ae-polish-selfheal.md (AE细节),
> docs/handoff-2026-09-02-sololeveling-beatsync.md (剪辑引擎历史)。

---

## 0. 一句话状态

run53 (30s 燃向, BGM=1_from10s.mp3) 已完成**第 6 版 AE 精修**并交付给用户预览:
`output/unified_run53/run53_final.mp4` — 逐镜头分段 + 按镜头上插件 + 拍点包络 +
光流感知选效果 + 13 个 Twixtor 光流慢镜, 验收闸门 7/7 全过。
用户反馈中**未决问题: 有镜头重复使用了同一源片段(洛天依形象重复出现)**。

---

## 1. 今日会话时间线 (任务与决策)

| # | 任务 | 结果/决策 |
|---|------|----------|
| 1 | 用户要求直接操作 AE (之前 AE 崩溃) | 发现**自动监听器随 AE 启动**, 无需 GUI 加载 jsx → 桥探活成功 |
| 2 | polish_pass 全片精修 Glow+Grain | 失败 → 诊断出 **aerender 5 坑** (见 §4), 修完成功 |
| 3 | **用户定调**: "发光效果插件不应直接作用视频=调色, 调色归达芬奇" | 废弃全片 adjustment 方案 → 转向**逐镜头分段 + 按镜头设计上插件** |
| 4 | 扫描插件库 | AE 枚举 **2413 特效** → tmp/ae_effects_all.txt |
| 5 | 参数勘探+校准 | 宫格渲染量化 → 剂量 dB 标尺 (见 §5.2) |
| 6 | 建 MASTER 总合成 v2 | BASE 底层 + 55 镜头层; **黑帧 bug** → v2.1 BASE 修复 |
| 7 | 用户: 13s前没效果 + 效果重复疲劳 | v3.1: 段落内相对能量 + 效果轮换禁连续 + 呼吸留白 |
| 8 | 用户: 看不出明显变化 | v4.3 剂量闭环: 基准×2-3 + 逐镜 PSNR 审计 + overrides 重渲 (可见率 62%→86%) |
| 9 | 外网顶尖 AMV 差距分析 | 交付5差距清单 → 用户选 1+3+4 → v4 拍点包络+连续密度+冲击层 |
| 10 | "继续" (第二波) | v5 光流感知选效果 (方向条纹+幅度耦合) |
| 11 | "继续" (最后一块) | v6 Twixtor 驯化: 13 慢镜光流重渲 (攻克3大坑) |
| 12 | 用户: "洛天依镜头重复" | **未解决**, 已诊断 (见 §3), 列入下一步 #1 |

---

## 2. 当前会话产物 (文件位置)

```
output/unified_run53/
  run53_final.mp4            ← 当前交付版 = v6 镜头级精修 (AE MASTER 103层 + SFX音轨)
  run53_final_v4.mp4         ← 存档: 你说"看不出变化"的那版 (平涂, 剂量低)
  run53_final_v43.mp4        ← 存档: 剂量闭环版
  run53_final_v5flow.mp4     ← 存档: 光流感知版
  run53_lut.mp4              ← 精修输入源 (已烘: 剪辑/变速/闪帧/转场/LUT调色/SFX音轨)
  polish/master.aep          ← 当前 MASTER 工程 (BASE+76效果层+13冲击层+13 TWX层)
  polish/master.mp4          ← 无音轨精修视频 (音轨复用 run53_final.mp4 的)
  polish/twx_src/*.mp4       ← Twixtor 源预裁件 (00-12)
  production_report.json     ← 引擎产出 (116 镜头剧本)
  unified_report.json        ← 本次渲染报告
scripts/build_master_polish.py   ← ★核心构建器 (v6 版, 映射规则+JSX+桥执行+源预裁一体)
ai/ae_render_channel.py          ← AE 桥通道 (polish_pass 已修 5 坑)
tmp/music_envelope.json          ← BGM 谐波RMS包络+强鼓点 (61个)
tmp/shot_motion.json             ← 116镜光流数据 (幅度+主方向)
tmp/master_plan.json             ← 当前效果计划 (shots+bursts+twx)
tmp/dose_overrides.json          ← 剂量闭环覆盖表
scripts/render_gate.py           ← 验收闸门 7 项
scripts/harvest_experience.py    ← 经验收割 (data/evolution/render_history.jsonl)
```

渲染链路: `run53_lut.mp4` (unified_edit 产出, 含音轨) → build_master_polish.py
建 MASTER → aerender 渲 master.mp4 → ffmpeg 混流 (master 视频 + final 音轨) →
render_gate 验收 → harvest 收割。

---

## 3. 未决问题: 镜头源素材重复 (用户最新反馈, 下一步 #1)

**症状**: 用户指出多个镜头重复出现同一角色/画面 (洛天依)。
**诊断 (已做)**: 116 镜中用到的源片段 (文件+source_start) 109 个, 其中 **6 个片段被复用,
13 个镜头受影响**:
- 独自升级5.mp4 @2.0s ×3 次 (落在 0.88s / 25.08s / 29.04s — 隔 24s 重复最明显)
- 其余 5 片段 ×2 次 (4.46/23.5, 5.17/21.88, 6.58/20.0, 7.46/23.04, 1.92/21.42)
- 源文件分布: 独自升级5.mp4×35, 猫2×19, 猫1×18, 初音×18, alya-05×10, 五条悟×8, 独自升级2×8
**根因**: 素材库仅 7 个源文件要填 116 镜; 引擎 source alternation 只防**相邻**镜头同源,
不防**全局**同片段复用。
**技术方案 (供接手程序)**:
1. 引擎源选择加"全局源片段去重"约束: 同一 (file, source_start±0.2s) 全片只许 1 次;
   冲突时按 AI 语义相似度 (battle/fighting/closeup 分类) 换语义相近的其他源片段
   (引擎已有 _get_semantic_windows 可复用)。
2. 若素材池不够, 扩库 (用户机器有大量素材: D:\AE-Work\resources\video, D:\BaiduNetdiskDownload\AE新手10套\)。
3. 快速缓解: 重复镜头可替换为同文件异起点 (偏移 >2s 画面通常已不同)。

---

## 4. 今日发现并解决的问题 (坑目录)

### 4.1 AE 桥自愈 (无需 GUI)
- 标准重启后**自动监听器随 AE 启动** (ae_auto_listener.log 出现 "Auto Listener started")。
- 探活: `AERenderChannel(out_dir=...)._bridge_run_jsx(timeout=60, command='executeAtomScript', args={'script':'app.version;','scriptContent':'app.version;'})` → status success。
- 监听器**不回传脚本返回值** (只 executed:true) → 读值让 JSX 写探针文件再 python 读。
- 崩溃恢复: taskkill AfterFX → 清 .ae-mcp-bridge/ae_command.json+ae_result.json → 启动 → 等加载 → 探活。

### 4.2 polish_pass 五坑 (已修进 ai/ae_render_channel.py)
1. **相对路径**: aerender 把相对路径解析到自身安装目录 → `.resolve()` 绝对路径。
2. **假成功**: JSX 只建合成没进渲染队列, aerender 空转 RC=0 → 传 `-comp POLISH` 按合成名渲。
3. **模板不存在**: 新工程无 "Best Settings/Lossless" 模板 → 去掉; 默认输出模块即 H.264 mp4。
4. **addSolid 时长单位是秒** (第6参), 传 1.0 只盖第 1 秒 → 传合成时长。
5. **中文版 AE 参数名**: `property("Glow Intensity")` 返 null → 必须 matchName
   (Glo2-0003 半径 / Glo2-0004 强度 / Noise-0001 数量)。`ADBE Add Grain` 此版不可脚本添加 → ADBE Noise。
另: aerender 中文输出 GBK, `text=True` 默认 utf-8 崩 reader 线程 → `encoding='utf-8', errors='replace'`。

### 4.3 AE 崩溃 (批量插件)
- **批量添加 15 个 GPU 插件 (Twixtor/Sapphire/BCC/Universe/HitFilm) 崩 AE** → 每批 ≤3 勘探。
- **Twixtor 单独添加不崩** (崩元凶是 Sapphire/BCC 系)。
- 崩溃症状: 进程消失 + 监听器日志停更。恢复 = 标准重启 (4.1)。

### 4.4 效果不可见 / 剂量问题 (用户: 看不出变化)
- 根因1: 单帧校准剂量在真实画面上浮动巨大 (40-55dB 不可见)。
- 根因2: 包络衰减砍总能量。
- 根因3: burst 落在烘好的黑白闪帧上 (纯色帧无效果)。
- 修复: 基准×2-3 + **闭环逐镜 PSNR 审计** (渲→测→overrides→重渲) + burst 后移 0.13s。
- **CC FMB 只在运动画面显效** (静止帧 47dB 上限, relVel 不可放大) → 只留运动段。
- 可见率 62% → 86% (10-40dB 带, 均值 25.8dB)。

### 4.5 Twixtor 三大坑 (今日最复杂)
1. **时间模型**: 读源时刻 = (t − startTime) × speed → `startTime = t0 − sin/spd` (含 t0 项)。
   用**三公式对照实验** (3 个独立合成各渲 1 帧对源帧) 确证; 试点 inPoint=0 掩盖了 t0 项。
2. **AE 零长层钳位**: startTime 巨负偏移把图层有效窗推出源时长 → AE 把 in/out 钳成
   **零长度层** (症状: in==out==负数, 该段漏底变黑)。→ ffmpeg 预裁源片 [sin−lead, ...],
   lead 自适应 (0.5/0.2/0.05, 源尾不足自动缩), sin 改片内偏移。
3. **验证方法论**: bloom 高剂量帧 vs 源帧 PSNR 崩到 6-15dB 但**内容正确** →
   视觉模型确认同场景 + **去效果渲单帧法** (22.1dB 基线) 才是真验证。
   教训: 全场像素对比在强效果在场时不可靠, 会连环误判 (曾把正确渲染判成 0/13 全错)。

### 4.6 工程架构 bug
- **黑帧**: 只给有效果镜头建图层 → 其余镜头黑 (症状: "原样"时码 PSNR 3-5dB) →
  v2.1 加 BASE 全片底层 (效果层叠加其上)。
- **脚本静默失败** (历史教训): heredoc 反斜杠转义咬人 → 写 .py 文件再执行;
  多步骤命令 str.replace 静默未命中 → 改完立即 grep 验证。

---

## 5. 今日经验与知识 (接手程序必读)

### 5.1 用户审美偏好 (强约束)
- **调色归达芬奇**: AE 层不做全片色彩调整; AE 只做逐镜头运动/冲击/质感效果。
- **克制优先**: 不要每个镜头都上效果; 效果重复=视觉疲劳 (用户原话)。
- **效果要跟拍点呼吸** (砸入→衰减), 不是平涂整镜头。
- 变速停顿(慢镜)是亮点区; 快切要配节奏; 铺垫段克制、决斗段放。
- 用户对"内容正确但像素对比低"无感 — 关心观感, 不关心指标。

### 5.2 插件库 (本机 2413 特效已枚举 → tmp/ae_effects_all.txt)
已驯化可用 (matchName + 剂量语义):
| 插件 | matchName | 设参 | 剂量参考 |
|------|-----------|------|----------|
| CC Force Motion Blur | CC Force Motion Blur | -0001=amount, -0003=角度 | 运动画面 amount 18-28 强; 静止帧无效 |
| GUTS BadTV | GUTS BadTV | -0001 | 2轻/4中/6重/9+猛 |
| AESweetsGlitch7in1 | AESweetsGlitch7in1 | 默认即 23.6dB | 克制用 |
| RWB Fast Bokeh | RWB Fast Bokeh | -0001=半径 | 1轻/2中 |
| ADBE Glo2 (原生) | ADBE Glo2 | -0002阈值/-0003半径/-0004强度 | 阈值0.8=只晕高光 |
| CC Radial Fast Blur | CC Radial Fast Blur | **-0002**=量 (默认50!) -0001=类型 | 15=26dB/60=22.6dB饱和 |
| Twixtor 45 | Twixtor 45 | -0004=timing模式, -0005=速度% | 55=0.55x |
已弃用: RealGlow (JAeToolsRealGlow) 参数空间不可控 (3.4-8dB 全糊);
批量 GPU 插件 (Sapphire/BCC) 无头易崩。
未驯化 (下步候选): Sapphire S_*, BCC, Universe, HitFilm, Particular (GPU 崩溃风险需单实例逐个驯)。

### 5.3 校准方法论 (可复用)
宫格 comp (3×3 同帧 9 变体, scale 33.33% + position 分格 + startTime=-20 取源帧) →
aerender -s 0 -e 0 渲 1 帧 → PIL 分格 PSNR vs 原帧 → 剂量 dB 标尺。
参数无标签 → 全部枚举 + 小批量试探 (≤3/批防崩)。

### 5.4 包络/密度设计 (v4, 用户认可方向)
- 拍点包络: `pr.setValueAtTime(t0, v)` (创建键!) 切点满剂量 → t0+0.12s 衰减到 30-45% 保持。
  (注意: setValueAtKey 只操作已有键会报"无法在此属性的键上执行任何操作")
- 连续密度: 剂量 = 基础 × (0.65 + 0.7×RMS包络); 包络 = BGM 谐波 RMS 0.6s 平滑 (与引擎呼吸语法同源)。
- 转场冲击层: 强鼓点切点顶层 2-4 帧 burst (radial/badtv), 起爆在闪帧后 +0.13s, 间隔 ≥0.8s。

### 5.5 光流感知 (v5)
- Farneback 光流 (320×180, 0.5/3/15/3/5/1.2/0), p90 幅度 + 幅度加权角度圆均值。
- 水平主导 (|cos|>0.7) + 高幅 → 方向条纹 (FMB 角度=实测运动角 mod180);
  缩放/垂直/静止 → radial_soft。幅度→长度连续耦合。

### 5.6 剪辑引擎现状 (前日已验收, 供上下文)
- V23 ProductionDirector: HPSS 鼓点/小提琴律动网格/能量呼吸语法(0.6s平滑+±18%滞回)/
  拍点包络变速/冲击帧(闪帧+glitch)/AI 语义选材/帧级对齐 — run50 用户"对了", run53 结构沿用。
- 引擎产出 116 镜 (intro 1 / build 62 / drop 53), 变速档 0.55/1.1/1.15/1.5/1.55。
- **洛天依重复 = 引擎源选择缺陷** (见 §3)。

### 5.7 运行手册 (重跑关键命令)
```
# 重建+重渲 AE 精修 (跑完整闭环)
python scripts/build_master_polish.py output/unified_run53 run53
aerender -project output/unified_run53/polish/master.aep -comp MASTER -output output/unified_run53/polish/master.mp4
ffmpeg -y -i .../master.mp4 -i .../run53_final.mp4 -map 0:v -map 1:a -c copy run53_final.mp4   # 混流
python scripts/render_gate.py output/unified_run53 run53 --bgm "D:/AE-Work/音频素材库/BGM/1_from10s.mp3"
python scripts/harvest_experience.py output/unified_run53 run53 --verdict "..." --bgm "..."
# AE 探活
python -c "from ai.ae_render_channel import AERenderChannel; print(AERenderChannel(out_dir='output/probe')._bridge_run_jsx(timeout=60, command='executeAtomScript', args={'script':'app.version;','scriptContent':'app.version;'}))"
```

---

## 6. 下一步 (按优先级, 接手程序从这开始)

1. **[用户未决] 源素材去重**: 修 §3 洛天依重复 — 引擎源选择加全局同片段去重约束 + 语义换源,
   重跑 unified_edit → 重渲 AE 精修 → 交付 (全链路 ~15 分钟 + 渲染)。
2. **[待用户验收] run53_final v6**: 若用户否 v6 (慢镜/效果), 按 §5.1 偏好调 build_master_polish.py
   的 RECIPES/plan_effects 参数重渲 (1 分钟/轮)。
3. **速度曲线 Twixtor 化**: 每镜 2-3 段常数速度 → 连续渐变 (Twixtor Speed 曲线, 变速无痕)。
   Twixtor 链已验证可用 (§4.5), 直接扩展。
4. **语义选效果**: 把 AI battle/closeup 分类接进效果映射 (战斗→冲击/拖尾, 特写→推镜+glint)。
5. **层2自进化** (等 20+ 样本): 参数寻优 + rhythm_reward 重训 (正负样本已积累);
   层3: N 变体自动竞争。经验在 data/evolution/render_history.jsonl。
6. 素材库扩充脚本 (语义检索建档 D:\AE-Work 全部素材) — 缓解源重复的根本。

## 7. 今日提交 (git)
374554e v6 Twixtor驯化 | 6219b22 v5 光流感知 | 3b23024 v4.3 剂量闭环 |
419b0b3 v4 拍点包络 | 33260e0 v3.1 段落覆盖 | 8b3c0a4 v2 镜头级精修 |
0ea69e7 polish_pass 五坑 | 以及早间 classifier 相关 (726f7d3 起, 非本会话主线)。
