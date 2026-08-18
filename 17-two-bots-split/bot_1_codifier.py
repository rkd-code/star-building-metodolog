#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бот 1: «Кодификатор регламентов Star Building» (Надежная версия v2.0)
Улучшения:
1. Хранение истории диалога (контекст уточняющих вопросов).
2. Поддержка изображений и скриншотов через мультимодальный анализ.
3. Увеличенные таймауты сети Telegram (защита от разрывов связи).
4. Подробное логирование и автосохранение черновиков в папку 01_В_РАБОТЕ.
"""

import os
import sys
import io
import asyncio
import logging
import tempfile
from pathlib import Path
from collections import defaultdict
from datetime import datetime

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

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("bot_codifier")

TOKEN = "8314030408:AAFywrGRSZNpCLqC_Yv06REa1yCn0Eh43fc"

# Инициализация Gemini
api_key = None
with open('/home/roman/.hermes/.env') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY=') or line.startswith('GOOGLE_API_KEY='):
            api_key = line.split('=', 1)[1].strip()
            break

ai_client = genai.Client(api_key=api_key)

# Память диалогов (до 10 последних реплик на каждого пользователя)
user_histories = defaultdict(list)

# Распознавание речи
stt_model = None
def get_stt():
    global stt_model
    if stt_model is None:
        logger.info("Загрузка модели распознавания речи Whisper...")
        stt_model = faster_whisper.WhisperModel("base", device="cpu", compute_type="int8")
    return stt_model

# Загрузка базы знаний
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
    user_id = update.effective_user.id if update.effective_user else 0
    user_histories[user_id].clear()
    msg = (
        "📝 **Бот-Кодификатор регламентов Star Building**\n\n"
        "Я предназначен исключительно для **создания, доработки и кодификации регламентов** компании.\n\n"
        "📌 **Как со мной работать:**\n"
        "1. **Отправьте черновик процесса** (текстом, голосовым сообщением, файлом `.docx`/`.pdf` или фото схемы) — я упакую его в стандартный регламент по 5 разделам.\n"
        "2. **Оставьте заявку на новый документ** (например: *«Нужна инструкция по приему инструмента на объекте»*) — я задам 3 целевых вопроса и сформирую первичный проект.\n"
        "3. **Отвечайте на мои вопросы прямо в чате** — я помню контекст предыдущих сообщений и сам дополню документ!\n\n"
        "Отправьте ваш черновик, аудио или тему документа!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def process_draft_request(user_text: str, author_name: str, user_id: int, image_bytes: bytes = None) -> str:
    loop = asyncio.get_event_loop()
    
    # Формирование контекста диалога
    history = user_histories[user_id]
    history_str = ""
    if history:
        history_str = "\n=== ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА С АВТОРОМ ===\n" + "\n".join(history[-8:]) + "\n"

    base_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"=== БАЗА ЗНАНИЙ КОМПАНИИ (КАРТОЧКИ РЕГЛАМЕНТОВ РЕГ-001..010) ===\n{KB_CARDS}\n\n"
        f"{history_str}\n"
        f"=== ТЕКУЩЕЕ ОБРАЩЕНИЕ АВТОРА ===\n"
        f"Автор: {author_name}\n"
        f"Входящий текст/ответ:\n{user_text}\n\n"
        f"ЖЕСТКИЕ ТРЕБОВАНИЯ К ВЫДАЧЕ:\n"
        f"1. Если у тебя достаточно информации (или автор ответил на твои уточняющие вопросы) — собери ПОЛНЫЙ проект регламента по стандарту 5 разделов (Код: РЕГ-XXX-ЧЕРНОВИК). "
        f"Используй должности строго по РЕГ-002. Оставшиеся белые пятна отметь маркером: [ТРЕБУЕТ УТОЧНЕНИЯ: формулировка с типовым вариантом].\n"
        f"2. Если автор только что подал краткую заявку с нуля — поблагодари и задай ровно 3 целевых вопроса (Исполнители, Шаги/Контроль, Сроки/Формы).\n"
        f"3. Если автор ответил на твои вопросы — объедини его ответы с предыдущим черновиком и выдай обновленную версию регламента.\n"
        f"Отвечай строго на русском языке, предельно аккуратно, уважительно и профессионально."
    )

    def _call_ai():
        if image_bytes:
            # Мультимодальный вызов (текст + картинка)
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
    
    # Сохраняем реплики в историю пользователя
    history.append(f"Автор ({author_name}): {user_text}")
    history.append(f"Кодификатор: {answer}")
    if len(history) > 12:
        user_histories[user_id] = history[-10:]

    # Автосохранение черновика в папку 01_В_РАБОТЕ при наличии 5 разделов
    if "## 1." in answer and "## 2." in answer and "## 3." in answer:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"draft_{author_name.replace(' ', '_')}_{timestamp}.md"
            draft_path = Path("/home/roman/knowledge_base/01_В_РАБОТЕ") / filename
            draft_path.write_text(answer, encoding="utf-8")
            logger.info(f"Сохранен черновик в 01_В_РАБОТЕ: {filename}")
        except Exception as e:
            logger.error(f"Не удалось сохранить черновик на диск: {e}")

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
        # 1. Голосовое сообщение
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

        # 2. Фотография / Скриншот
        elif msg.photo:
            await msg.reply_chat_action("typing")
            photo = msg.photo[-1] # Самое высокое разрешение
            file = await photo.get_file()
            bio = io.BytesIO()
            await file.download_to_memory(bio)
            image_bytes = bio.getvalue()
            text_content = msg.caption or "Проанализируй изображение и извлеки структуру регламента/процесса."

        # 3. Документ
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

        # 4. Обычный текст
        elif msg.text:
            text_content = msg.text
            if text_content.startswith('/start') or text_content.startswith('/clear'):
                await handle_start(update, context)
                return

        if not text_content and not image_bytes:
            await msg.reply_text("Пожалуйста, отправьте текст, голосовое сообщение, файл документа или фото черновика.")
            return

        await msg.reply_chat_action("typing")
        reply_text = await process_draft_request(text_content, author_name, user_id, image_bytes)
        
        chunks = [reply_text[i:i+4000] for i in range(0, len(reply_text), 4000)]
        for chunk in chunks:
            try:
                await msg.reply_text(chunk, parse_mode="Markdown")
            except Exception:
                await msg.reply_text(chunk)

    except Exception as e:
        logger.error(f"Глобальная ошибка обработчика: {e}", exc_info=True)
        await msg.reply_text(f"⚠ Произошла ошибка при обработке: {e}")

def main():
    logger.info("Запуск бота-кодификатора Star Building (v2.0 с памятью диалога)...")
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
