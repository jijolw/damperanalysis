from flask import Flask, render_template
from flask_session import Session
import os

# Initialize app
app = Flask(__name__)
app.secret_key = "secret_key"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Ensure reports folder exists
REPORT_FOLDER = "reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)

# Import and register blueprints
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
from flask import request, session, redirect, url_for

@app.route("/set_period")
def home_redirect():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    next_page = request.args.get("next", "/filter")  # default to /filter

    session["start_date"] = start_date
    session["end_date"] = end_date

    return redirect(next_page)


if __name__ == "__main__":
    app.run(debug=True)  