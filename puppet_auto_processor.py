#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
木偶风格化自动处理器 - 端到端自动识别与处理流程

自动完成以下流程:
1. MediaPipe 人物检测 → 获取 bbox、姿态数据、面部数据
2. PuppetStyleEngine 风格化 → 生成 AE 效果配置和关键帧
3. 输出 JSX 脚本 → 可直接在 AE 中执行
4. 可选：调用 AE 执行脚本

核心能力:
- 自动检测视频中的人物位置和姿态
- 根据检测结果生成针对性的木偶风格化效果
- 支持8种木偶风格预设
- 完整的错误处理和降级机制
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from mediapipe_integration import (
        MediaPipeIntegrator,
        MediaPipeConfig,
        MediaPipeResult,
    )
    _MEDIAPIPE_AVAILABLE = True
except ImportError:
    _MEDIAPIPE_AVAILABLE = False

try:
    from puppet_style_engine import (
        PuppetStyleEngine,
        PuppetStyleConfig,
        PuppetStyleResult,
    )
    _PUPPET_ENGINE_AVAILABLE = True
except ImportError:
    _PUPPET_ENGINE_AVAILABLE = False


class PuppetAutoProcessor:
    """木偶风格化自动处理器
    
    整合 MediaPipe 人物识别和 PuppetStyleEngine 风格化，
    提供端到端的自动处理能力。
    """
    
    def __init__(self, mediapipe_mode: str = "auto"):
        self.mediapipe_mode = mediapipe_mode
        self._mediapipe = None
        self._style_engine = None
        self._init_modules()
    
    def _init_modules(self):
        """初始化依赖模块"""
        if _MEDIAPIPE_AVAILABLE:
            config = MediaPipeConfig(
                mode=self.mediapipe_mode,
                detect_pose=True,
                detect_face=True,
                detect_hands=False,
                confidence_threshold=0.5,
                max_num_persons=1,
                sample_interval=5,
            )
            self._mediapipe = MediaPipeIntegrator(config)
        
        if _PUPPET_ENGINE_AVAILABLE:
            self._style_engine = PuppetStyleEngine()
    
    def is_mediapipe_available(self) -> bool:
        """检查 MediaPipe 是否可用"""
        return self._mediapipe is not None and self._mediapipe.is_available()
    
    def is_style_engine_available(self) -> bool:
        """检查风格引擎是否可用"""
        return self._style_engine is not None
    
    def get_available_styles(self) -> List[Dict[str, Any]]:
        """获取可用风格列表"""
        if not self._style_engine:
            return []
        return self._style_engine.get_available_styles()
    
    def process_video(self, video_path: str, style_type: str = "wooden_puppet",
                      intensity: float = 1.0, enable_face_puppet: bool = True,
                      output_dir: Optional[str] = None) -> Dict[str, Any]:
        """处理视频，自动识别人物并生成木偶风格化效果
        
        Args:
            video_path: 输入视频路径
            style_type: 木偶风格类型
            intensity: 风格强度
            enable_face_puppet: 是否启用面部木偶化
            output_dir: 输出目录（可选）
            
        Returns:
            处理结果字典，包含检测数据、风格化结果、输出文件路径
        """
        start_time = time.time()
        
        result = {
            "success": False,
            "video_path": video_path,
            "style_type": style_type,
            "intensity": intensity,
            "enable_face_puppet": enable_face_puppet,
            "mediapipe_mode": "simulate",
            "detection": None,
            "style_result": None,
            "output_files": {},
            "error": "",
        }
        
        if not os.path.exists(video_path):
            result["error"] = f"文件不存在: {video_path}"
            return result
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = str(PROJECT_ROOT / "output" / "puppet_auto")
            os.makedirs(output_dir, exist_ok=True)
        
        result["output_dir"] = output_dir
        
        # Step 1: MediaPipe 人物检测
        detection_data = self._detect_person(video_path)
        result["detection"] = detection_data
        
        if not detection_data.get("success"):
            print(f"  ⚠️ 人物检测失败，使用默认参数")
            bbox = None
            joint_data = []
            face_data = None
            width = 1920
            height = 1080
            duration = 5.0
        else:
            bbox = detection_data.get("bbox")
            joint_data = detection_data.get("joint_data", [])
            face_data = detection_data.get("face_data")
            width = detection_data.get("width", 1920)
            height = detection_data.get("height", 1080)
            duration = detection_data.get("duration", 5.0)
            result["mediapipe_mode"] = detection_data.get("mode", "simulate")
        
        # Step 2: 生成风格化配置
        config = PuppetStyleConfig(
            style_type=style_type,
            intensity=intensity,
            comp_width=width,
            comp_height=height,
            bbox=bbox,
            enable_face_puppet=enable_face_puppet,
            face_data=face_data,
            joint_data=joint_data,
        )
        
        # Step 3: 风格化生成
        style_result = self._generate_style(config, duration=duration)
        result["style_result"] = style_result
        
        if style_result is None:
            result["error"] = "风格化生成失败"
            return result
        
        # Step 4: 生成 JSX 脚本
        jsx_path = os.path.join(output_dir, f"puppet_{style_type}.jsx")
        jsx_content = self._generate_jsx(
            video_path=video_path,
            style_type=style_type,
            style_result=style_result,
            width=width,
            height=height,
            duration=duration,
            bbox=bbox,
        )
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx_content)
        result["output_files"]["jsx_script"] = jsx_path
        
        # Step 5: 保存检测结果
        detection_path = os.path.join(output_dir, "detection_result.json")
        if detection_data:
            with open(detection_path, "w", encoding="utf-8") as f:
                json.dump(detection_data, f, indent=2, ensure_ascii=False, default=str)
            result["output_files"]["detection_result"] = detection_path
        
        # Step 6: 保存风格化配置
        config_path = os.path.join(output_dir, "style_config.json")
        config_dict = {
            "style_type": config.style_type,
            "intensity": config.intensity,
            "comp_width": config.comp_width,
            "comp_height": config.comp_height,
            "bbox": config.bbox,
            "enable_face_puppet": config.enable_face_puppet,
            "face_data_available": config.face_data is not None,
            "joint_data_frames": len(config.joint_data) if config.joint_data else 0,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        result["output_files"]["style_config"] = config_path
        
        # Step 7: 保存风格化结果摘要
        summary_path = os.path.join(output_dir, "style_summary.json")
        summary = {
            "effects_count": len(style_result.effects),
            "keyframes_count": len(style_result.keyframes),
            "layers_count": len(style_result.layers),
            "expressions_count": len(style_result.expressions),
            "adjustment_layers_count": len(style_result.adjustment_layers),
            "face_effects_count": len(style_result.face_effects),
            "face_expressions_count": len(style_result.face_expressions),
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        result["output_files"]["style_summary"] = summary_path
        
        result["success"] = True
        result["duration"] = round(time.time() - start_time, 2)
        
        return result
    
    def _detect_person(self, video_path: str) -> Dict[str, Any]:
        """使用 MediaPipe 检测人物
        
        Args:
            video_path: 视频路径
            
        Returns:
            检测结果字典
        """
        if not self._mediapipe:
            return {
                "success": False,
                "error": "MediaPipe 不可用",
                "mode": "simulate",
            }
        
        result = self._mediapipe.process_video(video_path)
        
        if not result.success:
            return {
                "success": False,
                "error": result.error,
                "mode": result.mode,
            }
        
        puppet_format = self._mediapipe.convert_to_puppet_format(result)
        
        return {
            "success": True,
            "mode": result.mode,
            "width": result.width,
            "height": result.height,
            "fps": result.fps,
            "duration": result.duration,
            "bbox": puppet_format.get("bbox"),
            "joint_data": puppet_format.get("joint_data", []),
            "face_data": puppet_format.get("face_data"),
            "detection_count": len(result.detections),
        }
    
    def _generate_style(self, config: PuppetStyleConfig,
                        duration: float = 5.0) -> Optional[PuppetStyleResult]:
        """生成风格化效果
        
        Args:
            config: 风格配置
            duration: 持续时间
            
        Returns:
            风格化结果或 None
        """
        if not self._style_engine:
            return None
        
        try:
            result = self._style_engine.generate_style(
                config,
                layer_name="PuppetLayer",
                duration=duration,
            )
            return result
        except Exception as e:
            return None
    
    def _generate_jsx(self, video_path: str, style_type: str,
                      style_result: PuppetStyleResult, width: int, height: int,
                      duration: float, bbox: Optional[Dict[str, float]]) -> str:
        """生成 AE JSX 脚本
        
        Args:
            video_path: 输入视频路径
            style_type: 风格类型
            style_result: 风格化结果
            width: 合成宽度
            height: 合成高度
            duration: 持续时间
            bbox: 人物边界框
            
        Returns:
            JSX 脚本内容
        """
        video_path_js = video_path.replace("\\", "/")
        
        effects_js = self._generate_effects_js(style_result.effects, width, height)
        
        layers_js = self._generate_layers_js(style_result.layers, width, height, duration)
        
        keyframes_js = self._generate_keyframes_js(style_result.keyframes)
        
        expressions_js = self._generate_expressions_js(style_result.expressions)
        
        bbox_js = self._generate_bbox_js(bbox, width, height)
        
        keyframes_count = len(style_result.keyframes)
        expressions_count = len(style_result.expressions)
        
        bbox_comment = ""
        if bbox:
            bbox_comment = f"// 人物检测: x={bbox['x']:.0f}, y={bbox['y']:.0f}, w={bbox['width']:.0f}, h={bbox['height']:.0f}"
        
        jsx = f"""// 木偶风格化 AE 合成脚本 - 自动生成
// 风格: {style_type}
// 效果数: {len(style_result.effects)} | 关键帧数: {keyframes_count} | 表达式数: {expressions_count}
{bbox_comment}
#target aftereffects

(function() {{
    app.beginUndoGroup("Puppet Auto Style - {style_type}");

    try {{
        var comp = app.project.items.addComp(
            "Puppet_{style_type}",
            {width}, {height}, 1.0, {duration}, 30
        );

        var footageFile = new File("{video_path_js}");
        var footageItem = null;
        var mainLayer = null;
        
        if (footageFile.exists) {{
            footageItem = app.project.importFile(new ImportOptions(footageFile));
            mainLayer = comp.layers.add(footageItem);
            mainLayer.name = "视频层";
        }} else {{
            mainLayer = comp.layers.addSolid(
                [0.3, 0.3, 0.4],
                "占位层",
                {width}, {height}, 1.0, {duration}
            );
        }}

        var adjLayer = comp.layers.addSolid(
            [1, 1, 1],
            "风格化调整层",
            {width}, {height}, 1.0, {duration}
        );
        adjLayer.adjustmentLayer = true;

{bbox_js}

{effects_js}

{layers_js}

{keyframes_js}

{expressions_js}

        app.endUndoGroup();
        return true;
    }} catch (e) {{
        app.endUndoGroup(false);
        return false;
    }}
}})();
"""
        return jsx
    
    def _generate_effects_js(self, effects: List[Dict[str, Any]],
                             width: int, height: int) -> str:
        """生成效果应用 JSX 代码"""
        js_lines = []
        
        ae_effect_map = {
            "ADBE_CC Toner": "_addCCToner",
            "ADBE_Lumetri_Color": "_addLumetriColor",
            "ADBE Fast Blur 2": "_addFastBlur",
            "ADBE_Brightness & Contrast 2": "_addBrightnessContrast",
            "ADBE_Color Balance 2": "_addColorBalance",
            "ADBE_Levels": "_addLevels",
            "ADBE_Curves": "_addCurves",
            "ADBE_Hue/Saturation": "_addHueSaturation",
            "ADBE_Gamma/Pedestal/Gain": "_addGammaPedestalGain",
            "ADBE_Fill": "_addFill",
            "ADBE_Stroke": "_addStroke",
            "ADBE_Circle": "_addCircle",
            "ADBE_Beam": "_addBeam",
            "ADBE_Linear Wipe": "_addLinearWipe",
            "ADBE_Gradient Wipe": "_addGradientWipe",
            "ADBE_Transform": "_addTransform",
            "ADBE_Corner Pin": "_addCornerPin",
            "ADBE_Opacity2": "_addOpacity",
            "ADBE_Sharpen": "_addSharpen",
            "ADBE_Gaussian Blur": "_addGaussianBlur",
            "ADBE_Median": "_addMedian",
            "ADBE_Mosaic": "_addMosaic",
            "ADBE_Noise": "_addNoise",
            "ADBE_Noise Alpha": "_addNoiseAlpha",
            "ADBE_Turbulent Displace": "_addTurbulentDisplace",
            "ADBE_Roughen Edges": "_addRoughenEdges",
            "ADBE_Strobe Light": "_addStrobeLight",
            "ADBE_Echo": "_addEcho",
            "ADBE_Posterize Time": "_addPosterizeTime",
            "ADBE_Color Offset": "_addColorOffset",
            "ADBE_Channel Mixer": "_addChannelMixer",
            "ADBE_Directional Blur": "_addDirectionalBlur",
            "ADBE_Motion Tile": "_addMotionTile",
            "ADBE_Spread": "_addSpread",
            "ADBE_Texturize": "_addTexturize",
            "ADBE_Vector Blur": "_addVectorBlur",
            "ADBE_Wave Warp": "_addWaveWarp",
            "ADBE_Puppet": "_addPuppetPin",
        }
        
        for i, eff in enumerate(effects[:20]):
            name = eff.get("displayName", eff.get("name", f"Effect_{i}"))
            match_name = eff.get("matchName", "")
            settings = eff.get("settings", {})
            
            if match_name in ae_effect_map:
                js_lines.append(f"        {ae_effect_map[match_name]}(adjLayer, {json.dumps(settings)});")
            elif match_name:
                js_lines.append(f"        adjLayer.property('Effects').addProperty('{match_name}');")
            else:
                js_lines.append(f"        // 效果: {name}")
        
        if js_lines:
            return "\n".join(js_lines) + "\n"
        
        return "        adjLayer.property('Effects').addProperty('ADBE_CC Toner');\n        adjLayer.property('Effects').addProperty('ADBE_Lumetri_Color');\n"
    
    def _generate_layers_js(self, layers: List[Dict[str, Any]],
                            width: int, height: int, duration: float) -> str:
        """生成图层创建 JSX 代码"""
        js_lines = []
        
        for i, layer in enumerate(layers[:10]):
            name = layer.get("name", f"Layer_{i}")
            ltype = layer.get("type", "solid")
            
            if ltype == "adjustment":
                color = layer.get("color", [1, 1, 1])
                js_lines.append(f"        var adj_{i} = comp.layers.addSolid(")
                js_lines.append(f"            {json.dumps(color)},")
                js_lines.append(f"            '{name}',")
                js_lines.append(f"            {width}, {height}, 1.0, {duration}")
                js_lines.append(f"        );")
                js_lines.append(f"        adj_{i}.adjustmentLayer = true;")
            elif ltype == "solid":
                color = layer.get("color", [0.5, 0.5, 0.5])
                js_lines.append(f"        var solid_{i} = comp.layers.addSolid(")
                js_lines.append(f"            {json.dumps(color)},")
                js_lines.append(f"            '{name}',")
                js_lines.append(f"            {width}, {height}, 1.0, {duration}")
                js_lines.append(f"        );")
        
        if js_lines:
            return "\n".join(js_lines) + "\n"
        
        return ""
    
    def _generate_keyframes_js(self, keyframes: List[Dict[str, Any]]) -> str:
        """生成关键帧设置 JSX 代码"""
        js_lines = []
        
        for i, kf in enumerate(keyframes[:30]):
            layer_name = kf.get("layer", "mainLayer")
            property = kf.get("property", "Transform.position")
            values = kf.get("values", [])
            
            if values:
                js_lines.append(f"        // 关键帧: {property}")
                for v in values[:10]:
                    time_val = v.get("time", 0)
                    value = v.get("value", [0, 0])
                    easing = v.get("easing", "linear")
                    js_lines.append(f"        {layer_name}.property('{property}').setValueAtTime({time_val}, {json.dumps(value)});")
        
        if js_lines:
            return "\n".join(js_lines) + "\n"
        
        return ""
    
    def _generate_expressions_js(self, expressions: List[Dict[str, Any]]) -> str:
        """生成表达式设置 JSX 代码"""
        js_lines = []
        
        for i, expr in enumerate(expressions[:10]):
            layer_name = expr.get("layer", "mainLayer")
            property = expr.get("property", "Transform.position")
            expression = expr.get("expression", "")
            
            if expression:
                safe_expr = expression.replace("\\", "\\\\").replace("'", "\\'")
                js_lines.append(f"        {layer_name}.property('{property}').expression = '{safe_expr}';")
        
        if js_lines:
            return "\n".join(js_lines) + "\n"
        
        return ""
    
    def _generate_bbox_js(self, bbox: Optional[Dict[str, float]],
                          width: int, height: int) -> str:
        """生成人物边界框相关 JSX 代码"""
        if not bbox:
            return ""
        
        x = bbox.get("x", 0)
        y = bbox.get("y", 0)
        w = bbox.get("width", 0)
        h = bbox.get("height", 0)
        
        return f"""        // 人物边界框 ({x:.0f}, {y:.0f}, {w:.0f}, {h:.0f})
        var bboxMarker = comp.layers.addSolid(
            [1, 0, 0, 0.3],
            "人物检测框",
            {w}, {h}, 1.0, 5
        );
        bboxMarker.property("Transform").property("Position").setValueAtTime(0, [{x + w/2}, {y + h/2}]);
"""


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="木偶风格化自动处理器")
    parser.add_argument(
        "--video", "-v",
        required=True,
        help="输入视频路径",
    )
    parser.add_argument(
        "--style", "-s",
        choices=["wooden_puppet", "ceramic_puppet", "cloth_puppet", "clay_puppet",
                 "metal_puppet", "stop_motion_basic", "marionette", "shadow_puppet"],
        default="wooden_puppet",
        help="木偶风格类型",
    )
    parser.add_argument(
        "--intensity", "-i",
        type=float,
        default=1.0,
        help="风格强度 (0.0-2.0)",
    )
    parser.add_argument(
        "--no-face",
        action="store_true",
        help="禁用面部木偶化",
    )
    parser.add_argument(
        "--output", "-o",
        help="输出目录",
    )
    parser.add_argument(
        "--list-styles",
        action="store_true",
        help="列出可用风格",
    )
    parser.add_argument(
        "--mediapipe-mode",
        choices=["auto", "real", "simulate"],
        default="auto",
        help="MediaPipe 运行模式",
    )
    
    args = parser.parse_args()
    
    processor = PuppetAutoProcessor(mediapipe_mode=args.mediapipe_mode)
    
    if args.list_styles:
        styles = processor.get_available_styles()
        print(f"可用风格 ({len(styles)} 种):")
        for style in styles:
            print(f"  - {style['name']}: {style['display_name']}")
            print(f"    描述: {style['description']}")
        return
    
    print("=" * 60)
    print("🎭 木偶风格化自动处理器")
    print("=" * 60)
    print(f"视频: {args.video}")
    print(f"风格: {args.style}")
    print(f"强度: {args.intensity}")
    print(f"面部木偶化: {'启用' if not args.no_face else '禁用'}")
    print(f"MediaPipe: {'可用' if processor.is_mediapipe_available() else '不可用'}")
    print(f"风格引擎: {'可用' if processor.is_style_engine_available() else '不可用'}")
    
    print("\n开始处理...")
    
    result = processor.process_video(
        video_path=args.video,
        style_type=args.style,
        intensity=args.intensity,
        enable_face_puppet=not args.no_face,
        output_dir=args.output,
    )
    
    if result["success"]:
        print(f"\n✅ 处理完成!")
        print(f"耗时: {result['duration']} 秒")
        print(f"MediaPipe 模式: {result['mediapipe_mode']}")
        
        print(f"\n输出文件:")
        for key, path in result["output_files"].items():
            size = os.path.getsize(path) if os.path.exists(path) else 0
            print(f"  - {key}: {os.path.basename(path)} ({size} bytes)")
        
        if result["style_result"]:
            sr = result["style_result"]
            print(f"\n风格化统计:")
            print(f"  效果数: {len(sr.effects)}")
            print(f"  关键帧数: {len(sr.keyframes)}")
            print(f"  图层数: {len(sr.layers)}")
            print(f"  表达式数: {len(sr.expressions)}")
            print(f"  面部效果数: {len(sr.face_effects)}")
        
        if result["detection"]:
            det = result["detection"]
            print(f"\n人物检测统计:")
            print(f"  模式: {det.get('mode', 'N/A')}")
            print(f"  视频: {det.get('width', 0)}x{det.get('height', 0)}")
            print(f"  时长: {det.get('duration', 0):.2f}秒")
            print(f"  检测帧数: {det.get('detection_count', 0)}")
            print(f"  关节数据: {len(det.get('joint_data', []))} 帧")
            print(f"  面部数据: {'有' if det.get('face_data') else '无'}")
            print(f"  边界框: {'有' if det.get('bbox') else '无'}")
    else:
        print(f"\n❌ 处理失败")
        print(f"错误: {result.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
