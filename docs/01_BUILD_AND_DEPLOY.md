# 01. GitHub + PostgreSQL + Streamlit 구축

## 목표

```text
GitHub = 코드/자동실행
PostgreSQL = 데이터
Streamlit = 대표 화면
```

### A. GitHub
- Private repository 사용
- `.env`, DB, credential JSON 업로드 금지
- `.github/workflows/sync.yml`이 자동수집 담당

### B. PostgreSQL
- Streamlit과 GitHub Actions가 동시에 접근할 수 있는 인터넷 접근 가능한 DB 필요
- `DATABASE_URL`은 두 환경에 같은 값을 입력
- DB 연결에 SSL이 필요한 서비스라면 해당 서비스가 제공하는 connection string을 그대로 사용

### C. Streamlit
- main entry: `app.py`
- `requirements.txt`가 repo root에 있어야 함
- Secrets는 GitHub에 넣지 않고 Streamlit 앱 Settings의 Secrets에 별도 입력

### D. 첫 배포 체크

```bash
python -m scripts.migrate_v2
python -m scripts.doctor
pytest -q
```

### E. 데이터가 없는 초기 화면
초기에는 데이터가 비어 있어도 앱이 뜨는 것이 정상입니다. Cafe24 OAuth 후 첫 sync부터 DB에 쌓입니다.
