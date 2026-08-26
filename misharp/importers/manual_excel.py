from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO, StringIO
import hashlib
import re
from typing import Any

import pandas as pd
from sqlalchemy import func, select

from ..db import session_scope
from ..models import ProductSalesDaily
from ..repositories import (
    finish_sync_run,
    replace_inventory_for_day,
    start_sync_run,
    upsert_daily,
)


def _norm(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("\r", " ").strip().lower()
    return re.sub(r"[\s_\-()/\\]+", "", text)


def _alias_set(*items: str) -> set[str]:
    return {_norm(x) for x in items}


SELLMATE_ALIASES = {
    "product_no": _alias_set("상품번호", "카페24상품번호", "쇼핑몰상품번호", "product_no", "product no"),
    "variant_code": _alias_set(
        "품목코드", "옵션코드", "자체품목코드", "재고관리코드", "sku", "item code", "item_code",
        "상품코드", "품번", "goods_code",
    ),
    "product_name": _alias_set("상품명", "품명", "goods_name", "product_name", "상품"),
    "option_name": _alias_set("옵션", "옵션명", "옵션정보", "품목명", "option", "option_name", "옵션값"),
    "stock_qty": _alias_set(
        "현재고", "실재고", "재고", "재고수량", "실재고수량", "보유재고", "stock", "stock_qty",
        "현재재고", "총재고",
    ),
    "available_qty": _alias_set(
        "판매가능재고", "판매가능수량", "가용재고", "가용수량", "available_stock", "available_qty",
    ),
}

IAPPS_ALIASES = {
    "date": _alias_set("일자", "날짜", "기준일", "date", "ymd", "통계일", "통계일자"),
    "app_installs": _alias_set(
        "앱설치수", "앱 설치수", "설치수", "신규설치", "신규 설치", "신규설치수", "install", "installs",
        "installcount",
    ),
    "app_unique_visits": _alias_set(
        "앱순방문", "앱 순방문", "순방문", "순방문자", "순방문자수", "dau", "dailyactiveusers",
        "uniquevisitors", "unique visitors", "일순방문",
    ),
}


@dataclass
class ParsedUpload:
    frame: pd.DataFrame
    mapping: dict[str, str | None]
    sheet_name: str
    header_row: int


def _read_csv(data: bytes) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(StringIO(data.decode(enc)), header=None)
        except Exception:
            continue
    raise ValueError("CSV 인코딩을 읽지 못했습니다.")


def _sheet_candidates(data: bytes, filename: str):
    lower = filename.lower()
    if lower.endswith(".csv"):
        yield "CSV", _read_csv(data)
        return

    excel = pd.ExcelFile(BytesIO(data))
    for sheet in excel.sheet_names:
        try:
            raw = pd.read_excel(excel, sheet_name=sheet, header=None)
        except Exception:
            continue
        if raw.empty:
            continue
        yield sheet, raw


def _find_header(raw: pd.DataFrame, aliases: dict[str, set[str]], required: set[str]) -> tuple[int, dict[str, str | None]] | None:
    max_rows = min(len(raw), 35)
    for r in range(max_rows):
        row = raw.iloc[r].tolist()
        seen = {_norm(v): str(v).strip() for v in row if pd.notna(v) and str(v).strip()}
        mapping: dict[str, str | None] = {}
        hits: set[str] = set()
        for field, names in aliases.items():
            found = next((original for normed, original in seen.items() if normed in names), None)
            mapping[field] = found
            if found is not None:
                hits.add(field)
        if required.issubset(hits):
            return r, mapping
    return None


def _parse_with_aliases(
    data: bytes,
    filename: str,
    aliases: dict[str, set[str]],
    required_sets: list[set[str]],
) -> ParsedUpload:
    diagnostics: list[str] = []
    for sheet_name, raw in _sheet_candidates(data, filename):
        for required in required_sets:
            found = _find_header(raw, aliases, required)
            if not found:
                continue
            header_row, mapping = found
            headers = [str(x).strip() if pd.notna(x) else f"__blank_{i}" for i, x in enumerate(raw.iloc[header_row].tolist())]
            frame = raw.iloc[header_row + 1 :].copy()
            frame.columns = headers
            frame = frame.dropna(how="all").reset_index(drop=True)
            return ParsedUpload(frame=frame, mapping=mapping, sheet_name=sheet_name, header_row=header_row + 1)
        diagnostics.append(f"{sheet_name}: 헤더 자동탐지 실패")
    raise ValueError("파일에서 필요한 헤더를 찾지 못했습니다. " + " / ".join(diagnostics))


def _to_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "--"}:
        return None
    try:
        return int(round(float(text)))
    except Exception:
        digits = re.sub(r"[^0-9.-]", "", text)
        try:
            return int(round(float(digits))) if digits else None
        except Exception:
            return None


def _to_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if hasattr(value, "date") and not isinstance(value, str):
        try:
            return value.date()
        except Exception:
            pass
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"\([^)]*\)", "", text).strip()
    parsed = pd.to_datetime(text, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _stable_variant(product_name: str, option_name: str) -> str:
    raw = f"{product_name}|{option_name}".encode("utf-8")
    return "manual-" + hashlib.sha1(raw).hexdigest()[:20]


def preview_sellmate_inventory(data: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, str | None], str]:
    parsed = _parse_with_aliases(
        data,
        filename,
        SELLMATE_ALIASES,
        required_sets=[{"stock_qty", "product_name"}, {"stock_qty", "variant_code"}, {"available_qty", "product_name"}],
    )
    m = parsed.mapping
    rows = []
    for _, r in parsed.frame.iterrows():
        product_name = str(r.get(m.get("product_name"), "") or "").strip() if m.get("product_name") else ""
        option_name = str(r.get(m.get("option_name"), "") or "").strip() if m.get("option_name") else ""
        variant = str(r.get(m.get("variant_code"), "") or "").strip() if m.get("variant_code") else ""
        stock = _to_int(r.get(m.get("stock_qty"))) if m.get("stock_qty") else None
        available = _to_int(r.get(m.get("available_qty"))) if m.get("available_qty") else None
        if stock is None:
            stock = available
        if available is None:
            available = stock
        if stock is None and available is None:
            continue
        if not product_name and not variant:
            continue
        pno = _to_int(r.get(m.get("product_no"))) if m.get("product_no") else None
        if not variant:
            variant = _stable_variant(product_name, option_name)
        rows.append({
            "product_no": pno,
            "variant_code": variant[:100],
            "product_name": product_name[:500],
            "option_name": option_name[:500],
            "stock_qty": stock,
            "available_qty": available,
        })
    if not rows:
        raise ValueError("재고 행을 찾지 못했습니다. 파일의 상품명/품목코드/재고 컬럼을 확인해주세요.")
    return pd.DataFrame(rows), m, parsed.sheet_name


def _sales_maps(snapshot_date: date, product_nos: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    if not product_nos:
        return {}, {}
    start30 = snapshot_date - timedelta(days=29)
    start7 = snapshot_date - timedelta(days=6)
    with session_scope() as db:
        rows30 = db.execute(
            select(ProductSalesDaily.product_no, func.sum(ProductSalesDaily.sold_qty))
            .where(ProductSalesDaily.product_no.in_(product_nos), ProductSalesDaily.date.between(start30, snapshot_date))
            .group_by(ProductSalesDaily.product_no)
        ).all()
        rows7 = db.execute(
            select(ProductSalesDaily.product_no, func.sum(ProductSalesDaily.sold_qty))
            .where(ProductSalesDaily.product_no.in_(product_nos), ProductSalesDaily.date.between(start7, snapshot_date))
            .group_by(ProductSalesDaily.product_no)
        ).all()
    return ({int(k): int(v or 0) for k, v in rows7}, {int(k): int(v or 0) for k, v in rows30})


def import_sellmate_inventory(data: bytes, filename: str, snapshot_date: date) -> int:
    preview, _, _ = preview_sellmate_inventory(data, filename)
    pnos = sorted({int(x) for x in preview["product_no"].dropna().tolist()})
    sales7, sales30 = _sales_maps(snapshot_date, pnos)

    records: list[dict] = []
    for r in preview.to_dict("records"):
        pno = int(r["product_no"]) if pd.notna(r.get("product_no")) else None
        s7 = sales7.get(pno) if pno is not None else None
        s30 = sales30.get(pno) if pno is not None else None
        avg = None
        if s7 is not None and s7 > 0:
            avg = s7 / 7.0
        elif s30 is not None and s30 > 0:
            avg = s30 / 30.0
        stock = r.get("available_qty") if r.get("available_qty") is not None else r.get("stock_qty")
        days = (stock / avg) if stock is not None and avg and avg > 0 else None
        if stock is None:
            status = "자료없음"
        elif stock <= 0:
            status = "재고없음"
        elif avg is None:
            status = "판매데이터없음"
        elif days is not None and days <= 7:
            status = "품절임박"
        elif days is not None and days <= 30:
            status = "정상재고"
        elif days is not None and days <= 60:
            status = "관찰재고"
        elif days is not None and days <= 120:
            status = "과잉재고"
        else:
            status = "장기재고"
        records.append({
            **r,
            "sales_7d": s7,
            "sales_30d": s30,
            "avg_daily_sales": round(avg, 2) if avg is not None else None,
            "days_of_stock": round(days, 2) if days is not None else None,
            "status": status,
            "source": "sellmate_excel",
        })

    with session_scope() as db:
        run = start_sync_run(db, "sellmate_excel")
        try:
            count = replace_inventory_for_day(db, snapshot_date, records)
            finish_sync_run(db, run, "success", rows_written=count, message=f"{filename} / {snapshot_date.isoformat()}")
            return count
        except Exception as exc:
            finish_sync_run(db, run, "failed", message=str(exc))
            raise


def preview_iapps_daily(data: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, str | None], str]:
    parsed = _parse_with_aliases(
        data,
        filename,
        IAPPS_ALIASES,
        required_sets=[{"date", "app_installs"}, {"date", "app_unique_visits"}],
    )
    m = parsed.mapping
    rows = []
    for _, r in parsed.frame.iterrows():
        d = _to_date(r.get(m.get("date"))) if m.get("date") else None
        if d is None:
            continue
        installs = _to_int(r.get(m.get("app_installs"))) if m.get("app_installs") else None
        dau = _to_int(r.get(m.get("app_unique_visits"))) if m.get("app_unique_visits") else None
        if installs is None and dau is None:
            continue
        rows.append({"날짜": d, "앱 설치수": installs, "앱 순방문": dau})
    if not rows:
        raise ValueError("일자별 앱 통계 행을 찾지 못했습니다.")
    frame = pd.DataFrame(rows)
    # 같은 날짜가 여러 번 있으면 설치수는 합계, DAU는 가장 큰 값으로 보수적으로 처리.
    grouped = frame.groupby("날짜", as_index=False).agg({"앱 설치수": "sum", "앱 순방문": "max"})
    return grouped, m, parsed.sheet_name


def import_iapps_daily(data: bytes, filename: str) -> int:
    preview, _, _ = preview_iapps_daily(data, filename)
    with session_scope() as db:
        run = start_sync_run(db, "iapps_excel")
        try:
            count = 0
            for r in preview.to_dict("records"):
                d = r["날짜"]
                row = upsert_daily(
                    db,
                    d,
                    app_installs=_to_int(r.get("앱 설치수")),
                    app_unique_visits=_to_int(r.get("앱 순방문")),
                )
                sources = dict(row.sources or {})
                sources["iapps_excel"] = {"file": filename}
                row.sources = sources
                count += 1
            finish_sync_run(db, run, "success", rows_written=count, message=filename)
            return count
        except Exception as exc:
            finish_sync_run(db, run, "failed", message=str(exc))
            raise
