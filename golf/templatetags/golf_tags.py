from django import template
from golf.logic import fmt_pts

register = template.Library()


@register.filter
def format_pts(value):
    """Formate un float de points : 1.0 → '1', 0.5 → '0.5'"""
    if value is None:
        return '–'
    try:
        return fmt_pts(float(value))
    except (TypeError, ValueError):
        return '–'


@register.filter
def team_pts(totals_dict, team):
    """Extrait les points d'une équipe depuis le dict {team: pts}"""
    val = totals_dict.get(team, 0.0)
    return fmt_pts(val)


@register.simple_tag
def status_label(status):
    labels = {
        'pending': 'Non commencé',
        'in_progress': 'En cours',
        'done': 'Terminé',
    }
    return labels.get(status, status)
