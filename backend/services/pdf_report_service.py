"""
PDF Report Service — generates compliance PDF reports for documents.
Uses ReportLab if available, otherwise returns plain text.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


def generate_document_report(doc_data: Dict[str, Any]) -> bytes:
    """
    Generate a PDF compliance report for a document.
    Returns PDF bytes. Raises RuntimeError if generation fails.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Heading1'],
                                     fontSize=18, spaceAfter=12)
        h2_style    = ParagraphStyle('H2', parent=styles['Heading2'],
                                     fontSize=13, spaceBefore=12, spaceAfter=6)
        body_style  = styles['Normal']

        story = []

        # ── Header ──────────────────────────────────────────────────────────
        story.append(Paragraph('Compliance Report', title_style))
        story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#0ea5e9')))
        story.append(Spacer(1, 0.4*cm))

        # ── Document info ────────────────────────────────────────────────────
        story.append(Paragraph('Document Information', h2_style))
        info_data = [
            ['Field', 'Value'],
            ['Document ID',  str(doc_data.get('id', '—'))],
            ['Standard',     str(doc_data.get('norme_name', doc_data.get('standard', '—')))],
            ['Employee',     str(doc_data.get('employee_username', '—'))],
            ['Department',   str(doc_data.get('employee_department', '—'))],
            ['Status',       str(doc_data.get('status', '—')).upper()],
            ['Final Decision', str(doc_data.get('final_decision', '—')).upper()],
            ['Reviewed by',  str(doc_data.get('approved_by', '—'))],
            ['Generated',    datetime.now().strftime('%Y-%m-%d %H:%M')],
        ]
        table = Table(info_data, colWidths=[5*cm, 12*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING',    (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.5*cm))

        # ── Compliance score ─────────────────────────────────────────────────
        score = doc_data.get('compliance_score', 0)
        story.append(Paragraph('Compliance Score', h2_style))
        story.append(Paragraph(f'<b>{score}%</b> — {"Compliant" if score >= 70 else "Needs Review" if score >= 40 else "Non-Compliant"}', body_style))
        story.append(Spacer(1, 0.3*cm))

        # ── Validations ──────────────────────────────────────────────────────
        validations = doc_data.get('validations', [])
        if validations:
            story.append(Paragraph('Rule Validations', h2_style))
            val_data = [['Rule', 'Result', 'Evidence']]
            for v in validations:
                rule_title = v.get('rule', {}).get('title', '') if isinstance(v.get('rule'), dict) else str(v.get('rule', '—'))
                result     = '✓ Valid' if v.get('is_valid') else '✗ Invalid'
                evidence   = str(v.get('evidence_text', ''))[:80] + ('…' if len(str(v.get('evidence_text', ''))) > 80 else '')
                val_data.append([rule_title, result, evidence])

            vtable = Table(val_data, colWidths=[6*cm, 2.5*cm, 8.5*cm])
            vtable.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
                ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
                ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',   (0, 0), (-1, -1), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('PADDING',    (0, 0), (-1, -1), 5),
                ('TEXTCOLOR',  (1, 1), (1, -1), colors.HexColor('#16a34a')),
            ]))
            story.append(vtable)
            story.append(Spacer(1, 0.5*cm))

        # ── Decision reason ──────────────────────────────────────────────────
        reason = doc_data.get('decision_reason', '') or doc_data.get('reviewer_comment', '')
        if reason:
            story.append(Paragraph('Decision Reason', h2_style))
            story.append(Paragraph(str(reason)[:500], body_style))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    except ImportError:
        # ReportLab not available — return plain text as bytes
        logger.warning('ReportLab not available, returning plain text report')
        lines = [
            'COMPLIANCE REPORT',
            '=' * 50,
            f"Document ID: {doc_data.get('id', '—')}",
            f"Standard: {doc_data.get('norme_name', '—')}",
            f"Employee: {doc_data.get('employee_username', '—')}",
            f"Status: {doc_data.get('status', '—')}",
            f"Compliance Score: {doc_data.get('compliance_score', 0)}%",
            f"Decision: {doc_data.get('final_decision', '—')}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ]
        return '\n'.join(lines).encode('utf-8')
    except Exception as e:
        raise RuntimeError(f'PDF generation failed: {e}') from e
