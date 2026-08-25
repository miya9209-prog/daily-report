from __future__ import annotations

from datetime import date

from ..connectors.cafe24_analytics import Cafe24AnalyticsClient
from ..db import session_scope
from ..repositories import finish_sync_run, replace_hourly_for_day, start_sync_run


def _hour(row: dict) -> int | None:
    for key in ("hour", "time"):
        v = row.get(key)
        if v is not None:
            try:
                return int(str(v).split(":")[0][-2:])
            except Exception:
                return None
    return None


def sync_hourly(day: date) -> int:
    c = Cafe24AnalyticsClient()
    sales, visits, pvs = c.sales_times(day), c.visitors(day, "hour"), c.pageviews(day, "hour")
    by_hour: dict[int, dict] = {h: {"hour": h} for h in range(24)}
    for x in sales:
        h = _hour(x)
        if h is not None:
            by_hour[h]["paid_amount"] = float(x.get("order_amount") or 0)
            by_hour[h]["purchase_count"] = int(x.get("order_count") or 0)
    for x in visits:
        h = _hour(x)
        if h is not None: by_hour[h]["visitors"] = int(x.get("visit_count") or x.get("count") or 0)
    for x in pvs:
        h = _hour(x)
        if h is not None: by_hour[h]["pageviews"] = int(x.get("page_view") or x.get("count") or 0)
    records = []
    for h, rec in by_hour.items():
        if len(rec) == 1:
            continue
        paid, orders, visitors = rec.get("paid_amount"), rec.get("purchase_count"), rec.get("visitors")
        rec["avg_order_value"] = paid / orders if paid is not None and orders else None
        rec["conversion_rate"] = orders / visitors * 100 if orders is not None and visitors else None
        records.append(rec)
    with session_scope() as db:
        run = start_sync_run(db, "cafe24_hourly")
        try:
            n = replace_hourly_for_day(db, day, records); finish_sync_run(db, run, "success", n); return n
        except Exception as exc:
            finish_sync_run(db, run, "failed", message=str(exc)); raise
