from datetime import datetime

import pytest

from hiclaw.runtime_types import ConversationRef
from hiclaw.scheduler import check_due_tasks, compute_next_run_after_execution


def test_compute_next_run_after_execution_once_completes() -> None:
    next_run, status = compute_next_run_after_execution({"schedule_type": "once", "schedule_value": None})

    assert next_run is None
    assert status == "completed"


def test_compute_next_run_after_execution_daily_reactivates() -> None:
    next_run, status = compute_next_run_after_execution({"schedule_type": "daily", "schedule_value": "15:30"})

    assert status == "active"
    assert next_run is not None
    assert isinstance(next_run, datetime)
    assert next_run.hour == 15
    assert next_run.minute == 30


def test_compute_next_run_after_execution_weekly_reactivates() -> None:
    next_run, status = compute_next_run_after_execution({"schedule_type": "weekly", "schedule_value": "2|09:15"})

    assert status == "active"
    assert next_run is not None
    assert isinstance(next_run, datetime)
    assert next_run.weekday() == 2
    assert next_run.hour == 9
    assert next_run.minute == 15


@pytest.mark.asyncio
async def test_check_due_tasks_claims_before_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[str] = []

    class StubRouter:
        def owns(self, conversation: ConversationRef) -> bool:
            return True

        def has(self, conversation: ConversationRef) -> bool:
            return True

    claimed_task = {
        "id": "task1234",
        "channel": "telegram",
        "target_id": "1001",
        "session_scope": "telegram:chat:1001",
        "prompt": "提醒我喝水",
    }

    async def fake_list_due_task_record_ids() -> list[str]:
        return ["task1234", "task5678"]

    async def fake_claim_scheduled_task_record(task_id: str):
        return claimed_task if task_id == "task1234" else None

    async def fake_execute_scheduled_task(task, router) -> None:
        executed.append(task["id"])

    async def fake_release_claimed_task_record(task_id: str) -> None:
        raise AssertionError(f"did not expect release for claimed task {task_id}")

    monkeypatch.setattr("hiclaw.scheduler.list_due_task_record_ids", fake_list_due_task_record_ids)
    monkeypatch.setattr("hiclaw.scheduler.claim_scheduled_task_record", fake_claim_scheduled_task_record)
    monkeypatch.setattr("hiclaw.scheduler.execute_scheduled_task", fake_execute_scheduled_task)
    monkeypatch.setattr("hiclaw.scheduler.release_claimed_task_record", fake_release_claimed_task_record)

    await check_due_tasks(StubRouter())

    assert executed == ["task1234"]


@pytest.mark.asyncio
async def test_check_due_tasks_releases_claim_without_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    released: list[str] = []

    class StubRouter:
        def owns(self, conversation: ConversationRef) -> bool:
            return True

        def has(self, conversation: ConversationRef) -> bool:
            return False

    claimed_task = {
        "id": "task1234",
        "channel": "tui",
        "target_id": "tui:pid1",
        "session_scope": "tui:pid1",
        "prompt": "提醒我喝水",
    }

    async def fake_list_due_task_record_ids() -> list[str]:
        return ["task1234"]

    async def fake_claim_scheduled_task_record(task_id: str):
        return claimed_task

    async def fake_release_claimed_task_record(task_id: str) -> None:
        released.append(task_id)

    async def fake_execute_scheduled_task(task, router) -> None:
        raise AssertionError("did not expect task execution when sender is missing")

    monkeypatch.setattr("hiclaw.scheduler.list_due_task_record_ids", fake_list_due_task_record_ids)
    monkeypatch.setattr("hiclaw.scheduler.claim_scheduled_task_record", fake_claim_scheduled_task_record)
    monkeypatch.setattr("hiclaw.scheduler.release_claimed_task_record", fake_release_claimed_task_record)
    monkeypatch.setattr("hiclaw.scheduler.execute_scheduled_task", fake_execute_scheduled_task)

    await check_due_tasks(StubRouter())

    assert released == ["task1234"]


@pytest.mark.asyncio
async def test_check_due_tasks_releases_claim_when_route_not_owned(monkeypatch: pytest.MonkeyPatch) -> None:
    released: list[str] = []

    class StubRouter:
        def owns(self, conversation: ConversationRef) -> bool:
            return False

        def has(self, conversation: ConversationRef) -> bool:
            raise AssertionError("did not expect has() when route is not owned")

    claimed_task = {
        "id": "task1234",
        "channel": "feishu",
        "target_id": "oc_123",
        "session_scope": "feishu:chat:oc_123",
        "prompt": "提醒我喝水",
    }

    async def fake_list_due_task_record_ids() -> list[str]:
        return ["task1234"]

    async def fake_claim_scheduled_task_record(task_id: str):
        return claimed_task

    async def fake_release_claimed_task_record(task_id: str) -> None:
        released.append(task_id)

    async def fake_execute_scheduled_task(task, router) -> None:
        raise AssertionError("did not expect task execution when route is not owned")

    monkeypatch.setattr("hiclaw.scheduler.list_due_task_record_ids", fake_list_due_task_record_ids)
    monkeypatch.setattr("hiclaw.scheduler.claim_scheduled_task_record", fake_claim_scheduled_task_record)
    monkeypatch.setattr("hiclaw.scheduler.release_claimed_task_record", fake_release_claimed_task_record)
    monkeypatch.setattr("hiclaw.scheduler.execute_scheduled_task", fake_execute_scheduled_task)

    await check_due_tasks(StubRouter())

    assert released == ["task1234"]
