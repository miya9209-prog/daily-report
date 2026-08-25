# 09. 지표별 데이터 원천과 계산식

| 화면 항목 | 기준 원천 | 계산/필드 |
|---|---|---|
| 실결제/판매액 | Cafe24 Analytics | `/sales/times` `order_amount` 합계. 기존 실결제 정의와 2주 병행검증 |
| 주문/구매건수 | Cafe24 Analytics | `/sales/times` `order_count` |
| 객단가 | 계산 | 실결제 / 주문수 |
| 전환율 | 계산 | 주문수 / 전체방문 × 100 |
| 전체방문 | Cafe24 Analytics | `/visitors/view` `visit_count` |
| 페이지뷰 | Cafe24 Analytics | `/visitors/pageview` `page_view` |
| 검색방문 | Cafe24 Analytics | `/visitpaths/keywords` |
| 광고유입 | Cafe24 Analytics | `/visitpaths/ads` |
| 광고비 | Google Sheet | 날짜별 광고비 합계 |
| 광고비율 | 계산 | 광고비 / 실결제 × 100 |
| 상품 조회수 | Cafe24 Analytics | `/products/view` 또는 `/carts/action count` |
| 장바구니 | Cafe24 Analytics | `/carts/action add_cart_count` |
| 조회→장바구니 | 계산 | 장바구니 / 상품조회 × 100 |
| 상품판매건/수량/금액 | Cafe24 Analytics | `/products/sales` |
| 장바구니→주문 | 계산 | 상품 주문건 / 장바구니 × 100 |
| 택배수량 | Sellmate | 실제 API 명세의 출고/송장 완료 정의 확정 후 |
| 현재고/옵션재고 | Sellmate | 실제 API 명세 기준 |
| 앱 설치/순방문 | iApps | API 확정 후 |
| 회원가입 | Cafe24 Customer | `mall.read_customer`는 확보하되, 기존 일일보고의 회원가입 정의와 맞는 날짜집계 endpoint/쿼리는 실연동 후 확정 |
| SERA OpV/ESpV | SERA Excel | 참고 스냅샷 |

## 중요: `0`과 `자료없음`
- 0: API가 정상 응답했고 실제 값이 0
- NULL: 원천이 아직 연동되지 않았거나 해당 기간에 데이터 정의를 확보하지 못함
- 화면에서는 NULL을 `자료없음`으로 표시
