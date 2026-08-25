from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None:
        return str(value).strip()
    # Streamlit Community Cloud: root-level secrets를 직접 읽을 수 있게 보완.
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return str(default).strip()


def _int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = _env(name, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_timezone: str
    database_url: str
    database_schema: str
    token_encryption_key: str

    cafe24_mall_id: str
    cafe24_client_id: str
    cafe24_client_secret: str
    cafe24_redirect_uri: str
    cafe24_scopes: str
    cafe24_api_version: str
    cafe24_shop_no: int

    google_service_account_json: str
    ad_sheet_id: str
    ad_sheet_gid: int
    ad_sheet_date_header: str
    ad_sheet_cost_header: str

    sellmate_api_base_url: str
    sellmate_api_key: str
    sellmate_auth_header: str
    sellmate_inventory_endpoint: str
    sellmate_shipping_endpoint: str

    iapps_api_base_url: str
    iapps_api_key: str
    iapps_auth_header: str
    iapps_daily_endpoint: str

    season_end_date: str
    winner_min_orders: int
    winner_min_cvr: float
    recovery_min_stock: int
    detail_min_views: int
    cart_rescue_min_carts: int
    weak_cart_rate: float
    weak_cart_to_order_rate: float
    store_alert_ratio: float
    high_ad_cost_ratio: float

    @property
    def google_service_account_info(self) -> dict:
        if not self.google_service_account_json:
            return {}
        return json.loads(self.google_service_account_json)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_timezone=_env("APP_TIMEZONE", "Asia/Seoul"),
        database_url=_env("DATABASE_URL", "sqlite:///misharp_daily_report.db"),
        database_schema=_env("DATABASE_SCHEMA", "daily_report"),
        token_encryption_key=_env("TOKEN_ENCRYPTION_KEY"),
        cafe24_mall_id=_env("CAFE24_MALL_ID"),
        cafe24_client_id=_env("CAFE24_CLIENT_ID"),
        cafe24_client_secret=_env("CAFE24_CLIENT_SECRET"),
        cafe24_redirect_uri=_env("CAFE24_REDIRECT_URI"),
        cafe24_scopes=_env(
            "CAFE24_SCOPES",
            "mall.read_order mall.read_product mall.read_analytics mall.read_customer",
        ),
        cafe24_api_version=_env("CAFE24_API_VERSION", "2026-03-01"),
        cafe24_shop_no=_int("CAFE24_SHOP_NO", 1),
        google_service_account_json=_env("GOOGLE_SERVICE_ACCOUNT_JSON"),
        ad_sheet_id=_env("AD_SHEET_ID", "1LaWd3Xdjc9G86UlZ5XGNY9tciXAUMpv8w10QH_Mhd6c"),
        ad_sheet_gid=_int("AD_SHEET_GID", 1747434863),
        ad_sheet_date_header=_env("AD_SHEET_DATE_HEADER"),
        ad_sheet_cost_header=_env("AD_SHEET_COST_HEADER"),
        sellmate_api_base_url=_env("SELLMATE_API_BASE_URL"),
        sellmate_api_key=_env("SELLMATE_API_KEY"),
        sellmate_auth_header=_env("SELLMATE_AUTH_HEADER", "Authorization"),
        sellmate_inventory_endpoint=_env("SELLMATE_INVENTORY_ENDPOINT"),
        sellmate_shipping_endpoint=_env("SELLMATE_SHIPPING_ENDPOINT"),
        iapps_api_base_url=_env("IAPPS_API_BASE_URL"),
        iapps_api_key=_env("IAPPS_API_KEY"),
        iapps_auth_header=_env("IAPPS_AUTH_HEADER", "Authorization"),
        iapps_daily_endpoint=_env("IAPPS_DAILY_ENDPOINT"),
        season_end_date=_env("SEASON_END_DATE"),
        winner_min_orders=_int("WINNER_MIN_ORDERS", 2),
        winner_min_cvr=_float("WINNER_MIN_CVR", 2.0),
        recovery_min_stock=_int("RECOVERY_MIN_STOCK", 10),
        detail_min_views=_int("DETAIL_MIN_VIEWS", 50),
        cart_rescue_min_carts=_int("CART_RESCUE_MIN_CARTS", 3),
        weak_cart_rate=_float("WEAK_CART_RATE", 4.0),
        weak_cart_to_order_rate=_float("WEAK_CART_TO_ORDER_RATE", 20.0),
        store_alert_ratio=_float("STORE_ALERT_RATIO", 0.80),
        high_ad_cost_ratio=_float("HIGH_AD_COST_RATIO", 15.0),
    )
