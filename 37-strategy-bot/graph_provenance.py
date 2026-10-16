"""Модуль проверки происхождения (provenance), манифеста входов и согласованности графа знаний Graphify."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class GraphProvenanceError(Exception):
    """Исключение при отказе верификации происхождения графа знаний (Fail-Closed)."""
    pass


class GraphProvenanceVerifier:
    """Проверяет неизменяемый манифест входов, целостность и согласованность представлений графа."""

    CANONICAL_BASE_COMMIT = "1e372e84d8d8bcbcb8e1ffaa8e078677fccd1ae5"
    EXPECTED_NODE_COUNT = 1365
    EXPECTED_EDGE_COUNT = 1819
    EXPECTED_SOURCES_COUNT = 178

    KEY_NEW_FILES = [
        "37-strategy-bot/test_p026_coverage_contract.py",
    ]

    KEY_MODIFIED_FILES = [
        "37-strategy-bot/README.md",
        "37-strategy-bot/p026_subject_base.py",
        "37-strategy-bot/test_p026_integration.py",
        "37-strategy-bot/test_p026_subject_base.py",
        "CHANGELOG.md",
        "DATA_MODEL.md",
        "DECISIONS.md",
        "KNOWLEDGE_BASE.md",
        "PROJECT_CONTEXT.md",
        "PROJECT_STRUCTURE.md",
    ]

    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root is None:
            self.repo_root = Path(__file__).resolve().parent.parent
        else:
            self.repo_root = Path(repo_root).resolve()
        self.graphify_dir = self.repo_root / "graphify-out"
        self.manifest_path = self.graphify_dir / "provenance.json"
        self.graph_json_path = self.graphify_dir / "graph.json"
        self.graph_report_path = self.graphify_dir / "GRAPH_REPORT.md"
        self.graph_html_path = self.graphify_dir / "graph.html"

    @staticmethod
    def compute_manifest_digest(inputs: List[Dict[str, Any]]) -> str:
        """Детерминированно вычисляет контрольную сумму SHA-256 сортированного списка входов."""
        sorted_inputs = sorted(inputs, key=lambda x: x["path"])
        canonical = [
            {"path": str(e["path"]), "sha256": str(e["sha256"]), "size": int(e["size"])}
            for e in sorted_inputs
        ]
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def load_provenance_manifest(self, manifest_file: Optional[Path] = None) -> Dict[str, Any]:
        target = manifest_file or self.manifest_path
        if not target.is_file():
            raise GraphProvenanceError(f"Манифест происхождения не найден: {target}")
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except Exception as e:
            raise GraphProvenanceError(f"Повреждён манифест происхождения: {e}") from e

    def verify_manifest_integrity(self, manifest: Optional[Dict[str, Any]] = None) -> str:
        """Проверяет внутреннюю целостность манифеста (хэш и обязательные поля)."""
        if manifest is None:
            manifest = self.load_provenance_manifest()

        if "inputs" not in manifest or not isinstance(manifest["inputs"], list):
            raise GraphProvenanceError("В манифесте отсутствует обязательный список 'inputs'")

        expected_digest = manifest.get("input_manifest_sha256")
        if not expected_digest:
            raise GraphProvenanceError("В манифесте отсутствует 'input_manifest_sha256'")

        computed_digest = self.compute_manifest_digest(manifest["inputs"])
        if computed_digest != expected_digest:
            raise GraphProvenanceError(
                f"Несовпадение дайджеста манифеста входов: вычислен {computed_digest} != заявлен {expected_digest}"
            )

        for entry in manifest["inputs"]:
            path = entry.get("path", "")
            if path.startswith("graphify-out/") or path.startswith("./graphify-out/"):
                raise GraphProvenanceError(
                    f"Обнаружен циклический самохэшинг выходов: артефакт '{path}' включён во входы"
                )

        return computed_digest

    REPO_DOCS_DYNAMIC_FILES = {
        "PROJECT_CONTEXT.md",
        "PROJECT_STRUCTURE.md",
        "PROJECT_MANIFEST.json",
        "DOCS_INDEX.md",
        "CHANGELOG.md",
        "DECISIONS.md",
        "KNOWLEDGE_BASE.md",
    }

    def verify_inputs(
        self,
        manifest: Optional[Dict[str, Any]] = None,
        source_mode: str = "base_commit",
        git_target: Optional[str] = None,
        custom_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Проверяет все входы из манифеста.
        source_mode='base_commit': проверяет наличие и побайтовое совпадение с immutable git commit.
        source_mode='disk': проверяет наличие и побайтовое совпадение с дисковым снимком.
        """
        if manifest is None:
            manifest = self.load_provenance_manifest()

        self.verify_manifest_integrity(manifest)
        inputs = manifest["inputs"]
        root = custom_root or self.repo_root
        target_commit = git_target or manifest.get("base_commit", self.CANONICAL_BASE_COMMIT)

        verified = 0
        missing = []
        mutated = []

        for entry in inputs:
            p = entry["path"]
            exp_sha = entry["sha256"]
            exp_size = entry["size"]

            if source_mode == "base_commit":
                res = subprocess.run(
                    ["git", "-C", str(root), "show", f"{target_commit}:{p}"],
                    capture_output=True,
                )
                if res.returncode != 0:
                    missing.append(p)
                    continue
                content = res.stdout
                act_sha = hashlib.sha256(content).hexdigest()
                act_size = len(content)

                if act_sha != exp_sha or act_size != exp_size:
                    mutated.append({"path": p, "expected_sha": exp_sha, "actual_sha": act_sha})
                else:
                    verified += 1
            else:
                disk_path = root / p
                if not disk_path.is_file():
                    missing.append(p)
                    continue
                content = disk_path.read_bytes()
                act_sha = hashlib.sha256(content).hexdigest()
                act_size = len(content)

                # Для неизменяемых файлов кода и нормативной базы сверяем точный хэш;
                # для динамических файлов документации, обновляемых ensure_repo_docs, допускается актуализация.
                if p not in self.REPO_DOCS_DYNAMIC_FILES:
                    if act_sha != exp_sha or act_size != exp_size:
                        mutated.append({"path": p, "expected_sha": exp_sha, "actual_sha": act_sha})
                        continue
                else:
                    if act_size == 0:
                        mutated.append({"path": p, "expected_sha": "non-empty", "actual_sha": "empty"})
                        continue
                verified += 1

        if missing:
            raise GraphProvenanceError(f"Отсутствуют заявленные входные файлы ({len(missing)}): {missing[:5]}")
        if mutated:
            raise GraphProvenanceError(f"Обнаружено несовпадение содержимого входных файлов ({len(mutated)}): {mutated[:5]}")

        input_paths = {e["path"] for e in inputs}
        for nf in self.KEY_NEW_FILES:
            if nf not in input_paths:
                raise GraphProvenanceError(f"Новый обязательный файл не отражён в манифесте: {nf}")
        for mf in self.KEY_MODIFIED_FILES:
            if mf not in input_paths:
                raise GraphProvenanceError(f"Изменённый файл не отражён в манифесте: {mf}")

        return {
            "ok": True,
            "verified_files": verified,
            "total_declared": len(inputs),
            "manifest_digest": manifest["input_manifest_sha256"],
            "base_commit": target_commit,
        }

    def verify_cross_artifact_consistency(self) -> Dict[str, Any]:
        """Проверяет взаимную согласованность graph.json, GRAPH_REPORT.md, graph.html и provenance.json."""
        manifest = self.load_provenance_manifest()
        digest = self.verify_manifest_integrity(manifest)
        base_commit = manifest.get("base_commit", self.CANONICAL_BASE_COMMIT)
        short_commit = base_commit[:8]

        # 1. Проверка graph.json
        if not self.graph_json_path.is_file():
            raise GraphProvenanceError(f"Файл graph.json не найден: {self.graph_json_path}")
        g = json.loads(self.graph_json_path.read_text(encoding="utf-8"))

        if g.get("built_at_commit") != base_commit:
            raise GraphProvenanceError(
                f"Несовпадение built_at_commit в graph.json: {g.get('built_at_commit')} != {base_commit}"
            )
        if g.get("input_manifest_sha256") != digest:
            raise GraphProvenanceError(
                f"Несовпадение input_manifest_sha256 в graph.json: {g.get('input_manifest_sha256')} != {digest}"
            )

        nodes = g.get("nodes", [])
        edges = g.get("links", g.get("edges", []))
        if len(nodes) != self.EXPECTED_NODE_COUNT:
            raise GraphProvenanceError(
                f"Несовпадение числа узлов в graph.json: {len(nodes)} != {self.EXPECTED_NODE_COUNT}"
            )
        if len(edges) != self.EXPECTED_EDGE_COUNT:
            raise GraphProvenanceError(
                f"Несовпадение числа связей в graph.json: {len(edges)} != {self.EXPECTED_EDGE_COUNT}"
            )

        input_paths = {e["path"] for e in manifest["inputs"]}
        graph_sources = {n.get("source_file") for n in nodes if n.get("source_file")}
        extra_sources = graph_sources - input_paths
        if extra_sources:
            raise GraphProvenanceError(
                f"Граф содержит узлы из необъявленных во входах файлов (extra inputs): {extra_sources}"
            )

        # 2. Проверка GRAPH_REPORT.md
        if not self.graph_report_path.is_file():
            raise GraphProvenanceError(f"Файл GRAPH_REPORT.md не найден: {self.graph_report_path}")
        report_text = self.graph_report_path.read_text(encoding="utf-8")

        if short_commit not in report_text and base_commit not in report_text:
            raise GraphProvenanceError(
                f"GRAPH_REPORT.md не содержит ссылку на базовый коммит {short_commit} / {base_commit}"
            )
        if digest not in report_text:
            raise GraphProvenanceError(
                f"GRAPH_REPORT.md не содержит дайджест манифеста входов {digest}"
            )
        if str(self.EXPECTED_NODE_COUNT) not in report_text:
            raise GraphProvenanceError(
                f"GRAPH_REPORT.md не содержит число узлов {self.EXPECTED_NODE_COUNT}"
            )
        if str(self.EXPECTED_EDGE_COUNT) not in report_text:
            raise GraphProvenanceError(
                f"GRAPH_REPORT.md не содержит число связей {self.EXPECTED_EDGE_COUNT}"
            )

        # 3. Проверка graph.html
        if not self.graph_html_path.is_file():
            raise GraphProvenanceError(f"Файл graph.html не найден: {self.graph_html_path}")
        html_text = self.graph_html_path.read_text(encoding="utf-8")

        if short_commit not in html_text and base_commit not in html_text:
            raise GraphProvenanceError(
                f"graph.html не содержит ссылку на базовый коммит {short_commit} / {base_commit}"
            )
        if digest[:8] not in html_text and digest not in html_text:
            raise GraphProvenanceError(
                f"graph.html не содержит дайджест манифеста входов {digest}"
            )
        if str(self.EXPECTED_NODE_COUNT) not in html_text:
            raise GraphProvenanceError(
                f"graph.html не содержит число узлов {self.EXPECTED_NODE_COUNT}"
            )
        if str(self.EXPECTED_EDGE_COUNT) not in html_text:
            raise GraphProvenanceError(
                f"graph.html не содержит число связей {self.EXPECTED_EDGE_COUNT}"
            )

        return {
            "ok": True,
            "base_commit": base_commit,
            "manifest_digest": digest,
            "nodes": len(nodes),
            "edges": len(edges),
            "source_files": len(graph_sources),
        }
