#!/usr/bin/env python3
"""通过Windows COM自动化执行AE JSX脚本"""
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

try:
    import win32com.client
    print("尝试COM自动化连接AE...")
    ae = win32com.client.Dispatch("AfterFX.Application")
    print(f"✓ 连接成功! AE版本: {ae.version}")
    result = ae.DoScript('(function(){return "PING_OK:" + app.version;})();')
    print(f"DoScript结果: {result}")
except ImportError:
    print("win32com不可用, 尝试ctypes...")
    try:
        import comtypes.client
        ae = comtypes.client.CreateObject("AfterFX.Application")
        print("✓ comtypes连接成功!")
    except Exception as e:
        print(f"✗ comtypes也失败: {e}")
except Exception as e:
    print(f"✗ COM连接失败: {e}")
    print("\n尝试直接启动AE并等待Bridge...")
