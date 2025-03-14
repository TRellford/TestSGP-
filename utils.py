import requests
import numpy as np
from datetime import date
import streamlit as st
import time
import random

# Constants
BALL_DONT_LIE_API_URL = "https://api.balldontlie.io/v1"
ODDS_API_URL = "https://api.the-odds-api.com/v4"

def fetch_games(date, max_retries=3, initial_delay=2):
    """Fetch NBA games from Balldontlie API for a given date with retries."""
    api_key = st.secrets.get("balldontlie_api_key", None)
    if not api_key:
        st.error("Invalid API key for Balldontlie API. Check configuration.")
        return []

    url = f"{BALL_DONT_LIE_API_URL}/games"
    headers = {"Authorization": api_key}
    params = {"dates[]": date.strftime("%Y-%m-%d")}

    retries = 0
    while retries < max_retries:
        try:
            time.sleep(initial_delay)  # Delay to avoid rate limits
            response = requests.get(url, headers=headers, params=params, timeout=10)
            print(f"Balldontlie Request URL: {response.url}")
            print(f"Balldontlie Response Status Code: {response.status_code}")
            print(f"Balldontlie Raw Response: {response.text}")

            response.raise_for_status()

            games_data = response.json().get("data", [])
            if not games_data:
                return []

            formatted_games = [
                {
                    "id": game["id"],
                    "display": f"{game['home_team']['abbreviation']} vs {game['visitor_team']['abbreviation']}",
                    "home_team": game["home_team"]["full_name"],
                    "away_team": game["visitor_team"]["full_name"],
                    "date": game["date"]
                }
                for game in games_data
            ]
            return formatted_games

        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                st.error("Invalid API key for Balldontlie API. Check configuration.")
                return []
            elif response.status_code == 429:
                retries += 1
                wait_time = initial_delay * (2 ** retries)
                st.warning(f"Balldontlie API rate limit reached. Retrying in {wait_time} seconds... (Attempt {retries}/{max_retries})")
                time.sleep(wait_time)
            else:
                st.error(f"Error fetching games from Balldontlie API: {response.status_code} - {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            st.error(f"Network error fetching games from Balldontlie API: {e}")
            return []

    st.error("API rate limit reached for Balldontlie API. Try again later.")
    return []

def fetch_odds_api_events(date, max_retries=3, initial_delay=2):
    """Fetch all NBA events from The Odds API for a given date."""
    api_key = st.secrets.get("odds_api_key", None)
    if not api_key:
        st.error("Invalid API key for The Odds API. Check configuration.")
        return []

    url = f"{ODDS_API_URL}/sports/basketball_nba/events?date={date.strftime('%Y-%m-%d')}&apiKey={api_key}"
    
    retries = 0
    while retries < max_retries:
        try:
            time.sleep(initial_delay)
            response = requests.get(url, timeout=10)
            print(f"The Odds API Events Request URL: {response.url}")
            print(f"The Odds API Events Response Status Code: {response.status_code}")
            print(f"The Odds API Events Raw Response: {response.text}")

            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []

        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                st.error("Invalid API key for The Odds API. Check configuration.")
                return []
            elif response.status_code == 429:
                retries += 1
                wait_time = initial_delay * (2 ** retries)
                st.warning(f"The Odds API rate limit reached. Retrying in {wait_time} seconds... (Attempt {retries}/{max_retries})")
                time.sleep(wait_time)
            else:
                st.error(f"Error fetching events from The Odds API: {response.status_code} - {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            st.error(f"Network error fetching events from The Odds API: {e}")
            return []

    st.error("API rate limit reached for The Odds API. Try again later.")
    return []

@st.cache_data
def fetch_props(event_id, max_retries=3, initial_delay=2):
    """Fetch player props from The Odds API (cached to reduce API calls)."""
    api_key = st.secrets.get("odds_api_key", None)
    if not api_key:
        st.error("Invalid API key for The Odds API. Check configuration.")
        return {}

    markets = "player_points,player_rebounds,player_assists,player_steals,player_blocks"
    url = f"{ODDS_API_URL}/sports/basketball_nba/events/{event_id}/odds?regions=us&markets={markets}&oddsFormat=american&apiKey={api_key}"
    
    retries = 0
    while retries < max_retries:
        try:
            time.sleep(initial_delay)
            response = requests.get(url, timeout=10)
            print(f"The Odds API Props Request URL: {response.url}")
            print(f"The Odds API Props Response Status Code: {response.status_code}")
            print(f"The Odds API Props Raw Response: {response.text}")

            response.raise_for_status()
            data = response.json()

            props = {}
            if 'bookmakers' in data and data['bookmakers']:
                for bookmaker in data['bookmakers'][:1]:  # Use first bookmaker for simplicity
                    for market in bookmaker['markets']:
                        prop_type = market['key'].replace('player_', '')
                        for outcome in market['outcomes']:
                            if 'point' in outcome:
                                prop_name = f"{outcome['description']} {outcome['name']} {outcome['point']} {prop_type}"
                                odds = outcome['price']
                                props[prop_name] = {
                                    'odds': odds,
                                    'prop_type': prop_type,
                                    'point': outcome['point']
                                }
            if not props:
                st.info(f"No props available for event {event_id} from the bookmaker.")
            return props

        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                st.error("Invalid API key for The Odds API. Check configuration.")
                return {}
            elif response.status_code == 429:
                retries += 1
                wait_time = initial_delay * (2 ** retries)
                st.warning(f"The Odds API rate limit reached. Retrying in {wait_time} seconds... (Attempt {retries}/{max_retries})")
                time.sleep(wait_time)
            else:
                st.error(f"Error fetching props from The Odds API: {response.status_code} - {response.text}")
                return {}
        except requests.exceptions.RequestException as e:
            st.error(f"Network error fetching props from The Odds API: {e}")
            return {}

    st.error("API rate limit reached for The Odds API. Try again later.")
    return {}

def get_initial_confidence(odds):
    """Calculate a simple confidence score based on odds."""
    if odds <= -300:
        return 0.9
    elif -299 <= odds <= -200:
        return 0.8
    elif -199 <= odds <= -100:
        return 0.7
    elif -99 <= odds <= 100:
        return 0.6
    else:
        return 0.5

def detect_line_discrepancies(book_odds, confidence):
    """Detect discrepancies between book odds and confidence score."""
    implied_odds = 1 / (1 + (abs(book_odds) / 100) if book_odds < 0 else (book_odds / 100) + 1)
    return confidence > implied_odds * 1.1  # Flag if confidence is 10% higher

def american_odds_to_string(odds):
    """Convert odds to string format with + or -."""
    if odds > 0:
        return f"+{int(odds)}"
    return str(int(odds))

def calculate_parlay_odds(odds_list):
    """Calculate combined parlay odds from a list of American odds."""
    if not odds_list:
        return 0
    decimal_odds = [1 + (abs(odds) / 100) if odds < 0 else (odds / 100) + 1 for odds in odds_list]
    final_decimal_odds = np.prod(decimal_odds)
    if final_decimal_odds > 2:
        american_odds = (final_decimal_odds - 1) * 100
    else:
        american_odds = -100 / (final_decimal_odds - 1)
    return round(american_odds, 0)

def get_sharp_money_insights(selected_props):
    """Simulate sharp money insights."""
    insights = {}
    for game, props in selected_props.items():
        for prop in props:
            odds = [item['odds'] for item in selected_props[game] if item['prop'] == prop][0]
            sharp_indicator = "🔥 Sharp Money Detected" if odds <= -150 else "Public Money"
            odds_shift = random.uniform(-0.05, 0.15)
            insights[prop] = {"Sharp Indicator": sharp_indicator, "Odds Shift %": round(odds_shift * 100, 2)}
    return insights
