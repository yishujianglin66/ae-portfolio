"""
software_sdk/adapters - 软件适配器包

每个软件一个独立适配器文件。
"""
from software_sdk.adapters.ae_adapter import AfterEffectsAdapter
from software_sdk.adapters.silhouette_adapter import SilhouetteAdapter
from software_sdk.adapters.blender_adapter import BlenderAdapter
from software_sdk.adapters.topaz_adapter import TopazAdapter
from software_sdk.adapters.davinci_adapter import DaVinciAdapter
from software_sdk.adapters.ffmpeg_adapter import FFmpegAdapter

__all__ = [
    "AfterEffectsAdapter",
    "SilhouetteAdapter",
    "BlenderAdapter",
    "TopazAdapter",
    "DaVinciAdapter",
    "FFmpegAdapter",
]
