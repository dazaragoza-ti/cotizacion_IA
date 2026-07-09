"""
Configuración del módulo RAG.

Toda la configuración relacionada con embeddings,
búsqueda vectorial y sincronización vive aquí.

No deben existir valores "hardcodeados" en el resto
del proyecto.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class RagSettings(BaseSettings):
    # ===============================
    # Embeddings
    # ===============================

    EMBEDDING_PROVIDER: str = "voyage"

    EMBEDDING_MODEL: str = "text-embedding-3-small"

    EMBEDDING_DIMENSIONS: int = 1024  # voyage-3.5 (si usas openai/text-embedding-3-small, cambia a 1536)

    EMBEDDING_BATCH_SIZE: int = 64

    EMBEDDING_MAX_RETRIES: int = 3

    EMBEDDING_TIMEOUT: int = 60

    # ===============================
    # Vector Search
    # ===============================

    VECTOR_MATCH_COUNT: int = 10

    VECTOR_MIN_SCORE: float = 0.70

    # ===============================
    # Chunking
    # ===============================

    CHUNK_SIZE: int = 1000

    CHUNK_OVERLAP: int = 150

    # ===============================
    # Cache
    # ===============================

    ENABLE_CACHE: bool = True

    CACHE_TTL_SECONDS: int = 3600

    # ===============================
    # Sync
    # ===============================

    ENABLE_INCREMENTAL_SYNC: bool = True

    DELETE_OLD_CHUNKS: bool = True

    # ===============================
    # Logging
    # ===============================

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_rag_settings() -> RagSettings:
    return RagSettings()