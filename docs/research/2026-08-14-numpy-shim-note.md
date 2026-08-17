# 环境修复记录：numpy 2.x 兼容垫片

> 2026-08-14 | 为启用 RIFE 补帧后处理 (post_enhancer rife_local) 而实施

## 问题

- `skvideo` (scikit-video) 在 numpy 2.x 下崩溃：`np.float` 别名已移除
  （17 个文件、100+ 处使用），RIFE inference_video.py 依赖 skvideo 读视频。

## 修复

- 在 Python311 site-packages 写入 `sitecustomize.py`：启动时恢复
  `np.float/np.int/np.bool/np.object/np.str` 别名（内置类型映射）。
- 效果：RIFE 补帧 19.1s 1080p 视频 84.7s 完成（GPU），产出 48fps 版。
- 副作用：全局生效于本解释器环境；FutureWarning 已抑制。

## 复现（换机器/重装环境时）

```python
# C:\Users\<user>\AppData\Local\Programs\Python\Python311\Lib\site-packages\sitecustomize.py
import warnings
import numpy as np
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    for _name, _builtin in (("float", float), ("int", int), ("bool", bool),
                            ("object", object), ("str", str)):
        if not hasattr(np, _name):
            setattr(np, _name, _builtin)
```

## 移除条件

- skvideo 上游适配 numpy 2.x（或 RIFE 换用 decord/cv2 读帧后）。
