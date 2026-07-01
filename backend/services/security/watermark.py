"""
services/security/watermark.py — Document watermark service.

Public API
----------
  add_watermark(plaintext_bytes, filename, watermark_info) → bytes
  WatermarkInfo                                            ← dataclass

Supported formats
-----------------
  PDF   — diagonal semi-transparent text overlay on every page
           using reportlab (stamp generation) + pypdf (merge)
  DOCX  — paragraph prepended at the top of the document body

Watermark content
-----------------
  Downloaded by: <username>
  Date:          <YYYY-MM-DD>
  Time:          <HH:MM UTC>
  Classification: <level>

Design
------
- Pure in-memory: no temp files on disk.
- Graceful degradation: if watermarking fails for any reason, the original
  bytes are returned unchanged and the error is logged. A failed watermark
  must NEVER block a legitimate download.
- No Django imports at module level — safe to use in any context.

Extensibility
-------------
  Phase 8 — AuditService can log watermark application events.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ── Watermark data ────────────────────────────────────────────────────────────

@dataclass
class WatermarkInfo:
    """Metadata embedded in the watermark stamp."""
    username:        str
    downloaded_at:   Optional[datetime]  = None     # defaults to now (UTC)
    classification:  str                 = 'INTERNAL'

    def __post_init__(self):
        if self.downloaded_at is None:
            self.downloaded_at = datetime.now(tz=timezone.utc)

    @property
    def date_str(self) -> str:
        return self.downloaded_at.strftime('%Y-%m-%d')

    @property
    def time_str(self) -> str:
        return self.downloaded_at.strftime('%H:%M UTC')

    @property
    def lines(self) -> list[str]:
        return [
            f'Downloaded by: {self.username}',
            f'Date: {self.date_str}',
            f'Time: {self.time_str}',
            f'Classification: {self.classification}',
        ]

    @property
    def single_line(self) -> str:
        return (
            f'{self.username} | {self.date_str} {self.time_str} | {self.classification}'
        )


# ── Main entry point ──────────────────────────────────────────────────────────

def add_watermark(
    plaintext_bytes: bytes,
    filename:        str,
    info:            WatermarkInfo,
) -> bytes:
    """
    Apply a watermark to document bytes.

    Parameters
    ----------
    plaintext_bytes : bytes — original document content (never ciphertext)
    filename        : str   — used to detect file type (.pdf / .docx)
    info            : WatermarkInfo — user/date/classification data

    Returns
    -------
    bytes — watermarked document, or original bytes if watermarking failed.
    """
    lower = (filename or '').lower()

    try:
        if lower.endswith('.pdf'):
            return _watermark_pdf(plaintext_bytes, info)
        if lower.endswith('.docx'):
            return _watermark_docx(plaintext_bytes, info)
    except Exception as exc:
        logger.error(
            'watermark: failed for "%s" — %s. Returning original bytes.',
            filename, exc,
        )

    # Graceful degradation: return original if watermarking is not supported
    # or failed unexpectedly.
    return plaintext_bytes


# ── PDF watermark ─────────────────────────────────────────────────────────────

def _build_pdf_stamp(page_width: float, page_height: float, info: WatermarkInfo) -> bytes:
    """
    Build a single-page PDF containing a diagonal semi-transparent watermark.

    Uses reportlab to draw rotated grey text centered on the page.
    The stamp is later merged over every page of the original PDF by pypdf.
    """
    from reportlab.lib.colors  import Color
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen      import canvas as rl_canvas

    buf = io.BytesIO()

    # Use provided page dimensions so the stamp aligns correctly
    c = rl_canvas.Canvas(buf, pagesize=(page_width, page_height))

    # Semi-transparent grey (alpha supported by reportlab 4+)
    watermark_color = Color(0.5, 0.5, 0.5, alpha=0.25)
    c.setFillColor(watermark_color)

    # Diagonal stamp — rotate 45° around page centre
    c.saveState()
    c.translate(page_width / 2, page_height / 2)
    c.rotate(45)

    font_size = min(page_width, page_height) / 20
    c.setFont('Helvetica', font_size)

    lines = info.lines
    line_height = font_size * 1.4
    total_height = line_height * len(lines)
    start_y = total_height / 2

    for i, line in enumerate(lines):
        c.drawCentredString(0, start_y - i * line_height, line)

    c.restoreState()
    c.save()

    buf.seek(0)
    return buf.read()


def _watermark_pdf(pdf_bytes: bytes, info: WatermarkInfo) -> bytes:
    """
    Merge a diagonal watermark stamp over every page of a PDF.

    Strategy
    --------
    1. Read the original PDF with pypdf.
    2. For each page, generate a stamp PDF (same dimensions) using reportlab.
    3. Merge stamp over the original page content.
    4. Write the result to a BytesIO buffer and return.
    """
    import pypdf

    original  = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    writer    = pypdf.PdfWriter()

    for page in original.pages:
        # Page dimensions in PDF user units (1 pt = 1/72 inch)
        width  = float(page.mediabox.width)
        height = float(page.mediabox.height)

        stamp_bytes = _build_pdf_stamp(width, height, info)
        stamp_page  = pypdf.PdfReader(io.BytesIO(stamp_bytes)).pages[0]

        # Merge: stamp drawn OVER original content (visible on top)
        page.merge_page(stamp_page)
        writer.add_page(page)

    # Preserve metadata
    if original.metadata:
        writer.add_metadata(dict(original.metadata))

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


# ── DOCX watermark ────────────────────────────────────────────────────────────

def _watermark_docx(docx_bytes: bytes, info: WatermarkInfo) -> bytes:
    """
    Prepend a watermark paragraph at the top of a DOCX document.

    The watermark is inserted as the first paragraph with grey italic text,
    clearly marking the document as a controlled download copy.
    """
    from docx              import Document as DocxDocument
    from docx.shared       import Pt, RGBColor
    from docx.oxml.ns      import qn
    from docx.oxml         import OxmlElement

    doc = DocxDocument(io.BytesIO(docx_bytes))

    # Build the watermark text
    wm_text = ' | '.join(info.lines)

    # Insert a new paragraph at position 0 (before any existing content)
    # We use the underlying XML to prepend rather than append.
    body = doc.element.body
    new_para = OxmlElement('w:p')

    run_el = OxmlElement('w:r')

    # Run properties: grey italic small font
    rPr = OxmlElement('w:rPr')

    color_el = OxmlElement('w:color')
    color_el.set(qn('w:val'), '808080')   # grey
    rPr.append(color_el)

    italic_el = OxmlElement('w:i')
    rPr.append(italic_el)

    sz_el = OxmlElement('w:sz')
    sz_el.set(qn('w:val'), '16')          # 8pt (half-points)
    rPr.append(sz_el)

    run_el.append(rPr)

    text_el = OxmlElement('w:t')
    text_el.text = wm_text
    run_el.append(text_el)

    new_para.append(run_el)

    # Insert before the first child of body (i.e., at the very top)
    first_child = body[0] if len(body) > 0 else None
    if first_child is not None:
        body.insert(0, new_para)
    else:
        body.append(new_para)

    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out.read()
