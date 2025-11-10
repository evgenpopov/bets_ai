from django.db import models


class ModelAI(models.Model):
    name = models.CharField(max_length=100, unique=True)
    balance = models.FloatField(default=1000.0)

    def __str__(self):
        return self.name


class Match(models.Model):
    MATCH_TYPES = [
        ('boxing', 'Boxing'),
        ('football', 'Football'),
    ]

    type = models.CharField(max_length=20, choices=MATCH_TYPES)
    date = models.DateField()
    winner = models.CharField(max_length=100, blank=True, null=True)

    participant_1 = models.CharField(max_length=100)
    participant_2 = models.CharField(max_length=100)
    metadata_participant_1 = models.JSONField(blank=True, null=True)
    metadata_participant_2 = models.JSONField(blank=True, null=True)
    score_1 = models.IntegerField(blank=True, null=True)
    score_2 = models.IntegerField(blank=True, null=True)

    metadata = models.JSONField(blank=True, null=True)
    rapidapi_id = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"({self.date}) {self.participant_1} vs {self.participant_2}"

    def auto_set_winner(self):
        if self.score_1 is not None and self.score_2 is not None:
            if self.score_1 > self.score_2:
                self.winner = self.participant_1
            elif self.score_2 > self.score_1:
                self.winner = self.participant_2
            else:
                self.winner = "Draw"

    def save(self, *args, **kwargs):
        self.auto_set_winner()
        super().save(*args, **kwargs)


class Prediction(models.Model):
    ai_model = models.ForeignKey(ModelAI, on_delete=models.CASCADE, related_name="predictions")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="predictions")

    predicted_winner = models.CharField(max_length=100)
    bet_amount = models.FloatField(default=100.0)
    odds = models.FloatField(default=1.5)
    result = models.FloatField(null=True, blank=True)

    def evaluate(self):
        if not self.match.winner:
            return

        if self.match.winner == "Draw":
            self.result = 0
        elif self.predicted_winner == self.match.winner:
            self.result = self.bet_amount * (self.odds - 1)
        else:
            self.result = -self.bet_amount

        self.save()

        self.ai_model.balance += self.result
        self.ai_model.save()

        BalanceHistory.objects.create(
            ai_model=self.ai_model,
            balance=self.ai_model.balance
        )

    def __str__(self):
        return f"{self.ai_model.name} → {self.match}: {self.predicted_winner} (odds {self.odds})"


class BalanceHistory(models.Model):
    ai_model = models.ForeignKey(ModelAI, on_delete=models.CASCADE, related_name="balance_history")
    date = models.DateTimeField(auto_now_add=True)
    balance = models.FloatField()

    def __str__(self):
        return f"{self.ai_model.name} - {self.balance:.2f} ({self.date.strftime('%Y-%m-%d %H:%M')})"
