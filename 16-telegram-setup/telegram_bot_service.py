#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram-бот «Star Building — Регламенты и Стандарты»
Поддержка 2 веток:
1. Заявки и черновики регламентов (Кодификатор)
2. Вопросы и консультации (Консультант с автогенерацией документов)
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

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("STAR_BUILDING_CODIFIER_BOT_TOKEN")

# Инициализация модели Gemini
api_key = None
with open('/home/roman/.hermes/.env') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY=') or line.startswith('GOOGLE_API_KEY='):
            api_key = line.split('=', 1)[1].strip()
            break

ai_client = genai.Client(api_key=api_key)

# Инициализация распознавания речи
stt_model = None
def get_stt():
    global stt_model
    if stt_model is None:
        logger.info("Загрузка модели распознавания речи...")
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
    msg = (
        "👋 Здравствуйте! Я корпоративный ассистент группы компаний **Star Building**.\n\n"
        "🏛️ **Я работаю в двух направлениях:**\n"
        "1️⃣ **Заявки и черновики регламентов:** отправьте мне текст, голос или файл `.docx` — я сформирую стандартный регламент по 5 разделам или помогу составить документ с нуля.\n"
        "2️⃣ **Вопросы и консультации:** задайте любой рабочий вопрос — я выдам точный порядок действий по регламентам `РЕГ-001`..`010` и подготовлю предзаполненную служебную записку или акт.\n\n"
        "Чем могу помочь прямо сейчас?"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def process_user_request(user_text: str, is_draft_topic: bool, author_name: str) -> str:
    loop = asyncio.get_event_loop()
    
    if is_draft_topic:
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"=== БАЗА ЗНАНИЙ КОМПАНИИ (КАРТОЧКИ РЕГЛАМЕНТОВ РЕГ-001..010) ===\n{KB_CARDS}\n\n"
            f"=== ТЕКУЩИЙ ЗАПРОС: ВЕТКА «ЗАЯВКИ И ЧЕРНОВИКИ РЕГЛАМЕНТОВ» ===\n"
            f"Автор обращения: {author_name}\n"
            f"Текст/набросок от сотрудника:\n{user_text}\n\n"
            f"Инструкция:\n"
            f"1. Если прислан черновик процесса — собери нормативный проект регламента строго по 5 обязательным разделам (Код: РЕГ-ХХХ-ЧЕРНОВИК). При нехватке данных поставь [ТРЕБУЕТ УТОЧНЕНИЯ: контекст, вариант].\n"
            f"2. Если прислана заявка на разработку документа с нуля — поблагодари за инициативу и задай 3 наводящих вопроса автору для формулирования регламента.\n"
            f"Отвечай строго на русском языке, вежливо и структурированно."
        )
    else:
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"=== БАЗА ЗНАНИЙ КОМПАНИИ (КАРТОЧКИ РЕГЛАМЕНТОВ РЕГ-001..010) ===\n{KB_CARDS}\n\n"
            f"=== ТЕКУЩИЙ ЗАПРОС: ВЕТКА «ВОПРОСЫ И КОНСУЛЬТАЦИИ» ===\n"
            f"Сотрудник: {author_name}\n"
            f"Вопрос/инцидент:\n{user_text}\n\n"
            f"Инструкция:\n"
            f"1. Дай пошаговый порядок действий (что делать сейчас, что запрещено).\n"
            f"2. Дай нормативное обоснование со ссылками на пункты регламентов РЕГ-001..010.\n"
            f"3. Если ситуация требует оформления документа — выдай полностью заполненный текст служебной записки, акта дефектовки или заявления с подстановкой данных.\n"
            f"Отвечай строго на русском языке, четко, понятно и без лишних слов."
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

    # Определение автора
    user = update.effective_user
    author_name = user.full_name if user else "Сотрудник"
    
    # Определение ветки (темы)
    thread_id = getattr(msg, "message_thread_id", None)
    is_draft_topic = False
    
    # Если в группе есть ветки, можно ориентироваться на thread_id или ключевые слова
    text_content = ""
    
    # Обработка голосовых сообщений
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

    # Обработка документов
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
            
            # Если есть подпись к файлу
            if msg.caption:
                text_content = f"{msg.caption}\n\nСодержимое файла:\n{text_content}"
        else:
            text_content = msg.caption or ""

    # Обработка обычного текста
    elif msg.text:
        text_content = msg.text
        if text_content.startswith('/start'):
            await handle_start(update, context)
            return

    if not text_content:
        return

    # Определение намерения (ветка 1 или ветка 2)
    lower_text = text_content.lower()
    if any(w in lower_text for w in ["черновик", "регламент", "создать регламент", "инструкция", "разработать", "должностн"]):
        is_draft_topic = True
    
    await msg.reply_chat_action("typing")
    try:
        reply_text = await process_user_request(text_content, is_draft_topic, author_name)
        
        # Telegram ограничение на 4096 символов
        if len(reply_text) <= 4000:
            await msg.reply_text(reply_text, parse_mode="Markdown")
        else:
            for chunk in [reply_text[i:i+4000] for i in range(0, len(reply_text), 4000)]:
                await msg.reply_text(chunk, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        await msg.reply_text(f"⚠ Произошла ошибка при обработке запроса: {e}")

def main():
    logger.info("Запуск Telegram-бота Star Building...")
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
