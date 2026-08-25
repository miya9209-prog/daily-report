from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

KST = ZoneInfo("Asia/Seoul")


def _today() -> date:
    from datetime import datetime

    return datetime.now(KST).date()


def date_range_selector() -> tuple[date, date]:
    today = _today()
    if "range_start" not in st.session_state:
        st.session_state.range_start = today.replace(day=1)
        st.session_state.range_end = today

    cols = st.columns(6)
    if cols[0].button("오늘", use_container_width=True):
        st.session_state.range_start = st.session_state.range_end = today
    if cols[1].button("어제", use_container_width=True):
        yesterday = today - timedelta(days=1)
        st.session_state.range_start = st.session_state.range_end = yesterday
    if cols[2].button("최근 7일", use_container_width=True):
        st.session_state.range_start = today - timedelta(days=6)
        st.session_state.range_end = today
    if cols[3].button("이번 달", use_container_width=True):
        st.session_state.range_start = today.replace(day=1)
        st.session_state.range_end = today
    if cols[4].button("지난달", use_container_width=True):
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        st.session_state.range_start = last_prev.replace(day=1)
        st.session_state.range_end = last_prev
    if cols[5].button("직접 선택", use_container_width=True):
        pass

    selected = st.date_input(
        "조회 기간",
        value=(st.session_state.range_start, st.session_state.range_end),
        max_value=today,
    )
    if isinstance(selected, tuple) and len(selected) == 2:
        st.session_state.range_start, st.session_state.range_end = selected
    return st.session_state.range_start, st.session_state.range_end
