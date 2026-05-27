# Système d'Analyse de Conformité Documentaire - NLP Classique

## Vue d'ensemble

Ce système implémente une analyse intelligente de conformité documentaire basée sur des techniques classiques de NLP et Machine Learning, sans utiliser de LLM ou d'API externes. Il détecte automatiquement si un document respecte les règles ISO à partir d'une analyse sémantique du contenu.

## Architecture

### Pipeline NLP

1. **Extraction de texte**
   - PDF : `pdfplumber`
   - DOCX : `python-docx`

2. **Prétraitement**
   - Nettoyage du texte
   - Tokenization (NLTK)
   - Suppression des stop words
   - Lemmatization (NLTK/spaCy)
   - Segmentation en phrases

3. **Représentation sémantique**
   - TF-IDF (scikit-learn)
   - Word2Vec (gensim)
   - FastText (gensim)
   - spaCy embeddings

4. **Analyse de similarité**
   - Cosine similarity
   - Nearest neighbors
   - Distance vectorielle

5. **Scoring et décision**
   - Règles détectées/manquantes
   - Score de conformité (0-100%)
   - Seuil de similarité configurable

## Structure des dossiers

```
backend/ml/
├── __init__.py
├── services.py              # Service principal
├── extractors/              # Extraction de texte
│   └── __init__.py
├── preprocessors/           # Prétraitement NLP
│   └── __init__.py
├── vectorizers/             # Vectorisation sémantique
│   └── __init__.py
├── analyzers/               # Analyse de conformité
│   └── __init__.py
├── models/                  # Modèles entraînés sauvegardés
├── train.py                 # Entraînement existant
├── train_models.py          # Entraînement existant
└── search.py                # Recherche sémantique existante
```

## API Endpoints

### Analyse de conformité

- `POST /api/compliance/analyze/`
  - Analyse un document (texte ou fichier)
  - Retourne : règles détectées, manquantes, score, matches

- `GET /api/compliance/standards/`
  - Liste des standards ISO supportés

- `GET /api/compliance/rules/{standard}/`
  - Règles d'un standard spécifique

### Administration

- `POST /api/compliance/retrain/`
  - Réentraîne les modèles pour un standard

- `POST /api/compliance/threshold/`
  - Met à jour le seuil de similarité

- `GET /api/compliance/status/`
  - Statut du service

## Format de réponse

```json
{
  "standard": "ISO9001",
  "detected_rules": ["iso9001_1", "iso9001_3"],
  "missing_rules": ["iso9001_2", "iso9001_4"],
  "compliance_score": 67,
  "matches": [
    {
      "rule_id": "iso9001_1",
      "rule_text": "Identification du document",
      "sentence": "Le document doit être clairement identifié...",
      "similarity": 0.85
    }
  ],
  "total_sentences_analyzed": 45
}
```

## Installation et configuration

### Dépendances

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Téléchargement des ressources NLTK

```python
import nltk
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')
```

### Entraînement initial

```python
from ml.services import compliance_service
result = compliance_service.retrain_models('ISO9001')
```

## Optimisations de performance

### Stockage des vecteurs
- Les vecteurs TF-IDF sont sauvegardés dans `ml/models/`
- Cache des règles vectorisées en mémoire
- Rechargement automatique des modèles

### Gestion des seuils
- Seuil de similarité configurable (défaut : 0.4)
- Réduction des faux positifs par ajustement du seuil
- Métriques de précision/rappel

### Scalabilité
- Traitement par lots pour grands documents
- Vectorisation incrémentale
- Cache intelligent des calculs de similarité

## Bonnes pratiques NLP/ML

### Prétraitement
- Utilisation de spaCy pour la lemmatization avancée
- Conservation de la ponctuation pour la segmentation
- Filtrage des phrases trop courtes

### Vectorisation
- TF-IDF pour la similarité terme-document
- Word2Vec/FastText pour le contexte sémantique
- Combinaison de plusieurs méthodes

### Évaluation
- Métriques : précision, rappel, F1-score
- Validation croisée sur les données d'entraînement
- Tests A/B pour l'optimisation des seuils

## Workflow détaillé

1. **Upload du document**
   - Extraction automatique du texte
   - Validation du format (PDF/DOCX)

2. **Prétraitement**
   - Nettoyage et normalisation
   - Segmentation en unités sémantiques

3. **Analyse sémantique**
   - Comparaison avec les règles ISO
   - Calcul des similarités

4. **Génération du rapport**
   - Score global de conformité
   - Détail des règles détectées/manquantes
   - Extraits pertinents du document

5. **Intégration workflow**
   - Mise à jour du statut du document
   - Création d'échantillons d'entraînement
   - Notifications aux validateurs

## Métriques et monitoring

- **Performance** : Temps de traitement moyen
- **Qualité** : Taux de détection des règles
- **Fiabilité** : Taux de faux positifs/négatifs
- **Utilisation** : Nombre d'analyses par jour

## Extension et évolution

### Nouveaux standards
- Ajout de règles dans `api/models.py`
- Réentraînement automatique des modèles

### Amélioration de la précision
- Fine-tuning des seuils par standard
- Enrichissement du corpus d'entraînement
- Utilisation de techniques d'ensemble

### Intégration avancée
- API asynchrone pour les gros documents
- Cache distribué (Redis)
- Interface d'administration pour les seuils

## Tests et validation

### Tests unitaires
- Validation de chaque étape du pipeline
- Tests de performance
- Tests de régression

### Jeux de données de test
- Documents de référence par standard
- Cas limites (documents mal formatés)
- Métriques de qualité attendues

## Sécurité et conformité

- **Confidentialité** : Traitement local uniquement
- **Intégrité** : Validation des entrées
- **Audit** : Logs des analyses effectuées
- **Conformité RGPD** : Pas de données externes

---

*Ce système représente une solution professionnelle et académique pour l'analyse documentaire automatisée, adaptée aux contraintes industrielles et éducatives.*