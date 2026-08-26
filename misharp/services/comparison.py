from __future__ import annotations

from datetime import date

import pandas as pd
from dateutil.relativedelta import relativedelta
from sqlalchemy import select

from ..db import session_scope
from ..models import DailyCondition

SUM_FIELDS = {
    "paid_amount": "실결제", "ad_cost": "광고비", "visitors": "전체방문", "pageviews": "페이지뷰",
    "search_visits": "검색방문", "ad_visits": "광고유입", "bookmark_visits": "웹북마크",
    "app_installs": "앱 설치수", "app_unique_visits": "앱 순방문", "shipping_count": "택배수량",
    "member_signups": "회원가입", "purchase_count": "구매건수", "product_views": "상품조회",
    "add_cart_count": "장바구니", "product_order_count": "상품주문",
}
RATE_COLS = ["전환율(%)", "광고비율(%)", "조회→장바구니(%)", "조회→주문(%)", "장바구니→주문(%)"]


def _shift(start: date, end: date, years: int):
    return start + relativedelta(years=years), end + relativedelta(years=years)


def aggregate_range(start: date, end: date) -> dict:
    with session_scope() as db:
        rows = db.scalars(select(DailyCondition).where(DailyCondition.date.between(start, end))).all()
    result = {}
    for field, label in SUM_FIELDS.items():
        vals = []
        for r in rows:
            if field == "bookmark_visits" and r.bookmark_visits is None:
                if r.visitors is not None and r.ad_visits is not None and r.search_visits is not None:
                    vals.append(int(r.visitors) - int(r.ad_visits) - int(r.search_visits))
                continue
            value = getattr(r, field)
            if value is not None:
                vals.append(value)
        result[label] = sum(vals) if vals else None
    paid, orders, visitors, ad = result.get("실결제"), result.get("구매건수"), result.get("전체방문"), result.get("광고비")
    pv, carts, porders = result.get("상품조회"), result.get("장바구니"), result.get("상품주문")
    aovs = [r.avg_order_value for r in rows if r.avg_order_value is not None]
    convs = [r.conversion_rate for r in rows if r.conversion_rate is not None]
    result["객단가"] = paid / orders if paid is not None and orders else (sum(aovs)/len(aovs) if aovs else None)
    result["전환율(%)"] = orders / visitors * 100 if orders is not None and visitors else (sum(convs)/len(convs) if convs else None)
    result["광고비율(%)"] = ad / paid * 100 if ad is not None and paid else None
    result["조회→장바구니(%)"] = carts / pv * 100 if pv and carts is not None else None
    result["조회→주문(%)"] = porders / pv * 100 if pv and porders is not None else None
    result["장바구니→주문(%)"] = porders / carts * 100 if carts and porders is not None else None
    result["조회기간"] = f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}"
    return result


def comparison_dataframe(start: date, end: date) -> pd.DataFrame:
    cur = aggregate_range(start, end); p1s, p1e = _shift(start, end, -1); p2s, p2e = _shift(start, end, -2)
    p1, p2 = aggregate_range(p1s, p1e), aggregate_range(p2s, p2e)
    base = pd.DataFrame([cur, p1, p2], index=["현재기간", "전년도 동일기간", "전전년도 동일기간"])
    rows = []
    for label, prev in [("전년 대비", p1), ("전전년 대비", p2)]:
        r = {"조회기간": label}
        for col in [c for c in base.columns if c != "조회기간"]:
            a, b = cur.get(col), prev.get(col)
            if a is None or b is None: r[col] = None
            elif col in RATE_COLS: r[col] = a - b  # %p
            elif b == 0: r[col] = None
            else: r[col] = (a / b - 1) * 100
        rows.append(r)
    growth = pd.DataFrame(rows, index=["전년 대비 증감", "전전년 대비 증감"])
    return pd.concat([base, growth])
