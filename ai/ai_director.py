"""
AI Director System - AI 导演系统 v1.0
=====================================
从一句话描述到成品视频的完整自动化创作链。

Phase 1: 素材搜集 → 从B站/抖音下载参考素材
Phase 2: 视觉分析 → 场景/色彩/运动/情绪提取
Phase 3: AI 剧本 → LLM + 知识库生成完整剪辑剧本
Phase 4: JSX 翻译 → 剧本自动转为 AE 可执行脚本
Phase 5: AE 执行 → 自动渲染输出成品

用法:
    python ai_director.py
    director = AIDirector()
    result = director.produce("利威尔高燃混剪, 30秒, 竖屏")
"""
import importlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

# ── 路径配置 ──
PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
OUTPUT_DIR = PROJECT_ROOT / "output_director"
ENV_FILE = PROJECT_ROOT / ".env.doubao"

# ── 加载 API 配置 ──
def _load_env() -> dict[str, str]:
    env = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

ENV = _load_env()


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


def _is_trusted_material_result(r: dict) -> bool:
    """FIX-05/契约 §1：AI 生成素材入池白名单。

    拒收：非 success / 无路径 / source=="Mock" 占位片 / execution_path=="simulated"。
    旧行为只判 success，导致降级链末端 Mock 蓝色占位片被静默剪进成片（0924 审计 F6）。
    未带 execution_path 标记的历史适配器结果暂按 real 兼容（全量标记由 FIX-09 扫描器接管）。
    """
    if not (r.get("success") and r.get("path")):
        return False
    if str(r.get("source", "")) == "Mock":
        return False
    if r.get("execution_path") == "simulated":
        return False
    return True


def _ingest_aigc_results(aigc_results: list[dict], material_files: list) -> tuple[int, int]:
    """AI 生成结果入池循环（FIX-05 可测化接缝；白名单见 _is_trusted_material_result）。

    Returns: (accepted, rejected) 计数，供调用方/测试断言"Mock 永不入池"。
    """
    accepted = rejected = 0
    for r in aigc_results:
        if _is_trusted_material_result(r):
            material_files.append(r["path"])
            log(f"  AI素材已添加: {Path(r['path']).name}")
            accepted += 1
        else:
            log(f"  AI素材拒收(不可信来源: source={r.get('source')} "
                f"execution_path={r.get('execution_path')})，不得静默入池", "WARN")
            rejected += 1
    return accepted, rejected


# ================================================================
#  Phase 1: 素材搜集
# ================================================================
class MaterialCollector:
    """从多平台搜集素材视频"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir / "materials"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fetcher = None

    def _init_fetcher(self):
        if self.fetcher:
            return
        try:
            mf = importlib.import_module("media-fetcher")
            self.fetcher = mf.MediaFetcher()
            log("MediaFetcher 初始化成功")
        except Exception as e:
            log(f"MediaFetcher 不可用: {e}", "WARN")

    def collect_from_urls(self, urls: list[str]) -> list[dict]:
        """从给定 URL 列表下载素材"""
        self._init_fetcher()
        results = []
        for url in urls:
            try:
                r = self.fetcher.download_video(str(url), str(self.output_dir))
                results.append(r)
                status = "OK" if r.get("success") else "FAIL"
                log(f"  下载 {status}: {url[:60]}...")
            except Exception as e:
                results.append({"success": False, "error": str(e)})
                log(f"  下载失败: {e}", "ERROR")
        return results

    def collect_from_local(self, paths: list[str]) -> list[dict]:
        """使用本地已有素材"""
        results = []
        for p in paths:
            fp = Path(p)
            if fp.exists():
                results.append({
                    "success": True,
                    "path": str(fp),
                    "name": fp.name,
                    "size": fp.stat().st_size,
                })
                log(f"  本地素材: {fp.name}")
            else:
                results.append({"success": False, "error": f"文件不存在: {p}"})
                log(f"  文件不存在: {p}", "WARN")
        return results

    def scan_local_library(self, directory: str = None) -> list[dict]:
        """扫描本地素材库"""
        scan_dir = Path(directory) if directory else Path(r"D:\AE-Work\output")
        if not scan_dir.exists():
            return []
        videos = []
        for ext in ("*.mp4", "*.mov", "*.avi", "*.mkv"):
            for f in scan_dir.glob(ext):
                videos.append({
                    "path": str(f),
                    "name": f.name,
                    "size": f.stat().st_size,
                })
        log(f"  扫描到 {len(videos)} 个本地视频")
        return videos


# ================================================================
#  Phase 2: 视觉分析
# ================================================================
class VisualAnalyzer:
    """分析视频素材的视觉特征"""

    def analyze(self, video_path: str) -> dict[str, Any]:
        """用 OpenCV 分析视频视觉特征"""
        import cv2
        import numpy as np

        log(f"分析视频: {Path(video_path).name}")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": f"无法打开: {video_path}"}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps
        log(f"  {w}x{h}, {fps}fps, {duration:.1f}s, {total_frames}帧")

        # 采样分析
        step = max(1, total_frames // 100)
        brightness_list = []
        saturations = []
        scenes = []
        prev_hist = None
        colors_dominant = []

        for i in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            brightness = float(np.mean(gray))
            saturation = float(np.mean(hsv[:, :, 1]))
            brightness_list.append(brightness)
            saturations.append(saturation)

            # 主色调
            hist = cv2.normalize(cv2.calcHist([gray], [0], None, [64], [0, 256]),
                                 None).flatten()
            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                if diff > 0.3:
                    scenes.append({"frame": i, "time": round(i / fps, 1),
                                   "diff": round(diff, 3)})
            prev_hist = hist

            # 色彩分布 (BGR 通道均值)
            b, g, r = float(np.mean(frame[:,:,0])), float(np.mean(frame[:,:,1])), float(np.mean(frame[:,:,2]))
            colors_dominant.append({"r": r, "g": g, "b": b})

        cap.release()

        avg_brightness = sum(brightness_list) / len(brightness_list) if brightness_list else 50
        avg_saturation = sum(saturations) / len(saturations) if saturations else 50

        # 情绪推断
        mood = self._infer_mood(avg_brightness, avg_saturation, len(scenes), duration)

        result = {
            "width": w, "height": h, "fps": fps,
            "duration": round(duration, 1),
            "total_frames": total_frames,
            "avg_brightness": round(avg_brightness, 1),
            "avg_saturation": round(avg_saturation, 1),
            "scene_changes": len(scenes),
            "cut_rate": round(len(scenes) / max(duration, 1), 2),
            "mood": mood,
            "color_profile": self._avg_color(colors_dominant),
            "motion_level": self._motion_level(len(scenes), duration),
        }
        log(f"  分析完成: mood={mood}, brightness={avg_brightness:.0f}, "
            f"scenes={len(scenes)}, cut_rate={result['cut_rate']}")
        return result

    def _infer_mood(self, brightness: float, saturation: float,
                    scene_count: int, duration: float) -> str:
        cut_rate = scene_count / max(duration, 1)
        if brightness < 40 and saturation < 40:
            return "dark_serious"
        elif brightness < 50 and cut_rate > 1.5:
            return "intense_action"
        elif brightness > 70 and saturation > 60:
            return "bright_cheerful"
        elif brightness > 60 and cut_rate < 0.5:
            return "calm_epic"
        elif cut_rate > 2.0:
            return "fast_paced"
        else:
            return "cinematic"

    def _motion_level(self, scenes: int, duration: float) -> str:
        rate = scenes / max(duration, 1)
        if rate > 2.0:
            return "high"
        elif rate > 0.8:
            return "medium"
        return "low"

    def _avg_color(self, colors: list[dict]) -> dict:
        if not colors:
            return {"r": 128, "g": 128, "b": 128}
        n = len(colors)
        return {
            "r": round(sum(c["r"] for c in colors) / n, 1),
            "g": round(sum(c["g"] for c in colors) / n, 1),
            "b": round(sum(c["b"] for c in colors) / n, 1),
        }


# ================================================================
#  Phase 3: AI 剧本生成
# ================================================================
class ScriptGenerator:
    """用 LLM + 知识库生成剪辑剧本"""

    def __init__(self):
        # DuckMiss Claude (主力 - 更高质量)
        self.duck_key = ENV.get("DUCK_MISS_API_KEY", "")
        self.duck_key_backup = ENV.get("DUCK_MISS_API_KEY_BACKUP", "")
        self.duck_url = ENV.get("DUCK_MISS_BASE_URL", "https://duckmiss.site/v1")
        self.duck_model = ENV.get("DUCK_MISS_DEFAULT_MODEL", "claude-sonnet-4-6")
        # ARK (备用) — 必须用 endpoint ID，模型名对复杂 prompt 返回空
        self.ark_key = ENV.get("DOUBAO_API_KEY", "")
        self.ark_url = "https://ark.cn-beijing.volces.com/api/v3"
        self.ark_model = ENV.get("ARK_ENDPOINT_TEXT",
                         ENV.get("ARK_ENDPOINT_VISION",
                         ENV.get("ARK_MODEL_FLASH", "deepseek-v4-flash-260425")))

    def generate_script(self, user_prompt: str,
                        material_analyses: list[dict],
                        style: str = "cinematic") -> dict[str, Any]:
        """生成完整剪辑剧本"""
        log(f"生成剧本: 风格={style}")

        # 构建素材分析摘要
        material_summary = []
        for i, ma in enumerate(material_analyses):
            material_summary.append(
                f"素材{i+1}: {ma.get('width','?')}x{ma.get('height','?')}, "
                f"{ma.get('duration','?')}s, 情绪={ma.get('mood','?')}, "
                f"亮度={ma.get('avg_brightness','?')}, "
                f"切镜率={ma.get('cut_rate','?')}"
            )

        # 知识库风格配方
        style_recipe = self._get_style_recipe(style)

        system_prompt = """你是专业的短视频剪辑导演，精通电影感混剪。
你需要根据用户需求和素材分析结果，生成完整的剪辑剧本（JSON格式）。

输出JSON必须包含以下结构:
{
  "title": "作品标题",
  "total_duration": 总时长(秒),
  "resolution": {"width": 宽, "height": 高},
  "fps": 帧率,
  "segments": [
    {
      "name": "段落名",
      "type": "intro|build|drop|break|outro",
      "start": 开始时间,
      "end": 结束时间,
      "material_index": 使用的素材编号(1-based),
      "mood": "情绪描述",
      "camera": {
        "movement": "推|拉|摇|移|跟|环绕",
        "speed": "slow|normal|fast",
        "technique": "具体技法名"
      },
      "text_overlay": {
        "text": "叠加文字",
        "position": "top|center|bottom",
        "font_size": 字号,
        "color": "颜色",
        "animation": "fade_in|slide_up|scale_bounce|typewriter"
      },
      "effects": ["效果1", "效果2"],
      "transition_to_next": "crossfade|wipe|zoom|dissolve|cut"
    }
  ],
  "color_grading": {
    "temperature": 色温(-100~100),
    "tint": 色调(-100~100),
    "contrast": 对比度(-100~100),
    "saturation": 饱和度(-100~100)
  },
  "bgm_mood": "背景音乐情绪关键词"
}

规则:
- 每个段落 2-5 秒
- 文字要有叙事感，电影字幕风格
- 运镜要有电影感
- Drop段要密集高能，Break段要留白
- 只输出JSON"""

        user_content = f"""需求: {user_prompt}

素材分析结果:
{chr(10).join(material_summary)}

风格方向: {style}
{style_recipe}

请生成完整剪辑剧本JSON。"""

        # 调用 LLM
        script_json = self._call_llm(system_prompt, user_content)
        if script_json:
            log(f"  剧本生成成功: {script_json.get('title', '?')}, "
                f"{len(script_json.get('segments', []))} 个段落")
            return script_json
        else:
            log("  LLM 调用失败，使用规则生成 fallback 剧本", "WARN")
            return self._fallback_script(user_prompt, material_analyses, style)

    def _call_llm(self, system: str, user: str) -> dict | None:
        """调用 LLM API (优先 llm_gateway 网关, DuckMiss/ARK 直连兜底)"""
        # 优先走统一网关（收编直连调用，由网关负责路由/降级/脱敏）
        result = self._call_via_gateway(system, user)
        if result:
            return result
        # 尝试 DuckMiss (Claude - 更高质量)
        if self.duck_key:
            result = self._call_duckmiss(system, user, self.duck_key)
            if result:
                return result
        # 尝试 DuckMiss 备用 Key
        if self.duck_key_backup:
            result = self._call_duckmiss(system, user, self.duck_key_backup)
            if result:
                return result
        # 尝试 ARK API
        if self.ark_key:
            result = self._call_ark(system, user)
            if result:
                return result
        log("  所有 LLM API 不可用，使用 fallback", "WARN")
        return None
    
    def _call_via_gateway(self, system: str, user: str) -> dict | None:
        """通过 core/llm_gateway 统一网关调用 LLM

        异步网关在同步上下文中通过 asyncio.run 桥接；若 import 失败或已有
        运行中的事件循环，则返回 None 让上层降级到原有直连 HTTP 调用。
        """
        try:
            import asyncio

            from core.llm_gateway import llm_gateway
        except Exception as e:
            log(f"  llm_gateway 不可用，降级直连: {e}", "DEBUG")
            return None
        # 幂等初始化：确保已加载 .env/.env.doubao 并装配多 Provider（含 DuckMiss Claude / ARK / ModelScope）
        try:
            ensure = getattr(llm_gateway, "ensure_configured", None)
            if ensure:
                ensure()
        except Exception as e:
            log(f"  llm_gateway 初始化失败: {e}", "WARN")
        # 已有运行中的事件循环时 asyncio.run 会报错，此时降级到同步直连
        try:
            asyncio.get_running_loop()
            log("  检测到运行中的事件循环，降级直连 HTTP", "DEBUG")
            return None
        except RuntimeError:
            pass
        try:
            response = asyncio.run(llm_gateway.chat(
                message=user,
                system_prompt=system,
                temperature=0.7,
                max_tokens=4000,
            ))
        except Exception as e:
            log(f"  llm_gateway 调用异常: {e}", "WARN")
            return None
        if not response or not getattr(response, "success", False):
            log(f"  llm_gateway 返回失败: {getattr(response, 'error', '')}", "WARN")
            return None
        content = getattr(response, "content", "") or ""
        # 保留原有 JSON 解析逻辑（剥离 ```json 代码块）
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        try:
            parsed = json.loads(content)
        except Exception as e:
            log(f"  llm_gateway 响应 JSON 解析失败: {e}", "WARN")
            return None
        log(f"  llm_gateway 调用成功 ({getattr(response, 'model', '?')})")
        return parsed

    @staticmethod
    def _extract_json(content: str) -> dict | None:
        """从 LLM 返回文本中提取 JSON (多级降级)"""
        if not content or not content.strip():
            return None
        # 1. 直接解析
        try:
            return json.loads(content.strip())
        except Exception:
            pass
        # 2. 剥离 ```json ... ``` 代码块
        import re
        m = re.search(r'```json\s*([\s\S]*?)```', content)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except Exception:
                pass
        # 3. 剥离 ``` ... ```
        m = re.search(r'```\s*([\s\S]*?)```', content)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except Exception:
                pass
        # 4. 贪婪匹配最外层 { ... }
        m = re.search(r'\{[\s\S]*\}', content)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return None

    def _call_ark(self, system: str, user: str) -> dict | None:
        """火山方舟 ARK API"""
        try:
            import urllib.request
            url = f"{self.ark_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.ark_key}",
            }
            data = json.dumps({
                "model": self.ark_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
                "max_tokens": 4000,
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._extract_json(content)
            if parsed:
                log(f"  ARK API 调用成功 ({self.ark_model})")
                return parsed
            log(f"  ARK 返回内容无法解析为JSON (长度={len(content)}), 前200字: {content[:200]}", "WARN")
            return None
        except Exception as e:
            log(f"  ARK API 异常: {e}", "WARN")
            return None
    
    def _call_duckmiss(self, system: str, user: str, key: str = None) -> dict | None:
        """DuckMiss API (Claude)"""
        try:
            import urllib.request
            api_key = key or self.duck_key
            url = f"{self.duck_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0",
            }
            data = json.dumps({
                "model": self.duck_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
                "max_tokens": 4000,
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._extract_json(content)
            if parsed:
                log(f"  DuckMiss API 调用成功 ({self.duck_model})")
                return parsed
            log(f"  DuckMiss 返回内容无法解析为JSON (长度={len(content)})", "WARN")
            return None
        except urllib.error.HTTPError as e:
            log(f"  DuckMiss API HTTP {e.code}: {e.reason}", "WARN")
            return None
        except Exception as e:
            log(f"  DuckMiss API 异常: {e}", "WARN")
            return None

    def _get_style_recipe(self, style: str) -> str:
        """从知识库获取风格配方"""
        try:
            from video.style_template_library import STYLE_TEMPLATES
            tmpl = STYLE_TEMPLATES.get(style)
            if tmpl:
                effects_desc = []
                for fx in tmpl.get("effects", [])[:3]:
                    effects_desc.append(f"  - {fx['effectName']}")
                return (
                    f"风格配方 [{tmpl['display_name']}]:\n"
                    f"  描述: {tmpl['description']}\n"
                    f"  关键词: {', '.join(tmpl.get('keywords', []))}\n"
                    f"  效果:\n" + "\n".join(effects_desc)
                )
        except Exception:
            pass
        return f"参考风格: {style}"

    def _fallback_script(self, prompt: str, analyses: list[dict],
                         style: str) -> dict[str, Any]:
        """规则 fallback 剧本 — V2: NarrativeArcPlanner 能量包络版

        替代均分五等份: 段落时长比按能量包络(12/24/34/12/18)，
        切点对齐BPM网格，drop段70%处插入喘息点，
        运镜按多样性感知分配(8种专业运镜)。
        """
        n_materials = len(analyses) or 1
        total_dur = min(30, n_materials * 5)

        # 自动检测分辨率
        w, h = 1920, 1080
        if analyses:
            a = analyses[0]
            if a.get("height", 1080) > a.get("width", 1920):
                w, h = 1080, 1920  # 竖屏

        # 叙事弧线规划 (风格参数化)
        from core.camera_language import CAMERA_IDS, CameraLanguageLibrary
        from core.narrative_arc import NarrativeArcPlanner, StyleProfile
        try:
            planner_profile = StyleProfile().to_planner_profile(style or "")
        except Exception:
            planner_profile = {}
        bpm = 128
        planner = NarrativeArcPlanner()
        arc_segments = planner.plan_segments(total_dur, bpm,
                                             style_profile=planner_profile or None)
        camlib = CameraLanguageLibrary()

        mood_map = {"intro": "铺垫", "build": "升温", "drop": "高潮",
                    "break": "沉淀", "outro": "收尾", "breath_break": "喘息"}
        text_map = {"intro": "VINLAND SAGA", "build": "战斗开始",
                    "drop": "全力爆发", "break": "寂静时刻",
                    "outro": "传说不灭", "breath_break": ""}
        used_cams: list[str] = []
        segments = []
        for i, seg in enumerate(arc_segments):
            st = seg["type"]
            mat_idx = (i % n_materials) + 1
            # 多样性感知运镜分配: 优先段落偏好池中未用过的运镜
            # (基础8 + 段落适配3D摄像机池)
            pool = list((seg.get("camera_bias")
                         or camlib.cameras_for_segment(st) or CAMERA_IDS)
                        + camlib.cameras3d_for_segment(st))
            cam_id = (next((c for c in pool if c not in used_cams), None)
                      or next((c for c in CAMERA_IDS if c not in used_cams), None)
                      or pool[0])
            used_cams.append(cam_id)
            tmpl = camlib.get_template(cam_id) or {}
            inten = seg.get("intensity", "moderate")
            segments.append({
                "name": seg["name"],
                "type": st,
                "start": seg["start"],
                "end": seg["end"],
                "duration": seg["duration"],
                "energy_target": seg["energy_target"],
                "scene_tag": seg.get("scene_tag", ""),
                "cut_times": seg.get("cut_times", []),
                # 段落Z纵深: drop推进(纵深冲击) / break回拉(呼吸感)
                "z_depth": camlib.z_depth_for_segment(st),
                "material_index": mat_idx,
                "mood": mood_map.get(st, "中性"),
                "camera": {
                    "camera_id": cam_id,
                    "movement": tmpl.get("cn", cam_id),
                    "speed": {"intense": "fast", "moderate": "normal",
                              "gentle": "slow"}.get(inten, "normal"),
                    "technique": f"{cam_id}_camera",
                },
                "text_overlay": {
                    "text": text_map.get(st, ""),
                    "position": "center",
                    "font_size": 48 if st == "drop" else 36,
                    "color": "gold" if st in ("intro", "drop") else "white",
                    "animation": {"intro": "fade_in", "build": "slide_up",
                                  "drop": "scale_bounce", "break": "fade_in",
                                  "outro": "fade_in",
                                  "breath_break": "fade_in"}.get(st, "fade_in"),
                },
                "effects": (["Lumetri Color", "Glow"] if st == "drop"
                            else ["Lumetri Color"]),
                "transition_to_next": {
                    "intro": "crossfade", "build": "wipe",
                    "drop": "zoom", "break": "dissolve", "outro": "cut",
                    "breath_break": "cut",
                }.get(st, "cut"),
            })

        return {
            "title": f"AI Director - {prompt[:20]}",
            "total_duration": total_dur,
            "resolution": {"width": w, "height": h},
            "fps": 30,
            "bpm": bpm,
            "segments": segments,
            "color_grading": {
                "temperature": 10, "tint": -5,
                "contrast": 20, "saturation": 15,
            },
            "bgm_mood": "epic cinematic",
        }


# ================================================================
#  Phase 4: 剧本 → JSX 翻译器 (核心模块)
# ================================================================
class ScriptToJSXTranslator:
    """将 AI 剧本翻译为 AE 可执行的 JSX 脚本"""

    def translate(self, script: dict[str, Any],
                  material_paths: list[str]) -> str:
        """生成完整 JSX 脚本"""
        log("翻译剧本 → JSX...")

        res = script.get("resolution", {"width": 1920, "height": 1080})
        W = res.get("width", 1920)
        H = res.get("height", 1080)
        fps = script.get("fps", 30)
        total_dur = script.get("total_duration", 30)
        segments = script.get("segments", [])
        color_grade = script.get("color_grading", {})

        jsx_lines = []
        jsx_lines.append("// === AI Director Auto-Generated JSX ===")
        jsx_lines.append(f'var W = {W}, H = {H}, FPS = {fps};')
        jsx_lines.append(f'var TOTAL_DUR = {total_dur};')
        jsx_lines.append("")

        # 1. 创建主合成
        jsx_lines.append("// 1. 创建主合成")
        jsx_lines.append(
            f'var mainComp = app.project.items.addComp('
            f'"AI_Director_{int(time.time())}", {W}, {H}, 1, {total_dur}, {fps});'
        )
        jsx_lines.append("")

        # 2. 导入素材
        jsx_lines.append("// 2. 导入素材")
        for i, mp in enumerate(material_paths):
            safe_path = mp.replace("\\", "/")
            jsx_lines.append(f'var mat_{i+1} = null;')
            jsx_lines.append('try {')
            jsx_lines.append(f'  var io_{i+1} = new ImportOptions(File("{safe_path}"));')
            jsx_lines.append(f'  mat_{i+1} = app.project.importFile(io_{i+1});')
            jsx_lines.append(f'  mat_{i+1}.name = "Material_{i+1}";')
            jsx_lines.append('} catch(e) { }')
        jsx_lines.append("")

        # 3. 按段落创建图层和效果
        jsx_lines.append("// 3. 段落编排")
        # V2: 12运镜库 (8基础带Ease + 4真实3D摄像机null链) — 延迟导入避免硬依赖
        try:
            from core.camera_language import CAMERA_IDS_3D, CameraLanguageLibrary
            camlib = CameraLanguageLibrary()
        except Exception:
            camlib = None
            CAMERA_IDS_3D = []
        try:
            from core.effect_depth import EffectDepthLibrary
            efflib = EffectDepthLibrary()
        except Exception:
            efflib = None
        for seg_i, seg in enumerate(segments):
            mat_idx = seg.get("material_index", 1)
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 5)
            seg_dur = seg_end - seg_start
            mood = seg.get("mood", "")
            cam = seg.get("camera", {})
            text_ov = seg.get("text_overlay", {})

            jsx_lines.append(f'// --- Segment {seg_i+1}: {seg.get("name", "")} ({mood}) ---')

            # 素材图层
            jsx_lines.append(f'var seg{seg_i}_layer = null;')
            jsx_lines.append(f'if (typeof mat_{mat_idx} !== "undefined" && mat_{mat_idx}) {{')
            jsx_lines.append(f'  seg{seg_i}_layer = mainComp.layers.add(mat_{mat_idx});')
            jsx_lines.append(f'  seg{seg_i}_layer.name = "Seg{seg_i+1}_{seg.get("name", "")}";')
            # 时间重映射
            jsx_lines.append(f'  seg{seg_i}_layer.startTime = {seg_start};')
            jsx_lines.append(f'  seg{seg_i}_layer.outPoint = {seg_end};')

            # 摄像机运动 → CameraLanguageLibrary 8运镜 (带Ease曲线)
            cam_move = cam.get("movement", "推")
            cam_speed = cam.get("speed", "normal")
            speed_factor = {"slow": 0.5, "normal": 1.0, "fast": 2.0}.get(cam_speed, 1.0)

            jsx_lines.append(f'  // Camera: {cam_move} ({cam_speed})')
            scale_prop = f'seg{seg_i}_layer.property("ADBE Transform Group").property("ADBE Scale")'
            pos_prop = f'seg{seg_i}_layer.property("ADBE Transform Group").property("ADBE Position")'

            cam_id = cam.get("camera_id")
            if cam_id is None and camlib is not None:
                cam_id = camlib.camera_by_cn(cam_move)
            if camlib is not None and cam_id in CAMERA_IDS_3D:
                # 3D摄像机链: camera → null → layer, 关键帧打在null上
                jsx_lines.append('  ' + camlib.to_jsx_3d(
                    cam_id, f'seg{seg_i}_layer', 'mainComp',
                    seg_start, seg_end,
                    z_depth=seg.get("z_depth", 0.0),
                    speed_factor=speed_factor, uid=f"seg{seg_i}"))
            elif camlib is not None and cam_id is not None:
                # 新管线: 带 KeyframeEase 缓动的专业运镜 (scale≤150%防糊)
                jsx_lines.append('  ' + camlib.to_jsx(cam_id, f'seg{seg_i}_layer',
                                                      seg_start, seg_end, speed_factor))
            elif cam_move == "推":
                # 旧格式兼容降级: 线性两点关键帧
                jsx_lines.append(f'  {scale_prop}.setValueAtTime({seg_start}, [100, 100]);')
                jsx_lines.append(f'  {scale_prop}.setValueAtTime({seg_end}, [{100 + 15 * speed_factor}, {100 + 15 * speed_factor}]);')
            elif cam_move == "拉":
                jsx_lines.append(f'  {scale_prop}.setValueAtTime({seg_start}, [{100 + 20 * speed_factor}, {100 + 20 * speed_factor}]);')
                jsx_lines.append(f'  {scale_prop}.setValueAtTime({seg_end}, [100, 100]);')
            elif cam_move == "摇":
                jsx_lines.append(f'  {pos_prop}.setValueAtTime({seg_start}, [W/2 - 50, H/2, 0]);')
                jsx_lines.append(f'  {pos_prop}.setValueAtTime({seg_end}, [W/2 + 50, H/2, 0]);')
            elif cam_move == "快推":
                jsx_lines.append(f'  {scale_prop}.setValueAtTime({seg_start}, [100, 100]);')
                jsx_lines.append(f'  {scale_prop}.setValueAtTime({seg_start + seg_dur * 0.3}, [{100 + 30 * speed_factor}, {100 + 30 * speed_factor}]);')
                jsx_lines.append(f'  {scale_prop}.setValueAtTime({seg_end}, [{100 + 10 * speed_factor}, {100 + 10 * speed_factor}]);')

            # 运镜×效果联动 (whip+drop→RGB分离+速度线; break→柔光降饱和)
            if efflib is not None and cam_id:
                lk_jsx = efflib.link_jsx(f'seg{seg_i}_layer', 'mainComp',
                                         cam_id, seg.get("type", ""),
                                         seg_start, seg_end)
                if lk_jsx:
                    jsx_lines.append('  ' + lk_jsx.replace('\n', '\n  '))

            # 淡入淡出
            op_prop = f'seg{seg_i}_layer.property("ADBE Transform Group").property("ADBE Opacity")'
            jsx_lines.append(f'  {op_prop}.setValueAtTime({seg_start}, 0);')
            jsx_lines.append(f'  {op_prop}.setValueAtTime({seg_start + 0.3}, 100);')
            jsx_lines.append(f'  {op_prop}.setValueAtTime({seg_end - 0.3}, 100);')
            jsx_lines.append(f'  {op_prop}.setValueAtTime({seg_end}, 0);')
            jsx_lines.append('}')

            # 文字叠加
            if text_ov and text_ov.get("text"):
                txt = text_ov["text"].replace('"', '\\"')
                font_size = text_ov.get("font_size", 36)
                color = text_ov.get("color", "white")
                anim = text_ov.get("animation", "fade_in")
                position = text_ov.get("position", "center")

                # 颜色映射 (支持 hex 和命名)
                color_jsx = self._resolve_color(color)

                # 位置映射
                pos_map = {
                    "top": "[W/2, H*0.15, 0]",
                    "center": "[W/2, H/2, 0]",
                    "bottom": "[W/2, H*0.85, 0]",
                }
                pos_jsx = pos_map.get(position, "[W/2, H/2, 0]")

                jsx_lines.append(f'// Text: {txt}')
                jsx_lines.append(f'var txt{seg_i} = mainComp.layers.addText("{txt}");')
                jsx_lines.append(f'var tdp{seg_i} = txt{seg_i}.property("ADBE Text Properties").property("ADBE Text Document");')
                jsx_lines.append(f'var tdoc{seg_i} = tdp{seg_i}.value;')
                jsx_lines.append(f'tdoc{seg_i}.fontSize = {font_size};')
                jsx_lines.append(f'tdoc{seg_i}.fillColor = {color_jsx};')
                jsx_lines.append(f'tdoc{seg_i}.justification = ParagraphJustification.CENTER_JUSTIFY;')
                jsx_lines.append(f'tdp{seg_i}.setValue(tdoc{seg_i});')
                jsx_lines.append(f'txt{seg_i}.property("ADBE Transform Group").property("ADBE Position").setValue({pos_jsx});')

                # 文字动画
                txt_op = f'txt{seg_i}.property("ADBE Transform Group").property("ADBE Opacity")'
                txt_sc = f'txt{seg_i}.property("ADBE Transform Group").property("ADBE Scale")'
                if anim == "fade_in":
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_start}, 0);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_start + 0.5}, 100);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_end - 0.5}, 100);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_end}, 0);')
                elif anim == "scale_bounce":
                    jsx_lines.append(f'{txt_sc}.setValueAtTime({seg_start}, [50, 50]);')
                    jsx_lines.append(f'{txt_sc}.setValueAtTime({seg_start + 0.3}, [115, 115]);')
                    jsx_lines.append(f'{txt_sc}.setValueAtTime({seg_start + 0.6}, [100, 100]);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_start}, 0);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_start + 0.2}, 100);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_end - 0.3}, 100);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_end}, 0);')
                elif anim == "slide_up":
                    txt_pos = f'txt{seg_i}.property("ADBE Transform Group").property("ADBE Position")'
                    jsx_lines.append(f'{txt_pos}.setValueAtTime({seg_start}, [W/2, H/2 + 50, 0]);')
                    jsx_lines.append(f'{txt_pos}.setValueAtTime({seg_start + 0.5}, {pos_jsx});')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_start}, 0);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_start + 0.3}, 100);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_end - 0.3}, 100);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_end}, 0);')
                else:
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_start}, 0);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_start + 0.3}, 100);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_end - 0.3}, 100);')
                    jsx_lines.append(f'{txt_op}.setValueAtTime({seg_end}, 0);')

            # 效果
            effects = seg.get("effects", [])
            if effects:
                jsx_lines.append(f'// Effects for segment {seg_i+1}')
                jsx_lines.append(f'if (seg{seg_i}_layer) {{')
                for fx_name in effects:
                    ae_fx = self._map_effect_name(fx_name)
                    if ae_fx:
                        jsx_lines.append(f'  try {{ seg{seg_i}_layer.property("ADBE Effect Parade").addProperty("{ae_fx}"); }} catch(e) {{}}')
                jsx_lines.append('}')

            jsx_lines.append("")

        # 4. 调色调整层
        jsx_lines.append("// 4. 调色调整层")
        jsx_lines.append('var colorAdj = mainComp.layers.addSolid([0.5,0.5,0.5], "Color_Grade", W, H, 1, TOTAL_DUR);')
        jsx_lines.append('colorAdj.adjustmentLayer = true;')
        jsx_lines.append('colorAdj.moveToEnd();')
        jsx_lines.append('var lumetri = colorAdj.property("ADBE Effect Parade").addProperty("ADBE Lumetri");')
        if color_grade.get("temperature"):
            jsx_lines.append(f'try {{ lumetri.property("Temperature").setValue({color_grade["temperature"]}); }} catch(e) {{}}')
        if color_grade.get("contrast"):
            jsx_lines.append(f'try {{ lumetri.property("Contrast").setValue({color_grade["contrast"]}); }} catch(e) {{}}')
        if color_grade.get("saturation"):
            jsx_lines.append(f'try {{ lumetri.property("Saturation").setValue({color_grade["saturation"]}); }} catch(e) {{}}')
        jsx_lines.append("")

        # 5. 摄像机 (3D)
        jsx_lines.append("// 5. 摄像机")
        jsx_lines.append('var cam = mainComp.layers.addCamera("Director_Cam", [W/2, H/2]);')
        jsx_lines.append('var camOpt = cam.property("ADBE Camera Options Group");')
        jsx_lines.append('try { camOpt.property("ADBE Camera Zoom").setValue(W); } catch(e) {}')
        jsx_lines.append('try { camOpt.property("ADBE Camera Depth of Field").setValue(1); } catch(e) {}')
        # 摄像机缓慢推进
        cam_pos = 'cam.property("ADBE Transform Group").property("ADBE Position")'
        jsx_lines.append(f'{cam_pos}.setValueAtTime(0, [W/2, H/2, -500]);')
        jsx_lines.append(f'{cam_pos}.setValueAtTime(TOTAL_DUR, [W/2, H/2, -300]);')
        jsx_lines.append("")

        # 6. 渲染输出
        jsx_lines.append("// 6. 渲染输出")
        out_path = str(OUTPUT_DIR).replace("\\", "/")
        jsx_lines.append(f'var outDir = new Folder("{out_path}");')
        jsx_lines.append('if (!outDir.exists) outDir.create();')
        jsx_lines.append('mainComp.renderSettings = {')
        jsx_lines.append('  "outputModule": "Lossless",')
        jsx_lines.append('};')
        jsx_lines.append("")
        jsx_lines.append('var rqItem = app.project.renderQueue.items.add(mainComp);')
        jsx_lines.append('var om = rqItem.outputModule(1);')
        jsx_lines.append(f'om.file = new File("{out_path}/director_output.mp4");')
        jsx_lines.append('app.project.renderQueue.render();')
        jsx_lines.append("")
        jsx_lines.append('JSON.stringify({success: true, comp: mainComp.name, layers: mainComp.numLayers});')

        jsx_code = "\n".join(jsx_lines)
        log(f"  JSX 生成完成: {len(jsx_lines)} 行, {len(jsx_code)} 字符")
        return jsx_code

    def _map_effect_name(self, name: str) -> str:
        """效果名映射: 显示名 → AE matchName（使用 effect_registry + 知识库）"""
        try:
            from effects.effect_registry import KEYWORD_TO_EFFECT_MAP, get_effect_matchname
            ae_fx = get_effect_matchname(name)
            if ae_fx:
                return ae_fx
        except Exception:
            pass

        effect_map = {
            "Lumetri Color": "ADBE Lumetri",
            "Glow": "ADBE Glo2",
            "Gaussian Blur": "ADBE Gaussian Blur 2",
            "Brightness & Contrast": "ADBE Brightness & Contrast 2",
            "Color Balance": "ADBE Color Balance",
            "Vignette": "ADBE Vignette",
            "Noise": "ADBE Noise",
            "Sharpen": "ADBE Sharpen",
            "Curves": "ADBE CurvesCustom",
            "Hue/Saturation": "ADBE Hue/Saturation",
            "Fast Box Blur": "ADBE Fast Box Blur",
            "Turbulent Displace": "ADBE ATRC",
            "CC Light Sweep": "CC Light Sweep",
            "Particular": "Particular",
            "slow_motion": "",
            "reverse": "",
        }
        return effect_map.get(name, name if name.startswith("ADBE") or name.startswith("CC") else "")

    def _resolve_color(self, color: str) -> str:
        """解析颜色: 支持 hex (#FF4C4C) 和命名 (gold/white)"""
        if not color:
            return "[1, 1, 1]"
        # Hex 颜色
        if color.startswith("#"):
            hex_str = color.lstrip("#")
            if len(hex_str) == 6:
                r = int(hex_str[0:2], 16) / 255.0
                g = int(hex_str[2:4], 16) / 255.0
                b = int(hex_str[4:6], 16) / 255.0
                return f"[{r:.2f}, {g:.2f}, {b:.2f}]"
        # 命名颜色
        named = {
            "gold": "[1, 0.85, 0.2]",
            "white": "[1, 1, 1]",
            "red": "[1, 0.2, 0.2]",
            "cyan": "[0.2, 1, 1]",
            "yellow": "[1, 1, 0.2]",
            "silver": "[0.75, 0.75, 0.75]",
        }
        return named.get(color.lower(), "[1, 1, 1]")


# ================================================================
#  Phase 5: AE 执行器
# ================================================================
class AEExecutor:
    """通过 MCP Bridge 在 AE 中执行 JSX"""

    def __init__(self):
        self.client = None

    def connect(self) -> bool:
        """连接到 AE Bridge"""
        try:
            from ae_mcp_client import AEMCPClient
            self.client = AEMCPClient()
            result = self.client.send_command("ping", {})
            if result and result.get("status") != "error":
                log("AE Bridge 已连接")
                return True
        except Exception as e:
            log(f"AE Bridge 连接失败: {e}", "WARN")
        # Fallback: 文件系统方式
        log("尝试文件系统方式...", "WARN")
        self.client = None
        return True

    def execute_jsx(self, jsx_code: str) -> dict:
        """执行 JSX 脚本"""
        if self.client:
            try:
                result = self.client.send_command("execute_script", {"script": jsx_code})
                return result or {"success": False, "error": "No response"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return self._execute_via_filesystem(jsx_code)

    def _execute_via_filesystem(self, jsx_code: str) -> dict:
        """通过文件系统执行 (ae_command.json → ae_result.json)"""
        cmd_file = PROJECT_ROOT / "ae_command.json"
        res_file = PROJECT_ROOT / "ae_result.json"

        cmd = {
            "status": "pending",
            "command": "execute_script",
            "args": {"script": jsx_code},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        with open(cmd_file, "w", encoding="utf-8") as f:
            json.dump(cmd, f, ensure_ascii=False)
        log("  命令已写入 ae_command.json，等待 AE 执行...")

        # 等待结果
        for _ in range(60):
            time.sleep(2)
            if res_file.exists():
                try:
                    with open(res_file, "r", encoding="utf-8") as f:
                        result = json.load(f)
                    if result.get("status") in ("success", "completed", "error"):
                        return result
                except Exception:
                    pass
        return {"success": False, "error": "Timeout waiting for AE"}


# ================================================================
#  主编排器: AIDirector
# ================================================================
class AIDirector:
    """AI 导演系统 - 从描述到成品的完整自动化"""

    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.collector = MaterialCollector(self.output_dir)
        self.analyzer = VisualAnalyzer()
        self.script_gen = ScriptGenerator()
        self.translator = ScriptToJSXTranslator()
        self.executor = AEExecutor()
        # === 新增: 素材搜索与AI生成引擎 ===
        self.material_searcher = None  # 延迟初始化
        self.aigc_generator = None     # 延迟初始化
        # 3D 舞台编排器 (延迟初始化)
        self._stage3d = None
        # 风格迁移引擎 (延迟初始化)
        self._style_migrator = None
        # 音频剪辑引擎 (延迟初始化)
        self._audio_engine = None

    def _get_material_searcher(self):
        """获取素材搜索器 (延迟初始化)"""
        if self.material_searcher is None:
            from material_searcher import MaterialSearcher
            self.material_searcher = MaterialSearcher(self.output_dir / "materials")
        return self.material_searcher

    def _get_aigc_generator(self):
        """获取AI生成器 (延迟初始化)"""
        if self.aigc_generator is None:
            from aigc_generator import AIGCGenerator
            self.aigc_generator = AIGCGenerator(self.output_dir / "materials")
        return self.aigc_generator

    def _get_stage3d(self, w: int, h: int, dur: float, fps: float):
        if self._stage3d is None:
            from stage_3d_director import Stage3DDirector
            self._stage3d = Stage3DDirector(width=w, height=h, duration=dur, fps=fps)
        return self._stage3d

    def produce(self, user_prompt: str,
                material_urls: list[str] = None,
                material_paths: list[str] = None,
                style: str = "cinematic",
                auto_launch_ae: bool = True,
                enable_3d_stage: bool = True,
                enable_style_migration: bool = True,
                reference_video: str = None,
                audio_path: str = None,
                enable_audio_edit: bool = True) -> dict[str, Any]:
        """
        完整生产流程。

        Args:
            user_prompt: 用户描述 (如 "利威尔高燃混剪, 30秒, 竖屏")
            material_urls: 要下载的素材 URL
            material_paths: 本地素材路径
            style: 风格 (cinematic/cyberpunk/dreamy/...)
            auto_launch_ae: 是否自动启动 AE
        """
        start_time = time.time()
        report = {"prompt": user_prompt, "style": style, "phases": {}}

        print("\n" + "=" * 60)
        print(f"  AI Director - {user_prompt}")
        print(f"  风格: {style}")
        print("=" * 60)

        # ── Phase 1: 素材搜集 (新工作流: 搜索下载 → 筛选 → AI补充) ──
        print("\n--- Phase 1: 素材搜集 (搜索+AI补充) ---")
        material_files = []

        # Step 1: 处理用户提供的URL和本地路径
        if material_urls:
            results = self.collector.collect_from_urls(material_urls)
            material_files.extend([r["path"] for r in results if r.get("success") and r.get("path")])
        if material_paths:
            results = self.collector.collect_from_local(material_paths)
            material_files.extend([r["path"] for r in results if r.get("success")])

        # Step 2: 主动搜索下载素材 (核心改进)
        min_materials = 3  # 最少需要的素材数量
        if len(material_files) < min_materials:
            log(f"用户素材不足 ({len(material_files)}/{min_materials})，启动主动搜索...")
            try:
                searcher = self._get_material_searcher()
                search_results = searcher.search(
                    user_prompt=user_prompt,
                    material_urls=material_urls,
                    min_results=min_materials,
                    max_per_source=3,
                )
                # 添加搜索到的素材
                for r in search_results:
                    if r.get("success") and r.get("path"):
                        material_files.append(r["path"])
                log(f"搜索完成，当前素材: {len(material_files)} 个")
            except Exception as e:
                log(f"素材搜索失败(非致命): {e}", "WARN")

        # Step 3: 扫描本地素材库作为补充
        if len(material_files) < min_materials:
            log("扫描本地素材库...")
            local = self.collector.scan_local_library()
            for v in local[:min_materials - len(material_files)]:
                material_files.append(v["path"])

        # Step 4: AI生成补充素材 (当真实素材仍然不足时)
        if len(material_files) < min_materials:
            missing = min_materials - len(material_files)
            log(f"真实素材仍不足，启动AI生成补充 ({missing} 个)...")
            try:
                generator = self._get_aigc_generator()
                aigc_results = generator.generate_supplementary(
                    user_prompt=user_prompt,
                    missing_count=missing,
                    style=style,
                    material_type="video",
                )
                _ingest_aigc_results(aigc_results, material_files)  # FIX-05：Mock/simulated 永不入池
            except Exception as e:
                log(f"AI生成失败(非致命): {e}", "WARN")

        # 最终报告
        report["phases"]["collection"] = {
            "total": len(material_files),
            "files": [Path(f).name for f in material_files],
            "sources": {
                "user_provided": material_urls is not None or material_paths is not None,
                "searched": len(material_files) > 0,
                "aigc_supplemented": any("aigc_" in Path(f).name for f in material_files),
            }
        }
        log(f"素材就绪: {len(material_files)} 个")

        # ── Phase 2: 视觉分析 ──
        print("\n--- Phase 2: 视觉分析 ---")
        analyses = []
        for mf in material_files[:5]:
            try:
                analysis = self.analyzer.analyze(mf)
                analysis["source"] = mf
                analyses.append(analysis)
            except Exception as e:
                log(f"  分析失败: {e}", "ERROR")

        report["phases"]["analysis"] = {
            "analyzed": len(analyses),
            "summaries": [{"name": Path(a.get("source", "")).name,
                           "mood": a.get("mood"),
                           "duration": a.get("duration")} for a in analyses],
        }

        # ── Phase 2.5: 风格迁移 ──
        style_info = {}
        if enable_style_migration and reference_video and os.path.exists(reference_video):
            print("\n--- Phase 2.5: 风格迁移 ---")
            try:
                if self._style_migrator is None:
                    from style_migrator import StyleMigrator
                    self._style_migrator = StyleMigrator()
                fingerprint = self._style_migrator.extractor.extract(reference_video)
                match = self._style_migrator.matcher.match(fingerprint)
                style_info = {
                    "style_name": match["style_name"],
                    "style_score": match["style_score"],
                    "tags": fingerprint.get("style_tags", []),
                    "color_mood": fingerprint.get("color", {}).get("color_mood", "balanced"),
                    "rhythm": fingerprint.get("rhythm", {}).get("rhythm_type", "moderate"),
                    "energy": fingerprint.get("energy", {}).get("level", "medium"),
                }
                # 用迁移风格覆盖默认风格
                if match["style_name"]:
                    style = match["style_name"]
                log(f"  风格迁移: {match['style_name']} (score={match['style_score']})")
                log(f"  标签: {', '.join(fingerprint.get('style_tags', []))}")
                report["phases"]["style_migration"] = style_info
            except Exception as e:
                log(f"  风格迁移失败(非致命): {e}", "WARN")

        # ── Phase 2.7: 音频分析 ──
        audio_info = {}
        if enable_audio_edit and audio_path and os.path.exists(audio_path):
            print("\n--- Phase 2.7: 音频分析 ---")
            try:
                if self._audio_engine is None:
                    from audio_edit_engine import AudioEditEngine
                    self._audio_engine = AudioEditEngine(self.output_dir)
                audio_features = self._audio_engine.analyzer.analyze(audio_path)
                audio_info = {
                    "bpm": audio_features.get("bpm", 128),
                    "duration": audio_features.get("duration", 0),
                    "beats": len(audio_features.get("beats", [])),
                    "mood": audio_features.get("mood", "neutral"),
                    "genre": audio_features.get("genre", "unknown"),
                }
                # 生成 EDL
                edl = self._audio_engine.edl_gen.generate(audio_features, material_count=len(material_files))
                audio_info["edl_clips"] = len(edl)
                # 用音频节奏影响剧本
                if audio_features.get("bpm", 0) > 140:
                    style = "high_energy"
                elif audio_features.get("bpm", 0) < 80:
                    style = "slow_cinematic"
                log(f"  音频: BPM={audio_info['bpm']}, {audio_info['beats']} beats, mood={audio_info['mood']}")
                report["phases"]["audio_analysis"] = audio_info
            except Exception as e:
                log(f"  音频分析失败(非致命): {e}", "WARN")

        # ── Phase 3: AI 剧本 ──
        print("\n--- Phase 3: AI 剧本生成 ---")
        script = self.script_gen.generate_script(user_prompt, analyses, style)

        # Phase 3.5: /refine 自改进循环 (借鉴Prime Agent: 轨迹驱动确定性修补,
        # 零LLM成本; 隔离异常不阻断主管线)
        try:
            from core.refine_loop import DirectorRefineLoop
            refine_result = DirectorRefineLoop(
                target_score=90, max_iterations=3).refine_script(script)
            report["phases"]["refine"] = {
                "initial_score": refine_result["initial_score"],
                "final_score": refine_result["final_score"],
                "iterations": refine_result["iterations"],
                "actions": [a for t in refine_result["trajectory"]
                            for a in t["actions"]],
            }
            log(f"  /refine 自改进: {refine_result['initial_score']} → "
                f"{refine_result['final_score']} "
                f"({refine_result['iterations']}轮)")
        except Exception as e:
            log(f"  /refine 跳过(非致命): {e}", "WARN")

        report["phases"]["script"] = {
            "title": script.get("title"),
            "duration": script.get("total_duration"),
            "segments": len(script.get("segments", [])),
        }

        # 保存剧本
        script_path = self.output_dir / "director_script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
        log(f"  剧本已保存: {script_path}")

        # ── Phase 4: JSX 翻译 ──
        print("\n--- Phase 4: 剧本 → JSX ---")
        jsx_code = self.translator.translate(script, material_files)
        jsx_path = self.output_dir / "director_script.jsx"
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx_code)
        log(f"  JSX 已保存: {jsx_path}")
        report["phases"]["translation"] = {"jsx_lines": len(jsx_code.splitlines())}

        # ── Phase 4.5: 3D 舞台增强 ──
        if enable_3d_stage:
            print("\n--- Phase 4.5: 3D 舞台增强 ---")
            try:
                res = script.get("resolution", {"width": 1920, "height": 1080})
                stage3d = self._get_stage3d(
                    res.get("width", 1920), res.get("height", 1080),
                    script.get("total_duration", 30), script.get("fps", 30)
                )
                # 根据剧本选择摄像机运动和布光
                segments = script.get("segments", [])
                cam_move = "push_in"
                lighting = "cinematic"
                for seg in segments:
                    if seg.get("type") == "drop":
                        cam_move = seg.get("camera", {}).get("movement", "push_in")
                        break
                # 映射 mood 到布光
                mood_map = {"intense_action": "dramatic", "dark_serious": "dark",
                            "bright_cheerful": "soft", "calm_epic": "cinematic"}
                if analyses:
                    analysis_mood = analyses[0].get("mood", "")
                    lighting = mood_map.get(analysis_mood, "cinematic")

                stage_jsx = stage3d.generate_full_stage(
                    material_paths=material_files[:5],
                    camera_movement=cam_move,
                    lighting_mood=lighting,
                    transitions=[{"type": "cube_flip_y", "duration": 0.8}]
                )
                # 追加到主 JSX
                jsx_code += "\n\n// === 3D Stage Enhancement ===\n" + stage_jsx
                with open(jsx_path, "w", encoding="utf-8") as f:
                    f.write(jsx_code)
                log(f"  3D 舞台增强已追加: camera={cam_move}, lighting={lighting}")
                report["phases"]["stage3d"] = {
                    "camera": cam_move, "lighting": lighting,
                    "stage_lines": len(stage_jsx.splitlines())
                }
            except Exception as e:
                log(f"  3D 舞台增强失败(非致命): {e}", "WARN")

        # ── Phase 5: AE 执行 ──
        print("\n--- Phase 5: AE 执行 ---")
        if auto_launch_ae:
            self._ensure_ae_running()

        connected = self.executor.connect()
        if connected:
            result = self.executor.execute_jsx(jsx_code)
            report["phases"]["execution"] = result
            log(f"  执行结果: {result.get('status', result.get('success', '?'))}")
        else:
            log("AE 不可用，JSX 已保存为文件，可手动执行", "WARN")
            report["phases"]["execution"] = {"status": "saved_only", "jsx_path": str(jsx_path)}

        # ── 报告 ──
        elapsed = time.time() - start_time
        report["elapsed_seconds"] = round(elapsed, 1)
        report["output_dir"] = str(self.output_dir)

        report_path = self.output_dir / "director_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 60)
        print(f"  AI Director 完成! 耗时 {elapsed:.1f}s")
        print(f"  输出: {self.output_dir}")
        print(f"  报告: {report_path}")
        print("=" * 60)

        return report

    def _ensure_ae_running(self):
        """确保 AE 正在运行"""
        import subprocess
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq AfterFX.exe"],
                capture_output=True, text=True, timeout=5,
            )
            if "AfterFX.exe" in result.stdout:
                log("AE 已在运行")
                return
        except Exception:
            pass

        log("启动 AE...", "WARN")
        ae_path = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
        if os.path.exists(ae_path):
            import subprocess
            subprocess.Popen([ae_path], creationflags=0x00000008)  # DETACHED_PROCESS
            log("等待 AE 启动 (约30秒)...")
            time.sleep(30)


# ================================================================
#  主入口
# ================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  AI Director System v1.0")
    print("  从描述到成品的全自动视频创作")
    print("=" * 60)

    # 默认演示: 使用本地已有素材
    director = AIDirector()

    # 检测 V17 素材
    v17_video = r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4"
    if os.path.exists(v17_video):
        result = director.produce(
            user_prompt="冰海战记高燃混剪, 电影感, 30秒",
            material_paths=[v17_video],
            style="cinematic",
            auto_launch_ae=False,  # 先不启动AE, 仅生成JSX
        )
    else:
        print(f"\n  素材不存在: {v17_video}")
        print("  请准备素材后重试，或指定其他路径")
        # 仍然生成一个 demo 剧本
        result = director.produce(
            user_prompt="Demo 演示 - 自动生成剧本",
            material_paths=[],
            style="cinematic",
            auto_launch_ae=False,
        )

    print(f"\n  结果: {json.dumps(result.get('phases', {}), ensure_ascii=False, indent=2)[:500]}")