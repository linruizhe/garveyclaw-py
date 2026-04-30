from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from hiclaw.config import (
    CLAUDE_MEMORY_FILE,
    CONVERSATIONS_DIR,
    LONG_TERM_MEMORY_DIR,
    MEMORY_CANDIDATES_DIR,
    MEMORY_DIR,
    PROJECT_ROOT,
    SESSION_SUMMARIES_DIR,
    WORKING_STATE_FILE,
    WORKSPACE_DIR,
)

LONG_TERM_FILES = {
    "profile": LONG_TERM_MEMORY_DIR / "profile.md",
    "preferences": LONG_TERM_MEMORY_DIR / "preferences.md",
    "projects": LONG_TERM_MEMORY_DIR / "projects.md",
    "rules": LONG_TERM_MEMORY_DIR / "rules.md",
}

DEFAULT_WORKING_STATE = {
    "active_goal": "",
    "active_intent_type": "",
    "active_tasks": [],
    "recent_decisions": [],
    "open_questions": [],
    "touched_files": [],
    "updated_at": "",
}
FILE_REFERENCE_PATTERN = re.compile(r"(?:src|workspace|data|assets|skills|scripts)[/\\][^\s'\"`]+")
TASK_INTENT_PATTERN = re.compile(r"(帮我|请你|实现|修改|优化|重构|添加|增加|修复|排查|检查|分析|设计|整理|更新|刷新|生成|创建)")
QUESTION_INTENT_PATTERN = re.compile(r"(吗|么|什么|为何|为什么|如何|咋|怎么|哪|多少|是否|可不可以|能不能|\?|？)")
FILE_WORK_INTENT_PATTERN = re.compile(r"(文件|代码|模块|函数|类|路径|README|SVG|架构图|session|记忆|上下文|prompt)")


def _sanitize_scope(scope: str | None) -> str:
    if not scope:
        return "default"
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", scope.strip()).strip("_")
    return normalized or "default"


def get_session_summary_file(scope: str | None = None) -> Path:
    return SESSION_SUMMARIES_DIR / f"{_sanitize_scope(scope)}.json"


def get_working_state_file(scope: str | None = None) -> Path:
    safe_scope = _sanitize_scope(scope)
    if safe_scope == "default":
        return WORKING_STATE_FILE
    return WORKING_STATE_FILE.with_name(f"{WORKING_STATE_FILE.stem}_{safe_scope}{WORKING_STATE_FILE.suffix}")


def ensure_memory_files() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    LONG_TERM_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

    if not CLAUDE_MEMORY_FILE.exists():
        CLAUDE_MEMORY_FILE.write_text(
            "# 长期记忆\n\n"
            "## 目录说明\n"
            f"- 项目根目录：`{PROJECT_ROOT}`\n"
            f"- 工作区目录：`{WORKSPACE_DIR}`\n"
            f"- 长期记忆文件：`{CLAUDE_MEMORY_FILE}`\n"
            f"- 对话记录目录：`{CONVERSATIONS_DIR}`\n\n"
            "## 文件使用规则\n"
            "- 长期稳定信息写入 CLAUDE.md 或 long_term 目录。\n"
            "- 每轮对话原始记录追加写入 conversations 目录。\n"
            "- 工作区文件操作尽量限制在工作区目录内。\n\n"
            "## 默认背景\n"
            "- 当前项目是一个支持多入口和双 Provider 的个人 Agent。\n"
            "- 需要长期复用的信息优先结构化沉淀，而不是只追加原始日志。\n",
            encoding="utf-8",
        )

    defaults = {
        "profile": "# 用户画像\n\n- 暂无结构化画像。\n",
        "preferences": "# 用户偏好\n\n- 暂无结构化偏好。\n",
        "projects": "# 项目背景\n\n- 暂无结构化项目背景。\n",
        "rules": "# 长期规则\n\n- 暂无长期规则。\n",
    }
    for key, path in LONG_TERM_FILES.items():
        if not path.exists():
            path.write_text(defaults[key], encoding="utf-8")

    if not WORKING_STATE_FILE.exists():
        WORKING_STATE_FILE.write_text(json.dumps(DEFAULT_WORKING_STATE, ensure_ascii=False, indent=2), encoding="utf-8")

    default_summary_file = get_session_summary_file()
    if not default_summary_file.exists():
        default_summary_file.write_text(
            json.dumps(
                {
                    "session_scope": "default",
                    "updated_at": "",
                    "latest_user_message": "",
                    "latest_assistant_reply_excerpt": "",
                    "recent_topics": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def _read_json_file(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(fallback)
    return data if isinstance(data, dict) else dict(fallback)


def _compact_text(value: str, limit: int) -> str:
    return value.strip().replace("\n", " ")[:limit]


def _append_unique_tail(items: list[str], value: str, max_items: int) -> list[str]:
    normalized = value.strip()
    if not normalized:
        return items[-max_items:]
    result = [item for item in items if item != normalized]
    result.append(normalized)
    return result[-max_items:]


def _extract_touched_files(*texts: str) -> list[str]:
    matches: list[str] = []
    for text in texts:
        for match in FILE_REFERENCE_PATTERN.findall(text):
            normalized = match.replace("\\", "/")
            if normalized not in matches:
                matches.append(normalized)
    return matches


def _extract_open_question(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if any(stripped.endswith(mark) for mark in ("?", "？")):
        return _compact_text(stripped, 200)
    return ""


def _classify_intent(user_message: str) -> str:
    stripped = user_message.strip()
    if not stripped:
        return "empty"
    if stripped.startswith("/"):
        return "command"
    if FILE_WORK_INTENT_PATTERN.search(stripped) and TASK_INTENT_PATTERN.search(stripped):
        return "file_task"
    if TASK_INTENT_PATTERN.search(stripped):
        return "task"
    if QUESTION_INTENT_PATTERN.search(stripped):
        return "question"
    return "note"


def _extract_goal_candidate(user_message: str, intent_type: str) -> str:
    compact = _compact_text(user_message, 200)
    if intent_type in {"task", "file_task"}:
        return compact
    if intent_type == "question":
        return compact
    return ""


def _extract_decision_candidate(assistant_reply: str, intent_type: str) -> str:
    compact = _compact_text(assistant_reply, 240)
    if intent_type in {"task", "file_task", "question"}:
        return compact
    return compact[:160]


def load_long_term_memory() -> str:
    ensure_memory_files()
    return CLAUDE_MEMORY_FILE.read_text(encoding="utf-8")


def append_long_term_memory(note: str) -> None:
    ensure_memory_files()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with CLAUDE_MEMORY_FILE.open("a", encoding="utf-8") as file:
        file.write(f"\n## 追加记忆 {timestamp}\n- {note.strip()}\n")


def append_structured_long_term_memory(note: str, category: str) -> Path:
    ensure_memory_files()
    safe_category = re.sub(r"[^a-zA-Z0-9_-]+", "_", category.strip()).strip("_") or "general"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if safe_category in LONG_TERM_FILES:
        target = LONG_TERM_FILES[safe_category]
        with target.open("a", encoding="utf-8") as file:
            file.write(f"\n## 自动记忆 {timestamp}\n- {note.strip()}\n")
        return target
    append_long_term_memory(note)
    return CLAUDE_MEMORY_FILE


def append_memory_candidate(note: str, category: str = "general") -> Path:
    ensure_memory_files()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_category = re.sub(r"[^a-zA-Z0-9_-]+", "_", category.strip()).strip("_") or "general"
    target = MEMORY_CANDIDATES_DIR / f"{timestamp}_{safe_category}.md"
    target.write_text(f"# Memory Candidate\n\n- category: {safe_category}\n- created_at: {datetime.now().isoformat(timespec='seconds')}\n\n{note.strip()}\n", encoding="utf-8")
    return target


def list_memory_candidates(limit: int = 20) -> list[Path]:
    ensure_memory_files()
    return sorted(MEMORY_CANDIDATES_DIR.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]


def get_memory_candidate(name: str) -> Path | None:
    ensure_memory_files()
    target = MEMORY_CANDIDATES_DIR / name.strip()
    return target if target.exists() and target.is_file() else None


def accept_memory_candidate(name: str, category: str = "general") -> Path:
    candidate = get_memory_candidate(name)
    if candidate is None:
        raise FileNotFoundError(name)

    content = candidate.read_text(encoding="utf-8").strip()
    body = content.split("\n\n", maxsplit=2)[-1].strip() if content else ""
    safe_category = re.sub(r"[^a-zA-Z0-9_-]+", "_", category.strip()).strip("_") or "general"

    target = append_structured_long_term_memory(body, safe_category)

    candidate.unlink()
    return target


def reject_memory_candidate(name: str) -> None:
    candidate = get_memory_candidate(name)
    if candidate is None:
        raise FileNotFoundError(name)
    candidate.unlink()


def load_working_state(scope: str | None = None) -> dict[str, Any]:
    ensure_memory_files()
    data = _read_json_file(get_working_state_file(scope), DEFAULT_WORKING_STATE)
    merged = dict(DEFAULT_WORKING_STATE)
    merged.update(data)
    return merged


def save_working_state(state: dict[str, Any], scope: str | None = None) -> None:
    ensure_memory_files()
    payload = dict(DEFAULT_WORKING_STATE)
    payload.update(state)
    payload["session_scope"] = _sanitize_scope(scope)
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    get_working_state_file(scope).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update_working_state_from_turn(user_message: str, assistant_reply: str, scope: str | None = None) -> dict[str, Any]:
    ensure_memory_files()
    state = load_working_state(scope)

    intent_type = _classify_intent(user_message)
    active_goal = _extract_goal_candidate(user_message, intent_type)
    recent_decision = _extract_decision_candidate(assistant_reply, intent_type)
    open_question = _extract_open_question(assistant_reply)
    touched_files = _extract_touched_files(user_message, assistant_reply)

    state["active_intent_type"] = intent_type
    if active_goal:
        state["active_goal"] = active_goal
    state["active_tasks"] = _append_unique_tail(list(state.get("active_tasks") or []), active_goal, 5)
    state["recent_decisions"] = _append_unique_tail(list(state.get("recent_decisions") or []), recent_decision, 8)

    existing_questions = list(state.get("open_questions") or [])
    if open_question:
        state["open_questions"] = _append_unique_tail(existing_questions, open_question, 5)
    else:
        state["open_questions"] = existing_questions[-5:]

    merged_files = list(state.get("touched_files") or [])
    for touched in touched_files:
        merged_files = _append_unique_tail(merged_files, touched, 12)
    state["touched_files"] = merged_files[-12:]

    save_working_state(state, scope)
    return state


def load_session_summary(scope: str | None = None) -> dict[str, Any]:
    ensure_memory_files()
    return _read_json_file(
        get_session_summary_file(scope),
        {
            "session_scope": _sanitize_scope(scope),
            "updated_at": "",
            "latest_user_message": "",
            "latest_assistant_reply_excerpt": "",
            "recent_topics": [],
        },
    )


def save_session_summary(scope: str | None, user_message: str, assistant_reply: str) -> None:
    ensure_memory_files()
    summary = load_session_summary(scope)
    recent_topics = list(summary.get("recent_topics") or [])
    compact_user_message = user_message.strip().replace("\n", " ")
    if compact_user_message:
        recent_topics.append(compact_user_message[:80])
    recent_topics = recent_topics[-5:]
    payload = {
        "session_scope": _sanitize_scope(scope),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "latest_user_message": compact_user_message[:500],
        "latest_assistant_reply_excerpt": assistant_reply.strip().replace("\n", " ")[:800],
        "recent_topics": recent_topics,
    }
    get_session_summary_file(scope).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_context_snapshot(scope: str | None = None) -> str:
    ensure_memory_files()
    working_state = load_working_state(scope)
    session_summary = load_session_summary(scope)
    sections: list[str] = []

    for key, title in (
        ("profile", "用户画像"),
        ("preferences", "用户偏好"),
        ("projects", "项目背景"),
        ("rules", "长期规则"),
    ):
        content = LONG_TERM_FILES[key].read_text(encoding="utf-8").strip()
        sections.append(f"## {title}\n{content}")

    sections.append("## 工作记忆\n" + json.dumps(working_state, ensure_ascii=False, indent=2))
    sections.append("## 会话摘要\n" + json.dumps(session_summary, ensure_ascii=False, indent=2))
    sections.append("## 兼容长期记忆\n" + load_long_term_memory().strip())
    return "\n\n".join(sections).strip()


def append_conversation_record(user_message: str, assistant_reply: str, session_id: str | None, session_scope: str | None = None) -> None:
    ensure_memory_files()
    date_key = datetime.now().strftime("%Y-%m-%d")
    file_path = CONVERSATIONS_DIR / f"{date_key}.jsonl"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "session_id": session_id,
        "session_scope": _sanitize_scope(session_scope),
        "user_message": user_message,
        "assistant_reply": assistant_reply,
    }
    with file_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    save_session_summary(session_scope, user_message, assistant_reply)
    update_working_state_from_turn(user_message, assistant_reply, session_scope)
