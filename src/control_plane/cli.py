from __future__ import annotations

import argparse
import json
import os

from .audit import AuditLog
from .store import TaskStore


def main() -> None:
    parser = argparse.ArgumentParser(description="DS3 control-plane operational utilities")
    parser.add_argument("command", choices=["verify-audit", "init-db"])
    parser.add_argument("--database", default=os.getenv("DS3_DATABASE_PATH", "./var/control-plane.sqlite3"))
    args = parser.parse_args()
    if args.command == "init-db":
        TaskStore(args.database)
        AuditLog(args.database)
        print(json.dumps({"initialized": True, "database": args.database}))
        return
    valid, checked = AuditLog(args.database).verify_chain()
    print(json.dumps({"valid": valid, "events_checked": checked}))
    if not valid:
        raise SystemExit(2)
