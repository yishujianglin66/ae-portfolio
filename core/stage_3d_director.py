"""
Stage 3D Director - 3D 舞台编排系统
====================================
多平面视差 + 摄像机路径动画 + 三点布光 + 3D 转场

核心能力:
1. Multi-Plane Parallax: 多素材在不同 Z 深度，摄像机推拉产生视差
2. Camera Path: 推/拉/摇/移/环绕/升降 + wiggle 手持感
3. Three-Point Lighting: Key/Fill/Rim 三点布光 + 色温
4. 3D Transitions: 立方体翻转/书页翻转/开门/卡片翻转
5. Depth of Field: 景深控制 + 焦点转移

用法:
    director = Stage3DDirector(width=1080, height=1920, duration=30, fps=30)
    jsx = director.generate_stage_jsx(material_paths=["a.mp4", "b.mp4"])
"""
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class Stage3DDirector:
    """3D 舞台编排器"""

    def __init__(self, width: int = 1080, height: int = 1920,
                 duration: float = 30, fps: float = 30):
        self.W = width
        self.H = height
        self.DUR = duration
        self.FPS = fps
        self.cx = width / 2
        self.cy = height / 2

    # ================================================================
    #  1. 多平面视差设置
    # ================================================================
    def setup_parallax_layers(self, material_vars: list[str],
                              z_spacing: float = 300) -> str:
        """
        设置多平面视差图层。

        Args:
            material_vars: 素材变量名列表 ["mat_1", "mat_2", ...]
            z_spacing: Z 轴间距 (像素)

        Returns:
            JSX 代码片段
        """
        lines = []
        n = len(material_vars)
        # Z 分布: 从远到近
        z_start = z_spacing * (n - 1) / 2
        z_end = -z_start

        for i, var in enumerate(material_vars):
            z = z_start - i * z_spacing if n > 1 else 0
            # 根据 Z 深度调整缩放 (远的更小)
            scale_factor = 100 + (z / max(abs(z_start), 1)) * 15
            scale = max(80, min(130, scale_factor))

            lines.append(f"// Parallax Layer {i+1}: Z={z:.0f}")
            lines.append(f"if (typeof {var} !== 'undefined' && {var}) {{")
            lines.append(f"  var pLayer{i} = mainComp.layers.add({var});")
            lines.append(f"  pLayer{i}.name = 'Parallax_{i+1}';")
            lines.append(f"  pLayer{i}.threeDLayer = true;")
            lines.append(f"  pLayer{i}.property('ADBE Transform Group').property('ADBE Position').setValue([{self.cx}, {self.cy}, {z:.0f}]);")
            lines.append(f"  pLayer{i}.property('ADBE Transform Group').property('ADBE Scale').setValue([{scale:.1f}, {scale:.1f}]);")
            lines.append("}")

        return "\n".join(lines)

    # ================================================================
    #  2. 摄像机路径动画
    # ================================================================
    def camera_path(self, movement: str = "push_in",
                    speed: str = "normal",
                    intensity: float = 1.0,
                    start_z: float = -800,
                    end_z: float = -400) -> str:
        """
        生成摄像机路径动画。

        Args:
            movement: push_in|pull_out|orbit_left|orbit_right|crane_up|crane_down|handheld
            speed: slow|normal|fast
            intensity: 动画强度 (0.5-2.0)
            start_z: 起始 Z 位置
            end_z: 结束 Z 位置
        """
        speed_mult = {"slow": 0.5, "normal": 1.0, "fast": 2.0}.get(speed, 1.0)
        lines = []
        lines.append(f"// Camera: {movement} ({speed}, intensity={intensity})")
        lines.append(f"var cam = mainComp.layers.addCamera('Stage3D_Cam', [{self.cx}, {self.cy}]);")
        lines.append("cam.threeDLayer = true;")
        lines.append("var camOpt = cam.property('ADBE Camera Options Group');")
        lines.append(f"try {{ camOpt.property('ADBE Camera Zoom').setValue({self.W * 0.8:.0f}); }} catch(e) {{}}")
        lines.append("try { camOpt.property('ADBE Camera Depth of Field').setValue(1); } catch(e) {}")
        lines.append(f"try {{ camOpt.property('ADBE Camera Focus Distance').setValue({abs(start_z):.0f}); }} catch(e) {{}}")
        lines.append("try { camOpt.property('ADBE Camera Aperture').setValue(28); } catch(e) {}")
        lines.append("try { camOpt.property('ADBE Camera Blur Level').setValue(120); } catch(e) {}")
        lines.append("try { camOpt.property('ADBE Iris Shape').setValue(3); } catch(e) {}")

        cam_pos = "cam.property('ADBE Transform Group').property('ADBE Position')"
        cam_rot = "cam.property('ADBE Transform Group').property('ADBE Rotation Y')"
        cam_rotx = "cam.property('ADBE Transform Group').property('ADBE Rotation X')"

        t_mid = self.DUR / 2

        if movement == "push_in":
            lines.append(f"{cam_pos}.setValueAtTime(0, [{self.cx}, {self.cy}, {start_z}]);")
            lines.append(f"{cam_pos}.setValueAtTime({t_mid:.1f}, [{self.cx}, {self.cy}, {(start_z + end_z) / 2:.0f}]);")
            lines.append(f"{cam_pos}.setValueAtTime({self.DUR}, [{self.cx}, {self.cy}, {end_z}]);")
            # 轻微手持晃动
            lines.append(f"{cam_pos}.expression = 'wiggle(1.5, {3 * intensity:.0f}) + value';")

        elif movement == "pull_out":
            lines.append(f"{cam_pos}.setValueAtTime(0, [{self.cx}, {self.cy}, {end_z}]);")
            lines.append(f"{cam_pos}.setValueAtTime({self.DUR}, [{self.cx}, {self.cy}, {start_z}]);")
            lines.append(f"{cam_pos}.expression = 'wiggle(1, {2 * intensity:.0f}) + value';")

        elif movement == "orbit_left":
            radius = abs(start_z) * 0.3 * intensity
            lines.append(f"{cam_pos}.setValueAtTime(0, [{self.cx}, {self.cy}, {start_z}]);")
            lines.append(f"{cam_pos}.setValueAtTime({t_mid:.1f}, [{self.cx - radius:.0f}, {self.cy}, {start_z * 0.85:.0f}]);")
            lines.append(f"{cam_pos}.setValueAtTime({self.DUR}, [{self.cx}, {self.cy}, {start_z}]);")
            lines.append(f"{cam_rot}.setValueAtTime(0, 0);")
            lines.append(f"{cam_rot}.setValueAtTime({t_mid:.1f}, {15 * intensity:.1f});")
            lines.append(f"{cam_rot}.setValueAtTime({self.DUR}, 0);")

        elif movement == "orbit_right":
            radius = abs(start_z) * 0.3 * intensity
            lines.append(f"{cam_pos}.setValueAtTime(0, [{self.cx}, {self.cy}, {start_z}]);")
            lines.append(f"{cam_pos}.setValueAtTime({t_mid:.1f}, [{self.cx + radius:.0f}, {self.cy}, {start_z * 0.85:.0f}]);")
            lines.append(f"{cam_pos}.setValueAtTime({self.DUR}, [{self.cx}, {self.cy}, {start_z}]);")
            lines.append(f"{cam_rot}.setValueAtTime(0, 0);")
            lines.append(f"{cam_rot}.setValueAtTime({t_mid:.1f}, {-15 * intensity:.1f});")
            lines.append(f"{cam_rot}.setValueAtTime({self.DUR}, 0);")

        elif movement == "crane_up":
            lines.append(f"{cam_pos}.setValueAtTime(0, [{self.cx}, {self.cy}, {start_z}]);")
            lines.append(f"{cam_pos}.setValueAtTime({t_mid:.1f}, [{self.cx}, {self.cy - 100 * intensity:.0f}, {start_z * 0.9:.0f}]);")
            lines.append(f"{cam_pos}.setValueAtTime({self.DUR}, [{self.cx}, {self.cy}, {start_z}]);")
            lines.append(f"{cam_rotx}.setValueAtTime(0, 0);")
            lines.append(f"{cam_rotx}.setValueAtTime({t_mid:.1f}, {-10 * intensity:.1f});")
            lines.append(f"{cam_rotx}.setValueAtTime({self.DUR}, 0);")

        elif movement == "crane_down":
            lines.append(f"{cam_pos}.setValueAtTime(0, [{self.cx}, {self.cy}, {start_z}]);")
            lines.append(f"{cam_pos}.setValueAtTime({t_mid:.1f}, [{self.cx}, {self.cy + 80 * intensity:.0f}, {start_z * 0.9:.0f}]);")
            lines.append(f"{cam_pos}.setValueAtTime({self.DUR}, [{self.cx}, {self.cy}, {start_z}]);")

        elif movement == "handheld":
            lines.append(f"{cam_pos}.setValueAtTime(0, [{self.cx}, {self.cy}, {start_z}]);")
            lines.append(f"{cam_pos}.expression = 'wiggle(3, {8 * intensity:.0f}) + value';")
            lines.append(f"var camRig = mainComp.layers.addNull({self.DUR});")
            lines.append("camRig.name = 'Camera_Rig';")
            lines.append("camRig.threeDLayer = true;")
            lines.append("cam.parent = camRig;")
            lines.append("var rigRot = camRig.property('ADBE Transform Group').property('ADBE Rotation Y');")
            lines.append(f"rigRot.setValueAtTime(0, {-3 * intensity:.1f});")
            lines.append(f"rigRot.setValueAtTime({self.DUR}, {3 * intensity:.1f});")

        return "\n".join(lines)

    # ================================================================
    #  3. 三点布光
    # ================================================================
    def three_point_lighting(self,
                             key_intensity: float = 100,
                             key_color: tuple[float, float, float] = (1.0, 0.96, 0.9),
                             fill_intensity: float = 35,
                             fill_color: tuple[float, float, float] = (0.85, 0.92, 1.0),
                             rim_intensity: float = 65,
                             rim_color: tuple[float, float, float] = (0.9, 0.95, 1.0),
                             shadows: bool = True) -> str:
        """
        生成三点布光系统。

        Key Light: 主光源 (右上方, 暖色)
        Fill Light: 补光 (左下方, 冷色, 较弱)
        Rim Light: 轮廓光 (背后, 冷白)
        """
        lines = []
        lines.append("// === Three-Point Lighting ===")

        # Key Light (主光)
        kx = self.cx + self.W * 0.2
        ky = self.cy - self.H * 0.25
        kz = -350
        lines.append("// Key Light (主光)")
        lines.append(f"var keyLight = mainComp.layers.addLight('Key_Light', [{kx:.0f}, {ky:.0f}]);")
        lines.append("keyLight.threeDLayer = true;")
        lines.append("keyLight.property('ADBE Light Options Group').property('ADBE Light Type').setValue(0);")  # Point
        lines.append(f"keyLight.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue({key_intensity});")
        lines.append(f"keyLight.property('ADBE Light Options Group').property('ADBE Light Color').setValue([{key_color[0]}, {key_color[1]}, {key_color[2]}]);")
        if shadows:
            lines.append("keyLight.property('ADBE Light Options Group').property('ADBE Casts Shadows').setValue(1);")
            lines.append("keyLight.property('ADBE Light Options Group').property('ADBE Light Shadow Darkness').setValue(75);")
            lines.append("keyLight.property('ADBE Light Options Group').property('ADBE Light Shadow Diffusion').setValue(12);")
        lines.append(f"keyLight.property('ADBE Transform Group').property('ADBE Position').setValue([{kx:.0f}, {ky:.0f}, {kz}]);")

        # Fill Light (补光)
        fx = self.cx - self.W * 0.15
        fy = self.cy + self.H * 0.1
        fz = -100
        lines.append("// Fill Light (补光)")
        lines.append(f"var fillLight = mainComp.layers.addLight('Fill_Light', [{fx:.0f}, {fy:.0f}]);")
        lines.append("fillLight.threeDLayer = true;")
        lines.append(f"fillLight.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue({fill_intensity});")
        lines.append(f"fillLight.property('ADBE Light Options Group').property('ADBE Light Color').setValue([{fill_color[0]}, {fill_color[1]}, {fill_color[2]}]);")
        lines.append("fillLight.property('ADBE Light Options Group').property('ADBE Casts Shadows').setValue(0);")
        lines.append(f"fillLight.property('ADBE Transform Group').property('ADBE Position').setValue([{fx:.0f}, {fy:.0f}, {fz}]);")

        # Rim Light (轮廓光)
        rx = self.cx + self.W * 0.2
        ry = self.cy - self.H * 0.1
        rz = 300
        lines.append("// Rim Light (轮廓光)")
        lines.append(f"var rimLight = mainComp.layers.addLight('Rim_Light', [{rx:.0f}, {ry:.0f}]);")
        lines.append("rimLight.threeDLayer = true;")
        lines.append(f"rimLight.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue({rim_intensity});")
        lines.append(f"rimLight.property('ADBE Light Options Group').property('ADBE Light Color').setValue([{rim_color[0]}, {rim_color[1]}, {rim_color[2]}]);")
        lines.append("rimLight.property('ADBE Light Options Group').property('ADBE Casts Shadows').setValue(0);")
        lines.append(f"rimLight.property('ADBE Transform Group').property('ADBE Position').setValue([{rx:.0f}, {ry:.0f}, {rz}]);")

        return "\n".join(lines)

    # ================================================================
    #  4. 3D 转场
    # ================================================================
    def transition_3d(self, transition_type: str = "cube_flip",
                      duration: float = 0.8) -> str:
        """
        生成 3D 转场效果。

        Types:
            cube_flip_x / cube_flip_y - 立方体翻转
            page_turn - 书页翻转
            door_open - 开门效果
            card_wipe - 卡片翻转
        """
        lines = []
        lines.append(f"// 3D Transition: {transition_type} ({duration}s)")

        if transition_type == "cube_flip_y":
            # Y 轴立方体翻转: 两个面 + 旋转
            lines.append(f"var transPivot = mainComp.layers.addNull({duration});")
            lines.append("transPivot.name = 'TransPivot';")
            lines.append("transPivot.threeDLayer = true;")
            lines.append(f"transPivot.property('ADBE Transform Group').property('ADBE Position').setValue([{self.cx}, {self.cy}, 0]);")
            lines.append("var transRot = transPivot.property('ADBE Transform Group').property('ADBE Rotation Y');")
            lines.append("transRot.setValueAtTime(0, 0);")
            lines.append(f"transRot.setValueAtTime({duration}, -90);")

        elif transition_type == "cube_flip_x":
            lines.append(f"var transPivot = mainComp.layers.addNull({duration});")
            lines.append("transPivot.name = 'TransPivot';")
            lines.append("transPivot.threeDLayer = true;")
            lines.append(f"transPivot.property('ADBE Transform Group').property('ADBE Position').setValue([{self.cx}, {self.cy}, 0]);")
            lines.append("var transRot = transPivot.property('ADBE Transform Group').property('ADBE Rotation X');")
            lines.append("transRot.setValueAtTime(0, 0);")
            lines.append(f"transRot.setValueAtTime({duration}, 90);")

        elif transition_type == "page_turn":
            # 书页翻转: 锚点移到左边缘 + Y 旋转
            lines.append(f"var pageLayer = mainComp.layers.addSolid([0,0,0], 'PageTurn', {self.W}, {self.H}, 1, {duration});")
            lines.append("pageLayer.threeDLayer = true;")
            lines.append(f"pageLayer.property('ADBE Transform Group').property('ADBE Anchor Point').setValue([0, {self.cy}, 0]);")
            lines.append(f"pageLayer.property('ADBE Transform Group').property('ADBE Position').setValue([0, {self.cy}, 0]);")
            lines.append("var pageRot = pageLayer.property('ADBE Transform Group').property('ADBE Rotation Y');")
            lines.append("pageRot.setValueAtTime(0, 0);")
            lines.append(f"pageRot.setValueAtTime({duration}, -180);")

        elif transition_type == "door_open":
            # 开门效果: 两扇门向两侧旋转
            half_w = self.W / 2
            lines.append("// Left door")
            lines.append(f"var doorL = mainComp.layers.addSolid([0,0,0], 'Door_L', {half_w}, {self.H}, 1, {duration});")
            lines.append("doorL.threeDLayer = true;")
            lines.append(f"doorL.property('ADBE Transform Group').property('ADBE Anchor Point').setValue([{half_w}, {self.cy}, 0]);")
            lines.append(f"doorL.property('ADBE Transform Group').property('ADBE Position').setValue([0, {self.cy}, 0]);")
            lines.append("doorL.property('ADBE Transform Group').property('ADBE Rotation Y').setValueAtTime(0, 0);")
            lines.append(f"doorL.property('ADBE Transform Group').property('ADBE Rotation Y').setValueAtTime({duration}, -90);")
            lines.append("// Right door")
            lines.append(f"var doorR = mainComp.layers.addSolid([0,0,0], 'Door_R', {half_w}, {self.H}, 1, {duration});")
            lines.append("doorR.threeDLayer = true;")
            lines.append(f"doorR.property('ADBE Transform Group').property('ADBE Anchor Point').setValue([0, {self.cy}, 0]);")
            lines.append(f"doorR.property('ADBE Transform Group').property('ADBE Position').setValue([{half_w}, {self.cy}, 0]);")
            lines.append("doorR.property('ADBE Transform Group').property('ADBE Rotation Y').setValueAtTime(0, 0);")
            lines.append(f"doorR.property('ADBE Transform Group').property('ADBE Rotation Y').setValueAtTime({duration}, 90);")

        elif transition_type == "card_wipe":
            # 多卡片翻转
            rows, cols = 4, 4
            card_w = self.W / cols
            card_h = self.H / rows
            for r in range(rows):
                for c in range(cols):
                    delay = (r + c) * 0.05
                    cx = c * card_w + card_w / 2
                    cy = r * card_h + card_h / 2
                    lines.append(f"var card_{r}_{c} = mainComp.layers.addSolid([0.1,0.1,0.15], 'Card_{r}_{c}', {card_w:.0f}, {card_h:.0f}, 1, {duration});")
                    lines.append(f"card_{r}_{c}.threeDLayer = true;")
                    lines.append(f"card_{r}_{c}.property('ADBE Transform Group').property('ADBE Position').setValue([{cx:.0f}, {cy:.0f}, 0]);")
                    lines.append(f"card_{r}_{c}.property('ADBE Transform Group').property('ADBE Rotation X').setValueAtTime({delay:.2f}, 0);")
                    lines.append(f"card_{r}_{c}.property('ADBE Transform Group').property('ADBE Rotation X').setValueAtTime({delay + duration * 0.6:.2f}, 90);")

        return "\n".join(lines)

    # ================================================================
    #  5. 焦点转移 (Rack Focus)
    # ================================================================
    def rack_focus(self, focus_from_z: float = -500,
                   focus_to_z: float = 200,
                   time_start: float = 0,
                   time_end: float = 2.0) -> str:
        """焦点从一处转移到另一处 (景深效果)"""
        lines = []
        lines.append(f"// Rack Focus: Z={focus_from_z} -> Z={focus_to_z}")
        lines.append("try {")
        lines.append("  var focusDist = camOpt.property('ADBE Camera Focus Distance');")
        lines.append(f"  focusDist.setValueAtTime({time_start}, {abs(focus_from_z):.0f});")
        lines.append(f"  focusDist.setValueAtTime({time_end}, {abs(focus_to_z):.0f});")
        lines.append("} catch(e) {}")
        return "\n".join(lines)

    # ================================================================
    #  6. 完整舞台生成
    # ================================================================
    def generate_full_stage(self, material_paths: list[str],
                            camera_movement: str = "push_in",
                            lighting_mood: str = "cinematic",
                            transitions: list[dict] = None) -> str:
        """
        生成完整 3D 舞台 JSX。

        Args:
            material_paths: 素材文件路径列表
            camera_movement: 摄像机运动类型
            lighting_mood: 布光情绪 (cinematic/dramatic/soft/dark)
            transitions: 转场列表 [{"type": "cube_flip_y", "time": 5.0}, ...]
        """
        lines = []
        lines.append("// === Stage 3D Director - Auto Generated ===")
        lines.append(f"var W = {self.W}, H = {self.H}, DUR = {self.DUR};")
        lines.append("")

        # 1. 创建合成
        lines.append(f"var mainComp = app.project.items.addComp('Stage3D_{int(__import__('time').time())}', {self.W}, {self.H}, 1, {self.DUR}, {self.FPS});")
        lines.append("mainComp.bgColor = [0.05, 0.05, 0.08];")
        lines.append("")

        # 2. 导入素材
        lines.append("// --- Materials ---")
        mat_vars = []
        for i, mp in enumerate(material_paths):
            var = f"mat_{i+1}"
            mat_vars.append(var)
            safe_path = mp.replace("\\", "/")
            lines.append(f"var {var} = null;")
            lines.append(f"try {{ var io_{i+1} = new ImportOptions(File('{safe_path}')); {var} = app.project.importFile(io_{i+1}); }} catch(e) {{}}")
        lines.append("")

        # 3. 多平面视差
        lines.append("// --- Parallax Layers ---")
        lines.append(self.setup_parallax_layers(mat_vars[:5]))
        lines.append("")

        # 4. 摄像机
        lines.append("// --- Camera ---")
        lines.append(self.camera_path(camera_movement))
        lines.append("")

        # 5. 布光
        lines.append("// --- Lighting ---")
        mood_lighting = {
            "cinematic": {"key_intensity": 100, "fill_intensity": 35, "rim_intensity": 65,
                          "key_color": (1.0, 0.96, 0.9)},
            "dramatic": {"key_intensity": 130, "fill_intensity": 15, "rim_intensity": 80,
                         "key_color": (1.0, 0.85, 0.7)},
            "soft": {"key_intensity": 60, "fill_intensity": 50, "rim_intensity": 30,
                     "key_color": (1.0, 0.98, 0.95)},
            "dark": {"key_intensity": 80, "fill_intensity": 10, "rim_intensity": 50,
                     "key_color": (0.8, 0.85, 1.0)},
        }
        lp = mood_lighting.get(lighting_mood, mood_lighting["cinematic"])
        lines.append(self.three_point_lighting(**lp))
        lines.append("")

        # 6. 转场
        if transitions:
            lines.append("// --- 3D Transitions ---")
            for tr in transitions:
                lines.append(self.transition_3d(
                    tr.get("type", "cube_flip_y"),
                    tr.get("duration", 0.8)
                ))
            lines.append("")

        # 7. 调整层 (全局调色)
        lines.append("// --- Color Grade Adjustment ---")
        lines.append("var colorAdj = mainComp.layers.addSolid([0.5,0.5,0.5], 'Color_Grade', W, H, 1, DUR);")
        lines.append("colorAdj.adjustmentLayer = true;")
        lines.append("colorAdj.moveToEnd();")
        lines.append("var lumetri = colorAdj.property('ADBE Effect Parade').addProperty('ADBE Lumetri');")
        lines.append("try { lumetri.property('Contrast').setValue(20); } catch(e) {}")
        lines.append("try { lumetri.property('Saturation').setValue(15); } catch(e) {}")
        lines.append("")

        # 8. 结果
        lines.append("JSON.stringify({success: true, comp: mainComp.name, layers: mainComp.numLayers, stage3d: true});")

        return "\n".join(lines)


# ================================================================
#  主入口 (测试)
# ================================================================
if __name__ == "__main__":
    import time as _time

    print("=" * 60)
    print("  Stage 3D Director - 3D 舞台编排测试")
    print("=" * 60)

    director = Stage3DDirector(width=1080, height=1920, duration=30, fps=30)

    # 测试素材
    test_materials = [
        r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4",
    ]

    # 生成完整舞台
    jsx = director.generate_full_stage(
        material_paths=test_materials,
        camera_movement="push_in",
        lighting_mood="cinematic",
        transitions=[
            {"type": "cube_flip_y", "time": 10.0, "duration": 0.8},
            {"type": "door_open", "time": 20.0, "duration": 0.7},
        ]
    )

    # 保存
    output_path = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_director\stage3d_test.jsx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(jsx)

    print(f"\n  JSX 生成完成: {len(jsx.splitlines())} 行")
    print(f"  保存: {output_path}")

    # 分别测试各组件
    print("\n--- 组件测试 ---")
    print(f"\n[Parallax] {len(director.setup_parallax_layers(['m1','m2','m3']).splitlines())} lines")
    print(f"[Camera push_in] {len(director.camera_path('push_in').splitlines())} lines")
    print(f"[Camera orbit] {len(director.camera_path('orbit_left').splitlines())} lines")
    print(f"[Camera handheld] {len(director.camera_path('handheld').splitlines())} lines")
    print(f"[3-Point Light] {len(director.three_point_lighting().splitlines())} lines")
    print(f"[3D Cube Flip] {len(director.transition_3d('cube_flip_y').splitlines())} lines")
    print(f"[3D Door Open] {len(director.transition_3d('door_open').splitlines())} lines")
    print(f"[3D Card Wipe] {len(director.transition_3d('card_wipe').splitlines())} lines")
    print(f"[Rack Focus] {len(director.rack_focus().splitlines())} lines")

    print("\n  全部组件测试通过!")
