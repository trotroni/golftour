from django.db import models
from django.db.models import Min


class Tournament(models.Model):
    name = models.CharField(max_length=200, default="Golf Tournament")
    num_days = models.IntegerField(default=3)
    num_holes = models.IntegerField(default=18)

    def __str__(self):
        return self.name

    @classmethod
    def get_active(cls):
        return cls.objects.first()


class Team(models.Model):
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name='teams'
    )
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#2563eb')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class Player(models.Model):
    SAISIE_GROUP_CHOICES = [(1, 'Groupe 1'), (2, 'Groupe 2')]

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name='players'
    )
    name = models.CharField(max_length=100)
    order = models.IntegerField(default=0)
    saisie_group = models.IntegerField(choices=SAISIE_GROUP_CHOICES, default=1)

    class Meta:
        ordering = ['team__order', 'order']

    def __str__(self):
        return f"{self.name} ({self.team.name})"


class MatchDay(models.Model):
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name='days'
    )
    day_number = models.IntegerField()
    is_locked = models.BooleanField(default=False)

    class Meta:
        ordering = ['day_number']
        unique_together = ['tournament', 'day_number']

    def __str__(self):
        return f"Jour {self.day_number}"

    def is_fully_complete(self):
        holes = self.holes.all()
        if not holes.exists():
            return False
        completed = HoleResult.objects.filter(hole__match_day=self).count()
        return completed >= holes.count()


class Hole(models.Model):
    match_day = models.ForeignKey(
        MatchDay, on_delete=models.CASCADE, related_name='holes'
    )
    number = models.IntegerField()

    class Meta:
        ordering = ['number']
        unique_together = ['match_day', 'number']

    def __str__(self):
        return f"Trou {self.number} (Jour {self.match_day.day_number})"

    def get_all_players(self):
        return Player.objects.filter(team__tournament=self.match_day.tournament)

    def is_complete(self):
        total = self.get_all_players().count()
        if total == 0:
            return False
        submitted = self.scores.filter(strokes__isnull=False).count()
        return submitted >= total

    def get_status(self):
        if HoleResult.objects.filter(hole=self).exists():
            return 'done'
        submitted = self.scores.filter(strokes__isnull=False).count()
        if submitted > 0:
            return 'in_progress'
        return 'pending'

    def get_best_score_for_team(self, team):
        result = self.scores.filter(
            player__team=team,
            strokes__isnull=False
        ).aggregate(best=Min('strokes'))
        return result['best']


class Score(models.Model):
    hole = models.ForeignKey(
        Hole, on_delete=models.CASCADE, related_name='scores'
    )
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name='scores'
    )
    strokes = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ['hole', 'player']

    def __str__(self):
        return f"{self.player.name}: {self.strokes} coups (Trou {self.hole.number})"


class HoleResult(models.Model):
    hole = models.OneToOneField(
        Hole, on_delete=models.CASCADE, related_name='result'
    )
    team1 = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name='hole_results_t1'
    )
    team2 = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name='hole_results_t2'
    )
    team1_points = models.FloatField(default=0)
    team2_points = models.FloatField(default=0)
    team1_best = models.IntegerField(null=True, blank=True)
    team2_best = models.IntegerField(null=True, blank=True)

    def points_for_team(self, team):
        if team.id == self.team1_id:
            return self.team1_points
        if team.id == self.team2_id:
            return self.team2_points
        return 0.0

    def __str__(self):
        return (
            f"Trou {self.hole.number}: "
            f"{self.team1.name} {self.team1_points} - "
            f"{self.team2.name} {self.team2_points}"
        )
