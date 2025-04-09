import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Load Hugging Face API token from .env
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

# Hugging Face API setup
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

# Step 1: Read input log file
with open("logs/sample_log.txt", "r") as file:
    log_data = file.read()

# Step 2: Build AI prompt to detect deeper lockout issues
prompt = f"""
You are a senior Active Directory incident response analyst. Analyze the following log entry and return ONLY a JSON object with:

- root_cause: a 1-sentence explanation of the most likely cause
- confidence_score: number from 1–100
- recommended_fix: 1-line solution to fix the issue

Also consider deeper issues such as:
- Mobile devices (iOS/Android) using saved passwords after a reset
- Outlook or Gmail sync loops
- Background Windows services using old credentials
- Mapped drives retrying logins
- Cached credentials from old sessions
- Users logged into multiple machines
- VPN-triggered re-auth loops
- Scheduled tasks or service accounts
- Stale tokens or password change not propagated

Log:
{log_data}
"""

# Step 3: Send request to Hugging Face
response = requests.post(API_URL, headers=headers, json={"inputs": prompt})

# Step 4: Extract and parse result
try:
    ai_raw = response.json()[0]['generated_text']
    print("\n--- Raw AI Output ---")
    print(ai_raw)

    # Extract just the JSON portion
    json_start = ai_raw.find('{')
    json_text = ai_raw[json_start:].strip()

    ai_message = json.loads(json_text)

    print("\n--- Final Diagnosis ---")
    print(f"Root Cause       : {ai_message.get('root_cause')}")
    print(f"Confidence Score : {ai_message.get('confidence_score')}")
    print(f"Recommended Fix  : {ai_message.get('recommended_fix')}")

    # Step 5: Save to audit log
    audit_entry = {
        "timestamp": datetime.now().isoformat(),
        "log": log_data,
        "diagnosis": ai_message
    }

    with open("audit/audit_log.json", "a") as f:
        json.dump(audit_entry, f)
        f.write("\n")

except Exception as e:
    print("\n⚠️ Error parsing AI response.")
    print("Details:", e)
    print("Raw response:", response.json())
