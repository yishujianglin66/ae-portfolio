#!/usr/bin/env python3
"""
调用 V4 深度审查实战经验文档，提出优化建议
"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from ai_agent import V4Agent

agent = V4Agent()

prompt = r"""
请深度审查以下 AE 音频驱动自动化实战经验文档，提出可操作的优化建议：

## 文档位置
C:\Users\Administrator\Desktop\AE-Knowledge-Vault\10-风格化剪辑知识库\Phase2实战经验总结.md

## 已实现的内容
1. ExtendScript 显式 return 问题已解决
2. 强拍5帧/弱拍2帧差异化模板已实现
3. 4频段能量滑块控制器已创建
4. Glow/Opacity/Rotation 表达式已绑定
5. 真实音频分析（librosa）已集成

## 待优化项
1. 音频素材过短（仅4秒），冲击感不完整
2. 贝塞尔包络未实际应用
3. 单层驱动，背景/前景未分层
4. 风格自适应（on_beat/double_time切换）未实现

## 请分析以下维度

1. **文档结构优化**: 经验文档是否遗漏关键信息？应增加哪些章节？
2. **复用性提升**: 如何让这份经验文档更易于下次实战快速复用？
3. **自动化程度**: 哪些手动步骤可以进一步自动化？
4. **质量保证**: 如何在实战前自动检测潜在问题（如超时、返回值）？
5. **扩展方向**: Phase 3 应该优先实现什么？如何与 Phase 2 平滑衔接？
6. **知识沉淀**: 如何将 V4 的深度分析结果结构化沉淀，而非一次性消费？

请给出：
- 结论优先（3条核心建议）
- 逐维度详细分析
- 可直接执行的代码/脚本示例
- 下次实战的"一键启动"检查脚本
"""

print("=" * 60)
print("调用 V4-Pro 深度审查实战经验文档")
print("=" * 60)

result = agent.analyze(prompt)
print("\n" + "=" * 60)
print("V4 审查结果")
print("=" * 60)
print(result)

# 保存结果
with open("reports/v4_experience_review.md", "w", encoding="utf-8") as f:
    f.write("# V4 深度审查: Phase 2 实战经验文档优化建议\n\n")
    f.write(result)
    f.write("\n")

print("\n[已保存] reports/v4_experience_review.md")