import hashlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from p026_storage import P026Storage, PathTraversalError, get_default_storage_dir


class P026SecurityTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = P026Storage(base_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_source_catalogs_sha256_unmodified(self):
        """Проверяет неизменность SHA-256 файлов во всех исходных каталогах."""
        baseline_file = Path("/tmp/baseline_sha256_sources.txt")
        if not baseline_file.exists():
            self.skipTest("Файл базовых контрольных сумм /tmp/baseline_sha256_sources.txt не найден")

        mismatches = []
        checked = 0
        for line in baseline_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            expected_hash, filepath = line.split("  ", 1)
            p = Path(filepath)
            self.assertTrue(p.exists(), f"Исходный файл отсутствует: {p}")
            current_hash = hashlib.sha256(p.read_bytes()).hexdigest()
            if current_hash != expected_hash:
                mismatches.append(f"{p}: expected {expected_hash}, got {current_hash}")
            checked += 1

        self.assertGreater(checked, 0)
        self.assertEqual([], mismatches, f"Обнаружены несанкционированные изменения в исходных файлах: {mismatches}")

    def test_path_traversal_attack_matrix(self):
        """Проверяет блокировку всех векторов обхода каталогов."""
        attack_payloads = [
            "../secret.txt",
            "..\\windows_traversal.txt",
            "....//....//etc/shadow",
            "nested/../../etc/passwd",
            "/absolute/root/file",
            "~/home/file",
            "file\x00with_null.md",
            "../../.ssh/id_rsa",
            "drafts/../../strategy_bot.py",
            "./../draft",
            "..",
            "...",
        ]
        for payload in attack_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(PathTraversalError):
                    self.storage.save_draft(payload, "malicious payload")
                with self.assertRaises(PathTraversalError):
                    self.storage.read_draft(payload)

    def test_symlink_attack_rejected(self):
        """Проверяет невозможность чтения или создания через символические ссылки."""
        secret_file = Path(self.temp_dir.name) / "secret.env"
        secret_file.write_text("API_SECRET_KEY=12345", encoding="utf-8")

        symlink_target = self.storage.drafts_dir / "symlink_attack.md"
        try:
            symlink_target.symlink_to(secret_file)
            with self.assertRaises(PathTraversalError):
                self.storage.read_draft("symlink_attack.md")
        finally:
            if symlink_target.is_symlink():
                symlink_target.unlink()

    def test_parent_directory_symlink_attack_rejected_fail_closed(self):
        """Проверяет блокировку symlink на уровне родительских папок drafts и decisions (F1)."""
        outside = Path(self.temp_dir.name) / "outside"
        outside.mkdir()

        # Попытка смонтировать drafts через symlink
        spoofed_base1 = Path(self.temp_dir.name) / "spoofed1"
        spoofed_base1.mkdir()
        (spoofed_base1 / "drafts").symlink_to(outside, target_is_directory=True)

        with self.assertRaises(PathTraversalError):
            P026Storage(base_dir=spoofed_base1)

        # Попытка смонтировать decisions через symlink
        spoofed_base2 = Path(self.temp_dir.name) / "spoofed2"
        spoofed_base2.mkdir()
        (spoofed_base2 / "decisions").symlink_to(outside, target_is_directory=True)

        with self.assertRaises(PathTraversalError):
            P026Storage(base_dir=spoofed_base2)

    def test_no_hardcoded_secrets_or_tokens(self):
        """Проверяет отсутствие токенов Telegram и паролей в компоненте 37-strategy-bot."""
        token_pattern = re.compile(r"\d{8,12}:[A-Za-z0-9_-]{30,}")
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".json", ".template", ".service"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                matches = token_pattern.findall(text)
                self.assertEqual([], matches, f"Найден токен в файле {path}: {matches}")

    def test_storage_isolated_from_git_and_prod(self):
        """Хранилище по умолчанию расположено изолированно вне репозитория и вне prod."""
        # Вызов с create_dirs=False не создаёт каталогов в живом окружении
        default_dir = P026Storage(create_dirs=False).base_dir
        self.assertNotIn("/star-building-metodolog", str(default_dir))
        self.assertNotIn("/etc", str(default_dir))
        self.assertNotIn("/var", str(default_dir))


if __name__ == "__main__":
    unittest.main()
