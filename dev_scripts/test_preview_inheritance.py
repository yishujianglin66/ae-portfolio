# -*- coding: utf-8 -*-
"""预览系统继承能力回归测试 (V5.1)

防回退铁律 (用户目视反馈驱动):
- 48格矩阵规模保持 (V5增量)
- 字体多样化: ≥12个CJK家族覆盖 + 单家族占比≤8格 (V5.1修复"全部一个字体")
- 3D立体感: fx_extrude 深度参数化 step×12层, intense档step≥2 (V5.1修复"3D无立体感")
- 继承链: 预览字体池 ⊆ core/font_scanner 系统实扫结果
- 单帧渲染冒烟: render_frame 输出1920x1080且非纯色
"""
import importlib.util
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

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


# ── 导入预览模块 (main()守卫保证导入不触发渲染) ────────────────
spec = importlib.util.spec_from_file_location(
    "gta", os.path.join(ROOT, "tmp", "gen_text_anim_video.py"))
gta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gta)

print("=== 1. 48格矩阵规模保持 (V5增量不回退) ===")
check("ANIMS=48", len(gta.ANIMS) == 48, str(len(gta.ANIMS)))
check("FX_TABLE=48", len(gta.FX_TABLE) == 48, str(len(gta.FX_TABLE)))
check("LAYOUTS=48", len(gta.LAYOUTS) == 48, str(len(gta.LAYOUTS)))
check("8x6网格", gta.COLS == 8 and gta.ROWS == 6,
      f"{gta.COLS}x{gta.ROWS}")
kinds = [a.get("kind") for a in gta.ANIMS if a.get("kind")]
check("V5新增kind特殊渲染≥7种", len(set(kinds)) >= 7, str(set(kinds)))
check("动画函数返回键完整",
      all(set(gta.ANIMS[i]["fn"](0.6).keys()) >=
          {"text", "color", "scale", "rotation", "alpha", "ox", "oy"}
          for i in range(48)))

print("\n=== 2. 字体多样化 (V5.1: 消除'全部一个字体') ===")
fams = {}
for anim in gta.ANIMS:
    ov = gta._FONT_OVERRIDE.get(anim["en"])
    f = ov if ov else anim["font"]
    fams[gta._CJK_STYLE_MAP.get(f, "msyh")] = \
        fams.get(gta._CJK_STYLE_MAP.get(f, "msyh"), 0) + 1
print(f"  [INFO] 家族分布: {sorted(fams.items(), key=lambda x: -x[1])}")
check("CJK家族覆盖≥12种", len(fams) >= 12, str(len(fams)))
max_fam = max(fams.values())
check("单家族占比≤8格(防单字体霸屏)", max_fam <= 8, str(max_fam))
check("逐动画覆写表≥30条", len(gta._FONT_OVERRIDE) >= 30,
      str(len(gta._FONT_OVERRIDE)))
check("CJK映射表≥13家族", len(gta._CJK_STYLE_MAP) >= 13,
      str(len(gta._CJK_STYLE_MAP)))

# 映射到的每个家族必须有真实可加载的字体文件
missing = []
for fam in fams:
    try:
        fnt = gta.load_font(fam, 20)
        if fnt is None:
            missing.append(fam)
    except Exception as e:  # noqa: BLE001
        missing.append(f"{fam}:{e}")
check("全部家族字体可加载", len(missing) == 0, str(missing))

print("\n=== 3. 3D立体感参数化 (V5.1: fx_extrude深度可感知) ===")
sig = inspect.signature(gta.fx_extrude)
check("fx_extrude带step深度参数", "step" in sig.parameters,
      str(list(sig.parameters)))
check("fx_extrude带ground_shadow投影参数",
      "ground_shadow" in sig.parameters, str(list(sig.parameters)))
src = inspect.getsource(gta)
check("intense档挤出步长=2(24px深度)",
      'ex_step = 2 if anim["intensity"] == "intense"' in src)
check("extrude格padding=46容纳深度",
      'pad = 46 if kind == "extrude"' in src)
check("材质渐变shade范围0.18→0.90",
      "shade = 0.18 + 0.72 * p" in src)

# 渲染冒烟: extrude特效实际产出带深度偏移的像素
from PIL import Image, ImageDraw  # noqa: E402
probe = Image.new('RGBA', (160, 90), (0, 0, 0, 0))
ImageDraw.Draw(probe).text((40, 25), "Z", font=gta.load_font("SimHei", 40),
                           fill=(255, 255, 255, 255))
ex = gta.fx_extrude(probe, (255, 200, 90), layers=12, step=2)
# 深度方向(右下偏移12~24px处)应存在非透明像素
depth_px = sum(1 for x in range(70, 95) for y in range(60, 85)
               if ex.getpixel((x, y))[3] > 40)
check("挤出深度方向存在实体像素(>80个)", depth_px > 80, str(depth_px))

print("\n=== 4. 继承链: 预览字体池 ⊆ font_scanner 实扫 ===")
from core.font_scanner import SystemFontScanner  # noqa: E402
fs = SystemFontScanner()
scanned = fs.scan()
scanned_names = {f["name"].lower() for f in scanned}
scanned_files = {f["file"].lower() for f in scanned}
check("font_scanner实扫CJK≥10", fs.stats()["cjk"] >= 10,
      str(fs.stats()["cjk"]))
# 预览路径表中的CJK字体文件必须真实存在于扫描结果或磁盘
cjk_files_in_preview = [
    "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simkai.ttf",
    "C:/Windows/Fonts/SIMYOU.TTF", "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/simsunb.ttf", "C:/Windows/Fonts/simfang.ttf",
    "C:/Windows/Fonts/STKAITI.TTF", "C:/Windows/Fonts/STXIHEI.TTF",
    "C:/Windows/Fonts/STSONG.TTF", "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyhl.ttc",
    "C:/Windows/Fonts/NotoSerifSC-VF.ttf",
]
not_found = [p for p in cjk_files_in_preview
             if not os.path.exists(p) and
             os.path.basename(p).lower() not in scanned_files]
check("预览CJK字体池13件全部真实存在", len(not_found) == 0,
      str(not_found))
check("扫描结果含预览主力家族(simhei)",
      any("simhei" in n for n in scanned_names), str(len(scanned_names)))

print("\n=== 5. 单帧渲染冒烟 (main()守卫可导入性) ===")
img = gta.render_frame(60)
check("渲染输出1920x1080", img.size == (1920, 1080), str(img.size))
px = list(img.resize((64, 36)).getdata())
uniq = len(set(px))
check("画面非纯色(采样≥40种颜色)", uniq >= 40, str(uniq))
img2 = gta.render_frame(180)
check("不同帧画面不同",
      img.resize((64, 36)).tobytes() != img2.resize((64, 36)).tobytes())

print(f"\n{'='*50}\n继承回归结果: {PASS} PASS / {FAIL} FAIL")
if FAILURES:
    print("失败项:")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
