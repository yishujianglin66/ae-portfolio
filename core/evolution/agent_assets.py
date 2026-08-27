"""
core/evolution/agent_assets.py — Agent Prompt/Skill 资产管理 (P2)
===================================================================

借鉴 PenguinHarness「文件即真相」+ 计划中的人工确认规则:
1. 每个 Agent 的 Prompt/Skill 外置为独立文件 (data/evolution/prompts/{role}.md)
2. Optimizer 可以修改这些文件 → 下一轮执行即生效（Agent 每次执行前重新加载）
3. 安全规则: Prompt 修改 diff > 30% 时不自动应用，标记人工确认
4. 版本快照: 可打包当前全部资产供 VersionManager 存档

用法:
    from core.evolution.agent_assets import get_agent_asset_manager

    mgr = get_agent_asset_manager()
    prompt = mgr.load_prompt("style_analysis")
    result = mgr.update_prompt("style_analysis", new_text)
    # result.applied / result.needs_human_review / result.diff_ratio
"""
from __future__ import annotations

import difflib
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.evolution.protocol import append_jsonl, write_json

logger = logging.getLogger(__name__)

# 项目根目录（core/evolution/agent_assets.py → 上三级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# Prompt 修改差异超过该比例时需人工确认（计划中的风险控制规则）
HUMAN_REVIEW_DIFF_THRESHOLD = 0.30

# 各 Agent 角色的内置默认 Prompt（文件不存在时的兜底）
BUILTIN_PROMPTS: Dict[str, str] = {
    "style_analysis": (
        "你是视频风格分析专家。请从输入信息中提取可量化的风格参数：\n"
        "1. style_tags: 风格标签数组\n"
        "2. color_profile: brightness/saturation/warmth (0-100)\n"
        "3. rhythm_profile: cut_rate/avg_shot_duration\n"
        "4. ae_effect_presets: 推荐的 AE 效果及参数\n"
        "只输出严格 JSON 对象。"
    ),
    "code_generation": (
        "你是 AE JSX 代码生成专家。根据给定的风格分析结果生成 After Effects "
        "ExtendScript (JSX) 脚本，要求：\n"
        "1. 使用 app.project.activeItem 获取当前合成\n"
        "2. 通过 Effects.addProperty 添加效果并设置参数\n"
        "3. 禁止使用 eval，代码必须完整可执行\n"
        "只输出 JSX 代码，不要 markdown。"
    ),
    "param_optim": (
        "你是视频效果参数优化专家。根据当前效果与目标风格，给出参数调整建议：\n"
        "1. 每个参数给出具体数值\n"
        "2. 优先微调（±10% 以内），避免剧烈跳变\n"
        "只输出严格 JSON 对象 {参数名: 数值}。"
    ),
    "quality_review": (
        "你是质量审核专家。检查生成代码/结果的正确性与安全性：\n"
        "1. 检查是否有 eval() 等危险调用\n"
        "2. 检查代码完整性（长度、结构）\n"
        "3. 输出 JSON: {\"passed\": bool, \"issues\": [\"...\"]}"
    ),
}


@dataclass
class PromptUpdateResult:
    """Prompt 修改结果"""
    role: str
    applied: bool                       # 是否已写入文件
    needs_human_review: bool = False    # diff 超阈值，待人工确认
    diff_ratio: float = 0.0
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentAssetManager:
    """Agent Prompt/Skill 资产管理器"""

    DEFAULT_PROMPTS_DIR = str(PROJECT_ROOT / "data" / "evolution" / "prompts")

    def __init__(self, prompts_dir: str = DEFAULT_PROMPTS_DIR):
        self._prompts_dir = Path(prompts_dir)
        self._prompts_dir.mkdir(parents=True, exist_ok=True)
        self._pending_dir = self._prompts_dir / "pending_review"
        self._audit_log = self._prompts_dir / "update_log.jsonl"

    # ----------------------------------------------------------------
    #  加载
    # ----------------------------------------------------------------

    def prompt_path(self, role: str) -> Path:
        return self._prompts_dir / f"{role}.md"

    def load_prompt(self, role: str) -> str:
        """加载 Agent Prompt（文件优先，缺失时回退内置默认）

        Agent 每次执行前调用 → Optimizer 修改文件后下一轮即生效。
        """
        path = self.prompt_path(role)
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8").strip()
                if text:
                    return text
            except Exception as e:
                logger.warning("[AgentAssets] read %s failed: %s", path, e)
        return BUILTIN_PROMPTS.get(role, "")

    def prompt_source(self, role: str) -> str:
        """返回 prompt 来源: file / builtin"""
        return "file" if self.prompt_path(role).exists() else "builtin"

    def list_roles(self) -> List[str]:
        """已注册的角色（内置默认 ∪ 已存在文件）"""
        roles = set(BUILTIN_PROMPTS.keys())
        if self._prompts_dir.exists():
            for p in self._prompts_dir.glob("*.md"):
                roles.add(p.stem)
        return sorted(roles)

    # ----------------------------------------------------------------
    #  修改（Optimizer 入口，带人工确认规则）
    # ----------------------------------------------------------------

    def update_prompt(
        self,
        role: str,
        new_text: str,
        force: bool = False,
    ) -> PromptUpdateResult:
        """修改 Agent Prompt

        规则（对应计划「人工确认规则」）:
        - diff ≤ 30%: 自动应用
        - diff > 30%: 写入 pending_review/ 待人工确认，不自动生效
        - force=True: 人工确认后强制应用
        """
        new_text = (new_text or "").strip()
        if not new_text:
            return PromptUpdateResult(role=role, applied=False, reason="empty_prompt")

        old_text = self.load_prompt(role)
        diff_ratio = self.diff_ratio(old_text, new_text)

        if diff_ratio > HUMAN_REVIEW_DIFF_THRESHOLD and not force:
            # 暂存到待审目录，不影响当前运行
            self._pending_dir.mkdir(parents=True, exist_ok=True)
            write_json(self._pending_dir / f"{role}.json", {
                "role": role,
                "old_prompt": old_text,
                "new_prompt": new_text,
                "diff_ratio": round(diff_ratio, 4),
                "submitted_at": time.time(),
            })
            result = PromptUpdateResult(
                role=role, applied=False, needs_human_review=True,
                diff_ratio=round(diff_ratio, 4),
                reason=f"diff {diff_ratio:.0%} > {HUMAN_REVIEW_DIFF_THRESHOLD:.0%}, pending human review",
            )
        else:
            self.prompt_path(role).write_text(new_text + "\n", encoding="utf-8")
            result = PromptUpdateResult(
                role=role, applied=True,
                diff_ratio=round(diff_ratio, 4),
                reason="applied" if not force else "force_applied_after_review",
            )

        append_jsonl(self._audit_log, result.to_dict())
        logger.info(
            "[AgentAssets] %s prompt update: applied=%s diff=%.2f human_review=%s",
            role, result.applied, diff_ratio, result.needs_human_review,
        )
        return result

    def approve_pending(self, role: str) -> PromptUpdateResult:
        """人工确认待审 Prompt 并应用"""
        pending_path = self._pending_dir / f"{role}.json"
        if not pending_path.exists():
            return PromptUpdateResult(role=role, applied=False, reason="no_pending")
        import json
        try:
            with open(pending_path, "r", encoding="utf-8") as f:
                pending = json.load(f)
        except Exception:
            return PromptUpdateResult(role=role, applied=False, reason="pending_corrupted")
        result = self.update_prompt(role, pending.get("new_prompt", ""), force=True)
        if result.applied:
            try:
                pending_path.unlink()
            except Exception:
                pass
        return result

    def list_pending(self) -> List[Dict[str, Any]]:
        """列出全部待人工确认的 Prompt 修改"""
        if not self._pending_dir.exists():
            return []
        import json
        items: List[Dict[str, Any]] = []
        for p in sorted(self._pending_dir.glob("*.json")):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    items.append(json.load(f))
            except Exception:
                continue
        return items

    # ----------------------------------------------------------------
    #  工具
    # ----------------------------------------------------------------

    @staticmethod
    def diff_ratio(old_text: str, new_text: str) -> float:
        """计算两段文本的差异比例 (0=完全相同, 1=完全不同)"""
        if not old_text and not new_text:
            return 0.0
        if not old_text or not new_text:
            return 1.0
        ratio = difflib.SequenceMatcher(None, old_text, new_text).ratio()
        return 1.0 - ratio

    def snapshot_assets(self) -> Dict[str, str]:
        """打包全部 Prompt 快照（供 VersionManager 存档）"""
        return {role: self.load_prompt(role) for role in self.list_roles()}

    def restore_assets(self, snapshot: Dict[str, str]) -> int:
        """从快照恢复 Prompt（版本回退用），返回恢复数量"""
        count = 0
        for role, text in snapshot.items():
            if not text:
                continue
            self.prompt_path(role).write_text(text + "\n" if not text.endswith("\n") else text, encoding="utf-8")
            count += 1
        return count

    def ensure_seed_files(self) -> int:
        """为缺失的角色生成种子 Prompt 文件（不覆盖已有）"""
        created = 0
        for role, text in BUILTIN_PROMPTS.items():
            path = self.prompt_path(role)
            if not path.exists():
                path.write_text(text + "\n", encoding="utf-8")
                created += 1
        return created


# ============================================================================
#  全局单例
# ============================================================================

_global_assets: Optional[AgentAssetManager] = None


def get_agent_asset_manager(
    prompts_dir: str = AgentAssetManager.DEFAULT_PROMPTS_DIR,
) -> AgentAssetManager:
    """获取全局 Agent 资产管理器单例"""
    global _global_assets
    if _global_assets is None:
        _global_assets = AgentAssetManager(prompts_dir=prompts_dir)
    return _global_assets
