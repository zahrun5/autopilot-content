# ============================================================
# KONFIGURASI UTAMA - Non-secret settings
# API keys ada di .env (jangan di-commit ke git!)
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys (dari .env) ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
YOUTUBE_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS", "config/yt_client_secrets.json")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "")

# --- LLM Settings ---
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

# --- Konten Settings ---
NICHE_OPTIONS = {
    "motivasi": "Motivasi & Inspirasi",
    "kehidupan": "Quotes Kehidupan",
    "sukses": "Sukses & Karir",
    "cinta": "Cinta & Hubungan",
}
DEFAULT_NICHE = "motivasi"
BAHASA = "Indonesia"
JUMLAH_SLIDE = 7        # jumlah quotes per video

# --- Video Settings (Portrait 9:16) ---
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
FPS = 30
DURASI_PER_SLIDE = 5    # detik per quote

# --- Tampilan Quote ---
FONT_SIZE_QUOTE  = 68   # ukuran teks quote utama
FONT_SIZE_AUTHOR = 42   # ukuran nama sumber quote
FONT_SIZE_WATERMARK = 30
OVERLAY_OPACITY  = 0.50 # kegelapan overlay foto (0.0 - 1.0)
QUOTE_COLOR      = "white"
AUTHOR_COLOR     = "#F0C040"  # kuning keemasan untuk nama sumber

# --- Musik ---
MUSIK_DIR = "musik"     # taruh file .mp3 di sini

# --- Output ---
OUTPUT_DIR = "output"
AUDIO_DIR  = "output/audio"
IMAGE_DIR  = "output/images"
VIDEO_DIR  = "output/videos"
