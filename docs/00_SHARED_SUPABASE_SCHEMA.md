# 같은 Supabase를 HERO OS / CRM OS / DAILY REPORT가 함께 쓰는 방법

## 결론

**HERO ITEM OS에서 이미 사용 중인 `DATABASE_URL`을 그대로 복사해서 사용해도 됩니다.**

MISHARP DAILY REPORT는 아래 값을 추가로 사용합니다.

```toml
DATABASE_SCHEMA = "daily_report"
```

따라서 실제 저장 구조는 다음처럼 분리됩니다.

```text
같은 Supabase PostgreSQL
│
├─ public 또는 기존 HERO 영역
│   └─ HERO ITEM OS 기존 테이블
│
├─ CRM OS가 사용하는 기존 영역
│   └─ CRM OS V2 테이블
│
└─ daily_report
    ├─ daily_conditions
    ├─ hourly_conditions
    ├─ product_sales_daily
    ├─ inventory_snapshots
    ├─ sera_product_snapshots
    ├─ management_alerts
    ├─ marketing_actions
    ├─ oauth_tokens
    ├─ oauth_states
    └─ sync_runs
```

## Streamlit Secrets

MISHARP DAILY REPORT 앱의 **Manage app → Settings → Secrets**에 입력합니다.

```toml
DATABASE_URL = "HERO ITEM OS에 있는 값을 그대로 복사"
DATABASE_SCHEMA = "daily_report"
```

`DATABASE_URL` 자체를 이 문서나 GitHub 코드에 저장하지 마세요.

## 왜 안전한가

SQLAlchemy metadata에 `daily_report` schema를 지정했기 때문에 ORM이 만드는 테이블은 `daily_report.daily_conditions`처럼 schema-qualified 상태로 생성됩니다.

앱 시작 시 아래 작업만 자동 수행합니다.

```sql
CREATE SCHEMA IF NOT EXISTS daily_report;
```

그 뒤 `Base.metadata.create_all()`은 DAILY REPORT의 `daily_report` schema 안에서만 동작합니다.

## TOKEN_ENCRYPTION_KEY

DB를 공유해도 `TOKEN_ENCRYPTION_KEY`는 DAILY REPORT용으로 새로 발급하는 것을 권장합니다.

```bash
python -m scripts.generate_fernet_key
```

출력값을 DAILY REPORT Streamlit/GitHub Secrets의 `TOKEN_ENCRYPTION_KEY`로 넣습니다.

## GitHub Actions도 동일

Streamlit과 GitHub Actions는 같은 DB를 봐야 하므로 GitHub Actions Secrets에도 동일하게 넣습니다.

```text
DATABASE_URL       = HERO OS와 동일 DB URL
DATABASE_SCHEMA    = daily_report
```

## 주의

- `DATABASE_SCHEMA`를 `public`으로 바꾸지 않는 것을 권장합니다.
- HERO OS 테이블을 DAILY REPORT로 복사하거나 삭제할 필요가 없습니다.
- CRM OS 테이블도 건드리지 않습니다.
- Supabase 프로젝트를 새로 만들 필요가 없습니다.
