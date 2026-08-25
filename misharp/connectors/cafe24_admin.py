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
        headers = {
            "Authorization": f"Bearer {get_valid_access_token()}",
            "Content-Type": "application/json",
        }
        if self.settings.cafe24_api_version:
            headers["X-Cafe24-Api-Version"] = self.settings.cafe24_api_version
        response = self.http.get(f"{self.base_url}{path}", headers=headers, params=params or {}, timeout=40)
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
