from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from ...services.comparison import aggregate_range, comparison_dataframe
from ...services.export_xlsx import multi_sheet_xlsx
from ...services.query import alerts_dataframe, daily_dataframe, hourly_dataframe
from ..common import display_missing


def _fmt_money(v): return f"{v:,.0f}원" if v is not None and pd.notna(v) else "자료없음"
def _fmt_num(v): return f"{v:,.0f}" if v is not None and pd.notna(v) else "자료없음"
def _fmt_pct(v): return f"{v:.2f}%" if v is not None and pd.notna(v) else "자료없음"


def render(start: date, end: date) -> None:
    df = daily_dataframe(start, end); summary = aggregate_range(start, end); comp = comparison_dataframe(start, end)
    alerts = alerts_dataframe(start, end); hourly = hourly_dataframe(start, end)

    st.subheader("오늘의 핵심 지표")
    cols = st.columns(7)
    metrics = [
        ("실결제", _fmt_money(summary.get("실결제"))), ("주문", _fmt_num(summary.get("구매건수"))),
        ("객단가", _fmt_money(summary.get("객단가"))), ("방문", _fmt_num(summary.get("전체방문"))),
        ("전환율", _fmt_pct(summary.get("전환율(%)"))), ("광고비", _fmt_money(summary.get("광고비"))),
        ("광고비율", _fmt_pct(summary.get("광고비율(%)"))),
    ]
    for c, (label, val) in zip(cols, metrics): c.metric(label, val)

    fcols = st.columns(6)
    funnel = [
        ("상품조회", _fmt_num(summary.get("상품조회"))), ("장바구니", _fmt_num(summary.get("장바구니"))),
        ("조회→장바구니", _fmt_pct(summary.get("조회→장바구니(%)"))), ("상품주문", _fmt_num(summary.get("상품주문"))),
        ("조회→주문", _fmt_pct(summary.get("조회→주문(%)"))), ("장바구니→주문", _fmt_pct(summary.get("장바구니→주문(%)"))),
    ]
    for c, (label, val) in zip(fcols, funnel): c.metric(label, val)

    if not alerts.empty:
        st.subheader("대표 경보")
        for _, r in alerts.head(8).iterrows():
            icon = "🔴" if r["등급"] == "danger" else "🟠" if r["등급"] == "warning" else "🔵"
            st.info(f"{icon} **{r['제목']}** — {r['내용']}")

    st.subheader("일별 통계")
    st.dataframe(display_missing(df), use_container_width=True, hide_index=True)

    if not hourly.empty:
        with st.expander("시간대별 매출·주문·방문 보기", expanded=False):
            st.dataframe(display_missing(hourly), use_container_width=True, hide_index=True)
            if start == end and "시간" in hourly and "매출" in hourly:
                chart = hourly.set_index("시간")[["매출"]].apply(pd.to_numeric, errors="coerce")
                st.line_chart(chart)

    st.divider(); st.subheader("전년도 · 전전년도 동일기간 비교")
    comp_display = comp.reset_index().rename(columns={"index": "비교구분"})
    st.dataframe(display_missing(comp_display), use_container_width=True, hide_index=True)
    st.caption("전환율·광고비율·퍼널 비율의 비교행은 %p 차이, 금액·건수·방문 등은 증감률(%)입니다.")

    st.download_button(
        "일별 종합통계 XLSX 다운로드",
        data=multi_sheet_xlsx({"일별통계": df, "동일기간비교": comp_display, "시간대": hourly, "대표경보": alerts}),
        file_name=f"미샵_일별종합통계_{start:%Y%m%d}_{end:%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
