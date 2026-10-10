# Task List: Bulk Certificate Generator

See `tasks/plan.md` for design, API contract, and decisions.

## Phase 1: Foundation

- [x] **T1 (S): Project skeleton, config, DB models, test harness**
  - Acceptance:
    - App boots; `config.py` reads `DATABASE_URL`, storage dir, max recipients from env
    - `CertificateJob` and `Certificate` models exist with `UNIQUE(job_id, row_index)`
    - `conftest.py` provides temp DB, temp storage, and `TestClient` fixtures
  - Verify: `pytest -q` passes with one trivial DB round-trip test
  - Files: `app/main.py`, `app/config.py`, `app/db.py`, `app/models.py`, `tests/conftest.py`
  - Depends on: none

- [x] **T2 (S): ReportLab certificate renderer** *(parallel with T1)*
  - Acceptance:
    - `render(cert_data) -> bytes` returns a single-page PDF with border, title, recipient name (auto-shrunk to fit), course, issuer, date, certificate ID
    - Bundled Unicode TTF used; unsupported glyphs raise a clear error
  - Verify: `pytest tests/test_renderer.py`: output starts with `%PDF`; `pypdf` extracts the name; a long name does not overflow; an unsupported glyph raises
  - Files: `app/services/renderer.py`, `app/assets/fonts/`, `tests/test_renderer.py`
  - Depends on: none

## Phase 2: Core flow

- [x] **T3 (M): `POST /certificate-jobs` with per-recipient validation**
  - Acceptance:
    - Valid request returns `202` with `id`, `status`, `total`, `Location`
    - Invalid recipients (blank name, bad email, over-long name) stored as `FAILED` with `error_code` and `error_message`; valid ones stored as `PENDING`
    - Empty list, missing fields, or more than max recipients return `422` in the uniform error envelope
  - Verify: `pytest tests/test_create_job.py tests/test_validation.py`
  - Files: `app/schemas.py`, `app/errors.py`, `app/api/jobs.py`, `app/services/jobs.py`, tests
  - Depends on: T1

- [x] **T4 (M): Processor, background wiring, startup recovery**
  - Acceptance:
    - `process_job` handles only `PENDING` items; atomic claim; commit per item
    - One item raising does not stop the others; failure recorded on that item
    - Job moves `PENDING -> PROCESSING -> COMPLETED | COMPLETED_WITH_ERRORS | FAILED`
    - Files saved as `{job_id}/{certificate_id}.pdf` via `Storage`
    - On startup, `PROCESSING` items reset to `PENDING` and unfinished jobs re-enqueued
  - Verify: `pytest tests/test_processor.py` covering all-success, one injected failure, all-failed, and crash recovery
  - Files: `app/services/processor.py`, `app/services/storage.py`, `app/main.py`, tests
  - Depends on: T1, T2, T3

### Checkpoint A: Core flow
- [x] All tests pass
- [x] A batch of 3 with 1 bad row produces exactly 2 PDFs on disk
- [x] Review with human before proceeding

## Phase 3: Observability and retrieval

- [x] **T5 (S): Job status and certificates list**
  - Acceptance:
    - `GET /certificate-jobs/{id}` returns status, counts, `progress_percent`, timestamps
    - `GET /certificate-jobs/{id}/certificates` paginated, filterable by `status`, includes `error` and `download_url`
    - Unknown job returns `404`
  - Verify: `pytest tests/test_progress.py`: progress checked at 0%, mid-way, and 100% by processing items one at a time via the service layer
  - Files: `app/api/jobs.py`, `app/schemas.py`, `app/services/jobs.py`, tests
  - Depends on: T4

- [x] **T6 (M): Certificate retrieval (single PDF and ZIP)**
  - Acceptance:
    - `GET /certificates/{id}/download` returns the PDF with `application/pdf`; `404` unknown; `409` if not generated
    - `GET /certificate-jobs/{id}/download` returns a ZIP of succeeded PDFs only; `409` until the job is finished
    - ZIP is written to a temp file and streamed
  - Verify: `pytest tests/test_retrieval.py`
  - Files: `app/api/certificates.py`, `app/api/jobs.py`, `app/services/storage.py`, tests
  - Depends on: T4

### Checkpoint B: End-to-end
- [x] All tests pass
- [x] Submit -> poll -> list -> download works end-to-end via `TestClient`
- [x] Review with human before proceeding

## Phase 4: Finish

- [x] **T7 (S): Error handling and edge cases**
  - Acceptance:
    - Every error path (validation, bad UUID, 404, 409, unexpected 500) returns the uniform envelope
    - 500s never leak internal details
  - Verify: `pytest -q` including a parametrized test over error paths
  - Files: `app/errors.py`, `app/main.py`, tests
  - Depends on: T3, T5, T6

- [x] **T8 (S): README**
  - Acceptance:
    - Covers setup, run, test, a `curl` submit example, a status check, retrieval, and the ADR with trade-offs and upgrade path
    - A fresh clone can follow it start to finish
  - Verify: follow the README from a clean virtualenv
  - Files: `README.md`, `requirements.txt`
  - Depends on: T1-T7

### Checkpoint: Complete
- [x] All required behaviours from the brief covered by tests
- [x] README verified from a clean environment
- [x] Ready for review

## Optional (only after all required tasks)

- [ ] Retry-failed endpoint
- [ ] `Idempotency-Key` (only if fully honoured)
- [ ] QR code on certificate

## Phase 5: v2 (see Addendum v2 in plan.md)

- [x] **T9 (M): Batched parallel processing** — batched claim and commit, executor, WAL, bulk insert
- [x] **T10 (S): Editable wording** — `heading`, `intro`, `statement` on job, schema, renderer
- [x] **T11 (S): Certificate preview endpoint**
- [x] **T12 (S): Jobs list endpoint**
- [x] **T13 (M): Frontend redesign** — wording presets, preview dialog, jobs page, sticky action bar
- [x] **T14 (S): Tests, README, bulk test script**
