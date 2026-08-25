# v3.2.0

- 데이터·설정에 `Cafe24 연결 테스트` 버튼 추가
- `어제 Cafe24 데이터 수집`, `오늘 Cafe24 데이터 수집` 버튼 추가
- Cafe24 단독 수집은 Google Sheet/Sellmate/iApps 미설정 상태에서도 실행 가능
- GitHub Actions/CLI 전체수집에서 Google 광고비 서비스계정이 없으면 광고비 단계 자동 건너뜀

# CHANGELOG

## 3.1.0

- HERO ITEM OS / CRM OS와 **같은 Supabase DATABASE_URL 재사용** 지원
- MISHARP DAILY REPORT 전용 PostgreSQL schema 기본값 `daily_report` 추가
- 모든 DAILY REPORT ORM 테이블을 `daily_report.*` 아래에 생성하여 다른 프로그램 테이블과 충돌 방지
- 앱 시작 시 `CREATE SCHEMA IF NOT EXISTS daily_report` 자동 실행
- migration 스크립트도 `daily_report` schema만 검사/수정하도록 변경
- DB 미설정/초기화 실패 시 Streamlit redacted traceback 대신 Secrets 설정 안내 화면 표시
- 데이터·설정 화면에 현재 DB schema 표시
- `.env.example` / `secrets.toml.example`에 `DATABASE_SCHEMA` 추가

## 3.0.0

- 프로그램명 `MISHARP DAILY REPORT`로 변경
- MISHARP HERO ITEM OS와 동일한 상단 브랜드/가로 메뉴/푸터 UI 체계 적용
- 서브카피: `매출 → 유입 → 전환 → 상품 → 재고 → 비교·판단`
- 상단 메뉴: `일별 종합통계 | 상품 판매 베스트 | 주요 재고 현황 | 데이터·설정`
- 기존 Sidebar의 Cafe24 인증 기능을 `데이터·설정`으로 이동
- `MISHARP DAILY REPORT 이용방법` 추가
- 신규 Streamlit Main file을 `app.py`로 통일
- 기존 `streamlit_app.py`는 호환용으로 유지
- 통합 다운로드 파일명을 `미샵_데일리리포트_YYYYMMDD_YYYYMMDD.xlsx`로 변경
