from app.ai.rag.config import get_rag_settings

cfg = get_rag_settings()


def get_provider():
    """
    Imports diferidos a propósito: si usas 'voyage', no hace falta tener
    instalado el paquete `openai` (y viceversa) — cada proveedor solo se
    importa cuando de verdad se selecciona.
    """
    if cfg.EMBEDDING_PROVIDER == "openai":
        from app.ai.rag.providers.openai_provider import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider()

    if cfg.EMBEDDING_PROVIDER == "ollama":
        from app.ai.rag.providers.ollama_provider import OllamaEmbeddingProvider
        return OllamaEmbeddingProvider()

    if cfg.EMBEDDING_PROVIDER == "voyage":
        from app.ai.rag.providers.voyage_provider import VoyageEmbeddingProvider
        return VoyageEmbeddingProvider()

    raise Exception(
        "Proveedor de embeddings desconocido."
    )