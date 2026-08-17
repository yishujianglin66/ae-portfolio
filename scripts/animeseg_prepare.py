"""BiRefNet 动漫域微调 — 数据预处理：解压 imgs-masks.zip → 训练集划分 → 数据清单
（BiRefNet 训练格式：图像 + 二值 mask，1024 输入）"""
import sys
import zipfile
from pathlib import Path

ZIP = Path("external/animeseg/imgs-masks.zip")
OUT = Path("external/animeseg/dataset")
OUT.mkdir(parents=True, exist_ok=True)

if not ZIP.exists():
    print("zip 未下载完成", file=sys.stderr)
    sys.exit(1)

print("解压中...", file=sys.stderr)
with zipfile.ZipFile(ZIP) as z:
    names = z.namelist()
    imgs = [n for n in names if ("imgs" in n.lower() or "image" in n.lower()) and n.lower().endswith((".png", ".jpg"))]
    masks = [n for n in names if ("mask" in n.lower()) and n.lower().endswith((".png", ".jpg"))]
    print(f"zip 内: {len(names)} 文件, 图像 {len(imgs)}, mask {len(masks)}", file=sys.stderr)
    # 预览前几个路径结构
    for n in names[:10]:
        print("  ", n, file=sys.stderr)
    z.extractall(OUT)
print("解压完成", file=sys.stderr)
