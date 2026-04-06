"""
Resolve size codes to SIZES.size display text (Clarion SIZES table).
"""

from __future__ import annotations


def _normalize_size_code(size_code: str) -> str:
    return (size_code or "").strip()


def _lookup_size_master_name(size_code: str) -> str:
    """Return SIZES.size for this code, trying common key shapes."""
    from sales.models import Size

    c = _normalize_size_code(size_code)
    if not c:
        return ""
    for candidate in (c, c.zfill(3)):
        row = Size.objects.filter(code=candidate).values_list("size", flat=True).first()
        if row is not None:
            return (row or "").strip()
    return ""


def get_size_description(size_code: str) -> str:
    """Human-readable size label, or the raw code if not in the master table."""
    normalized = _normalize_size_code(size_code)
    if not normalized:
        return ""
    label = _lookup_size_master_name(normalized)
    return label or normalized
