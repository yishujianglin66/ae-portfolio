"""文字动画生成器 - 为 AE 合成添加各种文字动画效果

基于文字动画知识库，提供多种文字动画效果的 JSX 生成
"""
from typing import Any, Dict, List, Optional, Tuple


class TextAnimationGenerator:
    """文字动画生成器"""
    
    def __init__(self) -> None:
        self.width = 576
        self.height = 768
    
    def create_text_layer_jsx(self, text: str, position: tuple[float, float],
                             font_size: int = 36, font_color: tuple[float, float, float] = (1, 1, 1),
                             stroke_color: tuple[float, float, float] | None = None,
                             stroke_width: float = 0,
                             font_name: str = "Source Han Sans SC",
                             justify: str = "center") -> str:
        """创建基础文字图层的 JSX 代码
        
        Args:
            text: 文字内容
            position: 位置 (x, y)
            font_size: 字号
            font_color: 字体颜色 (r, g, b) 0-1 范围
            stroke_color: 描边颜色
            stroke_width: 描边宽度
            font_name: 字体名
            justify: 对齐方式 left/center/right
            
        Returns:
            JSX 代码字符串
        """
        justify_map = {
            "left": "ParagraphJustification.LEFT_JUSTIFY",
            "center": "ParagraphJustification.CENTER_JUSTIFY",
            "right": "ParagraphJustification.RIGHT_JUSTIFY",
        }
        justify_code = justify_map.get(justify, justify_map["center"])
        
        jsx = f'''
        var _textLayer = comp.layers.addText("{text}");
        _textLayer.name = "Text_{text[:10]}";
        try {{
            var _doc = _textLayer.property("ADBE Text Properties").property("ADBE Text Document");
            var _docVal = _doc.getValue();
            _docVal.fontSize = {font_size};
            _docVal.font = "{font_name}";
            _docVal.fillColor = [{font_color[0]}, {font_color[1]}, {font_color[2]}];
            _docVal.justification = {justify_code};
'''
        
        if stroke_color and stroke_width > 0:
            jsx += f'''
            _docVal.strokeColor = [{stroke_color[0]}, {stroke_color[1]}, {stroke_color[2]}];
            _docVal.strokeWidth = {stroke_width};
            _docVal.applyStroke = true;
'''
        
        jsx += f'''
            _doc.setValue(_docVal);
        }} catch(_eDoc) {{}}
        _textLayer.property("ADBE Transform Group").property("ADBE Position").setValue([{position[0]}, {position[1]}, 0]);
'''
        return jsx
    
    def fade_in_out(self, text: str, position: tuple[float, float],
                    start_time: float, duration: float,
                    font_size: int = 36, fade_time: float = 0.3,
                    **kwargs) -> str:
        """淡入淡出文字动画
        
        Args:
            text: 文字内容
            position: 位置
            start_time: 开始时间（秒）
            duration: 总时长（秒）
            font_size: 字号
            fade_time: 淡入淡出时间
            
        Returns:
            JSX 代码
        """
        base = self.create_text_layer_jsx(text, position, font_size, **kwargs)
        
        jsx = base + f'''
        _textLayer.startTime = {start_time};
        _textLayer.inPoint = {start_time};
        _textLayer.outPoint = {start_time + duration};
        
        var _op = _textLayer.property("ADBE Transform Group").property("ADBE Opacity");
        _op.setValueAtTime({start_time}, 0);
        _op.setValueAtTime({start_time + fade_time}, 100);
        _op.setValueAtTime({start_time + duration - fade_time}, 100);
        _op.setValueAtTime({start_time + duration}, 0);
'''
        return jsx
    
    def scale_pulse(self, text: str, position: tuple[float, float],
                    start_time: float, duration: float,
                    font_size: int = 48, pulse_period: float = 1.0,
                    pulse_scale: float = 1.1, **kwargs) -> str:
        """缩放脉冲文字动画（弹入 + 呼吸脉冲）
        
        Args:
            text: 文字内容
            position: 位置
            start_time: 开始时间
            duration: 总时长
            font_size: 字号
            pulse_period: 脉冲周期
            pulse_scale: 脉冲放大量级
            
        Returns:
            JSX 代码
        """
        base = self.create_text_layer_jsx(text, position, font_size, **kwargs)
        
        # 弹入关键帧
        bounce_jsx = ""
        bounce_times = [0, 0.1, 0.2, 0.3]
        bounce_values = [(0, 0), (115, 115), (95, 95), (100, 100)]
        
        pulse_jsx = ""
        # 计算脉冲关键帧（简化为几个关键帧）
        num_pulses = int(duration / pulse_period)
        pulse_t = 0.4  # 从弹入结束后开始
        
        jsx = base + f'''
        _textLayer.startTime = {start_time};
        _textLayer.inPoint = {start_time};
        _textLayer.outPoint = {start_time + duration};
        
        var _sc = _textLayer.property("ADBE Transform Group").property("ADBE Scale");
        // 弹入
        _sc.setValueAtTime({start_time + 0}, [0, 0]);
        _sc.setValueAtTime({start_time + 0.1}, [115, 115]);
        _sc.setValueAtTime({start_time + 0.2}, [95, 95]);
        _sc.setValueAtTime({start_time + 0.3}, [100, 100]);
'''

        # 脉冲关键帧
        t = 0.4
        pulse_count = 0
        while t < duration - 0.3 and pulse_count < 6:
            scale_val = 100 + (pulse_scale - 1) * 100
            jsx += f'''
        _sc.setValueAtTime({start_time + t}, [100, 100]);
        _sc.setValueAtTime({start_time + t + pulse_period/2}, [{scale_val}, {scale_val}]);
        _sc.setValueAtTime({start_time + t + pulse_period}, [100, 100]);
'''
            t += pulse_period
            pulse_count += 1
        
        # 淡出
        jsx += f'''
        var _op2 = _textLayer.property("ADBE Transform Group").property("ADBE Opacity");
        _op2.setValueAtTime({start_time}, 0);
        _op2.setValueAtTime({start_time + 0.1}, 100);
        _op2.setValueAtTime({start_time + duration - 0.2}, 100);
        _op2.setValueAtTime({start_time + duration}, 0);
'''
        
        return jsx
    
    def slide_from_direction(self, text: str, position: tuple[float, float],
                            start_time: float, duration: float,
                            direction: str = "bottom", distance: float = 100,
                            font_size: int = 32, fade_time: float = 0.3,
                            **kwargs) -> str:
        """从指定方向滑入文字
        
        Args:
            text: 文字内容
            position: 最终位置
            start_time: 开始时间
            duration: 总时长
            direction: 滑入方向 top/bottom/left/right
            distance: 滑动距离
            font_size: 字号
            fade_time: 淡入时间
            
        Returns:
            JSX 代码
        """
        x, y = position
        
        # 计算起始位置
        if direction == "top":
            start_pos = (x, y - distance)
        elif direction == "bottom":
            start_pos = (x, y + distance)
        elif direction == "left":
            start_pos = (x - distance, y)
        elif direction == "right":
            start_pos = (x + distance, y)
        else:
            start_pos = (x, y + distance)
        
        base = self.create_text_layer_jsx(text, position, font_size, **kwargs)
        
        jsx = base + f'''
        _textLayer.startTime = {start_time};
        _textLayer.inPoint = {start_time};
        _textLayer.outPoint = {start_time + duration};
        
        var _pos = _textLayer.property("ADBE Transform Group").property("ADBE Position");
        _pos.setValueAtTime({start_time}, [{start_pos[0]}, {start_pos[1]}, 0]);
        _pos.setValueAtTime({start_time + fade_time}, [{x}, {y}, 0]);
        _pos.setValueAtTime({start_time + duration - fade_time}, [{x}, {y}, 0]);
        _pos.setValueAtTime({start_time + duration}, [{start_pos[0]}, {start_pos[1]}, 0]);
        
        var _op3 = _textLayer.property("ADBE Transform Group").property("ADBE Opacity");
        _op3.setValueAtTime({start_time}, 0);
        _op3.setValueAtTime({start_time + fade_time}, 100);
        _op3.setValueAtTime({start_time + duration - fade_time}, 100);
        _op3.setValueAtTime({start_time + duration}, 0);
'''
        return jsx
    
    def per_character_fade(self, text: str, position: tuple[float, float],
                          start_time: float, duration: float,
                          font_size: int = 40, char_delay: float = 0.05,
                          **kwargs) -> str:
        """逐字淡入动画（使用 Text Animator）
        
        Args:
            text: 文字内容
            position: 位置
            start_time: 开始时间
            duration: 总时长
            font_size: 字号
            char_delay: 每个字的延迟时间
            
        Returns:
            JSX 代码
        """
        base = self.create_text_layer_jsx(text, position, font_size, **kwargs)
        
        total_anim = len(text) * char_delay
        
        jsx = base + f'''
        _textLayer.startTime = {start_time};
        _textLayer.inPoint = {start_time};
        _textLayer.outPoint = {start_time + duration};
        
        try {{
            var _textProps = _textLayer.property("ADBE Text Properties");
            var _animGroup = _textProps.addProperty("ADBE Text Animator");
            
            // 添加透明度动画
            var _animProps = _animGroup.addProperty("ADBE Text Property Group");
            _animProps.addProperty("ADBE Text Opacity").setValue(0);
            
            // 添加位置偏移（向上移动）
            _animProps.addProperty("ADBE Text Position").setValue([0, -20, 0]);
            
            // 范围选择器动画
            var _selector = _animGroup.property("ADBE Text Selectors").property("ADBE Text Selector 1");
            _selector.property("ADBE Text Selector Start").setValueAtTime({start_time}, 0);
            _selector.property("ADBE Text Selector Start").setValueAtTime({start_time + total_anim}, 100);
        }} catch(_eAnim) {{}}
        
        var _op4 = _textLayer.property("ADBE Transform Group").property("ADBE Opacity");
        _op4.setValueAtTime({start_time + total_anim}, 100);
        _op4.setValueAtTime({start_time + duration - 0.3}, 100);
        _op4.setValueAtTime({start_time + duration}, 0);
'''
        return jsx
    
    def add_stroke_animation(self, text_layer_var: str, start_time: float,
                            duration: float, stroke_end_val: float = 50) -> str:
        """添加描边动画（描边从无到有）- 预留接口
        
        Args:
            text_layer_var: 文字图层变量名
            start_time: 开始时间
            duration: 时长
            stroke_end_val: 最终描边宽度
            
        Returns:
            JSX 代码
        """
        return f'''
        // 描边动画（如需启用）
        // var _stroke = {text_layer_var}.property("ADBE Text Properties").property("ADBE Text Animators")...
'''


def generate_mv_texts(duration: float, bpm: float = 120) -> list[dict[str, Any]]:
    """生成 MV 风格的文字动画配置
    
    Args:
        duration: 视频总时长
        bpm: 音乐 BPM
        
    Returns:
        文字动画配置列表
    """
    texts = []
    
    beat_duration = 60.0 / bpm
    
    # 1. 开头大标题 - 第 0-3 秒
    texts.append({
        "type": "scale_pulse",
        "text": "一拳超人",
        "position": (288, 300),
        "start_time": 0.5,
        "duration": 3.0,
        "font_size": 64,
        "font_color": (1, 1, 1),
        "stroke_color": (0.8, 0.6, 0.2),
        "stroke_width": 2,
        "pulse_period": beat_duration * 2,
        "pulse_scale": 1.05,
    })
    
    # 2. 副标题 - 第 1-4 秒
    texts.append({
        "type": "fade",
        "text": "ONE PUNCH MAN",
        "position": (288, 370),
        "start_time": 1.2,
        "duration": 2.5,
        "font_size": 24,
        "font_color": (0.9, 0.9, 0.9),
    })
    
    # 3. 中间关键词 - 第 4-7 秒
    texts.append({
        "type": "slide",
        "text": "最强英雄",
        "position": (288, 380),
        "start_time": 4.0,
        "duration": 2.5,
        "font_size": 48,
        "font_color": (1, 0.95, 0.8),
        "direction": "bottom",
        "distance": 80,
    })
    
    # 4. 另一个关键词 - 第 5-8 秒
    texts.append({
        "type": "per_char",
        "text": "埼玉老师",
        "position": (288, 440),
        "start_time": 5.5,
        "duration": 3.0,
        "font_size": 36,
        "font_color": (1, 1, 1),
        "char_delay": 0.08,
    })
    
    # 5. 结尾文字 - 第 8-10 秒
    texts.append({
        "type": "fade",
        "text": "世界上没有一拳解决不了的事",
        "position": (288, 400),
        "start_time": 8.0,
        "duration": 1.8,
        "font_size": 28,
        "font_color": (1, 1, 1),
    })
    
    # 6. 底部小字 - 第 8.5-10 秒
    texts.append({
        "type": "slide",
        "text": "如果有，那就两拳",
        "position": (288, 450),
        "start_time": 8.7,
        "duration": 1.2,
        "font_size": 22,
        "font_color": (0.85, 0.85, 0.9),
        "direction": "top",
        "distance": 30,
    })
    
    return texts


def build_text_jsx(text_configs: list[dict[str, Any]], width: int = 576,
                   height: int = 768) -> str:
    """根据文字配置列表生成完整的 JSX 代码
    
    Args:
        text_configs: 文字配置列表
        width: 合成宽度
        height: 合成高度
        
    Returns:
        JSX 代码字符串
    """
    gen = TextAnimationGenerator()
    gen.width = width
    gen.height = height
    
    all_jsx = ""
    
    for i, cfg in enumerate(text_configs):
        anim_type = cfg.get("type", "fade")
        text = cfg.get("text", "")
        position = cfg.get("position", (width/2, height/2))
        start_time = cfg.get("start_time", 0)
        duration = cfg.get("duration", 2)
        font_size = cfg.get("font_size", 32)
        font_color = cfg.get("font_color", (1, 1, 1))
        stroke_color = cfg.get("stroke_color", None)
        stroke_width = cfg.get("stroke_width", 0)
        
        kwargs = {
            "font_color": font_color,
            "stroke_color": stroke_color,
            "stroke_width": stroke_width,
        }
        
        if anim_type == "fade":
            jsx = gen.fade_in_out(
                text=text,
                position=position,
                start_time=start_time,
                duration=duration,
                font_size=font_size,
                fade_time=cfg.get("fade_time", 0.3),
                **kwargs
            )
        elif anim_type == "scale_pulse":
            jsx = gen.scale_pulse(
                text=text,
                position=position,
                start_time=start_time,
                duration=duration,
                font_size=font_size,
                pulse_period=cfg.get("pulse_period", 1.0),
                pulse_scale=cfg.get("pulse_scale", 1.1),
                **kwargs
            )
        elif anim_type == "slide":
            jsx = gen.slide_from_direction(
                text=text,
                position=position,
                start_time=start_time,
                duration=duration,
                direction=cfg.get("direction", "bottom"),
                distance=cfg.get("distance", 100),
                font_size=font_size,
                fade_time=cfg.get("fade_time", 0.3),
                **kwargs
            )
        elif anim_type == "per_char":
            jsx = gen.per_character_fade(
                text=text,
                position=position,
                start_time=start_time,
                duration=duration,
                font_size=font_size,
                char_delay=cfg.get("char_delay", 0.05),
                **kwargs
            )
        else:
            jsx = gen.fade_in_out(
                text=text,
                position=position,
                start_time=start_time,
                duration=duration,
                font_size=font_size,
                **kwargs
            )
        
        # 给每个图层一个唯一的变量名
        jsx = jsx.replace("_textLayer", f"_textLayer{i}")
        jsx = jsx.replace("_doc", f"_doc{i}")
        jsx = jsx.replace("_docVal", f"_docVal{i}")
        jsx = jsx.replace("_op", f"_op{i}")
        jsx = jsx.replace("_sc", f"_sc{i}")
        jsx = jsx.replace("_pos", f"_pos{i}")
        jsx = jsx.replace("_textProps", f"_textProps{i}")
        jsx = jsx.replace("_animGroup", f"_animGroup{i}")
        jsx = jsx.replace("_animProps", f"_animProps{i}")
        jsx = jsx.replace("_selector", f"_selector{i}")
        jsx = jsx.replace("_eDoc", f"_eDoc{i}")
        jsx = jsx.replace("_eAnim", f"_eAnim{i}")
        
        all_jsx += jsx + "\n"
    
    return all_jsx


if __name__ == "__main__":
    # 测试
    texts = generate_mv_texts(10, 120)
    jsx = build_text_jsx(texts)
    print(f"生成 {len(texts)} 个文字动画")
    print(f"JSX 行数: {len(jsx.split(chr(10)))}")
    print("\n前 20 行 JSX:")
    for i, line in enumerate(jsx.split(chr(10))[:20], 1):
        print(f"{i:3d}: {line}")
