"""
Created on Fri Feb 20 12:24:31 2026

@author: sid
"""

# points_calculator.py — Championship story metrics & derived analytics
#
# Takes the raw standings DataFrame and computes:
#   • Points gap between championship leader and each driver
#   • "Momentum score" (rolling points per race)
#   • Deficit/recovery tracking for Verstappen comeback
#   • Win / podium streaks
#   • Points-per-race averages by phase of the season

import pandas as pd
import numpy as np
from config import TITLE_CONTENDERS


class ChampionshipStoryCalculator:
    """
    Derives championship narrative metrics from cumulative standings data.

    Parameters
    ----------
    standings_df : pd.DataFrame
        Output of F1DataFetcher.get_standings_after_each_race()
        Columns: round, race_name, country, driver, points, position, wins
    """

    def __init__(self, standings_df: pd.DataFrame):
        self.df = standings_df.copy()
        self.df = self.df.sort_values(["driver", "round"]).reset_index(drop=True)

    # ──────────────────────────────────────────────────────────────────────
    # Core story metrics
    # ──────────────────────────────────────────────────────────────────────

    def get_points_per_race(self) -> pd.DataFrame:
        """
        Returns points earned in each individual race (not cumulative).
        Derived by differencing consecutive cumulative totals.
        """
        df = self.df.copy()
        df["points_earned"] = df.groupby("driver")["points"].diff().fillna(df["points"])
        return df

    def get_championship_gap(self) -> pd.DataFrame:
        """
        For every round, compute the gap of each driver TO the leader.
        Positive gap = points behind leader.
        """
        df = self.df.copy()
        leader_pts = (
            df.groupby("round")["points"]
            .max()
            .rename("leader_points")
            .reset_index()
        )
        df = df.merge(leader_pts, on="round")
        df["gap_to_leader"] = df["leader_points"] - df["points"]
        return df

    def get_momentum_scores(self, window: int = 4) -> pd.DataFrame:
        """
        Rolling average of points earned per race over `window` races.
        A high momentum score = driver is in form; great for showing comeback.
        """
        per_race = self.get_points_per_race()
        per_race["momentum"] = (
            per_race.groupby("driver")["points_earned"]
            .transform(lambda x: x.rolling(window, min_periods=1).mean())
        )
        return per_race

    def get_verstappen_comeback_story(self, verstappen_name: str = "Max Verstappen") -> pd.DataFrame:
        """
        Focused view on Verstappen's deficit and recovery arc.
        Returns a DataFrame tracking his gap to the championship leader
        each race, and the rival leading at that point.
        """
        gap_df = self.get_championship_gap()
        ver_df  = gap_df[gap_df["driver"] == verstappen_name].copy()

        # Who was leading when VER was at his largest deficit?
        leader_each_round = (
            gap_df[gap_df["gap_to_leader"] == 0][["round", "driver"]]
            .rename(columns={"driver": "leader"})
        )
        ver_df = ver_df.merge(leader_each_round, on="round", how="left")

        # Tag the "dark period" (largest deficit) vs "recovery"
        max_deficit_round = ver_df.loc[ver_df["gap_to_leader"].idxmax(), "round"]
        ver_df["phase"] = np.where(
            ver_df["round"] <= max_deficit_round, "Deficit Phase", "Recovery Phase"
        )
        return ver_df

    def get_season_phases(self, n_phases: int = 3) -> pd.DataFrame:
        """
        Split the season into thirds (early / mid / late) and compute
        average points per race for each contender in each phase.
        """
        per_race = self.get_points_per_race()
        contenders = per_race[per_race["driver"].isin(TITLE_CONTENDERS)].copy()

        max_round = contenders["round"].max()
        phase_size = max_round // n_phases

        def assign_phase(rnd):
            if rnd <= phase_size:
                return "Early Season"
            elif rnd <= phase_size * 2:
                return "Mid Season"
            else:
                return "Late Season"

        contenders["phase"] = contenders["round"].apply(assign_phase)
        summary = (
            contenders.groupby(["driver", "phase"])["points_earned"]
            .mean()
            .reset_index()
            .rename(columns={"points_earned": "avg_points_per_race"})
        )
        # Force correct ordering
        phase_order = ["Early Season", "Mid Season", "Late Season"]
        summary["phase"] = pd.Categorical(summary["phase"], categories=phase_order, ordered=True)
        return summary.sort_values(["driver", "phase"])

    def get_win_streaks(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """
        Given per-race results (flat), compute win streaks and podium runs
        for each driver over the season.
        """
        race_results = results_df[~results_df["is_sprint"]].copy()
        race_results = race_results.sort_values(["driver", "round"])

        def streak_stats(group):
            wins = (group["position"] == 1).astype(int)
            podiums = (group["position"] <= 3).astype(int)
            max_win_streak = self._max_streak(wins)
            max_podium_streak = self._max_streak(podiums)
            return pd.Series({
                "total_wins":         wins.sum(),
                "total_podiums":      podiums.sum(),
                "max_win_streak":     max_win_streak,
                "max_podium_streak":  max_podium_streak,
                "dnfs":               (group["status"] != "Finished").sum()
                                       - (group["status"].str.contains("Lap", na=False)).sum(),
            })

        return race_results.groupby("driver").apply(streak_stats).reset_index()

    def get_head_to_head(self, driver_a: str, driver_b: str) -> pd.DataFrame:
        """
        Round-by-round comparison of two drivers' cumulative points.
        Includes who was leading at each point in the season.
        """
        df = self.df[self.df["driver"].isin([driver_a, driver_b])].copy()
        pivot = df.pivot(index="round", columns="driver", values="points").reset_index()
        pivot.columns.name = None
        pivot["leading"] = np.where(
            pivot.get(driver_a, 0) >= pivot.get(driver_b, 0),
            driver_a, driver_b
        )
        pivot["gap"] = abs(
            pivot.get(driver_a, pd.Series(dtype=float)) -
            pivot.get(driver_b, pd.Series(dtype=float))
        )
        return pivot

    def get_championship_summary(self) -> pd.DataFrame:
        """Final standings with key stats for the season summary card."""
        final_round = self.df["round"].max()
        final = self.df[self.df["round"] == final_round].copy()
        final = final.sort_values("position")
        return final[["position", "driver", "points", "wins"]]

    # ──────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _max_streak(binary_series: pd.Series) -> int:
        max_s = cur_s = 0
        for v in binary_series:
            if v == 1:
                cur_s += 1
                max_s = max(max_s, cur_s)
            else:
                cur_s = 0
        return max_s


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from data_fetcher import F1DataFetcher
    fetcher   = F1DataFetcher()
    standings = fetcher.get_standings_after_each_race()
    calc      = ChampionshipStoryCalculator(standings)

    print("=== Verstappen comeback arc ===")
    print(calc.get_verstappen_comeback_story().to_string(index=False))

    print("\n=== Final Championship Standings ===")
    print(calc.get_championship_summary().to_string(index=False))

    print("\n=== Season phase analysis ===")
    print(calc.get_season_phases().to_string(index=False))