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

    @staticmethod
    def _find_key_recursive(node: Any, key: str) -> Any:
        """Cafe24 응답이 dict/list 어느 형태여도 원하는 키를 찾는다."""
        if isinstance(node, dict):
            if key in node:
                return node.get(key)
            for value in node.values():
                found = Cafe24AdminClient._find_key_recursive(value, key)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = Cafe24AdminClient._find_key_recursive(item, key)
                if found is not None:
                    return found
        return None

    def new_members_today(self) -> int | None:
        payload = self.dashboard()
        value = self._find_key_recursive(payload, "new_members_count")
        if value is None:
            return None

        # 숫자 자체이거나 문자열인 일반 응답
        try:
            return int(float(value))
        except (TypeError, ValueError):
            pass

        # 혹시 객체 안에 count/value 형태로 감싸져 있는 경우까지 대응
        if isinstance(value, dict):
            for candidate_key in ("count", "value", "today", "current"):
                candidate = value.get(candidate_key)
                if candidate is None:
                    continue
                try:
                    return int(float(candidate))
                except (TypeError, ValueError):
                    continue
        return None

    def new_members_debug(self) -> dict:
        """신규회원 API 진단용. 비밀값 없이 응답 구조와 해석 결과만 반환한다."""
        payload = self.dashboard()
        value = self._find_key_recursive(payload, "new_members_count")

        def _shape(node: Any):
            if isinstance(node, dict):
                return {
                    "type": "dict",
                    "keys": list(node.keys())[:30],
                }
            if isinstance(node, list):
                first = node[0] if node else None
                return {
                    "type": "list",
                    "length": len(node),
                    "first_type": type(first).__name__ if first is not None else None,
                    "first_keys": list(first.keys())[:30] if isinstance(first, dict) else None,
                }
            return {"type": type(node).__name__}

        parsed = None
        if value is not None:
            try:
                parsed = int(float(value))
            except (TypeError, ValueError):
                if isinstance(value, dict):
                    for candidate_key in ("count", "value", "today", "current"):
                        candidate = value.get(candidate_key)
                        if candidate is None:
                            continue
                        try:
                            parsed = int(float(candidate))
                            break
                        except (TypeError, ValueError):
                            continue

        return {
            "parsed_new_members_count": parsed,
            "raw_new_members_value": value,
            "response_shape": _shape(payload),
        }
