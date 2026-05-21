from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST

from .models import Tournament, MatchDay, Hole, Score, Player, Team, HoleResult
from .logic import calculate_hole_result, get_current_hole, get_day_totals, get_tournament_totals, fmt_pts


def _base_ctx(tournament, day=None):
    ctx = {'tournament': tournament, 'days': tournament.days.all() if tournament else []}
    if day:
        ctx['day'] = day
    return ctx


def _build_day_statuses(tournament):
    result = []
    for day in tournament.days.all():
        total = day.holes.count()
        done = HoleResult.objects.filter(hole__match_day=day).count()
        if day.is_locked:        status = 'locked'
        elif done == 0:          status = 'pending'
        elif done >= total:      status = 'complete'
        else:                    status = 'in_progress'
        result.append({'day': day, 'status': status, 'done': done, 'total': total})
    return result


def _build_table_ctx(tournament, day, group):
    """
    Contexte pour la page de saisie.
    - team1_all / team2_all : TOUS les joueurs de chaque équipe (tous groupes confondus)
    - group_players : joueurs du groupe actif (pour la logique de validation)
    - player_scores dans visible_holes : scores de TOUS les joueurs
    """
    teams = list(tournament.teams.order_by('order'))
    all_players = list(
        Player.objects.filter(team__tournament=tournament)
        .select_related('team').order_by('team__order', 'order')
    )

    # Tous les joueurs par équipe — colonnes du tableau complet
    team1_all = [p for p in all_players if p.team_id == teams[0].id] if teams else []
    team2_all = [p for p in all_players if p.team_id == teams[1].id] if len(teams) > 1 else []

    # Joueurs du groupe actif seulement (validation)
    group_players = [p for p in all_players if p.saisie_group == group]

    current_hole = get_current_hole(day)

    all_scores = list(Score.objects.filter(hole__match_day=day).select_related('player'))
    scores_map = {(s.hole_id, s.player_id): s.strokes for s in all_scores}
    results_map = {
        r.hole_id: r
        for r in HoleResult.objects.filter(hole__match_day=day).select_related('team1', 'team2')
    }

    visible_holes = []
    for hole in day.holes.all():
        result = results_map.get(hole.id)
        is_current = current_hole is not None and hole.id == current_hole.id
        is_done = result is not None

        if not is_done and not is_current:
            continue

        # Scores de TOUS les joueurs pour ce trou
        player_scores = {p.id: scores_map.get((hole.id, p.id)) for p in all_players}

        # Meilleur score par équipe
        best_pids = {}
        for team in teams:
            team_all = [p for p in all_players if p.team_id == team.id]
            best = None; best_pid = None
            for p in team_all:
                s = scores_map.get((hole.id, p.id))
                if s is not None and (best is None or s < best):
                    best = s; best_pid = p.id
            best_pids[team.id] = best_pid

        # Le groupe actif a-t-il déjà tous ses scores ?
        group_validated = all(
            scores_map.get((hole.id, p.id)) is not None
            for p in group_players
        )

        visible_holes.append({
            'hole': hole,
            'is_current': is_current,
            'is_done': is_done,
            'result': result,
            'player_scores': player_scores,
            'best_pids': best_pids,
            'group_validated': group_validated,
        })

    return {
        'group': group,
        'teams': teams,
        'all_players': all_players,
        'team1_all': team1_all,
        'team2_all': team2_all,
        'group_players': group_players,
        'visible_holes': visible_holes,
        'current_hole': current_hole,
        'stroke_range': range(1, 16),
    }


# ── Home / Setup ──────────────────────────────────────────────────────────────

def home(request):
    tournament = Tournament.get_active()
    if not tournament:
        return redirect('setup')
    return render(request, 'golf/home.html', {
        **_base_ctx(tournament),
        'day_statuses': _build_day_statuses(tournament),
    })


def setup(request):
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
        Player.objects.create(team=usa, name='J1', order=0, saisie_group=1)
        Player.objects.create(team=usa, name='J2', order=1, saisie_group=1)
        Player.objects.create(team=usa, name='J3', order=2, saisie_group=2)
        Player.objects.create(team=eur, name='J4', order=0, saisie_group=1)
        Player.objects.create(team=eur, name='J5', order=1, saisie_group=2)
        for day_num in range(1, t.num_days + 1):
            d = MatchDay.objects.create(tournament=t, day_number=day_num)
            for hole_num in range(1, t.num_holes + 1):
                Hole.objects.create(match_day=d, number=hole_num)
        return redirect('home')
    return render(request, 'golf/setup.html')


# ── Saisie ────────────────────────────────────────────────────────────────────

def saisie(request, day_id, group=1):
    day = get_object_or_404(MatchDay, pk=day_id)
    if day.is_locked:
        return redirect('resultats', day_id=day_id)
    tournament = day.tournament
    ctx = _build_table_ctx(tournament, day, group)
    return render(request, 'golf/saisie.html', {**_base_ctx(tournament, day), **ctx})


def saisie_tbody_partial(request, day_id, group):
    day = get_object_or_404(MatchDay, pk=day_id)
    tournament = day.tournament
    ctx = _build_table_ctx(tournament, day, group)
    return render(request, 'golf/partials/saisie_tbody.html', {**_base_ctx(tournament, day), **ctx})


@require_POST
def update_score(request, hole_id, player_id):
    hole = get_object_or_404(Hole, pk=hole_id)
    player = get_object_or_404(Player, pk=player_id)
    day = hole.match_day

    if day.is_locked:
        return HttpResponseForbidden()
    current_hole = get_current_hole(day)
    if current_hole is None or current_hole.id != hole.id:
        return HttpResponseForbidden()

    strokes_raw = request.POST.get('strokes', '').strip()
    score_obj, _ = Score.objects.get_or_create(hole=hole, player=player)
    if strokes_raw:
        score_obj.strokes = max(1, min(15, int(strokes_raw)))
        score_obj.save()
    else:
        score_obj.strokes = None
        score_obj.save()

    if hole.is_complete():
        calculate_hole_result(hole)

    group = player.saisie_group
    return saisie_tbody_partial(request, day.id, group)


@require_POST
def validate_hole(request, hole_id, group):
    hole = get_object_or_404(Hole, pk=hole_id)
    day = hole.match_day

    if day.is_locked:
        return HttpResponseForbidden()
    current_hole = get_current_hole(day)
    if current_hole is None or current_hole.id != hole.id:
        return HttpResponseForbidden()

    players = Player.objects.filter(team__tournament=day.tournament, saisie_group=group)
    for player in players:
        strokes_raw = request.POST.get(f'score_{player.id}', '').strip()
        if strokes_raw:
            score_obj, _ = Score.objects.get_or_create(hole=hole, player=player)
            score_obj.strokes = max(1, min(15, int(strokes_raw)))
            score_obj.save()

    if hole.is_complete():
        calculate_hole_result(hole)

    return saisie_tbody_partial(request, day.id, group)


# ── Résultats ─────────────────────────────────────────────────────────────────

def resultats(request, day_id):
    day = get_object_or_404(MatchDay, pk=day_id)
    tournament = day.tournament
    teams = list(tournament.teams.order_by('order'))
    players = list(
        Player.objects.filter(team__tournament=tournament)
        .select_related('team').order_by('team__order', 'order')
    )
    all_scores = list(Score.objects.filter(hole__match_day=day).select_related('player__team'))
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
        team_data = []
        for team in teams:
            team_players = [p for p in players if p.team_id == team.id]
            best = None; best_pid = None
            player_scores_list = []
            for p in team_players:
                s = hole_scores.get(p.id)
                player_scores_list.append({'player': p, 'strokes': s})
                if s is not None and (best is None or s < best):
                    best = s; best_pid = p.id
            team_data.append({
                'team': team, 'player_scores': player_scores_list,
                'best': best, 'best_pid': best_pid,
                'points': result.points_for_team(team) if result else None,
            })
        holes_data.append({'hole': hole, 'status': hole.get_status(), 'result': result, 'team_data': team_data})

    day_totals = get_day_totals(day)
    tournament_totals = get_tournament_totals(tournament)
    days_data = [{'day': d, 'totals': get_day_totals(d)} for d in tournament.days.all()]

    return render(request, 'golf/resultats.html', {
        **_base_ctx(tournament, day),
        'teams': teams, 'players': players, 'holes_data': holes_data,
        'day_totals': day_totals, 'tournament_totals': tournament_totals,
        'days_data': days_data, 'fmt_pts': fmt_pts,
    })


# ── Verrouillage ──────────────────────────────────────────────────────────────

@require_POST
def lock_day(request, day_id):
    day = get_object_or_404(MatchDay, pk=day_id)
    day.is_locked = True; day.save()
    return redirect('resultats', day_id=day_id)


@require_POST
def unlock_day(request, day_id):
    day = get_object_or_404(MatchDay, pk=day_id)
    day.is_locked = False; day.save()
    return redirect('resultats', day_id=day_id)


# ── Settings ──────────────────────────────────────────────────────────────────

def settings_view(request):
    tournament = Tournament.get_active()
    if not tournament:
        return redirect('setup')
    return render(request, 'golf/settings.html', {
        **_base_ctx(tournament),
        'teams': list(tournament.teams.order_by('order')),
        'players': list(Player.objects.filter(team__tournament=tournament).select_related('team').order_by('team__order', 'order')),
    })


@require_POST
def settings_save(request):
    tournament = Tournament.get_active()
    if not tournament:
        return redirect('setup')
    tournament.name = request.POST.get('tournament_name', tournament.name).strip()
    tournament.save()
    for team in tournament.teams.all():
        name = request.POST.get(f'team_{team.id}_name', '').strip()
        color = request.POST.get(f'team_{team.id}_color', team.color)
        if name: team.name = name
        team.color = color; team.save()
    for player in Player.objects.filter(team__tournament=tournament):
        name = request.POST.get(f'player_{player.id}_name', '').strip()
        group = request.POST.get(f'player_{player.id}_group', str(player.saisie_group))
        if name: player.name = name
        player.saisie_group = int(group); player.save()
    return redirect('settings')


@require_POST
def reset_tournament(request):
    tournament = Tournament.get_active()
    if tournament:
        Score.objects.filter(hole__match_day__tournament=tournament).delete()
        HoleResult.objects.filter(hole__match_day__tournament=tournament).delete()
        MatchDay.objects.filter(tournament=tournament).update(is_locked=False)
    return redirect('home')