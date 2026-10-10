# Bulk Certificate Generator

Backend API that accepts one request with many recipients, renders a PDF certificate per valid recipient from a single predefined template, tracks per-item and per-job status, and serves the results individually or as a ZIP. A failure on one item never blocks the others.

Stack: Python, FastAPI, SQLAlchemy 2.0 (SQLite by default), Pydantic v2, ReportLab.

A small web UI is included as an optional extra. The API is complete without it.

## Setup

Requires Python 3.11 or later.

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead of the `source` line.

## Run

```
uvicorn app.main:create_app --factory --reload
```

The API is served at `http://localhost:8000/api/v1`, interactive API docs at `http://localhost:8000/docs`, and the web UI at `http://localhost:8000/`.

Configuration is read from environment variables or a `.env` file in the project root:

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./certificates.db` | Any SQLAlchemy URL |
| `STORAGE_DIR` | `./storage` | Where generated PDFs are written |
| `MAX_RECIPIENTS` | `10000` | Maximum recipients per request |
| `RENDER_WORKERS` | CPU count, capped at 8 | Rendering processes. `1` renders in a thread instead |
| `BATCH_SIZE` | `50` | Items claimed, rendered and committed together |

Example `.env`:

```
MAX_RECIPIENTS=500
RENDER_WORKERS=4
```

The database tables are created on startup. There are no migrations, so delete `certificates.db` after changing the schema during development.

Optional speed-up: `pip install rl_accel` adds C accelerators to ReportLab and cuts render time by roughly a quarter. It is not in `requirements.txt` because it may need a compiler on some platforms.

## Test

```
pytest -q
```

Tests use a temporary SQLite database and storage directory per test, so they never touch real data. The optional UI has a small set of CSV parsing tests that need Node 20 or later and no dependencies:

```
npm test
```

## Submit a certificate generation request

The examples use `curl` with bash line continuations. In PowerShell, `curl` is an alias for another command, so use Git Bash or WSL, or call `curl.exe`.

```
curl -i -X POST http://localhost:8000/api/v1/certificate-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "certificate": {"title": "Python Bootcamp", "issuer": "Acme Academy", "issue_date": "2026-10-01"},
    "recipients": [
      {"name": "Asha Verma", "email": "asha@example.com"},
      {"name": "Rohan Mehta", "email": "rohan@example.com"}
    ]
  }'
```

The response is `202 Accepted` with the job `id`, its `status`, the `total` number of recipients, and a `Location` header pointing at the job.

`certificate.title` is the event or course name. `heading`, `intro` and `statement` are optional and default to "Certificate of Completion", "This certifies that" and "has successfully completed". The layout itself is always the same.

Invalid recipients (blank or over-long name, malformed email) do not reject the request. They are stored as `FAILED` items with an `error_code` and message. Only a malformed request (wrong shape, empty list, more than `MAX_RECIPIENTS`) returns `422`.

### Check progress

```
curl http://localhost:8000/api/v1/certificate-jobs/<job_id>
```

Returns the job status, `total`, `counts` (`pending`, `succeeded`, `failed`), `progress_percent` and timestamps. Example:

```
{"id": "...", "status": "PROCESSING", "total": 500,
 "counts": {"pending": 310, "succeeded": 185, "failed": 5}, "progress_percent": 38.0}
```

List the individual certificates, with the reason for any failure (filter with `status`, paginate with `page` and `page_size`):

```
curl "http://localhost:8000/api/v1/certificate-jobs/<job_id>/certificates?status=FAILED"
```

Statuses:

- Job: `PENDING`, `PROCESSING`, `COMPLETED`, `COMPLETED_WITH_ERRORS`, `FAILED`
- Certificate: `PENDING`, `PROCESSING`, `SUCCEEDED`, `FAILED`

A job is `COMPLETED` when every item succeeded, `FAILED` when every item failed, and `COMPLETED_WITH_ERRORS` otherwise.

## Retrieve generated certificates

```
curl -O -J http://localhost:8000/api/v1/certificates/<certificate_id>/download
curl -O -J http://localhost:8000/api/v1/certificate-jobs/<job_id>/download
```

The first returns one PDF: `404` if the certificate is unknown, `409` if it was not generated. The second returns a ZIP of the succeeded PDFs only, and `409` until the job has finished. Each item in the certificate list includes a `download_url` when it succeeded.

## Other endpoints

```
curl "http://localhost:8000/api/v1/certificate-jobs?page=1&page_size=20"
curl http://localhost:8000/api/v1/limits
curl -X POST http://localhost:8000/api/v1/certificate-previews \
  -H "Content-Type: application/json" \
  -d '{"certificate": {"title": "Python Bootcamp", "issuer": "Acme Academy", "issue_date": "2026-10-01"}, "recipient_name": "Asha Verma"}' \
  -o preview.pdf
```

These list jobs newest first, report the configured recipient limit, and render a sample PDF without creating a job.

Every error uses one envelope:

```
{"error": {"code": "VALIDATION_ERROR", "message": "...", "details": {}}}
```

## Bulk test

With the server running, in another terminal:

```
python scripts/bulk_test.py http://127.0.0.1:8000 1000
```

It submits one job with every 50th row invalid on purpose, polls until it finishes, checks that the ZIP contains exactly the succeeded PDFs, and prints a link to open the job in the UI. The size is limited by `MAX_RECIPIENTS`.

## Web UI (optional)

The frontend is plain HTML, CSS and ES modules in `app/static`, served by the same FastAPI process with no build step. It can be removed by deleting that folder and the `app.mount` line in `app/main.py`.

- **New job:** set the event name, issuer, date and wording (four style presets, or edit the lines freely), then paste rows or upload a CSV. Problem rows are flagged before submitting, and the recipient limit is shown.
- **Preview:** renders the exact PDF for the first valid row before generating.
- **Jobs and job view:** every job newest first, live progress, filters, per-certificate download, a ZIP of everything generated, and an export of failed rows as CSV.

## Project layout

```
app/
  main.py            app factory, lifespan, static mount
  config.py          settings
  db.py              engine, SQLite WAL, UTC datetime type
  models.py          CertificateJob, Certificate
  schemas.py         request and response models
  errors.py          uniform error envelope
  deps.py            request-scoped dependencies
  api/               jobs, certificates, previews, limits routers
  services/
    jobs.py          creation, validation, queries, counts
    processor.py     batched processing, recovery
    renderer.py      ReportLab PDF rendering
    storage.py       file storage and ZIP building
  static/            optional web UI
tests/               pytest suite
scripts/bulk_test.py load test against a running server
```

## Design decisions

- **One template, parameterised.** A single fixed layout is rendered with ReportLab. The job supplies the event name, issuer and date; the heading, introduction and statement lines are optional and default to the standard wording, so the layout never changes.
- **Per-recipient validation.** Invalid recipients do not reject the request. They are stored as `FAILED` items with an error code, so one bad row never blocks the rest. Only a malformed request returns `422`.
- **`202` plus polling.** The request returns immediately, generation runs in the background, and the client polls the job. The reasoning and alternatives are in ADR-001.
- **The database is the source of truth.** Job and per-certificate status live in the database. Counts are computed from rows, so they cannot drift, and a restart resumes unfinished work.
- **Safe file names.** Files are stored as `{job_id}/{certificate_id}.pdf`, never from user input.
- **Injectable renderer and executor.** Tests replace the renderer to force a specific failure deterministically, and use a thread executor instead of processes.
- **Uniform error envelope** on every error path, and 500 responses never leak internals.
- **Relational database via SQLAlchemy.** SQLite by default; `DATABASE_URL` points it at another database (not tested against PostgreSQL here).

## ADR-001: Processing model

**Status:** Accepted

| Option | Complexity | Durability | Fit |
|---|---|---|---|
| A. Synchronous in the request | Low | n/a | Times out at large batches |
| B. Database-tracked items with FastAPI `BackgroundTasks` and startup recovery | Low | Good | Chosen |
| C. Celery or RQ with Redis | High | Very good | Right for production scale, heavy here |

**Decision:** B. The API persists one row per recipient and returns `202`. The worker processes only `PENDING` items, claiming work with an atomic `UPDATE ... WHERE status = 'PENDING'`; see ADR-002 for how items are batched and committed. The database is the source of truth and the background task is only a trigger. On startup, items stuck in `PROCESSING` are reset to `PENDING` and unfinished jobs are re-enqueued.

**Consequences:**

- A crash loses at most one in-flight batch, and recovery is safe because only `PENDING` work is processed.
- Progress counts are computed from item rows, so they cannot drift.
- The worker shares the API process and does not scale horizontally.
- Upgrade path: replace the `processor` callable with a Celery or RQ enqueue; the processing functions are unchanged.
- A retry endpoint would be a status reset from `FAILED` to `PENDING` plus a re-enqueue.

## ADR-002: Batched, parallel rendering

**Status:** Accepted

Profiling showed that rendering costs a few milliseconds per PDF, and most of the remaining time was two database commits per item. Items are now processed in batches: one atomic `UPDATE ... RETURNING` claims a batch, an executor renders it, files are stored, and a single commit records it. Production uses a spawn-based `ProcessPoolExecutor` so rendering scales across cores, SQLite runs in WAL mode, and job creation is one bulk insert.

- A crash loses at most one in-flight batch, which recovery resets and re-renders. Files are overwritten, never duplicated.
- Renderers passed to a process pool must be picklable. Tests inject a thread executor so they can use closures.
- `RENDER_WORKERS=1` renders in a single thread, which is the safe fallback if worker processes cause trouble on a given platform.

## Limitations

- Certificates use the bundled DejaVu Sans font. Scripts it cannot draw (for example Devanagari) fail that item with `UNSUPPORTED_TEXT` and a clear message.
- No authentication or per-client scoping; both are out of scope.
- No migrations; the schema is created on startup.
- Inline PDF preview in the web UI needs a browser with a built-in PDF viewer. Where there is none, use the "Open PDF in new tab" link in the preview dialog.