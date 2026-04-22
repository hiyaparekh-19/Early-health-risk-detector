

import ollama

def generate_health_response(
    combined_data,
    user_message,
    risk_score=50,
    risk_scores=None,
    days_count=0,
    days_in_month=30,
    risk_type="general"
):
    try:
        # 🧠 Build smart prompt using your project data
        prompt = f"""
User Health Data:
{combined_data}

Risk Type: {risk_type}
Risk Score: {risk_score}/100
Days Logged: {days_count}/{days_in_month}

User Question:
{user_message}

Instructions:
- Give simple, clear health advice
- Do NOT give medical diagnosis
- Be helpful and friendly
- Keep answer short (3-5 lines)
"""

        response = ollama.chat(
            model='phi3',   # 🔥 fast model
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response['message']['content']

    except Exception as e:
        return f"Error: {str(e)}"
    
def detect_risk_type(user_message, risk_scores):
    msg = user_message.lower()

    # keyword mapping (same as before)
    if any(word in msg for word in ["headache", "migraine"]):
        return "migraine"
    elif any(word in msg for word in ["stress", "burnout"]):
        return "burnout"
    elif any(word in msg for word in ["sleep"]):
        return "sleep_disorder"
    elif any(word in msg for word in ["eye"]):
        return "eye_strain"
    elif any(word in msg for word in ["water"]):
        return "dehydration"
    elif any(word in msg for word in ["exercise", "steps"]):
        return "sedentary"
    elif any(word in msg for word in ["anxiety"]):
        return "anxiety"
    elif any(word in msg for word in ["fatigue", "tired"]):
        return "fatigue"

    # 🔥 FIX: filter only numeric values
    if risk_scores:
        numeric_scores = {
            k: v for k, v in risk_scores.items()
            if isinstance(v, (int, float))
        }

        if numeric_scores:
            return max(numeric_scores, key=numeric_scores.get)

    return "overall"