from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User


class ModelAI(models.Model):
    name = models.CharField(max_length=100, unique=True)
    balance = models.FloatField(default=1000.0)
    slug = models.SlugField(unique=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Match(models.Model):
    MATCH_TYPES = [
        ('boxing', 'Boxing'),
        ('football', 'Football'),
    ]

    type = models.CharField(max_length=20, choices=MATCH_TYPES)
    date = models.DateField()
    winner = models.CharField(max_length=100, blank=True, null=True)

    home = models.CharField(max_length=100)
    away = models.CharField(max_length=100)
    metadata_home = models.JSONField(blank=True, null=True)
    metadata_away = models.JSONField(blank=True, null=True)
    score_home = models.IntegerField(blank=True, null=True)
    score_away = models.IntegerField(blank=True, null=True)

    metadata = models.JSONField(blank=True, null=True)
    odds = models.JSONField(blank=True, null=True)
    rapidapi_id = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"[{self.date}] {self.home} vs {self.away}"

    def save(self, *args, **kwargs):
        # auto set winner
        if self.score_home is not None and self.score_away is not None:
            if self.score_home > self.score_away:
                self.winner = self.home
            elif self.score_away > self.score_home:
                self.winner = self.away
            else:
                self.winner = "Draw"
        super().save(*args, **kwargs)


class Prediction(models.Model):
    ai_model = models.ForeignKey(ModelAI, on_delete=models.CASCADE, related_name="predictions")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="predictions")

    predicted_winner = models.CharField(max_length=100)
    bet_amount = models.FloatField(default=100.0)
    odds = models.FloatField(default=1.5)
    result = models.CharField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.ai_model.name} → {self.match}: {self.predicted_winner} (rate {self.odds})"


class BalanceHistory(models.Model):
    ai_model = models.ForeignKey(ModelAI, on_delete=models.CASCADE, related_name="balance_history")
    date = models.DateTimeField(auto_now_add=True)
    balance = models.FloatField()

    def __str__(self):
        return f"{self.ai_model.name} - {self.balance:.2f} ({self.date.strftime('%Y-%m-%d %H:%M')})"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account_type = models.CharField(max_length=10, choices=[('lite','Lite'),('premium','Premium')], default='lite')
