"""
Ultimate Video Factory - 一句话出视频终极系统
============================================
整合全部能力:
  A. AI Director (素材→分析→剧本→JSX→AE)
  B. 3D Stage (多图层空间编排)
  C. Style Migration (风格迁移)
  D. Audio Edit (音频驱动剪辑)

用法:
    factory = UltimateVideoFactory()
    result = factory.produce("利威尔高燃混剪, 30秒, 电影感")

    # 带参考视频风格迁移:
    result = factory.produce("赛博朋克风格混剪", reference_video="ref.mp4")

    # 带BGM音频驱动:
    result = factory.produce("高燃战斗混剪", audio_path="bgm.mp3")

    # 完整模式:
    result = factory.produce(
        "冰海战记史诗混剪, 30秒, 竖屏",
        material_urls=["https://www.bilibili.com/video/BV..."],
        reference_video="reference.mp4",
        audio_path="bgm.mp3",
        style="cinematic"
    )
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


class UltimateVideoFactory:
    """一句话出视频 - 终极工厂"""

    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else Path(
            r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_director")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 延迟加载各模块
        self._director = None
        self._style_migrator = None
        self._audio_engine = None

    @property
    def director(self):
        if self._director is None:
            from ai_director import AIDirector
            self._director = AIDirector(str(self.output_dir))
        return self._director

    @property
    def style_migrator(self):
        if self._style_migrator is None:
            from style_migrator import StyleMigrator
            self._style_migrator = StyleMigrator()
        return self._style_migrator

    @property
    def audio_engine(self):
        if self._audio_engine is None:
            from audio_edit_engine import AudioEditEngine
            self._audio_engine = AudioEditEngine(str(self.output_dir))
        return self._audio_engine

    def produce(self, prompt: str,
                material_urls: list[str] = None,
                material_paths: list[str] = None,
                reference_video: str = None,
                audio_path: str = None,
                style: str = "cinematic",
                auto_ae: bool = True,
                resolution: str = "1080x1920") -> dict[str, Any]:
        """
        一句话出视频 - 完整流程。

        Args:
            prompt: 用户描述 (如 "利威尔高燃混剪, 30秒, 竖屏")
            material_urls: 素材下载链接
            material_paths: 本地素材路径
            reference_video: 参考视频(风格迁移)
            audio_path: BGM音频(节拍同步)
            style: 风格预设
            auto_ae: 是否自动启动AE
            resolution: 分辨率 (1080x1920 / 1920x1080)
        """
        start_time = time.time()
        report = {
            "prompt": prompt,
            "style": style,
            "resolution": resolution,
            "modules_used": [],
            "phases": {},
        }

        print("\n" + "=" * 70)
        print("  ULTIMATE VIDEO FACTORY - 一句话出视频")
        print(f"  Prompt: {prompt}")
        print(f"  Style: {style} | Resolution: {resolution}")
        if reference_video:
            print(f"  Reference: {Path(reference_video).name}")
        if audio_path:
            print(f"  BGM: {Path(audio_path).name}")
        print("=" * 70)

        # ── Phase 0: 解析用户意图 ──
        print("\n--- Phase 0: 意图解析 ---")
        intent = self._parse_intent(prompt, resolution)
        report["intent"] = intent
        log(f"  意图: duration={intent.get('duration')}s, "
            f"orientation={intent.get('orientation')}, "
            f"mood={intent.get('mood')}")

        # ── Phase 1: 素材搜集 ──
        print("\n--- Phase 1: 素材搜集 ---")
        material_files = self._collect_materials(
            material_urls, material_paths, intent)
        report["phases"]["collection"] = {
            "total": len(material_files),
            "files": [Path(f).name for f in material_files],
        }
        log(f"素材就绪: {len(material_files)} 个")

        if not material_files:
            log("无素材可用，退出", "ERROR")
            report["error"] = "No materials available"
            return report

        # ── Phase 2: 视觉分析 ──
        print("\n--- Phase 2: 视觉分析 ---")
        analyses = self._analyze_materials(material_files)
        report["phases"]["analysis"] = {
            "analyzed": len(analyses),
            "summaries": [{"name": Path(a.get("source", "")).name,
                           "mood": a.get("mood"),
                           "duration": a.get("duration")} for a in analyses],
        }

        # ── Phase 2.5: 风格迁移 (可选) ──
        if reference_video and os.path.exists(reference_video):
            print("\n--- Phase 2.5: 风格迁移 ---")
            try:
                report["modules_used"].append("style_migration")
                fingerprint = self.style_migrator.extractor.extract(reference_video)
                match = self.style_migrator.matcher.match(fingerprint)
                style = match["style_name"] or style
                report["phases"]["style_migration"] = {
                    "style": match["style_name"],
                    "score": match["style_score"],
                    "tags": fingerprint.get("style_tags", []),
                }
                log(f"  风格: {match['style_name']} (score={match['style_score']})")
            except Exception as e:
                log(f"  风格迁移失败: {e}", "WARN")

        # ── Phase 2.7: 音频分析 (可选) ──
        audio_features = None
        if audio_path and os.path.exists(audio_path):
            print("\n--- Phase 2.7: 音频分析 ---")
            try:
                report["modules_used"].append("audio_edit")
                audio_features = self.audio_engine.analyzer.analyze(audio_path)
                bpm = audio_features.get("bpm", 128)
                n_beats = len(audio_features.get("beats", []))
                report["phases"]["audio_analysis"] = {
                    "bpm": bpm,
                    "beats": n_beats,
                    "mood": audio_features.get("mood"),
                }
                # BPM 影响风格
                if bpm > 140:
                    style = "high_energy"
                elif bpm < 80:
                    style = "slow_cinematic"
                log(f"  BPM={bpm}, {n_beats} beats, mood={audio_features.get('mood')}")
            except Exception as e:
                log(f"  音频分析失败: {e}", "WARN")

        # ── Phase 3: AI 剧本 ──
        print("\n--- Phase 3: AI 剧本生成 ---")
        script = self.director.script_gen.generate_script(prompt, analyses, style)
        report["phases"]["script"] = {
            "title": script.get("title"),
            "duration": script.get("total_duration"),
            "segments": len(script.get("segments", [])),
        }
        # 保存剧本
        script_path = self.output_dir / "ultimate_script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
        log(f"  剧本: {script.get('title')}, {len(script.get('segments', []))} 段")

        # ── Phase 4: JSX 翻译 ──
        print("\n--- Phase 4: 剧本 → JSX ---")
        jsx_code = self.director.translator.translate(script, material_files)
        log(f"  基础 JSX: {len(jsx_code.splitlines())} 行")

        # ── Phase 4.3: 音频驱动增强 ──
        if audio_features:
            print("\n--- Phase 4.3: 音频驱动增强 ---")
            try:
                edl = self.audio_engine.edl_gen.generate(
                    audio_features, material_count=len(material_files))
                # 追加节拍同步缩放
                beat_jsx = self._generate_beat_sync_jsx(audio_features, script)
                jsx_code += "\n\n// === Beat Sync Enhancement ===\n" + beat_jsx
                report["phases"]["beat_sync"] = {
                    "edl_clips": len(edl),
                    "beats_mapped": len(audio_features.get("beats", [])),
                }
                log(f"  节拍同步: {len(edl)} EDL clips, beat JSX added")
            except Exception as e:
                log(f"  音频增强失败: {e}", "WARN")

        # ── Phase 4.5: 3D 舞台增强 ──
        print("\n--- Phase 4.5: 3D 舞台增强 ---")
        try:
            report["modules_used"].append("3d_stage")
            res = script.get("resolution", {"width": 1920, "height": 1080})
            stage3d = self.director._get_stage3d(
                res.get("width", 1920), res.get("height", 1080),
                script.get("total_duration", 30), script.get("fps", 30))
            segments = script.get("segments", [])
            cam_move = "push_in"
            for seg in segments:
                if seg.get("type") == "drop":
                    cam_move = seg.get("camera", {}).get("movement", "push_in")
                    break
            mood_map = {"intense_action": "dramatic", "dark_serious": "dark",
                        "bright_cheerful": "soft", "calm_epic": "cinematic"}
            lighting = "cinematic"
            if analyses:
                lighting = mood_map.get(analyses[0].get("mood", ""), "cinematic")
            stage_jsx = stage3d.generate_full_stage(
                material_paths=material_files[:5],
                camera_movement=cam_move,
                lighting_mood=lighting,
                transitions=[{"type": "cube_flip_y", "duration": 0.8}])
            jsx_code += "\n\n// === 3D Stage ===\n" + stage_jsx
            report["phases"]["stage3d"] = {
                "camera": cam_move, "lighting": lighting,
                "lines": len(stage_jsx.splitlines())
            }
            log(f"  3D: camera={cam_move}, lighting={lighting}")
        except Exception as e:
            log(f"  3D 增强失败: {e}", "WARN")

        # ── 保存 JSX ──
        jsx_path = self.output_dir / "ultimate_video.jsx"
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx_code)
        report["phases"]["total_jsx"] = len(jsx_code.splitlines())
        log(f"  总 JSX: {len(jsx_code.splitlines())} 行, {len(jsx_code)} 字符")

        # ── Phase 5: AE 执行 ──
        print("\n--- Phase 5: AE 执行 ---")
        if auto_ae:
            self.director._ensure_ae_running()
        connected = self.director.executor.connect()
        if connected:
            result = self.director.executor.execute_jsx(jsx_code)
            report["phases"]["execution"] = result
            log(f"  执行: {result.get('status', result.get('success', '?'))}")
        else:
            log("AE 不可用，JSX 已保存", "WARN")
            report["phases"]["execution"] = {"status": "saved_only"}

        # ── 完成 ──
        elapsed = time.time() - start_time
        report["elapsed_seconds"] = round(elapsed, 1)
        report["output_dir"] = str(self.output_dir)

        # 保存报告
        report_path = self.output_dir / "ultimate_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 70)
        print(f"  完成! 耗时 {elapsed:.1f}s")
        print(f"  模块: {', '.join(report['modules_used'])}")
        print(f"  JSX: {report['phases'].get('total_jsx', 0)} 行")
        print(f"  输出: {self.output_dir}")
        print("=" * 70)

        return report

    def _parse_intent(self, prompt: str, resolution: str) -> dict[str, Any]:
        """解析用户意图"""
        intent = {"duration": 30, "orientation": "vertical", "mood": "epic"}

        # 解析时长
        import re
        m = re.search(r'(\d+)\s*[秒s]', prompt)
        if m:
            intent["duration"] = int(m.group(1))

        # 解析方向
        if "横屏" in prompt or "16:9" in prompt:
            intent["orientation"] = "horizontal"
        elif "竖屏" in prompt or "9:16" in prompt:
            intent["orientation"] = "vertical"

        # 解析情绪
        mood_keywords = {
            "高燃": "intense", "热血": "intense", "战斗": "intense",
            "悲伤": "sad", "感人": "emotional", "治愈": "calm",
            "搞笑": "funny", "恐怖": "horror", "浪漫": "romantic",
            "史诗": "epic", "震撼": "epic",
        }
        for kw, mood in mood_keywords.items():
            if kw in prompt:
                intent["mood"] = mood
                break

        return intent

    def _collect_materials(self, urls: list[str] = None,
                           paths: list[str] = None,
                           intent: dict = None) -> list[str]:
        """搜集素材"""
        files = []
        collector = self.director.collector

        if urls:
            results = collector.collect_from_urls(urls)
            files.extend([r["path"] for r in results if r.get("success") and r.get("path")])

        if paths:
            results = collector.collect_from_local(paths)
            files.extend([r["path"] for r in results if r.get("success")])

        if not files:
            log("扫描本地素材库...", "WARN")
            local = collector.scan_local_library()
            files = [v["path"] for v in local[:5]]

        return files

    def _analyze_materials(self, material_files: list[str]) -> list[dict]:
        """视觉分析"""
        analyses = []
        for mf in material_files[:5]:
            try:
                analysis = self.director.analyzer.analyze(mf)
                analysis["source"] = mf
                analyses.append(analysis)
            except Exception as e:
                log(f"  分析失败: {e}", "ERROR")
        return analyses

    def _generate_beat_sync_jsx(self, audio_features: dict, script: dict) -> str:
        """生成节拍同步 JSX"""
        beats = audio_features.get("beats", [])
        energy_vals = audio_features.get("energy_values", [])
        if not beats:
            return ""

        lines = []
        lines.append("// Beat-sync: scale pulse on strong beats")
        lines.append("var allLayers = comp.layers;")
        lines.append("for (var li = 1; li <= allLayers.numLayers; li++) {")
        lines.append("  var ly = allLayers.layer(li);")
        lines.append("  if (ly.adjustmentLayer) continue;")
        lines.append("  var sc = ly.property('ADBE Transform Group').property('ADBE Scale');")

        # 在强能量节拍处添加缩放脉冲
        count = 0
        for bt, en in zip(beats, energy_vals):
            if en > 0.7 and count < 30:
                scale_val = 100 + (en - 0.7) * 40
                lines.append(f"  try {{ sc.setValueAtTime({bt:.3f}, [{scale_val:.1f}, {scale_val:.1f}]); }} catch(e) {{}}")
                lines.append(f"  try {{ sc.setValueAtTime({bt + 0.12:.3f}, [100, 100]); }} catch(e) {{}}")
                count += 1

        lines.append("}")
        return "\n".join(lines)


# ================================================================
#  主入口
# ================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("  ULTIMATE VIDEO FACTORY v1.0")
    print("  一句话出视频 - 全能力整合")
    print("=" * 70)

    factory = UltimateVideoFactory()

    # 检测可用素材
    v17 = r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4"
    materials = [v17] if os.path.exists(v17) else []

    # 检测可用音频
    audio = None
    for p in [r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\audio_processed.wav",
              r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\audio_raw.wav"]:
        if os.path.exists(p):
            audio = p
            break

    result = factory.produce(
        prompt="冰海战记高燃史诗混剪, 30秒, 电影感",
        material_paths=materials,
        reference_video=v17 if os.path.exists(v17) else None,
        audio_path=audio,
        style="cinematic",
        auto_ae=False,
    )

    print("\n最终报告:")
    print(json.dumps(result.get("phases", {}), ensure_ascii=False, indent=2)[:800])
