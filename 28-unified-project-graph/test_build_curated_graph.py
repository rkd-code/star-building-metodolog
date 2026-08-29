import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODULE_PATH = ROOT / "build_curated_graph.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_curated_graph", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CuratedGraphTests(unittest.TestCase):
    def test_contains_all_projects_and_required_entities(self):
        extraction = load_module().build_extraction()
        ids = {node["id"] for node in extraction["nodes"]}

        self.assertLessEqual({f"p{i:03d}" for i in range(1, 15)}, ids)
        self.assertIn("repo_r001", ids)
        self.assertLessEqual({f"human_h{i:03d}" for i in range(1, 7)}, ids)
        self.assertLessEqual({f"doc_d{i:03d}" for i in range(1, 16)}, ids)
        self.assertLessEqual({f"adr_{i:03d}" for i in range(1, 27)}, ids)

    def test_every_edge_references_existing_nodes(self):
        extraction = load_module().build_extraction()
        ids = {node["id"] for node in extraction["nodes"]}

        self.assertTrue(extraction["edges"])
        self.assertTrue(all(edge["source"] in ids and edge["target"] in ids for edge in extraction["edges"]))

    def test_contains_no_secret_material(self):
        serialized = json.dumps(load_module().build_extraction(), ensure_ascii=False).lower()

        self.assertNotIn("private key", serialized)
        self.assertNotIn("bot_token=", serialized)
        self.assertNotIn("api_key=", serialized)
        self.assertNotIn("password=", serialized)

    def test_normalization_collapses_duplicate_project_ids_and_redirects_edges(self):
        module = load_module()
        data = {
            "nodes": [
                {"id": "semantic-p008", "label": "P-008 — Маркетинговые помощники"},
                {"id": "curated-p008", "label": "P-008 — Маркетинговые помощники Star Building", "current_status": "проверено"},
                {"id": "other", "label": "Другой узел"},
            ],
            "links": [
                {"source": "semantic-p008", "target": "other", "relation": "uses"},
                {"source": "curated-p008", "target": "other", "relation": "uses"},
            ],
            "hyperedges": [{"id": "h", "nodes": ["semantic-p008", "other"]}],
        }

        normalized = module.normalize_graph_data(data)
        project_nodes = [n for n in normalized["nodes"] if n["label"].startswith("P-008")]

        self.assertEqual(["curated-p008"], [n["id"] for n in project_nodes])
        self.assertTrue(all(edge["source"] == "curated-p008" for edge in normalized["links"]))
        self.assertEqual("curated-p008", normalized["hyperedges"][0]["nodes"][0])

    def test_normalization_also_collapses_duplicate_registry_entities(self):
        module = load_module()
        data = {
            "nodes": [
                {"id": "old-person", "label": "H-001 — лорд Витинари"},
                {"id": "new-person", "label": "H-001 — лорд Витинари", "verification": "verified"},
                {"id": "old-adr", "label": "ADR-022 — Сервис тестирования"},
                {"id": "new-adr", "label": "ADR-022 — Сервис тестирования", "verification": "verified"},
                {"id": "project", "label": "P-011 — Экзаменатор", "current_status": "концепция"},
            ],
            "links": [
                {"source": "old-person", "target": "project", "relation": "owns"},
                {"source": "old-adr", "target": "project", "relation": "governs"},
            ],
        }
        normalized = module.normalize_graph_data(data)
        labels = [node["label"] for node in normalized["nodes"]]

        self.assertEqual(1, labels.count("H-001 — лорд Витинари"))
        self.assertEqual(1, labels.count("ADR-022 — Сервис тестирования"))
        self.assertEqual("new-person", normalized["links"][0]["source"])
        self.assertEqual("new-adr", normalized["links"][1]["source"])


if __name__ == "__main__":
    unittest.main()
