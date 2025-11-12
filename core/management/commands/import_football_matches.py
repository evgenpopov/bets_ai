import json
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand

from core.models import ModelAI, Match, Prediction
from core.utils import get_matches, get_match_odds, get_team_stats, get_model_prediction, LEAGUES_LIST_ID


class Command(BaseCommand):
    # every day at 08:00
    def handle(self, *args, **options):
        # IMPORT MATCHES #
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

        # CREATE PREDICTIONS #
        matches = Match.objects.filter(winner__isnull=True)
        model = ModelAI.objects.get(name="ChatGPT 4")  # make qs of all models

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

            prediction_data = json.loads(get_model_prediction(data))
            prediction_result = prediction_data.get("result")
            prediction_stake = prediction_data.get("stake")
            Prediction.objects.create(
                ai_model=model,
                match=match,
                predicted_winner=prediction_result,
                bet_amount=prediction_stake,
                odds=odds_data.get(prediction_result, 1.5),
            )

            model.balance -= float(prediction_stake)
            model.save()
