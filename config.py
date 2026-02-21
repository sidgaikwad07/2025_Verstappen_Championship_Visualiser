"""
Created on Fri Feb 20 11:43:50 2026

@author: sid
"""

# config.py — F1 Championship Visualizer Configuration

SEASON = 2025

# Jolpica API (Ergast successor) — free, no auth needed
JOLPICA_BASE = "https://api.jolpi.ca/ergast/f1"

# FastF1 cache directory
CACHE_DIR = "./fastf1_cache"

# F1 2025 Team Colors (official approximate hex values)
# Keys match EXACTLY what the Jolpica API returns as constructor names
TEAM_COLORS = {
    "Red Bull":          "#3671C6",
    "Ferrari":           "#E8002D",
    "McLaren":           "#FF8000",
    "Mercedes":          "#27F4D2",
    "Aston Martin":      "#229971",
    "Alpine F1 Team":    "#0093CC",
    "Williams":          "#64C4FF",
    "RB F1 Team":        "#6692FF",
    "Sauber":            "#52E252",
    "Haas F1 Team":      "#B6BABD",
}

# Friendly short names for display labels in charts
TEAM_DISPLAY_NAMES = {
    "Alpine F1 Team":  "Alpine",
    "RB F1 Team":      "Racing Bulls",
    "Haas F1 Team":    "Haas",
    "Sauber":          "Kick Sauber",
    "Red Bull":        "Red Bull",
    "Ferrari":         "Ferrari",
    "McLaren":         "McLaren",
    "Mercedes":        "Mercedes",
    "Aston Martin":    "Aston Martin",
    "Williams":        "Williams",
}

# ── Mid-Season Driver Swaps ────────────────────────────────────────────────────
#
# Format: (driver_name, team, from_round, to_round)
#   from_round : first race round the driver raced for this team (inclusive)
#   to_round   : last race round for this team (inclusive). Use TOTAL_ROUNDS (24) for season end.
#
# Known 2025 swaps:
#   • Liam Lawson  → started at Red Bull (Rd 1–3), demoted to Racing Bulls (Rd 4+)
#   • Yuki Tsunoda → started at Racing Bulls (Rd 1–3), promoted to Red Bull (Rd 4+)
#   • Jack Doohan  → started at Alpine (Rd 1–3), replaced by Franco Colapinto (Rd 4+)
#
DRIVER_STINTS = [
    # ── Red Bull ──────────────────────────────────────────────────────────────
    ("Max Verstappen",        "Red Bull",       1,  24),
    ("Liam Lawson",           "Red Bull",       1,   3),   # demoted after Rd 3
    ("Yuki Tsunoda",          "Red Bull",       4,  24),   # promoted from Rd 4

    # ── Ferrari ───────────────────────────────────────────────────────────────
    ("Charles Leclerc",       "Ferrari",        1,  24),
    ("Lewis Hamilton",        "Ferrari",        1,  24),

    # ── McLaren ───────────────────────────────────────────────────────────────
    ("Lando Norris",          "McLaren",        1,  24),
    ("Oscar Piastri",         "McLaren",        1,  24),

    # ── Mercedes ──────────────────────────────────────────────────────────────
    ("George Russell",        "Mercedes",       1,  24),
    ("Andrea Kimi Antonelli", "Mercedes",       1,  24),

    # ── Aston Martin ──────────────────────────────────────────────────────────
    ("Fernando Alonso",       "Aston Martin",   1,  24),
    ("Lance Stroll",          "Aston Martin",   1,  24),

    # ── Alpine F1 Team ────────────────────────────────────────────────────────
    ("Pierre Gasly",          "Alpine F1 Team", 1,  24),
    ("Jack Doohan",           "Alpine F1 Team", 1,   6),   # replaced after Rd 6 (Miami)
    ("Franco Colapinto",      "Alpine F1 Team", 7,  24),   # joined from Rd 7 (Emilia Romagna)

    # ── Williams ──────────────────────────────────────────────────────────────
    ("Alexander Albon",       "Williams",       1,  24),
    ("Carlos Sainz",          "Williams",       1,  24),

    # ── RB F1 Team (Racing Bulls) ─────────────────────────────────────────────
    ("Yuki Tsunoda",          "RB F1 Team",     1,   3),   # before Red Bull promotion
    ("Liam Lawson",           "RB F1 Team",     4,  24),   # after Red Bull demotion
    ("Isack Hadjar",          "RB F1 Team",     1,  24),

    # ── Sauber (Kick Sauber) ──────────────────────────────────────────────────
    ("Nico Hülkenberg",       "Sauber",         1,  24),   # API uses umlaut ü
    ("Gabriel Bortoleto",     "Sauber",         1,  24),

    # ── Haas F1 Team ──────────────────────────────────────────────────────────
    ("Esteban Ocon",          "Haas F1 Team",   1,  24),
    ("Oliver Bearman",        "Haas F1 Team",   1,  24),
]


TOTAL_ROUNDS = 24   # 2025 F1 season — 24 Grands Prix


def get_driver_team(driver: str, round_number: int = TOTAL_ROUNDS) -> str:
    """
    Return the team a driver raced for at a specific round.
    Falls back to their most recent stint if no exact match.

    Examples
    --------
    >>> get_driver_team("Liam Lawson", round_number=2)
    'Red Bull'
    >>> get_driver_team("Liam Lawson", round_number=5)
    'Racing Bulls'
    >>> get_driver_team("Yuki Tsunoda", round_number=2)
    'Racing Bulls'
    >>> get_driver_team("Yuki Tsunoda", round_number=6)
    'Red Bull'
    >>> get_driver_team("Franco Colapinto", round_number=6)
    'Alpine'
    """
    matches = [
        team
        for (drv, team, frm, to) in DRIVER_STINTS
        if drv == driver and frm <= round_number <= to
    ]
    if matches:
        return matches[0]
    # Fallback: return the team from the driver's last known stint
    all_stints = [(frm, team) for (drv, team, frm, to) in DRIVER_STINTS if drv == driver]
    if all_stints:
        return sorted(all_stints)[-1][1]
    return "Unknown"


def get_team_drivers(team: str, round_number: int = TOTAL_ROUNDS) -> list:
    """Return the drivers racing for a team at a given round."""
    return [
        drv
        for (drv, t, frm, to) in DRIVER_STINTS
        if t == team and frm <= round_number <= to
    ]


# Convenience static dict — each driver mapped to their END-OF-SEASON team.
# Used for colour coding in charts where round context isn't available.
_seen = {}
for drv, team, frm, to in DRIVER_STINTS:
    _seen[drv] = team   # last write wins → most recent/final team
DRIVER_TEAMS = _seen


# ── Driver code → full name (for FastF1 compatibility) ─────────────────────────
DRIVER_CODE_MAP = {
    "VER": "Max Verstappen",
    "LAW": "Liam Lawson",
    "LEC": "Charles Leclerc",
    "HAM": "Lewis Hamilton",
    "NOR": "Lando Norris",
    "PIA": "Oscar Piastri",
    "RUS": "George Russell",
    "ANT": "Andrea Kimi Antonelli",
    "ALO": "Fernando Alonso",
    "STR": "Lance Stroll",
    "GAS": "Pierre Gasly",
    "DOO": "Jack Doohan",
    "COL": "Franco Colapinto",
    "ALB": "Alexander Albon",
    "SAI": "Carlos Sainz",
    "TSU": "Yuki Tsunoda",
    "HAD": "Isack Hadjar",
    "HUL": "Nico Hülkenberg",       # API returns umlaut ü
    "BOR": "Gabriel Bortoleto",
    "OCO": "Esteban Ocon",
    "BEA": "Oliver Bearman",
}

# Drivers to highlight in championship battle view
TITLE_CONTENDERS = ["Max Verstappen", "Lando Norris", "Charles Leclerc", "Oscar Piastri", "George Russell"]

# All drivers who appeared in 2025 (including mid-season replacements)
ALL_2025_DRIVERS = list(dict.fromkeys(drv for drv, *_ in DRIVER_STINTS))  # order-preserving unique

# Sprint weekends in 2025 (confirmed from race results data)
SPRINT_ROUNDS = {2, 6, 13, 19, 21, 23}  # China, Miami, Belgium, USA, São Paulo, Qatar

# F1 2025 Points system
POINTS_SYSTEM = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10,
                 6: 8,  7: 6,  8: 4,  9: 2, 10: 1}
FASTEST_LAP_POINT = 1   # awarded if finisher is in top 10
SPRINT_POINTS = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}