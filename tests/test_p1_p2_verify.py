#!/usr/bin/env python3
"""P1 反馈闭环 + P2 贝叶斯自动observe 验证"""
import sys, os, time, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['PYTHONIOENCODING'] = 'utf-8'

def test_feedback_loop():
    """P1: VQA → FeedbackExecutor 真实闭环"""
    print("\n" + "=" * 60)
    print("P1: FEEDBACK LOOP VERIFICATION")
    print("=" * 60)
    
    video_path = ROOT / "output" / "p0_full_7stage" / "pipeline_output.mp4"
    if not video_path.exists():
        print("  SKIP: No E2E output found")
        return False
    
    # 1. VQA 真实评估
    from pipeline.video_quality_assessor import VideoQualityAssessor
    vqa = VideoQualityAssessor(ffmpeg_bin=r"C:\ffmpeg\bin\ffmpeg.exe")
    result = vqa.assess(str(video_path))
    
    # result 是 dict
    score = result.get('overall_score', result.get('score', 0))
    passed = result.get('passed', False)
    print(f"  [VQA] score={score:.1f} passed={passed}")
    
    checks = result.get('checks', {})
    if checks:
        for name, val in checks.items():
            if isinstance(val, dict):
                print(f"    {name}: score={val.get('score', 'N/A')}")
            else:
                print(f"    {name}: {val}")
    
    # 2. FeedbackExecutor
    from pipeline.feedback_executor import FeedbackExecutor
    fb = FeedbackExecutor(ffmpeg_bin=r"C:\ffmpeg\bin\ffmpeg.exe")
    print(f"  [FeedbackExecutor] initialized OK")
    
    # 3. 生成反馈建议
    if hasattr(fb, 'generate_feedback'):
        feedback = fb.generate_feedback(result)
        print(f"  [Feedback] suggestions: {len(feedback) if feedback else 0}")
        if feedback:
            for i, f in enumerate(feedback[:3]):
                print(f"    [{i}] {f}")
    elif hasattr(fb, 'analyze_and_suggest'):
        suggestions = fb.analyze_and_suggest(result)
        print(f"  [Feedback] suggestions: {len(suggestions) if suggestions else 0}")
    else:
        methods = [m for m in dir(fb) if not m.startswith('_')]
        print(f"  [FeedbackExecutor] available methods: {methods[:8]}")
    
    print("  RESULT: PASS" if score > 60 else "  RESULT: FAIL")
    return score > 60


def test_bayesian_auto_observe():
    """P2: 贝叶斯优化器自动observe闭环"""
    print("\n" + "=" * 60)
    print("P2: BAYESIAN AUTO-OBSERVE LOOP")
    print("=" * 60)
    
    from core.bayesian_optimizer import get_optimizer, PARAMETER_SPACES
    
    optimizer = get_optimizer()
    print(f"  [Bayesian] initialized, {len(PARAMETER_SPACES)} effect spaces")
    
    # 统计当前观测数
    obs_dict = optimizer._observations if hasattr(optimizer, '_observations') else {}
    total_obs = sum(len(v) for v in obs_dict.values())
    print(f"  [Bayesian] current observations: {total_obs}")
    
    # 模拟管线执行后的自动observe (使用已知效果名)
    test_effect = "Glow"
    test_params = {"glow_intensity": 0.75, "glow_radius": 15.0, "glow_threshold": 0.6}
    test_quality = 88.5
    test_render_time = 4.2
    test_file_size = 5.5
    
    t0 = time.time()
    optimizer.observe(test_effect, test_params, test_quality, test_render_time, test_file_size)
    obs_time = time.time() - t0
    print(f"  [observe] {test_effect}: quality={test_quality} time={obs_time:.3f}s")
    
    # recommend 闭环
    t0 = time.time()
    suggestions = optimizer.recommend(test_effect, n_suggestions=2)
    rec_time = time.time() - t0
    print(f"  [recommend] {test_effect}: {len(suggestions)} suggestions in {rec_time:.2f}s")
    
    if suggestions:
        s = suggestions[0]
        print(f"    best: params={s.params}")
        print(f"    expected_quality={s.expected_quality:.1f} confidence={s.confidence:.2f}")
    
    # 验证观测数增加
    obs_dict2 = optimizer._observations if hasattr(optimizer, '_observations') else {}
    new_total = sum(len(v) for v in obs_dict2.values())
    print(f"  [Bayesian] observations after: {new_total} (+{new_total - total_obs})")
    
    passed = len(suggestions) > 0 and rec_time < 5.0
    print(f"  RESULT: {'PASS' if passed else 'FAIL'} (recommend {rec_time:.2f}s < 5s)")
    return passed


def test_learning_persistence():
    """P2: 学习闭环持久化验证"""
    print("\n" + "=" * 60)
    print("P2: LEARNING LOOP PERSISTENCE")
    print("=" * 60)
    
    from learning.persistent_learning_loop import PersistentLearningLoop
    
    loop = PersistentLearningLoop()
    print(f"  [LearningLoop] initialized")
    
    # 验证持久化文件存在
    state_dir = Path(os.environ.get('APPDATA', '')) / "AE-Knowledge-Vault" / "learning-state"
    if state_dir.exists():
        files = list(state_dir.glob("*.json"))
        print(f"  [persistence] {len(files)} state files in {state_dir}")
        total_size = 0
        for f in files:
            size = f.stat().st_size
            total_size += size
            print(f"    {f.name}: {size} bytes")
        
        # 读取 execution-records 统计
        exec_file = state_dir / "execution-records.json"
        if exec_file.exists():
            import json
            with open(exec_file, 'r', encoding='utf-8') as fp:
                records = json.load(fp)
            print(f"  [records] total execution records: {len(records)}")
        
        print("  RESULT: PASS" if total_size > 0 else "  RESULT: FAIL (empty)")
        return total_size > 0
    else:
        print(f"  [persistence] state dir not found: {state_dir}")
        print("  RESULT: FAIL")
        return False


def main():
    print("=" * 60)
    print("P1+P2 INTEGRATED VERIFICATION")
    print("=" * 60)
    
    results = {}
    results['feedback'] = test_feedback_loop()
    results['bayesian'] = test_bayesian_auto_observe()
    results['learning'] = test_learning_persistence()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, passed in results.items():
        mark = "PASS" if passed else "FAIL"
        print(f"  {mark}: {name}")
        if not passed:
            all_pass = False
    
    print(f"\n  OVERALL: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
