"""Комплексные тесты происхождения и целостности графа знаний (FN-014 / P1 PROVENANCE)."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graph_provenance import GraphProvenanceError, GraphProvenanceVerifier


class TestGraphProvenance(unittest.TestCase):
    """Тесты архитектурного инварианта происхождения графа знаний Graphify."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.verifier = GraphProvenanceVerifier(repo_root=self.repo_root)

    def test_canonical_manifest_integrity(self) -> None:
        """Позитивный тест: дайджест канонического манифеста совпадает и цикличность отсутствует."""
        digest = self.verifier.verify_manifest_integrity()
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)

    def test_canonical_inputs_verification_against_base_commit(self) -> None:
        """Позитивный тест: все 178 входов реально существуют в базовом коммите 1e372e8 и побайтово совпадают."""
        res = self.verifier.verify_inputs(source_mode="base_commit")
        self.assertTrue(res["ok"])
        self.assertEqual(res["verified_files"], 178)
        self.assertEqual(res["base_commit"], "1e372e84d8d8bcbcb8e1ffaa8e078677fccd1ae5")

    def test_canonical_cross_artifact_consistency(self) -> None:
        """Позитивный тест: graph.json, GRAPH_REPORT.md, graph.html и provenance.json строго согласованы."""
        res = self.verifier.verify_cross_artifact_consistency()
        self.assertTrue(res["ok"])
        self.assertEqual(res["nodes"], 1365)
        self.assertEqual(res["edges"], 1819)
        self.assertEqual(res["source_files"], 178)

    def test_new_file_and_10_modified_files_accounted_for(self) -> None:
        """Инвариант P1: новый файл test_p026_coverage_contract.py и 10 измененных файлов учтены во входах."""
        manifest = self.verifier.load_provenance_manifest()
        accounted_new = manifest.get("accounted_new_files", [])
        accounted_mod = manifest.get("accounted_modified_files", [])

        self.assertIn("37-strategy-bot/test_p026_coverage_contract.py", accounted_new)
        for mf in GraphProvenanceVerifier.KEY_MODIFIED_FILES:
            self.assertIn(mf, accounted_mod)

        input_paths = {e["path"] for e in manifest["inputs"]}
        self.assertIn("37-strategy-bot/test_p026_coverage_contract.py", input_paths)
        for mf in GraphProvenanceVerifier.KEY_MODIFIED_FILES:
            self.assertIn(mf, input_paths)

    def test_tampered_manifest_digest_fails_closed(self) -> None:
        """Fail-Closed: модификация дайджеста манифеста немедленно вызывает GraphProvenanceError."""
        manifest = self.verifier.load_provenance_manifest()
        tampered = copy.deepcopy(manifest)
        tampered["input_manifest_sha256"] = "0" * 64

        with self.assertRaises(GraphProvenanceError) as ctx:
            self.verifier.verify_manifest_integrity(tampered)
        self.assertIn("Несовпадение дайджеста манифеста", str(ctx.exception))

    def test_missing_input_file_fails_closed(self) -> None:
        """Fail-Closed: отсутствие заявленного входного файла вызывает отказ до приёмки."""
        manifest = self.verifier.load_provenance_manifest()
        tampered = copy.deepcopy(manifest)
        tampered["inputs"].append({
            "path": "non_existent_file_fixture_probe.md",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "size": 0,
        })
        tampered["input_manifest_sha256"] = GraphProvenanceVerifier.compute_manifest_digest(tampered["inputs"])

        with self.assertRaises(GraphProvenanceError) as ctx:
            self.verifier.verify_inputs(manifest=tampered, source_mode="base_commit")
        self.assertIn("Отсутствуют заявленные входные файлы", str(ctx.exception))

    def test_mutated_input_file_fails_closed(self) -> None:
        """Fail-Closed: искажение контрольной суммы входного файла вызывает отказ."""
        manifest = self.verifier.load_provenance_manifest()
        tampered = copy.deepcopy(manifest)
        tampered["inputs"][0]["sha256"] = "f" * 64
        if "base_commit_sha256" in tampered["inputs"][0]:
            tampered["inputs"][0]["base_commit_sha256"] = "f" * 64
        tampered["input_manifest_sha256"] = GraphProvenanceVerifier.compute_manifest_digest(tampered["inputs"])

        with self.assertRaises(GraphProvenanceError) as ctx:
            self.verifier.verify_inputs(manifest=tampered, source_mode="base_commit")
        self.assertIn("Обнаружено несовпадение содержимого", str(ctx.exception))

        with self.assertRaises(GraphProvenanceError) as ctx_disk:
            self.verifier.verify_inputs(manifest=tampered, source_mode="disk")
        self.assertIn("Обнаружено несовпадение содержимого", str(ctx_disk.exception))

    def test_cyclic_self_hashing_forbidden(self) -> None:
        """Fail-Closed: включение выходных файлов graphify-out/* во входы категорически запрещено."""
        manifest = self.verifier.load_provenance_manifest()
        tampered = copy.deepcopy(manifest)
        tampered["inputs"].append({
            "path": "graphify-out/graph.json",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "size": 0,
        })
        tampered["input_manifest_sha256"] = GraphProvenanceVerifier.compute_manifest_digest(tampered["inputs"])

        with self.assertRaises(GraphProvenanceError) as ctx:
            self.verifier.verify_manifest_integrity(tampered)
        self.assertIn("циклический самохэшинг", str(ctx.exception))

    def test_extra_graph_source_fails_closed(self) -> None:
        """Fail-Closed: появление в графе узлов из незаявленных источников отвергается."""
        with tempfile.TemporaryDirectory() as td:
            tmp_root = Path(td)
            out_dir = tmp_root / "graphify-out"
            out_dir.mkdir(parents=True)

            # Копируем манифест
            manifest = self.verifier.load_provenance_manifest()
            (out_dir / "provenance.json").write_text(json.dumps(manifest), encoding="utf-8")

            # Копируем graph.json с подменой источника узла на незаявленный
            g = json.loads(self.verifier.graph_json_path.read_text(encoding="utf-8"))
            g["nodes"][0]["source_file"] = "phantom_untracked_source.py"
            (out_dir / "graph.json").write_text(json.dumps(g), encoding="utf-8")
            (out_dir / "GRAPH_REPORT.md").write_text(self.verifier.graph_report_path.read_text(encoding="utf-8"), encoding="utf-8")
            (out_dir / "graph.html").write_text(self.verifier.graph_html_path.read_text(encoding="utf-8"), encoding="utf-8")

            verifier = GraphProvenanceVerifier(repo_root=tmp_root)
            with self.assertRaises(GraphProvenanceError) as ctx:
                verifier.verify_cross_artifact_consistency()
            self.assertIn("extra inputs", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
