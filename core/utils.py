import os
import requests

import anthropic
from google import genai
from openai import OpenAI
from xai_sdk import Client
from xai_sdk.chat import user, system

from dotenv import load_dotenv
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from .models import Match

load_dotenv()
LEAGUES_LIST_ID = [140, 2, 3, 848, 78, 32, 135, 39, 61]


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


def get_unfinished_match_data(rapidapi_id):
    response = requests.get(
        "https://api-football-v1.p.rapidapi.com/v3/fixtures",
        headers={
            "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
            "x-rapidapi-host": os.getenv("RAPIDAPI_HOST")
        },
        params={"id": str(rapidapi_id)}
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



def get_model_prediction(data, model_name):
    ai = AIModels()

    system_prompt = SYSTEM_PROMPT.format(data.get("balance"))

    user_prompt = USER_PROMPT.format(
        data.get("balance"),
        data.get("home"),
        data.get("away"),
        data.get("date"),
        data.get("home_last_results"),
        data.get("away_last_results"),
        data.get("home_rate"),
        data.get("draw_rate"),
        data.get("away_rate"),
        data.get("over"),
        data.get("under"),
        data.get("yes"),
        data.get("no"),
    )

    model_dispatch = {
        "ChatGPT 4": ai.openai,
        "DeepSeek": ai.deepseek,
        "Gemini": ai.gemini,
        "GROK 4": ai.grok,
        "Claude Sonnet 4.5": ai.anthropic,
    }

    model_func = model_dispatch.get(model_name, ai.deepseek)

    return model_func(system_prompt=system_prompt, user_prompt=user_prompt)


def get_scraper_api_response(url, render_js=False):
    params = {
        "api_key": os.getenv("SCRAPER_API_KEY"),
        "url": url,
        "render_js": render_js
    }

    response = requests.get(url='https://proxy.scrapeops.io/v1/', params=params)
    if response.status_code == 200:
        return response.content

    return None


def get_match_odds(home, away, league_id):
    LEAGUES_ODDS_MAP = {
        '2': 'https://www.olbg.com/betting-tips/Football/UEFA_Competitions/Champions_League/1',
        '3': 'https://www.olbg.com/betting-tips/Football/UEFA_Competitions/Europa_League/1',
        '32': 'https://www.olbg.com/betting-tips/Football/International/World_Cup_Finals/1',
        '39': 'https://www.olbg.com/betting-tips/Football/UK/England_Premier_League/1',
        '61': 'https://www.olbg.com/betting-tips/Football/European_Competitions/France_Ligue_1/1',
        '78': 'https://www.olbg.com/betting-tips/Football/European_Competitions/Germany_Bundesliga_I/1',
        '135': 'https://www.olbg.com/betting-tips/Football/European_Competitions/Italy_Serie_A/1',
        '140': 'https://www.olbg.com/betting-tips/Football/European_Competitions/Spain_Primera_Liga/1',
        '848': 'https://www.olbg.com/betting-tips/Football/UEFA_Competitions/UEFA_Europa_Conference_League/1',
    }

    result = {}
    response = requests.get(LEAGUES_ODDS_MAP[str(league_id)])
    soup = BeautifulSoup(response.content, "html.parser")
    for match in soup.find_all("a"):
        event_name_block = match.find("h5")
        if event_name_block:
            event_name = event_name_block.text
            if home in event_name or away in event_name:
                response = requests.get(match.get("href"))
                soup = BeautifulSoup(response.content, "html.parser")
                main_block = soup.find_all("div", {"class": "expanded"})[:3]
                for block in main_block:
                    odds_category = block.find_all("a")
                    for section in odds_category:
                        title_section = section.find("h4")
                        if not title_section:
                            continue
                        title = title_section.text.strip()
                        if any(title == t for t in [home, away, "Draw", "Over 2.50", "Under 2.50", "Yes", "No"]):
                            result[title_section.text.strip()] = section.find(
                                "span", {"class": "ui-odds"}
                            ).get("data-decimal")
    return result



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

    def deepseek(self, system_prompt, user_prompt):
        client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        ).choices[0].message.content

        return response

    def gemini(self, system_prompt, user_prompt):
        client = genai.Client(api_key=os.getenv("GENAI_KEY"))

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{system_prompt}/n{user_prompt}",
        ).text

        return response

    def grok(self, system_prompt, user_prompt):
        client = Client(
            api_key=os.getenv("GROK_API_KEY"),
            timeout=3600,
        )
        chat = client.chat.create(model="grok-4")
        chat.append(system(system_prompt))
        chat.append(user(user_prompt))
        response = chat.sample()

        return response.content

    def anthropic(self, system_prompt, user_prompt):
        headers = {
            "x-api-key": os.getenv("ANTHROPIC_API_KEY"),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        data = {
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 250,
            "temperature": 1,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data)

        return response.json()["content"][0]["text"]


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
     - {4}
    Recent Form ({2} last matches):
     - {5}
    Betting Odds:
     - Win {1}: {6}
     - Draw: {7}
     - Win {2}: {8}
     - Over 2.5 Goals: {9}
     - Under 2.5 Goals: {10}
     - BTTS Yes: {11}
     - BTTS No: {12}
    Your Task:
     - Analyze the matchup using the odds, team form, and home advantage.
     - Decide the most likely outcome among:
          - "{1}" (home win)
          - "{2}" (away win)
          - "Draw"
          - "Over 2.5 Goals"
          - "Under 2.5 Goals"
          - "BTTS Yes"
          - "BTTS No"
     - Calculate the optimal stake amount (max 15% of ${0}).
    Output strictly in this JSON format:
          "result": "Over 2.5 Goals",   // or "{1}", "{2}", "Draw", "Under 2.5 Goals", "BTTS Yes", "BTTS No"
          "stake": 30             // numeric value in dollars
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