import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
BOT = ROOT / "strategy_bot.py"

from p026_handler import P026Handler
from p026_storage import P026Storage
from p026_subject_base import P026SubjectBase, SubjectBaseIntegrityError


def load_bot():
    spec = importlib.util.spec_from_file_location("strategy_bot", BOT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class P026StrategyBotIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.module = load_bot()
        self.storage = P026Storage(base_dir=self.temp_dir.name)
        self.handler = P026Handler(storage=self.storage)
        setattr(self.module, "_p026_handler", self.handler)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prompt_includes_p026_rules(self):
        prompt = self.module.build_system_prompt("БАЗОВЫЙ КОНТЕКСТ")
        prompt_folded = prompt.casefold()

        self.assertIn("p-026", prompt_folded)
        self.assertIn("12.5%", prompt)
        self.assertIn("15%", prompt)
        self.assertIn("1 млрд тенге", prompt_folded)
        self.assertIn("не минимальный чек лида", prompt_folded)
        self.assertIn("3 рабочих час", prompt_folded)
        self.assertIn("вопрос №8", prompt_folded)
        self.assertIn("не переоткрывать навязчиво", prompt_folded)

    def test_prompt_includes_persistent_decisions(self):
        self.storage.record_decision(
            author="Корж И.С.",
            question_context="Пределы скидок",
            exact_text="Утвердить лимит скидки РОП до 12.5%",
            user_id=123,
            chat_id=456,
        )
        sys_prompt = self.module.build_system_prompt("БАЗОВЫЙ КОНТЕКСТ", user_id=123, chat_id=456)
        self.assertIn("Утвердить лимит скидки РОП до 12.5%", sys_prompt)

        user_prompt = self.module.build_user_prompt("Какой лимит?", "Корж И.С.", user_id=123, chat_id=456)
        self.assertIn("Утвердить лимит скидки РОП до 12.5%", user_prompt)

        # Другой пользователь не должен видеть это решение в промпте
        other_user_prompt = self.module.build_user_prompt("Какой лимит?", "Другой", user_id=999, chat_id=456)
        self.assertNotIn("Утвердить лимит скидки РОП до 12.5%", other_user_prompt)

    async def test_handle_project_authorized(self):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Корж И.С."
        update.effective_chat.id = 123
        update.effective_chat.type = "private"
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(
            os.environ,
            {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123", "DRAMKNOTE_P026_STORAGE_DIR": self.temp_dir.name},
            clear=True,
        ):
            await self.module.handle_project(update, None)

        update.effective_message.reply_text.assert_called()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("P-026", call_text)
        self.assertIn("Коммерческий департамент", call_text)
        self.assertIn("v0.6", call_text)
        self.assertIn("v0.3", call_text)
        self.assertIn("1 млрд тенге", call_text)

    async def test_handle_project_unauthorized(self):
        update = MagicMock()
        update.effective_user.id = 999
        update.effective_chat.id = 999
        update.effective_chat.type = "private"
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(
            os.environ,
            {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123", "DRAMKNOTE_P026_STORAGE_DIR": self.temp_dir.name},
            clear=True,
        ):
            await self.module.handle_project(update, None)

        update.effective_message.reply_text.assert_called_with("⛔ Этот стратегический контур закрыт. Обратитесь к владельцу доступа.")

    async def test_handle_record_decision_explicit(self):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Корж И.С."
        update.effective_chat.id = 123
        update.effective_chat.type = "private"
        update.effective_message.text = "/record_decision Утверждаю лимит скидки РОП до 12.5%"
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(
            os.environ,
            {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123", "DRAMKNOTE_P026_STORAGE_DIR": self.temp_dir.name},
            clear=True,
        ):
            await self.module.handle_record_decision(update, None)

        update.effective_message.reply_text.assert_called()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("зафиксировано", call_text.lower())
        self.assertIn("12.5%", call_text)

        # Проверяем, что в изолированном хранилище запись появилась
        decisions = self.storage.list_decisions(user_id=123)
        self.assertEqual(1, len(decisions))
        self.assertEqual("Утверждаю лимит скидки РОП до 12.5%", decisions[0]["exact_text"])

    async def test_handle_record_decision_ambiguous_rejected(self):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Корж И.С."
        update.effective_chat.id = 123
        update.effective_chat.type = "private"
        update.effective_message.text = "/record_decision да согласен"
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(
            os.environ,
            {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123", "DRAMKNOTE_P026_STORAGE_DIR": self.temp_dir.name},
            clear=True,
        ):
            await self.module.handle_record_decision(update, None)

        update.effective_message.reply_text.assert_called()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("неоднозначн", call_text.lower())

    async def test_handle_export_draft_sends_real_telegram_document(self):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Корж И.С."
        update.effective_chat.id = 123
        update.effective_chat.type = "private"
        update.effective_message.text = "/export_draft kd"
        update.effective_message.reply_text = AsyncMock()
        update.effective_message.reply_document = AsyncMock()

        with patch.dict(
            os.environ,
            {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123", "DRAMKNOTE_P026_STORAGE_DIR": self.temp_dir.name},
            clear=True,
        ):
            await self.module.handle_export_draft(update, None)

        # Проверка реального вызова отправки документа в Telegram
        update.effective_message.reply_document.assert_called()
        call_kwargs = update.effective_message.reply_document.call_args[1]
        self.assertIn("document", call_kwargs)
        self.assertIn("filename", call_kwargs)
        self.assertTrue(call_kwargs["filename"].startswith("DRAFT_КД_v1_"))
        doc_obj = call_kwargs["document"]
        doc_obj.seek(0)
        bytes_content = doc_obj.read()
        self.assertGreater(len(bytes_content), 100)
        self.assertIn(b"DRAFT ARTIFACT", bytes_content)

    async def test_handle_export_draft_group_chat_rejected(self):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_chat.id = -10012345
        update.effective_chat.type = "group"
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(
            os.environ,
            {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123", "DRAMKNOTE_P026_STORAGE_DIR": self.temp_dir.name},
            clear=True,
        ):
            await self.module.handle_export_draft(update, None)

        update.effective_message.reply_text.assert_called()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("личном диалоге", call_text.lower())

    async def test_process_and_reply_group_chat_rejected_before_model_and_history(self):
        """R2 / F2: Обычные сообщения в групповых чатах отклоняются до модели, исключая утечку приватной истории."""
        self.module._user_histories[123] = ["PRIVATE_DIALOG_SECRET_MARKER"]
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Корж И.С."
        update.effective_chat.id = -777
        update.effective_chat.type = "group"
        update.effective_message.reply_chat_action = AsyncMock()
        update.effective_message.reply_text = AsyncMock()

        with patch.object(self.module, "generate_answer", new_callable=AsyncMock) as mock_gen, \
             patch.dict(os.environ, {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123"}):
            await self.module.process_and_reply(update, supplied_text="Покажи историю")

        mock_gen.assert_not_called()
        update.effective_message.reply_text.assert_called()
        call_args_str = str(update.effective_message.reply_text.call_args_list)
        self.assertNotIn("PRIVATE_DIALOG_SECRET_MARKER", call_args_str)
        self.assertIn("личном", call_args_str.lower())

    def test_build_system_prompt_manifest_failure_fails_closed(self):
        """R3 / F6: Отказ генерации системного промпта при нарушении манифеста источников."""
        with patch.object(P026SubjectBase, "verify_all_sources", side_effect=SubjectBaseIntegrityError("TAMPERED")):
            prompt = self.module.build_system_prompt("БАЗОВЫЙ КОНТЕКСТ", user_id=123, chat_id=123)
            self.assertEqual("", prompt, "При нарушении манифеста источников системный промпт обязан быть пустым (fail-closed)")

    def test_get_p026_prompt_context_performs_source_reads(self):
        """R3 / F6: Генерация контекста P-026 фактически считывает канонические источники с диска."""
        base = P026SubjectBase()
        with patch.object(Path, "read_bytes", side_effect=AssertionError("SOURCE_READ")) as mock_read:
            ctx = base.get_p026_prompt_context()
            self.assertGreater(mock_read.call_count, 0, "Генерация контекста P-026 обязана обращаться к чтению источников")
            self.assertEqual("", ctx, "При исключении чтения контекст должен возвращать пустую строку fail-closed")

        # В нормальном режиме возвращается полный реальный контекст
        normal_ctx = base.get_p026_prompt_context()
        self.assertIn("РЕАЛЬНЫЕ МАТЕРИАЛЫ", normal_ctx)

if __name__ == "__main__":
    unittest.main()
