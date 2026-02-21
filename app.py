"""
Created on Fri Feb 20 12:25:21 2026

@author: sid
"""

# app.py — F1 2025 Championship Story Visualizer
# Run with:  streamlit run app.py

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

import config
from data_fetcher import F1DataFetcher
from points_calculator import ChampionshipStoryCalculator
import visualisations as viz
import telemetry_analysis as tel

# ── Page config ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="F1 2025 Championship Story",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Dark F1-themed styling */
    .stApp { background-color: #0D0D0D; color: #E0E0E0; }
    .css-1d391kg, section[data-testid="stSidebar"] {
        background-color: #111111 !important;
    }
    h1, h2, h3 { color: #FF1801 !important; }
    .metric-card {
        background: #1A1A1A;
        border: 1px solid #2A2A2A;
        border-left: 4px solid #FF1801;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 8px 0;
    }
    .metric-card h4 { color: #888; font-size: 0.8rem; margin: 0 0 4px 0; text-transform: uppercase; }
    .metric-card p  { color: #E0E0E0; font-size: 1.6rem; font-weight: bold; margin: 0; }
    .champion-banner {
        background: linear-gradient(135deg, #1A1A1A 0%, #2A1A00 100%);
        border: 2px solid #FFD700;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin-bottom: 24px;
    }
    .champion-banner h2 { color: #FFD700 !important; font-size: 2rem; margin: 0; }
    .champion-banner p  { color: #E0E0E0; font-size: 1.1rem; margin: 8px 0 0 0; }
    div[data-testid="stPlotlyChart"] { border-radius: 12px; overflow: hidden; }
    .stSelectbox label, .stMultiSelect label { color: #E0E0E0 !important; }
    .stMarkdown h3 { border-bottom: 1px solid #2A2A2A; padding-bottom: 8px; }
</style>
""", unsafe_allow_html=True)


# ── Data loading (cached) ────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    fetcher   = F1DataFetcher()
    standings = fetcher.get_standings_after_each_race()
    schedule  = fetcher.get_race_schedule()
    return standings, schedule


@st.cache_data(ttl=3600, show_spinner=False)
def compute_metrics(standings_df):
    calc = ChampionshipStoryCalculator(standings_df)
    return calc


# ── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🏎️ F1 2025")
    st.markdown("**Championship Story Visualizer**")
    st.markdown("---")

    page = st.radio(
        "Navigate",
        [
            "🏆 Season Overview",
            "📈 Points Evolution",
            "📉 Gap to Leader",
            "🔴 Verstappen Comeback",
            "🔥 Momentum Heatmap",
            "⚔️  Head-to-Head",
            "📊 Season Phases",
            "🎯 Consistency Analysis",
            "🏁 Final Stretch",
            "─── Telemetry ───",
            "⚡ Speed Traces",
            "🗺️ Circuit Speed Map",
            "🎮 Pedal & Gear Traces",
            "⏱️ Race Lap Progression",
            "🟩 Sector Deltas",
            "🏎️ Tyre Stint Analysis",
            "📍 Championship Moments",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")

    all_drivers = config.ALL_2025_DRIVERS
    highlighted = st.multiselect(
        "Highlight drivers",
        all_drivers,
        default=config.TITLE_CONTENDERS,
    )
    st.markdown("---")
    st.caption("Data: Jolpica API (Ergast successor) + FastF1")
    st.caption("Built with Streamlit + Plotly")


# ── Header ───────────────────────────────────────────────────────────────────────
st.markdown(
    '<h1 style="font-size:2.2rem;">🏎️ F1 2025 — Championship Story</h1>',
    unsafe_allow_html=True
)

# ── Load data ─────────────────────────────────────────────────────────────────────
with st.spinner("Loading 2025 season data..."):
    try:
        standings, schedule = load_data()
        calc = compute_metrics(standings)
        data_loaded = not standings.empty
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        st.info("Make sure you have an internet connection. The app fetches live data from the Jolpica F1 API.")
        data_loaded = False

if not data_loaded:
    st.stop()

# Pre-compute shared datasets
gap_df       = calc.get_championship_gap()
per_race_df  = calc.get_points_per_race()
momentum_df  = calc.get_momentum_scores(window=4)
comeback_df  = calc.get_verstappen_comeback_story()
phase_df     = calc.get_season_phases()
final_stnd   = calc.get_championship_summary()
race_labels  = (
    schedule["name"].tolist()
    if not schedule.empty
    else standings["race_name"].drop_duplicates().sort_values().tolist()
)

# ════════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def _telemetry_controls(default_round: int = 24):
    """Inline controls rendered above telemetry charts."""
    col1, col2, col3 = st.columns(3)
    all_codes = list(config.DRIVER_CODE_MAP.keys())
    round_num = col1.selectbox(
        "Round", list(range(1, config.TOTAL_ROUNDS + 1)),
        index=default_round - 1,
        format_func=lambda r: f"Rd {r} — {schedule[schedule['round']==r]['name'].values[0].replace(' Grand Prix',' GP') if not schedule.empty and r in schedule['round'].values else r}"
    )
    driver_a = col2.selectbox("Driver A", all_codes,
                              index=all_codes.index("VER") if "VER" in all_codes else 0)
    driver_b = col3.selectbox("Driver B", all_codes,
                              index=all_codes.index("NOR") if "NOR" in all_codes else 1)
    session_type = col1.radio("Session", ["Q", "R", "S"], horizontal=True,
                              help="Q=Qualifying, R=Race, S=Sprint")
    return round_num, driver_a, driver_b, session_type


# ════════════════════════════════════════════════════════════════════════════════
# PAGE ROUTING
# ════════════════════════════════════════════════════════════════════════════════

# ── 🏆 Season Overview ───────────────────────────────────────────────────────────
if page == "🏆 Season Overview":

    # Champion banner
    if not final_stnd.empty:
        champion = final_stnd.iloc[0]
        runner_up = final_stnd.iloc[1] if len(final_stnd) > 1 else None
        margin = int(champion["points"] - runner_up["points"]) if runner_up is not None else 0

        st.markdown(f"""
        <div class="champion-banner">
            <h2>🏆 {champion['driver']} — 2025 World Champion</h2>
            <p>{int(champion['points'])} Championship Points
            {"| Won by just <b>" + str(margin) + " point" + ("s" if margin != 1 else "") + "</b> — one of the closest titles in history!" if margin <= 5 else ""}
            </p>
        </div>
        """, unsafe_allow_html=True)

    # KPI metrics
    total_rounds = standings["round"].max()
    ver_row = final_stnd[final_stnd["driver"] == "Max Verstappen"]
    ver_pts  = int(ver_row["points"].values[0]) if not ver_row.empty else "N/A"
    ver_wins = int(ver_row["wins"].values[0]) if not ver_row.empty else "N/A"
    max_deficit = int(comeback_df["gap_to_leader"].max()) if not comeback_df.empty else "N/A"

    c1, c2, c3, c4, c5 = st.columns(5)
    metrics = [
        (c1, "Total Races",          f"{total_rounds}"),
        (c2, "Championship Margin",  f"{margin} pts"),
        (c3, "VER Final Points",     f"{ver_pts}"),
        (c4, "VER Race Wins",        f"{ver_wins}"),
        (c5, "VER Max Deficit",      f"{max_deficit} pts"),
    ]
    for col, label, value in metrics:
        col.markdown(f"""
        <div class="metric-card">
            <h4>{label}</h4>
            <p>{value}</p>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Final Championship Standings")

    # Color-coded standings table
    def color_driver_row(row):
        team  = config.DRIVER_TEAMS.get(row["Driver"], "Unknown")
        color = config.TEAM_COLORS.get(team, "#333333")
        # Convert hex to rgba for background (Streamlit styler needs valid CSS)
        hex_c = color.lstrip("#")
        r, g, b = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
        bg    = f"rgba({r},{g},{b},0.15)"
        return [f"background-color: {bg}; border-left: 3px solid {color}"] * len(row)

    if not final_stnd.empty:
        styled_df = (
            final_stnd.rename(columns={
                "position": "Pos", "driver": "Driver",
                "points": "Points", "wins": "Wins"
            })
        )
        st.dataframe(
            styled_df.style.apply(color_driver_row, axis=1),
            use_container_width=True, height=600,
        )

    st.markdown("---")
    st.markdown("### 2025 Race Calendar")
    if not schedule.empty:
        display_sched = schedule.rename(columns={
            "round": "Rd", "name": "Grand Prix", "circuit": "Circuit",
            "country": "Country", "date": "Date", "has_sprint": "Sprint?"
        })
        st.dataframe(display_sched, use_container_width=True)


# ── 📈 Points Evolution ──────────────────────────────────────────────────────────
elif page == "📈 Points Evolution":
    st.markdown("### Championship Points Evolution")
    st.caption("Bold lines = selected drivers. Faint lines = rest of the grid.")
    fig = viz.plot_championship_evolution(standings, highlight_drivers=highlighted)
    st.plotly_chart(fig, use_container_width=True)


# ── 📉 Gap to Leader ─────────────────────────────────────────────────────────────
elif page == "📉 Gap to Leader":
    st.markdown("### Points Gap to Championship Leader")
    st.caption("0 = leading the championship. Further down = further behind.")
    drivers_to_show = st.multiselect(
        "Select drivers", list(config.DRIVER_TEAMS.keys()),
        default=config.TITLE_CONTENDERS
    )
    fig = viz.plot_gap_to_leader(gap_df, highlight_drivers=drivers_to_show)
    st.plotly_chart(fig, use_container_width=True)


# ── 🔴 Verstappen Comeback ───────────────────────────────────────────────────────
elif page == "🔴 Verstappen Comeback":
    st.markdown("### The Comeback Story — Max Verstappen 2025")

    if not comeback_df.empty:
        max_def = int(comeback_df["gap_to_leader"].max())
        def_round = comeback_df.loc[comeback_df["gap_to_leader"].idxmax(), "round"]
        def_race = comeback_df.loc[comeback_df["gap_to_leader"].idxmax(), "race_name"]

        col1, col2, col3 = st.columns(3)
        col1.markdown(f"""<div class="metric-card">
            <h4>Peak Deficit</h4><p>-{max_def} pts</p></div>""", unsafe_allow_html=True)
        col2.markdown(f"""<div class="metric-card">
            <h4>Lowest Point</h4><p>Round {int(def_round)}</p></div>""", unsafe_allow_html=True)
        col3.markdown(f"""<div class="metric-card">
            <h4>Race (Low Point)</h4><p>{def_race}</p></div>""", unsafe_allow_html=True)

        st.markdown("")

    fig = viz.plot_verstappen_comeback(comeback_df)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Round-by-Round Data")
    if not comeback_df.empty:
        st.dataframe(
            comeback_df[["round", "race_name", "points", "gap_to_leader", "leader", "phase"]]
            .rename(columns={
                "round": "Rd", "race_name": "Race", "points": "VER Points",
                "gap_to_leader": "Gap to Leader", "leader": "Leader", "phase": "Phase"
            }),
            use_container_width=True,
        )


# ── 🔥 Momentum Heatmap ──────────────────────────────────────────────────────────
elif page == "🔥 Momentum Heatmap":
    st.markdown("### Driver Momentum Heatmap")
    st.caption("Rolling 4-race average points. Red = peak form. Dark = struggling.")
    window = st.slider("Rolling window (races)", 2, 6, 4)
    momentum_df = calc.get_momentum_scores(window=window)
    fig = viz.plot_momentum_heatmap(momentum_df)
    st.plotly_chart(fig, use_container_width=True)


# ── ⚔️ Head-to-Head ──────────────────────────────────────────────────────────────
elif page == "⚔️  Head-to-Head":
    st.markdown("### Head-to-Head Championship Battle")

    col1, col2 = st.columns(2)
    all_drivers_list = sorted(standings["driver"].unique())

    driver_a = col1.selectbox(
        "Driver A", all_drivers_list,
        index=all_drivers_list.index("Max Verstappen") if "Max Verstappen" in all_drivers_list else 0
    )
    driver_b = col2.selectbox(
        "Driver B", all_drivers_list,
        index=all_drivers_list.index("Lando Norris") if "Lando Norris" in all_drivers_list else 1
    )

    if driver_a != driver_b:
        h2h_df = calc.get_head_to_head(driver_a, driver_b)
        fig = viz.plot_head_to_head(h2h_df, driver_a, driver_b, race_labels)
        st.plotly_chart(fig, use_container_width=True)

        # Summary stats
        if not h2h_df.empty:
            last = h2h_df.iloc[-1]
            a_pts = last.get(driver_a, 0)
            b_pts = last.get(driver_b, 0)
            winner = driver_a if a_pts >= b_pts else driver_b
            st.markdown(f"""
            **Final:** {driver_a.split()[-1]} {int(a_pts)} — {int(b_pts)} {driver_b.split()[-1]}  
            **Champion:** 🏆 {winner} (by {abs(int(a_pts) - int(b_pts))} pts)
            """)
    else:
        st.warning("Please select two different drivers.")


# ── 📊 Season Phases ─────────────────────────────────────────────────────────────
elif page == "📊 Season Phases":
    st.markdown("### Average Points Per Race — By Season Phase")
    st.caption(
        "Early / Mid / Late thirds of the season. "
        "Shows who peaked when — crucial context for Verstappen's comeback."
    )
    drivers_ph = st.multiselect(
        "Drivers to include", all_drivers,
        default=config.TITLE_CONTENDERS
    )
    phase_df_filtered = phase_df[phase_df["driver"].isin(drivers_ph)]
    fig = viz.plot_season_phases(phase_df_filtered)
    st.plotly_chart(fig, use_container_width=True)


# ── 🎯 Consistency Analysis ──────────────────────────────────────────────────────
elif page == "🎯 Consistency Analysis":
    st.markdown("### Consistency vs Peak Performance")
    st.caption(
        "X-axis = variability (higher = boom/bust seasons).  "
        "Y-axis = average points per race.  "
        "Bubble size = total points."
    )
    fig = viz.plot_consistency_scatter(per_race_df)
    st.plotly_chart(fig, use_container_width=True)


# ── 🏁 Final Stretch ─────────────────────────────────────────────────────────────
elif page == "🏁 Final Stretch":
    st.markdown("### Final Stretch — Championship Decider")
    st.caption("The races that decided the 2025 title.")

    col1, col2, col3 = st.columns(3)
    driver_a = col1.selectbox(
        "Driver 1", sorted(standings["driver"].unique()),
        index=list(sorted(standings["driver"].unique())).index("Max Verstappen")
        if "Max Verstappen" in standings["driver"].unique() else 0,
    )
    driver_b = col2.selectbox(
        "Driver 2", sorted(standings["driver"].unique()),
        index=list(sorted(standings["driver"].unique())).index("Lando Norris")
        if "Lando Norris" in standings["driver"].unique() else 1,
    )
    last_n = col3.slider("Races to show", 3, 8, 6)

    fig = viz.plot_final_stretch_waterfall(per_race_df, driver_a, driver_b, last_n)
    st.plotly_chart(fig, use_container_width=True)

    # Points earned table for final stretch
    total_rounds = sorted(per_race_df["round"].unique())
    final_rounds = total_rounds[-last_n:]
    fin_df = (
        per_race_df[
            per_race_df["round"].isin(final_rounds) &
            per_race_df["driver"].isin([driver_a, driver_b])
        ]
        [["round", "race_name", "driver", "points_earned"]]
        .sort_values(["round", "driver"])
        .rename(columns={
            "round": "Rd", "race_name": "Race",
            "driver": "Driver", "points_earned": "Points Earned"
        })
    )
    st.dataframe(fin_df, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TELEMETRY PAGES  (FastF1 — downloads data on first load per session)
# ════════════════════════════════════════════════════════════════════════════════


# ── ⚡ Speed Traces ─────────────────────────────────────────────────────────────
elif page == "⚡ Speed Traces":
    st.markdown("### Speed Trace Comparison")
    st.caption(
        "Overlay fastest laps for two drivers. "
        "The delta panel shows where each driver gains or loses time across the lap."
    )
    round_num, driver_a, driver_b, session_type = _telemetry_controls(24)

    if st.button("🔄 Load Telemetry", type="primary"):
        with st.spinner(f"Loading FastF1 data for Rd {round_num} {session_type}..."):
            try:
                fig = tel.plot_speed_trace(round_num, [driver_a, driver_b], session_type)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Could not load telemetry: {e}")
    else:
        st.info("Select a round and drivers, then click **Load Telemetry**. "
                "First load downloads FastF1 data (~30–120s). Subsequent loads use cache.")


# ── 🗺️ Circuit Speed Map ────────────────────────────────────────────────────────
elif page == "🗺️ Circuit Speed Map":
    st.markdown("### Circuit Speed Heatmap")
    st.caption(
        "The track layout coloured by speed — blue = braking zones, "
        "red = flat-out sections. Reveals the character of each circuit."
    )
    col1, col2, col3 = st.columns(3)
    all_codes   = list(config.DRIVER_CODE_MAP.keys())
    round_num   = col1.selectbox(
        "Round", list(range(1, config.TOTAL_ROUNDS + 1)), index=23,
        format_func=lambda r: f"Rd {r} — {schedule[schedule['round']==r]['name'].values[0].replace(' Grand Prix',' GP') if not schedule.empty and r in schedule['round'].values else r}"
    )
    driver_code = col2.selectbox("Driver", all_codes,
                                 index=all_codes.index("VER") if "VER" in all_codes else 0)
    session_type = col3.radio("Session", ["Q", "R"], horizontal=True)

    if st.button("🔄 Load Circuit Map", type="primary"):
        with st.spinner("Loading circuit telemetry..."):
            try:
                fig = tel.plot_circuit_speed_heatmap(round_num, driver_code, session_type)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Could not load telemetry: {e}")
    else:
        st.info("Select round and driver, then click **Load Circuit Map**.")


# ── 🎮 Pedal & Gear Traces ──────────────────────────────────────────────────────
elif page == "🎮 Pedal & Gear Traces":
    st.markdown("### Pedal Inputs & Gear Traces")
    st.caption(
        "4-panel view: Speed / Throttle / Brake / Gear across a lap. "
        "Shows driving style differences — who trails the brake later, who's more aggressive on throttle."
    )
    round_num, driver_a, driver_b, session_type = _telemetry_controls(24)

    if st.button("🔄 Load Pedal Traces", type="primary"):
        with st.spinner("Loading pedal data..."):
            try:
                fig = tel.plot_pedal_traces(round_num, [driver_a, driver_b], session_type)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Could not load telemetry: {e}")
    else:
        st.info("Select round and drivers, then click **Load Pedal Traces**.")


# ── ⏱️ Race Lap Progression ─────────────────────────────────────────────────────
elif page == "⏱️ Race Lap Progression":
    st.markdown("### Race Lap Time Progression")
    st.caption(
        "Lap-by-lap race times. Faded ✕ markers = pit stop / safety car laps. "
        "Steeper climbs = tyre degradation. Sudden drops = fresh rubber."
    )
    col1, col2, col3 = st.columns(3)
    all_codes = list(config.DRIVER_CODE_MAP.keys())
    round_num = col1.selectbox(
        "Round", list(range(1, config.TOTAL_ROUNDS + 1)), index=23,
        format_func=lambda r: f"Rd {r} — {schedule[schedule['round']==r]['name'].values[0].replace(' Grand Prix',' GP') if not schedule.empty and r in schedule['round'].values else r}"
    )
    driver_a = col2.selectbox("Driver A", all_codes,
                              index=all_codes.index("VER") if "VER" in all_codes else 0)
    driver_b = col3.selectbox("Driver B", all_codes,
                              index=all_codes.index("NOR") if "NOR" in all_codes else 1)

    if st.button("🔄 Load Race Laps", type="primary"):
        with st.spinner("Loading race lap data..."):
            try:
                fig = tel.plot_lap_time_progression(round_num, [driver_a, driver_b])
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Could not load telemetry: {e}")
    else:
        st.info("Select a race round and drivers, then click **Load Race Laps**.")


# ── 🟩 Sector Deltas ─────────────────────────────────────────────────────────────
elif page == "🟩 Sector Deltas":
    st.markdown("### Qualifying Sector Delta Heatmap")
    st.caption(
        "Gap to the session-fastest time in each sector. "
        "Green = near fastest, red = most time lost. Sorted by overall lap time."
    )
    col1, _ = st.columns([1, 2])
    round_num = col1.selectbox(
        "Round", list(range(1, config.TOTAL_ROUNDS + 1)), index=23,
        format_func=lambda r: f"Rd {r} — {schedule[schedule['round']==r]['name'].values[0].replace(' Grand Prix',' GP') if not schedule.empty and r in schedule['round'].values else r}"
    )

    if st.button("🔄 Load Sector Deltas", type="primary"):
        with st.spinner("Loading qualifying sector times..."):
            try:
                fig = tel.plot_sector_delta_heatmap(round_num)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Could not load telemetry: {e}")
    else:
        st.info("Select a qualifying round, then click **Load Sector Deltas**.")


# ── 🏎️ Tyre Stint Analysis ───────────────────────────────────────────────────────
elif page == "🏎️ Tyre Stint Analysis":
    st.markdown("### Tyre Stint & Strategy Analysis")
    st.caption(
        "Lap times coloured by compound — 🔴 Soft, 🟡 Medium, ⚪ Hard. "
        "Reveals strategy differences and degradation rates between drivers."
    )
    col1, col2, col3 = st.columns(3)
    all_codes = list(config.DRIVER_CODE_MAP.keys())
    round_num = col1.selectbox(
        "Round", list(range(1, config.TOTAL_ROUNDS + 1)), index=23,
        format_func=lambda r: f"Rd {r} — {schedule[schedule['round']==r]['name'].values[0].replace(' Grand Prix',' GP') if not schedule.empty and r in schedule['round'].values else r}"
    )
    driver_a = col2.selectbox("Driver A", all_codes,
                              index=all_codes.index("VER") if "VER" in all_codes else 0)
    driver_b = col3.selectbox("Driver B", all_codes,
                              index=all_codes.index("NOR") if "NOR" in all_codes else 1)

    if st.button("🔄 Load Tyre Data", type="primary"):
        with st.spinner("Loading race tyre data..."):
            try:
                fig = tel.plot_tyre_stint_analysis(round_num, [driver_a, driver_b])
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Could not load telemetry: {e}")
    else:
        st.info("Select a race round and drivers, then click **Load Tyre Data**.")


# ── 📍 Championship Moments ──────────────────────────────────────────────────────
elif page == "📍 Championship Moments":
    st.markdown("### Full Season Comeback Analysis")
    st.caption(
        "Three views of the 2025 championship story told through pure pace data — "
        "not points, not positions, but raw speed across the entire season."
    )

    tab1, tab2, tab3 = st.tabs([
        "🌊 Season Pace Arc",
        "🎯 Gap to Pole — Full Season",
        "📋 Qualifying Lap Trend",
    ])

    # ── Tab 1: Full season pace evolution (overlaid speed traces at checkpoints)
    with tab1:
        st.markdown("#### Season Pace Arc — Speed Traces at Key Narrative Moments")
        st.markdown(
            "Overlaid qualifying speed traces at **9 checkpoint rounds** across the season — "
            "coloured from 🔴 struggle phase through 🟡 turning point to 🟢 dominant recovery. "
            "Each line is the same circuit only where comparable (note: different circuits mean "
            "raw speeds vary — focus on the **shape and consistency** of each trace)."
        )

        col1, col2 = st.columns([1, 3])
        all_codes = list(config.DRIVER_CODE_MAP.keys())
        driver_code = col1.selectbox(
            "Driver", all_codes,
            index=all_codes.index("VER") if "VER" in all_codes else 0,
            key="pace_arc_driver"
        )

        # Let user customise which checkpoint rounds to include
        default_rounds = [c[0] for c in tel.COMEBACK_CHECKPOINTS]
        selected_rounds = col2.multiselect(
            "Checkpoint rounds to include",
            options=list(range(1, config.TOTAL_ROUNDS + 1)),
            default=default_rounds,
            format_func=lambda r: f"Rd {r} — {schedule[schedule['round']==r]['name'].values[0].replace(' Grand Prix',' GP') if not schedule.empty and r in schedule['round'].values else r}",
            key="pace_arc_rounds"
        )

        if st.button("🔄 Load Season Arc", type="primary", key="btn_arc"):
            # Build custom checkpoints from selected rounds
            # Map known rounds to their labels, use generic label for others
            round_label_map = {c[0]: (c[1], c[2], c[3]) for c in tel.COMEBACK_CHECKPOINTS}
            # Colour gradient for unknown rounds
            import colorsys
            custom_checkpoints = []
            for i, rnd in enumerate(sorted(selected_rounds)):
                if rnd in round_label_map:
                    label, color, note = round_label_map[rnd]
                else:
                    # Interpolate color based on position in season
                    frac = rnd / config.TOTAL_ROUNDS
                    r_val = int(255 * (1 - frac))
                    g_val = int(255 * frac)
                    color = f"#{r_val:02x}{g_val:02x}44"
                    label = f"Rd {rnd}"
                    note  = f"Round {rnd}"
                custom_checkpoints.append((rnd, label, color, note))

            with st.spinner(f"Loading {len(selected_rounds)} qualifying sessions... (cached rounds load instantly)"):
                try:
                    fig = tel.plot_season_pace_evolution(driver_code, custom_checkpoints)
                    st.plotly_chart(fig, use_container_width=True)
                    st.info(
                        f"💡 **Reading this chart:** Each line is a different circuit so absolute speeds "
                        f"vary. Focus on the **consistency and smoothness** of each trace — more erratic "
                        f"lines = more errors/lock-ups. The recovery phase lines (green) tend to be "
                        f"cleaner and smoother than the struggle phase (red)."
                    )
                except Exception as e:
                    st.error(f"Could not load telemetry: {e}")
        else:
            st.info(
                "Select a driver and checkpoint rounds, then click **Load Season Arc**. "
                "Defaults to 9 pre-selected narrative moments across the season. "
                "Cached rounds load instantly — new rounds take ~30s each."
            )

    # ── Tab 2: Gap to pole across all 24 qualifying sessions
    with tab2:
        st.markdown("#### Gap to Pole — Qualifying Pace Across the Entire Season")
        st.markdown(
            "Each driver's **gap to the session pole time** across all 24 qualifying sessions. "
            "Since everyone runs the same circuit, this eliminates track differences and shows "
            "**pure relative pace** across the season. The golden dashed line marks Round 15 → 16, "
            "where Verstappen's recovery begins. Solid lines = 3-race rolling average."
        )

        all_codes = list(config.DRIVER_CODE_MAP.keys())
        selected_drivers = st.multiselect(
            "Drivers to compare",
            all_codes,
            default=["VER", "NOR", "PIA", "RUS", "LEC"],
            format_func=lambda c: config.DRIVER_CODE_MAP.get(c, c),
            key="gap_pole_drivers"
        )

        st.warning(
            "⏳ This loads all 24 qualifying sessions. First run = ~10–20 minutes. "
            "All sessions cached after that — subsequent runs take seconds."
        )

        if st.button("🔄 Load Gap to Pole (All 24 Rounds)", type="primary", key="btn_gap_pole"):
            with st.spinner("Loading all 24 qualifying sessions... check terminal for progress."):
                try:
                    fig = tel.plot_gap_to_pole_trend(selected_drivers)
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Could not load telemetry: {e}")
        else:
            st.info("Click **Load Gap to Pole** to begin. Progress is shown in the terminal.")

    # ── Tab 3: Raw qualifying lap time trend
    with tab3:
        st.markdown("#### Qualifying Lap Time Trend — Raw Times Across the Season")
        st.caption(
            "Raw fastest qualifying lap times per round. Times are NOT comparable across circuits "
            "but useful for seeing within-round gaps and each driver's personal progression."
        )

        all_codes = list(config.DRIVER_CODE_MAP.keys())
        selected_drivers_lt = st.multiselect(
            "Drivers",
            all_codes,
            default=["VER", "NOR", "PIA"],
            format_func=lambda c: config.DRIVER_CODE_MAP.get(c, c),
            key="laptime_trend_drivers"
        )

        st.warning("⏳ Loads all 24 qualifying sessions — same caching as Gap to Pole above.")

        if st.button("🔄 Load Lap Time Trend", type="primary", key="btn_lt_trend"):
            with st.spinner("Loading qualifying sessions..."):
                try:
                    fig = tel.plot_qualifying_laptime_trend(selected_drivers_lt)
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Could not load telemetry: {e}")
        else:
            st.info("Click **Load Lap Time Trend** to begin.")


# ── Divider page (non-navigable) ─────────────────────────────────────────────
elif page == "─── Telemetry ───":
    st.info("👈 Select a telemetry page from the sidebar.")