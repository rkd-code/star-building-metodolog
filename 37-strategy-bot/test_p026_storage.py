import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p026_storage import P026Storage, PathTraversalError


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
        )
        self.assertEqual("Корж И.С.", dec["author"])
        self.assertEqual("КД до 20%, маржа не менее 15%", dec["exact_text"])
        self.assertTrue(dec["id"].startswith("dec_"))
        self.assertTrue(dec["timestamp"])

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
        # Create a new storage instance pointing to the same directory
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
        )
        self.assertTrue(draft1["path"].exists())
        self.assertEqual(1, draft1["version"])
        self.assertIn("v1", draft1["filename"])

        draft2 = self.storage.save_draft(
            doc_name="KD_FUNCTIONAL",
            content="# Версия 2\nОбновленный текст",
            author="Пондер",
        )
        self.assertTrue(draft2["path"].exists())
        self.assertEqual(2, draft2["version"])
        self.assertIn("v2", draft2["filename"])
        self.assertNotEqual(draft1["path"], draft2["path"])

        # Check drafts listing
        drafts = self.storage.list_drafts("KD_FUNCTIONAL")
        self.assertEqual(2, len(drafts))
        self.assertEqual(2, drafts[0]["version"])  # Latest first
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

    def test_rejects_symlinks(self):
        # Create a real file outside
        outside_file = self.storage_path.parent / "external.txt"
        outside_file.write_text("external content", encoding="utf-8")

        # Create a symlink inside drafts_dir pointing outside
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


if __name__ == "__main__":
    unittest.main()
