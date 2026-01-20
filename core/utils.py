import os
import requests
from celery.worker.state import total_count

from django.db.models import Sum
from google import genai
from openai import OpenAI
from xai_sdk import Client
from xai_sdk.chat import user, system

from dotenv import load_dotenv
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from .models import Match, Prediction, ModelAI

load_dotenv()
LEAGUES_LIST_ID = [140, 2, 3, 848, 78, 32, 135, 39, 61]
# super cups 143, 871, 66, 137, 81, 526, 556


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



def get_model_prediction(data, model_name, event_count, event_num):
    ai = AIModels()

    system_prompt = SYSTEM_PROMPT.format(data.get("balance"))

    model = ModelAI.objects.get(name=model_name)
    pending_bets = Prediction.objects.filter(
        ai_model=model,
        result__isnull=True
    ).aggregate(total=Sum("bet_amount"))["total"] or 0
    total_balance = model.balance + pending_bets

    user_prompt = USER_PROMPT.format(
        balance=total_balance,
        home=data.get("home"),
        away=data.get("away"),
        date=data.get("date"),
        home_last=data.get("home_last_results"),
        away_last=data.get("away_last_results"),
        home_rate=data.get("home_rate"),
        draw_rate=data.get("draw_rate"),
        away_rate=data.get("away_rate"),
        over=data.get("over"),
        under=data.get("under"),
        btts_yes=data.get("yes"),
        btts_no=data.get("no"),
        event_count=event_count,
        event_num=event_num
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


SYSTEM_PROMPT = """
        You are an elite professional football bettor with over 20 years of real-market experience.
        You manage a bankroll of ${0} and think strictly in terms of long-term expected value (EV),
        risk-adjusted returns, and bankroll preservation.
        
        Your core principles:
        - You NEVER bet without clear value over the bookmaker's implied probability
        - You prioritize capital preservation over short-term profit
        - You think in hundreds of bets, not in single outcomes
        - You control variance, drawdowns, and overconfidence
        - You size stakes conservatively using fractional Kelly logic
        
        You behave like a disciplined syndicate-level bettor, not a gambler.
    """

USER_PROMPT = """
    Rules:
      - You operate as a professional football bettor with over 20 years of experience.
      - Your primary objective is long-term profitability and bankroll preservation, not short-term wins.
      - Never allocate more than your total available budget across all events combined.
      - Total budget available for this prediction: {balance}$
      - Count of events: {event_count}
      - Current event number: {event_num}
      - The total sum of all open bets must never exceed 50% of total bankroll.
      - Use ONLY the provided data (no assumptions, no external knowledge).
    
    Analytical Framework (MANDATORY):
    1. Convert all odds into implied probabilities.
    2. Estimate the true probability of each market outcome using:
       - Home advantage
       - Recent form patterns (consistency, not single results)
       - Relative performance of both teams
       - Market efficiency assumptions (assume bookmaker odds are generally efficient)
    3. Identify VALUE:
       - Value exists ONLY if your estimated probability is higher than the implied probability.
       - Avoid marginal edges — prioritize clear, defensible value.
    4. Compare all available markets and select ONLY ONE bet with the best
       risk-adjusted expected value.
    5. Prefer 1X2 markets (Home Win, Away Win, Draw).
       Use alternative markets ONLY if the edge is significantly clearer.
    
    Risk Management & Stake Sizing (Aggressive 50% Cap)
    - Base betting unit = 2% of total bankroll.
    - Stake sizing must follow conservative fractional-Kelly principles:
      - Low confidence / small edge: 1–2% of bankroll
      - Medium confidence / solid edge: 3–5% of bankroll
      - High confidence (rare): maximum 6-10% of bankroll
    - Exposure limit: total active stakes must not exceed 50% of bankroll.
    - NEVER increase stake due to perceived certainty.
    - NEVER chase odds or compensate for previous results.
    - Reduce stake if odds are below 1.60 (scale down to ~50% of calculated unit).
    - If bankroll is already partially committed, scale down new stakes to respect the 50% total cap.
    - Notes:
       - With these limits, multiple high-confidence bets can cumulatively reach ~50% of the bankroll.
       - Still maintains risk control via scaling and odds/edge adjustments.
    
    Professional Betting Constraints:
    - Treat each bet as one of hundreds in a long-term portfolio.
    - Do not assume recent form alone guarantees an outcome.
    - Avoid speculative or narrative-driven decisions.
    - Capital preservation is more important than maximizing single-bet profit.
    - If no strong value is detected, select the most conservative viable option
      with the minimum reasonable stake.
    
    Upcoming Match Info:
    - Home Team: {home}
    - Away Team: {away}
    - Date: {date}
    
    Recent Form ({home} last matches):
    - {home_last}
    
    Recent Form ({away} last matches):
    - {away_last}
    
    Betting Odds:
    - Win {home}: {home_rate}
    - Draw: {draw_rate}
    - Win {away}: {away_rate}
    - Over 2.5 Goals: {over}
    - Under 2.5 Goals: {under}
    - BTTS Yes: {btts_yes}
    - BTTS No: {btts_no}
    
    Your Task:
    - Analyze the matchup strictly using the framework above.
    - Determine the single most valuable and risk-controlled bet among:
        - "{home}" (Home Win)
        - "{away}" (Away Win)
        - "Draw"
        - "Over 2.5 Goals"
        - "Under 2.5 Goals"
        - "BTTS Yes"
        - "BTTS No"
    - Select the outcome with the best balance between probability, value, and risk.
    - Calculate an appropriate stake based on bankroll, confidence, and exposure.
    - Write a concise professional comment justifying the decision.
    
    Output Format (STRICT):
    {{
      "result": "{home} | {away} | Draw | Over 2.5 Goals | Under 2.5 Goals | BTTS Yes | BTTS No",
      "stake": 10,
      "comment": "Clear value identified based on probability edge, controlled risk, and market efficiency."
    }}
    
    Critical Constraints:
    - Return ONLY a valid JSON object using double quotes.
    - Do NOT include any explanations outside the JSON.
    - Do NOT use single quotes under any circumstances.
    - Do NOT include markdown or code blocks.
    - Stake must respect bankroll and exposure rules.
"""
