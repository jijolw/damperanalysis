import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Spreadsheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1LUQhz49MVcnhnk3UuLleI_VYMgFNWV1YBVPbHlfdjpc/edit#gid=0"

def get_google_sheets_data():
    try:
        print("Starting get_google_sheets_data()...")

        # Load credentials from environment variable
        cred_json = os.environ.get("GOOGLE_CREDS")
        if not cred_json:
            raise Exception("GOOGLE_CREDS environment variable not set")

        # Convert JSON string to dictionary
        cred_dict = json.loads(cred_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(cred_dict, scopes=scope)
        client = gspread.authorize(creds)

        print("Authorized client.")
        sheet = client.open_by_url(SHEET_URL).sheet1
        print("Opened sheet.")

        data = sheet.get_all_records()
        print(f"Retrieved {len(data)} rows from sheet.")
        df = pd.DataFrame(data)
        return df, None
    except Exception as e:
        print("ERROR in get_google_sheets_data:", e)
        return pd.DataFrame(), str(e)

def categorize_age(days):
    if days is None or days == "" or str(days).lower() == "nan":
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

# Create reports folder if it doesn't exist
REPORT_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
os.makedirs(REPORT_FOLDER, exist_ok=True)
