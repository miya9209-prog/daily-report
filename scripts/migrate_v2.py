from __future__ import annotations

from sqlalchemy import inspect, text

from misharp.db import DATABASE_SCHEMA, engine, init_db, qualified_table_name


def add_missing_columns(table: str, columns: dict[str, str]) -> None:
    insp = inspect(engine)
    tables = insp.get_table_names(schema=DATABASE_SCHEMA)
    if table not in tables:
        return
    existing = {x["name"] for x in insp.get_columns(table, schema=DATABASE_SCHEMA)}
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {qualified_table_name(table)} ADD COLUMN \"{name}\" {ddl}"))
                print("added", f"{DATABASE_SCHEMA + '.' if DATABASE_SCHEMA else ''}{table}", name)


def main():
    init_db()
    add_missing_columns(
        "daily_conditions",
        {
            "ad_cost_ratio": "FLOAT",
            "product_views": "INTEGER",
            "add_cart_count": "INTEGER",
            "product_order_count": "INTEGER",
            "view_to_cart_rate": "FLOAT",
            "view_to_order_rate": "FLOAT",
            "cart_to_order_rate": "FLOAT",
        },
    )
    add_missing_columns(
        "product_sales_daily",
        {
            "add_cart_count": "INTEGER",
            "add_cart_rate": "FLOAT",
            "cart_to_order_rate": "FLOAT",
            "first_buyer_count": "INTEGER",
            "repeat_buyer_count": "INTEGER",
            "decision": "VARCHAR(80)",
            "decision_reason": "VARCHAR(1000)",
        },
    )
    init_db()
    print("v2 migration complete")


if __name__ == "__main__":
    main()
