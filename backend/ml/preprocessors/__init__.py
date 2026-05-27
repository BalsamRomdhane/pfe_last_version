"""
Text preprocessing module for NLP pipeline.
Handles cleaning, tokenization, lemmatization, and sentence segmentation.
"""

import re
import logging
from typing import List, Optional, Dict, Any
import nltk

# Download required NLTK data
for _resource, _path in [
    ('punkt',     'tokenizers/punkt'),
    ('punkt_tab', 'tokenizers/punkt_tab'),
    ('stopwords', 'corpora/stopwords'),
    ('wordnet',   'corpora/wordnet'),
]:
    try:
        nltk.data.find(_path)
    except LookupError:
        nltk.download(_resource, quiet=True)

from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

try:
    import spacy
    nlp = spacy.load('en_core_web_sm')
except ImportError:
    spacy = None
    nlp = None

logger = logging.getLogger(__name__)


class TextPreprocessor:
    """Main text preprocessing class."""

    def __init__(self, language: str = 'english'):
        """
        Initialize preprocessor.

        Args:
            language: Language for processing (default: english)
        """
        self.language = language
        self.stop_words = set(stopwords.words(language))
        self.lemmatizer = WordNetLemmatizer()

        # Custom stop words for document analysis
        self.custom_stop_words = {
            'document', 'page', 'section', 'chapter', 'paragraph',
            'figure', 'table', 'appendix', 'reference', 'note'
        }
        self.stop_words.update(self.custom_stop_words)

    def preprocess_text(self, text: str) -> Dict[str, Any]:
        """
        Complete text preprocessing pipeline.

        Args:
            text: Raw text to preprocess

        Returns:
            Dictionary with processed text components
        """
        if not text or not isinstance(text, str):
            return {
                'original_text': text,
                'cleaned_text': '',
                'sentences': [],
                'tokens': [],
                'lemmatized_tokens': [],
                'error': 'Invalid input text'
            }

        try:
            # Clean text
            cleaned_text = self.clean_text(text)

            # Segment into sentences
            sentences = self.segment_sentences(cleaned_text)

            # Tokenize
            tokens = self.tokenize_text(cleaned_text)

            # Remove stop words
            filtered_tokens = self.remove_stop_words(tokens)

            # Lemmatize
            lemmatized_tokens = self.lemmatize_tokens(filtered_tokens)

            return {
                'original_text': text,
                'cleaned_text': cleaned_text,
                'sentences': sentences,
                'tokens': tokens,
                'filtered_tokens': filtered_tokens,
                'lemmatized_tokens': lemmatized_tokens,
                'error': None
            }

        except Exception as e:
            logger.error(f"Error in text preprocessing: {e}")
            return {
                'original_text': text,
                'cleaned_text': '',
                'sentences': [],
                'tokens': [],
                'lemmatized_tokens': [],
                'error': str(e)
            }

    def clean_text(self, text: str) -> str:
        """
        Clean raw text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove special characters but keep punctuation for sentence segmentation
        text = re.sub(r'[^\w\s\.\!\?\,\;\:\-\(\)]', '', text)

        # Normalize quotes
        text = re.sub(r'["""]', '"', text)
        text = re.sub(r"['']", "'", text)

        return text.strip()

    def segment_sentences(self, text: str) -> List[str]:
        """
        Segment text into sentences.

        Args:
            text: Cleaned text

        Returns:
            List of sentences
        """
        try:
            sentences = sent_tokenize(text)
            # Filter out very short sentences (likely artifacts)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
            return sentences
        except Exception as e:
            logger.warning(f"Sentence segmentation failed: {e}")
            # Fallback: split on periods
            return [s.strip() for s in text.split('.') if s.strip()]

    def tokenize_text(self, text: str) -> List[str]:
        """
        Tokenize text into words.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        try:
            tokens = word_tokenize(text.lower())
            return tokens
        except Exception as e:
            logger.warning(f"Tokenization failed: {e}")
            # Fallback: simple split
            return text.lower().split()

    def remove_stop_words(self, tokens: List[str]) -> List[str]:
        """
        Remove stop words from tokens.

        Args:
            tokens: List of tokens

        Returns:
            Filtered tokens
        """
        return [token for token in tokens if token not in self.stop_words]

    def lemmatize_tokens(self, tokens: List[str]) -> List[str]:
        """
        Lemmatize tokens.

        Args:
            tokens: List of tokens

        Returns:
            Lemmatized tokens
        """
        try:
            if spacy and nlp:
                # Use spaCy for better lemmatization
                doc = nlp(' '.join(tokens))
                return [token.lemma_ for token in doc]
            else:
                # Fallback to NLTK
                return [self.lemmatizer.lemmatize(token) for token in tokens]
        except Exception as e:
            logger.warning(f"Lemmatization failed: {e}")
            return tokens


class ISOTextPreprocessor(TextPreprocessor):
    """Specialized preprocessor for ISO document analysis."""

    def __init__(self, language: str = 'english'):
        super().__init__(language)

        # ISO-specific stop words
        self.iso_stop_words = {
            'iso', 'standard', 'requirement', 'shall', 'should', 'may',
            'must', 'clause', 'section', 'paragraph', 'subparagraph',
            'norm', 'norme', 'regulation', 'directive'
        }
        self.stop_words.update(self.iso_stop_words)

    def preprocess_iso_text(self, text: str) -> Dict[str, Any]:
        """
        Preprocess text specifically for ISO compliance analysis.

        Args:
            text: ISO document text

        Returns:
            Processed text components
        """
        result = self.preprocess_text(text)

        # Additional ISO-specific processing
        if result['sentences']:
            # Identify requirement sentences (containing modal verbs)
            requirement_sentences = []
            for sentence in result['sentences']:
                if any(word in sentence.lower() for word in ['shall', 'must', 'should', 'may']):
                    requirement_sentences.append(sentence)
            result['requirement_sentences'] = requirement_sentences

        return result