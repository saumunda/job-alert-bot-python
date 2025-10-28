import requests
import schedule
import time
from datetime import datetime
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

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

def send_message(text):
    """Send Telegram message."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Error sending message:", e)

def job_alert():
    """Send job alert summary."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"🕓 <b>Job Updates ({now})</b>\n\n"
    for category, links in SEARCH_LINKS.items():
        msg += f"🔹 <b>{category}</b>\n"
        for link in links:
            msg += f"➡️ {link}\n"
        msg += "\n"
    send_message(msg)

# 🩺 HEALTH PING: keeps worker alive by sending a silent ping every hour
def health_ping():
    try:
        requests.get("https://render.com")  # lightweight request
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Health ping sent ✅")
    except Exception as e:
        print("Ping failed:", e)

# Schedule alerts (twice per day)
schedule.every().day.at("03:15").do(job_alert)
schedule.every().day.at("09:00").do(job_alert)
schedule.every().day.at("16:20").do(job_alert)
schedule.every().day.at("23:10").do(job_alert)

# Schedule health ping (every hour)
schedule.every().hour.do(health_ping)

print("📡 Bot scheduler with health ping started...")
while True:
    schedule.run_pending()
    time.sleep(60)
