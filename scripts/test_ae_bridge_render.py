"""快速验证 AE Bridge 渲染路径"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from pipeline.stages.execution import ExecutionStage


class FakeConfig:
    output_dir = "output_p0_e2e/ae_test"
    project_name = "ae_bridge_test"
    input_topic = "AE Bridge Test"
    ffmpeg_bin = r"C:\ffmpeg\bin\ffmpeg.exe"

def main():
    os.makedirs("output_p0_e2e/ae_test", exist_ok=True)
    
    stage = ExecutionStage(FakeConfig())
    
    print("1. Testing Bridge ping...")
    r = stage._send_bridge_command("ping", {}, timeout=5.0)
    if r.get("status") != "success":
        print(f"   FAIL: Bridge not responding: {r}")
        return False
    print(f"   OK: {r}")
    
    print("2. Creating composition...")
    jsx_create = '''(function(){try{
        var c = app.project.items.addComp("BridgeTestComp", 1920, 1080, 1, 3, 30);
        c.openInViewer();
        return JSON.stringify({success:true, data:{compName: c.name}});
    }catch(e){return JSON.stringify({success:false,error:{message:e.toString()}});}})();'''
    r = stage._send_bridge_command("runScript", {"code": jsx_create}, timeout=10.0)
    print(f"   Result: {r}")
    time.sleep(1)  # Wait for comp to open
    
    print("3. Adding solid layer...")
    jsx = '''(function(){try{
        var c = app.project.activeItem;
        if(!c || !(c instanceof CompItem)) return JSON.stringify({success:false,error:{message:"no comp"}});
        var solid = c.layers.addSolid([0.2, 0.6, 1.0], "TestSolid", c.width, c.height, 1, c.duration);
        return JSON.stringify({success:true, data:{layerName: solid.name}});
    }catch(e){return JSON.stringify({success:false,error:{message:e.toString()}});}})();'''
    r = stage._send_bridge_command("runScript", {"code": jsx}, timeout=10.0)
    print(f"   Result: {r}")
    
    print("4. Rendering via Bridge...")
    output_path = os.path.abspath("output_p0_e2e/ae_test/bridge_render_test.mp4")
    render_ok = stage._render_via_bridge(output_path, duration=3.0)
    
    if render_ok and os.path.isfile(output_path):
        size = os.path.getsize(output_path)
        print(f"   SUCCESS: {output_path} ({size // 1024}KB)")
        if size > 10240:
            print("   AE Bridge render path: VERIFIED")
            return True
        else:
            print(f"   WARNING: File too small ({size}B)")
            return False
    else:
        print(f"   FAIL: render_ok={render_ok}, file_exists={os.path.isfile(output_path)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
