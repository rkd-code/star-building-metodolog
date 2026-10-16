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

    async def test_handle_record_decision_pseudo_agreements_rejected(self):
        """T1 / S3: Псевдосогласия («Всё устраивает», «Возражений не имею» и т.д.) отклоняются на уровне транспорта."""
        for phrase in ["Всё устраивает", "Возражений не имею", "Именно так и поступим", "Не возражаю"]:
            with self.subTest(phrase=phrase):
                update = MagicMock()
                update.effective_user.id = 123
                update.effective_user.full_name = "Корж И.С."
                update.effective_chat.id = 123
                update.effective_chat.type = "private"
                update.effective_message.text = f"/record_decision {phrase}"
                update.effective_message.reply_text = AsyncMock()

                with patch.dict(
                    os.environ,
                    {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123", "DRAMKNOTE_P026_STORAGE_DIR": self.temp_dir.name},
                    clear=True,
                ):
                    await self.module.handle_record_decision(update, None)

                update.effective_message.reply_text.assert_called()
                call_text = update.effective_message.reply_text.call_args[0][0]
                self.assertIn("согласие", call_text.lower())
                self.assertEqual(0, len(self.storage.list_decisions(user_id=123)))

    async def test_e2e_propose_and_confirm_decision_transport(self):
        """T1 / S3: End-to-end проверка transport → handler → storage для предложений и подтверждений."""
        user_id = 123
        env_dict = {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123,999", "DRAMKNOTE_P026_STORAGE_DIR": self.temp_dir.name}

        # 1. Формирование предложения через /propose_decision
        up_prop = MagicMock()
        up_prop.effective_user.id = user_id
        up_prop.effective_user.full_name = "Корж И.С."
        up_prop.effective_chat.id = user_id
        up_prop.effective_chat.type = "private"
        up_prop.effective_message.text = "/propose_decision Утвердить норматив РОП 4 часа"
        up_prop.effective_message.reply_text = AsyncMock()

        with patch.dict(os.environ, env_dict, clear=True):
            await self.module.handle_propose_decision(up_prop, None)

        up_prop.effective_message.reply_text.assert_called()
        prop_reply = up_prop.effective_message.reply_text.call_args[0][0]
        self.assertIn("сформировано предложение", prop_reply.lower())
        import re
        prop_id_match = re.search(r"`(prop_[^`]+)`", prop_reply)
        self.assertIsNotNone(prop_id_match, "ID предложения должен присутствовать в ответе бота")
        assert prop_id_match is not None
        prop_id = prop_id_match.group(1)

        # 2. Негативная попытка: чужой пользователь (999) пытается подтвердить чужое предложение
        up_foreign = MagicMock()
        up_foreign.effective_user.id = 999
        up_foreign.effective_user.full_name = "Чужой"
        up_foreign.effective_chat.id = 999
        up_foreign.effective_chat.type = "private"
        up_foreign.effective_message.text = f"/confirm_decision {prop_id}"
        up_foreign.effective_message.reply_text = AsyncMock()

        with patch.dict(os.environ, env_dict, clear=True):
            await self.module.handle_confirm_decision(up_foreign, None)

        foreign_reply = up_foreign.effective_message.reply_text.call_args[0][0]
        self.assertIn("чужой", foreign_reply.lower())
        self.assertEqual(0, len(self.storage.list_decisions(user_id=123)))

        # 3. Позитивное подтверждение владельцем через /confirm_decision
        up_confirm = MagicMock()
        up_confirm.effective_user.id = user_id
        up_confirm.effective_user.full_name = "Корж И.С."
        up_confirm.effective_chat.id = user_id
        up_confirm.effective_chat.type = "private"
        up_confirm.effective_message.text = f"/confirm_decision {prop_id}"
        up_confirm.effective_message.reply_text = AsyncMock()

        with patch.dict(os.environ, env_dict, clear=True):
            await self.module.handle_confirm_decision(up_confirm, None)

        confirm_reply = up_confirm.effective_message.reply_text.call_args[0][0]
        self.assertIn("успешно зафиксировано", confirm_reply.lower())
        decisions = self.storage.list_decisions(user_id=user_id)
        self.assertEqual(1, len(decisions))
        self.assertEqual("Утвердить норматив РОП 4 часа", decisions[0]["exact_text"])

        # 4. Повторное подтверждение отклоняется
        with patch.dict(os.environ, env_dict, clear=True):
            await self.module.handle_confirm_decision(up_confirm, None)
        repeat_reply = up_confirm.effective_message.reply_text.call_args[0][0]
        self.assertIn("уже", repeat_reply.lower())

    async def test_u1_transport_rejects_refusal_and_conditional_confirmations(self):
        """U1: Проверка на уровне транспорта: фразы с оговорками и условиями отклоняются без записи."""
        env_dict = {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123", "DRAMKNOTE_P026_STORAGE_DIR": self.temp_dir.name}
        test_cases = [
            ("/record_decision подтверждаю p1 лишь после проверки", self.module.handle_record_decision),
            ("/record_decision /confirm p1 не надо", self.module.handle_record_decision),
            ("/record_decision утверждаю p1 при условии проверки бюджета", self.module.handle_record_decision),
            ("/confirm p1 только после согласования юристом", self.module.handle_confirm_decision),
        ]
        for cmd_text, handler_func in test_cases:
            with self.subTest(cmd_text=cmd_text):
                # Устанавливаем предложение p1
                self.handler.set_pending_proposal(123, 123, "Утвердить лимит скидки 12.5%", proposal_id="p1")
                up = MagicMock()
                up.effective_user.id = 123
                up.effective_user.full_name = "Корж И.С."
                up.effective_chat.id = 123
                up.effective_chat.type = "private"
                up.effective_message.text = cmd_text
                up.effective_message.reply_text = AsyncMock()

                with patch.dict(os.environ, env_dict, clear=True):
                    await handler_func(up, None)

                up.effective_message.reply_text.assert_called()
                # 0 записей в хранилище
                self.assertEqual(0, len(self.storage.list_decisions(user_id=123, chat_id=123)))
                # Предложение остаётся в pending
                self.assertIsNotNone(self.handler.get_pending_proposal(123, 123))

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

    def test_generate_answer_integrity_failure_stops_before_model_and_history(self):
        """S1 / R3: Сбой integrity gate обязан останавливать модель и историю до SDK."""
        import asyncio, types
        from types import SimpleNamespace as NS

        calls = []
        def model_call(**kw):
            calls.append(kw)
            return NS(text="SHOULD_NOT_BE_CALLED")

        genai_mod = types.ModuleType("google.genai")
        genai_mod.Client = lambda **kw: NS(models=NS(generate_content=model_call))
        st_mod = types.ModuleType("google.genai.types")
        st_mod.GenerateContentConfig = lambda **kw: NS(**kw)
        st_mod.Part = NS(from_bytes=lambda **kw: NS(**kw))
        genai_mod.types = st_mod
        google_mod = types.ModuleType("google")
        google_mod.genai = genai_mod

        user_id = 999123
        self.module._user_histories[user_id].clear()

        with patch.dict(sys.modules, {"google": google_mod, "google.genai": genai_mod, "google.genai.types": st_mod}), \
             patch.object(self.module, "get_api_key", return_value="OFFLINE_KEY"), \
             patch.object(self.module, "get_strategy_context", return_value="BASE"), \
             patch.object(P026SubjectBase, "verify_all_sources", side_effect=SubjectBaseIntegrityError("TAMPERED")):

            answer = asyncio.run(self.module.generate_answer("Вопрос по P-026", "Автор", user_id, user_id))

        self.assertEqual(0, len(calls), "При отказе целостности обращение к модели категорически запрещено (0 calls)")
        self.assertEqual(0, len(self.module._user_histories[user_id]), "При отказе целостности история пользователя не должна обновляться")
        self.assertIn("целостность", answer.lower(), "Пользователю должно возвращаться безопасное сообщение об отказе целостности")

    async def test_process_and_reply_integrity_failure_stops_before_model(self):
        """S1 / R3: process_and_reply при сбое целостности возвращает отказ без обращения к модели."""
        user_id = 999124
        update = MagicMock()
        update.effective_user.id = user_id
        update.effective_user.full_name = "Корж И.С."
        update.effective_chat.id = user_id
        update.effective_chat.type = "private"
        update.effective_message.reply_chat_action = AsyncMock()
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(os.environ, {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": str(user_id)}), \
             patch.object(self.module, "get_api_key", return_value="OFFLINE_KEY"), \
             patch.object(self.module, "get_strategy_context", return_value="BASE"), \
             patch.object(P026SubjectBase, "verify_all_sources", side_effect=SubjectBaseIntegrityError("TAMPERED")), \
             patch("google.genai.Client") as mock_client:

            await self.module.process_and_reply(update, supplied_text="Любой вопрос по P-026")

        mock_client.assert_not_called()
        update.effective_message.reply_text.assert_called()
        call_args_str = str(update.effective_message.reply_text.call_args_list)
        self.assertIn("целостност", call_args_str.lower())
        self.assertEqual(0, len(self.module._user_histories[user_id]))

    def test_generate_answer_missing_parsers_fails_closed_before_sdk(self):
        """FN-014 HIGH INTEGRITY: Отсутствие openpyxl или pypdf блокирует модель и историю (0 SDK calls, 0 writes)."""
        import asyncio, types
        from types import SimpleNamespace as NS

        calls = []
        def model_call(**kw):
            calls.append(kw)
            return NS(text="SHOULD_NOT_BE_CALLED")

        genai_mod = types.ModuleType("google.genai")
        genai_mod.Client = lambda **kw: NS(models=NS(generate_content=model_call))
        st_mod = types.ModuleType("google.genai.types")
        st_mod.GenerateContentConfig = lambda **kw: NS(**kw)
        st_mod.Part = NS(from_bytes=lambda **kw: NS(**kw))
        genai_mod.types = st_mod
        google_mod = types.ModuleType("google")
        google_mod.genai = genai_mod

        for missing_mod in ("openpyxl", "pypdf"):
            user_id = 999800 + (1 if missing_mod == "openpyxl" else 2)
            self.module._user_histories[user_id].clear()
            calls.clear()

            with patch.dict(sys.modules, {"google": google_mod, "google.genai": genai_mod, "google.genai.types": st_mod, missing_mod: None}), \
                 patch.object(self.module, "get_api_key", return_value="OFFLINE_KEY"), \
                 patch.object(self.module, "get_strategy_context", return_value="BASE"):

                answer = asyncio.run(self.module.generate_answer("Вопрос по скидкам", "Автор", user_id, user_id))

            self.assertEqual(0, len(calls), f"При отсутствии {missing_mod} модель не должна вызываться")
            self.assertEqual(0, len(self.module._user_histories[user_id]), f"При отсутствии {missing_mod} история не должна пополняться")
            self.assertIn("целостность", answer.lower())
            self.assertNotIn("\ufffd", answer)

if __name__ == "__main__":
    unittest.main()
