#!/usr/bin/env python3
"""P0 学习闭环验证: PersistentLearningLoop 真实写入+读取
验证 learn 阶段正确写入学习记录，且下次运行能读取。
"""
import sys
import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['PYTHONIOENCODING'] = 'utf-8'

def main():
    print("=" * 60)
    print("P0 LEARNING LOOP VERIFICATION")
    print("=" * 60)
    
    # 1. 检查学习状态目录
    state_dir = Path(os.environ.get("APPDATA", "~")) / "AE-Knowledge-Vault" / "learning-state"
    print(f"\n[1] Learning state dir: {state_dir}")
    print(f"    Exists: {state_dir.exists()}")
    
    if state_dir.exists():
        files = list(state_dir.glob("*.json"))
        print(f"    JSON files: {len(files)}")
        for f in files:
            print(f"      - {f.name} ({f.stat().st_size} bytes)")
    
    # 2. 读取当前记录数
    records_file = state_dir / "execution-records.json"
    before_count = 0
    if records_file.exists():
        with open(records_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        before_count = len(records)
        print(f"\n[2] Current records: {before_count}")
        if records:
            last = records[-1]
            print(f"    Last record: {last.get('timestamp', 'unknown')}")
            print(f"    Last effect: {last.get('expected', {}).get('effect_name', 'unknown')}")
    
    # 3. 测试写入
    print("\n[3] Testing PersistentLearningLoop write...")
    try:
        from learning.persistent_learning_loop import PersistentLearningLoop
        from learning.learning_loop import (
            ExpectedParameters,
            ExpectedProperty,
            ExecutionResult,
            VerificationResult,
        )
        
        learner = PersistentLearningLoop()
        
        # 构建测试数据
        expected = ExpectedParameters(
            comp_name="test_comp",
            layer_index=0,
            effect_match_name="ADBE Gaussian Blur 2",
            effect_name="gaussian_blur",
            properties=[
                ExpectedProperty(name="blurriness", value=10.0),
                ExpectedProperty(name="direction", value=0.0),
            ],
        )
        execution = ExecutionResult(
            success=True,
            error_code=None,
            error_message=None,
            effect_name="gaussian_blur",
            execution_time_ms=100,
        )
        verification = VerificationResult(
            passed=True,
            deviation_score=0.1,
            reason="Test verification",
        )
        
        # 写入记录
        learner.record_execution(
            user_input="P0学习闭环测试",
            intent_type="test",
            expected=expected,
            execution=execution,
            verification=verification,
            user_feedback=None,
            reasoning_path=["test_path"],
        )
        
        print("    Write OK")
        
        # 4. 验证写入
        stats = learner.get_stats()
        after_count = stats.get("execution_records_count", 0)
        print(f"\n[4] After write: {after_count} records")
        
        if after_count > before_count:
            print(f"    Delta: +{after_count - before_count} records")
            print("\n    RESULT: PASS (write verified)")
            return 0
        else:
            print("    WARNING: Record count did not increase")
            print("\n    RESULT: FAIL")
            return 1
            
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
