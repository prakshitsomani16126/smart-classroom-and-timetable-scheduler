from flask import Flask, render_template, request, redirect, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        role TEXT,
        verified INTEGER DEFAULT 1,
        otp TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS classrooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS timetable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        classroom_id INTEGER,
        subject_id INTEGER,
        day TEXT,
        time TEXT
    )
    """)

    conn.commit()
    conn.close()

# ---------------- AUTH ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user"] = username
            session["role"] = user["role"]
            return redirect("/dashboard")
        else:
            flash("Invalid credentials")

    return render_template("index.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        email = request.form["email"]
        role = request.form["role"]

        conn = get_db()
        try:
            conn.execute("""
            INSERT INTO users (username, password, email, role)
            VALUES (?, ?, ?, ?)
            """, (username, password, email, role))
            conn.commit()
            flash("Account created! Login now.")
            return redirect("/")
        except:
            flash("Username already exists")

    return render_template("signup.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- API ----------------
@app.route("/api/classrooms", methods=["GET", "POST"])
def classrooms():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        data = request.json
        cursor.execute("INSERT INTO classrooms (name) VALUES (?)", (data["name"],))
        conn.commit()
        return jsonify({"message": "added"})

    rows = cursor.execute("SELECT * FROM classrooms").fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/subjects", methods=["GET", "POST"])
def subjects():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        data = request.json
        cursor.execute("INSERT INTO subjects (name) VALUES (?)", (data["name"],))
        conn.commit()
        return jsonify({"message": "added"})

    rows = cursor.execute("SELECT * FROM subjects").fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/timetable", methods=["GET", "POST"])
def timetable():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        data = request.json

        existing = cursor.execute("""
        SELECT * FROM timetable
        WHERE classroom_id=? AND day=? AND time=?
        """, (data["classroom_id"], data["day"], data["time"])).fetchone()

        if existing:
            return jsonify({"error": "Already booked"}), 400

        cursor.execute("""
        INSERT INTO timetable (classroom_id, subject_id, day, time)
        VALUES (?, ?, ?, ?)
        """, (data["classroom_id"], data["subject_id"], data["day"], data["time"]))

        conn.commit()
        return jsonify({"message": "scheduled"})

    rows = cursor.execute("""
    SELECT t.id, c.name as classroom, s.name as subject, t.day, t.time
    FROM timetable t
    JOIN classrooms c ON t.classroom_id=c.id
    JOIN subjects s ON t.subject_id=s.id
    """).fetchall()

    return jsonify([dict(row) for row in rows])

# ---------------- AI SCHEDULER ----------------
@app.route("/api/auto_schedule", methods=["POST"])
def auto_schedule():
    data = request.json

    classroom_id = data["classroom_id"]
    days = data["days"]
    times = data["times"]
    subject_ids = data["subjects"]

    conn = get_db()
    cursor = conn.cursor()

    # clear old data
    cursor.execute("DELETE FROM timetable WHERE classroom_id=?", (classroom_id,))

    for day in days:
        for time in times:
            subject_id = random.choice(subject_ids)

            cursor.execute("""
            INSERT INTO timetable (classroom_id, subject_id, day, time)
            VALUES (?, ?, ?, ?)
            """, (classroom_id, subject_id, day.strip(), time.strip()))

    conn.commit()
    return jsonify({"message": "AI timetable generated"})

# ---------------- DELETE ----------------
@app.route("/api/delete_all", methods=["POST"])
def delete_all():
    conn = get_db()
    conn.execute("DELETE FROM timetable")
    conn.commit()
    return jsonify({"message": "Deleted all timetable"})

# ---------------- PAGES ----------------
@app.route("/add")
def add_page():
    if "user" not in session:
        return redirect("/")
    return render_template("add.html")

@app.route("/timetable_page")
def timetable_page():
    if "user" not in session:
        return redirect("/")
    return render_template("timetable.html")

@app.route("/api/auto_generate", methods=["POST"])
def auto_generate():
    conn = get_db()
    cursor = conn.cursor()

    # get classrooms
    classrooms = cursor.execute("SELECT * FROM classrooms").fetchall()

    # get subjects
    subjects = cursor.execute("SELECT * FROM subjects").fetchall()

    if not classrooms or not subjects:
        return jsonify({"error": "Add classrooms & subjects first"}), 400

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    times = ["10:00", "11:00", "12:00"]

    # 🔥 CLEAR OLD DATA
    cursor.execute("DELETE FROM timetable")

    for classroom in classrooms:
        for day in days:
            used_subjects = []

            for time in times:
                # avoid repeating same subject in same day
                available = [s for s in subjects if s["id"] not in used_subjects]

                if not available:
                    available = subjects

                subject = random.choice(available)
                used_subjects.append(subject["id"])

                cursor.execute("""
                INSERT INTO timetable (classroom_id, subject_id, day, time)
                VALUES (?, ?, ?, ?)
                """, (classroom["id"], subject["id"], day, time))

    conn.commit()

    return jsonify({"message": "AI timetable generated automatically"})

# ---------------- RUN ----------------
import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
