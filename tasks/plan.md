# Implementation Plan: Bulk Certificate Generator

## Overview

A backend API that accepts one request containing many recipients, validates each, renders a PDF certificate per valid recipient from a single fixed template, tracks per-item and per-job status, and lets the client retrieve results individually or as a ZIP. A failure on one item never blocks the others.

Task checklist lives in `tasks/todo.md`.

## Assumptions (confirm or correct)

1. FastAPI + SQLAlchemy 2.0 + Pydantic v2, Python 3.11+.
2. SQLite by default; `DATABASE_URL` setting allows Postgres unchanged.
3. Output is PDF, rendered with ReportLab (pure Python, no system libs).
4. Job-level fields: `title`, `issuer`, `issue_date`. Per-recipient: `name` (required), `email` (required, validated).
5. Invalid recipients do NOT reject the request. Request returns `202`; bad rows are stored as `FAILED` items with a reason. Only a malformed request (wrong shape, empty list, over limit) returns `422`.
6. Max 1,000 recipients per request (configurable). No auth (out of scope).
7. Files stored on local disk behind a small `Storage` interface.

## Architecture

```
Client --POST /certificate-jobs--> API (validate request shape)
                                    1. insert Job + one Certificate row per recipient
                                       (invalid rows stored as FAILED immediately)
                                    2. enqueue process_job(job_id)
<-- 202 {id, status, links} --------
                                    v
                          Background worker (threadpool)
                          for each PENDING item:
                            claim -> render PDF -> save file -> mark SUCCEEDED
                            on exception -> mark FAILED + error, continue
                          finish -> set job status
Client --GET /certificate-jobs/{id}--> counts computed from item rows
Client --GET .../certificates, /download--> list, single PDF, or ZIP
```

The database is the source of truth. The queue is only a trigger, so a crash loses no state.

## Architecture Decisions

### ADR-001: Processing model for bulk jobs

**Status:** Proposed

| Option | Complexity | Durability | Fit |
|---|---|---|---|
| A. Synchronous in request | Low | n/a | Blocks/times out at large N. Fails "bulk". |
| **B. DB-tracked items + FastAPI `BackgroundTasks`, resume on startup** | Low | Good (state in DB) | **Chosen** |
| C. Celery/RQ + Redis | High | Very good | Right for production scale; overkill here |

**Decision:** B. API persists rows and returns `202`. Worker processes only `PENDING` items, so processing is idempotent. On startup, items stuck in `PROCESSING` are reset to `PENDING` and unfinished jobs re-enqueued.

**Consequences:**
- Easy tests: Starlette `TestClient` runs background tasks before returning.
- No horizontal scaling; worker shares the API process. Upgrade path: swap `enqueue(job_id)` for Celery/RQ.
- Per-item state makes "retry failed items" a small future endpoint.

### Other decisions

- **Per-recipient validation, not whole-request rejection.** Matches the requirement that one bad item must not block the rest.
- **Counts computed live** via `GROUP BY status` rather than denormalized counters, so they cannot drift.
- **File names are certificate UUIDs**, never user input (no path traversal).
- **Commit per item** so progress is visible and a crash loses at most one item.
- **Atomic claim** with `UPDATE ... WHERE status='PENDING'`, not read-then-write.
- **Injectable renderer** (`render(cert_data) -> bytes`) so tests can force a deterministic failure.
- **Bundled Unicode TTF (DejaVu Sans)** for broader name support; unsupported glyphs fail that item with a clear error.
- **snake_case fields**, uniform error envelope, UPPER_SNAKE enums.

## API Contract (`/api/v1`)

| Endpoint | Behaviour |
|---|---|
| `POST /certificate-jobs` | `202` with `id`, `status`, `total`, `Location` header. `422` for malformed request. |
| `GET /certificate-jobs/{id}` | Status, counts `{total, pending, succeeded, failed}`, `progress_percent`, timestamps |
| `GET /certificate-jobs/{id}/certificates?status=&page=&page_size=` | Paginated items: recipient, status, `error`, `download_url` |
| `GET /certificates/{cert_id}/download` | PDF. `404` unknown, `409` not generated |
| `GET /certificate-jobs/{id}/download` | ZIP of succeeded PDFs. `409` until job finished |

**Error shape (everywhere):**
```json
{"error": {"code": "VALIDATION_ERROR", "message": "...", "details": {}}}
```

**Job status:** `PENDING | PROCESSING | COMPLETED | COMPLETED_WITH_ERRORS | FAILED`
- all items succeeded -> `COMPLETED`
- some failed -> `COMPLETED_WITH_ERRORS`
- all failed -> `FAILED`

**Item status:** `PENDING | PROCESSING | SUCCEEDED | FAILED`

**Example request:**
```json
{
  "certificate": {"title": "Python Bootcamp", "issuer": "Acme Academy", "issue_date": "2026-10-01"},
  "recipients": [
    {"name": "Asha Verma", "email": "asha@example.com"},
    {"name": "Rohan Mehta", "email": "rohan@example.com"}
  ]
}
```

**Example status response:**
```json
{"id": "...", "status": "PROCESSING", "total": 500,
 "counts": {"pending": 310, "succeeded": 185, "failed": 5}, "progress_percent": 38.0}
```

## Data Model

**CertificateJob:** `id (uuid)`, `title`, `issuer`, `issue_date`, `status`, `created_at`, `started_at`, `completed_at`

**Certificate:** `id (uuid, also certificate number)`, `job_id (FK, indexed)`, `row_index`, `recipient_name`, `recipient_email`, `status`, `error_code`, `error_message`, `file_path`, `generated_at`; `UNIQUE(job_id, row_index)`

## Project Structure

```
app/  main.py  config.py  db.py  models.py  schemas.py  errors.py
      api/{jobs.py, certificates.py}
      services/{jobs.py, processor.py, renderer.py, storage.py}
      assets/fonts/
tests/ conftest.py  test_create_job.py  test_validation.py  test_renderer.py
       test_processor.py  test_progress.py  test_retrieval.py
README.md  requirements.txt
```

## Commands

```
Run:   uvicorn app.main:app --reload
Test:  pytest -q
```

## Testing Strategy

- pytest + FastAPI `TestClient`; per-test temp SQLite DB and temp storage dir.
- Renderer: output starts with `%PDF`; `pypdf` extracts the recipient name.
- Progress: process items one at a time via the service layer (no sleeps).
- Individual failure: inject a renderer that raises for one specific name; assert others succeed.
- Required coverage: create job, input validation, certificate generation, status/progress, individual failure, retrieval.

## Boundaries

- **Always:** validate at the API boundary, run tests before finishing a task, keep error shape uniform.
- **Ask first:** adding dependencies beyond the list, schema changes after T3, changing the processing model.
- **Never:** build file paths from user input, commit secrets, skip or delete failing tests.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Names with glyphs the font cannot draw (e.g. Devanagari) | Med | Bundle DejaVu Sans; unsupported glyphs fail that item with a clear error; document the limitation |
| Background work lost on restart | Med | Startup recovery of `PENDING`/`PROCESSING` items |
| SQLite writes from worker thread | Med | One session per task, short per-item transactions, `check_same_thread=False` |
| Large ZIP memory use | Low | Write to temp file and stream |
| Oversized or abusive payloads | Med | Max recipients, max name length, request-size cap |

## Open Questions (defaults in bold)

- Is `email` mandatory? **Yes.**
- Are duplicate recipients in one request allowed? **Yes, no dedupe.**
- Output PDF only? **Yes.**
- Invalid recipient fails only that item? **Yes.**

## Optional (only after all required tasks)

- Retry-failed endpoint (reset `FAILED` -> `PENDING`, re-enqueue).
- `Idempotency-Key`: only if fully honoured (atomic claim via unique constraint, payload-hash check, `409` for in-flight duplicates). Do not accept the header without honouring it.
- QR code on the certificate.

## Interview Talking Points

- Why `202` + polling; why the DB is the source of truth.
- Crash behaviour and why `PENDING`-only processing makes recovery safe.
- Where changes go if requirements shift: Celery replaces only `enqueue`; a new format touches only the renderer; retry is a status reset plus re-enqueue.

## Addendum v2: throughput, wording, preview, jobs list

### Scope
1. Faster processing without changing the API contract.
2. Editable certificate heading, introduction and statement, with presets.
3. Preview of the first certificate (exact PDF) before generating.
4. `GET /certificate-jobs` so every job is visible in the UI, however it was created.
5. Frontend redesign around those flows.

### ADR-002: Batched, parallel rendering pipeline

**Status:** Accepted (supersedes the per-item commit rule in ADR-001)

Profiling showed rendering costs about 6 ms per PDF in ReportLab and the remaining time was two database commits per item.

**Decision:** process `PENDING` items in batches of `BATCH_SIZE` (default 50). Each batch is claimed with one atomic `UPDATE ... RETURNING`, rendered through an injectable `Executor`, stored, and committed once. Production uses a `ProcessPoolExecutor` sized by `RENDER_WORKERS` (CPU count, capped at 8); a single worker uses a thread. SQLite runs in WAL mode with `synchronous=NORMAL`. Job creation uses one bulk insert.

**Consequences:**
- Throughput scales with cores; commits drop 100x.
- A crash loses at most one batch of in-flight items; they are `PROCESSING`, so startup recovery resets them and they are re-rendered (files are overwritten, never duplicated).
- Renderers passed to a process pool must be picklable module-level functions. Tests inject closures with a thread executor.

### API additions
| Endpoint | Behaviour |
|---|---|
| `GET /certificate-jobs?page=&page_size=` | Newest first, same shape as the job status response |
| `POST /certificate-previews` | `{certificate, recipient_name}` returns an inline PDF; `422` for invalid input or unsupported glyphs |
| `POST /certificate-jobs` | `certificate` gains optional `heading`, `intro`, `statement` |

Schema change: `certificate_jobs` gains `heading`, `intro`, `statement`. Existing development databases must be deleted.

## Tasks (v2)
