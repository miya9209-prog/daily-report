from __future__ import annotations

from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from ..config import get_settings
from ..db import session_scope
from ..repositories import latest_sync_runs


def display_missing(df: pd.DataFrame) -> pd.DataFrame:
    return df.astype(object).where(pd.notna(df), "자료없음")


def sync_status_bar() -> None:
    with session_scope() as db:
        rows = latest_sync_runs(db)
    if not rows:
        st.markdown('<div class="mso-status">아직 자동수집 실행 기록이 없습니다.</div>', unsafe_allow_html=True)
        return
    tz = ZoneInfo(get_settings().app_timezone)
    label = {
        "cafe24_daily": "카페24 일별",
        "cafe24_products": "카페24 상품",
        "cafe24_hourly": "카페24 시간대",
        "google_adsheet": "광고비시트",
        "sellmate": "셀메이트",
        "iapps": "아이앱스",
        "sera_reference": "SERA 참고",
    }
    parts = []
    for r in rows:
        icon = "●" if r.status == "success" else "▲"
        dt = r.finished_at or r.started_at
        if dt.tzinfo is None:
            when = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).strftime("%m-%d %H:%M")
        else:
            when = dt.astimezone(tz).strftime("%m-%d %H:%M")
        parts.append(f"{icon} {label.get(r.source, r.source)} {when}")
    st.markdown(f'<div class="mso-status">{" &nbsp;·&nbsp; ".join(parts)}</div>', unsafe_allow_html=True)


def daily_report_guide() -> None:
    with st.expander("MISHARP DAILY REPORT 이용방법 · 처음 세팅할 때 꼭 읽어주세요", expanded=False):
        st.markdown(
            """
            <div class="mso-guide-intro">
            MISHARP DAILY REPORT는 <b>매출·유입·전환·상품·재고·앱 통계</b>를 한곳에 모으고,
            전년·전전년 비교와 매출 회복 경보를 통해 <b>오늘 어디를 먼저 봐야 하는지</b> 판단하기 위한 경영 리포트입니다.
            </div>
            <div class="mso-guide-step"><b>1. 일별 종합통계</b><br>기간을 선택하면 실결제, 주문, 객단가, 방문, 전환율, 광고비와 상품조회 → 장바구니 → 주문 퍼널을 확인합니다. 하단에는 전년도·전전년도 동일기간 비교가 자동 표시됩니다.</div>
            <div class="mso-guide-step"><b>2. 상품 판매 베스트</b><br>Cafe24 Analytics의 조회·장바구니·판매·매출을 상품번호 기준으로 합산하고, 재고와 함께 매출확대 / 재고회수 / CRM회수 / 상세개선 후보를 표시합니다.</div>
            <div class="mso-guide-step"><b>3. 주요 재고 현황</b><br>Sellmate의 옵션별 판매가능재고와 최근 판매속도를 기준으로 예상 소진일과 시즌 종료일까지 필요한 일판매량을 계산합니다.</div>
            <div class="mso-guide-step"><b>4. 데이터 기준</b><br>공식 매출·상품 성과는 Cafe24 Analytics를 기준으로 합니다. SERA는 실시간 참고·검증용이며, 광고비는 Google Sheet, 재고는 Sellmate, 앱 통계는 iApps를 기준으로 연결합니다.</div>
            <div class="mso-guide-step"><b>5. 데이터가 비어 있을 때</b><br><b>데이터·설정</b>에서 각 연동 상태를 먼저 확인합니다. 값 0과 미수집을 구분하기 위해 수집되지 않은 값은 <b>자료없음</b>으로 표시합니다.</div>
            """,
            unsafe_allow_html=True,
        )
