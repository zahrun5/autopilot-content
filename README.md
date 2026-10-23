# Autopilot Content - Slideshow Video Generator

Generate & upload video slideshow otomatis ke YouTube dan Facebook.

## Struktur Project

```
autopilot-content/
├── main.py                  # Entry point utama
├── requirements.txt
├── config/
│   └── settings.py          # Semua konfigurasi & API keys
├── src/
│   ├── llm.py               # Generate script via OpenRouter/9router
│   ├── pexels.py            # Fetch foto gratis dari Pexels
│   ├── tts.py               # Text-to-speech via edge-tts
│   ├── video.py             # Render video slideshow via moviepy
│   └── upload.py            # Upload ke YouTube & Facebook
└── output/
    ├── audio/               # File audio per slide
    ├── images/              # Foto yang didownload
    └── videos/              # Video hasil render
```

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Isi API Keys di `config/settings.py`

| Key | Cara Dapat | Gratis? |
|-----|-----------|---------|
| `OPENROUTER_API_KEY` | https://openrouter.ai | Ya (ada free models) |
| `PEXELS_API_KEY` | https://www.pexels.com/api | Ya, unlimited |
| YouTube OAuth | Google Cloud Console → YouTube Data API v3 | Ya |
| `FACEBOOK_PAGE_ID` + `FACEBOOK_ACCESS_TOKEN` | Meta for Developers | Ya |

### 3. Setup YouTube (sekali saja)
1. Buka https://console.cloud.google.com
2. Buat project baru
3. Enable **YouTube Data API v3**
4. Buat credentials → **OAuth 2.0 Client ID** → Desktop app
5. Download JSON → simpan sebagai `config/yt_client_secrets.json`
6. Jalankan pipeline → browser akan minta login Google (sekali saja)

### 4. Setup Facebook (sekali saja)
1. Buka https://developers.facebook.com → buat app
2. Tambahkan **Pages API**
3. Buka **Graph API Explorer** → generate **Page Access Token**
4. Untuk token permanen: tukar ke long-lived token via API
5. Isi `FACEBOOK_PAGE_ID` dan `FACEBOOK_ACCESS_TOKEN` di settings.py

## Cara Pakai

```bash
# Generate + upload (niche otomatis = tips)
python main.py

# Pilih niche spesifik
python main.py --niche motivasi
python main.py --niche teknologi
python main.py --niche edukasi

# Topik spesifik
python main.py --niche tips --topik "5 kebiasaan orang sukses di pagi hari"

# Hanya generate video, skip upload (untuk testing)
python main.py --no-upload
```

## Niche yang Tersedia
- `tips` - Tips & Fakta Menarik
- `motivasi` - Motivasi & Quotes
- `teknologi` - Teknologi & AI
- `edukasi` - Edukasi & How-to

## Contoh Flow

```
LLM (9router) → script JSON (judul, narasi per slide, keyword foto)
     ↓
Pexels API → download foto per slide
     ↓
edge-tts → generate audio narasi per slide
     ↓
moviepy → gabungin foto + overlay + teks + audio → video.mp4
     ↓
YouTube API + Facebook Graph API → upload otomatis
```
