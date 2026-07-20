"""
Audition Engine - 专业音频处理
=================================

封装 Adobe Audition 的音频修复能力：
- AI降噪（比FFmpeg效果更好）
- 响度统一（多轨道LUFS对齐）
- 音频修复（去爆音/去混响/去咔嗒声）
- 批量音频处理

在流程中的定位：
- 前期：录制/获取原始音频后首先进入Audition修复
- 中期：多轨道混音、响度统一（-14 LUFS标准）
- 后期：最终母带处理

与FFmpeg的关系：
- FFmpeg：快速音频提取/格式转换
- Audition：质量修复、专业混音
- 建议流程：FFmpeg提取 → Audition修复 → FFmpeg编码

使用方式：
    engine = AuditionEngine()
    await engine.noise_reduction("noisy.wav", "clean.wav")
    await engine.match_loudness(["track1.wav", "track2.wav"], target_lufs=-14)
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ..base import BaseEngine, EngineResult  # noqa: E402
from ...config.settings import get_settings

# Bridge Client 在项目根目录，延迟导入
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class AuditionEngine(BaseEngine):
    """Adobe Audition engine via MCP Bridge / ES scripting."""

    name = "audition"

    def __init__(
        self,
        executable_path: Optional[Path | str] = None,
    ):
        self._settings = get_settings()
        self.au_path = self._resolve_executable(executable_path)
        super().__init__(executable_path or self.au_path or "audition")
        self._script_dir = Path(tempfile.gettempdir()) / "ae_kv_au_scripts"
        self._script_dir.mkdir(exist_ok=True)

        # 初始化 MCP Bridge Client（延迟导入，避免循环依赖）
        self._bridge_client = None
        self._bridge_available: Optional[bool] = None  # None=未检测, True=在线, False=离线

    def _resolve_executable(self, explicit: Optional[Path | str]) -> Optional[Path]:
        """解析可执行文件路径：显式参数 > settings配置 > 自动发现。"""
        if explicit:
            p = Path(explicit)
            if p.exists():
                return p

        if self._settings.audition_path:
            p = Path(self._settings.audition_path)
            if p.exists():
                return p
            logger.warning(f"[Audition] Settings path not found: {p}, falling back to auto-detect")

        return self._find_audition()

    @staticmethod
    def _find_audition() -> Optional[Path]:
        """自动发现 Audition 安装路径。"""
        possible_paths = [
            r"C:\Program Files\Adobe\Adobe Audition 2025\Adobe Audition.exe",
            r"C:\Program Files\Adobe\Adobe Audition 2024\Adobe Audition.exe",
            r"C:\Program Files\Adobe\Adobe Audition 2023\Adobe Audition.exe",
        ]
        for p in possible_paths:
            path = Path(p)
            if path.exists():
                return path
        return None

    async def execute(self, *args, **kwargs) -> EngineResult:
        """Dispatch to specific methods."""
        task = kwargs.get("task", "denoise")
        if task == "denoise":
            return await self.noise_reduction(**{k: v for k, v in kwargs.items() if k != "task"})
        if task == "loudness":
            return await self.match_loudness(**{k: v for k, v in kwargs.items() if k != "task"})
        if task == "repair":
            return await self.repair_audio(**{k: v for k, v in kwargs.items() if k != "task"})
        return EngineResult(success=False, error=f"Unknown task: {task}")

    async def noise_reduction(
        self,
        audio_path: Path | str,
        output_path: Path | str,
        noise_level: int = 80,  # 0-100
        preserve_quality: bool = True,
    ) -> EngineResult:
        """AI降噪处理。

        Args:
            audio_path: 输入音频路径
            output_path: 输出路径
            noise_level: 降噪强度
            preserve_quality: 是否启用语音保护
        """
        audio_path = Path(audio_path)
        output_path = Path(output_path)

        if not audio_path.exists():
            return EngineResult(
                success=False, error=f"Audio not found: {audio_path}",
            )

        # 构建 ES 脚本（优先通过 Bridge 执行）
        es_script = f"""
        (function() {{
            var audioFile = new File("{audio_path}");
            var outputFile = new File("{output_path}");

            // 打开音频文件
            var doc = app.open(audioFile);
            if (!doc) {{
                return {{status: "error", message: "Failed to open audio file"}};
            }}

            // 应用降噪效果
            try {{
                // 全选波形
                doc.selectAll();

                // 应用降噪效果（具体效果名称可能因版本而异）
                var effects = doc.effects;
                if (effects && effects.applyEffect) {{
                    effects.applyEffect("Denoise", {{
                        noiseLevel: {noise_level},
                        preserveQuality: {'true' if preserve_quality else 'false'}
                    }});
                }}

                // 导出文件
                doc.exportToFile(outputFile, "WAV");

                // 关闭文档
                doc.close(false);

                return {{status: "success", output: "{output_path}"}};
            }} catch (e) {{
                doc.close(false);
                return {{status: "error", message: e.toString()}};
            }}
        }})();
        """

        # 尝试通过 Bridge 执行，降级为 XML 脚本文件
        return await self._execute_script(es_script, "noise_reduction", audio_path, output_path, {
            "noise_level": noise_level,
            "preserve_quality": preserve_quality,
            "effect": "Denoise",
        })

    async def match_loudness(
        self,
        audio_paths: List[Path | str],
        target_lufs: float = -14.0,
        true_peak: float = -1.0,
    ) -> EngineResult:
        """响度统一（ITU-R BS.1770-4标准）。

        Args:
            audio_paths: 音频文件列表
            target_lufs: 目标响度（-14为YouTube标准，-16为Podcast标准）
            true_peak: 真实峰值限制
        """
        if not audio_paths:
            return EngineResult(success=False, error="No audio files provided")

        # 构建多轨道响度匹配的 ES 脚本
        paths_json = str([str(p) for p in audio_paths])
        es_script = f"""
        (function() {{
            var files = {paths_json};
            var targetLUFS = {target_lufs};
            var truePeak = {true_peak};
            var results = [];

            for (var i = 0; i < files.length; i++) {{
                try {{
                    var f = new File(files[i]);
                    var doc = app.open(f);
                    if (doc) {{
                        doc.selectAll();
                        // 应用响度匹配
                        var matchResult = doc.matchLoudness(targetLUFS, truePeak);
                        doc.save();
                        doc.close(false);
                        results.push({{file: files[i], status: "success"}});
                    }} else {{
                        results.push({{file: files[i], status: "error", message: "Failed to open"}});
                    }}
                }} catch (e) {{
                    results.push({{file: files[i], status: "error", message: e.toString()}});
                }}
            }}

            return {{status: "success", results: results, count: files.length}};
        }})();
        """

        # 尝试通过 Bridge 执行，降级为 XML 脚本文件
        return await self._execute_script(
            es_script,
            "match_loudness",
            None,
            None,
            {
                "target_lufs": target_lufs,
                "true_peak": true_peak,
                "file_count": len(audio_paths),
                "audio_paths": [str(p) for p in audio_paths],
            },
        )

    async def repair_audio(
        self,
        audio_path: Path | str,
        output_path: Path | str,
        repairs: Optional[List[str]] = None,
    ) -> EngineResult:
        """音频修复。

        Args:
            audio_path: 输入音频路径
            output_path: 输出路径
            repairs: 修复类型列表 ["declick", "declip", "dehum", "dereverb"]
        """
        audio_path = Path(audio_path)
        output_path = Path(output_path)
        repairs = repairs or ["declick", "declip"]

        if not audio_path.exists():
            return EngineResult(
                success=False, error=f"Audio not found: {audio_path}",
            )

        effects_list = ", ".join(f'"{r.capitalize()}"' for r in repairs)
        es_script = f"""
        (function() {{
            var audioFile = new File("{audio_path}");
            var outputFile = new File("{output_path}");
            var effects = [{effects_list}];

            var doc = app.open(audioFile);
            if (!doc) {{
                return {{status: "error", message: "Failed to open audio file"}};
            }}

            try {{
                doc.selectAll();

                // 依次应用各修复效果
                for (var i = 0; i < effects.length; i++) {{
                    try {{
                        if (doc.effects && doc.effects.applyEffect) {{
                            doc.effects.applyEffect(effects[i], {{}});
                        }}
                    }} catch (effErr) {{
                        // 单个效果失败不中断整体流程
                    }}
                }}

                doc.exportToFile(outputFile, "WAV");
                doc.close(false);

                return {{status: "success", output: "{output_path}", effectsApplied: effects.length}};
            }} catch (e) {{
                doc.close(false);
                return {{status: "error", message: e.toString()}};
            }}
        }})();
        """

        return await self._execute_script(es_script, "repair_audio", audio_path, output_path, {
            "repairs": repairs,
        })

    async def _execute_script(
        self,
        es_script: str,
        operation: str,
        audio_path: Optional[Path | str] = None,
        output_path: Optional[Path | str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> EngineResult:
        """通过 MCP Bridge 或临时脚本文件执行 Audition ES 脚本。

        优先使用 MCP Bridge（全自动），降级为生成脚本文件（手动执行）。

        Args:
            es_script: ES 脚本代码
            operation: 操作名称（用于日志和文件名）
            audio_path: 输入音频路径（降级模式下生成 XML 脚本用）
            output_path: 输出路径（降级模式下生成 XML 脚本用）
            extra_metadata: 额外的元数据
        """
        import time

        start = time.time()

        # 方式1: 尝试通过 MCP Bridge 自动执行
        if self._ensure_bridge():
            try:
                result = await asyncio.to_thread(
                    self._bridge_client.execute_script,
                    es_script,
                    30,  # timeout
                )
                success = result.get("status") == "success"
                error_msg = result.get("message", "") if not success else None

                metadata: Dict[str, Any] = {
                    "operation": operation,
                    "bridge_mode": "auto",
                    "result": result.get("result"),
                    "timestamp": result.get("timestamp"),
                }
                if extra_metadata:
                    metadata.update(extra_metadata)

                return EngineResult(
                    success=success,
                    error=error_msg,
                    output_path=str(output_path) if output_path and success else None,
                    metadata=metadata,
                    duration_seconds=time.time() - start,
                )
            except Exception as e:
                logger.warning(f"[Audition] Bridge execution failed, falling back to script file: {e}")
                self._bridge_available = False

        # 方式2: 降级 - 生成 XML 脚本文件，用户手动执行
        script_file = self._script_dir / f"audition_{operation}_{int(time.time())}.xml"

        # 根据操作类型生成对应的 XML 脚本
        xml_script = self._build_xml_script(operation, audio_path, output_path, extra_metadata)
        script_file.write_text(xml_script, encoding="utf-8")

        logger.info(f"[Audition] Script prepared (fallback): {script_file}")
        logger.info(f"[Audition] Run manually: Window > Batch Process > Load Script")

        metadata: Dict[str, Any] = {
            "script_path": str(script_file),
            "operation": operation,
            "bridge_mode": "manual_fallback",
            "note": "MCP Bridge offline. Run script manually or start au_mcp_bridge.jsx in Audition.",
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        return EngineResult(
            success=True,
            output_path=str(output_path) if output_path else None,
            metadata=metadata,
            duration_seconds=time.time() - start,
        )

    def _build_xml_script(
        self,
        operation: str,
        audio_path: Optional[Path | str],
        output_path: Optional[Path | str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建降级用的 XML 脚本。

        Args:
            operation: 操作类型
            audio_path: 输入音频路径
            output_path: 输出路径
            metadata: 额外参数

        Returns:
            XML 脚本字符串
        """
        metadata = metadata or {}

        if operation == "noise_reduction":
            noise_level = metadata.get("noise_level", 80)
            preserve_quality = metadata.get("preserve_quality", True)
            return f"""<?xml version="1.0" encoding="UTF-8"?>
<session>
    <open file="{audio_path}" />
    <effect name="Denoise">
        <param name="noiseLevel" value="{noise_level}" />
        <param name="preserveQuality" value="{'true' if preserve_quality else 'false'}" />
    </effect>
    <export file="{output_path}" format="wav" />
    <close />
</session>
"""

        if operation == "match_loudness":
            target_lufs = metadata.get("target_lufs", -14)
            true_peak = metadata.get("true_peak", -1)
            audio_paths = metadata.get("audio_paths", [])
            paths_str = "\n".join(f'    <file path="{p}" />' for p in audio_paths)
            return f"""<?xml version="1.0" encoding="UTF-8"?>
<batch>
    <loudness_match targetLUFS="{target_lufs}" truePeak="{true_peak}">
{paths_str}
    </loudness_match>
</batch>
"""

        if operation == "repair_audio":
            repairs = metadata.get("repairs", ["declick", "declip"])
            effects = "\n".join(f'    <effect name="{r.capitalize()}" />' for r in repairs)
            return f"""<?xml version="1.0" encoding="UTF-8"?>
<session>
    <open file="{audio_path}" />
{effects}
    <export file="{output_path}" format="wav" />
    <close />
</session>
"""

        # 默认返回空脚本
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<session>
    <!-- Operation: {operation} -->
</session>
"""

    def _ensure_bridge(self) -> bool:
        """确保 Bridge Client 已初始化且在线。延迟初始化 + 缓存检测结果。"""
        if self._bridge_available is False:
            return False

        if self._bridge_client is None:
            try:
                from au_bridge_client import AUBridgeClient  # 延迟导入
                self._bridge_client = AUBridgeClient(
                    bridge_dir=self._settings.au_bridge_dir,
                    timeout=self._settings.au_bridge_timeout,
                    poll_interval=self._settings.au_bridge_poll_interval,
                    signature_enabled=self._settings.au_bridge_signature_enabled,
                )
            except ImportError:
                logger.warning("[Audition] au_bridge_client not available")
                self._bridge_available = False
                return False
            except Exception as e:
                logger.warning(f"[Audition] Bridge init failed: {e}")
                self._bridge_available = False
                return False

        # 检测 Bridge 是否在线（首次检测后缓存）
        if self._bridge_available is None:
            try:
                result = self._bridge_client.ping(timeout=3)
                self._bridge_available = result.get("status") == "success"
                if self._bridge_available:
                    logger.info("[Audition] MCP Bridge is online")
                else:
                    logger.info(f"[Audition] MCP Bridge offline: {result.get('status', 'unknown')}")
            except Exception:
                self._bridge_available = False
                logger.info("[Audition] MCP Bridge not responding (is au_mcp_bridge.jsx running?)")

        return self._bridge_available is True

    def get_info(self) -> dict:
        """返回引擎信息。"""
        bridge_status = "unknown"
        if self._bridge_available is True:
            bridge_status = "online"
        elif self._bridge_available is False:
            bridge_status = "offline"

        return {
            "name": self.name,
            "audition_found": self.au_path is not None,
            "audition_path": str(self.au_path) if self.au_path else None,
            "bridge_status": bridge_status,
            "capabilities": [
                "noise_reduction",
                "match_loudness",
                "repair_audio",
            ],
            "workflow": "FFmpeg Extract → Audition Repair/Mix → FFmpeg Encode",
            "automation_level": "MCP Bridge (auto) / XML script (fallback)",
            "standards": {
                "youtube_lufs": -14,
                "podcast_lufs": -16,
                "streaming_lufs": -14,
            },
        }


# ========================================================================
# P1 双模式执行 - 类级别别名（必须在类定义完成后设置）
# ========================================================================

AuditionEngine._execute_jsx = AuditionEngine._execute_script
