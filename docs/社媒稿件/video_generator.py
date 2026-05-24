"""
攀升AI节点 - 6期社媒教程视频生成器
使用 Pillow + FFmpeg 生成 1080x1920 竖版教程视频
每期视频约 50-70 秒，适合小红书/视频号/抖音
"""

import os
import subprocess
import shutil
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── 配置 ────────────────────────────────────────────────────────────────────
W, H = 1080, 1920
FPS = 15          # 动态字幕类视频 15fps 足够，帧数减半
FONT_PATH = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
OUTPUT_DIR = Path("/sessions/sleepy-gracious-cray/mnt/ComfyUI-Tikpan-Pro/docs/社媒稿件/videos")
FRAMES_DIR = Path("/tmp/hf_frames")

# 颜色主题
THEMES = {
    1: {"bg": (12, 18, 40),     "accent": (99, 179, 255),  "tag": (50, 120, 200)},   # 深蓝 - 入门
    2: {"bg": (30, 18, 10),     "accent": (255, 185, 80),  "tag": (200, 120, 30)},   # 暖金 - 图片
    3: {"bg": (15, 10, 35),     "accent": (160, 100, 255), "tag": (100, 60, 200)},   # 紫蓝 - 视频
    4: {"bg": (35, 12, 12),     "accent": (255, 100, 80),  "tag": (200, 60, 40)},    # 橙红 - 音频
    5: {"bg": (10, 30, 15),     "accent": (80, 220, 130),  "tag": (40, 160, 80)},    # 绿色 - 分析
    6: {"bg": (20, 20, 20),     "accent": (200, 200, 255), "tag": (120, 100, 200)},  # 彩色 - 综合
}

def load_font(size):
    return ImageFont.truetype(FONT_PATH, size)

def ease_in_out(t):
    """缓动函数，0~1 → 0~1"""
    return t * t * (3 - 2 * t)

def lerp(a, b, t):
    return a + (b - a) * t

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# ─── 绘图工具 ─────────────────────────────────────────────────────────────────

def draw_rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.ellipse([x0, y0, x0 + 2*radius, y0 + 2*radius], fill=fill)
    draw.ellipse([x1 - 2*radius, y0, x1, y0 + 2*radius], fill=fill)
    draw.ellipse([x0, y1 - 2*radius, x0 + 2*radius, y1], fill=fill)
    draw.ellipse([x1 - 2*radius, y1 - 2*radius, x1, y1], fill=fill)

def draw_gradient_bg(img, color_top, color_bottom):
    """竖向渐变背景"""
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(lerp(color_top[0], color_bottom[0], t))
        g = int(lerp(color_top[1], color_bottom[1], t))
        b = int(lerp(color_top[2], color_bottom[2], t))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

def draw_grid_dots(draw, color, alpha=40):
    """装饰性背景网格点"""
    c = (*color, alpha)
    for x in range(0, W, 80):
        for y in range(0, H, 80):
            draw.ellipse([x-2, y-2, x+2, y+2], fill=color)

def draw_text_centered(draw, text, y, font, color, shadow=True, max_width=900):
    """居中绘制文字，支持自动换行"""
    lines = wrap_text(text, font, max_width)
    line_h = font.size + 12
    total_h = len(lines) * line_h
    cy = y - total_h // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        if shadow:
            draw.text((x+2, cy+2), line, font=font, fill=(0, 0, 0, 120))
        draw.text((x, cy), line, font=font, fill=color)
        cy += line_h

def wrap_text(text, font, max_width):
    """文字换行"""
    # 先按换行符分
    paragraphs = text.split("\n")
    result = []
    for para in paragraphs:
        if not para.strip():
            result.append("")
            continue
        line = ""
        for char in para:
            test = line + char
            bbox = font.getbbox(test)
            if bbox[2] - bbox[0] <= max_width:
                line = test
            else:
                if line:
                    result.append(line)
                line = char
        if line:
            result.append(line)
    return result

def draw_tag(draw, text, x, y, font, bg_color, text_color=(255,255,255)):
    """绘制标签按钮"""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 24, 12
    draw_rounded_rect(draw, [x, y, x + tw + pad_x*2, y + th + pad_y*2], 20, bg_color)
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=text_color)
    return tw + pad_x*2

def draw_progress_bar(draw, step, total, y, accent_color):
    """底部进度条"""
    bar_w = W - 120
    x0 = 60
    # 背景
    draw.rounded_rectangle([x0, y, x0 + bar_w, y + 8], radius=4, fill=(255,255,255,40))
    # 进度
    prog_w = int(bar_w * step / total)
    if prog_w > 0:
        draw.rounded_rectangle([x0, y, x0 + prog_w, y + 8], radius=4, fill=accent_color)

def draw_step_number(draw, n, total, x, y, accent):
    """步骤编号圆圈"""
    r = 36
    draw.ellipse([x-r, y-r, x+r, y+r], outline=accent, width=3)
    font = load_font(36)
    bbox = draw.textbbox((0,0), str(n), font=font)
    tw = bbox[2]-bbox[0]; th = bbox[3]-bbox[1]
    draw.text((x - tw//2, y - th//2), str(n), font=font, fill=accent)

# ─── 帧生成：各种幻灯片类型 ───────────────────────────────────────────────────

def make_intro_frame(ep_num, title, subtitle, progress_ratio, theme):
    """开场标题帧"""
    img = Image.new("RGB", (W, H))
    bg = theme["bg"]
    bg2 = tuple(min(255, c + 25) for c in bg)
    draw_gradient_bg(img, bg2, bg)
    draw = ImageDraw.Draw(img)

    # 装饰网格
    draw_grid_dots(draw, theme["accent"])

    # 顶部装饰线
    for i in range(3):
        y_off = 60 + i * 18
        alpha = 255 - i * 80
        draw.line([(120, y_off), (W - 120, y_off)], fill=(*theme["accent"], alpha), width=2 - i)

    # 期数标签
    f_ep = load_font(32)
    ep_text = f"第 {ep_num:02d} 期"
    draw_tag(draw, ep_text, 60, 140, f_ep, theme["tag"])

    # 主标题（动画：y从下方滑入）
    slide_y = int(lerp(H//2 + 200, H//2 - 60, ease_in_out(min(1, progress_ratio * 2.5))))
    alpha_v = int(lerp(0, 255, ease_in_out(min(1, progress_ratio * 2.5))))

    f_title = load_font(72)
    f_sub = load_font(44)

    # 主标题
    title_img = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    td = ImageDraw.Draw(title_img)
    lines = wrap_text(title, f_title, 900)
    cy = 20
    for line in lines:
        bbox = td.textbbox((0,0), line, font=f_title)
        tw = bbox[2]-bbox[0]
        x = (W - tw) // 2
        td.text((x+3, cy+3), line, font=f_title, fill=(0,0,0,60))
        td.text((x, cy), line, font=f_title, fill=(255,255,255,alpha_v))
        cy += f_title.size + 16

    img.paste(title_img, (0, slide_y - 150), title_img)

    # 副标题
    sub_img = Image.new("RGBA", (W, 200), (0,0,0,0))
    sd = ImageDraw.Draw(sub_img)
    sub_alpha = int(lerp(0, 200, ease_in_out(min(1, max(0, (progress_ratio - 0.3) * 2)))))
    draw_text_centered(sd, subtitle, 60, f_sub, (*theme["accent"], sub_alpha), shadow=False)
    img.paste(sub_img, (0, slide_y + 80), sub_img)

    # 底部品牌
    f_brand = load_font(36)
    draw.text((W//2 - 110, H - 160), "👑  攀升AI  ×  ComfyUI", font=f_brand, fill=(*theme["accent"], 160))

    return img


def make_content_frame(title, points, step_idx, total_steps, theme, show_ratio=1.0):
    """内容要点帧"""
    img = Image.new("RGB", (W, H))
    bg = theme["bg"]
    bg2 = tuple(min(255, c + 20) for c in bg)
    draw_gradient_bg(img, bg2, bg)
    draw = ImageDraw.Draw(img)
    draw_grid_dots(draw, theme["accent"])

    # 区块标题背景
    draw.rectangle([0, 140, W, 300], fill=tuple(c//3 for c in theme["accent"]))
    f_sec = load_font(54)
    draw_text_centered(draw, title, 220, f_sec, (255,255,255), shadow=True, max_width=900)

    # 要点列表
    f_pt = load_font(44)
    f_icon = load_font(48)
    icons = ["✦", "◈", "◆", "▸", "◉", "✧"]
    y_start = 380
    line_h = 110
    for i, point in enumerate(points):
        p_ratio = min(1.0, max(0.0, (show_ratio * len(points) - i)))
        if p_ratio <= 0:
            continue
        alpha = int(ease_in_out(min(1, p_ratio)) * 255)
        x_off = int(lerp(120, 0, ease_in_out(min(1, p_ratio))))
        y = y_start + i * line_h

        # 图标
        icon = icons[i % len(icons)]
        draw.text((80 + x_off, y), icon, font=f_icon, fill=(*theme["accent"], alpha))

        # 文字
        lines = wrap_text(point, f_pt, 820)
        for j, line in enumerate(lines):
            draw.text((160 + x_off, y + j * (f_pt.size + 8)), line,
                      font=f_pt, fill=(255, 255, 255, alpha))

    # 进度条
    draw_progress_bar(draw, step_idx, total_steps, H - 80, theme["accent"])

    # 底部品牌
    f_brand = load_font(30)
    draw.text((60, H - 50), "攀升AI  ×  ComfyUI", font=f_brand, fill=(*theme["accent"], 100))

    return img


def make_step_frame(step_num, total_steps, step_title, step_desc, ep_step, ep_total, theme, show_ratio=1.0):
    """操作步骤帧"""
    img = Image.new("RGB", (W, H))
    bg = theme["bg"]
    draw_gradient_bg(img, tuple(min(255, c+15) for c in bg), bg)
    draw = ImageDraw.Draw(img)

    # 左侧装饰竖线
    draw.rectangle([0, 0, 8, H], fill=theme["accent"])

    # 步骤标签
    f_label = load_font(36)
    draw_tag(draw, f"Step {step_num} / {total_steps}", 60, 120, f_label, theme["tag"])

    # 大步骤编号
    cx = W // 2
    draw_step_number(draw, step_num, total_steps, cx, 340, theme["accent"])

    # 步骤标题
    f_title = load_font(64)
    alpha_t = int(ease_in_out(min(1, show_ratio * 2)) * 255)
    draw_text_centered(draw, step_title, 490, f_title, (255,255,255, alpha_t), max_width=880)

    # 步骤说明
    f_desc = load_font(42)
    alpha_d = int(ease_in_out(min(1, max(0, show_ratio*2 - 0.6))) * 200)
    draw_text_centered(draw, step_desc, 700, f_desc,
                       (*theme["accent"], alpha_d), max_width=880)

    # 代码/命令框
    if show_ratio > 0.8:
        box_alpha = int(ease_in_out((show_ratio - 0.8) * 5) * 255)
        draw.rounded_rectangle([80, 850, W-80, 1050], radius=20,
                                fill=(*tuple(min(c+30, 255) for c in theme["bg"]), box_alpha),
                                outline=(*theme["accent"], box_alpha//2), width=2)

    # 进度条
    draw_progress_bar(draw, ep_step, ep_total, H - 80, theme["accent"])

    f_brand = load_font(30)
    draw.text((60, H - 50), "攀升AI  ×  ComfyUI", font=f_brand, fill=(*theme["accent"], 100))

    return img


def make_code_frame(title, code_lines, ep_step, ep_total, theme, show_ratio=1.0):
    """代码/流程图帧"""
    img = Image.new("RGB", (W, H))
    draw_gradient_bg(img, tuple(min(255, c+10) for c in theme["bg"]), theme["bg"])
    draw = ImageDraw.Draw(img)

    f_title = load_font(52)
    draw_text_centered(draw, title, 200, f_title, (255,255,255), max_width=900)

    # 代码框背景
    box_y = 280
    box_h = min(1400, len(code_lines) * 90 + 80)
    draw.rounded_rectangle([60, box_y, W-60, box_y + box_h], radius=24,
                            fill=tuple(max(0, c-8) for c in theme["bg"]),
                            outline=theme["accent"], width=2)

    f_code = load_font(38)
    for i, line in enumerate(code_lines):
        if i / len(code_lines) > show_ratio + 0.1:
            break
        line_alpha = int(ease_in_out(min(1, (show_ratio * len(code_lines) - i) * 1.5)) * 255)
        indent = line.count("  ") * 30
        color = (180, 220, 255) if line.strip().startswith("[") else (255, 255, 255)
        if "→" in line:
            color = theme["accent"]
        draw.text((100 + indent, box_y + 40 + i * 90), line.strip(), font=f_code,
                  fill=(*color, line_alpha))

    draw_progress_bar(draw, ep_step, ep_total, H - 80, theme["accent"])
    f_brand = load_font(30)
    draw.text((60, H - 50), "攀升AI  ×  ComfyUI", font=f_brand, fill=(*theme["accent"], 100))
    return img


def make_tip_frame(tip_title, tips, ep_step, ep_total, theme, show_ratio=1.0):
    """技巧/注意事项帧"""
    img = Image.new("RGB", (W, H))
    draw_gradient_bg(img, theme["bg"], tuple(max(0, c-10) for c in theme["bg"]))
    draw = ImageDraw.Draw(img)
    draw_grid_dots(draw, theme["accent"])

    # 💡 图标
    f_icon = load_font(100)
    draw.text((W//2 - 60, 120), "💡", font=f_icon, fill=(255,220,60))

    f_title = load_font(58)
    draw_text_centered(draw, tip_title, 350, f_title, (255,255,255), max_width=900)

    # 分隔线
    draw.line([(120, 430), (W-120, 430)], fill=theme["accent"], width=2)

    f_tip = load_font(42)
    y = 480
    for i, tip in enumerate(tips):
        p = min(1.0, max(0, (show_ratio * len(tips) - i) * 1.5))
        if p <= 0:
            continue
        alpha = int(ease_in_out(p) * 255)
        # 左侧彩色条
        draw.rectangle([60, y-4, 72, y + f_tip.size + 4],
                        fill=(*theme["accent"], alpha))
        lines = wrap_text(tip, f_tip, 840)
        for j, line in enumerate(lines):
            draw.text((100, y + j * (f_tip.size + 10)), line, font=f_tip,
                      fill=(255, 255, 255, alpha))
        y += len(lines) * (f_tip.size + 10) + 40

    draw_progress_bar(draw, ep_step, ep_total, H - 80, theme["accent"])
    f_brand = load_font(30)
    draw.text((60, H - 50), "攀升AI  ×  ComfyUI", font=f_brand, fill=(*theme["accent"], 100))
    return img


def make_outro_frame(next_ep_text, cta_text, theme, show_ratio=1.0):
    """片尾帧"""
    img = Image.new("RGB", (W, H))
    bg = theme["bg"]
    draw_gradient_bg(img, bg, tuple(max(0, c-20) for c in bg))
    draw = ImageDraw.Draw(img)
    draw_grid_dots(draw, theme["accent"])

    # 顶部装饰
    for i in range(5):
        y_off = 80 + i * 22
        draw.line([(80, y_off), (W-80, y_off)], fill=(*theme["accent"], 80 - i*15), width=1)

    # 感谢文字
    f_thanks = load_font(56)
    thanks_alpha = int(ease_in_out(min(1, show_ratio * 2)) * 255)
    draw_text_centered(draw, "感谢观看 🙌", 380, f_thanks, (255,255,255, thanks_alpha), max_width=900)

    # 下期预告
    if next_ep_text:
        f_next = load_font(42)
        next_alpha = int(ease_in_out(min(1, max(0, show_ratio*2 - 0.5))) * 200)
        draw_text_centered(draw, f"下期：{next_ep_text}", 540, f_next,
                           (*theme["accent"], next_alpha), max_width=880)

    # CTA 区域
    cta_alpha = int(ease_in_out(min(1, max(0, show_ratio*2 - 0.8))) * 255)
    f_cta = load_font(48)

    # 关注按钮
    draw_rounded_rect(draw, [W//2-220, 700, W//2+220, 800], 40, theme["tag"])
    btn_text = "❤️ 关注，不迷路"
    bbox = draw.textbbox((0,0), btn_text, font=f_cta)
    bw = bbox[2]-bbox[0]
    draw.text((W//2 - bw//2, 725), btn_text, font=f_cta, fill=(255,255,255,cta_alpha))

    # 收藏按钮
    draw_rounded_rect(draw, [W//2-200, 840, W//2+200, 940], 40,
                      tuple(max(0, c-20) for c in theme["tag"]))
    fav_text = "⭐ 收藏这篇"
    bbox2 = draw.textbbox((0,0), fav_text, font=f_cta)
    bw2 = bbox2[2]-bbox2[0]
    draw.text((W//2 - bw2//2, 865), fav_text, font=f_cta, fill=(255,255,255,cta_alpha))

    # 底部品牌
    f_brand = load_font(40)
    brand_alpha = int(ease_in_out(min(1, max(0, show_ratio * 1.5))) * 200)
    draw_text_centered(draw, "👑  攀升 AI  节点教程系列", H - 240, f_brand,
                       (*theme["accent"], brand_alpha), max_width=800)

    f_sub = load_font(32)
    draw_text_centered(draw, "ComfyUI-Tikpan-Pro", H - 170, f_sub,
                       (*theme["accent"], brand_alpha // 2), max_width=700)

    return img


# ─── 帧序列 → MP4 ─────────────────────────────────────────────────────────────

def write_frame(img, frames_dir, frame_idx):
    img.save(frames_dir / f"frame_{frame_idx:06d}.png")

def frames_to_video(frames_dir, output_path, fps=FPS):
    """用 FFmpeg 把帧序列合成 MP4"""
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%06d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-preset", "fast",
        "-movflags", "+faststart",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr[:500]}")
        return False
    return True


# ─── 每期视频的场景脚本 ───────────────────────────────────────────────────────

EPISODE_SCRIPTS = {

    1: {
        "title": "一个插件\nAI图片视频音频全搞定",
        "subtitle": "攀升AI节点  ·  入门教程",
        "theme": 1,
        "next": "AI商品图换背景，3步出大片",
        "scenes": [
            {"type": "intro", "duration": 3.5},
            {"type": "content", "title": "这个插件能做什么",
             "points": ["◆  生成商品图、海报、创意图", "◆  文字 / 图片生成视频", "◆  AI作曲 + 口播配音", "◆  拆解爆款，反推提示词"],
             "duration": 6.0},
            {"type": "step", "step": 1, "total": 3,
             "title": "安装插件",
             "desc": "ComfyUI Manager\n搜索 Tikpan  →  Install  →  重启",
             "duration": 4.0},
            {"type": "step", "step": 2, "total": 3,
             "title": "注册攀升AI账号",
             "desc": "访问攀升AI官网\n注册  →  控制台  →  创建 API Key",
             "duration": 4.0},
            {"type": "step", "step": 3, "total": 3,
             "title": "填入 API 密钥",
             "desc": "在节点的 API_密钥 框里\n粘贴你的 Key，即可开始使用",
             "duration": 4.0},
            {"type": "tip", "title": "省钱小技巧",
             "tips": ["测试时用低分辨率，确认效果再升高", "充值约 0.6元  =  1美元余额", "批量任务用异步模式，更稳定"],
             "duration": 5.0},
            {"type": "outro", "duration": 5.0},
        ]
    },

    2: {
        "title": "AI换背景\n商品图秒变大片",
        "subtitle": "GPT-Image-2 修图实战",
        "theme": 2,
        "next": "一张图片生成10秒展示视频",
        "scenes": [
            {"type": "intro", "duration": 3.5},
            {"type": "content", "title": "用这个节点能做什么",
             "points": ["◈  一键换背景（保留产品完整）", "◈  改风格：奢华 / 自然 / 简约", "◈  遮罩局部重绘精准控制", "◈  最多4张参考图指导生成"],
             "duration": 6.0},
            {"type": "code", "title": "最简工作流",
             "lines": ["[LoadImage: 商品原图]", "      ↓", "[GPT-Image-2 官方修图 V2]", "      ↓", "[PreviewImage  /  SaveImage]"],
             "duration": 5.0},
            {"type": "step", "step": 1, "total": 4,
             "title": "加载商品图",
             "desc": "右键画布  →  LoadImage\n选择你的商品原图（白底最佳）",
             "duration": 4.0},
            {"type": "step", "step": 2, "total": 4,
             "title": "添加修图节点",
             "desc": "右键  →  图片 | GPT-Image-2 官方修图 V2\n将商品图连接到「主图像」端口",
             "duration": 4.0},
            {"type": "step", "step": 3, "total": 4,
             "title": "写提示词（关键）",
             "desc": "「保留产品主体完全不变，\n将背景替换为...，真实摄影质感」",
             "duration": 4.5},
            {"type": "step", "step": 4, "total": 4,
             "title": "设置分辨率并运行",
             "desc": "测试用 1K，出片用 2K 或 4K\n点击 Queue Prompt 等待结果",
             "duration": 4.0},
            {"type": "tip", "title": "提示词公式",
             "tips": ["「保留产品主体 / 材质 / logo / 颜色完全不变」", "「将背景替换为【场景描述】」", "「真实自然光，商业摄影质感」"],
             "duration": 5.5},
            {"type": "outro", "duration": 5.0},
        ]
    },

    3: {
        "title": "一张图片\n生成10秒展示视频",
        "subtitle": "HappyHorse 图生视频实战",
        "theme": 3,
        "next": "AI作词作曲 + 口播配音",
        "scenes": [
            {"type": "intro", "duration": 3.5},
            {"type": "content", "title": "HappyHorse 4种视频节点",
             "points": ["▸  T2V：纯文字  →  视频", "▸  I2V：一张图  →  视频  (推荐入门)", "▸  R2V：多参考图  →  视频", "▸  Video-Edit：已有视频再编辑"],
             "duration": 6.0},
            {"type": "code", "title": "图生视频工作流",
             "lines": ["[LoadImage: 商品图]", "      ↓  首帧图片", "[HappyHorse 1.0 I2V]", "      ↓", "[PreviewVideo]"],
             "duration": 5.0},
            {"type": "step", "step": 1, "total": 4,
             "title": "加载你的图片",
             "desc": "LoadImage  →  选择精修后的商品图\n图片越清晰，视频质量越高",
             "duration": 4.0},
            {"type": "step", "step": 2, "total": 4,
             "title": "设置参数",
             "desc": "mode 选异步\nresolution 720p  →  1080p\nduration 5s / 8s / 10s",
             "duration": 4.0},
            {"type": "step", "step": 3, "total": 4,
             "title": "写视频提示词",
             "desc": "描述运镜 + 环境变化 + 锁定产品\n「镜头缓慢推进，产品周围水汽流动...」",
             "duration": 4.5},
            {"type": "step", "step": 4, "total": 4,
             "title": "异步查询下载",
             "desc": "提交后等5-10分钟\n用「异步任务查询」节点拿视频",
             "duration": 4.0},
            {"type": "tip", "title": "视频提示词公式",
             "tips": ["写运镜：「镜头缓慢推进 / 环绕旋转」", "写变化：「周围有水汽 / 光粒 / 微风效果」", "锁定：「保持产品外观颜色logo不变」"],
             "duration": 5.5},
            {"type": "outro", "duration": 5.0},
        ]
    },

    4: {
        "title": "AI作词作曲\n+ 口播配音",
        "subtitle": "Suno  &  豆包TTS 实战",
        "theme": 4,
        "next": "拆解爆款视频，AI反推提示词",
        "scenes": [
            {"type": "intro", "duration": 3.5},
            {"type": "content", "title": "音频节点一览",
             "points": ["◆  Suno：AI作词作曲，出完整歌曲", "◆  豆包TTS 2.0：中文口播配音", "◆  MiniMax speech：高端配音", "◆  Gemini TTS：多语言配音"],
             "duration": 6.0},
            {"type": "step", "step": 1, "total": 4,
             "title": "Suno 生成背景音乐",
             "desc": "节点：音频 | Suno 音乐生成\n生成模式  →  普通生成\n模型  →  V5 最新通用",
             "duration": 4.5},
            {"type": "tip", "title": "Suno 提示词示例",
             "tips": ["「适合美妆产品推广的中文流行电子歌」", "「副歌朗朗上口，整体明亮积极」", "风格标签：pop / cinematic / lofi"],
             "duration": 5.0},
            {"type": "step", "step": 2, "total": 4,
             "title": "豆包TTS 配音旁白",
             "desc": "节点：音频 | 豆包语音合成 2.0\n粘入旁白文案  →  选音色  →  运行",
             "duration": 4.0},
            {"type": "step", "step": 3, "total": 4,
             "title": "停顿控制技巧",
             "desc": "在文字中插入  <#0.5#>\n控制朗读节奏，强调关键词",
             "duration": 4.0},
            {"type": "step", "step": 4, "total": 4,
             "title": "合并音视频",
             "desc": "导入剪映 / PR\n配音主音轨 80%\n音乐副音轨 20% 背景",
             "duration": 4.0},
            {"type": "tip", "title": "实用建议",
             "tips": ["Suno 一次出2首，选最好的那首", "配音音色和品牌调性要匹配", "纯音乐时打开「生成纯音乐」开关"],
             "duration": 5.0},
            {"type": "outro", "duration": 5.0},
        ]
    },

    5: {
        "title": "拆解爆款视频\nAI反推提示词",
        "subtitle": "Gemini 分析  +  Grok 重构",
        "theme": 5,
        "next": "全自动AI内容工厂综合实战",
        "scenes": [
            {"type": "intro", "duration": 3.5},
            {"type": "content", "title": "这条链路能做什么",
             "points": ["◈  拆解爆款视频镜头逻辑", "◈  分析运镜 / 色调 / 节奏", "◈  生成可直接使用的提示词", "◈  复刻同款，植入你的产品"],
             "duration": 6.0},
            {"type": "code", "title": "视频拆解工作流",
             "lines": ["[填入爆款视频URL]", "      ↓", "[Gemini 3 Flash 视频分析]", "      ↓  分析报告", "[Grok 多图剧本重构]", "      ↓  生成视频提示词", "[HappyHorse / Veo 生成视频]"],
             "duration": 6.0},
            {"type": "step", "step": 1, "total": 3,
             "title": "Gemini 分析视频",
             "desc": "节点：多模态 | Gemini 3 Flash 分析\n分析任务  →  视频分镜拆解\n输出格式  →  Markdown结构化",
             "duration": 4.5},
            {"type": "step", "step": 2, "total": 3,
             "title": "Grok 重构提示词",
             "desc": "把分析报告接入 Grok 重构节点\n填入你的产品描述和运镜偏好\n输出  →  视频生成专用提示词",
             "duration": 4.5},
            {"type": "step", "step": 3, "total": 3,
             "title": "生成同款视频",
             "desc": "将重构提示词接入视频节点\nHappyHorse / Veo / Vidu3 均可\n出片！",
             "duration": 4.0},
            {"type": "tip", "title": "不止视频分析",
             "tips": ["商品图：用「商品卖点分析」任务类型", "长文档：用 Gemini 3.5 Flash 节点", "联网搜索：GPT-5.4 Mini 开启搜索工具"],
             "duration": 5.5},
            {"type": "outro", "duration": 5.0},
        ]
    },

    6: {
        "title": "AI内容工厂\n全自动一条龙",
        "subtitle": "1张图  →  图片+视频+音乐+配音",
        "theme": 6,
        "next": "更多垂直场景专题持续更新",
        "scenes": [
            {"type": "intro", "duration": 3.5},
            {"type": "content", "title": "今天要完成什么",
             "points": ["◆  4种风格商品精修图", "◆  2条展示视频（异步批量）", "◆  1首品牌背景音乐", "◆  1条产品旁白配音"],
             "duration": 6.0},
            {"type": "code", "title": "4条并行支线",
             "lines": ["商品原图", "  A  →  多风格精修图", "  B  →  展示视频（异步）", "  C  →  背景音乐（Suno）", "  D  →  旁白配音（TTS）"],
             "duration": 5.5},
            {"type": "step", "step": 1, "total": 4,
             "title": "Phase 1：图片精修",
             "desc": "4个 GPT-Image-2 修图实例并排\n不同场景提示词各出1-2张\n约2-5分钟完成",
             "duration": 4.5},
            {"type": "step", "step": 2, "total": 4,
             "title": "Phase 2：视频+音乐同时提交",
             "desc": "HappyHorse I2V 设为异步\nSuno 同时提交\n不用等！先做下一步",
             "duration": 4.5},
            {"type": "step", "step": 3, "total": 4,
             "title": "Phase 3：快速出配音",
             "desc": "豆包TTS 10秒内完成\n这期间视频/音乐在后台生成中",
             "duration": 4.0},
            {"type": "step", "step": 4, "total": 4,
             "title": "Phase 4：统一收货",
             "desc": "异步查询节点拿视频和音乐\n全部保存到 output 文件夹\n导入剪映合成发布！",
             "duration": 4.5},
            {"type": "tip", "title": "实际成本对比",
             "tips": ["传统方案：摄影+视频+音乐+配音 = 2000元+", "AI方案：全套素材约 5-12元", "节省成本 > 99%，效率提升 10倍+"],
             "duration": 5.5},
            {"type": "outro", "duration": 5.0},
        ]
    },
}


# ─── 视频渲染核心 ──────────────────────────────────────────────────────────────

def render_episode(ep_num):
    print(f"\n{'='*50}")
    print(f"  渲染第 {ep_num:02d} 期视频...")
    print(f"{'='*50}")

    script = EPISODE_SCRIPTS[ep_num]
    theme = THEMES[script["theme"]]
    scenes = script["scenes"]
    total_steps_in_scenes = sum(1 for s in scenes if s["type"] == "step")

    # 清理帧目录
    ep_frames = FRAMES_DIR / f"ep{ep_num:02d}"
    if ep_frames.exists():
        shutil.rmtree(ep_frames)
    ep_frames.mkdir(parents=True)

    frame_idx = 0
    step_counter = 0
    total_script_steps = len([s for s in scenes if s["type"] == "step"])

    for scene in scenes:
        stype = scene["type"]
        dur = scene["duration"]
        n_frames = int(dur * FPS)

        if stype == "intro":
            for f in range(n_frames):
                ratio = f / n_frames
                frame = make_intro_frame(ep_num, script["title"],
                                         script["subtitle"], ratio, theme)
                write_frame(frame, ep_frames, frame_idx)
                frame_idx += 1

        elif stype == "content":
            n_pts = len(scene["points"])
            for f in range(n_frames):
                ratio = f / n_frames
                # 前半段按步骤显示要点
                show_r = min(1.0, ratio * 1.6)
                frame = make_content_frame(
                    scene["title"], scene["points"],
                    step_counter, total_script_steps + 2,
                    theme, show_ratio=show_r
                )
                write_frame(frame, ep_frames, frame_idx)
                frame_idx += 1

        elif stype == "step":
            step_counter += 1
            for f in range(n_frames):
                ratio = f / n_frames
                frame = make_step_frame(
                    scene["step"], scene["total"],
                    scene["title"], scene["desc"],
                    step_counter, total_script_steps + 2,
                    theme, show_ratio=min(1.0, ratio * 2.5)
                )
                write_frame(frame, ep_frames, frame_idx)
                frame_idx += 1

        elif stype == "code":
            for f in range(n_frames):
                ratio = f / n_frames
                frame = make_code_frame(
                    scene["title"], scene["lines"],
                    step_counter, total_script_steps + 2,
                    theme, show_ratio=min(1.0, ratio * 1.8)
                )
                write_frame(frame, ep_frames, frame_idx)
                frame_idx += 1

        elif stype == "tip":
            for f in range(n_frames):
                ratio = f / n_frames
                frame = make_tip_frame(
                    scene["title"], scene["tips"],
                    step_counter, total_script_steps + 2,
                    theme, show_ratio=min(1.0, ratio * 1.6)
                )
                write_frame(frame, ep_frames, frame_idx)
                frame_idx += 1

        elif stype == "outro":
            for f in range(n_frames):
                ratio = f / n_frames
                frame = make_outro_frame(
                    script["next"], "关注不错过下期更新",
                    theme, show_ratio=min(1.0, ratio * 2.0)
                )
                write_frame(frame, ep_frames, frame_idx)
                frame_idx += 1

        print(f"  场景 [{stype}] → {n_frames} 帧 ✓")

    # 合成视频
    out_path = OUTPUT_DIR / f"ep{ep_num:02d}_攀升AI节点教程.mp4"
    print(f"\n  合成视频: {frame_idx} 帧 → {out_path.name}")
    ok = frames_to_video(ep_frames, out_path)
    if ok:
        size = os.path.getsize(out_path) / (1024*1024)
        duration = frame_idx / FPS
        print(f"  ✅ 完成！时长: {duration:.1f}秒  大小: {size:.1f}MB")
    else:
        print(f"  ❌ 合成失败")

    # 清理帧
    shutil.rmtree(ep_frames)
    return ok


# ─── 主入口 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    print("🎬 攀升AI节点教程视频生成器")
    print(f"   输出目录: {OUTPUT_DIR}")
    print(f"   分辨率: {W}×{H}  FPS: {FPS}")
    print()

    import sys
    eps = list(map(int, sys.argv[1:])) if len(sys.argv) > 1 else list(range(1, 7))

    results = {}
    for ep in eps:
        ok = render_episode(ep)
        results[ep] = ok

    print("\n" + "="*50)
    print("渲染汇总：")
    for ep, ok in results.items():
        status = "✅" if ok else "❌"
        print(f"  第{ep:02d}期: {status}")

    all_ok = all(results.values())
    print(f"\n输出目录: {OUTPUT_DIR}")
    sys.exit(0 if all_ok else 1)
