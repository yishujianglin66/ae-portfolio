# Audition 多轨混音与母带处理完全指南

> 版本: 2025-v1 | 适用: 多轨混音/母带处理/响度标准化

## 一、多轨混音架构

### 1.1 轨道组织

```
标准多轨架构:
├── A1-A4: 对话/旁白 (蓝色)
├── A5-A8: 音乐/BGM (绿色)
├── A9-A12: 音效/Foley (黄色)
├── A13-A16: 环境音 (紫色)
├── Bus 1: 对话总线 → 压缩+EQ
├── Bus 2: 音乐总线 → 轻度压缩
├── Bus 3: 音效总线 → 限制器
└── Master: 响度标准化
```

### 1.2 总线路由

| 总线 | 输入 | 处理 | 输出 |
|------|------|------|------|
| 对话总线 | A1-A4 | 压缩+EQ+去齿音 | Master |
| 音乐总线 | A5-A8 | 多段压缩 | Master |
| 音效总线 | A9-A12 | 限制器 | Master |
| Master | 所有Bus | 响度+限制 | 输出 |

### 1.3 闪避(Ducking)

```
自动闪避设置:
1. 选中BGM轨道
2. 效果→振幅与压限→闪避
3. 侧链源: 对话轨道
4. 参数:
   - 衰减量: -6dB(对话时BGM降低)
   - 启动: 200ms
   - 释放: 500ms
   - 阈值: -30dB
```

## 二、母带处理

### 2.1 母带处理链

```
Master总线处理链:
1. 参数EQ(微调)
   - 高通30Hz(去次低频)
   - 低架提升50Hz(+1dB,增加厚度)
   - 高频架12kHz(+0.5dB,增加空气感)

2. 多段压缩(轻度)
   - 低频(20-200Hz): 2:1, 轻触
   - 中频(200-4kHz): 1.5:1, 极轻
   - 高频(4k-20kHz): 2:1, 轻触

3. 立体声增强(微量)
   - 宽度: 105-110%(极轻微)

4. 限制器(最终)
   - 天花板: -1 dBTP
   - 释放: 自动

5. 响度计(监控)
   - 目标: -14 LUFS(YouTube)
   - 或 -16 LUFS(播客)
```

### 2.2 响度标准对照

| 平台 | 目标响度 | 真峰值 | 标准 |
|------|---------|--------|------|
| YouTube | -14 LUFS | -1 dBTP | YouTube |
| 播客 | -16 LUFS | -1 dBTP | Apple/Spotify |
| B站 | -14 LUFS | -1 dBTP | B站推荐 |
| 抖音 | -11 LUFS | -1 dBTP | TikTok |
| 广播(中国) | -24 LUFS | -2 dBTP | GB/T |
| 广播(欧洲) | -23 LUFS | -1 dBTP | EBU R128 |
| 音乐 | -14 LUFS | -1 dBTP | 流媒体 |

## 三、音效设计

### 3.1 音效分类

| 类别 | 命名规范 | 示例 |
|------|---------|------|
| Foley | FOLY_动作_材质_编号 | FOLY_脚步_木地板_01 |
| 环境 | AMB_场景_时间_编号 | AMB_城市_白天_01 |
| UI | UI_动作_类型_编号 | UI_点击_按钮_01 |
| 转场 | TRANS_类型_编号 | TRANS_whoosh_01 |
| 冲击 | HIT_材质_编号 | HIT_金属_01 |
| 音乐 | MUSIC_情绪_BPM_编号 | MUSIC_紧张_120bpm_01 |

### 3.2 音效处理技巧

| 技巧 | 方法 | 效果 |
|------|------|------|
| 音高变换 | 效果→时间与变调→变调 | 改变音调 |
| 时间拉伸 | 效果→时间与变调→伸缩 | 改变时长 |
| 反向 | 效果→特殊→反向 | 反转音效 |
| 混响 | 效果→混响→卷积混响 | 空间感 |
| 延迟 | 效果→延迟→模拟延迟 | 回声 |
| 失真 | 效果→特殊→失真 | 粗糙感 |

## 四、ExtendScript自动化

### 4.1 基础脚本

```javascript
// audition_script.jsx
// 批量响度标准化
var files = [
    "/audio/ep01.wav",
    "/audio/ep02.wav"
];

for (var i = 0; i < files.length; i++) {
    var doc = app.openDocument(File(files[i]));
    doc.matchLoudness({
        targetLoudness: -16,
        truePeakLimit: -1,
        tolerance: 1
    });
    doc.save();
    doc.close();
}
```

### 4.2 批量导出脚本

```javascript
// batch_export.jsx
var doc = app.activeDocument;
var formats = [
    {name: "YouTube", format: "MP3", bitrate: 320},
    {name: "Podcast", format: "MP3", bitrate: 128},
    {name: "Master", format: "WAV", bits: 24}
];

for (var i = 0; i < formats.length; i++) {
    var opts = new ExportOptions();
    opts.format = formats[i].format;
    // 导出逻辑...
}
```

## 五、与视频工作流集成

### 5.1 PR↔AU工作流

```
Premiere Pro → Audition:
1. 选中音频片段
2. 右键→在Audition中编辑
3. Audition打开单轨会话
4. 执行修复/调色/母带
5. Ctrl+S保存
6. PR自动更新

Audition → Premiere Pro:
1. 在AU中完成混音
2. 导出为WAV(48kHz/24bit)
3. 导入PR时间线
4. 替换原始音频
```

### 5.2 多软件协作最佳实践

- 所有音频统一48kHz/24bit
- 使用统一命名规范
- 导出前做响度检查
- 保留工程文件备份
- 使用LOUDNESS METER实时监控
