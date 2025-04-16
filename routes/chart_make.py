from flask import Blueprint, jsonify, render_template, request
import pandas as pd
import numpy as np
from .utils import get_google_sheets_data

chart_make_bp = Blueprint("chart_make_bp", __name__)

@chart_make_bp.route("/chart_make")
def chart_make():
    # This route renders the template with the chart
    return render_template("chart_make.html")

@chart_make_bp.route("/chart_make_analysis")
def chart_make_analysis():
    make = request.args.get("make", "").strip()
    df, error = get_google_sheets_data()
    
    if error:
        return jsonify({"error": f"Google Sheets Error: {error}"}), 500
    
    if df.empty or "Make" not in df.columns:
        return jsonify({"error": "No valid data found!"}), 404
    
    # Categorize age if needed
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

    # Filter the dataframe
    df_filtered = df[
        (df['Make'].str.strip().str.upper() == make.upper()) &
        (df['TYPE OF DAMPER'].notna()) &
        (df['Age Group'].notna())
    ].copy()

    if df_filtered.empty:
        return jsonify({"error": f"No data found for Make: {make}"}), 404

    # Add failure and total count columns
    df_filtered["Failed"] = (df_filtered["Test Result"] == "FAIL").astype(int)
    df_filtered["Total"] = 1

    # Summary by Type and Age Group
    summary = df_filtered.groupby(["TYPE OF DAMPER", "Age Group"]).agg(
        Failures=('Failed', 'sum'),
        Total_Receipts=('Total', 'sum')
    ).reset_index()

    if summary.empty:
        return jsonify({"error": f"Not enough valid data to generate charts for Make: {make}"}), 404

    summary["Failure %"] = (summary["Failures"] / summary["Total_Receipts"] * 100).round(2)

    # Summary by Damper Type
    damper_summary = summary.groupby("TYPE OF DAMPER").agg(
        Failures=('Failures', 'sum'),
        Total_Receipts=('Total_Receipts', 'sum')
    ).reset_index()
    damper_summary["Failure %"] = (damper_summary["Failures"] / damper_summary["Total_Receipts"] * 100).round(2)

    if damper_summary.empty:
        return jsonify({"error": f"Not enough valid damper data for Make: {make}"}), 404

    # Chart Data
    unique_age_groups = sorted(summary["Age Group"].unique())
    unique_dampers = sorted(damper_summary["TYPE OF DAMPER"].unique())

    labels = damper_summary["TYPE OF DAMPER"].tolist()
    values = damper_summary["Failure %"].tolist()

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
        for damper in unique_dampers:
            damper_age_data = age_data[age_data["TYPE OF DAMPER"] == damper]
            if not damper_age_data.empty:
                dataset["data"].append(damper_age_data["Failure %"].values[0])
            else:
                dataset["data"].append(0)
        age_datasets.append(dataset)

    # Pie and Pareto charts by Age
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
    sorted_age_summary["Cumulative %"] = (sorted_age_summary["Cumulative Failures"] / sorted_age_summary["Failures"].sum() * 100).round(2)

    pareto_labels = sorted_age_summary["Age Group"].tolist()
    pareto_values = sorted_age_summary["Failures"].tolist()
    pareto_cumulative = sorted_age_summary["Cumulative %"].tolist()

    # Type pie
    pie_type_labels = damper_summary["TYPE OF DAMPER"].tolist()
    pie_type_values = damper_summary["Failure %"].tolist()
    pie_type_colors = [colors[i % len(colors)] for i in range(len(pie_type_labels))]

    # Pareto for Make vs Type
    pareto_make_type = damper_summary.sort_values("Failures", ascending=False)
    pareto_make_type["Cumulative Failures"] = pareto_make_type["Failures"].cumsum()
    pareto_make_type["Cumulative %"] = (pareto_make_type["Cumulative Failures"] / pareto_make_type["Failures"].sum() * 100).round(2)

    pareto_make_labels = pareto_make_type["TYPE OF DAMPER"].tolist()
    pareto_make_values = pareto_make_type["Failures"].tolist()
    pareto_make_cumulative = pareto_make_type["Cumulative %"].tolist()

    # Final response
    return jsonify({
        "labels": labels or [],
        "values": values or [],
        "ageDatasets": age_datasets or [],
        "title": f"Failure Analysis for Make: {make}",
        "options": {
            "plugins": {
                "datalabels": {
                    "display": True,
                    "align": "center",
                    "color": "#000",
                    "font": {
                        "weight": "bold"
                    },
                    "formatter": "function(value) { return value + '%'; }"
                }
            }
        },
        "pieChart": {
            "labels": pie_labels or [],
            "values": pie_values or [],
            "backgroundColor": pie_colors or [],
            "title": f"Failure % by Age Group for Make: {make}"
        },
        "paretoChart": {
            "labels": pareto_labels or [],
            "values": pareto_values or [],
            "cumulative": pareto_cumulative or [],
            "title": f"Pareto Analysis of Failures by Age Group for Make: {make}"
        },
        "barChart_ageWise": {
            "labels": age_summary["Age Group"].tolist(),
            "values": age_summary["Failure %"].tolist(),
            "title": f"Failure % by Age Group for Make: {make}"
        },
        "pieChart_typeWise": {
            "labels": pie_type_labels or [],
            "values": pie_type_values or [],
            "backgroundColor": pie_type_colors or [],
            "title": f"Failure % by Damper Type for Make: {make}"
        },
        "paretoChart_makeType": {
            "labels": pareto_make_labels or [],
            "values": pareto_make_values or [],
            "cumulative": pareto_make_cumulative or [],
            "title": f"Pareto Chart: Make {make} vs Damper Type"
        }
    })

@chart_make_bp.route('/get_all_makes')
def get_all_makes():
    df, error = get_google_sheets_data()
    if error:
        return jsonify({"makes": [], "error": str(error)}), 500

    makes = sorted(df["Make"].dropna().unique().tolist())
    return jsonify({"makes": makes})
