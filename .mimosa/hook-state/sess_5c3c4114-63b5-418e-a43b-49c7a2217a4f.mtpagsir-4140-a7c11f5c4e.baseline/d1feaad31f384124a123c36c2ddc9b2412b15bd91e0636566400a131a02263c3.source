#!/usr/bin/env python3
"""
tests/test_transition_adapter_substring_gaps.py - commit bf99595 子串匹配修复回归测试

覆盖修复前从 0 条恢复到 31 条的关键逻辑：
  1. _find_type_column  子串/宽松匹配 + 排除列
  2. _find_effect_column 子串/宽松匹配 + 排除列
  3. _to_snake_case       各种命名风格转换
  4. _parse_params        参数解析（数值、字符串、空值、中文逗号边界）
  5. extract_from_blocks  用非精确列表头构造 MdBlock.TABLE 验证提取
  6. extract_from_text_blocks  KV 解析（粗体/非粗体 key、display_name 缺失等）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_base.types import BlockType, MdBlock, TransitionRecipe
from knowledge_base.adapters.transition_adapter import TransitionAdapter


@pytest.fixture
def adapter() -> TransitionAdapter:
    """每个测试用例共享一个适配器实例。"""
    return TransitionAdapter()


# =========================================================================
#  场景 1：_find_type_column 子串匹配
# =========================================================================
class TestFindTypeColumn:
    """类型列查找：精确匹配 → 子串匹配 → 宽松匹配 → 排除列。"""

    def test_exact_match_zhuanchang_leixing(self, adapter: TransitionAdapter) -> None:
        """精确匹配："转场类型"。"""
        headers = ["序号", "转场类型", "效果match", "备注"]
        assert adapter._find_type_column(headers) == "转场类型"

    def test_exact_match_transition_type(self, adapter: TransitionAdapter) -> None:
        """精确匹配："transition_type"。"""
        headers = ["transition_type", "effect_match"]
        assert adapter._find_type_column(headers) == "transition_type"

    def test_exact_match_transition(self, adapter: TransitionAdapter) -> None:
        """精确匹配："transition"（全小写后）。"""
        headers = ["Transition", "Effect Match"]
        assert adapter._find_type_column(headers) == "Transition"

    def test_substr_zhuanchang_fenlei(self, adapter: TransitionAdapter) -> None:
        """子串匹配：列名含"转场"且含"分类" → "转场分类"。"""
        headers = ["序号", "转场分类", "AE对应效果名"]
        assert adapter._find_type_column(headers) == "转场分类"

    def test_substr_zhuanchang_type(self, adapter: TransitionAdapter) -> None:
        """子串匹配：列名含"转场"且含"type" → "转场type"。"""
        headers = ["名称", "转场type", "效果"]
        assert adapter._find_type_column(headers) == "转场type"

    def test_substr_zhuanchang_effect_type(self, adapter: TransitionAdapter) -> None:
        """子串匹配：列名含"转场"和"类型"（非紧邻） → "转场效果类型"。"""
        headers = ["ID", "转场效果类型", "AE效果名"]
        assert adapter._find_type_column(headers) == "转场效果类型"

    def test_loose_changjian_zhuanchang(self, adapter: TransitionAdapter) -> None:
        """宽松匹配：列名仅含"转场"，不含排除关键词 → "常见转场"。"""
        headers = ["序号", "常见转场", "AE原生效果"]
        assert adapter._find_type_column(headers) == "常见转场"

    def test_loose_changyong_zhuanchang(self, adapter: TransitionAdapter) -> None:
        """宽松匹配：列名仅含"转场" → "常用转场"。"""
        headers = ["常用转场", "AE方案"]
        assert adapter._find_type_column(headers) == "常用转场"

    def test_exclude_zhuanchang_miaoshu(self, adapter: TransitionAdapter) -> None:
        """排除列：列名含"转场描述" → 返回 None。"""
        headers = ["转场描述", "转场分类", "效果"]
        # 因为"转场分类"在第二个位置会命中，但单独给"转场描述"要返回None
        headers_only_bad = ["转场描述", "其他说明"]
        assert adapter._find_type_column(headers_only_bad) is None

    def test_exclude_zhuanchang_changjing(self, adapter: TransitionAdapter) -> None:
        """排除列：列名含"转场场景" → 返回 None。"""
        headers = ["转场场景", "参数"]
        assert adapter._find_type_column(headers) is None

    def test_exclude_zhuanchang_shichang(self, adapter: TransitionAdapter) -> None:
        """排除列：列名含"转场时长" → 返回 None。"""
        headers = ["转场时长", "说明"]
        assert adapter._find_type_column(headers) is None

    def test_exclude_zhuanchang_tedian(self, adapter: TransitionAdapter) -> None:
        """排除列：列名含"转场特点" → 返回 None。"""
        headers = ["转场特点", "举例"]
        assert adapter._find_type_column(headers) is None

    def test_no_zhuanchang_returns_none(self, adapter: TransitionAdapter) -> None:
        """完全不含"转场"相关关键词 → 返回 None。"""
        headers = ["名称", "效果", "参数"]
        assert adapter._find_type_column(headers) is None

    def test_priority_exact_over_substr(self, adapter: TransitionAdapter) -> None:
        """优先级：精确匹配 > 子串匹配。"""
        headers = ["转场分类", "转场类型"]
        # "转场类型" 是精确匹配项，应优先返回
        assert adapter._find_type_column(headers) == "转场类型"


# =========================================================================
#  场景 2：_find_effect_column 子串匹配
# =========================================================================
class TestFindEffectColumn:
    """效果列查找：精确匹配 → 子串匹配(ae+关键词) → 宽松匹配(ae非脚本)。"""

    def test_exact_match_effectmatch(self, adapter: TransitionAdapter) -> None:
        """精确匹配："效果match"。"""
        headers = ["转场类型", "效果match", "参数"]
        assert adapter._find_effect_column(headers) == "效果match"

    def test_exact_match_effect_match(self, adapter: TransitionAdapter) -> None:
        """精确匹配："effect_match"。"""
        headers = ["transition_type", "effect_match", "params"]
        assert adapter._find_effect_column(headers) == "effect_match"

    def test_substr_ae_duiying_guoming(self, adapter: TransitionAdapter) -> None:
        """子串匹配：含"ae"且含"对应"+"名称" → "AE对应效果名"。"""
        headers = ["转场分类", "AE对应效果名", "备注"]
        assert adapter._find_effect_column(headers) == "AE对应效果名"

    def test_substr_ae_yuansheng(self, adapter: TransitionAdapter) -> None:
        """子串匹配：含"ae"且含"原生" → "AE原生效果"。"""
        headers = ["常见转场", "AE原生效果"]
        assert adapter._find_effect_column(headers) == "AE原生效果"

    def test_substr_ae_yuanzi(self, adapter: TransitionAdapter) -> None:
        """子串匹配：含"ae"且含"原子" → "AE原子方案"。"""
        headers = ["转场类型", "AE原子方案", "说明"]
        assert adapter._find_effect_column(headers) == "AE原子方案"

    def test_substr_ae_gongcheng_fangan(self, adapter: TransitionAdapter) -> None:
        """子串匹配：含"ae"且含"工程方案" → "AE工程方案"。"""
        headers = ["转场", "AE工程方案"]
        assert adapter._find_effect_column(headers) == "AE工程方案"

    def test_substr_ae_match(self, adapter: TransitionAdapter) -> None:
        """子串匹配：含"ae"且含"match" → "AE Match Name"。"""
        headers = ["type", "AE Match Name"]
        assert adapter._find_effect_column(headers) == "AE Match Name"

    def test_substr_ae_mingcheng(self, adapter: TransitionAdapter) -> None:
        """子串匹配：含"ae"且含"名称" → "AE效果名称"。"""
        headers = ["转场分类", "AE效果名称"]
        assert adapter._find_effect_column(headers) == "AE效果名称"

    def test_loose_ae_effect_name(self, adapter: TransitionAdapter) -> None:
        """宽松匹配：任何含"ae"的非脚本列 → "AE效果名"。"""
        headers = ["转场", "AE效果名"]
        assert adapter._find_effect_column(headers) == "AE效果名"

    def test_loose_case_insensitive_ae(self, adapter: TransitionAdapter) -> None:
        """宽松匹配：大小写不敏感 → "ae效果"。"""
        headers = ["转场", "ae效果"]
        assert adapter._find_effect_column(headers) == "ae效果"

    def test_exclude_ae_script_zh(self, adapter: TransitionAdapter) -> None:
        """排除列：含"脚本"的AE列 → "AE实现脚本" 应被排除。"""
        headers = ["转场分类", "AE实现脚本", "AE效果名称"]
        # "AE实现脚本" 被跳过，命中 "AE效果名称"
        assert adapter._find_effect_column(headers) == "AE效果名称"

    def test_exclude_ae_script_en(self, adapter: TransitionAdapter) -> None:
        """排除列：含"script"的AE列 → "AE Script" 应被排除。"""
        headers_only_script = ["Transition", "AE Script"]
        assert adapter._find_effect_column(headers_only_script) is None

    def test_exclude_only_script_and_no_ae(self, adapter: TransitionAdapter) -> None:
        """没有任何AE列 → 返回 None。"""
        headers = ["名称", "脚本", "说明"]
        assert adapter._find_effect_column(headers) is None

    def test_priority_exact_over_substr_and_loose(self, adapter: TransitionAdapter) -> None:
        """优先级：精确 > 子串(ae+关键词) > 宽松。"""
        headers = ["AE效果", "效果match", "AE实现脚本"]
        assert adapter._find_effect_column(headers) == "效果match"

    def test_priority_substr_over_loose(self, adapter: TransitionAdapter) -> None:
        """优先级：子串(ae+关键词) > 宽松。"""
        headers = ["效果", "AE对应效果名", "AE名称"]
        # "AE对应效果名" 含ae且含"对应"/"名称"，优先级高于宽松
        assert adapter._find_effect_column(headers) == "AE对应效果名"


# =========================================================================
#  场景 3：_to_snake_case 命名转换
# =========================================================================
class TestToSnakeCase:
    """静态方法 _to_snake_case 各种风格转换。"""

    def test_space_to_underscore(self) -> None:
        """空格转下划线："线性 擦除" → "linear_wipe"。"""
        assert TransitionAdapter._to_snake_case("线性 擦除") == "线性_擦除"

    def test_hyphen_to_underscore(self) -> None:
        """连字符转下划线："linear-wipe" → "linear_wipe"。"""
        assert TransitionAdapter._to_snake_case("linear-wipe") == "linear_wipe"

    def test_camel_case(self) -> None:
        """CamelCase 转 snake："LinearWipe" → "linear_wipe"。"""
        assert TransitionAdapter._to_snake_case("LinearWipe") == "linear_wipe"

    def test_mixed_space_hyphen_camel(self) -> None:
        """混合：空格+连字符+CamelCase → "Linear Wipe-Test" → "linear_wipe_test"。"""
        assert TransitionAdapter._to_snake_case("Linear Wipe-Test") == "linear_wipe_test"

    def test_strip_leading_trailing_underscores(self) -> None:
        """清理前后下划线："__wipe__" → "wipe"。"""
        assert TransitionAdapter._to_snake_case("__wipe__") == "wipe"

    def test_already_snake(self) -> None:
        """已是 snake_case 保持不变（仅转小写）。"""
        assert TransitionAdapter._to_snake_case("Linear_Wipe") == "linear_wipe"

    def test_multiple_spaces_and_hyphens(self) -> None:
        """多个连续空格/连字符合并为一个下划线。"""
        assert TransitionAdapter._to_snake_case("Linear   Wipe--Test") == "linear_wipe_test"

    def test_empty_string(self) -> None:
        """空字符串 → 空字符串。"""
        assert TransitionAdapter._to_snake_case("") == ""

    def test_single_word(self) -> None:
        """单个单词只转小写。"""
        assert TransitionAdapter._to_snake_case("FADE") == "fade"


# =========================================================================
#  场景 4：_parse_params 参数解析
# =========================================================================
class TestParseParams:
    """静态方法 _parse_params 数值/字符串/空值/边界。"""

    def test_integer_value(self) -> None:
        """整数："Wipe Angle=0" → {"Wipe Angle": 0}。"""
        result = TransitionAdapter._parse_params("Wipe Angle=0")
        assert result == {"Wipe Angle": 0}
        assert isinstance(result["Wipe Angle"], int)

    def test_float_value(self) -> None:
        """浮点数："Feather=30.5" → {"Feather": 30.5}。"""
        result = TransitionAdapter._parse_params("Feather=30.5")
        assert result == {"Feather": 30.5}
        assert isinstance(result["Feather"], float)

    def test_string_value(self) -> None:
        """字符串："Interpolation=linear" → {"Interpolation": "linear"}。"""
        result = TransitionAdapter._parse_params("Interpolation=linear")
        assert result == {"Interpolation": "linear"}
        assert isinstance(result["Interpolation"], str)

    def test_multiple_params(self) -> None:
        """多参数："Wipe Angle=0, Feather=30" → 两个键。"""
        result = TransitionAdapter._parse_params("Wipe Angle=0, Feather=30")
        assert result == {"Wipe Angle": 0, "Feather": 30}
        assert len(result) == 2

    def test_empty_string(self) -> None:
        """空字符串 → {}。"""
        assert TransitionAdapter._parse_params("") == {}

    def test_none_equals_token_skipped(self) -> None:
        """无等号 token 跳过："description only" → {}。"""
        assert TransitionAdapter._parse_params("description only") == {}

    def test_mixed_none_equals_and_valid(self) -> None:
        """混合：有效键值对 + 无等号描述 → 只保留有效对。"""
        result = TransitionAdapter._parse_params("Wipe Angle=0, description here, Feather=30")
        assert result == {"Wipe Angle": 0, "Feather": 30}
        assert len(result) == 2

    def test_empty_pair_between_commas(self) -> None:
        """逗号间空值："Wipe Angle=0,,Feather=30" → 两个键。"""
        result = TransitionAdapter._parse_params("Wipe Angle=0,,Feather=30")
        assert result == {"Wipe Angle": 0, "Feather": 30}
        assert len(result) == 2

    def test_whitespace_only_pair(self) -> None:
        """逗号间纯空格 token 跳过。"""
        result = TransitionAdapter._parse_params("A=1,   , B=2")
        assert result == {"A": 1, "B": 2}
        assert len(result) == 2

    def test_chinese_comma_current_behavior(self) -> None:
        """中文逗号边界：当前实现仅 split(",") 不处理中文逗号，断言行为。

        "Wipe Angle=0，Feather=30" 整体被当作一个 pair（没有英文逗号分割），
        但等号出现后 val="0，Feather=30"（含中文逗号），无法转 int/float，最终保留为字符串。
        """
        result = TransitionAdapter._parse_params("Wipe Angle=0，Feather=30")
        # 中文逗号不被视为分隔符，仅产生一个 key
        assert "Wipe Angle" in result
        assert len(result) == 1
        # 非英文逗号分隔，值中保留"0，Feather=30"且无法转数值，为字符串
        assert isinstance(result["Wipe Angle"], str)
        assert result["Wipe Angle"] == "0，Feather=30"

    def test_negative_integer(self) -> None:
        """负整数解析。"""
        result = TransitionAdapter._parse_params("Offset=-45")
        assert result == {"Offset": -45}
        assert isinstance(result["Offset"], int)

    def test_negative_float(self) -> None:
        """负浮点数解析。"""
        result = TransitionAdapter._parse_params("Scale=-0.5")
        assert result == {"Scale": -0.5}
        assert isinstance(result["Scale"], float)

    def test_value_with_equals_sign(self) -> None:
        """值中含有等号：split 仅切一次，保留值中等号。"""
        result = TransitionAdapter._parse_params("expr=a=b")
        assert result == {"expr": "a=b"}

    def test_key_and_value_stripped(self) -> None:
        """key / value 首尾空格被清理。"""
        result = TransitionAdapter._parse_params("  Wipe Angle  =  90  ,  Feather = 15 ")
        assert result == {"Wipe Angle": 90, "Feather": 15}


# =========================================================================
#  场景 5：extract_from_blocks 完整表格解析（非精确列表头）
# =========================================================================
class TestExtractFromBlocksSubstringHeaders:
    """用非精确匹配的"转场分类"/"AE对应效果名"等表头构造 TABLE 块做回归。"""

    def test_non_exact_zhuanchang_fenlei_and_ae_duiying(self, adapter: TransitionAdapter) -> None:
        """核心回归：使用"转场分类" + "AE对应效果名" 表头能提取配方。"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 序号 | 转场分类 | AE对应效果名 | 参数 |\n"
                "|------|----------|--------------|------|\n"
                "| 1 | Linear Wipe | ADBE Linear Wipe | Wipe Angle=0, Feather=30 |\n"
                "| 2 | Fade | opacity | |\n"
                "| 3 | Card Flip | ADBE Card Wipe | |"
            ),
        )
        recipes = adapter.extract_from_blocks([table_block], source_file="test.md")
        assert len(recipes) == 3
        assert recipes[0].transition_type == "linear_wipe"
        assert recipes[0].display_name == ""
        assert recipes[0].effect_match == "ADBE Linear Wipe"
        assert recipes[0].params == {"Wipe Angle": 0, "Feather": 30}
        assert recipes[0].source_file == "test.md"
        assert recipes[1].transition_type == "fade"
        assert recipes[1].effect_match == "opacity"
        assert recipes[2].transition_type == "card_flip"

    def test_non_exact_changjian_zhuanchang_and_ae_yuansheng(self, adapter: TransitionAdapter) -> None:
        """宽松匹配列："常见转场" + "AE原生效果"。"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 常见转场 | AE原生效果 |\n"
                "|----------|------------|\n"
                "| 线性 擦除 | ADBE Linear Wipe |\n"
                "| Radial-Wipe | ADBE Radial Wipe |"
            ),
        )
        recipes = adapter.extract_from_blocks([table_block])
        assert len(recipes) == 2
        # 空格 → 下划线 + 中文保留
        assert recipes[0].transition_type == "线性_擦除"
        assert recipes[0].effect_match == "ADBE Linear Wipe"
        # 连字符 → 下划线
        assert recipes[1].transition_type == "radial_wipe"
        assert recipes[1].effect_match == "ADBE Radial Wipe"

    def test_loose_changyong_zhuanchang_and_ae_mingcheng(self, adapter: TransitionAdapter) -> None:
        """宽松匹配："常用转场" + "AE效果名称"。"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 常用转场 | 显示名 | AE效果名称 |\n"
                "|----------|--------|------------|\n"
                "| fade | 淡入淡出 | opacity |"
            ),
        )
        recipes = adapter.extract_from_blocks([table_block])
        assert len(recipes) == 1
        assert recipes[0].transition_type == "fade"
        assert recipes[0].display_name == "淡入淡出"
        assert recipes[0].effect_match == "opacity"

    def test_only_type_col_without_effect_col_returns_empty(self, adapter: TransitionAdapter) -> None:
        """只有类型列，没有效果列 → recipes 为空。"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 转场分类 | 说明 |\n"
                "|----------|------|\n"
                "| Linear Wipe | 线性擦除效果 |\n"
                "| Fade | 淡入淡出 |"
            ),
        )
        recipes = adapter.extract_from_blocks([table_block])
        assert recipes == []

    def test_only_effect_col_without_type_col_returns_empty(self, adapter: TransitionAdapter) -> None:
        """只有效果列，没有类型列 → recipes 为空。"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 名称 | AE效果名 |\n"
                "|------|----------|\n"
                "| 擦除 | ADBE Linear Wipe |"
            ),
        )
        recipes = adapter.extract_from_blocks([table_block])
        assert recipes == []

    def test_skip_zhuanchang_miaoshu_as_type_col(self, adapter: TransitionAdapter) -> None:
        """表格中只有"转场描述"和"AE效果名" → "转场描述"被排除，无type_col → 空。"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 转场描述 | AE效果名 |\n"
                "|----------|----------|\n"
                "| 从左到右擦除 | ADBE Linear Wipe |"
            ),
        )
        recipes = adapter.extract_from_blocks([table_block])
        assert recipes == []

    def test_skip_ae_script_column(self, adapter: TransitionAdapter) -> None:
        """表格只有"转场"和"AE实现脚本"列 → AE列被排除，无effect_col → 空。"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 转场 | AE实现脚本 |\n"
                "|------|------------|\n"
                "| Wipe | some.jsx |"
            ),
        )
        recipes = adapter.extract_from_blocks([table_block])
        assert recipes == []

    def test_empty_row_transition_type_skipped(self, adapter: TransitionAdapter) -> None:
        """数据行中类型列为空 → 跳过该行。"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 转场分类 | AE对应效果名 |\n"
                "|----------|--------------|\n"
                "| Linear Wipe | ADBE Linear Wipe |\n"
                "|  | ADBE Radial Wipe |\n"
                "| Fade | opacity |"
            ),
        )
        recipes = adapter.extract_from_blocks([table_block])
        # 中间那行类型为空被跳过，共提取 2 条
        assert len(recipes) == 2
        assert recipes[0].transition_type == "linear_wipe"
        assert recipes[1].transition_type == "fade"

    def test_mixed_blocks_non_table_ignored(self, adapter: TransitionAdapter) -> None:
        """混合块中仅 TABLE 被处理。"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="转场清单", level=2),
            MdBlock(block_type=BlockType.PARAGRAPH, content="以下是常用转场"),
            MdBlock(
                block_type=BlockType.TABLE,
                content=(
                    "| 转场效果类型 | AE原子方案 |\n"
                    "|--------------|------------|\n"
                    "| Dissolve | ADBE Dissolve |"
                ),
            ),
            MdBlock(block_type=BlockType.LIST, content="- 其他说明"),
        ]
        recipes = adapter.extract_from_blocks(blocks, source_file="mixed.md")
        assert len(recipes) == 1
        assert recipes[0].transition_type == "dissolve"
        assert recipes[0].effect_match == "ADBE Dissolve"
        assert recipes[0].source_file == "mixed.md"


# =========================================================================
#  场景 6：extract_from_text_blocks KV 解析
# =========================================================================
class TestExtractFromTextBlocksKV:
    """KV_LINE_RE 各种边界：粗体/非粗体 key、display_name 缺失等。"""

    def test_bold_key_with_display_and_effect(self, adapter: TransitionAdapter) -> None:
        """粗体 key："**linear_wipe**: display_name=线性擦除, effect=ADBE Linear Wipe"。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content="- **linear_wipe**: display_name=线性擦除, effect=ADBE Linear Wipe",
        )
        recipes = adapter.extract_from_text_blocks([block], source_file="kv.md")
        assert len(recipes) == 1
        assert recipes[0].transition_type == "linear_wipe"
        assert recipes[0].display_name == "线性擦除"
        assert recipes[0].effect_match == "ADBE"
        assert recipes[0].source_file == "kv.md"

    def test_non_bold_key_with_display_and_effect(self, adapter: TransitionAdapter) -> None:
        """非粗体 key："linear_wipe: display_name=线性擦除, effect=ADBE Linear Wipe"。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content="linear_wipe: display_name=线性擦除, effect=ADBE Linear Wipe",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        assert recipes[0].transition_type == "linear_wipe"
        assert recipes[0].display_name == "线性擦除"
        # effect=\S+ 只取到空格前
        assert recipes[0].effect_match == "ADBE"

    def test_no_display_name_only_effect(self, adapter: TransitionAdapter) -> None:
        """无 display_name，仅 effect："**fade**: effect=opacity" → display_name 为空。"""
        block = MdBlock(
            block_type=BlockType.LIST,
            content="- **fade**: effect=opacity",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        assert recipes[0].transition_type == "fade"
        assert recipes[0].display_name == ""
        assert recipes[0].effect_match == "opacity"

    def test_kv_line_no_list_prefix(self, adapter: TransitionAdapter) -> None:
        """无列表前缀的 PARAGRAPH KV 行。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content="**card_flip**: display_name=卡片翻转, effect=ADBE",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        assert recipes[0].transition_type == "card_flip"
        assert recipes[0].display_name == "卡片翻转"
        assert recipes[0].effect_match == "ADBE"

    def test_kv_line_with_asterisk_prefix(self, adapter: TransitionAdapter) -> None:
        """* 列表前缀（非 -）。"""
        block = MdBlock(
            block_type=BlockType.LIST,
            content="* **radial_wipe**: display_name=径向擦除, effect=ADBE",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        assert recipes[0].transition_type == "radial_wipe"
        assert recipes[0].display_name == "径向擦除"
        assert recipes[0].effect_match == "ADBE"

    def test_kv_line_colon_chinese(self, adapter: TransitionAdapter) -> None:
        """中文冒号作为分隔符。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content="**zoom_blur**：display_name=变焦模糊, effect=ADBE",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        assert recipes[0].transition_type == "zoom_blur"
        assert recipes[0].display_name == "变焦模糊"

    def test_kv_line_type_camelcase_to_snake(self, adapter: TransitionAdapter) -> None:
        """KV key 为 CamelCase → 转 snake_case。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content="- LinearWipe: display_name=线性擦除, effect=ADBE",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        assert recipes[0].transition_type == "linear_wipe"

    def test_kv_line_type_with_space(self, adapter: TransitionAdapter) -> None:
        """KV key 含空格 → 转下划线。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content="- **Linear Wipe**: display_name=线性擦除, effect=ADBE",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        assert recipes[0].transition_type == "linear_wipe"

    def test_kv_line_no_effect_match_empty(self, adapter: TransitionAdapter) -> None:
        """存在 display_name，但无 effect= → effect_match 为空。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content="- **some**: display_name=某物",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        assert recipes[0].transition_type == "some"
        assert recipes[0].display_name == "某物"
        assert recipes[0].effect_match == ""

    def test_kv_display_name_with_chinese_comma(self, adapter: TransitionAdapter) -> None:
        """display_name= 正则使用 [^,，]+ 支持中文逗号停止。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content="- **wipe**: display_name=线性擦除，支持角度, effect=ADBE",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        # 中文逗号应作为 display_name 结束符，display_name 应停在"线性擦除"
        assert recipes[0].display_name == "线性擦除"
        assert recipes[0].effect_match == "ADBE"

    def test_multiline_kv_paragraph(self, adapter: TransitionAdapter) -> None:
        """段落内多行 KV，每行独立匹配。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content=(
                "- **linear_wipe**: display_name=线性擦除, effect=ADBE\n"
                "- **fade**: display_name=淡入淡出, effect=opacity\n"
                "- **card_flip**: display_name=卡片翻转, effect=Card"
            ),
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 3
        assert recipes[0].transition_type == "linear_wipe"
        assert recipes[1].transition_type == "fade"
        assert recipes[2].transition_type == "card_flip"

    def test_non_paragraph_and_non_list_ignored(self, adapter: TransitionAdapter) -> None:
        """非 PARAGRAPH / LIST 类型块被忽略。"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="**a**: effect=b", level=2),
            MdBlock(block_type=BlockType.CODE_BLOCK, content="**x**: effect=y"),
            MdBlock(block_type=BlockType.TABLE, content="|c|d|\n|-|-|\n|e|f|"),
        ]
        recipes = adapter.extract_from_text_blocks(blocks)
        assert recipes == []

    def test_kv_line_with_spaces_around_equals(self, adapter: TransitionAdapter) -> None:
        """等号前后空格不影响解析。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content="- **wipe**: display_name = 线性擦除, effect = ADBE",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        assert recipes[0].display_name == "线性擦除"
        assert recipes[0].effect_match == "ADBE"

    def test_kv_line_with_single_star_bold(self, adapter: TransitionAdapter) -> None:
        """单星号粗体 *key*。"""
        block = MdBlock(
            block_type=BlockType.PARAGRAPH,
            content="- *dissolve*: display_name=溶解, effect=ADBE",
        )
        recipes = adapter.extract_from_text_blocks([block])
        assert len(recipes) == 1
        assert recipes[0].transition_type == "dissolve"
        assert recipes[0].display_name == "溶解"
