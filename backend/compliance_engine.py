import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class Rule:
    id: str
    title: str
    severity: str
    condition: str
    action: str
    mandatory: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'severity': self.severity,
            'condition': self.condition,
            'action': self.action,
            'mandatory': self.mandatory,
        }


SEVERITY_WEIGHTS = {
    'CRITICAL': -40,
    'HIGH': -25,
    'MEDIUM': -10,
    'LOW': -5,
    'INFO': -1,
}

MANDATORY_SECTIONS = [
    'objective',
    'scope',
    'responsibilities',
    'procedure',
    'evidence',
    'validation',
    'review',
    'archive',
]

AMBIGUOUS_TERMS = [
    'possibly',
    'rapidly',
    'as needed',
    'if necessary',
    'appropriate',
    'eventually',
    'where appropriate',
    'as required',
]

CONFLICT_PATTERNS = [
    (r'review (?:annually|yearly|once a year)', r'expir(?:e|ation).{0,30}3 months'),
    (r'review (?:annually|yearly|once a year)', r'expir(?:e|ation).{0,30}90 days'),
    (r'validat(?:e|ion) (?:required|mandatory)', r'pending'),
]

PASSIVE_VOICE_PATTERNS = [
    r'\b(?:is|was|were|be|been|being|are)\s+[a-zA-Z]+ed\b',
    r'\b(?:is|was|were|be|been|being|are)\s+.*\bby\b',
]

TEXT_PATTERNS = {
    'version': [
        r'\b[Vv]ersion\s*[:\-]?\s*\d+(?:\.\d+)*\b',
        r'\b[vV]\d+(?:\.\d+)*\b',
    ],
    'document_id': [
        r'\b[A-Z]{2,}(?:-[A-Z0-9]+){1,5}\b',   # PROC-ISO9001-2026-014, DOC-QA-001
        r'\b[A-Z]{2,}-\d+\b',                    # DOC-001
        r'(?i)identifiant\s*[:\-]?\s*\S+',       # Identifiant: PROC-...
        r'(?i)\bID\s*[:\-]?\s*\S+',
    ],
    'approval': [
        r'(?i)\bapprouv[eé]\b',
        r'(?i)\bAPPROUV[EÉ]\b',
        r'(?i)\bstatut\s*[:\-]?\s*APPROUV[EÉ]\b',
        r'\bapproved\b',
        r'\bvalidated?\b',
        r'(?i)\bvalid[eé]\b',
        r'(?i)\bsign[eé]\b',
        r'\brejected?\b',
        r'(?i)\brefus[eé]\b',
        r'\bpending\b',
    ],
    'owner': [
        r'\bowner\b',
        r'\bmanager\b',
        r'(?i)\bresponsable\b',
        r'(?i)\bauteur\b',
        r'\bvalidated? by\b',
        r'(?i)\bvalid[eé] par\b',
        r'(?i)\bsign[eé] par\b',
        r'(?i)\bresponsable qualit[eé]\b',
        r'\bresponsible\b',
    ],
    'date': [
        r'\b\d{2}/\d{2}/\d{4}\b',
        r'\b\d{4}-\d{2}-\d{2}\b',
        r'\b\d{2}\.\d{2}\.\d{4}\b',
    ],
    'expiration': [
        r'(?i)\bexpir(?:e|ation|é)\b.*?(?:\d+\s*(?:days?|months?|years?|mois|ans?)|\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})',
        r'\bvalid until\b.*?(?:\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})',
    ],
}

DEFAULT_RULES: List[Rule] = [
    Rule(id='R1', title='Version required', severity='HIGH', condition='version_missing', action='Reject'),
    Rule(id='R2', title='Document ID required', severity='HIGH', condition='document_id_missing', action='Reject'),
    Rule(id='R3', title='Approval required', severity='CRITICAL', condition='approval_missing', action='Reject'),
    Rule(id='R4', title='Owner required', severity='HIGH', condition='owner_missing', action='Reject'),
    Rule(id='R5', title='Objective section required', severity='MEDIUM', condition='objective_section_missing', action='Reject'),
    Rule(id='R6', title='Scope section required', severity='MEDIUM', condition='scope_section_missing', action='Reject'),
    Rule(id='R7', title='Review section required', severity='MEDIUM', condition='review_section_missing', action='Reject'),
    Rule(id='R8', title='Archive section required', severity='MEDIUM', condition='archive_section_missing', action='Reject'),
    Rule(id='R9', title='Ambiguous language detected', severity='INFO', condition='ambiguous_language', action='Recommend'),
    Rule(id='R10', title='Conflicting review requirements', severity='CRITICAL', condition='review_conflict', action='Reject'),
]

TRAINING_FILE = Path(__file__).resolve().parent / 'compliance_training.json'
REFERENCE_FOLDER = Path(__file__).resolve().parent / 'compliance_references'


class ComplianceAnalysisError(Exception):
    pass


def normalize_text(text: str) -> str:
    if not text:
        return ''
    normalized = unicodedata.normalize('NFD', text)
    without_accents = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
    return re.sub(r'\s+', ' ', without_accents).strip().lower()


def extract_text_from_pdf(file_stream: BytesIO) -> str:
    text = ''
    try:
        import pdfplumber

        file_stream.seek(0)
        with pdfplumber.open(file_stream) as pdf:
            text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
    except Exception:
        pass

    if text:
        return text

    try:
        import fitz

        file_stream.seek(0)
        doc = fitz.open(stream=file_stream.read(), filetype='pdf')
        text = '\n'.join(page.get_text() or '' for page in doc)
        return text
    except Exception as exc:
        raise ComplianceAnalysisError('Could not extract text from PDF.') from exc


def extract_text_from_docx(file_stream: BytesIO) -> str:
    try:
        from docx import Document as DocxDocument

        file_stream.seek(0)
        doc = DocxDocument(file_stream)
        return '\n'.join(paragraph.text for paragraph in doc.paragraphs)
    except Exception as exc:
        raise ComplianceAnalysisError('Could not extract text from DOCX.') from exc


def extract_text_from_txt(file_stream: BytesIO) -> str:
    file_stream.seek(0)
    raw = file_stream.read()
    if isinstance(raw, bytes):
        return raw.decode('utf-8', errors='replace')
    return str(raw)


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    file_stream = BytesIO(file_bytes)
    lower_name = filename.lower()
    if lower_name.endswith('.pdf'):
        return extract_text_from_pdf(file_stream)
    if lower_name.endswith('.docx'):
        return extract_text_from_docx(file_stream)
    if lower_name.endswith('.txt'):
        return extract_text_from_txt(file_stream)
    raise ComplianceAnalysisError('Unsupported file type. Only PDF, DOCX and TXT are supported.')


def find_pattern_matches(patterns: List[str], text: str) -> List[str]:
    matches: List[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if isinstance(match, tuple):
                matches.append(''.join(match).strip())
            else:
                matches.append(str(match).strip())
    return matches


def detect_sections(normalized_text: str) -> Dict[str, bool]:
    found = {}
    for section in MANDATORY_SECTIONS:
        found[section] = bool(re.search(rf'\b{re.escape(section)}\b', normalized_text))
    return found


def detect_ambiguous_terms(normalized_text: str) -> List[str]:
    found = []
    for term in AMBIGUOUS_TERMS:
        pattern = rf'\b{re.escape(term)}\b'
        if re.search(pattern, normalized_text):
            found.append(term)
    return found


def detect_conflicts(normalized_text: str) -> List[str]:
    conflicts = []
    for left, right in CONFLICT_PATTERNS:
        if re.search(left, normalized_text) and re.search(right, normalized_text):
            conflicts.append(f'Conflict between "{left}" and "{right}"')
    return conflicts


def load_reference_texts() -> List[str]:
    if not REFERENCE_FOLDER.exists() or not REFERENCE_FOLDER.is_dir():
        return []
    texts = []
    for path in sorted(REFERENCE_FOLDER.glob('*.txt')):
        try:
            texts.append(path.read_text(encoding='utf-8', errors='replace'))
        except Exception:
            continue
    return texts


def compute_similarity_score(normalized_text: str) -> int:
    references = load_reference_texts()
    if not references:
        return 0
    documents = references + [normalized_text]
    vectorizer = TfidfVectorizer(stop_words='english')
    matrix = vectorizer.fit_transform(documents)
    similarity_matrix = cosine_similarity(matrix[-1:], matrix[:-1])
    if similarity_matrix.size == 0:
        return 0
    best = float(similarity_matrix.max())
    return int(round(best * 100))


def evaluate_rule(rule: Rule, extracted: Dict[str, Any], normalized_text: str, section_map: Dict[str, bool]) -> Tuple[bool, Optional[str]]:
    condition = rule.condition
    evidence = None

    if condition == 'version_missing':
        passed = bool(extracted['version'])
        evidence = extracted['version']
    elif condition == 'document_id_missing':
        passed = bool(extracted['document_id'])
        evidence = extracted['document_id']
    elif condition == 'approval_missing':
        passed = bool(extracted['approval']) and extracted['approval'].lower() not in ['pending']
        evidence = extracted['approval']
    elif condition == 'owner_missing':
        passed = bool(extracted['owner'])
        evidence = extracted['owner']
    elif condition == 'objective_section_missing':
        passed = section_map.get('objective', False)
    elif condition == 'scope_section_missing':
        passed = section_map.get('scope', False)
    elif condition == 'review_section_missing':
        passed = section_map.get('review', False)
    elif condition == 'archive_section_missing':
        passed = section_map.get('archive', False)
    elif condition == 'ambiguous_language':
        passed = len(extracted['ambiguous_terms']) == 0
        evidence = ', '.join(extracted['ambiguous_terms'][:5]) if extracted['ambiguous_terms'] else None
    elif condition == 'review_conflict':
        passed = len(extracted['conflicts']) == 0
        evidence = '; '.join(extracted['conflicts'][:3]) if extracted['conflicts'] else None
    else:
        passed = False

    return passed, evidence


def compute_rule_score(rule_failures: List[Dict[str, Any]]) -> int:
    score = 100
    for failure in rule_failures:
        score += SEVERITY_WEIGHTS.get(failure['severity'], 0)
    return max(0, min(100, score))


def compute_structure_score(section_map: Dict[str, bool]) -> int:
    total = len(MANDATORY_SECTIONS)
    present = sum(1 for present in section_map.values() if present)
    return int(round((present / total) * 100))


def compute_clarity_score(text: str, ambiguous_count: int) -> int:
    sentences = [s.strip() for s in re.split(r'[\.\?\!]+', text) if s.strip()]
    words = re.findall(r"[\wÀ-ÖØ-öø-ÿ']+", text)
    avg_sentence_length = len(words) / len(sentences) if sentences else 0
    sentence_score = max(0, 100 - abs(avg_sentence_length - 20) * 3)

    paragraph_lengths = [len(re.findall(r"[\wÀ-ÖØ-öø-ÿ']+", p)) for p in re.split(r'\n{2,}', text) if p.strip()]
    max_paragraph = max(paragraph_lengths) if paragraph_lengths else 0
    paragraph_penalty = max(0, (max_paragraph - 120) * 0.2)
    paragraph_score = max(0, 100 - paragraph_penalty)

    ambiguity_penalty = min(50, ambiguous_count * 5)
    ambiguous_score = max(0, 100 - ambiguity_penalty)

    clarity = int(round((sentence_score * 0.5) + (ambiguous_score * 0.3) + (paragraph_score * 0.2)))
    return max(0, min(100, clarity))


def compute_consistency_score(conflict_count: int) -> int:
    if conflict_count == 0:
        return 100
    return max(0, 100 - (20 * conflict_count))


def load_training_samples() -> List[Dict[str, Any]]:
    if not TRAINING_FILE.exists():
        return []
    try:
        return json.loads(TRAINING_FILE.read_text(encoding='utf-8'))
    except Exception:
        return []


def save_training_sample(sample: Dict[str, Any]) -> None:
    samples = load_training_samples()
    samples.append(sample)
    TRAINING_FILE.write_text(json.dumps(samples, indent=2), encoding='utf-8')


def is_automation_ready(confidence: int, critical_failed: bool, similarity_score: int, training_count: int) -> bool:
    return (
        training_count >= 30
        and confidence >= 90
        and not critical_failed
        and similarity_score >= 85
    )


class ComplianceEngine:
    def __init__(self):
        self.reference_folder = REFERENCE_FOLDER
        self.training_file = TRAINING_FILE

    def analyze_document(self, text: str, norme: Any, document: Optional[Any] = None) -> Dict[str, Any]:
        raw_text = str(text or '')
        normalized_text = normalize_text(raw_text)

        extracted = self._extract_metadata(normalized_text, raw_text)
        section_map = detect_sections(normalized_text)
        extracted['missing_sections'] = [section for section, present in section_map.items() if not present]

        detected_rules = []
        valid_rules = []
        invalid_rules = []
        rule_failures = []
        diagnostics: List[Dict[str, Any]] = []

        rules = list(getattr(norme, 'rules', []).all()) if norme is not None else []
        for rule in rules:
            valid, evidence = self._evaluate_rule(rule, normalized_text, raw_text, extracted, section_map)
            rule_data = {
                'id': rule.id,
                'title': rule.title,
                'description': rule.description,
                'severity': rule.severity,
                'condition': rule.condition,
                'action': rule.action,
                'is_valid': valid,
                'evidence': evidence,
            }
            # gather diagnostics for debugging why a rule matched or not
            candidates = list(set(self._extract_candidates(rule.condition or '') + self._extract_candidates(rule.title or '')))
            tokens = self._extract_keywords((rule.condition or '') + ' ' + (rule.title or ''))
            matched_candidates = [c for c in candidates if (c and (c in normalized_text or re.search(re.escape(c), raw_text, flags=re.IGNORECASE)))]
            matched_tokens = [t for t in tokens if t and t in normalized_text]
            diagnostics.append({
                'rule_id': rule.id,
                'candidates': candidates,
                'tokens': tokens,
                'matched_candidates': matched_candidates,
                'matched_tokens': matched_tokens,
                'evidence': evidence,
                'is_valid': valid,
            })
            detected_rules.append(rule_data)
            if valid:
                valid_rules.append(rule_data)
            else:
                invalid_rules.append(rule_data)
                rule_failures.append({
                    'rule': rule.title,
                    'severity': rule.severity,
                    'penalty': abs(SEVERITY_WEIGHTS.get(rule.severity, 0)),
                    'action': rule.action,
                    'condition': rule.condition,
                    'evidence': evidence,
                })

        rule_score = compute_rule_score(rule_failures)
        structure_score = compute_structure_score(section_map)
        clarity_score = self._compute_clarity_score(raw_text, len(extracted['ambiguous_terms']))
        consistency_score = compute_consistency_score(len(extracted['conflicts']))
        similarity_score = compute_similarity_score(normalized_text)
        evidence_score = self._compute_evidence_score(document, len(rules))

        confidence_score = int(round(
            0.40 * rule_score
            + 0.20 * structure_score
            + 0.15 * clarity_score
            + 0.10 * consistency_score
            + 0.15 * similarity_score
        ))

        critical_failures = sum(1 for failure in rule_failures if failure['severity'] == 'CRITICAL')
        decision = self._make_decision(critical_failures, confidence_score)
        document_status = self._document_status(decision)

        if document is not None and hasattr(document, 'status'):
            self._sync_document_status(document, document_status)

        return {
            'norme_id': getattr(norme, 'id', None),
            'norme_name': getattr(norme, 'name', ''),
            'rule_score': rule_score,
            'clarity_score': clarity_score,
            'structure_score': structure_score,
            'consistency_score': consistency_score,
            'similarity_score': similarity_score,
            'evidence_score': evidence_score,
            'confidence_score': confidence_score,
            'critical_failures': critical_failures,
            'decision': decision,
            'document_status': document_status,
            'total_rules': len(rules),
            'valid_count': len(valid_rules),
            'invalid_count': len(invalid_rules),
            'compliance': int((len(valid_rules) / len(rules)) * 100) if rules else 0,
            'detected_rules': detected_rules,
            'valid_rules': valid_rules,
            'invalid_rules': invalid_rules,
            'diagnostics': diagnostics,
            'automation_ready': is_automation_ready(confidence_score, critical_failures, similarity_score, len(load_training_samples())),
        }

    def _extract_metadata(self, normalized_text: str, raw_text: str) -> Dict[str, Any]:
        extracted = {
            'version': None,
            'document_id': None,
            'approval': None,
            'owner': None,
            'dates': [],
            'expiration': None,
            'ambiguous_terms': [],
            'conflicts': [],
        }

        for key, patterns in TEXT_PATTERNS.items():
            # Run on raw_text with IGNORECASE so French uppercase (APPROUVÉ, PROC-...)
            # and accented characters are matched correctly.
            matches = find_pattern_matches(patterns, raw_text)
            if not matches:
                # fallback to normalized text
                matches = find_pattern_matches(patterns, normalized_text)
            if not matches:
                continue
            if key == 'version':
                extracted['version'] = matches[0]
            elif key == 'document_id':
                extracted['document_id'] = matches[0]
            elif key == 'approval':
                extracted['approval'] = matches[0]
            elif key == 'owner':
                extracted['owner'] = matches[0]
            elif key == 'date':
                extracted['dates'] = matches
            elif key == 'expiration':
                extracted['expiration'] = matches[0]

        extracted['ambiguous_terms'] = detect_ambiguous_terms(normalized_text)
        extracted['conflicts'] = detect_conflicts(normalized_text)
        return extracted

    STOPWORDS = {
        'et', 'ou', 'le', 'la', 'les', 'du', 'de', 'des', 'un', 'une', 'dans', 'sur', 'avec', 'pour', 'par',
        'est', 'sont', 'se', 'sa', 'son', 'ces', 'qui', 'que', 'à', 'au', 'aux', 'du', 'd', 'il', 'elle',
        'ou', 'où', 'ne', 'pas', 'plus', 'moins', 'entre', 'comme', 'son', 'sa', 'ses', 'être', 'avoir', 'faire',
    }

    def _evaluate_rule(self, rule: Rule, normalized_text: str, raw_text: str, extracted: Dict[str, Any], section_map: Dict[str, bool]) -> Tuple[bool, Optional[str]]:
        condition = (rule.condition or '').strip().lower()
        evidence = None
        passed = False

        if condition in ('identification_missing', 'document_id_missing'):
            passed = bool(extracted['document_id'])
            evidence = extracted['document_id']
        elif condition == 'version_missing':
            passed = bool(extracted['version'])
            evidence = extracted['version']
        elif condition == 'approval_missing':
            approval_val = (extracted['approval'] or '').lower()
            rejected_words = ['pending', 'rejected', 'refuse', 'refusé', 'en attente']
            passed = bool(approval_val) and not any(w in approval_val for w in rejected_words)
            evidence = extracted['approval']
        elif condition == 'owner_missing':
            passed = bool(extracted['owner'])
            evidence = extracted['owner']
        elif condition == 'revision_overdue':
            keywords = ['revision', 'revue', 'periodique', 'annuelle', 'review', 'revu']
            matched = next((kw for kw in keywords if kw in normalized_text), None)
            passed = matched is not None
            evidence = matched
        elif condition == 'evidence_missing':
            keywords = ['annexe', 'audit', 'justificatif', 'preuve', 'evidence', 'formation', 'rapport']
            matched = next((kw for kw in keywords if kw in normalized_text), None)
            passed = matched is not None
            evidence = matched
        elif condition == 'traceability_missing':
            keywords = ['tracabilite', 'tracabilite', 'historique', 'modification', 'journal', 'traceability']
            matched = next((kw for kw in keywords if kw in normalized_text), None)
            passed = matched is not None
            evidence = matched
        elif condition == 'obsolete_document_used':
            keywords = ['obsolete', 'obsolete', 'archive', 'archive', 'bloque', 'bloque', 'perime', 'perime']
            matched = next((kw for kw in keywords if kw in normalized_text), None)
            passed = matched is not None
            evidence = matched
        elif condition == 'objective_section_missing':
            passed = section_map.get('objective', False)
        elif condition == 'scope_section_missing':
            passed = section_map.get('scope', False)
        elif condition == 'review_section_missing':
            passed = section_map.get('review', False)
        elif condition == 'archive_section_missing':
            passed = section_map.get('archive', False)
        elif condition == 'ambiguous_language':
            passed = len(extracted['ambiguous_terms']) == 0
            evidence = ', '.join(extracted['ambiguous_terms'][:5]) if extracted['ambiguous_terms'] else None
        elif condition == 'review_conflict':
            passed = len(extracted['conflicts']) == 0
            evidence = '; '.join(extracted['conflicts'][:3]) if extracted['conflicts'] else None
        elif 'absent' in condition or 'manquant' in condition:
            required_phrases = self._extract_required_phrases(condition)
            evidence_items = []
            missing_items = []
            for phrase in required_phrases:
                if self._phrase_in_text(phrase, normalized_text, raw_text):
                    evidence_items.append(phrase)
                else:
                    missing_items.append(phrase)
            passed = len(missing_items) == 0 and len(required_phrases) > 0
            evidence = ', '.join(evidence_items[:5]) if evidence_items else None
        elif 'statut validation' in condition or 'approuvé' in condition or 'validation' in condition:
            passed = bool(extracted['approval']) and extracted['approval'].lower() not in ['pending', 'rejected', 'refusé']
            evidence = extracted['approval']
        elif 'révision' in condition or 'revision' in condition:
            evidence = self._match_evidence(rule, normalized_text, raw_text)
            passed = evidence is not None
        else:
            evidence = self._match_evidence(rule, normalized_text, raw_text)
            passed = evidence is not None

        return passed, evidence

    def _phrase_in_text(self, phrase: str, normalized_text: str, raw_text: str) -> bool:
        phrase_norm = normalize_text(phrase)
        if phrase_norm and phrase_norm in normalized_text:
            return True
        return bool(re.search(re.escape(phrase), raw_text, flags=re.IGNORECASE))

    def _extract_required_phrases(self, condition: str) -> List[str]:
        parts = re.split(r'\b(?:ou|et)\b', condition)
        phrases = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            cleaned = re.sub(r'\b(absent|absente|absents|manquant|manquante|manquants|manquantes|absence|statut|validation|révision|revision|date|expir(?:e|ation)|dépasseé|dépassée)\b', '', part)
            cleaned = re.sub(r'[^\w\s\-]', ' ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned:
                phrases.append(cleaned)
        return phrases

    def _match_evidence(self, rule: Rule, normalized_text: str, raw_text: str) -> Optional[str]:
        search_fields = [rule.condition or '', rule.title or '']
        candidates = []
        for source in search_fields:
            candidates.extend(self._extract_candidates(source))

        for candidate in candidates:
            if candidate and candidate in normalized_text:
                return candidate
            if candidate and re.search(re.escape(candidate), raw_text, flags=re.IGNORECASE):
                return candidate

        tokens = self._extract_keywords(' '.join(search_fields))
        matched = [token for token in tokens if token in normalized_text]
        if matched and len(matched) >= max(2, len(tokens) // 2):
            return ' '.join(matched[:5])

        return None

    def _extract_candidates(self, source: str) -> List[str]:
        if not source:
            return []
        normalized = normalize_text(source)
        parts = re.split(r'\b(?:ou|et|,|;|\||\+|\-|>|<|=|\(|\))\b', normalized)
        return [part.strip() for part in parts if len(part.strip()) > 2]

    def _extract_keywords(self, source: str) -> List[str]:
        normalized = normalize_text(source)
        tokens = [token for token in re.findall(r"[\wÀ-ÖØ-öø-ÿ']+", normalized) if len(token) > 2]
        return [token for token in tokens if token not in self.STOPWORDS]

    def _compute_clarity_score(self, raw_text: str, ambiguous_count: int) -> int:
        sentences = [s.strip() for s in re.split(r'[\.\?\!]+', raw_text) if s.strip()]
        words = re.findall(r"[\wÀ-ÖØ-öø-ÿ']+", raw_text)
        avg_sentence_length = len(words) / len(sentences) if sentences else 0
        sentence_penalty = max(0, min(50, (avg_sentence_length - 20) * 2))

        avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
        complexity_penalty = max(0, min(20, (avg_word_length - 5) * 3))

        passive_matches = sum(bool(re.search(pattern, raw_text, flags=re.IGNORECASE)) for pattern in PASSIVE_VOICE_PATTERNS)
        passive_penalty = min(20, passive_matches * 5)

        ambiguous_penalty = min(30, ambiguous_count * 5)

        clarity = 100 - (sentence_penalty + complexity_penalty + passive_penalty + ambiguous_penalty)
        return max(0, min(100, int(round(clarity))))

    def _compute_evidence_score(self, document: Optional[Any], total_rules: int) -> int:
        if document is None or total_rules == 0:
            return 0

        validations = getattr(document, 'validations', None)
        if validations is None:
            return 0

        evidence_rules = 0
        for validation in validations.all():
            if (getattr(validation, 'evidence_text', None) and str(validation.evidence_text).strip()) or getattr(validation, 'evidence_file', None) or getattr(validation, 'comment', None):
                evidence_rules += 1

        score = int(round((evidence_rules / total_rules) * 100))
        return max(0, min(100, score))

    def _make_decision(self, critical_failures: int, confidence: int) -> str:
        if critical_failures > 0:
            return 'REJECTED'
        if confidence < 70:
            return 'TEAMLEAD_REVIEW'
        if confidence < 90:
            return 'ASSISTED_VALIDATION'
        return 'AUTO_APPROVE'

    def _document_status(self, decision: str) -> str:
        if decision == 'REJECTED':
            return 'rejected'
        if decision == 'AUTO_APPROVE':
            return 'auto_approved'
        return 'reviewing'

    def _sync_document_status(self, document: Any, status: str) -> None:
        if getattr(document, 'is_finalized', False):
            return
        if getattr(document, 'status', None) != status:
            document.status = status
            document.save(update_fields=['status'])


def analyze_document(file_bytes: bytes, filename: str, norm: str = 'ISO9001') -> Dict[str, Any]:
    raw_text = extract_text_from_file(file_bytes, filename)
    engine = ComplianceEngine()
    analysis = engine.analyze_document(text=raw_text, norme=None, document=None)
    analysis.update({'document_id': Path(filename).stem})
    return analysis


def record_review(document_id: str, decision: str, corrections: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    sample = {
        'document_id': document_id,
        'decision': decision,
        'corrections': corrections or {},
    }
    save_training_sample(sample)
    return {
        'recorded': True,
        'training_samples': len(load_training_samples()),
    }
