# 10. Meta 상세광고 / CRM 결과 추적 — 2차 확장

현재 v2의 광고비는 미샵이 관리하는 Google Sheet의 **일별 총광고비**를 회계 기준으로 사용합니다.

따라서 `매출광고/재고회수/상세개선` 자동판정은 현재 단계에서:
- Cafe24 상품 조회
- 장바구니
- 주문/매출
- Sellmate 재고

를 중심으로 만든 **운영 후보 판정**입니다.

상품별 Meta ROAS까지 반영하려면 다음 2차 확장을 합니다.

```text
Meta Insights API
→ campaign/adset/ad 단위 spend, impressions, clicks, CTR, purchase, purchase value, ROAS
→ product_no 또는 광고명 규칙으로 상품 매핑
→ product_decision에 광고효율 보정
```

권장 최종 규칙 예:
- 매출광고: 전환 우수 + ROAS 우수 + 재고 충분
- 재고회수: 재고 많음 + 구매증거 + ROAS 손익분기 이상
- 광고중단: ROAS 약함 + 상세/퍼널도 약함
- 광고중단(재고): ROAS가 좋아도 재고 부족

CRM은 `marketing_actions` 테이블에 문자/앱푸시/카카오 발송 시각·대상·상품을 기록한 뒤, 발송 전후 시간대 매출/상품주문 변화를 비교하는 방식으로 확장합니다.
