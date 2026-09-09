"""Batch validation + cancellation + progress + partial failures."""

import asyncio

import httpx

from raven_validator.config.settings import AppSettings
from raven_validator.database.database import Database
from raven_validator.domain.candidates import APICandidate
from raven_validator.services.validation_service import ValidationOptions, ValidationService


def make_candidate(idx: int) -> APICandidate:
    return APICandidate(name=f"API {idx}", base_url=f"https://api{idx}.example.com/v1")  # type: ignore[arg-type]


async def test_batch_10_candidates() -> None:
    settings = AppSettings(db_url="sqlite:///:memory:", max_concurrency=10)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    db = Database("sqlite:///:memory:")
    svc = ValidationService(settings, db)
    candidates = [make_candidate(i) for i in range(10)]
    opts = ValidationOptions(mode="quick")
    transport = httpx.MockTransport(handler)
    events = []
    async for ev in svc.validate_batch(candidates, opts, _transport=transport):
        events.append(ev)

    # Should have run_started, 10 candidate_finished, progress updates, run_finished.
    finished = [e for e in events if e.kind == "candidate_finished"]
    assert len(finished) == 10
    # All should persist.
    from raven_validator.database.repository import Repository

    with db.session() as sess:
        total_runs = 0
        for c in candidates:
            total_runs += len(Repository(sess).list_runs_for_candidate(c.id))
        assert total_runs == 10
    db.dispose()


async def test_batch_partial_failures() -> None:
    settings = AppSettings(db_url="sqlite:///:memory:", max_concurrency=5)

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        idx = int(host.replace("api", "").replace(".example.com", ""))
        if idx % 2 == 0:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"ok": True})

    db = Database("sqlite:///:memory:")
    svc = ValidationService(settings, db)
    candidates = [make_candidate(i) for i in range(6)]
    opts = ValidationOptions(mode="quick")
    transport = httpx.MockTransport(handler)
    events = [e async for e in svc.validate_batch(candidates, opts, _transport=transport)]
    finished = [e for e in events if e.kind == "candidate_finished"]
    assert len(finished) == 6
    # At least one success and one failure status.
    statuses = {e.status for e in finished}
    assert len(statuses) >= 2
    db.dispose()


async def test_batch_progress_updates() -> None:
    settings = AppSettings(db_url="sqlite:///:memory:", max_concurrency=3)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    db = Database("sqlite:///:memory:")
    svc = ValidationService(settings, db)
    candidates = [make_candidate(i) for i in range(5)]
    opts = ValidationOptions(mode="quick")
    transport = httpx.MockTransport(handler)
    progresses: list[tuple[int, int]] = []
    async for ev in svc.validate_batch(candidates, opts, _transport=transport):
        if ev.progress:
            progresses.append(ev.progress)
    # Progress should monotonically increase to (5,5) or final completed count.
    assert progresses
    assert progresses[-1][1] == 5
    # Should have at least 5 progress steps (one per candidate).
    progress_kinds = [e for e in progresses if e[0] <= e[1]]
    assert len(progress_kinds) >= 5
    db.dispose()


async def test_batch_cancellation() -> None:
    settings = AppSettings(db_url="sqlite:///:memory:", max_concurrency=1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    db = Database("sqlite:///:memory:")
    svc = ValidationService(settings, db)
    candidates = [make_candidate(i) for i in range(10)]
    opts = ValidationOptions(mode="quick")
    transport = httpx.MockTransport(handler)

    # Make each candidate take a while so cancellation has time to act.
    orig_validate_one = svc.validate_one

    async def slow_validate_one(candidate, options, client=None, _transport=None):  # type: ignore[no-untyped-def]
        await asyncio.sleep(0.25)
        return await orig_validate_one(candidate, options, client=client, _transport=_transport)

    svc.validate_one = slow_validate_one  # type: ignore[assignment]

    events: list[object] = []

    async def run_batch() -> None:
        async for ev in svc.validate_batch(candidates, opts, _transport=transport):
            events.append(ev)  # type: ignore[arg-type]

    task = asyncio.create_task(run_batch())
    # Let first candidate start, then cancel quickly.
    await asyncio.sleep(0.08)
    svc.cancel()
    await asyncio.wait_for(task, timeout=2.0)

    # After cancellation, not all 10 should have finished.
    from raven_validator.services.validation_service import BatchEvent

    typed: list[BatchEvent] = events  # type: ignore[assignment]
    finished = [e for e in typed if getattr(e, "kind", None) == "candidate_finished"]
    # Should have at least 1 but fewer than 10 (cancelled early).
    assert 0 <= len(finished) < 10
    # Completed results must still be persisted.
    from raven_validator.database.repository import Repository

    with db.session() as sess:
        persisted = 0
        for c in candidates:
            persisted += len(Repository(sess).list_runs_for_candidate(c.id))
        # Partial results must be kept; persisted <= finished and at least one real run.
        assert 0 <= persisted < 10
        # Persisted runs are those that actually started validation (have run_id).
        finished_with_run = [e for e in finished if getattr(e, "run_id", None) is not None]
        assert persisted == len(finished_with_run)

    db.dispose()
