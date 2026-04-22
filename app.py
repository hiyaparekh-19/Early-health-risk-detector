import sqlite3
from flask import Flask, render_template, request, redirect, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from risk_engine import calculate_risks
from chatbot import generate_health_response
from chatbot import detect_risk_type
from flask import request, jsonify
from profile_ai_model import predict_profile_risk
from flask import session, redirect, url_for
from explain_engine import generate_explanations
from datetime import date, timedelta

# ----------------------------
# APP SETUP
# ----------------------------
app = Flask(__name__)
app.secret_key = "supersecretkey"
DB_NAME = "health.db"


RISK_CARD_DETAILS = [
    {
        "key": "migraine",
        "title": "Migraine Risk",
        "definition": "Migraine is a recurring headache condition that can cause strong head pain, sensitivity to light, nausea, and tiredness.",
        "signals": "This score rises when screen time, stress, and headache logs stay high.",
        "tip": "Reduce bright screens, hydrate well, sleep consistently, and notice repeated triggers.",
    },
    {
        "key": "burnout",
        "title": "Burnout Risk",
        "definition": "Burnout is long-term physical and mental exhaustion caused by sustained stress and poor recovery.",
        "signals": "This score rises when stress is high, energy is low, and sleep recovery is weak.",
        "tip": "Add short breaks, protect sleep time, and lower workload intensity where possible.",
    },
    {
        "key": "sleep_disorder",
        "title": "Sleep Disorder",
        "definition": "Sleep disorder risk points to irregular, insufficient, or low-quality sleep patterns.",
        "signals": "This score rises when sleep hours or sleep quality stay below a healthy baseline.",
        "tip": "Keep a fixed sleep schedule and reduce late caffeine or screens before bedtime.",
    },
    {
        "key": "eye_strain",
        "title": "Eye Strain",
        "definition": "Eye strain is discomfort from long visual focus, often linked with screens, dryness, or poor lighting.",
        "signals": "This score rises with long screen time and repeated eye-strain logs.",
        "tip": "Use the 20-20-20 rule, adjust brightness, and blink often during screen sessions.",
    },
    {
        "key": "dehydration",
        "title": "Dehydration",
        "definition": "Dehydration means your body may not be getting enough fluids for normal function.",
        "signals": "This score rises when water intake trends are low across logged days.",
        "tip": "Keep water nearby and aim for steady intake through the day.",
    },
    {
        "key": "sedentary",
        "title": "Inactivity",
        "definition": "Inactivity risk means your daily movement may be too low for good metabolic and heart health.",
        "signals": "This score rises when step counts stay low.",
        "tip": "Add small walks, stretch breaks, and a realistic daily step target.",
    },
    {
        "key": "anxiety",
        "title": "Anxiety",
        "definition": "Anxiety risk reflects patterns of high stress, restlessness, and poor recovery.",
        "signals": "This score rises when stress is high and sleep is weak.",
        "tip": "Try breathing breaks, journaling, calmer evening routines, and ask for help if symptoms persist.",
    },
    {
        "key": "fatigue",
        "title": "Fatigue",
        "definition": "Fatigue is ongoing tiredness or low energy that does not fully improve with normal rest.",
        "signals": "This score rises when energy levels are low and sleep recovery is poor.",
        "tip": "Balance rest, hydration, nutrition, and lighter activity until energy stabilizes.",
    },
    {
        "key": "digital_addiction",
        "title": "Digital Addiction",
        "definition": "Digital addiction risk reflects excessive screen use that may affect sleep, focus, or mood.",
        "signals": "This score rises when daily screen time stays high.",
        "tip": "Set screen limits, add offline breaks, and keep devices away before sleep.",
    },
    {
        "key": "cardiovascular",
        "title": "Heart Risk",
        "definition": "Heart risk estimates patterns that may affect cardiovascular wellness over time.",
        "signals": "This score rises with low activity, high stress, and weak hydration.",
        "tip": "Build regular movement, manage stress, and keep hydration consistent.",
    },
    {
        "key": "posture",
        "title": "Posture",
        "definition": "Posture risk reflects strain from long sitting, screen use, and limited movement.",
        "signals": "This score rises when screen time is high and movement is low.",
        "tip": "Adjust screen height, sit supported, and stretch your neck, back, and shoulders.",
    },
    {
        "key": "immunity",
        "title": "Immunity",
        "definition": "Immunity risk estimates whether stress, sleep, and energy patterns may weaken recovery.",
        "signals": "This score rises when sleep is low, stress is high, and energy is poor.",
        "tip": "Prioritize sleep, hydration, balanced meals, and steady stress reduction.",
    },
]


# ----------------------------
# DATABASE FUNCTIONS (DEFINE FIRST)
# ----------------------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_NAME)
        db.row_factory = sqlite3.Row
    return db


def get_month_context(year=None, month=None):
    today = date.today()

    if year is None or month is None:
        year = today.year
        month = today.month

    month_start = date(int(year), int(month), 1)

    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)

    month_end = next_month - timedelta(days=1)
    data_end = today if today.year == month_start.year and today.month == month_start.month else month_end

    return {
        "start": month_start.isoformat(),
        "end": data_end.isoformat(),
        "days_in_month": month_end.day,
        "key": month_start.strftime("%Y-%m"),
        "label": month_start.strftime("%B %Y"),
    }


def get_current_month_context():
    return get_month_context()


def get_month_context_from_key(month_key):
    try:
        year, month = month_key.split("-")
        return get_month_context(int(year), int(month))
    except Exception:
        return get_current_month_context()


def has_daily_data_unique_index(cur):
    for index in cur.execute("PRAGMA index_list(daily_data)").fetchall():
        if not index[2]:
            continue

        index_name = index[1]
        columns = [
            column[2]
            for column in cur.execute(f'PRAGMA index_info("{index_name}")').fetchall()
        ]

        if columns == ["user_id", "date"]:
            return True

    return False


def repair_daily_data_table(conn):
    cur = conn.cursor()

    # Keep only the newest saved row for each user/date pair.
    cur.execute("""
    DELETE FROM daily_data
    WHERE id NOT IN (
        SELECT MAX(id)
        FROM daily_data
        GROUP BY user_id, date
    )
    """)

    if not has_daily_data_unique_index(cur):
        cur.execute("""
        CREATE UNIQUE INDEX idx_daily_data_user_date
        ON daily_data(user_id, date)
        """)




def get_latest_daily_entry(db, user_id, selected_date):
    return db.execute(
        """
        SELECT *
        FROM daily_data
        WHERE user_id = ? AND date = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, selected_date)
    ).fetchone()


def get_month_data(db, user_id, month):
    rows = db.execute(
        """
        SELECT d.*
        FROM daily_data d
        INNER JOIN (
            SELECT MAX(id) AS id
            FROM daily_data
            WHERE user_id = ? AND date BETWEEN ? AND ?
            GROUP BY date
        ) latest ON latest.id = d.id
        ORDER BY d.date DESC
        """,
        (user_id, month["start"], month["end"])
    ).fetchall()

    return rows, month


def get_current_month_data(db, user_id):
    return get_month_data(db, user_id, get_current_month_context())


def get_available_months(db, user_id):
    rows = db.execute(
        """
        SELECT substr(date, 1, 7) AS month_key, COUNT(DISTINCT date) AS logs_count
        FROM daily_data
        WHERE user_id = ? AND date <= ?
        GROUP BY month_key
        ORDER BY month_key DESC
        """,
        (user_id, date.today().isoformat())
    ).fetchall()

    months = []
    for row in rows:
        context = get_month_context_from_key(row["month_key"])
        months.append({
            "key": context["key"],
            "label": context["label"],
            "logs_count": row["logs_count"],
            "days_in_month": context["days_in_month"],
        })

    return months


def ensure_month_in_list(months, month_context):
    if any(month["key"] == month_context["key"] for month in months):
        return months

    return [{
        "key": month_context["key"],
        "label": month_context["label"],
        "logs_count": 0,
        "days_in_month": month_context["days_in_month"],
    }] + months


def get_default_history_month(available_months):
    current_key = date.today().strftime("%Y-%m")

    for month in available_months:
        if month["key"] != current_key:
            return month["key"]

    if available_months:
        return available_months[0]["key"]

    return current_key


def build_calendar_grid(month_context, logged_dates, selected_date=None):
    month_start = date.fromisoformat(month_context["start"])
    days_in_month = month_context["days_in_month"]
    today_value = date.today().isoformat()
    weeks = []
    week = []

    for _ in range(month_start.weekday()):
        week.append(None)

    for day_number in range(1, days_in_month + 1):
        day_value = month_start.replace(day=day_number).isoformat()
        week.append({
            "day": day_number,
            "date": day_value,
            "has_log": day_value in logged_dates,
            "selected": day_value == selected_date,
            "is_today": day_value == today_value,
        })

        if len(week) == 7:
            weeks.append(week)
            week = []

    if week:
        while len(week) < 7:
            week.append(None)
        weeks.append(week)

    return weeks


def clamp_score(value):
    return max(0, min(100, value))


def row_float(row, key, default=0):
    try:
        return float(row[key])
    except Exception:
        return default


def row_int(row, key, default=0):
    try:
        return int(row[key])
    except Exception:
        return default


def calculate_daily_health_score(row):
    sleep_hours = row_float(row, "sleep_hours")
    sleep_quality = row_int(row, "sleep_quality")
    water_intake = row_float(row, "water_intake")
    screen_time = row_float(row, "screen_time")
    steps_count = row_int(row, "steps_count")
    stress_level = row_int(row, "stress_level")
    energy_level = row_int(row, "energy_level")

    sleep_score = clamp_score(100 - abs(8 - sleep_hours) * 16)
    quality_score = clamp_score((sleep_quality / 5) * 100)
    water_score = clamp_score((water_intake / 2.5) * 100)
    activity_score = clamp_score((steps_count / 10000) * 100)
    stress_score = clamp_score(((10 - stress_level) / 9) * 100)
    energy_score = clamp_score((energy_level / 5) * 100)
    screen_score = clamp_score(100 - max(0, screen_time - 4) * 16)

    symptom_score = 100
    if str(row["headache"]).lower() == "yes":
        symptom_score -= 20
    if str(row["eye_strain"]).lower() == "yes":
        symptom_score -= 15

    parts = [
        sleep_score,
        quality_score,
        water_score,
        activity_score,
        stress_score,
        energy_score,
        screen_score,
        clamp_score(symptom_score),
    ]

    return round(sum(parts) / len(parts))


def build_month_summary(month_data):
    if not month_data:
        return None

    scored_days = []
    for row in month_data:
        scored_days.append({
            "date": row["date"],
            "score": calculate_daily_health_score(row),
        })

    best_day = max(scored_days, key=lambda day: day["score"])
    worst_day = min(scored_days, key=lambda day: day["score"])
    average_score = round(sum(day["score"] for day in scored_days) / len(scored_days))

    return {
        "best": best_day,
        "worst": worst_day,
        "average_score": average_score,
        "days_logged": len(scored_days),
    }


def build_month_metric_summary(month_data):
    if not month_data:
        return None

    count = len(month_data)
    average_sleep = round(sum(row_float(row, "sleep_hours") for row in month_data) / count, 1)
    average_stress = round(sum(row_float(row, "stress_level") for row in month_data) / count, 1)
    average_screen = round(sum(row_float(row, "screen_time") for row in month_data) / count, 1)
    average_steps = round(sum(row_float(row, "steps_count") for row in month_data) / count)
    average_water = round(sum(row_float(row, "water_intake") for row in month_data) / count, 1)
    average_energy = round(sum(row_float(row, "energy_level") for row in month_data) / count, 1)

    score_cards = [
        ("Sleep balance", round(clamp_score(100 - abs(8 - average_sleep) * 16))),
        ("Stress balance", round(clamp_score(((10 - average_stress) / 9) * 100))),
        ("Hydration", round(clamp_score((average_water / 2.5) * 100))),
        ("Activity", round(clamp_score((average_steps / 10000) * 100))),
        ("Screen balance", round(clamp_score(100 - max(0, average_screen - 4) * 16))),
        ("Energy", round(clamp_score((average_energy / 5) * 100))),
    ]

    return {
        "average_sleep": average_sleep,
        "average_stress": average_stress,
        "average_screen": average_screen,
        "average_steps": average_steps,
        "average_water": average_water,
        "average_energy": average_energy,
        "score_labels": [item[0] for item in score_cards],
        "score_values": [item[1] for item in score_cards],
    }


def empty_risk_scores():
    return {
        "migraine": 0,
        "burnout": 0,
        "sleep_disorder": 0,
        "eye_strain": 0,
        "dehydration": 0,
        "sedentary": 0,
        "anxiety": 0,
        "fatigue": 0,
        "digital_addiction": 0,
        "cardiovascular": 0,
        "posture": 0,
        "immunity": 0,
        "overall": 0,
        "top_risks": [],
    }


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    # Profile (Fixed Parameters)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        age INTEGER,
        gender TEXT,
        height REAL,
        weight REAL,
        smoking TEXT,
        alcohol TEXT,
        family TEXT,
        family_conditions TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Add family_conditions column if it doesn't exist (migration for existing DBs)
    try:
        cur.execute("ALTER TABLE user_profile ADD COLUMN family_conditions TEXT")
        conn.commit()
    except Exception:
        pass  # Column already exists

    # Daily Data Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        sleep_hours REAL,
        sleep_quality INTEGER,
        water_intake REAL,
        screen_time REAL,
        steps_count INTEGER,
        stress_level INTEGER,
        energy_level INTEGER,
        headache TEXT,
        eye_strain TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, date)
    )
    """)

    repair_daily_data_table(conn)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS contact_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        topic TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()


# 🔥 CALL AFTER FUNCTION DEFINITION (IMPORTANT)
init_db()


@app.context_processor
def inject_template_globals():
    return {
        "current_year": date.today().year,
    }


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


# ----------------------------
# ROUTES
# ----------------------------

@app.route("/")
def home():
    return render_template("home.html", public_page=True)


@app.route("/about")
def about():
    return render_template("about.html", public_page=True)


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", public_page=True)


@app.route("/faq")
def faq():
    return render_template("faq.html", public_page=True)

@app.route("/test-image")
def test_image():
    return '<img src="/static/images/jeet.jpeg">'


@app.route("/contact", methods=["GET", "POST"])
def contact():
    submitted = request.args.get("sent") == "1"

    if request.method == "POST":
        db = get_db()
        db.execute(
            """
            INSERT INTO contact_messages (user_id, name, email, topic, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session.get("user_id"),
                request.form["name"].strip(),
                request.form["email"].strip(),
                request.form["topic"].strip(),
                request.form["message"].strip(),
            )
        )
        db.commit()
        return redirect(url_for("contact", sent=1))

    return render_template("contact.html", public_page=True, submitted=submitted)


# ----------------------------
# REGISTER
# ----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        # 🔥 EMAIL VALIDATION
        allowed_domains = ["gmail.com", "yahoo.com", "hotmail.com", "nmims.edu"]

        try:
            domain = email.split("@")[1]
        except:
            domain = ""

        if domain not in allowed_domains:
            error = "Only Gmail, Yahoo, Hotmail or NMIMS emails are allowed."

        # 🔥 PASSWORD VALIDATION
        import re
        if not re.match(r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$', password):
            error = "Password must be 8+ chars, include uppercase, number, and special character."

        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password))
                )
                db.commit()

                # ✅ AUTO LOGIN AFTER REGISTER
                user = db.execute(
                    "SELECT * FROM users WHERE email = ?",
                    (email,)
                ).fetchone()

                session["user_id"] = user["id"]
                session["user_name"] = user["name"]

                # ✅ GO TO PROFILE PAGE
                return redirect("/profile")

            except:
                error = "Email already exists!"

    return render_template("register.html", error=error)


# ----------------------------
# LOGIN (PROFILE FIRST FLOW)
# ----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if not user:
            error = "No account found with this email. Please sign up."

        elif not check_password_hash(user["password"], password):
            error = "Incorrect password. Please try again."

        else:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            profile = db.execute(
                "SELECT * FROM user_profile WHERE user_id = ?",
                (user["id"],)
            ).fetchone()

            if profile is None:
                return redirect("/profile")
            else:
                return redirect("/dashboard")

    return render_template("login.html", error=error)

# ----------------------------
# PROFILE (FIXED PARAMETERS)
# ----------------------------
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()

    if request.method == "POST":
        family = request.form["family"]

        # Collect selected family conditions (only if family history = Yes)
        family_conditions = None
        if family == "Yes":
            selected = request.form.getlist("family_conditions")
            if selected:
                family_conditions = ",".join(selected)

        db.execute("""
            INSERT OR REPLACE INTO user_profile
            (user_id, age, gender, height, weight, smoking, alcohol, family, family_conditions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            request.form["age"],
            request.form["gender"],
            request.form["height"],
            request.form["weight"],
            request.form["smoking"],
            request.form["alcohol"],
            family,
            family_conditions
        ))

        db.commit()
        return redirect("/dashboard")

    # Load existing profile to pre-fill form
    existing = db.execute(
        "SELECT * FROM user_profile WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()

    return render_template("profile.html", profile=existing)


# ----------------------------
# DAILY LOG
# ----------------------------
@app.route("/daily", methods=["GET", "POST"])
def daily():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        db = get_db()

        db.execute("""
        INSERT INTO daily_data
        (user_id, date, sleep_hours, sleep_quality, water_intake,
         screen_time, steps_count, stress_level,
         energy_level, headache, eye_strain)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET
            sleep_hours = excluded.sleep_hours,
            sleep_quality = excluded.sleep_quality,
            water_intake = excluded.water_intake,
            screen_time = excluded.screen_time,
            steps_count = excluded.steps_count,
            stress_level = excluded.stress_level,
            energy_level = excluded.energy_level,
            headache = excluded.headache,
            eye_strain = excluded.eye_strain
        """, (
            session["user_id"],
            request.form["date"],
            request.form["sleep_hours"],
            request.form["sleep_quality"],
            request.form["water_intake"],
            request.form["screen_time"],
            request.form["steps_count"],
            request.form["stress_level"],
            request.form["energy_level"],
            request.form["headache"],
            request.form["eye_strain"]
        ))

        db.commit()
        return redirect("/dashboard")

    return render_template("daily.html", today=date.today().isoformat())

# ----------------------------
# DASHBOARD
# ----------------------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    user_id = session["user_id"]

    selected_date = request.args.get("date")
    selected_calendar_month = request.args.get("month")
    today_value = date.today().isoformat()

    if selected_date and selected_date > today_value:
        selected_date = None

    if selected_date:
        selected_calendar_month = selected_date[:7]

    if not selected_calendar_month:
        selected_calendar_month = get_current_month_context()["key"]

    # Get all logged dates
    dates_query = db.execute(
        "SELECT DISTINCT date FROM daily_data WHERE user_id = ? AND date <= ? ORDER BY date DESC",
        (user_id, date.today().isoformat())
    ).fetchall()

    date_list = [row["date"] for row in dates_query]
    logged_dates = set(date_list)
    available_months = ensure_month_in_list(
        get_available_months(db, user_id),
        get_current_month_context()
    )
    available_month_keys = [month["key"] for month in available_months]

    if selected_calendar_month not in available_month_keys:
        selected_calendar_month = get_current_month_context()["key"]

    calendar_context = get_month_context_from_key(selected_calendar_month)
    calendar_weeks = build_calendar_grid(calendar_context, logged_dates, selected_date)

    # Get selected date data
    daily = None
    if selected_date:
        daily = get_latest_daily_entry(db, user_id, selected_date)

    # Fetch profile
    profile_row = db.execute(
        "SELECT * FROM user_profile WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    profile = dict(profile_row) if profile_row else None

    # Get the selected calendar month's data instead of always using the current month.
    month_data, month_context = get_month_data(db, user_id, calendar_context)

    days_count = len(month_data)
    days_in_month = month_context["days_in_month"]
    full_month_unlocked = days_count >= days_in_month

    # Hybrid AI (trend-based)
    risks = None
    if days_count >= 7:
        try:
            risks = calculate_risks(month_data, profile)
        except Exception as e:
            print("AI Error:", e)

    # 🧠 PROFILE BASED AI (COLD START MODEL)
    profile_ai = None

    if profile and days_count < 7:
        profile_ai = predict_profile_risk(profile)
    else:
        profile_ai = None

    # Graph data
    graph_dates = [row["date"] for row in month_data][::-1]
    sleep_data = [row["sleep_hours"] for row in month_data][::-1]
    stress_data = [row["stress_level"] for row in month_data][::-1]
    screen_data = [row["screen_time"] for row in month_data][::-1]
    steps_data = [row["steps_count"] for row in month_data][::-1]
    water_data = [row["water_intake"] for row in month_data][::-1]
    explanations = generate_explanations(month_data, profile, risks or {})
    month_summary = build_month_summary(month_data)

    return render_template(
        "dashboard.html",
        dates=date_list,
        selected_date=selected_date,
        selected_calendar_month=selected_calendar_month,
        calendar_month_label=calendar_context["label"],
        calendar_weeks=calendar_weeks,
        available_months=available_months,
        daily=daily,
        risks=risks,
        days_count=days_count,
        days_in_month=days_in_month,
        full_month_unlocked=full_month_unlocked,
        month_label=month_context["label"],
        month_summary=month_summary,
        risk_cards=RISK_CARD_DETAILS,
        graph_dates=graph_dates,
        sleep_data=sleep_data,
        stress_data=stress_data,
        screen_data=screen_data,
        steps_data=steps_data,
        water_data=water_data,
        profile=profile,
        profile_ai=profile_ai,
        explanations=explanations
    )


@app.route("/analytics")
def analytics():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()

    # Get profile data
    profile_row = db.execute(
    "SELECT * FROM user_profile WHERE user_id = ?",
    (session["user_id"],)
    ).fetchone()

    profile = dict(profile_row) if profile_row else None

    # Get this calendar month's data.
    month_data, month_context = get_current_month_data(db, session["user_id"])

    days_count = len(month_data)
    days_in_month = month_context["days_in_month"]
    full_month_unlocked = days_count >= days_in_month

    # 🔥 AI only after 7 days
    risks = None
    if days_count >= 7:
        risks = calculate_risks(month_data, profile)
    else:
        risks = empty_risk_scores()

    # Graph data (even if <7 days we can still prepare)
    dates = [row["date"] for row in month_data][::-1]
    sleep = [row["sleep_hours"] for row in month_data][::-1]
    stress = [row["stress_level"] for row in month_data][::-1]
    screen = [row["screen_time"] for row in month_data][::-1]
    steps = [row["steps_count"] for row in month_data][::-1]
    month_summary = build_month_summary(month_data)

    return render_template(
        "analytics.html",
        risks=risks,
        days_count=days_count,
        days_in_month=days_in_month,
        full_month_unlocked=full_month_unlocked,
        month_label=month_context["label"],
        month_summary=month_summary,
        risk_cards=RISK_CARD_DETAILS,
        dates=dates,
        sleep=sleep,
        stress=stress,
        screen=screen,
        steps=steps
    )


@app.route("/monthly-history")
def monthly_history():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    user_id = session["user_id"]

    profile_row = db.execute(
        "SELECT * FROM user_profile WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    profile = dict(profile_row) if profile_row else None

    current_month_key = get_current_month_context()["key"]
    available_months = [
        month for month in get_available_months(db, user_id)
        if month["key"] != current_month_key
    ]
    selected_month = request.args.get("month")
    available_keys = [month["key"] for month in available_months]

    if selected_month not in available_keys and available_months:
        selected_month = available_months[0]["key"]

    if selected_month:
        month_context = get_month_context_from_key(selected_month)
        month_data, month_context = get_month_data(db, user_id, month_context)
        days_count = len(month_data)
        days_in_month = month_context["days_in_month"]
        full_month_unlocked = days_count >= days_in_month
    else:
        month_context = None
        month_data = []
        days_count = 0
        days_in_month = 0
        full_month_unlocked = False

    if days_count >= 7:
        risks = calculate_risks(month_data, profile)
    else:
        risks = empty_risk_scores()

    month_summary = build_month_summary(month_data)
    metric_summary = build_month_metric_summary(month_data)
    explanations = generate_explanations(month_data, profile, risks or {}) if month_data else []

    dates = [row["date"] for row in month_data][::-1]
    sleep = [row["sleep_hours"] for row in month_data][::-1]
    stress = [row["stress_level"] for row in month_data][::-1]
    screen = [row["screen_time"] for row in month_data][::-1]
    steps = [row["steps_count"] for row in month_data][::-1]
    risk_chart_labels = [risk["title"] for risk in RISK_CARD_DETAILS]
    risk_chart_values = [risks.get(risk["key"], 0) for risk in RISK_CARD_DETAILS]

    return render_template(
        "monthly_history.html",
        available_months=available_months,
        selected_month=month_context["key"] if month_context else None,
        month_label=month_context["label"] if month_context else "Archived History",
        days_count=days_count,
        days_in_month=days_in_month,
        full_month_unlocked=full_month_unlocked,
        month_summary=month_summary,
        metric_summary=metric_summary,
        risks=risks,
        risk_cards=RISK_CARD_DETAILS,
        explanations=explanations,
        dates=dates,
        sleep=sleep,
        stress=stress,
        screen=screen,
        steps=steps,
        risk_chart_labels=risk_chart_labels,
        risk_chart_values=risk_chart_values,
    )


@app.route("/chat", methods=["POST"])
def chat():
    if "user_id" not in session:
        return jsonify({"reply": "Please login first."})

    user_message = request.json.get("message")
    user_id = session["user_id"]

    db = get_db()

    # PROFILE
    profile_row = db.execute(
        "SELECT * FROM user_profile WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    profile = dict(profile_row) if profile_row else {}

    # Current calendar month data
    month_rows, month_context = get_current_month_data(db, user_id)

    month_data = [dict(row) for row in month_rows]
    days_count = len(month_data)

    # -----------------------------
    # RISK CALCULATION
    # -----------------------------
    if days_count > 0:
        risk_scores = calculate_risks(month_data, profile)

    else:
        # 🧊 COLD START FIXED
        risk_scores = predict_profile_risk(profile)

    # -----------------------------
    # DETECT RISK TYPE
    # -----------------------------
    risk_type = detect_risk_type(user_message, risk_scores)

    # -----------------------------
    # GET SCORE
    # -----------------------------
    risk_score = risk_scores.get(risk_type, risk_scores.get("overall", 50))

    # -----------------------------
    # COMBINE DATA FOR CHATBOT (FIX)
    # -----------------------------
    latest_data = month_data[0] if month_data else {}
    combined_data = {**profile, **latest_data}

    # -----------------------------
    # GENERATE RESPONSE
    # -----------------------------
    bot_reply = generate_health_response(
        combined_data,
        user_message,
        risk_score=risk_score,
        risk_scores=risk_scores,
        days_count=days_count,
        days_in_month=month_context["days_in_month"],
        risk_type=risk_type,
    )

    # NOTE FOR LOW DATA
    note = ""
    if days_count < 7:
        note = " (based on limited data)"

    return jsonify({
        "reply": bot_reply + note,
        "risk_type": risk_type,
        "risk_score": risk_score,
        "days_count": days_count,
        "days_in_month": month_context["days_in_month"],
        "month_label": month_context["label"]
    })

@app.route("/terms")
def terms():
    return render_template("terms.html", public_page=True)

@app.route("/chatbot")
def chatbot_page():
    return render_template("chatbot.html")

@app.route("/logout")
def logout():
    session.clear()  # clears all login data
    return redirect(url_for("login"))

# ----------------------------
# RUN SERVER
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)
