from __future__ import annotations

from datetime import date

from ..config import get_settings
from .http import resilient_session


class IAppsClient:
    """아이앱스 외부 API 명세를 받으면 환경변수/필드매핑만 맞추는 어댑터."""

    def __init__(self) -> None:
        self.s = get_settings()
        self.http = resilient_session()

    def fetch_daily_stats(self, day: date) -> dict:
        if not all([self.s.iapps_api_base_url, self.s.iapps_daily_endpoint, self.s.iapps_api_key]):
            raise NotImplementedError(
                "iApps 외부 통계 API 미설정. docs/05_SELLMATE_IAPPS_SETUP.md를 참고해 API 또는 자동 Sheet export를 확정하세요."
            )
        value = self.s.iapps_api_key
        if self.s.iapps_auth_header.lower() == "authorization" and not value.lower().startswith("bearer "):
            value = f"Bearer {value}"
        url = self.s.iapps_api_base_url.rstrip("/") + "/" + self.s.iapps_daily_endpoint.lstrip("/")
        r = self.http.get(url, headers={self.s.iapps_auth_header: value}, params={"date": day.isoformat()}, timeout=60)
        r.raise_for_status()
        p = r.json()
        if isinstance(p, dict) and isinstance(p.get("data"), dict):
            p = p["data"]
        return {
            "app_installs": p.get("app_installs") or p.get("installs") or p.get("install_count"),
            "app_unique_visits": p.get("app_unique_visits") or p.get("unique_visitors") or p.get("dau"),
        }
