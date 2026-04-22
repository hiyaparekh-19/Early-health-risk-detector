def generate_explanations(month_data, profile, risks):
    explanations = {
        "migraine": [],
        "burnout": [],
        "sleep_disorder": [],
        "eye_strain": [],
        "dehydration": [],
        "sedentary": [],
        "anxiety": [],
        "fatigue": [],
        "digital_addiction": [],
        "cardiovascular": [],
        "posture": [],
        "immunity": [],
        "overall": []
    }

    # Cold start
    if not month_data:
        explanations["overall"].append("Prediction based on profile and trained dataset")
        return explanations

    n = len(month_data)

    avg_sleep = sum(d["sleep_hours"] or 0 for d in month_data) / n
    avg_stress = sum(d["stress_level"] or 0 for d in month_data) / n
    avg_screen = sum(d["screen_time"] or 0 for d in month_data) / n
    avg_water = sum(d["water_intake"] or 0 for d in month_data) / n
    avg_steps = sum(d["steps_count"] or 0 for d in month_data) / n
    avg_energy = sum(d["energy_level"] or 0 for d in month_data) / n

    # -----------------------------
    # MIGRAINE
    # -----------------------------
    if avg_stress > 5:
        explanations["migraine"].append("Elevated stress levels detected")
    if avg_sleep < 7:
        explanations["migraine"].append("Sleep imbalance contributing to headaches")
    if avg_screen > 6:
        explanations["migraine"].append("High screen exposure increasing strain")

    # -----------------------------
    # BURNOUT
    # -----------------------------
    if avg_stress >= 7:
        explanations["burnout"].append("Very high stress levels detected")
    elif avg_stress >= 4:
        explanations["burnout"].append("Moderate stress patterns observed")
    else:
        explanations["burnout"].append("Stress levels are relatively controlled")

    if avg_sleep < 6:
        explanations["burnout"].append("Low sleep contributing to fatigue")

    if avg_screen > 6:
        explanations["burnout"].append("High screen time increasing mental fatigue")

    # -----------------------------
    # SLEEP
    # -----------------------------
    if avg_sleep < 6:
        explanations["sleep_disorder"].append("Average sleep below healthy threshold")
    else:
        explanations["sleep_disorder"].append("Sleep patterns slightly irregular")

    # -----------------------------
    # EYE STRAIN
    # -----------------------------
    if avg_screen > 5:
        explanations["eye_strain"].append("Prolonged screen time usage")

    # -----------------------------
    # DEHYDRATION
    # -----------------------------
    if avg_water < 2:
        explanations["dehydration"].append("Water intake below recommended levels")

    # -----------------------------
    # NEW RISKS 🔥
    # -----------------------------

    # Sedentary
    if avg_steps < 5000:
        explanations["sedentary"].append("Low daily movement detected")
    else:
        explanations["sedentary"].append("Activity levels are moderate")

    # Anxiety
    if avg_stress > 6:
        explanations["anxiety"].append("High stress contributing to anxiety patterns")
    if avg_sleep < 6:
        explanations["anxiety"].append("Insufficient sleep impacting mental balance")

    # Fatigue
    if avg_energy < 3:
        explanations["fatigue"].append("Low energy levels observed")
    if avg_sleep < 6:
        explanations["fatigue"].append("Sleep deficit causing tiredness")

    # Digital Addiction
    if avg_screen > 6:
        explanations["digital_addiction"].append("High screen time dependency detected")

    # Cardiovascular
    if avg_steps < 4000:
        explanations["cardiovascular"].append("Low physical activity affecting heart health")
    if avg_stress > 6:
        explanations["cardiovascular"].append("Stress impacting cardiovascular health")

    # Posture
    if avg_screen > 6:
        explanations["posture"].append("Long screen hours affecting posture")
    if avg_steps < 5000:
        explanations["posture"].append("Low movement contributing to poor posture")

    # Immunity
    if avg_sleep < 6:
        explanations["immunity"].append("Sleep deficiency weakening immunity")
    if avg_stress > 6:
        explanations["immunity"].append("High stress affecting immune response")

    # -----------------------------
    # OVERALL
    # -----------------------------
    explanations["overall"].append("Calculated using hybrid AI model")
    explanations["overall"].append("Based on current monthly health trends")

    if profile:
        explanations["overall"].append("Personal profile factors included")

    return explanations
