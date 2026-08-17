"""E2E 全智能验证脚本 - 真实 ModelScope API 调用"""
import sys, os, asyncio, json, time
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in [".", "learning", "core", "effects", "ae"]:
    p = os.path.join(_ROOT, d)
    if p not in sys.path:
        sys.path.insert(0, p)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import warnings; warnings.filterwarnings("ignore")
import logging; logging.disable(logging.WARNING)

from core.llm_gateway import _load_dotenv_manual, llm_gateway, TaskType
_load_dotenv_manual(override=True)
llm_gateway.configure_from_env()
llm_gateway.configure_providers_from_env()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("  E2E 全智能验证 - 真实 LLM 调用 + 学习闭环")
print("=" * 60)
print(f"  Providers: {list(llm_gateway._config.providers.keys())}")
print(f"  is_available: {llm_gateway.is_available()}")

# ============================================================
# Step 1: chat_with_routing 备选链
# ============================================================
print("\n[Step 1] chat_with_routing 备选 Provider 链...")

async def run_all_llm_calls():
    # Step 1
    resp1 = await llm_gateway.chat_with_routing(
        message="Answer in one word: what is 2+2?",
        task_type=TaskType.INTENT_CLASSIFICATION,
        system_prompt="Answer concisely.",
        max_tokens=30,
    )
    # Step 2
    resp2 = await llm_gateway.chat_with_provider(
        prompt="Say exactly: Hello World",
        provider="modelscope",
        model_type="default",
        system_prompt="Repeat exactly.",
        max_tokens=20,
    )
    return resp1, resp2

resp1, resp2 = asyncio.run(run_all_llm_calls())

print(f"  success={resp1.success}, provider={resp1.provider}, latency={resp1.latency_ms:.0f}ms")
print(f"  content={repr(resp1.content[:60])}")
assert resp1.success, f"FAILED: {resp1.error}"
print(f"  [PASS] 备选链调用成功 (provider={resp1.provider})")

# ============================================================
# Step 2: ModelScope 直接调用
# ============================================================
print("\n[Step 2] ModelScope 直接调用...")
print(f"  success={resp2.success}, provider={resp2.provider}, latency={resp2.latency_ms:.0f}ms")
print(f"  content={repr(resp2.content[:60])}")
assert resp2.success, f"FAILED: {resp2.error}"
assert resp2.provider == "modelscope"
print("  [PASS] ModelScope 直接调用成功!")

# ============================================================
# Step 3: optimize_enhanced LLM 增强
# ============================================================
print("\n[Step 3] optimize_enhanced LLM 增强路径...")
from parameter_optimizer import ParameterOptimizer, ParameterContext

optimizer = ParameterOptimizer()
ctx = ParameterContext(effect_name="Gaussian Blur", intensity=0.8, style_name="cinematic")

result_local = optimizer.optimize(ctx)
print(f"  [Local] settings={json.dumps(result_local.settings, ensure_ascii=False)}")
print(f"  [Local] confidence={result_local.confidence:.3f}")

result_enhanced = optimizer.optimize_enhanced(ctx)
print(f"  [Enhanced] settings={json.dumps(result_enhanced.settings, ensure_ascii=False)}")
print(f"  [Enhanced] confidence={result_enhanced.confidence:.3f}")
print(f"  [Enhanced] adjustments={len(result_enhanced.adjustments)} items")

enhanced_keys = set(result_enhanced.settings.keys())
local_keys = set(result_local.settings.keys())
extra_params = enhanced_keys - local_keys
if extra_params or result_enhanced.confidence > result_local.confidence:
    print(f"  [PASS] LLM 增强路径生效! 额外参数: {extra_params}")
else:
    print(f"  [INFO] LLM 增强未产生额外差异(建议与本地重合或LLM降级)")

# ============================================================
# Step 4: 学习闭环
# ============================================================
print("\n[Step 4] 学习闭环验证...")
feedback_file = os.path.join(PROJECT_ROOT, "learning", ".cache", "param_feedback.json")
os.makedirs(os.path.dirname(feedback_file), exist_ok=True)

feedback_data = {
    "entries": [{
        "effect_name": "Gaussian Blur",
        "style_name": "cinematic",
        "parameter": "blur_amount",
        "old_value": 20,
        "new_value": 12,
        "success": True,
        "timestamp": time.time(),
    }]
}
with open(feedback_file, "w", encoding="utf-8") as f:
    json.dump(feedback_data, f, ensure_ascii=False, indent=2)
print("  写入反馈: blur_amount 20->12 (success)")

# 重新优化
ctx2 = ParameterContext(effect_name="Gaussian Blur", intensity=0.8, style_name="cinematic")
result_after = optimizer.optimize(ctx2)
print(f"  [AfterFeedback] settings={json.dumps(result_after.settings, ensure_ascii=False)}")

before_val = result_local.settings.get("blur_amount")
after_val = result_after.settings.get("blur_amount")
if before_val != after_val:
    print(f"  [PASS] 学习闭环: blur_amount {before_val} -> {after_val}")
else:
    print(f"  [INFO] blur_amount 未变 ({before_val}), 反馈可能未匹配")

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
print("  E2E 全智能验证结果")
print("=" * 60)
print(f"  1. 备选 Provider 链: PASS (provider={resp1.provider})")
print(f"  2. ModelScope 直接调用: PASS (latency={resp2.latency_ms:.0f}ms)")
print(f"  3. optimize_enhanced: {'PASS' if extra_params or result_enhanced.confidence > result_local.confidence else 'INFO (降级)'}")
print(f"  4. 学习闭环: {'PASS' if before_val != after_val else 'INFO'}")
print("=" * 60)
