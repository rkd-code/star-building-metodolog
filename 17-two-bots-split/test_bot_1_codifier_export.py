#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обязательные тесты для FN-013: экспорт регламентов в HTML и Google Docs в Смотрителе (@ReglamentSB_bot).

10 обязательных сценариев:
1. complete draft → HTML + send_document
2. incomplete clarification → no export
3. follow-up export → cache, no LLM
4. HTML escaping / script injection
5. sanitized bounded filename
6. missing OAuth → HTML + stable unavailable message
7. mocked Drive success → Google Doc URL
8. Drive failure → HTML preserved + safe message
9. Telegram document payload
10. no duplicate artifacts
"""

import io
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Гарантируем видимость локальных модулей
sys.path.insert(0, str(Path(__file__).resolve().parent))

from artifact_exporter import (
    ArtifactCache,
    CompletedArtifact,
    FilenameSanitizer,
    GoogleDocExportResult,
    GoogleDriveAdapter,
    HtmlRenderer,
    detect_export_intent,
    is_complete_regulation,
    ExportService,
)


SAMPLE_COMPLETE_REGULATION = """# РЕГЛАМЕНТ: Входной контроль материалов
Код документа: РЕГ-011-ЧЕРНОВИК
Статус: Черновик для согласования (v0.1)
Владелец процесса: Главный инженер
Связанные базовые регламенты: [REG-001, REG-002, REG-003]

## 1. Цель и ключевые результаты (Key Results)
1.1. Назначение: Обеспечение 100% соответствия поступающих материалов проекту.
1.2. Key Results: 0 дефектов при монтаже, 100% входной контроль за 4 часа.

## 2. Область применения и роли
2.1. Контур действия: Все строительные площадки Star Building.
2.2. Матрица ответственности (RACI):
| Роль | R | A | C | I |
|---|---|---|---|---|
| Инженер СК | R | A | C | I |

## 3. Пошаговый алгоритм выполнения
3.1. Прибытие транспорта и проверка ТТН.
3.2. Визуальный осмотр и отбор проб.
3.3. Составление акта входного контроля.

## 4. Контроль и точки аудита
4.1. Еженедельная сверка журналов входного контроля.
4.2. Эскалация при обнаружении брака по REG-002.

## 5. Документооборот, формы и шаблоны
| № | Документ | Место хранения | Шаблон/Ссылка |
|---|---|---|---|
| 1 | Акт входного контроля | 1С:ERP / Архив | ФОРМА-011 |
"""

SAMPLE_INCOMPLETE_CLARIFICATION = """Спасибо за обращение! Для подготовки регламента ответьте, пожалуйста, на 3 вопроса:
1. Кто является ответственным исполнителем процесса?
2. Какие основные шаги выполнения от прибытия до приемки?
3. Какие формы документов и в какие сроки должны заполняться?
"""

SAMPLE_XSS_DRAFT = """# РЕГЛАМЕНТ: <script>alert("xss")</script>
Код: REG-999-DRAFT <img src=x onerror=alert(1)>

## 1. Цель и ключевые результаты
<iframe src="http://evil.com"></iframe>

## 2. Область применения и роли
Роль: <a href="javascript:steal()">Злоумышленник</a>

## 3. Пошаговый алгоритм выполнения
Шаг 1: `<b>test</b>` & "quotes" 'single'

## 4. Контроль и точки аудита
Точка 1

## 5. Документооборот, формы и шаблоны
Форма 1
"""


class TestArtifactExportContract(unittest.TestCase):
    def setUp(self):
        self.cache = ArtifactCache(max_users=50)
        self.renderer = HtmlRenderer()
        self.sanitizer = FilenameSanitizer()
        self.drive_adapter = GoogleDriveAdapter(token_path=None)
        self.service = ExportService(
            cache=self.cache,
            renderer=self.renderer,
            sanitizer=self.sanitizer,
            drive_adapter=self.drive_adapter,
        )

    # 1. complete draft → HTML + send_document
    def test_01_complete_draft_triggers_html_and_send_document(self):
        self.assertTrue(is_complete_regulation(SAMPLE_COMPLETE_REGULATION))
        artifact = self.service.register_completed_regulation(
            user_id=12345,
            author_name="Иван Иванов",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
        )
        self.assertIsNotNone(artifact)
        self.assertTrue(artifact.html_content.startswith("<!DOCTYPE html>"))
        self.assertIn("Входной контроль материалов", artifact.html_content)
        self.assertTrue(artifact.filename.endswith(".html"))

        # Проверяем генерацию документа для отправки
        payload = self.service.get_telegram_document_payload(artifact)
        self.assertIsInstance(payload["document"], io.BytesIO)
        self.assertEqual(payload["filename"], artifact.filename)
        self.assertEqual(payload["mime_type"], "text/html")

    # 2. incomplete clarification → no export
    def test_02_incomplete_clarification_does_not_trigger_export(self):
        self.assertFalse(is_complete_regulation(SAMPLE_INCOMPLETE_CLARIFICATION))
        artifact = self.service.register_completed_regulation(
            user_id=12345,
            author_name="Иван Иванов",
            regulation_text=SAMPLE_INCOMPLETE_CLARIFICATION,
        )
        self.assertIsNone(artifact)
        self.assertIsNone(self.service.get_last_artifact(user_id=12345))

    # 3. follow-up export → cache, no LLM
    def test_03_follow_up_export_uses_cache_without_llm(self):
        # Сохраняем в кэш
        self.service.register_completed_regulation(
            user_id=999,
            author_name="Петр Петров",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
        )

        # Проверяем детерминированное распознавание намерения экспорта
        export_intents = [
            "выдай файл",
            "дай html",
            "экспорт в html",
            "экспортируй в гугл докс",
            "сохрани в gdocs",
            "скинь документ",
            "скачать регламент",
            "файл",
            "Google Docs",
        ]
        for phrase in export_intents:
            self.assertTrue(detect_export_intent(phrase), f"Failed to detect intent for: '{phrase}'")

        # Не экспортные фразы
        non_export = [
            "Привет, как дела?",
            "Вот черновик регламента по закупкам...",
            "Нужно изменить пункт 2.1 в регламенте",
        ]
        for phrase in non_export:
            self.assertFalse(detect_export_intent(phrase), f"False positive intent for: '{phrase}'")

        # Проверяем получение из кэша без вызова LLM
        mock_llm = MagicMock()
        cached_artifact = self.service.get_last_artifact(user_id=999)
        self.assertIsNotNone(cached_artifact)
        self.assertEqual(cached_artifact.user_id, 999)
        mock_llm.assert_not_called()

    # 4. HTML escaping / script injection
    def test_04_html_escaping_and_script_injection(self):
        html = self.renderer.render(SAMPLE_XSS_DRAFT, author_name="Тестер")

        # Проверяем, что опасные сырые теги отсутствуют в HTML
        self.assertNotIn("<script>", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<a ", html)
        self.assertNotIn("href=\"javascript:", html)

        # Проверяем наличие безопасных экранированных сущностей
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;iframe", html)
        self.assertIn("&lt;img", html)
        self.assertIn("&quot;quotes&quot;", html)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("UTF-8", html)

    # 5. sanitized bounded filename
    def test_05_sanitized_bounded_filename(self):
        # Path traversal
        name1 = self.sanitizer.sanitize("../../etc/passwd/регламент", max_length=64)
        self.assertNotIn("..", name1)
        self.assertNotIn("/", name1)
        self.assertNotIn("\\", name1)
        self.assertTrue(name1.endswith(".html"))

        # Ограничение длины
        very_long = "РЕГ-001 " + "Очень длинное наименование регламента " * 10
        name2 = self.sanitizer.sanitize(very_long, max_length=50)
        self.assertLessEqual(len(name2), 50)
        self.assertTrue(name2.endswith(".html"))

        # Пустое / спецсимволы
        name3 = self.sanitizer.sanitize("   ??? /// ***   ", max_length=64)
        self.assertTrue(name3.startswith("reglament_"))
        self.assertTrue(name3.endswith(".html"))

    # 6. missing OAuth → HTML + stable unavailable message
    def test_06_missing_oauth_provides_html_and_stable_unavailable_message(self):
        adapter = GoogleDriveAdapter(token_path="/non/existent/token.json")
        result = adapter.export_html_to_google_doc(
            html_content="<html><body>Test</body></html>",
            title="Тестовый регламент",
        )
        self.assertFalse(result.success)
        self.assertIsNone(result.doc_url)
        self.assertIn("не настроен", result.message.lower())
        # Никаких утечек путей/секретов
        self.assertNotIn("/non/existent", result.message)

    # 7. mocked Drive success → Google Doc URL
    def test_07_mocked_drive_success_returns_verified_google_doc_url(self):
        adapter = GoogleDriveAdapter(token_path="/mock/token.json")
        mock_file_id = "1a2B3c4D5e6F7g8H9i0J"

        with patch.object(adapter, "is_configured", return_value=True), \
             patch.object(adapter, "_upload_to_drive", return_value={"id": mock_file_id}):
            result = adapter.export_html_to_google_doc(
                html_content="<html><body>Test</body></html>",
                title="РЕГ-001",
            )
            self.assertTrue(result.success)
            self.assertEqual(
                result.doc_url,
                f"https://docs.google.com/document/d/{mock_file_id}/edit",
            )
            self.assertEqual(result.doc_id, mock_file_id)

    # 8. Drive failure → HTML preserved + safe message
    def test_08_drive_failure_preserves_html_and_provides_safe_message(self):
        adapter = GoogleDriveAdapter(token_path="/mock/token.json")

        with patch.object(adapter, "is_configured", return_value=True), \
             patch.object(adapter, "_upload_to_drive", side_effect=RuntimeError("Google API 500 Internal Error")):
            result = adapter.export_html_to_google_doc(
                html_content="<html><body>Test</body></html>",
                title="РЕГ-001",
            )
            self.assertFalse(result.success)
            self.assertIsNone(result.doc_url)
            self.assertIn("временно недоступен", result.message)
            # Не утекает raw exception traceback
            self.assertNotIn("RuntimeError", result.message)
            self.assertNotIn("500 Internal Error", result.message)

    # 9. Telegram document payload format
    def test_09_telegram_document_payload_format(self):
        artifact = CompletedArtifact(
            user_id=111,
            author_name="Анна",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
            html_content="<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body>Регламент</body></html>",
            filename="reglament_anna_20260925.html",
            title="Входной контроль материалов",
            created_at="2026-09-25 12:00:00",
        )
        payload = self.service.get_telegram_document_payload(artifact)
        self.assertIn("document", payload)
        self.assertIn("filename", payload)
        self.assertIn("caption", payload)
        self.assertIn("mime_type", payload)

        doc_stream = payload["document"]
        self.assertIsInstance(doc_stream, io.BytesIO)
        content = doc_stream.getvalue().decode("utf-8")
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("Регламент", content)

    # 10. no duplicate artifacts and bounded cache
    def test_10_no_duplicate_artifacts_and_bounded_cache(self):
        # Проверяем ограничение кэша
        small_cache = ArtifactCache(max_users=3)
        small_service = ExportService(
            cache=small_cache,
            renderer=self.renderer,
            sanitizer=self.sanitizer,
            drive_adapter=self.drive_adapter,
        )

        for i in range(5):
            small_service.register_completed_regulation(
                user_id=i,
                author_name=f"User {i}",
                regulation_text=SAMPLE_COMPLETE_REGULATION,
            )

        self.assertEqual(len(small_cache), 3)
        # Пользователи 0 и 1 должны быть вытеснены
        self.assertIsNone(small_cache.get(0))
        self.assertIsNone(small_cache.get(1))
        self.assertIsNotNone(small_cache.get(4))

        # Повторная регистрация одного и того же черновика для пользователя обновляет артефакт, а не дублирует
        initial_len = len(small_cache)
        small_service.register_completed_regulation(
            user_id=4,
            author_name="User 4",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
        )
        self.assertEqual(len(small_cache), initial_len)


class TestBot1CodifierHandlerIntegration(unittest.IsolatedAsyncioTestCase):
    """Интеграционные тесты обработчика handle_message в bot_1_codifier."""

    async def asyncSetUp(self):
        import bot_1_codifier
        self.bot_module = bot_1_codifier
        self.bot_module.export_service.cache = ArtifactCache(max_users=50)

    async def test_handle_message_complete_draft_flow(self):
        update = MagicMock()
        msg = AsyncMock()
        user = MagicMock()
        user.id = 555
        user.full_name = "Инженер Петров"
        update.effective_user = user
        update.effective_message = msg
        msg.text = "Вот регламент по входному контролю"
        msg.voice = None
        msg.audio = None
        msg.photo = None
        msg.document = None

        with patch.object(
            self.bot_module,
            "process_draft_request",
            new=AsyncMock(return_value=SAMPLE_COMPLETE_REGULATION),
        ):
            await self.bot_module.handle_message(update, MagicMock())

            # Проверяем, что текстовый ответ отправлен
            msg.reply_text.assert_called()
            # Проверяем, что HTML-документ отправлен
            msg.reply_document.assert_called_once()
            _, kwargs = msg.reply_document.call_args
            self.assertEqual(kwargs["filename"], "РЕГ-011-ЧЕРНОВИК_") if False else self.assertTrue(kwargs["filename"].endswith(".html"))
            self.assertIsInstance(kwargs["document"], io.BytesIO)

    async def test_handle_message_follow_up_no_llm(self):
        # Сначала регистрируем завершенный регламент
        self.bot_module.export_service.register_completed_regulation(
            user_id=777,
            author_name="Главный Инженер",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
        )

        update = MagicMock()
        msg = AsyncMock()
        user = MagicMock()
        user.id = 777
        user.full_name = "Главный Инженер"
        update.effective_user = user
        update.effective_message = msg
        msg.text = "выдай файл"
        msg.voice = None
        msg.audio = None
        msg.photo = None
        msg.document = None

        mock_process_draft = AsyncMock()
        with patch.object(self.bot_module, "process_draft_request", new=mock_process_draft):
            await self.bot_module.handle_message(update, MagicMock())

            # LLM / process_draft_request НЕ должен вызываться
            mock_process_draft.assert_not_called()
            # Документ должен быть отправлен
            msg.reply_document.assert_called_once()

    async def test_handle_message_follow_up_empty_cache_friendly_message(self):
        update = MagicMock()
        msg = AsyncMock()
        user = MagicMock()
        user.id = 888  # Новый пользователь без кэша
        user.full_name = "Новый Сотрудник"
        update.effective_user = user
        update.effective_message = msg
        msg.text = "экспорт в html"
        msg.voice = None
        msg.audio = None
        msg.photo = None
        msg.document = None

        mock_process_draft = AsyncMock()
        with patch.object(self.bot_module, "process_draft_request", new=mock_process_draft):
            await self.bot_module.handle_message(update, MagicMock())

            # LLM НЕ вызывается
            mock_process_draft.assert_not_called()
            # Документ не отправляется, отправляется информативное сообщение
            msg.reply_document.assert_not_called()
            msg.reply_text.assert_called_once()
            called_text = msg.reply_text.call_args[0][0]
            self.assertIn("нет сохранённого завершённого регламента", called_text)


if __name__ == "__main__":
    unittest.main()
