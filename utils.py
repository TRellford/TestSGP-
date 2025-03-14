import requests
import numpy as np
from datetime import date
import streamlit as st
import time
import random
from nba_api.stats.endpoints import ScoreboardV2, BoxScoreTraditionalV2
from nba_api.stats.static import teams

# Constants
BALL_DONT_LIE_API_URL = "https://api.balldontlie.io/v1"
ODDS_API_URL = "https://api.the-odds-api.com/v4"
NBA_API_BASE = "https://stats.nba.com/stats"  # Placeholder for NBA API base URL

# Team name normalization to handle discrepancies
TEAM_NAME_MAPPING = {
    "los angeles clippers": "la clippers",
    "golden state warriors": "golden state warriors",
    # Add more as needed
}

def normalize_team_name(name):
    """Normalize team names for consistent matching between APIs."""
    name = name.lower().strip()
    return TEAM_NAME_MAPPING.get(name, name)

def normalize_player_name(name):
    """Normalize player names for consistent matching."""
    return name.lower().strip()

def fetch_games(date, max_retries=3, initial_delay=2):
    """Fetch NBA games from the NBA API with a fallback to Balldontlie API."""
    retries = 0
    while retries < max_retries:
        try:
            time.sleep(initial_delay)
            # Try NBA API first
            scoreboard = ScoreboardV2(game_date=date.strftime("%Y-%m-%d"))
            games_data = scoreboard.get_dict().get("resultSets", [])[0].get("rowSet", [])

            if not games_data:
                # Fallback to Balldontlie API
                st.warning("No games found via NBA API. Falling back to Balldontlie API.")
                api_key = st.secrets.get("balldontlie_api_key", None)
                if not api_key:
                    raise Exception("No Balldontlie API key available.")
                url = f"{BALL_DONT_LIE_API_URL}/games"
                params = {"dates[]": date.strftime("%Y-%m-%d")}
                headers = {"Authorization": api_key}
                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                games_data = response.json().get("data", [])
                if not games_data:
                    return []

                formatted_games = []
                for game in games_data:
                    home_team_info = game["home_team"]
                    away_team_info = game["visitor_team"]
                    formatted_games.append({
                        "home_team": home_team_info["full_name"],
                        "away_team": away_team_info["full_name"],
                        "game_id": game["id"],
                        "date": game["date"],
                        "start_time": game.get("date", "")  # Balldontlie uses "date" as a timestamp
                    })
                return formatted_games

            formatted_games = []
            for game in games_data:
                home_team_id = game[6]  # HOME_TEAM_ID
                away_team_id = game[4]  # VISITOR_TEAM_ID

                home_team_info = next(t for t in teams.get_teams() if t["id"] == home_team_id)
                away_team_info = next(t for t in teams.get_teams() if t["id"] == away_team_id)

                formatted_games.append({
                    "home_team": home_team_info["full_name"],
                    "away_team": away_team_info["full_name"],
                    "game_id": game[0],  # GAME_ID
                    "date": date.strftime("%Y-%m-%d"),
                    "start_time": game[2]  # GAME_DATE_EST (includes time)
                })
            return formatted_games

        except Exception as e:
            retries += 1
            wait_time = initial_delay * (2 ** retries)
            print(f"Exception caught: {type(e).__name__} - {str(e)}")
            st.warning(f"API request failed. Retrying in {wait_time} seconds... (Attempt {retries}/{max_retries})")
            time.sleep(wait_time)
            if retries == max_retries:
                st.error(f"Failed to fetch games after {max_retries} attempts: {e}")
                return []

def fetch_player_stats(player_name, season="2024", opponent_team=None, max_retries=3, initial_delay=2):
    """Fetch player season stats and historical performance from Balldontlie API."""
    api_key = st.secrets.get("balldontlie_api_key", None)
    if not api_key:
        st.error("Invalid API key for Balldontlie API. Check configuration.")
        return None

    # Step 1: Find the player ID by name
    url = f"{BALL_DONT_LIE_API_URL}/players"
    headers = {"Authorization": api_key}
    params = {"search": player_name}

    retries = 0
    while retries < max_retries:
        try:
            time.sleep(initial_delay)
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            players = response.json().get("data", [])
            if not players:
                return None
            player_id = players[0]["id"]
            break
        except requests.exceptions.RequestException as e:
            retries += 1
            wait_time = initial_delay * (2 ** retries)
            if retries == max_retries:
                st.error(f"Failed to fetch player ID from Balldontlie API: {e}")
                return None
            time.sleep(wait_time)

    # Step 2: Fetch season averages
    url = f"{BALL_DONT_LIE_API_URL}/season_averages"
    params = {"season": season, "player_ids[]": player_id}

    retries = 0
    while retries < max_retries:
        try:
            time.sleep(initial_delay)
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            stats = response.json().get("data", [])
            if not stats:
                return None
            season_stats = stats[0]
            break
        except requests.exceptions.RequestException as e:
            retries += 1
            wait_time = initial_delay * (2 ** retries)
            if retries == max_retries:
                st.error(f"Failed to fetch season stats from Balldontlie API: {e}")
                return None
            time.sleep(wait_time)

    # Step 3: Fetch historical performance vs opponent (if specified)
    historical_stats = None
    if opponent_team:
        url = f"{BALL_DONT_LIE_API_URL}/stats"
        params = {
            "player_ids[]": player_id,
            "seasons[]": season,
            "per_page": 100
        }
        retries = 0
        while retries < max_retries:
            try:
                time.sleep(initial_delay)
                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                game_logs = response.json().get("data", [])
                opponent_games = []
                for game in game_logs:
                    if game["team"]["full_name"] != opponent_team:
                        is_home_team = game["game"]["home_team_id"] == game["team"]["id"]
                        is_away_team = game["game"]["visitor_team_id"] == game["team"]["id"]
                        home_opponent_match = is_home_team and game["game"]["visitor_team"]["full_name"] == opponent_team
                        away_opponent_match = is_away_team and game["game"]["home_team"]["full_name"] == opponent_team
                        if home_opponent_match or away_opponent_match:
                            opponent_games.append(game)

                if opponent_games:
                    historical_stats = {
                        "pts": np.mean([game["pts"] for game in opponent_games]),
                        "reb": np.mean([game["reb"] for game in opponent_games]),
                        "ast": np.mean([game["ast"] for game in opponent_games]),
                        "stl": np.mean([game["stl"] for game in opponent_games]),
                        "blk": np.mean([game["blk"] for game in opponent_games]),
                        "games_played": len(opponent_games)
                    }
                break
            except requests.exceptions.RequestException as e:
                retries += 1
                wait_time = initial_delay * (2 ** retries)
                if retries == max_retries:
                    st.error(f"Failed to fetch game logs from Balldontlie API: {e}")
                    return season_stats
                time.sleep(wait_time)

    return {"season": season_stats, "historical": historical_stats}

def fetch_odds_api_events(date, max_retries=3, initial_delay=2):
    """Fetch all NBA events from The Odds API for a given date."""
    api_key = st.secrets.get("odds_api_key", None)
    if not api_key:
        st.error("Invalid API key for The Odds API. Check configuration.")
        return []

    url = f"{ODDS_API_URL}/sports/basketball_nba/events"
    params = {
        "date": date.strftime("%Y-%m-%d"),
        "apiKey": api_key,
        "regions": "us",
        "oddsFormat": "american"
    }
    
    retries = 0
    while retries < max_retries:
        try:
            time.sleep(initial_delay)
            response = requests.get(url, params=params, timeout=10)
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
            retries += 1
            wait_time = initial_delay * (2 ** retries)
            st.warning(f"Network error fetching events from The Odds API: {e}. Retrying in {wait_time} seconds... (Attempt {retries}/{max_retries})")
            time.sleep(wait_time)

    st.error("API rate limit reached for The Odds API. Try again later.")
    return []

@st.cache_data
def fetch_props(event_id, max_retries=3, initial_delay=2):
    """Fetch player props from The Odds API with support for alternative lines."""
    api_key = st.secrets.get("odds_api_key", None)
    if not api_key:
        st.error("Invalid API key for The Odds API. Check configuration.")
        return {}

    markets = "player_points,player_rebounds,player_assists"
    url = f"{ODDS_API_URL}/sports/basketball_nba/events/{event_id}/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": markets,
        "oddsFormat": "american"
    }
    
    retries = 0
    while retries < max_retries:
        try:
            time.sleep(initial_delay)
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            props = {}
            if 'bookmakers' in data and data['bookmakers']:
                for bookmaker in data['bookmakers'][:1]:  # Use first bookmaker for simplicity
                    for market in bookmaker['markets']:
                        prop_type = market['key'].replace('player_', '')
                        for outcome in market['outcomes']:
                            if 'point' in outcome:
                                player = outcome['description']
                                direction = outcome['name']  # "Over" or "Under"
                                key = f"{player}_{prop_type}_{direction}"
                                if key not in props:
                                    props[key] = []
                                props[key].append({
                                    'prop_name': f"{player} {direction} {outcome['point']} {prop_type}",
                                    'odds': outcome['price'],
                                    'prop_type': prop_type,
                                    'point': outcome['point'],
                                    'direction': direction,
                                    'player': player
                                })
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
            retries += 1
            wait_time = initial_delay * (2 ** retries)
            st.warning(f"Network error fetching props from The Odds API: {e}. Retrying in {wait_time} seconds... (Attempt {retries}/{max_retries})")
            time.sleep(wait_time)

    st.error("API rate limit reached for The Odds API. Try again later.")
    return {}

def adjust_confidence_with_stats(confidence, avg_stat, prop_line, direction, historical_stat=None):
    """Adjust confidence score based on player's season average and historical performance."""
    if avg_stat is None:
        return confidence

    # Adjust based on season average
    if direction.lower() == "over":
        adjustment = (avg_stat - prop_line) / prop_line if prop_line > 0 else 0
    else:  # Under
        adjustment = (prop_line - avg_stat) / prop_line if prop_line > 0 else 0
    confidence = min(max(confidence + adjustment * 0.3, 0), 1)  # Weight season stats at 30%

    # Further adjust based on historical performance vs opponent (if available)
    if historical_stat:
        hist_stat = historical_stat
        if direction.lower() == "over":
            hist_adjustment = (hist_stat - prop_line) / prop_line if prop_line > 0 else 0
        else:  # Under
            hist_adjustment = (prop_line - hist_stat) / prop_line if prop_line > 0 else 0
        confidence = min(max(confidence + hist_adjustment * 0.2, 0), 1)  # Weight historical stats at 20%

    return confidence

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
    """Simulate sharp money insights (placeholder for odds movement tracking)."""
    insights = {}
    for game, props in selected_props.items():
        for prop_item in props:
            prop = prop_item['prop_name']
            odds = prop_item['odds']
            sharp_indicator = "🔥 Sharp Money Detected" if odds <= -150 else "Public Money"
            odds_shift = random.uniform(-0.05, 0.15)
            insights[prop] = {"Sharp Indicator": sharp_indicator, "Odds Shift %": round(odds_shift * 100, 2)}
    return insights
