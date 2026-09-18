"""
闭环验证脚本：验证 P0-2 修复后参数反馈是否真正写入并被回读

验证逻辑：
  1. 模拟管线执行后 _trigger_param_feedback 的写入行为
  2. 验证 param_feedback.json 文件确实被创建
  3. 调用 optimize_with_feedback 验证反馈数据被读取并影响参数
  4. 对比有反馈 vs 无反馈的参数差异
"""
import json
import os
import sys

# 设置路径
PROJECT_ROOT = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"
sys.path.insert(0, os.path.join(PROJECT_ROOT, "learning"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "effects"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "knowledge_base"))

FEEDBACK_FILE = os.path.join(PROJECT_ROOT, "learning", ".cache", "param_feedback.json")

def cleanup():
    """清理旧反馈文件，确保测试干净"""
    if os.path.isfile(FEEDBACK_FILE):
        os.remove(FEEDBACK_FILE)
        print("[清理] 已删除旧反馈文件")

def step1_write_feedback():
    """模拟 _trigger_param_feedback 写入"""
    print("\n" + "=" * 60)
    print(" Step 1: 模拟管线完成后写入反馈")
    print("=" * 60)

    from parameter_optimizer import enhanced_optimizer

    # 模拟3轮管线执行的效果参数反馈
    feedbacks = [
        {"effect": "ADBE Glo2", "params": {"Glow Radius": 30, "Glow Intensity": 1.2}, "rating": 0.85, "style": "cyberpunk"},
        {"effect": "ADBE Glo2", "params": {"Glow Radius": 25, "Glow Intensity": 1.5}, "rating": 0.9, "style": "cyberpunk"},
        {"effect": "ADBE Gaussian Blur 2", "params": {"Blurriness": 12}, "rating": 0.7, "style": None},
    ]

    for i, fb in enumerate(feedbacks):
        enhanced_optimizer.record_feedback(
            effect_name=fb["effect"],
            parameters=fb["params"],
            rating=fb["rating"],
            style_name=fb["style"],
        )
        print(f"  写入 #{i+1}: {fb['effect']} rating={fb['rating']} params={fb['params']}")

    # 验证文件存在
    if os.path.isfile(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = len(data.get("records", []))
        print(f"\n  ✅ 反馈文件已创建: {FEEDBACK_FILE}")
        print(f"  ✅ 记录数: {count}")
        return count > 0
    else:
        print("\n  ❌ 反馈文件未创建!")
        return False

def step2_verify_readback():
    """验证 optimize_with_feedback 能读取反馈并影响参数"""
    print("\n" + "=" * 60)
    print(" Step 2: 验证反馈被 optimize_with_feedback 回读")
    print("=" * 60)

    from parameter_optimizer import EnhancedParameterOptimizer, ParameterContext

    optimizer = EnhancedParameterOptimizer()

    # 测试1: 有反馈的优化
    ctx_glow = ParameterContext(effect_name="ADBE Glo2", style_name="cyberpunk")
    result_with_fb = optimizer.optimize_with_feedback(ctx_glow, use_feedback=True)
    result_no_fb = optimizer.optimize_with_feedback(ctx_glow, use_feedback=False)

    print("\n  [Glow 效果]")
    print(f"  无反馈优化: {result_no_fb.settings}")
    print(f"  有反馈优化: {result_with_fb.settings}")
    print(f"  无反馈置信度: {result_no_fb.confidence}")
    print(f"  有反馈置信度: {result_with_fb.confidence}")

    # 检查是否有差异
    has_diff = False
    for key in result_with_fb.settings:
        if key in result_no_fb.settings:
            v1 = result_no_fb.settings[key]
            v2 = result_with_fb.settings[key]
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                if abs(v1 - v2) > 0.001:
                    has_diff = True
                    print(f"  📊 {key}: {v1} → {v2} (反馈影响)")

    if has_diff:
        print("\n  ✅ 反馈数据确实影响了参数优化结果！")
    else:
        print("\n  ⚠️ 参数无差异，可能反馈数据与规则表值接近")

    # 检查 adjustments 中是否有 feedback_weighted 标记
    fb_adjustments = [a for a in result_with_fb.adjustments if a.get("reason") == "feedback_weighted"]
    if fb_adjustments:
        print(f"  ✅ 发现 {len(fb_adjustments)} 个 feedback_weighted 调整:")
        for adj in fb_adjustments:
            print(f"     {adj['parameter']}: {adj['from']} → {adj['to']}")
    
    # 测试2: Blur 效果
    ctx_blur = ParameterContext(effect_name="ADBE Gaussian Blur 2")
    result_blur_fb = optimizer.optimize_with_feedback(ctx_blur, use_feedback=True)
    result_blur_no = optimizer.optimize_with_feedback(ctx_blur, use_feedback=False)

    print("\n  [Blur 效果]")
    print(f"  无反馈: Blurriness={result_blur_no.settings.get('Blurriness')}")
    print(f"  有反馈: Blurriness={result_blur_fb.settings.get('Blurriness')}")

    blur_diff = (result_blur_fb.settings.get('Blurriness', 0) != result_blur_no.settings.get('Blurriness', 0))
    if blur_diff:
        print("  ✅ Blur 参数被反馈修正！")

    return has_diff or blur_diff or len(fb_adjustments) > 0

def step3_multi_round():
    """模拟多轮管线运行，观察反馈积累效果"""
    print("\n" + "=" * 60)
    print(" Step 3: 多轮积累验证（模拟管线连续运行）")
    print("=" * 60)

    from parameter_optimizer import EnhancedParameterOptimizer, ParameterContext, enhanced_optimizer

    # 再追加2轮高评分反馈
    for i in range(2):
        enhanced_optimizer.record_feedback(
            effect_name="ADBE Glo2",
            parameters={"Glow Radius": 28, "Glow Intensity": 1.4},
            rating=0.95,
            style_name="cyberpunk",
        )

    optimizer = EnhancedParameterOptimizer()
    ctx = ParameterContext(effect_name="ADBE Glo2", style_name="cyberpunk")
    result = optimizer.optimize_with_feedback(ctx, use_feedback=True)

    print("  追加2轮高评分(0.95)反馈后:")
    print(f"  Glow Radius = {result.settings.get('Glow Radius')}")
    print(f"  Glow Intensity = {result.settings.get('Glow Intensity')}")
    print(f"  置信度 = {result.confidence}")

    fb_adj = [a for a in result.adjustments if a.get("reason") == "feedback_weighted"]
    if fb_adj:
        print(f"  ✅ 反馈权重调整数: {len(fb_adj)}")
        for a in fb_adj:
            print(f"     {a['parameter']}: {a['from']:.2f} → {a['to']:.2f}")

    # 检查反馈文件记录数
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    total = len(data.get("records", []))
    print(f"\n  反馈总记录数: {total}")
    print("  ✅ 多轮积累正常" if total >= 5 else "  ❌ 记录数不足")
    return total >= 5

def main():
    print("=" * 60)
    print(" 闭环验证：Py 参数反馈写入→回读→影响优化")
    print("=" * 60)

    cleanup()

    ok1 = step1_write_feedback()
    ok2 = step2_verify_readback() if ok1 else False
    ok3 = step3_multi_round() if ok1 else False

    print("\n" + "=" * 60)
    print(" 总结")
    print("=" * 60)
    print(f"  写入反馈: {'✅' if ok1 else '❌'}")
    print(f"  回读影响优化: {'✅' if ok2 else '⚠️'}")
    print(f"  多轮积累: {'✅' if ok3 else '❌'}")
    all_ok = ok1 and ok2 and ok3
    print(f"\n  {'✅ Py 侧反馈闭环完整验证通过！' if all_ok else '⚠️ 存在问题需排查'}")
    print("=" * 60)

if __name__ == "__main__":
    main()
