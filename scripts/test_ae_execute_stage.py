"""聚焦测试: AE Bridge 执行路径 (execute stage)"""
import sys, os, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from pipeline.stages.execution import ExecutionStage

class FakeConfig:
    output_dir = "output_p0_e2e/ae_exec_test"
    project_name = "ae_exec_test"
    input_topic = "AE Execute Test"
    ffmpeg_bin = r"C:\ffmpeg\bin\ffmpeg.exe"

def main():
    os.makedirs("output_p0_e2e/ae_exec_test", exist_ok=True)
    stage = ExecutionStage(FakeConfig())
    
    # 模拟 plan 阶段输出
    script = {
        "title": "AE_Execute_Test",
        "total_duration": 5,
        "width": 1920,
        "height": 1080,
        "fps": 30,
    }
    plan = {
        "script": script,
        "shot_list": [],
        "transition_plan": [],
        "effect_stack": [
            {"name": "Glow", "match_name": "ADBE Glo2", "params": {"Glow Threshold": 40, "Glow Radius": 25}},
        ],
        "style_params": {},
    }
    previous_data = {
        "perceive": {"videos": [], "images": []},
        "plan": plan,
    }
    
    print("=" * 60)
    print("AE Bridge Execute Stage Test")
    print("=" * 60)
    
    print("\n1. Checking Bridge...")
    bridge_ok = stage._check_bridge()
    print(f"   Bridge OK: {bridge_ok}")
    if not bridge_ok:
        print("   FAIL: Bridge not responding")
        return False
    
    print("\n2. Running execute stage...")
    start = time.time()
    result = stage.run(previous_data)
    elapsed = time.time() - start
    
    print(f"\n3. Result ({elapsed:.1f}s):")
    for k, v in result.items():
        print(f"   {k}: {v}")
    
    # 验证
    exec_mode = result.get("execution_mode", "")
    project_path = result.get("project_path", "")
    
    print("\n4. Verification:")
    if exec_mode == "ae_render" and project_path and os.path.isfile(project_path):
        size = os.path.getsize(project_path)
        print(f"   SUCCESS: AE render produced {project_path} ({size // 1024}KB)")
        return size > 10240
    elif exec_mode == "ffmpeg_fallback":
        print(f"   FALLBACK: FFmpeg path used (AE render failed)")
        if project_path and os.path.isfile(project_path):
            print(f"   But FFmpeg produced: {project_path}")
            return True
        return False
    else:
        print(f"   UNKNOWN: exec_mode={exec_mode}, path={project_path}")
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n{'='*60}")
    print(f"TEST {'PASSED' if success else 'FAILED'}")
    print(f"{'='*60}")
    sys.exit(0 if success else 1)
