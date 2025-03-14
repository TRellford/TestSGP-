import streamlit as st
from datetime import date
from utils import (
    fetch_games, fetch_odds_api_events, fetch_props, fetch_player_stats,
    calculate_parlay_odds, get_initial_confidence, get_sharp_money_insights,
    detect_line_discrepancies, american_odds_to_string, normalize_team_name,
    adjust_confidence_with_stats
)

# Streamlit UI Setup
st.set_page_config(page_title="NBA SGP Builder", layout="wide")
st.title("NBA Same Game Parlay Builder")
st.markdown("Build your NBA Same Game Parlay below!")

# Automatically use today's date
current_date = date.today()

# Sidebar for Filters
st.sidebar.subheader("Filters")
use_odds_filter = st.sidebar.checkbox("Apply Odds Range Filter", value=False)
min_odds, max_odds = -1000, 1000
if use_odds_filter:
    min_odds = st.sidebar.number_input("Min Odds", min_value=-1000, max_value=1000, value=-350, step=10)
    max_odds = st.sidebar.number_input("Max Odds", min_value=-1000, max_value=1000, value=200, step=10)

st.sidebar.subheader("Prop Types to Include")
prop_types = st.sidebar.multiselect(
    "Select Prop Types",
    options=["points", "rebounds", "assists"],
    default=["points", "rebounds", "assists"],
    help="Choose which prop types to include in your SGP."
)

st.sidebar.subheader("Confidence Level")
confidence_level = st.sidebar.selectbox(
    "Select Confidence Level",
    options=["High", "Medium", "Low"],
    index=1,
    help="Filter props based on confidence score."
)

st.sidebar.subheader("Props per Game")
props_per_game = st.sidebar.number_input(
    "Number of Props per Game", min_value=1, max_value=8, value=3, step=1,
    help="Select how many props to include per game (1-8)."
)

# Fetch Games
games = fetch_games(current_date)

if not games:
    st.info("No NBA games scheduled for today.")
else:
    # Fetch Events from The Odds API to map game IDs
    odds_api_events = fetch_odds_api_events(current_date)
    
    if not odds_api_events:
        st.info("No odds available for today's NBA games yet.")
    else:
        # Map games to Odds API events
        mapped_games = []
        for game in games:
            matching_event = next(
                (event for event in odds_api_events
                 if normalize_team_name(event["home_team"]) == normalize_team_name(game["home_team"])
                 and normalize_team_name(event["away_team"]) == normalize_team_name(game["away_team"])),
                None
            )
            if matching_event:
                game["odds_api_event_id"] = matching_event["id"]
                mapped_games.append(game)

        if not mapped_games:
            st.info("No matching events found in The Odds API for today's games.")
        else:
            # Game Selection
            game_displays = [f"{game['home_team']} vs {game['away_team']} (Start: {game['start_time']})" for game in mapped_games]
            selected_displays = st.multiselect(
                "Select Games",
                game_displays,
                default=None,
                help="Choose NBA games to build your SGP.",
                max_selections=12
            )
            selected_games = [
                game for game in mapped_games
                if f"{game['home_team']} vs {game['away_team']} (Start: {game['start_time']})" in selected_displays
            ]

            if not selected_games:
                st.warning("⚠️ Please select at least one game to build an SGP.")
            else:
                total_props = 0
                selected_props = {}
                odds_list = []
                game_prop_data = []

                # Analyze Each Game and Select Top Props
                for selected_game in selected_games:
                    event_id = selected_game.get("odds_api_event_id")
                    if not event_id:
                        st.warning(f"⚠️ No event ID found for {selected_game['home_team']} vs {selected_game['away_team']}. Skipping.")
                        continue

                    available_props = fetch_props(event_id)
                    if not available_props:
                        st.warning(f"⚠️ No props available for {selected_game['home_team']} vs {selected_game['away_team']}.")
                        continue

                    # Filter props by odds range and prop types
                    filtered_props = available_props
                    if use_odds_filter:
                        filtered_props = {
                            key: prop_list for key, prop_list in filtered_props.items()
                            if all(min_odds <= prop['odds'] <= max_odds for prop in prop_list)
                        }
                    if prop_types:
                        filtered_props = {
                            key: prop_list for key, prop_list in filtered_props.items()
                            if prop_list[0]['prop_type'] in prop_types
                        }

                    if not filtered_props:
                        st.info(f"No props available for {selected_game['home_team']} vs {selected_game['away_team']} within filters.")
                        continue

                    # Calculate confidence for each prop using player stats
                    prop_confidence_list = []
                    opponent_team = selected_game['home_team'] if selected_game['away_team'] != "N/A" else selected_game['home_team']
                    for key, prop_list in filtered_props.items():
                        player = prop_list[0]['player']
                        prop_type = prop_list[0]['prop_type']
                        direction = prop_list[0]['direction']
                        prop_line = prop_list[0]['point']

                        # Fetch player stats from Balldontlie
                        player_stats = fetch_player_stats(player, opponent_team=opponent_team)
                        stat_key = prop_type[:3]  # e.g., "pts" for points
                        season_stat = player_stats['season'].get(stat_key, None) if player_stats and 'season' in player_stats else None
                        historical_stat = player_stats['historical'].get(stat_key, None) if player_stats and player_stats.get('historical') else None

                        for prop_data in prop_list:
                            confidence_score = get_initial_confidence(prop_data['odds'])
                            confidence_score = adjust_confidence_with_stats(
                                confidence_score, season_stat, prop_line, direction, historical_stat
                            )
                            line_discrepancy = detect_line_discrepancies(prop_data['odds'], confidence_score)
                            prop_confidence_list.append({
                                "prop_name": prop_data['prop_name'],
                                "confidence": confidence_score,
                                "odds": prop_data['odds'],
                                "line_discrepancy": "🔥" if line_discrepancy else "",
                                "player_stat_key": f"{player}_{prop_type}",
                                "prop_type": prop_type,
                                "direction": direction,
                                "point": prop_line
                            })

                    # Sort by confidence and filter by confidence level
                    confidence_threshold = {"High": 80, "Medium": 60, "Low": 40}[confidence_level] / 100
                    prop_confidence_list = [
                        prop for prop in sorted(prop_confidence_list, key=lambda x: x['confidence'], reverse=True)
                        if prop['confidence'] * 100 >= confidence_threshold
                    ]

                    # Select top N props while avoiding conflicts
                    selected_prop_keys = set()
                    game_selected_props = []
                    for prop_item in prop_confidence_list:
                        player_stat_key = prop_item['player_stat_key']
                        if player_stat_key not in selected_prop_keys and len(game_selected_props) < props_per_game:
                            selected_prop_keys.add(player_stat_key)
                            game_selected_props.append(prop_item)

                    selected_props[selected_game['home_team'] + " vs " + selected_game['away_team']] = game_selected_props
                    total_props += len(game_selected_props)
                    odds_list.extend([item['odds'] for item in game_selected_props])

                    # Store data for display
                    game_prop_data.append({
                        "game": selected_game,
                        "props": game_selected_props,
                        "num_props": len(game_selected_props)
                    })

                if total_props == 0:
                    st.info("No props selected based on filters and confidence level.")
                else:
                    # Display Suggested Props per Game
                    for game_data in game_prop_data:
                        game = game_data['game']
                        props = game_data['props']
                        num_props = game_data['num_props']

                        st.markdown(f"**SGP: {game['home_team']} @ {game['away_team']}**")
                        st.write(f"{num_props} SELECTIONS  Start: {game['start_time']}")
                        for prop in props:
                            st.markdown(f"- {prop['prop_name']} ({american_odds_to_string(prop['odds'])}) {prop['line_discrepancy']}")
                        st.markdown("---")

                    # Final SGP Summary
                    final_odds = calculate_parlay_odds(odds_list)
                    st.subheader("Final SGP Summary")
                    st.write(f"**{total_props} Leg Same Game Parlay** {american_odds_to_string(final_odds)}")
                    st.write(f"Includes: {len(selected_games)} Games")

                    # Wager and Payout Calculation
                    wager = st.number_input("Wager ($)", min_value=0.0, value=10.0, step=0.5)
                    if final_odds > 0:
                        payout = wager * (final_odds / 100)
                    else:
                        payout = wager / (abs(final_odds) / 100)
                    st.write(f"To Win: ${round(payout, 2)}")

                    # Sharp Money Insights
                    st.subheader("Sharp Money Insights")
                    sharp_money_data = get_sharp_money_insights(selected_props)
                    st.table(sharp_money_data)

                    # Placeholder for Live Data (Future Enhancement)
                    st.subheader("Live Updates (Coming Soon)")
                    st.info("Live box scores and injury updates will be added in a future update.")
