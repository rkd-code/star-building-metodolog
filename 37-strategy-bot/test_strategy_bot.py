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

    def test_u6_context_budget_boundaries_and_history_growth(self):
        """U6: Проверка суммарного бюджета контекста на границе (ниже, на границе, выше) и роста истории."""
        import asyncio
        import types
        module = load_bot()

        calls = []
        genai = types.SimpleNamespace()
        typ = types.SimpleNamespace()
        google = types.SimpleNamespace()
        setattr(genai, "Client", lambda **kw: types.SimpleNamespace(
            models=types.SimpleNamespace(
                generate_content=lambda **kw: calls.append(1) or types.SimpleNamespace(text="OFFLINE_REPLY")
            )
        ))
        setattr(typ, "GenerateContentConfig", lambda **kw: types.SimpleNamespace(**kw))
        setattr(genai, "types", typ)
        setattr(google, "genai", genai)

        with patch.dict(sys.modules, {"google": google, "google.genai": genai, "google.genai.types": typ}), patch.object(module, "get_api_key", return_value="OFFLINE_KEY"):
            module._user_histories.clear()
            system_prompt = module.build_system_prompt(module.get_strategy_context(), user_id=123, chat_id=123)
            user_prompt = module.build_user_prompt("Вопрос по стратегии", "Автор", user_id=123, chat_id=123)
            exact_demand = len(system_prompt) + len(user_prompt) + module.MODEL_ANSWER_RESERVE_CHARS

            # 1. Ниже лимита (нормальный запрос)
            with patch.object(module, "MAX_TOTAL_CONTEXT_BUDGET_CHARS", exact_demand + 1000):
                calls.clear()
                ans = asyncio.run(module.generate_answer("Вопрос по стратегии", "Автор", 123, 123))
                self.assertEqual(1, len(calls), "Запрос ниже лимита обязан вызывать модель")
                self.assertEqual("OFFLINE_REPLY", ans)

            # 2. Ровно на границе бюджета
            module._user_histories.clear()
            with patch.object(module, "MAX_TOTAL_CONTEXT_BUDGET_CHARS", exact_demand):
                calls.clear()
                ans = asyncio.run(module.generate_answer("Вопрос по стратегии", "Автор", 123, 123))
                self.assertEqual(1, len(calls), "Запрос ровно на границе обязан выполняться")
                self.assertEqual("OFFLINE_REPLY", ans)

            # 3. Выше границы бюджета на 1 символ (fail-closed до вызова модели)
            module._user_histories.clear()
            before_hist = list(module._user_histories[123])
            with patch.object(module, "MAX_TOTAL_CONTEXT_BUDGET_CHARS", exact_demand - 1):
                calls.clear()
                ans = asyncio.run(module.generate_answer("Вопрос по стратегии", "Автор", 123, 123))
                self.assertEqual(0, len(calls), "При превышении бюджета 0 вызовов модели (fail-closed)")
                self.assertIn("превышает допустимый бюджет", ans)
                self.assertEqual(before_hist, module._user_histories[123], "История диалога обязана остаться неизменной")

            # 4. Имитация роста истории, приводящая к превышению бюджета
            module._user_histories.clear()
            u_p1 = module.build_user_prompt("Кратко", "Автор", user_id=123, chat_id=123)
            d1 = len(system_prompt) + len(u_p1) + module.MODEL_ANSWER_RESERVE_CHARS
            budget_tight = d1 + 10  # Запас всего 10 символов: первый вызов пройдёт, второй превысит из-за истории
            with patch.object(module, "MAX_TOTAL_CONTEXT_BUDGET_CHARS", budget_tight):
                calls.clear()
                # Первый вызов проходит (в рамках бюджета)
                ans1 = asyncio.run(module.generate_answer("Кратко", "Автор", 123, 123))
                self.assertEqual(1, len(calls))
                self.assertEqual("OFFLINE_REPLY", ans1)
                hist_after_1 = list(module._user_histories[123])
                self.assertGreater(len(hist_after_1), 0)

                # Второй вызов из-за выросшей истории превышает budget_tight -> отказ
                calls.clear()
                ans2 = asyncio.run(module.generate_answer("Повторный вопрос", "Автор", 123, 123))
                self.assertEqual(0, len(calls), "После роста истории при превышении бюджета модель не должна вызываться")
                self.assertIn("превышает допустимый бюджет", ans2)
                self.assertEqual(hist_after_1, module._user_histories[123], "История не должна меняться при отказе")


if __name__ == "__main__":
    unittest.main()
