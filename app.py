from flask import Flask, render_template, request, session, redirect, url_for
from flask_session import Session
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64

# Initialize app
app = Flask(__name__)
app.secret_key = "secret_key"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Password to protect the app
APP_PASSWORD = "abc123"

# Create reports folder if not exists
REPORT_FOLDER = "reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)

# Load Google credentials from environment variable (Base64 encoded)
google_credentials_b64 = os.getenv("GOOGLE_CREDENTIALS", None)
python_version = os.getenv("PYTHON_VERSION", None)

# Decode credentials
if google_credentials_b64:
    try:
        google_credentials_json = json.loads(base64.b64decode(google_credentials_b64).decode("utf-8"))
        print("Google credentials loaded successfully.")
    except Exception as e:
        print(f"Error decoding Google credentials: {e}")
else:
    print("Google credentials not found.")

if python_version:
    print(f"Python Version: {python_version}")
else:
    print("Python version is not set.")

# Authenticate Google Sheets
def authenticate_google_sheets():
    if google_credentials_b64:
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            google_credentials_json,
            scope=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(credentials)
        return client
    else:
        raise Exception("Google credentials are missing.")

# ----------------------------------------
# PASSWORD PROTECTION
# ----------------------------------------

@app.before_request
def require_login():
    allowed_routes = ["login", "static", "favicon"]
    if "logged_in" not in session and request.endpoint not in allowed_routes:
        return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Invalid password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

# ----------------------------------------
# Example route to fetch data
# ----------------------------------------

@app.route("/fetch_data")
def fetch_data():
    try:
        client = authenticate_google_sheets()
        sheet = client.open("Your Google Sheet Name").sheet1  # Replace with your sheet title
        data = sheet.get_all_records()
        return render_template("data_display.html", data=data)
    except Exception as e:
        print(f"Error fetching data: {e}")  # Log the error
        return f"Error fetching data: {e}"

# ----------------------------------------
# Register your Blueprints
# ----------------------------------------

# Ensure these route files exist and have defined routes
from routes.index_route import index_bp
from routes.download_route import download_bp
from routes.make_analysis import make_analysis_bp
from routes.type_analysis import type_analysis_bp
from routes.age_analysis import age_analysis_bp
from routes.chart_make import chart_make_bp
from routes.chart_type import chart_type_bp
from routes.chart_age import chart_age_bp

app.register_blueprint(index_bp, url_prefix="/filter")
app.register_blueprint(download_bp)
app.register_blueprint(make_analysis_bp)
app.register_blueprint(type_analysis_bp)
app.register_blueprint(age_analysis_bp)
app.register_blueprint(chart_make_bp)
app.register_blueprint(chart_type_bp)
app.register_blueprint(chart_age_bp)

# ----------------------------------------
# Home page
# ----------------------------------------

@app.route("/")
def home():
    return render_template("home.html")

@app.route('/favicon.ico')
def favicon():
    return "", 204

@app.route("/set_period")
def home_redirect():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    next_page = request.args.get("next", "/filter")

    session["start_date"] = start_date
    session["end_date"] = end_date
    return redirect(next_page)

# ----------------------------------------
# Run
# ----------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
