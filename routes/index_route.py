import os
import pandas as pd
import numpy as np
from flask import Blueprint, request, render_template, session, send_file
from .utils import get_google_sheets_data  # ✅ Use shared utility

index_bp = Blueprint("index", __name__)
REPORT_FOLDER = "reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)

def clean_and_convert_age(age):
    if pd.isna(age) or age == "":
        return np.nan
    if isinstance(age, str):
        age = age.replace(' days', '').strip()
    try:
        return int(age)
    except ValueError:
        return np.nan

def categorize_age(days):
    if pd.isna(days) or days == "":
        return "3-5 years"
    try:
        days = int(days)
    except ValueError:
        return "3-5 years"
    if days < 730:
        return "Less than 2 years"
    elif 730 <= days < 1095:
        return "2-3 years"
    elif 1095 <= days < 1825:
        return "3-5 years"
    else:
        return "Above 5 years"

@index_bp.route("/", methods=["GET", "POST"])
def index():
    df, error = get_google_sheets_data()
    if error:
        return error

    # Strip whitespace from column names
    df.columns = df.columns.str.strip()

    required_columns = ['Make', 'TYPE OF DAMPER', 'Age', 'Test Result']
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        return f"Error: Missing required columns - {', '.join(missing)}"

    # Apply cleaning
    df['Age'] = df['Age'].apply(clean_and_convert_age)
    df['Age'] = df['Age'].fillna(1460)
    df['Age Group'] = df['Age'].apply(categorize_age)
    df['Make'] = df['Make'].fillna("Unknown")
    df['TYPE OF DAMPER'] = df['TYPE OF DAMPER'].fillna("Unknown")

    # 🔍 Period Filter using 'Test date time' if present
    if "Test date time" in df.columns:
        df["Test date time"] = pd.to_datetime(df["Test date time"], errors="coerce")
        start_date = session.get("start_date")
        end_date = session.get("end_date")
        if start_date and end_date:
            try:
                df = df[(df["Test date time"] >= start_date) & (df["Test date time"] <= end_date)]
            except Exception as e:
                return f"Date filtering error: {str(e)}"

    # Dropdown options
    makes = ["ALL"] + sorted(df['Make'].dropna().unique().tolist()) + ["NONE"]
    dampers = ["ALL"] + sorted(df['TYPE OF DAMPER'].dropna().unique().tolist()) + ["NONE"]
    age_groups = ["ALL", "Less than 2 years", "2-3 years", "3-5 years", "Above 5 years", "NONE"]

    # Get filters from form
    make = request.form.get("make", "ALL")
    age_group = request.form.get("age_group", "ALL")
    damper_type = request.form.get("damper_type", "ALL")

    # Filter
    filtered_df = df.copy()
    if make != "ALL" and make != "NONE":
        filtered_df = filtered_df[filtered_df['Make'] == make]
    if damper_type != "ALL" and damper_type != "NONE":
        filtered_df = filtered_df[filtered_df['TYPE OF DAMPER'] == damper_type]
    if age_group != "ALL" and age_group != "NONE":
        filtered_df = filtered_df[filtered_df['Age Group'] == age_group]

    if filtered_df.empty:
        return "No data available for the selected filters."

    selected_columns = []
    if make != "NONE":
        selected_columns.append("Make")
    if damper_type != "NONE":
        selected_columns.append("TYPE OF DAMPER")
    if age_group != "NONE":
        selected_columns.append("Age Group")

    if not selected_columns:
        return "No valid columns selected for grouping."

    result = filtered_df.groupby(selected_columns, dropna=False).agg(
        Number_of_Receipts=('Test Result', 'count'),
        Number_of_Failures=('Test Result', lambda x: (x != 'PASS').sum())
    ).reset_index()

    result['Failure Percentage'] = (result['Number_of_Failures'] / result['Number_of_Receipts']) * 100

    total_row = pd.DataFrame({
        selected_columns[0]: ['Total'],
        'Number_of_Receipts': [result['Number_of_Receipts'].sum()],
        'Number_of_Failures': [result['Number_of_Failures'].sum()],
        'Failure Percentage': [result['Number_of_Failures'].sum() / result['Number_of_Receipts'].sum() * 100]
    })

    result = pd.concat([result, total_row], ignore_index=True)

    # Save filtered report
    report_file = os.path.join(REPORT_FOLDER, "Filtered_Damper_Data.xlsx")
    result.to_excel(report_file, index=False, engine='openpyxl')
    session["report_file"] = "Filtered_Damper_Data.xlsx"

    return render_template("index.html",
        data=result.to_html(index=False, classes="table table-bordered"),
        makes=makes,
        dampers=dampers,
        age_groups=age_groups
    )

@index_bp.route("/download")
def download():
    report_file = session.get("report_file")
    if not report_file:
        return "No report available. Please generate a report first.", 404

    file_path = os.path.join(REPORT_FOLDER, report_file)

    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "Stored report file not found.", 404
