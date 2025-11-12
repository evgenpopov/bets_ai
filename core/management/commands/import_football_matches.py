from datetime import datetime, timedelta
from django.core.management.base import BaseCommand

from core.models import Match
from core.utils import get_matches, get_team_stats, LEAGUES_LIST_ID


class Command(BaseCommand):
    def handle(self, *args, **options):
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
