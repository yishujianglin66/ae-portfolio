#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
integration_registry.py — 开源项目统一集成注册中心
====================================================

所有外部开源项目的统一注册、发现、健康检查入口。
五层架构中 Layer 1~5 的集成能力均通过此注册中心管理。

架构:
    integration_registry (统一注册)
    ├── Layer 1: adobe_mcp, comfyui, media_crawler, blender_proc, nexrender
    ├── Layer 2: firecrawl (数据收集服务)
    ├── Layer 3: opensource_integrations (RIFE/SAM2/Whisper/MoviePy)
    ├── Layer 4: firecrawl (Agent 联网增强)
    └── Layer 5: (semantica — 待集成)

使用:
    from integrations.integration_registry import IntegrationRegistry

    registry = IntegrationRegistry()
    registry.discover_all()      # 发现所有可用集成
    registry.health_check()      # 健康检查
    adapter = registry.get("adobe_mcp")  # 获取适配器
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class IntegrationStatus(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_INSTALLED = "not_installed"


class LayerLevel(int, Enum):
    L1_ENGINE = 1
    L2_SERVICE = 2
    L3_ORCHESTRATOR = 3
    L4_AGENT = 4
    L5_OBSERVABILITY = 5


@dataclass
class IntegrationInfo:
    """集成项目信息"""
    name: str
    display_name: str
    source_repo: str
    layer: LayerLevel
    status: IntegrationStatus = IntegrationStatus.NOT_INSTALLED
    adapter_class: Optional[str] = None
    adapter_instance: Optional[Any] = None
    operations_count: int = 0
    priority: str = "P2"  # P0/P1/P2
    description: str = ""
    defects_addressed: List[str] = field(default_factory=list)
    last_check: float = 0.0
    error: Optional[str] = None


class IntegrationRegistry:
    """开源项目统一集成注册中心"""

    # 所有已知集成项目的元数据
    KNOWN_INTEGRATIONS: Dict[str, Dict[str, Any]] = {
        # ── P0 ──────────────────────────────────────────────────────
        "adobe_mcp": {
            "display_name": "Adobe MCP (45工具/8应用)",
            "source_repo": "VoidChecksum/adobe-mcp",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P0",
            "adapter_module": "integrations.adobe_mcp_adapter",
            "adapter_class": "AdobeMCPAdapter",
            "description": "Adobe CC 全应用自动化 (PS/AI/PR/AE/ID/AN/AME/CH)",
            "defects_addressed": ["D-02", "D-04", "D-05", "D-06", "D-11", "D-12", "D-13", "D-14", "D-17R", "D-18", "D-19"],
        },
        "qwen_mm": {
            "display_name": "Qwen-MM (通义千问视觉)",
            "source_repo": "QwenLM/Qwen-MM-Plugins",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P0",
            "adapter_module": "integrations.qwen_mm_adapter",
            "adapter_class": "QwenMMAdapter",
            "description": "多模态视觉理解 (通过 DashScope API / qwen Provider)",
            "defects_addressed": ["D-01", "D-03", "D-15", "D-16"],
        },
        "resolve_mcp": {
            "display_name": "DaVinci Resolve MCP (28工具/双通道)",
            "source_repo": "samuelgursky/davinci-resolve-mcp",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P0",
            "adapter_module": "integrations.resolve_mcp_adapter",
            "adapter_class": "ResolveMCPAdapter",
            "description": "Resolve 自动化 (Python API + fuscript Lua 双通道降级)",
            "defects_addressed": ["D-05", "D-06", "D-11", "D-14"],
        },
        "auto_subs": {
            "display_name": "AutoSubs (字幕生成/faster-whisper)",
            "source_repo": "tmoroney/auto-subs",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P0",
            "adapter_module": "integrations.auto_subs_adapter",
            "adapter_class": "AutoSubsAdapter",
            "description": "AI 字幕生成 (faster-whisper 后端, SRT/VTT/TXT/JSON 输出)",
            "defects_addressed": ["D-05", "D-22"],
        },
        # ── P1 ──────────────────────────────────────────────────────
        "after_effects_mcp": {
            "display_name": "After Effects MCP",
            "source_repo": "Dakkshin/after-effects-mcp",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": None,  # 架构参考，功能已被 adobe_mcp 覆盖
            "adapter_class": None,
            "description": "AE MCP 参考实现 (架构设计参考)",
            "defects_addressed": ["D-02"],
        },
        "psd_tools": {
            "display_name": "psd-tools (PSD解析/1.4k★)",
            "source_repo": "psd-tools/psd-tools",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": "integrations.psd_tools_adapter",
            "adapter_class": "PsdToolsAdapter",
            "description": "PSD 文件解析/图层导出/文字提取/字体列表",
            "defects_addressed": ["D-03", "D-05"],
        },
        "dctl_presets": {
            "display_name": "DCTLs 色彩预设 (社区CTL变换)",
            "source_repo": "baldavenger/DCTLs",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": "integrations.dctl_preset_adapter",
            "adapter_class": "DCTLPresetAdapter",
            "description": "社区 CTL 色彩变换预设 (Demystify + MoazElgabry)",
            "defects_addressed": ["D-05", "D-11"],
        },
        "pr_mcp": {
            "display_name": "PR MCP 增强 (Premiere Pro 40+工具)",
            "source_repo": "hetpatel-11/AdobePremiereProMCP",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": "integrations.pr_mcp_adapter",
            "adapter_class": "PRMCPAdapter",
            "description": "PR 专用增强适配器 (Bridge + Adobe MCP + ExtendScript 三通道)",
            "defects_addressed": ["D-02", "D-05", "D-11", "D-17R"],
        },
        "corridor_key": {
            "display_name": "CorridorKey AI 抠像 (13.4k★)",
            "source_repo": "nikopueringer/CorridorKey",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": "integrations.corridor_key_adapter",
            "adapter_class": "CorridorKeyAdapter",
            "description": "神经网络绿幕抠像 (物理级颜色分离, VFX标准EXR输出)",
            "defects_addressed": ["D-07", "D-08"],
        },
        "openmontage": {
            "display_name": "OpenMontage (AI视频制作引擎)",
            "source_repo": "OpenMontage/OpenMontage",
            "layer": LayerLevel.L2_SERVICE,
            "priority": "P2",
            "adapter_module": "integrations.openmontage_adapter",
            "adapter_class": "OpenMontageAdapter",
            "description": "AI 驱动视频制作 pipeline (13管线+6风格+多AI后端)",
            "defects_addressed": ["D-05", "D-06", "D-08"],
        },
        "nexrender": {
            "display_name": "nexrender (模板化渲染)",
            "source_repo": "inlife/nexrender",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": "integrations.nexrender",
            "adapter_class": "NexrenderIntegration",
            "description": "数据驱动 AE 模板渲染 + 批量输出",
            "defects_addressed": ["D-05", "D-06", "D-11"],
        },
        "comfyui": {
            "display_name": "ComfyUI (AI生成引擎)",
            "source_repo": "Comfy-Org/ComfyUI",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": "integrations.comfyui_mcp_server",
            "adapter_class": "ComfyUIClient",
            "description": "节点式扩散模型引擎 (文生图/图生视频/3D)",
            "defects_addressed": ["D-07", "D-08", "D-20"],
        },
        "media_crawler": {
            "display_name": "MediaCrawler (社媒采集)",
            "source_repo": "NanmiCoder/MediaCrawler",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": "integrations.media_crawler_adapter",
            "adapter_class": "MediaCrawlerAdapter",
            "description": "7大中文社媒平台统一爬虫",
            "defects_addressed": ["D-01", "D-03"],
        },
        "blender_proc": {
            "display_name": "BlenderProc (3D场景生成)",
            "source_repo": "DLR-RM/BlenderProc",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": "integrations.blender_proc_adapter",
            "adapter_class": "BlenderProcAdapter",
            "description": "程序化3D场景生成 + 自动标注",
            "defects_addressed": ["D-07", "D-09"],
        },
        "firecrawl": {
            "display_name": "Firecrawl (联网上下文)",
            "source_repo": "mendableai/firecrawl",
            "layer": LayerLevel.L2_SERVICE,
            "priority": "P1",
            "adapter_module": "integrations.firecrawl_adapter",
            "adapter_class": "FirecrawlAdapter",
            "description": "AI Agent 网页上下文 API (Scrape/Crawl/Search)",
            "defects_addressed": ["D-08", "D-10"],
        },
        # ── P2 ──────────────────────────────────────────────────────
        "adb_mcp": {
            "display_name": "adb-mcp (Android调试)",
            "source_repo": "mikechambers/adb-mcp",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P2",
            "adapter_module": None,
            "adapter_class": None,
            "description": "Android 设备 MCP 控制 (移动端测试/录屏)",
            "defects_addressed": [],
        },
        "cloudflare_computer": {
            "display_name": "Cloudflare Computer",
            "source_repo": "cloudflare/computer",
            "layer": LayerLevel.L4_AGENT,
            "priority": "P2",
            "adapter_module": None,
            "adapter_class": None,
            "description": "云端浏览器 Agent (远程桌面自动化)",
            "defects_addressed": ["D-10"],
        },
        "blender_gpt": {
            "display_name": "BlenderGPT",
            "source_repo": "gd3kr/BlenderGPT",
            "layer": LayerLevel.L4_AGENT,
            "priority": "P2",
            "adapter_module": None,
            "adapter_class": None,
            "description": "ChatGPT 驱动 Blender 自动化",
            "defects_addressed": ["D-07"],
        },
        # ── 已有集成 ──────────────────────────────────────────────────
        "opensource_engine": {
            "display_name": "开源集成引擎 (RIFE/SAM2/Whisper/MoviePy)",
            "source_repo": "multiple",
            "layer": LayerLevel.L3_ORCHESTRATOR,
            "priority": "已集成",
            "adapter_module": "integrations.opensource_integrations",
            "adapter_class": None,
            "description": "RIFE帧插值 + SAM2分割 + Whisper语音 + MoviePy编辑",
            "defects_addressed": ["D-20", "D-21", "D-22", "D-23"],
        },
        # ── 2026-08-21 MG动画/手书动画 新增 (P0) ─────────────────────
        "scail2": {
            "display_name": "SCAIL-2 (角色动画/手绘驱动)",
            "source_repo": "zai-org/SCAIL-2",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P0",
            "adapter_module": "integrations.scail2_adapter",
            "adapter_class": "SCAIL2Adapter",
            "description": "DiT 端到端角色动画 (手绘/真实/动物/多人, 零样本, Apache 2.0)",
            "defects_addressed": ["MG-P0-1", "HD-P0-1"],
        },
        "musetalk": {
            "display_name": "MuseTalk (实时唇同步)",
            "source_repo": "TMElyralab/MuseTalk",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P0",
            "adapter_module": "integrations.musetalk_adapter",
            "adapter_class": "MuseTalkAdapter",
            "description": "30fps+ 实时音频驱动唇同步 (Whisper 编码, 4GB VRAM, Apache 2.0)",
            "defects_addressed": ["MG-P0-4"],
        },
        "matanyone2": {
            "display_name": "MatAnyone2 (发丝级视频抠图)",
            "source_repo": "pq-yang/MatAnyone2",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P0",
            "adapter_module": "integrations.matanyone2_adapter",
            "adapter_class": "MatAnyone2Adapter",
            "description": "CVPR 2026 Highlight, 发丝级视频抠图, 8GB VRAM, 4K 支持",
            "defects_addressed": ["MG-P0-2"],
        },
        "remotion_agent": {
            "display_name": "Remotion Agent Skills (MG动画引擎)",
            "source_repo": "remotion-dev/remotion",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P0",
            "adapter_module": "integrations.remotion_agent_adapter",
            "adapter_class": "RemotionAgentAdapter",
            "description": "React 编程式 MG 动画生成 (52k★, Agent Skills, 数据驱动)",
            "defects_addressed": ["MG-P0-3"],
        },
        "comfyui_handdrawn": {
            "display_name": "ComfyUI 手绘风格化 (img2img)",
            "source_repo": "Comfy-Org/ComfyUI",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": "integrations.comfyui_handdrawn_adapter",
            "adapter_class": "HanddrawnComfyUIAdapter",
            "description": "扩散模型手绘风格化主方案 (6种风格, OpenCV 降级兼容)",
            "defects_addressed": ["HD-P1-4"],
        },
        "motion_canvas": {
            "display_name": "Motion Canvas (TS 代码动画引擎)",
            "source_repo": "motion-canvas/motion-canvas",
            "layer": LayerLevel.L1_ENGINE,
            "priority": "P1",
            "adapter_module": "integrations.motion_canvas_adapter",
            "adapter_class": "MotionCanvasAdapter",
            "description": "TypeScript 声明式代码动画 (与 Remotion 双轨, 更轻量)",
            "defects_addressed": ["MG-P1-6"],
        },
        # ── 2026-08-13 新增 ──────────────────────────────────────────
        "pyscenedetect": {
            "display_name": "PySceneDetect (镜头边界检测)",
            "source_repo": "Breakthrough/PySceneDetect",
            "layer": LayerLevel.L3_ORCHESTRATOR,
            "priority": "已集成",
            "adapter_module": "core.shot_detector",
            "adapter_class": None,
            "description": "素材预处理: 镜头边界检测 + 结构摘要 (ContentDetector, 6 tests)",
            "defects_addressed": ["T5"],
        },
        "vmaf": {
            "display_name": "VMAF (Netflix 感知质量评估)",
            "source_repo": "Netflix/vmaf",
            "layer": LayerLevel.L3_ORCHESTRATOR,
            "priority": "已集成",
            "adapter_module": "integrations.vmaf_quality_adapter",
            "adapter_class": "VMAFAdapter",
            "description": "视频质量评估: 全参考/无参考降级, 已接入 AutoQualityEvaluator",
            "defects_addressed": ["Task9"],
        },
        "taste_contract": {
            "display_name": "品味契约 (三旋钮运镜治理)",
            "source_repo": "internal (OpenMontage taste-direction.md)",
            "layer": LayerLevel.L3_ORCHESTRATOR,
            "priority": "已集成",
            "adapter_module": "ai.taste_contract",
            "adapter_class": "TasteProfile",
            "description": "品味契约接入导演: visual_variance/motion_intensity/information_density + Anti-Default 机检 (12 tests)",
            "defects_addressed": ["T4"],
        },
        "style_card": {
            "display_name": "风格知识卡 (结构化品味治理)",
            "source_repo": "internal",
            "layer": LayerLevel.L3_ORCHESTRATOR,
            "priority": "已集成",
            "adapter_module": "knowledge.style_card",
            "adapter_class": "StyleCardIntegration",
            "description": "风格知识卡 schema: 3 试点 (amv_highenergy/cyberpunk/ambient_calm) + 品味+质量目标+反模式 (8 tests)",
            "defects_addressed": ["T6"],
        },
    }

    def __init__(self):
        self._integrations: Dict[str, IntegrationInfo] = {}
        self._initialized = False

    def discover_all(self) -> Dict[str, IntegrationInfo]:
        """发现并初始化所有已知集成"""
        for name, meta in self.KNOWN_INTEGRATIONS.items():
            info = IntegrationInfo(
                name=name,
                display_name=meta["display_name"],
                source_repo=meta["source_repo"],
                layer=meta["layer"],
                priority=meta["priority"],
                description=meta.get("description", ""),
                defects_addressed=meta.get("defects_addressed", []),
            )

            # 尝试加载适配器
            adapter_module = meta.get("adapter_module")
            adapter_class_name = meta.get("adapter_class")
            if adapter_module and adapter_class_name:
                try:
                    mod = __import__(adapter_module, fromlist=[adapter_class_name])
                    cls = getattr(mod, adapter_class_name)
                    instance = cls()
                    info.adapter_instance = instance
                    info.adapter_class = adapter_class_name

                    # 检查可用性
                    if hasattr(instance, "check_available"):
                        if instance.check_available():
                            info.status = IntegrationStatus.AVAILABLE
                            if hasattr(instance, "list_operations"):
                                info.operations_count = len(instance.list_operations())
                        else:
                            info.status = IntegrationStatus.DEGRADED
                    else:
                        info.status = IntegrationStatus.AVAILABLE

                except Exception as e:
                    info.status = IntegrationStatus.UNAVAILABLE
                    info.error = str(e)
                    logger.warning("[Registry] %s load failed: %s", name, e)
            elif adapter_module and not adapter_class_name:
                # 模块存在但无特定类（如 opensource_integrations）
                try:
                    __import__(adapter_module)
                    info.status = IntegrationStatus.AVAILABLE
                except ImportError:
                    info.status = IntegrationStatus.NOT_INSTALLED
            else:
                # 无适配器（架构参考或待开发）
                info.status = IntegrationStatus.NOT_INSTALLED

            info.last_check = time.time()
            self._integrations[name] = info

        self._initialized = True
        logger.info("[Registry] Discovered %d integrations", len(self._integrations))
        return self._integrations

    def health_check(self) -> Dict[str, Dict[str, Any]]:
        """全量健康检查"""
        if not self._initialized:
            self.discover_all()

        report = {}
        for name, info in self._integrations.items():
            report[name] = {
                "status": info.status.value,
                "layer": info.layer.value,
                "priority": info.priority,
                "operations": info.operations_count,
                "description": info.description,
                "defects": info.defects_addressed,
                "error": info.error,
            }
        return report

    def get(self, name: str) -> Optional[Any]:
        """获取指定集成适配器实例"""
        if not self._initialized:
            self.discover_all()
        info = self._integrations.get(name)
        return info.adapter_instance if info else None

    def get_info(self, name: str) -> Optional[IntegrationInfo]:
        """获取指定集成信息"""
        if not self._initialized:
            self.discover_all()
        return self._integrations.get(name)

    def list_by_layer(self) -> Dict[int, List[str]]:
        """按层级列出所有集成"""
        result: Dict[int, List[str]] = {}
        for name, info in self._integrations.items():
            layer = info.layer.value
            if layer not in result:
                result[layer] = []
            result[layer].append(name)
        return result

    def list_by_priority(self) -> Dict[str, List[str]]:
        """按优先级列出"""
        result: Dict[str, List[str]] = {}
        for name, info in self._integrations.items():
            p = info.priority
            if p not in result:
                result[p] = []
            result[p].append(name)
        return result

    def summary(self) -> Dict[str, Any]:
        """生成集成摘要"""
        if not self._initialized:
            self.discover_all()

        total = len(self._integrations)
        available = sum(1 for i in self._integrations.values()
                        if i.status == IntegrationStatus.AVAILABLE)
        degraded = sum(1 for i in self._integrations.values()
                       if i.status == IntegrationStatus.DEGRADED)
        unavailable = sum(1 for i in self._integrations.values()
                          if i.status in (IntegrationStatus.UNAVAILABLE, IntegrationStatus.NOT_INSTALLED))

        return {
            "total": total,
            "available": available,
            "degraded": degraded,
            "unavailable": unavailable,
            "by_layer": {str(k): v for k, v in self.list_by_layer().items()},
            "by_priority": self.list_by_priority(),
            "total_operations": sum(i.operations_count for i in self._integrations.values()),
        }


# ── 全局单例 ─────────────────────────────────────────────────────────────

_registry: Optional[IntegrationRegistry] = None


def get_registry() -> IntegrationRegistry:
    """获取全局注册中心单例"""
    global _registry
    if _registry is None:
        _registry = IntegrationRegistry()
    return _registry


def quick_test() -> Dict[str, Any]:
    """快速验证测试"""
    registry = get_registry()
    registry.discover_all()
    return registry.summary()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    result = quick_test()
    print(json.dumps(result, indent=2, ensure_ascii=False))

def get_registry() -> IntegrationRegistry:
    """获取全局注册中心单例"""
    global _registry
    if _registry is None:
        _registry = IntegrationRegistry()
    return _registry


def quick_test() -> Dict[str, Any]:
    """快速验证测试"""
    registry = get_registry()
    registry.discover_all()
    return registry.summary()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    result = quick_test()
    print(json.dumps(result, indent=2, ensure_ascii=False))
