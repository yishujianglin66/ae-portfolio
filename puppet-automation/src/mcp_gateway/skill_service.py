# -*- coding: utf-8 -*-
"""SkillRegistryService — 技能卡片库的网关消费端（P1-2）。

让 MCP 网关直接消费 schemas/skill_cards/registry.json（P1-1 产物）：
  skill_list    过滤查询卡片摘要（domain/stage/headless/skill_type/cost_class/keyword）
  skill_show    单卡完整内容（含证据链/契约/参数）
  skill_invoke  按卡执行：
                - tool_wrapper: 契约校验 -> 路由到 registry 中对应网关工具
                - effect_recipe / pipeline_step: 返回执行指引（v0.1 不自动执行）
治理闸门（与 schema 条件约束同源，双保险）：
  stage in (deprecated, archived) 拒绝执行；inputs 不合 card.contract.inputs 拒绝执行。

卡片库位置：仓库根 schemas/skill_cards/（本文件在 <repo>/puppet-automation/src/mcp_gateway/ 下）。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
CARDS_DIR = REPO_ROOT / "schemas" / "skill_cards"
REGISTRY_PATH = CARDS_DIR / "registry.json"

_BLOCKED_STAGES = {"deprecated", "archived"}


class SkillRegistryService:
    """网关侧技能卡片服务（同步查询 + 异步 invoke）。"""

    def __init__(self, registry_path: Path | None = None, cards_dir: Path | None = None) -> None:
        self._registry_path = registry_path or REGISTRY_PATH
        self._cards_dir = cards_dir or CARDS_DIR
        self._mcp_registry: Any = None  # late bind（initialize_gateway 末尾注入）
        self._index: dict[str, Any] = {}
        self._index_mtime: float = -1.0

    # ------------------------------------------------------------------ 内部
    def bind(self, mcp_registry: Any) -> None:
        """绑定 MCPRegistry 以便 skill_invoke 路由到真实工具。"""
        self._mcp_registry = mcp_registry

    def _ensure_index(self) -> dict[str, Any]:
        """registry.json 变化时重载（mtime 感知，卡片随开发常增删）。"""
        if not self._registry_path.exists():
            return {}
        mtime = self._registry_path.stat().st_mtime
        if mtime != self._index_mtime:
            reg = json.loads(self._registry_path.read_text(encoding="utf-8"))
            self._index = reg.get("skills", {})
            self._index_mtime = mtime
        return self._index

    def _load_card(self, skill_id: str) -> dict[str, Any] | None:
        entry = self._ensure_index().get(skill_id)
        if not entry:
            return None
        f = REPO_ROOT / entry["path"]
        if not f.exists():
            return None
        return yaml.safe_load(f.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ 查询
    def list_skills(
        self,
        domain: str | None = None,
        stage: str | None = None,
        headless: str | None = None,
        skill_type: str | None = None,
        cost_class: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        idx = self._ensure_index()
        rows = []
        kw = (keyword or "").lower()
        for sid, e in sorted(idx.items()):
            if domain and e["domain"] != domain:
                continue
            if stage and e["stage"] != stage:
                continue
            if headless and e["headless"] != headless:
                continue
            if skill_type and e["skill_type"] != skill_type:
                continue
            if cost_class and e["cost_class"] != cost_class:
                continue
            if kw and kw not in sid.lower() and kw not in str(e.get("domain", "")).lower():
                continue
            rows.append({"skill_id": sid, **{k: e[k] for k in
                        ("domain", "skill_type", "version", "stage", "headless",
                         "cost_class", "cost_sec", "hosts")}})
        rows = rows[:int(limit)]
        return {"success": True, "count": len(rows), "total_in_registry": len(idx), "skills": rows}

    def show_skill(self, skill_id: str) -> dict[str, Any]:
        card = self._load_card(skill_id)
        if card is None:
            return {"success": False, "error": f"skill '{skill_id}' 不在卡片库（skill_list 可查现有卡）"}
        return {"success": True, "card": card}

    # ------------------------------------------------------------------ 执行
    async def invoke(self, skill_id: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        inputs = inputs or {}
        card = self._load_card(skill_id)
        if card is None:
            return {"success": False, "error": f"skill '{skill_id}' 不存在"}

        # 治理闸门 1：生命周期
        stage = card.get("stage", "experimental")
        if stage in _BLOCKED_STAGES:
            return {"success": False,
                    "error": f"治理闸门拒绝：stage={stage} 的卡片不可执行",
                    "skill_id": skill_id}

        stype = card.get("skill_type")

        # 非 tool_wrapper：返回指引不自动执行（v0.1 边界，诚实声明）
        if stype != "tool_wrapper":
            return {"success": True, "mode": "guidance",
                    "note": f"{stype} 卡 v0.1 不自动执行，请按 recipe_ref 手动/经管线调用",
                    "recipe_ref": card.get("recipe_ref", ""),
                    "headless": card.get("headless"),
                    "cost": card.get("cost")}

        # 治理闸门 2：契约校验（jsonschema against card.contract.inputs）
        contract = (card.get("contract") or {}).get("inputs") or {}
        if contract.get("properties") or contract.get("required"):
            try:
                import jsonschema
                jsonschema.validate(inputs, contract)
            except ImportError:  # 环境缺库则降级放行并声明
                logger.warning("jsonschema 不可用，跳过契约校验")
            except Exception as e:  # ValidationError
                return {"success": False,
                        "error": f"契约校验失败（card.contract.inputs）：{getattr(e, 'message', e)}",
                        "failed_paths": [list(p) for p in getattr(e, "absolute_path", [])][:5]}

        # 治理闸门 3：requires_host 预检（仅提示，不阻断——宿主可能在轮询中启动）
        tool_ref = (card.get("tool_ref") or {}).get("gateway_tool") or skill_id
        if self._mcp_registry is None:
            return {"success": False, "error": "SkillRegistryService 未 bind MCPRegistry"}
        tool = self._mcp_registry.get_tool(tool_ref)
        if tool is None:
            return {"success": False,
                    "error": f"卡片指向的网关工具 '{tool_ref}' 未注册（对应引擎不可用）",
                    "hint": f"该卡 headless={card.get('headless')}，先启动宿主或注册引擎"}

        mcp_result = await self._mcp_registry.call_tool(tool_ref, inputs)
        content = {}
        try:
            content = json.loads(mcp_result["content"][0]["text"])
        except (KeyError, IndexError, ValueError):
            content = {"raw": mcp_result}
        return {
            "success": not mcp_result.get("isError", False),
            "mode": "tool_call",
            "skill_id": skill_id,
            "gateway_tool": tool_ref,
            "card_meta": {"headless": card.get("headless"), "cost": card.get("cost"),
                          "host": [h["app"] for h in card.get("requires_host", [])]},
            "result": content,
        }
