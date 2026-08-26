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
        "상품코드", "품번", "goods_code", "판매자상품코드", "업체상품코드",
        "상품관리코드", "관리코드", "관리번호",
    ),
    "product_name": _alias_set(
        "상품명", "품명", "판매상품명", "셀메이트상품명", "상품이름",
        "goods_name", "product_name"
    ),
    "option_name": _alias_set("옵션", "옵션명", "옵션정보", "품목명", "option", "option_name", "옵션값"),
    "stock_qty": _alias_set(
        "현재고", "실재고", "재고", "재고수량", "실재고수량", "보유재고", "stock", "stock_qty",
        "현재재고", "총재고", "재고량", "잔여재고", "정상재고",
        "현재고정상", "실재고정상", "총재고수량",
    ),
    "available_qty": _alias_set(
        "판매가능재고", "판매가능수량", "가용재고", "가용수량",
        "가용재고수량", "주문가능재고", "주문가능수량", "판매가능",
        "available_stock", "available_qty",
    ),
}

SELLMATE_SHIPPING_ALIASES = {
    "shipping_date": _alias_set(
        "발송일자", "발송일", "출고일자", "출고일", "배송일자", "배송일",
        "처리일자", "처리일", "shipping_date", "shipment_date", "dispatch_date",
    ),
    "shipping_count": _alias_set(
        "당일발송수량", "당일 발송수량", "발송수량", "발송 수량",
        "발송건수", "출고수량", "출고 수량", "출고건수",
        "택배수량", "택배 수량", "택배건수",
        "송장수량", "송장 수량", "송장건수", "배송건수",
        "shipping_count", "shipment_count", "dispatch_count",
    ),
    "tracking_no": _alias_set(
        "운송장번호", "운송장 번호", "송장번호", "송장 번호",
        "택배송장번호", "송장", "운송장", "배송번호", "택배번호",
        "송장코드", "운송장코드", "tracking_no", "trackingnumber", "invoice_no",
    ),
    "order_no": _alias_set(
        "주문번호", "주문 번호", "쇼핑몰주문번호", "몰주문번호",
        "주문코드", "주문id", "주문아이디", "셀메이트주문번호",
        "판매처주문번호", "원주문번호", "order_no", "orderno", "shop_order_no",
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


def _decode_csv_text(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    raise ValueError("CSV 인코딩을 읽지 못했습니다.")


def _read_csv(data: bytes) -> pd.DataFrame:
    """Sellmate CSV의 안내문/제목 1행 때문에 열 수 없는 문제를 피한다.

    실제 파일 예:
    ●일자별배송리스트 (2026-06-01~2026-08-26)
    "일련번호","송장번호",...,"발송일자",...
    """
    text = _decode_csv_text(data)
    lines = text.splitlines()

    # 첫 데이터 헤더로 보이는 줄부터 읽는다.
    start = 0
    for i, line in enumerate(lines[:120]):
        normalized = line.replace('"', "")
        if line.count(",") >= 2 and any(
            key in normalized
            for key in (
                "송장번호", "발송일자", "일련번호",
                "상품명", "실재고", "현재고", "옵션명",
                "날짜", "일자",
            )
        ):
            start = i
            break

    body = "\n".join(lines[start:])
    try:
        return pd.read_csv(StringIO(body), header=None)
    except Exception as exc:
        raise ValueError(f"CSV 내용을 읽지 못했습니다: {exc}") from exc


def _csv_declared_date_range(data: bytes) -> tuple[date, date] | None:
    """Sellmate CSV 제목의 '(YYYY-MM-DD~YYYY-MM-DD)' 범위를 읽는다."""
    try:
        text = _decode_csv_text(data)
    except Exception:
        return None
    head = "\n".join(text.splitlines()[:5])
    m = re.search(
        r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\s*[~～-]\s*"
        r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})",
        head,
    )
    if not m:
        return None
    try:
        start = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        end = date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
        return (start, end) if start <= end else (end, start)
    except Exception:
        return None


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


def _unique_headers(values: list[Any]) -> list[str]:
    out: list[str] = []
    counts: dict[str, int] = {}
    for i, value in enumerate(values):
        base = str(value).strip() if pd.notna(value) and str(value).strip() else f"__blank_{i}"
        counts[base] = counts.get(base, 0) + 1
        out.append(base if counts[base] == 1 else f"{base}__{counts[base]}")
    return out


def _best_alias_match(header: str, names: set[str]) -> tuple[int, int] | None:
    normed = _norm(header)
    if not normed:
        return None
    if normed in names:
        return (2, len(normed))

    # Sellmate 헤더는 '실재고(정상)', '쇼핑몰 주문번호(원본)'처럼
    # 접두/접미 설명이 붙는 경우가 많아 부분일치도 허용한다.
    best = None
    for alias in names:
        if not alias:
            continue
        # 2글자 별칭은 너무 짧을 수 있어 완전 포함일 때만 낮은 점수로 사용.
        if alias in normed or (len(normed) >= 3 and normed in alias):
            score = (1, len(alias))
            if best is None or score > best:
                best = score
    return best


def _detect_mapping(headers: list[str], aliases: dict[str, set[str]]) -> dict[str, str | None]:
    mapping: dict[str, str | None] = {}
    for field, names in aliases.items():
        best_header = None
        best_score = None
        for header in headers:
            score = _best_alias_match(header, names)
            if score is not None and (best_score is None or score > best_score):
                best_score = score
                best_header = header
        mapping[field] = best_header
    return mapping


def _find_header(
    raw: pd.DataFrame,
    aliases: dict[str, set[str]],
    required: set[str],
) -> tuple[int, int, list[str], dict[str, str | None]] | None:
    # Sellmate 파일은 안내문/필터조건 때문에 헤더가 아래쪽에 있을 수 있다.
    max_rows = min(len(raw), 120)
    for r in range(max_rows):
        variants: list[tuple[int, list[Any]]] = [(1, raw.iloc[r].tolist())]

        # 2단 헤더(예: 1행 '재고', 2행 '실재고/가용재고')도 한 헤더로 결합한다.
        if r + 1 < len(raw):
            first = raw.iloc[r].tolist()
            second = raw.iloc[r + 1].tolist()
            combined = []
            for a, b in zip(first, second):
                aa = "" if pd.isna(a) else str(a).strip()
                bb = "" if pd.isna(b) else str(b).strip()
                if aa and bb and aa != bb:
                    combined.append(f"{aa} {bb}")
                else:
                    combined.append(bb or aa)
            variants.append((2, combined))

        for consumed, values in variants:
            headers = _unique_headers(values)
            mapping = _detect_mapping(headers, aliases)
            hits = {field for field, header in mapping.items() if header is not None}
            if required.issubset(hits):
                return r, consumed, headers, mapping
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
            header_row, consumed, headers, mapping = found
            frame = raw.iloc[header_row + consumed :].copy()
            frame.columns = headers
            frame = frame.dropna(how="all").reset_index(drop=True)
            return ParsedUpload(
                frame=frame,
                mapping=mapping,
                sheet_name=sheet_name,
                header_row=header_row + 1,
            )

        # 실패 시 실제 후보 헤더를 오류에 함께 남겨 다음 보완이 쉽도록 한다.
        sample_headers: list[str] = []
        for r in range(min(len(raw), 20)):
            vals = [str(x).strip() for x in raw.iloc[r].tolist() if pd.notna(x) and str(x).strip()]
            if len(vals) >= 3:
                sample_headers = vals[:12]
                break
        hint = f" / 후보헤더={sample_headers}" if sample_headers else ""
        diagnostics.append(f"{sheet_name}: 헤더 자동탐지 실패{hint}")
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

    # '2026-06-01 오전 9:55:00'처럼 한국어 오전/오후가 붙어도
    # 날짜 부분만 먼저 안전하게 추출한다.
    m = re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            pass

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


def preview_sellmate_shipping(
    data: bytes,
    filename: str,
) -> tuple[pd.DataFrame, dict[str, str | None], str]:
    """Sellmate 발송 상세파일을 '일별 발송건수'로 집계한다.

    DAILY REPORT의 택배수량 정의:
    - 날짜 = 발송일자
    - 발송건수 = 날짜별 고유 송장번호 수
    - 같은 송장이 여러 상품행으로 반복되어도 1건으로 계산
    - 송장번호가 없는 파일만 주문번호 고유건수로 대체
    - CSV 제목에 조회기간이 있으면 그 기간의 무발송일도 0건으로 저장
    """
    parsed = _parse_with_aliases(
        data,
        filename,
        SELLMATE_SHIPPING_ALIASES,
        required_sets=[
            {"shipping_date", "tracking_no"},
            {"shipping_date", "order_no"},
            {"shipping_date", "shipping_count"},
        ],
    )
    m = parsed.mapping

    by_day: dict[date, set[str]] = {}
    summed_by_day: dict[date, int] = {}

    date_col = m.get("shipping_date")
    if not date_col:
        raise ValueError("발송일자 컬럼을 찾지 못했습니다.")

    tracking_col = m.get("tracking_no")
    order_col = m.get("order_no")
    count_col = m.get("shipping_count")

    method = ""
    if tracking_col:
        method = f"{tracking_col} 날짜별 고유건수"
        for _, r in parsed.frame.iterrows():
            day = _to_date(r.get(date_col))
            if day is None:
                continue
            value = str(r.get(tracking_col, "") or "").strip()
            if not value or value == "-":
                continue
            by_day.setdefault(day, set()).add(value)

    elif order_col:
        method = f"{order_col} 날짜별 고유건수"
        for _, r in parsed.frame.iterrows():
            day = _to_date(r.get(date_col))
            if day is None:
                continue
            value = str(r.get(order_col, "") or "").strip()
            if not value or value == "-":
                continue
            by_day.setdefault(day, set()).add(value)

    elif count_col:
        method = f"{count_col} 날짜별 합계"
        for _, r in parsed.frame.iterrows():
            day = _to_date(r.get(date_col))
            if day is None:
                continue
            count = _to_int(r.get(count_col))
            if count is None:
                continue
            summed_by_day[day] = summed_by_day.get(day, 0) + count

    counts: dict[date, int] = {}
    if by_day:
        counts = {day: len(values) for day, values in by_day.items()}
    elif summed_by_day:
        counts = summed_by_day

    if not counts:
        raise ValueError("발송일자별 발송건수를 계산할 수 있는 데이터가 없습니다.")

    # 조회기간 중 발송이 없는 날도 '자료없음'이 아니라 실제 0건으로 저장한다.
    declared_range = _csv_declared_date_range(data) if filename.lower().endswith(".csv") else None
    if declared_range:
        range_start, range_end = declared_range
    else:
        range_start, range_end = min(counts), max(counts)

    rows = []
    day = range_start
    while day <= range_end:
        rows.append({
            "날짜": day,
            "택배수량": int(counts.get(day, 0)),
            "집계방식": method,
        })
        day += timedelta(days=1)

    return pd.DataFrame(rows), m, parsed.sheet_name


def import_sellmate_shipping(
    data: bytes,
    filename: str,
) -> dict[str, int | date]:
    preview, _, _ = preview_sellmate_shipping(data, filename)

    if preview.empty:
        raise ValueError("저장할 발송 데이터가 없습니다.")

    with session_scope() as db:
        run = start_sync_run(db, "sellmate_shipping_excel")
        try:
            for _, r in preview.iterrows():
                day = _to_date(r["날짜"])
                shipping_count = _to_int(r["택배수량"])
                if day is None or shipping_count is None:
                    continue

                row = upsert_daily(
                    db,
                    day,
                    shipping_count=shipping_count,
                )
                sources = dict(row.sources or {})
                sources["sellmate_shipping_excel"] = {
                    "file": filename,
                    "method": str(r.get("집계방식") or ""),
                }
                row.sources = sources

            start_day = _to_date(preview["날짜"].min())
            end_day = _to_date(preview["날짜"].max())
            total_shipments = int(preview["택배수량"].fillna(0).sum())
            active_days = int((preview["택배수량"].fillna(0) > 0).sum())
            calendar_days = int(len(preview))

            finish_sync_run(
                db,
                run,
                "success",
                rows_written=calendar_days,
                message=(
                    f"{filename} / {start_day}~{end_day} / "
                    f"{calendar_days:,}일 / 발송일 {active_days:,}일 / "
                    f"총 발송 {total_shipments:,}건"
                ),
            )
            return {
                "start_date": start_day,
                "end_date": end_day,
                "calendar_days": calendar_days,
                "active_days": active_days,
                "total_shipments": total_shipments,
            }
        except Exception as exc:
            finish_sync_run(db, run, "failed", message=str(exc))
            raise

