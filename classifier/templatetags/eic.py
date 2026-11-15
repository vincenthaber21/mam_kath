from django import template

from classifier.labels import LABEL_SHORT, label_name as _label_name

register = template.Library()


@register.filter
def pct(value, digits=1):
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value) * 100:.{int(digits)}f}%"
    except (TypeError, ValueError):
        return "—"


@register.filter
def fixed2(value):
    if value is None or value == "":
        return "—"
    return f"{float(value):.2f}"


@register.filter
def ms(value):
    if value is None or value == "":
        return "—"
    return f"{round(float(value))} ms"


@register.filter
def label_name(value):
    return _label_name(value)


@register.filter
def label_short(value):
    return LABEL_SHORT.get(value, value)


@register.filter
def width_pct(value):
    """0-1 score -> CSS width percentage, clamped."""
    try:
        v = max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        v = 0.0
    return f"{v * 100:.1f}"


@register.filter
def thousands(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


@register.simple_tag
def cell_shade(value, maximum):
    """Background opacity for a confusion-matrix cell."""
    try:
        return f"{(float(value) / max(1.0, float(maximum))) * 0.85:.2f}"
    except (TypeError, ValueError):
        return "0"
