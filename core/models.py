from django.db import models


class Fight(models.Model):
    fighter1 = models.CharField(max_length=100)
    fighter2 = models.CharField(max_length=100)
    winner = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField()

    def str(self):
        return f"{self.fighter1} vs {self.fighter2} ({self.date})"


class ModelAI(models.Model):
    name = models.CharField(max_length=100, unique=True)
    balance = models.FloatField(default=1000.0)

    def str(self):
        return self.name


class Prediction(models.Model):
    ai_model = models.ForeignKey(ModelAI, on_delete=models.CASCADE)
    fight = models.ForeignKey(Fight, on_delete=models.CASCADE)
    predicted_winner = models.CharField(max_length=100)
    bet_amount = models.FloatField(default=100.0)
    result = models.FloatField(null=True, blank=True)

    def evaluate(self):
        if self.fight.winner:
            if self.predicted_winner == self.fight.winner:
                self.result = self.bet_amount * 0.5
            else:
                self.result = -self.bet_amount
            self.save()

            self.ai_model.balance += self.result
            self.ai_model.save()

            BalanceHistory.objects.create(
                ai_model=self.ai_model,
                balance=self.ai_model.balance
            )


class BalanceHistory(models.Model):
    ai_model = models.ForeignKey(ModelAI, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    balance = models.FloatField()

    def str(self):
        return f"{self.ai_model.name} - {self.balance:.2f} ({self.date.strftime('%Y-%m-%d %H:%M')})"
