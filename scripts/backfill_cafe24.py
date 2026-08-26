from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from misharp.db import init_db
from misharp.services.sync_daily import sync_cafe24_daily
from misharp.services.sync_products import sync_product_sales


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    p = argparse.ArgumentParser(description="Cafe24 누락기간 백필")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--skip-products", action="store_true")
    args = p.parse_args()

    start, end = parse_date(args.start), parse_date(args.end)
    if end < start:
        raise SystemExit("end는 start보다 빠를 수 없습니다.")
    if (end - start).days > 120:
        raise SystemExit("한 번에 최대 121일까지만 백필하세요.")

    init_db()
    d = start
    while d <= end:
        print("[Cafe24 daily]", d)
        sync_cafe24_daily(d)
        if not args.skip_products:
            print("[Cafe24 products]", d)
            sync_product_sales(d)
        d += timedelta(days=1)

    print(f"backfill complete: {start} ~ {end}")


if __name__ == "__main__":
    main()
