import os
import pandas as pd
from flask import Blueprint, request, render_template, session, send_file, redirect, url_for
from .utils import get_google_sheets_data  # ✅ Use shared utility

make_analysis_bp = Blueprint("make_analysis", __name__)
REPORT_FOLDER = "reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)

def categorize_age(age_days):
    try:
        age_days = float(age_days)
        if age_days < 730:
            return "Less than 2 years"
        elif age_days < 1095:
            return "2-3 years"
        elif age_days < 1825:
            return "3-5 years"
        else:
            return "Above 5 years"
    except ValueError:
        return "Above 5 years"

@make_analysis_bp.route("/select_make", methods=["GET", "POST"])
def select_make():
    df, error = get_google_sheets_data()
    if error:
        return error
    makes = ["ALL"] + sorted(df['Make'].dropna().unique().tolist()) + ["NONE"]
    if request.method == "POST":
        make = request.form.get("make")
        return redirect(url_for('make_analysis.analyze_make', value=make))
    
    return render_template("select_make.html", makes=makes)

@make_analysis_bp.route("/analyze_make", methods=["GET"])
def analyze_make():
    make = request.args.get("value")
    df, error = get_google_sheets_data()
    if error:
        return error
    
    # ✅ Ensure 'Test date time' column is converted to datetime
    df["Test date time"] = pd.to_datetime(df["Test date time"], errors="coerce")

    # ✅ Retrieve date range from session
    start_date = session.get("start_date")
    end_date = session.get("end_date")

    if not start_date or not end_date:
        return redirect(url_for("home"))  # Redirect if no dates are set in session

    try:
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
    except ValueError:
        return "Invalid date format in session."

    # ✅ Filter the dataframe based on the selected date range
    df = df[(df["Test date time"] >= start_dt) & (df["Test date time"] <= end_dt)]

    required_columns = ['Make', 'TYPE OF DAMPER', 'Age', 'Test Result']
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        return f"Error: Missing required columns - {', '.join(missing)}"
    
    df["Age"] = df["Age"].astype(str).str.replace(" days", "", regex=True).str.strip()
    df["Age"] = df["Age"].apply(lambda x: 1460 if x == "" or not x.isnumeric() else float(x))
    df["Age Group"] = df["Age"].apply(categorize_age)
    
    if make != "ALL" and make != "NONE":
        df_filtered = df[df['Make'] == make].copy()
    else:
        df_filtered = df.copy()
    
    if df_filtered.empty:
        return f"No data available for Make: {make}"
    
    df_filtered["Failed"] = (df_filtered["Test Result"] == "FAIL").astype(int)
    df_filtered["Total"] = 1
    
    summary = df_filtered.groupby(["TYPE OF DAMPER", "Age Group"]).agg(
        Failures=('Failed', 'sum'),
        Total_Receipts=('Total', 'sum')
    ).reset_index()
    
    damper_types = df_filtered["TYPE OF DAMPER"].unique().tolist()
    columns_age_groups = ["Less than 2 years", "2-3 years", "3-5 years", "Above 5 years", "Total"]
    columns_metrics = ["Failures", "Total", "Failure %"]
    
    column_tuples = [(age, metric) for age in columns_age_groups for metric in columns_metrics]
    column_index = pd.MultiIndex.from_tuples(column_tuples)
    final_table = pd.DataFrame(index=damper_types, columns=column_index)
    
    for damper_type in damper_types:
        for age_group in columns_age_groups[:-1]:
            subset = summary[(summary['TYPE OF DAMPER'] == damper_type) & (summary['Age Group'] == age_group)]
            failures = subset['Failures'].sum() if not subset.empty else 0
            total = subset['Total_Receipts'].sum() if not subset.empty else 0
            failure_pct = (failures / total * 100) if total > 0 else 0
            
            final_table.loc[damper_type, (age_group, 'Failures')] = int(failures)
            final_table.loc[damper_type, (age_group, 'Total')] = int(total)
            final_table.loc[damper_type, (age_group, 'Failure %')] = f"{failure_pct:.2f}%"
        
        damper_subset = summary[summary['TYPE OF DAMPER'] == damper_type]
        total_failures = damper_subset['Failures'].sum()
        total_receipts = damper_subset['Total_Receipts'].sum()
        total_percent = (total_failures / total_receipts * 100) if total_receipts > 0 else 0
        
        final_table.loc[damper_type, ('Total', 'Failures')] = int(total_failures)
        final_table.loc[damper_type, ('Total', 'Total')] = int(total_receipts)
        final_table.loc[damper_type, ('Total', 'Failure %')] = f"{total_percent:.2f}%"
    
    final_table.loc['All Types'] = pd.Series(dtype='object')
    
    for age_group in columns_age_groups[:-1]:
        age_subset = summary[summary['Age Group'] == age_group]
        age_failures = age_subset['Failures'].sum()
        age_total = age_subset['Total_Receipts'].sum()
        age_percent = (age_failures / age_total * 100) if age_total > 0 else 0
        
        final_table.loc['All Types', (age_group, 'Failures')] = int(age_failures)
        final_table.loc['All Types', (age_group, 'Total')] = int(age_total)
        final_table.loc['All Types', (age_group, 'Failure %')] = f"{age_percent:.2f}%"
    
    total_failures = summary['Failures'].sum()
    total_receipts = summary['Total_Receipts'].sum()
    total_percent = (total_failures / total_receipts * 100) if total_receipts > 0 else 0
    
    final_table.loc['All Types', ('Total', 'Failures')] = int(total_failures)
    final_table.loc['All Types', ('Total', 'Total')] = int(total_receipts)
    final_table.loc['All Types', ('Total', 'Failure %')] = f"{total_percent:.2f}%"
    
    final_table = final_table.fillna(0).infer_objects(copy=False)
    display_table = final_table.reset_index().rename(columns={'index': 'TYPE OF DAMPER'})
    
    # Heading for web page
    make_heading = f"<h4><strong>Failure Analysis for Make: <span style='color:#3c6382'>{make}</span></strong></h4>"
    table_html = display_table.to_html(classes="table table-bordered table-hover", escape=False, index=False)
    
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
        padding: 8px;
        border: 1px solid #ddd;
    }}
    .table td {{
        text-align: center;
        padding: 8px;
        border: 1px solid #ddd;
        background-color: #f9f9f9;
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
    </style>
    {make_heading}
    {table_html}
    """
    
    # Save to Excel with heading
    safe_make = "".join(c if c.isalnum() else "_" for c in make)
    report_file = os.path.join(REPORT_FOLDER, f"Make_Analysis_{safe_make}.xlsx")
    
    with pd.ExcelWriter(report_file, engine='openpyxl') as writer:
        flat_columns = [f"{col[0]} - {col[1]}" for col in final_table.columns]
        final_table_flat = final_table.copy()
        final_table_flat.columns = flat_columns
        final_df = final_table_flat.reset_index(names='TYPE OF DAMPER')
        final_df.to_excel(writer, sheet_name="Summary", index=False, startrow=1)
        
        # Merge and format heading in Excel
        workbook = writer.book
        worksheet = writer.sheets["Summary"]
        heading_text = f"Failure Analysis Report for Make: {make}"
        worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(final_df.columns))
        cell = worksheet.cell(row=1, column=1)
        cell.value = heading_text
        cell.font = cell.font.copy(bold=True, size=14)
    
    session["report_file"] = report_file
    
    return render_template(
        "analysis_make.html",
        table_html=table_html,
        download_link=url_for('make_analysis.download_make_analysis'),
        make=make
    )

@make_analysis_bp.route("/download_make_analysis")
def download_make_analysis():
    report_file = session.get("report_file")
    if not report_file or not os.path.exists(report_file):
        return "No report available. Please generate a report first.", 404
    return send_file(report_file, as_attachment=True)
