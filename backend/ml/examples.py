#!/usr/bin/env python
"""
Example usage of the Document Compliance Analysis system.
Demonstrates how to integrate the compliance analysis into your Django application.
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from ml.services import compliance_service


def example_text_analysis():
    """Example of analyzing document text directly."""
    print("=== Example: Text Analysis ===")

    # Sample document text
    document_text = """
    Quality Management System Document

    1. Document Identification
    This document is uniquely identified as QMS-001, version 2.1.

    2. Document Approval Process
    All documents must be approved by the quality manager before release.

    3. Document Control
    Changes to documents are controlled and versioned appropriately.

    4. Document Accessibility
    Authorized personnel have access to relevant documents.

    5. Document Protection
    Documents are protected from unauthorized modifications.
    """

    # Analyze compliance
    result = compliance_service.analyze_document_text(document_text, 'ISO9001')

    print(f"Compliance Score: {result['compliance_score']}%")
    print(f"Detected Rules: {result['detected_rules']}")
    print(f"Missing Rules: {result['missing_rules']}")

    return result


def example_file_analysis():
    """Example of analyzing a document file."""
    print("\n=== Example: File Analysis ===")

    # This would work with actual PDF/DOCX files
    # file_path = "/path/to/document.pdf"
    # result = compliance_service.analyze_document_file(file_path, 'ISO9001')

    print("File analysis would work similarly to text analysis")
    print("Just provide the file path instead of text content")


def example_api_integration():
    """Example of how to integrate with Django REST API."""
    print("\n=== Example: API Integration ===")

    # This shows how the API endpoints work
    print("API Endpoints available:")
    print("- POST /api/compliance/analyze/ (analyze document)")
    print("- GET /api/compliance/standards/ (list standards)")
    print("- GET /api/compliance/rules/{standard}/ (get rules)")
    print("- POST /api/compliance/retrain/ (retrain models)")
    print("- POST /api/compliance/threshold/ (update threshold)")

    # Example API payload
    api_payload = {
        "document_text": "Sample document content...",
        "standard": "ISO9001"
    }

    print(f"\nExample API request payload: {api_payload}")


def example_configuration():
    """Example of configuring the system."""
    print("\n=== Example: Configuration ===")

    # Update similarity threshold
    success = compliance_service.update_similarity_threshold(0.5)
    print(f"Threshold update successful: {success}")

    # Get service status
    status = compliance_service.get_service_status()
    print(f"Service status: {status['status']}")
    print(f"Supported standards: {status['supported_standards']}")

    # Retrain models
    result = compliance_service.retrain_models('ISO9001')
    print(f"Model retraining: {result['message']}")


def example_workflow_integration():
    """Example of integrating with the document validation workflow."""
    print("\n=== Example: Workflow Integration ===")

    # This shows how to integrate with your existing document validation
    workflow_steps = [
        "1. User uploads document",
        "2. Extract text from document",
        "3. Run compliance analysis",
        "4. Update document status based on score",
        "5. Create training sample if approved/rejected",
        "6. Notify team lead for manual validation if needed"
    ]

    for step in workflow_steps:
        print(f"  {step}")

    # Example integration code
    integration_code = '''
# In your views.py or services.py

from ml.services import compliance_service

def analyze_document_compliance(document):
    """Analyze document and update status."""
    result = compliance_service.analyze_document_file(
        document.file.path,
        'ISO9001'
    )

    # Update document with analysis results
    document.compliance_score = result['compliance_score']
    document.detected_rules = result['detected_rules']
    document.missing_rules = result['missing_rules']
    document.save()

    # Auto-approve if high confidence
    if result['compliance_score'] >= 80:
        document.status = Document.Status.APPROVED
        document.save()

    return result
'''

    print(f"\nExample integration code:\n{integration_code}")


def main():
    """Run all examples."""
    print("Document Compliance Analysis - Usage Examples")
    print("=" * 60)

    try:
        example_text_analysis()
        example_file_analysis()
        example_api_integration()
        example_configuration()
        example_workflow_integration()

        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("\nFor more information, see:")
        print("- backend/ml/README.md (documentation)")
        print("- backend/ml/test_compliance.py (test script)")
        print("- backend/ml/setup_ml.py (installation)")

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("Make sure the system is properly installed and configured.")


if __name__ == "__main__":
    main()