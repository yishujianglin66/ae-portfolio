"""
SadTalker 推理包装器
====================
放在项目目录中，通过 venv Python 执行。
解决 basicsr 1.4.2 与 torchvision >=0.18 的兼容性问题。
"""
import os
import sys
import types


# ============================================================
# 1. 兼容性补丁：必须在导入 basicsr 之前执行
# ============================================================
def patch_torchvision():
    """注入 torchvision.transforms.functional_tensor 兼容模块"""
    try:
        from torchvision.transforms import functional as F
        shim = types.ModuleType("torchvision.transforms.functional_tensor")
        # 暴露 basicsr 需要的函数
        for attr_name in dir(F):
            if not attr_name.startswith("_"):
                try:
                    setattr(shim, attr_name, getattr(F, attr_name))
                except (TypeError, AttributeError):
                    pass
        sys.modules["torchvision.transforms.functional_tensor"] = shim
    except ImportError:
        pass

patch_torchvision()

# ============================================================
# 2. 设置 SadTalker 环境
# ============================================================
SADTALKER_ROOT = os.environ.get("SADTALKER_ROOT", r"D:\AE-Work\sadtalker")
os.chdir(SADTALKER_ROOT)
if SADTALKER_ROOT not in sys.path:
    sys.path.insert(0, SADTALKER_ROOT)

# ============================================================
# 3. 执行 inference.py（透传命令行参数）
# ============================================================
if __name__ == "__main__":
    # sys.argv[0] 是本脚本路径，其余参数透传给 inference.py 的 argparse
    # inference.py 的 argparse.parse_args() 会读取 sys.argv[1:]
    import runpy
    inference_path = os.path.join(SADTALKER_ROOT, "inference.py")
    # runpy.run_path 会正确设置 __name__ 为 '__main__'
    # sys.argv 保持不变，argparse 会正确解析
    runpy.run_path(inference_path, run_name="__main__")
