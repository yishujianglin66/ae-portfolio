#!/usr/bin/env python3
"""MiniMax H3 接入：安全护栏验证。"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestRiskMapping:
    """P0-2 风险映射修正：付费视频/图像生成应为 L5_EXTERNAL。"""

    H3_PAID_TYPES_L5 = (
        "video_generation",
        "video_editing",
        "image_generation",
        "style_transfer",
        "motion_transfer",
        "object_replacement",
        "scene_alteration",
        "rate_adjustment",
        "inpainting",
        "minimax_h3_generate",
    )

    def test_h3_paid_types_default_l5(self):
        """11 类 H3 付费任务必须全部映射 L5_EXTERNAL（PURPOSE。"""
        from core.security import RiskAssessor, RiskLevel

        assessor = RiskAssessor()
        for task_type in self.H3_PAID_TYPES_L5:
            result = assessor.assess(task_type, {})
            assert result.risk_level == RiskLevel.L5_EXTERNAL, (
                f"{task_type}: 期望 L5_EXTERNAL，实际 L{result.risk_level.value}，"
                "付费任务不审批就执行会产生资金泄露风险"
            )
            assert result.requires_approval is True, f"{task_type} 应需审批"
            assert result.requires_second_confirm is True, f"{task_type} 需二次确认（L5规则）"

    def test_subtitle_modification_l3_not_paid(self):
        """subtitle_modification（非付费任务，映射 L3（白名单保护）。"""
        from core.security import RiskAssessor, RiskLevel

        assessor = RiskAssessor()
        r = assessor.assess("subtitle_modification", {})
        assert r.risk_level == RiskLevel.L3_OVERWRITE_SAFE
        assert r.requires_sandbox

    def test_original_29_mapping_unchanged(self):
        """原 29 条映射必须回归：不回归原风险等级，不回归原审批决策。"""
        from core.security import RiskAssessor, RiskLevel

        assessor = RiskAssessor()
        baseline = {
            "perception": RiskLevel.L1_READONLY,
            "planning": RiskLevel.L1_READONLY,
            "ae_compile": RiskLevel.L2_GENERATE,
            "pr_import": RiskLevel.L2_GENERATE,
            "ae_execute": RiskLevel.L3_OVERWRITE_SAFE,
            "ae_render": RiskLevel.L4_DESTRUCTIVE,
            "ffmpeg_export": RiskLevel.L4_DESTRUCTIVE,
            "runway_generate": RiskLevel.L5_EXTERNAL,
        }
        for task_type, expected_level in baseline.items():
            result = assessor.assess(task_type, {})
            assert result.risk_level == expected_level, (
                f"原映射回归：{task_type} 期望 {expected_level}，实际 {result.risk_level}"
            )

    def test_unknown_type_default_l3_failclosed(self):
        """未知 task_type 必须默认 L3（fail-closed），不改变既有行为）。"""
        from core.security import RiskAssessor, RiskLevel

        assessor = RiskAssessor()
        r = assessor.assess("completely_new_type_xyz_never_seen", {})
        assert r.risk_level == RiskLevel.L3_OVERWRITE_SAFE


class TestSandboxWhitelist:
    """P0-5 沙箱白名单包含 H3 下载/缓存目录。"""

    def test_sandbox_allowed_roots_has_h3_dirs(self, tmp_path):
        """SandboxPolicy/_allowed_roots 必须含 output/h3_downloads 和 data/h3_cache。"""
        from core.security import SandboxPolicy

        executor = SandboxPolicy(workspace_root=tmp_path)
        root_strs = [str(p) for p in executor._allowed_roots]
        joined = " ".join(root_strs).lower()
        assert "h3_downloads" in joined, (
            f"沙箱白名单缺少 H3 下载目录，当前 _allowed_roots={root_strs}"
        )
        assert "h3_cache" in joined, (
            f"沙箱白名单缺少 H3 缓存目录，当前 _allowed_roots={root_strs}"
        )
        # 3 个原有白名单根（data/sandbox、output/temp、data/cache）+ 2 个 H3 新增 = 至少 5 个
        assert len(executor._allowed_roots) >= 5


class TestWorkflowTaskType:
    """workflow_orchestrator.TaskType 枚举扩展（与 security 侧枚举对齐。"""

    H3_WF_MEMBERS = (
        "VIDEO_GENERATION",
        "VIDEO_EDITING",
        "IMAGE_GENERATION",
        "SUBTITLE_MODIFICATION",
        "STYLE_TRANSFER",
        "MOTION_TRANSFER",
        "OBJECT_REPLACEMENT",
        "SCENE_ALTERATION",
        "RATE_ADJUSTMENT",
        "INPAINTING",
        "MINIMAX_H3_GENERATE",
    )

    def test_workflow_tasktype_has_h3_members(self):
        """workflow_orchestrator.TaskType 含 11 个 H3 成员。"""
        from core.workflow_orchestrator import TaskType

        names = {m.name for m in TaskType}
        for name in self.H3_WF_MEMBERS:
            assert name in names, f"workflow_orchestrator.TaskType 缺少 {name!r}"

    def test_workflow_tasktype_values_match_risk_keys(self):
        """workflow_orchestrator.TaskType.value 字符串必须与 security.RiskAssessor 中的 key 完全一致。"""
        from core.security import RiskAssessor
        from core.workflow_orchestrator import TaskType

        assessor = RiskAssessor()
        for member_name in self.H3_WF_MEMBERS:
            member = getattr(TaskType, member_name)
            assert member.value in assessor.DEFAULT_RISK_MAP, (
                f"不匹配：TaskType.{member_name}.value={member.value!r} 不在 DEFAULT_RISK_MAP"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider"])
