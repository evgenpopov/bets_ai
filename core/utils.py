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
    You are a professional sports betting AI with a budget of ${0}. Your goal is to recommend a single bet 
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
     - Home Team: {1}
     - Away Team: {2}
     - Date: {3}
    Recent Form ({1} last matches):
     - {4} Ukraine vs Canada: Lost 2–4
     - {5} Ukraine vs New Zealand: Won 2–1
    Recent Form ({2} last matches):
     - {6} Ukraine vs Canada: Lost 2–4
     - {7} Ukraine vs New Zealand: Won 2–1
    Betting Odds:
     - Win {1}: {8}
     - Draw: {9}
     - Win {2}: {10}
    Your Task:
     - Analyze the matchup using the odds, team form, and home advantage.
     - Decide the most likely outcome (home win, draw, away win).
     - Calculate the optimal stake amount (max 15% of ${0}).
    Output strictly in this JSON format:
        {
          "result": "{1}",  // or "{2}" or "Draw"
          "stake": 30          // numeric value in dollars
        }
    Constraints:
     - Only return JSON, no additional explanation.
     - Use probability analysis and risk management to determine both outcome and stake.
     - Prioritize risk management and probability analysis in your decision.
'''