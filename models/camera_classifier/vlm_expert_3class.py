#!/usr/bin/env python3
"""
VLM Expert Model for zoom/tilt-orbit classification

Usage:
    python vlm_expert_3class.py <video_path>

Output:
    - prediction: "zoom" or "tilt-orbit" (or "static" if no motion detected)
    - confidence: 0.0-1.0
    - description: Camera motion description from VLM

Performance:
    - ~3 seconds per video on GPU (vGPU-32GB)
    - Expected accuracy: 0.55-0.65 for zoom vs tilt-orbit

Note:
    This is the second layer of the hierarchical architecture.
    Only call on samples classified as "motion" by the 2-class classifier.
"""

import argparse
import cv2
import numpy as np
import re
import torch
from core.torch_runtime import infer_ctx
from pathlib import Path
import sys
import time
import json

# Set HF mirror
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_XET"] = "1"

# --- Output parsing rules (verb-conjugation aware, per F2/F3 spec) ---
# Negation/minimizer phrases are stripped before motion detection so that
# "no movement" / "minimal shaking" never trigger the motion regexes.
_NEGATION_RE = re.compile(
    r"\b(?:no|minimal|little|without|hardly\s+any|barely\s+any)\s+"
    r"(?:camera\s+)?(?:movement|motion|shaking)\b", re.I)
# Strong, explicit static-camera statements only. Words like "steady"/
# "still"/"smooth" describe motion quality, not absence of motion, and
# must NOT count as static evidence.
_STATIC_RE = re.compile(
    r"\b(?:static|stationary|fixed\s+camera|locked[- ]off|locked\s+camera|"
    r"camera\s+(?:does\s+not|doesn'?t)\s+move|"
    r"camera\s+(?:is|stays|remains)\s+still|"
    r"remains\s+(?:still|static|stationary|motionless)|"
    r"no\s+(?:camera\s+)?(?:movement|motion))\b", re.I)
_MOTION_RE = re.compile(
    r"\b(?:zoom(?:s|ing|ed)?|doll(?:y|ies|ying|ied)|pans?|panning|panned|"
    r"tilt(?:s|ing|ed)?|orbits?|orbiting|rotat(?:e|es|ing|ed)|"
    r"revolv(?:e|es|ing|ed)|tracks?|tracking|trucks?|trucking|"
    r"cran(?:e|es|ing|ed)|pedestals?|moves?|moving|moved|movement|"
    r"descend(?:s|ing)?|descent|ascend(?:s|ing)?|ascent)\b", re.I)
_ZOOM_RE = re.compile(
    r"\bzoom(?:s|ing|ed)?\b|\bdoll(?:y|ies|ying|ied)\b|"
    r"\bpush(?:es|ing)?\s+in\b|\bpull(?:s|ing)?\s+(?:out|back)\b|"
    r"\bdolly[- ]?(?:in|out|forward|backward)\b|"
    r"\b(?:gets?|getting|moves?|moving|moved)\s+(?:closer|farther)\b|"
    r"\b(?:moves?|moving|moved)\s+(?:\w+\s+)?(?:forward|back(?:ward)?)\b|"
    r"\bcloser\b|\bfarther\b", re.I)
_TILT_ORBIT_RE = re.compile(
    r"\btilt(?:s|ing|ed)?\b|\borbit(?:s|ing|ed)?\b|\barc(?:s|ing|ed)?\b|"
    r"\brotat(?:e|es|ing|ed)\b|\brevolv(?:e|es|ing|ed)\b|"
    r"\bpan(?:s|ning|ned)?\b|\btrack(?:s|ing|ed)?\b|\btruck(?:s|ing|ed)?\b|"
    r"\bcran(?:e|es|ing|ed)\b|\bpedestal(?:s|ing|ed)?\b|"
    # Directional moves: only vertical/lateral count as tilt/orbit/pan;
    # forward/backward motion is zoom evidence (handled by _ZOOM_RE).
    r"\b(?:moves?|moving|moved)\s+(?:\w+\s+)?(?:down(?:ward)?|up(?:ward)?|"
    r"left|right|sideways|laterally)\b|"
    r"\b(?:descend(?:s|ing)?|descent|ascend(?:s|ing)?|ascent)\b", re.I)


class VLMExpertModel:
    """VLM expert model for fine-grained camera motion classification"""
    
    def __init__(self, model_name="chancharikm/qwen2.5-vl-7b-cam-motion", device='cuda',
                 quantize="auto"):
        """
        Args:
            model_name: HuggingFace model name
            device: 'cpu' or 'cuda'
            quantize: 'auto' (4bit when bitsandbytes available) /
                      '4bit' (force nf4) / 'none' (full precision)
        """
        self.device = device
        self.model_name = model_name
        self.quantize = quantize if quantize in ("none", "4bit", "auto") else "auto"
        self.model = None
        self.processor = None
        
        self.load_model()
    
    def load_model(self, timeout_seconds=60):
        """Load VLM model from HuggingFace with timeout protection."""
        print(f"Loading VLM model: {self.model_name}")
        
        try:
            from transformers import Qwen2_5_VLForConditionalGeneration as model_cls
            from transformers import AutoProcessor
            
            # Set download timeout via environment
            import os
            os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = str(timeout_seconds)
            os.environ['HF_HUB_DISABLE_XET'] = '1'
            
            # Check if model is cached locally first
            from huggingface_hub import try_to_load_from_cache
            import tempfile
            model_name = self.model_name
            cached = False
            try:
                # Quick check: can we find the model in cache?
                from huggingface_hub import scan_cache_dir
                cache_info = scan_cache_dir()
                model_slug = model_name.replace('/', '--')
                for repo in cache_info.repos:
                    # repo_id uses '/' while cache dir name uses '--' slug
                    if repo.repo_id == model_name or model_slug in str(repo.repo_path):
                        cached = True
                        break
            except Exception:
                pass
            
            if not cached:
                print(f"Model not found in local cache. Use --no-vlm for 2-class mode.")
                print(f"To download: huggingface-cli download {model_name}")
                raise RuntimeError(f"VLM model {model_name} not cached locally")
            
            # Cached locally: go fully offline so from_pretrained never
            # stalls on HEAD requests for files the repo does not have
            # (e.g. single-file model.safetensors, processor_config.json).
            os.environ.setdefault('HF_HUB_OFFLINE', '1')
            os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
            
            if self.device == 'cuda' and self.quantize in ('auto', '4bit') and self._bnb_available():
                # 7B bf16 (~15GB) does not fit 8GB VRAM; load with nf4 4-bit
                # (~5-6GB), same strategy as pipeline/visual_semantic_judge.py
                try:
                    self.model = self._load_4bit(model_cls)
                except Exception as e:
                    if self.quantize == '4bit':
                        raise
                    print(f"4bit load failed ({e}), falling back to device_map='auto'")
                    self.model = model_cls.from_pretrained(
                        self.model_name,
                        torch_dtype=torch.bfloat16,
                        device_map='auto',
                    )
            elif self.device == 'cuda':
                try:
                    self.model = model_cls.from_pretrained(
                        self.model_name,
                        torch_dtype=torch.bfloat16,
                        device_map='cuda',
                    )
                except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
                    print(f"bf16 GPU load failed ({e}), retrying with device_map='auto'")
                    self.model = model_cls.from_pretrained(
                        self.model_name,
                        torch_dtype=torch.bfloat16,
                        device_map='auto',
                    )
            else:
                self.model = model_cls.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float32,
                    device_map=None,
                )
            
            self.processor = AutoProcessor.from_pretrained(self.model_name)
            
            if self.device == 'cuda' and not hasattr(self.model, 'hf_device_map'):
                self.model = self.model.to(self.device)
            
            self.model.eval()
            print(f"Model loaded successfully on {self.device}")
            
        except Exception as e:
            print(f"Error loading model: {e}")
            raise
    
    @staticmethod
    def _bnb_available():
        try:
            import bitsandbytes  # noqa: F401
            return True
        except ImportError:
            return False
    
    def _load_4bit(self, model_cls):
        """bitsandbytes nf4 quantized load (~5-6GB VRAM for a 7B model)."""
        from transformers import BitsAndBytesConfig
        qconfig = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
        )
        return model_cls.from_pretrained(
            self.model_name,
            quantization_config=qconfig,
            device_map='cuda',
        )
    
    def extract_frames(self, video_path, n_frames=8, max_side=512):
        """Extract evenly spaced frames from video.

        E0-1 OOM 修复 (2026-09-05): 4K 源帧不缩放直进 Qwen 处理器时,
        视觉 token 网格爆炸(单帧 ~10k token × 8 帧 → 单次 12.21GiB 激活
        分配, 8GB 卡必 OOM → 全部素材降级光流)。统一限边 max_side。
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        def _fit(frame):
            h, w = frame.shape[:2]
            scale = max_side / max(h, w)
            if scale < 1.0:
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            return frame

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < n_frames:
            frames = []
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(_fit(frame))
            while len(frames) < n_frames:
                frames.append(frames[-1])
            cap.release()
            return frames[:n_frames]

        indices = np.linspace(0, total_frames - 1, n_frames, dtype=int)
        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(_fit(frame))

        cap.release()

        while len(frames) < n_frames:
            frames.append(frames[-1])

        return frames
    
    def classify_motion(self, video_path, prompt=None):
        """
        Classify camera motion type using VLM
        
        Args:
            video_path: Path to video file
            prompt: Custom prompt (default: camera motion description)
        
        Returns:
            (prediction, confidence, description)
        """
        import numpy as np
        
        if prompt is None:
            prompt = "Describe the camera motion in this video clip. Is it static, zoom, tilt, orbit, pan, or a combination? Be specific about the camera movement."
        
        # Extract frames
        frames = self.extract_frames(video_path, n_frames=8)
        
        # Convert BGR to RGB
        frames_rgb = [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in frames]
        
        # Prepare input (remove fps to avoid list/int type error)
        messages = [
            {"role": "user", "content": [
                {"type": "video", "video": frames_rgb},
                {"type": "text", "text": prompt}
            ]}
        ]
        
        # Process input
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.processor(
            text=[text],
            videos=[frames_rgb],
            padding=True,
            return_tensors="pt"
        )
        
        inputs = {k: v.to(self.device) if hasattr(v, 'to') else v for k, v in inputs.items()}
        
        # Generate (quantized models reject temperature/do_sample kwargs in
        # some transformers versions; keep the call minimal)
        with infer_ctx(self.device):
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=150,
                do_sample=False
            )
        
        # Decode
        output_text = self.processor.batch_decode(
            output_ids[:, inputs['input_ids'].shape[1]:],
            skip_special_tokens=True
        )[0].strip()
        
        # Parse prediction
        prediction, confidence = self._parse_prediction(output_text)
        
        return prediction, confidence, output_text
    
    def _parse_prediction(self, text):
        """Parse VLM output to extract prediction and confidence.

        Regex-based (verb conjugations covered). Priority on conflicts:
        static < tilt-orbit < zoom. Static only wins on explicit statements;
        quality words (steady/smooth/still) never count as static evidence.
        """
        cleaned = _NEGATION_RE.sub(" ", text)

        zoom_score = len(_ZOOM_RE.findall(cleaned))
        tilt_score = len(_TILT_ORBIT_RE.findall(cleaned))
        has_motion = bool(_MOTION_RE.search(cleaned))
        static_strong = bool(_STATIC_RE.search(text))

        # Explicit motion primitives always win over static statements
        # (covers "still moving forward" etc.)
        if zoom_score > 0 or tilt_score > 0:
            # Zoom takes precedence over tilt-orbit on ties (F2/F3 priority)
            if zoom_score >= tilt_score:
                return 'zoom', min(0.99, 0.5 + zoom_score * 0.1)
            return 'tilt-orbit', min(0.99, 0.5 + tilt_score * 0.1)

        if static_strong:
            return 'static', 0.7
        if has_motion:
            # Camera moves but no specific primitive matched
            return 'tilt-orbit', 0.55
        # Default to tilt-orbit (most common in anime)
        return 'tilt-orbit', 0.5


def main():
    parser = argparse.ArgumentParser(description='VLM expert for camera motion classification')
    parser.add_argument('video_path', type=str, help='Path to video file')
    parser.add_argument('--device', type=str, default='cuda',
                        help='Device: cpu or cuda (default: cuda)')
    parser.add_argument('--quantize', type=str, default='auto',
                        choices=['auto', '4bit', 'none'],
                        help='Quantization: auto/4bit/none (default: auto)')
    
    args = parser.parse_args()
    
    # Initialize VLM expert
    vlm = VLMExpertModel(device=args.device, quantize=args.quantize)
    
    # Classify
    start_time = time.time()
    pred, conf, desc = vlm.classify_motion(args.video_path)
    elapsed = time.time() - start_time
    
    # Output
    print(f"\nPrediction: {pred}")
    print(f"Confidence: {conf:.3f}")
    print(f"Description: {desc}")
    print(f"Time: {elapsed:.2f}s")
    
    return pred, conf, desc


if __name__ == '__main__':
    import numpy as np
    main()
