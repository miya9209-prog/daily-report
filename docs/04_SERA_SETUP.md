# 04. SERA 프로그램 데이터 세팅

## SERA의 역할
SERA는 Cafe24 쇼핑몰 화면에서 실시간으로 상품별 조회수, 주문율, 클릭 가치와 PC/Mobile 반응을 보는 분석 도구입니다.

이 프로젝트에서는 **기준 통계 원천이 아니라 실시간 참고/검증 원천**입니다.

왜 이렇게 두는가?
- Cafe24 Analytics API가 자동수집 가능한 공식 기준 데이터
- SERA는 실시간 진단에 유용
- 현재 확인 가능한 공개 문서에서는 별도의 외부 SERA API를 찾지 못했으므로, 자동화 핵심을 SERA에 의존하지 않음

## 1. SERA 사용 준비
Cafe24 공식 안내 기준:
1. Cafe24 App Store에서 SERA 설치
2. Chrome Web Store에서 SERA 확장 프로그램 설치
3. Chrome 우측 SERA 아이콘 클릭
4. 쇼핑몰 계정 로그인

## 2. 현재 보고서 형식 호환
이미 미샵에서 사용한 다음 구조를 parser가 지원합니다.

신형 예:
```text
상품번호, 상품코드, 상품명, 가격,
조회수, 조회_PC, 조회_Mobile,
주문수, 주문_PC, 주문_Mobile,
OpV, ESpV, 상품상세경로
```

구형 보고서에 상품번호가 없으면 `상품상세경로`의 `product_no` query에서 상품번호를 추출합니다.

## 3. SERA Excel 저장
현재 사용 중인 SERA에서 기존과 동일하게 `SERA_report_YYYYMMDD_HHMMSS.xlsx` 형태로 저장합니다.

SERA UI의 메뉴명은 버전에 따라 달라질 수 있으므로, **지금 미샵에서 이미 생성하고 있는 SERA_report 파일 생성 방식**을 그대로 사용하면 됩니다.

## 4. DB 적재

```bash
python -m scripts.import_sera_report "SERA_report_20260813_233242.xlsx"
```

저장 테이블:

```text
sera_product_snapshots
```

동일 시각+상품번호는 중복 저장하지 않습니다.

## 5. 화면에서 사용
② 상품 판매 베스트에:
- SERA 조회수
- SERA 주문수
- SERA OpV
- SERA ESpV

가 표시됩니다.

SERA와 Cafe24 API가 다르면 즉시 한쪽을 틀렸다고 보지 말고 **집계 시점/정의 차이**를 확인합니다.

## 6. 향후 SERA API가 공식 제공되면
`misharp/connectors/sera_report.py`를 `sera_api.py`로 교체하면 되고, DB/UI는 그대로 유지할 수 있습니다.

## 공식 안내
- https://support.cafe24.com/hc/ko/articles/47219635784601-SERA
