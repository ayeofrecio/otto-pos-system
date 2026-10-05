from django import template

from sales.color_lookup import get_color_description
from sales.size_lookup import get_size_description

register = template.Library()

DISCOUNT_TYPES = [
    {"code": "REG", "label": "Regular",        "pct": 0,  "button": "Regular %"},
    {"code": "SC",  "label": "Senior Citizen", "pct": 20, "button": "Senior Citizen (20%)"},
    {"code": "PWD", "label": "PWD",            "pct": 20, "button": "PWD (20%)"},
    {"code": "EMP", "label": "Employee",       "pct": 10, "button": "Employee (10%)"},
]
DENOMINATIONS = [1000, 500, 200, 100, 50, 20, 10, 5, 1]


@register.simple_tag
def denominations():
    return [{"value": str(d), "label": f"₱{d:,}"} for d in DENOMINATIONS]

@register.simple_tag
def discount_types():
    return DISCOUNT_TYPES

@register.simple_tag
def size_display(item_size):
    """Human-readable size label from SIZES master."""
    return get_size_description(item_size or "")


@register.simple_tag
def color_display(item_color, item_code, item_size):
    """Human-readable color label (handles 90–99 multi-color via ItemDetail.multi)."""
    return get_color_description(
        item_color or "",
        icode=item_code or "",
        size=item_size if item_size is not None else "",
    )