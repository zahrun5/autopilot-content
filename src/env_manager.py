"""
Env Manager - baca & tulis .env dengan aman.

Dipakai panel settings di bot Telegram supaya semua credential bisa
diatur dari HP tanpa edit file manual.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
)

# Definisi semua setting yang bisa diedit dari bot.
# key = nama env var, label = tampilan di bot, secret = sembunyikan nilainya
FIELDS = {
    "OPENROUTER_API_KEY": {
        "label": "🔑 LLM API Key (9router/OpenRouter)",
        "secret": True,
        "group": "llm",
    },
    "LLM_BASE_URL": {
        "label": "🌐 LLM Base URL",
        "secret": False,
        "group": "llm",
        "default": "https://openrouter.ai/api/v1",
        "hint": "OpenRouter: https://openrouter.ai/api/v1\n9router: https://9router.ai/api/v1",    },
    "LLM_MODEL": {
        "label": "🤖 Model LLM",
        "secret": False,
        "group": "llm",
        "default": "openai/gpt-4o-mini",
    },
    "PIXABAY_API_KEY": {
        "label": "🖼️ Pixabay API Key",
        "secret": True,
        "group": "media",
    },
    "FACEBOOK_PAGE_ID": {
        "label": "📘 Facebook Page ID",
        "secret": False,
        "group": "sosial",
    },
    "FACEBOOK_ACCESS_TOKEN": {
        "label": "🔐 Facebook Access Token",
        "secret": True,
        "group": "sosial",
    },
    "FACEBOOK_APP_ID": {
        "label": "🆔 Facebook App ID",
        "secret": False,
        "group": "sosial",
        "help": "Dipakai untuk refresh token otomatis",
    },
    "FACEBOOK_APP_SECRET": {
        "label": "🔑 Facebook App Secret",
        "secret": True,
        "group": "sosial",
        "help": "Dipakai untuk refresh token otomatis",
    },
    "YOUTUBE_CLIENT_SECRETS": {
        "label": "🎬 YouTube client secrets (path)",
        "secret": False,
        "group": "sosial",
        "default": "config/yt_client_secrets.json",
    },
    "TELEGRAM_BOT_TOKEN": {
        "label": "🤖 Telegram Bot Token",
        "secret": True,
        "group": "sosial",
    },
}

GROUPS = {
    "llm": "🧠 LLM",
    "media": "🖼️ Media",
    "sosial": "🌐 Sosial Media",
}


# ── Baca ──────────────────────────────────────────────────────

def read_env():
    """Baca .env jadi dict."""
    data = {}
    if not os.path.exists(ENV_PATH):
        return data
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def get(key, default=""):
    """Ambil satu nilai dari .env."""
    return read_env().get(key, default)


def masked(key):
    """Nilai disensor untuk ditampilkan di bot."""
    val = get(key, "")
    if not val:
        return "❌ belum diisi"
    if FIELDS.get(key, {}).get("secret") and len(val) > 12:
        return f"✅ `{val[:6]}...{val[-4:]}`"
    return f"✅ `{val}`"


# ── Tulis ─────────────────────────────────────────────────────

def _sanitize_value(value):
    """Bersihkan input user: buang newline & karakter kontrol."""
    value = str(value).strip()
    value = re.sub(r"[\r\n]+", " ", value)
    return value.strip().strip('"').strip("'")


def set_value(key, value):
    """
    Set satu key di .env, maintaining key lain & urutan.
    Returns (ok, message)
    """
    if key not in FIELDS:
        return False, f"Key tidak dikenal: {key}"

    value = _sanitize_value(value)
    if not value:
        return False, "Nilai kosong, dibatalkan."

    # Cek placeholder
    if value.lower() in ("your_api_key", "your_key", "xxx", "-"):
        return False, "Itu masih placeholder. Isi dengan nilai aslinya."

    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

    new_line = f"{key}={value}"
    replaced = False
    out = []
    for ln in lines:
        if ln.strip().startswith(f"{key}="):
            if not replaced:
                out.append(new_line)
                replaced = True
            # skip duplikat
        else:
            out.append(ln)

    if not replaced:
        out.append(new_line)

    # Tulis dengan permission ketat (secret!)
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")
    os.chmod(ENV_PATH, 0o600)

    return True, f"{key} tersimpan"


def clear_value(key):
    """Hapus key dari .env."""
    if key not in FIELDS:
        return False, f"Key tidak dikenal: {key}"
    if not os.path.exists(ENV_PATH):
        return False, "File .env tidak ada"

    out = []
    for ln in open(ENV_PATH, encoding="utf-8").read().splitlines():
        if ln.strip().startswith(f"{key}="):
            continue
        out.append(ln)

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")
    os.chmod(ENV_PATH, 0o600)
    return True, f"{key} dihapus"


# ── Validasi ──────────────────────────────────────────────────

def validate(key):
    """Cek credential benar-benar berfungsi. Returns (ok, pesan)."""
    import requests

    val = get(key, "")
    if not val:
        return False, "Belum diisi"

    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android) autopilot-content/1.0"}

    try:
        if key == "OPENROUTER_API_KEY":
            base = get("LLM_BASE_URL", "https://9router.ai/api/v1").rstrip("/")
            r = requests.get(f"{base}/models", headers={**headers, "Authorization": f"Bearer {val}"}, timeout=20)
            if r.status_code == 200:
                return True, "✅ Token valid"
            if r.status_code == 401:
                return False, "❌ Token ditolak (401)"
            return False, f"⚠️ HTTP {r.status_code}"

        if key == "PIXABAY_API_KEY":
            r = requests.get("https://pixabay.com/api/",
                             params={"key": val, "q": "nature", "per_page": 3},
                             headers=headers, timeout=20)
            if r.status_code == 200:
                try:
                    if r.json().get("hits") is not None:
                        return True, "✅ Token valid"
                except Exception:
                    pass
                return False, "❌ Response tidak valid"
            if r.status_code == 400:
                return False, "❌ API key ditolak"
            return False, f"⚠️ HTTP {r.status_code}"

        if key == "FACEBOOK_ACCESS_TOKEN":
            pid = get("FACEBOOK_PAGE_ID", "")
            if not pid:
                return False, "❌ Page ID belum diisi"
            r = requests.get(f"https://graph.facebook.com/v18.0/{pid}",
                             params={"access_token": val, "fields": "id,name"},
                             headers=headers, timeout=20)
            d = r.json()
            if "error" in d:
                msg = d["error"].get("message", "")
                if d["error"].get("code") == 190:
                    return False, "❌ Token expired"
                return False, f"❌ {msg[:80]}"
            return True, f"✅ Valid - {d.get('data', d).get('name', 'Page')}"

        if key == "FACEBOOK_PAGE_ID":
            tok = get("FACEBOOK_ACCESS_TOKEN", "")
            if not tok:
                return False, "❌ Access token belum diisi"
            r = requests.get(f"https://graph.facebook.com/v18.0/{val}",
                             params={"access_token": tok, "fields": "id,name"},
                             headers=headers, timeout=20)
            d = r.json()
            if "error" in d:
                return False, f"❌ {d['error'].get('message', '')[:80]}"
            return True, f"✅ {d.get('data', d).get('name', 'Page')}"

        if key == "TELEGRAM_BOT_TOKEN":
            r = requests.get(f"https://api.telegram.org/bot{val}/getMe", headers=headers, timeout=20)
            if r.status_code == 200:
                return True, f"✅ Bot @{r.json()['result']['username']}"
            return False, "❌ Token ditolak"

        if key == "YOUTUBE_CLIENT_SECRETS":
            if os.path.exists(val):
                return True, f"✅ File ditemukan"
            return False, "❌ File tidak ditemukan"

        if key in ("LLM_BASE_URL", "LLM_MODEL"):
            return True, "✅ Tersimpan"

    except Exception as e:
        return False, f"❌ Error: {str(e)[:100]}"

    return True, "✅ Tersimpan"


def status_summary():
    """Ringkasan status semua field."""
    rows = []
    for key, meta in FIELDS.items():
        val = get(key, "")
        if not val:
            icon = "❌"
            detail = "belum diisi"
        elif meta.get("secret"):
            icon = "✅"
            detail = f"{val[:6]}...{val[-4:]}" if len(val) > 12 else "✅ tersimpan"
        else:
            icon = "✅"
            detail = val
        rows.append((key, meta["label"], icon, detail))
    return rows
