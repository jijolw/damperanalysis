import os
import pandas as pd
from flask import Blueprint, request, jsonify, render_template, send_from_directory, session
from routes.utils import get_google_sheets_data, categorize_age
from datetime import datetime

type_analysis_bp = Blueprint("type_analysis", __name__)

# Folder to save reports
REPORT_FOLDER = "static/reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)

@type_analysis_bp.route("/analyze_type")
def analyze_type():
    damper_type = request.args.get("value", "").strip()
    df, error = get_google_sheets_data()

    if error:
        return jsonify({"error": f"Google Sheets Error: {error}"}), 500

    if df.empty or "TYPE OF DAMPER" not in df.columns:
        return jsonify({"error": "No valid data found!"}), 404

    if "Age" in df.columns and "Age Group" not in df.columns:
        df["Age"] = df["Age"].astype(str).str.replace(" days", "", regex=True).str.strip()
        df["Age"] = df["Age"].apply(lambda x: 1460 if x == "" or not x.isnumeric() else float(x))
        df["Age Group"] = df["Age"].apply(categorize_age)

    # Date filter logic - using the session to get start_date and end_date
    start_date = session.get("start_date")
    end_date = session.get("end_date")
    
    if start_date and end_date:
        try:
            # Ensure dates are in the correct format
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Convert 'Test date time' column to datetime
            df["Test date time"] = pd.to_datetime(df["Test date time"], errors='coerce')
            
            # Filter based on the date range
            df = df[(df["Test date time"] >= start_date) & (df["Test date time"] <= end_date)]
        except Exception as e:
            return jsonify({"error": f"Invalid date range: {e}"}), 400

    df_filtered = df[df['TYPE OF DAMPER'].str.strip().str.upper() == damper_type.upper()].copy()

    if df_filtered.empty:
        return jsonify({"error": f"No data found for Type: {damper_type}"}), 404

    df_filtered["Failed"] = (df_filtered["Test Result"] == "FAIL").astype(int)
    df_filtered["Total"] = 1

    summary = df_filtered.groupby(["Make", "Age Group"]).agg(
        Failures=('Failed', 'sum'),
        Total_Receipts=('Total', 'sum')
    ).reset_index()

    makes = summary['Make'].unique().tolist()
    columns_age_groups = ["Less than 2 years", "2-3 years", "3-5 years", "Above 5 years", "Total"]
    columns_metrics = ["Failures", "Total", "Failure %"]

    column_tuples = [(age, metric) for age in columns_age_groups for metric in columns_metrics]
    column_index = pd.MultiIndex.from_tuples(column_tuples)
    final_table = pd.DataFrame(index=makes, columns=column_index)

    for make in makes:
        for age_group in columns_age_groups[:-1]:
            subset = summary[(summary['Make'] == make) & (summary['Age Group'] == age_group)]
            failures = subset['Failures'].sum() if not subset.empty else 0
            total = subset['Total_Receipts'].sum() if not subset.empty else 0
            failure_pct = (failures / total * 100) if total > 0 else 0

            final_table.loc[make, (age_group, 'Failures')] = int(failures)
            final_table.loc[make, (age_group, 'Total')] = int(total)
            final_table.loc[make, (age_group, 'Failure %')] = f"{failure_pct:.2f}%"


        make_subset = summary[summary['Make'] == make]
        total_failures = make_subset['Failures'].sum()
        total_receipts = make_subset['Total_Receipts'].sum()
        total_percent = (total_failures / total_receipts * 100) if total_receipts > 0 else 0

        final_table.loc[make, ('Total', 'Failures')] = int(total_failures)
        final_table.loc[make, ('Total', 'Total')] = int(total_receipts)
        final_table.loc[make, ('Total', 'Failure %')] = f"{total_percent:.2f}%"


    final_table.loc['Total'] = pd.Series(dtype='object')

    for age_group in columns_age_groups[:-1]:
        age_subset = summary[summary['Age Group'] == age_group]
        age_failures = age_subset['Failures'].sum()
        age_total = age_subset['Total_Receipts'].sum()
        age_percent = (age_failures / age_total * 100) if age_total > 0 else 0

        final_table.loc['Total', (age_group, 'Failures')] = int(age_failures)
        final_table.loc['Total', (age_group, 'Total')] = int(age_total)
        final_table.loc['Total', (age_group, 'Failure %')] = f"{age_percent:.2f}%"


    total_failures = summary['Failures'].sum()
    total_receipts = summary['Total_Receipts'].sum()
    total_percent = (total_failures / total_receipts * 100) if total_receipts > 0 else 0

    final_table.loc['Total', ('Total', 'Failures')] = int(total_failures)
    final_table.loc['Total', ('Total', 'Total')] = int(total_receipts)
    final_table.loc['Total', ('Total', 'Failure %')] = f"{total_percent:.2f}%"


    final_table = final_table.fillna(0)
    final_table = final_table.infer_objects(copy=False)
    display_table = final_table.reset_index()
    display_table = display_table.rename(columns={'index': 'Make'})

    html_table = display_table.to_html(classes="table table-bordered table-hover", escape=False, index=False)

    # ✅ Styled header added above HTML table
    table_html = f"""
    <style>
    .table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
        color: #333;
    }}
    .table th {{
        background-color: #3c6382;
        color: white;
        text-align: center;
        vertical-align: middle;
        font-weight: bold;
        padding: 8px;
        border: 1px solid #ddd;
    }}
    .table td {{
        text-align: center;
        padding: 8px;
        border: 1px solid #ddd;
        background-color: #f9f9f9;
        color: #333;
    }}
    .table tr:nth-child(even) td {{
        background-color: #f2f2f2;
    }}
    .table tr:last-child td, .table tr:last-child th {{
        background-color: #c7ecee;
        font-weight: bold;
    }}
    .table tr:hover td {{
        background-color: #dff9fb;
    }}
    .table td:first-child {{
        font-weight: bold;
        background-color: #e6f2ff;
    }}
    .damper-header {{
        font-size: 24px;
        font-weight: bold;
        margin: 20px 0 10px 0;
        text-align: center;
        color: #2c3e50;
    }}
    </style>

    <div class="damper-header">TYPE OF DAMPER: {damper_type.upper()}</div>
    {html_table}
    """

    # Save Excel with flat columns
    safe_damper_type = "".join(c if c.isalnum() else "_" for c in damper_type)
    filename = f"Type_Analysis_{safe_damper_type}.xlsx"
    report_file = os.path.join(REPORT_FOLDER, filename)

    with pd.ExcelWriter(report_file, engine='openpyxl') as writer:
        flat_columns = [f"{col[0]} - {col[1]}" for col in final_table.columns]
        final_table_flat = final_table.copy()
        final_table_flat.columns = flat_columns
        final_table_flat.reset_index(names='Make', inplace=True)

        # Title header
        title_df = pd.DataFrame([[f"TYPE OF DAMPER: {damper_type.upper()}"]], columns=[""])
        title_df.to_excel(writer, sheet_name="Summary", index=False, header=False, startrow=0)
        final_table_flat.to_excel(writer, sheet_name="Summary", index=False, startrow=2)

    return jsonify({
        "table_html": table_html,
        "download_link": f"/download_analysis?file={filename}"
    })


@type_analysis_bp.route("/download_analysis")
def download_analysis():
    filename = request.args.get("file")
    if not filename or '..' in filename or '/' in filename:
        return jsonify({"error": "Invalid filename"}), 400

    file_path = os.path.join(REPORT_FOLDER, filename)
    if not os.path.isfile(file_path):
        return jsonify({"error": "File not found"}), 404

    return send_from_directory(REPORT_FOLDER, filename, as_attachment=True)


@type_analysis_bp.route("/get_damper_types")
def get_damper_types():
    df, error = get_google_sheets_data()
    if error:
        return jsonify({"error": f"Google Sheets Error: {error}"}), 500

    if "TYPE OF DAMPER" not in df.columns:
        return jsonify({"error": "TYPE OF DAMPER column missing!"}), 404

    unique_types = df["TYPE OF DAMPER"].dropna().unique().tolist()
    unique_types = sorted(set(t.strip().upper() for t in unique_types))

    return jsonify({"types": unique_types})


@type_analysis_bp.route("/analysis_type")
def analysis_type_page():
    return render_template("analysis_type.html")
