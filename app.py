from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
BASE = Path(__file__).resolve().parent
DB = BASE / "diet_analyzer.db"
FOOD_CSV = BASE / "data" / "food_dataset.csv"

def db_connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, age INTEGER, gender TEXT, weight REAL, height REAL,
                goal TEXT, bmi REAL, category TEXT, calories INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def calculate_bmi(weight, height_cm):
    height_m = height_cm / 100
    return float(np.round(weight / np.square(height_m), 2))

def get_category(bmi):
    if bmi < 18.5: return "Underweight"
    if bmi < 25: return "Normal"
    if bmi < 30: return "Overweight"
    return "Obesity range"

def estimate_calories(age, gender, weight, height, activity, goal):
    # Mifflin-St Jeor educational estimate
    bmr = 10 * weight + 6.25 * height - 5 * age + (5 if gender == "Male" else -161)
    factors = {"Low": 1.2, "Moderate": 1.55, "High": 1.725}
    maintenance = bmr * factors.get(activity, 1.2)
    if goal == "Weight loss": maintenance -= 300
    elif goal == "Weight gain": maintenance += 300
    return int(np.clip(np.round(maintenance), 1200, 4000))

def get_meals(goal):
    data = pd.read_csv(FOOD_CSV)
    selected = data[data["goal"] == goal]
    return {meal: selected[selected["meal"] == meal].iloc[0]["suggestion"]
            for meal in ["Breakfast", "Lunch", "Snack", "Dinner"]}

@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip() or "User"
            age = int(request.form["age"])
            gender = request.form["gender"]
            weight = float(request.form["weight"])
            height = float(request.form["height"])
            activity = request.form["activity"]
            goal = request.form["goal"]
            if not (1 <= age <= 100 and 20 <= weight <= 300 and 100 <= height <= 230):
                raise ValueError("Enter realistic positive age, weight and height values.")
            if gender not in ["Male", "Female"] or activity not in ["Low", "Moderate", "High"]:
                raise ValueError("Please select valid options.")
            if goal not in ["Weight loss", "Weight gain", "Maintain weight"]:
                raise ValueError("Please select a valid goal.")
            bmi = calculate_bmi(weight, height)
            category = get_category(bmi)
            calories = estimate_calories(age, gender, weight, height, activity, goal)
            meals = get_meals(goal)
            with db_connect() as conn:
                conn.execute("""INSERT INTO analysis_history
                    (name, age, gender, weight, height, goal, bmi, category, calories)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, age, gender, weight, height, goal, bmi, category, calories))
                conn.commit()
            result = {"name": name, "bmi": bmi, "category": category,
                      "calories": calories, "goal": goal, "meals": meals}
        except (ValueError, KeyError, TypeError) as error:
            flash(str(error) or "Please enter valid details.", "error")
    with db_connect() as conn:
        history = conn.execute("SELECT * FROM analysis_history ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("index.html", result=result, history=history)

@app.route("/history/delete", methods=["POST"])
def clear_history():
    with db_connect() as conn:
        conn.execute("DELETE FROM analysis_history")
        conn.commit()
    flash("History cleared.", "success")
    return redirect(url_for("home"))

init_db()

if __name__ == "__main__":
    app.run(debug=True)
