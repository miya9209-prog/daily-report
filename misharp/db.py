from __future__ import annotations

import re
from contextlib import contextmanager

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


settings = get_settings()
_IS_SQLITE = settings.database_url.startswith("sqlite")


def _validate_schema_name(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return "daily_report"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError("DATABASE_SCHEMA는 영문/숫자/밑줄만 사용할 수 있으며 숫자로 시작할 수 없습니다.")
    return value


DATABASE_SCHEMA = None if _IS_SQLITE else _validate_schema_name(settings.database_schema)


class Base(DeclarativeBase):
    # PostgreSQL 운영환경에서는 MISHARP DAILY REPORT 전용 schema를 사용합니다.
    # SQLite 로컬개발에서는 schema를 사용하지 않습니다.
    metadata = MetaData(schema=DATABASE_SCHEMA)


connect_args = {"check_same_thread": False} if _IS_SQLITE else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_app_schema() -> None:
    """Create only the DAILY REPORT schema when using PostgreSQL.

    The same Supabase DATABASE_URL can therefore be shared with HERO ITEM OS / CRM OS
    without sharing their tables.
    """
    if DATABASE_SCHEMA is None:
        return
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DATABASE_SCHEMA}"'))


def qualified_table_name(table: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError("잘못된 테이블명입니다.")
    if DATABASE_SCHEMA:
        return f'"{DATABASE_SCHEMA}"."{table}"'
    return f'"{table}"'


def init_db() -> None:
    from . import models  # noqa: F401

    ensure_app_schema()
    Base.metadata.create_all(bind=engine)
