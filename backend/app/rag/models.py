from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class KnowledgeChunk:

    tipo: str

    fuente: str

    referencia_id: str

    contenido: str

    metadata: dict[str, Any] = field(default_factory=dict)

    embedding: list[float] | None = None

    similarity: float | None = None

    created_at: datetime | None = None


@dataclass(slots=True)
class KnowledgeSource:

    nombre: str

    tipo: str

    origen_tabla: str

    origen_id: str

    version: int = 1

    checksum: str | None = None

    activo: bool = True

    updated_at: datetime | None = None