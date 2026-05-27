"""Optional Nomic Embed v1.5 wrapper.

Install: pip install cruxhive-mcp[full]
Downloads ~270 MB on first use (cached in ~/.cache/huggingface/).
Graceful no-op if sentence-transformers is not installed.
"""
from __future__ import annotations

import struct

_model = None
_available: bool | None = None  # None = not yet tried


def _load() -> bool:
    global _model, _available
    if _available is not None:
        return _available
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]

        _model = SentenceTransformer(
            "nomic-ai/nomic-embed-text-v1.5",
            trust_remote_code=True,
        )
        _available = True
    except Exception:
        _available = False
    return _available  # type: ignore[return-value]


def is_available() -> bool:
    return _load()


def encode_bytes(text: str) -> bytes | None:
    """Encode text → 768-dim float32 vector as raw bytes for sqlite-vec. None if unavailable."""
    if not _load() or _model is None:
        return None
    vec = _model.encode(text, normalize_embeddings=True).tolist()
    return struct.pack(f"{len(vec)}f", *vec)


def encode_list(text: str) -> list[float] | None:
    """Encode text → list of floats. None if unavailable."""
    if not _load() or _model is None:
        return None
    return _model.encode(text, normalize_embeddings=True).tolist()
