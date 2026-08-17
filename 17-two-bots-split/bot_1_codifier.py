#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бот 1: «Кодификатор регламентов Star Building»
Назначение: ТОЛЬКО прием черновиков и разработка новых регламентов.
"""

import os
import sys
import asyncio
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
import faster_whisper
import docx
import pypdf

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("bot_codifier")

TOKEN = "8314030408:AAFywrGRSZNpCLqC_Yv06REa1yCn0Eh43fc"

api_key = None
with open('/home/roman/.hermes/.env') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY=') or line.startswith('GOOGLE_API_KEY='):
            api_key = line.split('=', 1)[1].strip()
            break

ai_client = genai.Client(api_key=api_key)

stt_model = None
def get_stt():
    global stt_model
    if stt_model is None:
        logger.info("Загрузка модели распознавания речи...")
        stt_model = faster_whisper.WhisperModel("base", device="cpu", compute_type="int8")
    return stt_model

def load_kb_context():
    kb_path = Path("/home/roman/knowledge_base")
    cards = []
    cards_dir = kb_path / "01_КАРТОЧКИ"
    if cards_dir.exists():
        for f in sorted(cards_dir.glob("*.md")):
            cards.append(f.read_text(encoding="utf-8"))
    
    instructions = ""
    inst_file = Path("/home/roman/04-environment/custom_instructions.md")
    if inst_file.exists():
        instructions = inst_file.read_text(encoding="utf-8")
        
    return instructions, "\n\n---\n\n".join(cards)

SYSTEM_PROMPT, KB_CARDS = load_kb_context()

async def transcribe_audio(file_path: str) -> str:
    loop = asyncio.get_event_loop()
    def _run():
        model = get_stt()
        segments, _ = model.transcribe(file_path, language="ru")
        return " ".join([s.text for s in segments]).strip()
    return await loop.run_in_executor(None, _run)

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📝 **Бот-Кодификатор регламентов Star Building**\n\n"
        "Я предназначен исключительно для **создания и кодификации регламентов** компании.\n\n"
        "📌 **Как со мной работать:**\n"
        "1. **Отправьте черновик процесса** (текстом, голосовым сообщением или файлом `.docx`) — я оформлю его в стандартный регламент по 5 разделам.\n"
        "2. **Оставьте заявку на новый документ** (например: *«Нужна инструкция по приему инструмента»*) — я задам 3 вопроса и подготовлю проект.\n\n"
        "Отправьте ваш черновик или тему документа!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def process_draft_request(user_text: str, author_name: str) -> str:
    loop = asyncio.get_event_loop()
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"=== БАЗА ЗНАНИЙ КОМПАНИИ (КАРТОЧКИ РЕГЛАМЕНТОВ РЕГ-001..010) ===\n{KB_CARDS}\n\n"
        f"=== ЗАДАЧА: КОДИФИКАЦИЯ И СОЗДАНИЕ НОВОГО РЕГЛАМЕНТА ===\n"
        f"Автор обращения: {author_name}\n"
        f"Входящий текст от сотрудника:\n{user_text}\n\n"
        f"Инструкция:\n"
        f"1. Если прислан черновик — упакуй его строго в 5 обязательных разделов (РЕГ-XXX-ЧЕРНОВИК). "
        f"Роли бери строго по РЕГ-002. Недостающие параметры отметь как [ТРЕБУЕТ УТОЧНЕНИЯ: контекст, вариант].\n"
        f"2. Если прислан краткий запрос на создание документа — поблагодари за инициативу и задай 3 наводящих вопроса автору.\n"
        f"Отвечай строго на русском языке, четко и профессионально."
    )

    def _call_ai():
        resp = ai_client.models.generate_content(
            model="gemini-3.7-flash",
            contents=prompt
        )
        return resp.text

    return await loop.run_in_executor(None, _call_ai)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    user = update.effective_user
    author_name = user.full_name if user else "Сотрудник"
    text_content = ""
    
    if msg.voice or msg.audio:
        await msg.reply_chat_action("record_voice")
        audio_obj = msg.voice or msg.audio
        file = await audio_obj.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)
        try:
            text_content = await transcribe_audio(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        await msg.reply_text(f"🎤 *Распознано:* «_{text_content}_»", parse_mode="Markdown")

    elif msg.document:
        doc = msg.document
        fname = doc.file_name or "document"
        if fname.endswith(('.docx', '.pdf', '.txt', '.md')):
            file = await doc.get_file()
            suffix = Path(fname).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp_path = tmp.name
            await file.download_to_drive(tmp_path)
            try:
                if suffix == '.docx':
                    d = docx.Document(tmp_path)
                    text_content = "\n".join([p.text.strip() for p in d.paragraphs if p.text.strip()])
                elif suffix == '.pdf':
                    reader = pypdf.PdfReader(tmp_path)
                    text_content = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
                else:
                    with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text_content = f.read()
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            
            if msg.caption:
                text_content = f"{msg.caption}\n\nСодержимое файла:\n{text_content}"
        else:
            text_content = msg.caption or ""

    elif msg.text:
        text_content = msg.text
        if text_content.startswith('/start'):
            await handle_start(update, context)
            return

    if not text_content:
        return

    await msg.reply_chat_action("typing")
    try:
        reply_text = await process_draft_request(text_content, author_name)
        chunks = [reply_text[i:i+4000] for i in range(0, len(reply_text), 4000)]
        for chunk in chunks:
            try:
                await msg.reply_text(chunk, parse_mode="Markdown")
            except Exception as parse_err:
                logger.warning(f"Ошибка Markdown, отправка без разметки: {parse_err}")
                await msg.reply_text(chunk)
    except Exception as e:
        logger.error(f"Ошибка кодификации: {e}")
        await msg.reply_text(f"⚠ Ошибка обработки черновика: {e}")

def main():
    logger.info("Запуск бота-кодификатора Star Building...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
