from datetime import datetime, timedelta, timezone

import pytest

from hiclaw.runtime_types import ConversationRef
from hiclaw.scheduler_store import init_task_db
from hiclaw.task_repository import (
    claim_scheduled_task_record,
    create_scheduled_task_record,
    list_due_task_record_ids,
    list_scheduled_task_records,
    update_task_record_after_run,
)


@pytest.fixture
def isolated_task_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "tasks.db"
    monkeypatch.setattr("hiclaw.scheduler_store.TASK_DB_FILE", str(db_path))
    monkeypatch.setattr("hiclaw.task_repository.TASK_DB_FILE", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_claim_scheduled_task_record_only_succeeds_once(isolated_task_db) -> None:
    await init_task_db()
    conversation = ConversationRef(channel="telegram", target_id="1001", session_scope="telegram:chat:1001")
    run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await create_scheduled_task_record("task1234", conversation, "提醒我喝水", run_at)

    first = await claim_scheduled_task_record("task1234")
    second = await claim_scheduled_task_record("task1234")

    assert first is not None
    assert first["id"] == "task1234"
    assert first["status"] == "running"
    assert second is None


@pytest.mark.asyncio
async def test_list_due_task_record_ids_only_returns_active_due_tasks(isolated_task_db) -> None:
    await init_task_db()
    conversation = ConversationRef(channel="telegram", target_id="1001", session_scope="telegram:chat:1001")
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    await create_scheduled_task_record("due_task", conversation, "到期任务", past)
    await create_scheduled_task_record("future_task", conversation, "未来任务", future)
    await claim_scheduled_task_record("due_task")

    due_ids = await list_due_task_record_ids()

    assert due_ids == []


@pytest.mark.asyncio
async def test_update_task_record_after_run_reactivates_periodic_task(isolated_task_db) -> None:
    await init_task_db()
    conversation = ConversationRef(channel="telegram", target_id="1001", session_scope="telegram:chat:1001")
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    next_run = datetime.now(timezone.utc) + timedelta(days=1)
    await create_scheduled_task_record("daily123", conversation, "每天提醒", past, schedule_type="daily", schedule_value="09:00")
    claimed = await claim_scheduled_task_record("daily123")

    assert claimed is not None

    await update_task_record_after_run("daily123", "已执行", next_run, "active")

    tasks = await list_scheduled_task_records(channel="telegram", target_id="1001")
    assert len(tasks) == 1
    assert tasks[0]["id"] == "daily123"
    assert tasks[0]["status"] == "active"
