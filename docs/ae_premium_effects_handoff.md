# AE Premium Effects 自动化 — 任务交接文档

> 生成时间: 2026-09-07 20:30
> 项目: AE-Knowledge-Vault (`C:\Users\Administrator\Desktop\AE-Knowledge-Vault`)
> 任务: 为 run53v43 视频自动应用 139 个专业插件特效并渲染输出

---

## 一、任务目标

为 `output/unified_run53/run53_final_v43.mp4`（30s, 1920x1080, 24fps）自动应用 139 个拍点对齐的专业 AE 插件特效，渲染为最终 MP4。

用户原始需求: "一直输出直到有真正的成品输出"

---

## 二、当前状态

### 已完成
- [x] 139 个特效配置 JSON 已生成（`run53v43_effects_premium_v2.json`）
- [x] Python 脚本自动生成 ExtendScript (JSX) 并执行
- [x] AE Bridge 通信通道正常工作（文件轮询协议）
- [x] 首次渲染成功（43MB → 修复后 47.3MB）
- [x] 修复了 Optical Flares / Particular / Sapphire Glow / Bloom 的混合模式（Screen + 降低不透明度）

### 当前成品
- **文件**: `output/unified_run53/run53v43_premium_v2/run53v43_premium_v2.mp4`
- **大小**: 47.3 MB
- **规格**: 1920x1080, H264, 24fps, 30s, AAC 48kHz
- **AEP**: `output/unified_run53/run53v43_premium_v2/run53v43_premium_v2.aep` (26.7 MB)
- **JSX**: `output/unified_run53/run53v43_premium_v2/apply_effects_premium.jsx` (81KB)

### 待解决（用户反馈）
用户原话: **"4秒到5秒，以及24秒到25秒都被特效覆盖了，没有镜头。而且特效也特别的简陋。"**

已做的修复:
1. optical_flares → Screen 混合模式 + 40% 不透明度
2. particular → Screen 混合模式 + 50% 不透明度
3. sapphire_glow → Screen 混合模式 + 50% 不透明度
4. bloom → Screen 混合模式 + 40% 不透明度

**尚未验证修复效果**。用户可能仍不满意"简陋"的问题——特效参数全部使用默认值，没有精细调优。

---

## 三、核心文件清单

| 文件 | 用途 | 大小 |
|------|------|------|
| `scripts/auto_apply_run53v43_premium.py` | 主控脚本：读 JSON → 生成 JSX → AE Bridge 执行 → aerender 渲染 | 12KB |
| `output/unified_run53/run53v43_effects_premium_v2.json` | 139 个特效配置（类型/时间/参数/包络） | 80KB |
| `output/unified_run53/run53v43_premium_v2/apply_effects_premium.jsx` | 自动生成的 ExtendScript（实际在 AE 中执行的脚本） | 81KB |
| `output/unified_run53/run53v43_premium_v2/run53v43_premium_v2.aep` | AE 项目文件 | 26.7MB |
| `output/unified_run53/run53v43_premium_v2/run53v43_premium_v2.mp4` | 最终渲染输出 | 47.3MB |
| `output/unified_run53/run53_final_v43.mp4` | 输入源视频（30s 粗剪） | 56.7MB |
| `ae_mcp_auto_listener.jsx` | AE 端监听脚本（已加载在 AE 中运行） | ~50KB |

---

## 四、技术架构

### 4.1 AE Bridge 文件轮询协议

```
Python (scripts/)                    AE (ae_mcp_auto_listener.jsx)
     |                                        |
     |-- 写 .ae-mcp-bridge/ae_command.json -->|
     |                                        |-- 每500ms轮询
     |                                        |-- 执行命令
     |<-- 写 .ae-mcp-bridge/ae_result.json ---|
     |                                        |
```

**命令文件格式** (`.ae-mcp-bridge/ae_command.json`):
```json
{
  "command": "executeAtomScript",
  "args": {
    "script": "// ExtendScript code here",
    "scriptContent": "// same code"
  },
  "processed": false
}
```

**关键**: `executeScript` 函数使用 `eval()` 而非 `new Function()`，因为 ExtendScript 中 `new Function()` 无法捕获 IIFE 返回值。

### 4.2 Python 端 AERenderChannel

```python
from ai.ae_render_channel import AERenderChannel
channel = AERenderChannel(out_dir="output/unified_run53/run53v43_premium_v2")

# 执行 JSX 文件
result = channel._bridge_run_jsx("path/to/script.jsx", timeout=600)

# 执行内联脚本
result = channel._bridge_run_jsx(timeout=30, command="executeAtomScript",
    args={"script": "app.version;", "scriptContent": "app.version;"})
```

### 4.3 渲染流程

1. Python 读取 `run53v43_effects_premium_v2.json`
2. `generate_effects_jsx()` 生成 ExtendScript 脚本
3. 通过 AE Bridge 的 `executeAtomScript` 命令在 AE 中执行
4. JSX 脚本内部：新建项目 → 导入视频 → 建合成 → 逐个添加特效 → 保存 AEP
5. Python 调用 `aerender.exe` 命令行渲染最终 MP4

```
aerender.exe -project run53v43_premium_v2.aep -comp RUN53V43_PREMIUM_V2 -output run53v43_premium_v2.mp4
```

### 4.4 aerender.exe 路径

通过 `core.paths.aerender_exe()` 获取，通常在:
`C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe`

---

## 五、139 个特效类型分布

| 特效类型 | 数量 | 应用方式 | 混合模式修复状态 |
|----------|------|----------|------------------|
| film_stocks | 26 | 调整图层 + Tiffen Film Stocks | Normal（调色类，正常） |
| magic_bullet_looks | 20 | 调整图层 + Magic Bullet Looks | Normal（调色类，正常） |
| delirium | 20 | 调整图层 + Digieffects Delirium | Normal（特效类，可能需调整） |
| particular | 20 | 调整图层 + Trapcode Particular | **已修复: Screen + 50%** |
| optical_flares | 15 | 调整图层 + Optical Flares | **已修复: Screen + 40%** |
| burst_badtv | 12 | 调整图层 + ADBE Noise HLS Auto | Normal（短脉冲，正常） |
| burst_radial | 11 | 调整图层 + ADBE Radial Blur | Normal（短脉冲，正常） |
| motion_blur | 10 | 调整图层 + CC Force Motion Blur | Normal（工具类，正常） |
| sapphire_glow | 4 | 调整图层 + S_Glow | **已修复: Screen + 50%** |
| twixtor | 1 | 图层复制 + Scale 动画 | N/A（非调整图层） |

---

## 六、已知问题与陷阱

### 6.1 插件可用性

| 插件 | 状态 | 备注 |
|------|------|------|
| S_Glow (Sapphire) | 可用 | |
| Optical Flares | 可用 | |
| Trapcode Particular | 可用 | |
| CC Force Motion Blur | 可用 | |
| Camera Lens Blur | 可用 | |
| Radial Blur | 可用 | |
| ADBE Glow (内置) | **不可用** | 报错，bloom 类型会被 try-catch 跳过 |
| "Glow" (Boris FX) | **不可用** | 缺少 Dfx.dll |
| Digieffects Delirium | **未验证** | 可能不可用，try-catch 会跳过 |
| Magic Bullet Looks | **未验证** | 可能不可用 |
| Tiffen Film Stocks | **未验证** | 可能不可用 |
| ADBE Noise HLS Auto | 可用 | 内置效果 |
| ADBE Displacement Map | 可用 | 内置效果 |
| ADBE Radial Blur | 可用 | 内置效果 |

**重要**: 很多第三方插件可能未安装。JSX 中每个特效都包裹在 try-catch 中，失败的会被跳过并记录到 `errors` 数组。返回值包含 `{success, projectSaved, errors, effectCount}`。

### 6.2 ExtendScript 陷阱

1. **ES3 语法**: AE 使用 ExtendScript (ES3)，不支持 `let`/`const`/箭头函数/模板字符串
2. **eval vs new Function**: 必须用 `eval()` 执行脚本字符串，`new Function()` 无法捕获返回值
3. **图层复制**: `comp.layer(1).duplicate()` 正确；`comp.layers.duplicate()` 不存在
4. **混合模式**: `layer.blendingMode = BlendingMode.SCREEN;` (ExtendScript 枚举)
5. **调整图层**: `layer.adjustmentLayer = true;`
6. **项目关闭**: 必须先检查 `app.project && app.project.file` 再 close
7. **f-string 中的花括号**: Python 生成 JSX 时，JS 的花括号需用 `{{` `}}` 转义

### 6.3 禁止操作

- **禁止强杀 AE 进程**: 必须用 `app.quit()` 优雅退出（用户明确要求）
- **不要假设插件可用**: 每个 addProperty 调用都可能失败

### 6.4 用户审美偏好

- 调色归达芬奇，AE 只做逐镜头效果
- 克制，跟拍点呼吸
- 观感优先于像素指标
- 特效不能覆盖镜头（这是本次的核心问题）

---

## 七、重新运行的方法

### 7.1 完整重新渲染

```bash
cd C:\Users\Administrator\Desktop\AE-Knowledge-Vault
python scripts/auto_apply_run53v43_premium.py
```

这会：
1. 重新生成 JSX（基于当前 Python 代码）
2. 通过 AE Bridge 在 AE 中执行
3. 保存 AEP
4. 调用 aerender 渲染 MP4

**前提**: AE 必须正在运行，且 `ae_mcp_auto_listener.jsx` 已加载。

### 7.2 验证 AE Bridge 是否正常

```python
python -c "
from ai.ae_render_channel import AERenderChannel
ch = AERenderChannel(out_dir='output/unified_run53/run53v43_premium_v2')
res = ch._bridge_run_jsx(timeout=30, command='executeAtomScript',
    args={'script': 'app.version;', 'scriptContent': 'app.version;'})
print(res)
"
```

应返回 `{'status': 'success', 'result': {'executed': True, 'result': '25.3x71'}}`

### 7.3 如果 AE Bridge 不响应

1. 检查 AE 是否运行
2. 在 AE 中: File > Scripts > Run Script File → 选择 `ae_mcp_auto_listener.jsx`
3. 等待 `.ae-mcp-bridge/ae_auto_listener.log` 出现 "Polling started"
4. 重新运行验证命令

---

## 八、后续改进方向

### 8.1 用户反馈的核心问题

1. **"特效覆盖镜头"**: 已通过 Screen 混合模式修复，需验证
2. **"特效简陋"**: 特效参数全部使用默认值，需要精细调优

### 8.2 提升特效质量的思路

- **Optical Flares**: 不要只用 Brightness + Position，应设置 Flare Type、Color、Ray Length、Chromatic Shift 等
- **Particular**: 应设置 Particle Type (Sphere/Line)、Physics (Gravity/Turbulence)、Color over Life、Opacity over Life
- **Sapphire Glow**: 应设置 Inner/Outer Radius、Glow Gamma、Hue Shift
- **Delirium**: 应选择合适的预设而非只设 Intensity
- **Magic Bullet Looks**: 应指定具体的 Look Preset（如 Bleach Bypass、Cross Process）
- **Film Stocks**: 应指定胶片类型（Kodak 2383、Fuji 8552 等）

### 8.3 效果时间轴优化

当前问题: 某些时间段特效过于密集（如 4-5s 有 7 个 optical_flares 连续叠加），可能导致性能问题或视觉过载。

建议: 确保同一时刻只有 1-2 个可见特效叠加，避免多个调整图层同时生效。

### 8.4 验证清单

- [ ] 4-5s 区域镜头是否可见（Optical Flares 不再覆盖）
- [ ] 24-25s 区域镜头是否可见（Particular 不再覆盖）
- [ ] 整体特效是否有视觉层次感和变化
- [ ] 调色类特效（film_stocks, magic_bullet_looks）是否正常生效
- [ ] 脉冲类特效（burst_badtv, burst_radial）是否与拍点对齐

---

## 九、关键代码片段

### 9.1 生成 JSX 的核心函数签名

```python
def generate_effects_jsx(effects: list, video_path: str, aep_path: str, out_mp4: str) -> str:
    """根据特效配置列表生成完整的 ExtendScript 脚本"""
```

### 9.2 特效处理器模板（以 optical_flares 为例，修复后）

```python
elif etype == "optical_flares":
    brightness = params.get("brightness", 100)
    position = params.get("position", [960, 540])
    lines.append(f"  var adj_of{i} = comp.layers.addSolid([1,1,1], '...', w, h, 1.0, dur);")
    lines.append(f"  adj_of{i}.adjustmentLayer = true;")
    lines.append(f"  adj_of{i}.blendingMode = BlendingMode.SCREEN;")  # 修复: 不覆盖镜头
    lines.append(f"  adj_of{i}.opacity = 40;")                         # 修复: 降低不透明度
    lines.append(f"  adj_of{i}.startTime = {start_t};")
    lines.append(f"  adj_of{i}.outPoint = {end_t};")
    lines.append(f"  var fx_of{i} = adj_of{i}.property('ADBE Effect Parade').addProperty('Optical Flares');")
    lines.append(f"  fx_of{i}.property('Brightness').setValue({brightness});")
    lines.append(f"  fx_of{i}.property('Position').setValue([{position[0]}, {position[1]}]);")
```

### 9.3 JSX 脚本结构

```javascript
(function() {
  var errors = [];
  // 关闭旧项目
  try { if (app.project && app.project.file) app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch(e0) {}
  app.newProject();
  // 导入视频
  var imp = app.project.importFile(new ImportOptions(new File("...video...")));
  // 创建合成
  var comp = app.project.items.addComp("RUN53V43_PREMIUM_V2", imp.width, imp.height, 1.0, imp.duration, imp.frameRate);
  comp.layers.add(imp);
  // 逐个特效（每个包裹在 try-catch 中）
  try { /* effect 1 */ } catch(e) { errors.push(...); }
  try { /* effect 2 */ } catch(e) { errors.push(...); }
  // ... 139 个特效 ...
  // 保存项目
  app.project.save(new File("...aep..."));
  return {success: true, projectSaved: true, errors: errors, effectCount: 139};
})();
```

---

## 十、环境信息

- **OS**: Windows 10 (10.0.26200)
- **AE**: After Effects 25.3x71 (2025)
- **Node**: v24.18.0
- **Python**: 3.x (项目虚拟环境)
- **Shell**: Git Bash
- **工作目录**: `C:\Users\Administrator\Desktop\AE-Knowledge-Vault`
- **Git**: master 分支
