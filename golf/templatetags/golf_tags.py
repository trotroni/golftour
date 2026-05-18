from django import template
from golf.logic import fmt_pts

register = template.Library()


@register.filter
def format_pts(value):
    if value is None:
        return '–'
    try:
        return fmt_pts(float(value))
    except (TypeError, ValueError):
        return '–'


@register.filter
def team_pts(totals_dict, team):
    val = totals_dict.get(team, 0.0)
    return fmt_pts(val)


@register.filter
def dict_get(d, key):
    """Accès dict dans un template : {{ my_dict|dict_get:key }}"""
    if d is None:
        return None
    return d.get(key)


@register.simple_tag
def status_label(status):
    labels = {'pending': 'Non commencé', 'in_progress': 'En cours', 'done': 'Terminé'}
    return labels.get(status, status)
