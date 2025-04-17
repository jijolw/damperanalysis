import os
import json
import pandas as pd
import gspread
import base64
from google.oauth2.service_account import Credentials

# Spreadsheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1LUQhz49MVcnhnk3UuLleI_VYMgFNWV1YBVPbHlfdjpc/edit#gid=0"

def get_google_sheets_data():
    try:
        print("Starting get_google_sheets_data()...")
        
        # Load credentials from environment variable - use the same name as the first file
        google_credentials_b64 = os.environ.get("GOOGLE_CREDENTIALS")
        
        if not google_credentials_b64:
            print("Environment variables available:", [k for k in os.environ.keys() if 'GOOGLE' in k.upper()])
            raise Exception("GOOGLE_CREDENTIALS environment variable not set")
        
        # Decode from Base64 first (same as in first file)
        try:
            cred_dict = json.loads(base64.b64decode(google_credentials_b64).decode("utf-8"))
            print("Successfully decoded credentials from Base64")
        except Exception as e:
            print(f"Error decoding credentials from Base64: {e}")
            raise
        
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