# -*- coding: utf-8 -*-
"""T11: 验证BGE-M3加载 + 构建语义索引"""
import sys, json, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os as _os
# 修复1: 默认使用HF中国镜像（解决SSL超时/连接失败）
if not _os.environ.get("HF_ENDPOINT"):
    _os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

print("[T11] 加载BGE-M3...")
t0 = time.time()
from sentence_transformers import SentenceTransformer

# 修复2+3: 两层加载兜底 + 可操作错误信息
class BGEOfflineUnavailableError(Exception):
    pass

MODEL_NAME = "BAAI/bge-m3"
model = None

try:
    # 外层1: 正常在线加载（已默认走HF镜像 hf-mirror.com）
    model = SentenceTransformer(MODEL_NAME)
except (OSError, ImportError, RuntimeError) as _e1:
    try:
        import requests as _requests
        _ssl_err_cls = _requests.exceptions.SSLError
        _conn_err_cls = _requests.exceptions.ConnectionError
        if not isinstance(_e1, (_ssl_err_cls, _conn_err_cls, OSError, ImportError, RuntimeError)):
            raise
    except Exception:
        pass
    try:
        # 外层2: 切换离线模式，尝试从本地缓存加载
        _os.environ["TRANSFORMERS_OFFLINE"] = "1"
        model = SentenceTransformer(MODEL_NAME, local_files_only=True)
    except Exception as _e2:
        _user_profile = _os.environ.get("USERPROFILE", _os.environ.get("HOME", "~"))
        _hf_cache_default = str(Path(_user_profile) / ".cache" / "huggingface" / "hub")
        _actual_hf_home = _os.environ.get("HF_HOME", _hf_cache_default)
        _actionable_msg = (
            "BGE-M3 加载失败，请执行以下三步之一：\n"
            "  (1) 设置 HF_ENDPOINT=https://hf-mirror.com 并重试；\n"
            "  (2) 手动在联网机器下载 BAAI/bge-m3 到 " + _actual_hf_home + " ；\n"
            "  (3) 使用本地替代：在core/config.py设置 BGE_LOCAL_MODEL_DIR\n"
            "\n[在线加载错误] " + type(_e1).__name__ + ": " + str(_e1) + "\n"
            "[离线加载错误] " + type(_e2).__name__ + ": " + str(_e2)
        )
        _final_exc = BGEOfflineUnavailableError(_actionable_msg)
        try:
            raise _final_exc from _e2
        except BGEOfflineUnavailableError:
            raise _final_exc from None

dim = model.get_sentence_embedding_dimension()
print(f"[T11] BGE-M3 loaded in {time.time()-t0:.1f}s, dim={dim}")

# 测试编码
sentences = ["进击的巨人 艾伦变身", "无限滑板 竞速场景", "鬼灭之刃 火之神神乐"]
embeddings = model.encode(sentences)
print(f"[T11] 编码测试: {embeddings.shape}")

# 保存ready标记
ready_path = ROOT / "tmp" / "bge_m3_ready.txt"
ready_path.parent.mkdir(parents=True, exist_ok=True)
ready_path.write_text(f"ready\ndim={dim}\nload_time={time.time()-t0:.1f}s\n")
print("[T11] ✅ BGE-M3验证通过")
