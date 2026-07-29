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
import os
from sqlalchemy import text
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests





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



# Define the Student_info table
class StudentInfo(db.Model):
    __tablename__ = "student_info"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    roll = db.Column(db.Integer, unique=True, nullable=False)
    dept = db.Column(db.String(50), nullable=False)
    college_email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # ✅ updated



def get_connection_classrooms():
    return pymysql.connect(
        host="classiq.mysql.pythonanywhere-services.com",
        user="classiq",
        password=PYMYSQL_KEY,
        database="classiq$classrooms",
        cursorclass=pymysql.cursors.DictCursor
    )
# Simulated OTP store
otp_store = {}

ALLOWED_IPS = ["136.232.2.201", "45.112.71.121"]

def ip_whitelist(func):
    def wrapper(*args, **kwargs):
        if request.headers.getlist("X-Forwarded-For"):
            client_ip=request.headers.getlist("X-Forwarded-For")[0]
        else:
            client_ip=request.remote_addr
        print(f"client ip seen by flask: {client_ip}")
        if client_ip not in ALLOWED_IPS:
            abort(403)
        return func(*args, **kwargs)
    wrapper.__name__=func.__name__
    return wrapper

@app.route('/ipwhitelist')
@ip_whitelist
def ipwhitelist():
    return "<h1>This is ipwhitelist page</h1>"


@app.route('/scanner/<int:course_id>')
def open_scanner(course_id):
    return render_template("scanner.html", course_id=course_id)

@app.route("/save", methods=["POST"])
def save_data():
    if 'roll_no' not in session:
      return "You need to be logged in"
    try:
      data = request.get_json()
      course_id = data.get('course_id')
      qr_codes_set = set(data.get('qr_codes', []))
    except Exception as e:
        return f"Error: could not collect course and qr details, {e}"
    table_name = f"classroom{course_id}"   # can be dynamic if needed
    roll_no = session.get('roll_no')


    today_str = datetime.now().strftime("%d.%m.%y")

    try:
        conn = get_connection_classrooms()
        with conn.cursor() as cur:
            # Fetch original value
            cur.execute(f"SELECT `original` FROM `{table_name}` WHERE `is_master`=1 LIMIT 1;")
            row = cur.fetchone()
            if not row or row["original"] is None:
                return "attendance has not started yet code 0"
            print(f"original extracted: {row["original"]}")
            original_set = set(row["original"].split(","))

            # Compare lists
            if original_set != qr_codes_set:
                return "Attendance failed due to qr mismatch"

            # Check if today's column exists
            cur.execute(f"SHOW COLUMNS FROM `{table_name}` LIKE %s", (today_str,))
            col_exists = cur.fetchone()
            if not col_exists:
                return "attendance has not started yet code 1"

            # Get current value for this roll_no
            cur.execute(f"SELECT `current` FROM `{table_name}` WHERE `roll_no` = %s", (roll_no,))
            student = cur.fetchone()
            if not student:
                #return "You are not a part of this classroom"
                return jsonify(success=False, error="You are not a part of this classroom"), 500

            new_current = student["current"] + 1 if student["current"] else 1

            # Update both current and today's date column
            cur.execute(
                f"UPDATE `{table_name}` SET `current` = %s, `{today_str}` = %s WHERE `roll_no` = %s",
                (new_current, new_current, roll_no)
            )
            conn.commit()

        #return "Attendance marked successfully"
        return jsonify(success=True, message="Attendance marked successfully"), 200

    except Exception as e:
        return f"Error: {str(e)} [500]"
    finally:
        conn.close()

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

#from flask import render_template
@app.route('/logout_student')
def logout_student():
    # Clear the session
    session.clear()
    # Redirect back to login page
    return redirect(url_for('login_student'))


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
                name
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


    # Create login session
    session['user_id'] = user.id
    session['email'] = user.email
    session['name'] = user.first_name


    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "id": user.id,
            "name": user.first_name,
            "email": user.email
        }
    }), 200





@app.route('/logout')
def logout():
    # Clear all data from the current user's session
    session.clear()
    # Optional: Send a success message to the login page
    flash("You have been logged out successfully.", "success")

    # Redirect to your login route (ensure your login function is named 'login')
    return redirect(url_for('login_student'))



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



from flask import request, redirect, session, flash
from sqlalchemy import text

@app.route('/create_classroom', methods=['POST'])
def create_classroom():
    if 'user_id' not in session:
        return redirect('/login')

    class_name = request.form.get('name', '').strip()

    if class_name:
        db.session.execute(
            text("""
                INSERT INTO classrooms (name, faculty_id)
                VALUES (:name, :faculty_id)
            """),
            {
                "name": class_name,
                "faculty_id": session['user_id']
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

        # 1. Fetch classroom details to check who created it
        classroom = db.session.execute(
            text("SELECT id, faculty_id FROM classrooms WHERE id = :cid"),
            {"cid": cid}
        ).mappings().fetchone()

        if classroom:
            # 2. THE LOGIC: Block user if they are the creator/faculty of this classroom
            if classroom['faculty_id'] == session['user_id']:
                # Action blocked: User cannot join their own class
                # (Optional: You could use flash('You cannot join your own class.') here)
                return redirect('/dashboard_user')

            # 3. Otherwise, proceed to enroll the student
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




# @app.route('/student/dashboard')
# def student_dashboard():
#     roll_no = session.get("roll_no")  # ✅ read roll_no from session
#     if not roll_no:
#         return redirect(url_for("login_student"))  # ✅ must be function name, not HTML file

#     # --- First connection: enrolled courses ---
#     connection = pymysql.connect(
#         host='classiq.mysql.pythonanywhere-services.com',
#         user='classiq',
#         password='pythonanywhereman.com',
#         database='classiq$accounts',
#         cursorclass=pymysql.cursors.DictCursor
#     )

#     with connection.cursor() as cursor:
#         sql = "SELECT course_id, course_name FROM enrolled WHERE roll_no = %s"
#         cursor.execute(sql, (roll_no,))
#         courses = cursor.fetchall()
#     connection.close()

#     # --- Second connection: classrooms for attendance ---
#     connection2 = pymysql.connect(
#         host='classiq.mysql.pythonanywhere-services.com',
#         user='classiq',
#         password='pythonanywhereman.com',
#         database='classiq$classrooms',
#         cursorclass=pymysql.cursors.DictCursor
#     )

#     for course in courses:
#         table_name = f"classroom{course['course_id']}"  # e.g., classroom156

#         try:
#             with connection2.cursor() as cursor:
#                 sql = f"""
#                     SELECT c.current,
#                           (SELECT total FROM {table_name} WHERE is_master = TRUE LIMIT 1) AS total
#                     FROM {table_name} c
#                     WHERE c.roll_no = %s
#                     """
#                 cursor.execute(sql, (roll_no,))
#                 result = cursor.fetchone()

#                 if result and result["total"] > 0:
#                     attendance = (result["current"] / result["total"]) * 100
#                 else:
#                     attendance = 0.0
#         except Exception as e:
#             # if table doesn't exist or error occurs
#             attendance = None

#         course["attendance"] = round(attendance, 2) if attendance is not None else "N/A"

#     connection2.close()

#     # ✅ Now pass roll_no, courses with attendance to template
#     return render_template("student_courses.html", roll_no=roll_no, courses=courses)


#     # ---- Step 3: Send to template ----
#     return render_template("student_courses.html", roll_no=roll_no, courses=courses)




# @app.route('/xpage')
# def xpage():
#     # Ensure the user is logged in
#     teacher_id = session.get('user_id')
#     print(f"xpage user_id: {session.get('user_id')}")
#     if not teacher_id:
#         return redirect(url_for('login_faculty'))

#     # Establish MySQL connection using pymysql
#     try:
#         connection = pymysql.connect(
#             host='classiq.mysql.pythonanywhere-services.com',
#             user='classiq',   # e.g., 'yourusername'
#             password='pythonanywhereman.com',        # Replace with your MySQL password
#             database='classiq$accounts',  # e.g., 'yourusername$courses'
#             cursorclass=pymysql.cursors.DictCursor  # Ensures results are returned as dictionaries
#         )
#         with connection.cursor() as cursor:
#             # Query the database for course_id and course_name matching the teacher_id
#             query = "SELECT course_id, course_name FROM Courses WHERE teacher_id = %s"
#             cursor.execute(query, (teacher_id,))
#             courses = cursor.fetchall()

#     except pymysql.MySQLError as err:
#         print(f"Error: {err}")
#         return "An error occurred while connecting to the database.", 500

#     finally:
#         # Close the connection
#         if 'connection' in locals():
#             connection.close()

#     # Render the xpage.html template with the courses
#     return render_template('xpage.html', courses=courses)

# #----------xpage_sub-----------------------------------------------------------------------------
# @app.route('/xpage_sub', methods=['GET', 'POST'])
# def xpage_sub():
#     if request.method == 'POST':
#         course_id = request.form['course_id']
#         course_name = request.form['course_name']
#         teacher_id = session.get('user_id')   # assume user is logged in

#         # --- First DB: check + insert into courses table ---
#         conn1 = pymysql.connect(
#             host="classiq.mysql.pythonanywhere-services.com",
#             user="classiq",
#             password="pythonanywhereman.com",
#             database="classiq$accounts"
#         )
#         cur1 = conn1.cursor()

#         # check if (course_id, teacher_id) already exists
#         check_query = """
#             SELECT 1 FROM Courses WHERE course_id = %s AND teacher_id = %s
#         """
#         cur1.execute(check_query, (course_id, teacher_id))
#         exists = cur1.fetchone()

#         if exists:
#             cur1.close()
#             conn1.close()
#             return f"Course ID {course_id} is already assigned to you."

#         # insert new record
#         insert_query = """
#             INSERT INTO Courses (course_id, course_name, teacher_id)
#             VALUES (%s, %s, %s)
#         """
#         cur1.execute(insert_query, (course_id, course_name, teacher_id))
#         conn1.commit()
#         cur1.close()
#         conn1.close()

#         # --- Second DB: create a table for this course ---
#         conn2 = pymysql.connect(
#             host="classiq.mysql.pythonanywhere-services.com",
#             user="classiq",
#             password="pythonanywhereman.com",
#             database="classiq$classrooms"
#         )
#         cur2 = conn2.cursor()

#         table_name = f"classroom{course_id}"
#         create_table_query = f"""
#             CREATE TABLE IF NOT EXISTS `{table_name}` (
#                 roll_no INT NOT NULL PRIMARY KEY,
#                 student_name VARCHAR(100) DEFAULT NULL,
#                 original VARCHAR(50) DEFAULT NULL,
#                 total INT DEFAULT '0',
#                 current INT DEFAULT '0',
#                 is_master BOOLEAN NOT NULL DEFAULT FALSE
#             )
#         """


#         cur2.execute(create_table_query)
#         conn2.commit()
#         cur2.close()
#         conn2.close()
#         print("xpage_sub: classroom creation successfull")
#         return redirect(url_for('xpage'))

#     else:
#         return redirect(url_for('xpage'))

# #teacher
# @app.route('/classroom_viewer/<int:n>')
# def classroom_viewer(n):
#     table_name = f"classroom{n}"
#     students = []

#     try:
#         # connect inside route
#         connection = pymysql.connect(
#             host="classiq.mysql.pythonanywhere-services.com",
#             user="classiq",
#             password="pythonanywhereman.com",
#             database="classiq$classrooms",
#             cursorclass=pymysql.cursors.DictCursor
#         )
#         with connection.cursor() as cursor:
#             cursor.execute(f"SELECT student_name FROM {table_name}")
#             result = cursor.fetchall()
#             # extract just the student_name values into a list
#             students = [row["student_name"] for row in result]
#     except Exception as e:
#         return f"Error: {e}"
#     finally:
#         if 'connection' in locals():
#             connection.close()

#     return render_template("classroom_viewer.html", students=students, table_name=table_name, classroom_no=n)


# @app.route('/join_classroom/<int:n>', methods=['GET', 'POST'])
# def join_classroom(n):
#     #n is course_id
#     if 'roll_no' not in session:
#         return "You need to be logged in"
#     roll_no=session.get('roll_no')


#     conn1 = pymysql.connect(
#             host="classiq.mysql.pythonanywhere-services.com",
#             user="classiq",
#             password="pythonanywhereman.com",
#             database="classiq$accounts" #for enrolled and Courses
#         )
#     cur1 = conn1.cursor()

#     cur1.execute("SELECT course_name FROM Courses WHERE course_id = %s", (n,))
#     course_name=cur1.fetchone()[0]
#     print(f"course name is {course_name}--------------------------------------------------------------------------")
#     cur1.execute("SELECT name FROM student_info WHERE roll = %s", (roll_no,))
#     student_name=cur1.fetchone()[0]
#     print(f"student name is {student_name}----------------------------------------------------------------")
#     insert_query = """
#             INSERT INTO enrolled (roll_no, course_name, course_id)
#             VALUES (%s, %s, %s)
#         """
#     cur1.execute(insert_query, (roll_no, course_name, n))
#     conn1.commit()
#     cur1.close()
#     conn1.close()
#     #------connection for classrooms
#     conn2 = pymysql.connect(
#             host="classiq.mysql.pythonanywhere-services.com",
#             user="classiq",
#             password="pythonanywhereman.com",
#             database="classiq$classrooms"
#         )
#     cur2 = conn2.cursor()
#     # insert new record
#     try:
#         insert_query = f"""
#             INSERT INTO classroom{n} (roll_no, student_name, original, total, current, is_master)
#             VALUES (%s, %s, %s, %s, %s, %s)
#         """
#         cur2.execute(insert_query, (roll_no, student_name, None, 0, 0, False))
#         conn2.commit()  # don’t forget to commit the insert
#     except Exception as e:
#         print(f"Error inserting into classroom{n}: {e}------------------------------------------------------------")
#         conn2.rollback()

#     # Check how many rows are in the table
#     sql_count = f"SELECT COUNT(*) AS cnt FROM classroom{n}"
#     cur2.execute(sql_count)
#     count_result = cur2.fetchone()
#     print(f"{count_result}----------------------------")
#     # If only 1 row exists, set is_master = TRUE for that row
#     try:
#         if count_result[0] == 1:
#             sql_update_master = f"UPDATE classroom{n} SET is_master = TRUE LIMIT 1"
#             cur2.execute(sql_update_master)
#         conn2.commit()
#     except Exception as e:
#         print(f"Error while setting master row in classroom{n}: {e}")
#         conn2.rollback()

#     cur2.close()
#     conn2.close()
#     return redirect(url_for('student_dashboard'))

# @app.route("/attendance/<int:course_id>")
# def attendance(course_id):
#     table_name = f"classroom{course_id}"

#     try:
#         conn = get_connection_classrooms()
#         cur = conn.cursor(pymysql.cursors.DictCursor)

#         # total from the master row
#         cur.execute(f"SELECT `total` FROM `{table_name}` WHERE `is_master`=1 LIMIT 1;")
#         row = cur.fetchone()
#         total = row["total"] if row and row.get("total") is not None else 0
#         # list of students: roll_no + current (ALL rows, including master row)
#         cur.execute(f"SELECT `roll_no`, `current` FROM `{table_name}`;")
#         attendance_data = cur.fetchall()  # [{roll_no:..., current:...}, ...]
#         print(attendance_data)


#     except Exception as e:
#         # Optional: log the error for debugging
#         app.logger.exception("Error loading attendance for %s", table_name)
#         abort(500, description=str(e))
#     finally:
#         try:
#             conn.close()
#         except Exception:
#             pass

#     return render_template(
#         "attendance.html",
#         total=total,
#         attendance=attendance_data,
#         table_name=table_name,
#         classroom_no=course_id
#     )


# @app.route('/take_attendance/<int:n>')
# def take_attendance(n):
#     table_name = f"classroom{n}"
#     today_col = datetime.now().strftime("%d.%m.%y")

#     img_dir = os.path.join(app.static_folder, "images")
#     os.makedirs(img_dir, exist_ok=True)

#     try:
#         connection = pymysql.connect(
#             host="classiq.mysql.pythonanywhere-services.com",
#             user="classiq",
#             password="pythonanywhereman.com",
#             database="classiq$classrooms",
#             cursorclass=pymysql.cursors.DictCursor
#         )
#         with connection.cursor() as cursor:
#             # Check / create today's column
#             cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE %s", (today_col,))
#             if not cursor.fetchone():
#                 cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN `{today_col}` VARCHAR(255)")
#                 connection.commit()

#             # --- generate exactly 4 hex codes, each 5 digits ---
#             codes = [''.join(random.choices('0123456789abcdef', k=5)) for _ in range(4)]

#             # Save original codes to "original" column of first row (comma-separated, no spaces)
#             codes_str = ",".join(codes)
#             cursor.execute(
#                 f"UPDATE {table_name} SET original=%s, total=total+1 WHERE is_master = TRUE LIMIT 1",
#                 (codes_str,)
#             )
#             connection.commit()

#             # Create QR images and replace list entries with filenames (same-index replacement)
#             for i, code in enumerate(codes):
#                 img = qrcode.make(code)
#                 fname = f"{code}_{''.join(random.choices(string.ascii_lowercase+string.digits, k=6))}.png"
#                 img.save(os.path.join(img_dir, fname))
#                 codes[i] = fname  # replace code with filename in the SAME list

#     except Exception as e:
#         return f"Error: {e}"
#     finally:
#         if 'connection' in locals():
#             connection.close()

#     # 'codes' now holds the filenames; pass to template
#     return render_template("take_attendance.html", filenames=codes, table_name=table_name, today_col=today_col,course_id=n)

# @app.route('/delete', methods=['POST'])
# def delete_original_codes():
#     print("Delete route triggered")  # Debug
#     try:
#         data = request.get_json()
#         print("Received data:", data)  # Debug
#         course_id = data.get('course_id')
#         print("Course ID:", course_id)  # Debug

#         if not course_id:
#             return jsonify({'success': False, 'error': 'Course ID not provided'}), 400

#         table_name = f"classroom{course_id}"
#         print("Resolved table name:", table_name)

#         connection = pymysql.connect(
#             host="classiq.mysql.pythonanywhere-services.com",
#             user="classiq",
#             password="pythonanywhereman.com",
#             database="classiq$classrooms",
#             cursorclass=pymysql.cursors.DictCursor
#         )

#         with connection:
#             with connection.cursor() as cursor:
#                 query = f"UPDATE {table_name} SET original = NULL WHERE is_master = 1 LIMIT 1"
#                 print("Running query:", query)
#                 cursor.execute(query)
#                 rows_affected = cursor.rowcount
#                 print("Rows affected:", rows_affected)

#                 connection.commit()

#                 if rows_affected > 0:
#                     return jsonify({
#                         'success': True,
#                         'message': f'Successfully cleared original codes for {table_name}',
#                         'rows_affected': rows_affected
#                     })
#                 else:
#                     return jsonify({
#                         'success': False,
#                         'message': f'No master row found in {table_name}'
#                     })

#     except Exception as e:
#         print("Error:", str(e))
#         return jsonify({'success': False, 'error': str(e)}), 500

# @app.route('/login_faculty', methods=['POST', 'GET'])
# def login_faculty():
#     return render_template('login_faculty2.html')

# @app.route('/login_facultyy', methods=['POST'])
# def login_facultyy():
#     print("This is facultyy")
#     data = request.get_json()
#     email = data.get('email')
#     print(email)
#     password = data.get('password')
#     print(password)
#     user = User.query.filter_by(email=email).first()
#     if user and check_password_hash(user.password, password):
#         print("entered if")
#         session["user_id"] = user.id
#         print(f"session user_id: {session.get('user_id')}")
#         session["email"] = user.email
#         return jsonify({"success": True, "message": "Login successful"})
#     else:
#         print("entered else")
#         return jsonify({"success": False, "message": "Invalid email or password"}), 401


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




# @app.route('/register_student', methods=['POST'])
# def register_student():
#     data = request.json
#     name = data.get('studentName')
#     roll = data.get('rollNumber')
#     dept = data.get('department')
#     email = data.get('collegeEmail')
#     password = data.get('password')
#     phone = data.get('phoneNumber')   # not in table, will be ignored unless added

#     # Check if student already exists (by email or roll)
#     existing_student = StudentInfo.query.filter(
#         (StudentInfo.college_email == email) | (StudentInfo.roll == roll)
#     ).first()

#     if existing_student:
#         return jsonify({'message': 'Student already exists. Please log in.'}), 400

#     # Hash password
#     hashed_password = generate_password_hash(password)

#     # Generate OTP
#     otp = random.randint(100000, 999999)
#     otp_store[email] = {
#         'name': name,
#         'roll': roll,
#         'dept': dept,
#         'password': hashed_password,
#         'otp': otp
#     }


#     # Simulate sending OTP (replace with real email service later)
#     print(f"OTP for {email}: {otp}")
#     msg = Message(
#         subject="OTP for ClassIQ",
#         sender=("ClassIQ Support", app.config['MAIL_USERNAME']),
#         recipients=[email]
#     )
#     msg.body = f"{otp} is your OTP for ClassIQ student account creation. Do not share with anyone."

#     try:
#         mail.send(msg)
#         print("OTP sent to email!")
#     except Exception as e:
#         print(f"Error sending email {e}")

#     return jsonify({'message': 'Registration successful. OTP sent to email.'}), 200



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


@app.route('/verify-otp_student', methods=['POST'])
def verify_otp_student():
    data = request.json
    email = data.get('collegeEmail')
    otp = int(data.get('otp'))

    # Check if OTP matches
    if email in otp_store and otp_store[email]['otp'] == otp:
        student_data = otp_store[email]

        # Create new StudentInfo entry
        new_student = StudentInfo(
            name=student_data['name'],
            roll=student_data['roll'],
            dept=student_data['dept'],
            college_email=email,
            password=student_data['password']
        )

        db.session.add(new_student)
        db.session.commit()

        # Remove from otp_store after successful verification
        del otp_store[email]

        return jsonify({'message': 'OTP verified successfully! Student registered.'}), 200
    else:
        return jsonify({'message': 'Invalid OTP. Please try again.'}), 400



if __name__ == '__main__':
    # Create the database tables if they don't exist
    with app.app_context():
        db.create_all()

    app.run(debug=True)