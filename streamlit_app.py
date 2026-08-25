"""Backward-compatible Streamlit entrypoint.

새 배포의 Main file은 app.py를 권장합니다.
기존 Streamlit 설정이 streamlit_app.py를 가리키는 경우에도 그대로 실행되도록 유지합니다.
"""
from app import *  # noqa: F401,F403
