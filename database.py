import sqlite3
import hashlib

def init_db():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()

    # Users: Admin and Teachers
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'teacher'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT UNIQUE NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )''')

    # Link Table for Admin to assign work to Teachers
    c.execute('''CREATE TABLE IF NOT EXISTS teacher_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER,
        class_id INTEGER,
        subject_id INTEGER,
        FOREIGN KEY(teacher_id) REFERENCES users(id),
        FOREIGN KEY(class_id) REFERENCES classes(id),
        FOREIGN KEY(subject_id) REFERENCES subjects(id)
    )''')

    # Existing Student and Attendance logic [cite: 24, 23]
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        roll_no TEXT UNIQUE NOT NULL,
        photo_path TEXT,
        class_id INTEGER NOT NULL,
        FOREIGN KEY(class_id) REFERENCES classes(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        class_id INTEGER,
        date TEXT,
        status TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id),
        FOREIGN KEY(class_id) REFERENCES classes(id))''')

    # Seed Admin Account
    admin_pw = hashlib.sha256("admin123".encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)", 
                  ('Administrator', 'admin@sentinel.edu', admin_pw, 'admin'))
    except sqlite3.IntegrityError: pass

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()