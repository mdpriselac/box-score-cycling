"""
Cycling Race Prediction Web App

Run with: uv run streamlit run cycling_project/web/app.py
"""

import sys
from pathlib import Path

# Ensure the project root is on the path so cycling_project is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

from cycling_project.prediction_tools.future_race_loader import (
    parse_firstcycling_url,
    get_race_name,
    scrape_startlist,
    match_riders_to_db,
    get_latest_rider_snapshots,
    compute_field_features,
    get_reference_race_profile,
    average_race_profiles,
    assemble_prediction_df,
    search_historical_races,
)
from cycling_project.prediction_tools.model_registry import ModelRegistry


MODEL_DIR = str(Path(__file__).parent.parent.parent / "models" / "production")

st.set_page_config(page_title="Cycling Race Predictor", layout="wide")
st.title("Cycling Race Predictor")

# Initialize session state for selected references
if 'selected_refs' not in st.session_state:
    st.session_state['selected_refs'] = {}  # {comp_id: row_dict}
if 'search_counter' not in st.session_state:
    st.session_state['search_counter'] = 0


# ── Step 1: Scrape Start List ─────────────────────────────────────────────

st.header("1. Enter Race URL")
url = st.text_input(
    "FirstCycling race URL",
    placeholder="https://firstcycling.com/race.php?r=9&y=2026",
)

if st.button("Get Start List") and url:
    try:
        race_id, year = parse_firstcycling_url(url)
        with st.spinner(f"Scraping start list for race {race_id}, year {year}..."):
            teams = scrape_startlist(race_id, year)
            matched, unmatched = match_riders_to_db(teams)
            if not matched.empty:
                rider_ids = matched['rider_id'].tolist()
                snapshots = get_latest_rider_snapshots(rider_ids)
                field_features = compute_field_features(snapshots)
            else:
                snapshots = pd.DataFrame()
                field_features = {}

        st.session_state['teams'] = teams
        st.session_state['matched'] = matched
        st.session_state['unmatched'] = unmatched
        st.session_state['snapshots'] = snapshots
        st.session_state['field_features'] = field_features
        st.session_state['url'] = url
        st.session_state['race_name'] = get_race_name(race_id)
        st.session_state['race_year'] = year
        # Clear old predictions when new start list is scraped
        st.session_state.pop('all_predictions', None)
    except Exception as e:
        st.error(f"Error: {e}")

# Show start list results
if 'matched' in st.session_state and not st.session_state['matched'].empty:
    if 'race_name' in st.session_state:
        st.subheader(f"{st.session_state['race_name']} {st.session_state['race_year']}")

    matched = st.session_state['matched']
    unmatched = st.session_state['unmatched']

    col1, col2 = st.columns(2)
    with col1:
        st.success(f"Matched {len(matched)} riders in database")
        st.dataframe(
            matched[['rider_name', 'team_name', 'bib_number']].rename(
                columns={'rider_name': 'Rider', 'team_name': 'Team', 'bib_number': 'Bib'}
            ),
            hide_index=True,
            width='stretch',
        )
    with col2:
        if unmatched:
            st.warning(f"{len(unmatched)} riders not found in database")
            unmatched_df = pd.DataFrame(unmatched)[['rider_name', 'team_name', 'bib_number']].rename(
                columns={'rider_name': 'Rider', 'team_name': 'Team', 'bib_number': 'Bib'}
            )
            st.dataframe(unmatched_df, hide_index=True, width='stretch')
        else:
            st.success("All riders found in database")


# ── Step 2: Select Reference Races ────────────────────────────────────────

if 'matched' in st.session_state and not st.session_state['matched'].empty:
    st.header("2. Select Reference Races")

    # ── 2a. Currently selected races (always visible at top) ──
    selected_refs = st.session_state['selected_refs']

    if selected_refs:
        st.subheader(f"Selected ({len(selected_refs)}/5)")
        sel_rows = list(selected_refs.values())
        sel_df = pd.DataFrame(sel_rows)[[
            'competition_id', 'display_name', 'competition_date',
            'competition_type', 'race_dominant_profile',
            'race_sprint_score', 'race_mountain_score', 'race_hilly_score',
            'race_rolling_score', 'race_breakaway_score', 'race_time_trial_score',
        ]].copy()
        sel_df.columns = ['ID', 'Name', 'Date', 'Type', 'Profile',
                          'Sprint', 'Mtn', 'Hilly', 'Rolling', 'Breakaway', 'TT']
        for col in ['Sprint', 'Mtn', 'Hilly', 'Rolling', 'Breakaway', 'TT']:
            sel_df[col] = sel_df[col].apply(lambda v: f"{v:.2f}" if v is not None else "")
        st.dataframe(sel_df, hide_index=True, width='stretch')

        # Remove buttons
        cols = st.columns(min(len(selected_refs), 5))
        for i, (comp_id, ref) in enumerate(list(selected_refs.items())):
            with cols[i % len(cols)]:
                if st.button(f"Remove {ref['display_name'][:30]}...", key=f"rm_{comp_id}"):
                    del st.session_state['selected_refs'][comp_id]
                    st.rerun()

        if st.button("Clear all selections"):
            st.session_state['selected_refs'] = {}
            st.rerun()
    else:
        st.info("No reference races selected yet. Search below and add up to 5.")

    st.divider()

    # ── 2b. Search for races to add ──
    st.subheader("Search Historical Races")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        name_q = st.text_input("Race name", placeholder="Tour de France")
    with col2:
        year_q = st.number_input("Year", min_value=2010, max_value=2025, value=2024, step=1)
    with col3:
        cat_q = st.selectbox("Category", ["All", "wt", "pro", "d1"])
    with col4:
        type_q = st.selectbox("Type", ["All", "stage", "one_day", "gc"])

    if st.button("Search"):
        results = search_historical_races(
            name_filter=name_q if name_q else None,
            year_filter=int(year_q) if year_q else None,
            category_filter=cat_q if cat_q != "All" else None,
            type_filter=type_q if type_q != "All" else None,
            limit=200,
        )
        st.session_state['search_results'] = results
        st.session_state['search_counter'] += 1

    if 'search_results' in st.session_state and not st.session_state['search_results'].empty:
        results = st.session_state['search_results']

        # Show results with add checkboxes
        st.caption(f"{len(results)} results found")

        # Multi-select from search results
        already_selected = set(st.session_state['selected_refs'].keys())
        available = results[~results['competition_id'].isin(already_selected)].reset_index(drop=True)

        if available.empty:
            st.info("All search results are already selected.")
        else:
            display_df = available[[
                'competition_id', 'display_name', 'competition_date',
                'competition_type', 'race_category', 'field_size',
                'race_dominant_profile',
            ]].copy()
            display_df.columns = ['ID', 'Name', 'Date', 'Type', 'Category', 'Field Size', 'Profile']
            event = st.dataframe(
                display_df,
                hide_index=True,
                width='stretch',
                on_select="rerun",
                selection_mode="multi-row",
                key=f"search_results_table_{st.session_state['search_counter']}",
            )

            # ── Click-to-add from dataframe selection ──
            selected_rows = event.selection.rows
            if selected_rows:
                spots_left = 5 - len(st.session_state['selected_refs'])
                if spots_left <= 0:
                    st.warning("5/5 reference races selected. Remove one to add more.")
                else:
                    rows_to_add = selected_rows[:spots_left]
                    n_selected = len(selected_rows)
                    label = f"Add {len(rows_to_add)} selected race{'s' if len(rows_to_add) != 1 else ''}"
                    if n_selected > spots_left:
                        label += f" (only {spots_left} spot{'s' if spots_left != 1 else ''} left)"
                    if st.button(label, key="add_from_dataframe"):
                        for row_idx in rows_to_add:
                            comp_id = int(available.iloc[row_idx]['competition_id'])
                            if comp_id not in st.session_state['selected_refs']:
                                row = results[results['competition_id'] == comp_id]
                                if not row.empty:
                                    st.session_state['selected_refs'][comp_id] = row.iloc[0].to_dict()
                        st.rerun()

            st.divider()

            # Add by ID input
            spots_left = 5 - len(st.session_state['selected_refs'])
            if spots_left > 0:
                add_input = st.text_input(
                    f"Enter competition ID(s) to add (comma-separated, {spots_left} spot{'s' if spots_left != 1 else ''} left)",
                    placeholder="e.g. 141, 142, 10",
                    key="add_ids",
                )
                if st.button("Add to selection"):
                    if add_input:
                        try:
                            ids_to_add = [int(x.strip()) for x in add_input.split(',') if x.strip()]
                            added = 0
                            for cid in ids_to_add:
                                if added >= spots_left:
                                    break
                                if cid in st.session_state['selected_refs']:
                                    continue
                                row = results[results['competition_id'] == cid]
                                if not row.empty:
                                    st.session_state['selected_refs'][cid] = row.iloc[0].to_dict()
                                    added += 1
                                else:
                                    st.warning(f"ID {cid} not in current search results")
                            if added:
                                st.rerun()
                        except ValueError:
                            st.error("Enter valid comma-separated numbers")
            else:
                st.warning("5/5 reference races selected. Remove one to add more.")


# ── Step 3: Run Predictions ───────────────────────────────────────────────

if (
    st.session_state.get('selected_refs')
    and 'snapshots' in st.session_state
    and not st.session_state['snapshots'].empty
):
    st.header("3. Predictions")

    if st.button("Run Predictions", type="primary"):
        selected_refs = st.session_state['selected_refs']
        snapshots = st.session_state['snapshots']
        matched = st.session_state['matched']
        field_features = st.session_state['field_features']

        with st.spinner("Loading model and running predictions..."):
            try:
                # Load model (ensemble gives both bucket + time gap)
                registry = ModelRegistry(MODEL_DIR)
                bucket_pred, time_gap_pred, race_ranker = registry.load_with_ranker(
                    ranking_method='ensemble'
                )

                # Build name/team lookup
                name_map = matched.set_index('rider_id')[['rider_name', 'team_name']].to_dict('index')

                all_predictions = {}
                reference_profiles = []

                for comp_id in selected_refs:
                    profile = get_reference_race_profile(comp_id)
                    reference_profiles.append(profile)

                    pred_df = assemble_prediction_df(snapshots, matched, field_features, profile)
                    result = race_ranker.predict_race(pred_df, return_details=False)
                    result['team'] = result['rider_id'].map(
                        lambda rid: name_map.get(rid, {}).get('team_name', '')
                    )

                    label = f"{profile['competition_name']} ({profile['competition_date']})"
                    all_predictions[label] = result

                # Average prediction (always, even for 1 race)
                avg_profile = average_race_profiles(reference_profiles)
                pred_df = assemble_prediction_df(snapshots, matched, field_features, avg_profile)
                result = race_ranker.predict_race(pred_df, return_details=False)
                result['team'] = result['rider_id'].map(
                    lambda rid: name_map.get(rid, {}).get('team_name', '')
                )
                all_predictions['Averaged Reference Races'] = result

                st.session_state['all_predictions'] = all_predictions

            except Exception as e:
                st.error(f"Prediction error: {e}")
                import traceback
                st.code(traceback.format_exc())

    # Display predictions
    if 'all_predictions' in st.session_state:
        predictions = st.session_state['all_predictions']

        tabs = st.tabs(list(predictions.keys()))
        for tab, (label, result) in zip(tabs, predictions.items()):
            with tab:
                cols_to_show = ['predicted_rank', 'rider_name', 'team',
                                'expected_bucket', 'ranking_derived_bucket']
                col_rename = {
                    'predicted_rank': 'Rank',
                    'rider_name': 'Rider',
                    'team': 'Team',
                    'expected_bucket': 'Expected Bucket',
                    'ranking_derived_bucket': 'Predicted Bucket',
                }

                if 'predicted_time_gap' in result.columns:
                    cols_to_show.append('predicted_time_gap')
                    col_rename['predicted_time_gap'] = 'Time Gap (s)'

                display = result[cols_to_show].copy().rename(columns=col_rename)
                display['Expected Bucket'] = display['Expected Bucket'].round(2)
                if 'Time Gap (s)' in display.columns:
                    display['Time Gap (s)'] = display['Time Gap (s)'].round(0).astype(int)

                st.dataframe(
                    display,
                    hide_index=True,
                    width='stretch',
                )
