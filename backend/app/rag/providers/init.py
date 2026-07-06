from app.rag.config import get_rag_settings

from app.rag.providers.openai_provider import (
    OpenAIEmbeddingProvider
)

from app.rag.providers.ollama_provider import (
    OllamaEmbeddingProvider
)

from app.rag.providers.voyage_provider import (
    VoyageEmbeddingProvider
)


cfg = get_rag_settings()


def get_provider():

    if cfg.EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddingProvider()

    if cfg.EMBEDDING_PROVIDER == "ollama":
        return OllamaEmbeddingProvider()

    if cfg.EMBEDDING_PROVIDER == "voyage":
        return VoyageEmbeddingProvider()

    raise Exception(
        "Proveedor de embeddings desconocido."
    )