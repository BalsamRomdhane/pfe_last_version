"""
Configuration file for Document Compliance Analysis system.
Contains default settings, thresholds, and parameters.
"""

# Similarity thresholds for rule detection
# Lowered to 0.25 — TF-IDF on short French rule texts produces sparse vectors;
# a threshold of 0.4 misses clearly relevant sentences.
SIMILARITY_THRESHOLDS = {
    'ISO9001': 0.25,
    'ISO27001': 0.25,
    'default': 0.25
}

# Minimum sentence length for analysis
MIN_SENTENCE_LENGTH = 10

# Maximum number of top matches to return
MAX_MATCHES_RETURNED = 10

# Vectorization parameters
TFIDF_PARAMS = {
    'max_features': 5000,
    'min_df': 2,
    'max_df': 0.95,
    'ngram_range': (1, 2),
    'stop_words': 'english'
}

WORD2VEC_PARAMS = {
    'vector_size': 100,
    'window': 5,
    'min_count': 2,
    'workers': 4,
    'epochs': 10
}

FASTTEXT_PARAMS = {
    'vector_size': 100,
    'window': 5,
    'min_count': 2,
    'workers': 4,
    'epochs': 10
}

# Preprocessing settings
PREPROCESSING_CONFIG = {
    'language': 'english',
    'use_spacy_lemmatizer': True,
    'remove_punctuation': False,  # Keep for sentence segmentation
    'custom_stop_words': [
        'document', 'page', 'section', 'chapter', 'paragraph',
        'figure', 'table', 'appendix', 'reference', 'note',
        'iso', 'standard', 'requirement', 'clause', 'subparagraph'
    ]
}

# File processing limits
MAX_FILE_SIZE_MB = 50
SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.doc']

# Caching settings
CACHE_ENABLED = True
CACHE_TIMEOUT_SECONDS = 3600  # 1 hour

# Logging configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'compliance_analysis.log'
}

# Performance monitoring
PERFORMANCE_MONITORING = {
    'enabled': True,
    'metrics': ['processing_time', 'similarity_calculations', 'memory_usage']
}