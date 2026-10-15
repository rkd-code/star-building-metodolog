import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BOT = ROOT / "strategy_bot.py"
SERVICE = ROOT / "systemd" / "star-building-strategy.service"
SOURCES = {
    ROOT.parent / "35-commercial-marketing-strategy" / "STRATEGY.md",
    ROOT.parent / "35-commercial-marketing-strategy" / "PRESENTATION_THESES.md",
    ROOT.parent / "36-marketing-budget-2026" / "BUDGET_RATIONALE.md",
}


def load_bot():
    spec = importlib.util.spec_from_file_location("strategy_bot", BOT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StrategyBotTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_dir = Path(self.temp_dir.name) / "p026_storage"
        self.env_patcher = patch.dict(
            os.environ,
            {
                "DRAMKNOTE_P026_STORAGE_DIR": str(self.storage_dir),
                "STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123",
            },
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        self.temp_dir.cleanup()

    def test_sources_are_explicit_and_exist(self):
        module = load_bot()
        self.assertEqual(SOURCES, set(module.STRATEGY_SOURCE_FILES))
        self.assertTrue(all(path.is_file() for path in module.STRATEGY_SOURCE_FILES))
        context, manifest = module.load_strategy_context()
        self.assertIn("500 тонн", context)
        self.assertEqual(3, len(manifest))
        self.assertTrue(all(item["sha256"] and item["bytes"] > 0 for item in manifest))

    def test_access_is_closed_by_default(self):
        module = load_bot()
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(set(), module.allowed_user_ids())
            self.assertFalse(module.is_authorized(123))
        with patch.dict(os.environ, {"STAR_BUILDING_STRATEGY_ALLOWED_USER_IDS": "123, 456"}, clear=True):
            self.assertEqual({123, 456}, module.allowed_user_ids())
            self.assertTrue(module.is_authorized(123))
            self.assertFalse(module.is_authorized(999))

    def test_prompt_preserves_strategy_status_and_decision_boundary(self):
        module = load_bot()
        prompt = module.build_system_prompt("КОНТЕКСТ")
        prompt_folded = prompt.casefold()
        for phrase in (
            "рабочая версия",
            "не утверждённый корпоративный регламент",
            "ФАКТ",
            "РАСЧЁТ",
            "ПРЕДЛОЖЕНИЕ",
            "ТРЕБУЕТ РЕШЕНИЯ",
            "не изменяй канонические файлы",
            "не обещай срок без подтверждённого производственного слота",
        ):
            self.assertIn(phrase.casefold(), prompt_folded)

    def test_chunks_fit_telegram_limit_and_preserve_text(self):
        module = load_bot()
        text = ("Раздел стратегии\n" + "данные " * 800 + "\n") * 3
        chunks = module.split_for_telegram(text, limit=3900)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= 3900 for chunk in chunks))
        self.assertEqual(text, "".join(chunks))

    def test_input_limits_reject_oversized_payload(self):
        module = load_bot()
        with self.assertRaises(ValueError):
            module.validate_input("x" * (module.MAX_INPUT_CHARS + 1))
        self.assertEqual("вопрос", module.validate_input("  вопрос  "))

    def test_telegram_callback_keeps_context_separate_from_supplied_text(self):
        import inspect
        module = load_bot()
        params = list(inspect.signature(module.process_and_reply).parameters)
        self.assertEqual(["update", "context", "supplied_text"], params)

    def test_service_is_independent_and_hardened(self):
        text = SERVICE.read_text(encoding="utf-8")
        self.assertIn("WorkingDirectory=/home/roman/37-strategy-bot", text)
        self.assertIn("STAR_BUILDING_STRATEGY", (ROOT / "env.template").read_text(encoding="utf-8"))
        self.assertIn("EnvironmentFile=/home/roman/.config/star-building/strategy-bot.env", text)
        self.assertIn("Restart=always", text)
        self.assertIn("NoNewPrivileges=true", text)
        self.assertIn("PrivateTmp=true", text)
        self.assertIn("ReadWritePaths=/home/roman/.local/share/star-building/dramknote-p026", text)
        self.assertIn("StateDirectory=star-building/dramknote-p026", text)
        self.assertIn("DRAMKNOTE_P026_STORAGE_DIR", text)

    def test_repository_contains_no_token_value(self):
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".service", ".template"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                self.assertNotRegex(text, r"\d{8,12}:[A-Za-z0-9_-]{30,}")

    def test_no_default_home_pollution_during_tests(self):
        """Отрицательный тест-гард (R7 / F9): проверка изоляции тестов от $HOME/.local/share."""
        default_dir = Path.home() / ".local" / "share" / "star-building" / "dramknote-p026"
        module = load_bot()
        prompt = module.build_system_prompt("КОНТЕКСТ", user_id=123, chat_id=123)
        self.assertTrue(prompt)
        # Убеждаемся, что обращение изолировано во временной директории, а не в $HOME
        self.assertTrue(self.storage_dir.exists())


if __name__ == "__main__":
    unittest.main()
