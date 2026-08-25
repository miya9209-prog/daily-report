# 02. Cafe24 API 연동 상세 가이드

## 1. Cafe24 Developer Center 앱 만들기

Cafe24 Developers에서 앱을 등록하고 아래 값을 받습니다.

- Client ID
- Client Secret
- Redirect URI
- API version
- Scope

미샵 mall ID는 실제 운영 쇼핑몰 ID를 사용합니다. 현재 코드 예시는 `miyawa`입니다.

## 2. Redirect URI

Streamlit 배포주소를 정확히 등록합니다.

```text
https://YOUR-APP.streamlit.app/
```

`http/https`, 마지막 `/`, 경로가 다르면 OAuth token 교환이 실패할 수 있으므로 Cafe24 등록값과 `CAFE24_REDIRECT_URI`를 동일하게 합니다.

## 3. Scope

v2 권장:

```text
mall.read_order mall.read_product mall.read_analytics mall.read_customer
```

- `mall.read_analytics`: 방문/PV/상품조회/장바구니/판매분석
- `mall.read_order`: 주문 상세를 추후 교차검증/확장
- `mall.read_product`: 상품/품목 정보
- `mall.read_customer`: 회원/고객 분석 확장

쓰기 권한은 사용하지 않습니다.

## 4. API version

레포 작성 시 Cafe24 공식 Admin API 최신 버전은 `2026-03-01`이므로 기본값도 동일하게 두었습니다.

```text
CAFE24_API_VERSION=2026-03-01
```

향후 버전 변경 시 Developer Center의 앱 Version과 이 값도 함께 업데이트합니다.

## 5. OAuth 최초 인증

환경설정 후 Streamlit 상단 **데이터·설정** 메뉴에서:

1. `Cafe24 인증 링크 생성`
2. `Cafe24 쇼핑몰 관리자 승인`
3. Cafe24 로그인/권한 승인
4. Redirect URI로 돌아옴
5. 프로그램이 `code`와 `state` 검증
6. Access/Refresh token 발급
7. DB `oauth_tokens`에 암호화 저장

Cafe24 Authorization Code는 1회용이고 발급 후 짧은 시간 내 token 교환이 필요하므로 링크 생성 후 바로 승인합니다.

## 6. Token 갱신

`misharp/connectors/cafe24_oauth.py`가 담당합니다.

```text
Access token 만료 임박
→ refresh token 호출
→ 새 access token + 새 refresh token 수신
→ 암호화 DB 즉시 갱신
```

Refresh token을 GitHub Secret에 고정 저장하지 않는 이유는 갱신 때 새 refresh token이 생기기 때문입니다.

## 7. Analytics에서 실제 사용하는 리소스

| 리소스 | 프로그램 사용 |
|---|---|
| `/sales/times` | 시간대별 구매자/주문/판매액 |
| `/visitors/view` | 방문자, day/hour |
| `/visitors/pageview` | 페이지뷰, day/hour |
| `/products/sales` | 상품 판매건/수량/판매액 |
| `/products/view` | 상품 조회수 |
| `/carts/action` | 상품 조회/장바구니/장바구니율 |
| `/visitpaths/keywords` | 검색유입 |
| `/visitpaths/ads` | 광고유입 |

## 8. 최초 API 테스트

OAuth가 끝난 후:

```bash
python -m scripts.sync_all --days 1 --skip-adsheet
```

성공하면 `daily_conditions`, `product_sales_daily`, `hourly_conditions`에 데이터가 생깁니다.

## 9. 401/403/429 대응

- 401: token 만료/잘못된 token → OAuth/refresh 상태 확인
- 403: Scope 부족 → 앱 Scope와 재승인 확인
- 429: 호출 제한 → 잠시 대기. connector에 retry/backoff 적용되어 있음

Admin API는 응답의 usage/remain header를 보고 호출량을 조정하는 확장도 권장합니다.

## 공식 문서
- https://developers.cafe24.com/docs-new/docs/guide/intro
- https://developers.cafe24.com/docs-new/docs/guide/oauth2-authentication
- https://developers.cafe24.com/docs/api/admin/
- https://developers.cafe24.com/docs/ko/api/cafe24data/
