from __future__ import annotations

from datetime import date

from ..connectors.sellmate import SellmateClient
from ..db import session_scope
from ..repositories import finish_sync_run, replace_inventory_for_day, start_sync_run


def classify_inventory(stock_qty: int | None, avg_daily_sales: float | None) -> tuple[float | None, str]:
    if stock_qty is None:
        return None, "자료없음"
    if not avg_daily_sales or avg_daily_sales <= 0:
        return None, "판매정체" if stock_qty > 0 else "품절"
    days = stock_qty / avg_daily_sales
    if days <= 7:
        status = "품절임박"
    elif days <= 30:
        status = "정상재고"
    elif days <= 60:
        status = "관찰재고"
    elif days <= 120:
        status = "과잉재고"
    else:
        status = "장기재고"
    return round(days, 1), status


def sync_sellmate_inventory(snapshot_date: date) -> int:
    client = SellmateClient()
    records = client.fetch_inventory_snapshot(snapshot_date)
    for record in records:
        days, status = classify_inventory(record.get("available_qty") or record.get("stock_qty"), record.get("avg_daily_sales"))
        record["days_of_stock"] = record.get("days_of_stock") if record.get("days_of_stock") is not None else days
        record["status"] = record.get("status") or status
        record["source"] = "sellmate"

    with session_scope() as db:
        run = start_sync_run(db, "sellmate")
        try:
            count = replace_inventory_for_day(db, snapshot_date, records)
            finish_sync_run(db, run, "success", rows_written=count)
            return count
        except Exception as exc:
            finish_sync_run(db, run, "failed", message=str(exc))
            raise
