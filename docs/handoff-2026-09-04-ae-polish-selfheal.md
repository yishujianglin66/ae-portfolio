# 交接 2026-09-04: AE 精修通道自愈 + 镜头级插件精修 v2

## 成果 (v2 镜头级, 用户 18:15 定调)
- **run53_final.mp4 = 镜头级 AE 精修**: MASTER 总合成 = BASE 全片底层 + 55 个镜头切段图层
  (116 镜中 47% 上效果, 克制), 每镜头按设计单独上插件, aerender 单次渲染 50s。
- 闸门 7/7 PASS; 效果分布经 PSNR 抽检验证 (原样镜 >43dB=仅重编码噪声, 效果镜 13-49dB 分层)。
- 前一版全片 Glow 调色版存档 `run53_final_glowpass.mp4` (用户定调: 调色归达芬奇, 弃用)。
- 构建器: `scripts/build_master_polish.py` (映射规则+JSX 生成+桥执行一体)。

## 插件库 (本机 2413 特效已枚举 → tmp/ae_effects_all.txt)
关键可用 matchName (无头添加全部验证过):
- `CC Force Motion Blur` (运动模糊, -0001=amount, cal 12=轻/20=中; 实际运动中强得多)
- `GUTS BadTV` (-0001=强度, 2=轻 6=重; 模拟失真冲击)
- `AESweetsGlitch7in1` (默认 23.6dB 数字故障; -0005 非总量, 敏感参数未定位)
- `RWB Fast Bokeh` (-0001=半径, 1=轻 2=中; 慢镜散景)
- `ADBE Glo2` 原生发光 (-0002阈值/-0003半径/-0004强度; 高阈值 0.8=只晕高光 bloom)
- `GUTS SEPRGB` (默认 37dB 轻度RGB分裂; -0001 TwoD 不可 setValue, 未深挖—成片已烘 RGB)
- **RealGlow (ADBE JAeToolsRealGlow) 参数空间不可控, 弃用** (P1-P8 全试过, 3.4-8dB 全糊)
- 危险: 批量添加 15 个 GPU 插件(Twixtor/Sapphire/BCC/Universe/HitFilm)会崩 AE —
  每批 ≤3 个勘探。Twixtor/Sapphire/BCC 本轮未用 (崩溃风险>收益)。

## 镜头→插件映射 (build_master_polish.py RECIPES)
- 决斗变速停顿 spd≤0.55: bloom(高光晕) + bokeh@1 (能量高时)
- 决斗快切 spd≥1.5 能量前25%: badtv@2.5; 高潮 22.1-24.6 核心 4 镜 badtv_hard@6
- 每 9 个 drop 镜 1 个: glitch7in1 (节制的数字故障强调)
- 决斗其余快切: fmb@18 (拖影连切); build 快切: fmb_light@14
- 尾奏 t≥27 慢镜: bloom_soft; intro: 无
统计: fmb 19 / badtv 15 / bloom 11 / bokeh 11 / glitch 4 / badtv_hard 4 / bloom_soft 2

## 校准方法论 (第三方插件参数无标签 → 宫格渲染量化)
3×3 宫格 comp (同帧 9 变体, scale 33.33%, position 分格, startTime=-20 取源帧),
aerender -s 0 -e 0 渲 1 帧, PIL 分格 PSNR vs 原帧 → 剂量 dB 标尺。
两轮即定位全部配方; SEPRGB setValue 失败/RealGlow 不敏感当场排除。

## v2.1 修复: 黑帧架构 bug
只给有效果镜头建图层 → 其余 61 镜黑帧 (症状: "原样"时码 PSNR 3-5dB)。
修复: BASE 全片底层 + 效果镜头层叠加 (layers=56)。

## AE 桥自愈 (v1 发现, 仍然有效)
- 标准重启后自动监听器随 AE 启动 (ae_auto_listener.log "Auto Listener started"), 无需 GUI 加载 jsx
- 探活: AERenderChannel._bridge_run_jsx(args={'script':'app.version;',...}) → status success
- 监听器不回传脚本返回值 — 读值让 JSX 写探针文件
- 崩溃后标准重启: taskkill → 清 .ae-mcp-bridge/*.json → start AfterFX.exe → 等加载 → 探活

## 待办
- 用户验收 run53_final (镜头级精修版); 可调维度: 覆盖率47%/各配方剂量/分布规则
- 若通过: build_master_polish.py 接入 unified_edit ④-c 替换旧 polish_pass
- aerender 五坑 (相对路径/-comp/模板/时长/matchName) 见 v1 交接段落, polish_pass 源码已修

## 关键发现: AE 桥自愈（不需要 GUI 接管）
- AE 标准重启后（taskkill → 清 `.ae-mcp-bridge/ae_command.json+ae_result.json` → start AfterFX.exe → 等加载），
  **自动监听器随 AE 启动**（`.ae-mcp-bridge/ae_auto_listener.log` 出现
  `AE MCP Auto Listener started`），无需手动 File>Scripts 加载 jsx。
- 探活一行: `AERenderChannel(out_dir=...)._bridge_run_jsx(timeout=60, command='executeAtomScript',
  args={'script':'app.version;','scriptContent':'app.version;'})` → `status: success` 即活。
- 监听器不回传脚本返回值（只有 `executed: true`）——需要读值时让 JSX 写探针文件
  （`tmp/ae_probe*.json`，`rep.toSource()` + `File.open('w')`）再 python 读。

## polish_pass 五坑（都已修进源码）
1. **相对路径**: aerender 把 `-project` 相对路径解析到自己安装目录 → 必须 `od.resolve()` 绝对路径。
2. **-comp 按名渲染**: JSX 只建合成没进渲染队列，aerender 无参空转（RC=0 假成功）→ 传 `-comp POLISH`。
3. **模板不存在**: `app.newProject()` 新工程没有 "Best Settings/Lossless" 模板，
   `-RStemplate/-OMtemplate` 直接报错 → 全部去掉；默认输出模块就是 H.264 .mp4 (~16Mbps)，
   无需 Lossless AVI + ffmpeg 转码两级（顺带省 2GB 磁盘和一分钟）。
4. **adjustment layer 时长**: `layers.addSolid(..., duration)` 第 6 参单位是秒，传 1.0 只盖住第 1 秒
   （症状: t=0.5 有特效、t≥1s 无；PSNR 扫描 6 点定位）→ 传 `imp.duration`。
5. **中文版 AE 参数名**: `fx.property("Glow Intensity")` 返回 null（显示名是中文"发光强度"）→
   一律 matchName：`ADBE Glo2-0003`(半径)/`ADBE Glo2-0004`(强度)/`ADBE Noise-0001`(数量)。
   另: `ADBE Add Grain` 此版本不可脚本添加（报"无法添加到此 PropertyGroup"）→ 用 `ADBE Noise` 替代。

## 附: subprocess GBK 崩溃
aerender 中文输出是 GBK；`subprocess.run(text=True)` 默认 utf-8 会崩 reader 线程
（表现为莫名 "aerender 失败" 且看不到真实错误）→ `encoding='utf-8', errors='replace'`
（手动诊断时用 `.decode('gbk', errors='replace')`）。

## 验证方法（特效确实渲染了）
同帧 PSNR 扫描（lut vs polish, 6 个时间点 0.5/5/10/15/20/25s）:
- 特效生效 → PSNR 15~27dB（Glow 晕+噪点差异大）
- 纯黑/白闪帧上 Glow 无作用 → Noise 仍会拉到 ~45dB
- 特效没渲染 → ~91dB（仅重编码噪声）
陷阱: 单点对比可能撞上两文件解码帧错位（不同画面 → 17dB 假阳性），多点扫描才可靠。

## 待办
- 用户验收 run53_final（AE 精修版）
- 层2: 参数寻优 + rhythm_reward 重训（等 20+ 样本）；层3: N 变体竞争
- 文法卡更新到 run53 状态（小提琴锚定/36%鼓点跳过/持续音zoom_in/AE精修配方）

## v6 Twixtor 驯化 (2026-09-04 晚, 已交付 run53_final.mp4)

- **Twixtor 无头安全**: 单独添加不崩 (上次批量崩元凶是 Sapphire/BCC 系); matchName="Twixtor 45",
  速度参数=-0005 (默认100=100%), timing模式=-0004
- **时间模型 (三公式对照实验确证)**: source_time = (t - startTime) × speed
  → startTime = t0 - sin/spd (含 t0 项, 试点在 inPoint=0 时恰好掩盖了 t0 项)
- **AE 钳位坑**: startTime 巨偏移把图层有效窗推出源时长 → in/out 被钳成零长层
  (症状: in==out=负值) → ffmpeg 预裁源片 [sin-lead, sin+dur×spd+0.1], lead 自适应 (0.5/0.2/0.05,
  源尾不足时缩), sin 改片内偏移
- **验证方法论坑**: bloom 高剂量帧 vs 源帧 PSNR 会崩到 6-15dB 但内容正确 —
  视觉模型确认同场景 + 去效果单帧渲染法 (22.1dB 基线) 才是真验证; 全场像素对比会误判
- 推镜复刻: TWX 层 Scale 关键帧 [bs→bs×1.09/1.12] (zoom_in 1.12), bs=cover 尺度
- v6.2: 13/13 慢镜 Twixtor 层存活, 闸门 7/7
