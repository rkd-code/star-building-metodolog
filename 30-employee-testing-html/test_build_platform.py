import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODULE_PATH = ROOT / "build_platform.py"
BANK_PATH = ROOT.parent / "29-employee-testing-service" / "question_bank_pool_001.xlsx"
HTML_PATH = ROOT / "index.html"


def load_module():
    spec = importlib.util.spec_from_file_location("build_platform", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlatformBuilderTests(unittest.TestCase):
    def test_bank_contains_102_complete_single_answer_questions(self):
        module = load_module()
        questions = module.load_bank(BANK_PATH)
        self.assertEqual(102, len(questions))
        self.assertTrue(all(len(q["options"]) == 4 for q in questions))
        self.assertTrue(all(sum(o["correct"] for o in q["options"]) == 1 for q in questions))
        self.assertTrue(all(q["roles"] == ["Менеджеры продаж", "РОП / Руководитель отдела продаж"] for q in questions))

    def test_scoring_uses_90_percent_threshold(self):
        module = load_module()
        self.assertEqual({"correct": 9, "total": 10, "percent": 90.0, "passed": True}, module.score_answers([True] * 9 + [False], 90))
        self.assertEqual({"correct": 8, "total": 10, "percent": 80.0, "passed": False}, module.score_answers([True] * 8 + [False] * 2, 90))

    def test_monthly_attempt_rule_uses_calendar_month(self):
        module = load_module()
        self.assertFalse(module.can_attempt("2026-08-01T12:00:00", "2026-08-31T23:59:59"))
        self.assertTrue(module.can_attempt("2026-08-31T23:59:59", "2026-09-01T00:00:00"))
        self.assertTrue(module.can_attempt(None, "2026-08-27T10:00:00"))

    def test_generated_html_is_autonomous_and_embeds_platform_features(self):
        module = load_module()
        module.build(BANK_PATH, HTML_PATH)
        html = HTML_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(html, r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://')
        self.assertIn("Экзаменатор Star Building", html)
        self.assertIn("90%", html)
        self.assertIn("1 попытка в месяц", html)
        self.assertIn("Кабинет РОПа", html)
        self.assertIn("localStorage", html)
        self.assertIn("выгрузить результаты", html.lower())
        self.assertIn('id="timeMetric"', html)
        self.assertIn('id="timeText"', html)
        self.assertIn("deadline", html)
        self.assertIn("setInterval", html)
        match = re.search(r'<script id="question-data" type="application/json">(.*?)</script>', html, re.S)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertEqual(102, len(data))


if __name__ == "__main__":
    unittest.main()
