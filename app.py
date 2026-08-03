from flask import Flask, session, request, jsonify, flash
from flask import render_template,  redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import random
import qrcode
import string, os
from datetime import datetime
import pymysql
from dotenv import load_dotenv
from sqlalchemy import text
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import math
from datetime import timedelta
from itsdangerous import URLSafeSerializer




load_dotenv()
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY")#21
PYMYSQL_KEY = os.getenv("PYMYSQL_KEY")#23, 69
EMAIL_ID = os.getenv("EMAIL_ID")#34
EMAIL_KEY = os.getenv("EMAIL_KEY")#36
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")



app = Flask(__name__)
app.secret_key = APP_SECRET_KEY
# Configure MySQL database connection (PythonAnywhere MySQL settings)
app.config['SQLALCHEMY_DATABASE_URI'] = F'mysql+pymysql://classiq:{PYMYSQL_KEY}@classiq.mysql.pythonanywhere-services.com/classiq$account'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 280
}

db = SQLAlchemy(app)

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = EMAIL_ID
app.config['MAIL_PASSWORD'] = EMAIL_KEY  # <-- app password, not Gmail password
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)



# Define the User table
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=True)

    email = db.Column(db.String(255), unique=True, nullable=False)

    password_hash = db.Column(db.String(255), nullable=True)

    auth_provider = db.Column(
        db.Enum("local", "google", name="auth_provider_enum"),
        nullable=False,
        default="local"
    )

    provider_user_id = db.Column(db.String(255), nullable=True)

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        server_onupdate=db.func.current_timestamp(),
        nullable=False
    )


otp_store = {}



@app.route('/signup')
def signup_faculty():
    return render_template('signup.html')



@app.route('/dashboard')
def dashboard():
    # If the user is already logged in, redirect them to their dashboard
    if 'user_id' in session:
        return redirect('/dashboard_user')

    # Otherwise, show the normal public/landing dashboard page
    return render_template('dashboard.html')




@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('dashboard'))


@app.route('/login',methods=['GET'])
def login_student():
    return render_template('login.html')



@app.route('/dashboard_user')
def dashboard_user():

    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])

    if not user:
        session.clear()
        return redirect('/login')

    # Classes taught by this user
    my_classes = db.session.execute(
        text("""
            SELECT
                id,
                name,
                allowed_domain
            FROM classrooms
            WHERE faculty_id = :uid
            ORDER BY name
        """),
        {
            "uid": user.id
        }
    ).mappings().all()

    # Classes where this user is enrolled
    enrolled_classes = db.session.execute(
        text("""
            SELECT
                c.id,
                c.name,
                u.first_name AS faculty_name,
                u.last_name AS faculty_last_name
            FROM classroom_students cs
            JOIN classrooms c
                ON cs.classroom_id = c.id
            JOIN users u
                ON c.faculty_id = u.id
            WHERE cs.student_id = :uid
            ORDER BY c.name
        """),
        {
            "uid": user.id
        }
    ).mappings().all()

    return render_template(
        "dashboard_user.html",
        user=user,
        my_classes=my_classes,
        enrolled_classes=enrolled_classes
    )






@app.route('/login', methods=['POST'])
def login():

    data = request.get_json()

    email = data.get('email')
    password = data.get('password')


    # Validate input
    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400


    # Find user by email
    user = User.query.filter_by(email=email).first()


    if not user:
        return jsonify({
            "success": False,
            "message": "User does not exist"
        }), 404


    # Check authentication provider
    if user.auth_provider != "local":
        return jsonify({
            "success": False,
            "message": "Please login using Google authentication"
        }), 400


    # Verify password
    if not check_password_hash(user.password_hash, password):
        return jsonify({
            "success": False,
            "message": "Invalid password"
        }), 401

    session.pop('_flashes', None)

    # Create login session
    session['user_id'] = user.id
    session['email'] = user.email
    session['name'] = user.first_name


    #flash("You have been successfully logged in.")

    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "id": user.id,
            "name": user.first_name,
            "email": user.email
        }
    }), 200






# ==========================================
# --- NEW: GOOGLE LOGIN ROUTE ADDED HERE ---
# ==========================================
@app.route('/google-login', methods=['POST'])
def google_login():
    data = request.get_json()
    token = data.get('id_token')

    if not token:
        return jsonify({"success": False, "message": "No token provided"}), 400

    try:
        # 1. Verify the Google Token
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )

        # 2. Extract user info
        google_id = idinfo['sub']
        email = idinfo['email']
        first_name = idinfo.get('given_name', 'Unknown')
        last_name = idinfo.get('family_name', '')

        # 3. Database Check
        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                auth_provider='google',
                provider_user_id=google_id
            )
            db.session.add(user)
            db.session.commit()
        elif user.auth_provider == 'local':
            user.auth_provider = 'google'
            user.provider_user_id = google_id
            db.session.commit()
        else:
            user.first_name = first_name
            user.last_name = last_name
            db.session.commit()

        session.pop('_flashes', None)

        # 4. Create Session
        session['user_id'] = user.id
        session['email'] = user.email
        session['name'] = user.first_name

        return jsonify({
            "success": True,
            "message": "Logged in successfully with Google!"
        }), 200

    except ValueError:
        return jsonify({"success": False, "message": "Invalid Google token"}), 401

    except Exception as e:
        # THIS IS CRITICAL: If your DB schema is missing columns, it will print here.
        print(f"GOOGLE LOGIN FAILED: {str(e)}")
        db.session.rollback() # Prevent broken database state
        return jsonify({"success": False, "message": "Internal Server Error"}), 500



@app.route('/create_classroom', methods=['POST'])
def create_classroom():
    if 'user_id' not in session:
        return redirect('/login')

    class_name = request.form.get('name', '').strip()
    allowed_domain = request.form.get('allowed_domain', '').strip()

    if class_name:
        db.session.execute(
            text("""
                INSERT INTO classrooms (name, faculty_id, allowed_domain)
                VALUES (:name, :faculty_id, :allowed_domain)
            """),
            {
                "name": class_name,
                "faculty_id": session['user_id'],
                # Save as NULL in the database if the field was left empty
                "allowed_domain": allowed_domain if allowed_domain else None
            }
        )
        db.session.commit()

    return redirect('/dashboard_user')


@app.route('/join_classroom', methods=['POST'])
def join_classroom():
    if 'user_id' not in session:
        return redirect('/login')

    classroom_id = request.form.get('classroom_id', '').strip()

    if classroom_id and classroom_id.isdigit():
        cid = int(classroom_id)

        # 1. Fetch classroom details, now including the allowed_domain
        classroom = db.session.execute(
            text("SELECT id, faculty_id, allowed_domain FROM classrooms WHERE id = :cid"),
            {"cid": cid}
        ).mappings().fetchone()

        if classroom:
            # 2. Block user if they are the creator/faculty of this classroom
            if classroom['faculty_id'] == session['user_id']:
                flash('You cannot join your own class.')
                return redirect('/dashboard_user')

            # 3. Check domain restriction if an allowed_domain is set
            allowed_domain = classroom.get('allowed_domain')
            if allowed_domain:
                # Fetch the student's email to verify (Assumes your table is 'users' and column is 'email')
                student = db.session.execute(
                    text("SELECT email FROM users WHERE id = :sid"),
                    {"sid": session['user_id']}
                ).mappings().fetchone()

                if student and student['email']:
                    student_email = student['email'].lower()
                    # Ensure the domain starts with '@' for an exact match (handles if faculty typed 'university.edu' instead of '@university.edu')
                    domain_to_check = allowed_domain.lower() if allowed_domain.startswith('@') else f"@{allowed_domain.lower()}"

                    if not student_email.endswith(domain_to_check):
                        # Action blocked: Student's email domain does not match
                        flash('Your email domain is not authorized for this class.')
                        return redirect('/dashboard_user')
                else:
                    # Failsafe: If no email is found for the user, block the join
                    return redirect('/dashboard_user')

            # 4. Otherwise, proceed to enroll the student
            db.session.execute(
                text("""
                    INSERT IGNORE INTO classroom_students (classroom_id, student_id)
                    VALUES (:cid, :sid)
                """),
                {
                    "cid": cid,
                    "sid": session['user_id']
                }
            )
            db.session.commit()

    return redirect('/dashboard_user')


@app.route('/delete_classroom', methods=['POST'])
def delete_classroom():
    if 'user_id' not in session:
        return redirect('/login')

    classroom_id = request.form.get('classroom_id')

    if classroom_id and classroom_id.isdigit():
        # Deletes the class ONLY if the logged-in user is the faculty owner
        db.session.execute(
            text("""
                DELETE FROM classrooms
                WHERE id = :cid AND faculty_id = :uid
            """),
            {
                "cid": int(classroom_id),
                "uid": session['user_id']
            }
        )
        db.session.commit()

    return redirect('/dashboard_user')


@app.route('/leave_classroom', methods=['POST'])
def leave_classroom():
    if 'user_id' not in session:
        return redirect('/login')

    classroom_id = request.form.get('classroom_id')

    if classroom_id and classroom_id.isdigit():
        # Deletes the enrollment record linking this user to the class
        db.session.execute(
            text("""
                DELETE FROM classroom_students
                WHERE classroom_id = :cid AND student_id = :uid
            """),
            {
                "cid": int(classroom_id),
                "uid": session['user_id']
            }
        )
        db.session.commit()

    return redirect('/dashboard_user')




import io
import base64
import uuid

# ==========================================
# 1. PAGE ROUTE: Serve the Live QR Template
# ==========================================
@app.route('/take_attendance')
def live_qr_session():
    if 'user_id' not in session:
        return redirect('/login')

    class_id = request.args.get('class_id')
    class_name = request.args.get('class_name', 'Attendance Session')

    # Construct a simple dictionary from your existing session variables
    # so your template can use `user.id`, `user.name`, etc.
    user_data = {
        'id': session.get('user_id'),
        'name': session.get('name'),
        'email': session.get('email')
    }

    return render_template(
        'qr_sequence.html',
        user=user_data,
        class_id=class_id,
        class_name=class_name
    )

# ==========================================
# 2. API ROUTE: Generate & Send 4 QR Codes
# ==========================================
@app.route('/qr_sequence', methods=['POST'])
def generate_qr_sequence():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        class_id = data.get('class_id')

        if not user_id or not class_id:
            return jsonify({'error': 'Missing user_id or class_id'}), 400

        # --- 1. Database Insertion ---
        now = datetime.now()
        session_date = now.strftime('%Y-%m-%d')
        start_time = now.strftime('%H:%M:%S')

        # Assuming the total duration of the 4 QR sequence is 60 seconds (adjust timedelta as needed)
        qr_expires_at = now + timedelta(seconds=60)
        qr_expires_at_str = qr_expires_at.strftime('%Y-%m-%d %H:%M:%S')

        # Insert row into class_sessions
        result = db.session.execute(
            text("""
                INSERT INTO class_sessions (classroom_id, faculty_id, session_date, start_time, qr_expires_at)
                VALUES (:cid, :fid, :s_date, :s_time, :expires)
            """),
            {
                "cid": class_id,
                "fid": user_id,
                "s_date": session_date,
                "s_time": start_time,
                "expires": qr_expires_at_str
            }
        )
        db.session.commit()

        # Retrieve the auto-incremented ID of the new session
        session_id = result.lastrowid

        # --- 2. Create and Encode Dictionary ---
        payload = {
            "class_id": class_id,
            "session_id": session_id,
            "faculty_id": user_id,
            "expires": qr_expires_at_str
        }

        # Encode & sign the dictionary using your existing APP_SECRET_KEY
        serializer = URLSafeSerializer(app.secret_key)
        encoded_token = serializer.dumps(payload)

        # --- 3. Split Token into 4 Chunks ---
        chunk_size = math.ceil(len(encoded_token) / 4)
        chunks = [encoded_token[i:i + chunk_size] for i in range(0, len(encoded_token), chunk_size)]

        # Failsafe: Ensure exactly 4 elements exist just in case the string was unusually short
        while len(chunks) < 4:
            chunks.append("")

        # --- 4. Generate QR Codes ---
        qr_codes_payload = []

        for step in range(1, 5):
            # Extract the specific chunk for this step (Index is step - 1)
            chunk_data = chunks[step - 1]

            # Add metadata so the scanning app knows which chunk it just scanned
            unique_token = f"STEP:{step}|CHUNK:{chunk_data}"

            # Generate QR Code Image in Memory
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(unique_token)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # Save image to bytes buffer and encode to Base64 string
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            # Add to response payload
            qr_codes_payload.append({
                "qr_base64": img_base64,
                "qr_data": unique_token,
                "step": step
            })

        return jsonify({"qr_codes": qr_codes_payload}), 200

    except Exception as e:
        db.session.rollback()  # Rollback session insertion if something fails
        return jsonify({'error': str(e)}), 500



# ==========================================
# 1. PAGE ROUTE: Serve the Scanner Page
# ==========================================
@app.route('/scan_attendance')
def scan_attendance():
    if 'user_id' not in session:
        return redirect('/login')

    class_id = request.args.get('class_id')
    class_name = request.args.get('class_name', 'Class')

    user_data = {
        'id': session.get('user_id'),
        'first_name': session.get('first_name'),
        'last_name': session.get('last_name'),
    }

    return render_template(
        'scanner.html',
        user=user_data,
        class_id=class_id,
        class_name=class_name
    )


# ==========================================
# 2. API ROUTE: Process 4 Scanned QR Codes
# ==========================================
@app.route('/submit_scan_sequence', methods=['POST'])
def submit_scan_sequence():
    try:
        data = request.get_json()
        student_id = data.get('user_id')
        class_id = data.get('class_id')
        codes = data.get('codes', [])

        if len(codes) != 4:
            return jsonify({'error': 'Exactly 4 codes are required.'}), 400

        # --- A. Reassemble the Token Chunks ---
        chunks = [""] * 4

        for code in codes:
            if code.startswith("STEP:"):
                parts = code.split("|CHUNK:")
                if len(parts) == 2:
                    step = int(parts[0].replace("STEP:", ""))
                    chunk_data = parts[1]
                    chunks[step - 1] = chunk_data

        combined_token = "".join(chunks)

        # --- B. Decode & Verify Token ---
        serializer = URLSafeSerializer(app.secret_key)
        try:
            payload = serializer.loads(combined_token)
        except BadSignature:
            return jsonify({'error': 'Invalid or corrupted QR codes.'}), 400

        if str(payload.get('class_id')) != str(class_id):
            return jsonify({'error': 'This QR code does not match the selected class.'}), 400

        session_id = payload.get('session_id')

        # --- C. Check DB for Expiry ---
        now = datetime.now()  # Fixed: using datetime.now() directly

        session_record = db.session.execute(
            text("SELECT qr_expires_at FROM class_sessions WHERE id = :sid AND classroom_id = :cid"),
            {"sid": session_id, "cid": class_id}
        ).fetchone()

        if not session_record:
            return jsonify({'error': 'Invalid session.'}), 404

        qr_expires_at = session_record[0]

        if now > qr_expires_at:
            return jsonify({'error': 'QR code has expired. Please ask the faculty to generate a new session.'}), 400

        # --- D. Prevent Duplicate Attendance ---
        existing_attendance = db.session.execute(
            text("SELECT * FROM attendance WHERE session_id = :sid AND student_id = :stid"),
            {"sid": session_id, "stid": student_id}
        ).fetchone()

        if existing_attendance:
            return jsonify({'message': 'Attendance already marked successfully!'}), 200

        # --- E. Insert into Attendance Table ---
        db.session.execute(
            text("""
                INSERT INTO attendance (session_id, student_id, status, scan_time)
                VALUES (:sid, :stid, 'Present', :stime)
            """),
            {
                "sid": session_id,
                "stid": student_id,
                "stime": now.strftime('%Y-%m-%d %H:%M:%S')
            }
        )
        db.session.commit()

        return jsonify({'message': 'Attendance marked successfully!'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500






@app.route('/class_history/<int:class_id>')
def class_history(class_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    # 1. Fetch classroom details to check ownership
    classroom = db.session.execute(
        text("SELECT id, name, faculty_id FROM classrooms WHERE id = :cid"),
        {"cid": class_id}
    ).mappings().fetchone()

    if not classroom:
        flash("Classroom not found.")
        return redirect('/dashboard_user')

    # FIX 1: Safely compare IDs by casting to string to prevent int vs string mismatch
    is_teacher = (str(classroom['faculty_id']) == str(user_id))

    # 2. Get TOTAL SESSIONS held for this class till now
    total_result = db.session.execute(
        text("SELECT COUNT(id) AS total FROM class_sessions WHERE classroom_id = :cid"),
        {"cid": class_id}
    ).mappings().fetchone()

    # FIX 3: Check explicitly for None rather than relying on truthiness
    total_sessions_count = total_result['total'] if (total_result and total_result['total'] is not None) else 0

    # Ensure user data matches your dashboard variables
    user_data = {
        'id': session.get('user_id'),
        'first_name': session.get('name', 'User'),
        'email': session.get('email')
    }

    # ==========================================
    # TEACHER VIEW
    # ==========================================
    if is_teacher:
        history_records = db.session.execute(
            text("""
                SELECT
                    cs.id AS session_id,
                    cs.session_date,
                    cs.start_time,
                    -- FIX 2: Count by student_id instead of id to prevent SQL errors
                    COUNT(a.student_id) AS total_present
                FROM class_sessions cs
                LEFT JOIN attendance a
                    ON cs.id = a.session_id AND a.status = 'Present'
                WHERE cs.classroom_id = :cid
                GROUP BY cs.id, cs.session_date, cs.start_time
                ORDER BY cs.session_date DESC, cs.start_time DESC
            """),
            {"cid": class_id}
        ).mappings().fetchall()

        return render_template(
            'class_history.html',
            classroom=classroom,
            is_teacher=True,
            total_sessions=total_sessions_count,
            history=history_records,
            user=user_data
        )

    # ==========================================
    # STUDENT VIEW
    # ==========================================
    else:
        attended_result = db.session.execute(
            text("""
                SELECT COUNT(DISTINCT a.session_id) AS attended
                FROM attendance a
                JOIN class_sessions cs ON a.session_id = cs.id
                WHERE cs.classroom_id = :cid
                  AND a.student_id = :uid
                  AND a.status = 'Present'
            """),
            {"cid": class_id, "uid": user_id}
        ).mappings().fetchone()

        # FIX 3: Check explicitly for None
        student_attended_count = attended_result['attended'] if (attended_result and attended_result['attended'] is not None) else 0

        attendance_percentage = (
            round((student_attended_count / total_sessions_count) * 100, 2)
            if total_sessions_count > 0 else 0.0
        )

        history_records = db.session.execute(
            text("""
                SELECT
                    cs.id AS session_id,
                    cs.session_date,
                    cs.start_time,
                    -- FIX 2: Check against student_id instead of id to prevent SQL errors
                    IF(a.student_id IS NOT NULL, 'Present', 'Absent') AS my_status
                FROM class_sessions cs
                LEFT JOIN attendance a
                    ON cs.id = a.session_id
                    AND a.student_id = :uid
                    AND a.status = 'Present'
                WHERE cs.classroom_id = :cid
                ORDER BY cs.session_date DESC, cs.start_time DESC
            """),
            {"uid": user_id, "cid": class_id}
        ).mappings().fetchall()

        return render_template(
            'class_history.html',
            classroom=classroom,
            is_teacher=False,
            total_sessions=total_sessions_count,
            student_attended=student_attended_count,
            attendance_percentage=attendance_percentage,
            history=history_records,
            user=user_data
        )













@app.route('/')
def root():
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    first_name = data.get('firstName')
    last_name = data.get('lastName')
    email = data.get('email')
    password = data.get('password')

    # Validate required fields
    if not first_name or not email or not password:
        return jsonify({'message': 'Missing required fields.'}), 400

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'message': 'User already exists. Please log in.'}), 400

    # Hash the password
    hashed_password = generate_password_hash(password)

    # Generate OTP
    otp = random.randint(100000, 999999)

    # Store registration data temporarily until OTP verification
    otp_store[email] = {
        'first_name': first_name,
        'last_name': last_name,
        'password_hash': hashed_password,
        'auth_provider': 'local',
        'provider_user_id': None,
        'otp': otp
    }

    # Send OTP email
    msg = Message(
        subject="OTP for ClassIQ",
        sender=("ClassIQ Support", app.config['MAIL_USERNAME']),
        recipients=[email]
    )

    msg.body = (
        f"{otp} is your OTP for ClassIQ account creation.\n\n"
        "Do not share this OTP with anyone."
    )

    try:
        mail.send(msg)
        print(f"OTP sent to {email}")
    except Exception as e:
        print(f"Error sending email: {e}")
        return jsonify({'message': 'Failed to send OTP. Please try again.'}), 500

    return jsonify({
        'message': 'OTP sent to your email.'
    }), 200





@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    data = request.json
    email = data.get('email')

    if email in otp_store:
        # Generate a new OTP
        otp = random.randint(100000, 999999)
        otp_store[email]['otp'] = otp

        # Simulate sending the new OTP (in production, use an email service)
        print(f"New OTP for {email}: {otp}")

        return jsonify({'message': 'A new OTP has been sent to your email address.'}), 200
    else:
        return jsonify({'message': 'Email not found. Please register again.'}), 400


@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()

    email = data.get('email')
    otp = int(data.get('otp'))

    # Check if OTP exists and matches
    if email in otp_store and otp_store[email]['otp'] == otp:

        # Get temporary user data
        user_data = otp_store[email]

        # Create user record
        new_user = User(
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            email=email,
            password_hash=user_data['password_hash'],
            auth_provider='local',
            provider_user_id=None
        )

        db.session.add(new_user)
        db.session.commit()

        # Remove temporary OTP data
        del otp_store[email]

        return jsonify({
            'message': 'OTP verified successfully! Account created.'
        }), 200

    else:
        return jsonify({
            'message': 'Invalid OTP. Please try again.'
        }), 400



@app.route('/api/session_attendees/<int:session_id>')
def session_attendees(session_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']

    # Verify the user requesting this is the faculty member of the class
    session_record = db.session.execute(
        text("""
            SELECT c.faculty_id
            FROM class_sessions cs
            JOIN classrooms c ON cs.classroom_id = c.id
            WHERE cs.id = :sid
        """),
        {"sid": session_id}
    ).fetchone()

    if not session_record or str(session_record[0]) != str(user_id):
        return jsonify({'error': 'Unauthorized or session not found'}), 403

    # Fetch the students who attended this session
    attendees = db.session.execute(
        text("""
            SELECT u.first_name, u.last_name, u.email
            FROM attendance a
            JOIN users u ON a.student_id = u.id
            WHERE a.session_id = :sid AND a.status = 'Present'
            ORDER BY u.first_name, u.last_name
        """),
        {"sid": session_id}
    ).mappings().fetchall()

    attendees_list = [{
        'name': f"{row['first_name']} {row['last_name'] or ''}".strip(),
        'email': row['email']
    } for row in attendees]

    return jsonify({'attendees': attendees_list}), 200



if __name__ == '__main__':
    # Create the database tables if they don't exist
    with app.app_context():
        db.create_all()

    app.run(debug=True)