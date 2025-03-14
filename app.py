import streamlit as st
from datetime import date
from utils import (
    fetch_games, fetch_odds_api_events, fetch_props, fetch_player_stats,
    calculate_parlay_odds, get_initial_confidence, get_sharp_money_insights,
    detect_line_discrepancies, american_odds_to_string, normalize_team_name,
    normalize_player_name, adjust_confidence_with_stats
)

# Streamlit UI Setup
st.set_page_config(page_title="NBA SGP+ Builder", layout="wide")
st.title("NBA Same Game Parlay Builder")
st.markdown("Build your NBA Same Game Parlay below!")

# Automatically use today's date
current_date = date.today()

# Sidebar for Filters
st.sidebar.subheader("Filters")

# Odds Range Filter
use_odds_filter = st.sidebar.checkbox("Apply Odds Range Filter", value=False)
min_odds, max_odds = -1000, 1000  # Default: no filtering
if use_odds_filter:
    min_odds = st.sidebar.number_input("Min Odds", min_value=-1000, max_value=1000, value=-350, step=10)
    max_odds = st.sidebar.number_input("Max Odds", min_value=-1000, max_value=1000, value=200, step=10)

# Prop Type Selection
st.sidebar.subheader("Prop Types to Include")
prop_types = st.sidebar.multiselect(
    "Select Prop Types",
    options=["points", "rebounds", "assists", "steals", "blocks"],
    default=["points", "rebounds", "assists", "steals", "blocks"],
    help="Choose which prop types to include in your SGP."
)

# Number of Props per Game
st.sidebar.subheader("Props per Game")
props_per_game = st.sidebar.number_input(
    "Number of Props per Game", min_value=1, max_value=8, value=3, step=1,
    help="Select how many props to include per game (1-8)."
)

# Fetch Games from NBA API
games = fetch_games(current_date)

if not games:
    st.info("No NBA games scheduled for today.")
else:
    # Fetch Events from The Odds API
    odds_api_events = fetch_odds_api_events(current_date)
    
    if not odds_api_events:
        st.info("No odds available for today's NBA games yet.")
    else:
        # Debugging Output: Show fetched games and events
        st.write("**Games from NBA API:**", [f"{game['display']} (Start: {game['start_time']})" for game in games])
        st.write("**Events from The Odds API:**", [f"{event['home_team']} vs {event['away_team']}" for event in odds_api_events])

        # Map NBA API games to The Odds API events
        mapped_games = []
        unmatched_games = []
        for game in games:
            game_display = game["display"]
            home_team = normalize_team_name(game["home_team"])
            away_team = normalize_team_name(game["away_team"])
            matching_event = next(
                (event for event in odds_api_events
                 if normalize_team_name(event["home_team"]) == home_team
                 and normalize_team_name(event["away_team"]) == away_team),
                None
            )
            if matching_event:
                game["odds_api_event_id"] = matching_event["id"]
                mapped_games.append(game)
            else:
                unmatched_games.append(game_display)

        if unmatched_games:
            st.warning(f"⚠️ No matching events found in The Odds API for: {', '.join(unmatched_games)}")

        if not mapped_games:
            st.info("No matching events found in The Odds API for today's games.")
        else:
            # Game Selection
            game_displays = [f"{game['display']} (Start: {game['start_time']})" for game in mapped_games]
            selected_displays = st.multiselect(
                "Select 2-12 Games",
                game_displays,
                default=None,
                help="Choose between 2 and 12 NBA games to build your SGP.",
                max_selections=12
            )
            selected_games = [
                game for game in mapped_games
                if f"{game['display']} (Start: {game['start_time']})" in selected_displays
            ]

            if len(selected_games) < 2:
                st.warning("⚠️ Please select at least 2 games to build an SGP.")
            else:
                total_props = 0
                selected_props = {}
                odds_list = []
                game_prop_data = []

                # Analyze Each Game and Select Top Props
                for selected_game in selected_games:
                    available_props = fetch_props(selected_game['odds_api_event_id'])
                    if not available_props:
                        st.warning(f"⚠️ No props available for {selected_game['display']}. Check API key, rate limits, or game availability.")
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
                        st.info(f"No props available for {selected_game['display']} within the selected odds range or prop types.")
                        continue

                    # Calculate confidence for each prop, incorporating player stats
                    prop_confidence_list = []
                    for key, prop_list in filtered_props.items():
                        player = prop_list[0]['player']
                        prop_type = prop_list[0]['prop_type']
                        direction = prop_list[0]['direction']

                        # Fetch player stats from Balldontlie
                        opponent_team = selected_game['home_team'] if selected_game['away_team'] != player else selected_game['away_team']
                        player_stats = fetch_player_stats(player, opponent_team=opponent_team)
                        stat_key = prop_type[:3]  # e.g., "pts" for points, "reb" for rebounds
                        season_stat = player_stats['season'].get(stat_key, None) if player_stats and 'season' in player_stats else None
                        historical_stat = player_stats['historical'].get(stat_key, None) if player_stats and player_stats.get('historical') else None

                        for prop_data in prop_list:
                            confidence_score = get_initial_confidence(prop_data['odds'])
                            confidence_score = adjust_confidence_with_stats(
                                confidence_score, season_stat, prop_data['point'], prop_data['direction'], historical_stat
                            )
                            line_discrepancy = detect_line_discrepancies(prop_data['odds'], confidence_score)
                            prop_confidence_list.append({
                                "prop_name": prop_data['prop_name'],
                                "confidence": confidence_score,
                                "odds": prop_data['odds'],
                                "line_discrepancy": "🔥" if line_discrepancy else "",
                                "player_stat_key": f"{player}_{prop_type}",  # e.g., "LeBron_James_points"
                                "prop_type": prop_type,
                                "direction": direction,
                                "point": prop_data['point']
                            })

                    # Sort by confidence
                    prop_confidence_list = sorted(prop_confidence_list, key=lambda x: x['confidence'], reverse=True)

                    # Select top N props while avoiding conflicts
                    selected_prop_keys = set()  # Track selected player_stat combinations
                    game_selected_props = []
                    for prop_item in prop_confidence_list:
                        player_stat_key = prop_item['player_stat_key']
                        if player_stat_key not in selected_prop_keys and len(game_selected_props) < props_per_game:
                            selected_prop_keys.add(player_stat_key)
                            game_selected_props.append(prop_item)

                    selected_props[selected_game['display']] = game_selected_props
                    total_props += len(game_selected_props)

                    # Calculate combined odds for this game
                    game_odds = [item['odds'] for item in game_selected_props]
                    game_combined_odds = calculate_parlay_odds(game_odds) if game_odds else 0
                    odds_list.extend(game_odds)

                    # Store data for display
                    game_prop_data.append({
                        "game": selected_game,
                        "props": game_selected_props,
                        "combined_odds": game_combined_odds,
                        "num_props": len(game_selected_props)
                    })

                # Enforce Max 24 Props Across All Games
                if total_props > 24:
                    st.error("⚠️ You can select a maximum of 24 total props across all games.")
                elif total_props > 0:
                    # Display Suggested Props per Game
                    for game_data in game_prop_data:
                        game = game_data['game']
                        props = game_data['props']
                        combined_odds = game_data['combined_odds']
                        num_props = game_data['num_props']

                        st.markdown(f"**SGP: {game['home_team']} @ {game['away_team']}** {american_odds_to_string(combined_odds)}")
                        st.write(f"{num_props} SELECTIONS  Start: {game['start_time']}")
                        for prop in props:
                            st.markdown(f"- {prop['prop_name']} {prop['line_discrepancy']}")
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
                else:
                    st.info("No props available for the selected games after applying filters.")
