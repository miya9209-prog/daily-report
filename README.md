# MISHARP DAILY REPORT

미샵의 **매출 · 유입 · 전환 · 상품 · 재고 · 앱 통계**를 자동 수집하고 전년·전전년 비교와 매출 회복 판단까지 한 화면에서 확인하는 일별 경영 리포트입니다.

화면 디자인은 MISHARP HERO ITEM OS의 운영 UI 체계를 그대로 이어갑니다.

- 큰 영문 브랜드 타이틀 + 짧은 흐름형 서브카피
- 좌측 사이드바 없이 **상단 가로 메뉴**
- 동일한 폰트 크기/간격/테이블/버튼 스타일
- 동일한 저작권/제작자 푸터

## 상단 메뉴

1. **일별 종합통계**
   - 오늘 / 어제 / 최근 7일 / 이번 달 / 지난달 / 직접 선택
   - 실결제, 주문수, 객단가, 방문, 구매전환율, 광고비, 광고비율
   - 상품조회 → 장바구니 → 주문 퍼널
   - 시간대별 매출/주문/방문
   - 대표 경보
   - 전년도·전전년도 동일기간 비교
   - XLSX 다운로드
2. **상품 판매 베스트**
   - Cafe24 Analytics 상품 판매/조회/장바구니 데이터
   - 상품번호 기준 기간 합산
   - 매출확대 / 재고회수 / CRM회수 / 상세개선 후보 자동판정
   - SERA 참고 스냅샷 비교
   - XLSX 다운로드
3. **주요 재고 현황**
   - Sellmate 옵션별 재고
   - 최근 7/30일 판매, 예상 소진일
   - 시즌 종료일까지 필요한 일판매량 및 소진속도 달성률
   - XLSX 다운로드
4. **데이터·설정**
   - Cafe24 OAuth 최초 승인
   - 자동수집 상태
   - Google 광고비 Sheet / Sellmate / iApps / SERA 준비상태
   - 이용방법

## 화면 타이틀

```text
MISHARP DAILY REPORT
매출 → 유입 → 전환 → 상품 → 재고 → 비교·판단
```

## 데이터 기준

| 데이터 | 기준 원천 | 역할 |
|---|---|---|
| 매출/주문/방문/PV/상품조회/장바구니/상품판매 | Cafe24 Analytics API | 공식 통계 기준 |
| 주문/상품/회원 등 관리자 데이터 | Cafe24 Admin API | 필요 범위 보조 |
| 일별 광고비 | 지정 Google Sheet | 광고비 기준 |
| 재고/택배 | Sellmate API | 옵션별 현재고·출고 |
| 앱설치/앱순방문 | iApps | 앱 지표 |
| 실시간 상품 반응 | SERA | 참고·교차검증 |
| 과거 일별 통계 | 기존 월별 일일보고 Excel | 최초 1회 DB 백필 |

## 운영 구조

```text
Cafe24 Admin / Analytics ─┐
Google 광고비 Sheet ──────┼──> GitHub Actions ──> PostgreSQL/Supabase ──> Streamlit
Sellmate ─────────────────┤                                      │
iApps ────────────────────┘                                      ├─ 전년/전전년 비교
SERA 참고 snapshot ────────────────────────────────────────────────└─ 매출복구 판단
```

## GitHub / Streamlit 빠른 시작

1. GitHub에 **Private** 저장소 `misharp-daily-report` 생성
2. 이 레포 전체 업로드
3. Supabase/PostgreSQL `DATABASE_URL` 준비
4. Streamlit Community Cloud에서 배포
   - Repository: `misharp-daily-report`
   - Branch: `main`
   - Main file: **`app.py`**
5. 생성된 Streamlit URL을 Cafe24 Redirect URI로 등록
6. Streamlit Secrets와 GitHub Actions Secrets 입력
7. 상단 **데이터·설정**에서 Cafe24 최초 OAuth 승인
8. GitHub Actions 수동 실행 → 실데이터 확인

상세한 순서는 **[SETUP_GUIDE_KO.md](SETUP_GUIDE_KO.md)**를 위에서부터 따라가면 됩니다.

## 로컬 실행

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.init_db
streamlit run app.py
```

## 보안

- API Secret, DB 비밀번호, Google JSON Key, Cafe24 Token은 GitHub 코드에 저장하지 않습니다.
- Cafe24 Access/Refresh Token은 DB에 Fernet 암호화 저장합니다.
- Google 서비스 계정은 광고비 Sheet에 Viewer 권한만 부여합니다.
- 고객 이름/전화/주소 등 불필요한 개인정보는 이 통계 DB 기본 스키마에 저장하지 않습니다.

## 주요 문서

- `SETUP_GUIDE_KO.md` — 처음부터 운영까지 전체 순서
- `docs/02_CAFE24_API_SETUP.md` — Cafe24 OAuth/API
- `docs/03_GOOGLE_AD_SHEET_SETUP.md` — 광고비 Google Sheet
- `docs/04_SERA_SETUP.md` — SERA 참고 데이터
- `docs/05_SELLMATE_IAPPS_SETUP.md` — Sellmate/iApps
- `docs/06_HISTORICAL_DATA_SETUP.md` — 기존 일일보고 백필
- `docs/07_RECOVERY_ENGINE.md` — 매출복구 판단
- `docs/09_DATA_MAPPING.md` — 지표별 데이터 원천/계산식
