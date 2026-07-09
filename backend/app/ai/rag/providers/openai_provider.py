import os
from typing import List

from openai import OpenAI

from app.ai.rag.config import get_rag_settings
from app.ai.rag.providers.base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):

    def __init__(self):

        self.cfg = get_rag_settings()

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta OPENAI_API_KEY en el .env — necesaria para el proveedor "
                "de embeddings 'openai' (EMBEDDING_PROVIDER=openai en config.py)."
            )

        self.client = OpenAI(api_key=api_key)

    def embed_text(
        self,
        text: str
    ) -> List[float]:

        response = self.client.embeddings.create(

            model=self.cfg.EMBEDDING_MODEL,

            input=text

        )

        return response.data[0].embedding

    def embed_documents(

        self,

        docs: List[str]

    ) -> List[List[float]]:

        response = self.client.embeddings.create(

            model=self.cfg.EMBEDDING_MODEL,

            input=docs

        )

        return [

            item.embedding

            for item in response.data

        ]