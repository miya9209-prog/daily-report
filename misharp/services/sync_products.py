from __future__ import annotations

from datetime import date

from ..connectors.cafe24_analytics import Cafe24AnalyticsClient
from ..db import session_scope
from ..repositories import fill_missing_daily, finish_sync_run, replace_alerts_for_day, replace_product_sales_for_day, start_sync_run, upsert_daily
from .recovery_engine import build_store_alerts, classify_product, latest_stock_by_product


def _pno(x):
    try: return int(x.get("product_no"))
    except Exception: return None


def sync_product_sales(day: date, fill_missing_only: bool = False) -> int:
    client = Cafe24AnalyticsClient()
    sales, views, carts = client.product_sales(day), client.product_views(day), client.cart_actions(day)
    sales_map = {_pno(x): x for x in sales if _pno(x) is not None}
    views_map = {_pno(x): x for x in views if _pno(x) is not None}
    carts_map = {_pno(x): x for x in carts if _pno(x) is not None}
    stock_map = latest_stock_by_product(day)
    product_nos = sorted(set(sales_map) | set(views_map) | set(carts_map))
    records = []
    for product_no in product_nos:
        s, v, c = sales_map.get(product_no, {}), views_map.get(product_no, {}), carts_map.get(product_no, {})
        name = str(s.get("product_name") or v.get("product_name") or c.get("product_name") or "")
        orders = int(s.get("order_count") or 0)
        sold = int(s.get("order_product_count") or 0)
        amount = float(s.get("order_amount") or 0)
        product_views = int(v.get("count") or c.get("count") or 0)
        add_cart = int(c.get("add_cart_count") or 0)
        cart_rate = float(c.get("add_cart_rate")) if c.get("add_cart_rate") is not None else (add_cart / product_views * 100 if product_views else None)
        cvr = orders / product_views * 100 if product_views else None
        cart_to_order = orders / add_cart * 100 if add_cart else None
        d = classify_product(views=product_views, carts=add_cart, orders=orders, cvr=cvr,
                             cart_rate=cart_rate, cart_to_order=cart_to_order, stock=stock_map.get(product_no))
        records.append({
            "product_no": product_no, "product_name": name, "order_count": orders, "sold_qty": sold,
            "order_amount": amount, "product_views": product_views, "add_cart_count": add_cart,
            "add_cart_rate": cart_rate, "conversion_rate": cvr, "cart_to_order_rate": cart_to_order,
            "decision": d.decision, "decision_reason": d.reason,
        })

    total_views = sum(r["product_views"] or 0 for r in records)
    total_carts = sum(r["add_cart_count"] or 0 for r in records)
    total_orders = sum(r["order_count"] or 0 for r in records)
    with session_scope() as db:
        run = start_sync_run(db, "cafe24_products")
        try:
            n = replace_product_sales_for_day(db, day, records)
            daily_payload = dict(
                product_views=total_views,
                add_cart_count=total_carts,
                product_order_count=total_orders,
                view_to_cart_rate=total_carts / total_views * 100 if total_views else None,
                view_to_order_rate=total_orders / total_views * 100 if total_views else None,
                cart_to_order_rate=total_orders / total_carts * 100 if total_carts else None,
            )
            daily = (
                fill_missing_daily(db, day, **daily_payload)
                if fill_missing_only
                else upsert_daily(db, day, **daily_payload)
            )
            src = dict(daily.sources or {})
            src["cafe24_products_missing_fill" if fill_missing_only else "cafe24_products"] = "analytics_api"
            daily.sources = src
            if daily.ad_cost is not None and daily.paid_amount:
                daily.ad_cost_ratio = daily.ad_cost / daily.paid_amount * 100
            finish_sync_run(db, run, "success", rows_written=n)
        except Exception as exc:
            finish_sync_run(db, run, "failed", message=str(exc)); raise

    if not fill_missing_only:
        alerts = build_store_alerts(day)
        with session_scope() as db:
            replace_alerts_for_day(db, day, "store_", alerts)
    return len(records)
