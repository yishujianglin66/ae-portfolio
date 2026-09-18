# 创建测试素材图片
import os

from PIL import Image, ImageDraw, ImageFont

# 创建测试图片目录
test_dir = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\05-测试套件\test_resources"
os.makedirs(test_dir, exist_ok=True)

# 创建一个简单的测试图片
width, height = 512, 512
img = Image.new('RGB', (width, height), color='blue')
draw = ImageDraw.Draw(img)

# 绘制一些图形
draw.rectangle([(50, 50), (200, 200)], fill='red', outline='white', width=3)
draw.circle((350, 400), 80, fill='yellow', outline='white', width=3)
draw.line([(100, 450), (400, 100)], fill='white', width=5)

# 添加文字
try:
    font = ImageFont.truetype("arial.ttf", 36)
except:
    font = ImageFont.load_default()

draw.text((150, 250), "AE Import Test", fill='white', font=font)

# 保存图片
test_image_path = os.path.join(test_dir, "test_image.png")
img.save(test_image_path)

print(f"测试图片已创建: {test_image_path}")

# 也创建一个简单的 SVG 作为备选
import xml.etree.ElementTree as ET

svg = ET.Element('svg', width='512', height='512', xmlns='http://www.w3.org/2000/svg')
rect = ET.SubElement(svg, 'rect', width='512', height='512', fill='green')
circle = ET.SubElement(svg, 'circle', cx='256', cy='256', r='100', fill='orange')
text = ET.SubElement(svg, 'text', x='256', y='270', 
                     text_anchor='middle', 
                     font_size='30', fill='white')
text.text = 'SVG Test'

test_svg_path = os.path.join(test_dir, "test_image.svg")
tree = ET.ElementTree(svg)
tree.write(test_svg_path)

print(f"SVG 测试图片已创建: {test_svg_path}")
