"""
sitecustomize.py - Python 启动时自动加载
=========================================
修补 SadTalker 在新环境中的兼容性问题：
1. basicsr 1.4.2 与 torchvision >=0.18（functional_tensor 模块移除）
2. numpy >=1.24（np.float 等别名移除）
3. numpy >=2.0 额外别名
4. numpy >=1.24 拒绝异构形状数组（align_img 中 trans_params 构造失败）

此文件通过 PYTHONPATH 自动被 Python 解释器加载。
"""
import sys
import types

# ============================================================
# 1. torchvision.transforms.functional_tensor 兼容
# ============================================================
try:
    from torchvision.transforms import functional as F
    shim = types.ModuleType("torchvision.transforms.functional_tensor")
    for attr_name in dir(F):
        if not attr_name.startswith("_"):
            try:
                setattr(shim, attr_name, getattr(F, attr_name))
            except (TypeError, AttributeError):
                pass
    sys.modules["torchvision.transforms.functional_tensor"] = shim
except ImportError:
    pass

# ============================================================
# 2. numpy 已移除别名兼容（np.float, np.int, np.bool, np.object）
#    SadTalker 的 my_awing_arch.py 使用了 np.float
# ============================================================
try:
    import numpy as _np
    _deprecated_aliases = {
        "float": float,
        "int": int,
        "bool": bool,
        "object": object,
        "complex": complex,
        "str": str,
        "long": int,
        "unicode": str,
    }
    for _alias, _builtin in _deprecated_aliases.items():
        if not hasattr(_np, _alias):
            setattr(_np, _alias, _builtin)
except ImportError:
    pass

# ============================================================
# 4. SadTalker 兼容补丁（通过 import hook 注入）
#    a) src.face3d.util.preprocess.align_img: numpy>=1.24 拒绝异构形状数组
#    b) src.utils.videoio.save_video_with_watermark: PATH 中的 ffmpeg 为极简版，
#       不含 wav demuxer / 音频 decoder，需改用完整版 ffmpeg
# ============================================================
import importlib.abc
import importlib.machinery


class _SadTalkerModulePatcher(importlib.abc.MetaPathFinder):
    """拦截目标模块导入，在加载完成后执行 patch。"""

    _targets = {
        "src.face3d.util.preprocess": "_patch_align_img",
        "src.utils.videoio": "_patch_videoio",
    }
    _done = set()

    def find_spec(self, fullname, path, target=None):
        if fullname not in self._targets or fullname in self._done:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        original_loader = spec.loader
        outer = self

        class _WrappingLoader(importlib.abc.Loader):
            def create_module(self, spec):
                if hasattr(original_loader, "create_module"):
                    return original_loader.create_module(spec)
                return None

            def exec_module(self, module):
                original_loader.exec_module(module)
                outer._done.add(fullname)
                _apply_patch(fullname, module)

        spec.loader = _WrappingLoader()
        return spec


def _apply_patch(fullname, module):
    if fullname == "src.face3d.util.preprocess":
        _patch_align_img(module)
    elif fullname == "src.utils.videoio":
        _patch_videoio(module)


def _patch_align_img(module):
    if not hasattr(module, "align_img"):
        return
    import numpy as _np

    def align_img(img, lm, lm3D, mask=None, target_size=224., rescale_factor=102.):
        w0, h0 = img.size
        if lm.shape[0] != 5:
            lm5p = module.extract_5p(lm)
        else:
            lm5p = lm
        t, s = module.POS(lm5p.transpose(), lm3D.transpose())
        s = rescale_factor / s
        img_new, lm_new, mask_new = module.resize_n_crop_img(
            img, lm, t, s, target_size=target_size, mask=mask
        )
        # 修复：t[0]/t[1] 是 shape (1,) 数组，需 float() 标量化以兼容 numpy>=1.24
        trans_params = _np.array([w0, h0, float(s), float(t[0]), float(t[1])])
        return trans_params, img_new, lm_new, mask_new

    module.align_img = align_img


def _find_full_ffmpeg():
    """查找支持 wav/audio 的完整版 ffmpeg。"""
    import os
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.expandvars(r"%USERPROFILE%\scoop\apps\ffmpeg\current\bin\ffmpeg.exe"),
    ]
    try:
        import imageio_ffmpeg
        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def _patch_videoio(module):
    if not hasattr(module, "save_video_with_watermark"):
        return
    import os
    import shutil
    import subprocess
    import uuid

    _ffmpeg_exe = _find_full_ffmpeg()

    def save_video_with_watermark(video, audio, save_path, watermark=False):
        temp_file = os.path.join(
            os.path.dirname(os.path.abspath(save_path)),
            str(uuid.uuid4()) + ".mp4",
        )
        ffmpeg = _ffmpeg_exe or "ffmpeg"
        # 用 -c:v copy -c:a aac -shortest 替代原 -vcodec copy
        # 原命令缺少音频编码指定，且 PATH 中的 ffmpeg 为极简版无 wav 支持
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", video, "-i", audio,
            "-c:v", "copy", "-c:a", "aac", "-shortest", temp_file,
        ]
        subprocess.run(cmd, check=True)

        if watermark is False:
            shutil.move(temp_file, save_path)
        else:
            try:
                import webui
                from modules import paths
                watarmark_path = paths.script_path + "/extensions/SadTalker/docs/sadtalker_logo.png"
            except Exception:
                dir_path = os.path.dirname(os.path.realpath(module.__file__))
                watarmark_path = dir_path + "/../../docs/sadtalker_logo.png"
            cmd = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", temp_file, "-i", watarmark_path,
                "-filter_complex",
                "[1]scale=100:-1[wm];[0][wm]overlay=(main_w-overlay_w)-10:10",
                save_path,
            ]
            subprocess.run(cmd, check=True)
            if os.path.exists(temp_file):
                os.remove(temp_file)

    module.save_video_with_watermark = save_video_with_watermark


sys.meta_path.insert(0, _SadTalkerModulePatcher())
