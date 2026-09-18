"""检测哪些测试文件在导入时挂起或报错"""
import os
import subprocess
import sys

os.chdir(os.path.join(os.path.dirname(__file__), '..', 'tests'))
files = sorted(f for f in os.listdir('.') if f.startswith('test_') and f.endswith('.py'))

# 已排除的文件（从 pytest.ini 同步）
ignored = {
    'test_api_integration.py', 'test_api_endpoints.py', 'test_api_auth_fail_closed.py',
    'test_bilibili_downloader.py', 'test_audio_analysis_service.py', 'test_batch_queue.py',
    'test_canimport.py', 'test_davinci_api.py', 'test_e2e_resolve.py', 'test_h264_import.py',
    'test_multisegment_grade.py', 'test_batch_amv.py',
    'test_diag_e2e.py', 'test_douyin_downloader.py', 'test_download_flow.py',
    'test_downloader_utils.py', 'test_execute_return.py', 'test_real_amv.py',
    'test_scene_detect.py', 'test_unified_e2e.py', 'test_toolchain_integration.py',
    'test_layer_render_service.py', 'test_phase2_perception_enhancement.py',
}

hang = []
error = []
ok = []

for f in files:
    if f in ignored:
        continue
    try:
        r = subprocess.run(
            [sys.executable, '-c',
             f'import importlib.util,sys; sys.path.insert(0,"."); sys.path.insert(0,".."); '
             f'sys.path.insert(0,"../integrations"); sys.path.insert(0,"../analysis"); '
             f'sys.path.insert(0,"../media"); '
             f'spec=importlib.util.spec_from_file_location("t","{f}"); '
             f'mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)'],
            capture_output=True, timeout=8, text=True, encoding='utf-8', errors='replace'
        )
        if r.returncode != 0:
            err_line = r.stderr.strip().split('\n')[-1] if r.stderr else 'unknown'
            error.append((f, err_line))
        else:
            ok.append(f)
    except subprocess.TimeoutExpired:
        hang.append(f)

print("\n=== 检测结果 ===")
print(f"总计: {len(files)-len(ignored)} 文件 (排除 {len(ignored)} 个已知)")
print(f"正常: {len(ok)}")
print(f"导入错误: {len(error)}")
print(f"导入挂起(>8s): {len(hang)}")

if hang:
    print("\n--- 挂起文件 ---")
    for f in hang:
        print(f"  HANG: {f}")

if error:
    print("\n--- 导入错误文件 (前20) ---")
    for f, e in error[:20]:
        print(f"  ERR: {f} → {e[:120]}")
