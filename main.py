import os
import time
import threading
import requests
from playwright.sync_api import sync_playwright
from flask import Flask

# ------------------ SETTINGS ------------------
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "Warehouse Operative")
COUNTRY = os.getenv("COUNTRY", "United Kingdom")
LOCALE = os.getenv("LOCALE", "en-GB")
PAGE_SIZE = int(os.getenv("PAGE_SIZE", 100))
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", 3600))  # seconds
WAIT_TIME_MS = int(os.getenv("WAIT_TIME_MS", 5000))           # ms

# Telegram Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

# GraphQL Endpoint
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"

printed_job_ids = set()

# ------------------ TELEGRAM FUNCTION ------------------
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("📨 Telegram alert sent.")
    except Exception as e:
        print(f"⚠️ Telegram Error: {e}")

# ------------------ GET AUTH TOKEN ------------------
def get_auth_token():
    token = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        def handle_request(request):
            nonlocal token
            if "graphql" in request.url:
                auth = request.headers.get("authorization")
                if auth and auth.startswith("Bearer "):
                    token = auth.replace("Bearer ", "")
        page.on("request", handle_request)
        page.goto(f"https://www.jobsatamazon.co.uk/app#/jobSearch?query={SEARCH_QUERY.replace(' ', '%20')}&locale={LOCALE}")
        page.wait_for_timeout(WAIT_TIME_MS)
        browser.close()
    if token:
        print("🔑 Fetched new AUTH_TOKEN")
    else:
        print("⚠️ Failed to fetch AUTH_TOKEN")
    return token

# ------------------ FETCH JOBS ------------------
def fetch_jobs(auth_token):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }

    payload = {
        "operationName": "searchJobCardsByLocation",
        "variables": {
            "searchJobRequest": {
                "locale": LOCALE,
                "country": COUNTRY,
                "keyWords": SEARCH_QUERY,
                "equalFilters": [],
                "containFilters": [{"key":"isPrivateSchedule","val":["true","false"]}],
                "rangeFilters": [],
                "orFilters": [],
                "dateFilters": [],
                "sorters":[{"fieldName":"totalPayRateMax","ascending":"false"}],
                "pageSize": PAGE_SIZE,
                "consolidateSchedule": True
            }
        },
        "query": """
        query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) {
          searchJobCardsByLocation(searchJobRequest: $searchJobRequest) {
            nextToken
            jobCards {
              jobId
              jobTitle
              city
              jobType
              totalPayRateMax
            }
          }
        }
        """
    }

    try:
        response = requests.post(GRAPHQL_URL, json=payload, headers=headers, timeout=15)
        data = response.json()
        jobs = data["data"]["searchJobCardsByLocation"]["jobCards"]
        return jobs
    except Exception as e:
        print(f"⚠️ Error fetching jobs: {e}")
        return []

# ------------------ BOT LOOP ------------------
def run_bot():
    global printed_job_ids
    print(f"🟢 Amazon Job Bot started (Render Web Service)")
    print(f"🔍 Searching for '{SEARCH_QUERY}' in {COUNTRY}\n")

    while True:
        auth_token = get_auth_token()
        if not auth_token:
            print("⚠️ Cannot continue without AUTH_TOKEN. Retrying in 5 minutes...")
            time.sleep(300)
            continue

        jobs = fetch_jobs(auth_token)
        new_jobs = []

        for job in jobs:
            job_id = job.get("jobId")
            if job_id and job_id not in printed_job_ids:
                printed_job_ids.add(job_id)
                new_jobs.append(job)

        if new_jobs:
            message = f"🧱 <b>{SEARCH_QUERY} Jobs Update in {COUNTRY}</b>\n\n"
            for job in new_jobs:
                line = f"- {job['jobTitle']} | {job['city']} | {job['jobType']} | £{job.get('totalPayRateMax', 'N/A')}"
                message += line + "\n"
                print(line)
            send_telegram_message(message)
        else:
            print("No new jobs found.")

        print(f"\n⏳ Waiting {REFRESH_INTERVAL/60:.0f} minutes before next check...\n")
        time.sleep(REFRESH_INTERVAL)

# ------------------ FLASK APP FOR RENDER ------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Amazon Job Bot is running! 🔥"

# ------------------ START BOT IN THREAD ------------------
if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
