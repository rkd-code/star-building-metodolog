#!/usr/bin/env python3
"""CLI-утилита проверки происхождения графа знаний Graphify."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_module_path = REPO_ROOT / "37-strategy-bot" / "graph_provenance.py"
_spec = importlib.util.spec_from_file_location("graph_provenance", _module_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load module from {_module_path}")
_gp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gp)

GraphProvenanceError = _gp.GraphProvenanceError
GraphProvenanceVerifier = _gp.GraphProvenanceVerifier


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка происхождения графа знаний Graphify")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="Корень репозитория")
    parser.add_argument("--check", action="store_true", help="Строгий режим проверки (возврат rc!=0 при ошибке)")
    parser.add_argument("--source-mode", default="base_commit", choices=["base_commit", "disk"], help="Режим проверки источников")
    args = parser.parse_args()

    verifier = GraphProvenanceVerifier(repo_root=Path(args.repo))

    try:
        manifest_res = verifier.verify_manifest_integrity()
        consistency_res = verifier.verify_cross_artifact_consistency()
        inputs_res = verifier.verify_inputs(source_mode=args.source_mode)

        output = {
            "ok": True,
            "manifest_digest": manifest_res,
            "verified_files": inputs_res["verified_files"],
            "base_commit": consistency_res["base_commit"],
            "nodes": consistency_res["nodes"],
            "edges": consistency_res["edges"],
            "artifacts_agreed": True,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except GraphProvenanceError as e:
        error_output = {
            "ok": False,
            "error": str(e),
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except Exception as e:
        error_output = {
            "ok": False,
            "error": f"Непредвиденная ошибка: {e}",
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
