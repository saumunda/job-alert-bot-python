import requests
import json
import time
import threading
from flask import Flask
import asyncio
from playwright.async_api import async_playwright

# === CONFIGURATION ===
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"
JOB_PAGE_URL = "https://www.jobsatamazon.co.uk/app#/jobSearch?query=Warehouse%20Operative&locale=en-GB"

# Telegram bot credentials (set as ENV vars on Render)
import os
TELEGRAM_BOT_TOKEN = "8214392800:AAGrRksRKpAD8Oa8H4aByo5XKSwc_9SM9Bo"

# Track jobs already sent
seen_jobs = set()

app = Flask(__name__)

# === TOKEN FETCH USING PLAYWRIGHT (headless browser) ===
async def get_auth_token():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(JOB_PAGE_URL, wait_until="load")
            cookies = await page.context.cookies()
            await browser.close()

            for cookie in cookies:
                if "session" in cookie["name"].lower():
                    print(f"✅ Session cookie found: {cookie['name']}")
                    cokkiecheck = f"✅ Session cookie found: {cookie['name']}"
                    send_telegram_message(cokkiecheck)
                    return f"Bearer {cookie['value']}"
    except Exception as e:
        print(f"❌ Playwright token fetch failed: {e}")
    return None

# === TELEGRAM ALERT (supports multiple chat IDs) ===
def send_telegram_message(message):
    chat_ids = [
        "7943617436",  # your first chat ID
        ""   # your second chat ID (replace this)
    ]

    for chat_id in chat_ids:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            requests.post(url, data=payload)
        except Exception as e:
            print(f"⚠️ Telegram send error to {chat_id}: {e}")

# === JOB FETCH FUNCTION ===
def fetch_jobs(auth_token):
    payload = {
        "operationName": "searchJobCardsByLocation",
        "variables": {
            "searchJobRequest": {
                "locale": "en-GB",
                "country": "United Kingdom",
                "keyWords": "Warehouse Operative",
                "equalFilters": [],
                "containFilters": [{"key": "isPrivateSchedule", "val": ["true", "false"]}],
                "rangeFilters": [],
                "orFilters": [],
                "dateFilters": [],
                "sorters": [{"fieldName": "totalPayRateMax", "ascending": "false"}],
                "pageSize": 20,
                "consolidateSchedule": True
            }
        },
        "query": """
        query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) {
          searchJobCardsByLocation(searchJobRequest: $searchJobRequest) {
            jobCards {
              jobId
              jobTitle
              city
              state
              postalCode
              jobType
              employmentType
              totalPayRateMax
            }
          }
        }
        """
    }

    headers = {
        "Authorization": auth_token,
        "Content-Type": "application/json",
        "Origin": "https://www.jobsatamazon.co.uk",
        "Referer": "https://www.jobsatamazon.co.uk/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            job_cards = data.get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])
            print(f"📦 Found {len(job_cards)} jobs.")
            foundjobs = f"[📦 Currently Available {len(job_cards)} jobs in total.](https://www.jobsatamazon.co.uk/app#/jobSearch)"
            send_telegram_message(foundjobs)
            
            for job in job_cards:
            job_id = job.get("jobId")
            if job_id not in seen_jobs:
                seen_jobs.add(job_id)
                title = job.get("jobTitle")
                city = job.get("city")
                state = job.get("state")
                postal = job.get("postalCode")
                type_job = job.get("jobType")
                emp_type = job.get("employmentType")
                pay = job.get("totalPayRateMax")
                msg = (
                    f"💼 *{title}* in {city}, {state}, {postal}\n"
                    f"💰 Pay: £{pay}/hr\n"
                    f"🕒 Job Type: {type_job}\n"
                    f"📋 Employment Type: {emp_type}\n"
                    f"🔗 https://www.jobsatamazon.co.uk/app#/jobDetail?jobId={job_id}&locale=en-GB"

                )
                print("🔔 New job found:", title)
                send_telegram_message(msg)
        else:
            print("⚠️ GraphQL request failed:", response.status_code, response.text)
    except Exception as e:
        print("⚠️ Fetch error:", e)

# === BACKGROUND JOB LOOP ===
def job_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    DEFAULT_TOKEN = (
        "Bearer Status|unauthenticated|Session|"
        "eyJhbGciOiJLTVMiLCJ0eXAiOiJKV1QifQ.eyJpYXQiOjE3NjIyNzQwOTMsImV4cCI6MTc2MjI3NzY5M30."
        "AQICAHh9Y3eh+eSawH7KZrCzIFETq1dycngugjOljT8N4eCxVgHUjhNAx2EBPruQ8xTeM8qZAAAAtDCBsQYJKoZI"
        "hvcNAQcGoIGjMIGgAgEAMIGaBgkqhkiG9w0BBwEwHgYJYIZIAWUDBAEuMBEEDGMxfXv7ZLciMdQXNAIBEIBt3/"
        "BpJ/Kmb54bc5DlW3X3xyooeyLZxLLLkImLS1O0y9Tnn77otsO4nTxvQBQAz2UOawxNVrk16YDGeNJhpZnxcsjxsRc3TsrItNTEqnT2jbMfup2v1XgK3+dpL+PqzAJIqT2rBXhGRTCrYJeh0w=="
    )

    while True:
        print("⏳ Running scheduled job check...")
        send_telegram_message("⏳ Running scheduled job check...")

        token = None
        for attempt in range(1, 4):  # Retry 3 times
            print(f"🔄 Attempt {attempt}/3 to fetch session token...")
            token = loop.run_until_complete(get_auth_token())

            if token:
                print("✅ Successfully fetched session token.")
                send_telegram_message("✅ Successfully fetched session token.")
                break
            else:
                print(f"⚠️ Attempt {attempt} failed. Retrying in 10s...")
                time.sleep(10)

        if not token:
            print("⚠️ All attempts failed — using default unauthenticated token.")
            token = DEFAULT_TOKEN

        fetch_jobs(token)
        offcheck = ("✅ Amazon Job Bot is Offline..\n\n"
                    "[☕️ Fuel this bot](https://buymeacoffee.com/ukjobs)")
        send_telegram_message(offcheck)
        time.sleep(3600)  # every hour


# === FLASK ROUTE (Render needs this port open) ===
@app.route("/")
def home():
    livecheck = "✅ Amazon Job Bot is running (Online version) ✅"
    send_telegram_message(livecheck)
    return "✅ Amazon Job Bot is running (Online version)"


# === START EVERYTHING ===
if __name__ == "__main__":
    threading.Thread(target=job_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))



