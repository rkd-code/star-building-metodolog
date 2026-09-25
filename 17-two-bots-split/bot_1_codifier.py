#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бот 1: «Кодификатор регламентов Star Building» (Версия v2.1 с модулем Сверщика)
Функционал:
1. Автоматическая сверка нового черновика со ВСЕМИ действующими регламентами (РЕГ-001..010).
2. Выявление противоречий, пересечений сроков и ролей.
3. Формирование блока коллизий и вопросов автору/заказчику.
4. Упаковка регламента по 5 разделам в папку 01_В_РАБОТЕ.
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

# Гарантируем импорт модулей из текущего каталога
sys.path.insert(0, str(Path(__file__).resolve().parent))

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

from artifact_exporter import (
    ExportService,
    detect_export_intent,
    is_complete_regulation,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("bot_codifier")
# HTTPX включает адрес Telegram Bot API в INFO-журнал. Отключаем эти
# записи, чтобы учетные данные не попадали в журнал службы.
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = os.environ.get("STAR_BUILDING_CODIFIER_BOT_TOKEN")

api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not api_key and os.path.exists('/home/roman/.hermes/.env'):
    try:
        with open('/home/roman/.hermes/.env') as f:
            for line in f:
                if line.startswith('GEMINI_API_KEY=') or line.startswith('GOOGLE_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    break
    except Exception as e:
        logger.warning(f"Не удалось прочитать .hermes/.env: {e}")

ai_client = None
if api_key:
    try:
        ai_client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.warning(f"Не удалось инициализировать GenAI client: {e}")

user_histories = defaultdict(list)
export_service = ExportService()

stt_model = None
def get_stt():
    global stt_model
    if stt_model is None:
        logger.info("Загрузка модели распознавания речи Whisper...")
        stt_model = faster_whisper.WhisperModel("base", device="cpu", compute_type="int8")
    return stt_model

def load_kb_context():
    repo_root = Path(__file__).resolve().parent.parent
    kb_path = repo_root / "knowledge_base" if (repo_root / "knowledge_base").exists() else Path("/home/roman/knowledge_base")
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
    inst_file = repo_root / "04-environment/custom_instructions.md" if (repo_root / "04-environment/custom_instructions.md").exists() else Path("/home/roman/04-environment/custom_instructions.md")
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
        "📝 **Смотритель — Кодификатор регламентов Star Building**\n\n"
        "Я создаю новые регламенты и **автоматически проверяю их на противоречия** с уже действующей базой компании (`РЕГ-001`..`РЕГ-010`).\n\n"
        "📌 **Что я делаю при получении черновика:**\n"
        "1. **Сверяю с базой:** нахожу пересечения по срокам, ролям и документам.\n"
        "2. **Выделяю блок коллизий:** если есть нестыковки — прямо пишу, с каким регламентом конфликт и как его устранить.\n"
        "3. **Упаковываю регламент:** оформляю процесс строго по стандарту 5 разделов в папку `01_В_РАБОТЕ`.\n\n"
        "Отправьте черновик, аудиозапись или назовите тему документа!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def process_draft_request(user_text: str, author_name: str, user_id: int, image_bytes: bytes = None) -> str:
    loop = asyncio.get_event_loop()
    
    history = user_histories[user_id]
    history_str = ""
    if history:
        history_str = "\n=== ИСТОРИЯ ДИАЛОГА С АВТОРОМ ===\n" + "\n".join(history[-8:]) + "\n"

    base_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"=== РЕЕСТР ДЕЙСТВУЮЩИХ РЕГЛАМЕНТОВ ===\n{REESTR_TEXT}\n\n"
        f"=== БАЗА ЗНАНИЙ КОМПАНИИ (КАРТОЧКИ РЕГ-001..010) ===\n{KB_CARDS}\n\n"
        f"{history_str}\n"
        f"=== ВХОДЯЩИЙ ЧЕРНОВИК / ЗАЯВКА ОТ СОТРУДНИКА ===\n"
        f"Автор: {author_name}\n"
        f"Текст/аудио черновика:\n{user_text}\n\n"
        f"ОБЯЗАТЕЛЬНЫЙ АЛГОРИТМ КОДИФИКАЦИИ И СВЕРКИ:\n\n"
        f"ШАГ 1: АВТОМАТИЧЕСКАЯ СВЕРКА С БАЗОЙ ЗНАНИЙ (СВЕРЩИК)\n"
        f"- Сопоставь черновик с РЕГ-001 (Кодекс), РЕГ-002 (Оргструктура), РЕГ-006 (Договоры), РЕГ-007 (Кадры), РЕГ-009 (ГСМ), РЕГ-010 (Клиенты).\n"
        f"- Если обнаружены противоречия по срокам, дублирование функций или несоответствие Кодексу — ОБЯЗАТЕЛЬНО сформируй в начале ответа блок:\n"
        f"  «⚠️ АНАЛИЗ ПЕРЕСЕЧЕНИЙ И ПРОТИВОРЕЧИЙ:\n"
        f"   • Пересечение/Конфликт с [РЕГ-ХХХ]: [в чем суть конфликта]\n"
        f"   • Вопрос для заказчика/автора: [конкретный вопрос для устранения коллизии]»\n"
        f"- Если противоречий нет — напиши: «✅ Сверка пройдена: противоречий с действующими регламентами РЕГ-001..010 не обнаружено.»\n\n"
        f"ШАГ 2: СТАНДАРТИЗИРОВАННЫЙ ПРОЕКТ РЕГЛАМЕНТА (5 РАЗДЕЛОВ)\n"
        f"- Оформи документ строго по 5 обязательным разделам (Код: РЕГ-XXX-ЧЕРНОВИК, статус v0.1).\n"
        f"- Должности используй строго из РЕГ-002 (Оргструктура).\n"
        f"- Недостающие сроки и лимиты пометь маркером [ТРЕБУЕТ УТОЧНЕНИЯ: формулировка вопроса с вариантом].\n\n"
        f"ШАГ 3: ЕСЛИ ПРИСЛАНА ЗАЯВКА С НУЛЯ (НЕТ ШАГОВ ПРОЦЕССА)\n"
        f"- Поблагодари автора и задай ровно 3 целевых вопроса (Исполнители, Шаги, Сроки/Формы).\n\n"
        f"Отвечай строго на русском языке, предельно структурированно, грамотно и без воды."
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
        answer = resp.text or ""
        return answer

    answer: str = await loop.run_in_executor(None, _call_ai)
    
    history.append(f"Автор ({author_name}): {user_text}")
    history.append(f"Кодификатор: {answer}")
    if len(history) > 12:
        user_histories[user_id] = history[-10:]

    if is_complete_regulation(answer):
        try:
            export_service.register_completed_regulation(user_id, author_name, answer)
            repo_root = Path(__file__).resolve().parent.parent
            in_work_dir = repo_root / "knowledge_base/01_В_РАБОТЕ" if (repo_root / "knowledge_base/01_В_РАБОТЕ").exists() else Path("/home/roman/knowledge_base/01_В_РАБОТЕ")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"draft_{author_name.replace(' ', '_')}_{timestamp}.md"
            draft_path = in_work_dir / filename
            draft_path.write_text(answer, encoding="utf-8")
            logger.info(f"Черновик сохранен в 01_В_РАБОТЕ: {filename}")
        except Exception as e:
            logger.error(f"Ошибка сохранения черновика: {e}")

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
            text_content = msg.caption or "Проанализируй изображение и проверь на соответствие регламентам."

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

        # Детерминированное распознавание запроса на экспорт до LLM
        if text_content and not image_bytes and detect_export_intent(text_content):
            cached = export_service.get_last_artifact(user_id)
            if cached:
                payload = export_service.get_telegram_document_payload(cached)
                await msg.reply_document(
                    document=payload["document"],
                    filename=payload["filename"],
                    caption=payload["caption"],
                )
                gdocs_res = export_service.export_to_google_docs(cached)
                if gdocs_res.success and gdocs_res.doc_url:
                    await msg.reply_text(
                        f"🌐 **Google Docs:** {gdocs_res.doc_url}\nДокумент доступен для онлайн-согласования и редактирования.",
                        parse_mode="Markdown",
                    )
                else:
                    await msg.reply_text(f"ℹ️ {gdocs_res.message}")
            else:
                await msg.reply_text(
                    "ℹ️ У вас пока нет сохранённого завершённого регламента для выгрузки. Пожалуйста, отправьте черновик регламента для кодификации."
                )
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

        # Автоматическая выдача артефакта при завершении пятираздельного регламента
        if is_complete_regulation(reply_text):
            artifact = export_service.get_last_artifact(user_id)
            if not artifact:
                artifact = export_service.register_completed_regulation(user_id, author_name, reply_text)
            if artifact:
                payload = export_service.get_telegram_document_payload(artifact)
                await msg.reply_document(
                    document=payload["document"],
                    filename=payload["filename"],
                    caption=payload["caption"],
                )
                gdocs_res = export_service.export_to_google_docs(artifact)
                if gdocs_res.success and gdocs_res.doc_url:
                    await msg.reply_text(
                        f"🌐 **Google Docs:** {gdocs_res.doc_url}\nДокумент доступен для онлайн-согласования и редактирования.",
                        parse_mode="Markdown",
                    )
                else:
                    await msg.reply_text(f"ℹ️ {gdocs_res.message}")

    except Exception as e:
        logger.error(f"Глобальная ошибка обработчика: {e}", exc_info=True)
        await msg.reply_text(f"⚠ Произошла ошибка при обработке: {e}")

def main():
    if not TOKEN:
        raise RuntimeError("Не задана STAR_BUILDING_CODIFIER_BOT_TOKEN")
    logger.info("Запуск бота-кодификатора со встроенным Сверщиком коллизий...")
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
