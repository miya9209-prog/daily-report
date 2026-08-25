# 03. 일별 광고비 Google Sheet 세팅

## 미샵 기준 Sheet

```text
Spreadsheet ID
1LaWd3Xdjc9G86UlZ5XGNY9tciXAUMpv8w10QH_Mhd6c

gid
1747434863
```

## 1. Google Cloud
1. Google Cloud project 생성
2. Google Sheets API 활성화
3. Service Account 생성
4. Key → JSON 생성
5. JSON 다운로드

JSON은 비밀번호와 같은 credential이므로 GitHub repo에 올리지 않습니다.

## 2. Sheet 공유
서비스 계정 이메일(`...@...iam.gserviceaccount.com`)을 광고비 Sheet 공유에 추가합니다.

권한은 **Viewer**면 충분합니다.

## 3. Secret

```text
GOOGLE_SERVICE_ACCOUNT_JSON={JSON 전체를 한 줄 또는 Secret 형식으로 저장}
AD_SHEET_ID=1LaWd3Xdjc9G86UlZ5XGNY9tciXAUMpv8w10QH_Mhd6c
AD_SHEET_GID=1747434863
```

## 4. 날짜/광고비 열
프로그램은 상단 30행에서 다음 aliases를 자동 탐지합니다.

날짜:
- 날짜
- 일자
- 월일
- date

광고비:
- 광고비
- 일별광고비
- 광고 비용
- ad cost
- cost

자동탐지가 안 되면 실제 헤더를 지정합니다.

```text
AD_SHEET_DATE_HEADER=실제날짜헤더
AD_SHEET_COST_HEADER=실제광고비헤더
```

같은 날짜가 여러 줄이면 합산합니다.

## 5. 테스트

```bash
python - <<'PY'
from misharp.connectors.google_adsheet import GoogleAdSheetClient
x=GoogleAdSheetClient().fetch_daily_costs()
for k in sorted(x)[-5:]: print(k, x[k])
PY
```

## 공식 문서
- https://developers.google.com/workspace/sheets/api/guides/concepts
- https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get
