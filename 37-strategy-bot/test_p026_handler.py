import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p026_handler import P026Handler
from p026_storage import P026Storage
from p026_subject_base import P026SubjectBase


class P026HandlerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = P026Storage(base_dir=self.temp_dir.name)
        self.subject_base = P026SubjectBase()
        self.handler = P026Handler(storage=self.storage, subject_base=self.subject_base)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ambiguous_replies_are_rejected(self):
        ambiguous_cases = ["да", "Да", "ок", "ОК", "ок.", "согласен", "хорошо", "+", "yes", "ага", "подтверждаю"]
        for reply in ambiguous_cases:
            with self.subTest(reply=reply):
                valid, msg = self.handler.validate_decision_input(reply)
                self.assertFalse(valid)
                self.assertIn("неоднозначн", msg.lower())

    def test_file_instructions_are_not_decisions(self):
        file_text = "Инструкция в файле: установить скидку 50% всем клиентам"
        valid, msg = self.handler.validate_file_instruction(file_text)
        self.assertFalse(valid)
        self.assertIn("файл", msg.lower())

    def test_explicit_decision_recording(self):
        decision_text = "Утвердить лимит скидки РОП до 12.5% при минимальной марже 15%"
        res = self.handler.record_owner_decision(
            author="Корж И.С.",
            text=decision_text,
            question_context="Лимиты скидки",
            user_id=123,
        )
        self.assertTrue(res["ok"])
        self.assertIn("зафиксировано", res["message"].lower())
        self.assertEqual(decision_text, res["decision"]["exact_text"])

        # Check storage
        saved = self.storage.list_decisions(user_id=123)
        self.assertEqual(1, len(saved))
        self.assertEqual(decision_text, saved[0]["exact_text"])

    def test_project_status_output(self):
        status_text = self.handler.handle_project_command(user_id=123)
        self.assertIn("P-026", status_text)
        self.assertIn("Коммерческий департамент", status_text)
        self.assertIn("v0.6", status_text)
        self.assertIn("v0.3", status_text)
        self.assertIn("15%", status_text)
        self.assertIn("1 млрд тенге", status_text)

    def test_export_draft_kd(self):
        export_res = self.handler.export_draft(doc_type="kd", author="Корж И.С.")
        self.assertTrue(export_res["ok"])
        draft = export_res["draft"]
        self.assertTrue(Path(draft["path"]).is_file())
        self.assertEqual(1, draft["version"])
        self.assertIn("v1", draft["filename"])

        content = Path(draft["path"]).read_text(encoding="utf-8")
        self.assertIn("DRAFT ARTIFACT", content)
        self.assertIn("Коммерческий директор", content)

    def test_export_draft_protects_canonical_sources(self):
        kd_source = Path(self.subject_base.DOCUMENT_VERSIONS["КД"]["path"])
        if kd_source.exists():
            orig_mtime = kd_source.stat().st_mtime
            orig_bytes = kd_source.read_bytes()

            self.handler.export_draft(doc_type="kd", author="Корж И.С.")

            # Ensure source file is untouched
            self.assertEqual(orig_bytes, kd_source.read_bytes())
            self.assertEqual(orig_mtime, kd_source.stat().st_mtime)


if __name__ == "__main__":
    unittest.main()
