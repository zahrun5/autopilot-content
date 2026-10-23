"""
LLM Module - Generate quotes konten via OpenRouter (9router)
"""

import json
import re
import sys
import os
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    OPENROUTER_API_KEY, LLM_MODEL, LLM_BASE_URL,
    JUMLAH_SLIDE, NICHE_OPTIONS
)

SYSTEM_PROMPT = """Kamu adalah kurator konten quotes inspiratif profesional.
Tugasmu adalah membuat kumpulan quotes menarik dalam Bahasa Indonesia.
Selalu kembalikan respons dalam format JSON yang valid."""


def generate_script(niche: str = "motivasi", topik: str = None) -> dict:
    """
    Generate kumpulan quotes untuk video.

    Returns dict:
    {
        "judul": "...",
        "deskripsi": "...",
        "tags": ["...", "..."],
        "slides": [
            {
                "quote": "...",
                "author": "...",
                "keyword_foto": "..."
            },
            ...
        ]
    }
    """
    niche_label = NICHE_OPTIONS.get(niche, niche)
    topik_prompt = f'Topik spesifik: "{topik}"' if topik else f"Pilih sudut pandang menarik dari niche: {niche_label}"

    prompt = f"""Buat kumpulan quotes video untuk YouTube Shorts / Facebook Reels.

Niche: {niche_label}
{topik_prompt}
Jumlah quotes: {JUMLAH_SLIDE}

Kembalikan HANYA JSON valid (tanpa markdown, tanpa komentar) dengan struktur ini:
{{
  "judul": "judul video yang menarik dan SEO-friendly (max 70 karakter)",
  "deskripsi": "deskripsi video untuk YT/FB (150-250 karakter, engaging, ada emoji)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "slides": [
    {{
      "quote": "teks quote inspiratif dalam Bahasa Indonesia (1-2 kalimat, max 120 karakter, impactful)",
      "author": "nama tokoh atau sumber (contoh: 'Nelson Mandela' atau '— Anonim')",
      "keyword_foto": "keyword bahasa Inggris untuk cari foto di Pixabay (1-3 kata, tema nature/abstract/city)"
    }}
  ]
}}

Aturan:
- Quote harus singkat, padat, dan menohok
- Campur antara quote dari tokoh terkenal dan quote original
- keyword_foto harus tema yang cocok (sunset, mountain, ocean, forest, city lights, dll)
- Slide pertama = quote paling impactful sebagai hook
- Variasikan keyword_foto agar tiap slide punya foto berbeda"""

    print(f"[LLM] Generating quotes untuk niche: {niche_label}...")

    response = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android) autopilot-content/1.0",
        },
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.9,
            "max_tokens": 2000,
        },
        timeout=60,
    )
    response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"].strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        script = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM tidak mengembalikan JSON valid: {e}\n\nRaw:\n{raw}")

    for key in ["judul", "deskripsi", "tags", "slides"]:
        if key not in script:
            raise ValueError(f"JSON tidak lengkap, missing key: '{key}'")

    for i, slide in enumerate(script["slides"]):
        for sk in ["quote", "author", "keyword_foto"]:
            if sk not in slide:
                raise ValueError(f"Slide {i+1} missing key: '{sk}'")

    print(f"[LLM] Quotes generated: '{script['judul']}' ({len(script['slides'])} quotes)")
    return script


if __name__ == "__main__":
    result = generate_script(niche="motivasi")
    print(json.dumps(result, indent=2, ensure_ascii=False))
