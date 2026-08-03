"""
utils.py
--------
Small helper functions used by the Streamlit app.
Loads the HESS dataset and maps it to the decision engine inputs.
"""

import os
import pandas as pd
from decision_engine import decide_energy_sources


# colours used in charts (green = renewable, orange = battery, red = grid)
color_solar = "#2E8B57"
color_wind = "#3CB371"
color_renew = "#2E8B57"
color_batt = "#E67E22"
color_grid = "#C0392B"

COLOUR_SOLAR = color_solar
COLOUR_WIND = color_wind
COLOUR_RENEWABLE = color_renew
COLOUR_BATTERY = color_batt
COLOUR_GRID = color_grid
COLOUR_NEUTRAL = "#34495E"

SOURCE_COLOURS = {
    "Solar": color_solar,
    "Wind": color_wind,
    "Battery": color_batt,
    "Grid": color_grid,
}


def with_one_based_index(df):
    # streamlit tables start at 0 by default – change to 1
    out = df.copy()
    out.index = range(1, len(out) + 1)
    out.index.name = "#"
    return out


def get_data_folder():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def get_hess_path():
    return os.path.join(get_data_folder(), "HESS_Dataset.csv")


def get_data_path():
    # kept for older references – main data is now HESS_Dataset.csv
    return get_hess_path()


def hour_to_time_label(hour):
    # simple time-of-day buckets from timestamp hour
    hour = int(hour)
    if 5 <= hour <= 11:
        return "Morning"
    if 12 <= hour <= 16:
        return "Afternoon"
    if 17 <= hour <= 20:
        return "Evening"
    return "Night"


def guess_weather(solar_kw):
    # dataset has no weather column, so we estimate from solar level
    if solar_kw >= 30:
        return "Sunny"
    if solar_kw >= 15:
        return "Cloudy"
    return "Rainy"


def prepare_hess_dataframe(raw_df):
    """
    Map HESS columns to the names used by the decision engine:
    solar, wind, load, battery, weather, time
    Also keeps useful original columns for display.
    """
    df = raw_df.copy()
    df = df.dropna(subset=["Solar_Power_kW", "Wind_Power_kW", "Load_Demand_kW", "Battery_SoC_%"])

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.dropna(subset=["Timestamp"])

    df["solar"] = df["Solar_Power_kW"].astype(float).round(2)
    df["wind"] = df["Wind_Power_kW"].astype(float).round(2)
    df["load"] = df["Load_Demand_kW"].astype(float).round(2)
    df["battery"] = df["Battery_SoC_%"].astype(float).round(1)
    df["time"] = df["Timestamp"].dt.hour.apply(hour_to_time_label)
    df["weather"] = df["solar"].apply(guess_weather)

    # keep a few original fields for the Sample Scenarios page
    if "Grid_Power_kW" in df.columns:
        df["grid_from_dataset"] = df["Grid_Power_kW"].astype(float).round(2)
    if "Power_Supplied_kW" in df.columns:
        df["power_supplied"] = df["Power_Supplied_kW"].astype(float).round(2)
    if "Power_Loss_kW" in df.columns:
        df["power_loss"] = df["Power_Loss_kW"].astype(float).round(2)

    df = df.reset_index(drop=True)
    return df


def load_sample_data():
    """
    Load the HESS dataset and return mapped rows for the app.
    """
    path = get_hess_path()
    raw = pd.read_csv(path)
    return prepare_hess_dataframe(raw)


def run_simulation(solar, wind, load, battery, weather, time_of_day):
    # thin wrapper so we don't repeat args everywhere
    return decide_energy_sources(
        solar_kw=float(solar),
        wind_kw=float(wind),
        load_kw=float(load),
        battery_percent=float(battery),
        weather=str(weather),
        time_of_day=str(time_of_day),
    )


def run_simulation_on_row(row):
    return run_simulation(
        solar=row["solar"],
        wind=row["wind"],
        load=row["load"],
        battery=row["battery"],
        weather=row["weather"],
        time_of_day=row["time"],
    )


def result_to_log_row(result):
    return {
        "Time": result["time"],
        "Weather": result["weather"],
        "Load": result["load_input"],
        "Solar": result["solar_input"],
        "Wind": result["wind_input"],
        "Battery": result["battery_input"],
        "Decision": result["selected_source"],
        "Grid Used": result["grid_used"],
        "Renewable %": result["renewable_pct"],
    }


def simulate_all_scenarios(df=None, max_rows=None):
    if df is None:
        df = load_sample_data()

    # for the Results page we can limit rows if needed (default: all)
    if max_rows is not None:
        df = df.head(max_rows)

    rows = []
    for i, row in df.iterrows():
        out = run_simulation_on_row(row)
        rows.append({
            "scenario": i + 1,
            "timestamp": str(row["Timestamp"]) if "Timestamp" in row else "",
            "solar": row["solar"],
            "wind": row["wind"],
            "load": row["load"],
            "battery": row["battery"],
            "weather": row["weather"],
            "time": row["time"],
            "selected_source": out["selected_source"],
            "solar_used": out["solar_used"],
            "wind_used": out["wind_used"],
            "battery_used": out["battery_used"],
            "grid_used": out["grid_used"],
            "battery_remaining": out["battery_remaining"],
            "renewable_utilisation": out["renewable_pct"],
            "grid_dependency": out["grid_pct"],
            "co2_saving": out["co2_saving"],
            "cost_saving": out["cost_saving"],
            "system_efficiency": out["system_efficiency"],
        })

    return pd.DataFrame(rows)


def calculate_summary(results_df):
    return {
        "avg_renewable_usage": round(float(results_df["renewable_utilisation"].mean()), 1),
        "avg_grid_usage": round(float(results_df["grid_dependency"].mean()), 1),
        "avg_battery_used": round(float(results_df["battery_used"].mean()), 2),
        "total_cost_saving": round(float(results_df["cost_saving"].sum()), 2),
        "total_co2_saving": round(float(results_df["co2_saving"].sum()), 2),
        "avg_cost_saving": round(float(results_df["cost_saving"].mean()), 2),
        "avg_co2_saving": round(float(results_df["co2_saving"].mean()), 2),
        "num_scenarios": len(results_df),
    }


def compare_scenarios(result_a, result_b, label_a="Scenario A", label_b="Scenario B"):
    checks = [
        ("Renewable Usage %", "renewable_pct", True),
        ("Grid Usage %", "grid_pct", False),
        ("Battery Usage (kW)", "battery_used", True),
        ("Cost Saving (£)", "cost_saving", True),
        ("CO₂ Saving (kg)", "co2_saving", True),
    ]

    table_rows = []
    notes = []

    for title, key, higher_better in checks:
        a_val = result_a[key]
        b_val = result_b[key]

        if a_val == b_val:
            winner = "Tie"
        elif higher_better:
            winner = label_a if a_val > b_val else label_b
        else:
            winner = label_a if a_val < b_val else label_b

        table_rows.append({
            "Metric": title,
            label_a: a_val,
            label_b: b_val,
            "Better": winner,
        })

        if winner != "Tie":
            notes.append(f"{title}: **{winner}** looks better.")

    return pd.DataFrame(table_rows), notes


# 10 fixed tests – values closer to the HESS dataset scale
TEST_SCENARIOS = [
    {
        "name": "Sunny Morning",
        "solar": 42.0, "wind": 12.0, "load": 45.0, "battery": 80,
        "weather": "Sunny", "time": "Morning",
        "expected_decision": "Mostly solar (+ wind if needed)",
        "expected_notes": "High solar – renewables should cover a large share.",
    },
    {
        "name": "Cloudy Afternoon",
        "solar": 22.0, "wind": 18.0, "load": 55.0, "battery": 60,
        "weather": "Cloudy", "time": "Afternoon",
        "expected_decision": "Solar + Wind (maybe battery)",
        "expected_notes": "Medium solar, so wind/battery may help.",
    },
    {
        "name": "Rainy Evening",
        "solar": 8.0, "wind": 28.0, "load": 60.0, "battery": 55,
        "weather": "Rainy", "time": "Evening",
        "expected_decision": "Wind + battery / grid",
        "expected_notes": "Low solar in rain/evening.",
    },
    {
        "name": "Night High Load",
        "solar": 5.0, "wind": 15.0, "load": 75.0, "battery": 50,
        "weather": "Cloudy", "time": "Night",
        "expected_decision": "Wind + battery + grid",
        "expected_notes": "Night + high load – grid is likely.",
    },
    {
        "name": "Battery Low",
        "solar": 15.0, "wind": 10.0, "load": 65.0, "battery": 22,
        "weather": "Cloudy", "time": "Evening",
        "expected_decision": "Solar/Wind + Grid (no battery)",
        "expected_notes": "Battery under 30% so it should not discharge.",
    },
    {
        "name": "Battery Full",
        "solar": 45.0, "wind": 20.0, "load": 40.0, "battery": 95,
        "weather": "Sunny", "time": "Afternoon",
        "expected_decision": "Solar + Wind",
        "expected_notes": "Battery already full, little room to charge.",
    },
    {
        "name": "High Wind",
        "solar": 10.0, "wind": 38.0, "load": 50.0, "battery": 70,
        "weather": "Rainy", "time": "Afternoon",
        "expected_decision": "Mostly wind",
        "expected_notes": "Strong wind should cover a lot of the load.",
    },
    {
        "name": "Peak Load",
        "solar": 25.0, "wind": 15.0, "load": 78.0, "battery": 65,
        "weather": "Sunny", "time": "Evening",
        "expected_decision": "Mix including grid",
        "expected_notes": "Peak load usually needs more than one source.",
    },
    {
        "name": "Low Demand",
        "solar": 35.0, "wind": 18.0, "load": 32.0, "battery": 50,
        "weather": "Sunny", "time": "Morning",
        "expected_decision": "Solar (+ wind)",
        "expected_notes": "Lower demand – renewables should be enough.",
    },
    {
        "name": "Balanced Energy",
        "solar": 30.0, "wind": 20.0, "load": 50.0, "battery": 60,
        "weather": "Sunny", "time": "Afternoon",
        "expected_decision": "Solar + Wind",
        "expected_notes": "Supply and demand are fairly close.",
    },
]


def run_test_scenario(test_case):
    return run_simulation(
        solar=test_case["solar"],
        wind=test_case["wind"],
        load=test_case["load"],
        battery=test_case["battery"],
        weather=test_case["weather"],
        time_of_day=test_case["time"],
    )


def get_decision_flow_dot(selected_source="Selected Source"):
    label = selected_source.replace('"', "'")
    return f"""
    digraph DecisionFlow {{
        rankdir=TB;
        node [shape=box, style="rounded,filled", fontsize=11];

        inputs [label="Inputs\\n(Solar, Wind, Load, Battery, Weather, Time)", fillcolor="#D5F5E3"];
        engine [label="Decision Engine\\n(if/else rules)", fillcolor="#FCF3CF"];
        source [label="Selected Source\\n{label}", fillcolor="#D6EAF8"];
        alloc  [label="Energy Allocation\\n(Solar / Wind / Battery / Grid)", fillcolor="#FAD7A0"];
        results [label="Results\\n(numbers + charts)", fillcolor="#D5F5E3"];

        inputs -> engine;
        engine -> source;
        source -> alloc;
        alloc -> results;
    }}
    """
