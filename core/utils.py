import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

from .models import Match

load_dotenv()
LEAGUES_LIST_ID = [140, 2, 3, 848, 333, 78, 32]


def get_matches(date):
    response = requests.get(
        "https://api-football-v1.p.rapidapi.com/v3/fixtures",
        headers={
            "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
            "x-rapidapi-host": os.getenv("RAPIDAPI_HOST")
        },
        params={"date": date}
    )

    return response.json()['response']


def get_team_stats(season, team_id):
    response = requests.get(
        "https://api-football-v1.p.rapidapi.com/v3/fixtures" ,
        headers={
            "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
            "x-rapidapi-host": os.getenv("RAPIDAPI_HOST")
        },
        params={"season":f"{season}","team":f"{team_id}"}
    )

    return response.json()['response']


def create_matches_obj():
    tomorrow = datetime.now() + timedelta(days=3)
    matches = get_matches(tomorrow.strftime("%Y-%m-%d"))

    for fixture in matches:
        if fixture['league']['id'] in LEAGUES_LIST_ID:
            metadata_participant_1 = get_team_stats(tomorrow.year, fixture['teams']['home']['id'])
            if not metadata_participant_1:
                metadata_participant_1 = get_team_stats(tomorrow.year - 1, fixture['teams']['home']['id'])
            metadata_participant_2 = get_team_stats(tomorrow.year, fixture['teams']['away']['id'])
            if not metadata_participant_2:
                metadata_participant_2 = get_team_stats(tomorrow.year - 1, fixture['teams']['away']['id'])

            f, _ = Match.objects.get_or_create(
                rapidapi_id=fixture['fixture']['id'],
                defaults={
                    'type': 'football',
                    'date': datetime.fromisoformat(fixture['fixture']['date']).date(),
                    'participant_1': fixture['teams']['home']['name'],
                    'participant_2': fixture['teams']['away']['name'],
                    'metadata_participant_1': metadata_participant_1,
                    'metadata_participant_2': metadata_participant_2,
                    'metadata': fixture
                }
            )
