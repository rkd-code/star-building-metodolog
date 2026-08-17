#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бот 2: «Корпоративный консультант Star Building»
Назначение: Решение рабочих вопросов по регламентам РЕГ-001..010.
Правила:
1. Шаблоны документов только из утвержденной базы знаний (запрет выдумывать формы).
2. Сначала спрашивать сотрудника, нужен ли шаблон документа.
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
logger = logging.getLogger("bot_consultant")

TOKEN = "8928901139:AAFE9qOWDKYQJb7OXtfEeLqfCaSSD0yvAB0"

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
    msg = (
        "💼 **Корпоративный консультант Star Building**\n\n"
        "Я помогу решить любой рабочий вопрос на основе действующих регламентов (`РЕГ-001`..`РЕГ-010`).\n\n"
        "📌 **Как я работаю:**\n"
        "1. Даю пошаговый порядок действий (*что делать / что запрещено*).\n"
        "2. Указываю точные пункты регламентов компании.\n"
        "3. Если ситуация требует оформления документа — предлагаю подготовить заполненный шаблон.\n\n"
        "Задайте ваш вопрос текстом или голосовым сообщением!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def process_consultant_request(user_text: str, author_name: str) -> str:
    loop = asyncio.get_event_loop()
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"=== РЕЕСТР И МАТРИЦА ФОРМ ДОКУМЕНТОВ ===\n{REESTR_TEXT}\n\n"
        f"=== БАЗА ЗНАНИЙ (КАРТОЧКИ РЕГЛАМЕНТОВ РЕГ-001..010) ===\n{KB_CARDS}\n\n"
        f"=== ЗАДАЧА: КОНСУЛЬТАЦИЯ СОТРУДНИКА ПО ДЕЙСТВУЮЩИМ РЕГЛАМЕНТАМ ===\n"
        f"Сотрудник: {author_name}\n"
        f"Обращение сотрудника:\n{user_text}\n\n"
        f"ЖЕСТКИЕ ПРАВИЛА ВЫДАЧИ:\n"
        f"1. Дай пошаговый порядок действий (что разрешено делать сейчас, что категорически запрещено).\n"
        f"2. Укажи нормативное обоснование со ссылками на пункты регламентов РЕГ-001..010.\n"
        f"3. ПРАВИЛО ПО ШАБЛОНАМ ДОКУМЕНТОВ:\n"
        f"   - Использовать ТОЛЬКО утвержденные формы из реестра (ФОРМА-ДОГ-001, ФОРМА-КАДР-001..003, ФОРМА-МОТ-001, ФОРМА-ГСМ-001..002, ФОРМА-КЛИЕНТ-001..002). Запрещено придумывать новые формы!\n"
        f"   - Если сотрудник в текущем сообщении НЕ просил явно сформировать документ, а просто задал вопрос: НЕ выдавай текст документа сразу! Вместо этого напиши в конце ответа: «Для фиксации этой ситуации по регламенту РЕГ-XXX требуется оформить [Название формы]. Подготовить для вас готовый заполненный шаблон?»\n"
        f"   - Если сотрудник прямо пишет «да», «подготовь шаблон», «сделай служебку», «нужен шаблон» или подтверждает подготовку — сформируй полностью заполненный текст документа с подстановкой всех известных данных.\n"
        f"Отвечай строго на русском языке, предельно кратко, понятно и по делу."
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
        reply_text = await process_consultant_request(text_content, author_name)
        if len(reply_text) <= 4000:
            await msg.reply_text(reply_text, parse_mode="Markdown")
        else:
            for chunk in [reply_text[i:i+4000] for i in range(0, len(reply_text), 4000)]:
                await msg.reply_text(chunk, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка консультации: {e}")
        await msg.reply_text(f"⚠ Ошибка: {e}")

def main():
    logger.info("Запуск бота-консультанта Star Building с обновленными правилами...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
