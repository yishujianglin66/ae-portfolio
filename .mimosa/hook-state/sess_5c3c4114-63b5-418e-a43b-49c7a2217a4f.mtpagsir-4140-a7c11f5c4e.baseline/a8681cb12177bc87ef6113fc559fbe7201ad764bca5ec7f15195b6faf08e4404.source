#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MediaPipe 集成模块 - 人物自动识别与姿态提取

提供人物检测、姿态估计、面部跟踪、手部跟踪功能，
输出标准格式的数据供木偶风格化引擎使用。

支持三种运行模式:
- real: 使用真实 MediaPipe 模型进行识别
- simulate: 模拟识别数据（无安装时降级）
- auto: 自动检测，优先 real，失败降级为 simulate

输出数据格式:
- 姿态数据: 17个身体关节点坐标
- 面部数据: 眼睛、嘴巴、鼻子、下巴等特征点
- 手部数据: 21个手部关键点（可选）
- 人物边界框: 检测到的人物区域

与 puppet_style_engine 的对接:
- 姿态数据 → joint_system 的 joint_data 参数
- 面部数据 → face_puppet 的 face_data 参数
- 边界框 → PuppetStyleConfig 的 bbox 参数
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import os
import json
import time
import math
import random

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

_MEDIAPIPE_AVAILABLE = False
try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    from mediapipe.framework.formats import landmark_pb2
    _MEDIAPIPE_AVAILABLE = True
except ImportError:
    pass


@dataclass
class MediaPipeConfig:
    """MediaPipe 配置
    
    Attributes:
        mode: 运行模式 (real/simulate/auto)
        detect_pose: 是否检测人体姿态
        detect_face: 是否检测面部特征
        detect_hands: 是否检测手部（可选，默认关闭）
        confidence_threshold: 检测置信度阈值 (0-1)
        max_num_persons: 最大检测人数
        sample_interval: 采样间隔（帧数）
        model_complexity: 姿态模型复杂度 (0/1/2)
    """
    mode: str = "auto"
    detect_pose: bool = True
    detect_face: bool = True
    detect_hands: bool = False
    confidence_threshold: float = 0.5
    max_num_persons: int = 1
    sample_interval: int = 5
    model_complexity: int = 1


@dataclass
class PoseLandmark:
    """单个人体关节点
    
    Attributes:
        name: 关节名称
        x: 归一化 X 坐标 (0-1)
        y: 归一化 Y 坐标 (0-1)
        z: 深度坐标（可选）
        visibility: 可见性置信度 (0-1)
        side: 身体侧别 (left/right/center)
    """
    name: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    visibility: float = 0.0
    side: str = "center"


@dataclass
class FaceLandmark:
    """面部特征点
    
    Attributes:
        left_eye: 左眼位置
        right_eye: 右眼位置
        mouth: 嘴巴位置和尺寸
        nose: 鼻子位置
        jaw: 下巴位置
        face_bbox: 面部边界框
    """
    left_eye: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    right_eye: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    mouth: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0})
    nose: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    jaw: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    face_bbox: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0})


@dataclass
class PersonDetection:
    """单人检测结果
    
    Attributes:
        person_id: 人物ID
        bbox: 边界框（像素坐标）
        pose_landmarks: 身体关节点列表
        face_landmarks: 面部特征点
        hands_landmarks: 手部关键点（左右）
        confidence: 检测置信度
    """
    person_id: int = 0
    bbox: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0})
    pose_landmarks: List[PoseLandmark] = field(default_factory=list)
    face_landmarks: Optional[FaceLandmark] = None
    hands_landmarks: Dict[str, List[Dict[str, float]]] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class MediaPipeResult:
    """MediaPipe 识别结果
    
    Attributes:
        success: 是否成功
        mode: 实际运行模式 (real/simulate)
        video_path: 输入视频路径
        frame_count: 处理帧数
        duration: 视频时长（秒）
        width: 视频宽度
        height: 视频高度
        fps: 视频帧率
        detections: 逐帧人物检测列表
        error: 错误信息（如果失败）
    """
    success: bool = False
    mode: str = "simulate"
    video_path: str = ""
    frame_count: int = 0
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 30.0
    detections: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""


class MediaPipeIntegrator:
    """MediaPipe 集成器 - 主入口类
    
    提供人物检测、姿态估计、面部跟踪、手部跟踪功能，
    输出标准格式的数据供木偶风格化引擎使用。
    """
    
    POSE_LANDMARK_NAMES = [
        "nose", "left_eye_inner", "left_eye", "left_eye_outer",
        "right_eye_inner", "right_eye", "right_eye_outer",
        "left_ear", "right_ear", "mouth_left", "mouth_right",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_pinky", "right_pinky",
        "left_index", "right_index", "left_thumb", "right_thumb",
        "left_hip", "right_hip", "left_knee", "right_knee",
        "left_ankle", "right_ankle", "left_heel", "right_heel",
        "left_foot_index", "right_foot_index"
    ]
    
    JOINT_MAPPING = {
        "head": ["nose"],
        "neck": ["left_shoulder", "right_shoulder"],
        "shoulder_left": ["left_shoulder"],
        "shoulder_right": ["right_shoulder"],
        "elbow_left": ["left_elbow"],
        "elbow_right": ["right_elbow"],
        "wrist_left": ["left_wrist"],
        "wrist_right": ["right_wrist"],
        "spine": ["left_hip", "right_hip"],
        "hip_left": ["left_hip"],
        "hip_right": ["right_hip"],
        "knee_left": ["left_knee"],
        "knee_right": ["right_knee"],
        "ankle_left": ["left_ankle"],
        "ankle_right": ["right_ankle"],
    }
    
    def __init__(self, config: Optional[MediaPipeConfig] = None):
        self.config = config or MediaPipeConfig()
        self._pose_detector = None
        self._face_detector = None
        self._hands_detector = None
        self._mode = self.config.mode
        
        if self._mode == "auto":
            if _MEDIAPIPE_AVAILABLE and CV2_AVAILABLE:
                self._mode = "real"
                self._init_detectors()
            else:
                self._mode = "simulate"
        elif self._mode == "real":
            if _MEDIAPIPE_AVAILABLE and CV2_AVAILABLE:
                self._init_detectors()
            else:
                self._mode = "simulate"
    
    def is_available(self) -> bool:
        """检查 MediaPipe 是否可用"""
        return _MEDIAPIPE_AVAILABLE and CV2_AVAILABLE
    
    def get_mode(self) -> str:
        """获取当前运行模式"""
        return self._mode
    
    def _init_detectors(self) -> None:
        """初始化 MediaPipe 检测器"""
        try:
            base_options = python.BaseOptions(model_asset_path=None)
            
            if self.config.detect_pose:
                pose_options = vision.PoseLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.IMAGE,
                    num_poses=self.config.max_num_persons,
                    min_pose_detection_confidence=self.config.confidence_threshold,
                    min_pose_presence_confidence=self.config.confidence_threshold,
                    model_complexity=self.config.model_complexity,
                )
                self._pose_detector = vision.PoseLandmarker.create_from_options(pose_options)
            
            if self.config.detect_face:
                face_options = vision.FaceLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.IMAGE,
                    num_faces=self.config.max_num_persons,
                    min_face_detection_confidence=self.config.confidence_threshold,
                    min_face_presence_confidence=self.config.confidence_threshold,
                )
                self._face_detector = vision.FaceLandmarker.create_from_options(face_options)
            
            if self.config.detect_hands:
                hands_options = vision.HandLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.IMAGE,
                    num_hands=2,
                    min_hand_detection_confidence=self.config.confidence_threshold,
                    min_hand_presence_confidence=self.config.confidence_threshold,
                )
                self._hands_detector = vision.HandLandmarker.create_from_options(hands_options)
                
        except Exception as e:
            self._mode = "simulate"
            self._pose_detector = None
            self._face_detector = None
            self._hands_detector = None
    
    def process_video(self, video_path: str) -> MediaPipeResult:
        """处理视频，提取人物姿态和面部数据
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            MediaPipeResult 包含逐帧检测数据
        """
        result = MediaPipeResult(
            video_path=video_path,
            mode=self._mode,
        )
        
        if not os.path.exists(video_path):
            result.error = f"文件不存在: {video_path}"
            return result
        
        if self._mode == "simulate":
            return self._process_video_simulate(video_path)
        
        if not CV2_AVAILABLE:
            result.error = "OpenCV 未安装"
            return result
        
        cap = None
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                result.error = "无法打开视频"
                return result
            
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            
            result.width = width
            result.height = height
            result.fps = fps
            result.duration = duration
            
            frame_idx = 0
            detections = []
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % self.config.sample_interval == 0:
                    detection = self._process_frame(frame, frame_idx, fps, width, height)
                    detections.append(detection)
                
                frame_idx += 1
            
            result.frame_count = frame_idx
            result.detections = detections
            result.success = len(detections) > 0
            
        except Exception as e:
            result.error = str(e)
        finally:
            if cap is not None:
                cap.release()
        
        return result
    
    def _process_frame(self, frame: Any, frame_idx: int, fps: float, 
                       width: int, height: int) -> Dict[str, Any]:
        """处理单帧图像
        
        Args:
            frame: OpenCV 图像帧
            frame_idx: 帧索引
            fps: 帧率
            width: 图像宽度
            height: 图像高度
            
        Returns:
            单帧检测结果
        """
        time_sec = frame_idx / fps if fps > 0 else 0.0
        
        result = {
            "time_sec": round(time_sec, 3),
            "frame_idx": frame_idx,
            "persons": [],
        }
        
        if self.config.detect_pose and self._pose_detector:
            try:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
                pose_result = self._pose_detector.detect(mp_image)
                
                for i, landmarks in enumerate(pose_result.pose_landmarks):
                    if i >= self.config.max_num_persons:
                        break
                    
                    person = self._extract_pose_person(landmarks, width, height, i)
                    result["persons"].append(person)
                    
            except Exception:
                pass
        
        if self.config.detect_face and self._face_detector and result["persons"]:
            try:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
                face_result = self._face_detector.detect(mp_image)
                
                for i, landmarks in enumerate(face_result.face_landmarks):
                    if i < len(result["persons"]):
                        face_data = self._extract_face_data(landmarks, width, height)
                        result["persons"][i]["face_landmarks"] = face_data
                        result["persons"][i]["face_bbox"] = face_data.face_bbox
                        
            except Exception:
                pass
        
        if self.config.detect_hands and self._hands_detector:
            try:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
                hands_result = self._hands_detector.detect(mp_image)
                
                for i, person in enumerate(result["persons"]):
                    if i < len(hands_result.handedness):
                        person["hands_landmarks"] = {}
                        if hands_result.hand_landmarks[i]:
                            person["hands_landmarks"]["left"] = self._extract_hand_data(
                                hands_result.hand_landmarks[i][0] if len(hands_result.hand_landmarks[i]) > 0 else [],
                                width, height
                            )
                        if len(hands_result.hand_landmarks[i]) > 1:
                            person["hands_landmarks"]["right"] = self._extract_hand_data(
                                hands_result.hand_landmarks[i][1],
                                width, height
                            )
                            
            except Exception:
                pass
        
        return result
    
    def _extract_pose_person(self, landmarks: Any, width: int, height: int, 
                             person_id: int) -> Dict[str, Any]:
        """从姿态结果提取人物数据
        
        Args:
            landmarks: MediaPipe 姿态关键点
            width: 图像宽度
            height: 图像高度
            person_id: 人物ID
            
        Returns:
            人物数据字典
        """
        pose_landmarks = []
        
        for i, lm in enumerate(landmarks):
            name = self.POSE_LANDMARK_NAMES[i] if i < len(self.POSE_LANDMARK_NAMES) else f"landmark_{i}"
            
            if "_left" in name:
                side = "left"
            elif "_right" in name:
                side = "right"
            else:
                side = "center"
            
            pose_landmarks.append({
                "name": name,
                "x": lm.x,
                "y": lm.y,
                "z": lm.z,
                "visibility": lm.visibility,
                "side": side,
                "px": lm.x * width,
                "py": lm.y * height,
            })
        
        min_x = min(lm["x"] for lm in pose_landmarks)
        max_x = max(lm["x"] for lm in pose_landmarks)
        min_y = min(lm["y"] for lm in pose_landmarks)
        max_y = max(lm["y"] for lm in pose_landmarks)
        
        bbox = {
            "x": min_x * width,
            "y": min_y * height,
            "width": (max_x - min_x) * width,
            "height": (max_y - min_y) * height,
        }
        
        avg_visibility = sum(lm["visibility"] for lm in pose_landmarks) / max(len(pose_landmarks), 1)
        
        return {
            "person_id": person_id,
            "bbox": bbox,
            "pose_landmarks": pose_landmarks,
            "confidence": avg_visibility,
        }
    
    def _extract_face_data(self, landmarks: Any, width: int, height: int) -> FaceLandmark:
        """从面部关键点提取面部数据
        
        Args:
            landmarks: MediaPipe 面部关键点
            width: 图像宽度
            height: 图像高度
            
        Returns:
            FaceLandmark 数据类
        """
        left_eye_idx = 33
        right_eye_idx = 263
        nose_idx = 1
        mouth_center_idx = 13
        mouth_left_idx = 61
        mouth_right_idx = 291
        jaw_idx = 152
        
        left_eye = landmarks[left_eye_idx]
        right_eye = landmarks[right_eye_idx]
        nose = landmarks[nose_idx]
        mouth_center = landmarks[mouth_center_idx]
        mouth_left = landmarks[mouth_left_idx]
        mouth_right = landmarks[mouth_right_idx]
        jaw = landmarks[jaw_idx]
        
        min_x = min(lm.x for lm in landmarks)
        max_x = max(lm.x for lm in landmarks)
        min_y = min(lm.y for lm in landmarks)
        max_y = max(lm.y for lm in landmarks)
        
        return FaceLandmark(
            left_eye={
                "x": left_eye.x * width,
                "y": left_eye.y * height,
            },
            right_eye={
                "x": right_eye.x * width,
                "y": right_eye.y * height,
            },
            mouth={
                "x": mouth_center.x * width,
                "y": mouth_center.y * height,
                "width": abs(mouth_right.x - mouth_left.x) * width,
                "height": abs(mouth_center.y - nose.y) * height * 0.4,
            },
            nose={
                "x": nose.x * width,
                "y": nose.y * height,
            },
            jaw={
                "x": jaw.x * width,
                "y": jaw.y * height,
            },
            face_bbox={
                "x": min_x * width,
                "y": min_y * height,
                "width": (max_x - min_x) * width,
                "height": (max_y - min_y) * height,
            },
        )
    
    def _extract_hand_data(self, landmarks: Any, width: int, height: int) -> List[Dict[str, float]]:
        """提取手部关键点数据
        
        Args:
            landmarks: MediaPipe 手部关键点
            width: 图像宽度
            height: 图像高度
            
        Returns:
            手部关键点列表
        """
        hand_data = []
        for i, lm in enumerate(landmarks):
            hand_data.append({
                "name": f"finger_{i}",
                "x": lm.x * width,
                "y": lm.y * height,
                "z": lm.z,
            })
        return hand_data
    
    def _process_video_simulate(self, video_path: str) -> MediaPipeResult:
        """模拟模式处理视频
        
        当 MediaPipe 不可用时，生成合理的模拟数据。
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            模拟检测结果
        """
        result = MediaPipeResult(
            video_path=video_path,
            mode="simulate",
        )
        
        if CV2_AVAILABLE:
            try:
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    result.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    result.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    result.fps = cap.get(cv2.CAP_PROP_FPS)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    result.duration = total_frames / result.fps if result.fps > 0 else 5.0
                    cap.release()
                else:
                    result.width = 1920
                    result.height = 1080
                    result.fps = 30.0
                    result.duration = 5.0
            except:
                result.width = 1920
                result.height = 1080
                result.fps = 30.0
                result.duration = 5.0
        else:
            result.width = 1920
            result.height = 1080
            result.fps = 30.0
            result.duration = 5.0
        
        result.detections = self._generate_simulated_detections(result)
        result.success = True
        result.frame_count = len(result.detections) * self.config.sample_interval
        
        return result
    
    def _generate_simulated_detections(self, result: MediaPipeResult) -> List[Dict[str, Any]]:
        """生成模拟检测数据
        
        Args:
            result: 包含视频基本信息的结果对象
            
        Returns:
            模拟的逐帧检测列表
        """
        detections = []
        width = result.width
        height = result.height
        fps = result.fps
        duration = result.duration
        
        total_frames = int(duration * fps)
        sample_frames = total_frames // self.config.sample_interval
        
        center_x = width / 2.0
        center_y = height / 2.0
        bbox_width = width * 0.35
        bbox_height = height * 0.6
        
        for i in range(sample_frames):
            frame_idx = i * self.config.sample_interval
            time_sec = frame_idx / fps
            
            t = time_sec / duration
            sway_x = math.sin(t * 2 * math.pi) * 30
            sway_y = math.sin(t * 3 * math.pi) * 15
            
            person_bbox = {
                "x": center_x - bbox_width / 2 + sway_x,
                "y": center_y - bbox_height / 2 + sway_y,
                "width": bbox_width,
                "height": bbox_height,
            }
            
            pose_landmarks = self._generate_simulated_pose(person_bbox)
            face_landmarks = self._generate_simulated_face(person_bbox)
            
            detections.append({
                "time_sec": round(time_sec, 3),
                "frame_idx": frame_idx,
                "persons": [{
                    "person_id": 0,
                    "bbox": person_bbox,
                    "pose_landmarks": pose_landmarks,
                    "face_landmarks": face_landmarks,
                    "face_bbox": face_landmarks.face_bbox,
                    "confidence": 0.85 + random.random() * 0.1,
                }],
            })
        
        return detections
    
    def _generate_simulated_pose(self, bbox: Dict[str, float]) -> List[Dict[str, Any]]:
        """生成模拟姿态数据
        
        Args:
            bbox: 人物边界框
            
        Returns:
            模拟姿态关键点列表
        """
        x = bbox["x"]
        y = bbox["y"]
        w = bbox["width"]
        h = bbox["height"]
        
        cx = x + w / 2.0
        head_y = y + h * 0.12
        neck_y = y + h * 0.20
        shoulder_y = y + h * 0.28
        elbow_y = y + h * 0.45
        wrist_y = y + h * 0.60
        waist_y = y + h * 0.52
        hip_y = y + h * 0.58
        knee_y = y + h * 0.78
        ankle_y = y + h * 0.92
        
        shoulder_w = w * 0.35
        hip_w = w * 0.25
        
        joints = [
            {"name": "nose", "x": cx, "y": head_y, "visibility": 0.95, "side": "center"},
            {"name": "left_shoulder", "x": cx - shoulder_w, "y": shoulder_y, "visibility": 0.92, "side": "left"},
            {"name": "right_shoulder", "x": cx + shoulder_w, "y": shoulder_y, "visibility": 0.92, "side": "right"},
            {"name": "left_elbow", "x": cx - shoulder_w - w * 0.08, "y": elbow_y, "visibility": 0.88, "side": "left"},
            {"name": "right_elbow", "x": cx + shoulder_w + w * 0.08, "y": elbow_y, "visibility": 0.88, "side": "right"},
            {"name": "left_wrist", "x": cx - shoulder_w - w * 0.15, "y": wrist_y, "visibility": 0.85, "side": "left"},
            {"name": "right_wrist", "x": cx + shoulder_w + w * 0.15, "y": wrist_y, "visibility": 0.85, "side": "right"},
            {"name": "left_hip", "x": cx - hip_w, "y": hip_y, "visibility": 0.90, "side": "left"},
            {"name": "right_hip", "x": cx + hip_w, "y": hip_y, "visibility": 0.90, "side": "right"},
            {"name": "left_knee", "x": cx - hip_w * 0.7, "y": knee_y, "visibility": 0.85, "side": "left"},
            {"name": "right_knee", "x": cx + hip_w * 0.7, "y": knee_y, "visibility": 0.85, "side": "right"},
            {"name": "left_ankle", "x": cx - hip_w * 0.5, "y": ankle_y, "visibility": 0.80, "side": "left"},
            {"name": "right_ankle", "x": cx + hip_w * 0.5, "y": ankle_y, "visibility": 0.80, "side": "right"},
        ]
        
        for j in joints:
            j["px"] = j["x"]
            j["py"] = j["y"]
        
        return joints
    
    def _generate_simulated_face(self, bbox: Dict[str, float]) -> FaceLandmark:
        """生成模拟面部数据
        
        Args:
            bbox: 人物边界框
            
        Returns:
            FaceLandmark 数据类
        """
        x = bbox["x"]
        y = bbox["y"]
        w = bbox["width"]
        h = bbox["height"]
        
        face_top = y + h * 0.05
        face_bottom = y + h * 0.25
        face_width = w * 0.4
        face_x = x + w / 2 - face_width / 2
        
        face_h = face_bottom - face_top
        cx = face_x + face_width / 2
        
        eye_y = face_top + face_h * 0.35
        eye_spacing = face_width * 0.25
        
        return FaceLandmark(
            left_eye={
                "x": cx - eye_spacing,
                "y": eye_y,
            },
            right_eye={
                "x": cx + eye_spacing,
                "y": eye_y,
            },
            mouth={
                "x": cx,
                "y": face_top + face_h * 0.72,
                "width": face_width * 0.35,
                "height": face_h * 0.08,
            },
            nose={
                "x": cx,
                "y": face_top + face_h * 0.55,
            },
            jaw={
                "x": cx,
                "y": face_bottom - face_h * 0.05,
            },
            face_bbox={
                "x": face_x,
                "y": face_top,
                "width": face_width,
                "height": face_h,
            },
        )
    
    def convert_to_puppet_format(self, result: MediaPipeResult) -> Dict[str, Any]:
        """将 MediaPipe 结果转换为木偶风格化引擎可用的格式
        
        Args:
            result: MediaPipeResult 检测结果
            
        Returns:
            包含 bbox, joint_data, face_data 的字典
        """
        if not result.success or not result.detections:
            return {
                "bbox": None,
                "joint_data": [],
                "face_data": None,
            }
        
        first_detection = result.detections[0]
        if not first_detection.get("persons"):
            return {
                "bbox": None,
                "joint_data": [],
                "face_data": None,
            }
        
        person = first_detection["persons"][0]
        
        bbox = person.get("bbox")
        
        joint_data = self._convert_joint_data(result)
        
        face_data = None
        if person.get("face_landmarks"):
            fl = person["face_landmarks"]
            if isinstance(fl, FaceLandmark):
                face_data = {
                    "left_eye": fl.left_eye,
                    "right_eye": fl.right_eye,
                    "mouth": fl.mouth,
                    "nose": fl.nose,
                    "jaw": fl.jaw,
                    "face_bbox": fl.face_bbox,
                }
            elif isinstance(fl, dict):
                face_data = {
                    "left_eye": fl.get("left_eye", {}),
                    "right_eye": fl.get("right_eye", {}),
                    "mouth": fl.get("mouth", {}),
                    "nose": fl.get("nose", {}),
                    "jaw": fl.get("jaw", {}),
                    "face_bbox": fl.get("face_bbox", {}),
                }
        
        return {
            "bbox": bbox,
            "joint_data": joint_data,
            "face_data": face_data,
            "width": result.width,
            "height": result.height,
            "fps": result.fps,
            "duration": result.duration,
        }
    
    def _convert_joint_data(self, result: MediaPipeResult) -> List[Dict[str, Any]]:
        """转换关节数据为木偶风格化引擎可用的格式
        
        Args:
            result: MediaPipeResult 检测结果
            
        Returns:
            关节关键帧数据列表
        """
        joint_data = []
        
        for detection in result.detections:
            time_sec = detection.get("time_sec", 0.0)
            
            if detection.get("persons"):
                person = detection["persons"][0]
                pose_landmarks = person.get("pose_landmarks", [])
                
                joints = []
                for lm in pose_landmarks:
                    joint_name = self._map_landmark_to_joint(lm.get("name", ""))
                    if joint_name:
                        joints.append({
                            "name": joint_name,
                            "x": lm.get("px", lm.get("x", 0) * result.width),
                            "y": lm.get("py", lm.get("y", 0) * result.height),
                        })
                
                if joints:
                    joint_data.append({
                        "time": time_sec,
                        "joints": joints,
                    })
        
        return joint_data
    
    def _map_landmark_to_joint(self, landmark_name: str) -> Optional[str]:
        """将 MediaPipe 关键点名称映射为关节名称
        
        Args:
            landmark_name: MediaPipe 关键点名称
            
        Returns:
            关节名称或 None
        """
        mapping = {
            "nose": "head",
            "left_shoulder": "shoulder_left",
            "right_shoulder": "shoulder_right",
            "left_elbow": "elbow_left",
            "right_elbow": "elbow_right",
            "left_wrist": "wrist_left",
            "right_wrist": "wrist_right",
            "left_hip": "hip_left",
            "right_hip": "hip_right",
            "left_knee": "knee_left",
            "right_knee": "knee_right",
            "left_ankle": "ankle_left",
            "right_ankle": "ankle_right",
        }
        return mapping.get(landmark_name)
    
    def save_result(self, result: MediaPipeResult, output_path: str) -> bool:
        """保存检测结果到文件
        
        Args:
            result: MediaPipeResult 检测结果
            output_path: 输出文件路径
            
        Returns:
            是否成功保存
        """
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            data = {
                "success": result.success,
                "mode": result.mode,
                "video_path": result.video_path,
                "width": result.width,
                "height": result.height,
                "fps": result.fps,
                "duration": result.duration,
                "frame_count": result.frame_count,
                "detection_count": len(result.detections),
                "error": result.error,
            }
            
            puppet_format = self.convert_to_puppet_format(result)
            data["puppet_format"] = puppet_format
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            return True
        except Exception as e:
            return False


if __name__ == "__main__":
    print("=" * 60)
    print("MediaPipeIntegrator 模块自测")
    print("=" * 60)
    
    config = MediaPipeConfig(
        mode="auto",
        detect_pose=True,
        detect_face=True,
        detect_hands=False,
    )
    
    integrator = MediaPipeIntegrator(config)
    
    print(f"\n[配置信息]")
    print(f"  模式: {integrator.get_mode()}")
    print(f"  MediaPipe 可用: {integrator.is_available()}")
    print(f"  检测姿态: {config.detect_pose}")
    print(f"  检测面部: {config.detect_face}")
    print(f"  检测手部: {config.detect_hands}")
    print(f"  采样间隔: {config.sample_interval} 帧")
    
    print(f"\n[测试 1] 模拟模式处理")
    import tempfile
    import subprocess
    
    test_video = None
    ffmpeg_path = r"D:\app\FormatFactory\ffmpeg.exe"
    if os.path.exists(ffmpeg_path):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            test_video = f.name
        
        cmd = [
            ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", "testsrc=duration=3:size=640x360:rate=30",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=3",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            test_video,
        ]
        subprocess.run(cmd, capture_output=True, timeout=60)
    
    if test_video and os.path.exists(test_video):
        print(f"  测试视频: {os.path.basename(test_video)}")
        print(f"  开始处理...")
        
        start_time = time.time()
        result = integrator.process_video(test_video)
        elapsed = time.time() - start_time
        
        print(f"  处理耗时: {elapsed:.2f} 秒")
        print(f"  结果: {'成功' if result.success else '失败'}")
        print(f"  模式: {result.mode}")
        print(f"  视频: {result.width}x{result.height} @ {result.fps:.1f}fps")
        print(f"  时长: {result.duration:.2f} 秒")
        print(f"  检测帧数: {len(result.detections)}")
        
        if result.success and result.detections:
            first_det = result.detections[0]
            print(f"  第一帧人数: {len(first_det.get('persons', []))}")
            if first_det.get("persons"):
                person = first_det["persons"][0]
                print(f"    边界框: x={person['bbox']['x']:.0f}, y={person['bbox']['y']:.0f}, "
                      f"w={person['bbox']['width']:.0f}, h={person['bbox']['height']:.0f}")
                print(f"    姿态关键点: {len(person.get('pose_landmarks', []))}")
                print(f"    面部数据: {'有' if person.get('face_landmarks') else '无'}")
        
        puppet_format = integrator.convert_to_puppet_format(result)
        print(f"  木偶格式转换:")
        print(f"    bbox: {'有' if puppet_format['bbox'] else '无'}")
        print(f"    joint_data: {len(puppet_format['joint_data'])} 帧")
        print(f"    face_data: {'有' if puppet_format['face_data'] else '无'}")
        
        output_path = os.path.join(os.path.dirname(test_video), "mediapipe_result.json")
        saved = integrator.save_result(result, output_path)
        print(f"  结果保存: {'成功' if saved else '失败'}")
        
        os.unlink(test_video)
        if os.path.exists(output_path):
            os.unlink(output_path)
    else:
        print(f"  跳过（无 ffmpeg）")
    
    print(f"\n[测试 2] 直接生成模拟数据")
    sim_result = MediaPipeResult()
    sim_result.width = 1280
    sim_result.height = 720
    sim_result.fps = 30.0
    sim_result.duration = 5.0
    
    detections = integrator._generate_simulated_detections(sim_result)
    print(f"  生成检测帧数: {len(detections)}")
    if detections:
        det = detections[0]
        print(f"  第一帧时间: {det['time_sec']:.2f}s")
        print(f"  人物数: {len(det['persons'])}")
    
    puppet_format = integrator.convert_to_puppet_format(sim_result)
    print(f"  joint_data 帧数: {len(puppet_format['joint_data'])}")
    
    print(f"\n[测试 3] 关节映射")
    test_landmarks = ["nose", "left_shoulder", "right_elbow", "left_knee", "unknown"]
    for lm in test_landmarks:
        joint = integrator._map_landmark_to_joint(lm)
        print(f"  {lm} -> {joint}")
    
    print(f"\n{'=' * 60}")
    print("自测完成 ✓")
    print(f"{'=' * 60}")
