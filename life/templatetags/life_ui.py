from django import template


register = template.Library()


def get_importance_level(value):
    """Convert the stored 0-100 importance into the four-level UI scale."""
    try:
        importance = float(value)
    except (TypeError, ValueError):
        importance = 0

    if importance <= 20:
        return 1
    if importance <= 50:
        return 2
    if importance <= 80:
        return 3
    return 4


@register.inclusion_tag("life/partials/importance_stars.html")
def importance_stars(value):
    level = get_importance_level(value)
    return {
        "level": level,
        "stars": [position <= level for position in range(1, 5)],
    }
