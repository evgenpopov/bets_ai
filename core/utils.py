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


class AIModels:
    def openai(self):
        pass

    def gemini(self):
        pass

    def anthropic(self):
        pass

    def deepseek(self):
        pass


PROMPT = f'''
    You are a professional sports betting AI with a budget of $200. Your goal is to recommend a single bet 
    on the upcoming match using a data-driven, risk-managed strategy.

    Rules:
     - Never bet more than 15% of your total budget on a single outcome.
     - Use only the provided data: match info, historical results, and betting odds.
    Consider:
     - Home advantage
     - Recent form of both teams
     - Head-to-head results (if available)
     - Betting odds and implied probabilities
     - Potential payout vs. risk
    Upcoming Match Info:
     - Home Team: France
     - Away Team: Ukraine
     - Date: 2025-11-13 19:45 UTC
    Recent Form (Ukraine last 2 matches):
     - Ukraine vs Canada: Lost 2–4
     - Ukraine vs New Zealand: Won 2–1
    Betting Odds:
     - Win France: [insert odds]
     - Draw: [insert odds]
     - Win Ukraine: [insert odds]
    Your Task:
     - Analyze the matchup using the odds, team form, and home advantage.
     - Decide the most likely outcome (home win, draw, away win).
     - Calculate the optimal stake amount (max 15% of $200).
    Output strictly in this JSON format:
     - If France is predicted to win: {'result': 'France'}
     - If Ukraine is predicted to win: {'result': 'Ukraine'}
     - If a draw is predicted: {'result': 'Draw'}
    Constraints:
     - Do not provide any explanation outside the JSON.
     - Use only the data provided.
     - Prioritize risk management and probability analysis in your decision.
'''