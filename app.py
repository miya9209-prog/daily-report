from __future__ import annotations

import streamlit as st

from misharp.connectors.cafe24_oauth import exchange_code
from misharp.db import DATABASE_SCHEMA, init_db
from misharp.services.export_xlsx import multi_sheet_xlsx
from misharp.services.query import daily_dataframe, inventory_dataframe, product_sales_dataframe
from misharp.ui.common import sync_status_bar
from misharp.ui.date_filters import date_range_selector
from misharp.ui.layout import apply_style, render_brand, render_footer, render_nav
from misharp.ui.tabs import daily, inventory, product_best
from misharp.ui import settings as settings_page

st.set_page_config(
    page_title="MISHARP DAILY REPORT",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_style()
render_brand()

# DB 초기화 오류를 Streamlit의 redacted traceback으로 끝내지 않고,
# 사용자가 Secrets에서 바로 수정할 수 있도록 안내합니다.
try:
    init_db()
except Exception as exc:
    st.error("데이터베이스 연결 준비가 필요합니다.")
    st.markdown(
        """
**Streamlit → Manage app → Settings → Secrets**에 먼저 아래 두 값을 넣어주세요.

```toml
DATABASE_URL = "HERO ITEM OS에서 사용 중인 동일한 Supabase DATABASE_URL"
DATABASE_SCHEMA = "daily_report"
```

`DATABASE_URL`은 HERO ITEM OS와 같아도 됩니다. DAILY REPORT는 PostgreSQL의 **daily_report 전용 schema**에만 테이블을 생성하므로 HERO/CRM 테이블과 섞이지 않습니다.
        """
    )
    st.caption(f"DB 초기화 오류 유형: {type(exc).__name__}")
    render_footer()
    st.stop()

# Cafe24 OAuth callback. callback 처리 후 query parameter를 비워 기본화면으로 복귀합니다.
code = st.query_params.get("code")
state = st.query_params.get("state")
if code and state:
    try:
        token = exchange_code(str(code), str(state))
        st.query_params.clear()
        st.success(f"Cafe24 API 인증 완료: {token.get('mall_id', '')}")
    except Exception as exc:
        st.error(f"Cafe24 인증 실패: {exc}")


def page_daily() -> None:
    st.title("일별 종합통계")
    st.caption(
        "오늘의 핵심지표는 당일 기준으로 고정하고, "
        "아래 조회기간에 따라 기간별 통계와 전년·전전년 동일기간을 비교합니다."
    )
    daily.render()


def page_product_best() -> None:
    st.title("상품 판매 베스트")
    st.caption("Cafe24 Analytics의 조회 → 장바구니 → 구매 데이터를 상품번호 기준으로 합산해 판매력과 개선 기회를 봅니다.")
    start, end = date_range_selector()
    product_best.render(start, end)


def page_inventory() -> None:
    st.title("주요 재고 현황")
    st.caption("Sellmate 옵션별 재고와 최근 판매속도를 기준으로 시즌 내 소진 가능성을 확인합니다.")
    start, end = date_range_selector()
    inventory.render(start, end)


NAV = [
    ("daily", "일별 종합통계", page_daily),
    ("products", "상품 판매 베스트", page_product_best),
    ("inventory", "주요 재고 현황", page_inventory),
    ("settings", "데이터·설정", settings_page.render),
]
PAGE_MAP = {key: func for key, _, func in NAV}

raw_page = st.query_params.get("page", "daily")
if isinstance(raw_page, list):
    raw_page = raw_page[0] if raw_page else "daily"
page_key = str(raw_page or "daily")
if page_key not in PAGE_MAP:
    page_key = "daily"

render_nav(NAV, page_key)
if page_key != "settings":
    sync_status_bar()
PAGE_MAP[page_key]()

# 통합 XLSX는 데이터 페이지에서만 표시합니다.
if page_key in {"daily", "products", "inventory"}:
    try:
        start = st.session_state.get("range_start")
        end = st.session_state.get("range_end")
        if start and end:
            st.divider()
            all_xlsx = multi_sheet_xlsx(
                {
                    "일별 종합통계": daily_dataframe(start, end),
                    "상품 판매 베스트": product_sales_dataframe(start, end),
                    "주요 재고 현황": inventory_dataframe(end),
                }
            )
            st.download_button(
                "3개 메뉴 통합 XLSX 다운로드",
                data=all_xlsx,
                file_name=f"미샵_데일리리포트_{start:%Y%m%d}_{end:%Y%m%d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    except Exception as exc:
        st.caption(f"통합 XLSX 생성 대기: {exc}")

render_footer()
