from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select

from ..config import get_settings
from ..db import session_scope
from ..models import DailyCondition, InventorySnapshot


@dataclass
class ProductDecision:
    decision: str
    reason: str


def classify_product(*, views: int, carts: int, orders: int, cvr: float | None, cart_rate: float | None,
                     cart_to_order: float | None, stock: int | None) -> ProductDecision:
    s = get_settings()
    if stock is not None and stock <= 1 and orders > 0:
        return ProductDecision("광고중단(재고)", "판매증거는 있으나 판매가능재고가 거의 없어 광고비 누수 위험")
    if orders >= s.winner_min_orders and (cvr or 0) >= s.winner_min_cvr:
        return ProductDecision("매출광고", f"주문 {orders}건·전환율 {(cvr or 0):.2f}%로 승자상품 조건 충족")
    if (stock or 0) >= s.recovery_min_stock and (orders > 0 or carts >= s.cart_rescue_min_carts):
        return ProductDecision("재고회수", "재고가 많고 최근 구매/장바구니 증거가 있어 콘텐츠·광고·CRM 회수 우선")
    if views >= s.detail_min_views and carts >= s.cart_rescue_min_carts and (cart_to_order or 0) < s.weak_cart_to_order_rate:
        return ProductDecision("CRM회수", "장바구니까지 왔지만 주문 전환이 약해 쿠폰·배송·사이즈불안 해소 필요")
    if views >= s.detail_min_views and (cart_rate or 0) < s.weak_cart_rate:
        return ProductDecision("상세개선", "조회는 충분하지만 장바구니 진입이 약해 상품/소재/오퍼 개선 우선")
    if views >= s.detail_min_views and carts == 0 and orders == 0:
        return ProductDecision("중단/관찰", "조회 대비 장바구니·주문이 없어 추가 유입보다 상품매력 재검토")
    return ProductDecision("관찰", "표본이 작거나 명확한 우선 액션 조건에 아직 도달하지 않음")


def latest_stock_by_product(on_or_before: date) -> dict[int, int]:
    with session_scope() as db:
        latest = db.scalar(
            select(InventorySnapshot.snapshot_date)
            .where(InventorySnapshot.snapshot_date <= on_or_before)
            .order_by(InventorySnapshot.snapshot_date.desc()).limit(1)
        )
        if latest is None:
            return {}
        rows = db.scalars(select(InventorySnapshot).where(InventorySnapshot.snapshot_date == latest)).all()
    result: dict[int, int] = {}
    for r in rows:
        if r.product_no is not None:
            result[int(r.product_no)] = result.get(int(r.product_no), 0) + int(r.available_qty or r.stock_qty or 0)
    return result


def build_store_alerts(day: date) -> list[dict]:
    s = get_settings()
    with session_scope() as db:
        current = db.get(DailyCondition, day)
        start = day - timedelta(days=7)
        history = db.scalars(
            select(DailyCondition).where(DailyCondition.date.between(start, day - timedelta(days=1)))
        ).all()
    if current is None:
        return []

    alerts: list[dict] = []
    def avg(field):
        vals = [getattr(x, field) for x in history if getattr(x, field) is not None]
        return sum(vals) / len(vals) if vals else None

    avg_visitors = avg("visitors")
    avg_conv = avg("conversion_rate")
    avg_cart = avg("view_to_cart_rate")
    if avg_visitors and current.visitors and current.visitors >= avg_visitors * 0.95 and avg_conv and current.conversion_rate is not None and current.conversion_rate < avg_conv * s.store_alert_ratio:
        alerts.append({
            "severity": "warning", "alert_type": "store_conversion",
            "title": "유입은 유지되지만 구매전환이 약합니다",
            "message": f"방문자는 최근 평균과 비슷하지만 전환율 {current.conversion_rate:.2f}%가 최근 평균 {avg_conv:.2f}%보다 낮습니다. 광고 증액보다 상품/상세/오퍼를 먼저 점검하세요.",
            "payload": {"current_conversion": current.conversion_rate, "avg_conversion": avg_conv},
        })
    if avg_cart and current.view_to_cart_rate is not None and current.view_to_cart_rate < avg_cart * s.store_alert_ratio:
        alerts.append({
            "severity": "warning", "alert_type": "store_cart",
            "title": "상품조회→장바구니 단계가 약합니다",
            "message": f"현재 장바구니율 {current.view_to_cart_rate:.2f}%가 최근 평균 {avg_cart:.2f}%보다 낮습니다. 소재·핏·가격·혜택 메시지를 우선 개선하세요.",
            "payload": {"current_cart_rate": current.view_to_cart_rate, "avg_cart_rate": avg_cart},
        })
    if current.ad_cost_ratio is not None and current.ad_cost_ratio >= s.high_ad_cost_ratio:
        alerts.append({
            "severity": "danger", "alert_type": "store_adcost",
            "title": "매출 대비 광고비 비중이 높습니다",
            "message": f"광고비율이 {current.ad_cost_ratio:.1f}%입니다. 승자상품 집중과 저효율 광고 중단을 검토하세요.",
            "payload": {"ad_cost_ratio": current.ad_cost_ratio},
        })
    return alerts
