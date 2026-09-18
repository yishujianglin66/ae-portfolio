#!/usr/bin/env python3
"""
2-class Camera Motion Classifier (static vs motion)

Usage:
    python camera_classifier_2class.py <video_path> [--threshold-fallback]

Output:
    - prediction: "static" or "motion"
    - confidence: 0.0-1.0
    - method: "cnn" or "threshold"

Performance:
    - CNN: bal_acc=0.6725, 0.5M params, CPU ~1-2 sec/video
    - Threshold: bal_acc=0.6615, zero training, CPU ~0.5 sec/video

Note:
    0.67 is the label noise ceiling (VLM 2-class noise rate 25.7%),
    not a model capability limit. Further improvement requires label denoising.
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn

from core.torch_runtime import infer_ctx


class SmallMotionCNN(nn.Module):
    """4-layer CNN for motion classification (static vs motion)"""
    def __init__(self):
        super().__init__()
        self.feat = nn.Sequential(
            nn.Conv2d(3, 32, 3, 2, 1), nn.BatchNorm2d(32), nn.ReLU(),
            nn.Conv2d(32, 64, 3, 2, 1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.Conv2d(64, 128, 3, 2, 1), nn.BatchNorm2d(128), nn.ReLU(),
            nn.Conv2d(128, 256, 3, 2, 1), nn.BatchNorm2d(256), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Sequential(nn.Dropout(0.3), nn.Linear(256, 2))
    
    def forward(self, x):
        return self.head(self.feat(x).flatten(1))


class CameraClassifier2Class:
    """2-class camera motion classifier (static vs motion)"""
    
    def __init__(self, model_path=None, device='cpu', img_size=128, n_frames=8):
        """
        Args:
            model_path: Path to CNN model weights (.pt)
            device: 'cpu' or 'cuda'
            img_size: Input image size (default 128)
            n_frames: Number of frames to sample (default 8)
        """
        self.device = device
        self.img_size = img_size
        self.n_frames = n_frames
        self.model = None
        
        if model_path and Path(model_path).exists():
            self.load_model(model_path)
    
    def load_model(self, model_path):
        """Load CNN model weights"""
        self.model = SmallMotionCNN().to(self.device)
        state_dict = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()
        print(f"Loaded CNN model from {model_path}")
    
    def extract_frames(self, video_path, n_frames=8):
        """Extract evenly spaced frames from video"""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < n_frames:
            # If video too short, duplicate frames
            frames = []
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
            while len(frames) < n_frames:
                frames.append(frames[-1])
            cap.release()
            return frames[:n_frames]
        
        # Sample evenly
        indices = np.linspace(0, total_frames - 1, n_frames, dtype=int)
        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        
        cap.release()
        
        # Pad if needed
        while len(frames) < n_frames:
            frames.append(frames[-1])
        
        return frames
    
    def preprocess_frames(self, frames):
        """Preprocess frames for CNN input"""
        processed = []
        for frame in frames:
            # Resize
            frame = cv2.resize(frame, (self.img_size, self.img_size))
            # BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # To float32 [0, 1]
            frame = frame.astype(np.float32) / 255.0
            # Normalize to [-1, 1]
            frame = (frame - 0.5) / 0.5
            # HWC to CHW
            frame = np.transpose(frame, (2, 0, 1))
            processed.append(frame)
        
        return np.stack(processed)  # (N, C, H, W)
    
    def compute_frame_diffs(self, frames_tensor):
        """Compute absolute frame differences"""
        # frames_tensor: (N, C, H, W)
        diffs = np.abs(frames_tensor[1:] - frames_tensor[:-1])  # (N-1, C, H, W)
        return diffs
    
    def predict_cnn(self, video_path):
        """Predict using CNN model"""
        if self.model is None:
            raise ValueError("CNN model not loaded")
        
        # Extract and preprocess frames
        frames = self.extract_frames(video_path, self.n_frames)
        frames_tensor = self.preprocess_frames(frames)
        
        # Compute frame diffs
        diffs = self.compute_frame_diffs(frames_tensor)  # (7, 3, 128, 128)
        
        # Average diffs as input
        avg_diff = diffs.mean(axis=0, keepdims=True)  # (1, 3, 128, 128)
        
        # To tensor
        input_tensor = torch.from_numpy(avg_diff).float().to(self.device)
        
        # Inference
        with infer_ctx(self.device):
            output = self.model(input_tensor)
            probs = torch.softmax(output, dim=1)[0]
            pred_idx = probs.argmax().item()
            confidence = probs[pred_idx].item()
        
        labels = ['static', 'motion']
        return labels[pred_idx], confidence
    
    def predict_threshold(self, video_path, threshold=0.015):
        """
        Predict using frame difference threshold (fallback method)
        
        Threshold 0.015 was empirically determined (original 0.6615 bal_acc).
        This is a zero-training baseline.
        """
        frames = self.extract_frames(video_path, self.n_frames)
        frames_tensor = self.preprocess_frames(frames)
        diffs = self.compute_frame_diffs(frames_tensor)
        
        # Mean absolute difference
        mean_diff = diffs.mean()
        
        if mean_diff > threshold:
            return 'motion', min(0.99, 0.5 + mean_diff * 10)
        else:
            return 'static', min(0.99, 0.5 + (threshold - mean_diff) * 10)
    
    def predict(self, video_path, use_cnn=True):
        """
        Predict camera motion type
        
        Args:
            video_path: Path to video file
            use_cnn: If True and model loaded, use CNN; else use threshold
        
        Returns:
            (prediction, confidence, method)
        """
        if use_cnn and self.model is not None:
            pred, conf = self.predict_cnn(video_path)
            return pred, conf, 'cnn'
        else:
            pred, conf = self.predict_threshold(video_path)
            return pred, conf, 'threshold'


def main():
    parser = argparse.ArgumentParser(description='2-class camera motion classifier')
    parser.add_argument('video_path', type=str, help='Path to video file')
    parser.add_argument('--model', type=str, default=None, 
                        help='Path to CNN model (.pt). If not provided, uses threshold fallback.')
    parser.add_argument('--threshold-fallback', action='store_true',
                        help='Force use threshold method even if model is loaded')
    parser.add_argument('--device', type=str, default='cpu',
                        help='Device: cpu or cuda')
    
    args = parser.parse_args()
    
    # Initialize classifier
    classifier = CameraClassifier2Class(
        model_path=args.model,
        device=args.device
    )
    
    # Predict
    start_time = time.time()
    
    if args.threshold_fallback:
        pred, conf, method = classifier.predict(args.video_path, use_cnn=False)
    else:
        pred, conf, method = classifier.predict(args.video_path, use_cnn=True)
    
    elapsed = time.time() - start_time
    
    # Output
    print(f"\nPrediction: {pred}")
    print(f"Confidence: {conf:.3f}")
    print(f"Method: {method}")
    print(f"Time: {elapsed:.2f}s")
    
    return pred, conf, method


if __name__ == '__main__':
    main()
