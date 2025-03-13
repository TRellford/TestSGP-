import requests
import numpy as np

def fetch_games():
    """Fetch the list of available NBA games from Balldontlie API."""
    url = "https://www.balldontlie.io/api/v1/games?start_date=today&end_date=today"
    headers = {"Authorization": "Bearer YOUR_API_KEY"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses (e.g., 401, 500)

        data = response.json()
        if "data" in data and len(data["data"]) > 0:
            return [f"{game['home_team']['abbreviation']} v {game['visitor_team']['abbreviation']}" for game in data['data']]
        else:
            return ["No games available"]
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching games: {e}")
        return ["Error fetching games"]

def fetch_props(game):
    """Fetch player props for a given game from The Odds API."""
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds?regions=us&markets=player_points,player_rebounds,player_assists&oddsFormat=american&apiKey=YOUR_API_KEY"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        props = {}
        for game_data in data:
            if game in game_data['teams']:  # Ensure correct game selection
                for bookmaker in game_data['bookmakers']:
                    for market in bookmaker['markets']:
                        for outcome in market['outcomes']:
                            prop_name = f"{outcome['name']} Over {outcome['point']}"
                            props[prop_name] = {'odds': outcome['price'], 'confidence': "High"}
        return props
    return {}

def calculate_parlay_odds(odds_list):
    """Calculate the final combined parlay odds."""
    decimal_odds = [1 + (abs(odds)/100) if odds < 0 else (odds/100) + 1 for odds in odds_list]
    final_odds = np.prod(decimal_odds)
    return round(final_odds, 2)

def get_sharp_money_insights(selected_props):
    """Fetch sharp money insights from a betting trends API."""
    url = "https://api.sportsinsights.com/sharp_betting_trends"
    headers = {"Authorization": "Bearer YOUR_API_KEY"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        trends_data = response.json()
        insights = {}
        for game, props in selected_props.items():
            for prop in props:
                insights[prop] = {"Sharp Money %": trends_data.get(prop, {}).get("sharp_money", np.random.randint(50, 90))}
        return insights
    return {}
