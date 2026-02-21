"""
Created on Fri Feb 20 12:05:47 2026

@author: sid
"""
# visualizations.py — All Plotly charts for the Championship Story Visualizer
#
# Charts:
#   1. Championship Points Evolution (animated line)
#   2. Points Gap to Leader (area chart with drama zones)
#   3. Verstappen Recovery Arc (annotated comeback story)
#   4. Momentum Heatmap (rolling form by driver × race)
#   5. Head-to-Head Battle (dual-area rivalry chart)
#   6. Season Phase Performance (grouped bar)
#   7. Points-per-Race Scatter (consistency vs peak)
#   8. Championship Margin Waterfall (final 5 races)

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import config

# ── Shared theme ────────────────────────────────────────────────────────────────
DARK_BG    = "#0D0D0D"
CARD_BG    = "#1A1A1A"
GRID_COLOR = "#2A2A2A"
TEXT_COLOR = "#E0E0E0"
ACCENT     = "#FF1801"   # F1 red

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
    """Return team colour for a driver, optionally at a specific round (handles mid-season swaps)."""
    team = config.get_driver_team(driver, round_number)
    return config.TEAM_COLORS.get(team, "#AAAAAA")


def _hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    """Convert a #RRGGBB hex string to rgba(r,g,b,alpha) for Plotly fillcolor."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Championship Points Evolution
# ═══════════════════════════════════════════════════════════════════════════════

def plot_championship_evolution(
    standings_df: pd.DataFrame,
    highlight_drivers: list[str] = None,
    animate: bool = False,
) -> go.Figure:
    """
    Animated or static line chart of cumulative championship points.
    Highlighted drivers are bold & opaque; others are faint.
    """
    if highlight_drivers is None:
        highlight_drivers = config.TITLE_CONTENDERS

    fig = go.Figure()

    drivers = standings_df["driver"].unique()
    rounds  = sorted(standings_df["round"].unique())

    for driver in drivers:
        ddf   = standings_df[standings_df["driver"] == driver].sort_values("round")
        # Use the team colour from the driver's LAST round in the dataset
        # so swapped drivers (Tsunoda → RB, Lawson → Racing Bulls) show correct colour
        last_round = int(ddf["round"].max()) if not ddf.empty else config.TOTAL_ROUNDS
        color = _driver_color(driver, round_number=last_round)
        is_hl = driver in highlight_drivers
        races  = ddf["race_name"].tolist()

        fig.add_trace(go.Scatter(
            x=ddf["round"],
            y=ddf["points"],
            mode="lines+markers",
            name=driver,
            line=dict(
                color=color,
                width=3.5 if is_hl else 0.8,
                dash="solid" if is_hl else "dot",
            ),
            marker=dict(size=7 if is_hl else 3, color=color),
            opacity=1.0 if is_hl else 0.25,
            hovertemplate=(
                f"<b>{driver}</b><br>"
                "Round %{x} — %{text}<br>"
                "Points: <b>%{y}</b><extra></extra>"
            ),
            text=races,
            visible=True,
        ))

    # Add annotation for championship finale
    final_round = standings_df["round"].max()
    final_data  = standings_df[standings_df["round"] == final_round]
    if not final_data.empty:
        champ = final_data.loc[final_data["points"].idxmax()]
        fig.add_annotation(
            x=champ["round"], y=champ["points"],
            text=f"🏆 {champ['driver']}<br>{int(champ['points'])} pts",
            showarrow=True, arrowhead=2,
            arrowcolor=ACCENT, bgcolor=CARD_BG,
            bordercolor=ACCENT, borderwidth=1,
            font=dict(color=ACCENT, size=12),
            ax=30, ay=-40,
        )

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text="🏁 2025 F1 Championship Points Evolution", font=dict(size=22, color=ACCENT)),
        xaxis_title="Race Round",
        yaxis_title="Championship Points",
        hovermode="x unified",
    )

    # X-axis race labels
    race_labels = (
        standings_df[["round", "race_name"]]
        .drop_duplicates()
        .sort_values("round")
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=race_labels["round"].tolist(),
        ticktext=[n.replace(" Grand Prix", " GP") for n in race_labels["race_name"]],
        tickangle=45,
    )

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Points Gap to Leader
# ═══════════════════════════════════════════════════════════════════════════════

def plot_gap_to_leader(
    gap_df: pd.DataFrame,
    highlight_drivers: list[str] = None,
) -> go.Figure:
    """
    Area chart showing how far each driver was from the championship lead.
    Downward spikes = crisis moments. Recovery = rising back toward 0.
    """
    if highlight_drivers is None:
        highlight_drivers = config.TITLE_CONTENDERS

    fig = go.Figure()

    for driver in highlight_drivers:
        ddf = gap_df[gap_df["driver"] == driver].sort_values("round")
        if ddf.empty:
            continue
        color = _driver_color(driver)

        fig.add_trace(go.Scatter(
            x=ddf["round"],
            y=-ddf["gap_to_leader"],   # invert so leader = top
            mode="lines",
            name=driver,
            line=dict(color=color, width=2.5),
            fill="tozeroy",
            fillcolor=_hex_to_rgba(color, 0.15),
            hovertemplate=(
                f"<b>{driver}</b><br>"
                "Round %{x}<br>"
                "Gap: <b>%{customdata} pts</b><extra></extra>"
            ),
            customdata=ddf["gap_to_leader"],
        ))

    # Zero line = championship leader
    fig.add_hline(y=0, line_color=ACCENT, line_dash="dash", line_width=1.5,
                  annotation_text="Championship Lead", annotation_position="top right",
                  annotation_font_color=ACCENT)

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text="📉 Points Gap to Championship Leader", font=dict(size=20, color=ACCENT)),
        xaxis_title="Race Round",
        yaxis_title="Points Relative to Leader",
        hovermode="x unified",
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Verstappen Recovery Arc
# ═══════════════════════════════════════════════════════════════════════════════

def plot_verstappen_comeback(comeback_df: pd.DataFrame) -> go.Figure:
    """
    The hero chart — tells Max's comeback story with annotated drama zones.
    """
    fig = go.Figure()
    color = _driver_color("Max Verstappen")

    deficit_df  = comeback_df[comeback_df["phase"] == "Deficit Phase"]
    recovery_df = comeback_df[comeback_df["phase"] == "Recovery Phase"]

    # Deficit phase — shaded red danger zone
    if not deficit_df.empty:
        fig.add_trace(go.Scatter(
            x=deficit_df["round"], y=-deficit_df["gap_to_leader"],
            mode="lines+markers",
            name="Deficit Phase",
            line=dict(color="#FF4444", width=3),
            fill="tozeroy", fillcolor="rgba(255,68,68,0.15)",
            marker=dict(size=8, color="#FF4444"),
            hovertemplate="Round %{x}<br>Gap: <b>%{customdata} pts behind</b><extra></extra>",
            customdata=deficit_df["gap_to_leader"],
        ))

    # Recovery phase — shaded green comeback
    if not recovery_df.empty:
        # Overlap by one point for continuity
        connect = pd.concat([deficit_df.tail(1), recovery_df]) if not deficit_df.empty else recovery_df
        fig.add_trace(go.Scatter(
            x=connect["round"], y=-connect["gap_to_leader"],
            mode="lines+markers",
            name="Recovery Phase",
            line=dict(color="#00CC44", width=3),
            fill="tozeroy", fillcolor="rgba(0,204,68,0.15)",
            marker=dict(size=8, color="#00CC44"),
            hovertemplate="Round %{x}<br>Gap: <b>%{customdata} pts behind</b><extra></extra>",
            customdata=connect["gap_to_leader"],
        ))

    # Mark the nadir (maximum deficit)
    if not comeback_df.empty:
        nadir = comeback_df.loc[comeback_df["gap_to_leader"].idxmax()]
        fig.add_annotation(
            x=nadir["round"], y=-nadir["gap_to_leader"],
            text=f"⬇ -{int(nadir['gap_to_leader'])} pts<br>(Max deficit)",
            showarrow=True, arrowhead=2,
            arrowcolor="#FF4444", bgcolor=CARD_BG,
            bordercolor="#FF4444", font=dict(color="#FF4444", size=12),
            ax=40, ay=40,
        )

        # Final gap at season end
        finale = comeback_df.iloc[-1]
        fig.add_annotation(
            x=finale["round"], y=-finale["gap_to_leader"],
            text=f"Season End<br>-{int(finale['gap_to_leader'])} pts",
            showarrow=True, arrowhead=2,
            arrowcolor=ACCENT, bgcolor=CARD_BG,
            bordercolor=ACCENT, font=dict(color=ACCENT, size=12),
            ax=-60, ay=-30,
        )

    fig.add_hline(y=0, line_color="#FFD700", line_dash="dash", line_width=1.5,
                  annotation_text="Championship Leader", annotation_position="top right",
                  annotation_font_color="#FFD700")

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text="🔴 Max Verstappen's Championship Comeback Story 2025",
            font=dict(size=20, color=ACCENT)
        ),
        xaxis_title="Race Round",
        yaxis_title="Points Behind Leader",
        showlegend=True,
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Momentum Heatmap
# ═══════════════════════════════════════════════════════════════════════════════

def plot_momentum_heatmap(momentum_df: pd.DataFrame) -> go.Figure:
    """
    Heatmap of rolling momentum (avg pts/race) for top drivers.
    Hot colours = peak form. Cool = struggling.
    """
    drivers = config.TITLE_CONTENDERS
    df = momentum_df[momentum_df["driver"].isin(drivers)].copy()

    pivot = df.pivot_table(
        index="driver", columns="round", values="momentum", aggfunc="mean"
    )

    race_labels = (
        momentum_df[["round", "race_name"]]
        .drop_duplicates()
        .sort_values("round")["race_name"]
        .str.replace(" Grand Prix", " GP")
        .tolist()
    )

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=race_labels[:pivot.shape[1]],
        y=pivot.index.tolist(),
        colorscale=[
            [0.0,  "#0D0D0D"],
            [0.3,  "#1A3A6B"],
            [0.6,  "#FF8800"],
            [1.0,  "#FF0000"],
        ],
        hovertemplate="%{y}<br>%{x}<br>Momentum: <b>%{z:.1f} pts/race</b><extra></extra>",
        colorbar=dict(title="Avg pts / race", tickfont=dict(color=TEXT_COLOR)),
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text="🔥 Driver Momentum (4-Race Rolling Avg)", font=dict(size=20, color=ACCENT)),
    )
    fig.update_xaxes(tickangle=45, gridcolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR)
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Head-to-Head Rivalry Chart
# ═══════════════════════════════════════════════════════════════════════════════

def plot_head_to_head(
    h2h_df: pd.DataFrame,
    driver_a: str,
    driver_b: str,
    race_labels: list[str],
) -> go.Figure:
    """
    Dual-area chart showing two drivers' points trajectories.
    The "leading" shading switches colour as the lead changes hands.
    """
    color_a = _driver_color(driver_a)
    color_b = _driver_color(driver_b)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=h2h_df["round"], y=h2h_df.get(driver_a, pd.Series(dtype=float)),
        name=driver_a,
        mode="lines+markers",
        line=dict(color=color_a, width=3),
        fill="tozeroy", fillcolor=_hex_to_rgba(color_a, 0.2),
        hovertemplate=f"<b>{driver_a}</b><br>Round %{{x}}<br>Points: <b>%{{y}}</b><extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=h2h_df["round"], y=h2h_df.get(driver_b, pd.Series(dtype=float)),
        name=driver_b,
        mode="lines+markers",
        line=dict(color=color_b, width=3),
        fill="tonexty", fillcolor=_hex_to_rgba(color_b, 0.2),
        hovertemplate=f"<b>{driver_b}</b><br>Round %{{x}}<br>Points: <b>%{{y}}</b><extra></extra>",
    ))

    # Mark lead-change moments
    prev_lead = None
    for _, row in h2h_df.iterrows():
        cur_lead = row.get("leading")
        if prev_lead and cur_lead != prev_lead:
            fig.add_vline(
                x=row["round"],
                line_color="#FFD700", line_dash="dash", line_width=1,
                annotation_text="Lead Change",
                annotation_font_color="#FFD700",
                annotation_position="top",
            )
        prev_lead = cur_lead

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=f"⚔️ {driver_a.split()[-1]} vs {driver_b.split()[-1]} — Championship Battle",
            font=dict(size=20, color=ACCENT)
        ),
        xaxis_title="Race Round",
        yaxis_title="Cumulative Points",
        hovermode="x unified",
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=h2h_df["round"].tolist(),
        ticktext=[r.replace(" Grand Prix", " GP") for r in race_labels[:len(h2h_df)]],
        tickangle=45,
        gridcolor=GRID_COLOR,
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Season Phase Performance
# ═══════════════════════════════════════════════════════════════════════════════

def plot_season_phases(phase_df: pd.DataFrame) -> go.Figure:
    """
    Grouped bar chart — avg points per race by season phase.
    Reveals who started strong, who faded, who peaked late (Verstappen).
    """
    fig = go.Figure()

    for driver in phase_df["driver"].unique():
        ddf = phase_df[phase_df["driver"] == driver]
        color = _driver_color(driver)
        fig.add_trace(go.Bar(
            x=ddf["phase"],
            y=ddf["avg_points_per_race"],
            name=driver,
            marker_color=color,
            hovertemplate=f"<b>{driver}</b><br>%{{x}}<br>Avg: <b>%{{y:.1f}} pts</b><extra></extra>",
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text="📊 Average Points Per Race — By Season Phase", font=dict(size=20, color=ACCENT)),
        xaxis_title="Season Phase",
        yaxis_title="Avg Points Per Race",
        barmode="group",
        bargap=0.15,
        bargroupgap=0.1,
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Points-per-Race Scatter (Consistency vs Peak)
# ═══════════════════════════════════════════════════════════════════════════════

def plot_consistency_scatter(per_race_df: pd.DataFrame) -> go.Figure:
    """
    Scatter: X = std dev of points per race (lower = more consistent)
             Y = average points per race (higher = faster)
    Size = total points. Each dot = a driver.
    """
    drivers = config.TITLE_CONTENDERS
    df = per_race_df[per_race_df["driver"].isin(drivers)].copy()

    stats = df.groupby("driver")["points_earned"].agg(
        mean="mean", std="std", total="sum"
    ).reset_index()
    stats["std"] = stats["std"].fillna(0)

    fig = go.Figure()
    for _, row in stats.iterrows():
        color = _driver_color(row["driver"])
        fig.add_trace(go.Scatter(
            x=[row["std"]],
            y=[row["mean"]],
            mode="markers+text",
            name=row["driver"],
            marker=dict(size=row["total"] / 8, color=color, opacity=0.85,
                        line=dict(width=1.5, color=TEXT_COLOR)),
            text=[row["driver"].split()[-1]],
            textposition="top center",
            hovertemplate=(
                f"<b>{row['driver']}</b><br>"
                f"Avg: {row['mean']:.1f} pts/race<br>"
                f"Consistency σ: {row['std']:.1f}<br>"
                f"Total: {int(row['total'])} pts<extra></extra>"
            ),
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text="🎯 Consistency vs Peak Performance", font=dict(size=20, color=ACCENT)),
        xaxis_title="Variability (std dev of pts per race) →  Less consistent",
        yaxis_title="↑ Avg Points Per Race",
        showlegend=False,
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Final 5 Races Waterfall — Championship Drama
# ═══════════════════════════════════════════════════════════════════════════════

def plot_final_stretch_waterfall(
    per_race_df: pd.DataFrame,
    driver_a: str = "Max Verstappen",
    driver_b: str = None,
    last_n: int = 6,
) -> go.Figure:
    """
    Stacked bar showing points earned in the final N races by the two
    championship protagonists, with running gap line overlay.
    """
    all_rounds = sorted(per_race_df["round"].unique())
    final_rounds = all_rounds[-last_n:]

    df = per_race_df[
        per_race_df["round"].isin(final_rounds) &
        per_race_df["driver"].isin([d for d in [driver_a, driver_b] if d])
    ].copy()

    race_names = (
        per_race_df[per_race_df["round"].isin(final_rounds)][["round", "race_name"]]
        .drop_duplicates()
        .sort_values("round")
    )
    label_map = dict(zip(race_names["round"], race_names["race_name"].str.replace(" Grand Prix", " GP")))

    fig = go.Figure()

    for driver in [driver_a, driver_b]:
        if not driver:
            continue
        ddf = df[df["driver"] == driver].sort_values("round")
        color = _driver_color(driver)
        fig.add_trace(go.Bar(
            x=[label_map.get(r, str(r)) for r in ddf["round"]],
            y=ddf["points_earned"],
            name=driver,
            marker_color=color,
            hovertemplate=f"<b>{driver}</b><br>%{{x}}<br>Earned: <b>%{{y}} pts</b><extra></extra>",
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=f"🏁 Final {last_n} Races — Championship Decider",
            font=dict(size=20, color=ACCENT)
        ),
        xaxis_title="Race",
        yaxis_title="Points Earned",
        barmode="group",
        bargap=0.2,
    )
    return fig