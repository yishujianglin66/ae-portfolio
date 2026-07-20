#!/usr/bin/env python3
"""
调用 V4 深度分析 Phase 2 方案
"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from ai_agent import V4Agent

agent = V4Agent()

prompt = """
请深度审查以下 AE 音频驱动自动化方案，目标是"效果达到最完美"。

## 当前架构

1. **音频分析层**: librosa 提取 BPM、节拍时间点、能量曲线
2. **映射引擎层**: BeatKeyframeMapper (动态规划匹配，10ms精度)
3. **AE执行层**: 通过 AE MCP Bridge 批量写入关键帧 + 表达式

## 当前关键帧生成策略

每个节拍生成3个关键帧:
- Scale: 强拍 100→115, 弱拍 100→105 (easeInOut/linear)
- Opacity: 70→100 (easeOut/linear)
- Rotation: 0→30 持续累积 (linear)

表达式:
- Opacity: `80 + sin(t*2*pi*2.133) * 20` (正弦波呼吸)
- Rotation: `t*3 + sin(t*2*pi*2.133) * 5` (持续旋转+摆动)

## 素材信息
- 视频: 冰海战记 (Vinland Saga) 战斗剪辑
- 目标风格: 热血、节奏感强、冲击力强
- 当前BPM: 模拟128，待替换为真实音频分析

## 请分析并给出优化建议

1. **关键帧策略优化**: 当前每个节拍3个关键帧是否最优？是否应该区分强拍/弱拍/反拍的不同效果？
2. **表达式优化**: 当前正弦波表达式是否太简单？如何加入能量曲线驱动？
3. **效果参数驱动**: Glow、Fast Blur、Color Balance 如何参与音频驱动？
4. **多层协同**: 背景层、主体层、前景层分别应该响应哪些频段？
5. **贝塞尔包络**: 如何利用 BeatKeyframeMapper 的 calculate_bezier_envelope 生成更平滑的过渡？
6. **风格适配**: 针对"热血战斗"主题，推荐哪种 mapping style (default/on_beat/off_beat/double_time/half_time)？

请给出: 结论优先，然后逐条详细分析，最后给出可直接执行的 ExtendScript/Python 代码示例。
"""

print("=" * 60)
print("调用 V4-Pro 深度分析 Phase 2 方案")
print("=" * 60)

result = agent.analyze(prompt)
print("\n" + "=" * 60)
print("V4 分析结果")
print("=" * 60)
print(result)

# 保存结果
with open("reports/v4_phase2_review.md", "w", encoding="utf-8") as f:
    f.write("# V4 深度分析: Phase 2 音频驱动优化方案\n\n")
    f.write(result)
    f.write("\n")

print("\n[已保存] reports/v4_phase2_review.md")
