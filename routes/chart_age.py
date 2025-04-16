from flask import Blueprint, jsonify, render_template, request, session
import pandas as pd
import numpy as np
from .utils import get_google_sheets_data

chart_age_bp = Blueprint("chart_age_bp", __name__)

@chart_age_bp.route("/chart_age")
def chart_age():
    return render_template("chart_age.html")

@chart_age_bp.route("/age_group_analysis")
def age_group_analysis():
    age_group = request.args.get("group", "").strip()
    start_date = session.get('start_date', None)
    end_date = session.get('end_date', None)

    df, error = get_google_sheets_data()
    if error:
        return jsonify({"error": str(error)}), 500

    if "Age Group" not in df.columns:
        df["Age"] = df["Age"].astype(str).str.replace(" days", "", regex=True).str.strip()
        df["Age"] = pd.to_numeric(df["Age"], errors="coerce")

        def categorize_age(days):
            if pd.isna(days):
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

    # Filter by date
    if start_date and end_date:
        df["Test date time"] = pd.to_datetime(df["Test date time"], errors="coerce")
        df = df[(df["Test date time"] >= pd.to_datetime(start_date)) & (df["Test date time"] <= pd.to_datetime(end_date))]

    if age_group.upper() == "ALL":
        df_filtered = df[(df["TYPE OF DAMPER"].notna()) & (df["Make"].notna())].copy()
    else:
        df_filtered = df[(df["Age Group"].str.strip() == age_group) & 
                         (df["TYPE OF DAMPER"].notna()) & 
                         (df["Make"].notna())].copy()

    if df_filtered.empty:
        return jsonify({"error": f"No data found for Age Group: {age_group}"}), 404

    df_filtered["Failed"] = (df_filtered["Test Result"] == "FAIL").astype(int)
    df_filtered["Total"] = 1

    summary = df_filtered.groupby(["TYPE OF DAMPER", "Make"]).agg(
        Failures=('Failed', 'sum'),
        Total_Receipts=('Total', 'sum')
    ).reset_index()
    summary["Failure %"] = (summary["Failures"] / summary["Total_Receipts"] * 100).round(2)

    type_summary = df_filtered.groupby("TYPE OF DAMPER").agg(
        Failures=('Failed', 'sum'),
        Total_Receipts=('Total', 'sum')
    ).reset_index()
    type_summary["Failure %"] = (type_summary["Failures"] / type_summary["Total_Receipts"] * 100).round(2)
    type_summary["Failure Contribution %"] = (type_summary["Failures"] / type_summary["Failures"].sum() * 100).round(2)

    make_summary = df_filtered.groupby("Make").agg(
        Failures=('Failed', 'sum'),
        Total_Receipts=('Total', 'sum')
    ).reset_index()
    make_summary["Failure %"] = (make_summary["Failures"] / make_summary["Total_Receipts"] * 100).round(2)
    make_summary["Failure Contribution %"] = (make_summary["Failures"] / make_summary["Failures"].sum() * 100).round(2)

    # Add totals row to each summary table
    type_summary_with_total = type_summary.copy()
    type_summary_with_total.loc[len(type_summary_with_total)] = [
        "TOTAL", 
        type_summary["Failures"].sum(), 
        type_summary["Total_Receipts"].sum(),
        (type_summary["Failures"].sum() / type_summary["Total_Receipts"].sum() * 100).round(2),
        100.0
    ]

    make_summary_with_total = make_summary.copy()
    make_summary_with_total.loc[len(make_summary_with_total)] = [
        "TOTAL", 
        make_summary["Failures"].sum(), 
        make_summary["Total_Receipts"].sum(),
        (make_summary["Failures"].sum() / make_summary["Total_Receipts"].sum() * 100).round(2),
        100.0
    ]
    
    matrix_with_total = summary.copy()
    matrix_total = {
        "TYPE OF DAMPER": "TOTAL",
        "Make": "TOTAL",
        "Failures": summary["Failures"].sum(),
        "Total_Receipts": summary["Total_Receipts"].sum(),
        "Failure %": (summary["Failures"].sum() / summary["Total_Receipts"].sum() * 100).round(2)
    }
    matrix_with_total = pd.concat([matrix_with_total, pd.DataFrame([matrix_total])], ignore_index=True)

    unique_types = sorted(summary["TYPE OF DAMPER"].unique())
    unique_makes = sorted(summary["Make"].unique())

    colors = [
        'rgba(255, 99, 132, 0.7)', 'rgba(54, 162, 235, 0.7)', 
        'rgba(255, 206, 86, 0.7)', 'rgba(75, 192, 192, 0.7)',
        'rgba(153, 102, 255, 0.7)', 'rgba(255, 159, 64, 0.7)',
        'rgba(199, 199, 199, 0.7)', 'rgba(83, 102, 255, 0.7)'
    ]

    make_datasets = []
    for i, make in enumerate(unique_makes):
        make_data = summary[summary["Make"] == make]
        dataset = {
            "label": make,
            "backgroundColor": colors[i % len(colors)],
            "data": []
        }
        for damper_type in unique_types:
            row = make_data[make_data["TYPE OF DAMPER"] == damper_type]
            dataset["data"].append(row["Failure %"].values[0] if not row.empty else 0)
        make_datasets.append(dataset)

    # Pie charts
    pie_data = {
        "labels": type_summary["TYPE OF DAMPER"].tolist(),
        "values": type_summary["Failure Contribution %"].tolist(),
        "backgroundColor": [colors[i % len(colors)] for i in range(len(type_summary))],
    }
    pie_make_data = {
        "labels": make_summary["Make"].tolist(),
        "values": make_summary["Failure Contribution %"].tolist(),
        "backgroundColor": [colors[i % len(colors)] for i in range(len(make_summary))],
    }

    # PARETO CHART FIXES: Sort original data and prepare for total rows
    # --------------- TYPE PARETO CHART ---------------
    # First sort by Failure Contribution % (descending)
    pareto_type = type_summary.sort_values("Failure Contribution %", ascending=False).copy()
    pareto_type["Cumulative"] = pareto_type["Failure Contribution %"].cumsum().round(2)
    
    pareto_type_renamed = pareto_type.copy()
    pareto_type_renamed["Cumulative Failure %"] = pareto_type_renamed["Cumulative"].copy()
    pareto_type_renamed["Normalized Cumulative %"] = pareto_type_renamed["Cumulative"].copy()
    
    # Prepare total row for the end of the dataframe
    total_row_pareto_type = pd.DataFrame([{
        "TYPE OF DAMPER": "TOTAL",
        "Failures": pareto_type_renamed["Failures"].sum(),
        "Total_Receipts": pareto_type_renamed["Total_Receipts"].sum(),
        "Failure %": (pareto_type_renamed["Failures"].sum() / pareto_type_renamed["Total_Receipts"].sum() * 100).round(2),
        "Failure Contribution %": 100.0,
        "Cumulative": 100.0,
        "Cumulative Failure %": 100.0,
        "Normalized Cumulative %": 100.0
    }])
    
    # Simply append total row - no sorting needed after this
    pareto_type_with_total = pd.concat([pareto_type_renamed, total_row_pareto_type], ignore_index=True)
    
    # --------------- MAKE PARETO CHART ---------------
    # First sort by Failure Contribution % (descending)
    pareto_make = make_summary.sort_values("Failure Contribution %", ascending=False).copy()
    pareto_make["Cumulative"] = pareto_make["Failure Contribution %"].cumsum().round(2)
    
    pareto_make_renamed = pareto_make.copy()
    pareto_make_renamed["Cumulative Failure %"] = pareto_make_renamed["Cumulative"].copy()
    pareto_make_renamed["Normalized Cumulative %"] = pareto_make_renamed["Cumulative"].copy()
    
    # Prepare total row for the end of the dataframe
    total_row_pareto_make = pd.DataFrame([{
        "Make": "TOTAL",
        "Failures": pareto_make_renamed["Failures"].sum(),
        "Total_Receipts": pareto_make_renamed["Total_Receipts"].sum(),
        "Failure %": (pareto_make_renamed["Failures"].sum() / pareto_make_renamed["Total_Receipts"].sum() * 100).round(2),
        "Failure Contribution %": 100.0,
        "Cumulative": 100.0,
        "Cumulative Failure %": 100.0,
        "Normalized Cumulative %": 100.0
    }])
    
    # Simply append total row - no sorting needed after this
    pareto_make_with_total = pd.concat([pareto_make_renamed, total_row_pareto_make], ignore_index=True)

    insights = []
    if not type_summary.empty:
        top_type = type_summary.sort_values("Failure %", ascending=False).iloc[0]
        insights.append(f"✔️ Highest failing damper type: '{top_type['TYPE OF DAMPER']}' with {top_type['Failure %']}% failure rate.")

    if not make_summary.empty:
        top_make = make_summary.sort_values("Failure %", ascending=False).iloc[0]
        insights.append(f"✔️ Make with highest failure rate: '{top_make['Make']}' at {top_make['Failure %']}%.")

    if (type_summary["Failure %"] > 10).any():
        high_fail_types = type_summary[type_summary["Failure %"] > 10]["TYPE OF DAMPER"].tolist()
        insights.append("⚠️ Damper types >10% failure: " + ", ".join(high_fail_types))
    else:
        insights.append("✅ All damper types are within acceptable limits (<10% failure).")

    # Now we include a hint to let the frontend know what columns to use for the tables
    return jsonify({
        "title": f"Failure Analysis for Age Group: {age_group}",
        "makeDatasets": make_datasets,
        "matrixLabels": unique_types,
        "pieChart": pie_data,
        "pieChart_makeWise": pie_make_data,
        "paretoChart": {
            "labels": pareto_type["TYPE OF DAMPER"].tolist(),
            "values": pareto_type["Failure Contribution %"].tolist(),
            "cumulative": pareto_type["Cumulative"].tolist(),
        },
        "paretoChart_makeWise": {
            "labels": pareto_make["Make"].tolist(),
            "values": pareto_make["Failure Contribution %"].tolist(),
            "cumulative": pareto_make["Cumulative"].tolist(),
        },
        "insights": insights,
        "tableData": {
            "type": type_summary_with_total.to_dict(orient="records"),
            "make": make_summary_with_total.to_dict(orient="records"),
            "matrix": matrix_with_total.to_dict(orient="records"),
            "paretoType": pareto_type_with_total.to_dict(orient="records"),
            "paretoMake": pareto_make_with_total.to_dict(orient="records")
        },
        # Include column specifications for the tables (though the frontend might ignore this)
        "tableColumns": {
            "type": ["TYPE OF DAMPER", "Failures", "Total_Receipts", "Failure %", "Failure Contribution %"],
            "make": ["Make", "Failures", "Total_Receipts", "Failure %", "Failure Contribution %"],
            "matrix": ["TYPE OF DAMPER", "Make", "Failures", "Total_Receipts", "Failure %"],
            "paretoType": ["TYPE OF DAMPER", "Failures", "Total_Receipts", "Failure %", "Failure Contribution %", "Cumulative", "Cumulative Failure %", "Normalized Cumulative %"],
            "paretoMake": ["Make", "Failures", "Total_Receipts", "Failure %", "Failure Contribution %", "Cumulative", "Cumulative Failure %", "Normalized Cumulative %"]
        }
    })

# Add this route to your chart_age_bp Blueprint
@chart_age_bp.route('/get_all_age_groups')
def get_all_age_groups():
    df, error = get_google_sheets_data()
    if error:
        return jsonify({"age_groups": [], "error": str(error)}), 500

    if "Age Group" not in df.columns:
        df["Age"] = df["Age"].astype(str).str.replace(" days", "", regex=True).str.strip()
        df["Age"] = pd.to_numeric(df["Age"], errors="coerce")

        def categorize_age(days):
            if pd.isna(days):
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

    age_groups = ["ALL"] + sorted(df["Age Group"].dropna().unique().tolist())
    return jsonify({"age_groups": age_groups})