-- ============================================================
-- ClassIQ Database Schema
-- Schema only — NO real/user data included
-- ============================================================

CREATE DATABASE IF NOT EXISTS classiq;
USE classiq;

-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NULL,
    auth_provider ENUM('local', 'google') NOT NULL DEFAULT 'local',
    provider_user_id VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email)
);

-- ============================================================
-- CLASSROOMS
-- ============================================================

CREATE TABLE IF NOT EXISTS classrooms (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    faculty_id BIGINT UNSIGNED NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    allowed_domain VARCHAR(100) NULL,

    PRIMARY KEY (id),
    KEY idx_classrooms_faculty_id (faculty_id),

    CONSTRAINT fk_classrooms_faculty
        FOREIGN KEY (faculty_id)
        REFERENCES users(id)
);

-- ============================================================
-- CLASSROOM STUDENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS classroom_students (
    classroom_id BIGINT UNSIGNED NOT NULL,
    student_id BIGINT UNSIGNED NOT NULL,

    PRIMARY KEY (classroom_id, student_id),

    CONSTRAINT fk_classroom_students_classroom
        FOREIGN KEY (classroom_id)
        REFERENCES classrooms(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_classroom_students_student
        FOREIGN KEY (student_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

-- ============================================================
-- CLASS SESSIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS class_sessions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    classroom_id BIGINT UNSIGNED NOT NULL,
    faculty_id BIGINT UNSIGNED NOT NULL,
    session_date DATE NOT NULL,
    start_time TIME NOT NULL,
    qr_expires_at DATETIME NOT NULL,

    PRIMARY KEY (id),

    KEY idx_class_sessions_classroom_id (classroom_id),
    KEY idx_class_sessions_faculty_id (faculty_id),

    CONSTRAINT fk_class_sessions_classroom
        FOREIGN KEY (classroom_id)
        REFERENCES classrooms(id),

    CONSTRAINT fk_class_sessions_faculty
        FOREIGN KEY (faculty_id)
        REFERENCES users(id)
);

-- ============================================================
-- ATTENDANCE
-- ============================================================

CREATE TABLE IF NOT EXISTS attendance (
    session_id BIGINT UNSIGNED NOT NULL,
    student_id BIGINT UNSIGNED NOT NULL,
    status ENUM('Present', 'Absent') NOT NULL DEFAULT 'Present',
    scan_time DATETIME NULL,

    PRIMARY KEY (session_id, student_id),

    CONSTRAINT fk_attendance_session
        FOREIGN KEY (session_id)
        REFERENCES class_sessions(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_attendance_student
        FOREIGN KEY (student_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

-- ============================================================
-- END OF SCHEMA
-- ============================================================