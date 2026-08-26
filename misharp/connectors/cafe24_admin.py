from __future__ import annotations

from typing import Any

from ..config import get_settings
from .cafe24_oauth import get_valid_access_token
from .http import resilient_session


class Cafe24AdminClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = resilient_session()

    @property
    def base_url(self) -> str:
        return f"https://{self.settings.cafe24_mall_id}.cafe24api.com/api/v2/admin"

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        def _headers(token: str) -> dict[str, str]:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            if self.settings.cafe24_api_version:
                headers["X-Cafe24-Api-Version"] = self.settings.cafe24_api_version
            return headers

        url = f"{self.base_url}{path}"
        response = self.http.get(
            url,
            headers=_headers(get_valid_access_token()),
            params=params or {},
            timeout=40,
        )
        if response.status_code == 401:
            response = self.http.get(
                url,
                headers=_headers(get_valid_access_token(force_refresh=True)),
                params=params or {},
                timeout=40,
            )
        response.raise_for_status()
        return response.json()

    def products(self, *, limit: int = 100, offset: int = 0, **params) -> dict:
        return self.get("/products", {"limit": min(limit, 100), "offset": offset, **params})

    def orders(self, *, limit: int = 100, offset: int = 0, **params) -> dict:
        return self.get("/orders", {"limit": min(limit, 100), "offset": offset, **params})

    def variants(self, product_no: int, *, limit: int = 100, offset: int = 0) -> dict:
        return self.get(f"/products/{product_no}/variants", {"limit": min(limit, 100), "offset": offset})

    def inventory(self, product_no: int, variant_code: str) -> dict:
        return self.get(f"/products/{product_no}/variants/{variant_code}/inventories")


    def dashboard(self) -> dict:
        """Cafe24 Admin 대시보드 조회. scope: mall.read_store"""
        return self.get("/dashboard", {"shop_no": self.settings.cafe24_shop_no})

    def new_members_today(self) -> int | None:
        payload = self.dashboard()
        data = payload.get("dashboard", payload)
        if not isinstance(data, dict):
            return None
        value = data.get("new_members_count")
        if value is None:
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
