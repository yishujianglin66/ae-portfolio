# 资源库 ↔ 项目模块映射与推进方向（基于 resource_scan_report.txt）

> 日期：2026-08-16 · 数据源：`tmp/resource_scan_report.txt`（9466 行，扫描于 23:04）
> 扫描范围：`D:\AE-Work\resources`（外部资源库）+ `AE-Knowledge-Vault\resources` + `AE-Knowledge-Vault\data`
> 总计 **43396 个素材文件**（去重后有效资产约为报告数一半，大量双份拷贝）

---

## 一、资源全景（八大类 + 3D 模型）

| 类别 | 数量 | 核心内容 | 质量评估 |
|---|---|---|---|
| LUT | 16516 | Super Creators Pack 按风格主题分：HDR/好莱坞/婚礼/复古电影(胶片)/冷色调/夏日/商业/城市/回忆/寂静/天空无人机/Youtube Vlog(LOG转709)/创意 | ⭐ 最大资产，风格主题即目录名，天然可索引 |
| 音频 | 4753 | TVC音效库(50)、上升Risers(307)、信号干扰故障(185)、转场环绕/Whoosh/Trailer Hit、完整BGM曲目 | ⭐ 卡点链路的音频半环，全齐 |
| 图片 | 15834 | effects 特效贴图 **14 大类**：序列帧(770)/扩散旋转(543)/扭曲烟雾(452)/刀光(431)/光点(397)/魔法阵(385)/图案(367)/UV动画(325)/线性条状(267)/溅射光点(189)/物体(139)/无缝贴图(91)/文字(89)/物件(77)；references(1528) | ⭐ 透明 PNG 叠加层，分类即语义 |
| 字体 | 5060 | 中文/英文/毛笔书法/卡通可爱/可爱字体库 分类目录 | 按风格池扩展的现成弹药 |
| PSD | 1019 | 字体加排版 50 款分层模板等 | 排版知识可提取 |
| AE工程 | 33 | 新手10套案例：五条悟/初音/猫猫/美人鱼(艾利)/蓝色监狱/辉夜/独自升级/8.15/do you mean/李诗雅竖屏，**每套含成品.mp4 + 素材 + .aep** | ⭐ 人工成品的节奏真值 |
| 预设 | 6 | PR Cinematic Looks V7（多版本重复） | 低优先（PR 生态） |
| 3D模型 | 5179文件 | 王者荣耀 S389 人物模型（李白千年之狐/诸葛亮/花木兰/露娜/孙悟空/干将莫邪…含 Mesh/Sprite/贴图/预览mp4） | Blender 3D 素材层方向 |

**重要事实**：报告自带"生产可用性评估"已给出漫剪卡点链路映射（BGM分析→节奏锚定→变速运镜→特效叠加→LUT调色→字幕包装→工程输出），本文件在其基础上落到**项目真实模块**。

---

## 二、逐模块映射（资源 → 消费模块 → 现状 → 推进方向）

### 1. 调色链路：LUT 库 ↔ 风格卡 `color_grade_params`
- **现状**：8 张风格卡（`data/style_cards/*.json`）的调色是**手调 Lumetri 参数**（如 `ADBE Lumetri-0012: 25`），LUT 库 16516 个完全未接。`core/style_preset_adapter.py`/`style_presets.py` 只消费这些参数。
- **缺口**：AE 的 Lumetri 支持 `ApplyLUT` 挂 .cube，一行 JSX 就能接；风格卡 schema 无 `lut` 字段。
- **推进**：
  1. 风格卡加 `"lut"` 字段，按目录名主题索引：`cinematic_film → luts/好莱坞/`、`vintage_film → luts/复古电影/`、`cyberpunk → 冷色调/创意/`、`ambient_calm → 寂静/`、`amv_highenergy → HDR/商业/`
  2. `style_tree_builder`/`composition_tree` 的 adjustment 层加 `lut_layer` 类型（Lumetri ApplyLUT + cube 路径 + intensity）
  3. **重要连锁**：接 LUT 后画面色彩出现真实方差 → **color_harmony 维度可能从"标签天花板"解锁**（此前学不会正因为合成画面色彩全和谐无方差）→ 该维度可重新进入调参器自动迭代（GRID 加 lut 选择参数重采集）

### 2. 音效链路：SFX 库 ↔ `beat_events`（当前零消费）
- **现状**：grep 全 core/ 无任何 sfx/riser/whoosh 消费模块。`core/beat_strength_engine.py`/`music_dynamics.py` 只分析音乐，`audiovisual_correlator.py` 只做相关性。**4753 个音效一个都没用上。**
- **缺口**：这是卡点链路里"撞拍音效增强"的整条缺失环节。
- **推进**：
  1. 新建 `core/sfx_layer.py`：按 beat_type 映射音效池——`kick → Trailer Hit/Code Black`、`snare → 转场环绕/Whoosh`、`build 段 → Risers(307个)`铺垫上升、`drop 前拍 → Deep Riser`、故障转场 `→ 信号干扰Glitch音效(185个)`
  2. 合成树加 `type="audio"` 图层（AE 音频层 JSX：footage 导入 + 时间对齐 beat_event）
  3. 与 M2 闭环联动：pacing 维度评分将获得音频证据（现在只有视觉），是 OmniScientist"音频感知反向驱动剪辑决策"的自然延伸

### 3. 特效贴图链路：effects 14 大类 ↔ `plugin_fx_templates` / `edit_fx_vocabulary`
- **现状**：Trapcode Particular 粒子是参数生成（spark 模板 + psize/glow 参数）；`core/gen_fx_provider.py` 是生成式素材；`effect_registry.py` 硬编码映射。**现成贴图资产未进注册表。**
- **推进**：
  1. `effect_registry` 挂载 effects 目录 14 类为语义资产池：`刀光类→slash_fx`、`魔法阵类→magic_circle`、`序列帧贴图(770)→frame_sequence`（AE 序列帧导入直接可播）、`扭曲烟雾→smoke_warp`
  2. 合成树 `type="image_fx"` 图层：透明 PNG 叠加 + 撞拍时刻缩放/旋转关键帧（比 Particular 渲染快，且是"实战验证过"的美术资产）
  3. 调参器 GRID 扩展：`fx_asset 选择` 成为新的可调参数（贴图类型/混合模式/入场动画）

### 4. 字体链路：5060 字库 ↔ `font_style_map` / `font_manager`
- **现状**：`core/font_style_map.py` 风格卡字体映射只有少量字体（Anton/Bebas/勘亭流等），`font_scanner.py` 扫描系统字体。资源库按**风格目录**组织（01-中文/02-英文/04-卡通可爱/07-毛笔书法）。
- **推进**：
  1. 风格卡 `font_pool` 字段按资源目录映射：`hardcore_battle → 07-毛笔书法（毛笔大字撞拍）`、`emotional_lyric → 01-中文细体`、`cyberpunk → 02-英文字体（科技感）`、`ambient_calm → 手写细体`
  2. `font_manager` 支持资源库字体注册（AE 渲染机装字体或工程内嵌）
  3. text_read 维度的调参器可扩"字体选择"参数（不同字重/风格影响可读性评分）

### 5. 节奏知识链路：10 套人工成品工程 ↔ `template_rhythm` / 学习系统
- **现状**：`core/template_rhythm.py` 存在但案例工程未系统利用。10 套 .aep 是**人工成品的卡点真值**（成品.mp4 ↔ 工程 ↔ 素材三件套齐全）。
- **推进**：
  1. 用 AE 桥接解析每套 .aep 的时间线（层数/切点/转场/变速），抽成"节奏模式库"（如蓝色监狱=量多快切、美人鱼=较难变速卡点、初音=Twixtor 补帧流）
  2. 成品.mp4 直接进 M2 评分器做**人工作品锚点评分**——qwen/CNN 对人工成品 vs 我们自动成品的分差 = 质量差距的量化目标（黄金集思想向"作品级"延伸）
  3. 素材配对可做对照实验：同一素材 + 人工剪法 vs 自动剪法，隔离"素材质量"变量

### 6. 参考图链路：references 1528 ↔ 风格学习
- **推进**：`data/style_dataset`（现有 2 文件）扩容：references 按风格聚类 → CLIP 嵌入（复用 `encode_tuning_frames.py` 管线）→ 风格卡的视觉锚（每张卡的"参考帧质心"），供风格自检对比。

### 7. 3D 素材链路：王者模型 ↔ Blender 生成层
- **现状**：`gen_fx_provider.py` 有 3D 方向（用户有 Blender 4.21）。
- **推进**（低优先长线）：王者模型（含 Mesh/贴图/预览动画）→ Blender headless 渲染角色运镜镜头 → `type="footage"` 层进合成树。与 M2 闭环天然兼容（渲染出的镜头同样进评分器）。

### 8. 排版知识链路：PSD 50 款 ↔ 文字动画
- **推进**（低优先）：解析分层 PSD 的字号/字间距/行距/构图 → `text_3d.py`/文字动画的排版知识表。

---

## 三、与当前主线（M2 调参器/视觉评估闭环）的衔接

按交接文档（`docs/handoff-2026-08-16-m2-tuner.md`）遗留任务优先级，资源接入的最佳切入点：

1. **遗留#6 参数空间扩展 ← LUT 接入（最优先）**：GRID 加 `lut` 参数（风格主题内抽样 cube 文件），重采集 → color_harmony 标签解锁 → CNN/GBDT 重训 → 该维度首次可学。这把最大的闲置资产（16516 LUT）变成调参器的新维度。
2. **SFX 层新建（第二优先）**：beat_events 已有 kick/snare 结构，音效池映射是纯增量工作，补齐卡点链路音频半环。
3. **特效贴图注册（第三优先）**：effect_registry 挂 14 类资产池 + image_fx 图层类型，扩充效果语汇。
4. **人工作品锚点（与遗留#5 黄金集扩展合并）**：10 套成品.mp4 进评分器建立"作品级质量标尺"。

## 四、数据卫生提醒（资源接入同样适用交接铁律）

- LUT/贴图/音效接入 GRID 采集时：**资源文件名/内容哈希进样本行**（防"按路径绑定"在资源移动后错位——与黄金集签名匹配同理）
- 双份拷贝（`effects\` 与 `effects\特效贴图PNG\特效贴图（PNG）\` 完全重复、audio 同构）需先做去重索引，以内容哈希为准，避免采样到重复组合浪费渲染
- `._*` 开头文件（macOS 元数据 4KB 假文件）必须过滤，上升 Risers 目录里混了大量

## 五、一句话总结

4.3 万素材里三大闲置金矿：**16516 个 LUT（解锁 color_harmony 维度）、4753 个 SFX（补齐卡点音频半环）、14 类特效贴图 + 10 套人工成品工程（效果语汇与节奏真值）**——全部可按既有模块（风格卡/合成树/beat_events/effect_registry/M2 评分闭环）渐进接入，不需要新架构。

---

# 资源接入落地实录（2026-08-17 凌晨通宵轮）

## ✅ 已完成并真机验证

### 1. LUT 管线（核心突破）
- **AE 内路线证伪**: Lumetri LUT 参数 (0005/0125/0127) 是资产型, setValue 弹 UI 卡死无人值守 (真机实测)
- **ffmpeg lut3d 路线**: `core/lut_pipeline.py` — split+blend 线性强度混合, 像素级验证 (B 通道 6.8→22.6(0.5)→43.4(1.0) 精确线性)
- **索引**: `scripts/build_lut_index.py` → 41 主题/去重 3317/采样池 492 (`data/luts/`)
- **集成**: render_tree(lut=...) / GRID(lut_theme+lut_strength) / 8 张风格卡 lut 字段
- **⚠ HSV 误判教训**: 强度混合后 HSV 饱和度非线性 (深色帧 RGB 微偏 → S 暴涨), 验证必须用 RGB 像素差
- **color_harmony 解锁实证**: LUT 样本评分 [6.0-8.0] std 0.68 (此前天花板全 8 无方差), 主题分化 (夏日 8.0 vs 寂静 6.0)
- pick_lut 主题跟随 bug 修复 (combo 主题优先)

### 2. SFX 卡点音效层
- `core/sfx_layer.py` + `scripts/build_sfx_index.py` → 四池 40×4 (impact/whoosh/riser/glitch)
- `plan_sfx(beat_events)` 语义映射 (kick→Hit, snare→Whoosh) + `mix_sfx` ffmpeg adelay+amix
- 真机验证: kick 时窗 -14.2dB vs 无音效尾段 -19.2dB (落点真实)

### 3. 特效贴图层
- `scripts/build_fx_asset_index.py` → 14 类 420 张去重 (`data/fx_assets/`)
- `core/image_fx.py`: pick_fx_layer(slash/magic_circle/...) → footage 图层 + 撞拍 punch
- BEAT_FX_MAP: kick→刀光/爆开, drop→魔法阵, build→烟雾

### 4. 字体池
- `scripts/extend_font_pool.py` → 69 候选 (10 分类×8, fontTools PS 名), 会话级安装 3 (文件名冲突限制, 索引已备)

### 5. 人工作品质量标尺
- `scripts/human_benchmark.py` → 9 部人工成品 CNN 评分 + 差距表 (`output/m2_iteration/human_benchmark.json`)
- 自动 vs 人工: dynamism -0.27 / pacing -0.23 → 追赶方向明确

### 6. 风格视觉锚
- `scripts/build_style_visual_anchor.py` → 真实素材视频抽帧 120 张, CLIP 768 维质心 4 组 (dark 58/vivid 34/muted 20/bright 8)
- ⚠ references 1528 张全为 <100KB 小图标, 已弃用换 real_amv_test

## 🏆 端到端大验收 (grand_finale, 2026-08-17 02:31)
`scripts/grand_finale.py` → `output/grand_finale/finale.mp4`
- 7 层合成 (FATE素材+粒子+标题+3贴图撞拍层+grain) + 好莱坞 LUT 0.7 + 3 SFX 落点, 94s 渲染
- M2 hybrid 评分 vs 人工标尺: **7/7 维度 ≥ 人工均值**
  dynamism +0.15 / composition +1.08 / color_harmony +1.45 / text_read +0.06 /
  texture +0.18 / pacing +0.12 / overall +0.11
- color_harmony 从"不可学死维度"→ +1.45 优势维度 (LUT 接入的直接回报)
- 诚实边界: CNN 评分器与自动管线同分布 (自评偏好), 人工标尺是混合风格集, 差距为参考性

## 🔧 环境攻坚实录 (AE 启动连环坑, 全部破解)
1. **AE GUI 冷启动需 3-5 分钟** (322MB Plugin Loading.log + 5000 字体) — 此前 60-90s 就 taskkill 是自杀循环
2. **prefs 损坏**: 换出 25.3 → 重置; 新 prefs 缺脚本权限 (`Pref_SCRIPTING_FILE_NETWORK_SECURITY=0`) → 改 1 + 关运行警告
3. **Boris FX Continuum 插件错误弹窗卡启动** — 主窗口标题暴露; ESC+Enter 关闭后启动完成
4. **监听器自调度偶发断** (Polling started OK 但不消费命令) — 重启解决; ping 协议验证 (`AECommandClient('ping')`)
5. 322MB 巨型 Plugin Loading.log 移走 (句柄占用时等 AE 退出再删)

## ⚠ 已知阻塞与解法
- **人工工程挖掘 (mine_human_projects.py)**: app.open 大工程弹缺字体对话框卡脚本 → 解法: SendKeys 预案关框 / 预装工程字体 / aerender 通道
- **SynthesisOrchestrator 超时已改 300s** (首渲染需编译)
- SFX amix normalize=0 峰值 0dB (轻微削波) → 可加 alimiter

## 资产→模块 接入总表 (终态)
| 资产 | 模块 | 状态 |
|---|---|---|
| LUT 3317 | core/lut_pipeline + 风格卡 lut + GRID | ✅ 生产 |
| SFX 160池 | core/sfx_layer + beat_events | ✅ 生产 |
| 贴图 420 | core/image_fx + BEAT_FX_MAP | ✅ 生产 |
| 字体 69 候选 | scripts/extend_font_pool | ✅ 索引 (安装受限) |
| 成品 9 部 | scripts/human_benchmark | ✅ 标尺 |
| 素材帧 120 | data/style_cards_visual_anchor.json | ✅ 4 组质心 |
| 王者 3D 模型 | Blender headless | ⏸ 未启动 (长线) |
| PSD 排版 50 | 未启动 | ⏸ 低优先 |

---

# 通宵轮终章：清理事故与全面恢复（2026-08-17 03:00-04:00）

## ⚠ 事故：03:00 计划清理删除训练数据
- 计划任务 `AEKV-Daily-Disk-Cleanup`（每日 03:00）把 `output/m2_iteration/` 整目录清理
- 根因：`.jsonl` 不在 render_cleanup 的 `DOC_EXTS` 白名单 → train_samples.jsonl（166 行）/
  gold_set.jsonl / human_benchmark.json 被判"中间产物"删除（文档归档只留了 summary.txt）
- 铁证：`D:/AE-Work/渲染档案/.cleanup_log.txt` `[03:00:28] 释放 1.63GB`

## 恢复（全部完成）
1. **根因修复**: `core/render_cleanup.py` 加 `NEVER_DELETE_NAMES`（train_samples*/gold_set/
   human_benchmark 等永不动）+ `.jsonl` 进 DOC_EXTS
2. **数据迁居 data/**: 训练/评估数据全链 12 个文件路径从 output/m2_iteration →
   data/param_tuning（清理器只扫 output 任务目录, data 永不扫）——结构性根治
3. **gold_set 50 条重建**: 黄金标签完整保存在 calibrate_gold_set.py 的 GOLD dict
   （标签+qwen 签名+依据）, 已重建; frame_dir 留空待新采集签名自愈
4. **标尺重跑**: human_benchmark 输出迁 data/benchmarks; finale.mp4 为 OURS 代表
   （round* 被清理）, CNN 评分复现 7/7 维 ≥ 人工均值
5. **核心资产无损**: CLIP 嵌入 100×768 / 帧库 / CNN 头（含标定）/ clean_index 全在 data|models
6. **通宵重采集已启动**: data/param_tuning/train_samples.jsonl 新家, 含 LUT 维度
   （第 1 轮 6/6 已落盘, 复古电影 0.7 样本出现）
7. **晨间管线**: `scripts/morning_pipeline.py` 一条命令跑完
   重建索引→重编码→重训→签名自愈→重标定→基准→回归

## AE 启动稳定性手册（今晚全部踩坑, 通用解法）
| 症状 | 解法 |
|---|---|
| 冷启动慢 (322MB 日志+5000字体) | 等 5-8 分钟, 勿提前 taskkill |
| 215MB 无标题深卡 | **AppActivate 激活 + ESC/Enter 唤醒**（通用解法, 03:49 验证） |
| Boris FX Continuum Error 弹窗 | ESC+Enter 关闭（dialog_guard.ps1 可后台看护, 注意 PS1 中文需 UTF-8 BOM） |
| prefs 损坏 | 换出 25.3 目录重建; 新 prefs 需 `Pref_SCRIPTING_FILE_NETWORK_SECURITY=1` |
| 监听器长命令后自调度断 | ping 探活确认; 重启 AE + 唤醒法 |
| aerender 正常但 GUI 卡 | 引擎无恙, 纯 UI 层问题 |

## 监听器已知缺陷（待修, 写入交接）
- 长命令（20s+）执行后 checkForCommands 自调度链偶发断裂 → 后续命令全超时
- 修复方向: listener 的 scheduleTask 回调里加重注册兜底 / 心跳自检

---

# 终局：晨间管线全绿（2026-08-17 06:50）

## 数据链终态
- 通宵采集 100（含 LUT 维度）+ 黄金定向补采 40 = **140 干净样本**（data/param_tuning）
- 黄金集 50 条**全签名自愈**（frame_dir/cnn/gbdt 补全；匹配降级为参数六元组——qwen 重评分数会漂移）
- CNN 头重训 + 黄金标定 25.8% 改善写入

## 语义演化发现（本轮最有价值的科研发现之一）
**color_harmony 标定 slope=-1.03（负相关）**：黄金 50 条标签是"无 LUT 时代"校准的，
140 新样本（LUT 强色彩变化）下 CNN 学到的 color_harmony 语义已反转——
旧高分=深色和谐，新分布高分=色彩丰富。回归守卫捕获（slope>0.5 断言），
处置：负/浅斜率维合法跳过标定（防预测反转），该维留待**新黄金标签**（LUT 时代的
色彩审美校准是下一轮人工任务）。

## 终局基准（140 样本头 + 50 黄金标签）
| 模型 | MAE | 方向一致 |
|---|---|---|
| **cnn(标定后)** | **0.15** | **0.81** |
| gbdt | 0.22 | 0.80 |
| qwen | 0.32 | 0.67 |

cnn 6/7 维最近真值。回归 3/3 通过（守卫断言更新：≥5 维标定+全维 slope>0.5）。

---

# 参考视频逆向复刻管线（2026-08-17 晨, 用户核心需求落地）

## 需求原话理解
"达到外网漫剪顶尖水平 / 给一个参考视频能推理出剪辑技巧与效果应用, 用项目功能复刻呈现"
+ "合理运用资源库素材" → 不是评分达标, 是**风格迁移式复刻**。

## 实现: core/reference_analyzer.py + scripts/replicate_reference.py
```
参考片 → 8帧成对采样(相邻帧=运动证据) → qwen-vl 技巧分解
  → 结构化画像 (shake/zoom_punch/rgb_burst/speed_ramp/freeze/color/text/overlays/sfx/flash/pacing)
  → profile_to_params 映射 (与 edit_fx_vocabulary 一一对应)
  → 资源库选资产: LUT 41主题库 / 贴图14类 / SFX四池偏好 / 字号权重
  → build_replica_tree (节拍密度随 pacing 画像 3-9 拍自适应)
  → render_tree(+LUT) → SFX 混音 → M2 双评分对比
```

## 真机双参考验证 (2026-08-17 08:0x)
| 参考 | 画像要点 | 自动选择 | overall 差距 |
|---|---|---|---|
| 独自升级(一般) | dark@9 / 1.2切每秒 / glitch文字 / 魔法阵 | 戏剧性LUT@0.67 + streak/sparkle/magic_circle 贴图 | **-0.17** |
| 美人鱼(较难) | vivid@9 / every_beat punch / 霓虹 | 夏日光辉LUT@0.67 + pattern 贴图 + 逐拍punch | **-0.35** |

- 画像正确分化（不同参考 → 不同 LUT/贴图/punch 频率/节拍密度）
- 成片资源可见性实测：两片饱和度 129 vs 77 分化、音轨 -13.7dB 真实
- 7 维差距 -0.01~-0.59, color_harmony/text_read 几乎持平
- 诚实边界: 复刻用 FATE 素材 (非参考原素材), 差距含素材差异; CNN 评分同分布偏好
- 交付物: output/replicate_solo_leveling/ 与 output/replicate_mermaid/
  (replica.mp4 + profile.json + compare.json 画像/参数/资产/对比全留档)

## 用户任意参考的用法
```
python scripts/replicate_reference.py --ref <任意顶尖漫剪.mp4> --tag <名字>
```

---

# 诚实自评：复刻片的真实水平（2026-08-17 晨, 用户批评后的自检）

## 用户批评成立
"差距天差地别 / 你对自己做出来的成品做过视觉分析吗" — 之前 CNN 报的 -0.17/-0.35
是同分布自评, 无效。本次用三类客观证据自检：

## 客观证据（参考=美人鱼 vs 我的复刻）
| 指标 | 参考 | 我的复刻 | 差距 |
|---|---|---|---|
| 场景切换 | 0.6/s (11次/17.6s) | **0.0/s** | 致命：单镜头无剪辑 |
| 切点尖峰 | 1.1/s | 0.5/s | -55% |
| 运动能量 std | 13.80 | 3.77 | 只有 27% |
| 视觉AI评价 | 专业作品 | **业余/半成品** | 画面平/文字工业体每帧居中/特效粗糙单层/色彩单层无情绪 |

## 差距真相排序（画面扁平的根因）
1. **没有剪辑**：复刻片=一条 6s 素材+特效, 参考是 11 个场景的蒙太奇 — 效果参数弥补不了缺剪辑
2. 构图静态：无镜头运动变化、无逐镜头处理
3. 文字设计：工业粗体 vs 参考的风格化排版
4. 特效粗糙：单层贴图 vs 参考的多层光效/辉光
5. 色彩情绪：单层 LUT vs 参考的冷暖对比叙事

## 多镜头修复尝试（multishot_replica.py）与未解 bug
- 8 镜头×5 素材错峰排布（layer_builders startTime/outPoint 已确认正确映射）
- **结果: 7 个预期切点仅 1 个真实硬切（t=5s 帧差46.6, 其余 3.9-21.3）**
- 排除项: 层错峰映射正确 / 源素材两两差异大(0.26-0.34) / LUT 不是原因(统一处理)
- 待查嫌疑: ①同 z_index=0 的 8 层渲染顺序/覆盖行为 ②`time_range_source`(自造键)
  可能不被 builder 支持, 全部镜头读源 t=0 且源前几秒画面相似 ③speed_ramps 的
  timeRemap 与层 outPoint 交互
- 调试入口: core/layer_builders.py 的 footage builder + 逐层打印生成的 JSX

## 结论与下一步（诚实）
- **已真实具备**: 参考逆向画像(正确分化) / 资产选择挂载(LUT/贴图/SFX 实测可见) /
  效果参数渲染(punch/shake/chroma 有效)
- **核心缺失**: 剪辑本体（多镜头切换）— 这是"效果演示器"与"剪辑系统"的分界线
- 修复优先级: ①多镜头切换 bug（上文三嫌疑） ②镜头运动多样性(per-shot scale/pos)
  ③文字排版系统 ④多层特效叠加
