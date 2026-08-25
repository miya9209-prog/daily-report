from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

HEADER_ALIASES = {
    "product_no": ["상품번호"],
    "product_code": ["상품코드"],
    "product_name": ["상품명"],
    "price": ["가격"],
    "views": ["조회수"],
    "views_pc": ["조회_PC", "조회PC"],
    "views_mobile": ["조회_Mobile", "조회Mobile"],
    "orders": ["주문수"],
    "orders_pc": ["주문_PC", "주문PC"],
    "orders_mobile": ["주문_Mobile", "주문Mobile"],
    "opv": ["OpV", "OPV"],
    "espv": ["ESpV", "ESPV"],
    "detail_path": ["상품상세경로", "상품 상세 경로"],
}


def _norm(v) -> str:
    return re.sub(r"\s+", "", str(v or "")).lower()


def _find_col(df: pd.DataFrame, aliases: list[str]):
    norms = {_norm(x) for x in aliases}
    for c in df.columns:
        if _norm(c) in norms:
            return c
    return None


def _as_int(v):
    try:
        if pd.isna(v):
            return None
        return int(float(v))
    except Exception:
        return None


def _as_float(v):
    try:
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def _product_no_from_path(path: str | None) -> int | None:
    if not path:
        return None
    text = str(path)
    try:
        q = parse_qs(urlparse(text).query)
        for key in ("product_no", "product_no[]"):
            if q.get(key):
                return int(q[key][0])
    except Exception:
        pass
    m = re.search(r"(?:product_no=|/product/[^/]+/)(\d+)", text)
    return int(m.group(1)) if m else None


def captured_at_from_filename(path: Path) -> datetime:
    m = re.search(r"(20\d{6})[_-]?(\d{4,6})", path.stem)
    if not m:
        return datetime.fromtimestamp(path.stat().st_mtime)
    d, t = m.group(1), m.group(2).ljust(6, "0")[:6]
    return datetime.strptime(d + t, "%Y%m%d%H%M%S")


def parse_sera_xlsx(path: Path) -> tuple[datetime, list[dict]]:
    df = pd.read_excel(path, sheet_name=0)
    col = {k: _find_col(df, aliases) for k, aliases in HEADER_ALIASES.items()}
    if not col["product_name"] or not col["views"] or not col["orders"]:
        raise ValueError("SERA 헤더를 찾지 못했습니다. 첫 시트의 상품명/조회수/주문수 컬럼을 확인하세요.")

    records: list[dict] = []
    for _, row in df.iterrows():
        detail = str(row[col["detail_path"]]) if col["detail_path"] and not pd.isna(row[col["detail_path"]]) else None
        pno = _as_int(row[col["product_no"]]) if col["product_no"] else _product_no_from_path(detail)
        if pno is None:
            continue
        price = _as_float(row[col["price"]]) if col["price"] else None
        views = _as_int(row[col["views"]])
        orders = _as_int(row[col["orders"]])
        opv = _as_float(row[col["opv"]]) if col["opv"] else None
        espv = _as_float(row[col["espv"]]) if col["espv"] else None
        if opv is None and views:
            opv = (orders or 0) / views
        if espv is None and views and price is not None:
            espv = price * (orders or 0) / views
        records.append({
            "product_no": pno,
            "product_code": str(row[col["product_code"]]) if col["product_code"] and not pd.isna(row[col["product_code"]]) else None,
            "product_name": str(row[col["product_name"]] or ""),
            "price": price,
            "views": views,
            "views_pc": _as_int(row[col["views_pc"]]) if col["views_pc"] else None,
            "views_mobile": _as_int(row[col["views_mobile"]]) if col["views_mobile"] else None,
            "orders": orders,
            "orders_pc": _as_int(row[col["orders_pc"]]) if col["orders_pc"] else None,
            "orders_mobile": _as_int(row[col["orders_mobile"]]) if col["orders_mobile"] else None,
            "opv": opv,
            "espv": espv,
            "detail_path": detail,
        })
    return captured_at_from_filename(path), records
