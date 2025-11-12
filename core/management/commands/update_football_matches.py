from datetime import datetime, timedelta
from django.db.models import Sum
from django.core.management.base import BaseCommand

from core.models import Match, Prediction, BalanceHistory
from core.utils import get_unfinished_match_data


class Command(BaseCommand):
    # every day at 06:00
    def handle(self, *args, **options):
        # UPDATE MATCHES #
        now = datetime.now().date()
        matches = Match.objects.filter(date__lte=now, winner__isnull=True)
        for match in matches:
            if match.date < now - timedelta(days=2):
                continue
            fixture = get_unfinished_match_data(match.rapidapi_id)
            if not fixture:
                continue
            fixture = fixture[0]
            if fixture['fixture']['status']['short'] != "NS":
                if fixture['score']['penalty']['home'] is not None:
                    score_home = fixture['score']['penalty']['home']
                    score_away = fixture['score']['penalty']['away']
                elif fixture['score']['extratime']['home'] is not None:
                    score_home = fixture['score']['extratime']['home']
                    score_away = fixture['score']['extratime']['away']
                else:
                    score_home = fixture['score']['fulltime']['home']
                    score_away = fixture['score']['fulltime']['away']

                match.score_home = score_home
                match.score_away = score_away
                match.save()

                # UPDATE PREDICTIONS #
                for prediction in match.predictions.all():
                    if prediction.predicted_winner != match.winner:
                        prediction.result = f"-{prediction.bet_amount}"
                        prediction.ai_model.balance -= prediction.bet_amount
                    else:
                        prediction.result = f"+{prediction.bet_amount}"
                        prediction.ai_model.balance += prediction.bet_amount
                    prediction.save()

                    # UPDATE HISTORY #
                    pending_bets = Prediction.objects.filter(
                        ai_model=prediction.ai_model,
                        result__isnull=True
                    ).aggregate(total=Sum("bet_amount"))["total"] or 0

                    BalanceHistory.objects.create(
                        ai_model=prediction.ai_model,
                        balance=prediction.ai_model.balance + pending_bets
                    )
