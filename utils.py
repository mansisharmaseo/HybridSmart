"""
utils.py
--------
Small helper functions used by the Streamlit app.
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

# keep old names so older imports still work
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


def get_data_path():
    folder = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(folder, "data", "sample_energy_data.csv")


def load_sample_data():
    return pd.read_csv(get_data_path())


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


def simulate_all_scenarios(df=None):
    if df is None:
        df = load_sample_data()

    rows = []
    for i, row in df.iterrows():
        out = run_simulation_on_row(row)
        rows.append({
            "scenario": i + 1,
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
    # compare a few key numbers side by side
    checks = [
        ("Renewable Usage %", "renewable_pct", True),
        ("Grid Usage %", "grid_pct", False),  # lower is better
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


# 10 fixed tests for the Testing page
TEST_SCENARIOS = [
    {
        "name": "Sunny Morning",
        "solar": 5.5, "wind": 1.0, "load": 3.0, "battery": 80,
        "weather": "Sunny", "time": "Morning",
        "expected_decision": "Mostly solar",
        "expected_notes": "Sunny morning – solar should handle most of the load.",
    },
    {
        "name": "Cloudy Afternoon",
        "solar": 3.0, "wind": 1.5, "load": 3.5, "battery": 60,
        "weather": "Cloudy", "time": "Afternoon",
        "expected_decision": "Solar + Wind (maybe battery)",
        "expected_notes": "Clouds cut solar, so wind/battery may help.",
    },
    {
        "name": "Rainy Evening",
        "solar": 2.0, "wind": 2.2, "load": 4.0, "battery": 55,
        "weather": "Rainy", "time": "Evening",
        "expected_decision": "Wind + battery / grid",
        "expected_notes": "Rain + evening = weak solar.",
    },
    {
        "name": "Night High Load",
        "solar": 0.5, "wind": 1.8, "load": 5.0, "battery": 50,
        "weather": "Cloudy", "time": "Night",
        "expected_decision": "Wind + battery + grid",
        "expected_notes": "Night time, high load – grid is likely.",
    },
    {
        "name": "Battery Low",
        "solar": 2.0, "wind": 1.0, "load": 4.5, "battery": 22,
        "weather": "Cloudy", "time": "Evening",
        "expected_decision": "Solar/Wind + Grid (no battery)",
        "expected_notes": "Battery under 30% so it should not discharge.",
    },
    {
        "name": "Battery Full",
        "solar": 6.0, "wind": 1.2, "load": 2.5, "battery": 95,
        "weather": "Sunny", "time": "Afternoon",
        "expected_decision": "Solar",
        "expected_notes": "Battery already full, not much room to charge.",
    },
    {
        "name": "High Wind",
        "solar": 1.0, "wind": 4.0, "load": 3.5, "battery": 70,
        "weather": "Rainy", "time": "Afternoon",
        "expected_decision": "Mostly wind",
        "expected_notes": "Strong wind should cover a lot of the load.",
    },
    {
        "name": "Peak Load",
        "solar": 3.5, "wind": 1.5, "load": 7.0, "battery": 65,
        "weather": "Sunny", "time": "Evening",
        "expected_decision": "Mix including grid",
        "expected_notes": "Peak load usually needs more than one source.",
    },
    {
        "name": "Low Demand",
        "solar": 4.0, "wind": 1.5, "load": 1.5, "battery": 50,
        "weather": "Sunny", "time": "Morning",
        "expected_decision": "Solar only",
        "expected_notes": "Low demand – renewables should be enough.",
    },
    {
        "name": "Balanced Energy",
        "solar": 3.5, "wind": 1.5, "load": 3.5, "battery": 60,
        "weather": "Sunny", "time": "Afternoon",
        "expected_decision": "Solar (maybe + wind)",
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
