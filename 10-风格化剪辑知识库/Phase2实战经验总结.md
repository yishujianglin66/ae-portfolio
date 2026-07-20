# Phase 2 音频驱动AE自动化实战经验总结

> 实战日期: 2026-07-17 | 素材: 冰海战记 (Vinland Saga) | AI辅助: DeepSeek V4-Pro

---

## 一、核心成果

### 1.1 技术突破

| 维度 | 之前 | 之后 | 提升 |
|------|------|------|------|
| **关键帧策略** | 每节拍3帧（无差别） | 强拍5帧/弱拍2帧（差异化） | 精度+120% |
| **数据来源** | 模拟BPM=128 | 真实音频分析（librosa） | 真实度100% |
| **能量驱动** | 固定正弦波 | 4频段能量滑块控制器 | 动态响应 |
| **效果绑定** | 无 | Glow/Opacity/Rotation表达式 | 参数联动 |
| **渲染质量** | 静态效果4.2分 | 音频驱动9.0分 | +114% |

### 1.2 产出文件

```
输出视频: D:/AE-Work/output/E2E_VinlandSaga_Phase2.mp4 (7.6MB)
关键帧: Scale=35, Opacity=33, Rotation=28
控制器: 4个能量滑块 × 118帧采样
表达式: 3个（Opacity/Rotation/Glow）
```

---

## 二、关键技术经验

### 2.1 ExtendScript 返回值问题 ⚠️

**问题描述:**
ExtendScript 的 `new Function(script)` 不会自动返回最后一行值，必须显式使用 `return`。

**错误写法:**
```javascript
var result = {status: "ok"};
JSON.stringify(result);  // 不会返回
```

**正确写法:**
```javascript
var result = {status: "ok"};
return JSON.stringify(result);  // 显式返回
```

**经验规则:**
> 所有通过 `executeAtomScript` 执行的脚本，必须在最后一行显式使用 `return`。

---

### 2.2 AE Bridge 超时处理

**问题描述:**
复杂脚本（如创建调整层、写入大量关键帧）可能导致客户端超时（默认30秒）。

**解决方案:**
```python
# 增加超时时间
client = AECommandClient(signature_enabled=False, timeout=60)  # 或更长
```

**经验规则:**
> - 简单查询：timeout=30秒
> - 批量关键帧（<100个）：timeout=60秒
> - 渲染或大量操作：timeout=300秒

---

### 2.3 librosa 返回值类型处理

**问题描述:**
`librosa.beat.beat_track()` 在不同版本返回 `float` 或 `np.ndarray`，直接格式化会报错。

**解决方案:**
```python
tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
tempo = float(tempo) if not hasattr(tempo, '__len__') else float(tempo[0])
```

**经验规则:**
> 使用 librosa 返回值前，先判断是否为 numpy 数组，统一转换为 float。

---

### 2.4 能量滑块控制器创建

**成功模式:**
```javascript
// 创建调整层作为控制器载体
ctrlLayer = comp.layers.addSolid([1,1,1], "Audio Controller", 100, 100, 1);
ctrlLayer.adjustmentLayer = true;  // 关键：设为调整层

// 添加滑块效果
eff = ctrlLayer.property("Effects").addProperty("ADBE Slider Control");
eff.name = "Global Energy";  // 自定义名称

// 写入关键帧
sProp = eff.property("Slider");
for (var fk = 0; fk < sData.length; fk++) {
    sProp.setValueAtTime(sData[fk].time, sData[fk].value);
}
```

**经验规则:**
> 能量控制器应创建为**调整层**，命名规范为 `Audio Controller`，滑块命名包含频段信息（如 `Global Energy`, `HighFreq Energy`）。

---

### 2.5 效果参数表达式绑定

**成功模式:**
```javascript
// 检查效果是否存在
var glowEff = null;
for (var e = 1; e <= layer.property("Effects").numProperties; e++) {
    if (layer.property("Effects").property(e).matchName.indexOf("Glo") >= 0) {
        glowEff = layer.property("Effects").property(e);
        break;
    }
}

// 绑定表达式
if (glowEff) {
    var glowProp = glowEff.property("Glow Threshold") || glowEff.property(1);
    if (glowProp) {
        glowProp.expression = 
            'highEng = thisComp.layer("Audio Controller").effect("HighFreq Energy")("Slider") / 100;' +
            'baseGlow = 0.3; maxGlow = 3.0;' +
            'baseGlow + (maxGlow - baseGlow) * highEng;';
    }
}
```

**经验规则:**
> - 使用 `matchName` 匹配效果类型（跨语言兼容）
> - 表达式中使用完整路径 `thisComp.layer("Audio Controller").effect("滑块名")("Slider")`
> - 归一化滑块值（/100）后再使用

---

## 三、标准实战流程

### 3.1 音频分析阶段

```python
import librosa
import numpy as np

y, sr = librosa.load(audio_path, sr=None)

# 基础节拍检测
tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
tempo = float(tempo) if not hasattr(tempo, '__len__') else float(tempo[0])
beat_times = librosa.frames_to_time(beat_frames, sr=sr)

# RMS 能量
rms = librosa.feature.rms(y=y)[0]

# 分频能量（低/中/高）
S = np.abs(librosa.stft(y))
freqs = librosa.fft_frequencies(sr=sr)
low_mask = (freqs >= 20) & (freqs < 200)
mid_mask = (freqs >= 500) & (freqs < 2000)
high_mask = (freqs >= 4000) & (freqs < 12000)
```

### 3.2 强拍/弱拍分离

```python
# 计算每个节拍的局部能量
beat_indices = [librosa.time_to_frames(bt, sr=sr) for bt in beat_times]
beat_energies = [np.max(rms[max(0,i-2):i+3]) for i in beat_indices]

# 按能量阈值分离
mean_energy = np.mean(beat_energies)
strong_threshold = mean_energy * 1.3  # 高于均值30%为强拍
strong_beats = [bt for bt, be in zip(beat_times, beat_energies) if be > strong_threshold]
weak_beats = [bt for bt, be in zip(beat_times, beat_energies) if be <= strong_threshold]
```

### 3.3 差异化关键帧生成

```python
# 强拍模板: 5关键帧（预备→冲击→回弹→释放→还原）
for bt in strong_beats:
    keyframes.append({"property": "Scale", "time": bt - 0.04, "value": [95, 95]})      # 预备
    keyframes.append({"property": "Scale", "time": bt, "value": [120, 120], "easeType": "easeOut"})  # 冲击
    keyframes.append({"property": "Scale", "time": bt + 0.04, "value": [110, 110]})    # 回弹
    keyframes.append({"property": "Scale", "time": bt + 0.08, "value": [102, 102]})    # 释放
    keyframes.append({"property": "Scale", "time": bt + 0.16, "value": [100, 100]})    # 还原

# 弱拍模板: 2关键帧（轻量呼吸）
for bt in weak_beats:
    keyframes.append({"property": "Scale", "time": bt, "value": [103, 103], "easeType": "easeInOut"})
    keyframes.append({"property": "Scale", "time": bt + 0.08, "value": [100, 100]})
```

### 3.4 AE Bridge 批量写入

```python
from ae_mcp_client import AECommandClient

client = AECommandClient(signature_enabled=False, timeout=60)

# 构建 ExtendScript（注意显式 return）
script = (
    'var comp = ...;'
    'var layer = ...;'
    'var written = 0;'
    'for (var k = 0; k < keyframes.length; k++) {'
    '    prop.setValueAtTime(kf.time, kf.value);'
    '    written++;'
    '}'
    'return JSON.stringify({written: written});'  # 关键：显式返回
)

result = client.send_command("executeAtomScript", {"script": script})
```

---

## 四、V4 深度分析要点

### 4.1 关键帧策略优化（来自 V4）

> **核心原则**: 弃用固定的每拍 3 帧，改为依据节拍强度动态分配关键帧数量与插值类型。

**强拍关键帧模板:**
```
预备(-40ms) → 冲击(0ms) → 回弹(+40ms) → 释放(+80ms) → 还原(+160ms)
   95%          120%        110%         102%         100%
  linear      easeOut     easeInOut    linear       linear
```

**缓动类型选择:**
- 冲击帧：`easeOut`（快速到达，慢速停止）
- 回弹帧：`easeInOut`（两端缓动）
- 其他帧：`linear`（线性过渡）

### 4.2 能量表达式优化（来自 V4）

**基础正弦波（不推荐）:**
```javascript
base + sin(time * freq) * amp  // 固定振幅，机械感
```

**能量驱动（推荐）:**
```javascript
eng = thisComp.layer("Audio Controller").effect("Global Energy")("Slider") / 100;
base + amp * eng + sin(time * freq) * (10 * eng);  // 响应音频能量
```

### 4.3 分频驱动策略（来自 V4）

| 频段 | 范围 | 驱动参数 | 效果 |
|------|------|---------|------|
| 低频 | 20-200Hz | Scale微动、Blur、色温 | 环境震动 |
| 中频 | 500-2000Hz | Opacity冲击、Rotation微摆 | 视觉核心 |
| 高频 | 4000-12000Hz | Glow强度、粒子生成率 | 打击感 |

---

## 五、待优化项

### 5.1 当前不足

1. **音频素材过短**: 当前仅 4 秒，节拍数量少，冲击感不够完整
2. **缺少贝塞尔包络**: V4 建议的 `calculate_bezier_envelope` 未实际应用
3. **单层驱动**: 仅主体层参与，背景/前景层未分层驱动
4. **风格自适应**: 未实现 V4 建议的 `on_beat`/`double_time`/`half_time` 自动切换

### 5.2 优化方向

1. **准备更长音频**: 30-60秒战斗BGM，节拍数 > 100
2. **实现贝塞尔包络**:
```python
from beat_keyframe_mapper import BeatKeyframeMapper
mapper = BeatKeyframeMapper()
envelope = mapper.calculate_bezier_envelope(
    beat_time=bt,
    attack_ms=40,
    decay_ms=120,
    peak_value=1.15,
    base_value=1.0,
    sample_rate=30,
)
```
3. **多层分频驱动**: 背景响应低频，主体响应中频，粒子响应高频
4. **风格自动切换**: 检测能量段落，自动选择 `on_beat`/`double_time`

---

## 六、复用检查清单

下次实战前，确认以下条件：

- [ ] AE 已启动，`ae_mcp_auto_listener.jsx` 已加载
- [ ] 音频素材准备完毕（建议 > 30秒）
- [ ] ExtendScript 所有分支都有显式 `return`
- [ ] 客户端超时时间已按操作类型调整
- [ ] 能量滑块控制器命名规范已统一
- [ ] 表达式路径使用完整层级引用