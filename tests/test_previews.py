from io import BytesIO

from pypdf import PdfReader

from tests.factories import job_payload

URL = "/api/v1/certificate-previews"


def body(name="Asha Verma", **certificate):
    spec = {**job_payload()["certificate"], **certificate}
    return {"certificate": spec, "recipient_name": name}


def text_of(content):
    return PdfReader(BytesIO(content)).pages[0].extract_text()


def test_preview_returns_an_inline_pdf(client):
    response = client.post(URL, json=body())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.content.startswith(b"%PDF")


def test_preview_reflects_wording_and_name(client):
    payload = body("Zoë Müller", heading="Certificate of Merit", statement="for excelling in")
    response = client.post(URL, json=payload)
    text = text_of(response.content)
    for expected in ("Zoë Müller", "Certificate of Merit", "for excelling in", "Python Bootcamp"):
        assert expected in text


def test_preview_does_not_create_a_job(client):
    client.post(URL, json=body())
    assert client.get("/api/v1/certificate-jobs").json()["total"] == 0


def test_preview_rejects_invalid_input(client):
    assert client.post(URL, json=body(name="  ")).status_code == 422
    assert client.post(URL, json={"recipient_name": "Asha"}).status_code == 422


def test_preview_reports_unsupported_text(client):
    response = client.post(URL, json=body("आशा"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_TEXT"
