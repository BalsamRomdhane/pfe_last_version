from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    verbose_name = 'AI / Machine Learning'

    def ready(self):
        """Import signals when app is ready + warmup background tasks."""
        import api.signals  # noqa

        # ── Warmup asynchrone au démarrage ────────────────────────────────
        # Lancé dans un thread daemon pour ne pas bloquer le démarrage Daphne.
        # Objectif : réduire la latence des PREMIÈRES requêtes chat.
        #
        # 1. Charger le modèle SentenceTransformer en mémoire (évite 2-3s au 1er appel)
        # 2. Charger l'index FAISS en cache mémoire (évite 180ms au 1er appel)
        # 3. Pinger Ollama pour pré-chauffer le keep_alive et vérifier la disponibilité
        import threading
        t = threading.Thread(target=_warmup_chat_pipeline, daemon=True, name='chat-warmup')
        t.start()


def _warmup_chat_pipeline() -> None:
    """
    Préchauffage du pipeline chat dans un thread daemon.
    Exécuté une seule fois au démarrage du process Daphne.
    Toutes les erreurs sont silencieuses — ne jamais bloquer le démarrage.
    """
    import logging
    import time
    log = logging.getLogger('api.warmup')

    # Laisser Django finir son initialisation complète
    time.sleep(3)

    # 1. Charger le modèle SentenceTransformer
    try:
        from ml.search import _get_sentence_transformer, EMBEDDING_MODEL_NAME
        _get_sentence_transformer(EMBEDDING_MODEL_NAME)
        log.info('[warmup] SentenceTransformer loaded into cache')
    except Exception as exc:
        log.debug('[warmup] SentenceTransformer not available: %s', exc)

    # 2. Charger l'index FAISS en cache mémoire
    try:
        from ml.search import load_evidence_index
        load_evidence_index()
        log.info('[warmup] FAISS evidence index loaded into memory cache')
    except Exception as exc:
        log.debug('[warmup] FAISS index not available yet: %s', exc)

    # 3. Pré-chauffer Ollama avec keep_alive pour garder le modèle en GPU/RAM
    try:
        from services.llm_service import _get_session, OLLAMA_URL, OLLAMA_MODEL, _OLLAMA_OPTIONS
        resp = _get_session().post(
            f'{OLLAMA_URL}/api/generate',
            json={
                'model':      OLLAMA_MODEL,
                'prompt':     '',          # prompt vide — juste pour charger le modèle
                'stream':     False,
                'keep_alive': '-1',        # garder en mémoire indéfiniment
                'options':    _OLLAMA_OPTIONS,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            log.info('[warmup] Ollama model "%s" warmed up (keep_alive=-1)', OLLAMA_MODEL)
        else:
            log.debug('[warmup] Ollama warmup returned %s', resp.status_code)
    except Exception as exc:
        log.debug('[warmup] Ollama not available for warmup: %s', exc)

