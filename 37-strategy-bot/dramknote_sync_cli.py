#!/usr/bin/env python3
"""CLI-утилита доверенной регистрации и версионного обмена рабочими разработками Драмкнота (FN-015)."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

from p026_knowledge_sync import (
    DEFAULT_ALLOWED_AUDIENCE,
    SharedKnowledgeConsumer,
    SharedKnowledgeRegistrar,
)


def run_cli(args: list[str]) -> dict[str, Any]:
    """Программный запуск CLI с перехватом stdout/stderr и возвратом структурированного результата."""
    parser = argparse.ArgumentParser(description="Утилита версионного обмена разработками Драмкнота (FN-015)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Проверка состояния реестра и базы знаний")
    p_status.add_argument("--kb-dir", default=None, help="Путь к корню базы знаний")

    # register
    p_reg = subparsers.add_parser("register", help="Регистрация одного пакета разработки")
    p_reg.add_argument("--package", required=True, help="Путь к каталогу пакета разработки")
    p_reg.add_argument("--kb-dir", default=None, help="Путь к корню базы знаний")

    # process-outbox
    p_proc = subparsers.add_parser("process-outbox", help="Пакетная регистрация всех пакетов из outbox")
    p_proc.add_argument("--outbox", required=True, help="Путь к каталогу outbox")
    p_proc.add_argument("--kb-dir", default=None, help="Путь к корню базы знаний")

    # list
    p_list = subparsers.add_parser("list", help="Список доступных зарегистрированных материалов")
    p_list.add_argument("--requester", default="ponder", help="Роль запрашивающего агента")
    p_list.add_argument("--project", default=None, help="Фильтр по проекту")
    p_list.add_argument("--status", default=None, help="Фильтр по статусу")
    p_list.add_argument("--type", dest="material_type", default=None, help="Фильтр по типу материала")
    p_list.add_argument("--kb-dir", default=None, help="Путь к корню базы знаний")

    # read
    p_read = subparsers.add_parser("read", help="Чтение зарегистрированного материала")
    p_read.add_argument("--id", required=True, help="ID материала в реестре")
    p_read.add_argument("--requester", default="ponder", help="Роль запрашивающего агента")
    p_read.add_argument("--kb-dir", default=None, help="Путь к корню базы знаний")

    buf = io.StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        sys.stdout = buf
        sys.stderr = buf
        parsed = parser.parse_args(args)
        cmd = parsed.command

        kb_dir = Path(parsed.kb_dir) if parsed.kb_dir else None
        registrar = SharedKnowledgeRegistrar(kb_dir=kb_dir)
        consumer = SharedKnowledgeConsumer(kb_dir=kb_dir)

        if cmd == "status":
            records = consumer.list_materials(requester_role="ponder")
            out = {
                "ok": True,
                "working_dir": str(registrar.working_dir),
                "registry_file": str(registrar.registry_file),
                "total_records": len(records),
            }
            print(json.dumps(out, ensure_ascii=False, indent=2))
            rc = 0

        elif cmd == "register":
            res = registrar.register_package(parsed.package)
            print(json.dumps(res, ensure_ascii=False, indent=2))
            rc = 0 if res.get("ok") else 1

        elif cmd == "process-outbox":
            res = registrar.process_outbox(parsed.outbox)
            print(json.dumps(res, ensure_ascii=False, indent=2))
            rc = 0

        elif cmd == "list":
            res = consumer.list_materials(
                requester_role=parsed.requester,
                project=parsed.project,
                status=parsed.status,
                material_type=parsed.material_type,
            )
            print(json.dumps(res, ensure_ascii=False, indent=2))
            rc = 0

        elif cmd == "read":
            try:
                res = consumer.read_material(material_id=parsed.id, requester_role=parsed.requester)
                print(json.dumps(res, ensure_ascii=False, indent=2))
                rc = 0
            except (PermissionError, FileNotFoundError, RuntimeError) as err:
                err_out = {"ok": False, "error": str(err)}
                print(json.dumps(err_out, ensure_ascii=False, indent=2))
                rc = 1
        else:
            rc = 2

    except SystemExit as se:
        rc = se.code if isinstance(se.code, int) else 2
    except Exception as exc:
        print(f"Ошибка выполнения CLI: {exc}")
        rc = 1
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    return {"returncode": rc, "output": buf.getvalue()}


def main() -> int:
    res = run_cli(sys.argv[1:])
    print(res["output"], end="")
    return res["returncode"]


if __name__ == "__main__":
    sys.exit(main())
