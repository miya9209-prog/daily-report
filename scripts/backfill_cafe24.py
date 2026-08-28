from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from misharp.db import init_db
from misharp.services.sync_daily import sync_cafe24_daily, sync_google_ad_costs
from misharp.services.sync_products import sync_product_sales


LEGACY_PRIMARY_END = date(2026, 5, 31)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    p = argparse.ArgumentParser(description="Cafe24 누락기간 백필")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--skip-products", action="store_true")
    p.add_argument(
        "--overwrite-legacy",
        action="store_true",
        help="2026-05-31 이전 일일보고 기준값도 Cafe24 값으로 덮어씀(기본값: 보존)",
    )
    p.add_argument(
        "--skip-google",
        action="store_true",
        help="Google 광고비 백필은 건너뜀. GitHub Actions에서는 Cafe24/Google 단계를 분리할 때 사용",
    )
    args = p.parse_args()

    start, end = parse_date(args.start), parse_date(args.end)
    if end < start:
        raise SystemExit("end는 start보다 빠를 수 없습니다.")
    if (end - start).days > 183:
        raise SystemExit("한 번에 최대 184일(약 6개월)까지만 백필하세요.")

    init_db()
    d = start
    while d <= end:
        complement_only = d <= LEGACY_PRIMARY_END and not args.overwrite_legacy
        mode = "missing-only" if complement_only else "normal"

        print(f"[Cafe24 daily:{mode}] {d}")
        sync_cafe24_daily(d, fill_missing_only=complement_only)

        if not args.skip_products:
            print(f"[Cafe24 products:{mode}] {d}")
            sync_product_sales(d, fill_missing_only=complement_only)

        d += timedelta(days=1)

    google_rows = None
    if not args.skip_google:
        print(f"[Google ad cost] {start} ~ {end}")
        google_rows = sync_google_ad_costs(start_day=start, end_day=end)
        print(f"[Google ad cost] rows={google_rows}")

    print(
        f"backfill complete: {start} ~ {end} / "
        f"legacy primary end={LEGACY_PRIMARY_END} / "
        f"overwrite_legacy={args.overwrite_legacy} / "
        f"skip_google={args.skip_google} / google_rows={google_rows}"
    )


if __name__ == "__main__":
    main()
