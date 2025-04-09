import streamlit as st
import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Load the API key
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

# API details
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

# UI layout
st.title("🛡️ AD Lockout Diagnosis Bot")
st.write("Upload a sample AD lockout log and get a smart AI diagnosis.")

uploaded_file = st.file_uploader("Upload a log file (.txt)", type=["txt"])

if uploaded_file:
    log_data = uploaded_file.read().decode("utf-8")

    with st.expander("🔍 Log Preview"):
        st.code(log_data, language="text")

    # Build smart prompt
    prompt = f"""
    You are a senior Active Directory incident response analyst. Analyze the following log entry and return ONLY a JSON object with:

    - root_cause: a 1-sentence explanation of the most likely cause
    - confidence_score: number from 1–100
    - recommended_fix: 1-line solution to fix the issue

    Consider deeper issues like:
    - Mobile apps with old passwords
    - Outlook/Gmail sync loops
    - Background services or mapped drives
    - VPN, cached creds, remote logins, etc.

    Log:
    {log_data}
    """

    if st.button("🧠 Diagnose Lockout"):
        with st.spinner("Analyzing with AI..."):
            response = requests.post(API_URL, headers=headers, json={"inputs": prompt})

            try:
                ai_raw = response.json()[0]["generated_text"]
                json_start = ai_raw.find("{")
                json_text = ai_raw[json_start:].strip()
                result = json.loads(json_text)

                st.success("✅ AI Diagnosis Complete")
                st.json(result)

                # Save to audit
                audit_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "log": log_data,
                    "diagnosis": result
                }

                with open("audit/audit_log.json", "a") as f:
                    json.dump(audit_entry, f)
                    f.write("\n")

                st.download_button("⬇️ Download Diagnosis", json.dumps(result, indent=2), file_name="diagnosis.json")

            except Exception as e:
                st.error("❌ Failed to parse AI response.")
                st.text(response.json())
