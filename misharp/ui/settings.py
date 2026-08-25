from __future__ import annotations

import streamlit as st

from ..config import get_settings
from ..db import session_scope
from ..repositories import get_token
from ..connectors.cafe24_oauth import build_authorize_url
from .common import daily_report_guide, sync_status_bar


def _is_set(value: str) -> bool:
    return bool(str(value or "").strip())


def render() -> None:
    s = get_settings()
    with session_scope() as db:
        cafe24_token_saved = get_token(db, "cafe24") is not None

    st.title("데이터·설정")
    st.caption("Cafe24 Analytics를 공식 통계 원천으로 사용하고, 광고비·재고·앱·SERA 참고 데이터를 함께 연결합니다.")

    c1, c2, c3, c4 = st.columns(4)
    db_label = "PostgreSQL" if str(s.database_url).startswith("postgresql") else "로컬 SQLite" if str(s.database_url).startswith("sqlite") else "미설정"
    c1.metric("DB", db_label)
    c2.metric("Cafe24 Mall", s.cafe24_mall_id or "미설정")
    c3.metric("Cafe24 토큰", "저장됨" if cafe24_token_saved else "없음")
    c4.metric("광고비 시트", "설정됨" if _is_set(s.google_service_account_json) else "미설정")

    st.subheader("연동 상태")
    sync_status_bar()

    st.subheader("1. Cafe24 API")
    st.caption("상품·주문·접속통계 권한을 최초 1회 승인합니다. 이후 Access Token은 Refresh Token으로 자동 갱신합니다.")
    st.code(s.cafe24_scopes or "mall.read_order mall.read_product mall.read_analytics mall.read_customer", language=None)
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

    st.subheader("2. 외부 데이터 준비 상태")
    rows = [
        {
            "데이터": "Google 광고비 Sheet",
            "상태": "준비" if _is_set(s.google_service_account_json) else "미설정",
            "필요값": "GOOGLE_SERVICE_ACCOUNT_JSON / AD_SHEET_ID / AD_SHEET_GID",
        },
        {
            "데이터": "Sellmate 재고·택배",
            "상태": "준비" if _is_set(s.sellmate_api_base_url) and _is_set(s.sellmate_api_key) else "API 정보 필요",
            "필요값": "Base URL / API Key / 재고 endpoint / 출고 endpoint / JSON 샘플",
        },
        {
            "데이터": "iApps 앱 통계",
            "상태": "준비" if _is_set(s.iapps_api_base_url) and _is_set(s.iapps_api_key) else "API 정보 필요",
            "필요값": "Base URL / API Key / 일별 설치·DAU endpoint",
        },
        {
            "데이터": "SERA",
            "상태": "참고 연동",
            "필요값": "현재는 SERA 보고서 importer / 자동 API 제공 시 connector 교체",
        },
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.subheader("3. 운영 원칙")
    st.markdown(
        """
- **공식 매출·유입·상품 성과:** Cafe24 Analytics API
- **일별 광고비:** 지정 Google Sheet
- **옵션별 현재고·택배수량:** Sellmate API
- **앱 설치·앱 순방문:** iApps API 또는 자동 Export 연동
- **SERA:** 실시간 참고·교차검증용. 공식 집계와 혼합하지 않음
- **과거 비교:** 기존 월별 일일보고를 최초 1회 DB로 이관
        """
    )

    daily_report_guide()
