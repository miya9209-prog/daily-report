from __future__ import annotations

import argparse
from pathlib import Path

from misharp.connectors.sera_report import parse_sera_xlsx
from misharp.db import init_db, session_scope
from misharp.repositories import finish_sync_run, insert_sera_snapshot, start_sync_run


def main() -> None:
    p = argparse.ArgumentParser(description="SERA 엑셀을 참고/검증 스냅샷으로 DB 적재")
    p.add_argument("xlsx", type=Path)
    args = p.parse_args()
    init_db()
    captured_at, records = parse_sera_xlsx(args.xlsx)
    with session_scope() as db:
        run = start_sync_run(db, "sera_reference")
        try:
            n = insert_sera_snapshot(db, captured_at, records, args.xlsx.name)
            finish_sync_run(db, run, "success", n, f"captured_at={captured_at.isoformat()}")
        except Exception as exc:
            finish_sync_run(db, run, "failed", message=str(exc)); raise
    print(f"SERA 참고 스냅샷 적재 완료: {n}개 상품 / {captured_at}")


if __name__ == "__main__": main()
