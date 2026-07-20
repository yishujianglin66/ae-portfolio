#!/usr/bin/env python3
"""
调用 V4-Pro 深度策划完整视频脚本
"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from ai_agent import V4Agent

agent = V4Agent()

prompt = r"""
请为以下素材深度策划一个完整的《冰海战记》战斗剪辑视频脚本：

## 素材信息

### 音频素材
- 文件: ae实战音乐.mp3
- 时长: 23.15秒
- BPM: 112.35
- 风格: 激昂战斗音乐

### 视频素材
1. 冰海战记.mp4 - 0.7MB（预计10-15秒）
2. 托尔芬.mp4 - 0.3MB（预计5-8秒）
3. 额外可用: 木偶风格参考帧、高帧率处理版本

## 要求

1. **时间轴规划**: 精确到秒，将23秒音乐分为Intro → Build → Drop → Break → Outro 五个段落
2. **镜头安排**: 每个段落安排合适的画面（托尔芬特写、战斗场景、氛围镜头）
3. **节奏卡点**: 标记BPM节拍点，确定哪些强拍需要视觉冲击
4. **效果设计**: 每个镜头应使用什么AE效果（Glow、ColorBalance、Blur、粒子等）
5. **色彩风格**: 冰海战记风格（冷色调、高对比度、战斗氛围）
6. **字幕文案**: 建议的台词或文字出现时机和内容
7. **转场设计**: 段落之间的转场方式
8. **分层结构**: 背景层、主体层、前景层、特效层的安排

## 输出格式

请以JSON格式输出完整脚本，包含：
- timeline: 时间轴（秒）
- segments: 五个段落详情
- beats: 节拍卡点标记
- effects: 效果设计
- colors: 色彩方案
- text: 字幕文案
"""

print("=" * 60)
print("调用 V4-Pro 深度策划视频脚本")
print("=" * 60)

result = agent.analyze(prompt)
print("\n" + "=" * 60)
print("V4 脚本策划结果")
print("=" * 60)
print(result)

with open("scripts/video_script_v4.json", "w", encoding="utf-8") as f:
    f.write(result)

print("\n[已保存] scripts/video_script_v4.json")