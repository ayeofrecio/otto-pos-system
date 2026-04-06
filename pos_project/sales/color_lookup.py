"""
Clipper GetColorDesc-style color labels: codes whose last two digits are 90–99
use ItemDetail.multi; otherwise use the Color master table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sales.models import ItemDetail


def _normalize_color_code(color_code: str) -> str:
    return (color_code or "").strip()


def is_multi_color_code(color_code: str) -> bool:
    s = _normalize_color_code(color_code)
    if len(s) < 2:
        return False
    tail = s[-2:]
    if not tail.isdigit():
        return False
    v = int(tail)
    return 90 <= v <= 99


def _lookup_color_master_name(color_code: str) -> str:
    """Return COLORS.color for this code, trying a few key shapes."""
    from sales.models import Color

    c = _normalize_color_code(color_code)
    if not c:
        return ""
    for candidate in (c, c.zfill(3), c.zfill(5), c.ljust(5)[:5]):
        row = Color.objects.filter(code=candidate).values_list("color", flat=True).first()
        if row is not None:
            return (row or "").strip()
    return ""


def get_color_description(
    color_code: str,
    *,
    item_detail: Optional["ItemDetail"] = None,
    icode: Optional[str] = None,
    size: Optional[str] = None,
) -> str:
    """
    Resolve display text for a color code.
    Sub-case B: pass item_detail when iterating ItemDetail rows.
    Sub-case A: pass icode + size (+ color_code) for precise ITMDTL seek.
    """
    normalized = _normalize_color_code(color_code)
    base = _lookup_color_master_name(normalized)

    if not is_multi_color_code(normalized):
        return base or normalized

    multi_text = ""
    if item_detail is not None:
        multi_text = (getattr(item_detail, "multi", None) or "").strip()
    elif icode:
        from sales.models import ItemDetail

        sz = "" if size is None else size
        row = (
            ItemDetail.objects.filter(icode=icode, color=normalized, size=sz)
            .only("multi")
            .first()
        )
        if row:
            multi_text = (row.multi or "").strip()

    if multi_text:
        return multi_text
    return base or normalized
