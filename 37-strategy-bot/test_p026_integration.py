import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
BOT = ROOT / "strategy_bot.py"


def load_bot():
    spec = importlib.util.spec_from_file_location("strategy_bot", BOT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class P026StrategyBotIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = load_bot()

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

    async def test_handle_project_authorized(self):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Корж И.С."
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(os.environ, {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123"}, clear=True):
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
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(os.environ, {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123"}, clear=True):
            await self.module.handle_project(update, None)

        update.effective_message.reply_text.assert_called_with("⛔ Этот стратегический контур закрыт. Обратитесь к владельцу доступа.")

    async def test_handle_record_decision_explicit(self):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Корж И.С."
        update.effective_message.text = "/record_decision Утверждаю лимит скидки РОП до 12.5%"
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(os.environ, {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123"}, clear=True):
            await self.module.handle_record_decision(update, None)

        update.effective_message.reply_text.assert_called()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("зафиксировано", call_text.lower())
        self.assertIn("12.5%", call_text)

    async def test_handle_record_decision_ambiguous_rejected(self):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Корж И.С."
        update.effective_message.text = "/record_decision да"
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(os.environ, {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123"}, clear=True):
            await self.module.handle_record_decision(update, None)

        update.effective_message.reply_text.assert_called()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("неоднозначный ответ", call_text.lower())

    async def test_handle_export_draft(self):
        update = MagicMock()
        update.effective_user.id = 123
        update.effective_user.full_name = "Корж И.С."
        update.effective_message.text = "/export_draft kd"
        update.effective_message.reply_text = AsyncMock()

        with patch.dict(os.environ, {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123"}, clear=True):
            await self.module.handle_export_draft(update, None)

        update.effective_message.reply_text.assert_called()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("черновик", call_text.lower())
        self.assertIn("экспортирован", call_text.lower())


if __name__ == "__main__":
    unittest.main()
