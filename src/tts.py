"""
TTS Module - Generate audio narasi per slide menggunakan gTTS
Gratis, unlimited, pakai Google Translate TTS
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import AUDIO_DIR

try:
    from gtts import gTTS
except ImportError:
    raise ImportError("Jalankan: pip install gtts")


def generate_audio(teks: str, slide_index: int, lang: str = "id", max_retry: int = 3) -> str:
    """
    Generate audio dari teks menggunakan gTTS (Google TTS).
    Otomatis retry jika koneksi gagal.

    Returns: path file audio (.mp3)
    """
    os.makedirs(AUDIO_DIR, exist_ok=True)

    output_path = os.path.join(AUDIO_DIR, f"slide_{slide_index:02d}.mp3")

    print(f"[TTS] Generating audio slide {slide_index+1}: '{teks[:50]}...'")

    for attempt in range(1, max_retry + 1):
        try:
            tts = gTTS(text=teks, lang=lang, slow=False)
            tts.save(output_path)
            print(f"[TTS] Audio disimpan: {output_path}")
            return output_path
        except Exception as e:
            if attempt < max_retry:
                wait = attempt * 3
                print(f"[TTS] Gagal (percobaan {attempt}/{max_retry}): {e}. Retry dalam {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"[TTS] Gagal setelah {max_retry} percobaan: {e}")


def generate_semua_audio(slides: list) -> list:
    """
    Generate audio untuk semua slide.

    Args:
        slides: list slide dari LLM output (tiap slide punya 'narasi')

    Returns:
        list path audio, sesuai urutan slides
    """
    audio_paths = []
    for i, slide in enumerate(slides):
        # LLM output pakai 'quote' + 'author', gabungkan untuk TTS
        quote  = slide.get("quote", "")
        author = slide.get("author", "")
        narasi = slide.get("narasi", "")  # fallback jika ada key lama

        if not narasi:
            if quote and author:
                narasi = f"{quote}. — {author}"
            elif quote:
                narasi = quote
            else:
                raise ValueError(f"Slide {i+1} tidak punya quote atau narasi!")

        path = generate_audio(narasi, slide_index=i)
        audio_paths.append(path)
    return audio_paths


def get_audio_duration(audio_path: str) -> float:
    """
    Dapatkan durasi audio dalam detik.
    """
    try:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        return audio.info.length
    except ImportError:
        pass

    try:
        from moviepy import AudioFileClip
        with AudioFileClip(audio_path) as clip:
            return clip.duration
    except ImportError:
        pass

    print(f"[TTS] Warning: tidak bisa detect durasi, estimasi 5 detik")
    return 5.0


if __name__ == "__main__":
    test_slides = [
        {"narasi": "Halo semuanya! Selamat datang di channel kami. Hari ini kita akan belajar 5 fakta menarik yang mungkin belum kamu ketahui."},
        {"narasi": "Fakta pertama yang mengejutkan adalah bahwa otak manusia bisa menyimpan informasi setara dengan 2.5 petabyte data digital!"},
    ]
    paths = generate_semua_audio(test_slides)
    for p in paths:
        dur = get_audio_duration(p)
        print(f"{p} - durasi: {dur:.1f}s")
