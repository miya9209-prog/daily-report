from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from sqlalchemy import func, select

from ..db import session_scope
from ..models import DailyCondition, HourlyCondition, InventorySnapshot, ManagementAlert, ProductSalesDaily, SeraProductSnapshot
from .recovery_engine import classify_product

DAILY_COLUMNS = {
    "date": "날짜", "paid_amount": "실결제", "ad_cost": "일별 광고비", "ad_cost_ratio": "광고비율(%)",
    "avg_order_value": "객단가", "conversion_rate": "전환율(%)", "visitors": "전체방문", "pageviews": "페이지뷰",
    "search_visits": "검색방문", "ad_visits": "광고유입", "bookmark_visits": "웹북마크",
    "app_installs": "앱 설치수", "app_unique_visits": "앱 순방문", "shipping_count": "택배수량", "member_signups": "회원가입",
    "product_views": "상품조회", "add_cart_count": "장바구니", "view_to_cart_rate": "조회→장바구니(%)",
    "product_order_count": "상품주문", "view_to_order_rate": "조회→주문(%)", "cart_to_order_rate": "장바구니→주문(%)",
}


def _derived_bookmark_visits(row: DailyCondition):
    if row.bookmark_visits is not None:
        return row.bookmark_visits
    if row.visitors is None or row.ad_visits is None or row.search_visits is None:
        return None
    return int(row.visitors) - int(row.ad_visits) - int(row.search_visits)


def daily_dataframe(start: date, end: date) -> pd.DataFrame:
    with session_scope() as db:
        rows = db.scalars(
            select(DailyCondition)
            .where(DailyCondition.date.between(start, end))
            .order_by(DailyCondition.date)
        ).all()

    records = []
    for r in rows:
        rec = {}
        for field, label in DAILY_COLUMNS.items():
            rec[label] = _derived_bookmark_visits(r) if field == "bookmark_visits" else getattr(r, field)
        records.append(rec)
    return pd.DataFrame(records, columns=list(DAILY_COLUMNS.values()))


def hourly_dataframe(start: date, end: date) -> pd.DataFrame:
    with session_scope() as db:
        rows = db.scalars(select(HourlyCondition).where(HourlyCondition.date.between(start, end)).order_by(HourlyCondition.date, HourlyCondition.hour)).all()
    return pd.DataFrame([{
        "날짜": r.date, "시간": r.hour, "매출": r.paid_amount, "주문": r.purchase_count,
        "방문": r.visitors, "페이지뷰": r.pageviews, "객단가": r.avg_order_value, "전환율(%)": r.conversion_rate,
    } for r in rows])


def _latest_inventory_map(end: date) -> dict[int, int]:
    with session_scope() as db:
        latest = db.scalar(select(InventorySnapshot.snapshot_date).where(InventorySnapshot.snapshot_date <= end).order_by(InventorySnapshot.snapshot_date.desc()).limit(1))
        if latest is None: return {}
        rows = db.scalars(select(InventorySnapshot).where(InventorySnapshot.snapshot_date == latest)).all()
    out: dict[int, int] = {}
    for r in rows:
        if r.product_no is not None: out[int(r.product_no)] = out.get(int(r.product_no), 0) + int(r.available_qty or r.stock_qty or 0)
    return out


def _latest_sera_map(end: date) -> dict[int, SeraProductSnapshot]:
    end_dt = datetime.combine(end, datetime.max.time())
    with session_scope() as db:
        latest_dt = db.scalar(select(func.max(SeraProductSnapshot.captured_at)).where(SeraProductSnapshot.captured_at <= end_dt))
        if latest_dt is None: return {}
        rows = db.scalars(select(SeraProductSnapshot).where(SeraProductSnapshot.captured_at == latest_dt)).all()
        # detached usable because expire_on_commit=False
        return {r.product_no: r for r in rows}


def product_sales_dataframe(start: date, end: date) -> pd.DataFrame:
    with session_scope() as db:
        rows = db.scalars(select(ProductSalesDaily).where(ProductSalesDaily.date.between(start, end))).all()
    if not rows: return pd.DataFrame()
    raw = pd.DataFrame([{
        "상품번호": r.product_no, "상품명": r.product_name, "판매건수": r.order_count or 0, "판매수량": r.sold_qty or 0,
        "실결제 매출": r.order_amount or 0, "상품 조회수": r.product_views or 0, "장바구니": r.add_cart_count or 0,
    } for r in rows])
    agg = raw.groupby(["상품번호", "상품명"], as_index=False).sum(numeric_only=True)
    agg["장바구니율(%)"] = agg.apply(lambda x: x["장바구니"] / x["상품 조회수"] * 100 if x["상품 조회수"] else None, axis=1)
    agg["구매전환율(%)"] = agg.apply(lambda x: x["판매건수"] / x["상품 조회수"] * 100 if x["상품 조회수"] else None, axis=1)
    agg["장바구니→주문(%)"] = agg.apply(lambda x: x["판매건수"] / x["장바구니"] * 100 if x["장바구니"] else None, axis=1)
    stocks, sera = _latest_inventory_map(end), _latest_sera_map(end)
    agg["현재고"] = agg["상품번호"].map(stocks)
    decisions = agg.apply(lambda x: classify_product(
        views=int(x["상품 조회수"] or 0), carts=int(x["장바구니"] or 0), orders=int(x["판매건수"] or 0),
        cvr=x["구매전환율(%)"], cart_rate=x["장바구니율(%)"], cart_to_order=x["장바구니→주문(%)"], stock=x["현재고"] if pd.notna(x["현재고"]) else None,
    ), axis=1)
    agg["자동판정"] = [d.decision for d in decisions]; agg["판정근거"] = [d.reason for d in decisions]
    agg["SERA 조회수"] = agg["상품번호"].map(lambda p: sera.get(int(p)).views if int(p) in sera else None)
    agg["SERA 주문수"] = agg["상품번호"].map(lambda p: sera.get(int(p)).orders if int(p) in sera else None)
    agg["SERA OpV"] = agg["상품번호"].map(lambda p: sera.get(int(p)).opv if int(p) in sera else None)
    agg["SERA ESpV"] = agg["상품번호"].map(lambda p: sera.get(int(p)).espv if int(p) in sera else None)
    return agg.sort_values("실결제 매출", ascending=False, na_position="last")


def inventory_dataframe(snapshot_date: date, season_end: date | None = None) -> pd.DataFrame:
    with session_scope() as db:
        latest = db.scalar(select(InventorySnapshot.snapshot_date).where(InventorySnapshot.snapshot_date <= snapshot_date).order_by(InventorySnapshot.snapshot_date.desc()).limit(1))
        if latest is None: return pd.DataFrame()
        rows = db.scalars(select(InventorySnapshot).where(InventorySnapshot.snapshot_date == latest).order_by(InventorySnapshot.available_qty.desc().nullslast())).all()
    df = pd.DataFrame([{
        "기준일": r.snapshot_date, "상품번호": r.product_no, "품목코드": r.variant_code, "상품명": r.product_name, "옵션": r.option_name,
        "현재고": r.stock_qty, "판매가능재고": r.available_qty, "최근7일 판매": r.sales_7d, "최근30일 판매": r.sales_30d,
        "일평균 판매": r.avg_daily_sales, "예상 소진일": r.days_of_stock, "재고상태": r.status,
    } for r in rows])
    if season_end and not df.empty:
        days_left = max((season_end - snapshot_date).days + 1, 1)
        stock = pd.to_numeric(df["판매가능재고"], errors="coerce").fillna(pd.to_numeric(df["현재고"], errors="coerce")).fillna(0)
        pace = pd.to_numeric(df["일평균 판매"], errors="coerce")
        df["시즌남은일"] = days_left
        df["필요일판매"] = stock / days_left
        df["소진속도달성률(%)"] = (pace / df["필요일판매"] * 100).where(df["필요일판매"] > 0)
        df["시즌소진판정"] = df.apply(lambda x: "가능" if pd.notna(x["소진속도달성률(%)"]) and x["소진속도달성률(%)"] >= 100 else "부족", axis=1)
    return df


def alerts_dataframe(start: date, end: date) -> pd.DataFrame:
    with session_scope() as db:
        rows = db.scalars(select(ManagementAlert).where(ManagementAlert.date.between(start, end)).order_by(ManagementAlert.date.desc(), ManagementAlert.id.desc())).all()
    return pd.DataFrame([{"날짜": r.date, "등급": r.severity, "유형": r.alert_type, "제목": r.title, "내용": r.message} for r in rows])
