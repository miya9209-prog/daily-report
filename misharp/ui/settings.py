from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from ..config import get_settings
from ..db import session_scope
from ..repositories import get_token, latest_sync_runs
from ..connectors.cafe24_oauth import build_authorize_url
from ..connectors.cafe24_analytics import Cafe24AnalyticsClient
from ..services.query import daily_dataframe
from ..services.sync_daily import sync_cafe24_daily
from ..services.sync_hourly import sync_hourly
from ..services.sync_products import sync_product_sales
from ..importers.manual_excel import (
    import_iapps_daily, import_sellmate_inventory, preview_iapps_daily, preview_sellmate_inventory,
)
from ..importers.legacy_daily import import_legacy_daily, preview_legacy_daily
from .common import daily_report_guide, sync_status_bar, styled_numeric_table, render_report_table


def _is_set(value: str) -> bool:
    return bool(str(value or "").strip())


def _local_today():
    s = get_settings()
    return datetime.now(ZoneInfo(s.app_timezone)).date()


def _latest_sync_map():
    with session_scope() as db:
        return {r.source: r for r in latest_sync_runs(db)}


def _test_cafe24(day) -> dict:
    """DB에 쓰지 않고 Cafe24 Analytics 읽기 권한/토큰을 확인한다."""
    c = Cafe24AnalyticsClient()
    sales = c.sales_times(day)
    visitors = c.visitors(day, "day")
    carts = c.cart_actions(day)

    sales_amount = sum(float(x.get("order_amount") or 0) for x in sales)
    order_count = sum(int(float(x.get("order_count") or 0)) for x in sales)
    visit_count = sum(int(float(x.get("visit_count") or x.get("count") or 0)) for x in visitors)
    cart_count = sum(int(float(x.get("add_cart_count") or 0)) for x in carts)

    return {
        "기준일": day.isoformat(),
        "매출액": int(sales_amount),
        "주문수": order_count,
        "방문": visit_count,
        "장바구니": cart_count,
        "sales/times 응답행": len(sales),
        "visitors/view 응답행": len(visitors),
        "carts/action 응답행": len(carts),
    }


def _sync_cafe24_day(day) -> dict:
    daily = sync_cafe24_daily(day)
    products = sync_product_sales(day)
    hourly = sync_hourly(day)
    return {
        "date": daily.get("date", day.isoformat()),
        "상품행": products,
        "시간대행": hourly,
    }


def render() -> None:
    s = get_settings()
    with session_scope() as db:
        cafe24_token_saved = get_token(db, "cafe24") is not None
    sync_map = _latest_sync_map()

    st.title("데이터·설정")
    st.caption("Cafe24 Analytics를 공식 통계 원천으로 사용하고, 광고비·재고·앱·SERA 참고 데이터를 함께 연결합니다.")

    c1, c2, c3, c4 = st.columns(4)
    db_label = (
        f"PostgreSQL · {s.database_schema}"
        if str(s.database_url).startswith("postgresql")
        else "로컬 SQLite"
        if str(s.database_url).startswith("sqlite")
        else "미설정"
    )
    c1.metric("DB", db_label)
    c2.metric("Cafe24 Mall", s.cafe24_mall_id or "미설정")
    c3.metric("Cafe24 토큰", "저장됨" if cafe24_token_saved else "없음")
    google_ok = bool(sync_map.get("google_adsheet") and sync_map["google_adsheet"].status == "success")
    c4.metric("광고비 시트", "자동수집" if google_ok else "미수집")

    if str(s.database_url).startswith("postgresql"):
        st.caption(f"DB 분리: 같은 Supabase를 사용하되 `{s.database_schema}` schema에만 DAILY REPORT 테이블을 저장합니다.")

    st.subheader("연동 상태")
    sync_status_bar()

    st.subheader("1. Cafe24 API")
    st.caption("상품·주문·접속통계 권한을 최초 1회 승인합니다. 이후 Access Token은 Refresh Token으로 자동 갱신합니다.")
    st.code(
        s.cafe24_scopes or "mall.read_order mall.read_product mall.read_analytics mall.read_customer",
        language=None,
    )
    missing = [
        key
        for key, value in {
            "CAFE24_MALL_ID": s.cafe24_mall_id,
            "CAFE24_CLIENT_ID": s.cafe24_client_id,
            "CAFE24_CLIENT_SECRET": s.cafe24_client_secret,
            "CAFE24_REDIRECT_URI": s.cafe24_redirect_uri,
            "TOKEN_ENCRYPTION_KEY": s.token_encryption_key,
        }.items()
        if not _is_set(value)
    ]

    if missing:
        st.warning("Cafe24 인증 전 Secrets에 먼저 입력하세요: " + ", ".join(missing))
    else:
        if st.button("Cafe24 인증 링크 생성", use_container_width=False):
            try:
                st.session_state.cafe24_auth_url = build_authorize_url()
            except Exception as exc:
                st.error(f"인증 링크 생성 실패: {exc}")
        if st.session_state.get("cafe24_auth_url"):
            st.link_button("Cafe24 쇼핑몰 관리자 승인 열기", st.session_state.cafe24_auth_url)
        if cafe24_token_saved:
            st.success("Cafe24 OAuth 토큰이 DB에 암호화 저장되어 있습니다.")

            st.markdown("#### Cafe24 실데이터 확인")
            st.caption("다른 데이터원과 무관하게 Cafe24 Analytics만 단독으로 테스트·수집합니다.")

            today = _local_today()
            yesterday = today - timedelta(days=1)

            b1, b2, b3 = st.columns(3)

            if b1.button("Cafe24 연결 테스트", use_container_width=True):
                with st.spinner(f"{yesterday.isoformat()} Cafe24 Analytics를 확인하고 있습니다..."):
                    try:
                        result = _test_cafe24(yesterday)
                        st.success("Cafe24 Analytics 연결 정상")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("테스트 매출", f"{result['매출액']:,}원")
                        m2.metric("주문", f"{result['주문수']:,}건")
                        m3.metric("방문", f"{result['방문']:,}")
                        m4.metric("장바구니", f"{result['장바구니']:,}")
                        st.caption(
                            f"기준일 {result['기준일']} · "
                            f"sales/times {result['sales/times 응답행']}행 · "
                            f"visitors/view {result['visitors/view 응답행']}행 · "
                            f"carts/action {result['carts/action 응답행']}행"
                        )
                    except Exception as exc:
                        st.error(f"Cafe24 연결 테스트 실패: {exc}")

            if b2.button("어제 Cafe24 데이터 수집", use_container_width=True):
                with st.spinner(f"{yesterday.isoformat()} 일별·상품·시간대 데이터를 저장하고 있습니다..."):
                    try:
                        result = _sync_cafe24_day(yesterday)
                        st.success(
                            f"{result['date']} 수집 완료 · 상품 {result['상품행']:,}행 · 시간대 {result['시간대행']:,}행"
                        )
                        df = daily_dataframe(yesterday, yesterday)
                        if not df.empty:
                            render_report_table(df)
                    except Exception as exc:
                        st.error(f"어제 Cafe24 데이터 수집 실패: {exc}")

            if b3.button("오늘 Cafe24 데이터 수집", use_container_width=True):
                with st.spinner(f"{today.isoformat()} 현재까지 데이터를 저장하고 있습니다..."):
                    try:
                        result = _sync_cafe24_day(today)
                        st.success(
                            f"{result['date']} 현재까지 수집 완료 · 상품 {result['상품행']:,}행 · 시간대 {result['시간대행']:,}행"
                        )
                        df = daily_dataframe(today, today)
                        if not df.empty:
                            render_report_table(df)
                        st.info("오늘 데이터는 진행 중 집계입니다. 다음 자동수집에서 같은 날짜가 다시 갱신됩니다.")
                    except Exception as exc:
                        st.error(f"오늘 Cafe24 데이터 수집 실패: {exc}")

    st.subheader("2. 수동 데이터 업로드")
    st.caption("Sellmate와 iApps는 관리자에서 Excel을 내려받아 필요할 때 업로드합니다. 같은 기준일을 다시 올리면 DB 값을 교체합니다.")

    left, right = st.columns(2)

    with left:
        st.markdown("#### Sellmate 실제 재고 Excel")
        st.caption("Cafe24 재고는 사용하지 않습니다. Sellmate 실제 재고 파일만 기준으로 저장합니다.")
        inv_date = st.date_input("재고 기준일", value=_local_today(), key="sellmate_inventory_date")
        inv_file = st.file_uploader("Sellmate 재고 파일", type=["xlsx", "xls", "csv"], key="sellmate_inventory_file")
        if inv_file is not None:
            inv_bytes = inv_file.getvalue()
            try:
                preview, mapping, sheet = preview_sellmate_inventory(inv_bytes, inv_file.name)
                st.caption(f"인식 시트: {sheet} · {len(preview):,}행")
                st.code(" / ".join(f"{k}={v or '-'}" for k, v in mapping.items()), language=None)
                render_report_table(preview.head(10), max_height=360)
                if st.button("Sellmate 재고 DB 반영", key="apply_sellmate_excel", use_container_width=True):
                    count = import_sellmate_inventory(inv_bytes, inv_file.name, inv_date)
                    st.success(f"{inv_date} 실제 재고 {count:,}행 반영 완료")
                    st.rerun()
            except Exception as exc:
                st.error(f"Sellmate 파일 인식 실패: {exc}")

    with right:
        st.markdown("#### iApps 일별 통계 Excel")
        st.caption("일별 앱 설치수·앱 순방문(DAU)을 날짜 기준으로 덮어씁니다.")
        app_file = st.file_uploader("iApps 통계 파일", type=["xlsx", "xls", "csv"], key="iapps_daily_file")
        if app_file is not None:
            app_bytes = app_file.getvalue()
            try:
                preview, mapping, sheet = preview_iapps_daily(app_bytes, app_file.name)
                st.caption(f"인식 시트: {sheet} · {len(preview):,}일")
                st.code(" / ".join(f"{k}={v or '-'}" for k, v in mapping.items()), language=None)
                render_report_table(preview.head(14), max_height=360)
                if st.button("iApps 통계 DB 반영", key="apply_iapps_excel", use_container_width=True):
                    count = import_iapps_daily(app_bytes, app_file.name)
                    st.success(f"iApps 일별 통계 {count:,}일 반영 완료")
                    st.rerun()
            except Exception as exc:
                st.error(f"iApps 파일 인식 실패: {exc}")

    st.subheader("3. 과거·누락 데이터 채우기")
    st.caption("현재 월 누락분은 GitHub Actions의 MISHARP backfill로 채우고, 전년도·전전년도는 기존 일일보고 Excel을 최초 1회 업로드합니다.")

    st.markdown("#### 과거 일일보고 1회 업로드")
    st.caption("기존 2020~2026 월별 일일보고를 DB의 빈 칸에만 채웁니다. 이미 Cafe24/Google에서 들어온 최신 값은 덮어쓰지 않습니다.")
    legacy_file = st.file_uploader(
        "과거 일일보고 Excel",
        type=["xlsx"],
        key="legacy_daily_report_file",
    )
    if legacy_file is not None:
        legacy_bytes = legacy_file.getvalue()
        try:
            preview, notes = preview_legacy_daily(legacy_bytes)
            render_report_table(preview, max_height=220)
            if notes:
                with st.expander(f"인식 참고사항 {len(notes)}건"):
                    for note in notes[:30]:
                        st.write("-", note)
            if st.button("과거 일일보고 DB 빈칸 채우기", key="apply_legacy_daily", type="primary"):
                with st.spinner("과거 일일보고를 DB에 채우고 있습니다..."):
                    days, fields, notes2 = import_legacy_daily(
                        legacy_bytes,
                        legacy_file.name,
                    )
                st.success(f"과거 데이터 {days:,}일 검사 · 빈 필드 {fields:,}개 보충 완료")
                st.rerun()
        except Exception as exc:
            st.error(f"과거 일일보고 인식/적재 실패: {exc}")

    st.info(
        "2026년 8월 1~24일처럼 Cafe24 자동수집 시작 전 누락된 최신 기간은 "
        "GitHub → Actions → MISHARP backfill에서 시작일/종료일을 지정해 한 번만 실행하세요."
    )

    st.subheader("4. 데이터 운영 상태")
    sellmate_run = sync_map.get("sellmate_excel")
    iapps_run = sync_map.get("iapps_excel")
    rows = [
        {"데이터": "Cafe24 매출·유입·상품", "방식": "API 자동수집", "상태": "정상" if cafe24_token_saved else "인증 필요"},
        {"데이터": "Google 광고비", "방식": "GitHub Actions 자동수집", "상태": "정상" if google_ok else "미수집"},
        {"데이터": "Sellmate 실제 재고", "방식": "Excel 수동업로드", "상태": "업로드 이력 있음" if sellmate_run else "첫 업로드 필요"},
        {"데이터": "iApps 앱 통계", "방식": "Excel 수동업로드", "상태": "업로드 이력 있음" if iapps_run else "첫 업로드 필요"},
        {"데이터": "SERA", "방식": "참고용", "상태": "필요 시 업로드"},
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.subheader("5. 운영 원칙")
    st.markdown(
        """
- **공식 매출·유입·상품 성과:** Cafe24 Analytics API 자동수집
- **일별 광고비:** 지정 Google Sheet → GitHub Actions 자동수집
- **실제 재고:** Sellmate Excel 수동업로드. **Cafe24 재고수량은 사용하지 않음**
- **앱 설치·앱 순방문:** iApps Excel 수동업로드
- **같은 기준일 재업로드:** 기존 DB 값을 교체하여 중복 누적하지 않음
- **SERA:** 실시간 참고·교차검증용. 공식 집계와 혼합하지 않음
        """
    )

    daily_report_guide()
