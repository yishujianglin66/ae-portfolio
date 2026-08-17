# AE Bridge 避坑指南

> ⚠️⚠️ **重要纠正（2026-07-29）**：本文档部分结论已被实证推翻，**请勿再据其放弃 Bridge**。
> 7/27–7/29 会话证实：**Bridge 文件协议全程可靠**（含 98.3s 生产渲染零失败、无配额限制），Startup + scheduleTask **从未失效**。
> 被推翻的结论：「Bridge 不可靠/配额 1–2 条」（§一、§2.3）、「主通道=ComputerUse」（§2.4）、「脚本末尾加 alert() 作证据」（§2.4，alert 会阻塞管线）。
> 退化真因 = `Pref_SCRIPTING_FILE_NETWORK_SECURITY` 被置 0 + MCP build 指向错误 bridge 目录。
> **请以 [[2026-07-29_执行管线经验沉淀与检查清单]] 为准**，本文仅作历史参考。
> 最新实证结论、失败点与对策详见 `docs/ae_bridge_lessons.md`（AE Bridge 开发踩坑档案，涉 Bridge/JSX 执行前必读）。

> 最后更新：2026-07-28  
> 来源：项目记忆 + 多轮实战会话沉淀  
> 适用范围：所有需要与 AE 进行自动化通信的场景

---

## 一、AE 脚本执行通道决策树

```
需要在AE中执行JSX脚本？
│
├─ 首次执行/批量执行（推荐）
│   └─ 【主通道】ComputerUse UI自动化
│       文件(F) → 脚本 → 运行脚本文件... → 选择.jsx
│       ✅ 无配额限制、无轮询依赖、100%可靠
│
├─ Bridge存活时（偶尔可用）
│   └─ 【备用通道】文件协议（限1-2条命令/会话）
│       写入 ae_command.json → 等待 ae_result.json
│       ⚠️ 首次命令5秒未消费 → 立即放弃
│
└─ 禁止使用
    ✗ AfterFX.exe -r script.jsx（AE已运行时完全无效）
    ✗ COM接口 AfterEffects.Application（未注册）
    ✗ AdobeMCP adobe_run_jsx（依赖COM，100%失败）
```

---

## 二、问题-解决方案速查表

### 2.1 Bridge 双协议竞争

| 项目 | 内容 |
|------|------|
| **问题描述** | 向 `ae_command.json` 写入命令后永远不被消费 |
| **根因** | 系统存在两套不兼容的Bridge协议同时运行 |
| **正确做法** | 统一使用**一套**协议，且仅作为备用通道 |
| **错误做法（禁止）** | 同时部署headless和panel版bridge；在bridge等待期间让MCP服务器写入ping |
| **来源** | memory: `ba9ffb26` (AE Bridge双协议竞争) |

**两套协议对比：**

| 特征 | 项目内 headless 版 | 开源 panel 版 (Documents) |
|------|-------------------|--------------------------|
| 路径 | `.ae-mcp-bridge/ae_command.json` | `C:\Users\Administrator\Documents\ae-mcp-bridge\ae_command.json` |
| 触发字段 | `"processed": false` | `"status": "pending"` |
| 支持命令 | ping, getProjectInfo, **runScript**, extractActiveComp, openProject, closeProject, runExtraction, executeAtomScript | createComposition, createSolidLayer, **applyEffect**, listEffects, bridgeTestEffects 等24个固定命令 |
| 启动方式 | Startup脚本 `$.evalFile` | ScriptUI Panels 文件夹面板 |
| 可靠性 | Startup上下文中scheduleTask**完全不可用**→轮询立即死亡 | 面板onShow事件启动→但每次会话仅1-2条命令配额 |

**唯一可靠路径模板（headless版，当bridge恰好存活时）：**
```json
{"command":"runScript","args":{"file":"C:/Users/Administrator/Desktop/AE-Knowledge-Vault/temp/my_script.jsx"},"processed":false,"timestamp":"1785215775175"}
```

**唯一可靠路径模板（panel版，需手动触发Check按钮）：**
```json
{"command":"applyEffect","args":{"compIndex":1,"layerIndex":1,"effectMatchName":"ADBE Glo2"},"timestamp":"2026-07-28T13:35:01.000Z","status":"pending"}
```

---

### 2.2 executeAtomScript 命令不可用

| 项目 | 内容 |
|------|------|
| **问题描述** | 调用 `executeAtomScript` 返回 `"Unknown command"` |
| **根因** | 安装版 mcp-bridge-auto.jsx（ScriptUI Panels文件夹）不包含该命令；仅源码build版有 |
| **正确做法** | headless版用 `runScript(file=...)`；panel版用 `applyEffect`/`createComposition` 等已注册命令 |
| **错误做法（禁止）** | 向panel版bridge发送 `executeAtomScript`/`execute_script` |
| **来源** | memory: `89f8111c` (executeAtomScript不可用) |

**panel版已验证可用命令清单：**
```
getProjectInfo, listCompositions, getLayerInfo,
createComposition, createTextLayer, createShapeLayer, createSolidLayer,
setLayerProperties, setLayerKeyframe, setLayerExpression,
applyEffect, applyEffectTemplate, bridgeTestEffects,
createCamera, batchSetLayerProperties, setCompositionProperties,
duplicateLayer, deleteLayer, setLayerMask,
listEffects, applyPreset, e3dLoadModel,
particularEmitter, fixParticular, diagParticular
```

---

### 2.3 Bridge 轮询停止后的恢复

| 项目 | 内容 |
|------|------|
| **问题描述** | Bridge面板已打开但命令不被消费，日志无新条目 |
| **根因** | `app.scheduleTask` 在AE空闲后自动停止；每次会话仅可靠处理1-2条命令 |
| **正确做法** | 见下方恢复流程（4步） |
| **错误做法（禁止）** | 反复写入命令等待消费；用 `-r` 标志尝试重启轮询 |
| **来源** | memory: `05aa4079` (Bridge会话命令配额限制) |

**恢复流程（仅在必须使用Bridge时）：**
```powershell
# Step 1: 清空残留命令（防毒杀）
Remove-Item ".ae-mcp-bridge\ae_command.json" -ErrorAction SilentlyContinue
Remove-Item ".ae-mcp-bridge\ae_result.json" -ErrorAction SilentlyContinue

# Step 2: 关闭AE（注意：强杀有首选项损坏风险）
$p = Get-Process AfterFX -ErrorAction SilentlyContinue
if($p){Stop-Process -Id $p.Id -Force; Start-Sleep -Seconds 5}

# Step 3: 带项目参数启动（绕过Home Screen阻塞）
Start-Process "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe" `
  -ArgumentList '"C:\path\to\project.aep"'

# Step 4: 等待≥90秒，确认MainWindowTitle非空
Start-Sleep -Seconds 90
$ae = Get-Process AfterFX
if ($ae.MainWindowTitle -ne "") { Write-Host "AE Ready" }
```

**三大致命模式（必须规避）：**
1. **残留命令毒杀**：AE启动时自动消费残留ae_command.json → 若指向坏脚本 → bridge崩溃
2. **Home Screen阻塞**：prefs为空/损坏 → AE显示Home Screen → MainWindowTitle为空 → bridge完全不响应
3. **ping浪费配额**：MCP服务器health check写入ping → 占用1条配额 → 关键命令无法执行

---

### 2.4 主通道：ComputerUse 全自动脚本执行

| 项目 | 内容 |
|------|------|
| **问题描述** | 需要可靠地在AE中执行任意JSX脚本 |
| **根因** | Bridge不可靠（配额限制+轮询死亡），COM接口未注册 |
| **正确做法** | ComputerUse操作AE菜单：文件→脚本→运行脚本文件 |
| **错误做法（禁止）** | 依赖bridge轮询；使用-r启动参数（AE已运行时无效） |
| **来源** | memory: `578d1f75` (AE全自动脚本执行) |

**完整流程：**
```
1. 确保AE运行（带项目参数启动，等待90s）
2. 将JSX脚本写入 temp/ 目录
3. 脚本末尾添加 alert() 作为执行证据
4. 脚本将结果写入 JSON 文件（双保险）
5. ComputerUse: 文件(F) → 脚本 → 运行脚本文件... → 选择.jsx → 打开
6. 读取结果JSON确认执行状态
```

**脚本模板：**
```javascript
#target aftereffects
(function() {
    var RESULT_FILE = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/temp/result.json";
    var results = {};
    try {
        // ... 业务逻辑 ...
        results.status = "success";
    } catch(e) {
        results.status = "error";
        results.error = e.message + " (line " + e.line + ")";
    }
    var f = new File(RESULT_FILE);
    f.encoding = "UTF-8"; f.open("w");
    f.write(JSON.stringify(results, null, 2)); f.close();
    alert("Done: " + results.status);
})();
```

---

### 2.5 PowerShell 输出重定向编码

| 项目 | 内容 |
|------|------|
| **问题描述** | `python script.py > output.txt` 产生UTF-16文件，grep/Read工具无法正确解析 |
| **根因** | PowerShell `>` 重定向默认使用UTF-16LE编码（字符间有\x00） |
| **正确做法** | 用 `Out-File -Encoding UTF8` 或 `[System.IO.File]::WriteAllText()` |
| **错误做法（禁止）** | 直接用 `>` 重定向后尝试按UTF-8读取 |
| **来源** | 会话 75a3d3a6 (2026-07-28) |

**正确模板：**
```powershell
# 方案A：Out-File指定编码
python script.py 2>&1 | Out-File -FilePath temp\output.txt -Encoding UTF8

# 方案B：Python内部写文件（最可靠）
python -X utf8 -c "import subprocess; r=subprocess.run([...],capture_output=True,text=True); open('temp/out.txt','w',encoding='utf-8').write(r.stdout+r.stderr)"

# 方案C：读取时指定编码
Get-Content temp\output.txt -Encoding UTF8
```

---

### 2.6 长时间训练任务的非阻塞等待

| 项目 | 内容 |
|------|------|
| **问题描述** | 训练进程运行30-120分钟，反复GetTerminalOutput/Get-Process轮询触发死循环检测 |
| **根因** | 纯NumPy训练（512×3层×7600样本×300epochs）CPU密集，stdout被缓冲直到进程结束 |
| **正确做法** | 后台启动 → 单次长等待 → 进程结束后一次性读取输出 |
| **错误做法（禁止）** | 每30秒交替调用GetTerminalOutput和Get-Process（触发ALTERNATING LOOP DETECTED） |
| **来源** | 会话 75a3d3a6 (2026-07-28) |

**正确模式：**
```powershell
# 启动（后台）
Start-Process python -ArgumentList "-X utf8 models/train.py --epochs 300" `
  -RedirectStandardOutput temp\train_out.txt -RedirectStandardError temp\train_err.txt `
  -NoNewWindow -Wait

# 或者：后台启动 + 一次性等待完成
python -X utf8 models/train.py > temp\train_out.txt 2>&1  # is_background=true
# 然后仅调用一次 GetTerminalOutput(wait_seconds=180) 等待完成信号
# 完成后一次性读取: Get-Content temp\train_out.txt -Encoding UTF8
```

**禁止模式：**
```
❌ GetTerminalOutput → Get-Process → GetTerminalOutput → Get-Process → ...（循环）
❌ 每30秒检查一次进程状态（超过3次触发死循环检测）
```

---

### 2.7 AE 首选项损坏修复

| 项目 | 内容 |
|------|------|
| **问题描述** | 强杀AE后启动弹出"访问首选项文件时出错" |
| **根因** | Stop-Process -Force 导致 NTFS 权限异常 |
| **正确做法** | 运行 `fix_ae_prefs.bat`（workspace根目录） |
| **错误做法（禁止）** | 手动删除prefs目录；忽略警告继续操作 |
| **来源** | memory: `969b028b` (强杀AE致首选项损坏) |

---

### 2.8 AE 渲染“覆盖已存在文件”模态弹窗阻塞自动化（★最高频）

| 项目 | 内容 |
|------|------|
| **问题描述** | 渲染时弹出“所选输出模块将覆盖已存在的文件。要允许此操作，请按‘确定’”，不点确定就永久卡死（无超时、无后台继续），阻塞一切自动化 |
| **根因** | ①渲染脚本用固定输出文件名，重渲染必撞旧文件；②AE会静默更改输出扩展名（设.png实际输出.mp4），只删精确路径无效；③干扰MCP进程复活后重执行旧渲染命令，意外触发弹窗 |
| **正确做法** | 渲染前调用 `deleteExistingOutputs()`，按基础文件名删除所有扩展名的同名旧输出 |
| **错误做法（禁止）** | 直接 `om.file=new File(path)` 后渲染不清理；只删精确扩展名路径 |
| **来源** | 会话 2026-07-29（shadow诊断中反复被卡7分钟） |

**标准防护代码（所有渲染脚本必须内置，在 `om.file=` 之前调用）：**
```javascript
// 按基础文件名删除所有扩展名的同名旧输出，永久防止覆盖弹窗
function deleteExistingOutputs(outPath) {
  try {
    var f = new File(outPath);
    var base = f.name.replace(/\.[^.]+$/, "");
    var matches = f.parent.getFiles(base + ".*");
    for (var i = 0; i < matches.length; i++) {
      try { if (matches[i] instanceof File) matches[i].remove(); } catch(ed) {}
    }
  } catch(eAll) {}
}
```

**已固化该防护的脚本：** `temp/diag7_camera_design.jsx`、`temp/phase3_render_pass3.jsx`、`temp/diag3_render_test.jsx`、`temp/diag6_confirm.jsx`、`temp/levi_phase4_render.jsx`、`temp/levi_phase3_render_v3.jsx`、`temp/levi_phase3_render.jsx`

**配套措施：** 干扰进程（`node after-effects-mcp-main/build/index.js`、`python ae_tools_mcp_server.py`）会在会话间复活并争写 `ae_command.json`、重执行旧命令，**每次会话开始必须检查并 Stop-Process 停掉**。

---

### 2.9 3D文字摄像机居中 + 地板/阴影三大根因（★td_shadow_drama黑屏出画实锤）

| 项目 | 内容 |
|------|------|
| **问题描述** | 3D文字预设渲染黑屏/文字出画/地板阴影不可见 |
| **根因** | ①摄像机用X/Y Rotation居中无效（双节点POI相机）；②地板被2D背景遮挡；③阴影matchName写错+光源位置不对 |
| **正确做法** | 见下方三大SOP |
| **错误做法（禁止）** | 用 `cam.property('X Rotation')`/`autoOrient` 居中；`floor.moveToEnd()`；用 `ADBE Shadow Darkness` |
| **来源** | 会话 2026-07-29（diag8~diag15实证，修复固化于 `temp/gen_phase3_v4.js`） |

**SOP① 摄像机居中（双节点POI相机陷阱）：**
`layers.addCamera()` 创建双节点相机，`autoOrient=NO_AUTO_ORIENT`(4212) **不能**移除 Point of Interest，POI主导朝向→X/Y Rotation被忽略。旧方案 rotX=-8 + 默认zoom=2666.67(长焦) 把文字推出顶边。唯一可靠居中：
```javascript
// 文字世界视觉中心 = 控制null Position + sourceRect中心偏移(必须实测,不能假设)
var sr = L.sourceRectAtTime(dur*0.5, false);
var cx = ctrlPos[0] + sr.left + sr.width/2, cy = ctrlPos[1] + sr.top + sr.height/2;
cam.property('Position').setValue([cx, cy, -1600]);
cam.property('Point of Interest').setValue([cx, cy, 0]);   // ← 关键
cam.property('ADBE Camera Options Group').property('ADBE Camera Zoom').setValue(1500);  // ← 必须显式广角,禁用默认2667长焦
```
验证标准：文字center偏移<10px（实测t50=+2.1/-4.0）。drift表达式只加在Position（POI固定时只产生视差不丢居中）。

**SOP② 地板可见（2D切断3D渲染）：**
2D图层夹在3D图层之间会分割3D渲染，其下方3D图层渲染在它后面。`ShadowFloor`(3D)被`moveToEnd()`压到`BG_Grad`(2D不透明)下方→完全遮挡。修复：`floor.moveBefore(bgGrad)`（实测下部亮像素0%→74%）。

**SOP③ 阴影可见（matchName+光源几何）：**
```javascript
// 正确matchName(错误名返回null被try/catch静默吞掉,参数从未生效):
olOpts.property('ADBE Light Shadow Darkness').setValue(85);   // ≠ ADBE Shadow Darkness(错)
olOpts.property('ADBE Light Shadow Diffusion').setValue(35);   // ≠ ADBE Shadow Diffusion(错)
// 光源放文字正上方,阴影垂直落到可见地板(放上方偏前会投到地板远端外):
orbitLight.property('Position').setValue([cx, cy-330, -350]);
// 轨道光振幅宜小(±150/±60/±40),过大(±360)阴影甩出地板
```
诊断法：PIL+numpy，`lum=img.max(axis=2)`，地板阈值>40看下部波段，文字阈值>100看centroid。

---

## 三、命令格式速查

### 3.1 项目内Bridge（headless版，备用）

```json
// 执行JSX文件（最常用）
{"command":"runScript","args":{"file":"C:/absolute/path/script.jsx"},"processed":false,"timestamp":"毫秒时间戳"}

// 内联代码
{"command":"runScript","args":{"code":"app.project.name"},"processed":false,"timestamp":"毫秒时间戳"}

// 结果读取
// .ae-mcp-bridge/ae_result.json
{"command":"runScript","status":"success","result":{"success":true,"result":"返回值"},"timestamp":"ISO时间"}
```

### 3.2 开源Panel版（Documents路径，需手动触发）

```json
// 创建合成
{"command":"createComposition","args":{"name":"Test","width":1920,"height":1080,"duration":10,"frameRate":30},"timestamp":"ISO时间","status":"pending"}

// 应用效果
{"command":"applyEffect","args":{"compIndex":1,"layerIndex":1,"effectMatchName":"ADBE Glo2"},"timestamp":"ISO时间","status":"pending"}

// 结果读取
// C:\Users\Administrator\Documents\ae-mcp-bridge\ae_mcp_result.json
```

### 3.3 AE2025实机验证matchName清单

**✅ 已验证可用（38种）：**
```
// 色彩校正类
ADBE Lumetri, ADBE CurvesCustom, ADBE Pro Levels, ADBE Easy Levels,
ADBE Color Balance (HLS), ADBE Tint, ADBE Vibrance,
ADBE HUE SATURATION, ADBE Brightness & Contrast 2,
ADBE Exposure2, ADBE PhotoFilterPS,
// 模糊/扭曲类
ADBE Gaussian Blur 2, ADBE Turbulent Displace, ADBE Wave Warp,
ADBE Channel Blur, ADBE Camera Lens Blur, ADBE Bulge,
// 生成/风格化类
ADBE Fractal Noise, ADBE Mosaic, ADBE Roughen Edges,
ADBE Noise2, ADBE Ramp, ADBE Solid Composite,
// 通道/键控类
ADBE Shift Channels, ADBE Set Channels, ADBE Invert,
ADBE Extract, ADBE Color Key,
// 时间/转场类
ADBE Echo, ADBE Time Displacement, ADBE Posterize Time,
ADBE Linear Wipe, ADBE Radial Wipe,
// 3D/透视类
ADBE Basic 3D, ADBE FreePin3,
// 音频类
ADBE AudSpect,
// 发光类
ADBE Glo2
```

**❌ AE2025中不可用（已弃用/改名）：**
```
ADBE Curves          → 改用 ADBE CurvesCustom
ADBE Levels          → 改用 ADBE Pro Levels 或 ADBE Easy Levels
ADBE Levels (Individual Controls) → 改用 ADBE Pro Levels
ADBE Time Difference → 改用 ADBE Time Displacement
ADBE Linear Color Key → 改用 ADBE Color Key
```

---

## 四、诊断脚本模板（步骤标记法）

当JSX脚本执行失败但不知哪行出错时：

```javascript
// diagnose.jsx - 纯ASCII，无中文注释
#target aftereffects
var out = "DIAG:";
try {
    var comp = app.project.activeItem;
    out += "|comp=" + (comp ? comp.name : "null");
    
    var layer = comp.layer(1);
    out += "|layer=" + layer.name;
    
    var fx = layer.property("ADBE Effect Parade");
    out += "|fx=" + fx.numProperties;
    
    var eff = fx.addProperty("ADBE Glo2");
    out += "|eff=" + eff.matchName;
    
    out += "|ALL_OK";
} catch(e) {
    out += "|ERR:" + e.toString() + "|line:" + e.line;
}
out;
```

---

## 五、硬性规范总结

1. **Bridge不作为主执行通道**（已知不可靠，配额1-2条/会话）
2. **主通道 = ComputerUse + 脚本文件**（无限制、100%可靠）
3. **禁止使用 `-r` 标志**（AE已运行时完全无效）
4. **禁止使用 COM 接口**（未注册，100%失败）
5. **Bridge首次命令5秒未消费 → 立即放弃，不重试**
6. **启动AE必须带项目参数**（绕过Home Screen阻塞）
7. **等待AE加载 ≥ 90秒**（首次60s标题可能为空）
8. **发送Bridge命令前必须清空残留文件**（防毒杀）
9. **PowerShell重定向用 `Out-File -Encoding UTF8`**（禁止裸 `>`）
10. **长时间任务用后台执行 + 一次性读取**（禁止轮询循环）
11. **渲染前必须 `deleteExistingOutputs()` 清理同名旧输出**（否则“覆盖已存在文件”弹窗永久卡死自动化，见§2.8）
12. **每次会话开始必须停掉干扰MCP进程**（node after-effects-mcp / python ae_tools_mcp_server 会复活并争写命令文件，见§2.8）
13. **3D摄像机居中必须用 Point of Interest 对准文字视觉中心**（禁止用X/Y Rotation/autoOrient，双节点相机下无效，见§2.9 SOP①）
14. **3D地板必须 `moveBefore(2D背景)`**（moveToEnd会被2D背景遮挡，见§2.9 SOP②）；**阴影matchName用 `ADBE Light Shadow Darkness/Diffusion`**（见§2.9 SOP③）
15. **生成器/渲染脚本严禁 `alert()`**（modal永久阻塞无头自动化，结果一律写文件）；**`app.newProject()`前先`app.project.save()`**（否则弹“保存更改”对话框阻塞）
