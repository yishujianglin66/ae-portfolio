# 交接 2026-09-04: AE 精修通道自愈 + polish_pass 五坑修复

## 成果
- run53 终版 = AE 全片精修（Glow 0.3/8 + Noise 4%）+ SFX 混音音轨
  → `output/unified_run53/run53_final.mp4`（旧版存档 `run53_final_prepolish.mp4`）
- 闸门 7/7 PASS；经验已收割（render_history.jsonl）
- `ai/ae_render_channel.py polish_pass` 源码已同步修复，下次直接可用

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
