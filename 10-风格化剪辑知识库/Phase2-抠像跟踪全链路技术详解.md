# Phase 2 抠像与跟踪 - 全链路技术详解

---

## 文档信息

| 项目 | 内容 |
|------|------|
| **阶段** | Phase 2 抠像与跟踪 |
| **涉及引擎** | 8个（2商业 + 6开源） |
| **处理时长** | 约为视频时长的 2-5倍（取决于复杂度） |
| **核心产物** | EXR蒙版序列 + 关节点数据 + 面部数据 + 跟踪数据 + 相机位姿 |

---

## 一、抠像跟踪流水线总览

### 1.1 流水线结构

```
Phase 1 输出
    │ （增强视频 + 人物bbox + 初筛Alpha + 镜头列表）
    ▼
┌─────────────────────────────────────────────────────┐
│  步骤1：蒙版生成（双模型融合）                         │
│  SAM2Matting（精细） + RVM（时序稳定）→ 融合蒙版      │
└────────────────────────┬────────────────────────────┘
                         │
    ┌────────────────────┴────────────────────┐
    │                                         │
    ▼                                         ▼
┌──────────┐                          ┌──────────┐
│ 步骤2    │                          │ 步骤3    │
│ Silhouette│                          │ 人体姿态 │
│ 边缘精修  │                          │ 估计     │
│ + Roto   │                          │ MediaPipe│
│ 优化     │                          │ + DWPose │
└──────────┘                          └──────────┘
    │                                         │
    └────────────────────┬────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
┌──────────┐      ┌──────────┐        ┌──────────┐
│ 步骤4    │      │ 步骤5    │        │ 步骤6    │
│ 面部关键点│      │ 表情分析 │        │ 摄像机   │
│ Insight- │      │ OpenFace │        │ 反求     │
│ Face     │      │          │        │ Blender  │
│ +MediaPipe│      │          │        │ + COLMAP │
└──────────┘      └──────────┘        └──────────┘
    │                    │                    │
    └────────────────────┬────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  步骤7：数据融合与质量校验 + 格式转换                  │
│  所有跟踪/蒙版数据 → 统一格式 → Silhouette/AE可用格式  │
└─────────────────────────────────────────────────────┘
```

### 1.2 8引擎能力矩阵

| 引擎 | 核心能力 | 优势 | 适用场景 |
|------|---------|------|---------|
| **Silhouette 2026** | Roto抠像、跟踪、Paint、Mocha | 专业级边缘精度、时间稳定、节点图自动化 | 最终蒙版精修、复杂转场跟踪 |
| **Blender (Libmv)** | 摄像机跟踪、平面跟踪、运动解算 | 免费、开源、Python API完整 | 3D场景的摄像机反求 |
| **SAM2Matting** | 通用视频精细抠图 | 零样本、发丝级精度、支持半透明 | 复杂场景的AI初筛蒙版 |
| **MediaPipe Pose** | 33点人体姿态估计 | 轻量、快速、实时 | 快速关节点检测、运动幅度适中场景 |
| **MediaPipe Face Mesh** | 468点面部网格 | 轻量、快速、3D面部 | 快速面部对齐、基础表情 |
| **DWPose** | 高精度人体姿态估计 | YOLO基础、快速运动鲁棒 | 动作幅度大、快速运动场景 |
| **InsightFace** | 高精度面部关键点 | 侧脸/遮挡鲁棒、精度高 | 精细面部木偶化、侧脸场景 |
| **OpenFace** | 面部动作单元(AU)提取 | 学术级、AU参数完整 | 精细表情映射、面部动画 |
| **COLMAP** | 三维重建、相机位姿估计 | 精度极高、支持大运动/广角 | 复杂镜头、3D深度场景 |

---

## 二、各步骤技术详解

### 步骤1：AI蒙版生成（双模型融合）

**引擎**：SAM2Matting + RVM（来自Phase 1）

#### 1.1 双模型融合策略

```
视频帧 ──→ SAM2Matting ──→ 精细但可能闪烁的Alpha
  │
  └──→ RVM ────────────→ 时序稳定但边缘略粗糙的Alpha
                              │
                              ▼
                        ┌──────────┐
                        │ 融合算法 │ → 最终Alpha
                        └──────────┘
```

**融合策略**：
- 低频区域（边缘以外）：使用RVM结果（时序更稳定）
- 边缘区域（Alpha 0.05-0.95）：使用SAM2Matting结果（精度更高）
- 过渡区域：加权融合，边缘越靠近 SAM权重越高
- 时序平滑：对融合结果做时间域的轻度平滑，减少闪烁

#### 1.2 核心实现

```python
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class MatteFusionConfig:
    """蒙版融合配置"""
    edge_width: int = 10          # 边缘宽度（像素）
    sam_weight_edge: float = 0.9  # 边缘处SAM权重
    sam_weight_inner: float = 0.1 # 内部SAM权重
    temporal_smooth: int = 3      # 时序平滑帧数
    min_alpha: float = 0.05       # 边缘下限
    max_alpha: float = 0.95       # 边缘上限

@dataclass
class MatteFusionResult:
    """融合结果"""
    output_dir: str
    total_frames: int
    processing_time: float
    edge_quality: float
    temporal_stability: float
    fusion_method: str

class MatteFusion:
    """双模型蒙版融合器"""
    
    def __init__(self, config: MatteFusionConfig = None):
        self.config = config or MatteFusionConfig()
    
    def fuse(self, sam_alpha_dir: str,
              rvm_alpha_dir: str,
              output_dir: str) -> MatteFusionResult:
        """
        融合SAM2和RVM的蒙版
        
        Args:
            sam_alpha_dir: SAM2Matting的Alpha序列目录
            rvm_alpha_dir: RVM的Alpha序列目录
            output_dir: 输出目录
        """
        import time
        start_time = time.time()
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        sam_files = sorted(Path(sam_alpha_dir).glob("*.png"))
        rvm_files = sorted(Path(rvm_alpha_dir).glob("*.png"))
        
        # 对齐文件数量
        min_frames = min(len(sam_files), len(rvm_files))
        
        edge_qualities = []
        stability_scores = []
        prev_fused = None
        
        for i in range(min_frames):
            sam_alpha = cv2.imread(str(sam_files[i]), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
            rvm_alpha = cv2.imread(str(rvm_files[i]), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
            
            # 融合
            fused = self._fuse_single(sam_alpha, rvm_alpha)
            
            # 时序平滑
            if prev_fused is not None:
                fused = 0.7 * fused + 0.3 * prev_fused
            
            # 保存
            output_path = Path(output_dir) / f"fused_alpha_{i:06d}.png"
            cv2.imwrite(str(output_path), (fused * 255).astype(np.uint8))
            
            # 质量评估
            edge_q = self._evaluate_edge_quality(fused)
            edge_qualities.append(edge_q)
            
            if prev_fused is not None:
                stability = 1.0 - np.mean(np.abs(fused - prev_fused))
                stability_scores.append(stability)
            
            prev_fused = fused.copy()
        
        processing_time = time.time() - start_time
        
        return MatteFusionResult(
            output_dir=output_dir,
            total_frames=min_frames,
            processing_time=processing_time,
            edge_quality=float(np.mean(edge_qualities)),
            temporal_stability=float(np.mean(stability_scores)) if stability_scores else 0.0,
            fusion_method="weighted_edge_based",
        )
    
    def _fuse_single(self, sam_alpha: np.ndarray,
                     rvm_alpha: np.ndarray) -> np.ndarray:
        """单帧融合"""
        # 计算边缘权重图（基于RVM的梯度，边缘更信任SAM）
        grad_x = cv2.Sobel(rvm_alpha, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(rvm_alpha, cv2.CV_32F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        
        # 归一化梯度作为权重
        weight = np.clip(gradient_magnitude * 10, 0, 1)
        
        # 边缘区域权重高（SAM更好），内部权重低（RVM更稳定）
        sam_weight = (self.config.sam_weight_inner + 
                     (self.config.sam_weight_edge - self.config.sam_weight_inner) * weight)
        rvm_weight = 1.0 - sam_weight
        
        # 加权融合
        fused = sam_alpha * sam_weight + rvm_alpha * rvm_weight
        
        return np.clip(fused, 0, 1)
    
    def _evaluate_edge_quality(self, alpha: np.ndarray) -> float:
        """评估边缘质量"""
        grad_x = cv2.Sobel(alpha, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(alpha, cv2.CV_32F, 0, 1, ksize=3)
        gradient = np.sqrt(grad_x**2 + grad_y**2)
        
        edge_mask = (alpha > 0.05) & (alpha < 0.95)
        if np.sum(edge_mask) == 0:
            return 0.5
        
        avg_edge_grad = np.mean(gradient[edge_mask])
        quality = min(1.0, max(0.0, avg_edge_grad / 0.1))
        return float(quality)
```

---

### 步骤2：Silhouette 边缘精修（Python API自动化）

**引擎**：Silhouette 2026 内置 fx Python API

#### 2.1 自动化Roto流程

```
输入：融合Alpha序列 + 人物bbox + 镜头列表
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. 创建Silhouette项目与会话              │
│    → 创建新工程                          │
│    → 导入素材序列                        │
│    → 创建Source节点                      │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 2. 批量导入AI蒙版为Roto节点初始形状       │
│    → 创建RotoNode                        │
│    → 将AI蒙版导入为形状（逐帧）           │
│    → 设置前景/背景输入                   │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 3. 关键帧自动优化                        │
│    → 每10帧设置一个关键帧                 │
│    → 自动减少形状顶点数（简化路径）        │
│    → 应用时间平滑                        │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 4. 跟踪节点联动优化                      │
│    → 创建TrackerNode                     │
│    → 自动选择特征点                      │
│    → 将跟踪数据应用到Roto形状             │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 5. 输出多通道EXR                         │
│    → 创建OutputNode                      │
│    → 设置EXR输出格式                     │
│    → 输出Alpha / RGB蒙版 / 深度等通道     │
└─────────────────────────────────────────┘
```

#### 2.2 Silhouette Python脚本模板

```python
# Silhouette fx 模块脚本（在Silhouette内置Python环境中运行）
# 注意：此脚本必须在Silhouette的Script Editor或Actions中执行

import fx
import os
from pathlib import Path

def create_roto_project(footage_path: str,
                         alpha_dir: str,
                         output_path: str,
                         project_name: str = "AutoRoto"):
    """
    自动化创建Roto项目
    
    Args:
        footage_path: 原视频/序列路径
        alpha_dir: AI生成的Alpha序列目录
        output_path: 输出EXR路径
        project_name: 项目名称
    """
    
    # 1. 创建新项目
    project = fx.Project()
    project.setName(project_name)
    
    # 创建会话
    session = fx.Session()
    project.addItem(session)
    
    # 2. 创建Source节点（输入素材）
    source = fx.SourceNode()
    source.setProperty("path", footage_path)
    session.addNode(source)
    
    # 3. 创建Roto节点
    roto = fx.RotoNode()
    session.addNode(roto)
    
    # 连接：source.outputs[0] → roto.inputs[1] (foreground)
    # 注意：RotoNode的foreground是index 1，不是0！
    source.outputs[0].connect(roto.inputs[1])
    
    # 4. 导入AI蒙版为形状
    alpha_files = sorted(Path(alpha_dir).glob("*.png"))
    
    if alpha_files:
        # 获取形状层
        shapes_layer = roto.getProperty("shapes")
        
        # 创建一个新形状（基于首帧Alpha）
        first_alpha_path = str(alpha_files[0])
        
        # 导入蒙版为形状
        shape = fx.Object("Shape")
        shape.setProperty("name", "AI_Roto_Shape")
        shapes_layer.addObject(shape)
        
        # 设置首帧形状（实际中需要从Alpha提取轮廓）
        # 这里简化：使用Silhouette的B样条自动拟合
        shape.setProperty("spline", self._alpha_to_spline(first_alpha_path))
        
        # 5. 为其他帧添加关键帧（简化：每隔N帧添加）
        keyframe_interval = 10
        for i in range(keyframe_interval, len(alpha_files), keyframe_interval):
            frame = i
            alpha_path = str(alpha_files[i])
            
            # 设置该帧的形状
            # 实际中需要从Alpha提取轮廓并设置为关键帧
            # shape.setValue("spline", self._alpha_to_spline(alpha_path), frame)
            pass
    
    # 6. 可选：添加跟踪节点
    tracker = fx.TrackerNode()
    session.addNode(tracker)
    
    source.outputs[0].connect(tracker.inputs[0])
    
    # 自动添加跟踪点（基于运动检测）
    # tracker_points = auto_detect_tracking_points(source)
    # for point in tracker_points:
    #     tracker.addTracker(point)
    
    # 7. 创建Output节点
    output = fx.OutputNode()
    output.setProperty("path", output_path)
    output.setProperty("format", "exr")
    output.setProperty("channels", "rgba")
    session.addNode(output)
    
    roto.outputs[0].connect(output.inputs[0])
    
    # 8. 执行渲染（输出蒙版）
    output.render()
    
    return project

def _alpha_to_spline(alpha_path: str) -> list:
    """
    从Alpha图提取轮廓点（简化版）
    实际中需要OpenCV的findContours + 简化算法
    """
    import cv2
    import numpy as np
    
    alpha = cv2.imread(alpha_path, cv2.IMREAD_GRAYSCALE)
    _, binary = cv2.threshold(alpha, 128, 255, cv2.THRESH_BINARY)
    
    contours, _ = cv2.findContours(
        binary, 
        cv2.RETR_EXTERNAL, 
        cv2.CHAIN_APPROX_SIMPLE
    )
    
    if contours:
        # 取最大轮廓
        largest_contour = max(contours, key=cv2.contourArea)
        
        # 简化轮廓
        epsilon = 0.005 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)
        
        # 转换为Silhouette的spline格式
        spline_points = []
        for point in approx:
            x, y = point[0]
            spline_points.append([float(x), float(y)])
        
        return spline_points
    
    return []

# 执行
if __name__ == "__main__":
    result = create_roto_project(
        footage_path="/path/to/footage.####.exr",
        alpha_dir="/path/to/ai_alpha/",
        output_path="/path/to/output/roto_####.exr",
    )
```

#### 2.3 避坑指南

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `Property` 第二个参数必须是字符串 | Silhouette 2026 API变更 | 使用 `object.setProperty("name", value)` 而非索引 |
| `Object` 不能直接实例化 | API限制 | 使用 `createObject()` 工厂方法 |
| RotoNode输入索引错误 | foreground是index 1 | `src.outputs[0].connect(roto.inputs[1])` |
| 脚本执行失败 | AE有模态对话框 | 执行前关闭所有AE/Silhouette模态窗口 |
| 端口source属性只读 | 不能直接赋值 | 使用 `connect()` 方法连接节点 |

---

### 步骤3：人体姿态估计（双模型切换）

**引擎**：MediaPipe Pose + DWPose

#### 3.1 模型选择策略

```
输入视频帧 + 人物bbox
    │
    ▼
┌─────────────────────┐
│ 运动幅度检测         │
│ (计算帧间bbox位移)   │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
低/中运动      高运动
    │             │
    ▼             ▼
MediaPipe     DWPose
Pose          (高精度)
(快速)
    │             │
    └──────┬──────┘
           │
           ▼
   统一格式输出 (17/33关键点)
```

#### 3.2 MediaPipe Pose 核心实现

```python
import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Keypoint:
    """关键点"""
    x: float          # 归一化x坐标 (0-1)
    y: float          # 归一化y坐标 (0-1)
    z: float = 0.0    # 深度（MediaPipe支持）
    confidence: float = 1.0
    visibility: float = 1.0

@dataclass
class PoseResult:
    """姿态估计结果"""
    keypoints: List[Keypoint]  # 33点（MediaPipe）或17点（COCO）
    landmarks_3d: List[Keypoint] = None
    pose_detected: bool = False
    detection_confidence: float = 0.0

@dataclass
class PoseFrame:
    """单帧姿态数据"""
    frame_index: int
    timestamp: float
    poses: List[PoseResult]

class MediaPipePoseEstimator:
    """MediaPipe人体姿态估计器"""
    
    # MediaPipe 33个关键点名称
    LANDMARK_NAMES = [
        "nose", "left_eye_inner", "left_eye", "left_eye_outer",
        "right_eye_inner", "right_eye", "right_eye_outer",
        "left_ear", "right_ear", "mouth_left", "mouth_right",
        "left_shoulder", "right_shoulder",
        "left_elbow", "right_elbow",
        "left_wrist", "right_wrist",
        "left_pinky", "right_pinky",
        "left_index", "right_index",
        "left_thumb", "right_thumb",
        "left_hip", "right_hip",
        "left_knee", "right_knee",
        "left_ankle", "right_ankle",
        "left_heel", "right_heel",
        "left_foot_index", "right_foot_index",
    ]
    
    # 关节连接关系（用于可视化）
    CONNECTIONS = [
        (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
        (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
        (11, 23), (12, 24), (23, 24),
        (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
        (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
    ]
    
    def __init__(self, model_complexity: int = 1,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5,
                 static_image_mode: bool = False):
        import mediapipe as mp
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            static_image_mode=static_image_mode,
        )
    
    def estimate(self, frame: np.ndarray) -> PoseResult:
        """估计单帧姿态"""
        # MediaPipe需要RGB格式
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(frame_rgb)
        
        if not results.pose_landmarks:
            return PoseResult(keypoints=[], pose_detected=False)
        
        # 提取2D关键点
        keypoints = []
        for landmark in results.pose_landmarks.landmark:
            keypoints.append(Keypoint(
                x=landmark.x,
                y=landmark.y,
                z=landmark.z,
                confidence=landmark.visibility,
                visibility=landmark.visibility,
            ))
        
        # 提取3D关键点（如果有）
        landmarks_3d = []
        if results.pose_world_landmarks:
            for landmark in results.pose_world_landmarks.landmark:
                landmarks_3d.append(Keypoint(
                    x=landmark.x,
                    y=landmark.y,
                    z=landmark.z,
                    confidence=landmark.visibility,
                    visibility=landmark.visibility,
                ))
        
        return PoseResult(
            keypoints=keypoints,
            landmarks_3d=landmarks_3d,
            pose_detected=True,
            detection_confidence=np.mean([k.confidence for k in keypoints]),
        )
    
    def estimate_video(self, video_path: str,
                       sample_fps: float = 15.0,
                       person_box: List = None) -> List[PoseFrame]:
        """处理视频"""
        cap = cv2.VideoCapture(video_path)
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        sample_interval = max(1, int(video_fps / sample_fps))
        
        pose_frames = []
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx % sample_interval == 0:
                # 如果有人物框，裁剪后检测
                if person_box and len(person_box) >= 4:
                    x1, y1, x2, y2 = map(int, person_box)
                    # 扩展边界
                    pad_w = int((x2 - x1) * 0.2)
                    pad_h = int((y2 - y1) * 0.1)
                    x1 = max(0, x1 - pad_w)
                    y1 = max(0, y1 - pad_h)
                    x2 = min(frame.shape[1], x2 + pad_w)
                    y2 = min(frame.shape[0], y2 + pad_h)
                    cropped = frame[y1:y2, x1:x2]
                    
                    pose_result = self.estimate(cropped)
                    
                    # 将坐标映射回原图
                    h, w = y2 - y1, x2 - x1
                    for kp in pose_result.keypoints:
                        kp.x = (kp.x * w + x1) / frame.shape[1]
                        kp.y = (kp.y * h + y1) / frame.shape[0]
                else:
                    pose_result = self.estimate(frame)
                
                pose_frames.append(PoseFrame(
                    frame_index=frame_idx,
                    timestamp=frame_idx / video_fps,
                    poses=[pose_result] if pose_result.pose_detected else [],
                ))
            
            frame_idx += 1
        
        cap.release()
        return pose_frames
    
    def close(self):
        """释放资源"""
        self.pose.close()
```

#### 3.3 DWPose 高精度姿态估计

```python
class DWPoseEstimator:
    """
    DWPose高精度人体姿态估计器
    基于YOLO的姿态估计，快速运动场景精度更高
    """
    
    # COCO 17个关键点
    COCO_KEYPOINTS = [
        "nose", "left_eye", "right_eye", "left_ear", "right_ear",
        "left_shoulder", "right_shoulder",
        "left_elbow", "right_elbow",
        "left_wrist", "right_wrist",
        "left_hip", "right_hip",
        "left_knee", "right_knee",
        "left_ankle", "right_ankle",
    ]
    
    # MediaPipe 33点 → COCO 17点 映射
    MP_TO_COCO_MAP = {
        0: 0,    # nose
        2: 1,    # left_eye
        5: 2,    # right_eye
        7: 3,    # left_ear
        8: 4,    # right_ear
        11: 5,   # left_shoulder
        12: 6,   # right_shoulder
        13: 7,   # left_elbow
        14: 8,   # right_elbow
        15: 9,   # left_wrist
        16: 10,  # right_wrist
        23: 11,  # left_hip
        24: 12,  # right_hip
        25: 13,  # left_knee
        26: 14,  # right_knee
        27: 15,  # left_ankle
        28: 16,  # right_ankle
    }
    
    def __init__(self, model_path: str = "dwpose_l.pt",
                 device: str = "cuda",
                 conf_threshold: float = 0.5):
        """
        初始化DWPose
        
        实际使用需要安装dwpose库或使用ultralytics YOLO pose
        """
        self.device = device
        self.conf_threshold = conf_threshold
        
        # 使用ultralytics的YOLOv8-pose作为替代
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
        except ImportError:
            self.model = None
    
    def estimate(self, frame: np.ndarray) -> PoseResult:
        """估计单帧姿态"""
        if self.model is None:
            return PoseResult(keypoints=[], pose_detected=False)
        
        results = self.model.predict(
            frame,
            conf=self.conf_threshold,
            device=self.device,
            verbose=False,
        )
        
        poses = []
        for result in results:
            if result.keypoints is not None:
                for kpts in result.keypoints.data:
                    keypoints = []
                    for kp in kpts:
                        x, y, conf = kp.cpu().numpy()
                        h, w = frame.shape[:2]
                        keypoints.append(Keypoint(
                            x=float(x) / w,
                            y=float(y) / h,
                            confidence=float(conf),
                            visibility=float(conf),
                        ))
                    
                    poses.append(PoseResult(
                        keypoints=keypoints,
                        pose_detected=True,
                        detection_confidence=float(result.boxes.conf[0]) if result.boxes else 0.5,
                    ))
        
        return poses[0] if poses else PoseResult(keypoints=[], pose_detected=False)
    
    def convert_to_mediapipe_format(self, coco_keypoints: List[Keypoint]) -> List[Keypoint]:
        """将COCO 17点转换为MediaPipe 33点格式（插值填充）"""
        mp_keypoints = [None] * 33
        
        # 填充已知点
        for mp_idx, coco_idx in self.MP_TO_COCO_MAP.items():
            if coco_idx < len(coco_keypoints):
                mp_keypoints[mp_idx] = coco_keypoints[coco_idx]
        
        # 插值填充缺失的点（简单线性插值）
        # 实际中需要更复杂的插值
        for i in range(33):
            if mp_keypoints[i] is None:
                # 找最近的已知点
                # 简化：用0填充
                mp_keypoints[i] = Keypoint(x=0.5, y=0.5, confidence=0.0)
        
        return mp_keypoints
```

#### 3.4 双模型融合与自适应切换

```python
class AdaptivePoseEstimator:
    """自适应姿态估计器（双模型切换）"""
    
    def __init__(self, motion_threshold: float = 50.0):
        """
        Args:
            motion_threshold: 运动幅度阈值（像素/帧）
        """
        self.mediapipe_estimator = MediaPipePoseEstimator(
            model_complexity=1,
        )
        self.dwpose_estimator = DWPoseEstimator()
        self.motion_threshold = motion_threshold
        self.prev_bbox = None
    
    def estimate(self, frame: np.ndarray,
                 person_bbox: List[float] = None) -> PoseResult:
        """
        自适应选择模型
        
        Args:
            frame: 视频帧
            person_bbox: 人物框 [x1, y1, x2, y2]
        """
        motion_level = self._estimate_motion(person_bbox)
        
        if motion_level < self.motion_threshold:
            # 低/中运动 → MediaPipe（更快）
            return self.mediapipe_estimator.estimate(frame)
        else:
            # 高运动 → DWPose（更准）
            result = self.dwpose_estimator.estimate(frame)
            # 转换为统一格式
            if result.pose_detected and len(result.keypoints) == 17:
                result.keypoints = self.dwpose_estimator.convert_to_mediapipe_format(
                    result.keypoints
                )
            return result
    
    def _estimate_motion(self, bbox: List[float]) -> float:
        """估计运动幅度（基于bbox位移）"""
        if bbox is None or self.prev_bbox is None:
            self.prev_bbox = bbox
            return 0.0
        
        # 计算中心位移
        cx1 = (bbox[0] + bbox[2]) / 2
        cy1 = (bbox[1] + bbox[3]) / 2
        cx2 = (self.prev_bbox[0] + self.prev_bbox[2]) / 2
        cy2 = (self.prev_bbox[1] + self.prev_bbox[3]) / 2
        
        displacement = np.sqrt((cx1 - cx2)**2 + (cy1 - cy2)**2)
        
        self.prev_bbox = bbox
        return displacement
```

---

### 步骤4-5：面部关键点与表情分析

**引擎**：MediaPipe Face Mesh + InsightFace + OpenFace

#### 4.1 面部关键点双模型

```python
class FaceMeshEstimator:
    """MediaPipe Face Mesh 468点面部网格"""
    
    def __init__(self, min_detection_confidence: float = 0.5):
        import mediapipe as mp
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,  # 包含虹膜点
            min_detection_confidence=min_detection_confidence,
        )
    
    def estimate(self, frame: np.ndarray):
        """估计面部关键点"""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)
        
        if not results.multi_face_landmarks:
            return None
        
        landmarks = []
        for face_landmarks in results.multi_face_landmarks:
            face_points = []
            for lm in face_landmarks.landmark:
                face_points.append(Keypoint(
                    x=lm.x,
                    y=lm.y,
                    z=lm.z,
                    confidence=1.0,
                ))
            landmarks.append(face_points)
        
        return landmarks[0] if landmarks else None

class InsightFaceEstimator:
    """InsightFace 高精度面部关键点"""
    
    def __init__(self, model_name: str = "antelopev2",
                 det_size: tuple = (640, 640)):
        from insightface.app import FaceAnalysis
        self.app = FaceAnalysis(name=model_name)
        self.app.prepare(ctx_id=0, det_size=det_size)
    
    def estimate(self, frame: np.ndarray):
        """估计面部关键点"""
        faces = self.app.get(frame)
        
        if not faces:
            return None
        
        face = faces[0]  # 取第一个
        kps = face.kps  # 5点: 左眼、右眼、鼻子、左嘴角、右嘴角
        
        # 转换为统一格式
        h, w = frame.shape[:2]
        keypoints = []
        for kp in kps:
            keypoints.append(Keypoint(
                x=kp[0] / w,
                y=kp[1] / h,
                confidence=face.det_score,
            ))
        
        return keypoints
```

#### 4.2 OpenFace 面部动作单元(AU)提取

```python
class OpenFaceAUAnalyzer:
    """
    OpenFace面部动作单元分析器
    输出AU参数，用于精细表情映射
    """
    
    def __init__(self, openface_dir: str = None):
        self.openface_dir = openface_dir
    
    def analyze_video(self, video_path: str, output_dir: str) -> dict:
        """
        分析视频中的面部动作单元
        
        返回AU时间序列数据
        """
        import subprocess
        import os
        
        # OpenFace的FeatureExtraction工具
        feature_extractor = os.path.join(
            self.openface_dir, "FeatureExtraction"
        ) if self.openface_dir else "FeatureExtraction"
        
        cmd = [
            feature_extractor,
            "-f", video_path,
            "-out_dir", output_dir,
            "-aus",           # 提取动作单元
            "-2Dlandmarks",  # 2D关键点
            "-gaze",         # 视线
            "-pose",         # 头部姿态
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            
            # 读取CSV结果
            csv_path = os.path.join(output_dir, "video_name.csv")
            au_data = self._parse_openface_csv(csv_path)
            
            return au_data
        except Exception as e:
            print(f"OpenFace分析失败: {e}")
            return {}
    
    def _parse_openface_csv(self, csv_path: str) -> dict:
        """解析OpenFace输出的CSV"""
        import pandas as pd
        
        df = pd.read_csv(csv_path)
        
        # AU列通常以AU01_r, AU02_r等开头（强度）
        # 以及AU01_c, AU02_c等（是否存在）
        au_intensity_cols = [c for c in df.columns if c.startswith("AU") and c.endswith("_r")]
        au_presence_cols = [c for c in df.columns if c.startswith("AU") and c.endswith("_c")]
        
        return {
            "frame_count": len(df),
            "timestamps": df["timestamp"].tolist() if "timestamp" in df else [],
            "au_intensities": {
                col: df[col].tolist() for col in au_intensity_cols
            },
            "au_presence": {
                col: df[col].tolist() for col in au_presence_cols
            },
            # 头部姿态
            "pose": {
                "pitch": df["pose_Tx"].tolist() if "pose_Tx" in df else [],
                "yaw": df["pose_Ty"].tolist() if "pose_Ty" in df else [],
                "roll": df["pose_Tz"].tolist() if "pose_Tz" in df else [],
            }
        }
    
    def map_au_to_puppet_expression(self, au_data: dict) -> dict:
        """
        将AU参数映射为木偶表情参数
        
        常见AU到表情的映射：
        - AU1 (内侧眉抬高) → 惊讶/悲伤
        - AU2 (外侧眉抬高) → 惊讶
        - AU4 (眉压低) → 愤怒/专注
        - AU6 (脸颊抬起) → 真笑
        - AU9 (皱鼻) → 厌恶
        - AU12 (嘴角上扬) → 笑容
        - AU15 (嘴角下压) → 悲伤
        - AU20 (嘴角拉伸) → 恐惧
        - AU25 (嘴唇分开) → 说话/惊讶
        - AU26 (下颌下降) → 惊讶/说话
        """
        # 简化的表情映射
        # 实际项目中需要更复杂的映射模型
        ...
```

---

### 步骤6：摄像机反求（3D跟踪）

**引擎**：Blender Libmv + COLMAP

#### 6.1 Blender 摄像机跟踪自动化

```python
# Blender Python脚本（在Blender内部运行）
import bpy
import os

def auto_track_camera(footage_path: str,
                      output_path: str,
                      scene_name: str = "CameraTrack"):
    """
    Blender自动摄像机跟踪
    
    Args:
        footage_path: 视频/序列路径
        output_path: 输出路径（摄像机动画数据）
    """
    
    # 1. 设置场景
    scene = bpy.context.scene
    scene.name = scene_name
    
    # 设置渲染分辨率（匹配视频）
    # ... 获取视频信息 ...
    
    # 2. 创建跟踪对象（Movie Clip）
    bpy.ops.clip.open(directory=os.path.dirname(footage_path),
                      files=[{"name": os.path.basename(footage_path)}])
    
    clip = bpy.data.movieclips[os.path.basename(footage_path)]
    
    # 3. 创建摄像机
    cam = bpy.data.cameras.new("TrackedCamera")
    cam_obj = bpy.data.objects.new("TrackedCamera", cam)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    
    # 4. 添加约束（追踪约束）
    constraint = cam_obj.constraints.new(type='FOLLOW_TRACK')
    constraint.target = clip
    constraint.track = "Camera"  # 摄像机跟踪轨迹
    
    # 5. 自动检测并跟踪特征点
    # 进入Movie Clip Editor执行跟踪
    # 实际中需要调用跟踪操作
    
    # 6. 解算摄像机
    # bpy.ops.clip.solve_camera()
    
    # 7. 导出摄像机数据
    # 导出为FBX或自定义JSON格式
    
    return cam_obj

def export_camera_animation(cam_obj, output_json: str):
    """导出摄像机动画数据为JSON（供AE/Silhouette使用）"""
    import json
    
    scene = bpy.context.scene
    frame_start = scene.frame_start
    frame_end = scene.frame_end
    
    camera_data = {
        "name": cam_obj.name,
        "focal_length": cam_obj.data.lens,
        "sensor_width": cam_obj.data.sensor_width,
        "sensor_height": cam_obj.data.sensor_height,
        "frames": []
    }
    
    for frame in range(frame_start, frame_end + 1):
        scene.frame_set(frame)
        
        frame_data = {
            "frame": frame,
            "location": {
                "x": cam_obj.location.x,
                "y": cam_obj.location.y,
                "z": cam_obj.location.z,
            },
            "rotation": {
                "x": cam_obj.rotation_euler.x,
                "y": cam_obj.rotation_euler.y,
                "z": cam_obj.rotation_euler.z,
            },
            "scale": {
                "x": cam_obj.scale.x,
                "y": cam_obj.scale.y,
                "z": cam_obj.scale.z,
            },
        }
        camera_data["frames"].append(frame_data)
    
    with open(output_json, "w") as f:
        json.dump(camera_data, f, indent=2)
```

#### 6.2 COLMAP 复杂场景三维重建

```python
class COLMAPReconstructor:
    """COLMAP三维重建与摄像机位姿估计"""
    
    def __init__(self, colmap_path: str = "colmap"):
        self.colmap_path = colmap_path
    
    def reconstruct(self, image_dir: str,
                    output_dir: str,
                    camera_model: str = "OPENCV"):
        """
        从图像序列进行三维重建
        
        Args:
            image_dir: 抽帧图像目录
            output_dir: 输出目录
            camera_model: 摄像机模型
        """
        import subprocess
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 步骤1：特征提取
        self._feature_extractor(image_dir, output_dir, camera_model)
        
        # 步骤2：特征匹配
        self._feature_matcher(output_dir)
        
        # 步骤3：增量式重建
        self._mapper(image_dir, output_dir)
        
        # 步骤4：导出结果
        # 输出摄像机位姿、点云等
    
    def _feature_extractor(self, image_dir: str, output_dir: str,
                           camera_model: str):
        """特征提取"""
        database_path = os.path.join(output_dir, "database.db")
        
        cmd = [
            self.colmap_path, "feature_extractor",
            "--database_path", database_path,
            "--image_path", image_dir,
            "--ImageReader.camera_model", camera_model,
            "--SiftExtraction.use_gpu", "1",
        ]
        
        subprocess.run(cmd, check=True)
    
    def _feature_matcher(self, output_dir: str):
        """特征匹配"""
        database_path = os.path.join(output_dir, "database.db")
        
        cmd = [
            self.colmap_path, "exhaustive_matcher",
            "--database_path", database_path,
            "--SiftMatching.use_gpu", "1",
        ]
        
        subprocess.run(cmd, check=True)
    
    def _mapper(self, image_dir: str, output_dir: str):
        """增量式重建"""
        database_path = os.path.join(output_dir, "database.db")
        sparse_dir = os.path.join(output_dir, "sparse")
        os.makedirs(sparse_dir, exist_ok=True)
        
        cmd = [
            self.colmap_path, "mapper",
            "--database_path", database_path,
            "--image_path", image_dir,
            "--output_path", sparse_dir,
        ]
        
        subprocess.run(cmd, check=True)
    
    def get_camera_poses(self, output_dir: str) -> dict:
        """获取摄像机位姿（转换为可用于Blender/AE的格式）"""
        # 读取COLMAP输出的cameras.txt和images.txt
        # 转换为统一格式
        ...
```

---

### 步骤7：数据融合与格式转换

#### 7.1 统一跟踪数据格式

```python
{
  "tracking_data": {
    "version": "2.0",
    "video_info": {
      "width": 1920,
      "height": 1080,
      "fps": 30,
      "total_frames": 1800
    },
    
    // 人体姿态（33点 MediaPipe 格式）
    "pose": {
      "model": "mediapipe_pose",
      "keypoint_names": ["nose", "left_eye", ...],
      "connections": [[0, 1], [1, 2], ...],
      "frames": [
        {
          "frame": 0,
          "timestamp": 0.0,
          "person_id": 0,
          "keypoints": [
            {"x": 0.5, "y": 0.3, "confidence": 0.95},
            ...
          ]
        }
      ]
    },
    
    // 面部关键点（468点）
    "face": {
      "model": "mediapipe_facemesh",
      "num_landmarks": 468,
      "frames": [...]
    },
    
    // 面部动作单元
    "facial_aus": {
      "model": "openface",
      "aus": ["AU01_r", "AU02_r", ...],
      "frames": [...]
    },
    
    // 摄像机跟踪（3D）
    "camera": {
      "model": "blender_libmv",
      "focal_length": 50.0,
      "sensor_width": 36.0,
      "frames": [
        {
          "frame": 0,
          "location": [0.0, 0.0, 5.0],
          "rotation": [0.0, 0.0, 0.0],
          "fov": 39.6
        }
      ]
    },
    
    // 蒙版序列路径
    "matte": {
      "method": "sam2+rvm+fused+silhouette",
      "alpha_sequence": "/path/to/alpha/",
      "exr_sequence": "/path/to/exr/",
      "quality_score": 0.92
    }
  }
}
```

---

## 三、输出到Phase 3的标准接口

```python
{
  "phase2_output": {
    // 素材路径
    "video_path": "/path/to/enhanced.mp4",
    "matte_exr_path": "/path/to/silhouette_output/",
    "matte_alpha_path": "/path/to/fused_alpha/",
    
    // 跟踪数据
    "tracking_data": {
      "pose": {...},      // 人体姿态
      "face": {...},      // 面部关键点
      "face_aus": {...},  // 表情AU参数
      "camera": {...},    // 摄像机位姿
    },
    
    // 镜头列表
    "scenes": [...],
    
    // 质量报告
    "quality_report": {
      "matte_quality": 0.91,
      "pose_tracking_stability": 0.88,
      "face_detection_rate": 0.95,
      "camera_solve_error": 0.5,  // 像素
      "overall": 0.89
    },
    
    // 可用的AE/Silhouette脚本
    "ae_scripts": {
      "import_matte": "/path/to/import_matte.jsx",
      "import_pose": "/path/to/pose_to_nulls.jsx",
      "import_face": "/path/to/face_morph.jsx",
    }
  }
}
```

---

> **关联文档**：
> - [[Phase 1 预处理全链路技术详解]]
> - [[Phase 3 风格化全链路详解]]
> - [[Silhouette Python API开发指南]]
> - [[CV计算机视觉深度研究报告]]