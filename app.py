from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from flask_login import login_required

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Для роботи сесій

DB_NAME = "schedule.db"

def get_db_connection():
    db_path = os.path.abspath(DB_NAME)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    date = request.args.get('date')
    group_id = request.args.get('group')
    teacher = request.args.get('teacher')
    
    conn = get_db_connection()
    groups = conn.execute("SELECT id, name FROM groups").fetchall()
    groups_list = [("all", "Всі групи")] + [(g['id'], g['name']) for g in groups]
    
    query = """
        SELECT g.name AS group_name, s.name AS subject_name, t.name AS teacher_name, sch.lesson_number, sch.date
        FROM schedule sch
        JOIN groups g ON sch.group_id = g.id
        JOIN subjects s ON sch.subject_id = s.id
        JOIN teachers t ON sch.teacher_id = t.id
        WHERE 1=1
    """
    params = []
    
    if date:
        query += " AND sch.date = ?"
        params.append(date)
    if group_id and group_id != "all":
        query += " AND g.id = ?"
        params.append(group_id)
    if teacher:
        query += " AND t.name LIKE ?"
        params.append(f"%{teacher}%")
    
    query += " ORDER BY sch.date, sch.lesson_number"
    schedule = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('index.html', groups=groups_list, schedule=schedule, date=date, group=group_id, teacher=teacher)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == "admin" and password == "root":  # ТИМЧАСОВИЙ ЛОГІН
            session['admin'] = True
            return redirect(url_for('dashboard'))
        else:
            flash("Неправильний логін або пароль")
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    conn = sqlite3.connect("schedule.db")
    cursor = conn.cursor()
    
    # Отримуємо унікальні дати з розкладу
    cursor.execute("SELECT DISTINCT date FROM schedule ORDER BY date DESC")
    available_dates = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('admin/dashboard.html', available_dates=available_dates)



@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

# Додаємо API для отримання списку дисциплін
@app.route('/get-subjects', methods=['GET'])
def get_subjects():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM subjects")
    subjects = cursor.fetchall()  # Отримуємо предмети

    conn.close()
    return jsonify([{"id": s[0], "name": s[1]} for s in subjects])  # Формуємо JSON

@app.route('/admin/save-schedule', methods=['POST'])
@login_required
def save_schedule():
    data = request.json
    schedule = data.get("schedule")

    if not schedule:
        return jsonify({"error": "Немає даних для збереження"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for entry in schedule:
            group_id = entry["group_id"]
            lesson_number = entry["lesson_number"]
            subject_id = entry["subject_id"]
            date = entry["date"]  # Отримуємо дату

            # Перевіряємо, чи є запис у розкладі
            cursor.execute("""
                SELECT id FROM schedule 
                WHERE group_id = ? AND lesson_number = ? AND date = ?
            """, (group_id, lesson_number, date))
            existing_entry = cursor.fetchone()

            if existing_entry:
                # Оновлюємо запис
                cursor.execute("""
                    UPDATE schedule 
                    SET subject_id = ? 
                    WHERE id = ?
                """, (subject_id, existing_entry["id"]))
            else:
                # Додаємо новий запис
                cursor.execute("""
                    INSERT INTO schedule (group_id, lesson_number, subject_id, date) 
                    VALUES (?, ?, ?, ?)
                """, (group_id, lesson_number, subject_id, date))

        conn.commit()
        return jsonify({"success": True})
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    
    finally:
        conn.close()



@app.route('/admin/get-available-dates', methods=['GET'])
@login_required
def get_available_dates():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT date FROM schedule ORDER BY date DESC")
    available_dates = [row[0] for row in cursor.fetchall()]  # Оновлено!

    conn.close()
    return jsonify(available_dates)


@app.route('/admin/load-schedule', methods=['GET'])
@login_required
def load_schedule():
    date = request.args.get("date")

    if not date:
        return jsonify({"error": "Дата не вказана"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT group_id, lesson_number, subject_id
        FROM schedule
        WHERE date = ?
    """, (date,))

    schedule = [
        {"group_id": row["group_id"], "lesson_number": row["lesson_number"], "subject_id": row["subject_id"]}
        for row in cursor.fetchall()
    ]

    conn.close()
    
    return jsonify({"success": True, "schedule": schedule})



if __name__ == '__main__':
    app.run(debug=True)
