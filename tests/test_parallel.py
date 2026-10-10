from app.services.processor import create_executor
from tests.factories import job_payload, read_job, submit


def test_process_pool_renders_a_whole_job(make_client, settings):
    with create_executor(2) as executor:
        client = make_client(executor=executor)
        names = [f"Person {index}" for index in range(5)]
        job = read_job(client, submit(client, job_payload(*names)))
    assert job["status"] == "COMPLETED"
    assert job["counts"]["succeeded"] == 5
    assert len(list(settings.storage_dir.rglob("*.pdf"))) == 5
