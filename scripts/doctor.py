from __future__ import annotations

from misharp.config import get_settings
from misharp.db import DATABASE_SCHEMA, init_db, session_scope
from misharp.repositories import get_token


def flag(v):
    return "OK" if v else "MISSING"


def main():
    s = get_settings()
    init_db()
    print("DATABASE_URL", flag(s.database_url))
    print("DATABASE_SCHEMA", DATABASE_SCHEMA or "SQLite(local-no-schema)")
    print("TOKEN_ENCRYPTION_KEY", flag(s.token_encryption_key))
    print("CAFE24_MALL_ID", flag(s.cafe24_mall_id))
    print("CAFE24_CLIENT_ID", flag(s.cafe24_client_id))
    print("CAFE24_CLIENT_SECRET", flag(s.cafe24_client_secret))
    print("CAFE24_REDIRECT_URI", flag(s.cafe24_redirect_uri))
    print("GOOGLE_SERVICE_ACCOUNT_JSON", flag(s.google_service_account_json))
    with session_scope() as db:
        print("CAFE24_OAUTH_TOKEN", flag(get_token(db, "cafe24")))
    print(
        "SELLMATE",
        "READY" if s.sellmate_api_base_url and s.sellmate_inventory_endpoint and s.sellmate_api_key else "WAITING FOR API SPEC",
    )
    print(
        "IAPPS",
        "READY" if s.iapps_api_base_url and s.iapps_daily_endpoint and s.iapps_api_key else "WAITING FOR API SPEC",
    )


if __name__ == "__main__":
    main()
