import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict

from ae_bridge_base import AEBridgeClient

from core.config import ConfigManager

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
SECRET_FILE = os.path.join(os.path.dirname(__file__), ".ae-mcp-bridge", ".mcp_secret")

_config = ConfigManager()
_DEFAULT_FRAME_DIR = _config.get("media_library.frames_dir", "D:/AE-Work/视频素材库/frames")


def _escape_jsx_string(value: str) -> str:
    """安全转义 JSX/ExtendScript 字符串，防止脚本注入。

    转义规则：
    - 反斜杠 -> \\\\
    - 双引号 -> \\\"
    - 单引号 -> \\\\'
    - 换行 -> \\n
    - 回车 -> \\r
    - 制表符 -> \\t
    - 其他控制字符 -> \\xHH

    Args:
        value: 原始字符串

    Returns:
        可安全嵌入 JSX 双引号字符串中的转义后文本
    """
    if value is None:
        return ""

    result = []
    for ch in value:
        if ch == '\\':
            result.append('\\\\')
        elif ch == '"':
            result.append('\\"')
        elif ch == "'":
            result.append("\\'")
        elif ch == '\n':
            result.append('\\n')
        elif ch == '\r':
            result.append('\\r')
        elif ch == '\t':
            result.append('\\t')
        elif ord(ch) < 0x20:
            result.append(f'\\x{ord(ch):02x}')
        else:
            result.append(ch)
    return ''.join(result)


class AECommandClient(AEBridgeClient):
    """AE 命令客户端（op/params 协议）。

    继承 AEBridgeClient 的文件交换、签名、轮询逻辑，
    仅实现 op/params 命令结构与 config/mcp_secret 密钥加载。
    """

    def __init__(
        self,
        command_file: str = None,
        result_file: str = None,
        timeout: int = 10,
        poll_interval: float = 0.5,
        signature_enabled: bool = True
    ):
        super().__init__(
            command_file=command_file or os.path.join(
                os.path.dirname(__file__), ".ae-mcp-bridge", "ae_command.json"
            ),
            result_file=result_file or os.path.join(
                os.path.dirname(__file__), ".ae-mcp-bridge", "ae_result.json"
            ),
            timeout=timeout,
            poll_interval=poll_interval,
            signature_enabled=signature_enabled,
        )

    def _load_secret(self) -> str:
        if os.path.exists(SECRET_FILE):
            try:
                with open(SECRET_FILE, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except OSError:
                return ""
        return ""

    def _canonical_json(self, data: dict[str, Any]) -> str:
        return json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False)

    def send_command(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        self.clear_result()

        command = {
            "command": op,
            "args": params,
            "status": "pending",
            "timestamp": datetime.now().isoformat(),
            "signature": ""
        }

        if self.signature_enabled and self.secret:
            sign_data = {k: v for k, v in command.items() if k != "signature" and k != "signature_alg"}
            command["signature"] = self._generate_signature(sign_data)

        self._write_command_file(command)
        return self._wait_for_result()

    def send_batch_commands(self, commands: list) -> list:
        results = []
        for cmd in commands:
            op = cmd.get("op", "")
            params = cmd.get("params", {})
            result = self.send_command(op, params)
            results.append(result)
            self.clear_result()
        return results

    def set_keyframe_batch(
        self,
        comp_name: str,
        layer_name: str,
        keyframes: list,
        expressions: dict = None,
    ) -> dict[str, Any]:
        """批量写入关键帧到指定图层。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            keyframes: 关键帧列表，每项为 dict:
                - property (str): 属性名如 "Scale", "Opacity"
                - time (float): 时间（秒）
                - value: 属性值
                - easeType (str): "linear"/"easeIn"/"easeOut"/"easeInOut"
            expressions: 表达式映射 dict {属性名: 表达式字符串}

        Returns:
            {"written": N, "failed": M, "total": T, ...}
        """
        params = {
            "compName": comp_name,
            "layerName": layer_name,
            "keyframes": keyframes,
            "expressions": expressions or {},
        }
        return self.send_command("setKeyframeBatch", params)

    def create_e2e_music_video(
        self,
        bgm_path: str = None,
        frame_dir: str = _DEFAULT_FRAME_DIR,
        comp_name: str = "E2E_音乐视频",
        width: int = 576,
        height: int = 768,
        duration: float = 12,
        fps: int = 30,
        beat_times: list = None,
        energy_peaks: list = None,
        peak_values: list = None,
        bpm: float = 120,
    ) -> dict[str, Any]:
        """一键创建音乐同步AE合成。

        内部调用 e2eMusicVideo MCP命令，在AE端一次性完成：
        帧序列导入 → 主体/披风层 → 粒子系统 → 背景大气 → 调色 →
        节拍同步摄像机 → 能量峰值同步粒子 → BGM导入 → 层排序

        Args:
            bgm_path: BGM音频文件路径
            frame_dir: 帧序列目录路径
            comp_name: 合成名称
            width/height: 合成尺寸
            duration: 合成时长（秒）
            fps: 帧率
            beat_times: 节拍时间点列表（秒）
            energy_peaks: 能量峰值时间点列表（秒）
            peak_values: 能量峰值数值列表
            bpm: 节拍速度

        Returns:
            MCP命令执行结果
        """
        old_timeout = self.timeout
        self.timeout = 120
        try:
            params = {
                "compName": comp_name,
                "frameDir": frame_dir,
                "bgmPath": bgm_path or "",
                "beatTimes": beat_times or [],
                "energyPeaks": energy_peaks or [],
                "peakValues": peak_values or [],
                "bpm": bpm,
                "width": width,
                "height": height,
                "duration": duration,
                "fps": fps,
            }
            return self.send_command("e2eMusicVideo", params)
        finally:
            self.timeout = old_timeout

    def create_e2e_music_video_auto(
        self,
        bgm_path: str,
        frame_dir: str = _DEFAULT_FRAME_DIR,
        comp_name: str = "E2E_音乐视频",
        width: int = 576,
        height: int = 768,
        duration: float = 12,
        fps: int = 30,
    ) -> dict[str, Any]:
        """自动分析BGM并创建音乐同步AE合成（全自动）。

        在Python端用librosa分析BGM，然后将节拍/能量数据
        发送给AE端的 e2eMusicVideo 命令执行。

        Args:
            bgm_path: BGM音频文件路径（必填）
            frame_dir: 帧序列目录路径
            comp_name: 合成名称
            width/height: 合成尺寸
            duration: 合成时长（秒）
            fps: 帧率

        Returns:
            MCP命令执行结果（包含 bpm, beatKeyframes, energyPeaks 等）
        """
        import librosa
        import numpy as np

        y, sr = librosa.load(bgm_path, sr=44100, mono=True, duration=duration)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
        bpm = float(tempo.item()) if hasattr(tempo, 'item') else float(tempo)

        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=512)
        energy_avg = float(np.mean(rms))
        peak_thresh = energy_avg * 1.5

        energy_peaks = []
        peak_values = []
        for i in range(1, len(rms) - 1):
            if rms[i] > peak_thresh and rms[i] > rms[i-1] and rms[i] > rms[i+1]:
                energy_peaks.append(float(times[i]))
                peak_values.append(float(rms[i]))

        return self.create_e2e_music_video(
            bgm_path=bgm_path,
            frame_dir=frame_dir,
            comp_name=comp_name,
            width=width,
            height=height,
            duration=duration,
            fps=fps,
            beat_times=[round(float(t), 3) for t in beat_times],
            energy_peaks=[round(float(t), 3) for t in energy_peaks],
            peak_values=[round(float(v), 4) for v in peak_values],
            bpm=round(bpm, 1),
        )

    def create_e2e_music_video_with_silhouette(
        self,
        bgm_path: str = None,
        frame_dir: str = _DEFAULT_FRAME_DIR,
        comp_name: str = "E2E_音乐视频",
        width: int = 576,
        height: int = 768,
        duration: float = 12,
        fps: int = 30,
        beat_times: list = None,
        energy_peaks: list = None,
        peak_values: list = None,
        bpm: float = 120,
        matte_path: str = "D:/AE-Work/silhouette_output/matte_[####].exr",
    ) -> dict[str, Any]:
        """创建音乐同步AE合成（使用Silhouette Roto Matte）。

        先调用Silhouette生成Roto遮罩，然后创建AE合成并应用Matte。

        Args:
            matte_path: Silhouette生成的Matte序列路径
            其他参数同 create_e2e_music_video
        """
        old_timeout = self.timeout
        self.timeout = 120
        try:
            params = {
                "compName": comp_name,
                "frameDir": frame_dir,
                "bgmPath": bgm_path or "",
                "beatTimes": beat_times or [],
                "energyPeaks": energy_peaks or [],
                "peakValues": peak_values or [],
                "bpm": bpm,
                "width": width,
                "height": height,
                "duration": duration,
                "fps": fps,
                "mattePath": matte_path,
            }
            return self.send_command("e2eMusicVideo", params)
        finally:
            self.timeout = old_timeout

    def run_silhouette_roto(
        self,
        source_path: str,
        output_path: str = None,
        shape_type: str = "x-spline",
        tolerance: float = 1.0,
        keyframes: int = 5,
        preset: str = "standard_keying",
        mode: str = "real",
        tracking: str = None,
        output_format: str = "exr",
    ) -> dict[str, Any]:
        """调用Silhouette生成Roto遮罩（真实模式：自动启动Silhouette应用并渲染输出）。

        Args:
            source_path: 输入视频/图片路径
            output_path: 输出Matte序列路径（可选，默认EXR序列）
            shape_type: 形状类型 "x-spline" | "bezier"
            tolerance: 边缘容差
            keyframes: 关键帧间隔（帧）
            preset: 预设配置 "standard_keying" | "hair_keying" | "hard_edge_keying"
            mode: 执行模式 "real" | "auto" | "simulate"（默认real，自动启动Silhouette）
            tracking: 跟踪驱动的Roto（可选）
            output_format: 输出格式 "exr" | "png" | "tiff" | "dpx"

        Returns:
            Silhouette执行结果，包含真实Matte序列路径
        """
        from silhouette_executor import execute_silhouette_command
        return execute_silhouette_command(
            "silhouette_roto",
            mode=mode,
            source_path=source_path,
            output_path=output_path,
            shape_type=shape_type,
            tolerance=tolerance,
            keyframes=keyframes,
            preset=preset,
            tracking=tracking,
            output_format=output_format,
        )

    def run_silhouette_track(
        self,
        source_path: str,
        track_type: str = "planar",
        export_format: str = "ae",
        preset: str = "planar_track",
        mode: str = "real",
        search_area: int = None,
        accuracy: str = None,
        output_path: str = None,
    ) -> dict[str, Any]:
        """调用Silhouette执行跟踪（真实模式：自动启动Silhouette应用）。

        Args:
            source_path: 输入视频路径
            track_type: 跟踪类型 "planar" | "point" | "paint"
            export_format: 导出格式 "ae" | "json" | "csv"
            preset: 预设配置 "planar_track" | "high_precision_track" | "fast_track"
            mode: 执行模式 "real" | "auto" | "simulate"（默认real）
            search_area: 搜索区域大小（可选，覆盖预设）
            accuracy: 跟踪精度 "low" | "medium" | "high"（可选，覆盖预设）
            output_path: 跟踪数据输出路径（可选）

        Returns:
            Silhouette执行结果，包含跟踪数据
        """
        from silhouette_executor import execute_silhouette_command
        params = dict(
            mode=mode,
            source_path=source_path,
            track_type=track_type,
            export_format=export_format,
            preset=preset,
        )
        if search_area is not None:
            params["search_area"] = search_area
        if accuracy is not None:
            params["accuracy"] = accuracy
        if output_path is not None:
            params["output_path"] = output_path
        return execute_silhouette_command("silhouette_track", **params)

    def run_silhouette_paint(
        self,
        source_path: str,
        paint_mode: str = "clone",
        brush_size: int = 25,
        brush_hardness: float = None,
        preset: str = "clone_repair",
        exec_mode: str = "real",
        output_path: str = None,
    ) -> dict[str, Any]:
        """调用Silhouette执行Paint修复（真实模式：自动启动Silhouette应用并渲染输出）。

        Args:
            source_path: 输入路径
            paint_mode: 模式 "clone" | "repair" | "erase"
            brush_size: 笔刷大小
            brush_hardness: 笔刷硬度 0.0-1.0（可选，覆盖预设）
            preset: 预设配置 "clone_repair" | "smart_repair"
            exec_mode: 执行模式 "real" | "auto" | "simulate"（默认real）
            output_path: 输出路径（可选）

        Returns:
            Silhouette执行结果，包含修复后的帧序列
        """
        from silhouette_executor import execute_silhouette_command
        params = dict(
            mode=exec_mode,
            source_path=source_path,
            paint_mode=paint_mode,
            brush_size=brush_size,
            preset=preset,
        )
        if brush_hardness is not None:
            params["brush_hardness"] = brush_hardness
        if output_path is not None:
            params["output_path"] = output_path
        return execute_silhouette_command("silhouette_paint", **params)

    def run_silhouette_hair_keying(self, source_path: str, output_path: str = None) -> dict[str, Any]:
        """使用毛发抠像预设执行Roto。"""
        return self.run_silhouette_roto(source_path, output_path, preset="hair_keying")

    def run_silhouette_high_precision_track(self, source_path: str) -> dict[str, Any]:
        """使用高精度跟踪预设执行跟踪。"""
        return self.run_silhouette_track(source_path, preset="high_precision_track")

    def run_silhouette_smart_repair(self, source_path: str) -> dict[str, Any]:
        """使用智能修复预设执行Paint修复。"""
        return self.run_silhouette_paint(source_path, preset="smart_repair")

    def silhouette_roto_to_ae(
        self,
        source_path: str,
        target_layer: str = None,
        preset: str = "standard_keying",
        mode: str = "real",
        matte_mode: str = "alpha",
        invert_matte: bool = False,
    ) -> dict[str, Any]:
        """完整工作流：Silhouette Roto 生成 Matte → 导入 AE → 设置 Track Matte。

        一键完成从素材到 AE 合成的完整 Roto 工作流：
        1. 调用 Silhouette 生成 Roto Matte 序列
        2. 将 Matte 序列导入 AE 项目
        3. 将 Matte 图层放到目标图层上方
        4. 设置 Track Matte 模式

        Args:
            source_path: 源素材路径（视频/图片/帧序列）
            target_layer: AE 中目标图层名称（None 表示选中图层）
            preset: Silhouette Roto 预设
            mode: 执行模式 "real" | "auto" | "simulate"
            matte_mode: Track Matte 模式 "alpha" | "luma" | "alpha_inverted" | "luma_inverted"
            invert_matte: 是否反转遮罩

        Returns:
            包含 Silhouette 结果和 AE 集成结果的字典
        """
        print(f"[Silhouette→AE] Starting Roto workflow: {preset}")
        print(f"[Silhouette→AE] Source: {source_path}")

        # 第一步：Silhouette 生成 Matte
        sil_result = self.run_silhouette_roto(
            source_path=source_path,
            preset=preset,
            mode=mode,
        )

        if sil_result.get("status") not in ("success", "pending_silhouette"):
            return {
                "status": "error",
                "stage": "silhouette_roto",
                "error": sil_result.get("error", "Silhouette Roto failed"),
                "silhouette_result": sil_result,
            }

        matte_path = sil_result.get("output_file")
        if not matte_path:
            matte_path = sil_result.get("expected_output", "")

        print(f"[Silhouette→AE] Matte generated: {matte_path}")

        # 第二步：导入 Matte 到 AE 并设置 Track Matte
        # 优先使用 applySilhouetteMatte 命令，如果AE端不支持则回退到 executeAtomScript
        try:
            ae_result = self.send_command("applySilhouetteMatte", {
                "mattePath": matte_path,
                "targetLayer": target_layer or "",
                "matteMode": matte_mode,
                "invertMatte": invert_matte,
                "preset": preset,
            })

            # 检查是否返回 Unknown command
            if ae_result.get("error", "").startswith("Unknown command"):
                print("[Silhouette→AE] applySilhouetteMatte not supported, falling back to executeAtomScript")
                ae_result = self._apply_matte_via_atom_script(matte_path, target_layer, matte_mode)
        except Exception as e:
            print(f"[Silhouette→AE] send_command failed ({e}), trying executeAtomScript")
            ae_result = self._apply_matte_via_atom_script(matte_path, target_layer, matte_mode)

        return {
            "status": "success" if ae_result.get("status") == "success" else "partial",
            "stage": "complete",
            "silhouette": sil_result,
            "ae_integration": ae_result,
            "matte_path": matte_path,
            "manual_steps": [
                f"1. Matte path: {matte_path}",
                "2. Import into AE as footage",
                "3. Place above target layer",
                f"4. Set Track Matte: {matte_mode}",
            ] if ae_result.get("status") != "success" else [],
        }

    def silhouette_track_to_ae(
        self,
        source_path: str,
        target_layer: str = None,
        track_type: str = "planar",
        preset: str = "planar_track",
        mode: str = "real",
        apply_to: str = "position",
    ) -> dict[str, Any]:
        """完整工作流：Silhouette 跟踪 → 导出数据 → 应用到 AE 图层。

        Args:
            source_path: 源素材路径
            target_layer: AE 目标图层名称（None 表示选中图层）
            track_type: 跟踪类型 "planar" | "point"
            preset: 跟踪预设
            mode: 执行模式 "real" | "auto" | "simulate"
            apply_to: 应用到属性 "position" | "anchor" | "scale" | "rotation"

        Returns:
            包含跟踪结果和 AE 应用结果的字典
        """
        print(f"[Silhouette→AE] Starting track workflow: {preset}")

        # 第一步：Silhouette 跟踪
        sil_result = self.run_silhouette_track(
            source_path=source_path,
            track_type=track_type,
            preset=preset,
            mode=mode,
        )

        if sil_result.get("status") not in ("success", "pending_silhouette"):
            return {
                "status": "error",
                "stage": "silhouette_track",
                "error": sil_result.get("error", "Silhouette Track failed"),
                "silhouette_result": sil_result,
            }

        tracking_data_path = sil_result.get("output_file") or ""
        print(f"[Silhouette→AE] Tracking data: {tracking_data_path}")

        # 第二步：应用到 AE 图层
        try:
            ae_result = self.send_command("applySilhouetteTracking", {
                "trackingDataPath": tracking_data_path,
                "targetLayer": target_layer or "",
                "trackType": track_type,
                "applyTo": apply_to,
            })
            if ae_result.get("error", "").startswith("Unknown command"):
                print("[Silhouette→AE] applySilhouetteTracking not supported, using executeAtomScript")
                ae_result = self._apply_tracking_via_atom_script(tracking_data_path, target_layer, apply_to)
        except Exception as e:
            print(f"[Silhouette→AE] send_command failed ({e}), trying executeAtomScript")
            ae_result = self._apply_tracking_via_atom_script(tracking_data_path, target_layer, apply_to)

        return {
            "status": "success" if ae_result.get("status") == "success" else "partial",
            "stage": "complete",
            "silhouette": sil_result,
            "ae_integration": ae_result,
            "tracking_data_path": tracking_data_path,
        }

    def silhouette_paint_to_ae(
        self,
        source_path: str,
        target_layer: str = None,
        paint_mode: str = "clone",
        preset: str = "clone_repair",
        mode: str = "real",
    ) -> dict[str, Any]:
        """完整工作流：Silhouette Paint 修复 → 导入 AE 合成。

        Args:
            source_path: 源素材路径
            target_layer: AE 目标图层名称
            paint_mode: Paint 模式 "clone" | "repair" | "erase"
            preset: Paint 预设
            mode: 执行模式 "real" | "auto" | "simulate"

        Returns:
            包含 Paint 结果和 AE 集成结果的字典
        """
        print(f"[Silhouette→AE] Starting paint workflow: {preset}")

        # 第一步：Silhouette Paint
        sil_result = self.run_silhouette_paint(
            source_path=source_path,
            paint_mode=paint_mode,
            preset=preset,
            exec_mode=mode,
        )

        if sil_result.get("status") not in ("success", "pending_silhouette"):
            return {
                "status": "error",
                "stage": "silhouette_paint",
                "error": sil_result.get("error", "Silhouette Paint failed"),
                "silhouette_result": sil_result,
            }

        paint_output = sil_result.get("output_file") or ""
        print(f"[Silhouette→AE] Paint output: {paint_output}")

        # 第二步：导入 AE
        try:
            ae_result = self.send_command("importSilhouettePaint", {
                "paintPath": paint_output,
                "targetLayer": target_layer or "",
                "paintMode": paint_mode,
            })
            if ae_result.get("error", "").startswith("Unknown command"):
                print("[Silhouette→AE] importSilhouettePaint not supported, using importFootage")
                ae_result = self.import_footage_to_ae(paint_output, as_sequence=True)
        except Exception as e:
            print(f"[Silhouette→AE] send_command failed ({e}), trying importFootage")
            ae_result = self.import_footage_to_ae(paint_output, as_sequence=True)

        return {
            "status": "success" if ae_result.get("status") == "success" else "partial",
            "stage": "complete",
            "silhouette": sil_result,
            "ae_integration": ae_result,
            "paint_output": paint_output,
        }

    def _apply_matte_via_atom_script(self, matte_path: str, target_layer: str, matte_mode: str, comp_name: str = None) -> dict[str, Any]:
        """通过 executeAtomScript 命令导入 Matte 并设置 Track Matte（兼容旧版 AE bridge）。

        Args:
            matte_path: Matte 序列路径（支持 [####]、.####、%04d 格式）
            target_layer: 目标图层名称
            matte_mode: Track Matte 模式
            comp_name: 目标合成名称（None 则使用第一个找到的合成）
        """
        import os
        # 将路径中的 [####]、.####、%04d 替换为 0001，并将反斜杠转为正斜杠
        ae_path = matte_path.replace("[####]", "0001").replace(".####.", ".0001.").replace("%04d", "0001")
        ae_path = ae_path.replace("\\", "/")
        ae_path_jsx = _escape_jsx_string(ae_path)

        # TrackMatteType 枚举值（AE 实际数值，非标准文档值）
        matte_map_jsx = {
            "alpha": "5013",          # TrackMatteType.ALPHA
            "luma": "5015",           # TrackMatteType.LUMA
            "alpha_inverted": "5014", # TrackMatteType.ALPHA_INVERTED
            "luma_inverted": "5016",  # TrackMatteType.LUMA_INVERTED
        }
        matte_type_jsx = matte_map_jsx.get(matte_mode, "5013")  # 默认 ALPHA
        matte_mode_safe = _escape_jsx_string(matte_mode or "alpha")

        # 构建合成查找代码
        if comp_name:
            comp_name_safe = _escape_jsx_string(comp_name)
            comp_jsx = (
                f'var comp = null;\n'
                f'            for (var i=1; i<=app.project.numItems; i++) {{\n'
                f'                if (app.project.item(i) instanceof CompItem && app.project.item(i).name == "{comp_name_safe}") {{\n'
                f'                    comp = app.project.item(i); break;\n'
                f'                }}\n'
                f'            }}'
            )
        else:
            comp_jsx = (
                'var comp = app.project.activeItem;\n'
                '            if (!(comp instanceof CompItem)) {\n'
                '                for (var i=1; i<=app.project.numItems; i++) {\n'
                '                    if (app.project.item(i) instanceof CompItem) { comp = app.project.item(i); break; }\n'
                '                }\n'
                '            }'
            )

        # 构建目标图层查找代码
        if target_layer:
            target_layer_safe = _escape_jsx_string(target_layer)
            target_jsx = (
                f'var targetLayer = null;\n'
                f'                for (var j=1; j<=comp.numLayers; j++) {{\n'
                f'                    if (comp.layer(j).name == "{target_layer_safe}") {{\n'
                f'                        targetLayer = comp.layer(j); break;\n'
                f'                    }}\n'
                f'                }}\n'
                f'                if (!targetLayer) targetLayer = comp.layer(matteLayer.index + 1);'
            )
        else:
            target_jsx = "var targetLayer = comp.layer(matteLayer.index + 1);"

        # 构建 ExtendScript 代码（用函数包装确保访问全局枚举）
        jsx_code = (
            '(function() {\n'
            'var _result = {};\n'
            'try {\n'
            f'    var matteFile = new File("{ae_path_jsx}");\n'
            '    if (!matteFile.exists) {\n'
            '        var parent = matteFile.parent;\n'
            '        var pattern = matteFile.name.replace("0001", "*");\n'
            '        var files = parent.getFiles(pattern);\n'
            '        if (files.length > 0) matteFile = files[0];\n'
            '        else { _result = {status:"error",message:"Matte not found"}; }\n'
            '    }\n'
            '    if (!_result.status) {\n'
            '        var io = new ImportOptions(matteFile);\n'
            '        io.sequence = true;\n'
            '        var matteFootage = app.project.importFile(io);\n'
            f'        {comp_jsx}\n'
            '        if (!comp) { _result = {status:"error",message:"No comp found"}; }\n'
            '        else {\n'
            '            var matteLayer = comp.layers.add(matteFootage);\n'
            '            matteLayer.name = "Silhouette_Matte";\n'
            '            matteLayer.enabled = false;\n'
            '            matteLayer.moveToBeginning();\n'
            f'            {target_jsx}\n'
            f'            targetLayer.trackMatteType = {matte_type_jsx};\n'
            f'            _result = {{status:"success",matteLayer:matteLayer.name,targetLayer:targetLayer.name,matteMode:"{matte_mode_safe}",compName:comp.name}};\n'
            '        }\n'
            '    }\n'
            '} catch(e) {\n'
            '    _result = {status:"error",message:e.toString()};\n'
            '}\n'
            'return JSON.stringify(_result);\n'
            '})();\n'
        )
        try:
            return self.send_command("executeAtomScript", {"scriptContent": jsx_code})
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _apply_tracking_via_atom_script(self, tracking_data_path: str, target_layer: str, apply_to: str) -> dict[str, Any]:
        """通过 executeAtomScript 命令应用跟踪数据（兼容旧版 AE bridge）。"""
        VALID_APPLY_TO = {"position", "anchor"}
        if apply_to not in VALID_APPLY_TO:
            return {"status": "error", "error": f"Invalid apply_to value: {apply_to}. Valid: {VALID_APPLY_TO}"}

        try:
            with open(tracking_data_path, "r") as f:
                track_data = json.load(f)
        except Exception as e:
            return {"status": "error", "error": f"Cannot read tracking data: {e}"}

        trackers = track_data.get("trackers", [])
        fps = float(track_data.get("fps", 24.0))

        keyframes_jsx = ""
        for tracker in trackers:
            for frame_data in tracker.get("frames", []):
                frame_num = frame_data.get("frame", 0)
                x = frame_data.get("x", 0)
                y = frame_data.get("y", 0)
                try:
                    frame_num = int(frame_num)
                    x = float(x)
                    y = float(y)
                except (ValueError, TypeError):
                    return {"status": "error", "error": f"Invalid tracking data at frame {frame_num}"}
                time_val = frame_num / fps
                keyframes_jsx += f"prop.setValueAtTime({time_val}, [{x}, {y}]);\n"

        prop_map = {
            "position": 'property("ADBE Transform Group").property("ADBE Position")',
            "anchor": 'property("ADBE Transform Group").property("ADBE Anchor Point")',
        }
        prop_jsx = prop_map[apply_to]

        jsx_code = (
            '(function() {\n'
            'var _result = {};\n'
            'try {\n'
            '    var comp = app.project.activeItem;\n'
            '    if (!(comp instanceof CompItem)) {\n'
            '        for (var i=1; i<=app.project.numItems; i++) {\n'
            '            if (app.project.item(i) instanceof CompItem) { comp = app.project.item(i); break; }\n'
            '        }\n'
            '    }\n'
            '    if (!comp) { _result = {status:"error",message:"No comp found"}; }\n'
            '    else {\n'
            '        var targetLayer = comp.selectedLayers[0] || comp.layer(1);\n'
            '        if (!targetLayer) { _result = {status:"error",message:"No layer found"}; }\n'
            '        else {\n'
            f'            var prop = targetLayer.{prop_jsx};\n'
            f'            {keyframes_jsx}\n'
            '            _result = {status:"success",targetLayer:targetLayer.name,keyframes:' + str(len(trackers)) + '};\n'
            '        }\n'
            '    }\n'
            '} catch(e) {\n'
            '    _result = {status:"error",message:e.toString()};\n'
            '}\n'
            'return JSON.stringify(_result);\n'
            '})();\n'
        )
        try:
            return self.send_command("executeAtomScript", {"scriptContent": jsx_code})
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def import_footage_to_ae(
        self,
        file_path: str,
        name: str = None,
        as_sequence: bool = False,
    ) -> dict[str, Any]:
        """导入素材到 AE 项目。

        Args:
            file_path: 素材文件路径
            name: 项目面板中的名称（可选）
            as_sequence: 是否作为序列帧导入

        Returns:
            AE 导入结果
        """
        params = {
            "filePath": file_path,
            "name": name or "",
            "asSequence": as_sequence,
        }
        return self.send_command("importFootage", params)

    def set_track_matte(
        self,
        target_layer: str,
        matte_layer: str,
        matte_type: str = "alpha",
    ) -> dict[str, Any]:
        """设置 AE 图层的 Track Matte。

        Args:
            target_layer: 目标图层名称（被遮罩的图层）
            matte_layer: 遮罩图层名称
            matte_type: 遮罩类型 "alpha" | "luma" | "alpha_inverted" | "luma_inverted"

        Returns:
            AE 操作结果
        """
        params = {
            "targetLayer": target_layer,
            "matteLayer": matte_layer,
            "matteType": matte_type,
        }
        return self.send_command("setTrackMatte", params)
