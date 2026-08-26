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

        self.assertLessEqual({f"p{i:03d}" for i in range(1, 11)}, ids)
        self.assertIn("repo_r001", ids)
        self.assertLessEqual({f"human_h{i:03d}" for i in range(1, 7)}, ids)
        self.assertLessEqual({f"doc_d{i:03d}" for i in range(1, 11)}, ids)
        self.assertLessEqual({f"adr_{i:03d}" for i in range(1, 21)}, ids)

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


if __name__ == "__main__":
    unittest.main()
