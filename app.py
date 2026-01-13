from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash
from database.db_connection import get_connection
from mysql.connector import IntegrityError
import re

app = Flask(__name__)
app.secret_key = "supersecretkey"


# ------------------------ Helpers ------------------------

def normalize_phone(phone):
    phone = re.sub(r'\D', '', phone.strip())
    if phone.startswith('91') and len(phone) > 10:
        phone = phone[2:]
    elif phone.startswith('0') and len(phone) > 10:
        phone = phone[1:]
    return phone[-10:] if len(phone) >= 10 else phone


def valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)


# ------------------------ Person Routes ------------------------

@app.route('/', methods=['GET'])
def index():
    conn = get_connection()
    if not conn:
        flash("❌ Cannot connect to DB", "danger")
        return render_template('index.html', persons=[], headers=[], is_empty=True)

    cursor = conn.cursor(dictionary=True)
    q = request.args.get('q', '').strip()

    if q:
        wildcard = f"%{q}%"
        cursor.execute(
            "SELECT * FROM Persons WHERE name LIKE %s OR email LIKE %s OR phone LIKE %s",
            (wildcard, wildcard, wildcard)
        )
    else:
        cursor.execute("SELECT * FROM Persons")

    persons = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'index.html',
        persons=persons,
        is_empty=len(persons) == 0,
        search_query=q
    )


@app.route('/person/<int:id>')
def person_detail(id):
    conn = get_connection()
    if not conn:
        flash("❌ Cannot connect to DB", "danger")
        return redirect(url_for('index'))

    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM Persons WHERE person_id = %s", (id,))
    person = cursor.fetchone()

    if not person:
        cursor.close()
        conn.close()
        flash("❌ Person not found", "danger")
        return redirect(url_for('index'))

    cursor.execute("""
        SELECT career_id, job_title, company, years_experience, skills
        FROM Career
        WHERE person_id = %s
        ORDER BY career_id DESC
    """, (id,))
    careers = cursor.fetchall()

    cursor.execute("""
        SELECT edu_id, degree, institution, year_of_passing
        FROM Education
        WHERE person_id = %s
        ORDER BY year_of_passing DESC
    """, (id,))
    education = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'person_detail.html',
        person=person,
        careers=careers,
        education=education
    )


@app.route('/add', methods=['GET', 'POST'])
def add_person():
    if request.method == 'POST':
        name = request.form['name'].strip()
        dob = request.form.get('dob')
        gender = request.form['gender']
        phone = normalize_phone(request.form['phone'])
        email = request.form['email'].strip()
        address = request.form['address'].strip()

        if not name or not phone or not email:
            flash("⚠ Name, phone, and email are required", "warning")
            return redirect(url_for('add_person'))

        if dob:
            try:
                dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
                if dob_date > date.today():
                    flash("⚠ DOB cannot be in the future", "warning")
                    return redirect(url_for('add_person'))
            except ValueError:
                flash("⚠ Invalid DOB format", "warning")
                return redirect(url_for('add_person'))

        if not phone.isdigit() or len(phone) != 10:
            flash("⚠ Phone must be exactly 10 digits", "warning")
            return redirect(url_for('add_person'))

        if not valid_email(email):
            flash("⚠ Invalid email format", "warning")
            return redirect(url_for('add_person'))

        conn = get_connection()
        if not conn:
            flash("❌ Cannot connect to DB", "danger")
            return redirect(url_for('add_person'))

        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO Persons (name, dob, gender, phone, email, address)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, dob or None, gender, phone, email, address))
            conn.commit()
            flash("✅ Person added successfully", "success")
        except IntegrityError:
            conn.rollback()
            flash("⚠ Phone or email already exists", "warning")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('index'))

    return render_template(
        'add_person.html',
        current_date=date.today().isoformat()
    )


@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update_person(id):
    conn = get_connection()
    if not conn:
        flash("❌ Cannot connect to DB", "danger")
        return redirect(url_for('index'))

    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM Persons WHERE person_id = %s", (id,))
    person = cursor.fetchone()

    if not person:
        cursor.close()
        conn.close()
        flash("❌ Person not found", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        gender = request.form['gender']
        phone = normalize_phone(request.form['phone'])
        email = request.form['email'].strip()
        address = request.form['address'].strip()

        if not phone.isdigit() or len(phone) != 10:
            flash("⚠ Phone must be exactly 10 digits", "warning")
            return redirect(url_for('update_person', id=id))

        if not valid_email(email):
            flash("⚠ Invalid email format", "warning")
            return redirect(url_for('update_person', id=id))

        try:
            cursor.execute("""
                UPDATE Persons
                SET gender=%s, phone=%s, email=%s, address=%s
                WHERE person_id=%s
            """, (gender, phone, email, address, id))
            conn.commit()
            flash("✅ Person updated successfully", "success")
        except IntegrityError:
            conn.rollback()
            flash("⚠ Phone or email already exists", "warning")
            return redirect(url_for('update_person', id=id))
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('person_detail', id=id))

    cursor.close()
    conn.close()
    return render_template('update_person.html', person=person)


@app.route('/delete/<int:id>', methods=['POST'])
def delete_person(id):
    conn = get_connection()
    if not conn:
        flash("❌ Cannot connect to DB", "danger")
        return redirect(url_for('index'))

    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Persons WHERE person_id = %s", (id,))
        conn.commit()
        flash("🗑 Person deleted successfully", "success")
    except IntegrityError:
        conn.rollback()
        flash("❌ Cannot delete person (linked records exist)", "danger")
    except Exception as e:
        conn.rollback()
        flash(f"❌ An unexpected error occurred: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('index'))


# ------------------------ Career Routes ------------------------

@app.route('/career/view')
def view_career():
    conn = get_connection()
    if not conn:
        flash("❌ Cannot connect to DB", "danger")
        return redirect(url_for('index'))

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.career_id, p.name, c.job_title, c.company,
               c.years_experience, c.skills
        FROM Career c
        JOIN Persons p ON c.person_id = p.person_id
        ORDER BY c.career_id DESC
    """)
    data = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('view_career.html', data=data)


@app.route('/career/add/<int:person_id>', methods=['GET', 'POST'])
def add_career(person_id):
    conn = get_connection()
    if not conn:
        flash("❌ Cannot connect to DB", "danger")
        return redirect(url_for('index'))

    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT person_id, name FROM Persons WHERE person_id = %s",
        (person_id,)
    )
    person = cursor.fetchone()

    if not person:
        cursor.close()
        conn.close()
        flash("Person not found", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        cursor.execute("""
            INSERT INTO Career (person_id, job_title, company, years_experience, skills)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            person_id,
            request.form['job_title'],
            request.form['company'],
            request.form['years_experience'],
            request.form['skills']
        ))
        conn.commit()
        cursor.close()
        conn.close()

        flash("✅ Career added successfully!", "success")
        return redirect(url_for('person_detail', id=person_id))

    cursor.close()
    conn.close()
    return render_template('add_career.html', person=person)


@app.route('/career/delete/<int:id>', methods=['POST'])
def delete_career(id):
    conn = get_connection()
    if not conn:
        flash("❌ Cannot connect to DB", "danger")
        return redirect(request.referrer or url_for('index'))

    cursor = conn.cursor()
    person_id = None
    try:
        # First, find the person_id for the redirect
        cursor.execute(
            "SELECT person_id FROM Career WHERE career_id = %s", (id,))
        result = cursor.fetchone()
        if result:
            person_id = result[0]

        # Now, delete the record
        cursor.execute("DELETE FROM Career WHERE career_id = %s", (id,))
        conn.commit()
        flash("🗑 Career deleted successfully", "success")
    except Exception as e:
        conn.rollback()
        flash(f"❌ Error deleting career record: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    if person_id:
        return redirect(url_for('person_detail', id=person_id))
    else:
        return redirect(url_for('index'))


# ------------------------ Education Routes ------------------------

@app.route('/education/view')
def view_education():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT e.edu_id, p.name, e.degree,
               e.institution, e.year_of_passing
        FROM Education e
        JOIN Persons p ON e.person_id = p.person_id
        ORDER BY e.edu_id DESC
    """)
    data = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('view_education.html', data=data)


@app.route('/education/add/<int:person_id>', methods=['GET', 'POST'])
def add_education(person_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT person_id, name FROM Persons WHERE person_id = %s",
        (person_id,)
    )
    person = cursor.fetchone()

    if not person:
        cursor.close()
        conn.close()
        flash("Person not found", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        cursor.execute("""
            INSERT INTO Education (person_id, degree, institution, year_of_passing)
            VALUES (%s, %s, %s, %s)
        """, (
            person_id,
            request.form['degree'],
            request.form['institution'],
            request.form['year_of_passing']
        ))
        conn.commit()
        cursor.close()
        conn.close()

        flash("✅ Education added successfully!", "success")
        return redirect(url_for('person_detail', id=person_id))

    cursor.close()
    conn.close()
    return render_template('add_education.html', person=person, max_year=2050)


@app.route('/education/delete/<int:id>', methods=['POST'])
def delete_education(id):
    conn = get_connection()
    if not conn:
        flash("❌ Cannot connect to DB", "danger")
        return redirect(request.referrer or url_for('index'))

    cursor = conn.cursor()
    person_id = None
    try:
        # First, find the person_id for the redirect
        cursor.execute(
            "SELECT person_id FROM Education WHERE edu_id = %s", (id,))
        result = cursor.fetchone()
        if result:
            person_id = result[0]

        # Now, delete the record
        cursor.execute("DELETE FROM Education WHERE edu_id = %s", (id,))
        conn.commit()
        flash("🗑 Education deleted successfully", "success")
    except Exception as e:
        conn.rollback()
        flash(f"❌ Error deleting education record: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    if person_id:
        return redirect(url_for('person_detail', id=person_id))
    else:
        return redirect(url_for('index'))


@app.route('/career/edit/<int:id>', methods=['GET', 'POST'])
def edit_career(id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.*, p.person_id, p.name
        FROM Career c
        JOIN Persons p ON c.person_id = p.person_id
        WHERE c.career_id = %s
    """, (id,))
    career = cursor.fetchone()

    if not career:
        cursor.close()
        conn.close()
        flash("Career record not found", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Check for actual changes before updating
        if (
            request.form.get('job_title') != career['job_title'] or
            request.form.get('company') != career['company'] or
            request.form.get('years_experience', type=int) != career['years_experience'] or
            request.form.get('skills') != career['skills']
        ):
            cursor.execute("""
                UPDATE Career
                SET job_title=%s, company=%s,
                    years_experience=%s, skills=%s
                WHERE career_id=%s
            """, (
                request.form['job_title'],
                request.form['company'],
                request.form['years_experience'],
                request.form['skills'],
                id
            ))
            conn.commit()
            flash("✅ Career updated successfully", "success")

        cursor.close()
        conn.close()

        return redirect(url_for('person_detail', id=career['person_id']))

    cursor.close()
    conn.close()
    return render_template('edit_career.html', career=career)


@app.route('/education/edit/<int:id>', methods=['GET', 'POST'])
def edit_education(id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT e.*, p.person_id, p.name
        FROM Education e
        JOIN Persons p ON e.person_id = p.person_id
        WHERE e.edu_id = %s
    """, (id,))
    edu = cursor.fetchone()

    if not edu:
        cursor.close()
        conn.close()
        flash("Education record not found", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        cursor.execute("""
            UPDATE Education
            SET degree=%s, institution=%s, year_of_passing=%s
            WHERE edu_id=%s
        """, (
            request.form['degree'],
            request.form['institution'],
            request.form['year_of_passing'],
            id
        ))
        conn.commit()
        cursor.close()
        conn.close()

        flash("✅ Education updated successfully", "success")
        return redirect(url_for('person_detail', id=edu['person_id']))

    cursor.close()
    conn.close()
    return render_template('edit_education.html', education=edu)

# ------------------------ Run App ------------------------


if __name__ == '__main__':
    app.run(debug=True)
