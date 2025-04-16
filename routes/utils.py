import os
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_URL = "https://docs.google.com/spreadsheets/d/1LUQhz49MVcnhnk3UuLleI_VYMgFNWV1YBVPbHlfdjpc/edit#gid=0"
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")

def get_google_sheets_data():
    try:
        print("Starting get_google_sheets_data()...")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        print(f"Using credentials file at: {CREDENTIALS_FILE}")

        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
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
