"""
Text extraction module for PDF and DOCX documents.
Supports local processing without external APIs.
"""

import os
from typing import Optional, Dict, Any
import logging

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from docx import Document
except ImportError:
    Document = None

logger = logging.getLogger(__name__)


class DocumentExtractor:
    """Base class for document text extraction."""

    @staticmethod
    def extract_text(file_path: str) -> Optional[str]:
        """
        Extract text from a document file.

        Args:
            file_path: Path to the document file (PDF or DOCX)

        Returns:
            Extracted text or None if extraction fails
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension == '.pdf':
            return PDFExtractor.extract_text(file_path)
        elif file_extension in ['.docx', '.doc']:
            return DOCXExtractor.extract_text(file_path)
        else:
            logger.error(f"Unsupported file type: {file_extension}")
            return None


class PDFExtractor:
    """PDF text extraction using pdfplumber."""

    @staticmethod
    def extract_text(file_path: str) -> Optional[str]:
        """
        Extract text from PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text or None if extraction fails
        """
        if pdfplumber is None:
            logger.error("pdfplumber not installed")
            return None

        try:
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip()
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return None


class DOCXExtractor:
    """DOCX text extraction using python-docx."""

    @staticmethod
    def extract_text(file_path: str) -> Optional[str]:
        """
        Extract text from DOCX file.

        Args:
            file_path: Path to DOCX file

        Returns:
            Extracted text or None if extraction fails
        """
        if Document is None:
            logger.error("python-docx not installed")
            return None

        try:
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting DOCX text: {e}")
            return None


def get_document_info(file_path: str) -> Dict[str, Any]:
    """
    Get basic information about a document.

    Args:
        file_path: Path to the document

    Returns:
        Dictionary with document metadata
    """
    info = {
        'file_path': file_path,
        'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        'file_extension': os.path.splitext(file_path)[1].lower(),
        'extraction_success': False,
        'text_length': 0
    }

    text = DocumentExtractor.extract_text(file_path)
    if text:
        info['extraction_success'] = True
        info['text_length'] = len(text)

    return info