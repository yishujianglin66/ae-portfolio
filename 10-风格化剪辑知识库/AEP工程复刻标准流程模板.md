---
title: AEP工程复刻标准流程模板（Bridge+JSX分步策略）
date: 2026-07-23
tags:
  - 复刻模板
  - Bridge通信
  - JSX脚本
  - 工程复刻
  - 经验沉淀
---

# AEP工程复刻标准流程模板

> 基于「独自升级」V1→V3 复刻实战经验沉淀，适用于所有 AE 教程工程的自动化复刻。

---

## 一、标准流程（5阶段）

```
阶段1: 离线扫描（不启动AE）
├── 扫描工程目录素材文件（.mp4/.mov/.png）
├── 二进制解析 .aep 提取 matchName/合成参数（aep_binary_parser.py）
└── 输出: inspection.json（工程结构）

阶段2: 实机参数提取（AE Bridge）
├── 通过 Bridge 打开工程（注意：旧版本会弹窗！）
├── 执行 inspect_params.jsx 提取所有效果参数
└── 输出: params.json（参数值+关键帧）

阶段3: 脚本生成（本地 Python）
├── 基于 params.json 生成精简 JSX 复刻脚本
├── 控制体积 ≤ 300 行（避免内存溢出）
├── 拆分为: 结构脚本 → 效果脚本 → 文字脚本 → 动画脚本
└── 输出: replicate_XXX.jsx

阶段4: Bridge 执行（逐步验证）
├── 发送脚本到 AE（ae_command.json → runScript）
├── 等待结果（ae_result.json，超时 30s）
├── 验证输出文件生成
└── 每步执行后 ping 确认 AE 存活

阶段5: 质量评估（4维度）
├── 特效制作: 效果链完整度 + 参数还原精度
├── 文字动画: 缓动曲线 + Text Animator + 逐字延迟
├── 字体排版: 字体/字重/tracking/leading
└── 合成结构: 预合成嵌套 + 混合模式 + 调整图层层级
```

---

## 二、关键经验教训（Do / Don't）

### ✅ DO（必须遵循）

| 规则 | 原因 | 来源 |
|------|------|------|
| 脚本 ≤ 300 行 | 超过 400 行易触发 AE 内存溢出崩溃 | V2 崩溃事故 |
| 全新空工程构建 | 打开旧工程必弹版本转换对话框，阻塞 Bridge | replicate_safe 事故 |
| 所有 KF 添加缓动 | `setTemporalEaseAtKey(i, [easeIn], [easeOut])` | 差距分析 P0 |
| BCC matchName 无空格 | `BCC4Prism` / `BCCHalftone` / `BCC6SwishPan` | 插件扫描修正 |
| 生成型效果用独立图层 | Fractal Noise/Ramp 不能直接加在视频层 | Video_FX_Showcase V1→V2 |
| 导入素材用 try/catch | importFile 可能触发弹窗或失败 | V1 超时事故 |
| 每步执行后 ping AE | 确认进程存活再继续 | 崩溃检测 |
| 文字层单独脚本精修 | 字体/tracking/Text Animator 需细致配置 | V3 差距分析 |

### ❌ DON'T（严禁操作）

| 禁止 | 后果 | 替代方案 |
|------|------|----------|
| 一次创建 20+ 预合成 | AE 内存溢出崩溃 | 扁平化：直接视频层+裁切 |
| 打开 v18 旧工程 | 版本转换弹窗无限阻塞 | 离线解析+全新构建 |
| 使用 Array.reduce() | ExtendScript 不支持 | 用 for 循环 |
| 使用 toISOString() | ExtendScript 不支持 | 手动拼接日期字符串 |
| 使用 canImportFile() | AE 2025 已废弃 | 直接 try importFile |
| 并行处理多个工程 | 资源竞争+崩溃风险 | 串行逐个处理 |

---

## 三、JSX 脚本模板骨架

```javascript
// replicate_TEMPLATE.jsx - [工程名] 复刻脚本
(function() {
    "use strict";
    var W = 1920, H = 1080, FPS = 60, DUR = 10.0; // 按工程调整
    var SRC = "D:/BaiduNetdiskDownload/AE新手10套/[工程目录]/";
    var OUT = "D:/AE-Work/[工程名]_复刻.aep";

    var proj = app.project;
    if (!proj) return "ERROR: No project";

    // 导入素材（try/catch 防弹窗）
    var vid = null;
    try { vid = proj.importFile(new ImportOptions(File(SRC + "素材.mp4"))); } catch(e) {}
    if (!vid) return "ERROR: Cannot import";

    // 创建主合成
    var comp = proj.items.addComp("[工程名]_复刻", W, H, 1, DUR, FPS);

    // === 工具函数 ===
    function adj(name, inp, out) {
        var s = comp.layers.addSolid([1,1,1], name, W, H, 1);
        s.adjustmentLayer = true; s.inPoint = inp; s.outPoint = out;
        return s;
    }
    function fx(layer, mn) { try { return layer.Effects.addProperty(mn); } catch(e) { return null; } }
    function sv(p, v) { try { p.setValue(v); } catch(e) {} }
    function kf(p, arr) { try { for (var i=0;i<arr.length;i++) p.setValueAtTime(arr[i][0], arr[i][1]); } catch(e) {} }
    function easeKF(p) {
        try {
            var n = p.numKeys;
            for (var i = 1; i <= n; i++) {
                p.setTemporalEaseAtKey(i, [new KeyframeEase(0,33.3)], [new KeyframeEase(0,16.7)]);
            }
        } catch(e) {}
    }
    function kfE(p, arr) { kf(p, arr); easeKF(p); }

    // === 在此构建图层 ===
    // ...

    // 保存
    proj.save(new File(OUT));
    return "SUCCESS: " + comp.numLayers + " layers -> " + OUT;
})();
```

---

## 四、文字精修脚本模板（独立小脚本）

```javascript
// text_refine_XXX.jsx - 文字层精修（单独执行，不重建合成）
(function() {
    "use strict";
    var proj = app.project;
    var comp = null;
    // 找到目标合成
    for (var i = 1; i <= proj.numItems; i++) {
        if (proj.item(i) instanceof CompItem && proj.item(i).name.indexOf("复刻") >= 0) {
            comp = proj.item(i); break;
        }
    }
    if (!comp) return "ERROR: No target comp";

    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        if (layer instanceof TextLayer) {
            var td = layer.property("Source Text").value;
            // 设置字体（需系统已安装）
            // td.font = "SourceHanSansSC-Bold";
            // td.tracking = 50;    // 字间距
            // td.leading = 100;    // 行距
            td.applyFill = true;
            layer.property("Source Text").setValue(td);
        }
    }
    proj.save();
    return "SUCCESS: Text refined";
})();
```

---

## 五、后续 8 工程复刻优先级

| 顺序 | 工程 | 难度 | 核心效果 | 预计脚本数 |
|------|------|------|----------|-----------|
| 1 | do you mean | 简单 | Hue/Sat + Ramp | 2（结构+效果） |
| 2 | 李诗雅竖屏 | 简单 | Lumetri + Looks | 2 |
| 3 | 初音 | 简单 | 3D + TextureFlux | 3（+文字） |
| 4 | 猫猫 | 一般 | B&W + Box Blur | 3 |
| 5 | 8.15 | 一般 | Deep Glow + B&W | 3 |
| 6 | 五条悟 | 一般 | CrackedTiles + Mocha | 3 |
| 7 | 美人鱼 | 较难 | Audio Spectrum + BCC LED | 4 |
| 8 | 蓝色监狱 | 量多 | TextureCells + CrackedTiles | 4 |

**执行规则**：
- 每个工程拆分为 2~4 个小脚本（每个 ≤ 150 行）
- 每步执行后 ping + 验证文件
- 完成一个工程后立即进行 4 维度质量评估
- 经验累积后优化后续工程脚本

---

## 六、matchName 速查表（已验证可用）

```
=== BCC 系列（无空格！）===
BCC4Prism        — 棱镜色散
BCC Halftone     — 半调网点（注意：matchName 含空格！）
BCC6Swish Pan    — 快速摇摄（注意：matchName 含空格！）
BCCLED           — LED 点阵

=== Sapphire 系列 ===
S_Glow / S_Flicker / S_TextureFlux / S_TextureCells / S_DropShadow / S_TimeSlice

=== 内置效果 ===
ADBE Exposure2 / ADBE Gaussian Blur 2 / ADBE Tile / ADBE Ramp
ADBE Glo2 / ADBE Fractal Noise / ADBE HUE SATURATION
CC Particle World / ADBE CM CrackedTiles / ADBE Black&White

=== 第三方 ===
PEDG (Deep Glow) / efx_chromaber / Videocopilot Twitch / MB LookSuite3
DGE Instant 4K (缺失，用 ScaleUp 替代)
```

> [!warning] BCC matchName 特殊说明
> 文件名无空格（`BCCHalftone.aex`），但 **matchName 可能含空格**（`BCC Halftone`、`BCC6Swish Pan`）。
> 实际 matchName 以 params.json 实机提取为准，不能从文件名推断。
