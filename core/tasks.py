import json
from celery import shared_task
from django.db.models import Sum
from datetime import datetime, timedelta

from .models import ModelAI, Match, Prediction, BalanceHistory
from .utils import (get_model_prediction, get_match_odds, get_team_stats, LEAGUES_LIST_ID,
                    get_matches, get_unfinished_match_data)


@shared_task
def import_matches_and_predictions():
    tomorrow = datetime.now() + timedelta(days=1)
    matches = get_matches(tomorrow.strftime("%Y-%m-%d"))

    for fixture in matches:
        if fixture['league']['id'] in LEAGUES_LIST_ID:
            metadata_home = get_team_stats(tomorrow.year, fixture['teams']['home']['id'])
            if not metadata_home:
                metadata_home = get_team_stats(tomorrow.year - 1, fixture['teams']['home']['id'])
            metadata_away = get_team_stats(tomorrow.year, fixture['teams']['away']['id'])
            if not metadata_away:
                metadata_away = get_team_stats(tomorrow.year - 1, fixture['teams']['away']['id'])

            f, _ = Match.objects.get_or_create(
                rapidapi_id=fixture['fixture']['id'],
                defaults={
                    'type': 'football',
                    'date': datetime.fromisoformat(fixture['fixture']['date']).date(),
                    'home': fixture['teams']['home']['name'],
                    'away': fixture['teams']['away']['name'],
                    'metadata_home': metadata_home,
                    'metadata_away': metadata_away,
                    'metadata': fixture
                }
            )

    matches = Match.objects.filter(winner__isnull=True)
    models = ModelAI.objects.all()

    for model in models:
        for match in matches:
            odds_data = get_match_odds(match.home, match.away)
            if not odds_data:
                continue
            data = {
                "balance": model.balance, "home": match.home, "away": match.away,
                "date": match.date.strftime("%Y-%m-%d"),
                "home_last_results": match.metadata_home[:3] if match.metadata_home else "",
                "away_last_results": match.metadata_away[:3] if match.metadata_away else "",
                "home_rate": odds_data.get(match.home, "None"),
                "draw_rate": odds_data.get("Draw", "None"),
                "away_rate": odds_data.get(match.away, "None"),
            }

            if Prediction.objects.filter(ai_model=model,match=match).exists():
                continue

            prediction_data = get_model_prediction(data, model.name).replace("```json", "").replace("```", "")
            prediction_result = json.loads(prediction_data).get("result")
            prediction_stake = json.loads(prediction_data).get("stake")
            Prediction.objects.create(
                ai_model=model,
                match=match,
                predicted_winner=prediction_result,
                bet_amount=prediction_stake,
                odds=odds_data.get(prediction_result, 1.5),
            )

            model.balance -= float(prediction_stake)
            model.save()


@shared_task
def update_matches_and_predictions():
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

            for prediction in match.predictions.all():
                if prediction.predicted_winner != match.winner:
                    prediction.result = f"-{prediction.bet_amount}"
                    prediction.ai_model.balance -= prediction.bet_amount
                else:
                    prediction.result = f"+{prediction.bet_amount * prediction.odds}"
                    prediction.ai_model.balance += prediction.bet_amount * prediction.odds
                prediction.save()
                prediction.ai_model.save()

                pending_bets = Prediction.objects.filter(
                    ai_model=prediction.ai_model,
                    result__isnull=True
                ).aggregate(total=Sum("bet_amount"))["total"] or 0

                BalanceHistory.objects.create(
                    ai_model=prediction.ai_model,
                    balance=prediction.ai_model.balance + pending_bets
                )