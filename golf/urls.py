from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('setup/', views.setup, name='setup'),
    path('jour/<int:day_id>/saisie/<int:group>/', views.saisie, name='saisie'),
    path('jour/<int:day_id>/resultats/', views.resultats, name='resultats'),
    path('jour/<int:day_id>/verrouiller/', views.lock_day, name='lock_day'),
    path('jour/<int:day_id>/deverrouiller/', views.unlock_day, name='unlock_day'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/save/', views.settings_save, name='settings_save'),
    path('settings/reset/', views.reset_tournament, name='reset_tournament'),
    # HTMX
    path('htmx/tbody/<int:day_id>/<int:group>/', views.saisie_tbody_partial, name='saisie_tbody_partial'),
    path('htmx/valider/<int:hole_id>/<int:group>/', views.validate_hole, name='validate_hole'),
    path('htmx/score/<int:hole_id>/<int:player_id>/', views.update_score, name='update_score'),
]