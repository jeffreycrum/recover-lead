import io
import uuid

import structlog
from reportlab.lib.pagesizes import letter as LETTER_SIZE
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

logger = structlog.get_logger()


def generate_pdf(content: str, case_number: str = "") -> bytes:
    """Generate a print-ready PDF from letter content."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER_SIZE,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "LetterBody",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        spaceAfter=12,
    )

    story = []

    # Split content into paragraphs and render
    for paragraph in content.split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            # Escape HTML-sensitive characters for ReportLab
            paragraph = paragraph.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            paragraph = paragraph.replace("\n", "<br/>")
            story.append(Paragraph(paragraph, body_style))
            story.append(Spacer(1, 6))

    doc.build(story)
    return buffer.getvalue()
