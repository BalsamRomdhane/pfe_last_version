#!/usr/bin/env python
"""
Installation and setup script for Document Compliance Analysis system.
Downloads required NLTK data and spaCy models.
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a shell command and report success/failure."""
    print(f"\n📦 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e.stderr}")
        return False

def install_nltk_data():
    """Download required NLTK data."""
    print("\n🔄 Downloading NLTK data...")

    nltk_packages = [
        'punkt',
        'stopwords',
        'wordnet',
        'averaged_perceptron_tagger',
        'maxent_ne_chunker',
        'words'
    ]

    for package in nltk_packages:
        success = run_command(
            f'python -c "import nltk; nltk.download(\'{package}\', quiet=True)"',
            f"Downloading NLTK {package}"
        )
        if not success:
            print(f"⚠️  Warning: Failed to download NLTK {package}")

    print("✅ NLTK data download completed")

def install_spacy_model():
    """Download spaCy English model."""
    success = run_command(
        'python -m spacy download en_core_web_sm',
        "Downloading spaCy English model (en_core_web_sm)"
    )
    return success

def test_imports():
    """Test that all required packages can be imported."""
    print("\n🧪 Testing imports...")

    required_imports = [
        ('nltk', 'NLTK'),
        ('gensim', 'Gensim'),
        ('spacy', 'spaCy'),
        ('sklearn', 'scikit-learn'),
        ('pdfplumber', 'pdfplumber'),
        ('docx', 'python-docx'),
        ('numpy', 'NumPy'),
        ('pandas', 'Pandas'),
        ('joblib', 'Joblib')
    ]

    failed_imports = []

    for module, name in required_imports:
        try:
            __import__(module)
            print(f"✅ {name} imported successfully")
        except ImportError:
            print(f"❌ {name} import failed")
            failed_imports.append(name)

    if failed_imports:
        print(f"\n⚠️  Warning: The following packages could not be imported: {', '.join(failed_imports)}")
        print("Please install missing packages with: pip install -r requirements.txt")
        return False

    print("✅ All imports successful")
    return True

def test_spacy_model():
    """Test that spaCy model is working."""
    print("\n🧪 Testing spaCy model...")

    try:
        import spacy
        nlp = spacy.load('en_core_web_sm')

        # Test basic functionality
        doc = nlp("This is a test document for compliance analysis.")
        tokens = [token.text for token in doc]
        lemmas = [token.lemma_ for token in doc]

        print(f"✅ spaCy model loaded successfully")
        print(f"   Sample tokens: {tokens[:5]}")
        print(f"   Sample lemmas: {lemmas[:5]}")

        return True

    except Exception as e:
        print(f"❌ spaCy model test failed: {e}")
        return False

def test_ml_components():
    """Test basic ML components."""
    print("\n🧪 Testing ML components...")

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        # Test TF-IDF
        documents = [
            "This is a sample document about quality management.",
            "Quality assurance requires proper documentation.",
            "Document control is essential for compliance."
        ]

        vectorizer = TfidfVectorizer(max_features=100)
        tfidf_matrix = vectorizer.fit_transform(documents)

        # Test similarity
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

        print("✅ ML components working correctly")
        print(f"   TF-IDF matrix shape: {tfidf_matrix.shape}")
        print(f"   Sample similarity: {similarity:.3f}")

        return True

    except Exception as e:
        print(f"❌ ML components test failed: {e}")
        return False

def main():
    """Main installation function."""
    print("🚀 Document Compliance Analysis System - Installation")
    print("=" * 60)

    # Test basic imports first
    if not test_imports():
        print("\n❌ Basic imports failed. Please install requirements first:")
        print("   pip install -r requirements.txt")
        sys.exit(1)

    # Download NLTK data
    install_nltk_data()

    # Download spaCy model
    if not install_spacy_model():
        print("\n❌ spaCy model download failed. You may need to install it manually:")
        print("   python -m spacy download en_core_web_sm")
        sys.exit(1)

    # Test spaCy
    if not test_spacy_model():
        print("\n❌ spaCy model test failed.")
        sys.exit(1)

    # Test ML components
    if not test_ml_components():
        print("\n❌ ML components test failed.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🎉 Installation completed successfully!")
    print("\nNext steps:")
    print("1. Run Django migrations: python manage.py migrate")
    print("2. Train compliance models: python manage.py train_compliance")
    print("3. Start the server: python manage.py runserver")
    print("4. Test the API: POST /api/compliance/analyze/")
    print("\nFor detailed documentation, see: backend/ml/README.md")

if __name__ == "__main__":
    main()