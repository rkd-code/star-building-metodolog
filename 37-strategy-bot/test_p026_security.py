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

    def test_ancestor_symlink_attack_rejected_fail_closed(self):
        """R1 / F1: Проверяет блокировку symlink на любом уровне предков (выше base.parent)."""
        p = Path(self.temp_dir.name)
        real = p / "real"
        real.mkdir()
        link = p / "link"
        link.symlink_to(real, target_is_directory=True)

        with self.assertRaises(PathTraversalError):
            s = P026Storage(link / "a" / "b" / "store")
            s.record_decision("A", "Q", "EXTERNAL_WRITE", 123, 123)

        escaped = (real / "a/b/store/decisions/decisions.json").exists()
        self.assertFalse(escaped, "Файл не должен создаваться за пределами symlink-границы предков")

    def test_side_effects_before_refusal_prevented(self):
        """R1 / F1: Проверяет отсутствие побочных каталогов/файлов при отказе."""
        p = Path(self.temp_dir.name)
        real = p / "real_side_effects"
        real.mkdir()
        link2 = p / "link2"
        link2.symlink_to(real, target_is_directory=True)

        with self.assertRaises(PathTraversalError):
            P026Storage(link2 / "created_before_refusal")

        self.assertFalse((real / "created_before_refusal").exists(), "Каталог не должен создаваться до проверки symlink")

    def test_lock_symlink_attack_rejected_fail_closed(self):
        """R1 / F1: Проверяет блокировку symlink на lock-файле (.decisions.lock) с сохранением жертвы."""
        p = Path(self.temp_dir.name)
        s = P026Storage(p / "store_lock_test")
        victim = p / "outside_lock"
        victim.write_text("UNTOUCHED", encoding="utf-8")

        s.decisions_lock_file.unlink()
        s.decisions_lock_file.symlink_to(victim)

        with self.assertRaises(PathTraversalError):
            s.record_decision("A", "Q", "LOCK_FOLLOWED", 123, 123)
        self.assertEqual("UNTOUCHED", victim.read_text(encoding="utf-8"), "Жертва lock-атаки должна остаться нетронутой")

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

    def test_t2_rollback_procedure_tampered_backup_fails_closed_without_mutations(self):
        """T2 / S4: Процедура отката из DEPLOYMENT_PLAN.md на повреждённом бэкапе обязана завершаться fail-closed ДО любых мутаций."""
        import subprocess
        import json
        plan_path = ROOT / "DEPLOYMENT_PLAN.md"
        self.assertTrue(plan_path.is_file(), "DEPLOYMENT_PLAN.md должен существовать")
        text = plan_path.read_text(encoding="utf-8")
        section = text.split("### Шаг 2. Восстановление конфигурации и кода из pinned-бэкапа")[1]
        match = re.search(r"```bash\n(.*?)```", section, re.S)
        self.assertIsNotNone(match, "Блок bash отката должен присутствовать в плане")
        assert match is not None
        block = match.group(1)

        p = Path(self.temp_dir.name) / "rollback_sandbox"
        p.mkdir(parents=True, exist_ok=True)
        bindir = p / "bin"
        bindir.mkdir()
        backup = p / "pinned"
        backup.mkdir()
        (backup / "code").mkdir()
        (backup / "star-building-strategy.service").write_text("TAMPERED UNIT", encoding="utf-8")
        (backup / "code/app.py").write_text("TAMPERED CODE", encoding="utf-8")
        (backup / "pinned_metadata.json").write_text(json.dumps({"unit_sha256": "0" * 64, "code_files_count": 9999, "live_work_dir": "PINNED_OTHER_DIRECTORY"}), encoding="utf-8")

        for name in ["systemctl", "cp", "rsync"]:
            f = bindir / name
            if name == "systemctl":
                f.write_text('#!/bin/sh\nif [ "$1" = "--user" ] && [ "$2" = "show" ]; then printf "%s\\n" "$SAFE_WORK_DIR"; else printf "INTERCEPT systemctl %s\\n" "$*" >&2; fi\n', encoding="utf-8")
            else:
                f.write_text('#!/bin/sh\nprintf "INTERCEPT ' + name + ' %s\\n" "$*"\n', encoding="utf-8")
            f.chmod(0o700)

        env = {"HOME": str(p), "PATH": str(bindir) + ":/usr/bin:/bin", "PINNED_BACKUP_DIR": str(backup), "SAFE_WORK_DIR": str(p / "unrelated-directory"), "LANG": "C.UTF-8"}
        result = subprocess.run(["/bin/bash", "-c", block], env=env, text=True, capture_output=True)
        self.assertNotEqual(0, result.returncode, "Повреждённый бэкап обязан приводить к ненулевому коду завершения")
        self.assertNotIn("INTERCEPT cp", result.stdout, "cp не должен вызываться при сбое валидации бэкапа")
        self.assertNotIn("INTERCEPT rsync", result.stdout, "rsync не должен вызываться при сбое валидации бэкапа")

    def test_u2_u3_u4_rollback_comprehensive_matrix(self):
        """U2/U3/U4: Комплексная матрица сценариев отката: U2 bijection/manifest, U3 preflight before stop, U4 changed release."""
        import subprocess
        import json
        plan_path = ROOT / "DEPLOYMENT_PLAN.md"
        text = plan_path.read_text(encoding="utf-8")
        m_block = re.search(r"```bash\n(.*?)```", text.split("### Шаг 2. Восстановление конфигурации и кода из pinned-бэкапа")[1], re.S)
        assert m_block is not None
        block = m_block.group(1)
        m_stop = re.search(r"```bash\n(.*?)```", text.split("### Шаг 1. Остановка службы")[1], re.S)
        assert m_stop is not None
        stop = m_stop.group(1)

        cases = ["valid", "missing_files_map", "empty_files_map_tampered_code", "changed_current_release", "corrupt_before_stop", "systemctl_query_failure"]
        for case in cases:
            with self.subTest(case=case):
                p = Path(self.temp_dir.name) / f"rollback_{case}"
                p.mkdir(parents=True, exist_ok=True)
                bindir = p / "bin"
                bindir.mkdir()
                backup = p / "pinned"
                backup.mkdir()
                (backup / "code").mkdir()
                work = p / "old-release"
                work.mkdir()
                (backup / "star-building-strategy.service").write_text(f"[Service]\nWorkingDirectory={work}\n", encoding="utf-8")
                (backup / "code/app.py").write_text("print('safe')\n", encoding="utf-8")
                meta = {
                    "unit_sha256": hashlib.sha256((backup / "star-building-strategy.service").read_bytes()).hexdigest(),
                    "code_files_count": 1,
                    "live_work_dir": str(work),
                    "files": {"app.py": hashlib.sha256((backup / "code/app.py").read_bytes()).hexdigest()}
                }
                if case == "missing_files_map":
                    del meta["files"]
                elif case == "empty_files_map_tampered_code":
                    meta["files"] = {}
                    (backup / "code/app.py").write_text("TAMPERED", encoding="utf-8")
                elif case == "corrupt_before_stop":
                    meta["unit_sha256"] = "0" * 64
                (backup / "pinned_metadata.json").write_text(json.dumps(meta), encoding="utf-8")

                for name in ["cp", "rsync", "systemctl"]:
                    f = bindir / name
                    if name == "systemctl":
                        f.write_text('#!/bin/sh\nif [ "$2" = "show" ]; then if [ "$QUERY_FAIL" = 1 ]; then exit 1; fi; printf "%s\\n" "$SAFE_WORK_DIR"; else printf "INTERCEPT systemctl %s\\n" "$*"; fi\n', encoding="utf-8")
                    else:
                        f.write_text('#!/bin/sh\nprintf "INTERCEPT ' + name + ' %s\\n" "$*"\n', encoding="utf-8")
                    f.chmod(0o700)

                env = {
                    "HOME": str(p),
                    "PATH": str(bindir) + ":/usr/bin:/bin",
                    "PINNED_BACKUP_DIR": str(backup),
                    "SAFE_WORK_DIR": str(p / "new-release") if case == "changed_current_release" else str(work),
                    "QUERY_FAIL": "1" if case == "systemctl_query_failure" else "0",
                    "LANG": "C.UTF-8",
                }
                full_cmd = (stop if case == "corrupt_before_stop" else "") + "\n" + block
                proc = subprocess.run(["/bin/bash", "-c", full_cmd], env=env, text=True, capture_output=True)

                if case in {"valid", "changed_current_release"}:
                    self.assertEqual(0, proc.returncode, f"Сценарий {case} обязан завершиться успешно (exit 0)")
                    self.assertIn("INTERCEPT cp", proc.stdout)
                    self.assertIn("INTERCEPT rsync", proc.stdout)
                elif case == "corrupt_before_stop":
                    self.assertNotEqual(0, proc.returncode)
                    self.assertNotIn("INTERCEPT systemctl --user stop", proc.stdout, "При повреждённом бэкапе stop вызываться не должен (U3)!")
                    self.assertNotIn("INTERCEPT cp", proc.stdout)
                else:
                    self.assertNotEqual(0, proc.returncode, f"Сценарий {case} обязан завершиться fail-closed")
                    self.assertNotIn("INTERCEPT cp", proc.stdout)
                    self.assertNotIn("INTERCEPT rsync", proc.stdout)

    def test_u5_backup_allowlist_and_symlink_protection(self):
        """U5: Бэкап кода игнорирует .json/settings и блокирует разыменование внешних symlink."""
        plan_path = ROOT / "DEPLOYMENT_PLAN.md"
        text = plan_path.read_text(encoding="utf-8")
        step = text.split("### Шаг 2. Фиксация и полный бэкап")[1].split("### Шаг 3.")[0]
        m_code = re.search(r"python3 -c \"\n(.*?)\n\"", step, re.S)
        assert m_code is not None
        code = m_code.group(1)

        p = Path(self.temp_dir.name) / "u5_sandbox"
        p.mkdir(parents=True, exist_ok=True)
        src = p / "live"
        src.mkdir()
        dst = p / "backup"
        dst.mkdir()
        (dst / "code").mkdir()

        (src / "settings.json").write_text('{"fixture_only":"SYNTHETIC_SENSITIVE_SENTINEL"}', encoding="utf-8")
        (p / "external-fixture").write_text("SYNTHETIC_EXTERNAL_SENTINEL", encoding="utf-8")
        (src / "app.py").symlink_to(p / "external-fixture")
        (dst / "star-building-strategy.service").write_text("SAFE FIXTURE UNIT", encoding="utf-8")

        code = code.replace("$LIVE_WORK_DIR", str(src)).replace("$PINNED_BACKUP_DIR", str(dst)).replace("$BACKUP_TIMESTAMP", "FIXTURE").replace("$LIVE_UNIT_PATH", "FIXTURE_UNIT").replace("$LIVE_EXEC_START", "FIXTURE_EXEC")
        exec(compile(code, "DEPLOYMENT_PLAN backup excerpt", "exec"), {})

        self.assertFalse((dst / "code/settings.json").exists(), "settings.json не должен копироваться в бэкап кода")
        self.assertNotEqual("SYNTHETIC_EXTERNAL_SENTINEL", (dst / "code/app.py").read_text(encoding="utf-8"), "Внешний symlink target не должен копироваться")

if __name__ == "__main__":
    unittest.main()
