"""
app.py
------
Main Streamlit app for HybridSmart.
Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils import (
    COLOUR_BATTERY,
    COLOUR_GRID,
    COLOUR_RENEWABLE,
    COLOUR_SOLAR,
    SOURCE_COLOURS,
    TEST_SCENARIOS,
    calculate_summary,
    compare_scenarios,
    get_decision_flow_dot,
    load_sample_data,
    result_to_log_row,
    run_simulation,
    run_test_scenario,
    simulate_all_scenarios,
    with_one_based_index,
)
from report_generator import generate_simulation_report


st.set_page_config(page_title="HybridSmart", page_icon="⚡", layout="wide")

# tiny bit of styling + hide Streamlit chrome
st.markdown(
    """
    <style>
    div[data-testid="stMetricValue"] { font-size: 1.3rem; }
    [data-testid="stToolbarActions"] { display: none !important; }
    [data-testid="stAppHeader"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# store decisions during this browser session
if "decision_log" not in st.session_state:
    st.session_state.decision_log = []


def save_to_log(result):
    st.session_state.decision_log.append(result_to_log_row(result))


def draw_gauge(title, value, colour):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title, "font": {"size": 14}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": colour},
                "bgcolor": "#F2F3F4",
                "borderwidth": 1,
                "bordercolor": "#BDC3C7",
            },
            number={"suffix": "%"},
        )
    )
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=40, b=10))
    return fig


def pie_chart(result):
    data = pd.DataFrame({
        "Source": ["Solar", "Wind", "Battery", "Grid"],
        "kW": [
            result["solar_used"],
            result["wind_used"],
            result["battery_used"],
            result["grid_used"],
        ],
    })
    data = data[data["kW"] > 0]
    return px.pie(
        data,
        names="Source",
        values="kW",
        title="Energy Source Distribution",
        color="Source",
        color_discrete_map=SOURCE_COLOURS,
    )


def battery_bars(before, after):
    fig = go.Figure(
        data=[
            go.Bar(name="Before", x=["Battery"], y=[before], marker_color=COLOUR_BATTERY),
            go.Bar(name="After", x=["Battery"], y=[after], marker_color="#D35400"),
        ]
    )
    fig.update_layout(
        title="Battery Level (%)",
        barmode="group",
        yaxis_title="Percent",
        yaxis=dict(range=[0, 100]),
        height=350,
    )
    return fig


def renew_vs_grid_chart(result):
    data = pd.DataFrame({
        "Type": ["Renewable (Solar+Wind)", "Grid"],
        "kW": [result["solar_used"] + result["wind_used"], result["grid_used"]],
    })
    return px.bar(
        data,
        x="Type",
        y="kW",
        title="Renewable vs Grid Usage",
        color="Type",
        color_discrete_map={
            "Renewable (Solar+Wind)": COLOUR_RENEWABLE,
            "Grid": COLOUR_GRID,
        },
    )


def demand_supply_chart(result):
    data = pd.DataFrame({
        "Category": ["Demand (Load)", "Total Supply Used"],
        "kW": [result["load"], result["total_supply"]],
    })
    return px.bar(
        data,
        x="Category",
        y="kW",
        title="Energy Demand vs Supply",
        color="Category",
        color_discrete_map={
            "Demand (Load)": "#34495E",
            "Total Supply Used": COLOUR_SOLAR,
        },
    )


def show_gauges(result):
    st.subheader("Performance Indicators")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.plotly_chart(
            draw_gauge("Renewable Utilisation", result["renewable_pct"], COLOUR_RENEWABLE),
            use_container_width=True,
        )
    with c2:
        st.plotly_chart(
            draw_gauge("Grid Dependency", result["grid_pct"], COLOUR_GRID),
            use_container_width=True,
        )
    with c3:
        st.plotly_chart(
            draw_gauge("Battery Health", result["battery_health"], COLOUR_BATTERY),
            use_container_width=True,
        )
    with c4:
        st.plotly_chart(
            draw_gauge("System Efficiency", result["system_efficiency"], COLOUR_SOLAR),
            use_container_width=True,
        )


def show_why(result):
    st.subheader("Why this decision was selected")
    for line in result["explanation"]:
        st.markdown(f"- {line}")


def show_flow(source_name):
    st.subheader("Decision Flow")
    try:
        st.graphviz_chart(get_decision_flow_dot(source_name))
    except Exception:
        st.code(
            f"Inputs -> Decision Engine -> Selected Source ({source_name}) "
            f"-> Energy Allocation -> Results"
        )


def show_numbers(result):
    r1, r2, r3, r4, r5 = st.columns(5)
    r1.metric("Solar Used (kW)", result["solar_used"])
    r2.metric("Wind Used (kW)", result["wind_used"])
    r3.metric("Battery Used (kW)", result["battery_used"])
    r4.metric("Grid Used (kW)", result["grid_used"])
    r5.metric("Battery Remaining (%)", result["battery_remaining"])

    r6, r7, r8, r9 = st.columns(4)
    r6.metric("Renewable %", f"{result['renewable_pct']}%")
    r7.metric("Grid %", f"{result['grid_pct']}%")
    r8.metric("Est. CO₂ Saving (kg)", result["co2_saving"])
    r9.metric("Est. Cost Saving (£)", result["cost_saving"])


def show_charts(result, batt_before):
    st.subheader("Charts")
    left, right = st.columns(2)
    with left:
        st.plotly_chart(pie_chart(result), use_container_width=True)
    with right:
        st.plotly_chart(
            battery_bars(batt_before, result["battery_remaining"]),
            use_container_width=True,
        )
    left2, right2 = st.columns(2)
    with left2:
        st.plotly_chart(renew_vs_grid_chart(result), use_container_width=True)
    with right2:
        st.plotly_chart(demand_supply_chart(result), use_container_width=True)


def pdf_button(result, key_name="report"):
    inputs = {
        "Solar (kW)": result["solar_input"],
        "Wind (kW)": result["wind_input"],
        "Load (kW)": result["load_input"],
        "Battery (%)": result["battery_input"],
        "Weather": result["weather"],
        "Time": result["time"],
    }
    pdf_data = generate_simulation_report(result, inputs)
    st.download_button(
        label="Download Simulation Report",
        data=pdf_data,
        file_name="hybridsmart_report.pdf",
        mime="application/pdf",
        key=f"{key_name}_pdf",
    )


# ----- top of page -----
st.title("HybridSmart")
st.caption("Hybrid Energy System for Sustainable Smart Homes")
st.write(
    "This prototype shows how a smart home can choose between solar, wind, "
    "battery and grid using simple rules."
)

page = st.sidebar.radio(
    "Go to",
    [
        "Dashboard",
        "Scenario Comparison",
        "Decision Log",
        "Sample Scenarios",
        "Results Summary",
        "Testing",
        "Technical Information",
        "About Project",
    ],
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Colour key**")
st.sidebar.markdown("Green = renewable | Orange = battery | Red = grid")
st.sidebar.info("Uses if/else rules only. No ML.")


# =========================
# Dashboard
# =========================
if page == "Dashboard":
    st.header("Dashboard")
    st.write("Move the sliders and press Run to see what source gets selected.")

    left, right = st.columns(2)
    with left:
        solar = st.slider("Solar Power (kW)", 0.0, 50.0, 25.0, 0.1)
        wind = st.slider("Wind Power (kW)", 0.0, 40.0, 20.0, 0.1)
        load = st.slider("House Load (kW)", 5.0, 80.0, 55.0, 0.1)
    with right:
        battery = st.slider("Battery Level (%)", 0, 100, 70, 1)
        time_of_day = st.selectbox(
            "Time of Day", ["Morning", "Afternoon", "Evening", "Night"]
        )
        weather = st.selectbox("Weather", ["Sunny", "Cloudy", "Rainy"])

    if st.button("Run Simulation", type="primary"):
        out = run_simulation(solar, wind, load, battery, weather, time_of_day)
        save_to_log(out)
        st.session_state.last_result = out
        st.session_state.last_batt_before = battery

    if "last_result" in st.session_state:
        out = st.session_state.last_result
        batt_before = st.session_state.get("last_batt_before", out["battery_input"])

        st.success(f"Selected Energy Source: **{out['selected_source']}**")
        show_numbers(out)

        if out["battery_charged"] > 0:
            st.info(
                f"Extra renewable energy is going into the battery "
                f"(about {out['battery_charged']} kW)."
            )

        show_why(out)
        st.markdown("---")
        show_flow(out["selected_source"])
        st.markdown("---")
        show_gauges(out)
        st.markdown("---")
        show_charts(out, batt_before)
        st.markdown("---")
        st.subheader("Export Report")
        pdf_button(out, key_name="dashboard")

        with st.expander("Raw output (for checking)"):
            st.json(out)
    else:
        st.write("Set the values above and click **Run Simulation**.")


# =========================
# Scenario Comparison
# =========================
elif page == "Scenario Comparison":
    st.header("Scenario Comparison")
    st.write("Put two different situations side by side and see which one is better.")

    left, right = st.columns(2)

    with left:
        st.subheader("Scenario A")
        a_solar = st.slider("A - Solar (kW)", 0.0, 50.0, 40.0, 0.1, key="a_solar")
        a_wind = st.slider("A - Wind (kW)", 0.0, 40.0, 15.0, 0.1, key="a_wind")
        a_load = st.slider("A - Load (kW)", 5.0, 80.0, 45.0, 0.1, key="a_load")
        a_batt = st.slider("A - Battery (%)", 0, 100, 80, 1, key="a_batt")
        a_time = st.selectbox(
            "A - Time", ["Morning", "Afternoon", "Evening", "Night"], key="a_time"
        )
        a_weather = st.selectbox(
            "A - Weather", ["Sunny", "Cloudy", "Rainy"], key="a_weather"
        )

    with right:
        st.subheader("Scenario B")
        b_solar = st.slider("B - Solar (kW)", 0.0, 50.0, 8.0, 0.1, key="b_solar")
        b_wind = st.slider("B - Wind (kW)", 0.0, 40.0, 18.0, 0.1, key="b_wind")
        b_load = st.slider("B - Load (kW)", 5.0, 80.0, 70.0, 0.1, key="b_load")
        b_batt = st.slider("B - Battery (%)", 0, 100, 25, 1, key="b_batt")
        b_time = st.selectbox(
            "B - Time",
            ["Morning", "Afternoon", "Evening", "Night"],
            index=3,
            key="b_time",
        )
        b_weather = st.selectbox(
            "B - Weather", ["Sunny", "Cloudy", "Rainy"], index=2, key="b_weather"
        )

    if st.button("Compare Scenarios", type="primary"):
        out_a = run_simulation(a_solar, a_wind, a_load, a_batt, a_weather, a_time)
        out_b = run_simulation(b_solar, b_wind, b_load, b_batt, b_weather, b_time)
        save_to_log(out_a)
        save_to_log(out_b)

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Scenario A result")
            st.write(f"**Decision:** {out_a['selected_source']}")
            st.metric("Renewable %", f"{out_a['renewable_pct']}%")
            st.metric("Grid %", f"{out_a['grid_pct']}%")
            st.metric("Battery Used (kW)", out_a["battery_used"])
            st.metric("Cost Saving (£)", out_a["cost_saving"])
            st.metric("CO₂ Saving (kg)", out_a["co2_saving"])
        with c2:
            st.subheader("Scenario B result")
            st.write(f"**Decision:** {out_b['selected_source']}")
            st.metric("Renewable %", f"{out_b['renewable_pct']}%")
            st.metric("Grid %", f"{out_b['grid_pct']}%")
            st.metric("Battery Used (kW)", out_b["battery_used"])
            st.metric("Cost Saving (£)", out_b["cost_saving"])
            st.metric("CO₂ Saving (kg)", out_b["co2_saving"])

        table, notes = compare_scenarios(out_a, out_b)
        st.subheader("Comparison Table")
        st.dataframe(with_one_based_index(table), use_container_width=True)

        st.subheader("Which one is better?")
        if notes:
            for n in notes:
                st.markdown(f"- {n}")
        else:
            st.write("Both came out roughly the same on these metrics.")


# =========================
# Decision Log
# =========================
elif page == "Decision Log":
    st.header("Decision Log")
    st.write(
        "All simulations from this session show up here. "
        "You can download them as CSV if needed."
    )

    if st.button("Clear Log"):
        st.session_state.decision_log = []

    if len(st.session_state.decision_log) == 0:
        st.warning("Nothing in the log yet. Run something on the Dashboard first.")
    else:
        log_df = pd.DataFrame(st.session_state.decision_log)
        st.dataframe(with_one_based_index(log_df), use_container_width=True)
        csv_bytes = log_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Decision Log (CSV)",
            data=csv_bytes,
            file_name="hybridsmart_decision_log.csv",
            mime="text/csv",
        )


# =========================
# Sample Scenarios
# =========================
elif page == "Sample Scenarios":
    st.header("Sample Scenarios")
    st.write(
        "This page uses the **HESS dataset** (`data/HESS_Dataset.csv`) – "
        "about 1000 hourly rows. Columns are mapped to solar, wind, load, "
        "battery, weather and time for the decision engine."
    )

    df = load_sample_data()

    show_cols = [
        "Timestamp", "solar", "wind", "load", "battery", "weather", "time",
        "grid_from_dataset", "power_supplied", "power_loss",
    ]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(with_one_based_index(df[show_cols]), use_container_width=True)
    st.caption(f"Total rows loaded: {len(df)}")

    scen_no = st.number_input(
        f"Scenario number (1 to {len(df)})",
        min_value=1,
        max_value=len(df),
        value=1,
        step=1,
    )

    if st.button("Simulate Selected Scenario", key="sample_sim"):
        row = df.iloc[int(scen_no) - 1]
        out = run_simulation(
            row["solar"], row["wind"], row["load"],
            row["battery"], row["weather"], row["time"],
        )
        save_to_log(out)

        st.write(
            f"**Inputs:** Solar={row['solar']} kW, Wind={row['wind']} kW, "
            f"Load={row['load']} kW, Battery={row['battery']}%, "
            f"Weather={row['weather']}, Time={row['time']}"
        )
        if "Timestamp" in row:
            st.write(f"**Timestamp:** {row['Timestamp']}")
        st.success(f"Selected Energy Source: **{out['selected_source']}**")
        show_numbers(out)
        show_why(out)
        show_gauges(out)


# =========================
# Results Summary
# =========================
elif page == "Results Summary":
    st.header("Results Summary")
    st.write(
        "Average values after running the decision engine on the HESS dataset. "
        "You can choose how many rows to analyse (1000 rows can take a few seconds)."
    )

    df_all = load_sample_data()
    max_n = len(df_all)
    n_rows = st.slider("Rows to analyse", 50, max_n, min(200, max_n), 50)

    results_df = simulate_all_scenarios(df_all, max_rows=n_rows)
    summary = calculate_summary(results_df)

    a1, a2, a3 = st.columns(3)
    a1.metric("Average Renewable Usage", f"{summary['avg_renewable_usage']}%")
    a2.metric("Average Grid Usage", f"{summary['avg_grid_usage']}%")
    a3.metric("Average Battery Used (kW)", summary["avg_battery_used"])

    a4, a5, a6 = st.columns(3)
    a4.metric("Total Est. Cost Saving (£)", summary["total_cost_saving"])
    a5.metric("Total Est. CO₂ Reduction (kg)", summary["total_co2_saving"])
    a6.metric("Scenarios Analysed", summary["num_scenarios"])

    st.markdown("---")
    st.subheader("Per-scenario results")
    st.dataframe(with_one_based_index(results_df), use_container_width=True)

    st.subheader("Overview Charts")
    oc1, oc2 = st.columns(2)
    with oc1:
        fig1 = px.bar(
            x=["Renewable %", "Grid %"],
            y=[summary["avg_renewable_usage"], summary["avg_grid_usage"]],
            title="Average Renewable vs Grid Usage",
            labels={"x": "Type", "y": "Percent"},
            color=["Renewable %", "Grid %"],
            color_discrete_map={
                "Renewable %": COLOUR_RENEWABLE,
                "Grid %": COLOUR_GRID,
            },
        )
        st.plotly_chart(fig1, use_container_width=True)
    with oc2:
        fig2 = px.bar(
            results_df,
            x="scenario",
            y="co2_saving",
            title="CO₂ Saving per Scenario (kg)",
            labels={"scenario": "Scenario", "co2_saving": "CO₂ (kg)"},
            color_discrete_sequence=[COLOUR_RENEWABLE],
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.caption(
        "Cost and CO₂ values are rough estimates only "
        "(£0.28/kWh and 0.4 kg CO₂/kWh)."
    )


# =========================
# Testing
# =========================
elif page == "Testing":
    st.header("Testing")
    st.write(
        "These are 10 fixed test cases. "
        "Each one has a rough expected result and the actual output from the code."
    )

    names = [t["name"] for t in TEST_SCENARIOS]
    picked = st.selectbox("Select a test", names)
    test = next(t for t in TEST_SCENARIOS if t["name"] == picked)

    st.subheader("Test inputs")
    t1, t2, t3 = st.columns(3)
    t1.write(f"**Solar:** {test['solar']} kW")
    t1.write(f"**Wind:** {test['wind']} kW")
    t2.write(f"**Load:** {test['load']} kW")
    t2.write(f"**Battery:** {test['battery']}%")
    t3.write(f"**Weather:** {test['weather']}")
    t3.write(f"**Time:** {test['time']}")

    st.info(f"**Expected:** {test['expected_decision']} — {test['expected_notes']}")

    if st.button("Run Test", type="primary"):
        actual = run_test_scenario(test)
        save_to_log(actual)

        st.subheader("Actual output")
        st.success(f"Decision: **{actual['selected_source']}**")
        show_numbers(actual)
        show_why(actual)

        st.subheader("Expected vs Actual")
        check_df = pd.DataFrame([
            {
                "Field": "Decision",
                "Expected": test["expected_decision"],
                "Actual": actual["selected_source"],
            },
            {
                "Field": "Renewable %",
                "Expected": "High if sunny / low load",
                "Actual": actual["renewable_pct"],
            },
            {
                "Field": "Grid Used (kW)",
                "Expected": "0 if renewables cover load",
                "Actual": actual["grid_used"],
            },
        ])
        st.dataframe(with_one_based_index(check_df), use_container_width=True)

    st.markdown("---")
    st.subheader("Run all tests")
    if st.button("Run All 10 Tests"):
        all_rows = []
        for case in TEST_SCENARIOS:
            actual = run_test_scenario(case)
            save_to_log(actual)
            all_rows.append({
                "Test": case["name"],
                "Expected": case["expected_decision"],
                "Actual Decision": actual["selected_source"],
                "Renewable %": actual["renewable_pct"],
                "Grid Used": actual["grid_used"],
                "Cost Saving (£)": actual["cost_saving"],
                "CO₂ Saving (kg)": actual["co2_saving"],
            })
        st.dataframe(with_one_based_index(pd.DataFrame(all_rows)), use_container_width=True)
        st.success("Finished all 10 tests.")


# =========================
# Technical Information
# =========================
elif page == "Technical Information":
    st.header("Technical Information")

    st.subheader("System Architecture")
    st.markdown(
        """
        The project is split into a few simple parts:

        1. **Streamlit UI** – where the user enters values  
        2. **Decision engine** – Python file with the if/else rules  
        3. **CSV file** – sample scenarios  
        4. **Plotly charts** – for graphs and gauges  
        5. **PDF/CSV export** – for saving results  
        """
    )

    try:
        st.graphviz_chart(
            """
            digraph Architecture {
                rankdir=LR;
                node [shape=box, style="rounded,filled"];
                UI [label="Streamlit UI", fillcolor="#D5F5E3"];
                DE [label="Decision Engine", fillcolor="#FCF3CF"];
                CSV [label="CSV Dataset", fillcolor="#D6EAF8"];
                CH [label="Plotly Charts", fillcolor="#FAD7A0"];
                RP [label="PDF / CSV Export", fillcolor="#E8DAEF"];
                UI -> DE;
                CSV -> UI;
                DE -> CH;
                DE -> RP;
            }
            """
        )
    except Exception:
        st.code("Streamlit UI -> Decision Engine -> Charts / PDF\nCSV -> Streamlit UI")

    st.subheader("Project Structure")
    st.code(
        """
HybridSmart/
├── app.py
├── decision_engine.py
├── utils.py
├── report_generator.py
├── data/
│   └── HESS_Dataset.csv
├── requirements.txt
└── README.md
        """
    )

    st.subheader("Decision Logic")
    st.markdown(
        """
        The rules are straightforward:

        1. Change solar/wind a bit based on weather and time  
        2. Use solar first  
        3. Add wind if solar is short  
        4. Use battery if still short and battery > 30%  
        5. Use grid for whatever is left  
        6. Charge the battery if there is spare renewable power  
        """
    )

    st.subheader("Technologies Used")
    tech = pd.DataFrame({
        "Technology": ["Python", "Streamlit", "Pandas", "Plotly", "CSV Dataset", "fpdf2"],
        "Used for": [
            "Main language",
            "Local dashboard",
            "Reading / analysing CSV",
            "Charts and gauges",
            "Sample data (no database)",
            "PDF reports",
        ],
    })
    st.table(with_one_based_index(tech))


# =========================
# About Project
# =========================
elif page == "About Project":
    st.header("About Project")

    st.subheader("Project Objective")
    st.write(
        "The aim of this prototype is to show how a smart home can pick "
        "between solar, wind, battery and grid using simple rules. "
        "It also gives a rough idea of cost and CO₂ savings."
    )

    st.subheader("System Workflow")
    st.markdown(
        """
        1. User enters solar, wind, load, battery, weather and time  
        2. Rules adjust renewables for the conditions  
        3. Energy is split across the sources  
        4. Screen shows numbers, explanation and charts  
        5. Optional: download PDF or CSV  
        """
    )

    try:
        st.graphviz_chart(get_decision_flow_dot("Selected Source"))
    except Exception:
        st.write("Inputs -> Decision Engine -> Selected Source -> Allocation -> Results")

    st.subheader("Limitations")
    st.markdown(
        """
        - Values are simplified (not a full hourly model)  
        - Battery is treated as a fixed 10 kWh pack with basic rules  
        - Cost and CO₂ numbers are only estimates  
        - Weather/time effects use fixed multipliers  
        - This is a local demo, not a live control system  
        """
    )

    st.subheader("Future Scope")
    st.markdown(
        """
        - Try a full day or week simulation  
        - Improve the battery model  
        - Compare different house sizes / tariffs  
        - Add clearer pass/fail checks in testing  
        - Put more detail into the PDF report  
        """
    )
