from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
from zoneinfo import ZoneInfo

import streamlit as st

from ..config import get_settings
from ..db import session_scope
from ..repositories import get_token, latest_sync_runs
from ..connectors.cafe24_oauth import build_authorize_url, effective_cafe24_scopes
from ..connectors.cafe24_analytics import Cafe24AnalyticsClient
from ..connectors.cafe24_admin import Cafe24AdminClient
from ..services.query import daily_dataframe, inventory_dataframe
from ..services.sync_daily import sync_cafe24_daily
from ..services.sync_hourly import sync_hourly
from ..services.sync_products import sync_product_sales
from ..importers.manual_excel import (
    import_iapps_daily,
    import_sellmate_inventory,
    import_sellmate_shipping,
    preview_iapps_daily,
    preview_sellmate_inventory,
    preview_sellmate_shipping,
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



def _upload_signature(data: bytes, *parts) -> str:
    h = hashlib.sha256()
    h.update(data)
    for part in parts:
        h.update(str(part).encode("utf-8"))
    return h.hexdigest()


def _render_manual_upload_status(run, label: str) -> None:
    """페이지를 이동해도 DB에 남아 있는 최근 수동업로드 이력을 표시한다."""
    if run is None:
        st.caption(f"{label}: 아직 DB 반영 이력이 없습니다.")
        return

    when = run.finished_at or run.started_at
    when_text = when.strftime("%Y-%m-%d %H:%M:%S") if when else "시간 미확인"
    rows = int(run.rows_written or 0)
    message = str(run.message or "").strip()

    if run.status == "success":
        st.success(
            f"{label} DB 저장완료 · 최근 반영 {when_text} · {rows:,}행"
            + (f" · {message}" if message else "")
        )
    elif run.status == "running":
        st.info(f"{label}: DB 반영 작업 중 · 시작 {when_text}")
    else:
        st.error(
            f"{label}: 최근 DB 반영 실패 · {when_text}"
            + (f" · {message}" if message else "")
        )


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
        "member_signups": daily.get("member_signups"),
        "member_signup_error": daily.get("member_signup_error"),
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
        effective_cafe24_scopes(),
        language=None,
    )
    st.caption(
        "회원가입 수는 Cafe24 Admin 대시보드의 신규회원 수를 사용합니다. "
        "이번 버전부터 인증 링크에 mall.read_store 권한을 자동 포함합니다. "
        "기존 토큰은 아래 인증 링크로 한 번만 다시 승인해야 회원가입 수집이 시작됩니다."
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

            b1, b2, b3, b4 = st.columns(4)

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

            if b2.button("회원가입 API 테스트", use_container_width=True):
                with st.spinner("Cafe24 Admin 신규회원 수를 확인하고 있습니다..."):
                    try:
                        result = Cafe24AdminClient().new_members_debug()
                        parsed = result.get("parsed_new_members_count")
                        if parsed is not None:
                            st.success(f"Cafe24 신규회원 API 정상 · 현재 신규회원 {parsed:,}명")
                        else:
                            st.error(
                                "Cafe24 Dashboard 응답은 받았지만 new_members_count 값을 해석하지 못했습니다."
                            )
                        st.json(result)
                    except Exception as exc:
                        st.error(
                            "회원가입 API 호출 실패 · "
                            f"{type(exc).__name__}: {exc}"
                        )

            if b3.button("어제 Cafe24 데이터 수집", use_container_width=True):
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

            if b4.button("오늘 Cafe24 데이터 수집", use_container_width=True):
                with st.spinner(f"{today.isoformat()} 현재까지 데이터를 저장하고 있습니다..."):
                    try:
                        result = _sync_cafe24_day(today)
                        st.success(
                            f"{result['date']} 현재까지 수집 완료 · 상품 {result['상품행']:,}행 · 시간대 {result['시간대행']:,}행"
                        )
                        member_value = result.get("member_signups")
                        member_error = result.get("member_signup_error")
                        if member_value is not None:
                            st.success(f"회원가입 {int(member_value):,}명 DB 반영 확인")
                        elif member_error:
                            st.error(f"회원가입 수집 실패: {member_error}")
                        else:
                            st.warning(
                                "Cafe24 Dashboard 호출은 끝났지만 신규회원 값이 비어 있습니다. "
                                "왼쪽의 '회원가입 API 테스트' 결과를 확인해주세요."
                            )
                        df = daily_dataframe(today, today)
                        if not df.empty:
                            render_report_table(df)
                        st.info("오늘 데이터는 진행 중 집계입니다. 다음 자동수집에서 같은 날짜가 다시 갱신됩니다.")
                    except Exception as exc:
                        st.error(f"오늘 Cafe24 데이터 수집 실패: {exc}")

    st.subheader("2. 수동 데이터 업로드")
    st.caption(
        "Sellmate는 실제 재고 파일과 발송내역 파일이 서로 다르므로 업로드를 2개로 분리합니다. "
        "iApps도 관리자 Excel을 필요할 때 업로드합니다."
    )
    st.info(
        "Sellmate 재고 / Sellmate 발송내역 / iApps 통계는 파일을 선택하는 즉시 PostgreSQL DB에 저장합니다. "
        "페이지를 이동하면 파일 선택창은 비어 보일 수 있지만 DB 저장값과 최근 반영 이력은 유지됩니다."
    )

    st.markdown("### Sellmate")

    sell_left, sell_right = st.columns(2)

    with sell_left:
        st.markdown("#### ① 실제 재고 Excel")
        st.caption(
            "Cafe24 재고는 실제 수량이 아니므로 사용하지 않습니다. "
            "Sellmate에서 내려받은 실제 재고 파일만 재고 기준으로 저장합니다."
        )
        _render_manual_upload_status(
            sync_map.get("sellmate_excel"),
            "Sellmate 실제 재고",
        )
        inv_date = st.date_input(
            "재고 기준일",
            value=_local_today(),
            key="sellmate_inventory_date",
        )
        inv_file = st.file_uploader(
            "Sellmate 실제 재고 파일",
            type=["xlsx", "xls", "csv"],
            key="sellmate_inventory_file",
        )

        if inv_file is not None:
            inv_bytes = inv_file.getvalue()
            try:
                preview, mapping, sheet = preview_sellmate_inventory(
                    inv_bytes,
                    inv_file.name,
                )
                st.caption(
                    f"인식 시트: {sheet} · {len(preview):,}행"
                )
                st.code(
                    " / ".join(
                        f"{k}={v or '-'}"
                        for k, v in mapping.items()
                    ),
                    language=None,
                )
                render_report_table(
                    preview.head(10),
                    max_height=340,
                )

                sig = _upload_signature(
                    inv_bytes,
                    inv_date,
                )
                if st.session_state.get("sellmate_saved_sig") != sig:
                    with st.spinner(
                        "Sellmate 실제 재고를 DB에 저장하고 있습니다..."
                    ):
                        count = import_sellmate_inventory(
                            inv_bytes,
                            inv_file.name,
                            inv_date,
                        )
                    st.session_state["sellmate_saved_sig"] = sig
                    st.success(
                        f"{inv_date} 실제 재고 {count:,}행 DB 저장 완료"
                    )

                check = inventory_dataframe(inv_date)
                if not check.empty:
                    st.caption(
                        f"DB 재조회 확인: {len(check):,}행"
                    )
                    render_report_table(
                        check.head(10),
                        max_height=300,
                    )
            except Exception as exc:
                st.error(
                    f"Sellmate 재고 파일 인식/저장 실패: {exc}"
                )

    with sell_right:
        st.markdown("#### ② 발송내역 CSV/Excel")
        st.caption(
            "Sellmate의 일자별 배송리스트를 올리면 발송일자를 기준으로 "
            "날짜별 고유 송장번호를 집계해 일별 종합통계의 '택배수량'으로 저장합니다."
        )
        _render_manual_upload_status(
            sync_map.get("sellmate_shipping_excel"),
            "Sellmate 일별 발송건수",
        )

        ship_file = st.file_uploader(
            "Sellmate 발송내역 파일",
            type=["xlsx", "xls", "csv"],
            key="sellmate_shipping_file",
        )

        if ship_file is not None:
            ship_bytes = ship_file.getvalue()
            try:
                preview, mapping, sheet = preview_sellmate_shipping(
                    ship_bytes,
                    ship_file.name,
                )

                ship_start = preview["날짜"].min()
                ship_end = preview["날짜"].max()
                total_shipments = int(preview["택배수량"].fillna(0).sum())
                active_days = int((preview["택배수량"].fillna(0) > 0).sum())

                st.caption(
                    f"인식: {ship_start} ~ {ship_end} · "
                    f"{len(preview):,}일 · 발송일 {active_days:,}일 · "
                    f"총 발송 {total_shipments:,}건"
                )
                st.code(
                    " / ".join(
                        f"{k}={v or '-'}"
                        for k, v in mapping.items()
                    ),
                    language=None,
                )
                render_report_table(
                    preview.tail(20),
                    max_height=420,
                )

                sig = _upload_signature(ship_bytes)
                if st.session_state.get(
                    "sellmate_shipping_saved_sig"
                ) != sig:
                    with st.spinner(
                        "Sellmate 발송내역을 날짜별 발송건수로 집계해 DB에 저장하고 있습니다..."
                    ):
                        result = import_sellmate_shipping(
                            ship_bytes,
                            ship_file.name,
                        )
                    st.session_state[
                        "sellmate_shipping_saved_sig"
                    ] = sig
                    st.success(
                        f"{result['start_date']} ~ {result['end_date']} "
                        f"{result['calendar_days']:,}일 DB 저장 완료 · "
                        f"총 발송 {result['total_shipments']:,}건"
                    )

                check = daily_dataframe(
                    ship_start,
                    ship_end,
                )
                if not check.empty:
                    cols = [
                        c
                        for c in ["날짜", "택배수량"]
                        if c in check.columns
                    ]
                    st.caption("DB 재조회 확인 · 최근 20일")
                    render_report_table(
                        check[cols].tail(20),
                        max_height=420,
                    )
            except Exception as exc:
                st.error(
                    f"Sellmate 발송 파일 인식/저장 실패: {exc}"
                )

    st.markdown("### iApps")
    st.caption(
        "일별 앱 설치수·앱 순방문(DAU)을 날짜 기준으로 저장합니다."
    )
    _render_manual_upload_status(
        sync_map.get("iapps_excel"),
        "iApps 일별 통계",
    )
    app_file = st.file_uploader(
        "iApps 통계 파일",
        type=["xlsx", "xls", "csv"],
        key="iapps_daily_file",
    )
    if app_file is not None:
        app_bytes = app_file.getvalue()
        try:
            preview, mapping, sheet = preview_iapps_daily(
                app_bytes,
                app_file.name,
            )
            st.caption(
                f"인식 시트: {sheet} · {len(preview):,}일"
            )
            st.code(
                " / ".join(
                    f"{k}={v or '-'}"
                    for k, v in mapping.items()
                ),
                language=None,
            )
            render_report_table(
                preview.head(14),
                max_height=340,
            )

            sig = _upload_signature(app_bytes)
            if st.session_state.get("iapps_saved_sig") != sig:
                with st.spinner(
                    "iApps 일별 통계를 DB에 저장하고 있습니다..."
                ):
                    count = import_iapps_daily(
                        app_bytes,
                        app_file.name,
                    )
                st.session_state["iapps_saved_sig"] = sig
                st.success(
                    f"iApps 일별 통계 {count:,}일 DB 저장 완료"
                )

            app_start = preview["날짜"].min()
            app_end = preview["날짜"].max()
            check = daily_dataframe(
                app_start,
                app_end,
            )
            if not check.empty:
                app_cols = [
                    c
                    for c in ["날짜", "앱 설치수", "앱 순방문"]
                    if c in check.columns
                ]
                verify = check[app_cols].copy()
                populated = verify[
                    ["앱 설치수", "앱 순방문"]
                ].notna().any(axis=1).sum()
                if populated:
                    st.success(
                        f"DB 재조회 확인: {app_start} ~ {app_end} 중 "
                        f"앱 통계 저장 날짜 {int(populated):,}일"
                    )
                    render_report_table(
                        verify.tail(14),
                        max_height=340,
                    )
                else:
                    st.error(
                        "파일은 읽었지만 DB 재조회 결과 앱 설치수/앱 순방문이 비어 있습니다. "
                        "실제 iApps 파일 헤더를 기준으로 importer 보완이 필요합니다."
                    )
        except Exception as exc:
            st.error(
                f"iApps 파일 인식/저장 실패: {exc}"
            )

    st.subheader("3. 과거·누락 데이터 채우기")
    st.caption("현재 월 누락분은 GitHub Actions의 MISHARP backfill로 채우고, 전년도·전전년도는 기존 일일보고 Excel을 최초 1회 업로드합니다.")

    st.markdown("#### 과거 일일보고 1회 업로드")
    st.caption("기존 2020~2026 월별 일일보고는 용량이 크고 최초 1회 작업이므로, 파일 선택 후 아래 DB 반영 버튼을 직접 눌러 처리합니다. 이미 Cafe24/Google에서 들어온 최신 값은 덮어쓰지 않습니다.")
    _render_manual_upload_status(sync_map.get("legacy_excel"), "과거 일일보고")
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
    sellmate_shipping_run = sync_map.get("sellmate_shipping_excel")
    iapps_run = sync_map.get("iapps_excel")
    rows = [
        {"데이터": "Cafe24 매출·유입·상품", "방식": "API 자동수집", "상태": "정상" if cafe24_token_saved else "인증 필요"},
        {"데이터": "Google 광고비", "방식": "GitHub Actions 자동수집", "상태": "정상" if google_ok else "미수집"},
        {"데이터": "Sellmate 실제 재고", "방식": "Excel 수동업로드", "상태": "업로드 이력 있음" if sellmate_run else "첫 업로드 필요"},
        {"데이터": "Sellmate 일별 발송건수", "방식": "CSV/Excel 수동업로드", "상태": "업로드 이력 있음" if sellmate_shipping_run else "첫 업로드 필요"},
        {"데이터": "iApps 앱 통계", "방식": "Excel 수동업로드", "상태": "업로드 이력 있음" if iapps_run else "첫 업로드 필요"},
        {"데이터": "SERA", "방식": "참고용", "상태": "필요 시 업로드"},
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.subheader("5. 운영 원칙")
    st.markdown(
        """
- **공식 매출·유입·상품 성과:** Cafe24 Analytics API 자동수집
- **일별 광고비:** 지정 Google Sheet → GitHub Actions 자동수집
- **실제 재고:** Sellmate 실제 재고 Excel 수동업로드. **Cafe24 재고수량은 사용하지 않음**
- **택배수량:** Sellmate 발송내역 CSV/Excel → 발송일자별 고유 송장번호 수로 자동 집계
- **앱 설치·앱 순방문:** iApps Excel 수동업로드
- **같은 기준일 재업로드:** 기존 DB 값을 교체하여 중복 누적하지 않음
- **SERA:** 실시간 참고·교차검증용. 공식 집계와 혼합하지 않음
        """
    )

    daily_report_guide()
