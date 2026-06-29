"""
metadata_analyzer.py — Extract and risk-score document metadata.

Reuses the existing extract_text infrastructure (pdfplumber / python-docx)
already present in api/utils.py.  Never re-reads the file from disk —
accepts a binary content buffer or an open file-like object.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetadataResult:
    author: Optional[str]           = None
    company: Optional[str]          = None
    software: Optional[str]         = None
    created_at: Optional[str]       = None
    modified_at: Optional[str]      = None
    version: Optional[str]          = None
    comments: Optional[str]         = None
    hidden_text_detected: bool      = False
    extra_properties: Dict[str, Any]= field(default_factory=dict)
    risk_flags: List[str]           = field(default_factory=list)
    metadata_risk_score: int        = 0   # 0–30 contribution to overall score


def analyze_metadata(file_content: bytes, filename: str) -> MetadataResult:
    """
    Extract metadata from PDF or DOCX binary content.

    Parameters
    ----------
    file_content : bytes
        Raw file bytes (already read from storage).
    filename : str
        Original filename — used to determine the parser.

    Returns
    -------
    MetadataResult
        Populated with all extractable metadata and a risk assessment.
    """
    name_lower = (filename or '').lower()

    if name_lower.endswith('.pdf'):
        return _analyze_pdf(file_content)
    if name_lower.endswith(('.docx', '.doc')):
        return _analyze_docx(file_content)

    # For other formats (txt, csv…) return minimal result
    return MetadataResult(risk_flags=['metadata_not_extractable'])


# ── PDF ───────────────────────────────────────────────────────────────────────

def _analyze_pdf(content: bytes) -> MetadataResult:
    result = MetadataResult()
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            meta = pdf.metadata or {}
            result.author      = _clean(meta.get('Author') or meta.get('Creator'))
            result.company     = _clean(meta.get('Company'))
            result.software    = _clean(meta.get('Producer') or meta.get('Creator'))
            result.created_at  = _clean(meta.get('CreationDate'))
            result.modified_at = _clean(meta.get('ModDate'))
            result.version     = _clean(meta.get('PDFFormatVersion') or meta.get('Version'))
            result.comments    = _clean(meta.get('Subject') or meta.get('Keywords'))
            result.extra_properties = {
                k: str(v) for k, v in meta.items()
                if k not in ('Author', 'Creator', 'Company', 'Producer',
                             'CreationDate', 'ModDate', 'PDFFormatVersion',
                             'Version', 'Subject', 'Keywords')
            }
            # Hidden layers / annotations check
            for page in pdf.pages:
                if page.annots:
                    result.hidden_text_detected = True
                    break

    except ImportError:
        logger.warning('pdfplumber not available — PDF metadata skipped')
        result.risk_flags.append('metadata_library_unavailable')
    except Exception as exc:
        logger.warning('PDF metadata extraction failed: %s', exc)
        result.risk_flags.append('metadata_extraction_failed')

    return _score_metadata(result)


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _analyze_docx(content: bytes) -> MetadataResult:
    result = MetadataResult()
    try:
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(content))
        core = doc.core_properties

        result.author      = _clean(getattr(core, 'author', None))
        result.company     = _clean(getattr(core, 'company', None))
        result.software    = _clean(getattr(core, 'creator', None))
        result.created_at  = str(getattr(core, 'created', None) or '')
        result.modified_at = str(getattr(core, 'modified', None) or '')
        result.version     = _clean(getattr(core, 'version', None))
        result.comments    = _clean(getattr(core, 'comments', None))

        # Detect tracked changes / revisions
        if hasattr(core, 'revision') and int(getattr(core, 'revision', 0) or 0) > 1:
            result.extra_properties['revision_count'] = str(core.revision)

        # Detect comments / annotations
        if doc.comments:
            result.hidden_text_detected = True

    except ImportError:
        logger.warning('python-docx not available — DOCX metadata skipped')
        result.risk_flags.append('metadata_library_unavailable')
    except Exception as exc:
        logger.warning('DOCX metadata extraction failed: %s', exc)
        result.risk_flags.append('metadata_extraction_failed')

    return _score_metadata(result)


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score_metadata(result: MetadataResult) -> MetadataResult:
    """
    Assign a metadata risk score (0–30) and populate risk_flags.
    """
    score = 0

    if result.author:
        result.risk_flags.append('author_name_present')
        score += 5

    if result.company:
        result.risk_flags.append('company_name_present')
        score += 5

    if result.software:
        result.risk_flags.append('software_signature_present')
        score += 3

    if result.hidden_text_detected:
        result.risk_flags.append('hidden_content_detected')
        score += 10

    if result.extra_properties:
        result.risk_flags.append('extra_metadata_fields_present')
        score += min(len(result.extra_properties) * 2, 7)

    result.metadata_risk_score = min(score, 30)
    return result


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None
