"""
decision_engine.py
------------------
This file picks which energy source to use for the house.
Rules are plain if/else. Nothing fancy.
"""


def weather_effect(solar, wind, weather):
    # weather changes how much solar/wind we can actually use
    w = weather.lower()

    if w == "sunny":
        solar = solar * 1.0
        wind = wind * 0.9
    elif w == "cloudy":
        solar = solar * 0.55
        wind = wind * 1.0
    elif w == "rainy":
        solar = solar * 0.25
        wind = wind * 1.15

    return solar, wind


def time_effect(solar, wind, time_of_day):
    # night pe solar almost zero hota hai
    t = time_of_day.lower()

    if t == "morning":
        solar = solar * 0.7
        wind = wind * 0.9
    elif t == "afternoon":
        solar = solar * 1.0
        wind = wind * 0.85
    elif t == "evening":
        solar = solar * 0.35
        wind = wind * 1.0
    elif t == "night":
        solar = solar * 0.05
        wind = wind * 1.1

    return solar, wind


def make_explanation(result, batt_pct):
    """
    Short notes explaining why we picked these sources.
    Written in plain English for the demo.
    """
    notes = []

    s_used = result["solar_used"]
    w_used = result["wind_used"]
    b_used = result["battery_used"]
    g_used = result["grid_used"]
    load = result["load"]
    s_avail = result["solar_available"]
    w_avail = result["wind_available"]

    # solar
    if s_used >= load and load > 0:
        notes.append("Solar was enough to cover the house load.")
    elif s_used > 0:
        notes.append(
            f"Solar gave {s_used} kW, but that alone was not enough "
            f"(after weather/time adjust it was about {s_avail} kW)."
        )
    else:
        notes.append(
            "Solar could not be used much here (weather or time was not good for it)."
        )

    # wind
    if w_used > 0:
        notes.append(f"Wind was added as well ({w_used} kW).")
    elif s_used < load:
        notes.append(
            f"Wind was checked next (around {w_avail} kW available) "
            "but it still did not cover everything."
        )

    # battery
    if b_used > 0:
        notes.append(
            f"Battery was used ({b_used} kW) because solar+wind were short "
            f"and battery was above 30% (currently {batt_pct}%)."
        )
    elif batt_pct <= 30 and (s_used + w_used) < load:
        notes.append(
            f"Battery skipped – level is only {batt_pct}% "
            "(we only use battery if it is above 30%)."
        )
    else:
        notes.append("Battery was not needed.")

    # grid
    if g_used > 0:
        notes.append(f"Grid had to cover the leftover demand ({g_used} kW).")
    else:
        notes.append("Grid usage stayed at 0%.")

    # charging
    if result["battery_charged"] > 0:
        notes.append(
            f"Extra renewable power went into charging the battery "
            f"(+{result['battery_charged']} kW)."
        )

    # overall
    if result["renewable_pct"] >= 70:
        notes.append("Renewables were used first where possible.")
    elif result["grid_pct"] >= 50:
        notes.append(
            "Grid share is quite high here – renewables were limited."
        )
    else:
        notes.append("A mix of sources was used to meet the load.")

    return notes


def get_efficiency_score(result):
    # rough score for the gauges – not a real industry formula
    renew = result["renewable_pct"]
    grid = result["grid_pct"]
    load = result["load"]
    supply = result["total_supply"]

    score = renew * 0.7 + (100 - grid) * 0.2

    # small bonus if load is fully met
    if load > 0 and abs(supply - load) < 0.01:
        score = score + 10

    if score < 0:
        score = 0
    if score > 100:
        score = 100

    return round(score, 1)


def decide_energy_sources(solar_kw, wind_kw, load_kw, battery_percent, weather, time_of_day):
    """
    Main function.
    Takes the inputs and returns how much came from each source.
    """

    # save originals for the log / pdf
    saved_inputs = {
        "solar_in": round(float(solar_kw), 2),
        "wind_in": round(float(wind_kw), 2),
        "load_in": round(float(load_kw), 2),
        "batt_in": round(float(battery_percent), 1),
        "weather": weather,
        "time": time_of_day,
    }

    # step 1 – apply weather and time
    solar_now, wind_now = weather_effect(solar_kw, wind_kw, weather)
    solar_now, wind_now = time_effect(solar_now, wind_now, time_of_day)

    if solar_now < 0:
        solar_now = 0
    if wind_now < 0:
        wind_now = 0
    if load_kw < 0:
        load_kw = 0

    batt_pct = battery_percent
    if batt_pct < 0:
        batt_pct = 0
    if batt_pct > 100:
        batt_pct = 100

    # assuming battery size = 100 kWh for this HESS-scale prototype
    batt_size = 100.0
    batt_can_give = (batt_pct / 100.0) * batt_size

    solar_used = 0.0
    wind_used = 0.0
    batt_used = 0.0
    grid_used = 0.0
    batt_charged = 0.0

    left = load_kw
    used_list = []

    # rule 1 – try solar first
    if solar_now > 0 and left > 0:
        solar_used = min(solar_now, left)
        left = left - solar_used
        used_list.append("Solar")

    # rule 2 – add wind if still short
    if wind_now > 0 and left > 0:
        wind_used = min(wind_now, left)
        left = left - wind_used
        used_list.append("Wind")

    # rule 3 – battery only if above 30%
    if left > 0 and batt_pct > 30:
        take = min(batt_can_give * 0.5, left)
        # try not to go below ~20%
        max_drain_pct = batt_pct - 20
        max_drain_kw = (max_drain_pct / 100.0) * batt_size
        if max_drain_kw < 0:
            max_drain_kw = 0
        batt_used = min(take, max_drain_kw)
        left = left - batt_used
        if batt_used > 0:
            used_list.append("Battery")

    # rule 4 – whatever is left comes from grid
    if left > 0:
        grid_used = left
        left = 0
        used_list.append("Grid")

    # rule 5 – charge battery if we have leftover renewable
    spare_solar = solar_now - solar_used
    spare_wind = wind_now - wind_used
    spare = spare_solar + spare_wind

    if spare > 0 and batt_pct < 95:
        room = ((100 - batt_pct) / 100.0) * batt_size
        batt_charged = min(spare, room)

    # update battery %
    change = ((batt_charged - batt_used) / batt_size) * 100
    batt_left = batt_pct + change
    if batt_left < 0:
        batt_left = 0
    if batt_left > 100:
        batt_left = 100

    if len(used_list) == 0:
        source_name = "None"
    else:
        source_name = " + ".join(used_list)

    total = solar_used + wind_used + batt_used + grid_used
    if total > 0:
        renew_pct = ((solar_used + wind_used) / total) * 100
        grid_pct = (grid_used / total) * 100
    else:
        renew_pct = 0.0
        grid_pct = 0.0

    # rough estimates (for demo only)
    co2_save = (solar_used + wind_used + batt_used) * 0.4
    cost_save = (solar_used + wind_used + batt_used) * 0.28

    result = {
        "selected_source": source_name,
        "solar_used": round(solar_used, 2),
        "wind_used": round(wind_used, 2),
        "battery_used": round(batt_used, 2),
        "grid_used": round(grid_used, 2),
        "battery_charged": round(batt_charged, 2),
        "battery_remaining": round(batt_left, 1),
        "battery_health": round(batt_left, 1),
        "renewable_pct": round(renew_pct, 1),
        "grid_pct": round(grid_pct, 1),
        # keep old names too so older UI bits don't break if any left
        "renewable_utilisation": round(renew_pct, 1),
        "grid_dependency": round(grid_pct, 1),
        "co2_saving": round(co2_save, 2),
        "cost_saving": round(cost_save, 2),
        "solar_available": round(solar_now, 2),
        "wind_available": round(wind_now, 2),
        "load": round(load_kw, 2),
        "total_supply": round(total, 2),
        # input aliases used by log/pdf
        "solar_input": saved_inputs["solar_in"],
        "wind_input": saved_inputs["wind_in"],
        "load_input": saved_inputs["load_in"],
        "battery_input": saved_inputs["batt_in"],
        "solar_in": saved_inputs["solar_in"],
        "wind_in": saved_inputs["wind_in"],
        "load_in": saved_inputs["load_in"],
        "batt_in": saved_inputs["batt_in"],
        "weather": weather,
        "time": time_of_day,
    }

    result["system_efficiency"] = get_efficiency_score(result)
    result["explanation"] = make_explanation(result, batt_pct)

    return result
