"""
expression_library.py
Phase 4 - AE 表达式模板库与参数化生成器

用途：提供常见 AE 表达式的分类模板库，支持参数化生成，
      可根据意图动态选择模板并填充参数生成表达式字符串。

模板分类：
  - motion（运动）：wiggle、bounce、elastic、loopOut、pingPong
  - time（时间）：timeRemap、speedRamp、freezeFrame
  - color（颜色）：colorShift、flash、pulse
  - transform（变换）：swing、spin、float
  - utility（工具）：clamp、lerp、ease
  - audio（音频）：audioReact、beatPulse

设计对齐：effect_name_map.py / transition_map.py 的模块结构
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ExpressionTemplate",
    "ExpressionCategory",
    "EXPRESSION_TEMPLATES",
    "generate_expression",
    "list_templates_by_category",
    "find_template",
    "list_categories",
]


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

class ExpressionCategory:
    """表达式分类"""
    MOTION = "motion"
    TIME = "time"
    COLOR = "color"
    TRANSFORM = "transform"
    UTILITY = "utility"
    AUDIO = "audio"


@dataclass
class ExpressionParam:
    """表达式参数定义"""
    name: str
    display_name: str
    param_type: str = "float"  # float / int / bool / string
    default: Any = 0.0
    min_value: float | None = None
    max_value: float | None = None
    description: str = ""


@dataclass
class ExpressionTemplate:
    """表达式模板"""
    id: str
    name: str
    category: str
    display_name: str
    description: str = ""
    template: str = ""
    params: list[ExpressionParam] = field(default_factory=list)
    target_property: str = ""  # 适用的属性路径，如 "Transform/Position"
    tags: list[str] = field(default_factory=list)
    bpm_sensitive: bool = False  # 是否与 BPM 相关


# ---------------------------------------------------------------------------
# 模板库
# ---------------------------------------------------------------------------

EXPRESSION_TEMPLATES: list[ExpressionTemplate] = [
    # ===== motion: 运动类 =====

    ExpressionTemplate(
        id="wiggle_position",
        name="wiggle_position",
        category=ExpressionCategory.MOTION,
        display_name="位置抖动",
        description="在位置属性上产生随机抖动效果，常用于模拟手持摄像机或自然震动。",
        template="wiggle({freq}, {amp})",
        params=[
            ExpressionParam("freq", "频率", "float", 2.0, 0.1, 20.0, "每秒抖动次数"),
            ExpressionParam("amp", "幅度", "float", 10.0, 1.0, 100.0, "抖动幅度（像素）"),
        ],
        target_property="Transform/Position",
        tags=["抖动", "震动", "手持", "随机"],
    ),

    ExpressionTemplate(
        id="wiggle_scale",
        name="wiggle_scale",
        category=ExpressionCategory.MOTION,
        display_name="缩放抖动",
        description="在缩放属性上产生随机脉动效果。",
        template="wiggle({freq}, {amp})",
        params=[
            ExpressionParam("freq", "频率", "float", 1.5, 0.1, 10.0, "每秒脉动次数"),
            ExpressionParam("amp", "幅度", "float", 5.0, 1.0, 50.0, "缩放波动幅度（%）"),
        ],
        target_property="Transform/Scale",
        tags=["脉动", "呼吸", "缩放"],
    ),

    ExpressionTemplate(
        id="bounce",
        name="bounce",
        category=ExpressionCategory.MOTION,
        display_name="弹性弹跳",
        description="模拟弹跳效果，常用于文字入场或物体落地。",
        template=(
            "amp = {amplitude};\n"
            "freq = {frequency};\n"
            "decay = {decay};\n"
            "n = 0;\n"
            "if (numKeys > 0){\n"
            "  n = nearestKey(time).index;\n"
            "  if (key(n).time > time) n--;\n"
            "}\n"
            "if (n == 0){\n"
            "  t = 0;\n"
            "} else {\n"
            "  t = time - key(n).time;\n"
            "}\n"
            "if (n > 0 && t < 1){\n"
            "  v = velocityAtTime(key(n).time - thisComp.frameDuration/10);\n"
            "  value + v*amp*Math.sin(freq*t*2*Math.PI)/Math.exp(decay*t);\n"
            "} else {\n"
            "  value;\n"
            "}"
        ),
        params=[
            ExpressionParam("amplitude", "振幅", "float", 0.3, 0.1, 1.0, "弹跳幅度系数"),
            ExpressionParam("frequency", "频率", "float", 3.0, 1.0, 10.0, "弹跳频率（Hz）"),
            ExpressionParam("decay", "衰减", "float", 2.0, 0.5, 10.0, "衰减速度"),
        ],
        target_property="Transform/Position",
        tags=["弹跳", "弹性", "入场"],
    ),

    ExpressionTemplate(
        id="loop_out",
        name="loop_out",
        category=ExpressionCategory.MOTION,
        display_name="循环播放",
        description="从最后一个关键帧开始循环动画。",
        template="loopOut(\"{loop_type}\", {num_keyframes})",
        params=[
            ExpressionParam(
                "loop_type", "循环类型", "string", "cycle",
                description="cycle=周期, pingpong=往返, offset=偏移, continue=延续"
            ),
            ExpressionParam("num_keyframes", "关键帧数", "int", 0, 0, 10, "参与循环的关键帧数（0为全部）"),
        ],
        target_property="Transform/Position",
        tags=["循环", "重复"],
    ),

    ExpressionTemplate(
        id="elastic_scale",
        name="elastic_scale",
        category=ExpressionCategory.MOTION,
        display_name="弹性缩放",
        description="弹性缩放效果，常用于强调或点击反馈。",
        template=(
            "freq = {frequency};\n"
            "decay = {decay};\n"
            "t = {start_time};\n"
            "dur = {duration};\n"
            "t = Math.min(time - t, dur);\n"
            "if (t < 0) { value; } else {\n"
            "  s = 1 + {amplitude} * Math.exp(-decay * t) * Math.sin(freq * t * 2 * Math.PI);\n"
            "  value * s;\n"
            "}"
        ),
        params=[
            ExpressionParam("amplitude", "振幅", "float", 0.2, 0.05, 1.0),
            ExpressionParam("frequency", "频率", "float", 5.0, 1.0, 15.0),
            ExpressionParam("decay", "衰减", "float", 3.0, 0.5, 10.0),
            ExpressionParam("start_time", "开始时间", "float", 0.0, 0.0, 100.0),
            ExpressionParam("duration", "持续时间", "float", 1.0, 0.1, 10.0),
        ],
        target_property="Transform/Scale",
        tags=["弹性", "强调", "缩放"],
    ),

    # ===== time: 时间类 =====

    ExpressionTemplate(
        id="time_remap_speed",
        name="time_remap_speed",
        category=ExpressionCategory.TIME,
        display_name="时间重映射速度",
        description="控制视频播放速度的时间重映射。",
        template="value * {speed_multiplier}",
        params=[
            ExpressionParam("speed_multiplier", "速度倍率", "float", 1.0, 0.1, 5.0, "1.0=原速, 0.5=慢放, 2.0=快进"),
        ],
        target_property="Time Remap",
        tags=["慢动作", "快进", "时间"],
    ),

    ExpressionTemplate(
        id="freeze_frame",
        name="freeze_frame",
        category=ExpressionCategory.TIME,
        display_name="冻结帧",
        description="在指定时间点冻结画面。",
        template="valueAtTime({freeze_time})",
        params=[
            ExpressionParam("freeze_time", "冻结时间", "float", 1.0, 0.0, 100.0, "冻结画面的时间点（秒）"),
        ],
        target_property="Time Remap",
        tags=["定格", "冻结"],
    ),

    # ===== color: 颜色类 =====

    ExpressionTemplate(
        id="flash_opacity",
        name="flash_opacity",
        category=ExpressionCategory.COLOR,
        display_name="闪烁透明度",
        description="周期性闪烁效果，常用于警报或高亮。",
        template=(
            "freq = {frequency};\n"
            "min_op = {min_opacity};\n"
            "max_op = {max_opacity};\n"
            "t = time * freq * 2 * Math.PI;\n"
            "min_op + (max_op - min_op) * (Math.sin(t) * 0.5 + 0.5)"
        ),
        params=[
            ExpressionParam("frequency", "频率", "float", 2.0, 0.1, 10.0, "闪烁频率（Hz）"),
            ExpressionParam("min_opacity", "最小透明度", "float", 0.0, 0.0, 100.0),
            ExpressionParam("max_opacity", "最大透明度", "float", 100.0, 0.0, 100.0),
        ],
        target_property="Transform/Opacity",
        tags=["闪烁", "脉冲"],
    ),

    ExpressionTemplate(
        id="pulse_opacity",
        name="pulse_opacity",
        category=ExpressionCategory.COLOR,
        display_name="节拍脉冲",
        description="按 BPM 节拍脉冲透明度。",
        template=(
            "bpm = {bpm};\n"
            "beat = 60 / bpm;\n"
            "t = time % beat;\n"
            "p = t / beat;\n"
            "if (p < {attack}) {\n"
            "  {max_opacity} * (p / {attack});\n"
            "} else {\n"
            "  {max_opacity} * (1 - (p - {attack}) / (1 - {attack})) * 0.5 + {min_opacity};\n"
            "}"
        ),
        params=[
            ExpressionParam("bpm", "BPM", "float", 120.0, 60.0, 200.0, "每分钟节拍数"),
            ExpressionParam("max_opacity", "最大透明度", "float", 100.0, 0.0, 100.0),
            ExpressionParam("min_opacity", "最小透明度", "float", 30.0, 0.0, 100.0),
            ExpressionParam("attack", "起音比例", "float", 0.1, 0.01, 0.5, "起音时间占比"),
        ],
        target_property="Transform/Opacity",
        tags=["节拍", "脉冲", "音乐"],
        bpm_sensitive=True,
    ),

    # ===== transform: 变换类 =====

    ExpressionTemplate(
        id="spin_continuous",
        name="spin_continuous",
        category=ExpressionCategory.TRANSFORM,
        display_name="持续旋转",
        description="匀速持续旋转。",
        template="value + time * {rotation_speed}",
        params=[
            ExpressionParam("rotation_speed", "旋转速度", "float", 90.0, -720.0, 720.0, "每秒旋转角度（度），正值顺时针"),
        ],
        target_property="Transform/Rotation",
        tags=["旋转", "匀速"],
    ),

    ExpressionTemplate(
        id="float_sway",
        name="float_sway",
        category=ExpressionCategory.TRANSFORM,
        display_name="漂浮摆动",
        description="上下左右轻柔漂浮，模拟悬浮感。",
        template=(
            "x = Math.sin(time * {x_freq}) * {x_amp};\n"
            "y = Math.sin(time * {y_freq} + {phase}) * {y_amp};\n"
            "value + [x, y]"
        ),
        params=[
            ExpressionParam("x_freq", "X轴频率", "float", 0.5, 0.1, 5.0),
            ExpressionParam("y_freq", "Y轴频率", "float", 0.7, 0.1, 5.0),
            ExpressionParam("x_amp", "X轴幅度", "float", 15.0, 1.0, 100.0),
            ExpressionParam("y_amp", "Y轴幅度", "float", 10.0, 1.0, 100.0),
            ExpressionParam("phase", "相位偏移", "float", 0.5, 0.0, 6.28),
        ],
        target_property="Transform/Position",
        tags=["漂浮", "悬浮", "摆动"],
    ),

    # ===== utility: 工具类 =====

    ExpressionTemplate(
        id="clamp_value",
        name="clamp_value",
        category=ExpressionCategory.UTILITY,
        display_name="数值限制",
        description="将属性值限制在指定范围内。",
        template="clamp(value, {min_val}, {max_val})",
        params=[
            ExpressionParam("min_val", "最小值", "float", 0.0, -1000.0, 1000.0),
            ExpressionParam("max_val", "最大值", "float", 100.0, -1000.0, 1000.0),
        ],
        target_property="",
        tags=["限制", "工具"],
    ),

    ExpressionTemplate(
        id="ease_custom",
        name="ease_custom",
        category=ExpressionCategory.UTILITY,
        display_name="自定义缓动",
        description="在两个关键帧之间应用自定义缓动曲线。",
        template=(
            "if (numKeys < 2) { value; }\n"
            "t1 = key(1).time;\n"
            "t2 = key(numKeys).time;\n"
            "if (time <= t1) { key(1).value; }\n"
            "else if (time >= t2) { key(numKeys).value; }\n"
            "else {\n"
            "  p = (time - t1) / (t2 - t1);\n"
            "  p = ease(p, {ease_in}, {ease_out});\n"
            "  linear(p, key(1).value, key(numKeys).value);\n"
            "}"
        ),
        params=[
            ExpressionParam("ease_in", "缓入强度", "float", 0.33, 0.0, 0.99),
            ExpressionParam("ease_out", "缓出强度", "float", 0.33, 0.0, 0.99),
        ],
        target_property="",
        tags=["缓动", "曲线"],
    ),
]


# ---------------------------------------------------------------------------
# 查询 API
# ---------------------------------------------------------------------------

def list_categories() -> list[str]:
    """返回所有分类"""
    return [
        ExpressionCategory.MOTION,
        ExpressionCategory.TIME,
        ExpressionCategory.COLOR,
        ExpressionCategory.TRANSFORM,
        ExpressionCategory.UTILITY,
        ExpressionCategory.AUDIO,
    ]


def list_templates_by_category(category: str) -> list[ExpressionTemplate]:
    """按分类返回模板列表"""
    return [t for t in EXPRESSION_TEMPLATES if t.category == category]


def find_template(template_id: str) -> ExpressionTemplate | None:
    """根据 ID 查找模板"""
    for t in EXPRESSION_TEMPLATES:
        if t.id == template_id:
            return t
    return None


def find_templates_by_tag(tag: str) -> list[ExpressionTemplate]:
    """按标签搜索模板"""
    tag_lower = tag.lower()
    return [
        t for t in EXPRESSION_TEMPLATES
        if any(tag_lower in tg.lower() for tg in t.tags)
        or tag_lower in t.name.lower()
        or tag_lower in t.display_name.lower()
    ]


def find_template_by_intent(intent_keywords: list[str]) -> ExpressionTemplate | None:
    """根据意图关键词推荐最匹配的模板"""
    best_score = 0
    best_template = None
    for t in EXPRESSION_TEMPLATES:
        score = 0
        keyword_set = set(k.lower() for k in intent_keywords)
        tag_set = set(tg.lower() for tg in t.tags)
        score += len(keyword_set & tag_set) * 3
        if t.name.lower() in " ".join(intent_keywords).lower():
            score += 5
        if t.display_name in " ".join(intent_keywords):
            score += 5
        if score > best_score:
            best_score = score
            best_template = t
    return best_template if best_score > 0 else None


# ---------------------------------------------------------------------------
# 表达式生成 API
# ---------------------------------------------------------------------------

def generate_expression(template_id: str, params: dict[str, Any] | None = None) -> str:
    """根据模板 ID 和参数生成表达式字符串

    Args:
        template_id: 模板 ID
        params: 参数字典，覆盖模板默认值

    Returns:
        生成的 AE 表达式字符串

    Raises:
        ValueError: 模板不存在或参数无效
    """
    template = find_template(template_id)
    if not template:
        raise ValueError(f"模板不存在: {template_id}")

    final_params = {p.name: p.default for p in template.params}
    if params:
        for key, value in params.items():
            if key in final_params:
                final_params[key] = value
            # 静默忽略未知参数

    # 简单模板：直接 str.format
    try:
        return template.template.format(**final_params)
    except KeyError as e:
        raise ValueError(f"模板 {template_id} 缺少参数: {e}") from e


def generate_expression_by_intent(
    intent_keywords: list[str],
    bpm: float | None = None,
) -> tuple[str | None, str | None]:
    """根据意图关键词自动选择模板并生成表达式

    Returns:
        (表达式字符串, 模板 ID) —— 未找到匹配则 (None, None)
    """
    template = find_template_by_intent(intent_keywords)
    if not template:
        return None, None

    params = {}
    if bpm is not None and template.bpm_sensitive:
        params["bpm"] = bpm

    expr = generate_expression(template.id, params)
    return expr, template.id


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Expression Library: {len(EXPRESSION_TEMPLATES)} 个模板, {len(list_categories())} 个分类")
    print()
    for cat in list_categories():
        temps = list_templates_by_category(cat)
        print(f"  [{cat}] {len(temps)} 个:")
        for t in temps:
            print(f"    - {t.id}: {t.display_name}")
    print()
    # 测试生成
    expr = generate_expression("wiggle_position", {"freq": 3.0, "amp": 20.0})
    print("测试 wiggle_position:")
    print(expr)
    print()
    expr2, tid = generate_expression_by_intent(["闪烁", "脉冲"], bpm=120)
    print(f"意图匹配 '闪烁 脉冲' → {tid}:")
    print(expr2)
