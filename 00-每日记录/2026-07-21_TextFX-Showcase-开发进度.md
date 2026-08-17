# TextFX Showcase 文字特效展示视频 — 开发进度同步文档

**更新时间**: 2026-07-21  
**状态**: 构建成功 + 渲染黑屏待修复  
**优先级**: 🔴 高（下一步核心任务）

---

## 一、当前状态总结

| 维度 | 状态 | 说明 |
|------|------|------|
| JSX 构建脚本 | ✅ 完成 | 简化版 196 行，6 场景，AE 2025 兼容 |
| Bridge 通信 | ✅ 打通 | 小面板 runScript 执行成功 |
| AE 工程创建 | ✅ 成功 | 8 图层，1920×1080，30fps，25s |
| AE 内预览效果 | ✅ 理想 | 用户确认"效果已达到理想的进阶状态" |
| aerender 渲染 | ⚠️ 黑屏 | 输出 MP4 全黑，看不到任何文字效果 |
| 完整版 JSX (470行) | ❌ 阻塞 | AE 2025 效果 API 兼容性问题过多 |

---

## 二、🔴 核心待解决问题：渲染全黑

### 现象
- AE 中打开 `D:\AE-Work\TextFX_Showcase.aep`，预览效果很好
- aerender 渲染输出 `D:\AE-Work\output\TextFX_Showcase.mp4`（83KB），播放全黑

### 可能原因分析（按优先级排序）

| # | 可能原因 | 排查方法 | 修复方向 |
|---|----------|----------|----------|
| 1 | **输出模块/编码模板不匹配** | 检查默认 OM 模板是否为 H.264 | 不指定 -OMtemplate，用默认；或指定正确模板名 |
| 2 | **帧范围问题** | aerender 可能只渲染了第 0 帧 | 添加 `-s 1 -e 750` 指定帧范围 |
| 3 | **图层可见性/时间** | startTime/inPoint/outPoint 设置可能有问题 | 检查图层是否 enabled，时间范围是否覆盖 |
| 4 | **合成 bgColor 过暗** | [0.05,0.05,0.08] 在 H.264 低码率下近似纯黑 | 改为 [0.1,0.1,0.15] 或更高 |
| 5 | **文字图层渲染顺序** | 图层可能被固态层遮挡 | 检查图层堆叠顺序 |
| 6 | **aerender 与 AE GUI 渲染差异** | 某些效果/表达式在 aerender 中不生效 | 检查是否需要 `-continueOnMissingFootage` |

### 建议修复步骤
```
1. 先用最简命令测试：aerender -project "D:\AE-Work\TextFX_Showcase.aep" -comp "TextFX_Showcase" -output "D:\AE-Work\output\test.avi"
   （不指定模板，用 AVI 无损格式排除编码问题）
2. 如果 AVI 也黑 → 问题在工程结构（图层时间/可见性）
3. 如果 AVI 正常 → 问题在 H.264 输出模板
4. 在 JSX 中打印每个图层的 inPoint/outPoint/enabled 验证
5. 尝试添加 -s 1 -e 750 强制指定帧范围
```

---

## 三、已验证可用的自动化流程模板

### 3.1 全流程架构
```
Python 编排脚本 (build_textfx_showcase.py)
    │
    ├─ Step 1: Bridge 执行 JSX 构建
    │   └─ 写入 ae_command.json → 小面板轮询 → eval(JSX) → ae_result.json
    │
    ├─ Step 2: 保存工程
    │   └─ runScript: app.project.save(new File("D:/AE-Work/TextFX_Showcase.aep"))
    │
    └─ Step 3: aerender 渲染
        └─ aerender.exe -project ... -comp ... -output ...
```

### 3.2 Bridge 通信协议（关键！）

**必须使用小面板**（`2_mcp_bridge_loader.jsx`），不是大面板（`mcp-bridge-auto.jsx`）

| 项目 | 小面板（正确） | 大面板（错误） |
|------|---------------|---------------|
| 面板标题 | MCP Bridge: Active | MCP Bridge Auto - Ready |
| 源文件 | `.ae-mcp-bridge/2_mcp_bridge_loader.jsx` | `Program Files/.../mcp-bridge-auto.jsx` |
| 监听目录 | `{项目根}\.ae-mcp-bridge\` | `Documents\ae-mcp-bridge\` |
| 命令文件 | `ae_command.json` | `ae_command.json` |
| 结果文件 | `ae_result.json` | `ae_mcp_result.json` |
| 支持 runScript | ✅ 是 | ❌ 否 |
| 打开方式 | File > Scripts > 2_mcp_bridge_loader.jsx | Window > mcp-bridge-auto.jsx |

**命令格式**:
```json
{
  "command": "runScript",
  "args": {"code": "...完整JSX代码..."},
  "timestamp": "2026-07-21T12:00:00",
  "status": "pending"
}
```

**结果格式**:
```json
{"success": true, "data": {"result": "{\"status\":\"success\",\"comp\":\"TextFX_Showcase\",\"layers\":8}"}}
```

### 3.3 Python 编排脚本核心逻辑
```python
# 文件: scripts/build_textfx_showcase.py
BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")

def send_bridge(code, wait=180):
    cmd = {"command": "runScript", "args": {"code": code}, "timestamp": ..., "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd))
    # 轮询等待结果...
```

### 3.4 aerender 渲染命令
```powershell
& "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe" `
  -project "D:\AE-Work\TextFX_Showcase.aep" `
  -comp "TextFX_Showcase" `
  -output "D:\AE-Work\output\TextFX_Showcase.mp4"
```
**注意**: AE 2025 (v25.3x71) 不支持 `-rjsx` 标志（仅 AE 2026 v26.3 支持）

---

## 四、JSX 脚本 AE 2025 兼容性经验（重要！）

### 4.1 已验证可用的 API
| API | 用法 | 状态 |
|-----|------|------|
| `app.project.items.addComp()` | 创建合成 | ✅ |
| `comp.layers.addText(txt)` | 创建文字图层 | ✅ |
| `textDoc.fillColor = [R,G,B]` | 设置文字颜色 | ✅ |
| `textDoc.applyFill = true` | 启用填充 | ✅ |
| `layer.scale.setValueAtTime(t, [x,y])` | Scale 关键帧 | ✅ |
| `layer.opacity.setValueAtTime(t, val)` | Opacity 关键帧 | ✅ |
| `layer.position.setValueAtTime(t, [x,y])` | Position 关键帧 | ✅ |
| `layer.property("Effects").addProperty("ADBE Glo2")` | 添加发光 | ✅ |
| `glow.property("ADBE Glo2-0002").setValue(0.2)` | Glow Threshold | ✅ |
| `glow.property("ADBE Glo2-0003").setValue(20)` | Glow Radius | ✅ |
| `glow.property("ADBE Glo2-0004").setValue(2.0)` | Glow Intensity | ✅ |
| `app.project.save(new File(path))` | 保存工程 | ✅ |

### 4.2 需要 try-catch 或已确认有问题的 API
| API | 问题 | 解决方案 |
|-----|------|----------|
| Ramp 颜色 `ADBE Ramp-0001` | setValue 需要特定格式 | 用属性名 "Start Color" 或 try-catch |
| Turbulent Displace Amount | 范围 1-11（非 0-100+） | `Math.max(1, Math.min(11, val))` |
| Fractal Noise Contrast | 范围 1-4 | `Math.max(1, Math.min(4, val))` |
| Fractal Noise Brightness | 范围 -100~100 | `Math.max(-100, Math.min(100, val))` |
| Glow 颜色 A/B (0006/0007) | 格式不确定 | try-catch 包裹 |
| Text Range Type2 (Shape) | 属性名可能不同 | try-catch 包裹 |
| `$.evalFile()` 大文件 | 静默崩溃 | 用 eval(code) 代替 |

### 4.3 JSX 编写黄金规则
1. **自包含**：无 `#include`，所有函数内联
2. **防御性编程**：所有效果操作 try-catch
3. **返回 JSON**：`return JSON.stringify({status:"success/error", ...})`
4. **从后往前添加场景**：确保场景 1 在图层面板最上面
5. **ExtendScript 兼容**：无 `let/const`，无箭头函数，无模板字符串
6. **JSON polyfill**：ExtendScript 可能无原生 JSON，需内联实现

---

## 五、当前 JSX 脚本内容概要

### 简化版（当前使用，已验证构建成功）
**文件**: `temp/textfx_showcase_simple.jsx` (196 行)

| 场景 | 时间 | 文字 | 字体/大小 | 颜色 | 动画 |
|------|------|------|-----------|------|------|
| S1 Cyber | 0-4s | "CYBER PUNK" | Impact 140pt | 青 [0,1,0.8] | Scale 0→100 + Fade |
| S2 Ink | 4-8s | "水墨丹青" | KaiTi 130pt | 墨 [0.15,0.12,0.1] | Fade In/Out |
| S3 Neon | 8-12s | "NEON GLOW" | Arial-Black 150pt | 粉 [1,0.2,0.6] | Scale 弹跳 + Fade |
| S4 Holo | 12-16s | "HOLOGRAM" | Helvetica 120pt | 蓝 [0.3,0.7,1] | Position 上移 + Fade |
| S5 Fire/Ice | 16-21s | "FIRE" + "ICE" | Impact 160pt | 橙/冰蓝 | Scale + 交错入场 |
| S6 Logo | 21-25s | "TEXT FX" + 副标题 | Impact 200pt | 金 [1,0.85,0.3] | Scale 弹跳 + Fade |

所有场景均添加了 Glow 效果。

### 完整版（待兼容性修复后启用）
**文件**: `temp/textfx_showcase_build.jsx` (491 行)
- 包含 Text Animator、Wiggly Selector、表达式、湍流置换、分形噪波等高级效果
- 因 AE 2025 API 兼容性问题暂时搁置

---

## 六、今日全部开发变更汇总

### 6.1 AE Bridge 生产级稳定化（早期会话）
- WM_CLOSE 优雅关闭（崩溃率 100%→0%）
- 进程管理器 30+ 方法（看门狗+状态机+自动恢复）
- 工业级 IPC 协议（签名/重试/幂等/队列/死信）
- 5 个 P0 级安全/稳定性问题修复
- 测试套件 6 大类（烟雾/生命周期/通信/操作/压力/耐久）

### 6.2 Phase 3 统一架构（中期会话）
- MCP 客户端统一接入新协议层
- AE 端 CommandRegistry 架构（13 个命令）
- Bridge 健康监控 + 指标导出
- 多软件 Bridge 统一基类（PR/PS/AU）
- 110 项测试全部通过

### 6.3 开源基线统一（中后期会话）
- 隔离危险补丁脚本
- 抢救 9 个功能 JSX + 5 个工具库
- 退役 ae-mcp-server + 自研 bridge 栈
- 端到端冒烟测试 8/9 通过
- 发现 execute-atom-script 架构缺口

### 6.4 文字特效库建设
- 6 个脚本库（79 种程序化动画）
- 4998 个 .ffx 预设索引
- MCP Bridge 集成验证通过

### 6.5 TextFX Showcase 实战（本会话核心）
- 编写 470 行完整版 JSX（6 场景高级效果）
- 编写 Python 编排脚本（Bridge + aerender）
- 发现并解决两个 Bridge 面板混淆问题
- AE 2025 兼容性逐一修复（Ramp/TurbulentDisplace/FractalNoise/Glow/RangeSelector）
- 最终使用简化版 196 行 JSX 成功构建
- aerender 渲染完成但输出全黑（待修复）

---

## 七、核心文件索引

### 本次任务直接相关
| 文件 | 说明 |
|------|------|
| `temp/textfx_showcase_simple.jsx` | ✅ 当前使用的简化版 JSX（196行） |
| `temp/textfx_showcase_build.jsx` | 完整版 JSX（491行，待兼容修复） |
| `scripts/build_textfx_showcase.py` | Python 编排脚本（Bridge+aerender） |
| `D:\AE-Work\TextFX_Showcase.aep` | AE 工程文件（已创建） |
| `D:\AE-Work\output\TextFX_Showcase.mp4` | 渲染输出（全黑，待修复） |

### Bridge 通信相关
| 文件 | 说明 |
|------|------|
| `.ae-mcp-bridge/2_mcp_bridge_loader.jsx` | 小面板源码（533行，支持 runScript） |
| `.ae-mcp-bridge/ae_command.json` | 命令文件（Python 写入） |
| `.ae-mcp-bridge/ae_result.json` | 结果文件（AE 写入） |
| `.ae-mcp-bridge/ae_auto_listener.log` | 执行日志 |

### 架构文档
| 文件 | 说明 |
|------|------|
| `00-每日记录/2026-07-21_AE-Bridge-生产级稳定化-开发进度.md` | Phase 1 稳定化 |
| `00-每日记录/2026-07-21_AE-Bridge-Phase3-统一架构开发进度.md` | Phase 3 统一架构 |
| `00-每日记录/2026-07-21_AE-MCP-开源基线统一-开发进度.md` | 开源基线统一 |
| `00-每日记录/2026-07-21_AE-Bridge-自动启动验证-开发进度.md` | 自动启动验证 |

---

## 八、新会话快速启动指南

### 启动消息模板
```
请阅读 00-每日记录/2026-07-21_TextFX-Showcase-开发进度.md，然后继续修复渲染黑屏问题。

当前状态：
- AE 工程 D:\AE-Work\TextFX_Showcase.aep 已创建，AE 中预览效果正常
- aerender 渲染输出全黑（D:\AE-Work\output\TextFX_Showcase.mp4）
- 需要排查渲染黑屏原因并修复

关键约束：
- 使用小面板 Bridge（.ae-mcp-bridge/2_mcp_bridge_loader.jsx）执行 JSX
- AE 2025 不支持 aerender -rjsx
- Python 用 py -3.12 执行
```

### 环境检查清单
```powershell
# 1. AE 是否运行
Get-Process -Name "AfterFX" -ErrorAction SilentlyContinue

# 2. 小面板是否打开（检查日志是否有最近记录）
Get-Content ".ae-mcp-bridge\ae_auto_listener.log" -Tail 5

# 3. 工程文件是否存在
Test-Path "D:\AE-Work\TextFX_Showcase.aep"

# 4. aerender 是否可用
& "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe" -help 2>&1 | Select-Object -First 3
```

---

## 九、后续开发路线图

### 立即（修复黑屏）
1. 排查 aerender 渲染黑屏原因
2. 修复后重新渲染验证
3. 确认视频效果与 AE 预览一致

### 短期（效果增强）
4. 逐步启用完整版 JSX 的高级效果（Text Animator、表达式等）
5. 每增加一个效果就测试渲染，确保不黑屏
6. 添加背景音乐/音效轨道

### 中期（产品化）
7. 将流程封装为一键命令（`py -3.12 scripts/build_textfx_showcase.py`）
8. 支持自定义文字/颜色/时长参数
9. 批量生成不同风格的展示视频

### 长期（能力展示）
10. 整合 79 种动画 + 4998 预设的完整能力展示
11. 对接 DaVinci Resolve 调色流程
12. 形成可复用的视频自动化生产模板

---

## 十、关键经验教训

### 本次实战核心教训
1. **AE 预览 ≠ 渲染输出**：在 AE GUI 中看起来正常不代表 aerender 输出正常
2. **先简后繁**：先用最简 JSX 验证全流程，再逐步添加复杂效果
3. **两个 Bridge 面板必须分清**：小面板(runScript) vs 大面板(原子命令)
4. **AE 2025 效果 API 不可信**：文档说的参数范围与实际不符，必须 try-catch
5. **渲染问题优先排除编码格式**：先用 AVI 无损测试，排除 H.264 编码问题

### V12 版本经验继承
- V12 使用单 JSX + aerender CLI 全自动流程 → 本次继承
- V12 文字全白没设颜色 → 本次所有文字均设置了 fillColor
- V12 时间没把控 → 本次精确到每个场景的 inPoint/outPoint
- V12 不能自动渲染 → 本次通过 Bridge + aerender 实现全自动

---

> 返回 → [[🏠-AE知识中心]]
