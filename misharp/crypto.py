from __future__ import annotations

import json

from cryptography.fernet import Fernet

from .config import get_settings


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY가 없습니다. `python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"`로 생성하세요."
        )
    return Fernet(key.encode())


def encrypt_json(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return _fernet().encrypt(raw).decode("utf-8")


def decrypt_json(value: str) -> dict:
    raw = _fernet().decrypt(value.encode("utf-8"))
    return json.loads(raw.decode("utf-8"))
