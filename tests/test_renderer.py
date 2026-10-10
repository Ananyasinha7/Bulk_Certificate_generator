from datetime import date
from io import BytesIO
from uuid import uuid4

import pytest
from pypdf import PdfReader

from app.services.renderer import CertificateData, RenderError, render


def data(name="Asha Verma", **overrides):
    return CertificateData(
        certificate_id=uuid4(),
        recipient_name=name,
        title="Python Bootcamp",
        issuer="Acme Academy",
        issue_date=date(2026, 10, 1),
        **{
            "heading": "Certificate of Completion",
            "intro": "This certifies that",
            "statement": "has successfully completed",
            **overrides,
        },
    )


def text_of(pdf):
    pages = PdfReader(BytesIO(pdf)).pages
    assert len(pages) == 1
    return pages[0].extract_text()


def test_output_is_a_pdf():
    assert render(data()).startswith(b"%PDF")


def test_pdf_contains_every_field():
    certificate = data()
    text = text_of(render(certificate))
    for expected in (
        "Asha Verma",
        "Python Bootcamp",
        "Acme Academy",
        "01 October 2026",
        str(certificate.certificate_id),
    ):
        assert expected in text


def test_custom_wording_is_rendered():
    text = text_of(
        render(data(heading="Certificate of Participation", intro="Presented to", statement="for attending"))
    )
    for expected in ("Certificate of Participation", "Presented to", "for attending"):
        assert expected in text
    assert "has successfully completed" not in text


def test_long_name_still_renders_on_one_page():
    name = "W" * 100
    assert name in text_of(render(data(name)))


def test_accented_name_is_supported():
    assert "Zoë Müller" in text_of(render(data("Zoë Müller")))


def test_unsupported_glyph_raises_clear_error():
    with pytest.raises(RenderError, match=r"U\+"):
        render(data("आशा"))
