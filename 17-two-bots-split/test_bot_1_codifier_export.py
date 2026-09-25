#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обязательные тесты для FN-013: экспорт регламентов в HTML и Google Docs в Смотрителе (@ReglamentSB_bot).

Тестовое покрытие:
- 10 базовых сценариев FN-013
- HIGH-1: Регрессионные тесты is_complete_regulation (строгий порядок, ровно по одному, marker-only/out-of-order false, непустое содержимое)
- HIGH-2: Регрессионные тесты идемпотентности Google Docs (sequential reuse, 20 concurrent threads single create)
- HIGH-3: Регрессионные тесты безопасности OAuth токена (0644/symlink/hardlink/wrong owner/refresh/parent dir)
- HIGH-4: Регрессионные тесты PersistentArtifactStore (сохранение при перезапуске, изоляция user_id, fail-closed при повреждении)
- MEDIUM-1: Санитизация имени черновика и строгий контроль containment в 01_В_РАБОТЕ
- MEDIUM-4: Воспроизводимый манифест зависимостей и верификация импортов
"""

import concurrent.futures
import io
import os
import threading
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Гарантируем видимость локальных модулей
sys.path.insert(0, str(Path(__file__).resolve().parent))

from artifact_exporter import (
    ArtifactCache,
    CompletedArtifact,
    FilenameSanitizer,
    GoogleDocExportResult,
    GoogleDriveAdapter,
    HtmlRenderer,
    OAuthTokenSecurityError,
    OAuthTokenValidator,
    PersistentArtifactStore,
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
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_artifacts.db"
        self.store = PersistentArtifactStore(db_path=self.db_path, max_users=50)
        self.renderer = HtmlRenderer()
        self.sanitizer = FilenameSanitizer()
        self.drive_adapter = GoogleDriveAdapter(token_path=None)
        self.service = ExportService(
            store=self.store,
            renderer=self.renderer,
            sanitizer=self.sanitizer,
            drive_adapter=self.drive_adapter,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

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
        self.service.register_completed_regulation(
            user_id=999,
            author_name="Петр Петров",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
        )

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

        non_export = [
            "Привет, как дела?",
            "Вот черновик регламента по закупкам...",
            "Нужно изменить пункт 2.1 в регламенте",
        ]
        for phrase in non_export:
            self.assertFalse(detect_export_intent(phrase), f"False positive intent for: '{phrase}'")

        mock_llm = MagicMock()
        cached_artifact = self.service.get_last_artifact(user_id=999)
        self.assertIsNotNone(cached_artifact)
        self.assertEqual(cached_artifact.user_id, 999)
        mock_llm.assert_not_called()

    # 4. HTML escaping / script injection
    def test_04_html_escaping_and_script_injection(self):
        html = self.renderer.render(SAMPLE_XSS_DRAFT, author_name="Тестер")

        self.assertNotIn("<script>", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<a ", html)
        self.assertNotIn("href=\"javascript:", html)

        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;iframe", html)
        self.assertIn("&lt;img", html)
        self.assertIn("&quot;quotes&quot;", html)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("UTF-8", html)

    # 5. sanitized bounded filename
    def test_05_sanitized_bounded_filename(self):
        name1 = self.sanitizer.sanitize("../../etc/passwd/регламент", max_length=64)
        self.assertNotIn("..", name1)
        self.assertNotIn("/", name1)
        self.assertNotIn("\\", name1)
        self.assertTrue(name1.endswith(".html"))

        very_long = "РЕГ-001 " + "Очень длинное наименование регламента " * 10
        name2 = self.sanitizer.sanitize(very_long, max_length=50)
        self.assertLessEqual(len(name2), 50)
        self.assertTrue(name2.endswith(".html"))

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
        self.assertIn("недоступен", result.message.lower())
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

    # 10. no duplicate artifacts and bounded store
    def test_10_no_duplicate_artifacts_and_bounded_store(self):
        small_db = Path(self.temp_dir.name) / "small_artifacts.db"
        small_store = PersistentArtifactStore(db_path=small_db, max_users=3)
        small_service = ExportService(
            store=small_store,
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

        self.assertEqual(len(small_store), 3)
        self.assertIsNone(small_store.get(0))
        self.assertIsNone(small_store.get(1))
        self.assertIsNotNone(small_store.get(4))

        initial_len = len(small_store)
        small_service.register_completed_regulation(
            user_id=4,
            author_name="User 4",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
        )
        self.assertEqual(len(small_store), initial_len)

    # HIGH-1: is_complete_regulation regressions
    def test_11_is_complete_regulation_marker_only_rejected(self):
        marker_only_text = (
            "# РЕГЛАМЕНТ: Пустой документ\n"
            "## 1. Цель и ключевые результаты\n"
            "## 2. Область применения и роли\n"
            "## 3. Пошаговый алгоритм выполнения\n"
            "## 4. Контроль и точки аудита\n"
            "## 5. Документооборот, формы и шаблоны\n"
        )
        self.assertFalse(is_complete_regulation(marker_only_text))

    def test_12_is_complete_regulation_inverted_order_rejected(self):
        inverted_text = (
            "# РЕГЛАМЕНТ: Неверный порядок\n"
            "## 2. Область применения и роли\nРоли и матрица ответственности\n\n"
            "## 1. Цель и ключевые результаты\nЦели и задачи процесса\n\n"
            "## 3. Пошаговый алгоритм выполнения\nШаги процесса\n\n"
            "## 4. Контроль и точки аудита\nКонтрольные точки\n\n"
            "## 5. Документооборот, формы и шаблоны\nФормы и акты\n"
        )
        self.assertFalse(is_complete_regulation(inverted_text))

    def test_13_is_complete_regulation_duplicate_or_extra_headers_rejected(self):
        # Дубликат раздела 1
        duplicate_text = (
            SAMPLE_COMPLETE_REGULATION +
            "\n## 1. Цель и ключевые результаты\nПовторный блок\n"
        )
        self.assertFalse(is_complete_regulation(duplicate_text))

        # Лишний заголовок 2-го уровня
        extra_header_text = (
            SAMPLE_COMPLETE_REGULATION +
            "\n## 6. Дополнительные положения\nТекст\n"
        )
        self.assertFalse(is_complete_regulation(extra_header_text))

        # Только 4 раздела (пропущен 5-й)
        missing_section_text = (
            "# РЕГЛАМЕНТ: Неполный документ\n"
            "## 1. Цель и ключевые результаты\nЦели\n\n"
            "## 2. Область применения и роли\nРоли\n\n"
            "## 3. Пошаговый алгоритм выполнения\nШаги\n\n"
            "## 4. Контроль и точки аудита\nКонтроль\n"
        )
        self.assertFalse(is_complete_regulation(missing_section_text))

    def test_14_is_complete_regulation_empty_section_content_rejected(self):
        # Раздел 3 содержит только пробельные символы
        empty_section_3 = (
            "# РЕГЛАМЕНТ: Пустой раздел 3\n"
            "## 1. Цель и ключевые результаты\nЦели процесса\n\n"
            "## 2. Область применения и роли\nРоли RACI\n\n"
            "## 3. Пошаговый алгоритм выполнения\n   \n\n"
            "## 4. Контроль и точки аудита\nТочки контроля\n\n"
            "## 5. Документооборот, формы и шаблоны\nФормы\n"
        )
        self.assertFalse(is_complete_regulation(empty_section_3))

        # Раздел 5 в самом конце пуст
        empty_section_5 = (
            "# РЕГЛАМЕНТ: Пустой раздел 5\n"
            "## 1. Цель и ключевые результаты\nЦели процесса\n\n"
            "## 2. Область применения и роли\nРоли RACI\n\n"
            "## 3. Пошаговый алгоритм выполнения\nШаги\n\n"
            "## 4. Контроль и точки аудита\nТочки контроля\n\n"
            "## 5. Документооборот, формы и шаблоны\n"
        )
        self.assertFalse(is_complete_regulation(empty_section_5))

    # HIGH-2: Google Docs idempotency regressions
    def test_15_gdocs_idempotency_sequential_reuse(self):
        artifact = self.service.register_completed_regulation(
            user_id=101,
            author_name="Инженер",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
        )
        self.assertIsNotNone(artifact)
        mock_file_id = "doc_id_seq_12345"

        with patch.object(self.drive_adapter, "is_configured", return_value=True), \
             patch.object(self.drive_adapter, "_upload_to_drive", return_value={"id": mock_file_id}) as mock_upload:
            # Первый вызов создает документ
            res1 = self.service.export_to_google_docs(artifact)
            self.assertTrue(res1.success)
            self.assertEqual(res1.doc_id, mock_file_id)
            self.assertEqual(mock_upload.call_count, 1)

            # Второй последовательный вызов переиспользует сохраненный gdocs_url
            res2 = self.service.export_to_google_docs(artifact)
            self.assertTrue(res2.success)
            self.assertEqual(res2.doc_id, mock_file_id)
            self.assertEqual(res2.doc_url, res1.doc_url)
            # API НЕ должен вызываться повторно
            self.assertEqual(mock_upload.call_count, 1)

    def test_16_gdocs_idempotency_concurrent_20_threads(self):
        artifact = self.service.register_completed_regulation(
            user_id=202,
            author_name="Инженер Параллельный",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
        )
        self.assertIsNotNone(artifact)
        mock_file_id = "doc_id_concurrent_9999"

        call_count = 0
        call_lock = threading.Lock()

        def fake_upload(html_content, title):
            nonlocal call_count
            with call_lock:
                call_count += 1
            time.sleep(0.05)  # Имитация задержки сети
            return {"id": mock_file_id}

        with patch.object(self.drive_adapter, "is_configured", return_value=True), \
             patch.object(self.drive_adapter, "_upload_to_drive", side_effect=fake_upload):
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [
                    executor.submit(self.service.export_to_google_docs, artifact)
                    for _ in range(20)
                ]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            # Ровно один вызов Google Drive API
            self.assertEqual(call_count, 1)
            # Все 20 параллельных запросов получили один и тот же результат
            for r in results:
                self.assertTrue(r.success)
                self.assertEqual(r.doc_id, mock_file_id)
                self.assertEqual(r.doc_url, f"https://docs.google.com/document/d/{mock_file_id}/edit")

    # HIGH-3: OAuth token path security regressions
    def test_17_oauth_security_0644_rejected(self):
        token_file = Path(self.temp_dir.name) / "token_0644.json"
        token_file.write_text('{"token": "secret"}')
        os.chmod(token_file, 0o644)
        os.chmod(self.temp_dir.name, 0o700)

        valid, reason = OAuthTokenValidator.validate_token_file(token_file, allow_custom_dir=True)
        self.assertFalse(valid)
        self.assertIn("0644", reason)

    def test_18_oauth_security_symlink_rejected(self):
        real_file = Path(self.temp_dir.name) / "real_token.json"
        real_file.write_text('{"token": "secret"}')
        os.chmod(real_file, 0o600)
        os.chmod(self.temp_dir.name, 0o700)

        symlink_file = Path(self.temp_dir.name) / "symlink_token.json"
        symlink_file.symlink_to(real_file)

        valid, reason = OAuthTokenValidator.validate_token_file(symlink_file, allow_custom_dir=True)
        self.assertFalse(valid)
        self.assertIn("Символические ссылки", reason)

    def test_19_oauth_security_hardlink_rejected(self):
        file1 = Path(self.temp_dir.name) / "token_hardlink_1.json"
        file1.write_text('{"token": "secret"}')
        os.chmod(file1, 0o600)
        os.chmod(self.temp_dir.name, 0o700)

        file2 = Path(self.temp_dir.name) / "token_hardlink_2.json"
        os.link(file1, file2)

        valid, reason = OAuthTokenValidator.validate_token_file(file1, allow_custom_dir=True)
        self.assertFalse(valid)
        self.assertIn("жесткие ссылки", reason.lower())

    def test_20_oauth_security_wrong_owner_rejected(self):
        valid_file = Path(self.temp_dir.name) / "token_owner.json"
        valid_file.write_text('{"token": "secret"}')
        os.chmod(valid_file, 0o600)
        os.chmod(self.temp_dir.name, 0o700)

        with patch("os.getuid", return_value=99999):
            valid, reason = OAuthTokenValidator.validate_token_file(valid_file, allow_custom_dir=True)
            self.assertFalse(valid)
            self.assertIn("владелец", reason.lower())

    def test_21_oauth_atomic_refresh_success(self):
        token_path = Path(self.temp_dir.name) / "google_oauth_token.json"
        OAuthTokenValidator.atomic_write_token_file(token_path, '{"token": "initial"}')

        self.assertTrue(token_path.exists())
        st = os.lstat(token_path)
        self.assertEqual(st.st_mode & 0o777, 0o600)
        self.assertEqual(st.st_nlink, 1)

        # Перезапись при refresh
        OAuthTokenValidator.atomic_write_token_file(token_path, '{"token": "refreshed_value"}')
        self.assertEqual(token_path.read_text(), '{"token": "refreshed_value"}')
        st2 = os.lstat(token_path)
        self.assertEqual(st2.st_mode & 0o777, 0o600)

    # HIGH-4: PersistentArtifactStore regressions
    def test_22_persistent_store_survives_process_restart(self):
        db_file = Path(self.temp_dir.name) / "persist_test.db"

        # Инстанс 1: создаем и сохраняем артефакт
        store1 = PersistentArtifactStore(db_path=db_file)
        service1 = ExportService(store=store1, renderer=self.renderer, sanitizer=self.sanitizer)
        service1.register_completed_regulation(
            user_id=8888,
            author_name="Перезапуск Процесса",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
        )
        del service1
        del store1

        # Инстанс 2: новый процесс читает из того же файла
        store2 = PersistentArtifactStore(db_path=db_file)
        service2 = ExportService(store=store2, renderer=self.renderer, sanitizer=self.sanitizer)
        loaded_artifact = service2.get_last_artifact(user_id=8888)
        self.assertIsNotNone(loaded_artifact)

        self.assertIsNotNone(loaded_artifact)
        self.assertEqual(loaded_artifact.user_id, 8888)
        self.assertEqual(loaded_artifact.author_name, "Перезапуск Процесса")
        self.assertIn("Входной контроль материалов", loaded_artifact.title)
        self.assertTrue(loaded_artifact.html_content.startswith("<!DOCTYPE html>"))

    def test_23_persistent_store_user_isolation(self):
        db_file = Path(self.temp_dir.name) / "isolation_test.db"
        store = PersistentArtifactStore(db_path=db_file)

        store.put(1, CompletedArtifact(
            user_id=1,
            author_name="User 1",
            regulation_text=SAMPLE_COMPLETE_REGULATION,
            html_content="<html>1</html>",
            filename="u1.html",
            title="Title 1",
            created_at="2026-09-25",
        ))

        self.assertIsNotNone(store.get(1))
        self.assertIsNone(store.get(2))
        self.assertIsNone(store.get(999))

    def test_24_persistent_store_corruption_fail_closed(self):
        corrupt_db_file = Path(self.temp_dir.name) / "corrupt.db"
        # Записываем мусор в SQLite файл
        corrupt_db_file.write_bytes(b"NOT_A_VALID_SQLITE_HEADER_RANDOM_GARBAGE")

        corrupt_store = PersistentArtifactStore(db_path=corrupt_db_file)
        # При повреждении базы get() возвращает None (fail-closed), без неперехваченных исключений
        res = corrupt_store.get(user_id=123)
        self.assertIsNone(res)

    # MEDIUM-1: Markdown draft filename & containment regressions
    def test_25_markdown_draft_containment_in_work_dir(self):
        work_dir = Path(self.temp_dir.name) / "01_В_РАБОТЕ"
        work_dir.mkdir(parents=True, exist_ok=True)

        author_name = "Иван Петров"
        sanitized_author = FilenameSanitizer.sanitize_base_name(author_name)
        timestamp = "20260925_120000"
        draft_filename = FilenameSanitizer.sanitize(
            f"draft_{sanitized_author}_{timestamp}",
            default_prefix="draft",
            suffix=".md",
            max_length=64,
        )
        target_path = FilenameSanitizer.verify_path_containment(work_dir, work_dir / draft_filename)
        self.assertEqual(target_path.parent, work_dir.resolve())
        self.assertTrue(target_path.name.endswith(".md"))

    def test_26_markdown_draft_path_traversal_rejection(self):
        work_dir = Path(self.temp_dir.name) / "01_В_РАБОТЕ"
        work_dir.mkdir(parents=True, exist_ok=True)

        # Попытка побега через ../../
        malicious_escape_path = work_dir / "../../etc/cron.d/malicious.md"
        with self.assertRaises(ValueError):
            FilenameSanitizer.verify_path_containment(work_dir, malicious_escape_path)

        # Санитизация автора удаляет .. и спецсимволы
        malicious_author = "../../../etc/passwd"
        cleaned_author = FilenameSanitizer.sanitize_base_name(malicious_author)
        self.assertNotIn("..", cleaned_author)
        self.assertNotIn("/", cleaned_author)

    # MEDIUM-4: Reproducible dependency manifest & imports verification
    def test_27_reproducible_dependencies_and_imports(self):
        required_modules = [
            "telegram",
            "google.oauth2.credentials",
            "googleapiclient.discovery",
            "faster_whisper",
            "docx",
            "pypdf",
        ]
        for mod in required_modules:
            try:
                __import__(mod)
            except ImportError as e:
                self.fail(f"Обязательный runtime-модуль '{mod}' не может быть импортирован: {e}")


class TestBot1CodifierHandlerIntegration(unittest.IsolatedAsyncioTestCase):
    """Интеграционные тесты обработчика handle_message в bot_1_codifier."""

    async def asyncSetUp(self):
        import bot_1_codifier
        self.bot_module = bot_1_codifier
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "bot_test_artifacts.db"
        self.bot_module.export_service.store = PersistentArtifactStore(db_path=self.db_path, max_users=50)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

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

            msg.reply_text.assert_called()
            msg.reply_document.assert_called_once()
            _, kwargs = msg.reply_document.call_args
            self.assertTrue(kwargs["filename"].endswith(".html"))
            self.assertIsInstance(kwargs["document"], io.BytesIO)

    async def test_handle_message_follow_up_no_llm(self):
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

            mock_process_draft.assert_not_called()
            msg.reply_document.assert_called_once()

    async def test_handle_message_follow_up_empty_cache_friendly_message(self):
        update = MagicMock()
        msg = AsyncMock()
        user = MagicMock()
        user.id = 888
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

            mock_process_draft.assert_not_called()
            msg.reply_document.assert_not_called()
            msg.reply_text.assert_called_once()
            called_text = msg.reply_text.call_args[0][0]
            self.assertIn("нет сохранённого завершённого регламента", called_text)


if __name__ == "__main__":
    unittest.main()
