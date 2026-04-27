import os
import time
import schedule
import datetime
import json
import random
import threading
import asyncio
import requests
from flask import Flask
from playwright.async_api import async_playwright

# === CONFIGURATION ===
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"
JOB_PAGE_URL = "https://www.jobsatamazon.co.uk/app#/jobSearch?query=Warehouse%20Operative&locale=en-GB"

# Mode C settings
INTERVAL_MINUTES = 3    # every 1 minute
ACTIVE_START = datetime.time(9, 0)   # 08:00
ACTIVE_END = datetime.time(12, 0)    # 22:00

# === TELEGRAM SETTINGS (secure from Render env) ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")
CHAT_IDS = [chat.strip() for chat in CHAT_IDS.split(",") if chat.strip()]

if not TELEGRAM_BOT_TOKEN or not CHAT_IDS:
    print("f\n⚠️ Missing Telegram credentials — check Render env variables.")
else:
    print(f"\n✅ Telegram config loaded ({len(CHAT_IDS)} chat IDs).")

# === PROXY & USER-AGENT ROTATION ===
PROXIES = [
    "http://185.199.229.156:7492",
    "http://103.155.54.26:83",
    "http://91.92.155.207:3128",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15 Edg/129.0.0.0",
]

seen_jobs = set()
app = Flask(__name__)

# === TELEGRAM FUNCTION ===
def send_telegram_message(message: str):
    for chat_id in CHAT_IDS:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            response = requests.post(url, data=payload, timeout=10)
            if response.status_code != 200:
                print(f"\n⚠️ Telegram send error {chat_id}: {response.text}")
        except Exception as e:
            print(f"\n⚠️ Telegram send exception to {chat_id}: {e}")

# === FETCH TOKEN USING PLAYWRIGHT ===
async def get_auth_token():
    try:
        proxy = random.choice(PROXIES)
        agent = random.choice(USER_AGENTS)
        print(f"🌐 Using proxy: {proxy}")
        print(f"🧭 Using User-Agent: {agent}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy={"server": proxy}
            )
            context = await browser.new_context(
                user_agent=agent,
                extra_http_headers={
                    "Accept": "text/html",
                    "Referer": "https://www.jobsatamazon.co.uk/"
                }
            )

            page = await context.new_page()
            await page.goto(JOB_PAGE_URL, wait_until="load")

            cookies = await context.cookies()
            await browser.close()

            for cookie in cookies:
                if "session" in cookie["name"].lower():
                    print(f"\n✅ Session cookie found: {cookie['name']}")
                    return f"Bearer {cookie['value']}"

    except Exception as e:
        print(f"\n❌ Playwright token fetch failed: {e}")
    return None

# === FETCH JOB DATA ===
def fetch_jobs(auth_token: str):
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
        "User-Agent": random.choice(USER_AGENTS)
    }

    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=payload, timeout=15)
        if response.status_code != 200:
            print(f"\n⚠️ GraphQL request failed: {response.status_code}")
            return

        data = response.json()
        job_cards = data.get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])
        print(f"\n📦 Found {len(job_cards)} jobs.")

        for job in job_cards:
            job_id = job.get("jobId")
            if job_id not in seen_jobs:
                seen_jobs.add(job_id)
                msg = (
                    f"💼 *{job.get('jobTitle')}*\n"
                    f"📍 {job.get('city')}, {job.get('state')} {job.get('postalCode')}\n"
                    f"💰 £{job.get('totalPayRateMax')}/hr\n"
                    f"🕒 {job.get('jobType')} | {job.get('employmentType')}\n"
                    f"🔗 [View Job](https://www.jobsatamazon.co.uk/app#/jobDetail?jobId={job_id}&locale=en-GB)"
                )
                print(f"\n🔔 New job found:", job.get("jobTitle"))
                send_telegram_message(msg)

        print(f"\n✅ Job fetch complete.")

    except Exception as e:
        print(f"\n⚠️ Fetch error: {e}")

# === BACKGROUND JOB LOOP (with safe delay) ===
def job_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    DEFAULT_TOKEN = "Bearer Status|unauthenticated|Session|exampleToken"

    while True:
        try:
            print(f"\n⏳ Starting scheduled Amazon job check...")
            token = loop.run_until_complete(get_auth_token())
            if not token:
                print(f"\n⚠️ Using fallback token.")
                token = DEFAULT_TOKEN

            fetch_jobs(token)
            print("f\n🕓 Sleeping 1 min before next check.\n")
            time.sleep(60)  # 1 min delay
        except Exception as e:
            print(f"\n⚠️ Loop error: {e}")
            time.sleep(60)  # wait 1 min on error before retry

# === KEEP-ALIVE THREAD (Render idle prevention) ===
def keep_alive():
    url = os.getenv("RENDER_URL")
    if not url:
        return
    while True:
        try:
            requests.get(url, timeout=10)
            print(f"\n🌍 Keep-alive ping sent.")
        except:
            print(f"\n⚠️ Keep-alive failed.")
        time.sleep(180)

def run_job():
    print("🔄 Running job check...")
    now = datetime.datetime.now().time()
    print("⏱ Current time:", now)
    token = get_auth_token()
    if token:
        fetch_jobs(token)
    else:
        print("⚠️ Token error")

def interval_job():
        now = datetime.datetime.now().time()
        print("⏱ Current time:", now)
        if ACTIVE_START <= now <= ACTIVE_END:
            run_job()

schedule.every(INTERVAL_MINUTES).minutes.do(interval_job)
schedule.run_pending()
time.sleep(1)

# === FLASK ENDPOINTS ===
@app.route("/")
def home():
    return "✅ Amazon Job Bot is running online."
    offcheck = (f"\n✅ Amazon Job Bot is running Online..\n" "[☕️ Fuel this bot for running...] (https://buymeacoffee.com/ukjobs)")
    send_telegram_message(offcheck)

@app.route("/forcefetch")
def forcefetch():
    token = asyncio.run(get_auth_token())
    if not token:
        token = "Bearer Status|unauthenticated|Session|exampleToken"
    fetch_jobs(token)
    return "\n✅ Manual job fetch completed."

# === START APP ===
if __name__ == "__main__":
    threading.Thread(target=job_loop, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
