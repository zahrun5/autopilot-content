"""
Telegram Bot - Autopilot Content Controller
Kontrol pipeline generate & upload video via tombol Telegram
"""

import asyncio
import logging
import os
import re
import subprocess
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Pastikan cwd = project dir agar path relatif konsisten
os.chdir(PROJECT_DIR)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

from config.settings import NICHE_OPTIONS, MUSIK_DIR

logging.basicConfig(level=logging.WARNING)

# ── State global ──────────────────────────────────────────────
state = {
    "niche": "motivasi",
    "topik": None,
    "is_running": False,
    "stop_requested": False,
    "upload": True,   # default: upload ON
    "awaiting_topic": False,
}


# ── Keyboard helpers ──────────────────────────────────────────

def kb_main(is_running=False):
    """Keyboard utama."""
    niche_buttons = [
        InlineKeyboardButton(
            ("✅ " if state["niche"] == k else "") + v.split(" & ")[0],
            callback_data=f"niche_{k}"
        )
        for k, v in NICHE_OPTIONS.items()
    ]
    # 2 tombol per baris
    niche_rows = [niche_buttons[i:i+2] for i in range(0, len(niche_buttons), 2)]

    action_row = (
        [InlineKeyboardButton("⏹ Stop", callback_data="stop")]
        if is_running else
        [InlineKeyboardButton("▶️ Mulai Generate", callback_data="generate")]
    )

    upload_on = state.get("upload", True)
    upload_row = [
        InlineKeyboardButton(
            "☁️ Upload: ON ✅" if upload_on else "☁️ Upload: OFF ❌",
            callback_data="toggle_upload",
        ),
        InlineKeyboardButton("📝 Topik Custom", callback_data="custom_topic"),
    ]

    return InlineKeyboardMarkup(niche_rows + [action_row, upload_row])


def cek_credential():
    """Cek credential upload yang tersedia."""
    import os
    from config.settings import (
        FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN, YOUTUBE_CLIENT_SECRETS
    )
    fb_ok = bool(FACEBOOK_PAGE_ID and FACEBOOK_ACCESS_TOKEN
                 and "your_fb" not in FACEBOOK_PAGE_ID)
    yt_ok = os.path.exists(YOUTUBE_CLIENT_SECRETS)
    return fb_ok, yt_ok


def status_text():
    niche_label = NICHE_OPTIONS.get(state["niche"], state["niche"])
    topik = state.get("topik") or "(auto)"
    upload = "ON ✅" if state.get("upload", True) else "OFF ❌"
    running = "🔄 *Sedang berjalan...*" if state["is_running"] else "💤 *Idle*"

    fb_ok, yt_ok = cek_credential()
    fb_txt = "✅ siap" if fb_ok else "❌ belum"
    yt_txt = "✅ siap" if yt_ok else "❌ belum"

    return (
        f"🎬 *Autopilot Content Bot*\n\n"
        f"Niche  : {niche_label}\n"
        f"Topik  : {topik}\n"
        f"Upload : {upload}\n\n"
        f"📺 YouTube   : {yt_txt}\n"
        f"📘 Facebook  : {fb_txt}\n\n"
        f"Status : {running}"
    )


# ── Handlers ──────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan menu utama."""
    await update.message.reply_text(
        status_text(),
        reply_markup=kb_main(state["is_running"]),
        parse_mode=ParseMode.MARKDOWN,
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek status bot & credential."""
    await update.message.reply_text(
        status_text(),
        reply_markup=kb_main(state["is_running"]),
        parse_mode=ParseMode.MARKDOWN,
    )


async def topik_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set topik custom: /topik 5 kebiasaan sukses"""
    text = (update.message.text or "").replace("/topik", "", 1).strip()
    if not text:
        state["topik"] = None
        await update.message.reply_text(
            "✅ Topik direset (otomatis).",
            reply_markup=kb_main(state["is_running"]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    state["topik"] = text
    await update.message.reply_text(
        f"✅ Topik diset:\n_{text}_",
        reply_markup=kb_main(state["is_running"]),
        parse_mode=ParseMode.MARKDOWN,
    )


async def upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle upload: /upload on|off"""
    arg = (update.message.text or "").split()[-1].lower() if update.message.text else ""
    if arg in ("on", "true", "1", "ya"):
        state["upload"] = True
    elif arg in ("off", "false", "0", "tidak"):
        state["upload"] = False
    else:
        state["upload"] = not state.get("upload", True)

    status = "ON ✅" if state["upload"] else "OFF ❌"
    await update.message.reply_text(
        f"☁️ Upload: {status}",
        reply_markup=kb_main(state["is_running"]),
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bantuan."""
    await update.message.reply_text(
        "🤖 *Perintah bot*\n\n"
        "/start — buka menu\n"
        "/status — cek status & credential\n"
        "/topik _teks_ — set topik custom\n"
        "/topik — reset ke otomatis\n"
        "/upload on|off — toggle auto upload\n"
        "/help — bantuan ini\n\n"
        "🎵 Kirim *link YouTube* untuk download musik background.\n\n"
        "▶️ Tombol *Mulai Generate* akan:\n"
        "1. Generate quotes via AI\n"
        "2. Download foto dari Pixabay\n"
        "3. Render video + musik\n"
        "4. Upload ke platform yang siap\n"
        "5. Kirim videonya ke sini",
        parse_mode=ParseMode.MARKDOWN,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── Pilih niche ──
    if data.startswith("niche_"):
        niche = data.replace("niche_", "")
        state["niche"] = niche
        await query.edit_message_text(
            status_text(),
            reply_markup=kb_main(state["is_running"]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── Toggle upload ──
    if data == "toggle_upload":
        state["upload"] = not state.get("upload", True)
        await query.edit_message_text(
            status_text(),
            reply_markup=kb_main(state["is_running"]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── Topik custom ──
    if data == "custom_topic":
        state["awaiting_topic"] = True
        await query.edit_message_text(
            "📝 Kirim *topik* yang kamu mau.\n\n"
            "Contoh: `5 kebiasaan orang sukses di pagi hari`\n\n"
            "_Ketik /topik_ untuk membatalkan._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── Stop ──
    if data == "stop":
        state["stop_requested"] = True
        await query.edit_message_text(
            status_text() + "\n\n⚠️ _Stop diminta, menunggu proses selesai..._",
            reply_markup=kb_main(True),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── Generate ──
    if data == "generate":
        if state["is_running"]:
            await query.answer("Sudah berjalan!", show_alert=True)
            return

        state["is_running"] = True
        state["stop_requested"] = False

        await query.edit_message_text(
            status_text(),
            reply_markup=kb_main(True),
            parse_mode=ParseMode.MARKDOWN,
        )

        # Jalankan pipeline sebagai task async (pipeline blocking
        # sudah di-handle di dalam dengan run_in_executor)
        asyncio.create_task(_run_pipeline_async(query, context))


async def _run_pipeline_async(query, context):
    """Async wrapper untuk pipeline."""
    from main import run_pipeline

    chat_id = query.message.chat.id if query.message else query.message.chat_id

    async def notif(msg):
        try:
            await context.bot.send_message(chat_id=chat_id, text=msg,
                                          parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            print(f"[Bot] Gagal kirim notif: {e}")

    try:
        await notif(f"🚀 *Memulai generate...*\nNiche: {NICHE_OPTIONS.get(state['niche'])}")

        # Pipeline ini blocking (HTTP + ffmpeg), jadi jalankan di thread executor.
        # Loop asyncio tetap milik main thread sehingga context.bot aman dipakai.
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_pipeline(
                niche=state["niche"],
                topik=state.get("topik"),
                skip_upload=not state.get("upload", True),
            )
        )

        video_path = result.get("video_path", "")
        judul = result.get("script", {}).get("judul", "")
        yt_url = result.get("upload", {}).get("youtube")
        fb_url = result.get("upload", {}).get("facebook")

        msg = f"✅ *Selesai!*\n\n📹 `{os.path.basename(video_path)}`\n"
        if yt_url:
            msg += f"\n🎬 [YouTube]({yt_url})"
        if fb_url:
            msg += f"\n📘 [Facebook]({fb_url})"

        errors = result.get("upload", {}).get("errors", {})
        if errors:
            msg += "\n\n⚠️ *Gagal upload:*"
            for plat, err in errors.items():
                emoji = "🎬" if plat == "youtube" else "📘"
                msg += f"\n{emoji} {plat}: `{str(err)[:180]}`"
        elif not yt_url and not fb_url:
            msg += "\n_(upload dimatikan)_"

        await notif(msg)

        # Kirim file video jika ukuran < 50MB (limit Telegram)
        size_mb = os.path.getsize(video_path) / (1024 * 1024) if os.path.exists(video_path) else 999
        if size_mb < 50:
            try:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=open(video_path, "rb"),
                    caption=f"🎬 {judul}",
                    supports_streaming=True,
                )
            except Exception as e:
                print(f"[Bot] Gagal kirim video: {e}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        await notif(f"❌ *Error:*\n`{str(e)[:300]}`")

    finally:
        state["is_running"] = False
        state["stop_requested"] = False
        # Update tombol kembali ke idle (abaikan error kalau msg sudah berubah)
        try:
            await query.edit_message_text(
                status_text(),
                reply_markup=kb_main(False),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            print(f"[Bot] Gagal update tombol: {e}")


# ── Main ──────────────────────────────────────────────────────

NODE_PATH = "/data/data/com.termux/files/usr/bin/node"

YT_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]+"
)


async def musik_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima link YouTube, download audionya sebagai musik background."""
    text = update.message.text.strip()

    # ── Mode: menunggu topik custom ──
    if state.get("awaiting_topic"):
        state["awaiting_topic"] = False
        if text.lower() in ("/topik", "/batal", "/cancel"):
            state["topik"] = None
            await update.message.reply_text(
                "✅ Topik direset (otomatis).",
                reply_markup=kb_main(state["is_running"]),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        state["topik"] = text
        await update.message.reply_text(
            f"✅ Topik diset:\n_{text}_",
            reply_markup=kb_main(state["is_running"]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    match = YT_REGEX.search(text)
    if not match:
        # Telegram: beri hint supaya user tidak bingung
        await update.message.reply_text(
            "💡 Kirim *link YouTube* untuk download musik background,\n"
            "atau pakai tombol *📝 Topik Custom*.\n\n"
            "_Ketik /help untuk daftar perintah._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    url = match.group(0)
    if not url.startswith("http"):
        url = "https://" + url

    await update.message.reply_text(
        f"🎵 *Mendownload audio...*\n`{url}`",
        parse_mode=ParseMode.MARKDOWN,
    )

    musik_dir = os.path.join(PROJECT_DIR, MUSIK_DIR)
    os.makedirs(musik_dir, exist_ok=True)
    prefix = f"{len(os.listdir(musik_dir)) + 1:02d}_"
    cmd = [
        "yt-dlp",
        "-f", "bestaudio",
        "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "--js-runtimes", f"node:{NODE_PATH}",
        "-o", os.path.join(musik_dir, f"{prefix}%(title)s.%(ext)s"),
        "--no-playlist", "--quiet", "--no-warnings",
        url,
    ]

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, text=True,
                                   cwd=PROJECT_DIR, timeout=600)
        )
        if result.returncode == 0:
            mp3s = sorted(f for f in os.listdir(musik_dir) if f.endswith(".mp3"))
            nama = mp3s[-1] if mp3s else "unknown"
            await update.message.reply_text(
                f"✅ *Musik berhasil didownload!*\n`{nama}`\n\n"
                f"Total musik: {len(mp3s)} file",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            err = result.stderr[:300] if result.stderr else "Unknown error"
            await update.message.reply_text(
                f"❌ *Gagal download:*\n`{err}`",
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: `{str(e)[:300]}`",
                                        parse_mode=ParseMode.MARKDOWN)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("Isi TELEGRAM_BOT_TOKEN di .env!")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("topik", topik_cmd))
    app.add_handler(CommandHandler("upload", upload_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, musik_handler))

    print("[Bot] Bot Telegram berjalan... Buka Telegram dan ketik /start")
    print("[Bot] Kirim link YouTube ke bot untuk download musik background.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
