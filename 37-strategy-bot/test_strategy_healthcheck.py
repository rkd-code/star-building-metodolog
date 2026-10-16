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

    def test_webhook_failure_with_description_fails_closed(self):
        """H1: Неуспешный getWebhookInfo (ok=False) обязан вызывать отказ (fail-closed) и передавать ошибку."""
        module = load_module()
        result = module.evaluate_bot(
            "strategy_bot",
            {"ok": True, "result": {"username": "strategy_bot"}},
            {"ok": False, "description": "synthetic failure", "error_code": 400},
            True,
            True,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("synthetic failure" in p for p in result["problems"]))

    def test_me_failure_with_description_fails_closed(self):
        """H1: Неуспешный getMe (ok=False) обязан вызывать отказ и не маскироваться под неверное имя."""
        module = load_module()
        result = module.evaluate_bot(
            "strategy_bot",
            {"ok": False, "description": "Unauthorized", "error_code": 401},
            {"ok": True, "result": {"url": "", "pending_update_count": 0}},
            True,
            True,
        )
        self.assertFalse(result["ok"])
        self.assertIsNone(result["username"])
        self.assertTrue(any("Unauthorized" in p for p in result["problems"]))
        self.assertFalse(any("неверное имя" in p for p in result["problems"]))

    def test_missing_or_invalid_result_structure_fails_closed(self):
        """H1: Отсутствующий или не являющийся словарем result обязан приводить к fail-closed."""
        module = load_module()
        invalid_results = [
            {"ok": True},  # missing result
            {"ok": True, "result": None},
            {"ok": True, "result": "not_a_dict"},
            {"ok": True, "result": [1, 2, 3]},
            {"ok": True, "result": 123},
        ]
        for inv in invalid_results:
            # в getWebhookInfo
            res = module.evaluate_bot(
                "strategy_bot",
                {"ok": True, "result": {"username": "strategy_bot"}},
                inv,
                True,
                True,
            )
            self.assertFalse(res["ok"], f"Ожидался fail-closed для webhook={inv}")
            self.assertTrue(len(res["problems"]) > 0)

            # в getMe
            res = module.evaluate_bot(
                "strategy_bot",
                inv,
                {"ok": True, "result": {"url": "", "pending_update_count": 0}},
                True,
                True,
            )
            self.assertFalse(res["ok"], f"Ожидался fail-closed для me={inv}")
            self.assertTrue(len(res["problems"]) > 0)

    def test_non_boolean_ok_fails_closed(self):
        """H1: Поле ok обязано быть строго булевым True (is True); 1, 'true', None отклоняются."""
        module = load_module()
        non_bools = [1, "true", "True", 0, None, [True]]
        for nb in non_bools:
            # в getWebhookInfo
            res = module.evaluate_bot(
                "strategy_bot",
                {"ok": True, "result": {"username": "strategy_bot"}},
                {"ok": nb, "result": {}},
                True,
                True,
            )
            self.assertFalse(res["ok"], f"Ожидался fail-closed для webhook ok={nb!r}")
            self.assertTrue(len(res["problems"]) > 0)

            # в getMe
            res = module.evaluate_bot(
                "strategy_bot",
                {"ok": nb, "result": {"username": "strategy_bot"}},
                {"ok": True, "result": {"url": "", "pending_update_count": 0}},
                True,
                True,
            )
            self.assertFalse(res["ok"], f"Ожидался fail-closed для me ok={nb!r}")
            self.assertTrue(len(res["problems"]) > 0)

    def test_non_dict_responses_fail_closed(self):
        """H1: Ответы me или webhook не являющиеся словарями приводят к fail-closed."""
        module = load_module()
        non_dicts = [None, "error", 123, []]
        for nd in non_dicts:
            res_hook = module.evaluate_bot(
                "strategy_bot",
                {"ok": True, "result": {"username": "strategy_bot"}},
                nd,
                True,
                True,
            )
            self.assertFalse(res_hook["ok"])
            self.assertTrue(len(res_hook["problems"]) > 0)

            res_me = module.evaluate_bot(
                "strategy_bot",
                nd,
                {"ok": True, "result": {"url": "", "pending_update_count": 0}},
                True,
                True,
            )
            self.assertFalse(res_me["ok"])
            self.assertTrue(len(res_me["problems"]) > 0)

    def test_active_webhook_fails_closed(self):
        """H1: Активный webhook при режиме polling вызывает отказ."""
        module = load_module()
        result = module.evaluate_bot(
            "strategy_bot",
            {"ok": True, "result": {"username": "strategy_bot"}},
            {"ok": True, "result": {"url": "https://api.example.com/webhook", "pending_update_count": 5}},
            True,
            True,
        )
        self.assertFalse(result["ok"])
        self.assertIn("активен webhook при режиме polling", result["problems"])
        self.assertEqual(result["pending_updates"], 5)

    def test_webhook_last_error_message_fails_closed(self):
        """H1: Наличие last_error_message в webhook вызывает отказ."""
        module = load_module()
        result = module.evaluate_bot(
            "strategy_bot",
            {"ok": True, "result": {"username": "strategy_bot"}},
            {"ok": True, "result": {"url": "", "last_error_message": "Connection refused", "pending_update_count": 0}},
            True,
            True,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("Connection refused" in p for p in result["problems"]))

    def test_inactive_service_fails_closed(self):
        """H1: Неактивная служба systemd вызывает отказ."""
        module = load_module()
        result = module.evaluate_bot(
            "strategy_bot",
            {"ok": True, "result": {"username": "strategy_bot"}},
            {"ok": True, "result": {"url": "", "pending_update_count": 0}},
            False,
            True,
        )
        self.assertFalse(result["ok"])
        self.assertIn("служба не запущена", result["problems"])

    def test_unready_sources_fails_closed(self):
        """H1: Недоступность источников стратегии вызывает отказ."""
        module = load_module()
        result = module.evaluate_bot(
            "strategy_bot",
            {"ok": True, "result": {"username": "strategy_bot"}},
            {"ok": True, "result": {"url": "", "pending_update_count": 0}},
            True,
            False,
        )
        self.assertFalse(result["ok"])
        self.assertIn("источники стратегии недоступны", result["problems"])


if __name__ == "__main__":
    unittest.main()
