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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

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
                    return f"Bearer {cookie['value']}"
    except Exception as e:
        print(f"❌ Playwright token fetch failed: {e}")
    return None

# === TELEGRAM ALERT ===
def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"⚠️ Telegram send error: {e}")

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
              totalPayRateMax
              locationName
              totalPayRateMaxL10N
              employmentType
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
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            job_cards = data.get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])
            print(f"📦 Found {len(job_cards)} jobs.")

            for job in job_cards:
                job_id = job.get("jobId")
                if job_id not in seen_jobs:
                    seen_jobs.add(job_id)
                    title = job.get("jobTitle")
                    city = job.get("city")
                    pay = job.get("totalPayRateMax")
                    msg = f"💼 *{title}* in {city}\n💰 Pay: £{pay}/hr\n🔗 https://www.jobsatamazon.co.uk/app#/jobDetail/{job_id}"
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
    while True:
        print("⏳ Running scheduled job check...")
        token = loop.run_until_complete(get_auth_token())
        if token:
            fetch_jobs(token)
        else:
            print("⚠️ Could not get session token.")
        time.sleep(3600)  # every hour

# === FLASK ROUTE (Render needs this port open) ===
@app.route("/")
def home():
    return "✅ Amazon Job Bot is running online."

# === START EVERYTHING ===
if __name__ == "__main__":
    threading.Thread(target=job_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
