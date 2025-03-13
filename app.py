import streamlit as st
from utils import fetch_games, fetch_props, calculate_parlay_odds, get_sharp_money_insights

# Streamlit UI Setup
st.set_page_config(page_title="SGP+ Builder", layout="wide")
st.title("Same Game Parlay Plus (SGP+)")

# Fetch and Display Games
games = fetch_games()

if not games or games[0] in ["No games available", "Error fetching games"]:
    st.error("⚠️ No games available or issue fetching games. Please try again later.")
else:
    selected_games = st.multiselect("Select 2-12 Games", games, max_selections=12)

    if selected_games:
        total_props = 0
        selected_props = {}
        odds_list = []

        for game in selected_games:
            st.subheader(f"{game} Props")
            available_props = fetch_props(game)

            if not available_props:
                st.warning(f"⚠️ No props available for {game}.")
                continue
            
            # Select Props Per Game (Max 8)
            selected_props[game] = st.multiselect(f"Select Props for {game} (1-8)", list(available_props.keys()), max_selections=8)
            total_props += len(selected_props[game])

            # Display Props Table
            if selected_props[game]:
                selected_data = [available_props[prop] for prop in selected_props[game]]
                st.table(selected_data)
                
                # Store odds for final calculation
                odds_list.extend([available_props[prop]['odds'] for prop in selected_props[game]])

        # Ensure Max 24 Props Constraint
        if total_props > 24:
            st.error("⚠️ You can select a maximum of 24 total props across all games.")
        else:
            # Final Parlay Odds Calculation
            final_odds = calculate_parlay_odds(odds_list)
            st.subheader("Final SGP+ Odds")
            st.write(f"Combined Parlay Odds: {final_odds}")
            
            # Sharp Money Insights
            sharp_money_data = get_sharp_money_insights(selected_props)
            st.subheader("Sharp Money Insights")
            st.table(sharp_money_data)
