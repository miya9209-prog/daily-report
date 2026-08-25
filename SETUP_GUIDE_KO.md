# 미샵 데일리 리포트 — 전체 구축 가이드

> **중요 — DB는 새로 만들지 않습니다.**  
> HERO ITEM OS에서 이미 사용하는 Supabase `DATABASE_URL`을 그대로 재사용하고, DAILY REPORT만 `DATABASE_SCHEMA = "daily_report"`로 분리합니다. CRM OS V2처럼 같은 Supabase 프로젝트를 함께 써도 테이블은 섞이지 않습니다.


이 문서는 개발 경험이 많지 않아도 **처음부터 실제 운영까지** 순서대로 따라갈 수 있도록 작성했습니다.

---

## 0. 먼저 확정해야 할 운영 원칙

- 평소 운영에서 Excel/CSV를 올리지 않는다.
- Cafe24, Google Sheet, Sellmate, iApps의 데이터를 자동 수집한다.
- DB가 원본 누적 저장소이고 Streamlit은 조회/판단 화면이다.
- SERA는 실시간 참고/검증 데이터로만 사용한다.
- 기존 `★★미샵일일보고-2022년.xlsx`는 과거 2020~2026 이력을 만들기 위해 **최초 1회만** 사용한다.
- 핵심 데이터 메뉴 3개와 `데이터·설정` 관리 메뉴를 상단 가로 메뉴로 구성한다.

---

# 1단계. GitHub 레포 만들기

1. GitHub에서 **New repository**를 누릅니다.
2. 이름: `misharp-daily-report`
3. 반드시 **Private**로 생성합니다.
4. 이 ZIP을 압축 해제한 뒤 전체 파일을 레포에 올립니다.
5. `.env`, `.streamlit/secrets.toml`, DB 파일, API key 파일은 절대 커밋하지 않습니다.

로컬 PC에서 Git을 쓴다면:

```bash
git init
git add .
git commit -m "MISHARP DAILY REPORT initial"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO>
git push -u origin main
```

---

# 2단계. HERO ITEM OS의 Supabase DB 재사용

새 Supabase 프로젝트를 만들지 않습니다. **HERO ITEM OS에서 현재 사용 중인 `DATABASE_URL`을 그대로 복사**합니다.

MISHARP DAILY REPORT에는 아래 두 값을 사용합니다.

```text
DATABASE_URL=HERO_ITEM_OS와_동일한_값
DATABASE_SCHEMA=daily_report
```

같은 PostgreSQL 서버를 사용하지만 DAILY REPORT 테이블은 `daily_report` schema 안에만 생성됩니다. HERO ITEM OS 및 CRM OS의 기존 테이블은 건드리지 않습니다.

처음 테스트만 할 때는 기본 SQLite도 동작합니다.

```text
DATABASE_URL=sqlite:///misharp_daily_report.db
```

하지만 Streamlit과 GitHub Actions가 서로 다른 서버에서 실행되므로 **운영은 원격 PostgreSQL**이 필요합니다.

---

# 3단계. 토큰 암호화키 생성

Cafe24 OAuth token을 DB에 평문으로 저장하지 않기 위한 Fernet key입니다.

```bash
python -m scripts.generate_fernet_key
```

출력값을 복사해서 다음 이름으로 저장합니다.

```text
TOKEN_ENCRYPTION_KEY=출력값
```

이 값은 나중에 바꾸면 기존에 암호화해둔 Cafe24 token을 읽을 수 없으니, 운영 시작 후에는 함부로 변경하지 않습니다.

---

# 4단계. Streamlit 먼저 배포

Cafe24 앱 등록 시 Redirect URI가 필요하므로 **Streamlit 주소를 먼저 확보**하는 편이 쉽습니다.

1. Streamlit Community Cloud 로그인
2. Create app
3. GitHub의 `misharp-daily-report` repo 선택
4. Branch: `main`
5. Main file: `app.py`
6. Deploy
7. 생성된 URL을 기록합니다.

예:

```text
https://misharp-daily-report.streamlit.app/
```

첫 배포에서 DB가 아직 없으면 앱은 빨간 traceback 대신 `DATABASE_URL / DATABASE_SCHEMA` 설정 안내 화면을 표시합니다. URL을 확보한 뒤 Secrets를 넣으면 됩니다.

---

# 5단계. Cafe24 API 앱 등록 및 OAuth 연동

상세는 `docs/02_CAFE24_API_SETUP.md` 참고.

필요한 값:

```text
CAFE24_MALL_ID=miyawa
CAFE24_CLIENT_ID=...
CAFE24_CLIENT_SECRET=...
CAFE24_REDIRECT_URI=https://YOUR-APP.streamlit.app/
CAFE24_SCOPES=mall.read_order mall.read_product mall.read_analytics mall.read_customer
CAFE24_API_VERSION=2026-03-01
```

Streamlit 상단 **데이터·설정** 메뉴에서:

```text
Cafe24 인증 링크 생성
→ Cafe24 쇼핑몰 관리자 승인
→ Streamlit으로 자동 복귀
→ Access/Refresh Token 암호화 저장
```

최초 1회 이후에는 refresh token으로 자동 갱신합니다.

---

# 6단계. Google 광고비 시트 연동

현재 미샵 광고비 원천:

```text
Spreadsheet ID: 1LaWd3Xdjc9G86UlZ5XGNY9tciXAUMpv8w10QH_Mhd6c
Sheet gid: 1747434863
```

상세는 `docs/03_GOOGLE_AD_SHEET_SETUP.md`.

핵심:

1. Google Cloud에서 project 생성
2. Google Sheets API 활성화
3. 서비스 계정 생성
4. JSON key 생성
5. 서비스 계정 이메일을 광고비 Sheet에 **Viewer**로 공유
6. JSON 전체 내용을 `GOOGLE_SERVICE_ACCOUNT_JSON` secret에 저장
7. 날짜/광고비 헤더 자동 탐지 실패 시 실제 헤더명을 Secret에 지정

```text
AD_SHEET_DATE_HEADER=날짜
AD_SHEET_COST_HEADER=광고비
```

---

# 7단계. 과거 일일보고 1회 적재

기존 파일은 월별 시트가 섞여 있고 연도별 형식도 조금씩 다르므로, 전용 importer가 포함되어 있습니다.

먼저 검사:

```bash
python -m scripts.import_legacy_daily_report "★★미샵일일보고-2022년.xlsx" --dry-run
```

정상적으로 일자 수가 나오면 실제 적재:

```bash
python -m scripts.import_legacy_daily_report "★★미샵일일보고-2022년.xlsx"
```

이 작업은 **한 번만** 하면 됩니다.

이후 ① 일별 종합통계 하단에서 현재 선택기간에 대응하는 전년도·전전년도 동일 날짜 구간이 자동 비교됩니다.

---

# 8단계. SERA 참고 데이터 세팅

SERA는 카페24 쇼핑몰 화면 위에서 실시간 조회/주문/클릭가치를 보는 분석 도구입니다.

현재 제공받은 SERA 보고서 두 세대 형식을 모두 읽도록 parser를 만들었습니다.

- 신형: 상품번호/상품코드 컬럼 있음
- 구형: 상품번호가 없으면 `상품상세경로`의 `product_no`에서 추출

보고서가 있으면:

```bash
python -m scripts.import_sera_report "SERA_report_20260813_233242.xlsx"
```

SERA 데이터는 상품 판매 베스트 화면에서 `SERA 조회수 / 주문수 / OpV / ESpV`로 비교됩니다.

**중요:** SERA를 매출 통계의 기준 원천으로 쓰지 않습니다. Cafe24 Analytics API를 기준으로 하고 SERA는 실시간 교차검증용입니다.

---

# 9단계. Sellmate API 세팅

Sellmate는 공개 페이지에서 API 신청 절차는 제공하지만, 세부 endpoint/인증/응답 필드는 계약/계정 환경에 맞춰 받아야 합니다.

Sellmate에 다음을 요청합니다.

```text
1. 미샵 계정 API 사용 신청
2. 인증 방식(API Key/Bearer/별도 서명)
3. Base URL
4. 재고 조회 endpoint
5. 출고/송장 처리 건수 조회 endpoint
6. 상품/옵션 식별키 설명
7. 재고 응답 JSON 실제 샘플 1건
8. 호출 제한
```

받은 뒤 `.env`/Secrets에:

```text
SELLMATE_API_BASE_URL=...
SELLMATE_API_KEY=...
SELLMATE_AUTH_HEADER=Authorization
SELLMATE_INVENTORY_ENDPOINT=...
SELLMATE_SHIPPING_ENDPOINT=...
```

그리고 `misharp/connectors/sellmate.py`의 aliases를 실제 JSON key에 맞춥니다.

---

# 10단계. iApps 데이터 세팅

iApps에는 다음을 문의합니다.

```text
- 외부 통계 API 제공 여부
- 인증 방식
- 날짜별 앱 신규 설치수 endpoint
- 날짜별 앱 순방문/DAU endpoint
- 호출 제한
```

API를 받으면:

```text
IAPPS_API_BASE_URL=...
IAPPS_API_KEY=...
IAPPS_DAILY_ENDPOINT=...
```

만약 외부 API가 없다면 2순위 방식은 **iApps 자동 내보내기 → Google Sheet → 프로그램 자동 조회**입니다. 사람이 매일 Excel을 올리는 방식으로 돌아가지는 않습니다.

---

# 10.5단계. HERO OS의 Supabase DB를 그대로 재사용

1. HERO ITEM OS의 Streamlit 앱에서 **Manage app → Settings → Secrets**를 엽니다.
2. `DATABASE_URL` 값을 복사합니다.
3. MISHARP DAILY REPORT의 Streamlit Secrets에 같은 `DATABASE_URL`을 붙여넣습니다.
4. 바로 아래에 다음 줄을 추가합니다.

```toml
DATABASE_SCHEMA = "daily_report"
```

이 레포는 PostgreSQL일 때 자동으로 `daily_report` schema를 만들고 모든 테이블을 그 안에 생성합니다. HERO/CRM 테이블은 수정하지 않습니다.

# 11단계. Streamlit Secrets 입력

Streamlit 앱 → Settings → Secrets에 필요한 값을 입력합니다.

최소 운영 필수:

```toml
DATABASE_URL = "postgresql+psycopg://..."
DATABASE_SCHEMA = "daily_report"
TOKEN_ENCRYPTION_KEY = "..."
CAFE24_MALL_ID = "miyawa"
CAFE24_CLIENT_ID = "..."
CAFE24_CLIENT_SECRET = "..."
CAFE24_REDIRECT_URI = "https://YOUR-APP.streamlit.app/"
CAFE24_SCOPES = "mall.read_order mall.read_product mall.read_analytics mall.read_customer"
CAFE24_API_VERSION = "2026-03-01"
GOOGLE_SERVICE_ACCOUNT_JSON = "{...JSON 전체...}"
AD_SHEET_ID = "1LaWd3Xdjc9G86UlZ5XGNY9tciXAUMpv8w10QH_Mhd6c"
AD_SHEET_GID = "1747434863"
```

---

# 12단계. GitHub Actions Secrets 입력

GitHub repo → Settings → Secrets and variables → Actions → New repository secret.

Streamlit에 넣은 운영 Secret을 GitHub Actions에도 동일하게 넣습니다.

특히:

- DATABASE_URL
- DATABASE_SCHEMA (`daily_report`)
- TOKEN_ENCRYPTION_KEY
- CAFE24_MALL_ID
- CAFE24_CLIENT_ID
- CAFE24_CLIENT_SECRET
- CAFE24_REDIRECT_URI
- CAFE24_SCOPES
- CAFE24_API_VERSION
- GOOGLE_SERVICE_ACCOUNT_JSON
- AD_SHEET_ID / AD_SHEET_GID
- Sellmate/iApps 값(준비된 뒤)

---

# 13단계. DB migration

```bash
python -m scripts.migrate_v2
```

v1 DB가 이미 있으면 기존 테이블에 v2 퍼널/판정 컬럼을 추가하고, 새 시간대/SERA/경보 테이블을 생성합니다.

---

# 14단계. 첫 자동수집 테스트

로컬 또는 GitHub Actions에서:

```bash
python -m scripts.sync_all --days 1
```

7일 재검증:

```bash
python -m scripts.sync_all --days 7 --inventory
```

설정 점검:

```bash
python -m scripts.doctor
```

---

# 15단계. GitHub Actions 동작

현재 workflow는 서울 시간 기준:

- 매시 17분/47분: 당일 데이터를 갱신
- 매일 03:13: 최근 7일을 재검증하고 Sellmate 재고 스냅샷 시도

매시 정각을 피한 이유는 예약 실행 서비스가 정각 부근에서 지연될 가능성을 줄이기 위해서입니다.

---

# 16단계. 최종 검수

① 일별 종합통계

- 오늘 매출/주문/객단가/방문/전환율이 Cafe24 관리자와 비슷한가
- 광고비가 Google Sheet와 일치하는가
- 상품조회→장바구니→주문 퍼널이 표시되는가
- 전년/전전년 동일기간 비교가 맞는가
- 시간대 데이터가 들어오는가

② 상품 판매 베스트

- 같은 상품이 기간 내 한 줄로 합쳐지는가
- 조회/장바구니/주문/매출이 기간 합산되는가
- 자동판정이 납득 가능한가
- SERA 참고값이 있으면 별도 열로 보이는가

③ 주요 재고

- Sellmate 현재고/판매가능재고와 맞는가
- 옵션 단위로 구분되는가
- 시즌 종료일을 바꾸면 필요 일판매량이 바뀌는가

---

# 17단계. 운영 시작 후 2주간은 반드시 병행 검증

API 연동 첫 7~14일은 기존 보고 방식과 나란히 비교합니다.

특히 아래의 **정의**가 같은지 확인합니다.

- `실결제`: Cafe24 Analytics 판매액과 미샵 기존 실결제 정의
- 주문수: 주문건 vs 상품주문건
- 방문자: 전체방문 정의
- 광고비: Google Sheet 최종 입력값
- 택배수량: Sellmate에서 어떤 처리상태를 카운트하는지

오차가 발견되면 UI를 바꾸지 않고 **connector/계산식만 수정**합니다.


## Cafe24 OAuth 승인 직후 확인

`데이터·설정`에서 순서대로 실행합니다.

1. `Cafe24 연결 테스트`
2. `어제 Cafe24 데이터 수집`
3. `일별 종합통계`에서 어제 숫자 확인

Google 광고비, Sellmate, iApps가 아직 미설정이어도 위 Cafe24 단독 테스트/수집은 실행할 수 있습니다.
