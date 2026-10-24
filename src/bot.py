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
from telegram.error import BadRequest

from config.settings import NICHE_OPTIONS, MUSIK_DIR
from src import env_manager as env
from src import scheduler as sched

logging.basicConfig(level=logging.WARNING)


def md(text):
    """
    Escape karakter markdown dari input user (untuk teks di luar code span).

    Backtick diganti dengan tanda kutip tunggal, bukan di-escape, karena
    escape backtick di luar code span bisa bikin Telegram error
    "Can't parse entities".
    """
    if text is None:
        return ""
    return (str(text)
            .replace("\\", "\\\\")
            .replace("*", "\\*")
            .replace("_", "\\_")
            .replace("`", "'"))


def code(value):
    """
    Format nilai sebagai code span Telegram.

    Di dalam backtick, TIDAK boleh ada escape backslash - Telegram
    memperlakukannya literal dan bisa merusak parsing ("Can't parse
    entities"). Jadi cukup buang karakter backtick saja.
    """
    if value is None:
        return ""
    v = str(value).replace("`", "'")
    return f"`{v}`"


# ── Pengiriman aman (auto fallback kalau markdown rusak) ──────

def plain(text):
    """Buang semua markdown dari teks."""
    import re
    t = str(text)
    t = re.sub(r"```.*?```", "", t, flags=re.S)
    t = t.replace("*", "").replace("_", "").replace("`", "")
    t = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", t)
    return t


async def safe_edit(query, text, reply_markup=None):
    """Edit pesan; kalau markdown error, fallback ke plain text."""
    try:
        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )
        return True
    except (BadRequest, ValueError) as e:
        if "parse entities" not in str(e).lower() and "can't parse" not in str(e).lower():
            print(f"[Bot] edit error: {e}")
            return False
        print("[Bot] Markdown rusak, fallback ke plain text")
        try:
            await query.edit_message_text(plain(text), reply_markup=reply_markup)
            return True
        except Exception as e2:
            print(f"[Bot] Gagal edit: {e2}")
            return False


async def safe_reply(update, text, reply_markup=None):
    """Kirim pesan; kalau markdown error, fallback ke plain text."""
    try:
        await update.message.reply_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )
        return True
    except (BadRequest, ValueError) as e:
        if "parse entities" not in str(e).lower() and "can't parse" not in str(e).lower():
            print(f"[Bot] reply error: {e}")
            return False
        print("[Bot] Markdown rusak, fallback ke plain text")
        try:
            await update.message.reply_text(
                plain(text), reply_markup=reply_markup
            )
            return True
        except Exception as e2:
            print(f"[Bot] Gagal reply: {e2}")
            return False


async def safe_send(bot, chat_id, text, reply_markup=None):
    """Kirim pesan via bot; fallback ke plain text."""
    try:
        await bot.send_message(
            chat_id=chat_id, text=text,
            reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )
        return True
    except (BadRequest, ValueError) as e:
        if "parse entities" not in str(e).lower() and "can't parse" not in str(e).lower():
            print(f"[Bot] send error: {e}")
            return False
        print("[Bot] Markdown rusak, fallback ke plain text")
        try:
            await bot.send_message(
                chat_id=chat_id, text=plain(text), reply_markup=reply_markup
            )
            return True
        except Exception as e2:
            print(f"[Bot] Gagal send: {e2}")
            return False


# ── State global ──────────────────────────────────────────────
state = {
    "niche": "motivasi",
    "topik": None,
    "is_running": False,
    "stop_requested": False,
    "upload": True,   # default: upload ON
    "awaiting_topic": False,
    "awaiting_env": None,   # key env yang sedang diisi user
    "awaiting_interval": False,
}

# Chat ID user (diisi otomatis saat user chat bot) - dipakai notif scheduler
CHAT_ID = None


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

    # Baris tambahan: Settings + Auto 24/7
    extra_row = [
        InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
        InlineKeyboardButton("🤖 Auto 24/7", callback_data="auto_panel"),
    ]

    return InlineKeyboardMarkup(niche_rows + [action_row, upload_row, extra_row])


# ── Keyboard panel settings ───────────────────────────────────

def kb_settings(group="all"):
    """Keyboard panel settings."""
    rows = []

    if group == "all":
        # Ringkasan + navigasi group
        rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="settings")])
        for gname, glabel in env.GROUPS.items():
            rows.append([InlineKeyboardButton(glabel, callback_data=f"setgroup_{gname}")])
        rows.append([InlineKeyboardButton("◀️ Kembali", callback_data="back_main")])
        return InlineKeyboardMarkup(rows)

    # Isi per group
    for key, meta in env.FIELDS.items():
        if meta.get("group") != group:
            continue
        val = env.get(key, "")
        icon = "✅" if val else "❌"
        label = meta["label"].split(" ", 1)[1]  # buang emoji pertama
        rows.append([InlineKeyboardButton(
            f"{icon} {label}", callback_data=f"setval_{key}"
        )])

    rows.append([InlineKeyboardButton("🗑️ Reset semua", callback_data="settings_reset")])
    rows.append([InlineKeyboardButton("◀️ Kembali", callback_data="settings")])
    return InlineKeyboardMarkup(rows)


def settings_summary_text():
    """Teks ringkasan semua setting."""
    lines = ["⚙️ *SETTINGS*\n"]
    for gname, glabel in env.GROUPS.items():
        lines.append(f"\n*{glabel}*")
        for key, meta in env.FIELDS.items():
            if meta.get("group") != gname:
                continue
            val = env.get(key, "")
            if not val:
                status = "❌ belum"
            elif meta.get("secret"):
                status = f"✅ {code(val[:6] + '...' + val[-4:])}" if len(val) > 12 else "✅ tersimpan"
            else:
                status = f"✅ {code(val)}"
            lines.append(f"  {md(meta['label'])}: {status}")
    return "\n".join(lines)


def kb_auto():
    """Keyboard panel auto 24/7."""
    s = sched.get_state()
    enabled = s.get("enabled", False)

    rows = [
        [InlineKeyboardButton(
            "⏸️ Matikan Auto" if enabled else "▶️ Nyalakan Auto 24/7",
            callback_data="auto_toggle"
        )],
        [InlineKeyboardButton(f"⏱️ Interval: {s.get('interval_hours', 6)} jam", callback_data="auto_interval")],
        [InlineKeyboardButton(
            f"☁️ Auto Upload: {'ON ✅' if s.get('upload', True) else 'OFF ❌'}",
            callback_data="auto_upload"
        )],
        [InlineKeyboardButton("◀️ Kembali", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(rows)


def auto_status_text():
    s = sched.get_state()
    enabled = "✅ ON" if s.get("enabled") else "❌ OFF"
    import datetime
    last = "belum pernah"
    if s.get("last_run"):
        last = datetime.datetime.fromtimestamp(s["last_run"]).strftime("%d/%m %H:%M")
    err = f"\n⚠️ Error terakhir: {code(s['last_error'][:150])}" if s.get("last_error") else ""

    return (
        "🤖 *AUTO GENERATE 24/7*\n\n"
        f"Status     : {enabled}\n"
        f"Interval   : {s.get('interval_hours', 6)} jam\n"
        f"Upload     : {'ON ✅' if s.get('upload', True) else 'OFF ❌'}\n"
        f"Niche      : {NICHE_OPTIONS.get(s.get('niche', 'motivasi'), '?')}\n"
        f"Terakhir   : {last}\n"
        f"Total run  : {s.get('total_runs', 0)}\n"
        f"Berikutnya : {sched.human_next_run(s)}\n"
        f"{err}\n\n"
        "_Bot harus tetap jalan (tmux) supaya auto generate aktif._"
    )


def cek_credential():
    """Cek credential upload yang tersedia."""
    import os
    from src import fb_auth
    from config.settings import YOUTUBE_CLIENT_SECRETS
    fb_ok = bool(fb_auth.page_id() and fb_auth.page_token())
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
    global CHAT_ID
    if update.message and update.message.chat:
        CHAT_ID = update.message.chat.id

    await safe_reply(
            update,
        status_text(),
        reply_markup=kb_main(state["is_running"]),
    )


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buka panel settings."""
    await safe_reply(
            update,
        settings_summary_text(),
        reply_markup=kb_settings("all"),
    )


async def auto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buka panel auto 24/7."""
    await safe_reply(
            update,
        auto_status_text(),
        reply_markup=kb_auto(),
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek status bot & credential."""
    await safe_reply(
            update,
        status_text(),
        reply_markup=kb_main(state["is_running"]),
    )


async def topik_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set topik custom: /topik 5 kebiasaan sukses"""
    text = (update.message.text or "").replace("/topik", "", 1).strip()
    if not text:
        state["topik"] = None
        await safe_reply(
            update,
            "✅ Topik direset (otomatis).",
            reply_markup=kb_main(state["is_running"]),
        )
        return

    state["topik"] = text
    await safe_reply(
            update,
        f"✅ Topik diset:\n_{md(text)}_",
        reply_markup=kb_main(state["is_running"]),
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
    await safe_reply(
            update,
        f"☁️ Upload: {status}",
        reply_markup=kb_main(state["is_running"]),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bantuan."""
    await safe_reply(
            update,
        "🤖 *Perintah bot*\n\n"
        "/start — buka menu\n"
        "/status — cek status & credential\n"
        "/settings — panel semua credential (API key, Page ID, dll)\n"
        "/auto — panel auto generate 24/7\n"
        "/topik _teks_ — set topik custom\n"
        "/topik — reset ke otomatis\n"
        "/upload on|off — toggle auto upload\n"
        "/help — bantuan ini\n\n"
        "🎵 Kirim *link YouTube* untuk download musik background.\n\n"
        "⚙️ *Semua credential bisa diatur dari bot:*\n"
        "• LLM API key + Base URL + model\n"
        "• Pixabay API key\n"
        "• Facebook Page ID + Access Token\n"
        "• YouTube client_secrets path\n"
        "• Telegram bot token\n\n"
        "🤖 *Auto 24/7:*\n"
        "Set interval (jam), nyalakan/matikan, dan auto upload.\n"
        "Bot harus jalan di tmux supaya auto aktif.",
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        print(f"[Bot] query.answer error: {e}")

    data = query.data or ""

    try:
        await _handle_button(query, data, context)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Bot] Error di button '{data}': {e}")
        try:
            await query.answer(
                f"❌ Error: {str(e)[:150]}",
                show_alert=True,
            )
        except Exception:
            pass


async def _handle_button(query, data, context=None):
    """Handler logic tombol (dipisah supaya error bisa di-catch)."""
    # ── Pilih niche ──
    if data.startswith("niche_"):
        niche = data.replace("niche_", "")
        state["niche"] = niche
        await safe_edit(
            query,
            status_text(),
            reply_markup=kb_main(state["is_running"]),
        )
        return

    # ── Toggle upload ──
    if data == "toggle_upload":
        state["upload"] = not state.get("upload", True)
        await safe_edit(
            query,
            status_text(),
            reply_markup=kb_main(state["is_running"]),
        )
        return

    # ── Topik custom ──
    if data == "custom_topic":
        state["awaiting_topic"] = True
        await safe_edit(
            query,
            "📝 Kirim *topik* yang kamu mau.\n\n"
            "Contoh: `5 kebiasaan orang sukses di pagi hari`\n\n"
            "Ketik /topik untuk membatalkan.",
        )
        return

    # ── Panel Settings ──
    if data == "settings":
        await safe_edit(
            query,
            settings_summary_text(),
            reply_markup=kb_settings("all"),
        )
        return

    if data.startswith("setgroup_"):
        group = data.replace("setgroup_", "")
        await safe_edit(
            query,
            f"*{env.GROUPS.get(group, group)}*\n\n"
            "_Pilih field yang mau diubah:_",
            reply_markup=kb_settings(group),
        )
        return

    if data.startswith("setval_"):
        key = data.replace("setval_", "")
        meta = env.FIELDS.get(key)
        if not meta:
            await query.answer("Field tidak dikenal", show_alert=True)
            return

        state["awaiting_env"] = key
        current = env.get(key, "")
        cur_txt = f"\n\nNilai sekarang: {code(current[:8] + '...' + current[-4:])}" if (
            current and meta.get("secret") and len(current) > 12
        ) else (f"\n\nNilai sekarang: {code(current)}" if current else "\n\n_Belum diisi._")

        # Hint tidak boleh dibungkus _..._ kalau multi-line: underscore
        # italic harus balance per baris, kalau tidak Telegram error parse.
        hint = f"\n\n{meta['hint']}" if meta.get("hint") else ""
        await safe_edit(
            query,
            f"📝 *{meta['label']}*\n\n"
            f"Kirim nilai baru.{cur_txt}{hint}\n\n"
            "_Ketik /batal untuk membatalkan._",
        )
        return

    if data == "settings_reset":
        await safe_edit(
            query,
            "⚠️ *Reset semua setting?*\n\n"
            "Semua credential akan dihapus dari .env.\n"
            "Kamu harus isi ulang semuanya.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Ya, reset semua", callback_data="settings_reset_yes")],
                [InlineKeyboardButton("❌ Batal", callback_data="settings")],
            ]),
        )
        return

    if data == "settings_reset_yes":
        for key in env.FIELDS:
            env.clear_value(key)
        await safe_edit(
            query,
            "🗑️ Semua setting sudah dihapus.",
            reply_markup=kb_settings("all"),
        )
        return

    # ── Panel Auto 24/7 ──
    if data == "auto_panel":
        await safe_edit(
            query,
            auto_status_text(),
            reply_markup=kb_auto(),
        )
        return

    if data == "auto_toggle":
        s = sched.get_state()
        new_state = sched.set_enabled(not s.get("enabled", False))
        if new_state.get("enabled"):
            scheduler.start()
        await safe_edit(
            query,
            auto_status_text(),
            reply_markup=kb_auto(),
        )
        return

    if data == "auto_interval":
        state["awaiting_interval"] = True
        await safe_edit(
            query,
            "⏱️ *Mau generate tiap berapa jam?*\n\n"
            "Kirim angka, contoh: `2` (setiap 2 jam)\n"
            "_Ketik /batal untuk membatalkan._",
        )
        return

    if data == "auto_upload":
        s = sched.get_state()
        sched.set_enabled(
            s.get("enabled", False),
            upload=not s.get("upload", True),
        )
        await safe_edit(
            query,
            auto_status_text(),
            reply_markup=kb_auto(),
        )
        return

    # ── Kembali ke menu utama ──
    if data == "back_main":
        await safe_edit(
            query,
            status_text(),
            reply_markup=kb_main(state["is_running"]),
        )
        return

    # ── Stop ──
    if data == "stop":
        state["stop_requested"] = True
        await safe_edit(
            query,
            status_text() + "\n\n⚠️ *Stop diminta, menunggu proses selesai...*",
            reply_markup=kb_main(True),
        )
        return

    # ── Generate ──
    if data == "generate":
        if state["is_running"]:
            await query.answer("Sudah berjalan!", show_alert=True)
            return

        state["is_running"] = True
        state["stop_requested"] = False

        await safe_edit(
            query,
            status_text(),
            reply_markup=kb_main(True),
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
            await safe_send(context.bot, chat_id=chat_id, text=msg)
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

        msg = f"✅ *Selesai!*\n\n📹 {code(os.path.basename(video_path))}\n"
        if yt_url:
            msg += f"\n🎬 [YouTube]({yt_url})"
        if fb_url:
            msg += f"\n📘 [Facebook]({fb_url})"

        errors = result.get("upload", {}).get("errors", {})
        if errors:
            msg += "\n\n⚠️ *Gagal upload:*"
            for plat, err in errors.items():
                emoji = "🎬" if plat == "youtube" else "📘"
                msg += f"\n{emoji} {plat}: {code(str(err)[:180])}"
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
                    caption=f"🎬 {md(judul)}",
                    supports_streaming=True,
                )
            except Exception as e:
                print(f"[Bot] Gagal kirim video: {e}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        await notif(f"❌ *Error:*\n{code(str(e)[:300])}")

    finally:
        state["is_running"] = False
        state["stop_requested"] = False
        # Update tombol kembali ke idle (abaikan error kalau msg sudah berubah)
        try:
            await safe_edit(
            query,
                status_text(),
                reply_markup=kb_main(False),
            )
        except Exception as e:
            print(f"[Bot] Gagal update tombol: {e}")


# ── Main ──────────────────────────────────────────────────────

NODE_PATH = "/data/data/com.termux/files/usr/bin/node"

YT_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]+"
)


async def musik_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input teks: setting env, interval scheduler, atau link YouTube."""
    text = update.message.text.strip()

    # ── Mode: menunggu interval scheduler ──
    if state.get("awaiting_interval"):
        state["awaiting_interval"] = False
        if text.lower() in ("/batal", "/cancel"):
            await safe_reply(
            update,
                "❌ Dibatalkan.",
                reply_markup=kb_auto(),
            )
            return
        try:
            jam = int(re.sub(r"[^0-9]", "", text) or "0")
            if jam < 1 or jam > 168:
                raise ValueError
        except ValueError:
            await safe_reply(
            update,
                "❌ Masukkan angka 1-168 (jam).\n"
                "Contoh: `3` = setiap 3 jam",
                reply_markup=kb_auto(),
            )
            return

        s = sched.get_state()
        sched.set_enabled(s.get("enabled", False), interval_hours=jam)
        await safe_reply(
            update,
            f"✅ Interval diset: *{jam} jam*\n\n" + auto_status_text(),
            reply_markup=kb_auto(),
        )
        return

    # ── Mode: menunggu input setting env ──
    if state.get("awaiting_env"):
        key = state["awaiting_env"]
        state["awaiting_env"] = None
        meta = env.FIELDS.get(key, {})

        if text.lower() in ("/batal", "/cancel"):
            await safe_reply(
            update,
                "❌ Dibatalkan.",
                reply_markup=kb_main(state["is_running"]),
            )
            return

        ok, msg = env.set_value(key, text)
        if not ok:
            await safe_reply(
            update,
                f"❌ {msg}",
                reply_markup=kb_main(state["is_running"]),
            )
            return

        # Validasi credential (kecuali field biasa)
        val_txt = ""
        if key not in ("LLM_BASE_URL", "LLM_MODEL"):
            valid, pesan = env.validate(key)
            val_txt = f"\n\n*Validasi:* {md(pesan)}"
            if key in ("OPENROUTER_API_KEY", "PIXABAY_API_KEY",
                       "FACEBOOK_PAGE_ACCESS_TOKEN", "FACEBOOK_USER_ACCESS_TOKEN",
                       "FACEBOOK_PAGE_ID", "TELEGRAM_BOT_TOKEN"):
                env.set_value(key, env.get(key, ""))  # pastikan tetap tersimpan

        await safe_reply(
            update,
            f"✅ *{meta.get('label', key)}*\n{msg}{val_txt}\n\n"
            "_Cek semua setting:_ ⚙️ Settings",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Lihat Settings", callback_data="settings")],
                [InlineKeyboardButton("◀️ Menu Utama", callback_data="back_main")],
            ]),
        )
        return

    # ── Mode: menunggu topik custom ──
    if state.get("awaiting_topic"):
        state["awaiting_topic"] = False
        if text.lower() in ("/topik", "/batal", "/cancel"):
            state["topik"] = None
            await safe_reply(
            update,
                "✅ Topik direset (otomatis).",
                reply_markup=kb_main(state["is_running"]),
            )
            return

        state["topik"] = text
        await safe_reply(
            update,
            f"✅ Topik diset:\n_{md(text)}_",
            reply_markup=kb_main(state["is_running"]),
        )
        return

    match = YT_REGEX.search(text)
    if not match:
        # Telegram: beri hint supaya user tidak bingung
        await safe_reply(
            update,
            "💡 Kirim *link YouTube* untuk download musik background,\n"
            "atau pakai tombol *📝 Topik Custom*.\n\n"
            "_Ketik /help untuk daftar perintah._",
        )
        return

    url = match.group(0)
    if not url.startswith("http"):
        url = "https://" + url

    await safe_reply(
            update,
        f"🎵 *Mendownload audio...*\n{code(url)}",
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
            await safe_reply(
            update,
                f"✅ *Musik berhasil didownload!*\n{code(nama)}\n\n"
                f"Total musik: {len(mp3s)} file",
            )
        else:
            err = result.stderr[:300] if result.stderr else "Unknown error"
            await safe_reply(
            update,
            f"❌ *Gagal download:*\n{code(err)}",
        )
    except Exception as e:
        await safe_reply(
            update,
            f"❌ Error: {code(str(e)[:300])}",
        )


async def _scheduler_notify(context, chat_id, ok, payload):
    """Kirim notifikasi hasil auto generate."""
    try:
        if ok:
            judul = payload.get("script", {}).get("judul", "")
            video_path = payload.get("video_path", "")
            up = payload.get("upload", {})
            msg = f"🤖 *Auto generate selesai!*\n\n📹 {code(os.path.basename(video_path))}\n"
            if up.get("youtube"):
                msg += f"\n🎬 [YouTube]({up['youtube']})"
            if up.get("facebook"):
                msg += f"\n📘 [Facebook]({up['facebook']})"
            errors = up.get("errors", {})
            if errors:
                msg += "\n\n⚠️ " + " | ".join(f"{k}: {md(str(v)[:80])}" for k, v in errors.items())
            await safe_send(
            context.bot,chat_id=chat_id, text=msg)
        else:
            await safe_send(
                context.bot,
                chat_id=chat_id,
                text=f"❌ *Auto generate gagal:*\n{code(str(payload)[:300])}",
            )
    except Exception as e:
        print(f"[Bot] Gagal notif scheduler: {e}")


# Scheduler global (diisi di main())
scheduler = sched.Scheduler()


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("Isi TELEGRAM_BOT_TOKEN di .env!")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("topik", topik_cmd))
    app.add_handler(CommandHandler("upload", upload_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("auto", auto_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, musik_handler))

    # ── Scheduler 24/7 ──
    global scheduler

    async def on_done(result):
        if CHAT_ID:
            await _scheduler_notify(app, CHAT_ID, True, result)

    async def on_error(err):
        if CHAT_ID:
            await _scheduler_notify(app, CHAT_ID, False, err)

    scheduler = sched.Scheduler(on_done=on_done, on_error=on_error)
    scheduler.start()
    print(f"[Bot] Scheduler aktif: {sched.get_state().get('enabled', False)}")

    print("[Bot] Bot Telegram berjalan... Buka Telegram dan ketik /start")
    print("[Bot] Kirim link YouTube ke bot untuk download musik background.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
