"""
生成 Silhouette Roto 测试素材
创建一个简单的测试视频/图片，主体与背景对比明显
"""
import os
import sys

print("=" * 60)
print("  生成 Silhouette Roto 测试素材")
print("=" * 60)

# 测试素材路径
OUTPUT_DIR = r"C:\Temp\silhouette_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 尝试用 PIL 生成测试图片
try:
    from PIL import Image, ImageDraw, ImageFont
    print("  ✓ PIL 可用")

    # 创建 1920x1080 测试图片
    width, height = 1920, 1080

    # 图片1: 蓝色背景 + 红色圆形（简单跟踪目标）
    img1 = Image.new("RGB", (width, height), color=(30, 60, 120))
    draw1 = ImageDraw.Draw(img1)
    # 画一个红色圆形作为主体
    draw1.ellipse([760, 340, 1160, 740], fill=(220, 50, 50), outline=(255, 255, 255), width=3)
    # 添加文字标注
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except:
        font = ImageFont.load_default()
    draw1.text((800, 500), "TARGET", fill=(255, 255, 255), font=font)
    img1_path = os.path.join(OUTPUT_DIR, "roto_test_simple.png")
    img1.save(img1_path)
    print(f"  ✓ 简单测试图片: {img1_path}")

    # 图片2: 渐变背景 + 人物轮廓（模拟人像抠图场景）
    img2 = Image.new("RGB", (width, height))
    draw2 = ImageDraw.Draw(img2)
    # 渐变背景
    for y in range(height):
        r = int(50 + (y / height) * 100)
        g = int(80 + (y / height) * 80)
        b = int(120 + (y / height) * 60)
        draw2.line([(0, y), (width, y)], fill=(r, g, b))

    # 画一个简化的人物轮廓（头+身体）
    # 头部
    head_x, head_y = 960, 300
    draw2.ellipse([head_x-80, head_y-80, head_x+80, head_y+80], fill=(200, 170, 140))
    # 脖子
    draw2.rectangle([head_x-30, head_y+70, head_x+30, head_y+120], fill=(200, 170, 140))
    # 身体
    draw2.polygon([
        (head_x-150, head_y+120),
        (head_x+150, head_y+120),
        (head_x+180, 800),
        (head_x-180, 800),
    ], fill=(80, 100, 150))
    # 添加文字标注
    draw2.text((50, 50), "PERSON SILHOUETTE TEST", fill=(255, 255, 255), font=font)
    img2_path = os.path.join(OUTPUT_DIR, "roto_test_person.png")
    img2.save(img2_path)
    print(f"  ✓ 人物轮廓测试图片: {img2_path}")

    # 图片3: 多目标场景（用于复杂 Roto 测试）
    img3 = Image.new("RGB", (width, height), color=(40, 40, 50))
    draw3 = ImageDraw.Draw(img3)
    # 左侧矩形
    draw3.rectangle([200, 300, 500, 700], fill=(180, 60, 60))
    # 中间圆形
    draw3.ellipse([810, 350, 1110, 650], fill=(60, 180, 80))
    # 右侧三角形
    draw3.polygon([(1400, 300), (1700, 300), (1550, 700)], fill=(60, 100, 200))
    draw3.text((50, 50), "MULTI-TARGET TEST", fill=(255, 255, 255), font=font)
    img3_path = os.path.join(OUTPUT_DIR, "roto_test_multi.png")
    img3.save(img3_path)
    print(f"  ✓ 多目标测试图片: {img3_path}")

    print(f"\n  所有测试素材已生成到: {OUTPUT_DIR}")
    print(f"  文件列表:")
    for f in os.listdir(OUTPUT_DIR):
        fpath = os.path.join(OUTPUT_DIR, f)
        size = os.path.getsize(fpath)
        print(f"    {f} ({size} bytes)")

except ImportError:
    print("  ✗ PIL 不可用，尝试用 Silhouette 内置 Python 安装...")

    # 尝试用 Silhouette 内置 pip 安装 Pillow
    import subprocess
    sil_python = r"C:\Program Files\BorisFX\Silhouette 2026.0\resources\python\python.exe"

    print("  正在安装 Pillow...")
    result = subprocess.run(
        [sil_python, "-m", "pip", "install", "Pillow", "--quiet"],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        print("  ✓ Pillow 安装成功，重新运行此脚本")
    else:
        print(f"  ✗ 安装失败: {result.stderr}")
        print("  尝试手动创建测试图片...")

        # 创建一个最小的 PNG 文件（1x1 红色像素）
        # PNG 文件头 + IHDR + IDAT + IEND
        import struct
        import zlib

        def create_minimal_png(width, height, rgb_color):
            """创建最小 PNG 文件"""
            def png_chunk(chunk_type, data):
                chunk = chunk_type + data
                crc = struct.pack(">I", zlib.crc32(chunk) & 0xffffffff)
                return struct.pack(">I", len(data)) + chunk + crc

            # PNG signature
            sig = b'\x89PNG\r\n\x1a\n'

            # IHDR
            ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
            ihdr = png_chunk(b'IHDR', ihdr_data)

            # IDAT
            raw_data = b''
            for y in range(height):
                raw_data += b'\x00'  # filter byte
                for x in range(width):
                    raw_data += bytes(rgb_color)

            compressed = zlib.compress(raw_data)
            idat = png_chunk(b'IDAT', compressed)

            # IEND
            iend = png_chunk(b'IEND', b'')

            return sig + ihdr + idat + iend

        # 创建 1920x1080 蓝色图片
        png_data = create_minimal_png(1920, 1080, (50, 100, 150))
        test_path = os.path.join(OUTPUT_DIR, "roto_test_simple.png")
        with open(test_path, "wb") as f:
            f.write(png_data)

        print(f"  ✓ 最小测试图片已创建: {test_path}")
        print(f"    尺寸: {os.path.getsize(test_path)} bytes")

print("=" * 60)
