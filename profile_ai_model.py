import sqlite3


PROFILE_RISK_KEYS = [
    "migraine",
    "burnout",
    "sleep_disorder",
    "eye_strain",
    "dehydration",
    "sedentary",
    "anxiety",
    "fatigue",
    "digital_addiction",
    "cardiovascular",
    "posture",
    "immunity",
]

BASE_PROFILE_RISKS = {
    "migraine": 40,
    "burnout": 45,
    "sleep_disorder": 35,
    "eye_strain": 30,
    "dehydration": 35,
    "sedentary": 40,
    "anxiety": 45,
    "fatigue": 40,
    "digital_addiction": 35,
    "cardiovascular": 40,
    "posture": 35,
    "immunity": 45,
}

FAMILY_RISK_MULTIPLIERS = {
    "diabetes": {"overall": 0.20, "sedentary": 0.15, "dehydration": 0.10},
    "heart_disease": {"overall": 0.25, "burnout": 0.15, "sedentary": 0.20},
    "hypertension": {"overall": 0.20, "burnout": 0.20, "migraine": 0.15},
    "cancer": {"overall": 0.15},
    "depression": {"burnout": 0.25, "sleep_disorder": 0.20, "overall": 0.15},
    "migraine": {"migraine": 0.30, "overall": 0.10},
    "obesity": {"overall": 0.15, "sedentary": 0.20, "dehydration": 0.10},
    "stroke": {"overall": 0.20, "burnout": 0.10, "sedentary": 0.15},
}


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _clamp(value):
    return max(0, min(100, int(round(value))))


def _as_profile(profile_or_age, smoking=None, gender=None):
    if isinstance(profile_or_age, dict):
        return dict(profile_or_age)

    return {
        "age": profile_or_age,
        "smoking": smoking,
        "gender": gender,
    }


def _build_default_risk_map():
    return dict(BASE_PROFILE_RISKS)


def _load_similar_user_risks(cursor, profile):
    age = _to_int(profile.get("age"), 25)
    gender = str(profile.get("gender") or "Male")
    smoking = str(profile.get("smoking") or "No")

    cursor.execute(
        """
        SELECT DISTINCT up.user_id
        FROM user_profile up
        WHERE up.age BETWEEN ? AND ?
          AND up.gender = ?
          AND up.smoking = ?
          AND EXISTS (
              SELECT 1
              FROM daily_data dd
              WHERE dd.user_id = up.user_id
          )
        """,
        (age - 3, age + 3, gender, smoking),
    )
    user_ids = [row[0] for row in cursor.fetchall()]

    if not user_ids:
        return None

    query = f"""
        SELECT
            AVG(stress_level),
            AVG(sleep_hours),
            AVG(screen_time),
            AVG(water_intake),
            AVG(steps_count),
            AVG(CASE WHEN headache = 'Yes' THEN 1 ELSE 0 END),
            AVG(CASE WHEN eye_strain = 'Yes' THEN 1 ELSE 0 END),
            AVG(energy_level)
        FROM daily_data
        WHERE user_id IN ({",".join(["?"] * len(user_ids))})
    """

    cursor.execute(query, user_ids)
    result = cursor.fetchone()

    if not result or not any(value is not None for value in result):
        return None

    avg_stress, avg_sleep, avg_screen, avg_water, avg_steps, headache_freq, eye_freq, avg_energy = result

    avg_stress = avg_stress or 5
    avg_sleep = avg_sleep or 6
    avg_screen = avg_screen or 5
    avg_water = avg_water or 1.5
    avg_steps = avg_steps or 5000
    headache_freq = headache_freq or 0
    eye_freq = eye_freq or 0
    avg_energy = avg_energy or 5

    sleep_deficit = max(0, (7 - avg_sleep) / 7)
    water_deficit = max(0, (3 - avg_water) / 3)
    step_deficit = max(0, (6000 - avg_steps) / 6000)
    energy_deficit = max(0, (10 - avg_energy) / 10)

    return {
        "migraine": headache_freq * 100 + avg_stress * 4,
        "burnout": avg_stress * 8 + avg_screen * 3,
        "sleep_disorder": sleep_deficit * 100,
        "eye_strain": avg_screen * 10 + eye_freq * 50,
        "dehydration": water_deficit * 100,
        "sedentary": step_deficit * 100,
        "anxiety": avg_stress * 6 + sleep_deficit * 40,
        "fatigue": energy_deficit * 50 + sleep_deficit * 50,
        "digital_addiction": avg_screen * 10 + eye_freq * 40,
        "cardiovascular": step_deficit * 50 + avg_stress * 3 + water_deficit * 20,
        "posture": avg_screen * 5 + step_deficit * 50,
        "immunity": energy_deficit * 30 + sleep_deficit * 40 + avg_stress * 3,
    }


def _apply_profile_adjustments(risk_map, profile):
    age = _to_int(profile.get("age"), 25)
    smoking = str(profile.get("smoking") or "No").strip().lower()
    alcohol = str(profile.get("alcohol") or "None").strip().lower()
    height_cm = _to_float(profile.get("height"))
    weight_kg = _to_float(profile.get("weight"))

    age_delta = max(0, age - 25)
    if age_delta:
        risk_map["cardiovascular"] += min(15, age_delta * 0.5)
        risk_map["fatigue"] += min(8, age_delta * 0.2)
        risk_map["burnout"] += min(6, age_delta * 0.15)
        risk_map["immunity"] += min(5, age_delta * 0.1)

    if smoking == "yes":
        risk_map["cardiovascular"] += 16
        risk_map["immunity"] += 10
        risk_map["fatigue"] += 6
        risk_map["burnout"] += 4

    if alcohol == "occasional":
        risk_map["dehydration"] += 4
        risk_map["sleep_disorder"] += 3
        risk_map["burnout"] += 2
    elif alcohol == "regular":
        risk_map["dehydration"] += 12
        risk_map["sleep_disorder"] += 9
        risk_map["burnout"] += 6
        risk_map["fatigue"] += 4

    if height_cm > 0 and weight_kg > 0:
        bmi = weight_kg / ((height_cm / 100) ** 2)
        bmi_offset = bmi - 22

        if bmi_offset > 0:
            risk_map["cardiovascular"] += min(16, bmi_offset * 1.3)
            risk_map["sedentary"] += min(12, bmi_offset * 0.9)
            risk_map["fatigue"] += min(9, bmi_offset * 0.7)
            risk_map["posture"] += min(7, bmi_offset * 0.5)
        elif bmi < 18.5:
            underweight_gap = 18.5 - bmi
            risk_map["fatigue"] += min(8, underweight_gap * 1.5)
            risk_map["immunity"] += min(6, underweight_gap * 1.2)


def _calculate_overall(risk_map):
    overall = (
        risk_map["migraine"] * 0.15 +
        risk_map["burnout"] * 0.20 +
        risk_map["sleep_disorder"] * 0.15 +
        risk_map["sedentary"] * 0.10 +
        risk_map["dehydration"] * 0.10 +
        risk_map["anxiety"] * 0.10 +
        risk_map["fatigue"] * 0.10 +
        risk_map["cardiovascular"] * 0.10
    )
    return _clamp(overall)


def _apply_family_history(risk_map, profile):
    family = str(profile.get("family") or "No").strip().lower()
    family_conditions_raw = profile.get("family_conditions")

    if family != "yes" or not family_conditions_raw:
        return []

    active_conditions = []

    for condition in str(family_conditions_raw).split(","):
        condition = condition.strip()
        multipliers = FAMILY_RISK_MULTIPLIERS.get(condition)
        if not multipliers:
            continue

        active_conditions.append(condition)

        for risk_key, boost in multipliers.items():
            if risk_key in risk_map:
                risk_map[risk_key] *= (1 + boost)

    return active_conditions


def _finalize_risks(risk_map, active_conditions):
    result = {key: _clamp(risk_map[key]) for key in PROFILE_RISK_KEYS}
    result["overall"] = _clamp(risk_map["overall"])

    top_risks = sorted(
        [(key, result[key]) for key in PROFILE_RISK_KEYS],
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    result["top_risks"] = [risk_key for risk_key, _ in top_risks]

    if active_conditions:
        result["family_history_active"] = [
            condition.replace("_", " ").title()
            for condition in active_conditions
        ]

    return result


def predict_profile_risk(profile_or_age, smoking=None, gender=None, db_name="health.db"):
    profile = _as_profile(profile_or_age, smoking=smoking, gender=gender)

    conn = sqlite3.connect(db_name)
    try:
        cursor = conn.cursor()
        risk_map = _load_similar_user_risks(cursor, profile) or _build_default_risk_map()
    finally:
        conn.close()

    _apply_profile_adjustments(risk_map, profile)
    risk_map["overall"] = _calculate_overall(risk_map)
    active_conditions = _apply_family_history(risk_map, profile)

    return _finalize_risks(risk_map, active_conditions)
