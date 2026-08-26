from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from ...config import get_settings
from ...services.comparison import aggregate_range, comparison_dataframe
from ...services.export_xlsx import multi_sheet_xlsx
from ...services.query import alerts_dataframe, daily_dataframe
from ..common import render_report_table
from ..date_filters import date_range_selector


def _fmt_money(v):
    return f"{v:,.0f}원" if v is not None and pd.notna(v) else "자료없음"


def _fmt_num(v):
    return f"{v:,.0f}" if v is not None and pd.notna(v) else "자료없음"


def _fmt_pct(v):
    return f"{v:,.2f}%" if v is not None and pd.notna(v) else "자료없음"


def _render_today_metrics(today: date) -> pd.DataFrame:
    """오늘의 핵심지표는 조회기간과 무관하게 항상 당일 데이터만 사용한다."""
    summary = aggregate_range(today, today)
    alerts = alerts_dataframe(today, today)

    st.subheader("오늘의 핵심 지표")

    cols = st.columns(7)
    metrics = [
        ("실결제", _fmt_money(summary.get("실결제"))),
        ("주문", _fmt_num(summary.get("구매건수"))),
        ("객단가", _fmt_money(summary.get("객단가"))),
        ("방문", _fmt_num(summary.get("전체방문"))),
        ("전환율", _fmt_pct(summary.get("전환율(%)"))),
        ("광고비", _fmt_money(summary.get("광고비"))),
        ("광고비율", _fmt_pct(summary.get("광고비율(%)"))),
    ]
    for c, (label, val) in zip(cols, metrics):
        c.metric(label, val)

    fcols = st.columns(6)
    funnel = [
        ("상품조회", _fmt_num(summary.get("상품조회"))),
        ("장바구니", _fmt_num(summary.get("장바구니"))),
        ("조회→장바구니", _fmt_pct(summary.get("조회→장바구니(%)"))),
        ("상품주문", _fmt_num(summary.get("상품주문"))),
        ("조회→주문", _fmt_pct(summary.get("조회→주문(%)"))),
        ("장바구니→주문", _fmt_pct(summary.get("장바구니→주문(%)"))),
    ]
    for c, (label, val) in zip(fcols, funnel):
        c.metric(label, val)

    # 대표 경보는 오늘 데이터 기준으로 가장 중요한 1건만 한 줄 표시한다.
    if not alerts.empty:
        priority = {"danger": 0, "warning": 1, "info": 2}
        one = alerts.copy()
        one["_priority"] = one["등급"].map(priority).fillna(9)
        one = one.sort_values(["_priority"], kind="stable").iloc[0]

        icon = (
            "🔴"
            if one["등급"] == "danger"
            else "🟠"
            if one["등급"] == "warning"
            else "🔵"
        )
        st.caption(f"{icon} {one['제목']} · {one['내용']}")

    return alerts


def render() -> None:
    # 핵심 지표 숫자를 기존 대비 약 90% 크기로 표시한다.
    st.markdown(
        """
        <style>
        [data-testid="stMetricValue"] {
            transform: scale(0.90);
            transform-origin: left center;
            width: 111.12%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    today = datetime.now(ZoneInfo(get_settings().app_timezone)).date()

    # 1) 오늘의 핵심지표: 조회기간과 완전히 독립, 무조건 당일 고정
    today_alerts = _render_today_metrics(today)

    # 2) 조회기간: 오늘의 핵심지표 아래 / 조회기간별 통계 바로 위
    st.divider()
    st.subheader("조회기간")
    start, end = date_range_selector()

    # 3) 조회기간별 통계
    df = daily_dataframe(start, end)
    if not df.empty and "날짜" in df.columns:
        # 최근 일자부터 위에 표시
        df = df.sort_values(
            "날짜",
            ascending=False,
            kind="stable",
        ).reset_index(drop=True)

    st.subheader("조회기간별 통계")
    st.caption(f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}")
    render_report_table(df)

    # 4) 선택한 조회기간에 연동되는 전년도/전전년도 동일기간 비교
    st.divider()
    st.subheader("전년도 · 전전년도 동일기간 비교")
    comp = comparison_dataframe(start, end)
    comp_display = comp.reset_index().rename(columns={"index": "비교구분"})
    render_report_table(comp_display, comparison_mode=True)
    st.caption(
        "위 조회기간과 동일한 날짜 범위를 전년도·전전년도에 적용합니다. "
        "전환율·광고비율·퍼널 비율의 비교행은 %p 차이, "
        "금액·건수·방문 등은 증감률(%)입니다."
    )

    # 시간대별 매출·주문·방문 섹션은 삭제.
    st.download_button(
        "일별 종합통계 XLSX 다운로드",
        data=multi_sheet_xlsx(
            {
                "조회기간별통계": df,
                "동일기간비교": comp_display,
                "오늘대표경보": today_alerts,
            }
        ),
        file_name=f"미샵_일별종합통계_{start:%Y%m%d}_{end:%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
