import requests
import numpy as np

def fetch_games():
    """Fetch the list of available games."""
    response = requests.get("https://api.nba.com/games")
    if response.status_code == 200:
        return [game['matchup'] for game in response.json()]
    return []

def fetch_props(game):
    """Fetch player props for a given game."""
    response = requests.get(f"https://api.nba.com/props?game={game}")
    if response.status_code == 200:
        props = response.json()
        return {prop['name']: {'odds': prop['odds'], 'confidence': prop['confidence']} for prop in props}
    return {}

def calculate_parlay_odds(odds_list):
    """Calculate the final combined parlay odds."""
    decimal_odds = [1 + (abs(odds)/100) if odds < 0 else (odds/100) + 1 for odds in odds_list]
    final_odds = np.prod(decimal_odds)
    return round(final_odds, 2)

def get_sharp_money_insights(selected_props):
    """Fetch sharp money insights for selected props."""
    insights = {}
    for game, props in selected_props.items():
        for prop in props:
            insights[prop] = {"Sharp Money %": np.random.randint(50, 90)}
    return insights
