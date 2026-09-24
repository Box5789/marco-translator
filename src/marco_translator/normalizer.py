from __future__ import annotations

import re
import unicodedata


_SPACE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Conservative normalization only.

    Do not rewrite lexical meaning here. OCR-specific corrections belong to a
    versioned input profile so they can be audited separately from semantics.
    """
    value = unicodedata.normalize("NFKC", text or "")
    value = _SPACE.sub(" ", value).strip()
    return value
