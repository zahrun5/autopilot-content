"""
Video Module - Render quotes video portrait 9:16
Foto + overlay + teks quote di tengah + musik background
Semua pakai Pillow + ffmpeg, hemat RAM.
"""

import os
import sys
import subprocess
import tempfile
import random
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    VIDEO_WIDTH, VIDEO_HEIGHT, FPS,
    FONT_SIZE_QUOTE, FONT_SIZE_AUTHOR, FONT_SIZE_WATERMARK,
    OVERLAY_OPACITY, VIDEO_DIR, IMAGE_DIR, DURASI_PER_SLIDE,
    QUOTE_COLOR, AUTHOR_COLOR, MUSIK_DIR
)

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    raise ImportError("Jalankan: pip install pillow")

FONT_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
FONT_ITALIC_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansOblique.ttf",
]
FONT_REGULAR_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


def load_font(paths, size):
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def wrap_teks(text, font, max_width, draw):
    """Wrap teks agar muat dalam max_width piksel."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_shadow(draw, text, pos, font, fill, shadow=(0, 0, 0), offset=3):
    x, y = pos
    for dx, dy in [(-offset, -offset), (offset, -offset),
                   (-offset, offset), (offset, offset)]:
        draw.text((x + dx, y + dy), text, font=font, fill=shadow + (200,))
    draw.text((x, y), text, font=font, fill=fill)


def buat_frame(foto_path, quote, author, nomor_total) -> Image.Image:
    """Buat satu frame portrait: foto blur + overlay + quote di tengah."""
    font_quote  = load_font(FONT_ITALIC_PATHS, FONT_SIZE_QUOTE)
    font_author = load_font(FONT_BOLD_PATHS, FONT_SIZE_AUTHOR)
    font_wm     = load_font(FONT_REGULAR_PATHS, FONT_SIZE_WATERMARK)

    # --- Background: foto di-crop ke portrait lalu di-blur sedikit ---
    bg = Image.open(foto_path).convert("RGB")
    # Crop center ke rasio 9:16
    bw, bh = bg.size
    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
    current_ratio = bw / bh
    if current_ratio > target_ratio:
        # terlalu lebar, crop kiri-kanan
        new_w = int(bh * target_ratio)
        left = (bw - new_w) // 2
        bg = bg.crop((left, 0, left + new_w, bh))
    else:
        # terlalu tinggi, crop atas-bawah
        new_h = int(bw / target_ratio)
        top = (bh - new_h) // 2
        bg = bg.crop((0, top, bw, top + new_h))
    bg = bg.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=4))

    # --- Overlay gradient gelap ---
    overlay = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    # Gradient dari atas (gelap) ke tengah (agak terang) ke bawah (gelap)
    for y in range(VIDEO_HEIGHT):
        if y < VIDEO_HEIGHT // 3:
            alpha = int(OVERLAY_OPACITY * 255 * (1 - y / (VIDEO_HEIGHT // 3) * 0.3))
        elif y < VIDEO_HEIGHT * 2 // 3:
            alpha = int(OVERLAY_OPACITY * 200)
        else:
            alpha = int(OVERLAY_OPACITY * 255)
        draw_ov.line([(0, y), (VIDEO_WIDTH, y)], fill=(0, 0, 0, alpha))

    frame = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGBA")
    draw = ImageDraw.Draw(frame)

    max_w = VIDEO_WIDTH - 120

    # --- Tanda kutip dekoratif ---
    font_kutip = load_font(FONT_BOLD_PATHS, 160)
    draw.text((60, VIDEO_HEIGHT // 4 - 80), "\u201c", font=font_kutip,
              fill=(255, 255, 255, 80))

    # --- Quote text (tengah vertikal) ---
    lines = wrap_teks(quote, font_quote, max_w, draw)
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        line_heights.append(bbox[3] - bbox[1])
    line_spacing = 20
    total_h = sum(line_heights) + line_spacing * (len(lines) - 1)
    y_start = (VIDEO_HEIGHT - total_h) // 2 - 60

    y = y_start
    for line, lh in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        lw = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - lw) // 2
        draw_shadow(draw, line, (x, y), font_quote,
                    fill=(255, 255, 255, 255), offset=3)
        y += lh + line_spacing

    # --- Author ---
    author_text = f"— {author}"
    bbox = draw.textbbox((0, 0), author_text, font=font_author)
    aw = bbox[2] - bbox[0]
    ax = (VIDEO_WIDTH - aw) // 2
    draw_shadow(draw, author_text, (ax, y + 40), font_author,
                fill=(0xF0, 0xC0, 0x40, 255), offset=2)

    # --- Watermark (pojok bawah) ---
    draw.text((40, VIDEO_HEIGHT - 70), "@quotesharian",
              font=font_wm, fill=(255, 255, 255, 120))

    return frame.convert("RGB")


def get_musik() -> str | None:
    """Ambil file musik random dari folder musik/."""
    os.makedirs(MUSIK_DIR, exist_ok=True)
    files = glob.glob(os.path.join(MUSIK_DIR, "*.mp3")) + \
            glob.glob(os.path.join(MUSIK_DIR, "*.m4a")) + \
            glob.glob(os.path.join(MUSIK_DIR, "*.wav"))
    if not files:
        return None
    return random.choice(files)


def render_slide(foto_path, quote, author, slide_index, total_slides, output_path):
    """Render satu slide ke mp4 (tanpa audio)."""
    print(f"[Video] Slide {slide_index+1}/{total_slides}: rendering...")
    frame = buat_frame(foto_path, quote, author, f"{slide_index+1}/{total_slides}")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        frame_path = tmp.name
        frame.save(frame_path, "JPEG", quality=95)

    try:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", frame_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-t", str(DURASI_PER_SLIDE),
            "-preset", "ultrafast",
            "-an",   # no audio, ditambah nanti
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error slide {slide_index+1}:\n{result.stderr[-500:]}")
    finally:
        os.unlink(frame_path)


def buat_video(slides, foto_paths, output_filename="output.mp4") -> str:
    """
    Render semua slide, concat, lalu tambahkan musik background.
    """
    os.makedirs(VIDEO_DIR, exist_ok=True)
    output_path = os.path.join(VIDEO_DIR, output_filename)
    total = len(slides)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Render tiap slide ke file temp
        temp_files = []
        for i, (slide, foto) in enumerate(zip(slides, foto_paths)):
            temp_out = os.path.join(tmpdir, f"slide_{i:02d}.mp4")
            render_slide(
                foto_path=foto,
                quote=slide["quote"],
                author=slide["author"],
                slide_index=i,
                total_slides=total,
                output_path=temp_out,
            )
            temp_files.append(temp_out)

        # Concat semua slide jadi satu video (belum ada audio)
        list_file = os.path.join(tmpdir, "concat.txt")
        with open(list_file, "w") as f:
            for tf in temp_files:
                f.write(f"file '{tf}'\n")

        video_no_audio = os.path.join(tmpdir, "video_no_audio.mp4")
        print(f"[Video] Menggabungkan {total} slide...")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            video_no_audio,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat gagal:\n{result.stderr[-500:]}")

        # Tambahkan musik background
        musik = get_musik()
        if musik:
            print(f"[Video] Menambahkan musik: {os.path.basename(musik)}")
            cmd = [
                "ffmpeg", "-y",
                "-i", video_no_audio,
                "-stream_loop", "-1",   # loop musik jika kurang panjang
                "-i", musik,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "128k",
                "-filter:a", "volume=0.4",  # volume musik 40%
                "-shortest",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg musik gagal:\n{result.stderr[-500:]}")
        else:
            print("[Video] Tidak ada musik ditemukan, video tanpa audio.")
            import shutil
            shutil.copy(video_no_audio, output_path)

    print(f"[Video] Selesai! Video tersimpan di: {output_path}")
    return output_path
