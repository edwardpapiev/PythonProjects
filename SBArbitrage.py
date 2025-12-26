# -*- coding: utf-8 -*-
"""
Created on Sat Jan  4 20:28:02 2025

@author: Edward Papiev
"""
import requests as rq
import pandas as pd
import numpy as np
from datetime import datetime

stake = 100

api_key = "9126553aa7a47dbdae115638e9c52c1a"
base_url = "https://api.the-odds-api.com/v4/sports"


# basic odds fetcher helper function
def pullodds(sport="upcoming", odds_format="decimal"):
    url = f"{base_url}/{sport}/odds"
    params = {
        "apiKey": api_key,
        "bookmakers": "betmgm,fanduel,draftkings,sport888,betway,betvictor",
        "market": "h2h,totals",
        "oddsFormat": odds_format,
    }
    response = rq.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None


def normalize_data(odds_data):
    bookmakers_df = pd.json_normalize(
        odds_data,
        record_path="bookmakers",
        meta=["id", "sport_key", "sport_title", "commence_time", "home_team", "away_team"],
        record_prefix="bookmaker_",
    )

    markets_df = pd.json_normalize(
        bookmakers_df.to_dict(orient="records"),
        record_path="bookmaker_markets",
        meta=[
            "bookmaker_key", "bookmaker_title", "bookmaker_last_update", "id","sport_key",
            "sport_title", "commence_time", "home_team", "away_team",
        ],
        record_prefix="market_",
    )

    return markets_df


def _parse_commence_time(ts: str) -> datetime:
    # Handles ISO time strings
    if isinstance(ts, str) and ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def calculate_arbitrage(df: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    """
    Supports:
      - market_key == 'h2h' (2-way or 3-way incl Draw/Tie)
      - market_key == 'totals' (Over/Under), grouped by outcome 'point'
    Returns all opportunities sorted by largest ROI (profit_margin) by default.
    """
    expected_cols = [
        "id",
        "market",
        "line",  # totals point; NaN for h2h
        "sport",
        "time",
        "book1",
        "side1",
        "odds1",
        "book2",
        "side2",
        "odds2",
        "book3",  # optional (3-way h2h)
        "side3",  # optional (3-way h2h)
        "odds3",  # optional (3-way h2h)
        "inv_odds_sum",
        "profit_margin",
        "num_legs",
    ]

    if df is None or df.empty:
        return pd.DataFrame(columns=expected_cols)

    if "market_key" not in df.columns:
        raise KeyError("Expected column 'market_key' in normalized markets dataframe.")

    arbitrage_opportunities = []

    for (event_id, market_key), subset in df.groupby(["id", "market_key"], dropna=False):
        if market_key not in {"h2h", "totals"}:
            continue

        sport = subset["sport_title"].iloc[0] if "sport_title" in subset.columns and not subset.empty else ""
        try:
            d1 = _parse_commence_time(subset["commence_time"].iloc[0])
            readable_date = d1.strftime("%B %d, %Y at %I:%M %p")
        except Exception:
            readable_date = str(subset["commence_time"].iloc[0]) if "commence_time" in subset.columns else ""

        # Flatten outcomes to one-row-per-outcome
        flat = []
        for _, row in subset.iterrows():
            outcomes = row.get("market_outcomes", None)
            if not isinstance(outcomes, list):
                continue

            for o in outcomes:
                if not isinstance(o, dict):
                    continue

                price = o.get("price", None)
                if price in (None, 0, "0"):
                    continue

                flat.append(
                    {
                        "book": row.get("bookmaker_title", ""),
                        "name": o.get("name", ""),          # team OR "Draw"/"Tie" OR "Over"/"Under"
                        "price": price,
                        "point": o.get("point", np.nan),    # totals line
                    }
                )

        if not flat:
            continue

        flat_df = pd.DataFrame(flat)
        flat_df["price"] = pd.to_numeric(flat_df["price"], errors="coerce")
        flat_df = flat_df.dropna(subset=["price"])
        if flat_df.empty:
            continue

        if market_key == "h2h":
            # Consolidate per side (including Draw/Tie if present)
            flat_df = flat_df.copy()
            flat_df["name_norm"] = flat_df["name"].astype(str).str.strip()

            best_by_side = (
                flat_df.sort_values("price", ascending=False)
                .groupby("name_norm", as_index=False)
                .first()
            )

            # Support 2-way or 3-way only
            if len(best_by_side) not in (2, 3):
                continue

            legs = best_by_side.sort_values("price", ascending=False).to_dict("records")
            inv_odds_sum = sum(1 / float(leg["price"]) for leg in legs)

            if inv_odds_sum < 1:
                opp = {
                    "id": event_id,
                    "market": market_key,
                    "line": np.nan,
                    "sport": sport,
                    "time": readable_date,
                    "book1": legs[0]["book"],
                    "side1": legs[0]["name_norm"],
                    "odds1": legs[0]["price"],
                    "book2": legs[1]["book"],
                    "side2": legs[1]["name_norm"],
                    "odds2": legs[1]["price"],
                    "book3": np.nan,
                    "side3": np.nan,
                    "odds3": np.nan,
                    "inv_odds_sum": inv_odds_sum,
                    "num_legs": len(legs),
                }
                if len(legs) == 3:
                    opp["book3"] = legs[2]["book"]
                    opp["side3"] = legs[2]["name_norm"]
                    opp["odds3"] = legs[2]["price"]

                arbitrage_opportunities.append(opp)

        elif market_key == "totals":
            # Evaluate ALL totals lines offered: group by point
            for point, g in flat_df.groupby("point", dropna=True):
                g2 = g.copy()
                g2["name_norm"] = g2["name"].astype(str).str.strip().str.lower()

                over = g2[g2["name_norm"] == "over"].sort_values("price", ascending=False).head(1)
                under = g2[g2["name_norm"] == "under"].sort_values("price", ascending=False).head(1)

                if over.empty or under.empty:
                    continue

                o = over.iloc[0].to_dict()
                u = under.iloc[0].to_dict()

                inv_odds_sum = (1 / float(o["price"])) + (1 / float(u["price"]))
                if inv_odds_sum < 1:
                    arbitrage_opportunities.append(
                        {
                            "id": event_id,
                            "market": market_key,
                            "line": point,
                            "sport": sport,
                            "time": readable_date,
                            "book1": o["book"],
                            "side1": "Over",
                            "odds1": o["price"],
                            "book2": u["book"],
                            "side2": "Under",
                            "odds2": u["price"],
                            "book3": np.nan,
                            "side3": np.nan,
                            "odds3": np.nan,
                            "inv_odds_sum": inv_odds_sum,
                            "num_legs": 2,
                        }
                    )

    if not arbitrage_opportunities:
        return pd.DataFrame(columns=expected_cols)

    arb = pd.DataFrame(arbitrage_opportunities)
    arb["profit_margin"] = (1 - arb["inv_odds_sum"]) * 100
    arb = arb.sort_values(by="profit_margin", ascending=False)

    if top_n is not None:
        arb = arb.head(int(top_n))

    return arb


def calc_all(df: pd.DataFrame) -> pd.DataFrame:
    expected_cols = [
        "market",
        "line",
        "sport",
        "time",
        "num_legs",
        "side1",
        "book1",
        "odds1",
        "allocation1",
        "side2",
        "book2",
        "odds2",
        "allocation2",
        "side3",
        "book3",
        "odds3",
        "allocation3",
        "ROI",
        "total_allocation",
        "payout1",
        "payout2",
        "payout3",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=expected_cols)

    allocations = []
    for _, row in df.iterrows():
        inv_sum = float(row["inv_odds_sum"])

        o1 = float(row["odds1"])
        o2 = float(row["odds2"])
        has_third = pd.notna(row.get("odds3", np.nan))

        allocation1 = (1 / o1) / inv_sum * stake
        allocation2 = (1 / o2) / inv_sum * stake

        allocation3 = np.nan
        o3 = np.nan
        if has_third:
            o3 = float(row["odds3"])
            allocation3 = (1 / o3) / inv_sum * stake

        allocations.append(
            {
                "market": row["market"],
                "line": row["line"],
                "sport": row["sport"],
                "time": row["time"],
                "num_legs": int(row.get("num_legs", 3 if has_third else 2)),
                "side1": row["side1"],
                "book1": row["book1"],
                "odds1": o1,
                "allocation1": allocation1,
                "side2": row["side2"],
                "book2": row["book2"],
                "odds2": o2,
                "allocation2": allocation2,
                "side3": row.get("side3", np.nan),
                "book3": row.get("book3", np.nan),
                "odds3": o3 if has_third else np.nan,
                "allocation3": allocation3 if has_third else np.nan,
                "ROI": row["profit_margin"],
            }
        )

    alloc = pd.DataFrame(allocations)
    alloc["total_allocation"] = alloc["allocation1"] + alloc["allocation2"] + alloc["allocation3"].fillna(0.0)
    alloc["payout1"] = alloc["odds1"] * alloc["allocation1"]
    alloc["payout2"] = alloc["odds2"] * alloc["allocation2"]
    alloc["payout3"] = alloc["odds3"] * alloc["allocation3"]
    return alloc


if __name__ == "__main__":
    import streamlit as st

    # 1. Page Configuration
    st.set_page_config(page_title="Sportsbook Arbitrage Dashboard", layout="wide")
    st.title("🏆 Sportsbook Arbitrage Finder")
    st.markdown("Finding risk-free opportunities across major bookmakers.")

    # 2. Sidebar Configuration
    st.sidebar.header("Settings")
    api_key_input = st.sidebar.text_input("API Key", value=api_key, type="password")
    stake = st.sidebar.number_input("Total Stake ($)", min_value=10, max_value=10000, value=100)
    sport_choice = st.sidebar.selectbox("Select Sport", ["upcoming", "soccer_usa_mls", "americanfootball_nfl", "basketball_nba"])
    
    if st.sidebar.button("Refresh Odds"):
        st.cache_data.clear()

    # 3. Main Logic Execution
    with st.spinner("Fetching latest odds..."):
        api_key = api_key_input # Update global key from UI
        complete_data = pullodds(sport=sport_choice)
        
        if not complete_data:
            st.error("No data returned. Check your API key or limit.")
        else:
            flat_data = normalize_data(complete_data)
            arbitrage_df = calculate_arbitrage(flat_data)
            
            if arbitrage_df.empty:
                st.warning(f"No arbitrage opportunities found for {sport_choice} right now.")
            else:
                alloc_df = calc_all(arbitrage_df)

                # 4. Dashboard Metrics
                best_roi = alloc_df['ROI'].max()
                total_opps = len(alloc_df)
                
                col1, col2 = st.columns(2)
                col1.metric("Opportunities Found", total_opps)
                col2.metric("Best ROI", f"{best_roi:.2f}%")

                # 5. Presentation Table
                # We style the dataframe to highlight profit
                st.subheader("Current Arbitrage Opportunities")
                
                # Format numbers for better reading
                display_df = alloc_df.copy()
                cols_to_format = ['allocation1', 'allocation2', 'allocation3', 'payout1', 'payout2', 'payout3', 'ROI']
                for col in cols_to_format:
                    if col in display_df.columns:
                        display_df[col] = display_df[col].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")

                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True
                )

                st.success("Calculations complete. Markets are grouped by Event and Point Line.")

    # Optional
    # st.empty()
    # sleep(60)
    # st.rerun()

