import os
import re
import unicodedata

from rest_framework.exceptions import ValidationError


# ── Allowed upload types ──────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {'.pdf', '.docx'}
# Maximum upload size: 20 MB
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
# Allowed MIME types (belt-and-suspenders alongside extension check)
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

RULE_KEYWORDS = {
    'ISO9001': {
        'Identification du document': ['reference', 'doc id', 'référence'],
        'Version du document': ['version', 'revision', 'rev'],
        'Approbation du document': ['approved', 'validé', 'signature'],
        'Lisibilité et format': ['format', 'lisible'],
        'Contrôle des modifications': ['modification', 'historique'],
        'Accessibilité': ['accessible'],
        'Protection du document': ['confidentiel', 'protection'],
        'Archivage': ['archivage', 'archive'],
        'Validité du contenu': ['valide', 'exact'],
        'Signature ou validation officielle': ['signature', 'approuvé'],
    },
    'ISO27001': {},
}


def validate_uploaded_file(file):
    """
    Server-side file validation applied before any processing.

    Checks:
    1. File extension against the whitelist
    2. File size against MAX_UPLOAD_BYTES (20 MB)
    3. Content-type header against ALLOWED_MIME_TYPES (advisory only —
       the header is client-supplied, but it catches obvious mistakes)

    Raises ValidationError with a descriptive message on any failure.
    This function must be called in every view that accepts file uploads.
    """
    if not file:
        raise ValidationError({'file': 'No file provided.'})

    # 1. Extension check
    filename  = getattr(file, 'name', '')
    _, ext    = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError({
            'file': (
                f'File type "{ext}" is not allowed. '
                f'Accepted formats: {", ".join(sorted(ALLOWED_EXTENSIONS))}.'
            )
        })

    # 2. Size check
    size = getattr(file, 'size', None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ValidationError({
            'file': f'File size exceeds the {mb} MB limit.'
        })

    # 3. Content-type advisory check
    content_type = getattr(file, 'content_type', '') or ''
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError({
            'file': (
                f'Unexpected content type "{content_type}". '
                'Please upload a valid PDF or DOCX file.'
            )
        })


def extract_text(file):
    file_name = getattr(file, 'name', '').lower()
    file.seek(0)

    if file_name.endswith('.pdf'):
        try:
            import pdfplumber
        except ImportError as exc:
            raise ValidationError('pdfplumber is required to read PDF files.') from exc

        text = ''
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ''
        return text

    if file_name.endswith('.docx'):
        try:
            from docx import Document as DocxDocument
        except ImportError as exc:
            raise ValidationError('python-docx is required to read DOCX files.') from exc

        doc = DocxDocument(file)
        return '\n'.join([p.text for p in doc.paragraphs])

    raise ValidationError({'file': 'Unsupported file type. Only PDF and DOCX are supported.'})


def split_text(text, chunk_size=300):
    if not text:
        return []

    words = text.split()
    return [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]


def check_rule_with_evidence(chunks, keywords):
    for chunk in chunks:
        lower_chunk = chunk.lower()
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in lower_chunk:
                start = lower_chunk.find(keyword_lower)
                evidence_start = max(0, start - 50)
                evidence_end = min(len(chunk), start + len(keyword) + 50)
                evidence = chunk[evidence_start:evidence_end].strip()
                return {
                    'status': 1,
                    'keyword': keyword,
                    'evidence': evidence,
                }

    return {
        'status': 0,
        'keyword': None,
        'evidence': None,
    }


def normalize_standard(standard):
    if not standard:
        return ''
    return re.sub(r'\s+', '', str(standard)).upper()


def extract_features(text, standard):
    standard_key = normalize_standard(standard)
    rules = RULE_KEYWORDS.get(standard_key, {})
    chunks = split_text(text)
    results = {}

    for rule, keywords in rules.items():
        results[rule] = check_rule_with_evidence(chunks, keywords)

    return results


def compute_score(features):
    total = len(features)
    valid = sum(1 for feature in features.values() if feature.get('status') == 1)
    invalid = total - valid
    compliance = int((valid / total) * 100) if total else 0
    return compliance, valid, invalid


def extract_document_text(document):
    if not document.file:
        return ''

    file_path = getattr(document.file, 'path', None)
    if not file_path or not os.path.exists(file_path):
        return ''

    with open(file_path, 'rb') as f:
        return extract_text(f)


def normalize_text(text):
    if not text:
        return ''
    normalized = unicodedata.normalize('NFD', str(text))
    without_accents = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
    return re.sub(r'\s+', ' ', without_accents).strip().lower()
