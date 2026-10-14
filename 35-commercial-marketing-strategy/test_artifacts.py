import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class StrategyArtifactsTest(unittest.TestCase):
    def test_required_outputs_exist_and_are_nonempty(self):
        expected = {
            "star_building_strategy.docx": 20_000,
            "star_building_strategy_presentation.pptx": 20_000,
            "strategy_graph.html": 10_000,
            "strategy_mindmap.html": 8_000,
            "strategy_mindmap.excalidraw": 10_000,
        }
        for name, minimum in expected.items():
            path = ROOT / name
            self.assertTrue(path.exists(), name)
            self.assertGreater(path.stat().st_size, minimum, name)

    def test_graph_integrity(self):
        data = json.loads((ROOT / "strategy_graph.json").read_text(encoding="utf-8"))
        ids = [n["id"] for n in data["nodes"]]
        self.assertEqual(len(ids), len(set(ids)))
        known = set(ids)
        self.assertGreaterEqual(len(ids), 40)
        self.assertGreaterEqual(len(data["edges"]), 45)
        for edge in data["edges"]:
            self.assertIn(edge["source"], known)
            self.assertIn(edge["target"], known)
            self.assertNotEqual(edge["source"], edge["target"])

    def test_strategy_contains_decision_ready_sections(self):
        text = (ROOT / "STRATEGY.md").read_text(encoding="utf-8")
        for phrase in (
            "600 тонн",
            "500 тонн",
            "Коммерческий директор",
            "Менеджер по тендерам",
            "Новый B2B-менеджер",
            "Астана",
            "Midjourney",
            "Битрикс24",
            "Решения для утверждения Генеральным директором",
        ):
            self.assertIn(phrase, text)

    def test_graph_html_is_autonomous(self):
        for name in ("strategy_graph.html", "strategy_mindmap.html"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("<script src=", text)
            self.assertNotIn("<link rel=", text)
            self.assertIn("<!doctype html>", text.lower())

    def test_excalidraw_has_bound_text(self):
        data = json.loads((ROOT / "strategy_mindmap.excalidraw").read_text(encoding="utf-8"))
        self.assertEqual(data["type"], "excalidraw")
        shapes = [e for e in data["elements"] if e["type"] in {"rectangle", "ellipse"}]
        texts = [e for e in data["elements"] if e["type"] == "text"]
        self.assertGreaterEqual(len(shapes), 20)
        self.assertTrue(any(t.get("containerId") for t in texts))


if __name__ == "__main__":
    unittest.main()
