import unicodedata
from fpdf import FPDF
import pydeck as pdk
import streamlit as st
import json
import os
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
import matplotlib.pyplot as plt
from collections import Counter
from rapidfuzz import process


# Load token
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

# Load sample logs


@st.cache_data
def load_sample_logs():
    try:
        with open("demo_data/sample_logs.jsonl", "r") as f:
            return [json.loads(line) for line in f.readlines()]
    except:
        return []

# Convert logs to DataFrame


def logs_to_df(logs):
    return pd.DataFrame(logs)

# Build AI prompt


def build_prompt(question, logs):
    summary = "\n".join([
        f"[{log['timestamp']}] User: {log['user']}, Device: {log['device']}, IP: {log['ip']}, Cause: {log['cause']}, Location: {log['location']}"
        for log in logs
    ])
    return f"""
You are an enterprise security assistant trained to help diagnose Active Directory lockouts.

Use the following logs to answer the user's question as clearly and helpfully as possible.

Logs:
{summary}

User's question:
{question}
"""

# Call Hugging Face API


def ask_ai(prompt):
    try:
        response = requests.post(
            API_URL, headers=headers, json={"inputs": prompt})
        result = response.json()

        # Hugging Face returned an error object
        if isinstance(result, dict) and "error" in result:
            return f"❌ Hugging Face API Error: {result['error']}"

        # Expected response: list with generated_text
        if isinstance(result, list) and len(result) > 0:
            if "generated_text" in result[0]:
                return result[0]["generated_text"]
            else:
                return f"❌ No 'generated_text' in response: {result[0]}"

        # Unexpected structure
        return f"❌ Unexpected response structure: {result}"

    except Exception as e:
        return f"❌ Failed to contact Hugging Face API: {e}"


# UI setup
st.set_page_config(page_title="AI Lockout Assistant", layout="wide")
st.title("🛡️ AI Lockout Assistant — Partner Demo")

logs = load_sample_logs()
if not logs:
    st.error("No demo data found.")
    st.stop()

df = logs_to_df(logs)

# 📊 Section: Overview Cards
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🔁 Total Lockouts", len(df))
with col2:
    st.metric("👥 Unique Users", df['user'].nunique())
with col3:
    st.metric("📍 Unique Locations", df['location'].nunique())

st.markdown("---")

# 📊 Section: Charts
st.subheader("📊 Lockout Trends")

col4, col5 = st.columns(2)

with col4:
    st.markdown("**Top Locked Out Users**")
    user_counts = df['user'].value_counts().head(5)
    st.bar_chart(user_counts)

with col5:
    st.markdown("**Lockouts by Device Type**")
    device_counts = df['device'].apply(
        lambda x: x.split()[0]).value_counts().head(5)
    st.bar_chart(device_counts)

st.markdown("---")
st.markdown("---")
st.subheader("🗺️ Lockout Source Map")

# Mock location → lat/lon mapping (demo purposes only)
location_coords = {
    "Raleigh, NC": (35.7796, -78.6382),
    "Charlotte, NC": (35.2271, -80.8431),
    "Remote (VPN)": (37.0902, -95.7129),  # center of USA
    "Atlanta, GA": (33.7490, -84.3880),
    "Datacenter": (39.1031, -84.5120),  # Cincinnati
    "Unknown": (0, 0)
}

df["lat"] = df["location"].apply(
    lambda loc: location_coords.get(loc, (0, 0))[0])
df["lon"] = df["location"].apply(
    lambda loc: location_coords.get(loc, (0, 0))[1])


# Create a pydeck layer from your DataFrame
layer = pdk.Layer(
    "ScatterplotLayer",
    data=df,
    get_position="[lon, lat]",
    get_radius=80000,
    get_fill_color=[255, 140, 0, 160],
    pickable=True,
)

# Set initial view state over the U.S.
view_state = pdk.ViewState(
    latitude=37.0902,
    longitude=-95.7129,
    zoom=3,
    pitch=0
)

# Combine into a pydeck chart object
deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip={"text": "User: {user}\nLocation: {location}\nIP: {ip}"}
)

# Show in Streamlit
st.pydeck_chart(deck)


# 💬 AI Assistant
st.subheader("💬 Ask About Lockouts (AI Assistant)")

st.markdown("### 💬 Ask About a Specific User")

# Free-text input for partial username
user_input = st.text_input("Enter the username (or part of it):")

selected_user = None

if user_input:
    known_users = df["user"].dropna().unique().tolist()
    best_match = None
    score = 0

    # Fuzzy match the input
    if len(known_users) > 0:
        from rapidfuzz import process
        best_match, score, _ = process.extractOne(user_input, known_users)

    if best_match and score >= 70:
        st.info(f"Did you mean: **{best_match}**? (Confidence: {score:.1f})")
        if st.button("✅ Yes, use this user"):
            selected_user = best_match
    else:
        st.warning("No close match found. Try another name.")

if selected_user:
    custom_detail = st.text_input("Optional: Add extra context (e.g. 'locked out 3 times today')")
    if st.button("🔍 Analyze Lockout"):
        full_question = f"Why is {selected_user} getting locked out?"
        if custom_detail:
            full_question += f" {custom_detail}"
        with st.spinner("Analyzing..."):
            prompt = build_prompt(full_question, logs)
            answer = ask_ai(prompt)
        st.success("✅ AI Response:")
        st.write(answer)


    # 📤 Export Section
st.markdown("---")
st.subheader("📥 Export Reports")
st.markdown("---")
st.subheader("🛠 Remediation Playbook")

# Get unique causes from the logs
causes = df["cause"].dropna().unique()
fixes = []

for cause in causes:
    if "mobile" in cause or "gmail" in cause or "mail app" in cause:
        fixes.append(
            "📱 Ask user to update saved credentials on mobile apps (Gmail, Outlook, iOS Mail).")
    if "cached" in cause:
        fixes.append(
            "🧹 Clear cached credentials from user profile or credential manager.")
    if "brute" in cause:
        fixes.append(
            "🛡️ Check firewall rules and enable lockout threshold alerts.")
    if "service account" in cause or "script" in cause:
        fixes.append(
            "🔁 Rotate service account passwords and update in all scripts.")
    if "scheduled task" in cause:
        fixes.append("📅 Review all scheduled tasks for outdated logins.")
    if "vpn" in cause:
        fixes.append("🌐 Confirm VPN is not retrying with old credentials.")

for fix in set(fixes):
    st.markdown(f"- {fix}")

# CSV Export
csv_data = df.to_csv(index=False)
st.download_button("⬇️ Download CSV", data=csv_data,
                   file_name="lockouts.csv", mime="text/csv")

# PDF Export


class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Lockout Report", ln=True, align="C")

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def clean_text(text):
    # Normalize unicode characters and remove non-latin1 safely
    text = unicodedata.normalize("NFKD", text)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf(summary_text):
    clean_summary = clean_text(summary_text)
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, clean_summary)
    return pdf.output(dest="S").encode("latin-1", errors="replace")


if st.button("⬇️ Generate PDF Summary"):
    top_user = df['user'].value_counts().idxmax()
    top_cause = df['cause'].value_counts().idxmax()
    summary = f"""
    Lockout Summary Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}

    Total Lockouts: {len(df)}
    Unique Users: {df['user'].nunique()}
    Top Locked Out User: {top_user}
    Most Common Cause: {top_cause}

    Thank you for using the AI Lockout Assistant.
    """
    pdf_bytes = generate_pdf(summary)
    st.download_button("📄 Download PDF", data=pdf_bytes,
                       file_name="lockout_summary.pdf", mime="application/pdf")

# 📂 Raw logs
with st.expander("📄 View Full Log Records"):
    st.dataframe(df)
