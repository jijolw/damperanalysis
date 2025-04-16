from flask import Blueprint, jsonify, render_template, request, session
import pandas as pd
import numpy as np
from .utils import get_google_sheets_data

chart_type_bp = Blueprint("chart_type_bp", __name__)

@chart_type_bp.route("/chart_type")
def chart_type():
    return render_template("chart_type.html")

@chart_type_bp.route("/chart_type_analysis")
def chart_type_analysis():
    damper_type = request.args.get("type", "").strip()
    if damper_type == "All":  # Check if "All" is selected
        damper_type = None  # Set to None to select all types
    
    # Get the start and end dates from the session
    start_date = session.get('start_date', None)
    end_date = session.get('end_date', None)

    df, error = get_google_sheets_data()

    if error:
        return jsonify({"error": f"Google Sheets Error: {error}"}), 500

    if df.empty or "TYPE OF DAMPER" not in df.columns:
        return jsonify({"error": "No valid data found!"}), 404

    # Ensure that "Age Group" exists in the dataframe, if not, categorize based on "Age"
    if "Age Group" not in df.columns:
        df["Age"] = df["Age"].astype(str).str.replace(" days", "", regex=True).str.strip()
        df["Age"] = pd.to_numeric(df["Age"], errors="coerce")

        def categorize_age(days):
            if pd.isna(days) or days == "":
                return "3-5 years"
            days = int(days)
            if days < 730:
                return "Less than 2 years"
            elif 730 <= days < 1095:
                return "2-3 years"
            elif 1095 <= days < 1825:
                return "3-5 years"
            else:
                return "Above 5 years"

        df["Age Group"] = df["Age"].apply(categorize_age)

    # Filter by the selected date range (if provided)
    if start_date and end_date:
        df["Test date time"] = pd.to_datetime(df["Test date time"], errors="coerce")
        df = df[(df["Test date time"] >= pd.to_datetime(start_date)) & (df["Test date time"] <= pd.to_datetime(end_date))]

    # Filter data by damper type if provided
    if damper_type:  # If a specific type is selected, filter based on that
        df_filtered = df[
            (df['TYPE OF DAMPER'].str.strip().str.upper() == damper_type.upper()) &
            (df['Make'].notna()) & (df['Age Group'].notna())
        ].copy()
    else:  # If "All" is selected, don't filter by type
        df_filtered = df[
            (df['Make'].notna()) & (df['Age Group'].notna())
        ].copy()

    if df_filtered.empty:
        return jsonify({"error": f"No data found for Type: {damper_type}"}), 404

    df_filtered["Failed"] = (df_filtered["Test Result"] == "FAIL").astype(int)
    df_filtered["Total"] = 1

    summary = df_filtered.groupby(["Make", "Age Group"]).agg(
        Failures=('Failed', 'sum'),
        Total_Receipts=('Total', 'sum')
    ).reset_index()

    if summary.empty:
        return jsonify({"error": f"Not enough valid data to generate charts for Type: {damper_type}"}), 404

    summary["Failure %"] = (summary["Failures"] / summary["Total_Receipts"] * 100).round(2)

    make_summary = summary.groupby("Make").agg(
        Failures=('Failures', 'sum'),
        Total_Receipts=('Total_Receipts', 'sum')
    ).reset_index()
    make_summary["Failure %"] = (make_summary["Failures"] / make_summary["Total_Receipts"] * 100).round(2)

    unique_age_groups = sorted(summary["Age Group"].unique())
    unique_makes = sorted(make_summary["Make"].unique())

    labels = make_summary["Make"].tolist()
    values = make_summary["Failure %"].tolist()

    # Bar datasets by age group
    age_datasets = []
    colors = ['rgba(255, 99, 132, 0.7)', 'rgba(54, 162, 235, 0.7)', 
              'rgba(255, 206, 86, 0.7)', 'rgba(75, 192, 192, 0.7)',
              'rgba(153, 102, 255, 0.7)', 'rgba(255, 159, 64, 0.7)',
              'rgba(199, 199, 199, 0.7)', 'rgba(83, 102, 255, 0.7)']

    for i, age_group in enumerate(unique_age_groups):
        age_data = summary[summary["Age Group"] == age_group]
        dataset = {
            "label": age_group,
            "backgroundColor": colors[i % len(colors)],
            "data": []
        }
        for make in unique_makes:
            make_age_data = age_data[age_data["Make"] == make]
            dataset["data"].append(make_age_data["Failure %"].values[0] if not make_age_data.empty else 0)
        age_datasets.append(dataset)

    age_summary = df_filtered.groupby("Age Group").agg(
        Failures=('Failed', 'sum'),
        Total_Receipts=('Total', 'sum')
    ).reset_index()
    age_summary["Failure %"] = (age_summary["Failures"] / age_summary["Total_Receipts"] * 100).round(2)

    pie_labels = age_summary["Age Group"].tolist()
    pie_values = age_summary["Failure %"].tolist()
    pie_colors = [colors[i % len(colors)] for i in range(len(pie_labels))]

    sorted_age_summary = age_summary.sort_values("Failures", ascending=False)
    sorted_age_summary["Cumulative Failures"] = sorted_age_summary["Failures"].cumsum()
    sorted_age_summary["Cumulative %"] = (
        sorted_age_summary["Cumulative Failures"] / sorted_age_summary["Failures"].sum() * 100
    ).round(2)

    pareto_labels = sorted_age_summary["Age Group"].tolist()
    pareto_values = sorted_age_summary["Failures"].tolist()
    pareto_cumulative = sorted_age_summary["Cumulative %"].tolist()

    bar_age_labels = age_summary["Age Group"].tolist()
    bar_age_values = age_summary["Failure %"].tolist()

    pie_make_labels = make_summary["Make"].tolist()
    pie_make_values = make_summary["Failure %"].tolist()
    pie_make_colors = [colors[i % len(colors)] for i in range(len(pie_make_labels))]

    pareto_make = make_summary.sort_values("Failures", ascending=False)
    pareto_make["Cumulative Failures"] = pareto_make["Failures"].cumsum()
    pareto_make["Cumulative %"] = (
        pareto_make["Cumulative Failures"] / pareto_make["Failures"].sum() * 100
    ).round(2)

    pareto_make_labels = pareto_make["Make"].tolist()
    pareto_make_values = pareto_make["Failures"].tolist()
    pareto_make_cumulative = pareto_make["Cumulative %"].tolist()

    return jsonify({
        "labels": labels or [],
        "values": values or [],
        "ageDatasets": age_datasets or [],
        "title": f"Failure Analysis for Type: {damper_type}" if damper_type else "Failure Analysis for All Types",
        "options": {
            "plugins": {
                "datalabels": {
                    "display": True,
                    "align": "center",
                    "color": "#000",
                    "font": { "weight": "bold" },
                    "formatter": "function(value) { return value + '%'; }"
                }
            }
        },
        "pieChart": {
            "labels": pie_labels or [],
            "values": pie_values or [],
            "backgroundColor": pie_colors or [],
            "title": f"Failure % by Age Group for Type: {damper_type}" if damper_type else "Failure % by Age Group for All Types"
        },
        "paretoChart": {
            "labels": pareto_labels or [],
            "values": pareto_values or [],
            "cumulative": pareto_cumulative or [],
            "title": f"Pareto Analysis by Age Group for Type: {damper_type}" if damper_type else "Pareto Analysis by Age Group for All Types"
        },
        "barChart_ageWise": {
            "labels": bar_age_labels or [],
            "values": bar_age_values or [],
            "title": f"Failure % by Age Group for Type: {damper_type}" if damper_type else "Failure % by Age Group for All Types"
        },
        "pieChart_makeWise": {
            "labels": pie_make_labels or [],
            "values": pie_make_values or [],
            "backgroundColor": pie_make_colors or [],
            "title": f"Failure % by Make for Type: {damper_type}" if damper_type else "Failure % by Make for All Types"
        },
        "paretoChart_typeMake": {
            "labels": pareto_make_labels or [],
            "values": pareto_make_values or [],
            "cumulative": pareto_make_cumulative or [],
            "title": f"Pareto Chart: Type {damper_type} vs Make" if damper_type else "Pareto Chart: All Types vs Make"
        }
    })

@chart_type_bp.route('/get_all_types')
def get_all_types():
    df, error = get_google_sheets_data()
    if error:
        return jsonify({"types": [], "error": str(error)}), 500

    types = sorted(df["TYPE OF DAMPER"].dropna().unique().tolist())
    types.insert(0, "All")  # Add "All" option for dropdown
    return jsonify({"types": types})
