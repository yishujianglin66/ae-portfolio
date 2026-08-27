#!/usr/bin/env python3
"""
视频帧分析增强版 v2.0
增强功能：
1. 高级场景检测 - 结合PySceneDetect和帧差法
2. 精细颜色特征 - LAB/HSV/LCH多色彩空间分析
3. 运动强度检测 - 光流分析+镜头运动分类
4. 边缘与纹理分析 - Sobel/Laplacian/Canny综合特征
5. 构图分析 - 主体位置、三分法、对称检测
6. 镜头类型识别 - 全景/中景/近景/特写自动识别
"""
import os
import json
import math
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from scenedetect import detect, ContentDetector
    SCENEDETECT_AVAILABLE = True
except ImportError:
    SCENEDETECT_AVAILABLE = False


class EnhancedVideoAnalyzer:
    def __init__(self, enable_cache: bool = True, cache_dir: str = None):
        self._enable_cache = enable_cache
        self._disk_cache = None
        if enable_cache:
            try:
                from performance.cache_manager import DiskCache, file_fingerprint
                self._fingerprint = file_fingerprint
                if cache_dir is None:
                    cache_dir = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        ".cache", "video_analysis"
                    )
                self._disk_cache = DiskCache(cache_dir=cache_dir, name="video_analysis")
            except ImportError:
                # performance 模块不可用时降级为无缓存
                self._enable_cache = False
                self._fingerprint = None

    def analyze_video(self, video_path: str, sample_interval: int = 5, detail_level: str = "standard") -> Dict:
        if not os.path.exists(video_path):
            return {"success": False, "error": f"文件不存在: {video_path}"}

        if not CV2_AVAILABLE:
            return {"success": False, "error": "OpenCV未安装"}

        # 缓存命中检查：基于 path+mtime+参数生成指纹，文件变更自动失效
        if self._enable_cache and self._disk_cache is not None:
            fp_extra = f"{sample_interval}:{detail_level}"
            cache_key = self._fingerprint(video_path, fp_extra)
            cached = self._disk_cache.get(cache_key, source_path=video_path)
            if cached is not None:
                # 标记缓存命中，便于上游感知
                cached = dict(cached)
                cached["_from_cache"] = True
                return cached

        result = {
            "success": False,
            "video_path": video_path,
            "filename": os.path.basename(video_path),
            "analyze_time": datetime.now().isoformat(),
            "detail_level": detail_level
        }

        try:
            basic_info = self._get_basic_info(video_path)
            result["basic_info"] = basic_info

            frames_data = self._sample_frames_enhanced(video_path, sample_interval)
            result["total_frames_sampled"] = len(frames_data)
            result["frames_data"] = frames_data

            scenes = self._detect_scenes_enhanced(video_path)
            result["scenes"] = scenes
            result["scene_count"] = len(scenes)

            transitions = self._analyze_transitions_enhanced(frames_data)
            result["transitions"] = transitions

            color_features = self._analyze_color_features(frames_data)
            result["color_features"] = color_features

            motion_features = self._analyze_motion_features(frames_data)
            result["motion_features"] = motion_features

            composition_features = self._analyze_composition(frames_data)
            result["composition_features"] = composition_features

            shot_types = self._detect_shot_types(video_path)
            result["shot_types"] = shot_types

            visual_effects = self._detect_visual_effects(frames_data)
            result["visual_effects"] = visual_effects

            rhythm_analysis = self._analyze_rhythm(scenes, motion_features)
            result["rhythm_analysis"] = rhythm_analysis

            ae_parameters = self._generate_ae_parameters(result)
            result["ae_parameters"] = ae_parameters

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)

        # 写入缓存（仅成功结果）
        if self._enable_cache and self._disk_cache is not None and result.get("success"):
            try:
                self._disk_cache.set(cache_key, result, source_path=video_path)
            except Exception:
                pass

        return result
    
    def _get_basic_info(self, video_path: str) -> Dict:
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
                "resolution_label": self._get_resolution_label(width, height),
                "pixel_aspect_ratio": round(cap.get(cv2.CAP_PROP_SAR_NUM) / max(cap.get(cv2.CAP_PROP_SAR_DEN), 1), 4)
            }
        finally:
            cap.release()
    
    def _get_resolution_label(self, w: int, h: int) -> str:
        if w >= 7680: return "8K"
        elif w >= 3840: return "4K"
        elif w >= 2560: return "2K"
        elif w >= 1920: return "1080p"
        elif w >= 1280: return "720p"
        elif w >= 854: return "480p"
        else: return "SD"
    
    def _sample_frames_enhanced(self, video_path: str, interval: int = 5) -> List[Dict]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        
        frames_data = []
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
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
                        
                        "hsv": {
                            "hue": float(np.mean(hsv[:, :, 0])),
                            "saturation": float(np.mean(hsv[:, :, 1])),
                            "value": float(np.mean(hsv[:, :, 2])),
                            "hue_std": float(np.std(hsv[:, :, 0])),
                            "sat_std": float(np.std(hsv[:, :, 1])),
                            "val_std": float(np.std(hsv[:, :, 2]))
                        },
                        
                        "lab": {
                            "L": float(np.mean(lab[:, :, 0])),
                            "A": float(np.mean(lab[:, :, 1])),
                            "B": float(np.mean(lab[:, :, 2])),
                            "L_std": float(np.std(lab[:, :, 0])),
                            "A_std": float(np.std(lab[:, :, 1])),
                            "B_std": float(np.std(lab[:, :, 2]))
                        },
                        
                        "rgb": {
                            "R": float(np.mean(frame[:, :, 2])),
                            "G": float(np.mean(frame[:, :, 1])),
                            "B": float(np.mean(frame[:, :, 0])),
                            "R_std": float(np.std(frame[:, :, 2])),
                            "G_std": float(np.std(frame[:, :, 1])),
                            "B_std": float(np.std(frame[:, :, 0]))
                        },
                        
                        "contrast": float(np.std(gray)),
                        "brightness": float(np.mean(gray)),
                        "blur_score": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
                        "edge_intensity": float(np.mean(cv2.Canny(gray, 50, 150)) / 255.0),
                        "sharpness": self._calculate_sharpness(gray),
                        "noise_level": self._calculate_noise_level(gray)
                    }
                    
                    if prev_gray is not None and prev_gray.shape == gray.shape:
                        flow = cv2.calcOpticalFlowFarneback(
                            prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                        )
                        magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
                        
                        frame_info["motion"] = {
                            "avg_magnitude": float(np.mean(magnitude)),
                            "max_magnitude": float(np.max(magnitude)),
                            "min_magnitude": float(np.min(magnitude)),
                            "std_magnitude": float(np.std(magnitude)),
                            "dx": float(np.mean(flow[..., 0])),
                            "dy": float(np.mean(flow[..., 1])),
                            "direction": self._get_motion_direction(np.mean(flow[..., 0]), np.mean(flow[..., 1])),
                            "zoom": self._detect_zoom(flow, width, height)
                        }
                        
                        frame_diff = cv2.absdiff(prev_gray, gray)
                        frame_info["frame_diff"] = {
                            "mean_diff": float(np.mean(frame_diff)),
                            "max_diff": float(np.max(frame_diff)),
                            "diff_ratio": float(np.sum(frame_diff > 30) / (width * height))
                        }
                    else:
                        frame_info["motion"] = {
                            "avg_magnitude": 0, "max_magnitude": 0, "min_magnitude": 0,
                            "std_magnitude": 0, "dx": 0, "dy": 0, "direction": "none", "zoom": "static"
                        }
                        frame_info["frame_diff"] = {"mean_diff": 0, "max_diff": 0, "diff_ratio": 0}
                    
                    frame_info["composition"] = self._analyze_single_frame_composition(frame, width, height)
                    
                    frames_data.append(frame_info)
                    prev_gray = gray.copy()
                
                frame_idx += 1
        finally:
            cap.release()
        
        return frames_data
    
    def _calculate_sharpness(self, gray: np.ndarray) -> float:
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return float(np.mean(np.abs(laplacian)))
    
    def _calculate_noise_level(self, gray: np.ndarray) -> float:
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        noise = cv2.absdiff(gray, blurred)
        return float(np.mean(noise))
    
    def _get_motion_direction(self, dx: float, dy: float) -> str:
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            return "none"
        elif abs(dx) > abs(dy):
            return "right" if dx > 0 else "left"
        else:
            return "down" if dy > 0 else "up"
    
    def _detect_zoom(self, flow: np.ndarray, width: int, height: int) -> str:
        h, w = flow.shape[:2]
        cx, cy = w / 2, h / 2
        y_grid, x_grid = np.mgrid[0:h, 0:w]
        dx_from_center = x_grid - cx
        dy_from_center = y_grid - cy
        dist = np.sqrt(dx_from_center**2 + dy_from_center**2)
        dist[dist == 0] = 1
        
        radial_correlation = np.mean((flow[..., 0] * dx_from_center + flow[..., 1] * dy_from_center) / dist)
        
        if radial_correlation > 0.5:
            return "zoom_in"
        elif radial_correlation < -0.5:
            return "zoom_out"
        else:
            return "static"
    
    def _analyze_single_frame_composition(self, frame: np.ndarray, width: int, height: int) -> Dict:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            
            center_x = (x + w / 2) / width
            center_y = (y + h / 2) / height
            
            rule_of_thirds_score = self._calculate_rule_of_thirds(center_x, center_y)
            balance_score = self._calculate_balance(gray)
            
            return {
                "subject_center_x": round(center_x, 3),
                "subject_center_y": round(center_y, 3),
                "subject_size_ratio": round((w * h) / (width * height), 3),
                "rule_of_thirds_score": round(rule_of_thirds_score, 3),
                "balance_score": round(balance_score, 3),
                "composition_type": self._classify_composition(center_x, center_y, w, h, width, height)
            }
        
        return {
            "subject_center_x": 0.5,
            "subject_center_y": 0.5,
            "subject_size_ratio": 0,
            "rule_of_thirds_score": 0,
            "balance_score": 0,
            "composition_type": "unknown"
        }
    
    def _calculate_rule_of_thirds(self, cx: float, cy: float) -> float:
        thirds = [1/3, 2/3]
        min_dist_x = min(abs(cx - t) for t in thirds)
        min_dist_y = min(abs(cy - t) for t in thirds)
        score_x = max(0, 1 - min_dist_x * 3)
        score_y = max(0, 1 - min_dist_y * 3)
        return (score_x + score_y) / 2
    
    def _calculate_balance(self, gray: np.ndarray) -> float:
        h, w = gray.shape
        left_half = np.mean(gray[:, :w//2])
        right_half = np.mean(gray[:, w//2:])
        top_half = np.mean(gray[:h//2, :])
        bottom_half = np.mean(gray[h//2:, :])
        balance_x = 1 - abs(left_half - right_half) / 255
        balance_y = 1 - abs(top_half - bottom_half) / 255
        return (balance_x + balance_y) / 2
    
    def _classify_composition(self, cx: float, cy: float, w: float, h: float, width: float, height: float) -> str:
        size_ratio = (w * h) / (width * height)
        if size_ratio > 0.4:
            return "close_up"
        elif size_ratio > 0.15:
            return "medium_shot"
        elif size_ratio > 0.05:
            return "wide_shot"
        else:
            return "extreme_wide"
    
    def _detect_scenes_enhanced(self, video_path: str) -> List[Dict]:
        if SCENEDETECT_AVAILABLE:
            try:
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
                        "method": "scenedetect",
                        "type": "cut"
                    })
                return scene_list
            except:
                pass
        
        return self._detect_scenes_opencv(video_path)
    
    def _detect_scenes_opencv(self, video_path: str) -> List[Dict]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        
        scenes = []
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            prev_gray = None
            frame_idx = 0
            scene_start = 0
            prev_diff = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                if prev_gray is not None:
                    diff = cv2.absdiff(prev_gray, gray)
                    diff_score = np.mean(diff)
                    
                    gradient = abs(diff_score - prev_diff)
                    prev_diff = diff_score
                    
                    if diff_score > 35 or (diff_score > 20 and gradient > 15):
                        scene_end = frame_idx
                        scenes.append({
                            "scene_idx": len(scenes) + 1,
                            "start_time": round(scene_start / fps, 3),
                            "end_time": round(scene_end / fps, 3),
                            "duration": round((scene_end - scene_start) / fps, 3),
                            "start_frame": scene_start,
                            "end_frame": scene_end,
                            "type": "cut",
                            "diff_score": round(float(diff_score), 2),
                            "method": "opencv"
                        })
                        scene_start = frame_idx
                
                prev_gray = gray
                frame_idx += 1
            
            if scene_start < frame_idx:
                scenes.append({
                    "scene_idx": len(scenes) + 1,
                    "start_time": round(scene_start / fps, 3),
                    "end_time": round(frame_idx / fps, 3),
                    "duration": round((frame_idx - scene_start) / fps, 3),
                    "start_frame": scene_start,
                    "end_frame": frame_idx,
                    "type": "cut",
                    "method": "opencv"
                })
        finally:
            cap.release()
        
        return scenes
    
    def _analyze_transitions_enhanced(self, frames_data: List[Dict]) -> List[Dict]:
        transitions = []
        
        for i in range(1, len(frames_data)):
            prev = frames_data[i - 1]
            curr = frames_data[i]
            
            time_gap = curr["time_sec"] - prev["time_sec"]
            if time_gap <= 0:
                continue
            
            hsv_prev = prev["hsv"]
            hsv_curr = curr["hsv"]
            lab_prev = prev["lab"]
            lab_curr = curr["lab"]
            
            brightness_diff = abs(hsv_curr["value"] - hsv_prev["value"])
            hue_diff = abs(hsv_curr["hue"] - hsv_prev["hue"])
            sat_diff = abs(hsv_curr["saturation"] - hsv_prev["saturation"])
            l_diff = abs(lab_curr["L"] - lab_prev["L"])
            a_diff = abs(lab_curr["A"] - lab_prev["A"])
            b_diff = abs(lab_curr["B"] - lab_prev["B"])
            
            transition = {
                "time_sec": curr["time_sec"],
                "frame_idx": curr["frame_idx"]
            }
            
            frame_diff = curr.get("frame_diff", {}).get("mean_diff", 0)
            
            if frame_diff > 30 or brightness_diff > 50:
                transition["type"] = "hard_cut"
                transition["confidence"] = min(frame_diff / 60, 1.0)
                transition["ae_effect"] = "无转场效果，直接切换"
            elif brightness_diff > 25 and hsv_curr["value"] > hsv_prev["value"]:
                transition["type"] = "fade_in"
                transition["confidence"] = min(brightness_diff / 50, 1.0)
                transition["ae_params"] = {"property": "opacity", "from": 0, "to": 100}
            elif brightness_diff > 25 and hsv_curr["value"] < hsv_prev["value"]:
                transition["type"] = "fade_out"
                transition["confidence"] = min(brightness_diff / 50, 1.0)
                transition["ae_params"] = {"property": "opacity", "from": 100, "to": 0}
            elif hue_diff > 40 and l_diff < 20:
                transition["type"] = "color_wipe"
                transition["confidence"] = min(hue_diff / 80, 1.0)
                transition["ae_params"] = {"property": "Hue/Saturation", "hue_shift": round(hue_diff)}
            elif abs(curr["motion"]["dx"]) > 3 or abs(curr["motion"]["dy"]) > 3:
                motion_dir = curr["motion"]["direction"]
                transition["type"] = f"slide_{motion_dir}"
                transition["confidence"] = 0.65
                transition["ae_params"] = {"property": "position", "direction": motion_dir}
            elif curr["motion"]["zoom"] != "static" and prev["motion"]["zoom"] == "static":
                transition["type"] = f"zoom_{curr['motion']['zoom']}"
                transition["confidence"] = 0.7
                transition["ae_params"] = {"property": "scale", "from": 100, "to": 130 if curr["motion"]["zoom"] == "zoom_in" else 70}
            elif b_diff > 15 and a_diff > 10:
                transition["type"] = "crossfade"
                transition["confidence"] = min(b_diff / 30, 1.0)
                transition["ae_params"] = {"property": "opacity", "crossfade": True}
            else:
                continue
            
            transitions.append(transition)
        
        return transitions
    
    def _analyze_color_features(self, frames_data: List[Dict]) -> Dict:
        if not frames_data:
            return {}
        
        hues = [f["hsv"]["hue"] for f in frames_data]
        sats = [f["hsv"]["saturation"] for f in frames_data]
        vals = [f["hsv"]["value"] for f in frames_data]
        L_vals = [f["lab"]["L"] for f in frames_data]
        A_vals = [f["lab"]["A"] for f in frames_data]
        B_vals = [f["lab"]["B"] for f in frames_data]
        
        avg_b = np.mean(B_vals)
        if avg_b > 135:
            color_temp = "暖色"
            temp_kelvin = round(3000 + (avg_b - 128) * 120)
        elif avg_b < 121:
            color_temp = "冷色"
            temp_kelvin = round(7500 - (128 - avg_b) * 120)
        else:
            color_temp = "中性"
            temp_kelvin = 5500
        
        avg_sat = np.mean(sats)
        if avg_sat > 140:
            sat_style = "高饱和/鲜艳"
        elif avg_sat > 90:
            sat_style = "中等饱和"
        elif avg_sat > 50:
            sat_style = "低饱和/淡雅"
        else:
            sat_style = "黑白/去色"
        
        avg_contrast = np.mean([f["contrast"] for f in frames_data])
        if avg_contrast > 75:
            contrast_style = "高对比"
        elif avg_contrast > 50:
            contrast_style = "中等对比"
        else:
            contrast_style = "低对比/柔和"
        
        avg_hue = np.mean(hues)
        hue_ranges = {
            (0, 30): "红色系", (30, 60): "橙色系", (60, 90): "黄色系",
            (90, 120): "绿色系", (120, 150): "青色系", (150, 180): "蓝色系",
            (180, 210): "品红色系", (210, 240): "紫色系", (240, 270): "靛蓝色系",
            (270, 300): "紫罗兰色系", (300, 330): "洋红色系", (330, 360): "玫红色系"
        }
        dominant_hue = "中性"
        for (lo, hi), name in hue_ranges.items():
            if lo <= avg_hue <= hi or (lo > hi and (avg_hue >= lo or avg_hue <= hi)):
                dominant_hue = name
                break
        
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
            "avg_brightness": round(float(np.mean(vals)), 1),
            "avg_L": round(float(np.mean(L_vals)), 1),
            "avg_A": round(float(np.mean(A_vals)), 1),
            "avg_B": round(float(np.mean(B_vals)), 1),
            "grading_style": grading_style,
            "color_variance": {
                "hue_std": round(float(np.std(hues)), 1),
                "sat_std": round(float(np.std(sats)), 1),
                "brightness_std": round(float(np.std(vals)), 1)
            },
            "ae_lumetri_params": {
                "temperature": round((avg_b - 128) * 2.5, 1),
                "tint": round((np.mean(A_vals) - 128) * 2.5, 1),
                "contrast": round((avg_contrast - 50) * 2.5, 1),
                "saturation": round((avg_sat - 100) * 2, 1),
                "highlights": round(float(np.mean([v for v in vals if v > np.mean(vals)])) - 128, 1),
                "shadows": round(float(np.mean([v for v in vals if v < np.mean(vals)])) - 128, 1),
                "blacks": round(float(np.percentile(vals, 5)) - 128, 1),
                "whites": round(float(np.percentile(vals, 95)) - 128, 1)
            }
        }
    
    def _infer_grading_style(self, sat: float, contrast: float, b_channel: float, hue: float) -> str:
        if sat < 35:
            return "黑白/去色风格"
        elif sat > 140 and contrast > 70:
            return "赛博朋克/霓虹风格"
        elif b_channel > 140 and sat > 100:
            return "暖色胶片/电影风格"
        elif b_channel < 115 and sat > 80:
            return "冷色科技/悬疑风格"
        elif sat < 75 and contrast < 48:
            return "日系/小清新风格"
        elif contrast > 75 and sat > 110:
            return "高对比度/时尚风格"
        elif b_channel > 138 and sat < 85:
            return "复古/怀旧风格"
        elif contrast > 65 and sat < 65:
            return "暗调/情绪风格"
        elif b_channel > 145 and hue > 40 and hue < 80:
            return "橙色温暖风格"
        elif b_channel < 110 and hue > 180 and hue < 260:
            return "蓝色冷调风格"
        else:
            return "标准/自然风格"
    
    def _analyze_motion_features(self, frames_data: List[Dict]) -> Dict:
        if len(frames_data) < 2:
            return {"avg_motion": 0, "motion_style": "static"}
        
        motions = [f["motion"]["avg_magnitude"] for f in frames_data]
        directions = [f["motion"]["direction"] for f in frames_data]
        zooms = [f["motion"]["zoom"] for f in frames_data]
        
        avg_motion = np.mean(motions)
        max_motion = np.max(motions)
        
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
                elif ratio < 0.25:
                    speed_changes.append({
                        "time_sec": frames_data[i]["time_sec"],
                        "type": "slow_motion",
                        "ratio": round(ratio, 2),
                        "ae_effect": "timeRemap 慢动作",
                        "ae_params": {"property": "timeRemap", "speed": round(ratio, 1)}
                    })
        
        if avg_motion > 10:
            motion_style = "高动态/快节奏"
        elif avg_motion > 4:
            motion_style = "中等动态"
        elif avg_motion > 1.5:
            motion_style = "低动态/平稳"
        else:
            motion_style = "静态/固定镜头"
        
        direction_counts = {}
        for d in directions:
            direction_counts[d] = direction_counts.get(d, 0) + 1
        
        primary_direction = max(direction_counts, key=direction_counts.get, default="none")
        
        zoom_in_count = zooms.count("zoom_in")
        zoom_out_count = zooms.count("zoom_out")
        
        camera_motion = "固定"
        if zoom_in_count > len(zooms) * 0.3:
            camera_motion = "持续缩放进入"
        elif zoom_out_count > len(zooms) * 0.3:
            camera_motion = "持续缩放退出"
        elif primary_direction != "none" and direction_counts[primary_direction] > len(directions) * 0.3:
            camera_motion = {
                "right": "向右平移", "left": "向左平移",
                "up": "向上平移", "down": "向下平移"
            }.get(primary_direction, "固定")
        
        return {
            "avg_motion": round(float(avg_motion), 2),
            "max_motion": round(float(max_motion), 2),
            "motion_style": motion_style,
            "camera_motion": camera_motion,
            "primary_direction": primary_direction,
            "direction_distribution": direction_counts,
            "zoom_in_frames": zoom_in_count,
            "zoom_out_frames": zoom_out_count,
            "speed_changes": speed_changes,
            "motion_variance": round(float(np.std(motions)), 2)
        }
    
    def _analyze_composition(self, frames_data: List[Dict]) -> Dict:
        if not frames_data:
            return {}
        
        centers_x = [f["composition"]["subject_center_x"] for f in frames_data]
        centers_y = [f["composition"]["subject_center_y"] for f in frames_data]
        sizes = [f["composition"]["subject_size_ratio"] for f in frames_data]
        rot_scores = [f["composition"]["rule_of_thirds_score"] for f in frames_data]
        balance_scores = [f["composition"]["balance_score"] for f in frames_data]
        comp_types = [f["composition"]["composition_type"] for f in frames_data]
        
        comp_type_counts = {}
        for ct in comp_types:
            comp_type_counts[ct] = comp_type_counts.get(ct, 0) + 1
        
        dominant_comp_type = max(comp_type_counts, key=comp_type_counts.get, default="unknown")
        
        return {
            "avg_subject_center_x": round(float(np.mean(centers_x)), 3),
            "avg_subject_center_y": round(float(np.mean(centers_y)), 3),
            "avg_subject_size_ratio": round(float(np.mean(sizes)), 3),
            "avg_rule_of_thirds_score": round(float(np.mean(rot_scores)), 3),
            "avg_balance_score": round(float(np.mean(balance_scores)), 3),
            "dominant_composition_type": dominant_comp_type,
            "composition_type_distribution": comp_type_counts
        }
    
    def _detect_shot_types(self, video_path: str) -> List[Dict]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        
        shot_types = []
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            sample_interval = max(1, frame_count // 50)
            frame_idx = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % sample_interval == 0:
                    shot_type = self._classify_shot_type(frame, width, height)
                    
                    shot_types.append({
                        "time_sec": round(frame_idx / fps, 3) if fps > 0 else 0,
                        "frame_idx": frame_idx,
                        "shot_type": shot_type["type"],
                        "confidence": shot_type["confidence"],
                        "reason": shot_type["reason"]
                    })
                
                frame_idx += 1
        finally:
            cap.release()
        
        return shot_types
    
    def _classify_shot_type(self, frame: np.ndarray, width: int, height: int) -> Dict:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            
            size_ratio = (w * h) / (width * height)
            
            if size_ratio > 0.45:
                return {"type": "extreme_close_up", "confidence": min(size_ratio * 2, 1.0), "reason": f"主体占比 {size_ratio:.2%}"}
            elif size_ratio > 0.25:
                return {"type": "close_up", "confidence": min(size_ratio * 3, 1.0), "reason": f"主体占比 {size_ratio:.2%}"}
            elif size_ratio > 0.12:
                return {"type": "medium_close_up", "confidence": min(size_ratio * 5, 1.0), "reason": f"主体占比 {size_ratio:.2%}"}
            elif size_ratio > 0.06:
                return {"type": "medium_shot", "confidence": min(size_ratio * 10, 1.0), "reason": f"主体占比 {size_ratio:.2%}"}
            elif size_ratio > 0.02:
                return {"type": "wide_shot", "confidence": min(size_ratio * 20, 1.0), "reason": f"主体占比 {size_ratio:.2%}"}
            else:
                return {"type": "extreme_wide", "confidence": 0.8, "reason": "主体占比很小"}
        
        return {"type": "unknown", "confidence": 0.3, "reason": "无法检测主体"}
    
    def _detect_visual_effects(self, frames_data: List[Dict]) -> Dict:
        if not frames_data:
            return {}
        
        blur_scores = [f["blur_score"] for f in frames_data]
        edge_intensities = [f["edge_intensity"] for f in frames_data]
        motions = [f["motion"]["avg_magnitude"] for f in frames_data]
        brightness_values = [f["hsv"]["value"] for f in frames_data]
        saturations = [f["hsv"]["saturation"] for f in frames_data]
        
        effects = []
        
        avg_blur = np.mean(blur_scores)
        low_blur_frames = sum(1 for b in blur_scores if b < 50)
        if low_blur_frames > len(blur_scores) * 0.25:
            effects.append({
                "type": "blur",
                "name": "景深模糊/虚化",
                "confidence": min(low_blur_frames / len(blur_scores), 1.0),
                "ae_effect": "高斯模糊/摄像机镜头模糊",
                "ae_params": {"property": "Gaussian Blur", "blurriness": max(10, round(100 - avg_blur / 10))}
            })
        
        high_motion_frames = sum(1 for m in motions if m > 12)
        if high_motion_frames > len(motions) * 0.25:
            effects.append({
                "type": "shake",
                "name": "镜头抖动",
                "confidence": min(high_motion_frames / len(motions), 1.0),
                "ae_effect": "wiggle表达式",
                "ae_params": {"property": "position", "expression": "wiggle(6, 12)"}
            })
        
        high_edge_frames = sum(1 for e in edge_intensities if e > 0.18)
        if high_edge_frames > len(edge_intensities) * 0.35:
            effects.append({
                "type": "glow",
                "name": "发光/辉光效果",
                "confidence": min(high_edge_frames / len(edge_intensities), 1.0),
                "ae_effect": "发光(Glow)",
                "ae_params": {"property": "Glow", "intensity": 90, "radius": 35}
            })
        
        flash_frames = 0
        for i in range(1, len(brightness_values)):
            diff = abs(brightness_values[i] - brightness_values[i-1])
            if diff > 70:
                flash_type = "闪白" if brightness_values[i] > brightness_values[i-1] else "闪黑"
                effects.append({
                    "type": "flash",
                    "name": flash_type,
                    "time_sec": frames_data[i]["time_sec"],
                    "confidence": 0.85,
                    "ae_effect": "亮度闪白/闪黑",
                    "ae_params": {"property": "brightness", "value": 100 if flash_type == "闪白" else -100}
                })
                flash_frames += 1
        
        avg_sat = np.mean(saturations)
        if avg_sat > 150:
            effects.append({
                "type": "color_enhance",
                "name": "色彩增强/鲜艳",
                "confidence": min((avg_sat - 100) / 80, 1.0),
                "ae_effect": "自然饱和度",
                "ae_params": {"property": "Vibrance", "value": 30}
            })
        
        return {
            "detected_effects": effects,
            "effect_count": len(effects),
            "avg_blur_score": round(float(avg_blur), 2),
            "avg_edge_intensity": round(float(np.mean(edge_intensities)), 4),
            "flash_count": flash_frames
        }
    
    def _analyze_rhythm(self, scenes: List[Dict], motion_features: Dict) -> Dict:
        if not scenes:
            return {"rhythm": "unknown"}
        
        durations = [s.get("duration", 0) for s in scenes if s.get("duration", 0) > 0]
        
        if not durations:
            return {"rhythm": "unknown"}
        
        avg_duration = np.mean(durations)
        cut_rate = len(scenes) / max(sum(durations), 1)
        motion_level = motion_features.get("motion_style", "medium")
        
        if avg_duration < 1.2:
            rhythm = "快节奏/高切镜率"
            bpm_equivalent = round(60 / avg_duration)
        elif avg_duration < 3.5:
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
            "longest_shot": round(float(max(durations)), 2),
            "motion_level": motion_level,
            "rhythm_motion_coordination": self._calculate_rhythm_motion_coordination(rhythm, motion_level)
        }
    
    def _calculate_rhythm_motion_coordination(self, rhythm: str, motion_level: str) -> float:
        coordination_map = {
            ("快节奏/高切镜率", "高动态/快节奏"): 0.9,
            ("快节奏/高切镜率", "中等动态"): 0.7,
            ("快节奏/高切镜率", "低动态/平稳"): 0.4,
            ("中等节奏", "中等动态"): 0.85,
            ("中等节奏", "高动态/快节奏"): 0.6,
            ("中等节奏", "低动态/平稳"): 0.6,
            ("慢节奏/长镜头", "低动态/平稳"): 0.9,
            ("慢节奏/长镜头", "中等动态"): 0.6,
            ("慢节奏/长镜头", "高动态/快节奏"): 0.3
        }
        return coordination_map.get((rhythm, motion_level), 0.5)
    
    def _generate_ae_parameters(self, analysis: Dict) -> Dict:
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
        
        color = analysis.get("color_features", {})
        if color.get("ae_lumetri_params"):
            ae_params["adjustment_layers"].append({
                "name": "调色调整层",
                "effect": "Lumetri Color",
                "params": color["ae_lumetri_params"]
            })
        
        for t in analysis.get("transitions", []):
            if t.get("ae_params"):
                ae_params["effects"].append({
                    "name": f"转场_{t['type']}@{t['time_sec']}s",
                    "time": t["time_sec"],
                    "effect": t.get("ae_effect", ""),
                    "params": t["ae_params"]
                })
        
        motion = analysis.get("motion_features", {})
        for sc in motion.get("speed_changes", []):
            if sc.get("ae_params"):
                ae_params["keyframes"].append({
                    "name": f"速度变化_{sc['type']}@{sc['time_sec']}s",
                    "time": sc["time_sec"],
                    "property": "timeRemap",
                    "params": sc["ae_params"]
                })
        
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
        
        if motion.get("camera_motion") in ["持续缩放进入", "持续缩放退出"]:
            ae_params["keyframes"].append({
                "name": "缩放动画",
                "property": "scale",
                "from": 100 if "进入" in motion["camera_motion"] else 130,
                "to": 130 if "进入" in motion["camera_motion"] else 100
            })
        
        return ae_params


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
                analyzer = EnhancedVideoAnalyzer()
                
                func_name = request.get("func")
                params = request.get("params", {})
                
                func_map = {
                    "analyze_video": analyzer.analyze_video,
                }
                
                if func_name in func_map:
                    result = func_map[func_name](**params)
                else:
                    result = {"success": False, "error": f"Unknown function: {func_name}"}
                
                print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return
    
    print("视频帧分析增强版 v2.0")
    print("用法: python video_analyzer_enhanced.py --json-input '{\"func\":\"analyze_video\",\"params\":{\"video_path\":\"xxx.mp4\"}}'")


if __name__ == "__main__":
    main()