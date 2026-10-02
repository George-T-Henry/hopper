"""Batched sync pushes: chunking, resumable cursor, 413 handling (issue #9)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from hopper.storage.tasks import LocalTask
from hopper.upstream.client import PayloadTooLargeError, UpstreamClient, UpstreamError
from hopper.upstream.protocol import SyncResponse, SyncTask
from hopper.upstream.sync import SyncState, pending_changes, sync_with_upstream

INSTANCE = "t"


def _task(i: int, ms: int | None = None) -> LocalTask:
    ts = datetime.fromtimestamp((ms if ms is not None else 1_000_000 + i) / 1000, tz=UTC)
    return LocalTask(id=f"t{i:08d}", title=f"Task {i}", created_at=ts, updated_at=ts)


def _store(tasks: list[LocalTask]) -> Any:
    store = MagicMock()
    store.list_since.side_effect = lambda since, include_deleted=False: [
        t for t in tasks if int(t.updated_at.timestamp() * 1000) > since
    ]
    store.get.return_value = None
    return store


def _ok(
    tasks: list[SyncTask],
    since: int = 0,
    instance: str = INSTANCE,
    pull_limit: int | None = None,
) -> SyncResponse:
    return SyncResponse(tasks=[], server_time=5_000_000, accepted=[t.id for t in tasks])


def test_pushes_in_bounded_batches(tmp_path: Path) -> None:
    client = MagicMock()
    client.sync.side_effect = _ok
    result = sync_with_upstream(
        _store([_task(i) for i in range(250)]), client, tmp_path / ".s", INSTANCE, batch_size=100
    )
    assert [len(c.kwargs["tasks"]) for c in client.sync.call_args_list] == [100, 100, 50]
    assert len(result.pushed) == 250
    assert not result.errors


def test_byte_budget_splits_batches(tmp_path: Path) -> None:
    client = MagicMock()
    client.sync.side_effect = _ok
    sync_with_upstream(
        _store([_task(i) for i in range(10)]),
        client,
        tmp_path / ".s",
        INSTANCE,
        batch_size=100,
        batch_bytes=1,  # every task exceeds the budget, so each goes alone
    )
    assert [len(c.kwargs["tasks"]) for c in client.sync.call_args_list] == [1] * 10


def test_failure_mid_run_resumes_after_last_good_batch(tmp_path: Path) -> None:
    tasks = [_task(i) for i in range(30)]
    state_path = tmp_path / ".s"
    client = MagicMock()
    # first call succeeds (10 records), second fails
    client.sync.side_effect = [
        SyncResponse(server_time=5_000_000, accepted=[t.id for t in tasks[:10]]),
        UpstreamError("boom"),
    ]
    result = sync_with_upstream(_store(tasks), client, state_path, INSTANCE, batch_size=10)
    assert result.errors == ["boom"]

    # Retry sends only what the failed run never delivered (plus the tie-safe
    # 1 ms overlap of the last delivered task).
    retry = MagicMock()
    retry.sync.side_effect = _ok
    sync_with_upstream(_store(tasks), retry, state_path, INSTANCE, batch_size=100)
    sent = [t.id for c in retry.sync.call_args_list for t in c.kwargs["tasks"]]
    assert sent[0] == tasks[9].id
    assert sent[1:] == [t.id for t in tasks[10:]]


def test_413_halves_batch_and_retries(tmp_path: Path) -> None:
    limit = 25

    def server(
        tasks: list[SyncTask],
        since: int = 0,
        instance: str = INSTANCE,
        pull_limit: int | None = None,
    ) -> SyncResponse:
        if len(tasks) > limit:
            raise PayloadTooLargeError("413")
        return _ok(tasks)

    client = MagicMock()
    client.sync.side_effect = server
    result = sync_with_upstream(
        _store([_task(i) for i in range(100)]), client, tmp_path / ".s", INSTANCE, batch_size=100
    )
    assert not result.errors
    assert len(result.pushed) == 100


def test_413_on_single_record_reports_error(tmp_path: Path) -> None:
    client = MagicMock()
    client.sync.side_effect = PayloadTooLargeError("413: too big")
    result = sync_with_upstream(_store([_task(1)]), client, tmp_path / ".s", INSTANCE)
    assert result.errors == ["413: too big"]


def test_many_tasks_sharing_one_timestamp_still_terminate(tmp_path: Path) -> None:
    tasks = [_task(i, ms=1_000_000) for i in range(40)]
    client = MagicMock()
    client.sync.side_effect = _ok
    result = sync_with_upstream(_store(tasks), client, tmp_path / ".s", INSTANCE, batch_size=7)
    assert sorted(result.pushed) == sorted(t.id for t in tasks)


def test_final_batch_sets_snapshot_cursor(tmp_path: Path) -> None:
    client = MagicMock()
    client.sync.side_effect = _ok
    sync_with_upstream(_store([_task(i) for i in range(5)]), client, tmp_path / ".s", INSTANCE)
    state = SyncState.load(tmp_path / f".s_{INSTANCE}")
    assert state.last_sync > 1_000_100  # wall-clock snapshot, not a task timestamp


def test_pending_changes_counts_records_and_bytes(tmp_path: Path) -> None:
    count, size = pending_changes(_store([_task(i) for i in range(3)]), tmp_path / ".s", INSTANCE)
    assert count == 3
    assert size > 0


def _client_with_status(status: int, body: str, content_type: str) -> UpstreamClient:
    client = UpstreamClient(server_url="https://x", did_key=MagicMock())
    request = httpx.Request("POST", "https://x/sync")
    client._make_request = lambda *a, **k: httpx.Response(  # type: ignore[method-assign]
        status, text=body, headers={"content-type": content_type}, request=request
    )
    return client


def test_client_413_is_one_line_without_html() -> None:
    html = "<html><head><title>413 Request Entity Too Large</title></head>nginx/1.24.0</html>"
    client = _client_with_status(413, html, "text/html")
    with pytest.raises(PayloadTooLargeError) as exc:
        client.sync([])
    msg = str(exc.value)
    assert "413" in msg and "--batch-size" in msg
    assert "<" not in msg and "\n" not in msg


def test_client_other_html_error_has_no_html_dump() -> None:
    client = _client_with_status(502, "<html><body>Bad Gateway nginx</body></html>", "text/html")
    with pytest.raises(UpstreamError) as exc:
        client.sync([])
    assert "<" not in str(exc.value)
    assert "502" in str(exc.value)


# --- paged pulls -----------------------------------------------------------


def _storage_with(tmp_path: Path, stamps: list[int]):
    from hopper.upstream.storage import UpstreamStorage

    storage = UpstreamStorage(tmp_path)
    for i in range(len(stamps)):
        t = SyncTask(id=f"s{i:03d}", title="x", status="open", instance=INSTANCE)
        assert storage.put(t, from_did="did:key:x")[0]
    # Force deterministic index timestamps.
    keys = sorted(storage._index)
    for key, ts in zip(keys, stamps, strict=True):
        storage._index[key] = ts
    storage._index_by_time = sorted((ts, k) for k, ts in storage._index.items())
    return storage


def test_server_pages_cover_everything_once_including_ties(tmp_path: Path) -> None:
    stamps = [100, 200, 200, 200, 300, 400, 400, 500]
    storage = _storage_with(tmp_path, stamps)
    seen: list[str] = []
    since: int | None = 0
    pages = 0
    while since is not None:
        tasks, since = storage.list_since_page(since, INSTANCE, limit=2)
        seen += [t.id for t in tasks]
        pages += 1
    assert sorted(seen) == [f"s{i:03d}" for i in range(8)]
    assert len(seen) == 8  # no duplicates
    assert pages > 1


def test_client_drains_pull_pages_and_resumes_cursor(tmp_path: Path) -> None:
    def remote(i: int) -> SyncTask:
        ts = datetime.fromtimestamp(2_000_000 / 1000, tz=UTC)
        return SyncTask(id=f"r{i}", title="r", status="open", created_at=ts, updated_at=ts)

    pages = [
        SyncResponse(tasks=[remote(0), remote(1)], server_time=9, has_more=True, next_since=111),
        SyncResponse(tasks=[remote(2), remote(3)], server_time=9, has_more=True, next_since=222),
        SyncResponse(tasks=[remote(4)], server_time=9_000_000),
    ]
    client = MagicMock()
    client.sync.side_effect = pages
    store = _store([])
    store.get.return_value = None
    result = sync_with_upstream(store, client, tmp_path / ".s", INSTANCE, batch_size=2)
    assert len(result.pulled) == 5
    assert [c.kwargs["since"] for c in client.sync.call_args_list] == [0, 111, 222]
    assert all(c.kwargs["pull_limit"] == 2 for c in client.sync.call_args_list)
    assert SyncState.load(tmp_path / f".s_{INSTANCE}").last_server_time == 9_000_000


def test_pull_failure_keeps_page_cursor(tmp_path: Path) -> None:
    client = MagicMock()
    client.sync.side_effect = [
        SyncResponse(tasks=[], server_time=9, has_more=True, next_since=111),
        UpstreamError("boom"),
    ]
    result = sync_with_upstream(_store([]), client, tmp_path / ".s", INSTANCE)
    assert result.errors == ["boom"]
    assert SyncState.load(tmp_path / f".s_{INSTANCE}").last_server_time == 111


def test_old_server_without_paging_fields_still_works() -> None:
    resp = SyncResponse.model_validate({"tasks": [], "server_time": 5})
    assert resp.has_more is False and resp.next_since is None
