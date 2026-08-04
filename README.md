# HybridSmart

**Hybrid Energy System for Sustainable Smart Homes**

Simple prototype that shows how a smart home can choose between solar, wind, battery and grid.

---

## Project Overview

HybridSmart is a small local app built for a dissertation-style demo.

It decides which source to use based on:

- how much solar / wind is available
- house load
- battery level
- weather
- time of day

The logic is plain **if/else**. No machine learning.

---

## Features

- Dashboard with sliders
- Short explanation after each run ("Why this decision was selected")
- Decision flow diagram
- Compare two scenarios
- Decision log + CSV download
- Gauges for renewable / grid / battery / efficiency
- 10 fixed test cases
- PDF report download
- Technical Information page
- About Project page
- Sample CSV with ~30 rows

---

## Installation

```bash
cd HybridSmart
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

If the flow diagram does not show, install Graphviz on your system too  
(`brew install graphviz` on Mac). The app still works without it.

---

## Folder Structure

```
HybridSmart/
├── app.py
├── decision_engine.py
├── utils.py
├── report_generator.py
├── data/
│   └── HESS_Dataset.csv
├── requirements.txt
└── README.md
```

---

## Dataset

The app uses `data/HESS_Dataset.csv` (about 1000 hourly rows).

Original columns include:

- `Timestamp`
- `Solar_Power_kW`
- `Wind_Power_kW`
- `Load_Demand_kW`
- `Battery_SoC_%`
- `Grid_Power_kW`
- and related power fields

These are mapped for the decision engine / UI as:

- Solar (kW) / Wind (kW) / Load (kW) / Battery (%)
- Time of Day (from timestamp hour)
- Weather (estimated from solar level, because the CSV has no weather column)

Tables in the app show clean labels (no underscores), for example:
`Solar Used (kW)`, `Selected Source`, `Grid in Dataset (kW)`.

---

## Decision Logic

1. Adjust solar/wind using weather and time
2. Use solar first
3. Add wind if needed
4. Use battery if still short and battery > 30%
5. Use grid for leftover demand
6. Charge battery if there is spare renewable power

Rough estimate factors used in the demo:

- Grid cost ≈ £0.28 / kWh
- Grid CO₂ ≈ 0.4 kg / kWh

---

## Pages

| Page | What it does |
|------|----------------|
| Dashboard | Run a simulation |
| Scenario Comparison | Compare A vs B |
| Decision Log | See past runs + CSV |
| Sample Scenarios | Run rows from the CSV |
| Results Summary | Averages over all samples |
| Testing | 10 preset tests |
| Technical Information | Architecture / tech list |
| About Project | Objective, limits, future work |

---

## Colour Key

- Green = renewable
- Orange = battery
- Red = grid

---

## Screenshots

Add screenshots here later:

- [ ] Dashboard
- [ ] Explanation panel
- [ ] Comparison page
- [ ] Testing page
- [ ] PDF report

---

## Future Improvements

- Hourly / daily simulation
- Better battery model
- Different household profiles
- Stronger test checks
- More detail in the PDF

---

## Note

Cost and CO₂ figures are estimates for demonstration only.

## License

All rights reserved.

- Commercial use is **not allowed**
- Use without written permission is **not allowed**

See the `LICENSE` file for full terms.
Contact: mansisharmaseo@gmail.com
