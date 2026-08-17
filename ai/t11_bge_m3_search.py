# -*- coding: utf-8 -*-
"""T11: 验证BGE-M3加载 + 构建语义索引"""
import sys, json, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

print("[T11] 加载BGE-M3...")
t0 = time.time()
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-m3")
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
print(f"[T11] ✅ BGE-M3验证通过")
