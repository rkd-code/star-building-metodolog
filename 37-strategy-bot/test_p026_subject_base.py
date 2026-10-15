import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p026_subject_base import P026SubjectBase, SubjectBaseIntegrityError


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
        agent_topic = next((t for t in topics if "агент" in t["title"].lower()), None)
        self.assertIsNotNone(agent_topic)
        self.assertTrue(agent_topic["do_not_reopen_in_current_cycle"])

        crm_topic = next((t for t in topics if "битрикс24" in t["title"].lower() or "crm" in t["title"].lower()), None)
        self.assertIsNotNone(crm_topic)

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

    def test_read_verified_document_success_and_sha256(self):
        content = self.base.read_verified_document("КД")
        self.assertIn("Коммерческий директор", content)
        self.assertGreater(len(content), 100)

    def test_read_verified_document_missing_raises(self):
        with tempfile.TemporaryDirectory() as td:
            self.base.DOCUMENT_VERSIONS["КД"] = dict(
                self.base.DOCUMENT_VERSIONS["КД"],
                path=str(Path(td) / "missing.md"),
            )
            with self.assertRaises(FileNotFoundError):
                self.base.read_verified_document("КД")

    def test_read_verified_document_tampered_sha_raises(self):
        with tempfile.TemporaryDirectory() as td:
            tampered = Path(td) / "tampered.md"
            tampered.write_text("Поддельный текст", encoding="utf-8")
            self.base.DOCUMENT_VERSIONS["КД"] = dict(
                self.base.DOCUMENT_VERSIONS["КД"],
                path=str(tampered),
                expected_sha256="0" * 64,
            )
            with self.assertRaises(SubjectBaseIntegrityError):
                self.base.read_verified_document("КД")

    def test_read_verified_document_symlink_raises(self):
        with tempfile.TemporaryDirectory() as td:
            real_file = Path(td) / "real.md"
            real_file.write_text("Реальный файл", encoding="utf-8")
            link_file = Path(td) / "link.md"
            link_file.symlink_to(real_file)
            self.base.DOCUMENT_VERSIONS["КД"] = dict(
                self.base.DOCUMENT_VERSIONS["КД"],
                path=str(link_file),
            )
            with self.assertRaises(SubjectBaseIntegrityError):
                self.base.read_verified_document("КД")

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
        self.assertIn("каталог 76", ctx.lower())
        self.assertIn("рег-001", ctx.lower())
        self.assertIn("договоров №88/89", ctx)
        self.assertIn("не переоткрывать навязчиво", ctx.lower())

    def test_sources_manifest_contains_30_sources(self):
        manifest = self.base.get_source_manifest()
        self.assertEqual(30, len(manifest))
        self.assertTrue(all(s.get("sha256") and s.get("status") and (s.get("bytes") or 0) > 0 for s in manifest))

    def test_verify_all_sources_integrity(self):
        res = self.base.verify_all_sources()
        self.assertTrue(res["ok"])
        self.assertEqual(30, res["verified_count"])


    def test_get_p026_prompt_context_connects_all_30_sources_and_specific_norms(self):
        """S2 / R3: Все 30 источников предметной базы должны быть содержательно подключены."""
        ctx = self.base.get_p026_prompt_context()
        self.assertGreater(len(ctx), 100_000, "Контекст обязан содержать полный подключённый корпус (>100K символов)")

        # Проверка точной нормы МОП -> РОП -> ПТО
        self.assertIn("передаёт запрос в ПТО через РОП", ctx)

        # Проверка наличия утверждённых регламентов РЕГ-001..009
        for reg_num in range(1, 10):
            self.assertIn(f"REG-00{reg_num}", ctx)

        # Проверка оргорегламента 102
        self.assertIn("REG_COMMERCIAL_ORG_V0.1.md", ctx)

        # Безопасность извлечения: отсутствие сырых скриптов, стилей и base64
        self.assertNotIn("<script", ctx.lower())
        self.assertNotIn("<style", ctx.lower())
        self.assertNotIn("data:image/", ctx.lower())
        self.assertNotIn(";base64", ctx.lower())

        # Приоритет решений 107/109
        idx_107 = ctx.find("107-commercial-role-functions-cd-limits-04/OWNER_DECISIONS.md")
        self.assertGreaterEqual(idx_107, 0)

    def test_corpus_reads_all_sources_multiple_times_and_all_norms_present(self):
        """S2 / R3: Проверка фактического чтения содержимого всех 30 источников и отсутствия пропусков норм."""
        from unittest.mock import patch
        original_read = Path.read_bytes
        reads = []
        def trace(p):
            reads.append(str(p))
            return original_read(p)

        with patch.object(Path, "read_bytes", trace):
            ctx = self.base.get_p026_prompt_context()

        manifest_rel = [x["relative_path"] for x in self.base.CANONICAL_SOURCE_MANIFEST]
        counts = {p: reads.count("/home/roman/" + p) for p in manifest_rel}
        validation_only = [p for p, n in counts.items() if n <= 1]
        content_read = [p for p, n in counts.items() if n > 1]

        self.assertEqual([], validation_only, f"Источники, прочитанные только для хеша: {validation_only}")
        self.assertEqual(30, len(content_read), "Все 30 источников должны быть прочитаны более 1 раза (верификация + контент)")

        evidence = []
        for entry in self.base.CANONICAL_SOURCE_MANIFEST:
            p = Path("/home/roman") / entry["relative_path"]
            if "02_УТВЕРЖДЕНО" in str(p) or "101-commercial" in str(p):
                lines = [l.strip() for l in p.read_text().splitlines() if len(l.strip()) > 110 and l.strip() not in ctx and not l.startswith(("#", "|", "<"))]
                evidence.append({"source": entry["relative_path"], "sample_absent": lines[0] if lines else None})
        absent = [e for e in evidence if e["sample_absent"] is not None]
        self.assertEqual([], absent, f"Пропущенные нормы в утверждённых файлах и 101: {absent}")

if __name__ == "__main__":
    unittest.main()
