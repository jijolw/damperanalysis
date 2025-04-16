from flask import Flask, render_template, request, session, redirect, url_for
from flask_session import Session
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Initialize app
app = Flask(__name__)
app.secret_key = "secret_key"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Ensure reports folder exists
REPORT_FOLDER = "reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)

# Read Google credentials and Python version from environment variables
google_credentials_path = os.getenv("GOOGLE_CREDENTIALS", None)  # Path to Google credentials JSON
python_version = os.getenv("PYTHON_VERSION", None)  # Python version (optional for logging)

# Check if credentials are set
if google_credentials_path:
    try:
        with open(google_credentials_path) as f:
            google_credentials = json.load(f)
            # Optionally, print or use the credentials as needed
            print("Google credentials loaded successfully.")
    except Exception as e:
        print(f"Error loading Google credentials: {e}")
else:
    print("Google credentials not found.")

# Check if Python version is set
if python_version:
    print(f"Python Version: {python_version}")
else:
    print("Python version is not set.")

# Google Sheets authentication function
def authenticate_google_sheets():
    if google_credentials_path:
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            google_credentials, scope=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(credentials)
        return client
    else:
        raise Exception("Google credentials are missing. Please set up the environment variable.")

# Example route to fetch data from Google Sheets
@app.route("/fetch_data")
def fetch_data():
    try:
        # Authenticate and retrieve data from Google Sheets
        client = authenticate_google_sheets()
        
        # Example: Open a specific sheet by title
        sheet = client.open("Your Google Sheet Name").sheet1  # Replace with your sheet name
        data = sheet.get_all_records()  # Fetch all records
        
        return render_template("data_display.html", data=data)  # Render data to a new template
        
    except Exception as e:
        return f"Error fetching data from Google Sheets: {e}"

# Import and register blueprints (routes)
from routes.index_route import index_bp
from routes.download_route import download_bp
from routes.make_analysis import make_analysis_bp
from routes.type_analysis import type_analysis_bp
from routes.age_analysis import age_analysis_bp
from routes.chart_make import chart_make_bp
from routes.chart_type import chart_type_bp
from routes.chart_age import chart_age_bp

app.register_blueprint(index_bp, url_prefix="/filter")  # index route is now at /filter
app.register_blueprint(download_bp)
app.register_blueprint(make_analysis_bp)
app.register_blueprint(type_analysis_bp)
app.register_blueprint(age_analysis_bp)
app.register_blueprint(chart_make_bp)
app.register_blueprint(chart_type_bp)
app.register_blueprint(chart_age_bp)

# Home route
@app.route("/")
def home():
    return render_template("home.html")

# Optional favicon route
@app.route('/favicon.ico')
def favicon():
    return "", 204

# Route to set period (from home.html form)
@app.route("/set_period")
def home_redirect():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    next_page = request.args.get("next", "/filter")  # default to /filter

    session["start_date"] = start_date
    session["end_date"] = end_date

    return redirect(next_page)

# Running the app
if __name__ == "__main__":
    app.run(debug=True)
