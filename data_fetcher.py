"""
Created on Fri Feb 20 12:23:52 2026

@author: sid
"""
# data_fetcher.py — Fetches F1 2025 season data from Jolpica API + FastF1
#
# Primary source : Jolpica API  (https://api.jolpi.ca/ergast/f1)
# Secondary source: FastF1      (for lap-level telemetry if needed)
#
# Usage:
#   fetcher = F1DataFetcher()
#   results = fetcher.get_all_race_results()        # list of per-race DataFrames
#   standings = fetcher.get_standings_after_each_race()  # cumulative points

import time
import requests
import pandas as pd
import numpy as np
from pathlib import Path
import json
import fastf1

import config

# ── Cache setup ────────────────────────────────────────────────────────────────
CACHE_FILE = Path("./data_cache/season_2025.json")
CACHE_FILE.parent.mkdir(exist_ok=True)

CSV_DIR = Path("./data_csv")
CSV_DIR.mkdir(exist_ok=True)

# FastF1 requires the cache directory to exist before enabling it
Path(config.CACHE_DIR).mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(config.CACHE_DIR)


class F1DataFetcher:
    """Fetches and caches 2025 F1 season data."""

    BASE = config.JOLPICA_BASE
    SEASON = config.SEASON

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_race_schedule(self) -> pd.DataFrame:
        """Return the 2025 race calendar."""
        url = f"{self.BASE}/{self.SEASON}.json?limit={config.TOTAL_ROUNDS}"
        data = self._get(url)
        races = data["MRData"]["RaceTable"]["Races"]
        rows = []
        for r in races:
            rnd = int(r["round"])
            rows.append({
                "round":      rnd,
                "name":       r["raceName"],
                "circuit":    r["Circuit"]["circuitName"],
                "country":    r["Circuit"]["Location"]["country"],
                "date":       r["date"],
                "has_sprint": rnd in config.SPRINT_ROUNDS,  # API field unreliable — use known set
            })
        df = pd.DataFrame(rows)
        df.to_csv(CSV_DIR / "schedule_2025.csv", index=False)
        print(f"[DataFetcher] Saved schedule → data_csv/schedule_2025.csv")
        return df

    def get_all_race_results(self) -> pd.DataFrame:
        """
        Returns a flat DataFrame of every race result in 2025.
        Columns: round, race_name, driver, constructor, position,
                 points, fastest_lap, status
        """
        if CACHE_FILE.exists():
            return pd.read_json(CACHE_FILE)

        all_rows = []
        schedule = self.get_race_schedule()

        for _, race in schedule.iterrows():
            rnd = race["round"]
            results = self._fetch_race_results(rnd)
            sprint   = self._fetch_sprint_results(rnd)

            for row in results:
                row["round"]     = rnd
                row["race_name"] = race["name"]
                all_rows.append(row)

            for row in sprint:
                row["round"]     = rnd
                row["race_name"] = race["name"]
                row["is_sprint"] = True
                all_rows.append(row)

            time.sleep(0.3)   # be polite to the API

        df = pd.DataFrame(all_rows)
        df.to_json(CACHE_FILE)
        df.to_csv(CSV_DIR / "race_results_2025.csv", index=False)
        print(f"[DataFetcher] Saved race results → data_csv/race_results_2025.csv")
        return df

    def get_standings_after_each_race(self) -> pd.DataFrame:
        """
        Returns a DataFrame where each row = (round, driver, cumulative_points).
        This drives all the championship story visualisations.
        """
        all_rounds = []
        schedule = self.get_race_schedule()

        for _, race in schedule.iterrows():
            rnd = race["round"]
            url = f"{self.BASE}/{self.SEASON}/{rnd}/driverStandings.json"
            data = self._get(url)
            try:
                standings_list = (
                    data["MRData"]["StandingsTable"]
                       ["StandingsLists"][0]["DriverStandings"]
                )
            except (KeyError, IndexError):
                continue   # race hasn't happened yet

            for entry in standings_list:
                driver_surname = entry["Driver"]["familyName"]
                driver_given   = entry["Driver"]["givenName"]
                full_name = f"{driver_given} {driver_surname}"
                full_name = self._normalise_name(full_name)

                all_rounds.append({
                    "round":       rnd,
                    "race_name":   race["name"],
                    "country":     race["country"],
                    "driver":      full_name,
                    "constructor": entry["Constructors"][0]["name"] if entry["Constructors"] else "Unknown",
                    "points":      float(entry["points"]),
                    "position":    self._safe_int(entry.get("position") or entry.get("positionText")),
                    "wins":        int(entry["wins"]),
                })
            time.sleep(0.3)

        df = pd.DataFrame(all_rounds)
        df.to_csv(CSV_DIR / "standings_by_round_2025.csv", index=False)
        print(f"[DataFetcher] Saved standings → data_csv/standings_by_round_2025.csv")
        return df

    def get_qualifying_telemetry(self, round_number: int, driver_code: str):
        """
        Return the fastest qualifying lap telemetry for a driver in a given round.
        Uses FastF1 for lap-level data.
        """
        session = fastf1.get_session(self.SEASON, round_number, "Q")
        session.load(telemetry=True, weather=False, messages=False)
        laps = session.laps.pick_driver(driver_code)
        fastest = laps.pick_fastest()
        telemetry = fastest.get_telemetry()
        return telemetry

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_race_results(self, round_number: int) -> list[dict]:
        url = f"{self.BASE}/{self.SEASON}/{round_number}/results.json"
        data = self._get(url)
        try:
            raw = data["MRData"]["RaceTable"]["Races"][0]["Results"]
        except (KeyError, IndexError):
            return []

        rows = []
        for r in raw:
            driver_name = self._normalise_name(
                f"{r['Driver']['givenName']} {r['Driver']['familyName']}"
            )
            fl_point = 0
            if r.get("FastestLap", {}).get("rank") == "1":
                try:
                    pos = int(r.get("position", 99))
                    if pos <= 10:
                        fl_point = 1
                except ValueError:
                    pass

            rows.append({
                "driver":      driver_name,
                "constructor": r["Constructor"]["name"],
                "position":    self._safe_int(r.get("position")),
                "grid":        self._safe_int(r.get("grid")),
                "points":      float(r.get("points", 0)),
                "fastest_lap_point": fl_point,
                "status":      r.get("status", ""),
                "is_sprint":   False,
            })
        return rows

    def _fetch_sprint_results(self, round_number: int) -> list[dict]:
        url = f"{self.BASE}/{self.SEASON}/{round_number}/sprint.json"
        data = self._get(url)
        try:
            raw = data["MRData"]["RaceTable"]["Races"][0]["SprintResults"]
        except (KeyError, IndexError):
            return []

        rows = []
        for r in raw:
            driver_name = self._normalise_name(
                f"{r['Driver']['givenName']} {r['Driver']['familyName']}"
            )
            rows.append({
                "driver":      driver_name,
                "constructor": r["Constructor"]["name"],
                "position":    self._safe_int(r.get("position")),
                "grid":        self._safe_int(r.get("grid")),
                "points":      float(r.get("points", 0)),
                "fastest_lap_point": 0,
                "status":      r.get("status", ""),
                "is_sprint":   True,
            })
        return rows

    def _get(self, url: str) -> dict:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[DataFetcher] Warning: {e} for {url}")
            return {}

    @staticmethod
    def _normalise_name(name: str) -> str:
        """
        Normalise driver names to match API output exactly.
        The API is the source of truth — config.py mirrors it.
        """
        mapping = {
            "Kimi Antonelli":  "Andrea Kimi Antonelli",
            "Nico Hulkenberg": "Nico Hülkenberg",   # ensure umlaut is always present
        }
        for k, v in mapping.items():
            if k in name:
                return v
        return name

    @staticmethod
    def _safe_int(val) -> int:
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    fetcher = F1DataFetcher()

    print("Fetching 2025 schedule...")
    schedule = fetcher.get_race_schedule()
    print(schedule[["round", "name", "country"]].to_string(index=False))

    print("\nFetching all race results...")
    results = fetcher.get_all_race_results()
    print(f"  → {len(results)} rows fetched")
    print(results.head(10).to_string(index=False))

    print("\nFetching championship standings after each race...")
    standings = fetcher.get_standings_after_each_race()
    print(f"  → {len(standings)} rows fetched")
    print(standings[standings["driver"] == "Max Verstappen"].to_string(index=False))

    print("\n✅ All CSVs saved to ./data_csv/")
    print("   • data_csv/schedule_2025.csv")
    print("   • data_csv/race_results_2025.csv")
    print("   • data_csv/standings_by_round_2025.csv")