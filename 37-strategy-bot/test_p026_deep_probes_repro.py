"""Воспроизведение независимых deep_probes ревизии f9ae76f8 в изолированных фикстурах."""
import asyncio
import copy
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import strategy_bot as bot
import p026_subject_base as sb
from p026_handler import P026Handler
from p026_storage import JournalCorruptionError, P026Storage


class P026DeepProbesReproTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name) / "state"
        self.storage = P026Storage(self.state_dir)
        self.handler = P026Handler(storage=self.storage)
        bot._p026_handler = self.handler

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_repro_probe_s1_runtime_gate(self):
        """S1: Отказ integrity gate останавливает модель и историю до SDK."""
        calls = []

        def model(**kw):
            calls.append({"system_instruction": kw["config"].system_instruction, "contents": kw["contents"]})
            return NS(text="OFFLINE_STUB_ANSWER")

        genai = types.ModuleType("google.genai")
        genai.Client = lambda **kw: NS(models=NS(generate_content=model))
        st = types.ModuleType("google.genai.types")
        st.GenerateContentConfig = lambda **kw: NS(**kw)
        st.Part = NS(from_bytes=lambda **kw: NS(**kw))
        genai.types = st
        google = types.ModuleType("google")
        google.genai = genai

        user_id = 999333
        bot._user_histories[user_id].clear()

        with patch.dict(sys.modules, {"google": google, "google.genai": genai, "google.genai.types": st}), \
             patch.object(bot, "get_api_key", return_value="OFFLINE-NON-CREDENTIAL"), \
             patch.object(bot, "get_strategy_context", return_value="BASE"), \
             patch.object(sb.P026SubjectBase, "verify_all_sources", side_effect=sb.SubjectBaseIntegrityError("SOURCE_TAMPERED")):

            answer = asyncio.run(bot.generate_answer("Вопрос по P-026", "A", user_id, user_id))

        self.assertEqual(0, len(calls), "При отказе целостности обращение к модели должно быть 0")
        self.assertEqual(0, len(bot._user_histories[user_id]), "История не должна обновляться")
        self.assertIn("целостност", answer.lower())

    def test_repro_probe_s2_corpus(self):
        """S2: Содержательное чтение всех 30 источников и отсутствие пропусков норм."""
        original = pathlib.Path.read_bytes
        reads = []

        def trace(p):
            reads.append(str(p))
            return original(p)

        with patch.object(pathlib.Path, "read_bytes", trace):
            ctx = sb.P026SubjectBase().get_p026_prompt_context()

        manifest_rel = [x["relative_path"] for x in sb.P026SubjectBase.CANONICAL_SOURCE_MANIFEST]
        counts = {p: reads.count("/home/roman/" + p) for p in manifest_rel}

        validation_only_files = [p for p, n in counts.items() if n <= 1]
        content_read_files = [p for p, n in counts.items() if n > 1]

        self.assertEqual([], validation_only_files, f"Файлы только для верификации: {validation_only_files}")
        self.assertEqual(30, len(content_read_files), "Все 30 файлов должны быть прочитаны более 1 раза")
        self.assertGreater(len(ctx), 100_000, "Контекст должен быть содержательным")

        evidence = []
        for entry in sb.P026SubjectBase.CANONICAL_SOURCE_MANIFEST:
            p = pathlib.Path("/home/roman") / entry["relative_path"]
            if "02_УТВЕРЖДЕНО" in str(p) or "101-commercial" in str(p):
                lines = [
                    l.strip()
                    for l in p.read_text().splitlines()
                    if len(l.strip()) > 110 and l.strip() not in ctx and not l.startswith(("#", "|", "<"))
                ]
                evidence.append({"source": entry["relative_path"], "sample_absent": lines[0] if lines else None})

        absent = [e for e in evidence if e["sample_absent"] is not None]
        self.assertEqual([], absent, f"Пропущенные нормы: {absent}")

    def test_repro_probe_s3_agreements(self):
        """S3: Общие согласия отклоняются без pending proposal; конкретная норма принимается."""
        phrases = [
            "да я согласен",
            "я согласен",
            "подтверждаю всё вышеизложенное",
            "подтверждаю всё сказанное ранее",
            "поддерживаю ваше предложение",
            "согласен с предложенным регламентом",
            "одобряю предложенный вариант",
            "Утвердить лимит скидки РОП до 12.5%",
        ]
        results = {t: self.handler.record_owner_decision("A", t, user_id=123, chat_id=123)["ok"] for t in phrases}

        self.assertTrue(results["Утвердить лимит скидки РОП до 12.5%"], "Конкретная норма должна приниматься")
        for p in phrases[:-1]:
            self.assertFalse(results[p], f"Фраза согласия '{p}' не должна приниматься как решение")

    def test_repro_probe_s5_journal_preservation_and_schema(self):
        """S5: Карантин при пустом/невалидном журнале и безопасная обработка в consumer."""
        # 1. Пустой и [{}]
        for raw in ["", "[{}]"]:
            self.storage.decisions_file.write_text(raw)
            with self.assertRaises(JournalCorruptionError):
                self.storage.record_decision("A", "Q", "NORMAL", 123, 123)
            self.assertEqual(raw, self.storage.decisions_file.read_text())
            self.assertTrue(any(p.read_text() == raw for p in self.storage.decisions_dir.glob("*.bak")))

        # 2. Невалидный timestamp "not-a-time" вызывает отказ
        raw_invalid = [{"decision_id": "x", "timestamp": "not-a-time", "context": "Q", "text": "TEXT", "user_id": 123, "chat_id": 123, "status": "active"}]
        self.storage.decisions_file.write_text(json.dumps(raw_invalid))
        with self.assertRaises(JournalCorruptionError):
            self.storage.list_decisions(123, 123)

        # Consumer не падает с необработанным исключением, возвращает safe empty
        res = bot.build_system_prompt("BASE", 123, 123)
        self.assertEqual("", res)

        # 3. Валидный timestamp с legacy-алиасами нормализуется
        raw_valid_alias = [{"decision_id": "x", "timestamp": "2026-10-15T00:00:00+00:00", "context": "Q", "text": "TEXT", "user_id": 123, "chat_id": 123, "status": "active"}]
        self.storage.decisions_file.write_text(json.dumps(raw_valid_alias))
        items = self.storage.list_decisions(123, 123)
        self.assertEqual("x", items[0]["id"])
        self.assertEqual("Q", items[0]["question_context"])
        self.assertEqual("TEXT", items[0]["exact_text"])

        # Consumer корректно строит системный промпт
        sys_prompt = bot.build_system_prompt("BASE", 123, 123)
        self.assertIn("- [x] (Q): TEXT", sys_prompt)


if __name__ == "__main__":
    unittest.main()
