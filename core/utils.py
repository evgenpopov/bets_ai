import os
import requests
from google import genai
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
        data.get("away_rate")
    )

    model_dispatch = {
        "ChatGPT 4": ai.openai,
        "DeepSeek": ai.deepseek,
        "Gemini": ai.gemini
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


def get_match_odds(home, away):
    result = {}
    response = requests.get("https://www.olbg.com/betting-tips/Football/1")
    #response = get_scraper_api_response(url="https://www.olbg.com/betting-tips/Football/1", render_js=True)
    soup = BeautifulSoup(response.content, "html.parser")
    for match in soup.find_all("a"):
        event_name_block = match.find("h5")
        if event_name_block:
            event_name = event_name_block.text
            if home in event_name or away in event_name:
                response = requests.get(match.get("href"))
                soup = BeautifulSoup(response.content, "html.parser")
                main_block = soup.find("div", {"class": "expanded"})
                odds_category = main_block.find_all("a")
                for section in odds_category:
                    title_section = section.find("h4")
                    if not title_section:
                        continue
                    title = title_section.text.strip()
                    if any(title == t for t in [home, away, "Draw"]):
                        result[title_section.text.strip()] = section.find(
                            "span", {"class": "ui-odds"}
                        ).get("data-decimal")
                break
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