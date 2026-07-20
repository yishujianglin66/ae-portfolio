# AE预设解析与实战调用完全手册

> **核心目标**：理解AE所有预设格式的内部结构，掌握参数解析方法，能通过脚本/表达式/手动方式精准调用预设中的每个参数。
> **适用版本**：After Effects 2024-2026 | **语法标准**：ExtendScript ES3

---

## 一、AE预设体系总览

### 1.1 预设类型分类

AE生态中的预设覆盖了从单效果参数快照到完整项目模板的全部层级。理解每种预设的本质区别，是精准调用的前提。

#### 效果预设（.ffx）- 单个效果或效果组合的参数快照

效果预设是最基础的预设类型，保存一个或多个效果插件的所有参数值。它不包含关键帧数据（除非同时作为动画预设），仅记录某一时刻效果的"参数快照"。

```
效果预设结构：
┌─────────────────────┐
│   .ffx 文件         │
│  ┌───────────────┐  │
│  │ Effect 1      │  │
│  │  - Param 1: v │  │
│  │  - Param 2: v │  │
│  │  - Param N: v │  │
│  └───────────────┘  │
│  ┌───────────────┐  │
│  │ Effect 2      │  │
│  │  - Param 1: v │  │
│  │  - Param N: v │  │
│  └───────────────┘  │
└─────────────────────┘
```

**典型场景**：Glow效果预设（保存Glow Threshold、Radius、Intensity参数值）、调色预设（保存Lumetri全参数）。

#### 动画预设（.ffx）- 带关键帧的动画参数快照

动画预设与效果预设使用相同的`.ffx`格式，但额外包含关键帧数据。一个动画预设可以包含变换属性（Position/Scale/Rotation/Opacity）的关键帧、效果参数的关键帧，以及缓动曲线信息。

**典型场景**：缩放弹跳预设（Scale从0%→120%→100%的弹性关键帧）、位置滑动预设（带缓动的位移动画）。

#### 文字动画预设（.ffx）- 文字动画器预设

文字动画预设专门针对AE的文字动画器（Text Animator）体系，保存动画器、选择器（Selector）和动画属性的完整配置。

**典型场景**：打字机效果（Character Offset + Range Selector逐字推进）、文字淡入滑动、逐字缩放。

#### 形状预设（.ffx）- 形状图层路径/描边/填充预设

形状预设保存形状图层的Path、Stroke、Fill等属性参数。通过Presets面板应用时，会替换当前形状图层的对应属性。

**典型场景**：箭头形状预设、星形路径预设、虚线描边预设。

#### 合成模板（.aep）- 完整合成项目

AEP模板是最完整的预设形式，包含所有图层、效果、表达式、素材引用和合成设置。用户需要通过File > Open或Import方式使用。

**典型场景**：片头模板、Logo演绎模板、信息图表模板。

#### MOGRT模板（.mogrt）- Essential Graphics封装的PR/AE通用模板

MOGRT（Motion Graphics Template）是Adobe跨应用模板格式，通过Essential Graphics面板将AE合成的可编辑参数暴露给Premiere Pro使用。内部为ZIP压缩包，包含AEP项目文件、XMP元数据和嵌入资源。

**典型场景**：字幕条模板、Lower Third模板、社交媒体标题模板。

#### 表达式预设 - 表达式模板库

表达式预设并非独立文件格式，而是以表达式代码形式存储的参数驱动逻辑。通常保存在.ffx预设的属性表达式中，或以文本/脚本文件形式分发。

**典型场景**：弹性表达式（overshoot）、循环表达式（loopOut）、抖动表达式（wiggle控制）。

#### 调色预设/LUT - .3dl/.cube/.look调色查找表

LUT（Look-Up Table）是色彩映射表，定义输入颜色到输出颜色的对应关系。AE通过Lumetri Color或Apply Color LUT效果加载。

**典型场景**：Teal & Orange调色、电影感Look、VHS褪色调色。

#### 转场预设 - 转场动画预设包

转场预设是包含关键帧动画的.ffx文件，通常应用在调整图层（Adjustment Layer）上，通过效果动画实现场景间的过渡。

**典型场景**：缩放转场、模糊转场、Glitch转场、光效转场。

#### 第三方预设包 - Trapcode/Sapphire/BCC预设

第三方插件厂商提供的预设系统，格式通常为.ffx或私有格式，依赖对应插件运行。

**典型场景**：Trapcode Particular粒子预设、Sapphire转场预设、BCC光效预设。

---

### 1.2 预设存储位置

#### 系统预设路径

AE安装时自带一套系统预设，位于安装目录下：

| 平台 | 路径 |
|------|------|
| Windows | `C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\Presets\` |
| macOS | `/Applications/Adobe After Effects 2026/Presets/` |

系统预设按类别组织子目录：`Effects`、`Animation`、`Shapes`、`Text`、`Transitions`等。

#### 用户自定义预设路径

用户保存的预设存储在用户目录下，不会因AE版本升级而丢失：

| 平台 | 路径 |
|------|------|
| Windows | `C:\Users\<用户名>\AppData\Roaming\Adobe\After Effects\26.0\UserPresets\` |
| macOS | `~/Library/Application Support/Adobe/After Effects/26.0/UserPresets/` |

> **注意**：`26.0`对应AE 2026版本号。用户预设仅在该版本中可见。

#### 第三方预设安装路径

第三方预设通常安装在以下位置：

```
# 方式1：放入用户预设目录（推荐）
C:\Users\<用户名>\AppData\Roaming\Adobe\After Effects\26.0\UserPresets\

# 方式2：放入系统预设目录（需管理员权限）
C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\Presets\

# 方式3：通过AE内置预设管理器导入
Effects & Presets面板 → 右键 → Import Preset
```

#### 跨版本预设兼容性

| 版本跨度 | 兼容性 | 说明 |
|----------|--------|------|
| 同大版本（如26.x→26.y） | ✅ 完全兼容 | .ffx格式不变 |
| 前一版本（如25→26） | ✅ 基本兼容 | 新版可读旧版预设 |
| 跨多个版本（如22→26） | ⚠️ 部分兼容 | 内置效果可能重命名/参数调整 |
| 旧版→新版（CS6→2026） | ⚠️ 可能缺失 | 部分旧效果已被移除或替换 |
| 新版→旧版（2026→2024） | ❌ 不兼容 | 新增效果参数无法降级 |

**关键规则**：
- .ffx本质为XML文本，可手动编辑修复兼容性问题
- MOGRT仅支持向前兼容（新版PR可读旧版MOGRT，反之不行）
- 第三方插件预设依赖对应版本插件，需同时升级插件

---

## 二、.ffx预设深度解析

### 2.1 .ffx文件格式

#### .ffx本质：XML格式文件

.ffx文件本质是UTF-8编码的XML文本文件，使用Adobe自定义的XML Schema描述AE属性数据。任何文本编辑器均可打开阅读和修改。

#### .ffx文件结构解析

一个典型的.ffx文件结构如下：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<adobeeffectpresets version="6.0">
  <effectpreset name="My Glow Preset" presetID="{UUID}">
    <property id="ADBE Effect Parade">
      <property id="ADBE Glo2">
        <property id="ADBE Glo2-0001">
          <value>0.0</value>
        </property>
        <property id="ADBE Glo2-0002">
          <value>50.0</value>
        </property>
        <property id="ADBE Glo2-0003">
          <value>255.0</value>
        </property>
        <property id="ADBE Glo2-0004">
          <value type="color">
            <red>1.0</red>
            <green>1.0</green>
            <blue>1.0</blue>
            <alpha>1.0</alpha>
          </value>
        </property>
      </property>
    </property>
  </effectpreset>
</adobeeffectpresets>
```

#### 如何用文本编辑器打开和阅读.ffx

1. 将.ffx文件拖入VS Code或Notepad++打开
2. 若显示乱码，尝试以UTF-8编码重新打开
3. 使用XML格式化插件美化代码（VS Code推荐XML Tools扩展）
4. 关注`id`属性中的Match Name（如`ADBE Glo2`），这是效果的唯一标识符

#### .ffx中的关键标签

| 标签 | 含义 | 示例 |
|------|------|------|
| `<adobeeffectpresets>` | 根元素，声明版本 | `version="6.0"` |
| `<effectpreset>` | 单个预设定义 | `name="My Preset"` |
| `<property>` | 属性节点，可嵌套 | `id="ADBE Glo2-0001"` |
| `<value>` | 属性值 | `<value>50.0</value>` |
| `<keyframe>` | 关键帧数据 | `time="0.5" value="100"` |
| `<temporalEase>` | 时间缓动 | 入速度/出速度 |
| `<spatialBezier>` | 空间贝塞尔 | 切线手柄坐标 |
| `<expression>` | 表达式代码 | 包含表达式文本 |

---

### 2.2 效果预设解析

#### 解析单个效果参数

以Glow效果为例，其Match Name为`ADBE Glo2`，参数结构：

| 参数序号 | Match Name | 参数名 | 数据类型 | 默认值 | 范围 |
|----------|-----------|--------|----------|--------|------|
| 1 | ADBE Glo2-0001 | Threshold | 数值 | 0 | 0-255 |
| 2 | ADBE Glo2-0002 | Radius | 数值 | 50 | 0-500 |
| 3 | ADBE Glo2-0003 | Intensity | 数值 | 0 | 0-255 |
| 4 | ADBE Glo2-0004 | Color | 颜色 | 白色 | - |
| 5 | ADBE Glo2-0005 | Glow Operation | 下拉菜单 | Add | 枚举 |
| 6 | ADBE Glo2-0006 | Glow Technique | 下拉菜单 | Precise | 枚举 |

.ffx中的表示：

```xml
<property id="ADBE Glo2">
  <property id="ADBE Glo2-0001">
    <value>25.0</value>  <!-- Threshold = 25 -->
  </property>
  <property id="ADBE Glo2-0002">
    <value>80.0</value>  <!-- Radius = 80 -->
  </property>
  <property id="ADBE Glo2-0003">
    <value>150.0</value>  <!-- Intensity = 150 -->
  </property>
</property>
```

#### 解析多效果组合

一个.ffx预设可包含多个效果，每个效果都是`ADBE Effect Parade`下的并列`<property>`节点：

```xml
<property id="ADBE Effect Parade">
  <!-- 效果1：Glow -->
  <property id="ADBE Glo2">
    <!-- ... Glow参数 ... -->
  </property>
  <!-- 效果2：Curves -->
  <property id="ADBE Curves">
    <!-- ... Curves参数 ... -->
  </property>
  <!-- 效果3：Vignette -->
  <property id="ADBE Vignette">
    <!-- ... Vignette参数 ... -->
  </property>
</property>
```

#### 解析效果中的关键帧

关键帧以`<keyframe>`标签表示，包含时间戳和值：

```xml
<property id="ADBE Glo2-0003">  <!-- Intensity -->
  <keyframe time="0" value="0" interpType="linear"/>
  <keyframe time="0.5" value="200" interpType="bezier">
    <temporalEase inSpeed="0" inInfluence="16.67" outSpeed="200" outInfluence="16.67"/>
  </keyframe>
  <keyframe time="1.0" value="100" interpType="bezier">
    <temporalEase inSpeed="200" inInfluence="16.67" outSpeed="0" outInfluence="16.67"/>
  </keyframe>
</property>
```

| 属性 | 含义 | 单位 |
|------|------|------|
| `time` | 关键帧时间 | 秒 |
| `value` | 参数值 | 效果参数单位 |
| `interpType` | 插值类型 | linear/bezier/hold |
| `inSpeed` | 入速度 | 值/秒 |
| `outSpeed` | 出速度 | 值/秒 |
| `inInfluence` | 入影响范围 | 百分比 |
| `outInfluence` | 出影响范围 | 百分比 |

#### 解析效果中的表达式

表达式存储在属性的`<expression>`标签中：

```xml
<property id="ADBE Glo2-0003">
  <expression>wiggle(2, 50)</expression>
  <value>100</value>
</property>
```

#### 参数数据类型

| 数据类型 | .ffx表示 | 示例 | 脚本访问方式 |
|----------|----------|------|-------------|
| 数值 | `<value>50.0</value>` | Radius=50 | `.setValue(50)` |
| 颜色 | `<red>1.0</red><green>0.5</green><blue>0.2</blue><alpha>1.0</alpha>` | RGB 255,128,51 | `.setValue([1,0.5,0.2,1])` |
| 角度 | `<value>45.0</value>` | 45° | `.setValue(45)` |
| 点 | `<value><x>960</x><y>540</y></value>` | 960,540 | `.setValue([960,540])` |
| 下拉菜单 | `<value>2</value>` | 第3项（0索引） | `.setValue(2)` |
| 复选框 | `<value>1</value>` | 开启 | `.setValue(1)` |
| 文本 | `<value>Hello</value>` | 字符串 | `.setValue("Hello")` |

---

### 2.3 动画预设解析

#### 解析关键帧数据

动画预设的核心是关键帧序列。一个完整的缩放弹性动画预设：

```xml
<property id="ADBE Scale">
  <keyframe time="0" value="0 0" interpType="bezier">
    <temporalEase inSpeed="0 0" inInfluence="0 0" outSpeed="120 120" outInfluence="8.33 8.33"/>
  </keyframe>
  <keyframe time="0.4" value="120 120" interpType="bezier">
    <temporalEase inSpeed="120 120" inInfluence="8.33 8.33" outSpeed="-40 -40" outInfluence="8.33 8.33"/>
  </keyframe>
  <keyframe time="0.6" value="95 95" interpType="bezier">
    <temporalEase inSpeed="-40 -40" inInfluence="8.33 8.33" outSpeed="10 10" outInfluence="8.33 8.33"/>
  </keyframe>
  <keyframe time="0.75" value="102 102" interpType="bezier">
    <temporalEase inSpeed="10 10" inInfluence="8.33 8.33" outSpeed="-5 -5" outInfluence="8.33 8.33"/>
  </keyframe>
  <keyframe time="0.85" value="99 99" interpType="bezier">
    <temporalEase inSpeed="-5 -5" inInfluence="8.33 8.33" outSpeed="0 0" outInfluence="8.33 8.33"/>
  </keyframe>
  <keyframe time="1.0" value="100 100" interpType="linear"/>
</property>
```

此预设实现了0%→120%→95%→102%→99%→100%的弹性缩放动画。

#### 解析关键帧缓动（temporalEase）

缓动数据决定了关键帧间的插值曲线：

```
temporalEase参数解读：
┌────────────────────────────────────────────┐
│  inSpeed    : 前一关键帧到此帧的入速度      │
│  outSpeed   : 此帧到下一关键帧的出速度      │
│  inInfluence: 入方向影响范围（百分比×0.01）  │
│  outInfluence: 出方向影响范围（百分比×0.01） │
│                                            │
│  速度=0 → 平滑停止                         │
│  速度≠0 → 持续运动                         │
│  影响范围越大 → 缓动越柔和                  │
└────────────────────────────────────────────┘
```

常见缓动模式对应的temporalEase值：

| 缓动类型 | inSpeed | outSpeed | inInfluence | outInfluence |
|----------|---------|----------|-------------|--------------|
| 线性 | 不设置 | 不设置 | - | - |
| 缓入（Ease In） | 0 | N/A | 33.33 | N/A |
| 缓出（Ease Out） | N/A | 0 | N/A | 33.33 |
| 缓入缓出 | 0 | 0 | 33.33 | 33.33 |
| 弹性过冲 | 负值 | 正值 | 小值 | 小值 |

#### 解析关键帧贝塞尔手柄

空间属性（如Position）的关键帧包含贝塞尔手柄：

```xml
<keyframe time="0" value="0 540" interpType="bezier">
  <spatialBezier>
    <inTangent x="0" y="0"/>
    <outTangent x="320" y="0"/>
  </spatialBezier>
  <temporalEase inSpeed="0 0" inInfluence="0 0" outSpeed="960 0" outInfluence="33.33 33.33"/>
</keyframe>
```

`outTangent`定义出方向切线，控制运动路径的弯曲方向。

#### 解析空间关键帧（spatial properties）

空间属性（Position、Anchor Point）的关键帧有三种空间插值模式：

| 模式 | .ffx标记 | 行为 |
|------|----------|------|
| 线性 | 无贝塞尔数据 | 关键帧间直线运动 |
| 自动贝塞尔 | `<spatialBezier>` + 自动切线 | 平滑曲线路径 |
| 连续贝塞尔 | `<spatialBezier>` + 手动切线 | 可手动调整曲线 |

#### 解析循环和保持关键帧

```xml
<!-- 保持关键帧（Hold Keyframe）-->
<keyframe time="0" value="100" interpType="hold"/>

<!-- 循环表达式 -->
<property id="ADBE Rotate Z">
  <expression>loopOut("cycle")</expression>
  <keyframe time="0" value="0" interpType="linear"/>
  <keyframe time="1" value="360" interpType="linear"/>
</property>
```

---

### 2.4 文字动画预设解析

#### 文字动画器结构

文字动画器在.ffx中以嵌套的`<property>`结构表示：

```
文字图层属性结构：
ADBE Text Properties
  └─ ADBE Text Animators
       └─ ADBE Text Animator           ← 动画器
            ├─ ADBE Text Animator Properties
            │    └─ ADBE Text Position 3D  ← 动画属性
            ├─ ADBE Text Selectors
            │    └─ ADBE Text Range Selector 1  ← 选择器
            │         ├─ ADBE Text Range Start
            │         ├─ ADBE Text Range End
            │         ├─ ADBE Text Range Offset
            │         └─ ADBE Text Range Units
            └─ ADBE Text More Options
```

#### 选择器参数

| 参数 | Match Name | 说明 | 典型值 |
|------|-----------|------|--------|
| Start | ADBE Text Range Start | 选择范围起始 | 0% |
| End | ADBE Text Range End | 选择范围结束 | 100% |
| Offset | ADBE Text Range Offset | 范围偏移 | 关键帧0→100% |
| Units | ADBE Text Range Units | 单位模式 | 百分比/索引 |
| Based On | ADBE Text Range Based On | 基于对象 | 字符/词/行 |
| Mode | ADBE Text Range Mode | 混合模式 | Add/Subtract/Intersect |
| Amount | ADBE Text Range Amount | 作用量 | 0-100% |
| Shape | ADBE Text Range Shape | 选择器形状 | Square/Round/Ramp/Smooth |
| Ease High | ADBE Text Range Ease High | 缓入 | 0-100% |
| Ease Low | ADBE Text Range Ease Low | 缓出 | 0-100% |

#### 动画属性参数

| 动画属性 | Match Name | 关键帧参数 |
|----------|-----------|-----------|
| 位置 | ADBE Text Position 3D | [x, y, z] |
| 缩放 | ADBE Text Scale | [sx, sy] |
| 旋转 | ADBE Text Rotation | 角度值 |
| 不透明度 | ADBE Text Opacity | 0-100% |
| 填充色 | ADBE Text Fill Color | RGB |
| 描边色 | ADBE Text Stroke Color | RGB |
| 字间距 | ADBE Text Tracking | 数值 |
| 行锚点 | ADBE Text Line Anchor | -100~100% |
| 字符偏移 | ADBE Text Char Offset | 0-255 |
| 字符值 | ADBE Text Char Value | Unicode值 |
| 模糊 | ADBE Text Blur | [x, y] |

#### 常见文字预设类型

**打字机效果**：
```
动画器：1个
选择器：Range Selector
  - Start: 0%（固定）
  - End: 0%→100%（关键帧，每帧+1字）
  - Offset: 0%
  - Units: Index
  - Based On: Characters
动画属性：Opacity = 0%（选择器未覆盖区域为0）
```

**淡入滑动效果**：
```
动画器：1个
选择器：Range Selector
  - Start: 0%
  - End: 100%
  - Offset: -100%→100%（关键帧，缓动）
  - Shape: Ramp Up
  - Ease High: 0%
  - Ease Low: 50%
动画属性：
  - Opacity: 0%
  - Position Y: 30（向上滑入）
```

**缩放弹跳效果**：
```
动画器：1个
选择器：Range Selector
  - Offset: -100%→100%
  - Shape: Round
动画属性：
  - Scale: 0%
  - Rotation: -5°（微旋）
```

---

## 三、MOGRT模板深度解析

### 3.1 MOGRT内部结构

#### 双层ZIP解压方法

MOGRT本质是一个ZIP压缩包，内部结构：

```
my_template.mogrt (ZIP Layer 1)
├── [Content_Types].xml
├── _rels/
│   └── .rels
├── Project.aegraphic (ZIP Layer 2)
│   ├── project.aep        ← AE项目文件
│   ├── essentialgraphics/  ← EGP控件定义
│   │   └── *.json
│   ├── fonts/              ← 嵌入字体
│   │   └── *.ttf / *.otf
│   ├── assets/             ← 嵌入素材
│   │   ├── images/
│   │   └── videos/
│   └── scripts/            ← 嵌入脚本
│       └── *.jsx
└── metadata/
    └── xmp.xml             ← XMP元数据
```

**解压步骤**：

1. 将`.mogrt`重命名为`.zip`，解压第一层
2. 找到`Project.aegraphic`，再次重命名为`.zip`，解压第二层
3. 第二层中的`project.aep`即为完整AE项目

```javascript
// ExtendScript自动解压MOGRT
function extractMogrt(mogrtPath, outputDir) {
    var mogrt = new File(mogrtPath);
    var dest = new Folder(outputDir);
    if (!dest.exists) dest.create();

    // 第一层解压
    var cmd1 = 'powershell -Command "Expand-Archive -Path \'' +
               mogrt.fsName + '\' -DestinationPath \'' +
               dest.fsName + '\\layer1\' -Force"';

    // 第二层解压
    var aegraphic = new File(dest.fsName + '\\layer1\\Project.aegraphic');
    if (aegraphic.exists) {
        var cmd2 = 'powershell -Command "Expand-Archive -Path \'' +
                   aegraphic.fsName + '\' -DestinationPath \'' +
                   dest.fsName + '\\layer2\' -Force"';
    }

    system.callSystem(cmd1);
    if (aegraphic.exists) system.callSystem(cmd2);
}
```

#### Project.aegraphic内部文件详解

| 文件/目录 | 说明 | 用途 |
|-----------|------|------|
| `project.aep` | AE项目文件 | 包含完整合成、图层、效果、表达式 |
| `essentialgraphics/` | EGP定义目录 | 控件类型、范围、默认值定义 |
| `fonts/` | 字体目录 | 嵌入的TTF/OTF字体文件 |
| `assets/` | 素材目录 | 嵌入的图片、视频等资源 |
| `scripts/` | 脚本目录 | 预设内嵌的ExtendScript脚本 |

#### XMP元数据解析（EGP控件定义）

XMP元数据定义了Essential Graphics面板的控件结构：

```xml
<x:xmpmeta>
  <rdf:RDF>
    <rdf:Description>
      <egp:essentialGraphics>
        <egp:property>
          <egp:name>Title Text</egp:name>
          <egp:type>sourceText</egp:type>
          <egp:displayName>Title</egp:displayName>
          <egp:default>Sample Text</egp:default>
        </egp:property>
        <egp:property>
          <egp:name>Color Control</egp:name>
          <egp:type>color</egp:type>
          <egp:displayName>Accent Color</egp:displayName>
          <egp:default>#FF5733</egp:default>
        </egp:property>
        <egp:property>
          <egp:name>Slider 1</egp:name>
          <egp:type>slider</egp:type>
          <egp:displayName>Intensity</egp:displayName>
          <egp:default>50</egp:default>
          <egp:min>0</egp:min>
          <egp:max>100</egp:max>
        </egp:property>
      </egp:essentialGraphics>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
```

#### 嵌入资源：字体/图片/视频/脚本

- **字体嵌入**：MOGRT创建时勾选"Include Fonts"，字体文件打包进aegraphic
- **图片/视频**：合成中引用的本地素材可选择嵌入
- **脚本**：通过脚本面板关联的.jsx文件自动嵌入

---

### 3.2 Essential Graphics控件映射

AE中添加的Essential Graphics控件与脚本访问路径的完整映射：

| EGP控件 | AE中的控件层 | Match Name | 脚本访问路径 | 值类型 |
|---------|-------------|-----------|-------------|--------|
| 文本控件 | Source Text | ADBE Text Properties | `layer.property("Source Text")` | TextDocument |
| 颜色控件 | Color属性 | ADBE Color Control | `effect("Color Control").property(1)` | [r,g,b,a] 0-1 |
| 滑块控件 | Slider Control | ADBE Slider Control | `effect("Slider Control").property(1)` | Number 0-100 |
| 角度控件 | Angle Control | ADBE Angle Control | `effect("Angle Control").property(1)` | Number 0-360 |
| 点控件 | Point Control | ADBE Point Control | `effect("Point Control").property(1)` | [x,y] |
| 复选框控件 | Checkbox Control | ADBE Checkbox Control | `effect("Checkbox Control").property(1)` | 0 or 1 |
| 媒体替换 | Footage图层 | ADBE AV Layer | `layer.replaceSource(newFootage)` | FootageItem |
| 下拉菜单 | Dropdown Menu Control | ADBE Dropdown | `effect("Dropdown Menu Control").property(1)` | Index (0-based) |

**脚本操作示例**：

```javascript
// 读取MOGRT控件值
function readMogrtControls(comp) {
    var layer = comp.layer(1);
    var results = [];

    // 遍历所有效果（控件作为效果添加）
    var effects = layer.property("ADBE Effect Parade");
    for (var i = 1; i <= effects.numProperties; i++) {
        var effect = effects.property(i);
        var matchName = effect.matchName;
        var name = effect.name;
        var value;

        if (matchName === "ADBE Slider Control") {
            value = effect.property(1).value;
            results.push({type: "slider", name: name, value: value});
        } else if (matchName === "ADBE Color Control") {
            value = effect.property(1).value;
            results.push({type: "color", name: name, value: value});
        } else if (matchName === "ADBE Angle Control") {
            value = effect.property(1).value;
            results.push({type: "angle", name: name, value: value});
        } else if (matchName === "ADBE Point Control") {
            value = effect.property(1).value;
            results.push({type: "point", name: name, value: value});
        } else if (matchName === "ADBE Checkbox Control") {
            value = effect.property(1).value;
            results.push({type: "checkbox", name: name, value: value});
        } else if (matchName === "ADBE Dropdown") {
            value = effect.property(1).value;
            results.push({type: "dropdown", name: name, value: value});
        }
    }
    return results;
}
```

---

### 3.3 MOGRT参数逆向工程

#### 从.mogrt提取.aep的方法

```
步骤1：复制.mogrt文件
步骤2：重命名扩展名为.zip
步骤3：解压ZIP（7-Zip / 系统解压）
步骤4：找到Project.aegraphic文件
步骤5：重命名.aegraphic为.zip
步骤6：再次解压
步骤7：得到project.aep，用AE打开
```

> **注意**：部分商业MOGRT可能使用加密或混淆处理，此时aegraphic内容可能无法正常提取。

#### 提取表达式代码

从提取的.aep中，选中图层→效果→查看各属性的表达式。也可通过脚本批量提取：

```javascript
// 批量提取合成中所有表达式
function extractAllExpressions(comp) {
    var expressions = [];
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        extractExpressionsFromProperty(layer, expressions, layer.name);
    }
    return expressions;
}

function extractExpressionsFromProperty(prop, results, layerName) {
    if (prop.propertyType === PropertyType.PROPERTY) {
        if (prop.canSetExpression && prop.expression !== "") {
            results.push({
                layer: layerName,
                property: prop.name,
                expression: prop.expression
            });
        }
    } else if (prop.propertyType === PropertyType.INDEXED_GROUP ||
               prop.propertyType === PropertyType.NAMED_GROUP) {
        for (var j = 1; j <= prop.numProperties; j++) {
            extractExpressionsFromProperty(
                prop.property(j), results, layerName
            );
        }
    }
}
```

#### 提取嵌入资源

```
从解压的aegraphic目录中：
├── fonts/       → 复制字体文件到系统字体目录安装
├── assets/      → 复制素材到工作目录
└── scripts/     → 复制.jsx文件查看脚本逻辑
```

#### 分析控件与表达式的映射关系

MOGRT的核心机制是：EGP控件 → 效果控件属性 → 表达式引用 → 驱动目标属性

```
映射链示例：
EGP面板"Intensity"滑块
  → Slider Control效果.property("Slider")
    → 其他属性的表达式引用: effect("Slider Control")("Slider")
      → 驱动: Glow Intensity / Blur Amount / Scale等
```

**分析方法**：
1. 在EGP面板中记录每个控件名称
2. 在AE中找到对应的Slider/Color/Checkbox效果
3. 搜索所有表达式，查找引用该效果名的表达式
4. 绘制控件→表达式的映射关系图

#### 修改和定制MOGRT

修改MOGRT的完整流程：

1. 提取.aep并打开
2. 修改合成内容（效果参数、表达式、控件范围）
3. 重新通过File → Export → Motion Graphics Template导出
4. 在PR中替换原MOGRT测试

---

## 四、调色预设/LUT深度解析

### 4.1 LUT格式详解

#### .3dl格式

3DL是Autodesk Lustre和Resolve使用的LUT格式，以文本存储3D LUT网格：

```
# 示例3DL文件结构
# 网格尺寸声明
3 32

# 输入范围映射（从暗到亮）
0 128 255 512 1024 2048 4096

# LUT数据（R G B → R' G' B'）
0 0 0 0 2 4
0 0 1 0 3 5
0 0 2 1 4 6
...
```

| 特性 | 说明 |
|------|------|
| 编码 | ASCII文本 |
| 网格 | 可变尺寸（17/32/64等） |
| 输入范围 | 可自定义 |
| 兼容性 | Resolve、Lustre、AE（通过Lumetri） |

#### .cube格式

CUBE是Adobe推荐的LUT标准格式，由IRIDAS开发：

```
# 示例CUBE文件
TITLE "Teal & Orange"
LUT_3D_SIZE 33
DOMAIN_MIN 0.0 0.0 0.0
DOMAIN_MAX 1.0 1.0 1.0

# LUT数据行：R_in G_in B_in → R_out G_out B_out
0.000000 0.000000 0.000000
0.000000 0.000000 0.030303
0.000000 0.000000 0.062500
...
```

| 特性 | 说明 |
|------|------|
| 编码 | ASCII文本 |
| 网格 | 可变尺寸（通常17/33/65） |
| 范围 | 0.0-1.0浮点（可自定义DOMAIN） |
| 兼容性 | AE、PR、Resolve、Nuke、DaVinci等 |

#### .look格式

LOOK是Adobe SpeedGrade/Lumetri的专有格式，基于LUT + 额外调色参数：

```
# LOOK文件内部包含：
1. 基础3D LUT数据
2. Primary调色参数（Lift/Gamma/Gain）
3. Secondary调色参数（限定颜色范围调整）
4. Curves数据
5. 输入/输出色彩空间转换
```

#### .mga格式

MGA是Magic Bullet Looks的预设格式，包含完整的Looks调色链：

```
MGA文件结构：
├── Subject（主体处理）
│   ├── Exposure
│   ├── Spot Exposure
│   └── Chromatic Aberration
├── Matte（蒙版处理）
│   ├── Vignette
│   └── Edge Softness
├── Lens（镜头处理）
│   ├── Distortion
│   └── Flare
├── Camera（相机处理）
│   ├── Curves
│   └── Color Temperature
└── Post（后期处理）
    ├── Grain
    └── Letterbox
```

#### 各格式参数解析方法

| 格式 | 解析工具 | 解析方法 |
|------|----------|----------|
| .3dl | 文本编辑器 | 读取网格数据和输入范围映射 |
| .cube | 文本编辑器 | 读取LUT_3D_SIZE和数据行 |
| .look | SpeedGrade/AE Lumetri | 仅能通过Lumetri加载，内部为XML |
| .mga | Magic Bullet Looks | 通过MBL插件界面加载和编辑 |

---

### 4.2 调色预设参数结构

#### 输入范围映射

LUT定义了输入颜色到输出颜色的映射关系。输入范围决定了LUT覆盖的色域：

```
输入颜色空间                    LUT映射                    输出颜色空间
┌───────────┐              ┌───────────┐              ┌───────────┐
│ 0-255 RGB │───索引查找──→│ 3D LUT网格 │───映射值───→│ 新RGB值   │
│ (0.0-1.0) │              │ R×G×B节点 │              │ (0.0-1.0) │
└───────────┘              └───────────┘              └───────────┘

DOMAIN_MIN定义暗部起始点
DOMAIN_MAX定义亮部终止点
超出范围的值被裁剪
```

#### 输出颜色映射

LUT的每个节点定义一个输入RGB到输出RGB的映射：

```
CUBE格式示例（3×3×3网格简化）：
输入RGB          输出RGB
(0, 0, 0)    →   (0.00, 0.02, 0.05)    ← 暗部偏青
(0.5, 0.5, 0.5) → (0.45, 0.50, 0.55)   ← 中间调微调
(1, 1, 1)    →   (0.95, 0.93, 0.90)    ← 高光偏暖
```

#### 3D LUT网格结构

3D LUT是一个三维数组，每个维度对应R/G/B一个通道：

```
3D LUT网格尺寸 = N × N × N
N = 17时：17×17×17 = 4,913个数据点
N = 33时：33×33×33 = 35,937个数据点
N = 65时：65×65×65 = 274,625个数据点

数据点越多 → 颜色映射越精确 → 文件越大
N=17是AE/PR的常用尺寸（精度与性能的平衡）
```

CUBE文件中数据按B→G→R顺序排列（最快变化到最慢变化）：

```
for b = 0 to N-1:
  for g = 0 to N-1:
    for r = 0 to N-1:
      write LUT[r][g][b]
```

#### 1D LUT vs 3D LUT

| 特性 | 1D LUT | 3D LUT |
|------|--------|--------|
| 维度 | 3个独立1D表（R/G/B各一） | 1个3D表 |
| 通道相关性 | ❌ 独立处理 | ✅ 通道间有交叉映射 |
| 色彩调整 | 仅亮度/对比度/白平衡 | 任意色彩变换 |
| 数据量 | 3×N（通常3×1024） | N³（通常33³=35,937） |
| 精度 | 高（每通道1024+节点） | 依赖网格尺寸 |
| 典型用途 | Gamma转换、Log→Linear | 创意调色、风格化Look |

---

### 4.3 常用调色预设参数表

#### Teal & Orange

| 参数 | 数值 | 范围 | 说明 |
|------|------|------|------|
| Lumetri - Temperature | +15 | -100~100 | 整体偏暖 |
| Lumetri - Tint | -5 | -100~100 | 微调绿色通道 |
| Lumetri - Highlights | +10 | -100~100 | 提升高光 |
| Lumetri - Shadows | -8 | -100~100 | 压暗阴影 |
| Lumetri - Hue vs Hue (Orange区) | +8° | -180°~180° | 橙色色相偏移 |
| Lumetri - Hue vs Sat (Teal区) | +35 | -100~100 | 青色饱和度提升 |
| Lumetri - Hue vs Sat (Skin区) | +15 | -100~100 | 肤色饱和度提升 |
| Curves - RGB Master | S曲线 | - | 对比度增强 |
| Curves - Red Channel | 高光提亮 | - | 暖色高光 |
| Curves - Blue Channel | 暗部压低 | - | 冷色阴影 |
| LUT 3D Size | 33 | - | 映射精度 |

#### Cinematic Look

| 参数 | 数值 | 范围 | 说明 |
|------|------|------|------|
| Lumetri - Temperature | +8 | -100~100 | 微暖色温 |
| Lumetri - Contrast | +25 | -100~100 | 增强对比 |
| Lumetri - Highlights | -12 | -100~100 | 压高光保留细节 |
| Lumetri - Shadows | +8 | -100~100 | 提阴影保留细节 |
| Lumetri - Whites | -5 | -100~100 | 柔化白峰 |
| Lumetri - Blacks | +5 | -100~100 | 提黑不纯黑 |
| Lumetri - Saturation | -15 | -100~100 | 降低整体饱和 |
| Curves - Master | Soft S | - | 胶片S曲线 |
| Curves - Blue Shadow Lift | +5 | - | 阴影偏蓝 |
| Vignette Amount | -30 | - | 暗角 |

#### Vintage Film

| 参数 | 数值 | 范围 | 说明 |
|------|------|------|------|
| Lumetri - Temperature | +25 | -100~100 | 暖色温偏移 |
| Lumetri - Contrast | -10 | -100~100 | 降低对比（褪色感） |
| Lumetri - Highlights | +5 | -100~100 | 轻微过曝 |
| Lumetri - Shadows | +15 | -100~100 | 提阴影（低对比） |
| Lumetri - Saturation | -25 | -100~100 | 显著降饱和 |
| Lumetri - Faded Film | +30 | 0~100 | 褪色效果 |
| Curves - Master | 趾部抬升 | - | 黑场不纯黑 |
| Curves - Red | 高光加红 | - | 肤色偏暖 |
| Film Grain Amount | 15% | 0~100% | 胶片颗粒 |
| Color Halation | +10 | 0~100 | 彩色光晕 |

#### Cyberpunk

| 参数 | 数值 | 范围 | 说明 |
|------|------|------|------|
| Lumetri - Temperature | -30 | -100~100 | 冷色温 |
| Lumetri - Tint | +20 | -100~100 | 偏品红 |
| Lumetri - Contrast | +35 | -100~100 | 高对比 |
| Lumetri - Saturation | +20 | -100~100 | 高饱和 |
| Lumetri - Hue vs Hue (Cyan) | +15° | -180°~180° | 青色偏移 |
| Lumetri - Hue vs Hue (Magenta) | -10° | -180°~180° | 品红偏移 |
| Curves - Blue | 高光提亮 | - | 霓虹蓝高光 |
| Curves - Red | 中间调提亮 | - | 品红中间调 |
| Chromatic Aberration | +3px | 0~20px | 色差 |
| Scan Lines Opacity | 8% | 0~100% | 扫描线 |

#### Noir

| 参数 | 数值 | 范围 | 说明 |
|------|------|------|------|
| Lumetri - Saturation | -100 | -100~100 | 完全去色 |
| Lumetri - Contrast | +40 | -100~100 | 高对比 |
| Lumetri - Highlights | -15 | -100~100 | 压高光 |
| Lumetri - Shadows | -20 | -100~100 | 深阴影 |
| Curves - Master | 陡峭S曲线 | - | 极端明暗对比 |
| Curves - Blue Lift | +3 | - | 微量冷色调 |
| Vignette Amount | -45 | - | 强暗角 |
| Film Grain | 10% | 0~100% | 颗粒感 |
| Glow Threshold | 200 | 0~255 | 仅最亮部发光 |

---

## 五、预设实战调用方法

### 5.1 手动调用预设

#### 效果预设应用步骤

1. 选中目标图层
2. 打开Effects & Presets面板（Ctrl+5 / Cmd+5）
3. 在搜索栏输入预设名称或效果名
4. 双击预设或拖拽到图层上应用
5. 在Effect Controls面板调整参数

#### 动画预设应用步骤

1. 选中目标图层（确保时间指示器在正确位置）
2. 在Effects & Presets面板展开*Animation Presets*
3. 找到目标动画预设
4. 双击应用（关键帧从当前时间开始）

> **注意**：动画预设的应用起点由当前时间指示器位置决定，应用前务必将时间线定位到目标起始帧。

#### 预设修改与自定义

1. 应用预设后，在Effect Controls或Timeline面板修改参数
2. 选中修改后的效果或属性组
3. 执行Animation > Save Animation Preset
4. 选择保存位置（建议用户预设目录）
5. 命名并保存

#### 保存自定义预设

保存位置选择策略：

| 保存位置 | 可见性 | 升级保留 | 推荐场景 |
|----------|--------|----------|----------|
| 用户预设目录 | 仅当前版本 | ❌ 版本升级可能丢失 | 个人临时预设 |
| 系统预设目录 | 所有用户 | ❌ 需重新安装 | 团队共享预设 |
| 自定义目录 | 需手动导入 | ✅ 永久保留 | 长期项目预设 |
| 项目内嵌 | 仅当前项目 | ✅ 随项目迁移 | 项目专属预设 |

---

### 5.2 脚本调用预设（ExtendScript）

#### applyPreset()方法详解

AE ExtendScript中应用预设的方法：

```javascript
// 方法1：通过属性应用预设
layer.property("ADBE Effect Parade").property(1).applyPreset(presetFile);

// 方法2：通过图层应用预设（应用到整个图层）
layer.applyPreset(presetFile);
```

**applyPreset()参数与行为**：

| 调用对象 | 行为 | 注意事项 |
|----------|------|----------|
| 单个效果属性 | 替换该属性的参数值 | 不影响其他效果 |
| 效果组（Effect Parade） | 在效果列表末尾添加预设中的效果 | 不替换现有效果 |
| 图层 | 应用预设到图层 | 包含效果+关键帧+表达式 |

#### 批量应用预设脚本

```javascript
// 批量应用效果预设到选中图层
function batchApplyPreset(presetPath) {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        alert("请先选中一个合成");
        return;
    }

    var presetFile = new File(presetPath);
    if (!presetFile.exists) {
        alert("预设文件不存在: " + presetPath);
        return;
    }

    var layers = comp.selectedLayers;
    if (layers.length === 0) {
        alert("请先选中至少一个图层");
        return;
    }

    app.beginUndoGroup("批量应用预设");

    for (var i = 0; i < layers.length; i++) {
        try {
            layers[i].applyPreset(presetFile);
        } catch (e) {
            alert("图层 " + layers[i].name + " 应用预设失败: " + e.toString());
        }
    }

    app.endUndoGroup();
    presetFile.close();
}

// 使用示例
batchApplyPreset("C:/Users/Administrator/AppData/Roaming/Adobe/After Effects/26.0/UserPresets/MyGlow.ffx");
```

#### 预设参数读取与修改

```javascript
// 读取效果预设文件中的参数值
function readPresetParams(presetPath) {
    var file = new File(presetPath);
    if (!file.exists) return null;

    file.open("r");
    var content = file.read();
    file.close();

    // 解析XML提取参数
    var params = [];
    var propRegex = /<property id="([^"]+)">\s*<value[^>]*>([^<]*)<\/value>/g;
    var match;

    while ((match = propRegex.exec(content)) !== null) {
        params.push({
            matchName: match[1],
            value: match[2]
        });
    }

    return params;
}

// 修改已应用效果的参数
function modifyEffectParams(layer, effectIndex, paramValues) {
    var effect = layer.property("ADBE Effect Parade").property(effectIndex);

    for (var i = 0; i < paramValues.length; i++) {
        var param = effect.property(paramValues[i].index);
        if (param && param.canSetValue) {
            param.setValue(paramValues[i].value);
        }
    }
}

// 完整代码示例：应用效果预设并修改参数
function applyAndModifyPreset() {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) return;

    var layer = comp.layer(1);

    // 添加Gaussian Blur效果
    var effect = layer.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");

    // 设置参数
    effect.property("ADBE Gaussian Blur 2-0001").setValue(25);  // Blurriness = 25
    effect.property("ADBE Gaussian Blur 2-0002").setValue(1);   // Repeat = 1

    // 应用预设覆盖参数
    var presetFile = File("~/Desktop/MyBlurPreset.ffx");
    if (presetFile.exists) {
        layer.applyPreset(presetFile);
    }
    presetFile.close();
}
```

---

### 5.3 表达式调用预设参数

#### 通过表达式引用控制器参数

```javascript
// 在效果属性上添加表达式，引用Slider Control
// 应用到: Glow > Intensity
effect("Glow")("Intensity") = effect("Slider Control")("Slider");

// 引用Color Control
// 应用到: Glow > Color
effect("Glow")("Color") = effect("Color Control")("Color");

// 引用Angle Control
// 应用到: Transform > Rotation
transform.rotation = effect("Angle Control")("Angle");

// 引用Checkbox Control实现开关
if (effect("Checkbox Control")("Checkbox") == 1) {
    effect("Glow")("Intensity");
} else {
    0;
}
```

#### 通过表达式实现预设效果

```javascript
// 弹性缩放表达式（替代关键帧预设）
// 应用到: Scale属性
var freq = 3;    // 弹性频率
var decay = 5;   // 衰减速度
var n = 0;
var t = 0;
if (numKeys > 0) {
    n = nearestKey(time).index;
    if (key(n).time > time) n--;
}
if (n > 0) {
    t = time - key(n).time;
    var v = velocityAtTime(key(n).time - 0.001);
    var amp = Math.abs(v) / (2 * Math.PI * freq);
    var w = freq * 2 * Math.PI;
    value + v / w * Math.sin(w * t) * Math.exp(-decay * t);
} else {
    value;
}
```

#### 表达式预设库设计

```javascript
// 表达式预设库：统一管理和调用常用表达式
var EXPR_PRESETS = {
    // 弹性过冲
    overshoot: {
        name: "弹性过冲",
        params: ["freq", "decay"],
        defaults: {freq: 3, decay: 5},
        code: function(p) {
            return 'var freq = ' + p.freq + '; ' +
                   'var decay = ' + p.decay + '; ' +
                   'var n = 0; var t = 0; ' +
                   'if (numKeys > 0) { ' +
                   '  n = nearestKey(time).index; ' +
                   '  if (key(n).time > time) n--; ' +
                   '} ' +
                   'if (n > 0) { ' +
                   '  t = time - key(n).time; ' +
                   '  var v = velocityAtTime(key(n).time - 0.001); ' +
                   '  var w = freq * 2 * Math.PI; ' +
                   '  value + v / w * Math.sin(w * t) * Math.exp(-decay * t); ' +
                   '} else { value; }';
        }
    },
    // 弹性回弹
    bounce: {
        name: "弹性回弹",
        params: ["e", "g"],
        defaults: {e: 0.7, g: 5},
        code: function(p) {
            return 'var e = ' + p.e + '; ' +
                   'var g = ' + p.g + '; ' +
                   'var n = 0; var t = 0; ' +
                   'if (numKeys > 0) { ' +
                   '  n = nearestKey(time).index; ' +
                   '  if (key(n).time > time) n--; ' +
                   '} ' +
                   'if (n > 0) { ' +
                   '  t = time - key(n).time; ' +
                   '  var v = -velocityAtTime(key(n).time + 0.001); ' +
                   '  var vl = length(v); ' +
                   '  if (vl > 0) { ' +
                   '    var nMax = Math.ceil(Math.log(0.01) / Math.log(e)); ' +
                   '    var totalT = 0; ' +
                   '    for (var i = 0; i < nMax; i++) { ' +
                   '      totalT += 2 * vl * Math.pow(e, i) / g; ' +
                   '    } ' +
                   '    if (t < totalT) { ' +
                   '      var ct = 0; ' +
                   '      for (var i = 0; i < nMax; i++) { ' +
                   '        var dur = 2 * vl * Math.pow(e, i) / g; ' +
                   '        if (t < ct + dur) { ' +
                   '          value + (vl * Math.pow(e, i)) / g * Math.sin(Math.PI * (t - ct) / (dur / 2)); ' +
                   '          break; ' +
                   '        } ' +
                   '        ct += dur; ' +
                   '      } ' +
                   '    } else { value; } ' +
                   '  } else { value; } ' +
                   '} else { value; }';
        }
    },
    // 循环
    loop: {
        name: "循环",
        params: ["type", "nKeyframes"],
        defaults: {type: "cycle", nKeyframes: 2},
        code: function(p) {
            return 'loopOut("' + p.type + '", ' + p.nKeyframes + ')';
        }
    },
    // 抖动
    wiggle: {
        name: "抖动",
        params: ["freq", "amp"],
        defaults: {freq: 2, amp: 10},
        code: function(p) {
            return 'wiggle(' + p.freq + ', ' + p.amp + ')';
        }
    }
};

// 应用表达式预设
function applyExpressionPreset(prop, presetName, params) {
    if (!prop.canSetExpression) return false;

    var preset = EXPR_PRESETS[presetName];
    if (!preset) return false;

    var mergedParams = {};
    for (var k in preset.defaults) {
        mergedParams[k] = preset.defaults[k];
    }
    if (params) {
        for (var k2 in params) {
            mergedParams[k2] = params[k2];
        }
    }

    prop.expression = preset.code(mergedParams);
    return true;
}
```

---

### 5.4 MCP桥接调用预设

#### 通过MCP Bridge远程应用预设

MCP Bridge允许外部系统（如AI助手）通过JSON-RPC协议远程控制AE，实现预设的自动化应用：

```javascript
// MCP Bridge预设应用处理器（运行在AE端）
function handlePresetApply(params) {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        return {success: false, error: "无活动合成"};
    }

    var layerIndex = params.layerIndex || 1;
    var layer = comp.layer(layerIndex);
    if (!layer) {
        return {success: false, error: "图层不存在"};
    }

    app.beginUndoGroup("MCP Apply Preset");

    try {
        // 方式1：通过预设文件路径应用
        if (params.presetPath) {
            var presetFile = new File(params.presetPath);
            if (presetFile.exists) {
                layer.applyPreset(presetFile);
                presetFile.close();
            }
        }

        // 方式2：通过效果参数直接构建
        if (params.effects) {
            var effectParade = layer.property("ADBE Effect Parade");
            for (var i = 0; i < params.effects.length; i++) {
                var effectDef = params.effects[i];
                var effect = effectParade.addProperty(effectDef.matchName);
                effect.name = effectDef.name || effect.name;

                // 设置参数
                if (effectDef.params) {
                    for (var j = 0; j < effectDef.params.length; j++) {
                        var param = effectDef.params[j];
                        var prop = effect.property(param.index);
                        if (prop && prop.canSetValue) {
                            if (param.value instanceof Array) {
                                prop.setValue(param.value);
                            } else {
                                prop.setValue(param.value);
                            }
                        }
                    }
                }

                // 添加表达式
                if (effectDef.expressions) {
                    for (var k = 0; k < effectDef.expressions.length; k++) {
                        var expr = effectDef.expressions[k];
                        var exprProp = effect.property(expr.index);
                        if (exprProp && exprProp.canSetExpression) {
                            exprProp.expression = expr.code;
                        }
                    }
                }
            }
        }

        app.endUndoGroup();
        return {success: true, message: "预设应用成功"};

    } catch (e) {
        app.endUndoGroup();
        return {success: false, error: e.toString()};
    }
}
```

#### 预设参数JSON格式定义

MCP Bridge传输预设参数的标准JSON格式：

```json
{
    "action": "applyPreset",
    "compName": "Main Comp",
    "layerIndex": 1,
    "effects": [
        {
            "matchName": "ADBE Glo2",
            "name": "Glow",
            "params": [
                {"index": 1, "name": "Threshold", "value": 25},
                {"index": 2, "name": "Radius", "value": 80},
                {"index": 3, "name": "Intensity", "value": 150},
                {"index": 4, "name": "Color", "value": [1, 0.8, 0.3, 1]}
            ],
            "expressions": [
                {"index": 3, "code": "effect('Slider Control')('Slider')"}
            ]
        },
        {
            "matchName": "ADBE Gaussian Blur 2",
            "name": "Gaussian Blur",
            "params": [
                {"index": 1, "name": "Blurriness", "value": 15},
                {"index": 2, "name": "Blur Dimensions", "value": 0}
            ]
        }
    ],
    "keyframes": [
        {
            "property": "ADBE Transform Group/ADBE Scale",
            "keys": [
                {"time": 0, "value": [0, 0], "easeOut": [0, 0]},
                {"time": 0.5, "value": [120, 120], "easeIn": [0, 0], "easeOut": [0, 0]},
                {"time": 0.8, "value": [100, 100], "easeIn": [0, 0]}
            ]
        }
    ]
}
```

#### 自动化预设应用流程

```
AI助手                         MCP Bridge                     AE
  │                               │                           │
  │ 1.发送预设JSON                 │                           │
  ├──────────────────────────────→│                           │
  │                               │ 2.解析JSON                 │
  │                               │ 3.验证参数                 │
  │                               ├──────────────────────────→│
  │                               │                           │ 4.应用效果
  │                               │                           │ 5.设置参数
  │                               │                           │ 6.添加关键帧
  │                               │                           │ 7.添加表达式
  │                               │←──────────────────────────┤
  │                               │ 8.返回执行结果             │
  │←──────────────────────────────┤                           │
  │ 9.确认/微调                    │                           │
```

---

## 六、预设参数库（按风格分类）

### 6.1 战斗/硬核风格预设

#### 效果组合

Glow + Chromatic Aberration + Vignette + Radial Blur + Motion Blur

#### 完整参数表

| 效果名 | 参数名 | 数值 | 范围 | 说明 |
|--------|--------|------|------|------|
| **Glow** | Threshold | 50 | 0-255 | 高阈值只让亮部发光 |
| | Radius | 60 | 0-500 | 中等扩散半径 |
| | Intensity | 180 | 0-255 | 强发光强度 |
| | Color | [1, 0.9, 0.5, 1] | - | 暖黄发光色 |
| | Glow Operation | Add | 枚举 | 叠加模式 |
| | Glow Technique | Precise | 枚举 | 精确模式 |
| **CC Lens** | Size | 120 | 0-300 | 轻微鱼眼畸变 |
| | Curvature | -5 | -100~100 | 负值收缩 |
| | Convergence | 100 | 0-100 | 保持中心清晰 |
| **Vignette** | Amount | -60 | -100~100 | 强暗角 |
| | Size | 40 | 0-100 | 中等暗角范围 |
| | Roundness | 50 | 0-100 | 圆形暗角 |
| | Softness | 70 | 0-100 | 柔和边缘 |
| **Radial Blur** | Amount | 8 | 0-100 | 径向模糊量 |
| | Type | Zoom | 枚举 | 缩放式模糊 |
| | Center | [960, 540] | - | 画面中心 |
| **CC Force Motion Blur** | Amount | 0.8 | 0-1 | 运动模糊量 |
| | Samples | 8 | 2-64 | 采样数 |

#### 关键帧设置

```
缩放曲线（一拳出拳瞬间）：
时间    值          缓动
0.00s   100%        linear
0.05s   85%         ease out（蓄力收缩）
0.10s   135%        ease in（爆发放大）
0.20s   110%        ease（回弹）
0.30s   100%        ease（归位）

位置曲线（冲击偏移）：
时间    X偏移       Y偏移      缓动
0.00s   0           0          linear
0.10s   +80px       +20px      ease out（冲击方向）
0.20s   -10px       0          ease（回弹）
0.30s   0           0          ease（归位）

旋转曲线（冲击旋转）：
时间    值          缓动
0.00s   0°          linear
0.10s   3°          ease out
0.20s   -1°         ease
0.30s   0°          ease
```

#### 表达式设置

```javascript
// 冲击缩放表达式（配合关键帧使用）
var impactTime = 0.1;  // 冲击时刻
var decay = 8;
var freq = 4;
var t = time - impactTime;
if (t > 0) {
    var amp = 15;
    value + amp * Math.sin(freq * 2 * Math.PI * t) * Math.exp(-decay * t) * [1, 1];
} else {
    value;
}
```

#### 适用场景和调整指南

- **适用**：战斗打击、爆炸冲击、力量释放
- **调整**：Glow Intensity控制发光强度，Radial Blur Amount控制动感，Vignette Amount控制聚焦感
- **提示**：短时间（0.1-0.3秒）的Scale脉冲效果最佳，过长的冲击动画会显得拖沓

---

### 6.2 情感/治愈风格预设

#### 效果组合

Soft Focus + Warm Color + Vignette + Film Grain

#### 完整参数表

| 效果名 | 参数名 | 数值 | 范围 | 说明 |
|--------|--------|------|------|------|
| **Fast Box Blur** | Blurriness | 3 | 0-100 | 轻微柔焦 |
| | Repeat Edges | On | 开/关 | 边缘重复 |
| | Blur Dimensions | Horizontal & Vertical | 枚举 | 双向模糊 |
| **Lumetri Color** | Temperature | +20 | -100~100 | 暖色温 |
| | Tint | +5 | -100~100 | 微偏品 |
| | Highlights | +8 | -100~100 | 提升高光 |
| | Shadows | +10 | -100~100 | 提升阴影 |
| | Saturation | -8 | -100~100 | 微降饱和 |
| | Creative Look | Soft Warmth | - | 内置Look |
| **Vignette** | Amount | -30 | -100~100 | 柔和暗角 |
| | Size | 50 | 0-100 | 中等范围 |
| | Softness | 80 | 0-100 | 柔和过渡 |
| **Noise** | Amount of Noise | 3% | 0-100% | 微量胶片噪点 |
| | Noise Type | Soft Color | 枚举 | 柔和彩色噪点 |
| | Clipping | Off | 开/关 | 不裁剪 |

#### 关键帧设置

```
淡入动画：
时间    Opacity     缓动
0.00s   0%          linear
1.00s   100%        ease out（柔和淡入）

缩放呼吸：
时间    Scale       缓动
0.00s   100%        ease in out
3.00s   103%        ease in out
6.00s   100%        ease in out
（循环：loopOut("cycle")）
```

#### 适用场景和调整指南

- **适用**：回忆场景、温馨片段、治愈系内容
- **调整**：Blurriness控制柔焦程度，Temperature控制暖色程度，Vignette控制画面聚焦
- **提示**：配合慢速推拉（Scale 100→103%）和轻微的Opacity变化增强氛围感

---

### 6.3 科幻/赛博朋克风格预设

#### 效果组合

CC Glow + CC Lens + Scan Lines + Chromatic Aberration + Colorama

#### 完整参数表

| 效果名 | 参数名 | 数值 | 范围 | 说明 |
|--------|--------|------|------|------|
| **CC Glow** | Threshold | 80 | 0-255 | 中等阈值 |
| | Radius | 40 | 0-500 | 发光扩散 |
| | Intensity | 120 | 0-255 | 中等强度 |
| | Color | [0, 0.8, 1, 1] | - | 青色发光 |
| **CC Lens** | Size | 110 | 0-300 | 轻微畸变 |
| | Curvature | 8 | -100~100 | 正值膨胀 |
| | Convergence | 85 | 0-100 | 收敛值 |
| **Scan Lines** | Blend | 0.1 | 0-1 | 扫描线可见度 |
| | Height | 2 | 1-50 | 扫描线高度(px) |
| | Angle | 0° | 0-360° | 水平扫描线 |
| | Phase | 0 | 0-360° | 相位偏移 |
| **Shift Channels** | Take Alpha From | Luminance | 枚举 | 色差基础 |
| | Take Red From | Red | 枚举 | 红通道 |
| | Take Green From | Green | 枚举 | 绿通道 |
| | Take Blue From | Blue | 枚举 | 蓝通道 |
| **CC Vignette** | Amount | -40 | -100~100 | 暗角 |
| | Softness | 70 | 0-100 | 柔和边缘 |
| **Colorama** | Input Phase | Intensity | 枚举 | 基于亮度 |
| | Output Cycle | Neon preset | - | 霓虹色谱 |
| | Blend w/ Original | 70% | 0-100% | 保留70%原色 |

#### 关键帧设置

```
故障闪烁动画：
时间    Opacity     缓动
0.00s   100%        hold
0.03s   0%          hold
0.05s   100%        hold
0.07s   60%         hold
0.10s   100%        linear

色差偏移动画：
时间    Red Offset  Blue Offset
0.00s   +3px        -3px
0.10s   +6px        -6px       （故障增强）
0.15s   0           0          （恢复正常）
```

#### 适用场景和调整指南

- **适用**：科幻场景、赛博朋克风格、故障效果、数字界面
- **调整**：CC Glow色温控制氛围（青色冷感/品红暖感），Scan Lines控制CRT感，Colorama控制色谱映射
- **提示**：间歇性的Glitch闪烁（通过Opacity hold关键帧）比持续效果更有冲击力

---

### 6.4 复古/VHS风格预设

#### 效果组合

Noise + Shift Channels + Fast Box Blur + Color Correction + Interlace

#### 完整参数表

| 效果名 | 参数名 | 数值 | 范围 | 说明 |
|--------|--------|------|------|------|
| **Noise** | Amount of Noise | 8% | 0-100% | 中等噪点 |
| | Noise Type | Clamped | 枚举 | 限制噪点范围 |
| | Color Noise | On | 开/关 | 彩色噪点 |
| **Shift Channels** | Take Red From | Red+2px | - | 红通道右偏移2px |
| | Take Green From | Green | - | 绿通道不变 |
| | Take Blue From | Blue-2px | - | 蓝通道左偏移2px |
| **Fast Box Blur** | Blurriness | 1.5 | 0-100 | 微模糊（模拟低分辨率） |
| | Repeat Edges | On | - | 边缘处理 |
| **Lumetri Color** | Temperature | +10 | -100~100 | 偏暖 |
| | Contrast | -5 | -100~100 | 微降对比 |
| | Saturation | -20 | -100~100 | 褪色 |
| | Highlights | +5 | -100~100 | 轻微过曝 |
| | Shadows | +10 | -100~100 | 提阴影 |
| **Wave Warp** | Wave Type | Sine | 枚举 | 正弦波 |
| | Wave Height | 2 | 0-100 | 微抖动高度 |
| | Wave Width | 500 | 1-5000 | 宽波 |
| | Direction | 180° | 0-360° | 水平抖动 |
| | Speed | 0.5 | 0-10 | 缓慢漂移 |
| **Posterize Time** | Frame Rate | 24 | 1-60 | 模拟帧率 |

#### 关键帧设置

```
VHS追踪偏移：
时间    Position X  缓动
0.00s   0           hold
0.50s   +3px        hold
0.52s   -5px        hold
0.55s   +1px        hold
0.60s   0           hold
（不定期重复，模拟磁带追踪不稳）

色差脉冲：
时间    Red Shift   Blue Shift
0.00s   0           0
2.30s   +8px        -8px        （突然色差）
2.33s   0           0           （恢复）
5.10s   +5px        -5px
5.12s   0           0
```

#### 适用场景和调整指南

- **适用**：复古回忆、恐怖场景、VHS美学、Lo-Fi风格
- **调整**：Noise量控制噪点密度，Shift Channels偏移量控制色差强度，Wave Warp控制画面抖动
- **提示**：关键帧的hold模式是VHS风格的关键——突然跳变而非平滑过渡

---

### 6.5 悬疑/暗黑风格预设

#### 效果参数表

| 效果名 | 参数名 | 数值 | 范围 | 说明 |
|--------|--------|------|------|------|
| **Vignette** | Amount | -70 | -100~100 | 极强暗角 |
| | Size | 35 | 0-100 | 小范围中心聚焦 |
| | Softness | 60 | 0-100 | 中等柔和 |
| **Lumetri Color** | Temperature | -15 | -100~100 | 冷色温 |
| | Contrast | +30 | -100~100 | 高对比 |
| | Saturation | -40 | -100~100 | 大幅降饱和 |
| | Highlights | -10 | -100~100 | 压高光 |
| | Shadows | -15 | -100~100 | 深阴影 |
| | Curves | 陡峭S | - | 增强明暗对比 |
| **Noise** | Amount | 12% | 0-100% | 粗颗粒 |
| | Noise Type | Clamped | 枚举 | 限制范围 |
| **Shadow/Highlight** | Shadow Amount | 20 | 0-100 | 轻微提阴影 |
| | Highlight Amount | 15 | 0-100 | 轻微压高光 |
| | Shadow Radius | 30 | 0-100 | 阴影过渡半径 |
| | Highlight Radius | 30 | 0-100 | 高光过渡半径 |

#### 关键帧设置

```
呼吸式暗角脉动：
时间    Vignette Amount  缓动
0.00s   -60              ease in out
2.00s   -75              ease in out
4.00s   -60              ease in out
（loopOut("cycle")）

悬疑揭示（从暗到亮）：
时间    Opacity     缓动
0.00s   0%          linear
2.00s   100%        ease out（缓慢揭示）
```

#### 适用场景和调整指南

- **适用**：悬疑场景、恐怖片段、暗黑风格、神秘氛围
- **调整**：Vignette强度控制聚焦程度，Saturation控制去色程度，Contrast控制明暗分离
- **提示**：暗角脉动动画（呼吸感）比静态暗角更有压迫感

---

### 6.6 奇幻/魔法风格预设

#### 效果参数表

| 效果名 | 参数名 | 数值 | 范围 | 说明 |
|--------|--------|------|------|------|
| **CC Light Burst 2.5** | Ray Length | 50 | 0-500 | 光线长度 |
| | Burst | 50 | 0-100 | 爆发量 |
| | Shape | Straight | 枚举 | 直线光束 |
| | Color | [0.6, 0.8, 1, 1] | - | 冷蓝白光 |
| | Transfer Mode | Add | 枚举 | 叠加模式 |
| **Glow** | Threshold | 100 | 0-255 | 仅亮部发光 |
| | Radius | 80 | 0-500 | 大扩散 |
| | Intensity | 200 | 0-255 | 强发光 |
| | Color | [0.7, 0.5, 1, 1] | - | 紫色发光 |
| **Colorama** | Input Phase | Hue | 枚举 | 基于色相 |
| | Output Cycle | Pastels | - | 柔和色谱 |
| | Blend w/ Original | 60% | 0-100% | 保留60%原色 |
| **CC Vignette** | Amount | -25 | -100~100 | 轻暗角 |
| **Lens Flare** | Flare Center | [960, 540] | - | 画面中心 |
| | Brightness | 80 | 0-300 | 中等亮度 |
| | Lens Type | 105mm | 枚举 | 105mm镜头 |
| | Blend w/ Original | Add | 枚举 | 叠加 |

#### 关键帧设置

```
魔法释放爆发：
时间    Scale       Glow Intensity   Ray Length
0.00s   100%        80               20
0.15s   110%        250              150          （爆发）
0.40s   102%        120              60           （回落）
0.60s   100%        80               20           （归位）

色相旋转：
表达式: effect("Colorama")("Output Cycle") + time * 30
```

#### 适用场景和调整指南

- **适用**：魔法释放、奇幻场景、超自然力量、梦幻效果
- **调整**：CC Light Burst的Ray Length控制光线长度，Glow Color控制魔法颜色倾向，Colorama控制色谱映射
- **提示**：配合粒子效果（Trapcode Particular）实现更丰富的魔法粒子

---

### 6.7 喜剧/活泼风格预设

#### 效果参数表

| 效果名 | 参数名 | 数值 | 范围 | 说明 |
|--------|--------|------|------|------|
| **Squash & Stretch** | Amount | 30 | 0-100 | 形变量 |
| | Axis | Auto | 枚举 | 自动轴向 |
| | Ease | 75% | 0-100% | 缓动 |
| **Hue/Saturation** | Master Saturation | +20 | -100~100 | 提高饱和 |
| | Channel Control | Master | 枚举 | 全局调整 |
| **Fast Box Blur** | Blurriness | 0 | 0-100 | 默认关闭（运动时通过表达式开启）|
| **Warp** | Warp Style | Bulge | 枚举 | 膨胀效果 |
| | Amount | 5 | -100~100 | 微膨胀 |
| | Bend | 1 | 1-10 | 弯曲度 |

#### 关键帧设置

```
弹跳缩放（卡通式）：
时间    Scale X     Scale Y     缓动
0.00s   100%        100%        linear
0.08s   80%         130%        ease out（压扁蓄力）
0.16s   130%        80%         ease in out（拉伸弹出）
0.24s   95%         108%        ease（回弹）
0.32s   100%        100%        ease（归位）

旋转抖动：
表达式: wiggle(5, 2)
```

#### 适用场景和调整指南

- **适用**：喜剧场景、卡通风格、活泼欢快、趣味动画
- **调整**：Squash & Stretch Amount控制形变程度，Hue/Saturation控制色彩鲜艳度
- **提示**：X/Y轴不等比缩放（压扁/拉伸）是卡通弹跳的核心技巧

---

### 6.8 电影/纪录片风格预设

#### 效果参数表

| 效果名 | 参数名 | 数值 | 范围 | 说明 |
|--------|--------|------|------|------|
| **Noise** | Amount | 4% | 0-100% | 细腻胶片颗粒 |
| | Noise Type | Soft Color | 枚举 | 柔和彩色噪点 |
| **Lumetri Color** | Temperature | +5 | -100~100 | 微暖 |
| | Contrast | +15 | -100~100 | 增强对比 |
| | Highlights | -8 | -100~100 | 压高光 |
| | Shadows | +5 | -100~100 | 提阴影 |
| | Saturation | -10 | -100~100 | 微降饱和 |
| | Curves | 胶片S曲线 | - | 趾部+肩部 |
| **Vignette** | Amount | -25 | -100~100 | 轻暗角 |
| | Softness | 85 | 0-100 | 极柔和 |
| **Glow** | Threshold | 230 | 0-255 | 仅最亮部微发光 |
| | Radius | 30 | 0-500 | 小扩散 |
| | Intensity | 40 | 0-255 | 弱发光 |
| **Mask/Shape** | Letterbox | 2.39:1 | - | 宽银幕遮幅 |

#### 关键帧设置

```
电影感缓推：
时间    Scale       Position Y  缓动
0.00s   100%        540         ease in out
5.00s   105%        550         ease in out
（loopOut("cycle")配合长周期）
```

#### 适用场景和调整指南

- **适用**：电影片段、纪录片、叙事性内容、严肃主题
- **调整**：Letterbox遮幅比例决定电影感（1.85:1 / 2.39:1），Noise控制胶片颗粒量，Curves控制影调
- **提示**：2.39:1遮幅+胶片S曲线+微颗粒是电影感三件套

---

### 6.9 漫剪/AMV风格预设

#### 效果组合

Dolly Zoom + Shake + Glow + Chromatic Aberration + Speed Lines + Motion Blur

#### 完整参数表（含一拳超人实战参数）

| 效果名 | 参数名 | 数值 | 范围 | 说明 |
|--------|--------|------|------|------|
| **Glow** | Threshold | 30 | 0-255 | 低阈值大面积发光 |
| | Radius | 70 | 0-500 | 大扩散 |
| | Intensity | 200 | 0-255 | 极强发光 |
| | Color | [1, 0.85, 0.4, 1] | - | 金色发光 |
| | Glow Technique | Precise | 枚举 | 精确渲染 |
| **CC Lens** | Size | 130 | 0-300 | 强鱼眼畸变 |
| | Curvature | -10 | -100~100 | 负值强烈收缩 |
| **Radial Blur** | Amount | 15 | 0-100 | 强径向模糊 |
| | Type | Zoom | 枚举 | 缩放式 |
| **Shift Channels** | Take Red From | Red+4px | - | 色差红偏移 |
| | Take Blue From | Blue-4px | - | 色差蓝偏移 |
| **CC Force Motion Blur** | Amount | 1.0 | 0-1 | 全量运动模糊 |
| | Samples | 16 | 2-64 | 高质量采样 |
| **Vignette** | Amount | -55 | -100~100 | 强暗角 |
| | Size | 30 | 0-100 | 小范围 |

#### 一拳超人实战参数

```
一拳出拳核心参数配置：

【Phase 1 - 蓄力】(0.00s - 0.15s)
Scale:     100% → 80%        (缓出，收缩蓄力)
Position:  中心 → 后退20px    (蓄力后退)
Glow:      Intensity 50       (低发光)
CC Lens:   Curvature 0        (无畸变)

【Phase 2 - 爆发】(0.15s - 0.25s)
Scale:     80% → 140%         (缓入，爆发放大)
Position:  后退 → 前进150px   (冲击位移)
Rotation:  0° → 5°            (微旋转)
Glow:      Intensity 255      (最大发光)
CC Lens:   Curvature -15      (强畸变)
Radial:    Amount 20          (强径向模糊)
Color Ab:  ±8px               (强色差)

【Phase 3 - 回弹】(0.25s - 0.40s)
Scale:     140% → 105%        (缓入缓出)
Position:  前进 → 回退10px    (回弹)
Rotation:  5° → -1°           (回弹旋转)
Glow:      Intensity 120      (回落)
CC Lens:   Curvature -3       (弱畸变)

【Phase 4 - 归位】(0.40s - 0.55s)
Scale:     105% → 100%        (缓出)
Position:  回退 → 中心        (归位)
Rotation:  -1° → 0°           (归位)
Glow:      Intensity 80       (恢复)
CC Lens:   Curvature 0        (恢复)
```

#### 关键帧设置

```
Dolly Zoom关键帧（焦距+距离同时变化）：
时间    Scale       Camera Zoom   缓动
0.00s   100%        50mm          linear
0.15s   80%         50mm          ease out
0.20s   140%        85mm          ease in（同时拉远焦距+放大）
0.35s   105%        65mm          ease
0.50s   100%        50mm          ease

震屏表达式：
var shakeAmp = 15;
var shakeFreq = 20;
var shakeDecay = 8;
var impactTime = 0.20;
var t = time - impactTime;
if (t > 0) {
    var s = shakeAmp * Math.exp(-shakeDecay * t);
    value + [Math.sin(shakeFreq * t) * s, Math.cos(shakeFreq * t) * s];
} else {
    value;
}
```

#### 适用场景和调整指南

- **适用**：漫剪/AMV高燃片段、一拳超人式冲击、热血战斗
- **调整**：爆发阶段的Scale峰值控制冲击感，Glow Intensity控制发光强度，Radial Blur控制动感
- **提示**：蓄力→爆发→回弹→归位的四阶段节奏是漫剪冲击的黄金法则

---

### 6.10 MG动画风格预设

#### 效果参数表

| 效果名 | 参数名 | 数值 | 范围 | 说明 |
|--------|--------|------|------|------|
| **Slider Control** | Slider | 100 | 0-100 | 动画进度控制 |
| **Angle Control** | Angle | 0 | 0-360° | 旋转控制 |
| **Color Control** | Color | [0.2, 0.6, 1, 1] | - | 主题色控制 |

#### 关键帧设置

```
Overshoot弹跳缩放：
表达式:
var freq = 2.5;
var decay = 4;
var n = 0;
var t = 0;
if (numKeys > 0) {
    n = nearestKey(time).index;
    if (key(n).time > time) n--;
}
if (n > 0) {
    t = time - key(n).time;
    var v = velocityAtTime(key(n).time - 0.001);
    var w = freq * 2 * Math.PI;
    value + v / w * Math.sin(w * t) * Math.exp(-decay * t);
} else {
    value;
}

Elastic缓动缩放：
关键帧：0% → 100%
时间    Scale       缓动
0.00s   0%          ease out (80% 影响范围)
0.40s   115%        ease in out
0.55s   95%         ease in out
0.65s   103%        ease in out
0.70s   100%        ease in

路径动画（Path节点动画）：
使用Trim Paths的Start/End关键帧
时间    End         缓动
0.00s   0%          ease out
0.50s   100%        ease out

色彩偏移：
表达式:
var colors = [[0.2,0.6,1], [1,0.4,0.2], [0.2,1,0.6]];
var idx = Math.floor(time / 2) % colors.length;
var t = (time / 2) % 1;
var c1 = colors[idx];
var c2 = colors[(idx + 1) % colors.length];
[c1[0]*(1-t) + c2[0]*t, c1[1]*(1-t) + c2[1]*t, c1[2]*(1-t) + c2[2]*t, 1]
```

#### 适用场景和调整指南

- **适用**：MG动画、UI动画、信息图表、品牌动画
- **调整**：freq/decay参数控制弹性频率和衰减，Trim Paths控制路径绘制速度
- **提示**：MG动画的核心是统一的缓动风格——同一项目中所有元素应使用一致的freq/decay值

---

## 七、预设逆向工程实战

### 7.1 逆向工程流程

```
┌──────────────────────────────────────────────────────┐
│                 预设逆向工程完整流程                    │
│                                                      │
│  1. 获取预设文件                                      │
│     └─ .ffx / .mogrt / .aep / .cube                │
│                                                      │
│  2. 解压/解析文件结构                                  │
│     ├─ .ffx → 文本编辑器直接打开                       │
│     ├─ .mogrt → 双层ZIP解压                           │
│     ├─ .aep → AE打开                                 │
│     └─ .cube → 文本编辑器打开                         │
│                                                      │
│  3. 提取参数数据                                       │
│     ├─ 效果MatchName + 参数索引                       │
│     ├─ 参数值（数值/颜色/角度/点）                     │
│     ├─ 关键帧数据（时间/值/缓动）                      │
│     └─ 表达式代码                                     │
│                                                      │
│  4. 分析参数关系                                       │
│     ├─ 控件→表达式→效果映射链                         │
│     ├─ 关键帧时序与缓动模式                           │
│     └─ 效果堆叠顺序与混合模式                         │
│                                                      │
│  5. 重建参数体系                                       │
│     ├─ 编写参数JSON描述                               │
│     ├─ 编写ApplyScript重建脚本                        │
│     └─ 验证参数还原度                                 │
│                                                      │
│  6. 验证参数效果                                       │
│     ├─ 应用到测试图层                                 │
│     ├─ 对比原图/原效果                                │
│     └─ 微调差异参数                                   │
│                                                      │
│  7. 优化和定制                                         │
│     ├─ 参数化控件（添加Slider Control）               │
│     ├─ 优化表达式性能                                 │
│     └─ 保存为自定义预设                               │
└──────────────────────────────────────────────────────┘
```

---

### 7.2 逆向工程案例

#### 案例1：解析商业MOGRT模板

**目标**：提取一个商业字幕条MOGRT的完整参数结构。

**步骤**：

```
步骤1：解压MOGRT
  - 将title_bar.mogrt重命名为title_bar.zip
  - 解压得到：Project.aegraphic、[Content_Types].xml、_rels/

步骤2：解压aegraphic
  - 将Project.aegraphic重命名为Project.zip
  - 解压得到：project.aep、essentialgraphics/、fonts/

步骤3：用AE打开project.aep
  - 找到主合成（通常名为"Main"或"Edit"）
  - 分析图层结构

步骤4：识别控件映射
  - 打开Essential Graphics面板
  - 记录每个控件名称和类型
  - 在Effect Controls中找到对应的Control效果

步骤5：提取表达式
  - 逐层展开属性
  - 记录所有非空表达式
```

**提取结果示例**：

```javascript
// MOGRT控件→表达式映射表
var mogrtMapping = {
    controls: [
        {name: "Title Text", type: "sourceText", default: "Your Title Here"},
        {name: "Accent Color", type: "color", default: [0.2, 0.6, 1, 1]},
        {name: "Bar Width", type: "slider", default: 80, min: 0, max: 100},
        {name: "Animation Speed", type: "slider", default: 50, min: 10, max: 100}
    ],
    expressions: [
        {
            layer: "Bar Shape",
            property: "Scale",
            expression: "var w = effect('Bar Width')('Slider'); [w, 100]"
        },
        {
            layer: "Bar Shape",
            property: "Contents/Rectangle 1/Fill 1/Color",
            expression: "effect('Accent Color')('Color')"
        },
        {
            layer: "Title Text",
            property: "Source Text",
            expression: "var speed = effect('Animation Speed')('Slider') / 50; " +
                         "var t = time * speed; " +
                         "text.sourceText"
        }
    ]
};
```

#### 案例2：解析.ffx动画预设

**目标**：从一个弹性缩放.ffx预设中提取关键帧参数。

**步骤**：

```
步骤1：用VS Code打开preset.ffx
步骤2：搜索ADBE Scale属性
步骤3：提取所有<keyframe>标签
步骤4：解析缓动参数
步骤5：重建关键帧数据
```

**脚本提取**：

```javascript
// 从.ffx文件提取关键帧数据的脚本
function extractKeyframesFromFFX(ffxPath) {
    var file = new File(ffxPath);
    if (!file.exists) return null;

    file.open("r");
    var xml = file.read();
    file.close();

    // 解析XML（使用ExtendScript的XML对象）
    var root = new XML(xml);

    // 查找Scale属性
    var scaleProps = root..*.(function() {
        return attribute("id") == "ADBE Scale";
    })();

    var keyframes = [];
    for each (var kf in scaleProps..keyframe) {
        keyframes.push({
            time: Number(kf.@time),
            value: String(kf.@value),
            interpType: String(kf.@interpType),
            inSpeed: kf.temporalEase.length() > 0 ?
                     Number(kf.temporalEase.@inSpeed) : 0,
            outSpeed: kf.temporalEase.length() > 0 ?
                      Number(kf.temporalEase.@outSpeed) : 0,
            inInfluence: kf.temporalEase.length() > 0 ?
                         Number(kf.temporalEase.@inInfluence) : 0,
            outInfluence: kf.temporalEase.length() > 0 ?
                          Number(kf.temporalEase.@outInfluence) : 0
        });
    }

    return keyframes;
}

// 在AE中重建关键帧
function rebuildKeyframes(prop, keyframes) {
    if (!prop.canSetKeyframe) return;

    app.beginUndoGroup("重建关键帧");

    // 先清除现有关键帧
    while (prop.numKeys > 0) {
        prop.deleteKey(1);
    }

    // 按时间排序
    keyframes.sort(function(a, b) { return a.time - b.time; });

    // 添加关键帧
    for (var i = 0; i < keyframes.length; i++) {
        var kf = keyframes[i];
        var valArr = kf.value.split(" ");
        var val = [];
        for (var j = 0; j < valArr.length; j++) {
            val.push(parseFloat(valArr[j]));
        }
        if (val.length === 1) {
            prop.setValueAtTime(kf.time, val[0]);
        } else {
            prop.setValueAtTime(kf.time, val);
        }
    }

    // 设置缓动
    for (var i2 = 0; i2 < keyframes.length; i2++) {
        var kf2 = keyframes[i2];
        var keyIndex = prop.nearestKeyIndex(kf2.time);

        if (kf2.interpType === "hold") {
            prop.setInterpolationTypeAtKey(keyIndex, KeyframeInterpolationType.HOLD);
        } else if (kf2.interpType === "bezier" || kf2.interpType === "linear") {
            var inType = kf2.interpType === "bezier" ?
                         KeyframeInterpolationType.BEZIER :
                         KeyframeInterpolationType.LINEAR;
            var outType = inType;
            prop.setInterpolationTypeAtKey(keyIndex, inType, outType);

            if (kf2.interpType === "bezier") {
                var inE = new KeyframeEase(kf2.inSpeed, kf2.inInfluence);
                var outE = new KeyframeEase(kf2.outSpeed, kf2.outInfluence);
                prop.setTemporalEaseAtKey(keyIndex, [inE], [outE]);
            }
        }
    }

    app.endUndoGroup();
}
```

#### 案例3：解析调色LUT

**目标**：从.cube文件中提取LUT映射数据。

**步骤**：

```
步骤1：用文本编辑器打开.cube文件
步骤2：读取LUT_3D_SIZE确定网格尺寸
步骤3：读取DOMAIN_MIN/MAX确定范围
步骤4：逐行解析RGB映射数据
步骤5：生成参数摘要
```

**解析脚本**：

```javascript
// 解析CUBE LUT文件
function parseCubeLUT(cubePath) {
    var file = new File(cubePath);
    if (!file.exists) return null;

    file.open("r");
    var lines = [];
    while (!file.eof) {
        lines.push(file.readln());
    }
    file.close();

    var lutData = {
        title: "",
        size: 0,
        domainMin: [0, 0, 0],
        domainMax: [1, 1, 1],
        data: []
    };

    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].replace(/^\s+|\s+$/g, "");

        // 跳过空行和注释
        if (line === "" || line.charAt(0) === "#") continue;

        // 解析标题
        if (line.indexOf("TITLE") === 0) {
            lutData.title = line.match(/"([^"]+)"/)[1];
        }
        // 解析网格尺寸
        else if (line.indexOf("LUT_3D_SIZE") === 0) {
            lutData.size = parseInt(line.split(/\s+/)[1]);
        }
        // 解析域范围
        else if (line.indexOf("DOMAIN_MIN") === 0) {
            var vals = line.split(/\s+/);
            lutData.domainMin = [parseFloat(vals[1]), parseFloat(vals[2]), parseFloat(vals[3])];
        }
        else if (line.indexOf("DOMAIN_MAX") === 0) {
            var vals2 = line.split(/\s+/);
            lutData.domainMax = [parseFloat(vals2[1]), parseFloat(vals2[2]), parseFloat(vals2[3])];
        }
        // 解析数据行
        else {
            var rgb = line.split(/\s+/);
            if (rgb.length >= 3) {
                lutData.data.push([
                    parseFloat(rgb[0]),
                    parseFloat(rgb[1]),
                    parseFloat(rgb[2])
                ]);
            }
        }
    }

    // 生成摘要
    lutData.summary = {
        title: lutData.title,
        gridSize: lutData.size,
        totalPoints: lutData.data.length,
        expectedPoints: lutData.size * lutData.size * lutData.size,
        isComplete: lutData.data.length === lutData.size * lutData.size * lutData.size,
        darkPoint: lutData.data[0],
        midPoint: lutData.data[Math.floor(lutData.data.length / 2)],
        brightPoint: lutData.data[lutData.data.length - 1]
    };

    return lutData;
}
```

#### 案例4：解析第三方插件预设

**目标**：解析Trapcode Particular预设的参数映射。

**步骤**：

```
步骤1：用VS Code打开Particular预设.ffx
步骤2：搜索Trapcode Particular的Match Name
步骤3：对照Particular参数索引表提取值
步骤4：重建Particular参数配置
```

**Particular关键参数索引**（部分）：

| 索引 | 参数名 | 说明 | 常用值 |
|------|--------|------|--------|
| 1 | Emission > Particles/sec | 每秒粒子数 | 50-5000 |
| 2 | Emission > Emitter Type | 发射器类型 | Point/Box/Sphere |
| 6 | Emission > Direction | 方向 | 0-360° |
| 8 | Emission > Velocity | 速度 | 0-500 |
| 11 | Emission > Velocity Random | 速度随机 | 0-100% |
| 22 | Particle > Life | 生命周期(秒) | 0.5-10 |
| 23 | Particle > Life Random | 生命随机 | 0-100% |
| 24 | Particle > Particle Type | 粒子类型 | Sphere/Glow/Sprite |
| 30 | Particle > Size | 大小 | 1-50 |
| 31 | Particle > Size Random | 大小随机 | 0-100% |
| 36 | Particle > Color | 颜色 | RGB |
| 42 | Physics > Gravity | 重力 | -500~500 |
| 48 | Physics > Air > Wind X | X风向 | -500~500 |
| 52 | Physics > Air > Turbulence | 紊流 | 0-500 |

---

### 7.3 逆向工程工具

| 工具 | 用途 | 操作 |
|------|------|------|
| **VS Code** | 编辑/分析.ffx/.cube/.3dl | 安装XML Tools扩展格式化 |
| **Notepad++** | 快速查看预设文件 | 设置XML语法高亮 |
| **7-Zip** | 解压.mogrt双层ZIP | 右键→7-Zip→Extract Here |
| **MediaInfo** | 分析LUT文件信息 | 拖入文件查看元数据 |
| **ExtendScript Toolkit** | 脚本调试执行 | 连接AE实时调试 |
| **AE预设管理器** | 预设浏览和预览 | Effects & Presets面板 |
| **HEX编辑器** | 分析二进制预设文件 | 查看非文本格式的预设 |

---

## 八、预设开发与打包

### 8.1 创建自定义预设

#### 创建效果预设

1. 在图层上添加一个或多个效果
2. 调整所有参数到目标值
3. 在Effect Controls面板中选中效果（可多选）
4. 执行`Animation > Save Animation Preset`
5. 选择保存位置并命名

#### 创建动画预设

1. 在图层上创建关键帧动画
2. 选中包含关键帧的属性（可多选）
3. 执行`Animation > Save Animation Preset`
4. 命名并保存

#### 保存和导出预设

```javascript
// 通过脚本保存预设
function saveAsPreset(layer, presetName, savePath) {
    var saveFile = new File(savePath + "/" + presetName + ".ffx");
    layer.saveAnimationPreset(saveFile);
    return saveFile.exists;
}
```

#### 预设命名规范

```
推荐命名格式：[风格]_[效果类型]_[变体编号]
示例：
  Action_Glow_Burst_01.ffx
  Cinematic_Color_TealOrange.ffx
  VHS_Distortion_Heavy.ffx
  Comedy_Bounce_Cartoon.ffx
```

---

### 8.2 创建MOGRT模板

#### 设计Essential Graphics控件

```
控件设计原则：
1. 最少控件原则 - 只暴露用户需要调整的参数
2. 语义化命名 - 控件名应直观表达功能（"Title Color"而非"Color 1"）
3. 合理范围 - Slider的范围应匹配实际使用需求
4. 默认值优化 - 默认值应是最常用的配置
5. 控件分组 - 相关控件放在同一组
```

#### 编写表达式驱动

```javascript
// MOGRT表达式驱动模板
// 应用到目标属性，引用EGP控件

// 颜色控件驱动
effect("Accent Color")("Color")

// 滑块控件驱动（带范围映射）
var rawValue = effect("Intensity")("Slider");
var mappedValue = rawValue / 100 * 255;  // 0-100映射到0-255

// 复选框开关
if (effect("Enable Glow")("Checkbox") == 1) {
    effect("Glow")("Intensity");
} else {
    0;
}

// 下拉菜单驱动
var mode = effect("Style")("Menu");
if (mode == 0) {
    // 选项1：暖色
    [1, 0.8, 0.5, 1];
} else if (mode == 1) {
    // 选项2：冷色
    [0.5, 0.8, 1, 1];
} else {
    // 选项3：中性
    [1, 1, 1, 1];
}
```

#### 嵌入字体和资源

1. 在AE中选择`File > Dependencies > Collect Files`
2. 勾选"Include Fonts"
3. 在导出MOGRT时选择嵌入选项

#### 测试兼容性

```
测试清单：
□ AE中打开并验证所有控件工作正常
□ Premiere Pro中导入MOGRT并测试
□ 修改每个控件值，确认响应正确
□ 测试不同分辨率（1920×1080 / 3840×2160）
□ 测试不同帧率（24/25/30/60fps）
□ 测试字体回退（目标机器无嵌入字体时）
```

#### 导出MOGRT

1. 在AE中打开Essential Graphics面板
2. 确认所有控件已添加
3. 点击"Export Motion Graphics Template"
4. 选择保存位置
5. 测试导出的.mogrt文件

---

### 8.3 创建调色LUT

#### 使用Lumetri调色

1. 在AE中添加Lumetri Color效果到调整图层
2. 完成调色（Temperature/Tint/Curves/HSL等）
3. 记录所有参数值

#### 导出.cube/.3dl

AE本身不直接导出LUT，需要通过以下方式：

| 方法 | 工具 | 步骤 |
|------|------|------|
| Premiere Pro导出 | Lumetri面板 | 导出LUT → .cube |
| DaVinci Resolve导出 | LUT管理器 | 右键→Export LUT |
| 在线工具 | LUT Creator | 上传调色截图生成 |
| 脚本生成 | ExtendScript | 读取Lumetri参数生成.cube |

```javascript
// 通过脚本生成CUBE LUT文件（简化版1D LUT）
function generateCubeLUT(outputPath, size, gamma, lift, gain) {
    var file = new File(outputPath);
    file.open("w");

    file.writeln("TITLE \"Custom LUT\"");
    file.writeln("LUT_3D_SIZE " + size);
    file.writeln("DOMAIN_MIN 0.0 0.0 0.0");
    file.writeln("DOMAIN_MAX 1.0 1.0 1.0");
    file.writeln("");

    for (var b = 0; b < size; b++) {
        for (var g = 0; g < size; g++) {
            for (var r = 0; r < size; r++) {
                var ri = r / (size - 1);
                var gi = g / (size - 1);
                var bi = b / (size - 1);

                // 应用Gamma
                var ro = Math.pow(ri, gamma);
                var go = Math.pow(gi, gamma);
                var bo = Math.pow(bi, gamma);

                // 应用Lift/Gain
                ro = ro * gain + lift;
                go = go * gain + lift;
                bo = bo * gain + lift;

                // Clamp
                ro = Math.min(1, Math.max(0, ro));
                go = Math.min(1, Math.max(0, go));
                bo = Math.min(1, Math.max(0, bo));

                file.writeln(
                    ro.toFixed(6) + " " +
                    go.toFixed(6) + " " +
                    bo.toFixed(6)
                );
            }
        }
    }

    file.close();
    return file.exists;
}
```

#### LUT验证和测试

1. 在AE中通过`Lumetri Color > Creative > Look`加载生成的.cube
2. 与原始调色对比
3. 检查高光/阴影/肤色区域是否正常
4. 确认无色带（banding）问题

#### 跨平台兼容性

| 平台 | 推荐格式 | 网格尺寸 | 注意事项 |
|------|----------|----------|----------|
| AE/PR | .cube | 33 | 通过Lumetri加载 |
| DaVinci Resolve | .cube / .3dl | 33 | 通过LUT管理器加载 |
| Final Cut Pro | .cube | 33 | 通过Custom LUT效果 |
| Nuke | .cube / .3dl | 33 | 通过Vectorfield节点 |
| OBS | .cube | 33 | 通过滤镜添加 |

---

### 8.4 预设批量打包脚本

#### 批量导出.ffx

```javascript
// 批量导出合成中所有图层的效果预设
function batchExportPresets(comp, outputDir) {
    var outputFolder = new Folder(outputDir);
    if (!outputFolder.exists) outputFolder.create();

    var exported = [];

    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        var effects = layer.property("ADBE Effect Parade");

        if (effects && effects.numProperties > 0) {
            var fileName = layer.name.replace(/[^a-zA-Z0-9_\-]/g, "_");
            var saveFile = new File(outputDir + "/" + fileName + ".ffx");

            try {
                layer.saveAnimationPreset(saveFile);
                exported.push({
                    layer: layer.name,
                    file: saveFile.fsName,
                    effects: effects.numProperties
                });
            } catch (e) {
                exported.push({
                    layer: layer.name,
                    error: e.toString()
                });
            }
        }
    }

    return exported;
}
```

#### 批量创建MOGRT

```javascript
// 批量导出合成为MOGRT（需AE 2024+）
function batchExportMogrt(comp, outputDir) {
    var outputFolder = new Folder(outputDir);
    if (!outputFolder.exists) outputFolder.create();

    // 获取Essential Graphics面板中已配置的合成
    var mogrtName = comp.name.replace(/[^a-zA-Z0-9_\-]/g, "_");
    var savePath = outputDir + "/" + mogrtName + ".mogrt";

    // 使用AE内部命令导出MOGRT
    app.executeCommand(3841);  // Export Motion Graphics Template命令ID

    return savePath;
}
```

#### 自动化测试

```javascript
// 自动化预设测试脚本
function testPresetApplication(presetPath, comp) {
    var results = [];

    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        var beforeEffects = layer.property("ADBE Effect Parade").numProperties;

        app.beginUndoGroup("Test Preset");
        try {
            var presetFile = new File(presetPath);
            layer.applyPreset(presetFile);
            presetFile.close();

            var afterEffects = layer.property("ADBE Effect Parade").numProperties;
            results.push({
                layer: layer.name,
                success: true,
                effectsAdded: afterEffects - beforeEffects
            });
        } catch (e) {
            results.push({
                layer: layer.name,
                success: false,
                error: e.toString()
            });
        }
        app.endUndoGroup();
        app.undo();  // 撤销测试操作
    }

    return results;
}
```

---

## 九、预设资源推荐

### 9.1 免费预设资源

| 资源 | 类型 | 链接 | 说明 |
|------|------|------|------|
| **Adobe官方预设库** | 效果/动画/文字 | AE安装自带 | 系统预设，质量有保证 |
| **Video Copilot** | 效果/3D | videocopilot.net | Andrew Kramer出品，教程+预设 |
| **Motion Array Free** | 效果/转场/MOGRT | motionarray.com | 每日免费下载额度 |
| **Mixkit** | 转场/MOGRT | mixkit.co | 完全免费，无需注册 |
| **GitHub开源** | 脚本/表达式 | github.com | 搜索"AE presets"或"after effects" |
| **Surfaced Studio** | 效果/转场 | surfacedstudio.com | 免费教程和预设包 |
| **Ben Marriott** | 效果/表达式 | benmarriott.com | YouTube教程配套预设 |

### 9.2 付费预设资源

| 资源 | 类型 | 价格模式 | 说明 |
|------|------|----------|------|
| **Envato Elements** | 全类型 | 订阅制（月/年） | 无限下载，含AE模板/预设/素材 |
| **VideoHive** | 模板/MOGRT | 单品购买 | Envato Marketplace，质量参差需筛选 |
| **Motion Array** | 全类型 | 订阅制 | 含AE/PR/DAV模板，更新频繁 |
| **aescripts** | 脚本/插件 | 单品购买 | 专业开发者工具，质量最高 |
| **Cinecom** | 效果/转场 | 单品/套装 | 教程风格的专业预设包 |
| **Sauce** | 调色LUT | 单品购买 | 专业电影级调色LUT |

### 9.3 第三方插件预设

| 插件 | 内置预设数 | 预设特色 | 获取方式 |
|------|-----------|----------|----------|
| **Trapcode Suite** | 200+ | 粒子/光效/3D | redgiant.com 安装后自动加载 |
| **Sapphire** | 300+ | 转场/光效/风格化 | borisfx.com 需单独安装预设包 |
| **BCC** | 250+ | 修复/风格化/转场 | borisfx.com 随插件安装 |
| **Red Giant Universe** | 100+ | 复古/故障/光效 | redgiant.com 订阅制 |
| **Video Copilot** | 50+ | 3D/光效/粒子 | videocopilot.net Element 3D配套 |
| **Stardust** | 80+ | 粒子/3D/物理 | superluminal.tv 随插件安装 |

---

## 十、预设与实战项目对接

### 10.1 一拳超人项目预设配置

#### 完整预设清单

| 序号 | 效果 | 应用图层 | 用途 |
|------|------|----------|------|
| 1 | Glow | 人物图层 | 冲击发光 |
| 2 | CC Lens | 人物图层 | 冲击畸变 |
| 3 | Radial Blur | 调整图层 | 径向模糊 |
| 4 | CC Force Motion Blur | 调整图层 | 运动模糊 |
| 5 | Shift Channels | 调整图层 | 色差效果 |
| 6 | Vignette | 调整图层 | 暗角聚焦 |
| 7 | Noise | 调整图层 | 质感颗粒 |
| 8 | Lumetri Color | 调整图层 | 调色 |
| 9 | Speed Lines（形状图层） | 顶层 | 速度线 |
| 10 | Impact Flash（纯色图层） | 顶层 | 冲击闪白 |

#### 每个效果的参数值

| 效果 | 参数 | 数值 | 备注 |
|------|------|------|------|
| Glow | Threshold | 30 | 低阈值大面积发光 |
| | Radius | 70 | 大扩散 |
| | Intensity | 200→80 | 关键帧：爆发时200→回落80 |
| | Color | [1,0.85,0.4,1] | 金色 |
| | Operation | Add | 叠加 |
| CC Lens | Size | 130 | 强畸变 |
| | Curvature | 0→-15→0 | 关键帧：爆发时-15→恢复0 |
| Radial Blur | Amount | 0→20→0 | 关键帧：爆发时20→恢复0 |
| | Type | Zoom | 缩放式 |
| CC Force Motion Blur | Amount | 1.0 | 全量 |
| | Samples | 16 | 高质量 |
| Shift Channels | Red From | Red+4px | 红右偏 |
| | Blue From | Blue-4px | 蓝左偏 |
| Vignette | Amount | -55 | 强暗角 |
| | Size | 30 | 小范围 |
| Noise | Amount | 5% | 微颗粒 |
| | Type | Soft Color | 柔和 |
| Lumetri | Temperature | +5 | 微暖 |
| | Contrast | +20 | 高对比 |
| | Saturation | +10 | 提饱和 |

#### 关键帧曲线设置

```
四阶段时间线（总长0.55秒）：

Phase 1 蓄力 (0.00s-0.15s):
  Scale:  100% → 80%       (ease out, influence: 70%)
  Glow:   Intensity 50      (静态)
  Lens:   Curvature 0       (静态)

Phase 2 爆发 (0.15s-0.25s):
  Scale:  80% → 140%        (ease in, influence: 30%)
  Glow:   Intensity 255     (ease out)
  Lens:   Curvature -15     (ease out)
  Radial: Amount 20         (ease out)
  Position: +150px冲击       (ease out, influence: 20%)

Phase 3 回弹 (0.25s-0.40s):
  Scale:  140% → 105%       (ease in out)
  Glow:   Intensity 120     (ease in out)
  Lens:   Curvature -3      (ease in out)
  Radial: Amount 5          (ease in out)
  Position: -10px回弹        (ease in out)

Phase 4 归位 (0.40s-0.55s):
  Scale:  105% → 100%       (ease out)
  Glow:   Intensity 80      (ease out)
  Lens:   Curvature 0       (ease out)
  Radial: Amount 0          (ease out)
  Position: 0               (ease out)
```

#### 表达式配置

```javascript
// 冲击震屏（应用到Position）
var impactTime = 0.20;
var amp = 15;
var freq = 20;
var decay = 8;
var t = time - impactTime;
if (t > 0 && t < 0.5) {
    var s = amp * Math.exp(-decay * t);
    value + [Math.sin(freq * t * 2 * Math.PI) * s,
             Math.cos(freq * t * 2 * Math.PI) * s * 0.6];
} else {
    value;
}

// 闪白控制（应用到Solid图层Opacity）
var impactTime = 0.20;
var t = time - impactTime;
if (t > 0 && t < 0.1) {
    100 * (1 - t / 0.1);
} else {
    0;
}

// 速度线缩放（应用到Shape图层Scale）
var impactTime = 0.20;
var t = time - impactTime;
if (t > 0 && t < 0.3) {
    var s = t / 0.3;
    [100 + s * 200, 100 + s * 200];
} else {
    [100, 100];
}
```

#### 图层混合模式

| 图层 | 混合模式 | 不透明度 | 说明 |
|------|----------|----------|------|
| 人物图层 | Normal | 100% | 主体 |
| 调整图层1（模糊+色差） | Normal | 100% | 效果调整层 |
| 调整图层2（调色） | Normal | 100% | 调色调整层 |
| 速度线（形状） | Screen | 60% | 速度线叠加 |
| 冲击闪光（纯色白） | Add | 关键帧0→100→0 | 瞬间闪白 |

#### 渲染输出设置

| 参数 | 设置 | 说明 |
|------|------|------|
| 格式 | H.264 / ProRes | 根据平台选择 |
| 分辨率 | 1920×1080 | Full HD |
| 帧率 | 24fps | 电影帧率 |
| 比特率 | 20Mbps+ | 高质量 |
| 色彩空间 | sRGB | 网络发布 |
| 渲染器 | Mercury GPU | GPU加速 |

---

### 10.2 预设到项目的映射流程

```
┌────────────────────────────────────────────────────────┐
│              预设到项目映射完整流程                       │
│                                                        │
│  1. 分析目标效果                                       │
│     ├─ 观察参考视频/截图                               │
│     ├─ 拆解效果组合（哪些效果叠加）                     │
│     └─ 识别关键特征（发光/色差/模糊/震屏等）            │
│                                                        │
│  2. 选择匹配预设                                       │
│     ├─ 从预设库中搜索匹配风格                          │
│     ├─ 优先使用最接近的预设（减少调参量）               │
│     └─ 多预设组合（基础预设+效果叠加）                  │
│                                                        │
│  3. 调整参数适配                                       │
│     ├─ 根据素材尺寸调整空间参数                        │
│     ├─ 根据素材亮度调整Glow Threshold                  │
│     ├─ 根据项目时长调整动画速度                        │
│     └─ 根据风格需求微调颜色/强度                       │
│                                                        │
│  4. 添加关键帧                                         │
│     ├─ 对齐音乐节拍点                                  │
│     ├─ 设置蓄力→爆发→回弹→归位四阶段                  │
│     └─ 微调缓动曲线                                    │
│                                                        │
│  5. 测试渲染                                           │
│     ├─ RAM Preview实时预览                             │
│     ├─ 检查效果叠加顺序                                │
│     └─ 验证关键帧时序                                  │
│                                                        │
│  6. 微调优化                                           │
│     ├─ 根据预览效果微调参数                            │
│     ├─ 优化表达式性能                                  │
│     └─ 保存为项目专属预设                              │
└────────────────────────────────────────────────────────┘
```

---

### 10.3 预设调优指南

#### 根据素材调整预设参数

| 素材特征 | 需调整的参数 | 调整方向 |
|----------|-------------|----------|
| 画面偏暗 | Glow Threshold | 降低（让更多区域发光）|
| 画面偏亮 | Glow Threshold | 提高（仅最亮部发光）|
| 高分辨率(4K) | Blur Radius | 增大（同等视觉效果的模糊值需翻倍）|
| 低分辨率(720p) | Blur Radius | 减小 |
| 高对比素材 | Vignette Amount | 减小（已有足够对比）|
| 低对比素材 | Contrast + Vignette | 增大（增强明暗分离）|
| 快速运动素材 | Motion Blur Amount | 增大 |
| 静态素材 | Motion Blur | 可关闭 |

#### 根据音乐节奏调整动画

```javascript
// 根据BPM自动计算关键帧时间
function bpmToKeyframeTimes(bpm, startTime, count) {
    var beatDuration = 60 / bpm;  // 每拍时长(秒)
    var times = [];
    for (var i = 0; i < count; i++) {
        times.push(startTime + i * beatDuration);
    }
    return times;
}

// 示例：128BPM的冲击节奏
var impactTimes = bpmToKeyframeTimes(128, 0, 4);
// 结果: [0, 0.469, 0.938, 1.406]秒

// 应用到Scale属性
function applyRhythmScale(prop, impactTimes) {
    for (var i = 0; i < impactTimes.length; i++) {
        var t = impactTimes[i];
        prop.setValueAtTime(t, 130);
        prop.setValueAtTime(t + 0.05, 105);
        prop.setValueAtTime(t + 0.15, 100);
    }
}
```

#### 根据场景风格调整调色

| 场景 | Temperature | Saturation | Contrast | 特殊调整 |
|------|-------------|------------|----------|----------|
| 室内日光 | +5 | -5 | +10 | 暖色调 |
| 室外阴天 | -10 | -15 | +20 | 冷色调+提阴影 |
| 夜景 | -20 | -25 | +30 | 强冷色+降噪 |
| 日落 | +25 | +10 | +5 | 暖橙色调 |
| 战斗场景 | +5 | +15 | +25 | 高对比+强Glow |
| 回忆场景 | +15 | -20 | -10 | 褪色+柔焦 |

#### 根据输出平台调整格式

| 平台 | 分辨率 | 帧率 | 编码 | 码率 | 色彩空间 |
|------|--------|------|------|------|----------|
| YouTube | 1920×1080 / 3840×2160 | 24/30/60 | H.264 High | 20-45 Mbps | sRGB |
| Bilibili | 1920×1080 | 24/30 | H.264 High | 16-20 Mbps | sRGB |
| 抖音/TikTok | 1080×1920 (竖屏) | 30 | H.264 | 8-12 Mbps | sRGB |
| Instagram Reels | 1080×1920 | 30 | H.264 | 5-8 Mbps | sRGB |
| 微信视频号 | 1920×1080 | 30 | H.264 | 10-15 Mbps | sRGB |
| 本地存档 | 3840×2160 | 24/30 | ProRes 4444 | 无损 | Linear |

---

> **手册版本**：v1.0 | **更新日期**：2026-07-09 | **兼容版本**：AE 2024-2026
> 
> 本手册为AE专业用户提供预设解析与调用的完整参考，涵盖从格式解析到实战调用的全链路知识。所有脚本代码基于ExtendScript ES3语法，可直接在AE中运行。
