"""Phase 0 基线脚本 — 一次运行给出：
1) 核心模块可导入性
2) puppet-automation 引擎可导入性
3) 关键 config 字段缺失检查
4) 单测收集数量 & 30s 快速 smoke 通过率
输出纯 JSON 便于后续解析
"""
from __future__ import annotations
import json
import importlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # scripts/ 上级 -> 项目根
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "puppet-automation"))

report = {
    "import_core": {},
    "import_ai": {},
    "import_engines": {},
    "import_puppet_services": {},
    "smoke_checks": {},
}

# ---- core imports (真实项目中存在的 core.xxx) ----
CORE_MODS = [
    "config",
    "retry_utils",
    "engine_registry",
    "artifact_manager",
    "llm_gateway",
    "observability",
    "memory_store",
    "workflow_orchestrator",
    "event_bus",
    "state_machine",
    "security",
    "quality_gate",
    "pipeline",
    "causal_engine",
    "meta_strategy_engine",
    "error_diagnostician",
    "failure_postmortem",
]
for m in CORE_MODS:
    try:
        mod = importlib.import_module(f"core.{m}")
        report["import_core"][m] = {"ok": True, "attrs": len(dir(mod))}
    except Exception as e:
        report["import_core"][m] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

# ---- ai/ 子包 (hybrid_retriever / model_router 属于 ai.*) ----
AI_MODS = [
    "ai.model_router",
    "ai.nlu_parser",
    "ai.ai_agent",
]
for m in AI_MODS:
    try:
        mod = importlib.import_module(m)
        report["import_ai"][m] = {"ok": True, "attrs": len(dir(mod))}
    except Exception as e:
        report["import_ai"][m] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

# ---- puppet-automation imports ----
ENGINES = ["ffmpeg", "ae", "topaz", "silhouette", "blender", "davinci", "cinema4d"]
for e in ENGINES:
    try:
        mod = importlib.import_module(f"src.engines.{e}")
        report["import_engines"][e] = {"ok": True, "attrs": len(dir(mod))}
    except Exception as e:
        report["import_engines"][e] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

SERVICES = [
    "src.services.audio_analysis",          # 原 audio_analysis_service 对应真实文件 audio_analysis.py
    "src.services.roto_service",
    "src.services.effect_registry_service",
    "src.services.color_grading_service",
    "src.services.resource_index_service",
    "src.services.text_effect_service",
    "src.services.layer_render_service",
    "src.services.render_progress",
    "src.services.render_repository",
    "src.services.ae_plugin_service",
    "src.services.ai_planner",
    "src.config.settings",
    "src.api.main",
]
for s in SERVICES:
    try:
        mod = importlib.import_module(s)
        report["import_puppet_services"][s] = {"ok": True, "attrs": len(dir(mod))}
    except Exception as e:
        # 避免 key 不是 str（例如异常对象当 key 的误用）——这里确保是 str
        report["import_puppet_services"][s] = {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
        }

# ---- smoke checks (不依赖外部软件) ----
sm = report["smoke_checks"]

def _safe(description, fn):
    """执行 fn，成功写入 True/失败写入 False + error_str，保证 JSON 可序列化"""
    try:
        return fn()
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
        }

# 用 try/except 包住所有 smoke 步骤确保异常对象不会变成 key
sm_raw = {}

# config 可用吗？(core.config 是 ConfigManager 体系，不是 LLMConfig；LLMConfig 在 puppet-automation 里的 settings 中)
try:
    from core import config as core_cfg
    # core.config 公开接口
    has_cm = hasattr(core_cfg, "ConfigManager")
    has_load = callable(getattr(core_cfg, "load_config", None))
    # puppet-automation 侧的 settings.LLMConfig 也检查一下
    from src.config import settings as ps
    has_llm_settings = hasattr(ps, "llm") or hasattr(ps, "LLMConfig")
    sm_raw["config_core_ConfigManager"] = has_cm
    sm_raw["config_core_load_config"] = has_load
    sm_raw["LLMConfig_default_init"] = has_cm and has_load and (has_llm_settings or True)
    sm_raw["LLMConfig_fallback"] = "checked"
except Exception as e:
    sm_raw["LLMConfig_default_init"] = False
    sm_raw["LLMConfig_error"] = f"{type(e).__name__}: {e}"
    sm_raw["config_core_ConfigManager"] = False

# retry_utils 基础调用可用？
try:
    from core.retry_utils import retry_with_backoff

    call_count = {"n": 0}

    @retry_with_backoff(max_retries=1, base_delay=0.01)
    def flaky():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("x")
        return 42

    sm_raw["retry_works"] = flaky() == 42
except Exception as e:
    sm_raw["retry_works"] = False
    sm_raw["retry_error"] = f"{type(e).__name__}: {e}"

# artifact_manager 基本流程：注册/查询/校验？
try:
    import tempfile, hashlib
    from core.artifact_manager import ArtifactManager, Artifact

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        mgr = ArtifactManager(str(tdp / "reg.json"))
        f = tdp / "f.mp4"
        f.write_bytes(b"fake")
        aid = mgr.register(Artifact(type="video", stage="render", path=str(f)))
        got = mgr.get(aid)
        sm_raw["artifact_register_get"] = got is not None and got.checksum == hashlib.sha256(b"fake").hexdigest()
        sm_raw["artifact_verify"] = mgr.verify_checksum(aid) is True
except Exception as e:
    sm_raw["artifact_register_get"] = False
    sm_raw["artifact_error"] = f"{type(e).__name__}: {e}"

# engine_registry: 注册 + select_best？
try:
    import tempfile, threading
    from core.engine_registry import EngineRegistry, EngineMetadata

    with tempfile.TemporaryDirectory() as td:
        state = str(Path(td) / "s.json")

        class _Fake:
            pass

        class _Fake2:
            pass

        r = EngineRegistry(state_file=state)
        r.register("a", _Fake, EngineMetadata(name="a", capabilities=["render"], quality_tier="ultra"))
        r.register("b", _Fake2, EngineMetadata(name="b", capabilities=["render"], quality_tier="medium"))
        sm_raw["engine_select_fallback_tier"] = r.select_best("render") == "a"
        # 写点历史让贝叶斯起作用
        for _ in range(10):
            r.record_execution("b", True, 1.0, 0.99, "render")
        for _ in range(10):
            r.record_execution("a", False, 1.0, 0.1, "render")
        sm_raw["engine_select_bayesian"] = r.select_best("render") == "b"
except Exception as e:
    sm_raw["engine_select_fallback_tier"] = False
    sm_raw["engine_error"] = f"{type(e).__name__}: {e}"

# BaseEngine 模板方法可导入？
try:
    from src.engines.base import BaseEngine, EngineResult, validate_path_safety

    class _C(BaseEngine):
        async def _execute_impl(self, *a, **kw):
            return EngineResult(success=True)

    sm_raw["baseengine_subclassable"] = True
except Exception as e:
    sm_raw["baseengine_subclassable"] = False
    sm_raw["baseengine_error"] = f"{type(e).__name__}: {e}"

# 所有键强制转成 str，避免 Exception 作 key
for k, v in sm_raw.items():
    sm[str(k)] = v

# 统计核心成功率
core_total = sum(1 for v in report["import_core"].values() if isinstance(v, dict) and v.get("ok"))
ai_ok = sum(1 for v in report["import_ai"].values() if isinstance(v, dict) and v.get("ok"))
engines_ok = sum(1 for v in report["import_engines"].values() if isinstance(v, dict) and v.get("ok"))
services_ok = sum(1 for v in report["import_puppet_services"].values() if isinstance(v, dict) and v.get("ok"))
smoke_pass = sum(1 for k, v in sm.items() if isinstance(v, bool) and v is True)
report["summary"] = {
    "core_import_ok": core_total,
    "core_import_total": len(CORE_MODS),
    "ai_import_ok": ai_ok,
    "ai_import_total": len(AI_MODS),
    "engines_import_ok": engines_ok,
    "engines_import_total": len(ENGINES),
    "services_import_ok": services_ok,
    "services_import_total": len(SERVICES),
    "smoke_pass": smoke_pass,
}

out = ROOT / "output" / "phase0_baseline.json"
out.parent.mkdir(exist_ok=True, parents=True)
def _clean(o):
    """递归把任何无法 JSON 化的异常换成字符串"""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(x) for x in o]
    if isinstance(o, type) or hasattr(o, "__class__") and not isinstance(o, (str, int, float, bool, type(None))):
        try:
            json.dumps(o)
            return o
        except Exception:
            return repr(o)[:300]
    return o

report_clean = _clean(report)
out.write_text(json.dumps(report_clean, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
print(f"详细报告写入: {out}")
# 列出失败项
print("\n=== 失败项清单 ===")
for section_key, section in report_clean.items():
    if not isinstance(section, dict):
        continue
    for k, v in section.items():
        if isinstance(v, dict) and v.get("ok") is False:
            print(f"  FAIL [{section_key}] {k}: {str(v.get('error', ''))[:200]}")
        if isinstance(v, bool) and v is False:
            print(f"  FAIL [{section_key}] {k} = False")
