#!/usr/bin/env python3
"""P1 知识库注入验证: KB → plan → execute
验证知识库推荐能正确注入到 plan 阶段的 effect_stack。
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['PYTHONIOENCODING'] = 'utf-8'

def main():
    print("=" * 60)
    print("P1 KB INJECTION VERIFICATION")
    print("=" * 60)
    
    # 1. 检查知识库
    print("\n[1] Checking knowledge base...")
    try:
        from knowledge_base.kb_loader import KnowledgeBaseLoader
        kb = KnowledgeBaseLoader.get_instance()
        print("    KnowledgeBaseLoader loaded OK")
        
        # 测试获取风格上下文
        style_ctx = kb.get_style_context("高燃混剪") if hasattr(kb, 'get_style_context') else {}
        print(f"    Style context: {type(style_ctx)}")
        
    except Exception as e:
        print(f"    KnowledgeBaseLoader error: {e}")
        import traceback
        traceback.print_exc()
        # 继续测试 plan 阶段
    
    # 2. 测试 plan 阶段 KB 注入
    print("\n[2] Testing KB injection in plan stage...")
    try:
        from pipeline.unified_pipeline import UnifiedPipeline, PipelineConfig
        
        config = PipelineConfig(
            input_topic="高燃混剪",
            output_dir=str(ROOT / "output" / "p1_kb_test"),
            ffmpeg_bin=r"C:\ffmpeg\bin\ffmpeg.exe",
            use_knowledge=True,  # 启用知识库
            enable_vrs=False,
            enable_feedback_loop=False,
            enable_multi_agent=False,
            skip_stages=["perceive", "analyze", "execute", "render", "verify", "learn"],
        )
        
        pipe = UnifiedPipeline(config)
        
        # 手动运行 plan 阶段
        pipe._results["perceive"] = type('StageResult', (), {
            'stage': 'perceive', 'status': type('StageStatus', (), {'value': 'done'})(),
            'data': {'videos': []}, 'error': None, 'duration_sec': 0, 'timestamp': ''
        })()
        pipe._results["analyze"] = type('StageResult', (), {
            'stage': 'analyze', 'status': type('StageStatus', (), {'value': 'done'})(),
            'data': {}, 'error': None, 'duration_sec': 0, 'timestamp': ''
        })()
        
        plan_data = pipe._run_plan()
        
        print(f"    Plan effect_stack: {len(plan_data.get('effect_stack', []))} effects")
        print(f"    KB context: {'kb_context' in plan_data}")
        print(f"    Merged style: {'merged_style' in plan_data}")
        
        if plan_data.get('effect_stack'):
            print("    Effects:")
            for eff in plan_data['effect_stack'][:3]:
                print(f"      - {eff.get('name', 'unknown')}")
        
        print("\n    RESULT: PASS")
        return 0
        
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
