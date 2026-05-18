"""
Logique métier du tournoi de golf.
Toute la logique de calcul est centralisée ici.
"""
from .models import Hole, Score, HoleResult, MatchDay, Tournament, Team


def get_current_hole(match_day: MatchDay):
    """
    Retourne le premier trou sans résultat (trou actif).
    Retourne None si tous les trous sont complétés.
    """
    completed_ids = HoleResult.objects.filter(
        hole__match_day=match_day
    ).values_list('hole_id', flat=True)

    return match_day.holes.exclude(id__in=completed_ids).order_by('number').first()


def calculate_hole_result(hole: Hole):
    """
    Calcule et sauvegarde le résultat d'un trou complété.

    Règles :
    - Meilleur score (min coups) de chaque équipe
    - L'équipe avec le moins de coups gagne (1 pt)
    - Égalité → 0.5 pt chacun

    Retourne HoleResult ou None si le trou n'est pas complet.
    """
    if not hole.is_complete():
        return None

    tournament = hole.match_day.tournament
    teams = list(tournament.teams.order_by('order'))

    if len(teams) < 2:
        return None

    team1, team2 = teams[0], teams[1]

    team1_best = hole.get_best_score_for_team(team1)
    team2_best = hole.get_best_score_for_team(team2)

    if team1_best is None or team2_best is None:
        return None

    if team1_best < team2_best:
        t1_pts, t2_pts = 1.0, 0.0
    elif team2_best < team1_best:
        t1_pts, t2_pts = 0.0, 1.0
    else:
        t1_pts, t2_pts = 0.5, 0.5

    result, _ = HoleResult.objects.update_or_create(
        hole=hole,
        defaults={
            'team1': team1,
            'team2': team2,
            'team1_points': t1_pts,
            'team2_points': t2_pts,
            'team1_best': team1_best,
            'team2_best': team2_best,
        }
    )
    return result


def get_day_totals(match_day: MatchDay) -> dict:
    """
    Retourne {team: points_float} pour la journée.
    """
    tournament = match_day.tournament
    teams = list(tournament.teams.order_by('order'))
    totals = {t: 0.0 for t in teams}

    results = HoleResult.objects.filter(
        hole__match_day=match_day
    ).select_related('team1', 'team2')

    for r in results:
        for t in teams:
            if t.id == r.team1_id:
                totals[t] += r.team1_points
            elif t.id == r.team2_id:
                totals[t] += r.team2_points

    return totals


def get_tournament_totals(tournament: Tournament) -> dict:
    """
    Retourne {team: points_float} cumulés sur toutes les journées.
    """
    teams = list(tournament.teams.order_by('order'))
    totals = {t: 0.0 for t in teams}

    for day in tournament.days.all():
        day_totals = get_day_totals(day)
        for t, pts in day_totals.items():
            totals[t] += pts

    return totals


def fmt_pts(pts: float) -> str:
    """Formatte les points : 1.0 → '1', 0.5 → '0.5'"""
    if pts == int(pts):
        return str(int(pts))
    return str(pts)


def build_hole_live_result(hole: Hole) -> dict | None:
    """
    Retourne un dict avec le résultat partiel du trou en cours
    (meilleur score connu de chaque équipe, même si incomplet).
    Utilisé pour l'affichage live pendant la saisie.
    """
    tournament = hole.match_day.tournament
    teams = list(tournament.teams.order_by('order'))
    if len(teams) < 2:
        return None

    team1, team2 = teams[0], teams[1]
    t1_best = hole.get_best_score_for_team(team1)
    t2_best = hole.get_best_score_for_team(team2)

    winner = None
    if t1_best is not None and t2_best is not None:
        if t1_best < t2_best:
            winner = team1
        elif t2_best < t1_best:
            winner = team2
        else:
            winner = 'tie'

    return {
        'team1': team1,
        'team2': team2,
        'team1_best': t1_best,
        'team2_best': t2_best,
        'winner': winner,
    }
