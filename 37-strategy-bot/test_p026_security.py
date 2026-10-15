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
                if case == "changed_current_release":
                    (p / "new-release").mkdir(exist_ok=True)
                (backup / "star-building-strategy.service").write_text(f"[Service]\nWorkingDirectory={work}\nExecStart=/fixture/python {work}/app.py\n", encoding="utf-8")
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
                        f.write_text('#!/bin/sh\nif [ "$2" = "show" ]; then if [ "$QUERY_FAIL" = 1 ]; then exit 1; fi; case "$*" in *ExecStart*) printf "/fixture/python %s/app.py\\n" "$SAFE_WORK_DIR";; *) printf "%s\\n" "$SAFE_WORK_DIR";; esac; else printf "INTERCEPT systemctl %s\\n" "$*"; fi\n', encoding="utf-8")
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
        """U5 / W4: Бэкап кода игнорирует settings.json, а symlink entrypoint отвергается fail-closed."""
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

        code_u5 = code.replace("$LIVE_WORK_DIR", str(src)).replace("$PINNED_BACKUP_DIR", str(dst)).replace("$BACKUP_TIMESTAMP", "FIXTURE").replace("$LIVE_UNIT_PATH", "FIXTURE_UNIT").replace("$LIVE_EXEC_START", f"/fixture/python {src}/app.py")
        # W4: symlink entrypoint обязан вызывать немедленный fail-closed отказ (SystemExit)
        with self.assertRaises(SystemExit):
            exec(compile(code_u5, "DEPLOYMENT_PLAN backup excerpt", "exec"), {})

        self.assertFalse((dst / "code/settings.json").exists(), "settings.json не должен копироваться в бэкап кода")
        self.assertFalse((dst / "code/app.py").exists(), "symlink app.py не должен копироваться в бэкап")

        # Позитивный сценарий: обычный валидный app.py копируется, settings.json игнорируется
        (src / "app.py").unlink()
        (src / "app.py").write_text("SAFE_REGULAR_CODE", encoding="utf-8")
        exec(compile(code_u5, "DEPLOYMENT_PLAN backup excerpt", "exec"), {})
        self.assertTrue((dst / "code/app.py").exists(), "Обычный файл app.py обязан быть скопирован в бэкап")
        self.assertFalse((dst / "code/settings.json").exists(), "settings.json не должен копироваться")

    def test_v2_v3_v4_v5_deployment_plan_probes(self):
        """V2, V3, V4, V5: Независимая верификация preflight, инвентаря, корней, whitelist и roundtrip."""
        import subprocess
        import json
        plan_path = ROOT / "DEPLOYMENT_PLAN.md"
        plan = plan_path.read_text(encoding="utf-8")
        def get_block(title):
            m = re.search(r"```bash\n(.*?)```", plan.split(title)[1], re.S)
            assert m is not None
            return m.group(1)

        stop = get_block("### Шаг 1. Остановка службы")
        restore = get_block("### Шаг 2. Восстановление конфигурации и кода из pinned-бэкапа")
        backup_block = get_block("### Шаг 2. Фиксация и полный бэкап")

        # Проверка V4 (положительный whitelist путей релиза без заглушек symlink)
        p_v4 = Path(self.temp_dir.name) / "v4_sandbox"
        p_v4.mkdir(parents=True, exist_ok=True)
        live_v4 = p_v4 / "live"; live_v4.mkdir()
        dst_v4 = p_v4 / "pinned"; dst_v4.mkdir(); (dst_v4 / "code").mkdir()
        (dst_v4 / "star-building-strategy.service").write_text("[Service]\n")
        (live_v4 / "private").mkdir()
        (live_v4 / "private/notes.txt").write_text("SYNTHETIC_SENSITIVE_SENTINEL")
        (live_v4 / "app.py").write_text('print("fixture")')
        (live_v4 / "linked.py").symlink_to(live_v4 / "app.py")

        m_v4 = re.search(r"python3 -c \"\n(.*?)\n\"", backup_block, re.S)
        assert m_v4 is not None
        code_v4 = m_v4.group(1)
        for a, b in {
            "$LIVE_WORK_DIR": str(live_v4),
            "$PINNED_BACKUP_DIR": str(dst_v4),
            "$BACKUP_TIMESTAMP": "FIXTURE",
            "$LIVE_UNIT_PATH": "FIXTURE",
            "$LIVE_EXEC_START": "FIXTURE",
        }.items():
            code_v4 = code_v4.replace(a, b)
        exec(compile(code_v4, "v4 backup excerpt", "exec"), {})

        self.assertFalse((dst_v4 / "code/private/notes.txt").exists(), "V4: private/notes.txt не должен копироваться в бэкап!")
        self.assertTrue((dst_v4 / "code/app.py").exists(), "V4: app.py обязан быть скопирован в бэкап")
        self.assertFalse((dst_v4 / "code/linked.py").exists(), "V4: symlink linked.py не должен заменяться заглушкой!")

        # Проверка V2, V3, V5, W1, W2 на rollback
        test_cases = [
            "valid_changed_release",
            "unexported_backup",
            "code_root_symlink",
            "extra_fifo",
            "boolean_count",
            "redirect_destination",
            "empty_current_handle",
            "backup_ancestor_symlink",
            "unapproved_current",
            "symlink_current",
            "nonexistent_current",
            "symlink_destination",
            "unapproved_destination",
        ]
        for case in test_cases:
            with self.subTest(case=case):
                p = Path(self.temp_dir.name) / f"v_probe_{case}"
                p.mkdir(parents=True, exist_ok=True)
                backup = p / "backup"; backup.mkdir(); (backup / "code").mkdir()
                (backup / "code/app.py").write_text('print("fixture")\n')
                old = p / "old-release"; old.mkdir(parents=True, exist_ok=True)
                new = p / "new-release"
                if case not in {"nonexistent_current", "empty_current_handle"}:
                    new.mkdir(parents=True, exist_ok=True)
                dest = str(old)
                handle = str(new)

                if case == "unapproved_current":
                    handle = "/unapproved-root/current"
                elif case == "nonexistent_current":
                    handle = str(p / "missing")
                elif case == "symlink_current":
                    (p / "current-link").symlink_to(new, target_is_directory=True)
                    handle = str(p / "current-link")
                elif case == "symlink_destination":
                    (p / "old-link").symlink_to(old, target_is_directory=True)
                    dest = str(p / "old-link")
                elif case == "unapproved_destination":
                    dest = "/unapproved-root/restore"
                elif case == "redirect_destination":
                    dest = str(p / "unrelated-target")

                unit = backup / "star-building-strategy.service"
                unit.write_text(f"[Service]\nWorkingDirectory={dest}\nExecStart=/fixture/python {dest}/app.py\n")
                meta = {
                    "unit_sha256": hashlib.sha256(unit.read_bytes()).hexdigest(),
                    "code_files_count": 1,
                    "live_work_dir": dest,
                    "files": {"app.py": hashlib.sha256((backup / "code/app.py").read_bytes()).hexdigest()},
                }
                if case == "redirect_destination":
                    meta["live_work_dir"] = str(p / "unrelated-target-wrong")
                if case == "code_root_symlink":
                    (backup / "code").rename(p / "outside")
                    (backup / "code").symlink_to(p / "outside", target_is_directory=True)
                if case == "backup_ancestor_symlink":
                    (p / "alias").symlink_to(p, target_is_directory=True)
                    backup = p / "alias/backup"
                if case == "extra_fifo":
                    os.mkfifo(backup / "code/untracked.pipe")
                if case == "boolean_count":
                    meta["code_files_count"] = True
                (backup / "pinned_metadata.json").write_text(json.dumps(meta))

                bindir = p / "bin"; bindir.mkdir()
                for name in ["systemctl", "cp", "rsync", "mkdir"]:
                    content = (
                        '#!/bin/sh\nif [ "$2" = show ]; then [ "$QUERY_FAIL" != 1 ] || exit 1; case "$*" in *ExecStart*) printf "/fixture/python %s/app.py\\n" "$CURRENT_HANDLE";; *) printf "%s\\n" "$CURRENT_HANDLE";; esac; else printf "INTERCEPT systemctl %s\\n" "$*"; fi\n'
                        if name == "systemctl"
                        else '#!/bin/sh\nprintf "INTERCEPT ' + name + ' %s\\n" "$*"\n'
                    )
                    f = bindir / name; f.write_text(content); f.chmod(0o700)

                env = {
                    "HOME": str(p),
                    "PATH": str(bindir) + ":/usr/bin:/bin",
                    "LANG": "C.UTF-8",
                    "QUERY_FAIL": "0",
                    "CURRENT_HANDLE": "" if case == "empty_current_handle" else handle,
                }
                prefix = ""
                if case == "unexported_backup":
                    prefix = f"PINNED_BACKUP_DIR={backup}\n"
                else:
                    env["PINNED_BACKUP_DIR"] = str(backup)

                proc = subprocess.run(
                    ["/bin/bash", "-c", prefix + stop + "\n" + restore],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                if case in {"valid_changed_release", "unexported_backup"}:
                    self.assertEqual(0, proc.returncode, f"Сценарий {case} обязан завершаться успешно (exit 0): {proc.stderr}")
                    self.assertIn("INTERCEPT cp", proc.stdout)
                    self.assertIn("INTERCEPT rsync", proc.stdout)
                else:
                    # Отрицательные сценарии V2, V3, W1, W2 обязаны давать отказ ДО вызова stop и любых мутаций!
                    self.assertNotEqual(0, proc.returncode, f"Отрицательный сценарий {case} обязан завершаться с ненулевым кодом: {proc.stdout}")
                    self.assertNotIn("INTERCEPT systemctl --user stop", proc.stdout, f"Служба не должна останавливаться в сценарии {case}!")
                    self.assertNotIn("INTERCEPT cp", proc.stdout, f"cp не должен вызываться в сценарии {case}!")
                    self.assertNotIn("INTERCEPT rsync", proc.stdout, f"rsync не должен вызываться в сценарии {case}!")
                    self.assertNotIn("INTERCEPT mkdir", proc.stdout, f"mkdir не должен вызываться в сценарии {case}!")

    def test_v5_consecutive_backup_switch_rollback_roundtrip(self):
        """V5 (MEDIUM): Сквозной тест consecutive round-trip (backup -> switch -> rollback) без внешнего export."""
        import subprocess
        import shutil
        plan_path = ROOT / "DEPLOYMENT_PLAN.md"
        plan = plan_path.read_text(encoding="utf-8")
        def get_block(title):
            m = re.search(r"```bash\n(.*?)```", plan.split(title)[1], re.S)
            assert m is not None
            return m.group(1)

        backup = get_block("### Шаг 2. Фиксация и полный бэкап")
        switch = get_block("### Шаг 4. Атомарное переключение службы")
        stop = get_block("### Шаг 1. Остановка службы")
        restore = get_block("### Шаг 2. Восстановление конфигурации и кода из pinned-бэкапа")
        start = get_block("### Шаг 4. Запуск восстановленной службы")

        for manual_export in [False, True]:
            with self.subTest(manual_export=manual_export):
                p = Path(self.temp_dir.name) / f"roundtrip_export_{manual_export}"
                p.mkdir(parents=True, exist_ok=True)
                home = p / "home"; home.mkdir()
                old = home / "old-release"; old.mkdir()
                (old / "app.py").write_text("OLD_FIXTURE_CODE\n")
                (old / "runtime-state.bin").write_text("PRESERVE_STATE")
                unit = home / ".config/systemd/user/star-building-strategy.service"
                unit.parent.mkdir(parents=True)
                oldunit = f"[Service]\nWorkingDirectory={old}\nExecStart=/fixture/python {old}/app.py\n"
                unit.write_text(oldunit)

                release = home / "new-release"
                (release / "37-strategy-bot/systemd").mkdir(parents=True)
                shutil.copyfile(ROOT / "systemd/star-building-strategy.service", release / "37-strategy-bot/systemd/star-building-strategy.service")

                bindir = p / "bin"; bindir.mkdir()
                log = p / "calls.log"
                systemctl = bindir / "systemctl"
                systemctl.write_text('#!/usr/bin/python3\nimport os,sys,pathlib\na=sys.argv[1:]\nu=pathlib.Path(os.environ["FIXTURE_UNIT"])\nif a[1]=="show":\n key=a[a.index("-p")+1]\n if key=="FragmentPath": print(u)\n else:\n  lines=u.read_text().splitlines()\n  print(next((l.split("=",1)[1] for l in lines if l.startswith(key+"=")),""))\nelse:\n with open(os.environ["FIXTURE_LOG"],"a") as f:\n  f.write("systemctl "+" ".join(a)+"\\n")\n')
                systemctl.chmod(0o700)

                rsync = bindir / "rsync"
                rsync.write_text('#!/usr/bin/python3\nimport os,pathlib,shutil,sys\ns=pathlib.Path(sys.argv[-2]); d=pathlib.Path(sys.argv[-1]); root=pathlib.Path(os.environ["FIXTURE_ROOT"])\nassert s.resolve().is_relative_to(root) and d.resolve().is_relative_to(root)\nshutil.copytree(s,d,dirs_exist_ok=True)\nwith open(os.environ["FIXTURE_LOG"],"a") as f:\n  f.write("rsync sandbox-copy\\n")\n')
                rsync.chmod(0o700)

                journal = bindir / "journalctl"
                journal.write_text("#!/bin/sh\nexit 0\n")
                journal.chmod(0o700)

                script = (backup + "\n" + switch + "\n" + ("export PINNED_BACKUP_DIR\n" if manual_export else "") + stop + "\n" + restore + "\n" + start).replace("/home/roman", str(home))
                script = "set -euo pipefail\nTARGET_COMMIT=FIXTURE\nRELEASE_DIR=" + str(release) + "\n" + script
                env = {"HOME": str(home), "PATH": str(bindir) + ":/usr/bin:/bin", "LANG": "C.UTF-8", "FIXTURE_UNIT": str(unit), "FIXTURE_LOG": str(log), "FIXTURE_ROOT": str(p)}

                proc = subprocess.run(["/bin/bash", "-c", script], env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(0, proc.returncode, f"Roundtrip (manual_export={manual_export}) завершился с ошибкой: {proc.stderr}\nSTDOUT:\n{proc.stdout}")
                self.assertTrue(unit.read_text() == oldunit, "Unit-файл службы должен быть точно восстановлен к старому релизу")
                self.assertEqual("PRESERVE_STATE", (old / "runtime-state.bin").read_text(), "Runtime-state не должен повреждаться/удаляться")
                self.assertEqual("OLD_FIXTURE_CODE\n", (old / "app.py").read_text(), "Код приложения должен быть точно восстановлен")

    def test_w3_w4_backup_security_probes(self):
        """W3, W4 (HIGH): Проверка доверенного inventory, canonical containment и отказа при неполном backup."""
        import json
        plan_path = ROOT / "DEPLOYMENT_PLAN.md"
        plan = plan_path.read_text(encoding="utf-8")
        m_block = re.search(r"```bash\n(.*?)```", plan.split("### Шаг 2. Фиксация и полный бэкап")[1], re.S)
        assert m_block is not None
        backup_block = m_block.group(1)
        m_code = re.search(r"python3 -c \"\n(.*?)\n\"", backup_block, re.S)
        assert m_code is not None
        backup_code = m_code.group(1)

        cases = ["canonical_control", "manifest_private", "manifest_traversal", "missing_entrypoint", "symlink_entrypoint", "empty_code"]
        for case in cases:
            with self.subTest(case=case):
                p = Path(self.temp_dir.name) / f"w_backup_{case}"
                p.mkdir(parents=True, exist_ok=True)
                live = p / "live"; live.mkdir()
                dst = p / "pinned"; dst.mkdir(); (dst / "code").mkdir()
                (dst / "star-building-strategy.service").write_text("[Service]\n")
                (live / "app.py").write_text("SAFE_APP")
                (live / "README.md").write_text("SAFE_README")
                (live / "private").mkdir()
                (live / "private/notes.txt").write_text("SYNTHETIC_PRIVATE_SENTINEL")

                if case == "manifest_private":
                    (live / "release_manifest.json").write_text(json.dumps({"files": ["app.py", "private/notes.txt"]}))
                elif case == "manifest_traversal":
                    (live / "sub").mkdir()
                    (live / "release_manifest.json").write_text(json.dumps({"files": ["sub/../../live/app.py"]}))
                elif case == "missing_entrypoint":
                    (live / "app.py").unlink()
                elif case == "symlink_entrypoint":
                    (live / "app.py").rename(live / "payload.py")
                    (live / "app.py").symlink_to(live / "payload.py")
                elif case == "empty_code":
                    (live / "app.py").unlink()
                    (live / "README.md").unlink()

                code = backup_code
                for a, b in {
                    "$LIVE_WORK_DIR": str(live),
                    "$PINNED_BACKUP_DIR": str(dst),
                    "$BACKUP_TIMESTAMP": "FIXTURE",
                    "$LIVE_UNIT_PATH": "FIXTURE",
                    "$LIVE_EXEC_START": f"/fixture/python {live}/app.py",
                }.items():
                    code = code.replace(a, b)

                if case == "canonical_control":
                    exec(compile(code, "exact backup excerpt", "exec"), {})
                    self.assertFalse((dst / "code/private/notes.txt").exists(), "private/notes.txt не должен копироваться")
                    self.assertFalse((dst / "live/app.py").exists(), "Файлы не должны выходить за пределы code/")
                    self.assertTrue((dst / "code/app.py").exists(), "app.py обязан присутствовать в бэкапе")
                else:
                    with self.assertRaises(SystemExit):
                        exec(compile(code, "exact backup excerpt", "exec"), {})
                    self.assertFalse((dst / "code/private/notes.txt").exists(), f"Небезопасный файл скопирован в {case}")
                    self.assertFalse((dst / "live/app.py").exists(), f"Path traversal произошёл в {case}")

    def test_w4_destructive_recovery_roundtrip(self):
        """W4 (HIGH): Деструктивный сценарий восстановления: код удаляется/модифицируется, rollback восстанавливает exact файлы."""
        import subprocess
        import shutil
        plan_path = ROOT / "DEPLOYMENT_PLAN.md"
        plan = plan_path.read_text(encoding="utf-8")
        def get_block(title):
            m = re.search(r"```bash\n(.*?)```", plan.split(title)[1], re.S)
            assert m is not None
            return m.group(1)

        backup = get_block("### Шаг 2. Фиксация и полный бэкап")
        switch = get_block("### Шаг 4. Атомарное переключение службы")
        stop = get_block("### Шаг 1. Остановка службы")
        restore = get_block("### Шаг 2. Восстановление конфигурации и кода из pinned-бэкапа")
        start = get_block("### Шаг 4. Запуск восстановленной службы")

        p = Path(self.temp_dir.name) / "destructive_roundtrip"
        p.mkdir(parents=True, exist_ok=True)
        home = p / "home"; home.mkdir()
        old = home / "old-release"; old.mkdir()
        (old / "app.py").write_text("AUTHENTIC_ORIGINAL_CODE\n")
        (old / "README.md").write_text("AUTHENTIC_README\n")
        (old / "runtime-state.bin").write_text("PRESERVE_STATE")
        unit = home / ".config/systemd/user/star-building-strategy.service"
        unit.parent.mkdir(parents=True)
        oldunit = f"[Service]\nWorkingDirectory={old}\nExecStart=/fixture/python {old}/app.py\n"
        unit.write_text(oldunit)

        release = home / "new-release"
        (release / "37-strategy-bot/systemd").mkdir(parents=True)
        shutil.copyfile(ROOT / "systemd/star-building-strategy.service", release / "37-strategy-bot/systemd/star-building-strategy.service")

        bindir = p / "bin"; bindir.mkdir()
        log = p / "calls.log"
        systemctl = bindir / "systemctl"
        systemctl.write_text('#!/usr/bin/python3\nimport os,sys,pathlib\na=sys.argv[1:]\nu=pathlib.Path(os.environ["FIXTURE_UNIT"])\nif a[1]=="show":\n key=a[a.index("-p")+1]\n if key=="FragmentPath": print(u)\n else:\n  lines=u.read_text().splitlines()\n  print(next((l.split("=",1)[1] for l in lines if l.startswith(key+"=")),""))\nelse:\n with open(os.environ["FIXTURE_LOG"],"a") as f:\n  f.write("systemctl "+" ".join(a)+"\\n")\n')
        systemctl.chmod(0o700)

        rsync = bindir / "rsync"
        rsync.write_text('#!/usr/bin/python3\nimport os,pathlib,shutil,sys\ns=pathlib.Path(sys.argv[-2]); d=pathlib.Path(sys.argv[-1]); root=pathlib.Path(os.environ["FIXTURE_ROOT"])\nassert s.resolve().is_relative_to(root) and d.resolve().is_relative_to(root)\nshutil.copytree(s,d,dirs_exist_ok=True)\nwith open(os.environ["FIXTURE_LOG"],"a") as f:\n  f.write("rsync sandbox-copy\\n")\n')
        rsync.chmod(0o700)

        journal = bindir / "journalctl"
        journal.write_text("#!/bin/sh\nexit 0\n")
        journal.chmod(0o700)

        # 1. Выполняем backup и switch
        script_part1 = (backup + "\n" + switch).replace("/home/roman", str(home))
        script_part1 = "set -euo pipefail\nTARGET_COMMIT=FIXTURE\nRELEASE_DIR=" + str(release) + "\n" + script_part1
        env = {"HOME": str(home), "PATH": str(bindir) + ":/usr/bin:/bin", "LANG": "C.UTF-8", "FIXTURE_UNIT": str(unit), "FIXTURE_LOG": str(log), "FIXTURE_ROOT": str(p)}
        proc1 = subprocess.run(["/bin/bash", "-c", script_part1], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(0, proc1.returncode, f"Backup + switch завершились с ошибкой: {proc1.stderr}")

        m_dir = re.search(r"Бэкап работающего релиза надёжно зафиксирован в: (.*)", proc1.stdout)
        assert m_dir is not None
        pinned_dir = m_dir.group(1).strip()
        env["PINNED_BACKUP_DIR"] = pinned_dir

        # 2. ДЕСТРУКТИВНОЕ ВОЗДЕЙСТВИЕ: удаляем app.py и модифицируем README в старом каталоге
        (old / "app.py").unlink()
        (old / "README.md").write_text("TAMPERED_CONTENT")

        # 3. Выполняем stop + restore + start
        script_part2 = (stop + "\n" + restore + "\n" + start).replace("/home/roman", str(home))
        script_part2 = "set -euo pipefail\nTARGET_COMMIT=FIXTURE\nRELEASE_DIR=" + str(release) + "\n" + script_part2
        proc2 = subprocess.run(["/bin/bash", "-c", script_part2], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(0, proc2.returncode, f"Rollback после деструктивного воздействия завершился с ошибкой: {proc2.stderr}\nSTDOUT:\n{proc2.stdout}")

        # 4. Проверяем полное и точное восстановление удалённого entrypoint и хэшей
        self.assertTrue((old / "app.py").exists(), "Удалённый entrypoint app.py обязан быть восстановлен!")
        self.assertEqual("AUTHENTIC_ORIGINAL_CODE\n", (old / "app.py").read_text(), "Содержимое entrypoint app.py обязано быть в точности восстановлено!")
        self.assertEqual("AUTHENTIC_README\n", (old / "README.md").read_text(), "Содержимое README.md обязано быть восстановлено из бэкапа!")
        self.assertEqual("PRESERVE_STATE", (old / "runtime-state.bin").read_text(), "Runtime-state не должен повреждаться!")
        self.assertTrue(unit.read_text() == oldunit, "Unit-файл службы должен быть точно восстановлен к старому релизу")

    def test_x1_x2_rollback_approved_roots_and_execstart_probes(self):
        """X1, X2 (HIGH): Проверка каноничности approved roots (без ..), существования destination и identity ExecStart."""
        import json
        import subprocess
        plan_path = ROOT / "DEPLOYMENT_PLAN.md"
        plan = plan_path.read_text(encoding="utf-8")
        def get_block(title):
            m = re.search(r"```bash\n(.*?)```", plan.split(title)[1], re.S)
            assert m is not None
            return m.group(1)

        stop = get_block("### Шаг 1. Остановка службы")
        restore = get_block("### Шаг 2. Восстановление конфигурации и кода из pinned-бэкапа")

        cases = [
            "control",
            "destination_escape",
            "current_escape",
            "missing_destination",
            "old_exec_mismatch",
            "old_exec_missing",
            "current_exec_mismatch",
        ]
        for phase, script in [("stop", stop), ("restore", restore)]:
            for case in cases:
                with self.subTest(phase=phase, case=case):
                    p = Path(self.temp_dir.name) / f"x12_{phase}_{case}"
                    p.mkdir(parents=True, exist_ok=True)
                    home = p / "home"; home.mkdir()
                    old = home / "old"; old.mkdir()
                    cur = home / "current"; cur.mkdir()
                    dst = home / "backup"; dst.mkdir(); (dst / "code").mkdir()
                    (old / "app.py").write_text("SYNTHETIC_APP\n")
                    (cur / "app.py").write_text("CURRENT_APP\n")
                    (dst / "code/app.py").write_text("SYNTHETIC_BACKUP\n")

                    dest = str(old)
                    handle = str(cur)
                    execstart = f"/fixture/python {old}/app.py"
                    current_exec = f"/fixture/python {cur}/app.py"

                    if case == "destination_escape":
                        dest = str(home / ".." / "outside")
                        (p / "outside").mkdir()
                        execstart = f"/fixture/python {dest}/app.py"
                    elif case == "current_escape":
                        handle = str(home / ".." / "outside")
                        (p / "outside").mkdir()
                        current_exec = f"/fixture/python {handle}/app.py"
                    elif case == "missing_destination":
                        (old / "app.py").unlink()
                        old.rmdir()
                    elif case == "old_exec_mismatch":
                        execstart = f"/fixture/python {p}/unrelated/app.py"
                    elif case == "old_exec_missing":
                        execstart = ""
                    elif case == "current_exec_mismatch":
                        current_exec = f"/fixture/python {p}/unrelated/app.py"

                    unit = f"[Service]\nWorkingDirectory={dest}\nExecStart={execstart}\n"
                    (dst / "star-building-strategy.service").write_text(unit)
                    meta = {
                        "unit_sha256": hashlib.sha256(unit.encode()).hexdigest(),
                        "code_files_count": 1,
                        "live_work_dir": dest,
                        "files": {"app.py": hashlib.sha256((dst / "code/app.py").read_bytes()).hexdigest()}
                    }
                    (dst / "pinned_metadata.json").write_text(json.dumps(meta))

                    bindir = p / "bin"; bindir.mkdir()
                    log = p / "calls.log"
                    stub = bindir / "systemctl"
                    stub_code = f"""#!/usr/bin/python3
import os, sys, json
a = sys.argv[1:]
with open("{str(log)}", "a") as f:
    f.write(json.dumps(a) + "\\n")
if "show" in a:
    if "WorkingDirectory" in a:
        print("{handle}")
    elif "ExecStart" in a:
        print("{current_exec}")
    else:
        print("")
"""
                    stub.write_text(stub_code)
                    stub.chmod(0o700)

                    for cmd in ["cp", "mv", "rsync", "mkdir"]:
                        stub2 = bindir / cmd
                        stub2.write_text(f'#!/bin/sh\nprintf "MUTATION {cmd}\\n" >> "{str(log)}"\n')
                        stub2.chmod(0o700)

                    env = {
                        "HOME": str(home),
                        "PATH": str(bindir) + ":/usr/bin:/bin",
                        "PINNED_BACKUP_DIR": str(dst),
                    }
                    proc = subprocess.run(["/bin/bash", "-c", script], env=env, capture_output=True, text=True, timeout=10)
                    calls = log.read_text().splitlines() if log.exists() else []

                    if case == "control":
                        self.assertEqual(0, proc.returncode, f"Control case обязан завершаться с кодом 0: {proc.stderr}")
                    else:
                        self.assertNotEqual(0, proc.returncode, f"Отрицательный сценарий {case} ({phase}) обязан завершаться с ошибкой: {proc.stdout}")
                        mutations = [c for c in calls if "MUTATION" in c]
                        self.assertEqual([], mutations, f"Мутации не должны выполняться при отказе в {case}: {mutations}")
                        self.assertNotIn("systemctl --user stop", " ".join(calls) if phase == "stop" else "", f"Служба не должна останавливаться в {case}")

    def test_x3_backup_target_and_source_symlinks(self):
        """X3 (HIGH): Запрет target symlink (root/nested) и source root symlink при бэкапе."""
        import json
        plan_path = ROOT / "DEPLOYMENT_PLAN.md"
        plan = plan_path.read_text(encoding="utf-8")
        m_block = re.search(r"```bash\n(.*?)```", plan.split("### Шаг 2. Фиксация и полный бэкап")[1], re.S)
        assert m_block is not None
        backup_block = m_block.group(1)
        m_code = re.search(r"python3 -c \"\n(.*?)\n\"", backup_block, re.S)
        assert m_code is not None
        backup_code = m_code.group(1)

        cases = ["control", "target_root_symlink", "target_nested_symlink", "source_root_symlink"]
        for case in cases:
            with self.subTest(case=case):
                p = Path(self.temp_dir.name) / f"x3_backup_{case}"
                p.mkdir(parents=True, exist_ok=True)
                home = p / "home"; home.mkdir()
                src = home / "src"; src.mkdir()
                dst = home / "dst"; dst.mkdir(); (dst / "code").mkdir()
                ext = p / "outside"; ext.mkdir()
                (ext / "app.py").write_text("EXTERNAL_UNCHANGED\n")
                (src / "app.py").write_text("SYNTHETIC_APP\n")
                (src / "p026_storage.py").write_text("SYNTHETIC_STORAGE\n")

                if case == "target_root_symlink":
                    (dst / "code").rmdir()
                    (dst / "code").symlink_to(ext, target_is_directory=True)
                elif case == "source_root_symlink":
                    alias = home / "alias"
                    alias.symlink_to(src, target_is_directory=True)
                    src = alias
                elif case == "target_nested_symlink":
                    (src / "systemd").mkdir()
                    (src / "systemd/star-building-strategy.service").write_text("SYNTHETIC_UNIT\n")
                    (dst / "code/systemd").symlink_to(ext, target_is_directory=True)

                (dst / "star-building-strategy.service").write_text("[Service]\n")
                code = backup_code
                for a, b in {
                    "$LIVE_WORK_DIR": str(src),
                    "$PINNED_BACKUP_DIR": str(dst),
                    "$BACKUP_TIMESTAMP": "FIXTURE",
                    "$LIVE_UNIT_PATH": "FIXTURE",
                    "$LIVE_EXEC_START": f"/fixture/python {src}/app.py",
                }.items():
                    code = code.replace(a, b)

                if case == "control":
                    exec(compile(code, "exact backup excerpt", "exec"), {})
                    self.assertTrue((dst / "code/app.py").exists(), "app.py обязан быть в бэкапе")
                    self.assertTrue((dst / "code/p026_storage.py").exists(), "p026_storage.py обязан быть в бэкапе")
                else:
                    with self.assertRaises(SystemExit):
                        exec(compile(code, "exact backup excerpt", "exec"), {})
                    self.assertEqual("EXTERNAL_UNCHANGED\n", (ext / "app.py").read_text(), f"Внешний файл изменён в {case}")

    def test_x4_manifest_incomplete_and_executable_recovery_e2e(self):
        """X4 (HIGH): Обязательная полнота inventory, отказ неполного манифеста и исполнение восстановленного entrypoint."""
        import json
        import subprocess
        plan_path = ROOT / "DEPLOYMENT_PLAN.md"
        plan = plan_path.read_text(encoding="utf-8")
        def get_block(title):
            m = re.search(r"```bash\n(.*?)```", plan.split(title)[1], re.S)
            assert m is not None
            return m.group(1)

        backup_block = get_block("### Шаг 2. Фиксация и полный бэкап")
        switch = get_block("### Шаг 4. Атомарное переключение службы")
        stop = get_block("### Шаг 1. Остановка службы")
        restore = get_block("### Шаг 2. Восстановление конфигурации и кода из pinned-бэкапа")
        start = get_block("### Шаг 4. Запуск восстановленной службы")

        m_code = re.search(r"python3 -c \"\n(.*?)\n\"", backup_block, re.S)
        assert m_code is not None
        backup_code = m_code.group(1)

        p = Path(self.temp_dir.name) / "x4_recovery"
        p.mkdir(parents=True, exist_ok=True)
        home = p / "home"; home.mkdir()
        old = home / "old-release"; old.mkdir()
        cur = home / "current-release"; cur.mkdir()

        (old / "app.py").write_text("import p026_storage\nprint(p026_storage.VALUE)\n")
        (old / "p026_storage.py").write_text("VALUE = 'RECOVERED_OK'\n")

        # 1. Негативный сценарий X4: неполный manifest_incomplete (files=['app.py'] при наличии p026_storage.py) отвергается fail-closed
        (old / "release_manifest.json").write_text(json.dumps({"files": ["app.py"]}))
        dst_bad = home / "bad_backup"; dst_bad.mkdir(); (dst_bad / "code").mkdir()
        (dst_bad / "star-building-strategy.service").write_text("[Service]\n")
        bad_code = backup_code
        for a, b in {
            "$LIVE_WORK_DIR": str(old),
            "$PINNED_BACKUP_DIR": str(dst_bad),
            "$BACKUP_TIMESTAMP": "FIXTURE",
            "$LIVE_UNIT_PATH": "FIXTURE",
            "$LIVE_EXEC_START": f"/fixture/python {old}/app.py",
        }.items():
            bad_code = bad_code.replace(a, b)

        with self.assertRaises(SystemExit):
            exec(compile(bad_code, "exact backup excerpt", "exec"), {})
        self.assertFalse((dst_bad / "pinned_metadata.json").exists(), "Неполный манифест не должен формировать успешную metadata!")

        # 2. Позитивный сценарий X4: полный манифест с зависимостями
        (old / "release_manifest.json").write_text(json.dumps({"files": ["app.py", "p026_storage.py"]}))

        # Проверяем, что исходный entrypoint штатно исполняется до бэкапа
        initial_run = subprocess.run([sys.executable, str(old / "app.py")], capture_output=True, text=True)
        self.assertEqual(0, initial_run.returncode)
        self.assertEqual("RECOVERED_OK", initial_run.stdout.strip())

        unit = home / ".config/systemd/user/star-building-strategy.service"
        unit.parent.mkdir(parents=True)
        oldunit = f"[Service]\nWorkingDirectory={old}\nExecStart={sys.executable} {old}/app.py\n"
        unit.write_text(oldunit)

        release = home / "new-release"
        (release / "37-strategy-bot/systemd").mkdir(parents=True)
        import shutil
        shutil.copyfile(ROOT / "systemd/star-building-strategy.service", release / "37-strategy-bot/systemd/star-building-strategy.service")

        bindir = p / "bin"; bindir.mkdir()
        log = p / "calls.log"
        systemctl = bindir / "systemctl"
        systemctl.write_text('#!/usr/bin/python3\nimport os,sys,pathlib\na=sys.argv[1:]\nu=pathlib.Path(os.environ["FIXTURE_UNIT"])\nif a[1]=="show":\n key=a[a.index("-p")+1]\n if key=="FragmentPath": print(u)\n else:\n  lines=u.read_text().splitlines()\n  print(next((l.split("=",1)[1] for l in lines if l.startswith(key+"=")),""))\nelse:\n with open(os.environ["FIXTURE_LOG"],"a") as f:\n  f.write("systemctl "+" ".join(a)+"\\n")\n')
        systemctl.chmod(0o700)

        rsync = bindir / "rsync"
        rsync.write_text('#!/usr/bin/python3\nimport os,pathlib,shutil,sys\ns=pathlib.Path(sys.argv[-2]); d=pathlib.Path(sys.argv[-1]); root=pathlib.Path(os.environ["FIXTURE_ROOT"])\nassert s.resolve().is_relative_to(root) and d.resolve().is_relative_to(root)\nshutil.copytree(s,d,dirs_exist_ok=True)\nwith open(os.environ["FIXTURE_LOG"],"a") as f:\n  f.write("rsync sandbox-copy\\n")\n')
        rsync.chmod(0o700)

        journal = bindir / "journalctl"
        journal.write_text("#!/bin/sh\nexit 0\n")
        journal.chmod(0o700)

        # Выполняем backup и switch
        script_part1 = (backup_block + "\n" + switch).replace("/home/roman", str(home))
        script_part1 = "set -euo pipefail\nTARGET_COMMIT=FIXTURE\nRELEASE_DIR=" + str(release) + "\n" + script_part1
        env = {"HOME": str(home), "PATH": str(bindir) + ":/usr/bin:/bin", "LANG": "C.UTF-8", "FIXTURE_UNIT": str(unit), "FIXTURE_LOG": str(log), "FIXTURE_ROOT": str(p)}
        proc1 = subprocess.run(["/bin/bash", "-c", script_part1], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(0, proc1.returncode, f"Backup + switch завершились с ошибкой: {proc1.stderr}")

        m_dir = re.search(r"Бэкап работающего релиза надёжно зафиксирован в: (.*)", proc1.stdout)
        assert m_dir is not None
        pinned_dir = m_dir.group(1).strip()
        env["PINNED_BACKUP_DIR"] = pinned_dir

        # ДЕСТРУКТИВНОЕ ВОЗДЕЙСТВИЕ: удаляем оба исходных модуля из old
        (old / "app.py").unlink()
        (old / "p026_storage.py").unlink()

        # Выполняем stop + restore + start
        script_part2 = (stop + "\n" + restore + "\n" + start).replace("/home/roman", str(home))
        script_part2 = "set -euo pipefail\nTARGET_COMMIT=FIXTURE\nRELEASE_DIR=" + str(release) + "\n" + script_part2
        proc2 = subprocess.run(["/bin/bash", "-c", script_part2], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(0, proc2.returncode, f"Rollback завершился с ошибкой: {proc2.stderr}\nSTDOUT:\n{proc2.stdout}")

        # ИСПОЛНЕНИЕ ВОССТАНОВЛЕННОГО ENTRYPOINT (Ключевое требование X4)
        self.assertTrue((old / "app.py").exists(), "app.py обязан быть восстановлен!")
        self.assertTrue((old / "p026_storage.py").exists(), "p026_storage.py обязан быть восстановлен!")

        restored_run = subprocess.run([sys.executable, str(old / "app.py")], capture_output=True, text=True)
        self.assertEqual(0, restored_run.returncode, f"Исполнение восстановленного entrypoint завершилось с ошибкой: {restored_run.stderr}")
        self.assertEqual("RECOVERED_OK", restored_run.stdout.strip())
        self.assertEqual("", restored_run.stderr)

if __name__ == "__main__":
    unittest.main()
