from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConversationRef:
    channel: str
    target_id: str
    session_scope: str
    user_id: str | None = None
