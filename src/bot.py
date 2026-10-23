"""
Telegram Bot - Autopilot Content Controller
Kontrol pipeline generate & upload video via tombol Telegram
"""

import asyncio
import logging
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
from telegram.constants import ParseMode

from config.settings import NICHE_OPTIONS

logging.basicConfig(level=logging.WARNING)

# ── State global ──────────────────────────────────────────────
state = {
    "niche": "motivasi",
    "topik": None,
    "is_running": False,
    "stop_requested": False,
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

    upload_row = [
        InlineKeyboardButton("☁️ Upload ON/OFF", callback_data="toggle_upload"),
    ]

    return InlineKeyboardMarkup(niche_rows + [action_row, upload_row])


def status_text():
    niche_label = NICHE_OPTIONS.get(state["niche"], state["niche"])
    topik = state.get("topik") or "(auto)"
    upload = "ON ✅" if state.get("upload", True) else "OFF ❌"
    running = "🔄 *Sedang berjalan...*" if state["is_running"] else "💤 *Idle*"
    return (
        f"🎬 *Autopilot Content Bot*\n\n"
        f"Niche  : {niche_label}\n"
        f"Topik  : {topik}\n"
        f"Upload : {upload}\n\n"
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

        # Jalankan pipeline di thread terpisah agar bot tetap responsif
        thread = threading.Thread(
            target=run_pipeline_thread,
            args=(query, context),
            daemon=True,
        )
        thread.start()


def run_pipeline_thread(query, context):
    """Jalankan pipeline di background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run_pipeline_async(query, context))
    loop.close()


async def _run_pipeline_async(query, context):
    """Async wrapper untuk pipeline."""
    from main import run_pipeline

    chat_id = query.message.chat_id

    async def notif(msg):
        await context.bot.send_message(chat_id=chat_id, text=msg,
                                       parse_mode=ParseMode.MARKDOWN)

    try:
        await notif(f"🚀 *Memulai generate...*\nNiche: {NICHE_OPTIONS.get(state['niche'])}")

        # Jalankan pipeline (blocking, di thread ini)
        result = await asyncio.get_event_loop().run_in_executor(
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
        if not yt_url and not fb_url:
            msg += "\n_(upload dimatikan)_"

        await notif(msg)

        # Kirim file video jika ukuran < 50MB (limit Telegram)
        size_mb = os.path.getsize(video_path) / (1024 * 1024) if os.path.exists(video_path) else 999
        if size_mb < 50:
            await context.bot.send_video(
                chat_id=chat_id,
                video=open(video_path, "rb"),
                caption=f"🎬 {judul}",
                supports_streaming=True,
            )

    except Exception as e:
        await notif(f"❌ *Error:*\n`{str(e)[:300]}`")

    finally:
        state["is_running"] = False
        state["stop_requested"] = False
        # Update tombol kembali ke idle
        await query.edit_message_text(
            status_text(),
            reply_markup=kb_main(False),
            parse_mode=ParseMode.MARKDOWN,
        )


# ── Main ──────────────────────────────────────────────────────

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("Isi TELEGRAM_BOT_TOKEN di .env!")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("[Bot] Bot Telegram berjalan... Buka Telegram dan ketik /start")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
