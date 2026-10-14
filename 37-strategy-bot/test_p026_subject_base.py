import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p026_subject_base import P026SubjectBase


class P026SubjectBaseTest(unittest.TestCase):
    def setUp(self):
        self.base = P026SubjectBase()

    def test_discount_limits(self):
        limits = self.base.get_discount_limits()
        self.assertEqual(5.0, limits["МОП"])
        self.assertEqual(5.0, limits["Старший МОП"])
        self.assertEqual(12.5, limits["РОП"])
        self.assertEqual(20.0, limits["КД"])
        self.assertEqual(30.0, limits["ОД"])
        self.assertEqual("Свыше 30%", limits["ГД"])

    def test_margin_rule(self):
        rule = self.base.get_margin_rule()
        self.assertEqual(15.0, rule["min_margin_pct"])
        self.assertTrue(rule["below_min_requires_gd"])
        self.assertIn("15%", rule["description"])
        self.assertIn("ГД", rule["description"])

    def test_strategic_deal_threshold(self):
        threshold = self.base.get_strategic_deal_threshold()
        self.assertEqual(1_000_000_000, threshold["amount_tenge"])
        self.assertFalse(threshold["is_lead_minimum_check"])
        self.assertIn("1 млрд тенге", threshold["description"])
        self.assertIn("НЕ минимальный чек лида", threshold["description"])

    def test_rop_answers_109(self):
        rop = self.base.get_rop_rules()
        self.assertEqual(3, rop["first_response_work_hours"])
        self.assertEqual(3, rop["deal_stall_base_days"])
        self.assertEqual(3, rop["pto_response_max_days"])
        self.assertEqual("85–90%", rop["forecast_accuracy_hot"])
        self.assertEqual("50%", rop["forecast_accuracy_warm"])
        self.assertFalse(rop["can_suspend_agent_unilaterally"])
        self.assertTrue(rop["secondary_interview"])
        self.assertIn("инициатив", rop["hr_authority"].lower())

    def test_deferred_topics(self):
        topics = self.base.get_deferred_topics()
        # Must include question 8 about agents
        agent_topic = next((t for t in topics if "агент" in t["title"].lower()), None)
        self.assertIsNotNone(agent_topic)
        self.assertTrue(agent_topic["do_not_reopen_in_current_cycle"])

        # Must include CRM fields
        crm_topic = next((t for t in topics if "битрикс24" in t["title"].lower() or "crm" in t["title"].lower()), None)
        self.assertIsNotNone(crm_topic)

        # Must include Google form
        gform_topic = next((t for t in topics if "гугл" in t["title"].lower() or "google" in t["title"].lower()), None)
        self.assertIsNotNone(gform_topic)

    def test_document_versions(self):
        docs = self.base.get_document_versions()
        self.assertEqual("v0.6", docs["КД"]["version"])
        self.assertEqual("v0.3", docs["РОП"]["version"])
        self.assertEqual("v0.1", docs["Старший МОП"]["version"])
        self.assertEqual("v0.1", docs["МОП"]["version"])
        self.assertEqual("v0.1", docs["Лидоруб"]["version"])
        self.assertEqual("v0.1", docs["Оргструктура КД"]["version"])

    def test_format_project_status(self):
        status_text = self.base.format_project_status()
        self.assertIn("P-026", status_text)
        self.assertIn("Коммерческий департамент", status_text)
        self.assertIn("v0.6", status_text)
        self.assertIn("v0.3", status_text)
        self.assertIn("12,5%", status_text.replace(".", ","))
        self.assertIn("15%", status_text)
        self.assertIn("1 млрд", status_text)
        self.assertIn("вопрос №8", status_text.lower())

    def test_prompt_context_includes_critical_rules(self):
        ctx = self.base.get_p026_prompt_context()
        self.assertIn("1 млрд", ctx)
        self.assertIn("НЕ минимальный чек", ctx)
        self.assertIn("15%", ctx)
        self.assertIn("не переоткрывать навязчиво", ctx.lower())


if __name__ == "__main__":
    unittest.main()
