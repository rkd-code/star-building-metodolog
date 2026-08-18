#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бот 2: «Корпоративный консультант Star Building» (Надежная версия v2.0)
Улучшения:
1. Память диалога (помнит исходный вопрос, когда пользователь отвечает «Да, сделай шаблон»).
2. Таймауты сети Telegram 60 сек.
3. Поддержка голосовых, фото и документов.
4. Выдача форм строго из реестра.
"""

import os
import sys
import io
import asyncio
import logging
import tempfile
from pathlib import Path
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest
from google import genai
import faster_whisper
import docx
import pypdf

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("bot_consultant")

TOKEN = "8928901139:AAFE9qOWDKYQJb7OXtfEeLqfCaSSD0yvAB0"

api_key = None
with open('/home/roman/.hermes/.env') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY=') or line.startswith('GOOGLE_API_KEY='):
            api_key = line.split('=', 1)[1].strip()
            break

ai_client = genai.Client(api_key=api_key)

# Память диалогов
user_histories = defaultdict(list)

# Распознавание речи
stt_model = None
def get_stt():
    global stt_model
    if stt_model is None:
        logger.info("Загрузка модели распознавания речи Whisper...")
        stt_model = faster_whisper.WhisperModel("base", device="cpu", compute_type="int8")
    return stt_model

def load_kb_context():
    kb_path = Path("/home/roman/knowledge_base")
    cards = []
    cards_dir = kb_path / "01_КАРТОЧКИ"
    if cards_dir.exists():
        for f in sorted(cards_dir.glob("*.md")):
            cards.append(f.read_text(encoding="utf-8"))
    
    reestr_text = ""
    reestr_file = kb_path / "00_РЕЕСТР/reestr-reglamentov.md"
    if reestr_file.exists():
        reestr_text = reestr_file.read_text(encoding="utf-8")
        
    instructions = ""
    inst_file = Path("/home/roman/04-environment/custom_instructions.md")
    if inst_file.exists():
        instructions = inst_file.read_text(encoding="utf-8")
        
    return instructions, "\n\n---\n\n".join(cards), reestr_text

SYSTEM_PROMPT, KB_CARDS, REESTR_TEXT = load_kb_context()

async def transcribe_audio(file_path: str) -> str:
    loop = asyncio.get_event_loop()
    def _run():
        model = get_stt()
        segments, _ = model.transcribe(file_path, language="ru")
        return " ".join([s.text for s in segments]).strip()
    return await loop.run_in_executor(None, _run)

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else 0
    user_histories[user_id].clear()
    msg = (
        "💼 **Корпоративный консультант Star Building**\n\n"
        "Я помогу решить любой рабочий вопрос на основе действующих регламентов компании (`РЕГ-001`..`РЕГ-010`).\n\n"
        "📌 **Как я работаю:**\n"
        "1. Даю пошаговый порядок действий (*что разрешено делать сейчас / что запрещено*).\n"
        "2. Указываю точные пункты регламентов Star Building.\n"
        "3. Если ситуация требует оформления документа — предлагаю подготовить заполненный шаблон.\n\n"
        "Задайте ваш вопрос текстом, голосом или пришлите фото ситуации!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def process_consultant_request(user_text: str, author_name: str, user_id: int, image_bytes: bytes = None) -> str:
    loop = asyncio.get_event_loop()
    
    history = user_histories[user_id]
    history_str = ""
    if history:
        history_str = "\n=== ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА С СОТРУДНИКОМ ===\n" + "\n".join(history[-8:]) + "\n"

    base_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"=== РЕЕСТР И МАТРИЦА ФОРМ ДОКУМЕНТОВ ===\n{REESTR_TEXT}\n\n"
        f"=== БАЗА ЗНАНИЙ (КАРТОЧКИ РЕГЛАМЕНТОВ РЕГ-001..010) ===\n{KB_CARDS}\n\n"
        f"{history_str}\n"
        f"=== ТЕКУЩЕЕ ОБРАЩЕНИЕ СОТРУДНИКА ===\n"
        f"Сотрудник: {author_name}\n"
        f"Сообщение / вопрос:\n{user_text}\n\n"
        f"ЖЕСТКИЕ ПРАВИЛА ВЫДАЧИ:\n"
        f"1. Дай пошаговый порядок действий (что разрешено делать сейчас, что категорически запрещено).\n"
        f"2. Укажи нормативное обоснование со ссылками на пункты регламентов РЕГ-001..010.\n"
        f"3. ПРАВИЛО ПО ШАБЛОНАМ ДОКУМЕНТОВ:\n"
        f"   - Использовать ТОЛЬКО утвержденные формы из реестра (ФОРМА-ДОГ-001, ФОРМА-КАДР-001..003, ФОРМА-МОТ-001, ФОРМА-ГСМ-001..002, ФОРМА-КЛИЕНТ-001..002). Запрещено выдумывать новые формы!\n"
        f"   - Если сотрудник в текущем сообщении НЕ просил явно сформировать документ, а просто задал вопрос: НЕ выдавай текст документа сразу! Вместо этого спроси в конце: «Для фиксации этой ситуации по регламенту РЕГ-XXX требуется оформить [Название формы]. Подготовить для вас готовый заполненный шаблон?»\n"
        f"   - Если сотрудник пишет «да», «подготовь шаблон», «сделай служебку», «нужен шаблон» или подтверждает подготовку — сгенерируй полностью заполненный текст документа, учитывая тему из истории диалога.\n"
        f"Отвечай строго на русском языке, предельно кратко, понятно и без лишних слов."
    )

    def _call_ai():
        if image_bytes:
            from google.genai import types
            contents = [
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                base_prompt
            ]
            resp = ai_client.models.generate_content(
                model="gemini-3.7-flash",
                contents=contents
            )
        else:
            resp = ai_client.models.generate_content(
                model="gemini-3.7-flash",
                contents=base_prompt
            )
        return resp.text

    answer = await loop.run_in_executor(None, _call_ai)
    
    history.append(f"Сотрудник ({author_name}): {user_text}")
    history.append(f"Консультант: {answer}")
    if len(history) > 12:
        user_histories[user_id] = history[-10:]

    return answer

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    user = update.effective_user
    user_id = user.id if user else 0
    author_name = user.full_name if user else "Сотрудник"
    text_content = ""
    image_bytes = None
    
    try:
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

        elif msg.photo:
            await msg.reply_chat_action("typing")
            photo = msg.photo[-1]
            file = await photo.get_file()
            bio = io.BytesIO()
            await file.download_to_memory(bio)
            image_bytes = bio.getvalue()
            text_content = msg.caption or "Проанализируй фото с объекта и ответь по регламентам компании."

        elif msg.document:
            await msg.reply_chat_action("typing")
            doc = msg.document
            fname = doc.file_name or "document"
            suffix = Path(fname).suffix.lower()
            file = await doc.get_file()
            
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
                elif suffix in ['.png', '.jpg', '.jpeg']:
                    with open(tmp_path, 'rb') as f:
                        image_bytes = f.read()
                    text_content = msg.caption or "Проанализируй документ на изображении."
                else:
                    with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text_content = f.read()
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            
            if msg.caption and not image_bytes:
                text_content = f"{msg.caption}\n\nСодержимое документа:\n{text_content}"

        elif msg.text:
            text_content = msg.text
            if text_content.startswith('/start') or text_content.startswith('/clear'):
                await handle_start(update, context)
                return

        if not text_content and not image_bytes:
            await msg.reply_text("Пожалуйста, отправьте вопрос текстом, голосом или прикрепите документ.")
            return

        await msg.reply_chat_action("typing")
        reply_text = await process_consultant_request(text_content, author_name, user_id, image_bytes)
        
        chunks = [reply_text[i:i+4000] for i in range(0, len(reply_text), 4000)]
        for chunk in chunks:
            try:
                await msg.reply_text(chunk, parse_mode="Markdown")
            except Exception:
                await msg.reply_text(chunk)

    except Exception as e:
        logger.error(f"Глобальная ошибка консультанта: {e}", exc_info=True)
        await msg.reply_text(f"⚠ Ошибка: {e}")

def main():
    logger.info("Запуск бота-консультанта Star Building (v2.0 с памятью диалога)...")
    req = HTTPXRequest(
        connection_pool_size=16,
        read_timeout=60.0,
        write_timeout=60.0,
        connect_timeout=60.0,
        pool_timeout=60.0
    )
    app = Application.builder().token(TOKEN).request(req).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("clear", handle_start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
