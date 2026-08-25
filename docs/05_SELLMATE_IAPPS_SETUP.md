# 05. Sellmate / iApps 데이터 세팅

# A. Sellmate

## 필요한 데이터
① 일별 종합통계:
- 택배수량/출고수량

③ 주요 재고:
- 상품번호 또는 상품코드
- 옵션/품목코드
- 상품명
- 옵션명
- 현재고
- 판매가능재고
- 가능하면 최근 7/30일 판매량

## API 신청
Sellmate 공식 사이트의 API 신청 안내를 통해 미샵 계정 API를 신청합니다.

요청문 예:

```text
미샵 자체 경영통계 시스템을 구축하고 있습니다.
읽기 전용으로 상품/옵션별 재고와 일별 출고/송장 처리건수를 자동 조회하고자 합니다.
API 인증방식, Base URL, endpoint 문서, 실제 JSON 응답샘플, 호출제한을 요청드립니다.
```

### Sellmate에서 받아야 하는 값
- API Base URL
- API Key 또는 token
- 인증 header명
- 재고 endpoint
- 출고/택배 endpoint
- request date parameter 형식
- response JSON sample

### Secret

```text
SELLMATE_API_BASE_URL=...
SELLMATE_API_KEY=...
SELLMATE_AUTH_HEADER=Authorization
SELLMATE_INVENTORY_ENDPOINT=...
SELLMATE_SHIPPING_ENDPOINT=...
```

### 연결 후 작업
`misharp/connectors/sellmate.py`에서 실제 응답 key를 aliases에 맞춥니다.

예를 들어 Sellmate 응답이:

```json
{"itemCode":"ABC", "stockCount":17}
```

이라면 현재 adapter의 `variant_code`, `stock_qty` mapping에 `itemCode`, `stockCount`를 추가합니다.

**추측으로 API URL/필드명을 만들지 마세요. 실제 Sellmate 문서/샘플을 받은 뒤 맞추는 것이 핵심입니다.**

# B. iApps

## 필요한 데이터
- 날짜별 신규 앱 설치수
- 날짜별 앱 순방문(또는 DAU와 같은 미샵 기존 지표에 대응하는 수치)

## 업체에 확인할 내용

```text
1. 외부 통계 API가 있습니까?
2. 날짜별 신규 설치수 API는 무엇입니까?
3. 날짜별 unique app visitor / DAU API는 무엇입니까?
4. 인증방식과 호출제한은 무엇입니까?
5. API가 없다면 통계를 Google Sheet/SFTP/API endpoint로 자동 export할 수 있습니까?
```

### API가 있으면

```text
IAPPS_API_BASE_URL=...
IAPPS_API_KEY=...
IAPPS_AUTH_HEADER=Authorization
IAPPS_DAILY_ENDPOINT=...
```

### API가 없으면
우선순위:
1. iApps 자동 export → Google Sheet → API 읽기
2. iApps 자동 export → SFTP/object storage → 자동 읽기
3. 최후 수단만 수동 파일

이 프로젝트의 기본 목표는 대표의 반복 업로드 업무를 없애는 것이므로 1/2 방식부터 협의합니다.

## Sellmate 공식 API 신청 안내
- https://sellmate.io/sellmate_api
