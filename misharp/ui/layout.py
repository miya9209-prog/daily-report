from __future__ import annotations

import html
from collections.abc import Callable

import streamlit as st


BRAND_TITLE = "MISHARP DAILY REPORT"
BRAND_SUBTITLE = "매출 → 유입 → 전환 → 상품 → 재고 → 비교·판단"


CSS = r"""
<style>
:root {
  --mso-text: #202124;
  --mso-muted: #747b86;
  --mso-line: #dedfe3;
  --mso-soft: #f5f6f8;
  --mso-active: #e7ebef;
}

[data-testid="stSidebar"] {display:none;}
[data-testid="stHeader"] {background: rgba(255,255,255,.94);}
.block-container {
  max-width: 1640px;
  padding-top: 2.2rem;
  padding-bottom: 5rem;
  padding-left: 3.6rem;
  padding-right: 3.6rem;
}

.mso-brand-wrap {
  margin: 0;
  padding: .2rem 0 1.25rem 0;
}
.mso-brand {
  color: #050505;
  font-size: clamp(2.25rem, 3.15vw, 3.65rem);
  font-weight: 900;
  letter-spacing: -0.052em;
  line-height: 1.02;
  margin: 0;
}
.mso-brand-sub {
  margin-top: .62rem;
  color: var(--mso-muted);
  font-size: .86rem;
  letter-spacing: -0.02em;
}

.mso-nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .12rem;
  padding: .15rem 0 .72rem 0;
  margin: 0 0 1.2rem 0;
  border-bottom: 1px solid #202124;
}
.mso-nav a {
  display: inline-block;
  text-decoration: none !important;
  color: #2b3036 !important;
  font-size: .92rem;
  font-weight: 680;
  letter-spacing: -0.025em;
  padding: .42rem .72rem;
  border-radius: 6px;
  transition: background .12s ease;
}
.mso-nav a:hover {background:#f1f3f5;}
.mso-nav a.active {
  background: var(--mso-active);
  color: #151515 !important;
  font-weight: 850;
}

h1 {
  font-weight: 860 !important;
  font-size: clamp(2.05rem, 2.6vw, 3rem) !important;
  letter-spacing: -0.05em !important;
  color: var(--mso-text) !important;
  margin-top: .7rem !important;
  margin-bottom: .35rem !important;
}
h2, h3 {letter-spacing: -0.035em !important;}

[data-testid="stMetric"] {padding: .35rem 0 .5rem 0;}
[data-testid="stMetricLabel"] {
  color: #555c66;
  font-weight: 650;
  letter-spacing: -0.02em;
}
[data-testid="stMetricValue"] {
  color: #202124;
  font-weight: 700;
  letter-spacing: -0.035em;
}

.stButton > button, .stDownloadButton > button {
  border-radius: 6px;
  font-weight: 650;
}
[data-baseweb="input"] > div,
[data-baseweb="select"] > div {border-radius: 6px !important;}

[data-testid="stDataFrame"] {
  border: 1px solid var(--mso-line);
  border-radius: 4px;
  overflow: hidden;
}

.mso-status {
  margin: -.25rem 0 1rem;
  color: #737a84;
  font-size: .79rem;
  line-height: 1.6;
}

.mso-guide-intro {
  color: #626a75;
  font-size: .93rem;
  line-height: 1.75;
  margin: .2rem 0 .7rem;
}
.mso-guide-step {
  padding: .72rem 0;
  border-bottom: 1px solid #eef0f3;
  line-height: 1.65;
}
.mso-guide-step:last-child {border-bottom: 0;}
.mso-guide-step b {color:#222;}

.mso-footer {
  margin-top: 5rem;
  padding: 1.7rem 0 .4rem 0;
  border-top: 1px solid var(--mso-line);
  color: #8a9099;
  font-size: .76rem;
  line-height: 1.75;
  letter-spacing: -0.015em;
}
.mso-footer strong {color:#5f6670; font-weight:700;}

@media (max-width: 900px) {
  .block-container {padding-left: 1.2rem; padding-right: 1.2rem;}
  .mso-brand {font-size: 2.1rem;}
  .mso-nav a {font-size:.84rem; padding:.36rem .5rem;}
}
</style>
"""


def apply_style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def render_brand() -> None:
    st.markdown(
        f"""
        <div class="mso-brand-wrap">
          <div class="mso-brand">{html.escape(BRAND_TITLE)}</div>
          <div class="mso-brand-sub">{html.escape(BRAND_SUBTITLE)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_nav(nav: list[tuple[str, str, Callable]], active_key: str) -> None:
    links: list[str] = []
    for key, label, _ in nav:
        active = " active" if key == active_key else ""
        links.append(
            f'<a class="mso-nav-item{active}" href="?page={html.escape(key)}" '
            f'target="_self">{html.escape(label)}</a>'
        )
    st.markdown(f'<nav class="mso-nav">{"".join(links)}</nav>', unsafe_allow_html=True)


def render_footer() -> None:
    st.markdown(
        """
        <div class="mso-footer">
          <strong>© MISHARP COMPANY. All rights reserved.</strong><br>
          본 시스템 및 콘텐츠의 저작권은 MISHARP COMPANY에 있으며, 무단 복제·배포·전재·상업적 사용을 금합니다.<br>
          This system and its contents are proprietary to MISHARP COMPANY. Unauthorized copying, reproduction or distribution is prohibited.<br>
          Creator: <strong>MISHARP COMPANY PARK HYUNG JOON</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )
