"""
core/font_manager.py
====================
统一字体资源管理器 - 整合V12后本地安装的3038款字体到AE项目

提供：
- 字体元数据加载 (config/font_presets.json)
- 场景→字体映射查询
- JSX字体应用模板生成
- ExtendScript ES3兼容的字体PostScript名规范化
- 已安装字体快速验证 (PowerShell后端)
- 风格化设计经验: 8大场景、5种动画配方

使用示例:
    from core.font_manager import FontManager
    fm = FontManager()
    preset = fm.get_preset("sub_cn_impact")
    jsx = fm.generate_apply_jsx("sub_cn_impact", "战", 100, 9.0, 9.5)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FONT_CONFIG = _PROJECT_ROOT / "config" / "font_presets.json"
_INSTALLED_FONTS_LIST = Path(r"D:\AE-Work\installed_fonts.txt")


class FontManager:
    """统一字体资源管理器 - AE字体风格化引擎"""

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or _FONT_CONFIG
        self._config: Dict[str, Any] = {}
        self._installed_cache: Optional[set] = None
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        else:
            raise FileNotFoundError(
                f"字体配置不存在: {self._config_path}，"
                f"请先运行 scripts/install_fonts.ps1 安装字体"
            )

    # ============ 基础查询 ============

    @property
    def version(self) -> str:
        return self._config.get("version", "1.0")

    @property
    def installed_count(self) -> int:
        return self._config.get("installed_count", 0)

    def categories(self) -> List[str]:
        """返回所有字体分类键"""
        return list(self._config.get("categories", {}).keys())

    def get_preset(self, key: str) -> Optional[Dict[str, Any]]:
        """通过 key 获取单条字体预设"""
        for cat_data in self._config.get("categories", {}).values():
            for f in cat_data.get("fonts", []):
                if f.get("key") == key:
                    return f
        return None

    def get_scene_font(self, scene: str) -> Optional[Dict[str, Any]]:
        """根据场景键返回对应字体预设

        scene ∈ {intro_hero, build_emotion, drop_battle_cn, break_quote, ...}
        """
        mapping = self._config.get("scene_font_mapping", {})
        font_key = mapping.get(scene)
        if not font_key:
            return None
        return self.get_preset(font_key)

    def list_presets(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有字体预设，可按分类过滤"""
        if category:
            return self._config.get("categories", {}).get(category, {}).get("fonts", [])
        result = []
        for cat_data in self._config.get("categories", {}).values():
            result.extend(cat_data.get("fonts", []))
        return result

    # ============ 安装验证 ============

    def _load_installed_fonts(self) -> set:
        """从 installed_fonts.txt 加载已安装字体名（小写）

        索引三种形式:
        - 完整文件名 (xx.ttf)
        - 去扩展的显示名 (xx)
        - 去常见分隔符的紧凑名 (xx)
        """
        if self._installed_cache is not None:
            return self._installed_cache
        installed = set()
        if _INSTALLED_FONTS_LIST.exists():
            with open(_INSTALLED_FONTS_LIST, "r", encoding="utf-8") as f:
                for line in f:
                    name = line.strip()
                    if not name:
                        continue
                    base = Path(name).stem
                    installed.add(name.lower())
                    installed.add(base.lower())
                    # 同时索引去空格/连字符/下划线的版本
                    compact = re.sub(r"[\s\-_]+", "", base).lower()
                    installed.add(compact)
        self._installed_cache = installed
        return installed

    def is_font_installed(self, font_name: str, postscript: Optional[str] = None) -> bool:
        """检查字体是否已安装（按文件名、显示名或PostScript名）

        Args:
            font_name: 字体显示名或文件名
            postscript: 可选PostScript名,用于补充匹配(许多字体PostScript名与文件名不一致)
        """
        installed = self._load_installed_fonts()
        candidates = [font_name, Path(font_name).stem]
        if postscript:
            candidates.append(postscript)
        for c in candidates:
            if not c:
                continue
            cn = c.lower()
            if cn in installed:
                return True
            # 紧凑匹配 (去空格/连字符/下划线)
            compact = re.sub(r"[\s\-_]+", "", cn)
            if compact in installed:
                return True
            # 前缀匹配 (bebasneue vs Bebas Neue, 04b_30 vs 04B_30)
            for inst in installed:
                # 双向前缀包含
                if inst.startswith(compact[:6]) and len(compact) >= 6:
                    return True
                if compact.startswith(inst[:6]) and len(inst) >= 6:
                    return True
        return False

    def _preset_check_keys(self, preset: Dict[str, Any]) -> List[str]:
        """获取一个预设的所有可能匹配名(显示名+PostScript紧凑型)"""
        names = [preset.get("name", ""), preset.get("postscript", "")]
        return [n for n in names if n]

    def validate_all_presets(self) -> List[Dict[str, Any]]:
        """验证所有预设的字体是否已安装"""
        results = []
        for preset in self.list_presets():
            ok = self.is_font_installed(
                preset.get("name", ""),
                postscript=preset.get("postscript", ""),
            )
            results.append({
                "key": preset["key"],
                "name": preset["name"],
                "installed": ok,
                "tag": preset.get("tag", ""),
            })
        return results

    def reload_installed_list(self) -> int:
        """通过 PowerShell 重新扫描系统字体并写回 installed_fonts.txt"""
        ps_cmd = (
            "Get-ChildItem -Path 'C:\\Windows\\Fonts',"
            "'$env:LOCALAPPDATA\\Microsoft\\Windows\\Fonts'"
            " -Recurse -File -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Extension -in '.ttf','.otf','.ttc' } | "
            "ForEach-Object { $_.Name } | Out-File -FilePath "
            "'D:\\AE-Work\\installed_fonts.txt' -Encoding UTF8"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and _INSTALLED_FONTS_LIST.exists():
            self._installed_cache = None  # 强制重载
            return sum(1 for _ in open(_INSTALLED_FONTS_LIST, encoding="utf-8"))
        return -1

    # ============ PostScript 名规范化 ============

    @staticmethod
    def normalize_postscript(name: str) -> str:
        """将字体名/文件名规范化为 ExtendScript 可用的 PostScript 名

        规则:
        - 去扩展名
        - 中文/特殊字符保持原样(ExtendScript 字符串支持UTF-8)
        - 移除多余空格
        """
        # 去扩展名
        name = re.sub(r"\.(ttf|otf|ttc|fon)$", "", name, flags=re.I)
        # 移除首尾空白
        return name.strip()

    # ============ JSX 模板生成 ============

    def generate_apply_jsx(
        self,
        font_key: str,
        text: str,
        font_size: float,
        start_t: float,
        end_t: float,
        y_pos: float = 0.0,
        anim: str = "bounce_in",
        x_center: float = 540.0,
    ) -> str:
        """生成可直接通过 MCP executeAtomScript 执行的 IIFE JSX

        Args:
            font_key: 字体预设key (如 "sub_cn_impact")
            text: 文字内容
            font_size: 字号(pt)
            start_t, end_t: 起止时间(秒)
            y_pos: 垂直位置(像素)
            anim: 动画配方 (bounce_in / kinetic_smash / glitch_pop / tracking_fade)
            x_center: 水平中心(像素)
        """
        preset = self.get_preset(font_key)
        if not preset:
            raise ValueError(f"未找到字体预设: {font_key}")

        ps_name = self.normalize_postscript(preset["postscript"])
        color = self._parse_color(preset.get("color", "#FFFFFF"))
        stroke = self._parse_color(preset.get("stroke", "#000000"))
        stroke_w = preset.get("stroke_w", 1.5)

        anim_kf = self._build_anim_keyframes(anim, start_t, end_t)

        jsx = f'''(function(){{var _r={{}};try{{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){{_r={{status:'error',message:'No active comp'}};return JSON.stringify(_r);}}
var tl=c.layers.addText("{self._escape_jsx_str(text)}");
tl.name="TXT_{font_key}";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="{ps_name}";
td.fontSize={font_size};
td.applyFill=true;td.fillColor={color};
td.applyStroke=true;td.strokeColor={stroke};
td.strokeWidth={stroke_w};
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime={start_t};tl.inPoint={start_t};tl.outPoint={end_t};
tl.position.setValueAtTime({start_t},[{x_center},{y_pos+25}]);
tl.position.setValueAtTime({start_t}+0.4,[{x_center},{y_pos}]);
{anim_kf}
tl.opacity.setValueAtTime({start_t},0);
tl.opacity.setValueAtTime({start_t}+0.2,100);
tl.opacity.setValueAtTime({end_t}-0.2,100);
tl.opacity.setValueAtTime({end_t},0);
try{{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}}catch(e_g){{}}
_r={{status:'success',font:'{ps_name}',text:'{self._escape_jsx_str(text)}',start:{start_t},end:{end_t}}};
}}catch(e){{_r={{status:'error',message:e.toString()}};}}
return JSON.stringify(_r);}})();'''
        return jsx

    def _build_anim_keyframes(self, anim: str, start_t: float, end_t: float) -> str:
        """生成动画关键帧代码"""
        recipes = self._config.get("animation_recipes", {})
        recipe = recipes.get(anim)
        if not recipe:
            return ""
        if "expression" in recipe:
            expr = recipe["expression"]
            return (
                f'try{{tl.property("ADBE Text Properties")'
                f'.property("ADBE Text Document").expression='
                f'"{self._escape_jsx_str(expr)}";}}catch(e_anim){{}}'
            )
        # 关键帧式动画
        lines = []
        for kf in recipe.get("keyframes", []):
            t = round(start_t + kf["t"], 4)
            s = kf.get("scale")
            o = kf.get("opacity")
            r = kf.get("rotation", 0)
            xs = kf.get("x_shift", 0)
            if s:
                lines.append(
                    f'tl.scale.setValueAtTime({t},[{s[0]},{s[1]}]);'
                )
            if o is not None:
                lines.append(f'tl.opacity.setValueAtTime({t},{o});')
            if xs:
                # 仅水平偏移
                lines.append(
                    f'tl.position.setValueAtTime({t},'
                    f'[tl.position.value[0]+({xs}),tl.position.value[1]]);'
                )
            if r:
                lines.append(f'tl.rotation.setValueAtTime({t},{r});')
        return "\n".join(lines)

    @staticmethod
    def _parse_color(hex_str: str) -> str:
        """#RRGGBB -> [r,g,b] 0-1"""
        m = re.match(r"^#?([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$", hex_str)
        if not m:
            return "[1,1,1]"
        r, g, b = (int(m.group(i), 16) / 255.0 for i in (1, 2, 3))
        return f"[{r:.3f},{g:.3f},{b:.3f}]"

    @staticmethod
    def _escape_jsx_str(s: str) -> str:
        """JSX 字符串转义（避免引号/反斜杠）"""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    # ============ 批量方案生成 ============

    def generate_v17_text_plan_jsx(
        self, scene_presets: List[Dict[str, Any]], width: float = 1080
    ) -> str:
        """根据场景-字体方案列表批量生成 V17 字幕系统 JSX

        scene_presets: [{scene, text, start, end, size?}, ...]
        """
        blocks = []
        for item in scene_presets:
            preset = self.get_scene_font(item["scene"])
            if not preset:
                continue
            key = preset["key"]
            size = item.get("size", 80)
            anim = item.get("anim", "bounce_in")
            y_pos = item.get("y", 960)
            blocks.append(
                self.generate_apply_jsx(
                    key, item["text"], size, item["start"], item["end"],
                    y_pos=y_pos, anim=anim, x_center=width / 2,
                )
            )
        return "\n".join(blocks)

    # ============ 风格化经验摘要 ============

    def get_styling_guide(self) -> Dict[str, str]:
        """返回风格化设计经验摘要"""
        return {
            "scene_to_font": (
                "主视觉→暴力粗黑(方正兰亭)；卡点战吼→极粗冲击(Impact/Bebas)；"
                "诗意留白→衬线(思源宋体/Playfair)；科技数据→DIN/Consolas"
            ),
            "font_pairing": (
                "中文暴力粗黑+英文极粗(Impact)是燃向混剪黄金组合；"
                "衬线+无衬线形成冷热对比；字重差>300才形成视觉层级"
            ),
            "color_rule": (
                "白字+黑描边是基础安全组合；战斗字幕用青/橙/红三色呼应BPM情绪；"
                "数据面板用单色高亮(青/绿)配深色描边"
            ),
            "tracking_rule": (
                "字距+0~+30适合短促卡点；+50~+150适合电影感大标题；"
                "字距动画必须用SourceText.expression，不能用关键帧"
            ),
            "es3_pitfall": (
                "ExtendScript基于ES3,只能用PostScript名(不是文件名)；"
                "ScriptUI.newFont()不支持,Date.toISOString()不存在"
            ),
        }


# 便捷工厂
_default_manager: Optional[FontManager] = None


def get_font_manager() -> FontManager:
    """获取默认字体管理器单例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = FontManager()
    return _default_manager


if __name__ == "__main__":
    fm = get_font_manager()
    print(f"字体配置版本: {fm.version}")
    print(f"已安装字体数: {fm.installed_count}")
    print(f"分类: {', '.join(fm.categories())}")
    print()
    print("=== 验证已安装字体 ===")
    results = fm.validate_all_presets()
    installed = sum(1 for r in results if r["installed"])
    print(f"已安装预设: {installed}/{len(results)}")
    for r in results:
        mark = "OK" if r["installed"] else "MISS"
        print(f"  [{mark}] {r['name']:<30} ({r['tag']})")
    print()
    print("=== 风格化经验摘要 ===")
    for k, v in fm.get_styling_guide().items():
        print(f"[{k}] {v}")
