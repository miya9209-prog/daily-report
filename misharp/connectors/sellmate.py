from __future__ import annotations

from datetime import date
from typing import Any

from ..config import get_settings
from .http import resilient_session


class SellmateClient:
    """실제 셀메이트 API 명세를 받은 뒤 환경변수와 normalize 부분만 맞추는 어댑터.

    공개 페이지는 API 신청만 안내하고 상세 엔드포인트/응답 스키마는 계정별 제공이므로,
    현재 코드는 임의 엔드포인트를 발명하지 않는다.
    """

    def __init__(self) -> None:
        self.s = get_settings()
        self.http = resilient_session()

    def _headers(self) -> dict[str, str]:
        if not self.s.sellmate_api_key:
            return {}
        value = self.s.sellmate_api_key
        if self.s.sellmate_auth_header.lower() == "authorization" and not value.lower().startswith("bearer "):
            value = f"Bearer {value}"
        return {self.s.sellmate_auth_header: value}

    @staticmethod
    def _rows(payload: Any) -> list[dict]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "items", "rows", "result"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    for nested in value.values():
                        if isinstance(nested, list):
                            return nested
        return []

    def fetch_inventory_snapshot(self, snapshot_date: date) -> list[dict]:
        if not all([self.s.sellmate_api_base_url, self.s.sellmate_inventory_endpoint, self.s.sellmate_api_key]):
            raise NotImplementedError(
                "Sellmate API 미설정. docs/05_SELLMATE_IAPPS_SETUP.md의 신청/샘플응답 확보 절차를 먼저 진행하세요."
            )
        url = self.s.sellmate_api_base_url.rstrip("/") + "/" + self.s.sellmate_inventory_endpoint.lstrip("/")
        r = self.http.get(url, headers=self._headers(), params={"date": snapshot_date.isoformat()}, timeout=60)
        r.raise_for_status()
        raw = self._rows(r.json())
        # 아래 key aliases는 실제 샘플 응답을 받은 뒤 맞추면 된다.
        records = []
        for x in raw:
            variant = x.get("variant_code") or x.get("item_code") or x.get("sku") or x.get("goods_code")
            if not variant:
                continue
            records.append({
                "product_no": x.get("product_no"),
                "variant_code": str(variant),
                "product_name": str(x.get("product_name") or x.get("goods_name") or ""),
                "option_name": str(x.get("option_name") or x.get("option") or ""),
                "stock_qty": x.get("stock_qty") if x.get("stock_qty") is not None else x.get("stock"),
                "available_qty": x.get("available_qty") if x.get("available_qty") is not None else x.get("available_stock"),
                "sales_7d": x.get("sales_7d"),
                "sales_30d": x.get("sales_30d"),
                "avg_daily_sales": x.get("avg_daily_sales"),
                "days_of_stock": x.get("days_of_stock"),
                "status": x.get("status"),
            })
        return records

    def fetch_shipping_count(self, day: date) -> int | None:
        if not all([self.s.sellmate_api_base_url, self.s.sellmate_shipping_endpoint, self.s.sellmate_api_key]):
            return None
        url = self.s.sellmate_api_base_url.rstrip("/") + "/" + self.s.sellmate_shipping_endpoint.lstrip("/")
        r = self.http.get(url, headers=self._headers(), params={"date": day.isoformat()}, timeout=60)
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, dict):
            for key in ("shipping_count", "count", "total"):
                if payload.get(key) is not None:
                    return int(payload[key])
        return len(self._rows(payload))
