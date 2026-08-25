from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from ..config import get_settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
DATE_ALIASES = ["날짜", "일자", "월일", "date"]
COST_ALIASES = ["광고비", "일별광고비", "광고 비용", "ad cost", "cost"]


def _norm(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _to_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(text) if text else None
    except ValueError:
        return None


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    text = re.sub(r"\([^)]*\)", "", text).strip()
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class GoogleAdSheetClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.google_service_account_info:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON이 설정되지 않았습니다.")
        creds = Credentials.from_service_account_info(
            self.settings.google_service_account_info,
            scopes=SCOPES,
        )
        self.service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    def sheet_title(self) -> str:
        meta = self.service.spreadsheets().get(
            spreadsheetId=self.settings.ad_sheet_id,
            fields="sheets(properties(sheetId,title))",
        ).execute()
        for sheet in meta.get("sheets", []):
            props = sheet.get("properties", {})
            if int(props.get("sheetId", -1)) == self.settings.ad_sheet_gid:
                return props["title"]
        raise RuntimeError(f"gid={self.settings.ad_sheet_gid} 시트를 찾지 못했습니다.")

    def fetch_daily_costs(self) -> dict[date, float]:
        title = self.sheet_title().replace("'", "''")
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.settings.ad_sheet_id,
            range=f"'{title}'!A:ZZ",
            valueRenderOption="UNFORMATTED_VALUE",
            dateTimeRenderOption="FORMATTED_STRING",
        ).execute()
        rows = result.get("values", [])
        if not rows:
            return {}

        header_idx, date_idx, cost_idx = self._detect_columns(rows)
        totals: dict[date, float] = {}
        for row in rows[header_idx + 1 :]:
            d = _to_date(row[date_idx] if date_idx < len(row) else None)
            cost = _to_number(row[cost_idx] if cost_idx < len(row) else None)
            if d and cost is not None:
                totals[d] = totals.get(d, 0.0) + cost
        return totals

    def _detect_columns(self, rows: list[list[Any]]) -> tuple[int, int, int]:
        wanted_date = _norm(self.settings.ad_sheet_date_header)
        wanted_cost = _norm(self.settings.ad_sheet_cost_header)
        date_aliases = {_norm(x) for x in DATE_ALIASES}
        cost_aliases = {_norm(x) for x in COST_ALIASES}

        for header_idx, row in enumerate(rows[:30]):
            normalized = [_norm(v) for v in row]
            date_idx = next((i for i, v in enumerate(normalized) if (wanted_date and v == wanted_date) or v in date_aliases), None)
            cost_idx = next((i for i, v in enumerate(normalized) if (wanted_cost and v == wanted_cost) or v in cost_aliases), None)
            if date_idx is not None and cost_idx is not None:
                return header_idx, date_idx, cost_idx
        raise RuntimeError(
            "광고비 시트에서 날짜/광고비 헤더를 자동 탐지하지 못했습니다. "
            "AD_SHEET_DATE_HEADER와 AD_SHEET_COST_HEADER를 실제 헤더명으로 설정하세요."
        )
