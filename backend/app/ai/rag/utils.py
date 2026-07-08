from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_text(text: str) -> str:

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def json_hash(data: dict[str, Any]) -> str:

    text = json.dumps(

        data,

        sort_keys=True,

        ensure_ascii=False,

    )

    return sha256_text(text)