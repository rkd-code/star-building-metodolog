import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("ensure_repo_docs.py")


def load_module():
    spec = importlib.util.spec_from_file_location("ensure_repo_docs", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()


class RepositoryDocumentationTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Test")
        git(repo, "remote", "add", "origin", "git@github.com:owner/example.git")
        (repo / "README.md").write_text("# Пример проекта\n\nОписание проекта.\n", encoding="utf-8")
        (repo / "src").mkdir()
        (repo / "src" / "app.py").write_text('"""Основной модуль приложения."""\nprint("ok")\n', encoding="utf-8")
        (repo / "данные").mkdir()
        (repo / "данные" / "описание.md").write_text("# Описание данных\n", encoding="utf-8")
        git(repo, "add", "README.md", "src/app.py", "данные/описание.md")
        return repo

    def test_bootstrap_creates_required_context_and_linked_manifest(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            result = module.ensure_repository(repo, stage=True)
            self.assertTrue(result["updated"])
            for name in module.REQUIRED_FILES:
                self.assertTrue((repo / name).exists(), name)
            manifest = json.loads((repo / "PROJECT_MANIFEST.json").read_text(encoding="utf-8"))
            app = next(item for item in manifest["files"] if item["path"] == "src/app.py")
            self.assertEqual("Основной модуль приложения.", app["description"])
            self.assertEqual("https://github.com/owner/example/blob/main/src/app.py", app["github_url"])
            unicode_item = next(item for item in manifest["files"] if item["name"] == "описание.md")
            self.assertEqual("данные/описание.md", unicode_item["path"])
            self.assertNotIn("\\320", unicode_item["github_url"])
            self.assertIn("PROJECT_CONTEXT.md", git(repo, "diff", "--cached", "--name-only"))

    def test_check_detects_stale_structure_after_new_staged_file(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            module.ensure_repository(repo, stage=True)
            git(repo, "commit", "-m", "initial")
            (repo / "src" / "new.py").write_text('"""Новая функция."""\n', encoding="utf-8")
            git(repo, "add", "src/new.py")
            self.assertFalse(module.check_repository(repo)["ok"])
            module.ensure_repository(repo, stage=True)
            self.assertTrue(module.check_repository(repo)["ok"])
            structure = (repo / "PROJECT_STRUCTURE.md").read_text(encoding="utf-8")
            self.assertIn("src/new.py", structure)

    def test_source_hash_ignores_generated_document_changes(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(Path(temp))
            module.ensure_repository(repo, stage=True)
            first = module.source_tree_hash(repo)
            context = repo / "PROJECT_CONTEXT.md"
            context.write_text(context.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            git(repo, "add", "PROJECT_CONTEXT.md")
            self.assertEqual(first, module.source_tree_hash(repo))


if __name__ == "__main__":
    unittest.main()
