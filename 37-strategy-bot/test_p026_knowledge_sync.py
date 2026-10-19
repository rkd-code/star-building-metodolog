"""Комплексные тесты версионного обмена рабочими знаниями Драмкнота (FN-015).

Проверяет:
1. Producer: создание неизменяемого пакета разработки в outbox.
2. Registrar: доверенная валидация, регистрация в 01_В_РАБОТЕ, ведение реестра.
3. Consumer: интерфейс чтения с проверкой прав (actor/role isolation) и ссылочной целостности.
4. Immunity: абсолютная неприкосновенность контура 02_УТВЕРЖДЕНО (0 мутаций).
5. Идемпотентность и fail-closed карантин при любых нарушениях.
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import shutil
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p026_knowledge_sync import (
    ALLOWED_STATUSES,
    ApprovedContourImmunityError,
    DramknoteProducer,
    PackageValidationError,
    SharedKnowledgeConsumer,
    SharedKnowledgeRegistrar,
    STATUS_ARCHIVED,
    STATUS_CONFIRMED_DECISION,
    STATUS_DRAFT,
    STATUS_SUPERSEDED,
    STATUS_VERIFIED_MATERIAL,
)
from p026_storage import PathTraversalError


class TestP026KnowledgeSync(unittest.TestCase):
    """Тестовый набор для FN-015: обмен знаниями Драмкнота с общей базой."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.tmp_dir.name)

        # Структура директорий Драмкнота (Producer state)
        self.dramknote_state_dir = self.root_path / "dramknote_state"
        self.outbox_dir = self.dramknote_state_dir / "outbox"

        # Структура общей базы знаний (Knowledge base)
        self.kb_dir = self.root_path / "knowledge_base"
        self.kb_work_dir = self.kb_dir / "01_В_РАБОТЕ"
        self.kb_approved_dir = self.kb_dir / "02_УТВЕРЖДЕНО"
        self.kb_registry_dir = self.kb_work_dir / "00_РЕЕСТР_РАЗРАБОТОК"
        self.quarantine_dir = self.kb_work_dir / "quarantine"

        self.kb_work_dir.mkdir(parents=True, exist_ok=True)
        self.kb_approved_dir.mkdir(parents=True, exist_ok=True)

        # Заполняем эталонный файл в 02_УТВЕРЖДЕНО для контроля неприкосновенности
        self.sentinel_file = self.kb_approved_dir / "REG-001_kodeks.md"
        self.sentinel_content = "# ЭТАЛОННЫЙ УТВЕРЖДЕННЫЙ КОДЕКС\nНеприкосновенно."
        self.sentinel_file.write_text(self.sentinel_content, encoding="utf-8")
        self.initial_approved_hash = hashlib.sha256(self.sentinel_file.read_bytes()).hexdigest()

        # Инициализация компонентов
        self.producer = DramknoteProducer(outbox_dir=self.outbox_dir)
        self.registrar = SharedKnowledgeRegistrar(
            kb_dir=self.kb_dir,
            working_dir=self.kb_work_dir,
            approved_dir=self.kb_approved_dir,
            registry_dir=self.kb_registry_dir,
            quarantine_dir=self.quarantine_dir,
        )
        self.consumer = SharedKnowledgeConsumer(
            kb_dir=self.kb_dir,
            registry_dir=self.kb_registry_dir,
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _assert_approved_contour_untouched(self) -> None:
        """Инвариант неприкосновенности ГД-контура: 0 изменений."""
        self.assertTrue(self.sentinel_file.exists())
        current_hash = hashlib.sha256(self.sentinel_file.read_bytes()).hexdigest()
        self.assertEqual(current_hash, self.initial_approved_hash)
        approved_files = list(self.kb_approved_dir.iterdir())
        self.assertEqual(len(approved_files), 1)
        self.assertEqual(approved_files[0].name, "REG-001_kodeks.md")

    # -------------------------------------------------------------------------
    # 1. Producer тесты
    # -------------------------------------------------------------------------

    def test_producer_creates_valid_package(self) -> None:
        """Producer формирует корректный неизменяемый пакет разработки в outbox."""
        payload = "# Решение по РОП\nСрок реакции 3 часа."
        pkg = self.producer.create_package(
            material_id="pkg_test_01",
            project="P-026",
            author="Руководитель",
            content=payload,
            filename="rop_decision.md",
            material_type="decision",
            version=1,
            status=STATUS_CONFIRMED_DECISION,
            audience=["ponder", "dramknote", "commercial_department"],
            user_id=12345,
            chat_id=-100987654321,
            metadata={"context": "Лимиты времени РОП"},
        )

        self.assertTrue(pkg["package_dir"].exists())
        manifest_file = pkg["package_dir"] / "manifest.json"
        payload_file = pkg["package_dir"] / "rop_decision.md"

        self.assertTrue(manifest_file.exists())
        self.assertTrue(payload_file.exists())
        self.assertEqual(payload_file.read_text(encoding="utf-8"), payload)

        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "pkg_test_01")
        self.assertEqual(manifest["project"], "P-026")
        self.assertEqual(manifest["author"], "Руководитель")
        self.assertEqual(manifest["user_id"], 12345)
        self.assertEqual(manifest["chat_id"], -100987654321)
        self.assertEqual(manifest["material_type"], "decision")
        self.assertEqual(manifest["status"], STATUS_CONFIRMED_DECISION)
        self.assertEqual(manifest["payload_filename"], "rop_decision.md")
        self.assertEqual(manifest["payload_size"], len(payload.encode("utf-8")))
        self.assertEqual(
            manifest["payload_sha256"],
            hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        )
        self.assertIn("ponder", manifest["audience"])

    def test_producer_path_traversal_payload_filename_rejected(self) -> None:
        """Producer отклоняет попытки path traversal в имени файла полезной нагрузки."""
        with self.assertRaises(PathTraversalError):
            self.producer.create_package(
                material_id="pkg_evil",
                project="P-026",
                author="Hacker",
                content="malicious",
                filename="../../etc/passwd",
                material_type="draft",
                status=STATUS_DRAFT,
                audience=["ponder"],
            )

        with self.assertRaises(PathTraversalError):
            self.producer.create_package(
                material_id="pkg_evil_abs",
                project="P-026",
                author="Hacker",
                content="malicious",
                filename="/root/secret.txt",
                material_type="draft",
                status=STATUS_DRAFT,
                audience=["ponder"],
            )

    # -------------------------------------------------------------------------
    # 2. Registrar тесты и сквозной тракт
    # -------------------------------------------------------------------------

    def test_e2e_register_and_read_authorized(self) -> None:
        """Сквозной тракт: создание пакета -> регистрация в 01_В_РАБОТЕ -> чтение разрешенным агентом."""
        content = "## Решение №88: Лимит скидки МОП 5%\nДействует с 2026-10-19."
        pkg = self.producer.create_package(
            material_id="pkg_decision_88",
            project="P-026",
            author="Владелец",
            content=content,
            filename="decision_88.md",
            material_type="decision",
            version=1,
            status=STATUS_CONFIRMED_DECISION,
            audience=["ponder", "developer", "dramknote", "commercial_department"],
            user_id=101,
            chat_id=-202,
        )

        res = self.registrar.register_package(pkg["package_dir"])
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "registered")
        self.assertIn("registered_path", res)

        # Проверка дискового артефакта
        registered_path = Path(res["registered_path"])
        self.assertTrue(registered_path.exists())
        self.assertEqual(registered_path.read_text(encoding="utf-8"), content)
        # Артефакт сохранен внутри 01_В_РАБОТЕ
        self.assertTrue(registered_path.resolve().is_relative_to(self.kb_work_dir.resolve()))

        # Проверка записи в реестре
        registry_file = self.kb_registry_dir / "registry.json"
        self.assertTrue(registry_file.exists())
        registry_data = json.loads(registry_file.read_text(encoding="utf-8"))
        self.assertEqual(len(registry_data["records"]), 1)
        record = registry_data["records"][0]
        self.assertEqual(record["id"], "pkg_decision_88")
        self.assertEqual(record["project"], "P-026")
        self.assertEqual(record["status"], STATUS_CONFIRMED_DECISION)
        self.assertEqual(record["payload_sha256"], hashlib.sha256(content.encode("utf-8")).hexdigest())

        # Чтение разрешенным потребителем (Пондер)
        ponder_read = self.consumer.read_material("pkg_decision_88", requester_role="ponder")
        self.assertTrue(ponder_read["ok"])
        self.assertEqual(ponder_read["content"], content)
        self.assertEqual(ponder_read["record"]["author"], "Владелец")

        # Чтение Драмкнотом
        dramknote_read = self.consumer.read_material("pkg_decision_88", requester_role="dramknote")
        self.assertTrue(dramknote_read["ok"])
        self.assertEqual(dramknote_read["content"], content)

        # Контур ГД по-прежнему не тронут
        self._assert_approved_contour_untouched()

    def test_consumer_isolation_unauthorized_denied(self) -> None:
        """Изоляция прав: бот «Ом», неавторизованные роли и утвержденный контур не видят рабочие материалы."""
        content = "Конфиденциальные условия сделки на 1.2 млрд тенге."
        pkg = self.producer.create_package(
            material_id="pkg_confidential_01",
            project="P-026",
            author="Владелец",
            content=content,
            filename="confidential.md",
            material_type="decision",
            status=STATUS_CONFIRMED_DECISION,
            audience=["ponder", "dramknote", "commercial_department"],
        )
        reg_res = self.registrar.register_package(pkg["package_dir"])
        self.assertTrue(reg_res["ok"])

        # 1. Попытка чтения ботом «Ом» (консультант рядовых сотрудников)
        with self.assertRaises(PermissionError) as ctx_om:
            self.consumer.read_material("pkg_confidential_01", requester_role="om")
        self.assertIn("запрещен", str(ctx_om.exception).lower())

        # 2. Попытка чтения ролью approved_only
        with self.assertRaises(PermissionError):
            self.consumer.read_material("pkg_confidential_01", requester_role="approved_only")

        # 3. Попытка чтения неизвестным агентом (сторонняя роль)
        with self.assertRaises(PermissionError):
            self.consumer.read_material("pkg_confidential_01", requester_role="unauthorized_guest")

        # 4. Поиск / листинг материалов: бот «Ом» получает 0 записей
        om_list = self.consumer.list_materials(requester_role="om")
        self.assertEqual(len(om_list), 0)

        unauth_list = self.consumer.list_materials(requester_role="unauthorized_guest")
        self.assertEqual(len(unauth_list), 0)

        # Авторизованный видит 1 запись
        ponder_list = self.consumer.list_materials(requester_role="ponder")
        self.assertEqual(len(ponder_list), 1)

    # -------------------------------------------------------------------------
    # 3. Абсолютная защита ГД-контура (02_УТВЕРЖДЕНО)
    # -------------------------------------------------------------------------

    def test_approved_contour_immunity_enforced(self) -> None:
        """Попытка регистрации с указанием пути или контура 02_УТВЕРЖДЕНО строго пресекается."""
        pkg = self.producer.create_package(
            material_id="pkg_fake_approval",
            project="P-026",
            author="Attacker",
            content="Попытка утверждения без ГД",
            filename="fake.md",
            material_type="regulation",
            status=STATUS_CONFIRMED_DECISION,
            audience=["ponder"],
        )

        # 1. Попытка направить регистратор в approved_dir
        with self.assertRaises(ApprovedContourImmunityError):
            bad_registrar = SharedKnowledgeRegistrar(
                kb_dir=self.kb_dir,
                working_dir=self.kb_approved_dir,  # Попытка подмены рабочего каталога на утвержденный
                approved_dir=self.kb_approved_dir,
                registry_dir=self.kb_registry_dir,
                quarantine_dir=self.quarantine_dir,
            )

        # 2. Попытка подсунуть относительный путь к 02_УТВЕРЖДЕНО в manifest
        manifest_path = pkg["package_dir"] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["target_subpath"] = "../02_УТВЕРЖДЕНО/injected.md"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        res = self.registrar.register_package(pkg["package_dir"])
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "quarantined")
        self.assertIn("traversal", res["reason"].lower())

        self._assert_approved_contour_untouched()

    # -------------------------------------------------------------------------
    # 4. Идемпотентность и восстановление
    # -------------------------------------------------------------------------

    def test_registrar_idempotency_no_duplicate_records(self) -> None:
        """Повторная регистрация идентичного пакета возвращает existing запись без дубликатов."""
        content = "Норматив: согласование сделок свыше 1 млрд тенге."
        pkg = self.producer.create_package(
            material_id="pkg_idempotent_01",
            project="P-026",
            author="Владелец",
            content=content,
            filename="threshold.md",
            material_type="decision",
            status=STATUS_CONFIRMED_DECISION,
            audience=["ponder"],
        )

        # Первая регистрация
        res1 = self.registrar.register_package(pkg["package_dir"])
        self.assertTrue(res1["ok"])
        self.assertEqual(res1["status"], "registered")

        # Вторая регистрация того же пакета
        res2 = self.registrar.register_package(pkg["package_dir"])
        self.assertTrue(res2["ok"])
        self.assertEqual(res2["status"], "already_registered")

        # Проверяем, что в реестре ровно 1 запись
        registry_file = self.kb_registry_dir / "registry.json"
        registry_data = json.loads(registry_file.read_text(encoding="utf-8"))
        self.assertEqual(len(registry_data["records"]), 1)
        self.assertEqual(registry_data["records"][0]["id"], "pkg_idempotent_01")

    def test_duplicate_id_conflicting_hash_quarantined(self) -> None:
        """Повторный ID с несовпадающим хэшем или измененным контентом отправляется в карантин."""
        pkg1 = self.producer.create_package(
            material_id="pkg_collision_01",
            project="P-026",
            author="Владелец",
            content="Исходный текст нормы",
            filename="norm.md",
            material_type="decision",
            status=STATUS_CONFIRMED_DECISION,
            audience=["ponder"],
        )
        res1 = self.registrar.register_package(pkg1["package_dir"])
        self.assertTrue(res1["ok"])

        # Создаем второй пакет с тем же ID, но другим текстом
        pkg2_dir = self.outbox_dir / "pkg_collision_second"
        pkg2_dir.mkdir(parents=True, exist_ok=True)
        payload2 = pkg2_dir / "norm.md"
        payload2.write_text("Подмененный текст нормы", encoding="utf-8")
        manifest2 = copy.deepcopy(json.loads((pkg1["package_dir"] / "manifest.json").read_text(encoding="utf-8")))
        manifest2["payload_sha256"] = hashlib.sha256(payload2.read_bytes()).hexdigest()
        manifest2["payload_size"] = len(payload2.read_bytes())
        (pkg2_dir / "manifest.json").write_text(json.dumps(manifest2), encoding="utf-8")

        res2 = self.registrar.register_package(pkg2_dir)
        self.assertFalse(res2["ok"])
        self.assertEqual(res2["status"], "quarantined")
        self.assertIn("конфликт", res2["reason"].lower())

        # Реестр остался в исходном валидном состоянии (1 запись с исходным хэшем)
        registry_file = self.kb_registry_dir / "registry.json"
        registry_data = json.loads(registry_file.read_text(encoding="utf-8"))
        self.assertEqual(len(registry_data["records"]), 1)
        self.assertEqual(registry_data["records"][0]["payload_sha256"], hashlib.sha256("Исходный текст нормы".encode("utf-8")).hexdigest())

    # -------------------------------------------------------------------------
    # 5. Негативные сценарии (Fail-Closed и Карантин)
    # -------------------------------------------------------------------------

    def test_corrupted_manifest_json_quarantined(self) -> None:
        """Невалидный синтаксис JSON в манифесте отправляет пакет в карантин."""
        bad_pkg = self.outbox_dir / "pkg_bad_json"
        bad_pkg.mkdir(parents=True, exist_ok=True)
        (bad_pkg / "manifest.json").write_text("{ unclosed json ...", encoding="utf-8")
        (bad_pkg / "data.md").write_text("valid payload", encoding="utf-8")

        res = self.registrar.register_package(bad_pkg)
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "quarantined")
        self.assertIn("json", res["reason"].lower())

    def test_tampered_payload_hash_quarantined(self) -> None:
        """Несовпадение хэша полезной нагрузки отправляет пакет в карантин."""
        pkg = self.producer.create_package(
            material_id="pkg_tampered_hash",
            project="P-026",
            author="Владелец",
            content="Исходные данные",
            filename="data.md",
            material_type="draft",
            status=STATUS_DRAFT,
            audience=["ponder"],
        )
        # Модифицируем файл полезной нагрузки на диске с сохранением заявленного размера,
        # чтобы изолированно проверить именно несовпадение хэша
        manifest_file = pkg["package_dir"] / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["payload_size"] = len("Искаженные данные".encode("utf-8"))
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        (pkg["package_dir"] / "data.md").write_text("Искаженные данные", encoding="utf-8")

        res = self.registrar.register_package(pkg["package_dir"])
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "quarantined")
        self.assertIn("хэш", res["reason"].lower())

    def test_payload_size_mismatch_quarantined(self) -> None:
        """Несовпадение заявленного размера полезной нагрузки отправляет пакет в карантин."""
        pkg = self.producer.create_package(
            material_id="pkg_size_mismatch",
            project="P-026",
            author="Владелец",
            content="1234567890",
            filename="data.md",
            material_type="draft",
            status=STATUS_DRAFT,
            audience=["ponder"],
        )
        manifest_file = pkg["package_dir"] / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["payload_size"] = 999999
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

        res = self.registrar.register_package(pkg["package_dir"])
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "quarantined")
        self.assertIn("размер", res["reason"].lower())

    def test_missing_required_fields_quarantined(self) -> None:
        """Отсутствие обязательных полей манифеста отправляет пакет в карантин."""
        pkg = self.producer.create_package(
            material_id="pkg_missing_field",
            project="P-026",
            author="Владелец",
            content="test",
            filename="data.md",
            material_type="draft",
            status=STATUS_DRAFT,
            audience=["ponder"],
        )
        manifest_file = pkg["package_dir"] / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        del manifest["author"]  # Удаляем обязательное поле

        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

        res = self.registrar.register_package(pkg["package_dir"])
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "quarantined")
        self.assertIn("author", res["reason"])

    def test_invalid_status_quarantined(self) -> None:
        """Недопустимый статус разработки отправляет пакет в карантин."""
        pkg = self.producer.create_package(
            material_id="pkg_invalid_status",
            project="P-026",
            author="Владелец",
            content="test",
            filename="data.md",
            material_type="draft",
            status=STATUS_DRAFT,
            audience=["ponder"],
        )
        manifest_file = pkg["package_dir"] / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["status"] = "GD_APPROVED_FAKE"  # Недопустимый статус

        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

        res = self.registrar.register_package(pkg["package_dir"])
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "quarantined")
        self.assertIn("статус", res["reason"].lower())

    def test_invalid_timestamp_quarantined(self) -> None:
        """Невалидный timestamp (без часового пояса) отправляет пакет в карантин."""
        pkg = self.producer.create_package(
            material_id="pkg_bad_ts",
            project="P-026",
            author="Владелец",
            content="test",
            filename="data.md",
            material_type="draft",
            status=STATUS_DRAFT,
            audience=["ponder"],
        )
        manifest_file = pkg["package_dir"] / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["timestamp"] = "2026-10-19 12:00:00"  # Без таймзоны

        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

        res = self.registrar.register_package(pkg["package_dir"])
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "quarantined")
        self.assertIn("timestamp", res["reason"].lower())

    def test_symlink_payload_quarantined(self) -> None:
        """Символическая ссылка в файле полезной нагрузки строго запрещена."""
        symlink_target = self.root_path / "target_secret.txt"
        symlink_target.write_text("sensitive data", encoding="utf-8")

        pkg_dir = self.outbox_dir / "pkg_symlink"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        payload_symlink = pkg_dir / "data.md"
        payload_symlink.symlink_to(symlink_target)

        manifest = {
            "id": "pkg_symlink_01",
            "project": "P-026",
            "author": "Attacker",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "material_type": "draft",
            "version": 1,
            "parent_ref": None,
            "payload_filename": "data.md",
            "payload_sha256": hashlib.sha256(symlink_target.read_bytes()).hexdigest(),
            "payload_size": len(symlink_target.read_bytes()),
            "status": STATUS_DRAFT,
            "audience": ["ponder"],
        }
        (pkg_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        res = self.registrar.register_package(pkg_dir)
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "quarantined")
        self.assertIn("символ", res["reason"].lower())

    def test_referential_integrity_consumer_detects_tampered_disk_file(self) -> None:
        """Потребитель проверяет побайтовую целостность и выявляет искажение файла на диске."""
        content = "Исходное содержание материала."
        pkg = self.producer.create_package(
            material_id="pkg_tamper_after_reg",
            project="P-026",
            author="Владелец",
            content=content,
            filename="doc.md",
            material_type="draft",
            status=STATUS_DRAFT,
            audience=["ponder"],
        )
        res = self.registrar.register_package(pkg["package_dir"])
        self.assertTrue(res["ok"])

        # Физически портим зарегистрированный файл на диске
        disk_path = Path(res["registered_path"])
        disk_path.write_text("Испорченный текст!", encoding="utf-8")

        # Потребитель обязан выявить расхождение контрольной суммы
        with self.assertRaises(RuntimeError) as ctx:
            self.consumer.read_material("pkg_tamper_after_reg", requester_role="ponder")
        self.assertIn("целостност", str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # 6. Пакетная обработка outbox
    # -------------------------------------------------------------------------

    def test_process_outbox_batch(self) -> None:
        """Registrar обрабатывает очередь outbox пакетов (успешные регистрирует, поврежденные карантинит)."""
        # Создаем 2 валидных пакета
        pkg1 = self.producer.create_package(
            material_id="batch_pkg_01",
            project="P-026",
            author="Владелец",
            content="Содержимое пакета 1",
            filename="doc1.md",
            material_type="decision",
            status=STATUS_CONFIRMED_DECISION,
            audience=["ponder"],
        )
        pkg2 = self.producer.create_package(
            material_id="batch_pkg_02",
            project="P-026",
            author="Владелец",
            content="Содержимое пакета 2",
            filename="doc2.md",
            material_type="draft",
            status=STATUS_DRAFT,
            audience=["ponder"],
        )
        # И 1 битый пакет
        bad_pkg = self.outbox_dir / "batch_pkg_bad"
        bad_pkg.mkdir(parents=True, exist_ok=True)
        (bad_pkg / "manifest.json").write_text("INVALID JSON", encoding="utf-8")

        batch_res = self.registrar.process_outbox(self.outbox_dir)
        self.assertEqual(batch_res["total"], 3)
        self.assertEqual(batch_res["registered"], 2)
        self.assertEqual(batch_res["quarantined"], 1)

        # Проверяем, что оба валидных зарегистрированы и доступны
        p1 = self.consumer.read_material("batch_pkg_01", requester_role="ponder")
        self.assertTrue(p1["ok"])
        p2 = self.consumer.read_material("batch_pkg_02", requester_role="ponder")
        self.assertTrue(p2["ok"])

    # -------------------------------------------------------------------------
    # 7. Интеграция с P026Storage и P026Handler
    # -------------------------------------------------------------------------

    def test_storage_queue_decision_package_e2e(self) -> None:
        """P026Storage может формировать outbox-пакет из зафиксированного решения."""
        from p026_storage import P026Storage

        storage = P026Storage(base_dir=self.dramknote_state_dir)
        decision = storage.record_decision(
            author="Руководитель",
            question_context="Порог скидки РОП",
            exact_text="Установить порог скидки РОП 12.5%.",
            user_id=123,
            chat_id=-456,
        )

        pkg = storage.queue_decision_package(
            decision_id=decision["id"],
            user_id=123,
            chat_id=-456,
            audience=["ponder", "dramknote"],
        )

        self.assertTrue(pkg["package_dir"].exists())
        manifest_file = pkg["package_dir"] / "manifest.json"
        self.assertTrue(manifest_file.exists())
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], decision["id"])
        self.assertEqual(manifest["status"], STATUS_CONFIRMED_DECISION)

        # Теперь регистрируем этот пакет в общей базе
        reg_res = self.registrar.register_package(pkg["package_dir"])
        self.assertTrue(reg_res["ok"])

        # Читаем через Consumer
        mat = self.consumer.read_material(decision["id"], requester_role="ponder")
        self.assertTrue(mat["ok"])
        self.assertIn("12.5%", mat["content"])

    def test_handler_export_and_queue_development_e2e(self) -> None:
        """P026Handler экспортирует черновик и сразу ставит его в outbox разработки."""
        from p026_handler import P026Handler
        from p026_storage import P026Storage

        storage = P026Storage(base_dir=self.dramknote_state_dir)
        handler = P026Handler(storage=storage)

        # Экспорт черновика с постановкой в outbox
        res = handler.export_and_queue_development(
            doc_type="kd",
            author="Руководитель",
            user_id=555,
            chat_id=-777,
            audience=["ponder", "commercial_department"],
        )
        self.assertTrue(res["ok"])
        self.assertIn("package", res)
        pkg_dir = res["package"]["package_dir"]
        self.assertTrue(pkg_dir.exists())

        # Регистрация пакета черновика
        reg_res = self.registrar.register_package(pkg_dir)
        self.assertTrue(reg_res["ok"])
        pkg_id = res["package"]["package_id"]

        # Пондер может прочитать черновик
        ponder_draft = self.consumer.read_material(pkg_id, requester_role="ponder")
        self.assertTrue(ponder_draft["ok"])
        self.assertEqual(ponder_draft["record"]["material_type"], "draft")
        self.assertEqual(ponder_draft["record"]["status"], STATUS_DRAFT)

        # Бот «Ом» не имеет доступа
        with self.assertRaises(PermissionError):
            self.consumer.read_material(pkg_id, requester_role="om")

    def test_cli_probes_and_operations(self) -> None:
        """Проверка CLI-интерфейса доверенной синхронизации знаний."""
        from dramknote_sync_cli import run_cli

        # CLI status
        status_res = run_cli(["status", "--kb-dir", str(self.kb_dir)])
        self.assertEqual(status_res["returncode"], 0)
        self.assertIn("ok", status_res["output"].lower())


if __name__ == "__main__":
    unittest.main()
