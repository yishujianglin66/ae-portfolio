#!/usr/bin/env python3
"""
Hierarchical Camera Motion Classifier (3-class: static/zoom/tilt-orbit)

Architecture:
    Layer 1: CNN 2-class classifier (static vs motion, 0.67, CPU ~1-2s)
    Layer 2: VLM expert model (zoom vs tilt-orbit, ~3s, GPU)

Usage:
    python camera_classifier_hierarchical.py <video_path> [--device cuda]

Output:
    - prediction: "static", "zoom", or "tilt-orbit"
    - confidence: 0.0-1.0
    - method: "cnn" or "vlm"
    - description: Camera motion description (if VLM used)

Performance:
    - static: ~1-2s (CNN only)
    - zoom/tilt-orbit: ~4-5s (CNN + VLM)
    - Expected 3-class bal_acc: 0.50-0.60
"""

import argparse
import sys
import time
from pathlib import Path

# Add models directory to path
sys.path.insert(0, str(Path(__file__).parent))

from camera_classifier_2class import CameraClassifier2Class


class HierarchicalCameraClassifier:
    """Hierarchical 3-class camera motion classifier"""
    
    def __init__(self, cnn_model_path=None, vlm_model_name=None, device='cuda'):
        """
        Args:
            cnn_model_path: Path to 2-class CNN model (.pt)
            vlm_model_name: HuggingFace model name for VLM expert
            device: 'cpu' or 'cuda'
        """
        self.device = device
        
        # Layer 1: 2-class CNN classifier
        print("Initializing Layer 1: 2-class CNN classifier...")
        self.cnn_classifier = CameraClassifier2Class(
            model_path=cnn_model_path,
            device='cpu',  # CNN runs on CPU
            img_size=128,
            n_frames=8
        )
        
        # Layer 2: VLM expert (lazy loading)
        self.vlm_model_name = vlm_model_name or "chancharikm/qwen2.5-vl-7b-cam-motion"
        self.vlm_expert = None
        self._vlm_loaded = False
    
    def _load_vlm(self):
        """Lazy load VLM expert model with graceful degradation."""
        if not self._vlm_loaded:
            print(f"Initializing Layer 2: VLM expert model ({self.vlm_model_name})...")
            try:
                from vlm_expert_3class import VLMExpertModel
                self.vlm_expert = VLMExpertModel(
                    model_name=self.vlm_model_name,
                    device=self.device
                )
                self._vlm_loaded = True
            except Exception as e:
                print(f"VLM load failed, falling back to 2-class mode: {e}")
                self.vlm_expert = None
                self._vlm_loaded = False
    
    def predict(self, video_path, use_vlm=True):
        """
        Predict camera motion type (3-class)
        
        Args:
            video_path: Path to video file
            use_vlm: If True, use VLM for motion samples; else return 2-class
        
        Returns:
            (prediction, confidence, method, description)
        """
        # Layer 1: 2-class classification
        pred_2class, conf_2class, method_2class = self.cnn_classifier.predict(
            video_path, use_cnn=True
        )
        
        # If static, return immediately
        if pred_2class == 'static':
            return 'static', conf_2class, 'cnn', 'Static camera (no motion detected)'
        
        # If motion and VLM enabled, use VLM for fine-grained classification
        if use_vlm and not self._vlm_loaded:
            self._load_vlm()
        
        if use_vlm and self._vlm_loaded:
            
            pred_3class, conf_3class, description = self.vlm_expert.classify_motion(
                video_path
            )
            
            # Combine confidences
            final_conf = conf_2class * conf_3class
            
            return pred_3class, final_conf, 'vlm', description
        else:
            # VLM not available, return motion without fine-grained classification
            return 'motion', conf_2class, 'cnn', 'Motion detected (VLM not loaded)'


def main():
    parser = argparse.ArgumentParser(description='Hierarchical 3-class camera motion classifier')
    parser.add_argument('video_path', type=str, help='Path to video file')
    parser.add_argument('--cnn-model', type=str, 
                        default='models/camera_classifier/d2_cnn_2class_best.pt',
                        help='Path to 2-class CNN model')
    parser.add_argument('--vlm-model', type=str,
                        default='chancharikm/qwen2.5-vl-7b-cam-motion',
                        help='VLM expert model name')
    parser.add_argument('--device', type=str, default='cuda',
                        help='Device for VLM: cpu or cuda')
    parser.add_argument('--no-vlm', action='store_true',
                        help='Disable VLM (2-class only)')
    
    args = parser.parse_args()
    
    # Initialize hierarchical classifier
    classifier = HierarchicalCameraClassifier(
        cnn_model_path=args.cnn_model,
        vlm_model_name=args.vlm_model,
        device=args.device
    )
    
    # Predict
    start_time = time.time()
    pred, conf, method, desc = classifier.predict(
        args.video_path,
        use_vlm=not args.no_vlm
    )
    elapsed = time.time() - start_time
    
    # Output
    print(f"\nPrediction: {pred}")
    print(f"Confidence: {conf:.3f}")
    print(f"Method: {method}")
    print(f"Description: {desc}")
    print(f"Time: {elapsed:.2f}s")
    
    return pred, conf, method, desc


if __name__ == '__main__':
    main()
