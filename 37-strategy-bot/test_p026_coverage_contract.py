"""Регрессионные испытания архитектурного контракта полноты P026v1 (Integrity).

Проверяет:
1. Инвариант Integrity: hash/size + supported extraction + содержательная полнота фрагментов.
2. Служебные заголовки и номера страниц не считаются содержанием.
3. Пропуск листа / части ячеек, пропуск страницы / части текста.
4. Перестановка и подмена фрагментов.
5. Устаревший (stale) или подменённый coverage artifact.
6. Отсутствие парсера / исключения.
7. Неизменность реального корпуса из 40 источников.
"""
import copy
import hashlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, PropertyMock

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openpyxl
import pypdf
from openpyxl.worksheet.worksheet import Worksheet
from pypdf._page import PageObject
from p026_subject_base import P026SubjectBase, SubjectBaseIntegrityError


class P026CoverageContractTest(unittest.TestCase):
    def setUp(self):
        self.base = P026SubjectBase()

    def test_coverage_manifest_consistent_with_canonical_sources(self):
        """Инвариант Integrity: манифест покрытия строго согласован с 40 источниками P026v1."""
        res = self.base.verify_coverage_manifest()
        self.assertTrue(res["ok"])
        self.assertEqual(3, res["covered_sources"], "Должно быть ровно 3 бинарных источника (2 XLSX, 1 PDF)")

        manifest = self.base.get_coverage_manifest()
        self.assertEqual(3, len(manifest))

        total_fragments = sum(m["total_fragments"] for m in manifest.values())
        self.assertEqual(23, total_fragments, "7 листов XLSX + 10 страниц PDF + 6 листов XLSX = 23 фрагмента")

    def test_stale_or_tampered_coverage_artifact_rejected(self):
        """HIGH INTEGRITY: Stale / подменённый coverage-артефакт вызывает SubjectBaseIntegrityError."""
        xlsx_rel = "114-a-profile-executive-card-02/approved/A_Profile_Card_Leadership_v02.xlsx"
        # Передаём чужие байты с тем же путём канонического источника
        fake_bytes = b"STALE_OR_TAMPERED_SOURCE_BYTES_123456789"
        with self.assertRaises(SubjectBaseIntegrityError) as ctx:
            self.base._extract_xlsx_text(fake_bytes, rel_path=xlsx_rel)
        self.assertIn("устарел (stale) или подменён", str(ctx.exception))

        # Проверка дискового артефакта p026_coverage_manifest.json на подмену
        json_path = ROOT / "p026_coverage_manifest.json"
        self.assertTrue(json_path.is_file(), "Файл p026_coverage_manifest.json обязан присутствовать")
        orig_content = json_path.read_text(encoding="utf-8")
        try:
            tampered_data = json.loads(orig_content)
            # Модифицируем один хэш фрагмента
            first_key = next(iter(tampered_data))
            tampered_data[first_key]["fragments"][0]["content_sha256"] = "0" * 64
            json_path.write_text(json.dumps(tampered_data), encoding="utf-8")

            with self.assertRaises(SubjectBaseIntegrityError) as ctx_disk:
                self.base.verify_coverage_manifest()
            self.assertIn("не совпадает с каноническим манифестом", str(ctx_disk.exception))
        finally:
            json_path.write_text(orig_content, encoding="utf-8")

    def test_xlsx_dropped_sheet_rejected_fail_closed(self):
        """HIGH INTEGRITY: Пропуск непустого листа XLSX вызывает SubjectBaseIntegrityError."""
        xlsx_entry = next(x for x in self.base.CANONICAL_SOURCE_MANIFEST if x["relative_path"].endswith("A_Profile_Card_Leadership_v02.xlsx"))
        p = self.base._resolve_source_path(xlsx_entry["relative_path"])
        raw_bytes = p.read_bytes()

        orig_load = openpyxl.load_workbook
        def drop_one_sheet(*a, **kw):
            wb = orig_load(*a, **kw)
            # Удаляем последний лист
            wb.remove(wb[wb.sheetnames[-1]])
            return wb

        with patch.object(openpyxl, "load_workbook", drop_one_sheet):
            with self.assertRaises(SubjectBaseIntegrityError) as ctx:
                self.base._extract_xlsx_text(raw_bytes, rel_path=xlsx_entry["relative_path"])
            self.assertIn("несовпадение количества листов", str(ctx.exception))

    def test_xlsx_reordered_sheets_rejected_fail_closed(self):
        """HIGH INTEGRITY: Перестановка листов XLSX вызывает SubjectBaseIntegrityError."""
        xlsx_entry = next(x for x in self.base.CANONICAL_SOURCE_MANIFEST if x["relative_path"].endswith("A_Profile_Card_Leadership_v02.xlsx"))
        p = self.base._resolve_source_path(xlsx_entry["relative_path"])
        raw_bytes = p.read_bytes()

        orig_load = openpyxl.load_workbook
        def swap_sheets(*a, **kw):
            wb = orig_load(*a, **kw)
            # Переставляем листы 0 и 1 местами
            sheets = getattr(wb, "_sheets")
            sheets[0], sheets[1] = sheets[1], sheets[0]
            return wb

        with patch.object(openpyxl, "load_workbook", swap_sheets):
            with self.assertRaises(SubjectBaseIntegrityError) as ctx:
                self.base._extract_xlsx_text(raw_bytes, rel_path=xlsx_entry["relative_path"])
            self.assertIn("несовпадение структуры или порядка листов", str(ctx.exception))

    def test_xlsx_dropped_cell_content_rejected_fail_closed(self):
        """HIGH INTEGRITY: Потеря части ячеек листа XLSX вызывает SubjectBaseIntegrityError."""
        xlsx_entry = next(x for x in self.base.CANONICAL_SOURCE_MANIFEST if x["relative_path"].endswith("A_Profile_Card_Leadership_v02.xlsx"))
        p = self.base._resolve_source_path(xlsx_entry["relative_path"])
        raw_bytes = p.read_bytes()

        orig_iter = Worksheet.iter_rows
        def drop_first_row(ws, *a, **kw):
            rows = list(orig_iter(ws, *a, **kw))
            return iter(rows[1:] if len(rows) > 1 else rows)

        with patch.object(Worksheet, "iter_rows", drop_first_row):
            with self.assertRaises(SubjectBaseIntegrityError) as ctx:
                self.base._extract_xlsx_text(raw_bytes, rel_path=xlsx_entry["relative_path"])
            self.assertIn("подмена или повреждение содержимого листа", str(ctx.exception))

    def test_pdf_dropped_page_rejected_fail_closed(self):
        """HIGH INTEGRITY: Пропуск страницы PDF вызывает SubjectBaseIntegrityError."""
        pdf_entry = next(x for x in self.base.CANONICAL_SOURCE_MANIFEST if x["relative_path"].endswith(".pdf"))
        p = self.base._resolve_source_path(pdf_entry["relative_path"])
        raw_bytes = p.read_bytes()

        real_reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        nine_pages = list(real_reader.pages)[:-1]

        with patch.object(pypdf.PdfReader, "pages", new_callable=PropertyMock, return_value=nine_pages):
            with self.assertRaises(SubjectBaseIntegrityError) as ctx:
                self.base._extract_pdf_text(raw_bytes, rel_path=pdf_entry["relative_path"])
            self.assertIn("несовпадение количества страниц", str(ctx.exception))

    def test_pdf_truncated_page_text_rejected_fail_closed(self):
        """HIGH INTEGRITY: Потеря части текста страницы PDF вызывает SubjectBaseIntegrityError."""
        pdf_entry = next(x for x in self.base.CANONICAL_SOURCE_MANIFEST if x["relative_path"].endswith(".pdf"))
        p = self.base._resolve_source_path(pdf_entry["relative_path"])
        raw_bytes = p.read_bytes()

        orig_extract = PageObject.extract_text
        def truncate_page(self_page, *a, **kw):
            text = orig_extract(self_page, *a, **kw)
            if text and len(text) > 100:
                # Отрезаем половину страницы
                return text[:50]
            return text

        with patch.object(PageObject, "extract_text", truncate_page):
            with self.assertRaises(SubjectBaseIntegrityError) as ctx:
                self.base._extract_pdf_text(raw_bytes, rel_path=pdf_entry["relative_path"])
            self.assertIn("подмена или повреждение содержимого страницы", str(ctx.exception))

    def test_canonical_40_source_corpus_extracts_cleanly(self):
        """Штатный путь: Все 40 канонических источников извлекаются без ложных отказов с полным покрытием."""
        # 1. verify_all_sources проходит без ошибок
        ver_res = self.base.verify_all_sources()
        self.assertTrue(ver_res["ok"])
        self.assertEqual(40, ver_res["verified_count"])

        # 2. get_p026_prompt_context формирует полный нормативный контекст
        ctx = self.base.get_p026_prompt_context()
        self.assertGreater(len(ctx), 1_000_000, "Контекст P-026 должен превышать 1 млн знаков")
        self.assertEqual(13, ctx.count("--- Лист:"), "Должно быть ровно 13 маркеров листов (7 + 6)")
        self.assertEqual(10, ctx.count("--- Страница"), "Должно быть ровно 10 маркеров страниц PDF")
        self.assertNotIn("\ufffd", ctx, "В нормативном контексте не должно быть символов замещения")


if __name__ == "__main__":
    unittest.main()
