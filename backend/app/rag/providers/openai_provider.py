from typing import List

from openai import OpenAI

from app.config import settings
from app.rag.config import get_rag_settings
from app.rag.providers.base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):

    def __init__(self):

        self.cfg = get_rag_settings()

        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY
        )

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