from flask import Flask, render_template, request, redirect, session
import psycopg2

app = Flask(__name__)
app.secret_key = 'secret123'

# ---------------- DATABASE CONNECTION ----------------
conn = psycopg2.connect(
    dbname="appointment_db",
    user="postgres",
    password="123",
    host="localhost"
)
cur = conn.cursor()

# ---------------- HOME ----------------
@app.route('/')
def index():
    return render_template('index.html')

# ---------------- PATIENT REGISTER ----------------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        try:
            cur.execute(
                "INSERT INTO patients(name,email,password) VALUES(%s,%s,%s)",
                (name,email,password)
            )
            conn.commit()
            return redirect('/login')
        except Exception as e:
            conn.rollback()
            return f"Registration error: {e}"

    return render_template('register.html')

# ---------------- PATIENT LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur.execute(
            "SELECT patient_id FROM patients WHERE email=%s AND password=%s",
            (email,password)
        )
        user = cur.fetchone()

        if user:
            session['patient_id'] = user[0]
            return redirect('/book')
        else:
            return "Invalid email or password"

    return render_template('login.html')

# ---------------- BOOK APPOINTMENT ----------------
@app.route('/book', methods=['GET','POST'])
def book():
    if 'patient_id' not in session:
        return redirect('/login')

    # fetch doctors
    cur.execute("SELECT doctor_id, doctor_name, specialization FROM doctors")
    doctors = cur.fetchall()

    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        date = request.form['date']
        time = request.form['time']

        try:
            cur.execute(
                "SELECT book_appointment(%s,%s,%s,%s)",
                (session['patient_id'], doctor_id, date, time)
            )
            conn.commit()
            return redirect('/myappointments')
        except Exception as e:
            conn.rollback()
            return f"Booking error: {e}"

    return render_template('book_appointment.html', doctors=doctors)

# ---------------- PATIENT VIEW APPOINTMENTS ----------------
@app.route('/myappointments')
def myappointments():
    if 'patient_id' not in session:
        return redirect('/login')

    cur.execute("""
        SELECT a.appointment_date,
               a.appointment_time,
               d.doctor_name,
               d.specialization,
               a.status
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.doctor_id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date
    """,(session['patient_id'],))

    data = cur.fetchall()
    return render_template('my_appointments.html', data=data)

# ---------------- ADMIN LOGIN ----------------
@app.route('/admin', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur.execute(
            "SELECT admin_id FROM admin WHERE username=%s AND password=%s",
            (username,password)
        )
        admin = cur.fetchone()

        if admin:
            session['admin'] = admin[0]
            return redirect('/admin/dashboard')
        else:
            return "Invalid admin credentials"

    return render_template('admin_login.html')

# ---------------- ADMIN DASHBOARD ---------------- return render_template('admin_dashboard.html', appointments=appointments)
@app.route('/admin/dashboard')
def admin_dashboard():
    try:
        cur.execute("""
            SELECT a.appointment_id,
                   p.name,
                   d.doctor_name,
                   a.appointment_date,
                   a.appointment_time,
                   a.status
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            JOIN doctors d ON a.doctor_id = d.doctor_id
            ORDER BY a.appointment_date DESC
        """)
        data = cur.fetchall()
    except Exception as e:
        data = []
        print(e)

    return render_template('admin_dashboard.html', data=data)

# ---------------- ADMIN CONFIRM / REJECT ----------------
@app.route('/admin/update/<int:aid>/<status>')
def admin_update(aid, status):
    if 'admin' not in session:
        return redirect('/admin')

    if status not in ['Confirmed','Rejected']:
        return "Invalid status"

    try:
        cur.execute(
            "UPDATE appointments SET status=%s WHERE appointment_id=%s",
            (status, aid)
        )
        conn.commit()
    except:
        conn.rollback()

    return redirect('/admin/dashboard')
@app.route('/check_appointment', methods=['GET','POST'])
def check_appointment():
    data = None
    message = None

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Verify patient
            cur.execute(
                "SELECT patient_id FROM patients WHERE email=%s AND password=%s",
                (email, password)
            )
            user = cur.fetchone()

            if not user:
                message = "Invalid email or password"
            else:
                pid = user[0]

                cur.execute("""
                    SELECT a.appointment_id,
                           d.doctor_name,
                           a.appointment_date,
                           a.appointment_time,
                           a.status
                    FROM appointments a
                    JOIN doctors d ON a.doctor_id = d.doctor_id
                    WHERE a.patient_id = %s
                    ORDER BY a.appointment_date DESC
                """, (pid,))
                data = cur.fetchall()

                if not data:
                    message = "No appointments found"

        except Exception as e:
            conn.rollback()
            message = f"Error: {e}"

    return render_template('check_appointment.html', data=data, message=message)

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
@app.route('/cancel_check/<int:aid>', methods=['POST'])
def cancel_check(aid):
    email = request.form.get('email')
    password = request.form.get('password')

    try:
        cur.execute(
            "SELECT patient_id FROM patients WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cur.fetchone()

        if not user:
            return "Invalid credentials"

        pid = user[0]

        cur.execute("""
            UPDATE appointments
            SET status='Cancelled'
            WHERE appointment_id=%s
              AND patient_id=%s
              AND status='Pending'
        """, (aid, pid))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return f"Cancel error: {e}"

    return redirect('/check_appointment')

@app.route('/admin/confirm/<int:aid>', methods=['POST'])
def confirm_appointment(aid):
    try:
        cur.execute("""
            UPDATE appointments
            SET status='Confirmed'
            WHERE appointment_id=%s AND status='Pending'
        """, (aid,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Error: {e}"

    return redirect('/admin/dashboard')

@app.route('/admin/reject/<int:aid>', methods=['POST'])
def reject_appointment(aid):
    try:
        cur.execute("""
            UPDATE appointments
            SET status='Rejected'
            WHERE appointment_id=%s AND status='Pending'
        """, (aid,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Error: {e}"

    return redirect('/admin/dashboard')

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
