from flask import Flask, render_template, request, redirect, flash, session
import sqlite3
from datetime import date
import random   # NEW (for unique ID)

app = Flask(__name__)
app.secret_key = "admin123"


# ---------------- DATABASE ----------------

def get_db():
    return sqlite3.connect("database.db")


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS Donor(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_code TEXT UNIQUE,
        name TEXT,
        blood_group TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS Stock(
        blood_group TEXT PRIMARY KEY,
        units INTEGER,
        expiry_date TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS Donation(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_id INTEGER,
        donation_date TEXT,
        units INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS Requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital TEXT,
        blood_group TEXT,
        units INTEGER,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "iqrazindabad":
            session["user"] = username
            return redirect("/")
        else:
            flash("Invalid Login")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")


# ---------------- HOME ----------------

@app.route("/")
def home():

    if "user" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM Donor")
    donors = cur.fetchone()[0]

    cur.execute("SELECT SUM(units) FROM Stock")
    stock = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM Requests")
    requests_count = cur.fetchone()[0]

    conn.close()

    return render_template("index.html",
                           donors=donors,
                           stock=stock,
                           requests=requests_count)


# ---------------- DONOR ----------------

@app.route("/donor", methods=["GET", "POST"])
def donor():

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":

        donor_type = request.form["donor_type"]
        units = int(request.form["units"])
        today = str(date.today())

        # ---------------- NEW DONOR ----------------
        if donor_type == "new":

            name = request.form["name"]
            bg = request.form["blood_group"]

            # UNIQUE DONOR ID
            donor_code = "D" + date.today().strftime("%d%m%Y") + str(random.randint(100,999))

            cur.execute("""
            INSERT INTO Donor(donor_code, name, blood_group)
            VALUES(?,?,?)
            """, (donor_code, name, bg))

            donor_id = cur.lastrowid

            flash(f"New Donor ID: {donor_code}")

        # ---------------- EXISTING DONOR ----------------
        else:

            code = request.form["donor_code"]

            cur.execute("SELECT id, blood_group FROM Donor WHERE donor_code=?", (code,))
            row = cur.fetchone()

            if not row:
                flash("Invalid Donor ID")
                return redirect("/donor")

            donor_id = row[0]
            bg = row[1]   # take blood group from DB

        # ---------------- SAVE DONATION ----------------

        cur.execute("""
        INSERT INTO Donation(donor_id, donation_date, units)
        VALUES(?,?,?)
        """, (donor_id, today, units))

        # ---------------- UPDATE STOCK ----------------

        cur.execute("SELECT units FROM Stock WHERE blood_group=?", (bg,))
        stock_row = cur.fetchone()

        if stock_row:
            cur.execute("UPDATE Stock SET units = units + ? WHERE blood_group=?",
                        (units, bg))
        else:
            cur.execute("""
            INSERT INTO Stock(blood_group, units, expiry_date)
            VALUES(?,?,?)
            """, (bg, units, today))

        conn.commit()
        flash("Donation Saved Successfully")

    cur.execute("SELECT * FROM Donor")
    donors = cur.fetchall()

    conn.close()

    return render_template("donor.html", donors=donors)


# ---------------- FETCH DONOR ----------------

@app.route("/get_donor/<code>")
def get_donor(code):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT name, blood_group FROM Donor WHERE donor_code=?", (code,))
    donor = cur.fetchone()

    conn.close()

    if donor:
        return {
            "name": donor[0],
            "blood_group": donor[1]
        }
    else:
        return {"error": "not found"}


# ---------------- DELETE ----------------

@app.route("/delete/<int:id>")
def delete(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM Donor WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect("/donor")


# ---------------- STOCK ----------------

@app.route("/stock")
def stock():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM Stock")
    data = cur.fetchall()

    conn.close()

    return render_template("stock.html", data=data)


# ---------------- HISTORY ----------------

@app.route("/history")
def history():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT Donor.name,
           Donor.blood_group,
           Donation.donation_date,
           Donation.units
    FROM Donation
    JOIN Donor ON Donation.donor_id = Donor.id
    """)

    data = cur.fetchall()
    conn.close()

    return render_template("history.html", data=data)


# ---------------- REQUEST ----------------

@app.route("/request", methods=["GET", "POST"])
def request_page():

    if request.method == "POST":

        hospital = request.form["hospital"]
        bg = request.form["blood_group"]
        units = int(request.form["units"])

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT units FROM Stock WHERE blood_group=?", (bg,))
        stock = cur.fetchone()

        if stock and stock[0] >= units:
            cur.execute("UPDATE Stock SET units = units - ? WHERE blood_group=?",
                        (units, bg))
            status = "Approved"
        else:
            status = "Rejected"

        cur.execute("""
        INSERT INTO Requests(hospital, blood_group, units, status)
        VALUES(?,?,?,?)
        """, (hospital, bg, units, status))

        conn.commit()
        conn.close()

        flash(f"Request {status}")

    return render_template("request.html")


# ---------------- VIEW REQUESTS ----------------

@app.route("/requests")
def requests():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM Requests")
    data = cur.fetchall()

    conn.close()

    return render_template("requests.html", data=data)


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)