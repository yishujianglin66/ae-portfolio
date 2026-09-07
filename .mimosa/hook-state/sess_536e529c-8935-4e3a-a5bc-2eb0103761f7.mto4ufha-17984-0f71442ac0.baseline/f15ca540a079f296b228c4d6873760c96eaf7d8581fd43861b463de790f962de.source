"""
Visual Content Analyzer - 视觉模型素材内容分析
============================================
从视频中抽取关键帧 → 调用豆包视觉模型 → 理解内容 → 辅助剧本生成

核心能力:
1. 关键帧抽取: 按场景变化/等间隔抽取代表性帧
2. 视觉理解: 人物/动作/场景/情绪/色彩风格
3. 内容标签: 自动生成可用于剧本的关键词
4. 场景描述: 为每个段落提供画面描述

用法:
    analyzer = VisualContentAnalyzer()
    result = analyzer.analyze("video.mp4", num_frames=8)
    # result = {"scenes": [...], "tags": [...], "summary": "..."}
"""
import os
import sys
import json
import time
import base64
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


class VisualContentAnalyzer:
    """视觉模型内容分析器"""

    def __init__(self):
        self._load_config()

    def _load_config(self):
        """加载 API 配置 - 四层视觉分析"""
        env_path = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.env.doubao")
        config = {}
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        config[k.strip()] = v.strip()

        # Layer 1: ARK 视觉 Endpoint (主力 - 已验证可用)
        self.ark_key = config.get("DOUBAO_API_KEY", "")
        self.ark_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        self.ark_vision_model = config.get("ARK_ENDPOINT_VISION", "ep-20260716122053-t2lst")
        self.ark_text_model = config.get("ARK_ENDPOINT_TEXT", "deepseek-v4-flash-260425")

        # Layer 2: DuckMiss 视觉模型 (备用 - Claude)
        self.dm_key = config.get("DUCK_MISS_API_KEY", "")
        self.dm_url = config.get("DUCK_MISS_BASE_URL", "https://duckmiss.site/v1") + "/chat/completions"
        self.dm_vision_model = config.get("DUCK_MISS_VISION_MODEL", "claude-sonnet-4-6")

        # Layer 3: SiliconFlow 视觉模型 (备用 - Qwen)
        self.sf_key = config.get("SILICONFLOW_API_KEY", "")
        self.sf_url = config.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1") + "/chat/completions"
        self.sf_vision_model = config.get("SILICONFLOW_VISION_MODEL", "Qwen/Qwen3-VL-8B-Instruct")

    def analyze(self, video_path: str,
                num_frames: int = 8,
                prompt: str = None) -> Dict[str, Any]:
        """
        分析视频内容。

        Args:
            video_path: 视频文件路径
            num_frames: 抽取帧数
            prompt: 自定义分析提示词

        Returns:
            分析结果: scenes, tags, summary, characters, actions
        """
        log(f"视觉内容分析: {Path(video_path).name}")

        # Step 1: 抽取关键帧
        frames = self._extract_keyframes(video_path, num_frames)
        if not frames:
            log("  无法抽取关键帧", "ERROR")
            return {"error": "无法抽取关键帧", "scenes": [], "tags": []}

        log(f"  抽取 {len(frames)} 帧")

        # Step 2: 调用视觉模型
        result = self._call_vision_api(frames, prompt)

        # Step 3: 清理临时文件
        for fp in frames:
            try:
                os.remove(fp)
            except Exception:
                pass

        return result

    def _extract_keyframes(self, video_path: str, num_frames: int) -> List[str]:
        """从视频抽取关键帧图片"""
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        duration = total / fps

        # 等间隔采样 + 场景变化检测
        step = max(1, total // (num_frames * 3))  # 过采样再筛选
        candidates = []
        prev_hist = None

        for i in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.normalize(cv2.calcHist([gray], [0], None, [64], [0, 256]),
                                 None).flatten()

            # 场景变化分数
            scene_score = 0
            if prev_hist is not None:
                scene_score = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
            prev_hist = hist

            # 清晰度 (拉普拉斯方差)
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            candidates.append({
                "frame_idx": i,
                "time": i / fps,
                "scene_score": scene_score,
                "sharpness": sharpness,
                "frame": frame,
            })

        cap.release()

        # 筛选: 优先选场景变化大的 + 清晰的帧
        candidates.sort(key=lambda c: c["scene_score"] + c["sharpness"] * 0.001, reverse=True)
        selected = candidates[:num_frames]
        selected.sort(key=lambda c: c["time"])  # 按时间排序

        # 保存为临时文件
        temp_dir = tempfile.mkdtemp(prefix="vca_frames_")
        frame_paths = []
        for c in selected:
            fp = os.path.join(temp_dir, f"frame_{c['frame_idx']:06d}.jpg")
            cv2.imwrite(fp, c["frame"])
            frame_paths.append(fp)

        return frame_paths

    def _call_vision_api(self, frame_paths: List[str],
                         prompt: str = None) -> Dict[str, Any]:
        """四层叠加视觉分析: ARK视觉 → DuckMiss → SiliconFlow → OpenCV+LLM → 规则回退"""

        # === Layer 1: ARK 视觉 Endpoint (主力) ===
        result = self._call_ark_vision(frame_paths, prompt)
        if result and result.get("scenes"):
            log("  [OK] ARK 视觉模型分析成功")
            cv_features = self._extract_cv_features(frame_paths)
            if cv_features:
                result["cv_features"] = cv_features
                result["analysis_mode"] = "ark_vision+opencv"
            return result

        # === Layer 2: DuckMiss 视觉模型 (Claude) ===
        log("  ARK 视觉不可用, 尝试 DuckMiss", "WARN")
        result = self._call_duckmiss_vision(frame_paths, prompt)
        if result and result.get("scenes"):
            log("  [OK] DuckMiss 视觉模型分析成功")
            result["analysis_mode"] = "duckmiss_vision"
            return result

        # === Layer 3: SiliconFlow 视觉模型 (Qwen) ===
        log("  DuckMiss 不可用, 尝试 SiliconFlow", "WARN")
        result = self._call_siliconflow_vision(frame_paths, prompt)
        if result and result.get("scenes"):
            log("  [OK] SiliconFlow 视觉模型分析成功")
            result["analysis_mode"] = "siliconflow_vision"
            return result

        # === Layer 4: OpenCV 特征 + ARK 文本 LLM 推断 ===
        log("  所有视觉API不可用, 回退到 OpenCV+LLM", "WARN")
        result = self._call_opencv_llm(frame_paths, prompt)
        if result and result.get("scenes"):
            result["analysis_mode"] = "opencv+llm"
            return result

        # === Layer 5: 规则回退 ===
        log("  所有分析不可用, 使用规则分析", "WARN")
        return self._fallback_analysis()

    def _call_ark_vision(self, frame_paths: List[str],
                          prompt: str = None) -> Optional[Dict]:
        """Layer 1: ARK 视觉 Endpoint 直接分析图片"""
        if not self.ark_key:
            return None
        import urllib.request
        system_prompt = """分析这些视频帧，返回JSON:
{"summary":"内容概述(20字)","scenes":[{"time_order":1,"description":"画面内容","mood":"情绪"}],"characters":["角色"],"actions":["动作"],"visual_style":"视觉风格","tags":["标签5-10个"],"suggested_edit":"建议剪辑风格"}
只返回JSON。"""
        user_text = prompt or "请分析这些视频帧的画面内容、人物、动作、情绪和风格。"
        content_parts = [{"type": "text", "text": user_text}]
        for fp in frame_paths[:6]:
            try:
                with open(fp, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
            except Exception:
                continue
        data = json.dumps({
            "model": self.ark_vision_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content_parts},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                self.ark_url, data=data,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self.ark_key}"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            log(f"  ARK 视觉响应: {len(content)} 字符")
            parsed = self._parse_json_response(content)
            if parsed:
                log(f"  场景: {len(parsed.get('scenes', []))} 个")
                log(f"  标签: {', '.join(parsed.get('tags', [])[:5])}")
            return parsed
        except Exception as e:
            log(f"  ARK 视觉失败: {e}", "WARN")
            return None

    def _call_duckmiss_vision(self, frame_paths: List[str],
                               prompt: str = None) -> Optional[Dict]:
        """Layer 2: DuckMiss Claude 视觉模型分析图片"""
        if not self.dm_key:
            return None
        import urllib.request
        system_prompt = """分析这些视频帧，返回JSON:
{"summary":"内容概述(20字)","scenes":[{"time_order":1,"description":"画面内容","mood":"情绪"}],"characters":["角色"],"actions":["动作"],"visual_style":"视觉风格","tags":["标签5-10个"],"suggested_edit":"建议剪辑风格"}
只返回JSON。"""
        user_text = prompt or "请分析这些视频帧的画面内容、人物、动作、情绪和风格。"
        content_parts = [{"type": "text", "text": user_text}]
        for fp in frame_paths[:6]:
            try:
                with open(fp, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
            except Exception:
                continue
        data = json.dumps({
            "model": self.dm_vision_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content_parts},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                self.dm_url, data=data,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self.dm_key}",
                         "User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            log(f"  DuckMiss 视觉响应: {len(content)} 字符")
            parsed = self._parse_json_response(content)
            if parsed:
                log(f"  场景: {len(parsed.get('scenes', []))} 个")
                log(f"  标签: {', '.join(parsed.get('tags', [])[:5])}")
            return parsed
        except Exception as e:
            log(f"  DuckMiss 视觉失败: {e}", "WARN")
            return None

    def _call_siliconflow_vision(self, frame_paths: List[str],
                                  prompt: str = None) -> Optional[Dict]:
        """Layer 1: 调用 SiliconFlow 视觉模型直接分析图片"""
        if not self.sf_key:
            return None

        import urllib.request

        system_prompt = """分析这些视频帧，返回JSON:
{"summary":"内容概述(20字)","scenes":[{"time_order":1,"description":"画面内容","mood":"情绪"}],"characters":["角色"],"actions":["动作"],"visual_style":"视觉风格","tags":["标签5-10个"],"suggested_edit":"建议剪辑风格"}
只返回JSON。"""
        user_text = prompt or "请分析这些视频帧的画面内容、人物、动作、情绪和风格。"

        content_parts = [{"type": "text", "text": user_text}]
        for fp in frame_paths[:6]:  # 最多6帧
            try:
                with open(fp, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
            except Exception:
                continue

        data = json.dumps({
            "model": self.sf_vision_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content_parts},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                self.sf_url, data=data,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self.sf_key}"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            log(f"  SiliconFlow 视觉响应: {len(content)} 字符")
            parsed = self._parse_json_response(content)
            if parsed:
                log(f"  场景: {len(parsed.get('scenes', []))} 个")
                log(f"  标签: {', '.join(parsed.get('tags', [])[:5])}")
            return parsed
        except Exception as e:
            log(f"  SiliconFlow 失败: {e}", "WARN")
            return None

    def _call_opencv_llm(self, frame_paths: List[str],
                          prompt: str = None) -> Optional[Dict]:
        """Layer 2: OpenCV 特征提取 + ARK 文本 LLM 推断"""
        cv_features = self._extract_cv_features(frame_paths)
        if not cv_features:
            return None

        features_text = json.dumps(cv_features, ensure_ascii=False)
        llm_prompt = f"""根据视频帧视觉特征数据推断内容，返回JSON:
帧特征: {features_text}
返回格式: {{"summary":"概述","scenes":[{{"time_order":1,"description":"内容","mood":"情绪"}}],"characters":["角色"],"actions":["动作"],"visual_style":"风格","tags":["标签"],"suggested_edit":"建议"}}
只返回JSON。"""
        return self._call_ark_text_llm(llm_prompt)

    def _extract_cv_features(self, frame_paths: List[str]) -> List[Dict]:
        """用 OpenCV 提取每帧视觉特征"""
        import cv2
        import numpy as np
        features = []
        for i, fp in enumerate(frame_paths):
            img = cv2.imread(fp)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            brightness = float(np.mean(gray))
            saturation = float(np.mean(hsv[:, :, 1]))
            hue = float(np.mean(hsv[:, :, 0]))
            edge_density = float(np.mean(cv2.Canny(gray, 50, 150))) / 255.0
            b_mean, g_mean, r_mean = [float(np.mean(img[:,:,c])) for c in range(3)]
            face_count = 0
            try:
                cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                faces = cascade.detectMultiScale(gray, 1.1, 4)
                face_count = len(faces)
            except Exception:
                pass
            features.append({
                "frame": i + 1,
                "brightness": round(brightness, 1),
                "saturation": round(saturation, 1),
                "hue": round(hue, 1),
                "edge_density": round(edge_density, 3),
                "dominant_rgb": {"r": round(r_mean, 1), "g": round(g_mean, 1), "b": round(b_mean, 1)},
                "faces": face_count,
            })
        return features

    def _call_ark_text_llm(self, prompt: str) -> Optional[Dict]:
        """调用 ARK 文本 LLM"""
        import urllib.request
        if not self.ark_key:
            return None
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.ark_key}",
        }
        data = json.dumps({
            "model": self.ark_text_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1500,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(self.ark_url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            log(f"  ARK LLM 推断响应: {len(content)} 字符")
            return self._parse_json_response(content)
        except Exception as e:
            log(f"  ARK LLM 失败: {e}", "ERROR")
            return None

    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """从模型响应中解析 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except Exception:
            pass

        # 尝试提取 ```json ... ```
        import re
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        # 尝试找到第一个 { 到最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass

        return None

    def _fallback_analysis(self) -> Dict[str, Any]:
        """规则回退分析"""
        return {
            "summary": "视觉模型不可用, 使用基础分析",
            "scenes": [{"time_order": 1, "description": "通用场景", "mood": "neutral"}],
            "characters": [],
            "actions": [],
            "visual_style": "unknown",
            "tags": ["auto", "generic"],
            "suggested_edit": "cinematic",
        }


# ================================================================
#  主入口
# ================================================================
if __name__ == "__main__":
    analyzer = VisualContentAnalyzer()

    v17 = r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4"
    if os.path.exists(v17):
        result = analyzer.analyze(v17, num_frames=6)
        print(f"\n结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:1000])
    else:
        print(f"视频不存在: {v17}")
