import mysql.connector
from mysql.connector import Error

DB_NAME = "personal_info_db"

def get_server_connection():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="1234"
        )
    except Error as e:
        print(f"❌ Cannot connect to MySQL server: {e}")
        return None

def get_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="1234",
            database=DB_NAME
        )
        return conn if conn.is_connected() else None
    except Error as e:
        print(f"❌ Database connection failed: {e}")
        return None

def ensure_database_exists():
    conn = get_server_connection()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        print(f"✅ Database '{DB_NAME}' ready.")
    except Error as e:
        print(f"❌ Error creating database: {e}")
    finally:
        cursor.close()
        conn.close()

def ensure_tables_exist():
    conn = get_connection()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Persons (
            person_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            dob DATE,
            gender VARCHAR(20),
            phone VARCHAR(15) UNIQUE,
            email VARCHAR(100) UNIQUE,
            address TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Career (
            career_id INT AUTO_INCREMENT PRIMARY KEY,
            person_id INT,
            job_title VARCHAR(100),
            company VARCHAR(100),
            years_experience INT,
            skills TEXT,
            FOREIGN KEY (person_id) REFERENCES Persons(person_id) ON DELETE CASCADE
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Education (
            edu_id INT AUTO_INCREMENT PRIMARY KEY,
            person_id INT,
            degree VARCHAR(100),
            institution VARCHAR(100),
            year_of_passing YEAR,
            FOREIGN KEY (person_id) REFERENCES Persons(person_id) ON DELETE CASCADE
        )
        """)
        conn.commit()
        print("✅ All tables ready.")
    except Error as e:
        print(f"❌ Error creating tables: {e}")
    finally:
        cursor.close()
        conn.close()

# Initialize DB & tables
ensure_database_exists()
ensure_tables_exist()
