from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, select

from .models import (
    DailyCondition, HourlyCondition, InventorySnapshot, ManagementAlert,
    OAuthState, OAuthToken, ProductSalesDaily, SeraProductSnapshot, SyncRun,
)


def upsert_daily(session, day: date, **values) -> DailyCondition:
    """날짜 기준 안전한 부분 upsert.

    Cafe24 백필/자동수집과 iApps·Sellmate 수동업로드가 같은 날짜를
    동시에 건드려도 INSERT 충돌이 나지 않도록 DB의 ON CONFLICT를 사용한다.
    전달된 값 중 None은 기존 값을 지우지 않는다.
    """
    payload = {
        key: value
        for key, value in values.items()
        if hasattr(DailyCondition, key) and value is not None
    }
    payload["updated_at"] = datetime.utcnow()

    insert_payload = {"date": day, **payload}
    # ORM Python default가 Core INSERT에서 누락되는 환경을 대비한다.
    if "sources" not in insert_payload:
        insert_payload["sources"] = {}

    dialect = session.get_bind().dialect.name

    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert

        stmt = dialect_insert(DailyCondition).values(**insert_payload)
        update_values = {
            key: getattr(stmt.excluded, key)
            for key in payload
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=[DailyCondition.date],
            set_=update_values,
        )
        session.execute(stmt)
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert

        stmt = dialect_insert(DailyCondition).values(**insert_payload)
        update_values = {
            key: getattr(stmt.excluded, key)
            for key in payload
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=[DailyCondition.date],
            set_=update_values,
        )
        session.execute(stmt)
    else:
        # 예상치 못한 DB에서도 최대한 안전하게 update-first로 처리한다.
        with session.no_autoflush:
            row = session.scalar(
                select(DailyCondition).where(DailyCondition.date == day).limit(1)
            )
        if row is None:
            row = DailyCondition(**insert_payload)
            session.add(row)
            session.flush()
        else:
            for key, value in payload.items():
                setattr(row, key, value)
            session.flush()
        return row

    # DB-native upsert 후 ORM 객체를 새로 읽어 호출부에서 sources 등을 이어서 수정한다.
    with session.no_autoflush:
        row = session.scalar(
            select(DailyCondition)
            .where(DailyCondition.date == day)
            .execution_options(populate_existing=True)
            .limit(1)
        )
    if row is None:
        raise RuntimeError(f"일별 데이터 upsert 후 재조회 실패: {day}")
    return row



def fill_missing_daily(session, day: date, **values) -> DailyCondition:
    """기존 값을 보존하고 NULL인 필드만 보충한다.

    과거 일일보고(~2026-05-31)를 기준 데이터로 유지하면서 Cafe24 백필은
    페이지뷰/상품퍼널처럼 원본에 없던 값만 채우기 위해 사용한다.
    """
    with session.no_autoflush:
        row = session.scalar(
            select(DailyCondition)
            .where(DailyCondition.date == day)
            .limit(1)
        )

    if row is None:
        return upsert_daily(session, day, **values)

    changed = False
    for key, value in values.items():
        if not hasattr(DailyCondition, key) or value is None or key == "sources":
            continue
        if getattr(row, key, None) is None:
            setattr(row, key, value)
            changed = True

    if changed:
        row.updated_at = datetime.utcnow()
        session.flush()
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
        "sellmate", "iapps", "sellmate_excel", "sellmate_shipping_excel", "iapps_excel", "legacy_excel", "sera_reference",
    ]
    rows = []
    for source in sources:
        row = session.scalar(
            select(SyncRun).where(SyncRun.source == source).order_by(SyncRun.started_at.desc()).limit(1)
        )
        if row:
            rows.append(row)
    return rows
