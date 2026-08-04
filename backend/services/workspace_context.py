"""Request-scoped workspace identity with a safe local default."""
from flask import g, has_request_context

from models.workspace import DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID


def current_user_id() -> str:
    if has_request_context():
        return getattr(g, "current_user_id", DEFAULT_USER_ID)
    return DEFAULT_USER_ID


def current_workspace_id() -> str:
    if has_request_context():
        return getattr(g, "current_workspace_id", DEFAULT_WORKSPACE_ID)
    return DEFAULT_WORKSPACE_ID
