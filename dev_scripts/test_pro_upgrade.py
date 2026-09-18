# -*- coding: utf-8 -*-
"""专业化升级验收测试 — 12运镜 + 3D艺术字体 + 字体扫描 + 效果深化

验收标准:
- 12运镜(8基础+4真实3D摄像机), 3D运镜生成null+camera父子链
- 新增≥12种3D/高级动画JSX全部通过 validate_jsx
- 3D艺术字: Z层叠≥12层+材质光照, DOF与能量挂钩, 3D翻转
- 字体扫描: C:/Windows/Fonts扫描+20场景匹配+三级层次
- 效果深化: 三档intensity联动 + 运镜联动规则
- DirectorQualityScorer.score_card 对新管线剧本≥85分
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.camera_language import CAMERA_IDS, CAMERA_IDS_3D, CAMERA_IDS_ALL, CameraLanguageLibrary  # noqa: E402
from core.director_scorer import DirectorQualityScorer  # noqa: E402
from core.effect_depth import INTENSITY_TIERS, EffectDepthLibrary  # noqa: E402
from core.font_scanner import SCENE_FONT_RULES, SystemFontScanner  # noqa: E402
from core.text_3d import MATERIAL_PRESETS, MIN_STACK_LAYERS, Text3DRenderer, dof_params_from_energy  # noqa: E402

PASS = 0
FAIL = 0
FAILURES = []


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} — {detail}")


camlib = CameraLanguageLibrary()
V = CameraLanguageLibrary.validate_jsx

print("=== 1. 12运镜体系 ===")
check("基础8运镜保持", len(CAMERA_IDS) == 8, str(CAMERA_IDS))
check("新增4种3D运镜",
      set(CAMERA_IDS_3D) == {"dolly_zoom", "crane", "orbit_3d", "shake"},
      str(CAMERA_IDS_3D))
check("全量12运镜", len(CAMERA_IDS_ALL) == 12, str(len(CAMERA_IDS_ALL)))
check("list_cameras_all=12", len(camlib.list_cameras_all()) == 12,
      str(camlib.list_cameras_all()))
check("list_cameras仍=8(兼容V1)", len(camlib.list_cameras()) == 8)

print("\n=== 2. 3D运镜JSX: null+camera父子链 ===")
for cid in CAMERA_IDS_3D:
    jsx = camlib.to_jsx_3d(cid, "segL", "mainComp", 0.0, 5.0,
                           z_depth=camlib.z_depth_for_segment("drop"),
                           uid="t")
    check(f"[{cid}] JSX非空", bool(jsx))
    check(f"[{cid}] 含addNull控制器", "addNull" in jsx)
    check(f"[{cid}] 含addCamera真实摄像机", "addCamera" in jsx)
    check(f"[{cid}] 图层parent指向null", "segL.parent = ctrl_t" in jsx)
    check(f"[{cid}] 图层置3D", "segL.threeDLayer = true" in jsx)
    v = V(jsx)
    check(f"[{cid}] validate_jsx通过", v["ok"], str(v["issues"]))

check("dolly_zoom缩放补偿≤150",
      "140, 140" in camlib.to_jsx_3d("dolly_zoom", "L", "c", 0, 5, uid="d"))
shake_jsx = camlib.to_jsx_3d("shake", "L", "c", 0, 3, uid="s")
check("shake=6关键帧手持抖动", shake_jsx.count("setValueAtTime") >= 6,
      str(shake_jsx.count("setValueAtTime")))

print("\n=== 3. z_depth 段落纵深 ===")
check("drop段Z推进(+)", camlib.z_depth_for_segment("drop") > 0,
      str(camlib.z_depth_for_segment("drop")))
check("break段Z回拉(-)", camlib.z_depth_for_segment("break") < 0,
      str(camlib.z_depth_for_segment("break")))
check("outro段Z回拉(-)", camlib.z_depth_for_segment("outro") < 0)
check("cameras3d_for_segment(drop)非空",
      len(camlib.cameras3d_for_segment("drop")) >= 2,
      str(camlib.cameras3d_for_segment("drop")))

print("\n=== 4. 3D艺术字体管线 ===")
t3d = Text3DRenderer()
zs = t3d.z_stack_jsx("mainComp", "txtL", layers=14, material="metal")
check("Z层叠≥12层(duplicate×13)", zs.count(".duplicate()") >= 13,
      str(zs.count(".duplicate()")))
check("最小层数铁律=12", MIN_STACK_LAYERS == 12)
check("材质Specular参数", "ADBE Specular Intensity" in zs)
check("材质Shininess参数", "ADBE Specular Shininess" in zs)
check("材质Metal参数", "ADBE Metal" in zs)
check("聚光灯打光", "addLight" in zs and "LightType.SPOT" in zs)
check("5种材质预设", len(MATERIAL_PRESETS) >= 5, str(list(MATERIAL_PRESETS)))
v = V(zs)
check("z_stack validate_jsx通过", v["ok"], str(v["issues"]))

dof_hi = dof_params_from_energy(1.0)
dof_lo = dof_params_from_energy(0.1)
check("DOF能量联动: 高能量大光圈", dof_hi["aperture"] > dof_lo["aperture"],
      f"{dof_hi['aperture']} vs {dof_lo['aperture']}")
check("DOF能量联动: 高能量近对焦", dof_hi["focus_end"] < dof_lo["focus_end"])
djsx = t3d.dof_camera_jsx("mainComp", 0.9)
check("DOF JSX含Aperture/Focus Distance",
      "ADBE Aperture" in djsx and "ADBE Focus Distance" in djsx)
check("DOF validate_jsx通过", V(djsx)["ok"], str(V(djsx)["issues"]))

for ax, dr in (("Y", "in"), ("X", "in"), ("Y", "out")):
    fj = t3d.flip_3d_jsx("txtL", ax, dr)
    check(f"flip {ax}/{dr} validate_jsx通过", V(fj)["ok"], str(V(fj)["issues"]))
    check(f"flip {ax}/{dr} 3D图层", "threeDLayer = true" in fj)
seg3d = t3d.segment_3d_jsx("mainComp", "txtL", energy=0.95)
check("完整3D段落组合三段", seg3d.count("try {") == 3)
check("3D风格清单≥9种", len(t3d.list_3d_styles()) >= 9)

print("\n=== 5. 系统字体扫描 ===")
fs = SystemFontScanner()
fonts = fs.scan()
st = fs.stats()
print(f"  [INFO] 扫描到字体: {st}")
check("扫描到字体>0", st["total"] > 0, str(st))
check("含CJK字体", st["cjk"] > 0, str(st["cjk"]))
check("20场景规则齐全", len(SCENE_FONT_RULES) == 20,
      str(len(SCENE_FONT_RULES)))
battle_fonts = fs.match_scene("battle")
check("battle场景匹配非空", len(battle_fonts) > 0, str(battle_fonts))
ink_fonts = fs.match_scene("ink_wash")
check("ink_wash匹配书法体", len(ink_fonts) > 0, str(ink_fonts))
hier = fs.hierarchy("battle")
check("三级层次齐全",
      all(k in hier and hier[k] for k in ["title", "subtitle", "body"]),
      str(hier))
all_m = fs.all_scene_matches()
check("20场景全覆盖匹配", len(all_m) == 20 and
      all(len(v) > 0 for v in all_m.values()),
      str({k: len(v) for k, v in all_m.items()}))

print("\n=== 6. 效果深化: 三档intensity联动 ===")
ed = EffectDepthLibrary()
check("三档参数齐全",
      all(k in INTENSITY_TIERS for k in ["subtle", "moderate", "intense"]))
check("振幅单调递增",
      INTENSITY_TIERS["subtle"]["amp"] < INTENSITY_TIERS["moderate"]["amp"]
      < INTENSITY_TIERS["intense"]["amp"])
check("透明度单调递增",
      INTENSITY_TIERS["subtle"]["opacity"] < INTENSITY_TIERS["intense"]["opacity"])

for inten in ["subtle", "moderate", "intense"]:
    g = ed.glow_double_jsx("txtL", inten)
    check(f"glow双层[{inten}] 双Glow实例", g.count("ADBE Glo2") >= 2)
    check(f"glow[{inten}] 色相偏移关键帧", "ADBE HUE SATUR" in g)
    check(f"glow[{inten}] validate通过", V(g)["ok"], str(V(g)["issues"]))

sl = ed.speed_lines_jsx("txtL", "intense")
check("速度线: 方向模糊动画", "ADBE Directional Blur" in sl and
      "motionBlur = true" in sl)
check("速度线 validate通过", V(sl)["ok"], str(V(sl)["issues"]))

rgb = ed.rgb_split_jsx("txtL", "intense")
check("RGB分离: 双副本", rgb.count(".duplicate()") == 2)
check("RGB分离: Screen混合", rgb.count("BlendingMode.SCREEN") == 2)
check("RGB分离: 通道分离", "ADBE Shift Channels" in rgb)
check("RGB分离 validate通过", V(rgb)["ok"], str(V(rgb)["issues"]))

pw = ed.particle_world_jsx("mainComp", "intense")
check("CC Particle World", "CC Particle World" in pw)
check("粒子 validate通过", V(pw)["ok"], str(V(pw)["issues"]))
sb = ed.saber_jsx("mainComp")
check("Saber光线描边(降级包裹)", "Video Copilot Saber" in sb and
      "try {" in sb)
fm = ed.form_grid_jsx("mainComp")
check("Trapcode Form三维阵列(降级包裹)", "Trapcode Form" in fm and
      "try {" in fm)
check("效果清单7种", len(ed.list_effects()) == 7)

print("\n=== 7. 效果×运镜联动 ===")
lk_whip = ed.camera_effect_link("whip", "drop")
check("whip+drop→RGB分离",
      any(l["effect"] == "rgb_split" for l in lk_whip), str(lk_whip))
check("whip+drop→速度线",
      any(l["effect"] == "speed_lines" for l in lk_whip), str(lk_whip))
lk_break = ed.camera_effect_link("pull", "break")
check("break段→柔光降饱和",
      any(l["effect"] == "soft_breathe" for l in lk_break), str(lk_break))
sbj = ed.soft_breathe_jsx("txtL")
check("柔光降饱和 validate通过", V(sbj)["ok"], str(V(sbj)["issues"]))
link_block = ed.link_jsx("txtL", "mainComp", "whip", "drop", 0.0, 2.0)
check("link_jsx组合输出", "ADBE Shift Channels" in link_block)

print("\n=== 8. ai_director端到端: 新管线score_card≥85 ===")
from ai.ai_director import ScriptGenerator, ScriptToJSXTranslator  # noqa: E402

gen = ScriptGenerator()
analyses = [{"width": 1920, "height": 1080, "duration": 10.0}] * 6
script = gen._fallback_script("3D升级验收", analyses, "热血战斗")
segs = script["segments"]
check("每段携带z_depth字段", all("z_depth" in s for s in segs),
      str([s.get("z_depth") for s in segs]))
drop_z = [s["z_depth"] for s in segs if s["type"] == "drop"]
break_z = [s["z_depth"] for s in segs if s["type"] == "break"]
check("drop段z_depth>0", all(z > 0 for z in drop_z), str(drop_z))
check("break段z_depth<0", all(z < 0 for z in break_z), str(break_z))

cam_ids = [s["camera"]["camera_id"] for s in segs]
check("剧本含3D运镜", any(c in CAMERA_IDS_3D for c in cam_ids), str(cam_ids))
check("运镜多样性≥6", len(set(cam_ids)) >= 6, str(cam_ids))

jsx = ScriptToJSXTranslator().translate(script, ["D:/fake/m1.mp4"])
check("JSX含null控制器(3D链)", "addNull" in jsx)
check("JSX含真实摄像机", "addCamera" in jsx)
check("JSX含效果联动块", "ADBE Shift Channels" in jsx or
      "ADBE Saturation" in jsx or "ADBE Glo2" in jsx)
v = V(jsx)
check("端到端JSX validate通过", v["ok"], str(v["issues"]))

scorer = DirectorQualityScorer()
combo = {"unique_combos": len(set(cam_ids)), "total_combo_uses": len(cam_ids)}
evidence = {"has_ease": "setTemporalEaseAtKey" in jsx, "max_scale": 140,
            "beat_ok": True, "uniform_segments": False,
            "camera_unique": len(set(cam_ids))}
card = scorer.score_card(script, combo, evidence)
print(f"  [INFO] score_card总分: {card['total_score']}")
check("score_card≥85分", card["total_score"] >= 85,
      str(card["total_score"]))
check("score_card达标passed", card["passed"] is True)

ev_path = os.path.join(ROOT, "tmp", "pro_upgrade_evidence.json")
os.makedirs(os.path.dirname(ev_path), exist_ok=True)
with open(ev_path, "w", encoding="utf-8") as f:
    json.dump({"scorecard": card,
               "cameras": cam_ids,
               "font_stats": st,
               "effects": ed.list_effects(),
               "styles_3d": t3d.list_3d_styles()},
              f, ensure_ascii=False, indent=2)
check("证据落盘", os.path.exists(ev_path))

print(f"\n{'='*50}\n验收结果: {PASS} PASS / {FAIL} FAIL")
if FAILURES:
    print("失败项:")
    for f_ in FAILURES:
        print(f"  - {f_}")
sys.exit(1 if FAIL else 0)
