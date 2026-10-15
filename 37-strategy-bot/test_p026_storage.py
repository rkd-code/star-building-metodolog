import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p026_storage import JournalCorruptionError, P026Storage, PathTraversalError


class P026StorageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.temp_dir.name)
        self.storage = P026Storage(base_dir=self.storage_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_creates_isolated_directories(self):
        self.assertTrue(self.storage.decisions_dir.is_dir())
        self.assertTrue(self.storage.drafts_dir.is_dir())

    def test_record_and_retrieve_decision(self):
        dec = self.storage.record_decision(
            author="Корж И.С.",
            question_context="Пределы скидок КД",
            exact_text="КД до 20%, маржа не менее 15%",
            user_id=12345,
            chat_id=98765,
        )
        self.assertEqual("Корж И.С.", dec["author"])
        self.assertEqual("КД до 20%, маржа не менее 15%", dec["exact_text"])
        self.assertTrue(dec["id"].startswith("dec_"))
        self.assertTrue(dec["timestamp"])
        self.assertEqual(12345, dec["user_id"])
        self.assertEqual(98765, dec["chat_id"])

        decisions = self.storage.list_decisions(user_id=12345)
        self.assertEqual(1, len(decisions))
        self.assertEqual(dec["id"], decisions[0]["id"])

    def test_persistence_across_instances(self):
        self.storage.record_decision(
            author="Корж И.С.",
            question_context="Срок первого ответа РОП",
            exact_text="В течение 3х рабочих часов",
            user_id=54321,
        )
        new_storage = P026Storage(base_dir=self.storage_path)
        decisions = new_storage.list_decisions(user_id=54321)
        self.assertEqual(1, len(decisions))
        self.assertEqual("В течение 3х рабочих часов", decisions[0]["exact_text"])

    def test_isolation_between_users(self):
        self.storage.record_decision(author="User A", question_context="Q1", exact_text="Ans A", user_id=100)
        self.storage.record_decision(author="User B", question_context="Q2", exact_text="Ans B", user_id=200)

        user_a_decisions = self.storage.list_decisions(user_id=100)
        user_b_decisions = self.storage.list_decisions(user_id=200)

        self.assertEqual(1, len(user_a_decisions))
        self.assertEqual("Ans A", user_a_decisions[0]["exact_text"])
        self.assertEqual(1, len(user_b_decisions))
        self.assertEqual("Ans B", user_b_decisions[0]["exact_text"])

    def test_versioned_draft_saving(self):
        draft1 = self.storage.save_draft(
            doc_name="KD_FUNCTIONAL",
            content="# Версия 1\nТекст",
            author="Пондер",
            user_id=123,
        )
        self.assertTrue(draft1["path"].exists())
        self.assertEqual(1, draft1["version"])
        self.assertIn("v1", draft1["filename"])

        draft2 = self.storage.save_draft(
            doc_name="KD_FUNCTIONAL",
            content="# Версия 2\nОбновленный текст",
            author="Пондер",
            user_id=123,
        )
        self.assertTrue(draft2["path"].exists())
        self.assertEqual(2, draft2["version"])
        self.assertIn("v2", draft2["filename"])
        self.assertNotEqual(draft1["path"], draft2["path"])

        drafts = self.storage.list_drafts("KD_FUNCTIONAL")
        self.assertEqual(2, len(drafts))
        self.assertEqual(2, drafts[0]["version"])
        self.assertEqual(1, drafts[1]["version"])

    def test_path_traversal_protection_in_draft_name(self):
        traversal_attempts = [
            "../secret.txt",
            "../../etc/passwd",
            "/absolute/path/file.md",
            "folder/../../outside.md",
            "doc\x00null.md",
            "nested/file.md",
        ]
        for bad_name in traversal_attempts:
            with self.subTest(bad_name=bad_name):
                with self.assertRaises(PathTraversalError):
                    self.storage.save_draft(bad_name, "content")

    def test_rejects_symlinks_in_files(self):
        outside_file = self.storage_path.parent / "external.txt"
        outside_file.write_text("external content", encoding="utf-8")

        symlink_path = self.storage.drafts_dir / "sneaky_symlink.md"
        try:
            symlink_path.symlink_to(outside_file)
            with self.assertRaises(PathTraversalError):
                self.storage.read_draft("sneaky_symlink.md")
        finally:
            if symlink_path.is_symlink():
                symlink_path.unlink()
            if outside_file.exists():
                outside_file.unlink()

    def test_rejects_symlink_parents_fail_closed(self):
        outside = Path(self.temp_dir.name) / "outside"
        outside.mkdir()
        symlink_base = Path(self.temp_dir.name) / "symlink_base"
        symlink_base.mkdir()

        (symlink_base / "drafts").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(PathTraversalError):
            P026Storage(base_dir=symlink_base)

        dec_base = Path(self.temp_dir.name) / "dec_base"
        dec_base.mkdir()
        (dec_base / "decisions").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(PathTraversalError):
            P026Storage(base_dir=dec_base)

    def test_concurrent_decisions_preserve_all_updates(self):
        barrier = threading.Barrier(2)
        original_read = self.storage._read_decisions_raw

        def synced_read():
            data = original_read()
            try:
                barrier.wait(timeout=2)
            except threading.BrokenBarrierError:
                pass
            return data

        self.storage._read_decisions_raw = synced_read
        threads = [
            threading.Thread(
                target=self.storage.record_decision,
                args=("Автор", "Вопрос", f"Решение {i}", i),
            )
            for i in [1, 2]
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.storage._read_decisions_raw = original_read

        saved = self.storage.list_decisions()
        self.assertEqual(2, len(saved), f"Ожидалось 2 сохранённых решения, фактически {len(saved)}")

    def test_concurrent_draft_saving_creates_unique_versions(self):
        results = []

        def save_work(i):
            info = self.storage.save_draft("CONCURRENT_DOC", f"Content {i}", f"Author {i}")
            results.append(info)

        t1 = threading.Thread(target=save_work, args=(1,))
        t2 = threading.Thread(target=save_work, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(2, len(results))
        versions = {r["version"] for r in results}
        self.assertEqual({1, 2}, versions, f"Ожидались версии 1 и 2, получено {versions}")
        paths = {str(r["path"]) for r in results}
        self.assertEqual(2, len(paths), "Черновики не должны перезаписывать один и тот же путь")

    def test_corrupted_journal_fails_closed_and_creates_quarantine(self):
        self.storage.record_decision("Автор", "Вопрос", "Ответ 1", user_id=1)
        self.storage.decisions_file.write_text("{broken json payload", encoding="utf-8")

        with self.assertRaises(JournalCorruptionError):
            self.storage.record_decision("Автор", "Вопрос", "Ответ 2", user_id=1)

        baks = list(self.storage.decisions_dir.glob("decisions_corrupted_*.json.bak"))
        self.assertGreater(len(baks), 0, "Карантинная копия поврежденного журнала должна быть создана")
        self.assertIn("{broken", baks[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
