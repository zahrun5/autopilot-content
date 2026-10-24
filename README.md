# Autopilot Content

Generate video slideshow quotes otomatis (AI script → foto → TTS → musik → render) lalu upload ke **Facebook** dan **YouTube**, dikendalikan penuh dari **bot Telegram**.

---

## Struktur Project

```
autopilot-content/
├── main.py                  # Entry point CLI (generate manual)
├── run_bot.sh               # Launcher bot via tmux (start/stop/restart/log)
├── setup_youtube.py         # Login OAuth YouTube (sekali, manual di terminal)
├── download_musik.py        # Download musik bebas copyright
├── cek_credential.py        # Cek semua credential sekaligus
├── test_tombol.py           # Test semua tombol bot (otomatis)
├── test_pesan.py            # Validasi format pesan Telegram
├── .env                     # Semua credential (git-ignored, mode 0600)
├── config/
│   ├── settings.py          # Setting non-secret (niche, ukuran, font, warna)
│   └── yt_client_secrets.json
├── src/
│   ├── bot.py               # Bot Telegram: menu, tombol, pipeline, notifikasi
│   ├── scheduler.py         # Worker auto-generate 24/7
│   ├── env_manager.py       # Baca/tulis/validasi .env + panel Settings
│   ├── llm.py               # Generate script via OpenRouter / 9router
│   ├── pixabay.py           # Fetch foto gratis dari Pixabay
│   ├── pexels.py            # Alternatif fetch foto dari Pexels
│   ├── tts.py               # Text-to-speech (edge-tts / gTTS)
│   ├── video.py             # Render video slideshow via moviepy
│   ├── upload.py            # Upload ke YouTube & Facebook
│   ├── yt_auth.py           # Helper OAuth YouTube (token + refresh + import ytbot)
│   └── fb_auth.py           # Helper token Facebook (cek + refresh otomatis)
├── musik/                   # Musik background bebas copyright (.mp3)
└── output/
    ├── audio/               # Audio TTS per slide
    ├── images/              # Foto yang didownload
    └── videos/              # Video hasil render
```

---

## Setup

### 1. Install dependencies

```bash
cd ~/autopilot-content
pip install -r requirements.txt
```

Butuh `ffmpeg` untuk render video. Di Termux:

```bash
pkg install ffmpeg
```

### 2. Isi `.env` (bukan `config/settings.py`)

Semua credential ada di file `.env` di root project. File ini **tidak** di-commit ke Git dan permission-nya `0600`.

| Key | Cara Dapat | Gratis? |
|-----|-----------|---------|
| `OPENROUTER_API_KEY` | https://openrouter.ai | Ya (ada free models) |
| `PIXABAY_API_KEY` | https://pixabay.com/api/docs | Ya, unlimited |
| `FACEBOOK_APP_ID` + `FACEBOOK_APP_SECRET` | Meta for Developers → App Dashboard | Ya |
| `FACEBOOK_PAGE_ID` + `FACEBOOK_PAGE_ACCESS_TOKEN` | `python fb_token.py llt` | Ya |
| `FACEBOOK_USER_ACCESS_TOKEN` | Graph API Explorer | Ya |
| `YOUTUBE_CLIENT_SECRETS` | Path ke `client_secrets.json` | Ya |
| `TELEGRAM_BOT_TOKEN` | @BotFather di Telegram | Ya |

> `FACEBOOK_APP_ID` & `FACEBOOK_APP_SECRET` opsional tapi **sangat disarankan** — dipakai untuk me-refresh token Facebook otomatis sebelum expired.

### 3. Setup YouTube (sekali saja)

**Cara tercepat** — kalau kamu sudah punya project `ytbot` (di `~/ytbot`), credential-nya bisa langsung dipakai:

```bash
python setup_youtube.py import    # copy client_secret.json + token.json dari ytbot
python setup_youtube.py status    # cek
```

> ⚠️ OAuth client **harus bertipe Desktop app** (`installed`). Client bertipe Web akan error `redirect_uri_mismatch` di Termux. `import` otomatis mengganti yang lama.

Kalau belum punya ytbot, login manual:

```bash
python setup_youtube.py login     # buka URL, pilih akun, paste kode
python setup_youtube.py status    # cek
python setup_youtube.py logout    # hapus token
```

Langkah di Google Cloud Console:
1. Buka https://console.cloud.google.com → buat project
2. Enable **YouTube Data API v3**
3. **OAuth 2.0 Client ID** → tipe **Desktop app** (bukan Web!)
4. Download JSON → simpan sebagai `config/yt_client_secrets.json`
5. Jalankan `python setup_youtube.py login`

Token disimpan di `config/yt_token.json` (mode 0600) dan **di-refresh otomatis** oleh bot. Bot tidak pernah menjalankan login interaktif.

### 4. Setup Facebook (sekali saja)

Facebook punya 2 jenis token, dipisah di `.env`:

| Key | Isi | Umur |
|-----|-----|------|
| `FACEBOOK_USER_ACCESS_TOKEN` | User token dari Graph API Explorer | pendek (1-2 jam) |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | Turunan long-lived user token → **dipakai upload** | tidak kedaluwarsa |

Plus `FACEBOOK_APP_ID` + `FACEBOOK_APP_SECRET` (dari App Dashboard → Settings → Basic) untuk refresh otomatis.

**Alurnya:**

1. Ambil user token dari https://developers.facebook.com/tools/explorer
   - Pilih app kamu → **Get Access Token** → **Get User Access Token**
   - Centang: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `pages_manage_video`, `public_profile`
   - Copy token
2. Paste ke `.env` sebagai `FACEBOOK_USER_ACCESS_TOKEN`
3. Tukar ke page token:
   ```bash
   python fb_token.py llt
   ```
4. Verifikasi:
   ```bash
   python fb_token.py scopes
   ```
   Hasil yang benar:
   ```
   Tipe    : PAGE
   Valid   : True
   Expires : (tidak ada) → TIDAK KEDALUWARSA ✅
   ```
   Kalau baris **Expires** tidak muncul → token tidak kedaluwarsa.

**Refresh otomatis:** kalau page token expired, `src/fb_auth.py` otomatis menukarnya dari user token (`llt` + `/me/accounts`) dan menyimpan yang baru ke `.env`. Jadi user token cukup di-set sekali.

Perintah lain:
```bash
python fb_token.py refresh   # refresh sekarang
python fb_token.py list      # daftar page + token
python fb_token.py link      # panduan
```

Cek semua credential sekaligus:
```bash
python cek_credential.py     # cek FB + YouTube + Telegram
```

### 5. Setup Telegram Bot

1. Chat **@BotFather** di Telegram → `/newbot` → simpan token
2. Masukkan ke `.env` sebagai `TELEGRAM_BOT_TOKEN`
3. Jalankan bot:
   ```bash
   ./run_bot.sh start
   ```
4. Buka chat bot kamu → `/start`

---

## Menjalankan Bot

```bash
cd ~/autopilot-content

./run_bot.sh start      # jalankan (background via tmux)
./run_bot.sh stop       # stop
./run_bot.sh restart    # restart
./run_bot.sh status     # cek status
./run_bot.sh log        # lihat log
./run_bot.sh attach     # masuk terminal bot (Ctrl+B lalu D untuk keluar)
```

> Kalau kamu mengubah `TELEGRAM_BOT_TOKEN` atau credential lain di `.env`, **restart bot** supaya nilainya terbaca.

### Tombol Bot

| Tombol | Fungsi |
|--------|--------|
| 🎬 Generate | Langsung generate video dengan niche & topik terpilih |
| 📂 Pilih Niche | Motivasi / Kehidupan / Sukses / Cinta |
| 📝 Topik Custom | Tulis topik spesifik sendiri |
| 📤 Upload ON/OFF | Aktifkan/matikan auto-upload ke FB & YT |
| ⚙️ Settings | Atur semua API key & credential |
| 📊 Status | Lihat status pipeline, scheduler, dan token |
| ⏰ Auto 24/7 | Toggle auto-generate terjadwal |
| ⬆️ Upload Terakhir | Upload ulang video terakhir |

### Panel Settings

Bisa mengatur langsung dari Telegram: `OPENROUTER_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `PIXABAY_API_KEY`, `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_USER_ACCESS_TOKEN`, `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `YOUTUBE_CLIENT_SECRETS`, `TELEGRAM_BOT_TOKEN`.

---

## Auto-Generate 24/7

`src/scheduler.py` menjalankan generate otomatis dengan interval + jitter-random, bisa di-toggle dari bot. State disimpan di `.scheduler.json` jadi tetap jalan setelah bot restart.

Aktifkan lewat tombol **⏰ Auto 24/7**, atau set env:

```bash
AUTO_UPLOAD_ENABLED=true
AUTO_INTERVAL_MINUTES=180
```

---

## Musik Background

Taruh file `.mp3` bebas copyright di folder `musik/`. Video akan pakai musik yang dipilih acak sebagai background.

Untuk download otomatis dari YouTube:
```bash
pkg install yt-dlp nodejs    # yt-dlp butuh Node untuk bypass JS challenge
python download_musik.py 3   # download 3 lagu
```

> `yt-dlp` di Termux wajib pakai `--js-runtimes node:/data/data/com.termux/files/usr/bin/node`, sudah otomatis di script.

---

## Cara Pakai CLI (tanpa bot)

```bash
# Generate + upload (niche default)
python main.py

# Niche spesifik
python main.py --niche kehidupan

# Topik spesifik
python main.py --niche motivasi --topik "5 kebiasaan orang sukses di pagi hari"

# Hanya generate video, skip upload (testing)
python main.py --no-upload
```

## Niche yang Tersedia

| Kode | Label |
|------|-------|
| `motivasi` | Motivasi & Inspirasi |
| `kehidupan` | Quotes Kehidupan |
| `sukses` | Sukses & Karir |
| `cinta` | Cinta & Hubungan |

---

## Contoh Flow

```
LLM (OpenRouter) → script JSON (judul, narasi per slide, keyword foto)
     ↓
Pixabay API → download foto per slide
     ↓
edge-tts → generate audio narasi per slide
     ↓
moviepy → gabungin foto + overlay + teks + audio + musik background → video.mp4
     ↓
YouTube Data API v3 + Facebook Graph API → upload otomatis
```

Upload di-trigger otomatis oleh bot, tapi tiap upload punya handling error sendiri — kalau YouTube gagal, upload Facebook tetap jalan (dan sebaliknya).

---

## Troubleshooting

Cek dulu semuanya:
```bash
python cek_credential.py
```

| Error | Penyebab & Solusi |
|-------|-----------------|
| `Login dibatalkan / timeout` (YouTube) | Token OAuth belum ada. Jalankan `python setup_youtube.py import` (dari ytbot) atau `login`. |
| `redirect_uri_mismatch` (YouTube) | OAuth client bertipe Web. Ganti ke Desktop app, atau pakai `setup_youtube.py import` dari ytbot. |
| `Error validating access token` / `code=190` (Facebook) | Page token expired. Otomatis di-refresh dari user token. Kalau gagal: `python fb_token.py llt` |
| `Token OAuth belum ada` (YouTube) | `python setup_youtube.py login` |
| `403` / scope kurang (Facebook) | Permission Graph Explorer belum dicentang. Lihat daftar permission di [Setup Facebook](#4-setup-facebook-sekali-saja). |
| `FFMPEG not found` | `pkg install ffmpeg` |
| Bot tidak merespon | `./run_bot.sh log` untuk lihat error, lalu `./run_bot.sh restart` |
| Perubahan `.env` tidak berefek | Restart bot: `./run_bot.sh restart` |
| Markdown error di Telegram | Sudah di-handle otomatis (fallback ke plain text) via `safe_edit`/`safe_reply`/`safe_send` |
| `no matches found: *.mp4` di zsh | zsh abort saat glob kosong. Pakai `find output -name '*.mp4' -delete` |

---

## Testing

```bash
python test_tombol.py    # test semua tombol bot (aman, tidak destructive)
python test_pesan.py     # validasi format pesan
```

`test_tombol.py` otomatis backup & restore `.env`, tidak menjalankan pipeline sungguhan, dan tidak bisa tidak sengaja trigger reset settings.
