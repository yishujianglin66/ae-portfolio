#!/usr/bin/env python3
"""临时测试：验证 AE 引擎实际脚本执行能力。"""
import sys
import asyncio
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "puppet-automation"))

from src.engines.ae.engine import AEEngine  # noqa: E402


@pytest.mark.real_ae
async def test_ae_operations():
    ae = AEEngine()
    print("Testing AE high-level operations...")
    
    # Test 1: Create a comp (this creates a .aep project)
    try:
        print("\n--- Test 1: create_comp ---")
        result = await ae.create_comp(
            name="PuppetTest_Comp",
            width=1920,
            height=1080,
            fps=30,
            duration=5.0
        )
        print(f'create_comp result: success={result.success}')
        if result.error:
            print(f'  error: {str(result.error)[:200]}')
        if result.metadata:
            print(f'  metadata: {list(result.metadata.keys())}')
    except Exception as e:
        print(f'create_comp error: {e}')
    
    # Test 2: Run a test JSX script
    try:
        print("\n--- Test 2: run_script ---")
        test_jsx = """
#target aftereffects
app.beginUndoGroup("Test from Puppet");
var comp = app.project.items.addComp("Test_Python_Comp", 1920, 1080, 1, 3, 30);
var solid = comp.layers.addSolid([1, 0, 0], "Red Solid", comp.width, comp.height, 1);
app.endUndoGroup();
alert("AE Python integration test successful!");
"""
        result = await ae.run_script(script_content=test_jsx)
        print(f'run_script result: success={result.success}')
        if result.error:
            print(f'  error: {str(result.error)[:200]}')
        if result.metadata and result.metadata.get('stdout'):
            print(f'  stdout: {result.metadata["stdout"][:200]}')
    except Exception as e:
        print(f'run_script error: {e}')

if __name__ == "__main__":
    asyncio.run(test_ae_operations())