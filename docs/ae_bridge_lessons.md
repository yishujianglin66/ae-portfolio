# AE Bridge 开发踩坑档案（经验沉淀，必读）

> 本文件汇总历次 AE Bridge / 真实渲染链开发中**实际验证过**的失败点与对策。
> 任何涉及 AE 命令下发、JSX 执行、渲染输出的任务，开工前先读本文件，避免重复踩坑。
> 新经验请按「编号 + 日期」追加到文末。

---

## 1. Bridge 文件轮询协议（.ae-mcp-bridge/）

- 命令通道：项目根 `.ae-mcp-bridge/ae_command.json`，结果：`ae_result.json`，listener 每 ~200ms 轮询。
- **listener 用文件 mtime 变化检测新命令**（`mtime.getTime() !== lastCmdTime`）。
  Windows 文件系统秒级精度 → **同一秒内写两次命令，第二次会被跳过**。
  ~~对策：Python 侧写命令后 `os.utime(cmd_path, (t, t))` 强制 mtime 严格递增~~
  **【2026-08-05 修正：此法已废弃】** Python `time.time()` 与 Windows 文件时间
  可能存在分钟级偏差，`os.utime(max(time.time(), last+1))` 会把 mtime 设到
  "过去"，listener 永远检测不到新命令 → **桥接永久卡死**（实测事故）。
  现行对策：不碰 mtime（文件写入自带新时间戳）+ 真实时钟串行间隔 ≥1.1s
  （见 `integrations/resolve_ae_resolve_pipeline.py::AEBridgeLite._send`）。
- 响应格式：`{"status": "success"|"error", "result": ...}`，**没有 `success` 字段**；
  数据通常在 `result` 里（可能是 JSON 字符串，需二次 `json.loads`）。
- **结果文件竞态**：listener 先置 `processed=true` 再写 `ae_result.json`，
  Python 侧看到 processed 立即读结果会读到**上一条命令的旧文件**（表现为 result 丢失/只剩 executed:true）。
  对策：发送前记录 `ae_result.json` mtime，轮询时要求 mtime 严格增大才读取。

## 2. listener 命令集（jsx/AE-Bridge.jsx + jsx/AE-CommandListener.jsx）

- 支持的原生命令：`ping`、`getProjectInfo`、`executeAtomScript`、`listCompositions`、`importFootage`。
- **不支持 `runScript`** — 发 runScript 会报错；非原生操作一律包装成
  `executeAtomScript` + `{"script": "return " + jsx代码}`。
- `executeAtomScript` 用 `new Function(scriptStr)` 执行脚本体 → **脚本体是函数体，
  需要 `return` 前缀**（如 `return eval("(...IIFE...)");` 或直接 `return (function(){...})();`）。
  **注意 ASI 陷阱**：`return` 后紧跟换行会被 JS 自动插入分号（返回 undefined，result 丢失），
  JSX 必须与 return 同一行或先行去除换行。
- JSX 里返回数据用 `JSON.stringify({success:true, data:{...}})`，Python 侧解析 `result`。

## 3. JSX / ExtendScript 常见失败点

- **`app.project.activeItem` 会被 importFootage 劫持**：导入素材后 activeItem 变成素材，
  依赖 activeItem 的后续 JSX（加图层/渲染）全部静默失败 → **所有 JSX 必须按合成名定位**：
  ```js
  function __gc(n){for(var i=1;i<=app.project.numItems;i++){
    var it=app.project.item(i);
    if(it instanceof CompItem&&it.name===n)return it;}return null;}
  var c=__gc("合成名");
  ```
  实现参考 `pipeline/stages/execution.py` 的 `_comp_prefix` / `_add_footage_to_comp`。
- 素材入合成必须显式 `layer.startTime = 现有图层最大 outPoint`，并裁剪
  `layer.outPoint = min(原outPoint, comp.duration)`，否则出现空时段黑屏。
- 渲染 JSX：`app.project.renderQueue.items.add(comp)` → `om.file=new File("正斜杠路径")` →
  `om.format="QuickTime"`（输出 .mp4 容器也可被 ffmpeg 读）→ `rq.render()` 同步阻塞 → `rqi.remove()`。
  路径必须 `\\` 转 `/`。
- 效果 matchName（已验证可 addProperty）：
  - 色相饱和度：`ADBE HUE SATURATION`（主饱和度属性 matchName=`ADBE HUE SATURATION-0005`，-100~100）
  - 亮度对比：`ADBE Brightness & Contrast 2`（注意带 ` 2` 后缀！亮度=`-0001`，对比度=`-0002`）
  - 色彩平衡：`ADBE Color Balance`（Red=`-0001`/Green=`-0002`/Blue=`-0003`）
  - 辉光：`ADBE Glo2`；噪点/颗粒：`ADBE Noise`
  - 完整属性表见 `video/style_migrator.py` 的映射字典
  - 【P4 新增 2026-08】粒子：`CC Particle World`/`CC Particle Systems II`；
    CC Rainfall/Snowfall 真实 matchName = `CSRainfall`/`CSSnowfall`（≠显示名！）；
    Glo2 颜色 A/B = `-0012`/`-0013`（不是 -0006/-0007）；
    Shift Channels = `ADBE Shift Channels`、Set Channels = `ADBE Set Channels`、
    位移 = `ADBE Offset` 均已实测
- **【P4 新增】枚举属性一律不传裸数字**：BlendingMode、ParagraphJustification
  （`textDoc.justification=1` 直接报错）、Glo2-0005（合成原始图像）等，
  裸数字 setValue 抛"无法转换/无法应用"异常 → 用枚举对象或直接跳过用默认值。
- **中文版 AE 的属性显示名是本地化的**：`eff.property("Master Saturation")` 返回 null！
  必须遍历 `eff.property(i).matchName` 定位属性再 setValue（matchName 不随语言变化）。
- 风格类效果应落在**调整图层**上（`addSolid` + `adjustmentLayer=true`），才对全合成可见。
- **【P4 新增】Lumetri 首次 addProperty 会同步初始化效果引擎，实测耗时 120s+**，
  会打穿任何客户端超时 → 正式作业前先跑 `StylePresetEngine.warmup_effects()`
  （小合成 addProperty Lumetri+Glo2 后删合成）预热。
- **【P4 新增】Bridge 单槽协议丢命令窗口**：AE 忙时客户端新命令会覆盖
  ae_command.json，中间命令丢失；`core/fx/particle_presets.py::_send_raw` 已加
  防丢单：超时后查 processed 标志，仍 false 则重顶 mtime 再等一轮（不重写内容、无重复执行风险）。
- **【P4 新增】Python 拼 JSX 字符串时，语句之间不能用逗号 join**（逗号不是语句分隔符，
  报 ReferenceError）；多个 try 块直接无分隔符拼接。
- **【P4 新增】textFXMaster 只认 layerIndex 不认 layerName**；按名定位需先经 JSX
  查索引（见 `StylePresetEngine.resolve_layer_index`）。附加式 JSX 的返回函数名是
  buildSuccess/buildError，历史脚本误用 buildSuccessResponse 的需补别名。
- **【P5 新增】表达式赋值不抛语法错误**：`prop.expression = "坏表达式"` 本身不报错，
  错误只在求值时出现 → 预检必须试设后强制求值（读 `prop.value`）再读
  `prop.expressionError` 才能抓到 SyntaxError/运行时错误（AE 错误消息含行号与 ▶ 代码指针）。
- **【P5 新增】表达式预检防脏状态配方**（`core/fx/expression_preflight.py` 已实现）：
  备份原表达式 → 试设 → 强制求值 → **无论成败一律恢复原表达式**；先查
  `propertyType===PropertyType.PROPERTY` 与 `canSetExpression` 再试设（组属性赋值会抛异常）。
  属性路径按段 resolve（`p.property(seg)` 同时认 name/matchName），失败时返回
  结构化 `{comp, layer, property, error_type, message}`。
- **【P5 新增】`_send_raw` 返回契约**：直接返回解包后的 dict（无 result 包装层），
  传输失败时为 `{"status":"error","message":...}`；调用方不要再 `res["result"]`。

## 4. 产物校验

- **不能只看文件大小**：5s/1080p 黑底 h264 渲染物只有 ~25KB，会被 100KB 阈值误杀。
  以 ffprobe 实测为准：`duration >= 1s 且 width > 0` 即有效。
- 判断"黑屏"用 `ffmpeg -i x.mp4 -vf signalstats -f null -`，看 `YAVG`。
  **limited range 下纯黑 YAVG=16（不是0）**，黑屏阈值用 YAVG<20。
  饱和度/色温倾向看 UAVG/VAVG 偏移。
- **signalstats 数值可能是整数**：纯黑/纯色内容 YAVG 输出 `16` 而非 `16.000`，
  解析正则必须用 `=(\d+(?:\.\d+)?)` 而非 `=(\d+\.\d+)`，否则纯黑样本测不到值。
- 纯黑视频 signalstats YAVG=16（非0），但 OpenCV 亮度<10 判黑；两套阈值都安全。
- freezedetect 冻结持续到视频结尾时**只输出 freeze_start 不输出 freeze_duration**，
  静帧检测需补未闭合段：按 start 到视频末尾计冻结时长。
- **【P4 新增】粒子存在性度量**：`-vf tblend=all_mode=difference,signalstats` 读帧间差
  YAVG（静帧=0，粒子≥0.8，多层粒子实测 19.6）；**辉光占比**：
  `-vf geq='if(gt(lum(X,Y),200),255,0)',signalstats` 读 YAVG/255 = 亮像素占比。
  两者已接入 evaluator `_measure_video_stats`（temporal_diff/bright_ratio）与
  particle_presence/glow_ratio_min 断言。

## 5. 环境与工具链

- Python 全路径：`C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`（不在 PATH）。
- ffmpeg/ffprobe：`C:\ffmpeg\bin\`。
- 模块导入测试需 `sys.path.insert(0, 项目根)`。
- **Bash 工具的 PowerShell 会剥离 `$` 变量**：内联命令中 `$var` 会消失。
  长命令写 `.ps1` 文件执行，短命令用纯字面量路径，分隔符用 `;` 不用 `&&`。
- AE 与 listener 需保持已加载运行状态；重启 AE 后需重新经菜单加载两个 jsx。
- **【2026-08-11 新增】Startup 自动加载方案（v4 延迟加载）**：
  - **崩溃根因**：在 `Scripts/Startup/` 中直接 `eval()` 1460 行 listener 代码，此时 AE
    的 `app`/`scheduleTask`/文件 I/O 尚未完全初始化 → AE 启动崩溃。
  - **v4 方案**：Startup 脚本只做 `app.scheduleTask(code, 5000, false)`，5 秒后 AE 完全
    就绪再 eval listener → 不崩溃，自动加载 + 自动轮询。
  - **文件位置**：
    - Startup 脚本：`C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\Startup\z_mcp_bridge_startup.jsx`
    - 源文件：`tmp/z_mcp_bridge_startup_v4.jsx`
    - 安装脚本：`tmp/install_startup.bat`（需管理员权限）
  - **验证结果**：AE 重启后 Bridge 自动可用（ping 响应 + 创建合成成功），无需手动加载。
  - **注意**：如果 Startup 脚本被删除/覆盖，需重新运行 `tmp/install_startup.bat` 安装。
- **【2026-08-11 新增】严禁强制杀 AE 进程**：`Stop-Process -Force` 或 `taskkill /F`
  会导致 AE 下次启动时弹出"崩溃修复选项"对话框，用户误以为功能崩溃。
  正确关闭方式：通过 AE UI 正常退出（Alt+F4），或用 Bridge 发送 `app.quit()`。
  本项目中 Agent 已多次因此导致用户误判，必须杜绝。
  - **【2026-09-13 违反代价实录】** 本轮又 force-kill 两次，完整走了一遍后果链：
    force-kill → 下次启动弹"崩溃修复选项" → 若进**安全模式** → 第三方增效工具被禁用
    （Sapphire 冲击配方全失效），且**实测把 `Pref_SCRIPTING_FILE_NETWORK_SECURITY` 置 0**
    → listener 无法写 json（报"权限被拒绝…是否启用了'首选项>脚本和表达式>允许脚本写入文件和访问网络'"）
    → **桥接全断**，且表现是 send_bridge 静默超时（不报错），极易误判成"AE 挂了/脚本有问题"。
    **正确处置**：该对话框必须点「**继续**」，不要点「以安全模式启动」。
- **【2026-09-13 新增】AE 启动卡住的判据是内存，不是时间**：启动期间若内存**静止在约 213-222MB**，
  就是卡在模态对话框（本轮实测连发 10 次全局回车无效 —— 因为 AE 不是前台窗口，全局按键送到了别的进程）；
  越过弹窗后内存会涨到 2GB 以上。别用"等了多久"判断，用内存增量判断。
  弹窗只能走 UI 关：本机 UIA 能读到该对话框的按钮，`AXPress` 有效；
  但 `mouse_move` 需先 `screenshot` 建立 frame，否则报 "no actionable frame available"。
- **【2026-09-13 新增】`Pref_SCRIPTING_FILE_NETWORK_SECURITY` 的位置与修改纪律**：
  `%APPDATA%\Adobe\After Effects\25.3\Adobe After Effects 25.3 设置.txt`（UTF-8），
  键在 `[Extendscript]` 段，**`"1"` 才是正确状态**（本文档早前记录一致）。
  **必须在 AE 退出后**才能改 —— AE 退出时会回写首选项，运行中改会被覆盖。改前留 `.bak-*` 备份。
- **【2026-09-13 新增】正常启动链路：不要手工点菜单**。`Scripts/Startup/z_mcp_bridge_startup.jsx`
  （v4 延迟 5 秒方案）仍在位，**普通启动 `AfterFX.exe` 即可**，约 5 秒后自动 `Polling started OK`（本轮实测生效）。
  注意启动日志里可能出现**两次** "AE MCP Auto Listener started" —— 这是本文档记录的既有双轮询冲突
  （`mcp_bridge_panel.jsx` 二次 eval 同一 listener），与当轮改动无关。
- **【P5 新增】Bridge 下发的 JSX 里禁止 alert()/模态操作**：ExtendScript 单线程，
  alert 会冻结整个轮询循环，表现为命令写入后永不应答（日志停在 "Executing" 无 Success）。
  恢复只能走 AE UI：关闭挂起对话框 → 菜单 文件 > 脚本 > 运行脚本文件 重新执行
  `ae_mcp_auto_listener.jsx` + `start_mcp_listener.jsx`（命令行注入无效，见记忆）。
  AE 自绘保存确认框无 UIA 按钮，需向对话框句柄发 WM_CHAR 助记符（如 'D' = 不保存）。
- **【2026-08-11 新增】adobe-mcp 库的 COM 自动化在本机不可用**：
  - AE 2025 / PR 2025 的 COM 类未注册（`REGDB_E_CLASSNOTREG`），`New-Object -ComObject`
    对 AE/PR 全部失败。PS 的 COM 对象可创建但功能受限。
  - `adobe_mcp_adapter.py` 的实际执行路径仍是旧 Bridge 文件轮询（写 ae_command.json →
    等轮询 → 读 ae_result.json），不是真正的 COM 直连。
  - 当前唯一可靠的 AE 控制通道：Bridge 文件轮询（ae_mcp_auto_listener.jsx）。
- **【2026-08-11 新增】Bridge 发送端文件锁重试**：`os.replace(tmp, cmd_file)` 可能因
  listener 正在读文件而抛 `PermissionError`。必须在 `os.replace` 外层加重试循环
  （`for retry in range(10): try os.replace; except PermissionError: sleep(0.3)`）。

## 6. 进化闭环相关

- LLM 不可用（api_key 空）→ Rubrics 通道禁用（`--no-rubrics`），语义评分用确定性测量替代。
- 进化验证用隔离目录：`tmp/run_ae_evolution.ps1`（复制 benchmark 到 `%TEMP%` 目录跑）。
- 历史黑屏根因链：activeItem 劫持 → 图层没进合成 → 25KB 黑帧 → VQA 启发式恒 59.2 →
  分数恒定 82.6 → Optimizer 阈值(均分<70)不触发 → 零提案。修复顺序：内容真实 → 评分梯度 → 归因提案。
- 【P3 验收结果 2026-08】内容修复后真实进化 2 轮×3 题：分数 97.5/87.5/82.5（区分度 std≈6.2，
  不再是恒定 82.6）；VQA 实测 83.4；黑屏产物被 evaluator 判 0 分、VQA 封顶 15；
  Optimizer 已消费 style_match_detail.failures 产出归因提案。
- 【P4 验收结果 2026-08】粒子特效×文字动画管线全部真机验证 PASS：
  - P4-A `ae_additive_scripts/particleFXMaster.jsx`（7 粒子类型/三层叠加/beat 爆发/氛围雾）
    + `core/fx/particle_presets.py`，真实渲染非黑屏（YAVG 实测有内容）
  - P4-B `ae_additive_scripts/textImpactMaster.jsx`（impact/beat_sync/rgb_glitch）
    + `core/fx/text_impact.py`，渲染 5s/720p 产物 YAVG=35.2 PASS
  - P4-C `data/style_templates/templates.json`（6 风格：高燃/赛博朋克/霓虹/故障/水墨/电影感）
    + `core/fx/style_preset_engine.py`，cyberpunk 端到端 4/4 步骤成功，渲染 SATAVG=47.9/U>V 偏冷
  - P4-D evaluator 新增 temporal_diff/bright_ratio 实测 + particle_presence/glow_ratio_min
    断言（粒子 1.2/风格 19.6/静帧 0.0 区分度清晰）；train benchmark 扩至 12 题
  - 回归 50 passed, 1 skipped
- 【P5 验收结果 2026-08】表达式预检闸门真机 5/5 PASS：
  `core/fx/expression_preflight.py`（generate/preflight_expression/apply_expression/ExpressionGate），
  正常写入+读回一致、语法错误阻断（抓到 AE 行号级报错）、属性缺失捕获、
  组属性不可设捕获、预检失败后原表达式零改动（无脏状态）；回归 50 passed, 1 skipped

---

## 7. 混合管线 Stage B 新增踩坑（2026-08-05，resolve_ae_resolve_pipeline.py）

1. **【暗屏决定性根因】`app.project.items.addComp(name,width,height,pixelAspect,duration,frameRate)`：
   第4参数是像素宽高比，正方形像素必须传 1.0**。误传 fps（如 24）→ PAR=24 →
   画面水平压缩 24 倍（1920/24=80px 中央细竖条+近黑，YAVG≈19-25，切点检出 0），
   且图层诊断/ffprobe 全部正常，极难肉眼定位。
2. **诊断利器 `comp.saveFrameToPng(time, file)`**（AE 24+，**time 在前 File 在后**，
   传反报"File 不是数字"）：绕开渲染队列/输出模块直接导出引擎内帧；
   配合读 `comp.pixelAspect`（应为 1）可秒定位 PAR 类问题。
3. **ExtendScript 部分类名不可用于 instanceof**：`FootageSource` 未定义
   （ReferenceError），`CompItem`/`TextLayer`/`AVLayer` 可用；不确定的一律
   用 try/catch 包属性访问。
4. **Bridge 命令偶发丢失**：ping 正常但紧随的 JSX 命令 `processed` 恒为 None
   （轮询链存活却跳过）。对策：超时后 ping 探活再重发同一命令
   （输出路径带 uuid 时重发无副作用）。
5. **QuickTime 输出扩展名自动改写**（AE 25.3）：请求 .mov 实际写出 .mp4，
   产物探测必须多扩展名候选；QuickTime 容器实际写出 H.264。
6. **工程卫生**：每次运行的合成名带 uuid 后缀，渲染完成后 JSX 内
   `rqi.remove();c.remove();ft.remove();` 即建即销，防 numItems 无限堆积
   （实测一轮事故后涨到 136+）。
7. **验证纪律**：抽帧 AI 描述/肉眼判断不可信（本轮多次幻觉出不存在的文字），
   一律用客观像素统计：PIL/numpy 行列亮度分布、signalstats YAVG、scene 切点计数。
8. **渲染前清空渲染队列**（历史残留项会被 `rq.render()` 一并渲掉污染输出）：
   `for(var qi=app.project.renderQueue.numItems;qi>=1;qi--){...item(qi).remove();}`。

---
*创建：P3 阶段（黑屏修复）期间。每次 AE 相关任务完成后请回写新条目。*

---

## 8. 进化第二轮新增踩坑（2026-08-05，文字密度/饱和度/节拍优化迭代）

1. **AE 多文字图层 JSX 拼接注意变量唯一性**：每个文字图层必须用
   `tt0/tt1/...` 和 `td0/td1/...` 独立变量名，不能复用同一变量。
   实测 9 个文字图层 + 1 个标题 + 1 个副标题 = 11 个文字图层，
   AE 渲染正常，耗时约 10 分钟（含一次命令丢失重发）。
2. **JSX 字符串中的花括号转义陷阱**：Python 普通字符串（非 f-string）中
   `{{` 是两个字面 `{`，不是转义。只有 f-string 中 `{{` 才产生单个 `{`。
   混用 f-string 和普通字符串拼接 JSX 时必须格外小心。
3. **AE 渲染耗时随文字图层数线性增长**：1 个标题约 60s，9 个文字图层
   约 600s。后续优化可考虑减少文字数或合并为单个表达式控制图层。

---

## 9. 深度研究：ExtendScript 自动化运动曲线与关键帧生成（2026-08-05）

### 9.1 结论：**关键帧自动化完全可以在 ExtendScript 中解决**

ExtendScript 提供了完整的关键帧插值 API，可以实现从简单淡入淡出到复杂弹性运动的
全部动画效果。瓶颈不在 API 能力，而在实现复杂度。

### 9.2 关键帧插值 API 完整能力边界

**A. 插值类型控制（已实测验证）**：
- `keyframe.setInterpolationTypeAtKey(k, inType, outType)` — 设置入/出插值
  - `KeyframeInterpolationType.LINEAR` — 线性（匀速）
  - `KeyframeInterpolationType.BEZIER` — 贝塞尔（平滑加减速）
  - `KeyframeInterpolationType.HOLD` — 保持（突变）
- 适用属性：所有可动画属性（Position/Scale/Rotation/Opacity 等）

**B. 贝塞尔曲线手柄控制（已实测验证）**：
- `keyframe.setSpatialTangentAtKey(k, [dx,dy,dz])` — 空间切线（仅 Position 等空间属性）
- `keyframe.setTemporalEaseAtKey(k, [inEase, outEase])` — 时间缓动值
- `property.setTemporalAutoBezierAtKey(k, true)` — 自动贝塞尔（AE 自动平滑手柄）
- 实测：text_rotation 预设中 `setInterpolationTypeAtKey(k, BEZIER, BEZIER)` 已验证可用

**C. 表达式内置函数（已实测验证）**：
- `ease(t, tMin, tMax, val1, val2)` — 平滑 S 形缓动
- `easeIn(t, tMin, tMax, val1, val2)` — 缓入（慢启动）
- `easeOut(t, tMin, tMax, val1, val2)` — 缓出（慢停止）
- `loopOut("cycle"|"pingpong"|"offset")` — 循环动画（无限重复）
- 表达式赋值：`prop.expression = "ease(time, 0, 2, 0, 100)"` — 但注意
  表达式与手动关键帧互斥（同一属性不能同时有表达式和手动关键帧）

### 9.3 复杂运动路径实现方案

| 运动类型 | 实现方式 | 复杂度 |
|---------|---------|--------|
| 平滑加减速 | `setInterpolationTypeAtKey(BEZIER)` | 低 |
| 弹性回弹 | 表达式 `wiggle()` 或自定义弹簧函数 | 中 |
| 惯性滑动 | 贝塞尔手柄 + 时间缓动值调整 | 中 |
| 打字机效果 | 逐字符 opacity 关键帧 + 时间偏移 | 中 |
| 3D 翻转 | Y Rotation 关键帧 + threeDLayer=true | 低 |
| 物理弹跳 | 表达式 `value + Math.sin(time*freq)*amp*Math.exp(-time*decay)` | 高 |

### 9.4 实际限制与注意事项

1. **表达式 vs 手动关键帧互斥**：同一属性不能同时有 expression 和 setValueAtTime。
   方案选择：简单动画用关键帧，复杂循环/物理动画用表达式。
2. **空间切线仅适用于空间属性**：Position/Anchor Point 可用 setSpatialTangentAtKey，
   Scale/Rotation/Opacity 只能用 setTemporalEaseAtKey。
3. **性能上限**：数百个关键帧的 JSX 字符串拼接会导致 Bridge 传输变慢，
   建议单属性关键帧数不超过 50。
4. **枚举值不可用裸数字**：`KeyframeInterpolationType.BEZIER` 不能写成 `2`，
   否则报"无法转换"异常（与 BlendingMode/ParagraphJustification 同类踩坑）。

### 9.5 本项目已实现的动画类型（第三轮智能导演）

以下 6 种动画类型已在 `integrations/smart_director.py` 中通过 ExtendScript 关键帧实现：
1. **scale_bounce** — 缩放弹跳入场 + 缩小出场（参考 douyin_bounce_title）
2. **slide_left** — 左侧滑入 + 右侧滑出（参考 mg_animation slide）
3. **slide_right** — 右侧滑入 + 左侧滑出
4. **rotate_3d** — Y 轴 3D 旋转进出（参考 3d_effect.json → text_rotation）
5. **drop_top** — 顶部下落 + 底部下落（参考漫剪拉镜技法）
6. **fade_scale** — 渐显放大 + 渐隐缩小（大师知识库慢节奏技法）

每种均包含完整的"入场→展示→出场"生命周期，通过 setValuesAtTimes 实现
贝塞尔平滑过渡。

---

## 10. 全系统实战 smoke 新增踩坑（2026-09-24，ae_smoke_0924.py 真渲染验证通过）

1. **listener 两代协议分叉**（**已于 2026-09-24 晚统一修复**：ae_mcp_auto_listener.jsx::executeScript
改为双兑底——先按表达式 eval，遇 SyntaxError 自动包成函数体执行；PROTO_CHECK 实测两种风格全过，
客户端无需再适配）：根目录 `ae_mcp_auto_listener.jsx` 的 `executeScript` 用
`eval(scriptStr)` 执行——**不能带 `return` 前缀**（报 SyntaxError: 函数体外的非法 return）；
而 `AEBridgeLite.execute_jsx` 按新协议自动拼 `"return "+body`（适配 new Function 型 listener）。
两者不兼容。对策：对 eval 型 listener 直接 `_send({"command":"executeAtomScript",
"args":{"script":"(function(){...})()"}})` 发裸 IIFE（见 tmp/ae_smoke_0924.py::exec_raw）。
2. **Start 文件夹自动拉起不可靠**：AE 实机配置目录存在 2025/25.0/25.3 多版本并存，
Start 脚本放错版本目录则静默不执行且无任何报错。可靠注入方式：GUI
文件>脚本>运行脚本文件…手动执行 listener（非阻塞 setTimeout 轮询型），或先确认
最近 LastWriteTime 的版本目录再放 Start。
3. **渲染 API 是 `app.project.renderQueue.render()`**，RenderQueueItem 无 render() 方法
（报 ReferenceError: 函数 rqi.render 未定义）；与第 3 节原始结论一致，勿凭直觉改写。
4. **om.file 后缀不代表实际输出**：设 `.mov` + format=QuickTime，实际按输出模块模板
落盘为 `.mp4`；结果回传的 `om.file.fsName` 才是真实路径，校验应以它为准。
5. **杀 AE 进程重启不弹崩溃恢复框**（本实测），Responding=True + 主窗口标题正常
即可继续桥接；ping 往返 <1s。
6. 真执行链基准：ping 0s → listCompositions 1s → 建合成+2层 2s → 渲染 640x360x3s
QuickTime/H.264 共 6s，产物 34KB 经 ffprobe 验证 h264/3.0s。
7. **Startup 自动拉起正确姿势（2026-09-24 23:32 复验成功）**：唯一生效位置是
**程序级** `<AE>\Support Files\Scripts\Startup\`（需提权写入）；正本 loader 为
`.ae-mcp-bridge/z_mcp_bridge_startup.jsx`（v5：延迟 3s + read/eval 兜底，$.evalFile 本机不可用）。
用户级 `%APPDATA%\...\Config\Scripts\Start\` 目录 AE 根本不读（静默无效）；
用户级 `Scripts\Startup` 未验证且与程序级双部署会造成 listener 双实例轮询竞争，禁止双部。
8. **AE 冷启动可能超过 100 秒**：进程存活但 RAM ~200MB、无窗口是正常早期阶段，
勿误判为卡死而强杀（铁律：关 AE 用正常退出，禁 Stop-Process -Force，防配置损坏）。
9. `CLOSE_PROJECT_DO_NOT_SAVE_CHANGES` 枚举在 executeAtomScript 上下文未定义（ReferenceError）；
关工程需先查证正确枚举值或用 app.project 其它 API。
7. **Startup 自动拉起正确姿势（2026-09-24 23:32 复验成功）**：唯一生效位置是
**程序级** `<AE>\Support Files\Scripts\Startup\`（需提权写入）；正本 loader 为
`.ae-mcp-bridge/z_mcp_bridge_startup.jsx`（v5：延迟 3s + read/eval 兜底，$.evalFile 本机不可用）。
用户级 `%APPDATA%\...\Config\Scripts\Start\` 目录 AE 根本不读（静默无效）；
用户级 `Scripts\Startup` 未验证且与程序级双部署会造成 listener 双实例轮询竞争，禁止双部。
8. **AE 冷启动可能超过 100 秒**：进程存活但 RAM ~200MB、无窗口是正常早期阶段，
勿误判为卡死而强杀（铁律：关 AE 用正常退出，禁 Stop-Process -Force，防配置损坏）。
9. `CLOSE_PROJECT_DO_NOT_SAVE_CHANGES` 枚举在 executeAtomScript 上下文未定义（ReferenceError）；
关工程需先查证正确枚举值或用 app.project 其它 API。
