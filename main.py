import json
import os
import time
import threading
import requests
import schedule
from flask import Flask
from playwright.sync_api import sync_playwright
from telegram import Bot

# === Config ===
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Render Env
CHAT_ID = os.getenv("CHAT_ID")                # Render Env

app = Flask(__name__)

QUERY = {
    "query": """query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) {
      searchJobCardsByLocation(searchJobRequest: $searchJobRequest) {
        jobCards {
          jobId
          jobTitle
          locationName
          city
          totalPayRateMax
          totalPayRateMaxL10N
          employmentType
        }
      }
    }""",
    "variables": {
        "searchJobRequest": {
            "locale": "en-GB",
            "country": "United Kingdom",
            "keyWords": "Warehouse Operative",
            "equalFilters": [],
            "containFilters": [{"key": "isPrivateSchedule", "val": ["true","false"]}],
            "rangeFilters": [],
            "orFilters": [],
            "dateFilters": [],
            "sorters": [{"fieldName": "totalPayRateMax", "ascending": "false"}],
            "pageSize": 20,
            "consolidateSchedule": True
        }
    }
}


def get_auth_token():
    """Grab session token from Amazon Jobs page."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.jobsatamazon.co.uk/app#/jobSearch?query=Warehouse%20Operative&locale=en-GB",
                  wait_until="networkidle")
        cookies = page.context.cookies()
        browser.close()

        for c in cookies:
            if "Session" in c.get("value", ""):
                print("✅ AUTH_TOKEN found.")
                return f"Bearer {c['value']}"
        print("⚠️ AUTH_TOKEN not found.")
        return None


def fetch_jobs(auth_token):
    headers = {
        "authorization": auth_token,
        "content-type": "application/json",
        "origin": "https://www.jobsatamazon.co.uk",
        "accept": "text/html",
        "referer": "https://www.jobsatamazon.co.uk/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    print("📡 Fetching jobs...")
    fetchingjobs = "📡 Fetching jobs..."
    send_telegram_message(fetchingjobs)
    r = requests.post(GRAPHQL_URL, headers=headers, data=json.dumps(QUERY))
    return r.json()


def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram not configured.")
        return
    bot = Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=text)


def job_runner():
    """Fetch jobs and send top 5 to Telegram."""
    token = get_auth_token()
    if not token:
        print("❌ No token, skipping.")
        return
    data = fetch_jobs(token)
    jobs = data.get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])
    if not jobs:
        print("⚠️ No jobs found.")
        nojobs = "⚠️ No jobs found."
        send_telegram_message(nojobs)
        return

    msg = "🧭 *Latest Amazon Jobs (Sheffield)*\n\n"
    for j in jobs[:5]:
        msg += f"🏷️ {j['jobTitle']} — {j['locationName']}\n💷 {j.get('totalPayRateMaxL10N','N/A')}\n\n"

    print(msg)
    send_telegram_message(msg)


# === Scheduler Loop ===
def scheduler_loop():
    schedule.every(1).hours.do(job_runner)
    job_runner()  # run immediately
    while True:
        schedule.run_pending()
        time.sleep(60)


# === Flask Web Service (bind port for Render) ===
@app.route("/")
def home():
    return "✅ Amazon Job Bot is running (Online).."
    livecheck = "✅ Amazon Job Bot is running (Online)."
    send_telegram_message(livecheck)


if __name__ == "__main__":
    threading.Thread(target=scheduler_loop, daemon=True).start()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    send_telegram_message(port)


