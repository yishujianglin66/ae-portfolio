"""
test_effect_registry.py - 测试效果注册表知识库集成
"""
from effect_registry import KEYWORD_TO_EFFECT_MAP, get_effect_matchname

print(f"总映射数: {len(KEYWORD_TO_EFFECT_MAP)}")
print(f"高斯模糊: {get_effect_matchname('高斯模糊')}")
print(f"particular: {get_effect_matchname('particular')}")
print(f"grid_wipe: {get_effect_matchname('grid_wipe')}")
print(f"starglow: {get_effect_matchname('starglow')}")
print(f"turbulent: {get_effect_matchname('turbulent')}")

# 验证知识库新增条目
kb_only = [k for k in KEYWORD_TO_EFFECT_MAP if k.startswith('grid') or k.startswith('cross')]
print(f"\n知识库新增关键词示例: {kb_only[:10]}")
