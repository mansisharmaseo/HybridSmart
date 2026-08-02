"""
report_generator.py
-------------------
Makes a basic PDF report after a simulation.
"""

from datetime import datetime
from fpdf import FPDF


class SimpleReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 8, "HybridSmart - Simulation Report", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, "Hybrid energy prototype", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def clean_text(text):
    # fpdf basic fonts struggle with some characters
    if text is None:
        return ""
    text = str(text)
    text = text.replace("£", "GBP ")
    text = text.replace("₂", "2")
    text = text.replace("CO₂", "CO2")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("→", "->")
    text = text.replace("↓", "->")
    return text.encode("latin-1", "replace").decode("latin-1")


def write_heading(pdf, title):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 8, clean_text(title))
    pdf.set_font("Helvetica", "", 10)


def write_line(pdf, label, value):
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 6, clean_text(f"{label}: {value}"))


def generate_simulation_report(result, inputs=None):
    if inputs is None:
        inputs = {
            "Solar (kW)": result.get("solar_input"),
            "Wind (kW)": result.get("wind_input"),
            "Load (kW)": result.get("load_input"),
            "Battery (%)": result.get("battery_input"),
            "Weather": result.get("weather"),
            "Time": result.get("time"),
        }

    pdf = SimpleReport()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)

    write_line(pdf, "Generated", datetime.now().strftime("%Y-%m-%d %H:%M"))
    pdf.ln(2)

    write_heading(pdf, "1. Inputs")
    for k, v in inputs.items():
        write_line(pdf, k, v)
    pdf.ln(2)

    write_heading(pdf, "2. Decision")
    write_line(pdf, "Selected Source", result["selected_source"])
    write_line(pdf, "Solar Used (kW)", result["solar_used"])
    write_line(pdf, "Wind Used (kW)", result["wind_used"])
    write_line(pdf, "Battery Used (kW)", result["battery_used"])
    write_line(pdf, "Grid Used (kW)", result["grid_used"])
    write_line(pdf, "Battery Remaining (%)", result["battery_remaining"])
    pdf.ln(2)

    write_heading(pdf, "3. Performance")
    write_line(pdf, "Renewable %", result["renewable_pct"])
    write_line(pdf, "Grid %", result["grid_pct"])
    write_line(pdf, "Battery Health (%)", result["battery_health"])
    write_line(pdf, "System Efficiency (%)", result["system_efficiency"])
    write_line(pdf, "CO2 Saving (kg)", result["co2_saving"])
    write_line(pdf, "Cost Saving (GBP)", result["cost_saving"])
    pdf.ln(2)

    write_heading(pdf, "4. Why this decision was selected")
    for line in result.get("explanation", []):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 6, clean_text(f"- {line}"))
    pdf.ln(2)

    write_heading(pdf, "5. Energy split")
    total = result["total_supply"] if result["total_supply"] else 1
    write_line(pdf, "Solar share", f"{round(result['solar_used'] / total * 100, 1)}%")
    write_line(pdf, "Wind share", f"{round(result['wind_used'] / total * 100, 1)}%")
    write_line(pdf, "Battery share", f"{round(result['battery_used'] / total * 100, 1)}%")
    write_line(pdf, "Grid share", f"{round(result['grid_used'] / total * 100, 1)}%")
    pdf.ln(2)

    write_heading(pdf, "6. Short conclusion")
    if result["grid_pct"] == 0:
        end_note = (
            "In this run the house load was covered without using the grid. "
            "Renewables did most of the work."
        )
    elif result["renewable_pct"] >= 50:
        end_note = (
            "Renewables covered a good part of the demand. "
            "Some grid support was still needed."
        )
    else:
        end_note = (
            "Grid use was high in this case. "
            "That usually happens at night, in bad weather, or when the load is high."
        )

    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 6, clean_text(end_note))
    pdf.ln(4)

    pdf.set_font("Helvetica", "I", 9)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(
        0,
        5,
        clean_text(
            "Note: cost and CO2 numbers are rough estimates only "
            "(GBP 0.28/kWh and 0.4 kg CO2/kWh)."
        ),
    )

    out = pdf.output()
    if isinstance(out, bytearray):
        out = bytes(out)
    return out
