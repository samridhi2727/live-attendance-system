import sqlite3
import hashlib
import os
import uuid
import base64
import numpy as np
import cv2
from datetime import datetime, timedelta
from pathlib import Path
from nicegui import ui, app

# Import the advanced AI model file
import ai_model

# ---------------- SINGLE ADMIN CONFIGURATION ----------------
ADMIN_NAME = "Samridhi"
ADMIN_PASSWORD = "admin123"

# Initialize Cascade Classifier in Main for drawing boxes
face_cascade_main = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# ---------------- GLOBAL UI CONFIGURATION ----------------
# Injecting premium Google Font (Poppins), Custom CSS, and Bulletproof Camera Manager with AR Tracking
ui.add_head_html('''
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
    body { font-family: 'Poppins', sans-serif; }
    .glass-card { background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.6); }
    .glass-dark { background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.1); }
</style>
<script>
    window.appCameraStream = null;

    // Advanced starter with fallback mechanism to guarantee elements are found
    window.startAppCamera = async function(vidId, imgId, overlayId) {
        let video = document.getElementById(vidId);
        
        if (!video) {
            console.warn("Target ID missed. Using fallback query selector.");
            video = document.querySelector('video');
        }

        if (!video) {
            alert("❌ UI Render Error: Camera display area not fully loaded.");
            return;
        }

        let img = imgId ? document.getElementById(imgId) : null;
        let overlay = overlayId ? document.getElementById(overlayId) : null;

        if (img) img.style.display = "none";
        if (overlay) overlay.style.display = "block";
        video.style.display = "block";
        
        // Clear previous tracking canvas if it exists
        let tc = document.getElementById("tracking_canvas");
        if(tc) {
            tc.getContext("2d").clearRect(0, 0, tc.width, tc.height);
        }

        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                alert("❌ Camera API blocked by browser! Please use 'localhost' or 'HTTPS'.");
                return;
            }
            
            // If the stream is already alive, just reuse it for instant switching
            if (window.appCameraStream && window.appCameraStream.active) {
                if (video.srcObject !== window.appCameraStream) {
                    video.srcObject = window.appCameraStream;
                }
                await video.play();
                return;
            }
            
            window.appCameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
            video.srcObject = window.appCameraStream;
            await video.play();
        } catch (e) {
            alert("❌ Camera Access Denied: " + e.message);
        }
    };

    window.captureAppCamera = function(vidId, imgId, overlayId) {
        let v = document.getElementById(vidId) || document.querySelector('video');
        if(!v || !v.srcObject) return null;
        
        let c = document.createElement("canvas");
        c.width = v.videoWidth;
        c.height = v.videoHeight;
        c.getContext("2d").drawImage(v, 0, 0);
        let data = c.toDataURL("image/jpeg");
        
        v.pause(); // Pause hardware instead of killing to prevent flickering
        
        let img = document.getElementById(imgId);
        let overlay = overlayId ? document.getElementById(overlayId) : null;
        let tracking = document.getElementById("tracking_canvas");
        
        if(img) {
            img.src = data;
            img.style.display = "block";
            v.style.display = "none";
        }
        if(overlay) overlay.style.display = "none";
        if(tracking) tracking.getContext("2d").clearRect(0, 0, tracking.width, tracking.height);
        
        return data;
    };

    window.resetAppCamera = function(vidId, imgId, overlayId) {
        let v = document.getElementById(vidId) || document.querySelector('video');
        let i = imgId ? document.getElementById(imgId) : null;
        let o = overlayId ? document.getElementById(overlayId) : null;
        
        if(i) { i.src = ""; i.style.display = "none"; }
        if(o) { o.style.display = "none"; }
        if(v) { 
            v.style.display = "block"; 
            if(v.srcObject) v.play().catch(e=>console.log(e)); 
        }
    };
    
    // Safely stops the camera hardware lock completely
    window.stopAppCamera = function(vidId, imgId, overlayId) {
        if (window.appCameraStream) {
            window.appCameraStream.getTracks().forEach(t => t.stop());
            window.appCameraStream = null;
        }
        
        let v = document.getElementById(vidId) || document.querySelector('video');
        if (v) {
            v.srcObject = null;
            v.style.display = "none";
        }
        
        let i = imgId ? document.getElementById(imgId) : null;
        if (i) i.style.display = "none";
        
        let o = overlayId ? document.getElementById(overlayId) : null;
        if (o) o.style.display = "none";

        let tc = document.getElementById("tracking_canvas");
        if(tc) {
            tc.getContext("2d").clearRect(0, 0, tc.width, tc.height);
        }
    };
    
    // Live Augmented Reality Tracking Drawer (Advanced HUD)
    window.updateTracking = function(x, y, w, h, text) {
        let c = document.getElementById("tracking_canvas");
        let v = document.getElementById("scan_vid_element");
        if(!c || !v || v.style.display === "none" || v.videoWidth === 0) return;
        
        c.width = v.clientWidth;
        c.height = v.clientHeight;
        let ctx = c.getContext("2d");
        ctx.clearRect(0, 0, c.width, c.height);
        
        if(w > 0) {
            // Scale CV coordinate space to native UI dimensions
            let scaleX = c.width / v.videoWidth;
            let scaleY = c.height / v.videoHeight;
            let sx = x * scaleX;
            let sy = y * scaleY;
            let sw = w * scaleX;
            let sh = h * scaleY;
            
            let color = text.includes("Unknown") ? "#ef4444" : "#10b981"; // Red if unknown, Green if match
            
            // 1. Draw High-Tech Reticle Corners
            ctx.strokeStyle = color;
            ctx.lineWidth = 4;
            let len = 25; // Corner line length
            ctx.beginPath();
            // Top-left
            ctx.moveTo(sx, sy + len); ctx.lineTo(sx, sy); ctx.lineTo(sx + len, sy);
            // Top-right
            ctx.moveTo(sx + sw - len, sy); ctx.lineTo(sx + sw, sy); ctx.lineTo(sx + sw, sy + len);
            // Bottom-left
            ctx.moveTo(sx, sy + sh - len); ctx.lineTo(sx, sy + sh); ctx.lineTo(sx + len, sy + sh);
            // Bottom-right
            ctx.moveTo(sx + sw - len, sy + sh); ctx.lineTo(sx + sw, sy + sh); ctx.lineTo(sx + sw, sy + sh - len);
            ctx.stroke();

            // 2. Draw Subtle transparent fill box
            ctx.fillStyle = color + "22"; // Add 20% opacity
            ctx.fillRect(sx, sy, sw, sh);
            
            // 3. Draw Top Label Banner
            ctx.fillStyle = color;
            ctx.font = "bold 16px Poppins, sans-serif";
            let textWidth = ctx.measureText(text).width;
            ctx.fillRect(sx, sy - 34, textWidth + 20, 34);
            
            ctx.fillStyle = "#ffffff";
            ctx.fillText(text, sx + 10, sy - 11);

            // 4. Draw Animated Sweeping Laser inside the box
            let time = Date.now();
            let sweepRatio = (time % 1500) / 1500; // 1.5 second loop
            let laserY = sy + (sweepRatio * sh);
            
            ctx.beginPath();
            ctx.moveTo(sx, laserY);
            ctx.lineTo(sx + sw, laserY);
            ctx.lineWidth = 2;
            ctx.strokeStyle = color;
            ctx.shadowBlur = 15;
            ctx.shadowColor = color;
            ctx.stroke();
            ctx.shadowBlur = 0; // Reset shadow
        }
    };
</script>
''', shared=True)

# ---------------- DATABASE INITIALIZATION ----------------
def init_db():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, date_of_joining TEXT, password TEXT, role TEXT)''')
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN password TEXT")
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, class_id INTEGER)''')
    try:
        c.execute("ALTER TABLE subjects ADD COLUMN class_id INTEGER")
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS teacher_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id INTEGER, class_id INTEGER, subject_id INTEGER,
        FOREIGN KEY(teacher_id) REFERENCES users(id),
        FOREIGN KEY(class_id) REFERENCES classes(id),
        FOREIGN KEY(subject_id) REFERENCES subjects(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, roll_no TEXT, photo_path TEXT, class_id INTEGER,
        FOREIGN KEY(class_id) REFERENCES classes(id),
        UNIQUE(roll_no, class_id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, class_id INTEGER, subject_id INTEGER, date TEXT, time TEXT, status TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id))''')
        
    try:
        c.execute("ALTER TABLE attendance ADD COLUMN subject_id INTEGER")
    except:
        pass

    try:
        c.execute("DELETE FROM users WHERE role='admin'")
    except: pass
    
    conn.commit()
    conn.close()

def db_query(query, args=(), fetch=True):
    with sqlite3.connect('attendance.db') as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, args)
        if fetch: return [dict(row) for row in c.fetchall()]
        conn.commit()
        return True

# ---------------- AUTH LOGIC ----------------
def login(name, secret, required_role):
    if required_role == 'admin':
        if name == ADMIN_NAME and secret == ADMIN_PASSWORD:
            app.storage.user.update({'id': 'admin_master', 'name': ADMIN_NAME, 'role': 'admin'})
            ui.navigate.to('/')
        else:
            ui.notify('Invalid Admin credentials', color='negative', position='top-right')
        return

    if required_role == 'teacher':
        hpw = hashlib.sha256(secret.encode()).hexdigest()
        user = db_query("SELECT * FROM users WHERE name=? AND password=? AND role=?", (name, hpw, required_role))
        if user:
            app.storage.user.update({'id': user[0]['id'], 'name': user[0]['name'], 'role': user[0]['role']})
            ui.navigate.to('/')
        else:
            ui.notify('Invalid Teacher credentials', color='negative', position='top-right')

def update_password(name, old_pw, new_pw):
    if not name or not old_pw or not new_pw:
        ui.notify('All fields are required!', color='negative', position='top-right')
        return
    hpw_old = hashlib.sha256(old_pw.encode()).hexdigest()
    user = db_query("SELECT id FROM users WHERE name=? AND password=? AND role='teacher'", (name, hpw_old))
    
    if user:
        hpw_new = hashlib.sha256(new_pw.encode()).hexdigest()
        db_query("UPDATE users SET password=? WHERE id=?", (hpw_new, user[0]['id']), fetch=False)
        ui.notify('Password updated successfully! Please login.', color='positive', position='top-right')
        ui.navigate.to('/teacher-login')
    else:
        ui.notify('Invalid Teacher Name or Current Password', color='negative', position='top-right')

def admin_add_teacher(name, date_of_joining):
    if not name or not date_of_joining:
        ui.notify('All fields are required!', color='negative', position='top-right')
        return False
    
    default_password = "123456"
    hpw = hashlib.sha256(default_password.encode()).hexdigest()
    
    try:
        db_query("INSERT INTO users (name, date_of_joining, password, role) VALUES (?, ?, ?, 'teacher')", 
                 (name, date_of_joining, hpw), fetch=False)
        ui.notify(f'Teacher {name} added! (Default Password: 123456)', color='positive', position='top-right')
        return True
    except:
        ui.notify('Name already registered', color='negative', position='top-right')
        return False

# ---------------- UI PAGES ----------------
@ui.page('/')
def main_entry():
    if not app.storage.user.get('id'):
        ui.navigate.to('/teacher-login')
        return
    
    role = app.storage.user.get('role')
    if role == 'admin': render_admin()
    else: render_teacher()

@ui.page('/login')
def legacy_login_redirect():
    ui.navigate.to('/teacher-login')

@ui.page('/admin-login')
def admin_login_page():
    ui.query('body').classes('bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 min-h-screen')
    
    with ui.card().classes('absolute-center p-10 w-[420px] rounded-3xl shadow-[0_20px_60px_-15px_rgba(0,0,0,0.7)] glass-dark'):
        ui.label('OptiMark Admin').classes('text-3xl font-black text-center mb-2 text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-300 w-full')
        ui.label('Secure Access Panel').classes('text-sm text-center mb-8 text-slate-400 w-full font-semibold tracking-wider uppercase')
        
        n = ui.input('Administrator Name').classes('w-full mb-2').props('dark')
        p = ui.input('Master Password', password=True).classes('w-full mb-6').props('dark')
        
        ui.button('AUTHENTICATE', on_click=lambda: login(n.value, p.value, 'admin')).classes('w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-xl shadow-lg hover:shadow-indigo-500/50 transition-all duration-300 transform hover:-translate-y-1')
        
        ui.separator().classes('my-6 opacity-30')
        ui.button('Switch to Teacher Portal', on_click=lambda: ui.navigate.to('/teacher-login')).props('flat').classes('w-full text-indigo-300 hover:text-white transition-colors')

@ui.page('/teacher-login')
def teacher_login_page():
    ui.query('body').classes('bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-100 min-h-screen')
    
    with ui.card().classes('absolute-center p-10 w-[420px] rounded-3xl shadow-[0_20px_50px_-12px_rgba(0,0,0,0.15)] glass-card'):
        ui.label('OptiMark AI').classes('text-4xl font-black text-center mb-1 text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600 w-full')
        ui.label('Teacher Portal').classes('text-sm text-center mb-8 text-slate-500 w-full font-semibold tracking-widest uppercase')
        
        n = ui.input('Teacher Full Name').classes('w-full mb-2 text-lg')
        p = ui.input('Password', password=True).classes('w-full mb-6 text-lg')
        
        ui.button('SIGN IN', on_click=lambda: login(n.value, p.value, 'teacher')).classes('w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-bold rounded-xl shadow-lg hover:shadow-indigo-500/40 transition-all duration-300 transform hover:-translate-y-1 tracking-wider')
        ui.button('Change Password?', on_click=lambda: ui.navigate.to('/change-password')).props('flat').classes('w-full mt-2 text-indigo-600 font-medium')
        
        ui.separator().classes('my-6')
        ui.button('Admin Login', icon='admin_panel_settings', on_click=lambda: ui.navigate.to('/admin-login')).props('outline').classes('w-full text-slate-700 border-slate-300 rounded-xl hover:bg-slate-50')

@ui.page('/change-password')
def change_password_page():
    ui.query('body').classes('bg-gradient-to-br from-orange-50 via-rose-50 to-pink-100 min-h-screen')
    
    with ui.card().classes('absolute-center p-10 w-[420px] rounded-3xl shadow-[0_20px_50px_-12px_rgba(0,0,0,0.1)] glass-card'):
        ui.label('Security Update').classes('text-2xl font-black mb-6 text-center w-full text-transparent bg-clip-text bg-gradient-to-r from-orange-600 to-rose-600')
        
        n = ui.input('Teacher Full Name').classes('w-full mb-2')
        op = ui.input('Current Password', password=True).classes('w-full mb-2')
        np_in = ui.input('New Password', password=True).classes('w-full mb-6')
        
        ui.button('UPDATE PASSWORD', on_click=lambda: update_password(n.value, op.value, np_in.value)).classes('w-full py-3 bg-gradient-to-r from-orange-500 to-rose-500 hover:from-orange-600 hover:to-rose-600 text-white font-bold rounded-xl shadow-lg hover:shadow-rose-500/40 transition-all duration-300 transform hover:-translate-y-1')
        ui.button('Back to Login', on_click=lambda: ui.navigate.to('/teacher-login')).props('flat').classes('w-full mt-3 text-rose-600 font-semibold')

# ---------------- ADMIN VIEW ----------------
def render_admin():
    ui.query('body').classes('bg-gradient-to-br from-slate-100 to-slate-200 min-h-screen')
    
    with ui.header().classes('bg-gradient-to-r from-slate-900 to-slate-800 items-center justify-between shadow-lg px-6 py-3'):
        ui.label('OptiMark Control Center').classes('text-2xl font-black tracking-tight text-white')
        ui.button('Secure Logout', icon='logout', on_click=lambda: (app.storage.user.clear(), ui.navigate.to('/admin-login'))).props('flat text-white').classes('font-semibold hover:bg-white/10 rounded-lg')

    with ui.column().classes('w-full max-w-6xl mx-auto p-8'):
        ui.label('Administrative Dashboard').classes('text-4xl font-black mb-6 text-slate-800')
        
        with ui.tabs().classes('w-full bg-white rounded-t-2xl shadow-sm border-b border-slate-200') as tabs:
            t1 = ui.tab('Teacher Assignments').classes('font-semibold tracking-wide')
            t2 = ui.tab('Manage Classes').classes('font-semibold tracking-wide')
            t3 = ui.tab('Manage Teachers').classes('font-semibold tracking-wide')
        
        @ui.refreshable
        def assignment_form():
            with ui.card().classes('p-8 max-w-xl mx-auto shadow-[0_8px_30px_rgb(0,0,0,0.04)] w-full rounded-3xl border border-slate-100 bg-white mt-8'):
                ui.label('Link Teacher to Class & Subject').classes('text-xl font-bold mb-6 text-slate-700 text-center w-full')
                
                teachers = {str(r['id']): r['name'] for r in db_query("SELECT id, name FROM users WHERE role='teacher'")}
                classes = {str(r['id']): r['name'] for r in db_query("SELECT id, name FROM classes")}
                
                t = ui.select(teachers, label='Select Teacher').classes('w-full mb-2').props('outlined')
                c = ui.select(classes, label='Select Class').classes('w-full mb-2').props('outlined')
                s = ui.input('Type Subject Name').classes('w-full mb-6').props('outlined')
                
                def save_assignment():
                    if not t.value or not c.value or not s.value.strip():
                        ui.notify('Please fill all fields', color='warning', position='top')
                        return
                    
                    subject_name = s.value.strip()
                    class_id = c.value
                    
                    existing_subject = db_query("SELECT id FROM subjects WHERE name=? AND class_id=?", (subject_name, class_id))
                    if existing_subject:
                        subject_id = existing_subject[0]['id']
                    else:
                        db_query("INSERT INTO subjects (name, class_id) VALUES (?, ?)", (subject_name, class_id), fetch=False)
                        subject_id = db_query("SELECT id FROM subjects WHERE name=? AND class_id=?", (subject_name, class_id))[0]['id']

                    db_query(
                        "INSERT INTO teacher_assignments (teacher_id, class_id, subject_id) VALUES (?, ?, ?)",
                        (t.value, c.value, subject_id), fetch=False
                    )
                    ui.notify('Assignment Saved Successfully!', color='positive', position='top-right')
                    s.value = '' 
                    
                ui.button('SAVE ASSIGNMENT', on_click=save_assignment).classes('w-full py-3 bg-gradient-to-r from-slate-800 to-slate-700 hover:from-slate-900 hover:to-slate-800 text-white font-bold rounded-xl shadow-lg transition-all duration-300 transform hover:-translate-y-1')

        def delete_class(c_id):
            db_query("DELETE FROM teacher_assignments WHERE class_id=?", (c_id,), fetch=False)
            db_query("DELETE FROM subjects WHERE class_id=?", (c_id,), fetch=False)
            db_query("DELETE FROM classes WHERE id=?", (c_id,), fetch=False)
            ui.notify('Class deleted securely!', color='positive', position='top-right')
            classes_list.refresh()
            assignment_form.refresh()

        def delete_teacher(t_id):
            db_query("DELETE FROM teacher_assignments WHERE teacher_id=?", (t_id,), fetch=False)
            db_query("DELETE FROM users WHERE id=?", (t_id,), fetch=False)
            ui.notify('Teacher profile removed!', color='positive', position='top-right')
            teachers_list.refresh()
            assignment_form.refresh()

        def save_teacher_edit(t_id, new_name, dialog):
            if not new_name.strip():
                ui.notify('Name cannot be empty!', color='negative')
                return
            try:
                db_query("UPDATE users SET name=? WHERE id=?", (new_name.strip(), t_id), fetch=False)
                ui.notify('Teacher name updated successfully!', color='positive')
                dialog.close()
                teachers_list.refresh()
                assignment_form.refresh()
            except:
                ui.notify('Name already exists or invalid!', color='negative')

        def open_edit_teacher_dialog(t_id, current_name):
            with ui.dialog() as dialog, ui.card().classes('p-8 min-w-[350px] rounded-3xl shadow-2xl'):
                ui.label('Edit Teacher Name').classes('text-xl font-bold mb-4 text-slate-800')
                new_name_input = ui.input('Teacher Name', value=current_name).classes('w-full mb-6').props('outlined bg-color="white"')
                with ui.row().classes('w-full justify-end gap-3'):
                    ui.button('Cancel', on_click=dialog.close).props('flat text-slate-500 hover:bg-slate-50 rounded-lg')
                    ui.button('Save', on_click=lambda: save_teacher_edit(t_id, new_name_input.value, dialog)).classes('bg-blue-600 text-white font-bold rounded-lg px-6')
            dialog.open()

        @ui.refreshable
        def classes_list():
            classes_data = db_query("SELECT id, name FROM classes ORDER BY id ASC")
            with ui.card().classes('w-full max-w-3xl mx-auto mt-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-3xl border border-slate-100 p-2'):
                ui.label('Recorded Classes').classes('text-2xl font-bold mb-4 px-4 pt-2 text-slate-800')
                if not classes_data:
                    ui.label('No classes added yet.').classes('text-gray-400 italic px-4 pb-4')
                else:
                    with ui.row().classes('w-full font-black border-b-2 border-slate-100 pb-3 mb-2 text-slate-400 uppercase tracking-wider text-sm px-4'):
                        ui.label('S.No.').classes('w-16')
                        ui.label('Class Name').classes('flex-grow')
                        ui.label('Action').classes('w-24 text-center')
                    for i, c_item in enumerate(classes_data):
                        with ui.row().classes('w-full items-center py-3 px-4 hover:bg-slate-50 rounded-xl transition-colors'):
                            ui.label(str(i + 1)).classes('w-16 text-slate-500 font-bold')
                            ui.label(c_item['name']).classes('flex-grow font-semibold text-lg text-slate-700')
                            ui.button('Delete', on_click=lambda c_id=c_item['id']: delete_class(c_id)).props('dense size=sm outline').classes('w-24 font-bold text-red-500 border-red-200 hover:bg-red-50 rounded-lg')

        @ui.refreshable
        def teachers_list():
            teachers_data = db_query("SELECT id, name, date_of_joining FROM users WHERE role='teacher' ORDER BY id ASC")
            with ui.card().classes('w-full max-w-4xl mx-auto mt-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-3xl border border-slate-100 p-2'):
                ui.label('Registered Teachers').classes('text-2xl font-bold mb-4 px-4 pt-2 text-slate-800')
                if not teachers_data:
                    ui.label('No teachers registered yet.').classes('text-gray-400 italic px-4 pb-4')
                else:
                    with ui.row().classes('w-full font-black border-b-2 border-slate-100 pb-3 mb-2 text-slate-400 uppercase tracking-wider text-sm px-4'):
                        ui.label('S.No.').classes('w-16')
                        ui.label('Teacher Name').classes('flex-grow')
                        ui.label('Join Date').classes('w-32')
                        ui.label('Actions').classes('w-40 text-center')
                    for i, t_item in enumerate(teachers_data):
                        with ui.row().classes('w-full items-center py-3 px-4 hover:bg-slate-50 rounded-xl transition-colors'):
                            ui.label(str(i + 1)).classes('w-16 text-slate-500 font-bold')
                            ui.label(t_item['name']).classes('flex-grow font-semibold text-lg text-slate-700')
                            ui.label(t_item['date_of_joining'] or 'N/A').classes('w-32 text-slate-500')
                            with ui.row().classes('w-40 justify-center gap-2'):
                                ui.button('Edit', on_click=lambda t_id=t_item['id'], name=t_item['name']: open_edit_teacher_dialog(t_id, name)).props('dense size=sm outline').classes('font-bold text-blue-600 border-blue-200 hover:bg-blue-50 rounded-lg px-3')
                                ui.button('Delete', on_click=lambda t_id=t_item['id']: delete_teacher(t_id)).props('dense size=sm outline').classes('font-bold text-red-500 border-red-200 hover:bg-red-50 rounded-lg px-3')

        with ui.tab_panels(tabs, value=t1).classes('w-full bg-transparent p-0').props('keep-alive'):
            with ui.tab_panel(t1):
                assignment_form()

            with ui.tab_panel(t2):
                with ui.column().classes('w-full items-center mt-8'):
                    with ui.card().classes('p-8 max-w-md w-full mx-auto shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-3xl border border-slate-100'):
                        ui.label('Add New Class').classes('text-xl font-bold mb-4 text-center w-full text-slate-800')
                        cl_in = ui.input('Class Name').classes('w-full mb-6').props('outlined')
                        
                        def add_class_action():
                            if not cl_in.value: return
                            try:
                                db_query("INSERT INTO classes (name) VALUES (?)", (cl_in.value,), fetch=False)
                                ui.notify(f"Class '{cl_in.value}' added successfully!", color='positive')
                                cl_in.value = ''
                                assignment_form.refresh() 
                                classes_list.refresh()
                            except:
                                ui.notify('Class already exists!', color='negative')
                                
                        ui.button('ADD CLASS', on_click=add_class_action).classes('w-full py-3 bg-gradient-to-r from-blue-600 to-blue-500 text-white font-bold rounded-xl shadow-lg hover:shadow-blue-500/40 transition-all transform hover:-translate-y-1')
                    
                    classes_list()

            with ui.tab_panel(t3):
                with ui.column().classes('w-full items-center mt-8'):
                    with ui.card().classes('p-8 max-w-md w-full mx-auto shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-3xl border border-slate-100'):
                        ui.label('Register New Teacher').classes('text-xl font-bold mb-4 text-center w-full text-slate-800')
                        t_n = ui.input('Teacher Full Name').classes('w-full mb-2').props('outlined')
                        t_d = ui.input('Date of Joining').props('type=date outlined').classes('w-full mb-4')
                        ui.label('Default Password is auto-set to: 123456').classes('text-xs text-slate-400 font-medium w-full text-center mb-4')
                        
                        def _add_teacher_action():
                            if admin_add_teacher(t_n.value, t_d.value):
                                t_n.value, t_d.value = '' , ''
                                assignment_form.refresh() 
                                teachers_list.refresh()
                            
                        ui.button('ADD TEACHER', on_click=_add_teacher_action).classes('w-full py-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-bold rounded-xl shadow-lg hover:shadow-emerald-500/40 transition-all transform hover:-translate-y-1')
                    
                    teachers_list()

# ---------------- TEACHER VIEW ----------------
def render_teacher():
    ui.query('body').classes('bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-100 via-indigo-50 to-purple-100 min-h-screen')
    
    t_id, t_name = app.storage.user['id'], app.storage.user['name']
    
    with ui.header().classes('bg-gradient-to-r from-blue-700 via-indigo-700 to-purple-800 items-center justify-between shadow-xl px-6 py-3'):
        with ui.row().classes('items-center gap-3'):
            ui.icon('face_retouching_natural', size='sm').classes('text-white/80')
            ui.label(f'OptiMark AI').classes('text-2xl font-black tracking-tight text-white')
        ui.button('Logout', icon='logout', on_click=lambda: (app.storage.user.clear(), ui.navigate.to('/teacher-login'))).props('flat text-white').classes('font-semibold hover:bg-white/10 rounded-lg')

    with ui.column().classes('w-full max-w-6xl mx-auto p-8'):
        ui.label(f"Welcome, Professor {t_name.split()[0]}!").classes('text-5xl font-black mb-2 text-transparent bg-clip-text bg-gradient-to-r from-blue-700 to-indigo-600')
        ui.label('Select a class module to begin session.').classes('text-lg text-slate-500 font-medium mb-8')
        
        assigns = db_query("""
            SELECT c.id as cid, c.name as cname, s.id as sid, s.name as sname FROM teacher_assignments ta
            JOIN classes c ON ta.class_id = c.id
            JOIN subjects s ON ta.subject_id = s.id
            WHERE ta.teacher_id = ?
        """, (t_id,))
        
        ui.label('Your Assigned Modules').classes('text-sm font-bold tracking-widest uppercase text-indigo-400 mb-2')
        
        ui_state = {}
        def go_to_manage(cid):
            tabs.value = t_mng
            if ui_state.get('mng_select'):
                ui_state['mng_select'].value = str(cid)

        with ui.row().classes('w-full gap-6 mb-8'):
            if not assigns:
                ui.label('No classes assigned yet. Please contact the Administrator.').classes('text-slate-400 italic px-2 p-4 bg-white rounded-2xl border border-slate-100 w-full')
            for row in assigns:
                with ui.card().classes('p-6 bg-white/80 backdrop-blur-md border-l-8 border-indigo-500 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl min-w-[240px] cursor-pointer hover:shadow-xl hover:-translate-y-1.5 transition-all duration-300 ring-1 ring-slate-100').on('click', lambda e, cid=row['cid']: go_to_manage(cid)):
                    ui.label(f"{row['cname']}").classes('font-black text-3xl text-slate-800 pointer-events-none tracking-tight')
                    ui.label(f"Course: {row['sname']}").classes('text-indigo-600 font-semibold mt-1 pointer-events-none')

        with ui.tabs().classes('w-full bg-white/60 backdrop-blur-md rounded-2xl shadow-sm border border-slate-100 p-1') as tabs:
            t_stu = ui.tab('👥 Register').classes('font-bold tracking-wide rounded-xl')
            t_mng = ui.tab('📋 Roster').classes('font-bold tracking-wide rounded-xl')
            t_att = ui.tab('📷 Live AI Scanner').classes('font-bold tracking-wide rounded-xl text-blue-600')
            t_rep = ui.tab('📊 Analytics').classes('font-bold tracking-wide rounded-xl')
            t_perc = ui.tab('💯 Percentage').classes('font-bold tracking-wide rounded-xl text-emerald-600')

        # CRITICAL FIX: keep_alive=True ensures the camera DOM elements aren't destroyed on tab switch
        with ui.tab_panels(tabs, value=t_stu).classes('w-full bg-transparent p-0 mt-6').props('keep-alive'):
            with ui.tab_panel(t_stu):
                render_student_mgmt(assigns)
            with ui.tab_panel(t_mng):
                ui_state['mng_select'] = render_student_manager(assigns)
            with ui.tab_panel(t_att):
                render_live_scanner(assigns)
            with ui.tab_panel(t_rep):
                render_reports(assigns)
            with ui.tab_panel(t_perc):
                render_percentage(assigns)

# ---------------- AI INTEGRATED CORE LOGIC ----------------
def save_student(name, roll, cid, photo, clear_form_callback):
    if not name:
        ui.notify('Please enter the Student Full Name.', color='negative')
        return
    if not roll:
        ui.notify('Please enter the Roll Number.', color='negative')
        return
    if not cid:
        ui.notify('Please select a Class from the dropdown.', color='negative')
        return
    if not photo.get('content'):
        ui.notify('Please upload or capture a Student Photo.', color='warning')
        return
        
    # --- STRICT FACE VALIDATION ---
    nparr = np.frombuffer(photo['content'], np.uint8)
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    img_cv = cv2.equalizeHist(img_cv) # Normalize lighting for strict detection
    faces = face_cascade_main.detectMultiScale(img_cv, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    
    if len(faces) == 0:
        ui.notify('Registration Failed: No human face detected! Ensure good lighting and look directly at the camera.', color='negative', position='top', timeout=5000)
        return
    if len(faces) > 1:
        ui.notify('Registration Failed: Multiple faces detected! Only one person should be in the frame.', color='negative', position='top', timeout=5000)
        return
    # ------------------------------
    
    existing_student = db_query("SELECT id FROM students WHERE roll_no=? AND class_id=?", (roll, cid))
    if existing_student:
        ui.notify(f'Error: Roll Number {roll} is already registered in this class!', color='negative')
        return
        
    is_duplicate, duplicate_id = ai_model.check_duplicate_face(photo['content'], cid)
    if is_duplicate:
        dup_student = db_query("SELECT name, roll_no FROM students WHERE id=?", (duplicate_id,))
        if dup_student:
            dup_name = dup_student[0]['name']
            dup_roll = dup_student[0]['roll_no']
            ui.notify(f"Registration Failed: Face already registered to {dup_name} ({dup_roll})!", color='negative', timeout=6000)
        else:
            ui.notify("Registration Failed: Face already registered!", color='negative')
        return
    
    try:
        db_query("INSERT INTO students (name, roll_no, photo_path, class_id) VALUES (?, ?, ?, ?)", (name, roll, "", cid), fetch=False)
        student_id = db_query("SELECT id FROM students WHERE roll_no=? AND class_id=?", (roll, cid))[0]['id']
        
        os.makedirs('student_images', exist_ok=True)
        path = f"student_images/{cid}_{roll}.jpg"
        with open(path, 'wb') as f: f.write(photo['content'])
        
        db_query("UPDATE students SET photo_path=? WHERE id=?", (path, student_id), fetch=False)
        
        students_in_class = db_query("SELECT id, photo_path FROM students WHERE class_id=?", (cid,))
        try:
            success = ai_model.train_class_model(cid, students_in_class)
            if not success:
                raise Exception("Failed to compile face features.")
        except Exception as e:
            db_query("DELETE FROM students WHERE id=?", (student_id,), fetch=False)
            if os.path.exists(path): os.remove(path)
            
            if isinstance(e, AttributeError) or 'cv2.face' in str(e):
                ui.notify('Setup Error: "opencv-contrib-python" missing!', color='negative', timeout=6000)
            else:
                ui.notify(f'AI Error: {e}', color='negative')
            return
        
        ui.notify(f'✨ {name} successfully registered and AI Trained!', color='positive')
        clear_form_callback() 
    except Exception as e:
        ui.notify(f"Database Error: {e}", color='negative')

def render_student_mgmt(assigns):
    photo_state = {'content': None}
    
    # Extract unique classes for registration dropdown
    c_opts = {str(a['cid']): a['cname'] for a in assigns}
    
    with ui.row().classes('w-full justify-center p-6'):
        with ui.card().classes('p-8 w-full max-w-xl shadow-[0_20px_50px_-12px_rgba(0,0,0,0.1)] rounded-3xl border border-white bg-white/90 backdrop-blur-sm'):
            ui.label('Onboard New Student').classes('text-3xl font-black mb-6 text-slate-800 text-center w-full tracking-tight')
            
            n = ui.input('Student Full Name').classes('w-full mb-3 text-lg').props('outlined bg-color="white"')
            r = ui.input('Roll Number (Unique per class)').classes('w-full mb-3 text-lg').props('outlined bg-color="white"')
            c_sel = ui.select(c_opts, label='Assign to Class').classes('w-full mb-6 text-lg font-medium').props('outlined bg-color="white"')
            
            ui.label('Biometric Profile Photo').classes('text-sm font-bold text-slate-400 uppercase tracking-widest mb-2')
            
            with ui.tabs().classes('w-full bg-slate-100 rounded-xl p-1 mb-2') as photo_tabs:
                tab_upload = ui.tab('Upload Image').classes('font-semibold rounded-lg')
                tab_camera = ui.tab('Live WebCam').classes('font-semibold rounded-lg')
                
            with ui.tab_panels(photo_tabs, value=tab_camera).classes('w-full p-0 bg-transparent mb-6'):
                with ui.tab_panel(tab_upload):
                    async def handle_upload(e):
                        try:
                            if hasattr(e, 'content'):
                                raw_bytes = await e.content.read()
                            elif hasattr(e, 'file'):
                                raw_bytes = await e.file.read()
                            elif hasattr(e, 'stream'):
                                raw_bytes = await e.stream.read()
                            else:
                                ui.notify('File read error.', color='negative')
                                return
                            
                            nparr = np.frombuffer(raw_bytes, np.uint8)
                            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            if img is not None:
                                # --- UPLOAD STRICT FACE CHECK ---
                                img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                                img_gray = cv2.equalizeHist(img_gray)
                                faces = face_cascade_main.detectMultiScale(img_gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
                                
                                if len(faces) == 0:
                                    ui.notify('⚠️ Upload Rejected: No clear face detected in the image!', color='negative', position='top')
                                    upload_element.reset()
                                    return
                                if len(faces) > 1:
                                    ui.notify('⚠️ Upload Rejected: Multiple faces detected! Please use a single portrait.', color='negative', position='top')
                                    upload_element.reset()
                                    return
                                # --------------------------------
                                
                                max_dim = 800
                                h, w = img.shape[:2]
                                if max(h, w) > max_dim:
                                    scale = max_dim / max(h, w)
                                    img = cv2.resize(img, (int(w * scale), int(h * scale)))
                                _, enc_img = cv2.imencode('.jpg', img)
                                photo_state['content'] = enc_img.tobytes()
                            else:
                                photo_state['content'] = raw_bytes
                                
                            ui.notify('Valid photo attached!', color='positive')
                        except Exception as ex:
                            ui.notify(f'Upload Error: {ex}', color='negative')
                        
                    upload_element = ui.upload(on_upload=handle_upload, label='Drag & Drop Photo', auto_upload=True).classes('w-full border-2 border-dashed border-slate-300 rounded-2xl p-4 bg-slate-50')
                              
                with ui.tab_panel(tab_camera):
                    def start_cam():
                        photo_state['content'] = None
                        ui.run_javascript('window.startAppCamera("reg_vid_element", "reg_img_element", null);')
                        
                    def stop_cam():
                        ui.run_javascript('window.stopAppCamera("reg_vid_element", "reg_img_element", null);')
                        photo_state['content'] = None
                        ui.notify('Camera turned off.', color='info')

                    with ui.row().classes('w-full gap-2 mb-3'):
                        ui.button('Turn On Camera', icon='videocam', on_click=start_cam).classes('flex-1 bg-slate-700 hover:bg-slate-800 text-white font-bold rounded-xl py-2 shadow-md transition-colors')
                        ui.button('Turn Off', icon='videocam_off', on_click=stop_cam).classes('bg-red-600 hover:bg-red-700 text-white font-bold rounded-xl py-2 shadow-md transition-colors')
                    
                    with ui.card().classes('p-1 bg-slate-900 shadow-inner rounded-2xl overflow-hidden mb-3 flex items-center justify-center w-full min-h-[280px] border border-slate-700 relative'):
                        # Using Native NiceGUI UI elements instead of raw HTML to fix DOM loss
                        ui.element('video').props('autoplay playsinline id="reg_vid_element"').classes('w-full h-full absolute inset-0 object-cover rounded-xl')
                        ui.element('img').props('id="reg_img_element"').classes('w-full h-full absolute inset-0 object-cover rounded-xl').style('display: none;')
                    
                    async def capture_photo():
                        img_b64 = await ui.run_javascript('return window.captureAppCamera("reg_vid_element", "reg_img_element", null);')
                        if img_b64:
                            encoded = img_b64.split(',')[1]
                            raw_bytes = base64.b64decode(encoded)
                            
                            # --- LIVE SNAPSHOT STRICT FACE CHECK ---
                            nparr = np.frombuffer(raw_bytes, np.uint8)
                            img_cv = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
                            img_cv = cv2.equalizeHist(img_cv)
                            faces = face_cascade_main.detectMultiScale(img_cv, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
                            
                            if len(faces) == 0:
                                ui.notify('⚠️ No face detected! Please look at the camera and try again.', color='warning', position='top')
                                photo_state['content'] = None
                                ui.run_javascript('window.resetAppCamera("reg_vid_element", "reg_img_element", null);')
                                return
                            if len(faces) > 1:
                                ui.notify('⚠️ Multiple faces detected! Please ensure only one person is in frame.', color='warning', position='top')
                                photo_state['content'] = None
                                ui.run_javascript('window.resetAppCamera("reg_vid_element", "reg_img_element", null);')
                                return
                            # ---------------------------------------
                            
                            photo_state['content'] = raw_bytes
                            ui.notify('📸 Valid Face Captured successfully!', color='positive', position='top')
                        else:
                            ui.notify('Error: Turn on camera first.', color='warning')
                            
                    ui.button('Snap Photo', icon='camera', on_click=capture_photo).classes('w-full bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded-xl py-2 shadow-sm transition-colors')

            def clear_form():
                n.value = ''
                r.value = ''
                c_sel.value = None
                photo_state['content'] = None
                upload_element.reset()
                ui.run_javascript('window.resetAppCamera("reg_vid_element", "reg_img_element", null);')

            with ui.row().classes('w-full gap-3 mt-2'):
                ui.button('Reset', icon='restart_alt', on_click=clear_form).classes('w-1/3 bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold py-3 rounded-xl shadow-sm transition-colors')
                ui.button('Complete Registration', icon='how_to_reg', on_click=lambda: save_student(n.value, r.value, c_sel.value, photo_state, clear_form)).classes('flex-grow bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold py-3 rounded-xl shadow-lg hover:shadow-indigo-500/40 transform hover:-translate-y-1 transition-all duration-300')

def render_student_manager(assigns):
    if not assigns:
        ui.label('No assigned classes available.').classes('p-6 italic text-slate-400')
        return None

    # Classes are unique in this dropdown for editing the roster
    c_opts = {str(a['cid']): a['cname'] for a in assigns}
    
    with ui.column().classes('w-full items-center p-2 pb-12'):
        sel_class = ui.select(c_opts, label='Filter by Class Roster', on_change=lambda e: students_table.refresh(e.value)).classes('w-80 mb-6 font-medium text-lg').props('outlined bg-color="white" color="indigo-600"')
        
        def delete_student(s_id, cid, photo_path):
            db_query("DELETE FROM attendance WHERE student_id=?", (s_id,), fetch=False)
            db_query("DELETE FROM students WHERE id=?", (s_id,), fetch=False)
            
            if photo_path and os.path.exists(photo_path):
                try: os.remove(photo_path)
                except: pass
            
            ui.notify('Student profile removed permanently.', color='positive')
            
            students_in_class = db_query("SELECT id, photo_path FROM students WHERE class_id=?", (cid,))
            if students_in_class:
                try: ai_model.train_class_model(cid, students_in_class)
                except: pass
            else:
                model_path = f'models/class_{cid}.yml'
                if os.path.exists(model_path):
                    try: os.remove(model_path)
                    except: pass
                    
            students_table.refresh(cid)

        def save_student_edit(s_id, old_roll, new_name, new_roll, cid, old_photo_path, dialog):
            if not new_name.strip() or not new_roll.strip():
                ui.notify('Name and Roll Number cannot be empty!', color='negative')
                return
            
            if old_roll != new_roll:
                existing = db_query("SELECT id FROM students WHERE roll_no=? AND class_id=?", (new_roll, cid))
                if existing:
                    ui.notify(f'Roll Number {new_roll} is already registered!', color='negative')
                    return
            
            new_photo_path = old_photo_path
            if old_roll != new_roll and old_photo_path and os.path.exists(old_photo_path):
                new_photo_path = f"student_images/{cid}_{new_roll}.jpg"
                try:
                    os.rename(old_photo_path, new_photo_path)
                except Exception:
                    new_photo_path = old_photo_path 
            
            db_query("UPDATE students SET name=?, roll_no=?, photo_path=? WHERE id=?", 
                     (new_name.strip(), new_roll.strip(), new_photo_path, s_id), fetch=False)
            
            ui.notify('Student details synced!', color='positive')
            dialog.close()
            students_table.refresh(cid)

        def open_edit_dialog(s_id, current_name, current_roll, cid, photo_path):
            with ui.dialog() as dialog, ui.card().classes('p-8 min-w-[350px] rounded-3xl shadow-2xl'):
                ui.label('Edit Identity Data').classes('text-xl font-bold mb-4 text-slate-800')
                new_name_input = ui.input('Student Name', value=current_name).classes('w-full mb-3').props('outlined bg-color="white"')
                new_roll_input = ui.input('Roll Number', value=current_roll).classes('w-full mb-6').props('outlined bg-color="white"')
                with ui.row().classes('w-full justify-end gap-3'):
                    ui.button('Cancel', on_click=dialog.close).props('flat text-slate-500 hover:bg-slate-50 rounded-lg')
                    ui.button('Save Changes', on_click=lambda: save_student_edit(s_id, current_roll, new_name_input.value, new_roll_input.value, cid, photo_path, dialog)).classes('bg-blue-600 text-white font-bold rounded-lg px-6')
            dialog.open()

        @ui.refreshable
        def students_table(class_id):
            if not class_id:
                with ui.card().classes('w-full max-w-4xl shadow-sm border border-slate-200 bg-white/50 backdrop-blur-sm rounded-3xl p-12 flex items-center justify-center'):
                    ui.label('Select a class module from the dropdown to view enrolled students.').classes('text-slate-400 font-medium text-lg')
                return
            
            students_data = db_query("SELECT id, name, roll_no, photo_path FROM students WHERE class_id=? ORDER BY roll_no ASC", (class_id,))
            
            with ui.card().classes('w-full max-w-4xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] bg-white rounded-3xl border border-slate-100 p-2'):
                if not students_data:
                    ui.label('Roster is empty. Register students first.').classes('text-slate-400 italic p-6')
                else:
                    with ui.row().classes('w-full font-black border-b-2 border-slate-100 pb-3 mb-2 pt-2 px-4 text-slate-400 uppercase tracking-wider text-sm'):
                        ui.label('S.No.').classes('w-16')
                        ui.label('Roll No.').classes('w-32')
                        ui.label('Student Name').classes('flex-grow')
                        ui.label('Actions').classes('w-40 text-center')
                    
                    for i, s in enumerate(students_data):
                        with ui.row().classes('w-full items-center border-b border-slate-50 py-3 px-4 hover:bg-blue-50/50 rounded-xl transition-colors'):
                            ui.label(str(i + 1)).classes('w-16 text-slate-400 font-bold')
                            ui.label(s['roll_no']).classes('w-32 font-mono font-bold text-blue-600')
                            ui.label(s['name']).classes('flex-grow font-semibold text-lg text-slate-700')
                            with ui.row().classes('w-40 justify-center gap-2'):
                                ui.button('Edit', on_click=lambda s_id=s['id'], name=s['name'], roll=s['roll_no'], cid=class_id, p=s['photo_path']: open_edit_dialog(s_id, name, roll, cid, p)).props('dense size=sm outline').classes('font-bold text-blue-600 border-blue-200 hover:bg-blue-100 rounded-lg px-3')
                                ui.button('Delete', on_click=lambda s_id=s['id'], cid=class_id, p=s['photo_path']: delete_student(s_id, cid, p)).props('dense size=sm outline').classes('font-bold text-red-500 border-red-200 hover:bg-red-100 rounded-lg px-3')
        
        students_table(sel_class.value)
        return sel_class

def render_live_scanner(assigns):
    att_opts = {f"{a['cid']}_{a['sid']}": f"{a['cname']} | {a['sname']}" for a in assigns}
    
    # State tracking to avoid overlapping processing during continuous AR overlay mode
    tracking_state = {'is_processing': False}
    
    def start_att_cam(e=None):
        if e is not None and hasattr(e, 'value') and not e.value: 
            return 
        ui.run_javascript('window.startAppCamera("scan_vid_element", "scan_img_element", "scan_overlay_element");')
        
    def stop_att_cam():
        ui.run_javascript('window.stopAppCamera("scan_vid_element", "scan_img_element", "scan_overlay_element");')
        ui.notify('Camera turned off.', color='info')
    
    # LIVE AR OVERLAY: Continuously runs every 0.4 seconds while camera is active
    async def live_tracking():
        if not sel.value: return
        if tracking_state.get('is_processing'): return
        
        tracking_state['is_processing'] = True
        try:
            img_b64 = await ui.run_javascript('''
                var v = document.getElementById("scan_vid_element"); 
                if(!v || !v.srcObject || v.paused || v.videoWidth === 0 || v.style.display === "none") return null; 
                var c = document.createElement("canvas"); 
                c.width = v.videoWidth; 
                c.height = v.videoHeight; 
                c.getContext("2d").drawImage(v,0,0); 
                return c.toDataURL("image/jpeg", 0.6); // Slightly lower quality for speedy live processing
            ''')
            if img_b64:
                cid_str, sid_str = sel.value.split('_')
                class_id = int(cid_str)
                
                # Perform rapid Face Detection first
                encoded_data = img_b64.split(',')[1]
                nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                faces = face_cascade_main.detectMultiScale(img_gray, scaleFactor=1.1, minNeighbors=4, minSize=(50, 50))
                
                if len(faces) > 0:
                    (x, y, w, h) = faces[0]
                    # If face found, attempt to recognize the identity
                    status, student_id, conf = ai_model.recognize_student(img_b64, class_id)
                    if status == "SUCCESS" and student_id:
                        s = db_query("SELECT name, roll_no FROM students WHERE id=?", (student_id,))[0]
                        text = f"{s['roll_no']} - {s['name']}"
                        ui.run_javascript(f'window.updateTracking({x}, {y}, {w}, {h}, "{text}");')
                    else:
                        ui.run_javascript(f'window.updateTracking({x}, {y}, {w}, {h}, "Unknown Person");')
                else:
                    ui.run_javascript('window.updateTracking(0,0,0,0,"");') # Clear overlay if no face
        except Exception as e:
            pass
        finally:
            tracking_state['is_processing'] = False

    # Start the continuous tracking timer with faster refresh
    ui.timer(0.4, live_tracking)
            
    def process_ai_scan(img_b64, composite_id):
        if not composite_id:
            ui.notify('Select an active session first!', color='warning')
            start_att_cam()
            return

        cid_str, sid_str = composite_id.split('_')
        class_id = int(cid_str)
        subject_id = int(sid_str)

        status, student_id, conf = ai_model.recognize_student(img_b64, class_id)
        
        if status == "SUCCESS" and student_id:
            student_info = db_query("SELECT id, name, roll_no FROM students WHERE id=?", (student_id,))
            if student_info:
                s = student_info[0]
                
                # --- 50-MINUTE COOLDOWN CHECK ---
                now = datetime.now()
                current_date = now.strftime('%Y-%m-%d')
                last_record = db_query("SELECT time FROM attendance WHERE student_id=? AND class_id=? AND subject_id=? AND date=? ORDER BY id DESC LIMIT 1", 
                                       (s['id'], class_id, subject_id, current_date))
                
                if last_record:
                    last_time_str = last_record[0]['time']
                    last_time = datetime.strptime(last_time_str, '%H:%M').time()
                    last_dt = datetime.combine(now.date(), last_time)
                    time_diff = (now - last_dt).total_seconds() / 60.0
                    
                    if time_diff < 50:
                        ui.notify(f"⏳ {s['name']} (Roll: {s['roll_no']}) was marked present {int(time_diff)} mins ago. (Cooldown: 50m)", color='warning', position='top')
                        ui.timer(2.0, start_att_cam, once=True) # Auto-restart smoothly
                        return
                # --------------------------------
                
                try:
                    # Draw a beautiful Overlay frame with OpenCV on the frozen snapshot
                    encoded_data = img_b64.split(',')[1]
                    nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    
                    faces = face_cascade_main.detectMultiScale(img_gray, scaleFactor=1.1, minNeighbors=4, minSize=(50, 50))
                    
                    for (x, y, w, h) in faces:
                        cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 3)
                        text = f"{s['roll_no']} - {s['name']}"
                        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)
                        cv2.rectangle(img, (x, y - 35), (x + tw + 10, y), (0, 255, 0), cv2.FILLED)
                        cv2.putText(img, text, (x + 5, y - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 0), 2)
                        break 
                        
                    _, buffer = cv2.imencode('.jpg', img)
                    drawn_b64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode('utf-8')
                    ui.run_javascript(f'document.getElementById("scan_img_element").src = "{drawn_b64}";')
                except Exception as e:
                    print(f"Error drawing overlay: {e}")
                
                show_confirmation_dialog(s['id'], s['name'], s['roll_no'], class_id, subject_id)
        else:
            if status == "NO_MODEL":
                ui.notify("❌ Class AI Model empty! Register students first.", color='warning')
            elif status == "NO_FACE":
                ui.notify("❌ No face detected. Ensure the student is looking at the camera.", color='negative')
            elif status == "UNKNOWN":
                ui.notify("❌ Identity Unverified (Low confidence or unregistered face).", color='negative')
            elif status == "MISSING_MODULE":
                ui.notify('❌ System Error: "opencv-contrib-python" not found.', color='negative')
            else:
                ui.notify(f"❌ AI Error: {status}", color='negative')
            
            # AUTOMATIC RESTART: Seamlessly resume scanning after a failure!    
            ui.timer(2.0, start_att_cam, once=True)

    def show_confirmation_dialog(sid, name, roll, cid, subject_id):
        with ui.dialog() as dialog, ui.card().classes('p-8 text-center shadow-2xl rounded-3xl min-w-[320px]'):
            ui.icon('verified_user', size='lg', color='green-500').classes('mb-2 w-full flex justify-center')
            ui.label("Biometric Match!").classes('text-2xl font-black text-green-600 mb-4 tracking-tight w-full')
            
            with ui.column().classes('w-full bg-slate-50 rounded-xl p-4 mb-6 border border-slate-100'):
                ui.label(f"{name}").classes('text-xl font-bold text-slate-800 w-full')
                ui.label(f"Roll No: {roll}").classes('text-md text-blue-600 font-mono font-bold w-full')
            
            ui.label("Log this presence record?").classes('mb-6 font-semibold text-slate-500 w-full')
            
            def close_and_restart():
                dialog.close()
                # AUTOMATIC RESTART: Seamlessly resume scanning after dismissing prompt!
                ui.timer(0.5, start_att_cam, once=True)
                
            def mark_present():
                now = datetime.now()
                # Pass both class_id AND subject_id to ensure attendance is specific to this session
                db_query("INSERT INTO attendance (student_id, class_id, subject_id, date, time, status) VALUES (?, ?, ?, ?, ?, ?)",
                         (sid, cid, subject_id, now.strftime('%Y-%m-%d'), now.strftime('%H:%M'), 'Present'), fetch=False)
                ui.notify(f'✅ {name} logged as Present!', color='positive', position='top')
                close_and_restart()

            with ui.row().classes('justify-center w-full gap-3'):
                ui.button("✖ REJECT", on_click=close_and_restart).classes('bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold rounded-xl py-3 px-6')
                ui.button("✔ CONFIRM", on_click=mark_present).classes('bg-green-500 hover:bg-green-600 text-white font-bold rounded-xl py-3 px-6 shadow-lg hover:shadow-green-500/40 transform hover:scale-105 transition-all')
                
        dialog.open()

    with ui.column().classes('w-full items-center p-6 pb-12'):
        ui.label('Live AI Authentication').classes('text-3xl font-black mb-2 text-slate-800 tracking-tight')
        ui.label('Face the camera to log attendance').classes('text-slate-400 font-medium mb-4')
        
        clock_label = ui.label().classes('text-lg font-bold text-indigo-700 bg-indigo-50/80 px-6 py-2 rounded-2xl border border-indigo-100 shadow-sm mb-6 tracking-wide')
        def update_clock():
            clock_label.set_text(datetime.now().strftime("%A, %B %d, %Y | %I:%M:%S %p"))
        update_clock()
        ui.timer(1.0, update_clock)
        
        sel = ui.select(att_opts, label='Select Active Session', on_change=start_att_cam).classes('w-80 mb-8 font-medium text-lg').props('outlined bg-color="white" color="indigo-600"')
        
        with ui.card().classes('p-3 bg-slate-900 shadow-[0_0_50px_rgba(59,130,246,0.15)] rounded-[2rem] overflow-hidden flex items-center justify-center w-full max-w-2xl min-h-[400px] mx-auto border border-slate-700 relative ring-4 ring-slate-800/50'):
            ui.element('video').props('autoplay playsinline id="scan_vid_element"').classes('w-full h-full absolute inset-0 object-cover rounded-[24px]')
            
            # The new Transparent HTML5 Canvas overlaid specifically for Live AR CV Tracking
            ui.html('<canvas id="tracking_canvas" style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:20;"></canvas>')
            
            ui.element('img').props('id="scan_img_element"').classes('w-full h-full absolute inset-0 object-cover rounded-[24px] z-15').style('display: none;')
            
            ui.html('''
                <div id="scan_overlay_element" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:10;">
                    <div style="position:absolute; width:100%; height:100%; border: 4px solid rgba(59,130,246,0.3); border-radius: 24px; box-shadow: inset 0 0 30px rgba(59,130,246,0.2);"></div>
                    <div style="position:absolute; width:100%; height:3px; background:rgba(59,130,246,0.9); box-shadow:0 0 15px #3b82f6; top:0; animation: full_scan 3s infinite linear;"></div>
                </div>
                <style>@keyframes full_scan { 0% {top:0%; opacity:0;} 10% {opacity:1;} 90% {opacity:1;} 100% {top:100%; opacity:0;} }</style>
            ''').classes('w-full h-full absolute inset-0 pointer-events-none z-10')
            
        with ui.row().classes('w-full max-w-2xl mt-6 gap-4'):
            
            async def capture_and_scan():
                if not sel.value:
                    ui.notify('Select an active session first!', color='warning')
                    return
                img_b64 = await ui.run_javascript('return window.captureAppCamera("scan_vid_element", "scan_img_element", "scan_overlay_element");')
                
                if img_b64:
                    process_ai_scan(img_b64, sel.value)
                else:
                    ui.notify('Lens not initialized.', color='negative')
            
            ui.button('START', icon='play_arrow', on_click=start_att_cam).classes('flex-1 h-14 text-md bg-slate-800 hover:bg-slate-700 rounded-2xl font-bold text-white shadow-lg transition-colors')
            ui.button('STOP', icon='stop', on_click=stop_att_cam).classes('flex-1 h-14 text-md bg-red-600 hover:bg-red-700 rounded-2xl font-bold text-white shadow-lg transition-colors')
            ui.button('AUTHENTICATE FACE', icon='document_scanner', on_click=capture_and_scan).classes('flex-[2] h-14 text-lg bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 rounded-2xl font-black shadow-xl hover:shadow-blue-500/40 text-white tracking-widest transform hover:-translate-y-1 transition-all duration-300')

def render_reports(assigns):
    if not assigns:
        ui.label('No assigned classes to show reports for.').classes('p-6 italic text-slate-500')
        return

    with ui.column().classes('w-full items-center p-6 pb-12'):
        ui.label('Statistical Analytics').classes('text-3xl font-black mb-6 text-slate-800 tracking-tight w-full max-w-5xl')
        
        for a in assigns:
            with ui.expansion(f"{a['cname']} | {a['sname']}", icon='pie_chart').classes('w-full max-w-5xl bg-white shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 rounded-2xl mb-4 text-lg font-bold text-slate-700'):
                
                state = {
                    'period': 'Specific Date',
                    'date': datetime.now().strftime('%Y-%m-%d')
                }
                
                content_container = ui.column().classes('w-full p-4 font-normal text-base')
                
                def build_ui(cid=a['cid'], sid=a['sid'], s_dict=state, container=content_container):
                    container.clear()
                    with container:
                        with ui.row().classes('w-full items-center gap-4 mb-6 bg-slate-50/50 p-4 rounded-xl border border-slate-100'):
                            p_sel = ui.select(['Specific Date', 'Weekly', 'Monthly', 'Quarterly', '6-Monthly'], 
                                              label='Select Timeframe', value=s_dict['period'], 
                                              on_change=lambda e: s_dict.update({'period': e.value})).classes('w-48').props('outlined bg-color="white"')
                            
                            d_sel = ui.input('Select Date', value=s_dict['date'], 
                                             on_change=lambda e: s_dict.update({'date': e.value})).props('type=date outlined bg-color="white"').classes('w-48')
                            d_sel.bind_visibility_from(p_sel, 'value', backward=lambda v: v == 'Specific Date')
                            
                            ui.button('FETCH DATA', icon='sync', on_click=lambda: build_ui(cid, sid, s_dict, container)).classes('bg-indigo-600 hover:bg-indigo-700 text-white font-bold h-14 rounded-xl px-6 shadow-md')
                        
                        now = datetime.now()
                        date_clause = ""
                        params = [cid, sid]
                        
                        if s_dict['period'] == 'Specific Date':
                            if not s_dict['date']: return
                            date_clause = "AND att.date = ?"
                            params.append(s_dict['date'])
                            show_percent = False
                        elif s_dict['period'] == 'Weekly':
                            date_clause = "AND att.date >= ?"
                            params.append((now - timedelta(days=7)).strftime('%Y-%m-%d'))
                            show_percent = True
                        elif s_dict['period'] == 'Monthly':
                            date_clause = "AND att.date >= ?"
                            params.append((now - timedelta(days=30)).strftime('%Y-%m-%d'))
                            show_percent = True
                        elif s_dict['period'] == 'Quarterly':
                            date_clause = "AND att.date >= ?"
                            params.append((now - timedelta(days=90)).strftime('%Y-%m-%d'))
                            show_percent = True
                        elif s_dict['period'] == '6-Monthly':
                            date_clause = "AND att.date >= ?"
                            params.append((now - timedelta(days=180)).strftime('%Y-%m-%d'))
                            show_percent = True
                        else: 
                            show_percent = False

                        tc_query = f"SELECT COUNT(DISTINCT date) as tc FROM attendance att WHERE class_id=? AND subject_id=? {date_clause}"
                        total_classes_held = db_query(tc_query, tuple(params))[0]['tc']

                        params.append(cid)
                        stats = db_query(f"""
                            SELECT s.id as student_id, s.name, s.roll_no, 
                                   COUNT(att.id) as days_present
                            FROM students s
                            LEFT JOIN attendance att ON s.id = att.student_id AND att.class_id = ? AND att.subject_id = ? {date_clause}
                            WHERE s.class_id = ?
                            GROUP BY s.id
                            ORDER BY s.roll_no ASC
                        """, tuple(params))

                        if not stats:
                            ui.label('No students registered in this class yet.').classes('text-slate-400 italic p-4')
                            return

                        can_edit = False
                        if not show_percent:
                            try:
                                target_date_obj = datetime.strptime(s_dict['date'], '%Y-%m-%d').date()
                                today_date_obj = datetime.now().date()
                                # Allow editing only if the target date is within the last 24 hours (Today or Yesterday)
                                if 0 <= (today_date_obj - target_date_obj).days <= 1:
                                    can_edit = True
                            except: pass

                        total_present_all = sum(r['days_present'] for r in stats)
                        total_possible_all = total_classes_held * len(stats) if total_classes_held > 0 else 0
                        total_absent_all = total_possible_all - total_present_all

                        table_data = []
                        for r in stats:
                            row_data = {
                                'student_id': r['student_id'],
                                'roll_no': r['roll_no'],
                                'name': r['name']
                            }
                            if show_percent:
                                row_data['days_present'] = r['days_present']
                                row_data['total_classes'] = total_classes_held
                                perc = round((r['days_present'] / total_classes_held * 100), 1) if total_classes_held > 0 else 0
                                row_data['percentage'] = f"{perc}%"
                            else:
                                row_data['status'] = 'Present' if r['days_present'] > 0 else 'Absent'
                                row_data['can_edit'] = can_edit
                            table_data.append(row_data)

                        if show_percent:
                            cols = [
                                {'name': 'roll_no', 'label': 'Roll No', 'field': 'roll_no', 'align': 'left'},
                                {'name': 'name', 'label': 'Student Name', 'field': 'name', 'align': 'left'},
                                {'name': 'days_present', 'label': 'Days Present', 'field': 'days_present', 'align': 'center'},
                                {'name': 'total_classes', 'label': 'Total Classes', 'field': 'total_classes', 'align': 'center'},
                                {'name': 'percentage', 'label': 'Attendance %', 'field': 'percentage', 'align': 'center'}
                            ]
                        else:
                            cols = [
                                {'name': 'roll_no', 'label': 'Roll No', 'field': 'roll_no', 'align': 'left'},
                                {'name': 'name', 'label': 'Student Name', 'field': 'name', 'align': 'left'},
                                {'name': 'status', 'label': 'Status', 'field': 'status', 'align': 'center'},
                                {'name': 'action', 'label': 'Action', 'field': 'action', 'align': 'center'}
                            ]

                        with ui.row().classes('w-full items-start gap-8'):
                            with ui.column().classes('flex-grow max-w-2xl'):
                                ui.label('Roster Detail').classes('font-bold text-slate-500 uppercase tracking-widest text-sm mb-2')
                                table = ui.table(columns=cols, rows=table_data, row_key='roll_no').classes('w-full shadow-none border border-slate-200 rounded-2xl')
                                
                                if not show_percent:
                                    table.add_slot('body-cell-action', '''
                                        <q-td :props="props">
                                            <q-btn v-if="props.row.can_edit" 
                                                   :color="props.row.status === 'Present' ? 'negative' : 'positive'" 
                                                   :label="props.row.status === 'Present' ? 'Mark Absent' : 'Mark Present'" 
                                                   dense outline size="sm" @click="() => $parent.$emit('toggle', props.row)" />
                                            <span v-else class="text-xs text-slate-400 font-medium tracking-wider uppercase bg-slate-100 px-3 py-1 rounded-lg">Locked</span>
                                        </q-td>
                                    ''')
                                    
                                    def handle_toggle(e):
                                        row = e.args
                                        student_id = row['student_id']
                                        current_status = row['status']
                                        if current_status == 'Present':
                                            db_query("DELETE FROM attendance WHERE student_id=? AND class_id=? AND subject_id=? AND date=?", (student_id, cid, sid, s_dict['date']), fetch=False)
                                            ui.notify(f"Marked {row['name']} as Absent", color='warning')
                                        else:
                                            now_time = datetime.now().strftime('%H:%M')
                                            db_query("INSERT INTO attendance (student_id, class_id, subject_id, date, time, status) VALUES (?, ?, ?, ?, ?, ?)",
                                                     (student_id, cid, sid, s_dict['date'], now_time, 'Present'), fetch=False)
                                            ui.notify(f"Marked {row['name']} as Present", color='positive')
                                        build_ui(cid, sid, s_dict, container)
                                        
                                    table.on('toggle', handle_toggle)

                            with ui.column().classes('flex-grow items-center justify-center bg-white shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-3xl border border-slate-100 p-6 min-w-[300px]'):
                                if show_percent and total_possible_all > 0:
                                    ui.label(f"Overall Class Attendance ({s_dict['period']})").classes('font-bold text-slate-700 mb-2')
                                    ui.echart({
                                        'tooltip': {'trigger': 'item', 'formatter': '{b}: {c} ({d}%)'},
                                        'legend': {'bottom': '0%', 'left': 'center'},
                                        'series': [{
                                            'type': 'pie',
                                            'radius': ['40%', '70%'],
                                            'avoidLabelOverlap': False,
                                            'itemStyle': {
                                                'borderRadius': 8,
                                                'borderColor': '#fff',
                                                'borderWidth': 3
                                            },
                                            'label': {'show': False},
                                            'data': [
                                                {'value': total_present_all, 'name': 'Present', 'itemStyle': {'color': '#6366f1'}}, 
                                                {'value': total_absent_all, 'name': 'Absent', 'itemStyle': {'color': '#e2e8f0'}}    
                                            ]
                                        }]
                                    }).classes('w-full h-64')
                                elif not show_percent:
                                    day_present = sum(r['days_present'] for r in stats)
                                    day_absent = len(stats) - day_present
                                    ui.label(f"Attendance for {s_dict['date']}").classes('font-bold text-slate-700 mb-2')
                                    ui.echart({
                                        'tooltip': {'trigger': 'item', 'formatter': '{b}: {c} ({d}%)'},
                                        'legend': {'bottom': '0%', 'left': 'center'},
                                        'series': [{
                                            'type': 'pie',
                                            'radius': '70%',
                                            'data': [
                                                {'value': day_present, 'name': 'Present', 'itemStyle': {'color': '#10b981'}}, 
                                                {'value': day_absent, 'name': 'Absent', 'itemStyle': {'color': '#f43f5e'}}    
                                            ],
                                            'emphasis': {
                                                'itemStyle': {
                                                    'shadowBlur': 10,
                                                    'shadowOffsetX': 0,
                                                    'shadowColor': 'rgba(0, 0, 0, 0.5)'
                                                }
                                            }
                                        }]
                                    }).classes('w-full h-64')
                                else:
                                    ui.icon('pie_chart_outline', size='4rem', color='slate-300').classes('mb-4')
                                    ui.label('No attendance logged for this period.').classes('text-slate-400 italic text-center')

                build_ui(a['cid'], a['sid'], state, content_container)

def render_percentage(assigns):
    if not assigns:
        ui.label('No assigned classes to show percentages for.').classes('p-6 italic text-slate-500')
        return

    with ui.column().classes('w-full items-center p-6 pb-12'):
        ui.label('Class-wise Attendance Percentage').classes('text-3xl font-black mb-6 text-slate-800 tracking-tight w-full max-w-5xl')
        
        for a in assigns:
            with ui.expansion(f"{a['cname']} | {a['sname']}", icon='percent').classes('w-full max-w-5xl bg-white shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 rounded-2xl mb-4 text-lg font-bold text-slate-700'):
                
                # Get the total distinct dates a class was held for this subject
                tc_query = "SELECT COUNT(DISTINCT date) as tc FROM attendance WHERE class_id=? AND subject_id=?"
                total_classes_held = db_query(tc_query, (a['cid'], a['sid']))[0]['tc']

                stats = db_query("""
                    SELECT s.id as student_id, s.name, s.roll_no, 
                           COUNT(att.id) as days_present
                    FROM students s
                    LEFT JOIN attendance att ON s.id = att.student_id AND att.class_id = ? AND att.subject_id = ?
                    WHERE s.class_id = ?
                    GROUP BY s.id
                    ORDER BY s.roll_no ASC
                """, (a['cid'], a['sid'], a['cid']))

                if not stats:
                    ui.label('No students registered in this class yet.').classes('text-slate-400 italic p-4 font-normal text-base')
                    continue

                table_data = []
                chart_names = []
                chart_percs = []
                
                for r in stats:
                    perc_val = round((r['days_present'] / total_classes_held * 100), 1) if total_classes_held > 0 else 0
                    table_data.append({
                        'roll_no': r['roll_no'],
                        'name': r['name'],
                        'days_present': r['days_present'],
                        'total_classes': total_classes_held,
                        'percentage': f"{perc_val}%"
                    })
                    chart_names.append(r['name'])
                    chart_percs.append(perc_val)

                cols = [
                    {'name': 'roll_no', 'label': 'Roll No', 'field': 'roll_no', 'align': 'left'},
                    {'name': 'name', 'label': 'Student Name', 'field': 'name', 'align': 'left'},
                    {'name': 'days_present', 'label': 'Days Present', 'field': 'days_present', 'align': 'center'},
                    {'name': 'total_classes', 'label': 'Total Classes', 'field': 'total_classes', 'align': 'center'},
                    {'name': 'percentage', 'label': 'Overall Percentage', 'field': 'percentage', 'align': 'center'}
                ]

                with ui.row().classes('w-full items-start gap-8 p-4 font-normal text-base'):
                    with ui.column().classes('flex-grow max-w-2xl'):
                        ui.label('Cumulative Percentage Roster').classes('font-bold text-slate-500 uppercase tracking-widest text-sm mb-2')
                        ui.table(columns=cols, rows=table_data, row_key='roll_no').classes('w-full shadow-none border border-slate-200 rounded-2xl')
                    
                    with ui.column().classes('flex-grow items-center justify-center bg-white shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-3xl border border-slate-100 p-6 min-w-[300px]'):
                        ui.label('Student Attendance Graph').classes('font-bold text-slate-700 mb-2')
                        ui.echart({
                            'tooltip': {
                                'trigger': 'axis',
                                'axisPointer': {'type': 'shadow'},
                                'formatter': '{b}: {c}%'
                            },
                            'grid': {'left': '5%', 'right': '5%', 'bottom': '15%', 'top': '10%', 'containLabel': True},
                            'xAxis': {
                                'type': 'category', 
                                'data': chart_names,
                                'axisLabel': {'color': '#64748b', 'fontFamily': 'Poppins', 'rotate': 45}
                            },
                            'yAxis': {
                                'type': 'value', 
                                'max': 100,
                                'axisLabel': {'color': '#64748b', 'fontFamily': 'Poppins', 'formatter': '{value}%'},
                                'splitLine': {'lineStyle': {'color': '#f1f5f9', 'type': 'dashed'}}
                            },
                            'series': [{
                                'type': 'bar', 
                                'name': 'Percentage', 
                                'data': chart_percs, 
                                'itemStyle': {
                                    'color': 'rgba(16, 185, 129, 0.7)', 
                                    'borderColor': '#10b981',
                                    'borderWidth': 2,
                                    'borderRadius': [8, 8, 0, 0]
                                },
                                'barWidth': '40%'
                            }]
                        }).classes('w-full h-64')

# ---------------- INITIALIZATION ----------------
init_db()
os.makedirs('student_images', exist_ok=True)
os.makedirs('models', exist_ok=True) # Prepare models directory

ui.run(title='OptiMark AI Pro', storage_secret=uuid.uuid4().hex, port=8080)