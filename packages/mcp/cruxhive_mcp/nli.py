"""Optional NLI faithfulness checker.

Model: cross-encoder/nli-deberta-v3-small (~82 MB, Apache 2.0)
Install: pip install cruxhive-mcp[full]
Runs post-session async. ~400 ms for 3-5 constraints on CPU.
Graceful no-op if sentence-transformers is not installed.
"""
from __future__ import annotations

_model = None
_available: bool | None = None  # None = not yet tried

# DeBERTa NLI label order returned by CrossEncoder with apply_softmax=True:
# index 0 = contradiction, index 1 = entailment, index 2 = neutral
_CONTRADICTION = 0


def _load() -> bool:
    global _model, _available
    if _available is not None:
        return _available
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import]

        _model = CrossEncoder("cross-encoder/nli-deberta-v3-small")
        _available = True
    except Exception:
        _available = False
    return _available  # type: ignore[return-value]


def is_available() -> bool:
    return _load()


def check(response: str, constraints: list[str], threshold: float = 0.7) -> list[dict]:
    """Return list of constraints the response likely contradicts.

    Each violation: {"constraint": str, "score": float, "severity": "high"|"medium"}
    Returns [] if model not available or no violations found.
    """
    if not _load() or _model is None or not constraints:
        return []

    pairs = [(response[:2048], c[:512]) for c in constraints]
    try:
        scores = _model.predict(pairs, apply_softmax=True)
    except Exception:
        return []

    violations = []
    for score_row, constraint in zip(scores, constraints):
        if hasattr(score_row, "__iter__"):
            c_score = float(score_row[_CONTRADICTION])
        else:
            c_score = float(score_row)
        if c_score >= threshold:
            violations.append({
                "constraint": constraint[:120] + ("…" if len(constraint) > 120 else ""),
                "score": round(c_score, 3),
                "severity": "high" if c_score >= 0.9 else "medium",
            })
    return violations


def check_conflicts(
    candidate: str,
    approved_entries: list[dict],
    threshold: float = 0.7,
) -> list[dict]:
    """Check whether a candidate entry contradicts any approved entry.

    approved_entries: list of {"path": str, "content": str, ...}
    Returns: [{"path": str, "score": float, "severity": ..., "preview": str}]
    """
    if not _load() or _model is None or not approved_entries or not candidate:
        return []

    pairs = [(candidate[:2048], (e.get("content") or "")[:512]) for e in approved_entries]
    try:
        scores = _model.predict(pairs, apply_softmax=True)
    except Exception:
        return []

    conflicts = []
    for score_row, entry in zip(scores, approved_entries):
        if hasattr(score_row, "__iter__"):
            c_score = float(score_row[_CONTRADICTION])
        else:
            c_score = float(score_row)
        if c_score >= threshold:
            preview = (entry.get("content") or "").strip().replace("\n", " ")[:120]
            conflicts.append({
                "path": entry.get("path", "?"),
                "topic": entry.get("topic"),
                "score": round(c_score, 3),
                "severity": "high" if c_score >= 0.9 else "medium",
                "preview": preview + ("…" if len(preview) >= 120 else ""),
            })
    return conflicts
