import asyncio
import logging
import time

import pytest

from hiclaw.runtime_locks import acquire_runtime_lock, get_runtime_lock_stats


@pytest.mark.asyncio
async def test_runtime_locks_allow_different_scopes_in_parallel() -> None:
    order: list[str] = []

    async def worker(scope: str) -> None:
        async with acquire_runtime_lock(scope, "test"):
            order.append(f"start:{scope}")
            await asyncio.sleep(0.01)
            order.append(f"end:{scope}")

    await asyncio.gather(worker("scope-a"), worker("scope-b"))

    assert order.count("start:scope-a") == 1
    assert order.count("start:scope-b") == 1


@pytest.mark.asyncio
async def test_runtime_locks_serialize_same_scope() -> None:
    concurrent = 0
    max_concurrent = 0

    async def worker() -> None:
        nonlocal concurrent, max_concurrent
        async with acquire_runtime_lock("scope-a", "test"):
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            await asyncio.sleep(0.01)
            concurrent -= 1

    await asyncio.gather(worker(), worker())

    assert max_concurrent == 1


@pytest.mark.asyncio
async def test_runtime_locks_same_scope_take_serial_time() -> None:
    async def worker() -> None:
        async with acquire_runtime_lock("shared-scope", "test"):
            await asyncio.sleep(0.05)

    started = time.perf_counter()
    await asyncio.gather(worker(), worker())
    elapsed = time.perf_counter() - started

    assert elapsed >= 0.09


@pytest.mark.asyncio
async def test_runtime_locks_different_scopes_take_parallel_time() -> None:
    async def worker(scope: str) -> None:
        async with acquire_runtime_lock(scope, "test"):
            await asyncio.sleep(0.05)

    started = time.perf_counter()
    await asyncio.gather(worker("scope-a"), worker("scope-b"))
    elapsed = time.perf_counter() - started

    assert elapsed < 0.09


@pytest.mark.asyncio
async def test_runtime_locks_emit_waiting_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="hiclaw.runtime_locks")

    async with acquire_runtime_lock("scope-log", "diagnostic"):
        pass

    messages = [record.message for record in caplog.records]
    assert any("Waiting for runtime lock" in message for message in messages)
    assert any("Acquired runtime lock" in message for message in messages)
    assert any("Released runtime lock" in message for message in messages)


@pytest.mark.asyncio
async def test_runtime_lock_entries_are_cleaned_after_release() -> None:
    async with acquire_runtime_lock("scope-cleanup", "cleanup"):
        stats_during = get_runtime_lock_stats()
        assert "scope-cleanup" in stats_during
        assert stats_during["scope-cleanup"]["holders"] == 1

    stats_after = get_runtime_lock_stats()
    assert "scope-cleanup" not in stats_after


@pytest.mark.asyncio
async def test_runtime_lock_stats_show_waiters_for_same_scope() -> None:
    blocker_ready = asyncio.Event()
    release_blocker = asyncio.Event()
    waiter_started = asyncio.Event()

    async def blocker() -> None:
        async with acquire_runtime_lock("scope-waiters", "blocker"):
            blocker_ready.set()
            await release_blocker.wait()

    async def waiter() -> None:
        waiter_started.set()
        async with acquire_runtime_lock("scope-waiters", "waiter"):
            pass

    blocker_task = asyncio.create_task(blocker())
    await blocker_ready.wait()
    waiter_task = asyncio.create_task(waiter())
    await waiter_started.wait()
    await asyncio.sleep(0.01)

    stats = get_runtime_lock_stats()
    assert stats["scope-waiters"]["holders"] == 1
    assert stats["scope-waiters"]["waiting"] >= 1
    assert stats["scope-waiters"]["locked"] is True

    release_blocker.set()
    await asyncio.gather(blocker_task, waiter_task)

    assert "scope-waiters" not in get_runtime_lock_stats()
