"""
场景编排引擎
提供场景管理、转场生成、镜头运动和时间线编排功能
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math


TRANSITION_TYPES = {
    "crossfade": "交叉淡入淡出",
    "slide_left": "向左滑动",
    "slide_right": "向右滑动",
    "zoom_in": "放大进入",
    "wipe_left": "向左擦除",
    "dissolve": "溶解",
    "flash_white": "白光闪切",
    "blur": "模糊过渡",
    "scale_up": "放大过渡",
    "page_turn": "翻页",
}


CAMERA_MOVE_TYPES = {
    "push": "推镜",
    "pull": "拉镜",
    "pan_left": "左摇",
    "pan_right": "右摇",
    "tilt_up": "上摇",
    "tilt_down": "下摇",
    "follow": "跟随",
    "shake": "手持抖动",
    "dolly": "轨道移动",
    "crane": "升降镜头",
}


@dataclass
class CameraMove:
    type: str
    duration: float
    start_scale: float = 100.0
    end_scale: float = 100.0
    start_x: float = 0.0
    end_x: float = 0.0
    start_y: float = 0.0
    end_y: float = 0.0
    shake_amplitude: float = 0.0
    shake_frequency: float = 0.0


@dataclass
class Scene:
    name: str
    duration: float
    layer_name: str = ""
    start_time: float = 0.0
    effects: List[Dict] = field(default_factory=list)
    camera_moves: List[CameraMove] = field(default_factory=list)


@dataclass
class Transition:
    type: str
    duration: float
    start_time: float = 0.0
    from_scene: str = ""
    to_scene: str = ""


class SceneOrchestrator:
    def __init__(self, fps: float = 30, comp_width: int = 1920, comp_height: int = 1080):
        self.fps = fps
        self.comp_width = comp_width
        self.comp_height = comp_height
        self.scenes: List[Scene] = []
        self.transitions: List[Transition] = []
        self._scene_counter = 0

    def add_scene(self, scene: Scene) -> Scene:
        if not scene.layer_name:
            self._scene_counter += 1
            scene.layer_name = f"Scene_{self._scene_counter:02d}_{scene.name}"

        if self.scenes:
            last_scene = self.scenes[-1]
            scene.start_time = last_scene.start_time + last_scene.duration
        else:
            scene.start_time = 0.0

        self.scenes.append(scene)
        return scene

    @property
    def total_duration(self) -> float:
        if not self.scenes:
            return 0.0
        last_scene = self.scenes[-1]
        return last_scene.start_time + last_scene.duration

    def generate_transitions(self, transition_type: str, duration: float = 0.5) -> List[Transition]:
        self.transitions = []
        if transition_type not in TRANSITION_TYPES:
            raise ValueError(f"Unknown transition type: {transition_type}. "
                           f"Available: {list(TRANSITION_TYPES.keys())}")

        for i in range(len(self.scenes) - 1):
            current_scene = self.scenes[i]
            next_scene = self.scenes[i + 1]

            transition_start = current_scene.start_time + current_scene.duration - duration / 2

            transition = Transition(
                type=transition_type,
                duration=duration,
                start_time=transition_start,
                from_scene=current_scene.layer_name,
                to_scene=next_scene.layer_name,
            )
            self.transitions.append(transition)

        return self.transitions

    def apply_camera_move(self, scene: Scene, move: CameraMove, layer_name: str = "") -> List[Dict]:
        keyframes = []
        target_layer = layer_name or scene.layer_name
        start_time = scene.start_time

        if move.type == "push":
            keyframes.extend(self._gen_scale_keyframes(target_layer, start_time, move.duration,
                                                        move.start_scale, move.end_scale))
        elif move.type == "pull":
            keyframes.extend(self._gen_scale_keyframes(target_layer, start_time, move.duration,
                                                        move.start_scale, move.end_scale))
        elif move.type in ("pan_left", "pan_right"):
            keyframes.extend(self._gen_position_x_keyframes(target_layer, start_time, move.duration,
                                                             move.start_x, move.end_x))
        elif move.type in ("tilt_up", "tilt_down"):
            keyframes.extend(self._gen_position_y_keyframes(target_layer, start_time, move.duration,
                                                             move.start_y, move.end_y))
        elif move.type == "follow":
            keyframes.extend(self._gen_position_x_keyframes(target_layer, start_time, move.duration,
                                                             move.start_x, move.end_x))
            keyframes.extend(self._gen_position_y_keyframes(target_layer, start_time, move.duration,
                                                             move.start_y, move.end_y))
        elif move.type == "shake":
            keyframes.extend(self._gen_shake_keyframes(target_layer, start_time, move.duration,
                                                        move.shake_amplitude, move.shake_frequency))
        elif move.type == "dolly":
            keyframes.extend(self._gen_scale_keyframes(target_layer, start_time, move.duration,
                                                        move.start_scale, move.end_scale))
            keyframes.extend(self._gen_position_x_keyframes(target_layer, start_time, move.duration,
                                                             move.start_x, move.end_x))
        elif move.type == "crane":
            keyframes.extend(self._gen_position_y_keyframes(target_layer, start_time, move.duration,
                                                             move.start_y, move.end_y))
            keyframes.extend(self._gen_scale_keyframes(target_layer, start_time, move.duration,
                                                        move.start_scale, move.end_scale))

        return keyframes

    def _gen_scale_keyframes(self, layer_name: str, start_time: float, duration: float,
                              start_scale: float, end_scale: float) -> List[Dict]:
        return [
            {
                "layerName": layer_name,
                "propertyName": "Scale",
                "time": round(start_time, 3),
                "value": [start_scale, start_scale],
                "easeType": "linear",
            },
            {
                "layerName": layer_name,
                "propertyName": "Scale",
                "time": round(start_time + duration, 3),
                "value": [end_scale, end_scale],
                "easeType": "linear",
            },
        ]

    def _gen_position_x_keyframes(self, layer_name: str, start_time: float, duration: float,
                                   start_x: float, end_x: float) -> List[Dict]:
        center_x = self.comp_width / 2
        return [
            {
                "layerName": layer_name,
                "propertyName": "Position",
                "time": round(start_time, 3),
                "value": [center_x + start_x, self.comp_height / 2],
                "easeType": "linear",
            },
            {
                "layerName": layer_name,
                "propertyName": "Position",
                "time": round(start_time + duration, 3),
                "value": [center_x + end_x, self.comp_height / 2],
                "easeType": "linear",
            },
        ]

    def _gen_position_y_keyframes(self, layer_name: str, start_time: float, duration: float,
                                   start_y: float, end_y: float) -> List[Dict]:
        center_y = self.comp_height / 2
        return [
            {
                "layerName": layer_name,
                "propertyName": "Position",
                "time": round(start_time, 3),
                "value": [self.comp_width / 2, center_y + start_y],
                "easeType": "linear",
            },
            {
                "layerName": layer_name,
                "propertyName": "Position",
                "time": round(start_time + duration, 3),
                "value": [self.comp_width / 2, center_y + end_y],
                "easeType": "linear",
            },
        ]

    def _gen_shake_keyframes(self, layer_name: str, start_time: float, duration: float,
                              amplitude: float, frequency: float) -> List[Dict]:
        keyframes = []
        if frequency <= 0 or amplitude <= 0:
            return keyframes

        shake_count = max(2, int(duration * frequency))
        interval = duration / shake_count

        for i in range(shake_count + 1):
            t = start_time + i * interval
            if i == 0 or i == shake_count:
                offset_x = 0.0
                offset_y = 0.0
            else:
                angle = (i * 2 * math.pi) / shake_count
                offset_x = math.sin(angle) * amplitude
                offset_y = math.cos(angle) * amplitude * 0.7

            keyframes.append({
                "layerName": layer_name,
                "propertyName": "Position",
                "time": round(t, 3),
                "value": [self.comp_width / 2 + offset_x, self.comp_height / 2 + offset_y],
                "easeType": "linear",
            })

        return keyframes

    def generate_timeline(self) -> List[Dict]:
        timeline = []

        for scene in self.scenes:
            timeline.append({
                "type": "scene",
                "name": scene.name,
                "layerName": scene.layer_name,
                "startTime": round(scene.start_time, 3),
                "duration": round(scene.duration, 3),
                "endTime": round(scene.start_time + scene.duration, 3),
                "effectsCount": len(scene.effects),
                "cameraMovesCount": len(scene.camera_moves),
            })

        for transition in self.transitions:
            timeline.append({
                "type": "transition",
                "name": transition.type,
                "fromScene": transition.from_scene,
                "toScene": transition.to_scene,
                "startTime": round(transition.start_time, 3),
                "duration": round(transition.duration, 3),
                "endTime": round(transition.start_time + transition.duration, 3),
            })

        timeline.sort(key=lambda x: x["startTime"])
        return timeline

    def generate_transition_keyframes(self) -> List[Dict]:
        keyframes = []

        for transition in self.transitions:
            t = transition.type
            start = transition.start_time
            dur = transition.duration
            from_layer = transition.from_scene
            to_layer = transition.to_scene

            if t == "crossfade":
                keyframes.extend(self._crossfade_keyframes(from_layer, to_layer, start, dur))
            elif t == "blur":
                keyframes.extend(self._blur_transition_keyframes(from_layer, to_layer, start, dur))
            elif t == "slide_left":
                keyframes.extend(self._slide_keyframes(from_layer, to_layer, start, dur, direction="left"))
            elif t == "slide_right":
                keyframes.extend(self._slide_keyframes(from_layer, to_layer, start, dur, direction="right"))
            elif t == "zoom_in":
                keyframes.extend(self._zoom_transition_keyframes(from_layer, to_layer, start, dur))
            elif t == "wipe_left":
                keyframes.extend(self._wipe_keyframes(from_layer, to_layer, start, dur, direction="left"))
            elif t == "dissolve":
                keyframes.extend(self._dissolve_keyframes(from_layer, to_layer, start, dur))
            elif t == "flash_white":
                keyframes.extend(self._flash_white_keyframes(from_layer, to_layer, start, dur))
            elif t == "scale_up":
                keyframes.extend(self._scale_up_keyframes(from_layer, to_layer, start, dur))
            elif t == "page_turn":
                keyframes.extend(self._page_turn_keyframes(from_layer, to_layer, start, dur))

        return keyframes

    def _crossfade_keyframes(self, from_layer: str, to_layer: str, start: float, dur: float) -> List[Dict]:
        return [
            {"layerName": from_layer, "propertyName": "Opacity", "time": round(start, 3), "value": 100, "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Opacity", "time": round(start + dur, 3), "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity", "time": round(start, 3), "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity", "time": round(start + dur, 3), "value": 100, "easeType": "linear"},
        ]

    def _blur_transition_keyframes(self, from_layer: str, to_layer: str, start: float, dur: float) -> List[Dict]:
        half = dur / 2
        kfs = []
        kfs.append({"layerName": from_layer, "propertyName": "Opacity", "time": round(start, 3), "value": 100, "easeType": "linear"})
        kfs.append({"layerName": from_layer, "propertyName": "Opacity", "time": round(start + half, 3), "value": 0, "easeType": "linear"})
        kfs.append({"layerName": to_layer, "propertyName": "Opacity", "time": round(start + half, 3), "value": 0, "easeType": "linear"})
        kfs.append({"layerName": to_layer, "propertyName": "Opacity", "time": round(start + dur, 3), "value": 100, "easeType": "linear"})

        kfs.append({"layerName": "Adjustment_Blur", "propertyName": "Gaussian Blur.Blurriness",
                    "time": round(start, 3), "value": 0, "easeType": "linear"})
        kfs.append({"layerName": "Adjustment_Blur", "propertyName": "Gaussian Blur.Blurriness",
                    "time": round(start + half, 3), "value": 50, "easeType": "linear"})
        kfs.append({"layerName": "Adjustment_Blur", "propertyName": "Gaussian Blur.Blurriness",
                    "time": round(start + dur, 3), "value": 0, "easeType": "linear"})
        return kfs

    def _slide_keyframes(self, from_layer: str, to_layer: str, start: float, dur: float, direction: str) -> List[Dict]:
        offset = self.comp_width if direction == "left" else -self.comp_width
        center_x = self.comp_width / 2
        center_y = self.comp_height / 2
        return [
            {"layerName": from_layer, "propertyName": "Position", "time": round(start, 3),
             "value": [center_x, center_y], "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Position", "time": round(start + dur, 3),
             "value": [center_x + offset, center_y], "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Position", "time": round(start, 3),
             "value": [center_x - offset, center_y], "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Position", "time": round(start + dur, 3),
             "value": [center_x, center_y], "easeType": "linear"},
        ]

    def _zoom_transition_keyframes(self, from_layer: str, to_layer: str, start: float, dur: float) -> List[Dict]:
        return [
            {"layerName": from_layer, "propertyName": "Scale", "time": round(start, 3),
             "value": [100, 100], "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Scale", "time": round(start + dur, 3),
             "value": [200, 200], "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Opacity", "time": round(start, 3),
             "value": 100, "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Opacity", "time": round(start + dur, 3),
             "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Scale", "time": round(start, 3),
             "value": [50, 50], "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Scale", "time": round(start + dur, 3),
             "value": [100, 100], "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity", "time": round(start, 3),
             "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity", "time": round(start + dur, 3),
             "value": 100, "easeType": "linear"},
        ]

    def _wipe_keyframes(self, from_layer: str, to_layer: str, start: float, dur: float, direction: str) -> List[Dict]:
        kfs = []
        kfs.extend(self._crossfade_keyframes(from_layer, to_layer, start, dur))
        return kfs

    def _dissolve_keyframes(self, from_layer: str, to_layer: str, start: float, dur: float) -> List[Dict]:
        return self._crossfade_keyframes(from_layer, to_layer, start, dur)

    def _flash_white_keyframes(self, from_layer: str, to_layer: str, start: float, dur: float) -> List[Dict]:
        half = dur / 2
        return [
            {"layerName": from_layer, "propertyName": "Opacity", "time": round(start, 3), "value": 100, "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Opacity", "time": round(start + half, 3), "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity", "time": round(start + half, 3), "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity", "time": round(start + dur, 3), "value": 100, "easeType": "linear"},
            {"layerName": "Adjustment_Flash", "propertyName": "Opacity", "time": round(start, 3), "value": 0, "easeType": "linear"},
            {"layerName": "Adjustment_Flash", "propertyName": "Opacity", "time": round(start + half, 3), "value": 100, "easeType": "linear"},
            {"layerName": "Adjustment_Flash", "propertyName": "Opacity", "time": round(start + dur, 3), "value": 0, "easeType": "linear"},
        ]

    def _scale_up_keyframes(self, from_layer: str, to_layer: str, start: float, dur: float) -> List[Dict]:
        return [
            {"layerName": from_layer, "propertyName": "Scale", "time": round(start, 3),
             "value": [100, 100], "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Scale", "time": round(start + dur, 3),
             "value": [150, 150], "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Opacity", "time": round(start, 3),
             "value": 100, "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Opacity", "time": round(start + dur, 3),
             "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Scale", "time": round(start, 3),
             "value": [150, 150], "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Scale", "time": round(start + dur, 3),
             "value": [100, 100], "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity", "time": round(start, 3),
             "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity", "time": round(start + dur, 3),
             "value": 100, "easeType": "linear"},
        ]

    def _page_turn_keyframes(self, from_layer: str, to_layer: str, start: float, dur: float) -> List[Dict]:
        return self._crossfade_keyframes(from_layer, to_layer, start, dur)

    def to_planning_result(self) -> Dict:
        keyframes = []
        layers = []
        effects = []

        for scene in self.scenes:
            layers.append({
                "name": scene.layer_name,
                "type": "footage",
                "startTime": round(scene.start_time, 3),
                "duration": round(scene.duration, 3),
                "width": self.comp_width,
                "height": self.comp_height,
            })

            for effect in scene.effects:
                effect_copy = dict(effect)
                effect_copy["layerName"] = scene.layer_name
                effects.append(effect_copy)

            for move in scene.camera_moves:
                camera_kfs = self.apply_camera_move(scene, move)
                keyframes.extend(camera_kfs)

        transition_kfs = self.generate_transition_keyframes()
        keyframes.extend(transition_kfs)

        transition_dicts = []
        for t in self.transitions:
            transition_dicts.append({
                "type": t.type,
                "duration": round(t.duration, 3),
                "startTime": round(t.start_time, 3),
                "fromScene": t.from_scene,
                "toScene": t.to_scene,
            })

        timeline = self.generate_timeline()

        execution_order = []
        for scene in self.scenes:
            execution_order.append(f"create_layer:{scene.layer_name}")
        for scene in self.scenes:
            for effect in scene.effects:
                execution_order.append(f"apply_effect:{scene.layer_name}:{effect.get('name', 'unknown')}")
        execution_order.append("apply_keyframes")
        execution_order.append("apply_transitions")

        return {
            "composition": {
                "width": self.comp_width,
                "height": self.comp_height,
                "fps": self.fps,
                "duration": round(self.total_duration, 3),
            },
            "layers": layers,
            "effects": effects,
            "keyframes": keyframes,
            "transitions": transition_dicts,
            "timeline": timeline,
            "execution_order": execution_order,
        }
