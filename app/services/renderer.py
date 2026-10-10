import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from uuid import UUID

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

logger = logging.getLogger(__name__)

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
REGULAR = "DejaVuSans"
BOLD = "DejaVuSans-Bold"
PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)
MAX_TEXT_WIDTH = PAGE_WIDTH - 140


class RenderError(Exception):
    pass


@dataclass(frozen=True)
class CertificateData:
    certificate_id: UUID
    recipient_name: str
    title: str
    issuer: str
    issue_date: date
    heading: str
    intro: str
    statement: str


@dataclass(frozen=True)
class RenderOutcome:
    pdf: bytes | None = None
    code: str | None = None
    message: str | None = None


Renderer = Callable[[CertificateData], bytes]


@lru_cache(maxsize=1)
def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(REGULAR, str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(FONT_DIR / "DejaVuSans-Bold.ttf")))


def draw_line(canvas: Canvas, text: str, y: float, font: str, size: float) -> None:
    glyphs = pdfmetrics.getFont(font).face.charToGlyph
    for char in text:
        if ord(char) not in glyphs:
            raise RenderError(f"Unsupported character U+{ord(char):04X}")
    width = pdfmetrics.stringWidth(text, font, size)
    if width > MAX_TEXT_WIDTH:
        size = size * MAX_TEXT_WIDTH / width
    canvas.setFont(font, size)
    canvas.drawCentredString(PAGE_WIDTH / 2, y, text)


def render(data: CertificateData) -> bytes:
    register_fonts()
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), pageCompression=0)
    canvas.setLineWidth(3)
    canvas.rect(30, 30, PAGE_WIDTH - 60, PAGE_HEIGHT - 60)
    canvas.setLineWidth(1)
    canvas.rect(40, 40, PAGE_WIDTH - 80, PAGE_HEIGHT - 80)
    draw_line(canvas, data.heading, 470, BOLD, 34)
    draw_line(canvas, data.intro, 410, REGULAR, 16)
    draw_line(canvas, data.recipient_name, 345, BOLD, 40)
    draw_line(canvas, data.statement, 285, REGULAR, 16)
    draw_line(canvas, data.title, 235, BOLD, 26)
    draw_line(canvas, f"Issued by {data.issuer}", 140, REGULAR, 16)
    draw_line(canvas, data.issue_date.strftime("%d %B %Y"), 112, REGULAR, 14)
    draw_line(canvas, f"Certificate ID: {data.certificate_id}", 65, REGULAR, 9)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def attempt(renderer: Renderer, data: CertificateData) -> RenderOutcome:
    try:
        return RenderOutcome(pdf=renderer(data))
    except RenderError as exc:
        return RenderOutcome(code="UNSUPPORTED_TEXT", message=str(exc))
    except Exception:
        logger.exception("Certificate rendering failed")
        return RenderOutcome(code="RENDER_ERROR", message="Certificate could not be generated")
