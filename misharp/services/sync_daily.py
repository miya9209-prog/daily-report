from __future__ import annotations

from datetime import date, datetime, timedelta

from ..connectors.cafe24_analytics import Cafe24AnalyticsClient
from ..connectors.cafe24_admin import Cafe24AdminClient
from ..connectors.google_adsheet import GoogleAdSheetClient
from ..connectors.iapps import IAppsClient
from ..connectors.sellmate import SellmateClient
from ..db import session_scope
from ..models import DailyCondition
from ..config import get_settings
from zoneinfo import ZoneInfo
from ..repositories import fill_missing_daily, finish_sync_run, start_sync_run, upsert_daily


def _sum(rows: list[dict], *keys: str) -> float | int | None:
    vals = []
    for row in rows:
        for key in keys:
            if row.get(key) is not None:
                vals.append(float(row[key]))
                break
    return sum(vals) if vals else None



def _local_today() -> date:
    return datetime.now(ZoneInfo(get_settings().app_timezone)).date()


def sync_cafe24_daily(day: date, fill_missing_only: bool = False) -> dict:
    client = Cafe24AnalyticsClient()
    sales = client.sales_times(day)
    visitor_rows = client.visitors(day, "day")
    page_rows = client.pageviews(day, "day")
    search_rows = client.search_visits(day)
    ad_rows = client.ad_visits(day)

    paid_amount = _sum(sales, "order_amount")
    purchase_count = _sum(sales, "order_count")
    visitors = _sum(visitor_rows, "visit_count", "count")
    pageviews = _sum(page_rows, "page_view", "count")
    search_visits = _sum(search_rows, "visit_count", "count")
    ad_visits = _sum(ad_rows, "visit_count", "count")
    avg_order_value = paid_amount / purchase_count if paid_amount is not None and purchase_count else None
    conversion_rate = purchase_count / visitors * 100 if purchase_count is not None and visitors else None

    # 미샵 정의: 웹북마크 = 전체방문 - 광고유입 - 검색방문
    bookmark_visits = None
    if visitors is not None and ad_visits is not None and search_visits is not None:
        bookmark_visits = max(int(visitors) - int(ad_visits) - int(search_visits), 0)

    # Cafe24 Admin dashboard 신규회원 수는 오늘 값만 제공하므로 오늘 수집시에만 저장한다.
    member_signups = None
    member_signup_error = None
    if day == _local_today():
        try:
            member_signups = Cafe24AdminClient().new_members_today()
        except Exception as exc:
            member_signup_error = f"{type(exc).__name__}: {exc}"[:300]

    with session_scope() as db:
        run = start_sync_run(db, "cafe24_daily")
        try:
            existing = db.get(DailyCondition, day)
            sources = dict(existing.sources or {}) if existing else {}
            sources["cafe24"] = "analytics_api"
            sources["bookmark_visits"] = "derived: visitors-ad_visits-search_visits"
            if member_signups is not None:
                sources["member_signups"] = "cafe24_admin_dashboard"
            elif member_signup_error:
                sources["member_signups_error"] = member_signup_error

            payload = dict(
                paid_amount=paid_amount,
                purchase_count=int(purchase_count) if purchase_count is not None else None,
                avg_order_value=avg_order_value,
                conversion_rate=conversion_rate,
                visitors=int(visitors) if visitors is not None else None,
                pageviews=int(pageviews) if pageviews is not None else None,
                search_visits=int(search_visits) if search_visits is not None else None,
                ad_visits=int(ad_visits) if ad_visits is not None else None,
                bookmark_visits=bookmark_visits,
                member_signups=member_signups,
            )
            if fill_missing_only:
                row = fill_missing_daily(db, day, **payload)
                merged_sources = dict(row.sources or {})
                merged_sources["cafe24_missing_fill"] = "analytics_api"
                if member_signups is not None:
                    merged_sources["member_signups"] = "cafe24_admin_dashboard"
                row.sources = merged_sources
            else:
                row = upsert_daily(db, day, **payload, sources=sources)
            finish_sync_run(
                db,
                run,
                "success",
                rows_written=1,
                message=(
                    f"member_signups={member_signups}"
                    if member_signups is not None
                    else f"member_signups=missing"
                    + (f" / {member_signup_error}" if member_signup_error else "")
                ),
            )
            return {
                "date": row.date.isoformat(),
                "status": "success",
                "fill_missing_only": fill_missing_only,
                "member_signups": member_signups,
                "member_signup_error": member_signup_error,
            }
        except Exception as exc:
            finish_sync_run(db, run, "failed", message=str(exc)); raise


def sync_google_ad_costs(
    start_day: date | None = None,
    end_day: date | None = None,
) -> int:
    """Google Sheet 광고비를 DB에 반영한다.

    start_day/end_day를 주면 해당 기간만 반영한다. 백필에서는 Cafe24를 먼저
    저장한 뒤 이 함수를 1회 호출해 실결제 기준 광고비율까지 함께 계산한다.
    Google Sheet 광고비는 미샵 DAILY REPORT의 광고비 공식 원천이므로, 기존
    일일보고 광고비가 있어도 Sheet에 같은 날짜가 있으면 Google 값을 우선한다.
    """
    if start_day and end_day and end_day < start_day:
        raise ValueError("Google 광고비 종료일은 시작일보다 빠를 수 없습니다.")

    costs = GoogleAdSheetClient().fetch_daily_costs()
    if start_day is not None:
        costs = {d: cost for d, cost in costs.items() if d >= start_day}
    if end_day is not None:
        costs = {d: cost for d, cost in costs.items() if d <= end_day}

    with session_scope() as db:
        run = start_sync_run(db, "google_adsheet")
        try:
            for day, cost in costs.items():
                existing = db.get(DailyCondition, day)
                sources = dict(existing.sources or {}) if existing else {}
                sources["ad_cost"] = "google_sheets"
                ratio = (
                    cost / existing.paid_amount * 100
                    if existing and existing.paid_amount
                    else None
                )
                upsert_daily(
                    db,
                    day,
                    ad_cost=cost,
                    ad_cost_ratio=ratio,
                    sources=sources,
                )

            range_text = (
                f"{start_day}~{end_day}"
                if start_day is not None or end_day is not None
                else "all"
            )
            finish_sync_run(
                db,
                run,
                "success",
                rows_written=len(costs),
                message=f"range={range_text}",
            )
            return len(costs)
        except Exception as exc:
            finish_sync_run(db, run, "failed", message=str(exc))
            raise


def sync_optional_daily_sources(day: date) -> None:
    # Sellmate / iApps는 실제 계정 API 명세가 세팅된 경우만 실행한다.
    try:
        ship = SellmateClient().fetch_shipping_count(day)
        if ship is not None:
            with session_scope() as db:
                run = start_sync_run(db, "sellmate")
                existing = db.get(DailyCondition, day); src = dict(existing.sources or {}) if existing else {}
                src["shipping"] = "sellmate_api"; upsert_daily(db, day, shipping_count=ship, sources=src)
                finish_sync_run(db, run, "success", rows_written=1, message="shipping_count")
    except NotImplementedError:
        pass
    try:
        stats = IAppsClient().fetch_daily_stats(day)
        with session_scope() as db:
            run = start_sync_run(db, "iapps")
            existing = db.get(DailyCondition, day); src = dict(existing.sources or {}) if existing else {}
            src["app"] = "iapps_api"; upsert_daily(db, day, **stats, sources=src)
            finish_sync_run(db, run, "success", rows_written=1)
    except NotImplementedError:
        pass


def sync_recent_daily(days: int = 7, end_day: date | None = None) -> None:
    end_day = end_day or _local_today(); start_day = end_day - timedelta(days=max(days - 1, 0))
    day = start_day
    while day <= end_day:
        sync_cafe24_daily(day); sync_optional_daily_sources(day); day += timedelta(days=1)
    sync_google_ad_costs()
