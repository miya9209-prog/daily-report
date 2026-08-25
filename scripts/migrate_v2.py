from __future__ import annotations

from sqlalchemy import inspect, text

from misharp.db import engine, init_db


def add_missing_columns(table: str, columns: dict[str, str]) -> None:
    insp = inspect(engine)
    if table not in insp.get_table_names(): return
    existing = {x["name"] for x in insp.get_columns(table)}
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                print("added", table, name)


def main():
    init_db()
    add_missing_columns("daily_conditions", {
        "ad_cost_ratio":"FLOAT", "product_views":"INTEGER", "add_cart_count":"INTEGER", "product_order_count":"INTEGER",
        "view_to_cart_rate":"FLOAT", "view_to_order_rate":"FLOAT", "cart_to_order_rate":"FLOAT",
    })
    add_missing_columns("product_sales_daily", {
        "add_cart_count":"INTEGER", "add_cart_rate":"FLOAT", "cart_to_order_rate":"FLOAT", "first_buyer_count":"INTEGER",
        "repeat_buyer_count":"INTEGER", "decision":"VARCHAR(80)", "decision_reason":"VARCHAR(1000)",
    })
    init_db(); print("v2 migration complete")

if __name__ == "__main__": main()
