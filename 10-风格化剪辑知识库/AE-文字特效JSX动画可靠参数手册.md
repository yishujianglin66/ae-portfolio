# AE 文字特效 JSX 动画可靠参数手册

> **定位**：所有参数均经 AE2025 + aerender 实测验证（渲染文件 >100KB = 内容可见）。可直接复制使用。
> **配套**：`scripts/batch_render_expand_v3.py`（7个辅助函数 + 10个风格生成器）、`scripts/batch_render_expand_v4.py`（8个新辅助函数 + 8个高级生成器）、`04-设计模式与反模式/文字特效开发技术陷阱警醒文档.md`（陷阱清单）。
> **实测日期**：2026-07-24（V3.1 出场动画升级）、2026-07-25（V4 Phase1 摄像机/视差/粒子/点光、V4 Phase2 路径/景深/运动模糊）、2026-07-26（P1 Text Animator级联动画+预设库）

---

## 〇、通用铁律

| 项目 | 规则 |
|------|------|
| opacity 单位 | **0-100**（非0-1）。`setValueAtTime(time, value)`，value∈[0,100] |
| 语法 | ExtendScript = ES3：只用 `var`，禁 let/const/箭头函数/模板字符串；`int` 是保留字 |
| 渲染验证 | 输出文件 >100KB 才算内容可见 |
| 逐字动画 | `ADBE Text Opacity`、`ADBE Text Rotation Y`、`ADBE Text Scale 3D`、`ADBE Text Tracking Amount`（`ADBE Text Position` 不存在） |

---

## 一、easeOutBack 过冲缓动（位置滑入）

**公式**：`1 + ((s+1)*p*p*p + s*p*p)`，其中 `s=1.70158`，`p=progress-1`。

### 水平滑入（x0→x1，y固定）
```javascript
L.position.expression =
  "t=time-inPoint;" +
  "if(t<0.1){[-400,480];}" +                                  // t0前停在起点
  "else if(t<0.9){p=(t-0.1)/0.8;s=1.70158;p=p-1;" +          // t0~t1 过冲
  "x=-400+(650-(-400))*(1+((s+1)*p*p*p+s*p*p));[x,480];}" +
  "else{[650,480];}";                                         // t1后落定
```
- **实测**：FX_EaseBack 551KB ✅
- **参数范围**：过冲量 s=1.70158（标准）；时长 t1-t0 建议 0.6~0.9s。

### 垂直坠落（y0→y1，x固定）
同上，把 x 换成 y。用于 liquid_morph 顶部坠落、data_matrix 从下升起。

---

## 二、矩形遮罩揭示（Mask Reveal）

**API 链**：`layer.property("ADBE Mask Parade")` → `.addProperty("Mask")` → `.property("ADBE Mask Shape")` → `.setValueAtTime(t, Shape对象)`。

```javascript
var mp = L.property("ADBE Mask Parade");
var mk = mp.addProperty("Mask");
var ms = mk.property("ADBE Mask Shape");
var s0 = new Shape();
s0.vertices = [[-hw,-hh],[-hw,-hh],[-hw,hh],[-hw,hh]];  // 收缩到左缘(左->右揭示)
s0.closed = true;
var s1 = new Shape();
s1.vertices = [[-hw,-hh],[hw,-hh],[hw,hh],[-hw,hh]];    // 完整矩形
s1.closed = true;
ms.setValueAtTime(0.3, s0);
ms.setValueAtTime(0.9, s1);
```
- **实测**：FX_MaskRect 279KB ✅
- **hw/hh**：文字半宽/半高，需完全覆盖文字。估算 `hw = len(text)*fontSize*0.55`，`hh = fontSize*0.9`。
- **四方向**（v0 收缩边）：
  - left→右揭示：4顶点收到 `x=-hw`
  - right→左揭示：收到 `x=+hw`
  - up→下揭示：收到 `y=-hh`
  - down→上揭示：收到 `y=+hh`

---

## 三、圆形遮罩扩散（中心揭示）

**贝塞尔近似圆**：4顶点 `[[0,-r],[r,0],[0,r],[-r,0]]`，切线系数 **k=0.5523**。

```javascript
var k = 0.5523, r0 = 5, r1 = 700;
var c0 = new Shape();
c0.vertices = [[0,-r0],[r0,0],[0,r0],[-r0,0]];
c0.inTangents  = [[-r0*k,0],[0,-r0*k],[r0*k,0],[0,r0*k]];
c0.outTangents = [[r0*k,0],[0,r0*k],[-r0*k,0],[0,-r0*k]];
c0.closed = true;
// c1 同理，半径用 r1
ms.setValueAtTime(0.2, c0);
ms.setValueAtTime(1.2, c1);
```
- **实测**：FX_MaskCircle 297KB ✅
- **参数范围**：r0≈5（起点近圆心），r1 需覆盖文字对角（如 700~800）。

---

## 四、3D Y轴翻转

```javascript
L.threeDLayer = true;
L.property("ADBE Transform Group").property("ADBE Rotate Y").expression =
  "t=time-inPoint;" +
  "if(t<0.2){90;}" +                                  // 起始角度(侧对镜头,不可见)
  "else if(t<1.0){p=(t-0.2)/0.8;s=1.70158;p=p-1;" +  // 翻转过冲
  "90*(1+((s+1)*p*p*p+s*p*p));}" +
  "else{0;}";                                          // 落定正面
```
- **实测**：FX_Flip3D 351KB ✅
- **参数范围**：起始角 90°（完全侧对）；RGB 色差层可各偏移 ±15°（105°/75°/90°）并延迟 0.05~0.1s 入场。

---

## 五、逐字揭示（打字机 / 逐字点亮）

**唯一可靠方案**：`ADBE Text Opacity` 动画器 + Range Selector Offset。

```javascript
var an = L.property("Text").property("ADBE Text Animators");
var a  = an.addProperty("ADBE Text Animator"); a.name = "Stagger";
var sl = a.property("ADBE Text Selectors");
var r  = sl.addProperty("ADBE Text Selector");
r.property("ADBE Text Percent Start").setValue(0);
r.property("ADBE Text Percent End").setValue(100);
r.property("ADBE Text Percent Offset").setValueAtTime(0.3, 0);    // 起始:全隐藏
r.property("ADBE Text Percent Offset").setValueAtTime(1.5, 100);  // 结束:全显示
var pr = a.property("ADBE Text Animator Properties");
var op = pr.addProperty("ADBE Text Opacity"); op.setValue(0);     // 选中字透明
```
- **原理**：Start=0,End=100,Offset 0→100 使"隐藏窗口"从左滑到右，实现左→右逐字揭示。
- **⚠️ 勿用** `ADBE Text Position`（AE2025 不存在，实测报错）。

---

## 六、标准淡入淡出（opacity 0-100）

```javascript
L.opacity.setValueAtTime(0, 0);      // t=0 透明
L.opacity.setValueAtTime(0.2, 100);  // t=0.2 完全显示
L.opacity.setValueAtTime(4.5, 100);  // 保持
L.opacity.setValueAtTime(5.0, 0);    // t=5 淡出
```

---

## 七、Glow（ADBE Glo2）已验证参数

```javascript
var gf = L.property("Effects").addProperty("ADBE Glo2");
gf.property("ADBE Glo2-0002").setValue(2.0);    // Glow Intensity (1.5~2.0)
gf.property("ADBE Glo2-0003").setValue(150);    // Glow Radius (60~200)
gf.property("ADBE Glo2-0004").setValue(0);      // Glow Threshold (0~1)
```
- 双色渐变 Glow：`ADBE Glo2-0005`=3（A&B色），`-0006`/`-0007` 为两个 [r,g,b,a] 颜色数组（需 try/catch 包裹）。

---

## 八、3D 图层与摄像机（V4 新增，实测可靠）

**前提**：摄像机/灯光只影响 `threeDLayer=true` 的图层。文字层转3D后 position 为三维 `[x,y,z]`（z=0 为合成平面，负值远离镜头）。

### 3D 文字层
```javascript
L.threeDLayer = true;
L.position.setValue([960,540,0]);   // [x,y,z]
```

### 摄像机推进（Camera Push In）
```javascript
var cam = comp.layers.addCamera("Cam", [960,540]);
cam.pointOfInterest.setValue([960,540,0]);        // 注视画面中心
cam.position.setValueAtTime(0,   [960,540,-2400]); // 远
cam.position.setValueAtTime(4.5, [960,540,-1300]); // 近(推进)
```
- **实测**：FX_CamPush 1677KB ✅
- **参数范围**：z0=-2400~-2000（远），z1=-1300~-1000（近）；文字层放 z=0，背景层放 z=-500/-1000 形成视差。

### 摄像机环绕（Camera Orbit，sin弧线）
```javascript
var cam = comp.layers.addCamera("Cam", [960,540]);
cam.pointOfInterest.setValue([960,540,0]);
cam.position.expression =
  "t=time-inPoint;var a=Math.sin(t*1.1)*0.45;" +   // 摆动幅度0.45rad,速度1.1
  "[960+Math.sin(a)*1500,540,-Math.cos(a)*1500];";  // 半径1500弧线
```
- **实测**：FX_CamOrbit 2491KB ✅
- **参数范围**：半径 1500~1600；摆幅 amp 0.4~0.5；速度 speed 1.0~1.2。

### Z轴纵深视差（摄像机横漂）
```javascript
// 前/中/背三层 threeD，z 分别 0/-450/-900
var cam = comp.layers.addCamera("Cam", [960,540]);
cam.pointOfInterest.setValue([960,540,0]);
cam.position.expression =
  "t=time-inPoint;[960+Math.sin(t*0.7)*250,540,-1600];";  // 横漂振幅250
```
- **实测**：FX_ZParallax 4930KB ✅
- **原理**：摄像机横移时，z 越近的层视差位移越大，产生纵深感。

---

## 九、CC Particle World 粒子（V4 新增，实测可靠）

```javascript
var pL = comp.layers.addSolid([0,0,0], "Particles", 1920, 1080, 1, 5);
var pw = pL.property("Effects").addProperty("CC Particle World");
// ⚠️ 属性索引因版本而异，必须实测探测（见警醒文档陷阱11）
try { pw.property("CC Particle World-0050").setValue(6); } catch(e) {}  // Birth Rate(真实索引-0050,非-0001)
try { pw.property("CC Particle World-0002").setValue(3); } catch(e) {}  // Longevity
try { pw.property("CC Particle World-0008").setValue([960,950,0]); } catch(e) {} // Producer位置
// 配合 Glow + blendMode=5 上色
var pg = pL.property("Effects").addProperty("ADBE Glo2");
pL.blendMode = 5;
```
- **实测**：FX_Particle 11620KB ✅（默认参数即大量粒子，内容充足）
- **关键**：默认参数已保证粒子可见；Birth Rate/Longevity/Producer 为非核心微调，用 try/catch 保护（核心效果不依赖）。

---

## 十、动态点光源（V4 新增，实测可靠）

```javascript
var light = comp.layers.addLight("Sweep", [960,540]);
light.position.setValueAtTime(0, [200,540,-500]);    // 起点(画面外左侧)
light.position.setValueAtTime(3, [1720,540,-500]);   // 终点(扫到右侧)
var lo = light.property("ADBE Light Options Group");
lo.property("ADBE Light Intensity").setValue(300);   // 强度 250~300
lo.property("ADBE Light Color").setValue([0.3,0.8,1]);
try { lo.property("ADBE Light Falloff Type").setValue(1); } catch(e) {}  // 平滑衰减
```
- **实测**：FX_Light 1116KB ✅
- **前提**：被照层必须 `threeDLayer=true`；光源 z 建议 -300~-500（在文字层前方）。

---

## 十一、路径动画（maskPath.pointOnPath，V4 新增，实测可靠）

**核心**：在隐藏参考层（opacity=0 的 Solid）上建 mask 贝塞尔路径，运动层 position 表达式读取 `pointOnPath`，**必须用 `toComp()` 换算坐标空间**。

```javascript
// 1. 建隐藏路径参考层 (verts相对图层中心锚点偏移, in/outTangents水平切线)
var pathRef = comp.layers.addSolid([0,0,0], "PathRef", 1920, 1080, 1, 5);
pathRef.opacity.setValue(0);
var s = new Shape();
s.vertices = [[-300,-40],[-100,40],[100,-40],[300,40]];
s.inTangents = [[-120,0],[-120,0],[-120,0],[-120,0]];
s.outTangents = [[120,0],[120,0],[120,0],[120,0]];
s.closed = false;
pathRef.property("ADBE Mask Parade").addProperty("Mask").property("ADBE Mask Shape").setValue(s);
// 2. 运动层跟随路径
L.position.expression =
  "var ref=thisComp.layer('PathRef');" +
  "var t01=clamp(time/2.5,0,1);" +                       // 单次遍历(或用ping-pong往返)
  "var p=ref.mask('Mask 1').maskPath.pointOnPath(t01);" +
  "ref.toComp(p);";                                       // 图层坐标->合成空间
```
- **实测**：FX_PathMove 328.3KB ✅
- **坐标换算**：`pointOnPath` 返回参考层图层坐标（相对其锚点），**必须 `ref.toComp(p)`** 换算到合成空间，否则位置错误。
- **3D层**：返回 `[p[0],p[1],z]`（z=0）；2D层直接 `ref.toComp(p)`。
- **ping-pong往返**（glitch抱动）：`var ph=(time/1.3)%2; var t01=ph<1?ph:2-ph;`

---

## 十二、景深（Depth of Field，V4 新增，实测可靠）

```javascript
var cam = comp.layers.addCamera("Cam", [960,540]);
cam.pointOfInterest.setValue([960,540,0]);
cam.position.setValue([960,540,-1600]);
var co = cam.property("ADBE Camera Options Group");
co.property("ADBE Camera Depth of Field").setValue(1);              // 开启景深
co.property("ADBE Camera Focus Distance").setValueAtTime(0.3, 700);  // 先聚焦背景(距离700)
co.property("ADBE Camera Focus Distance").setValueAtTime(2.5, 1600); // 拉到主字(距离1600)
co.property("ADBE Camera Aperture").setValue(10);                    // 光圈越大景深越浅
```
- **实测**：FX_DOF 891.4KB ✅（属性名实测探测确认）
- **焦跞=镜头到主体的距离**（非z坐标）：相机z=-1600，主体z=0→焦跞1600；背景z=-900→焦跞700。
- **参数范围**：aperture 8~12（越大虚化越强）；背景层与主字层均需 threeDLayer=true。

---

## 十三、运动模糊（Motion Blur，V4 新增，实测可靠）

```javascript
comp.motionBlur = true;     // 合成级开关(必须)
L.motionBlur = true;        // 图层级开关(必须)
// 快速位移产生拖影 (0.4s内-600->960)
L.position.setValueAtTime(0.2, [-600,540]);
L.position.setValueAtTime(0.6, [960,540]);
```
- **实测**：FX_MotionBlur 545.8KB ✅
- **双开关缺一不可**：comp.motionBlur 与 layer.motionBlur 都为 true 才生效。
- **位移速度**：0.3~0.5s 内移动半屏以上距离，拖影明显；配合关键帧（非表达式）最可靠。

---

## 十四、常用表达式片段

| 效果 | 表达式 |
|------|--------|
| 灯管闪烁 | `base=t<0.2?t/0.2:(t>4.5?(5-t)/0.5:1); flicker=(t>1.2&&Math.random()>0.92)?0.3:1; base*flicker*100` |
| 落定微抖动 | `t=time-inPoint; if(t>1.2){wiggle(2,1.5);}else{0;}` |
| 故障随机跳变 | `seedRandom(Math.floor(t*12),true); ...` + decay 衰减 |
| 节拍弹跳 | scale 用 `100+Math.sin(t*freq)*amp`（相位连续） |

---

## 附A：V3.1 十个特效出场手法对照

| 特效 | 主字位置 | 入场手法 | 渲染大小 |
|------|----------|----------|----------|
| neon_cyber | 左三分(0.34w,0.45h) | easeOutBack左滑入 + RGB延迟跟随 | 3.8MB |
| glitch_storm | 右三分(0.66w,0.40h) | 故障散落汇聚 + 碎片多向 | 1.8MB |
| liquid_chrome | 上三分(0.5w,0.30h) | 顶部坠落 + 弹性挤压 | 2.3MB |
| strobe_pulse | 右三分(0.68w,0.50h) | 右缘甩入 + 节拍挤压 | 4.7MB |
| neon_tube | 左三分(0.32w,0.42h) | 逐字点亮 + 灯管闪烁 | 4.2MB |
| data_matrix | 下三分(0.40w,0.68h) | 打字机 + 从下升起 | 0.8MB |
| ink_splash | 左三分(0.36w,0.48h) | 圆形遮罩揭示 + 缩放 | 3.7MB |
| holo_max | 上三分(0.5w,0.34h) | 3D Y翻转 + RGB偏移 | 2.2MB |
| laser_sweep | 右三分(0.62w,0.45h) | 矩形遮罩上→下 + 激光束 | 0.9MB |
| hud_max | 左三分(0.38w,0.40h) | 左推入 + 逐字加载 | 0.5MB |

---

## 附B：V4 Phase1 四个高级特效手法对照

| 特效 | 画幅 | 核心手法 | 渲染大小 |
|------|------|----------|----------|
| epic_push | 横屏 | 摄像机推进 + 三层Z视差 + 点光横扫 + 圆形遮罩揭示 | 3.9MB |
| holo_orbit | 竖屏 | 摄像机环绕 + RGB色差闪烁 + 3D Y翻转 + 灯管闪烁 | 2.4MB |
| ember_burst | 横屏 | CC Particle World火星 + 冲击波环 + 缩放爆发 | 11.4MB |
| cyber_depth | 横屏 | Z视差横漂 + HUD数据层 + 点光扫过 + 逐字加载 | 4.9MB |

**V4 新增辅助函数**（`batch_render_expand_v4.py`）：`_txt3d`、`_make3d`、`_cameraPush`、`_cameraOrbit`、`_cameraDrift`、`_particleWorld`、`_pointLight`、`_slideBack3d`。

---

## 附C：V4 Phase2 四个高级特效手法对照

| 特效 | 画幅 | 核心手法 | 渲染大小 |
|------|------|----------|----------|
| glitch_path | 横屏 | RGB碎片沿路径ping-pong + 湍流置换 + 摄像机seedRandom抖动 | 2.3MB |
| fluid_flow | 竖屏 | 湍流置换流体扭曲 + 3光球沿S路径流动 | 2.5MB |
| dof_focus | 横屏 | 景深焦点从背景拉至主字 + 背景虚化 | 1.8MB |
| speed_blur | 横屏 | 高速关键帧滑入 + 运动模糊拖影 + 红色残影 | 6.6MB |

**V4 Phase2 新增辅助函数**：`_pathRefLayer`、`_pathMove`、`_pathPingPong`、`_dof`、`_motionBlur`。

---

## 十五、3D翻转文字（2026-07-25 实测 356.9KB PASS）

```javascript
// 3D层 + X/Y Rotation 关键帧
tL.threeDLayer = true;
tL.position.setValue([960, 540, 0]);
tL.property("X Rotation").setValueAtTime(0, 90);   // 侧面不可见
tL.property("X Rotation").setValueAtTime(0.8, 0);  // 翻转到正面
tL.property("Y Rotation").setValueAtTime(1.0, 0);
tL.property("Y Rotation").setValueAtTime(2.0, 15); // 轻微旋转强调
tL.property("Y Rotation").setValueAtTime(3.0, 0);
// 必须配合摄像机
var cam = comp.layers.addCamera("Cam", [960, 540]);
cam.property("ADBE Camera Options Group").property("ADBE Camera Zoom").setValue(1200);
```

## 十六、打字机逐字显现（2026-07-25 实测 283.1KB PASS）

```javascript
// Text Animator + Range Selector + Opacity
var tProp = tL.property("Text");
var animators = tProp.property("ADBE Text Animators");
var anim = animators.addProperty("ADBE Text Animator");
var animProps = anim.property("ADBE Text Animator Properties");
animProps.addProperty("ADBE Text Opacity").setValue(0);  // 被选中字符透明=0
// Range Selector（必须用索引，中文名无法用英文）
var selectors = anim.property("ADBE Text Selectors");
var rSel = selectors.addProperty("ADBE Text Selector");
rSel.property(1).setValue(0);    // ADBE Text Percent Start
rSel.property(2).setValue(100);  // ADBE Text Percent End
rSel.property(3).setValueAtTime(0, -100);  // Offset: -100=全隐藏
rSel.property(3).setValueAtTime(2.5, 0);   // Offset: 0=全显示
```

**关键发现**：Range Selector 属性必须用索引(1/2/3)，matchName为 `ADBE Text Percent Start/End/Offset`，但用 `"ADBE Text Offset"` 会返回 null。

## 十七、模糊淡入（2026-07-25 实测 837.8KB PASS）

```javascript
// Gaussian Blur + opacity + 缩放组合
var blur = tL.property("Effects").addProperty("ADBE Gaussian Blur 2");
blur.property(1).setValueAtTime(0, 80);   // Blurriness: 80→ 0
blur.property(1).setValueAtTime(1.2, 0);
tL.opacity.setValueAtTime(0, 0);
tL.opacity.setValueAtTime(0.8, 100);
tL.scale.setValueAtTime(0, [120, 120]);   // 轻微缩入
tL.scale.setValueAtTime(1.0, [100, 100]);
```

## 十八、全息扫描线（2026-07-25 实测 2484.8KB PASS）

```javascript
// Linear Wipe 揭示 + 扫描线层 + 闪烁表达式
var wipe = tL.property("Effects").addProperty("ADBE Linear Wipe");
wipe.property(1).setValueAtTime(0, 100);  // Transition Completion: 100%=全隐藏
wipe.property(1).setValueAtTime(1.5, 0);  // 0%=全显示
wipe.property(2).setValue(270);           // Wipe Angle: 270=从上到下
// 扫描线层（亮线从上到下）
var scanL = comp.layers.addSolid([0,1,1], "ScanLine", 1920, 6, 1, 5);
scanL.position.setValueAtTime(0, [960, 100]);
scanL.position.setValueAtTime(1.5, [960, 980]);
scanL.blendMode = 5;  // Add
// 文字闪烁
tL.opacity.expression = "t=time-inPoint;if(t>1.5){95+Math.random()*5;}else{100;}";
```

## 十九、波浪文字（2026-07-25 实测 4465.2KB PASS）

```javascript
// position/rotation/scale 全部用 sin 表达式驱动
tL.position.expression = "x=value[0];y=value[1]+Math.sin(time*3)*30;[x,y]";
tL.rotation.expression = "Math.sin(time*2)*5";
tL.scale.expression = "v=100+Math.sin(time*4)*5;[v,v]";
// 双层错位波浪制造层次感
t2.position.expression = "x=value[0];y=value[1]+Math.sin(time*3+1.5)*25;[x,y]";
t2.opacity.setValue(40); t2.blendMode = 5;
```

## 二十、弹性缩放（2026-07-25 实测 1726.8KB PASS）

```javascript
// Elastic easeOut 表达式
tL.scale.expression = "t=time-inPoint;" +
  "if(t<0.01){[0,0];}" +
  "else{amp=120;freq=2.5;decay=4;" +
  "s=amp*Math.sin(freq*t*Math.PI*2)/Math.exp(decay*t)+100;" +
  "[s,s];}";
tL.opacity.setValueAtTime(0, 0);
tL.opacity.setValueAtTime(0.15, 100);
```

## 二十一、字间距动画（2026-07-25 实测 443.9KB PASS）

```javascript
// Text Animator + Tracking Amount
var animProps = anim.property("ADBE Text Animator Properties");
var track = animProps.addProperty("ADBE Text Tracking Amount");
track.setValueAtTime(0, 200);   // 起始字距很大
track.setValueAtTime(2.0, 0);   // 收拢到正常
```

---

## 附D：阶段二新验证技法对照（2026-07-25）

| 技法 | 核心手法 | 渲染大小 | 状态 |
|------|----------|----------|------|
| 3D翻转 | X/Y Rotation + Camera | 356.9KB | ✅ |
| 打字机逐字 | Text Animator + Range Selector(idx 1/2/3) | 283.1KB | ✅ |
| 模糊淡入 | Gaussian Blur(idx 1) + opacity + scale | 837.8KB | ✅ |
| 全息扫描线 | Linear Wipe(idx 1/2) + 扫描层 + 闪烁 | 2484.8KB | ✅ |
| 波浪文字 | sin表达式(position/rotation/scale) | 4465.2KB | ✅ |
| 弹性缩放 | elastic easeOut表达式 | 1726.8KB | ✅ |
| 字间距动画 | ADBE Text Tracking Amount | 443.9KB | ✅ |
| 破碎重组 | Shatter效果 | - | ❌ AE2025不可用 |

**新增约束**：
- Shatter效果在AE 2025(25.3x71)中不可用（"Shatter"/"ADBE Shatter"/"碎裂"均报错）
- Range Selector 属性必须用索引(1/2/3)，不能用"ADBE Text Offset"(返回null)
- Gaussian Blur matchName = "ADBE Gaussian Blur 2"，Blurriness = property(1)
- Linear Wipe matchName = "ADBE Linear Wipe"，Completion=property(1)，Angle=property(2)

---

## 附E：P1 Text Animator级联动画新验证属性（2026-07-26）

| 属性 matchName | 类型 | 值域 | 渲染验证 | 状态 |
|------|------|------|------|------|
| ADBE Text Rotation Y | 每字Y轴旋转 | -360~360 | P1_3D_Cascade 12724KB | ✅ |
| ADBE Text Scale 3D | 每字3D缩放 | [0,0,0]~[100,100,100] | P1_3D_Cascade 12724KB | ✅ |
| ADBE Text Tracking Amount | 字间距 | -1000~1000 | Preset_TrackConverge 373KB | ✅ |
| ADBE Text Opacity + Rotation Y组合 | 级联翻入 | - | Preset_WaveFlip 415KB | ✅ |
| ADBE Text Scale 3D + Opacity组合 | 缩放脉冲 | - | Preset_ScalePulse 126KB | ✅ |

**预设库渲染结果**：

| 预设名 | 核心技法 | 渲染大小 | 状态 |
|------|------|------|------|
| Preset_WaveFlip | Rotation Y(120°) + Opacity + 弹性缩放 | 415.6KB | ✅ |
| Preset_ScalePulse | Scale 3D([0,0,0]) + Opacity + Glow + 呼吸 | 126.0KB | ✅ |
| Preset_TrackConverge | Tracking(400→0) + Opacity + 表达式呼吸 | 373.8KB | ✅ |
| Preset_SignatureSnap | easeOutBack弹射 + Rotation Y(45°) + 冲击波 | 226.6KB | ✅ |
| P1_3D_Cascade_Test | RotY + Scale3D + Tracking + Camera + Glow | 12724.8KB | ✅ |

**新增约束**：
- `ADBE Text Rotation Y` 和 `ADBE Text Scale 3D` 在 AE 2025(25.3x71) 中确认可用
- Text Animator 内属性不能重复 addProperty（第二次会报错），必须先存引用再 setValueAtTime
- Range Selector offset 关键帧: `rs.property(3).setValueAtTime(t, value)`，-100=全隐藏，0=全显示
- 多动画器可叠加: 同一文字层可添加多个 ADBE Text Animator，各自独立作用

---

## 附F：P2 粒子特效与多模态复合标题新验证技法（2026-07-26）

| 技法 | 核心手法 | 渲染大小 | 状态 |
|------|----------|----------|------|
| 多层粒子纵深 | 3层CC Particle World(z=-200/200/600) + 3D摄像机视差 | 13548KB | ✅ |
| 粒子颜色分层 | ADBE Tint(property 2/3)映射黑白到自定义色 | 13548KB | ✅ |
| 粒子节奏脉冲 | opacity表达式 sin脉动 + 爆发衰减曲线 | 8956KB | ✅ |
| 粒子-文字联动 | 粒子层opacity/scale与Text Animator揭示同步 | 8956KB | ✅ |
| 冲击波环 | ADBE Ramp(radial) + opacity/scale瞬间爆发表达式 | 7471KB | ✅ |
| RGB色散分离 | 复制层+ADBE Tint(红/蓝)+seedRandom位置抖动 | 7471KB | ✅ |
| 体积光模拟 | ADBE Ramp(linear) + Screen混合 + 呼吸表达式 | 7471KB | ✅ |
| 多模态复合标题 | 10层协同: 文字+粒子+Glow+色散+冲击波+光束+摄像机 | 7471KB | ✅ |

**新增已验证效果 matchName**：
- `ADBE Tint`: property(2)=Map Black To [r,g,b,a], property(3)=Map White To [r,g,b,a]
- `ADBE Ramp`: property(1)=Start Pos, (2)=Start Color, (3)=End Pos, (4)=End Color, (5)=Ramp Shape(1=linear,2=radial)
- `CC Particle World` + `ADBE Tint` 组合: 粒子默认白色，Tint可映射为任意色调

**多模态复合标题时间线编排模式**：
```
0-0.5s  蓄力期: 背景粒子缓慢漂浮, 文字未显现
0.5-1.5s 入场期: Text Animator级联揭示 + 粒子层opacity爆发
1.5s    冲击点: 冲击波环(scale 5→300) + RGB色散抖动 + Glow峰值
1.5-3s  扩散期: 粒子扩散衰减 + 文字tracking呼吸 + 光束渐显
3-5s    稳定态: 微呼吸动画 + 环境粒子持续
```

**新增约束**：
- ADBE Tint 颜色值格式: [r, g, b, a]，范围0-1
- 粒子层必须 blendMode=5(Screen) 才能在深色背景上可见
- 冲击波表达式核心: opacity瞬间80→指数衰减, scale线性扩散(5+p*300)
- 多层粒子视差: 各层z深度差异≥200, 摄像机z在-800~-1400范围
