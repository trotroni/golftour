from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST

from .models import Tournament, MatchDay, Hole, Score, Player, Team, HoleResult
from .logic import (
    calculate_hole_result, get_current_hole,
    get_day_totals, get_tournament_totals, build_hole_live_result, fmt_pts
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _base_ctx(tournament, day=None):
    """Contexte commun à toutes les vues."""
    ctx = {
        'tournament': tournament,
        'days': tournament.days.all() if tournament else [],
    }
    if day:
        ctx['day'] = day
    return ctx


# ─── Setup ────────────────────────────────────────────────────────────────────

def home(request):
    tournament = Tournament.get_active()
    if not tournament:
        return redirect('setup')
    return render(request, 'golf/home.html', {
        **_base_ctx(tournament),
        'day_statuses': _build_day_statuses(tournament),
    })


def _build_day_statuses(tournament):
    """Construit la liste des jours avec leur statut pour la home."""
    result = []
    for day in tournament.days.all():
        total = day.holes.count()
        done = HoleResult.objects.filter(hole__match_day=day).count()
        if day.is_locked:
            status = 'locked'
        elif done == 0:
            status = 'pending'
        elif done >= total:
            status = 'complete'
        else:
            status = 'in_progress'
        result.append({'day': day, 'status': status, 'done': done, 'total': total})
    return result


def setup(request):
    """Crée le tournoi initial si aucun n'existe."""
    if Tournament.objects.exists():
        return redirect('home')

    if request.method == 'POST':
        t = Tournament.objects.create(
            name=request.POST.get('name', 'Golf Tournament'),
            num_days=int(request.POST.get('num_days', 3)),
            num_holes=int(request.POST.get('num_holes', 18)),
        )

        usa = Team.objects.create(tournament=t, name='USA', color='#2563eb', order=0)
        eur = Team.objects.create(tournament=t, name='EUR', color='#dc2626', order=1)

        # J1, J2 USA → groupe 1 ; J3 USA → groupe 2
        Player.objects.create(team=usa, name='J1', order=0, saisie_group=1)
        Player.objects.create(team=usa, name='J2', order=1, saisie_group=1)
        Player.objects.create(team=usa, name='J3', order=2, saisie_group=2)
        # J4 EUR → groupe 1 ; J5 EUR → groupe 2
        Player.objects.create(team=eur, name='J4', order=0, saisie_group=1)
        Player.objects.create(team=eur, name='J5', order=1, saisie_group=2)

        for day_num in range(1, t.num_days + 1):
            day = MatchDay.objects.create(tournament=t, day_number=day_num)
            for hole_num in range(1, t.num_holes + 1):
                Hole.objects.create(match_day=day, number=hole_num)

        return redirect('home')

    return render(request, 'golf/setup.html')


# ─── Saisie ───────────────────────────────────────────────────────────────────

def saisie(request, day_id, group):
    """Page de saisie pour le groupe 1 ou 2."""
    day = get_object_or_404(MatchDay, pk=day_id)
    tournament = day.tournament

    if day.is_locked:
        return redirect('resultats', day_id=day_id)

    current_hole = get_current_hole(day)
    if current_hole is None:
        # Tous les trous sont complétés → résultats
        return redirect('resultats', day_id=day_id)

    ctx = _build_saisie_ctx(tournament, day, current_hole, group)
    return render(request, 'golf/saisie.html', {
        **_base_ctx(tournament, day),
        **ctx,
    })


def _build_saisie_ctx(tournament, day, hole, group):
    """Construit le contexte pour la saisie (utilisé aussi par le partial HTMX)."""
    players = list(
        Player.objects.filter(
            team__tournament=tournament,
            saisie_group=group
        ).select_related('team').order_by('team__order', 'order')
    )

    scores_map = {
        s.player_id: s
        for s in Score.objects.filter(hole=hole, player__in=players)
    }

    player_data = []
    for p in players:
        s = scores_map.get(p.id)
        player_data.append({
            'player': p,
            'strokes': s.strokes if s else None,
        })

    all_players_count = tournament.teams.first().players.count() + \
        tournament.teams.last().players.count() \
        if tournament.teams.count() >= 2 else 0
    all_players = Player.objects.filter(team__tournament=tournament)
    all_players_count = all_players.count()
    submitted_count = Score.objects.filter(
        hole=hole, strokes__isnull=False
    ).count()

    live = build_hole_live_result(hole)

    return {
        'group': group,
        'current_hole': hole,
        'player_data': player_data,
        'submitted_count': submitted_count,
        'total_players': all_players_count,
        'hole_complete': hole.is_complete(),
        'live': live,
    }


def saisie_form_partial(request, hole_id, group):
    """
    Partial HTMX : retourne uniquement le formulaire de saisie mis à jour.
    Appelé après chaque modification de score.
    """
    hole = get_object_or_404(Hole, pk=hole_id)
    day = hole.match_day
    tournament = day.tournament

    ctx = _build_saisie_ctx(tournament, day, hole, group)
    return render(request, 'golf/partials/saisie_form.html', {
        **_base_ctx(tournament, day),
        **ctx,
    })


@require_POST
def update_score(request, hole_id, player_id):
    """
    Endpoint HTMX : met à jour le score d'un joueur.
    Retourne le formulaire de saisie mis à jour.
    """
    hole = get_object_or_404(Hole, pk=hole_id)
    player = get_object_or_404(Player, pk=player_id)
    day = hole.match_day

    # Vérifications de sécurité
    if day.is_locked:
        return HttpResponseForbidden("Journée verrouillée")

    # Contrainte séquentielle : on ne peut modifier que le trou actif
    current_hole = get_current_hole(day)
    if current_hole is None or current_hole.id != hole.id:
        return HttpResponseForbidden("Ce trou n'est plus modifiable")

    # Lecture des paramètres
    delta = request.POST.get('delta')
    strokes_raw = request.POST.get('strokes')

    score_obj, _ = Score.objects.get_or_create(hole=hole, player=player)

    if strokes_raw is not None:
        new_strokes = int(strokes_raw)
    elif delta is not None:
        current = score_obj.strokes if score_obj.strokes is not None else 4
        new_strokes = current + int(delta)
    else:
        new_strokes = 4

    # Clamp 1–15
    new_strokes = max(1, min(15, new_strokes))
    score_obj.strokes = new_strokes
    score_obj.save()

    # Calcul automatique si le trou est complet
    if hole.is_complete():
        calculate_hole_result(hole)

    # Retourner le partial mis à jour
    return saisie_form_partial(request, hole_id, player.saisie_group)


# ─── Résultats ────────────────────────────────────────────────────────────────

def resultats(request, day_id):
    """Page de résultats globaux."""
    day = get_object_or_404(MatchDay, pk=day_id)
    tournament = day.tournament
    teams = list(tournament.teams.order_by('order'))
    players = list(
        Player.objects.filter(team__tournament=tournament)
        .select_related('team')
        .order_by('team__order', 'order')
    )

    # Pré-charger tous les scores et résultats de la journée
    all_scores = list(
        Score.objects.filter(hole__match_day=day)
        .select_related('player__team')
    )
    scores_by_hole = {}
    for s in all_scores:
        scores_by_hole.setdefault(s.hole_id, {})[s.player_id] = s.strokes

    results_by_hole = {
        r.hole_id: r
        for r in HoleResult.objects.filter(hole__match_day=day).select_related('team1', 'team2')
    }

    holes_data = []
    for hole in day.holes.all():
        hole_scores = scores_by_hole.get(hole.id, {})
        result = results_by_hole.get(hole.id)
        status = hole.get_status()

        team_data = []
        for team in teams:
            team_players = [p for p in players if p.team_id == team.id]
            best = None
            best_pid = None
            player_scores = []
            for p in team_players:
                s = hole_scores.get(p.id)
                player_scores.append({'player': p, 'strokes': s})
                if s is not None and (best is None or s < best):
                    best = s
                    best_pid = p.id

            pts = None
            if result:
                pts = result.points_for_team(team)

            team_data.append({
                'team': team,
                'player_scores': player_scores,
                'best': best,
                'best_pid': best_pid,
                'points': pts,
            })

        holes_data.append({
            'hole': hole,
            'status': status,
            'result': result,
            'team_data': team_data,
        })

    day_totals = get_day_totals(day)
    tournament_totals = get_tournament_totals(tournament)

    # Toutes les journées avec leurs totaux
    days_data = []
    for d in tournament.days.all():
        dt = get_day_totals(d)
        days_data.append({'day': d, 'totals': dt})

    return render(request, 'golf/resultats.html', {
        **_base_ctx(tournament, day),
        'teams': teams,
        'players': players,
        'holes_data': holes_data,
        'day_totals': day_totals,
        'tournament_totals': tournament_totals,
        'days_data': days_data,
        'fmt_pts': fmt_pts,
    })


# ─── Verrouillage ─────────────────────────────────────────────────────────────

@require_POST
def lock_day(request, day_id):
    day = get_object_or_404(MatchDay, pk=day_id)
    day.is_locked = True
    day.save()
    return redirect('resultats', day_id=day_id)


@require_POST
def unlock_day(request, day_id):
    day = get_object_or_404(MatchDay, pk=day_id)
    day.is_locked = False
    day.save()
    return redirect('resultats', day_id=day_id)


# ─── Settings ─────────────────────────────────────────────────────────────────

def settings_view(request):
    tournament = Tournament.get_active()
    if not tournament:
        return redirect('setup')

    teams = list(tournament.teams.order_by('order'))
    players = list(
        Player.objects.filter(team__tournament=tournament)
        .select_related('team')
        .order_by('team__order', 'order')
    )

    return render(request, 'golf/settings.html', {
        **_base_ctx(tournament),
        'teams': teams,
        'players': players,
    })


@require_POST
def settings_save(request):
    tournament = Tournament.get_active()
    if not tournament:
        return redirect('setup')

    # Tournoi
    tournament.name = request.POST.get('tournament_name', tournament.name).strip()
    tournament.save()

    # Équipes
    for team in tournament.teams.all():
        name = request.POST.get(f'team_{team.id}_name', '').strip()
        color = request.POST.get(f'team_{team.id}_color', team.color)
        if name:
            team.name = name
        team.color = color
        team.save()

    # Joueurs
    for player in Player.objects.filter(team__tournament=tournament):
        name = request.POST.get(f'player_{player.id}_name', '').strip()
        group = request.POST.get(f'player_{player.id}_group', str(player.saisie_group))
        if name:
            player.name = name
        player.saisie_group = int(group)
        player.save()

    return redirect('settings')


@require_POST
def reset_tournament(request):
    """Réinitialise complètement les scores (sans supprimer la structure)."""
    tournament = Tournament.get_active()
    if not tournament:
        return redirect('setup')

    Score.objects.filter(hole__match_day__tournament=tournament).delete()
    HoleResult.objects.filter(hole__match_day__tournament=tournament).delete()
    MatchDay.objects.filter(tournament=tournament).update(is_locked=False)

    return redirect('home')
