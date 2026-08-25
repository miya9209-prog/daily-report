from __future__ import annotations

from datetime import date
from typing import Any

from ..config import get_settings
from .cafe24_oauth import get_valid_access_token
from .http import polite_pause, resilient_session


class Cafe24AnalyticsClient:
    base_url = "https://ca-api.cafe24data.com"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = resilient_session()

    @staticmethod
    def _extract_items(payload: Any) -> list[dict]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ("data", "result", "items", "resource"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for nested in value.values():
                    if isinstance(nested, list):
                        return nested
        for value in payload.values():
            if isinstance(value, list):
                return value
        return []

    def get_all(self, path: str, params: dict[str, Any], *, limit: int = 1000) -> list[dict]:
        base_params = {
            "mall_id": self.settings.cafe24_mall_id,
            "shop_no": self.settings.cafe24_shop_no,
            "timezone": self.settings.app_timezone,
            "locale": "ko-KR",
            **params,
        }
        rows: list[dict] = []
        offset = 0
        while True:
            req = {**base_params, "limit": min(limit, 1000), "offset": offset}
            headers = {"Authorization": f"Bearer {get_valid_access_token()}"}
            response = self.http.get(f"{self.base_url}{path}", headers=headers, params=req, timeout=40)
            if response.status_code == 429:
                polite_pause(2.2)
                continue
            response.raise_for_status()
            chunk = self._extract_items(response.json())
            rows.extend(chunk)
            if len(chunk) < req["limit"]:
                break
            offset += req["limit"]
            polite_pause()
        return rows

    @staticmethod
    def _date_params(day: date) -> dict[str, str]:
        d = day.isoformat()
        return {"start_date": d, "end_date": d, "device_type": "total"}

    def sales_times(self, day: date) -> list[dict]:
        return self.get_all("/sales/times", self._date_params(day))

    def visitors(self, day: date, format_type: str = "day") -> list[dict]:
        return self.get_all("/visitors/view", {**self._date_params(day), "format_type": format_type})

    def pageviews(self, day: date, format_type: str = "day") -> list[dict]:
        return self.get_all("/visitors/pageview", {**self._date_params(day), "format_type": format_type})

    def search_visits(self, day: date) -> list[dict]:
        return self.get_all("/visitpaths/keywords", self._date_params(day))

    def ad_visits(self, day: date) -> list[dict]:
        return self.get_all("/visitpaths/ads", self._date_params(day))

    def product_sales(self, day: date) -> list[dict]:
        return self.get_all("/products/sales", {**self._date_params(day), "sort": "order_amount", "order": "desc"})

    def product_views(self, day: date) -> list[dict]:
        return self.get_all("/products/view", {**self._date_params(day), "sort": "count", "order": "desc"})

    def cart_actions(self, day: date) -> list[dict]:
        return self.get_all("/carts/action", self._date_params(day))
