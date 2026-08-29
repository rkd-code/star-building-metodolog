import importlib.util
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("export_chat_history.py")


def load_module():
    spec = importlib.util.spec_from_file_location("export_chat_history", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_db(path: Path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY, source TEXT, title TEXT, display_name TEXT,
            started_at REAL, profile_name TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
            timestamp REAL, active INTEGER, display_kind TEXT
        );
        """
    )
    db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)", ("s1", "telegram", "Диалог", "Star", 0, "default"))
    db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (1, "s1", "user", "Вопрос", 1787281200, 1, None))
    db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (2, "s1", "assistant", "Ответ", 1787281260, 1, None))
    db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (3, "s1", "tool", "Служебное", 1787281270, 1, None))
    db.commit()
    db.close()


class ExportTests(unittest.TestCase):
    def test_exports_user_and_assistant_into_month_folder(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "state.db"
            create_db(db)
            archive = root / "archive"
            result = module.export_history(
                database_specs=[(db, "default")],
                archive_root=archive,
                timezone_name="Asia/Almaty",
                today=date(2026, 8, 21),
                discovered_profiles={"default", "developer"},
            )
            default_file = archive / "2026-08" / "2026-08-21__default.txt"
            developer_file = archive / "2026-08" / "2026-08-21__developer.txt"
            self.assertTrue(default_file.exists())
            self.assertTrue(developer_file.exists())
            text = default_file.read_text(encoding="utf-8")
            self.assertIn("Вопрос", text)
            self.assertIn("Ответ", text)
            self.assertNotIn("Служебное", text)
            self.assertIn("Профиль: default", text)
            self.assertIn("Часовой пояс: Asia/Almaty", text)
            self.assertIn("Переписки за этот день нет", developer_file.read_text(encoding="utf-8"))
            self.assertEqual(2, result["files_written"])

    def test_malformed_session_title_falls_back_to_display_name(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db_path = root / "state.db"
            create_db(db_path)
            db = sqlite3.connect(db_path)
            db.execute("UPDATE sessions SET title = ?, display_name = ?", ('{\"title', "Star building"))
            db.commit()
            db.close()
            messages = module.read_database(db_path, "default", module.ZoneInfo("Asia/Almaty"))
            self.assertEqual("Star building", messages[0]["title"])

    def test_repeated_export_overwrites_without_duplicates(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "state.db"
            create_db(db)
            archive = root / "archive"
            kwargs = dict(database_specs=[(db, "default")], archive_root=archive,
                          timezone_name="Asia/Almaty", today=date(2026, 8, 21),
                          discovered_profiles={"default"})
            module.export_history(**kwargs)
            module.export_history(**kwargs)
            text = (archive / "2026-08" / "2026-08-21__default.txt").read_text(encoding="utf-8")
            self.assertEqual(1, text.count("Вопрос"))
            self.assertEqual(1, text.count("Ответ"))


if __name__ == "__main__":
    unittest.main()
