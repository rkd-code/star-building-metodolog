#!/usr/bin/env python3
"""Испытания диагностики двух Telegram-ботов Star Building."""

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("bot_healthcheck.py")


def load_module():
    spec = importlib.util.spec_from_file_location("bot_healthcheck", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BotHealthcheckTests(unittest.TestCase):
    def test_evaluate_bot_requires_matching_username_and_clean_polling(self):
        module = load_module()
        status = module.evaluate_bot(
            expected_username="ReglamentSB_bot",
            me={"ok": True, "result": {"username": "ReglamentSB_bot"}},
            webhook={"ok": True, "result": {"url": "", "pending_update_count": 0}},
            service_active=True,
        )
        self.assertTrue(status["ok"])
        self.assertEqual([], status["problems"])

    def test_evaluate_bot_reports_wrong_account_and_inactive_service(self):
        module = load_module()
        status = module.evaluate_bot(
            expected_username="star_building_help_bot",
            me={"ok": True, "result": {"username": "wrong_bot"}},
            webhook={"ok": True, "result": {"url": "https://example.invalid", "pending_update_count": 3, "last_error_message": "timeout"}},
            service_active=False,
        )
        self.assertFalse(status["ok"])
        self.assertIn("неверное имя бота", status["problems"])
        self.assertIn("служба не запущена", status["problems"])
        self.assertIn("активен webhook при режиме polling", status["problems"])
        self.assertIn("Telegram сообщил ошибку: timeout", status["problems"])


if __name__ == "__main__":
    unittest.main()
