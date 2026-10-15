import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p026_handler import P026Handler
from p026_storage import P026Storage, JournalCorruptionError
from p026_subject_base import P026SubjectBase, SubjectBaseIntegrityError
from unittest.mock import patch


class P026HandlerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = P026Storage(base_dir=self.temp_dir.name)
        self.subject_base = P026SubjectBase()
        self.handler = P026Handler(storage=self.storage, subject_base=self.subject_base)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ambiguous_replies_are_rejected(self):
        ambiguous_cases = [
            "да", "Да", "ок", "ОК", "ок.", "согласен", "хорошо", "+", "yes", "ага", "подтверждаю",
            "да согласен", "ок хорошо", "всё верно", "согласен с этим", "ок принято", "подтверждаю всё",
            "да я согласен", "я согласен", "подтверждаю всё вышеизложенное", "согласен со всем",
            "одобряю вышесказанное", "полностью поддерживаю",
        ]
        for reply in ambiguous_cases:
            with self.subTest(reply=reply):
                valid, msg = self.handler.validate_decision_input(reply)
                self.assertFalse(valid, f"Ответ '{reply}' должен быть отклонён")
                self.assertTrue("неоднозначн" in msg.lower() or "согласие" in msg.lower() or "краткая" in msg.lower())

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
            user_id=123,
            chat_id=456,
        )
        self.assertTrue(res["ok"])
        self.assertIn("зафиксировано", res["message"].lower())
        self.assertEqual(decision_text, res["decision"]["exact_text"])
        self.assertEqual("Пределы скидок и полномочий", res["decision"]["question_context"])

        # Проверка изоляции в хранилище
        saved = self.storage.list_decisions(user_id=123, chat_id=456)
        self.assertEqual(1, len(saved))
        self.assertEqual(decision_text, saved[0]["exact_text"])

    def test_project_status_output(self):
        self.handler.record_owner_decision(
            author="Корж И.С.",
            text="Утвердить лимит скидки РОП до 12.5%",
            user_id=123,
            chat_id=456,
        )
        status_text = self.handler.handle_project_command(user_id=123, chat_id=456)
        self.assertIn("P-026", status_text)
        self.assertIn("Коммерческий департамент", status_text)
        self.assertIn("v0.6", status_text)
        self.assertIn("v0.3", status_text)
        self.assertIn("15%", status_text)
        self.assertIn("1 млрд тенге", status_text)
        self.assertIn("Зафиксированные решения текущего пользователя", status_text)
        self.assertIn("12.5%", status_text)

        # Другой пользователь не видит эти решения
        other_status = self.handler.handle_project_command(user_id=999, chat_id=456)
        self.assertNotIn("Зафиксированные решения текущего пользователя", other_status)

    def test_export_draft_kd(self):
        export_res = self.handler.export_draft(doc_type="kd", author="Корж И.С.", user_id=123)
        self.assertTrue(export_res["ok"])
        draft = export_res["draft"]
        self.assertTrue(Path(draft["path"]).is_file())
        self.assertEqual(1, draft["version"])
        self.assertIn("v1", draft["filename"])

        content = Path(draft["path"]).read_text(encoding="utf-8")
        self.assertIn("DRAFT ARTIFACT", content)
        self.assertIn("Коммерческий директор", content)

    def test_export_draft_missing_source_fails_closed(self):
        self.subject_base.DOCUMENT_VERSIONS["КД"] = dict(
            self.subject_base.DOCUMENT_VERSIONS["КД"],
            path=str(Path(self.temp_dir.name) / "nonexistent.md"),
        )
        res = self.handler.export_draft("kd", user_id=123)
        self.assertFalse(res["ok"], "При отсутствующем источнике экспорт обязан завершиться отказом")
        self.assertIsNone(res.get("draft"))
        self.assertIn("отказ", res["error"].lower())

    def test_handle_project_manifest_failure_fails_closed(self):
        """R3 / F6: Отказ команды /project при нарушении целостности манифеста источников."""
        with patch.object(self.subject_base, "verify_all_sources", side_effect=SubjectBaseIntegrityError("TAMPERED")):
            status = self.handler.handle_project_command(user_id=123, chat_id=123)
            self.assertEqual("", status, "При сбое целостности манифеста статус проекта должен быть пустым (fail-closed)")

    def test_export_draft_manifest_failure_fails_closed(self):
        """R3 / F6: Отказ экспорта черновика при нарушении целостности манифеста источников."""
        with patch.object(self.subject_base, "verify_all_sources", side_effect=SubjectBaseIntegrityError("TAMPERED")):
            res = self.handler.export_draft("kd", user_id=123, chat_id=123)
            self.assertFalse(res["ok"], "При сбое манифеста экспорт обязан завершаться отказом")

    def test_export_draft_isolates_user_decisions(self):
        # Пользователь 1 фиксирует приватное решение
        self.handler.record_owner_decision(
            author="User 1",
            text="СЕКРЕТНОЕ_РЕШЕНИЕ_ПОЛЬЗОВАТЕЛЯ_1: скидка 7%",
            user_id=1,
        )

        # Пользователь 2 экспортирует черновик
        export_res = self.handler.export_draft(doc_type="kd", author="User 2", user_id=2)
        self.assertTrue(export_res["ok"])

        draft_content = Path(export_res["draft"]["path"]).read_text(encoding="utf-8")
        self.assertNotIn(
            "СЕКРЕТНОЕ_РЕШЕНИЕ_ПОЛЬЗОВАТЕЛЯ_1",
            draft_content,
            "Чужое решение не должно попадать в черновик другого пользователя!",
        )

    def test_s3_agreement_variations_without_pending_proposal_are_rejected(self):
        """S3 / R5: Вариации согласий без pending proposal обязаны отклоняться."""
        agreement_phrases = [
            "да я согласен",
            "я согласен",
            "подтверждаю всё вышеизложенное",
            "подтверждаю всё сказанное ранее",
            "поддерживаю ваше предложение",
            "согласен с предложенным регламентом",
            "одобряю предложенный вариант",
        ]
        for phrase in agreement_phrases:
            with self.subTest(phrase=phrase):
                res = self.handler.record_owner_decision("A", phrase, user_id=123, chat_id=123)
                self.assertFalse(res["ok"], f"Фраза согласия '{phrase}' не должна быть принята без pending proposal")
                self.assertIsNone(res["decision"])
                self.assertIn("согласие", res["message"].lower())

        # А контрольная конкретная норма принимается
        valid_res = self.handler.record_owner_decision("A", "Утвердить лимит скидки РОП до 12.5%", user_id=123, chat_id=123)
        self.assertTrue(valid_res["ok"])
        self.assertIsNotNone(valid_res["decision"])

    def test_s3_two_step_pending_proposal_confirmation(self):
        """S3 / R5: Двухшаговый механизм: подтверждение согласует точное ранее показанное предложение."""
        self.handler.set_pending_proposal(
            user_id=123, chat_id=123,
            proposal_text="Утвердить регламент РОП v0.3",
            question_context="Регламент РОП",
            proposal_id="prop_101",
        )
        res = self.handler.record_owner_decision("A", "подтверждаю", user_id=123, chat_id=123)
        self.assertTrue(res["ok"])
        self.assertEqual("Утвердить регламент РОП v0.3", res["decision"]["exact_text"])

    def test_t1_pseudo_agreements_without_pending_are_rejected(self):
        """T1 / S3: Без предложения запрещено сохранять псевдосогласия как решения."""
        pseudo_agreements = [
            "Всё устраивает",
            "Возражений не имею",
            "Именно так и поступим",
            "Не возражаю",
        ]
        for phrase in pseudo_agreements:
            with self.subTest(phrase=phrase):
                res = self.handler.record_owner_decision("A", phrase, user_id=123, chat_id=123)
                self.assertFalse(res["ok"], f"Фраза '{phrase}' не должна приниматься как самостоятельное решение")
                self.assertIsNone(res["decision"])

        # Структурированная норма принимается
        res_valid = self.handler.record_owner_decision("A", "Утвердить лимит скидки РОП до 12.5%", user_id=123, chat_id=123)
        self.assertTrue(res_valid["ok"])
        self.assertIsNotNone(res_valid["decision"])

    def test_t1_pending_proposal_rejects_empty_dots_disagreement_and_conditional(self):
        """T1 / S3: Пустая строка, точки, отказ и условные фразы не должны утверждать норму."""
        invalid_inputs = ["", "...", "Не согласен", "Подтверждаю, но только после уточнения"]
        for text in invalid_inputs:
            with self.subTest(text=text):
                self.handler.set_pending_proposal(
                    user_id=123, chat_id=123,
                    proposal_text="Утвердить лимит скидки РОП до 12.5%",
                    proposal_id="specific-Q1",
                )
                res = self.handler.record_owner_decision("A", text, question_context="OTHER QUESTION", user_id=123, chat_id=123)
                self.assertFalse(res["ok"], f"Ввод '{text}' не должен приводить к утверждению нормы")
                self.assertIsNone(res["decision"])
                # Pending proposal не должен теряться при невалидном вводе
                self.assertIsNotNone(self.handler.get_pending_proposal(123, 123))

    def test_t1_proposal_id_binding_foreign_and_reuse_rejection(self):
        """T1 / S3: Привязка подтверждения к proposal_id, отказ для чужого и повторного ID."""
        self.handler.set_pending_proposal(
            user_id=123, chat_id=123,
            proposal_text="Утвердить норматив РОП 4 часа",
            proposal_id="prop_fixed_42",
            question_context="Нормативы РОП",
        )
        # 1. Неверный proposal_id
        res_wrong = self.handler.record_owner_decision("A", "подтверждаю", user_id=123, chat_id=123, proposal_id="wrong_id")
        self.assertFalse(res_wrong["ok"])
        self.assertIn("неверный", res_wrong["message"].lower())

        # 2. Чужой user_id
        res_foreign = self.handler.record_owner_decision("B", "подтверждаю", user_id=999, chat_id=123, proposal_id="prop_fixed_42")
        self.assertFalse(res_foreign["ok"])

        # 3. Успешное подтверждение владельцем с правильным proposal_id
        res_ok = self.handler.record_owner_decision("A", "подтверждаю", user_id=123, chat_id=123, proposal_id="prop_fixed_42")
        self.assertTrue(res_ok["ok"])
        self.assertEqual("Утвердить норматив РОП 4 часа", res_ok["decision"]["exact_text"])
        # После успешной записи pending предложение сброшено
        self.assertIsNone(self.handler.get_pending_proposal(123, 123))

        # 4. Повторное подтверждение того же ID отклоняется
        res_reuse = self.handler.record_owner_decision("A", "подтверждаю", user_id=123, chat_id=123, proposal_id="prop_fixed_42")
        self.assertFalse(res_reuse["ok"])
        self.assertIn("уже", res_reuse["message"].lower())

    def test_t1_pending_preserved_if_storage_fails(self):
        """T1 / S3: Pending proposal не теряется, если запись в хранилище завершилась ошибкой."""
        self.handler.set_pending_proposal(user_id=123, chat_id=123, proposal_text="Norm", proposal_id="p_err")
        with patch.object(self.storage, "record_decision", side_effect=JournalCorruptionError("DISK_FAIL")):
            res = self.handler.record_owner_decision("A", "подтверждаю", user_id=123, chat_id=123, proposal_id="p_err")
            self.assertFalse(res["ok"])
            self.assertIsNotNone(self.handler.get_pending_proposal(123, 123), "Pending не должен сбрасываться при ошибке записи")

if __name__ == "__main__":
    unittest.main()
