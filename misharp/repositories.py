from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, select

from .models import (
    DailyCondition, HourlyCondition, InventorySnapshot, ManagementAlert,
    OAuthState, OAuthToken, ProductSalesDaily, SeraProductSnapshot, SyncRun,
)


def upsert_daily(session, day: date, **values) -> DailyCondition:
    row = session.get(DailyCondition, day)
    if row is None:
        row = DailyCondition(date=day)
        session.add(row)
    for key, value in values.items():
        if hasattr(row, key) and value is not None:
            setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    return row


def replace_hourly_for_day(session, day: date, records: list[dict]) -> int:
    session.execute(delete(HourlyCondition).where(HourlyCondition.date == day))
    for rec in records:
        session.add(HourlyCondition(date=day, **rec))
    return len(records)


def replace_product_sales_for_day(session, day: date, records: list[dict]) -> int:
    session.execute(delete(ProductSalesDaily).where(ProductSalesDaily.date == day))
    for rec in records:
        session.add(ProductSalesDaily(date=day, **rec))
    return len(records)


def replace_inventory_for_day(session, day: date, records: list[dict]) -> int:
    session.execute(delete(InventorySnapshot).where(InventorySnapshot.snapshot_date == day))
    for rec in records:
        session.add(InventorySnapshot(snapshot_date=day, **rec))
    return len(records)


def replace_alerts_for_day(session, day: date, alert_type_prefix: str, records: list[dict]) -> int:
    session.execute(
        delete(ManagementAlert).where(
            ManagementAlert.date == day,
            ManagementAlert.alert_type.like(f"{alert_type_prefix}%"),
        )
    )
    for rec in records:
        session.add(ManagementAlert(date=day, **rec))
    return len(records)


def insert_sera_snapshot(session, captured_at: datetime, records: list[dict], source_file: str) -> int:
    count = 0
    for rec in records:
        product_no = rec.get("product_no")
        if product_no is None:
            continue
        existing = session.scalar(
            select(SeraProductSnapshot).where(
                SeraProductSnapshot.captured_at == captured_at,
                SeraProductSnapshot.product_no == int(product_no),
            )
        )
        payload = {**rec, "source_file": source_file}
        if existing:
            for k, v in payload.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
        else:
            session.add(SeraProductSnapshot(captured_at=captured_at, **payload))
        count += 1
    return count


def save_token(session, provider: str, encrypted_payload: str) -> None:
    row = session.get(OAuthToken, provider)
    if row is None:
        session.add(OAuthToken(provider=provider, encrypted_payload=encrypted_payload))
    else:
        row.encrypted_payload = encrypted_payload
        row.updated_at = datetime.utcnow()


def get_token(session, provider: str) -> OAuthToken | None:
    return session.get(OAuthToken, provider)


def save_oauth_state(session, state: str, expires_at: datetime) -> None:
    session.add(OAuthState(state=state, expires_at=expires_at))


def consume_oauth_state(session, state: str) -> bool:
    row = session.get(OAuthState, state)
    now = datetime.utcnow()
    if row is None or row.used_at is not None or row.expires_at < now:
        return False
    row.used_at = now
    return True


def start_sync_run(session, source: str) -> SyncRun:
    row = SyncRun(source=source, status="running")
    session.add(row)
    session.flush()
    return row


def finish_sync_run(session, run: SyncRun, status: str, rows_written: int = 0, message: str = "") -> None:
    run.finished_at = datetime.utcnow()
    run.status = status
    run.rows_written = rows_written
    run.message = message[:4000] if message else None


def latest_sync_runs(session) -> list[SyncRun]:
    sources = [
        "cafe24_daily", "cafe24_products", "cafe24_hourly", "google_adsheet",
        "sellmate", "iapps", "sellmate_excel", "iapps_excel", "sera_reference",
    ]
    rows = []
    for source in sources:
        row = session.scalar(
            select(SyncRun).where(SyncRun.source == source).order_by(SyncRun.started_at.desc()).limit(1)
        )
        if row:
            rows.append(row)
    return rows
