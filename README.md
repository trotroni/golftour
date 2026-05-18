# Golf Tournament

Application Django mobile-first pour gérer une compétition de golf par équipes (USA vs EUR).

## Lancement rapide (dev)

```bash
# 1. Créer le venv et installer les dépendances
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Migrations (déjà incluses dans le repo)
python manage.py migrate

# 3. Lancer le serveur
python manage.py runserver 0.0.0.0:8000
```

Ouvre ensuite `http://localhost:8000` et configure le tournoi.

---

## Déploiement sur Raspberry Pi (server64)

```bash
# Sur ton Mac — copier le projet
rsync -av --exclude='.venv' --exclude='db.sqlite3' --exclude='staticfiles' \
    ./golftour/ trotroni@server64:/home/trotroni/golftour/

# Sur le Pi
cd /home/trotroni/golftour
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Migrations + collectstatic
python manage.py migrate
python manage.py collectstatic --no-input

# Créer le dossier logs
mkdir -p logs

# Installer le service
sudo cp golftour.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable golftour
sudo systemctl start golftour

# Vérifier
sudo systemctl status golftour
```

---

## Structure du projet

```
golftour/
├── config/                 # Settings, urls, wsgi
├── golf/
│   ├── models.py           # Tournament, Team, Player, MatchDay, Hole, Score, HoleResult
│   ├── views.py            # Toutes les vues + endpoints HTMX
│   ├── logic.py            # Logique métier (calculate_hole_result, totaux...)
│   ├── urls.py             # Routes
│   ├── admin.py            # Interface admin Django
│   ├── templatetags/
│   │   └── golf_tags.py    # Filtres Jinja (format_pts, team_pts...)
│   ├── templates/golf/
│   │   ├── base.html       # Layout + nav + HTMX
│   │   ├── home.html       # Page d'accueil
│   │   ├── setup.html      # Initialisation du tournoi
│   │   ├── saisie.html     # Page de saisie (shell)
│   │   ├── resultats.html  # Résultats globaux
│   │   ├── settings.html   # Configuration
│   │   └── partials/
│   │       └── saisie_form.html   # Partial HTMX pour la saisie live
│   └── migrations/
├── static/
│   └── golf.css            # CSS mobile-first complet
├── manage.py
├── requirements.txt
└── golftour.service        # Fichier systemd
```

---

## Pages disponibles

| URL | Description |
|-----|-------------|
| `/` | Accueil — sélection de journée |
| `/setup/` | Configuration initiale |
| `/jour/<id>/saisie/1/` | Saisie Groupe 1 (J1, J2, J4) |
| `/jour/<id>/saisie/2/` | Saisie Groupe 2 (J3, J5) |
| `/jour/<id>/resultats/` | Résultats du jour + tournoi |
| `/settings/` | Renommer joueurs, équipes, couleurs |
| `/admin/` | Interface admin Django |

---

## Règles de calcul

- Meilleur score (min coups) de chaque équipe par trou
- Equipe avec le moins de coups → **1 point**
- Égalité → **0.5 point chacun**
- Le trou suivant ne s'ouvre que quand tous les scores sont saisis
- Les journées peuvent être verrouillées pour bloquer les modifications

---

## Note — faute dans le service original

Le `service` d'origine contenait `connfig.wsgi` (double `n`).
Le fichier `golftour.service` fourni ici est corrigé → `config.wsgi`.
