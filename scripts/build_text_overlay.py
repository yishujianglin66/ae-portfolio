# -*- coding: utf-8 -*-
"""文字-剪辑集成调度器 P0 (2026-09-08) — 八大方向方案 §7.1 / 交接文档 §四

定位: 文字不是静态叠加, 而是锚定镜头节拍/情绪的动态元素 (解锁 G1)。
本脚本 = 事件表规划器 + JSX 生成器, 本身不直接操作 AE:
  --dry-run  只出事件表 + JSX 不碰 AE (离线验证, 默认推荐先行)
  (无 --dry-run)  写 JSX 落盘 → 调 .ae-mcp-bridge/send_bridge.py 文件协议注入

数据输入 (缺一降级, 全缺报错):
  output/<run_dir>/production_report.json  → pr["script"]["segments"]
      (字段: start_time/end_time/mood/energy/speed; 注意顶层 segments 无 start_time, 别用错)
  tmp/true_onsets.json    [{t, s}] 真实 kick; 缺失回退 tmp/music_envelope.json strong 列表
  tmp/music_envelope.json {env, env_times, strong} RMS 包络 (能量→字号/发光缩放)
  tmp/shot_scenes_raw.json {t0: {motion, edge, skin, bright}} 肤色代理 (closeup 避让);
      缺失 → 关避障, 全部走默认位置

事件模型 (契约, P1-P3 消费):
  {t_in, t_out, hold, mood, energy, style_id, word, font, font_stack,
   probe_font, x, y, size, closeup, enter, fades, glow, tracking}

语义规则 (方案 §7.1):
  intro/outro → intro_serif 衬线居中低饱和 (衬线字体未实证 → 探针清单, 回退 BebasNeue)
  build       → build_side 无衬线侧置 (BebasNeue 已实证)
  drop        → drop_impact impact 字体居中+描边 (Anton/Impact 已实证)
  closeup (skin≥0.30 且 motion≤p70) → 避让主体框, 置上下安全带 (y=0.18h/0.82h), 字号×0.8

实证边界 (A1, 违反=翻车):
  - JSX 仅用已实证 API: addText + ADBE Text Document(font/fontSize/fillColor/applyFill/
    applyStroke/justification) / 图层 opacity(0-100) / ADBE Text Tracking Amount /
    ADBE Glo2(0002/0003/0004) / easeOutBack 位置表达式 / Scale 关键帧
  - Text Document 的 strokeColor/strokeWidth 见交接 §四已实证属性名, JSX 内 try/catch 保护
  - ES3 语法; aerender -s/-e 是帧号 (执行模式渲染时秒×24)
  - 字体实证清单 (v6, 2026-09-11 probe_font_pool.jsx 26 字体全 =YES): 见 VERIFIED_FONTS;
    字形覆盖约束: JP 词 (強発壊無縛臨韻) 只配 JP 字体, CN 池可混 JP 字体 (JIS1-2 覆盖简体常用字)

用法 (位置参数契约同 build_master_polish, 2026-09-05 公布, 不可变更):
  python scripts/build_text_overlay.py <run_dir> <tag> [--dry-run]
      [--words-json X] [--hold-mode phrase|shot] [--max-events N]
示例:
  python scripts/build_text_overlay.py unified_run53 run53 --dry-run
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 24.0
FRAME = 1.0 / FPS          # 0.0417s
ONSET_TOL = 2 * FRAME      # 节拍门: ≤2 帧

# 乐段分区 (与 build_master_polish v23 分段调色 / plan_bursts 同口径)
ZONES = [
    ("intro", 0.0, 3.3),
    ("build", 3.3, 12.7),
    ("drop", 12.7, 27.0),
    ("outro", 27.0, 1e9),
]
ZONE_CFG = {
    #            最小间距  最大保持  事件上限
    "intro": {"gap": 1.2, "hold": 2.5, "cap": 2},
    "build": {"gap": 0.85, "hold": 2.2, "cap": 6},
    "drop":  {"gap": 0.60, "hold": 0.95, "cap": 15},   # v39 cap 12→15: 供"补洞"使用 (见 MAX_GAP)
    "outro": {"gap": 1.2, "hold": 2.5, "cap": 2},
}
# v39 最大空档约束 (Boss: "几乎能跟上音乐节奏踩点, 继续推进")
# 实测诊断: 强度贪心 + 0.60s 间距护栏 的交互会剪掉"紧邻已选强拍"的强拍 —— drop 区
#   23.24→26.01 留下 2.77s 无字空档, 而其间 25.55 强度 0.81 (全片第 14 强) 竟未入选;
#   16.78→18.62 同样留 1.84s 空档 (17.70 强度 0.71 未入选)。
# 只约束 drop (高潮段): build 段的长保持是"收", 有意为之, 不动。
MAX_GAP = {"intro": 99.0, "build": 99.0, "drop": 1.15, "outro": 99.0}
BEAT_PULSE_THR = 0.55      # v39 保持期内脉冲入选阈值 (归一强度); 未达标则保底取最强 1 拍

# ── v44 "字效预设" (Boss: "新的成品和以前没啥区别" → 承认在单一样式内调参已到感知阈值以下) ──
# 实测依据: drop 15 次命中按 **(字号20px档 + 位置 + 光晕色)** 聚类只有 9 种、最大重复 3 次;
#   按 (字体+精确字号+位置+填充色) 聚类则 15/15 各异 —— 说明前几轮优化的是"属性方差",
#   而观众感知的是"外观种类"。位置 13/15 挤在三个点、发光色 12/15 是完全相同的青蓝。
# 方案: 4 种**真正不同**的字效轮换 (每相邻两次必然不同款) + 字号三档拉开动态范围(极差 ~1.7x),
#   并把"最强拍"升档到特大号 —— 让"音量"跟着音乐走, 而不是 15 次一样响。
LOOKS = ("solid", "hollow", "invert", "tilt")
LOOK_DESC = {
    "solid":  "实心 (现状: 白字+深描边+冷光晕)",
    "hollow": "空心 (无填充+粗反差描边+同色光晕)",
    "invert": "反相 (彩色填充+浅描边+收光晕)",
    "tilt":   "倾斜 (构图打破永远水平居中)",
}
SIZE_TIERS = (1.0, 0.60, 0.86)      # 循环档: 大 / 小 / 中  (小号是刻意留的"轻喊")
SIZE_TIER_XL = 1.16                 # 音乐局部强度 ≥0.85 的最强拍升到此档
XL_PROMOTE_LI = 0.85

# ── v46 排版预设 (Boss: "效果不错继续下一步") ──
# 上一版四个字效仍共用"水平单行"这一个排版框架 —— 那才是构图层面最后的单一。
# 本版引入结构性排版, 但**保持单行为主** (周期 4 里占 2): 结构变化太频繁会伤可读性,
# 目标是"偶尔一次构图级惊喜", 而不是每次都变形。
LAYOUTS = ("single", "stack", "single", "vertical")
LAYOUT_DESC = {
    "single":   "单行 (基线)",
    "stack":    "双行堆叠 — 字形块更高更窄, 轮廓完全不同",
    "vertical": "竖排 (一字一行) — 汉字天然可读; 拉丁词自动降级为 stack",
}
LAYOUT_H_PEAK = 900.0               # 高度守卫: 弹性峰值 138% 下多行块必须落框内 (1080 留边)
LAYOUT_LEAD_RATIO = 1.02            # 多行行距 = 字号 × 此值 (默认 auto leading 偏松)


def _has_cjk(s: str) -> bool:
    return any("\u3400" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" for ch in s)


def apply_layout(word: str, lay: str):
    """把词排成指定版式 → (带换行的文本, 行数)。

    AE 的 TextDocument 用 '\\r' 作换行符 (不是 '\\n')。
    拉丁词不做一字一行 (B/R/E/A/K 会读不出), 自动降级为双行。
    """
    if len(word) < 2 or lay == "single":
        return word, 1
    if lay == "vertical":
        if not _has_cjk(word):
            lay = "stack"
        else:
            return "\r".join(word), len(word)
    k = (len(word) + 1) // 2
    return word[:k] + "\r" + word[k:], 2

ZONE_END_GUARD = 0.35     # 锚点距分区结束 <0.35s 不选 (会被钳成不可读短事件)
DROP_POS_CYCLE = [(960, 540), (700, 380), (1220, 700)]   # v9: 内收 (v8 实证 620/1300 宽字超框)
ONSET_S_THR = 0.40         # 归一化强度阈值 (D4 口径 s≥0.5 收紧到 0.4 保覆盖)
# v37 时段处理强度分级 (Boss: "应该局部或者某些时间段应用" / "感觉没啥变化")
# 实证依据: 逐帧"成片 vs 原始素材"差异曲线显示 安静段(9.69) 竟强于 drop 段(8.00)
#   → 之前所有改动只动短暂特效(占比极小), 真正影响观感的是"文字本身一直很重"
# 分级: intro 极简(细描边/无发光) → build 轻(弱发光) → drop 满(重描边+强发光+特效) → outro 柔
ZONE_TREAT = {
    # size=字号倍率 (实证: 光晕/描边的差异对"视觉重量"影响有限, 字号才是主杠杆)
    "intro": {"glow": 0.0,  "stroke": 2.5, "shadow": 0.5, "bevel": 0.4, "shimmer": False, "size": 0.78},
    "build": {"glow": 0.45, "stroke": 5.5, "shadow": 0.8, "bevel": 0.7, "shimmer": False, "size": 0.70},
    "drop":  {"glow": 1.0,  "stroke": 12.0, "shadow": 1.0, "bevel": 1.0, "shimmer": True, "size": 1.10},
    "outro": {"glow": 0.6,  "stroke": 4.5, "shadow": 0.9, "bevel": 0.8, "shimmer": False, "size": 0.95},
}

# 字体: font_stack[0] 为首选 (probe_font=true 表示未实机实证, 探针不过则用栈尾已实证字体)
# v2 样式 (2026-09-10 Boss 反馈"效果太普通"后升级, 配方①描边投影+④双层发光+⑦轻斜面):
#   glow/glow2 = (threshold 0-255, radius, intensity) —— 实证序号: 0002=阈值(0-255!), 0003=半径, 0004=强度
#   shadow = (opacity 0-1, direction deg, distance, softness) —— ADBE Drop Shadow 0002/3/4/5
#   bevel  = (edge_thickness, light_angle, light_intensity) —— ADBE Bevel Alpha 0001/2/4
STYLES = {
    "build_side": {
        "size": (98, 134), "fill": [0.95, 0.95, 0.98],
        "stroke": ([0.03, 0.03, 0.06], 2.2), "pos": "side_alt", "enter": "slide_back",
        # W2 入场变款循环: 滑入 / 上升揭示 / 横向揭示 (Linear Wipe, 层级效果 → 字体安全)
        "enter_cycle": ["slide_back", "wipe_up", "slide_back", "wipe_right"],
        "glow": (130, 18, 0.9), "glow2": None,
        "shadow": (0.6, 135, 6, 8), "bevel": (2, -45, 0.35),
        "tracking": None,
        # v7 禁用 RS 动画器 (typewriter/cascade): 实证动画范围选择器切换逐字光栅化路径时
        # 脚本设置的字体被静默替换为默认字体 (v6.1 二分: punch/elastic/无动画层字体全部正常)
        "typewriter": False,
    },
    "intro_serif": {
        "size": (100, 125), "fill": [0.96, 0.94, 0.89],
        "stroke": ([0.05, 0.04, 0.06], 1.8), "pos": "center", "enter": "fade_scale",
        # W2 入场变款循环 (开场/收尾): 缩放淡入 / 上升揭示 / 模糊淡入 / 横向揭示
        "enter_cycle": ["fade_scale", "wipe_up", "blurfade", "wipe_right"],
        "glow": (150, 30, 0.55), "glow2": None,
        "shadow": (0.45, 135, 5, 15), "bevel": None,
        "tracking": None,
        "blurfade": True,     # v3: 模糊淡入（手册 §十七, ADBE Gaussian Blur 2 prop1: 60→0）
    },
    "drop_impact": {
        "size": (150, 196), "fill": [1.0, 1.0, 1.0],
        "stroke": ([0.02, 0.02, 0.05], 5.0), "pos": "center",
        "enter": "punch_tracking",
        # v8: 去 Bloom 第二发光 (Boss"特效重复添加"观感 = 双发光叠加); 主发光大幅收紧防全帧提亮
        "glow": (115, 25, 1.7), "glow2": None,
        "shadow": (0.78, 135, 10, 12), "bevel": (3, -45, 0.55),
        "tracking": 110,   # v9: 250→110 (v8 实证 punch 展开期 5 字母超框被切)
        "cascade": False,   # v7 禁用: RS 动画器与脚本字体互斥 (见 build_side 注)
        "elastic": True,    # 弹性缩放砸入: amp*sin/exp 衰减表达式（层变换, 字体安全）
        "shockwave": False, # v4 关闭: 合成级白固态闪光（视频被影响的感知来源）
    },
}
MOOD_TO_STYLE = {"intro": "intro_serif", "build": "build_side",
                 "drop": "drop_impact", "outro": "intro_serif"}

# v27 W4 情绪档案 (mood profile): 同一份音乐可演绎成不同风格, 由 CLI 切换
# chroma=通道分离 / wipe=遮罩揭示 / drift_mul=漂移幅度倍率 / glow_mul=发光倍率 / pulse_mul=节拍脉冲倍率
MOOD_PROFILES = {
    "auto":    None,                                                  # 保持既有行为
    "impact":  {"chroma": True,  "wipe": True,  "drift_mul": 1.2, "glow_mul": 1.15, "pulse_mul": 1.15},
    "elegant": {"chroma": False, "wipe": True,  "drift_mul": 0.7, "glow_mul": 0.85, "pulse_mul": 0.75},
    "kinetic": {"chroma": True,  "wipe": False, "drift_mul": 1.5, "glow_mul": 1.05, "pulse_mul": 1.35},
}

# ── v18 字体池 (2026-09-11 重建: HKLM 真相表 + fontTools cmap 字形覆盖双校验) ──
# 铁律: ① AE 只解析 HKLM 系统字体 (用户目录字体不可见) ② 必须校验 cmap 覆盖——
#   日文词 (強発壊無縛臨韻) 只有部分字体覆盖 (实测 琥珀/彩云/新魏/行楷/粗黑宋 = 9/17 不覆盖!),
#   故 jp 池只收 17/17 全覆字体 (LiSu/DengXian-Bold/YuGothic系/MS-Gothic系/STSong系/STXihei),
#   cn 池才能用装饰性字体 (琥珀/彩云/新魏/彩色系). 覆盖表见 tmp/check_glyph_coverage.py
FONT_POOLS = {
    "drop_impact": {   # 冲击词: v24 厚重字体回归池首 (细/装饰体后置, 避免整体观感变轻变平)
        "jp":    ["YuGothic-Bold", "MS-PGothic", "DengXian-Bold", "LiSu"],
        "cn":    ["FZCCHFW--GB1-0", "HYa0gj", "FZHPFW--GB1-0", "FZCHSJW--GB1-0", "STHupo", "STCaiyun"],
        "latin": ["Anton-Regular", "BlackOpsOne-Regular", "AlfaSlabOne-Regular",
                  "GillSans-UltraBoldCondensed", "CooperBlack", "Bangers-Regular",
                  "MetalMania-Regular", "Blanka-Regular", "321impact",
                  "BebasKai", "Brat", "BroadcastMatter", "FasterOne-Regular"],
    },
    "build_side": {    # 铺垫词 (4-11s 段): v25 换成有个性的字体 (原 等线/平黑/Lato 被 Boss 判不达标)
        "jp":    ["LiSu", "DengXian-Bold", "YuGothic-Bold", "STZhongsong"],
        "cn":    ["FZHPFW--GB1-0", "FZSTFW--GB1-0", "STHupo", "FZKTFW--GB1-0"],
        "latin": ["HansonBold", "BrandonGrotesque-Black", "Kanit-Black", "321impact",
                  "BebasNeue-Bold", "Inter-Black"],
    },
    "intro_serif": {   # 开场/收尾: 厚重衬线优先, 细花体后置
        "jp":    ["STZhongsong", "STFangsong", "YuGothic-Light"],
        "cn":    ["FZSSFW--GB1-0", "FZKTFW--GB1-0", "STXingkai", "STLiti", "STKaiti"],
        "latin": ["AlfaSlabOne-Regular", "BowlbyOneSC-Regular", "BodoniMTBlack",
                  "CopperplateGothic-Bold", "AutourOne-Regular", "Asset-Regular",
                  "DrSugiyama-Regular", "GreatVibes-Regular", "Allura-Regular"],
    },
}
# ── v47 细体池 (Boss 选定方向: "克制为主 + 偶发重音", 中文换细体) ──
# 全部字面已过 A1 实证 (probe_light_fonts.jsx: 同词逐字面渲 1 帧, 判据双条 ——
#   ① 任意两格像素完全相同 = 至少一个被静默替换; ② 标称 Light/Thin 必须明显细于默认粗体)。
#   实测: 无任何两格相同, 且白像素占比按预期分层 (仿宋 0.038 < 正黑细 0.039 < 等线细 0.041
#   < 楷体 0.048 < 普惠体细 0.051 < 雅黑细 0.056; 拉丁 Lato-Hairline 0.007 最细)。
LIGHT_POOLS = {
    "drop_calm": {
        "jp":    ["DengXian-Light", "AlibabaPuHuiTi_3_45_Light", "MicrosoftJhengHeiLight",
                  "YuGothic-Light", "FangSong", "MicrosoftYaHeiLight"],
        "cn":    ["DengXian-Light", "FangSong", "AlibabaPuHuiTi_3_45_Light",
                  "MicrosoftJhengHeiLight", "KaiTi", "MicrosoftYaHeiLight"],
        # 拉丁细体按"越细越靠前": 无衬线为主, 衬线体 (Merriweather) 放末尾当变奏
        "latin": ["Lato-Hairline", "BebasNeue-Light", "Kanit-Thin", "Lato-Light",
                  "Inter-Light", "BrandonGrotesque-Light", "Antonio-Light", "Merriweather-Light"],
    },
}
# 克制的取色 (不与背景"抢亮"): 暗底用奶白而非纯白, 亮底用近墨而非纯黑
CALM_CREAM = [0.95, 0.93, 0.87]
CALM_INK = [0.06, 0.06, 0.09]
CALM_TRACKING = 90          # 克制档用较宽字距 (编辑排版感), 而非冲击档的展开动画
# 极弱同色光晕 (threshold, radius, intensity): 与字同色、半径小、强度低 ——
# 目的是"让字从画面里浮起来"而不是"发光"。冲击档是 (185,20,1.7) 的青色泛光, 两者量级差 ~6 倍。
CALM_GLOW = (150, 11, 0.30)
PUNCH_TOP_N = 3             # "偶发重音": 只给音乐局部强度最高的 N 个 drop 事件保留冲击处理
CALM_SMALL_PX = 140         # 克制档小字号门限 (低于此值补细描边, 见可读性兜底)
CALM_MIN_DL = 55.0          # 字色与局部背景的最小亮度差 (低于此值补细描边)
CALM_LIGHT_BG = 140.0       # 克制档"亮底"判据 (用字期中段亮度, 非 bg_class)
# 依据: drop 的 local_i 实测区间 0.54-0.75, 若用绝对阈值(如 0.9)会一个都不触发 ——
#   故按**排名**取前 N (与 _recipe_ts 的强度优先贪心同一思路)。

VERIFIED_FONTS = {          # HKLM 真相表 + cmap 覆盖 + 渲染差分三重校验 (2026-09-11/12)
    # v47 细体批次 (probe_light_fonts.jsx 实证: 逐格互不相同 + 粗细分层符合预期)
    "AlibabaPuHuiTi_3_45_Light", "YuGothic-Light", "KaiTi",
    "DengXian-Light", "MicrosoftJhengHeiLight", "MicrosoftYaHeiLight", "FangSong",
    "BebasNeue-Light", "Kanit-Thin", "Lato-Light", "Lato-Hairline", "Inter-Light",
    "BrandonGrotesque-Light", "Antonio-Light", "Merriweather-Light",
    # 系统级安装批次一 (tmp/install_fonts_full.py, 28 个; 不含 trial)
    "Anton-Regular", "BebasNeue-Bold", "Antonio-Bold", "BlackOpsOne-Regular",
    "Bangers-Regular", "AlfaSlabOne-Regular", "BowlbyOneSC-Regular", "Blanka-Regular",
    "BungeeShade-Regular", "HansonBold", "Kanit-Black", "Kanit-ExtraBold",
    "Bumrush", "321impact", "ArtBrush",
    "FZWBFW--GB1-0", "FZCCHFW--GB1-0", "FZH4FW--GB1-0", "FZHPFW--GB1-0",
    "FZHTFW--GB1-0", "FZPHFW--GB1-0", "FZSSFW--GB1-0", "FZKTFW--GB1-0",
    "FZSTFW--GB1-0", "HYa0gj", "GBWeiBei-Bold", "SungtiEG-Ultra-GB",
    # L1 白名单批次 (scripts/install_fonts_l1.py, 84 个)
    "BebasKai", "Brat", "BroadcastMatter", "FasterOne-Regular", "MetalMania-Regular",
    "Creepster-Regular", "GreatVibes-Regular", "Allura-Regular", "DrSugiyama-Regular",
    "Chewy-Regular", "LuckiestGuy-Regular", "Asset-Regular", "AutourOne-Regular",
    "Lato-Black", "Inter-Black", "BrandonGrotesque-Black", "AlegreyaSansSC-Black",
    "Kanit-Thin", "Merriweather-Black", "Eater-Regular", "LondrinaShadow-Regular",
    "LondrinaOutline-Regular", "FascinateInline-Regular", "Codystar-Light",
    "Galada-Regular", "Charmonman-Bold", "Elianto-Regular", "Hundo", "Aspire-DemiBold",
    "Barriecito-Regular", "Flavors-Regular", "HennyPenny-Regular", "FingerPaint-Regular",
    "BadScript-Regular", "HerrVonMuellerhoff-Regular",
    # 既有系统字体
    "LiSu", "DengXian-Bold", "YuGothic-Bold", "YuGothic-Medium", "YuGothic-Regular",
    "YuGothic-Light", "MS-PGothic", "MS-Gothic", "STHupo", "FZCHSJW--GB1-0",
    "STCaiyun", "STXinwei", "STKaiti", "STXingkai", "STLiti", "STZhongsong",
    "STSong", "STFangsong", "STXihei", "SimSun", "SimHei", "KaiTi", "YouYuan",
    "AlibabaPuHuiTi_3_45_Light", "MicrosoftYaHei-Bold",
    "Impact", "Haettenschweiler", "Arial-Black", "GillSans-UltraBoldCondensed",
    "CooperBlack", "BodoniMTBlack", "FranklinGothic-Heavy", "FranklinGothic-DemiCond",
    "SegoeUIBlack", "ShowcardGothic-Reg", "Stencil", "Rockwell-ExtraBold",
    "CopperplateGothic-Bold", "CenturyGothic-Bold", "AgencyFB-Bold",
    "BernardMT-Condensed", "TwCenMT-CondensedBold", "TrebuchetMS-Bold",
    "Georgia", "Rockwell", "GloucesterMT-ExtraCondensed", "BerlinSansFB-Bold",
}
JP_ONLY_CHARS = set("強発壊無縛臨韻")      # 词库内 JP 专字形 (JP 字体优先保字形正确)


def script_class(word):
    """jp=含 JP 专字形; cn=仅通用汉字; latin=ASCII"""
    if any(ch in JP_ONLY_CHARS for ch in word):
        return "jp"
    if any("\u4e00" <= ch <= "\u9fff" for ch in word):
        return "cn"
    return "latin"


# v28 字体-文字系兼容白名单 (依据 tmp/check_glyph_coverage.py 实测 cmap 结果)
JP_SAFE_FONTS = {          # 日文词全覆盖 (17/17)
    "LiSu", "DengXian-Bold", "YuGothic-Bold", "YuGothic-Medium", "YuGothic-Regular",
    "YuGothic-Light", "MS-PGothic", "MS-Gothic", "STSong", "STZhongsong", "STFangsong",
    "STXihei", "SimSun", "SimHei", "KaiTi", "STKaiti", "YouYuan", "AlibabaPuHuiTi_3_45_Light",
}
CN_SAFE_FONTS = JP_SAFE_FONTS | {   # 中文词额外可用 (中文 11/11, 日文不足)
    "STHupo", "STCaiyun", "STXinwei", "STXingkai", "STLiti", "MicrosoftYaHei-Bold",
    "FZCHSJW--GB1-0", "FZCCHFW--GB1-0", "FZH4FW--GB1-0", "FZHPFW--GB1-0", "FZHTFW--GB1-0",
    "FZPHFW--GB1-0", "FZSSFW--GB1-0", "FZKTFW--GB1-0", "FZSTFW--GB1-0", "FZWBFW--GB1-0",
    "HYa0gj", "GBWeiBei-Bold", "SungtiEG-Ultra-GB",
}


def font_allowed_for_script(font, scl):
    """latin 词: 任意已实证字体; cn 词: 中文白名单; jp 词: 仅日文全覆白名单"""
    if scl == "latin":
        return True
    if scl == "cn":
        return font in CN_SAFE_FONTS
    return font in JP_SAFE_FONTS

# 默认词库 (报告无歌词素材 → 按源 IP 咒术回战/五条悟 的 AMV 惯用词)
# v25: 词库外置 —— 若 data/text_overlay_words.json 存在则覆盖 (改文字无需改代码)
DEFAULT_WORDS = {
    "intro": ["五条悟", "THE STRONGEST"],
    "build": ["無限", "束縛", "加速", "VIOLATION", "迂回", "LIMIT",
              "静止", "臨界", "REVERSE"],
    "drop":  ["最強", "BREAK", "爆発", "無下限", "ZERO", "IMPACT",
              "崩壊", "RED", "虚式"],
    "outro": ["THE END", "余韻"],
}
WORDS_FILE = "data/text_overlay_words.json"
TIMELINE_FILE = "data/text_overlay_timeline.json"   # v28: 时间→文字(可带字体) 对应表
TIMELINE_TOL = 0.6                                  # 事件锚点与该时刻相差 ≤ 此值即命中 (秒)
# run 目录名 / tag 白名单 (路径安全: 严格 fullmatch 防遍历; 与 build_master_polish 对齐)
# Step1.5: 放宽接受 R1 修复run (unified_r1_fixed_vN) → 文字链也能指向 R1 成果
RUN_DIR_PATTERN = r"unified_(?:run\d+|r1_fixed_v\d+)"
TAG_PATTERN = r"run\d+"


def load_timeline():
    """时间-文字对应表: [{t, word, font?}] —— 存在则优先于分区词库的循环分配"""
    p = ROOT / TIMELINE_FILE
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] 时间表解析失败, 忽略: {e}")
        return []
    items = raw if isinstance(raw, list) else raw.get("timeline", [])
    out = []
    for it in items:
        if isinstance(it, dict) and "t" in it and it.get("word"):
            try:
                out.append({"t": float(it["t"]), "word": str(it["word"]),
                            "font": it.get("font") or None,
                            "note": it.get("note") or ""})
            except (TypeError, ValueError):
                print(f"[WARN] 时间表条目非法, 跳过: {it}")
    out.sort(key=lambda x: x["t"])
    return out


def load_words(override: dict | None = None) -> dict:
    """词库优先级: --words-json > data/text_overlay_words.json > DEFAULT_WORDS"""
    words = {k: list(v) for k, v in DEFAULT_WORDS.items()}
    p = ROOT / WORDS_FILE
    if p.exists():
        try:
            ext = json.loads(p.read_text(encoding="utf-8"))
            for k, v in ext.items():
                if isinstance(v, list) and v:
                    words[k] = list(v)
        except Exception as e:
            print(f"[WARN] 词库文件解析失败, 用默认: {e}")
    if override:
        for k, v in override.items():
            if isinstance(v, list) and v:
                words[k] = list(v)
    return words

COMP_NAME = "run53_premium_v3"     # 验收基线合成 (交接 §一)
AEP_NAME = "run53_premium_v3.aep"


# ── 数据加载 (缺省降级, 与 build_master_polish 同源逻辑) ────────────────
def load_segments(run_dir: Path):
    pr = json.loads((run_dir / "production_report.json").read_text(encoding="utf-8"))
    return pr["script"]["segments"]


def load_onsets():
    """true_onsets 缺失回退 strong 列表 (交接 §八.3)"""
    p = ROOT / "tmp" / "true_onsets.json"
    if p.exists():
        return [(float(d["t"]), float(d["s"])) for d in json.loads(p.read_text(encoding="utf-8"))]
    d = json.loads((ROOT / "tmp" / "music_envelope.json").read_text(encoding="utf-8"))
    return [(float(t), 1.0) for t in d["strong"]]


def load_envelope_at():
    p = ROOT / "tmp" / "music_envelope.json"
    if not p.exists():
        return lambda t: 0.5
    d = json.loads(p.read_text(encoding="utf-8"))
    times, env = d["env_times"], d["env"]

    def at(t):
        i = min(range(len(times)), key=lambda k: abs(times[k] - t))
        return float(env[i])
    return at


def load_scenes():
    """{t0(str, 3位小数): {motion, skin, ...}}; 缺失返回空 dict → 关避障"""
    p = ROOT / "tmp" / "shot_scenes_raw.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def zone_of(t):
    for name, lo, hi in ZONES:
        if lo <= t < hi:
            return name
    return "outro"


# ── 事件规划 ────────────────────────────────────────────────────────────
def plan_events(segs, onsets, env_at, scenes, words, hold_mode="phrase",
                max_events=None, total_dur=None, bg_video=None,
                profile=None, entropy=0.65, speed=1.0, seed=20260912, mood_name="auto",
                timeline=None, tl_tol=TIMELINE_TOL):
    """产出事件表 + 逐 segment 处置表 (显式记账, 不静默丢)"""
    if total_dur is None:
        total_dur = float(segs[-1]["end_time"]) if segs else 0.0
    smax = max(s for _, s in onsets) if onsets else 1.0
    smax = smax if smax > 0 else 1.0
    seg_bounds = [(float(s["start_time"]), float(s["end_time"])) for s in segs]

    # 1) 按强度贪心选锚点 (强优先, 间距护栏, 分区 cap)
    picked = []          # [(t, s_norm, zone)]
    for zone, _lo, _hi in ZONES:
        cfg = ZONE_CFG[zone]
        cands = sorted(((t, s / smax) for t, s in onsets
                        if zone_of(t) == zone and s / smax >= ONSET_S_THR),
                       key=lambda x: -x[1])
        n_zone = 0
        for t, sn in cands:
            if n_zone >= cfg["cap"]:
                break
            # 间距护栏: 区内用本区 gap; 跨分区只做 0.30s 边界护栏
            # (原实现误用本区 gap 对全区已选事件检查, 会把 outro 开场锚点误杀)
            if any(abs(t - pt) < cfg["gap"] for pt, _sn, pz in picked if pz == zone):
                continue
            if any(abs(t - pt) < 0.30 for pt, _, _ in picked):
                continue
            # 锚点必须落在有效镜头内 (找包含或紧邻镜头)
            if _shot_index(seg_bounds, t) is None:
                continue
            # 分区尾护栏: 太贴近分区界的锚点会被钳成 <0.25s 不可读事件
            z_end = min(z[2] for z in ZONES if z[0] == zone)
            if z_end - t < ZONE_END_GUARD:
                continue
            picked.append((t, sn, zone))
            n_zone += 1

    # 1b) v39 补洞: 把超过 MAX_GAP 的无字空档用"该空档内最强且合法"的 onset 填上
    #     为什么单独做这一步: 贪心是"局部最优", 它先选了 A 就必然剪掉 A±0.6s 内的强拍 B,
    #     但 B 可能是填洞的唯一人选 —— 所以必须按"时间轴覆盖率"再做一遍, 而不是放松阈值
    #     (放松阈值会让强拍邻居更早被剪, 反而更糟)。
    for zone, _lo, _hi in ZONES:
        mg = MAX_GAP.get(zone, 99.0)
        if mg >= 99.0:
            continue
        cfg = ZONE_CFG[zone]
        hi = _hi
        for _round in range(4):                        # 每轮每个空档补 1 个, 最多 4 轮
            zp = sorted(p for p in picked if p[2] == zone)
            if len(zp) >= cfg["cap"]:
                break
            added = 0
            for a, b in zip(zp, zp[1:]):
                if b[0] - a[0] <= mg:
                    continue
                if len([p for p in picked if p[2] == zone]) >= cfg["cap"]:
                    break
                lo_i, hi_i = a[0] + cfg["gap"], b[0] - cfg["gap"]
                cs = [(t, s / smax) for t, s in onsets
                      if lo_i <= t <= hi_i and s / smax >= ONSET_S_THR
                      and zone_of(t) == zone
                      and hi - t >= ZONE_END_GUARD
                      and _shot_index(seg_bounds, t) is not None
                      and all(abs(t - pt) >= 0.30 for pt, _, _ in picked)]
                if not cs:
                    continue
                t, sn = max(cs, key=lambda x: x[1])
                picked.append((t, sn, zone))
                added += 1
            if not added:
                break

    if max_events:
        picked = sorted(picked, key=lambda x: -x[1])[:int(max_events)]
    picked.sort(key=lambda x: x[0])

    # 2) 逐事件生成 (t_in=onset, t_out 见 hold_mode)
    events = []
    bank_pos = {z: 0 for z in ZONE_CFG}
    env_vals = [env_at(t) for t, _, _ in picked]
    env_max = max(env_vals) if env_vals else 1.0
    side_flip = 0
    font_pos = {}        # v6 池内轮换游标 (按 样式×文字系 独立, 保证每池首字都能轮到)
    last_font = {}
    wf_map = {}          # v18 词→最近一次字体 (同词换字体)
    enter_pos = {}       # W2 入场变款游标 (按样式)
    drop_ord = 0         # v43 drop 段"逐次变款"序数 (按 zone=drop 递增)
    _rng = random.Random(seed)                 # 非安全用途: 确定性变款控制 (同 seed 同输出, 可复现性要求)
    _prof = profile or {}
    _ent = max(0.0, min(1.0, float(entropy)))
    _sp = 1.0 / max(float(speed), 0.1)          # 时长缩放 (speed 越大入场越快)
    _glow_mul = float(_prof.get("glow_mul", 1.0))
    _drift_mul = float(_prof.get("drift_mul", 1.0))
    _pulse_mul = float(_prof.get("pulse_mul", 1.0))
    _plugins_on = os.environ.get("TEXT_OVERLAY_PLUGINS", "1") not in ("0", "false", "False")
    # v35 音乐结构驱动强度: 用音乐包络的**局部强度**决定"哪里给特效、给多强"(替代固定隔拍)
    # 副歌/高潮(包络高)密而强, 主歌(包络低)疏而弱 → 留白跟着音乐呼吸
    _env_raw = [env_at(t) for t, _, _ in picked] if picked else [0.5]
    _sv = sorted(_env_raw)
    def _pct(vals, p):
        if not vals:
            return 0.0
        return vals[min(int(len(vals) * p), len(vals) - 1)]
    _lo, _hi = _pct(_sv, 0.10), _pct(_sv, 0.95)
    def _nrm(v):
        return 0.0 if _hi <= _lo else max(0.0, min(1.0, (v - _lo) / (_hi - _lo)))
    def _local_i(t):
        vs = [env_at(t + d) for d in (-0.4, -0.2, 0.0, 0.2, 0.4)]
        return round(_nrm(sum(vs) / len(vs)), 3)
    # v35 阈值: 以 **drop 区事件**的局部强度中位数为界 → 只有该区里较响的拍子才给特效
    # (若用全体事件分位, 会被 intro/build 的安静值拉偏 → 特效过稀, 实测仅 1 个)
    _drop_t = []
    for _t, _sn, _z in picked:
        _si = _shot_index([(float(s["start_time"]), float(s["end_time"])) for s in segs], _t)
        if _si is not None and zone_of(_t) == "drop":
            _drop_t.append(_local_i(_t))
    _thr_rec = round(sorted(_drop_t)[len(_drop_t) // 2], 3) if _drop_t else 0.5
    _last_recipe_t = None
    # v35 选取策略: 强度优先贪心 (先选最响的拍, 再选距其 ≥1.0s 的次响拍)
    # —— 时间序先到先得会让"最响的拍"因间隔规则被漏掉 (实测安静拍里出现过 local_i 0.948)
    RECIPE_MIN_GAP = 1.0                                            # 特效事件最小间隔(秒), 防扎堆
    _cand = sorted([(t, _local_i(t)) for t, _sn, _z in picked if _z == "drop"], key=lambda x: -x[1])
    _sel = []
    for _t, _li2 in _cand:
        if _li2 < _thr_rec:
            break
        if all(abs(_t - _st) >= RECIPE_MIN_GAP for _st in _sel):
            _sel.append(_t)
    _recipe_ts = {round(t, 3) for t in _sel}
    # v47 "偶发重音": 只给音乐局部强度最高的 PUNCH_TOP_N 个 drop 事件保留冲击处理, 其余走克制。
    # 用**排名**而非绝对阈值 —— drop 的 local_i 实测区间 0.54-0.75, 阈值法会一个都不触发。
    _punch_ts = {round(t, 3) for t, _li3 in
                 sorted([(t, _local_i(t)) for t, _sn, _z in picked if _z == "drop"],
                        key=lambda x: -x[1])[:PUNCH_TOP_N]}
    for i, (t, sn, zone) in enumerate(picked):
        cfg = ZONE_CFG[zone]
        mood = "outro" if zone == "outro" else zone
        style_id = MOOD_TO_STYLE[mood]
        st = STYLES[style_id]
        si = _shot_index(seg_bounds, t)
        seg = segs[si]
        t0, t1 = seg_bounds[si]

        t_in = max(t, t0)                       # onset 贴镜头内即用原值, 越界钳到镜头头
        t_in = round(t_in, 3)
        nxt = picked[i + 1][0] if i + 1 < len(picked) else 1e9
        z_end = min(z[2] for z in ZONES if z[0] == zone)
        if hold_mode == "shot":
            t_out = min(t1 - 2 * FRAME, t_in + cfg["hold"])
        else:  # phrase: 保持到下一切点/分区界/上限 (可读性优先; 交接 §四 契约的工程化放宽)
            t_out = min(t_in + cfg["hold"], nxt - 2 * FRAME, z_end)
        t_out = min(t_out, total_dur)                  # 不越过片长
        t_out = round(max(t_out, t_in + 0.15), 3)      # 最小保持 0.15s (≈4帧)
        hold = round(t_out - t_in, 3)

        # 词 (v28: 时间表优先 → 未命中处回退分区词库循环)
        _tl = list(timeline or [])       # 拷贝! 不可 mutate 调用方列表 (否则主流程对账看不到条目)
        _tl_font_override = None
        _tl_hit = None
        for _k, _item in enumerate(_tl):
            if abs(_item["t"] - t_in) <= tl_tol:
                _tl_hit = _tl.pop(_k)
                break
        if _tl_hit is not None:
            w = _tl_hit["word"]
            _tl_font_override = _tl_hit.get("font")
        else:
            bank = words.get(zone) or words.get(mood) or ["TEXT"]
            w = bank[bank_pos[zone] % len(bank)]
            if len(events) and events[-1]["word"] == w:
                w = bank[(bank_pos[zone] + 1) % len(bank)]
                bank_pos[zone] += 1
            bank_pos[zone] += 1
        _from_tl = _tl_hit is not None

        # v6: 字体按文字系分池轮换 (jp/cn/latin 见 FONT_POOLS), 池内不背靠背重复
        scl = script_class(w)
        pool = FONT_POOLS[style_id][scl]
        fkey = (style_id, scl)
        font = pool[font_pos.get(fkey, 0) % len(pool)]
        _adv = 1 if _rng.random() < _ent else 0
        if _adv == 0 and last_font.get(fkey) == font and len(pool) > 1:
            _adv = 1                              # entropy=0 时也避免背靠背同款
        if last_font.get(fkey) == font and len(pool) > 1:
            font = pool[(font_pos.get(fkey, 0) + 1) % len(pool)]
            font_pos[fkey] = font_pos.get(fkey, 0) + 1
        font_pos[fkey] = font_pos.get(fkey, 0) + _adv
        last_font[fkey] = font
        # v28 时间表字体指定: 需已实证 + 覆盖该词文字系 (覆盖判定基于实测 cmap 结果)
        if _tl_font_override:
            if _tl_font_override not in VERIFIED_FONTS:
                print(f"[WARN] 时间表字体未实证, 忽略: {_tl_font_override} (词 {w})")
            elif not font_allowed_for_script(_tl_font_override, scl):
                print(f"[WARN] 时间表字体 {_tl_font_override} 不覆盖 {scl} 字形, 忽略 (词 {w})")
            else:
                font = _tl_font_override
        # v18: 同一个词再次出现时换字体 (词-字体去重, 防同词同款)
        if wf_map.get(w) == font and len(pool) > 1:
            font = pool[(font_pos.get(fkey, 0)) % len(pool)]
            font_pos[fkey] = font_pos.get(fkey, 0) + 1
        wf_map[w] = font

        # v8: 发光按文字系大幅收紧 — 全片逐帧扫描实证 107/720 帧整帧提亮 (峰值+13),
        # 来源=文字白墨+光晕覆盖画面 20-30% 面积 (Boss"视频被影响/亮度过剩"的量化根因);
        # 收紧目标: 阈值抬高只让最亮核心发光 + 半径砍半 + 去 Bloom 第二发光
        glow, glow2, bevel, pulse = st["glow"], st.get("glow2"), st.get("bevel"), 1.7
        if scl in ("jp", "cn"):
            glow = (185, 14, round(glow[2] * 0.62, 3)) if glow else glow
            glow2 = None
            bevel = (bevel[0], bevel[1], round(bevel[2] * 0.55, 3)) if bevel else bevel
            pulse = 1.28
        elif glow:   # latin
            glow = (158, 16, round(glow[2] * 0.78, 3))
            glow2 = None
            pulse = 1.42

        # 能量 → 字号/发光 (镜头 energy × 包络 归一混合)
        shot_en = float(seg.get("energy", 0.4))
        env_n = (env_at(t_in) / env_max) if env_max > 0 else 0.5
        energy = round(min(1.0, 0.55 * shot_en + 0.45 * env_n), 3)
        sz_lo, sz_hi = st["size"]
        size = int(round(sz_lo + (sz_hi - sz_lo) * energy))

        # 位置 (语义规则 + closeup 避让)
        sc = scenes.get(str(round(t0, 3)))
        closeup = bool(sc and sc.get("skin", 0) >= 0.30
                       and sc.get("motion", 99) <= _skin_p70(scenes))
        x, y = 960, 540
        if st["pos"] == "center":
            if closeup:
                y = int(1080 * (0.18 if side_flip % 2 == 0 else 0.82))
                size = int(size * 0.8)
                side_flip += 1
            elif style_id == "drop_impact":
                # v4.1: 背景亮度感知选位 (双时刻加权, 防白字压高光; 回退轮换)
                x, y = _pick_dark_pos(t_in, bg_video, bank_pos[zone], hold=hold)
        else:  # side_alt
            x = int(1920 * (0.30 if side_flip % 2 == 0 else 0.70))
            y = int(1080 * 0.42)
            side_flip += 1
            if closeup:
                y = int(1080 * (0.18 if side_flip % 2 == 0 else 0.82))

        # W2 三维层 (2026-09-11 探针: 基底4层全2D → 加摄像机不影响基底; 默认 z=-2666.67 为1:1)
        # 仅 drop 区 (能量最高) 转 3D; z 三档轮换做纵深层次; 摄像机方案实测否决 (整帧重合成)
        z_dep = 0
        is3d = (style_id == "drop_impact")
        if is3d:
            z_dep = (0, -140, 140)[bank_pos[zone] % 3]

        # v10 对比度感知样式 (Boss"有些字发光看不出"): 12 drop 事件 9 个落在亮背景
        # (读字期最坏亮度 136-254) → 白字+白辉光融进背景; 且同一位置亮度在保持期内
        # 大幅跳变(如 82→253→74) → 必须按最坏情况定样式, 不能一刀切
        stroke_cfg = st["stroke"]
        shadow_cfg = st.get("shadow")
        glow_col = None            # (A_rgb, B_rgb); None=AE 默认白/黑
        # W1 双描边 (2026-09-11 探针: 图层样式不可脚本启用 → 用双文字层实现"彩色外环+深色内描边")
        dbl, accent, outer_w, inner_w = False, None, 0.0, 0.0
        bg_lum = _worst_region_luma(bg_video, t_in, hold, x, y)
        if bg_lum >= 150:          # 亮底: 白字白辉光物理上看不出 → 青色光晕可见 + 粗描边保读
            bg_class = "bright"
            stroke_cfg = (stroke_cfg[0], 11.0)      # v24: 9→11 加强描边(观感变弱的主因之一)
            shadow_cfg = (0.85, 135, 8, 14)
            glow = (185, 20, round((glow[2] if glow else 1.0) * 1.35, 3)) if glow else glow
            glow_col = ([0.10, 0.80, 1.0], [0.0, 0.15, 0.45])
            pulse = 1.15
            dbl, accent, outer_w, inner_w = False, None, 0.0, 0.0
        elif bg_lum >= 90:         # 中间调: 暖金光晕
            bg_class = "mid"
            stroke_cfg = (stroke_cfg[0], 9.0)       # v24: 7→9
            shadow_cfg = (0.80, 135, 10, 14)
            glow = (175, 18, round((glow[2] if glow else 1.0) * 1.20, 3)) if glow else glow
            glow_col = ([1.0, 0.66, 0.18], [0.30, 0.10, 0.0])
            pulse = 1.25
            dbl, accent, outer_w, inner_w = False, None, 0.0, 0.0
        else:                      # 暗底: 白辉光清晰可见 (保留 v11 已验收单层样式)
            bg_class = "dark"
            stroke_cfg = (stroke_cfg[0], 3.5)
            shadow_cfg = (0.55, 135, 8, 10)
            glow = (150, 18, round((glow[2] if glow else 1.0) * 1.30, 3)) if glow else glow
            pulse = 1.45

        # v17 冲击分级 (镜头运动强度归一化调制) + 通道分离冲击 (高能 drop 词)
        # 依据: v15 的线性 energy 调制对静止镜头也过强; 改用 shot_scenes motion 归一值
        mo_n = 0.5
        if sc is not None:
            mo_n = min(1.0, float(sc.get("motion", 0)) / max(_skin_p70(scenes), 1e-6))
        impact_mul = round(0.82 + 0.36 * mo_n, 3)
        chroma = bool(is3d and energy >= 0.70)   # 仅最强 3 个爆点用通道分离 (防同款连打疲劳)
        chroma_dx = round(12 + 16 * mo_n, 1)

        # v9: drop 变款全整层平移 (RS 动画器与脚本字体互斥; v8 实证旋转变款使文字倾斜超框压高光)
        # _v: 0=drop_fall 自上落下 / 1=rise_up 自下升起 / 2=纯 punch tracking
        # v29 修正: 变款循环改用事件序号 (原用 bank_pos, 但时间表命中时不推进 bank_pos → 相邻同款)
        drop_fall = rise_up = False
        if style_id == "drop_impact":
            _v = i % 3
            drop_fall, rise_up = (_v == 0), (_v == 1)

        # W2 入场变款循环 (wipe_up/wipe_right = Linear Wipe 层级效果 → 字体安全, 已探针实证)
        enter = st["enter"]
        ecyc = st.get("enter_cycle")
        if ecyc and _ent > 0:
            _eadv = 1 if _rng.random() < _ent else 0
            enter = ecyc[enter_pos.get(style_id, 0) % len(ecyc)]
            enter_pos[style_id] = enter_pos.get(style_id, 0) + max(_eadv, 1)
        elif ecyc:
            enter = ecyc[0]                       # entropy=0 → 固定首款 (最稳最一致)
        if _prof.get("wipe") is False and enter in ("wipe_up", "wipe_right"):
            enter = "fade_scale" if style_id == "intro_serif" else "slide_back"

        # v25 音乐联动: 事件窗内节拍脉冲 (供非弹性层做缩放脉冲) + 包络采样 (供发光逐帧呼吸)
        # v39 修 "保持期内有字无动作": 原取窗内最强 3 拍, 第 4 强的强拍(实测 29.23 强度 0.76)
        #   就完全没动作 → 改为"强度达标即入选", 上限 5 (避免末段长保持事件脉冲过密)。
        bz = [(round(tt, 3), round(ss / smax, 3)) for tt, ss in onsets if t_in <= tt <= t_out]
        bz.sort(key=lambda x: -x[1])
        beats = [b for b in bz if b[1] >= BEAT_PULSE_THR][:5] or bz[:1]
        n_s = 7
        env_s = [(round(t_in + hold * k / (n_s - 1), 3),
                  round((env_at(t_in + hold * k / (n_s - 1)) / env_max), 3) if env_max else 0.5)
                 for k in range(n_s)]

        # W3 运动迁移: 镜头运动强度 (shot_scenes.motion) 驱动**保持期缓慢漂移**
        # 负结果记录: 相位相关(置信0.004-0.015)/中值光流(前后景反向运动抵消≈0)/ECC(cc 0.03-0.55)
        # 三种矢量估计在本素材(平均每0.8s切点+粒子+前后景混合运动)均不可信 → 不硬凑矢量,
        # 改为: 方向取确定性循环(8 向, 按事件序号, 防重复疲劳) + 幅度随镜头运动强度(12~30px)
        _DIRS = [(0.71, -0.71), (-0.71, -0.71), (0.71, 0.71), (-0.71, 0.71),
                 (1.0, 0.0), (-1.0, 0.0), (0.0, -1.0), (0.0, 1.0)]
        _dir = _DIRS[i % len(_DIRS)]
        _amp = (12.0 + 18.0 * mo_n) * (1.2 if style_id == "drop_impact" else 1.0) * _drift_mul
        mv_dx = round(_dir[0] * _amp, 1)
        mv_dy = round(_dir[1] * _amp, 1)
        # 安全边距门禁: 估文字半宽/半高, 保证漂移后不出画
        _half_w = 0.30 * size * max(len(w), 1)
        _half_h = 0.75 * size
        mv_dx = max(min(mv_dx, 1740 - _half_w - x), -(_half_w + x - 180))
        mv_dy = max(min(mv_dy, 960 - _half_h - y), -(y - 120 - _half_h))

        # 情绪档案: 发光倍率
        if glow:
            glow = (glow[0], glow[1], round(glow[2] * _glow_mul, 3))
        chroma = bool(chroma and _prof.get("chroma", True))    # elegant 档关闭通道分离

        # v35: 计算本事件的音乐局部强度, 决定是否给冲击特效 (并记录, 供报告与强度缩放)
        _li = _local_i(t_in)
        _want_recipe = bool(style_id == "drop_impact" and beats and _plugins_on
                            and round(t_in, 3) in _recipe_ts)

        # v37 时段处理分级: 把"整体处理强度"按时段缩放 (这才是可见的收放)
        _zc = ZONE_TREAT.get(zone, ZONE_TREAT["drop"])
        if glow:
            glow = None if _zc["glow"] <= 0 else (glow[0], glow[1], round(glow[2] * _zc["glow"], 3))
        if glow2 and _zc["glow"] < 0.7:
            glow2 = None                                       # 轻时段不要双层发光
        stroke_cfg = (stroke_cfg[0], round(min(stroke_cfg[1], _zc["stroke"]), 1))
        # v38 分段字号倍率 (主杠杆): build 段文字明显变小 → 与 drop 段形成体量对比
        size = max(60, int(round(size * _zc.get("size", 1.0))))
        if shadow_cfg:
            shadow_cfg = (round(shadow_cfg[0] * _zc["shadow"], 2),) + tuple(shadow_cfg[1:])
        if bevel:
            bevel = (bevel[0], bevel[1], round(bevel[2] * _zc["bevel"], 2))
        _shimmer = _zc["shimmer"]
        if not _shimmer:
            chroma = False                                     # 通道分离只属 drop 时段

        # ── v44 字效预设 (取代 v43 的"微差变款"; 见文件头 LOOKS 的实证依据) ──
        # 保留 v43 已验证的部分: 入场跟踪展开量轮换 + "弹性峰值不超框"宽度守卫。
        # 新增: 4 种字效轮换 (相邻必不同) + 字号三档 + 最强拍升档。
        # 关键区分仍成立: 光晕色/描边宽受背景对比度约束, 所以每种字效的**取色按 bg_class 选**,
        #   而不是随意轮换色相 —— 轮换的是"字效结构"(有无填充/谁是被描边的那一方/是否倾斜)。
        fill_cfg = st["fill"]
        track_cfg = st["tracking"]
        apply_fill = True
        rot_deg = 0.0
        look_name = None
        layout_name = "single"
        word_emit = w
        n_lines = 1
        _is_calm = False                              # v47: 克制档标记 (控制 elastic/enter/踩拍动作)
        if zone == "drop":
            drop_ord += 1
            _vo = drop_ord
            _punch = round(t_in, 3) in _punch_ts          # v47: 只有最强 N 拍走冲击档
            look_name = LOOKS[(_vo - 1) % len(LOOKS)]
            layout_name = LAYOUTS[(_vo - 1) % len(LAYOUTS)]
            word_emit, n_lines = apply_layout(w, layout_name)
            layout_name = "single" if n_lines == 1 else layout_name
            tier = SIZE_TIERS[(_vo - 1) % len(SIZE_TIERS)]
            if _li >= XL_PROMOTE_LI:
                tier = SIZE_TIER_XL                           # 最强拍升档: 音量跟着音乐走
            size = max(60, int(round(size * tier)))
            # v46 排版的高度守卫 —— **位置感知**: 约束不是"块高 ≤ 某个常数", 而是
            #   "块的上下缘在弹性峰值 (138%) 下都留在安全框内", 即 peak_h ≤ 2*min(y-60, 1020-y)。
            #   实测教训: 竖排 3 行放在 y=380 时, 块高 3×168 = 504 看似没问题, 但 ×1.38 峰值
            #   达 869 → 上缘跑到 y=-54, 会被切掉 (只持续 ~0.1s, 但会被看见)。
            if n_lines >= 3:
                y = 540                                    # 竖排高块居中, 上下各留出余量
            for _ in range(14):
                _peak_h = size * 1.25 * n_lines * 1.38
                _room = 2.0 * min(y - 60, 1020 - y)
                if n_lines <= 1 or _peak_h <= min(_room, LAYOUT_H_PEAK):
                    break
                size = max(60, int(round(size * 0.92)))
            _trk = (80, 110, 145)[_vo % 3]                     # v9 记 250 会让长词在 punch 展开期超框
            # 宽度守卫: 弹性峰值 138% × 跟踪展开后的估宽。多行时按**最长那一行**算 (不是整词长度)
            _maxlen = max(len(s) for s in word_emit.split("\r"))
            def _peak_w(t):
                return size * 0.62 * max(1, _maxlen) * (1 + t / 1000.0) * 1.38
            while _trk > 0 and _peak_w(_trk) > 1780:
                _trk -= 15
            track_cfg = _trk if _trk > 0 else None

            # 按背景亮度取色。两种字效**必须用不同色相**, 否则"空心=蓝描边 / 反相=蓝填充"
            # 读起来像同一种东西 (首版对比表实测暴露的问题):
            #   hollow(空心) 用"近黑描边" —— 空心字的辨识度来自"没有填充", 颜色越中性越好;
            #   invert(反相) 用**彩色填充** —— 承担"彩色"这一身份, 亮底用深红避免与青辉光撞色,
            #                暗底用琥珀金 (与 solid 的青拉开色相)。
            _hollow_dark = [0.04, 0.05, 0.14]      # 空心落在亮底时的近黑描边
            _inv_fill = {"bright": [0.62, 0.07, 0.13], "mid": [0.85, 0.35, 0.03],
                         "dark": [1.00, 0.72, 0.15]}[bg_class]
            _acc = {"bright": [0.10, 0.80, 1.0], "mid": [1.0, 0.66, 0.18],
                    "dark": [0.30, 0.90, 1.0]}[bg_class]
            _deep = {"bright": [0.02, 0.30, 0.58], "mid": [0.52, 0.28, 0.02],
                     "dark": [0.05, 0.50, 0.80]}[bg_class]
            _light = [0.97, 0.97, 1.0]

            if look_name == "hollow":
                # 空心描边色改用**字期中段亮度**判定, 而不是 bg_class (后者取字期内最亮时刻,
                #   是给白字 + 深描边设计的保守策略)。理由: 空心只有一根描边, 它的取色必须
                #   匹配"文字真正停在那儿"的那段背景; 用最亮时刻取色会让深色描边落到暗段上
                #   (实测 #9 BREAK: 判 150 取近黑, 中段实际 76 → 深色叠深色 = 隐形)。
                _lmin, _lmax = _region_luma_range(bg_video, t_in, hold, x, y)
                _lmid = _region_luma(bg_video, t_in + 0.55 * hold, x, y)
                _lmid = 128.0 if _lmid is None else _lmid
                if (_lmax - _lmin) >= SPAN_EXTREME_DIFF:
                    # 字期内亮度摆幅极端 (爆闪类镜头) → 任何单色都保不住, 降级为反相
                    #   (实心彩色填充块 + 浅描边, 两种背景都能读)
                    look_name = "invert"
                else:
                    apply_fill = False
                    stroke_cfg = (([0.97, 0.97, 1.0] if _lmid < 140 else _hollow_dark),
                                  round(size * 0.075, 1))
                    if glow:
                        glow_col = (_acc, [c * 0.20 for c in _acc])
            if look_name == "hollow":
                pass                                   # 已在上面的分支内完成设置
            elif look_name == "invert":
                # 反相: 彩色填充 + 浅描边, 光晕收到 45% (避免与填充色打架/亮底过曝)
                fill_cfg = _inv_fill
                stroke_cfg = (_light if bg_class != "bright" else [1.0, 1.0, 1.0],
                              round(size * 0.032, 1))
                if glow:
                    glow = (glow[0], glow[1], round(glow[2] * 0.45, 3))
                chroma = False
            elif look_name == "tilt":
                # 倾斜: 只动构图 (不碰颜色), 打破"永远水平居中"
                # 注意: 用"第几次 tilt"定符号 —— 用 _vo%2 会失效 (tilt 恒落在偶数序数 → 永远同一方向)
                rot_deg = 6.0 if (((_vo - 1) // len(LOOKS)) % 2 == 0) else -6.0

            # ── v47 克制档 (Boss 选定: "克制为主 + 偶发重音") ──
            # 放在所有字效分支之后 = 覆盖取胜。克制的三件事:
            #   ① 换细体池 (实证过; 中文细体是"高级感"里最立竿见影的一项)
            #   ② 去掉全部"抢亮"处理: 粗描边 / 辉光 / 投影 / 斜面都不给 ——
            #      质感交给字体本身与留白, 而不是靠描边把字"抠"出来
            #   ③ 缓入替弹跳: elastic=False 同时自动去掉踩拍上跳与砸入过冲 (JSX 侧按 elastic 门控)
            # 取色按背景反差, 但用**奶白/近墨**而非纯白/纯黑 (纯白在画面里是最亮的白, 显"喊")
            if not _punch:
                _pool_light = LIGHT_POOLS["drop_calm"][scl]
                font = _pool_light[font_pos.get(("drop_calm", scl), 0) % len(_pool_light)]
                font_pos[("drop_calm", scl)] = font_pos.get(("drop_calm", scl), 0) + 1
                # 字色改用**字期中段亮度**选 (与空心字同一教训): bg_class 取字期内最亮时刻,
                #   对"白字+粗描边"安全, 但克制档默认无描边 → 字色必须匹配"文字真正停在那儿"
                #   的背景。实测 #17 被判亮底配近墨, 而中段区域仅 51 → 近墨压深背景 ΔL 35, 隐形。
                _lmid2 = _region_luma(bg_video, t_in + 0.55 * hold, x, y)
                _lmid2 = 128.0 if _lmid2 is None else _lmid2
                fill_cfg = CALM_INK if _lmid2 >= CALM_LIGHT_BG else CALM_CREAM
                stroke_cfg = None
                # v48 极弱**同色**光晕 —— 但只给"暗底浅字"那一档。
                #   实测得来的限制: 亮底深字若给光晕, 且 glow_col 留 None 就会落到 AE 的
                #   默认泛光色 (白/黑), 在深字周围生成**白晕** → 字发浑、对比反而下降。
                #   (这是我 v48 第一版的实际错误, 靠"干净素材暗像素 0 → 渲出 14349"的
                #    逐帧差分定位到 #10 是深字, 才发现目视判读把深字看成了浅字。)
                #   所以: 暗底浅字 → 同色淡晕(浮起来); 亮底深字 → 不加光晕(保持干净)。
                if _lmid2 < CALM_LIGHT_BG:
                    glow = CALM_GLOW
                    # 单色光晕 (A=B): 若 B 取更暗的同色, Glo2 的 A→B 渐变会把**亮背景压暗**
                    # (实测 #17 亮像素由 119,623 掉到 93,380 = 字周围多出一块发浑暗区)。
                    # 光晕的作用是"让字浮起来", 单色即可, 不需要暗部衰减。
                    glow_col = ([c * 0.85 for c in fill_cfg], [c * 0.85 for c in fill_cfg])
                else:
                    glow = None
                    glow_col = None
                glow2 = None
                shadow_cfg = None
                bevel = None
                chroma = False
                track_cfg = CALM_TRACKING
                rot_deg = 0.0                             # 倾斜属于"张扬", 克制档不用
                look_name = "calm"
                enter = "fade_scale"                      # 缓入替弹跳
                _is_calm = True
                # 可读性兜底 (实测得来): 细体把可读性全押在"字色 vs 背景"上, 但细笔画在
                #   小字号下抗锯齿退化 —— 实测 #12(97px)/#18(119px) 峰值亮度只到 189/171
                #   (拿不到标称奶白 236), ΔL 掉到 37/30, 不够读。
                # 修法: 小字号**或**背景中亮度时补一根 1.5-2.6px 细描边把字骨立住 ——
                #   细描边仍是"排版", 与冲击档 11px 粗边有本质区别。
                _lmid2 = _region_luma(bg_video, t_in + 0.55 * hold, x, y)
                _lmid2 = 128.0 if _lmid2 is None else _lmid2
                _txtL = (0.299 * fill_cfg[0] + 0.587 * fill_cfg[1] + 0.114 * fill_cfg[2]) * 255
                if size < CALM_SMALL_PX or abs(_txtL - _lmid2) < CALM_MIN_DL:
                    _sink = CALM_INK if _txtL > _lmid2 else [0.98, 0.98, 1.0]
                    stroke_cfg = (_sink, round(max(1.5, min(2.6, size * 0.018)), 1))

        ev = {
            "id": i, "t_in": t_in, "t_out": t_out, "hold": hold,
            "mood": mood, "energy": energy, "style_id": style_id,
            "word": word_emit, "size": size, "x": x, "y": y, "closeup": closeup,
            "layout": layout_name, "n_lines": n_lines,
            "font": font,
            "font_stack": pool,
            "script": scl,
            "probe_font": font not in VERIFIED_FONTS,
            "fill": fill_cfg,
            "apply_fill": apply_fill,     # v44 空心字效: false → 只描边不填充
            "rot": rot_deg,               # v44 倾斜字效 (度, Z 轴)
            "look": look_name,
            "stroke": stroke_cfg,
            "enter": enter,
            "glow": glow,
            "glow2": glow2,
            "shadow": shadow_cfg,
            "bevel": bevel,
            "glow_pulse": pulse,
            "glow_col_a": glow_col[0] if glow_col else None,
            "glow_col_b": glow_col[1] if glow_col else None,
            "bg_lum": round(bg_lum, 1),
            "bg_class": bg_class,
            "dbl": dbl,
            "accent": accent,
            "outer_w": outer_w,
            "inner_w": inner_w,
            "is3d": is3d,
            "z": z_dep,
            "beats": beats,
            "env_s": env_s,
            "mv_dx": mv_dx,
            "mv_dy": mv_dy,
            "sp": round(_sp, 4),
            "pulse_mul": round(_pulse_mul, 3),
            "mood_profile": mood_name,
            "entropy": round(_ent, 3),
            # v33 视觉编排 (Boss: "太乱, 应局部/某些时段应用"): 引入留白与对比
            # 数据依据: 参照作品静段 31-89% / 强段 3-21% / 最长连续强段 1-3s;
            #   本片(v32)静段 0% / 强段 100% / 连续强段 29s → 无收放, 故观感乱
            # 规则: ① 配方只给"隔拍"(drop 内 i 为偶数) → 每两次爆点只一次特效, 另一半留白
            #       ② intro/build/outro 一律不给冲击配方 (纯文字与揭示, 保持安静)
            #       ③ 颗粒只在收尾段(电影感/余韵)出现, 见 JSX 关键帧
            # v35 音乐结构驱动: 局部强度 ≥ 阈值 且 距上一个特效 ≥1.2s 才给配方 (副歌密/主歌疏)
            "impact_recipe": (["shake", "rays", "chroma", "feedback", "edgerays", "filmflash"][(i // 2) % 6]
                              if _want_recipe else None),
            "recipe_i": i,
            "recipe_occ": i // 2,
            "local_i": _li,            # v31d: 用"出现次数"做参数变化 —— 只用 i%k 会让同配方的两次出现参数完全相同 (i 与 i+6 同奇偶同模3)
            "recipe_occ": i // 6,
            "from_timeline": bool(_from_tl),
            "font_override": _tl_font_override,
            "chroma": chroma,
            "chroma_dx": chroma_dx,
            "impact_mul": impact_mul,
            "cascade": st.get("cascade", False),
            "elastic": (False if _is_calm else st.get("elastic", False)),
            "calm": _is_calm,                     # v47 克制档 (JSX 据此关掉踩拍缩放脉冲)
            "shockwave": st.get("shockwave", False),
            "typewriter": st.get("typewriter", False),
            "drop_fall": drop_fall,
            "rise_up": rise_up,
            "blurfade": st.get("blurfade", False),
            "tracking": track_cfg,
            "anchor_shot": {"index": seg.get("index"), "t0": t0, "t1": t1},
        }
        events.append(ev)

    # 3) 逐 segment 处置 (覆盖记账: 事件窗 / 显式跳过原因)
    spans = [(e["t_in"], e["t_out"]) for e in events]
    disposition = []
    for si, (t0, t1) in enumerate(seg_bounds):
        hit = next((e["id"] for e, (a, b) in zip(events, spans)
                    if min(t1, b) - max(t0, a) >= 0.5 * (t1 - t0)), None)
        if hit is not None:
            disposition.append({"seg": si, "t0": round(t0, 3), "event": hit})
        else:
            reason = "无过阈值 onset 锚点" if si not in {e["anchor_shot"]["index"] for e in events} \
                else "间距护栏/cap 淘汰"
            disposition.append({"seg": si, "t0": round(t0, 3), "skip": reason})
    return events, disposition


def _shot_index(seg_bounds, t):
    """包含 t 的镜头; 无包含则找 start 距 t ≤2帧 的镜头; 都无 → None"""
    for i, (a, b) in enumerate(seg_bounds):
        if a <= t < b:
            return i
    for i, (a, _b) in enumerate(seg_bounds):
        if 0 <= t - a <= ONSET_TOL:
            return i
    return None


def _skin_p70(scenes):
    mos = sorted(v.get("motion", 99) for v in scenes.values())
    return mos[int(len(mos) * 0.7)] if mos else 99.0


def _region_luma(video, t, cx, cy, w=520, h=320):
    """采样视频 t 时刻候选位区域平均亮度 (gray 1x1); 失败返回 255=按亮处理不选"""
    try:
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(max(t - 0.05, 0.0)), "-i", str(video),
             "-frames:v", "1", "-vf",
             "crop=%d:%d:%d:%d,scale=1:1" % (w, h, max(cx - w // 2, 0), max(cy - h // 2, 0)),
             "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True, timeout=10)
        b = r.stdout
        return sum(b) / len(b) if b else 255.0
    except Exception:
        return 255.0


def _worst_region_luma(video, t_in, hold, x, y, w=520, h=320):
    """读字期内该位置的最大区域亮度 (最坏情况); 无基线/失败回退 128(中间调)"""
    if not video or not Path(video).exists():
        return 128.0
    vals = [_region_luma(video, t_in + f * hold, x, y, w, h)
            for f in (0.12, 0.45, 0.80)]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else 128.0


def _region_luma_range(video, t_in, hold, x, y, w=520, h=320):
    """字期内该位置区域亮度的 (min, max), 采样点与 _worst_region_luma 一致。

    为什么需要 min: 对**白字**取最亮时刻是正确策略 (深描边在任何背景都保读),
    但**空心字**只有单一描边色 —— 若字期跨越明暗两端, 深色描边必在暗时刻隐形
    (实测 #9 BREAK: bg_lum 判定 150 取近黑描边, 而渲染时刻背景仅 76 → 深色叠深色)。
    故空心需知道"字期是否跨明暗", 据此决定能否用空心。
    """
    if not video or not Path(video).exists():
        return 128.0, 128.0
    vals = [_region_luma(video, t_in + f * hold, x, y, w, h)
            for f in (0.12, 0.45, 0.80)]
    vals = [v for v in vals if v is not None]
    return (min(vals), max(vals)) if vals else (128.0, 128.0)


# 空心降级判据: 字期内亮度摆幅超过此值 = 爆闪类镜头, 单色描边保不住 → 降级为反相
SPAN_EXTREME_DIFF = 150.0


def _pick_dark_pos(t_in, bg_video, fallback_i, hold=0.9):
    """v4.1 背景亮度感知选位: 三候选位 × 读字窗口(t+0.35h / t+0.65h)两点采样,
    每位取最大亮度(最坏情况), 挑最小者——BREAK 案例实证: t_in 是切点闪光帧全屏无区分度,
    爆炸类高光会在保持期内瞬态后发, 只看 t_in 或单点中期都会漏;
    无基线视频/全失败 → 回退三分位轮换"""
    if not bg_video or not Path(bg_video).exists():
        return DROP_POS_CYCLE[fallback_i % len(DROP_POS_CYCLE)]
    best, best_l = DROP_POS_CYCLE[fallback_i % 3], 1e9
    for cx, cy in DROP_POS_CYCLE:
        # v9: 加早期采样 0.12h — v8 实证爆炸高光在 0.13h 就爆发, 0.35h 起步的采样全漏
        lum = max(_region_luma(bg_video, t_in + 0.12 * hold, cx, cy),
                  _region_luma(bg_video, t_in + 0.35 * hold, cx, cy),
                  _region_luma(bg_video, t_in + 0.65 * hold, cx, cy))
        if lum < best_l - 1e-6:
            best, best_l = (cx, cy), lum
    return best


# ── JSX 生成 (仅实证 API; ES3) ──────────────────────────────────────────
ENV_DECAY_S = 0.16
ENV_TAIL = 0.45


def build_jsx(events, out_aep: Path, nonce: str = "start"):
    """在验收基线工程上追加文字层 (非破坏: 不动现有层, 只 addText + save 新文件)

    消费 comp: run53_premium_v3 (已在 AE 打开则直接用 — apply_premium_fx.jsx 同款
    遍历; 未打开则 app.open 回退 — ae_auto_render_orchestrator 实证)。
    """
    def _ev_js(e):
        d = {k: e[k] for k in ("t_in", "t_out", "word", "size", "x", "y",
                               "fill", "font", "enter")}
        if e.get("stroke"):
            d["strokeColor"], d["strokeW"] = e["stroke"]
        else:
            d["strokeColor"], d["strokeW"] = None, 0
        if e.get("glow"):
            # glow = (threshold 0-255, radius, intensity); 能量只调制强度(第3位)
            gt_, gr, gi_ = e["glow"]
            d["glow"] = [gt_, gr, round(gi_ * (0.7 + 0.6 * e["energy"]), 3)]
        else:
            d["glow"] = None
        d["glow2"] = list(e["glow2"]) if e.get("glow2") else None
        d["glow_pulse"] = float(e.get("glow_pulse", 1.7))
        d["glow_col_a"] = list(e["glow_col_a"]) if e.get("glow_col_a") else None
        d["glow_col_b"] = list(e["glow_col_b"]) if e.get("glow_col_b") else None
        d["shadow"] = list(e["shadow"]) if e.get("shadow") else None
        d["bevel"] = list(e["bevel"]) if e.get("bevel") else None
        d["dbl"] = bool(e.get("dbl"))
        d["accent"] = list(e["accent"]) if e.get("accent") else None
        d["outer_w"] = float(e.get("outer_w", 0))
        d["inner_w"] = float(e.get("inner_w", 0))
        d["is3d"] = bool(e.get("is3d"))
        d["applyFill"] = bool(e.get("apply_fill", True))   # v44
        d["rot"] = float(e.get("rot", 0.0))                # v44
        d["look"] = e.get("look")                          # v44 (仅报告用)
        d["nLines"] = int(e.get("n_lines", 1))              # v46 排版行数 (供行距设置)
        d["calm"] = bool(e.get("calm"))                     # v47 克制档: 关掉踩拍动作
        d["z"] = float(e.get("z", 0))
        d["beats"] = [[float(a), float(b)] for a, b in (e.get("beats") or [])]
        d["env_s"] = [[float(a), float(b)] for a, b in (e.get("env_s") or [])]
        d["mv_dx"] = float(e.get("mv_dx", 0))
        d["mv_dy"] = float(e.get("mv_dy", 0))
        d["sp"] = float(e.get("sp", 1.0))            # 时长缩放 (1/speed)
        d["pulse_mul"] = float(e.get("pulse_mul", 1.0))
        d["px_shake"] = bool(e.get("px_shake"))
        d["lshadow"] = bool(e.get("lshadow"))
        d["impact_recipe"] = e.get("impact_recipe")
        d["recipe_i"] = int(e.get("recipe_i", 0))
        d["recipe_occ"] = int(e.get("recipe_occ", 1))
        d["local_i"] = float(e.get("local_i", 0.5))       # v35 音乐局部强度 (0-1)
        # v15/v17 冲击力包参数 (探针实证: ADBE Motion Blur=方向模糊 / ADBE Radial Blur / ADBE Turbulent Displace)
        # v17: 冲量按镜头运动强度分级 (impact_mul), 静止镜头收敛 / 高速爆炸镜头拉满
        en = float(e.get("energy", 0.6))
        im = float(e.get("impact_mul", 1.0))
        d["chroma"] = bool(e.get("chroma"))
        d["chroma_dx"] = float(e.get("chroma_dx", 12))
        d["db_dir"] = 0 if e.get("z", 0) == 0 else 90
        # v36 对比强化 (Boss: "感觉没啥变化" → 前两版只调结构, 观感强度未变):
        # 峰均比是关键 (参照 2.5-8.4 vs 我们 1.15) ⇒ ① 安静拍**彻底去掉**入场模糊(原来还有 65%)
        # ② 特效拍幅度与时长放大 (见 JSX ik 与 PEAK 倍率) → 该静的静透, 该炸的炸开
        _calm = 0.0 if not e.get("impact_recipe") else 1.0
        _peak = 1.9 if e.get("impact_recipe") else 1.0      # 特效拍增幅
        d["db_in"] = round((45 + 45 * en) * im * _calm * _peak, 1)
        d["db_out"] = round((30 + 30 * en) * im * _calm * _peak, 1)
        d["rb_in"] = round((12 + 20 * en) * im * _calm * _peak, 1)
        d["tb_amt"] = round((2 + 4.5 * en) * (1.0 if e.get("impact_recipe") else 0.35), 2)
        d["peak"] = round(_peak, 2)
        d["tb_size"] = round(55 + 65 * en, 1)
        d["tb_evo"] = round(80 + 70 * en, 1)
        d["cascade"] = bool(e.get("cascade"))
        d["elastic"] = bool(e.get("elastic"))
        d["shockwave"] = bool(e.get("shockwave"))
        d["typewriter"] = bool(e.get("typewriter"))
        d["drop_fall"] = bool(e.get("drop_fall"))
        d["rise_up"] = bool(e.get("rise_up"))
        d["blurfade"] = bool(e.get("blurfade"))
        d["tracking"] = e.get("tracking")
        # 入/出场关键帧时刻 (hold 过短时按比例缩, 保证 keyframes 单调)
        hold = e["t_out"] - e["t_in"]
        fin = round(min(0.083, hold * 0.3), 3)            # 入场 2 帧
        fout = round(max(0.042, min(0.125, hold * 0.4)), 3)  # 出场 3 帧
        d["fin"], d["fout"] = fin, fout
        return d

    evs_js = json.dumps([_ev_js(e) for e in events], separators=(",", ":"))
    aep_in = (ROOT / "output" / "unified_run53" / AEP_NAME).resolve().as_posix()
    log_p = (ROOT / "tmp" / "ae_text_build.txt").as_posix()
    # v43 注入回执 nonce: 每次构建唯一。AE 侧把它写在日志开头, 调用侧必须回读到同一个
    # nonce 才算注入成功 —— 否则"上一版留下的日志"会被当成成功 (实测踩过: v43 没注入,
    # 却因为 v42 的日志同样是 "start|saved layers=41 texts=25" 而报成功)。
    return f"""
(function() {{
  var rep = "{nonce}";
  var compName = "{COMP_NAME}";
  function findComp() {{
    for (var i = 1; i <= app.project.numItems; i++) {{
      if (app.project.item(i) instanceof CompItem && app.project.item(i).name == compName)
        return app.project.item(i);
    }}
    return null;
  }}
  try {{
    var comp = findComp();
    if (!comp) {{ var fp = new File("{aep_in}"); app.open(fp); comp = findComp(); }}
    if (!comp) {{ rep += "|NOCOMP"; }}
    else {{
      try {{ comp.motionBlur = true; }} catch (mbe) {{ rep += "|COMPMB"; }}   // v15: 合成运动模糊
      // v20 基底光效规范化 (Boss 设定): 素材层 Glo2 = OFF, 粒子层 Glo2 = ON
      // (独立 bridge 调用启用粒子发光曾多次超时/卡住 → 并入注入流程, 状态确定且可核验)
      for (var bi = 1; bi <= comp.numLayers; bi++) {{
        var bly = comp.layer(bi);
        var bfx = null;
        try {{ bfx = bly.property("Effects"); }} catch (be0) {{ continue; }}
        if (!bfx) continue;
        for (var bj = 1; bj <= bfx.numProperties; bj++) {{
          var be = bfx.property(bj);
          var bmn = "";
          try {{ bmn = be.matchName; }} catch (be1) {{ continue; }}
          if (bmn !== "ADBE Glo2") continue;
          var want = (bly.name.indexOf("PART_") === 0);
          try {{ be.enabled = want; }} catch (be2) {{ rep += "|GLOWNORM"; }}
        }}
      }}
      var evs = {evs_js};
      // ── W1 双描边 helper (2026-09-11) ─────────────────────────────────
      function setDoc(L, ev, fillCol, strokeCol, strokeW) {{
        var tp = L.property("Text");
        var d = tp.property("ADBE Text Document").value;
        d.font = ev.font; d.fontSize = ev.size;
        d.fillColor = [fillCol[0], fillCol[1], fillCol[2]];
        // v44 空心字效: applyFill=false → 只渲染描边 (字形保持完整, 不是透明色)
        d.applyFill = (ev.applyFill === undefined) ? true : ev.applyFill;
        try {{
          d.applyStroke = strokeW > 0;
          if (strokeW > 0) {{
            d.strokeColor = [strokeCol[0], strokeCol[1], strokeCol[2]];
            d.strokeWidth = strokeW; d.strokeOverFill = false;
          }}
        }} catch (se) {{ rep += "|STROKE"; }}
        // v46 排版: 多行时收紧行距 (默认 auto leading 约 1.2 倍, 堆叠看起来散)
        // 注: 换行符是 CR (AE TextDocument 口径), 已由 ev.word 自带, 此处只设行距
        try {{
          if (ev.nLines && ev.nLines > 1) {{
            d.autoLeading = false;
            d.leading = Math.round(ev.size * {LAYOUT_LEAD_RATIO});
          }}
        }} catch (le) {{ rep += "|LEAD"; }}
        d.justification = ParagraphJustification.CENTER_JUSTIFY;
        tp.property("ADBE Text Document").setValue(d);
      }}
      function applyTilt(L, ev) {{
        // v44 倾斜字效 (B.rotation 在 3D 层上的行为需实测 → 两种 matchName 都试, 并自报结果)
        if (!ev.rot) return;
        var rz = null;
        try {{ rz = L.property("Transform").property("ADBE Rotate Z"); }} catch (e1) {{}}
        if (!rz) {{ try {{ rz = L.property("Transform").property("ADBE Rotate"); }} catch (e2) {{}} }}
        if (!rz) {{ try {{ rz = L.property("Transform").property("Rotation"); }} catch (e3) {{}} }}
        if (rz) {{ try {{ rz.setValue(ev.rot); }} catch (e4) {{ rep += "|ROTSET"; }} }}
        else {{ rep += "|ROTNONE"; }}
      }}
      function addKick(L, ev) {{
        // 入场砸入 → 保持 → 出场淡出 (opacity 0-100, 实证口径)
        L.opacity.setValueAtTime(ev.t_in, 0);
        L.opacity.setValueAtTime(ev.t_in + ev.fin, 100);
        L.opacity.setValueAtTime(ev.t_out - ev.fout, 100);
        L.opacity.setValueAtTime(ev.t_out, 0);
      }}
      function addTrack(L, ev) {{
        if (!ev.tracking) return;
        var tp2 = L.property("Text");
        var an = tp2.property("ADBE Text Animators").addProperty("ADBE Text Animator");
        an.name = "Punch";
        var tr = an.property("ADBE Text Animator Properties")
                   .addProperty("ADBE Text Tracking Amount");
        tr.setValueAtTime(ev.t_in, ev.tracking);
        tr.setValueAtTime(ev.t_in + 0.2, 0);
      }}
      function addMove(GL, ev) {{
        // 变换类入场动画只施加于底层 (上层经 parent 继承)
        var yOff = 0, zOff = 0;
        if (ev.enter == "fade_scale") {{
          GL.scale.setValueAtTime(ev.t_in, [115, 115]);
          GL.scale.setValueAtTime(ev.t_in + 0.35 * ev.sp, [100, 100]);
        }} else if (ev.enter == "slide_back") {{
          var dx = ev.x < 960 ? -420 : 420;   // 从所在侧外侧滑入
          GL.position.expression =
            "t=time-inPoint;var x0=" + (ev.x + dx) + ",x1=" + ev.x + ";var y=" + ev.y + ";" +
            "if(t<0.08){{[x0,y];}}else if(t<0.58){{p=(t-0.08)/0.5;s=1.70158;p=p-1;" +
            "x=x0+(x1-x0)*(1+((s+1)*p*p*p+s*p*p));[x,y];}}else{{[x1,y];}}";
        }}
        if (ev.elastic) {{
          // 3D 层 scale 为三维 → 表达式须返回 3 值, 否则 AE 报错
          var s0 = ev.is3d ? "[0,0,0]" : "[0,0]";
          var s1 = ev.is3d ? "[s,s,s]" : "[s,s]";
          var fr = (2.8 / ev.sp).toFixed(3);            // speed 越大振荡越快
          var dc = (5.0 / ev.sp).toFixed(3);
          GL.scale.expression =
            "t=time-inPoint;if(t<0.01){{" + s0 + ";}}else{{" +
            "amp=38;freq=" + fr + ";decay=" + dc + ";" +
            "s=amp*Math.sin(freq*t*Math.PI*2)/Math.exp(decay*t)+100;" + s1 + ";}}";
        }}
        if (ev.is3d) {{ zOff = -170; }}          // 3D 纵深: 由远及近的 Z 位移 (无摄像机)
        var _mvDur = 0.26 * ev.sp;
        if (ev.drop_fall || ev.rise_up || zOff !== 0) {{
          var y0 = ev.y + (ev.drop_fall ? -240 : (ev.rise_up ? 240 : 0));
          var dur = (ev.drop_fall || ev.rise_up) ? _mvDur : (0.34 * ev.sp);
          GL.position.setValueAtTime(ev.t_in, [ev.x, y0, ev.z + zOff]);
          GL.position.setValueAtTime(ev.t_in + dur, [ev.x, ev.y, ev.z]);
        }}
      }}
      // W2 三维层: 不建摄像机 —— 实测 (v13) 合成内存在摄像机会使 Advanced 3D 渲染器
      // 对整帧重新合成 (无文字帧亦出现 0.48% 全画面细微差异) = "视频被影响"风险面;
      // 改为 3D 图层自身的 Z 位移动画 (无摄像机时 AE 用默认视图, 2D 基底层零影响)。
      for (var i = 0; i < evs.length; i++) {{
        var ev = evs[i];
        var L = null, U = null, MV = null;
        if (ev.dbl) {{
          // 双描边: 底层 = 彩色外环(实心), 上层 = 白字 + 深色内描边
          // (图层样式描边无法脚本启用 → canSetEnabled=false, 用双文字层等效实现)
          U = comp.layers.addText(ev.word);
          U.name = "TXTU" + i + "_" + ev.word;
          setDoc(U, ev, ev.accent, ev.accent, ev.outer_w);
          if (ev.is3d) {{ U.threeDLayer = true; }}
          U.position.setValue([ev.x, ev.y, ev.z]);
          U.inPoint = ev.t_in; U.outPoint = ev.t_out + 0.05;
          addKick(U, ev); addTrack(U, ev);
          L = comp.layers.addText(ev.word);
          L.name = "TXT" + i + "_" + ev.word;
          setDoc(L, ev, ev.fill, ev.strokeColor, ev.inner_w);
          if (ev.is3d) {{ L.threeDLayer = true; }}
          L.parent = U; L.position.setValue([0, 0, 0]);
          L.inPoint = ev.t_in; L.outPoint = ev.t_out + 0.05;
          addKick(L, ev); addTrack(L, ev);
          MV = U;
        }} else {{
          L = comp.layers.addText(ev.word);
          L.name = "TXT" + i + "_" + ev.word;
          setDoc(L, ev, ev.fill, ev.strokeColor, ev.strokeW);
          applyTilt(L, ev);                                   // v44 倾斜字效 (仅该字效非 0)
          if (ev.is3d) {{ L.threeDLayer = true; }}
          L.position.setValue([ev.x, ev.y, ev.z]);
          L.inPoint = ev.t_in; L.outPoint = ev.t_out + 0.05;
          addKick(L, ev);
          if (ev.enter == "punch_tracking") addTrack(L, ev);
          MV = L;
        }}
        var tp = L.property("Text");
        try {{ addMove(MV, ev); }} catch (mve) {{ rep += "|MOVE" + i; }}
        // ── v25 音乐联动: 节拍脉冲缩放 (非弹性层; 弹性的 drop 层由发光呼吸负责律动) ──
        if (ev.beats && ev.beats.length && !ev.elastic && !ev.calm) {{
          try {{
            for (var b = 0; b < ev.beats.length; b++) {{
              var bt = ev.beats[b][0], bstr = ev.beats[b][1];
              var amp = (4 + 10 * bstr) * ev.pulse_mul;            // 节拍越强脉冲越大; pulse_mul 为情绪档倍率
              L.scale.setValueAtTime(bt, [100 + amp, 100 + amp]);
              L.scale.setValueAtTime(bt + 0.12 * ev.sp, [100, 100]);
            }}
          }} catch (sbe) {{ rep += "|BEATSCALE" + i; }}
        }}
        // ── v26 W3 运动迁移: 镜头运动强度驱动的径向视差漂移 (保持期内缓慢位移) ──
        // 跳过 slide_back (其 position 由表达式持有); drop_fall/rise_up 已有起止键 → 追加末帧漂移
        if ((ev.mv_dx || ev.mv_dy) && ev.enter != "slide_back") {{
          try {{
            var px = ev.x, py = ev.y, pz = ev.z || 0;
            if (ev.is3d) {{
              MV.position.setValueAtTime(ev.t_out - ev.fout, [px, py, pz]);
              MV.position.setValueAtTime(ev.t_out, [px + ev.mv_dx, py + ev.mv_dy, pz]);
            }} else {{
              MV.position.setValueAtTime(ev.t_out - ev.fout, [px, py]);
              MV.position.setValueAtTime(ev.t_out, [px + ev.mv_dx, py + ev.mv_dy]);
            }}
          }} catch (mve2) {{ rep += "|MVDRIFT" + i; }}
        }}
        // ── v41 踩拍上跳 (弹性层专用; 修"drop 段无节拍响应") ──
        // 为什么不用 scale: 弹性层的 scale 由表达式持有 → setValueAtTime 无效;
        // 为什么不用发光闪(v40试过): 亮背景上发光本就看不见 (实测中位变化 +0.0001),
        //   必须用**几何位移**才能在明暗背景上都可见。position 未被表达式占用, 可安全打键。
        // v42 Boss"更狠": 幅度 14+22*bstr → 24+36*bstr (约 45-56px), 回落 0.09→0.07s,
        //   并加"过冲回弹" (弹起→回落→向下过冲 0.16*kick→归位) 与最强拍水平冲击 6px。
        if (ev.elastic && ev.beats && ev.beats.length) {{
          try {{
            var bs4 = ev.beats;
            for (var b4 = 0; b4 < bs4.length; b4++) {{
              var bt4 = bs4[b4][0], bstr4 = bs4[b4][1];
              // 守卫: 避开入场动画 (0.40s) 与出场漂移键 (需留出整套回弹时间)
              if (bt4 <= ev.t_in + 0.40 || bt4 + 0.25 * ev.sp >= ev.t_out - 0.02) continue;
              var kick = (24 + 36 * bstr4) * ev.pulse_mul;
              var jit = (bstr4 >= 0.85) ? 6 : 0;                 // 最强拍加水平冲击
              var zz = ev.z || 0;
              if (ev.is3d) {{
                MV.position.setValueAtTime(bt4, [ev.x + jit, ev.y - kick, zz]);
                MV.position.setValueAtTime(bt4 + 0.07 * ev.sp, [ev.x, ev.y, zz]);
                MV.position.setValueAtTime(bt4 + 0.13 * ev.sp, [ev.x, ev.y + 0.16 * kick, zz]);
                MV.position.setValueAtTime(bt4 + 0.22 * ev.sp, [ev.x, ev.y, zz]);
              }} else {{
                MV.position.setValueAtTime(bt4, [ev.x + jit, ev.y - kick]);
                MV.position.setValueAtTime(bt4 + 0.07 * ev.sp, [ev.x, ev.y]);
                MV.position.setValueAtTime(bt4 + 0.13 * ev.sp, [ev.x, ev.y + 0.16 * kick]);
                MV.position.setValueAtTime(bt4 + 0.22 * ev.sp, [ev.x, ev.y]);
              }}
            }}
          }} catch (bke) {{ rep += "|BEATKICK" + i; }}
        }}
        // ── v30 冲击配方轮换 (每事件一种, 解决"效果单一"; 参数按事件序号再变化) ──
        if (ev.impact_recipe) {{
          var ri = ev.recipe_i || 0;
          var oc = ev.recipe_occ || 1;              // 出现次数: 同配方第 2 次参数必须不同
          var ik = (0.75 + 0.6 * (ev.local_i || 0.5)) * (ev.peak || 1.0);  // v36: 音乐强度 × 峰值倍率
          var bs = ev.beats || [];
          if (ev.impact_recipe == "shake") {{
            try {{
              var shk = L.property("Effects").addProperty("S_Shake");
              try {{ shk.property("S_Shake-0001").setValue(1 + (oc % 3)); }} catch (s0) {{}}   // Style 1-3
              shk.property("S_Shake-0051").setValue(5 + (oc % 3) * 3);                        // Freq 5/8/11
              try {{ shk.property("S_Shake-0054").setValue(1); }} catch (s1) {{}}
              try {{ shk.property("S_Shake-0056").setValue(7); }} catch (s2) {{}}
              var amp = shk.property("S_Shake-0050");
              amp.setValueAtTime(ev.t_in, 0);
              for (var b2 = 0; b2 < bs.length; b2++) {{
                var bt2 = bs[b2][0], bstr2 = bs[b2][1];
                amp.setValueAtTime(bt2, (0.35 + 0.9 * bstr2) * ev.pulse_mul * ik);
                amp.setValueAtTime(bt2 + 0.14 * ev.sp, 0);
              }}
              amp.setValueAtTime(ev.t_out, 0);
            }} catch (e_sh) {{ rep += "|SHAKE" + i; }}
          }} else if (ev.impact_recipe == "rays") {{
            try {{
              var rys = L.property("Effects").addProperty("S_Rays");
              rys.property("S_Rays-0050").setValue([ev.x, ev.y]);                             // 中心=文字位
              rys.property("S_Rays-0051").setValue(0.18 + 0.10 * (oc % 2));                   // 长度轮换
              try {{ rys.property("S_Rays-0100").setValue(oc % 2); }} catch (r0) {{}}          // 方向轮换
              var br = rys.property("S_Rays-0052");
              br.setValueAtTime(ev.t_in, 0.4);
              br.setValueAtTime(ev.t_in + 0.12 * ev.sp, (2.8 + 0.7 * (oc % 2)) * ev.pulse_mul * ik);
              br.setValueAtTime(ev.t_in + 0.42 * ev.sp, 0);
            }} catch (e_ry) {{ rep += "|RAYS" + i; }}
          }} else if (ev.impact_recipe == "chroma") {{
            try {{
              var wc = L.property("Effects").addProperty("S_WarpChroma");
              wc.property("S_WarpChroma-0051").setValue([ev.x, ev.y]);
              try {{ wc.property("S_WarpChroma-0054").setValue(((oc % 2) ? 1 : -1) * 0.03); }} catch (c0) {{}}
              try {{ wc.property("S_WarpChroma-0058").setValue(((oc % 2) ? -1 : 1) * 0.03); }} catch (c1) {{}}
              var wa = wc.property("S_WarpChroma-0100");
              wa.setValueAtTime(ev.t_in, 0.02);
              wa.setValueAtTime(ev.t_in + 0.14 * ev.sp, (0.42 + 0.16 * (oc % 2)) * ev.pulse_mul * ik);
              wa.setValueAtTime(ev.t_in + 0.5 * ev.sp, 0.02);
            }} catch (e_wc) {{ rep += "|WARPCHROMA" + i; }}
          }} else if (ev.impact_recipe == "feedback") {{
            try {{
              var fb = L.property("Effects").addProperty("S_Feedback");
              fb.property("S_Feedback-0100").setValue(10 + (oc % 3) * 4);                      // Max Steps 10/14/18
              var fbPrev = fb.property("S_Feedback-0050");                                    // Prev Brightness
              fbPrev.setValueAtTime(ev.t_in, 0.15);                                           // v31c: 文字先可见
              fbPrev.setValueAtTime(ev.t_in + 0.16 * ev.sp, (0.45 + 0.12 * (oc % 2)) * ik);          // 回授堆叠(按出现次数+强度)
              fbPrev.setValueAtTime(ev.t_in + 0.60 * ev.sp, 0.08);                            // 衰减
              var fbBlur = fb.property("S_Feedback-0056");
              fbBlur.setValueAtTime(ev.t_in, 2.5);
              fbBlur.setValueAtTime(ev.t_in + 0.3 * ev.sp, 0);
            }} catch (e_fb) {{ rep += "|FEEDBACK" + i; }}
          }} else if (ev.impact_recipe == "edgerays") {{
            try {{
              var er = L.property("Effects").addProperty("S_EdgeRays");
              er.property("S_EdgeRays-0050").setValue([ev.x, ev.y]);
              er.property("S_EdgeRays-0051").setValue(0.22 + 0.12 * (oc % 2));
              try {{ er.property("S_EdgeRays-0100").setValue(oc % 2); }} catch (er0) {{}}
              var erb = er.property("S_EdgeRays-0052");
              erb.setValueAtTime(ev.t_in, 0.3);
              erb.setValueAtTime(ev.t_in + 0.10 * ev.sp, (2.3 + 0.9 * (oc % 2)) * ev.pulse_mul * ik);
              erb.setValueAtTime(ev.t_in + 0.45 * ev.sp, 0);
            }} catch (e_er) {{ rep += "|EDGERAYS" + i; }}
          }} else if (ev.impact_recipe == "filmflash") {{
            try {{
              var fe = L.property("Effects").addProperty("S_FilmEffect");
              var fpe = fe.property("S_FilmEffect-0057");                                     // Print Exposure
              fpe.setValueAtTime(ev.t_in, 0);
              fpe.setValueAtTime(ev.t_in + 0.08 * ev.sp, (1.1 + 0.7 * (oc % 2)) * ik);
              fpe.setValueAtTime(ev.t_in + 0.5 * ev.sp, 0);
              var fgb = fe.property("S_FilmEffect-0063");                                     // Glow Brightness
              fgb.setValueAtTime(ev.t_in, 0);
              fgb.setValueAtTime(ev.t_in + 0.08 * ev.sp, (1.7 + 1.0 * (oc % 2)) * ev.pulse_mul * ik);
              fgb.setValueAtTime(ev.t_in + 0.55 * ev.sp, 0);
              try {{ fe.property("S_FilmEffect-0056").setValueAtTime(ev.t_in, -0.3 + 0.7 * (oc % 2)); }} catch (fe0) {{}}
            }} catch (e_fe) {{ rep += "|FILMFLASH" + i; }}
          }}
        }}
        if (ev.lshadow) {{                                                // 文字长阴影 (显式开关; 默认关)
          try {{
            var ls = L.property("Effects").addProperty("LongShadow");
            ls.property("ADBE LongShadow-0005").setValue(225);
            ls.property("ADBE LongShadow-0006").setValue(22);
          }} catch (lse) {{ rep += "|LSHADOW" + i; }}
        }}
        // ── W2 揭示技法: 图层遮罩 (探针实证: mask atom + Shape 赋值/关键帧可用, 不碰文字动画器) ──
        // 为何不用 Linear Wipe: 它作用于整帧(1920x1080)而非文字范围 → 擦除线扫过时文字整块跳出
        // (v21/v22 实证); 遮罩按 sourceRectAtTime 的文字边界裁切 = 真正的"揭示"
        if (ev.enter == "wipe_up" || ev.enter == "wipe_right") {{
          try {{
            var mk = L.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
            var r = L.sourceRectAtTime(ev.t_in, false);
            var x0 = r.left - 8, x1 = r.left + r.width + 8;
            var y0 = r.top - 8, y1 = r.top + r.height + 8;
            var sFull = new Shape();
            sFull.vertices = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]; sFull.closed = true;
            var sZero = new Shape();
            if (ev.enter == "wipe_up") {{
              sZero.vertices = [[x0, y1], [x1, y1], [x1, y1], [x0, y1]];
            }} else {{
              sZero.vertices = [[x0, y0], [x0, y0], [x0, y1], [x0, y1]];
            }}
            sZero.closed = true;
            var shp = mk.property("ADBE Mask Shape");
            shp.setValueAtTime(ev.t_in, sZero);
            shp.setValueAtTime(ev.t_in + 0.34 * ev.sp, sFull);
            shp.setValueAtTime(ev.t_out - ev.fout, sFull);
            shp.setValueAtTime(ev.t_out, sZero);
            try {{ mk.property("ADBE Mask Feather").setValue([6, 6]); }} catch (mfe) {{}}
          }} catch (mke) {{ rep += "|MASKREVEAL" + i; }}
        }}
        // ── v3 手册实证技法（全部 try/catch, 手册: AE-文字特效JSX动画可靠参数手册 附D/E/F）──
        if (ev.cascade) {{                                    // 逐字级联翻入: RotY(-90)+Opacity(0)+RS idx3 扫过
          try {{
            var ca = tp.property("ADBE Text Animators").addProperty("ADBE Text Animator");
            ca.name = "Cascade";
            var crs = ca.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
            crs.property(1).setValue(0);                      // Percent Start (必须用索引, 手册约束)
            crs.property(2).setValue(100);                    // Percent End
            crs.property(3).setValueAtTime(ev.t_in, -100);    // Offset: -100=全隐藏
            crs.property(3).setValueAtTime(ev.t_in + 0.30, 0);// 0=全显示 (0.30s 级联扫过)
            var cpr = ca.property("ADBE Text Animator Properties");
            cpr.addProperty("ADBE Text Opacity").setValue(0);
            cpr.addProperty("ADBE Text Rotation Y").setValue(-90);
          }} catch (ce) {{ rep += "|CASCADE" + i; }}
        }}
        if (ev.shockwave) {{                                    // 冲击波爆发 (手册 附F: Ramp radial + Add + 衰减)
          try {{
            var wv = comp.layers.addSolid([1, 1, 1], "SHOCK" + i, 240, 240, 1, 5);
            wv.position.setValue([ev.x, ev.y]);
            wv.blendMode = 5;                                  // Add
            wv.inPoint = ev.t_in - 0.02; wv.outPoint = ev.t_in + 0.7;
            var rp = wv.property("Effects").addProperty("ADBE Ramp");
            rp.property(1).setValue([120, 120]);
            rp.property(2).setValue([1, 1, 1, 1]);
            rp.property(3).setValue([120, 120]);
            rp.property(4).setValue([0, 0, 0, 0]);
            rp.property(5).setValue(2);                         // radial
            wv.scale.expression =
              "t=time-inPoint;p=Math.min(t/0.45,1);s=10+p*88;[s,s];";
            wv.opacity.expression =
              "t=time-inPoint;if(t<0.04){{85*(t/0.04);}}else{{Math.max(85*Math.exp(-7*(t-0.04)),0);}}";
          }} catch (we) {{ rep += "|SHOCKWAVE" + i; }}
        }}
        if (ev.typewriter) {{                                   // 打字机逐字揭示 (手册 §十六)
          try {{
            var ta = tp.property("ADBE Text Animators").addProperty("ADBE Text Animator");
            ta.name = "TypeIn";
            var trs = ta.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
            trs.property(1).setValue(0);
            trs.property(2).setValue(100);
            trs.property(3).setValueAtTime(ev.t_in, -100);
            trs.property(3).setValueAtTime(ev.t_in + 0.45, 0);
            ta.property("ADBE Text Animator Properties").addProperty("ADBE Text Opacity").setValue(0);
          }} catch (te) {{ rep += "|TYPEWRITER" + i; }}
        }}
        if (ev.blurfade) {{                                     // 模糊淡入 (手册 §十七: Gaussian Blur 2 prop1)
          try {{
            var bl = L.property("Effects").addProperty("ADBE Gaussian Blur 2");
            bl.property(1).setValueAtTime(ev.t_in, 60);
            bl.property(1).setValueAtTime(ev.t_in + 0.5, 0);
          }} catch (be) {{ rep += "|BLURFADE" + i; }}
        }}
        if (ev.glow) {{
          // 实证序号 (2026-09-10 探针): 0002=发光阈值(0-255), 0003=半径, 0004=强度
          // v10 探针补充: 0012=颜色A / 0013=颜色B (默认 白/黑 → 光永远是白的; 亮底上不可见)
          var gf = L.property("Effects").addProperty("ADBE Glo2");
          gf.property("ADBE Glo2-0002").setValue(ev.glow[0]);          // threshold
          gf.property("ADBE Glo2-0003").setValue(ev.glow[1]);          // radius
          if (ev.glow_col_a) {{
            try {{
              gf.property("ADBE Glo2-0007").setValue(2);   // 发光颜色模式= A&B (默认1=原色, 忽略A/B!)
              gf.property("ADBE Glo2-0012").setValue(
                [ev.glow_col_a[0], ev.glow_col_a[1], ev.glow_col_a[2], 1]);
              gf.property("ADBE Glo2-0013").setValue(
                [ev.glow_col_b[0], ev.glow_col_b[1], ev.glow_col_b[2], 1]);
            }} catch (gce) {{ rep += "|GLOWCOL" + i; }}
          }}
          gf.property("ADBE Glo2-0004").setValueAtTime(                // 强度入场脉冲 (ENV 语法, v6.1 按文字系)
            ev.t_in, ev.glow[2] * ev.glow_pulse * ev.pulse_mul);
          gf.property("ADBE Glo2-0004").setValueAtTime(
            ev.t_in + {ENV_DECAY_S} * ev.sp, ev.glow[2]);
          // v25 音乐联动: 保持期内发光强度按音乐包络逐帧呼吸 (确定性烘焙, 非随机)
          var es = ev.env_s || [];
          for (var q = 1; q < es.length; q++) {{
            gf.property("ADBE Glo2-0004").setValueAtTime(
              es[q][0], Math.max(0.05, ev.glow[2] * (0.78 + 0.60 * es[q][1])));
          }}
          // ── v40 踩拍发光闪 (修 drop 段"整段无节拍响应") ──
          // 根因: drop_impact 样式的 scale 由 elastic 表达式驱动 → setValueAtTime 对表达式属性无效,
          //   且脉冲代码有 !ev.elastic 守卫 → 高潮段 13 个事件**一个节拍脉冲都没有** (实测 AE 属性真值:
          //   TXT8-TXT22 的 scale 无关键帧)。而发光强度是逐帧烘焙的关键帧, 不受表达式限制 → 用它做踩拍。
          // 加守卫: ① 跳过入场附近 (入场自带脉冲) ② 有冲击配方的事件不加 (配方已在拍点上调制自身幅度)。
          if (!ev.impact_recipe) {{
            try {{
              var bs2 = ev.beats || [];
              for (var b3 = 0; b3 < bs2.length; b3++) {{
                var bt3 = bs2[b3][0], bstr3 = bs2[b3][1];
                if (bt3 <= ev.t_in + 0.22 || bt3 >= ev.t_out - 0.06) continue;
                var envb = 0.78 + 0.60 * bstr3;                      // 该拍的包络基线
                var boost = 1.22 + 0.50 * bstr3;                     // 1.22-1.72 倍发光闪
                gf.property("ADBE Glo2-0004").setValueAtTime(
                  bt3, Math.max(0.05, ev.glow[2] * envb * boost));
                gf.property("ADBE Glo2-0004").setValueAtTime(
                  bt3 + 0.10 * ev.sp, Math.max(0.05, ev.glow[2] * envb));
              }}
            }} catch (bbe) {{ rep += "|BEATGLOW" + i; }}
          }}
        }}
        if (ev.glow2) {{                                                // 配方④: 高阈值大半径外层 bloom
          try {{
            var g2 = L.property("Effects").addProperty("ADBE Glo2");
            g2.name = "Bloom";
            g2.property("ADBE Glo2-0002").setValue(ev.glow2[0]);
            g2.property("ADBE Glo2-0003").setValue(ev.glow2[1]);
            g2.property("ADBE Glo2-0004").setValue(ev.glow2[2]);
          }} catch (g2e) {{ rep += "|GLOW2" + i; }}
        }}
        if (ev.shadow) {{                                               // 配方①: 投影层次
          try {{
            var sh = L.property("Effects").addProperty("ADBE Drop Shadow");
            sh.property("ADBE Drop Shadow-0001").setValue([0, 0, 0, 1]);   // 颜色
            sh.property("ADBE Drop Shadow-0002").setValue(ev.shadow[0] * 255); // 不透明度(0-255)
            sh.property("ADBE Drop Shadow-0003").setValue(ev.shadow[1]);   // 方向
            sh.property("ADBE Drop Shadow-0004").setValue(ev.shadow[2]);   // 距离
            sh.property("ADBE Drop Shadow-0005").setValue(ev.shadow[3]);   // 柔和度
          }} catch (she) {{ rep += "|SHADOW" + i; }}
        }}
        if (ev.bevel) {{                                                // 配方⑦lite: 边缘立体
          try {{
            var bv = L.property("Effects").addProperty("ADBE Bevel Alpha");
            bv.property("ADBE Bevel Alpha-0001").setValue(ev.bevel[0]);   // 边缘厚度
            bv.property("ADBE Bevel Alpha-0002").setValue(ev.bevel[1]);   // 灯光角度
            bv.property("ADBE Bevel Alpha-0004").setValue(ev.bevel[2]);   // 灯光强度
          }} catch (bve) {{ rep += "|BEVEL" + i; }}
        }}
        // ── v15 冲击力包 (探针实证内建效果参数) ──────────────────────────
        try {{                                        // 方向模糊: 入场拖影 + 出场拉出
          var dbf = L.property("Effects").addProperty("ADBE Motion Blur");
          dbf.property("ADBE Motion Blur-0001").setValue(ev.db_dir);
          dbf.property("ADBE Motion Blur-0002").setValueAtTime(ev.t_in, ev.db_in);
          dbf.property("ADBE Motion Blur-0002").setValueAtTime(ev.t_in + 0.14, 0);
          dbf.property("ADBE Motion Blur-0002").setValueAtTime(ev.t_out - ev.fout, 0);
          dbf.property("ADBE Motion Blur-0002").setValueAtTime(ev.t_out, ev.db_out);
        }} catch (dbe) {{ rep += "|DIRBLUR" + i; }}
        try {{                                        // 径向模糊: 入场爆发 (向心/离心)
          var rbf = L.property("Effects").addProperty("ADBE Radial Blur");
          rbf.property("ADBE Radial Blur-0002").setValue([ev.x, ev.y]);
          rbf.property("ADBE Radial Blur-0001").setValueAtTime(ev.t_in, ev.rb_in);
          rbf.property("ADBE Radial Blur-0001").setValueAtTime(ev.t_in + 0.16, 0);
        }} catch (rbe) {{ rep += "|RADBLUR" + i; }}
        try {{                                        // 湍流置换: 保持期微流动 (活起来)
          var tbf = L.property("Effects").addProperty("ADBE Turbulent Displace");
          tbf.property("ADBE Turbulent Displace-0002").setValue(ev.tb_amt);
          tbf.property("ADBE Turbulent Displace-0003").setValue(ev.tb_size);
          tbf.property("ADBE Turbulent Displace-0006").expression = "time*" + ev.tb_evo;
        }} catch (tbe) {{ rep += "|TURB" + i; }}
        try {{                                        // 图层运动模糊 (合成开关已开)
          L.motionBlur = true;
          if (U) U.motionBlur = true;
        }} catch (mbe2) {{ rep += "|LAYERMB" + i; }}
        if (ev.chroma) {{                             // v17 通道分离: 红/青幽灵层错位入场 (Add 混合)
          try {{
            var mkGhost = function (col, dx, nm) {{
              var G = comp.layers.addText(ev.word);
              G.name = nm + i + "_" + ev.word;
              setDoc(G, ev, col, col, 0);
              G.blendMode = 5;                        // Add
              G.parent = L;
              G.inPoint = ev.t_in; G.outPoint = ev.t_out + 0.05;
              addKick(G, ev);
              G.position.setValueAtTime(ev.t_in, [dx, 0, 0]);
              G.position.setValueAtTime(ev.t_in + 0.20, [0, 0, 0]);
            }};
            mkGhost([1.0, 0.06, 0.06], -ev.chroma_dx, "TXTR");
            mkGhost([0.06, 0.85, 1.0], ev.chroma_dx, "TXTC");
          }} catch (che) {{ rep += "|CHROMA" + i; }}
        }}
        // ── W2 揭示技法已前移至效果栈首 (见上方, 必须在发光/模糊之前才能裁字形) ──
      }}
      // ── v32/v33 颗粒实验结论: 已停用 (默认关闭) ──
      // 实证: ① 细颗粒(Freq 100) 无损可见但被 H.264@15Mbps 完全压掉; ② 粗颗粒(Freq 12) 形成大块
      // 明暗斑并把整帧提亮 (4.5s 均值 57→127, 且采样点趋同 ≈ 恒定偏移) → 正是"太乱"的主因;
      // ③ 关键帧化的 Color Amplitude 在该版本上未按预期生效 → 不做无依据的补救。
      // 需要重启颗粒实验时设 TEXT_OVERLAY_GRAIN=1 (届时必须做**同帧** A/B 区域级校验)。
      if ({'true' if os.environ.get("TEXT_OVERLAY_GRAIN", "0") == "1" else 'false'}) {{
        try {{
          var footage = null;
          for (var fi = comp.numLayers; fi >= 1; fi--) {{
            var fn = comp.layer(fi).name;
            if (fn.indexOf("TXT") === 0) continue;
            if (fn.indexOf(".mp4") >= 0 || fn.indexOf("final") >= 0) {{ footage = comp.layer(fi); break; }}
          }}
          if (footage) {{
            var gr = footage.property("Effects").addProperty("S_Grain");
            gr.property("S_Grain-0052").setValue(30);
            gr.property("S_Grain-0051").setValue(0.12);
            rep += "|GRAIN_ON";
          }}
        }} catch (ge) {{ rep += "|GRAIN"; }}
      }}
      app.project.save(new File("{out_aep.as_posix()}"));
      rep += "|saved layers=" + comp.numLayers + " texts=" + evs.length;
    }}
  }} catch (e) {{ rep += "|FATAL:" + e.toString(); }}
  var f = new File("{log_p}");
  f.encoding = "UTF-8"; f.open("w"); f.write(rep); f.close();
}})()
"""


# ── 门禁自检 (dry-run 报告) ─────────────────────────────────────────────
def validate(events, disposition, segs, onsets, total_dur):
    smax = max(s for _, s in onsets) if onsets else 1.0
    checks = {}
    onset_ts = [t for t, _ in onsets]
    dev = [min(abs(e["t_in"] - t) for t in onset_ts) for e in events]
    checks["onset_align_max_frames"] = round(max(dev) * FPS, 2) if dev else None
    checks["onset_align_pass"] = all(d <= ONSET_TOL + 1e-6 for d in dev)
    checks["min_hold"] = round(min(e["hold"] for e in events), 3) if events else None
    checks["min_hold_pass"] = all(e["hold"] >= 0.15 for e in events)
    # 时间线覆盖 (事件窗并集 / 总时长)
    cov = 0.0
    for e in events:
        a, b = e["t_in"], e["t_out"]
        cov += max(0.0, b - a)
    checks["timeline_coverage"] = round(cov / total_dur, 3)
    checks["timeline_coverage_pass"] = checks["timeline_coverage"] >= 0.80
    # segment 处置覆盖 (每个镜头要么挂事件要么显式跳过)
    checks["segments_total"] = len(segs)
    checks["segments_in_event"] = sum(1 for d in disposition if "event" in d)
    checks["segment_disposition_coverage"] = round(len(disposition) / len(segs), 3)
    # 分区均有事件
    zones_hit = sorted({zone_of(e["t_in"]) for e in events})
    checks["zones_covered"] = zones_hit
    checks["zones_pass"] = set(zones_hit) >= {"intro", "build", "drop"}
    # 字体实证记账
    checks["probe_fonts"] = sorted({e["font"] for e in events if e["probe_font"]})
    checks["verified_fonts_only"] = not checks["probe_fonts"]

    # ── W4 硬门禁 (设计规则, 来自 bang-motion 类实践: menus-not-defaults / 不重复 / 两级文字 / 字号下限) ──
    def _variant(e):
        if e["style_id"] == "drop_impact":
            return "drop_fall" if e.get("drop_fall") else ("rise_up" if e.get("rise_up") else "punch")
        return e["enter"]

    rep_font = [f"{a['word']}→{b['word']}" for a, b in zip(events, events[1:]) if a["font"] == b["font"]]
    rep_var = [f"{a['word']}→{b['word']}" for a, b in zip(events, events[1:])
               if _variant(a) == _variant(b)]
    # 时间表显式指定字体导致的相邻重复 → 用户意图优先, 门禁不计失败, 仅提示
    rep_font_override = [f"{a['word']}→{b['word']}" for a, b in zip(events, events[1:])
                         if a["font"] == b["font"] and (a.get("font_override") or b.get("font_override"))]
    rep_font = [x for x in rep_font if x not in rep_font_override]
    checks["no_repeat_consecutive_fonts"] = not rep_font
    checks["font_repeat_from_override"] = rep_font_override
    _ent_used = events[0].get("entropy", 0.65) if events else 0.65
    # 低熵档 (entropy<0.35) 本就是"固定变款"的显式选择 → 该门禁标 N/A 而非失败 (诚实口径)
    checks["entropy"] = _ent_used
    checks["no_repeat_consecutive_variants"] = (not rep_var) or (_ent_used < 0.35)
    checks["variant_gate_note"] = "N/A(低熵档显式固定变款)" if _ent_used < 0.35 else ""
    checks["repeat_font_pairs"] = rep_font[:5]
    checks["repeat_variant_pairs"] = rep_var[:5]
    # 并发文字层数 (两级文字约束: 本项目设计为单层事件, 上限 2)
    ev_sorted = sorted(events, key=lambda e: e["t_in"])
    max_conc, cur = 0, []
    for e in ev_sorted:
        cur = [x for x in cur if x["t_out"] > e["t_in"]]
        cur.append(e)
        max_conc = max(max_conc, len(cur))
    checks["max_concurrent_text"] = max_conc
    checks["two_levels_pass"] = max_conc <= 2
    # 字号下限 (1920 宽舞台: 60px 下限, 对应 1080 宽 30px 的可读性经验)
    checks["min_font_size"] = min(e["size"] for e in events) if events else None
    checks["font_size_floor_pass"] = bool(events) and checks["min_font_size"] >= 60
    checks["mood_entropy_speed"] = {"mood": events[0].get("mood_profile") if events else None,
                                    "sp": events[0].get("sp") if events else None,
                                    "pulse_mul": events[0].get("pulse_mul") if events else None}
    return checks


# ── CLI ─────────────────────────────────────────────────────────────────
def _parse_args():
    ap = argparse.ArgumentParser(
        prog="build_text_overlay.py",
        description="文字-剪辑集成调度器 P0 — 消费 segments+onsets+envelope 出事件表与注入 JSX",
        epilog="示例: python scripts/build_text_overlay.py unified_run53 run53 --dry-run")
    ap.add_argument("run_dir", help="run 目录, 白名单 unified_run\\d+ (可带 output/ 前缀)")
    ap.add_argument("tag", help="tag, 白名单 run\\d+")
    ap.add_argument("--dry-run", action="store_true",
                    help="只生成事件表 + JSX 落盘, 不调用 AE Bridge (离线验证)")
    ap.add_argument("--words-json", default=None,
                    help="词库覆盖 {zone: [word, ...]}")
    ap.add_argument("--hold-mode", choices=["phrase", "shot"], default="phrase",
                    help="phrase=保持到下一切点/上限(可读性优先, 默认); shot=严格镜头边界")
    ap.add_argument("--max-events", type=int, default=None,
                    help="事件总数上限 (默认按分区 cap: 2+6+10+2=20)")
    ap.add_argument("--mood", choices=list(MOOD_PROFILES.keys()), default="auto",
                    help="情绪档案: auto=既有行为 / impact=冲击优先 / elegant=克制优雅 / kinetic=动感")
    ap.add_argument("--entropy", type=float, default=0.65,
                    help="变款随机度 0~1 (0=固定首款最一致, 1=每事件换款最多样); 确定性(固定 seed)")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="节奏速度倍率 (入场/脉冲时长 ∝ 1/speed; 弹性动画频率 ∝ speed)")
    ap.add_argument("--seed", type=int, default=20260912, help="变款 PRNG 种子 (保证可复现)")
    ap.add_argument("--edl", dest="edl", default=None,
                    help="edl.json 路径; 提供时先过 lint 契约闸门, 且其 text_events 轨(若有)直接作事件表(跳过现场 plan_events)")
    return ap.parse_args()


def main():
    args = _parse_args()
    raw = str(args.run_dir).replace("\\", "/").removeprefix("output/")
    if not re.fullmatch(RUN_DIR_PATTERN, raw):
        print(f"[ERR] 非法 run 目录名(白名单 unified_run<N> | unified_r1_fixed_v<N>): {raw}")
        sys.exit(2)
    if not re.fullmatch(TAG_PATTERN, str(args.tag)):
        print(f"[ERR] 非法 tag(白名单 run\\d+): {args.tag}")
        sys.exit(2)
    run_dir = ROOT / "output" / raw
    if not (run_dir / "production_report.json").exists():
        print(f"[ERR] 缺前置产物 {run_dir / 'production_report.json'}")
        sys.exit(2)

    # §4/Step1.5: --edl 数据契约闸门(读+lint, fail-fast)。仅显式传入才启用 → 无 --edl 时零行为变化(BACKWARD)
    _edl = None
    if args.edl:
        from scripts.edl import load_edl
        _edl_p = Path(args.edl)
        if not _edl_p.exists():
            print(f"[ERR] --edl 不存在: {_edl_p}")
            sys.exit(2)
        try:
            _edl = load_edl(_edl_p)          # lint 失败抛 ValueError
        except ValueError as _e:
            print(f"[ERR] EDL 契约校验失败: {_e}")
            sys.exit(2)
    _edl_events = (_edl or {}).get("text_events") or None

    words = load_words(None)
    _wp = ROOT / WORDS_FILE
    if not _wp.exists():
        _wp.parent.mkdir(parents=True, exist_ok=True)
        _wp.write_text(json.dumps(DEFAULT_WORDS, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[P0] 已生成可编辑词库: {_wp} (改文字后重跑本脚本即生效)")
    if args.words_json:
        words = load_words(json.loads(Path(args.words_json).read_text(encoding="utf-8")))
        print(f"[P0] 词库覆盖: {args.words_json}")

    segs = load_segments(run_dir)
    onsets = load_onsets()
    env_at = load_envelope_at()
    scenes = load_scenes()
    total_dur = float(segs[-1]["end_time"]) if segs else 0.0
    timeline = load_timeline()
    if timeline:
        print(f"[P0] 时间表命中: 载入 {len(timeline)} 条 (容差 ±{TIMELINE_TOL}s)")

    if _edl_events:
        # §4: EDL text_events 轨(上游已规划的完整事件表)直接作事件源 → 跳过现场 plan_events
        events, disposition = _edl_events, []   # EDL 恢复路径不重算 segment 处置(validate 容忍空 disposition)
        print(f"[P0] text_events 来自 EDL 契约({len(events)} 条), 跳过现场生成")
    else:
        events, disposition = plan_events(segs, onsets, env_at, scenes, words,
                                          hold_mode=args.hold_mode,
                                          max_events=args.max_events,
                                          total_dur=total_dur,
                                          bg_video=run_dir / "run53_premium_final.mp4",
                                          profile=MOOD_PROFILES.get(args.mood),
                                          entropy=args.entropy,
                                          speed=args.speed,
                                          seed=args.seed,
                                          mood_name=args.mood,
                                          timeline=timeline)
    checks = validate(events, disposition, segs, onsets, total_dur)
    if _edl_events:
        checks["event_source"] = "edl_text_events"    # 诚实记账: 事件来自 EDL 契约, 非现场生成
        checks["disposition_recomputed"] = False
    # 时间表对账 (显式记账: 命中/未命中, 未命中告警——否则用户以为指定了其实没生效)
    if timeline:
        matched_t = [round(e["t_in"], 2) for e in events if e.get("from_timeline")]
        unmatched = [it for it in timeline if not any(abs(it["t"] - mt) <= TIMELINE_TOL for mt in matched_t)]
        checks["timeline_specified"] = len(timeline)
        checks["timeline_matched"] = len(matched_t)
        checks["timeline_unmatched"] = [{"t": it["t"], "word": it["word"]} for it in unmatched]
        if unmatched:
            _txt = ", ".join(f"{it['t']}s:{it['word']}" for it in unmatched)
            print(f"[P0] ⚠ 时间表未命中 {len(unmatched)} 条 (该时刻无事件锚点): {_txt}")

    out_dir = run_dir / "text_overlay"
    out_dir.mkdir(parents=True, exist_ok=True)
    ver = os.environ.get("TEXT_OVERLAY_VER", "v2")            # v2=P1配方①④⑦样式 (v1已被git历史覆盖备份)
    out_aep = run_dir / f"run53_text_{ver}.aep"
    nonce = f"{ver}-{int(time.time())}"
    jsx = build_jsx(events, out_aep, nonce)
    (out_dir / "events.json").write_text(
        json.dumps({"events": events, "disposition": disposition,
                    "checks": checks, "hold_mode": args.hold_mode,
                    "generated_by": "build_text_overlay.py P0"},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    jsx_p = out_dir / f"text_overlay_{ver}.jsx"
    # ── 语法自检 (v46 立) ──
    # 起因: JSX 是 Python f-string 生成的, 注释里写 '\r' 会被 Python 解释成**真实回车**,
    #   插进 JS 的 // 注释中间 → 注释被截断 → 后半截当代码 → ExtendScript 报
    #   "SyntaxError: 未终止的字符串常数" (行号还是按监听器算的, 极难定位)。
    # 不变量: 生成脚本里除行尾 CRLF 外不得出现裸 CR (文本换行在 JSON 字符串内是转义形式)。
    for _ln, _line in enumerate(jsx.split("\n"), 1):
        if "\r" in _line.rstrip("\r") or (_line.endswith("\r") is False and "\r" in _line):
            _bad = _line.replace("\r", "<CR>")
            print(f"[ERR] 生成脚本第 {_ln} 行含裸回车 (f-string 转义泄漏): {_bad[:160]}")
            sys.exit(3)
    jsx_p.write_text(jsx, encoding="utf-8")

    # ── 报告 ──
    print(f"[P0] 事件 {len(events)} 个 / 镜头 {len(segs)} / onsets {len(onsets)} "
          f"(hold_mode={args.hold_mode})")
    for e in events:
        probe = " [字体待探针]" if e["probe_font"] else ""
        cu = " closeup→安全带" if e["closeup"] else ""
        print(f"  #{e['id']:02d} {e['t_in']:6.2f}-{e['t_out']:6.2f} "
              f"({e['hold']:4.2f}s) {e['mood']:<5} {e['style_id']:<12} "
              f"'{e['word']}'[{e.get('script', '?')}] {e['font']} "
              f"{e['size']}px @({e['x']},{e['y']}) bg={e.get('bg_class', '?')}"
              f"({e.get('bg_lum', -1):.0f}){' 双描边' if e.get('dbl') else ''}{cu}{probe}")
    zc = {}
    for e in events:
        zc[zone_of(e["t_in"])] = zc.get(zone_of(e["t_in"]), 0) + 1
    print(f"[P0] 分区分布: {zc}")
    print(f"[P0] 门禁: onset对齐≤2帧={checks['onset_align_pass']} "
          f"({checks['onset_align_max_frames']}帧) | 最小保持≥0.15s={checks['min_hold_pass']} "
          f"({checks['min_hold']}s) | 时间线覆盖≥80%={checks['timeline_coverage_pass']} "
          f"({checks['timeline_coverage']:.0%}) | 分区覆盖={checks['zones_pass']} "
          f"{checks['zones_covered']}")
    print(f"[P0] 镜头处置: {checks['segments_in_event']}/{checks['segments_total']} "
          f"挂事件, 其余显式跳过 (处置覆盖 {checks['segment_disposition_coverage']:.0%})")
    print(f"[P0] W4 门禁: 同款不连打-字体={checks['no_repeat_consecutive_fonts']} "
          f"同款不连打-变款={checks['no_repeat_consecutive_variants']} "
          f"两级文字≤2={checks['two_levels_pass']}(实测并发 {checks['max_concurrent_text']}) "
          f"字号下限≥60={checks['font_size_floor_pass']}(最小 {checks['min_font_size']})")
    if checks["repeat_font_pairs"] or checks["repeat_variant_pairs"]:
        print(f"[P0] ⚠ 相邻重复: 字体 {checks['repeat_font_pairs']} / 变款 {checks['repeat_variant_pairs']}")
    print(f"[P0] 情绪档: mood={checks['mood_entropy_speed']['mood']} "
          f"时长缩放 sp={checks['mood_entropy_speed']['sp']} "
          f"脉冲倍率={checks['mood_entropy_speed']['pulse_mul']}")
    if checks["probe_fonts"]:
        print(f"[P0] ⚠ 字体待实机探针: {checks['probe_fonts']} — 注入前跑字体在位清单 "
              f"(交接 §六.6), 不过则降级 BebasNeue")
    print(f"[P0] 事件表: {out_dir / 'events.json'}")
    print(f"[P0] JSX: {jsx_p} ({len(jsx):,} 字符)")

    if args.dry_run:
        print("[dry-run] 未调用 AE Bridge — 注入由执行模式完成 "
              "(python .ae-mcp-bridge/send_bridge.py <jsx>)")
        hard_fail = not (checks["onset_align_pass"] and checks["min_hold_pass"]
                         and checks["zones_pass"])
        sys.exit(1 if hard_fail else 0)

    # 执行模式: 文件协议 Bridge (硬约束: python .ae-mcp-bridge/send_bridge.py <jsx>)
    log = ROOT / "tmp" / "ae_text_build.txt"
    if log.exists():
        log.unlink()          # 先删旧日志: 否则上一版留下的同文本日志会被当成本轮成功 (实测踩过)
    r = subprocess.run([sys.executable, str(ROOT / ".ae-mcp-bridge" / "send_bridge.py"),
                        str(jsx_p)], capture_output=True, text=True, timeout=420)
    print(r.stdout[-1500:] if r.stdout else "(bridge 无输出)")
    if r.returncode != 0:
        print(f"[ERR] send_bridge 失败 exit={r.returncode}")
        sys.exit(4)
    if log.exists():
        rep = log.read_text(encoding="utf-8")
        print("build:", rep[:600])
        if "FATAL" in rep or "NOCOMP" in rep:
            print("[ERR] AE 执行报错 — 见 ae_text_build.txt")
            sys.exit(4)
        if nonce not in rep:
            print(f"[ERR] 日志未回显本轮 nonce ({nonce}) — 注入未生效 "
                  "(AE 没跑 / 桥接断 / 跑的是别的脚本)")
            sys.exit(4)
        print(f"[OK] 注入回执校验通过 nonce={nonce}")
    else:
        print("[ERR] 未找到 ae_text_build.txt — AE 可能未执行 JSX")
        sys.exit(4)


if __name__ == "__main__":
    main()
