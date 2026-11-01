"""
Safe Telegram HTML/JS formatter
- Accepts .html, .htm, .js, and .txt files.
- Formats HTML and JavaScript for readability.
- Extracts inline JavaScript into separate .js files.
- Decodes HTML entities only.
- Does NOT execute uploaded code, crack passwords, bypass licensing,
  or decrypt proprietary/encrypted code.
"""

import os
import re
import html
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from bs4 import BeautifulSoup
import jsbeautifier

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_BYTES = 15 * 1024 * 1024  # 15 MB

if not BOT_TOKEN:
    raise RuntimeError("Set the BOT_TOKEN environment variable first.")

HELP = (
    "📂 HTML/JS Formatter Bot\n\n"
    "একটি .html / .htm / .js / .txt ফাইল পাঠাও।\n"
    "আমি HTML/JS readable করে দেব এবং inline JavaScript আলাদা ফাইলে দেব।\n\n"
    "নোট: এটি encrypted/proprietary code crack করে না, password বা license "
    "bypass করে না, এবং কোনো uploaded code execute করে না।"
)

def format_html(source: str):
    # Decode HTML entities, then parse/pretty-print the document.
    source = html.unescape(source)
    soup = BeautifulSoup(source, "html.parser")
    inline_scripts = []

    for index, tag in enumerate(soup.find_all("script"), start=1):
        if tag.get("src"):
            continue
        js_source = tag.string or tag.get_text() or ""
        if js_source.strip():
            formatted_js = jsbeautifier.beautify(
                js_source,
                jsbeautifier.default_options()
            )
            inline_scripts.append((index, formatted_js))
            tag.string = f"\n/* Inline script {index} formatted separately. */\n"

    return soup.prettify(formatter="html"), inline_scripts

def format_js(source: str):
    return jsbeautifier.beautify(source, jsbeautifier.default_options())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    filename = Path(doc.file_name or "upload.txt").name
    suffix = Path(filename).suffix.lower()

    if suffix not in {".html", ".htm", ".js", ".txt"}:
        await update.message.reply_text(
            "এই ফাইল টাইপ সমর্থিত নয়। .html, .htm, .js অথবা .txt পাঠাও।"
        )
        return

    if doc.file_size and doc.file_size > MAX_BYTES:
        await update.message.reply_text("ফাইলটি ১৫ MB-এর বেশি। ছোট ফাইল পাঠাও।")
        return

    telegram_file = await context.bot.get_file(doc.file_id)

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / filename
        await telegram_file.download_to_drive(custom_path=str(input_path))
        raw = input_path.read_text(encoding="utf-8", errors="replace")

        if suffix in {".html", ".htm"}:
            formatted, scripts = format_html(raw)
            output_path = Path(temp_dir) / f"{input_path.stem}_formatted.html"
            output_path.write_text(formatted, encoding="utf-8")
            await update.message.reply_document(
                document=str(output_path),
                caption="✅ Readable HTML তৈরি হয়েছে।"
            )

            for number, js in scripts:
                js_path = Path(temp_dir) / f"{input_path.stem}_script_{number}.js"
                js_path.write_text(js, encoding="utf-8")
                await update.message.reply_document(
                    document=str(js_path),
                    caption=f"Inline JavaScript #{number} (formatted)"
                )

        else:
            formatted = format_js(raw) if suffix == ".js" else html.unescape(raw)
            output_path = Path(temp_dir) / f"{input_path.stem}_formatted{suffix}"
            output_path.write_text(formatted, encoding="utf-8")
            await update.message.reply_document(
                document=str(output_path),
                caption="✅ Readable text/JavaScript তৈরি হয়েছে।"
            )

async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ফাইল হিসেবে HTML/JS/TXT পাঠাও। /start লিখলে সাহায্য পাবে।")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_other))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
