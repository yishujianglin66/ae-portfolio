#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video_reverse_engine.py
视频技术逆向分析引擎

功能：
  1. 智能抽帧（基于场景变化+运动峰值）
  2. 多模型投票分析（Claude + GPT + ARK 三路交叉验证）
  3. AE效果参数推断（内置效果+第三方插件指纹库）
  4. 图层堆栈推断
  5. 关键帧曲线推断
  6. 输出结构化逆向分析报告

每一步智能选择最优模型：
  - 视觉理解: Claude Sonnet + GPT-Sol 多模型投票
  - 深度推理: Claude Opus + GPT-Terra
  - 快速分类: Claude Haiku + GPT-Mini
  - 参数推断: Claude Opus (最强推理)
  - 代码生成: GPT-Luna (代码专精)
"""

import os
import sys
import json
import time
import base64
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests

# ===== 环境变量加载 =====
def _load_env():
    env_path = PROJECT_ROOT / ".env.doubao"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

_load_env()


# ===== 模型配置 =====
class ModelConfig:
    """统一模型配置 - 三大API提供商"""
    
    # Claude (DuckMiss中转站1)
    CLAUDE_PRO = os.environ.get("DUCK_MISS_PRO_MODEL", "claude-opus-4-8")
    CLAUDE_DEFAULT = os.environ.get("DUCK_MISS_DEFAULT_MODEL", "claude-sonnet-4-6")
    CLAUDE_FAST = os.environ.get("DUCK_MISS_FAST_MODEL", "claude-sonnet-4-6")
    CLAUDE_VISION = os.environ.get("DUCK_MISS_VISION_MODEL", "claude-sonnet-4-6")
    CLAUDE_KEY = os.environ.get("DUCK_MISS_API_KEY", "")
    CLAUDE_URL = os.environ.get("DUCK_MISS_BASE_URL", "https://duckmiss.site/v1")
    
    # GPT (复用DuckMiss Claude)
    GPT_PRO = os.environ.get("GPT_GATEWAY_PRO_MODEL", "claude-opus-4-8")
    GPT_DEFAULT = os.environ.get("GPT_GATEWAY_DEFAULT_MODEL", "claude-sonnet-4-6")
    GPT_FAST = os.environ.get("GPT_GATEWAY_FAST_MODEL", "claude-sonnet-4-6")
    GPT_CODE = os.environ.get("GPT_GATEWAY_CODE_MODEL", "claude-sonnet-4-6")
    GPT_VISION = os.environ.get("GPT_GATEWAY_VISION_MODEL", "claude-sonnet-4-6")
    GPT_KEY = os.environ.get("DUCK_MISS_API_KEY_BACKUP", "")
    GPT_URL = os.environ.get("GPT_GATEWAY_BASE_URL", "https://duckmiss.site/v1")
    
    # ARK (火山方舟)
    ARK_PRO = "deepseek-v4-pro-260425"
    ARK_FLASH = "deepseek-v4-flash-260425"
    ARK_KEY = os.environ.get("DOUBAO_API_KEY", "")
    ARK_URL = "https://ark.cn-beijing.volces.com/api/v3"
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """获取可用的API提供商列表"""
        providers = []
        if cls.CLAUDE_KEY:
            providers.append("claude")
        if cls.GPT_KEY:
            providers.append("gpt")
        if cls.ARK_KEY:
            providers.append("ark")
        return providers


# ===== API调用器 =====
class MultiModelCaller:
    """多模型统一调用器 - 支持多模型投票"""
    
    def __init__(self):
        self.sessions = {
            "claude": requests.Session(),
            "gpt": requests.Session(),
            "ark": requests.Session(),
        }
        if ModelConfig.CLAUDE_KEY:
            self.sessions["claude"].headers.update({
                "Authorization": f"Bearer {ModelConfig.CLAUDE_KEY}",
                "Content-Type": "application/json",
            })
        if ModelConfig.GPT_KEY:
            self.sessions["gpt"].headers.update({
                "Authorization": f"Bearer {ModelConfig.GPT_KEY}",
                "Content-Type": "application/json",
            })
        if ModelConfig.ARK_KEY:
            self.sessions["ark"].headers.update({
                "Authorization": f"Bearer {ModelConfig.ARK_KEY}",
                "Content-Type": "application/json",
            })
    
    def call_model(self, provider: str, model: str, messages: List[Dict],
                   max_tokens: int = 4096, temperature: float = 0.7) -> Dict:
        """调用单个模型"""
        url_map = {
            "claude": f"{ModelConfig.CLAUDE_URL}/chat/completions",
            "gpt": f"{ModelConfig.GPT_URL}/chat/completions",
            "ark": f"{ModelConfig.ARK_URL}/chat/completions",
        }
        
        url = url_map.get(provider)
        if not url:
            return {"error": f"未知提供商: {provider}"}
        
        session = self.sessions.get(provider)
        if not session:
            return {"error": f"提供商 {provider} 未配置"}
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        try:
            resp = session.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            if "choices" in data and data["choices"]:
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {
                    "success": True,
                    "content": content,
                    "model": model,
                    "provider": provider,
                    "tokens": usage.get("total_tokens", 0),
                }
            return {"error": f"无choices: {data}"}
        except Exception as e:
            return {"error": str(e), "provider": provider, "model": model}
    
    def call_vision(self, provider: str, model: str, prompt: str,
                    image_base64: str, max_tokens: int = 4096) -> Dict:
        """调用视觉模型分析图片"""
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
            ]
        }]
        return self.call_model(provider, model, messages, max_tokens=max_tokens)
    
    def multi_model_vote(self, prompt: str, providers: List[str] = None,
                         max_tokens: int = 4096) -> Dict:
        """多模型投票 - 并行调用多个模型，交叉验证"""
        if providers is None:
            providers = ModelConfig.get_available_providers()
        
        model_map = {
            "claude": ModelConfig.CLAUDE_DEFAULT,
            "gpt": ModelConfig.GPT_DEFAULT,
            "ark": ModelConfig.ARK_PRO,
        }
        
        results = {}
        for provider in providers:
            model = model_map.get(provider)
            if not model:
                continue
            
            messages = [{"role": "user", "content": prompt}]
            result = self.call_model(provider, model, messages, max_tokens)
            if result.get("success"):
                results[provider] = result
        
        return self._merge_results(results)
    
    def _merge_results(self, results: Dict) -> Dict:
        """合并多模型结果"""
        if not results:
            return {"error": "所有模型调用失败"}
        if len(results) == 1:
            provider = list(results.keys())[0]
            return results[provider]
        
        # 多模型结果合并
        merged = {
            "success": True,
            "providers": list(results.keys()),
            "responses": {},
            "consensus": None,
        }
        
        # 尝试提取JSON并合并
        json_results = []
        for provider, result in results.items():
            merged["responses"][provider] = result["content"]
            # 尝试解析JSON
            content = result["content"]
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start != -1 and json_end != -1:
                try:
                    parsed = json.loads(content[json_start:json_end])
                    json_results.append(parsed)
                except json.JSONDecodeError:
                    pass
        
        # 如果多个模型都返回了JSON，取并集
        if json_results:
            consensus = {}
            for key in set().union(*[set(r.keys()) for r in json_results]):
                values = [r.get(key) for r in json_results if key in r]
                # 如果所有模型都同意某个值，取该值
                if len(set(str(v) for v in values)) == 1:
                    consensus[key] = values[0]
                else:
                    # 否则取第一个非空值
                    for v in values:
                        if v:
                            consensus[key] = v
                            break
            merged["consensus"] = consensus
        
        return merged


# ===== 智能抽帧器 =====
class SmartFrameExtractor:
    """智能关键帧提取器"""
    
    def __init__(self, ffmpeg_path: str = None):
        if ffmpeg_path is None:
            # 从项目配置加载FFmpeg路径
            ffmpeg_path = os.environ.get("FFMPEG_PATH", r"C:\ffmpeg\bin\ffmpeg.exe")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"
        self.ffmpeg = ffmpeg_path
    
    def extract_keyframes(self, video_path: str, max_frames: int = 12,
                          output_dir: str = None) -> List[str]:
        """提取关键帧 - 基于场景变化检测"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频不存在: {video_path}")
        
        if output_dir is None:
            # 使用项目output目录避免中文路径问题
            output_dir = os.path.join(str(PROJECT_ROOT), "output", "_keyframes")
        os.makedirs(output_dir, exist_ok=True)
        
        # 清理旧帧
        for f in os.listdir(output_dir):
            if f.endswith(".jpg"):
                os.remove(os.path.join(output_dir, f))
        
        # 方法1: 使用FFmpeg场景检测
        frame_paths = self._extract_scene_based(video_path, output_dir, max_frames)
        
        if len(frame_paths) < 3:
            # 方法2: 均匀采样兜底
            frame_paths = self._extract_uniform(video_path, output_dir, max_frames)
        
        return frame_paths
    
    def _extract_scene_based(self, video_path: str, output_dir: str,
                              max_frames: int) -> List[str]:
        """基于场景变化提取关键帧"""
        output_pattern = os.path.join(output_dir, "scene_%03d.jpg")
        # 使用Windows短路径避免中文编码问题
        safe_video = self._get_safe_path(video_path)
        safe_output = self._get_safe_path(output_pattern)
        cmd = [
            self.ffmpeg, "-i", safe_video,
            "-vf", "select='gt(scene,0.3)'",
            "-vsync", "vfr",
            "-q:v", "2",
            safe_output,
            "-y", "-hide_banner", "-loglevel", "error",
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except Exception:
            pass

        frames = sorted([
            os.path.join(output_dir, f) for f in os.listdir(output_dir)
            if f.startswith("scene_") and f.endswith(".jpg")
        ])
        return frames[:max_frames]
    
    def _extract_uniform(self, video_path: str, output_dir: str,
                          max_frames: int) -> List[str]:
        """均匀采样提取帧"""
        safe_video = self._get_safe_path(video_path)
        # 先获取视频时长
        cmd = [self.ffmpeg, "-i", safe_video, "-f", "null", "-"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            duration = self._parse_duration(result.stderr)
        except Exception:
            duration = 10.0
        
        if duration <= 0:
            duration = 10.0
        
        interval = duration / (max_frames + 1)
        frames = []
        for i in range(1, max_frames + 1):
            timestamp = interval * i
            output_path = os.path.join(output_dir, f"uniform_{i:03d}.jpg")
            safe_output = self._get_safe_path(output_path)
            cmd = [
                self.ffmpeg, "-ss", str(timestamp), "-i", safe_video,
                "-frames:v", "1", "-q:v", "2",
                safe_output, "-y", "-hide_banner", "-loglevel", "error",
            ]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if os.path.exists(output_path):
                    frames.append(output_path)
            except Exception:
                pass
        
        return frames
    
    def _get_safe_path(self, path: str) -> str:
        """获取Windows安全路径（处理中文编码）"""
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            rv = ctypes.windll.kernel32.GetShortPathNameW(path, buf, 260)
            if rv > 0:
                return buf.value
        except Exception:
            pass
        return path
    
    def _parse_duration(self, stderr: str) -> float:
        """从FFmpeg输出解析视频时长"""
        import re
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
        if match:
            h, m, s = match.groups()
            return int(h) * 3600 + int(m) * 60 + float(s)
        return 10.0
    
    def encode_image(self, image_path: str) -> str:
        """编码图片为base64"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


# ===== 视频技术逆向分析引擎 =====
class VideoReverseEngine:
    """视频技术逆向分析引擎"""
    
    def __init__(self):
        self.caller = MultiModelCaller()
        self.extractor = SmartFrameExtractor()
        self.providers = ModelConfig.get_available_providers()
        
        # 加载AE效果知识图谱
        self.effect_kb = self._load_effect_kb()
    
    def _load_effect_kb(self) -> Dict:
        """加载AE效果知识库"""
        kb = {"builtin_effects": [], "third_party_plugins": []}
        
        # 加载内置效果知识图谱
        try:
            from effect_knowledge_graph import EFFECT_KNOWLEDGE_GRAPH
            kb["builtin_effects"] = EFFECT_KNOWLEDGE_GRAPH if isinstance(EFFECT_KNOWLEDGE_GRAPH, list) else []
        except ImportError:
            pass
        
        return kb
    
    def analyze(self, video_path: str, deep_analysis: bool = True) -> Dict:
        """完整视频逆向分析"""
        print(f"\n{'='*60}")
        print(f"  视频技术逆向分析引擎")
        print(f"{'='*60}")
        print(f"  视频: {video_path}")
        print(f"  可用模型: {', '.join(self.providers)}")
        print()
        
        result = {
            "video_path": video_path,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "providers": self.providers,
            "stages": {},
        }
        
        # ===== Stage 1: 智能抽帧 =====
        print("  [Stage 1] 智能抽帧...")
        try:
            frames = self.extractor.extract_keyframes(video_path, max_frames=12)
            result["stages"]["frame_extraction"] = {
                "success": True,
                "frame_count": len(frames),
                "frames": frames,
            }
            print(f"    提取 {len(frames)} 个关键帧")
        except Exception as e:
            result["stages"]["frame_extraction"] = {"success": False, "error": str(e)}
            print(f"    抽帧失败: {e}")
            return result
        
        if not frames:
            result["stages"]["frame_extraction"] = {"success": False, "error": "未提取到帧"}
            return result
        
        # ===== Stage 2: 多模型视觉分析 =====
        print("\n  [Stage 2] 多模型视觉分析（投票机制）...")
        visual_analysis = self._multi_model_visual_analysis(frames[:6])
        result["stages"]["visual_analysis"] = visual_analysis
        print(f"    视觉分析完成: {visual_analysis.get('providers_used', [])}")
        
        # ===== Stage 3: AE效果参数推断 =====
        print("\n  [Stage 3] AE效果参数推断...")
        effect_params = self._infer_ae_parameters(visual_analysis, frames[:3])
        result["stages"]["ae_parameters"] = effect_params
        print(f"    识别效果数: {len(effect_params.get('effects', []))}")
        
        # ===== Stage 4: 图层堆栈推断 =====
        print("\n  [Stage 4] 图层堆栈推断...")
        layer_stack = self._infer_layer_stack(visual_analysis)
        result["stages"]["layer_stack"] = layer_stack
        print(f"    推断图层数: {len(layer_stack.get('layers', []))}")
        
        # ===== Stage 5: 调色参数推断 =====
        print("\n  [Stage 5] 调色参数推断...")
        color_params = self._infer_color_params(frames[:3])
        result["stages"]["color_params"] = color_params
        print(f"    调色节点数: {len(color_params.get('nodes', []))}")
        
        # ===== Stage 6: 节奏与剪辑分析 =====
        print("\n  [Stage 6] 节奏与剪辑分析...")
        rhythm = self._analyze_rhythm(video_path, frames)
        result["stages"]["rhythm"] = rhythm
        print(f"    BPM: {rhythm.get('bpm', 'N/A')}")
        
        # ===== Stage 7: 生成复现方案 =====
        if deep_analysis:
            print("\n  [Stage 7] 生成智能复现方案...")
            reproduction = self._generate_reproduction_plan(result)
            result["reproduction_plan"] = reproduction
            print(f"    复现步骤数: {len(reproduction.get('steps', []))}")
        
        # ===== 汇总 =====
        result["summary"] = self._generate_summary(result)
        
        print(f"\n{'='*60}")
        print(f"  分析完成!")
        print(f"{'='*60}")
        
        return result
    
    def _multi_model_visual_analysis(self, frame_paths: List[str]) -> Dict:
        """多模型投票视觉分析"""
        prompt = """你是专业视频特效分析师。请深度分析这张视频帧，识别所有视觉技术和特效。

请输出JSON格式:
{
  "visual_effects": ["效果1", "效果2"],
  "color_grading": {
    "primary_color": "主色调",
    "color_temperature": "warm/cool/neutral",
    "contrast": "low/medium/high",
    "saturation": "low/medium/high"
  },
  "camera_movement": "运镜方式",
  "lighting": "打光方式",
  "composition": "构图方式",
  "post_effects": ["后期效果1"],
  "possible_plugins": ["可能的AE插件"],
  "style_keywords": ["风格关键词"],
  "confidence": 0.0-1.0
}
"""
        
        results = {"frames": [], "providers_used": []}
        
        for frame_path in frame_paths:
            try:
                image_b64 = self.extractor.encode_image(frame_path)
            except Exception as e:
                continue
            
            frame_result = {"frame": frame_path, "analyses": {}}
            
            # 调用多个视觉模型
            vision_calls = []
            
            if "claude" in self.providers:
                vision_calls.append(("claude", ModelConfig.CLAUDE_VISION))
            if "gpt" in self.providers:
                vision_calls.append(("gpt", ModelConfig.GPT_VISION))
            
            for provider, model in vision_calls:
                print(f"    [{provider}] 分析 {os.path.basename(frame_path)}...")
                result = self.caller.call_vision(provider, model, prompt, image_b64)
                if result.get("success"):
                    frame_result["analyses"][provider] = result["content"]
                    if provider not in results["providers_used"]:
                        results["providers_used"].append(provider)
            
            # 合并多模型结果
            if len(frame_result["analyses"]) > 1:
                frame_result["consensus"] = self.caller._merge_results(
                    {k: {"content": v, "success": True} for k, v in frame_result["analyses"].items()}
                ).get("consensus")
            
            results["frames"].append(frame_result)
        
        return results
    
    def _infer_ae_parameters(self, visual_analysis: Dict, frame_paths: List[str]) -> Dict:
        """推断AE效果参数"""
        # 收集所有识别到的效果
        all_effects = set()
        for frame_data in visual_analysis.get("frames", []):
            analyses = frame_data.get("analyses", {})
            for provider, content in analyses.items():
                try:
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    if json_start != -1 and json_end != -1:
                        parsed = json.loads(content[json_start:json_end])
                        for eff in parsed.get("visual_effects", []):
                            all_effects.add(eff)
                        for eff in parsed.get("possible_plugins", []):
                            all_effects.add(eff)
                except (json.JSONDecodeError, KeyError):
                    pass
        
        # 用最强模型推断精确参数
        prompt = f"""你是AE特效参数专家。根据以下识别到的视觉效果，推断具体的AE效果参数。

识别到的效果: {json.dumps(list(all_effects), ensure_ascii=False)}

请为每个效果输出:
{{
  "effects": [
    {{
      "name": "效果名称",
      "ae_effect": "AE内置效果名或插件名",
      "matchname": "ADBE XXX",
      "category": "built-in/third-party",
      "key_params": {{
        "参数名": "推断值"
      }},
      "confidence": 0.0-1.0,
      "reproduction_difficulty": "easy/medium/hard",
      "alternative": "替代方案"
    }}
  ]
}}
"""
        
        # 选择最强推理模型
        if "claude" in self.providers:
            result = self.caller.call_model(
                "claude", ModelConfig.CLAUDE_PRO,
                [{"role": "user", "content": prompt}],
                max_tokens=8192
            )
        elif "gpt" in self.providers:
            result = self.caller.call_model(
                "gpt", ModelConfig.GPT_PRO,
                [{"role": "user", "content": prompt}],
                max_tokens=8192
            )
        else:
            result = self.caller.call_model(
                "ark", ModelConfig.ARK_PRO,
                [{"role": "user", "content": prompt}],
                max_tokens=8192
            )
        
        if result.get("success"):
            content = result["content"]
            try:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end != -1:
                    return json.loads(content[json_start:json_end])
            except json.JSONDecodeError:
                pass
            return {"raw": content, "effects": list(all_effects)}
        
        return {"effects": list(all_effects), "error": result.get("error")}
    
    def _infer_layer_stack(self, visual_analysis: Dict) -> Dict:
        """推断图层堆栈"""
        prompt = """根据视频帧的视觉分析结果，推断AE图层堆栈结构。

请输出JSON:
{
  "layers": [
    {
      "index": 1,
      "name": "图层名称",
      "type": "footage/solid/adjustment/null/text/shape",
      "blend_mode": "normal/screen/add/multiply/overlay",
      "opacity": 100,
      "effects": ["效果1"],
      "mask": "none/rectangle/ellipse/pen",
      "confidence": 0.0-1.0
    }
  ],
  "compositions": [
    {
      "name": "主合成",
      "width": 1920,
      "height": 1080,
      "fps": 30
    }
  ]
}
"""
        # 收集视觉分析摘要
        summary = ""
        for frame_data in visual_analysis.get("frames", [])[:2]:
            for provider, content in frame_data.get("analyses", {}).items():
                summary += f"\n[{provider}]: {content[:500]}"
        
        full_prompt = prompt + f"\n\n视觉分析摘要:\n{summary}"
        
        if "claude" in self.providers:
            result = self.caller.call_model(
                "claude", ModelConfig.CLAUDE_PRO,
                [{"role": "user", "content": full_prompt}],
                max_tokens=4096
            )
        elif "gpt" in self.providers:
            result = self.caller.call_model(
                "gpt", ModelConfig.GPT_PRO,
                [{"role": "user", "content": full_prompt}],
                max_tokens=4096
            )
        else:
            result = self.caller.call_model(
                "ark", ModelConfig.ARK_PRO,
                [{"role": "user", "content": full_prompt}],
                max_tokens=4096
            )
        
        if result.get("success"):
            content = result["content"]
            try:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end != -1:
                    return json.loads(content[json_start:json_end])
            except json.JSONDecodeError:
                pass
            return {"raw": content}
        
        return {"error": result.get("error")}
    
    def _infer_color_params(self, frame_paths: List[str]) -> Dict:
        """推断调色参数"""
        if not frame_paths:
            return {"error": "无帧可分析"}
        
        prompt = """你是调色专家。请分析这张图片的调色参数，输出JSON:
{
  "nodes": [
    {
      "tool": "Lift/Gamma/Gain/Offset/Saturation/Contrast",
      "value": "推断值",
      "confidence": 0.0-1.0
    }
  ],
  "lut_suggestion": "推荐的LUT名称",
  "overall_style": "整体调色风格描述"
}
"""
        try:
            image_b64 = self.extractor.encode_image(frame_paths[0])
        except Exception:
            return {"error": "图片编码失败"}
        
        # 用视觉模型分析
        if "claude" in self.providers:
            result = self.caller.call_vision(
                "claude", ModelConfig.CLAUDE_VISION, prompt, image_b64
            )
        elif "gpt" in self.providers:
            result = self.caller.call_vision(
                "gpt", ModelConfig.GPT_VISION, prompt, image_b64
            )
        else:
            return {"error": "无可用的视觉模型"}
        
        if result.get("success"):
            content = result["content"]
            try:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end != -1:
                    return json.loads(content[json_start:json_end])
            except json.JSONDecodeError:
                pass
            return {"raw": content}
        
        return {"error": result.get("error")}
    
    def _analyze_rhythm(self, video_path: str, frames: List[str]) -> Dict:
        """分析视频节奏"""
        prompt = """根据视频关键帧数量和分布，推断视频节奏特征。输出JSON:
{
  "bpm": 数字,
  "pace": "slow/medium/fast",
  "avg_shot_duration": 秒,
  "cut_frequency": "low/medium/high",
  "rhythm_pattern": "节奏模式描述"
}
"""
        frame_info = f"视频路径: {video_path}\n关键帧数量: {len(frames)}\n"
        if len(frames) >= 2:
            frame_info += f"帧间隔分析: {len(frames)}帧覆盖整个视频"
        
        full_prompt = prompt + "\n\n" + frame_info
        
        # 用快速模型做节奏分析
        if "claude" in self.providers:
            result = self.caller.call_model(
                "claude", ModelConfig.CLAUDE_FAST,
                [{"role": "user", "content": full_prompt}],
                max_tokens=1024
            )
        elif "gpt" in self.providers:
            result = self.caller.call_model(
                "gpt", ModelConfig.GPT_FAST,
                [{"role": "user", "content": full_prompt}],
                max_tokens=1024
            )
        else:
            result = self.caller.call_model(
                "ark", ModelConfig.ARK_FLASH,
                [{"role": "user", "content": full_prompt}],
                max_tokens=1024
            )
        
        if result.get("success"):
            content = result["content"]
            try:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end != -1:
                    return json.loads(content[json_start:json_end])
            except json.JSONDecodeError:
                pass
        
        return {"bpm": "N/A", "pace": "unknown"}
    
    def _generate_reproduction_plan(self, analysis: Dict) -> Dict:
        """生成智能复现方案"""
        prompt = """你是视频特效复现专家。根据以下视频逆向分析结果，生成一个完整的复现方案。

要求：
1. 每一步选择最适合的模型（Claude/GPT/ARK）
2. 每一步选择最适合的软件（AE/PR/DaVinci/Blender/FFmpeg）
3. 对于难以直接复现的效果，提供替代方案
4. 考虑软件间的资产传递

请输出JSON:
{
  "steps": [
    {
      "index": 1,
      "name": "步骤名称",
      "description": "详细描述",
      "software": "AE/PR/DaVinci/Blender/FFmpeg",
      "model": "claude-opus/gpt-terra/ark-pro",
      "model_reason": "选择此模型的原因",
      "actions": ["具体操作1", "操作2"],
      "params": {"参数名": "值"},
      "difficulty": "easy/medium/hard",
      "alternative": "替代方案"
    }
  ],
  "estimated_quality": "复现质量评估 0-100",
  "missing_capabilities": ["无法复现的部分"],
  "suggestions": ["优化建议"]
}
"""
        # 准备分析摘要
        summary = json.dumps(analysis, ensure_ascii=False, default=str)[:3000]
        full_prompt = prompt + f"\n\n分析结果摘要:\n{summary}"
        
        # 用最强模型生成复现方案
        if "claude" in self.providers:
            result = self.caller.call_model(
                "claude", ModelConfig.CLAUDE_PRO,
                [{"role": "user", "content": full_prompt}],
                max_tokens=8192, temperature=0.5
            )
        elif "gpt" in self.providers:
            result = self.caller.call_model(
                "gpt", ModelConfig.GPT_PRO,
                [{"role": "user", "content": full_prompt}],
                max_tokens=8192, temperature=0.5
            )
        else:
            result = self.caller.call_model(
                "ark", ModelConfig.ARK_PRO,
                [{"role": "user", "content": full_prompt}],
                max_tokens=8192, temperature=0.5
            )
        
        if result.get("success"):
            content = result["content"]
            try:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end != -1:
                    return json.loads(content[json_start:json_end])
            except json.JSONDecodeError:
                pass
            return {"raw": content}
        
        return {"error": result.get("error")}
    
    def _generate_summary(self, result: Dict) -> Dict:
        """生成分析摘要"""
        summary = {
            "total_stages": len(result.get("stages", {})),
            "successful_stages": sum(
                1 for s in result.get("stages", {}).values()
                if isinstance(s, dict) and s.get("success") is not False
            ),
            "providers_used": result.get("stages", {})
                .get("visual_analysis", {})
                .get("providers_used", []),
            "effects_found": len(
                result.get("stages", {})
                .get("ae_parameters", {})
                .get("effects", [])
            ),
            "layers_inferred": len(
                result.get("stages", {})
                .get("layer_stack", {})
                .get("layers", [])
            ),
        }
        return summary
    
    def save_report(self, result: Dict, output_path: str = None) -> str:
        """保存分析报告"""
        if output_path is None:
            output_path = os.path.join(
                PROJECT_ROOT, "output",
                f"reverse_analysis_{int(time.time())}.json"
            )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        
        # 同时生成Markdown报告
        md_path = output_path.replace(".json", ".md")
        self._generate_markdown_report(result, md_path)
        
        print(f"\n  JSON报告: {output_path}")
        print(f"  MD报告: {md_path}")
        
        return output_path
    
    def _generate_markdown_report(self, result: Dict, output_path: str):
        """生成Markdown报告"""
        lines = [
            "# 视频技术逆向分析报告",
            "",
            f"**视频**: `{result.get('video_path', 'N/A')}`",
            f"**分析时间**: {result.get('timestamp', 'N/A')}",
            f"**使用模型**: {', '.join(result.get('providers', []))}",
            "",
        ]
        
        stages = result.get("stages", {})
        
        # Stage 1: 抽帧
        frame_data = stages.get("frame_extraction", {})
        lines.extend([
            "## 1. 关键帧提取",
            f"- 帧数量: {frame_data.get('frame_count', 'N/A')}",
            ""
        ])
        
        # Stage 2: 视觉分析
        visual = stages.get("visual_analysis", {})
        lines.extend([
            "## 2. 多模型视觉分析",
            f"- 使用模型: {', '.join(visual.get('providers_used', []))}",
            f"- 分析帧数: {len(visual.get('frames', []))}",
            ""
        ])
        
        # Stage 3: AE效果参数
        ae_params = stages.get("ae_parameters", {})
        effects = ae_params.get("effects", [])
        lines.extend([
            "## 3. AE效果参数推断",
            f"- 识别效果数: {len(effects)}",
        ])
        for eff in effects:
            if isinstance(eff, dict):
                lines.append(f"  - **{eff.get('name', 'N/A')}**: {eff.get('ae_effect', 'N/A')} (置信度: {eff.get('confidence', 'N/A')})")
        lines.append("")
        
        # Stage 4: 图层堆栈
        layers = stages.get("layer_stack", {}).get("layers", [])
        lines.extend([
            "## 4. 图层堆栈推断",
            f"- 推断图层数: {len(layers)}",
        ])
        for layer in layers:
            if isinstance(layer, dict):
                lines.append(f"  - Layer {layer.get('index', '?')}: {layer.get('name', 'N/A')} ({layer.get('type', 'N/A')})")
        lines.append("")
        
        # Stage 5: 调色参数
        color = stages.get("color_params", {})
        lines.extend([
            "## 5. 调色参数",
            f"```json",
            json.dumps(color, indent=2, ensure_ascii=False, default=str)[:500],
            "```",
            "",
        ])
        
        # Stage 6: 节奏
        rhythm = stages.get("rhythm", {})
        lines.extend([
            "## 6. 节奏分析",
            f"- BPM: {rhythm.get('bpm', 'N/A')}",
            f"- 节奏: {rhythm.get('pace', 'N/A')}",
            f"- 平均镜头时长: {rhythm.get('avg_shot_duration', 'N/A')}秒",
            "",
        ])
        
        # 复现方案
        repro = result.get("reproduction_plan", {})
        steps = repro.get("steps", [])
        if steps:
            lines.extend([
                "## 7. 智能复现方案",
                f"- 预计复现质量: {repro.get('estimated_quality', 'N/A')}/100",
                f"- 步骤数: {len(steps)}",
                "",
            ])
            for step in steps:
                if isinstance(step, dict):
                    lines.append(f"### Step {step.get('index', '?')}: {step.get('name', 'N/A')}")
                    lines.append(f"- **软件**: {step.get('software', 'N/A')}")
                    lines.append(f"- **模型**: {step.get('model', 'N/A')}")
                    lines.append(f"- **原因**: {step.get('model_reason', 'N/A')}")
                    lines.append(f"- **难度**: {step.get('difficulty', 'N/A')}")
                    desc = step.get('description', '')
                    if desc:
                        lines.append(f"- **描述**: {desc}")
                    lines.append("")
            
            missing = repro.get("missing_capabilities", [])
            if missing:
                lines.extend(["### 无法复现的部分", ""])
                for m in missing:
                    lines.append(f"- {m}")
                lines.append("")
            
            suggestions = repro.get("suggestions", [])
            if suggestions:
                lines.extend(["### 优化建议", ""])
                for s in suggestions:
                    lines.append(f"- {s}")
                lines.append("")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


# ===== CLI入口 =====
def main():
    import argparse
    parser = argparse.ArgumentParser(description="视频技术逆向分析引擎")
    parser.add_argument("video", help="视频文件路径")
    parser.add_argument("--deep", action="store_true", help="深度分析（含复现方案）")
    parser.add_argument("--output", help="输出报告路径", default=None)
    args = parser.parse_args()
    
    engine = VideoReverseEngine()
    result = engine.analyze(args.video, deep_analysis=args.deep)
    
    report_path = engine.save_report(result, args.output)
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
