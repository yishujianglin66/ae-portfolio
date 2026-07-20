# Premiere Pro 色彩校正与调色完全指南

---

## 一、色彩基础理论

### 1.1 色彩空间与工作流

```
色彩工作流：
┌─────────────────────────────────────────────┐
│  拍摄 → ProRes/DNxHR → Premiere Pro        │
│  ├── 输入色彩空间: Rec.709 / P3 / Log       │
│  ├── 工作色彩空间: ACES / Rec.709          │
│  └── 输出色彩空间: Rec.709 / HDR           │
└─────────────────────────────────────────────┘
```

### 1.2 常用色彩空间

| 色彩空间 | 用途 | 特点 |
|---------|------|------|
| **Rec.709** | 标准HD | 电视广播标准 |
| **Rec.2020** | 4K/8K | 超广色域 |
| **DCI-P3** | 影院 | 电影级色域 |
| **ACES** | 专业级 | 开放色彩体系 |

---

## 二、调色面板使用

### 2.1 Lumetri Color 面板

```javascript
// 使用ExtendScript控制Lumetri Color
function applyLumetriColor(clip, settings) {
    var lumetriEffect = clip.effects.add("Lumetri Color");
    
    // 基本校正
    lumetriEffect.property("Basic").property("Exposure").setValue(settings.exposure);
    lumetriEffect.property("Basic").property("Contrast").setValue(settings.contrast);
    lumetriEffect.property("Basic").property("Highlights").setValue(settings.highlights);
    lumetriEffect.property("Basic").property("Shadows").setValue(settings.shadows);
    
    // 色温
    lumetriEffect.property("Basic").property("Temperature").setValue(settings.temperature);
    lumetriEffect.property("Basic").property("Tint").setValue(settings.tint);
}
```

### 2.2 曲线调整

```
曲线类型：
1. RGB曲线 - 全局调整
2. 红通道曲线 - 红色调整
3. 绿通道曲线 - 绿色调整
4. 蓝通道曲线 - 蓝色调整
5. 色相vs饱和度曲线
6. 色相vs色相曲线
7. 色相vs亮度曲线
8. 饱和度vs饱和度曲线
```

---

## 三、调色工作流程

### 3.1 标准调色流程

```
三步调色法：
┌─────────────────────────────────────────────┐
│  Step 1: 一级校色                            │
│  - 曝光、对比度、白平衡                       │
│  - 还原正确色彩                              │
├─────────────────────────────────────────────┤
│  Step 2: 二级调色                            │
│  - 色彩分级、风格化                           │
│  - 创建电影感色调                            │
├─────────────────────────────────────────────┤
│  Step 3: 细节优化                            │
│  - 锐化、降噪、光晕                          │
│  - 增强画面质感                              │
└─────────────────────────────────────────────┘
```

### 3.2 一级校色技巧

| 工具 | 功能 | 使用方法 |
|------|------|---------|
| **自动色调** | 自动调整 | 快速修复基础问题 |
| **自动对比度** | 自动对比度 | 增加画面层次 |
| **自动颜色** | 自动白平衡 | 修复色偏 |
| **白平衡选择器** | 手动白平衡 | 点击中性灰区域 |

---

## 四、风格化调色预设

### 4.1 经典电影风格

```javascript
// 电影风格调色预设
function applyCinematicLook(clip) {
    var lumetri = clip.effects.add("Lumetri Color");
    
    // 降低对比度
    lumetri.property("Basic").property("Contrast").setValue(-10);
    
    // 降低饱和度
    lumetri.property("Saturation").property("Saturation").setValue(-15);
    
    // 添加暖色调
    lumetri.property("Basic").property("Temperature").setValue(500);
    
    // 曲线调整 - 电影对比度
    var curve = lumetri.property("RGB Curve").property("Curve");
    curve.setValue([
        [0, 0],
        [100, 50],
        [200, 220],
        [255, 255]
    ]);
}
```

### 4.2 热门风格预设

| 风格 | 特点 | 参数调整 |
|------|------|---------|
| **胶片风格** | 颗粒感、低对比度 | 降低对比度，添加颗粒 |
| **赛博朋克** | 青蓝+洋红 | 青色阴影，洋红高光 |
| **复古暖色** | 怀旧感 | 暖色温，低饱和度 |
| **日系清新** | 高亮度、低对比 | 提高亮度，降低对比 |

---

## 五、色轮与调色

### 5.1 色轮操作

```javascript
// 使用色轮调整
function adjustColorWheels(clip, shadows, midtones, highlights) {
    var lumetri = clip.effects.add("Lumetri Color");
    
    // 阴影色轮
    lumetri.property("Color Wheels").property("Shadows").setValue(shadows);
    
    // 中间调色轮
    lumetri.property("Color Wheels").property("Midtones").setValue(midtones);
    
    // 高光色轮
    lumetri.property("Color Wheels").property("Highlights").setValue(highlights);
}
```

### 5.2 色轮使用技巧

| 区域 | 颜色调整 | 效果 |
|------|---------|------|
| **阴影** | 青色 | 冷色调氛围 |
| **阴影** | 蓝色 | 夜晚感 |
| **中间调** | 橙色 | 皮肤红润 |
| **高光** | 黄色 | 温暖感 |
| **高光** | 青色 | 冷光感 |

---

## 六、HDR调色

### 6.1 HDR工作流程

```
HDR调色流程：
1. 导入HDR素材 (HDR10 / Dolby Vision)
2. 设置项目色彩空间为Rec.2020
3. 使用Lumetri Color进行调色
4. 导出HDR格式
```

### 6.2 HDR导出设置

| 设置项 | 推荐值 |
|--------|--------|
| **格式** | QuickTime |
| **视频编码** | ProRes 4444 XQ |
| **色彩空间** | Rec.2020 |
| **HDR格式** | HDR10 / Dolby Vision |

---

## 七、调色自动化

### 7.1 批量调色

```javascript
// 批量应用调色预设
function applyPresetToAllClips(presetName) {
    var sequence = app.project.activeSequence;
    
    for (var i = 0; i < sequence.videoTracks.numTracks; i++) {
        var track = sequence.videoTracks[i];
        for (var j = 0; j < track.clips.numClips; j++) {
            var clip = track.clips[j];
            clip.applyEffectPreset(presetName);
        }
    }
}
```

### 7.2 调色匹配

```javascript
// 匹配两段素材颜色
function matchColor(sourceClip, targetClip) {
    var matchEffect = targetClip.effects.add("Color Match");
    matchEffect.property("Source").setValue(sourceClip);
}
```

---

## 八、调色插件集成

### 8.1 常用调色插件

| 插件 | 功能 | 特点 |
|------|------|------|
| **Magic Bullet Looks** | 电影级调色 | 大量预设 |
| **Red Giant Colorista** | 精细调色 | 专业工具 |
| **FilmConvert** | 胶片模拟 | 真实胶片质感 |
| **DaVinci Resolve** | 专业调色 | 免费专业级 |

### 8.2 插件工作流

```
插件使用流程：
1. 一级校色 (Premiere内置)
2. 二级调色 (插件)
3. 细节处理 (插件)
4. 导出
```

---

## 九、常见调色问题

### 9.1 问题诊断

| 问题 | 表现 | 解决方案 |
|------|------|---------|
| **色偏** | 整体颜色偏移 | 使用白平衡工具 |
| **对比度不足** | 画面灰蒙 | 调整对比度/曲线 |
| **过曝** | 高光丢失 | 降低曝光/调整高光 |
| **欠曝** | 阴影死黑 | 提高曝光/调整阴影 |

### 9.2 肤色校正

```javascript
// 肤色保护调色
function protectSkinTones(clip) {
    var lumetri = clip.effects.add("Lumetri Color");
    
    // 启用肤色保护
    lumetri.property("Face Detection").property("Enable").setValue(true);
    
    // 设置肤色范围
    lumetri.property("Face Detection").property("Range").setValue(0.5);
}
```

---

> **关联文档**：
> - [[DaVinci-Resolve-企业级集成与调色指南]]
> - [[Premiere-Pro-时间线剪辑完全指南]]
> - [[Premiere-Pro-企业级集成与剪辑指南]]