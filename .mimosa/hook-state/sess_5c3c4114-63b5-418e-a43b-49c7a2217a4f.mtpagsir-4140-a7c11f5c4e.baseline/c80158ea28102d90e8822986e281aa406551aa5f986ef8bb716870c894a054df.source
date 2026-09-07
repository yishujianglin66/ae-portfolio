"""plugin_fx_templates — 付费插件参数模板库（P2/P3）

基于真机探测的参数布局（2026-08-16 scripts/_probe_fx_params.py /
_probe_part_deep.py, 产物存 .ae-mcp-bridge/_fxparams_*.txt 与 _partdeep_*.txt）:
  tc Particular: 7756 参数; 发射区段: 粒子/秒=14, 位置(组)=18, 位置XY=19,
                  发射器大小X/Y=27/28, 分布=30, 方向由深层参数控制(见各模板)
  S_Shake: 83 参数; 核心区段: Amplitude=21, Frequency=22, Phase=23,
           Drift=26, Center Bias=27, Z Dist=28
  GUTS BadTV: 15 参数全探明: Signal Distortion=4, Scan Distortion=5,
           Noise=9, Scanline Overlay=10, Blend w/ Original=13

四类 Particular 粒子模板（对应顶尖 edit 场景语汇）:
  spark      火花迸射 — kick 时刻短促爆发
  ember      余烬漂浮 — 氛围段缓慢上升光尘
  trail      拖尾粒子 — 快速运动残影
  burst      冲击扩散 — crash 全屏冲击

用法:
    from core.plugin_fx_templates import particular_jsx, s_shake_jsx, badtv_jsx
    jsx = particular_jsx("layer1", template="spark", t_hit=0.5)
"""
from __future__ import annotations

from typing import List, Optional


# ── Trapcode Particular 模板 ────────────────────────────────────────
# 真机探测的参数索引（_partdeep_*.txt 逐条对应; 中文版 AE）
# 注意 96/97 的区分: 96="Particle Type"(英文组标签, 不可设值),
# 97="粒子类型"(可设枚举 1-6, 真机验证 1=Sprite, 见 _probe_ptype2.py)
_PART_IDX = {
    "pps": 14,            # 粒子/秒
    "pos_group": 18,      # 位置(组)
    "pos_xy": 19,         # 位置XY(点)
    "size_x": 27, "size_y": 28,          # 发射器大小X/Y
    "direction": 45,
    "rot_x": 47, "rot_y": 48, "rot_z": 49,
    "velocity": 50, "vel_random": 51,
    "life": 94, "life_random": 95,
    "ptype": 97,          # 粒子类型(枚举; 96 是同名英文组标签, 勿用)
    "sprite_layer": 101,  # 图层(精灵引用)
    "feather": 110,
    "mass": 112, "air_res": 115,
    "psize": 121, "size_rand": 122,      # 大小 / 大小随机
    "rand_rot": 135,      # 随机旋转
}
# 真机默认常量（不属于模板差异、每次相同的固定值）
_VEL_RANDOM_DEFAULT = 35     # 速率随机(自然感)
_PTYPE_SPRITE = 1            # 粒子类型=Sprite
_SIZE_RANDOM_DEFAULT = 75    # 大小随机(自然感)

# template: (pps, size_x, size_y, velocity, life, psize, rot_x_deg, air_res)
# 物理取向经真机布局调校（方向=90°=向上 由 rot 区段组合表达）
_PARTICULAR_TEMPLATES = {
    "spark":  dict(pps=5000, size_x=1920, size_y=1080, velocity=1300, life=1.0, psize=28,  rot_x=0,   air_res=5),   # 底部横向迸射, 高速短命
    "ember":  dict(pps=60,   size_x=1920, size_y=1080, velocity=45,  life=6.0,  psize=4.0, rot_x=90,  air_res=55), # 全屏光尘缓慢上升(向上+高阻力)
    "trail":  dict(pps=400,  size_x=100, size_y=100,  velocity=120, life=1.8,  psize=2.5, rot_x=0,   air_res=25), # 点源拖尾
    "burst":  dict(pps=3200, size_x=340, size_y=340,  velocity=1300, life=1.1, psize=11,  rot_x=0,   air_res=2),  # 中心球状爆发, 低阻力飞散
}


def particular_jsx(var: str, template: str = "spark",
                   t_hit: Optional[float] = None,
                   duration: float = 5.0,
                   sprite: Optional[str] = None,
                   comp_var: str = "comp",
                   psize_scale: float = 1.0,
                   glow_mult: float = 1.0,
                   pps_mult: float = 1.0,
                   tint_black: Optional[List[float]] = None,
                   tint_white: Optional[List[float]] = None) -> str:
    """Trapcode Particular 粒子层（含物理 + 贴图精灵）。

    sprite: 特效贴图路径 — 传入则导入为引导层并设为粒子精灵
    （真机验证: 粒子类型=1(Sprite) + 参数101=图层index, 2026-08-16）。
    psize_scale: 粒子大小缩放（M2 迭代: composition 低 → <1.0 缩小不挡脸）。
    glow_mult: Glow 强度倍率（M2g 调参器特征, 2026-08-16 修复: 此前死参数,
              样本记录了却不参与渲染 = 噪声特征）。
    pps_mult: 粒子/秒倍率。
    贴图库: resources/effects/ 4057 张（光点/溅射/魔法阵等 14 类）。
    """
    if template not in _PARTICULAR_TEMPLATES:
        raise ValueError(f"模板 {template} 不在 {list(_PARTICULAR_TEMPLATES)}")
    P = _PARTICULAR_TEMPLATES[template]
    I = _PART_IDX
    psize = round(P["psize"] * psize_scale, 2)
    pps = int(P["pps"] * pps_mult)
    tag = var.replace("layer", "P")
    lines: List[str] = [
        f'    var _pt{tag} = {var}.property("ADBE Effect Parade").addProperty("tc Particular");',
        f'    if (_pt{tag}) {{',
        f'        var _pps{tag} = _pt{tag}.property({I["pps"]});   // 粒子/秒',
    ]
    if t_hit is not None:
        lines.append(f'        _pps{tag}.setValuesAtTimes([0, {t_hit:.3f}, {t_hit + 0.4:.3f}, {duration:.3f}],'
                     f' [0, {pps}, {int(pps * 0.1)}, 0]);')
    else:
        lines.append(f'        _pps{tag}.setValue({P["pps"]});')
    lines += [
        f'        _pt{tag}.property({I["size_x"]}).setValue({P["size_x"]});   // 发射器大小X',
        f'        _pt{tag}.property({I["size_y"]}).setValue({P["size_y"]});   // 发射器大小Y',
        f'        _pt{tag}.property({I["rot_x"]}).setValue({P["rot_x"]});    // X轴旋转(90=向上发射)',
        f'        _pt{tag}.property({I["velocity"]}).setValue({P["velocity"]}); // 速率',
        f'        _pt{tag}.property({I["vel_random"]}).setValue({_VEL_RANDOM_DEFAULT});'
        f'              // 速率随机(自然感)',
        f'        _pt{tag}.property({I["life"]}).setValue({P["life"]});     // 生命周期s',
        f'        _pt{tag}.property({I["air_res"]}).setValue({P["air_res"]}); // 空气阻力',
        f'        _pt{tag}.property({I["psize"]}).setValue({psize});   // 粒子大小',
    ]
    if sprite:
        from pathlib import Path as _P
        sp_js = str(_P(sprite).resolve()).replace("\\", "/")
        lines += [
            f'        try {{',
            f'            var _sp{tag} = {comp_var}.layers.add(app.project.importFile('
            f'new ImportOptions(new File("{sp_js}"))));',
            f'            _sp{tag}.guideLayer = true;   // 引导层不直接渲染, 供精灵引用',
            f'            _pt{tag}.property({I["ptype"]}).setValue({_PTYPE_SPRITE});'
            f'          // 粒子类型=Sprite(真机1-6)',
            f'            _pt{tag}.property({I["sprite_layer"]}).setValue(_sp{tag}.index);'
            f' // 精灵图层引用',
            f'            _pt{tag}.property({I["rand_rot"]}).setValue(1);'
            f'          // 随机旋转(动感)',
            f'            _pt{tag}.property({I["size_rand"]}).setValue({_SIZE_RANDOM_DEFAULT});'
            f'         // 大小随机(自然感)',
            f'            var _tint{tag} = {var}.property("ADBE Effect Parade").addProperty("ADBE Tint");',
            f'            if (_tint{tag}) {{',
            f'                _tint{tag}.property(1).setValue({tint_black or [0.28, 0.12, 0.05, 1]});'
            f'  // 黑→深色',
            f'                _tint{tag}.property(2).setValue({tint_white or [1.0, 0.72, 0.15, 1]});'
            f'   // 白→主色',
            f'                _tint{tag}.property(3).setValue(100);                    // Amount 全染',
            f'            }}',
            f'            // 更亮: 外部 Glow 增强',
            f'            var _glow{tag} = {var}.property("ADBE Effect Parade").addProperty("ADBE Glo2");',
            f'            if (_glow{tag}) {{',
            f'                _glow{tag}.property(3).setValue(14.0);   // 半径',
            f'                _glow{tag}.property(4).setValue({round(4.5 * glow_mult, 2)});'
            f'  // 强度(×glow_mult)',
            f'            }}',
            f'            // 粒子内部辉光(真机读回: glowSize=300/glowOp=25 已生效)',
            f'            // 拖尾: Echo 残影(真机探测 ADBE Echo: 时间=1/数量=2/强度=3/衰减=4)',
            f'            var _echo{tag} = {var}.property("ADBE Effect Parade").addProperty("ADBE Echo");',
            f'            if (_echo{tag}) {{',
            f'                _echo{tag}.property(1).setValue(0.10);   // 残影时间 100ms',
            f'                _echo{tag}.property(2).setValue(10);     // 残影数量 10 个',
            f'                _echo{tag}.property(3).setValue(1.0);    // 起始强度',
            f'                _echo{tag}.property(4).setValue(0.4);    // 衰减(更长拖尾)',
            f'            }}',
            f'        }} catch(_e) {{ }} // 精灵失败退回默认粒子',
        ]
    lines.append('    }')
    return "\n".join(lines)


# ── Sapphire S_Shake（真抖动引擎, 替代 wiggle 表达式的专业版） ──────

def s_shake_jsx(var: str, amplitude: float = 0.5, frequency: float = 20.0,
                drift: float = 0.1, t_start: Optional[float] = None,
                t_end: Optional[float] = None) -> str:
    """S_Shake 专业抖动: 比原生 wiggle 多 Drift(漂移)/Z Dist(纵深) — 手持感更真。

    时间窗: Amplitude 关键帧控制生效区间(窗口外归零)。
    """
    tag = var.replace("layer", "S")
    lines = [
        f'    var _sk{tag} = {var}.property("ADBE Effect Parade").addProperty("S_Shake");',
        f'    if (_sk{tag}) {{',
        f'        var _amp{tag} = _sk{tag}.property(21);   // Amplitude(真机确认)',
    ]
    if t_start is not None and t_end is not None:
        lines.append(f'        _amp{tag}.setValuesAtTimes([0, {t_start:.3f}, {t_end:.3f}, {t_end + 0.1:.3f}],'
                     f' [0, {amplitude}, {amplitude}, 0]);')
    else:
        lines.append(f'        _amp{tag}.setValue({amplitude});')
    lines += [
        f'        _sk{tag}.property(22).setValue({frequency});   // Frequency',
        f'        _sk{tag}.property(26).setValue({drift});       // Drift',
        '    }',
    ]
    return "\n".join(lines)


# ── Bad TV 故障（参数全探明, 窗口式故障爆开） ──────────────────────

def badtv_jsx(var: str, t_start: float = 1.0, t_end: float = 1.3,
              signal: float = 55.0, scan: float = 30.0, noise: float = 25.0) -> str:
    """GUTS Bad TV: 信号扭曲+扫描线+噪声 — 顶尖 edit 故障段标配。

    生效窗口外 Blend w/ Original=0（原画面直通）。
    """
    tag = var.replace("layer", "B")
    return "\n".join([
        f'    var _bt{tag} = {var}.property("ADBE Effect Parade").addProperty("GUTS BadTV");',
        f'    if (_bt{tag}) {{',
        f'        var _sg{tag} = _bt{tag}.property(4);   // Signal Distortion',
        f'        _sg{tag}.setValuesAtTimes([0, {t_start:.3f}, {t_end:.3f}, {t_end + 0.1:.3f}],'
        f' [0, {signal}, {signal}, 0]);',
        f'        _bt{tag}.property(5).setValue({scan});    // Scan Distortion',
        f'        _bt{tag}.property(9).setValue({noise});   // Noise',
        f'        _bt{tag}.property(10).setValue(1);        // Scanline Overlay on',
        f'    }}',
    ])


__all__ = ["particular_jsx", "s_shake_jsx", "badtv_jsx"]
