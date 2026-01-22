import subprocess
import time
import os
import signal
import re
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# ================= CONFIG =================
BOT_TOKEN = "7714074717:AAGe_hpofp64dPaWmILdbXiQ_523JzIkzx4"
UPLOAD_DIR = "uploads"
WORDLIST = "rockyou.txt"
# =========================================

os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- regex ---
ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
key_regex = re.compile(r'KEY FOUND!\s*\[\s*(.*?)\s*\]', re.IGNORECASE)
handshake_regex = re.compile(r'handshake', re.IGNORECASE)


def clean(text: str) -> str:
    return ansi_escape.sub('', text).strip()


# ---------- HANDSHAKE CHECK (UNCHANGED) ----------
def has_handshake(pcap_path: str) -> bool:
    try:
        proc = subprocess.run(
            ["aircrack-ng", pcap_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15
        )
        return bool(handshake_regex.search(proc.stdout))
    except Exception:
        return False


# ---------- BACKGROUND CRACK RUNNER (NEW) ----------
async def crack_runner(update, context, cmd, msg):
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True
    )

    context.application.bot_data["process"] = process
    context.application.bot_data["task"] = asyncio.current_task()

    output = ""
    last_edit = time.time()

    try:
        while True:
            line = await asyncio.to_thread(process.stdout.readline)
            if not line:
                break

            line = clean(line)
            if not line:
                continue

            match = key_regex.search(line)
            if match:
                key = match.group(1)
                await update.message.reply_text(
                    f"🔓 **KEY FOUND!**\n\nPassword: `{key}`",
                    parse_mode="Markdown"
                )
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                return

            output += line + "\n"

            if time.time() - last_edit > 1.5:
                await msg.edit_text(
                    "📡 Running aircrack-ng...\n\n" + output[-3500:]
                )
                last_edit = time.time()

        await msg.edit_text("❌ Finished. Key not found.")

    finally:
        context.application.bot_data.clear()


# ---------- TEXT HANDLER (NEW CANCEL) ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text.strip().lower()
    process = context.application.bot_data.get("process")
    task = context.application.bot_data.get("task")

    if text == "cancel":
        if process:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception:
                pass

        if task:
            task.cancel()

        context.application.bot_data.clear()
        await update.message.reply_text("🛑 Process cancelled.")
        return

    await update.message.reply_text(
        "📎 Send a `.pcap` file.\n"
        "✋ Send `cancel` to stop cracking."
    )


# ---------- FILE HANDLER (MINIMALLY MODIFIED) ----------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.document:
        return

    if context.application.bot_data.get("task"):
        await update.message.reply_text("⚠️ A process is already running. Send `cancel` first.")
        return

    doc = update.message.document
    filename = doc.file_name

    if not filename.endswith(".pcap"):
        await update.message.reply_text("❌ Only `.pcap` files allowed.")
        return

    file_path = os.path.join(UPLOAD_DIR, filename)
    tg_file = await doc.get_file()
    await tg_file.download_to_drive(file_path)

    await update.message.reply_text("🔍 Checking for WPA handshake...")

    if not has_handshake(file_path):
        await update.message.reply_text(
            "❌ No WPA handshake found.\n"
            "Please capture a valid handshake and try again."
        )
        return

    await update.message.reply_text("✅ Handshake detected. Starting aircrack-ng...")

    cmd = [
        "aircrack-ng",
        file_path,
        "-w",
        WORDLIST
    ]

    msg = await update.message.reply_text("🚀 Cracking started...")

    task = asyncio.create_task(
        crack_runner(update, context, cmd, msg)
    )

    context.application.bot_data["task"] = task


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot running (FINAL, cancel fixed)...")
    app.run_polling()


if __name__ == "__main__":
    main()
