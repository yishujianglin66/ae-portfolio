"""
SadTalker Runner - 兼容性补丁 + 推理入口
========================================

作用：
1. 修补 basicsr 1.4.2 与 torchvision >=0.18 的不兼容问题
   （torchvision.transforms.functional_tensor 模块在 0.18+ 已移除）
2. 作为 SadTalker inference.py 的包装器，被 SadTalkerEngine 调用

使用方式：
    python sadtalker_runner.py --driven_audio audio.wav --source_image image.png ...

引擎集成：
    SadTalkerEngine 通过 subprocess 调用本脚本，使用 venv 中的 Python 解释器。
"""
from __future__ import annotations

import sys
import types
import importlib


def _patch_torchvision_functional_tensor() -> None:
    """创建 torchvision.transforms.functional_tensor 兼容模块。

    basicsr 1.4.2 的 degradations.py 执行：
        from torchvision.transforms.functional_tensor import rgb_to_grayscale

    但 torchvision >= 0.18 移除了 functional_tensor 模块，
    rgb_to_grayscale 已迁移到 torchvision.transforms.functional。
    此函数在 sys.modules 中注入一个兼容模块，让旧导入路径仍然有效。
    """
    try:
        from torchvision.transforms import functional as F
        shim = types.ModuleType("torchvision.transforms.functional_tensor")
        shim.rgb_to_grayscale = F.rgb_to_grayscale
        # 额外暴露 basicsr 可能用到的其他函数
        for attr_name in ("adjust_brightness", "adjust_contrast", "adjust_saturation",
                          "normalize", "to_tensor", "crop", "center_crop",
                          "resize", "hflip", "vflip", "rotate"):
            if hasattr(F, attr_name):
                setattr(shim, attr_name, getattr(F, attr_name))
        sys.modules["torchvision.transforms.functional_tensor"] = shim
    except ImportError:
        # torchvision 不可用时静默跳过（后续导入 basicsr 会自然报错）
        pass


def main() -> int:
    # 1. 打补丁 —— 必须在导入 basicsr 之前执行
    _patch_torchvision_functional_tensor()

    # 2. 切换工作目录到 SadTalker 仓库根目录
    import os
    sadtalker_root = os.environ.get("SADTALKER_ROOT", r"D:\AE-Work\sadtalker")
    os.chdir(sadtalker_root)

    # 3. 将 SadTalker 源码加入 sys.path
    if sadtalker_root not in sys.path:
        sys.path.insert(0, sadtalker_root)

    # 4. 构造 inference.py 的 argv 并调用其 main
    #    保留原始 argv[0]，其余参数透传给 inference.py
    inference_module = importlib.import_module("inference")
    # inference.py 的 __main__ 块会在 import 时被 argparse 执行，
    # 但它使用 sys.argv，所以我们直接透传命令行参数
    return 0


if __name__ == "__main__":
    _patch_torchvision_functional_tensor()

    import os
    sadtalker_root = os.environ.get("SADTALKER_ROOT", r"D:\AE-Work\sadtalker")
    os.chdir(sadtalker_root)
    if sadtalker_root not in sys.path:
        sys.path.insert(0, sadtalker_root)

    # 直接 exec inference.py，保留 sys.argv 中的参数
    inference_path = os.path.join(sadtalker_root, "inference.py")
    with open(inference_path, "r", encoding="utf-8") as f:
        code = f.read()

    # 替换 __name__ 检查，使 main() 被执行
    exec(compile(code, inference_path, "exec"), {"__name__": "__main__"})
