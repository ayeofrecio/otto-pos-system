from django import template

from sales.color_lookup import get_color_description
from sales.size_lookup import get_size_description

register = template.Library()


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
