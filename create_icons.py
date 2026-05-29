from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, filename):
    """创建图标"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 绘制渐变圆形背景
    center = size // 2
    radius = int(size * 0.45)
    
    # 渐变效果
    for i in range(radius, 0, -1):
        ratio = i / radius
        r = int(102 + (118 - 102) * ratio)
        g = int(126 + (107 - 126) * ratio)
        b = int(234 + (162 - 234) * ratio)
        color = (r, g, b, 255)
        draw.ellipse([center - i, center - i, center + i, center + i], fill=color)
    
    # 绘制鱼符号
    emoji_size = int(size * 0.5)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", emoji_size)
    except:
        font = ImageFont.load_default()
    
    # 绘制简单的鱼形状
    fish_size = int(size * 0.3)
    fish_color = (255, 255, 255, 255)
    
    # 鱼身
    body_left = center - int(fish_size * 0.6)
    body_top = center - int(fish_size * 0.3)
    body_right = center + int(fish_size * 0.3)
    body_bottom = center + int(fish_size * 0.3)
    draw.ellipse([body_left, body_top, body_right, body_bottom], fill=fish_color)
    
    # 鱼尾
    tail_left = center + int(fish_size * 0.2)
    tail_top = center - int(fish_size * 0.4)
    tail_right = center + int(fish_size * 0.6)
    tail_bottom = center + int(fish_size * 0.4)
    points = [
        (tail_left, center),
        (tail_right, tail_top),
        (tail_right, tail_bottom)
    ]
    draw.polygon(points, fill=fish_color)
    
    img.save(filename, 'PNG')

# 创建图标目录
icon_dir = '/Users/liuyi/code/xianyu-auto-agent/XianyuAutoAgent-main/chrome-extension/icons'
os.makedirs(icon_dir, exist_ok=True)

# 生成不同尺寸的图标
sizes = [16, 32, 48, 128]
for size in sizes:
    filename = os.path.join(icon_dir, f'icon{size}.png')
    create_icon(size, filename)
    print(f'Created: {filename}')

print('All icons created successfully!')