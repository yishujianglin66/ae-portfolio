#!/usr/bin/env python3
"""
视频剪辑效果逆向分析器 v1.0
从参考视频中提取剪辑参数，生成AE可执行的参数表和提示词

核心能力：
1. 场景/镜头检测 - 自动分割场景，识别硬切和渐变
2. 转场效果分析 - 检测转场类型（硬切/淡入淡出/缩放/擦除等）
3. 色彩调色分析 - 提取色温、饱和度、对比度、色调参数
4. 运动/速度分析 - 检测速度变化、慢动作、加速
5. 视觉效果检测 - 模糊、抖动、缩放效果
6. 构图分析 - 主体位置、运动方向
7. 生成AE参数表 - 输出可执行的AE ExtendScript参数

依赖：pip install scenedetect opencv-python scikit-image numpy scipy
"""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class VideoEffectAnalyzer:
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path) if config_path else {}
    
    def _load_config(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    
    # ============================================================
    #  一、完整分析入口
    # ============================================================
    
    def analyze_video(self, video_path: str, detail_level: str = "full") -> dict:
        """
        完整视频效果逆向分析
        :param video_path: 视频文件路径
        :param detail_level: 分析精度 "quick"(快速) / "standard"(标准) / "full"(完整)
        :return: 分析结果字典
        """
        if not os.path.exists(video_path):
            return {"success": False, "error": f"文件不存在: {video_path}"}
        
        result = {
            "success": False,
            "video_path": video_path,
            "filename": os.path.basename(video_path),
            "analyze_time": datetime.now().isoformat(),
            "detail_level": detail_level
        }
        
        try:
            # 基础信息
            basic_info = self._get_basic_info(video_path)
            result["basic_info"] = basic_info
            
            # 采样帧
            sample_interval = {"quick": 30, "standard": 10, "full": 5}[detail_level]
            frames_data = self._sample_frames(video_path, sample_interval)
            result["total_frames_sampled"] = len(frames_data)
            
            # 场景检测
            scenes = self._detect_scenes(video_path)
            result["scenes"] = scenes
            result["scene_count"] = len(scenes)
            
            # 转场分析
            transitions = self._analyze_transitions(frames_data)
            result["transitions"] = transitions
            
            # 色彩调色分析
            color_grading = self._analyze_color_grading(frames_data)
            result["color_grading"] = color_grading
            
            # 运动/速度分析
            motion = self._analyze_motion(frames_data)
            result["motion_analysis"] = motion
            
            # 视觉效果检测
            effects = self._detect_visual_effects(frames_data)
            result["visual_effects"] = effects
            
            # 生成AE参数表
            ae_params = self._generate_ae_parameters(result)
            result["ae_parameters"] = ae_params
            
            # 生成提示词
            prompts = self._generate_prompts(result)
            result["prompts"] = prompts
            
            # 剪辑节奏总结
            rhythm = self._analyze_rhythm(scenes, transitions, motion)
            result["rhythm_analysis"] = rhythm
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    # ============================================================
    #  二、基础信息获取
    # ============================================================
    
    def _get_basic_info(self, video_path: str) -> dict:
        """获取视频基础信息"""
        import cv2
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": "无法打开视频"}
        
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0
            
            return {
                "width": width,
                "height": height,
                "fps": round(fps, 2),
                "frame_count": frame_count,
                "duration": round(duration, 2),
                "aspect_ratio": round(width / height, 2) if height > 0 else 0,
                "resolution_label": self._get_resolution_label(width, height)
            }
        finally:
            cap.release()
    
    def _get_resolution_label(self, w: int, h: int) -> str:
        if w >= 3840: return "4K"
        elif w >= 2560: return "2K"
        elif w >= 1920: return "1080p"
        elif w >= 1280: return "720p"
        elif w >= 854: return "480p"
        else: return "SD"
    
    # ============================================================
    #  三、帧采样
    # ============================================================
    
    def _sample_frames(self, video_path: str, interval: int = 5) -> list[dict]:
        """按间隔采样视频帧，提取特征"""
        import cv2
        import numpy as np
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        
        frames_data = []
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            frame_idx = 0
            prev_gray = None
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % interval == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
                    
                    frame_info = {
                        "frame_idx": frame_idx,
                        "time_sec": round(frame_idx / fps, 3) if fps > 0 else 0,
                        
                        # HSV色彩特征
                        "avg_hue": float(np.mean(hsv[:, :, 0])),
                        "avg_saturation": float(np.mean(hsv[:, :, 1])),
                        "avg_brightness": float(np.mean(hsv[:, :, 2])),
                        
                        # LAB色彩特征
                        "avg_L": float(np.mean(lab[:, :, 0])),
                        "avg_A": float(np.mean(lab[:, :, 1])),
                        "avg_B": float(np.mean(lab[:, :, 2])),
                        
                        # 对比度（灰度标准差）
                        "contrast": float(np.std(gray)),
                        
                        # 模糊度（Laplacian方差）
                        "blur_score": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
                        
                        # 边缘强度
                        "edge_intensity": float(np.mean(cv2.Canny(gray, 50, 150)) / 255.0),
                    }
                    
                    # 光流运动分析
                    if prev_gray is not None and prev_gray.shape == gray.shape:
                        flow = cv2.calcOpticalFlowFarneback(
                            prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                        )
                        magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
                        frame_info["avg_motion"] = float(np.mean(magnitude))
                        frame_info["max_motion"] = float(np.max(magnitude))
                        
                        # 运动方向
                        avg_dx = float(np.mean(flow[..., 0]))
                        avg_dy = float(np.mean(flow[..., 1]))
                        frame_info["motion_dx"] = avg_dx
                        frame_info["motion_dy"] = avg_dy
                        
                        # Zoom检测
                        h, w = flow.shape[:2]
                        cx, cy = w / 2, h / 2
                        y_grid, x_grid = np.mgrid[0:h, 0:w]
                        dx_from_center = x_grid - cx
                        dy_from_center = y_grid - cy
                        dist = np.sqrt(dx_from_center**2 + dy_from_center**2)
                        dist[dist == 0] = 1
                        radial_correlation = np.mean((flow[..., 0] * dx_from_center + flow[..., 1] * dy_from_center) / dist)
                        
                        if radial_correlation > 0.3:
                            frame_info["zoom"] = "zoom_in"
                        elif radial_correlation < -0.3:
                            frame_info["zoom"] = "zoom_out"
                        else:
                            frame_info["zoom"] = "static"
                    else:
                        frame_info["avg_motion"] = 0
                        frame_info["max_motion"] = 0
                        frame_info["motion_dx"] = 0
                        frame_info["motion_dy"] = 0
                        frame_info["zoom"] = "static"
                    
                    frames_data.append(frame_info)
                    prev_gray = gray.copy()
                
                frame_idx += 1
        finally:
            cap.release()
        
        return frames_data
    
    # ============================================================
    #  四、场景/镜头检测
    # ============================================================
    
    def _detect_scenes(self, video_path: str) -> list[dict]:
        """使用PySceneDetect检测场景切换"""
        try:
            from scenedetect import ContentDetector, ThresholdDetector, detect
            
            # 硬切检测
            scenes = detect(video_path, ContentDetector(threshold=27.0))
            
            scene_list = []
            for i, (start, end) in enumerate(scenes):
                scene_list.append({
                    "scene_idx": i + 1,
                    "start_time": round(start.get_seconds(), 3),
                    "end_time": round(end.get_seconds(), 3),
                    "duration": round(end.get_seconds() - start.get_seconds(), 3),
                    "start_frame": start.get_frames(),
                    "end_frame": end.get_frames(),
                    "type": "cut"
                })
            
            return scene_list
            
        except ImportError:
            # 如果PySceneDetect不可用，用帧差法替代
            return self._detect_scenes_opencv(video_path)
        except Exception as e:
            return [{"error": str(e)}]
    
    def _detect_scenes_opencv(self, video_path: str) -> list[dict]:
        """OpenCV帧差法场景检测（备用方案）"""
        import cv2
        import numpy as np
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        
        scenes = []
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            prev_gray = None
            frame_idx = 0
            scene_start = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                if prev_gray is not None:
                    diff = cv2.absdiff(prev_gray, gray)
                    diff_score = np.mean(diff)
                    
                    if diff_score > 30:  # 硬切阈值
                        scene_end = frame_idx
                        scenes.append({
                            "scene_idx": len(scenes) + 1,
                            "start_time": round(scene_start / fps, 3),
                            "end_time": round(scene_end / fps, 3),
                            "duration": round((scene_end - scene_start) / fps, 3),
                            "start_frame": scene_start,
                            "end_frame": scene_end,
                            "type": "cut",
                            "diff_score": round(float(diff_score), 2)
                        })
                        scene_start = frame_idx
                
                prev_gray = gray
                frame_idx += 1
            
            # 最后一个场景
            if scene_start < frame_idx:
                scenes.append({
                    "scene_idx": len(scenes) + 1,
                    "start_time": round(scene_start / fps, 3),
                    "end_time": round(frame_idx / fps, 3),
                    "duration": round((frame_idx - scene_start) / fps, 3),
                    "start_frame": scene_start,
                    "end_frame": frame_idx,
                    "type": "cut"
                })
        finally:
            cap.release()
        
        return scenes
    
    # ============================================================
    #  五、转场分析
    # ============================================================
    
    def _analyze_transitions(self, frames_data: list[dict]) -> list[dict]:
        """分析转场效果类型"""
        if len(frames_data) < 2:
            return []
        
        transitions = []
        
        for i in range(1, len(frames_data)):
            prev = frames_data[i - 1]
            curr = frames_data[i]
            
            # 跳过时间不连续的帧
            time_gap = curr["time_sec"] - prev["time_sec"]
            if time_gap <= 0:
                continue
            
            # 硬切：亮度/颜色突然变化
            brightness_diff = abs(curr["avg_brightness"] - prev["avg_brightness"])
            hue_diff = abs(curr["avg_hue"] - prev["avg_hue"])
            sat_diff = abs(curr["avg_saturation"] - prev["avg_saturation"])
            contrast_diff = abs(curr["contrast"] - prev["contrast"])
            
            transition = {
                "time_sec": curr["time_sec"],
                "frame_idx": curr["frame_idx"]
            }
            
            if brightness_diff > 40 and sat_diff > 30:
                transition["type"] = "hard_cut"
                transition["confidence"] = min(brightness_diff / 80, 1.0)
                transition["ae_effect"] = "无转场效果，直接切换"
            elif brightness_diff > 20 and curr["avg_brightness"] > prev["avg_brightness"]:
                transition["type"] = "fade_in"
                transition["confidence"] = min(brightness_diff / 50, 1.0)
                transition["ae_effect"] = "opacity 0→100%"
                transition["ae_params"] = {"property": "opacity", "from": 0, "to": 100}
            elif brightness_diff > 20 and curr["avg_brightness"] < prev["avg_brightness"]:
                transition["type"] = "fade_out"
                transition["confidence"] = min(brightness_diff / 50, 1.0)
                transition["ae_effect"] = "opacity 100→0%"
                transition["ae_params"] = {"property": "opacity", "from": 100, "to": 0}
            elif hue_diff > 30 and brightness_diff < 20:
                transition["type"] = "color_transition"
                transition["confidence"] = min(hue_diff / 60, 1.0)
                transition["ae_effect"] = "色相偏移转场"
                transition["ae_params"] = {
                    "hue_shift": round(hue_diff, 1),
                    "property": "Hue/Saturation"
                }
            elif curr.get("zoom") == "zoom_in" and prev.get("zoom") != "zoom_in":
                transition["type"] = "zoom_in_transition"
                transition["confidence"] = 0.7
                transition["ae_effect"] = "缩放进入转场"
                transition["ae_params"] = {"property": "scale", "from": 100, "to": 150}
            elif curr.get("zoom") == "zoom_out" and prev.get("zoom") != "zoom_out":
                transition["type"] = "zoom_out_transition"
                transition["confidence"] = 0.7
                transition["ae_effect"] = "缩放退出转场"
                transition["ae_params"] = {"property": "scale", "from": 150, "to": 100}
            elif contrast_diff > 20 and brightness_diff < 15:
                transition["type"] = "dissolve"
                transition["confidence"] = min(contrast_diff / 40, 1.0)
                transition["ae_effect"] = "溶解转场"
                transition["ae_params"] = {"property": "opacity", "crossfade": True}
            else:
                continue  # 无明显转场
            
            transitions.append(transition)
        
        return transitions
    
    # ============================================================
    #  六、色彩调色分析
    # ============================================================
    
    def _analyze_color_grading(self, frames_data: list[dict]) -> dict:
        """分析整体色彩调色风格"""
        if not frames_data:
            return {}
        
        import numpy as np
        
        hues = [f["avg_hue"] for f in frames_data]
        sats = [f["avg_saturation"] for f in frames_data]
        brights = [f["avg_brightness"] for f in frames_data]
        contrasts = [f["contrast"] for f in frames_data]
        a_channels = [f["avg_A"] for f in frames_data]
        b_channels = [f["avg_B"] for f in frames_data]
        
        # 色温推断（B通道偏移方向）
        avg_b = np.mean(b_channels)
        if avg_b > 135:
            color_temp = "暖色"
            temp_kelvin = round(3000 + (avg_b - 128) * 100)
        elif avg_b < 121:
            color_temp = "冷色"
            temp_kelvin = round(7500 - (128 - avg_b) * 100)
        else:
            color_temp = "中性"
            temp_kelvin = 5500
        
        # 饱和度风格
        avg_sat = np.mean(sats)
        if avg_sat > 130:
            sat_style = "高饱和/鲜艳"
        elif avg_sat > 80:
            sat_style = "中等饱和"
        elif avg_sat > 40:
            sat_style = "低饱和/淡雅"
        else:
            sat_style = "黑白/去色"
        
        # 对比度风格
        avg_contrast = np.mean(contrasts)
        if avg_contrast > 70:
            contrast_style = "高对比"
        elif avg_contrast > 45:
            contrast_style = "中等对比"
        else:
            contrast_style = "低对比/柔和"
        
        # 色调偏好
        avg_hue = np.mean(hues)
        hue_ranges = {
            (0, 30): "红色系", (30, 60): "橙色系", (60, 90): "黄色系",
            (90, 120): "绿色系", (120, 150): "青色系", (150, 180): "蓝色系"
        }
        dominant_hue = "中性"
        for (lo, hi), name in hue_ranges.items():
            if lo <= avg_hue <= hi:
                dominant_hue = name
                break
        
        # 调色风格推断
        grading_style = self._infer_grading_style(avg_sat, avg_contrast, avg_b, avg_hue)
        
        return {
            "color_temperature": color_temp,
            "temperature_kelvin": temp_kelvin,
            "saturation_style": sat_style,
            "avg_saturation": round(float(avg_sat), 1),
            "contrast_style": contrast_style,
            "avg_contrast": round(float(avg_contrast), 1),
            "dominant_hue": dominant_hue,
            "avg_hue": round(float(avg_hue), 1),
            "avg_brightness": round(float(np.mean(brights)), 1),
            "avg_A": round(float(np.mean(a_channels)), 1),
            "avg_B": round(float(np.mean(b_channels)), 1),
            "grading_style": grading_style,
            "ae_lumetri_params": {
                "temperature": round((avg_b - 128) * 2, 1),
                "tint": round((np.mean(a_channels) - 128) * 2, 1),
                "contrast": round((avg_contrast - 50) * 2, 1),
                "saturation": round((avg_sat - 100) * 1.5, 1),
                "highlights": round(float(np.mean([b for b in brights if b > np.mean(brights)])) - 128, 1),
                "shadows": round(float(np.mean([b for b in brights if b < np.mean(brights)])) - 128, 1)
            }
        }
    
    def _infer_grading_style(self, sat: float, contrast: float, b_channel: float, hue: float) -> str:
        """推断整体调色风格"""
        if sat < 30:
            return "黑白/去色风格"
        elif sat > 130 and contrast > 65:
            return "赛博朋克/霓虹风格"
        elif b_channel > 138 and sat > 90:
            return "暖色胶片/电影风格"
        elif b_channel < 118 and sat > 70:
            return "冷色科技/悬疑风格"
        elif sat < 70 and contrast < 45:
            return "日系/小清新风格"
        elif contrast > 70 and sat > 100:
            return "高对比度/时尚风格"
        elif b_channel > 135 and sat < 80:
            return "复古/怀旧风格"
        elif contrast > 60 and sat < 60:
            return "暗调/情绪风格"
        else:
            return "标准/自然风格"
    
    # ============================================================
    #  七、运动/速度分析
    # ============================================================
    
    def _analyze_motion(self, frames_data: list[dict]) -> dict:
        """分析运动和速度变化"""
        import numpy as np
        
        if len(frames_data) < 2:
            return {"avg_motion": 0, "motion_style": "static"}
        
        motions = [f.get("avg_motion", 0) for f in frames_data]
        max_motions = [f.get("max_motion", 0) for f in frames_data]
        zooms = [f.get("zoom", "static") for f in frames_data]
        dx_list = [f.get("motion_dx", 0) for f in frames_data]
        dy_list = [f.get("motion_dy", 0) for f in frames_data]
        
        avg_motion = np.mean(motions)
        max_motion = np.max(motions)
        
        # 速度变化检测（speed ramp）
        speed_changes = []
        for i in range(1, len(motions)):
            if motions[i] > 0 and motions[i-1] > 0:
                ratio = motions[i] / max(motions[i-1], 0.1)
                if ratio > 3.0:
                    speed_changes.append({
                        "time_sec": frames_data[i]["time_sec"],
                        "type": "speed_up",
                        "ratio": round(ratio, 2),
                        "ae_effect": "timeRemap 加速",
                        "ae_params": {"property": "timeRemap", "speed": round(ratio, 1)}
                    })
                elif ratio < 0.3:
                    speed_changes.append({
                        "time_sec": frames_data[i]["time_sec"],
                        "type": "slow_motion",
                        "ratio": round(ratio, 2),
                        "ae_effect": "timeRemap 慢动作",
                        "ae_params": {"property": "timeRemap", "speed": round(ratio, 1)}
                    })
        
        # 运动风格
        if avg_motion > 8:
            motion_style = "高动态/快节奏"
        elif avg_motion > 3:
            motion_style = "中等动态"
        elif avg_motion > 1:
            motion_style = "低动态/平稳"
        else:
            motion_style = "静态/固定镜头"
        
        # 相机运动方向
        avg_dx = np.mean([d for d in dx_list if abs(d) > 0.5]) if dx_list else 0
        avg_dy = np.mean([d for d in dy_list if abs(d) > 0.5]) if dy_list else 0
        
        camera_motion = "固定"
        if abs(avg_dx) > abs(avg_dy) and abs(avg_dx) > 1.5:
            camera_motion = "向右平移" if avg_dx > 0 else "向左平移"
        elif abs(avg_dy) > abs(avg_dx) and abs(avg_dy) > 1.5:
            camera_motion = "向下平移" if avg_dy > 0 else "向上平移"
        
        zoom_in_count = zooms.count("zoom_in")
        zoom_out_count = zooms.count("zoom_out")
        if zoom_in_count > len(zooms) * 0.3:
            camera_motion = "持续缩放进入"
        elif zoom_out_count > len(zooms) * 0.3:
            camera_motion = "持续缩放退出"
        
        return {
            "avg_motion": round(float(avg_motion), 2),
            "max_motion": round(float(max_motion), 2),
            "motion_style": motion_style,
            "camera_motion": camera_motion,
            "avg_dx": round(float(np.mean(dx_list)), 2),
            "avg_dy": round(float(np.mean(dy_list)), 2),
            "zoom_in_frames": zoom_in_count,
            "zoom_out_frames": zoom_out_count,
            "speed_changes": speed_changes
        }
    
    # ============================================================
    #  八、视觉效果检测
    # ============================================================
    
    def _detect_visual_effects(self, frames_data: list[dict]) -> dict:
        """检测视觉特效"""
        import numpy as np
        
        if not frames_data:
            return {}
        
        blur_scores = [f.get("blur_score", 0) for f in frames_data]
        edge_intensities = [f.get("edge_intensity", 0) for f in frames_data]
        motions = [f.get("avg_motion", 0) for f in frames_data]
        
        effects = []
        
        # 模糊效果检测
        avg_blur = np.mean(blur_scores)
        low_blur_frames = sum(1 for b in blur_scores if b < 50)
        if low_blur_frames > len(blur_scores) * 0.3:
            effects.append({
                "type": "blur",
                "name": "景深模糊/虚化",
                "confidence": min(low_blur_frames / len(blur_scores), 1.0),
                "ae_effect": "高斯模糊/摄像机镜头模糊",
                "ae_params": {"property": "Gaussian Blur", "blurriness": 20}
            })
        
        # 抖动效果检测
        high_motion_frames = sum(1 for m in motions if m > 10)
        if high_motion_frames > len(motions) * 0.3:
            effects.append({
                "type": "shake",
                "name": "镜头抖动",
                "confidence": min(high_motion_frames / len(motions), 1.0),
                "ae_effect": "wiggle表达式",
                "ae_params": {"property": "position", "expression": "wiggle(5, 10)"}
            })
        
        # 边缘发光检测
        high_edge_frames = sum(1 for e in edge_intensities if e > 0.15)
        if high_edge_frames > len(edge_intensities) * 0.4:
            effects.append({
                "type": "glow",
                "name": "发光/辉光效果",
                "confidence": min(high_edge_frames / len(edge_intensities), 1.0),
                "ae_effect": "发光(Glow)",
                "ae_params": {"property": "Glow", "intensity": 80, "radius": 30}
            })
        
        # 闪白/闪黑检测
        brightness_list = [f.get("avg_brightness", 0) for f in frames_data]
        flash_frames = 0
        for i in range(1, len(brightness_list)):
            if abs(brightness_list[i] - brightness_list[i-1]) > 60:
                flash_type = "闪白" if brightness_list[i] > brightness_list[i-1] else "闪黑"
                effects.append({
                    "type": "flash",
                    "name": flash_type,
                    "time_sec": frames_data[i]["time_sec"],
                    "confidence": 0.8,
                    "ae_effect": "亮度闪白/闪黑",
                    "ae_params": {"property": "brightness", "value": 100 if flash_type == "闪白" else -100}
                })
                flash_frames += 1
        
        return {
            "detected_effects": effects,
            "effect_count": len(effects),
            "avg_blur_score": round(float(avg_blur), 2),
            "avg_edge_intensity": round(float(np.mean(edge_intensities)), 4)
        }
    
    # ============================================================
    #  九、剪辑节奏分析
    # ============================================================
    
    def _analyze_rhythm(self, scenes: list[dict], transitions: list[dict], motion: dict) -> dict:
        """分析视频剪辑节奏"""
        import numpy as np
        
        if not scenes:
            return {"rhythm": "unknown"}
        
        durations = [s.get("duration", 0) for s in scenes if s.get("duration", 0) > 0]
        
        if not durations:
            return {"rhythm": "unknown"}
        
        avg_duration = np.mean(durations)
        cut_rate = len(scenes) / max(sum(durations), 1)  # 每秒切镜次数
        
        if avg_duration < 1.5:
            rhythm = "快节奏/高切镜率"
            bpm_equivalent = round(60 / avg_duration)
        elif avg_duration < 4:
            rhythm = "中等节奏"
            bpm_equivalent = round(60 / avg_duration)
        else:
            rhythm = "慢节奏/长镜头"
            bpm_equivalent = round(60 / avg_duration)
        
        return {
            "rhythm": rhythm,
            "avg_shot_duration": round(float(avg_duration), 2),
            "cut_rate": round(float(cut_rate), 3),
            "bpm_equivalent": bpm_equivalent,
            "total_cuts": len(scenes),
            "shortest_shot": round(float(min(durations)), 2),
            "longest_shot": round(float(max(durations)), 2)
        }
    
    # ============================================================
    #  十、生成AE参数表
    # ============================================================
    
    def _generate_ae_parameters(self, analysis: dict) -> dict:
        """从分析结果生成AE可执行的参数表"""
        ae_params = {
            "composition": {
                "width": analysis.get("basic_info", {}).get("width", 1920),
                "height": analysis.get("basic_info", {}).get("height", 1080),
                "fps": analysis.get("basic_info", {}).get("fps", 30),
                "duration": analysis.get("basic_info", {}).get("duration", 10)
            },
            "adjustment_layers": [],
            "effects": [],
            "keyframes": [],
            "expressions": []
        }
        
        # 调色参数
        color = analysis.get("color_grading", {})
        if color.get("ae_lumetri_params"):
            ae_params["adjustment_layers"].append({
                "name": "调色调整层",
                "effect": "Lumetri Color",
                "params": color["ae_lumetri_params"]
            })
        
        # 转场参数
        for t in analysis.get("transitions", []):
            if t.get("ae_params"):
                ae_params["effects"].append({
                    "name": f"转场_{t['type']}@{t['time_sec']}s",
                    "time": t["time_sec"],
                    "effect": t.get("ae_effect", ""),
                    "params": t["ae_params"]
                })
        
        # 速度变化参数
        motion = analysis.get("motion_analysis", {})
        for sc in motion.get("speed_changes", []):
            if sc.get("ae_params"):
                ae_params["keyframes"].append({
                    "name": f"速度变化_{sc['type']}@{sc['time_sec']}s",
                    "time": sc["time_sec"],
                    "property": "timeRemap",
                    "params": sc["ae_params"]
                })
        
        # 视觉效果参数
        vfx = analysis.get("visual_effects", {})
        for eff in vfx.get("detected_effects", []):
            if eff.get("ae_params"):
                if "expression" in eff.get("ae_params", {}):
                    ae_params["expressions"].append({
                        "name": f"效果_{eff['name']}",
                        "property": eff["ae_params"]["property"],
                        "expression": eff["ae_params"]["expression"]
                    })
                else:
                    ae_params["effects"].append({
                        "name": f"效果_{eff['name']}",
                        "effect": eff.get("ae_effect", ""),
                        "params": eff["ae_params"]
                    })
        
        # 缩放动画
        if motion.get("camera_motion") in ["持续缩放进入", "持续缩放退出"]:
            ae_params["keyframes"].append({
                "name": "缩放动画",
                "property": "scale",
                "from": 100 if "进入" in motion["camera_motion"] else 130,
                "to": 130 if "进入" in motion["camera_motion"] else 100
            })
        
        return ae_params
    
    # ============================================================
    #  十一、生成提示词
    # ============================================================
    
    def _generate_prompts(self, analysis: dict) -> dict:
        """生成自然语言提示词，用于MCP端控制AE"""
        color = analysis.get("color_grading", {})
        motion = analysis.get("motion_analysis", {})
        rhythm = analysis.get("rhythm_analysis", {})
        vfx = analysis.get("visual_effects", {})
        
        # 整体风格描述
        style_desc = f"这是一个{color.get('grading_style', '标准')}风格的视频，"
        style_desc += f"色温偏{color.get('color_temperature', '中性')}，"
        style_desc += f"{color.get('saturation_style', '中等饱和')}，"
        style_desc += f"{color.get('contrast_style', '中等对比')}。"
        style_desc += f"剪辑节奏为{rhythm.get('rhythm', '中等节奏')}，"
        style_desc += f"平均镜头时长{rhythm.get('avg_shot_duration', 0):.1f}秒。"
        style_desc += f"相机运动为{motion.get('camera_motion', '固定')}。"
        
        # MCP执行提示词
        mcp_prompt = "请帮我创建一个AE合成，应用以下效果：\n"
        
        if color.get("ae_lumetri_params"):
            lp = color["ae_lumetri_params"]
            mcp_prompt += f"1. 添加Lumetri Color调整层：色温{lp['temperature']}、色调{lp['tint']}、对比度{lp['contrast']}、饱和度{lp['saturation']}\n"
        
        for t in analysis.get("transitions", []):
            if t.get("ae_effect"):
                mcp_prompt += f"2. 在{t['time_sec']}秒添加{t['ae_effect']}\n"
        
        for eff in vfx.get("detected_effects", []):
            if eff.get("ae_effect"):
                mcp_prompt += f"3. 添加{eff['ae_effect']}效果\n"
        
        if motion.get("camera_motion") in ["持续缩放进入", "持续缩放退出"]:
            mcp_prompt += f"4. 添加缩放动画：{motion['camera_motion']}\n"
        
        return {
            "style_description": style_desc,
            "mcp_prompt": mcp_prompt,
            "tags": [
                color.get("grading_style", ""),
                color.get("color_temperature", ""),
                rhythm.get("rhythm", ""),
                motion.get("camera_motion", "")
            ]
        }


# ============================================================
#  JSON输入模式
# ============================================================

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            if len(sys.argv) > 2:
                input_data = sys.argv[2]
            else:
                input_data = sys.stdin.read()
            
            if input_data:
                request = json.loads(input_data)
                analyzer = VideoEffectAnalyzer()
                
                func_name = request.get("func")
                params = request.get("params", {})
                
                func_map = {
                    "analyze_video": analyzer.analyze_video,
                }
                
                if func_name in func_map:
                    result = func_map[func_name](**params)
                else:
                    result = {"success": False, "error": f"Unknown function: {func_name}"}
                
                print(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return
    
    # 交互模式
    print("视频剪辑效果逆向分析器 v1.0")
    print("用法: python video-effect-analyzer.py --json-input '{\"func\":\"analyze_video\",\"params\":{\"video_path\":\"xxx.mp4\"}}'")

if __name__ == "__main__":
    main()
