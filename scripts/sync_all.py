from __future__ import annotations

import argparse
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from misharp.config import get_settings
from misharp.db import init_db
from misharp.services.sync_daily import sync_cafe24_daily, sync_google_ad_costs, sync_optional_daily_sources
from misharp.services.sync_hourly import sync_hourly
from misharp.services.sync_inventory import sync_sellmate_inventory
from misharp.services.sync_products import sync_product_sales


def local_today() -> date:
    from datetime import datetime
    return datetime.now(ZoneInfo(get_settings().app_timezone)).date()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=1)
    p.add_argument("--skip-hourly", action="store_true")
    p.add_argument("--skip-products", action="store_true")
    p.add_argument("--skip-adsheet", action="store_true")
    p.add_argument("--inventory", action="store_true", help="셀메이트 재고 스냅샷 수집")
    args = p.parse_args(); init_db()
    end = local_today(); start = end - timedelta(days=max(args.days-1, 0)); d = start
    while d <= end:
        print("[Cafe24 daily]", d); sync_cafe24_daily(d)
        if not args.skip_products: print("[Cafe24 products]", d); sync_product_sales(d)
        sync_optional_daily_sources(d)
        d += timedelta(days=1)
    if not args.skip_hourly: print("[Cafe24 hourly]", end); sync_hourly(end)
    if not args.skip_adsheet: print("[Google ad sheet]"); print(sync_google_ad_costs(), "dates updated")
    if args.inventory:
        try:
            print("[Sellmate inventory]", end); print(sync_sellmate_inventory(end), "inventory rows updated")
        except NotImplementedError as exc:
            print("[Sellmate inventory skipped]", exc)


if __name__ == "__main__": main()
