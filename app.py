import os
import random
import string
import sqlite3
import pandas as pd
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

DATABASE = 'results.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    return conn

def create_table():
    conn = get_db()
    c = conn.cursor()
    # The user's request specified 'matric TEXT PRIMARY KEY', which would not allow
    # storing multiple courses per student. To fulfill the requirement of
    # calculating CGPA over multiple courses, a composite primary key of
    # (matric, name) is used instead, assuming 'name' is the course name.
    c.execute('''
        CREATE TABLE IF NOT EXISTS results (
            matric TEXT,
            name TEXT,
            pwd TEXT,
            ca INTEGER,
            exam INTEGER,
            total INTEGER,
            grade TEXT,
            unit INTEGER,
            points INTEGER,
            PRIMARY KEY (matric, name)
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the database
with app.app_context():
    create_table()

def calculate_grade(total):
    if total >= 70:
        return 'A', 5
    elif total >= 60:
        return 'B', 4
    elif total >= 50:
        return 'C', 3
    elif total >= 45:
        return 'D', 2
    else:
        return 'F', 0

@app.route('/admin/upload', methods=['POST'])
def upload_results():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        passwords = {}
        conn = get_db()
        c = conn.cursor()

        for index, row in df.iterrows():
            matric = row['matric']
            name = row['name']
            ca = row['ca']
            exam = row['exam']
            unit = row['unit']

            total = ca + exam
            grade, points = calculate_grade(total)

            password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            passwords[matric] = password

            c.execute('''
                INSERT OR REPLACE INTO results (matric, name, pwd, ca, exam, total, grade, unit, points)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (matric, name, password, ca, exam, total, grade, unit, points))

        conn.commit()
        conn.close()

        password_df = pd.DataFrame(list(passwords.items()), columns=['matric', 'password'])
        csv_response = password_df.to_csv(index=False)

        return csv_response, 200, {'Content-Type': 'text/csv'}
    else:
        return "Invalid file type", 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    matric = data.get('matric')
    password = data.get('password')

    if not matric or not password:
        return "Matric and password are required", 400

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM results WHERE matric = ?", (matric,))
    courses = c.fetchall()

    if courses and courses[0][2] == password: # Check password from the first course
        total_points = 0
        total_units = 0

        student_courses = []
        for course in courses:
            total_points += course[8] * course[7] # points * unit
            total_units += course[7]
            student_courses.append({
                "name": course[1],
                "ca": course[3],
                "exam": course[4],
                "total": course[5],
                "grade": course[6],
                "unit": course[7],
                "points": course[8]
            })

        cgpa = (total_points / total_units) if total_units > 0 else 0

        conn.close()
        return jsonify({"courses": student_courses, "cgpa": round(cgpa, 2)})
    else:
        conn.close()
        return "Invalid credentials", 401

@app.route('/admin/download', methods=['GET'])
def download_results():
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM results", conn)
    conn.close()

    csv_response = df.to_csv(index=False)

    return csv_response, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=results.csv'
    }

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
