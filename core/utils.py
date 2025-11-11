import os
import requests
from openai import OpenAI
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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
        "https://api-football-v1.p.rapidapi.com/v3/fixtures",
        headers={
            "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
            "x-rapidapi-host": os.getenv("RAPIDAPI_HOST")
        },
        params={"season": f"{season}", "team": f"{team_id}"}
    )

    return response.json()['response']


def create_matches_obj():
    tomorrow = datetime.now() + timedelta(days=3)
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


def get_model_prediction():
    result = AIModels().openai(
        system_prompt=SYSTEM_PROMPT.format("1000"),
        user_prompt=USER_PROMPT.format(
            "1000", "France", "Ukraine", "13.11.2025 21:45",
            "France vs New Zealand: Draw 2–2", "France vs Germany: Win 2–0",
            "Ukraine vs Canada: Lost 2–4", "Ukraine vs New Zealand: Won 2–1",
            "1.19", "6.90", "16.50"
        )
    )
    return result


def get_match_odds(home, away):
    response = requests.get("https://www.olbg.com/betting-tips/Football/1")
    soup = BeautifulSoup(response.content, "html.parser")
    matches = soup.find_all("a")
    for i in matches:
        print(i)
    # for match in matches:
    #     event_name = match.find("h5").text
    #     print(event_name)
    #     if home in event_name or away in event_name:
    #         print(link.get("href"))
    pass



class AIModels:
    def openai(self, system_prompt, user_prompt):
        client = OpenAI(api_key=os.getenv("OPENAI_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.2,
            frequency_penalty=0,
            presence_penalty=0,
            max_tokens=200,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        ).choices[0].message.content

        return response

    def anthropic(self, system_prompt, user_prompt):
        headers = {
            "x-api-key": os.getenv("ANTHROPIC_API_KEY"),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        data = {
            "model": "claude-3-7-sonnet-20250219",
            "max_tokens": 250,
            "temperature": 1,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data)

        return response

    def gemini(self):
        pass

    def deepseek(self):
        pass


SYSTEM_PROMPT = '''
    You are a professional sports betting AI with a budget of ${0}. Your goal is to recommend a single bet 
    on the upcoming match using a data-driven, risk-managed strategy.
'''


USER_PROMPT = '''
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
          "result": "{1}",  // or "{2}" or "Draw"
          "stake": 30       // numeric value in dollars
    Constraints:
     - Only return JSON, no additional explanation.
     - Use probability analysis and risk management to determine both outcome and stake.
     - Prioritize risk management and probability analysis in your decision.
     - Return ONLY valid JSON string using double quotes ("), as per JSON specification. 
     - Do NOT use single quotes under any circumstances.
     - *** Do NOT use ```json, just clean dict with double quotes. ***
     - *** NEVER use single quotes (') — output MUST be valid JSON. ***
     - The output must be a valid JSON dictionary — not a Python dict.
'''