"""
Style Migrator - 知识库驱动的智能风格迁移引擎
==============================================
输入参考视频 → 提取风格特征 → 匹配知识库配方 → 生成目标项目 JSX

核心流程:
1. 参考视频风格指纹提取 (色彩/节奏/转场/文字/特效)
2. 知识库风格匹配 (211个md配方 + style_template_library)
3. 风格迁移 JSX 生成 (效果/转场/调色/文字动画)

用法:
    migrator = StyleMigrator()
    fingerprint = migrator.extract_style("reference.mp4")
    match = migrator.match_style(fingerprint)
    jsx = migrator.generate_transfer_jsx(match, target_materials)
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ================================================================
#  1. 风格指纹提取器
# ================================================================
class StyleFingerprintExtractor:
    """从参考视频提取风格指纹"""

    def extract(self, video_path: str) -> dict[str, Any]:
        """提取完整风格指纹"""
        import cv2
        import numpy as np

        log(f"提取风格指纹: {Path(video_path).name}")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": f"无法打开: {video_path}"}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps

        # 采样分析
        step = max(1, total_frames // 200)
        brightness_samples = []
        saturation_samples = []
        hue_samples = []
        edge_densities = []
        scene_changes = []
        color_profiles = []
        prev_hist = None
        frame_times = []

        for i in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                break
            t = i / fps
            frame_times.append(t)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # 亮度
            brightness = float(np.mean(gray))
            brightness_samples.append(brightness)

            # 饱和度
            saturation = float(np.mean(hsv[:, :, 1]))
            saturation_samples.append(saturation)

            # 主色调 (Hue 分布)
            hue_mean = float(np.mean(hsv[:, :, 0]))
            hue_samples.append(hue_mean)

            # 边缘密度 (运动/细节量)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = float(np.mean(edges)) / 255.0
            edge_densities.append(edge_density)

            # 色彩分布
            b_mean, g_mean, r_mean = [float(np.mean(frame[:,:,c])) for c in range(3)]
            color_profiles.append({"r": r_mean, "g": g_mean, "b": b_mean})

            # 场景切换检测
            hist = cv2.normalize(cv2.calcHist([gray], [0], None, [64], [0, 256]),
                                 None).flatten()
            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                if diff > 0.3:
                    scene_changes.append({"time": round(t, 2), "diff": round(diff, 3)})
            prev_hist = hist

        cap.release()

        # 计算风格特征
        avg_brightness = sum(brightness_samples) / max(len(brightness_samples), 1)
        avg_saturation = sum(saturation_samples) / max(len(saturation_samples), 1)
        avg_hue = sum(hue_samples) / max(len(hue_samples), 1)
        avg_edge = sum(edge_densities) / max(len(edge_densities), 1)
        brightness_std = float(np.std(brightness_samples)) if brightness_samples else 0
        cut_rate = len(scene_changes) / max(duration, 1)

        # 色彩温度推断
        avg_r = sum(c["r"] for c in color_profiles) / max(len(color_profiles), 1)
        avg_b = sum(c["b"] for c in color_profiles) / max(len(color_profiles), 1)
        warmth = avg_r - avg_b  # 正值=暖色, 负值=冷色

        # 风格推断
        color_mood = self._infer_color_mood(avg_brightness, avg_saturation, warmth)
        rhythm = self._infer_rhythm(cut_rate, avg_edge)
        energy = self._infer_energy(avg_edge, cut_rate, brightness_std)

        fingerprint = {
            "source": video_path,
            "resolution": {"width": w, "height": h},
            "duration": round(duration, 1),
            "fps": fps,
            # 色彩特征
            "color": {
                "avg_brightness": round(avg_brightness, 1),
                "avg_saturation": round(avg_saturation, 1),
                "avg_hue": round(avg_hue, 1),
                "warmth": round(warmth, 1),
                "brightness_std": round(brightness_std, 1),
                "color_mood": color_mood,
                "dominant_rgb": {
                    "r": round(avg_r, 1),
                    "g": round(sum(c["g"] for c in color_profiles) / max(len(color_profiles), 1), 1),
                    "b": round(avg_b, 1),
                },
            },
            # 节奏特征
            "rhythm": {
                "scene_changes": len(scene_changes),
                "cut_rate": round(cut_rate, 2),
                "avg_edge_density": round(avg_edge, 3),
                "rhythm_type": rhythm,
            },
            # 能量特征
            "energy": {
                "level": energy,
                "brightness_variation": round(brightness_std, 1),
                "motion_intensity": round(avg_edge * cut_rate, 3),
            },
            # 综合风格标签
            "style_tags": self._generate_style_tags(
                avg_brightness, avg_saturation, warmth, cut_rate, avg_edge, brightness_std
            ),
        }

        log(f"  风格指纹: mood={color_mood}, rhythm={rhythm}, energy={energy}")
        log(f"  色彩: brightness={avg_brightness:.0f}, saturation={avg_saturation:.0f}, warmth={warmth:.0f}")
        log(f"  节奏: {len(scene_changes)} cuts, rate={cut_rate:.2f}/s")

        return fingerprint

    def _infer_color_mood(self, brightness: float, saturation: float, warmth: float) -> str:
        if brightness < 35 and saturation < 30:
            return "dark_desaturated"
        elif brightness < 45 and warmth > 15:
            return "dark_warm"
        elif brightness < 45 and warmth < -10:
            return "dark_cool"
        elif brightness > 65 and saturation > 60:
            return "bright_vivid"
        elif brightness > 60 and warmth > 10:
            return "warm_bright"
        elif brightness > 60 and warmth < -10:
            return "cool_bright"
        elif 40 <= brightness <= 60 and saturation < 40:
            return "muted_neutral"
        else:
            return "balanced"

    def _infer_rhythm(self, cut_rate: float, edge_density: float) -> str:
        if cut_rate > 2.5:
            return "hyper_fast"
        elif cut_rate > 1.2:
            return "fast_cut"
        elif cut_rate > 0.5:
            return "moderate"
        elif cut_rate > 0.2:
            return "slow"
        else:
            return "long_take"

    def _infer_energy(self, edge: float, cut_rate: float, bright_std: float) -> str:
        score = edge * 100 + cut_rate * 10 + bright_std * 0.5
        if score > 50:
            return "high"
        elif score > 25:
            return "medium"
        return "low"

    def _generate_style_tags(self, brightness: float, saturation: float,
                             warmth: float, cut_rate: float,
                             edge: float, bright_std: float) -> list[str]:
        tags = []
        # 色彩标签
        if brightness < 40:
            tags.append("暗调")
        elif brightness > 65:
            tags.append("明亮")
        if saturation > 60:
            tags.append("高饱和")
        elif saturation < 30:
            tags.append("低饱和")
        if warmth > 15:
            tags.append("暖色")
        elif warmth < -10:
            tags.append("冷色")
        # 节奏标签
        if cut_rate > 2.0:
            tags.append("快切")
        elif cut_rate < 0.3:
            tags.append("长镜头")
        if edge > 0.15:
            tags.append("高细节")
        if bright_std > 30:
            tags.append("高对比")
        # 综合标签
        if "暗调" in tags and "暖色" in tags:
            tags.append("电影感")
        if "快切" in tags and "高饱和" in tags:
            tags.append("高燃")
        if "低饱和" in tags and "冷色" in tags:
            tags.append("赛博朋克")
        if "长镜头" in tags and "低饱和" in tags:
            tags.append("文艺")
        return tags


# ================================================================
#  2. 知识库风格匹配器
# ================================================================
class KnowledgeBaseStyleMatcher:
    """从知识库中匹配最接近的风格配方"""

    def __init__(self):
        self._style_templates = None
        self._kb_recipes = None

    def _load_styles(self):
        if self._style_templates is not None:
            return
        try:
            from style_template_library import STYLE_TEMPLATES
            self._style_templates = STYLE_TEMPLATES
            log(f"  加载 {len(STYLE_TEMPLATES)} 个风格模板")
        except Exception as e:
            log(f"  风格模板加载失败: {e}", "WARN")
            self._style_templates = {}

    def _load_kb_recipes(self):
        if self._kb_recipes is not None:
            return
        try:
            from knowledge_base.kb_loader import KnowledgeBaseLoader
            loader = KnowledgeBaseLoader.get_instance()
            self._kb_recipes = {
                "effects": loader.get_effect_map(),
                "transitions": loader.get_transition_map(),
            }
            log(f"  知识库加载: effects={len(self._kb_recipes.get('effects', {}))}, "
                f"transitions={len(self._kb_recipes.get('transitions', {}))}")
        except Exception as e:
            log(f"  知识库加载失败(非致命): {e}", "WARN")
            self._kb_recipes = {}

    def match(self, fingerprint: dict[str, Any]) -> dict[str, Any]:
        """匹配最佳风格"""
        self._load_styles()
        self._load_kb_recipes()

        style_tags = fingerprint.get("style_tags", [])
        color_mood = fingerprint.get("color", {}).get("color_mood", "balanced")
        rhythm = fingerprint.get("rhythm", {}).get("rhythm_type", "moderate")
        energy = fingerprint.get("energy", {}).get("level", "medium")

        # 对每个风格模板打分
        scores = {}
        for style_name, template in self._style_templates.items():
            score = self._score_style(template, style_tags, color_mood, rhythm, energy)
            scores[style_name] = score

        # 排序
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_name = ranked[0][0] if ranked else "cinematic"
        best_score = ranked[0][1] if ranked else 0

        best_template = self._style_templates.get(best_name, {})

        log(f"  最佳匹配: {best_name} (score={best_score:.2f})")
        if len(ranked) > 1:
            log(f"  备选: {ranked[1][0]} ({ranked[1][1]:.2f}), {ranked[2][0]} ({ranked[2][1]:.2f})")

        return {
            "style_name": best_name,
            "style_score": round(best_score, 3),
            "template": best_template,
            "fingerprint": fingerprint,
            "all_scores": {k: round(v, 3) for k, v in ranked[:5]},
            "kb_effects": self._kb_recipes.get("effects", {}),
            "kb_transitions": self._kb_recipes.get("transitions", {}),
        }

    def _score_style(self, template: dict, tags: list[str],
                     color_mood: str, rhythm: str, energy: str) -> float:
        score = 0.0
        keywords = template.get("keywords", [])
        # 标签匹配
        for tag in tags:
            for kw in keywords:
                if tag in kw or kw in tag:
                    score += 3.0
        # 色彩情绪匹配
        desc = template.get("description", "").lower()
        mood_keywords = {
            "dark_desaturated": ["暗", "低饱和", "dark", "desaturated"],
            "dark_warm": ["暗", "暖", "dark", "warm"],
            "dark_cool": ["暗", "冷", "dark", "cool"],
            "bright_vivid": ["亮", "高饱和", "bright", "vivid"],
            "warm_bright": ["暖", "亮", "warm", "bright"],
            "cool_bright": ["冷", "亮", "cool", "bright"],
            "muted_neutral": ["柔", "中性", "muted", "neutral"],
            "balanced": ["平衡", "balanced"],
        }
        for kw in mood_keywords.get(color_mood, []):
            if kw in desc:
                score += 2.0
        # 节奏匹配
        if rhythm in ("hyper_fast", "fast_cut") and any(k in desc for k in ["快", "激烈", "fast"]):
            score += 2.0
        if rhythm in ("slow", "long_take") and any(k in desc for k in ["慢", "柔", "slow"]):
            score += 2.0
        # 能量匹配
        if energy == "high" and any(k in desc for k in ["高", "强", "intense"]):
            score += 1.5
        if energy == "low" and any(k in desc for k in ["柔", "静", "soft"]):
            score += 1.5
        return score


# ================================================================
#  3. 风格迁移 JSX 生成器
# ================================================================
class StyleTransferJSXGenerator:
    """根据匹配结果生成风格迁移 JSX"""

    def generate(self, match_result: dict[str, Any],
                 material_paths: list[str],
                 comp_name: str = "StyleTransfer") -> str:
        """生成风格迁移 JSX"""
        template = match_result.get("template", {})
        fingerprint = match_result.get("fingerprint", {})
        style_name = match_result.get("style_name", "cinematic")

        W = fingerprint.get("resolution", {}).get("width", 1920)
        H = fingerprint.get("resolution", {}).get("height", 1080)
        dur = fingerprint.get("duration", 30)
        fps = fingerprint.get("fps", 30)

        lines = []
        lines.append(f"// === Style Transfer: {style_name} ===")
        lines.append(f"var W = {W}, H = {H}, DUR = {dur};")
        lines.append("")

        # 1. 创建合成
        lines.append(f"var comp = app.project.items.addComp('{comp_name}_{style_name}', {W}, {H}, 1, {dur}, {fps});")
        lines.append("")

        # 2. 导入素材
        for i, mp in enumerate(material_paths[:5]):
            safe = mp.replace("\\", "/")
            lines.append(f"var mat_{i+1} = null;")
            lines.append(f"try {{ var io = new ImportOptions(File('{safe}')); mat_{i+1} = app.project.importFile(io); }} catch(e) {{}}")
        lines.append("")

        # 3. 添加素材图层
        lines.append("// --- Layers ---")
        for i in range(min(len(material_paths), 5)):
            seg_dur = dur / min(len(material_paths), 5)
            start = i * seg_dur
            end = start + seg_dur
            lines.append(f"if (mat_{i+1}) {{")
            lines.append(f"  var ly{i} = comp.layers.add(mat_{i+1});")
            lines.append(f"  ly{i}.name = 'StyleLayer_{i+1}';")
            lines.append(f"  ly{i}.startTime = {start:.1f};")
            lines.append(f"  ly{i}.outPoint = {end:.1f};")
            # 淡入淡出
            op = f"ly{i}.property('ADBE Transform Group').property('ADBE Opacity')"
            lines.append(f"  {op}.setValueAtTime({start:.1f}, 0);")
            lines.append(f"  {op}.setValueAtTime({start + 0.3:.1f}, 100);")
            lines.append(f"  {op}.setValueAtTime({end - 0.3:.1f}, 100);")
            lines.append(f"  {op}.setValueAtTime({end:.1f}, 0);")
            lines.append("}")
        lines.append("")

        # 4. 应用风格效果
        effects = template.get("effects", [])
        if effects:
            lines.append(f"// --- Style Effects ({style_name}) ---")
            lines.append("var adjLayer = comp.layers.addSolid([0.5,0.5,0.5], 'StyleAdj', W, H, 1, DUR);")
            lines.append("adjLayer.adjustmentLayer = true;")
            lines.append("adjLayer.moveToEnd();")
            for fx in effects:
                fx_name = fx.get("effectName", "")
                settings = fx.get("settings", {})
                if fx_name:
                    lines.append("try {")
                    lines.append(f"  var fx = adjLayer.Effects.addProperty('{fx_name}');")
                    for param, value in settings.items():
                        if isinstance(value, list):
                            val_str = f"[{', '.join(str(v) for v in value)}]"
                        elif isinstance(value, bool):
                            val_str = "1" if value else "0"
                        else:
                            val_str = str(value)
                        lines.append(f"  try {{ fx.property('{param}').setValue({val_str}); }} catch(e) {{}}")
                    lines.append("} catch(e) {}")
            lines.append("")

        # 5. 文字风格 (根据 fingerprint 推断)
        color_info = fingerprint.get("color", {})
        warmth = color_info.get("warmth", 0)
        text_color = "[1, 0.9, 0.7]" if warmth > 10 else "[0.9, 0.95, 1]" if warmth < -10 else "[1, 1, 1]"
        lines.append("// --- Text Style ---")
        lines.append(f"var title = comp.layers.addText('{style_name.upper()}');")
        lines.append("var tdp = title.property('ADBE Text Properties').property('ADBE Text Document');")
        lines.append("var td = tdp.value;")
        lines.append("td.fontSize = 48;")
        lines.append(f"td.fillColor = {text_color};")
        lines.append("td.justification = ParagraphJustification.CENTER_JUSTIFY;")
        lines.append("tdp.setValue(td);")
        lines.append("title.property('ADBE Transform Group').property('ADBE Position').setValue([W/2, H/2, 0]);")
        lines.append("title.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(0, 0);")
        lines.append("title.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(0.5, 100);")
        lines.append("title.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(3, 100);")
        lines.append("title.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(3.5, 0);")
        lines.append("")

        # 6. 结果
        lines.append(f"JSON.stringify({{success: true, style: '{style_name}', layers: comp.numLayers}});")

        return "\n".join(lines)


# ================================================================
#  4. 主编排器: StyleMigrator
# ================================================================
class StyleMigrator:
    """风格迁移主编排器"""

    def __init__(self):
        self.extractor = StyleFingerprintExtractor()
        self.matcher = KnowledgeBaseStyleMatcher()
        self.generator = StyleTransferJSXGenerator()

    def migrate(self, reference_video: str,
                target_materials: list[str] = None,
                output_dir: str = None) -> dict[str, Any]:
        """
        完整风格迁移流程。

        Args:
            reference_video: 参考视频路径
            target_materials: 目标素材路径列表
            output_dir: 输出目录
        """
        out = Path(output_dir) if output_dir else Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_director")
        out.mkdir(parents=True, exist_ok=True)

        print("\n" + "=" * 60)
        print("  Style Migrator - 风格迁移引擎")
        print("=" * 60)

        # Step 1: 提取风格指纹
        print("\n--- Step 1: 风格指纹提取 ---")
        fingerprint = self.extractor.extract(reference_video)
        fp_path = out / "style_fingerprint.json"
        with open(fp_path, "w", encoding="utf-8") as f:
            json.dump(fingerprint, f, ensure_ascii=False, indent=2)
        log(f"  指纹已保存: {fp_path}")

        # Step 2: 知识库匹配
        print("\n--- Step 2: 知识库匹配 ---")
        match = self.matcher.match(fingerprint)
        match_path = out / "style_match.json"
        with open(match_path, "w", encoding="utf-8") as f:
            json.dump({
                "style_name": match["style_name"],
                "style_score": match["style_score"],
                "all_scores": match["all_scores"],
            }, f, ensure_ascii=False, indent=2)
        log(f"  匹配结果: {match['style_name']} (score={match['style_score']})")

        # Step 3: 生成迁移 JSX
        print("\n--- Step 3: 风格迁移 JSX ---")
        materials = target_materials or [reference_video]
        jsx = self.generator.generate(match, materials)
        jsx_path = out / "style_transfer.jsx"
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx)
        log(f"  JSX 已保存: {jsx_path} ({len(jsx.splitlines())} 行)")

        # 报告
        report = {
            "reference": reference_video,
            "style": match["style_name"],
            "score": match["style_score"],
            "fingerprint_tags": fingerprint.get("style_tags", []),
            "jsx_lines": len(jsx.splitlines()),
            "outputs": {
                "fingerprint": str(fp_path),
                "match": str(match_path),
                "jsx": str(jsx_path),
            }
        }
        report_path = out / "style_migration_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 60)
        print("  风格迁移完成!")
        print(f"  参考: {Path(reference_video).name}")
        print(f"  匹配: {match['style_name']} (score={match['style_score']})")
        print(f"  标签: {', '.join(fingerprint.get('style_tags', []))}")
        print(f"  JSX: {len(jsx.splitlines())} 行")
        print("=" * 60)

        return report


# ================================================================
#  主入口
# ================================================================
if __name__ == "__main__":
    migrator = StyleMigrator()

    # 使用 V17 作为参考视频
    ref = r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4"
    if os.path.exists(ref):
        result = migrator.migrate(
            reference_video=ref,
            target_materials=[ref],
        )
        print(f"\n结果: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
    else:
        print(f"参考视频不存在: {ref}")
