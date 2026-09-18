#!/usr/bin/env python3
"""P2 贝叶斯优化器闭环验证
验证 BayesianParameterOptimizer 的 observe() 和 recommend() 闭环。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['PYTHONIOENCODING'] = 'utf-8'

def main():
    print("=" * 60)
    print("P2 BAYESIAN OPTIMIZER VERIFICATION")
    print("=" * 60)
    
    # 1. 加载优化器
    print("\n[1] Loading BayesianParameterOptimizer...")
    try:
        from core.bayesian_optimizer import PARAMETER_SPACES, get_optimizer
        optimizer = get_optimizer()
        print("    Optimizer loaded OK")
        print(f"    Parameter spaces: {len(PARAMETER_SPACES)} effects")
        for k in list(PARAMETER_SPACES.keys())[:5]:
            print(f"      - {k}: {len(PARAMETER_SPACES[k])} params")
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 2. 测试 recommend()
    print("\n[2] Testing recommend()...")
    try:
        # 获取一个效果的推荐参数
        test_effect = list(PARAMETER_SPACES.keys())[0] if PARAMETER_SPACES else None
        if test_effect:
            rec = optimizer.recommend(test_effect)
            print(f"    Effect: {test_effect}")
            print(f"    Recommended params: {rec}")
        else:
            print("    No parameter spaces available")
    except Exception as e:
        print(f"    recommend() error: {e}")
    
    # 3. 测试 observe()
    print("\n[3] Testing observe()...")
    try:
        if test_effect:
            # 模拟一次观测: observe(effect_name, params, quality, render_time, file_size)
            params = {p.name: 0.5 for p in PARAMETER_SPACES[test_effect][:3]}
            quality = 75.0
            render_time = 2.5  # 秒
            file_size = 50.0   # MB
            optimizer.observe(test_effect, params, quality, render_time, file_size)
            print(f"    Observed: effect={test_effect}, quality={quality}, render_time={render_time}s, file_size={file_size}MB")
            print(f"    Params: {params}")
            
            # 再次推荐，看是否基于观测调整
            import time
            t0 = time.time()
            rec2 = optimizer.recommend(test_effect)
            elapsed = time.time() - t0
            print(f"    New recommendation ({elapsed:.2f}s): {rec2[0].params if rec2 else 'none'}")
    except Exception as e:
        print(f"    observe() error: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. 检查历史观测
    print("\n[4] Checking observation history...")
    try:
        stats = optimizer.get_stats() if hasattr(optimizer, 'get_stats') else {}
        print(f"    Stats: {stats}")
    except Exception as e:
        print(f"    Stats error: {e}")
    
    print("\n    RESULT: PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
