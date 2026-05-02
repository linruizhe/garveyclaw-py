from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from hiclaw.runtime_types import ConversationRef
from hiclaw.task_service import TaskCommandResult, handle_task_command


def build_conversation(channel: str = "telegram", target_id: str = "1001") -> ConversationRef:
    return ConversationRef(channel=channel, target_id=target_id, session_scope=f"{channel}:chat:{target_id}")


@pytest.mark.asyncio
async def test_schedule_in_creates_once_task(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_create_scheduled_task(conversation, prompt, run_at, schedule_type="once", schedule_value=None, continue_session=False):
        captured.update(
            conversation=conversation,
            prompt=prompt,
            run_at=run_at,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            continue_session=continue_session,
        )
        return "task1234"

    monkeypatch.setattr("hiclaw.task_service.create_scheduled_task", fake_create_scheduled_task)

    result = await handle_task_command(build_conversation(), "/schedule_in 60 1分钟后提醒我喝水")

    assert result.handled is True
    assert "task1234" in result.message
    assert captured["prompt"] == "1分钟后提醒我喝水"
    assert captured["schedule_type"] == "once"
    assert captured["schedule_value"] is None


@pytest.mark.asyncio
async def test_schedule_command_uses_natural_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    run_at = datetime(2026, 5, 2, 15, 0, tzinfo=timezone.utc)
    natural = type("NaturalSchedule", (), {
        "prompt": "提醒我喝水",
        "run_at": run_at,
        "schedule_type": "daily",
        "schedule_value": "15:00",
    })()

    async def fake_create_scheduled_task(**kwargs):
        assert kwargs["schedule_type"] == "daily"
        assert kwargs["schedule_value"] == "15:00"
        return "daily001"

    monkeypatch.setattr("hiclaw.task_service.parse_natural_schedule", lambda text: natural)
    monkeypatch.setattr("hiclaw.task_service.create_scheduled_task", fake_create_scheduled_task)

    result = await handle_task_command(build_conversation(), "/schedule 每天下午3点提醒我喝水")

    assert result.handled is True
    assert "daily001" in result.message
    assert "每天 15:00" in result.message


@pytest.mark.asyncio
async def test_tasks_command_lists_only_current_channel_target(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list_scheduled_tasks(channel, target_id):
        assert channel == "feishu"
        assert target_id == "oc_123"
        return [
            {
                "id": "abc12345",
                "next_run": "2026-05-02T15:00:00+00:00",
                "prompt": "提醒我喝水",
                "schedule_type": "daily",
                "schedule_value": "15:00",
            }
        ]

    monkeypatch.setattr("hiclaw.task_service.list_scheduled_tasks", fake_list_scheduled_tasks)

    result = await handle_task_command(
        ConversationRef(channel="feishu", target_id="oc_123", session_scope="feishu:chat:oc_123"),
        "/tasks",
    )

    assert result.handled is True
    assert "abc12345" in result.message
    assert "提醒我喝水" in result.message


@pytest.mark.asyncio
async def test_cancel_command_is_scoped_to_channel_and_target(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_cancel_scheduled_task(task_id, channel, target_id):
        assert task_id == "abc12345"
        assert channel == "tui"
        assert target_id == "tui:pid1"
        return True

    monkeypatch.setattr("hiclaw.task_service.cancel_scheduled_task", fake_cancel_scheduled_task)

    result = await handle_task_command(
        ConversationRef(channel="tui", target_id="tui:pid1", session_scope="tui:pid1"),
        "/cancel abc12345",
    )

    assert result == TaskCommandResult(True, "任务 abc12345 已取消。")


@pytest.mark.asyncio
async def test_plain_text_natural_schedule_is_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    run_at = datetime(2026, 5, 2, 9, 0, tzinfo=timezone.utc)
    natural = type("NaturalSchedule", (), {
        "prompt": "提醒我开会",
        "run_at": run_at,
        "schedule_type": "weekly",
        "schedule_value": "1|09:00",
    })()

    monkeypatch.setattr("hiclaw.task_service.parse_natural_schedule", lambda text: natural)
    monkeypatch.setattr("hiclaw.task_service.create_scheduled_task", AsyncMock(return_value="wk000001"))

    result = await handle_task_command(build_conversation(), "每周二上午9点提醒我开会")

    assert result.handled is True
    assert "wk000001" in result.message
    assert "每周二 09:00" in result.message


@pytest.mark.asyncio
async def test_unrecognized_text_is_not_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("hiclaw.task_service.parse_natural_schedule", lambda text: None)

    result = await handle_task_command(build_conversation(), "这不是定时命令")

    assert result == TaskCommandResult(False, "")
