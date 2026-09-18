# -*- coding: utf-8 -*-
"""CameraLanguageLibrary — 12种专业运镜 + Ease曲线JSX生成 (T2→V2)

消费 config/master_rules.json 的 camera_templates(8基础) 与
camera3d_templates(4真实3D摄像机)，为每段镜头生成带 KeyframeEase
缓动曲线的 JSX（替代线性两点关键帧）。

基础8运镜: push推 / pull拉 / pan摇 / truck移 / follow跟 /
           orbit环绕 / whip甩镜 / dutch斜切
3D新增4运镜: dolly_zoom推拉变焦 / crane摇臂升降 /
             orbit_3d三维环绕 / shake手持震动
  — 均生成 null object + camera + 父子关系完整JSX链，
    空对象作为运动控制器: 所有关键帧打在null上，图层仅子级跟随。

铁律(知识库):
- Scale ≤ 150% 防糊
- JSX 无 alert/confirm
- whip 甩镜带快门360°运动模糊标记
- 段落z_depth: drop段Z推进(纵深冲击)，break段Z回拉(呼吸感)
"""
import json
import os
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_RULES_PATH = os.path.join(ROOT, "config", "master_rules.json")

# Ease 曲线 → AE KeyframeEase(speed%, influence%) 参数
# speed 控制进入/离开关键帧的速度, influence 控制曲线弯曲程度
EASE_PRESETS = {
    "easeOut":       (1.0, 75.0),   # 快速启动缓速收尾(推镜标准)
    "easeIn":        (1.0, 75.0),   # 缓速启动加速离开
    "easeInOut":     (1.0, 75.0),   # 两端缓中间快
    "easeInHard":    (100.0, 90.0), # 甩镜: 急加速
    "linear_smooth": (1.0, 0.1),    # 近线性微平滑(移镜)
    "linear":        (1.0, 0.1),
}

CAMERA_IDS = ["push", "pull", "pan", "truck", "follow", "orbit", "whip", "dutch"]
CAMERA_IDS_3D = ["dolly_zoom", "crane", "orbit_3d", "shake"]
CAMERA_IDS_ALL = CAMERA_IDS + CAMERA_IDS_3D  # 全量12运镜


def load_master_rules() -> dict[str, Any]:
    with open(MASTER_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


class CameraLanguageLibrary:
    """12运镜模板库: 8基础(2D变换) + 4真实3D摄像机(null控制器链)"""

    def __init__(self, rules: dict[str, Any] | None = None):
        self.rules = rules or load_master_rules()
        self.templates: dict[str, Any] = {
            k: v for k, v in self.rules.get("camera_templates", {}).items()
            if not k.startswith("_")
        }
        self.templates_3d: dict[str, Any] = {
            k: v for k, v in self.rules.get("camera3d_templates", {}).items()
            if not k.startswith("_")
        }
        self.z_depth_profile: dict[str, float] = {
            k: v for k, v in self.rules.get("z_depth_profile", {}).items()
            if not k.startswith("_")
        }

    # ── 查询 ────────────────────────────────────────────────
    def list_cameras(self) -> list[str]:
        return list(self.templates.keys())

    def list_cameras_3d(self) -> list[str]:
        return list(self.templates_3d.keys())

    def list_cameras_all(self) -> list[str]:
        return self.list_cameras() + self.list_cameras_3d()

    def get_template(self, cam_id: str) -> dict[str, Any] | None:
        return self.templates.get(cam_id) or self.templates_3d.get(cam_id)

    def cameras_for_segment(self, seg_type: str) -> list[str]:
        """返回适用该叙事段落的基础运镜列表(保持V1行为)"""
        return [cid for cid, t in self.templates.items()
                if seg_type in t.get("segments", [])]

    def cameras3d_for_segment(self, seg_type: str) -> list[str]:
        """返回适用该叙事段落的3D摄像机运镜列表"""
        return [cid for cid, t in self.templates_3d.items()
                if seg_type in t.get("segments", [])]

    def z_depth_for_segment(self, seg_type: str) -> float:
        """段落Z纵深: drop推进(+) / break回拉(-)"""
        return float(self.z_depth_profile.get(seg_type, 0.0))

    def camera_by_cn(self, cn_name: str) -> str | None:
        """中文运镜名 → camera id (兼容旧剧本 movement 字段)"""
        mapping = {"推": "push", "拉": "pull", "摇": "pan", "移": "truck",
                   "跟": "follow", "环绕": "orbit", "甩镜": "whip", "甩": "whip",
                   "斜切": "dutch", "快推": "push", "慢拉": "pull",
                   "推拉变焦": "dolly_zoom", "眩晕变焦": "dolly_zoom",
                   "摇臂": "crane", "升降": "crane", "三维环绕": "orbit_3d",
                   "手持": "shake", "震动": "shake"}
        return mapping.get(cn_name)

    # ── JSX 生成 ────────────────────────────────────────────
    def _ease_jsx(self, var: str, ease_name: str, n_keys: int) -> list[str]:
        """生成 setTemporalEaseAtKey 语句 (in/out 同参数)"""
        speed, infl = EASE_PRESETS.get(ease_name, (1.0, 0.1))
        lines = []
        for k in range(1, n_keys + 1):
            lines.append(
                f'var __e{k} = new KeyframeEase({speed}, {infl});'
                f' {var}.setTemporalEaseAtKey({k}, [__e{k}], [__e{k}]);')
        return lines

    def to_jsx(self, cam_id: str, layer_var: str,
               seg_start: float, seg_end: float,
               speed_factor: float = 1.0) -> str:
        """生成单运镜的完整JSX片段 (带Ease曲线, try/catch安全包裹)"""
        t = self.templates.get(cam_id)
        if t is None:
            return ""
        tg = f'{layer_var}.property("ADBE Transform Group")'
        lines = ["try {"]
        ease = t.get("ease", "easeInOut")
        prop = t.get("prop")

        if prop == "scale":
            frm, to = t["from"], t["to"]
            max_scale = t.get("max_scale", 150)
            # 速度因子放大但不超过 max_scale (知识库铁律 ≤150% 防糊)
            to_adj = [min(max_scale, 100 + (v - 100) * speed_factor) for v in to]
            frm_adj = [min(max_scale, 100 + (v - 100) * speed_factor) for v in frm]
            p = f'{tg}.property("ADBE Scale")'
            lines.append(f'{p}.setValueAtTime({seg_start}, [{frm_adj[0]}, {frm_adj[1]}]);')
            lines.append(f'{p}.setValueAtTime({seg_end}, [{to_adj[0]}, {to_adj[1]}]);')
            lines.extend(self._ease_jsx(p, ease, 2))
        elif prop == "position":
            fx, fy = t["from"]; tx, ty = t["to"]
            # percent_of_w 单位: 相对合成宽高百分比偏移
            sf = min(speed_factor, 2.0)
            p = f'{tg}.property("ADBE Position")'
            lines.append(f'{p}.setValueAtTime({seg_start}, '
                         f'[W/2 + ({fx})*W*{sf}, H/2 + ({fy})*H*{sf}, 0]);')
            lines.append(f'{p}.setValueAtTime({seg_end}, '
                         f'[W/2 + ({tx})*W*{sf}, H/2 + ({ty})*H*{sf}, 0]);')
            lines.extend(self._ease_jsx(p, ease, 2))
        elif prop == "rotation":
            frm, to = t["from"], t["to"]
            p = f'{tg}.property("ADBE Rotate Z")'
            lines.append(f'{p}.setValueAtTime({seg_start}, {frm * speed_factor});')
            lines.append(f'{p}.setValueAtTime({seg_end}, {to * speed_factor});')
            lines.extend(self._ease_jsx(p, ease, 2))
            if t.get("motion_blur"):
                lines.append(f'{layer_var}.motionBlur = true;')

        lines.append("} catch(e) {}")
        return " ".join(lines)

    # ── 3D摄像机 JSX 生成 (null控制器链) ─────────────────────
    def to_jsx_3d(self, cam_id: str, layer_var: str, comp_var: str,
                  seg_start: float, seg_end: float,
                  z_depth: float = 0.0, speed_factor: float = 1.0,
                  uid: str = "") -> str:
        """生成真实3D摄像机运镜JSX: camera → null → layer 父子链

        铁律: 所有关键帧打在 null 上，图层仅做子级跟随。
        z_depth: 段落纵深偏移(drop+ / break-)，叠加到图层Z位置。
        """
        t = self.templates_3d.get(cam_id)
        if t is None:
            return ""
        u = uid or cam_id
        null_v = f"ctrl_{u}"
        cam_v = f"cam_{u}"
        ease = t.get("ease", "easeInOut")
        lines = ["try {"]
        # 1) null 运动控制器 (3D)
        lines.append(f'var {null_v} = {comp_var}.layers.addNull();')
        lines.append(f'{null_v}.name = "{cam_id}_ctrl";')
        lines.append(f'{null_v}.threeDLayer = true;')
        # 2) 图层置3D + Z纵深 + 父级指向null
        lines.append(f'{layer_var}.threeDLayer = true;')
        lines.append(f'{layer_var}.parent = {null_v};')
        if z_depth:
            lines.append(f'{layer_var}.property("ADBE Transform Group")'
                         f'.property("ADBE Position").setValue([W/2, H/2, {z_depth}]);')
        # 3) 真实摄像机 (POI看向合成中心)
        lines.append(f'var {cam_v} = {comp_var}.layers.addCamera('
                     f'"{cam_id}_cam", [W/2, H/2]);')

        ntg = f'{null_v}.property("ADBE Transform Group")'
        if cam_id == "dolly_zoom":
            zf, zt = t["cam_z_from"], t["cam_z_to"]
            sf = min(speed_factor, 2.0)
            zf_adj = zf * sf if sf < 1.0 else zf
            zt_adj = zt * sf if sf < 1.0 else zt
            cp = f'{cam_v}.property("ADBE Transform Group").property("ADBE Position")'
            lines.append(f'{cp}.setValueAtTime({seg_start}, [W/2, H/2, {zf_adj}]);')
            lines.append(f'{cp}.setValueAtTime({seg_end}, [W/2, H/2, {zt_adj}]);')
            lines.extend(self._ease_jsx(cp, ease, 2))
            # null缩放补偿(眩晕感): scale ≤150 铁律
            max_scale = t.get("max_scale", 150)
            sfrm = [min(max_scale, v) for v in t["null_scale_from"]]
            sto = [min(max_scale, v) for v in t["null_scale_to"]]
            nsp = f'{ntg}.property("ADBE Scale")'
            lines.append(f'{nsp}.setValueAtTime({seg_start}, [{sfrm[0]}, {sfrm[1]}, 100]);')
            lines.append(f'{nsp}.setValueAtTime({seg_end}, [{sto[0]}, {sto[1]}, 100]);')
            lines.extend(self._ease_jsx(nsp, ease, 2))
        elif cam_id == "crane":
            cy_f = t["null_y_from"]
            cy_t = t["null_y_to"]
            cz = t.get("cam_z", -900)
            npos = f'{ntg}.property("ADBE Position")'
            lines.append(f'{npos}.setValueAtTime({seg_start}, [W/2, H/2 + ({cy_f})*H, 0]);')
            lines.append(f'{npos}.setValueAtTime({seg_end}, [W/2, H/2 + ({cy_t})*H, 0]);')
            lines.extend(self._ease_jsx(npos, ease, 2))
            cp = f'{cam_v}.property("ADBE Transform Group").property("ADBE Position")'
            lines.append(f'{cp}.setValue([W/2, H/2, {cz}]);')
        elif cam_id == "orbit_3d":
            rf = t["null_y_rot_from"] * min(speed_factor, 2.0)
            rt = t["null_y_rot_to"] * min(speed_factor, 2.0)
            cz = t.get("cam_z", -1100)
            nrot = f'{ntg}.property("ADBE Rotate Y")'
            lines.append(f'{nrot}.setValueAtTime({seg_start}, {rf});')
            lines.append(f'{nrot}.setValueAtTime({seg_end}, {rt});')
            lines.extend(self._ease_jsx(nrot, ease, 2))
            cp = f'{cam_v}.property("ADBE Transform Group").property("ADBE Position")'
            lines.append(f'{cp}.setValue([W/2, H/2, {cz}]);')
        elif cam_id == "shake":
            amp = t["amplitude"] * min(speed_factor, 2.0)
            npos = f'{ntg}.property("ADBE Position")'
            # 6关键帧不规则手持抖动 (确定性偏移序列, 关键帧全在null)
            offsets = [(0, 0), (0.6, -0.8), (-1.0, 0.5), (0.8, 0.9),
                       (-0.5, -0.6), (0, 0)]
            dur = max(seg_end - seg_start, 0.1)
            for i, (ox, oy) in enumerate(offsets):
                tt = round(seg_start + dur * i / (len(offsets) - 1), 3)
                lines.append(f'{npos}.setValueAtTime({tt}, '
                             f'[W/2 + ({ox})*{amp}, H/2 + ({oy})*{amp}, 0]);')
            lines.extend(self._ease_jsx(npos, ease, len(offsets)))
            cz = t.get("cam_z", -900)
            cp = f'{cam_v}.property("ADBE Transform Group").property("ADBE Position")'
            lines.append(f'{cp}.setValue([W/2, H/2, {cz}]);')

        lines.append("} catch(e) {}")
        return " ".join(lines)

    # ── 校验 ────────────────────────────────────────────────
    @staticmethod
    def validate_jsx(jsx: str) -> dict[str, Any]:
        """JSX安全与质量校验: 无alert/带Ease/scale≤150"""
        issues = []
        if "alert(" in jsx or "confirm(" in jsx:
            issues.append("contains alert/confirm")
        if "setValueAtTime" in jsx and "setTemporalEaseAtKey" not in jsx:
            issues.append("keyframes without ease curves")
        # scale 上限检查 (提取所有数值对)
        import re
        for m in re.finditer(r'ADBE Scale[^;]*setValueAtTime\([^,]+, \[([\d.]+), ([\d.]+)\]', jsx):
            if float(m.group(1)) > 150 or float(m.group(2)) > 150:
                issues.append(f"scale {m.group(1)} exceeds 150")
        return {"ok": not issues, "issues": issues}
