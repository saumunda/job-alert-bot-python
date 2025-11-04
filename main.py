import json
import os
import time
import threading
import requests
import schedule
from flask import Flask
from playwright.sync_api import sync_playwright
from telegram import Bot

# === Configuration ===
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # add in Render Dashboard
CHAT_ID = os.getenv("CHAT_ID")                # your Telegram chat ID

app = Flask(__name__)

QUERY = {
    "query": """query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) {
      searchJobCardsByLocation(searchJobRequest: $searchJobRequest) {
        jobCards {
          jobId
          jobTitle
          locationName
          city
          totalPayRateMaxL10N
          employmentType
        }
      }
    }""",
    "variables": {
        "searchJobRequest": {
            "locale": "en-GB",
            "country": "United Kingdom",
            "keyWords": "Sheffield",
            "equalFilters": [],
            "containFilters": [{"key": "isPrivateSchedule", "val": ["true", "false"]}],
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
    """Open Amazon jobs site silently and get session cookie."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.jobsatamazon.co.uk/app#/jobSearch?query=Sheffield&locale=en-GB", wait_until="networkidle")
        cookies = page.context.cookies()
        browser.close()

        for c in cookies:
            if "Session" in c.get("value", ""):
                print("✅ AUTH_TOKEN found.")
                return f"Bearer {c['value']}"
        print("⚠️ AUTH_TOKEN not found.")
        return None


def fetch_jobs(auth_token):
    """Run the GraphQL query using the live token."""
    headers = {
        "authorization": auth_token,
        "content-type": "application/json",
        "origin": "https://www.jobsatamazon.co.uk",
        "referer": "https://www.jobsatamazon.co.uk/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    print("📡 Fetching jobs...")
    r = requests.post(GRAPHQL_URL, headers=headers, data=json.dumps(QUERY))
    return r.json()


def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram not configured.")
        return
    bot = Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=text)


def job_runner():
    """Main job: fetch & send jobs every hour."""
    token = get_auth_token()
    if not token:
        print("❌ No token found, skipping.")
        return
    data = fetch_jobs(token)
    jobs = data.get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])
    if not jobs:
        print("⚠️ No jobs found.")
        return

    message = "🧭 *Latest Amazon Jobs in Sheffield:*\n\n"
    for j in jobs[:5]:  # send top 5
        message += f"🏷️ {j['jobTitle']} — {j['locationName']}\n💷 {j.get('totalPayRateMaxL10N', 'N/A')}\n\n"

    print(message)
    send_telegram_message(message)


# === Scheduler ===
def scheduler_loop():
    schedule.every(1).hours.do(job_runner)
    job_runner()  # run immediately
    while True:
        schedule.run_pending()
        time.sleep(60)


# === Flask Web Service (for Render port binding) ===
@app.route("/")
def home():
    return "✅ Amazon Job Bot is running."


if __name__ == "__main__":
    # Start background scheduler
    threading.Thread(target=scheduler_loop, daemon=True).start()

    # Bind to Render port
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
