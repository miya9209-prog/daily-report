from __future__ import annotations

import base64
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from dateutil.parser import isoparse

from ..config import get_settings
from ..crypto import decrypt_json, encrypt_json
from ..db import session_scope
from ..repositories import consume_oauth_state, get_token, save_oauth_state, save_token
from .http import resilient_session

PROVIDER = "cafe24"


def _basic_auth(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def build_authorize_url() -> str:
    s = get_settings()
    missing = [name for name, value in {
        "CAFE24_MALL_ID": s.cafe24_mall_id,
        "CAFE24_CLIENT_ID": s.cafe24_client_id,
        "CAFE24_REDIRECT_URI": s.cafe24_redirect_uri,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"환경변수 누락: {', '.join(missing)}")

    state = secrets.token_urlsafe(32)
    with session_scope() as db:
        save_oauth_state(db, state, datetime.utcnow() + timedelta(minutes=10))

    params = {
        "response_type": "code",
        "client_id": s.cafe24_client_id,
        "state": state,
        "redirect_uri": s.cafe24_redirect_uri,
        "scope": s.cafe24_scopes,
    }
    return f"https://{s.cafe24_mall_id}.cafe24api.com/api/v2/oauth/authorize?{urlencode(params)}"


def exchange_code(code: str, state: str) -> dict:
    s = get_settings()
    with session_scope() as db:
        if not consume_oauth_state(db, state):
            raise RuntimeError("OAuth state가 유효하지 않거나 만료되었습니다. 인증을 다시 시작하세요.")

    url = f"https://{s.cafe24_mall_id}.cafe24api.com/api/v2/oauth/token"
    headers = {
        "Authorization": f"Basic {_basic_auth(s.cafe24_client_id, s.cafe24_client_secret)}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    response = resilient_session().post(
        url,
        headers=headers,
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": s.cafe24_redirect_uri},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    with session_scope() as db:
        save_token(db, PROVIDER, encrypt_json(payload))
    return payload


def _load_token() -> dict:
    with session_scope() as db:
        row = get_token(db, PROVIDER)
        if row is None:
            raise RuntimeError("Cafe24 토큰이 없습니다. Streamlit에서 최초 OAuth 인증을 진행하세요.")
        return decrypt_json(row.encrypted_payload)


def _parse_expiry(value: str) -> datetime:
    dt = isoparse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def refresh_token(refresh_token_value: str) -> dict:
    s = get_settings()
    url = f"https://{s.cafe24_mall_id}.cafe24api.com/api/v2/oauth/token"
    headers = {
        "Authorization": f"Basic {_basic_auth(s.cafe24_client_id, s.cafe24_client_secret)}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    response = resilient_session().post(
        url,
        headers=headers,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token_value},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    # Cafe24는 갱신 시 새 Refresh Token을 반환하고 기존 Refresh Token을 폐기하므로 즉시 DB에 덮어쓴다.
    with session_scope() as db:
        save_token(db, PROVIDER, encrypt_json(payload))
    return payload


def get_valid_access_token() -> str:
    payload = _load_token()
    expires_at = _parse_expiry(payload["expires_at"])
    now = datetime.now(timezone.utc)
    if now >= expires_at - timedelta(minutes=5):
        payload = refresh_token(payload["refresh_token"])
    return payload["access_token"]
