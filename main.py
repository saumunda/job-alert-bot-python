from flask import Flask
import threading
import os
import schedule
import time
import requests
from datetime import datetime

app = Flask(__name__)

# Telegram Bot config
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Job search links
SEARCH_LINKS = {
    "Developer/Data Roles": [
        "https://www.michaelpage.co.uk/jobs/technology/sheffield",
        "https://www.robertwalters.co.uk/information-technology/jobs.html",
        "https://www.wearespinks.com/jobs",
        "https://www.gravitasgroup.com/job-search",
        "https://www.morganhunt.com/jobs/technology",
        "https://itharper.com/job-search",
        "https://isepartners.com/jobs",
        "https://www.jobs.nhs.uk/candidate/search/results?q=data&l=sheffield"
    ],
    "Warehouse/Logistics Roles": [
        "https://www.skills-provision.com/jobs",
        "https://www.michaelpage.co.uk/jobs/logistics",
        "https://www.morganhunt.com/jobs/facilities-management",
        "https://www.gravitasgroup.com/job-search",
        "https://www.jobsatamazon.co.uk/app#/jobSearch"
        
    ]
}

# Function to send Telegram message
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Error sending message:", e)

# Function to generate job alert
def job_alert():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"🕓 <b>Job Updates ({now})</b>\n\n"
    for category, links in SEARCH_LINKS.items():
        msg += f"🔹 <b>{category}</b>\n"
        for link in links:
            msg += f"➡️ {link}\n"
        msg += "\n"
    send_message(msg)
    print(f"[{now}] Job alert sent ✅")

# Scheduler function
def run_schedule():
    # Job alerts four times daily
    schedule.every().day.at("03:15").do(job_alert)
    schedule.every().day.at("09:00").do(job_alert)
    schedule.every().day.at("16:20").do(job_alert)
    schedule.every().day.at("23:00").do(job_alert)
    # Health ping hourly
    schedule.every().hour.do(lambda: requests.get("https://render.com"))

    while True:
        schedule.run_pending()
        time.sleep(60)

# Start scheduler in a background thread
threading.Thread(target=run_schedule, daemon=True).start()

# Minimal Flask endpoint to bind $PORT
@app.route("/")
def index():
    return "Telegram Job Bot is running ✅"

# Run Flask app on $PORT
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
