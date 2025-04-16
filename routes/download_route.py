import os
from flask import Blueprint, request, session, send_file, current_app

download_bp = Blueprint("download", __name__)

REPORT_FOLDER = "reports"  # Ensure this folder path is defined properly.

@download_bp.route("/download")
def download():
    # Check if analysis file is requested via query parameter
    analysis_file = request.args.get("file")
    if analysis_file:
        file_path = os.path.join(REPORT_FOLDER, analysis_file)
        
        # Debugging: Check the file path
        print(f"Requested file path: {file_path}")
        
        # Ensure the file is within the REPORT_FOLDER to avoid security risks
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            print(f"File not found: {file_path}")
            return "File not found.", 404

    # Fall back to session-stored report file
    report_file = session.get("report_file")
    if not report_file:
        return "No report available in session. Please generate a report first.", 404
    
    # Fix path construction to avoid double 'reports' directory
    report_file_path = os.path.join(REPORT_FOLDER, report_file)  # This should work
    print(f"Stored report file path: {report_file_path}")

    # Ensure the file is within the REPORT_FOLDER
    if os.path.exists(report_file_path):
        return send_file(report_file_path, as_attachment=True)
    
    print(f"Stored report file not found: {report_file_path}")
    return "Stored report file not found.", 404
