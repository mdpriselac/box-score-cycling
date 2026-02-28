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
    scrape_or_load_startlist,
    match_riders_to_db,
    get_latest_rider_snapshots,
    compute_field_features,
    get_reference_race_profile,
    average_race_profiles,
    assemble_prediction_df,
    search_historical_races,
    get_selected_race_details,
    detect_race_stages,
    scrape_or_load_results,
    compute_characteristics_from_results,
    compare_race_characteristics,
    evaluate_predictions_against_actual,
    get_race_finishing_characteristics,
)
from cycling_project.prediction_tools.model_registry import ModelRegistry


MODEL_DIR = str(Path(__file__).parent.parent.parent / "models" / "production")


def _decimal_to_american(d: float) -> str:
    """Convert decimal odds to American moneyline format."""
    if d >= 2.0:
        return f"+{round((d - 1) * 100)}"
    if d > 1.0:
        return f"-{round(100 / (d - 1))}"
    return "—"


def _decimal_to_fractional(d: float) -> str:
    """Convert decimal odds to fractional (British) format."""
    from fractions import Fraction
    profit = d - 1
    if profit >= 10:
        # Long shots: round to X/1
        return f"{round(profit)}/1"
    if profit <= 0:
        return "—"
    frac = Fraction(profit).limit_denominator(10)
    return str(frac)

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
force_refresh_startlist = st.checkbox("Force refresh start list", value=False)

if st.button("Get Start List") and url:
    try:
        race_id, year = parse_firstcycling_url(url)
        with st.spinner(f"Loading start list for race {race_id}, year {year}..."):
            teams, from_cache = scrape_or_load_startlist(race_id, year, force_refresh=force_refresh_startlist)
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
        st.session_state['fc_race_id'] = race_id
        st.session_state['race_name'] = get_race_name(race_id)
        st.session_state['race_year'] = year
        st.session_state['startlist_from_cache'] = from_cache
        # Clear old predictions and results when new start list is loaded
        st.session_state.pop('all_predictions', None)
        st.session_state.pop('actual_results', None)
        st.session_state.pop('race_stages', None)
    except Exception as e:
        st.error(f"Error: {e}")

# Show start list results
if 'matched' in st.session_state and not st.session_state['matched'].empty:
    if 'race_name' in st.session_state:
        st.subheader(f"{st.session_state['race_name']} {st.session_state['race_year']}")
        if st.session_state.get('startlist_from_cache'):
            st.caption("Start list loaded from cache")

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

        # Get enriched details for selected races
        comp_ids = list(selected_refs.keys())
        details_df = get_selected_race_details(comp_ids)
        st.session_state['reference_details'] = details_df

        # Main profile table
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

        # Finishing Time Distributions expander
        if not details_df.empty and 'biggest_group_metric' in details_df.columns:
            with st.expander("Finishing Time Distributions"):
                char_cols = {
                    'display_name': 'Race',
                    'biggest_group_metric': 'Biggest Group',
                    'time_gap_evenness_metric': 'Evenness',
                    'clumpiness_score': 'Clumpiness',
                    'selection_metric': 'Selection',
                    'total_race_duration': 'Duration (s)',
                    'variance_normalized': 'Variance',
                    'skewness_normalized': 'Skewness',
                    'gini_coefficient': 'Gini',
                    'total_finishers': 'Finishers',
                    'abandon_ratio': 'Abandon %',
                    'largest_group_size': 'Largest Group',
                    'proportion_in_groups': 'In Groups %',
                }
                available = [c for c in char_cols if c in details_df.columns]
                char_df = details_df[available].copy()
                char_df = char_df.rename(columns=char_cols)
                # Format numeric columns
                for col in char_df.columns:
                    if col not in ['Race', 'Finishers', 'Largest Group', 'Duration (s)']:
                        char_df[col] = char_df[col].apply(
                            lambda v: f"{v:.3f}" if pd.notna(v) else ""
                        )
                st.dataframe(char_df, hide_index=True, width='stretch')

        # Field Composition expander
        if not details_df.empty and 'field_size' in details_df.columns:
            with st.expander("Field Composition"):
                field_cols = {
                    'display_name': 'Race',
                    'field_size': 'Field Size',
                    'experience_mean': 'Avg Experience',
                    'bucket_mean': 'Avg Bucket',
                    'sprinter_count': 'Sprinters',
                    'climber_count': 'Climbers',
                    'hilly_specialist_count': 'Hilly',
                    'rolling_specialist_count': 'Rolling',
                    'breakaway_specialist_count': 'Breakaway',
                    'time_trialist_count': 'TT',
                }
                available = [c for c in field_cols if c in details_df.columns]
                field_df = details_df[available].copy()
                field_df = field_df.rename(columns=field_cols)
                for col in ['Avg Experience', 'Avg Bucket']:
                    if col in field_df.columns:
                        field_df[col] = field_df[col].apply(
                            lambda v: f"{v:.1f}" if pd.notna(v) else ""
                        )
                st.dataframe(field_df, hide_index=True, width='stretch')

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
                    result = race_ranker.predict_race(pred_df, return_details=True)
                    result['team'] = result['rider_id'].map(
                        lambda rid: name_map.get(rid, {}).get('team_name', '')
                    )

                    label = f"{profile['competition_name']} ({profile['competition_date']})"
                    all_predictions[label] = result

                # Average prediction (always, even for 1 race)
                avg_profile = average_race_profiles(reference_profiles)
                pred_df = assemble_prediction_df(snapshots, matched, field_features, avg_profile)
                result = race_ranker.predict_race(pred_df, return_details=True)
                result['team'] = result['rider_id'].map(
                    lambda rid: name_map.get(rid, {}).get('team_name', '')
                )
                all_predictions['Averaged Reference Races'] = result

                st.session_state['all_predictions'] = all_predictions
                st.session_state['reference_profiles'] = reference_profiles
                # Clear old actual results when new predictions are run
                st.session_state.pop('actual_results', None)
                st.session_state.pop('eval_results', None)

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

                if 'is_contender' in result.columns:
                    cols_to_show.append('is_contender')
                    col_rename['is_contender'] = 'Contender'

                if 'predicted_time_gap' in result.columns:
                    cols_to_show.append('predicted_time_gap')
                    col_rename['predicted_time_gap'] = 'Time Gap (s)'

                # Add cumulative probability columns if available
                has_probs = 'prob_win' in result.columns
                if has_probs:
                    cols_to_show.extend(['prob_win', 'prob_podium', 'prob_top5', 'prob_top15'])
                    col_rename.update({
                        'prob_win': 'Win %',
                        'prob_podium': 'Podium %',
                        'prob_top5': 'Top 5 %',
                        'prob_top15': 'Top 15 %',
                    })

                display = result[cols_to_show].copy().rename(columns=col_rename)
                display['Expected Bucket'] = display['Expected Bucket'].round(2)
                if 'Contender' in display.columns:
                    display['Contender'] = display['Contender'].map({True: 'Yes', False: ''})
                if 'Time Gap (s)' in display.columns:
                    display['Time Gap (s)'] = display['Time Gap (s)'].round(0).astype(int)
                if has_probs:
                    display['Win %'] = (result['prob_win'] * 100).round(1)
                    display['Podium %'] = (result['prob_podium'] * 100).round(1)
                    display['Top 5 %'] = (result['prob_top5'] * 100).round(1)
                    display['Top 15 %'] = (result['prob_top15'] * 100).round(1)

                st.dataframe(
                    display,
                    hide_index=True,
                    width='stretch',
                )

                # Odds view in expander
                if has_probs:
                    with st.expander("Odds"):
                        odds_format = st.radio(
                            "Format",
                            ["Decimal", "American", "Fractional"],
                            horizontal=True,
                            key=f"odds_fmt_{label}",
                        )

                        id_cols = ['predicted_rank', 'rider_name', 'team']
                        id_rename = {
                            'predicted_rank': 'Rank',
                            'rider_name': 'Rider',
                            'team': 'Team',
                        }
                        if 'is_contender' in result.columns:
                            id_cols.append('is_contender')
                            id_rename['is_contender'] = 'Contender'

                        decimal_cols = ['odds_win', 'odds_podium', 'odds_top5',
                                        'odds_top15', 'odds_top30']
                        market_names = {
                            'odds_win': 'Win',
                            'odds_podium': 'Podium',
                            'odds_top5': 'Top 5',
                            'odds_top15': 'Top 15',
                            'odds_top30': 'Top 30',
                        }

                        available_id = [c for c in id_cols if c in result.columns]
                        available_dec = [c for c in decimal_cols if c in result.columns]
                        odds_display = result[available_id + available_dec].copy()
                        odds_display = odds_display.rename(columns=id_rename)

                        if 'Contender' in odds_display.columns:
                            odds_display['Contender'] = odds_display['Contender'].map({True: 'Yes', False: ''})

                        if odds_format == "Decimal":
                            odds_display = odds_display.rename(columns=market_names)

                        elif odds_format == "American":
                            for col, name in market_names.items():
                                if col in odds_display.columns:
                                    odds_display[name] = odds_display[col].apply(_decimal_to_american)
                                    odds_display = odds_display.drop(columns=[col])

                        elif odds_format == "Fractional":
                            for col, name in market_names.items():
                                if col in odds_display.columns:
                                    odds_display[name] = odds_display[col].apply(_decimal_to_fractional)
                                    odds_display = odds_display.drop(columns=[col])

                        st.dataframe(
                            odds_display,
                            hide_index=True,
                            width='stretch',
                        )


# ── Step 4: Compare with Actual Results ──────────────────────────────────

if 'all_predictions' in st.session_state and 'fc_race_id' in st.session_state:
    st.header("4. Compare with Actual Results")

    fc_race_id = st.session_state['fc_race_id']
    race_year = st.session_state['race_year']

    # ── 4a. Stage detection & selection ──
    if 'race_stages' not in st.session_state:
        with st.spinner("Checking for stages..."):
            is_stage_race, stages = detect_race_stages(fc_race_id, race_year)
        st.session_state['race_stages'] = (is_stage_race, stages)
    else:
        is_stage_race, stages = st.session_state['race_stages']

    selected_stage_id = None
    selected_stage_param = None

    if is_stage_race and stages:
        stage_names = [s['name'] for s in stages]
        selected_stage_name = st.selectbox("Select stage to compare", stage_names)
        selected_stage = next(s for s in stages if s['name'] == selected_stage_name)
        selected_stage_id = selected_stage['url_param']
        selected_stage_param = selected_stage['url_param']

    # ── 4b. Fetch results ──
    col1, col2 = st.columns([3, 1])
    with col1:
        force_refresh_results = st.checkbox("Force re-scrape results", value=False)
    with col2:
        get_results_btn = st.button("Get Actual Results", type="primary")

    if get_results_btn:
        with st.spinner("Loading actual results..."):
            actual_df, winning_time = scrape_or_load_results(
                fc_race_id, race_year,
                stage_id=selected_stage_id,
                stage_url_param=selected_stage_param,
                force_refresh=force_refresh_results,
            )
        if actual_df is not None and not actual_df.empty:
            st.session_state['actual_results'] = actual_df
            st.session_state['winning_time'] = winning_time
            # Clear old eval results
            st.session_state.pop('eval_results', None)
        else:
            st.warning("No results found. The race may not have been completed yet.")

    if 'actual_results' in st.session_state:
        actual_df = st.session_state['actual_results']

        # ── 4c. Actual results display ──
        st.subheader("Actual Race Results")
        actual_display_cols = ['place', 'rider_name']
        actual_rename = {'place': 'Place', 'rider_name': 'Rider'}
        if 'team_name' in actual_df.columns:
            actual_display_cols.append('team_name')
            actual_rename['team_name'] = 'Team'
        if 'time_gap' in actual_df.columns:
            actual_display_cols.append('time_gap')
            actual_rename['time_gap'] = 'Time Gap (s)'
        if 'place_bucket' in actual_df.columns:
            actual_display_cols.append('place_bucket')
            actual_rename['place_bucket'] = 'Bucket'

        available_cols = [c for c in actual_display_cols if c in actual_df.columns]
        actual_show = actual_df[available_cols].copy().rename(
            columns={k: v for k, v in actual_rename.items() if k in available_cols}
        )
        st.dataframe(actual_show, hide_index=True, width='stretch')

        # ── 4d. Side-by-side comparison ──
        predictions = st.session_state['all_predictions']
        st.subheader("Predicted vs Actual")

        pred_tabs = st.tabs(list(predictions.keys()))
        for tab, (label, pred_result) in zip(pred_tabs, predictions.items()):
            with tab:
                if 'rider_id' in pred_result.columns and 'rider_id' in actual_df.columns:
                    merged = pred_result.merge(
                        actual_df[['rider_id', 'place', 'time_gap', 'place_bucket']].dropna(subset=['rider_id']).rename(
                            columns={
                                'place': 'actual_place',
                                'time_gap': 'actual_gap',
                                'place_bucket': 'actual_bucket',
                            }
                        ),
                        on='rider_id',
                        how='inner',
                    ).sort_values('predicted_rank')

                    if not merged.empty:
                        compare_cols = ['predicted_rank', 'rider_name', 'team',
                                        'ranking_derived_bucket', 'actual_place',
                                        'actual_bucket']
                        compare_rename = {
                            'predicted_rank': 'Pred Rank',
                            'rider_name': 'Rider',
                            'team': 'Team',
                            'ranking_derived_bucket': 'Pred Bucket',
                            'actual_place': 'Actual Place',
                            'actual_bucket': 'Actual Bucket',
                        }
                        if 'predicted_time_gap' in merged.columns:
                            compare_cols.append('predicted_time_gap')
                            compare_rename['predicted_time_gap'] = 'Pred Gap (s)'
                        if 'actual_gap' in merged.columns:
                            compare_cols.append('actual_gap')
                            compare_rename['actual_gap'] = 'Actual Gap (s)'

                        avail = [c for c in compare_cols if c in merged.columns]
                        compare_display = merged[avail].copy().rename(
                            columns={k: v for k, v in compare_rename.items() if k in avail}
                        )
                        for col in ['Pred Bucket', 'Actual Bucket']:
                            if col in compare_display.columns:
                                compare_display[col] = compare_display[col].apply(
                                    lambda v: int(v) if pd.notna(v) else ''
                                )
                        if 'Pred Gap (s)' in compare_display.columns:
                            compare_display['Pred Gap (s)'] = compare_display['Pred Gap (s)'].apply(
                                lambda v: f"{v:.0f}" if pd.notna(v) else ''
                            )
                        if 'Actual Gap (s)' in compare_display.columns:
                            compare_display['Actual Gap (s)'] = compare_display['Actual Gap (s)'].apply(
                                lambda v: f"{v:.0f}" if pd.notna(v) and isinstance(v, (int, float)) else str(v) if pd.notna(v) else ''
                            )
                        st.dataframe(compare_display, hide_index=True, width='stretch')
                    else:
                        st.info("No riders matched between predictions and actual results.")
                else:
                    st.info("Cannot compare — missing rider IDs.")

        # ── 4e. Prediction accuracy metrics ──
        st.subheader("Prediction Accuracy")

        if 'eval_results' not in st.session_state:
            eval_results = evaluate_predictions_against_actual(
                predictions, actual_df
            )
            st.session_state['eval_results'] = eval_results

        eval_results = st.session_state['eval_results']

        if eval_results:
            # Summary table
            summary_rows = []
            for label, metrics in eval_results.items():
                row = {'Prediction': label, 'Riders Matched': metrics.get('n_matched', 0)}
                if 'ranking' in metrics:
                    row['Kendall Tau'] = f"{metrics['ranking']['kendall_tau']:.3f}"
                    row['Top-3 Precision'] = f"{metrics['ranking']['top3_precision']:.1%}"
                    row['Top-5 Precision'] = f"{metrics['ranking']['top5_precision']:.1%}"
                if 'bucket' in metrics:
                    row['Bucket MAE'] = f"{metrics['bucket']['mae']:.2f}"
                    row['Bucket Accuracy'] = f"{metrics['bucket']['accuracy']:.1%}"
                    row['Within-1'] = f"{metrics['bucket']['within_1']:.1%}"
                if 'time_gap' in metrics:
                    row['TG MAE (s)'] = f"{metrics['time_gap']['mae']:.0f}"
                # Mark best predictions
                best_for = metrics.get('best_for', [])
                if best_for:
                    row['Best For'] = ', '.join(best_for)
                summary_rows.append(row)

            if summary_rows:
                summary_df = pd.DataFrame(summary_rows)
                st.dataframe(summary_df, hide_index=True, width='stretch')

            # Detailed metrics per prediction
            with st.expander("Detailed Metrics"):
                for label, metrics in eval_results.items():
                    st.markdown(f"**{label}**")
                    detail_cols = st.columns(3)
                    with detail_cols[0]:
                        if 'bucket' in metrics:
                            st.caption("Bucket Metrics")
                            for k, v in metrics['bucket'].items():
                                if isinstance(v, float):
                                    st.text(f"  {k}: {v:.3f}")
                                else:
                                    st.text(f"  {k}: {v}")
                    with detail_cols[1]:
                        if 'ranking' in metrics:
                            st.caption("Ranking Metrics")
                            for k, v in metrics['ranking'].items():
                                if isinstance(v, float):
                                    st.text(f"  {k}: {v:.3f}")
                                else:
                                    st.text(f"  {k}: {v}")
                    with detail_cols[2]:
                        if 'time_gap' in metrics:
                            st.caption("Time Gap Metrics")
                            for k, v in metrics['time_gap'].items():
                                if isinstance(v, float):
                                    st.text(f"  {k}: {v:.1f}")
                                else:
                                    st.text(f"  {k}: {v}")
                    st.divider()

        # ── 4f. Race characteristics comparison ──
        winning_time = st.session_state.get('winning_time')
        if winning_time and actual_df is not None:
            actual_chars = compute_characteristics_from_results(actual_df, winning_time)

            if actual_chars:
                st.subheader("Race Characteristics Comparison")

                # Get reference characteristics
                ref_chars_list = []
                selected_refs = st.session_state.get('selected_refs', {})
                for comp_id, ref_info in selected_refs.items():
                    chars = get_race_finishing_characteristics(comp_id)
                    if chars:
                        chars['label'] = ref_info.get('display_name', str(comp_id))
                        ref_chars_list.append(chars)

                # Add averaged profile characteristics if available
                if len(ref_chars_list) > 1:
                    avg_chars = {}
                    for key in actual_chars:
                        vals = [c[key] for c in ref_chars_list if c.get(key) is not None]
                        avg_chars[key] = sum(vals) / len(vals) if vals else 0
                    avg_chars['label'] = 'Averaged Reference Races'
                    ref_chars_list.append(avg_chars)

                if ref_chars_list:
                    comparison_df = compare_race_characteristics(actual_chars, ref_chars_list)

                    if not comparison_df.empty:
                        # Highlight most similar
                        most_similar_row = comparison_df[comparison_df['most_similar']].iloc[0]
                        st.success(
                            f"Most similar reference race: **{most_similar_row['label']}** "
                            f"(similarity: {most_similar_row['similarity']:.3f})"
                        )

                        # Best prediction callout
                        if eval_results:
                            best_ranking_labels = [
                                l for l, m in eval_results.items()
                                if 'ranking' in (m.get('best_for') or [])
                            ]
                            if best_ranking_labels:
                                st.info(f"Best ranking prediction: **{best_ranking_labels[0]}**")

                        # Comparison table
                        with st.expander("Characteristic Details"):
                            # Build a comparison table: actual vs each reference
                            display_metrics = [
                                'biggest_group_metric', 'time_gap_evenness_metric',
                                'clumpiness_score', 'selection_metric',
                                'total_race_duration', 'gini_coefficient',
                            ]
                            comp_rows = [{'Metric': m, 'Actual': f"{actual_chars.get(m, 0):.3f}"}
                                         for m in display_metrics]
                            for ref in ref_chars_list:
                                label = ref.get('label', '')[:25]
                                for i, m in enumerate(display_metrics):
                                    comp_rows[i][label] = f"{ref.get(m, 0):.3f}" if ref.get(m) is not None else ''

                            comp_table = pd.DataFrame(comp_rows)
                            st.dataframe(comp_table, hide_index=True, width='stretch')

                            # Similarity scores table
                            sim_display = comparison_df[['label', 'similarity', 'distance']].copy()
                            sim_display.columns = ['Reference Race', 'Similarity', 'Distance']
                            sim_display['Similarity'] = sim_display['Similarity'].apply(lambda v: f"{v:.3f}")
                            sim_display['Distance'] = sim_display['Distance'].apply(lambda v: f"{v:.3f}")
                            st.dataframe(sim_display, hide_index=True, width='stretch')
