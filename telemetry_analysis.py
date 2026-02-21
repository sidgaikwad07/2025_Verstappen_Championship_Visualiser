#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 20 15:16:58 2026

@author: sid
"""
# telemetry_analysis.py — Advanced FastF1 Telemetry Analysis
#
# Provides:
#   1. Speed trace comparison      — two drivers overlaid on fastest lap
#   2. Circuit speed heatmap       — track map coloured by speed
#   3. Throttle / brake traces     — pedal inputs across a lap
#   4. Gear map                    — gear usage around the circuit
#   5. Lap time progression        — stint degradation during a race
#   6. Sector delta analysis       — mini-sector time gaps
#   7. Championship moment laps    — key race laps (nadir Rd15 + finale Rd24)
#
# All chart functions return Plotly figures — consumed directly by app.py
#
# Usage (standalone):
#   python telemetry_analysis.py
#
# NOTE: First run per session downloads ~50–200 MB of FastF1 data.
#       Subsequent runs use the local ./fastf1_cache/ directory.

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import fastf1
from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

import config

# ── FastF1 cache ────────────────────────────────────────────────────────────────
Path(config.CACHE_DIR).mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(config.CACHE_DIR)

# ── Shared dark theme ───────────────────────────────────────────────────────────
DARK_BG    = "#0D0D0D"
CARD_BG    = "#1A1A1A"
GRID_COLOR = "#2A2A2A"
TEXT_COLOR = "#E0E0E0"
ACCENT     = "#FF1801"

LAYOUT_BASE = dict(
    paper_bgcolor=DARK_BG,
    plot_bgcolor=CARD_BG,
    font=dict(color=TEXT_COLOR, family="Inter, Arial, sans-serif"),
    xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
    yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
    margin=dict(l=60, r=40, t=70, b=60),
    legend=dict(bgcolor=CARD_BG, bordercolor=GRID_COLOR, borderwidth=1),
)

def _driver_color(driver: str, round_number: int = config.TOTAL_ROUNDS) -> str:
    team = config.get_driver_team(driver, round_number)
    return config.TEAM_COLORS.get(team, "#AAAAAA")


def _hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    """Convert a #RRGGBB hex string to rgba(r,g,b,alpha) for Plotly fillcolor."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ══════════════════════════════════════════════════════════════════════════════
# SESSION LOADER  (cached at module level to avoid repeated API calls)
# ══════════════════════════════════════════════════════════════════════════════

_session_cache: dict = {}

def load_session(round_number: int, session_type: str = "Q") -> fastf1.core.Session:
    """
    Load and cache a FastF1 session.
    session_type: 'Q' = Qualifying, 'R' = Race, 'S' = Sprint
    """
    key = (round_number, session_type)
    if key not in _session_cache:
        print(f"[FastF1] Loading Round {round_number} — {session_type}...")
        session = fastf1.get_session(config.SEASON, round_number, session_type)
        session.load(telemetry=True, weather=True, messages=False, laps=True)
        _session_cache[key] = session
        print(f"[FastF1] ✅ Loaded: {session.event['EventName']} {session_type}")
    return _session_cache[key]


def get_fastest_lap(session: fastf1.core.Session, driver_code: str):
    """Return the fastest lap object for a driver in a session."""
    try:
        laps = session.laps.pick_drivers(driver_code)
        return laps.pick_fastest()
    except Exception as e:
        print(f"[FastF1] Could not get fastest lap for {driver_code}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 1. SPEED TRACE COMPARISON
# ══════════════════════════════════════════════════════════════════════════════

def plot_speed_trace(
    round_number: int,
    driver_codes: list[str],
    session_type: str = "Q",
) -> go.Figure:
    """
    Overlay speed traces for multiple drivers across a full lap.
    X = distance (m), Y = speed (km/h)
    Delta line shows gap to the fastest driver at each point.
    """
    session = load_session(round_number, session_type)
    event_name = session.event["EventName"]

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.72, 0.28],
        shared_xaxes=True,
        subplot_titles=["Speed Trace", "Delta to Fastest (s)"],
        vertical_spacing=0.08,
    )

    telemetry_data = {}
    for code in driver_codes:
        lap = get_fastest_lap(session, code)
        if lap is None:
            continue
        tel = lap.get_telemetry().add_distance()
        tel = tel.dropna(subset=["Distance", "Speed"])
        telemetry_data[code] = tel

        full_name = config.DRIVER_CODE_MAP.get(code, code)
        color     = _driver_color(full_name, round_number)

        # Format lap time cleanly (e.g. "1:23.456")
        try:
            total_s   = lap["LapTime"].total_seconds()
            mins      = int(total_s // 60)
            secs      = total_s % 60
            lap_label = f"{mins}:{secs:06.3f}"
        except Exception:
            lap_label = "N/A"

        fig.add_trace(go.Scatter(
            x=tel["Distance"], y=tel["Speed"],
            mode="lines", name=f"{code}  {lap_label}",
            line=dict(color=color, width=2),
            hovertemplate=f"<b>{code}</b> | dist: %{{x:.0f}}m | speed: <b>%{{y:.0f}} km/h</b><extra></extra>",
        ), row=1, col=1)

    # Delta line — compare each driver against the fastest
    if len(telemetry_data) == 2:
        codes_list  = list(telemetry_data.keys())
        ref_code    = codes_list[0]
        comp_code   = codes_list[1]
        ref_tel     = telemetry_data[ref_code]
        comp_tel    = telemetry_data[comp_code]

        # Interpolate onto common distance axis
        common_dist = np.linspace(
            max(ref_tel["Distance"].min(), comp_tel["Distance"].min()),
            min(ref_tel["Distance"].max(), comp_tel["Distance"].max()),
            1000,
        )
        ref_time  = np.interp(common_dist, ref_tel["Distance"],
                              ref_tel["SessionTime"].dt.total_seconds())
        comp_time = np.interp(common_dist, comp_tel["Distance"],
                              comp_tel["SessionTime"].dt.total_seconds())
        delta = comp_time - ref_time

        ref_color  = _driver_color(config.DRIVER_CODE_MAP.get(ref_code, ref_code), round_number)
        comp_color = _driver_color(config.DRIVER_CODE_MAP.get(comp_code, comp_code), round_number)

        fig.add_trace(go.Scatter(
            x=common_dist, y=delta,
            mode="lines",
            name=f"Δ {comp_code} vs {ref_code}",
            line=dict(color=comp_color, width=1.5),
            fill="tozeroy",
            fillcolor=_hex_to_rgba(comp_color, 0.2),
            hovertemplate="Distance: %{x:.0f}m<br>Delta: <b>%{y:+.3f}s</b><extra></extra>",
        ), row=2, col=1)

        fig.add_hline(y=0, line_color=ref_color, line_dash="dash",
                      line_width=1, row=2, col=1)

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=f"⚡ Speed Trace — {event_name} {session_type} | "
                 f"{' vs '.join(driver_codes)}",
            font=dict(size=18, color=ACCENT),
        ),
        height=600,
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Speed (km/h)", row=1, col=1, gridcolor=GRID_COLOR)
    fig.update_yaxes(title_text="Delta (s)", row=2, col=1, gridcolor=GRID_COLOR)
    fig.update_xaxes(title_text="Distance (m)", row=2, col=1, gridcolor=GRID_COLOR)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# 2. CIRCUIT SPEED HEATMAP
# ══════════════════════════════════════════════════════════════════════════════

def plot_circuit_speed_heatmap(
    round_number: int,
    driver_code: str,
    session_type: str = "Q",
) -> go.Figure:
    """
    Track map coloured by speed — shows braking zones, acceleration zones,
    high-speed corners visually on the actual circuit layout.
    """
    session = load_session(round_number, session_type)
    event_name = session.event["EventName"]

    lap = get_fastest_lap(session, driver_code)
    if lap is None:
        return go.Figure().update_layout(title="No data available")

    tel = lap.get_telemetry().add_distance()
    tel = tel.dropna(subset=["X", "Y", "Speed"])

    full_name = config.DRIVER_CODE_MAP.get(driver_code, driver_code)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=tel["X"], y=tel["Y"],
        mode="markers",
        marker=dict(
            color=tel["Speed"],
            colorscale=[
                [0.0,  "#0000FF"],   # slow — deep blue
                [0.3,  "#00FFFF"],   # medium
                [0.6,  "#00FF00"],   # fast — green
                [0.85, "#FFFF00"],   # very fast — yellow
                [1.0,  "#FF0000"],   # flat out — red
            ],
            size=3,
            colorbar=dict(
                title="Speed (km/h)",
                tickfont=dict(color=TEXT_COLOR),
                titlefont=dict(color=TEXT_COLOR),
            ),
            showscale=True,
        ),
        hovertemplate="Speed: <b>%{marker.color:.0f} km/h</b><extra></extra>",
        showlegend=False,
    ))

    # Mark start/finish
    fig.add_trace(go.Scatter(
        x=[tel["X"].iloc[0]], y=[tel["Y"].iloc[0]],
        mode="markers+text",
        marker=dict(color=ACCENT, size=14, symbol="star"),
        text=["S/F"], textposition="top center",
        textfont=dict(color=ACCENT, size=11),
        name="Start/Finish",
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=f"🗺️ Circuit Speed Map — {event_name} {session_type} | {driver_code} ({full_name.split()[-1]})",
            font=dict(size=18, color=ACCENT),
        ),
        height=620,
    )
    # Override axes AFTER layout (avoids duplicate kwarg conflict with LAYOUT_BASE)
    fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False)
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False,
                     scaleanchor="x", scaleratio=1)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# 3. THROTTLE / BRAKE / GEAR TRACES
# ══════════════════════════════════════════════════════════════════════════════

def plot_pedal_traces(
    round_number: int,
    driver_codes: list[str],
    session_type: str = "Q",
) -> go.Figure:
    """
    4-panel chart: Speed / Throttle % / Brake on|off / Gear
    for one or two drivers overlaid — reveals driving style differences.
    """
    session = load_session(round_number, session_type)
    event_name = session.event["EventName"]

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.35, 0.25, 0.2, 0.2],
        subplot_titles=["Speed (km/h)", "Throttle (%)", "Brake", "Gear"],
        vertical_spacing=0.06,
    )

    channels = [
        ("Speed",    1, "Speed (km/h)"),
        ("Throttle", 2, "Throttle (%)"),
        ("Brake",    3, "Brake"),
        ("nGear",    4, "Gear"),
    ]

    for code in driver_codes:
        lap = get_fastest_lap(session, code)
        if lap is None:
            continue
        tel = lap.get_telemetry().add_distance().dropna(subset=["Distance"])
        full_name = config.DRIVER_CODE_MAP.get(code, code)
        color     = _driver_color(full_name, round_number)

        for channel, row, _ in channels:
            if channel not in tel.columns:
                continue
            fig.add_trace(go.Scatter(
                x=tel["Distance"],
                y=tel[channel],
                mode="lines",
                name=f"{code}" if row == 1 else None,
                showlegend=(row == 1),
                line=dict(color=color, width=1.8),
                hovertemplate=f"<b>{code}</b> | %{{x:.0f}}m | {channel}: <b>%{{y}}</b><extra></extra>",
            ), row=row, col=1)

    for _, row, label in channels:
        fig.update_yaxes(title_text=label, row=row, col=1, gridcolor=GRID_COLOR)
    fig.update_xaxes(title_text="Distance (m)", row=4, col=1)

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=f"🎮 Pedal & Gear Traces — {event_name} {session_type} | "
                 f"{' vs '.join(driver_codes)}",
            font=dict(size=18, color=ACCENT),
        ),
        height=720,
        hovermode="x unified",
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# 4. LAP TIME PROGRESSION (race stint degradation)
# ══════════════════════════════════════════════════════════════════════════════

def plot_lap_time_progression(
    round_number: int,
    driver_codes: list[str],
) -> go.Figure:
    """
    Race lap-by-lap times for selected drivers.
    Reveals tyre degradation, safety car periods, pit stop laps, and form.
    Outlier laps (pit in/out, SC) are shown as faded markers.
    """
    session = load_session(round_number, "R")
    event_name = session.event["EventName"]

    fig = go.Figure()

    for code in driver_codes:
        try:
            laps = session.laps.pick_drivers(code).copy()
        except Exception:
            continue

        laps = laps.dropna(subset=["LapTime"])
        laps["LapTimeS"] = laps["LapTime"].dt.total_seconds()

        # Tag outlier laps (pit stop, SC, VSC)
        median_t = laps["LapTimeS"].median()
        laps["is_outlier"] = laps["LapTimeS"] > median_t * 1.07

        full_name = config.DRIVER_CODE_MAP.get(code, code)
        color     = _driver_color(full_name, round_number)
        surname   = full_name.split()[-1]

        normal  = laps[~laps["is_outlier"]]
        outlier = laps[laps["is_outlier"]]

        # Normal laps
        fig.add_trace(go.Scatter(
            x=normal["LapNumber"], y=normal["LapTimeS"],
            mode="lines+markers",
            name=surname,
            line=dict(color=color, width=2),
            marker=dict(size=5, color=color),
            hovertemplate=(
                f"<b>{surname}</b><br>Lap %{{x}}<br>"
                "Time: <b>%{y:.3f}s</b><extra></extra>"
            ),
        ))

        # Outlier laps (pit/SC) — faded
        fig.add_trace(go.Scatter(
            x=outlier["LapNumber"], y=outlier["LapTimeS"],
            mode="markers",
            name=f"{surname} (pit/SC)",
            marker=dict(size=7, color=color, opacity=0.35,
                        symbol="x", line=dict(width=1, color=color)),
            showlegend=False,
            hovertemplate=(
                f"<b>{surname}</b> — outlier<br>Lap %{{x}}<br>"
                "Time: <b>%{y:.3f}s</b><extra></extra>"
            ),
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=f"⏱️ Race Lap Time Progression — {event_name} | "
                 f"{' vs '.join(driver_codes)}",
            font=dict(size=18, color=ACCENT),
        ),
        xaxis_title="Lap Number",
        yaxis_title="Lap Time (s)",
        hovermode="x unified",
        height=520,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# 5. SECTOR DELTA HEATMAP (qualifying — all drivers vs fastest)
# ══════════════════════════════════════════════════════════════════════════════

def plot_sector_delta_heatmap(round_number: int) -> go.Figure:
    """
    Heatmap of sector time gaps to the session-fastest time.
    Rows = drivers, columns = Sector 1 / 2 / 3.
    Green = time gained vs fastest, red = time lost.
    """
    session = load_session(round_number, "Q")
    event_name = session.event["EventName"]

    laps = session.laps.pick_quicklaps().copy()
    laps = laps.dropna(subset=["Sector1Time", "Sector2Time", "Sector3Time"])

    # Best sector time per driver
    best = laps.groupby("Driver").agg(
        S1=("Sector1Time", "min"),
        S2=("Sector2Time", "min"),
        S3=("Sector3Time", "min"),
    ).reset_index()
    best["S1s"] = best["S1"].dt.total_seconds()
    best["S2s"] = best["S2"].dt.total_seconds()
    best["S3s"] = best["S3"].dt.total_seconds()
    best["Total"] = best["S1s"] + best["S2s"] + best["S3s"]
    best = best.sort_values("Total")

    # Delta vs fastest in each sector
    for col in ["S1s", "S2s", "S3s"]:
        best[f"{col}_delta"] = best[col] - best[col].min()

    z = best[["S1s_delta", "S2s_delta", "S3s_delta"]].values
    driver_labels = [
        config.DRIVER_CODE_MAP.get(d, d) for d in best["Driver"]
    ]
    # Shorten to surnames
    driver_labels = [n.split()[-1] for n in driver_labels]

    fig = go.Figure(go.Heatmap(
        z=z,
        x=["Sector 1", "Sector 2", "Sector 3"],
        y=driver_labels,
        colorscale=[
            [0.0,  "#00AA44"],   # fastest — green
            [0.3,  "#AACC00"],
            [0.6,  "#FFAA00"],
            [1.0,  "#FF2200"],   # slowest — red
        ],
        text=np.round(z, 3),
        texttemplate="+%{text}s",
        hovertemplate="%{y}<br>%{x}<br>Gap: <b>+%{z:.3f}s</b><extra></extra>",
        colorbar=dict(title="Gap (s)", tickfont=dict(color=TEXT_COLOR)),
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=f"🟩 Qualifying Sector Deltas — {event_name}",
            font=dict(size=18, color=ACCENT),
        ),
        height=max(400, len(driver_labels) * 35),
    )
    fig.update_xaxes(side="top")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# 6. FULL SEASON COMEBACK ANALYSIS — VER's entire 2025 arc
# ══════════════════════════════════════════════════════════════════════════════

# Narrative checkpoints across the season — each with a story label and colour
# Phase colours: red = struggling, amber = turning point, green = dominant
COMEBACK_CHECKPOINTS = [
    # (round, label,               phase_color,  story_note)
    (1,  "Rd 1 — Australia",      "#4FC3F7",  "Season opener — VER P2, -7 behind Norris"),
    (6,  "Rd 6 — Miami",          "#FF6B6B",  "Deficit grows to -32 — Piastri dominates"),
    (9,  "Rd 9 — Spain",          "#FF1801",  "Darkest early form — scored only 1 pt"),
    (15, "Rd 15 — Dutch GP",      "#FF0000",  "Peak deficit: -104 pts — season in crisis"),
    (16, "Rd 16 — Monza",         "#FFB347",  "Recovery begins — wins Italy"),
    (19, "Rd 19 — COTA",          "#FFD700",  "33-pt sprint+race weekend — gap closes"),
    (22, "Rd 22 — Las Vegas",     "#90EE90",  "Stunning win — gap to Norris -24"),
    (23, "Rd 23 — Qatar",         "#00CC44",  "30 pts — gap down to -12 with 1 race left"),
    (24, "Rd 24 — Abu Dhabi",     "#00FF88",  "Season finale — wins race, loses title by 2"),
]


def plot_season_pace_evolution(
    driver_code: str = "VER",
    checkpoints: list = None,
    session_type: str = "Q",
) -> go.Figure:
    """
    Full-season pace evolution — overlays fastest qualifying laps from
    narrative checkpoint rounds to show how a driver's pace changed
    across the entire season arc.

    Each line is coloured by championship phase:
      🔵 Early season  →  🔴 Struggle  →  🟡 Turning point  →  🟢 Recovery
    """
    if checkpoints is None:
        checkpoints = COMEBACK_CHECKPOINTS

    full_name = config.DRIVER_CODE_MAP.get(driver_code, driver_code)
    surname   = full_name.split()[-1]

    fig = go.Figure()
    loaded = []

    for rnd, label, color, note in checkpoints:
        try:
            session = load_session(rnd, session_type)
            lap     = get_fastest_lap(session, driver_code)
            if lap is None:
                print(f"  [skip] No lap data for {driver_code} Rd {rnd}")
                continue

            tel = lap.get_telemetry().add_distance().dropna(subset=["Distance", "Speed"])

            # Format lap time
            try:
                total_s   = lap["LapTime"].total_seconds()
                mins      = int(total_s // 60)
                secs      = total_s % 60
                lap_label = f"{mins}:{secs:06.3f}"
            except Exception:
                lap_label = "N/A"

            fig.add_trace(go.Scatter(
                x=tel["Distance"],
                y=tel["Speed"],
                mode="lines",
                name=f"{label}  ({lap_label})",
                line=dict(color=color, width=2),
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    f"{note}<br>"
                    "Dist: %{x:.0f}m | Speed: <b>%{y:.0f} km/h</b><extra></extra>"
                ),
                legendrank=rnd,
            ))
            loaded.append((rnd, label, color, note))
            print(f"  ✅ Loaded Rd {rnd:2d} — {label}")

        except Exception as e:
            print(f"  ⚠️  Could not load Rd {rnd}: {e}")

    # Phase zone annotations (vertical bands are too complex — use legend annotations)
    phase_annotations = [
        dict(text="◀ Struggle Phase",       x=0.01, y=0.06, xref="paper", yref="paper",
             showarrow=False, font=dict(color="#FF6B6B", size=10), bgcolor=CARD_BG),
        dict(text="◀ Turning Point",        x=0.01, y=0.02, xref="paper", yref="paper",
             showarrow=False, font=dict(color="#FFD700", size=10), bgcolor=CARD_BG),
    ]

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=f"🏆 {surname}'s Full Season Pace Evolution — 2025 F1 Championship",
            font=dict(size=20, color=ACCENT),
        ),
        xaxis_title="Distance (m)",
        yaxis_title="Speed (km/h)",
        height=580,
        hovermode="x unified",
        annotations=phase_annotations,
    )
    fig.update_layout(legend=dict(
        bgcolor=CARD_BG, bordercolor=GRID_COLOR, borderwidth=1,
        font=dict(size=11),
        title=dict(text="Round — Lap Time", font=dict(color=TEXT_COLOR, size=12)),
    ))
    return fig


def plot_qualifying_laptime_trend(
    driver_codes: list[str] = None,
    session_type: str = "Q",
) -> go.Figure:
    """
    Line chart of each driver's fastest qualifying lap time (in seconds)
    across every round of the season — shows pace progression, not points.

    Unlike the points chart, this is purely about raw speed:
    who got faster over the season, who stagnated, who peaked early.
    """
    if driver_codes is None:
        driver_codes = ["VER", "NOR", "PIA", "RUS"]

    fig = go.Figure()

    for code in driver_codes:
        full_name = config.DRIVER_CODE_MAP.get(code, code)
        surname   = full_name.split()[-1]
        color     = _driver_color(full_name)

        rounds_done = []
        lap_times   = []
        race_names  = []

        for rnd in range(1, config.TOTAL_ROUNDS + 1):
            try:
                session = load_session(rnd, session_type)
                lap     = get_fastest_lap(session, code)
                if lap is None:
                    continue
                t = lap["LapTime"].total_seconds()
                if pd.notna(t) and t > 0:
                    rounds_done.append(rnd)
                    lap_times.append(t)
                    race_names.append(session.event["EventName"].replace(" Grand Prix", " GP"))
            except Exception:
                continue

        if not rounds_done:
            continue

        # Normalise to % of each round's fastest lap so circuits are comparable
        # (lap times are meaningless across different tracks raw)
        # We'll store raw here and normalise per-round below after all drivers loaded
        fig.add_trace(go.Scatter(
            x=rounds_done,
            y=lap_times,
            mode="lines+markers",
            name=surname,
            line=dict(color=color, width=2.5),
            marker=dict(size=6, color=color),
            text=race_names,
            hovertemplate=(
                f"<b>{surname}</b><br>"
                "Rd %{x} — %{text}<br>"
                "Lap: <b>%{y:.3f}s</b><extra></extra>"
            ),
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text="⏱️ Qualifying Lap Time Trend — Full 2025 Season",
            font=dict(size=20, color=ACCENT),
        ),
        xaxis_title="Race Round",
        yaxis_title="Fastest Lap Time (s)  [varies by circuit]",
        height=520,
        hovermode="x unified",
        annotations=[dict(
            text="Note: Times are not comparable across circuits — use for within-round gaps only",
            x=0.5, y=-0.12, xref="paper", yref="paper",
            showarrow=False, font=dict(color="#888888", size=10),
        )],
    )

    # Label x-axis with round numbers
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, config.TOTAL_ROUNDS + 1)),
        ticktext=[str(r) for r in range(1, config.TOTAL_ROUNDS + 1)],
    )
    return fig


def plot_gap_to_pole_trend(
    driver_codes: list[str] = None,
) -> go.Figure:
    """
    For each qualifying session, compute each driver's gap to pole (in seconds).
    Plotted across the season — shows who was consistently near the front
    and whose single-lap pace grew or faded.

    This is the PUREST pace metric — eliminates circuit differences
    since everyone is on the same track each round.
    Gap to pole = 0 means they set pole. Larger = further off pace.
    """
    if driver_codes is None:
        driver_codes = ["VER", "NOR", "PIA", "RUS", "LEC"]

    # Collect pole time and each driver's best per round
    all_data: dict[str, dict] = {code: {"rounds": [], "gaps": [], "races": []} for code in driver_codes}

    for rnd in range(1, config.TOTAL_ROUNDS + 1):
        try:
            session  = load_session(rnd, "Q")
            race_name = session.event["EventName"].replace(" Grand Prix", " GP")

            # Pole time = fastest lap across all drivers in session
            fastest_laps = session.laps.pick_quicklaps()
            if fastest_laps.empty:
                continue
            pole_time = fastest_laps["LapTime"].min().total_seconds()

            for code in driver_codes:
                lap = get_fastest_lap(session, code)
                if lap is None:
                    continue
                t = lap["LapTime"].total_seconds()
                if pd.notna(t) and t > 0:
                    gap = t - pole_time
                    all_data[code]["rounds"].append(rnd)
                    all_data[code]["gaps"].append(round(gap, 3))
                    all_data[code]["races"].append(race_name)

        except Exception as e:
            print(f"  [Rd {rnd}] {e}")
            continue

    fig = go.Figure()

    for code in driver_codes:
        d = all_data[code]
        if not d["rounds"]:
            continue
        full_name = config.DRIVER_CODE_MAP.get(code, code)
        surname   = full_name.split()[-1]
        color     = _driver_color(full_name)

        # Rolling 3-round average to smooth out circuit-specific outliers
        gaps_series = pd.Series(d["gaps"])
        rolling_avg = gaps_series.rolling(3, min_periods=1).mean().round(3).tolist()

        fig.add_trace(go.Scatter(
            x=d["rounds"],
            y=d["gaps"],
            mode="markers",
            name=f"{surname} (raw)",
            marker=dict(size=5, color=color, opacity=0.4),
            showlegend=False,
            hovertemplate=(
                f"<b>{surname}</b><br>"
                "Rd %{x} — " + "%{text}<br>" +
                "Gap to pole: <b>+%{y:.3f}s</b><extra></extra>"
            ),
            text=d["races"],
        ))

        fig.add_trace(go.Scatter(
            x=d["rounds"],
            y=rolling_avg,
            mode="lines",
            name=f"{surname}",
            line=dict(color=color, width=2.5),
            hovertemplate=(
                f"<b>{surname}</b> (3-race avg)<br>"
                "Rd %{x}<br>"
                "Avg gap: <b>+%{y:.3f}s</b><extra></extra>"
            ),
        ))

    # Mark Verstappen's turning point (Rd 16)
    fig.add_vline(
        x=15.5,
        line_color="#FFD700", line_dash="dash", line_width=1.5,
        annotation_text="VER turns it around →",
        annotation_position="top right",
        annotation_font_color="#FFD700",
        annotation_font_size=11,
    )

    fig.add_vline(
        x=0.5,
        line_color=GRID_COLOR, line_dash="dot", line_width=1,
    )

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text="🎯 Gap to Pole — Full 2025 Season Qualifying Pace",
            font=dict(size=20, color=ACCENT),
        ),
        xaxis_title="Race Round",
        yaxis_title="Gap to Pole (s)  — lower = closer to pole",
        height=540,
        hovermode="x unified",
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, config.TOTAL_ROUNDS + 1)),
        ticktext=[str(r) for r in range(1, config.TOTAL_ROUNDS + 1)],
    )
    # Invert y so "better" (closer to pole) is higher visually
    fig.update_yaxes(autorange="reversed")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# 7. TYRE STINT ANALYSIS (race — coloured by compound)
# ══════════════════════════════════════════════════════════════════════════════

COMPOUND_COLORS = {
    "SOFT":   "#FF3333",
    "MEDIUM": "#FFD700",
    "HARD":   "#FFFFFF",
    "INTER":  "#39B54A",
    "WET":    "#0067FF",
    "UNKNOWN": "#888888",
}

def plot_tyre_stint_analysis(
    round_number: int,
    driver_codes: list[str],
) -> go.Figure:
    """
    Lap times coloured by tyre compound — shows strategy and degradation.
    Each compound gets its own colour (red=soft, yellow=medium, white=hard).
    """
    session = load_session(round_number, "R")
    event_name = session.event["EventName"]

    fig = go.Figure()

    for code in driver_codes:
        try:
            laps = session.laps.pick_drivers(code).copy()
        except Exception:
            continue

        laps = laps.dropna(subset=["LapTime", "Compound"])
        laps["LapTimeS"] = laps["LapTime"].dt.total_seconds()
        laps = laps[laps["LapTimeS"] < laps["LapTimeS"].median() * 1.08]

        full_name = config.DRIVER_CODE_MAP.get(code, code)
        surname   = full_name.split()[-1]

        for compound in laps["Compound"].unique():
            c_laps = laps[laps["Compound"] == compound]
            c_color = COMPOUND_COLORS.get(compound.upper(), "#888888")

            fig.add_trace(go.Scatter(
                x=c_laps["LapNumber"],
                y=c_laps["LapTimeS"],
                mode="markers+lines",
                name=f"{surname} — {compound}",
                marker=dict(color=c_color, size=7,
                            line=dict(color="#333", width=0.5)),
                line=dict(color=c_color, width=1.5, dash="dot"),
                hovertemplate=(
                    f"<b>{surname}</b> [{compound}]<br>"
                    "Lap %{x}<br>Time: <b>%{y:.3f}s</b><extra></extra>"
                ),
            ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=f"🏎️ Tyre Stint Analysis — {event_name} Race | "
                 f"{' vs '.join(driver_codes)}",
            font=dict(size=18, color=ACCENT),
        ),
        xaxis_title="Lap Number",
        yaxis_title="Lap Time (s)",
        hovermode="x unified",
        height=520,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import plotly.io as pio
    pio.renderers.default = "browser"

    print("=" * 60)
    print("F1 2025 Telemetry Analysis — Standalone Test")
    print("=" * 60)

    # Test 1: Speed trace — Abu Dhabi qualifying (season finale)
    print("\n[1] Speed trace — Rd 24 Abu Dhabi Qualifying: VER vs NOR")
    fig1 = plot_speed_trace(24, ["VER", "NOR"], "Q")
    fig1.show()

    # Test 2: Circuit speed heatmap — Abu Dhabi
    print("\n[2] Circuit heatmap — Rd 24 Abu Dhabi: VER")
    fig2 = plot_circuit_speed_heatmap(24, "VER", "Q")
    fig2.show()

    # Test 3: Pedal traces — Abu Dhabi qualifying
    print("\n[3] Pedal traces — Rd 24 Abu Dhabi: VER vs NOR")
    fig3 = plot_pedal_traces(24, ["VER", "NOR"], "Q")
    fig3.show()

    # Test 4: Lap time progression — Abu Dhabi race (finale)
    print("\n[4] Lap time progression — Rd 24 Abu Dhabi Race: VER vs NOR")
    fig4 = plot_lap_time_progression(24, ["VER", "NOR"])
    fig4.show()

    # Test 5: Sector delta heatmap — Abu Dhabi qualifying (finale)
    print("\n[5] Sector deltas — Rd 24 Abu Dhabi Qualifying")
    fig5 = plot_sector_delta_heatmap(24)
    fig5.show()

    # Test 6: Full season pace evolution — VER's entire comeback arc
    print("\n[6] Full season pace evolution — VER across 9 narrative checkpoints")
    print("    Loading qualifying data from Rd 1, 6, 9, 15, 16, 19, 22, 23, 24...")
    fig6 = plot_season_pace_evolution("VER")
    fig6.show()

    # Test 7: Gap to pole — all title contenders across full season
    print("\n[7] Gap to pole trend — VER, NOR, PIA, RUS, LEC full season")
    print("    (Loading all 24 qualifying sessions — this will take a few minutes)")
    fig7 = plot_gap_to_pole_trend(["VER", "NOR", "PIA", "RUS", "LEC"])
    fig7.show()

    # Test 8: Tyre stint — Abu Dhabi race (finale)
    print("\n[8] Tyre stints — Rd 24 Abu Dhabi Race: VER vs NOR")
    fig8 = plot_tyre_stint_analysis(24, ["VER", "NOR"])
    fig8.show()

    print("\n✅ All telemetry charts generated successfully.")