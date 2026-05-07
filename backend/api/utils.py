import os
import re

from rest_framework.exceptions import ValidationError


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
    return re.sub(r'\s+', ' ', text or '').strip().lower()
