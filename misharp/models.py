from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class DailyCondition(Base):
    __tablename__ = "daily_conditions"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    paid_amount: Mapped[Optional[float]] = mapped_column(Float)
    ad_cost: Mapped[Optional[float]] = mapped_column(Float)
    ad_cost_ratio: Mapped[Optional[float]] = mapped_column(Float)
    purchase_count: Mapped[Optional[int]] = mapped_column(Integer)
    avg_order_value: Mapped[Optional[float]] = mapped_column(Float)
    conversion_rate: Mapped[Optional[float]] = mapped_column(Float)
    visitors: Mapped[Optional[int]] = mapped_column(Integer)
    pageviews: Mapped[Optional[int]] = mapped_column(Integer)
    search_visits: Mapped[Optional[int]] = mapped_column(Integer)
    ad_visits: Mapped[Optional[int]] = mapped_column(Integer)
    bookmark_visits: Mapped[Optional[int]] = mapped_column(Integer)
    app_installs: Mapped[Optional[int]] = mapped_column(Integer)
    app_unique_visits: Mapped[Optional[int]] = mapped_column(Integer)
    shipping_count: Mapped[Optional[int]] = mapped_column(Integer)
    member_signups: Mapped[Optional[int]] = mapped_column(Integer)
    product_views: Mapped[Optional[int]] = mapped_column(Integer)
    add_cart_count: Mapped[Optional[int]] = mapped_column(Integer)
    product_order_count: Mapped[Optional[int]] = mapped_column(Integer)
    view_to_cart_rate: Mapped[Optional[float]] = mapped_column(Float)
    view_to_order_rate: Mapped[Optional[float]] = mapped_column(Float)
    cart_to_order_rate: Mapped[Optional[float]] = mapped_column(Float)
    sources: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HourlyCondition(Base):
    __tablename__ = "hourly_conditions"
    __table_args__ = (UniqueConstraint("date", "hour", name="uq_hourly_conditions"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    hour: Mapped[int] = mapped_column(Integer, index=True)
    paid_amount: Mapped[Optional[float]] = mapped_column(Float)
    purchase_count: Mapped[Optional[int]] = mapped_column(Integer)
    visitors: Mapped[Optional[int]] = mapped_column(Integer)
    pageviews: Mapped[Optional[int]] = mapped_column(Integer)
    avg_order_value: Mapped[Optional[float]] = mapped_column(Float)
    conversion_rate: Mapped[Optional[float]] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductSalesDaily(Base):
    __tablename__ = "product_sales_daily"
    __table_args__ = (UniqueConstraint("date", "product_no", name="uq_product_sales_daily"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    product_no: Mapped[int] = mapped_column(Integer, index=True)
    product_name: Mapped[str] = mapped_column(String(500), default="")
    order_count: Mapped[Optional[int]] = mapped_column(Integer)
    sold_qty: Mapped[Optional[int]] = mapped_column(Integer)
    order_amount: Mapped[Optional[float]] = mapped_column(Float)
    product_views: Mapped[Optional[int]] = mapped_column(Integer)
    add_cart_count: Mapped[Optional[int]] = mapped_column(Integer)
    add_cart_rate: Mapped[Optional[float]] = mapped_column(Float)
    conversion_rate: Mapped[Optional[float]] = mapped_column(Float)
    cart_to_order_rate: Mapped[Optional[float]] = mapped_column(Float)
    first_buyer_count: Mapped[Optional[int]] = mapped_column(Integer)
    repeat_buyer_count: Mapped[Optional[int]] = mapped_column(Integer)
    decision: Mapped[Optional[str]] = mapped_column(String(80))
    decision_reason: Mapped[Optional[str]] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_date", "variant_code", name="uq_inventory_snapshot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    product_no: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    variant_code: Mapped[str] = mapped_column(String(100), index=True)
    product_name: Mapped[str] = mapped_column(String(500), default="")
    option_name: Mapped[str] = mapped_column(String(500), default="")
    stock_qty: Mapped[Optional[int]] = mapped_column(Integer)
    available_qty: Mapped[Optional[int]] = mapped_column(Integer)
    sales_7d: Mapped[Optional[int]] = mapped_column(Integer)
    sales_30d: Mapped[Optional[int]] = mapped_column(Integer)
    avg_daily_sales: Mapped[Optional[float]] = mapped_column(Float)
    days_of_stock: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(50), default="sellmate")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SeraProductSnapshot(Base):
    __tablename__ = "sera_product_snapshots"
    __table_args__ = (UniqueConstraint("captured_at", "product_no", name="uq_sera_snapshot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    product_no: Mapped[int] = mapped_column(Integer, index=True)
    product_code: Mapped[Optional[str]] = mapped_column(String(100))
    product_name: Mapped[str] = mapped_column(String(500), default="")
    price: Mapped[Optional[float]] = mapped_column(Float)
    views: Mapped[Optional[int]] = mapped_column(Integer)
    views_pc: Mapped[Optional[int]] = mapped_column(Integer)
    views_mobile: Mapped[Optional[int]] = mapped_column(Integer)
    orders: Mapped[Optional[int]] = mapped_column(Integer)
    orders_pc: Mapped[Optional[int]] = mapped_column(Integer)
    orders_mobile: Mapped[Optional[int]] = mapped_column(Integer)
    opv: Mapped[Optional[float]] = mapped_column(Float)
    espv: Mapped[Optional[float]] = mapped_column(Float)
    detail_path: Mapped[Optional[str]] = mapped_column(Text)
    source_file: Mapped[Optional[str]] = mapped_column(String(500))


class ManagementAlert(Base):
    __tablename__ = "management_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    alert_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str] = mapped_column(Text)
    related_product_no: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MarketingAction(Base):
    __tablename__ = "marketing_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    channel: Mapped[str] = mapped_column(String(50))
    target: Mapped[Optional[str]] = mapped_column(String(300))
    message: Mapped[Optional[str]] = mapped_column(Text)
    sent_count: Mapped[Optional[int]] = mapped_column(Integer)
    related_product_no: Mapped[Optional[int]] = mapped_column(Integer)
    note: Mapped[Optional[str]] = mapped_column(Text)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"
    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OAuthState(Base):
    __tablename__ = "oauth_states"
    state: Mapped[str] = mapped_column(String(200), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class SyncRun(Base):
    __tablename__ = "sync_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), default="running")
    rows_written: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[Optional[str]] = mapped_column(Text)
