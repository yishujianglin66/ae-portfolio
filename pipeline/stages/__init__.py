"""pipeline.stages - 管线各阶段实现

包含:
- FFmpeg/FFprobe 路径解析工具
- StageBase 抽象基类 (P2.3 新增): 新阶段必须继承
- StageContext / StageResult / StageMetadata 数据类: 用于 StageBase 标准接口

向后兼容: 现有阶段 (PerceptionStage / AnalysisStage / ...) 不强制改造，
保留各自的 run(prev) 方法继续工作。新增阶段建议继承 StageBase 以获得
统一的能力声明、上下文传递和结果标准化。
"""
from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# FFmpeg/FFprobe 路径解析 (支持自定义路径 + PATH 搜索)
_FFMPEG_CACHE: dict = {}

# env 覆盖路径（AEK_FFMPEG / AEK_FFPROBE，经 core/paths.py 统一收口）作为最高优先级候选
try:
    from core.paths import ffmpeg_bin as _env_ffmpeg, ffprobe_bin as _env_ffprobe
except ImportError:
    _env_ffmpeg = lambda: ""
    _env_ffprobe = lambda: ""


def resolve_ffmpeg(config=None, force_refresh: bool = False) -> str:
    """解析 ffmpeg 可执行文件路径

    Args:
        config: 配置对象 (可包含 ffmpeg_bin 字段)
        force_refresh: 强制重新查找, 忽略缓存

    Returns:
        ffmpeg 可执行文件路径; 找不到时返回 "ffmpeg" (依赖 PATH)
    """
    key = "ffmpeg"
    if not force_refresh and key in _FFMPEG_CACHE:
        return _FFMPEG_CACHE[key]
    # 1. 配置指定
    if config and getattr(config, 'ffmpeg_bin', ''):
        path = config.ffmpeg_bin
        if os.path.isfile(path):
            _FFMPEG_CACHE[key] = path
            return path
    # 2. 常见路径（env 覆盖优先，其后为历史候选）
    for p in [_env_ffmpeg(), r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\ffmpeg-tmp\bin\ffmpeg.exe",
              r"/usr/bin/ffmpeg", r"/usr/local/bin/ffmpeg"]:
        if p and os.path.isfile(p):
            _FFMPEG_CACHE[key] = p
            return p
    # 3. PATH 搜索
    found = shutil.which("ffmpeg")
    if found:
        _FFMPEG_CACHE[key] = found
        return found
    # 修复: 不缓存 fallback 值, 允许后续 (安装 ffmpeg 后) 重新查找
    return "ffmpeg"


def resolve_ffprobe(config=None, force_refresh: bool = False) -> str:
    """解析 ffprobe 可执行文件路径

    Args:
        config: 配置对象 (可包含 ffmpeg_bin 字段)
        force_refresh: 强制重新查找, 忽略缓存

    Returns:
        ffprobe 可执行文件路径; 找不到时返回 "ffprobe" (依赖 PATH)
    """
    key = "ffprobe"
    if not force_refresh and key in _FFMPEG_CACHE:
        return _FFMPEG_CACHE[key]
    if config and getattr(config, 'ffmpeg_bin', ''):
        base = os.path.dirname(config.ffmpeg_bin)
        probe = os.path.join(base, "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if os.path.isfile(probe):
            _FFMPEG_CACHE[key] = probe
            return probe
    for p in [_env_ffprobe(), r"C:\ffmpeg\bin\ffprobe.exe", r"C:\ffmpeg-tmp\bin\ffprobe.exe",
              r"/usr/bin/ffprobe", r"/usr/local/bin/ffprobe"]:
        if p and os.path.isfile(p):
            _FFMPEG_CACHE[key] = p
            return p
    found = shutil.which("ffprobe")
    if found:
        _FFMPEG_CACHE[key] = found
        return found
    # 修复: 不缓存 fallback 值, 允许后续 (安装 ffprobe 后) 重新查找
    return "ffprobe"


# ============================================================================
#  P2.3: Stage 抽象统一
# ============================================================================
# 这组抽象为新增阶段提供统一接口。现有阶段保留 run(prev) 接口，
# 不强制继承，保证向后兼容。

class StageStatus(Enum):
    """阶段执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageContext:
    """阶段执行上下文
    
    封装阶段执行所需的所有输入，替代旧的 `previous_data: Dict` 风格。
    旧代码可继续使用 dict，新阶段建议使用 StageContext。
    
    Attributes:
        stage_name: 当前阶段名 (perceive / analyze / plan / execute / render / verify / learn)
        config: PipelineConfig 或类似配置对象
        previous_data: 前序阶段输出的聚合 dict (向后兼容)
        run_id: 当前管线运行 ID
        iteration: 当前质量迭代轮数 (0 表示首轮)
        mode: 管线模式 (text_topic / reference_video / mixed)
        global_context: 全局共享上下文 (VRS 结果、KB 经验等)
    """
    stage_name: str = ""
    config: Any = None
    previous_data: Dict[str, Any] = field(default_factory=dict)
    run_id: str = ""
    iteration: int = 0
    mode: str = "auto"
    global_context: Dict[str, Any] = field(default_factory=dict)

    def get_previous(self, stage_name: str) -> Dict[str, Any]:
        """获取指定前序阶段的输出数据
        
        Args:
            stage_name: 前序阶段名
        
        Returns:
            该阶段的数据字典，不存在返回空字典
        """
        return self.previous_data.get(stage_name, {}) if isinstance(self.previous_data, dict) else {}


@dataclass
class StageResult:
    """阶段执行结果
    
    与 unified_pipeline.py 中的 StageResult 类似但独立，避免循环导入。
    StageBase 子类应返回此类型；旧 run(prev) 风格返回 dict 时由适配器转换。
    
    Attributes:
        stage: 阶段名
        status: 执行状态
        data: 输出数据 (供后续阶段使用)
        error: 错误信息 (失败时填写)
        duration_sec: 执行耗时
        timestamp: ISO 时间戳
    """
    stage: str
    status: StageStatus = StageStatus.PENDING
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_sec: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def is_success(self) -> bool:
        """是否成功"""
        return self.status == StageStatus.DONE

    def to_dict(self) -> Dict[str, Any]:
        """转 dict (供序列化)"""
        return {
            "stage": self.stage,
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "duration_sec": self.duration_sec,
            "timestamp": self.timestamp,
        }


@dataclass
class StageMetadata:
    """阶段元数据
    
    Attributes:
        name: 阶段唯一名
        version: 阶段版本
        description: 阶段描述
        inputs: 依赖的输入数据键名
        outputs: 产出的数据键名
        tags: 标签 (用于分组/过滤)
        critical: 是否关键阶段 (失败时是否中断管线)
    """
    name: str
    version: str = "1.0"
    description: str = ""
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    critical: bool = False


class StageBase(ABC):
    """阶段抽象基类
    
    所有新增阶段应继承此类，统一接口、能力声明与元数据。
    现有阶段 (PerceptionStage / AnalysisStage / ...) 不强制继承，保证向后兼容。
    
    设计原则:
    1. execute() 是唯一入口，接收 StageContext，返回 StageResult
    2. can_handle() 声明此阶段能否处理当前上下文 (用于动态路由)
    3. get_metadata() 暴露元数据 (用于编排器调度)
    
    用法:
        class MyStage(StageBase):
            def get_metadata(self):
                return StageMetadata(name="my_stage", description="...")
            
            def can_handle(self, context):
                return context.mode in ("text_topic", "mixed")
            
            async def execute(self, context):
                # ... 业务逻辑
                return StageResult(stage="my_stage", status=StageStatus.DONE, data={...})
    """
    
    @property
    def name(self) -> str:
        """阶段名 (默认从元数据获取)"""
        try:
            return self.get_metadata().name
        except NotImplementedError:
            return self.__class__.__name__

    @abstractmethod
    async def execute(self, context: StageContext) -> StageResult:
        """执行阶段逻辑 (子类必须实现)
        
        Args:
            context: 阶段执行上下文
        
        Returns:
            阶段执行结果
        
        Raises:
            NotImplementedError: 子类未实现时
        """
        raise NotImplementedError

    def can_handle(self, context: StageContext) -> bool:
        """声明此阶段能否处理当前上下文
        
        默认实现返回 True。子类可重写以实现基于上下文的动态路由。
        
        Args:
            context: 阶段执行上下文
        
        Returns:
            能否处理
        """
        return True

    def get_metadata(self) -> StageMetadata:
        """返回阶段元数据
        
        默认实现使用类名作为 name。子类应重写以提供更详细的元数据。
        
        Returns:
            阶段元数据
        """
        return StageMetadata(name=self.__class__.__name__)


# ============================================================================
#  适配器: 旧风格阶段 → StageBase 接口
# ============================================================================

class LegacyStageAdapter(StageBase):
    """将旧风格 run(prev)->dict 阶段适配为 StageBase 接口
    
    用于让现有阶段在不修改源码的情况下接入新的 StageBase 体系。
    """
    
    def __init__(self, stage_name: str, legacy_instance: Any):
        """初始化适配器
        
        Args:
            stage_name: 阶段名
            legacy_instance: 旧风格阶段实例 (需有 run(prev)->dict 方法)
        """
        self._stage_name = stage_name
        self._legacy = legacy_instance
    
    def get_metadata(self) -> StageMetadata:
        return StageMetadata(
            name=self._stage_name,
            description=f"Legacy adapter for {type(self._legacy).__name__}",
            tags=["legacy"],
        )
    
    def can_handle(self, context: StageContext) -> bool:
        # 旧阶段无能力声明，默认可处理
        return True
    
    async def execute(self, context: StageContext) -> StageResult:
        """调用旧风格的 run(prev) 并包装为 StageResult"""
        import time
        start = time.time()
        try:
            data = self._legacy.run(context.previous_data)
            dur = time.time() - start
            if not isinstance(data, dict):
                data = {"result": data}
            return StageResult(
                stage=self._stage_name,
                status=StageStatus.DONE,
                data=data,
                duration_sec=dur,
            )
        except Exception as e:
            dur = time.time() - start
            return StageResult(
                stage=self._stage_name,
                status=StageStatus.FAILED,
                error=str(e),
                duration_sec=dur,
            )
