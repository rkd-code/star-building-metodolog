import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("strategy_healthcheck.py")


def load_module():
    spec = importlib.util.spec_from_file_location("strategy_healthcheck", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StrategyHealthcheckTest(unittest.TestCase):
    def test_healthy_polling_bot(self):
        module = load_module()
        result = module.evaluate_bot(
            "strategy_bot",
            {"ok": True, "result": {"username": "strategy_bot"}},
            {"ok": True, "result": {"url": "", "pending_update_count": 0}},
            True,
            True,
        )
        self.assertTrue(result["ok"])
        self.assertEqual([], result["problems"])

    def test_detects_identity_service_webhook_and_source_errors(self):
        module = load_module()
        result = module.evaluate_bot(
            "expected_bot",
            {"ok": True, "result": {"username": "other_bot"}},
            {"ok": True, "result": {"url": "https://example.test/hook", "last_error_message": "conflict"}},
            False,
            False,
        )
        self.assertFalse(result["ok"])
        joined = " | ".join(result["problems"])
        for phrase in ("неверное имя", "служба не запущена", "webhook", "источники", "Telegram сообщил ошибку"):
            self.assertIn(phrase, joined)


if __name__ == "__main__":
    unittest.main()
