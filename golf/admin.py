from django.contrib import admin
from .models import Tournament, Team, Player, MatchDay, Hole, Score, HoleResult


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ['name', 'num_days', 'num_holes']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'tournament', 'color', 'order']


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'team', 'order', 'saisie_group']
    list_filter = ['team', 'saisie_group']


@admin.register(MatchDay)
class MatchDayAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'day_number', 'is_locked']
    list_filter = ['tournament', 'is_locked']


@admin.register(Hole)
class HoleAdmin(admin.ModelAdmin):
    list_display = ['number', 'match_day']
    list_filter = ['match_day__day_number']


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ['player', 'hole', 'strokes']
    list_filter = ['hole__match_day__day_number', 'player__team']


@admin.register(HoleResult)
class HoleResultAdmin(admin.ModelAdmin):
    list_display = ['hole', 'team1', 'team1_points', 'team2', 'team2_points']
