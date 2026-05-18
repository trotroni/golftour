from django.urls import path
from . import views

urlpatterns = [
    # ── Navigation principale ────────────────────────────────────
    path('', views.home, name='home'),
    path('setup/', views.setup, name='setup'),

    # ── Saisie des scores ────────────────────────────────────────
    path('jour/<int:day_id>/saisie/<int:group>/', views.saisie, name='saisie'),

    # ── Résultats ────────────────────────────────────────────────
    path('jour/<int:day_id>/resultats/', views.resultats, name='resultats'),

    # ── Verrouillage journée ─────────────────────────────────────
    path('jour/<int:day_id>/verrouiller/', views.lock_day, name='lock_day'),
    path('jour/<int:day_id>/deverrouiller/', views.unlock_day, name='unlock_day'),

    # ── Settings ─────────────────────────────────────────────────
    path('settings/', views.settings_view, name='settings'),
    path('settings/save/', views.settings_save, name='settings_save'),
    path('settings/reset/', views.reset_tournament, name='reset_tournament'),

    # ── Endpoints HTMX ───────────────────────────────────────────
    path(
        'htmx/score/<int:hole_id>/<int:player_id>/',
        views.update_score,
        name='update_score',
    ),
    path(
        'htmx/saisie-form/<int:hole_id>/<int:group>/',
        views.saisie_form_partial,
        name='saisie_form_partial',
    ),
]
