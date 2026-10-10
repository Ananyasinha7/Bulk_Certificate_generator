import io
import zipfile

from tests.factories import CERTIFICATES_URL, JOBS_URL, job_payload, seed_job, submit

UNKNOWN = "00000000-0000-0000-0000-000000000000"


def test_list_exposes_download_url_only_for_succeeded(client):
    recipients = [
        {"name": "Asha Verma", "email": "asha@example.com"},
        {"name": "", "email": "nobody@example.com"},
    ]
    job_id = submit(client, job_payload(recipients=recipients))
    first, second = client.get(f"{JOBS_URL}/{job_id}/certificates").json()["items"]
    assert first["status"] == "SUCCEEDED"
    assert first["download_url"].endswith(f"{CERTIFICATES_URL}/{first['id']}/download")
    assert second["status"] == "FAILED"
    assert second["download_url"] is None
    assert second["error"]["code"] == "INVALID_NAME"


def test_list_pagination_and_filter(client):
    names = [f"Person {index}" for index in range(5)]
    job_id = submit(client, job_payload(*names))
    url = f"{JOBS_URL}/{job_id}/certificates"
    first = client.get(url, params={"page_size": 2}).json()
    last = client.get(url, params={"page": 3, "page_size": 2}).json()
    assert first["total"] == 5
    assert [item["row_index"] for item in first["items"]] == [0, 1]
    assert [item["row_index"] for item in last["items"]] == [4]
    assert client.get(url, params={"status": "FAILED"}).json()["total"] == 0


def test_list_rejects_oversized_page(client):
    job_id = submit(client, job_payload())
    response = client.get(f"{JOBS_URL}/{job_id}/certificates", params={"page_size": 101})
    assert response.status_code == 422


def test_list_for_unknown_job_is_not_found(client):
    assert client.get(f"{JOBS_URL}/{UNKNOWN}/certificates").status_code == 404


def test_download_single_pdf(client):
    job_id = submit(client, job_payload("Asha"))
    item = client.get(f"{JOBS_URL}/{job_id}/certificates").json()["items"][0]
    response = client.get(item["download_url"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_download_unknown_certificate_is_not_found(client):
    assert client.get(f"{CERTIFICATES_URL}/{UNKNOWN}/download").status_code == 404


def test_download_failed_certificate_conflicts(client):
    recipients = [{"name": "", "email": "nobody@example.com"}]
    job_id = submit(client, job_payload(recipients=recipients))
    item = client.get(f"{JOBS_URL}/{job_id}/certificates").json()["items"][0]
    response = client.get(f"{CERTIFICATES_URL}/{item['id']}/download")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NOT_GENERATED"


def test_zip_contains_only_succeeded_pdfs(client):
    recipients = [
        {"name": "Asha Verma", "email": "asha@example.com"},
        {"name": "", "email": "nobody@example.com"},
        {"name": "Rohan Mehta", "email": "rohan@example.com"},
    ]
    job_id = submit(client, job_payload(recipients=recipients))
    response = client.get(f"{JOBS_URL}/{job_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert len(names) == 2
        assert all(archive.read(name).startswith(b"%PDF") for name in names)


def test_zip_conflicts_until_job_finished(client):
    job_id = seed_job(client, job_payload())
    response = client.get(f"{JOBS_URL}/{job_id}/download")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "JOB_NOT_FINISHED"


def test_zip_of_unknown_job_is_not_found(client):
    assert client.get(f"{JOBS_URL}/{UNKNOWN}/download").status_code == 404
