def calculate_risks(month_data, profile):
    if not month_data:
        return None

    n = len(month_data)

    avg_sleep = sum(d["sleep_hours"] for d in month_data) / n
    avg_stress = sum(d["stress_level"] for d in month_data) / n
    avg_screen = sum(d["screen_time"] for d in month_data) / n
    avg_water = sum(d["water_intake"] for d in month_data) / n
    avg_steps = sum(d["steps_count"] for d in month_data) / n
    avg_energy = sum(d["energy_level"] for d in month_data) / n

    headache_days = sum(1 for d in month_data if d["headache"] == "Yes")
    eye_strain_days = sum(1 for d in month_data if d["eye_strain"] == "Yes")

    headache_ratio = headache_days / n
    eye_ratio = eye_strain_days / n

    # -----------------------------
    # SAFE DEFICIT CALCULATIONS ✅
    # -----------------------------
    sleep_deficit = max(0, (7 - avg_sleep) / 7)
    water_deficit = max(0, (3 - avg_water) / 3)
    step_deficit = max(0, (6000 - avg_steps) / 6000)
    energy_deficit = max(0, (10 - avg_energy) / 10)

    # PROFILE FACTORS
    age_factor = 1.0
    lifestyle_factor = 1.0

    FAMILY_RISK_MULTIPLIERS = {
        "diabetes":      {"overall": 0.20, "sedentary": 0.15, "dehydration": 0.10},
        "heart_disease": {"overall": 0.25, "burnout": 0.15, "sedentary": 0.20},
        "hypertension":  {"overall": 0.20, "burnout": 0.20, "migraine": 0.15},
        "cancer":        {"overall": 0.15},
        "depression":    {"burnout": 0.25, "sleep_disorder": 0.20, "overall": 0.15},
        "migraine":      {"migraine": 0.30, "overall": 0.10},
        "obesity":       {"overall": 0.15, "sedentary": 0.20, "dehydration": 0.10},
        "stroke":        {"overall": 0.20, "burnout": 0.10, "sedentary": 0.15},
    }

    active_conditions = set()
    family_notes = []

    if profile:
        age = profile.get("age", 25)
        smoking = profile.get("smoking", "No")
        alcohol = profile.get("alcohol", "No")

        family_has_history = profile.get("family", "No")
        family_conditions_raw = profile.get("family_conditions")

        if age > 40:
            age_factor = 1.2
        if smoking == "Yes":
            lifestyle_factor += 0.2
        if alcohol == "Regular":
            lifestyle_factor += 0.1

        if family_has_history == "Yes" and family_conditions_raw:
            for cond in family_conditions_raw.split(","):
                cond = cond.strip()
                if cond in FAMILY_RISK_MULTIPLIERS:
                    active_conditions.add(cond)
                    family_notes.append(cond.replace("_", " ").title())

    # -----------------------------
    # RISK CALCULATIONS
    # -----------------------------
    migraine = (
        (avg_screen / 10) * 30 +
        (avg_stress / 10) * 30 +
        headache_ratio * 40
    ) * lifestyle_factor

    burnout = (
        (avg_stress / 10) * 40 +
        energy_deficit * 30 +
        sleep_deficit * 30
    ) * lifestyle_factor

    sleep_disorder = sleep_deficit * 100

    eye_strain = (
        (avg_screen / 10) * 60 +
        eye_ratio * 40
    )

    dehydration = water_deficit * 100

    anxiety = (
        (avg_stress / 10) * 60 +
        sleep_deficit * 40
    ) * lifestyle_factor

    fatigue = (
        energy_deficit * 50 +
        sleep_deficit * 50
    )

    digital_addiction = (
        (avg_screen / 10) * 70 +
        eye_ratio * 30
    )

    cardiovascular = (
        step_deficit * 50 +
        (avg_stress / 10) * 30 +
        water_deficit * 20
    ) * age_factor

    posture = (
        (avg_screen / 10) * 50 +
        step_deficit * 50
    )

    immunity = (
        energy_deficit * 30 +
        sleep_deficit * 40 +
        (avg_stress / 10) * 30
    )

    sedentary = step_deficit * 100

    overall = (
        migraine * 0.15 +
        burnout * 0.2 +
        sleep_disorder * 0.15 +
        sedentary * 0.1 +
        dehydration * 0.1 +
        anxiety * 0.1 +
        fatigue * 0.1 +
        cardiovascular * 0.1
    ) * age_factor

    # -----------------------------
    # RISK MAP
    # -----------------------------
    risk_map = {
        "migraine": migraine,
        "burnout": burnout,
        "sleep_disorder": sleep_disorder,
        "eye_strain": eye_strain,
        "dehydration": dehydration,
        "sedentary": sedentary,
        "anxiety": anxiety,
        "fatigue": fatigue,
        "digital_addiction": digital_addiction,
        "cardiovascular": cardiovascular,
        "posture": posture,
        "immunity": immunity,
        "overall": overall,
    }

    # Apply family history boosts
    for condition in active_conditions:
        multipliers = FAMILY_RISK_MULTIPLIERS[condition]
        for risk_key, boost in multipliers.items():
            if risk_key in risk_map:
                risk_map[risk_key] *= (1 + boost)

    def clamp(x):
        return max(0, min(round(x), 100))

    # -----------------------------
    # FINAL RESULT (CLEAN)
    # -----------------------------
    result = {k: clamp(v) for k, v in risk_map.items()}
    result["days_analyzed"] = n

    # 🔥 Top 3 risks
    top_risks = sorted(
        [(k, result[k]) for k in result if k not in ["overall", "days_analyzed"]],
        key=lambda x: x[1],
        reverse=True
    )[:3]

    result["top_risks"] = [r[0] for r in top_risks]

    if family_notes:
        result["family_history_active"] = family_notes

    return result