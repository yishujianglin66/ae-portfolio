"""
core/artifact_manager.py — 产物管理 (P4.3)
=============================================

跟踪管线各阶段产生的产物（视频、脚本、配置、日志等），
支持血缘追踪、完整性校验、过期清理、清单导出。

设计原则:
1. 单一注册中心: 所有产物通过 register() 注册，统一管理
2. 血缘可追溯: 每个 artifact 记录 parent_ids，可向上追溯
3. 完整性校验: SHA-256 校验和，防止产物被篡改
4. 持久化: registry.json 保存所有元数据，重启可恢复
5. 离线可用: 纯 hashlib + json，无外部依赖

集成方式:
    from core.artifact_manager import get_artifact_manager, Artifact

    mgr = get_artifact_manager()
    art_id = mgr.register(Artifact(
        type="video",
        stage="render",
        path="output/final.mp4",
        parent_ids=["art_perceive_001", "art_plan_002"],
    ))
    assert mgr.verify_checksum(art_id) is True
    manifest = mgr.export_manifest(run_id="run_2025_001")
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
#  数据类
# ============================================================================

@dataclass
class Artifact:
    """产物实体

    Attributes:
        id: 唯一 ID（注册时若为空则自动生成）
        type: 产物类型 ("video" / "audio" / "script" / "config" / "log" / "report" / "image" / "other")
        stage: 产生该产物的阶段名 ("perceive" / "analyze" / "plan" / "execute" / "render" / "verify" / "learn")
        path: 产物文件路径（绝对或相对）
        checksum: SHA-256 校验和（注册时自动计算）
        size: 文件大小（字节）
        created_at: 创建时间戳
        parent_ids: 上游产物 ID 列表（用于血缘追踪）
        metadata: 额外元数据
        run_id: 所属管线 run_id
        expires_at: 过期时间戳（0 表示永不过期）
    """
    id: str = ""
    type: str = "other"
    stage: str = ""
    path: str = ""
    checksum: str = ""
    size: int = 0
    created_at: float = 0.0
    parent_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    run_id: str = ""
    expires_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================================
#  ArtifactManager
# ============================================================================

class ArtifactManager:
    """产物管理器

    职责:
    1. 注册产物，自动计算校验和
    2. 按 stage / type 查询产物
    3. 校验产物完整性（重新计算 SHA-256 对比）
    4. 清理过期产物
    5. 血缘追溯（向上找父产物）
    6. 导出 run_id 的产物清单

    持久化:
    - 所有元数据写入 data/artifacts/registry.json
    - 文件本身不移动，仅记录路径与元数据
    """

    def __init__(self, registry_path: str = "data/artifacts/registry.json"):
        """初始化产物管理器

        Args:
            registry_path: 注册表持久化路径
        """
        self._registry_path = Path(registry_path)
        try:
            self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        # id -> Artifact
        self._artifacts: dict[str, Artifact] = {}
        # _logger 必须先于 _load_registry 初始化，否则加载失败时
        # _load_registry 内部的 logger.warning 会触发 AttributeError
        self._logger = logging.getLogger(__name__ + ".ArtifactManager")
        self._load_registry()

    # ---- 持久化 ----
    def _load_registry(self) -> None:
        """从磁盘加载注册表"""
        if not self._registry_path.exists():
            return
        try:
            with open(self._registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("artifacts", []):
                try:
                    art = Artifact(**item)
                    self._artifacts[art.id] = art
                except Exception as e:
                    self._logger.warning("[ArtifactManager] load skip: %s", e)
        except Exception as e:
            self._logger.warning("[ArtifactManager] load registry failed: %s", e)

    def _save_registry(self) -> None:
        """保存注册表到磁盘"""
        try:
            data = {
                "artifacts": [a.to_dict() for a in self._artifacts.values()],
                "updated_at": time.time(),
                "count": len(self._artifacts),
            }
            with open(self._registry_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            self._logger.warning("[ArtifactManager] save registry failed: %s", e)

    # ---- 校验和 ----
    @staticmethod
    def _compute_checksum(path: str) -> str:
        """计算文件 SHA-256 校验和

        Args:
            path: 文件路径

        Returns:
            16 进制 SHA-256 字符串；文件不存在时返回空串
        """
        try:
            p = Path(path)
            if not p.exists() or not p.is_file():
                return ""
            h = hashlib.sha256()
            with open(p, "rb") as f:
                # 分块读取，支持大文件
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    @staticmethod
    def _file_size(path: str) -> int:
        """获取文件大小（字节）"""
        try:
            return os.path.getsize(path)
        except Exception:
            return 0

    # ---- 核心 API ----
    def register(self, artifact: Artifact) -> str:
        """注册产物

        若 artifact.id 为空则自动生成；
        若 artifact.path 指向真实文件则自动计算 checksum 和 size；
        若 artifact.created_at 为 0 则使用当前时间。

        Args:
            artifact: 待注册的产物

        Returns:
            artifact_id
        """
        if not artifact.id:
            artifact.id = f"art_{uuid.uuid4().hex[:12]}"
        if not artifact.created_at:
            artifact.created_at = time.time()
        if artifact.path and not artifact.checksum:
            artifact.checksum = self._compute_checksum(artifact.path)
        if artifact.path and artifact.size <= 0:
            artifact.size = self._file_size(artifact.path)

        self._artifacts[artifact.id] = artifact
        self._save_registry()
        self._logger.debug(
            "[ArtifactManager] registered: %s (type=%s, stage=%s, size=%d)",
            artifact.id, artifact.type, artifact.stage, artifact.size,
        )
        return artifact.id

    def get(self, artifact_id: str) -> Artifact | None:
        """获取产物

        Args:
            artifact_id: 产物 ID

        Returns:
            Artifact 或 None
        """
        return self._artifacts.get(artifact_id)

    def list_by_stage(self, stage: str) -> list[Artifact]:
        """按阶段列出产物

        Args:
            stage: 阶段名

        Returns:
            产物列表（按创建时间升序）
        """
        items = [a for a in self._artifacts.values() if a.stage == stage]
        items.sort(key=lambda x: x.created_at)
        return items

    def list_by_type(self, artifact_type: str) -> list[Artifact]:
        """按类型列出产物

        Args:
            artifact_type: 产物类型

        Returns:
            产物列表（按创建时间升序）
        """
        items = [a for a in self._artifacts.values() if a.type == artifact_type]
        items.sort(key=lambda x: x.created_at)
        return items

    def list_by_run(self, run_id: str) -> list[Artifact]:
        """按 run_id 列出产物

        Args:
            run_id: 管线运行 ID

        Returns:
            产物列表
        """
        items = [a for a in self._artifacts.values() if a.run_id == run_id]
        items.sort(key=lambda x: x.created_at)
        return items

    def verify_checksum(self, artifact_id: str) -> bool:
        """校验产物完整性

        重新计算文件 SHA-256，与注册时记录的校验和对比。
        - 文件不存在 → False
        - 校验和不匹配 → False
        - 校验和匹配 → True
        - 原校验和为空（注册时文件不存在）→ 重新计算并返回是否存在

        Args:
            artifact_id: 产物 ID

        Returns:
            是否通过校验
        """
        art = self._artifacts.get(artifact_id)
        if art is None:
            return False
        if not art.path:
            return False
        current = self._compute_checksum(art.path)
        if not current:
            return False  # 文件不存在或读取失败
        if not art.checksum:
            # 原校验和为空，回填并视为通过
            art.checksum = current
            self._save_registry()
            return True
        return current == art.checksum

    def cleanup_expired(self, max_age_days: int = 30) -> int:
        """清理过期产物

        删除 created_at 早于 max_age_days 天的产物记录；
        若产物文件本身也存在且可写，则一并删除文件。

        Args:
            max_age_days: 最大保留天数

        Returns:
            清理的产物数量
        """
        threshold = time.time() - max_age_days * 86400
        expired_ids = [
            aid for aid, a in self._artifacts.items()
            if 0 < a.created_at < threshold
        ]
        deleted_files = 0
        for aid in expired_ids:
            art = self._artifacts.pop(aid, None)
            if art and art.path:
                try:
                    p = Path(art.path)
                    if p.exists() and p.is_file():
                        p.unlink()
                        deleted_files += 1
                except Exception as e:
                    self._logger.debug(
                        "[ArtifactManager] cleanup file failed: %s (%s)",
                        art.path, e,
                    )
        if expired_ids:
            self._save_registry()
            self._logger.info(
                "[ArtifactManager] cleanup: %d artifacts (%d files deleted)",
                len(expired_ids), deleted_files,
            )
        return len(expired_ids)

    def get_lineage(self, artifact_id: str, max_depth: int = 10) -> list[str]:
        """获取产物血缘（上游所有祖先）

        使用 BFS 向上遍历 parent_ids，返回所有上游产物 ID。
        避免环路：维护 visited 集合。

        Args:
            artifact_id: 起始产物 ID
            max_depth: 最大追溯深度（防止无限循环）

        Returns:
            上游产物 ID 列表（不含起始产物自身）
        """
        visited: set = set()
        result: list[str] = []
        queue: list[tuple] = [(artifact_id, 0)]
        while queue:
            current_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            if current_id in visited:
                continue
            visited.add(current_id)
            art = self._artifacts.get(current_id)
            if art is None:
                continue
            for pid in art.parent_ids:
                if pid not in visited:
                    result.append(pid)
                    queue.append((pid, depth + 1))
        return result

    def export_manifest(self, run_id: str) -> dict[str, Any]:
        """导出某次 run 的产物清单

        Args:
            run_id: 管线运行 ID

        Returns:
            清单字典，包含:
            - run_id
            - artifact_count
            - artifacts (按 stage 分组)
            - total_size_bytes
            - exported_at
        """
        items = self.list_by_run(run_id)
        by_stage: dict[str, list[dict[str, Any]]] = {}
        total_size = 0
        for a in items:
            by_stage.setdefault(a.stage, []).append(a.to_dict())
            total_size += a.size
        return {
            "run_id": run_id,
            "artifact_count": len(items),
            "artifacts_by_stage": by_stage,
            "total_size_bytes": total_size,
            "exported_at": time.time(),
        }

    def count(self) -> int:
        """返回已注册产物总数"""
        return len(self._artifacts)


# ============================================================================
#  全局单例
# ============================================================================

_global_artifact_manager: ArtifactManager | None = None


def get_artifact_manager() -> ArtifactManager:
    """获取全局 ArtifactManager 单例

    Returns:
        ArtifactManager 实例
    """
    global _global_artifact_manager
    if _global_artifact_manager is None:
        _global_artifact_manager = ArtifactManager()
    return _global_artifact_manager


def reset_artifact_manager() -> None:
    """重置全局 ArtifactManager（仅用于测试）"""
    global _global_artifact_manager
    _global_artifact_manager = None
