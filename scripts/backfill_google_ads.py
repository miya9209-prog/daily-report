from __future__ import annotations

import argparse
import os
from datetime import date, datetime

from misharp.db import init_db
from misharp.services.sync_daily import sync_google_ad_costs


REQUIRED_ENV = (
    "DATABASE_URL",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "AD_SHEET_ID",
    "AD_SHEET_GID",
    "AD_SHEET_DATE_HEADER",
    "AD_SHEET_COST_HEADER",
)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    p = argparse.ArgumentParser(description="Google Sheet 광고비 기간 백필")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    args = p.parse_args()

    start, end = parse_date(args.start), parse_date(args.end)
    if end < start:
        raise SystemExit("end는 start보다 빠를 수 없습니다.")

    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        raise SystemExit(
            "Google 광고비 백필에 필요한 GitHub Actions Secret/환경변수가 없습니다: "
            + ", ".join(missing)
            + ". .github/workflows/backfill.yml 또는 backfill_google_ads.yml이 최신인지 확인하세요."
        )

    print(f"[Google preflight] OK / range={start}~{end}")
    init_db()
    rows = sync_google_ad_costs(start_day=start, end_day=end)
    print(f"[Google ad cost] rows={rows}")
    print(f"google ad cost backfill complete: {start} ~ {end}")


if __name__ == "__main__":
    main()
