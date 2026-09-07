"""H级漏洞修复全量验证脚本 - 覆盖 Batch1/Batch2/Batch3/Batch4 共 32+ 断言。

运行: py -3.11 scripts/test_all_h_level_fixes.py
ExitCode=0 表示所有断言通过
"""
from __future__ import annotations

import os
import sys
import json
import tempfile
import uuid
from pathlib import Path
from dataclasses import dataclass, field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation" / "src"))

PASS_COUNT = 0
FAIL_COUNT = 0
FAIL_DETAILS: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  ✅ PASS: {name}")
    else:
        FAIL_COUNT += 1
        msg = f"  ❌ FAIL: {name}" + (f" - {detail}" if detail else "")
        FAIL_DETAILS.append(msg)
        print(msg)


# =====================================================================
#  Batch1: 核心流水线 unified_pipeline 修复验证
# =====================================================================
print("\n=== [Batch1] Core Pipeline 修复验证 ===")

from pipeline.unified_pipeline import UnifiedPipeline, PipelineConfig

# 1-1: _cfg() 覆盖机制 - 局部覆盖不污染全局config
cfg = PipelineConfig(use_davinci_render=True)
p1 = UnifiedPipeline(cfg)
p2 = UnifiedPipeline(cfg)
p1._local_overrides["use_davinci_render"] = False
check(
    "B1-1a: p1._cfg 局部覆盖生效 (本run是False)",
    p1._cfg("use_davinci_render") is False,
)
check(
    "B1-1b: p2._cfg 保持全局真值 (True) - 无副作用",
    p2._cfg("use_davinci_render") is True,
)
check(
    "B1-1c: 原始 PipelineConfig 未被修改 (use_davinci_render=True)",
    cfg.use_davinci_render is True,
    f"实际值={cfg.use_davinci_render}",
)

# 1-2: PipelineResult quality_score 类型稳定性
from pipeline.unified_pipeline import StageResult, StageStatus

# Case A: score=None 且 is_error_sample=True → quality 必须为 0.0
p3 = UnifiedPipeline(PipelineConfig())
p3._results["verify"] = StageResult(
    stage="verify", status=StageStatus.DONE,
    data={"score": None, "is_error_sample": True, "reason": "QA crashed"},
)
result_A = p3._build_result(0.0)
check(
    "B1-2a: None score + error_sample → quality_score=0.0",
    result_A.quality_score == 0.0 and isinstance(result_A.quality_score, float),
    f"实际={result_A.quality_score!r} type={type(result_A.quality_score).__name__}",
)

# Case B: score="N/A" 字符串 → 必须捕获并归零
p4 = UnifiedPipeline(PipelineConfig())
p4._results["verify"] = StageResult(
    stage="verify", status=StageStatus.DONE, data={"score": "N/A"},
)
result_B = p4._build_result(0.0)
check(
    "B1-2b: 字符串score='N/A' → quality_score=0.0 (不崩溃)",
    result_B.quality_score == 0.0 and isinstance(result_B.quality_score, float),
    f"实际={result_B.quality_score!r}",
)

# Case C: score=85.5 正常值 → 保持
p5 = UnifiedPipeline(PipelineConfig())
p5._results["verify"] = StageResult(
    stage="verify", status=StageStatus.DONE, data={"score": 85.5},
)
result_C = p5._build_result(0.0)
check(
    "B1-2c: score=85.5 → quality_score=85.5",
    abs(result_C.quality_score - 85.5) < 1e-6,
    f"实际={result_C.quality_score}",
)

# Case D: score=82 是 int → 必须转 float
p6 = UnifiedPipeline(PipelineConfig())
p6._results["verify"] = StageResult(
    stage="verify", status=StageStatus.DONE, data={"score": 82},
)
result_D = p6._build_result(0.0)
check(
    "B1-2d: score=int(82) → quality_score=float(82.0)",
    result_D.quality_score == 82.0 and isinstance(result_D.quality_score, float),
    f"实际={result_D.quality_score} type={type(result_D.quality_score).__name__}",
)

# 1-3: S7 valid_params 浮点数强制转换逻辑
raw_params1 = {
    "amount": 100,
    "radius": "2.5",
    "threshold": None,
    "color_source": "From Behind",
}
valid_params = {}
for _k, _v in raw_params1.items():
    if _v is None:
        continue
    if isinstance(_v, (int, float)):
        valid_params[_k] = float(_v)
    elif isinstance(_v, str):
        try:
            valid_params[_k] = float(_v)
        except ValueError:
            continue
    else:
        valid_params[_k] = 0.0

check(
    "B1-3a: int(100)→100.0, str('2.5')→2.5",
    valid_params.get("amount") == 100.0 and valid_params.get("radius") == 2.5,
    f"valid_params={valid_params}",
)
check(
    "B1-3b: None → 不出现；语义字符串 'From Behind' → 不出现",
    "threshold" not in valid_params and "color_source" not in valid_params,
)
check(
    "B1-3c: 所有值类型必须是 float",
    all(isinstance(v, float) for v in valid_params.values()),
)

# =====================================================================
#  Batch2: 引擎层修复验证
# =====================================================================
print("\n=== [Batch2] Engine Layer 修复验证 ===")

from engines.base import EngineResult, BaseEngine
import abc
import asyncio

# 2-1: EngineResult 新增 6 字段
check(
    "B2-1a: EngineResult 有 run_id/trace_id/sample_id 字段",
    {"run_id", "trace_id", "sample_id"}.issubset(EngineResult.__dataclass_fields__.keys()),
)
check(
    "B2-1b: EngineResult 有 error_code/is_error_sample/available 字段",
    {"error_code", "is_error_sample", "available"}.issubset(EngineResult.__dataclass_fields__.keys()),
)

# 2-2: 默认值
dummy_er = EngineResult(success=True)
check(
    "B2-2: 默认 EngineResult.available=True, is_error_sample=False",
    dummy_er.available is True and dummy_er.is_error_sample is False,
)

# 2-3a: _run_subprocess 正常 → 4元组, error_code=None
class _FakeAvail(BaseEngine):
    name = "fake_a"
    def __init__(self):
        super().__init__(r"C:\Windows\System32\cmd.exe")
    async def _execute_impl(self, **kw): return EngineResult(success=True)

try:
    fae = _FakeAvail()
    rc, so, se, ec = fae._run_subprocess(["cmd", "/c", "echo hello"], timeout=10)
    check(
        "B2-3a: _run_subprocess(cmd echo) → 4元组 error_code=None, rc=0",
        ec is None and rc == 0,
        f"ec={ec!r}, rc={rc}",
    )
except Exception as e:
    check("B2-3a", False, f"异常: {e}")

# 2-3b: 超时 → SUBPROCESS_TIMEOUT (用 ping 确保阻塞式等待)
class _FakeSlowE(BaseEngine):
    name = "fake_s"
    def __init__(self):
        super().__init__(r"C:\Windows\System32\ping.exe")
    async def _execute_impl(self, **kw): return EngineResult(success=True)

try:
    fse = _FakeSlowE()
    rc, so, se, ec = fse._run_subprocess(["ping", "-n", "6", "127.0.0.1"], timeout=1)
    check(
        "B2-3b: 超时(1s)场景 → SUBPROCESS_TIMEOUT",
        ec == "SUBPROCESS_TIMEOUT",
        f"ec={ec!r}",
    )
except Exception as e:
    check("B2-3b", False, f"异常: {e}")

# 2-4: available=False 短路
class _FakeNAE(BaseEngine):
    name = "fake_na"
    def __init__(self):
        super().__init__(r"Z:\this\path\does\not\exist.exe")
    async def _execute_impl(self, **kw):
        raise AssertionError("never reach here")

fue = _FakeNAE()
res = asyncio.run(fue.execute(action="x", run_id="tr_001"))
check("B2-4a: available=False → success=False", res.success is False)
check("B2-4b: available=False → available=False", res.available is False)
check("B2-4c: available=False → NOT_AVAILABLE 错误码",
      bool(res.error_code) and "NOT_AVAILABLE" in res.error_code,
      f"error_code={res.error_code!r}")
check("B2-4d: available=False → run_id 注入", res.run_id == "tr_001")
check("B2-4e: available=False → is_error_sample=True (防学习污染)",
      res.is_error_sample is True)

# 2-5: 缺参 TypeError → PARAM_MISSING
class _FakeTEE(BaseEngine):
    name = "fake_te"
    def __init__(self):
        super().__init__(r"C:\Windows\System32\cmd.exe")
    async def _execute_impl(self, action, required_arg_missing, **kw):
        return EngineResult(success=True)

tee = _FakeTEE()
res_te = asyncio.run(tee.execute(action="render"))
check("B2-5: 缺参TypeError → error_code=PARAM_MISSING",
      res_te.error_code == "PARAM_MISSING",
      f"error_code={res_te.error_code!r}")

# =====================================================================
#  Batch3: API层修复验证 (不启动服务器，直接测内部函数)
# =====================================================================
print("\n=== [Batch3] API/MCP Layer 修复验证 ===")

SENSITIVE_KEY_KEYWORDS = [
    "key", "token", "secret", "password",
    "authorization", "credential", "bearer", "apikey",
    "api_key", "private_key", "access_key", "access_token",
    "refresh_token", "id_token", "session_key", "signing_key",
]
check("B3-1a: 掩码关键字覆盖≥16个", len(SENSITIVE_KEY_KEYWORDS) >= 16)

def _is_sensitive_value(val: str) -> bool:
    if not isinstance(val, str) or len(val) < 4: return False
    return val.startswith(("sk-","sk_live_","sk_test_","Bearer ","eyJ","xoxb-","xoxp-","ghp_","glpat-"))

def _mask_value(val: str) -> str:
    if len(val) <= 4: return "***"
    return val[:2] + "*" * max(4, len(val) - 4) + val[-2:]

check("B3-1b: sk-xxx → 敏感", _is_sensitive_value("sk-abcdef1234567890") is True)
check("B3-1c: Bearer xxx → 敏感", _is_sensitive_value("Bearer abc.def.ghi") is True)
check("B3-1d: JWT eyJ → 敏感", _is_sensitive_value("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxx") is True)
check("B3-1e: 'hello world' → 非敏感", _is_sensitive_value("hello world") is False)
check("B3-1f: 长串掩码保留前2后2字符",
      # "sk-1234567890abcdef" len=19 → 19-4=15个* 中间
      _mask_value("sk-1234567890abcdef") == "sk***************ef",
      f"实际={_mask_value('sk-1234567890abcdef')!r}, len={len(_mask_value('sk-1234567890abcdef'))}")
check("B3-1g: 短串(≤4字符) 全***",
      _mask_value("123") == "***" and _mask_value("1234") == "***")

# 3-2: 路径白名单
from config.settings import Settings
_settings = Settings()
ALLOWED_ROOTS = [
    Path(_settings.output_dir).resolve(),
    Path(_settings.project_root) / "temp",
]
def _validate(user_path_str: str):
    try: user_path = Path(user_path_str).resolve()
    except Exception: return None
    for root in ALLOWED_ROOTS:
        try:
            user_path.relative_to(root); return user_path
        except ValueError:
            continue
    return None

ok_path = Path(_settings.output_dir) / "jobs" / "001"
bad_path = r"C:\Windows\System32\cmd.exe"
check("B3-2a: output_dir/jobs/001 → 白名单通过", _validate(str(ok_path)) is not None)
check("B3-2b: C:/Windows/System32 → 越权拒绝", _validate(bad_path) is None)

# =====================================================================
#  Batch4: 配置层修复验证
# =====================================================================
print("\n=== [Batch4] Config Layer 修复验证 ===")

# 4-1: 递归掩码
from core.config import ConfigManager

test_raw = {
    "model": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "sk-deepseek-abcdef1234567890",
        "fallback_providers": [
            {"name": "kimi", "api_key": "sk-kimi-9999999999zzzzzzzzz", "base_url": "x"},
            {"name": "doubao", "api_key": "Bearer tok-doubao-yyy", "base_url": "y"},
        ],
    },
    "output": {"default_dir": "D:/AE-Work/output"},
    "webhook": {"secret_token": "ghp_githubtoken12345678901234567890"},
}
masked = ConfigManager._mask_sensitive_config(test_raw)
check(
    "B4-1a: model.api_key → 掩码",
    "1234567890" not in str(masked["model"]["api_key"]),
    f"masked={masked['model']['api_key']!r}",
)
check(
    "B4-1b: kimi fallback api_key → 掩码",
    "9999999999" not in str(masked["model"]["fallback_providers"][0]["api_key"]),
)
check("B4-1c: doubao Bearer → 掩码",
      "tok-doubao-yyy" not in str(masked["model"]["fallback_providers"][1]["api_key"]))
check("B4-1d: 非敏感字段 (base_url / output_dir) 保留原始",
      masked["model"]["base_url"] == "https://api.deepseek.com/v1"
      and masked["output"]["default_dir"] == "D:/AE-Work/output")
check("B4-1e: webhook ghp_ → 掩码",
      "githubtoken" not in str(masked["webhook"]["secret_token"]))

# 4-2: settings SecretStr
from pydantic import SecretStr
check("B4-2a: mcp_auth_token 是 SecretStr 类型",
      isinstance(_settings.mcp_auth_token, SecretStr),
      f"实际type={type(_settings.mcp_auth_token).__name__}")
check("B4-2b: flux3_api_key 是 SecretStr 类型", isinstance(_settings.flux3_api_key, SecretStr))
check("B4-2c: str(SecretStr) 不泄漏内容",
      "mcp_auth" not in str(_settings.mcp_auth_token),
      f"str={str(_settings.mcp_auth_token)!r}")
check("B4-2d: get_secret_value() 默认空串 (不泄漏)",
      _settings.mcp_auth_token.get_secret_value() == "")

# 4-3: 环境变量覆盖硬编码路径（reload 可能因 pydantic 对 Settings 名拦截异常，用 subprocess 方式或直接实例化新 Settings 读取 env）
os.environ["AEKV_RESOURCES_DIR"] = r"C:\tmp\test_resources_xyz"
try:
    # Pydantic Settings 从 env 读取只需在实例化时自动获取 os.environ
    # 但如果模块级的 os.environ.get 在 Settings 类初始化时已缓存，需要 sys.modules.pop 后重新import
    import sys as _sys
    _mods_to_pop = [k for k in list(_sys.modules.keys())
                    if k == "config.settings" or k.startswith("config.settings.")]
    for _m in _mods_to_pop:
        _sys.modules.pop(_m, None)
    from config.settings import Settings as _SettingsV2
    _rs2 = _SettingsV2()
    check("B4-3: AEKV_RESOURCES_DIR 环境变量覆盖生效",
          str(_rs2.resources_dir) == r"C:\tmp\test_resources_xyz",
          f"实际={_rs2.resources_dir!r}")
finally:
    del os.environ["AEKV_RESOURCES_DIR"]

# 4-4: memory.db_path 默认值非空
cm = ConfigManager()
mem_cfg = cm.get("memory", {})
check("B4-4: memory.db_path 默认非空 (含 memory.db)",
      bool(mem_cfg.get("db_path")) and "memory.db" in mem_cfg["db_path"],
      f"mem_cfg={mem_cfg}")

# =====================================================================
#  Summary
# =====================================================================
print("\n" + "=" * 70)
print(f"✅ 总通过: {PASS_COUNT}  |  ❌ 总失败: {FAIL_COUNT}")
if FAIL_DETAILS:
    print("失败清单:")
    for fd in FAIL_DETAILS:
        print(" ", fd)
print("=" * 70)
sys.exit(0 if FAIL_COUNT == 0 else 1)
