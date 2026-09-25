# -*- coding: utf-8 -*-
"""Skill schema v0.1 体系回归测试（P1 Top50 封装的守门测试）

锁住六条不变式：
 1. 元 schema 自身是合法 JSON Schema
 2. 全部卡片 against schema 零违规（Draft-07）
 3. skill_id 全局唯一 + 与文件名一致
 4. 治理闸门：stage=active 必须 evidence real_execution；auto_generated 不许超过 validated
 5. registry.json 与卡片目录不脱节（数量一致、路径有效）
 6. 网关 37 工具全部有 tool_wrapper 卡（一工具一卡，P1 承诺）
"""
import json
import re
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
SCHEMA_PATH = ROOT / "schemas" / "skill_card_schema_v0.1.json"
CARDS_DIR = ROOT / "schemas" / "skill_cards"
REGISTRY_PATH = CARDS_DIR / "registry.json"


def _cards():
    out = []
    for f in sorted(CARDS_DIR.rglob("*.yaml")):
        out.append((f, yaml.safe_load(f.read_text(encoding="utf-8"))))
    return out


def test_meta_schema_valid():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)


@pytest.mark.parametrize("path,card", _cards(), ids=lambda x: x.name if isinstance(x, Path) else "")
def test_each_card_conforms(path, card):
    errs = list(jsonschema.Draft7Validator(
        json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))).iter_errors(card))
    assert not errs, f"{path.name}: {errs[0].message}"


def test_ids_unique_and_match_filename():
    ids = [c["skill_id"] for _, c in _cards()]
    assert len(ids) == len(set(ids)), "skill_id 重复"
    for f, c in _cards():
        assert f.stem == c["skill_id"], f"{f.name} 文件名与 skill_id 不一致"


def test_governance_gate():
    for f, c in _cards():
        status = c["evidence_chain"]["status"]
        if c["stage"] == "active":
            assert status == "real_execution", f"{f.name}: active 卡必须有真实执行证据"
        if status == "auto_generated":
            assert c["stage"] in ("experimental", "validated"), \
                f"{f.name}: 自动生成卡不许越过 validated"


def test_registry_in_sync():
    assert REGISTRY_PATH.exists(), "先跑 skill_cli build-registry"
    reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    files = dict((c["skill_id"], f) for f, c in _cards())
    assert reg["count"] == len(files), f"registry {reg['count']} vs 卡片 {len(files)} 脱节"
    for sid, e in reg["skills"].items():
        assert (ROOT / e["path"]).exists(), f"{sid} registry 路径失效"


def test_gateway_tools_all_wrapped():
    from skill_cli import GATEWAY_PY, _extract_gateway_tools
    tools = {t["name"] for t in _extract_gateway_tools()}
    assert len(tools) >= 37, f"网关工具数异常缩水: {len(tools)}"
    cards = {c["skill_id"] for _, c in _cards() if c["skill_type"] == "tool_wrapper"}
    missing = tools - cards
    assert not missing, f"未封装工具: {sorted(missing)}"


def test_headless_matrix_enum():
    for f, c in _cards():
        assert c["headless"] in ("headless", "requires_gui", "requires_running_host")
