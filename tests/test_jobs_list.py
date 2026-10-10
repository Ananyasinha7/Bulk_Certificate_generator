from tests.factories import JOBS_URL, job_payload, read_job, seed_job, submit


def test_empty_list(client):
    body = client.get(JOBS_URL).json()
    assert body == {"items": [], "page": 1, "page_size": 20, "total": 0}


def test_jobs_created_through_the_api_are_listed_newest_first(client):
    first = submit(client, job_payload("A"))
    second = submit(client, job_payload("B", "C"))
    body = client.get(JOBS_URL).json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [str(second), str(first)]


def test_list_items_match_the_status_response(client):
    job_id = submit(client, job_payload("A", "B"))
    [item] = client.get(JOBS_URL).json()["items"]
    assert item == read_job(client, job_id)


def test_list_counts_are_per_job(client):
    done = submit(client, job_payload("A", "B"))
    waiting = seed_job(client, job_payload("C", "D", "E"))
    items = {item["id"]: item for item in client.get(JOBS_URL).json()["items"]}
    assert items[str(done)]["counts"] == {"pending": 0, "succeeded": 2, "failed": 0}
    assert items[str(waiting)]["counts"] == {"pending": 3, "succeeded": 0, "failed": 0}
    assert items[str(waiting)]["progress_percent"] == 0.0


def test_list_pagination(client):
    for index in range(3):
        submit(client, job_payload(f"Person {index}"))
    first = client.get(JOBS_URL, params={"page_size": 2}).json()
    last = client.get(JOBS_URL, params={"page": 2, "page_size": 2}).json()
    assert (len(first["items"]), len(last["items"]), first["total"]) == (2, 1, 3)


def test_list_rejects_oversized_page(client):
    assert client.get(JOBS_URL, params={"page_size": 101}).status_code == 422
