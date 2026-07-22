"""生成 WindowLocker 图标"""
from PIL import Image, ImageDraw, ImageFont


def create_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 背景渐变
    for y in range(size):
        t = y / (size - 1)
        r = int(30 * (1 - t) + 10 * t)
        g = int(110 * (1 - t) + 60 * t)
        b = int(200 * (1 - t) + 140 * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))
    
    # 圆角矩形外框 - 窗户
    pad = size // 12
    corner = size // 8
    rect = [pad, pad, size - pad, size - pad]
    draw.rounded_rectangle(rect, radius=corner, outline=(255, 255, 255, 220), width=max(2, size // 24))
    
    # 窗格十字线
    mid_x = size // 2
    mid_y = size // 2
    line_w = max(2, size // 32)
    draw.line([(mid_x, pad + corner // 2), (mid_x, size - pad - corner // 2)], fill=(255, 255, 255, 200), width=line_w)
    draw.line([(pad + corner // 2, mid_y), (size - pad - corner // 2, mid_y)], fill=(255, 255, 255, 200), width=line_w)
    
    # 锁头 - 在窗户中央
    lock_w = size // 3
    lock_h = size // 4
    lock_x = (size - lock_w) // 2
    lock_y = size * 11 // 24
    
    # 锁梁（弧形）
    arc_y = lock_y - lock_h // 2
    arc_h = lock_h
    arc_w = lock_w
    draw.arc([lock_x, arc_y - arc_h // 2, lock_x + arc_w, arc_y + arc_h], 
             start=0, end=180, fill=(255, 215, 0, 255), width=max(3, size // 16))
    
    # 锁体
    body_y = lock_y
    body_rect = [lock_x, body_y, lock_x + lock_w, body_y + lock_h]
    draw.rounded_rectangle(body_rect, radius=max(2, size // 24), fill=(255, 215, 0, 255))
    
    # 钥匙孔
    keyhole_x = lock_x + lock_w // 2
    keyhole_y = body_y + lock_h // 2
    keyhole_r = max(2, size // 24)
    draw.ellipse([keyhole_x - keyhole_r, keyhole_y - keyhole_r, 
                  keyhole_x + keyhole_r, keyhole_y + keyhole_r], fill=(60, 60, 60, 255))
    draw.rectangle([keyhole_x - keyhole_r // 2, keyhole_y, 
                    keyhole_x + keyhole_r // 2, body_y + lock_h - size // 24], fill=(60, 60, 60, 255))
    
    return img


if __name__ == "__main__":
    # 生成多尺寸 ICO
    sizes = [256, 128, 64, 48, 32, 16]
    images = [create_icon(s) for s in sizes]
    images[0].save("icon.ico", format="ICO", sizes=[(s, s) for s in sizes])
    print("图标已保存为 icon.ico")
