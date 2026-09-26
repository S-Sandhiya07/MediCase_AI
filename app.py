
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
from pathlib import Path
from model import CaseTakingModel

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "medicase.db"

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY_BEFORE_DEPLOYMENT"

ai_model = CaseTakingModel()

LANGUAGES = {
    "English": "en-IN",
    "Tamil": "ta-IN",
    "Hindi": "hi-IN",
    "Telugu": "te-IN",
    "Kannada": "kn-IN",
    "Malayalam": "ml-IN",
}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('patient','doctor')),
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        patient_code TEXT NOT NULL UNIQUE,
        age INTEGER,
        gender TEXT,
        phone TEXT,
        preferred_language TEXT DEFAULT 'English',
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS consultations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'In Progress',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS case_information (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consultation_id INTEGER NOT NULL UNIQUE,
        chief_complaint TEXT DEFAULT '',
        symptoms TEXT DEFAULT '',
        duration TEXT DEFAULT '',
        severity TEXT DEFAULT '',
        symptom_details TEXT DEFAULT '',
        medical_history TEXT DEFAULT '',
        previous_surgeries TEXT DEFAULT '',
        medications TEXT DEFAULT '',
        allergies TEXT DEFAULT '',
        family_history TEXT DEFAULT '',
        lifestyle TEXT DEFAULT '',
        FOREIGN KEY(consultation_id) REFERENCES consultations(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consultation_id INTEGER NOT NULL,
        speaker TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(consultation_id) REFERENCES consultations(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS doctor_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consultation_id INTEGER NOT NULL UNIQUE,
        doctor_id INTEGER NOT NULL,
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(consultation_id) REFERENCES consultations(id) ON DELETE CASCADE,
        FOREIGN KEY(doctor_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    # Demo doctor account for SIH presentation.
    doctor = conn.execute("SELECT id FROM users WHERE email=?", ("doctor@medicase.ai",)).fetchone()
    if not doctor:
        conn.execute(
            "INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
            ("Demo Doctor", "doctor@medicase.ai",
             generate_password_hash("Doctor@123"), "doctor", datetime.now().isoformat())
        )
    conn.commit()
    conn.close()

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user

def require_role(role):
    user = current_user()
    if not user or user["role"] != role:
        return None
    return user

def patient_for_user(user_id):
    conn = db()
    p = conn.execute("""
        SELECT p.*, u.name, u.email
        FROM patients p JOIN users u ON u.id=p.user_id
        WHERE p.user_id=?
    """, (user_id,)).fetchone()
    conn.close()
    return p

def next_patient_code(conn):
    row = conn.execute("SELECT COUNT(*) AS n FROM patients").fetchone()
    return f"MC-PAT-{row['n'] + 10001:05d}"

def add_message(conn, consultation_id, speaker, message):
    conn.execute(
        "INSERT INTO conversations(consultation_id,speaker,message,created_at) VALUES(?,?,?,?)",
        (consultation_id, speaker, message, datetime.now().isoformat())
    )

@app.route("/")
def home():
    return render_template("landing.html", user=current_user())

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        age = request.form.get("age") or None
        gender = request.form.get("gender") or ""
        phone = request.form.get("phone") or ""
        language = request.form.get("preferred_language") or "English"

        if not name or not email or not password:
            flash("Please fill the required fields.", "error")
            return redirect(url_for("register"))

        conn = db()
        try:
            cur = conn.execute(
                "INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                (name,email,generate_password_hash(password),"patient",datetime.now().isoformat())
            )
            user_id = cur.lastrowid
            code = next_patient_code(conn)
            conn.execute(
                "INSERT INTO patients(user_id,patient_code,age,gender,phone,preferred_language) VALUES(?,?,?,?,?,?)",
                (user_id,code,age,gender,phone,language)
            )
            conn.commit()
            flash(f"Account created. Your Patient ID is {code}. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("An account with that email already exists.", "error")
        finally:
            conn.close()
    return render_template("register.html", user=current_user(), languages=LANGUAGES)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            if user["role"] == "doctor":
                return redirect(url_for("doctor_dashboard"))
            return redirect(url_for("patient_dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html", user=current_user())

@app.route("/doctor/login", methods=["GET","POST"])
def doctor_login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND role='doctor'", (email,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("doctor_dashboard"))
        flash("Invalid doctor credentials.", "error")
    return render_template("doctor_login.html", user=current_user())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/patient/dashboard")
def patient_dashboard():
    user = require_role("patient")
    if not user:
        return redirect(url_for("login"))
    patient = patient_for_user(user["id"])
    conn = db()
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM consultations WHERE patient_id=?", (patient["id"],)
    ).fetchone()["n"]
    latest = conn.execute("""
        SELECT * FROM consultations
        WHERE patient_id=? ORDER BY id DESC LIMIT 1
    """, (patient["id"],)).fetchone()
    conn.close()
    return render_template("patient_dashboard.html", user=user, patient=patient,
                           consultation_count=count, latest=latest)

@app.route("/patient/profile", methods=["GET","POST"])
def patient_profile():
    user = require_role("patient")
    if not user:
        return redirect(url_for("login"))
    patient = patient_for_user(user["id"])
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        age = request.form.get("age") or None
        gender = request.form.get("gender") or ""
        phone = request.form.get("phone") or ""
        language = request.form.get("preferred_language") or "English"
        conn = db()
        try:
            conn.execute("UPDATE users SET name=?,email=? WHERE id=?",
                         (name,email,user["id"]))
            conn.execute("""UPDATE patients SET age=?,gender=?,phone=?,preferred_language=?
                            WHERE user_id=?""",
                         (age,gender,phone,language,user["id"]))
            conn.commit()
            flash("Profile updated.", "success")
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("That email is already in use.", "error")
        finally:
            conn.close()
        return redirect(url_for("patient_profile"))
    patient = patient_for_user(user["id"])
    return render_template("patient_profile.html", user=user, patient=patient, languages=LANGUAGES)

@app.route("/consultation/new")
def new_consultation():
    user = require_role("patient")
    if not user:
        return redirect(url_for("login"))
    patient = patient_for_user(user["id"])
    conn = db()
    cur = conn.execute(
        "INSERT INTO consultations(patient_id,status,created_at,updated_at) VALUES(?,?,?,?)",
        (patient["id"],"In Progress",datetime.now().isoformat(),datetime.now().isoformat())
    )
    cid = cur.lastrowid
    conn.execute("INSERT INTO case_information(consultation_id) VALUES(?)", (cid,))
    add_message(conn, cid, "AI",
                "Hello! I’m your AI Case-Taking Assistant. I’ll collect information for your doctor consultation. I do not diagnose conditions.")
    add_message(conn, cid, "AI", "What problem are you experiencing today?")
    conn.commit()
    conn.close()
    return redirect(url_for("consultation", consultation_id=cid))

def get_patient_consultation(cid, patient_id):
    conn = db()
    row = conn.execute("""
        SELECT c.*, ci.*, p.patient_code, u.name, p.age, p.gender, p.preferred_language
        FROM consultations c
        JOIN case_information ci ON ci.consultation_id=c.id
        JOIN patients p ON p.id=c.patient_id
        JOIN users u ON u.id=p.user_id
        WHERE c.id=? AND c.patient_id=?
    """, (cid,patient_id)).fetchone()
    messages = conn.execute(
        "SELECT * FROM conversations WHERE consultation_id=? ORDER BY id", (cid,)
    ).fetchall()
    conn.close()
    return row, messages

QUESTION_FLOW = [
    ("chief_complaint", "What problem are you experiencing today?"),
    ("duration", "Since when have you been experiencing this problem?"),
    ("severity", "How severe is it from 1 to 10?"),
    ("symptoms", "Are there any other symptoms you want to mention?"),
    ("medications", "Are you currently taking any medicines? If none, say none."),
    ("allergies", "Do you have any known allergies? If none, say none."),
    ("medical_history", "Do you have any important past medical history? If none, say none."),
    ("family_history", "Is there any relevant family medical history? If none, say none."),
    ("lifestyle", "Is there anything about your lifestyle that you want your doctor to know, such as smoking, alcohol, sleep, or exercise? If none, say none."),
]

def next_missing_field(case):
    for field, _ in QUESTION_FLOW:
        if not (case[field] or "").strip():
            return field
    return None

def clean_value(field, text):
    value = text.strip()
    if field == "severity":
        import re
        m = re.search(r"\b(10|[1-9])\b", value)
        if m:
            return m.group(1) + "/10"
    return value

@app.route("/consultation/<int:consultation_id>")
def consultation(consultation_id):
    user = require_role("patient")
    if not user:
        return redirect(url_for("login"))
    patient = patient_for_user(user["id"])
    case, messages = get_patient_consultation(consultation_id, patient["id"])
    if not case:
        flash("Consultation not found.", "error")
        return redirect(url_for("patient_history"))
    return render_template("consultation.html", user=user, patient=patient,
                           case=case, messages=messages, languages=LANGUAGES)

@app.route("/api/consultation/<int:consultation_id>/message", methods=["POST"])
def consultation_message(consultation_id):
    user = require_role("patient")
    if not user:
        return jsonify({"error":"Unauthorized"}), 401
    patient = patient_for_user(user["id"])
    conn = db()
    case = conn.execute("""
        SELECT c.*, ci.*
        FROM consultations c JOIN case_information ci ON ci.consultation_id=c.id
        WHERE c.id=? AND c.patient_id=?
    """, (consultation_id,patient["id"])).fetchone()
    if not case:
        conn.close()
        return jsonify({"error":"Consultation not found"}), 404

    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()
    if not text:
        conn.close()
        return jsonify({"error":"Empty message"}), 400

    add_message(conn, consultation_id, "Patient", text)
    intent = ai_model.predict_intent(text)
    field = next_missing_field(case)

    # The model classifies the utterance, while the safe case-taking flow
    # uses the current missing field to decide where to store information.
    if field:
        value = clean_value(field, text)
        conn.execute(f"UPDATE case_information SET {field}=? WHERE consultation_id=?",
                     (value,consultation_id))
        reply = None
        fields = {["chief_complaint"]: "chief_complaint"}  # no-op; keeps response simple
        idx = next((i for i,(f,_) in enumerate(QUESTION_FLOW) if f == field), 0)
        if idx + 1 < len(QUESTION_FLOW):
            reply = QUESTION_FLOW[idx+1][1]
        else:
            reply = "Thank you. I have collected the available information. Please review it before saving the case."
    else:
        reply = "Thank you. Please review the collected information before saving the case."

    # Small intent-aware fallback for an off-flow answer.
    if intent == "greeting":
        reply = "Hello. I’m ready to collect your case information. " + (QUESTION_FLOW[0][1] if not case["chief_complaint"] else QUESTION_FLOW[1][1])

    add_message(conn, consultation_id, "AI", reply)
    conn.execute("UPDATE consultations SET updated_at=? WHERE id=?",
                 (datetime.now().isoformat(),consultation_id))
    conn.commit()
    new_case = conn.execute("SELECT * FROM case_information WHERE consultation_id=?",
                            (consultation_id,)).fetchone()
    conn.close()
    return jsonify({
        "reply": reply,
        "intent": intent,
        "case": dict(new_case)
    })

@app.route("/api/consultation/<int:consultation_id>/manual", methods=["POST"])
def manual_case(consultation_id):
    user = require_role("patient")
    if not user:
        return jsonify({"error":"Unauthorized"}), 401
    patient = patient_for_user(user["id"])
    conn = db()
    allowed = ["chief_complaint","symptoms","duration","severity","symptom_details",
               "medical_history","previous_surgeries","medications","allergies",
               "family_history","lifestyle"]
    data = request.get_json(silent=True) or {}
    exists = conn.execute("SELECT id FROM consultations WHERE id=? AND patient_id=?",
                          (consultation_id,patient["id"])).fetchone()
    if not exists:
        conn.close()
        return jsonify({"error":"Not found"}),404
    for field in allowed:
        if field in data:
            conn.execute(f"UPDATE case_information SET {field}=? WHERE consultation_id=?",
                         (str(data[field] or ""),consultation_id))
    conn.commit()
    conn.close()
    return jsonify({"ok":True})

@app.route("/consultation/<int:consultation_id>/save", methods=["POST"])
def save_consultation(consultation_id):
    user = require_role("patient")
    if not user:
        return redirect(url_for("login"))
    patient = patient_for_user(user["id"])
    conn = db()
    row = conn.execute("SELECT id FROM consultations WHERE id=? AND patient_id=?",
                       (consultation_id,patient["id"])).fetchone()
    if not row:
        conn.close()
        flash("Consultation not found.", "error")
        return redirect(url_for("patient_history"))
    conn.execute("UPDATE consultations SET status='Pending Review', updated_at=? WHERE id=?",
                 (datetime.now().isoformat(),consultation_id))
    conn.commit()
    conn.close()
    flash("Consultation saved and sent for doctor review.", "success")
    return redirect(url_for("case_summary", consultation_id=consultation_id))

@app.route("/consultation/<int:consultation_id>/summary")
def case_summary(consultation_id):
    user = require_role("patient")
    if not user:
        return redirect(url_for("login"))
    patient = patient_for_user(user["id"])
    case, messages = get_patient_consultation(consultation_id, patient["id"])
    if not case:
        return redirect(url_for("patient_history"))
    return render_template("case_summary.html", user=user, patient=patient,
                           case=case, messages=messages)

@app.route("/patient/history")
def patient_history():
    user = require_role("patient")
    if not user:
        return redirect(url_for("login"))
    patient = patient_for_user(user["id"])
    conn = db()
    rows = conn.execute("""
        SELECT c.*, ci.chief_complaint
        FROM consultations c JOIN case_information ci ON ci.consultation_id=c.id
        WHERE c.patient_id=? ORDER BY c.id DESC
    """,(patient["id"],)).fetchall()
    conn.close()
    return render_template("patient_history.html", user=user, patient=patient, rows=rows)

@app.route("/doctor/dashboard")
def doctor_dashboard():
    user = require_role("doctor")
    if not user:
        return redirect(url_for("doctor_login"))
    conn = db()
    stats = {
        "patients": conn.execute("SELECT COUNT(*) n FROM patients").fetchone()["n"],
        "today": conn.execute(
            "SELECT COUNT(*) n FROM consultations WHERE date(created_at)=date('now')"
        ).fetchone()["n"],
        "pending": conn.execute(
            "SELECT COUNT(*) n FROM consultations WHERE status='Pending Review'"
        ).fetchone()["n"],
        "completed": conn.execute(
            "SELECT COUNT(*) n FROM consultations WHERE status='Finalized'"
        ).fetchone()["n"],
    }
    rows = conn.execute("""
        SELECT c.*, p.patient_code, p.age, u.name,
               ci.chief_complaint
        FROM consultations c
        JOIN patients p ON p.id=c.patient_id
        JOIN users u ON u.id=p.user_id
        JOIN case_information ci ON ci.consultation_id=c.id
        ORDER BY c.id DESC LIMIT 30
    """).fetchall()
    conn.close()
    return render_template("doctor_dashboard.html", user=user, stats=stats, rows=rows)

def doctor_case_data(cid):
    conn = db()
    row = conn.execute("""
        SELECT c.*, ci.*, p.patient_code, p.age, p.gender, p.phone,
               p.preferred_language, u.name, u.email
        FROM consultations c
        JOIN case_information ci ON ci.consultation_id=c.id
        JOIN patients p ON p.id=c.patient_id
        JOIN users u ON u.id=p.user_id
        WHERE c.id=?
    """,(cid,)).fetchone()
    messages = conn.execute(
        "SELECT * FROM conversations WHERE consultation_id=? ORDER BY id",(cid,)
    ).fetchall()
    note = conn.execute(
        "SELECT * FROM doctor_notes WHERE consultation_id=?",(cid,)
    ).fetchone()
    conn.close()
    return row,messages,note

@app.route("/doctor/case/<int:consultation_id>", methods=["GET","POST"])
def doctor_case(consultation_id):
    user = require_role("doctor")
    if not user:
        return redirect(url_for("doctor_login"))
    if request.method == "POST":
        notes = request.form.get("notes","")
        action = request.form.get("action","save")
        conn = db()
        now = datetime.now().isoformat()
        existing = conn.execute(
            "SELECT id FROM doctor_notes WHERE consultation_id=?",(consultation_id,)
        ).fetchone()
        if existing:
            conn.execute("UPDATE doctor_notes SET notes=?,doctor_id=?,updated_at=? WHERE consultation_id=?",
                         (notes,user["id"],now,consultation_id))
        else:
            conn.execute(
                "INSERT INTO doctor_notes(consultation_id,doctor_id,notes,created_at,updated_at) VALUES(?,?,?,?,?)",
                (consultation_id,user["id"],notes,now,now)
            )
        if action == "finalize":
            conn.execute("UPDATE consultations SET status='Finalized',updated_at=? WHERE id=?",
                         (now,consultation_id))
        else:
            conn.execute("UPDATE consultations SET status='Reviewed',updated_at=? WHERE id=?",
                         (now,consultation_id))
        conn.commit()
        conn.close()
        flash("Case updated." if action != "finalize" else "Case finalized by doctor.", "success")
        return redirect(url_for("doctor_case", consultation_id=consultation_id))
    row,messages,note = doctor_case_data(consultation_id)
    if not row:
        flash("Case not found.", "error")
        return redirect(url_for("doctor_dashboard"))
    return render_template("doctor_case.html", user=user, case=row, messages=messages, note=note)

@app.context_processor
def inject_globals():
    return {"current_user": current_user()}

if __name__ == "__main__":
    init_db()
    print("\nMediCase AI is running at: http://127.0.0.1:5000")
    print("Demo doctor: doctor@medicase.ai")
    print("Demo doctor password: Doctor@123")
    app.run(debug=True)
