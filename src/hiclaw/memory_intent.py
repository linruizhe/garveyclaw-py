from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryIntent:
    category: str
    content: str
    confidence: str
    reason: str


AUTO_ACCEPT_CATEGORIES = {"profile", "preferences", "rules"}


EXPLICIT_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"^(?:你要记得|你记住|你给我记住)[：:，,\s]*(?P<content>.+)$"), "rules", "explicit_remember"),
    (re.compile(r"^(?:帮我记住|帮我记一下|把这个记住|把这条记住|把这个记下来|把这条记下来)[：:，,\s]*(?P<content>.+)$"), "general", "explicit_remember"),
    (re.compile(r"^(?:记住这个|记住这点|记一下这个|记下来)[：:，,\s]*(?P<content>.+)$"), "general", "explicit_remember"),
    (re.compile(r"^(?:以后你要|下次你要|后面你要|之后你要)[：:，,\s]*(?P<content>.+)$"), "rules", "future_rule"),
    (re.compile(r"^(?:以后不要|下次不要|以后别再|下次别再)[：:，,\s]*(?P<content>.+)$"), "rules", "future_rule"),
    (re.compile(r"^(?:以后回答我时要|下次回答我时要|之后回答我时要)[：:，,\s]*(?P<content>.+)$"), "rules", "response_rule"),
    (re.compile(r"^(?:你可以叫我|以后叫我|下次叫我)[：:，,\s]*(?P<content>.+)$"), "profile", "addressing_rule"),
    (re.compile(r"^(?:你以后叫|以后你叫|下次你叫)[：:，,\s]*(?P<content>.+)$"), "rules", "assistant_name_rule"),
    (re.compile(r"^(?:以后都用|以后用|下次用)[：:，,\s]*(?P<content>.+)$"), "preferences", "language_preference"),
    (re.compile(r"^(?:我喜欢你用|我希望你用|我更喜欢你用)[：:，,\s]*(?P<content>.+)$"), "preferences", "preference_statement"),
)

PROFILE_HINTS = ("我叫", "我是", "我是做", "我的名字", "你可以叫我")
PREFERENCE_HINTS = ("我喜欢", "我不喜欢", "我习惯", "我偏好", "我通常", "我更喜欢")
PROJECT_HINTS = ("这个项目", "我的项目", "当前项目", "HiClaw", "这个仓库")


def _normalize_memory_content(content: str) -> str:
    normalized = content.strip().strip("，,。；;：:！!？?")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized[:500]


def _classify_category(content: str, default_category: str) -> str:
    if any(hint in content for hint in PROFILE_HINTS):
        return "profile"
    if any(hint in content for hint in PREFERENCE_HINTS):
        return "preferences"
    if any(hint in content for hint in PROJECT_HINTS):
        return "projects"
    return default_category


def detect_memory_intent(text: str) -> MemoryIntent | None:
    stripped = text.strip()
    if not stripped:
        return None

    for pattern, default_category, reason in EXPLICIT_PATTERNS:
        match = pattern.match(stripped)
        if not match:
            continue
        content = _normalize_memory_content(match.group("content"))
        if not content:
            return None
        category = _classify_category(content, default_category)
        return MemoryIntent(category=category, content=content, confidence="high", reason=reason)

    return None


def should_auto_accept_memory_intent(intent: MemoryIntent) -> bool:
    return intent.confidence == "high" and intent.category in AUTO_ACCEPT_CATEGORIES


def build_memory_intent_ack(intent: MemoryIntent, auto_accepted: bool, debug: bool = False, detail: str = "") -> str:
    if auto_accepted:
        text = "好，这条我记住了，后面会按这个来。"
    else:
        text = "好，这条我先记下，之后会按这个来。"

    if debug:
        extras = [
            f"- 分类：{intent.category}",
            f"- 原因：{intent.reason}",
        ]
        if detail:
            extras.append(f"- 记录：{detail}")
        return text + "\n" + "\n".join(extras)
    return text
